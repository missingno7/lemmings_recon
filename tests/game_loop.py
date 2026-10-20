"""Continuous menu/load/session/result differential with real IRQ08/09.

Constructed startup state, pinned UI resources and normal LEVEL files; no boot
or runtime snapshot. The second level's input header has zero minutes (the
existing session time-up fixture), while its real terrain/objects stay intact.
Only explicit polls deliver IRQs; ordinary-RAM DAT children retain their typed
DOS ABI/event projection, exactly as in level_start. No child results are stubbed.
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
import game_session as session
import main_menu as menu
import level_start as start
import level_result as result
import resource_select as resources
import menu_timer
from bounded_process import temporary_build_directory,run_bounded
from cbuild import build,source_files
from common import BUILD,sha,write_json

INS=session.INS|menu.INS|start.INS|result.INS|menu_timer.INS
POLLS=session.POLLS|result.POLLS|{0x4453,0x446D,0x4660,0x4683,0x468B,
    0x4D23,0x43CE,0x49D2,0x49DA,0x4AED,0x4AF5}
BOUNDARIES={0x43F2,0x4401,0x4967,0x4A01,0x454C,0x4551,0xFB,0x46EB}
CHECKPOINT,BOUNDARY,RETRY_BOUNDARY=0xC001,0xC002,0xC003
MAX_STEPS,MAX_EVENTS=60_000_000,10_000_000
REPORT=BUILD/'game-loop-differential.json'
OBSERVE=session.OBSERVE
class Services(ct.Structure):
    _fields_=[('video',ct.POINTER(menu.VideoServices)),('dos',ct.POINTER(v.InterruptService)),
        ('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),('poll',ct.POINTER(v.ForegroundPoll)),
        ('start',ct.POINTER(start.Services)),('session',ct.POINTER(session.Services)),
        ('result',ct.POINTER(result.Services)),('observer_context',ct.c_void_p),('observe',OBSERVE),
        ('game_data_segment',ct.c_uint16),('code_segment',ct.c_uint16)]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs)]+[(n,ct.c_uint16) for n in
        ('status','core_entry','core_status','child_status','service_status')]

INS[0x4B1C]=next(v.MD.disasm(v.IMAGE[0x4B1C:0x4B24],0x4B1C))
ASSETS=set()
def asset(name):
    p=ROOT/'assets'/name;ASSETS.add(p);return p.read_bytes()

class Provider(resources.Provider):
    def file(self,function,seg,off,flags):
        name=self.filename(seg,off).decode('ascii').lower();kind=self.kind(name.encode())
        selection=self.mem[v.physical(self.data,0x1F6B)]
        payload=asset(name)
        if kind=='graphics':payload=payload[:resources.section_spans(payload)[1][1]]
        if kind=='level' and selection==1:
            # Input header before the original loader, not a live countdown patch.
            records=[bytearray(resources.decode_section(payload[a:b])[0])
                     for a,b in resources.section_spans(payload)]
            for record in records:record[6:8]=b'\0\0'
            payload=b''.join(start.packed(bytes(record)) for record in records)
        self.payloads[kind]=payload
        value,count,returned=super().file(function,seg,off,flags)
        if function==0x43 and self.case.get('retry_stop'):return 5,count,returned|1
        return value,count,returned

def setup(entry=0x43F2):
    c=next(c for c in menu.cases() if c['kind']=='startup' and c.get('media',0)!=0xFD)
    c=c|dict(name=f'loop-{entry:04x}',load=0x1010,seed=0x100F,flags=0x202,group=0,
        entry=0,option=0,toggle=0,driver=0,pinned=True,mode=4,media=0,keys=(0x80,),pit=0x1234)
    memory,r,device=menu.setup(c);ds=r['ds'];r.update(ip=entry,ss=0x9000,sp=0x8000,flags=0x202)
    # 0027..0031 startup clear. Resource/UI buffers above2011 come from the
    # same pinned MAIN.DAT fixtures used by main_menu; allocation and device
    # fields below are explicit outputs of startup producers, never dumps.
    memory[v.physical(ds,0):v.physical(ds,0)+0x2012]=bytes(0x2012)
    for off,value in ((0x1FEE,0x4000),(0x1FF0,0x7000),(0x1FE4,0x5000),(0x1FF4,0x7FFF),
        (0x1FDA,0x3D4),(0x1F7C,4),(0x1FC9,0x4567),(0x1FBE,session.CHAIN[1]),(0x1FC0,session.CHAIN[0])):
        v.put16(memory,ds,off,value)
    for off,value in ((0x200C,255),(0x200F,255),(0x25A7,0),(0x1F71,0),(0x1F73,0),(0x2010,0),(0x200A,0),(0x200B,0)):
        v.put8(memory,ds,off,value)
    for i,value in enumerate(session.keyboard.PINNED_BINDINGS):v.put8(memory,ds,0x201F+i,value)
    for i,value in enumerate(session.keyboard.PINNED_CHARACTERS):v.put8(memory,ds,0x202E+i,value)
    v.put8(memory,r['cs'],0x83BE,255)
    for n,(cs,ip) in session.BINDINGS.items():v.put16(memory,0,n*4,ip);v.put16(memory,0,n*4+2,cs)
    for n,ip in ((8,0x4C47),(9,0x16D4)):
        v.put16(memory,0,n*4,ip);v.put16(memory,0,n*4+2,r['cs'])
    for name,value in dict(DatCacheEnabled=0,DatCacheSelected=0,DatCacheRecordCount=0,
        DatRetryEnabled=255,DatCriticalErrorFlag=0).items():v.put8(memory,ds,resources.field(name),value)
    c['game_data_segment']=ds
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return c,memory,r,device

class Access(session.Access):
    def __init__(self,*args):
        super().__init__(*args);self.max_events=MAX_EVENTS;self.device.trace=v.PackedDeviceTrace(MAX_EVENTS);self.quiet=False;self.omitted=0
        self.screen='menu';self.menu_count=0;self.sessions=0;self.results=0;self.typed=0
        self.last_scan=None;self.cheated=False;self.screens=[];self.queue=[];self.vectors=[]
    def inp(self,port,flags,mask=v.FLAGS):
        if port in (0x3DA,0x3BA):
            # Same finite cyclic provider as game_session, with an aggregate
            # allowance for menu, three loads/sessions and all result screens.
            value=(0,9,9,0)[self.status_reads%4];self.status_reads+=1
            v.check(self.status_reads<500_000,'loop display input budget exhausted')
            self.cursor+=1;self.emit('in',port,value,flags,mask);return value
        return super().inp(port,flags,mask)
    def emit(self,kind,address,value,flags,mask=v.FLAGS):
        if self.quiet and kind in ('read','write'):
            v.check(not v.VGA_BASE<=address<v.VGA_END,'typed DOS child reached VGA')
            self.omitted+=1;v.check(self.omitted<10_000_000,'legacy RAM event budget exhausted');return
        super().emit(kind,address,value,flags,mask)
    def boundary(self,r):
        ip=r['ip'];ds=r['ds']
        self.screens.append((ip,self.memory[v.physical(ds,0x1F6B)],self.memory[v.physical(ds,0x1F6D)]))
        if ip in (0x43F2,0x4401):self.screen='menu';self.menu_count+=1
        elif ip==0x4967:self.screen='code'
        elif ip in (0x454C,0x4551):self.screen='briefing'
        elif ip==0xFB:self.screen='session';self.sessions+=1;self.frame=-1;self.raster_delivered=False;self.pit_reads=0
        elif ip==0x46EB:self.screen='result';self.results+=1
    def script(self,r,site):
        self.polls.append((site,r['flags']));v.check(len(self.polls)<2500,'loop poll budget exhausted')
        scans=[];ticks=0
        if site==0x4453:
            if self.results==3:return None
            self.mouse=(150,100,0);ticks=1
        elif site==0x446D:
            self.mouse=(150,100,0 if self.menu_count==1 else 1);ticks=1
        elif site==0x4D23 and r['bx']==0:
            if self.last_scan is not None:scans.append(self.last_scan|0x80);self.last_scan=None
            if self.screen=='menu' and self.menu_count==1:scans.append(0x3C);self.last_scan=0x3C
            elif self.screen=='code' and self.typed<11:
                char=b'BILLANDTED\r'[self.typed];self.typed+=1
                scan=next(i for i,x in enumerate(session.keyboard.PINNED_CHARACTERS) if x==char and i>0)
                scans.append(scan);self.last_scan=scan
        elif site==0x4660:self.mouse=(150,100,0);ticks=1
        elif site==0x4683:self.mouse=(150,100,1);ticks=1
        elif site in (0x04AA,0x04BA):self.mouse=(150,100,0);ticks=1
        elif site==0x0131:
            ticks=0 if self.raster_delivered else 1;self.raster_delivered=True
        elif site==0x0179:
            self.frame+=1;ticks=5
            if self.sessions==1 and not self.cheated:scans.append(0x4C);self.cheated=True
            elif self.sessions==1 and self.frame==1:scans.append(0xCC)
        elif site==0x01DF:ticks=1
        elif site==0x47A9:self.mouse=(150,100,0);ticks=1
        elif site==0x47B1:self.mouse=(150,100,1 if self.results<3 else 2);ticks=1
        if self.c.get('stop_poll')==site:return None
        self.queue=[(9,scan,site) for scan in scans]+[(8,0,site)]*ticks
        return list(self.queue)

def provider(number):
    base=session.provider(number)
    if number!='chain':return base
    def chain(a,r):
        entry=dict(r);v.check(v.get16(a.memory,r['ss'],r['sp']) in (0x189D,0x4C70),'saved BIOS frame differs')
        v.check(not r['flags']&0x200,'saved BIOS handler requires CLI');a.out(0x20,0x20,r['flags'])
        a.service_events.append(dict(number='chain',entry=entry,returned=dict(r)));return 0
    return chain

class Reference:
    def __init__(self,c,memory,r,device):
        self.access=a=Access(c,memory,r,device);self.frames=[];self.resume_poll=False;self.resume_boundary=False
        self.provider=Provider(c,memory,r,r['ds'],{},bytes(2048))
        def before(m,i):
            if i.address==0x4B1C and c.get('retry_stop'):m.stop(RETRY_BOUNDARY);return True
            if not m.hardware_frames:
                is_boundary=i.address in BOUNDARIES and (i.address not in (0x4401,0x4551) or m.steps==0 or m.previous and m.previous.mnemonic=='jmp')
                if is_boundary:
                    if not self.resume_boundary:m.stop(BOUNDARY);return True
                    self.resume_boundary=False
                if i.address in POLLS:
                    if not self.resume_poll:m.stop(CHECKPOINT);return True
                    if a.queue:
                        number,a.scan,site=a.queue.pop(0);a.deliveries.append((number,a.scan,site))
                        a.vectors.append((number,v.get16(a.memory,0,number*4+2),v.get16(a.memory,0,number*4)))
                        v.check(m.hardware_interrupt(number,returns={0x18B1,0x4C7D} if number==8 else {0x17B3}),'IRQ masked');return True
                    self.resume_poll=False
            a.quiet=any(f[2] for f in self.frames)
            if i.mnemonic=='ret' and self.frames and self.frames[-1][2]:a.quiet=False
            if i.mnemonic in ('call','lcall'):self.frames.append((i.address+i.size,i.mnemonic=='lcall',i.address in start.LEGACY_CALLS))
            return False
        def expected(m,off):
            v.check(bool(self.frames),'undeclared loop RET');ip,far,_=self.frames.pop();a.quiet=any(f[2] for f in self.frames)
            return {(c['load'],ip)} if far else {ip}
        def interrupt(m,number):
            q=m.state();p=self.provider;fn=q['ax']>>8
            if number==0x10 and q['ax']==0x90:
                q.update(menu.video_provider(a,{n:q[n] for n in menu.animation.FIELDS}));m.set_state(q);m.mask=v.FLAGS;m.flags=q['flags'];return
            if number==0x21 and fn in (0x3D,0x43,0x23,0x3F,0x3E):
                v.check(len(p.trace)<512,'DOS budget exhausted')
                if fn in (0x3D,0x43):q['ax'],count,q['flags']=p.file(fn,q['ds'],q['dx'],q['flags']);q['cx']=count if fn==0x43 else q['cx']
                elif fn==0x23:q['ax'],q['flags']=p.query(q['ds'],q['dx'],q['flags'])
                elif fn==0x3F:q['ax'],q['flags']=p.read(q['bx'],q['ds'],q['dx'],q['cx'],q['flags'])
                else:q['ax'],q['flags']=p.close(q['bx'],q['ax'],q['flags'])
                m.cpu.mem_write(0,bytes(memory));m.cpu.mem_write(v.SIZE,bytes(memory));m.set_state(q);m.mask=v.FLAGS
            else:m.software_interrupt(number,q['ip'],session.BINDINGS[number],provider(number))
        self.machine=v.OriginalMachine(c,memory,r,device,False,instructions=INS,access=a,outer_returns=(),
            child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},
            far_calls={0x1899:(0x189D,session.CHAIN,provider('chain')),0x4C6C:(0x4C70,session.CHAIN,provider('chain'))},
            mutable_operands=((0x4137,2),(0x5884,2)),before=before,interrupt=interrupt,max_steps=MAX_STEPS,
            unhooked_movsb={0x37B4})
    def advance(self):
        m=self.machine;m.stopped=False;m.status=0;out=m.run()
        out['services']=(self.access.service_events,self.provider.trace);return out

class Native:
    def __init__(self,directory,mutation=0):
        self.mutation=mutation
        self.lib=ct.CDLL(str(build(Path(directory)/f'loop-{mutation}.dll',mutation,'game_loop')))
        self.fn=self.lib.lmn_game_loop_core;self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(Services)];self.fn.restype=Result
        self.irq=self.lib.lmn_deliver_hardware_irq;self.irq.restype=session.IrqResult
        self.irq.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_uint16,ct.POINTER(session.IrqServices)]
    def run(self,c,memory,r,device):
        reference=Reference(c,bytearray(memory),dict(r),copy.deepcopy(device))
        memory,device=bytearray(memory),copy.deepcopy(device);a=Access(c,memory,r,device);cb=v.NativeCallbacks(a)
        p=Provider(c,memory,r,r['ds'],{},bytes(2048));errors=[];rows=[]
        callbacks={n:cb.interrupt(provider(n)) for n in (*session.BINDINGS,'chain')}
        bindings={n:v.InterruptService(None,callbacks[n],*(session.CHAIN if n=='chain' else session.BINDINGS[n])) for n in callbacks}
        ptr=lambda n:ct.pointer(bindings[n]);mem=(ct.c_uint8*v.SIZE).from_buffer(memory)
        irq=session.IrqServices(ptr(0x33),ptr(0x60),ptr(0x61),ptr('chain'),ct.pointer(cb.ports),ct.pointer(cb.bus),c['load'])
        def compare(state,kind):
            ref=reference.advance();status=ref['status'];ref['status']=0
            actual=dict(regs=state,status=0,memory=memory,device=device,events=a.events,
                services=(a.service_events,p.trace),providers=a.providers,cursor=a.cursor)
            try:v.compare_states(f'{c["name"]} {kind} {state["ip"]:04x}',actual,ref)
            except v.Mismatch as error:
                diffs=[(i,x,ref['memory'][i]) for i,x in enumerate(memory) if x!=ref['memory'][i]]
                print('RAM DIFF',len(diffs),diffs[:40],flush=True)
                print('REGS',state,ref['regs'],'steps',ref['steps'],'events',len(a.events),len(ref['events']),flush=True)
                raise error
            v.require(a.crtc==reference.access.crtc,'CRTC differs');v.require(a.deliveries==reference.access.deliveries,'IRQ schedule differs');v.require(a.vectors==reference.access.vectors,'live IRQ vector differs')
            if kind=='boundary' or state['ip'] in (0x4660,0x4683,0x04AA):
                print(f'CHECK {kind} {state["ip"]:04x} steps={ref["steps"]} events={len(a.events)}',flush=True)
            rows.append(dict(kind=kind,site=state['ip'],steps=ref['steps'],events=len(a.events),
                selection=memory[v.physical(state['ds'],0x1F6B)],success=memory[v.physical(state['ds'],0x1F6D)],
                ram_sha256=sha(memory)))
            if not self.mutation and (kind=='boundary' or state['ip'] in (0x4660,0x04AA)):
                write_json(BUILD/'game-loop-checkpoint.json',dict(accepted=False,case=c,rows=rows,
                    steps=ref['steps'],sites=sorted(reference.machine.sites),edges=sorted(reference.machine.edges),
                    display_reads=a.status_reads,legacy_ram_events=reference.access.omitted))
            a.reset_observations();reference.access.reset_observations();p.trace=[];reference.provider.trace=[]
            return status
        def poll(access,state,site):
            if errors:return 0xCA11
            try:
                v.require(compare(state,'poll')==CHECKPOINT,'original missed poll')
                script=a.script(state,site);v.require(script==reference.access.script(state,site),'script differs')
                reference.resume_poll=True
                if script is None:return 0xCA11
                for number,scan,where in script:
                    a.scan=scan;a.deliveries.append((number,scan,where))
                    a.vectors.append((number,v.get16(memory,0,number*4+2),v.get16(memory,0,number*4)))
                    out=self.irq(mem,ct.byref(v.Regs(**state)),number,ct.byref(irq))
                    state.update({n:getattr(out.registers,n) for n in v.REG_NAMES})
                    v.require(out.status==0,f'IRQ stop {out.status}/{out.handler_status}/{out.child_status}/{out.service_status} at {out.registers.cs:04x}:{out.registers.ip:04x}')
                return 0
            except v.Mismatch as error:errors.append(error);return 0xCA11
        @OBSERVE
        def observe(_,m,regs):
            if errors:return
            try:
                state={n:getattr(regs.contents,n) for n in v.REG_NAMES}
                print(f'BOUNDARY {c["name"]} {state["ip"]:04x}',flush=True)
                v.require(compare(state,'boundary')==BOUNDARY,'original missed boundary')
                a.boundary(state);reference.access.boundary(state);reference.resume_boundary=True
            except v.Mismatch as error:errors.append(error)
            except BaseException as error:v.callback_failure(error)
        handler=cb.foreground(poll);foreground=v.ForegroundPoll(None,handler)
        # Typed preserving DOS callbacks belong to the already accepted loader
        # ABI. They share canonical RAM; all other services use real INT/IRET.
        def guarded(fn,out,*args):
            try:
                v.check(len(p.trace)<512,'native DOS budget exhausted')
                for (name,_),value in zip(out.contents._fields_,fn(*args)):setattr(out.contents,name,value)
            except BaseException as error:v.callback_failure(error)
        opened=resources.FILE(lambda _,m,seg,off,f,out:guarded(p.file,out,0x3D,seg,off,f))
        attributes=resources.FILE(lambda _,m,seg,off,f,out:guarded(p.file,out,0x43,seg,off,f))
        query=resources.QUERY(lambda _,m,seg,off,f,out:guarded(p.query,out,seg,off,f))
        read=resources.READ(lambda _,m,h,seg,off,n,f,out:guarded(p.read,out,h,seg,off,n,f))
        retry=resources.RETRY_FN(lambda *args:v.callback_failure(v.OracleFailure('unexpected resource retry')))
        raw_open=resources.OPEN(lambda _,m,seg,off,f,out:guarded(lambda *args:(lambda t:(t[0],t[2]))(p.file(0x3D,*args)),out,seg,off,f))
        close=resources.OPEN(lambda _,m,h,value,f,out:guarded(p.close,out,h,value,f))
        files=resources.Services(None,opened,attributes,retry);io=resources.Io(None,query,read);raw=resources.RawServices(None,raw_open,read,close)
        selection=resources.SelectionServices(ct.pointer(files),ct.pointer(io),ct.pointer(raw));full=start.FullServices(ct.pointer(selection),None,None)
        segments=start.Segments(*(v.get16(memory,r['cs'],resources.SYMS[name]['address']+delta) for name,delta in
            (('CheckDatFile',0x33),('SelectCachedDatFile',0x50),('ReadDatBytes',8),('DatReadFailure',1))))
        @menu.VIDEO
        def mode(_,binding,incoming,outgoing):
            try:
                state=menu.video_provider(a,{n:getattr(incoming.contents,n) for n in menu.animation.FIELDS})
                for n,value in state.items():setattr(outgoing.contents,n,value)
            except BaseException as error:v.callback_failure(error)
        video=menu.VideoServices(None,mode,menu.VIDEO())
        probe_video=session.frame.initialize.VideoServices(ptr(0x10),ct.pointer(cb.ports),ct.pointer(cb.bus))
        brief=start.briefing.Services(None,ct.pointer(cb.ports),ct.pointer(cb.bus))
        loader=start.Services(ct.pointer(segments),ct.pointer(full),ct.pointer(brief),ct.pointer(cb.bus),r['ds'])
        level=session.frame.initialize.LevelServices(None,None,ct.pointer(cb.bus),ct.pointer(cb.ports))
        init=session.frame.initialize.GameServices(ct.pointer(probe_video),ct.pointer(cb.ports),ct.pointer(cb.bus),ct.pointer(level),
            r['ds'],0,ptr(0x33),ptr(0x21),ct.cast(ct.pointer(foreground),ct.c_void_p))
        frames=session.frame.Services(ct.pointer(cb.ports),ct.pointer(cb.bus),ptr(0x60),ptr(0x61),ptr(0x21),ptr(0x1A),None,None,ct.pointer(foreground),r['ds'])
        game=session.Services(ct.pointer(init),ct.pointer(frames),None,OBSERVE())
        screen=result.Services(ct.pointer(cb.ports),ct.pointer(cb.bus),ct.pointer(video),ct.pointer(foreground),r['ds'])
        services=Services(ct.pointer(video),ptr(0x21),ct.pointer(cb.ports),ct.pointer(cb.bus),ct.pointer(foreground),
            ct.pointer(loader),ct.pointer(game),ct.pointer(screen),None,observe,r['ds'],r['cs'])
        out=self.fn(mem,ct.byref(v.Regs(**r)),ct.byref(services))
        if errors:
            if not self.mutation:
                m=reference.machine
                write_json(BUILD/'game-loop-failure.json',dict(accepted=False,case=c,error=str(errors[0]),rows=rows,
                    sites=sorted(m.sites),edges=sorted(m.edges),steps=m.steps,deliveries=a.deliveries,
                    omitted_ram_events=reference.access.omitted))
            raise errors[0]
        if c.get('retry_stop'):
            state={n:getattr(out.registers,n) for n in v.REG_NAMES}
            v.require(out.status==2 and state['ip']==0x4B1C,'retry entry was not retained')
            v.require(compare(state,'retry')==RETRY_BOUNDARY,'original missed retry entry')
            return dict(rows=rows,steps=reference.machine.steps,sites=sorted(reference.machine.sites),edges=sorted(reference.machine.edges))
        if c.get('stop_poll'):return dict(rows=rows)
        v.require(out.status==0 and out.registers.ip==0x4453 and out.child_status==0xCA11,'final poll stop differs')
        v.check(a.sessions==3 and a.results==3 and a.typed==11,'journey incomplete')
        v.check([(ip,sel,success) for ip,sel,success in a.screens if ip in (0x454C,0x4551)]==
            [(0x454C,0,0),(0x4551,1,255),(0x4551,1,0)],'next/retry/outcome ownership differs')
        m=reference.machine
        return dict(rows=rows,screens=a.screens,sites=sorted(m.sites),edges=sorted(m.edges),steps=m.steps,
            polls=len(a.polls),deliveries=a.deliveries,vectors=a.vectors,display_reads=a.status_reads,
            omitted_ram_events=reference.access.omitted)

def poll_stop_helpers(native):
    """Stop before the new read, including the adapters' pending RET words."""
    rows=[]
    for stem,site,ports in (('read_keyboard_character',0x4D23,False),('choose_input_controller',0x43CE,True)):
        for suffix in ('core','adapter'):
            c,memory,r,device=setup();r['ip']=0x4D1A if not ports else site
            access=Access(c,memory,r,device);cb=v.NativeCallbacks(access)
            ref_memory=bytearray(memory);ref_device=copy.deepcopy(device)
            ref_access=Access(c,ref_memory,dict(r),ref_device)
            def before(m,i):
                if i.address==site:m.stop(0);return True
                return False
            ref=v.OriginalMachine(c,ref_memory,dict(r),ref_device,False,instructions=INS,access=ref_access,
                outer_returns=(),before=before,max_steps=8).run()
            handler=cb.foreground(lambda a,q,p:0x4321);poll=v.ForegroundPoll(None,handler)
            fn=getattr(native.lib,'lmn_'+stem+'_'+suffix+'_polled');fn.restype=session.keyboard.Result
            fn.argtypes=[v.MEM,ct.POINTER(v.Regs),*([ct.POINTER(v.Ports)] if ports else []),ct.POINTER(v.Bus),ct.POINTER(v.ForegroundPoll)]
            args=[(ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r))]
            if ports:args.append(ct.byref(cb.ports))
            out=fn(*args,ct.byref(cb.bus),ct.byref(poll))
            v.check((out.status,out.service_status)==(8,0x4321),'new keyboard poll status lost')
            v.compare_states(stem+' '+suffix,dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=0,
                memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor),ref)
            rows.append(dict(entry=r['ip'],stop=site,adapter=suffix=='adapter',steps=ref['steps']))
    # Dispatch-only unsupported/unbound exits have no instruction or bus effect.
    services=Services();services.code_segment=0x1010
    for ip,status in ((0x04D0,1),(0x4B1C,2),(0x04F7,3),(0x04F9,3),(0xFFFF,4),(0xFB,5)):
        c,memory,r,device=setup();r['ip']=ip;original=bytes(memory)
        out=native.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),ct.byref(services))
        v.check(out.status==status and {n:getattr(out.registers,n) for n in v.REG_NAMES}==r and memory==original,
                'explicit dispatch stop changed live state')
        rows.append(dict(entry=ip,status=status))
    for ip in BOUNDARIES:
        c,memory,r,device=setup();r['ip']=ip;original=bytes(memory)
        out=native.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),ct.byref(services))
        v.check(out.status==5 and {n:getattr(out.registers,n) for n in v.REG_NAMES}==r and memory==original,
                'unbound foreground poll entered a core')
        rows.append(dict(entry=ip,unbound_poll=True,status=out.status))
    return rows

def input_hashes():
    paths=set(source_files('game_loop'))|{p for p in (ROOT/'c').glob('*.h') if p.name!='resource_retry.h'}
    paths|={Path(m.__file__).resolve() for m in tuple(sys.modules.values()) if getattr(m,'__file__',None)
        and Path(m.__file__).suffix=='.py' and Path(m.__file__).resolve().parent in (ROOT/'tests',ROOT/'tools')}
    paths.update(ROOT/p for p in ('metadata/symbols.json','metadata/oracle.json','assets/vgalemmi.exe','assets/main.dat'))
    # Exact normal selections traversed by this script; include their static
    # resource files before any compilation/execution so preservation is audited.
    for selector in (0,1):
        case=next(c for c in resources.cases() if c['name']=='real-selection-'+str(selector))
        paths.update(ROOT/p for p in resources.prepare(case)[-1])
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}

def worker(directory):
    began=time.perf_counter();reports=[];mutants=[];before=input_hashes()
    native=Native(directory)
    helpers=poll_stop_helpers(native)
    c,m,r,d=setup(0x454C);c['retry_stop']=True;reports.append(native.run(c,m,r,d))
    c,m,r,d=setup()
    reports.append(native.run(c,m,r,d))
    write_json(BUILD/'game-loop-progress.json',dict(accepted=False,cases=reports,input_hashes=before))
    c,m,r,d=setup(0x4401);c['stop_poll']=0x4453;reports.append(native.run(c,m,r,d))
    for mutation in (1,2,3,4):
        mutant=Native(directory,mutation)
        c,m,r,d=setup()
        try:mutant.run(c,m,r,d)
        except v.Mismatch as error:mutants.append(dict(id=mutation,witness=str(error)))
        else:raise AssertionError(f'surviving loop mutant{mutation}')
        del mutant;gc.collect()
    del native;gc.collect()
    v.check(before==input_hashes(),'loop inputs changed during campaign')
    v.check({p.relative_to(ROOT).as_posix() for p in ASSETS}<=set(before),'unhashed fixture asset')
    write_json(REPORT,dict(scope='continuous-game-loop-irq-at-poll',fixture='real-level',own_ranges=[],cases=reports,helpers=helpers,mutants=mutants,
        seconds=time.perf_counter()-began,input_hashes=before,
        limits=dict(outer_seconds=3600,worker_seconds=3540,memory_mib=768,instructions=MAX_STEPS,
            events=MAX_EVENTS,polls=2500,display_reads=500_000)))
    print(f'PASS game_loop: continuous journey + refresh entry, {len(mutants)} completed mutants, {time.perf_counter()-began:.2f}s',flush=True)
def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='game-loop-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',directory],cwd=ROOT,timeout=3540,memory_mib=768,check=True)
if __name__=='__main__':main()
