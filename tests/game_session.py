"""00FB session with real INT08/09 at explicit foreground polls only.

No preemption inside children or handlers and no nested IRQs. Both sides push
FLAGS/CS/IP on live SS:SP, honour IF, read the installed live IVT and execute
17C7/16D4 through their real IRET. INT33, sound INT60/61, saved BIOS INT08,
DOS vector writes and finite ports are declared platform providers. The loaded
normal LEVEL/resources and earlier4551/startup clears are constructed, never a
boot snapshot. Every poll compares full RAM/registers/ordered events/VGA; thus
each successive frame handoff is checked before any next input is delivered.
The read-only session observer also compares the exact0105/46EB boundaries;
it never injects interrupts or changes canonical state.
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
import game_frame as frame
import game_initialize as initialize
import game_timer as timer
import keyboard_input as keyboard
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

OWN_RANGES=((0xFB,0x105),)
OWN={i.address:i for i in v.MD.disasm(v.IMAGE[0xFB:0x105],0xFB)}
INS=frame.INS|initialize.INS|timer.INS|keyboard.BASE_INS|OWN
POLLS={0x04AA,0x04BA,0x0131,0x0179,0x01DF}
BINDINGS={0x10:(0xB000,0x100),0x21:(0xB000,0x200),0x33:(0xB000,0x300),
          0x60:(0xB000,0x400),0x61:(0xB000,0x500),0x1A:(0xB000,0x600)}
CHAIN=(0xB000,0x700)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=1800,768,30_000_000,2_000_000
REPORT=BUILD/'game-session-differential.json'
CHECKPOINT=0xC001
FRAME_BOUNDARY=0xC002
OBSERVE=ct.CFUNCTYPE(None,ct.c_void_p,v.MEM,ct.POINTER(v.Regs))

class Services(ct.Structure):
    _fields_=[('initialize',ct.POINTER(frame.initialize.GameServices)),('frame',ct.POINTER(frame.Services)),
        ('observer_context',ct.c_void_p),('observe',OBSERVE)]
class IrqServices(ct.Structure):
    _fields_=[('mouse',ct.POINTER(v.InterruptService)),('int60',ct.POINTER(v.InterruptService)),
        ('int61',ct.POINTER(v.InterruptService)),('saved_int08',ct.POINTER(v.InterruptService)),
        ('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),('code_segment',ct.c_uint16)]
class IrqResult(ct.Structure):
    _fields_=[('registers',v.Regs)]+[(n,ct.c_uint16) for n in ('status','handler_status','child_status','service_status')]

class Access(v.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
        self.status_reads=0;self.pit_reads=0;self.crtc={0x3B5:0xA5,0x3D5:0xA5}
        self.frame=-1;self.mouse=(150,100,0);self.scan=0;self.polls=[];self.deliveries=[]
        self.queue=[];self.at_checkpoint=False
        self.raster_delivered=False
    def inp(self,port,flags,mask=v.FLAGS):
        if port in (0x3B5,0x3D5):value=self.crtc[port]
        elif port in (0x3DA,0x3BA):
            value=(0,9,9,0)[self.status_reads%4];self.status_reads+=1
            v.check(self.status_reads<100_000,'finite display input budget exhausted')
        elif port==0x3C5:value=0x93
        elif port==0x40:
            value=(self.c['pit']>>(8*self.pit_reads))&255;self.pit_reads+=1
            v.check(self.pit_reads<=2,'PIT input budget exhausted')
        elif port==0x60:value=self.scan
        elif port==0x61:value=0x15
        elif port==0x64:value=0
        else:raise v.OracleFailure(f'undeclared session input{port:04X}')
        self.cursor+=1;self.emit('in',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=v.FLAGS):
        v.check(port in (0x3B4,0x3B5,0x3D4,0x3D5,0x3C0,0x3C4,0x3C5,0x3C8,0x3C9,
                        0x43,0x40,0x20,0x61,0x64,0x60),'undeclared session output')
        if port in self.crtc:self.crtc[port]=value
        self.emit('out8',port,value,flags,mask)
    def out_word(self,port,value,flags,mask=v.FLAGS):
        if port in (0x3D4,0x3B4):self.crtc[(port,value&255)]=value>>8
        else:self.device.out(port,value,flags)
        self.emit('out',port,value,flags,mask)
    def script(self,r,site):
        self.polls.append((site,r['flags']))
        v.check(len(self.polls)<200,'session poll budget exhausted')
        scans=[];ticks=1
        if site==0x0131:
            ticks=0 if self.raster_delivered else 1;self.raster_delivered=True
        if site==0x0179:
            self.frame+=1;ticks=5
            if self.c['scenario']=='gameplay':
                n=self.frame
                self.mouse=(150,100,0)
                if n==40:self.mouse=(328,70,0)
                if n==41:self.mouse=(8,70,0)
                if n==73:scans=[0x3E]  # select ordinal3 before the panel click
                if n==74:scans=[0xBE]
                if n==76:self.mouse=(40,184,1)  # panel ordinal2, climbing
                if n in (77,78,79):
                    ds=r['ds'];x=v.get16(self.memory,ds,0x88);y=v.get16(self.memory,ds,0x8A)
                    bx=v.get16(self.memory,ds,0x8C);by=v.get16(self.memory,ds,0x8E)
                    self.mouse=((x+bx-v.get16(self.memory,ds,0)+16)&65535,
                                (y+by-8)&65535,1 if n==78 else 0)
                if n in (82,85):scans=[0x4E]  # real pause toggle command
                if n in (83,86):scans=[0xCE]
                if n==88:scans=[keyboard.PINNED_BINDINGS[5]] # quit mask0020
            if self.c.get('stop_frame')==self.frame:return None
        self.queue=[(9,scan,site) for scan in scans]+[(8,0,site)]*ticks
        return list(self.queue)
    def reset_observations(self):
        self.events=v.PackedEvents();self.device.trace=v.PackedDeviceTrace(MAX_EVENTS)
        self.service_events=[]

def provider(number):
    def execute(a,r):
        entry=dict(r)
        if number==0x10:
            # The same pinned BIOS identification contract as video_probe.
            if r['ax']==0x1A00:r.update(ax=(r['ax']&0xFF00)|0x1A,bx=7)
            elif r['ax']>>8==0x12:r.update(bx=r['bx']&0xFF00,cx=r['cx']&0xFF00)
            elif r['ax']>>8==0x0F:r['ax']=(r['ax']&0xFF00)|3
            else:v.check(r['ax']==0x8D,'undeclared BIOS video request')
        elif number==0x21:
            v.check(r['ax'] in (0x2508,0x2560),'undeclared DOS vector request')
            n=r['ax']&255;a.word_write(0,n*4,r['dx'],r['flags']);a.word_write(0,n*4+2,r['ds'],r['flags'])
        elif number==0x33:
            if r['ax']==4:v.check((r['cx'],r['dx'])==(150,100),'initial mouse position differs')
            else:
                v.check(r['ax']==3,'undeclared mouse function')
                r['cx'],r['dx'],r['bx']=a.mouse
        elif number==0x1A:v.check(r['ax']==0x100,'undeclared clock request')
        elif number=='chain':
            v.check(v.get16(a.memory,r['ss'],r['sp'])==0x189D,'BIOS chain frame differs')
            v.check(not r['flags']&0x200,'BIOS chain requires CLI')
            # The saved BIOS fixture acknowledges the PIC, before its real IRET.
            a.out(0x20,0x20,r['flags'])
        else:v.check(number in (0x60,0x61),'undeclared service')
        a.service_events.append(dict(number=number,entry=entry,returned=dict(r)))
        return 0
    return execute

def setup(scenario,**kw):
    c=next(c for c in initialize.cases() if c['name']=='carry-neg-nonzero')
    c=c|dict(name=scenario,scenario=scenario,option=0,mouse=0,mode=4,patch='')|kw
    memory,r,device=initialize.setup(c);r['ip']=0xFB
    ds=r['ds']
    # Startup/platform fields, outside the session's per-level clear.
    for off,value in ((0x1F73,0),(0x25A6,0),(0x25A7,0),(0x2010,0),(0x200A,0),(0x200B,0),
                      (0x1FE3,0),(0x1FCD,0),(0x2002,0)):
        v.put8(memory,ds,off,value)
    v.put16(memory,ds,0x1FC7,0)
    for i,value in enumerate(keyboard.PINNED_BINDINGS):v.put8(memory,ds,0x201F+i,value)
    for n,(cs,ip) in BINDINGS.items():v.put16(memory,0,n*4,ip);v.put16(memory,0,n*4+2,cs)
    # The earlier keyboard installer is outside00FB; its actual IVT result is
    # an explicit precondition, not an intercepted hardware-vector replacement.
    v.put16(memory,0,9*4,0x16D4);v.put16(memory,0,9*4+2,c['load'])
    v.put16(memory,ds,0x1FBE,CHAIN[1]);v.put16(memory,ds,0x1FC0,CHAIN[0])
    v.put8(memory,c['load'],0x83BE,255)
    if scenario=='gameplay':
        # Normal LEVEL commands, not runtime map/VGA patches: the real36B6
        # terrain initializer draws a solid floor beneath the default release
        # coordinates. Reuse the maintained fixture's normal tile record and
        # explicitly constructed graphics heap. No game-state producer is
        # bypassed; creation retains its real20-tick initial countdown.
        commands=[frame.level.command(x,32) for x in range(208,353,24)]
        commands.append((0xFFFF,0x57AD))
        for n,words in enumerate(commands):
            for delta,value in enumerate(b''.join(w.to_bytes(2,'big') for w in words)):
                v.put8(memory,ds,0x10EB+4*n+delta,value)
        frame.level.piece.record(memory,ds,2,24,3,0x2000,0x4000)
        memory[0x50000:0x60000]=bytes((255,))*65536
    if scenario=='time-up':
        # Loaded normal LEVEL header has zero minutes: real initialization
        # consumes it, then foreground detects00:00 without provider patches.
        v.put8(memory,ds,0x0FD1,0);v.put8(memory,ds,0x0FD2,0)
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return c,memory,r,device

class Reference:
    def __init__(self,c,memory,r,device):
        self.access=a=Access(c,memory,r,device);self.frames=[];self.resume_poll=False;self.resume_frame=False
        def before(m,i):
            if i.address==0x46EB:m.stop(0);return True
            if i.address==0x0105 and not m.hardware_frames:
                if not self.resume_frame:m.stop(FRAME_BOUNDARY);return True
                self.resume_frame=False
            if i.address in POLLS and not m.hardware_frames:
                if not self.resume_poll:m.stop(CHECKPOINT);return True
                if a.queue:
                    number,a.scan,site=a.queue.pop(0)
                    a.deliveries.append((number,a.scan,site))
                    v.check(m.hardware_interrupt(number,returns={0x18B1} if number==8 else {0x17B3}),
                            'scripted IRQ unexpectedly masked')
                    return True
                self.resume_poll=False
            if i.mnemonic in ('call','lcall'):self.frames.append((i.address+i.size,i.mnemonic=='lcall'))
            return False
        def expected(m,off):
            v.check(bool(self.frames),'undeclared session RET');ip,far=self.frames.pop()
            v.check(not far,'RET consumed far frame');return {ip}
        def expected_far(m,off):
            v.check(bool(self.frames),'undeclared session RETF');ip,far=self.frames.pop()
            v.check(far,'RETF consumed near frame');return {(c['load'],ip)}
        def interrupt(m,number):
            v.check(number in BINDINGS,'undeclared session interrupt')
            m.software_interrupt(number,m.state()['ip'],BINDINGS[number],provider(number))
            v.check(not m.stopped,'platform service stopped')
        self.machine=v.OriginalMachine(c,memory,r,device,False,instructions=INS,access=a,
            outer_returns=(),child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected_far for p,i in INS.items() if i.mnemonic=='retf'},
            far_calls={0x1899:(0x189D,CHAIN,provider('chain'))},
            mutable_operands=((0x4137,2),(0x5884,2)),before=before,interrupt=interrupt,max_steps=MAX_STEPS)
    def advance(self):
        self.machine.stopped=False;self.machine.status=0
        result=self.machine.run();result['services']=self.access.service_events
        return result
    def resume(self,r,site):
        script=self.access.script(r,site);self.resume_poll=True
        return script

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'session-{mutation}.dll',mutation,'game_session')))
        self.fn=self.lib.lmn_game_session_core;self.fn.restype=frame.Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(Services)]
        self.irq=self.lib.lmn_deliver_hardware_irq;self.irq.restype=IrqResult
        self.irq.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_uint16,ct.POINTER(IrqServices)]
    def run(self,c,memory,r,device):
        reference=Reference(c,bytearray(memory),dict(r),copy.deepcopy(device))
        memory,device=bytearray(memory),copy.deepcopy(device);a=Access(c,memory,r,device);cb=v.NativeCallbacks(a)
        callbacks={n:cb.interrupt(provider(n)) for n in (*BINDINGS,'chain')}
        bindings={n:v.InterruptService(None,callbacks[n],*(CHAIN if n=='chain' else BINDINGS[n])) for n in callbacks}
        p=lambda n:ct.pointer(bindings[n])
        irq=IrqServices(p(0x33),p(0x60),p(0x61),p('chain'),ct.pointer(cb.ports),ct.pointer(cb.bus),c['load'])
        rows=[];mismatches=[]
        def compare(state,status):
            ref=reference.advance();ref_status=ref['status'];ref['status']=status
            actual=dict(regs=state,status=status,memory=memory,device=device,events=a.events,
                services=a.service_events,providers=a.providers,cursor=a.cursor)
            v.compare_states(c['name'],actual,ref)
            v.require(a.crtc==reference.access.crtc,'CRTC state differs')
            v.require(a.deliveries==reference.access.deliveries,'interrupt schedule differs')
            ds=state['ds']
            rows.append(dict(site=state['ip'],frame=a.frame,steps=ref['steps'],events=len(a.events),
                counter=memory[v.physical(ds,0x1FCD)],slots=memory[v.physical(ds,0x43)],
                origin=v.get16(memory,ds,0),pointer=[v.get16(memory,ds,0x10),v.get16(memory,ds,0x12)],
                selector=memory[v.physical(ds,0x82)],inventory=memory[v.physical(ds,0x6A)],
                paused=memory[v.physical(ds,0x2B)],end=memory[v.physical(ds,0x4F)],
                transition=memory[v.physical(ds,0x4E)],creation_gate=memory[v.physical(ds,0x55)],
                creation_countdown=memory[v.physical(ds,0x48)],
                countdown=[memory[v.physical(ds,p)] for p in (0x20A7,0x20A9,0x20AA)],
                candidate=memory[v.physical(ds,0x63)],record=list(memory[v.physical(ds,0x88):v.physical(ds,0x88)+0x2D]),
                ram_sha256=sha(memory)))
            a.reset_observations();reference.access.reset_observations()
            return ref_status
        def poll(access,state,site):
            if mismatches:return 0xCA11
            try:
                if site in (0x04AA,0x04BA) or (site==0x0179 and (access.frame+1)%10==0):
                    print(f'CHECK {c["name"]} poll{site:04X} frame{access.frame+1}',flush=True)
                v.require(compare(state,0)==CHECKPOINT,'reference did not reach same poll')
                script=access.script(state,site)
                other=reference.resume(state,site)
                v.require(script==other,'script differs')
                if script is None:return 0xCA11
                for number,scan,where in script:
                    access.scan=scan;access.deliveries.append((number,scan,where))
                    result=self.irq((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**state)),number,ct.byref(irq))
                    state.update({n:getattr(result.registers,n) for n in v.REG_NAMES})
                    v.require(result.status==0,f'IRQ stopped{result.status}/{result.handler_status}')
                return 0
            except v.Mismatch as error:mismatches.append(error);return 0xCA11
        @OBSERVE
        def observe(_,mem,registers):
            if mismatches:return
            try:
                v.check(ct.addressof(mem.contents)==ct.addressof((ct.c_uint8*v.SIZE).from_buffer(memory)),
                        'observer canonical RAM binding differs')
                state={n:getattr(registers.contents,n) for n in v.REG_NAMES}
                expected=0 if state['ip']==0x46EB else FRAME_BOUNDARY
                v.require(compare(state,0)==expected,'reference did not reach exact frame boundary')
                reference.resume_frame=True
            except v.Mismatch as error:mismatches.append(error)
            except BaseException as error:v.callback_failure(error)
        handler=cb.foreground(poll);foreground=v.ForegroundPoll(None,handler)
        video=frame.initialize.VideoServices(p(0x10),ct.pointer(cb.ports),ct.pointer(cb.bus))
        level=frame.initialize.LevelServices(None,None,ct.pointer(cb.bus),ct.pointer(cb.ports))
        init=frame.initialize.GameServices(ct.pointer(video),ct.pointer(cb.ports),ct.pointer(cb.bus),ct.pointer(level),
            c['game_data_segment'],0,p(0x33),p(0x21),ct.cast(ct.pointer(foreground),ct.c_void_p))
        frames=frame.Services(ct.pointer(cb.ports),ct.pointer(cb.bus),p(0x60),p(0x61),p(0x21),p(0x1A),
            None,None,ct.pointer(foreground),c['game_data_segment'])
        services=Services(ct.pointer(init),ct.pointer(frames),None,observe)
        out=self.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),ct.byref(services))
        if mismatches:raise mismatches[0]
        state={n:getattr(out.registers,n) for n in v.REG_NAMES}
        if c.get('stop_frame') is not None:
            v.require((out.status,out.child_status,out.service_status)==(3,2,0xCA11),'poll stop not propagated')
        else:
            v.require(out.status==0,f'session stopped{out.status}/{out.child_status} at{state["ip"]:04X}')
            v.require(bool(rows) and rows[-1]['site']==0x46EB,'session exit was not observed')
            v.check(state['ip']==0x46EB,'session exit target differs')
        m=reference.machine
        return dict(rows=rows,sites=sorted(m.sites),edges=sorted(m.edges),steps=m.steps,
                    deliveries=a.deliveries,status=out.status)

FIXTURE_SOURCES=set()
def remember_fixture_sources():
    FIXTURE_SOURCES.update(Path(m.__file__).resolve() for m in tuple(sys.modules.values()) if getattr(m,'__file__',None)
        and Path(m.__file__).suffix=='.py' and Path(m.__file__).resolve().parent==ROOT/'tests')

def hashes():
    paths=set(source_files('game_session'))
    paths.update(p for p in (ROOT/'c').glob('*.h') if p.name!='level_result.h')
    paths.update(ROOT/p for p in ('tests/game_session.py','tests/verification.py','tools/cbuild.py',
        'tools/bounded_process.py','tools/difftest.py','metadata/symbols.json','assets/vgalemmi.exe'))
    # Imported fixture domains and normal LEVEL/resource construction are inputs.
    paths.update(FIXTURE_SOURCES)
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}

def helper_case(native,*,masked=False,ss=None,sp=None):
    """IRQ09 full original/native parity independent of session scheduling."""
    c,memory,r,device=setup('helper')
    r['ip']=0x04AA
    if masked:r['flags']&=~0x200
    if ss is not None:r['ss']=ss
    if sp is not None:r['sp']=sp
    reference_memory=bytearray(memory);reference_device=copy.deepcopy(device)
    a=Access(c,memory,r,device);ref=Access(c,reference_memory,r,reference_device)
    a.scan=ref.scan=0x4E
    frames=[];attempted=[]
    def before(m,i):
        if i.address==0x04AA:
            if not attempted:
                attempted.append(m.hardware_interrupt(9,returns={0x17B3}))
                if attempted[-1]:return True
            m.stop(1 if masked else 0);return True
        if i.mnemonic=='call':frames.append(i.address+i.size)
        return False
    def expected(m,off):v.check(bool(frames),'undeclared keyboard child');return {frames.pop()}
    machine=v.OriginalMachine(c,reference_memory,dict(r),reference_device,False,
        instructions=keyboard.BASE_INS|{0x04AA:initialize.INS[0x04AA]},access=ref,outer_returns=(),
        child_returns={p:expected for p,i in keyboard.BASE_INS.items() if i.mnemonic=='ret'},
        before=before,max_steps=1000)
    reference=machine.run();cb=v.NativeCallbacks(a)
    services=IrqServices(None,None,None,None,ct.pointer(cb.ports),ct.pointer(cb.bus),c['load'])
    result=native.irq((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),9,ct.byref(services))
    actual=dict(regs={n:getattr(result.registers,n) for n in v.REG_NAMES},status=result.status,
        memory=memory,device=device,events=a.events,providers=a.providers,cursor=a.cursor)
    v.compare_states('hardware09-masked' if masked else 'hardware09',actual,reference)
    v.check(result.handler_status==0,'keyboard helper handler stopped')
    return dict(masked=masked,ss=r['ss'],sp=r['sp'],steps=reference['steps'],events=len(a.events),sites=sorted(reference['sites']))

def independent(result):
    rows={r['frame']:r for r in result['rows'] if r['site']==0x0179}
    v.check(all(row['counter']==0 for n,row in rows.items() if n>=0),'accepted ticks did not drop/reset excess IRQ counts')
    if result['name']=='gameplay':
        v.check(rows[69]['slots']>0,'release cue did not create a creature')
        v.check(rows[40]['origin']==rows[39]['origin']+8 and rows[41]['origin']==rows[39]['origin'],
                'mouse edge scroll did not move right and back')
        walking=[r for n,r in rows.items() if 69<=n<=74 and r['record'][8:10]==[0,0]]
        v.check(len(walking)>=2 and walking[0]['record'][:2]!=walking[-1]['record'][:2],
                'released creature did not land and walk on the LEVEL-produced floor')
        v.check(rows[73]['selector']==3 and rows[76]['selector']==2,'panel click did not change ordinal3 to2')
        v.check(rows[77]['candidate']>0,'mouse over the real created record did not select it')
        v.check(rows[78]['inventory']==rows[77]['inventory']-1,'skill assignment did not consume one item')
        v.check(rows[82]['paused']==255 and rows[84]['paused']==255 and rows[85]['paused']==0,
                'IRQ09 pause toggle/hold/resume differed')
        v.check(rows[88]['end']==255,'quit scan did not reach foreground closing request')
    elif result['name']=='time-up':
        v.check(rows[0]['countdown']==[0x30]*3 and rows[0]['end']==255,'zero-minute LEVEL did not request time-up')

def worker(directory):
    started=time.monotonic();fixtures=[setup('gameplay'),setup('time-up'),setup('raster',option=255,stop_frame=1)]
    remember_fixture_sources();before=hashes();native=Native(directory);results=[];mutants=[]
    for c,m,r,d in fixtures:
        name=c['scenario'];print('CHECK session '+name,flush=True)
        result=native.run(c,m,r,d);result['name']=name;results.append(result)
        write_json(BUILD/'game-session-progress.json',dict(accepted=False,cases=results,input_hashes=before))
        independent(result)
        print(f'PASS {name}: {len(result["rows"])} checkpoints, {result["steps"]} instructions',flush=True)
        gc.collect()
    helpers=[helper_case(native,masked=masked,**placement) for masked,placement in
        ((False,{}),(True,{}),(False,dict(ss=0xFFFF,sp=3)))]
    try:helper_case(Native(directory,11),masked=True)
    except v.Mismatch as error:mutants.append(dict(mutation=11,mismatch=str(error),completed=True))
    else:raise v.OracleFailure('IF mutant survived')
    for mutation in (1,3,12):
        c,m,r,d=setup('gameplay',stop_frame=0)
        try:Native(directory,mutation).run(c,m,r,d)
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,mismatch=str(error),completed=True))
        else:raise v.OracleFailure(f'session mutant{mutation} survived')
        gc.collect()
    after=hashes();changed=[p for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
    v.check(not changed,'session inputs changed during campaign: '+str(changed))
    sites=set(p for row in results for p in row['sites']);edges=set(tuple(e) for row in results for e in row['edges'])
    write_json(REPORT,dict(code_ranges=OWN_RANGES,own_bytes=sum(i.size for i in OWN.values()),
        own_executed_instruction_addresses=sorted(set(OWN)&sites),executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges),cases=results,helpers=helpers,mutations=mutants,runtime_seconds=time.monotonic()-started,
        input_hashes=before,limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,steps=MAX_STEPS,events=MAX_EVENTS),
        irq_domain=__doc__))
    print('PASS native game session',flush=True)

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-worker':
        c,m,r,d=setup('gameplay',stop_frame=0);Native(sys.argv[2]).run(c,m,r,d);print('PASS session initialization and real IRQ smoke',flush=True);return
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='game-session-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--smoke-worker' if sys.argv[1:]==['--smoke'] else '--worker',str(directory)],cwd=ROOT,timeout=SECONDS,
            memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()
