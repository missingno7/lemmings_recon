"""Bounded original/native checks for MarkEntityDrawingDirty (5726)."""
from __future__ import annotations

import ctypes as ct
import gc
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, read_json, sha, write_json
import entity_interactions as interactions
import view_visibility as visibility
from unpack import ASSET, unpack

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END, RETURN_IP = 0x5726, 0x57D1, 0x57D0
MAIN_SEG = interactions.MAIN_SEG
DATA_SEGMENT = (MAIN_SEG + 0x09A9) & 0xFFFF
MAP_WORD = 0x0026
VISIBILITY_BASE = 0x0EA8
MAX_INSTRUCTIONS, MAX_EVENTS = 30000, 5000
MAX_MODEL_WRITES = MAX_EVENTS
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-dirty-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-dirty-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row
        for row in read_json(ROOT / 'metadata/symbols.json')}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in
           MD.disasm(IMAGE[ENTRY:END], ENTRY)}


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if (ins.operands and
                ins.operands[-1].type == capstone.x86.X86_OP_IMM):
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


OWN_EDGES = branch_edges(OWN_INS)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status')]


class OracleFailure(AssertionError):
    """The original or independent finite model did not meet its boundary."""


class NativeMismatch(AssertionError):
    """A completed native/original comparison differed."""


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def selected_cell_index(case):
    total = ((case.get('x', 0x20) & 0xFFFF) +
             (case.get('width', 0x10) & 0xFFFF)) & 0xFFFF
    if total & 0x8000:
        total = (total + 0x0160) & 0xFFFF
    return total >> 3


def cases():
    """Finite coverage of eligibility, coordinate math, row loops and aliases."""
    rows = [
        dict(name='eligible-standard'),
        dict(name='eligibility-zero', eligible=0),
        dict(name='eligibility-two-is-not-one', eligible=2),
        dict(name='signed-x-correction-witness', x=0x8000, width=0,
             y=0x19, height=7, wrong_gate=0),
        dict(name='x-add-wraps-to-positive', x=0xFFF0, width=0x0030),
        dict(name='x-signed-boundary-after-add', x=0x7FF0, width=0x0030),
        dict(name='subtracted-origin-sign-clamps', x=0x20, width=0x10,
             origin_x=0x0100),
        dict(name='second-map-word-read-is-live', x=0x20, width=0x10,
             y=0x19, height=7, map_base=0x3000,
             map_after_first_read=0x0020),
        dict(name='height-flag-clear-bit-path', y=0x20, height=0x20,
             height_adjust=0),
        dict(name='height-flag-set-extra-eight', y=0x20, height=0x20,
             height_adjust=1),
        dict(name='y-positive-after-height', y=0x20, height=0x10),
        dict(name='y-short-negative-adjust-loop', y=0x0000, height=8),
        dict(name='y-adjust-full-4096-steps', y=0x8010, height=8),
        dict(name='y-wrap-near-ffff-adjust', y=0x000F, height=8),
        dict(name='y-seven-fff-positive', y=0x7FFF, height=8),
        dict(name='y-eight-zero-boundary', y=0x8000, height=8),
        dict(name='dy-low-three-bits-round-up', y=0x33, height=0x18),
        dict(name='record-mask-selects-five-byte-row', record_flags=2),
        dict(name='cl-zero-still-draws-first-row-and-wraps', x=0, width=0,
             y=0x10, height=8, map_base=0x3000),
        dict(name='destination-start-beyond-map-limit', x=0x1900, width=0,
             y=0x19, height=7),
        dict(name='word-si-wraps-through-map-limit', x=0, width=0,
             y=0x19, height=7, map_base=0xFFFE),
        dict(name='output-overwrites-map-word-but-keeps-bp',
             x=0x28, width=0, y=0x19, height=7, map_base=0xFFF8,
             ds=0x5000, ss=0x5000),
        dict(name='row-write-aliases-live-cx-si-saves', x=0x20, width=0x10,
             y=0x19, height=7, map_base=0xCFCD, sp=0xD000),
        dict(name='row-write-overwrites-active-ret', x=0x20, width=0x10,
             y=0x19, height=7, map_base=0x6FF9, sp=0x7000,
             return_word=0xBEEF),
        dict(name='adapter-ret-word-crosses-physical-end', ss=0xFFFF,
             sp=0x000F, return_word=0xBEEF),
        dict(name='dirty-write-crosses-physical-end', x=0x28, width=0,
             y=0x19, height=7, map_base=0xFFE0, ss=0xFFFF,
             sp=0x7000),
        dict(name='five-byte-row-crosses-physical-end',
             record_flags=2, map_base=0xFEEE, ss=0xFFFF,
             x=0x20, width=0x10, y=0x30, height=0x20),
        dict(name='data-and-stack-segments-alias', ds=0x5000, ss=0x5000),
        dict(name='record-fields-wrap-logical-di', di=0xFFFC, ds=0x4000,
             origin_x=0x20, x=0x40, width=0x10),
        dict(name='word-record-load-wraps-physical-20-bit',
             ds=0xFFFF, di=0x000F, x=0x20, width=0x10,
             y=0x19, height=7),
        dict(name='df-set-does-not-reverse-explicit-increments', df=True),
        dict(name='provider-restores-live-cx-zero-high-byte',
             x=0x20, width=0x10, y=0x20, height=0x20,
             cx_after_first_dirty_write=0x0002),
        dict(name='five-byte-output-overwrites-map-word-keeps-bp',
             record_flags=2, x=0x28, width=0, y=0x19, height=7,
             map_base=0xFFF8, ds=0x5000, ss=0x5000),
    ]
    oracle_require(30 <= len(rows) <= 45,
                   f'entity-dirty fixture count changed: {len(rows)}')
    for index, case in enumerate(rows):
        case.setdefault('seed', 0x572600 + index * 71)
        case.setdefault('x', 0x20)
        case.setdefault('width', 0x10)
        case.setdefault('y', 0x30)
        case.setdefault('height', 0x20)
        case.setdefault('origin_x', 0)
        case.setdefault('height_adjust', 0)
        case.setdefault('record_flags', 0)
        case.setdefault('eligible', 1)
        case.setdefault('map_base', 0x3000)
        case.setdefault('di', 0x6000)
        case.setdefault('ds', DATA_SEGMENT)
        case.setdefault('ss', 0x5000)
        case.setdefault('sp', 0xD000)
        case.setdefault('return_word', 0x3456)
        case.setdefault('df', False)
        case.setdefault('flags', 0x0ED7)
    return rows


def setup(case):
    template = dict(case, load=MAIN_SEG, poison=False, name=case['name'])
    memory, regs, _device, _pc, _sound, _ = interactions.setup(template)
    ds = case['ds'] & 0xFFFF
    ss = case['ss'] & 0xFFFF
    sp = case['sp'] & 0xFFFF
    di = case['di'] & 0xFFFF
    rng_seed = case['seed'] & 0xFFFFFFFF
    import random
    rng = random.Random(rng_seed)
    for name in interactions.REG_NAMES:
        regs[name] = rng.randrange(0x10000)
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if case.get('df', False) else (flags & ~0x0400)
    regs.update(ax=0xBEEF, bx=0x7139, cx=0x6A55, dx=0x42D3,
                si=case.get('si', 0x4000) & 0xFFFF, di=di,
                bp=case.get('bp', 0xA641) & 0xFFFF,
                cs=MAIN_SEG, ip=ENTRY, ds=ds, es=case.get('es', 0x6200),
                ss=ss, sp=sp, flags=flags)

    put16(memory, ds, 0x0000, case.get('origin_x', 0))
    put16(memory, ds, MAP_WORD, case['map_base'])
    put16(memory, ds, di, case['x'])
    put16(memory, ds, di + 2, case['y'])
    put16(memory, ds, di + 4, case['width'])
    put16(memory, ds, di + 6, case['height'])
    put16(memory, ds, di + 8, case['record_flags'])
    put8(memory, ds, di + 0x20, case['height_adjust'])
    gate_index = selected_cell_index(case)
    put8(memory, ds, VISIBILITY_BASE + gate_index, case['eligible'])
    if 'wrong_gate' in case:
        wrong_index = (((case['x'] + case['width']) & 0xFFFF) >> 3)
        if wrong_index != gate_index:
            put8(memory, ds, VISIBILITY_BASE + wrong_index, case['wrong_gate'])
    put16(memory, ss, sp, case['return_word'])
    return memory, regs, None


class DirtyAccess(interactions.Access):
    """Bounded RAM bus with deferred original-side live-word providers."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []
        self.pending_labels = []
        self.case_ds = case['ds'] & 0xFFFF
        self.case_ss = case['ss'] & 0xFFFF
        self.case_sp = case['sp'] & 0xFFFF
        self.output_address = None
        if case.get('cx_after_first_dirty_write') is not None:
            self.output_address = physical(self.case_ss,
                                           case['_first_output_offset'])

    def _replace_word(self, segment, offset, value, label):
        if self.native:
            self.modify_word(segment, offset, value)
        else:
            address = physical(segment, offset)
            self.pending.extend(((address, value & 0xFF),
                                 ((address + 1) & MASK, value >> 8)))
            self.pending_labels.append(label)
        self.used.add(label)

    def _provider(self, kind, address):
        case = self.case
        address &= MASK
        if (kind == 'read' and
                address == physical(self.case_ds, MAP_WORD + 1) and
                'map-after-first-read' not in self.used and
                'map_after_first_read' in case):
            self._replace_word(self.case_ds, MAP_WORD,
                               case['map_after_first_read'],
                               'map-after-first-read')
        if (kind == 'write' and self.output_address == address and
                'live-cx-after-first-write' not in self.used and
                'cx_after_first_dirty_write' in case):
            self._replace_word(self.case_ss, self.case_sp - 2,
                               case['cx_after_first_dirty_write'],
                               'live-cx-after-first-write')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= MAX_EVENTS:
            raise OracleFailure('entity-dirty callback event budget exhausted')
        address &= MASK
        if kind == 'read':
            value = self.memory[address]
            self.store(address, value)
        else:
            value &= 0xFF
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF,
                            flags & 0xFFFF, mask))
        self._provider(kind, address)
        return value & 0xFF

    def instruction_complete(self):
        for address, value in self.pending:
            self.store(address, value)
        self.pending.clear()


def original(case, memory, regs, *, core):
    access_case = dict(case)
    access_case['_first_output_offset'] = independent_setup(
        case, memory, regs)[2]['start_si']
    return interactions.original(
        case, bytearray(memory), dict(regs), None, core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        access_factory=lambda c, m, r, d: DirtyAccess(
            access_case, m, r, d),
        instruction_limit=MAX_INSTRUCTIONS)


def independent_setup(case, memory, regs):
    """Project original word arithmetic and its ordinary-RAM dirty footprint."""
    expected = bytearray(memory)
    writes = []
    ds, ss, sp, di = regs['ds'], regs['ss'], regs['sp'], regs['di']
    x = get16(expected, ds, di)
    width = get16(expected, ds, (di + 4) & 0xFFFF)
    bx = (x + width) & 0xFFFF
    if bx & 0x8000:
        bx = (bx + 0x0160) & 0xFFFF
    gate_index = bx >> 3
    gate = get8(expected, ds, VISIBILITY_BASE + gate_index)
    info = dict(gate_index=gate_index, eligible=gate == 1, rows=0,
                stores=0, start_si=None, initial_map=None, live_bound=None)
    if gate != 1:
        return expected, writes, info

    ax = (bx - get16(expected, ds, 0)) & 0xFFFF
    if ax & 0x8000:
        ax = 0
    ax >>= 3
    initial_map = get16(expected, ds, MAP_WORD)
    ax = (ax + initial_map) & 0xFFFF
    if 'map_after_first_read' in case:
        put16(expected, ds, MAP_WORD, case['map_after_first_read'])
        live_bound = case['map_after_first_read'] & 0xFFFF
    else:
        live_bound = get16(expected, ds, MAP_WORD)
    bp = (live_bound + 0x0321) & 0xFFFF
    ax = (ax + 1) & 0xFFFF
    si = ax

    cx = get16(expected, ds, (di + 6) & 0xFFFF)
    cx = (cx - 8) & 0xFFFF
    y = get16(expected, ds, (di + 2) & 0xFFFF)
    if get8(expected, ds, (di + 0x20) & 0xFFFF) != 0:
        cx = (cx - 8) & 0xFFFF
    ax = (y + cx) & 0xFFFF
    ax = (ax - 0x10) & 0xFFFF
    if ax & 0x8000:
        for _ in range(4096):
            cx = (cx + 8) & 0xFFFF
            ax = (ax + 8) & 0xFFFF
            if not ax & 0x8000:
                ax = 0
                cx = (cx - 8) & 0xFFFF
                break
        else:
            raise OracleFailure(case['name'] + ': independent Y adjustment exceeded 4096 steps')

    cx = (-cx) & 0xFFFF
    dx = ax
    ax &= 0xFFF8
    si = (si + ax) & 0xFFFF
    ax = (ax << 1) & 0xFFFF
    ax = (ax << 1) & 0xFFFF
    si = (si + ax) & 0xFFFF
    row_bytes = 5 if get16(expected, ds, (di + 8) & 0xFFFF) & 2 else 3
    al = cx & 0xFF
    cl = (cx & 0xFF) >> 3
    if dx & 7:
        cl = (cl + 1) & 0xFF
    if al & 7:
        cl = (cl + 1) & 0xFF
    cx = ((row_bytes << 8) | cl) & 0xFFFF
    info.update(initial_map=initial_map, live_bound=live_bound,
                start_si=si, row_bytes=row_bytes, initial_cl=cl, bp=bp)

    for _row_guard in range(MAX_EVENTS):
        info['rows'] += 1
        # PUSH CX / PUSH SI; these are live SS words read back after the row.
        sp_cx = (sp - 2) & 0xFFFF
        sp_si = (sp - 4) & 0xFFFF
        for address, value in ((physical(ss, sp_cx), cx & 0xFF),
                               (physical(ss, sp_cx) + 1 & MASK, cx >> 8),
                               (physical(ss, sp_si), si & 0xFF),
                               ((physical(ss, sp_si) + 1) & MASK, si >> 8)):
            expected[address] = value & 0xFF
            writes.append((address, value & 0xFF))

        # The inner loop is do/while: CH=0 means 256 stores.
        byte_count = (cx >> 8) or 0x100
        if info['stores'] + byte_count > MAX_MODEL_WRITES:
            raise OracleFailure(case['name'] + ': independent dirty-store model exceeded its budget')
        for index in range(byte_count):
            address = physical(ss, si + index)
            expected[address] = 1
            writes.append((address, 1))
        info['stores'] += byte_count
        if (info['rows'] == 1 and
                case.get('cx_after_first_dirty_write') is not None):
            provider_address = physical(ss, sp_cx)
            expected[provider_address] = case['cx_after_first_dirty_write'] & 0xFF
            expected[(provider_address + 1) & MASK] = (
                case['cx_after_first_dirty_write'] >> 8) & 0xFF

        si = get16(expected, ss, sp_si)
        cx = get16(expected, ss, sp_cx)
        si = (si + 0x28) & 0xFFFF
        if si >= bp:
            break
        cl = ((cx & 0xFF) - 1) & 0xFF
        cx = (cx & 0xFF00) | cl
        if cl == 0:
            break
    else:
        raise OracleFailure(case['name'] + ': independent row loop exceeded its write budget')

    info['final_si'] = si
    info['final_cx'] = cx
    return expected, writes, info


def assert_independent(case, initial, observed):
    expected_memory, expected_writes, info = independent_setup(
        case, initial, observed['initial_regs'])
    oracle_require(observed['memory'] == expected_memory,
                   case['name'] + ': original RAM differs from independent dirty-footprint model')
    actual_writes = [(event[1], event[2]) for event in observed['events']
                     if event[0] == 'write']
    oracle_require(actual_writes == expected_writes,
                   case['name'] + ': original ordered row/stack writes differ from independent model')
    if case.get('eligible', 1) != 1:
        oracle_require(info['stores'] == 0 and not actual_writes,
                       case['name'] + ': ineligible map entry wrote dirty bytes')
    if case['name'] == 'cl-zero-still-draws-first-row-and-wraps':
        oracle_require(info['initial_cl'] == 0 and info['rows'] > 1,
                       'CL=0 did not execute the first row before byte wrap')
    if case['name'] == 'output-overwrites-map-word-but-keeps-bp':
        oracle_require(info['bp'] == 0x0319 and
                       get16(observed['memory'], case['ds'], MAP_WORD) == 0x0101,
                       'row output did not overwrite DS:26 after BP was captured')
    if case['name'] == 'five-byte-output-overwrites-map-word-keeps-bp':
        oracle_require(info['bp'] == 0x0319 and info['row_bytes'] == 5 and
                       get16(observed['memory'], case['ds'], MAP_WORD) == 0x0101,
                       'five-byte output did not overwrite DS:26 after BP was captured')
    if case['name'] == 'row-write-aliases-live-cx-si-saves':
        oracle_require(info['start_si'] == 0xCFFC and
                       get16(observed['memory'], case['ss'], case['sp'] - 4) == 0x0101,
                       'row output did not overwrite the live saved SI word')
    if case['name'] == 'dirty-write-crosses-physical-end':
        oracle_require(physical(case['ss'], info['start_si']) == 0xFFFFE and
                       actual_writes[4][0] == 0xFFFFE and
                       actual_writes[6][0] == 0,
                       'three-byte dirty row did not wrap physical FFFFF to zero')
    if case['name'] == 'five-byte-row-crosses-physical-end':
        oracle_require(physical(case['ss'], info['start_si']) == 0xFFFFD and
                       actual_writes[4][0] == 0xFFFFD and
                       actual_writes[7][0] == 0,
                       'five-byte dirty row did not wrap physical FFFFF to zero')
    if case['name'] == 'provider-restores-live-cx-zero-high-byte':
        oracle_require(info['stores'] >= 259 and 'live-cx-after-first-write' in observed['used'],
                       'live CX provider did not trigger the bounded 256-store row')
    if 'map_after_first_read' in case:
        oracle_require(info['initial_map'] == case['map_base'] and
                       info['live_bound'] == case['map_after_first_read'] and
                       'map-after-first-read' in observed['used'],
                       'the two DS:26 reads did not retain distinct live values')
    return info


def original_case(case, *, core):
    initial, regs, _device = setup(case)
    expected_memory, _writes, _info = independent_setup(case, initial, regs)
    observed = original(case, initial, regs, core=core)
    observed['initial_regs'] = regs
    info = assert_independent(case, initial, observed)
    expected_continuation = RETURN_IP if core else get16(
        expected_memory, regs['ss'], regs['sp'])
    oracle_require(observed['status'] == 0 and
                   observed['continuation'] == expected_continuation,
                   case['name'] + f': original status/continuation '
                   f'{observed["status"]}/{observed["continuation"]:04X}, '
                   f'expected 0/{expected_continuation:04X}')
    return dict(initial=initial, regs=regs, original=observed, info=info)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: bus event count {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        require(got[:3] == ref[:3],
                f'{label}: bus event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
                f'under mask {ref[4]:04X}')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class NativeBus:
    def __init__(self, case, memory, regs):
        self.access = DirtyAccess(case, memory, regs, None, native=True)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_EXIT,
                        f'unexpected entity-dirty OUT {port:04X}={value:04X}/{flags:04X}')

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-dirty-m{mutation}.dll',
                     mutation, 'entity_dirty')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_mark_entity_drawing_dirty_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_mark_entity_drawing_dirty_adapter
        self.adapter.argtypes = [interactions.MEM,
                                 ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16
        self.visibility_core = self.library.lmn_rebuild_view_visibility_map_core
        self.visibility_core.argtypes = [visibility.MEM,
                                         ct.POINTER(visibility.Call),
                                         ct.POINTER(visibility.RasterBus)]
        self.visibility_core.restype = visibility.Result
        self.visibility_adapter = self.library.lmn_rebuild_view_visibility_map_adapter
        self.visibility_adapter.argtypes = [
            visibility.MEM, ct.POINTER(interactions.Regs), ct.c_uint16,
            ct.POINTER(visibility.RasterBus)]
        self.visibility_adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, *, core):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        access_case = dict(case)
        access_case['_first_output_offset'] = independent_setup(
            case, memory, regs)[2]['start_si']
        bus = NativeBus(access_case, memory, regs)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in
                          ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp',
                           'cs', 'ds', 'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), ct.byref(bus.bus))
            state.ax, state.bx, state.cx, state.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            state.si, state.di, state.bp = (
                result.record_cursor, result.object_cursor,
                result.candidate_y)
            state.cs, state.ds, state.es = (
                result.code_segment, result.data_segment,
                result.extra_segment)
            state.ss, state.sp, state.flags, state.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus.bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs,
                    events=bus.access.events, used=bus.access.used,
                    status=status, continuation=final_regs['ip'])

    def run_visibility(self, case, initial, initial_regs,
                       runtime_stack_segment, *, core=True):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        bus = visibility.NativeBus(case, memory, regs, runtime_stack_segment)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = visibility.Call(
                *(regs[name] for name in visibility.CORE_REGS),
                runtime_stack_segment)
            result = self.visibility_core(ram, ct.byref(call), ct.byref(bus.bus))
            for name in visibility.CORE_REGS:
                setattr(state, name, getattr(result, visibility.RESULT_FIELDS[name]))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.visibility_adapter(
                ram, ct.byref(state), runtime_stack_segment, ct.byref(bus.bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs,
                    events=bus.events, used=bus.used,
                    status=status, continuation=final_regs['ip'])


def compare_case(native, case, *, core):
    saved = original_case(case, core=core)
    expected = saved['original']
    actual = native.run(case, saved['initial'], saved['regs'], core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        require(actual['regs'][name] == expected['regs'][name],
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X}')
    require(((actual['regs']['flags'] ^ expected['regs']['flags']) &
             expected['flag_mask']) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{expected["regs"]["flags"]:04X} under '
            f'{expected["flag_mask"]:04X}')
    require(actual['memory'] == expected['memory'],
            label + ': complete 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: providers {actual["used"]}/{expected["used"]}')
    own_sites = {address for source, address in expected['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target)
                 for source, source_ip, target in expected['edges']
                 if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core,
                status=expected['status'], continuation=expected['continuation'],
                sites=sorted(own_sites), edges=[list(edge) for edge in sorted(own_edges)],
                events=len(expected['events']), steps=expected['steps'])


def compare_visibility_handoff(label, actual, expected):
    require(actual['status'] == expected['status'],
            f'{label}: producer status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: producer continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    require(actual['memory'] == expected['memory'],
            label + ': producer full 1 MiB RAM differs')
    for name in interactions.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: producer {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    compare_events(label + ' producer', actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: producer providers {actual["used"]}/{expected["used"]}')


def seed_handoff_records(memory, ds, origin):
    # The producer fills a base-relative byte window. Keep one accepted and one
    # neighboring zero byte record resident while the producer runs.
    indices = ((0x26, 0x27) if origin == 0 else
               (((origin >> 3) - 3, (origin >> 3) - 2)))
    records = []
    for record_index, table_index in enumerate(indices):
        di = (0x6000 + record_index * 0x2D) & 0xFFFF
        x = (table_index << 3) & 0xFFFF
        for offset, value in ((0, x), (2, 0x19), (4, 0), (6, 7),
                              (8, 0), (0x20, 0)):
            if offset == 0x20:
                put8(memory, ds, (di + offset) & 0xFFFF, value)
            else:
                put16(memory, ds, (di + offset) & 0xFFFF, value)
        records.append(dict(di=di, x=x, table_index=table_index,
                            accepted=(table_index == 0x26 if origin == 0
                                      else table_index == (origin >> 3) - 2)))
    return records


def prepare_handoff_frame(producer_memory, producer_regs, record_di):
    """Preserve producer RAM except for the real CALL 3654 stack frame."""
    memory = bytearray(producer_memory)
    regs = dict(producer_regs)
    ss = regs['ss']
    outer_sp = 0x7000
    put16(memory, ss, outer_sp - 2, regs['cx'])
    put16(memory, ss, outer_sp - 4, record_di)
    call_sp = (outer_sp - 6) & 0xFFFF
    put16(memory, ss, call_sp, 0x3657)
    regs.update(cs=MAIN_SEG, ip=ENTRY, di=record_di, sp=call_sp)
    return memory, regs


def producer_handoff(native):
    """Verify 410F output, then feed its unchanged map to real 5726 callers."""
    reports = []
    for index, origin in enumerate((0x0000, 0x0180)):
        producer_case = dict(
            visibility.make_cases()[0],
            name=f'visibility-origin-{origin:04x}-dirty-handoff',
            base=origin, load=MAIN_SEG, seed=0x410F800 + index)
        initial, initial_regs, runtime_stack_segment = visibility.setup(producer_case)
        seeded_records = seed_handoff_records(
            initial, initial_regs['ds'], origin)
        expected_producer = visibility.original(
            producer_case, initial, initial_regs, runtime_stack_segment, core=True)
        visibility.assert_independent(
            producer_case, initial, initial_regs, runtime_stack_segment,
            expected_producer, core=True)
        actual_producer = native.run_visibility(
            producer_case, initial, initial_regs, runtime_stack_segment, core=True)
        producer_label = producer_case['name'] + ' core'
        compare_visibility_handoff(producer_label, actual_producer, expected_producer)
        require(actual_producer['status'] == 0 and
                actual_producer['continuation'] == visibility.RETURN,
                producer_label + ': producer did not stop at the pre-RET boundary')

        producer_memory = actual_producer['memory']
        producer_regs = actual_producer['regs']
        accepted_index = 0x26 if origin == 0 else (origin >> 3) - 2
        rejected_index = accepted_index + 1 if origin == 0 else accepted_index - 1
        accepted_address = (visibility.MAP_CLEAR_START + accepted_index) & 0xFFFF
        rejected_address = (visibility.MAP_CLEAR_START + rejected_index) & 0xFFFF
        accepted_gate = get8(producer_memory, producer_regs['ds'], accepted_address)
        rejected_gate = get8(producer_memory, producer_regs['ds'], rejected_address)
        oracle_require(accepted_gate == 1 and rejected_gate == 0 and
                       abs(accepted_index - rejected_index) == 1,
                       f'{producer_case["name"]}: expected adjacent producer gates '
                       f'1/0, got {accepted_gate}/{rejected_gate}')
        for record in seeded_records:
            oracle_require(get16(expected_producer['memory'], producer_regs['ds'],
                                 record['di']) == record['x'],
                           producer_case['name'] + ': producer altered seeded record')
        require(bytes(initial) != producer_memory,
                producer_case['name'] + ': producer did not change its map output')

        for record in seeded_records:
            case_memory, case_regs = prepare_handoff_frame(
                producer_memory, producer_regs, record['di'])
            require(get16(case_memory, case_regs['ds'], record['di']) == record['x'],
                    producer_case['name'] + ': caller record changed before handoff')
            case_name = ('accepted' if record['accepted']
                         else 'visibility-rejected-adjacent')
            case = dict(
                name=f'{producer_case["name"]}-{case_name}',
                x=record['x'], width=0, y=0x19, height=7,
                origin_x=origin, height_adjust=0, record_flags=0,
                eligible=1 if record['accepted'] else 0,
                map_base=get16(case_memory, case_regs['ds'], MAP_WORD),
                di=record['di'], ds=case_regs['ds'], ss=case_regs['ss'],
                sp=case_regs['sp'], return_word=0x3657,
                df=bool(case_regs['flags'] & 0x0400),
                flags=case_regs['flags'], seed=0x410F900 + origin + record['di'])
            gate_address = (VISIBILITY_BASE + record['table_index']) & 0xFFFF
            oracle_require(get8(case_memory, case_regs['ds'], gate_address) ==
                           (1 if record['accepted'] else 0),
                           case['name'] + ': seeded record did not hit its producer byte')

            producer_snapshot = bytes(case_memory)
            expected_consumer = original(case, case_memory, case_regs, core=False)
            expected_consumer['initial_regs'] = case_regs
            info = assert_independent(case, producer_snapshot, expected_consumer)
            expected_return = get16(expected_consumer['memory'], case_regs['ss'],
                                    case_regs['sp'])
            oracle_require(expected_consumer['status'] == 0 and
                           expected_consumer['continuation'] == expected_return == 0x3657,
                           case['name'] + ': original did not consume caller RET 3657')
            oracle_require(info['eligible'] == record['accepted'] and
                           (info['stores'] > 0 if record['accepted']
                            else info['stores'] == 0),
                           case['name'] + ': producer byte did not control dirty eligibility')

            actual_consumer = native.run(case, producer_snapshot, case_regs, core=False)
            label = case['name'] + ' adapter'
            require(actual_consumer['status'] == expected_consumer['status'],
                    f'{label}: status {actual_consumer["status"]}/'
                    f'{expected_consumer["status"]}')
            require(actual_consumer['continuation'] == expected_consumer['continuation'],
                    f'{label}: continuation {actual_consumer["continuation"]:04X}/'
                    f'{expected_consumer["continuation"]:04X}')
            require(actual_consumer['memory'] == expected_consumer['memory'],
                    label + ': full 1 MiB RAM differs')
            for name in interactions.REG_NAMES:
                mask = expected_consumer['flag_mask'] if name == 'flags' else 0xFFFF
                require(((actual_consumer['regs'][name] ^
                          expected_consumer['regs'][name]) & mask) == 0,
                        f'{label}: {name} {actual_consumer["regs"][name]:04X}/'
                        f'{expected_consumer["regs"][name]:04X} under {mask:04X}')
            compare_events(label, actual_consumer['events'], expected_consumer['events'])
            require(actual_consumer['used'] == expected_consumer['used'],
                    f'{label}: providers {actual_consumer["used"]}/'
                    f'{expected_consumer["used"]}')
            reports.append(dict(
                producer=producer_case['name'], view_origin=origin,
                producer_instruction_sites=sorted(visibility.observed_sites(expected_producer)),
                producer_events=len(expected_producer['events']),
                record_di=record['di'], table_index=record['table_index'],
                gate_address=gate_address, gate_value=1 if record['accepted'] else 0,
                accepted=record['accepted'], caller_return=0x3657,
                consumer_events=len(expected_consumer['events']),
                consumer_dirty_stores=info['stores']))
        del initial, initial_regs, expected_producer, actual_producer, producer_memory
        gc.collect()
    return reports


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-simulation.md',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/adlib-regions.json',
        'metadata/adlib-encodings.json', 'metadata/tandysnd-symbols.json',
        'metadata/tandysnd-regions.json', 'metadata/tandysnd-encodings.json',
        'metadata/pcspeaker-symbols.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'src/game_code.asm', 'src/game_code_late_after_palette.asm',
        'src/entity_dirty.asm', 'src/program.asm', 'src/image_tail.asm',
        'src/view_visibility.asm', 'src/game_code_late_after_selection.asm',
        'c/entity_dirty.c', 'c/entity_dirty.h', 'c/view_visibility.c',
        'c/view_visibility.h', 'c/lemmings_sym.h', 'c/regs.h',
        'c/special_blit.h', 'tests/entity_dirty.py',
        'tests/entity_interactions.py', 'tests/view_visibility.py',
        'tests/pcspeaker_dispatch.py',
        'tests/sound_latches.py', 'tests/minimap_vga.py', 'tools/resources.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/coverage.py', 'tools/difftest.py', 'tools/unpack.py',
        'docs/entity-display.md', 'docs/indirect-callbacks.md',
        'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(before):
    oracle_require(before == input_hashes(),
                   'entity-dirty input hashes changed before original campaign')
    oracle_require(len(OWN_INS) == 73 and
                   sum(ins.size for ins in OWN_INS.values()) == 171,
                   f'entity-dirty static code accounting changed: '
                   f'{len(OWN_INS)} sites/{sum(ins.size for ins in OWN_INS.values())} bytes')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed main image hash changed')
    covered, edges, rows = set(), set(), []
    specs = cases()
    for case in specs:
        for core in (True, False):
            saved = original_case(case, core=core)
            observed = saved['original']
            sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
            case_edges = {(source_ip, target)
                          for source, source_ip, target in observed['edges']
                          if source == 'main' and source_ip in OWN_INS}
            covered.update(sites)
            edges.update(case_edges)
            rows.append(dict(name=case['name'], core=core,
                             sites=sorted(sites),
                             edges=[list(edge) for edge in sorted(case_edges)],
                             events=len(observed['events']), steps=observed['steps']))
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'entity-dirty original misses sites {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'entity-dirty original edge union differs: '
                   f'missing={sorted(OWN_EDGES-edges)} extra={sorted(edges-OWN_EDGES)}')
    oracle_require(before == input_hashes(),
                   'entity-dirty inputs changed during original campaign')
    print(f'PASS entity dirty original: {len(specs)} fixtures x core/adapter, '
          f'{len(covered)} sites/{len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} events; bounded original only',
          flush=True)
    return rows, edges


def worker(directory, hash_path):
    import json
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'entity-dirty inputs changed before native worker')
    original_rows, _ = original_campaign(before)
    specs = cases()
    baseline = Native(directory)
    rows, sites, edges, event_count, step_count = [], set(), set(), 0, 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            event_count += row['events']
            step_count += row['steps']
        gc.collect()
    oracle_require(sites == set(OWN_INS),
                   f'entity-dirty native sites miss {sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == OWN_EDGES,
                   f'entity-dirty native edges differ: '
                   f'missing={sorted(OWN_EDGES-edges)} extra={sorted(edges-OWN_EDGES)}')
    handoff_rows = producer_handoff(baseline)
    producer_event_counts = {row['producer']: row['producer_events']
                             for row in handoff_rows}
    consumer_handoff_events = sum(row['consumer_events'] for row in handoff_rows)
    witnesses = {
        1: 'signed-x-correction-witness',
        2: 'eligibility-zero',
        3: 'second-map-word-read-is-live',
        4: 'y-short-negative-adjust-loop',
        5: 'record-mask-selects-five-byte-row',
        6: 'eligible-standard',
        7: 'row-write-aliases-live-cx-si-saves',
    }
    by_name = {case['name']: case for case in specs}
    mutations = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'entity-dirty mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(before == input_hashes(),
                   'entity-dirty inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
        translated_code_bytes=171, instruction_sites=len(OWN_INS),
        own_branch_edges=len(OWN_EDGES), case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations, executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        total_bus_events=event_count, original_code_hook_steps=step_count,
        producer_handoff=dict(
            code_range=[visibility.ENTRY, visibility.END],
            instruction_sites=len(visibility.VIS_SITES),
            executed_instruction_addresses=sorted(
                visibility.VIS_SITES - {visibility.RETURN}),
            producer_execution_count=2,
            producer_comparisons=len(producer_event_counts),
            consumer_comparisons=len(handoff_rows),
            boundary='producer logical core before actual RET',
            case_count=len(handoff_rows),
            total_bus_events=sum(producer_event_counts.values()) +
            consumer_handoff_events,
            producer_bus_events=sum(producer_event_counts.values()),
            consumer_bus_events=consumer_handoff_events,
            cases=handoff_rows,
            scope='410F producer core output was compared fully before its RAM fed adjacent 5726 records with an actual 3654->3657 caller frame; this is data-flow evidence, not execution of 3634'),
        original_only_case_count=len(original_rows), input_hashes=before,
        cases=[dict(name=row['name'], core=row['core'], sites=row['sites'],
                    edges=row['edges'], events=row['events'], steps=row['steps'])
               for row in rows],
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domains=[
            'MarkEntityDrawingDirty 5726..57D0 logical pre-RET core and actual-RET adapter, ordinary RAM only',
            'eligibility byte must equal one; signed X+width correction and the live DS:0000 subtraction/clamp',
            'independent live DS:0026 reads for output origin and unsigned BP bound, including provider replacement',
            'height-adjust byte, signed Y correction loop through its 4096-step boundary, CH=3/5 and byte CL wrap',
            'first-row do/while when CL is zero, bounded by the original unsigned BP comparison',
            'live SS:SI dirty writes, live per-row CX/SI saves, DS=SS/map aliases, changed actual RET and physical wrapping',
            'whole 1 MiB RAM, all registers, defined FLAGS and ordered byte callbacks',
            'verified 410F view-visibility output at origins 0000/0180 feeding accepted and adjacent rejected records with a 3654->3657 caller frame; data-flow composition only, not 3634 execution',
        ]))
    print(f'PASS entity dirty: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {event_count} events, '
          f'{len(mutations)} completed mutants; {len(handoff_rows)} producer handoffs',
          flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-dirty-original-',
                                        parent=BUILD) as directory:
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        import json
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, edges = original_campaign(before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
            known_code_bytes=171, instruction_sites=len(OWN_INS),
            own_branch_edges=len(OWN_EDGES), case_count=len(cases()),
            executed_instruction_addresses=sorted(
                {address for row in rows for address in row['sites']}),
            branch_edges=[list(edge) for edge in sorted(edges)],
            input_hashes=before,
            domain='Bounded original-only dirty-map eligibility, row footprint, live aliases and core/actual-RET checks.'))
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_dirty.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-dirty-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
