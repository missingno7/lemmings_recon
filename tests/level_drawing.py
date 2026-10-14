"""Native clear/layout composition versus the original near/far CALL frames."""
import ctypes
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INSN,UC_HOOK_INTR
from unicorn import x86_const as x
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated
from dat_io_c import Regs,MEM
import dat_io as oracle
from special_blit import Vga,Bus,READ,WRITE,OUT,fixture_vectors

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={};LOCAL=set()
for name in ('InitializeLevelDrawing','ClearLevelDrawingTail','ClearVgaBytes','SetDrawingLayout'):
    s=SYMS[name];part={i.address:i for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address'])};INS.update(part)
    if name in ('InitializeLevelDrawing','ClearLevelDrawingTail'):LOCAL.update(part)
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
def field(name):return SYMS[name]['address']

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for tail in (False,True):
        for df in (False,True):
            for value in (0,0x7fff,0xffff):add(f'tail-{tail}-df-{df}-segment-{value:04x}',tail=tail,df=df,value=value)
        for sp in (0,1,65535):add(f'tail-{tail}-sp-{sp:04x}',tail=tail,sp=sp)
        add(f'tail-{tail}-SS-physical-wrap',tail=tail,ss=65535,sp=0x8000)
    add('near-return-mirror-alias',sp=10)
    add('far-return-layout-width-pitch-alias',same_segments=True,sp=field('DrawingWidthPixels')+4)
    add('far-return-layout-origin-CS-alias',same_segments=True,sp=field('DrawingOrigin')+2)
    add('live-input-segment-at-call-frame',same_segments=True,sp=field('GraphicsResourceInputSegment')+2,value=0xffff)
    add('near-return-aperture-cleared',ss=0xa000,sp=0x5802)
    add('far-return-aperture-zero-set-reset',ss=0xa000,sp=0xe000)
    add('tail-return-aperture-cleared',tail=True,ss=0xa000,sp=0xcf00)
    return out

def prepare(case):
    rng=random.Random(0x368e+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=field('ClearLevelDrawingTail' if case.get('tail') else 'InitializeLevelDrawing'),
        ds=case.get('ds',load+0x9a9),ss=case.get('ss',0x7000),sp=case.get('sp',0x8000))
    if case.get('same_segments'):regs['ss']=regs['ds']
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    oracle.put16(mem,regs['ds'],field('GraphicsResourceInputSegment'),case.get('value',0x5000))
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags

class ClearDevice(Vga):
    def __init__(self,seed):
        super().__init__(seed,seed%4)
        self.seq[2]=15;self.gc[1]=0;self.gc[5]=0;self.gc[3]=0;self.gc[8]=255
        self.layout_done=False
    def read(self,mem,p,flags):
        value=super().read(mem,p,flags)
        if self.layout_done and 0xa0000<=p<0xb0000:self.trace[-1]=('read',p-0xa0000,value,flags&0xf03)
        return value
    def out(self,port,value,flags):
        first=self.outputs==0;super().out(port,value,flags)
        self.trace[-1]=('out',port,value,flags&(0xfd7 if first else 0xfc7))

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'level_drawing-m{mutation}.dll',mutation,'level_drawing')))
    lib.lmn_level_drawing_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.c_uint,ctypes.POINTER(Bus)]
    lib.lmn_level_drawing_adapter.restype=None;return lib

def retf_hook_observation():
    results=[]
    for hooked in (False,True):
        u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20)
        # Construct only an identified RETF and its input frame. The poisoned
        # game entry/startup is never executed in this independent observation.
        u.mem_write(0x10110,IMAGE[0x8821:0x8822]);u.mem_write(0x77ffc,b'\x05\x00\x10\x10')
        u.reg_write(x.UC_X86_REG_CS,0x1010);u.reg_write(x.UC_X86_REG_SS,0x7000);u.reg_write(x.UC_X86_REG_SP,0x7ffc)
        if hooked:u.hook_add(UC_HOOK_MEM_READ,lambda *args:None)
        u.emu_start(0x10110,0,count=1)
        results.append((u.reg_read(x.UC_X86_REG_CS),u.reg_read(x.UC_X86_REG_IP),u.reg_read(x.UC_X86_REG_SP)))
    if results!=[(0x1010,5,0x8000),(0x1010,0x10,0x8000)]:raise AssertionError(f'Pinned Unicorn RETF observation changed: {results}')
    return dict(read_free_return=results[0],read_hook_return=results[1],detail='Read hook retains instruction IP; isolated original RETF opcode, no target rewriting')

def compare(lib,case):
    mem,regs,flags=prepare(case);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    cv=ClearDevice(case['seed']+0x368e);uv=ClearDevice(case['seed']+0x368e);errors=[]
    expected=[bytearray(p) for p in uv.planes]
    start,count=(0xcc40,0x340) if case.get('tail') else (0x4a40,0x8880)
    for i in range(count):
        offset=(start+(-i if flags&0x400 else i))&65535
        for plane in expected:plane[offset]=0
    @READ
    def read(ctx,m,p,f):
        try:return cv.read(c_mem,p,f)
        except Exception as e:errors.append(e);return 0
    @WRITE
    def write(ctx,m,p,value,f):
        try:
            cv.write(c_mem,p,value,f)
            if p==oracle.at(regs['ds'],field('DrawingExtentBytes')):cv.layout_done=True
        except Exception as e:errors.append(e)
    @OUT
    def output(ctx,port,value,f):
        try:cv.out(port,value,f)
        except Exception as e:errors.append(e)
    bus=Bus(None,read,write,output)
    lib.lmn_level_drawing_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),case.get('tail',False),ctypes.byref(bus))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(mem));u.mem_write(1<<20,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;pending=None;done=False;exit_kind='outer';far_pause=False
    def code(uc,pc,size,_):
        nonlocal previous,pending,done,exit_kind,far_pause
        cs=uc.reg_read(oracle.REG['cs']);off=(pc-(cs<<4))&65535
        if pending:
            old=pending;pending=None
            normal=(old==0x4e36 and not case.get('tail') and cs==regs['cs'] and off==field('LevelDrawingAfterClear')) or (
                old==0x8821 and cs==regs['cs'] and off==field('LevelDrawingAfterLayout'))
            if not normal:done=True;exit_kind='clear' if old==0x4e36 else 'layout' if old==0x8821 else 'outer';uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        if cs!=regs['cs'] or off not in INS:raise AssertionError(f'{case["name"]}: escaped at {cs:04x}:{off:04x}')
        seen.add(off);previous=off
        if INS[off].mnemonic in ('ret','retf'):pending=off
        if off==0x8821:far_pause=True;uc.emu_stop()
    def memory_read(uc,access,address,size,value,_):
        for i in range(size):
            p=(address+i)&0xfffff;byte=uv.read(mem,p,uc.reg_read(x.UC_X86_REG_EFLAGS))
            if address+i>=1<<20 or 0xa0000<=p<0xb0000:uc.mem_write(address+i,bytes((byte,)))
    def memory_write(uc,access,address,size,value,_):
        for i in range(size):
            p=(address+i)&0xfffff;byte=(value>>(8*i))&255;uv.write(mem,p,byte,uc.reg_read(x.UC_X86_REG_EFLAGS))
            if p==oracle.at(regs['ds'],field('DrawingExtentBytes')):uv.layout_done=True
            if address+i>=1<<20:uc.mem_write(p,bytes((byte,)))
    def port(uc,port,size,value,_):
        if size!=2:raise AssertionError('Non-word port output')
        uv.out(port,value,uc.reg_read(x.UC_X86_REG_EFLAGS))
    def intr(uc,num,_):raise AssertionError(f'Unexpected INT{num:02x}')
    code_hook=u.hook_add(UC_HOOK_CODE,code);read_hook=u.hook_add(UC_HOOK_MEM_READ,memory_read)
    u.hook_add(UC_HOOK_MEM_WRITE,memory_write)
    u.hook_add(UC_HOOK_INSN,port,None,1,0,x.UC_X86_INS_OUT);u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(oracle.at(regs['cs'],regs['ip']),0,count=150000)
    if far_pause:
        # Unicorn2.1.4 corrupts the RETF instruction pointer with a memory-read
        # hook covering its stack. Refresh the device/A20 read boundary, remove
        # the read hook, and execute the original RETF once. No target is patched.
        u.hook_del(code_hook);u.hook_del(read_hook)
        ss=u.reg_read(oracle.REG['ss']);sp=u.reg_read(oracle.REG['sp']);f=u.reg_read(x.UC_X86_REG_EFLAGS)
        for delta in (0,2):
            linear=(ss<<4)+((sp+delta)&65535)
            for i in range(2):
                p=(linear+i)&0xfffff;value=uv.read(mem,p,f);u.mem_write(linear+i,bytes((value,)))
        u.emu_start((u.reg_read(oracle.REG['cs'])<<4)+0x8821,0,count=1)
        if (u.reg_read(oracle.REG['cs']),u.reg_read(oracle.REG['ip']))!=(regs['cs'],field('LevelDrawingAfterLayout')):
            done=True;exit_kind='layout'
        else:
            u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,memory_read)
            u.ctl_remove_cache(0,2<<20)
            u.emu_start((u.reg_read(oracle.REG['cs'])<<4)+u.reg_read(oracle.REG['ip']),0,count=32)
    if not done:raise AssertionError('Level drawing instruction budget exceeded')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(r,n):04x}/ASM={u.reg_read(reg):04x}; exit={exit_kind} at {u.reg_read(oracle.REG["cs"]):04x}:{u.reg_read(oracle.REG["ip"]):04x}')
    mask=0xfc7 if case.get('tail') or exit_kind=='clear' else 0xf03 if exit_kind=='layout' else 0xfd7
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&mask:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at{p:05x}')
    if cv.state()!=uv.state():raise AssertionError(f'{case["name"]}: VGA state differs')
    if cv.trace!=uv.trace:raise AssertionError(f'{case["name"]}: ordered VGA trace differs')
    if regs['ss']!=0xa000 and uv.planes!=expected:raise AssertionError('Independent clear footprint/untouched planes differ')
    expected_ports=[(0x3c4,0x0f02),(0x3ce,0),(0x3ce,0x0f01),(0x3ce,5),(0x3ce,3),(0x3ce,0xff08)]
    if [(a[1],a[2]) for a in uv.trace if a[0]=='out']!=expected_ports:raise AssertionError('Independent port sequence differs')
    if exit_kind=='outer' and not case.get('tail'):
        for name,value in [('DrawingWidthPixels',1664),('DrawingHeight',164),('DrawingOrigin',0x4a40),('DrawingPitchBytes',208),('DrawingExtentBytes',0x8540)]:
            if oracle.get16(actual,regs['ds'],field(name))!=value:raise AssertionError(f'Independent layout {name} differs')
        expected_segment=(oracle.get16(actual,regs['ds'],field('GraphicsResourceInputSegment'))+1)&65535
        if oracle.get16(actual,regs['ds'],field('GraphicsResourceSegment'))!=expected_segment:raise AssertionError('Live segment publication differs')
        if case['name']=='live-input-segment-at-call-frame' and expected_segment!=regs['cs']+1:raise AssertionError('Live far-CALL CS did not replace input segment')
    expected_exit={'near-return-mirror-alias':(regs['cs'],0xf02),'far-return-layout-width-pitch-alias':(208,1664),
        'far-return-layout-origin-CS-alias':(0x4a40,0x36a5),'near-return-aperture-cleared':(regs['cs'],0),
        'far-return-aperture-zero-set-reset':(0,0),'tail-return-aperture-cleared':(regs['cs'],0)}
    if case['name'] in expected_exit and (r.cs,r.ip)!=expected_exit[case['name']]:raise AssertionError('Constructed changed-return target differs')
    return seen,edges

def main():
    report=BUILD/'level-drawing-differential.json';report.unlink(missing_ok=True);fixture_vectors();retf_observation=retf_hook_observation();baseline=cases();lib=library();seen=set();edges=set()
    for case in baseline:a,b=compare(lib,case);seen|=a;edges|=b
    if seen!=set(INS) or edges!=EDGES:raise AssertionError(f'Missing caller sites/edges {set(INS)-seen}/{EDGES-edges}')
    mutants=[]
    for mutation,name in ((1,'tail-False-df-False-segment-0000'),(2,'tail-True-df-False-segment-0000'),(3,'far-return-layout-width-pitch-alias')):
        try:compare(library(mutation),next(c for c in baseline if c['name']==name))
        except AssertionError:mutants.append(dict(mutation=mutation,case=name))
        else:raise AssertionError(f'Caller mutation{mutation} survived')
    paths=tuple('c/'+n for n in ('level_drawing.c','level_drawing.h','vga_clear.c','vga_clear.h','drawing_layout.c','drawing_layout.h','special_blit.h','regs.h','lemmings_sym.h'))
    paths+=('tests/level_drawing.py','tests/special_blit.py','tests/resource_rle.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','tools/unpack.py','metadata/symbols.json')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,cases=baseline,mutations_detected=mutants,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(LOCAL),branch_edges=sorted(edges),translated_code_bytes=40,
        unicorn_retf_hook_observation=retf_observation,
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},domain='Intact code; quiescent IRQ; mode0 unchained64KiB VGA; live SS mirrors/CALL frames and DS layout/input aliases; original inner changed RET/RETF boundaries'))
    print(f'PASS level drawing: {len(baseline)} cases,{len(LOCAL)} caller sites,{len(seen)} integrated sites,{len(edges)} edges;3 compiled mutations detected')
if __name__=='__main__':main()
