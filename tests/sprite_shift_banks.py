"""Bounded original/native checks for the 5B11 three-byte sprite banks."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
from functools import reduce
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import sprite_bank as shared
import entity_sprite_aligned as aligned

oracle, layout = shared.oracle, shared.layout
IMAGE, SIZE, MASK, FLAGS = shared.IMAGE, shared.SIZE, shared.MASK, shared.FLAGS
ENTRY, RET, END = 0x5B11, 0x5BAF, 0x5BB0
MAX_STEPS, MAX_EVENTS = 1_000_000, 180_000
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {i.address:i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
REPORT = BUILD/'sprite-shift-banks-differential.json'
ORIGINAL_REPORT = BUILD/'sprite-shift-banks-original-differential.json'
check, require, physical = shared.check, shared.require, shared.physical
put8, put16, get16 = shared.put8, shared.put16, shared.get16


def cases():
    specs = [dict(name=f'normal-{dx:04x}', dx=dx, independent=True)
             for dx in (0x020A, 0x020C, 0x020D, 0x030A, 0x030D, 0x030E, 0x0310, 0x040E)]
    specs += [
        dict(name='zero-dh-is-256-planes', dx=0x0001, zero_model=True),
        dict(name='zero-dl-is-256-rows', dx=0x0100, zero_model=True),
        dict(name='df-does-not-reverse-byte-operands', flags=0x0ED7, independent=True),
        dict(name='exact-source-destination-overlap', ds=0x6000, si=0x0200),
        dict(name='forward-byte-overlap', ds=0x6000, si=0x0200, di=0x0201),
        dict(name='backward-byte-overlap', ds=0x6000, si=0x0200, di=0x01FF),
        dict(name='source-byte-ea-wrap-ffff', si=0xFFFF, dx=0x0101, wrap_model=True),
        dict(name='destination-byte-ea-wrap-ffff', di=0xFFFF, dx=0x0101),
        dict(name='mask-byte-ea-wrap-ffff', di=0xFFFF, dx=0x0102),
        dict(name='segment-fold-wrap', es=0xFFF0, dx=0x0101),
        dict(name='stack-offset-wrap', sp=1, dx=0x0101),
        dict(name='outer-ret-offset-ffff', sp=0xFFFF, dx=0x0101),
        dict(name='physical-outer-ret-fffff', ss=0xFFFF, sp=0x000F, dx=0x0101),
        dict(name='physical-source-byte-fffff', ds=0xFFFF, si=0x000F, dx=0x0101),
        dict(name='output-overwrites-outer-ret', es=0x5000, di=0x9000, dx=0x0101),
        dict(name='output-overwrites-saved-si', es=0x5000, di=0x8FFC, dx=0x0101,
             source_pair=(0x01, 0x07)),
        dict(name='provider-replaces-bank-si', provider='bank-si'),
        dict(name='provider-shortens-mask-count', provider='mask-cx'),
        dict(name='provider-changes-restored-dx', provider='mask-dx'),
        dict(name='provider-shortens-outer-shifts', provider='bank-cx'),
        dict(name='provider-wraps-outer-shift-count', dx=0x0101, provider='bank-cx-wrap'),
        dict(name='provider-drives-shift-count-255', dx=0x0101, provider='bank-cx-255'),
        dict(name='provider-shortens-plane-count', provider='plane-cx'),
        dict(name='provider-replaces-mask-si', provider='mask-si'),
        dict(name='vga-destination', es=0xA000, dx=0x0203, vga=True),
        dict(name='vga-source', ds=0xA000, dx=0x0203, vga=True),
        dict(name='vga-stack', ss=0xA000, dx=0x0101, vga=True),
    ]
    for final in (0x000F, 0x0010, 0x7FFF, 0x8000, 0xFFFF):
        specs.append(dict(name=f'signed-fold-final-{final:04x}', dx=0x0101,
                          di=(final-48)&0xFFFF, expected_final_di=final))
    base = dict(dx=0x0203, ds=0x7000, es=0x6000, ss=0x5000, sp=0x9000,
                si=0x0100, di=0x0200, flags=0x0AD7, provider=None)
    return [dict(base, seed=0x5B1100+index, **spec) for index,spec in enumerate(specs)]


def setup(case):
    memory, regs, device = shared.setup(case)
    regs['ip'] = ENTRY
    if case.get('source_pair'):
        for n,value in enumerate(case['source_pair']):
            put8(memory, regs['ds'], regs['si']+n, value)
    if case.get('wrap_model'):
        put8(memory, regs['ds'], 0xFFFF, 0xC3)
        put8(memory, regs['ds'], 0, 0x5A)
        # Deliberately differs from the explicit [SI+1] byte.
        memory[(physical(regs['ds'], 0xFFFF)+1)&MASK] = 0xE7
    return memory, regs, device


class Access(oracle.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native, self.pending, self.low, self.occurrences = native, [], None, 0

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for offset,value,label in pending:
            self.modify_word(self.regs['ss'], offset, value)
            self.used.add(label)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        observed = super().access(kind, address, flags, mask, value)
        label = self.case.get('provider')
        if kind == 'write' and label and label not in self.used:
            # Exact saved words relative to entry SP, including nested saves.
            distance, occurrence, replacement = {
                'bank-si': (4, 1, 0xBEEF),
                'mask-cx': (8, 1, 0x0100),
                'mask-dx': (10, 1, 0x0101),
                'bank-cx': (2, 1, 0xA507),
                'bank-cx-wrap': (2, 1, 0x12FF),
                'bank-cx-255': (2, 1, 0x12FE),
                'plane-cx': (6, 1, 0x0100),
                'mask-si': (6, (self.case['dx']>>8)+1, 0x0500),
            }[label]
            offset = (self.regs['sp']-distance)&0xFFFF
            start = physical(self.regs['ss'], offset)
            if address == start:
                self.low = observed
            if address == ((start+1)&MASK) and self.low is not None:
                self.occurrences += 1
                if self.occurrences == occurrence:
                    self.pending.append((offset, replacement, label))
                self.low = None
                if self.native:
                    self.instruction_complete()
        return observed


def original(case, memory, regs, device, *, core):
    return oracle.original(case, bytearray(memory), dict(regs), copy.deepcopy(device),
        core, entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        access_factory=lambda c,m,r,d:Access(c,m,r,d), instruction_limit=MAX_STEPS)


def independent(case, initial, regs, ref):
    if case.get('independent') or case.get('zero_model') or case.get('wrap_model'):
        dh, dl = case['dx']>>8, case['dx']&255
        planes, rows = dh or 256, dl or 256
        # Explicit byte operand addressing; this is a separate 24-bit equation.
        source = bytes(initial[physical(regs['ds'], regs['si']+n)]
                       for n in range(2*planes*rows))
        banks = layout.expected_5b11(source, (planes<<8)|rows) if dh and dl else None
        if banks is None:
            banks = []
            for shift in range(8):
                body = []
                for p in range(planes):
                    plane = bytearray()
                    for y in range(rows):
                        n = 2*(p*rows+y)
                        word = (source[n]<<16)|(source[n+1]<<8)
                        plane.extend((word>>shift).to_bytes(3, 'big'))
                    body.append(bytes(plane))
                mask = bytes(reduce(int.__or__, values)
                             for values in zip(*body))
                banks.append(b''.join(body)+mask)
        output = b''.join(banks)
        observed = bytes(ref['memory'][physical(regs['es'], regs['di']+n)]
                         for n in range(len(output)))
        check(observed == output, case['name']+': independent 24-bit banks differ')
        return len(output)
    return 0


def validate(case, initial, regs, ref, *, core):
    check(ref['status'] == 0, case['name']+': unexpected original stop')
    check(ref['used'] == ({case['provider']} if case.get('provider') else set()),
          case['name']+': provider effects differ')
    check(ref['regs']['ip'] == (RET if core else get16(ref['memory'], regs['ss'], regs['sp'])),
          case['name']+': live caller word differs')
    check(ref['regs']['sp'] == ((regs['sp']+(0 if core else 2))&0xFFFF),
          case['name']+': unbalanced stack')
    check(ref['regs']['flags']&0x400 == regs['flags']&0x400, case['name']+': DF changed')
    if 'expected_final_di' in case:
        raw = case['expected_final_di'];fold = 0x10 <= raw < 0x8000
        check(ref['regs']['di'] == (raw&15 if fold else raw), case['name']+': signed DI')
        check(ref['regs']['es'] == ((regs['es']+(raw>>4))&0xFFFF if fold else regs['es']),
              case['name']+': signed ES')
        check(ref['regs']['cx'] == (regs['es'] if fold else (regs['cx']&0xFF00)|8),
              case['name']+': final CX')
    return independent(case, initial, regs, ref)


class Native:
    def __init__(self, directory, mutation=0):
        self.lib = ct.CDLL(str(build(Path(directory)/f'sprite-shifts-m{mutation}.dll',
                                     mutation, 'sprite_shift_banks')))
        self.core = self.lib.lmn_generate_sprite_shift_banks3_core
        self.core.argtypes = [shared.MEM, ct.POINTER(shared.Call), ct.POINTER(shared.Bus)]
        self.core.restype = shared.Result
        self.adapter = self.lib.lmn_generate_sprite_shift_banks3_adapter
        self.adapter.argtypes = [shared.MEM, ct.POINTER(oracle.Regs), ct.POINTER(shared.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)
        def read(_c, _m, address, flags):
            try:return access.access('read', address, flags)
            except BaseException as error:shared.die(error)
        def write(_c, _m, address, value, flags):
            try:access.access('write', address, flags, value=value)
            except BaseException as error:shared.die(error)
        def out(*_args):shared.die('unexpected OUT in three-byte bank generator')
        callbacks = shared.READ(read), shared.WRITE(write), shared.OUT(out)
        bus = shared.Bus(None, *callbacks);ram = (ct.c_uint8*SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        if core:
            result = self.core(ram, ct.byref(shared.Call(*(regs[n] for n in shared.REGS))), ct.byref(bus))
            for role,reg in zip(shared.NAMES, shared.REGS):setattr(state, reg, getattr(result, role))
            state.ip = result.continuation;status = result.status
        else:status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory), regs={n:getattr(state,n) for n in oracle.REG_NAMES},
                    status=status, events=access.events, used=access.used, device=device)


def compare(native, case, *, core):
    memory, regs, device = setup(case)
    ref = original(case, memory, regs, device, core=core)
    checks = validate(case, memory, regs, ref, core=core)
    got = native.run(case, bytearray(memory), dict(regs), copy.deepcopy(device), core=core)
    shared.equal(got, ref, case['name']+(' core' if core else ' adapter'))
    return ref, checks


def handoffs(native=None, directory=None):
    """Feed all eight actual banks into the native aligned drawing callback.

    Producer and consumers share canonical RAM. Explicit constructed CALL
    frames connect the data contract without claiming execution of 59BB.
    """
    case = next(c for c in cases() if c['name']=='normal-020a')
    memory, regs, _ = setup(case)
    device = shared.MinimapVga(case['seed'], read_map=0)
    device.seq[2] = 15
    for n in (0,1,3,4,5):device.gc[n] = 0
    device.gc[6] = 5;device.gc[8] = 255
    memory[shared.VGA_BASE:shared.VGA_END] = device.planes[0]
    ref = original(case, memory, regs, device, core=False)
    checks = validate(case, memory, regs, ref, core=False)
    actual_memory = bytearray(memory)
    child = aligned.Native(directory) if native is not None else None
    if native is not None:
        actual = native.run(case, actual_memory, dict(regs), copy.deepcopy(device), core=False)
        shared.equal(actual, ref, 'eight-bank handoff producer')
    start = physical(regs['es'], regs['di']);banks = ref['memory'][start:start+720]
    check(len(banks)==720 and checks==720, 'handoff producer layout')
    producer_events, producer_steps = len(ref['events']), ref['steps']
    ref_memory = bytearray(ref['memory']);ref_state = dict(ref['regs']);ref_device = ref['device']
    native_state = dict(actual['regs']) if native is not None else None
    native_device = actual['device'] if native is not None else None
    rows = []
    for index in range(8):
        ccase = dict(name=f'native-bank-{index}', provider=False)
        offset = regs['di']+90*index
        def prepare(ram, state):
            state.update(ip=aligned.ENTRY, cx=regs['es'], si=offset, bx=offset+60,
                         di=0x3000+index*0x0200, sp=(state['sp']-2)&0xFFFF)
            put16(ram, state['ss'], state['sp'], 0xD00D)
        prepare(ref_memory, ref_state)
        child_ref = aligned.run_original(ccase, ref_memory, ref_state, ref_device, core=False)
        check(child_ref['status']==0, ccase['name']+': child original did not return')
        check(child_ref['memory'][start:start+720]==banks, ccase['name']+': original bank changed')
        if child is not None:
            prepare(actual_memory, native_state)
            got = child.run(ccase, actual_memory, native_state, native_device, core=False)
            shared.equal(got, child_ref, ccase['name'])
            require(actual_memory[start:start+720]==banks, ccase['name']+': native bank changed')
            native_state, native_device = dict(got['regs']), got['device']
        rows.append(dict(bank_index=index, bank_bytes=90,
            bank_sha256=sha(banks[index*90:(index+1)*90]),
            consumer_events=len(child_ref['events']), consumer_steps=child_ref['steps'],
            consumer_sites=sorted(pc for scope,pc in child_ref['sites'] if scope=='main')))
        ref_memory = bytearray(child_ref['memory'])
        ref_state, ref_device = dict(child_ref['regs']), child_ref['device']
    return dict(bank_bytes=720, bank_sha256=sha(banks),
                producer_events=producer_events, producer_steps=producer_steps,
                native_compared=native is not None,
                native_phase_comparisons=9 if native is not None else 0, banks=rows)


def edges():
    return {(pc,target) for pc,i in OWN_INS.items() if i.group(capstone.CS_GRP_JUMP)
            for target in ((i.operands[0].imm&0xFFFF), (pc+i.size)&0xFFFF)
            if i.mnemonic != 'jmp' or target == (i.operands[0].imm&0xFFFF)}


def hashes():
    paths = set(shared.hashes()) | set(aligned.input_hashes())
    paths.update(('c/sprite_shift_banks.c', 'c/sprite_shift_banks.h',
                  'tests/sprite_shift_banks.py', 'docs/sprite-shift-banks.md'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def collect(ref, case, core, count):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
        sites=sorted(pc for scope,pc in ref['sites'] if scope=='main'),
        edges=sorted([a,b] for scope,a,b in ref['edges'] if scope=='main'),
        events=len(ref['events']), steps=ref['steps'], independent_bytes=count)


def original_campaign():
    before = hashes();rows = []
    for case in cases():
        memory,regs,device = setup(case)
        for core in (True,False):
            ref = original(case,memory,regs,device,core=core)
            rows.append(collect(ref,case,core,validate(case,memory,regs,ref,core=core)))
        gc.collect()
    check(before == hashes(), 'inputs changed during original campaign')
    hands = handoffs()
    check(before == hashes(), 'inputs changed during original handoffs')
    return before, rows, hands


def publish(path, before, rows, hands, mutants=None):
    sites = {pc for row in rows for pc in row['sites']}
    branches = {tuple(e) for row in rows for e in row['edges']}
    check(sites == OWN_SITES, 'missing original instruction sites')
    check(branches == edges(), f'missing branch outcomes: {edges()-branches}; extra {branches-edges()}')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(cases()),
        comparison_count=len(rows), translated_code_bytes=159, instruction_sites=74,
        executed_instruction_addresses=sorted(sites), branch_edges=sorted([a,b] for a,b in branches),
        branch_edge_count=len(branches), ordered_events=sum(r['events'] for r in rows),
        original_instruction_steps=sum(r['steps'] for r in rows),
        independent_output_bytes=sum(r['independent_bytes'] for r in rows),
        original_only=mutants is None, mutation_count=len(mutants or []), mutations=mutants or [],
        rows=rows, input_hashes=before, producer_consumer_handoff=hands,
        limits=dict(timeout_seconds=420, process_commit_mib=384,
                    original_instruction_limit=MAX_STEPS, bus_event_limit=MAX_EVENTS))
    write_json(path, report)
    print(f'PASS three-byte banks: {len(cases())} fixtures/{len(rows)} boundaries, '
          f'{len(sites)} sites/{len(branches)} edges, {report["ordered_events"]} events, '
          f'{len(mutants or [])} mutants', flush=True)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text());check(before == hashes(), 'input snapshot differs')
    native = Native(directory);rows = []
    for case in cases():
        for core in (True,False):
            ref,count = compare(native,case,core=core);rows.append(collect(ref,case,core,count))
        gc.collect()
    witnesses = [(1,'zero-dh-is-256-planes',True), (2,'zero-dl-is-256-rows',True),
        (3,'normal-020a',True), (4,'normal-020a',True),
        (5,'source-byte-ea-wrap-ffff',True), (6,'signed-fold-final-8000',True),
        (7,'provider-replaces-bank-si',True), (8,'provider-shortens-mask-count',True),
        (9,'output-overwrites-outer-ret',False), (10,'normal-020a',False)]
    by_name = {c['name']:c for c in cases()};mutants = []
    for number,name,core in witnesses:
        mutant = Native(directory,number)
        try:compare(mutant,by_name[name],core=core)
        except shared.Mismatch as error:
            mutants.append(dict(mutation=number,case=name,core=core,completed=True,mismatch=str(error)))
        else:raise shared.OracleFailure(f'mutation {number} survived')
        gc.collect()
    hands = handoffs(native, directory)
    check(before == hashes(), 'inputs changed during native campaign')
    publish(REPORT,before,rows,hands,mutants)


def main():
    args = sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(args[1],args[2]);return
    if args==['--original-worker']:
        before,rows,hands = original_campaign();publish(ORIGINAL_REPORT,before,rows,hands);return
    if args not in ([],['--original-only']):raise SystemExit('usage: sprite_shift_banks.py [--original-only]')
    BUILD.mkdir(exist_ok=True)
    if args:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,
                    timeout=420,memory_mib=384,check=True);return
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='sprite-shifts-',parent=BUILD) as directory:
        snapshot = Path(directory)/'inputs.json';snapshot.write_text(json.dumps(hashes()))
        run_bounded([sys.executable,__file__,'--worker',directory,str(snapshot)],cwd=ROOT,
                    timeout=420,memory_mib=384,check=True)


if __name__=='__main__':main()
