"""Original timer-chain caller tails against constructed external IRET services.

The external service is fixture code. Input polling is a declared near boundary.
No timer game body, original BIOS/DOS ISR or original game boot is executed.
"""
import random
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import BUILD,sha,write_json
from unpack import unpack,ASSET,relocated
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x

REGS=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip')
REG={n:getattr(x,'UC_X86_REG_'+n.upper()) for n in REGS}
STOP=0xff00
def address(seg,off):return ((seg<<4)+(off&0xffff))&0xfffff
def putword(mem,seg,off,value):
    p=address(seg,off);mem[p]=value&255;mem[(p+1)&0xfffff]=(value>>8)&255

def run_case(kind,tag,clobber=False,change_ds=False,poll_clobber=False,sp=0x8000):
    image,oracle=unpack(ASSET.read_bytes());cs=(0x1010,0x1213,0x2345)[tag%3]
    ds=(cs+0x9a9)&0xffff;ss=0x7000;external=0x5000;newds=0x5200
    rng=random.Random(0x71A0+tag);mem=bytearray(rng.randbytes(1<<20))
    mem[cs<<4:(cs<<4)+len(image)]=relocated(image,oracle['relocations'],cs)
    r={n:rng.randrange(0x10000) for n in REGS}
    r.update(cs=cs,ds=ds,ss=ss,sp=sp,ip=0x1893 if kind=='game' else 0x4c66)
    # Distinct saved registers expose save ordering and the missing menu ES save.
    saved={n:rng.randrange(0x10000) for n in ('ax','bx','cx','dx','si','di','bp','ds','es')}
    flags=2|((tag*0x95)&0xed5);return_flags=2|((tag*0x51)&0xed5)
    inner_flags=2|((tag*0x31)&0xed5)
    order=('di','si','bp','bx','dx','cx','es','ds','ax') if kind=='game' else ('ds','bp','di','si','dx','cx','bx','ax')
    words=([inner_flags] if kind=='game' else [])+[saved[n] for n in order]+[STOP,cs,return_flags]
    for n,v in enumerate(words):putword(mem,ss,sp+2*n,v)
    putword(mem,ds,0x1fbe,0x100);putword(mem,ds,0x1fc0,external)
    for frame in (ds,newds):
        mem[address(frame,0x1fcf)]=0x22;mem[address(frame,0x1fcd)]=0xff
    # Actual fixture machine code returns with IRET through the caller's frame.
    code=b''
    if clobber:
        code+=bytes.fromhex('b83412 bb4523 b95634 ba6745 be7856 bf8967 bdaa78')
        code+=bytes.fromhex('b8bbbb 8ec0') # ES is deliberately clobbered.
    if change_ds:code+=bytes.fromhex('b80052 8ed8')
    code+=b'\xcf'
    mem[address(external,0x100):address(external,0x100)+len(code)]=code
    expected=bytearray(mem)
    resume=0x189d if kind=='game' else 0x4c70
    putword(expected,ss,sp-2,flags);putword(expected,ss,sp-4,cs);putword(expected,ss,sp-6,resume)
    if kind=='game':
        frame=newds if change_ds else ds
        expected[address(frame,0x1fcf)]=0xff
        expected[address(frame,0x1fcd)]=0
    else:putword(expected,ss,sp-2,0x4c75)
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,v in r.items():u.reg_write(REG[n],v)
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    done=False;poll=False;seen=set();external_seen=False;frames=[]
    def hook(uc,pc,size,_):
        nonlocal done,poll,external_seen
        if pc==address(cs,STOP):done=True;uc.emu_stop();return
        actual_cs=uc.reg_read(REG['cs'])
        if actual_cs==external:
            if not address(external,0x100)<=pc<address(external,0x100)+len(code):
                raise AssertionError('External fixture escaped')
            if not external_seen:
                current_sp=uc.reg_read(REG['sp'])
                frame=b''.join(bytes(uc.mem_read(address(ss,current_sp+2*n),2)) for n in range(3))
                if frame!=struct.pack('<HHH',resume,cs,flags):raise AssertionError(f'{kind}/{tag}: original IRET chain frame differs: {frame.hex()}')
                frames.append(frame.hex());external_seen=True
            return
        if actual_cs!=cs:raise AssertionError('Unexpected code segment')
        off=pc-(cs<<4)
        if kind=='menu' and off==0x418c:
            poll=True;uc.emu_stop();return
        lo,hi=(0x1893,0x18b2) if kind=='game' else (0x4c66,0x4c7e)
        if not lo<=off<hi:raise AssertionError(f'Execution outside identified chain tail at {off:04X}')
        seen.add(off)
    def interrupt(uc,num,_):raise AssertionError(f'Unexpected interrupt {num:02X}')
    u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,interrupt)
    u.emu_start(address(cs,r['ip']),0,count=1000)
    if poll:
        if u.reg_read(REG['ds'])!=(newds if change_ds else ds):raise AssertionError('Chain normalized external DS unexpectedly')
        if u.reg_read(REG['dx'])&255!=0xff:raise AssertionError('Input poll was not entered with DL=FF')
        if poll_clobber:
            for n in ('ax','bx','cx','dx','si','di','bp','ds','es'):u.reg_write(REG[n],0xcccc)
        current_sp=u.reg_read(REG['sp'])
        ret=int.from_bytes(u.mem_read(address(ss,current_sp),2),'little')
        if ret!=0x4c75:raise AssertionError('Input poll near return differs')
        u.reg_write(REG['sp'],(current_sp+2)&0xffff);u.reg_write(REG['ip'],ret)
        u.emu_start(address(cs,ret),0,count=1000)
    if not done or not external_seen:raise AssertionError('Chain failed to return within budget')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=expected:
        at=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
        raise AssertionError(f'{kind}/{tag}: memory {at:05X}={actual[at]:02X}/{expected[at]:02X}')
    for n in order:
        if u.reg_read(REG[n])!=saved[n]:raise AssertionError(f'Saved {n} not restored')
    if kind=='menu':
        wanted=0xcccc if poll_clobber else 0xbbbb if clobber else r['es']
        if u.reg_read(REG['es'])!=wanted:raise AssertionError('Original unsaved ES effect changed')
    if u.reg_read(REG['sp'])!=(sp+2*len(words))&0xffff:raise AssertionError('Stack cleanup differs')
    if u.reg_read(x.UC_X86_REG_EFLAGS)&0xfd7!=return_flags:raise AssertionError('Final IRET flags differ')
    return dict(kind=kind,tag=tag,load_segment=cs,stack_offset=sp,external_clobber=clobber,
                external_ds_change=change_ds,poll_clobber=poll_clobber,
                frames=frames,instructions=sorted(seen),memory_sha256=sha(actual))

def check():
    cases=[]
    for kind in ('game','menu'):
        for clobber,change_ds in ((False,False),(True,False),(True,True)):
            for sp in (0x8000,2,0xfff8):
                cases.append(run_case(kind,len(cases),clobber,change_ds,kind=='menu',sp))
    cases.append(run_case('menu',len(cases),True,True,False))
    sites={p for r in cases for p in r['instructions']}
    result=dict(case_count=len(cases),cases=cases,original_instruction_sites=sorted(sites),
                scope='Original timer-chain caller tails; fixture external IRET and declared input-poll boundary; not BIOS, C, full IRQ or game execution')
    write_json(BUILD/'timer-chain-tests.json',result)
    print(f'PASS timer chains: {len(cases)} bounded tails, full memory/saved-register/IRET flag comparison, {len(sites)} caller sites')
    return result

if __name__=='__main__':check()
