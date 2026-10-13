"""Original raw file open/read/close routine versus portable C."""
import ctypes
import random
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x
from dat_io_c import Regs,Result,MEM,READ
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={r['symbol_name']:r for r in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['ReadRawResourceFile'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
FATAL=SYMS['DatFileErrorTransfer']['address']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY) if i.mnemonic!='nop'}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}
OPEN=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,*([ctypes.c_uint16]*3),ctypes.POINTER(Result))
class Services(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('open',OPEN),('read',READ),('close',OPEN)]

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'resource_raw-m{mutation}.dll',mutation,'resource_raw')))
    lib.lmn_read_raw_resource_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Services)]
    lib.lmn_read_raw_resource_adapter.restype=None;return lib

def prepare(case):
    rng=random.Random(0x1916+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=0x5000,dx=0x100,es=0x4000,ax=case.get('offset',0x200),
                cx=case.get('count',16),ss=0x7000,sp=case.get('sp',0x8000))
    if case.get('read_save_alias'):regs.update(es=regs['ss'],ax=(regs['sp']-4)&65535,cx=4)
    if case.get('filename_save_alias'):regs.update(ss=regs['ds'],sp=SYMS['LastResourceFilenameOffset']['address']+2)
    flags=2|((case['seed']*0x95)&0xed5)
    mem[oracle.at(regs['ds'],regs['dx']):oracle.at(regs['ds'],regs['dx'])+13]=b'TESTFILE.DAT\0'
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags

def provider(case,mem):
    trace=[]
    def open_file(segment,offset,flags):
        failed=case.get('error_stage',0)==1;value=5 if failed else case.get('handle',0x1234)
        trace.append(dict(function=0x3d,segment=segment,offset=offset,flags=flags&0xfd7))
        return value,(flags&~0x8d5)|0x894|(1 if failed else 0)
    def read(handle,segment,offset,count,flags):
        failed=case.get('error_stage',0)==2;returned=min(count,case.get('returned',count))
        if not failed:
            for n in range(returned):mem[oracle.at(segment,offset+n)]=(0x51+n*17)&255
        trace.append(dict(function=0x3f,handle=handle,segment=segment,offset=offset,count=count,flags=flags&0xfd7))
        return 5 if failed else returned,(flags&~0x8d5)|0x894|(1 if failed else 0)
    def close(handle,value,flags):
        failed=case.get('error_stage',0)==3
        trace.append(dict(function=0x3e,handle=handle,value=value,flags=flags&0xfd7))
        return 5 if failed else value,(flags&~0x8d5)|0x894|(1 if failed else 0)
    return open_file,read,close,trace

def compare(lib,case):
    mem,regs,flags=prepare(case);c_mem=bytearray(mem);c_r=Regs(**regs,flags=flags)
    co,cr,cc,ctrace=provider(case,c_mem);errors=[]
    def call(fn,out,*args):
        try:out.contents.value,out.contents.flags=fn(*args)
        except Exception as e:errors.append(e)
    @OPEN
    def opened(ctx,memory,seg,offset,inflags,out):call(co,out,seg,offset,inflags)
    @READ
    def read(ctx,memory,handle,seg,offset,count,inflags,out):call(cr,out,handle,seg,offset,count,inflags)
    @OPEN
    def close(ctx,memory,handle,value,inflags,out):call(cc,out,handle,value,inflags)
    services=Services(None,opened,read,close)
    lib.lmn_read_raw_resource_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(c_r),ctypes.byref(services))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;done=False
    uo,ur,uc,trace=provider(case,mem)
    def interrupt(cpu,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        mem[:]=cpu.mem_read(0,1<<20);ax=cpu.reg_read(oracle.REG['ax']);function=ax>>8
        inflags=cpu.reg_read(x.UC_X86_REG_EFLAGS)
        if function==0x3d:
            if ax!=0x3d00:raise AssertionError('Open is not read-only')
            value,outflags=uo(cpu.reg_read(oracle.REG['ds']),cpu.reg_read(oracle.REG['dx']),inflags)
        elif function==0x3f:value,outflags=ur(cpu.reg_read(oracle.REG['bx']),cpu.reg_read(oracle.REG['ds']),cpu.reg_read(oracle.REG['dx']),cpu.reg_read(oracle.REG['cx']),inflags)
        elif function==0x3e:value,outflags=uc(cpu.reg_read(oracle.REG['bx']),ax,inflags)
        else:raise AssertionError('Wrong DOS service')
        cpu.mem_write(0,bytes(mem));cpu.reg_write(oracle.REG['ax'],value);cpu.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    def code(cpu,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (0xff00,FATAL):done=True;cpu.emu_stop();return
        if cpu.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Escaped raw reader at {off:x}')
        seen.add(off);previous=off
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt);u.emu_start(oracle.at(regs['cs'],ENTRY),0,count=1000)
    if not done:raise AssertionError('Raw reader exceeded budget')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(c_r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(c_r,n):04x}/original={u.reg_read(reg):04x}')
    if (u.reg_read(x.UC_X86_REG_EFLAGS)^c_r.flags)&0xfd7:raise AssertionError('Defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at {p:05x}')
    if trace!=ctrace:raise AssertionError(f'{case["name"]}: service trace differs {trace}/{ctrace}')
    return seen,edges

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for count in (0,1,2,15,256,65535):
        for error in (0,1,2,3):add(f'count-{count}-error-{error}',count=count,error_stage=error)
    for offset in (0,1,0xfff0,65535):add(f'offset-{offset}',offset=offset)
    for sp in (0,1,65535):
        for error in (0,1,2,3):add(f'stack-{sp}-error-{error}',sp=sp,error_stage=error)
    add('short-read',returned=3)
    add('empty-read',returned=0)
    add('read-overwrites-saved-segments',read_save_alias=True)
    add('filename-store-overwrites-saved-ds',filename_save_alias=True)
    add('zero-handle',handle=0)
    add('ffff-handle',handle=65535)
    return out

def main():
    report=BUILD/'resource-raw-differential.json';report.unlink(missing_ok=True);baseline=cases();lib=library();seen=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);seen|=a;edges|=b
    if seen!=set(INS) or edges!=EDGES:raise AssertionError(f'Missing sites/edges {set(INS)-seen}/{EDGES-edges}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if not hit:raise AssertionError(f'Raw mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/resource_raw.c','c/resource_raw.h','c/dat_io.h','c/regs.h','c/lemmings_sym.h','tests/resource_raw.py',
           'tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,
        cases=baseline,mutations_detected=mutations,executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),
        translated_code_bytes=sum(i.size for i in INS.values()),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Declared preserving DOS open/read/close; original1916..1948 only;1949 fatal exit; full mapped memory; live save-slot aliases'))
    print(f'PASS raw resource C: {len(baseline)} cases, {len(seen)} sites, {len(edges)} branch edges; 3 compiled mutations detected')
if __name__=='__main__':main()
