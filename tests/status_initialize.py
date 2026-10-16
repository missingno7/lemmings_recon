"""Bounded original/native checks for status initialization at 39CE."""
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
import decimal_field as decimal
import entity_interactions as interactions
import status_copy as copy_test
import status_count as count_test
import status_display as display_test
import status_glyph as glyph_test
import status_icons as icons_test
from minimap_vga import MinimapVga
from unpack import ASSET, unpack

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, RETURN, END = 0x39CE, 0x3AC7, 0x3AC8
LOAD = 0x1010
DEFINED_FLAGS = 0x0FD7
DF = 0x0400
MAX_INSTRUCTIONS, MAX_EVENTS = 20000, 32768
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-initialize-differential.json'
ORIGINAL_REPORT = BUILD / 'status-initialize-original-differential.json'

CORE_FIELDS = ('value', 'map_cursor', 'count', 'auxiliary_value',
               'record_cursor', 'object_cursor', 'candidate_y',
               'code_segment', 'data_segment', 'extra_segment',
               'stack_segment', 'stack_offset', 'flags')
CORE_REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')
RESULT_FIELDS = dict(zip(CORE_REGS, CORE_FIELDS))
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_FIELDS]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                CORE_FIELDS + ('continuation', 'status', 'child_entry', 'child_status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The original execution, fixture domain, or a declared hard bound failed."""


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


def oracle_require(condition, message):
    if not condition:
        raise interactions.OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return ((((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK)


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
COPY_INS = copy_test.OWN_INS
COUNT_INS = count_test.OWN_INS
GLYPH_INS = glyph_test.INSTRUCTIONS
DECIMAL_INS = decimal.INS
ICON_INS = icons_test.INSTRUCTIONS
MAIN_INS = PARENT_INS | COPY_INS | COUNT_INS | GLYPH_INS | DECIMAL_INS | ICON_INS
PARENT_SITES = set(PARENT_INS)
PARENT_EDGES = set()
PARENT_CALL_RETURNS = {
    0x39CE: ({0x7629}, 2),
    0x75F7: ({0x7629}, 1),
    0x3AB7: ({0x4BBD}, 2),
    0x3AC4: ({0x789D}, 2),
}
COUNT_CALLS = (0x3A5D, 0x3A66, 0x3A6F, 0x3A78, 0x3A81,
               0x3A8A, 0x3A93, 0x3A9C, 0x3AA5, 0x3AAE)
COUNT_RETURN_SITES = {0x76DA, 0x7707}
for _call in COUNT_CALLS:
    PARENT_CALL_RETURNS[_call] = (COUNT_RETURN_SITES, 2)

PARENT_BYTES = sum(ins.size for ins in PARENT_INS.values())
oracle_require(PARENT_BYTES == 250 and len(PARENT_SITES) == 70,
               f'initializer source boundary changed: {PARENT_BYTES} bytes, '
               f'{len(PARENT_SITES)} instruction sites')
oracle_require(not any(ins.group(capstone.CS_GRP_JUMP) for ins in PARENT_INS.values()),
               'initializer expected to remain a straight-line parent span')

COUNT_ROWS = (
    (0x64, 0x65, 0x66), (0x67, 0x68, 0x69),
    (0x70, 0x71, 0x72), (0x7F, 0x80, 0x81),
    (0x6A, 0x6B, 0x6C), (0x76, 0x77, 0x78),
    (0x73, 0x74, 0x75), (0x79, 0x7A, 0x7B),
    (0x6D, 0x6E, 0x6F), (0x7C, 0x7D, 0x7E),
)
COUNTERS = (0x66, 0x69, 0x72, 0x81, 0x6C, 0x78, 0x75, 0x7B, 0x6F, 0x7E, 0x84)
SNAPSHOTS = (0x65, 0x68, 0x71, 0x80, 0x6B, 0x77, 0x74, 0x7A, 0x6E, 0x7D)


def make_cases():
    common = dict(completion=24, limit=76, row_state='mixed', selector=3,
                  icon_snapshot=3, icon_counter=0, text='A')
    return [
        dict(name='complete-all-ten-action-counts-copy-decimal-outline',
             **common, pass_count=42, release_setting=1, minimum_count=1,
             seed=0x39CE01),
        dict(name='release-rate-zero-and-pass-count-zero',
             **{**common, 'row_state': 'zero-wrap'}, pass_count=0,
             release_setting=0, minimum_count=0, seed=0x39CE02),
        dict(name='release-rate-one-odd-shift-witness',
             **common, pass_count=99, release_setting=1, seed=0x39CE03),
        dict(name='release-rate-high-byte-wrap-and-df-copy',
             **{**common, 'df': True}, pass_count=255, release_setting=0xFF,
             seed=0x39CE04),
        dict(name='release-rate-middle-boundary',
             **common, pass_count=100, release_setting=0x63, seed=0x39CE05),
        dict(name='refresh-counter-before-snapshot-order',
             **common, pass_count=7, release_setting=0x62, seed=0x39CE06),
        dict(name='action-two-and-seven-distinct-counts',
             **common, pass_count=255, release_setting=0x62,
             minimum_count=4, count_values={0x70: 2, 0x7F: 7}, seed=0x39CE07),
        dict(name='returned-live-ds-from-copy-wrapper',
             **common, pass_count=73, release_setting=1, provider_copy_ds=0x4500,
             seed=0x39CE08),
        dict(name='nested-copy-return-same-as-parent-continuation',
             **common, pass_count=33, release_setting=0x62,
             provider_inner_return=0x39D1, expected_status=1,
             expected_child_entry=0x75EF, expected_child_status=1,
             expected_continuation=0x39D1, seed=0x39CE09),
        dict(name='changed-parent-copy-return',
             **common, pass_count=12, release_setting=0x62,
             provider_parent_return=0x4567, expected_status=2,
             expected_child_entry=0x75EF, expected_child_status=0,
             expected_continuation=0x4567, seed=0x39CE0A),
        dict(name='adapter-reads-live-outer-return-after-output',
             **common, pass_count=31, release_setting=0x62,
             provider_outer_return=0x4567, outer_return=0x4C12,
             seed=0x39CE0B),
        dict(name='df-and-if-clear-entry-state',
             **{**common, 'df': True, 'iflag': False}, pass_count=80,
             release_setting=0x64, seed=0x39CE0C),
        dict(name='ds-equals-ss-with-distant-live-stack',
             **common, pass_count=18, release_setting=0xFF, ds=0x5200,
             ss=0x5200, sp=0x7000, seed=0x39CE0D),
        dict(name='physical-word-wrap-stack-return',
             **common, pass_count=18, release_setting=0xFF, ss=0xFFFC,
             sp=0x003F, seed=0x39CE0E),
        dict(name='vga-mirror-aliases-first-count-return',
             **common, pass_count=18, release_setting=0xFF, ss=0xFFFF,
             sp=0x000F, expected_status=2, expected_child_entry=0x762A,
             expected_child_status=0, expected_continuation=0x080C,
             seed=0x39CE0F),
    ]


def _status_case(case):
    base = dict(name=case['name'], completion=case.get('completion', 24),
                limit=case.get('limit', 76),
                row_state=case.get('row_state', 'mixed'),
                selector=case.get('selector', 3),
                icon_snapshot=case.get('icon_snapshot', 3),
                icon_counter=case.get('icon_counter', 0),
                text=case.get('text', 'A'), seed=case['seed'],
                ds=case.get('ds', 0x3500), ss=case.get('ss', 0x5200),
                sp=case.get('sp', 0x7000),
                df=case.get('df', False), iflag=case.get('iflag', True))
    return base


def _seed_status_segment(memory, segment, case):
    put8(memory, segment, 0x0045, case['pass_count'])
    put8(memory, segment, 0x0048, 0xE7)
    put8(memory, segment, 0x0049, 0xE6)
    put8(memory, segment, 0x0064, case.get('minimum_count', 1))
    put8(memory, segment, 0x0067, case['release_setting'])
    for value_offset, _snapshot, _counter in COUNT_ROWS[2:]:
        if value_offset in case.get('count_values', {}):
            put8(memory, segment, value_offset, case['count_values'][value_offset])
    put16(memory, segment, 0x1F78, case.get('alternate_origin', 0x5800))
    put8(memory, segment, 0x0082, case.get('selector', 3))
    put8(memory, segment, 0x0083, 0xA7)
    put8(memory, segment, 0x0084, 0xB6)
    for offset in COUNTERS:
        put8(memory, segment, offset, 0x5A)
    for offset in SNAPSHOTS:
        put8(memory, segment, offset, 0xA5)
    for offset, value in ((0x2095, 0xCC), (0x2096, 0xDD),
                          (0x2097, 0xEE), (0x209C, 0xF1),
                          (0x209D, 0xF2), (0x209E, 0xF3)):
        put8(memory, segment, offset, value)


def setup(case):
    display_case = _status_case(case)
    memory, regs, device = display_test.setup(display_case)
    regs['ip'] = ENTRY
    regs['ax'] = case.get('ax', 0xB5A5)
    regs['bx'] = case.get('bx', 0xC217)
    regs['cx'] = case.get('cx', 0x8A51)
    regs['dx'] = case.get('dx', 0x3CE0)
    regs['si'] = case.get('si', 0x5123)
    regs['di'] = case.get('di', 0x42A7)
    regs['bp'] = case.get('bp', 0x6D93)
    ds = regs['ds']
    _seed_status_segment(memory, ds, case)
    alt_ds = case.get('provider_copy_ds')
    if alt_ds is not None:
        display_test.prepare_data(memory, regs, display_case, (ds, alt_ds))
        _seed_status_segment(memory, alt_ds, case)
        put16(memory, alt_ds, 0x1F78, case.get('alternate_origin', 0x6600))
    regs['sp'] = case.get('sp', 0x7000) & 0xFFFF
    regs['ss'] = case.get('ss', 0x5200) & 0xFFFF
    regs['ds'] = ds
    regs['ip'] = ENTRY
    status_display_return = case.get('outer_return', 0x4C35)
    put16(memory, regs['ss'], regs['sp'], status_display_return)
    if regs['ss'] == 0xA000:
        device.gc[4] = 0
        device.planes[0][regs['sp']] = status_display_return & 0xFF
        device.planes[0][(regs['sp'] + 1) & 0xFFFF] = status_display_return >> 8

    # The parent and every composed child execute only pinned original bytes.
    for address, ins in MAIN_INS.items():
        expected = IMAGE[address:address + ins.size]
        actual = bytes(memory[physical(regs['cs'], address) + i]
                       for i in range(ins.size))
        oracle_require(actual == expected,
                       f"{case['name']}: setup changed executable bytes at {address:04X}")
    return memory, regs, device


class InitializeAccess(display_test.DisplayAccess):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.entry_sp = regs['sp'] & 0xFFFF

    def out_word(self, port, value, flags, mask=DEFINED_FLAGS):
        first = self.out_count == 0
        super().out_word(port, value, flags, mask)
        if not first:
            return
        ss, sp = self.regs['ss'], self.entry_sp
        if self.case.get('provider_inner_return') is not None:
            self._word(ss, sp - 4, self.case['provider_inner_return'])
            self.used.add('copy-inner-live-ret')
        if self.case.get('provider_parent_return') is not None:
            self._word(ss, sp - 2, self.case['provider_parent_return'])
            self.used.add('parent-copy-live-ret')
        if self.case.get('provider_copy_ds') is not None:
            self._word(ss, sp - 6, self.case['provider_copy_ds'])
            self.used.add('copy-wrapper-live-ds')


def original(case, memory, regs, device, *, core):
    stops = {RETURN: 0} if core else None
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=DEFINED_FLAGS, main_instructions=MAIN_INS,
        main_call_returns=PARENT_CALL_RETURNS, stop_offsets=stops,
        access_factory=InitializeAccess, instruction_limit=MAX_INSTRUCTIONS)


def assert_independent(case, initial_memory, initial_regs, result, *, core):
    wanted_status = case.get('expected_status', 0)
    oracle_require(result['status'] == wanted_status,
                   f"{case['name']}: original status {result['status']}/{wanted_status}")
    if case.get('expected_continuation') is not None:
        oracle_require(result['continuation'] == case['expected_continuation'],
                       f"{case['name']}: original continuation "
                       f"{result['continuation']:04X}/"
                       f"{case['expected_continuation']:04X}")
    if wanted_status:
        expected_sp = ((initial_regs['sp'] - 2) & 0xFFFF
                       if wanted_status == 1 else initial_regs['sp'])
        oracle_require(result['regs']['sp'] == expected_sp,
                       case['name'] + ': stopped before consuming initializer CALL frame')
        return
    oracle_require(result['status'] == 0, case['name'] + ': successful path did not return READY')
    if core:
        oracle_require(result['continuation'] == RETURN,
                       case['name'] + ': core did not stop before the actual outer RET')
        oracle_require(result['regs']['sp'] == initial_regs['sp'],
                       case['name'] + ': core consumed the outer return word')
    else:
        oracle_require(result['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       case['name'] + ': adapter did not consume the actual outer RET')

    ds = result['regs']['ds']
    source_rate = get8(initial_memory, ds, 0x0067)
    rate = (4 + (((99 - source_rate) & 0xFF) >> 1)) & 0xFF
    oracle_require(get8(result['memory'], ds, 0x0048) == 0x14 and
                   get8(result['memory'], ds, 0x0049) == rate,
                   case['name'] + ': creation countdown/reload arithmetic differs')
    oracle_require(all(get8(result['memory'], ds, offset) == 0 for offset in COUNTERS),
                   case['name'] + ': refresh counters were not reset')
    oracle_require(all(get8(result['memory'], ds, offset) == 0xFF for offset in SNAPSHOTS) and
                   get8(result['memory'], ds, 0x0083) == 3 and
                   get8(result['memory'], ds, 0x0084) == 0,
                   case['name'] + ': initial display snapshots/icon state differ')
    rendered = decimal.format_contract(decimal.ENTRY_FULL,
                                       get8(initial_memory, ds, 0x0045))[0]
    oracle_require(tuple(get8(result['memory'], ds, 0x2095 + i) for i in range(3)) == rendered,
                   case['name'] + ': independent decimal-field bytes differ')
    oracle_require(get8(result['memory'], ds, 0x209C) == 0x20,
                   case['name'] + ': explicit percent-field space was not stored')


def observed_parent_sites(result):
    return {off for source, off in result['sites']
            if source == 'main' and off in PARENT_SITES}


def observed_parent_edges(result):
    return {edge[1:] for edge in result['edges']
            if edge[0] == 'main' and edge[1] in PARENT_SITES}


def run_rate_prefixes():
    """Execute the real eight-instruction rate prefix for every input byte."""
    case = dict(name='rate-prefix-template', pass_count=0, release_setting=0,
                seed=0x3900, completion=0, limit=76, row_state='zero-wrap',
                selector=3, icon_snapshot=3, icon_counter=0, text='')
    memory, regs, device = setup(case)
    ds = regs['ds']
    rows = []
    sites = set()
    total_steps = 0
    for rate_in in range(256):
        put8(memory, ds, 0x0067, rate_in)
        prefix_regs = dict(regs)
        prefix_regs.update(ip=0x39D6, flags=(0x0ED7 | (DF if rate_in & 1 else 0)) & ~0x0100)
        result = interactions.original(
            dict(case, name=f'rate-prefix-{rate_in:02X}'), memory, prefix_regs,
            copy.deepcopy(device), False, entry_flag_mask=DEFINED_FLAGS,
            main_instructions=PARENT_INS, stop_offsets={0x39E9: 0},
            access_factory=InitializeAccess, instruction_limit=16)
        actual = get8(result['memory'], ds, 0x0049)
        expected = 4 + (((99 - rate_in) & 0xFF) >> 1)
        oracle_require(actual == expected,
                       f'rate prefix {rate_in:02X}: stored {actual:02X}/{expected:02X}')
        oracle_require(result['continuation'] == 0x39E9 and result['steps'] == 9,
                       f'rate prefix {rate_in:02X}: wrong bounded prefix endpoint')
        own = observed_parent_sites(result)
        oracle_require(own == {0x39D6, 0x39D8, 0x39DC, 0x39DE,
                               0x39E0, 0x39E2, 0x39E4, 0x39E6},
                       f'rate prefix {rate_in:02X}: executed sites differ')
        sites |= own
        total_steps += result['steps']
        rows.append((rate_in, actual))
        if rate_in % 32 == 31:
            gc.collect()
    return rows, sites, total_steps


def input_hashes():
    paths = set(display_test.input_hashes())
    paths.update((
        'src/status_initialize.asm', 'src/status_copy.asm', 'src/decimal_fields.asm',
        'c/status_initialize.c', 'c/status_initialize.h', 'c/status_copy.c',
        'c/status_copy.h', 'c/status_count.c', 'c/status_count.h',
        'c/decimal_field.c', 'c/decimal_field.h', 'c/status_icons.c',
        'c/status_icons.h', 'tests/status_initialize.py', 'tests/status_copy.py',
        'tests/decimal_field.py', 'tests/status_count.py', 'tests/status_glyph.py',
    ))
    missing = sorted(path for path in paths if not (ROOT / path).is_file())
    oracle_require(not missing, 'required initializer inputs missing: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'initializer inputs changed before preflight')
    rows, sites, edges = [], set(), set()
    total_steps = total_events = 0
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = original(case, initial, regs, device, core=core)
            assert_independent(case, initial, regs, expected, core=core)
            own_sites = observed_parent_sites(expected)
            own_edges = observed_parent_edges(expected)
            if expected['status'] == 0:
                expected_sites = PARENT_SITES - ({RETURN} if core else set())
                oracle_require(own_sites == expected_sites,
                               f"{case['name']}: parent executed-site gap "
                               f'{sorted(expected_sites-own_sites)}')
            rows.append(dict(name=case['name'], core=core, status=expected['status'],
                             continuation=expected['continuation'],
                             parent_sites=sorted(own_sites),
                             parent_edges=[list(edge) for edge in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events'])))
            sites.update(own_sites)
            edges.update(own_edges)
            total_steps += expected['steps']
            total_events += len(expected['events'])
        del initial, regs, device
        gc.collect()
    rate_rows, rate_sites, rate_steps = run_rate_prefixes()
    sites |= rate_sites
    oracle_require(sites == PARENT_SITES,
                   f'initializer parent sites differ: missing={sorted(PARENT_SITES-sites)}')
    oracle_require(edges == PARENT_EDGES,
                   f'initializer branch outcomes differ: missing={sorted(PARENT_EDGES-edges)}')
    oracle_require(before == input_hashes(), 'initializer inputs changed during preflight')
    return rows, sites, edges, total_steps, total_events, rate_rows, rate_steps


class NativeBus:
    def __init__(self, case, memory, regs, device):
        native_case = dict(case, _native=True)
        self.access = InitializeAccess(native_case, memory, regs, device)
        self.events, self.used = self.access.events, self.access.used

        def read(_ctx, _mem, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'initializer native read callback failed: {error}')

        def write(_ctx, _mem, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'initializer native write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'initializer native OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-initialize-m{mutation}.dll',
                     mutation, 'status_initialize')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_initialize_status_display_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_initialize_status_display_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial_memory, initial_regs, initial_device, *, core):
        memory = bytearray(initial_memory)
        regs_values = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs_values, device)
        native_memory = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs_values)
        child_entry = child_status = 0xFFFF
        if core:
            call = Call(*(regs_values[name] for name in CORE_REGS))
            result = self.core(native_memory, ct.byref(call), ct.byref(callback.bus))
            for name in CORE_REGS:
                setattr(state, name, getattr(result, RESULT_FIELDS[name]))
            state.ip = result.continuation
            status = result.status
            child_entry, child_status = result.child_entry, result.child_status
        else:
            status = self.adapter(native_memory, ct.byref(state), ct.byref(callback.bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs, device=device,
                    events=callback.events, used=set(callback.used), status=status,
                    continuation=final_regs['ip'], child_entry=child_entry,
                    child_status=child_status)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    expected = original(case, initial, regs, device, core=core)
    assert_independent(case, initial, regs, expected, core=core)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    for name in interactions.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: providers {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA planes/latches/registers differ')
    if core:
        expected_child = case.get('expected_child_entry', 0)
        expected_raw = case.get('expected_child_status', 0xFFFF)
        require(actual['child_entry'] == expected_child,
                f'{label}: child entry {actual["child_entry"]:04X}/{expected_child:04X}')
        require(actual['child_status'] == expected_raw,
                f'{label}: child raw status {actual["child_status"]:04X}/{expected_raw:04X}')
    return dict(name=case['name'], core=core, status=actual['status'],
                continuation=actual['continuation'],
                parent_sites=sorted(observed_parent_sites(expected)),
                parent_edges=[list(edge) for edge in sorted(observed_parent_edges(expected))],
                steps=expected['steps'], events=len(expected['events']))


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'initializer inputs changed before native worker')
    specs = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['parent_sites'])
            edges.update(tuple(edge) for edge in row['parent_edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    rate_rows, rate_sites, rate_steps = run_rate_prefixes()
    oracle_require(len(rate_rows) == 256,
                   f'native rate-prefix sweep executed {len(rate_rows)}/256 inputs')
    oracle_require(rate_sites == {0x39D6, 0x39D8, 0x39DC, 0x39DE,
                                  0x39E0, 0x39E2, 0x39E4, 0x39E6},
                   'native worker rate-prefix instruction coverage differs')
    oracle_require(sites == PARENT_SITES,
                   f'native initializer sites differ: missing={sorted(PARENT_SITES-sites)}')
    oracle_require(edges == PARENT_EDGES,
                   f'native initializer branch outcomes differ: missing={sorted(PARENT_EDGES-edges)}')

    lookup = {case['name']: case for case in specs}
    witnesses = {
        1: 'complete-all-ten-action-counts-copy-decimal-outline',
        2: 'release-rate-one-odd-shift-witness',
        3: 'refresh-counter-before-snapshot-order',
        4: 'action-two-and-seven-distinct-counts',
        5: 'complete-all-ten-action-counts-copy-decimal-outline',
        6: 'complete-all-ten-action-counts-copy-decimal-outline',
        7: 'complete-all-ten-action-counts-copy-decimal-outline',
        8: 'complete-all-ten-action-counts-copy-decimal-outline',
    }
    mutants = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, lookup[name], core=True)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'initializer mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'initializer inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[ENTRY, END]], translated_code_bytes=PARENT_BYTES,
        instruction_sites=len(PARENT_SITES),
        static_instruction_addresses=sorted(PARENT_SITES),
        branch_edge_count=len(PARENT_EDGES), static_branch_edges=[],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        original_only_rate_prefix_samples=len(rate_rows),
        original_only_rate_prefix_steps=rate_steps,
        mutation_count=len(mutants), mutations=mutants,
        executed_instruction_addresses=sorted(sites), branch_edges=[], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domains=[
            '39CE..3AC7 initializer: 250 bytes/70 straight-line caller sites',
            'status-copy wrapper, ten count draws, full decimal field and icon outline composed with actual stack returns',
            'release-rate wrap/shift arithmetic checked independently for all 256 byte inputs',
            'refresh reset and snapshot initialization order, including action selector call order',
            'live DS returned from the copy wrapper, same-IP nested child boundary, changed parent CALL and actual outer RET',
            'full 1 MiB RAM, 13 logical roles plus IP, defined FLAGS, ordered bus events and VGA planes/latches/registers',
        ]))
    print(f'PASS status initialize: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)}/70 parent sites, {total_events} bus events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-initialize-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, edges, steps, events, rate_rows, rate_steps = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=PARENT_BYTES, instruction_sites=len(PARENT_SITES),
            static_instruction_addresses=sorted(PARENT_SITES),
            branch_edge_count=len(PARENT_EDGES), branch_edges=[],
            executed_instruction_addresses=sorted(sites), case_count=len(make_cases()),
            core_adapter_comparisons=len(rows), total_original_steps=steps,
            total_events=events, rate_prefix_samples=len(rate_rows),
            rate_prefix_steps=rate_steps,
            rate_prefix=[dict(input=source, stored=value) for source, value in rate_rows],
            input_hashes=before, cases=rows,
            domains=['bounded original parent/child composition at core and actual-RET adapter boundaries',
                     'independent arithmetic formula for every release-setting byte']))
        print(f'PASS status initialize original preflight: {len(make_cases())} fixtures x '
              f'core/adapter, {len(sites)}/70 sites, 256 rate prefixes', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_initialize.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-initialize-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
