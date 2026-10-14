"""Original prologue state feeding the connected native 882D drawing prefix."""
import ctypes
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INTR
from unicorn import x86_const as x
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated
from cbuild import build
from dat_io_c import Regs,MEM
from special_blit import Bus,READ,WRITE,OUT
import dat_io as oracle

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
def field(name):return SYMS[name]['address']
START=field('PreparePlanarDrawingInputs');END=START+SYMS['PreparePlanarDrawingInputs']['size'];ABORT=field('PlanarDrawingAbortReturn')
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
PROLOGUE={i.address:i for i in MD.disasm(IMAGE[0x8822:START],0x8822)}
INS={i.address:i for i in MD.disasm(IMAGE[START:END],START)};LOCAL=set(INS)
for name in ('ClipPlanarDrawingRectangle','MarkDrawingDirtyCells'):
    s=SYMS[name];INS.update({i.address:i for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address']) if i.address!=0x9996})
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,pc+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}
ARITH={'add','sub','and','xor','or','test','cmp','neg','inc','dec','shr','shl','mul'}
UNDEFINED_AF={'and','xor','or','test','shr','shl'}

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for control in (0,4,8,12):
        for left in (16,0xfff8,1660,1672):
            for top in (0,0xfffe,160,170):
                add(f'control-{control}-x-{left:04x}-y-{top:04x}',control=control,left=left,top=top,dirty=(len(out)%2)*255)
    for enabled in (0,1,254,255):add(f'enable-{enabled:02x}',dirty=enabled)
    for height in (0,1,7,8,248,255):add(f'height-{height}',height=height,dirty=255)
    for width in (1,7,8,9,15,16,255,0xffff):add(f'width-{width:04x}',width=width,dirty=0)
    for sp in (0,1,0xffff):add(f'stack-{sp:04x}',sp=sp,dirty=255)
    add('SS-physical-wrap',ss=0xffff,dirty=255)
    add('DS-physical-wrap',ds=0xffff,dirty=255)
    add('negative-unclipped-x-aborts',left=0xffff,control=8,dirty=255,return_ip=ABORT)
    add('clip-two-left-steps',left=0xfff0,width=24,control=4,dirty=0)
    add('clip-fully-left',left=0xfff0,width=8,control=4,dirty=0,return_ip=ABORT)
    add('clip-fully-above',top=0xfff0,height=8,control=8,dirty=0,return_ip=ABORT)
    add('clip-zero-width-check',width=0,height=8,control=12,dirty=0,return_ip=ABORT)
    add('clip-zero-height-check',width=24,height=0,control=12,dirty=0,return_ip=ABORT)
    add('clip-zero-height-negative-y-fast-return',top=0xfffe,height=2,control=8,dirty=0,restored_height=0)
    add('dirty-unaligned-width-and-height',left=17,top=3,width=9,height=7,dirty=255)
    add('source-extent-product-overflow',width=0xffff,height=0x45ff,dirty=0)
    add('pitch-overwrites-height-save',same_segments=True,sp=0x6700,width=64,height=0xaa10,dirty=0,restored_height=8)
    add('extent-overwrites-width-and-left-saves',same_segments=True,sp=0x66fc,width=64,height=16,dirty=0,restored_width=128,restored_left=8)
    add('dirty-map-read-after-live-PUSH-SI',same_segments=True,sp=0x2a,width=8,height=8,dirty=255,outer_ip=0xffff,map_from_source=True)
    add('dirty-near-return-low-byte-alias',base=0x47fd,left=16,top=0,width=8,height=8,dirty=255,sp=0x4800,return_ip=0x8801)
    add('dirty-near-return-high-byte-alias',base=0x47fe,left=16,top=0,width=8,height=8,dirty=255,sp=0x4800,return_ip=0x015e)
    add('dirty-zero-width-live-save-overwrite',left=16,top=0,width=0,height=8,dirty=255,return_ip=0x0101,all_restored=0x0101)
    return out

def prepare(case):
    rng=random.Random(0x882d+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=0x8822,ds=case.get('ds',load+0x9a9),ss=case.get('ss',0x7000),sp=case.get('sp',0x8000),
        ax=case.get('left',16),bx=case.get('top',0),cx=case.get('height',0x4508),dx=case.get('width',24),
        si=0x2000,di=0x4000,bp=case.get('control',0))
    if case.get('same_segments'):regs['ss']=regs['ds']
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case['seed']%2 else 0)
    for name,value in [('DrawingWidthPixels',1664),('DrawingHeight',164),('DrawingDirtyCellMapOffset',case.get('base',0x1000))]:
        oracle.put16(mem,regs['ds'],field(name),value)
    mem[oracle.at(regs['ds'],field('DrawingDirtyCellsEnabledByte'))]=case.get('dirty',0)
    oracle.put16(mem,regs['ss'],regs['sp'],case.get('outer_ip',0xff00))
    oracle.put16(mem,regs['ss'],(regs['sp']+2)&65535,load)
    return mem,regs,flags

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'drawing-inputs-m{mutation}.dll',mutation,'drawing_inputs')))
    lib.lmn_prepare_planar_drawing_inputs_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Bus)]
    lib.lmn_prepare_planar_drawing_inputs_adapter.restype=None;return lib

def compare(lib,case):
    mem,regs,flags=prepare(case);u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(mem)*2)
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);prologue=set();at_span=False
    def prologue_code(uc,pc,size,_):
        nonlocal at_span
        off=pc-(regs['cs']<<4)
        if off==START:at_span=True;uc.emu_stop();return
        if off not in PROLOGUE:raise AssertionError('Original prologue escaped')
        prologue.add(off)
    def read_wrap(uc,access,address,size,value,_):
        for i in range(size):
            if address+i>=1<<20:uc.mem_write(address+i,bytes(uc.mem_read((address+i)&0xfffff,1)))
    def write_wrap(uc,access,address,size,value,_):
        for i in range(size):
            p=address+i
            if p>=1<<20:uc.mem_write(p&0xfffff,bytes(((value>>(8*i))&255,)))
    hook=u.hook_add(UC_HOOK_CODE,prologue_code);u.hook_add(UC_HOOK_MEM_READ,read_wrap);u.hook_add(UC_HOOK_MEM_WRITE,write_wrap)
    u.emu_start((regs['cs']<<4)+0x8822,0,count=20)
    if not at_span or prologue!=set(PROLOGUE):raise AssertionError('Original prologue did not reach native span')
    u.hook_del(hook)
    span_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()};span_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    before=bytes(u.mem_read(0,1<<20));c_mem=bytearray(before);r=Regs(**span_regs,flags=span_flags);c_events=[];u_events=[]
    @READ
    def read(ctx,m,p,f):
        value=c_mem[p];c_events.append(('read',p,value,f));return value
    @WRITE
    def write(ctx,m,p,value,f):c_mem[p]=value;c_events.append(('write',p,value,f))
    bus=Bus(None,read,write,OUT())
    lib.lmn_prepare_planar_drawing_inputs_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),ctypes.byref(bus))
    direct=bytearray(before);plain=Regs(**span_regs,flags=span_flags)
    lib.lmn_prepare_planar_drawing_inputs_adapter((ctypes.c_uint8*(1<<20)).from_buffer(direct),ctypes.byref(plain),None)
    if direct!=c_mem or bytes(plain)!=bytes(r):raise AssertionError('Null bus and callback RAM differ')
    seen=set();edges=set();previous=None;paused=None;done=False;steps=0;defined=0xfc7;u_masks=[]
    def code(uc,pc,size,_):
        nonlocal previous,paused,done,steps,defined
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (END,ABORT):done=True;uc.emu_stop();return
        if off not in INS or uc.reg_read(oracle.REG['cs'])!=regs['cs']:raise AssertionError(f'{case["name"]}: escaped at{off:04x}')
        steps+=1
        if steps>600000:raise AssertionError('Drawing inputs instruction budget exceeded')
        seen.add(off);previous=off
        # Memory events observe flags BEFORE this instruction executes. Their
        # masks are captured by the memory hook using the prior setter below.
        if INS[off].mnemonic=='ret':paused=off;uc.emu_stop()
    flag_mask=0xfc7;current_op=None;instruction_flags=span_flags
    def reads(uc,access,address,size,value,_):
        for i in range(size):u_events.append(('read',(address+i)&0xfffff,bytes(uc.mem_read(address+i,1))[0],instruction_flags));u_masks.append(flag_mask)
    def writes(uc,access,address,size,value,_):
        for i in range(size):u_events.append(('write',(address+i)&0xfffff,(value>>(8*i))&255,instruction_flags));u_masks.append(flag_mask)
    def observed_code(uc,pc,size,data):
        nonlocal flag_mask,current_op,defined,instruction_flags
        if current_op in ARITH:flag_mask=0xf03 if current_op=='mul' else 0xfc7 if current_op in UNDEFINED_AF else 0xfd7
        off=pc-(regs['cs']<<4);current_op=INS[off].mnemonic if off in INS else None;defined=flag_mask
        instruction_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        code(uc,pc,size,data)
    def intr(uc,num,_):raise AssertionError(f'Unexpected INT{num:02x}')
    hook=u.hook_add(UC_HOOK_CODE,observed_code);u.hook_add(UC_HOOK_MEM_READ,reads);u.hook_add(UC_HOOK_MEM_WRITE,writes);u.hook_add(UC_HOOK_INTR,intr)
    pc=(regs['cs']<<4)+START
    while not done:
        paused=None;u.emu_start(pc,0,count=600000-steps)
        if done:break
        if paused is None:raise AssertionError('No bounded drawing-input exit')
        u.hook_del(hook);u.emu_start((regs['cs']<<4)+paused,0,count=1)
        expected=field('PlanarInputsAfterClip') if paused in (0x99e7,0x9a0b,0x9a14) else END
        actual_ip=u.reg_read(oracle.REG['ip'])
        if u.reg_read(oracle.REG['cs'])!=regs['cs'] or actual_ip!=expected:done=True;break
        hook=u.hook_add(UC_HOOK_CODE,observed_code);u.ctl_remove_cache(0,2<<20);pc=(regs['cs']<<4)+actual_ip
    for name,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,name):raise AssertionError(f'{case["name"]}: {name} C={getattr(r,name):04x}/ASM={u.reg_read(reg):04x}')
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&defined:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: RAM differs at{p:05x}')
    if len(c_events)!=len(u_events):raise AssertionError(f'{case["name"]}: bus access count differs {len(c_events)}/{len(u_events)}')
    for n,(a,b,mask) in enumerate(zip(c_events,u_events,u_masks)):
        if a[:3]!=b[:3] or (a[3]^b[3])&mask:raise AssertionError(f'{case["name"]}: ordered RAM event{n} differs {a}/{b},mask{mask:04x}')
    if case.get('return_ip') is not None and r.ip!=case['return_ip']:raise AssertionError('Constructed continuation differs')
    for name,attr in [('restored_height','cx'),('restored_width','dx'),('restored_left','ax')]:
        if name in case and getattr(r,attr)!=case[name]:raise AssertionError('Constructed live prologue restore differs')
    if 'all_restored' in case and any(getattr(r,n)!=case['all_restored'] for n in ('ax','bx','cx','dx','si','di','bp')):raise AssertionError('Dirty full-stack overwrite did not restore all changed words')
    if case.get('map_from_source') and oracle.get16(actual,regs['ds'],field('DrawingDirtyCellMapOffset'))!=regs['si']:raise AssertionError('Dirty map was cached before PUSH SI')
    for start,end in ((0x8822,END),(0x9967,0x9a8f)):
        p=(regs['cs']<<4)+start
        if actual[p:p+end-start]!=IMAGE[start:end]:raise AssertionError('Executing drawing instruction bytes were overwritten')
    return seen,edges,prologue

def observe_mul_write_hook():
    """Two identified original instructions; no C-derived flags or patched bytes."""
    from unicorn import __version__
    load=0x1010;u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20)
    u.mem_write(load<<4,IMAGE)
    for name,value in (('cs',load),('ds',0x6000),('ax',3),('cx',8),('dx',24)):
        u.reg_write(oracle.REG[name],value)
    u.reg_write(x.UC_X86_REG_EFLAGS,2);boundaries=[];writes=[]
    def code(uc,pc,size,_):
        boundaries.append((pc-(load<<4),uc.reg_read(x.UC_X86_REG_EFLAGS)))
    def write(uc,access,address,size,value,_):
        writes.append((address,size,value,uc.reg_read(x.UC_X86_REG_EFLAGS)))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    # Stop before POP CX. MUL CX and MOV DS:66F8,AX are the only executed sites.
    u.emu_start((load<<4)+0x8832,(load<<4)+0x8837)
    final=u.reg_read(x.UC_X86_REG_EFLAGS)
    if [pc for pc,f in boundaries]!=[0x8832,0x8834] or boundaries[1][1]&0x801 or final&0x801:
        raise AssertionError('Original MUL product24 must clear defined CF/OF')
    if len(writes)!=1 or writes[0][:3]!=(0x666f8,2,24) or bytes(u.mem_read(0x666f8,2))!=b'\x18\x00':
        raise AssertionError('Original MUL/MOV observation changed')
    return dict(unicorn_version=__version__,instruction_boundary_flags=boundaries,
        memory_hook=writes,after_store_flags=final,
        transient_defined_flag_disagreement=bool((writes[0][3]^boundaries[1][1])&0x801),
        executed_original_only_sites=[0x8832,0x8834],counts_as_c_case=False)

def main():
    report=BUILD/'drawing-inputs-differential.json';report.unlink(missing_ok=True);baseline=cases();hook_observation=observe_mul_write_hook();lib=library();seen=set();edges=set();prologue=set()
    for case in baseline:a,b,c=compare(lib,case);seen|=a;edges|=b;prologue|=c
    if seen!=set(INS) or edges!=EDGES:raise AssertionError(f'Missing native sites/edges {set(INS)-seen}/{EDGES-edges}')
    mutants=[]
    for mutation,name in ((1,'enable-ff'),(2,'pitch-overwrites-height-save'),(3,'dirty-near-return-low-byte-alias')):
        try:compare(library(mutation),next(c for c in baseline if c['name']==name))
        except AssertionError:mutants.append(dict(mutation=mutation,case=name))
        else:raise AssertionError(f'Preparation mutation{mutation} survived')
    paths=tuple('c/'+n for n in ('drawing_inputs.c','drawing_inputs.h','drawing_clip.c','drawing_clip.h','drawing_dirty.c','drawing_dirty.h','special_blit.h','regs.h','lemmings_sym.h'))
    paths+=('tests/drawing_inputs.py','tests/special_blit.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','tools/unpack.py','metadata/symbols.json')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,cases=baseline,mutations_detected=mutants,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(LOCAL),branch_edges=sorted(edges),original_only_prologue_sites=sorted(prologue),
        translated_code_bytes=49,mul_write_hook_observation=hook_observation,input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='882D..885D native continuation with three live saves from original8822 prologue; near clip/dirty calls native; separate885E dispatch scope,88AB unported RETF or changed childRET; intact executing code; RAM/null/callback buses; quiescentIRQ; permissive20-bit stack model'))
    print(f'PASS drawing inputs: {len(baseline)} cases,{len(LOCAL)} caller sites,{len(seen)} integrated sites,{len(edges)} edges;3 compiled mutants detected;{len(prologue)} prologue sites excluded from C coverage')
if __name__=='__main__':main()
