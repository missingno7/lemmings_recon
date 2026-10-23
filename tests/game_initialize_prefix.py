"""Shared-engine differential for the connected 03E7 initialization prefix."""
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
import video_probe as probe
import level_initialize as level
from cbuild import build,source_files
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

START,BOUNDARY=0x03E7,0x046E
LEVEL_ENTRY,LEVEL_SERVICE_STOP=0x36B6,0x1A7B
OWN_RANGES=((START,BOUNDARY),)
BASE_CHILD_RANGES=((0x0FB2,0x0FF8),(0x13DC,0x14C1),(0x14C2,0x1530),
              (0x15AD,0x1644),(0x52F4,0x531D),
              (0x5425,0x5447),(0x548C,0x54C4))
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
CHILD={i.address:i for a,b in BASE_CHILD_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
CHILD.update(level.INS)
BOUNDARY_INSTRUCTION=next(v.MD.disasm(v.IMAGE[BOUNDARY:BOUNDARY+8],BOUNDARY))
INS=OWN|CHILD|{BOUNDARY_INSTRUCTION.address:BOUNDARY_INSTRUCTION}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=180,384,2_000_000,1_000_000
REPORT=BUILD/'game-initialize-prefix-differential.json'

class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),
              ('child_status',ct.c_uint16),('service_status',ct.c_uint16)]

class VideoServices(ct.Structure):
    _fields_=[('bios',ct.POINTER(v.InterruptService)),('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus))]

class LevelServices(ct.Structure):
    _fields_=[('dat_segments',ct.c_void_p),('special',ct.c_void_p),
              ('raster',ct.POINTER(v.Bus)),('ports',ct.POINTER(v.Ports))]

class GameServices(ct.Structure):
    _fields_=[('video',ct.POINTER(VideoServices)),('ports',ct.POINTER(v.Ports)),
              ('bus',ct.POINTER(v.Bus)),('level',ct.POINTER(LevelServices)),
              ('game_data_segment',ct.c_uint16),('stop_at_mouse_check',ct.c_uint16),
              ('mouse',ct.POINTER(v.InterruptService)),('dos',ct.POINTER(v.InterruptService)),
              ('foreground',ct.c_void_p)]

def cases():
    rows=[]
    for load in v.LOADS:
        for direction,flags in (('forward',0x0AD7),('backward',0x06D7)):
            rows.append(dict(name=f'{direction}-{load:04x}',load=load,seed=0x3E7^load,
                ds=0x6000,ss=0x9000,flags=flags,ax=0xB543))
    rows.extend((
        dict(name='ds-ss-alias',load=v.LOADS[0],seed=0x31A5,ds=0x6800,ss=0x6800,
             flags=0x0AD7,ax=0xC37E,expected=1,child_status=6),
        dict(name='vga-data-and-stack',load=v.LOADS[1],seed=0x31A6,ds=0xA000,ss=0xA000,
             flags=0x0AD7,ax=0xA55A,expected=1,child_status=6),
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
        dict(name='palette-rgb',load=v.LOADS[0],seed=0x31B0,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4),
        dict(name='palette-rgb-blanking-off',load=v.LOADS[1],seed=0x31B1,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,blanking=0),
        dict(name='palette-parent-return-changed',load=v.LOADS[2],seed=0x31B2,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,patch='palette-parent-return',expected=2),
        dict(name='palette-service-missing-input',load=v.LOADS[0],seed=0x31B3,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=2,missing_in=True,expected=1,child_status=1,service_status=1),
        dict(name='palette-service-missing-output',load=v.LOADS[1],seed=0x31B4,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=2,missing_out=True,expected=1,child_status=1,service_status=2),
        dict(name='timer-fixed-option',load=v.LOADS[0],seed=0x31B5,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,option=0xFF),
        dict(name='timer-parent-return-changed',load=v.LOADS[1],seed=0x31B6,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,option=0xFF,patch='timer-parent-return',expected=2),
        dict(name='level-special-service-stop',load=v.LOADS[0],seed=0x31B7,ds=0x6000,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,option=0xFF,level_services=True,
             level_selector=1,expected=1,child_status=1,service_status=1),
        dict(name='level-normal-return',load=v.LOADS[0],seed=0x31B8,ds=0x19B9,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,option=0xFF,level_services=True,
             level_ready=True,game_data_segment=0x19B9,expected=0,child_status=0,service_status=0),
        dict(name='level-parent-return-changed',load=v.LOADS[0],seed=0x31B9,ds=0x19B9,ss=0x9000,
             flags=0x0AD7,ax=0xB543,mode=4,option=0xFF,level_services=True,
             level_ready=True,game_data_segment=0x19B9,patch='level-parent-return',
             expected=2,child_status=0,service_status=0),
    ))
    defaults=dict(pit=0x1234,primary=7,secondary=0,dcc=True,ega=True,ega_config=0,
                  color=True,mono=True,mono_id=0x50,base=0x3D4,
                  game_data_segment=0x7000)
    for case in rows:
        case.update({key:value for key,value in defaults.items() if key not in case})
        if case['ds']==case['ss']:case['base']=0
    return rows

def setup(case):
    memory,device=v.initial_memory(case)
    if case.get('level_ready'):
        level_memory,level_regs,_,game_data_segment=level.prepare(level.cases()[0])
        v.check(level_regs['cs']==case['load'] and level_regs['ds']==case['ds'],
                'level-ready fixture segment/load differs')
        v.check(game_data_segment==case['game_data_segment'],
                'explicit game-data segment differs from level fixture')
        start=v.physical(level_regs['ds'],0)
        memory[start:start+0x10000]=level_memory[start:start+0x10000]
    regs=v.default_regs(case['load'],case['seed'],ds=case['ds'],ss=case['ss'],
                        sp=case.get('sp',0x4AF4),flags=case['flags'])
    regs.update(ip=START,ax=case['ax'])
    for segment in {case['ds'],0x7000}:
        v.put16(memory,segment,0x1FDA,case['base'],device)
        v.put16(memory,segment,0x1F7C,case.get('mode',2),device)
        v.put16(memory,segment,0x1FC9,case.get('reload',0x4567),device)
        v.put16(memory,segment,0x2011,case.get('raster_mode',0),device)
        v.sync_memory_byte(memory,device,segment,0x200E,case.get('option',0xFF))
        v.sync_memory_byte(memory,device,segment,0x200C,case.get('blanking',0xFF))
        for n in range(48):
            v.sync_memory_byte(memory,device,segment,0x2608+n,(n*7+3)&63)
        for n in range(9):v.put16(memory,segment,0x002E+2*n,0xD234,device)
    if case.get('level_services') and not case.get('level_ready'):
        for offset in range(0,24,2):
            value=(0x8100+offset*13+case['seed'])&65535
            for n,byte in enumerate(value.to_bytes(2,'big')):
                memory[v.physical(case['ds'],0x0FCB+offset+n)]=byte
        v.sync_memory_byte(memory,device,case['ds'],0x0FE8,case.get('level_selector',0))
        v.put16(memory,case['ds'],0x1FF0,0x5000,device)
    v.put16(memory,0,0x40,0x0100);v.put16(memory,0,0x42,0xB000)
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return memory,regs,device

class Access(probe.Access):
    def __init__(self,*args):
        super().__init__(*args)
        self.timer_phase=False
        self.level_phase=False
        self.palette_inputs=0
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        if kind=='read' and address==v.physical(self.r['ds'],0x2011):
            self.timer_phase=True
        if (self.c.get('level_services') and kind=='write' and value==0x6E and
                address==v.physical(self.r['ss'],
                    (self.c.get('sp',0x4AF4)-2)&0xFFFF)):
            self.level_phase=True
        if (self.c.get('patch')=='level-parent-return' and self.level_phase and
                kind=='write' and value==0x04 and
                address==v.physical(self.r['ss'],
                    (self.c.get('sp',0x4AF4)-1)&0xFFFF) and
                'level-parent-return' not in self.providers):
            # Patch only after the actual 046B CALL has written its 046E
            # return word. Earlier child calls reuse this stack slot.
            self.patch(self.r['ss'],(self.c.get('sp',0x4AF4)-2)&0xFFFF,
                       0xD234,'level-parent-return')
        if (self.c.get('patch')=='timer-parent-return' and kind=='write' and
                address==v.physical(self.r['ds'],0x1FC9) and
                'timer-parent-return' not in self.providers):
            self.patch(self.r['ss'],(self.r.get('sp',0x4AF4)-2)&0xFFFF,
                       0xD234,'timer-parent-return')
        return got
    def out_word(self,port,value,flags,mask=v.FLAGS):
        if self.level_phase:
            self.device.out(port,value,flags)
            self.emit('out',port,value,flags,mask)
            return
        expected_port=0 if self.c['ds']==self.c['ss'] else 0x3D4
        v.check((port,value)==(expected_port,0x1613),
                f"{self.c['name']}: unexpected game-video word OUT {port:04X}:{value:04X}, expected {expected_port:04X}:1613")
        self.outputs.append((port,value));self.emit('out',port,value,flags,mask)
        if self.c.get('patch')=='parent-return' and 'parent-return' not in self.providers:
            ss=self.r['ss'];sp=self.r.get('sp',0x4AF4)
            self.patch(ss,(sp-2)&0xFFFF,0xD234,'parent-return')
    def inp(self,port,flags,mask=v.FLAGS):
        if not self.timer_phase:
            status_port=(self.c['base']&0xFF00)|((self.c['base']+6)&0xFF)
            if port in (status_port,0x3C5):
                value=0x93 if port==0x3C5 else 0
                self.palette_inputs+=1
                v.check(self.palette_inputs<=4,'palette input budget exhausted')
                self.cursor+=1;self.emit('in',port,value,flags,mask);return value
        return super().inp(port,flags,mask)
    def out(self,port,value,flags,mask=v.FLAGS):
        if not self.timer_phase and port in (0x00C0,0x3C0,0x3C4,0x3C5,0x3C8,0x3C9):
            self.emit('out8',port,value,flags,mask)
            if (self.c.get('patch')=='palette-parent-return' and
                    'palette-parent-return' not in self.providers):
                self.patch(self.r['ss'],(self.r.get('sp',0x4AF4)-2)&0xFFFF,
                           0xD234,'palette-parent-return')
            return
        return super().out(port,value,flags,mask)

def bios_provider(access,r):
    if r['ax']!=0x008D:
        access.timer_phase=True
        return probe.bios_provider(access,r)
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
        if instruction.address==LEVEL_ENTRY and not case.get('level_services'):
            self_state['child_status']=1
            self_state['service_status']=1
            machine.stop(1)
            return True
        if instruction.address==LEVEL_SERVICE_STOP and case.get('level_services'):
            self_state['child_status']=1
            self_state['service_status']=1
            machine.stop(1)
            return True
        if instruction.address==0x1407 and machine.state()['ax'] not in probe.TARGETS:
            self_state['child_status']=6
            machine.stop(1)
            return True
        missing=(case.get('missing_in') if instruction.mnemonic=='in' else
                 case.get('missing_out') if instruction.mnemonic=='out' and
                 instruction.operands[-1].size==1 else False)
        if missing:
            self_state['child_status']=1
            self_state['service_status']=1 if instruction.mnemonic=='in' else 2
            machine.stop(1)
            return True
        if instruction.mnemonic in ('call','lcall'):
            frames.append((instruction.address,instruction.address+instruction.size,
                           instruction.mnemonic=='lcall'))
        return False
    def expected(machine,offset):
        v.check(bool(frames),'undeclared initializer child return')
        owner,resume,far=frames.pop()
        v.check(not far,'near RET consumed a far CALL frame')
        return {resume}
    def expected_far(machine,offset):
        v.check(bool(frames),'undeclared initializer far return')
        owner,resume,far=frames.pop()
        v.check(far,'far RET consumed a near CALL frame')
        return {(case['load'],resume)}
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
        far_returns={p:expected_far for p,i in INS.items() if i.mnemonic=='retf'},
        before=before,interrupt=interrupt,changed_return_status=2,max_steps=MAX_STEPS)
    out=machine.run();out['child_status']=self_state['child_status'];out['service_status']=self_state['service_status']
    out['services']=access.service_events;out['hardware']=access.outputs
    return out

class Native:
    def __init__(self,directory,mutation=0):
        baseline=Path(directory)/'game-initialize-0.dll'
        self.dependencies=None
        if mutation:
            if not baseline.is_file():build(baseline,0,'game_initialize')
            self.dependencies=ct.CDLL(str(baseline))
        path=build(Path(directory)/f'game-initialize-{mutation}.dll',mutation,'game_initialize',
                   dependency_library=baseline if mutation else None)
        self.lib=ct.CDLL(str(path))
        self.fn=self.lib.lmn_initialize_game_core
        self.fn.restype=Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(GameServices)]
    def run(self,case,memory,regs,device):
        memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(case,memory,regs,device)
        callbacks=v.NativeCallbacks(access,missing_in=case.get('missing_in'),
                                    missing_out=case.get('missing_out'))
        handler=callbacks.interrupt(bios_provider)
        binding=v.InterruptService(None,handler,0xB000,0x0100)
        video=VideoServices(None if case.get('no_bios') else ct.pointer(binding),
                            ct.pointer(callbacks.ports),ct.pointer(callbacks.bus))
        level_services=(LevelServices(None,None,ct.pointer(callbacks.bus),
                                       ct.pointer(callbacks.ports))
                        if case.get('level_services') else None)
        services=GameServices(ct.pointer(video),ct.pointer(callbacks.ports),
                              ct.pointer(callbacks.bus),
                              None if level_services is None else ct.pointer(level_services),
                              case.get('game_data_segment',0x7000),1,None,None,None)
        native_regs=v.Regs(**regs)
        result=self.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(native_regs),ct.byref(services))
        return dict(regs={name:getattr(result.registers,name) for name in v.REG_NAMES},
            status=result.status,child_status=result.child_status,service_status=result.service_status,
            memory=memory,device=device,events=access.events,providers=access.providers,
            cursor=access.cursor,services=access.service_events,hardware=access.outputs)

def independent(case,initial,reference):
    result=reference['regs'];step=-1 if case['flags']&0x400 else 1
    timer_started=0x15AD in reference['sites']
    parent_return=(0xD234 if case.get('patch') in ('parent-return','palette-parent-return','timer-parent-return','level-parent-return')
                   else 0x0465 if reference['status']==1 and reference['child_status']==3
                   else 0x0468 if reference['status']==1 and case['name'].startswith('palette-') and
                        (case.get('missing_in') or case.get('missing_out'))
                   else 0x046B if reference['regs']['ip']==0x1407
                   else 0x046E)
    if reference['status'] in (0,2) and case.get('level_ready'):
        v.check(result['sp']==initial['sp'],'level child did not consume its internal and parent frames')
        v.check(result['ip']==parent_return,'level child return target differs')
    elif reference['status'] in (0,2):
        if case['ds']==case['ss'] and reference['status']==0:
            v.check(result['cx']==case['pit'],'timer measurement did not preserve the PIT count')
        else:v.check(result['cx']==0,'initializer did not exhaust the final palette count')
        v.check(result['ip']==parent_return,'initializer did not preserve the live parent RET target')
        if case['ds']!=case['ss']:
            v.check((result['flags']&0x400)==(case['flags']&0x400),'video child changed DF')
            expected_di=0x2200 if case.get('returned_state') else (0x42B2+step*0x0642)&0xFFFF
            v.check(result['di']==expected_di,'live DI differs after first child return')
            v.check(result['bp']==(0xABCD if case.get('returned_state') else initial['bp']),
                    'live BP differs after first child return')
        mode=0 if case['ds']==case['ss'] else case.get('mode',2)
        if case['ds']!=case['ss'] and case.get('patch') not in ('parent-return','palette-parent-return','timer-parent-return'):
            palette_step=-1 if case['flags']&0x400 else 1
            palette_count=48 if mode==4 else 16
            v.check(result['si']==(0x2608+palette_step*palette_count)&0xFFFF,
                    'base palette source cursor differs')
        slots=(0x6170,0x64D9,0x65D8,0x66D7,0x6817,0x6957,0x6A97,0x6BDB,0x6CFC)
        for n,value in enumerate(slots):
            v.check(v.get16(reference['memory'],result['ds'],0x2E+2*n)==value,
                    f'video child callback slot {n} differs')
        expected_port=0 if case['ds']==case['ss'] else 0x3D4
        v.check(reference['hardware'][0]==(expected_port,0x1613),'video child word OUT differs')
        if case.get('patch') not in ('parent-return','palette-parent-return') and mode==4:
            banks=[event[2] for event in reference['events'] if event[:2]==('out8',0x3C8)]
            colors=[event[2] for event in reference['events'] if event[:2]==('out8',0x3C9)]
            v.check(banks==[0,16],'base palette DAC bank starts differ')
            v.check(colors==[(i*7+3)&63 for i in range(48)],
                    'base palette source continuation differs')
        timer_ds=0x7000 if case.get('returned_state') else case['ds']
        final_option=0 if case['ds']==case['ss'] else case.get('option',0xFF)
        timer_reached=reference['status']==0 or case.get('patch')=='timer-parent-return'
        if timer_reached and final_option==0xFF:
            v.check(v.get16(reference['memory'],timer_ds,0x1FC9)==0x4000,
                    'fixed timer option did not publish the literal reload')
        elif timer_reached and case['ds']==case['ss']:
            v.check(v.get16(reference['memory'],timer_ds,0x1FC9)==(0xFFFF-case['pit'])&0xFFFF,
                    'measured timer reload differs from the independent PIT complement')
    stack_start=(case.get('sp',0x4AF4)-2)&0xFFFF
    frame_offsets={(stack_start+n)&0xFFFF for n in range(2)}
    for first in (-4,-6,-8):
        frame_offsets.update(((case.get('sp',0x4AF4)+first+n)&0xFFFF) for n in range(2))
    for start,count in ((0x0012,0x42A0),(0x42B2,0x0642)):
        for n in range(count):
            offset=(start+step*n)&0xFFFF
            if offset in frame_offsets:continue
            if case['ds']==case['ss'] and 0x2E<=offset<0x40:continue
            if case['ds']==case['ss'] and timer_started and 0x1FC9<=offset<0x2020:continue
            at=v.physical(case['ss'],offset)
            v.check(reference['memory'][at]==0,
                    f'{case["name"]}: ordered stack/SS clear result differs at {offset:04X}')
    actual_return=v.get16(reference['memory'],case['ss'],stack_start)
    v.check(actual_return==parent_return,
            f"{case['name']}: actual parent CALL return word {actual_return:04X}/{parent_return:04X}")
    if case.get('level_services') and not case.get('level_ready'):
        v.check(reference['regs']['ip']==LEVEL_SERVICE_STOP,
                'level special-resource provider stop target differs')
        v.check(v.get16(reference['memory'],case['ss'],
                        (case.get('sp',0x4AF4)-4)&0xFFFF)==0x374C,
                'special-resource child CALL return word differs')
    elif reference['regs']['ip']==LEVEL_ENTRY:
        v.check(actual_return==0x046E,'missing raster stop lost the level CALL frame')
    if case['ds']!=case['ss'] and not case.get('level_services'):
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
                if case['ds']==case['ss'] and 0x2E<=offset<0x40:continue
                if case['ds']==case['ss'] and timer_started and 0x1FC9<=offset<0x2020:continue
                for plane in reference['device'].planes:
                    v.check(plane[offset]==0,f'{case["name"]}: planar clear misses {offset:04X}')

def compare(native,case):
    memory,regs,device=setup(case)
    ref=original(case,bytearray(memory),dict(regs),copy.deepcopy(device))
    expected_status=case.get('expected',1)
    child_status=case.get('child_status',0 if expected_status==2 else 1)
    expected=(expected_status,child_status,
              case.get('service_status',0 if expected_status==2 or child_status in (3,6) else 1))
    v.check((ref['status'],ref['child_status'],ref['service_status'])==expected,
            case['name']+f': unexpected original stop {(ref["status"],ref["child_status"],ref["service_status"])}; expected {expected}')
    actual=native.run(case,memory,regs,device)
    v.compare_states(case['name'],actual,ref)
    v.require(actual['hardware']==ref['hardware'],case['name']+': device output differs')
    independent(case,regs,ref)
    return ref

def hashes():
    paths={'tests/game_initialize_prefix.py','tests/video_probe.py','tests/verification.py','tests/minimap_vga.py',
        'tools/cbuild.py','tools/bounded_process.py','tools/common.py',
        'tools/unpack.py','metadata/oracle.json','metadata/toolchain-lock.json','assets/vgalemmi.exe',
        'src/entry_services.asm','src/palette_frontends.asm'}
    paths.update(level.input_hashes())
    # Registry additions do not change this suite's declared limits or inputs.
    paths.discard('tools/difftest.py')
    pending=list(source_files('game_initialize'))
    while pending:
        path=pending.pop();name=path.relative_to(ROOT).as_posix()
        if name in paths:continue
        paths.add(name)
        pending.extend(path.parent/name for name in re.findall(r'#include\s+"([^"]+)"',path.read_text()))
    return {name:sha((ROOT/name).read_bytes()) for name in sorted(paths)}

MUTANTS=((1,'forward-1010'),(2,'backward-1010'),(3,'forward-1010'),
         (4,'video-parent-return-changed'),(5,'palette-parent-return-changed'),
         (6,'timer-parent-return-changed'),(7,'level-special-service-stop'),
         (8,'level-parent-return-changed'))

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
    child_sites=set(sites)-set(OWN)
    observed_bytes=sorted({pc+d for pc in child_sites for d in range(INS[pc].size)})
    observed_ranges=[]
    for address in observed_bytes:
        if not observed_ranges or address!=observed_ranges[-1][1]:
            observed_ranges.append([address,address+1])
        else:observed_ranges[-1][1]=address+1
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(rows),comparison_count=len(rows),
        native_code_ranges=[list(bound) for bound in OWN_RANGES],own_known_bytes=sum(i.size for i in OWN.values()),
        connected_code_ranges=observed_ranges,known_connected_bytes=sum(i.size for i in OWN.values())+sum(INS[p].size for p in child_sites),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=[],own_branch_edges=[],mutation_count=len(mutants),mutations=mutants,
        instruction_steps=sum(row['steps'] for row in rows),ordered_bus_events=sum(row['events'] for row in rows),
        rows=rows,input_hashes=before,limits=dict(worker_seconds=SECONDS,windows_process_mib=MEMORY_MIB,
        windows_tree_mib=MEMORY_MIB+256,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='03E7 state initialization and SS interaction/dirty-map clears composed through actual0462/0465/0468/046B CALL/RETs to native video, palette, timer-calibration and level-initialization cores. Twenty-seven memory/frame cases cover BIOS returns, unbound services and detector target, changed parent returns, packed/RGB palette, fixed timer reload, missing byte-port stops, raster stop at level entry, level drawing/header fallthrough to the declared missing-special-service stop at1A7B, normal level return to046E and a changed live parent return word. They also retain20-bit physical wrap, DS/SS aliases, planar VGA,DF and ordered bus/device effects. The conditional mouse-service check at046E, remaining game children/providers, timer/IRQ schedule, frame loop and full game remain open.'))
    print(f'PASS game initialization: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(child_sites)} child sites,{len(mutants)} mutants',flush=True)

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
