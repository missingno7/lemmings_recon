"""Bounded packed terrain caller connected to the native planar renderer."""
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
    UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN, UC_HOOK_INTR)
from unicorn import x86_const as x
import aligned_masked as common
import drawing_render as render
import drawing_bitmap as bitmap
import drawing_aligned_render as aligned
import dat_io as oracle
from dat_io_c import Regs, MEM
from aligned_read_mask import Ports, OUT_BYTE, IN_BYTE
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, read_json, write_json
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
START, END = 0x7c67, 0x7cbc
MAX_STEPS = 2_000_000
common.MAX_BUS_EVENTS = 1_000_000
common.MAX_VGA_EVENTS = 300_000
common.EventTrace._KINDS = {**common.EventTrace._KINDS, 'outb':3, 'inb':4}
MD = capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16)
MD.detail = True
UNKNOWN = {0x88aa,0x8add,0x8cf4,0x8f8d,0x9339,0x94c7,0x9507,
           0x9659,0x98f4,0x9932}
INS = {i.address:i for lo,hi in ((START,END),(0x8822,0x9a90))
       for i in MD.disasm(IMAGE[lo:hi],lo) if i.address not in UNKNOWN and i.address!=0x9996}
LOCAL = {p for p in INS if START<=p<END}
BRANCHES = {p for p,i in INS.items() if i.group(capstone.CS_GRP_JUMP)
            or i.mnemonic.startswith('loop')}
LOCAL_EDGES = {(p,i.operands[0].imm&65535) for p,i in INS.items() if p in BRANCHES and p in LOCAL}
LOCAL_EDGES |= {(p,p+i.size) for p,i in INS.items() if p in BRANCHES and p in LOCAL and i.mnemonic!='jmp'}
FAMILIES = {v[0]:k for k,v in {**aligned.FAMILIES,**bitmap.NEW,
                              **bitmap.effects.SHIFTED}.items()}
GROUND = {p.name:p.read_bytes() for p in sorted((ROOT/'assets').glob('ground*o.dat'))}


class TerrainCall(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint16) for n in ('data_segment','game_data_segment',
        'stack_segment','stack_offset','code_segment','packed_horizontal',
        'packed_vertical','source_cursor','output_segment','flags')]


class SourceState(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint16) for n in ('work_value','second_source_cursor',
        'packed_counts','width_state','source_cursor','destination_cursor','control',
        'stack_offset','flags','continuation')]


class PlanState(ctypes.Structure):
    _fields_=[('state',SourceState),('changed_return',ctypes.c_uint16)]


class RenderState(ctypes.Structure):
    _fields_=[('plan',PlanState),('source_segment',ctypes.c_uint16),
        ('output_segment',ctypes.c_uint16),('body_returned',ctypes.c_uint16)]


class TerrainResult(ctypes.Structure):
    _fields_=[('drawing',RenderState),('code_segment',ctypes.c_uint16),
        ('ready_to_return',ctypes.c_uint16),('changed_far_return',ctypes.c_uint16)]


def field(name):
    return SYMS[name]['address']


def cases():
    out=[]
    def add(name,**kw):
        out.append(dict(name=name,seed=len(out),**kw))
    for flags in range(8):
        for shift in range(8):
            for df in (0,1):
                for ignored_bit in (0,1):
                    add(f'packed-{flags}-{shift}-{df}-{ignored_bit}',flags=flags,
                        left=128+shift,top=5,index=2,ignored_bit=ignored_bit,df=df,
                        width=24,height=3,independent=True)
    for ground in GROUND:
        for index in range(64):
            add(f'{ground}-terrain-{index}',ground=ground,index=index,
                flags=index%8,left=128+index%8,top=5,df=0,independent=True)
    for top in (-260,-256,-5,-4,0,159,163,164,251):
        add(f'signed-top-{top}',top=top,height=8,left=131,index=2,independent=True)
    for left in (0,7,1656,1663,1664,8191):
        add(f'clip-left-{left}',left=left,width=24,height=3,index=2,independent=True)
    for sp in (0,1,3,0xfffe,0xffff):
        add(f'stack-wrap-{sp:04x}',sp=sp,left=8191,width=8,height=1,index=2,
            expected='outer-return')
    add('stack-physical-wrap',ss=0xffff,left=8191,width=8,height=1,index=2,
        expected='outer-return')
    add('incoming-DS-distinct',ds=0x3000,left=131,width=24,height=1,index=2)
    add('source-physical-and-offset-wrap',source_segment=0xffff,source=0xfff0,
        mask=0xffe0,left=131,width=24,height=3,index=2,independent=True)
    add('record-fields-overwritten-by-saved-SI',same_segments=True,sp=0x1d0d,
        saved_si=0x0108,width=24,height=3,index=0,left=131)
    add('record-fields-overwritten-by-saved-coordinates',same_segments=True,
        sp=0x1d11,index=0,left=16,top=0,width=24,height=3)
    add('live-SI-scratch-alias-preserves-far-CS',same_segments=True,sp=0x66fb,
        load=0x1010,width=128,height=1,left=8191,index=2,saved_si=0x4567,
        expected='outer-return',expected_si=0x1000)
    add('changed-far-CS-stops-before-caller-pop',same_segments=True,sp=0x66fb,
        load=0x1010,width=16,height=1,left=8191,index=2,saved_si=0x4567,
        expected='changed-child-far',expected_cs=0x0210)
    add('dirty-near-return-low-byte-alias',sp=0x4806,base=0x47fd,dirty=255,
        left=16,top=0,width=8,height=8,index=2,expected='changed-child-near',expected_ip=0x8801)
    add('dirty-near-return-high-byte-alias',sp=0x4806,base=0x47fe,dirty=255,
        left=16,top=0,width=8,height=8,index=2,expected='changed-child-near',expected_ip=0x015e)
    add('dirty-map-normal',dirty=255,left=131,top=5,width=24,height=3,index=2,
        independent=True)
    # The malformed selector mutant still reads constructed finite metadata.
    add('selector-bit6-mutation-witness',index=2,ignored_bit=1,left=131,top=5,
        width=24,height=3,alternate_record=True,independent=True)
    add('signed-shift-mutation-witness',index=2,left=131,top=-5,width=24,height=8,
        independent=True)
    add('effect-enable-mutation-witness',flags=1,index=2,left=131,top=5,width=24,
        height=3,independent=True)
    return out


def record(memory,ds,index,width,height,source,mask):
    base=field('GroundTerrainGraphicsRecords')+8*index
    for n,v in enumerate((width,height)):
        memory[oracle.at(ds,base+n)] = v
    oracle.put16(memory,ds,base+2,source)
    oracle.put16(memory,ds,base+4,mask)
    memory[oracle.at(ds,base+6)] = 0xa5
    memory[oracle.at(ds,base+7)] = 0x5a


def prepare(case):
    rng=random.Random(START+case['seed'])
    load=case.get('load',(0x1010,0x1213,0x2345)[case['seed']%3])
    memory=bytearray(rng.randbytes(1<<20))
    memory[load<<4:(load<<4)+len(IMAGE)] = relocated(IMAGE,ORACLE['relocations'],load)
    ds=case.get('ds',(load+0x9a9)&65535)
    game_ds=(load+0x9a9)&65535
    ss=ds if case.get('same_segments') else case.get('ss',0x7000)
    if case.get('ground'):
        for n,v in enumerate(GROUND[case['ground']]):
            memory[oracle.at(ds,field('GroundResourceBuffer')+n)]=v
    else:
        record(memory,ds,case.get('index',2),case.get('width',24),case.get('height',3),
               case.get('source',0x2000),case.get('mask',0x4000))
    if case.get('alternate_record'):
        record(memory,ds,case['index']+64,8,1,0x6000,0x7000)
    for segment in {ds,game_ds}:
        for name,value in (('DrawingWidthPixels',1664),('DrawingHeight',164),
            ('DrawingPitchBytes',208),('DrawingOrigin',0x1000),
            ('DrawingPageByteOffset',0x0200),('DrawingDirtyCellMapOffset',case.get('base',0x1000)),
            ('GraphicsResourceSegment',case.get('source_segment',0x5000)),
            ('DrawingSourcePlaneExtent',0x31),('DrawingSourceRowAdvance',7),
            ('DrawingActiveDestinationRowAdvance',208)):
            oracle.put16(memory,segment,field(name),value)
        memory[oracle.at(segment,field('DrawingDirtyCellsEnabledByte'))]=case.get('dirty',0)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=START,ds=ds,es=0x6000,ss=ss,sp=case.get('sp',0x8000),
        ax=(case.get('left',131)&0x1fff)|(case.get('flags',0)<<13),
        bx=(((case.get('top',5)+4)&0x1ff)<<7)|case.get('index',2)|
           (case.get('ignored_bit',0)<<6),si=case.get('saved_si',0x4567))
    flags=2|((case['seed']*0x95)&0xad5)
    flags=(flags&~0x400)|(0x400 if case.get('df') else 0)
    oracle.put16(memory,ss,regs['sp'],case.get('outer_ip',0xeed1))
    return memory,regs,flags,game_ds


def library(directory,mutation=0):
    lib=ctypes.CDLL(str(build(Path(directory)/f'terrain-drawing-{mutation}.dll',mutation,'terrain_drawing')))
    lib.lmn_draw_terrain_piece_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.c_uint16,
        ctypes.POINTER(common.RasterBus),ctypes.POINTER(Ports)]
    lib.lmn_draw_terrain_piece_adapter.restype=None
    lib.lmn_draw_terrain_piece_core.argtypes=[MEM,ctypes.POINTER(TerrainCall),
        ctypes.POINTER(common.RasterBus),ctypes.POINTER(Ports)]
    lib.lmn_draw_terrain_piece_core.restype=TerrainResult
    return lib


def check_device(device,label):
    if len(device.vga.trace)>common.MAX_VGA_EVENTS:
        device.vga.trace.pop()
        device.vga_exhausted=True
    device.check(label)


def byte_ports(device):
    fixture=aligned.BytePortFixture()
    @OUT_BYTE
    def out(_ctx,_mem,port,value,flags):
        try:
            fixture.out_byte(device.vga,port,value,flags)
            device.events.add('outb',port,value,flags)
            check_device(device,'native byte output')
        except common.GuardExhaustion as error:
            common.exit_worker(86,str(error))
        except BaseException as error:
            common.exit_worker(87,f'byte output failed:{error}')
    @IN_BYTE
    def inp(_ctx,_mem,port,flags):
        try:
            value=fixture.in_byte(device.vga,port,flags,{})
            device.events.add('inb',port,value,flags)
            check_device(device,'native byte input')
            return value
        except common.GuardExhaustion as error:
            common.exit_worker(86,str(error))
        except BaseException as error:
            common.exit_worker(87,f'byte input failed:{error}')
    return Ports(None,out,inp)


def original(case,device,regs,flags,stop_before_outer=False):
    u=Uc(UC_ARCH_X86,UC_MODE_16)
    u.mem_map(0,2<<20)
    u.mem_write(0,bytes(device.memory)*2)
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    seen,edges=set(),set()
    previous=None
    last=None
    mask=0xfd7
    event_flags=flags
    steps=0
    frames=[]
    pending_near=None
    pause=None
    boundary=None
    failure=[]
    child_entry=None
    body_entry=None
    body_memory=None
    body_planes=None
    body_address=None

    def fail(message):
        if not failure:failure.append(message)
        u.emu_stop()

    def code(uc,pc,_size,_):
        nonlocal previous,last,mask,event_flags,steps,pending_near,pause,boundary
        nonlocal child_entry,body_entry,body_memory,body_planes,body_address
        cs=uc.reg_read(oracle.REG['cs'])
        off=uc.reg_read(oracle.REG['ip'])
        if last is not None:
            mask=render._defined_mask(last,mask)
        if pending_near is not None:
            expected=pending_near;pending_near=None
            if expected is False:
                boundary=('outer-return',cs,off);uc.emu_stop();return
            frames.pop()
            if (cs,off)!=expected:
                boundary=('changed-child-near',cs,off);uc.emu_stop();return
        if cs!=regs['cs'] or off not in INS:
            fail(f'{case["name"]}: original escaped at{cs:04x}:{off:04x};last={last},previous={previous},frames={frames}');return
        if stop_before_outer and off==0x7cbb:
            boundary=('ready-return',cs,off);uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        ins=INS[off]
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        steps+=1
        if steps>MAX_STEPS:fail('original step budget exhausted');return
        seen.add(off)
        previous=off;last=ins.mnemonic
        if off==0x8822:
            child_entry={n:uc.reg_read(r) for n,r in oracle.REG.items()}
            child_entry['flags']=event_flags
        if off in FAMILIES and body_entry is None:
            body_address=off
            body_entry={n:uc.reg_read(r) for n,r in oracle.REG.items()}
            body_entry['flags']=event_flags
            body_memory=bytes(device.memory)
            body_planes=[bytearray(p) for p in device.vga.planes]
        if off==0x7cb5:
            frames.append((regs['cs'],0x7cba))
        elif ins.mnemonic=='call':
            frames.append((cs,off+ins.size))
        elif ins.mnemonic=='retf':
            pause=(cs,off,event_flags);uc.emu_stop()
        elif ins.mnemonic=='ret':
            pending_near=frames[-1] if frames else False

    def read(uc,_access,address,size,_value,_):
        for n in range(size):
            raw=address+n;p=raw&0xfffff
            try:
                value=device.vga.read(device.memory,p,event_flags)
                device.events.add('read',p,value,event_flags,mask)
                uc.mem_write(raw,bytes((value,)))
                check_device(device,'original read')
            except BaseException as error:fail(str(error));return

    def write(uc,_access,address,size,value,_):
        for n in range(size):
            raw=address+n;p=raw&0xfffff;byte=(value>>(8*n))&255
            try:
                device.vga.write(device.memory,p,byte,event_flags)
                device.events.add('write',p,byte,event_flags,mask)
                if raw>=1<<20:uc.mem_write(p,bytes((byte,)))
                check_device(device,'original write')
            except BaseException as error:fail(str(error));return

    fixture=aligned.BytePortFixture()
    def out(uc,port,size,value,_):
        try:
            if size==2:
                device.vga.out(port,value,event_flags)
                device.events.add('out',port,value,event_flags,mask)
            elif size==1:
                fixture.out_byte(device.vga,port,value,event_flags)
                device.events.add('outb',port,value,event_flags,mask)
            else:raise common.VerificationFailure('unsupported output width')
            check_device(device,'original output')
        except BaseException as error:fail(str(error))

    def inp(uc,port,size,_):
        try:
            if size!=1:raise common.VerificationFailure('unsupported input width')
            value=fixture.in_byte(device.vga,port,event_flags,{})
            device.events.add('inb',port,value,event_flags,mask)
            check_device(device,'original input')
            return value
        except BaseException as error:fail(str(error));return 0

    code_hook=u.hook_add(UC_HOOK_CODE,code)
    read_hook=u.hook_add(UC_HOOK_MEM_READ,read)
    u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.hook_add(UC_HOOK_INSN,out,None,1,0,x.UC_X86_INS_OUT)
    u.hook_add(UC_HOOK_INSN,inp,None,1,0,x.UC_X86_INS_IN)
    u.hook_add(UC_HOOK_INTR,lambda uc,num,_:fail(f'unexpected INT{num:02x}'))
    while boundary is None and not failure:
        pc=(u.reg_read(oracle.REG['cs'])<<4)+u.reg_read(oracle.REG['ip'])
        u.emu_start(pc,0,count=MAX_STEPS-steps+1)
        if pause is None:
            if boundary is None and not failure:fail('original instruction budget exhausted')
            break
        cs,ip,ret_flags=pause;pause=None
        if not frames:fail('far return without a known caller frame');break
        expected=frames.pop()
        ss=u.reg_read(oracle.REG['ss']);sp=u.reg_read(oracle.REG['sp'])
        # Record original bus-visible words, then execute the original RETF
        # without its read hook. No opcode or target is patched. Word high bytes
        # use physical+1; SP wraps only between the two words.
        for word in range(2):
            offset=(sp+2*word)&65535
            for n in range(2):
                raw=(ss<<4)+offset+n;p=raw&0xfffff
                value=device.vga.read(device.memory,p,ret_flags)
                device.events.add('read',p,value,ret_flags,mask)
                u.mem_write(raw,bytes((value,)))
        check_device(device,'original far-return reads')
        u.hook_del(code_hook);u.hook_del(read_hook)
        u.ctl_remove_cache(0,2<<20)
        u.emu_start((cs<<4)+ip,0,count=1)
        actual=(u.reg_read(oracle.REG['cs']),u.reg_read(oracle.REG['ip']))
        code_hook=u.hook_add(UC_HOOK_CODE,code)
        read_hook=u.hook_add(UC_HOOK_MEM_READ,read)
        u.ctl_remove_cache(0,2<<20)
        if actual!=expected:boundary=('changed-child-far',*actual)
    if failure:raise common.VerificationFailure(f'{case["name"]}: {failure[0]}')
    device.check(case['name'])
    result={n:u.reg_read(r) for n,r in oracle.REG.items()}
    result['flags']=u.reg_read(x.UC_X86_REG_EFLAGS)
    return result,mask,seen,edges,boundary,child_entry,(body_address,body_entry,body_memory,body_planes)


def compare(lib,case):
    memory,regs,flags,game_ds=prepare(case)
    c=common.TraceDevice(bytearray(memory),case['seed']+START)
    o=common.TraceDevice(bytearray(memory),case['seed']+START)
    state=Regs(**regs,flags=flags)
    ports=byte_ports(c)
    lib.lmn_draw_terrain_piece_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c.memory),
        ctypes.byref(state),game_ds,ctypes.byref(c.bus),ctypes.byref(ports))
    c.check(case['name'])
    actual,mask,seen,edges,boundary,child,body=original(case,o,regs,flags)
    for n in oracle.REG_NAMES:
        common.require(getattr(state,n)==actual[n],
            f'{case["name"]}:{n} C={getattr(state,n):04x}/ASM={actual[n]:04x};{boundary}')
    common.require(not((state.flags^actual['flags'])&mask),f'{case["name"]}:defined flags differ')
    common.require(c.memory==o.memory,f'{case["name"]}:whole RAM differs')
    common.compare_event_traces(c.events,o.events,case['name'])
    common.require(c.vga.state()==o.vga.state(),f'{case["name"]}:VGA state differs')
    common.require(render._vga_trace_equal(c.vga.trace,o.vga.trace),f'{case["name"]}:VGA/port order differs')
    if case.get('expected'):
        common.require(boundary[0]==case['expected'],f'{case["name"]}:wrong boundary {boundary}')
    for name,reg in (('expected_si','si'),('expected_cs','cs'),('expected_ip','ip')):
        if name in case:common.require(actual[reg]==case[name],f'{case["name"]}:wrong live {reg}')
    if case.get('independent'):
        base=field('GroundTerrainGraphicsRecords')+8*(regs['bx']&63)
        packed=regs['ax'];y=regs['bx'] if regs['bx']<0x8000 else regs['bx']-65536
        control=15|((packed>>7)&0xc0)|(0xf00 if packed&0x2000 else 0)|(0x8000 if packed&0x8000 else 0)
        expected=dict(ax=packed&8191,bx=((y//128)-4)&65535,
            dx=memory[oracle.at(regs['ds'],base)],
            cx=0x400|memory[oracle.at(regs['ds'],base+1)],
            si=oracle.get16(memory,regs['ds'],base+2),
            di=oracle.get16(memory,regs['ds'],base+4),bp=control)
        common.require(child is not None,f'{case["name"]}:caller never reached renderer')
        for reg,value in expected.items():
            common.require(child[reg]==value,f'{case["name"]}:independent child input {reg}')
        address,entry,scratch,planes=body
        if entry is not None:
            bitmap.configure(FAMILIES[address])
            footprint=render._independent_planes(planes,scratch,entry,game_ds)
            common.require(footprint==o.vga.planes,f'{case["name"]}:independent whole-plane footprint')
        for delta in (6,7):
            p=oracle.at(regs['ds'],base+delta)
            common.require(o.memory[p]==memory[p],f'{case["name"]}:unused record byte changed')
    for lo,hi in ((START,END),(0x8822,0x9a90)):
        expected=relocated(IMAGE,ORACLE['relocations'],regs['cs'])[lo:hi]
        p=(regs['cs']<<4)+lo
        if o.memory[p:p+hi-lo]!=expected:
            raise common.VerificationFailure(f'{case["name"]}:executing code changed')
    return seen,edges,boundary,body[0]


def compare_core(lib,case):
    memory,regs,flags,game_ds=prepare(case)
    c=common.TraceDevice(bytearray(memory),case['seed']+START)
    o=common.TraceDevice(bytearray(memory),case['seed']+START)
    ports=byte_ports(c)
    call=TerrainCall(regs['ds'],game_ds,regs['ss'],regs['sp'],regs['cs'],
        regs['ax'],regs['bx'],regs['si'],regs['es'],flags)
    result=lib.lmn_draw_terrain_piece_core(
        (ctypes.c_uint8*(1<<20)).from_buffer(c.memory),ctypes.byref(call),
        ctypes.byref(c.bus),ctypes.byref(ports))
    actual,mask,seen,edges,boundary,_child,_body=original(case,o,regs,flags,True)
    state=result.drawing.plan.state
    values=dict(ax=state.work_value,bx=state.second_source_cursor,
        cx=state.packed_counts,dx=state.width_state,si=state.source_cursor,
        di=state.destination_cursor,bp=state.control,sp=state.stack_offset,
        ds=result.drawing.source_segment,es=result.drawing.output_segment,
        cs=result.code_segment,ip=state.continuation)
    for name,value in values.items():
        common.require(value==actual[name],f'{case["name"]}:core {name} differs')
    common.require(not((state.flags^actual['flags'])&mask),f'{case["name"]}:core flags differ')
    common.require(result.ready_to_return==int(boundary[0]=='ready-return'),
        f'{case["name"]}:core ready-to-return status differs')
    common.require(result.changed_far_return==int(boundary[0]=='changed-child-far'),
        f'{case["name"]}:core far-return status differs')
    common.require(result.drawing.plan.changed_return==int(boundary[0]=='changed-child-near'),
        f'{case["name"]}:core near-return status differs')
    common.require(c.memory==o.memory,f'{case["name"]}:core RAM differs')
    common.compare_event_traces(c.events,o.events,case['name'])
    common.require(c.vga.state()==o.vga.state(),f'{case["name"]}:core VGA differs')
    common.require(render._vga_trace_equal(c.vga.trace,o.vga.trace),f'{case["name"]}:core VGA order differs')
    c.check(case['name']);o.check(case['name'])
    return seen,edges


def worker(directory):
    baseline=library(directory)
    group=cases()
    seen,edges=set(),set()
    body_counts={}
    boundaries={}
    for case in group:
        sites,branches,boundary,body=compare(baseline,case)
        seen|=sites;edges|=branches
        boundaries[boundary[0]]=boundaries.get(boundary[0],0)+1
        if body is not None:body_counts[FAMILIES[body]]=body_counts.get(FAMILIES[body],0)+1
        gc.collect()
    core_cases=[group[0],*[c for c in group if c['name'] in (
        'live-SI-scratch-alias-preserves-far-CS','changed-far-CS-stops-before-caller-pop',
        'dirty-near-return-low-byte-alias','dirty-near-return-high-byte-alias','stack-wrap-0001')]]
    for case in core_cases:
        sites,branches=compare_core(baseline,case)
        seen|=sites;edges|=branches;gc.collect()
    if not LOCAL<=seen or not LOCAL_EDGES<=edges:
        raise common.VerificationFailure('terrain caller site/edge coverage incomplete')
    witnesses={1:'selector-bit6-mutation-witness',2:'signed-shift-mutation-witness',
        3:'effect-enable-mutation-witness',4:'changed-far-CS-stops-before-caller-pop',
        5:'live-SI-scratch-alias-preserves-far-CS'}
    mutations=[]
    for mutation,name in witnesses.items():
        case=next(c for c in group if c['name']==name)
        try:compare(library(directory,mutation),case)
        except common.Mismatch as error:
            mutations.append(dict(mutation=mutation,case=name,reason=str(error)))
        else:raise common.VerificationFailure(f'TERRAIN_MUTATION={mutation} survived')
        finally:gc.collect()
    sources=('terrain_drawing','drawing_render','drawing_plan','drawing_inputs','drawing_clip',
        'drawing_dirty','drawing_dispatch','drawing_source','aligned_opaque','aligned_masked',
        'aligned_protected','aligned_read_mask','aligned_mask_effects','shifted_mask_effects',
        'shifted_opaque','shifted_masked','shifted_protected','shifted_read_mask')
    paths=tuple('c/'+n+ext for n in sources for ext in ('.c','.h'))
    paths+=('c/regs.h','c/special_blit.h','c/lemmings_sym.h','metadata/symbols.json',
        'tests/terrain_drawing.py','tests/aligned_masked.py','tests/aligned_read_mask.py',
        'tests/drawing_render.py','tests/drawing_bitmap.py','tests/drawing_aligned_render.py',
        'tests/drawing_masked_render.py','tests/drawing_shifted_render.py','tests/minimap_vga.py',
        'tests/drawing_plan.py','tests/drawing_inputs.py','tests/drawing_dispatch.py',
        'tests/drawing_source.py','tests/drawing_clip.py','tests/drawing_dirty.py','tests/special_blit.py',
        'tests/dat_io.py','tests/dat_io_c.py','tools/unpack.py','tools/cbuild.py',
        'tools/difftest.py','tools/coverage.py','tools/bounded_process.py')
    paths+=tuple('assets/'+name for name in GROUND)
    write_json(BUILD/'terrain-drawing-differential.json',dict(image='main',image_sha256=sha(IMAGE),
        range_inclusive='7C67..7CBB',range_sha256=sha(IMAGE[START:END]),
        translated_code_bytes=85,caller_instruction_addresses=sorted(LOCAL),
        executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),
        case_count=len(group),cases=group,body_counts=body_counts,boundaries=boundaries,
        core_boundary_case_count=len(core_cases),core_boundary_cases=[c['name'] for c in core_cases],
        mutation_count=len(mutations),mutations_detected=mutations,
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Native7C67 packed terrain caller,live64record reads and farCALL8822 composition. Constructedsourcebytes with all320 supplied GROUNDmetadatarecords; no gameboot. WholeRAM/regs/definedflags/orderedbus/VGA,independentpackedinput/wholeplane/unusedrecord checks. OriginalRETF readhook observation uses intact opcode and actual bus-visible frame,then resumes7CBA only when actualtarget matches. Changedchildreturns exposed before target execution; IRQ/deviceownership/producerallocation/UNKNOWN remain open.'))
    print(f'PASS terrain drawing:{len(group)} cases,{len(LOCAL)} caller/{len(seen)} integrated sites,{len(edges)} edges;{len(mutations)} mutants;{boundaries}')


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
    elif len(sys.argv)==1:
        (BUILD/'terrain-drawing-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='terrain-drawing-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],
                        cwd=ROOT,timeout=180)
    else:raise SystemExit('Unexpected terrain_drawing arguments')
