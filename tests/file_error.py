"""Original/model/C file error printer with live DOS pointers and cleanup tail."""
import ctypes
import gc
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INTR)
from unicorn import x86_const as x
import fatal_cleanup as cleanup
import video_restore as common
import vector_restore as vectors
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import ROOT,BUILD,sha,write_json
from dat_io_c import MEM,Regs
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes())
START,END=0x1949,0x197d
CODE=bytes.fromhex('52baa9098edae8a6f65ab409cd21b402b220cd218b1e28258a1722d2740743b402cd21ebf3b20db402cd21b20ab402cd21e96deb')
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for a,b in ((START,END),(0xff8,0x1007),(0x4ea,0x4f9),(0x1582,0x1592)) for i in MD.disasm(IMAGE[a:b],a)}
CALLS={0x194f:(0xff8,0x1952),0x4ea:(0x1582,0x4ed)}
REGS,FIELDS,FULL,LOGIC=common.REGS,common.FIELDS,common.FULL,common.LOGIC
State,RETURN=common.State,vectors.VECTOR
REPORT=BUILD/'file-error-differential.json';ORIGINAL_REPORT=BUILD/'file-error-contract-original.json'
SIZE=1<<20


class Services(ctypes.Structure):
    _fields_=[('video',ctypes.POINTER(common.Services)),('cleanup',ctypes.POINTER(cleanup.Services)),
              ('context',ctypes.c_void_p),('write_message',RETURN),('write_character',RETURN)]


class NativeMismatch(AssertionError):pass
def oracle_fail(message):raise common.fixture.VerificationFailure(message)
def native_fail(message):raise NativeMismatch(message)


def cases():
    rows=[dict(name=f'filename-byte-{n:02x}',seed=n,byte=n,suffix=True,gate=0) for n in range(256)]
    for kind in ('saved-dx-overwrite','changed-video-return','video-stack-ffff','video-stack-a20',
                 'push-sp-zero','push-sp-one','filename-bx-ffff','filename-ds-a20','returned-ds-bx',
                 'space-pointer','long-name','vga-page','vga-stack','vga-filename','vga-message'):
        rows.append(dict(name=kind,kind=kind,seed=len(rows),byte=65,suffix=True,gate=0))
    for load in common.LOADS:
        for missing in ('none','video','mode','page','message','character','cleanup','cleanup-vector','cleanup-message','terminate'):
            rows.append(dict(name=f'missing-{missing}-{load:04x}',missing=missing,seed=len(rows),byte=65,suffix=True,gate=0,load=load))
    for row in rows:
        row.setdefault('load',common.LOADS[row['seed']%3])
        row['length']=(3 if row.get('kind') in ('returned-ds-bx','space-pointer') else
                       24 if row.get('kind')=='long-name' else 1 if row['byte'] else 0)
    return rows


def string(memory,segment,offset,value):
    for n,byte in enumerate(value):memory[common.physical(segment,(offset+n)&65535)]=byte


def prepare(case):
    memory,initial=cleanup.prepare(case)
    main=(case['load']+0x9a9)&65535
    initial.update(dx=0x2300)
    kind=case.get('kind')
    if kind=='push-sp-zero':initial['sp']=0
    if kind=='push-sp-one':initial['sp']=1
    if kind=='vga-stack':initial['ss']=0xa000
    filename=(b'ABC' if kind=='returned-ds-bx' else b'new' if kind=='space-pointer' else
              b'abcdefghijklmnopqrstuvwx' if kind=='long-name' else bytes((case['byte'],)) if case['byte'] else b'')
    for ds in (main,0x3000,0x3400,0x3500,0x3600,0x3700,0x4200,0xffff):
        memory[common.physical(ds,0x1fe1)]=3;memory[common.physical(ds,0x1fe2)]=7
        common.putword(memory,ds,0x2528,0x8800 if ds==0x3500 else 0x9000)
        common.putword(memory,ds,0x1fba,0x4411);common.putword(memory,ds,0x1fbc,0x5511)
        string(memory,ds,0x2300,b'file error$\0');string(memory,ds,0x2400,b'changed error$\0')
        string(memory,ds,0x8800,b'old\0' if kind=='space-pointer' else filename+b'\0')
        string(memory,ds,0x9000,filename+b'\0')
        string(memory,ds,0x20ac,b'exit after file error$')
    if kind=='space-pointer':string(memory,0x3600,0x8800,b'bad\0')
    if kind=='returned-ds-bx':string(memory,0x3700,0x9000,b'xy\0')
    if kind=='filename-bx-ffff':
        common.putword(memory,0x3600,0x2528,0xffff);string(memory,0x3600,0xffff,b'A\0')
    return memory,initial


def device(memory,case):
    backend=cleanup.device(memory,case)
    common.putword(backend.vga.planes[2],0,0x2528,0x9000)
    string(backend.vga.planes[2],0,0x9000,bytes((case['byte'],0)))
    string(backend.vga.planes[2],0,0x2300,b'VGA error$\0');string(backend.vga.planes[2],0,0x2400,b'VGA changed$\0')
    common.putword(backend.vga.planes[2],0,0x7ffc,0x1952)
    common.putword(backend.vga.planes[2],0,0x7ffe,0x2400)
    return backend


class Environment(cleanup.Environment):
    def __init__(self,case,backend):
        super().__init__(case,backend);self.characters=[];self.character_calls=0
    def invoke(self,key,incoming,mask):
        if len(self.calls)>=64:oracle_fail('File-error service budget exhausted')
        case,kind=self.case,self.case.get('kind');changed=[]
        if key in cleanup.KEYS:
            if key=='terminate':
                out=dict(incoming);self.backend.memory[0x90000]=0x4c;changed=[0x90000]
            else:out,changed=self.effect(key,incoming)
        else:
            rng=random.Random(0x194900+case['seed']*113+len(self.calls))
            out={k:rng.randrange(65536) for k in REGS}
            out.update(ds=incoming['ds'],ss=incoming['ss'],sp=incoming['sp'],bx=incoming['bx'],
                       flags=2|((case['seed']*0x59+len(self.calls)*0x97)&0xed5))
            writes=[]
            if key in ('error-mode','error-page'):
                out.update(ds=0x3400 if key=='error-mode' else 0x3500,ss=0x7500,sp=0x8200 if key=='error-mode' else 0x8400)
                if key=='error-mode' and kind=='vga-page':out['ds']=0xa000
                if key=='error-page' and kind=='vga-message':out['ds']=0xa000
                if key=='error-page' and kind=='video-stack-ffff':out.update(ss=0x7600,sp=0xffff)
                if key=='error-page' and kind=='video-stack-a20':out.update(ss=0xffff,sp=0xf)
                saved=[];p=common.physical(incoming['ss'],(incoming['sp']+2)&65535)
                for n in range(2):saved.append(self.backend.vga.read(self.backend.memory,(p+n)&0xfffff,incoming['flags']))
                message=saved[0]|saved[1]<<8
                if key=='error-page' and kind=='saved-dx-overwrite':message=0x2400
                writes=[(out['ss'],out['sp'],0xdead if kind=='changed-video-return' and key=='error-page' else 0x1952),
                        (out['ss'],(out['sp']+2)&65535,message)]
            if key=='file-message':out['ds']=0x3500
            if key=='space':out.update(ds=0xffff if kind=='filename-ds-a20' else 0xa000 if kind=='vga-filename' else 0x3600,bx=0x7777)
            if key=='character' and kind=='returned-ds-bx' and self.character_calls==2:out.update(ds=0x3700,bx=0x9000)
            if key=='cr':out.update(ds=0x3700,ss=0x7800,sp=0x8500)
            if key=='lf':out.update(ds=0x4200,ss=0x7900,sp=0x8600)
            for seg,off,value in writes:
                common.putword(self.backend.memory,seg,off,value);p=common.physical(seg,off);changed.extend((p,(p+1)&0xfffff))
        if key in ('message','file-message'):
            data=[]
            for n in range(64):
                value=self.backend.vga.read(self.backend.memory,common.physical(incoming['ds'],(incoming['dx']+n)&65535),incoming['flags'])
                if value==36:break
                data.append(value)
            else:oracle_fail('File-error DOS09 string budget exhausted')
            self.payloads.append(bytes(data).hex())
        if key in ('space','character','cr','lf'):self.characters.append(incoming['dx']&255)
        self.calls.append((key,dict(incoming),dict(out),mask));return out,changed
    def character_key(self):
        count=self.character_calls;self.character_calls+=1
        return 'space' if count==0 else 'character' if count<=self.case['length'] else 'cr' if count==self.case['length']+1 else 'lf'


def stop_pc(case):
    return {'none':0xffd,'video':0xffd,'mode':0xffd,'page':0x1004,'message':0x1955,
            'character':0x195b,'cleanup':0x158e,'cleanup-vector':0x158e,
            'cleanup-message':0x4f2,'terminate':0x4f7}.get(case.get('missing'))


def model(case,memory,initial,*,backend=None,environment=None):
    backend=device(memory,case) if backend is None else backend
    env=Environment(case,backend) if environment is None else environment
    s=dict(initial);mask=FULL;sites=set();edges=set()
    def mark(pc):sites.add(pc)
    def readword(seg,off):
        p=common.physical(seg,off);values=[]
        for n in range(2):
            address=(p+n)&0xfffff;value=backend.vga.read(backend.memory,address,s['flags'])
            backend.events.add('read',address,value,s['flags'],mask);values.append(value)
        return values[0]|values[1]<<8
    def readbyte(seg,off):
        p=common.physical(seg,off);v=backend.vga.read(backend.memory,p,s['flags']);backend.events.add('read',p,v,s['flags'],mask);return v
    def push(value):
        s['sp']=(s['sp']-2)&65535;p=common.physical(s['ss'],s['sp'])
        for n in range(2):
            address=(p+n)&0xfffff;v=(value>>(n*8))&255
            backend.vga.write(backend.memory,address,v,s['flags']);backend.events.add('write',address,v,s['flags'],mask)
    def pop():v=readword(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535;return v
    def service(pc,key):
        nonlocal s,mask
        if pc==stop_pc(case):raise cleanup.Boundary(pc,1)
        mark(pc);s,_=env.invoke(key,s,mask);mask=FULL
    try:
        mark(0x1949);push(s['dx']);mark(0x194a);s['dx']=(case['load']+0x9a9)&65535
        mark(0x194d);s['ds']=s['dx'];mark(0x194f);push(0x1952)
        mark(0xff8);s['ax']=(s['ax']&0xff00)|readbyte(s['ds'],0x1fe1)
        mark(0xffb);s['ax']&=255;s['flags']=(s['flags']&~0x8c5)|0x44;mask=LOGIC
        service(0xffd,'error-mode');mark(0xfff);s['ax']=(s['ax']&255)|0x500
        mark(0x1001);s['ax']=(s['ax']&0xff00)|readbyte(s['ds'],0x1fe2);service(0x1004,'error-page');mark(0x1006)
        target=pop()
        if target!=0x1952:raise cleanup.Boundary(target,2)
        mark(0x1952);s['dx']=pop();mark(0x1953);s['ax']=(s['ax']&255)|0x900;service(0x1955,'file-message')
        mark(0x1957);s['ax']=(s['ax']&255)|0x200;mark(0x1959);s['dx']=(s['dx']&0xff00)|0x20
        service(0x195b,env.character_key());mark(0x195d);s['bx']=readword(s['ds'],0x2528)
        iterations=0
        while True:
            iterations+=1
            if iterations>64:oracle_fail('File-error model loop budget exhausted')
            mark(0x1961);value=readbyte(s['ds'],s['bx']);s['dx']=(s['dx']&0xff00)|value
            mark(0x1963);s['flags']=(s['flags']&~0x8c5)|(4 if not value.bit_count()&1 else 0)|(0x40 if value==0 else 0)|(0x80 if value&128 else 0);mask=LOGIC
            mark(0x1965);edges.add((0x1965,0x196e if value==0 else 0x1967))
            if value==0:break
            mark(0x1967);old=s['bx'];s['bx']=(old+1)&65535;v=s['bx']
            s['flags']=(s['flags']&~0x8d4)|(4 if not (v&255).bit_count()&1 else 0)|(0x10 if old&15==15 else 0)|(0x40 if v==0 else 0)|(0x80 if v&0x8000 else 0)|(0x800 if old==0x7fff else 0);mask=FULL
            mark(0x1968);s['ax']=(s['ax']&255)|0x200;service(0x196a,env.character_key());mark(0x196c);edges.add((0x196c,0x1961))
        mark(0x196e);s['dx']=(s['dx']&0xff00)|13;mark(0x1970);s['ax']=(s['ax']&255)|0x200;service(0x1972,env.character_key())
        mark(0x1974);s['dx']=(s['dx']&0xff00)|10;mark(0x1976);s['ax']=(s['ax']&255)|0x200;service(0x1978,env.character_key())
        mark(0x197a);edges.add((0x197a,0x4ea))
        tail=dict(case,missing={'cleanup':'no-services','cleanup-vector':'vectors','cleanup-message':'message','terminate':'terminate'}.get(case.get('missing')))
        _,state,_,target,status,tailmask,childsites,childedges=cleanup.model(tail,backend.memory,s,backend=backend,environment=env)
        return backend,state,env,target,status,tailmask,sites|childsites,edges|childedges
    except cleanup.Boundary as boundary:return backend,s,env,boundary.target,boundary.status,mask,sites,edges


def original(case,memory,initial):
    backend=device(memory,case);env=Environment(case,backend);cpu=Uc(UC_ARCH_X86,UC_MODE_16)
    cpu.mem_map(0,SIZE*2);cpu.mem_write(0,bytes(backend.memory)*2)
    for key,value in dict(initial,cs=case['load'],ip=START).items():cpu.reg_write(x.UC_X86_REG_EFLAGS if key=='flags' else common.drawing.oracle.REG[key],value)
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load'])
    values={(case['load']<<4)+p+n:loaded[p+n] for p,ins in INS.items() for n in range(ins.size)}
    if any(backend.memory[p]!=v for p,v in values.items()):oracle_fail('File error entered modified code')
    mask,event_flags,previous,pending,status,done,steps=FULL,initial['flags'],None,None,None,False,0
    stack,sites,edges,failure=[],set(),set(),[]
    def fail(error):
        if not failure:failure.append(str(error))
        cpu.emu_stop()
    def sync(addresses):
        for p in addresses:
            v=bytes((backend.memory[p],));cpu.mem_write(p,v);cpu.mem_write(p+SIZE,v)
        if any(backend.memory[p]!=v for p,v in values.items()):oracle_fail('File-error provider modified decoded code')
    def code(uc,_pc,_size,_user):
        nonlocal mask,event_flags,previous,pending,status,done,steps
        if previous in (0xffb,0x1963):mask=LOGIC
        if previous==0x1967:mask=FULL
        off,cs=uc.reg_read(x.UC_X86_REG_IP),uc.reg_read(x.UC_X86_REG_CS)
        if pending is not None:
            expected=pending;pending=None
            if not stack or stack.pop()!=expected:fail('Unknown file error return frame');return
            if off!=expected or cs!=case['load']:done,status=True,2;uc.emu_stop();return
        if previous in (0x1965,0x196c,0x197a):edges.add((previous,off))
        if cs!=case['load'] or off not in INS:fail(f'File error escaped {cs:04x}:{off:04x}');return
        if off==stop_pc(case):done,status=True,1;uc.emu_stop();return
        steps+=1
        if steps>512:fail('File-error instruction budget exhausted');return
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS);previous=off;sites.add(off)
        if off in CALLS:stack.append(CALLS[off][1])
        if INS[off].mnemonic=='ret':
            if not stack:fail('Forbidden file-error outer RET');return
            pending=stack[-1]
    def read(uc,_a,address,size,_value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=backend.vga.read(backend.memory,p,event_flags)
                backend.events.add('read',p,v,event_flags,mask);uc.mem_write(address+n,bytes((v,)))
            backend.check('file-error original read')
        except BaseException as error:fail(error)
    def write(_uc,_a,address,size,value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=(value>>(n*8))&255
                if p in values and values[p]!=v:oracle_fail('File error wrote decoded code')
                backend.vga.write(backend.memory,p,v,event_flags);backend.events.add('write',p,v,event_flags,mask);sync((p,))
            backend.check('file-error original write')
        except BaseException as error:fail(error)
    def interrupt(uc,number,_user):
        nonlocal mask,done,status
        try:
            key={0xffd:'error-mode',0x1004:'error-page',0x1955:'file-message',0x158e:'keyboard2',0x4f2:'message',0x4f7:'terminate'}.get(previous)
            if previous in (0x195b,0x196a,0x1972,0x1978):key=env.character_key()
            if key is None or number!=(0x10 if key in ('error-mode','error-page') else 0x21):oracle_fail('Unexpected file-error interrupt')
            incoming={k:uc.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in REGS}
            out,changed=env.invoke(key,incoming,mask);sync(changed)
            if key=='terminate':done,status=True,0;uc.emu_stop();return
            for k in REGS:uc.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],out[k])
            mask=FULL
        except BaseException as error:fail(error)
    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write);cpu.hook_add(UC_HOOK_INTR,interrupt)
    cpu.emu_start((case['load']<<4)+START,0,count=513)
    if failure:oracle_fail(case['name']+':'+failure[0])
    if not done:oracle_fail('File error did not finish')
    regs={k:cpu.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in (*REGS,'cs','ip')}
    return backend,regs,env,regs['ip'],status,mask,sites,edges


def equal_env(actual,expected,fail,label):
    common.equal_calls(actual.calls,expected.calls,fail,label)
    if (actual.payloads,actual.characters)!=(expected.payloads,expected.characters):fail(label+' printed live bytes differ')


def original_case(case):
    memory,initial=prepare(case);expected,state,env,target,status,mask,sites,edges=model(case,memory,initial)
    backend,regs,observed,got_target,got_status,got_mask,got_sites,got_edges=original(case,memory,initial)
    common.equal_state(regs,state,mask,oracle_fail,case['name']+' model');common.equal_device(backend,expected,oracle_fail,case['name']+' model');equal_env(observed,env,oracle_fail,case['name']+' model')
    if (got_target,got_status,got_mask,got_sites,got_edges,regs['cs'])!=(target,status,mask,sites,edges,case['load']):oracle_fail(case['name']+' original boundary/site coverage differs')
    return memory,initial,backend,regs,observed,target,status,mask,sites,edges


def native_services(case,backend,*,environment=None):
    env=Environment(case,backend) if environment is None else environment
    refs=[]
    def callback(key):
        @RETURN
        def function(_ctx,_memory,incoming,outgoing):
            if len(env.calls)>=64:common.fixture.exit_worker(86,'File-error provider budget exhausted')
            try:
                actual=env.character_key() if key=='character-output' else key
                out,_=env.invoke(actual,common.state_dict(incoming[0]),LOGIC if actual in ('error-mode','cr') else FULL)
                for field,k in zip(FIELDS,REGS):setattr(outgoing[0],field,out[k])
            except BaseException as error:common.fixture.exit_worker(87,f'File-error callback:{error}')
        refs.append(function);return function
    @cleanup.TERMINATE
    def terminate(_ctx,_memory,incoming):
        if len(env.calls)>=64:common.fixture.exit_worker(86,'File-error terminal budget exhausted')
        try:env.invoke('terminate',common.state_dict(incoming[0]),FULL)
        except BaseException as error:common.fixture.exit_worker(87,f'File-error terminal:{error}')
    missing=case.get('missing')
    if missing=='none':return None,env,(refs,terminate)
    video=common.Services(None,RETURN() if missing=='mode' else callback('error-mode'),RETURN() if missing=='page' else callback('error-page'))
    vector=vectors.Services(None,RETURN() if missing=='cleanup-vector' else callback('keyboard2'))
    tail=cleanup.Services(None,ctypes.pointer(vector),None,None,RETURN(),RETURN() if missing=='cleanup-message' else callback('message'),cleanup.TERMINATE() if missing=='terminate' else terminate)
    service=Services(None if missing=='video' else ctypes.pointer(video),None if missing=='cleanup' else ctypes.pointer(tail),None,
                     RETURN() if missing=='message' else callback('file-message'),RETURN() if missing=='character' else callback('character-output'))
    return service,env,(refs,terminate,video,vector,tail)


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'file-error-m{mutation}.dll',mutation,'file_error')))
        self.core=self.lib.lmn_file_error_core;self.core.argtypes=[MEM,ctypes.c_uint16,ctypes.POINTER(State),ctypes.POINTER(Services),ctypes.POINTER(common.fixture.RasterBus)];self.core.restype=cleanup.Result
        self.adapter=self.lib.lmn_file_error_adapter;self.adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Services),ctypes.POINTER(common.fixture.RasterBus)]


def compare(native,case):
    memory,initial,expected,regs,env,target,status,mask,sites,edges=original_case(case);vga=case.get('kind','').startswith('vga-')
    for core in (False,True):
        for null in (False,True):
            if null and vga:continue
            backend=device(memory,case);services,observed,refs=native_services(case,backend);bus=None if null else ctypes.byref(backend.bus)
            label=case['name']+(' core' if core else ' adapter')
            if core:
                state=common.to_state(initial);out=native.core(common.buffer(backend.memory),(case['load']+0x9a9)&65535,ctypes.byref(state),common.pointer(services),bus)
                current=common.state_dict(out.state)
                if (out.continuation,out.status)!=(target,status):native_fail(label+' boundary/status differs')
            else:
                r=Regs(**{k:v for k,v in initial.items() if k!='flags'},cs=case['load'],ip=START,flags=initial['flags'])
                native.adapter(common.buffer(backend.memory),ctypes.byref(r),common.pointer(services),bus);current={k:getattr(r,k) for k in REGS}
                if (r.cs,r.ip)!=(case['load'],target):native_fail(label+' ip/cs differs')
            common.equal_state(current,regs,mask,native_fail,label);equal_env(observed,env,native_fail,label)
            if null:
                if backend.memory!=expected.memory:native_fail(label+' null RAM differs')
            else:common.equal_device(backend,expected,native_fail,label)
    return dict(name=case['name'],vga=vga,status=status,target=target,sites=sorted(sites),edges=sorted(edges))


def input_hashes(native=False):
    paths=set(cleanup.input_hashes(native));paths.update(('tests/file_error.py','docs/file-error.md'))
    if native:paths.update(('c/file_error.c','c/file_error.h'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before=input_hashes();rows=[];sites=set();edges=set()
    if sha(ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d' or sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or IMAGE[START:END]!=CODE:oracle_fail('Pinned file error image changed')
    if not any(r['linear']==0x194b for r in ORACLE['relocations']):oracle_fail('File error segment operand relocation missing')
    for case in cases():
        r=original_case(case);rows.append(case['name']);sites.update(r[-2]);edges.update(r[-1]);gc.collect()
    if len(INS)!=45 or sites!=set(INS) or edges!={(0x1965,0x1967),(0x1965,0x196e),(0x196c,0x1961),(0x197a,0x4ea)}:oracle_fail('File error integrated site/edge coverage differs')
    if before!=input_hashes():oracle_fail('File error original inputs changed')
    write_json(ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),cases=rows,caller_sites=25,caller_bytes=52,integrated_bytes=98,executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),c_coverage_claimed=False,input_hashes=before))
    print(f'PASS file error original:{len(rows)} cases,25 caller/45 integrated sites,4 edges;no C coverage',flush=True)


def worker(directory=None):
    common.fixture.MAX_BUS_EVENTS=512;common.fixture.MAX_VGA_EVENTS=512
    before=input_hashes(directory is not None);original_phase()
    if directory is None:return
    native=Native(directory);specs=cases();rows=[]
    for case in specs:rows.append(compare(native,case));gc.collect()
    mutants=[]
    for number,name in ((1,'saved-dx-overwrite'),(2,'space-pointer'),(3,'returned-ds-bx'),(4,'filename-byte-41')):
        variant=Native(directory,number);case=next(c for c in specs if c['name']==name)
        try:compare(variant,case)
        except NativeMismatch as error:mutants.append(dict(mutation=number,case=name,mismatch=str(error),completed=True))
        else:oracle_fail(f'File error mutant{number} survived')
        gc.collect()
    if before!=input_hashes(True):oracle_fail('File error native inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),auxiliary_core_cases=len(rows),null_bus_adapter_cases=sum(not r['vga'] for r in rows),cases=rows,mutation_count=4,mutations=mutants,translated_code_bytes=52,native_code_ranges=[[START,END]],caller_instruction_sites=25,executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),branch_edges=sorted({tuple(e) for r in rows for e in r['edges']}),input_hashes=before,limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_instructions=512,bus_events=512,service_calls=64,string_bytes=64),domain='Pinned1949 printer/video/04EA tail through direct logical cores; loaded194Bsegment operand; explicit returning DOS/BIOS and terminalDOS providers; allstate/RAM/VGA/order; intactcode/sameCS/TFclear/quiescentIRQ.'))
    print(f'PASS file error C:{len(rows)} adapter+core cases,25 caller/45 integrated sites,4 completed mutants',flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True);run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected file error arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='file-error-',parent=BUILD) as directory:run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)


if __name__=='__main__':main()
