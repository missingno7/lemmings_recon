"""ShowResourceRetryScreen input prefix on the shared bounded engine."""
import copy
import ctypes as ct
import gc
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import display_setup as setup_oracle
import level_result as result_suite
import main_menu as menus
import game_loop as loop_suite
from bounded_process import temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

START, BUTTON, SCAN, END = 0x4B3B,0x4B40,0x4B48,0x4B50
OWN={i.address:i for i in v.MD.disasm(v.IMAGE[START:END+3],START)}
PARENT={i.address:i for i in v.MD.disasm(v.IMAGE[0x4B1C:0x4B5C],0x4B1C)}|setup_oracle.INS
FULL_INS=PARENT|result_suite.INS
class Result(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in ('value','flags','continuation','status','service_status')]
class VideoState(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in ('value','base_value','count','argument','source_cursor','output_cursor','frame_cursor','data_segment','extra_segment','stack_segment','stack_offset','flags')]
class ScreenResult(ct.Structure):
    _fields_=[('state',VideoState),('code_segment',ct.c_uint16),('continuation',ct.c_uint16),
        ('status',ct.c_uint32),('child_entry',ct.c_uint16),('child_status',ct.c_uint16)]
class Access(v.BusAccess):
    def __init__(self,c,m,r,d):
        super().__init__(c,m,r,d,max_events=2048)
        self.polls=[];self.counts={}
    def poll(self,r,site):
        n=self.counts.get(site,0)+1;self.counts[site]=n
        self.polls.append((site,n,r['flags']))
        if self.c.get('stop')==site:return 0xCA11
        if self.c.get('null'):return 0
        buttons=None;scan=None
        if site==BUTTON:
            if self.c['kind']=='button':buttons=self.c['value']
            elif self.c['kind']=='upper':buttons=self.c['value'] if n==1 else 0
            elif self.c['kind']=='delayed' and n==2:buttons=4
            else:buttons=0
        elif site==SCAN:
            if self.c['kind']=='scan':scan=self.c['value']
            elif self.c['kind'] in ('button','upper'):scan=0x40
            else:scan=0
        if buttons is not None:self.patch(r['ds'],0x14,buttons,'poll-button')
        if scan is not None:self.patch(r['ds'],0x1FD0,scan,'poll-scan',word=False)
        return 0

class RetryScreenAccess(result_suite.Access):
    def __init__(self,c,m,r,d):
        super().__init__(c,m,r,d);self.retry_polls=[];self.retry_counts={}
    def poll(self,r,site):
        n=self.retry_counts.get(site,0)+1;self.retry_counts[site]=n
        v.check(sum(self.retry_counts.values())<=16,'retry screen poll budget exhausted')
        self.retry_polls.append((site,n,r['flags']))
        if site==BUTTON:
            value=1 if self.c['input']=='button' else 0
            self.patch(r['ds'],0x14,value,f'retry-button-{n}')
        elif site==SCAN:
            value=0x41 if self.c['input']=='scan' else 0
            self.patch(r['ds'],0x1FD0,value,f'retry-scan-{n}',word=False)
        else:raise AssertionError(f'unexpected retry poll site {site:04X}')
        return 0

class Machine(v.OriginalMachine):
    def __init__(self,c,m,r,d):
        access=Access(c,m,r,d)
        def before(machine,ins):
            if ins.address in (BUTTON,SCAN):
                if c.get('null') and ins.address==BUTTON:machine.stop(3);return True
                status=access.poll(machine.state(),ins.address)
                if status:machine.service_status=status;machine.stop(4);return True
            if ins.address==END:machine.stop(0);return True
            return False
        super().__init__(c,m,r,d,False,instructions=OWN,access=access,
            outer_returns=(),before=before,max_steps=1000)
        self.paccess=access
    def run(self):
        out=super().run();out['polls']=self.paccess.polls;out['service_status']=self.service_status;return out

def cases():
    out=[dict(name='button-low',kind='button',value=1),
         dict(name='button-third-bit',kind='button',value=4),
         dict(name='button-upper-retained',kind='upper',value=0x8000),
         dict(name='scan-nonzero',kind='scan',value=0x80),
         dict(name='delayed-button',kind='delayed'),
         dict(name='null-wait',kind='button',value=0,null=True),
         dict(name='stop-button',kind='button',value=1,stop=BUTTON),
         dict(name='stop-scan',kind='scan',value=0x20,stop=SCAN)]
    for load in v.LOADS:out.append(dict(name=f'load-{load:04x}',kind='scan',value=0x31,load=load))
    return [dict(c,seed=0x4b3b+i,load=c.get('load',v.LOADS[0])) for i,c in enumerate(out)]

def setup(c):
    rng=random.Random(c['seed']);m=bytearray(rng.randbytes(v.SIZE));v.code_image(m,c['load'])
    d=v.new_device(c['seed']);r=v.default_regs(c['load'],c['seed'],ds=0x4000,ss=0x7000,sp=0x8000)
    r['ip']=START
    v.put16(m,r['ds'],0x14,0xA500,d);v.put8(m,r['ds'],0x1FD0,0x77)
    return m,r,d

class Native:
    def __init__(self,output,mutation):
        self.lib=ct.CDLL(str(build(Path(output)/f'resource-retry-{mutation}.dll',mutation,
            'resource_retry' if mutation else 'game_loop')))
        self.fn=self.lib.lmn_resource_retry_input_core;self.fn.restype=Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(v.Bus),ct.POINTER(v.ForegroundPoll)]
        self.screen=self.lib.lmn_resource_retry_screen_core;self.screen.restype=ScreenResult
        self.screen.argtypes=[v.MEM,ct.c_uint16,ct.c_uint16,ct.POINTER(VideoState),ct.c_void_p,
            ct.POINTER(v.Bus),ct.POINTER(v.Ports),ct.POINTER(v.ForegroundPoll)]
        self.screen_adapter=self.lib.lmn_resource_retry_screen_adapter;self.screen_adapter.restype=None
        self.screen_adapter.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_uint16,ct.c_void_p,
            ct.POINTER(v.Bus),ct.POINTER(v.Ports),ct.POINTER(v.ForegroundPoll)]
        if not mutation:
            self.loop=self.lib.lmn_game_loop_core;self.loop.restype=loop_suite.Result
            self.loop.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(loop_suite.Services)]
    def close(self):
        self.fn=None;self.screen=None;self.screen_adapter=None;self.loop=None
        if self.lib is not None:
            ct.windll.kernel32.FreeLibrary(ct.c_void_p(self.lib._handle))
            self.lib._handle=0
        self.lib=None
    def run(self,c,m,r,d,mutation=0):
        mem=bytearray(m);regs=v.Regs(**r);access=Access(c,mem,r,copy.deepcopy(d));callbacks=v.NativeCallbacks(access)
        @v.FOREGROUND
        def poll(_,memory,live,site):
            try:
                state={n:getattr(live.contents,n) for n in v.REG_NAMES}
                status=access.poll(state,site)
                for n,x in state.items():setattr(live.contents,n,x)
                return status
            except BaseException as e:v.callback_failure(e)
        p=v.ForegroundPoll(None,ct.cast(poll,v.FOREGROUND))
        result=self.fn((ct.c_uint8*v.SIZE).from_buffer(mem),ct.byref(regs),ct.byref(callbacks.bus),
            None if c.get('null') else ct.byref(p))
        return dict(result=result,regs={n:getattr(regs,n) for n in v.REG_NAMES},memory=mem,
            device=access.device,events=access.events,polls=access.polls,providers=access.providers,
            service_status=result.service_status)
    def run_screen(self,c,m,r,d,*,core=False):
        memory,device=bytearray(m),copy.deepcopy(d);regs=v.Regs(**r)
        access=RetryScreenAccess(c,memory,dict(r),device);callbacks=v.NativeCallbacks(access)
        mem=(ct.c_uint8*v.SIZE).from_buffer(memory)
        @menus.VIDEO
        def mode(_,binding,incoming,outgoing):
            try:
                v.check(ct.addressof(binding.contents)==ct.addressof(mem),'retry BIOS RAM binding differs')
                state=menus.video_provider(access,{n:getattr(incoming.contents,n) for n in menus.animation.FIELDS})
                for name,value in state.items():setattr(outgoing.contents,name,value)
            except BaseException as error:v.callback_failure(error)
        video=menus.VideoServices(None,mode,menus.VIDEO())
        poll_callback=callbacks.foreground(lambda a,live,site:a.poll(live,site))
        poll=v.ForegroundPoll(None,poll_callback)
        result=None
        if core:
            state=VideoState(*[getattr(regs,n) for n in ('ax','bx','cx','dx','si','di','bp','ds','es','ss','sp','flags')])
            result=self.screen(mem,regs.cs,(c['load']+0x9A9)&65535,ct.byref(state),ct.byref(video),
                ct.byref(callbacks.bus),ct.byref(callbacks.ports),ct.byref(poll))
            state=result.state
            regs.ax=state.value;regs.bx=state.base_value;regs.cx=state.count;regs.dx=state.argument
            regs.si=state.source_cursor;regs.di=state.output_cursor;regs.bp=state.frame_cursor
            regs.ds=state.data_segment;regs.es=state.extra_segment;regs.ss=state.stack_segment
            regs.sp=state.stack_offset;regs.flags=state.flags;regs.cs=result.code_segment;regs.ip=result.continuation
        else:
            self.screen_adapter(mem,ct.byref(regs),(c['load']+0x9A9)&65535,ct.byref(video),
                ct.byref(callbacks.bus),ct.byref(callbacks.ports),ct.byref(poll))
        return dict(result=result,regs={n:getattr(regs,n) for n in v.REG_NAMES},memory=memory,device=access.device,
            events=access.events,providers=access.providers,cursor=access.cursor,
            services=access.service_events,polls=access.retry_polls)

class FullMachine(v.OriginalMachine):
    def __init__(self,c,m,r,d):
        frames=[];failed=[];access=RetryScreenAccess(c,m,r,d)
        def before(machine,ins):
            if ins.address in (BUTTON,SCAN):
                status=access.poll(machine.state(),ins.address)
                if status:machine.service_status=status;machine.stop(4);return True
            if ins.mnemonic in ('call','lcall'):
                target=ins.operands[-1].imm if ins.operands and ins.operands[-1].type==v.capstone.x86_const.X86_OP_IMM else None
                frames.append(dict(owner=ins.address,resume=ins.address+ins.size,
                    far=ins.mnemonic=='lcall',target=target))
            return False
        def expected(machine,off):
            v.check(bool(frames),'undeclared retry child RET')
            frame=frames.pop();failed[:]=[frame]
            return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
        def changed(machine,off):
            v.check(bool(failed),'retry changed-return lacks a live CALL')
            return 6
        def interrupt(machine,number):
            v.check(number==0x10,'unexpected retry-screen interrupt')
            live=machine.state()
            out=menus.video_provider(access,{n:live[n] for n in menus.animation.FIELDS})
            live.update(out);machine.set_state(live);machine.mask=v.FLAGS;machine.flags=live['flags']
        super().__init__(c,m,r,d,False,instructions=FULL_INS,access=access,
            outer_returns={0x4B5B},child_returns={p:expected for p,i in FULL_INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in FULL_INS.items() if i.mnemonic=='retf'},
            before=before,interrupt=interrupt,changed_return_status=changed,max_steps=4_000_000)
        self.retry_access=access
    def run(self):
        out=super().run();out['polls']=self.retry_access.retry_polls
        out['services']=self.retry_access.service_events;return out

def prepare_screen(c):
    memory,r,device=result_suite.setup(c);r['ip']=0x4B1C
    return memory,r,device

def run_full_screen(native,c):
    memory,r,device=prepare_screen(c)
    ref=FullMachine(c,bytearray(memory),dict(r),copy.deepcopy(device)).run()
    actual=native.run_screen(c,memory,r,device,core=c.get('changed',False))
    out=dict(regs=actual['regs'],memory=actual['memory'],device=actual['device'],events=actual['events'],
        providers=actual['providers'],cursor=actual['cursor'],services=actual['services'],
        status=ref['status'],mask=ref['mask'])
    v.compare_states(c['name'],out,ref)
    v.require(actual['polls']==ref['polls'],c['name']+': full-screen poll schedule differs')
    if c.get('changed'):
        v.require(actual['result'].status==2 and actual['result'].child_entry==0x4BE7 and
            actual['result'].continuation==0xD234,'changed setup return diagnostic differs')
    else:
        v.require(actual['regs']['ip']==0xD00D and actual['regs']['sp']==(r['sp']+2)&0xFFFF,
            'full screen did not consume the actual outer RET')
    return dict(name=c['name'],sites=sorted(ref['sites']),edges=sorted(ref['edges']),
        polls=ref['polls'],services=ref['services'],status=ref['status'],final_ip=ref['regs']['ip'])

def full_screen_cases():
    common=dict(entry=0x4B1C,load=v.LOADS[0],flags=0x0AD7,input_mode=0,
        completion=80,required=50,selection=37,time_zero=False,initial_buttons=0,initial_keys=0)
    return [dict(common,name='full-button-exit',seed=0x5B01,input='button'),
        dict(common,name='full-scan-exit',seed=0x5B02,input='scan'),
        dict(common,name='full-changed-setup-return',seed=0x5B03,input='button',
            return_patch=0x4B1F,changed=True)]

def run_case(native,c,mutation=0):
    m,r,d=setup(c);ref=Machine(c,bytearray(m),dict(r),copy.deepcopy(d)).run()
    got=native.run(c,m,r,d,mutation);x=got['result']
    if x.status!=ref['status']:raise AssertionError(f"{c['name']}: status {x.status} != {ref['status']}")
    if x.continuation!=ref['regs']['ip']:raise AssertionError(f"{c['name']}: continuation differs")
    gr=dict(got['regs']);gr.update(ax=x.value,flags=x.flags,cs=c['load'],ip=x.continuation)
    v.compare_states(c['name'],dict(regs=gr,memory=got['memory'],device=got['device'],events=got['events'],
        providers=got['providers'],cursor=0,service_status=x.service_status,mask=ref['mask']),
        dict(regs=ref['regs'],memory=ref['memory'],device=ref['device'],events=ref['events'],
        providers=ref['providers'],cursor=ref['cursor'],service_status=ref['service_status'],mask=ref['mask']))
    v.require(got['polls']==ref['polls'],c['name']+': poll schedule differs')
    return ref

def run_parent_prefix(native):
    c=dict(name='parent-missing-bios',seed=0x4b1c,load=v.LOADS[0])
    m,r,d=setup(c);r['ip']=0x4B1C
    def before(machine,ins):
        if ins.address==0x4BF2:machine.stop(5);return True
        return False
    original_memory=bytearray(m);access=Access(c,original_memory,r,copy.deepcopy(d))
    ref=v.OriginalMachine(c,original_memory,dict(r),access.device,False,
        instructions=PARENT,access=access,outer_returns=(),before=before,max_steps=1000).run()
    mem=bytearray(m);state=VideoState(*[r[k] for k in ('ax','bx','cx','dx','si','di','bp','ds','es','ss','sp','flags')])
    native_access=Access(c,mem,r,copy.deepcopy(d));callbacks=v.NativeCallbacks(native_access)
    result=native.screen((ct.c_uint8*v.SIZE).from_buffer(mem),r['cs'],0x19A9,ct.byref(state),None,
        ct.byref(callbacks.bus),None,None)
    out=dict(regs=dict(zip(('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip','flags'),
        [result.state.value,result.state.base_value,result.state.count,result.state.argument,
         result.state.source_cursor,result.state.output_cursor,result.state.frame_cursor,result.state.stack_offset,
         result.code_segment,result.state.data_segment,result.state.extra_segment,result.state.stack_segment,
        result.continuation,result.state.flags])),memory=mem,device=native_access.device,events=native_access.events,
        providers=native_access.providers,cursor=native_access.cursor,
        status=result.status,child_status=result.child_status,service_status=0,mask=v.FLAGS)
    want=dict(regs=ref['regs'],memory=ref['memory'],device=ref['device'],events=ref['events'],providers=ref['providers'],
        cursor=ref['cursor'],status=1,child_status=1,service_status=0,mask=ref['mask'])
    v.compare_states('parent-missing-bios',out,want)
    v.require((result.child_entry,result.continuation)==(0x4BE7,0x4BF2),'parent child stop boundary differs')

class RoutedAccess(RetryScreenAccess):
    """The inherited DAT children use their typed RAM ABI; the UI uses the bus."""
    def __init__(self,*args):
        super().__init__(*args);self.quiet=False;self.omitted=0
    def emit(self,kind,address,value,flags,mask=v.FLAGS):
        if self.quiet and kind in ('read','write'):
            v.check(not v.VGA_BASE<=address<v.VGA_END,'typed DAT child reached VGA')
            self.omitted+=1;v.check(self.omitted<=2_000_000,'routed DAT access budget exhausted');return
        super().emit(kind,address,value,flags,mask)
    def poll(self,r,site):
        v.check(len(self.retry_polls)<16,'routed retry poll budget exhausted')
        if self.c.get('stop')==site:
            self.retry_polls.append((site,1,r['flags']));return 0xCA11
        status=super().poll(r,site)
        if self.c.get('changed_return') and 'retry-return' not in self.providers:
            self.patch(r['ss'],r['sp'],0xD234,'retry-return')
        return status

class RoutedProvider(loop_suite.start.Provider):
    def file(self,function,seg,off,flags):
        result=super().file(function,seg,off,flags)
        if function==0x3D and self.case.get('open_critical') and not getattr(self,'failed_open',False):
            self.failed_open=True
            v.put8(self.mem,seg,loop_suite.resources.field('DatCriticalErrorFlag'),1)
        return result

def routed_cases():
    base=next(c for c in loop_suite.start.cases() if c['name']=='resources-order-1')
    rows=[dict(name='route-attribute-button',input='button'),
          dict(name='route-attribute-scan',input='scan',load=v.LOADS[1]),
          dict(name='route-open-critical-button',input='button',attribute_errors=0,open_critical=True),
          dict(name='route-repeat-attribute',input='scan',attribute_errors=2),
          dict(name='route-stop-button',input='button',stop=BUTTON),
          dict(name='route-stop-scan',input='scan',stop=SCAN),
          dict(name='route-changed-return',input='button',changed_return=True),
          dict(name='route-unbound-video',input='button',unbound_video=True)]
    return [dict(base,flags=0x202,attribute_errors=1)|row for row in rows]

def run_routed(native,c):
    start=loop_suite.start;resources=loop_suite.resources
    memory,r,device,payloads,record=start.setup(c)
    v.put8(memory,r['ds'],resources.field('DatRetryEnabled'),255)
    instructions=start.INS|FULL_INS
    ref_memory=bytearray(memory);ref_device=copy.deepcopy(device)
    access=RoutedAccess(c,ref_memory,dict(r),ref_device)
    provider=RoutedProvider(c,ref_memory,dict(r),r['ds'],payloads,record)
    frames=[];retry_entries=[]
    def before(machine,ins):
        if ins.address==0x4566:machine.stop(5);return True
        if ins.address==0x4B1C:
            retry_entries.append(machine.state())
            if c.get('unbound_video'):machine.stop(5);return True
        if ins.address in (BUTTON,SCAN):
            if access.poll(machine.state(),ins.address):machine.stop(0);return True
        access.quiet=any(f['legacy'] for f in frames) and not any(f['retry'] for f in frames)
        if ins.mnemonic=='ret' and frames and frames[-1]['legacy']:access.quiet=False
        if ins.mnemonic in ('call','lcall'):
            frames.append(dict(resume=ins.address+ins.size,far=ins.mnemonic=='lcall',
                legacy=ins.address in start.LEGACY_CALLS,retry=ins.address in (0x1D17,0x1B9E)))
        return False
    def expected(machine,off):
        v.check(bool(frames),'undeclared routed RET');frame=frames.pop()
        access.quiet=any(f['legacy'] for f in frames) and not any(f['retry'] for f in frames)
        return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
    def interrupt(machine,number):
        live=machine.state();fn=live['ax']>>8
        if number==0x10:
            live.update(menus.video_provider(access,{n:live[n] for n in menus.animation.FIELDS}))
        else:
            v.check(number==0x21 and len(provider.trace)<512,'routed DOS service budget exhausted')
            if fn in (0x3D,0x43):
                live['ax'],count,live['flags']=provider.file(fn,live['ds'],live['dx'],live['flags'])
                if fn==0x43:live['cx']=count
            elif fn==0x23:live['ax'],live['flags']=provider.query(live['ds'],live['dx'],live['flags'])
            elif fn==0x3F:live['ax'],live['flags']=provider.read(live['bx'],live['ds'],live['dx'],live['cx'],live['flags'])
            elif fn==0x3E:live['ax'],live['flags']=provider.close(live['bx'],live['ax'],live['flags'])
            else:raise v.OracleFailure('undeclared routed DOS function')
        machine.cpu.mem_write(0,bytes(ref_memory));machine.cpu.mem_write(v.SIZE,bytes(ref_memory))
        machine.set_state(live);machine.mask=v.FLAGS;machine.flags=live['flags']
    machine=v.OriginalMachine(c,ref_memory,dict(r),ref_device,False,instructions=instructions,
        access=access,outer_returns=(),before=before,interrupt=interrupt,
        child_returns={p:expected for p,i in instructions.items() if i.mnemonic=='ret'},
        far_returns={p:expected for p,i in instructions.items() if i.mnemonic=='retf'},
        changed_return_status=4,max_steps=4_000_000)
    ref=machine.run();ref['services']=(access.service_events,provider.trace)
    got_memory=bytearray(memory);got_access=RoutedAccess(c,got_memory,dict(r),copy.deepcopy(device))
    callbacks=v.NativeCallbacks(got_access);mem=(ct.c_uint8*v.SIZE).from_buffer(got_memory)
    p=RoutedProvider(c,got_memory,dict(r),r['ds'],payloads,record)
    def guarded(fn,out,binding,*args):
        try:
            v.check(ct.addressof(binding.contents)==ct.addressof(mem),'routed provider RAM differs')
            v.check(len(p.trace)<512,'native routed DOS budget exhausted')
            for (name,_),value in zip(out.contents._fields_,fn(*args)):setattr(out.contents,name,value)
        except BaseException as error:v.callback_failure(error)
    opened=resources.FILE(lambda _,m,seg,off,f,out:guarded(p.file,out,m,0x3D,seg,off,f))
    attributes=resources.FILE(lambda _,m,seg,off,f,out:guarded(p.file,out,m,0x43,seg,off,f))
    query=resources.QUERY(lambda _,m,seg,off,f,out:guarded(p.query,out,m,seg,off,f))
    read=resources.READ(lambda _,m,h,seg,off,n,f,out:guarded(p.read,out,m,h,seg,off,n,f))
    retry=resources.RETRY_FN(lambda *args:v.callback_failure(v.OracleFailure('legacy retry service called')))
    raw_open=resources.OPEN(lambda _,m,seg,off,f,out:guarded(
        lambda *args:(lambda t:(t[0],t[2]))(p.file(0x3D,*args)),out,m,seg,off,f))
    close=resources.OPEN(lambda _,m,h,value,f,out:guarded(p.close,out,m,h,value,f))
    files=resources.Services(None,opened,attributes,retry);io=resources.Io(None,query,read)
    raw=resources.RawServices(None,raw_open,read,close)
    selection=resources.SelectionServices(ct.pointer(files),ct.pointer(io),ct.pointer(raw))
    full=start.FullServices(ct.pointer(selection),None,None)
    segments=start.Segments(*(v.get16(memory,r['cs'],resources.SYMS[name]['address']+delta) for name,delta in
        (('CheckDatFile',0x33),('SelectCachedDatFile',0x50),('ReadDatBytes',8),('DatReadFailure',1))))
    loader=start.Services(ct.pointer(segments),ct.pointer(full),None,ct.pointer(callbacks.bus),r['ds'])
    @menus.VIDEO
    def mode(_,binding,incoming,outgoing):
        try:
            v.check(ct.addressof(binding.contents)==ct.addressof(mem),'routed video RAM differs')
            state=menus.video_provider(got_access,{n:getattr(incoming.contents,n) for n in menus.animation.FIELDS})
            for name,value in state.items():setattr(outgoing.contents,name,value)
        except BaseException as error:v.callback_failure(error)
    video=menus.VideoServices(None,mode,menus.VIDEO())
    handler=callbacks.foreground(lambda a,live,site:a.poll(live,site));poll=v.ForegroundPoll(None,handler)
    services=loop_suite.Services(None if c.get('unbound_video') else ct.pointer(video),None,
        ct.pointer(callbacks.ports),ct.pointer(callbacks.bus),ct.pointer(poll),ct.pointer(loader),
        None,None,None,loop_suite.OBSERVE(),r['ds'],r['cs'])
    result=native.loop(mem,ct.byref(v.Regs(**r)),ct.byref(services))
    actual=dict(regs={n:getattr(result.registers,n) for n in v.REG_NAMES},status=result.status,
        memory=got_memory,device=got_access.device,events=got_access.events,providers=got_access.providers,
        cursor=got_access.cursor,services=(got_access.service_events,p.trace))
    v.compare_states(c['name'],actual,ref)
    v.require(got_access.retry_polls==access.retry_polls,c['name']+': routed poll schedule differs')
    v.require(bool(retry_entries),c['name']+': retry path unused')
    if c.get('stop'):
        v.require((result.core_status,result.service_status,result.registers.ip)==(4,0xCA11,c['stop']),
            'routed poll stop lost its diagnostics')
    elif c.get('changed_return'):
        v.require(result.registers.ip==0xD234 and result.core_status==2,'changed RET target/diagnostic was hidden')
    elif not c.get('unbound_video'):
        expected_return=0x1BA1 if c.get('open_critical') else 0x1D1A
        v.require(expected_return in ref['sites'],'DAT caller did not execute its retry tail')
        v.require(len(retry_entries)==max(1,c['attribute_errors']),'wrong retry count')
        v.require(p.attributes>=2 and result.registers.ip==0x4566,'probe did not recover to briefing')
        v.require(bytes(got_memory[v.physical(r['ds'],0xFCB+i)] for i in range(2048))==record,
            'recovered resource data differs')
        v.require(got_memory[v.physical(r['ds'],resources.field('DatCriticalErrorFlag'))]==0,
            'retry UI did not clear the critical-error latch')
    return dict(name=c['name'],status=result.status,final_ip=result.registers.ip,steps=ref['steps'],
        sites=sorted(ref['sites']),edges=sorted(ref['edges']),retry_entries=retry_entries,
        polls=access.retry_polls,services=ref['services'],legacy_ram_events=access.omitted)

def input_hashes():
    paths=set(source_files('game_loop'))|{p for p in (ROOT/'c').glob('*.h') if p.name!='pklite_unpack.h'}
    paths|={Path(m.__file__).resolve() for m in tuple(sys.modules.values()) if getattr(m,'__file__',None)
        and Path(m.__file__).suffix=='.py' and Path(m.__file__).resolve().parent in (ROOT/'tests',ROOT/'tools')}
    paths.update(ROOT/p for p in ('metadata/symbols.json','metadata/oracle.json','assets/vgalemmi.exe','assets/main.dat'))
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}

def main():
    summaries=[];screen_summaries=[];routed_summaries=[];before=input_hashes()
    with temporary_build_directory(prefix='resource-retry-',parent=BUILD) as directory:
        loaded=[]
        try:
            native=Native(directory,0);loaded.append(native)
            for c in cases():
                print('CASE '+c['name'],flush=True)
                ref=run_case(native,c);summaries.append(dict(name=c['name'],sites=sorted(ref['sites']),edges=sorted(ref['edges']),polls=len(ref['polls'])))
            run_parent_prefix(native)
            for c in full_screen_cases():
                print('FULL '+c['name'],flush=True)
                screen_summaries.append(run_full_screen(native,c))
            for c in routed_cases():
                print('ROUTED '+c['name'],flush=True)
                routed_summaries.append(run_routed(native,c))
            native.close();loaded.remove(native);del native;gc.collect()
            witnesses={10:'button-third-bit',11:'button-upper-retained',12:'button-low'}
            mutants=[]
            for mutation,name in witnesses.items():
                print(f'MUTANT {mutation}',flush=True)
                mutant=Native(directory,mutation);loaded.append(mutant)
                try:run_case(mutant,next(c for c in cases() if c['name']==name),mutation)
                except (AssertionError,v.Mismatch):mutants.append(dict(id=mutation,witness=name,outcome='detected'))
                else:raise AssertionError(f'mutation {mutation} escaped its witness')
                mutant.close();loaded.remove(mutant);del mutant;gc.collect()
            if len(mutants)!=len(witnesses):raise AssertionError('mutation witness missing')
        finally:
            for native in loaded:native.close()
            loaded.clear();gc.collect()
    v.check(before==input_hashes(),'resource-retry inputs changed during campaign')
    write_json(BUILD/'resource-retry-differential.json',dict(source=sha((ROOT/'c/resource_retry.c').read_bytes()),
        input_hashes=before,input_cases=summaries,full_screen_cases=screen_summaries,
        routed_cases=routed_summaries,mutants=mutants))
    print(f'PASS resource retry input cases={len(summaries)} full-screen cases={len(screen_summaries)} routed cases={len(routed_summaries)} mutants={len(mutants)}')
if __name__=='__main__':main()
