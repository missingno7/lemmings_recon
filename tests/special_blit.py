"""Original special-resource VGA strips versus native C and a documented device fixture."""
import ctypes
import random
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR,UC_HOOK_INSN,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
from dat_io_c import Regs,MEM
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated
import resource_rle

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROOTS=[SYMS[f'BlitSpecialResourceStrip{n}'] for n in range(4)]
END=SYMS['InitializeCodeChecksum']['address']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ROOTS[0]['address']:END],ROOTS[0]['address']) if i.mnemonic!='nop'}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}
READ=ctypes.CFUNCTYPE(ctypes.c_uint8,ctypes.c_void_p,MEM,ctypes.c_uint32,ctypes.c_uint16)
WRITE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.c_uint32,ctypes.c_uint8,ctypes.c_uint16)
OUT=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint16)
class Bus(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('read',READ),('write',WRITE),('out',OUT)]

class Vga:
    """Unchained A000 64KiB aperture; mode0 reads/writes, per FreeVGA vgamem.htm.
    Planes are device-owned memory. The CPU aperture cache is not a display buffer.
    """
    def __init__(self,seed,read_map):
        rng=random.Random(seed);self.planes=[bytearray(rng.randbytes(65536)) for _ in range(4)]
        self.latches=[rng.randrange(256) for _ in range(4)]
        self.seq=[rng.randrange(256) for _ in range(5)];self.gc=[rng.randrange(256) for _ in range(9)]
        # The caller's established aperture: no chain4/odd-even, A000 64KiB.
        self.seq[4]=0x06;self.gc[6]=0x05
        self.gc[4]=read_map;self.si=0;self.gi=0;self.trace=[];self.outputs=0
    def out(self,port,value,flags):
        mask=0xfc7 if 1<=self.outputs<=5 else 0xfd7
        self.trace.append(('out',port,value,flags&mask));self.outputs+=1
        index=value&255;data=value>>8
        if port==0x3c4:self.si=index;self.seq[index]=data
        elif port==0x3ce:self.gi=index;self.gc[index]=data
        else:raise AssertionError('Unexpected word port')
    def read(self,mem,p,flags):
        if not 0xa0000<=p<0xb0000:return mem[p]
        offset=p-0xa0000
        if self.gc[5]&0xb:raise AssertionError('Fixture expects read/write mode0')
        self.latches=[plane[offset] for plane in self.planes]
        value=self.latches[self.gc[4]&3];mem[p]=value
        self.trace.append(('read',offset,value,flags&0xfc7));return value
    def write(self,mem,p,value,flags):
        if 0xa0000<=p<0xb0000:
            if self.gc[5]&3 or self.gc[3]!=0 or self.gc[8]!=255:raise AssertionError('Unsupported fixture write mode')
            offset=p-0xa0000
            for n,plane in enumerate(self.planes):
                if self.seq[2]&(1<<n):
                    plane[offset]=(255 if self.gc[0]&(1<<n) else 0) if self.gc[1]&(1<<n) else value
            self.trace.append(('write',offset,value,flags&0xfc7))
        mem[p]=value
    def state(self):return self.planes,self.latches,self.seq,self.gc,self.si,self.gi

def fixture_vectors():
    mem=bytearray(1<<20);v=Vga(1,2);offset=0x123
    for n,p in enumerate(v.planes):p[offset]=0x11*(n+1)
    v.gc[5]=0;v.gc[3]=0;v.gc[8]=255
    if v.read(mem,0xa0000+offset,0)!=0x33 or v.latches!=[0x11,0x22,0x33,0x44]:raise AssertionError('Read-map/latches contract')
    v.out(0x3c4,0x0f02,0);v.out(0x3ce,0x0300,0);v.out(0x3ce,0x0e01,0);v.write(mem,0xa0000+offset,0x5a,0)
    if [p[offset] for p in v.planes]!=[0x5a,255,0,0]:raise AssertionError('Set/reset contract')
    v.out(0x3ce,0x0001,0);v.out(0x3c4,0x0202,0);v.write(mem,0xa0000+offset,0xa5,0)
    if [p[offset] for p in v.planes]!=[0x5a,0xa5,0,0]:raise AssertionError('Map-mask contract')

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'special_blit-m{mutation}.dll',mutation,'special_blit')))
    lib.lmn_blit_special_strip_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.c_uint16,ctypes.POINTER(Bus)]
    lib.lmn_blit_special_strip_adapter.restype=None;return lib
def unpack_rle(stream):
    out=bytearray();p=0
    while True:
        control=stream[p];p+=1
        if control==128:break
        if control>128:out+=bytes([stream[p]])*((1-control)&255);p+=1
        else:out+=stream[p:p+control+1];p+=control+1
    if len(out)!=14400 or p!=len(stream):raise AssertionError('Wrong real strip extent')
    return out
def prepare(case):
    rng=random.Random(0x8238+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    data=load+0x9a9
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ROOTS[case['strip']]['address'],ds=data,ss=0x7000,sp=case.get('sp',0x8000))
    if case.get('pointer_save_alias'):regs.update(ds=regs['ss'],sp=0x1ff2)
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    heap=0x5000;oracle.put16(mem,regs['ds'],SYMS['LevelGraphicsSegment']['address'],heap)
    source=case.get('decoded',rng.randbytes(14400));mem[(heap<<4)+0x8000:(heap<<4)+0xb840]=source
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags
def compare(lib,case):
    mem,regs,flags=prepare(case);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    cv=Vga(case['seed']+0x8238,case.get('read_map',0));uv=Vga(case['seed']+0x8238,case.get('read_map',0));errors=[]
    expected_planes=None
    if not case.get('df') and not case.get('pointer_save_alias'):
        source=mem[0x58000:0x5b840];expected_planes=[bytearray(p) for p in uv.planes]
        start=0x4a68+case['strip']*40*208
        for row in range(40):
            for column in range(120):
                index=row*120+column;target=(start+row*208+column)&65535
                colors=[source[index+n*4800] for n in range(3)]
                for n,value in enumerate(colors+[colors[0]|colors[1]|colors[2]]):expected_planes[n][target]=value
    @READ
    def read(ctx,memory,p,inflags):
        try:return cv.read(c_mem,p,inflags)
        except Exception as e:errors.append(e);return 0
    @WRITE
    def write(ctx,memory,p,value,inflags):
        try:cv.write(c_mem,p,value,inflags)
        except Exception as e:errors.append(e)
    @OUT
    def out(ctx,port,value,inflags):
        try:cv.out(port,value,inflags)
        except Exception as e:errors.append(e)
    bus=Bus(None,read,write,out)
    lib.lmn_blit_special_strip_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),case['strip'],ctypes.byref(bus))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;done=False
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off==0xff00:done=True;uc.emu_stop();return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Blitter escaped at {off:x}')
        seen.add(off);previous=off
    def intr(uc,num,_):raise AssertionError(f'Unexpected interrupt {num}')
    def output(uc,port,size,value,_):
        if size!=2:raise AssertionError('Expected word port output')
        uv.out(port,value,uc.reg_read(x.UC_X86_REG_EFLAGS))
    def memory_read(uc,access,p,size,value,_):
        for i in range(size):
            byte=uv.read(mem,p+i,uc.reg_read(x.UC_X86_REG_EFLAGS));uc.mem_write(p+i,bytes([byte]))
    def memory_write(uc,access,p,size,value,_):
        for i in range(size):uv.write(mem,p+i,(value>>(8*i))&255,uc.reg_read(x.UC_X86_REG_EFLAGS))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.hook_add(UC_HOOK_INSN,output,None,1,0,x.UC_X86_INS_OUT)
    u.hook_add(UC_HOOK_MEM_READ,memory_read,None,0xa0000,0xaffff);u.hook_add(UC_HOOK_MEM_WRITE,memory_write,None,0xa0000,0xaffff)
    u.emu_start(oracle.at(regs['cs'],regs['ip']),0,count=500000)
    if not done:raise AssertionError('Blitter exceeded budget')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(r,n):04x}/original={u.reg_read(reg):04x}')
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0xfd7:raise AssertionError('Defined exit flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: RAM/aperture cache differs at {p:05x}')
    if cv.state()!=uv.state():raise AssertionError(f'{case["name"]}: VGA device state differs')
    if expected_planes is not None and uv.planes!=expected_planes:
        raise AssertionError(f'{case["name"]}: original planes differ from independent strip geometry/content')
    if cv.trace!=uv.trace:
        n=next((n for n,(a,b) in enumerate(zip(cv.trace,uv.trace)) if a!=b),min(len(cv.trace),len(uv.trace)))
        raise AssertionError(f'{case["name"]}: VGA/IF/DF trace differs at event {n}')
    return seen,edges
def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for strip in range(4):
        for df in (False,True):add(f'strip-{strip}-df-{df}',strip=strip,df=df,read_map=strip)
    for sp in (0x10,0x12,65535):add(f'stack-{sp}',strip=0,sp=sp)
    add('level-pointer-alias-saved-ds',strip=0,pointer_save_alias=True)
    for case in resource_rle.cases():
        if 'asset' in case:
            strip=int(case['name'].split('-')[-1]);add(case['name'],strip=strip,decoded=bytes(unpack_rle(case['stream'])),asset=case['asset'],stream_start=case['stream_start'],stream_end=case['stream_end'])
    return out
def main():
    report=BUILD/'special-blit-differential.json';report.unlink(missing_ok=True);fixture_vectors();baseline=cases();lib=library();seen=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);seen|=a;edges|=b
    if seen!=set(INS) or edges!=EDGES:raise AssertionError(f'Missing sites/edges {set(INS)-seen}/{EDGES-edges}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if not hit:raise AssertionError(f'Blit mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/special_blit.c','c/special_blit.h','c/regs.h','c/lemmings_sym.h','tests/special_blit.py','tests/resource_rle.py',
        'tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json')+tuple(f'assets/vgaspec{n}.dat' for n in range(4))
    public=[{k:v for k,v in c.items() if k!='decoded'}|({'decoded_sha256':sha(c['decoded'])} if 'decoded' in c else {}) for c in baseline]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,cases=public,
        mutations_detected=mutations,executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),
        translated_code_bytes=sum(i.size for i in INS.values()),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        device_contract='FreeVGA unchained planar64KiB A000 aperture; read mode0/write mode0; map/set-reset/bitmask/latches; no IRQ scheduling',
        domain='RAM source/SS; intact instructions/active returns; both DF values; port/MMIO order and IF/DF trace; all defined exit flags'))
    print(f'PASS special VGA strips: {len(baseline)} cases, {len(seen)} sites, {len(edges)} branch edges; 3 compiled mutations detected')
if __name__=='__main__':main()
