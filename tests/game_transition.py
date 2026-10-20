"""031E..03E6 foreground transitions, using the shared original/native engine.

IRQs are quiescent. Finite raster providers are reused from palette_transition;
INT61 is a declared full-register pre-IRET fixture, never a sound-engine claim.
"""
import copy
import ctypes as ct
import gc
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import palette_transition as palette
import palette_timer
import display_status
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

OWN_RANGES=((0x031E,0x03E7),)
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
INS=OWN|palette.SPLIT_INS|palette_timer.INS|display_status.INS
EDGES=v.direct_jump_edges(OWN)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=240,384,400_000,500_000
REPORT=BUILD/'game-transition-differential.json'
BINDING=(0xB000,0x0100)
class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16),('service_status',ct.c_uint16)]
class Services(ct.Structure):
    _fields_=[('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),('int61',ct.POINTER(v.InterruptService))]

def cases():
    rows=[]
    for mode in (2,4):
        for flags in range(8):
            for counter in (0,15,35,55,56):
                rows.append(dict(name=f'flags-{flags}-cue-{counter}-mode-{mode}',mode=mode,transition=flags,counter=counter))
        for opening in (True,False):
            for delta in (0,3):
                for raster in (0,255):
                    rows.append(dict(name=f'{"opening" if opening else "closing"}-{delta}-raster-{raster}-m{mode}',
                        mode=mode,transition=1 if opening else 2,delta=delta,option=raster))
            for delta in (0,3):
                rows.append(dict(name=f'direct-{opening}-{delta}-m{mode}',mode=mode,entry=1 if opening else 2,
                    transition=1 if opening else 2,delta=delta))
    rows += [dict(name='cue-disabled-driver',transition=4,counter=15,enabled=0),
        dict(name='cue0f-muted',transition=4,counter=15,sound=0),
        dict(name='cue23-disabled-driver',transition=4,counter=35,enabled=0),
        dict(name='cue-muted',transition=4,counter=35,sound=0),
        dict(name='cue37-shared-ret',transition=4,counter=55,sound=1),
        dict(name='cue-unbound',transition=4,counter=15,no_service=True,expected=3,child_status=1),
        dict(name='cue-provider-stop',transition=4,counter=15,provider_stop=0x1234,expected=1,child_status=2,service_status=0x1234),
        dict(name='cue-changed-iret',transition=4,counter=15,iret_patch=True,expected=2,child_status=3),
        dict(name='changed-palette-return',entry=1,transition=1,return_patch=0x03D1,expected=2),
        dict(name='changed-step-return',transition=1,return_patch=0x0340,expected=2),
        dict(name='changed-status-return',transition=1,option=255,return_patch=0x0333,expected=2),
        dict(name='df-direct',entry=1,transition=1,flags=0x6D7),
        dict(name='stack-word-wrap',entry=2,transition=2,ss=0xFFF0,sp=0xFF),
    ]
    return [dict(load=v.LOADS[i%3],seed=0x031E+i,mode=2,transition=0,counter=0,delta=0,
        option=0,entry=0,enabled=255,sound=3,flags=0xAD7,patch='',count=16,first=0,second=0,
        expected=0,child_status=0,service_status=0)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=v.initial_memory(c)
    r=v.default_regs(c['load'],c['seed'],ds=0x6000,ss=c.get('ss',0x7000),sp=c.get('sp',0x8000),flags=c['flags'])
    r.update(ip=(0x031E,0x03C1,0x03D7)[c['entry']],ax=0xB000|c['transition'])
    for table in (0x52D4,0x52E4):
        for slot in range(8):v.put16(memory,r['cs'],table+2*slot,0x3000+slot*0x100,device)
    for slot in range(8):
        value=c['delta'] if (slot in (4,6) if c['transition']&1 else slot in (0,7)) else 0
        for n in range(-64,96):v.sync_memory_byte(memory,device,r['ds'],0x3000+slot*0x100+n,value)
    for off,value in ((0x004E,c['transition']),(0x0052,c['counter']),(0x0054,7),(0x0055,0),
                      (0x200E,c['option']),(0x2010,c['enabled']),(0x25A7,c['sound']),(0x200C,255)):
        v.sync_memory_byte(memory,device,r['ds'],off,value)
    v.put16(memory,r['ds'],0x1F7C,c['mode'],device);v.put16(memory,r['ds'],0x1FDA,0x3D4,device)
    v.put16(memory,r['ss'],r['sp'],0xEED1,device)
    v.put16(memory,0,0x184,BINDING[1]);v.put16(memory,0,0x186,BINDING[0])
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return memory,r,device

class Access(palette.SplitAccess):
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        if kind=='write' and self.c.get('return_patch') and 'return' not in self.providers:
            # Detect the high byte only after the real CALL has stored both bytes.
            lo=(address-1)&v.MASK
            if value==self.c['return_patch']>>8 and self.memory[lo]==(self.c['return_patch']&255):
                for depth in (2,4,6):
                    off=(self.r['sp']-depth)&65535
                    if lo==v.physical(self.r['ss'],off):self.patch(self.r['ss'],off,0xD234,'return')
        return got

def provider(access,r):
    access.service_events.append(dict(entry=dict(r)))
    if access.c.get('iret_patch'):access.word_write(r['ss'],r['sp'],0xD234,r['flags'])
    # Preserve the full returned register handoff, including AX on cue RETs.
    r.update(ax=0xA526,bx=0x7A31,es=0x6123,bp=0x8ABC)
    return access.c.get('provider_stop',0)

def original(c,memory,r,device,core):
    access=Access(c,memory,r,device);frames=[];diagnostics={'child_status':0,'service_status':0}
    def before(m,i):
        if i.mnemonic=='call':frames.append((i.address,i.address+i.size))
        return False
    def expected(m,off):
        v.check(bool(frames),'undeclared transition RET');return {frames.pop()[1]}
    def interrupt(m,number):
        v.check(number==0x61,'undeclared transition INT')
        m.software_interrupt(number,m.state()['ip'],BINDING,None if c.get('no_service') else provider)
        if m.stopped:
            raw=m.status;diagnostics.update(child_status=raw,service_status=m.service_status)
            m.status={1:3,2:1,3:2}[raw]
    m=v.OriginalMachine(c,memory,r,device,core,instructions=INS,access=access,
        outer_returns=lambda m,off:not frames,child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
        before=before,interrupt=interrupt,changed_return_status=2,max_steps=MAX_STEPS)
    out=m.run();out.update(diagnostics,services=access.service_events);return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'transition-{mutation}.dll',mutation,'game_transition')))
    def run(self,c,memory,r,device,core):
        memory,device=bytearray(memory),copy.deepcopy(device);access=Access(c,memory,r,device)
        cb=v.NativeCallbacks(access);handler=cb.interrupt(provider);binding=v.InterruptService(None,handler,*BINDING)
        services=Services(ct.pointer(cb.ports),ct.pointer(cb.bus),None if c.get('no_service') else ct.pointer(binding))
        fn=getattr(self.lib,'lmn_game_transition_'+('core' if core else 'adapter'))
        fn.restype=Result;fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_int,ct.POINTER(Services)]
        out=fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),c['entry'],ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,
            child_status=out.child_status,service_status=out.service_status,memory=memory,device=device,
            events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)

def hashes():
    paths={p for cluster in ('game_transition',) for p in source_files(cluster)}
    paths.update((ROOT/'c').glob('*.h'))
    paths.update(ROOT/p for p in ('tests/game_transition.py','tests/verification.py','tests/palette_transition.py',
        'tests/palette_timer.py','tests/display_status.py','tools/cbuild.py','tools/bounded_process.py',
        'src/entry_services.asm','metadata/symbols.json','assets/vgalemmi.exe'))
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p.read_bytes()) for p in sorted(paths)}

def compare(native,c,core):
    memory,r,device=setup(c);reference=original(c,bytearray(memory),dict(r),copy.deepcopy(device),core)
    v.check(reference['status']==c['expected'],c['name']+': unexpected original stop')
    actual=native.run(c,memory,r,device,core);v.compare_states(c['name'],actual,reference)
    return reference

def worker(directory):
    started=time.monotonic();before=hashes();native=Native(directory);sites=set();edges=set();rows=[]
    for c in cases():
        for core in (True,False):
            out=compare(native,c,core);sites|=out['sites'];edges|=out['edges']
            rows.append(dict(name=c['name'],core=core,steps=out['steps'],events=len(out['events'])))
        gc.collect()
    v.check(set(OWN)<=sites,f'missing transition sites {sorted(set(OWN)-sites)}')
    v.check(EDGES<=edges,f'missing transition outcomes {sorted(EDGES-edges)}')
    witnesses={1:'direct-True-0-m2',2:'opening-3-raster-255-m2',3:'flags-5-cue-15-mode-2'}
    lookup={c['name']:c for c in cases()};mutants=[]
    for mutation,name in witnesses.items():
        try:compare(Native(directory,mutation),lookup[name],False)
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,mismatch=str(error),completed=True))
        else:raise v.OracleFailure(f'transition mutant {mutation} survived')
    v.check(before==hashes(),'transition inputs changed during campaign')
    write_json(REPORT,dict(code_ranges=OWN_RANGES,own_bytes=sum(i.size for i in OWN.values()),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(edges&EDGES),cases=rows,mutations=mutants,
        runtime_seconds=time.monotonic()-started,input_hashes=before,
        limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,steps=MAX_STEPS,events=MAX_EVENTS)))
    print(f'PASS game transition: {len(rows)} comparisons, {len(set(OWN)&sites)} sites, {len(EDGES)} outcomes, {len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='game-transition-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',str(directory)],cwd=ROOT,
            timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()
