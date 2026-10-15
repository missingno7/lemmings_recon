"""Bounded 378A object-record oracle and native C comparisons."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import dat_io as oracle
from dat_io_c import Regs,MEM
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from bounded_process import run_bounded, temporary_build_directory
from resources import section_spans,decode_section
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['CopyLevelObjectGraphicsRecords'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
DEFINITIONS=SYMS['LevelObjectDefinitions']['address']
LEVEL_RECORD=SYMS['LoadedLevelRecord']['address']
GRAPHICS=SYMS['LevelObjectGraphicsRecords']['address']
GROUND=SYMS['GroundResourceBuffer']['address']
RET=END-1
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY)}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&0xffff) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,pc+i.size) for pc,i in INS.items() if pc in BRANCHES}
MEMORY_SIZE=1<<20
MEMORY_MASK=MEMORY_SIZE-1
LOADS=(0x1010,0x1213,0x2345)
LIBRARY_DIRECTORY=BUILD


def physical(segment,offset):
    return ((segment<<4)+(offset&0xffff))&MEMORY_MASK


def read8(mem,segment,offset):
    return mem[physical(segment,offset)]


def write_bytes(mem,segment,offset,data):
    for n,value in enumerate(data):
        mem[physical(segment,offset+n)]=value


def read_word(mem,segment,offset):
    p=physical(segment,offset)
    return mem[p]|(mem[(p+1)&MEMORY_MASK]<<8)


def put_definition(mem,segment,index,object_type):
    base=DEFINITIONS+8*index
    mem[physical(segment,base)]=1
    mem[physical(segment,base+1)]=0
    mem[physical(segment,base+4)]=(object_type>>8)&255
    mem[physical(segment,base+5)]=object_type&255


def add_case(out,name,definitions=(),**kw):
    out.append(dict(name=name,definitions=tuple(definitions),seed=len(out),**kw))


def cases():
    out=[]
    add_case(out,'all-inactive')
    values=(0,1,35,36)
    add_case(out,'all-active-forward',((i,values[i%len(values)]) for i in range(32)))
    add_case(out,'all-active-backward',((i,values[i%len(values)]) for i in range(32)),df=True)
    for index in range(32):
        add_case(out,f'single-slot-{index:02d}',((index,values[index%len(values)]),),df=bool(index&1))
    for object_type in (0,1,35,36,0xffff,2092,2341):
        add_case(out,f'type-{object_type:04x}',((7,object_type),),df=bool(object_type&1))
    # Type 3FE0 wraps its product so source SI lands on slot zero. Slot one
    # reads the bytes slot zero received in the preceding loop iteration.
    add_case(out,'live-output-source-alias',((0,0),(1,0x3fe0)))
    # The first forward copy overwrites the live saved DI/CX/SI words and the
    # return word. The next active copy uses restored FFF0 SI/FFFC DI; its
    # source and destination both wrap, and the forward ranges overlap live.
    add_case(out,'saved-cursors-counter-and-ret-alias',((0,0),(1,0)),
        ds=0x6000,ss=0x6000,sp=0x17d1,stack_alias=True,
        source_prefix=bytes((0xe0,0xff,0x02,0x00,0xf0,0xff)))
    add_case(out,'saved-di-sign-overflow-alias',((0,0),),ds=0x6000,ss=0x6000,
        sp=0x17d1,stack_alias=True,
        source_prefix=bytes((0xff,0x7f,0x01,0x00,0x4b,0x1b)))
    for sp in (0,1,0xffff):
        add_case(out,f'stack-sp-{sp:04x}',((0,1),),sp=sp)
    add_case(out,'physical-word-wrap-ffff',(),ds=0xffff,ss=0xffff,sp=0xffff,
        physical_wrap=True)
    for backwards in (False,True):
        add_case(out,f'physical-source-wrap-{backwards}',((0,2092),),
            ds=0xffff,df=backwards,physical_wrap=True)

    # Exercise every pinned LEVEL section with the matching loaded ground set.
    for group in range(10):
        asset=f'assets/level{group:03d}.dat'
        packed=(ROOT/asset).read_bytes()
        spans=section_spans(packed)
        if len(spans)!=8:
            raise AssertionError(f'{asset}: expected eight pinned level sections')
        for section,(start,end) in enumerate(spans):
            record,_=decode_section(packed[start:end])
            if len(record)!=2048:
                raise AssertionError(f'{asset} section {section}: unexpected level record size')
            ground_index=record[27]
            ground_asset=f'assets/ground{ground_index}o.dat'
            ground=(ROOT/ground_asset).read_bytes()
            out.append(dict(name=f'real-level-{group:03d}-{section}',seed=len(out),
                real=True,level_asset=asset,ground_asset=ground_asset,
                section=section,record=record,ground=ground,df=False))
    return out


def prepare(case):
    rng=random.Random(0x378a+case['seed'])
    load=LOADS[case['seed']%len(LOADS)]
    mem=bytearray(rng.randbytes(MEMORY_SIZE))
    mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={name:rng.randrange(65536) for name in oracle.REG_NAMES}
    data_segment=case.get('ds',(load+0x09a9)&0xffff)
    regs.update(cs=load,ip=ENTRY,ds=data_segment,es=rng.randrange(65536),
        ss=case.get('ss',0x7000),sp=case.get('sp',0x8000))
    flags=2|(rng.randrange(65536)&0xed5)
    if case.get('df'):
        flags|=0x0400
    else:
        flags&=~0x0400

    # The ground table is live DS memory. The actual pinned files below replace
    # this deterministic backing store for the 80 real level-section cases.
    ground=bytes((n*31+case['seed']*17+7)&255 for n in range(0x1000))
    write_bytes(mem,data_segment,GROUND,ground)
    if not case.get('real'):
        stale=bytes((n*29+0x5b)&255 for n in range(32*28))
        write_bytes(mem,data_segment,GRAPHICS,stale)
    if case.get('real'):
        write_bytes(mem,data_segment,LEVEL_RECORD,case['record'])
        write_bytes(mem,data_segment,GROUND,case['ground'])
    else:
        write_bytes(mem,data_segment,DEFINITIONS,bytes(0x100))
        for index,object_type in case.get('definitions',()):
            put_definition(mem,data_segment,index,object_type)
        if case.get('source_prefix'):
            write_bytes(mem,data_segment,GROUND,case['source_prefix'])
            # The second live read begins at FFF0 and walks forward across
            # zero after the first copy restores SI=FFF0 and DI=FFFC.
            for offset in range(0x0000,0x0019):
                mem[physical(data_segment,offset)]=(offset*13+0x41)&255
            for offset in (0xfffd,0xfffe,0xffff):
                mem[physical(data_segment,offset)]=(offset*13+0x41)&255

    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags


def expected_copy_region(mem,case,regs,flags):
    """Independent live byte-copy model for cases without stack/data aliases."""
    expected=bytearray(mem)
    ds=regs['ds'];bx=DEFINITIONS;si=GROUND;di=GRAPHICS
    step=-1 if flags&0x0400 else 1
    for _ in range(32):
        active=(read8(expected,ds,bx)!=0 or read8(expected,ds,(bx+1)&0xffff)!=0)
        if active:
            object_type=(read8(expected,ds,(bx+4)&0xffff)<<8)|read8(expected,ds,(bx+5)&0xffff)
            source=(si+((object_type*28)&0xffff))&0xffff
            for n in range(28):
                src=(source+step*n)&0xffff
                dst=(di+step*n)&0xffff
                expected[physical(ds,dst)]=expected[physical(ds,src)]
        bx=(bx+8)&0xffff
        di=(di+28)&0xffff
    return expected


def library(mutation=0):
    lib=ctypes.CDLL(str(build(LIBRARY_DIRECTORY/f'object-graphics-m{mutation}.dll',mutation,'object_graphics')))
    lib.lmn_copy_object_graphics_adapter.argtypes=[MEM,ctypes.POINTER(Regs)]
    lib.lmn_copy_object_graphics_adapter.restype=None
    return lib


def run_case(lib,case,collect_coverage=False):
    mem,regs,flags=prepare(case)
    expected=None
    if not case.get('stack_alias'):
        expected=expected_copy_region(mem,case,regs,flags)

    c_mem=bytearray(mem)
    c_regs=Regs(**regs,flags=flags)
    lib.lmn_copy_object_graphics_adapter(
        (ctypes.c_uint8*MEMORY_SIZE).from_buffer(c_mem),ctypes.byref(c_regs))

    # Map a mirror above 1 MiB so Unicorn's linear accesses implement the DOS
    # 20-bit bus. Hooks keep both views live for offset and physical wrap cases.
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<21)
    u.mem_write(0,bytes(mem));u.mem_write(MEMORY_SIZE,bytes(mem))
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    sites=set();edges=set();previous=None;done=False
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if previous==RET:
            done=True;uc.emu_stop();return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:
            raise RuntimeError(f"{case['name']}: original escaped at {off:04x}")
        sites.add(off);previous=off
    def a20_read(uc,access,address,size,value,_):
        for n in range(size):
            current=address+n
            if current>=MEMORY_SIZE:
                uc.mem_write(current,bytes(uc.mem_read(current&MEMORY_MASK,1)))
    def a20_write(uc,access,address,size,value,_):
        for n in range(size):
            current=address+n
            byte=bytes(((value>>(8*n))&255,))
            if current>=MEMORY_SIZE:
                uc.mem_write(current&MEMORY_MASK,byte)
            else:
                uc.mem_write(current+MEMORY_SIZE,byte)
    def intr(uc,number,_):
        raise RuntimeError(f"{case['name']}: unexpected interrupt {number}")
    u.hook_add(UC_HOOK_CODE,code)
    u.hook_add(UC_HOOK_MEM_READ,a20_read)
    u.hook_add(UC_HOOK_MEM_WRITE,a20_write)
    u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(physical(regs['cs'],ENTRY),0,count=100000)
    if not done:raise RuntimeError(f"{case['name']}: routine exceeded bounded execution")

    original_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()}
    original_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    original_mem=bytes(u.mem_read(0,MEMORY_SIZE))
    if case['name']=='saved-cursors-counter-and-ret-alias':
        wanted=dict(ax=0,bx=0x0ffb,cx=0,dx=0,si=0xfff0,di=0x0018,
            es=regs['ds'],sp=(regs['sp']+2)&0xffff)
        if any(original_regs[name]!=value for name,value in wanted.items()):
            got={name:original_regs[name] for name in wanted}
            raise AssertionError(f'Saved-cursor fixture did not control restores: {got}')
        live_return=read_word(original_mem,regs['ss'],regs['sp'])
        if original_regs['ip']!=live_return or live_return==0xff00:
            raise AssertionError('Saved-cursor fixture did not overwrite the live return word')
    if case['name']=='saved-di-sign-overflow-alias':
        expected_flags=(flags&~0x08d5)|0x0894
        if original_regs['di']!=0x801b or (original_flags^expected_flags)&0x0fd7:
            raise AssertionError('Saved-DI fixture did not expose the final ADD sign/overflow flags')
    for name in oracle.REG_NAMES:
        if original_regs[name]!=getattr(c_regs,name):
            raise AssertionError(f"{case['name']}: {name} C={getattr(c_regs,name):04x}/original={original_regs[name]:04x}")
    if (c_regs.flags^original_flags)&0xfd7:
        raise AssertionError(f"{case['name']}: defined flags differ")
    if bytes(c_mem)!=original_mem:
        p=next(i for i,(left,right) in enumerate(zip(c_mem,original_mem)) if left!=right)
        raise AssertionError(f"{case['name']}: whole RAM differs at {p:05x}")

    if expected is not None:
        start=GRAPHICS-0x1b;end=GRAPHICS+32*28
        for offset in range(start,end):
            address=physical(regs['ds'],offset)
            if original_mem[address]!=expected[address]:
                raise AssertionError(f"{case['name']}: independent live-copy model differs at DS:{offset:04x}")
    if collect_coverage:return sites,edges
    return None


def main():
    report=BUILD/'object-graphics-differential.json';report.unlink(missing_ok=True)
    baseline=cases();lib=library();sites=set();edges=set()
    for case in baseline:
        case_sites,case_edges=run_case(lib,case,True)
        sites|=case_sites;edges|=case_edges
    if sites!=set(INS):raise AssertionError(f'Missing instruction sites: {set(INS)-sites}')
    if edges!=EDGES:raise AssertionError(f'Missing branch edges: {EDGES-edges}')

    mutant_fixtures={
        1:next(case for case in baseline if case['name']=='all-inactive'),
        2:next(case for case in baseline if case['name']=='type-ffff'),
        3:next(case for case in baseline if case['name']=='all-active-backward'),
    }
    mutations=[]
    for mutation,case in mutant_fixtures.items():
        mutant=library(mutation)
        try:
            run_case(mutant,case)
        except AssertionError:
            mutations.append(dict(mutation=mutation,case=case['name']))
        else:
            raise AssertionError(f'Compiled mutation {mutation} survived')

    assets=tuple(f'assets/level{n:03d}.dat' for n in range(10))+tuple(
        f'assets/ground{n}o.dat' for n in range(5))
    paths=('c/object_graphics.c','c/object_graphics.h','c/regs.h','c/lemmings_sym.h',
        'tests/object_graphics.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py',
        'tools/difftest.py','tools/unpack.py','tools/resources.py','metadata/symbols.json',
        'metadata/inputs.json','assets/vgalemmi.exe')+assets
    public_cases=[]
    for case in baseline:
        row=dict(name=case['name'],df=bool(case.get('df')))
        if case.get('real'):
            row.update(level_asset=case['level_asset'],section=case['section'],
                ground_asset=case['ground_asset'])
        else:
            row.update(active_indices=[index for index,_ in case.get('definitions',())],
                types=[value for _,value in case.get('definitions',())],
                stack_alias=bool(case.get('stack_alias')),physical_wrap=bool(case.get('physical_wrap')))
        public_cases.append(row)
    # This cluster has two independently executed backends. Keep their cases
    # distinct, while unioning the same original instruction/byte interval.
    run_bounded([sys.executable,str(Path(__file__).with_name('object_graphics_bus.py'))],
                cwd=ROOT,timeout=180)
    bus_report=read_json(BUILD/'object-graphics-bus-differential.json')
    if bus_report['image_sha256']!=sha(IMAGE):
        raise RuntimeError('Object graphics bus report image changed')
    input_hashes={path:sha((ROOT/path).read_bytes()) for path in paths}
    for path,expected_hash in bus_report['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=expected_hash:
            raise RuntimeError(f'Stale object graphics bus report: {path}')
        if path in input_hashes and input_hashes[path]!=expected_hash:
            raise RuntimeError(f'Object graphics input changed: {path}')
        input_hashes[path]=expected_hash
    bus_sites=set(bus_report['original_observed_instruction_sites'])
    bus_edges={tuple(edge) for edge in bus_report['original_observed_branch_edges']}
    if bus_sites!=set(INS) or bus_edges!=EDGES or not bus_report['original_ret_executed']:
        raise RuntimeError('Object graphics bus original coverage incomplete')
    sites|=bus_sites;edges|=bus_edges
    public_cases=[dict(row,backend='null-bus') for row in public_cases]
    public_cases.extend(dict(row,backend='raster-bus') for row in bus_report['cases'])
    mutations=[dict(row,backend='null-bus') for row in mutations]+[
        dict(row,backend='raster-bus') for row in bus_report['mutations_detected']]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(public_cases),
        ram_case_count=len(baseline),bus_case_count=bus_report['case_count'],
        mutation_count=len(mutations),mutations_detected=mutations,cases=public_cases,
        translated_code_bytes=sum(i.size for i in INS.values()),instruction_sites=sorted(sites),
        branch_edges=sorted(edges),routine=dict(name=ROUTINE['symbol_name'],start=ENTRY,end=END),
        fixture_domains=dict(synthetic_single_active_slots=32,all_inactive=True,
            all_active_directions=['forward','backward'],types=[0,1,35,36,0xffff,2092,2341],
            live_source_output_alias=True,saved_si_cx_di_and_return_alias=True,
            stack_offsets=[0,1,0xffff],physical_20_bit_wrap=True,real_level_sections=80,
            paired_ground_assets=sorted(set(case['ground_asset'] for case in baseline if case.get('real')))),
        input_hashes=input_hashes,
        domain='Original bounded CS:378A..37C1 and C11 core; null-bus and ordered raster-bus access, VGA stack/source/destination, unchecked BE type multiplication, stale inactive slots, incoming DF, live SS saves/RET aliases, 16-bit offsets, 20-bit physical memory, paired real LEVEL/GROUND sections'))
    print(f'PASS object graphics C: {len(public_cases)} cases ({len(baseline)} null-bus/{bus_report["case_count"]} raster-bus), {len(sites)} instruction sites, {len(edges)} branch edges; {len(mutations)} compiled mutation checks detected')


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        LIBRARY_DIRECTORY=Path(sys.argv[2]);main()
    elif len(sys.argv)==1:
        BUILD.mkdir(exist_ok=True)
        (BUILD/'object-graphics-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='object-graphics-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],
                        cwd=ROOT,timeout=180)
    else:raise SystemExit('Unexpected object_graphics arguments')
