"""Original resource RLE versus C, including rollover AL corruption and DF."""
import ctypes
import random
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x
from dat_io_c import Regs,MEM
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated
from resources import section_spans,decode_section

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['DecodeResourceRle'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY)}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'resource_rle-m{mutation}.dll',mutation,'resource_rle')))
    lib.lmn_decode_resource_rle_adapter.argtypes=[MEM,ctypes.POINTER(Regs)];lib.lmn_decode_resource_rle_adapter.restype=None
    return lib
def prepare(case):
    rng=random.Random(0x1b42+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=case.get('source_segment',0x3000),si=case.get('source',0x1000),
        es=case.get('output_segment',0x4000),di=case.get('output',0x100),ss=0x7000,sp=case.get('sp',0x8000))
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    step=-1 if case.get('df') else 1
    for n,value in enumerate(case['stream']):mem[oracle.at(regs['ds'],regs['si']+step*n)]=value
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags
def compare(lib,case):
    mem,regs,flags=prepare(case);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    lib.lmn_decode_resource_rle_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r))
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;done=False
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off==0xff00:done=True;uc.emu_stop();return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'RLE escaped interval at {off:x}')
        seen.add(off);previous=off
    def intr(uc,num,_):raise AssertionError(f'Unexpected interrupt {num}')
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(oracle.at(regs['cs'],ENTRY),0,count=1000000)
    if not done:raise AssertionError('RLE exceeded budget')
    if 'asset' in case:
        if (u.reg_read(oracle.REG['si']),u.reg_read(oracle.REG['di']),u.reg_read(oracle.REG['es']))!=(
            case['stream_end']+0x10,0x8000+case['decoded_size'],regs['es']):
            raise AssertionError('Original special-resource extent differs from static packet accounting')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(r,n):04x}/original={u.reg_read(reg):04x}')
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0xfd7:raise AssertionError('Defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at {p:05x}')
    return seen,edges
def cases():
    out=[]
    def add(name,stream,**kw):out.append(dict(name=name,stream=stream,seed=len(out),**kw))
    for control in range(256):
        if control==128:stream=b'\x80'
        elif control<128:stream=bytes([control])+bytes([128])*(control+1)+b'\x80'
        else:stream=bytes([control,0x7a,128])
        add(f'control-{control:02x}',stream)
    for df in (False,True):
        for output in (0,1,0xfffe,65535):
            add(f'repeat-boundary-{output}-{df}',bytes([0xfd,0x7a,128]),output=output,df=df,output_segment=0x4513)
            add(f'literal-boundary-{output}-{df}',bytes([2,0x11,0x22,0x33,128]),output=output,df=df,output_segment=0x4513)
        for source in (0,1,65535):add(f'source-{source}-{df}',bytes([0xfd,0x7a,0,0x55,128]),source=source,df=df)
    add('repeat-multiple-rollovers',bytes([0x81,0x7a])*513+b'\x80',output=65535,output_segment=0x4513)
    add('repeat-segment-wrap',bytes([0xff,0x7a,128]),output=65535,output_segment=0xf000)
    add('literal-segment-wrap',bytes([1,0x11,0x22,128]),output=65535,output_segment=0xf000)
    add('literal-live-overlap',bytes([1,0x80,0x7e,0x80]),source_segment=0x4000,source=0x100,output=0x102)
    add('repeat-live-overlap',bytes([0xff,0x80,0x80]),source_segment=0x4000,source=0x100,output=0x102)
    add('mixed',bytes([0xff,0x12,1,0x23,0x34,0x81,0x45,0,0x56,0x80]))
    for sp in (0,1,65535):add(f'stack-{sp}',bytes([0xff,0x12,0x80]),sp=sp)
    # 1A5A selects vgaspec?.dat and loads its first section at offset10;
    # 1A7B starts the four successive RLE calls at live source offset38.
    for number in range(4):
        asset=f'assets/vgaspec{number}.dat';packed=(ROOT/asset).read_bytes()
        start,end=section_spans(packed)[0];image,_=decode_section(packed[start:end]);cursor=0x28
        for stream_number in range(4):
            first=cursor;size=0
            while True:
                control=image[cursor];cursor+=1
                if control==128:break
                count=(1-control)&255 if control>128 else control+1
                cursor+=1 if control>128 else count;size+=count
                if cursor>len(image):raise AssertionError('Truncated statically parsed special-resource stream')
            if size!=14400:raise AssertionError('Unexpected special-resource decoded span')
            add(f'vgaspec-{number}-stream-{stream_number}',image[first:cursor],source=first+0x10,output=0x8000,
                asset=asset,section_offset=start,stream_start=first,stream_end=cursor,decoded_size=size)
        if cursor!=len(image):raise AssertionError('Unaccounted special-resource section suffix')
    return out
def main():
    report=BUILD/'resource-rle-differential.json';report.unlink(missing_ok=True);baseline=cases();lib=library();seen=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);seen|=a;edges|=b
    if seen!=set(INS) or edges!=EDGES:raise AssertionError(f'Missing sites/edges {set(INS)-seen}/{EDGES-edges}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if not hit:raise AssertionError(f'RLE mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/resource_rle.c','c/resource_rle.h','c/regs.h','tests/resource_rle.py','tests/dat_io.py','tests/dat_io_c.py',
        'tools/cbuild.py','tools/difftest.py','metadata/symbols.json')
    paths+=('metadata/inputs.json',)+tuple(f'assets/vgaspec{n}.dat' for n in range(4))
    public=[{k:(v.hex() if isinstance(v,bytes) else v) for k,v in c.items() if k!='stream' or 'asset' not in c}
            |dict(input_sha256=sha(c['stream'])) for c in baseline]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,cases=public,
        mutations_detected=mutations,executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),
        translated_code_bytes=sum(i.size for i in INS.values()),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Terminated constructed streams; quiescent mapped memory; both DF values; intact code and active return words; all final defined flags'))
    print(f'PASS resource RLE C: {len(baseline)} cases, {len(seen)} sites, {len(edges)} branch edges; 3 compiled mutations detected')
if __name__=='__main__':main()
