"""SetDrawingLayout against its bounded original far-call contract."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['SetDrawingLayout'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
KNOWN_CODE_BYTES={byte for symbol in SYMS.values() if symbol.get('kind')=='entry'
                   for byte in range(symbol['address'],symbol['address']+(symbol.get('size') or 0))}
FIELDS={name:SYMS[name]['address'] for name in
        ('DrawingWidthPixels','DrawingHeight','DrawingOrigin',
         'DrawingPitchBytes','DrawingExtentBytes')}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY)}
RET=END-1
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
EDGES=set()
MEMORY_SIZE=1<<20
MAPPED_SIZE=2*MEMORY_SIZE
LOADS=(0x1010,0x1213,0x2345)
CF,PF,AF,ZF,SF,TF,IF,DF,OF=1,4,0x10,0x40,0x80,0x100,0x200,0x400,0x800
UNDEFINED_MUL=PF|AF|ZF|SF
DEFINED_FLAGS=0x0f03
MEM=ctypes.POINTER(ctypes.c_uint8)
REG_NAMES=oracle.REG_NAMES+('flags',)

class Regs(ctypes.Structure):
    _fields_=[(name,ctypes.c_uint16) for name in REG_NAMES]

READ=ctypes.CFUNCTYPE(ctypes.c_uint8,ctypes.c_void_p,MEM,ctypes.c_uint32,ctypes.c_uint16)
WRITE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.c_uint32,ctypes.c_uint8,ctypes.c_uint16)
OUT=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint16)

class RasterBus(ctypes.Structure):
    _fields_=[('context',ctypes.c_void_p),('read_byte',READ),
              ('write_byte',WRITE),('out_word',OUT)]


def physical(segment,offset):
    return ((segment<<4)+offset)&0xfffff


def word(mem,segment,offset):
    address=physical(segment,offset)
    return mem[address]|(mem[(address+1)&0xfffff]<<8)


def word_at(mem,address):
    address&=0xfffff
    return mem[address]|(mem[(address+1)&0xfffff]<<8)


def putword(mem,segment,offset,value):
    address=physical(segment,offset)
    mem[address]=value&255
    mem[(address+1)&0xfffff]=(value>>8)&255


def putword_at(mem,address,value):
    address&=0xfffff
    mem[address]=value&255
    mem[(address+1)&0xfffff]=(value>>8)&255


def parity_even(value):
    return (value&255).bit_count()%2==0


def shift_flags(flags,before):
    after=before>>1
    value=(flags&~(CF|PF|ZF|SF|OF))
    if before&1:value|=CF
    if parity_even(after):value|=PF
    if after==0:value|=ZF
    if before&0x8000:value|=OF
    return value&0xffff


def expected_fields(width,height,origin):
    pitch=width>>3
    product=pitch*height
    return dict(width=width,height=height,origin=origin,pitch=pitch,
                extent=product&0xffff,ax=product&0xffff,dx=(product>>16)&0xffff)


def add_case(out,name,width,height,origin,**kw):
    out.append(dict(name=name,width=width&0xffff,height=height&0xffff,
                    origin=origin&0xffff,seed=len(out),**kw))


def assert_no_known_instruction_writes(data_segment,load):
    code_start=load<<4
    code_end=code_start+len(IMAGE)
    for offset in FIELDS.values():
        first=physical(data_segment,offset)
        for address in (first,(first+1)&0xfffff):
            if code_start<=address<code_end and address-code_start in KNOWN_CODE_BYTES:
                raise AssertionError(f'DS write aliases known mainCS instruction at {address-code_start:04x}')


def cases():
    out=[]
    # Every low-three-bit residue appears both near zero and near the 16-bit
    # limit. Width 0, 1, 7, 8 and FFFF are all explicit acceptance points.
    widths=tuple(range(8))+tuple(0xfff8+r for r in range(8))
    heights=(0,1,7,8,0x1234,0x8001,0xffff)
    for width in widths:
        for height in heights:
            add_case(out,f'grid-w{width:04x}-h{height:04x}',width,height,
                     (width*73+height*19)&0xffff)
    add_case(out,'explicit-width-zero',0,0xffff,0x1357)
    add_case(out,'explicit-width-one',1,0xffff,0x2468)
    add_case(out,'explicit-width-seven',7,0xffff,0x369a)
    add_case(out,'explicit-width-eight',8,0xffff,0x48bc)
    add_case(out,'explicit-width-ffff',0xffff,0xffff,0x5ade)
    add_case(out,'mul-high-and-low',0xfffd,0xfedc,0x9876)

    # These cases exercise the far return against the writes the routine just
    # made, a wrapped SP word address, and the 20-bit physical address edge.
    add_case(out,'ds-ss-alias-return-fields',0x2468,0x1357,0xa55a,
             ds=0x6000,ss=0x6000,sp=FIELDS['DrawingWidthPixels'])
    add_case(out,'ds-ss-alias-return-pitch-extent',0x51b7,0x8043,0x3179,
             ds=0x6000,ss=0x6000,sp=FIELDS['DrawingPitchBytes'])
    add_case(out,'stack-sp-zero',0x0101,0x0103,0x1110,sp=0)
    add_case(out,'stack-sp-one',0x0203,0x0405,0x2220,sp=1)
    add_case(out,'stack-sp-wrap-ffff',0x0107,0x8000,0x1111,sp=0xffff)
    add_case(out,'stack-word-crosses-ffff',0x020f,0x7fff,0x2222,sp=0xfffe)
    add_case(out,'stack-physical-20bit-wrap',0x1017,0xf123,0x3333,
             ss=0xffff,sp=0x000f)
    add_case(out,'drawing-fields-physical-20bit-wrap',0x7fff,0x9001,0x4444,
             ds=0xffff)
    add_case(out,'physical-wrap-ds-ss-alias',0x6789,0x5678,0x9876,
             ds=0xffff,ss=0xffff,sp=FIELDS['DrawingWidthPixels'])

    rng=random.Random(0x8808)
    for n in range(24):
        add_case(out,f'random-{n:02d}',rng.randrange(65536),rng.randrange(65536),
                 rng.randrange(65536),flags=((rng.randrange(1<<12)&~TF)|2))
    return out


def prepare(case):
    rng=random.Random(0x8808+case['seed'])
    load=LOADS[case['seed']%len(LOADS)]
    mem=bytearray(rng.randbytes(MEMORY_SIZE))
    image=relocated(IMAGE,ORACLE['relocations'],load)
    start=load<<4
    mem[start:start+len(image)]=image
    regs={name:rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=case.get('ds',(load+0x09a9)&0xffff),
                ss=case.get('ss',0x7000),sp=case.get('sp',0x8000),
                ax=case['width'],bx=case['height'],dx=case['origin'])
    assert_no_known_instruction_writes(regs['ds'],load)
    flags=case.get('flags',2|((rng.randrange(1<<12))&~TF))
    stack_address=physical(regs['ss'],regs['sp'])
    putword_at(mem,stack_address,0xff00)
    pop_cs_address=physical(regs['ss'],(regs['sp']+2)&0xffff)
    putword_at(mem,pop_cs_address,0x7f00)
    if regs['sp']>=0xfffe:
        # Unicorn fetches its RETF words contiguously before updating SP.
        # Preserve a separate sentinel there; native checks use sequential
        # 16-bit POP semantics and expose that emulator discrepancy below.
        batch_cs_address=(stack_address+2)&0xfffff
        if batch_cs_address!=pop_cs_address:
            putword_at(mem,batch_cs_address,0xb22e)
    return mem,regs,flags,load


def library(mutation=0):
    path=build(BUILD/f'drawing-layout-m{mutation}.dll',mutation,'drawing_layout')
    lib=ctypes.CDLL(str(path))
    lib.lmn_set_drawing_layout_adapter.argtypes=[MEM,ctypes.POINTER(Regs),
                                                  ctypes.POINTER(RasterBus)]
    lib.lmn_set_drawing_layout_adapter.restype=None
    return lib


def make_bus(c_mem):
    events=[];errors=[]
    @READ
    def read(context,memory,address,flags):
        try:
            address&=0xfffff
            value=c_mem[address]
            events.append(('read',address,value,flags))
            return value
        except Exception as exc:
            errors.append(exc)
            return 0
    @WRITE
    def write(context,memory,address,value,flags):
        try:
            address&=0xfffff
            c_mem[address]=value
            events.append(('write',address,value,flags))
        except Exception as exc:
            errors.append(exc)
    bus=RasterBus(None,read,write,OUT())
    return bus,events,errors,(read,write)


def expected_bus_events(case,mem,regs,flags):
    fields=expected_fields(case['width'],case['height'],case['origin'])
    ds=regs['ds'];events=[];post=bytearray(mem)
    def writes(offset,value,current_flags):
        address=physical(ds,offset)
        for p,byte_value in ((address,value&255),
                             ((address+1)&0xfffff,(value>>8)&255)):
            post[p]=byte_value
            events.append(('write',p,byte_value,current_flags))
    writes(FIELDS['DrawingWidthPixels'],fields['width'],flags)
    writes(FIELDS['DrawingHeight'],fields['height'],flags)
    writes(FIELDS['DrawingOrigin'],fields['origin'],flags)
    shift=flags
    value=case['width']
    for _ in range(3):
        shift=shift_flags(shift,value)
        value>>=1
    writes(FIELDS['DrawingPitchBytes'],fields['pitch'],shift)
    mul_flags=(shift&~(CF|OF))|((CF|OF) if fields['dx'] else 0)
    writes(FIELDS['DrawingExtentBytes'],fields['extent'],mul_flags)

    stack_address=physical(regs['ss'],regs['sp'])
    ip=word_at(post,stack_address)
    cs_address=physical(regs['ss'],(regs['sp']+2)&0xffff)
    cs=word_at(post,cs_address)
    for address,result in ((stack_address,ip),(cs_address,cs)):
        address&=0xfffff
        events.append(('read',address,result&255,mul_flags))
        events.append(('read',(address+1)&0xfffff,(result>>8)&255,mul_flags))
    return events


def run_original(case,mem,regs,flags,load,stop_before_retf=False):
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,MAPPED_SIZE)
    u.mem_write(0,bytes(mem)+bytes(mem))
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    sites=set();edges=set();previous=None;done=False;write_trace=[];instruction_flags={}
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(load<<4)
        if stop_before_retf and off==RET:
            done=True;uc.emu_stop();return
        if previous==RET:
            done=True;uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        if uc.reg_read(oracle.REG['cs'])!=load or off not in INS:
            raise AssertionError(f"{case['name']}: SetDrawingLayout escaped at {off:04x}")
        sites.add(off);previous=off
        instruction_flags[off]=uc.reg_read(x.UC_X86_REG_EFLAGS)
    def intr(uc,num,_):raise AssertionError(f'Unexpected interrupt {num}')
    def mirror_writes(uc,access,address,size,value,_):
        for byte_index in range(size):
            raw=address+byte_index
            physical_address=raw&0xfffff
            byte_value=(value>>(8*byte_index))&255
            write_trace.append((physical_address,byte_value,
                               uc.reg_read(x.UC_X86_REG_EFLAGS)))
            other=(physical_address+MEMORY_SIZE) if raw<MEMORY_SIZE else physical_address
            if other!=raw:
                uc.mem_write(other,bytes((byte_value,)))
            if raw>=MEMORY_SIZE:
                uc.mem_write(physical_address,bytes((byte_value,)))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.hook_add(UC_HOOK_MEM_WRITE,mirror_writes)
    u.emu_start(physical(regs['cs'],ENTRY),0,count=1000)
    if not done:raise AssertionError(f"{case['name']}: far return did not finish")
    got_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()}
    got_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    got_mem=bytes(u.mem_read(0,MEMORY_SIZE))
    return got_regs,got_flags,got_mem,sites,edges,write_trace,instruction_flags


def expected_write_trace(case,regs,flags):
    fields=expected_fields(case['width'],case['height'],case['origin'])
    expected=[]
    def append(offset,value,current):
        address=physical(regs['ds'],offset)
        expected.extend(((address,value&255,current),
                         ((address+1)&0xfffff,(value>>8)&255,current)))
    append(FIELDS['DrawingWidthPixels'],fields['width'],flags)
    append(FIELDS['DrawingHeight'],fields['height'],flags)
    append(FIELDS['DrawingOrigin'],fields['origin'],flags)
    shifted=flags;value=case['width']
    for _ in range(3):
        shifted=shift_flags(shifted,value);value>>=1
    append(FIELDS['DrawingPitchBytes'],fields['pitch'],shifted)
    mul_flags=(shifted&~(CF|OF))|((CF|OF) if fields['dx'] else 0)
    append(FIELDS['DrawingExtentBytes'],fields['extent'],mul_flags)
    return expected


def expected_return(case,mem,regs):
    post=bytearray(mem);fields=expected_fields(case['width'],case['height'],case['origin'])
    for name,key in (('DrawingWidthPixels','width'),('DrawingHeight','height'),
                     ('DrawingOrigin','origin'),('DrawingPitchBytes','pitch'),
                     ('DrawingExtentBytes','extent')):
        putword(post,regs['ds'],FIELDS[name],fields[key])
    ip=word_at(post,physical(regs['ss'],regs['sp']))
    cs=word_at(post,physical(regs['ss'],(regs['sp']+2)&0xffff))
    return ip,cs,(regs['sp']+4)&0xffff


def compare(lib,case):
    mem,regs,flags,load=prepare(case)
    c_mem=bytearray(mem);c_regs=Regs(**regs,flags=flags)
    bus,events,errors,callbacks=make_bus(c_mem)
    lib.lmn_set_drawing_layout_adapter(
        (ctypes.c_uint8*MEMORY_SIZE).from_buffer(c_mem),ctypes.byref(c_regs),ctypes.byref(bus))
    if errors:raise errors[0]

    # The null-bus path is the ordinary canonical RAM backend. Keep a paired
    # call for every fixture so callback routing cannot hide fallback errors.
    plain_mem=bytearray(mem);plain_regs=Regs(**regs,flags=flags)
    lib.lmn_set_drawing_layout_adapter(
        (ctypes.c_uint8*MEMORY_SIZE).from_buffer(plain_mem),ctypes.byref(plain_regs),None)
    if bytes(plain_mem)!=bytes(c_mem):
        address=next(i for i,(a,b) in enumerate(zip(plain_mem,c_mem)) if a!=b)
        raise AssertionError(f"{case['name']}: null-bus RAM differs at {address:05x}")
    for name in REG_NAMES:
        if getattr(plain_regs,name)!=getattr(c_regs,name):
            raise AssertionError(f"{case['name']}: null-bus {name} differs from callback bus")

    expected=expected_fields(case['width'],case['height'],case['origin'])
    actual_regs={name:getattr(c_regs,name) for name in oracle.REG_NAMES}
    boundary_stack=regs['sp']>=0xfffe
    artifact={}
    if boundary_stack:
        body,body_flags,body_mem,sites,edges,original_writes,_=run_original(
            case,mem,regs,flags,load,stop_before_retf=True)
        original,original_flags,original_mem,full_sites,full_edges,_,_=run_original(
            case,mem,regs,flags,load)
        sites|=full_sites;edges|=full_edges
        want_ip,want_cs,want_sp=expected_return(case,mem,regs)
        batch_address=(physical(regs['ss'],regs['sp'])+2)&0xfffff
        pop_address=physical(regs['ss'],(regs['sp']+2)&0xffff)
        if original['ip']!=want_ip or original['cs']!=word_at(original_mem,batch_address):
            raise AssertionError(f"{case['name']}: Unicorn RETF artifact did not use contiguous words")
        if batch_address==pop_address or original['cs']==want_cs:
            raise AssertionError(f"{case['name']}: fixture did not expose the Unicorn RETF boundary discrepancy")
        if body['ip']!=RET or body['cs']!=regs['cs'] or body['sp']!=regs['sp']:
            raise AssertionError(f"{case['name']}: original body did not stop before RETF")
        for name in oracle.REG_NAMES:
            if name in ('ip','cs','sp'):continue
            if actual_regs[name]!=body[name]:
                raise AssertionError(f"{case['name']}: C body {name} differs before isolated RETF")
        if (c_regs.flags^body_flags)&DEFINED_FLAGS:
            raise AssertionError(f"{case['name']}: defined body flags differ before isolated RETF")
        if bytes(c_mem)!=body_mem:
            address=next(i for i,(a,b) in enumerate(zip(c_mem,body_mem)) if a!=b)
            raise AssertionError(f"{case['name']}: body RAM differs before RETF at {address:05x}")
        if (c_regs.ip,c_regs.cs,c_regs.sp)!=(want_ip,want_cs,want_sp):
            raise AssertionError(f"{case['name']}: native sequential-pop RETF differs from independent contract")
        artifact=dict(sp=regs['sp'],unicorn_ip=original['ip'],unicorn_cs=original['cs'],
            adapter_model_ip=want_ip,adapter_model_cs=want_cs,
            unicorn_second_word_address=batch_address,adapter_model_second_word_address=pop_address,
            detail='Original body is compared through the instruction before RETF; the adapter uses the permissive two-POP bus model. CPU-family stack-limit faults are outside this domain. Unicorn RETF performs contiguous reads across SP wrap.')
    else:
        original,original_flags,original_mem,sites,edges,original_writes,_=run_original(
            case,mem,regs,flags,load)
        for name in oracle.REG_NAMES:
            if actual_regs[name]!=original[name]:
                raise AssertionError(f"{case['name']}: C {name}={actual_regs[name]:04x}, original={original[name]:04x}")
        if (c_regs.flags^original_flags)&DEFINED_FLAGS:
            raise AssertionError(f"{case['name']}: defined MUL/IF/DF flags differ")
        if bytes(c_mem)!=original_mem:
            address=next(i for i,(a,b) in enumerate(zip(c_mem,original_mem)) if a!=b)
            raise AssertionError(f"{case['name']}: C whole RAM differs at {address:05x}")
    if (original['ax'],original['dx'])!=(expected['ax'],expected['dx']):
        raise AssertionError(f"{case['name']}: original product differs from independent multiply")
    want_writes=expected_write_trace(case,regs,flags)
    got_writes=[event[1:] for event in events if event[0]=='write']
    if len(got_writes)!=len(want_writes):
        raise AssertionError(f"{case['name']}: C emitted {len(got_writes)} bus writes, expected {len(want_writes)}")
    for n,(actual,want) in enumerate(zip(got_writes,want_writes)):
        if actual[:2]!=want[:2] or ((actual[2]^want[2])&DEFINED_FLAGS):
            raise AssertionError(f"{case['name']}: C bus write {n} differs: {actual}/{want}")
    original_byte_writes=[(a,v) for a,v,_ in original_writes]
    if original_byte_writes!=[(a,v) for a,v,_ in want_writes]:
        raise AssertionError(f"{case['name']}: original write order/value differs from five-field contract")
    # Status bits undefined after MUL are compared separately below; the
    # bus contract checks their defined subset and exact address/value order.
    expected_events=expected_bus_events(case,mem,regs,flags)
    if len(events)!=len(expected_events):
        raise AssertionError(f"{case['name']}: bus read/write event count differs")
    for n,(actual,want) in enumerate(zip(events,expected_events)):
        # First three words retain entry flags; pitch follows SHR; only
        # extent and the RETF reads have MUL's undefined arithmetic bits.
        event_flags=0xfd7 if n<6 else 0xfc7 if n<8 else DEFINED_FLAGS
        if actual[:3]!=want[:3] or ((actual[3]^want[3])&event_flags):
            raise AssertionError(f"{case['name']}: bus event {n} differs: {actual}/{want}")
    return sites,edges,artifact


def main():
    report=BUILD/'drawing-layout-differential.json';report.unlink(missing_ok=True)
    baseline=cases();lib=library();sites=set();edges=set();retf_artifacts=[]
    for case in baseline:
        got_sites,got_edges,artifact=compare(lib,case);sites|=got_sites;edges|=got_edges
        if artifact:retf_artifacts.append(dict(case=case['name'],**artifact))
    if sites!=set(INS):raise AssertionError(f'Missing SetDrawingLayout sites: {set(INS)-sites}')
    if edges!=EDGES:raise AssertionError(f'SetDrawingLayout branch edges differ: {edges}/{EDGES}')

    mutations=[]
    for mutation in (1,2,3):
        mutant=library(mutation);hit=None
        for case in baseline:
            try:compare(mutant,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'Layout compiled mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))

    paths=('c/drawing_layout.c','c/drawing_layout.h','c/regs.h','c/special_blit.h',
           'c/lemmings_sym.h','tools/cbuild.py','tests/drawing_layout.py',
           'metadata/symbols.json')
    public_cases=[{k:v for k,v in case.items()} for case in baseline]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),
        mutation_count=len(mutations),cases=public_cases,mutations_detected=mutations,
        translated_code_bytes=sum(i.size for i in INS.values()),
        instruction_sites=sorted(sites),executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges),
        routine=dict(name=ROUTINE['symbol_name'],start=ENTRY,end=END),
        routine_bytes_hex=IMAGE[ENTRY:END].hex(),
        routine_bytes_sha256=sha(IMAGE[ENTRY:END]),
        fixture_domains=dict(width_residues=list(range(8)),explicit_widths=[0,1,7,8,0xffff],
            height_values=[0,1,7,8,0x1234,0x8001,0xffff],
            loads=[f'{load:04x}' for load in LOADS],
            null_bus_ram=True,raster_bus_callback_ram=True,ds_ss_alias=True,
            stack_offsets=[0,1,0x8000,0xfffe,0xffff],physical_20_bit_wrap=True,
            known_maincs_instruction_write_exclusion=True,
            isolated_unicorn_retf_sp_wrap_cases=[c['name'] for c in baseline if c.get('sp') in (0xfffe,0xffff)]),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        unicorn_retf_boundary_observations=retf_artifacts,
        domain='DS width/height/origin writes excluding known mainCS instruction bytes; exact floor(width/8) pitch; unsigned DX:AX pitch*height; null-bus RAM and LmnRasterBus callback RAM; DS/SS aliases; permissive two-POP RETF adapter model; CPU-family stack-limit/fault behavior excluded; physical word wrap; loads 1010/1213/2345; all defined MUL/IF/DF flags; Unicorn SP-wrap RETF discrepancy isolated and recorded'))
    print(f'PASS drawing layout C: {len(baseline)} cases, {len(sites)} sites, {len(edges)} branch edges; 3 compiled mutations detected')


if __name__=='__main__':main()
