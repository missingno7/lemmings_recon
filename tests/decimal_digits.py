"""Original decimal leaf contract; no C coverage and no game boot."""
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated

def check():
    image,meta=unpack(ASSET.read_bytes());symbols=read_json(ROOT/'metadata/symbols.json')
    row=next(s for s in symbols if s['symbol_name']=='WriteDecimalByteDigits');start=row['address'];end=start+row['size']
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);md.detail=True
    ins={i.address:i for i in md.disasm(image[start:end],start)}
    branches={pc for pc,i in ins.items() if i.group(capstone.CS_GRP_JUMP)}
    want={(pc,i.operands[0].imm&65535) for pc,i in ins.items() if pc in branches}|{(pc,pc+ins[pc].size) for pc in branches}
    cases=[dict(value=n,si=0x100,sp=0x8000) for n in range(256)]
    cases += [dict(value=255,si=0xfffe,sp=0x8000),dict(value=100,si=0xffff,sp=0x8000),
              dict(value=9,si=0,sp=0xffff),dict(value=0,si=1,sp=0)]
    seen=set();edges=set()
    for seed,case in enumerate(cases):
        rng=random.Random(0x4bc2+seed);load=(0x1010,0x1213,0x2345)[seed%3]
        mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(image)]=relocated(image,meta['relocations'],load)
        regs={n:rng.randrange(65536) for n in oracle.REG_NAMES};regs.update(cs=load,ip=start,ds=0x4513,ss=0x7000,sp=case['sp'],si=case['si'])
        regs['ax']=(regs['ax']&0xff00)|case['value'];flags=2|(rng.randrange(65536)&0xed5)
        oracle.put16(mem,regs['ss'],regs['sp'],0xff00);expected=bytearray(mem);digits=f'{case["value"]:03d}'.encode()
        for n,value in enumerate(digits):expected[oracle.at(regs['ds'],(regs['si']+n)&65535)]=value
        outregs=regs|dict(ax=(digits[1]<<8)|digits[2],si=(regs['si']+2)&65535,sp=(regs['sp']+2)&65535,ip=0xff00)
        outflags=(flags&~0x8d5)|(4 if digits[2].bit_count()%2==0 else 0)
        u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
        for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
        u.reg_write(x.UC_X86_REG_EFLAGS,flags);previous=None;done=False
        def code(uc,pc,size,_):
            nonlocal previous,done
            off=pc-(load<<4)
            if previous in branches:edges.add((previous,off))
            if off==0xff00:done=True;uc.emu_stop();return
            if off not in ins or uc.reg_read(oracle.REG['cs'])!=load:raise AssertionError('Decimal leaf escaped')
            seen.add(off);previous=off
        u.hook_add(UC_HOOK_CODE,code);u.emu_start(oracle.at(load,start),0,count=1000)
        if not done:raise AssertionError('Decimal leaf exceeded budget')
        for name,reg in oracle.REG.items():
            if u.reg_read(reg)!=outregs[name]:raise AssertionError(f'Decimal {case}: {name} contract differs')
        if (u.reg_read(x.UC_X86_REG_EFLAGS)^outflags)&0xfd7:raise AssertionError('Decimal flags differ')
        if bytes(u.mem_read(0,1<<20))!=expected:raise AssertionError('Decimal live memory differs')
    if seen!=set(ins) or edges!=want:raise AssertionError('Decimal contract misses sites/branches')
    result=dict(case_count=len(cases),instruction_sites=sorted(seen),branch_edges=sorted(edges),image_sha256=sha(image),
        domain='Original-only independent decimal formula; all256 AL values, poisoned AH/control flags, SI and stack wrap; intact instruction/return bytes; no C translation')
    write_json(BUILD/'decimal-digits-contracts.json',result)
    print(f'PASS decimal ASM contract: {len(cases)} cases, {len(seen)} sites, {len(edges)} branch edges; no C coverage')
    return result
if __name__=='__main__':check()
