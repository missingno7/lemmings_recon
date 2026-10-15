"""Independent bus-visible raw reader and connected fatal error paths."""
import ctypes
import gc
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INTR)
from unicorn import x86_const as x
import file_error as printer
import fatal_cleanup as cleanup
import video_restore as common
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import ROOT,BUILD,sha,write_json
from dat_io_c import MEM,Regs
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes());START=0x1916
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
RAW_INS={i.address:i for i in MD.disasm(IMAGE[START:0x1949],START) if i.address not in (0x193f,0x1945)}
INS=dict(printer.INS,**{})|RAW_INS
RAW_EDGES={(0x1924,0x193a),(0x1924,0x1926),(0x192f,0x1940),(0x192f,0x1931),
           (0x1935,0x1946),(0x1935,0x1937),(0x193d,0x1949),(0x1943,0x1949)}
BRANCHES={p for p,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
State,REGS,FULL=common.State,common.REGS,common.FULL
REPORT=BUILD/'resource-raw-full-differential.json';ORIGINAL_REPORT=BUILD/'resource-raw-full-contract-original.json'
SIZE=1<<20


class DosResult(ctypes.Structure):_fields_=[('value',ctypes.c_uint16),('flags',ctypes.c_uint16)]
OPEN=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,*([ctypes.c_uint16]*3),ctypes.POINTER(DosResult))
READ=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,*([ctypes.c_uint16]*5),ctypes.POINTER(DosResult))
class RawServices(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('open',OPEN),('read',READ),('close',OPEN)]
class Services(ctypes.Structure):_fields_=[('raw',ctypes.POINTER(RawServices)),('file_error',ctypes.POINTER(printer.Services))]
class RawCall(ctypes.Structure):
    _fields_=[(k,ctypes.c_uint16) for k in ('filename_segment','filename_offset','destination_segment','destination_offset','count','initial_handle','stack_segment','stack_offset','flags')]
class RawResult(ctypes.Structure):
    _fields_=[(k,ctypes.c_uint16) for k in ('value','handle','count','offset','segment','extra_segment','stack_offset','flags','error_stage')]
class NativeMismatch(AssertionError):pass
def oracle_fail(message):raise common.fixture.VerificationFailure(message)
def native_fail(message):raise NativeMismatch(message)


def cases():
    rows=[]
    def add(name,error=0,**kw):rows.append(dict(name=name,error=error,seed=len(rows),byte=82,length=1,suffix=True,gate=0,**kw))
    for count in (0,1,2,15,256,65535):
        for error in range(4):add(f'count-{count}-error-{error}',error,count=count)
    for sp in (0,1,65535):
        for error in range(4):add(f'sp-{sp}-error-{error}',error,sp=sp)
    for handle in (0,65535):
        for error in range(4):add(f'handle-{handle}-error-{error}',error,handle=handle)
    for kind in ('read-saves','read-return','filename-alias','vga-stack','vga-filename','vga-destination','ds-a20','stack-a20','short-read','empty-read'):add(kind,kind=kind)
    for error in (1,2,3):
        for kind in ('vga-stack','vga-filename','vga-destination','changed-video-return'):add(f'{kind}-error-{error}',error,kind=kind)
    for error in (1,2,3):
        for load in common.LOADS:add(f'missing-printer-{error}-{load:04x}',error,missing='none',load=load)
        for missing in ('message','character','cleanup','terminate'):add(f'missing-{missing}-error-{error}',error,missing=missing)
    for row in rows:row.setdefault('load',common.LOADS[row['seed']%3])
    return rows


def prepare(case):
    memory,s=printer.prepare(case);s.update(ds=0x3000,dx=0x9000,es=0x4000,ax=0x200,cx=case.get('count',4),ss=0x7000,sp=case.get('sp',0x8000))
    kind=case.get('kind')
    if kind=='ds-a20':s['ds']=0xffff
    if kind=='stack-a20':s.update(ss=0xffff,sp=0x11)
    if kind=='filename-alias':s.update(ss=s['ds'],sp=0x252a)
    if kind in ('read-saves','read-return'):s.update(es=s['ss'],ax=(s['sp']-4)&65535 if kind=='read-saves' else s['sp'],cx=4 if kind=='read-saves' else 2)
    if kind=='vga-stack':s['ss']=0xa000
    if kind=='vga-filename':s['ds']=0xa000
    if kind=='vga-destination':s['es']=0xa000
    if kind=='short-read':s['cx']=256
    if kind=='empty-read':s['cx']=8
    for ds in {(case['load']+0x9a9)&65535,0x3000,0x3400,0x3500,0x3600,0x3700,0x4200,0xffff}:
        for offset,text in ((0x2194,b'open failure$'),(0x21a5,b'read failure$'),(0x21b6,b'close failure$')):printer.string(memory,ds,offset,text)
    printer.string(memory,s['ds'],s['dx'],b'R\0')
    common.putword(memory,s['ss'],s['sp'],0xeedd)
    return memory,s


def device(memory,case):
    backend=printer.device(memory,case)
    if case.get('kind')=='vga-stack':
        for p,v in ((0x7ff6,2),(0x7ff8,0x4000),(0x7ffa,0x200),(0x7ffc,0x4200),(0x7ffe,0x4300),(0x8000,0xeedd)):
            common.putword(backend.vga.planes[2],0,p,v)
        if case['error']:
            sp=0x8000-(10 if case['error']==1 else 4)
            common.putword(backend.vga.planes[2],0,(sp-2)&65535,{1:0x2194,2:0x21a5,3:0x21b6}[case['error']])
            common.putword(backend.vga.planes[2],0,(sp-4)&65535,0x1952)
    return backend


class Environment(printer.Environment):
    def __init__(self,case,backend):super().__init__(case,backend);self.raw_calls=[]
    def raw(self,function,args,flags):
        if len(self.raw_calls)>=3:oracle_fail('Raw service budget exhausted')
        stage={'open':1,'read':2,'close':3}[function];failed=self.case['error']==stage
        changed=[]
        if function=='open':value=5 if failed else self.case.get('handle',0x1234)
        elif function=='close':value=5 if failed else args[1]
        else:
            handle,seg,off,count=args;kind=self.case.get('kind')
            returned=min(count,0 if kind=='empty-read' else 1 if kind=='short-read' else 4 if kind=='read-saves' else 2 if kind=='read-return' else 3)
            value=5 if failed else returned
            if not failed:
                payload=b'\x44\x33\x66\x55' if kind=='read-saves' else b'\xad\xde' if kind=='read-return' else bytes((0x51+n*17)&255 for n in range(returned))
                for n,byte in enumerate(payload[:returned]):
                    p=common.physical(seg,(off+n)&65535)
                    self.backend.vga.write(self.backend.memory,p,byte,flags);changed.append(p)
        outflags=2|((self.case['seed']*0x59+stage*0x97)&0xed4)|(1 if failed else 0)
        self.raw_calls.append((function,tuple(args),flags&FULL,value,outflags&FULL))
        return value,outflags,changed


def model(case,memory,initial,*,core,raw_only):
    backend=device(memory,case);env=Environment(case,backend);s=dict(initial);sites=set();edges=set()
    def mark(p):sites.add(p)
    def readword(seg,off):
        p=common.physical(seg,off);values=[]
        for n in range(2):
            q=(p+n)&0xfffff;v=backend.vga.read(backend.memory,q,s['flags']);backend.events.add('read',q,v,s['flags'],FULL);values.append(v)
        return values[0]|values[1]<<8
    def putword(seg,off,value):
        p=common.physical(seg,off)
        for n in range(2):
            q=(p+n)&0xfffff;v=(value>>(n*8))&255;backend.vga.write(backend.memory,q,v,s['flags']);backend.events.add('write',q,v,s['flags'],FULL)
    def push(v):s['sp']=(s['sp']-2)&65535;putword(s['ss'],s['sp'],v)
    def pop():v=readword(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535;return v
    def raw(pc,function,args):mark(pc);s['ax'],s['flags'],_=env.raw(function,args,s['flags'])
    for pc,k in ((0x1916,'ds'),(0x1917,'es'),(0x1918,'ax'),(0x1919,'es'),(0x191a,'cx')):mark(pc);push(s[k])
    mark(0x191b);putword(s['ds'],0x2528,s['dx']);mark(0x191f);s['ax']=0x3d00;raw(0x1922,'open',(s['ds'],s['dx']))
    mark(0x1924);failed=bool(s['flags']&1);edges.add((0x1924,0x193a if failed else 0x1926))
    if failed:mark(0x193a);s['dx']=0x2194;mark(0x193d);edges.add((0x193d,0x1949))
    else:
        mark(0x1926);s['bx']=s['ax'];mark(0x1928);s['ax']=(s['ax']&255)|0x3f00
        mark(0x192a);s['cx']=pop();mark(0x192b);s['ds']=pop();mark(0x192c);s['dx']=pop()
        raw(0x192d,'read',(s['bx'],s['ds'],s['dx'],s['cx']))
        mark(0x192f);failed=bool(s['flags']&1);edges.add((0x192f,0x1940 if failed else 0x1931))
        if failed:mark(0x1940);s['dx']=0x21a5;mark(0x1943);edges.add((0x1943,0x1949))
        else:
            mark(0x1931);s['ax']=(s['ax']&255)|0x3e00;raw(0x1933,'close',(s['bx'],s['ax']))
            mark(0x1935);failed=bool(s['flags']&1);edges.add((0x1935,0x1946 if failed else 0x1937))
            if failed:mark(0x1946);s['dx']=0x21b6
            else:
                mark(0x1937);s['es']=pop();mark(0x1938);s['ds']=pop()
                if core:return backend,s,env,0x1939,0,FULL,sites,edges
                mark(0x1939);target=pop();return backend,s,env,target,0,FULL,sites,edges
    if raw_only:return backend,s,env,0x1949,4,FULL,sites,edges
    _,state,_,target,status,mask,childsites,childedges=printer.model(case,backend.memory,s,backend=backend,environment=env)
    return backend,state,env,target,status+1,mask,sites|childsites,edges|childedges


def original(case,memory,initial,*,core,raw_only):
    backend=device(memory,case);env=Environment(case,backend);cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,SIZE*2);cpu.mem_write(0,bytes(backend.memory)*2)
    for k,v in dict(initial,cs=case['load'],ip=START).items():cpu.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],v)
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load']);values={(case['load']<<4)+p+n:loaded[p+n] for p,i in INS.items() for n in range(i.size)}
    if any(backend.memory[p]!=v for p,v in values.items()):oracle_fail('Raw full entered modified code')
    mask,event_flags,previous,pending,status,done,steps=FULL,initial['flags'],None,None,None,False,0
    stack,sites,edges,failure=[],set(),set(),[]
    def fail(error):
        if not failure:failure.append(str(error))
        cpu.emu_stop()
    def sync(addresses):
        for p in addresses:
            v=bytes((backend.memory[p],));cpu.mem_write(p,v);cpu.mem_write(p+SIZE,v)
        if any(backend.memory[p]!=v for p,v in values.items()):oracle_fail('Raw provider modified decoded code')
    def code(uc,_pc,_size,_user):
        nonlocal mask,event_flags,previous,pending,status,done,steps
        if previous in (0xffb,0x1963):mask=common.LOGIC
        if previous==0x1967:mask=FULL
        off,cs=uc.reg_read(x.UC_X86_REG_IP),uc.reg_read(x.UC_X86_REG_CS)
        if pending is not None:
            wanted=pending;pending=None
            if wanted is False:done,status=True,0;uc.emu_stop();return
            if not stack or stack.pop()!=wanted:fail('Unknown raw full child frame');return
            if off!=wanted or cs!=case['load']:done,status=True,3;uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        if core and off==0x1939:done,status=True,0;uc.emu_stop();return
        if raw_only and off==0x1949:done,status=True,4;uc.emu_stop();return
        if cs!=case['load'] or off not in INS:fail(f'Raw full escaped {cs:04x}:{off:04x}');return
        if not raw_only and off==printer.stop_pc(case):done,status=True,2;uc.emu_stop();return
        steps+=1
        if steps>512:fail('Raw full instruction budget exhausted');return
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS);previous=off;sites.add(off)
        if off in printer.CALLS:stack.append(printer.CALLS[off][1])
        if INS[off].mnemonic=='ret':
            if off==0x1939:pending=False
            elif stack:pending=stack[-1]
            else:fail('Forbidden raw full outer RET')
    def read(uc,_a,address,size,_v,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=backend.vga.read(backend.memory,p,event_flags);backend.events.add('read',p,v,event_flags,mask);uc.mem_write(address+n,bytes((v,)))
            backend.check('raw full original read')
        except BaseException as error:fail(error)
    def write(_uc,_a,address,size,value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=(value>>(n*8))&255
                if p in values and values[p]!=v:oracle_fail('Raw full wrote decoded code')
                backend.vga.write(backend.memory,p,v,event_flags);backend.events.add('write',p,v,event_flags,mask);sync((p,))
            backend.check('raw full original write')
        except BaseException as error:fail(error)
    def interrupt(uc,number,_user):
        nonlocal mask,done,status
        try:
            incoming={k:uc.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in REGS}
            if previous in (0x1922,0x192d,0x1933):
                if number!=0x21:oracle_fail('Wrong raw interrupt')
                key={0x1922:'open',0x192d:'read',0x1933:'close'}[previous]
                if incoming['ax']>>8!={'open':0x3d,'read':0x3f,'close':0x3e}[key] or key=='open' and incoming['ax']!=0x3d00:oracle_fail('Wrong raw DOS function')
                args=(incoming['ds'],incoming['dx']) if key=='open' else (incoming['bx'],incoming['ds'],incoming['dx'],incoming['cx']) if key=='read' else (incoming['bx'],incoming['ax'])
                value,flags,changed=env.raw(key,args,incoming['flags']);sync(changed);uc.reg_write(x.UC_X86_REG_AX,value);uc.reg_write(x.UC_X86_REG_EFLAGS,flags);mask=FULL;return
            key={0xffd:'error-mode',0x1004:'error-page',0x1955:'file-message',0x158e:'keyboard2',0x4f2:'message',0x4f7:'terminate'}.get(previous)
            if previous in (0x195b,0x196a,0x1972,0x1978):key=env.character_key()
            if key is None or number!=(0x10 if key in ('error-mode','error-page') else 0x21):oracle_fail('Unexpected raw full interrupt')
            out,changed=env.invoke(key,incoming,mask);sync(changed)
            if key=='terminate':done,status=True,1;uc.emu_stop();return
            for k in REGS:uc.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],out[k])
            mask=FULL
        except BaseException as error:fail(error)
    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write);cpu.hook_add(UC_HOOK_INTR,interrupt)
    cpu.emu_start((case['load']<<4)+START,0,count=513)
    if failure:oracle_fail(case['name']+':'+failure[0])
    if not done:oracle_fail('Raw full did not finish')
    regs={k:cpu.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in (*REGS,'cs','ip')}
    return backend,regs,env,regs['ip'],status,mask,sites,edges


def equal_env(got,want,fail,label):
    printer.equal_env(got,want,fail,label)
    if got.raw_calls!=want.raw_calls:fail(label+' raw DOS trace differs')


def original_case(case,*,core,raw_only):
    memory,initial=prepare(case);expected,s,env,target,status,mask,sites,edges=model(case,memory,initial,core=core,raw_only=raw_only)
    backend,regs,actual,at,ast,am,asi,ae=original(case,memory,initial,core=core,raw_only=raw_only)
    label=case['name']+' model';common.equal_state(regs,s,mask,oracle_fail,label);common.equal_device(backend,expected,oracle_fail,label);equal_env(actual,env,oracle_fail,label)
    if (at,ast,am,asi,ae,regs['cs'])!=(target,status,mask,sites,edges,case['load']):oracle_fail(label+' boundary/sites differ')
    return memory,initial,backend,regs,actual,target,status,mask,sites,edges


def native_services(case,backend):
    env=Environment(case,backend)
    file_service,_,refs=printer.native_services(case,backend,environment=env)
    def call(fn,args,flags,out):
        if len(env.raw_calls)>=3:common.fixture.exit_worker(86,'Raw DOS budget exhausted')
        try:out[0].value,out[0].flags,_=env.raw(fn,args,flags)
        except BaseException as error:common.fixture.exit_worker(87,f'Raw DOS callback:{error}')
    @OPEN
    def opened(_ctx,_memory,seg,offset,flags,out):call('open',(seg,offset),flags,out)
    @READ
    def read(_ctx,_memory,handle,seg,offset,count,flags,out):call('read',(handle,seg,offset,count),flags,out)
    @OPEN
    def close(_ctx,_memory,handle,value,flags,out):call('close',(handle,value),flags,out)
    raw=RawServices(None,opened,read,close);full=Services(ctypes.pointer(raw),ctypes.pointer(file_service) if file_service is not None else None)
    return full,raw,env,(file_service,refs,opened,read,close)


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'raw-full-m{mutation}.dll',mutation,'resource_raw_full')))
        bus=ctypes.POINTER(common.fixture.RasterBus)
        self.core=self.lib.lmn_read_raw_resource_full_core;self.core.argtypes=[MEM,ctypes.c_uint16,ctypes.POINTER(State),ctypes.POINTER(Services),bus];self.core.restype=cleanup.Result
        self.adapter=self.lib.lmn_read_raw_resource_full_adapter;self.adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Services),bus]
        self.rawcore=self.lib.lmn_read_raw_resource_bus_core;self.rawcore.argtypes=[MEM,ctypes.POINTER(RawCall),ctypes.POINTER(RawServices),bus];self.rawcore.restype=RawResult
        self.rawadapter=self.lib.lmn_read_raw_resource_bus_adapter;self.rawadapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(RawServices),bus]


def compare(native,case):
    sites,edges=set(),set();vga=case.get('kind','').startswith('vga-')
    for raw_only in (True,False):
        for core in (False,True):
            memory,initial,expected,regs,env,target,status,mask,executed,branch=original_case(case,core=core,raw_only=raw_only);sites|=executed;edges|=branch
            for null in (False,True):
                if null and vga:continue
                backend=device(memory,case);services,raw,actual,refs=native_services(case,backend);bus=None if null else ctypes.byref(backend.bus)
                label=case['name']+(' raw' if raw_only else ' full')+(' core' if core else ' adapter')
                if core:
                    if raw_only:
                        c=RawCall(initial['ds'],initial['dx'],initial['es'],initial['ax'],initial['cx'],initial['bx'],initial['ss'],initial['sp'],initial['flags'])
                        out=native.rawcore(common.buffer(backend.memory),ctypes.byref(c),ctypes.byref(raw),bus);current=dict(initial)
                        for k,field in (('ax','value'),('bx','handle'),('cx','count'),('dx','offset'),('ds','segment'),('es','extra_segment'),('sp','stack_offset'),('flags','flags')):current[k]=getattr(out,field)
                        if out.error_stage!=case['error']:native_fail(label+' raw stage differs')
                    else:
                        s=common.to_state(initial);out=native.core(common.buffer(backend.memory),(case['load']+0x9a9)&65535,ctypes.byref(s),ctypes.byref(services),bus);current=common.state_dict(out.state)
                        if (out.continuation,out.status)!=(target,status):native_fail(label+' boundary/status differs')
                else:
                    r=Regs(**{k:v for k,v in initial.items() if k!='flags'},cs=case['load'],ip=START,flags=initial['flags'])
                    if raw_only:native.rawadapter(common.buffer(backend.memory),ctypes.byref(r),ctypes.byref(raw),bus)
                    else:native.adapter(common.buffer(backend.memory),ctypes.byref(r),ctypes.byref(services),bus)
                    current={k:getattr(r,k) for k in REGS}
                    if (r.cs,r.ip)!=(case['load'],target):native_fail(label+' ip/cs differs')
                common.equal_state(current,regs,mask,native_fail,label);equal_env(actual,env,native_fail,label)
                if null:
                    if backend.memory!=expected.memory:native_fail(label+' null RAM differs')
                else:common.equal_device(backend,expected,native_fail,label)
    return dict(name=case['name'],error=case['error'],vga=vga,sites=sorted(sites),edges=sorted(edges))


def input_hashes(native=False):
    paths=set(printer.input_hashes(native));paths.update(('tests/resource_raw_full.py','docs/resource-raw-full.md','docs/resource-raw.md'))
    if native:paths.update(('c/resource_raw.c','c/resource_raw.h','c/resource_raw_full.c','c/resource_raw_full.h','c/dat_io.h'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before=input_hashes();rows=[];sites=set();edges=set()
    if sha(ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d' or sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e':
        oracle_fail('Raw full image changed')
    for case in cases():
        for raw_only in (True,False):
            for core in (False,True):
                r=original_case(case,core=core,raw_only=raw_only);sites.update(r[-2]);edges.update(r[-1])
        rows.append(case['name']);gc.collect()
    if len(RAW_INS)!=27 or len(INS)!=72 or sites!=set(INS) or edges!=RAW_EDGES|{(0x1965,0x1967),(0x1965,0x196e),(0x196c,0x1961),(0x197a,0x4ea)}:oracle_fail('Raw full static/branch coverage differs')
    if before!=input_hashes():oracle_fail('Raw full original inputs changed')
    write_json(ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),original_boundaries_per_case=4,caller_sites=27,caller_bytes=49,integrated_bytes=147,executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),cases=rows,input_hashes=before,c_coverage_claimed=False))
    print(f'PASS raw full original:{len(rows)} cases x4 boundaries,27 caller/72 integrated sites,12 edges;no C coverage',flush=True)


def worker(directory=None):
    common.fixture.MAX_BUS_EVENTS=512;common.fixture.MAX_VGA_EVENTS=512
    before=input_hashes(directory is not None);original_phase()
    if directory is None:return
    native=Native(directory);rows=[];specs=cases()
    for case in specs:rows.append(compare(native,case));gc.collect()
    mutants=[]
    for number,name in ((1,'count-1-error-0'),(2,'filename-alias'),(3,'count-1-error-1'),(4,'count-1-error-2')):
        variant=Native(directory,number);case=next(c for c in specs if c['name']==name)
        try:compare(variant,case)
        except NativeMismatch as error:mutants.append(dict(mutation=number,case=name,mismatch=str(error),completed=True))
        else:oracle_fail(f'Raw full mutant{number} survived')
        gc.collect()
    if before!=input_hashes(True):oracle_fail('Raw full native inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),auxiliary_core_cases=len(rows),auxiliary_raw_adapter_cases=len(rows),auxiliary_raw_core_cases=len(rows),null_bus_cases_each_boundary=sum(not r['vga'] for r in rows),mutation_count=4,mutations=mutants,cases=rows,translated_code_bytes=49,native_code_ranges=[[0x1916,0x193f],[0x1940,0x1945],[0x1946,0x1949]],executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),branch_edges=sorted({tuple(e) for r in rows for e in r['edges']}),input_hashes=before,limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_instructions=512,bus_events=512,raw_services=3,printer_services=64),domain='1916 bus core and direct1949 fatal composition; narrow preserving raw DOS AX/flags contract plus all-state printer/cleanup services; intactcode/sameCS/TFclear/quiescentIRQ; canonical RAM/VGA,actualnormalRET andoriginalfatalframes.'))
    print(f'PASS raw full C:{len(rows)} cases x4 boundaries,27 caller/72 integrated sites,4 completed mutants',flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True);run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected raw full arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='raw-full-',parent=BUILD) as directory:run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)


if __name__=='__main__':main()
