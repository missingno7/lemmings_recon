"""Bounded complete 59BB transform and native child-frame comparisons."""
from __future__ import annotations

from array import array
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_sprite_bank_layout as model
import sprite_bank as shared
import sprite_shift_banks as shifts
import sprite_wide_banks as wide

oracle = shared.oracle
IMAGE, SIZE, MASK, FLAGS = shared.IMAGE, shared.SIZE, shared.MASK, shared.FLAGS
ENTRY, RET, END = 0x59BB, 0x5AC0, 0x5AC1
SOURCE_SELECTOR, OUTPUT_SELECTOR = 0x1FE4, 0x1FE6
MAX_STEPS, MAX_EVENTS = 3_000_000, 900_000
WORKER_SECONDS, MEMORY_MIB = 900, 512
REPORT = BUILD/'entity-sprite-banks-differential.json'
ORIGINAL_REPORT = BUILD/'entity-sprite-banks-original-differential.json'
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {i.address:i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
MAIN_INS = OWN_INS | shifts.OWN_INS | shared.OWN_INS | wide.OWN_INS
CHILD_RETS = {0x5B11:0x5BAF, 0x5BB0:0x5C05, 0x5C06:0x5CC0}
CALLS = tuple(model.GROUPS)+(model.FINAL_CHILD,)
CALL_RETURNS = {row['call_site']:({CHILD_RETS[row['child_entry']]},101+n)
                for n,row in enumerate(CALLS)}
RETURN_ROWS = {row['return_ip']:row for row in CALLS}
check, require = shared.check, shared.require
physical, put8, put16, get16 = shared.physical, shared.put8, shared.put16, shared.get16


class CompactEvents:
    """Exact ordered tuples in bounded packed storage, never an unbounded list."""
    def __init__(self):self.data = array('I')
    def __len__(self):return len(self.data)//5
    def append(self, event):
        kind,address,value,flags,mask = event
        self.data.extend((int(kind=='write'),address,value,flags,mask))
    def __iter__(self):
        for n in range(0,len(self.data),5):
            yield ('write' if self.data[n] else 'read', *self.data[n+1:n+5])


class Result(ct.Structure):
    _fields_ = shared.Result._fields_ + [('child_entry',ct.c_uint16),('child_status',ct.c_uint16)]


def cases():
    specs = [
        dict(name='full-main-section-zero', short=False, source='asset', independent=True),
        dict(name='full-constructed-source', short=False, independent=True),
        dict(name='one-call-per-group', independent=True),
        dict(name='df-sensitive-word-children', flags=0x0ED7),
        dict(name='destination-paragraph-wrap', es=0xFFF0, independent=True),
        dict(name='source-physical-wrap', source_segment=0xFFFF),
        dict(name='stack-offset-one', sp=1),
        dict(name='outer-ret-offset-ffff', sp=0xFFFF),
        dict(name='physical-outer-ret-top', ss=0xFFFF, sp=0x000F),
        dict(name='stack-aliases-live-source', ss=0x7000, sp=0x0080),
        dict(name='source-output-exact-alias', es=0x7000),
        dict(name='source-output-paragraph-overlap', es=0x7001),
        dict(name='output-replaces-outer-ret', ss=0x4000, sp=0, mutable_ret=True),
        dict(name='output-replaces-saved-ds', ss=0x4000, sp=2, mutable_ds=True),
        dict(name='push-ds-replaces-source-selector', ss=0x2000, sp=0x1FE6),
        dict(name='provider-source-selector-after-es-read', effect='source-selector'),
        dict(name='provider-replaces-saved-ds', effect='saved-ds'),
        dict(name='changed-three-byte-child-ret', effect='child-ret', target=0x59D2),
        dict(name='changed-word-child-ret', effect='child-ret', target=0x59E2),
        dict(name='changed-wide-child-ret', effect='child-ret', target=0x5ABB),
        dict(name='zero-loop-count-wrap-then-child-stop', effect='child-ret',
             target=0x59D2, occurrence=2, first_count=0),
        dict(name='vga-source', source_segment=0xA000, vga=True),
        dict(name='vga-destination', es=0xA000, vga=True),
        dict(name='vga-stack', ss=0xA000, vga=True),
    ]
    base = dict(short=True, source='constructed', ds=0x2000, es=0x4000,
                source_segment=0x7000, ss=0x8000, sp=0x9000, flags=0x0AD7,
                effect=None, target=None, occurrence=1, provider=None)
    return [dict(base, seed=0x59BB00+n, **s) for n,s in enumerate(specs)]


def setup(case):
    memory = bytearray(random.Random(case['seed']).randbytes(SIZE))
    loaded = shared.relocated(IMAGE,shared.META['relocations'],0x1010)
    memory[0x10100:0x10100+len(loaded)] = loaded
    regs = dict(cs=0x1010, ip=ENTRY, ax=0xBEEF, bx=0xC17D, cx=0x4A93,
                dx=0xB271, si=0x1234, di=0xABCD, bp=0x79A3,
                ds=case['ds'], es=0x3510, ss=case['ss'],sp=case['sp'],flags=case['flags'])
    source = model.main_source() if case['source']=='asset' else random.Random(case['seed']^0xA713).randbytes(0x5270)
    for n,value in enumerate(source):put8(memory,case['source_segment'],n,value)
    put16(memory,regs['ds'],SOURCE_SELECTOR,case['source_segment'])
    put16(memory,regs['ds'],OUTPUT_SELECTOR,case['es'])
    device = None
    if case.get('vga'):
        device = shared.MinimapVga(case['seed'],read_map=0)
        device.seq[2] = 15
        for n in (0,1,3,4,5):device.gc[n] = 0
        device.gc[6] = 5;device.gc[8] = 255
        memory[shared.VGA_BASE:shared.VGA_END] = device.planes[0]
    put16(memory,regs['ss'],regs['sp'],0xD00D)
    return memory,regs,device


class Access(oracle.Access):
    event_limit = MAX_EVENTS
    def __init__(self,case,memory,regs,device,*,native=False):
        super().__init__(case,memory,regs,device)
        self.events = CompactEvents()
        self.native,self.pending = native,[]
        self.words,self.count_saves,self.call_words = {},[],[]
        self.target_occurrences = 0
    def queue(self,segment,offset,value,label):
        self.pending.append((segment,offset&0xFFFF,value,label))
    def instruction_complete(self):
        pending,self.pending = self.pending,[]
        for seg,off,value,label in pending:
            self.modify_word(seg,off,value)
            # The VGA stack is device-backed. Provider edits must reach the
            # live planes as well as their canonical read-map RAM mirror.
            if self.device is not None:
                address = physical(seg,off)
                for n,byte in enumerate((value&255,value>>8)):
                    at = (address+n)&MASK
                    if shared.VGA_BASE<=at<shared.VGA_END:
                        for plane in self.device.planes:plane[at-shared.VGA_BASE] = byte
            self.used.add(label)
    def access(self,kind,address,flags,mask=FLAGS,value=None):
        result = super().access(kind,address,flags,mask,value)
        case,ss,sp = self.case,self.regs['ss'],self.regs['sp']
        if kind=='write':
            # Only parent saves/CALL slots; child frames are deeper.
            for depth in (2,4,6):
                off = (sp-depth)&0xFFFF;start = physical(ss,off)
                if address==start:self.words[depth] = result
                elif address==((start+1)&MASK) and depth in self.words:
                    word = self.words.pop(depth)|(result<<8)
                    if depth==2 and case['effect']=='saved-ds' and 'saved-ds' not in self.used:
                        self.queue(ss,off,0x6200,'saved-ds')
                    if depth==4 and (word<=0x40 or word==0xFFFF):
                        self.count_saves.append(word)
                        if case['short']:
                            new = case.get('first_count',1) if len(self.count_saves)==1 else 1
                            self.queue(ss,off,new,'short-counts')
                    if (depth==6 or depth==4 and word==0x5ABB) and word in RETURN_ROWS:
                        self.call_words.append(word)
                        if case['effect']=='child-ret' and word==case['target']:
                            self.target_occurrences += 1
                            if self.target_occurrences==case['occurrence']:
                                self.queue(ss,off,0x1234,'child-ret')
        elif kind=='read' and case['effect']=='source-selector' and 'source-selector' not in self.used:
            dest = physical(self.regs['ds'],OUTPUT_SELECTOR)
            if address==((dest+1)&MASK):
                self.queue(self.regs['ds'],SOURCE_SELECTOR,0x6800,'source-selector')
        if self.native:self.instruction_complete()
        return result


def original(case,memory,regs,device,*,core):
    observers = []
    ref = oracle.original(case,bytearray(memory),dict(regs),copy.deepcopy(device),False,
        entry_flag_mask=FLAGS,main_instructions=MAIN_INS,main_call_returns=CALL_RETURNS,
        stop_offsets={RET:0} if core else {},instruction_limit=MAX_STEPS,
        access_factory=lambda c,m,r,d:observers.append(Access(c,m,r,d)) or observers[-1])
    raw = ref['status'];ref['raw_status'] = raw
    ref.update(child_entry=CALLS[raw-101]['child_entry'] if raw>=101 else 0,
               child_status=0 if raw>=101 else 0xFFFF,status=2 if raw>=101 else raw,
               count_saves=observers[0].count_saves,call_words=observers[0].call_words)
    return ref


def validate(case,memory,regs,ref,*,core):
    stopped = case['effect']=='child-ret'
    check(ref['status']==(2 if stopped else 0),case['name']+': wrong original stop')
    expected_used = ({'short-counts'} if case['short'] else set()) | ({case['effect']} if case['effect'] else set())
    check(ref['used']==expected_used,case['name']+': provider coverage')
    if stopped:
        check(ref['regs']['ip']==0x1234,case['name']+': changed child target')
        expected_sp = (regs['sp']-(2 if case['target']==0x5ABB else 4))&0xFFFF
        check(ref['regs']['sp']==expected_sp,case['name']+': child stop frame')
        if case.get('first_count')==0:
            check(ref['count_saves'][:2]==[18,0xFFFF],case['name']+': LOOP zero did not wrap')
        return 0
    check(ref['regs']['sp']==((regs['sp']+(0 if core else 2))&0xFFFF),case['name']+': outer SP')
    check(ref['regs']['ip']==(RET if core else get16(ref['memory'],regs['ss'],regs['sp'])),
          case['name']+': actual outer RET')
    if case['effect']=='saved-ds':check(ref['regs']['ds']==0x6200,case['name']+': live POP DS')
    if case.get('mutable_ds'):check(ref['regs']['ds']!=regs['ds'],case['name']+': DS alias did not change save')
    if case.get('mutable_ret') and not core:check(ref['regs']['ip']!=0xD00D,case['name']+': RET alias missing')
    if case['short']:
        check(len(ref['count_saves'])==15 and len(ref['call_words'])==16,
              case['name']+': constructed counter edits did not select one call per group')
    if not case.get('independent'):return 0
    source = bytes(memory[physical(case['source_segment'],n)] for n in range(0x5270))
    output,descriptors = model.expected(source,[1]*15 if case['short'] else None)
    base = physical(case['es'],0)
    actual = bytes(ref['memory'][(base+n)&MASK] for n in range(len(output)))
    check(actual==output,case['name']+': independent complete bank layout')
    check(ref['call_words']==[d['return_ip'] for d in descriptors],case['name']+': literal CALL sequence')
    source_end = descriptors[-1]['source_offset']+0x180
    check(ref['regs']['si']==source_end,case['name']+': source end')
    check(ref['regs']['es']==((case['es']+(len(output)>>4))&0xFFFF),case['name']+': flowing ES')
    check(ref['regs']['di']==(len(output)&15),case['name']+': final DI')
    return len(output)


class Native:
    def __init__(self,directory,mutation=0):
        self.lib = ct.CDLL(str(build(Path(directory)/f'entity-sprite-banks-m{mutation}.dll',mutation,'entity_sprite_banks')))
        self.core = self.lib.lmn_generate_entity_sprite_banks_core
        self.core.argtypes = [shared.MEM,ct.POINTER(shared.Call),ct.POINTER(shared.Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_generate_entity_sprite_banks_adapter
        self.adapter.argtypes = [shared.MEM,ct.POINTER(oracle.Regs),ct.POINTER(shared.Bus)]
        self.adapter.restype = ct.c_uint16
    def run(self,case,memory,regs,device,*,core):
        access = Access(case,memory,regs,device,native=True)
        def read(_c,_m,address,flags):
            try:return access.access('read',address,flags)
            except BaseException as error:shared.die(error)
        def write(_c,_m,address,value,flags):
            try:access.access('write',address,flags,value=value)
            except BaseException as error:shared.die(error)
        def out(*_args):shared.die('unexpected OUT in sprite-bank parent')
        callbacks = shared.READ(read),shared.WRITE(write),shared.OUT(out)
        bus = shared.Bus(None,*callbacks);ram = (ct.c_uint8*SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        child_entry,child_status = None,None
        if core:
            result = self.core(ram,ct.byref(shared.Call(*(regs[n] for n in shared.REGS))),ct.byref(bus))
            for role,reg in zip(shared.NAMES,shared.REGS):setattr(state,reg,getattr(result,role))
            state.ip = result.continuation;status = result.status
            child_entry,child_status = result.child_entry,result.child_status
        else:status = self.adapter(ram,ct.byref(state),ct.byref(bus))
        return dict(memory=bytes(memory),regs={n:getattr(state,n) for n in oracle.REG_NAMES},
            status=status,events=access.events,used=access.used,device=device,
            child_entry=child_entry,child_status=child_status,
            count_saves=access.count_saves,call_words=access.call_words)


def compare(native,case,*,core):
    memory,regs,device = setup(case)
    ref = original(case,memory,regs,device,core=core)
    checks = validate(case,memory,regs,ref,core=core)
    gc.collect()
    got = native.run(case,bytearray(memory),dict(regs),copy.deepcopy(device),core=core)
    shared.equal(got,ref,case['name'])
    if core:
        require(got['child_entry']==ref['child_entry'] and got['child_status']==ref['child_status'],
                case['name']+': child status provenance')
    require(got['count_saves']==ref['count_saves'] and got['call_words']==ref['call_words'],
            case['name']+': actual save/call sequence')
    return ref,checks


def branch_edges(ins):
    return {(pc,t) for pc,i in ins.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic=='loop'
            for t in ((i.operands[0].imm&0xFFFF),(pc+i.size)&0xFFFF)
            if i.mnemonic!='jmp' or t==(i.operands[0].imm&0xFFFF)}


def hashes():
    paths = set(wide.hashes()) | set(model.input_hashes())
    paths.update(('c/entity_sprite_banks.c','c/entity_sprite_banks.h',
                  'tests/entity_sprite_banks.py'))
    # Prose and C-progress fields do not feed this campaign. The generated
    # symbol header still pins every compiled address; the independent static
    # gate validates the ledger and exact maintained ASM. Do not weaken hashes
    # of executable inputs, instruction sources, helpers or native code.
    paths = {p for p in paths if not p.startswith('docs/') and p!='metadata/symbols.json'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def collect(ref,case,core,checks):
    return dict(case=case['name'],boundary='core' if core else 'adapter',status=ref['status'],
        sites=sorted(pc for scope,pc in ref['sites'] if scope=='main'),
        edges=sorted([a,b] for scope,a,b in ref['edges'] if scope=='main'),
        ordered_events=len(ref['events']),original_steps=ref['steps'],
        trace_storage_bytes=len(ref['events'].data)*ref['events'].data.itemsize,
        actual_child_calls=len(ref['call_words']),independent_bytes=checks,
        source_end=ref['regs']['si'],output_segment=ref['regs']['es'],output_offset=ref['regs']['di'])


def publish(path,before,rows,mutants=None):
    sites = {p for row in rows for p in row['sites']};edges = {tuple(e) for row in rows for e in row['edges']}
    check(sites==set(MAIN_INS),'missing integrated instruction sites')
    check(edges<=branch_edges(MAIN_INS),'unexpected integrated branch outcome')
    own_edges = edges & branch_edges(OWN_INS)
    check(own_edges==branch_edges(OWN_INS),'missing parent branch outcome')
    report = dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases()),comparison_count=len(rows),
        translated_code_bytes=262,instruction_sites=114,integrated_code_bytes=694,
        integrated_instruction_sites=len(MAIN_INS),executed_instruction_addresses=sorted(sites),
        parent_executed_instruction_addresses=sorted(sites&set(OWN_INS)),
        branch_edges=sorted([a,b] for a,b in edges),branch_edge_count=len(edges),
        integrated_static_branch_edge_count=len(branch_edges(MAIN_INS)),
        parent_branch_edge_count=len(own_edges),ordered_events=sum(r['ordered_events'] for r in rows),
        original_instruction_steps=sum(r['original_steps'] for r in rows),
        independent_output_bytes=sum(r['independent_bytes'] for r in rows),
        original_only=mutants is None,mutation_count=len(mutants or []),mutations=mutants or [],
        rows=rows,input_hashes=before,main_section_zero_bytes=len(model.main_source()),
        main_section_zero_sha256=sha(model.main_source()),
        limits=dict(timeout_seconds=WORKER_SECONDS,process_commit_mib=MEMORY_MIB,
                    original_instruction_limit=MAX_STEPS,bus_event_limit=MAX_EVENTS,
                    trace_bytes_per_event=20))
    write_json(path,report)
    print(f'PASS sprite-bank transform: {len(cases())} fixtures/{len(rows)} boundaries, '
          f'{len(sites)} integrated sites/{len(edges)} edges, '
          f'{report["ordered_events"]} events, {len(mutants or [])} mutants',flush=True)


def worker(directory,snapshot):
    before = json.loads(Path(snapshot).read_text());check(before==hashes(),'input snapshot differs')
    native = Native(directory);rows = []
    for case in cases():
        for core in (True,False):
            ref,checks = compare(native,case,core=core);rows.append(collect(ref,case,core,checks))
            del ref;gc.collect()
        print('CHECKED native '+case['name'],flush=True)
    witnesses = [(1,'push-ds-replaces-source-selector',True),(2,'one-call-per-group',True),
        (3,'one-call-per-group',True),(4,'one-call-per-group',True),
        (5,'changed-three-byte-child-ret',True),(6,'one-call-per-group',True),
        (7,'provider-replaces-saved-ds',True),(8,'stack-offset-one',True),
        (9,'output-replaces-outer-ret',False),(10,'one-call-per-group',False)]
    by_name = {c['name']:c for c in cases()};mutants = []
    for number,name,core in witnesses:
        try:compare(Native(directory,number),by_name[name],core=core)
        except shared.Mismatch as error:
            mutants.append(dict(mutation=number,case=name,core=core,completed=True,mismatch=str(error)))
        else:raise shared.OracleFailure(f'mutation {number} survived')
        gc.collect()
    check(before==hashes(),'inputs changed during native campaign')
    publish(REPORT,before,rows,mutants)


def original_campaign():
    before,rows = hashes(),[]
    for case in cases():
        memory,regs,device = setup(case)
        for core in (True,False):
            ref = original(case,memory,regs,device,core=core)
            rows.append(collect(ref,case,core,validate(case,memory,regs,ref,core=core)))
            del ref;gc.collect()
        print('CHECKED original '+case['name'],flush=True)
    check(before==hashes(),'inputs changed during original campaign')
    publish(ORIGINAL_REPORT,before,rows)


def main():
    args = sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(args[1],args[2]);return
    if args==['--original-worker']:original_campaign();return
    if args not in ([],['--original-only']):raise SystemExit('usage: entity_sprite_banks.py [--original-only]')
    BUILD.mkdir(exist_ok=True)
    if args:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,
                    timeout=WORKER_SECONDS,memory_mib=MEMORY_MIB,check=True);return
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-sprite-banks-',parent=BUILD) as directory:
        snapshot = Path(directory)/'inputs.json';snapshot.write_text(json.dumps(hashes()))
        run_bounded([sys.executable,__file__,'--worker',directory,str(snapshot)],cwd=ROOT,
                    timeout=WORKER_SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()
