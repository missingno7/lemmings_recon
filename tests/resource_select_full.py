"""Selector continuations and direct fatal tails, using bounded original code."""
import ctypes
import gc
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),
                str(Path(__file__).resolve().parent)]
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN)
from unicorn import x86_const as x
import resource_select as prefix
import file_error as printer
import fatal_cleanup as cleanup
import video_restore as common
from dat_files import Call, MAPPING
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json, read_json

SIZE = 1 << 20
REPORT = BUILD/'resource-select-full-differential.json'
ORIGINAL_REPORT = BUILD/'resource-select-full-contract-original.json'
INS = prefix.INS | printer.INS | cleanup.INS
BRANCHES = {p for p,i in INS.items() if i.group(prefix.decoder.capstone.CS_GRP_JUMP)
            or i.mnemonic.startswith('loop')}
TOP_CALLS = {0x19a0:0x19a3,0x19b3:0x19b6,0x19be:0x19c1,0x19dc:0x19df,
             0x1a18:0x1a1b,0x1a40:0x1a43,0x1a51:0x1a54,0x1a72:0x1a75}
RETURNS = (0x1a59,0x1a7a)
MEM, Regs = prefix.MEM, prefix.Regs
FULL, LOGIC = common.FULL, common.LOGIC


class Segments(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint16) for n in ('retry','lookup','read','failure')]
class Execution(ctypes.Structure):
    _fields_=[('state',Call),('continuation',ctypes.c_uint16),('status',ctypes.c_int)]
class Services(ctypes.Structure):
    _fields_=[('selection',ctypes.POINTER(prefix.SelectionServices)),
              ('file_error',ctypes.POINTER(printer.Services)),
              ('cleanup',ctypes.POINTER(cleanup.Services))]


class NativeMismatch(AssertionError): pass
def fail(message): raise common.fixture.VerificationFailure(message)
def native_fail(message): raise NativeMismatch(message)


def cases():
    rows=[]
    def add(base,**kw):
        row=dict(base);row.update(kw);row['seed']=len(rows)
        row.setdefault('route','normal');row.setdefault('length',3)
        row.setdefault('gate',0);row['suffix']=row['route']=='file'
        row['byte']=65;row['load']=common.LOADS[row['seed']%3];rows.append(row)
    old=prefix.cases()
    normal=('section-0-odd-False','section-7-odd-True','special-resource-path',
            'cache-hit','cache-miss','attributes-retry','stack-ffff','stack-underflow',
            'ground-read-overwrites-saved-ds','level-close-carry-ignored','final-close-carry-exposed')
    for row in old:
        if row['name'] in normal or row['name'].startswith('real-'):add(row)
        elif 'fatal' in row['name']:
            add(row,route='file' if row.get('raw_error') or row['name']=='attributes-fatal' else 'cleanup')
    base=next(r for r in old if r['name']=='ground-open-fatal')
    add(base,name='error-printer-uses-relocated-main-frame',route='file',entry_ds=0x6000)
    for missing in ('none','video','mode','page','message','character','cleanup','cleanup-vector','cleanup-message','terminate'):
        add(base,name='file-missing-'+missing,route='file',missing=missing)
    base=next(r for r in old if r['name']=='level-header-fatal')
    for missing in ('no-services','timer','port','clock','vectors','video','mode','page','mouse','message','terminate'):
        add(base,name='cleanup-missing-'+missing,route='cleanup',missing=missing)
    for target,kind,order,special in ((0x19b6,'level',1,0),(0x19c1,'level',3,0),
        (0x19df,'odd',2,0),(0x1a1b,'ground',1,0),(0x1a43,'graphics',1,0),
        (0x1a54,'graphics',1,0),(0x1a75,'special',1,1)):
        add(dict(name=f'changed-{target:04x}',order=order,special=special),
            route='changed',change_return=target,change_kind=kind,changed_target=0xdead)
    for destination in (0x1949,0x4d0):
        add(dict(name=f'changed-to-fatal-address-{destination:04x}',order=1),route='changed',
            change_return=0x1a1b,change_kind='ground',changed_target=destination)
    add(dict(name='decimal-digits-overwrite-child-return',order=1),route='changed',decimal_alias=True)
    for route,base_name,kinds in (('file','ground-read-fatal',('changed-video-return','saved-dx-overwrite','returned-ds-bx','space-pointer')),
                                 ('cleanup','graphics-header-fatal',('changed-clock','changed-keyboard2','message-stack-ffff'))):
        base=next(r for r in old if r['name']==base_name)
        for kind in kinds:add(base,name=route+'-'+kind,route=route,kind=kind)
    return rows


class Events:
    def __init__(self):self.count=0
    def add(self,*_args):
        self.count+=1
        if self.count>1024:fail('Suffix model access budget exhausted')
class Ram:
    def read(self,memory,address,_flags):return memory[address&0xfffff]
    def write(self,memory,address,value,_flags):memory[address&0xfffff]=value
class Backend:
    def __init__(self,memory):self.memory=memory;self.vga=Ram();self.events=Events()


def prepare(case):
    memory,regs,flags,data,payloads,chosen,assets=prefix.prepare(case)
    # Only fields read by the error/restore leaves and fixture-returned frames.
    # Main prefix buffers and filenames retain their original fixture contents.
    for ds in (data,0x3000,0x3100,0x3400,0x3500,0x3600,0x3700,0x3800,0x4200):
        for off,value in ((0x1fba,0x4411),(0x1fbc,0x5511),(0x1fbe,0x4422),
                          (0x1fc0,0x5522),(0x1fc2,0x4433),(0x1fc4,0x5533),
                          (0x259c,0x1234),(0x259e,0xabcd)):
            common.putword(memory,ds,off,value)
        for off,value in ((0x1fc6,case['seed']&255),(0x1fe1,3),(0x1fe2,7),(0x1f73,case['gate'])):
            memory[common.physical(ds,off)]=value
        if ds!=data:common.putword(memory,ds,0x2528,0x9000)
        for off,text in ((0x20ac,b'exit$'),(0x2194,b'open error$'),(0x21a5,b'read error$'),
                         (0x21b6,b'close error$'),(0x2300,b'error$'),(0x2400,b'changed$'),
                         (0x8800,b'old\0'),(0x9000,b'ABC\0')):
            printer.string(memory,ds,off,text)
    if case.get('kind')=='space-pointer':
        common.putword(memory,0x3500,0x2528,0x8800)
        printer.string(memory,0x3600,0x8800,b'bad\0')
        printer.string(memory,0x3600,0x9000,b'new\0')
    if case.get('kind')=='returned-ds-bx':printer.string(memory,0x3700,0x9000,b'xy\0')
    if case.get('decimal_alias'):
        regs.update(ss=data,sp=prefix.field('LevelResourceFilenameDigits')+6)
        common.putword(memory,regs['ss'],regs['sp'],0xff00)
    if case.get('entry_ds'):
        start=common.physical(data,0);target=common.physical(case['entry_ds'],0)
        memory[target:target+65536]=memory[start:start+65536]
        regs['ds']=case['entry_ds']
    return memory,dict(regs,flags=flags),data,payloads,chosen,assets


class Provider(prefix.Provider):
    def __init__(self,*args):super().__init__(*args);self.changed=False
    def read(self,handle,seg,off,count,flags):
        result=super().read(handle,seg,off,count,flags)
        if not self.changed and self.handles[handle]==self.case.get('change_kind'):
            # The second graphics decoder is not active on the first section.
            if self.case['change_return']!=0x1a54 or self.calls[handle]>=3:
                wanted=self.case['change_return'];sp=self.regs['sp'];ss=self.regs['ss']
                matches=[(sp-d)&65535 for d in range(2,66,2)
                         if cleanup.word(self.mem,ss,(sp-d)&65535)==wanted]
                if not matches:return result
                if len(matches)!=1:fail(f'Expected one active {wanted:04x} frame, got {matches}')
                common.putword(self.mem,ss,matches[0],self.case['changed_target']);self.changed=True
        return result


def native_prefix(case,backend,initial,data,payloads,chosen):
    p=Provider(case,backend.memory,initial,data,payloads,chosen);refs=[]
    def guarded(fn,out,*args):
        if len(p.trace)>=512:common.fixture.exit_worker(86,'Selector provider budget exhausted')
        try:
            for (name,_),value in zip(out[0]._fields_,fn(*args)):setattr(out[0],name,value)
        except BaseException as error:common.fixture.exit_worker(87,f'Selector callback:{error}')
    @prefix.FILE
    def opened(_ctx,_mem,seg,off,flags,out):guarded(p.file,out,0x3d,seg,off,flags)
    @prefix.FILE
    def attributes(_ctx,_mem,seg,off,flags,out):guarded(p.file,out,0x43,seg,off,flags)
    @prefix.QUERY
    def query(_ctx,_mem,seg,off,flags,out):guarded(p.query,out,seg,off,flags)
    @prefix.READ
    def read(_ctx,_mem,handle,seg,off,count,flags,out):guarded(p.read,out,handle,seg,off,count,flags)
    @prefix.RETRY_FN
    def retry(_ctx,_mem,call,out):guarded(p.retry,out,{reg:getattr(call[0],name) for name,reg in MAPPING.items()})
    @prefix.OPEN
    def raw_open(_ctx,_mem,seg,off,flags,out):
        def invoke(*args):value,_count,f=p.file(0x3d,*args);return value,f
        guarded(invoke,out,seg,off,flags)
    @prefix.OPEN
    def close(_ctx,_mem,handle,value,flags,out):guarded(p.close,out,handle,value,flags)
    files=prefix.Services(None,opened,attributes,retry);io=prefix.Io(None,query,read)
    raw=prefix.RawServices(None,raw_open,read,close)
    service=prefix.SelectionServices(ctypes.pointer(files),ctypes.pointer(io),ctypes.pointer(raw))
    refs.extend((opened,attributes,query,read,retry,raw_open,close,files,io,raw))
    return service,p,refs


def original(case,memory,initial,data,payloads,chosen,*,full,core):
    backend=Backend(bytearray(memory));p=Provider(case,backend.memory,initial,data,payloads,chosen)
    env=(printer.Environment if case['route']=='file' else cleanup.Environment)(case,backend)
    cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,SIZE*2);cpu.mem_write(0,bytes(memory)*2)
    loaded=prefix.decoder.relocated(prefix.decoder.IMAGE,prefix.decoder.ORACLE['relocations'],initial['cs'])
    pinned={(initial['cs']<<4)+off+n:loaded[off+n] for off,i in INS.items() for n in range(i.size)}
    def intact():
        if any(backend.memory[p]!=v for p,v in pinned.items()):fail('Selector modified identified instruction bytes')
    intact()
    def state():return {n:cpu.reg_read(x.UC_X86_REG_EFLAGS if n=='flags' else prefix.oracle.REG[n])&65535 for n in common.REGS}
    for n,v in initial.items():cpu.reg_write(x.UC_X86_REG_EFLAGS if n=='flags' else prefix.oracle.REG[n],v)
    sites=set();edges=set();stack=[];pending=None;previous=None;done=False;status=None
    mask=FULL;steps=0;failure=[];suffix_snapshot=None;suffix_mask=None;suffix_sites=set();suffix_edges=set()
    def sync():
        intact();cpu.mem_write(0,bytes(backend.memory));cpu.mem_write(SIZE,bytes(backend.memory))
    def error(exc):
        if not failure:failure.append(str(exc))
        cpu.emu_stop()
    def code(uc,pc,_size,_user):
        nonlocal pending,previous,done,status,mask,steps,suffix_snapshot,suffix_mask
        try:
            off=pc-(initial['cs']<<4)
            # All identified instructions use near calls/returns. The providers
            # return twelve fields, which exclude CS. Check CS at boundaries.
            cs=initial['cs']
            if previous in (0xffb,0x1963,0x16af,0x16b5,0x4e6):mask=LOGIC
            if previous==0x1967:mask=FULL
            if pending is not None:
                expected,site=pending;pending=None
                if expected is False:done,status=True,0;uc.emu_stop();return
                if off!=expected or cs!=initial['cs']:
                    if site not in TOP_CALLS and site not in cleanup.CALLS and site not in printer.CALLS:
                        fail('Changed internal DAT return outside declared child contract')
                    done,status=True,3;uc.emu_stop();return
            if previous in BRANCHES:
                edges.add((previous,off))
                if suffix_snapshot is not None:suffix_edges.add((previous,off))
            if core and off in RETURNS:done,status=True,0;uc.emu_stop();return
            if off in (0x1949,0x4d0):
                if not full:done,status=True,1 if off==0x1949 else 2;uc.emu_stop();return
                if suffix_snapshot is None:
                    backend.memory[:]=uc.mem_read(0,SIZE)
                    suffix_snapshot=(off,bytes(backend.memory),state());suffix_mask=mask
            if cs!=initial['cs']:fail('Selector changed CS')
            if suffix_snapshot is not None:
                missing=printer.stop_pc(case) if case['route']=='file' else cleanup.missing_pc(case)
                if off==missing:done,status=True,2;uc.emu_stop();return
            if off==prefix.loader.RETRY:
                backend.memory[:]=uc.mem_read(0,SIZE);view=state()
                ax,bx,bp,flags=p.retry(view);sync()
                for n,v in dict(ax=ax,bx=bx,bp=bp,si=0x2222,di=0x3333,ds=0x4444,es=0x5555,cx=0x6666,dx=0x7777).items():uc.reg_write(prefix.oracle.REG[n],v)
                ss,sp=view['ss'],view['sp'];target=cleanup.word(backend.memory,ss,sp)
                expected,site=stack.pop()
                if target!=expected:fail('Changed retry return outside declared contract')
                uc.reg_write(prefix.oracle.REG['ip'],target);uc.reg_write(prefix.oracle.REG['sp'],(sp+2)&65535)
                uc.reg_write(x.UC_X86_REG_EFLAGS,flags);mask=FULL;previous=None;return
            if off not in INS:fail(f'Selector escaped at {off:04x}')
            steps+=1
            if steps>10000000:fail('Selector original instruction budget exhausted')
            sites.add(off)
            if suffix_snapshot is not None:suffix_sites.add(off)
            ins=INS[off]
            if ins.mnemonic=='call':stack.append(((off+ins.size)&65535,off))
            if ins.mnemonic=='ret':pending=(False,off) if off in RETURNS else stack.pop()
            previous=off
        except BaseException as exc:error(exc)
    def read(uc,_access,address,size,_value,_user):
        # Only the 20-bit mirror needs intervention; ordinary RAM is Unicorn-owned.
        if address+size>SIZE:
            for n in range(size):uc.mem_write(address+n,bytes((uc.mem_read((address+n)&0xfffff,1)[0],)))
    def write(uc,_access,address,size,value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;byte=(value>>(8*n))&255
                if p in pinned and pinned[p]!=byte:fail('Selector wrote identified instruction bytes')
                if address+size>SIZE:uc.mem_write(p,bytes((byte,)))
        except BaseException as exc:error(exc)
    def interrupt(uc,number,_user):
        nonlocal done,status,mask
        try:
            backend.memory[:]=uc.mem_read(0,SIZE);incoming=state()
            if suffix_snapshot is None:
                if number!=0x21:fail('Unexpected prefix interrupt')
                fn=incoming['ax']>>8
                if fn in (0x3d,0x43):value,count,flags=p.file(fn,incoming['ds'],incoming['dx'],incoming['flags'])
                elif fn==0x23:value,flags=p.query(incoming['ds'],incoming['dx'],incoming['flags'])
                elif fn==0x3f:value,flags=p.read(incoming['bx'],incoming['ds'],incoming['dx'],incoming['cx'],incoming['flags'])
                elif fn==0x3e:value,flags=p.close(incoming['bx'],incoming['ax'],incoming['flags'])
                else:fail('Unexpected prefix DOS function')
                if len(p.trace)>512:fail('Selector original provider budget exhausted')
                sync();uc.reg_write(prefix.oracle.REG['ax'],value)
                if fn==0x43:uc.reg_write(prefix.oracle.REG['cx'],count)
                uc.reg_write(x.UC_X86_REG_EFLAGS,flags);mask=FULL;return
            if case['route']=='file':
                key={0xffd:'error-mode',0x1004:'error-page',0x1955:'file-message',0x158e:'keyboard2',0x4f2:'message',0x4f7:'terminate'}.get(previous)
                if previous in (0x195b,0x196a,0x1972,0x1978):key=env.character_key()
            else:
                key=cleanup.INTERRUPTS.get(previous)
                if previous==0x158e:key='keyboard1' if stack[-1][0]==0x4d6 else 'keyboard2'
            wanted=0x10 if key in ('error-mode','error-page','mode','page') else 0x1a if key=='clock' else 0x33 if key=='mouse' else 0x21
            if key is None or number!=wanted:fail('Unexpected connected suffix interrupt')
            out,_=env.invoke(key,incoming,mask);sync()
            if key=='terminate':done,status=True,1;uc.emu_stop();return
            for n,v in out.items():uc.reg_write(x.UC_X86_REG_EFLAGS if n=='flags' else prefix.oracle.REG[n],v)
            mask=FULL
        except BaseException as exc:error(exc)
    def port(uc,number,size,value,_user):
        try:
            if size!=1:fail('Unexpected suffix OUT width')
            env.port(number,value,state()['flags'],mask)
        except BaseException as exc:error(exc)
    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_INTR,interrupt)
    cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write)
    cpu.hook_add(UC_HOOK_INSN,port,None,1,0,x.UC_X86_INS_OUT)
    cpu.emu_start(common.physical(initial['cs'],prefix.ENTRY),0,count=10000001)
    if failure:fail(case['name']+': '+failure[0])
    if not done:fail(case['name']+': selector did not reach boundary')
    regs=dict(state(),cs=cpu.reg_read(x.UC_X86_REG_CS),ip=cpu.reg_read(x.UC_X86_REG_IP))
    backend.memory[:]=cpu.mem_read(0,SIZE)
    intact()
    if suffix_snapshot is not None:
        entry,ram,start=suffix_snapshot;expected=Backend(bytearray(ram))
        model_env=(printer.Environment if entry==0x1949 else cleanup.Environment)(case,expected)
        result=(printer.model if entry==0x1949 else cleanup.model)(case,expected.memory,start,backend=expected,environment=model_env)
        _backend,s,_env,target,st,defined,model_sites,model_edges=result
        common.equal_state(regs,s,defined,fail,case['name']+' suffix model')
        if bytes(backend.memory)!=bytes(expected.memory):fail(case['name']+' suffix model RAM differs')
        if (regs['ip'],status,suffix_sites,suffix_edges)!=(target,st+1,model_sites,model_edges):
            fail(case['name']+f' suffix model control differs: {(regs["ip"],status)} vs {(target,st+1)}; sites{suffix_sites^model_sites}; edges{suffix_edges^model_edges}')
        equal_env(env,model_env,fail,case['name']+' suffix model');mask=defined
    if regs['ip']==0xff00 and not case.get('change_return'):
        at=common.physical(data,prefix.field('LoadedLevelRecord'))
        if backend.memory[at:at+2048]!=p.expected:fail('Independent selected-record bytes differ')
    return backend,regs,p,env,status,mask,sites,edges


def equal_env(actual,expected,error,label):
    cleanup.equal_environment(actual,expected,error,label)
    if getattr(actual,'characters',[])!=getattr(expected,'characters',[]):error(label+' characters differ')


class Native:
    def __init__(self,directory,mutation=0):
        path=Path(directory)/f'select-full-m{mutation}.dll'
        if not path.exists():build(path,mutation,'resource_select_full')
        self.lib=ctypes.CDLL(str(path))
        self.execution=self.lib.lmn_load_selected_resources_execution_core
        self.execution.argtypes=[MEM,ctypes.POINTER(Call),ctypes.POINTER(Segments),ctypes.POINTER(prefix.SelectionServices)];self.execution.restype=Execution
        self.prefix=self.lib.lmn_load_selected_resources_adapter
        self.prefix.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(prefix.SelectionServices)];self.prefix.restype=None
        self.core=self.lib.lmn_load_selected_resources_full_core
        self.core.argtypes=[MEM,ctypes.c_uint16,ctypes.POINTER(Call),ctypes.POINTER(Segments),ctypes.POINTER(Services)];self.core.restype=cleanup.Result
        self.adapter=self.lib.lmn_load_selected_resources_full_adapter
        self.adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Services)];self.adapter.restype=None


def compare(native,case,boundary=None):
    memory,initial,data,payloads,chosen,assets=prepare(case);seen=set();edges=set();boundaries=[]
    for full in (False,True):
        for core in (False,True):
            if boundary is not None and int(full)*2+int(core)!=boundary:continue
            expected,regs,provider,env,status,mask,sites,branch=original(case,memory,initial,data,payloads,chosen,full=full,core=core)
            seen|=sites;edges|=branch
            if native is not None:
                backend=Backend(bytearray(memory));selection,actual,refs=native_prefix(case,backend,initial,data,payloads,chosen)
                if case['route']=='file':file_service,observed,tail_refs=printer.native_services(case,backend);cleanup_service=None
                else:cleanup_service,observed,tail_refs=cleanup.native_services(case,backend);file_service=None
                service=Services(ctypes.pointer(selection),ctypes.pointer(file_service) if file_service is not None else None,
                                 ctypes.pointer(cleanup_service) if cleanup_service is not None else None)
                buffer=common.buffer(backend.memory);call=Call(**{name:initial[reg] for name,reg in MAPPING.items()})
                # Resolve the same relocated instruction operands as original code.
                segments=Segments(*(cleanup.word(memory,initial['cs'],prefix.SYMS[name]['address']+delta) for name,delta in
                    (('CheckDatFile',0x33),('SelectCachedDatFile',0x50),('ReadDatBytes',8),('DatReadFailure',1))))
                if core:
                    out=native.core(buffer,data,ctypes.byref(call),ctypes.byref(segments),ctypes.byref(service)) if full else native.execution(buffer,ctypes.byref(call),ctypes.byref(segments),ctypes.byref(selection))
                    got=common.state_dict(out.state) if full else {reg:getattr(out.state,name) for name,reg in MAPPING.items()}
                    target,got_status=out.continuation,out.status
                    if (target,got_status)!=(regs['ip'],status):native_fail(case['name']+f' core control {(target,got_status)} != {(regs["ip"],status)}')
                else:
                    r=Regs(**initial)
                    if full:native.adapter(buffer,ctypes.byref(r),ctypes.byref(service))
                    else:native.prefix(buffer,ctypes.byref(r),ctypes.byref(selection))
                    got={n:getattr(r,n) for n in common.REGS}
                    if (r.cs,r.ip)!=(regs['cs'],regs['ip']):native_fail(case['name']+' adapter continuation differs')
                common.equal_state(got,regs,mask,native_fail,case['name'])
                if backend.memory!=expected.memory:
                    at=next(p for p,(a,b) in enumerate(zip(backend.memory,expected.memory)) if a!=b)
                    native_fail(case['name']+f' RAM differs at {at:05x}')
                if actual.trace!=provider.trace or actual.changed!=provider.changed:native_fail(case['name']+' prefix provider effects differ')
                equal_env(observed,env,native_fail,case['name'])
            if regs['cs']!=initial['cs']:fail('Changed original CS at selector boundary')
            if case['route']=='changed':
                target=case.get('changed_target',0x3030)
                if (status,regs['ip'])!=(3,target):fail(case['name']+' did not exercise the exact changed child return')
                if case.get('change_return') and not provider.changed:fail('Requested return-word mutation was not performed')
                if env.calls:fail('Changed return unexpectedly dispatched an error tail')
            elif case['route']=='normal':
                target=(0x1a7a if provider.expected[29] else 0x1a59) if core else 0xff00
                if (status,regs['ip'])!=(0,target):fail('Wrong original normal selector boundary')
            elif not full:
                if (status,regs['ip'])!=({'file':(1,0x1949),'cleanup':(2,0x4d0)}[case['route']]):fail('Wrong original fatal handoff')
            boundaries.append(dict(full=full,core=core,target=regs['ip'],status=status))
    return dict(name=case['name'],sites=sorted(seen),edges=sorted(edges),boundaries=boundaries,assets=assets)


def input_hashes(native=False):
    paths=set(printer.input_hashes(native));paths.update(('tests/resource_select.py','tests/resource_select_full.py','metadata/inputs.json','tools/resources.py'))
    paths.update('tests/'+n+'.py' for n in ('dat_io_c','dat_files','dat_load','dat_section','resource_raw','decimal_digits_c'))
    paths.update('assets/'+p.name for p in (ROOT/'assets').glob('*.dat'))
    if native:paths.update('c/'+n+'.'+ext for n in ('resource_select','resource_select_full','decimal_digits','resource_raw','dat_load','dat_files','dat_cache','dat_section','dat_io','dat') for ext in ('c','h'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory,indexes,boundary,*,native_enabled):
    before=input_hashes(native_enabled);rows=[];native=Native(directory) if native_enabled else None
    baseline=cases()
    for index in indexes:
        rows.append(compare(native,baseline[index],boundary));gc.collect()
    if before!=input_hashes(native_enabled):fail('Selector chunk inputs changed')
    write_json(Path(directory)/'chunk.json',dict(rows=rows,input_hashes=before))


def mutation_worker(directory):
    mutants=[]
    for mutation,name in ((1,'changed-1a1b'),(2,'ground-open-fatal'),(3,'ground-open-fatal'),(4,'changed-to-fatal-address-1949')):
        mutant=Native(directory,mutation);case=next(c for c in cases() if c['name']==name)
        try:compare(mutant,case)
        except NativeMismatch:mutants.append(dict(mutation=mutation,case=name))
        else:fail(f'Selector full mutant{mutation} survived')
    write_json(Path(directory)/'mutants.json',mutants)


def campaign(native_enabled):
    before=input_hashes(native_enabled);baseline=cases();rows={};mutants=[]
    if sha(prefix.decoder.IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e':fail('Canonical image identity differs')
    for row in read_json(ROOT/'metadata/inputs.json')['files']:
        content=(ROOT/row['path']).read_bytes()
        if len(content)!=row['size'] or sha(content)!=row['sha256']:fail('Pinned input identity differs: '+row['path'])
    with temporary_build_directory(prefix='resource-select-full-',parent=BUILD) as directory:
        if native_enabled:build(Path(directory)/'select-full-m0.dll',0,'resource_select_full')
        chunks=[];small=[]
        for index,case in enumerate(baseline):
            if case.get('real'):
                chunks.extend(([index],boundary) for boundary in range(4))
            else:small.append(index)
        chunks[:0]=[(small[n:n+6],None) for n in range(0,len(small),6)]
        for number,(indexes,boundary) in enumerate(chunks):
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--native-chunk' if native_enabled else '--original-chunk',directory,
                         ','.join(map(str,indexes)),str(boundary) if boundary is not None else 'all'],cwd=ROOT,timeout=120,memory_mib=384)
            chunk=read_json(Path(directory)/'chunk.json')
            if chunk['input_hashes']!=before:fail('Chunk used different campaign inputs')
            for row in chunk['rows']:
                if row['name'] not in rows:rows[row['name']]=row
                else:
                    old=rows[row['name']];old['sites']=sorted(set(old['sites'])|set(row['sites']))
                    old['edges']=sorted(set(map(tuple,old['edges']))|set(map(tuple,row['edges'])))
                    old['boundaries'].extend(row['boundaries'])
            print(f'PASS selector chunk {number+1}/{len(chunks)} ({len(rows)}/{len(baseline)} cases observed)',flush=True)
        if native_enabled:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--mutants',directory],cwd=ROOT,timeout=120,memory_mib=384)
            mutants=read_json(Path(directory)/'mutants.json')
    rows=[rows[case['name']] for case in baseline]
    if any(len(row['boundaries'])!=4 or
           {(b['full'],b['core']) for b in row['boundaries']}!={(False,False),(False,True),(True,False),(True,True)}
           for row in rows):fail('Incomplete selector boundary campaign')
    if not set(prefix.LOCAL)<={p for row in rows for p in row['sites']}:fail('Missing selector caller instruction sites')
    if not prefix.EDGES<={tuple(edge) for row in rows for edge in row['edges']}:fail('Missing selector caller branch edges')
    if before!=input_hashes(native_enabled):fail('Selector campaign inputs changed')
    report=dict(image='main',image_sha256=sha(prefix.decoder.IMAGE),case_count=len(rows),boundaries_per_case=4,cases=rows,
        mutation_count=len(mutants),mutations_detected=mutants,caller_sites=len(prefix.LOCAL),translated_code_bytes=253,
        executed_instruction_addresses=sorted({p for row in rows for p in row['sites']}),branch_edges=sorted({tuple(e) for row in rows for e in row['edges']}),
        input_hashes=before,c_coverage_claimed=native_enabled,
        limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,instructions_per_original=10000000,prefix_services=512,suffix_services=64,suffix_model_accesses=1024,workers_concurrent=1),
        domain='197D RAM prefix with narrow preserving DOS/retry seams and intact internal DAT returns; eight live immediate child returns; separate1A59/1A7A boundaries; direct1949/04D0 logical fatal tails with all-state providers, no CALL or unwind; quiescentIRQ/intactcode/sameCS/TFclear. No general raster-bus claim.')
    write_json(REPORT if native_enabled else ORIGINAL_REPORT,report)
    print(f'PASS selector full {"C" if native_enabled else "original"}: {len(rows)} cases x4 boundaries,108 caller/{len(report["executed_instruction_addresses"])} integrated sites; {len(mutants)} completed mutants',flush=True)


def main():
    if len(sys.argv)==5 and sys.argv[1] in ('--native-chunk','--original-chunk'):
        worker(sys.argv[2],list(map(int,sys.argv[3].split(','))),None if sys.argv[4]=='all' else int(sys.argv[4]),native_enabled=sys.argv[1]=='--native-chunk');return
    if len(sys.argv)==3 and sys.argv[1]=='--mutants':mutation_worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        campaign(False);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected selector full arguments')
    BUILD.mkdir(exist_ok=True);REPORT.unlink(missing_ok=True)
    campaign(True)
if __name__=='__main__':main()
