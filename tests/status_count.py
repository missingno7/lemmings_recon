"""Bounded original/native checks for DrawStatusCount at 762A."""
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
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as interactions
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, END, LOAD = 0x762A, 0x7708, 0x1010
DRAWING_ORIGIN = 0x1F76
GLYPH_SEGMENT_WORD = 0x1FEC
RUNTIME_MIRRORS = {
    0x0008: 0x0F02,
    0x000A: 0x0000,
    0x000C: 0x0C01,
    0x000E: 0x0F08,
    0x0000: 0x0005,
    0x0002: 0x0003,
}
DEFINED_FLAGS = 0x0FD7
CF, PF, AF, ZF, SF, IF, DF, OF = 0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0200, 0x0400, 0x0800
MAX_INSTRUCTIONS, MAX_EVENTS = 512, 8192
WORKER_SECONDS, PROCESS_MIB = 240, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-count-differential.json'
ORIGINAL_REPORT = BUILD / 'status-count-original-differential.json'
CORE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
              'ss', 'sp', 'flags')
RESULT_FIELDS = dict(ax='value', bx='map_cursor', cx='count', dx='auxiliary_value',
                     si='record_cursor', di='object_cursor', bp='candidate_y',
                     cs='code_segment', ds='data_segment', es='extra_segment',
                     ss='stack_segment', sp='stack_offset', flags='flags')
REG_NAMES, REG_IDS = interactions.REG_NAMES, interactions.REG_IDS
MEM = ct.POINTER(ct.c_uint8)

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}


def static_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


EXPECTED_SITES = set(OWN_INS)
EXPECTED_EDGES = static_edges()
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())
interactions.oracle_require(CODE_BYTES == 222 and len(EXPECTED_SITES) == 105,
    f'status-count static boundary changed: {CODE_BYTES} bytes/{len(EXPECTED_SITES)} sites')
interactions.oracle_require(len(EXPECTED_EDGES) == 12,
    f'status-count branch map changed: {sorted(EXPECTED_EDGES)}')


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in (
        'value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
        'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
        'extra_segment', 'stack_segment', 'stack_offset', 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in (
        'value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
        'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
        'extra_segment', 'stack_segment', 'stack_offset', 'flags',
        'continuation', 'status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """A completed C/original comparison differs."""


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


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def canonical_flags(case):
    flags = case.get('flags', 0x00D7) | 2
    flags &= DEFINED_FLAGS | 2
    if case.get('df', False):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('iflag', False):
        flags |= IF
    else:
        flags &= ~IF
    return flags & 0xFFFF


def make_cases():
    cases = []
    for count in range(256):
        cases.append(dict(name=f'count-ah-{count:02x}', count=count, slot=0x25,
                          flags=(0x00D7 | (IF if count & 2 else 0) |
                                 (DF if count & 1 else 0)),
                          seed=0x762A ^ (count * 0x9E3779B1),
                          df=bool(count & 1), iflag=bool(count & 2)))
    cases.extend([
        dict(name='count-stride-11', count=11, slot=0x00, seed=0x1102),
        dict(name='count-stride-15', count=15, slot=0xFF, seed=0x150F),
        dict(name='stack-mirror-live-pop-ax-and-ret', count=17, slot=0x3A,
             sp=0x000C, seed=0xA003),
        dict(name='stack-mirror-blank-pop-and-ret', count=0, slot=0xFE,
             sp=0x000E, seed=0xA004),
        dict(name='vga-stack-live-pop-di', count=23, slot=0x01, ss=0xA000,
             sp=0x1006, origin=0xEED0, seed=0xD104),
        dict(name='live-glyph-segment-after-first-out', count=84, slot=0x80,
             provider_glyph_segment=0x6200, seed=0xFEC5),
        dict(name='df-backward-lodsb-stosb', count=37, slot=0xFE, df=True,
             seed=0xDF37),
        dict(name='if-clear-cli-phase', count=1, slot=0x15, iflag=False,
             seed=0x1F07),
        dict(name='slot-forward-wrap-at-ffff', count=10, slot=0xFF,
             origin=0xDCD3, seed=0xFFFF),
        dict(name='slot-backward-wrap-at-zero', count=18, slot=0x00,
             origin=0xDED2, df=True, seed=0x0001),
        dict(name='glyph-physical-20bit-wrap', count=255, slot=0x55,
             glyph_segment=0xFFFF, seed=0x20B1),
        dict(name='data-stack-segment-alias', count=42, slot=0x91,
             ds=0x5200, ss=0x5200, seed=0xD55A),
        dict(name='ds-ss-push-overwrites-live-glyph-pointer', count=56, slot=0x39,
             ds=0x5200, ss=0x5200, sp=0x1FEE, seed=0x1FEC),
        dict(name='stack-offset-push-wrap', count=9, slot=0xA4,
             ss=0xFFFF, sp=0x0001, seed=0xFFFF),
    ])
    oracle_require(len(cases) == 270, f'expected 270 focused fixtures, got {len(cases)}')
    oracle_require({case['count'] for case in cases[:256]} == set(range(256)),
                   'the complete AH count domain is missing')
    return cases


def setup(case):
    seed = case['seed'] & 0xFFFFFFFF
    rng = random.Random(seed)
    memory = bytearray(SIZE)
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    base = (LOAD << 4) & MASK
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    memory[:len(loaded) - first] = loaded[first:]

    ds = case.get('ds', 0x4200) & 0xFFFF
    ss = case.get('ss', 0x5200) & 0xFFFF
    sp = case.get('sp', 0x7000) & 0xFFFF
    glyph_segment = case.get('glyph_segment', 0x6000) & 0xFFFF
    alt_glyph_segment = case.get('provider_glyph_segment', glyph_segment) & 0xFFFF
    regs = {name: ((0x3217 * (index + 5) + seed * 13 + 0x51A3) & 0xFFFF)
            for index, name in enumerate(REG_NAMES)}
    regs.update(ax=((case['count'] & 0xFF) << 8) | (case['slot'] & 0xFF),
                bx=0xC217, cx=0x8A51, dx=0x3CE0, si=0x5123, di=0x42A7,
                bp=0x6D93, cs=LOAD, ip=ENTRY, ds=ds, es=0x7131,
                ss=ss, sp=sp, flags=canonical_flags(case))

    # Both source halves are patterned well beyond the nominal ten glyphs.
    # Segment-relative stores preserve 20-bit wrap for the FFFF witness.
    data_segments = {ds}
    for segment, salt in ((glyph_segment, 0x31), (alt_glyph_segment, 0xA7),
                          *((segment, 0x5D) for segment in data_segments)):
        for offset in range(0x240):
            put8(memory, segment, offset,
                 ((offset * 37 + seed * 11 + salt * 19) ^ (offset >> 2)) & 0xFF)
    origin = case.get('origin', (0x0137 + seed * 19) & 0xFFFF)
    put16(memory, ds, DRAWING_ORIGIN, origin)
    put16(memory, ds, GLYPH_SEGMENT_WORD, glyph_segment)
    return_word = case.get('return_word', (0xA531 + seed * 7) & 0xFFFF)
    put16(memory, ss, sp, return_word)

    device = MinimapVga(seed ^ 0x762A, read_map=(seed >> 3) & 3)
    # The routine changes only these VGA registers; keep the aperture mapping
    # valid even for pushes to an A000-backed stack before its first OUT.
    device.seq[2], device.seq[4] = 0x0F, 0x06
    device.gc[0], device.gc[1], device.gc[3] = 0, 0, 0
    device.gc[5], device.gc[6], device.gc[8] = 0, 0x05, 0xFF
    if ss == 0xA000:
        device.gc[4] = 0
        device.planes[0][sp] = return_word & 0xFF
        device.planes[0][(sp + 1) & 0xFFFF] = (return_word >> 8) & 0xFF
    return memory, regs, device


class CountAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def access(self, kind, address, flags, mask=DEFINED_FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('status-count bus event budget exhausted')
        return super().access(kind, address, flags, mask, value)

    def out_word(self, port, value, flags, mask=DEFINED_FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('status-count OUT event budget exhausted')
        if port not in (0x03C4, 0x03CE) or self.device is None:
            raise interactions.OracleFailure(f'unexpected status-count OUT {port:04X}')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        index = self.out_count
        self.out_count += 1
        if index == 0 and self.case.get('provider_glyph_segment') is not None:
            self.used.add('glyph-segment-after-first-out')
            put16(self.memory, self.regs['ds'], GLYPH_SEGMENT_WORD,
                  self.case['provider_glyph_segment'])
            if self.mirror is not None:
                address = physical(self.regs['ds'], GLYPH_SEGMENT_WORD)
                self.mirror(address, self.case['provider_glyph_segment'] & 0xFF)
                self.mirror(address + 1, self.case['provider_glyph_segment'] >> 8)


def live_first_pop_ax(case, regs):
    offset = (regs['sp'] - 4) & 0xFFFF
    if offset in RUNTIME_MIRRORS:
        return RUNTIME_MIRRORS[offset]
    return regs['ax']


def live_glyph_segment(case, regs):
    if (regs['ds'] == regs['ss'] and
            ((regs['sp'] - 2) & 0xFFFF) == GLYPH_SEGMENT_WORD):
        return regs['ds']
    return case.get('provider_glyph_segment',
                    case.get('glyph_segment', 0x6000)) & 0xFFFF


def stack_word_reads(events, segment, offset):
    low = physical(segment, offset)
    high = (low + 1) & MASK
    rows = [event for event in events if event[0] == 'read']
    words = []
    for index in range(len(rows) - 1):
        if rows[index][1] == low and rows[index + 1][1] == high:
            words.append(rows[index][2] | (rows[index + 1][2] << 8))
    return words


def expected_source_reads(first_ax, second_ax, regs, glyph_segment):
    count = (first_ax >> 8) & 0xFF
    if count == 0:
        return []
    quotient = count // 10
    remainder = (second_ax >> 8) & 0xFF
    delta = -1 if regs['flags'] & DF else 1
    offsets = [((quotient * 16 + row * delta) & 0xFFFF) for row in range(8)]
    offsets += [((remainder * 16 + 8 + row * delta) & 0xFFFF)
                for row in range(8)]
    return [(physical(glyph_segment, offset), offset) for offset in offsets]


def project_pixels(case, initial_memory, regs, initial_device, glyph_segment):
    """Independent sequential replay of the two eight-row glyph cells."""
    if regs['ss'] == 0xA000 or regs['ds'] == 0xA000:
        return None
    expected = copy.deepcopy(initial_device)
    memory = bytearray(initial_memory)
    expected.out(0x03C4, 0x0F02, regs['flags'])
    expected.out(0x03CE, 0x0000, regs['flags'])
    expected.out(0x03CE, 0x0C01, regs['flags'])
    expected.out(0x03CE, 0x0005, regs['flags'])
    expected.out(0x03CE, 0x0003, regs['flags'])
    expected.out(0x03CE, 0x0F08, regs['flags'])

    entry_slot = regs['ax'] & 0xFF
    origin = get16(initial_memory, regs['ds'], DRAWING_ORIGIN)
    first_di = (2 * entry_slot + 0x212C + origin + 2) & 0xFFFF
    live_ax = live_first_pop_ax(case, regs)
    count = (live_ax >> 8) & 0xFF
    direction = -1 if regs['flags'] & DF else 1
    if count:
        quotient, remainder = divmod(count, 10)
        sources = (quotient * 16, remainder * 16 + 8)
        starts = (first_di, (first_di + 1) & 0xFFFF)
        for cell, (source_start, output_start) in enumerate(zip(sources, starts)):
            if cell:
                expected.out(0x03CE, 0xF008, regs['flags'])
            source = source_start
            dest = output_start
            for _row in range(8):
                address = VGA_BASE + dest
                expected.latches = [plane[dest] for plane in expected.planes]
                memory[address] = expected.latches[expected.gc[4] & 3]
                source_value = memory[physical(glyph_segment, source)]
                expected.write(memory, address, source_value, regs['flags'])
                source = (source + direction) & 0xFFFF
                dest = (dest + direction) & 0xFFFF
                dest = (dest + 0x2B) & 0xFFFF
    else:
        for cell, output_start in enumerate((first_di, (first_di + 1) & 0xFFFF)):
            if cell:
                expected.out(0x03CE, 0xF008, regs['flags'])
            dest = output_start
            for _row in range(8):
                address = VGA_BASE + dest
                expected.latches = [plane[dest] for plane in expected.planes]
                memory[address] = expected.latches[expected.gc[4] & 3]
                expected.write(memory, address, 0xFF, regs['flags'])
                dest = (dest + direction) & 0xFFFF
                dest = (dest + 0x2B) & 0xFFFF
    return expected


def assert_independent(case, initial_memory, regs, initial_device, observed):
    glyph_segment = live_glyph_segment(case, regs)
    saved_ax = stack_word_reads(observed['events'], regs['ss'],
                                (regs['sp'] - 4) & 0xFFFF)
    oracle_require(saved_ax, f"{case['name']}: original did not read the live saved AX word")
    first_ax = saved_ax[0]
    oracle_require(first_ax == live_first_pop_ax(case, regs),
        f"{case['name']}: setup stack/VGA projection predicts POP AX "
        f"{live_first_pop_ax(case, regs):04X}, original read {first_ax:04X}")
    first_count = (first_ax >> 8) & 0xFF
    second_ax = 0
    if first_count:
        oracle_require(len(saved_ax) >= 2,
                       f"{case['name']}: original did not read post-glyph live POP AX")
        second_ax = saved_ax[1]
        if regs['ss'] != 0xA000:
            quotient, remainder = divmod(first_count, 10)
            pushed_quotient_remainder = (remainder << 8) | quotient
            oracle_require(second_ax == pushed_quotient_remainder,
                f"{case['name']}: independent ordinary-stack quotient/remainder word "
                f"{pushed_quotient_remainder:04X}/{second_ax:04X}")
    expected_reads = expected_source_reads(first_ax, second_ax, regs, glyph_segment)
    actual_source = [(event[1], event[2]) for event in observed['events']
                     if event[0] == 'read' and
                     event[1] in {address for address, _offset in expected_reads}]
    want_source = [(address, initial_memory[address]) for address, _offset in expected_reads]
    oracle_require(actual_source == want_source,
        f"{case['name']}: independent quotient/remainder glyph source sequence differs: "
        f'{actual_source!r}/{want_source!r}')
    if regs['ss'] != 0xA000:
        pixel_writes = [event for event in observed['events']
                        if event[0] == 'write' and VGA_BASE <= event[1] < VGA_END]
        oracle_require(len(pixel_writes) == 16,
                       f"{case['name']}: expected 16 sequential VGA destination writes, got {len(pixel_writes)}")
    oracle_require(sum(event[0] == 'out' for event in observed['events']) == 7,
                   f"{case['name']}: expected six setup ports and one second-cell mask OUT")
    projected = project_pixels(case, initial_memory, regs, initial_device, glyph_segment)
    if projected is not None:
        oracle_require(projected.state() == observed['device'].state(),
            f"{case['name']}: independent 8+8 VGA plane/latch replay differs")


def make_instruction_map():
    return OWN_INS


def original(case, memory, regs, device, *, core):
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), core,
        entry_flag_mask=DEFINED_FLAGS, main_instructions=make_instruction_map(),
        instruction_limit=MAX_INSTRUCTIONS, access_factory=CountAccess)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = CountAccess(case, memory, regs, device)
        self.events, self.used = self.access.events, self.access.used

        def read(_ctx, _mem, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-count read callback failed: {error}')
                return 0

        def write(_ctx, _mem, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-count write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-count OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-count-m{mutation}.dll',
                     mutation, 'status_count')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_status_count_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_status_count_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs_dict = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs_dict, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**regs_dict)
        if core:
            call = Call(*(regs_dict[name] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(callback.bus))
            for name in CORE_NAMES:
                setattr(regs, name, getattr(result, RESULT_FIELDS[name]))
            regs.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(regs), ct.byref(callback.bus))
        final = {name: getattr(regs, name) & 0xFFFF for name in REG_NAMES}
        return dict(memory=bytes(memory), regs=final, events=callback.events,
                    used=set(callback.used), device=device, status=status,
                    continuation=final['ip'], out_count=callback.access.out_count)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered bus event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    expected = original(case, initial, regs, device, core=core)
    assert_independent(case, initial, regs, device, expected)
    if core:
        oracle_require(expected['continuation'] ==
                       (0x7707 if live_first_pop_ax(case, regs) >> 8 == 0 else 0x76DA),
                       case['name'] + ': original reached the wrong core return boundary')
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == 0, f'{label}: status {actual["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    for name in REG_NAMES:
        if name == 'flags':
            require(((actual['regs'][name] ^ expected['regs'][name]) &
                     expected['flag_mask']) == 0,
                    f'{label}: defined FLAGS {actual["regs"][name]:04X}/'
                    f'{expected["regs"][name]:04X}')
        else:
            require(actual['regs'][name] == expected['regs'][name],
                    f'{label}: {name} {actual["regs"][name]:04X}/'
                    f'{expected["regs"][name]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: provider observations {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA planes/latches/registers differ')
    return dict(name=case['name'], core=core,
                sites=sorted(off for source, off in expected['sites'] if source == 'main'),
                edges=[list(edge[1:]) for edge in sorted(expected['edges'])
                       if edge[0] == 'main'],
                steps=expected['steps'], events=len(expected['events']),
                plane_check=('independent sequential 8+8 glyph replay'
                             if regs['ss'] != 0xA000 and regs['ds'] != 0xA000
                             else 'full device comparison with A000-backed alias'))


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/status-display.md', 'assets/vgalemmi.exe',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/inputs.json',
        'metadata/regions.json', 'metadata/hints.json', 'metadata/toolchain-lock.json',
        'src/program.asm', 'src/image_tail.asm', 'src/status_glyphs.asm',
        'src/game_code_before_minimap.asm', 'c/status_count.c', 'c/status_count.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/status_count.py', 'tests/entity_interactions.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py', 'tools/resources.py',
        'tests/minimap_vga.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/unpack.py', 'tools/difftest.py',
        'tools/coverage.py', 'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'required input hashes missing: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'status-count inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = original(case, initial, regs, device, core=core)
            assert_independent(case, initial, regs, device, expected)
            own_sites = {off for source, off in expected['sites'] if source == 'main'}
            own_edges = {edge[1:] for edge in expected['edges'] if edge[0] == 'main'}
            rows.append(dict(name=case['name'], core=core,
                             sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == EXPECTED_SITES,
        f'original site union differs: missing={sorted(EXPECTED_SITES-sites)} '
        f'extra={sorted(sites-EXPECTED_SITES)}')
    oracle_require(edges == EXPECTED_EDGES,
        f'original branch outcomes differ: missing={sorted(EXPECTED_EDGES-edges)} '
        f'extra={sorted(edges-EXPECTED_EDGES)}')
    oracle_require(before == input_hashes(), 'status-count inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'status-count inputs changed before native worker')
    specs = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == EXPECTED_SITES,
        f'native-comparison site union differs: missing={sorted(EXPECTED_SITES-sites)}')
    oracle_require(edges == EXPECTED_EDGES,
        f'native-comparison branch outcomes differ: missing={sorted(EXPECTED_EDGES-edges)}')

    by_name = {case['name']: case for case in specs}
    witnesses = {
        1: ('count-ah-64', True),
        2: ('count-stride-11', True),
        3: ('stack-mirror-live-pop-ax-and-ret', True),
        4: ('vga-stack-live-pop-di', True),
        5: ('live-glyph-segment-after-first-out', True),
        6: ('df-backward-lodsb-stosb', True),
        7: ('if-clear-cli-phase', True),
    }
    mutants = []
    for mutation, (name, core) in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise interactions.OracleFailure(f'status-count mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'status-count inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(EXPECTED_SITES),
        static_instruction_addresses=sorted(EXPECTED_SITES),
        branch_edge_count=len(EXPECTED_EDGES),
        static_branch_edges=[list(e) for e in sorted(EXPECTED_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutants), mutations=mutants,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(e) for e in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='DrawStatusCount 762A..7707: every AH byte count at one slot plus slot, '
               'stack, segment, source-pointer provider, DF/IF phase and address-wrap fixtures; '
               'the core stops at its selected live RET and the adapter consumes actual SS:SP.'))
    print(f'PASS status count: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-count-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, edges = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(EXPECTED_SITES),
            static_instruction_addresses=sorted(EXPECTED_SITES),
            branch_edge_count=len(EXPECTED_EDGES), branch_edges=[list(e) for e in sorted(edges)],
            executed_instruction_addresses=sorted(sites), case_count=len(make_cases()),
            core_adapter_comparisons=len(rows), input_hashes=before, cases=rows,
            domain='Original-only 256-count byte domain, actual-RET adapters and independent 8+8 VGA replay.'))
        print(f'PASS status count original preflight: {len(make_cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_count.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-count-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
