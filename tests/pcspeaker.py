"""Original PC-speaker helpers versus portable C, including live-data alias cases."""
import ctypes
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR,UC_HOOK_INSN
from unicorn import x86_const as x
from common import ROOT,BUILD,sha,write_json,read_json
from resources import sound_images
from unpack import unpack,ASSET,relocated
from cbuild import build

REPORT=BUILD/'pcspeaker-differential.json'
REG_NAMES=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip','flags')
class Regs(ctypes.Structure):_fields_=[(n,ctypes.c_uint16) for n in REG_NAMES]
READ=ctypes.CFUNCTYPE(ctypes.c_uint8,ctypes.c_void_p,ctypes.c_uint16)
WRITE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_uint16,ctypes.c_uint8)
class Ports(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('read',READ),('write',WRITE)]
IMAGE,META=sound_images()['pcspeaker']
MAIN,ORACLE=unpack(ASSET.read_bytes())
LEDGER=read_json(ROOT/'metadata/pcspeaker-symbols.json')
ROUTINES={r['symbol_name'].removeprefix('pcspeaker_'):r for r in LEDGER if r.get('c_implementation')}
SYMBOLS={r['symbol_name'].removeprefix('pcspeaker_'):r['address'] for r in LEDGER}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for r in ROUTINES.values() for i in MD.disasm(IMAGE[r['address']:r['address']+r['size']],r['address'])}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EXPECTED_EDGES={(pc,i.operands[0].imm&0xffff) for pc,i in INS.items() if pc in BRANCHES}
EXPECTED_EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}
REG={n:getattr(x,'UC_X86_REG_'+n.upper()) for n in REG_NAMES if n!='flags'}

def at(seg,off):return ((seg<<4)+(off&0xffff))&0xfffff
def put8(mem,seg,off,value):mem[at(seg,off)]=value&255
def put16(mem,seg,off,value):
    p=at(seg,off);mem[p]=value&255;mem[(p+1)&0xfffff]=(value>>8)&255

def library(mutation=0):
    path=BUILD/f'pcspeaker-m{mutation}.dll'
    lib=ctypes.CDLL(str(build(path,mutation,'pcspeaker')))
    for kind in ('effect','stop'):
        fn=getattr(lib,'lmn_pc_sound_'+kind+'_adapter');fn.argtypes=[ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(Regs)]
        fn.restype=None
    lib.lmn_pc_sound_tick_adapter.argtypes=[ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(Regs),ctypes.POINTER(Ports)]
    lib.lmn_pc_sound_tick_adapter.restype=None
    return lib

def prepare(case):
    rng=random.Random(0x6050+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    cs=load+0x842;ds=case.get('ds',cs)
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(MAIN)]=relocated(MAIN,ORACLE['relocations'],load)
    mem[cs<<4:(cs<<4)+len(IMAGE)]=IMAGE
    r=Regs(**{n:rng.randrange(0x10000) for n in REG_NAMES})
    r.cs=cs;r.ds=ds;r.ss=0x7000;r.sp=case.get('sp',0x8000);r.ip=0
    r.flags=2|(rng.randrange(0x10000)&0xed5)
    kind=case['kind'];r.ip=ROUTINES[{'effect':'LoadEffect','tick':'Tick','stop':'Stop'}[kind]]['address']
    if kind=='effect':r.ax=(r.ax&0xff00)|case['effect']
    if kind=='tick':
        default={'EffectActive':0,'NoiseStep':0x80,'NoisePhase':0xf0,'EffectDuration':2,
                 'EffectReload':0x0302,'ModulationCountdown':1,'PulseCountdown':1,
                 'ModulationPattern':1,'GatePattern':0,'CurrentPeriod':0x1200,
                 'PeriodStep':0x20,'PulseResetPeriod':0x1800,'ModulationDeltaA':0x11,
                 'ModulationDeltaB':0xffc0,'LastPitPeriod':0}
        default.update(case.get('data',{}))
        wide={'EffectReload','CurrentPeriod','PeriodStep','PulseResetPeriod','ModulationDeltaA','ModulationDeltaB','LastPitPeriod'}
        for key,value in default.items():
            (put16 if key in wide else put8)(mem,ds,SYMBOLS[key],value)
    put16(mem,r.ss,r.sp,0xff00)
    return mem,r

def compare(lib,case):
    mem,r=prepare(case);c_mem=bytearray(mem);c_r=Regs.from_buffer_copy(r)
    ports_value=case.get('port',0xa0);c_ports=[];u_ports=[]
    @READ
    def read(context,port):
        c_ports.append(('in',port,1,ports_value));return ports_value
    @WRITE
    def write(context,port,value):c_ports.append(('out',port,1,value))
    bus=Ports(None,read,write)
    buf=(ctypes.c_uint8*(1<<20)).from_buffer(c_mem)
    fn=getattr(lib,'lmn_pc_sound_'+case['kind']+'_adapter')
    if case['kind']=='tick':fn(buf,ctypes.byref(c_r),ctypes.byref(bus))
    else:fn(buf,ctypes.byref(c_r))
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in REG.items():u.reg_write(reg,getattr(r,n))
    u.reg_write(x.UC_X86_REG_EFLAGS,r.flags)
    sites=set();edges=set();previous=None;done=False
    entry=r.ip;end=entry+ROUTINES[{'effect':'LoadEffect','tick':'Tick','stop':'Stop'}[case['kind']]]['size']
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(r.cs<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if pc==at(r.cs,0xff00):done=True;uc.emu_stop();return
        if uc.reg_read(x.UC_X86_REG_CS)!=r.cs or not entry<=off<end:raise AssertionError('Helper escaped identified interval')
        sites.add(off);previous=off
    def intr(uc,num,_):raise AssertionError(f'Unexpected interrupt {num:02X}')
    def io_read(uc,port,size,_):
        if (port,size)!=(0x61,1):raise AssertionError('Unexpected input port')
        u_ports.append(('in',port,size,ports_value));return ports_value
    def io_write(uc,port,size,value,_):
        if port not in (0x43,0x42,0x61) or size!=1:raise AssertionError('Unexpected output port')
        u_ports.append(('out',port,size,value))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.hook_add(UC_HOOK_INSN,io_read,None,1,0,x.UC_X86_INS_IN)
    u.hook_add(UC_HOOK_INSN,io_write,None,1,0,x.UC_X86_INS_OUT)
    u.emu_start(at(r.cs,r.ip),0,count=10000)
    if not done:raise AssertionError('Helper did not return within budget')
    for n,reg in REG.items():
        value=u.reg_read(reg)
        if getattr(c_r,n)!=value:raise AssertionError(f'{case["name"]}: {n} C={getattr(c_r,n):04X} original={value:04X}')
    mask=0xfd7 if case['kind']=='effect' else 0xfc7
    if (c_r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&mask:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if c_mem!=actual:
        pos=next(i for i,(a,b) in enumerate(zip(c_mem,actual)) if a!=b)
        raise AssertionError(f'{case["name"]}: memory differs at {pos:05X}')
    if c_ports!=u_ports:raise AssertionError(f'{case["name"]}: port trace differs {c_ports}/{u_ports}')
    return sites,edges

def cases():
    result=[dict(name=f'effect-{n:02x}',kind='effect',effect=n,seed=n) for n in range(256)]
    result += [dict(name='effect-other-ds',kind='effect',effect=0xff,seed=256,ds=0x5000),
               dict(name='effect-stack-wrap',kind='effect',effect=0xfd,seed=257,sp=0xffff),
               dict(name='stop',kind='stop',seed=258),dict(name='stop-stack-wrap',kind='stop',seed=259,sp=0xffff)]
    settings=[('inactive-pit-write',{}),('inactive-pit-same',{'LastPitPeriod':2}),
              ('duration-expires',{'EffectActive':0xff,'EffectDuration':1}),
              ('duration-wrap',{'EffectActive':1,'EffectDuration':0}),
              ('modulation-a',{'EffectActive':1,'ModulationPattern':1}),
              ('modulation-b',{'EffectActive':1,'ModulationPattern':0}),
              ('modulation-no-step',{'EffectActive':1,'ModulationCountdown':2}),
              ('pulse-no-reset',{'EffectActive':1,'PulseCountdown':2}),
              ('gate-silence',{'EffectActive':1,'GatePattern':1}),
              ('counts-wrap',{'EffectActive':1,'ModulationCountdown':0,'PulseCountdown':0}),
              ('period-wrap',{'EffectActive':1,'CurrentPeriod':0xfff0,'ModulationDeltaA':0x40,'PeriodStep':0xffff})]
    for n,(name,data) in enumerate(settings):
        result.append(dict(name=name,kind='tick',seed=300+n,data=data,port=(n*29)&255))
    for n in range(64):
        rng=random.Random(n+6010)
        data={key:rng.randrange(256) for key in ('EffectActive','NoiseStep','NoisePhase','EffectDuration','ModulationCountdown',
              'PulseCountdown','ModulationPattern','GatePattern')}
        data.update({key:rng.randrange(65536) for key in ('EffectReload','CurrentPeriod','PeriodStep','PulseResetPeriod',
                    'ModulationDeltaA','ModulationDeltaB','LastPitPeriod')})
        result.append(dict(name=f'tick-poison-{n}',kind='tick',seed=400+n,data=data,port=rng.randrange(256)))
    return result

def main():
    REPORT.unlink(missing_ok=True);lib=library();baseline=cases();coverage=set();edges=set()
    for case in baseline:
        seen,branches=compare(lib,case);coverage|=seen;edges|=branches
    if coverage!=set(INS):raise AssertionError(f'Missing helper instructions: {set(INS)-coverage}')
    if edges!=EXPECTED_EDGES:raise AssertionError(f'Missing/extra branch edges: {EXPECTED_EDGES-edges}/{edges-EXPECTED_EDGES}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'Mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/pcspeaker.c','c/pcspeaker.h','c/pcspeaker_sym.h','c/regs.h','tools/cbuild.py',
           'tools/pcspeaker_symtab.py','tools/difftest.py','tests/pcspeaker.py',
           'metadata/pcspeaker-symbols.json','metadata/sound-oracle.json')
    report=dict(image='pcspeaker',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=len(mutations),
                mutations_detected=mutations,cases=baseline,translated_code_bytes=sum(r['size'] for r in ROUTINES.values()),
                routines=[dict(name=r['symbol_name'],start=r['address'],end=r['address']+r['size'],
                           instruction_addresses=sorted(pc for pc in coverage if r['address']<=pc<r['address']+r['size'])) for r in ROUTINES.values()],
                executed_instruction_addresses=sorted(coverage),branch_edges=sorted(edges),
                input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
                domain='Near helpers; quiescent interrupts; arbitrary signed AL/data/defined flags within mapped 1MiB; byte-port service contracts',
                flags_note='AF excluded only for tick final OR and stop final XOR; effect compares all modeled arithmetic flags')
    write_json(REPORT,report)
    print(f'PASS PC-speaker C: {len(baseline)} cases, {len(coverage)}/{len(INS)} instruction sites, {len(edges)} branch edges, {len(mutations)} compiled mutations detected')

if __name__=='__main__':main()
