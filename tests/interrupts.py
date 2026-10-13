"""Bounded installed main handlers with constructed interrupt/callback frames.

INT62 and the cursor callback are declared fixture boundaries. Their service
semantics are not original-handler coverage. No original game startup executes.
"""
import random
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
def inc_flags(value,flags):
    result=(value+1)&255
    return ((flags&~0x8d4)|(4 if result.bit_count()%2==0 else 0)|
            (0x10 if value&15==15 else 0)|(0x40 if result==0 else 0)|
            (result&0x80)|(0x800 if value==0x7f else 0))

def run_case(kind,tag,count=0,second=0,inhibit=0,change_ds=False,sp=0x8000):
    image,oracle=unpack(ASSET.read_bytes());cs=(0x1010,0x1213,0x2345)[tag%3]
    game_ds=(cs+0x9a9)&0xffff;ss=0x7000;other=0x5200
    rng=random.Random(0x1A70+tag);mem=bytearray(rng.randbytes(1<<20))
    mem[cs<<4:(cs<<4)+len(image)]=relocated(image,oracle['relocations'],cs)
    r={n:rng.randrange(0x10000) for n in REGS}
    entry={'bridge':0xf70,'critical_error':0x18f8,'mouse_return':0xf6f}[kind]
    r.update(cs=cs,ss=ss,sp=sp,ip=entry)
    flags=2|((tag*0x95)&(0xed5 if kind=='mouse_return' else 0xfd5))
    putword(mem,ss,sp,STOP);putword(mem,ss,sp+2,cs)
    if kind!='mouse_return':putword(mem,ss,sp+4,flags)
    mem[address(cs,0x83be)]=inhibit
    mem[address(game_ds,0x2002)]=count;mem[address(game_ds,0x2003)]=second
    mem[address(other,0x2002)]=1;mem[address(other,0x2003)]=0x80
    expected=bytearray(mem);out=dict(r);out.update(ip=STOP)
    chain_flags=None;cursor_expected=False
    if kind=='mouse_return':out['sp']=(sp+4)&0xffff
    else:
        out['sp']=(sp+6)&0xffff
        putword(expected,ss,sp-2,r['ds'])
        if kind=='critical_error':
            expected[address(game_ds,0x1fdf)]=0xff
            out['ax']=game_ds&0xff00
        else:
            putword(expected,ss,sp-4,r['ax'])
            expected[address(game_ds,0x2002)]=(count+1)&255
            expected[address(game_ds,0x2003)]=(second+1)&255
            chain_flags=inc_flags(second,inc_flags(count,flags&~0x300))
            putword(expected,ss,sp-6,chain_flags);putword(expected,ss,sp-8,cs);putword(expected,ss,sp-10,0xf81)
            destination=other if change_ds else game_ds
            expected[address(destination,0x2002)]=(expected[address(destination,0x2002)]-1)&255
            expected[address(destination,0x2003)]=(expected[address(destination,0x2003)]-1)&255
            out['dx']=0xabcd # Deliberate external-service clobber.
            cursor_expected=inhibit==0 and expected[address(destination,0x2002)]==0
            if cursor_expected:
                putword(expected,ss,sp-6,0xabcd);putword(expected,ss,sp-8,0xf9c)
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,v in r.items():u.reg_write(REG[n],v)
    u.reg_write(x.UC_X86_REG_EFLAGS,flags if kind=='mouse_return' else flags&~0x300)
    stopped=False;cursor=False;events=[];sites=set()
    def interrupt(uc,number,_):
        if kind!='bridge' or number!=0x62:raise AssertionError(f'Unexpected interrupt {number:02X}')
        got=uc.reg_read(x.UC_X86_REG_EFLAGS)&0xfd7
        if got!=chain_flags:raise AssertionError('Nested-service incoming flags differ')
        actual_sp=uc.reg_read(REG['sp'])
        if actual_sp!=(sp-4)&0xffff or uc.reg_read(REG['ip'])!=0xf81:raise AssertionError('Nested-service caller frame differs')
        # Unicorn exposes a software INT as a service hook. Model its declared
        # frame/IRET transport, including residue, without running a BIOS body.
        for delta,value in ((2,chain_flags),(4,cs),(6,0xf81)):
            uc.mem_write(address(ss,actual_sp-delta),bytes((value&255,value>>8)))
        events.append(dict(vector=number,return_ip=0xf81,flags=chain_flags))
        uc.reg_write(REG['dx'],0xabcd)
        if change_ds:uc.reg_write(REG['ds'],other)
    def code(uc,pc,size,_):
        nonlocal stopped,cursor
        if pc==address(cs,STOP):stopped=True;uc.emu_stop();return
        off=pc-(cs<<4)
        if kind=='bridge' and off==0x587f:cursor=True;uc.emu_stop();return
        lo,hi={'bridge':(0xf70,0xfa0),'critical_error':(0x18f8,0x1908),'mouse_return':(0xf6f,0xf70)}[kind]
        if uc.reg_read(REG['cs'])!=cs or not lo<=off<hi:raise AssertionError('Handler escaped identified range')
        sites.add(off)
    u.hook_add(UC_HOOK_INTR,interrupt);u.hook_add(UC_HOOK_CODE,code)
    u.emu_start(address(cs,entry),0,count=1000)
    if cursor:
        if not cursor_expected:raise AssertionError('Unexpected cursor callback')
        actual_sp=u.reg_read(REG['sp'])
        ret=int.from_bytes(u.mem_read(address(ss,actual_sp),2),'little')
        if ret!=0xf9c:raise AssertionError('Cursor callback frame differs')
        u.reg_write(REG['dx'],0xdddd);u.reg_write(REG['ax'],0xeeee)
        u.reg_write(REG['sp'],(actual_sp+2)&0xffff);u.reg_write(REG['ip'],ret)
        u.emu_start(address(cs,ret),0,count=1000)
    if not stopped or cursor!=cursor_expected:raise AssertionError('Handler return/guard differs')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=expected:
        at=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
        raise AssertionError(f'{kind}/{tag}: memory {at:05X}={actual[at]:02X}/{expected[at]:02X}')
    for n,v in out.items():
        if u.reg_read(REG[n])!=v:raise AssertionError(f'{kind}/{tag}: {n} differs')
    if u.reg_read(x.UC_X86_REG_EFLAGS)&0xfd7!=flags:raise AssertionError('Return flags differ')
    return dict(kind=kind,tag=tag,load_segment=cs,stack_offset=sp,count=count,second=second,
                inhibit=inhibit,external_ds_change=change_ds,cursor=cursor,
                events=events,instructions=sorted(sites),memory_sha256=sha(actual))

def check():
    cases=[]
    for kind in ('mouse_return','critical_error'):
        for sp in (0x8000,2,0xfffc):cases.append(run_case(kind,len(cases),sp=sp))
    for count,second in ((0,0),(1,1),(0xff,0xff),(0x7f,0x7f),(0x80,0x80)):
        for inhibit in (0,1):cases.append(run_case('bridge',len(cases),count,second,inhibit))
    cases.append(run_case('bridge',len(cases),0,0,0,False,2))
    cases.append(run_case('bridge',len(cases),0,0,1,False,0xfffc))
    cases.append(run_case('bridge',len(cases),2,5,0,True))
    sites={pc for r in cases for pc in r['instructions']}
    result=dict(case_count=len(cases),cases=cases,original_instruction_sites=sorted(sites),
                scope='Installed main handler bodies; INT62/cursor are declared boundaries; not external ISR, C or game execution')
    write_json(BUILD/'interrupt-tests.json',result)
    print(f'PASS installed handlers: {len(cases)} bounded frames, full memory/register/defined-flag comparison, {len(sites)} original sites')
    return result

if __name__=='__main__':check()
