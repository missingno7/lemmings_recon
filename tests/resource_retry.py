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
from bounded_process import temporary_build_directory
from cbuild import build
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
        self.lib=ct.CDLL(str(build(Path(output)/f'resource-retry-{mutation}.dll',mutation,'resource_retry')))
        self.fn=self.lib.lmn_resource_retry_input_core;self.fn.restype=Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(v.Bus),ct.POINTER(v.ForegroundPoll)]
        self.screen=self.lib.lmn_resource_retry_screen_core;self.screen.restype=ScreenResult
        self.screen.argtypes=[v.MEM,ct.c_uint16,ct.c_uint16,ct.POINTER(VideoState),ct.c_void_p,
            ct.POINTER(v.Bus),ct.POINTER(v.Ports),ct.POINTER(v.ForegroundPoll)]
        self.screen_adapter=self.lib.lmn_resource_retry_screen_adapter;self.screen_adapter.restype=None
        self.screen_adapter.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_uint16,ct.c_void_p,
            ct.POINTER(v.Bus),ct.POINTER(v.Ports),ct.POINTER(v.ForegroundPoll)]
    def close(self):
        self.fn=None
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

def main():
    summaries=[];screen_summaries=[]
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
    write_json(BUILD/'resource-retry-differential.json',dict(source=sha((ROOT/'c/resource_retry.c').read_bytes()),
        input_cases=summaries,full_screen_cases=screen_summaries,mutants=mutants))
    print(f'PASS resource retry input cases={len(summaries)} full-screen cases={len(screen_summaries)} mutants={len(mutants)}')
if __name__=='__main__':main()
