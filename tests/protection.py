"""Bounded original protection-handler checks with constructed interrupt frames.

No protected disk routine, BIOS service, game entry or legacy interpreter runs.
The Python expectation describes handler effects, not instruction execution.
"""
import random
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import BUILD,sha,write_json
from unpack import ASSET,unpack,relocated
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x

TF,IF=0x100,0x200
REGS=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip')

def physical(seg,off):
    return ((seg<<4)+(off&0xffff))&0xfffff

def word(mem,seg,off):
    p=physical(seg,off)
    return mem[p]|mem[(p+1)&0xfffff]<<8

def putword(mem,seg,off,val):
    p=physical(seg,off)
    mem[p]=val&255
    mem[(p+1)&0xfffff]=(val>>8)&255

def transform(mem,seg,pc):
    prior=word(mem,seg,pc-2)^0xffff
    key=((prior<<1)|(prior>>15))&0xffff
    return word(mem,seg,pc)^key

def expectation(mem,r,kind):
    """Expected full memory and return state, including saved-stack residue."""
    mem=bytearray(mem);r=dict(r)
    cs,ss,sp=r['cs'],r['ss'],r['sp']
    return_pc,return_cs,flags=(word(mem,ss,sp+n) for n in (0,2,4))
    for delta,reg in ((2,'ax'),(4,'si'),(6,'ds')):
        putword(mem,ss,sp-delta,r[reg])
    if kind=='int3':
        # CALL-next return is overwritten by PUSH CS at the same stack word.
        putword(mem,ss,sp-8,cs)
        putword(mem,0,4,0xdff);putword(mem,0,6,cs)
        for pc in range(0xdff,0xe3a):
            p=physical(cs,pc);mem[p]=(-mem[p])&255
        flags^=TF|IF
        putword(mem,ss,sp+4,flags)
        if not flags&TF:
            oldpc,oldcs=word(mem,0,0),word(mem,0,2)
            restored=transform(mem,oldcs,oldpc)
            if restored&255!=0xcc:
                putword(mem,oldcs,oldpc,restored)
    else:
        oldpc,oldcs=word(mem,0,0),word(mem,0,2)
        previous_plain=word(mem,oldcs,oldpc)
        putword(mem,oldcs,oldpc,transform(mem,oldcs,oldpc))
        # The transformed INT1 handler checks the displaced plaintext byte.
        if previous_plain&255==0xcc:
            r.update(sp=(sp+6)&0xffff,cs=return_cs,ip=return_pc,flags=flags)
            return mem,r
    if flags&TF or kind=='int1':
        putword(mem,return_cs,return_pc,transform(mem,return_cs,return_pc))
        putword(mem,ss,sp-8,return_cs)
        putword(mem,0,0,return_pc);putword(mem,0,2,return_cs)
    r.update(sp=(sp+6)&0xffff,cs=return_cs,ip=return_pc,flags=flags)
    return mem,r

def run_case(kind,tag,oldpc=0x66d,nextpc=0x66e,stop_marker=False,
             initial_tf=False,prior_word=None,old_segment=None,return_segment=None,
             frame_sp=0x8000,expected_visible=None):
    static,oracle=unpack(ASSET.read_bytes())
    cs=(0x1010,0x1213,0x2345)[tag%3]
    rng=random.Random(0xC1A0+tag)
    mem=bytearray(rng.randbytes(1<<20))
    mem[cs<<4:(cs<<4)+len(static)]=relocated(static,oracle['relocations'],cs)
    r={n:rng.randrange(0x10000) for n in REGS}
    r.update(cs=cs,ss=0x7000,sp=frame_sp,ip=0xdb3 if kind=='int3' else 0xdff,
             flags=0x2|IF|(TF if initial_tf else 0)|((tag*0x51)&0xcd5))
    oldcs=cs if old_segment is None else old_segment
    nextcs=cs if return_segment is None else return_segment
    putword(mem,0,0,oldpc);putword(mem,0,2,oldcs)
    # INT1 is plaintext whenever TF is active; INT3 toggles its 59-byte image.
    if kind=='int1' or initial_tf:
        for pc in range(0xdff,0xe3a):
            p=physical(cs,pc);mem[p]=(-mem[p])&255
    if prior_word is not None:
        putword(mem,oldcs,oldpc-2,prior_word)
    if kind=='int1' or initial_tf:
        if stop_marker:
            putword(mem,oldcs,oldpc,0x90cc)
        else:
            putword(mem,oldcs,oldpc,transform(mem,oldcs,oldpc))
    for off,val in ((0,nextpc),(2,nextcs),(4,r['flags'])):
        putword(mem,r['ss'],r['sp']+off,val)
    expected,er=expectation(mem,r,kind)
    uc=Uc(UC_ARCH_X86,UC_MODE_16);uc.mem_map(0,1<<20);uc.mem_write(0,bytes(mem))
    for n in REGS:uc.reg_write(getattr(x,'UC_X86_REG_'+n.upper()),r[n])
    # Interrupt entry has already cleared TF/IF; saved flags are in the frame.
    uc.reg_write(x.UC_X86_REG_EFLAGS,r['flags']&~(TF|IF))
    seen=set();stopped=False
    def code(u,pc,size,_):
        nonlocal stopped
        if pc==physical(nextcs,nextpc):
            stopped=True;u.emu_stop();return
        off=pc-(cs<<4)
        allowed=(0xdb3<=off<0xe3a) if kind=='int3' else (0xdff<=off<0xe3a)
        if not allowed:raise AssertionError(f'Execution outside identified {kind} handler: {pc:05X}')
        seen.add(off)
    def interrupt(u,number,_):
        raise AssertionError(f'Unexpected interrupt {number:02X}')
    uc.hook_add(UC_HOOK_CODE,code);uc.hook_add(UC_HOOK_INTR,interrupt)
    uc.emu_start(physical(cs,r['ip']),0,count=2000)
    if not stopped:raise AssertionError('Handler did not return within budget')
    actual=bytes(uc.mem_read(0,1<<20))
    if actual!=expected:
        at=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
        raise AssertionError(f'{kind}/{tag}: memory mismatch at {at:05X}: {actual[at]:02X}/{expected[at]:02X}')
    if expected_visible is not None:
        at=physical(nextcs,nextpc)
        if actual[at:at+len(expected_visible)]!=expected_visible:
            raise AssertionError(f'Original handler does not expose derived instruction at {nextpc:04X}')
    for n in REGS:
        got=uc.reg_read(getattr(x,'UC_X86_REG_'+n.upper()))
        if got!=er[n]:raise AssertionError(f'{kind}/{tag}: {n} {got:04X}/{er[n]:04X}')
    got=uc.reg_read(x.UC_X86_REG_EFLAGS)&0x0fd7
    if got!=(er['flags']&0x0fd7):raise AssertionError(f'{kind}/{tag}: flags {got:04X}/{er["flags"]:04X}')
    return dict(kind=kind,tag=tag,load_segment=cs,oldpc=oldpc,nextpc=nextpc,
                stop_marker=stop_marker,initial_tf=initial_tf,instructions=sorted(seen),
                input_sha256=sha(mem),output_sha256=sha(actual))

def check():
    cases=[]
    cases.append(run_case('int3',0,nextpc=0x66d))
    cases.append(run_case('int3',1,nextpc=0xda2))
    cases.append(run_case('int3',2,oldpc=0x96f,nextpc=0x970,initial_tf=True))
    cases.append(run_case('int3',3,oldpc=0xd9e,nextpc=0xd9f,initial_tf=True))
    # The low-byte CC guard in the original INT3 checks restored ciphertext.
    cases.append(run_case('int3',4,oldpc=0xda1,nextpc=0xda2,initial_tf=True))
    for tag,(oldpc,nextpc) in enumerate(((0x66d,0x66e),(0x66e,0x671),
                                      (0x675,0x676),(0x689,0x68f),
                                      (0x695,0x786),(0x785,0x698),
                                      (0xda2,0x8c8)),5):
        cases.append(run_case('int1',tag,oldpc=oldpc,nextpc=nextpc,initial_tf=True))
    cases.append(run_case('int1',12,oldpc=0xa010,nextpc=0xa020,
                          stop_marker=True,initial_tf=True))
    for tag,prior in enumerate((0,0xffff,0x7fff,0x8000),13):
        cases.append(run_case('int1',tag,oldpc=0x1000,nextpc=0x2000,
                              old_segment=0x5000,return_segment=0x5100,
                              prior_word=prior,initial_tf=True))
    cases.append(run_case('int1',17,oldpc=1,nextpc=0xffff,old_segment=0x5000,
                          return_segment=0x5100,initial_tf=True,frame_sp=0))
    cases.append(run_case('int3',18,nextpc=0x66d,frame_sp=0xfffc))
    from protection import derive
    stream=derive()[3]
    point_cases=[]
    for tag,row in enumerate(stream['instructions'],100):
        if row['state']=='tf_on':
            point_cases.append(run_case('int1',tag,oldpc=0xa010,nextpc=row['address'],
                                        initial_tf=True,expected_visible=bytes.fromhex(row['bytes'])))
    cases+=point_cases
    covered={a for r in cases for a in r['instructions']}
    result=dict(cases=cases,case_count=len(cases),instruction_addresses=sorted(covered),
                constructed_frame_cases=19,derived_instruction_points=len(point_cases),
                scope='Original INT3 and transformed INT1 handlers only; no C or game execution')
    write_json(BUILD/'protection-tests.json',result)
    print(f'PASS protection: 19 constructed frames + {len(point_cases)} derived instruction points, full memory/register/flag comparison, {len(covered)} handler instruction sites')
    return result

if __name__=='__main__':
    from protection_native import main
    main()
