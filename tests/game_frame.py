"""Connected foreground frame differential; original-only level/session setup.

All scenarios use the declared minimal IRQ fixture: at the explicit poll,
when IF is set, perform only the183E tail's foreground-visible stores
(1FCF=FF, INC byte1FCD), preserving all CPU roles as the handler's IRET does.
This proves the controller handshake and handoffs, not hardware-frame/input/
BIOS-chain scheduling inside17C7. Quiescent scenarios deliver no IRQ. The
finite display provider comes from palette_transition. INT services are
declared pre-IRET fixtures; child sound-engine domains remain unchanged.
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
import game_transition as transition
import view_scroll as scroll
import game_initialize_prefix as initialize
import game_prepare as prepare
import level_initialize as level
import entity_action_dispatch as actions
import entity_batch as batch
import object_animation as animation
import object_drawing_tick as objects
import entity_drawing as drawing
import entity_select as selection
import status_display_full as status
import status_initialize
import fixed_pattern_update as pattern
import timer_install as timer
import level_briefing as briefing
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json
OWN_RANGES=((0x0105,0x0182),(0x0183,0x01B0),(0x01B6,0x031E))
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
# Child instruction domains come from their owning suites, including UNKNOWN
# exclusions. No linear decoding of an unproved child gap is introduced here.
INS=dict(OWN)
for domain in (transition.INS,scroll.INS,prepare.INS,actions.COMPOSED_INS,batch.INTEGRATED_INS,
    animation.OWN_INS,objects.INS,drawing.MAIN_INS,selection.MAIN_INS,status.FULL_INS,
    pattern.MAIN_INS,timer.INS,briefing.INS,initialize.INS):
    for p,i in domain.items():
        if p in INS:v.check(bytes(INS[p].bytes)==bytes(i.bytes),f'conflicting child instruction{p:04X}')
        INS[p]=i
RESULT_INSTRUCTION=next(v.MD.disasm(v.IMAGE[0x46EB:0x46F3],0x46EB))
INS[0x46EB]=RESULT_INSTRUCTION
INS.update({i.address:i for i in v.MD.disasm(v.IMAGE[0x0480:0x04A4],0x0480)})
EDGES=v.direct_jump_edges(OWN)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=600,512,2_000_000,1_500_000
REPORT=BUILD/'game-frame-differential.json'
BINDINGS={0x60:(0xB000,0x100),0x61:(0xB000,0x200),0x21:(0xB000,0x300),0x1A:(0xB000,0x400),0x10:(0xB000,0x500)}
class Services(ct.Structure):
    _fields_=[('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),
        ('int60',ct.POINTER(v.InterruptService)),('int61',ct.POINTER(v.InterruptService)),
        ('dos',ct.POINTER(v.InterruptService)),('bios_clock',ct.POINTER(v.InterruptService)),
        ('pc',ct.c_void_p),('sound',ct.c_void_p),('poll',ct.POINTER(v.ForegroundPoll)),('game_data_segment',ct.c_uint16)]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs)]+[(n,ct.c_uint16) for n in ('status','child_entry','child_status','service_status')]

class Access(transition.palette.SplitAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device);self.max_events=MAX_EVENTS
        self.poll_count=0;self.polls=[];self.irq_deliveries=0;self.crtc={}
    def out_word(self,port,value,flags,mask=v.FLAGS):
        if port in (0x3D4,0x3B4):self.crtc[(port,value&255)]=value>>8
        else:self.device.out(port,value,flags)
        self.emit('out',port,value,flags,mask)
    def out(self,port,value,flags,mask=v.FLAGS):
        super().out(port,value,flags,mask)
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        c=self.c
        if c.get('return_patch') and kind=='write' and 'frame-return' not in self.providers:
            target=c['return_patch'];lo=(address-1)&v.MASK
            if value==target>>8 and self.memory[lo]==target&255:
                off=(self.r['sp']-2)&65535
                if lo==v.physical(self.r['ss'],off):self.patch(self.r['ss'],off,0xD234,'frame-return')
        if (c.get('sound_race') and kind=='write' and address==v.physical(self.r['ds'],0x25A7)
            and value==0 and 'sound-race' not in self.providers):self.patch(self.r['ds'],0x25A7,3,'sound-race',word=False)
        return got
    def irq_tail(self,r):
        if not r['flags']&0x200:return False
        self.patch(r['ds'],0x1FCF,255,'irq-tail',word=False)
        self.emit('irq-store',v.physical(r['ds'],0x1FCF),255,r['flags'])
        off=v.physical(r['ds'],0x1FCD);value=(self.memory[off]+1)&255
        self.patch(r['ds'],0x1FCD,value,'irq-tail',word=False)
        self.emit('irq-store',off,value,r['flags']);self.irq_deliveries+=1;return True
    def poll(self,r,site):
        v.check(r['ip']==site,'poll IP is not the original read site')
        self.poll_count+=1;v.check(self.poll_count<=32,
            f"{self.c['name']}: foreground poll budget exhausted at{site:04X}, DS{r['ds']:04X}, FLAGS{r['flags']:04X}, counter{self.memory[v.physical(r['ds'],0x1FCD)]}")
        self.polls.append((site,self.poll_count,r['flags']))
        if self.c.get('poll_stop')==site:return 0xCA11
        if self.c.get('raster_edge_once') and site==0x0131 and 'raster-edge' not in self.providers:
            self.irq_tail(r);self.providers.add('raster-edge')
        if self.c.get('irq_site')==site and self.poll_count>=self.c.get('irq_poll',1):
            for _ in range(self.c.get('irq_count',1)):self.irq_tail(r)
        if self.c.get('stop_after_watchdog') and site==0x0179:return 0xCA11
        return 0

def service(number):
    def execute(access,r):
        event=dict(number=number,entry=dict(r));access.service_events.append(event)
        if number==0x21:
            v.check(r['ax'] in (0x2508,0x2560),'unexpected frame DOS service')
            vector=r['ax']&255
            access.word_write(0,vector*4,r['dx'],r['flags']);access.word_write(0,vector*4+2,r['ds'],r['flags'])
        elif number==0x1A:v.check(r['ax']==0x100,'unexpected frame BIOS clock service')
        elif number in (0x60,0x61):
            # Observe the service-returned AX on early cue/controller paths.
            r['ax']=access.c.get('sound_ax',0xA526)
        else:raise v.OracleFailure('unexpected frame service')
        return 0
    return execute

def original(c,memory,r,device,*,stop=None,access_factory=Access,instructions=INS,interrupt_provider=None,core=True):
    access=access_factory(c,memory,r,device);frames=[];dispatches=[]
    diagnostics={'child_status':0,'service_status':0}
    initial=r['ip'];entered=False
    def before(m,i):
        nonlocal entered
        if stop is not None and i.address==stop:m.stop(0);return True
        if i.address==0x46EB:m.stop(1);return True
        if i.address==0x0105 and entered:m.stop(0);return True
        entered=True
        if i.address==0x3150:
            state=m.state();ds=state['ds']
            dispatches.append(dict(return_word=v.get16(memory,state['ss'],state['sp']),
                candidate=memory[v.physical(ds,0x63)],buttons=v.get16(memory,ds,0x14),
                latch=memory[v.physical(ds,0x61)],inventory=memory[v.physical(ds,0x6A)]))
        if i.address in (0x0131,0x0179,0x01DF):
            state=m.state()
            if c.get('null_poll'):
                if i.address==0x01DF:m.stop(6);return True
            elif access.poll(state,i.address):
                diagnostics['service_status']=0xCA11;m.stop(2);return True
            # The minimal tail projection restores every register. Its two
            # canonical stores are already synchronized by BusAccess.patch.
        if i.mnemonic in ('call','lcall'):frames.append((i.address,i.address+i.size,i.mnemonic=='lcall'))
        return False
    def expected(m,off):
        v.check(bool(frames),'undeclared frame child RET');owner,resume,far=frames.pop()
        v.check(not far,'near RET consumed far frame');return {resume}
    def expected_far(m,off):
        v.check(bool(frames),'undeclared frame child RETF');owner,resume,far=frames.pop()
        v.check(far,'far RET consumed near frame');return {(c['load'],resume)}
    def interrupt(m,number):
        binding=BINDINGS[number]
        provider=interrupt_provider if interrupt_provider is not None else service(number)
        if c.get('unbound')==number:provider=None
        m.software_interrupt(number,m.state()['ip'],binding,provider)
        if m.stopped:
            raw=m.status;diagnostics.update(child_status=raw,service_status=m.service_status)
            if 0x031E<=m.previous.address<0x03E7:
                diagnostics['child_status']={1:3,2:1,3:2}[raw]
                if not diagnostics['service_status']:diagnostics['service_status']=raw
            m.status={1:5,2:3,3:4}[raw]
    machine=v.OriginalMachine(c,memory,r,device,core,instructions=instructions,access=access,
        outer_returns=lambda m,p:not frames,child_returns={p:expected for p,i in instructions.items() if i.mnemonic=='ret'},
        far_returns={p:expected_far for p,i in instructions.items() if i.mnemonic=='retf'},
        before=before,interrupt=interrupt,changed_return_status=4,max_steps=MAX_STEPS)
    out=machine.run();out.update(diagnostics,services=access.service_events,dispatches=dispatches)
    out.update(polls=getattr(access,'polls',[]),irq_deliveries=getattr(access,'irq_deliveries',0),crtc=getattr(access,'crtc',{}))
    return out

def fixture():
    """Run original03E7..046D, then0480..04A0, never boot the game."""
    c=next(c for c in initialize.cases() if c.get('level_ready') and c.get('expected',0)==0)
    # Use the maintained normal terrain-only LEVEL/resource fixture. Its source
    # bytes and header are consumed by the original36B6 initializer here.
    memory,r,device=initialize.setup(c)
    # 4551 owns this per-level clear before LEVEL loading; the fixture's
    # header/resources start at0FCB and are retained for36B6 to consume.
    base=v.physical(r['ds'],0);memory[base:base+0x0FCB]=bytes(0x0FCB)
    for number,(cs,ip) in BINDINGS.items():v.put16(memory,0,number*4,ip);v.put16(memory,0,number*4+2,cs)
    out=original(c,memory,r,device,stop=0x046E,access_factory=initialize.Access,
        interrupt_provider=initialize.bios_provider)
    v.check(out['status']==0,'original session prefix did not finish')
    prefix_steps=out['steps']
    memory,r,device=out['memory'],out['regs'],out['device'];ds=r['ds']
    # Small declared pacing budget replaces the later calibration measurement.
    # Runtime/platform fields below are service inputs (not copied game state).
    v.put16(memory,ds,0x1FFE,3,device);v.put16(memory,ds,0x2000,0,device)
    for number,(cs,ip) in BINDINGS.items():v.put16(memory,0,number*4,ip);v.put16(memory,0,number*4+2,cs)
    r['ip']=0x0480
    init_c=defaults('initializer-children')
    out=original(init_c,memory,r,device,stop=0x04A1)
    v.check(out['status']==0,'original0480..049E children did not finish')
    #1644 installs the real PC-speaker vector. The frame scenarios declare
    #external pre-IRET service bodies at these explicit fixture bindings.
    for number,(cs,ip) in BINDINGS.items():v.put16(out['memory'],0,number*4,ip);v.put16(out['memory'],0,number*4+2,cs)
    return out['memory'],out['regs'],out['device'],dict(prefix_steps=prefix_steps,initializer_children_steps=out['steps'],
        initialized_from='tests/game_initialize_prefix.py normal level_ready fixture; original03E7 and0480 children')

def defaults(name,**values):
    return dict(name=name,load=0x1010,seed=0x105,entry=0,patch='',count=16,
        expected=0,child_status=0,service_status=0)|values

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'frame-{mutation}.dll',mutation,'game_frame')))
        self.fn=self.lib.lmn_game_frame_core;self.fn.restype=Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(Services)]
    def run(self,c,memory,r,device):
        memory,device=bytearray(memory),copy.deepcopy(device);access=Access(c,memory,r,device);cb=v.NativeCallbacks(access)
        handlers={n:cb.interrupt(service(n)) for n in (0x60,0x61,0x21,0x1A)}
        bindings={n:v.InterruptService(None,handlers[n],*BINDINGS[n]) for n in handlers}
        handler=cb.foreground(lambda a,state,site:a.poll(state,site))
        poll_service=v.ForegroundPoll(None,handler)
        def binding(n):return None if c.get('unbound')==n else ct.pointer(bindings[n])
        services=Services(ct.pointer(cb.ports),ct.pointer(cb.bus),binding(0x60),binding(0x61),
            binding(0x21),binding(0x1A),None,None,None if c.get('null_poll') else ct.pointer(poll_service),0x19B9)
        out=self.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,
            child_status=out.child_status,service_status=out.service_status,child_entry=out.child_entry,
            memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor,
            services=access.service_events,polls=access.polls,irq_deliveries=access.irq_deliveries,crtc=access.crtc)

def set8(state,off,value):v.sync_memory_byte(state[0],state[2],state[1]['ds'],off,value)
def set16(state,off,value):v.put16(state[0],state[1]['ds'],off,value,state[2])
def compare(native,c,state):
    memory,r,device=state
    device=copy.deepcopy(device);device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    reference=original(c,bytearray(memory),dict(r),copy.deepcopy(device))
    allowed=c['expected'] if isinstance(c['expected'],tuple) else (c['expected'],)
    v.check(reference['status'] in allowed,f"{c['name']}: original status{reference['status']}, ip{reference['regs']['ip']:04X}")
    if native is not None:
        actual=native.run(c,memory,r,device);v.compare_states(c['name'],actual,reference)
        v.require(actual['polls']==reference['polls'],c['name']+': poll schedule differs')
        v.require(actual['crtc']==reference['crtc'],c['name']+': CRTC registers differ')
    return reference

def hashes():
    paths=set(source_files('game_frame'))|set((ROOT/'c').glob('*.h'))
    # The concurrent initializer worker owns these files; fixture code is a
    # real input and is hashed, but unrelated initializer C is not this closure.
    paths.discard(ROOT/'c/game_initialize.h')
    paths.update(ROOT/p for p in ('tests/game_frame.py','tests/game_transition.py','tests/view_scroll.py',
        'tests/verification.py','tests/game_initialize_prefix.py','tests/level_initialize.py','tools/cbuild.py',
        'tools/bounded_process.py','metadata/symbols.json','assets/vgalemmi.exe','src/entry_services.asm','src/game_timer.asm'))
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p.read_bytes()) for p in sorted(paths)}

def worker(directory,original_only=False):
    started=time.monotonic();before=hashes();native=None if original_only else Native(directory)
    memory,r,device,setup_evidence=fixture()
    pristine=(memory,r,device);rows=[];sites=set();edges=set();saved={}
    def run(c,state):
        print('CHECK '+c['name'],flush=True)
        out=compare(native,c,state);sites.update(out['sites']);edges.update(out['edges'])
        rows.append(dict(name=c['name'],steps=out['steps'],events=len(out['events']),
            sites=sorted(out['sites']),edges=sorted(out['edges']),status=out['status'],
            dispatches=out['dispatches'],
            irq_model='minimal183E foreground stores, IF honoured',polls=out['polls'],irq_deliveries=out['irq_deliveries']))
        if c['name'] in ('signed-tick-reject','skill-first-dispatch','double-wait','changed-frame-child-return'):
            saved[c['name']]=(c,copy.deepcopy(state))
        gc.collect()
        return out
    state=copy.deepcopy(pristine)
    # Cue23 opens creation; run several successive real-state ticks. First entry
    # is0186, later entries0105 include swap, budget polling and five IRQ stores.
    for off,value in ((0x1FCD,5),(0x0052,0x23),(0x004E,4),(0x25A7,0),(0x1F74,0),
        (0x200E,0),(0x48,1),(0x49,1),
        (0x0085,1),(0x0086,1),(0x20A7,0x31),(0x20A9,0x30),(0x20AA,0x30)):set8(state,off,value)
    state[1]['ip']=0x0186
    for tick in range(4):
        c=defaults(f'accepted-tick-{tick}',irq_site=0x0179,irq_count=5)
        out=run(c,state)
        v.check(out['memory'][v.physical(r['ds'],0x55)]==255,'cue23 did not open creation')
        if tick==0:v.check(out['memory'][v.physical(r['ds'],0x20A7)]==0x30 and out['memory'][v.physical(r['ds'],0x20A9)]==0x35 and out['memory'][v.physical(r['ds'],0x20AA)]==0x39,'ASCII minute borrow differs')
        state=(out['memory'],out['regs'],out['device'])
    v.check(state[0][v.physical(r['ds'],0x43)]>0,'accepted ticks did not create a creature')
    # Preserve a live created record; selection from its real producer is used
    # on the following tick. A press is eligible at the first3150 call.
    skill=copy.deepcopy(state);skill[1]['ip']=0x0186
    set8(skill,0x1FCD,5);set8(skill,0x82,2);set16(skill,0x14,1)
    set8(skill,0x61,0);set8(skill,0x2B,0)
    # Candidate ownership is established by the real3CDE child, using a pointer
    # over the created record; this preparation is original-only.
    x=v.get16(skill[0],skill[1]['ds'],0x88);y=v.get16(skill[0],skill[1]['ds'],0x8A)
    bx=v.get16(skill[0],skill[1]['ds'],0x8C);by=v.get16(skill[0],skill[1]['ds'],0x8E)
    set16(skill,0x10,(x+bx-v.get16(skill[0],skill[1]['ds'],0)+16)&65535)
    set16(skill,0x12,(y+by-8)&65535)
    skill[1]['ip']=0x3CDE
    # Supply one inherited near return and stop immediately after it.
    skill[1]['sp']=(skill[1]['sp']-2)&65535;v.put16(skill[0],skill[1]['ss'],skill[1]['sp'],0x0186)
    chosen=original(defaults('selection-setup'),*skill,stop=0x0186,core=False)
    skill=(chosen['memory'],chosen['regs'],chosen['device'])
    v.check(skill[0][v.physical(r['ds'],0x63)]>0,'pointer over a created creature did not select a candidate')
    inventory=skill[0][v.physical(r['ds'],0x6A)]
    out=run(defaults('skill-first-dispatch'),skill)
    v.check(out['memory'][v.physical(r['ds'],0x61)]==255,'first dispatch did not latch the press')
    v.check(out['memory'][v.physical(r['ds'],0x6A)]==(inventory-1)&255,'press did not consume exactly one skill')
    v.check([d['return_word'] for d in out['dispatches']]==[0x01B0,0x01C8] and
        [d['latch'] for d in out['dispatches']]==[0,255] and
        out['dispatches'][1]['inventory']==(inventory-1)&255,
        'first3150 must consume the press before the second3150 observes the shared latch')
    second=copy.deepcopy(skill);set8(second,0x63,0)
    out=run(defaults('skill-second-dispatch'),second)
    v.check([d['latch'] for d in out['dispatches']]==[0,0] and
        out['dispatches'][0]['candidate']==0 and out['dispatches'][1]['candidate']>0 and
        out['memory'][v.physical(r['ds'],0x6A)]==(inventory-1)&255,
        'fresh selection must make the second3150 consume a press gated at the first')
    # Additional controller fixtures retain the initialized game state and all
    # children, changing only named frame inputs and live control fields.
    def fresh():
        st=copy.deepcopy(state);st[1]['ip']=0x0186;set8(st,0x1FCD,5);set16(st,0x14,0);return st
    st=fresh();set8(st,0x4A,255);run(defaults('double-wait',irq_site=0x01DF,irq_poll=2),st)
    st=fresh();set8(st,0x4A,255);run(defaults('double-wait-null-poll',null_poll=True,expected=6),st)
    st=fresh();st[1]['ip']=0x0105;run(defaults('chosen-wait-irq',irq_site=0x0179,irq_poll=2,irq_count=5),st)
    st=fresh();st[1]['ip']=0x0105;set16(st,0x1FFE,1);set16(st,0x2000,1)
    run(defaults('split-word-borrow',irq_site=0x0179,irq_count=5),st)
    st=fresh();st[1]['ip']=0x0105;set16(st,0x1FFE,1)
    out=run(defaults('watchdog-reinstall',null_poll=True),st)
    v.check(0x1644 in out['sites'],'exhausted split budget did not reinstall the timer')
    st=fresh();set8(st,0x1FCD,0x80);run(defaults('signed-tick-reject',poll_stop=0x0179,expected=2),st)
    st=fresh();set8(st,0x200E,255);st[1]['ip']=0x0105
    run(defaults('option-ff-raster',irq_site=0x0179,irq_count=5),st)
    st=fresh();set8(st,0x200E,255);st[1]['ip']=0x0105
    run(defaults('option-ff-raster-retry',raster_edge_once=True,irq_site=0x0179,irq_count=5),st)
    st=fresh();set8(st,0x200E,255);st[1]['ip']=0x0105
    run(defaults('option-ff-poll-stop',poll_stop=0x0131,expected=2),st)
    st=fresh();set16(st,0x1FC7,0x20);out=run(defaults('quit-bit'),st)
    v.check(out['memory'][v.physical(r['ds'],0x4F)]==255 and out['memory'][v.physical(r['ds'],0x4E)]&2,
        'quit command did not request the closing transition')
    st=fresh()
    for off in (0x20A7,0x20A9,0x20AA):set8(st,off,0x30)
    out=run(defaults('time-zero'),st)
    v.check(out['memory'][v.physical(r['ds'],0x4F)]==255,'expired time did not request the closing transition')
    closing=(out['memory'],out['regs'],out['device'])
    for n in range(64):
        out=run(defaults(f'closing-{n}',irq_site=0x0179,irq_count=5,expected=(0,1)),closing)
        closing=(out['memory'],out['regs'],out['device'])
        if out['status']==1:break
    v.check(out['status']==1,'closing transition did not reach the46EB stop')
    st=fresh();set8(st,0x1F74,255);set16(st,0x1FC7,0x8000);out=run(defaults('BILLANDTED-cheat',expected=1),st)
    v.check(out['memory'][v.physical(r['ds'],0x40)]==100,'cheat completion result differs')
    st=fresh();set8(st,0x4F,255);set8(st,0x4E,0);set8(st,0x2010,0);set8(st,0x25A7,3)
    run(defaults('exit-pc-services',expected=1),st)
    st=fresh();set8(st,0x4F,255);set8(st,0x4E,0);set8(st,0x2010,255);set8(st,0x25A7,3)
    run(defaults('exit-external-service',expected=1),st)
    st=fresh();set8(st,0x4F,255);set8(st,0x4E,0);set8(st,0x2010,255);set8(st,0x25A7,0)
    run(defaults('exit-muted-service',expected=1),st)
    for name,values in (('all-accounted',((0x43,0),(0x47,0),(0x45,0))),
        ('all-accounted-stale-pass-count',((0x43,0),(0x47,0))),('paused-countdown',((0x2B,255),)),
        ('countdown-divider-byte-wrap',((0x85,0),)),('countdown-seconds-borrow',((0x20A7,0x30),(0x20A9,0x31),(0x20AA,0x30))),
        ('cheat-enabled-key-absent',((0x1F74,255),))):
        st=fresh()
        for off,value in values:set8(st,off,value)
        result=run(defaults(name),st)
        if name=='all-accounted':v.check(result['memory'][v.physical(r['ds'],0x4F)]==255,'accounted entities did not request fade')
        if name=='all-accounted-stale-pass-count':v.check(result['memory'][v.physical(r['ds'],0x4F)]!=255,'zero-bound draw unexpectedly cleared its stale pass count')
        if name=='countdown-divider-byte-wrap':v.check(result['memory'][v.physical(r['ds'],0x85)]==255,'zero divider did not byte-wrap')
    for key in (0x80,0x100):
        st=fresh();set16(st,0x1FC7,key);set8(st,0x25A7,3);set8(st,0x2010,0)
        run(defaults(f'command-{key}'),st)
    st=fresh();set16(st,0x1FC7,0x80);set8(st,0x2010,0);set8(st,0x25A7,0)
    run(defaults('command-muted-pc'),st)
    st=fresh();set16(st,0x1FC7,0x80);set8(st,0x2010,255)
    run(defaults('int61-returned-ax-command',sound_race=True,sound_ax=0x100),st)
    st=fresh();set8(st,0x4E,4);set8(st,0x52,15);set8(st,0x25A7,3);set8(st,0x2010,255)
    run(defaults('unbound-cue-service',unbound=0x61,expected=5,child_status=3),st)
    st=fresh();run(defaults('changed-frame-child-return',return_patch=0x01A0,expected=4),st)
    mutants=[]
    for mutation,name in ({} if original_only else {1:'signed-tick-reject',2:'skill-first-dispatch',3:'double-wait',4:'changed-frame-child-return'}).items():
        c,st=saved[name]
        try:compare(Native(directory,mutation),c,st)
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,mismatch=str(error),completed=True))
        else:raise v.OracleFailure(f'frame mutant{mutation} survived')
        gc.collect()
    v.check(before==hashes(),'frame inputs changed during campaign')
    write_json(REPORT.with_name('game-frame-original-preflight.json') if original_only else REPORT,dict(code_ranges=OWN_RANGES,own_bytes=sum(i.size for i in OWN.values()),setup=setup_evidence,
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(edges&EDGES),unexecuted_own_sites=sorted(set(OWN)-sites),
        unexecuted_own_edges=sorted(EDGES-edges),cases=rows,mutations=mutants,runtime_seconds=time.monotonic()-started,
        input_hashes=before,limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,steps=MAX_STEPS,events=MAX_EVENTS)))
    print(f'PASS game frame: {len(rows)} boundaries, {len(set(OWN)&sites)}/{len(OWN)} own sites, {len(EDGES&edges)}/{len(EDGES)} outcomes, {len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if len(sys.argv)==3 and sys.argv[1]=='--original-worker':worker(sys.argv[2],True);return
    with temporary_build_directory(prefix='game-frame-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker' if sys.argv[1:]==['--original-only'] else '--worker',str(directory)],cwd=ROOT,
            timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()
