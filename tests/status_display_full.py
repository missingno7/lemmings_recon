"""Bounded differential checks for the 3AC8 full status-display caller.

This harness composes the already-tested 3AC8 minimap prefix with the 3ACE
status-display body in one original instruction stream.  It keeps the real
CALL/RET frames, live register handoff, VGA device and callback providers.
"""
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
import entity_interactions as interactions
from entity_interactions import OracleFailure, REG_NAMES, Regs
import minimap_status as prefix_test
import status_display as suffix_test
from unpack import ASSET, unpack

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, FALLTHROUGH, DIVIDE, RET, END = 0x3AC8, 0x3ACE, 0x3AED, 0x3CDD, 0x3CDE
UNKNOWN = 0x3B08
DEFINED_FLAGS = prefix_test.DEFINED_FLAGS
MAX_INSTRUCTIONS, MAX_EVENTS = 40000, 65536
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-display-full-differential.json'
ORIGINAL_REPORT = BUILD / 'status-display-full-original-differential.json'
CORE_NAMES = suffix_test.CORE_NAMES
RESULT_FIELDS = suffix_test.RESULT_FIELDS
MEM = ct.POINTER(ct.c_uint8)


class Call(suffix_test.Call):
    pass


class Result(suffix_test.Result):
    pass


class RasterBus(suffix_test.RasterBus):
    pass


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def add_instruction_map(target, source, label):
    for address, ins in source.items():
        prior = target.get(address)
        oracle_require(prior is None or (prior.bytes == ins.bytes and
                                         prior.size == ins.size),
                       f'{label}: instruction-map conflict at {address:04X}')
        target[address] = ins


FULL_INS = {}
add_instruction_map(FULL_INS, prefix_test.INTEGRATED_INS, 'prefix integration')
add_instruction_map(FULL_INS, suffix_test.MAIN_INS, 'suffix integration')
FULL_CALL_RETURNS = dict(prefix_test.MAIN_CALL_RETURNS)
for address, contract in suffix_test.PARENT_CALL_RETURNS.items():
    oracle_require(address not in FULL_CALL_RETURNS,
                   f'overlapping CALL contract at {address:04X}')
    FULL_CALL_RETURNS[address] = contract
FULL_OWN_INS = dict(prefix_test.OWN_INS)
add_instruction_map(FULL_OWN_INS, suffix_test.PARENT_INS, 'owned parent span')
FULL_OWN_SITES = set(FULL_OWN_INS)
CODE_BYTES = 6 + suffix_test.CODE_BYTES


def static_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        mnemonic = ins.mnemonic.lower()
        if not (ins.group(capstone.CS_GRP_JUMP) or
                mnemonic in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if mnemonic not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


FULL_EDGES = static_edges(FULL_OWN_INS)
oracle_require(CODE_BYTES == 533 and len(FULL_OWN_SITES) == 174 and
               len(prefix_test.OWN_INS) == 2 and UNKNOWN not in FULL_OWN_SITES,
               'full status-display parent range changed from 533 bytes/174 sites')


def _by_name(module, wanted):
    rows = module.cases()
    for row in rows:
        if row['name'] == wanted:
            return dict(row)
    raise OracleFailure(f'{module.__name__}: fixture not found: {wanted}')


def cases():
    """Focused wrapper handoffs; child branch matrices stay in their leaf suites."""
    rows = [
        dict(name='full-prefix-to-all-ten-counts-core-and-adapter',
             prefix='normal-zero-alignment-all-ones',
             suffix='full-status-line-renders-updated-percent-and-all-counts',
             modes=(True, False)),
        dict(name='full-prefix-df-to-equal-snapshot-suffix',
             prefix='normal-df-set-if-set',
             suffix='exact-100-percent-equal-snapshots-skip-counts',
             modes=(True,)),
        dict(name='full-prefix-live-returned-ds-feeds-suffix',
             prefix='stack-mirror-live-pop-ds-feeds-viewport',
             suffix='unclamped-255-through-division', modes=(True, False),
             split_ds=True),
        dict(name='full-prefix-inner-column-return-stops-before-suffix',
             prefix='inner-column-sample-return-changed',
             suffix='exact-100-percent-equal-snapshots-skip-counts', modes=(True,)),
        dict(name='full-prefix-column-call-return-stops-before-suffix',
             prefix='column-call-live-return-word-changed',
             suffix='exact-100-percent-equal-snapshots-skip-counts', modes=(True,)),
        dict(name='full-prefix-viewport-call-return-stops-before-suffix',
             prefix='viewport-call-live-return-word-changed',
             suffix='exact-100-percent-equal-snapshots-skip-counts', modes=(True,)),
        dict(name='full-suffix-text-call-return-preserves-wrapper-seam',
             prefix='normal-seven-pixel-offset-if-clear',
             suffix='changed-parent-text-call-return', modes=(True,)),
        dict(name='full-prefix-completes-before-divide-error-boundary',
             prefix='normal-nonzero-column-and-retained-planes',
             suffix='divide-overflow-at-three-over-one', modes=(True, False)),
        dict(name='full-adapter-reads-outer-return-after-suffix-output',
             prefix='signed-column-upper-bound-is-reset',
             suffix='live-outer-return-word-after-first-child-output',
             modes=(False,)),
        dict(name='full-prefix-and-suffix-preserve-clear-if',
             prefix='normal-seven-pixel-offset-if-clear',
             suffix='if-clear-entry-flows-through-cli-sti-children', modes=(True,)),
    ]
    for row in rows:
        row['prefix_case'] = _by_name(prefix_test, row['prefix'])
        row['suffix_case'] = _by_name(suffix_test, row['suffix'])
        oracle_require(row['prefix_case']['expected'] in
                       ('ready', 'ds-mirror', 'inner-column', 'column-call',
                        'viewport-call'),
                       row['name'] + ': unknown prefix boundary class')
    oracle_require(8 <= len(rows) <= 12 and
                   len({row['name'] for row in rows}) == len(rows),
                   'full status-display handoff fixture inventory changed')
    return rows


class FullAccess(prefix_test.StatusAccess, suffix_test.DisplayAccess):
    """One event/provider surface for both real parent spans and children."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        suffix_test.DisplayAccess.__init__(self, case, memory, regs, device)
        self.suffix_started = False
        self.suffix_start_addresses = {
            suffix_test.physical(segment, 0x0046)
            for segment in case.get('_suffix_data_segments', (regs['ds'],))
        }

    def access(self, kind, address, flags, mask=DEFINED_FLAGS, value=None):
        address &= MASK
        if (not self.suffix_started and kind == 'read' and
                address in self.suffix_start_addresses):
            # DisplayAccess providers count from its first suffix OUT. The
            # prefix has its own VGA outcount and must not consume that phase.
            self.out_count = 0
            self.suffix_started = True
        return suffix_test.DisplayAccess.access(
            self, kind, address, flags, mask, value)

    def out_word(self, port, value, flags, mask=DEFINED_FLAGS):
        if not self.suffix_started:
            return prefix_test.StatusAccess.out_word(self, port, value, flags, mask)
        return suffix_test.DisplayAccess.out_word(self, port, value, flags, mask)


def prepare_fixture(spec):
    pcase = dict(spec['prefix_case'])
    scase = dict(spec['suffix_case'])
    memory, regs, flags, device = prefix_test.setup(pcase)
    entry_ds = regs['ds'] & 0xFFFF
    active_ds = (pcase.get('viewport_segment', entry_ds) & 0xFFFF
                 if pcase.get('expected') == 'ds-mirror' else entry_ds)

    # The suffix helper writes only data and fonts. Preserve the flags produced
    # by the caller setup: these are the actual entry flags for the prefix.
    suffix_data_case = dict(scase)
    suffix_data_case['df'] = bool(flags & 0x0400)
    suffix_data_case['iflag'] = bool(flags & 0x0200)
    if spec.get('split_ds'):
        # The entry DS intentionally overflows DIV; the live viewport POP DS
        # selects a separately prepared, finite suffix state.
        entry_data_case = dict(suffix_data_case, completion=4, limit=1,
                               row_state='equal-skip', text='')
        suffix_test.prepare_data(memory, regs, entry_data_case,
                                 data_segments=(entry_ds,))
        active_segments = [active_ds]
        if suffix_data_case.get('provider_glyph_ds') is not None:
            active_segments.append(suffix_data_case['provider_glyph_ds'])
        suffix_test.prepare_data(memory, regs, suffix_data_case,
                                 data_segments=active_segments)
    else:
        suffix_test.prepare_data(memory, regs, suffix_data_case)
    regs['flags'] = flags

    combined = dict(pcase)
    combined.update(suffix_data_case)
    suffix_segments = [entry_ds, active_ds]
    if suffix_data_case.get('provider_glyph_ds') is not None:
        suffix_segments.append(suffix_data_case['provider_glyph_ds'])
    combined.update(name=spec['name'], ss=regs['ss'], sp=regs['sp'],
                    _suffix_data_segments=tuple(dict.fromkeys(suffix_segments)),
                    _prefix_expected=pcase['expected'],
                    _active_data_segment=active_ds,
                    _split_ds=bool(spec.get('split_ds')))
    return dict(case=combined, prefix_case=pcase, suffix_case=suffix_data_case,
                memory=memory, regs=regs, device=device, entry_ds=entry_ds,
                active_ds=active_ds, entry_flags=flags)


def run_reference(fixture, *, core=True):
    case = fixture['case']
    divide_error = bool(fixture['suffix_case'].get('divide_error'))
    if divide_error:
        stops = {DIVIDE: 1}
    elif core:
        stops = {RET: 0}
    else:
        stops = None
    return interactions.original(
        case, bytearray(fixture['memory']), dict(fixture['regs']),
        copy.deepcopy(fixture['device']), False,
        entry_flag_mask=DEFINED_FLAGS, main_instructions=FULL_INS,
        main_call_returns=FULL_CALL_RETURNS, stop_offsets=stops,
        access_factory=FullAccess, instruction_limit=MAX_INSTRUCTIONS)


def expected_wrapper_metadata(fixture, observed):
    pexpected = fixture['prefix_case']['expected']
    suffix_case = fixture['suffix_case']
    if pexpected not in ('ready', 'ds-mirror'):
        return (5, observed['continuation'], ENTRY, observed['status'])
    if suffix_case.get('divide_error'):
        return (1, DIVIDE, 0, 0xFFFF)
    if suffix_case.get('expected_status') is not None:
        return (observed['status'], observed['continuation'], 0x417B, 0)
    return (0, observed['continuation'], 0, 0xFFFF)


def validate_original(fixture, observed, *, core):
    case = fixture['case']
    pcase = fixture['prefix_case']
    scase = fixture['suffix_case']
    pexpected = pcase['expected']
    if pexpected in ('ready', 'ds-mirror'):
        oracle_require({('main', prefix_test.COLUMN),
                        ('main', prefix_test.VIEWPORT),
                        ('main', prefix_test.COLUMN_RET),
                        ('main', prefix_test.VIEWPORT_RET)} <= observed['sites'],
                       case['name'] + ': normal prefix missed an actual child seam')
        oracle_require(('main', FALLTHROUGH) in observed['sites'],
                       case['name'] + ': successful prefix did not execute suffix')
    else:
        expected_prefix_status = {'inner-column': 1, 'column-call': 2,
                                  'viewport-call': 2}[pexpected]
        oracle_require(observed['status'] == expected_prefix_status and
                       observed['continuation'] == pcase['changed_return'],
                       case['name'] + ': original prefix did not stop at its changed child seam')
        oracle_require(('main', FALLTHROUGH) not in observed['sites'] and
                       not any(('main', address) in observed['sites']
                               for address in suffix_test.PARENT_SITES),
                       case['name'] + ': suffix ran after a prefix boundary')
        provider_name = {'inner-column': 'inner-column-return',
                         'column-call': 'column-call-return',
                         'viewport-call': 'viewport-call-return'}[pexpected]
        oracle_require(provider_name in observed['used'],
                       case['name'] + ': prefix return-word provider did not fire')
        return

    if scase.get('divide_error'):
        suffix_test.assert_independent(scase, fixture['memory'],
                                       dict(fixture['regs'], ds=fixture['active_ds']),
                                       observed, core=core)
        oracle_require(observed['continuation'] == DIVIDE and
                       ('main', DIVIDE) not in observed['sites'],
                       case['name'] + ': divide boundary was not pre-instruction')
        return

    independent_regs = dict(fixture['regs'], ds=fixture['active_ds'])
    suffix_test.assert_independent(scase, fixture['memory'], independent_regs,
                                   observed, core=core)
    if fixture['active_ds'] != fixture['entry_ds']:
        oracle_require(observed['regs']['ds'] == fixture['active_ds'],
                       case['name'] + ': suffix did not retain prefix-returned DS')
    if scase.get('provider_outer_return') is not None and not core:
        oracle_require(observed['regs']['ip'] == scase['provider_outer_return'] and
                       'outer-return-provider' in observed['used'],
                       case['name'] + ': adapter did not consume the live outer RET')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered bus event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


class NativeBus:
    def __init__(self, case, memory, regs, device):
        callback_case = dict(case, _native=True)
        self.access = FullAccess(callback_case, memory, regs, device)
        self.events, self.used = self.access.events, self.access.used

        def read(_ctx, _mem, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'full status-display read callback failed: {error}')

        def write(_ctx, _mem, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'full status-display write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'full status-display OUT callback failed: {error}')

        self.callbacks = (suffix_test.READ(read), suffix_test.WRITE(write),
                          suffix_test.OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-display-full-m{mutation}.dll',
                     mutation, 'status_display_full')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_update_status_display_full_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_update_status_display_full_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, fixture, *, core):
        case = fixture['case']
        memory = bytearray(fixture['memory'])
        regs = dict(fixture['regs'])
        device = copy.deepcopy(fixture['device'])
        callback = NativeBus(case, memory, regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(callback.bus))
            for name in CORE_NAMES:
                setattr(state, name, getattr(result, RESULT_FIELDS[name]))
            state.ip = result.continuation
            status = result.status
            child_entry, child_status = result.child_entry, result.child_status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(callback.bus))
            child_entry = child_status = 0xFFFF
        final_regs = {name: getattr(state, name) & 0xFFFF for name in REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs, device=device,
                    events=callback.events, used=set(callback.used), status=status,
                    continuation=final_regs['ip'], child_entry=child_entry,
                    child_status=child_status)


def compare_case(native, fixture, *, core):
    expected = run_reference(fixture, core=core)
    validate_original(fixture, expected, core=core)
    actual = native.run(fixture, core=core)
    case = fixture['case']
    label = case['name'] + (' core' if core else ' adapter')
    want_status, want_cont, want_child, want_child_status = \
        expected_wrapper_metadata(fixture, expected)
    require(actual['status'] == want_status,
            f'{label}: status {actual["status"]}/{want_status}')
    require(actual['continuation'] == want_cont,
            f'{label}: continuation {actual["continuation"]:04X}/{want_cont:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    for name in REG_NAMES:
        flag_mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & flag_mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {flag_mask:04X}')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: provider effects {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': complete VGA state differs')
    if core:
        require((actual['child_entry'], actual['child_status']) ==
                (want_child, want_child_status),
                f'{label}: child metadata '
                f'{actual["child_entry"]:04X}/{actual["child_status"]:04X} != '
                f'{want_child:04X}/{want_child_status:04X}')
    own_sites = {off for source, off in expected['sites']
                 if source == 'main' and off in FULL_OWN_SITES}
    own_edges = {(off, target) for source, off, target in expected['edges']
                 if source == 'main' and off in FULL_OWN_SITES}
    return dict(name=case['name'], core=core, status=actual['status'],
                continuation=actual['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                steps=expected['steps'], events=len(expected['events']))


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/minimap.md', 'docs/minimap-viewport.md', 'docs/minimap-vga.md',
        'docs/status-display.md', 'docs/status-icons.md',
        'assets/vgalemmi.exe', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/game_code_late.asm',
        'src/game_code_before_minimap.asm', 'src/minimap.asm',
        'src/minimap_viewport.asm', 'src/status_display.asm',
        'src/status_glyphs.asm', 'src/status_icons.asm', 'src/image_tail.asm',
        'c/status_display_full.c', 'c/status_display_full.h',
        'c/status_display.c', 'c/status_display.h', 'c/minimap_status.c',
        'c/minimap_status.h', 'c/minimap_viewport.c', 'c/minimap_viewport.h',
        'c/minimap_column.c', 'c/minimap_column.h', 'c/minimap_row.c',
        'c/minimap_row.h', 'c/minimap_sample.c', 'c/minimap_sample.h',
        'c/status_text.c', 'c/status_text.h', 'c/status_glyph.c', 'c/status_glyph.h',
        'c/status_count.c', 'c/status_count.h', 'c/status_icons.c', 'c/status_icons.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/status_display_full.py', 'tests/status_display.py',
        'tests/minimap_status.py', 'tests/minimap_connected.py',
        'tests/minimap_viewport.py', 'tests/minimap_column.py', 'tests/minimap_row.py',
        'tests/minimap_sample.py', 'tests/minimap_vga.py', 'tests/status_text.py',
        'tests/status_glyph.py', 'tests/status_count.py', 'tests/status_icons.py',
        'tests/entity_interactions.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tools/resources.py',
        'tools/unpack.py', 'tools/common.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'full status-display input hashes missing: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(),
                   'full status-display inputs changed before original preflight')
    prefix_test.verify_static_identity()
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for spec in specs:
        fixture = prepare_fixture(spec)
        for core in spec['modes']:
            expected = run_reference(fixture, core=core)
            validate_original(fixture, expected, core=core)
            own_sites = {off for source, off in expected['sites']
                         if source == 'main' and off in FULL_OWN_SITES}
            own_edges = {(off, target) for source, off, target in expected['edges']
                         if source == 'main' and off in FULL_OWN_SITES}
            rows.append(dict(name=fixture['case']['name'], core=core,
                             status=expected_wrapper_metadata(fixture, expected)[0],
                             continuation=expected['continuation'],
                             sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events'])))
            sites.update(own_sites)
            edges.update(own_edges)
            total_events += len(expected['events'])
            total_steps += expected['steps']
        del fixture
        gc.collect()
    oracle_require({prefix_test.ENTRY, prefix_test.COLUMN_AFTER} <= sites,
                   'full wrapper campaign did not execute both owned CALL sites')
    oracle_require(before == input_hashes(),
                   'full status-display inputs changed during original preflight')
    return rows, sites, edges, total_events, total_steps


def verify_actual_div_trap():
    suffix_test.verify_actual_div_trap()


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'full status-display inputs changed before native worker')
    specs = cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    fixture_by_name = {}
    prepared = {}
    for spec in specs:
        fixture = prepare_fixture(spec)
        fixture_by_name[spec['name']] = fixture
        for core in spec['modes']:
            row = compare_case(baseline, fixture, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
        prepared[spec['name']] = fixture
        gc.collect()

    witnesses = {
        1: 'full-prefix-to-all-ten-counts-core-and-adapter',
        2: 'full-prefix-live-returned-ds-feeds-suffix',
        3: 'full-prefix-viewport-call-return-stops-before-suffix',
    }
    mutants = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        fixture = fixture_by_name[name]
        try:
            compare_case(variant, fixture, core=True)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'full status-display mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after,
                   'full status-display inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[0x3AC8, 0x3B08], [0x3B09, END]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(FULL_OWN_SITES),
        static_instruction_addresses=sorted(FULL_OWN_SITES),
        branch_edge_count=len(FULL_EDGES),
        static_branch_edges=[list(edge) for edge in sorted(FULL_EDGES)],
        case_count=len(specs), comparisons=len(rows), mutation_count=len(mutants),
        mutations=mutants, executed_instruction_addresses=sorted(sites),
        executed_site_count=len(sites), branch_edges=[list(edge) for edge in sorted(edges)],
        cases=rows, total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domains=[
            '3AC8 two-CALL minimap prefix and its no-frame fallthrough to the 3ACE suffix',
            'actual minimap column/viewport return contracts, including nested and outer changed targets',
            'live DS returned by the viewport child is consumed by the suffix without a copied state frame',
            'suffix percentage division boundary, text child return, ten count calls, and live outer RET',
            'whole 1 MiB RAM, all logical registers, defined FLAGS, ordered byte/word callbacks, and complete VGA device state',
            'the 3B08 UNKNOWN byte is excluded from the translated instruction map',
        ]))
    print(f'PASS full status display: {len(specs)} focused fixtures, '
          f'{len(sites)}/{len(FULL_OWN_SITES)} own sites, '
          f'{len(edges)} observed branch outcomes, {total_events} events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-display-full-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, edges, events, steps = original_campaign(cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE),
            code_ranges=[[0x3AC8, 0x3B08], [0x3B09, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(FULL_OWN_SITES),
            static_instruction_addresses=sorted(FULL_OWN_SITES),
            branch_edge_count=len(FULL_EDGES),
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=len(cases()), input_hashes=before,
            total_bus_events=events, original_instruction_steps=steps, cases=rows,
            domains=['single-stream original composition of prefix and suffix',
                     'bounded changed-child seams and a separate pre-DIV error boundary']))
        print(f'PASS full status-display original preflight: {len(cases())} fixtures, '
              f'{len(sites)} sites, {len(edges)} branch outcomes', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_display_full.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-display-full-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
