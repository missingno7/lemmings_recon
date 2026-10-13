"""Bounded original callback callers with explicit constructed callee boundaries.

These fixtures verify pointer/stack routing. Callee graphics, device and input
semantics are intercepted and are not part of the execution coverage claim.
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

CS,DS,SS=0x1010,0x19b9,0x7000
STOP=0xff00
REGS=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip')
REG={n:getattr(x,'UC_X86_REG_'+n.upper()) for n in REGS}

def address(seg,off):return ((seg<<4)+(off&0xffff))&0xfffff
def word(mem,seg,off):
    p=address(seg,off);return mem[p]|mem[(p+1)&0xfffff]<<8
def putword(mem,seg,off,value):
    p=address(seg,off);mem[p]=value&255;mem[(p+1)&0xfffff]=(value>>8)&255

class Fixture:
    def __init__(self,entry,tag):
        image,oracle=unpack(ASSET.read_bytes())
        self.mem=bytearray(random.Random(0xD15A+tag).randbytes(1<<20))
        self.mem[CS<<4:(CS<<4)+len(image)]=relocated(image,oracle['relocations'],CS)
        self.regs={n:(0x1234+tag*13+idx*0x211)&0xffff for idx,n in enumerate(REGS)}
        self.regs.update(cs=CS,ds=DS,es=DS,ss=SS,sp=0x8000,ip=entry)
        self.flags=0x202
        putword(self.mem,SS,0x8000,STOP)

    def run(self,ranges,stubs,observe=None):
        u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(self.mem))
        for n,v in self.regs.items():u.reg_write(REG[n],v)
        u.reg_write(x.UC_X86_REG_EFLAGS,self.flags)
        seen=set();trace=[];pending=None;done=False;steps=0
        def code(uc,pc,size,_):
            nonlocal pending,done,steps
            off=pc-(CS<<4)
            if pc==address(CS,STOP):done=True;uc.emu_stop();return
            if uc.reg_read(REG['cs'])!=CS:raise AssertionError('Unexpected code segment')
            if off in stubs:
                pending=off;uc.emu_stop();return
            if not any(lo<=off<hi for lo,hi in ranges):raise AssertionError(f'Execution outside caller fixture at {off:04X}')
            steps+=1
            if steps>20000:raise AssertionError('Caller instruction budget exceeded')
            seen.add(off)
            if observe:observe(uc,off,trace)
        def interrupt(uc,num,_):raise AssertionError(f'Unexpected interrupt {num:02X}')
        u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt)
        for event in range(200):
            u.emu_start(address(u.reg_read(REG['cs']),u.reg_read(REG['ip'])),0,count=20001)
            if done:break
            if pending is None:raise AssertionError('Caller did not reach a bounded boundary')
            target=pending;pending=None
            stubs[target](u,trace)
            # Declared near callee RET boundary; CALL/JMP themselves run originally.
            sp=u.reg_read(REG['sp']);seg=u.reg_read(REG['ss'])
            ret=int.from_bytes(u.mem_read(address(seg,sp),2),'little')
            u.reg_write(REG['sp'],(sp+2)&0xffff);u.reg_write(REG['ip'],ret)
        if not done:raise AssertionError('Caller boundary budget exceeded')
        self.actual=bytes(u.mem_read(0,1<<20))
        self.out={n:u.reg_read(reg) for n,reg in REG.items()}
        self.outflags=u.reg_read(x.UC_X86_REG_EFLAGS)&0x0fd7
        return dict(entry=self.regs['ip'],trace=trace,instructions=sorted(seen),steps=steps,
                    memory_sha256=sha(self.actual))

def table_case(first=False,clear_later=False,direction=False,unlisted=False):
    f=Fixture(0x13dc,int(first)+int(clear_later)*2+int(direction)*4+int(unlisted)*8)
    putword(f.mem,DS,0x2006,0xaaaa);putword(f.mem,DS,0x2008,0xbbbb)
    f.mem[address(DS,0x2013)]=0xff if first else 0
    targets=[word(f.mem,DS,0x2014+3*n) for n in range(4)]
    if unlisted:
        targets[0]=0x9000;putword(f.mem,DS,0x2014,targets[0])
    if direction:
        f.flags|=0x400
        # DF=1 reads a different word overlapping the first enable byte.
        f.mem[address(DS,0x2013)]=0x14
        f.mem[address(DS,0x2012)]=0x10
        for p in (0x2010,0x200d,0x200a):f.mem[address(DS,p)]=0
    expected=bytearray(f.mem)
    for p in (0x2006,0x2008):putword(expected,DS,p,0)
    for p in (0x2016,0x2019,0x201c):expected[address(DS,p)]=0xff
    selected=[0] if direction else ([0,1] if clear_later else ([0,1,2,3] if first else [1,2,3]))
    calls=[]
    def callback(u,trace):
        target=u.reg_read(REG['ip']);calls.append(target)
        sp=u.reg_read(REG['sp'])
        if int.from_bytes(u.mem_read(address(SS,sp),2),'little')!=0x1409:raise AssertionError('Display callback return frame differs')
        idx=selected[len(calls)-1]
        si=(0x2013-3*idx-3 if direction else 0x2013+3*(idx+1))&0xffff
        # SI/CX save words remain after the original POPs.
        putword(expected,SS,0x7ffe,si);putword(expected,SS,0x7ffc,4-idx)
        putword(expected,SS,0x7ffa,0x1409)
        u.reg_write(REG['si'],0xdead);u.reg_write(REG['cx'],0xbeef)
        if clear_later and len(calls)==1:
            for p in (0x2019,0x201c):
                u.mem_write(address(DS,p),b'\0');expected[address(DS,p)]=0
        trace.append(dict(callback=target,return_ip=0x1409))
    result=f.run(((0x13dc,0x1410),(0x14fa,0x1523)),{p:callback for p in set(targets+[0x1410])})
    wanted=[0x1410] if direction else [targets[n] for n in selected]
    if calls!=wanted:raise AssertionError(f'Display dispatch sequence {calls}/{wanted}')
    if f.actual!=expected:raise AssertionError('Display caller memory/stack residue differs')
    if f.out['si']!=(0x2007 if direction else 0x201f) or f.out['cx']!=0 or f.out['sp']!=0x8002:
        raise AssertionError('Display caller did not preserve loop state around callees')
    if bool(f.outflags&0x400)!=direction:raise AssertionError('Display caller changed DF')
    result.update(kind='display',first=first,clear_later=clear_later,direction=direction,unlisted=unlisted)
    return result

def input_poll_case(target,tag):
    f=Fixture(0x42a1,tag);f.regs['dx']=0xabff
    putword(f.mem,DS,0x25a0,target);expected=bytearray(f.mem)
    putword(expected,SS,0x7ffe,0xabff);putword(expected,SS,0x7ffc,0x42a7)
    def callback(u,trace):
        if u.reg_read(REG['ax'])!=target:raise AssertionError('Input callback AX differs')
        trace.append(dict(callback=target,return_ip=0x42a7))
        u.reg_write(REG['dx'],0x1234);u.reg_write(REG['bx'],0xbeef);u.reg_write(REG['cx'],0xdead)
    result=f.run(((0x42a1,0x42b0),(0x4333,0x4334)),{target:callback})
    if f.actual!=expected or f.out['dx']!=0xabff or f.out['sp']!=0x8002:
        raise AssertionError('Input callback save/return contract differs')
    result.update(kind='input_poll',target=target);return result

def code_input_case(keys,tag):
    f=Fixture(0x4c7e,tag);values=iter(keys);calls=[];sites=[]
    f.mem[address(DS,0x4df2):address(DS,0x4df2)+11]=b'.'*11
    def observe(u,off,trace):
        if off in (0x4cc9,0x4d18):
            if u.reg_read(REG['bp'])!=0x503b:raise AssertionError('Input BP callback was not restored')
            sites.append(off)
    def stub(u,trace):
        pc=u.reg_read(REG['ip']);trace.append(dict(callback=pc))
        if pc==0x4d1a:
            try:key=next(values)
            except StopIteration:raise AssertionError('Input fixture exhausted keys')
            u.reg_write(REG['ax'],key)
        if pc==0x503b:calls.append(pc)
        # Every surrounding original save/restore must survive these clobbers.
        for n in ('bp','si','cx','dx'):u.reg_write(REG[n],0xd00d)
    result=f.run(((0x4c7e,0x4d1a),),{p:stub for p in (0x1550,0x503b,0x4c20,0x4d1a)},observe)
    if sites!=[0x4cc9]*len(keys)+[0x4d18] or len(calls)!=len(keys)+1:
        raise AssertionError('Input callback call/tail sequence differs')
    if f.out['sp']!=0x8002 or f.out['bp']!=0xd00d:
        raise AssertionError('Final JMP callback did not consume the original caller return frame')
    result.update(kind='code_input',keys=keys,indirect_sites=sites);return result

def object_case(target,erase,tag,visible=True):
    f=Fixture(0x706f,tag);f.regs['di']=0x88
    putword(f.mem,DS,0,0x10);putword(f.mem,DS,0x1f76,0x2000)
    putword(f.mem,DS,0x1fe6,0x3000);putword(f.mem,DS,0x1fe8,0x4000)
    for off,val in ((0,25),(2,2),(4,0),(6,0),(0xa,0x100),(0xc,0x200),(0x10,16),(0x12,0x80),(0x14,target)):
        putword(f.mem,DS,0x88+off,val)
    for off,val in ((0x20,erase),(0x27,1),(0x28,1),(0x29,0),(0x2a,0xff)):
        f.mem[address(DS,0x88+off)]=val
    f.mem[address(DS,0xea8+3)]=int(visible)
    callbacks=[];seen_sites=[]
    def observe(u,off,trace):
        if off==0x715b:
            if u.reg_read(REG['ax'])!=target or u.reg_read(REG['dx'])!=1:
                raise AssertionError('Saved object callback or pixel alignment changed')
            seen_sites.append(off)
    def callback(u,trace):
        pc=u.reg_read(REG['ip']);callbacks.append(pc);trace.append(dict(callback=pc))
        if pc==0x6f7b:
            for n in ('ax','bx','cx','dx','si','di','bp'):u.reg_write(REG[n],0xeeee)
        else:u.reg_write(REG['di'],0xbbbb)
    result=f.run(((0x706f,0x715f),),{target:callback,0x6f7b:callback},observe)
    expected=[] if not visible else ([0x6f7b,target] if erase else [target])
    if callbacks!=expected or f.out['di']!=0x88 or f.out['sp']!=0x8002:
        raise AssertionError('Object caller callback/save contract differs')
    if seen_sites!=([0x715b] if visible else []):raise AssertionError('Unexpected object dispatch site')
    result.update(kind='object',target=target,erase=erase,visible=visible);return result

def check():
    cases=[table_case(),table_case(first=True),table_case(first=True,clear_later=True),
           table_case(direction=True),table_case(first=True,unlisted=True)]
    cases += [input_poll_case(p,10+n) for n,p in enumerate((0x4252,0x4334,0x4359,0x9000))]
    cases += [code_input_case([0xff,ord('A'),ord('B'),0x7f,0x0d],20),
              code_input_case([0xff]*21+[0x0d],21)]
    for n,p in enumerate((0x6170,0x64d9,0x65d8,0x66d7,0x6817,0x6957,0x6a97,0x6bdb,0x6cfc,0x9000)):
        cases += [object_case(p,erase,30+2*n+int(bool(erase))) for erase in (0,0x10)]
    cases.append(object_case(0x6170,0,99,visible=False))
    sites={pc for r in cases for pc in r['instructions']}
    result=dict(case_count=len(cases),cases=cases,original_instruction_sites=sorted(sites),
                scope='Original callback callers only; callees are explicit fixtures; not C coverage or a target-domain completeness proof')
    write_json(BUILD/'dispatch-tests.json',result)
    print(f'PASS dispatch: {len(cases)} bounded caller cases, {len(sites)} original instruction sites; callee semantics and alias closure remain open')
    return result

if __name__=='__main__':check()
