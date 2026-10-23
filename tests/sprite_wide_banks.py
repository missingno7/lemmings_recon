"""Bounded original/native checks for the five-byte 5C06 sprite banks."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_sprite_wide as wide
import sprite_bank as bus_shared
import sprite_shift_banks as shared

oracle, layout = shared.oracle, shared.layout
IMAGE, SIZE, MASK, FLAGS = shared.IMAGE, shared.SIZE, shared.MASK, shared.FLAGS
ENTRY, RET, END = 0x5C06, 0x5CC0, 0x5CC1
MAX_STEPS, MAX_EVENTS = 1_000_000, 180_000
REPORT = BUILD / 'sprite-wide-banks-differential.json'
ORIGINAL_REPORT = BUILD / 'sprite-wide-banks-original-differential.json'
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
check, require, physical = shared.check, shared.require, shared.physical
put8, put16, get16 = shared.put8, shared.put16, shared.get16


def cases():
    specs = [
        dict(name='ordinary-eight-banks', independent=True),
        dict(name='ordinary-carry-rich-source', independent=True, seed_add=0x101),
        dict(name='df-set-does-not-reverse-byte-operands', flags=0x0ED7),
        dict(name='vga-source-segment', ds=0xA000, vga=True),
        dict(name='vga-destination-segment', es=0xA000, vga=True),
        dict(name='vga-stack-segment', ss=0xA000, vga=True),
        dict(name='exact-source-output-overlap', ds=0x6000, si=0x0200, di=0x0200),
        dict(name='forward-byte-overlap', ds=0x6000, si=0x0200, di=0x0201),
        dict(name='backward-byte-overlap', ds=0x6000, si=0x0200, di=0x01FF),
        dict(name='source-ea-wrap-ffff', ds=0x6000, si=0xFFFF,
             source_pattern=True, source_ea_wrap=True),
        dict(name='source-physical-fffff', ds=0xFFFF, si=0x000F,
             source_pattern=True),
        dict(name='output-offset-ffff-crossing-0', di=0xFFFB),
        dict(name='output-offset-ffff-crossing-1', di=0xFFFC),
        dict(name='output-offset-ffff-crossing-2', di=0xFFFD),
        dict(name='output-offset-ffff-crossing-3', di=0xFFFE),
        dict(name='output-offset-ffff-crossing-4', di=0xFFFF),
        dict(name='stack-offset-wrap-one', sp=0x0001),
        dict(name='stack-offset-wrap-ffff', sp=0xFFFF),
        dict(name='physical-stack-top-wrap', ss=0xFFFF, sp=0x000F),
        dict(name='output-overwrites-live-saved-di', es=0x5000, di=0x8FFA),
        dict(name='output-overwrites-actual-outer-ret', es=0x5000, di=0x9000),
        dict(name='provider-replaces-saved-di-before-5c53', provider='saved-di'),
        dict(name='provider-replaces-per-bank-saved-si', provider='saved-si'),
        dict(name='provider-shortens-first-plane', provider='plane-cx'),
        dict(name='provider-mask-cx-fourth-sp-8-write', provider='mask-cx'),
        dict(name='provider-shortens-outer-banks', provider='outer-cx'),
        dict(name='provider-replaces-mask-si-second-sp-6-write', provider='mask-si'),
        dict(name='provider-plane-cx-shift-255', provider='plane-cx-255'),
        dict(name='signed-fold-below-0010', final_di=0x000F),
        dict(name='signed-fold-at-0010', final_di=0x0010),
        dict(name='signed-fold-at-7fff', final_di=0x7FFF),
        dict(name='signed-fold-negative-8000', final_di=0x8000),
        dict(name='signed-fold-negative-ffff', final_di=0xFFFF),
    ]
    base = dict(dx=0xD39B, ds=0x7000, es=0x6000, ss=0x5000, sp=0x9000,
                si=0x0100, di=0x0200, cx=0xA731, ax=0xBEEF, bx=0xC17D,
                bp=0x79A3, flags=0x0AD7, provider=None, seed=0x5C0600)
    result = []
    for index, spec in enumerate(specs):
        row = dict(base)
        row['seed'] += index + spec.pop('seed_add', 0)
        row.update(spec)
        if 'final_di' in row:
            row['di'] = (row['final_di'] - 8 * 4 * 32 * 5) & 0xFFFF
        result.append(row)
    return result


def setup(case):
    memory, regs, device = shared.setup(case)
    regs.update(ip=ENTRY, cx=case.get('cx', regs['cx']))
    if case.get('source_pattern'):
        # Seed through explicit segmented byte operands, including SI wrap.
        for n in range(3 * 32 * 4):
            offset = (regs['si'] + n) & 0xFFFF
            value = (0x39 + n * 73 + (n >> 2) * 19 + case['seed']) & 0xFF
            put8(memory, regs['ds'], offset, value)
    if case.get('source_ea_wrap'):
        # The linear byte after DS:FFFF is deliberately different from DS:0000.
        decoy = (physical(regs['ds'], regs['si']) + 1) & MASK
        memory[decoy] = memory[decoy] ^ 0xA7
    put16(memory, regs['ss'], regs['sp'], 0xD00D)
    if device is not None and regs['ss'] == 0xA000:
        # The setup RET word is written into canonical VGA RAM directly.
        device.planes[0][:] = memory[bus_shared.VGA_BASE:bus_shared.VGA_END]
    return memory, regs, device


class Access(oracle.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []
        self.low = None
        self.occurrences = 0

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for offset, value, label in pending:
            self.modify_word(self.regs['ss'], offset, value)
            self.used.add(label)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        observed = super().access(kind, address, flags, mask, value)
        label = self.case.get('provider')
        if kind == 'write' and label and label not in self.used:
            distance, occurrence, replacement = {
                'saved-di': (6, 1, 0x0520),
                'saved-si': (4, 1, 0x0340),
                'plane-cx': (8, 1, 0x0100),
                'plane-cx-255': (8, 1, 0x02FF),
                # The first three SP-8 writes are plane counters. The fourth
                # is the first mask-row CX save at 5C57.
                'mask-cx': (8, 4, 0x0100),
                'outer-cx': (2, 1, 0x0007),
                # SP-6 is saved DI at 5C0A, then the mask cursor at 5C56.
                'mask-si': (6, 2, 0x0520),
            }[label]
            offset = (self.regs['sp'] - distance) & 0xFFFF
            start = physical(self.regs['ss'], offset)
            if address == start:
                self.low = observed
            elif address == ((start + 1) & MASK) and self.low is not None:
                self.occurrences += 1
                if self.occurrences == occurrence:
                    self.pending.append((offset, replacement, label))
                self.low = None
                if self.native:
                    self.instruction_complete()
        return observed


def original(case, memory, regs, device, *, core):
    return oracle.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        access_factory=lambda c, m, r, d: Access(c, m, r, d),
        instruction_limit=MAX_STEPS)


def independent(case, initial, regs, ref):
    if not case.get('independent'):
        return 0
    source = bytes(initial[physical(regs['ds'], (regs['si'] + n) & 0xFFFF)]
                   for n in range(3 * 32 * 4))
    expected = b''.join(layout.expected_5c06(source))
    observed = bytes(ref['memory'][physical(regs['es'], (regs['di'] + n) & 0xFFFF)]
                     for n in range(len(expected)))
    check(observed == expected, case['name'] + ': independent 40-bit banks differ')
    return len(expected)


def validate(case, initial, regs, ref, *, core):
    check(ref['status'] == 0, case['name'] + ': original did not reach READY')
    check(ref['used'] == ({case['provider']} if case.get('provider') else set()),
          case['name'] + ': provider transition differs')
    if core:
        check(ref['regs']['ip'] == RET, case['name'] + ': core did not stop before RET')
        check(ref['regs']['sp'] == regs['sp'],
              case['name'] + ': core did not restore the live entry stack offset')
    else:
        ret_word = get16(ref['memory'], ref['regs']['ss'], regs['sp'])
        check(ref['regs']['ip'] == ret_word,
              case['name'] + ': adapter did not consume the live outer RET')
        check(ref['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
              case['name'] + ': actual RET did not advance SP')
    check((ref['regs']['flags'] & 0x0400) == (regs['flags'] & 0x0400),
          case['name'] + ': DF changed')
    if 'final_di' in case:
        raw = case['final_di']
        folded = 0x0010 <= raw < 0x8000
        check(ref['regs']['di'] == ((raw & 0x000F) if folded else raw),
              case['name'] + ': signed final DI differs')
        expected_es = ((regs['es'] + (raw >> 4)) & 0xFFFF) if folded else regs['es']
        check(ref['regs']['es'] == expected_es,
              case['name'] + ': signed final ES differs')
        expected_cx = regs['es'] if folded else ((regs['cx'] & 0xFF00) | 8)
        check(ref['regs']['cx'] == expected_cx,
              case['name'] + ': final CX ownership differs')
    if case.get('name') == 'output-overwrites-actual-outer-ret':
        check(ref['regs']['ip'] != 0xD00D,
              'output alias did not replace the actual outer return word')
    return independent(case, initial, regs, ref)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'sprite-wide-banks-m{mutation}.dll',
                     mutation, 'sprite_wide_banks')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_generate_sprite_shift_banks5_core
        self.core.argtypes = [bus_shared.MEM, ct.POINTER(bus_shared.Call),
                              ct.POINTER(bus_shared.Bus)]
        self.core.restype = bus_shared.Result
        self.adapter = self.lib.lmn_generate_sprite_shift_banks5_adapter
        self.adapter.argtypes = [bus_shared.MEM, ct.POINTER(oracle.Regs),
                                 ct.POINTER(bus_shared.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)

        def read(_context, _memory, address, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    bus_shared.die('native callback event budget exhausted')
                return access.access('read', address, flags)
            except BaseException as error:
                bus_shared.die(error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    bus_shared.die('native callback event budget exhausted')
                access.access('write', address, flags, value=value)
            except BaseException as error:
                bus_shared.die(error)

        def out(*_args):
            bus_shared.die('unexpected OUT from 5C06 bank generator')

        callbacks = bus_shared.READ(read), bus_shared.WRITE(write), bus_shared.OUT(out)
        bus = bus_shared.Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        if core:
            call = bus_shared.Call(*(regs[name] for name in bus_shared.REGS))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for role, reg in zip(bus_shared.NAMES, bus_shared.REGS):
                setattr(state, reg, getattr(result, role))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in oracle.REG_NAMES},
                    status=status, events=access.events, used=access.used,
                    device=device)


def compare(native, case, *, core):
    memory, regs, device = setup(case)
    ref = original(case, memory, regs, device, core=core)
    checks = validate(case, memory, regs, ref, core=core)
    got = native.run(case, bytearray(memory), dict(regs), copy.deepcopy(device), core=core)
    bus_shared.equal(got, ref, case['name'] + (' core' if core else ' adapter'))
    return ref, checks


def edges():
    out = set()
    for pc, ins in OWN_INS.items():
        if not ins.group(capstone.CS_GRP_JUMP):
            continue
        target = ins.operands[0].imm & 0xFFFF
        out.add((pc, target))
        if ins.mnemonic.lower() != 'jmp':
            out.add((pc, (pc + ins.size) & 0xFFFF))
    return out


def hashes():
    paths = set(shared.hashes()) | set(wide.input_hashes())
    paths.update(('c/sprite_wide_banks.c', 'c/sprite_wide_banks.h',
                  'tests/sprite_wide_banks.py'))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def collect(ref, case, core, checked):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(pc for scope, pc in ref['sites'] if scope == 'main'),
                edges=sorted([a, b] for scope, a, b in ref['edges'] if scope == 'main'),
                events=len(ref['events']), steps=ref['steps'],
                independent_bytes=checked)


def original_campaign():
    before, rows = hashes(), []
    for case in cases():
        memory, regs, device = setup(case)
        for core in (True, False):
            ref = original(case, memory, regs, device, core=core)
            checked = validate(case, memory, regs, ref, core=core)
            rows.append(collect(ref, case, core, checked))
        gc.collect()
    hands = handoffs()
    check(before == hashes(), 'inputs changed during original campaign')
    return before, rows, hands


def handoffs(native=None, directory=None):
    """Feed the eight actual native banks to the existing VGA wide consumer.

    The producer and consumer use one canonical 1 MiB RAM image. Each child
    invocation gets an explicit near-CALL word, and consumer sites/events are
    recorded separately from the 5C06 leaf.
    """
    case = next(row for row in cases() if row['name'] == 'ordinary-eight-banks')
    memory, regs, _device = setup(case)
    native_memory = bytearray(memory) if native is not None else None
    producer_ref = original(case, memory, regs, None, core=False)
    validate(case, memory, regs, producer_ref, core=False)
    producer_native = None
    if native is not None:
        producer_native = native.run(case, native_memory, dict(regs), None, core=False)
        bus_shared.equal(producer_native, producer_ref, 'wide handoff producer')

    source_bytes = bytes(memory[physical(regs['ds'], (regs['si'] + n) & 0xFFFF)]
                         for n in range(3 * 32 * 4))
    output_start = physical(regs['es'], regs['di'])
    output = producer_ref['memory'][output_start:output_start + 8 * 640]
    check(len(output) == 5120, 'wide handoff producer did not emit 5120 bytes')

    def witness(memory_after):
        descriptors = tuple(layout.DataBank(
            index=index, shift=index, output_offset=index * 640,
            output_length=640, plane_offset=index * 640, plane_length=480,
            plane_count=3, plane_stride=160, mask_offset=index * 640 + 480,
            mask_length=160) for index in range(8))
        return layout.ProducerWitness(
            entry=ENTRY, dx=regs['dx'], source_segment=regs['ds'],
            source_offset=regs['si'], source_bytes=source_bytes,
            destination_segment=regs['es'], destination_offset=regs['di'],
            output_bytes=output, banks=descriptors, memory=bytearray(memory_after),
            registers=dict(producer_ref['regs']),
            sites=frozenset(pc for scope, pc in producer_ref['sites'] if scope == 'main'),
            edges=frozenset((a, b) for scope, a, b in producer_ref['edges']
                            if scope == 'main'),
            steps=producer_ref['steps'], events=tuple(producer_ref['events']),
            event_count=len(producer_ref['events']))

    ref_witness = witness(producer_ref['memory'])
    first_case = next(row for row in wide.make_cases(ref_witness)
                      if row['name'] == 'actual-5c06-shift-bank-0')
    video_memory, _video_regs, initial_device = wide.setup(first_case, ref_witness)
    video_bytes = video_memory[wide.VGA_BASE:wide.VGA_END]
    ref_memory = bytearray(producer_ref['memory'])
    ref_memory[wide.VGA_BASE:wide.VGA_END] = video_bytes
    wide_native = None
    if native is not None:
        native_memory[wide.VGA_BASE:wide.VGA_END] = video_bytes
        wide_native = wide.Native(directory)

    ref_state = dict(producer_ref['regs'])
    native_state = dict(producer_native['regs']) if producer_native else None
    ref_device = copy.deepcopy(initial_device)
    native_device = copy.deepcopy(initial_device) if native is not None else None
    ref_rows, consumer_sites, consumer_edges = [], set(), set()
    consumer_events = consumer_steps = 0
    bank_hash = sha(output)
    for index, descriptor in enumerate(ref_witness.banks):
        consumer_case = dict(first_case)
        consumer_case.update(name=f'wide-consumer-bank-{index}', producer_bank=index,
                             di=0x3000, provider=None)

        def prepare(ram, state):
            state.update(cs=wide.LOAD, ip=wide.ENTRY,
                         cx=ref_witness.destination_segment,
                         si=ref_witness.destination_offset + descriptor.plane_offset,
                         bx=ref_witness.destination_offset + descriptor.mask_offset,
                         di=consumer_case['di'], sp=(state['sp'] - 2) & 0xFFFF)
            put16(ram, state['ss'], state['sp'], 0xD00D)

        prepare(ref_memory, ref_state)
        expected = wide.run_original(consumer_case, ref_memory, ref_state,
                                     ref_device, core=False)
        wide.oracle_require(expected['status'] == 0,
                            consumer_case['name'] + ': original consumer did not return')
        check(expected['regs']['ip'] == 0xD00D,
              consumer_case['name'] + ': constructed child RET changed')
        check(expected['memory'][output_start:output_start + 5120] == output,
              consumer_case['name'] + ': original consumer changed producer banks')
        consumer_sites.update(pc for scope, pc in expected['sites'] if scope == 'main')
        consumer_edges.update((a, b) for scope, a, b in expected['edges']
                              if scope == 'main')
        consumer_events += len(expected['events'])
        consumer_steps += expected['steps']

        if native is not None:
            prepare(native_memory, native_state)
            actual = wide_native.run(consumer_case, native_memory, native_state,
                                     native_device, core=False)
            wide.require(actual['status'] == 0,
                         consumer_case['name'] + ': native consumer did not return')
            wide.require(actual['continuation'] == expected['continuation'],
                         consumer_case['name'] + ': consumer continuation differs')
            wide.compare_regs(consumer_case['name'], actual['regs'], expected['regs'],
                              expected['flag_mask'], wide.Mismatch)
            wide.compare_memory(consumer_case['name'], actual['memory'],
                                expected['memory'], wide.Mismatch)
            wide.compare_events(consumer_case['name'], actual['events'],
                                expected['events'], wide.Mismatch)
            wide.compare_devices(consumer_case['name'], actual['device'],
                                 expected['device'], wide.Mismatch)
            wide.require(actual['used'] == expected['used'],
                         consumer_case['name'] + ': consumer providers differ')
            wide.require(actual['memory'][output_start:output_start + 5120] == output,
                         consumer_case['name'] + ': native consumer changed producer banks')
            native_state = dict(actual['regs'])
            native_device = actual['device']

        ref_rows.append(dict(bank_index=index, bank_bytes=640,
                             bank_sha256=sha(output[index * 640:(index + 1) * 640]),
                             consumer_events=len(expected['events']),
                             consumer_steps=expected['steps'],
                             consumer_sites=sorted(pc for scope, pc in expected['sites']
                                                  if scope == 'main')))
        ref_memory = bytearray(expected['memory'])
        ref_state = dict(expected['regs'])
        ref_device = expected['device']

    return dict(bank_bytes=len(output), bank_sha256=bank_hash,
                producer_events=len(producer_ref['events']),
                producer_steps=producer_ref['steps'],
                native_compared=native is not None,
                native_phase_comparisons=9 if native is not None else 0,
                consumer_bank_count=len(ref_rows),
                consumer_code_bytes=wide.CODE_BYTES,
                consumer_executed_instruction_bytes=sum(
                    wide.OWN_INS[pc].size for pc in consumer_sites),
                consumer_instruction_sites=len(consumer_sites),
                consumer_executed_instruction_addresses=sorted(consumer_sites),
                consumer_branch_edges=sorted([a, b] for a, b in consumer_edges),
                consumer_branch_edge_count=len(consumer_edges),
                consumer_ordered_events=consumer_events,
                consumer_instruction_steps=consumer_steps,
                banks=ref_rows)


def publish(path, before, rows, hands, mutants=None):
    sites = {pc for row in rows for pc in row['sites']}
    branches = {tuple(edge) for row in rows for edge in row['edges']}
    check(sites == OWN_SITES, f'missing instruction sites: {OWN_SITES - sites}')
    check(branches == edges(), f'missing branch outcomes: {edges() - branches}')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(cases()),
        comparison_count=len(rows), translated_code_bytes=187, instruction_sites=80,
        executed_instruction_addresses=sorted(sites),
        branch_edges=sorted([a, b] for a, b in branches),
        branch_edge_count=len(branches), ordered_events=sum(r['events'] for r in rows),
        original_instruction_steps=sum(r['steps'] for r in rows),
        independent_output_bytes=sum(r['independent_bytes'] for r in rows),
        original_only=mutants is None, mutation_count=len(mutants or []),
        mutations=mutants or [], rows=rows, input_hashes=before,
        producer_consumer_handoff=hands,
        limits=dict(timeout_seconds=420, process_commit_mib=384,
                    original_instruction_limit=MAX_STEPS, bus_event_limit=MAX_EVENTS))
    write_json(path, report)
    print(f'PASS five-byte banks: {len(cases())} fixtures/{len(rows)} boundaries, '
          f'{len(sites)} sites/{len(branches)} edges, {report["ordered_events"]} events, '
          f'{len(mutants or [])} mutants', flush=True)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == hashes(), 'input snapshot differs')
    native, rows = Native(directory), []
    for case in cases():
        for core in (True, False):
            ref, checked = compare(native, case, core=core)
            rows.append(collect(ref, case, core, checked))
        gc.collect()

    witnesses = [
        (1, 'ordinary-eight-banks', True),
        (2, 'ordinary-eight-banks', True),
        (3, 'ordinary-eight-banks', True),
        (4, 'provider-replaces-saved-di-before-5c53', True),
        (5, 'source-ea-wrap-ffff', True),
        (6, 'signed-fold-negative-8000', True),
        (7, 'provider-replaces-per-bank-saved-si', True),
        (8, 'provider-mask-cx-fourth-sp-8-write', True),
        (9, 'output-overwrites-actual-outer-ret', False),
        (10, 'ordinary-eight-banks', False),
    ]
    by_name = {case['name']: case for case in cases()}
    mutants = []
    for number, name, core in witnesses:
        try:
            compare(Native(directory, number), by_name[name], core=core)
        except bus_shared.Mismatch as error:
            mutants.append(dict(mutation=number, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise bus_shared.OracleFailure(f'mutation {number} survived')
        gc.collect()
    hands = handoffs(native, directory)
    check(before == hashes(), 'inputs changed during native campaign')
    publish(REPORT, before, rows, hands, mutants)


def main():
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == '--worker':
        worker(args[1], args[2])
        return
    if args == ['--original-worker']:
        before, rows, hands = original_campaign()
        publish(ORIGINAL_REPORT, before, rows, hands)
        return
    if args not in ([], ['--original-only']):
        raise SystemExit('usage: sprite_wide_banks.py [--original-only]')
    BUILD.mkdir(exist_ok=True)
    if args:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=420, memory_mib=384, check=True)
        return
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='sprite-wide-banks-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'inputs.json'
        snapshot.write_text(json.dumps(hashes()))
        run_bounded([sys.executable, __file__, '--worker', directory, str(snapshot)],
                    cwd=ROOT, timeout=420, memory_mib=384, check=True)


if __name__ == '__main__':
    main()
