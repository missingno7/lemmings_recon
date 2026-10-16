"""Bounded pinned-original/native checks for 5BB0 plane copy and OR mask."""
from __future__ import annotations
import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as oracle
import entity_sprite_layout as layout
import entity_sprite_planes as planes
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
ENTRY, RET, END = 0x5BB0, 0x5C05, 0x5C06
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY)}
OWN_SITES = set(OWN_INS)
MAX_STEPS, MAX_EVENTS = 500_000, 160_000
REPORT = BUILD/'sprite-bank-differential.json'
ORIGINAL_REPORT = BUILD/'sprite-bank-original-differential.json'
NAMES = ('value','map_cursor','count','auxiliary_value','record_cursor',
         'object_cursor','candidate_y','code_segment','data_segment',
         'extra_segment','stack_segment','stack_offset','flags')
REGS = ('ax','bx','cx','dx','si','di','bp','cs','ds','es','ss','sp','flags')
MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8,ct.c_void_p,MEM,ct.c_uint32,ct.c_uint16)
WRITE = ct.CFUNCTYPE(None,ct.c_void_p,MEM,ct.c_uint32,ct.c_uint8,ct.c_uint16)
OUT = ct.CFUNCTYPE(None,ct.c_void_p,ct.c_uint16,ct.c_uint16,ct.c_uint16)
class Call(ct.Structure):
    _fields_ = [(n,ct.c_uint16) for n in NAMES]
class Result(ct.Structure):
    _fields_ = [(n,ct.c_uint16) for n in NAMES+('continuation','status')]
class Bus(ct.Structure):
    _fields_ = [('context',ct.c_void_p),('read_byte',READ),
                ('write_byte',WRITE),('out_word',OUT)]
class OracleFailure(AssertionError): pass
class Mismatch(AssertionError): pass
def check(value,message):
    if not value: raise OracleFailure(message)
def require(value,message):
    if not value: raise Mismatch(message)
def physical(seg,off): return (((seg&0xFFFF)*16+(off&0xFFFF))&MASK)
def put8(m,seg,off,v): m[physical(seg,off)]=v&255
def put16(m,seg,off,v):
    p=physical(seg,off);m[p]=v&255;m[(p+1)&MASK]=(v>>8)&255
def get16(m,seg,off):
    p=physical(seg,off);return m[p]|(m[(p+1)&MASK]<<8)

def cases():
    specs=[dict(name=f'normal-{dx:04x}',dx=dx,independent=True)
           for dx in (0x020C,0x020D,0x030A,0x030D,0x030E,0x0310,0x040E)]
    specs += [
        dict(name='zero-dh-is-256-planes',dx=0x0001,zero_model='planes'),
        dict(name='zero-dl-is-256-masks',dx=0x0100,zero_model='masks'),
        dict(name='both-zero-65536-or-iterations',dx=0,zero_model='masks'),
        dict(name='df-backward-copy-forward-mask',flags=0x0ED7),
        dict(name='exact-in-place',ds=0x6000,si=0x0200,di=0x0200,independent=True),
        dict(name='forward-byte-overlap',ds=0x6000,si=0x0200,di=0x0201),
        dict(name='backward-byte-overlap',ds=0x6000,si=0x0200,di=0x01FF),
        dict(name='source-word-offset-ffff',si=0xFFFF,dx=0x0101),
        dict(name='mask-byte-ea-wrap-ffff',di=0xFFFF,dx=0x0101,mask_wrap=True),
        dict(name='stosw-word-offset-ffff',di=0xFFFB,dx=0x0102),
        dict(name='segment-fold-wrap',es=0xFFF0,dx=0x0101),
        dict(name='stack-offset-wrap',sp=1,dx=0x0101),
        dict(name='outer-ret-offset-ffff',sp=0xFFFF,dx=0x0101),
        dict(name='physical-outer-ret-fffff',ss=0xFFFF,sp=0x000F,dx=0x0101),
        dict(name='physical-source-word-fffff',ds=0xFFFF,si=0x000F,dx=0x0101),
        dict(name='output-overwrites-saved-si-and-ret',es=0x5000,di=0x8FFE,
             dx=0x0101,source_word=0xBEEF),
        dict(name='output-overwrites-copy-cx',es=0x5000,di=0x8FFC,
             dx=0x0201,source_word=0x0105),
        dict(name='output-overwrites-mask-cx',es=0x5000,di=0x8FF6,
             dx=0x0102,source_word=0x0107),
        dict(name='provider-replaces-final-si',provider='saved-si'),
        dict(name='provider-shortens-mask-count',dx=0x0202,provider='mask-cx'),
        dict(name='output-overwrites-outer-ret',es=0x5000,di=0x9000,
             dx=0x0101,source_word=0x1234),
        dict(name='vga-destination',es=0xA000,dx=0x0203,vga=True),
        dict(name='vga-source',ds=0xA000,dx=0x0203,vga=True),
    ]
    for final in (0x000F,0x0010,0x7FFF,0x8000,0xFFFF):
        specs.append(dict(name=f'signed-fold-final-{final:04x}',dx=0x0101,
                          di=(final-4)&0xFFFF,expected_final_di=final))
    return [dict(dict(name='',dx=0x0203,ds=0x7000,es=0x6000,
                      ss=0x5000,sp=0x9000,si=0x0100,di=0x0200,
                      flags=0x0AD7,provider=None,seed=0x5BB000+index),**s)
            for index,s in enumerate(specs)]

def setup(case):
    memory=bytearray(random.Random(case['seed']).randbytes(SIZE))
    load=0x1010
    code=relocated(IMAGE,META['relocations'],load)
    memory[load*16:load*16+len(code)]=code
    regs=dict(ax=0xBEEF,bx=0xC17D,cx=0x4A93,dx=case['dx'],
              si=case['si'],di=case['di'],bp=0x79A3,sp=case['sp'],
              cs=load,ds=case['ds'],es=case['es'],ss=case['ss'],
              ip=ENTRY,flags=case['flags'])
    if case.get('source_word') is not None:
        put16(memory,regs['ds'],regs['si'],case['source_word'])
    if case.get('mask_wrap'):
        put16(memory,regs['ds'],regs['si'],0xC35A)
        put8(memory,regs['es'],0,0x7E)
    device=None
    if case.get('vga'):
        device=MinimapVga(case['seed'],read_map=0)
        device.seq[2]=0x0F
        for n in (0,1,3,4,5):device.gc[n]=0
        device.gc[6]=5;device.gc[8]=0xFF
        memory[VGA_BASE:VGA_END]=device.planes[0]
    put16(memory,regs['ss'],regs['sp'],0xD00D)
    return memory,regs,device

class Access(oracle.Access):
    event_limit=MAX_EVENTS
    def __init__(self,case,memory,regs,device,*,native=False):
        super().__init__(case,memory,regs,device)
        self.native=native;self.pending=[];self.low=None
    def instruction_complete(self):
        pending,self.pending=self.pending,[]
        for off,value,label in pending:
            self.modify_word(self.regs['ss'],off,value);self.used.add(label)
    def access(self,kind,address,flags,mask=FLAGS,value=None):
        observed=super().access(kind,address,flags,mask,value)
        label=self.case.get('provider')
        if kind=='write' and label and label not in self.used:
            offset=(self.regs['sp']-(2 if label=='saved-si' else 6))&0xFFFF
            start=physical(self.regs['ss'],offset)
            if address==start:self.low=observed
            if address==((start+1)&MASK) and self.low is not None:
                replacement=0xBEEF if label=='saved-si' else 0x0193
                self.pending.append((offset,replacement,label));self.low=None
                if self.native:self.instruction_complete()
        return observed

def original(case,memory,regs,device,*,core):
    return oracle.original(case,bytearray(memory),dict(regs),copy.deepcopy(device),
        core,entry_flag_mask=FLAGS,main_instructions=OWN_INS,
        access_factory=lambda c,m,r,d:Access(c,m,r,d),instruction_limit=MAX_STEPS)

def independent(case,initial,regs,expected):
    if case.get('independent'):
        dh,dl=case['dx']>>8,case['dx']&255
        source=bytes(initial[(physical(regs['ds'],regs['si'])+n)&MASK]
                     for n in range(2*dh*dl))
        bank=layout.expected_5bb0(source,case['dx'])
        start=physical(regs['es'],regs['di'])
        observed=bytes(expected['memory'][(start+n)&MASK] for n in range(len(bank)))
        check(observed==bank,case['name']+': independent bank differs')
        return len(bank)
    if case.get('zero_model'):
        start=physical(regs['es'],regs['di'])
        if case['zero_model']=='planes':
            source=initial[physical(regs['ds'],regs['si']):physical(regs['ds'],regs['si'])+512]
            low=high=0
            for n in range(0,512,2):low|=source[n];high|=source[n+1]
            bank=source+bytes([low,high])
        else:
            bank=initial[start:start+512]
        check(expected['memory'][start:start+len(bank)]==bank,
              case['name']+': independent zero-count output differs')
        return len(bank)
    if case.get('mask_wrap'):
        check(get16(expected['memory'],regs['es'],1)==0x7E5A,
              'separate byte operands lost their16-bit EA wrap')
        return 2
    return 0

def validate_original(case,memory,regs,expected,*,core):
    check(expected['status']==0,case['name']+': unexpected original seam')
    if case.get('provider'):
        check(expected['used']=={case['provider']},case['name']+': provider missing')
    check(expected['regs']['ip']==(RET if core else get16(expected['memory'],
          expected['regs']['ss'],regs['sp'])),case['name']+': actual outer RET differs')
    check(expected['regs']['sp']==((regs['sp']+(0 if core else 2))&0xFFFF),
          case['name']+': stack is not balanced')
    if 'expected_final_di' in case:
        raw=case['expected_final_di'];folded=raw>=0x10 and raw<0x8000
        check(expected['regs']['di']==(raw&15 if folded else raw),
              case['name']+': signed fold destination differs')
        check(expected['regs']['es']==((regs['es']+(raw>>4))&0xFFFF if folded else regs['es']),
              case['name']+': signed fold segment differs')
        check(expected['regs']['cx']==(regs['es'] if folded else regs['cx']&255),
              case['name']+': fold-path CX ownership differs')
    return independent(case,memory,regs,expected)

def die(error):
    try:os.write(2,(str(error)+'\n').encode('utf-8',errors='replace'))
    finally:os._exit(86 if 'budget' in str(error) else 87)

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'sprite-bank-m{mutation}.dll',mutation,'sprite_bank')))
        self.core=self.lib.lmn_copy_sprite_planes_mask_core
        self.core.argtypes=[MEM,ct.POINTER(Call),ct.POINTER(Bus)]
        self.core.restype=Result
        self.adapter=self.lib.lmn_copy_sprite_planes_mask_adapter
        self.adapter.argtypes=[MEM,ct.POINTER(oracle.Regs),ct.POINTER(Bus)]
        self.adapter.restype=ct.c_uint16
    def run(self,case,memory,regs,device,*,core):
        access=Access(case,memory,regs,device,native=True)
        def read(_c,_m,address,flags):
            try:return access.access('read',address,flags)
            except BaseException as e:die(e)
        def write(_c,_m,address,value,flags):
            try:access.access('write',address,flags,value=value)
            except BaseException as e:die(e)
        def out(*_args):die('unexpected OUT in sprite-bank leaf')
        callbacks=READ(read),WRITE(write),OUT(out)
        bus=Bus(None,*callbacks);ram=(ct.c_uint8*SIZE).from_buffer(memory)
        state=oracle.Regs(**regs)
        if core:
            result=self.core(ram,ct.byref(Call(*(regs[n] for n in REGS))),ct.byref(bus))
            for role,reg in zip(NAMES,REGS):setattr(state,reg,getattr(result,role))
            state.ip=result.continuation;status=result.status
        else:status=self.adapter(ram,ct.byref(state),ct.byref(bus))
        return dict(memory=bytes(memory),regs={n:getattr(state,n) for n in oracle.REG_NAMES},
                    status=status,events=access.events,used=access.used,device=device)

def equal(got,ref,label):
    require(got['status']==ref['status'],label+': status')
    require(got['memory']==ref['memory'],label+': RAM')
    for name in oracle.REG_NAMES:
        mask=ref['flag_mask'] if name=='flags' else 0xFFFF
        require(((got['regs'][name]^ref['regs'][name])&mask)==0,
                f'{label}: {name} {got["regs"][name]:04X}/{ref["regs"][name]:04X} mask{mask:04X}')
    require(got['used']==ref['used'],label+': provider transitions')
    require(len(got['events'])==len(ref['events']),label+': event count')
    for index,(actual,wanted) in enumerate(zip(got['events'],ref['events'])):
        require(actual[:3]==wanted[:3],f'{label}: event{index} {actual[:3]}/{wanted[:3]}')
        require(((actual[3]^wanted[3])&wanted[4])==0,
                f'{label}: event{index} FLAGS{actual[3]:04X}/{wanted[3]:04X} mask{wanted[4]:04X}')
    if ref['device'] is not None:
        require(got['device'].state()==ref['device'].state(),label+': VGA state')
        require([e[:3] for e in got['device'].trace]==[e[:3] for e in ref['device'].trace],
                label+': VGA trace')

def compare(native,case,*,core):
    memory,regs,device=setup(case)
    ref=original(case,memory,regs,device,core=core)
    checks=validate_original(case,memory,regs,ref,core=core)
    got=native.run(case,bytearray(memory),dict(regs),copy.deepcopy(device),core=core)
    equal(got,ref,case['name']+(' core' if core else ' adapter'))
    return ref,checks

def handoffs(native=None,directory=None):
    """Actual bank bytes flow through one RAM image into existing C consumers.

    The constructed second CALL frame is explicit; this is not execution59BB.
    Consumer sites/events are separate from the86-byte producer acceptance.
    """
    child=planes.Native(directory) if native is not None else None
    result=[]
    for dx,profile,shift in ((0x030A,'3plane10',0),(0x030D,'3plane13',1),
            (0x030E,'3plane14',7),(0x0310,'3plane16',3),(0x040E,'4plane14',5)):
        pcase=next(c for c in cases() if c['name']==f'normal-{dx:04x}')
        ccase=next(c for c in planes.make_cases()
                   if c['name']==profile+'-shift-000').copy()
        ccase.update(shift=shift,plane_check=False)
        memory,regs,_=setup(pcase)
        device=MinimapVga(pcase['seed'],read_map=0)
        device.seq[2]=0x0F
        for n in (0,1,3,4,5):device.gc[n]=0
        device.gc[6]=5;device.gc[8]=0xFF
        memory[VGA_BASE:VGA_END]=device.planes[0]
        ref=original(pcase,memory,regs,device,core=False)
        validate_original(pcase,memory,regs,ref,core=False)
        actual_memory=bytearray(memory)
        if native is not None:
            got=native.run(pcase,actual_memory,dict(regs),copy.deepcopy(device),core=False)
            equal(got,ref,profile+' handoff producer')
        bank_length=2*(dx&255)*((dx>>8)+1)
        start=physical(regs['es'],regs['di'])
        bank=ref['memory'][start:start+bank_length]
        crefregs=dict(ref['regs'])
        # Preserve returned DS/ES/FLAGS and other residual roles. Prepare only
        # the consumer arguments and its actual new near-CALL return word.
        def prepare(ram,state):
            state.update(ip=planes.PROFILES[profile]['entry'],cx=regs['es'],
                         si=regs['di'],bx=regs['di']+2*(dx>>8)*(dx&255),
                         di=0x3000,dx=shift,sp=(state['sp']-2)&0xFFFF)
            put16(ram,state['ss'],state['sp'],0xD00D)
        refmem=bytearray(ref['memory'])
        prepare(refmem,crefregs)
        cref=planes.run_original(ccase,refmem,crefregs,ref['device'],core=False)
        check(cref['status']==0,profile+': consumer original did not return')
        check(cref['memory'][start:start+bank_length]==bank,profile+': original bank changed')
        if child is not None:
            cregs=dict(got['regs']);prepare(actual_memory,cregs)
            actual=child.run(ccase,actual_memory,cregs,got['device'],core=False)
            equal(actual,cref,profile+' handoff consumer')
            require(actual_memory[start:start+bank_length]==bank,profile+': native bank changed')
        result.append(dict(profile=profile,dx=dx,shift=shift,bank_bytes=bank_length,
            bank_sha256=sha(bank),producer_events=len(ref['events']),
            producer_steps=ref['steps'],consumer_events=len(cref['events']),
            consumer_steps=cref['steps'],consumer_sites=sorted(p for scope,p in cref['sites']
                                                             if scope=='main'),
            native_compared=native is not None))
    return result

def hashes():
    paths=set(('AGENTS.md','docs/executable.md','docs/bottom-up.md','docs/next-work.md',
        'docs/sprite-bank.md','assets/vgalemmi.exe','assets/adlib.dat','assets/tandysnd.dat',
        'assets/main.dat','c/sprite_bank.c','c/sprite_bank.h','c/lemmings_sym.h','c/regs.h',
        'c/special_blit.h','tests/sprite_bank.py','tests/entity_interactions.py',
        'tests/entity_sprite_layout.py','tests/minimap_vga.py','tests/pcspeaker_dispatch.py',
        'tests/sound_latches.py','tools/cbuild.py','tools/bounded_process.py',
        'tools/difftest.py','tools/common.py','tools/unpack.py','tools/resources.py','tools/coverage.py'))
    paths.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'metadata').glob('*.json'))
    paths.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'src').rglob('*.asm'))
    paths.update(planes.input_hashes())
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def edges():
    return {(pc,target) for pc,i in OWN_INS.items() if i.group(capstone.CS_GRP_JUMP)
            for target in ((i.operands[0].imm&0xFFFF),(pc+i.size)&0xFFFF)}

def collect(ref,case,core,checks):
    return dict(name=case['name'],boundary='core' if core else 'adapter',
        sites=sorted(off for scope,off in ref['sites'] if scope=='main'),
        edges=sorted([a,b] for scope,a,b in ref['edges'] if scope=='main'),
        events=len(ref['events']),steps=ref['steps'],independent_bytes=checks)

def original_campaign():
    before=hashes();rows=[]
    for case in cases():
        memory,regs,device=setup(case)
        for core in (True,False):
            ref=original(case,memory,regs,device,core=core)
            count=validate_original(case,memory,regs,ref,core=core)
            rows.append(collect(ref,case,core,count))
        gc.collect()
    check(before==hashes(),'inputs changed during original campaign')
    hands=handoffs()
    check(before==hashes(),'inputs changed during original handoffs')
    return before,rows,hands

def publish(path,before,rows,hands,mutants=None):
    sites={pc for row in rows for pc in row['sites']}
    branches={tuple(e) for row in rows for e in row['edges']}
    check(sites==OWN_SITES,'missing original instruction sites')
    check(branches==edges(),'missing original branch outcomes')
    report=dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases()),
        comparison_count=len(rows),translated_code_bytes=86,instruction_sites=45,
        executed_instruction_addresses=sorted(sites),branch_edges=sorted([a,b] for a,b in branches),
        branch_edge_count=len(branches),ordered_events=sum(r['events'] for r in rows),
        original_instruction_steps=sum(r['steps'] for r in rows),
        independent_output_bytes=sum(r['independent_bytes'] for r in rows),
        original_only=mutants is None,mutation_count=len(mutants or []),
        mutations=mutants or [],rows=rows,input_hashes=before,
        producer_consumer_handoffs=hands,
        handoff_native_comparisons=0 if mutants is None else 2*len(hands),
        handoff_ordered_events=sum(h['producer_events']+h['consumer_events'] for h in hands),
        limits=dict(timeout_seconds=360,process_commit_mib=384,
                    original_instruction_limit=MAX_STEPS,bus_event_limit=MAX_EVENTS))
    write_json(path,report)
    print(f'PASS sprite bank: {len(cases())} fixtures/{len(rows)} boundaries, '
          f'{len(sites)} sites/{len(branches)} edges, {report["ordered_events"]} events, '
          f'{len(mutants or [])} mutants',flush=True)

def worker(directory,hash_path):
    before=json.loads(Path(hash_path).read_text());check(before==hashes(),'snapshot differs')
    _,preflight,_=original_campaign()
    check({p for r in preflight for p in r['sites']}==OWN_SITES,'original site union')
    check({tuple(e) for r in preflight for e in r['edges']}==edges(),'original edge union')
    native=Native(directory);rows=[]
    for case in cases():
        for core in (True,False):
            ref,count=compare(native,case,core=core);rows.append(collect(ref,case,core,count))
        gc.collect()
    witnesses=[(1,'zero-dh-is-256-planes',True),(2,'zero-dl-is-256-masks',True),
        (3,'df-backward-copy-forward-mask',True),(4,'normal-030d',True),
        (5,'mask-byte-ea-wrap-ffff',True),(6,'signed-fold-final-8000',True),
        (7,'provider-replaces-final-si',True),(8,'provider-shortens-mask-count',True),
        (9,'output-overwrites-outer-ret',False),(10,'normal-020c',False)]
    by_name={c['name']:c for c in cases()};mutants=[]
    for number,name,core in witnesses:
        mutant=Native(directory,number)
        try:compare(mutant,by_name[name],core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=number,case=name,core=core,completed=True,mismatch=str(error)))
        else:raise OracleFailure(f'mutation{number} survived')
        gc.collect()
    check(before==hashes(),'inputs changed during native campaign')
    hands=handoffs(native,directory)
    check(before==hashes(),'inputs changed during native handoffs')
    publish(REPORT,before,rows,hands,mutants)

def main():
    args=sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(args[1],args[2]);return
    if args==['--original-worker']:
        before,rows,hands=original_campaign();publish(ORIGINAL_REPORT,before,rows,hands);return
    if args not in ([],['--original-only']):raise SystemExit('usage: sprite_bank.py [--original-only]')
    BUILD.mkdir(exist_ok=True)
    if args:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,
                    timeout=360,memory_mib=384,check=True);return
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='sprite-bank-',parent=BUILD) as directory:
        snap=Path(directory)/'inputs.json';snap.write_text(json.dumps(hashes()))
        run_bounded([sys.executable,__file__,'--worker',directory,str(snap)],cwd=ROOT,
                    timeout=360,memory_mib=384,check=True)
if __name__=='__main__':main()
