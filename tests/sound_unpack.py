"""Original CS:1BAF decoder vs static DAT extractor; no driver/game execution."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import struct
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_INTR,UC_HOOK_CODE
from unicorn import x86_const as x
from common import ROOT
from unpack import ASSET,unpack,relocated
from resources import decode_section

def check(name,segment=0x3000,poison=0xa5):
    data=(ROOT/'assets'/f'{name}.dat').read_bytes()
    expected,meta=decode_section(data)
    static,oracle=unpack(ASSET.read_bytes())
    u=Uc(UC_ARCH_X86,UC_MODE_16)
    u.mem_map(0,0x100000)
    u.mem_write(0,bytes([poison])*0x100000)
    u.mem_write(0x10100,relocated(static,oracle['relocations'],0x1010))
    u.mem_write(0x19b90+0x1f93,b'\0') # DOS read path, no preloaded cache.
    u.mem_write(0x70000+0x8000,struct.pack('<H',0xff00))
    for reg,val in dict(cs=0x1010,ip=0x1baf,ds=segment,es=segment,si=0,di=0,
                        ss=0x7000,sp=0x8000,bx=7,eflags=0x202).items():
        u.reg_write(getattr(x,'UC_X86_REG_'+reg.upper()),val)
    pos=0
    reads=[]
    stopped=False
    executed=set()
    def interrupt(uc,number,_):
        nonlocal pos
        ax=uc.reg_read(x.UC_X86_REG_AX)
        if number!=0x21 or ax>>8!=0x3f or uc.reg_read(x.UC_X86_REG_BX)!=7:
            raise AssertionError(f'Unexpected service {number:02x}/{ax:04x}')
        count=uc.reg_read(x.UC_X86_REG_CX)
        target=(uc.reg_read(x.UC_X86_REG_DS)<<4)+uc.reg_read(x.UC_X86_REG_DX)
        part=data[pos:pos+count]
        uc.mem_write(target,part)
        reads.append(dict(offset=pos,count=count,returned=len(part)))
        pos+=len(part)
        uc.reg_write(x.UC_X86_REG_AX,len(part))
        uc.reg_write(x.UC_X86_REG_EFLAGS,uc.reg_read(x.UC_X86_REG_EFLAGS)&~1)
    def code(uc,address,size,_):
        nonlocal stopped
        if address==0x20000:
            stopped=True
            uc.emu_stop()
        else:
            executed.add(address-0x10100)
    u.hook_add(UC_HOOK_INTR,interrupt)
    u.hook_add(UC_HOOK_CODE,code)
    u.emu_start(0x11caf,0,count=5_000_000)
    if not stopped:
        raise AssertionError('Decoder did not return within budget')
    actual=bytes(u.mem_read(segment<<4,len(expected)))
    if actual!=expected:
        off=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
        raise AssertionError(f'{name}: output mismatch at{off:04X}')
    assert pos==len(data)
    assert u.reg_read(x.UC_X86_REG_EFLAGS)&0x40, 'Original checksum failure'
    assert u.reg_read(x.UC_X86_REG_DI)==0
    assert u.reg_read(x.UC_X86_REG_DS)==segment
    print(f'PASS {name}: {len(expected)} bytes exact, {len(executed)} original instructions, {reads}')
    return dict(name=name,segment=segment,poison=poison,reads=reads,instructions=sorted(executed),**meta)

if __name__=='__main__':
    from common import BUILD,write_json
    results=[check(n,s,p) for n in ('adlib','tandysnd') for s,p in ((0x3000,0xa5),(0x4000,0x5a))]
    write_json(BUILD/'sound-unpack-tests.json',results)
