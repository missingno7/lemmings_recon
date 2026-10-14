"""Shared bounded original near-call harness for the minimap composition."""
import ctypes
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INSN,UC_HOOK_INTR
from unicorn import x86_const as x
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated
from dat_io_c import Regs,MEM
from special_blit import Bus,READ,WRITE,OUT
from minimap_vga import MinimapVga,fixture_vectors
from cbuild import build
import dat_io as oracle

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
PART={}
for name in ('AccumulateMinimapSample','AccumulateMinimapRow','UpdateMinimapColumn'):
    s=SYMS[name];PART[name]={i.address:i for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address'])}
def field(name):return SYMS[name]['address']
def signed(value):return value if value<32768 else value-65536
def word_bytes(mem,segment,offset,values):
    for i,value in enumerate(values):mem[oracle.at(segment,(offset+i)&65535)]=value

def library(cluster,mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'{cluster}-m{mutation}.dll',mutation,cluster)))
    fn=getattr(lib,'lmn_accumulate_minimap_row_adapter' if cluster=='minimap_row' else 'lmn_update_minimap_column_adapter')
    fn.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Bus)];fn.restype=None
    return lib,fn

def prepare(case,column):
    rng=random.Random((0x796f if column else 0x7a25)+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=field('UpdateMinimapColumn' if column else 'AccumulateMinimapRow'),ds=case.get('ds',load+0x9a9),
        es=case.get('es',0x5000),ss=case.get('ss',0x7000),sp=case.get('sp',0x8000),
        si=case.get('si',0x1000),bx=field('MinimapColumnBits'),cx=case.get('cx',0x1234))
    if case.get('cs_ss'):regs['ss']=regs['cs']
    if case.get('ds_cs'):regs['ds']=regs['cs']
    if case.get('ds_scratch_alias'):regs['ds']=regs['cs']+0x837
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    if column:
        oracle.put16(mem,regs['ds'],field('MinimapSourceColumnByteOffset'),case.get('column',0))
        word_bytes(mem,regs['cs'],field('MinimapColumnBits'),bytes((i*19+case['seed']*7+0x35)&255 for i in range(20)))
        if case.get('aperture_pop_es'):mem[0x83c1:0x83d5]=b'\xa5'*20
    else:
        samples=case.get('words',[((1<<((j+case['seed'])%17))-1)&65535 for j in range(8)])
        if case.get('counter_alias'):samples=[65535]*260
        for j,value in enumerate(samples):word_bytes(mem,regs['es'],(regs['si']+2*j)&65535,value.to_bytes(2,'big'))
    return mem,regs,flags

def devices(case,regs,column):
    v=MinimapVga(case['seed']+0x796f,case['seed']%4)
    v.seq[2]=15;v.gc[0]=0;v.gc[1]=8 if case.get('aperture_pop_es') else 0;v.gc[3]=0;v.gc[5]=0;v.gc[8]=255
    if case.get('aperture_pop_es'):v.gc[4]=3
    if column:
        new_column=(case.get('column',0)+16)&65535
        if signed(new_column)>=208:new_column=0
        source=(new_column+0x5740)&65535
        for row in range(20):
            for j in range(8):
                bits=65535 if case.get('all_ones') else ((1<<((row+j+case['seed'])%17))-1)&65535
                v.planes[3][(source+row*0x680+2*j)&65535]=bits>>8
                v.planes[3][(source+row*0x680+2*j+1)&65535]=bits&255
    return v

def independent_column(mem,regs,flags,v):
    # Preserve the ordering: the CS clear may change the live DS input; its
    # subsequent publication can itself alias the scratch bytes being sampled.
    after=bytearray(mem)
    for j in range(10):oracle.put16(after,regs['cs'],field('MinimapColumnBits')+(-2*j if flags&0x400 else 2*j),0)
    column=(oracle.get16(after,regs['ds'],field('MinimapSourceColumnByteOffset'))+16)&65535
    if signed(column)>=208:column=0
    oracle.put16(after,regs['ds'],field('MinimapSourceColumnByteOffset'),column)
    start=oracle.at(regs['cs'],field('MinimapColumnBits'));bits=bytearray(after[start:start+20])
    source=(column+0x5740)&65535;dest=(0xd320+(column>>4))&65535
    for row in range(20):
        for j in range(8):
            value=(v.planes[3][(source+row*0x680+2*j)&65535]<<8)|v.planes[3][(source+row*0x680+2*j+1)&65535]
            if value.bit_count()>8:bits[row]|=0x80>>j
    planes=[bytearray(p) for p in v.planes]
    for row in range(19):
        p=(dest+row*13)&65535
        for plane in range(4):planes[plane][p]=bits[row] if plane<3 else 0
    after[start:start+20]=bits
    return column,bits,planes,dest,oracle.get16(after,regs['ds'],field('MinimapSourceColumnByteOffset'))

def compare(native,case,column=False):
    lib,fn=native;mem,regs,flags=prepare(case,column);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    cv=devices(case,regs,column);uv=devices(case,regs,column);expected=None;errors=[]
    if column and not case.get('cs_ss') and regs['ss']!=0xa000 and regs['sp']>=0x100:
        expected=independent_column(mem,regs,flags,uv)
    @READ
    def read(ctx,m,p,f):
        try:return cv.read(c_mem,p,f)
        except Exception as e:errors.append(e);return 0
    @WRITE
    def write(ctx,m,p,value,f):
        try:cv.write(c_mem,p,value,f)
        except Exception as e:errors.append(e)
    @OUT
    def output(ctx,port,value,f):
        try:cv.out(port,value,f)
        except Exception as e:errors.append(e)
    bus=Bus(None,read,write,output)
    iterations=case.get('iterations',1)
    for iteration in range(iterations):
        if iteration:
            r.ip=regs['ip'];r.sp=regs['sp'];oracle.put16(c_mem,r.ss,r.sp,0xff00)
        if column and not case.get('cs_ss') and regs['ss']!=0xa000 and regs['sp']>=0x100:
            current_regs={n:getattr(r,n) for n in oracle.REG_NAMES}
            expected=independent_column(c_mem,current_regs,r.flags,cv)
        fn((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),ctypes.byref(bus))
        if errors:raise errors[0]
        if iterations>1 and r.ip!=0xff00:raise AssertionError('Repeated column call escaped normal outer return')
        if expected is not None:
            col,bits,planes,dest,final_column=expected
            if cv.planes!=planes:raise AssertionError('Independent plane footprint differs during column cycle')
    names=('UpdateMinimapColumn','AccumulateMinimapRow','AccumulateMinimapSample') if column else ('AccumulateMinimapRow','AccumulateMinimapSample')
    ins={pc:i for n in names for pc,i in PART[n].items()};local=set(PART[names[0]])
    branches={pc for pc,i in ins.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(mem)*2)
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;paused=None;instructions=0;samples=0;done=False;exit_kind='outer'
    def code(uc,pc,size,_):
        nonlocal previous,paused,instructions,samples
        off=(pc-(uc.reg_read(oracle.REG['cs'])<<4))&65535
        if previous in branches:edges.add((previous,off))
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in ins:raise AssertionError(f'{case["name"]}: escaped at{off:04x}')
        instructions+=1
        if instructions>500000:raise AssertionError('Minimap instruction budget exceeded')
        seen.add(off);previous=off
        if off==field('AccumulateMinimapSample'):samples+=1
        if ins[off].mnemonic=='ret':paused=off;uc.emu_stop()
    def memory_read(uc,access,address,size,value,_):
        for i in range(size):
            p=(address+i)&0xfffff;value=uv.read(mem,p,uc.reg_read(x.UC_X86_REG_EFLAGS))
            if address+i>=1<<20 or 0xa0000<=p<0xb0000:uc.mem_write(address+i,bytes((value,)))
    def memory_write(uc,access,address,size,value,_):
        for i in range(size):
            p=(address+i)&0xfffff;value_byte=(value>>(8*i))&255;uv.write(mem,p,value_byte,uc.reg_read(x.UC_X86_REG_EFLAGS))
            if address+i>=1<<20:uc.mem_write(p,bytes((value_byte,)))
    def port(uc,port,size,value,_):
        if size!=2:raise AssertionError('Expected VGA word port write')
        uv.out(port,value,uc.reg_read(x.UC_X86_REG_EFLAGS))
    def intr(uc,num,_):raise AssertionError(f'Unexpected INT{num:02x}')
    hook=u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,memory_read);u.hook_add(UC_HOOK_MEM_WRITE,memory_write)
    u.hook_add(UC_HOOK_INSN,port,None,1,0,x.UC_X86_INS_OUT);u.hook_add(UC_HOOK_INTR,intr)
    pc=oracle.at(regs['cs'],regs['ip']);iteration=0
    while not done:
        paused=None;u.emu_start(pc,0,count=500000-instructions)
        if paused is None:raise AssertionError('Minimap did not reach a bounded return')
        u.hook_del(hook);u.emu_start((regs['cs']<<4)+paused,0,count=1)
        target=(u.reg_read(oracle.REG['cs']),u.reg_read(oracle.REG['ip']))
        expected_target=None
        if paused in (0x7a54,0x7a59):expected_target=(regs['cs'],field('MinimapRowAfterSample'))
        elif paused==0x7a38 and column:expected_target=(regs['cs'],field('MinimapColumnAfterRow'))
        if expected_target is None or target!=expected_target:
            done=True;exit_kind='sample' if paused in (0x7a54,0x7a59) else 'row' if paused==0x7a38 and column else 'outer'
            if exit_kind=='outer' and iteration+1<iterations:
                if target!=(regs['cs'],0xff00):raise AssertionError('Original repeated call escaped normal outer return')
                iteration+=1;done=False;previous=None
                u.reg_write(oracle.REG['sp'],regs['sp']);oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
                p=oracle.at(regs['ss'],regs['sp']);u.mem_write(p,b'\x00\xff')
                hook=u.hook_add(UC_HOOK_CODE,code);u.ctl_remove_cache(0,2<<20)
                pc=oracle.at(regs['cs'],regs['ip'])
        else:
            hook=u.hook_add(UC_HOOK_CODE,code);u.ctl_remove_cache(0,2<<20)
            pc=(target[0]<<4)+target[1]
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(r,n):04x}/ASM={u.reg_read(reg):04x}')
    flag_mask=0xfd7 if column and exit_kind=='outer' else 0xfc7
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&flag_mask:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    start=(regs['cs']<<4)+field('UpdateMinimapColumn');end=(regs['cs']<<4)+field('AccumulateMinimapSample')+SYMS['AccumulateMinimapSample']['size']
    if actual[start:end]!=IMAGE[0x796f:0x7a5a] or c_mem[start:end]!=IMAGE[0x796f:0x7a5a]:raise AssertionError('Executing minimap instruction bytes changed outside the tested domain')
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: RAM differs at{p:05x}')
    if cv.state()!=uv.state():raise AssertionError(f'{case["name"]}: planes/latches/device registers differ')
    def normalize(trace):return [event[:-1]+(event[-1]&(0xfd7 if event[0]=='out' else 0xfc7),) for event in trace]
    if normalize(cv.trace)!=normalize(uv.trace):raise AssertionError(f'{case["name"]}: ordered port/MMIO trace differs')
    if 'samples' in case and samples!=case['samples']:raise AssertionError(f'{case["name"]}: original sample calls {samples}, expected{case["samples"]}')
    if 'return_ip' in case and r.ip!=case['return_ip']:raise AssertionError('Constructed changed return differs')
    if 'restored_si' in case and r.si!=case['restored_si']:raise AssertionError('Constructed live saved SI differs')
    if 'restored_cx' in case and r.cx!=case['restored_cx']:raise AssertionError('Constructed live saved CX differs')
    if 'restored_ds' in case and r.ds!=case['restored_ds']:raise AssertionError('Constructed live saved DS differs')
    if expected is not None:
        col,bits,planes,dest,final_column=expected
        if uv.planes!=planes:raise AssertionError('Independent minimap plane footprint/untouched bytes differ')
        if actual[oracle.at(regs['cs'],field('MinimapColumnBits')):oracle.at(regs['cs'],field('MinimapColumnBits'))+20]!=bits:raise AssertionError('Independent twenty sampled row bytes differ')
        if r.di!=(dest+19*13)&65535 or r.si!=(col+0xd940)&65535:raise AssertionError('Independent minimap cursors differ')
        if oracle.get16(actual,regs['ds'],field('MinimapSourceColumnByteOffset'))!=final_column:raise AssertionError('Independent signed column update/live scratch alias differs')
    if column:
        ports=[(e[1],e[2]) for e in uv.trace if e[0]=='out']
        expected_ports=[(0x3c4,0xf02),(0x3ce,0x600),(0x3ce,0x801),(0x3ce,0x805),(0x3ce,3),(0x3ce,0x807),(0x3ce,0x802),(0x3ce,0xff08)]
        if exit_kind=='outer':expected_ports.append((0x3ce,5))
        if ports!=expected_ports*iterations:raise AssertionError('Independent port sequence differs')
        if case.get('saved_ds_mirror') and (r.ds,r.ip)!=(0xf02,0x600):raise AssertionError('Live SS mirror/saved DS/outer RET alias differs')
        if case.get('aperture_pop_es'):
            if r.ip!=0:raise AssertionError('Aperture zero set/reset return should be zero')
            if actual[0x83c1:0x83d5]!=bytes(20):raise AssertionError('Live POP ES did not clear the independently poisoned zero-segment scratch')
    elif not case.get('cs_ss'):
        initial=mem[oracle.at(regs['cs'],regs['bx'])]
        expected_mask=0
        for j,value in enumerate(case.get('words',[((1<<((j+case['seed'])%17))-1)&65535 for j in range(8)])):
            if value.bit_count()>8:expected_mask|=0x80>>j
        if actual[oracle.at(regs['cs'],regs['bx'])]!=initial|expected_mask:raise AssertionError('Independent eight-sample mask differs')
    return seen,edges,samples

def run_suite(cluster,baseline,mutants):
    column=cluster=='minimap_column';report=BUILD/(cluster.replace('_','-')+'-differential.json');report.unlink(missing_ok=True)
    fixture_vectors();native=library(cluster);seen=set();edges=set();counts={}
    for case in baseline:
        a,b,c=compare(native,case,column);seen|=a;edges|=b;counts[case['name']]=c
    names=('UpdateMinimapColumn','AccumulateMinimapRow','AccumulateMinimapSample') if column else ('AccumulateMinimapRow','AccumulateMinimapSample')
    ins={pc:i for n in names for pc,i in PART[n].items()};local=set(PART[names[0]])
    branches={pc for pc,i in ins.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
    expected_edges={(pc,i.operands[0].imm&65535) for pc,i in ins.items() if pc in branches}
    expected_edges|={(pc,pc+i.size) for pc,i in ins.items() if pc in branches and i.mnemonic!='jmp'}
    if seen!=set(ins) or edges!=expected_edges:raise AssertionError(f'Missing sites/edges {set(ins)-seen}/{expected_edges-edges}')
    detected=[]
    for mutation,name in mutants:
        try:compare(library(cluster,mutation),next(c for c in baseline if c['name']==name),column)
        except AssertionError:detected.append(dict(mutation=mutation,case=name))
        else:raise AssertionError(f'{cluster} mutation{mutation} survived')
    paths=('c/minimap_helpers.h','c/minimap_row.c','c/minimap_row.h','c/minimap_sample.c','c/minimap_sample.h','c/special_blit.h','c/regs.h','c/lemmings_sym.h',
        'tests/minimap_connected.py','tests/minimap_vga.py','tests/special_blit.py','tests/dat_io.py','tests/dat_io_c.py','tests/'+cluster+'.py',
        'tools/cbuild.py','tools/difftest.py','tools/unpack.py','metadata/symbols.json')
    if column:paths+=('c/minimap_column.c','c/minimap_column.h')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=len(detected),cases=baseline,mutations_detected=detected,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(local),branch_edges=sorted(edges),sample_calls=counts,
        translated_code_bytes=sum(i.size for i in PART[names[0]].values()),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Intact executing code; quiescent IRQ; original live SS CALL/save/RET frames; CS scratch bytes; 20-bit permissive bus; explicit changed inner near-return targets before target execution; VGA unchained read modes0/1 and write mode0; independent whole-plane footprint'))
    print(f'PASS {cluster}: {len(baseline)} cases,{len(local)} caller sites,{len(seen)} integrated sites,{len(edges)} edges;{len(detected)} compiled mutations detected')
