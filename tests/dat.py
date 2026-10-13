"""Bounded original DAT leaf routines versus C; no game or DOS execution."""
import ctypes
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x
from common import ROOT,BUILD,sha,write_json,read_json
from unpack import unpack,ASSET,relocated
from cbuild import build

REPORT=BUILD/'dat-differential.json'
NAMES=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip','flags')
class Regs(ctypes.Structure):_fields_=[(n,ctypes.c_uint16) for n in NAMES]
REG={n:getattr(x,'UC_X86_REG_'+n.upper()) for n in NAMES if n!='flags'}
IMAGE,ORACLE=unpack(ASSET.read_bytes())
LEDGER={r['symbol_name']:r for r in read_json(ROOT/'metadata/symbols.json')}
ROUTINES={kind:(LEDGER[name]['address'],LEDGER[name]['address']+LEDGER[name]['size']) for kind,name in
    (('read_bits','ReadReverseBits'),('copy_match','CopyReverseMatch'),('write_literal','WriteReverseLiteral'))}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for start,end in ROUTINES.values() for i in MD.disasm(IMAGE[start:end],start)}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EXPECTED={(pc,i.operands[0].imm&0xffff) for pc,i in INS.items() if pc in BRANCHES}
EXPECTED|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES}

def at(seg,off):return ((seg<<4)+(off&0xffff))&0xfffff
def put16(mem,seg,off,value):
    p=at(seg,off);mem[p]=value&255;mem[(p+1)&0xfffff]=(value>>8)&255

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'dat-m{mutation}.dll',mutation,'dat')))
    for kind in ROUTINES:
        fn=getattr(lib,'lmn_dat_'+kind+'_adapter')
        fn.argtypes=[ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(Regs)];fn.restype=None
    return lib

def prepare(case):
    rng=random.Random(0x1ca3+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    r=Regs(**{n:rng.randrange(65536) for n in NAMES})
    r.cs=load;r.ds=0x3000;r.es=0x4000;r.ss=0x7000;r.sp=0x8000
    r.ip=ROUTINES[case['kind']][0];r.flags=2|(rng.randrange(65536)&0xed5)
    for n,value in case.get('regs',{}).items():setattr(r,n,value)
    put16(mem,r.ss,r.sp,0xff00)
    return mem,r

def compare(lib,case):
    mem,r=prepare(case);c_mem=bytearray(mem);c_r=Regs.from_buffer_copy(r)
    getattr(lib,'lmn_dat_'+case['kind']+'_adapter')((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(c_r))
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in REG.items():u.reg_write(reg,getattr(r,n))
    u.reg_write(x.UC_X86_REG_EFLAGS,r.flags)
    sites=set();edges=set();previous=None;done=False
    start,end=ROUTINES[case['kind']]
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(r.cs<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if pc==at(r.cs,0xff00):done=True;uc.emu_stop();return
        if uc.reg_read(x.UC_X86_REG_CS)!=r.cs or not start<=off<end:raise AssertionError('DAT helper escaped interval')
        sites.add(off);previous=off
    def intr(uc,num,_):raise AssertionError(f'Unexpected interrupt {num}')
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(at(r.cs,r.ip),0,count=600000)
    if not done:raise AssertionError('DAT helper exceeded budget')
    for n,reg in REG.items():
        actual=u.reg_read(reg)
        if getattr(c_r,n)!=actual:raise AssertionError(f'{case["name"]}: {n} C={getattr(c_r,n):04x} original={actual:04x}')
    if (c_r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0xfd7:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if c_mem!=actual:
        pos=next(i for i,(a,b) in enumerate(zip(c_mem,actual)) if a!=b)
        raise AssertionError(f'{case["name"]}: memory differs at {pos:05x}')
    return sites,edges

def cases():
    result=[]
    def add(name,kind,**regs):result.append(dict(name=name,kind=kind,seed=len(result),regs=regs))
    for count in range(256):
        add(f'bits-count-{count}', 'read_bits',cx=((1,2,8,0,9,255)[count%6]<<8)|count,
            si=(0,1,0xffff,0x8000)[count%4],dx=(count*257)^0xa55a)
    for ch in (0,1,2,8,9,255):
        for count in (0,1,8,16,17,255):add(f'bits-ch-{ch}-cl-{count}','read_bits',cx=(ch<<8)|count,si=0,dx=0xffff)
    for cursor in (0,1,0x10,0x7fff,0x8000,0xffff):
        for distance in (0,1,0xf,0x7fff,0x8000,0xffff):
            for count in (0,1,3,255):
                add(f'copy-{cursor:x}-{distance:x}-{count}','copy_match',di=cursor,ax=distance,bx=count)
    for distance in (0,1,0xffff):add(f'copy-full-{distance}','copy_match',di=0,ax=distance,bx=0xffff)
    # These live output writes overwrite PUSHed SI/DS/CX but leave the return word intact.
    for count in (1,3,5,7):add(f'copy-saved-register-alias-{count}','copy_match',es=0x7000,di=0x8000,ax=0x20,bx=count)
    for sp in (0,1,0xffff):add(f'copy-stack-wrap-{sp}','copy_match',sp=sp,di=0,ax=0xffff,bx=2)
    for cursor in (0,1,0xf,0x10,0x7fff,0x8000,0xffff):
        for flags in (2,3,0xed7):
            add(f'literal-{cursor:x}-{flags:x}','write_literal',di=cursor,flags=flags,ax=cursor^0xa55a)
    for kind in ROUTINES:
        add(f'{kind}-return-word-crossing',kind,sp=0xffff,di=0x100,ax=1,bx=0,cx=0x801)
    return result

def main():
    REPORT.unlink(missing_ok=True);lib=library();baseline=cases();sites=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);sites|=a;edges|=b
    if sites!=set(INS):raise AssertionError(f'Missing instructions {set(INS)-sites}')
    if edges!=EXPECTED:raise AssertionError(f'Missing/extra branches {EXPECTED-edges}/{edges-EXPECTED}')
    mutations=[]
    for mutation,kind in ((1,'read_bits'),(2,'copy_match'),(3,'write_literal')):
        lib=library(mutation);hit=None
        for case in baseline:
            if case['kind']!=kind:continue
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'Mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/dat.c','c/dat.h','c/regs.h','tools/cbuild.py','tools/difftest.py','tests/dat.py','metadata/symbols.json')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=len(mutations),
        mutations_detected=mutations,cases=baseline,translated_code_bytes=sum(b-a for a,b in ROUTINES.values()),
        routines=[dict(kind=k,start=a,end=b,instruction_addresses=sorted(pc for pc in sites if a<=pc<b)) for k,(a,b) in ROUTINES.items()],
        executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Quiescent near calls; full 1MiB; no executing-code or return-word writes; saved register aliases included',
        flags_note='All defined final arithmetic flags compared; TF clear'))
    print(f'PASS DAT C: {len(baseline)} cases, {len(sites)}/{len(INS)} instruction sites, {len(edges)} branch edges, 3 compiled mutations detected')

if __name__=='__main__':main()
