"""Bounded body-level differential for the aligned opaque planar renderer."""
import ctypes
import random
import sys
from pathlib import Path

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,UC_HOOK_INTR,UC_HOOK_INSN)
from unicorn import x86_const as x
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated
from cbuild import build
from dat_io_c import Regs,MEM
import dat_io as oracle
from minimap_vga import MinimapVga,VGA_BASE,VGA_END

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
START=SYMS['PlanarAlignedOpaqueBody']['address']
END=0x9967
RETF=0x9966
UNKNOWN={0x98f4,0x9932}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
ALL_INS={i.address:i for i in MD.disasm(IMAGE[START:END],START) if i.address not in UNKNOWN}
BODY_INS={a:i for a,i in ALL_INS.items() if a!=RETF}
BRANCHES={pc for pc,i in BODY_INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&0xffff) for pc,i in BODY_INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in BODY_INS.items()
    if pc in BRANCHES and i.mnemonic!='jmp'}
VGA_WRITE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.c_uint32,
    ctypes.c_uint8,ctypes.c_uint16)
VGA_READ=ctypes.CFUNCTYPE(ctypes.c_uint8,ctypes.c_void_p,MEM,
    ctypes.c_uint32,ctypes.c_uint16)
VGA_OUT=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_uint16,
    ctypes.c_uint16,ctypes.c_uint16)

class RasterBus(ctypes.Structure):
    _fields_=[('context',ctypes.c_void_p),('read_byte',VGA_READ),
        ('write_byte',VGA_WRITE),('out_word',VGA_OUT)]

class TraceDevice:
    """The independent minimap fixture with a byte-ordered whole-bus log."""
    def __init__(self,memory,seed,read_map=0):
        self.memory=memory
        self.vga=MinimapVga(seed,read_map)
        # The body establishes these registers before its first drawing access.
        # Establish a valid mode-0 device before any possible SS=A000 stack push.
        self.vga.seq[2]=0x0f
        self.vga.gc[0]=0
        self.vga.gc[1]=0
        self.vga.gc[3]=0
        self.vga.gc[5]=0
        self.vga.gc[8]=0xff
        self.events=[]
        self.errors=[]
        def read(_ctx,_mem,address,flags):
            p=address&0xfffff
            try:
                value=self.vga.read(self.memory,p,flags) if VGA_BASE<=p<VGA_END else self.memory[p]
                self.events.append(('read',p,value,flags&0xffff))
                return value
            except Exception as error:
                self.errors.append(error)
                return 0
        def write(_ctx,_mem,address,value,flags):
            p=address&0xfffff
            try:
                if VGA_BASE<=p<VGA_END:self.vga.write(self.memory,p,value,flags)
                else:self.memory[p]=value
                self.events.append(('write',p,value,flags&0xffff))
            except Exception as error:self.errors.append(error)
        def out(_ctx,port,value,flags):
            try:
                self.vga.out(port,value,flags)
                self.events.append(('out',port,value,flags&0xffff))
            except Exception as error:self.errors.append(error)
        self._read=VGA_READ(read)
        self._write=VGA_WRITE(write)
        self._out=VGA_OUT(out)
        self.bus=RasterBus(None,self._read,self._write,self._out)

    def check(self):
        if self.errors:raise self.errors[0]

def physical(segment,offset):return (((segment<<4)+offset)&0xfffff)
def put16(memory,segment,offset,value):
    p=physical(segment,offset)
    memory[p]=(value&255)
    memory[(p+1)&0xfffff]=(value>>8)&255

def fixture(seed,read_map=0):
    memory=bytearray(1<<20)
    return memory,TraceDevice(memory,seed,read_map)

def cases():
    result=[]
    def add(name,**kwargs):result.append(dict(name=name,seed=len(result),**kwargs))
    for limit in (1,2,3,4,0,5,0xff):
        for width in (1,2,7):
            for height in (1,2):
                add(f'limit-{limit:02x}-width-{width}-height-{height}',
                    plane_limit=limit,width=width,height=height,
                    low_width=(limit*17+width)&255,read_map=(limit+width)&3,
                    independent=(limit in (4,0) and width in (1,7) and height in (1,2)))
    add('zero-CL-one-byte-wrapping-loop',plane_limit=1,width=0,height=1,low_width=0x7d)
    add('zero-CH-means-256-rows',plane_limit=1,width=1,height=0,low_width=0x19)
    add('DF-one-source-and-destination-cursors',plane_limit=4,width=2,height=2,df=True,
        source_cursor=0x2100,destination_cursor=0x0430,independent=True)
    add('DF-zero-independent-footprint',plane_limit=4,width=7,height=2,df=False,
        independent=True)
    add('segment-and-physical-20bit-wrap',plane_limit=2,width=2,height=1,df=True,
        ds=0xffff,source_segment=0xffff,source_cursor=0xfffe,destination_cursor=0xffff,
        ss=0xffff,sp=0x0010)
    add('SP-sixteen-bit-wrap-at-zero',plane_limit=3,width=1,height=1,sp=0)
    add('initial-DS-stack-alias-overwrites-graphics-pointer',plane_limit=2,width=2,height=1,
        same_segments=True,sp=0x1fe6)
    add('SS-saves-alias-row-advance-fields',plane_limit=4,width=2,height=2,
        same_segments=True,sp=0x6706)
    add('SS-saves-alias-inter-plane-extent',plane_limit=4,width=2,height=1,
        same_segments=True,sp=0x66fa)
    add('outer-far-frame-feeds-live-row-advance',plane_limit=3,width=2,height=1,
        same_segments=True,sp=0x6704)
    add('SS-aperture-stack-writes',plane_limit=1,width=2,height=1,ss=0xa000,sp=0x5000,
        destination_cursor=0x5100,stack_device=True)
    add('SS-aperture-return-frame-overlapped-by-draw',plane_limit=1,width=2,height=1,
        ss=0xa000,sp=0x5000,destination_cursor=0x5000,stack_device=True)
    add('far-return-SP-FFFF-boundary',plane_limit=1,width=1,height=1,sp=0xfffe,
        return_boundary=True)
    return result

def prepare(case):
    rng=random.Random(0x983b+case['seed'])
    load=(0x1010,0x1213,0x2345)[case['seed']%3]
    memory=bytearray(rng.randbytes(1<<20))
    memory[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    data=load+0x09a9
    ss=case.get('ss',0x7000)
    ds=data if case.get('same_segments') else case.get('ds',data)
    sp=case.get('sp',0x8000)
    source_segment=case.get('source_segment',0x5000)
    for name,value in (
        ('GraphicsResourceSegment',source_segment),
        ('DrawingSourcePlaneExtent',case.get('extent',0x0310)),
        ('DrawingSourcePitchBytes',0x0010),
        ('DrawingHorizontalSkipBytes',0x0003),
        ('DrawingVerticalSkipBytes',0x0005),
        ('DrawingDestinationRowAdvance',case.get('destination_advance',0x0013)),
        ('DrawingSourceRowAdvance',case.get('source_advance',0x000b)),
        ('DrawingActiveDestinationRowAdvance',case.get('destination_advance',0x0013))):
        oracle.put16(memory,ds,SYMS[name]['address'],value)
    regs={name:rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load,ip=START,ds=ds,ss=ss,sp=sp,es=rng.randrange(65536),
        cx=((case['height']&255)<<8)|(case['width']&255),
        dx=((case['plane_limit']&255)<<8)|(case.get('low_width',0x6d)&255),
        si=case.get('source_cursor',0x2000),di=case.get('destination_cursor',0x0410))
    if case.get('same_segments'):regs['ss']=ds
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    # The entry PUSH DS occurs before the relocated graphics-segment load, so
    # it may intentionally overwrite the pointer in the DS/SS alias cases.
    put16(memory,regs['ss'],sp,case.get('outer_ip',0xedd1))
    put16(memory,regs['ss'],(sp+2)&0xffff,case.get('outer_cs',0xbabe))
    dev=TraceDevice(memory,case['seed']+0x983b,case.get('read_map',0))
    if case.get('stack_device'):
        # The live far frame is device-owned when SS=A000. Seed the selected
        # VGA read plane independently; later body writes may change it.
        read_plane=dev.vga.gc[4]&3
        for n,value in enumerate((case.get('outer_ip',0xedd1)&255,
            case.get('outer_ip',0xedd1)>>8,case.get('outer_cs',0xbabe)&255,
            case.get('outer_cs',0xbabe)>>8)):
            dev.vga.planes[read_plane][(sp+n)&0xffff]=value
    return memory,regs,flags,load+0x09a9,dev

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'aligned-opaque-m{mutation}.dll',mutation,'aligned_opaque')))
    class Call(ctypes.Structure):
        _fields_=[('initial_data_segment',ctypes.c_uint16),('game_data_segment',ctypes.c_uint16),
            ('stack_segment',ctypes.c_uint16),('stack_offset',ctypes.c_uint16),
            ('packed_counts',ctypes.c_uint16),('width_state',ctypes.c_uint16),
            ('source_cursor',ctypes.c_uint16),('destination_cursor',ctypes.c_uint16),
            ('flags',ctypes.c_uint16)]
    class Result(ctypes.Structure):
        _fields_=[('work_value',ctypes.c_uint16),('packed_counts',ctypes.c_uint16),
            ('port',ctypes.c_uint16),('source_cursor',ctypes.c_uint16),
            ('destination_cursor',ctypes.c_uint16),('plane_counter',ctypes.c_uint16),
            ('stack_offset',ctypes.c_uint16),('source_segment',ctypes.c_uint16),
            ('output_segment',ctypes.c_uint16),('flags',ctypes.c_uint16)]
    lib.lmn_draw_aligned_opaque_core.argtypes=[MEM,ctypes.POINTER(Call),ctypes.POINTER(RasterBus)]
    lib.lmn_draw_aligned_opaque_core.restype=Result
    lib.lmn_draw_aligned_opaque_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.c_uint16,
        ctypes.POINTER(RasterBus)]
    lib.lmn_draw_aligned_opaque_adapter.restype=None
    lib._OpaqueCall=Call;lib._OpaqueResult=Result
    return lib

def call_of(lib,regs,game_ds,flags):
    return lib._OpaqueCall(regs['ds'],game_ds,regs['ss'],regs['sp'],regs['cx'],
        regs['dx'],regs['si'],regs['di'],flags)

def oracle_body(case,memory,regs,flags,device):
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20)
    original=bytes(memory);u.mem_write(0,original+original)
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    seen=set();edges=set();previous=None;finished=False;steps=0
    event_flags=flags;flag_mask=0x0fd7;last_op=None
    def code(uc,pc,size,_):
        nonlocal previous,finished,steps,event_flags,flag_mask,last_op
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off==RETF:
            finished=True;uc.emu_stop();return
        if off not in BODY_INS or uc.reg_read(oracle.REG['cs'])!=regs['cs']:
            raise AssertionError(f'{case["name"]}: oracle escaped at {off:04x}')
        if last_op in ('and','or','xor','test'):
            flag_mask=0x0fc7
        elif last_op in ('add','sub','dec','inc','mul','neg'):
            flag_mask=0x0fd7
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        seen.add(off);previous=off;steps+=1
        if steps>3000000:raise AssertionError('Aligned opaque instruction budget exceeded')
        last_op=BODY_INS[off].mnemonic
    def mem_read(uc,access,address,size,value,_):
        for i in range(size):
            raw=address+i;p=raw&0xfffff
            value=device.vga.read(memory,p,event_flags) if VGA_BASE<=p<VGA_END else memory[p]
            uc.mem_write(raw,bytes((value,)))
            device.events.append(('read',p,value,event_flags&0xffff,flag_mask))
    def mem_write(uc,access,address,size,value,_):
        for i in range(size):
            raw=address+i;p=raw&0xfffff;b=(value>>(8*i))&255
            if VGA_BASE<=p<VGA_END:device.vga.write(memory,p,b,event_flags)
            else:memory[p]=b
            if raw>=1<<20:uc.mem_write(raw,bytes((memory[p],)))
            device.events.append(('write',p,b,event_flags&0xffff,flag_mask))
    def out(uc,port,size,value,_):
        if size!=2:raise AssertionError('Renderer used a non-word VGA output')
        device.vga.out(port,value,event_flags)
        device.events.append(('out',port,value,event_flags&0xffff,flag_mask))
    def intr(uc,num,_):raise AssertionError(f'Unexpected INT{num:02x}')
    u.hook_add(UC_HOOK_CODE,code)
    u.hook_add(UC_HOOK_MEM_READ,mem_read)
    u.hook_add(UC_HOOK_MEM_WRITE,mem_write)
    u.hook_add(UC_HOOK_INSN,out,None,1,0,x.UC_X86_INS_OUT)
    u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(oracle.at(regs['cs'],START),0,count=3000000)
    if not finished:raise AssertionError(f'{case["name"]}: oracle did not stop at RETF')
    return u,seen,edges

def compare_core(lib,case):
    memory,regs,flags,game_ds,cdev=prepare(case)
    initial_vga=[bytearray(p) for p in cdev.vga.planes]
    c_memory=bytearray(memory);cdev=TraceDevice(c_memory,case['seed']+0x983b,case.get('read_map',0))
    call=call_of(lib,regs,game_ds,flags)
    c_result=lib.lmn_draw_aligned_opaque_core(
        (ctypes.c_uint8*(1<<20)).from_buffer(c_memory),ctypes.byref(call),ctypes.byref(cdev.bus))
    cdev.check()
    o_memory=bytearray(memory);odev=TraceDevice(o_memory,case['seed']+0x983b,case.get('read_map',0))
    u,seen,edges=oracle_body(case,o_memory,regs,flags,odev);odev.check()
    for name,want in (
        ('ax',c_result.work_value),('bx',regs['bx']),('cx',c_result.packed_counts),
        ('dx',c_result.port),('si',c_result.source_cursor),('di',c_result.destination_cursor),
        ('bp',c_result.plane_counter),('sp',c_result.stack_offset),('ds',c_result.source_segment),
        ('es',c_result.output_segment),('ss',regs['ss']),('cs',regs['cs']),('ip',RETF)):
        got=u.reg_read(oracle.REG[name])
        if got!=want:raise AssertionError(f'{case["name"]}: {name} C={want:04x}/ASM={got:04x}')
    if (c_result.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0x0fd7:
        raise AssertionError(f'{case["name"]}: defined flags C={c_result.flags:04x}/ASM={u.reg_read(x.UC_X86_REG_EFLAGS):04x}')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_memory:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_memory)) if a!=b)
        raise AssertionError(f'{case["name"]}: full RAM differs at {p:05x}: {actual[p]:02x}/{c_memory[p]:02x}')
    if cdev.vga.state()!=odev.vga.state():raise AssertionError(f'{case["name"]}: VGA planes/latches/registers differ')
    if len(cdev.events)!=len(odev.events):
        raise AssertionError(f'{case["name"]}: ordered byte event count {len(cdev.events)}/{len(odev.events)}')
    for n,(a,b) in enumerate(zip(cdev.events,odev.events)):
        if a[:3]!=b[:3] or ((a[3]^b[3])&b[4]):
            raise AssertionError(f'{case["name"]}: ordered event {n} differs {a}/{b}')

    if case.get('independent'):
        independent_planes=[bytearray(p) for p in initial_vga]
        limit=(regs['dx']>>8)&255
        passes=limit if 1<=limit<=3 else 4
        source_segment=case.get('source_segment',0x5000)
        extent=oracle.get16(memory,regs['ds'],SYMS['DrawingSourcePlaneExtent']['address'])
        src_advance=oracle.get16(memory,regs['ds'],SYMS['DrawingSourceRowAdvance']['address'])
        dst_advance=oracle.get16(memory,regs['ds'],SYMS['DrawingActiveDestinationRowAdvance']['address'])
        width=regs['cx']&255;height=(regs['cx']>>8)&255
        row_count=height or 256
        direction=-1 if flags&0x400 else 1
        base_si=regs['si'];base_di=regs['di']
        source_stride=(width*direction+src_advance)&0xffff
        destination_stride=(width*direction+dst_advance)&0xffff
        # The first all-plane pass selects source for plane 0 and set/reset
        # zero for planes 1..3. Later passes replace one selected plane.
        for row in range(row_count):
            target_di=(base_di+row*destination_stride)&0xffff
            target_si=(base_si+row*source_stride)&0xffff
            for _ in range(width):
                source=memory[physical(source_segment,target_si)]
                for plane_no in range(4):
                    independent_planes[plane_no][target_di]=source if plane_no==0 else 0
                target_si=(target_si+direction)&0xffff
                target_di=(target_di+direction)&0xffff
        for plane in range(1,passes):
            for row in range(row_count):
                target_di=(base_di+row*destination_stride)&0xffff
                target_si=(base_si+plane*extent+row*source_stride)&0xffff
                for _ in range(width):
                    source=memory[physical(source_segment,target_si)]
                    independent_planes[plane][target_di]=source
                    target_si=(target_si+direction)&0xffff
                    target_di=(target_di+direction)&0xffff
        if cdev.vga.planes!=independent_planes:
            diff=next((plane,offset) for plane in range(4)
                for offset,(actual_byte,expected_byte) in enumerate(zip(cdev.vga.planes[plane],independent_planes[plane]))
                if actual_byte!=expected_byte)
            plane,offset=diff
            writes=[(p-VGA_BASE,v) for kind,p,v,_f in cdev.events if kind=='write' and VGA_BASE<=p<VGA_END]
            raise AssertionError(f'{case["name"]}: independent source-plane footprint differs at {plane}:{offset:04x} {cdev.vga.planes[plane][offset]:02x}/{independent_planes[plane][offset]:02x}; writes={writes[:20]} source={regs["si"]:04x} dest={regs["di"]:04x} advances={src_advance:04x}/{dst_advance:04x}')

    return seen,edges,c_result

def isolated_return(lib,case):
    memory,regs,flags,game_ds,device=prepare(case)
    native_memory=bytearray(memory);native_device=TraceDevice(native_memory,case['seed']+0x983b,case.get('read_map',0))
    native_regs=Regs(**regs,flags=flags)
    lib.lmn_draw_aligned_opaque_adapter((ctypes.c_uint8*(1<<20)).from_buffer(native_memory),
        ctypes.byref(native_regs),game_ds,ctypes.byref(native_device.bus))
    native_device.check()
    # Snapshot the original instruction boundary, then probe only RETF without
    # memory hooks. Unicorn's read-hook RETF artifact remains outside this probe.
    o_memory=bytearray(memory);odev=TraceDevice(o_memory,case['seed']+0x983b,case.get('read_map',0))
    u,_,_=oracle_body(case,o_memory,regs,flags,odev)
    snapshot=bytes(u.mem_read(0,1<<20));boundary={n:u.reg_read(r) for n,r in oracle.REG.items()}
    boundary_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    probe=Uc(UC_ARCH_X86,UC_MODE_16);probe.mem_map(0,2<<20);probe.mem_write(0,snapshot+snapshot)
    for name,reg in oracle.REG.items():probe.reg_write(reg,boundary[name])
    probe.reg_write(x.UC_X86_REG_EFLAGS,boundary_flags)
    probe.emu_start(oracle.at(regs['cs'],RETF),0,count=1)
    for name,reg in oracle.REG.items():
        want=probe.reg_read(reg);got=getattr(native_regs,name)
        if want!=got:raise AssertionError(f'{case["name"]}: adapter RETF {name} C={got:04x}/ASM={want:04x}')
    expected_ram=bytes(probe.mem_read(0,1<<20))
    if expected_ram!=native_memory:
        p=next(i for i,(a,b) in enumerate(zip(expected_ram,native_memory)) if a!=b)
        raise AssertionError(f'{case["name"]}: adapter RAM differs at {p:05x}')

def raw_bus_parity(lib):
    case=dict(name='nullbus-parity',seed=0x4d,plane_limit=2,width=2,height=1)
    memory,regs,flags,game_ds,_=prepare(case)
    null_memory=bytearray(memory);raw_memory=bytearray(memory)
    call=call_of(lib,regs,game_ds,flags)
    null_result=lib.lmn_draw_aligned_opaque_core(
        (ctypes.c_uint8*(1<<20)).from_buffer(null_memory),ctypes.byref(call),None)
    def rd(_ctx,_mem,address,_flags):return raw_memory[address&0xfffff]
    def wr(_ctx,_mem,address,value,_flags):raw_memory[address&0xfffff]=value
    def out(_ctx,_port,_value,_flags):pass
    bus=RasterBus(None,VGA_READ(rd),VGA_WRITE(wr),VGA_OUT(out))
    raw_result=lib.lmn_draw_aligned_opaque_core(
        (ctypes.c_uint8*(1<<20)).from_buffer(raw_memory),ctypes.byref(call),ctypes.byref(bus))
    if null_memory!=raw_memory or bytes(null_result)!=bytes(raw_result):
        raise AssertionError('Null-bus and raw-RAM callback parity differs; this is not VGA equivalence')

def adapter_permissive_boundaries(lib):
    # Keep SP=FFFE as a native two-POP contract. The original body is compared
    # at 9966, while this boundary is independently checked byte by byte.
    case=dict(name='adapter-permissive-SP-boundary',seed=0x7e,plane_limit=1,
        width=1,height=1,sp=0xfffe,return_boundary=True)
    memory,regs,flags,game_ds,device=prepare(case)
    native=bytearray(memory);ndev=TraceDevice(native,case['seed']+0x983b)
    r=Regs(**regs,flags=flags)
    lib.lmn_draw_aligned_opaque_adapter((ctypes.c_uint8*(1<<20)).from_buffer(native),
        ctypes.byref(r),game_ds,ctypes.byref(ndev.bus))
    # Independently run the logical body, then perform the adapter's four
    # sequential reads with 16-bit SP stepping and 20-bit physical wrap.
    logical=bytearray(memory);ldev=TraceDevice(logical,case['seed']+0x983b)
    call=call_of(lib,regs,game_ds,flags)
    body=lib.lmn_draw_aligned_opaque_core((ctypes.c_uint8*(1<<20)).from_buffer(logical),
        ctypes.byref(call),ctypes.byref(ldev.bus))
    sp=body.stack_offset;values=[]
    for _ in range(4):
        values.append(ldev.vga.read(logical,physical(regs['ss'],sp),body.flags)
            if VGA_BASE<=physical(regs['ss'],sp)<VGA_END else logical[physical(regs['ss'],sp)])
        sp=(sp+1)&0xffff
    if r.ip!=(values[0]|values[1]<<8) or r.cs!=(values[2]|values[3]<<8) or r.sp!=sp:
        raise AssertionError('Permissive far adapter did not consume low/high bytes with SP wrap')

def main():
    if len(ALL_INS)!=149 or sum(i.size for i in ALL_INS.values())!=298:
        raise AssertionError(f'Unexpected aligned opaque static accounting: {len(ALL_INS)} sites/{sum(i.size for i in ALL_INS.values())} bytes')
    if any(IMAGE[a]!=0x90 for a in UNKNOWN):raise AssertionError('The excluded UNKNOWN bytes changed')
    fixture_cases=cases();baseline=library();seen=set();edges=set();reports=[]
    for case in fixture_cases:
        sites,case_edges,result=compare_core(baseline,case)
        seen|=sites;edges|=case_edges
        reports.append(dict(name=case['name'],seed=case['seed'],input=case,
            result={n:getattr(result,n) for n,_ in result._fields_}))
    if seen!=set(BODY_INS):raise AssertionError(f'C-covered sites differ: {set(BODY_INS)-seen}')
    if edges!=EDGES:raise AssertionError(f'C branch edges differ: missing={EDGES-edges},extra={edges-EDGES}')
    original_return_cases=[]
    original_return_exclusions=[]
    for case in fixture_cases:
        if case.get('stack_device') or case.get('return_boundary'):
            original_return_exclusions.append(case['name'])
            continue
        isolated_return(baseline,case)
        original_return_cases.append(case['name'])
    if len(original_return_cases)!=52:
        raise AssertionError(f'Expected 52 isolated original RETF probes, got {len(original_return_cases)}')
    adapter_permissive_boundaries(baseline)
    raw_bus_parity(baseline)
    mutations=[]
    for mutation in (1,2,3):
        mutant=library(mutation);detected=None
        for case in fixture_cases:
            try:compare_core(mutant,case)
            except AssertionError:detected=case['name'];break
        if detected is None:raise AssertionError(f'Compiled opaque mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=detected))
    input_paths=(
        'assets/vgalemmi.exe','c/aligned_opaque.c','c/aligned_opaque.h','c/special_blit.h',
        'c/regs.h','c/lemmings_sym.h','tests/aligned_opaque.py','tests/minimap_vga.py',
        'tests/dat_io.py','tests/dat_io_c.py','tools/common.py','tools/unpack.py',
        'tools/cbuild.py','tools/difftest.py','tools/coverage.py','tools/symtab.py',
        'tools/graph.py','tools/verify.py','metadata/symbols.json',
        'metadata/inputs.json','build/unpack.json','src/planar_drawing.asm')
    public_cases=[{k:v for k,v in c.items()} for c in fixture_cases]
    write_json(BUILD/'aligned-opaque-differential.json',dict(
        image='main',image_sha256=sha(IMAGE),range_inclusive='983B..9966',
        range_sha256=sha(IMAGE[START:END]),unknown_bytes=[dict(address=a,value=IMAGE[a]) for a in sorted(UNKNOWN)],
        case_count=len(fixture_cases),cases=public_cases,mutation_count=3,
        mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen|({RETF} if original_return_cases else set())),
        body_instruction_addresses=sorted(seen),
        executed_adapter_instruction_addresses=([RETF] if original_return_cases else []),
        branch_edges=sorted([list(e) for e in edges]),physical_code_bytes=300,
        translated_code_bytes=298,c_body_bytes=297,adapter_code_bytes=1,
        physical_instruction_sites=149,c_body_instruction_sites=len(BODY_INS),
        adapter_instruction_sites=1,
        adapter_instruction_addresses=[RETF],far_return_instruction_site_adapter=RETF,
        original_retf_probe_address=RETF,original_retf_probe_case_count=len(original_return_cases),
        original_retf_probe_cases=original_return_cases,
        original_retf_probe_exclusions=original_return_exclusions,
        permissive_adapter_only_case_count=1,
        permissive_adapter_only_cases=['far-return-SP-FFFF-boundary'],
        ordered_event_defined_flag_masks={
            'entry_and_after_add_or_dec':'0x0FD7',
            'after_logic_AF_undefined':'0x0FC7'},
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in input_paths},
        device_contract='tests/minimap_vga.py unchained A000 64KiB aperture; read mode0, write mode0, latches, map/set-reset/bit-mask and word-port order; no IRQ scheduling',
        domain='Constructed RAM and quiescent IRQs. Main body starts at 983B, stops before RETF target; 988B shared entry remains outside C and no arbitrary incoming shared-tail state is claimed. Both DF values, unchecked byte/row counts, plane-limit 0/>4, live DS/SS and far-return aliases included.'))
    print(f'PASS aligned opaque: {len(fixture_cases)} cases, {len(seen)} body sites, {len(edges)} branch edges; 3 compiled mutations detected')

if __name__=='__main__':main()
