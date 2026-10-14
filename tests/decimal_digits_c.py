"""Native decimal-digit leaf against bounded original ASM and decimal math."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['WriteDecimalByteDigits'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY)}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
EDGES={(pc,i.operands[0].imm&0xffff) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES}
RET=END-1
MEM=ctypes.POINTER(ctypes.c_uint8)

class Regs(ctypes.Structure):
    _fields_=[(name,ctypes.c_uint16) for name in
        ('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip','flags')]


def physical(segment,offset):
    return ((segment<<4)+(offset&0xffff))&0xfffff


def cases():
    out=[]
    def add(name,number,**kw):
        out.append(dict(name=name,number=number,seed=len(out),**kw))
    for number in range(256):
        add(f'value-{number:03d}',number,ah=(number*73+0xa5)&255)
    for si in (0,1,0xfffe,0xffff):
        add(f'si-wrap-{si:04x}',(si^0xa5)&255,si=si,df=True)
    for sp in (0,1,0xfffe,0xffff):
        add(f'stack-wrap-{sp:04x}',(sp^0x5a)&255,sp=sp)
    for segment,si in ((0xffff,0x20),(0xf000,0xffff),(0xfff0,0x0010)):
        add(f'physical-wrap-{segment:04x}-{si:04x}',0x7b,ds=segment,si=si,df=True)
    add('return-alias-full-word',0x7b,ds=0x7000,ss=0x7000,si=0x8000,sp=0x8000)
    add('return-alias-high-byte',0x25,ds=0x7000,ss=0x7000,si=0x8001,sp=0x8000)
    add('return-alias-offset-wrap',0x99,ds=0x7000,ss=0x7000,si=0xffff,sp=0xffff)
    return out


def prepare(case):
    rng=random.Random(0x4bc2+case['seed'])
    load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20))
    mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={name:rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=case.get('ds',0x4513),
        ss=case.get('ss',0x7000),sp=case.get('sp',0x8000),si=case.get('si',0x100))
    regs['ax']=((case.get('ah',(case['seed']*109+0x5b)&255)<<8)|case['number'])
    flags=2|(rng.randrange(65536)&0xed5)
    if case.get('df'):
        flags|=0x400
    else:
        flags&=~0x400
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags


def load_library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'decimal-digits-m{mutation}.dll',mutation,'decimal_digits')))
    lib.lmn_write_decimal_digits_adapter.argtypes=[MEM,ctypes.POINTER(Regs)]
    lib.lmn_write_decimal_digits_adapter.restype=None
    return lib


def independent_result(mem,regs,flags,number):
    digits=f'{number:03d}'.encode('ascii')
    expected=bytearray(mem)
    for i,digit in enumerate(digits):
        expected[physical(regs['ds'],regs['si']+i)]=digit
    units=number%10
    result=(units+0x30)&255
    status=((result.bit_count()%2==0)*0x04)
    expected_flags=(flags&~0x8d5)|status
    expected_regs=regs.copy()
    expected_regs.update(ax=(digits[1]<<8)|digits[2],
        si=(regs['si']+2)&0xffff,sp=(regs['sp']+2)&0xffff,
        ip=expected[physical(regs['ss'],regs['sp'])] |
           (expected[(physical(regs['ss'],regs['sp'])+1)&0xfffff]<<8))
    return expected,expected_regs,expected_flags,digits


def run_case(lib,case,check_c=True):
    mem,regs,flags=prepare(case)
    expected,expected_regs,expected_flags,digits=independent_result(mem,regs,flags,case['number'])

    c_mem=bytearray(mem)
    c_regs=Regs(**regs,flags=flags)
    if check_c:
        lib.lmn_write_decimal_digits_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(c_regs))

    # Unicorn exposes addresses above 1 MiB directly; the pinned DOS machine
    # contract is 20-bit, so mirror those rare writes through the A20 wrap.
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<21);u.mem_write(0,bytes(mem))
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
            raise AssertionError(f"{case['name']}: decimal leaf escaped at {off:04x}")
        sites.add(off);previous=off
    def a20_wrap(uc,access,address,size,value,_):
        for i in range(size):
            target=address+i
            if target>=1<<20:
                uc.mem_write((target&0xfffff),bytes([(value>>(i*8))&255]))
    u.hook_add(UC_HOOK_CODE,code)
    u.hook_add(UC_HOOK_MEM_WRITE,a20_wrap)
    u.emu_start(physical(regs['cs'],ENTRY),0,count=1000)
    if not done:raise AssertionError(f"{case['name']}: decimal leaf exceeded instruction budget")
    original_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()}
    original_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    original_mem=bytes(u.mem_read(0,1<<20))
    for name in oracle.REG_NAMES:
        if original_regs[name]!=expected_regs[name]:
            raise AssertionError(f"{case['name']}: original {name} differs from independent decimal contract")
    if (original_flags^expected_flags)&0xfd7:
        raise AssertionError(f"{case['name']}: original defined flags differ from independent ADD contract")
    if original_mem!=bytes(expected):
        p=next(i for i,(a,b) in enumerate(zip(original_mem,expected)) if a!=b)
        raise AssertionError(f"{case['name']}: original RAM differs from independent digits at {p:05x}")
    if check_c:
        for name in oracle.REG_NAMES:
            if getattr(c_regs,name)!=original_regs[name]:
                raise AssertionError(f"{case['name']}: C {name}={getattr(c_regs,name):04x}, original={original_regs[name]:04x}")
        if (c_regs.flags^original_flags)&0xfd7:
            raise AssertionError(f"{case['name']}: C defined flags differ from original")
        if bytes(c_mem)!=original_mem:
            p=next(i for i,(a,b) in enumerate(zip(bytes(c_mem),original_mem)) if a!=b)
            raise AssertionError(f"{case['name']}: C whole RAM differs from original at {p:05x}")
    return sites,edges,digits


def main():
    report=BUILD/'decimal-digits-c-differential.json';report.unlink(missing_ok=True)
    baseline=cases();lib=load_library();sites=set();edges=set()
    for case in baseline:
        got_sites,got_edges,_=run_case(lib,case)
        sites|=got_sites;edges|=got_edges
    if sites!=set(INS):raise AssertionError(f'Missing decimal instruction sites: {set(INS)-sites}')
    if edges!=EDGES:raise AssertionError(f'Missing decimal branch edges: {EDGES-edges}')

    mutant_cases={1:baseline[0],2:baseline[1],3:next(c for c in baseline if c.get('df'))}
    mutations=[]
    for mutation,case in mutant_cases.items():
        mutant=load_library(mutation)
        try:
            run_case(mutant,case)
        except AssertionError:
            mutations.append(dict(mutation=mutation,case=case['name']))
        else:
            raise AssertionError(f'Decimal compiled mutation {mutation} survived')

    paths=('c/decimal_digits.c','c/decimal_digits.h','c/regs.h','tools/cbuild.py',
           'tests/decimal_digits.py','tests/decimal_digits_c.py','metadata/symbols.json','tools/difftest.py')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),
        mutation_count=len(mutations),mutations_detected=mutations,cases=[c['name'] for c in baseline],
        translated_code_bytes=sum(i.size for i in INS.values()),instruction_sites=sorted(sites),
        branch_edges=sorted(edges),routine=dict(name='WriteDecimalByteDigits',start=ENTRY,end=END),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Direct DS:SI writes, three ASCII digits, AX tens/units, SI+2, 20-bit physical wrapping, DF-independent forward writes, final ADD flags, live RET-word reread after stack aliases'))
    print(f'PASS decimal digits C: {len(baseline)} cases, {len(sites)} instruction sites, {len(edges)} branch edges; {len(mutations)} compiled mutations detected')


if __name__=='__main__':main()
