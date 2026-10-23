"""Bounded original/native comparison for the planar dispatch prefix."""
import ctypes
import random
import sys
from pathlib import Path

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
import capstone
from unicorn import (Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,
                     UC_HOOK_MEM_WRITE,UC_HOOK_INTR,__version__ as UNICORN_VERSION)
from unicorn import x86_const as x
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated
from cbuild import build
from dat_io_c import Regs,MEM
import dat_io as oracle

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
START=SYMS['PlanarInputsReady']['address']
GATE=SYMS['PlanarIncomingFlagGate']['address']
SELECTOR=SYMS['SelectUnshiftedPlanarPath']['address']
ABORT=SYMS['PlanarDrawingAbortReturn']['address']
SHIFTED=SYMS['PrepareShiftedMaskedPlanarRows']['address']
SHIFTED_OPAQUE=SYMS['PrepareShiftedOpaquePlanarRows']['address']
ALIGNED=SYMS['PrepareAlignedMaskedPlanarRows']['address']
ALIGNED_OPAQUE=SYMS['PrepareAlignedOpaquePlanarRows']['address']
ENDPOINTS={ABORT,SHIFTED,SHIFTED_OPAQUE,ALIGNED,ALIGNED_OPAQUE}
RANGES=((0x885E,0x88AA),(0x88AC,0x88BF),(0x939E,0x93A7))
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for begin,end in RANGES for i in MD.disasm(IMAGE[begin:end],begin)}
MAIN_SITES={pc for pc in INS if pc<SELECTOR}
TAIL_SITES={pc for pc in INS if pc>=SELECTOR}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
ARITH_MASK=0x8D5
DEFINED_MASK=0xFC7

class DispatchCall(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint16) for n in (
        'data_segment','stack_segment','stack_offset','left','top','packed_height','width',
        'source_cursor','destination_cursor','control','flags')]

class DispatchResult(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint16) for n in (
        'work_value','second_source_cursor','packed_counts','width_state','source_cursor',
        'destination_cursor','control','stack_offset','flags','continuation')]

READ=ctypes.CFUNCTYPE(ctypes.c_uint8,ctypes.c_void_p,MEM,ctypes.c_uint32,ctypes.c_uint16)
WRITE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.c_uint32,ctypes.c_uint8,ctypes.c_uint16)
OUT=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint16)
class RasterBus(ctypes.Structure):
    _fields_=[('context',ctypes.c_void_p),('read_byte',READ),('write_byte',WRITE),('out_word',OUT)]

def physical(segment,offset):
    return (((segment<<4)+offset)&0xFFFFF)

def put_byte(memory,segment,offset,value):
    memory[physical(segment,offset)]=value&255

def put_word(memory,segment,offset,value):
    address=physical(segment,offset)
    memory[address]=value&255
    memory[(address+1)&0xFFFFF]=(value>>8)&255

def library(mutation=0):
    path=BUILD/('drawing-dispatch-m{}.dll'.format(mutation))
    lib=ctypes.CDLL(str(build(path,mutation,'drawing_dispatch')))
    lib.lmn_prepare_planar_drawing_dispatch_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(RasterBus)]
    lib.lmn_prepare_planar_drawing_dispatch_adapter.restype=None
    lib.lmn_prepare_planar_drawing_dispatch_core.argtypes=[MEM,ctypes.POINTER(DispatchCall),ctypes.POINTER(RasterBus)]
    lib.lmn_prepare_planar_drawing_dispatch_core.restype=DispatchResult
    lib.lmn_select_unshifted_planar_path_core.argtypes=[MEM,ctypes.POINTER(DispatchCall),ctypes.POINTER(RasterBus)]
    lib.lmn_select_unshifted_planar_path_core.restype=DispatchResult
    return lib

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for control in (0,1,2,3):
        for residue in range(8):
            add('normal-control-{}-left-residue-{}'.format(control,residue),entry=START,
                left=0x1200+residue,top=(0x30+residue*0x101)&0xFFFF,
                height=(0x4500|((residue*37+9)&255)),width=(0x1200+residue*0x101)&0xFFFF,
                control=control,page=(0x100+residue*0x31)&0xFFFF)
    add('normal-left-save-overwrites-pushed-BX',entry=START,ds=0x6000,ss=0x6000,sp=0xA94A,
        left=0xBEEF,top=0x1234,height=0x7A08,width=0xF13B,pitch=0x29,origin=0xFFF0,page=0x1001,control=1)
    add('normal-pushed-DX-overwrites-live-pitch',entry=START,ds=0x6000,ss=0x6000,sp=0x66F6,
        left=0x1027,top=0x1234,height=0xA50B,width=0xD267,pitch=0x31,origin=0x8001,page=0xFFFF,control=3)
    add('normal-data-physical-wrap',entry=START,ds=0xFFFF,ss=0xFFFF,sp=0x0001,
        left=0xFFFD,top=0xFE12,height=0x00FF,width=0xFFFF,pitch=0x0103,origin=0xF123,page=0xABCD,control=2)
    add('normal-stack-offset-wrap',entry=START,ds=0x7000,ss=0x7000,sp=0x0000,
        left=0xAA07,top=0xFFFF,height=0x1200,width=0xFFFF,pitch=0xE003,origin=0xFFFF,page=0x0001,control=1)
    add('normal-row-arithmetic-wrap',entry=START,ds=0x6200,ss=0x7100,sp=0xFFFF,
        left=0xFE07,top=0xFFFF,height=0xFFFE,width=0xFFFF,pitch=0x0001,origin=0x8000,page=0x8001,control=3)
    add('normal-zero-pitch-extent',entry=START,left=0xAB07,top=0xFFFF,height=0xFF08,width=0xFFFF,
        pitch=0,origin=0xFFFF,page=0xFFFF,extent=0,control=0)
    add('normal-wide-multiply-product',entry=START,left=0x1705,top=0x1234,height=0x9E7F,width=0x4567,
        pitch=0x2345,origin=0xEDCB,page=0x7654,extent=0xBEEF,control=2)
    for zf in (0,1):
        for shift in (0,1,7,0x80):
            for control in (0,1,2,3):
                add('incoming-88a6-zf-{}-shift-{:02x}-control-{}'.format(zf,shift,control),entry=GATE,
                    zf=zf,shift=shift,control=control,left=0xA125,top=0xB637,height=0x8C4D,
                    width=0xE39B,source=0x1357,destination=0x2468,sp=0x7FFF)
    for control in (0,1,2,3,0x80,0x8002):
        add('tail-entry-939e-control-{:04x}'.format(control),entry=SELECTOR,control=control,
            left=0xA123,top=0x4567,height=0x89AB,width=0xCDEF,source=0x1357,
            destination=0x2468,sp=0xFFFE)
    return out

def prepare(case):
    rng=random.Random(0x885E+case['seed'])
    load=0x1010
    memory=bytearray(rng.randbytes(1<<20))
    memory[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    ds=case.get('ds',load+0x9A9);ss=case.get('ss',0x7000);sp=case.get('sp',0x8000)
    regs={name:rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load,ip=case.get('entry',START),ds=ds,ss=ss,sp=sp,
        ax=case.get('left',0x1507),bx=case.get('top',0x0259),
        cx=case.get('height',0x4609),dx=case.get('width',0x238D),
        si=case.get('source',0x2468),di=case.get('destination',0x3579),bp=case.get('control',0))
    flags=2|((case['seed']*0x95)&0x8D5)
    if case['seed']&1:flags|=0x200
    if case['seed']%3==0:flags|=0x400
    if case.get('entry')==GATE and case.get('zf'):flags|=0x40
    else:flags&=~0x40
    for offset,key,default in ((0x66F4,'pitch',0x15A3),(0x1F76,'origin',0x2345),
        (0x1F7A,'page',0x3456),(0x66F8,'extent',0x789A)):
        put_word(memory,ds,offset,case.get(key,default))
    if case.get('entry')==GATE:put_byte(memory,ds,0xA948,case.get('shift',0))
    put_word(memory,ss,sp,0xA55A)
    put_word(memory,ss,(sp+2)&0xFFFF,0xB66B)
    return memory,regs,flags,load

def expected_flag_mask(case,continuation):
    if case.get('entry')==GATE and continuation==ABORT:
        return DEFINED_MASK|0x10
    return DEFINED_MASK

def execute_original(case):
    memory,regs,flags,load=prepare(case)
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(memory)*2)
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    entry=case.get('entry',START)
    entry_name={START:'normal885e',GATE:'incoming88a6',SELECTOR:'tail939e'}[entry]
    seen=set();edges=set();current_pc=None;current_flags=flags;current_mask=DEFINED_MASK
    pending_mask=DEFINED_MASK;suppress_mirror=False
    done={};memory_events=[];raw_mul_read_flags=[];steps=0
    def code(uc,pc,size,_):
        nonlocal current_pc,current_flags,current_mask,pending_mask,steps
        off=pc-(load<<4)
        if current_pc in BRANCHES:edges.add((entry_name,current_pc,off))
        if off in ENDPOINTS:done['continuation']=off;uc.emu_stop();return
        if off not in INS or uc.reg_read(oracle.REG['cs'])!=load:
            raise AssertionError('{}: original escaped at {:04x}'.format(case['name'],off))
        current_mask=pending_mask
        current_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        current_pc=off;seen.add(off);steps+=1
        if steps>80:raise AssertionError('{}: instruction budget exceeded'.format(case['name']))
        mnemonic=INS[off].mnemonic
        if mnemonic in ('and','test','shr'):pending_mask=0x8C5
        elif mnemonic in ('add','sub','neg','cmp'):pending_mask=ARITH_MASK
        elif mnemonic=='mul':pending_mask=0x801
    def read_wrap(uc,access,address,size,value,_):
        nonlocal suppress_mirror
        for i in range(size):
            p=address+i
            if p>=1<<20:
                suppress_mirror=True
                uc.mem_write(p,bytes(uc.mem_read(p&0xFFFFF,1)))
                suppress_mirror=False
    def write_wrap(uc,access,address,size,value,_):
        nonlocal suppress_mirror
        for i in range(size):
            p=address+i
            if p>=1<<20:
                suppress_mirror=True
                uc.mem_write(p&0xFFFFF,bytes(((value>>(8*i))&255,)))
                suppress_mirror=False
    def mem_read(uc,access,address,size,value,_):
        if current_pc is None or suppress_mirror:return
        for i in range(size):
            p=(address+i)&0xFFFFF;b=bytes(uc.mem_read(address+i,1))[0]
            memory_events.append(('read',p,b,current_flags,current_mask))
        if current_pc==0x886F:
            raw_mul_read_flags.append(dict(boundary=current_flags,hook=uc.reg_read(x.UC_X86_REG_EFLAGS)))
    def mem_write(uc,access,address,size,value,_):
        if current_pc is None or suppress_mirror:return
        for i in range(size):
            p=(address+i)&0xFFFFF
            memory_events.append(('write',p,(value>>(8*i))&255,current_flags,current_mask))
    def intr(uc,num,_):raise AssertionError('{}: unexpected INT {:02x}'.format(case['name'],num))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read_wrap);u.hook_add(UC_HOOK_MEM_WRITE,write_wrap)
    u.hook_add(UC_HOOK_MEM_READ,mem_read);u.hook_add(UC_HOOK_MEM_WRITE,mem_write);u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start((load<<4)+entry,0,count=100)
    if 'continuation' not in done:raise AssertionError('{}: original missed a dispatch boundary'.format(case['name']))
    final_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()}
    final_flags=u.reg_read(x.UC_X86_REG_EFLAGS);final_memory=bytes(u.mem_read(0,1<<20))
    for begin,end in RANGES:
        p=(load<<4)+begin
        if final_memory[p:p+end-begin]!=IMAGE[begin:end]:
            raise AssertionError('{}: dispatch instruction bytes changed'.format(case['name']))
    return dict(memory=final_memory,regs=final_regs,flags=final_flags,continuation=done['continuation'],
        events=memory_events,sites=seen,edges=edges,raw_mul_read_flags=raw_mul_read_flags,
        final_mask=expected_flag_mask(case,done['continuation']))

def execute_native(case,lib,with_bus=True):
    memory,initial_regs,flags,load=prepare(case);regs=Regs(**initial_regs,flags=flags)
    events=[];callbacks=[]
    if with_bus:
        @READ
        def read(context,m,p,inflags):
            value=m[p];events.append(('read',int(p),int(value),int(inflags),DEFINED_MASK));return value
        @WRITE
        def write(context,m,p,value,inflags):
            m[p]=value;events.append(('write',int(p),int(value),int(inflags),DEFINED_MASK))
        callbacks.extend((read,write));bus=RasterBus(None,read,write,OUT());bus_arg=ctypes.byref(bus)
    else:bus_arg=None
    mem_array=(ctypes.c_uint8*(1<<20)).from_buffer(memory)
    lib.lmn_prepare_planar_drawing_dispatch_adapter(mem_array,ctypes.byref(regs),bus_arg)
    output_regs={name:getattr(regs,name) for name in oracle.REG_NAMES}
    return dict(memory=bytes(memory),regs=output_regs,flags=regs.flags,continuation=regs.ip,events=events,load=load)

def mismatch(original,native,case,compare_events=True):
    if native['continuation']!=original['continuation']:
        return 'continuation C={:04x}/ASM={:04x}'.format(native['continuation'],original['continuation'])
    for name in oracle.REG_NAMES:
        if native['regs'][name]!=original['regs'][name]:
            return '{} C={:04x}/ASM={:04x}'.format(name,native['regs'][name],original['regs'][name])
    mask=original['final_mask']
    if (native['flags']^original['flags'])&mask:
        return 'flags C={:04x}/ASM={:04x},mask={:04x}'.format(native['flags'],original['flags'],mask)
    if native['memory']!=original['memory']:
        p=next(i for i,(a,b) in enumerate(zip(native['memory'],original['memory'])) if a!=b)
        return 'RAM differs at {:05x}: C={:02x}/ASM={:02x}'.format(p,native['memory'][p],original['memory'][p])
    if compare_events:
        a=native['events'];b=original['events']
        if len(a)!=len(b):return 'RAM bus event count C={}/ASM={}'.format(len(a),len(b))
        for index,(c_event,u_event) in enumerate(zip(a,b)):
            if c_event[:3]!=u_event[:3]:
                return 'RAM event {} C={}/ASM={}'.format(index,c_event[:3],u_event[:3])
            if (c_event[3]^u_event[3])&u_event[4]:
                return 'RAM event {} flags C={:04x}/ASM={:04x},mask={:04x}'.format(
                    index,c_event[3],u_event[3],u_event[4])
    return None

def direct_core_check(lib):
    memory=bytearray(1<<20)
    call=DispatchCall(0x1234,0x5678,0x9ABC,0xA123,0x4567,0x89AB,0xCDEF,
        0x1357,0x2468,2,0x0AD7)
    arr=(ctypes.c_uint8*(1<<20)).from_buffer(memory)
    dispatch=lib.lmn_prepare_planar_drawing_dispatch_core(arr,ctypes.byref(call),None)
    selector_call=DispatchCall(0x1234,0x5678,0x9ABC,0xA123,0x4567,0x89AB,0xCDEF,
        0x1357,0x2468,0,0x0AD7)
    selected=lib.lmn_select_unshifted_planar_path_core(arr,ctypes.byref(selector_call),None)
    if dispatch.continuation!=ALIGNED or dispatch.control!=2 or dispatch.source_cursor!=0x1357:
        raise AssertionError('typed dispatch core result malformed')
    if selected.continuation!=ALIGNED_OPAQUE or selected.second_source_cursor!=0x4567:
        raise AssertionError('typed selector core result malformed')

def required_edges():
    rows=[]
    def add(entry,source,*targets):
        rows.extend((entry,source,target) for target in targets)
    e='normal885e'
    add(e,0x88A1,0x88A3,0x88A6);add(e,0x88A3,0x939E);add(e,0x88A6,0x88A8)
    add(e,0x88A8,0x88AC);add(e,0x88B1,0x88B3,0x88B6);add(e,0x88B3,0x939E)
    add(e,0x88BA,0x88BC,0x88BF);add(e,0x88BC,0x9140)
    add(e,0x93A2,0x93A4,0x93A7);add(e,0x93A4,0x9810)
    e='incoming88a6'
    add(e,0x88A6,0x88A8,0x88AB);add(e,0x88A8,0x88AC)
    add(e,0x88B1,0x88B3,0x88B6);add(e,0x88B3,0x939E)
    add(e,0x88BA,0x88BC,0x88BF);add(e,0x88BC,0x9140)
    add(e,0x93A2,0x93A4,0x93A7);add(e,0x93A4,0x9810)
    e='tail939e';add(e,0x93A2,0x93A4,0x93A7);add(e,0x93A4,0x9810)
    return set(rows)

def main():
    report=BUILD/'drawing-dispatch-differential.json';report.unlink(missing_ok=True)
    baseline=cases();lib=library();direct_core_check(lib)
    seen=set();edges=set();cases_report=[];mul_observations=[]
    for case in baseline:
        original=execute_original(case);native=execute_native(case,lib,True)
        problem=mismatch(original,native,case)
        if problem:raise AssertionError('{}: {}'.format(case['name'],problem))
        plain=execute_native(case,lib,False);problem=mismatch(original,plain,case,False)
        if problem:raise AssertionError('{}: null-bus path {}'.format(case['name'],problem))
        if plain['memory']!=native['memory'] or plain['regs']!=native['regs'] or plain['flags']!=native['flags']:
            raise AssertionError('{}: RAM callback and null-bus paths differ'.format(case['name']))
        seen|=original['sites'];edges|=original['edges']
        for observation in original['raw_mul_read_flags']:
            mul_observations.append(dict(case=case['name'],
                instruction_boundary_flags=observation['boundary'],
                memory_hook_flags=observation['hook'],
                cf_of_disagrees=bool((observation['boundary']^observation['hook'])&0x801)))
        cases_report.append(case['name'])
    if seen!=set(INS):raise AssertionError('missing original sites {}'.format(sorted(set(INS)-seen)))
    if edges!=required_edges():
        raise AssertionError('branch edge coverage differs; missing={}, unexpected={}'.format(
            sorted(required_edges()-edges),sorted(edges-required_edges())))

    mutations=[]
    for mutation,name,case_name in (
        (1,'shift-mask-minus-high-bit','normal-control-1-left-residue-7'),
        (2,'destination-page-offset-omitted','normal-control-0-left-residue-3'),
        (3,'stale-DX-after-MUL','normal-wide-multiply-product')):
        mutated=library(mutation);case=next(c for c in baseline if c['name']==case_name)
        original=execute_original(case);native=execute_native(case,mutated,True)
        problem=mismatch(original,native,case)
        if not problem:raise AssertionError('compiled mutation {} survived'.format(mutation))
        mutations.append(dict(mutation=mutation,name=name,case=case_name,difference=problem))

    paths=('src/program.asm','src/planar_drawing.asm','c/drawing_dispatch.c','c/drawing_dispatch.h','c/lemmings_sym.h',
        'c/special_blit.h','c/regs.h','tests/drawing_dispatch.py','tests/drawing_inputs.py',
        'tests/special_blit.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py',
        'tools/difftest.py','tools/unpack.py','tools/coverage.py','metadata/symbols.json')
    entry_tagged_branch_edges=[dict(entry=entry,source=source,target=target)
        for entry,source,target in sorted(edges)]
    branch_edges=sorted({(source,target) for _,source,target in edges})
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),
        mutation_count=3,mutations_detected=mutations,cases=cases_report,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(MAIN_SITES),
        shared_tail_instruction_addresses=sorted(TAIL_SITES),branch_edges=branch_edges,
        entry_tagged_branch_edges=entry_tagged_branch_edges,
        translated_code_bytes=sum(i.size for i in INS.values()),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        mul_memory_hook_observation=dict(unicorn_version=UNICORN_VERSION,observations=mul_observations,
            boundary_flags_used=True,cf_of_disagreement_count=sum(o['cf_of_disagrees'] for o in mul_observations),
            counts_as_case=False),
        domain='885E..88AA plus 88AC..88BF and shared 939E..93A6; UNKNOWN 88AA and far RETF 88AB excluded; logical exits at 88AB/88BF/9140/93A7/9810; direct 88A6 incoming-ZF and 939E tail entries; intact executing code; whole 1 MiB RAM, all registers, defined flags and ordered byte-bus access; RAM callbacks and null-bus parity; no renderer body execution'))
    print('PASS drawing dispatch: {} cases, {} caller sites, {} shared-tail sites, {} executed sites, {} entry-tagged observations, {} unique static edges; 3 compiled mutants, {} translated bytes'.format(
        len(baseline),len(MAIN_SITES),len(TAIL_SITES),len(seen),len(edges),len(branch_edges),sum(i.size for i in INS.values())))

if __name__=='__main__':main()
