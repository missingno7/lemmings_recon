"""Shared-engine differential for the 03E7 parent and its first native child."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
from cbuild import build,source_files
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

START,BOUNDARY=0x03E7,0x0465
OWN_RANGES=((START,BOUNDARY),)
CHILD_RANGES=((0x0FB2,0x0FF8),)
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
CHILD={i.address:i for a,b in CHILD_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
BOUNDARY_INSTRUCTION=next(v.MD.disasm(v.IMAGE[BOUNDARY:BOUNDARY+3],BOUNDARY))
INS=OWN|CHILD|{BOUNDARY_INSTRUCTION.address:BOUNDARY_INSTRUCTION}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=180,384,100_000,50_000
REPORT=BUILD/'game-initialize-prefix-differential.json'

class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),
              ('child_status',ct.c_uint16),('service_status',ct.c_uint16)]

class VideoServices(ct.Structure):
    _fields_=[('bios',ct.POINTER(v.InterruptService)),('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus))]

class GameServices(ct.Structure):
    _fields_=[('video',ct.POINTER(VideoServices)),('bus',ct.POINTER(v.Bus))]

def cases():
    rows=[]
    for load in v.LOADS:
        for direction,flags in (('forward',0x0AD7),('backward',0x06D7)):
            rows.append(dict(name=f'{direction}-{load:04x}',load=load,seed=0x3E7^load,
                ds=0x6000,ss=0x9000,flags=flags,ax=0xB543))
    rows.extend((
        dict(name='ds-ss-alias',load=v.LOADS[0],seed=0x31A5,ds=0x6800,ss=0x6800,
             flags=0x0AD7,ax=0xC37E),
        dict(name='vga-data-and-stack',load=v.LOADS[1],seed=0x31A6,ds=0xA000,ss=0xA000,
             flags=0x0AD7,ax=0xA55A),
        dict(name='vga-data-separate-stack',load=v.LOADS[0],seed=0x31AA,ds=0xA000,ss=0x9000,
             flags=0x0AD7,ax=0xA55A),
        dict(name='vga-stack-backward',load=v.LOADS[2],seed=0x31A7,ds=0x6000,ss=0xA000,
             flags=0x06D7,ax=0xD4E1),
        dict(name='physical-wrap-forward',load=v.LOADS[0],seed=0x31A8,ds=0x6000,ss=0xFFF0,
             flags=0x0AD7,ax=0xE24C,expected=1,child_status=3),
        dict(name='physical-wrap-backward',load=v.LOADS[2],seed=0x31A9,ds=0x6000,ss=0xFFF0,
             flags=0x06D7,ax=0xF981),
        dict(name='stack-map-overlap',load=v.LOADS[1],seed=0x31AB,ds=0x6000,ss=0x9078,
             sp=0x42B3,flags=0x0AD7,ax=0xA376),
        dict(name='stack-segment-end',load=v.LOADS[2],seed=0x31AC,ds=0x6000,ss=0x7600,
             sp=0x0001,flags=0x0AD7,ax=0x93E2),
        dict(name='video-returned-registers',load=v.LOADS[0],seed=0x31AD,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,returned_state=True),
        dict(name='video-service-unbound',load=v.LOADS[1],seed=0x31AE,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,no_bios=True,expected=1,child_status=3,service_status=0),
        dict(name='video-parent-return-changed',load=v.LOADS[2],seed=0x31AF,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,patch='parent-return',expected=2),
    ))
    return rows

def setup(case):
    memory,device=v.initial_memory(case)
    regs=v.default_regs(case['load'],case['seed'],ds=case['ds'],ss=case['ss'],
                        sp=case.get('sp',0x4AF4),flags=case['flags'])
    regs.update(ip=START,ax=case['ax'])
    for segment in {case['ds'],0x7000}:
        v.put16(memory,segment,0x1FDA,0x3D4,device)
        for n in range(9):v.put16(memory,segment,0x002E+2*n,0xD234,device)
    v.put16(memory,0,0x40,0x0100);v.put16(memory,0,0x42,0xB000)
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return memory,regs,device

class Access(v.BusAccess):
    def __init__(self,*args):
        super().__init__(*args,max_events=MAX_EVENTS,packed_events=True)
        self.outputs=[]
    def out_word(self,port,value,flags,mask=v.FLAGS):
        expected_port=0 if self.c['ds']==self.c['ss'] else 0x3D4
        v.check((port,value)==(expected_port,0x1613),
                f"{self.c['name']}: unexpected game-video word OUT {port:04X}:{value:04X}, expected {expected_port:04X}:1613")
        self.outputs.append((port,value));self.emit('out',port,value,flags,mask)
        if self.c.get('patch')=='parent-return' and 'parent-return' not in self.providers:
            ss=self.r['ss'];sp=self.r.get('sp',0x4AF4)
            self.patch(ss,(sp-2)&0xFFFF,0xD234,'parent-return')

def bios_provider(access,r):
    entry=dict(r);v.check(r['ax']==0x008D,'unexpected BIOS video service')
    if access.c.get('returned_state'):
        r.update(ds=0x7000,es=0x7100,di=0x2200,bp=0xABCD)
    access.service_events.append(dict(entry=entry,returned=dict(r)))
    return 0

def original(case,memory,regs,device):
    access=Access(case,memory,regs,device)
    frames=[];self_state={'child_status':0,'service_status':0}
    def before(machine,instruction):
        if instruction.address==BOUNDARY:
            machine.stop(0)
            return True
        if instruction.mnemonic=='call':frames.append((instruction.address,instruction.address+instruction.size))
        return False
    def expected(machine,offset):
        v.check(bool(frames),'undeclared initializer child return')
        return {frames.pop()[1]}
    def interrupt(machine,number):
        v.check(number==0x10,'undeclared initializer interrupt')
        machine.software_interrupt(0x10,machine.state()['ip'],(0xB000,0x0100),
            None if case.get('no_bios') else bios_provider)
        if machine.stopped:
            self_state['child_status']=3
            self_state['service_status']=machine.service_status
            machine.status=1
    machine=v.OriginalMachine(case,memory,regs,device,True,instructions=INS,access=access,
        outer_returns=lambda m,off:not frames,
        child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
        before=before,interrupt=interrupt,changed_return_status=2,max_steps=MAX_STEPS)
    out=machine.run();out['child_status']=self_state['child_status'];out['service_status']=self_state['service_status']
    out['services']=access.service_events;out['hardware']=access.outputs
    return out

class Native:
    def __init__(self,directory,mutation=0):
        path=build(Path(directory)/f'game-initialize-{mutation}.dll',mutation,'game_initialize')
        self.lib=ct.CDLL(str(path))
        self.fn=self.lib.lmn_initialize_game_core
        self.fn.restype=Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(GameServices)]
    def run(self,case,memory,regs,device):
        memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(case,memory,regs,device)
        callbacks=v.NativeCallbacks(access)
        handler=callbacks.interrupt(bios_provider)
        binding=v.InterruptService(None,handler,0xB000,0x0100)
        video=VideoServices(None if case.get('no_bios') else ct.pointer(binding),
                            ct.pointer(callbacks.ports),ct.pointer(callbacks.bus))
        services=GameServices(ct.pointer(video),ct.pointer(callbacks.bus))
        native_regs=v.Regs(**regs)
        result=self.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(native_regs),ct.byref(services))
        return dict(regs={name:getattr(result.registers,name) for name in v.REG_NAMES},
            status=result.status,child_status=result.child_status,service_status=result.service_status,
            memory=memory,device=device,events=access.events,providers=access.providers,
            cursor=access.cursor,services=access.service_events,hardware=access.outputs)

def independent(case,initial,reference):
    result=reference['regs'];step=-1 if case['flags']&0x400 else 1
    parent_return=0xD234 if case.get('patch')=='parent-return' else BOUNDARY
    v.check(result['cx']==0,'initializer failed to exhaust the second REP count')
    v.check(result['si']==initial['si'],'initializer changed SI')
    if reference['status'] in (0,2):
        v.check(result['ip']==parent_return,'initializer did not preserve the live parent RET target')
        v.check(result['ax']==0x1613,'video child OUT register contract differs')
        v.check((result['flags']&0x400)==(case['flags']&0x400),'video child changed DF')
        expected_di=0x2200 if case.get('returned_state') else (0x42B2+step*0x0642)&0xFFFF
        v.check(result['di']==expected_di,'live DI differs after first child return')
        v.check(result['bp']==(0xABCD if case.get('returned_state') else initial['bp']),
                'live BP differs after first child return')
        slots=(0x6170,0x64D9,0x65D8,0x66D7,0x6817,0x6957,0x6A97,0x6BDB,0x6CFC)
        for n,value in enumerate(slots):
            v.check(v.get16(reference['memory'],result['ds'],0x2E+2*n)==value,
                    f'video child callback slot {n} differs')
        expected_port=0 if case['ds']==case['ss'] else 0x3D4
        v.check(reference['hardware']==[(expected_port,0x1613)],'video child word OUT differs')
    stack_start=(case.get('sp',0x4AF4)-2)&0xFFFF
    frame_offsets={(stack_start+n)&0xFFFF for n in range(2)}
    for first in (-4,-6,-8):
        frame_offsets.update(((case.get('sp',0x4AF4)+first+n)&0xFFFF) for n in range(2))
    for start,count in ((0x0012,0x42A0),(0x42B2,0x0642)):
        for n in range(count):
            offset=(start+step*n)&0xFFFF
            if offset in frame_offsets:continue
            if case['ds']==case['ss'] and reference['status'] in (0,2) and 0x2E<=offset<0x40:continue
            at=v.physical(case['ss'],offset)
            v.check(reference['memory'][at]==0,
                    f'{case["name"]}: ordered stack/SS clear result differs at {offset:04X}')
    v.check(v.get16(reference['memory'],case['ss'],stack_start)==parent_return,
            'actual parent CALL return word differs')
    if case['ds']!=case['ss']:
        ds=case['ds']
        expected=((0,2,0x0218),(2,2,0x0043),(0x10,2,0x0096),(0x12,2,0x0064),
                  (0x1A,1,0),(0x47,1,0xC8),(0x4A,1,0),(0x4D,1,0x50),(0x4E,1,1),
                  (0x4F,1,0),(0x52,1,0),(0x55,1,0),(0x82,1,2),(0x83,1,3),
                  (0x85,1,0x11),(0x86,1,0x11),(0x2A,1,0),(0x1FD3,1,0),(0x1FD4,1,0),
                  (0x20A9,1,0x30),(0x20AA,1,0x30))
        for offset,width,value in expected:
            got=(v.get16(reference['memory'],ds,offset) if width==2 else
                 reference['memory'][v.physical(ds,offset)])
            v.check(got==value,f'{case["name"]}: independent DS field {offset:04X} differs')
    if case.get('sp')==0x42B3:
        v.check(v.get16(reference['memory'],case['ss'],0x42B1)==parent_return,
                'actual parent CALL word was not preserved at the map boundary')
    if case.get('sp')==1:
        v.check(v.get16(reference['memory'],case['ss'],0xFFFF)==parent_return,
                'live parent CALL word across the segment end at SP=1 differs')
    if case['ss']==0xA000:
        for start,count in ((0x0012,0x42A0),(0x42B2,0x0642)):
            for n in range(count):
                offset=(start+step*n)&0xFFFF
                if case['ds']==case['ss'] and reference['status'] in (0,2) and 0x2E<=offset<0x40:continue
                for plane in reference['device'].planes:
                    v.check(plane[offset]==0,f'{case["name"]}: planar clear misses {offset:04X}')

def compare(native,case):
    memory,regs,device=setup(case)
    ref=original(case,bytearray(memory),dict(regs),copy.deepcopy(device))
    expected=(case.get('expected',0),case.get('child_status',0),case.get('service_status',0))
    v.check((ref['status'],ref['child_status'],ref['service_status'])==expected,
            case['name']+f': unexpected original stop {(ref["status"],ref["child_status"],ref["service_status"])}; expected {expected}')
    actual=native.run(case,memory,regs,device)
    v.compare_states(case['name'],actual,ref)
    v.require(actual['hardware']==ref['hardware'],case['name']+': device output differs')
    independent(case,regs,ref)
    return ref

def hashes():
    paths={'tests/game_initialize_prefix.py','tests/verification.py','tests/minimap_vga.py',
        'tools/cbuild.py','tools/difftest.py','tools/bounded_process.py','tools/common.py',
        'tools/unpack.py','metadata/oracle.json','metadata/toolchain-lock.json','assets/vgalemmi.exe',
        'src/entry_services.asm'}
    pending=list(source_files('game_initialize'))
    while pending:
        path=pending.pop();name=path.relative_to(ROOT).as_posix()
        if name in paths:continue
        paths.add(name)
        pending.extend(path.parent/name for name in re.findall(r'#include\s+"([^"]+)"',path.read_text()))
    return {name:sha((ROOT/name).read_bytes()) for name in sorted(paths)}

MUTANTS=((1,'forward-1010'),(2,'backward-1010'),(3,'forward-1010'),(4,'video-parent-return-changed'))

def worker(directory,snapshot):
    before=hashes();v.check(before==json.loads(Path(snapshot).read_text()),'initializer inputs changed')
    native=Native(directory);rows=[];sites=set()
    for case in cases():
        ref=compare(native,case);sites.update(ref['sites'])
        rows.append(dict(case=case['name'],steps=ref['steps'],events=len(ref['events'])))
        del ref;gc.collect()
    v.check(set(OWN)<=sites,'missing initializer sites: '+str(sorted(set(OWN)-sites)))
    mutants=[];lookup={case['name']:case for case in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure('surviving game initialization mutant')
    v.check(before==hashes(),'initializer inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(rows),comparison_count=len(rows),
        native_code_ranges=[list(bound) for bound in OWN_RANGES],own_known_bytes=sum(i.size for i in OWN.values()),
        connected_code_ranges=[list(bound) for bound in CHILD_RANGES],known_connected_bytes=sum(i.size for i in OWN.values())+sum(i.size for i in CHILD.values()),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=[],own_branch_edges=[],mutation_count=len(mutants),mutations=mutants,
        instruction_steps=sum(row['steps'] for row in rows),ordered_bus_events=sum(row['events'] for row in rows),
        rows=rows,input_hashes=before,limits=dict(worker_seconds=SECONDS,windows_process_mib=MEMORY_MIB,
        windows_tree_mib=MEMORY_MIB+256,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='03E7 state initialization and SS interaction/dirty-map clears composed through the actual0462 CALL/RET to native0FB2 video setup. Fourteen memory/frame cases plus BIOS returned registers, unbound BIOS and changed parent RET;20-bit physical wrap, DS/SS alias,VGA,DF and ordered bus/device effects. Stops before0465 palette CALL. Later providers, timer/IRQ schedule, frame loop and full game remain open.'))
    print(f'PASS game initialization: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(CHILD)} child sites,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)>1:raise SystemExit('usage: game_initialize_prefix.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='game-initialize-prefix-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,
                    timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)

if __name__=='__main__':
    if len(sys.argv)>=3 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3])
    else:main()
