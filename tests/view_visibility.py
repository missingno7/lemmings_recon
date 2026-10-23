"""Bounded original/native checks for the 410F view-visibility-map producer."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as interactions
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
DEFAULT_LOAD = 0x0000
ENTRY, RETURN, END = 0x410F, 0x414E, 0x414F
DEFINED_FLAGS = interactions.FLAGS
CF, IF, DF = 0x0001, 0x0200, 0x0400
MAP_CLEAR_START, MAP_CLEAR_WORDS = 0x0EA8, 0x68
MAP_FILL_BYTES = 0x29
MAX_INSTRUCTIONS, MAX_EVENTS = 512, 2048
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'view-visibility-differential.json'
ORIGINAL_REPORT = BUILD / 'view-visibility-original-differential.json'

CORE_FIELDS = ('value', 'map_cursor', 'count', 'auxiliary_value',
               'record_cursor', 'object_cursor', 'candidate_y',
               'code_segment', 'data_segment', 'extra_segment',
               'stack_segment', 'stack_offset', 'flags')
CORE_REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')
RESULT_FIELDS = dict(zip(CORE_REGS, CORE_FIELDS))
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    # runtime_stack_segment is the relocated immediate at 4137h, distinct
    # from the caller's live SS field above.
    _fields_ = [(name, ct.c_uint16) for name in CORE_FIELDS +
                ('runtime_stack_segment',)]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                CORE_FIELDS + ('continuation', 'status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The original execution or a declared bound/domain failed."""


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


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


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
VIS_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
VIS_SITES = set(VIS_INS)
VIS_EDGES = set()
VIS_BYTES = sum(ins.size for ins in VIS_INS.values())
oracle_require(VIS_BYTES == 64 and len(VIS_SITES) == 27 and
               RETURN in VIS_INS and VIS_INS[RETURN].mnemonic == 'ret',
               f'view-visibility source boundary changed: {VIS_BYTES} bytes/'
               f'{len(VIS_SITES)} sites')


def make_cases():
    common = dict(base=0x0180, marker_a=0x0042, marker_b=0x0057,
                  ds=0x3500, ss=0x5200, sp=0x7000,
                  es=0x6C20, flags=0x0203, outer_return=0x4C35)
    return [
        dict(name='ordinary-forward-fill', **common, seed=0x410F01),
        dict(name='reverse-clear-and-fill-df', **{**common, 'flags': 0x0603},
             seed=0x410F02),
        dict(name='zero-base-wraps-two-decrements', **{**common, 'base': 0},
             seed=0x410F03),
        dict(name='one-unit-base', **{**common, 'base': 1}, seed=0x410F04),
        dict(name='base-exactly-eight', **{**common, 'base': 8}, seed=0x410F05),
        dict(name='base-near-clear-boundary', **{**common, 'base': 0x00F8},
             seed=0x410F06),
        dict(name='largest-base', **{**common, 'base': 0xFFFF}, seed=0x410F07),
        dict(name='incoming-if-clear', **{**common, 'flags': 0x0003},
             seed=0x410F08),
        dict(name='incoming-if-and-df-set', **{**common, 'flags': 0x0603},
             seed=0x410F09),
        dict(name='data-and-stack-segment-alias', **{**common, 'ds': 0x5200,
             'ss': 0x5200}, seed=0x410F0A),
        dict(name='push-slot-aliases-clear-and-caller-word',
             **{**common, 'ds': 0x3500, 'es': 0x3500, 'ss': 0x3500,
                'sp': 0x0EAA, 'load': 0x1010},
             seed=0x410F0B),
        dict(name='runtime-marker-segment-aliases-ds',
             **{**common, 'ds': 0x143E, 'marker_a': 0x0028,
                'marker_b': 0x0044}, seed=0x410F0C),
        dict(name='live-stack-segment-equals-relocated-marker-segment',
             **{**common, 'ss': 0x143E, 'sp': 0x8100}, seed=0x410F0D),
        dict(name='markers-at-offset-wrap-boundaries',
             **{**common, 'marker_a': 0xFFFF, 'marker_b': 0x0000},
             seed=0x410F0E),
        dict(name='physical-push-word-wrap', **{**common, 'ss': 0xFFFF,
             'sp': 0x0011}, seed=0x410F0F),
        dict(name='physical-caller-return-word-wrap', **{**common, 'ss': 0xFFFC,
             'sp': 0x003F}, seed=0x410F10),
        dict(name='provider-changes-map-base-during-clear',
             **{**common, 'es': 0x3500}, provider='clear-map-base',
             provider_base=0x0380, seed=0x410F11),
        dict(name='provider-changes-second-marker-offset', **common,
             provider='second-marker-offset', provider_marker_b=0x00A6,
             seed=0x410F12),
        dict(name='same-marker-offset-written-twice',
             **{**common, 'marker_b': common['marker_a']}, seed=0x410F13),
        dict(name='poisoned-untouched-memory', **common, poison=True,
             seed=0x410F14),
        dict(name='entry-register-poison-and-flags',
             **{**common, 'flags': 0x0AD7}, poison=True, seed=0x410F15),
        dict(name='zero-valued-marker-offsets', **{**common, 'marker_a': 0,
             'marker_b': 0}, seed=0x410F16),
        dict(name='fill-overwrites-cleared-forward-area',
             **{**common, 'base': 0x00F8}, seed=0x410F17),
        dict(name='map-base-read-wraps-fill-offset',
             **{**common, 'base': 0xFFF8, 'flags': 0x0603}, seed=0x410F18),
        dict(name='caller-return-gets-overwritten-by-clear',
             **{**common, 'ds': 0x3500, 'es': 0x3500, 'ss': 0x3500,
                'sp': 0x0EAA, 'load': 0x1010,
                'outer_return': 0x7123}, seed=0x410F19),
        dict(name='relocated-immediate-at-load-1010', **common,
             load=0x1010, seed=0x410F1A),
        dict(name='relocated-immediate-at-load-2345', **common,
             load=0x2345, seed=0x410F1B),
        dict(name='provider-changes-live-pop-es', **common,
             provider='live-pop-es', provider_es=0x6100, seed=0x410F1C),
    ]


def setup(case):
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE) if case.get('poison') else SIZE)
    load = case.get('load', DEFAULT_LOAD)
    load_image = relocated(IMAGE, ORACLE['relocations'], load)
    linear = physical(load, 0)
    first = min(len(load_image), SIZE - linear)
    memory[linear:linear + first] = load_image[:first]
    memory[:len(load_image) - first] = load_image[first:]

    regs = ({name: rng.randrange(0x10000) for name in interactions.REG_NAMES}
            if case.get('poison') else
            {name: ((0x410F * (i + 3) + 0x3501) & 0xFFFF)
             for i, name in enumerate(interactions.REG_NAMES)})
    regs.update(ax=case.get('ax', 0xB5A5), bx=case.get('bx', 0xC217),
                cx=case.get('cx', 0x8A51), dx=case.get('dx', 0x3CE0),
                si=case.get('si', 0x5123), di=case.get('di', 0x42A7),
                bp=case.get('bp', 0x6D93), cs=load, ds=case.get('ds', 0x3500),
                es=case.get('es', 0x6C20), ss=case.get('ss', 0x5200),
                sp=case.get('sp', 0x7000), ip=ENTRY, flags=case.get('flags', 0x0203))
    runtime_stack_segment = get16(memory, load, 0x4137)
    expected_runtime = (load + 0x143E) & 0xFFFF
    oracle_require(runtime_stack_segment == expected_runtime,
                   f'{case["name"]}: relocated 143E operand '
                   f'{runtime_stack_segment:04X}/{expected_runtime:04X}')

    ds = regs['ds']
    put16(memory, ds, 0x0000, case.get('base', 0x0180))
    put16(memory, ds, 0x0026, case.get('marker_a', 0x0042))
    put16(memory, ds, 0x0028, case.get('marker_b', 0x0057))
    put16(memory, regs['ss'], regs['sp'], case.get('outer_return', 0x4C35))

    for address, ins in VIS_INS.items():
        expected = load_image[address:address + ins.size]
        actual = bytes(memory[(physical(load, address) + i) & MASK]
                       for i in range(ins.size))
        oracle_require(actual == expected,
                       f'{case["name"]}: setup changed executable byte at {address:04X}')
    return memory, regs, runtime_stack_segment


class VisibilityAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, _device):
        super().__init__(case, memory, regs, None)
        self.runtime_stack_segment = case.get('_runtime_stack_segment',
                                              (case.get('load', DEFAULT_LOAD) +
                                               0x143E) & 0xFFFF)

    def _provider(self, kind, address):
        provider = self.case.get('provider')
        ds = self.case.get('ds', 0x3500)
        if (provider == 'live-pop-es' and kind == 'read' and
                'live-pop-es' not in self.used):
            ss = self.case.get('ss', 0x5200)
            sp = self.case.get('sp', 0x7000)
            if address == physical(ss, (sp - 2) & 0xFFFF):
                self.modify_word(ss, (sp - 2) & 0xFFFF,
                                 self.case['provider_es'])
                self.used.add('live-pop-es')
        elif provider == 'clear-map-base' and kind == 'write' and 'clear-map-base' not in self.used:
            if address == physical(ds, MAP_CLEAR_START):
                self.modify_word(ds, 0, self.case['provider_base'])
                self.used.add('clear-map-base')
        elif (provider == 'second-marker-offset' and kind == 'write' and
              'second-marker-offset' not in self.used):
            marker_a = self.case.get('marker_a', 0x0042)
            target = physical(self.runtime_stack_segment, marker_a)
            if address == target:
                self.modify_word(ds, 0x0028, self.case['provider_marker_b'])
                self.used.add('second-marker-offset')


def original(case, memory, regs, runtime_stack_segment, *, core):
    actual_case = dict(case, _runtime_stack_segment=runtime_stack_segment)
    load_image = relocated(IMAGE, ORACLE['relocations'], regs['cs'])
    with patch.object(interactions, 'IMAGE', load_image):
        return interactions.original(
            actual_case, bytearray(memory), dict(regs), None, core,
            entry_flag_mask=DEFINED_FLAGS, main_instructions=VIS_INS,
            stop_offsets={RETURN: 0} if core else None,
            access_factory=VisibilityAccess, instruction_limit=MAX_INSTRUCTIONS)


def independent_projection(case, initial_memory, initial_regs, runtime_stack_segment):
    """Replay the three memory phases without interpreting the instruction stream."""
    memory = bytearray(initial_memory)
    ds, ss, sp = initial_regs['ds'], initial_regs['ss'], initial_regs['sp']
    step = -1 if initial_regs['flags'] & DF else 1
    used = set()

    # PUSH DS / POP ES uses the caller's existing stack; it creates no new frame.
    put16(memory, ss, (sp - 2) & 0xFFFF, ds)
    if case.get('provider') == 'live-pop-es':
        put16(memory, ss, (sp - 2) & 0xFFFF, case['provider_es'])
        used.add('live-pop-es')
    es = get16(memory, ss, (sp - 2) & 0xFFFF)

    di = MAP_CLEAR_START
    for index in range(MAP_CLEAR_WORDS):
        put16(memory, es, di, 0)
        if (case.get('provider') == 'clear-map-base' and
                'clear-map-base' not in used and index == 0):
            put16(memory, ds, 0, case['provider_base'])
            used.add('clear-map-base')
        di = (di + 2 * step) & 0xFFFF

    base = get16(memory, ds, 0)
    shifted = base
    for _ in range(3):
        shifted >>= 1
    before_add = (shifted - 2) & 0xFFFF
    di = ((before_add + MAP_CLEAR_START) & 0xFFFF)
    for _ in range(MAP_FILL_BYTES):
        put8(memory, es, di, 0x01)
        di = (di + step) & 0xFFFF

    marker_a = get16(memory, ds, 0x0026)
    put8(memory, runtime_stack_segment, marker_a, 0xFF)
    if case.get('provider') == 'second-marker-offset':
        put16(memory, ds, 0x0028, case['provider_marker_b'])
        used.add('second-marker-offset')
    marker_b = get16(memory, ds, 0x0028)
    put8(memory, runtime_stack_segment, marker_b, 0xFF)

    wide = before_add + MAP_CLEAR_START
    add_result = wide & 0xFFFF
    add_flags = 0
    low = add_result & 0xFF
    if (low.bit_count() & 1) == 0:
        add_flags |= 0x0004
    if add_result == 0:
        add_flags |= 0x0040
    if add_result & 0x8000:
        add_flags |= 0x0080
    if wide > 0xFFFF:
        add_flags |= 0x0001
    if (before_add ^ MAP_CLEAR_START ^ add_result) & 0x0010:
        add_flags |= 0x0010
    if (~(before_add ^ MAP_CLEAR_START) & (before_add ^ add_result) & 0x8000):
        add_flags |= 0x0800
    final_flags = ((initial_regs['flags'] & ~0x08D5) | add_flags | IF) & 0xFFFF

    return memory, dict(es=es, ax=es, bx=marker_b, cx=runtime_stack_segment,
                        di=di, flags=final_flags), used


def observed_sites(result):
    return {off for source, off in result['sites']
            if source == 'main' and off in VIS_SITES}


def observed_edges(result):
    return {edge[1:] for edge in result['edges']
            if edge[0] == 'main' and edge[1] in VIS_SITES}


def assert_independent(case, initial_memory, initial_regs, runtime_stack_segment,
                       result, *, core):
    oracle_require(result['status'] == 0,
                   f'{case["name"]}: original status {result["status"]}, expected READY')
    projected, role_expectations, used = independent_projection(
        case, initial_memory, initial_regs, runtime_stack_segment)
    if not core:
        # The only post-body operation is the caller's real RET. Its word may
        # have been changed by an intentional stack/map alias.
        return_word = get16(projected, initial_regs['ss'], initial_regs['sp'])
        role_expectations['ip'] = return_word
        oracle_require(result['regs']['sp'] ==
                       ((initial_regs['sp'] + 2) & 0xFFFF),
                       case['name'] + ': actual caller RET did not consume SS:SP')
        oracle_require(result['regs']['ip'] == return_word,
                       case['name'] + ': RET target differs from independently projected word')
    else:
        role_expectations['ip'] = RETURN
        oracle_require(result['continuation'] == RETURN,
                       case['name'] + ': logical core did not stop before actual RET')
        oracle_require(result['regs']['sp'] == initial_regs['sp'],
                       case['name'] + ': core consumed the caller return word')

    role_expectations.update(ds=initial_regs['ds'], ss=initial_regs['ss'],
                             cs=initial_regs['cs'], si=initial_regs['si'],
                             bp=initial_regs['bp'], dx=initial_regs['dx'],
                             es=role_expectations['es'])
    oracle_require(result['memory'] == bytes(projected),
                   case['name'] + ': independent clear/fill/marker projection differs')
    for name, expected in role_expectations.items():
        oracle_require(result['regs'][name] == expected,
                       f'{case["name"]}: independent {name} '
                       f'{result["regs"][name]:04X}/{expected:04X}')
    oracle_require(((result['regs']['flags'] ^ role_expectations['flags']) &
                    DEFINED_FLAGS) == 0,
                   case['name'] + ': independent final FLAGS differ')
    if case.get('provider'):
        oracle_require(result['used'] == used,
                       f'{case["name"]}: provider effects {result["used"]}/{used}')
    oracle_require(observed_sites(result) == VIS_SITES - ({RETURN} if core else set()),
                   f'{case["name"]}: owned sites differ at requested boundary')
    oracle_require(observed_edges(result) == VIS_EDGES,
                   f'{case["name"]}: unexpected branch edges')


def input_hashes():
    paths = {
        'assets/vgalemmi.exe', 'metadata/inputs.json', 'metadata/oracle.json',
        'metadata/toolchain-lock.json',
        'src/game_code_late_after_selection.asm', 'src/view_visibility.asm',
        'src/image_tail.asm', 'src/program.asm',
        'c/view_visibility.c', 'c/view_visibility.h', 'c/lemmings_sym.h',
        'c/special_blit.h', 'c/regs.h',
        'tests/view_visibility.py', 'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tools/resources.py', 'tools/unpack.py',
        'tools/common.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/difftest.py',
    }
    missing = sorted(path for path in paths if not (ROOT / path).is_file())
    oracle_require(not missing, 'required view-visibility inputs missing: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'view-visibility inputs changed before original campaign')
    rows, sites = [], set()
    total_steps = total_events = 0
    for case in specs:
        initial, regs, runtime_stack_segment = setup(case)
        for core in (True, False):
            expected = original(case, initial, regs, runtime_stack_segment, core=core)
            assert_independent(case, initial, regs, runtime_stack_segment, expected, core=core)
            own = observed_sites(expected)
            rows.append(dict(name=case['name'], core=core, status=expected['status'],
                             continuation=expected['continuation'],
                             instruction_sites=sorted(own),
                             steps=expected['steps'], events=len(expected['events']),
                             providers=sorted(expected['used'])))
            sites.update(own)
            total_steps += expected['steps']
            total_events += len(expected['events'])
        del initial, regs
        gc.collect()
    oracle_require(sites == VIS_SITES,
                   f'view-visibility executed sites differ: missing={sorted(VIS_SITES-sites)}')
    oracle_require(before == input_hashes(), 'view-visibility inputs changed during original campaign')
    return rows, sites, total_steps, total_events


class NativeBus:
    def __init__(self, case, memory, regs, runtime_stack_segment):
        actual_case = dict(case, _runtime_stack_segment=runtime_stack_segment)
        self.access = VisibilityAccess(actual_case, memory, regs, None)
        self.events, self.used = self.access.events, self.access.used

        def read(_context, _memory, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'view-visibility native read callback failed: {error}')

        def write(_context, _memory, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'view-visibility native write callback failed: {error}')

        def output(_context, port, value, flags):
            worker_exit(CALLBACK_EXIT,
                        f'unexpected view-visibility OUT {port:04X}={value:04X} '
                        f'FLAGS={flags:04X}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'view-visibility-m{mutation}.dll',
                     mutation, 'view_visibility')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_rebuild_view_visibility_map_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_rebuild_view_visibility_map_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs), ct.c_uint16,
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial_memory, initial_regs, runtime_stack_segment, *, core):
        memory = bytearray(initial_memory)
        regs_values = dict(initial_regs)
        callback = NativeBus(case, memory, regs_values, runtime_stack_segment)
        native_memory = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs_values)
        if core:
            call = Call(*(regs_values[name] for name in CORE_REGS), runtime_stack_segment)
            result = self.core(native_memory, ct.byref(call), ct.byref(callback.bus))
            for name in CORE_REGS:
                setattr(state, name, getattr(result, RESULT_FIELDS[name]))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(native_memory, ct.byref(state),
                                  runtime_stack_segment, ct.byref(callback.bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs, events=callback.events,
                    used=set(callback.used), status=status,
                    continuation=final_regs['ip'])


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered memory-event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, runtime_stack_segment = setup(case)
    expected = original(case, initial, regs, runtime_stack_segment, core=core)
    assert_independent(case, initial, regs, runtime_stack_segment, expected, core=core)
    actual = native.run(case, initial, regs, runtime_stack_segment, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    if actual['memory'] != expected['memory']:
        mismatch = next(i for i, (a, b) in enumerate(zip(actual['memory'], expected['memory']))
                        if a != b)
        raise Mismatch(f'{label}: full RAM differs at {mismatch:05X}: '
                       f'{actual["memory"][mismatch]:02X}/{expected["memory"][mismatch]:02X}')
    for name in interactions.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: providers {actual["used"]}/{expected["used"]}')
    return dict(name=case['name'], core=core, status=actual['status'],
                continuation=actual['continuation'], instruction_sites=sorted(observed_sites(expected)),
                steps=expected['steps'], events=len(expected['events']),
                providers=sorted(expected['used']))


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'view-visibility inputs changed before native worker')
    specs = make_cases()
    baseline = Native(directory)
    rows, sites = [], set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['instruction_sites'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == VIS_SITES,
                   f'native view-visibility sites differ: missing={sorted(VIS_SITES-sites)}')

    lookup = {case['name']: case for case in specs}
    witnesses = {
        1: 'reverse-clear-and-fill-df',
        2: 'provider-changes-map-base-during-clear',
        3: 'base-exactly-eight',
        4: 'zero-base-wraps-two-decrements',
        5: 'incoming-if-and-df-set',
        6: 'ordinary-forward-fill',
        7: 'ordinary-forward-fill',
        8: 'provider-changes-second-marker-offset',
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
            raise OracleFailure(f'view-visibility mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'view-visibility inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        translated_code_bytes=VIS_BYTES, instruction_sites=len(VIS_SITES),
        static_instruction_addresses=sorted(VIS_SITES),
        branch_edge_count=len(VIS_EDGES), static_branch_edges=[],
        case_count=len(specs), core_adapter_comparisons=len(rows),
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
            '410F..414E shared visibility producer: 64 bytes/27 original sites; no new guest CALL frame',
            'load-segment 0000 plus relocated 1010 and 2345 views of the 143E immediate',
            'live DS:0000 base after clear; DF-sensitive 68-word clear and 29-byte fill with 16-bit offset wrap',
            'PUSH DS/POP ES through actual SS:SP, including a live saved-word provider change; runtime marker segment is distinct from live SS',
            'live DS:0026/0028 marker reads, CLI write phase, restored ES and final STI',
            'full 1 MiB RAM, 13 logical register roles, defined FLAGS and ordered byte accesses',
            'independent sequential clear/fill/marker projection; no semantic extent or lifetime inferred']))
    print(f'PASS view visibility: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)}/27 sites, {total_events} bus events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='view-visibility-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, steps, events = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=VIS_BYTES, instruction_sites=len(VIS_SITES),
            static_instruction_addresses=sorted(VIS_SITES), branch_edge_count=0,
            branch_edges=[], executed_instruction_addresses=sorted(sites),
            case_count=len(make_cases()), core_adapter_comparisons=len(rows),
            total_original_steps=steps, total_events=events, input_hashes=before,
            cases=rows, domains=['bounded original execution at pre-RET core and actual-RET adapter boundaries',
                                 'independent sequential clear/fill/marker projection',
                                 'explicit 0000, 1010 and 2345 relocated load-segment views']))
        print(f'PASS view visibility original preflight: {len(make_cases())} fixtures '
              f'x core/adapter, {len(sites)}/27 sites, {events} events', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: view_visibility.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='view-visibility-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
