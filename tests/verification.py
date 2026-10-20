"""Shared bounded differential machinery; original instructions run only in Unicorn.

Suites supply instruction domains, boundary policies, finite providers and independent
expectations. This module supplies no translated game routine or expected algorithm.
"""
import copy
import ctypes as ct
import os
import random
import sys
from array import array
from collections.abc import Sequence
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools')]
import capstone
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, relocated, unpack
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN, UC_HOOK_INTR)
from unicorn import x86_const as x

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SIZE,MASK,FLAGS=1<<20,(1<<20)-1,0x0FD7
LOADS=(0x1010,0x1213,0x2345)
REG_NAMES=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip','flags')
REG_IDS={n:getattr(x,'UC_X86_REG_'+n.upper()) for n in REG_NAMES if n!='flags'}
REG_IDS['flags']=x.UC_X86_REG_EFLAGS
MEM=ct.POINTER(ct.c_uint8)
class Regs(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in REG_NAMES]
READ=ct.CFUNCTYPE(ct.c_uint8,ct.c_void_p,MEM,ct.c_uint32,ct.c_uint16)
WRITE=ct.CFUNCTYPE(None,ct.c_void_p,MEM,ct.c_uint32,ct.c_uint8,ct.c_uint16)
OUT=ct.CFUNCTYPE(None,ct.c_void_p,ct.c_uint16,ct.c_uint16,ct.c_uint16)
OUT8=ct.CFUNCTYPE(None,ct.c_void_p,MEM,ct.c_uint16,ct.c_uint8,ct.c_uint16)
IN8=ct.CFUNCTYPE(ct.c_uint8,ct.c_void_p,MEM,ct.c_uint16,ct.c_uint16)
INTERRUPT=ct.CFUNCTYPE(ct.c_uint16,ct.c_void_p,MEM,ct.POINTER(Regs),ct.c_void_p)
FOREGROUND=ct.CFUNCTYPE(ct.c_uint16,ct.c_void_p,MEM,ct.POINTER(Regs),ct.c_uint16)
class ForegroundPoll(ct.Structure):
    _fields_=[('context',ct.c_void_p),('poll',FOREGROUND)]
class Bus(ct.Structure):
    _fields_=[('context',ct.c_void_p),('read_byte',READ),('write_byte',WRITE),('out_word',OUT)]
class Ports(ct.Structure):
    _fields_=[('context',ct.c_void_p),('out_byte',OUT8),('in_byte',IN8)]
# The bus pointer is opaque in this callback ABI; providers use the same
# bounded BusAccess object on both sides rather than dereferencing a C table.
class InterruptService(ct.Structure):
    _fields_=[('context',ct.c_void_p),('execute',INTERRUPT),
              ('code_segment',ct.c_uint16),('instruction_pointer',ct.c_uint16)]
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
class OracleFailure(AssertionError):pass
class Mismatch(AssertionError):pass
def check(condition,message):
    if not condition:raise OracleFailure(message)
def require(condition,message):
    if not condition:raise Mismatch(message)

def is_branch(ins):
    return ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')


def direct_jump_edges(instructions, *, external_transfers=()):
    """Static outcomes of known direct branches; does not prove feasibility."""
    edges=set()
    for address,ins in instructions.items():
        if not is_branch(ins):continue
        if address in external_transfers:continue
        check(ins.operands[0].type==capstone.x86_const.X86_OP_IMM,
              'indirect branch requires an explicit target-domain contract')
        edges.add((address,ins.operands[0].imm&0xFFFF))
        if ins.mnemonic!='jmp':edges.add((address,(address+ins.size)&0xFFFF))
    return edges

def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK

def get16(memory, segment, offset):
    at = physical(segment, offset)
    return memory[at] | (memory[(at + 1) & MASK] << 8)

def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF

def sync_memory_byte(memory, device, segment, offset, value):
    at = physical(segment, offset)
    value &= 0xFF
    memory[at] = value
    if device is not None and VGA_BASE <= at < VGA_END:
        index = at - VGA_BASE
        for plane in device.planes:
            plane[index] = value

def put16(memory, segment, offset, value, device=None):
    at = physical(segment, offset)
    for delta, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
        address = (at + delta) & MASK
        memory[address] = byte
        if device is not None and VGA_BASE <= address < VGA_END:
            for plane in device.planes:
                plane[address - VGA_BASE] = byte

def loaded_image(load):
    return relocated(IMAGE, ORACLE["relocations"], load)

def code_image(memory, load):
    image = loaded_image(load)
    base = (load << 4) & MASK
    first = min(len(image), SIZE - base)
    memory[base:base + first] = image[:first]
    if first < len(image):
        memory[:len(image) - first] = image[first:]
    return image

def default_regs(load, seed, *, ss=0x5000, sp=0x9000, ds=0x3000,
                 es=0x6400, flags=0x0AD7):
    rng = random.Random(seed)
    return dict(ax=rng.randrange(0x10000), bx=rng.randrange(0x10000),
                cx=0x3A71 ^ seed, dx=0x91C2 ^ seed,
                si=rng.randrange(0x10000), di=rng.randrange(0x10000),
                bp=rng.randrange(0x10000), cs=load, ds=ds, es=es,
                ss=ss, sp=sp, ip=0, flags=flags & 0xFFFF)

def new_device(seed):
    device = MinimapVga(seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[5] = 0
    device.gc[8] = 0xFF
    return device

def initial_memory(case):
    rng = random.Random(case.get("seed", 0x587F))
    memory = bytearray(rng.randbytes(SIZE))
    load = case.get("load", LOADS[0])
    code_image(memory, load)
    device = new_device(case.get("seed", 0x587F) ^ 0xA5A5)
    return memory, device


class PackedEvents(Sequence):
    """Lossless ordered observations with five uint32 words per event.

    This changes storage only. Callers retain the same tuple interface, masks,
    slicing and hard event-budget failure; no observations are sampled/dropped.
    """
    def __init__(self):
        self.words=array('I');self.kinds=[];self.kind_ids={}
    def __len__(self):return len(self.words)//5
    def append(self,event):
        kind,address,value,flags,mask=event
        if kind not in self.kind_ids:
            self.kind_ids[kind]=len(self.kinds);self.kinds.append(kind)
        self.words.extend((self.kind_ids[kind],address,value,flags,mask))
    def __getitem__(self,index):
        if isinstance(index,slice):return [self[i] for i in range(*index.indices(len(self)))]
        if index<0:index+=len(self)
        if not 0<=index<len(self):raise IndexError(index)
        p=index*5
        return (self.kinds[self.words[p]],*self.words[p+1:p+5])
    def __iter__(self):
        for p in range(0,len(self.words),5):
            yield (self.kinds[self.words[p]],*self.words[p+1:p+5])


class PackedDeviceTrace(Sequence):
    """Lossless bounded four-field device observations over shared storage."""
    def __init__(self,max_events):self.events=PackedEvents();self.max_events=max_events
    def append(self,event):
        check(len(self)<self.max_events,'device event budget exhausted')
        self.events.append((*event,0))
    def __len__(self):return len(self.events)
    def __iter__(self):return (e[:4] for e in self.events)
    def __getitem__(self,index):
        if isinstance(index,slice):return [e[:4] for e in self.events[index]]
        return self.events[index][:4]
    def clear(self):self.events=PackedEvents()


class BusAccess:
    """One canonical RAM image and bounded, ordered observations on either side."""
    def __init__(self, case, memory, registers, device, *, max_events, packed_events=False):
        self.c,self.memory,self.r,self.device=case,memory,registers,device
        self.events=PackedEvents() if packed_events else []
        self.providers=set();self.cursor=0;self.sync=None
        self.max_events=max_events
        self.service_events=[];self.transport_events=0

    def emit(self,kind,address,value,flags,mask=FLAGS):
        if len(self.events)>=self.max_events:raise OracleFailure('callback event budget exhausted')
        self.events.append((kind,address,value,flags,mask))

    def access(self,kind,address,flags,mask=FLAGS,value=None):
        address&=MASK
        if kind=='read':
            value=self.device.read(self.memory,address,flags) if VGA_BASE<=address<VGA_END else self.memory[address]
        elif VGA_BASE<=address<VGA_END:self.device.write(self.memory,address,value,flags)
        else:self.memory[address]=value
        self.emit(kind,address,value,flags,mask)
        return value

    def patch(self,segment,offset,value,name,word=True):
        if word:put16(self.memory,segment,offset,value,self.device)
        else:sync_memory_byte(self.memory,self.device,segment,offset,value)
        at=physical(segment,offset)
        if self.sync:
            for delta in range(2 if word else 1):
                p=(at+delta)&MASK
                self.sync(p,bytes((self.memory[p],)));self.sync(p+SIZE,bytes((self.memory[p],)))
        self.providers.add(name)

    def word_read(self,segment,offset,flags,mask=FLAGS):
        at=physical(segment,offset)
        return self.access('read',at,flags,mask)|(self.access('read',at+1,flags,mask)<<8)

    def word_write(self,segment,offset,value,flags,mask=FLAGS):
        at=physical(segment,offset)
        for delta in range(2):
            p=(at+delta)&MASK
            self.access('write',p,flags,mask,(value>>(delta*8))&255)
            if self.sync:
                self.sync(p,bytes((self.memory[p],)));self.sync(p+SIZE,bytes((self.memory[p],)))


def callback_failure(error):
    """A ctypes exception cannot unwind native loops; terminate the bounded worker."""
    try:os.write(2,(str(error)+'\n').encode('utf8',errors='backslashreplace'))
    finally:os._exit(86 if 'budget' in str(error) else 87)


class NativeCallbacks:
    def __init__(self,access,*,missing_in=False,missing_out=False):
        self.access=access
        def guarded(fn):
            def call(*args):
                try:return fn(*args)
                except BaseException as error:callback_failure(error)
            return call
        def unexpected(*args):raise OracleFailure('unexpected word OUT')
        self.keep=(READ(guarded(lambda _,m,a,f:access.access('read',a,f))),
                   WRITE(guarded(lambda _,m,a,v,f:access.access('write',a,f,value=v))),
                   OUT(guarded(lambda _,p,v,f:getattr(access,'out_word',unexpected)(p,v,f))),
                   OUT8(guarded(lambda _,m,p,v,f:access.out(p,v,f))),
                   IN8(guarded(lambda _,m,p,f:access.inp(p,f))))
        self.bus=Bus(None,*self.keep[:3])
        self.ports=Ports(None,OUT8() if missing_out else self.keep[3],
                         IN8() if missing_in else self.keep[4])

    def interrupt(self,provider):
        """Guard a declared full-register pre-IRET fixture provider."""
        def call(_,memory,registers,bus):
            try:
                address=ct.addressof((ct.c_uint8*len(self.access.memory)).from_buffer(self.access.memory))
                check(ct.addressof(memory.contents)==address,'provider canonical RAM binding differs')
                r={name:getattr(registers.contents,name) for name in REG_NAMES}
                status=provider(self.access,r)
                for name in REG_NAMES:setattr(registers.contents,name,r[name])
                return status
            except BaseException as error:callback_failure(error)
        return INTERRUPT(call)

    def foreground(self,provider):
        """Guard a declared foreground scheduling point on canonical RAM."""
        def call(_,memory,registers,site):
            try:
                address=ct.addressof((ct.c_uint8*len(self.access.memory)).from_buffer(self.access.memory))
                check(ct.addressof(memory.contents)==address,'poll canonical RAM binding differs')
                r={name:getattr(registers.contents,name) for name in REG_NAMES}
                check(r['ip']==site,'poll IP differs from declared site')
                status=provider(self.access,r,site)
                for name in REG_NAMES:setattr(registers.contents,name,r[name])
                return status
            except BaseException as error:callback_failure(error)
        return FOREGROUND(call)


def compare_states(label,actual,reference):
    """Compare full canonical state and each defined observation; no budget credit."""
    for name in ('status','child_status','service_status'):
        if name in reference:require(actual[name]==reference[name],label+': '+name+' differs')
    require(actual['memory']==reference['memory'],label+': RAM differs')
    for name in REG_NAMES:
        mask=reference['mask'] if name=='flags' else 0xFFFF
        require(((actual['regs'][name]^reference['regs'][name])&mask)==0,
                f'{label}: {name} {actual["regs"][name]:04X}/{reference["regs"][name]:04X}')
    if len(actual['events'])!=len(reference['events']):
        at=next((i for i,(a,b) in enumerate(zip(actual['events'],reference['events']))
                 if a[:3]!=b[:3]),min(len(actual['events']),len(reference['events'])))
        raise Mismatch(f"{label}: event count {len(actual['events'])}/{len(reference['events'])}; "
                       f"first difference {at}: {actual['events'][at:at+2]}/{reference['events'][at:at+2]}")
    for i,(a,b) in enumerate(zip(actual['events'],reference['events'])):
        require(a[:3]==b[:3] and ((a[3]^b[3])&b[4])==0,f'{label}: event{i} {a}/{b}')
    for name in ('providers','cursor','services'):
        if name in reference:require(actual[name]==reference[name],label+': '+name+' differs')
    require(actual['device'].state()==reference['device'].state(),label+': VGA state differs')
    require([e[:3] for e in actual['device'].trace]==[e[:3] for e in reference['device'].trace],label+': VGA access order differs')


class OriginalMachine:
    """Continuous exact Unicorn execution with declarative actual-RET boundaries.

    The domain owns decoded instruction extents, not C source. Callers provide
    finite port/service providers and may stop before an unsupported transfer.
    Interrupt transport is explicitly declared separately from executed sites.
    """
    def __init__(self,case,memory,registers,device,core,*,instructions,access,
                 outer_returns,child_returns=None,max_steps=100000,
                 changed_return_status=4,before=None,interrupt=None,
                 mutable_operands=(), far_calls=None, far_returns=None):
        self.c,self.memory,self.r,self.device,self.core=case,memory,registers,device,core
        self.instructions=instructions;self.access=access
        self.outer_returns=outer_returns if callable(outer_returns) else set(outer_returns)
        self.child_returns=child_returns or {};self.max_steps=max_steps
        self.changed_return_status=changed_return_status;self.before=before;self.interrupt=interrupt
        self.far_calls=far_calls or {}
        self.far_returns=far_returns or {}
        for off in self.far_calls:
            check(off in instructions and instructions[off].id==capstone.x86_const.X86_INS_LJMP,
                  'external chain is not an identified far JMP')
        for off in self.far_returns:
            check(off in instructions and instructions[off].mnemonic=='retf' and instructions[off].size==1,
                  'far return is not an identified plain RETF')
        self.cpu=Uc(UC_ARCH_X86,UC_MODE_16);self.cpu.mem_map(0,SIZE*2)
        self.cpu.mem_write(0,bytes(memory));self.cpu.mem_write(SIZE,bytes(memory))
        self.access.sync=self.cpu.mem_write
        self.mask=FLAGS;self.flags=registers['flags'];self.steps=0;self.sites=set();self.edges=set()
        self.previous=None;self.previous_count=0;self.pending=False;self.executing_boundary=False
        self.status=0;self.service_status=0;self.stopped=False
        self.far_return_events=0
        self.loaded=loaded_image(case['load'])
        self.code_bytes={physical(case['load'],p+d) for p,i in instructions.items() for d in range(i.size)}
        self.mutable_operands={};self.operand_versions={};self.pending_fetch=None
        for start,width in mutable_operands:
            owner=next((i for i in instructions.values()
                        if i.address+i.imm_offset==start and i.imm_size==width),None)
            check(owner is not None and width>0,'mutable field is not a complete decoded immediate')
            self.mutable_operands[owner.address]=(start,width)
            self.operand_versions[owner.address]=bytes(self.loaded[start:start+width])
            self.code_bytes.difference_update(physical(case['load'],start+d) for d in range(width))
        self.cpu.hook_add(UC_HOOK_CODE,self.code)
        self.read_hook=self.cpu.hook_add(UC_HOOK_MEM_READ,self.read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,self.write)
        self.cpu.hook_add(UC_HOOK_INSN,self.inp,None,1,0,x.UC_X86_INS_IN)
        self.cpu.hook_add(UC_HOOK_INSN,self.out,None,1,0,x.UC_X86_INS_OUT)
        self.cpu.hook_add(UC_HOOK_INTR,self.on_interrupt)
        self.set_state(registers)

    def state(self):return {n:self.cpu.reg_read(REG_IDS[n])&0xFFFF for n in REG_NAMES}
    def set_state(self,registers):
        for n in REG_NAMES:self.cpu.reg_write(REG_IDS[n],registers[n])

    def stop(self,status):
        self.status=status;self.stopped=True;self.cpu.emu_stop()

    def code(self,u,address,size,_):
        off=(address-(self.c['load']<<4))&0xFFFF
        check(u.reg_read(REG_IDS['cs'])==self.c['load'] and off in self.instructions,'escaped identified code domain')
        ins=self.instructions[off]
        if self.previous:
            old=self.previous
            if is_branch(old):self.edges.add((old.address,off))
            if old.mnemonic in ('xor','and','or','test','shr','sar','shl'):self.mask=FLAGS&~0x10
            elif old.mnemonic in ('add','sub','cmp','neg','popf'):self.mask=FLAGS
            elif old.mnemonic in ('inc','dec'):self.mask|=0x8D4
            elif old.mnemonic=='ror':self.mask|=0x801
            elif old.mnemonic=='mul':self.mask=(self.mask&~0xD4)|0x801
            elif old.mnemonic=='div':self.mask&=~0x8D5
            elif old.mnemonic.split()[-1] in ('scasb','scasw'):
                # A zero-count REP performs no comparison and defines no flags.
                if not old.mnemonic.startswith('rep') or self.previous_count:self.mask=FLAGS
        expected=bytearray(self.loaded[off:off+ins.size])
        if off in self.mutable_operands:
            start,width=self.mutable_operands[off]
            value=bytes(self.memory[physical(self.c['load'],start+d)] for d in range(width))
            expected[start-off:start-off+width]=value
        check(bytes(u.mem_read(address,ins.size))==bytes(expected),f'code differs at {off:04X}')
        if off in self.mutable_operands and value!=self.operand_versions[off]:
            # Only explicitly identified immediate bytes may change. Resume at
            # this real instruction after invalidating Unicorn's decoded cache;
            # never replace its execution with a Python instruction model.
            self.operand_versions[off]=value;self.previous=None
            self.pending_fetch=off;u.emu_stop();return
        if (ins.mnemonic in ('ret','iret') or off in self.far_calls or off in self.far_returns) and not self.executing_boundary:
            # Observe the completed predecessor's defined flags/edge even when
            # the core boundary leaves this RET itself unexecuted.
            self.previous=None;self.pending=True;u.emu_stop();return
        if self.before and self.before(self,ins):return
        if ins.mnemonic in ('in','out'):
            missing=(self.c.get('missing_in') if ins.mnemonic=='in' else
                     self.c.get('missing_out' if ins.operands[-1].size==1 else 'missing_word_out'))
            if missing:
                self.service_status=self.c.get('missing_service_status',0)
                self.stop(self.c.get('missing_port_status',1));return
        self.flags=u.reg_read(REG_IDS['flags'])&0xFFFF
        self.previous=ins;self.previous_count=u.reg_read(REG_IDS['cx'])&0xFFFF
        self.sites.add(off);self.steps+=1
        if self.steps>self.max_steps:raise OracleFailure('original instruction budget exhausted')

    def read(self,u,kind,address,size,value,_):
        for d in range(size):
            p=(address+d)&MASK;v=self.access.access('read',p,self.flags,self.mask)
            u.mem_write(p,bytes((v,)));u.mem_write(p+SIZE,bytes((v,)))

    def write(self,u,kind,address,size,value,_):
        for d in range(size):
            p=(address+d)&MASK
            check(p not in self.code_bytes,'undeclared code write')
            self.access.access('write',p,self.flags,self.mask,(value>>(8*d))&255)
        for d in range(size):
            p=(address+d)&MASK;v=self.memory[p]
            u.mem_write(p,bytes((v,)));u.mem_write(p+SIZE,bytes((v,)))

    def inp(self,u,port,size,_):
        check(size==1,'not a byte IN');return self.access.inp(port,self.flags,self.mask)
    def out(self,u,port,size,value,_):
        if size==2:
            check(hasattr(self.access,'out_word'),'undeclared word OUT')
            self.access.out_word(port,value,self.flags,self.mask)
        else:
            check(size==1,'not a byte OUT');self.access.out(port,value,self.flags,self.mask)
    def on_interrupt(self,u,number,_):
        check(self.interrupt is not None,'unexpected interrupt')
        self.interrupt(self,number)

    def software_interrupt(self,number,resume,binding,provider):
        """Declared external pre-IRET provider, with actual canonical frame words."""
        r=self.state();old_cs=r['cs'];access=self.access
        check(r['ip']==resume,'software INT resume differs')
        start=len(access.events)
        for index,value in enumerate((r['flags'],old_cs,resume)):
            r['sp']=(r['sp']-2)&0xFFFF
            access.word_write(r['ss'],r['sp'],value,r['flags'],self.mask)
            if index==0:r['flags']&=~0x300
        r['cs']=access.word_read(0,number*4+2,r['flags'],self.mask)
        r['ip']=access.word_read(0,number*4,r['flags'],self.mask)
        access.transport_events+=len(access.events)-start
        self.set_state(r)
        self.external_iret(old_cs,resume,binding,provider)

    def external_iret(self,return_cs,resume,binding,provider):
        """Declared bound service body; consumes the provider's live IRET frame."""
        r=self.state();access=self.access
        if provider is None or (r['cs'],r['ip'])!=binding:
            self.set_state(r);self.stop(1);return
        self.service_status=provider(access,r)
        if self.service_status:
            self.set_state(r);self.stop(2);return
        start=len(access.events);values=[]
        for _ in range(3):
            values.append(access.word_read(r['ss'],r['sp'],r['flags']))
            r['sp']=(r['sp']+2)&0xFFFF
        access.transport_events+=len(access.events)-start
        r['ip'],r['cs']=values[:2];r['flags']=(values[2]&0x7FD5)|2
        self.mask=FLAGS;self.flags=r['flags'];self.set_state(r)
        if (r['cs'],r['ip'])!=(return_cs,resume):self.stop(3)

    def run(self):
        # Each resumed near-return consumes at least one instruction, so this
        # phase ceiling also covers unexpectedly recursive/changed call graphs.
        for phase in range(self.max_steps+1):
            if self.stopped:break
            r=self.state();self.pending=False;self.pending_fetch=None
            self.cpu.emu_start(physical(r['cs'],r['ip']),0,count=self.max_steps-self.steps+1)
            if self.stopped:break
            if self.pending_fetch is not None:
                self.cpu.ctl_remove_cache(0,SIZE*2)
                continue
            check(self.pending,'original did not reach bounded return/chain boundary')
            off=self.state()['ip']
            if off in self.far_calls:
                self.executing_boundary=True
                self.cpu.emu_start(physical(self.c['load'],off),0,count=1)
                self.executing_boundary=False
                resume,binding,provider=self.far_calls[off]
                self.previous=None  # The external return is not a direct jump edge.
                self.external_iret(self.c['load'],resume,binding,provider)
                continue
            outer=self.outer_returns(self,off) if callable(self.outer_returns) else off in self.outer_returns
            if outer and self.core:self.stopped=True;break
            if off in self.far_returns:
                # Unicorn's RETF is corrupted by its memory-read hook. As in
                # drawing_caller_oracle, observe/inject the actual frame reads,
                # then execute the unchanged original instruction without that
                # hook. Do not synthesize CS/IP/SP or patch an opcode/target.
                r=self.state()
                check(r['sp']<0xFFFE,
                      'RETF reference limitation: pinned Unicorn does not wrap the selector word EA; independent wrap oracle required')
                observed=[];start=len(self.access.events)
                for word in range(2):
                    offset=(r['sp']+2*word)&0xFFFF
                    value=self.access.word_read(r['ss'],offset,r['flags'],self.mask)
                    at=physical(r['ss'],offset)
                    for delta in range(2):
                        p=(at+delta)&MASK;byte=bytes(((value>>(8*delta))&255,))
                        observed.append((p,byte))
                self.far_return_events+=len(self.access.events)-start
                # A later read's provider can overwrite an already observed word.
                # The instruction consumes the observed values; canonical provider
                # writes are published again after it, never discarded.
                for p,byte in observed:
                    self.cpu.mem_write(p,byte);self.cpu.mem_write(p+SIZE,byte)
                self.cpu.hook_del(self.read_hook);self.executing_boundary=True
                try:
                    self.cpu.ctl_remove_cache(0,SIZE*2)
                    self.cpu.emu_start(physical(r['cs'],off),0,count=1)
                finally:
                    self.executing_boundary=False
                    for p,_ in observed:
                        byte=bytes((self.memory[p],))
                        self.cpu.mem_write(p,byte);self.cpu.mem_write(p+SIZE,byte)
                    self.read_hook=self.cpu.hook_add(UC_HOOK_MEM_READ,self.read)
                    self.cpu.ctl_remove_cache(0,SIZE*2)
                expected=self.far_returns[off]
                if callable(expected):expected=expected(self,off)
                returned=self.state()
                if (returned['cs'],returned['ip']) not in expected:
                    status=self.changed_return_status
                    if callable(status):status=status(self,off)
                    if isinstance(status,dict):status=status[off]
                    if isinstance(status,tuple):status,self.service_status=status
                    self.stop(status);break
                if outer:self.stopped=True;break
                continue
            self.executing_boundary=True
            self.cpu.emu_start(physical(self.c['load'],off),0,count=1)
            self.executing_boundary=False
            if outer:self.stopped=True;break
            check(off in self.child_returns,'undeclared child RET')
            expected=self.child_returns[off]
            if callable(expected):expected=expected(self,off)
            if self.state()['ip'] not in expected:
                status=self.changed_return_status
                if callable(status):status=status(self,off)
                if isinstance(status,dict):status=status[off]
                if isinstance(status,tuple):status,self.service_status=status
                self.stop(status);break
        check(self.stopped,'original phase budget exhausted')
        check(bytes(self.cpu.mem_read(0,SIZE))==bytes(self.memory),'canonical original RAM diverged')
        return dict(regs=self.state(),status=self.status,memory=bytearray(self.memory),device=copy.deepcopy(self.device),
                    events=self.access.events,providers=self.access.providers,cursor=self.access.cursor,
                    sites=self.sites,edges=self.edges,steps=self.steps,mask=self.mask,
                    far_return_events=self.far_return_events)
