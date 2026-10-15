"""Pinned full/suffix cleanup executions, independent model, and direct C composition."""
import ctypes
import gc
import random
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'), str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_READ,
                     UC_HOOK_MEM_WRITE, UC_HOOK_INSN, UC_HOOK_INTR)
from unicorn import x86_const as x
import video_restore as common
import timer_restore as timer
import vector_restore as vectors
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
CODE = bytes.fromhex('e8d611e8ac10e8c70ae81c0b803e731fff7407b80c0033c9cd33e89510baac20b409cd21b8004ccd21')
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
RANGES = ((0x4d0,0x4f9),(0x16a9,0x16d4),(0x1582,0x1592),(0xfa0,0xfb2),(0xff8,0x1007))
INS = {i.address:i for a,b in RANGES for i in MD.disasm(IMAGE[a:b],a)}
CALLS = {0x4d0:(0x16a9,0x4d3),0x4d3:(0x1582,0x4d6),0x4d6:(0xfa0,0x4d9),
         0x4d9:(0xff8,0x4dc),0x4ea:(0x1582,0x4ed)}
RETURNS = {'clock':0x4d3,'keyboard1':0x4d6,'private':0x4d9,'mode':0x4dc,'page':0x4dc,'keyboard2':0x4ed}
INTERRUPTS = {0x16d1:'clock',0xfae:'private',0xffd:'mode',0x1004:'page',
              0x4e8:'mouse',0x4f2:'message',0x4f7:'terminate'}
KEYS = ('clock','keyboard1','private','mode','page','mouse','keyboard2','message','terminate')
REGS, FIELDS, FULL, LOGIC = common.REGS, common.FIELDS, common.FULL, common.LOGIC
State, RETURN = common.State, vectors.VECTOR
TERMINATE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.POINTER(State))
SIZE = 1 << 20
REPORT = BUILD/'fatal-cleanup-differential.json'
ORIGINAL_REPORT = BUILD/'fatal-cleanup-contract-original.json'


class Services(ctypes.Structure):
    _fields_ = [('timer',ctypes.POINTER(timer.Services)),('vectors',ctypes.POINTER(vectors.Services)),
                ('video',ctypes.POINTER(common.Services)),('context',ctypes.c_void_p),
                ('disable_mouse',RETURN),('write_message',RETURN),('terminate',TERMINATE)]


class Result(ctypes.Structure):
    _fields_ = [('state',State),('continuation',ctypes.c_uint16),('status',ctypes.c_int)]


class NativeMismatch(AssertionError): pass
class Boundary(Exception):
    def __init__(self,target,status): self.target,self.status=target,status
def oracle_fail(message): raise common.fixture.VerificationFailure(message)
def native_fail(message): raise NativeMismatch(message)


def cases():
    rows=[dict(name=f'full-mouse-gate-{n:02x}',seed=n,gate=n,suffix=False) for n in range(256)]
    rows += [dict(name=f'suffix-{n:02x}',seed=len(rows)+n,gate=n,suffix=True) for n in range(32)]
    kinds=('timer-ivt-return','timer-push-vector','timer-push-sp-zero','timer-push-sp-one',
           'timer-a20','vector-ivt-update','changed-clock','changed-keyboard1','changed-private',
           'changed-page','changed-keyboard2','page-writes-gate','mode-live-page','mouse-live-stack',
           'message-live-ds','message-stack-ffff','message-stack-a20','provider-message-write',
           'vga-vector','vga-stack','vga-return','vga-gate','ds-a20')
    for kind in kinds: rows.append(dict(name=kind,kind=kind,seed=len(rows),gate=0,suffix=False))
    for kind in ('changed-keyboard2','message-live-ds','message-stack-ffff','message-stack-a20','provider-message-write','vga-message'):
        rows.append(dict(name='suffix-'+kind,kind=kind,seed=len(rows),gate=0,suffix=True))
    for suffix in (False,True):
        missing=('no-services','vectors','message','terminate') if suffix else (
            'no-services','timer','port','clock','vectors','video','mode','page','mouse','message','terminate')
        for load in common.LOADS:
            for key in missing:
                rows.append(dict(name=f'{"suffix" if suffix else "full"}-missing-{key}-{load:04x}',
                                 seed=len(rows),suffix=suffix,gate=0,missing=key,load=load))
    for row in rows: row.setdefault('load',common.LOADS[row['seed']%3])
    return rows


def prepare(case):
    rng=random.Random(0x4d0+case['seed'])
    memory=bytearray(rng.randbytes(SIZE))
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load'])
    memory[case['load']<<4:(case['load']<<4)+len(loaded)]=loaded
    state={k:rng.randrange(65536) for k in REGS}
    state.update(ds=0x3000,ss=0x7000,sp=0x8000,es=0x6200,
                 flags=2|((case['seed']*0x95)&0xed5))
    kind=case.get('kind')
    if kind=='timer-ivt-return': state.update(ss=0,sp=0x22)
    if kind=='timer-push-vector': state.update(ss=state['ds'],sp=0x1fc2)
    if kind=='timer-push-sp-zero': state['sp']=0
    if kind=='timer-push-sp-one': state['sp']=1
    if kind=='timer-a20': state.update(ss=0xffff,sp=0x13)
    if kind=='ds-a20': state['ds']=0xffff
    if kind in ('vga-stack','vga-return'): state['ss']=0xa000
    for ds in (0x3000,0x3100,0x3400,0x3500,0x3600,0x3800,0x4200,0xffff):
        for p,v in ((0x1fba,0x4411),(0x1fbc,0x5511),(0x1fbe,0x4422),(0x1fc0,0x5522),
                    (0x1fc2,0x4433),(0x1fc4,0x5533),(0x259c,0x1234),(0x259e,0xabcd)):
            common.putword(memory,ds,p,v)
        for p,v in ((0x1fc6,case['seed']&255),(0x1fe1,3),(0x1fe2,7),(0x1f73,case['gate'])):
            memory[common.physical(ds,p)]=v
        text=(f'live exit {ds:04x}/{case["seed"]:03d}\r\n$').encode()
        start=common.physical(ds,0x20ac)
        for n,value in enumerate(text): memory[(start+n)&0xfffff]=value
    memory[common.physical(state['ds'],0x1f73)]=case['gate']^255
    common.putword(memory,state['ss'],state['sp'],0xeedd)
    return memory,state


def device(memory,case):
    backend=common.fixture.TraceDevice(bytearray(memory),0x4d000+case['seed'],read_map=2)
    backend.vga.seq[2]=1
    for p,v in ((0x1fba,0x4411),(0x1fbc,0x5511),(0x1fc2,0x4433),(0x1fc4,0x5533),
                (0x7ffc,0x3000),(0x7ffe,0xdead)):
        common.putword(backend.vga.planes[2],0,p,v)
    backend.vga.planes[2][0x1fc6]=0x74
    backend.vga.planes[2][0x1fe1]=0x13
    backend.vga.planes[2][0x1fe2]=9
    backend.vga.planes[2][0x1f73]=case['gate']
    text=b'VGA-backed exit$'
    backend.vga.planes[2][0x20ac:0x20ac+len(text)]=text
    return backend


def word(memory,segment,offset):
    p=common.physical(segment,offset)
    return memory[p]|memory[(p+1)&0xfffff]<<8


class Environment:
    """Declared deterministic providers; no original DOS/BIOS implementation is assumed."""
    def __init__(self,case,backend): self.case,self.backend,self.calls,self.ports,self.payloads=case,backend,[],[],[]
    def effect(self,key,incoming):
        case,kind=self.case,self.case.get('kind')
        index=KEYS.index(key)
        rng=random.Random(0x4d000+case['seed']*101+index)
        out={k:rng.randrange(65536) for k in REGS}
        out.update(ds={'clock':0x3100,'mode':0x3400,'page':0x3500,'mouse':0x3600,'message':0x3800}.get(key,0x5100),
                   es=0x6300+index*0x10,ss=incoming['ss'],sp=incoming['sp'],
                   flags=2|((case['seed']*0x59+index*0x97)&0xed5))
        moved=bool((case['seed']+index)&1)
        if key in ('mouse','message') or moved: out.update(ss=0x7100+index*0x80,sp=0x8100+index*0x40)
        if kind in ('timer-ivt-return','vga-return') and key=='clock': out.update(ss=incoming['ss'],sp=incoming['sp'])
        if kind=='vga-vector' and key=='clock': out['ds']=0xa000
        if kind=='vga-gate' and key=='page': out['ds']=0xa000
        if kind=='vector-ivt-update' and key=='clock': out.update(ss=0,sp=0x26)
        if kind=='vector-ivt-update' and key=='keyboard1': out.update(ss=incoming['ss'],sp=incoming['sp'])
        if kind=='mouse-live-stack' and key=='mouse': out.update(ss=0xffff,sp=1)
        if kind=='message-stack-ffff' and key=='message': out.update(ss=0x7800,sp=0xffff)
        if kind=='message-stack-a20' and key=='message': out.update(ss=0xffff,sp=0xf)
        writes=[]
        if key in ('keyboard1','private','keyboard2'):
            saved=word(self.backend.memory,incoming['ss'],incoming['sp'])
            if (out['ss'],out['sp'])!=(incoming['ss'],incoming['sp']):
                writes.extend(((out['ss'],out['sp'],saved),(out['ss'],(out['sp']+2)&65535,RETURNS[key])))
            if key=='keyboard2' and kind in ('message-live-ds','vga-message'):
                writes.append((out['ss'],out['sp'],0xa000 if kind=='vga-message' else 0x4200))
        elif key in RETURNS and (out['ss'],out['sp'])!=(incoming['ss'],incoming['sp']):
            writes.append((out['ss'],out['sp'],RETURNS[key]))
        if kind=='changed-'+key:
            writes.append((out['ss'],(out['sp']+2)&65535 if key in ('keyboard1','private','keyboard2') else out['sp'],0xdead))
        if kind=='vector-ivt-update' and key=='keyboard1':
            writes.extend(((0,0x24,incoming['dx']),(0,0x26,incoming['ds'])))
        if kind=='provider-message-write' and key=='keyboard2':
            segment=word(self.backend.memory,out['ss'],out['sp'])
            for n,value in enumerate(b'Changed by final keyboard$'):
                self.backend.memory[(common.physical(segment,0x20ac)+n)&0xfffff]=value
        changed=[]
        for seg,off,value in writes:
            common.putword(self.backend.memory,seg,off,value)
            p=common.physical(seg,off);changed.extend((p,(p+1)&0xfffff))
        if kind=='provider-message-write' and key=='keyboard2':
            changed.extend((common.physical(segment,0x20ac)+n)&0xfffff for n in range(26))
        if kind=='page-writes-gate' and key=='page':
            p=common.physical(out['ds'],0x1f73);self.backend.memory[p]=255;changed.append(p)
        if kind=='mode-live-page' and key=='mode':
            p=common.physical(out['ds'],0x1fe2);self.backend.memory[p]=0x7f;changed.append(p)
        return out,changed
    def invoke(self,key,incoming,mask):
        if len(self.calls)>=9: oracle_fail('Cleanup provider budget exhausted')
        if key=='terminate':
            out,changed=dict(incoming),[]
            self.backend.memory[0x90000]=0x4c;changed=[0x90000]
        else: out,changed=self.effect(key,incoming)
        if key=='message':
            payload=[]
            for n in range(64):
                value=self.backend.vga.read(self.backend.memory,common.physical(incoming['ds'],(incoming['dx']+n)&65535),incoming['flags'])
                if value==36: break
                payload.append(value)
            else: oracle_fail('DOS09 fixture string budget exhausted')
            self.payloads.append(bytes(payload).hex())
        self.calls.append((key,dict(incoming),dict(out),mask))
        return out,changed
    def port(self,port,value,flags,mask):
        if len(self.ports)>=3: oracle_fail('Cleanup port budget exhausted')
        self.ports.append((port,value,flags,mask))
        self.backend.events.add('out',port,value,flags,mask)


def missing_pc(case):
    key=case.get('missing')
    if key=='no-services': return 0x158e if case['suffix'] else 0x16ad
    return {'timer':0x16ad,'port':0x16ad,'clock':0x16d1,'vectors':0x158e,
            'video':0xffd,'mode':0xffd,'page':0x1004,'mouse':0x4e8,
            'message':0x4f2,'terminate':0x4f7}.get(key)


def model(case,memory,initial,*,backend=None,environment=None):
    backend=device(memory,case) if backend is None else backend
    env=Environment(case,backend) if environment is None else environment
    s=dict(initial);mask=FULL
    sites,edges=set(),set()
    def mark(pc): sites.add(pc)
    def readbyte(seg,off):
        p=common.physical(seg,off);v=backend.vga.read(backend.memory,p,s['flags'])
        backend.events.add('read',p,v,s['flags'],mask);return v
    def readword(seg,off):
        p=common.physical(seg,off);values=[]
        for n in range(2):
            address=(p+n)&0xfffff;v=backend.vga.read(backend.memory,address,s['flags'])
            backend.events.add('read',address,v,s['flags'],mask);values.append(v)
        return values[0]|values[1]<<8
    def push(value):
        s['sp']=(s['sp']-2)&65535;writeword(s['ss'],s['sp'],value)
    def writeword(seg,off,value):
        p=common.physical(seg,off)
        for n in range(2):
            address=(p+n)&0xfffff;v=(value>>(8*n))&255
            backend.vga.write(backend.memory,address,v,s['flags']);backend.events.add('write',address,v,s['flags'],mask)
    def pop():
        value=readword(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535;return value
    def xorflags():
        nonlocal mask
        s['flags']=(s['flags']&~0x8c5)|0x44;mask=LOGIC
    def service(pc,key):
        nonlocal s,mask
        if missing_pc(case)==pc: raise Boundary(pc,1)
        mark(pc);s,_=env.invoke(key,s,mask);mask=FULL
    def call(site,kind):
        nonlocal s,mask
        mark(site);entry,expected=CALLS[site];push(expected)
        if kind=='clock':
            mark(0x16a9);push(s['ds']);mark(0x16aa);s['flags']&=~0x200
            mark(0x16ab);s['ax']=(s['ax']&0xff00)|0x36
            if missing_pc(case)==0x16ad: raise Boundary(0x16ad,1)
            mark(0x16ad);env.port(0x43,0x36,s['flags'],mask)
            mark(0x16af);s['ax']&=0xff00;xorflags()
            for pc in (0x16b1,0x16b3): mark(pc);env.port(0x40,0,s['flags'],mask)
            mark(0x16b5);s['ax']=0;xorflags();mark(0x16b7)
            s['bx']=readword(s['ds'],0x1fbe);s['es']=readword(s['ds'],0x1fc0)
            mark(0x16bb);s['ds']=0;mark(0x16bd);writeword(0,0x20,s['bx'])
            mark(0x16c1);writeword(0,0x22,s['es']);mark(0x16c5);s['flags']|=0x200
            mark(0x16c6);s['ds']=pop();mark(0x16c7);s['cx']=readword(s['ds'],0x259c)
            mark(0x16cb);s['dx']=readword(s['ds'],0x259e);mark(0x16cf);s['ax']=0x100
            service(0x16d1,'clock');mark(0x16d3)
        elif kind in ('keyboard1','private','keyboard2'):
            private=kind=='private';mark(0xfa0 if private else 0x1582);push(s['ds'])
            if private:
                mark(0xfa1);s['ax']=(s['ax']&255)|0x2500;mark(0xfa3);s['ax']=(s['ax']&0xff00)|readbyte(s['ds'],0x1fc6)
                mark(0xfa6);s['dx']=readword(s['ds'],0x1fc2);mark(0xfaa);s['ds']=readword(s['ds'],0x1fc4)
                service(0xfae,kind);mark(0xfb0);s['ds']=pop();mark(0xfb1)
            else:
                mark(0x1583);s['ax']=0x2509;mark(0x1586);s['dx']=readword(s['ds'],0x1fba)
                mark(0x158a);s['ds']=readword(s['ds'],0x1fbc);service(0x158e,kind)
                mark(0x1590);s['ds']=pop();mark(0x1591)
        else:
            mark(0xff8);s['ax']=(s['ax']&0xff00)|readbyte(s['ds'],0x1fe1)
            mark(0xffb);s['ax']&=255;xorflags();service(0xffd,'mode')
            mark(0xfff);s['ax']=(s['ax']&255)|0x500;mark(0x1001)
            s['ax']=(s['ax']&0xff00)|readbyte(s['ds'],0x1fe2);service(0x1004,'page');mark(0x1006)
        target=pop()
        if target!=expected: raise Boundary(target,2)
    try:
        if not case['suffix']:
            for site,key in ((0x4d0,'clock'),(0x4d3,'keyboard1'),(0x4d6,'private'),(0x4d9,'video')): call(site,key)
            mark(0x4dc);v=readbyte(s['ds'],0x1f73);result=(v-255)&255
            parity=not (result.bit_count()&1)
            s['flags']=(s['flags']&~0x8d5)|(v<255)| (4 if parity else 0)| (0x10 if (v^255^result)&16 else 0)| (0x40 if result==0 else 0)| (0x80 if result&128 else 0)| (0x800 if ((v^255)&(v^result)&128) else 0)
            mask=FULL;mark(0x4e1);edges.add((0x4e1,0x4ea if v==255 else 0x4e3))
            if v!=255:
                mark(0x4e3);s['ax']=0xc;mark(0x4e6);s['cx']=0;xorflags();service(0x4e8,'mouse')
        call(0x4ea,'keyboard2');mark(0x4ed);s['dx']=0x20ac
        mark(0x4f0);s['ax']=(s['ax']&255)|0x900;service(0x4f2,'message');mark(0x4f4);s['ax']=0x4c00
        if missing_pc(case)==0x4f7: raise Boundary(0x4f7,1)
        mark(0x4f7);env.invoke('terminate',s,mask);raise Boundary(0x4f9,0)
    except Boundary as boundary:
        return backend,s,env,boundary.target,boundary.status,mask,sites,edges


def original(case,memory,initial):
    backend=device(memory,case);env=Environment(case,backend)
    cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,SIZE*2);cpu.mem_write(0,bytes(backend.memory)*2)
    for key,value in dict(initial,cs=case['load'],ip=0x4ea if case['suffix'] else 0x4d0).items():
        cpu.reg_write(x.UC_X86_REG_EFLAGS if key=='flags' else common.drawing.oracle.REG[key],value)
    values={(case['load']<<4)+p+n:IMAGE[p+n] for p,ins in INS.items() for n in range(ins.size)}
    if any(backend.memory[p]!=v for p,v in values.items()): oracle_fail('Cleanup entered changed code')
    mask,event_flags,previous,pending,done,status,steps=FULL,initial['flags'],None,None,False,None,0
    stack,sites,edges,failure=[],set(),set(),[]
    def fail(error):
        if not failure:failure.append(str(error))
        cpu.emu_stop()
    def sync(addresses):
        for p in addresses:
            value=bytes((backend.memory[p],));cpu.mem_write(p,value);cpu.mem_write(p+SIZE,value)
        if any(backend.memory[p]!=v for p,v in values.items()):oracle_fail('Cleanup provider modified decoded code')
    def code(uc,_pc,_size,_user):
        nonlocal mask,event_flags,previous,pending,done,status,steps
        if previous in (0x16af,0x16b5,0xffb,0x4e6):mask=LOGIC
        if previous==0x4dc:mask=FULL
        off,cs=uc.reg_read(x.UC_X86_REG_IP),uc.reg_read(x.UC_X86_REG_CS)
        if pending is not None:
            expected=pending;pending=None
            if not stack or stack.pop()!=expected:fail('Unknown cleanup RET frame');return
            if off!=expected or cs!=case['load']:done,status=True,2;uc.emu_stop();return
        if previous==0x4e1:edges.add((0x4e1,off))
        if cs!=case['load'] or off not in INS:fail(f'Cleanup escaped at{cs:04x}:{off:04x}');return
        if off==missing_pc(case):done,status=True,1;uc.emu_stop();return
        steps+=1
        if steps>80:fail('Cleanup instruction budget exhausted');return
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS);previous=off;sites.add(off)
        if off in CALLS:stack.append(CALLS[off][1])
        if INS[off].mnemonic=='ret':
            if not stack:fail('Cleanup outerRET is forbidden');return
            pending=stack[-1]
    def read(uc,_a,address,size,_value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=backend.vga.read(backend.memory,p,event_flags)
                backend.events.add('read',p,v,event_flags,mask);uc.mem_write(address+n,bytes((v,)))
            backend.check('cleanup original read')
        except BaseException as error:fail(error)
    def write(_uc,_a,address,size,value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=(value>>(8*n))&255
                if p in values and values[p]!=v:oracle_fail('Cleanup wrote decoded code')
                backend.vga.write(backend.memory,p,v,event_flags);backend.events.add('write',p,v,event_flags,mask);sync((p,))
            backend.check('cleanup original write')
        except BaseException as error:fail(error)
    def port(_uc,number,size,value,_user):
        try:
            if size!=1:oracle_fail('Cleanup unexpected port width')
            env.port(number,value,event_flags,mask)
        except BaseException as error:fail(error)
    def interrupt(uc,number,_user):
        nonlocal mask,done,status
        try:
            key=INTERRUPTS.get(previous)
            if previous==0x158e:key='keyboard1' if stack[-1]==0x4d6 else 'keyboard2'
            wanted=0x1a if key=='clock' else 0x10 if key in ('mode','page') else 0x33 if key=='mouse' else 0x21
            if key is None or number!=wanted:oracle_fail('Unexpected cleanup interrupt')
            incoming={k:uc.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in REGS}
            out,changed=env.invoke(key,incoming,mask);sync(changed)
            if key=='terminate':done,status=True,0;uc.emu_stop();return
            for k in REGS:uc.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],out[k])
            mask=FULL
        except BaseException as error:fail(error)
    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write)
    cpu.hook_add(UC_HOOK_INSN,port,None,1,0,x.UC_X86_INS_OUT);cpu.hook_add(UC_HOOK_INTR,interrupt)
    cpu.emu_start((case['load']<<4)+(0x4ea if case['suffix'] else 0x4d0),0,count=81)
    if failure:oracle_fail(case['name']+': '+failure[0])
    if not done:oracle_fail(case['name']+': no cleanup boundary')
    regs={k:cpu.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in (*REGS,'cs','ip')}
    return backend,regs,env,regs['ip'],status,mask,sites,edges


def equal_environment(actual,expected,fail,label):
    common.equal_calls(actual.calls,expected.calls,fail,label)
    timer.equal_ports(actual.ports,expected.ports,fail,label)
    if actual.payloads!=expected.payloads:fail(label+' live DOS09 bytes differ')


def original_case(case):
    memory,initial=prepare(case)
    expected,state,env,target,status,mask,sites,edges=model(case,memory,initial)
    backend,regs,observed,actual_target,actual_status,actual_mask,actual_sites,actual_edges=original(case,memory,initial)
    common.equal_state(regs,state,mask,oracle_fail,case['name']+' model')
    common.equal_device(backend,expected,oracle_fail,case['name']+' model')
    equal_environment(observed,env,oracle_fail,case['name']+' model')
    if (actual_target,actual_status,actual_mask,actual_sites,actual_edges,regs['cs'])!=(target,status,mask,sites,edges,case['load']):
        oracle_fail(case['name']+' original control/site domain differs')
    return memory,initial,backend,regs,observed,target,status,mask,sites,edges


def native_services(case,backend):
    env=Environment(case,backend);references=[];vector_count=0
    def provider(key,incoming,outgoing=None):
        if len(env.calls)>=9:common.fixture.exit_worker(86,'Cleanup service budget exhausted')
        try:
            state=common.state_dict(incoming[0]);out,_=env.invoke(key,state,LOGIC if key in ('clock','mode','mouse') else FULL)
            if outgoing is not None:
                for field,k in zip(FIELDS,REGS):setattr(outgoing[0],field,out[k])
        except BaseException as error:common.fixture.exit_worker(87,f'Cleanup provider failed:{error}')
    def returning(key):
        @RETURN
        def callback(_context,_memory,incoming,outgoing):provider(key,incoming,outgoing)
        references.append(callback);return callback
    @RETURN
    def vector(_context,_memory,incoming,outgoing):
        nonlocal vector_count
        keys=('keyboard2',) if case['suffix'] else ('keyboard1','private','keyboard2')
        if vector_count>=len(keys):common.fixture.exit_worker(86,'Cleanup vector budget exhausted')
        key=keys[vector_count];vector_count+=1;provider(key,incoming,outgoing)
    @timer.PORT
    def port(_context,number,value,flags):
        if len(env.ports)>=3:common.fixture.exit_worker(86,'Cleanup byte-port budget exhausted')
        try:env.port(number,value,flags,FULL if not env.ports else LOGIC)
        except BaseException as error:common.fixture.exit_worker(87,f'Cleanup port failed:{error}')
    @TERMINATE
    def terminate(_context,_memory,incoming):provider('terminate',incoming)
    missing=case.get('missing')
    if missing=='no-services':return None,env,(vector,port,terminate,references)
    ts=timer.Services(None,timer.PORT() if missing=='port' else port,timer.CLOCK() if missing=='clock' else returning('clock'))
    vs=vectors.Services(None,RETURN() if missing=='vectors' else vector)
    bios=common.Services(None,RETURN() if missing=='mode' else returning('mode'),RETURN() if missing=='page' else returning('page'))
    service=Services(None if missing=='timer' else ctypes.pointer(ts),ctypes.pointer(vs),
        None if missing=='video' else ctypes.pointer(bios),None,
        RETURN() if missing=='mouse' else returning('mouse'),RETURN() if missing=='message' else returning('message'),
        TERMINATE() if missing=='terminate' else terminate)
    return service,env,(ts,vs,bios,vector,port,terminate,references)


class Native:
    def __init__(self,directory,mutation=0):
        self.library=ctypes.CDLL(str(build(Path(directory)/f'fatal-cleanup-m{mutation}.dll',mutation,'fatal_cleanup')))
        self.core=self.library.lmn_fatal_cleanup_core
        self.core.argtypes=[MEM,ctypes.POINTER(State),ctypes.c_uint,ctypes.POINTER(Services),ctypes.POINTER(common.fixture.RasterBus)]
        self.core.restype=Result
        self.adapter=self.library.lmn_fatal_cleanup_adapter
        self.adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.c_uint,ctypes.POINTER(Services),ctypes.POINTER(common.fixture.RasterBus)]


def compare(native,case):
    memory,initial,expected,regs,env,target,status,mask,sites,edges=original_case(case)
    vga=case.get('kind','').startswith('vga-')
    for core in (False,True):
        for null in (False,True):
            if null and vga:continue
            backend=device(memory,case);services,actual,refs=native_services(case,backend)
            bus=None if null else ctypes.byref(backend.bus)
            label=case['name']+(' core' if core else ' adapter')
            if core:
                state=common.to_state(initial)
                result=native.core(common.buffer(backend.memory),ctypes.byref(state),case['suffix'],common.pointer(services),bus)
                current=common.state_dict(result.state)
                if (result.continuation,result.status)!=(target,status):native_fail(label+' boundary/status differs')
            else:
                current_regs=Regs(**{k:v for k,v in initial.items() if k!='flags'},cs=case['load'],ip=0x4ea if case['suffix'] else 0x4d0,flags=initial['flags'])
                native.adapter(common.buffer(backend.memory),ctypes.byref(current_regs),case['suffix'],common.pointer(services),bus)
                current={k:getattr(current_regs,k) for k in REGS}
                if (current_regs.cs,current_regs.ip)!=(case['load'],target):native_fail(label+' ip/cs differs')
            common.equal_state(current,regs,mask,native_fail,label)
            equal_environment(actual,env,native_fail,label)
            if null:
                if backend.memory!=expected.memory:native_fail(label+' null RAM differs')
            else:common.equal_device(backend,expected,native_fail,label)
    return dict(name=case['name'],suffix=case['suffix'],vga=vga,status=status,target=target,sites=sorted(sites),edges=sorted(edges))


def input_hashes(native=False):
    paths=set(timer.input_hashes(False))|set(vectors.input_hashes(False))
    paths.update(('tests/fatal_cleanup.py','docs/fatal-cleanup.md'))
    if native:paths.update(('c/fatal_cleanup.c','c/fatal_cleanup.h','c/timer_restore.c','c/timer_restore.h',
        'c/vector_restore.c','c/vector_restore.h','c/video_restore.c','c/video_restore.h','c/lemmings_sym.h',
        'c/regs.h','c/special_blit.h','tools/cbuild.py','tools/coverage.py','tools/difftest.py'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before=input_hashes();rows=[];sites=set();edges=set()
    if sha(ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d' or sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e':oracle_fail('Pinned cleanup image changed')
    if IMAGE[0x4d0:0x4f9]!=CODE:oracle_fail('Cleanup bytes changed')
    for case in cases():
        result=original_case(case)
        if case.get('kind','').startswith('changed-') and result[5:7]!=(0xdead,2):
            oracle_fail(case['name']+' did not change the actual child return')
        sites.update(result[-2]);edges.update(result[-1]);rows.append(case['name']);gc.collect()
    if len(INS)!=56 or sites!=set(INS) or edges!={(0x4e1,0x4e3),(0x4e1,0x4ea)}:oracle_fail('Cleanup original static/branch coverage differs')
    if before!=input_hashes():oracle_fail('Cleanup original inputs changed')
    write_json(ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),cases=rows,
        executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),caller_sites=15,
        caller_bytes=41,integrated_bytes=133,c_coverage_claimed=False,input_hashes=before))
    print(f'PASS fatal cleanup original:{len(rows)} cases,15 caller/56 integrated sites,2 edges;no C coverage',flush=True)


def worker(directory=None):
    common.fixture.MAX_BUS_EVENTS=256;common.fixture.MAX_VGA_EVENTS=256
    before=input_hashes(directory is not None);original_phase()
    if directory is None:return
    native=Native(directory);specs=cases();rows=[]
    for case in specs:rows.append(compare(native,case));gc.collect()
    mutants=[]
    for number,name in ((1,'full-mouse-gate-00'),(2,'full-mouse-gate-00'),(3,'changed-private'),(4,'message-stack-a20')):
        variant=Native(directory,number);case=next(c for c in specs if c['name']==name)
        try:compare(variant,case)
        except NativeMismatch as error:mutants.append(dict(mutation=number,case=name,mismatch=str(error),completed=True))
        else:oracle_fail(f'Cleanup mutant{number} survived')
        gc.collect()
    if before!=input_hashes(True):oracle_fail('Cleanup native inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),auxiliary_core_cases=len(rows),
        null_bus_adapter_cases=sum(not r['vga'] for r in rows),cases=rows,mutation_count=4,mutations=mutants,
        translated_code_bytes=41,native_code_ranges=[[0x4d0,0x4f9]],caller_instruction_sites=15,
        executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),
        branch_edges=sorted({tuple(e) for r in rows for e in r['edges']}),input_hashes=before,
        limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_instructions=80,
                    bus_events=256,byte_port_calls=3,service_calls=9,dos09_bytes=64),
        domain='Full04D0 and independently reached04EA, directlogicalrestorecores/liveCALLRET; explicit PIT/returning BIOS/DOS/mouse and terminalDOS providers; intactcode/sameCS/TFclear/quiescentIRQ; canonical RAM/VGA, allstate/definedflags/order.'))
    print(f'PASS fatal cleanup C:{len(rows)} adapter+core cases,15 caller/56 integrated sites,4 completed mutants',flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected fatal cleanup arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='fatal-cleanup-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)


if __name__=='__main__':main()
