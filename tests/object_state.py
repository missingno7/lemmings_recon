"""Four original object-setup calls versus directly connected native cores."""
import ctypes
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from resources import section_spans,decode_section
from unpack import ASSET,unpack,relocated
import dat_io as oracle
from dat_io_c import Regs,MEM

IMAGE,ORACLE=unpack(ASSET.read_bytes());SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ENTRY=SYMS['PrepareLevelObjectState']['address'];END=ENTRY+SYMS['PrepareLevelObjectState']['size']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY)};LOCAL=set(INS)
for name in ('CopyLevelObjectGraphicsRecords','WriteSteelInteractionCells','WriteObjectInteractionCells','CollectTypeOneObjectCoordinates'):
    s=SYMS[name];INS.update({i.address:i for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address'])})
RETS={pc for pc,i in INS.items() if i.mnemonic=='ret'}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,pc+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}

def field(name):return SYMS[name]['address']
def at(segment,offset):return ((segment<<4)+(offset&65535))&0xfffff
def put_bytes(mem,segment,offset,data):
    for i,value in enumerate(data):mem[at(segment,offset+i)]=value
def be(mem,segment,offset):return (mem[at(segment,offset)]<<8)|mem[at(segment,offset+1)]
def put_be(mem,segment,offset,value):put_bytes(mem,segment,offset,value.to_bytes(2,'big'))

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for df in (False,True):
        for count in (0,1,2,3,4,16,32):add(f'count-{count}-df-{df}',count=count,df=df)
    add('object-overwrites-steel',overlap=True)
    add('upper-object-only',upper=True)
    add('byte3-steel-presence',byte3=True)
    for sp in (0,1,65535):add(f'stack-{sp:04x}',count=1,sp=sp)
    add('ss-physical-wrap',count=2,ss=65535)
    add('graphics-return-word-changed',alias=True)
    add('steel-return-word-changed',alias=True,alias_stage='steel')
    add('object-return-word-changed',alias=True,alias_stage='object')
    add('coordinates-return-word-changed',alias=True,alias_stage='coordinates')
    for group in range(10):
        asset=f'assets/level{group:03d}.dat';packed=(ROOT/asset).read_bytes()
        for section,(a,b) in enumerate(section_spans(packed)):
            record,_=decode_section(packed[a:b]);add(f'real-level-{group:03d}-{section}',
                level_asset=asset,section=section,record=record)
    return out

def prepare(case):
    rng=random.Random(0x376a+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=load+0x9a9,ss=case.get('ss',load+0x143e),sp=case.get('sp',0x4af4))
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    put_bytes(mem,regs['ds'],field('LoadedLevelRecord'),bytes(2048));assets=[]
    if 'record' in case:
        record=case['record'];asset=f'assets/ground{record[27]}o.dat';assets=[case['level_asset'],asset]
        put_bytes(mem,regs['ds'],field('LoadedLevelRecord'),record)
        put_bytes(mem,regs['ds'],field('GroundResourceBuffer'),(ROOT/asset).read_bytes())
    else:
        ground=bytes((i*29+7)&255 for i in range(1056))
        put_bytes(mem,regs['ds'],field('GroundResourceBuffer'),ground)
        for typ in range(16):
            p=field('GroundResourceBuffer')+28*typ
            oracle.put16(mem,regs['ds'],p+14,0);oracle.put16(mem,regs['ds'],p+16,0)
            put_bytes(mem,regs['ds'],p+18,bytes((2,2,typ&15)))
        indices=(31,) if case.get('upper') else range(case.get('count',1 if case.get('overlap') else 0))
        for index in indices:
            p=field('LevelObjectDefinitions')+8*index
            for offset,value in ((0,20+4*index),(2,12+4*(index%3)),(4,1)):
                put_be(mem,regs['ds'],p+offset,value)
        if case.get('overlap'):
            p=field('GroundResourceBuffer')+28
            put_bytes(mem,regs['ds'],p+18,bytes((3,2,10)))
            # X=5, row=2, width=3, height=2; object zero has the same rectangle.
            put_bytes(mem,regs['ds'],field('LevelSteelDefinitions'),bytes((2,0x82,0x21,0)))
        if case.get('byte3'):put_bytes(mem,regs['ds'],field('LevelSteelDefinitions'),b'\0\0\0\1')
    if case.get('alias') and case.get('alias_stage','graphics')=='graphics':
        # Keep the first copy's restored DI/CX/SI controlled, and change only
        # its near return to the declared outside-code boundary at6000.
        regs.update(ss=regs['ds'],sp=field('LevelObjectGraphicsRecords')+10)
        p=field('LevelObjectDefinitions');put_be(mem,regs['ds'],p,256);put_be(mem,regs['ds'],p+4,0)
        prefix=bytearray(28)
        prefix[2:4]=field('LevelObjectGraphicsRecords').to_bytes(2,'little')
        prefix[4:6]=(1).to_bytes(2,'little');prefix[6:8]=field('GroundResourceBuffer').to_bytes(2,'little')
        prefix[8:10]=(0x6000).to_bytes(2,'little');prefix[18:21]=bytes((1,1,1))
        put_bytes(mem,regs['ds'],field('GroundResourceBuffer'),prefix)
    elif case.get('alias_stage')=='steel':
        regs['sp']=field('InteractionCellMapBase')+2
        put_bytes(mem,regs['ds'],field('LevelSteelDefinitions'),b'\0\0\0\1')
    elif case.get('alias_stage')=='object':
        regs['sp']=0x8000
        p=field('LevelObjectDefinitions');put_be(mem,regs['ds'],p,4);put_be(mem,regs['ds'],p+4,0)
        template=field('GroundResourceBuffer')
        oracle.put16(mem,regs['ds'],template+14,0x7ffe-field('InteractionCellMapBase')-1)
        oracle.put16(mem,regs['ds'],template+16,1)
        put_bytes(mem,regs['ds'],template+18,bytes((1,1,0x5a)))
    elif case.get('alias_stage')=='coordinates':
        regs.update(ss=regs['ds'],sp=field('TypeOneObjectCoordinates')+2)
        p=field('LevelObjectDefinitions')
        for offset,value in ((0,20),(2,12),(4,1)):put_be(mem,regs['ds'],p+offset,value)
    oracle.put16(mem,regs['ss'],regs['sp'],0xfa00)
    return mem,regs,flags,assets

def independent_objects(mem,regs,flags):
    """Independent output expectations for disjoint stack/data fixtures."""
    expected=bytearray(mem);ds=regs['ds'];ss=regs['ss'];step=-1 if flags&0x400 else 1
    for index in range(32):
        p=field('LevelObjectDefinitions')+8*index
        if be(expected,ds,p):
            source=(field('GroundResourceBuffer')+28*be(expected,ds,p+4))&65535
            dest=field('LevelObjectGraphicsRecords')+28*index
            for i in range(28):expected[at(ds,dest+step*i)]=expected[at(ds,source+step*i)]
    touched=set()
    for index in range(32):
        p=field('LevelSteelDefinitions')+4*index;raw=bytes(expected[at(ds,p+i)] for i in range(4))
        if not any(raw):continue
        column=(raw[0]<<1)|(raw[1]>>7);row=raw[1]&127;width=(raw[2]>>4)+1;height=(raw[2]&15)+1
        for y in range(height):
            for xvalue in range(width):
                target=at(ss,field('InteractionCellMapBase')+416*(row+y)+column+xvalue)
                expected[target]=9;touched.add(target)
    for index in range(16):
        p=field('LevelObjectDefinitions')+8*index
        if not be(expected,ds,p):continue
        template=(field('GroundResourceBuffer')+28*be(expected,ds,p+4))&65535
        column=((be(expected,ds,p)>>2)+oracle.get16(expected,ds,template+14))&65535
        row=((be(expected,ds,p+2)>>2)+oracle.get16(expected,ds,template+16)-1)&65535
        width=expected[at(ds,template+18)] or 256;height=expected[at(ds,template+19)] or 256
        value=((index<<4)|expected[at(ds,template+20)])&255
        for y in range(height):
            for xvalue in range(width):
                target=at(ss,field('InteractionCellMapBase')+416*(row+y)+column+xvalue)
                expected[target]=value;touched.add(target)
    coordinates=[]
    for index in range(32):
        p=field('LevelObjectDefinitions')+8*index
        if be(expected,ds,p+4)==1:coordinates.append(((be(expected,ds,p)+24)&65535,(be(expected,ds,p+2)+30)&65535))
    coordinate_base=field('TypeOneObjectCoordinates')
    if not coordinates:
        for offset,value in ((0,256),(2,16),(4,256),(6,16),(8,256),(10,16),(10,256),(14,16)):
            oracle.put16(expected,ds,coordinate_base+offset,value)
    else:
        filled=coordinates.copy()
        if len(filled)==1:filled*=4
        elif len(filled)==2:filled.extend((filled[-1],filled[0]))
        elif len(filled)==3:filled.append(filled[1])
        for index,(xx,yy) in enumerate(filled):
            oracle.put16(expected,ds,coordinate_base+4*index,xx);oracle.put16(expected,ds,coordinate_base+4*index+2,yy)
    return expected,touched,len(coordinates)

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'object-state-m{mutation}.dll',mutation,'object_state')))
    lib.lmn_prepare_level_object_state_adapter.argtypes=[MEM,ctypes.POINTER(Regs)]
    lib.lmn_prepare_level_object_state_adapter.restype=None;return lib

def compare(lib,case):
    mem,regs,flags,assets=prepare(case);expected=None
    if not case.get('alias'):expected,touched,count=independent_objects(mem,regs,flags)
    c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    lib.lmn_prepare_level_object_state_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r))
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<21);u.mem_write(0,bytes(mem)+bytes(mem))
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;continuation=None;done=False;phase=None
    def code(uc,pc,size,_):
        nonlocal previous,continuation,done,phase
        off=pc-(regs['cs']<<4)
        if previous in RETS:
            if off!=continuation:done=True;uc.emu_stop();return
            continuation=None
        if previous in BRANCHES:edges.add((previous,off))
        if off==END:done=True;uc.emu_stop();return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'{case["name"]}: escaped span at{off:04x}')
        if off in LOCAL:continuation=off+3;phase=off
        seen.add(off);previous=off
    def read(uc,access,address,size,value,_):
        for i in range(size):
            p=address+i
            if p>=1<<20:uc.mem_write(p,bytes(uc.mem_read(p&0xfffff,1)))
    def write(uc,access,address,size,value,_):
        for i in range(size):
            p=address+i;other=(p&0xfffff) if p>=1<<20 else p+(1<<20)
            uc.mem_write(other,bytes(((value>>(8*i))&255,)))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.emu_start(at(regs['cs'],ENTRY),0,count=3000000)
    if not done:raise AssertionError('Object-state span exceeded instruction budget')
    for name,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,name):raise AssertionError(f'{case["name"]}: {name} C={getattr(r,name):04x}/original={u.reg_read(reg):04x}')
    mask=0xfd7
    if phase==END-3 and r.bp==0:mask&=~16 # Final AND BP,BP leaves only AF undefined.
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&mask:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: RAM differs at{p:05x}')
    if case.get('alias'):
        targets={'graphics':0x6000,'steel':0x3709,'object':0x375a,'coordinates':44}
        if r.ip!=targets[case.get('alias_stage','graphics')] or r.sp!=regs['sp']:raise AssertionError('Changed-return boundary not exposed')
    else:
        if r.ip!=END or r.sp!=regs['sp'] or r.bp!=count:raise AssertionError('Object-state normal continuation/count differs')
        for target in touched:
            if actual[target]!=expected[target]:raise AssertionError(f'{case["name"]}: expected interaction cell differs at{target:05x}')
        # Every original PUSH is at most eight bytes below the outer SP.
        # Outside those live save words, the whole SS window must match the
        # independent cell footprint, including untouched bytes.
        saves={(((regs['ss']<<4)+((regs['sp']-n)&65535)+i)&0xfffff) for n in (2,4,6,8) for i in (0,1)}
        for offset in range(65536):
            target=at(regs['ss'],offset)
            if target not in saves and actual[target]!=expected[target]:raise AssertionError(f'{case["name"]}: independent SS footprint differs at{target:05x}')
        for base,size in ((field('LevelObjectGraphicsRecords'),896),(field('TypeOneObjectCoordinates'),128)):
            for offset in range(base,base+size):
                if actual[at(regs['ds'],offset)]!=expected[at(regs['ds'],offset)]:raise AssertionError(f'{case["name"]}: expected object output differs atDS:{offset:04x}')
    return seen,edges,assets

def main():
    report=BUILD/'object-state-differential.json';report.unlink(missing_ok=True);baseline=cases();lib=library();seen=set();edges=set();assets=set()
    for case in baseline:
        a,b,c=compare(lib,case);seen|=a;edges|=b;assets.update(c)
    if seen!=set(INS) or edges!=EDGES:raise AssertionError(f'Missing object-state sites/edges {set(INS)-seen}/{EDGES-edges}')
    mutants=[]
    for mutation,name in ((1,'object-overwrites-steel'),(2,'count-0-df-False'),(3,'graphics-return-word-changed')):
        try:compare(library(mutation),next(c for c in baseline if c['name']==name))
        except AssertionError:mutants.append(dict(mutation=mutation,case=name))
        else:raise AssertionError(f'Object-state mutant{mutation} survived')
    paths=tuple('c/'+name for name in ('object_state.c','object_state.h','object_graphics.c','object_graphics.h','steel_cells.c','steel_cells.h','object_cells.c','object_cells.h','object_coordinates.c','object_coordinates.h','regs.h','lemmings_sym.h'))
    paths+=('tests/object_state.py','tests/object_graphics.py','tests/steel_cells.py','tests/object_cells.py','tests/object_coordinates.py','tests/dat_io.py','tests/dat_io_c.py',
        'tools/cbuild.py','tools/difftest.py','tools/unpack.py','tools/resources.py','metadata/symbols.json','metadata/inputs.json')+tuple(sorted(assets))
    public=[{k:v for k,v in c.items() if k!='record'} for c in baseline]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,cases=public,mutations_detected=mutants,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(LOCAL),branch_edges=sorted(edges),translated_code_bytes=12,
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Four native leaf calls at376A..3775; explicit3776 boundary or changed near-return target; intact executing code; quiescent IRQ; live SS stack/cells; all80 realLEVEL/GROUND pairs'))
    print(f'PASS object state C: {len(baseline)} cases,{len(LOCAL)} span sites,{len(seen)} integrated sites,{len(edges)} integrated edges;3 compiled mutants detected')
if __name__=='__main__':main()
