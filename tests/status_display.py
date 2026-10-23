"""Bounded differential checks for the 3ACE status-display suffix.

The suite composes the already-tested status text, glyph, icon, and count
leaves under their real CALL frames.  It owns only 3ACE..3CDD; 3B08 remains
UNKNOWN and the byte DIV overflow is an explicit pre-instruction boundary.
"""
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
from entity_interactions import OracleFailure, REG_NAMES, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
import status_count as count_test
import status_glyph as glyph_test
import status_icons as icon_test
import status_text as text_test
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
LOAD = 0x1010
ENTRY, DIVIDE, AFTER_DIVIDE, RET, END = 0x3ACE, 0x3AED, 0x3AEF, 0x3CDD, 0x3CDE
KNOWN_RANGES = ((ENTRY, 0x3B08), (0x3B09, END))
UNKNOWN_BYTES = (0x3B08,)
DATA_SEGMENT, STACK_SEGMENT = 0x3500, 0x5200
FONT_SEGMENT, ALT_DATA_SEGMENT = 0x6000, 0x4500
DEFINED_FLAGS = 0x0FD7
DF, IF, TF = 0x0400, 0x0200, 0x0100
MAX_INSTRUCTIONS, MAX_EVENTS = 28000, 32768
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-display-differential.json'
ORIGINAL_REPORT = BUILD / 'status-display-original-differential.json'
DIV_BYTES = IMAGE[DIVIDE:DIVIDE + 2]

CORE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
              'ss', 'sp', 'flags')
RESULT_FIELDS = dict(ax='value', bx='map_cursor', cx='count', dx='auxiliary_value',
                     si='record_cursor', di='object_cursor', bp='candidate_y',
                     cs='code_segment', ds='data_segment', es='extra_segment',
                     ss='stack_segment', sp='stack_offset', flags='flags')
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags', 'continuation', 'status', 'child_entry', 'child_status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


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
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


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
PARENT_INS = {}
for start, stop in KNOWN_RANGES:
    PARENT_INS.update({ins.address: ins for ins in
                       MD.disasm(IMAGE[start:stop], start)})
CHILD_INS = (text_test.PARENT_INS | glyph_test.INSTRUCTIONS |
             icon_test.INSTRUCTIONS | count_test.OWN_INS)
MAIN_INS = PARENT_INS | CHILD_INS
PARENT_SITES = set(PARENT_INS)


def static_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


PARENT_EDGES = static_edges(PARENT_INS)
CODE_BYTES = sum(stop - start for start, stop in KNOWN_RANGES)
oracle_require(CODE_BYTES == 527 and len(PARENT_SITES) == 172 and
               not (set(UNKNOWN_BYTES) & PARENT_SITES),
               f'status-display static span changed: {CODE_BYTES} known bytes, '
               f'{len(PARENT_SITES)} sites')

COUNT_ROWS = (
    # literal slot, value, snapshot, refresh-counter byte offsets
    (0, 0x64, 0x65, 0x66),
    (1, 0x67, 0x68, 0x69),
    (4, 0x70, 0x71, 0x72),
    (9, 0x7F, 0x80, 0x81),
    (2, 0x6A, 0x6B, 0x6C),
    (6, 0x76, 0x77, 0x78),
    (5, 0x73, 0x74, 0x75),
    (7, 0x79, 0x7A, 0x7B),
    (3, 0x6D, 0x6E, 0x6F),
    (8, 0x7C, 0x7D, 0x7E),
)
COUNT_CONTINUATIONS = (0x3B7E, 0x3BA5, 0x3BCC, 0x3BF3, 0x3C1A,
                       0x3C41, 0x3C68, 0x3C8F, 0x3CB6, 0x3CDD)
COUNT_SLOT_BY_CONTINUATION = {target: row[0]
                              for target, row in zip(COUNT_CONTINUATIONS, COUNT_ROWS)}
PARENT_CALL_RETURNS = {
    0x3B26: ({0x418B}, 2),
    0x3B36: ({0x789D}, 2),
    0x3B3C: ({0x78FF}, 2),
}
PARENT_CALL_RETURNS.update({
    call: ({0x76DA, 0x7707}, 2)
    for call in (0x3B7B, 0x3BA2, 0x3BC9, 0x3BF0, 0x3C17,
                 0x3C3E, 0x3C65, 0x3C8C, 0x3CB3, 0x3CDA)
})
PARENT_CALL_RETURNS[0x4182] = ({0x77FD, 0x780C}, 1)


def default_counts(kind):
    if kind == 'zero-wrap':
        return [{'value': 0, 'snapshot': 0, 'counter': 0xFF} for _ in COUNT_ROWS]
    if kind == 'equal-skip':
        return [{'value': i + 1, 'snapshot': i + 1, 'counter': 2}
                for i in range(len(COUNT_ROWS))]
    if kind == 'changed-ack':
        return [{'value': i + 1, 'snapshot': (i + 1) ^ 0x5A, 'counter': 2}
                for i in range(len(COUNT_ROWS))]
    if kind == 'mixed':
        values = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
        return [dict(value=value,
                     snapshot=(value if index % 3 == 1 else value ^ 0x33),
                     counter=(0xFF if index % 3 == 0 else
                              2 if index % 3 == 2 else 1))
                for index, value in enumerate(values)]
    raise ValueError(f'unknown status row state {kind}')


def cases():
    full_line = IMAGE[0x09A90 + 0x2083:0x09A90 + 0x20AB].decode('ascii')
    oracle_require(len(full_line) == 40,
                   'pinned stored status line must contain 40 bytes')
    rows = [
        dict(name='zero-percent-zero-count-forces-all-ten-and-wraps-ff',
             completion=0, limit=76, row_state='zero-wrap', selector=3,
             icon_snapshot=3, icon_counter=0xFF, text='A', seed=0x3ACE01),
        dict(name='full-status-line-renders-updated-percent-and-all-counts',
             completion=100, limit=100, row_state='zero-wrap', selector=3,
             icon_snapshot=3, icon_counter=0xFF,
             text=full_line, seed=0x3ACE20),
        dict(name='exact-100-percent-equal-snapshots-skip-counts', completion=100,
             limit=100, row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=2, text='', seed=0x3ACE02),
        dict(name='all-changed-counts-ack-counter-two', completion=150,
             limit=76, row_state='changed-ack', selector=3, icon_snapshot=3,
             icon_counter=1, text='A 5', seed=0x3ACE03),
        dict(name='mixed-literal-slot-order-and-counter-wrap', completion=255,
             limit=100, row_state='mixed', selector=3, icon_snapshot=3,
             icon_counter=0xFF, text='X', seed=0x3ACE04),
        dict(name='divisor-zero-bypasses-div-and-keeps-low-product',
             completion=255, limit=0, row_state='equal-skip', selector=3,
             icon_snapshot=3, icon_counter=0, text='', seed=0x3ACE05),
        dict(name='divide-quotient-fit-at-two-over-one', completion=2,
             limit=1, row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE06),
        dict(name='divide-overflow-at-three-over-one', completion=3,
             limit=1, row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE07, divide_error=True),
        dict(name='divide-overflow-255-over-75', completion=255, limit=75,
             row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE08, divide_error=True),
        dict(name='unclamped-255-through-division', completion=255,
             limit=100, row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE09),
        dict(name='icon-change-ack-clears-old-selector-zero', completion=12,
             limit=76, row_state='changed-ack', selector=4, icon_snapshot=0,
             icon_counter=2, text='', seed=0x3ACE0A),
        dict(name='icon-change-ack-clears-old-selector-one', completion=12,
             limit=76, row_state='changed-ack', selector=4, icon_snapshot=1,
             icon_counter=0, text='', seed=0x3ACE0B),
        dict(name='icon-change-ack-clears-old-selector-two', completion=12,
             limit=76, row_state='changed-ack', selector=4, icon_snapshot=2,
             icon_counter=2, text='', seed=0x3ACE0C),
        dict(name='icon-change-clears-old-selector-nine', completion=12,
             limit=76, row_state='mixed', selector=4, icon_snapshot=9,
             icon_counter=0xFF, text='', seed=0x3ACE0D),
        dict(name='icon-change-negative-old-selector-80', completion=12,
             limit=76, row_state='mixed', selector=4, icon_snapshot=0x80,
             icon_counter=2, text='', seed=0x3ACE0E),
        dict(name='icon-change-negative-old-selector-ff', completion=12,
             limit=76, row_state='mixed', selector=4, icon_snapshot=0xFF,
             icon_counter=1, text='', seed=0x3ACE0F),
        dict(name='icon-counter-two-ack-and-refresh-zero', completion=25,
             limit=76, row_state='equal-skip', selector=0x25, icon_snapshot=3,
             icon_counter=2, text='', seed=0x3ACE10),
        dict(name='counter-changed-between-cmp-and-live-inc', completion=40,
             limit=76, row_state='changed-ack', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE11,
             provider_counter=(0x66, 0xFE), count_overrides={0x66: 1}),
        dict(name='selector-snapshot-reread-after-outline-provider', completion=16,
             limit=76, row_state='mixed', selector=4, icon_snapshot=0,
             icon_counter=0, text='', seed=0x3ACE12,
             provider_old_selector=5),
        dict(name='returned-ds-from-live-glyph-stack-save', completion=8,
             limit=76, row_state='mixed', selector=3, icon_snapshot=3,
             icon_counter=0, text='A', seed=0x3ACE13,
             ds=DATA_SEGMENT, ss=STACK_SEGMENT, sp=0x7000,
             provider_glyph_ds=ALT_DATA_SEGMENT),
        dict(name='changed-parent-text-call-return', completion=8,
             limit=76, row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=0, text='A', seed=0x3ACE14,
             alter_text_return=0x3B2D, expected_status=2,
             expected_child_entry=0x417B, expected_child_status=0,
             expected_continuation=0x3B2D),
        dict(name='changed-inner-glyph-call-return', completion=8,
             limit=76, row_state='equal-skip', selector=3, icon_snapshot=3,
             icon_counter=0, text='A', seed=0x3ACE15,
             alter_glyph_return=0x4186, expected_status=1,
             expected_child_entry=0x417B, expected_child_status=1,
             expected_continuation=0x4186),
        dict(name='changed-parent-count-call-return', completion=8,
             limit=76, row_state='zero-wrap', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE16,
             alter_count_return=0x3BA5, expected_status=2,
             expected_child_entry=0x762A, expected_child_status=0,
             expected_continuation=0x3BA5),
        dict(name='live-outer-return-word-after-first-child-output', completion=8,
             limit=76, row_state='zero-wrap', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE17,
             provider_outer_return=0x4567),
        dict(name='df-reverse-text-glyph-and-counts', completion=33,
             limit=76, row_state='mixed', selector=3, icon_snapshot=3,
             icon_counter=0, text='AB', seed=0x3ACE18, df=True),
        dict(name='if-clear-entry-flows-through-cli-sti-children', completion=65,
             limit=76, row_state='changed-ack', selector=3, icon_snapshot=3,
             icon_counter=0, text='A', seed=0x3ACE19, iflag=False),
        dict(name='ds-equals-ss-stack-frame-and-state-alias', completion=9,
             limit=76, row_state='mixed', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE1A,
             ds=STACK_SEGMENT, ss=STACK_SEGMENT, sp=0x0042),
        dict(name='vga-backed-stack-and-live-return', completion=9,
             limit=76, row_state='zero-wrap', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE1B,
             ss=0xA000, sp=0x7000, expected_status=2,
             expected_child_entry=0x762A, expected_child_status=0,
             expected_continuation=0x3BAB),
        dict(name='child-stack-write-overwrites-parent-global', completion=21,
             limit=76, row_state='mixed', selector=3, icon_snapshot=3,
             icon_counter=0, text='', seed=0x3ACE1C,
             ds=STACK_SEGMENT, ss=STACK_SEGMENT, sp=0x0042),
    ]
    oracle_require(len(rows) == 29, f'expected 29 focused status-display cases, got {len(rows)}')
    return rows


def write_counts(memory, ds, specs):
    rows = specs if specs is not None else default_counts('mixed')
    oracle_require(len(rows) == len(COUNT_ROWS), 'status-count triple fixture is not ten rows')
    for (slot, value_off, snapshot_off, counter_off), triple in zip(COUNT_ROWS, rows):
        put8(memory, ds, value_off, triple['value'])
        put8(memory, ds, snapshot_off, triple['snapshot'])
        put8(memory, ds, counter_off, triple['counter'])


def _load_image(memory):
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    base = LOAD << 4
    memory[base:base + len(loaded)] = loaded


def prepare_data(memory, regs, case, data_segments=None):
    """Prepare only the suffix-owned data in an existing live memory image.

    This is also used by the caller-composition suite after its own prefix
    setup.  It intentionally leaves registers, device state, code, and the
    caller's live SS:SP return word untouched.
    """
    seed = case.get('seed', 0x3ACE01) & 0xFFFFFFFF
    segments = ([regs['ds'] & 0xFFFF] if data_segments is None else
                list(dict.fromkeys(int(segment) & 0xFFFF for segment in data_segments)))
    oracle_require(bool(segments), 'status-display prepare_data needs at least one DS')

    # The bitmap children share this live pointer and a patterned font bank.
    font_segment = case.get('font_segment', FONT_SEGMENT) & 0xFFFF
    alt_font_segment = case.get('provider_font_segment', font_segment) & 0xFFFF
    for segment, salt in ((font_segment, 0x31), (alt_font_segment, 0xA7)):
        for offset in range(0x800):
            put8(memory, segment, offset,
                 ((offset * 37 + seed * 11 + salt * 19) ^ (offset >> 2)) & 0xFF)
    # The parent always calls the text leaf. A short explicit string keeps the
    # pixels finite while exercising the same live source and glyph handoff.
    text = case.get('text', 'A').encode('ascii')
    counts = default_counts(case.get('row_state', 'mixed'))
    for slot, value in case.get('count_overrides', {}).items():
        slot = int(slot) & 0xFFFF
        for row, layout in zip(counts, COUNT_ROWS):
            if layout[3] == slot:
                row['counter'] = int(value) & 0xFF
                break
        else:
            raise OracleFailure(f'unknown status counter offset {slot:04X}')

    for ds in segments:
        put16(memory, ds, 0x1F76, case.get('origin', 0x1000))
        put16(memory, ds, 0x1FEC, font_segment)
        for index, char in enumerate(text):
            put8(memory, ds, 0x2083 + index, char)
        put8(memory, ds, 0x2083 + len(text), 0)
        put8(memory, ds, 0x0046, case.get('completion', 0))
        put8(memory, ds, 0x0047, case.get('limit', 76))
        put8(memory, ds, 0x0082, case.get('selector', 3))
        put8(memory, ds, 0x0083, case.get('icon_snapshot', 3))
        put8(memory, ds, 0x0084, case.get('icon_counter', 0))
        write_counts(memory, ds, counts)
        put8(memory, ds, 0x0040, 0xCC)
        put8(memory, ds, 0x209C, 0xEE)
        put8(memory, ds, 0x209D, 0xDD)
        put8(memory, ds, 0x209E, 0xBB)

    if case.get('provider_glyph_ds') is not None:
        alt_ds = case['provider_glyph_ds'] & 0xFFFF
        if alt_ds not in segments:
            primary = physical(segments[0], 0)
            target = physical(alt_ds, 0)
            memory[target:target + 0x2200] = memory[primary:primary + 0x2200]
        put8(memory, alt_ds, 0x2083, ord('A'))
        put8(memory, alt_ds, 0x2084, 0)
        put16(memory, alt_ds, 0x1FEC, font_segment)
    return tuple(segments)


def setup(case):
    seed = case['seed'] & 0xFFFFFFFF
    rng = random.Random(seed)
    memory = bytearray(SIZE)
    _load_image(memory)
    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    ss = case.get('ss', STACK_SEGMENT) & 0xFFFF
    sp = case.get('sp', 0x7000) & 0xFFFF
    flags = 2 | (case.get('flags', 0x00D5) & DEFINED_FLAGS)
    flags &= ~TF
    if case.get('df', False):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('iflag', True):
        flags |= IF
    else:
        flags &= ~IF
    flags |= 2

    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    regs.update(ax=0xB5A5, bx=0xC217, cx=0x8A51, dx=0x3CE0,
                si=0x5123, di=0x42A7, bp=0x6D93,
                cs=LOAD, ip=ENTRY, ds=ds, es=0x7131, ss=ss, sp=sp,
                flags=flags)
    prepare_data(memory, regs, case)

    return_word = case.get('outer_return', (0x4C00 + seed * 13) & 0xFFFF)
    put16(memory, ss, sp, return_word)
    device = MinimapVga(seed ^ 0x3ACE, read_map=(seed >> 3) & 3)
    device.seq[2], device.seq[4] = 0x0F, 0x06
    device.gc[0], device.gc[1], device.gc[3] = 0, 0, 0
    device.gc[5], device.gc[6], device.gc[8] = 0, 0x05, 0xFF
    if ss == 0xA000:
        device.gc[4] = 0
        device.planes[0][sp] = return_word & 0xFF
        device.planes[0][(sp + 1) & 0xFFFF] = return_word >> 8
    oracle_require(memory[(LOAD << 4) + ENTRY:(LOAD << 4) + END] ==
                   relocated(IMAGE, META['relocations'], LOAD)[ENTRY:END],
                   case['name'] + ': fixture setup modified suffix code')
    return memory, regs, device


class DisplayAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.native = bool(case.get('_native', False))
        self.out_count = 0
        self.pending = []

    def _word(self, segment, offset, value):
        address = physical(segment, offset)
        self.store(address, value & 0xFF)
        self.store(address + 1, value >> 8)

    def _byte(self, segment, offset, value):
        self.store(physical(segment, offset), value & 0xFF)

    def access(self, kind, address, flags, mask=DEFINED_FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        provider = self.case.get('provider_counter')
        if (provider is not None and kind == 'read' and
                address == physical(self.regs['ds'], provider[0]) and
                'counter-provider-fired' not in self.used):
            change = (address, provider[1] & 0xFF)
            if self.native:
                self.store(*change)
            else:
                self.pending.append(change)
            self.used.add('counter-provider-fired')
        return result

    def instruction_complete(self):
        while self.pending:
            self.store(*self.pending.pop(0))

    def out_word(self, port, value, flags, mask=DEFINED_FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('status-display OUT callback budget exhausted')
        if self.device is None or port not in (0x03C4, 0x03CE):
            raise OracleFailure(f'undeclared status-display OUT {port:04X}')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        index = self.out_count
        self.out_count += 1
        case = self.case
        if index == 0 and case.get('provider_old_selector') is not None:
            self._byte(self.regs['ds'], 0x0083, case['provider_old_selector'])
            self.used.add('old-icon-selector-after-outline')
        if index == 0 and case.get('provider_glyph_ds') is not None:
            self._word(self.regs['ss'], self.regs['sp'] - 10,
                       case['provider_glyph_ds'])
            self.used.add('glyph-pop-ds-provider')
        if index == 0 and case.get('alter_text_return') is not None:
            self._word(self.regs['ss'], self.regs['sp'] - 2,
                       case['alter_text_return'])
            self.used.add('text-call-return-provider')
        if index == 0 and case.get('alter_glyph_return') is not None:
            self._word(self.regs['ss'], self.regs['sp'] - 8,
                       case['alter_glyph_return'])
            self.used.add('glyph-call-return-provider')
        if index == 0 and case.get('alter_count_return') is not None:
            self._word(self.regs['ss'], self.regs['sp'] - 2,
                       case['alter_count_return'])
            self.used.add('count-call-return-provider')
        if index == 0 and case.get('provider_outer_return') is not None:
            self._word(self.regs['ss'], self.regs['sp'],
                       case['provider_outer_return'])
            self.used.add('outer-return-provider')


def make_instruction_map():
    return MAIN_INS


def run_reference(case, memory, regs, device, *, core=True):
    overflow = bool(case.get('divide_error'))
    stops = {DIVIDE: 0} if overflow else ({RET: 0} if core else None)
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=DEFINED_FLAGS, main_instructions=MAIN_INS,
        main_call_returns=PARENT_CALL_RETURNS,
        stop_offsets=stops, access_factory=DisplayAccess,
        instruction_limit=MAX_INSTRUCTIONS)


def percent_value(completion, limit):
    numerator = (completion & 0xFF) * 100
    if limit & 0xFF:
        quotient = numerator // (limit & 0xFF)
        return None if quotient > 0xFF else quotient & 0xFF
    return numerator & 0xFF


def percent_digits(value, old_leading):
    if value == 100:
        return (0x31, 0x30, 0x30)
    al, ah = value & 0xFF, 0
    while True:
        ah = (ah + 1) & 0xFF
        old = al
        al = (al - 10) & 0xFF
        if old < 10:
            break
    al = (al + 0x3A) & 0xFF
    ah = (ah - 1) & 0xFF
    if ah == 0:
        ah = 0xF0
    ah = (ah + 0x30) & 0xFF
    return (old_leading, ah, al)


def expected_count_rows(memory, ds, *, icon_old, icon_new, icon_counter,
                        provider_counter=None):
    triples = [{
        'slot': slot,
        'value': get8(memory, ds, value_off),
        'snapshot': get8(memory, ds, snapshot_off),
        'counter': get8(memory, ds, counter_off),
        'snapshot_off': snapshot_off,
        'counter_off': counter_off,
    } for slot, value_off, snapshot_off, counter_off in COUNT_ROWS]
    cleared_index = None
    if icon_new != icon_old:
        # RestoreStatusIcon clears the saved icon's adjacent snapshot/counter
        # word for signed AL<10, including byte-wrapped negative selectors.
        signed_old = icon_old if icon_old < 0x80 else icon_old - 0x100
        if signed_old < 10:
            start = (0x65 + ((3 * icon_old) & 0xFF)) & 0xFFFF
            put8(memory, ds, start, 0)
            put8(memory, ds, start + 1, 0)
            for index, triple in enumerate(triples):
                if triple['snapshot_off'] == start:
                    triple['snapshot'] = 0
                    triple['counter'] = 0
                    cleared_index = index
        if icon_counter == 2:
            icon_old = icon_new
            icon_counter = 0
        else:
            icon_counter = (icon_counter + 1) & 0xFF

    call_slots = []
    for index, row in enumerate(triples):
        live, snapshot, counter = row['value'], row['snapshot'], row['counter']
        draws = live == 0 or snapshot != live
        if not draws:
            continue
        call_slots.append(row['slot'])
        if provider_counter is not None and index == provider_counter[0]:
            counter = provider_counter[1] & 0xFF
        if counter == 2:
            row['snapshot'] = live
            row['counter'] = 0
        else:
            row['counter'] = (counter + 1) & 0xFF
    return triples, call_slots, icon_old, icon_counter, cleared_index


def parent_stack_call_words(events, regs):
    low = physical(regs['ss'], regs['sp'] - 2)
    high = (low + 1) & MASK
    calls = []
    for index in range(len(events) - 1):
        first, second = events[index], events[index + 1]
        if (first[0] == second[0] == 'write' and first[1] == low and
                second[1] == high):
            word = first[2] | (second[2] << 8)
            if word in (0x3B29, 0x3B39, 0x3B3F, *COUNT_CONTINUATIONS):
                calls.append(word)
    return calls


def assert_independent(case, initial, regs, expected, *, core):
    if case.get('divide_error'):
        oracle_require(expected['continuation'] == DIVIDE and
                       expected['regs']['ip'] == DIVIDE,
                       case['name'] + ': original did not stop before byte DIV')
        numerator = (case['completion'] & 0xFF) * 100
        oracle_require(expected['regs']['ax'] == numerator and
                       (expected['regs']['cx'] & 0xFF) == case['limit'] and
                       (numerator // case['limit']) > 0xFF,
                       case['name'] + ': original pre-DIV AX/CL do not overflow')
        return

    pct = percent_value(case['completion'], case['limit'])
    oracle_require(pct is not None, case['name'] + ': expected normal case overflows DIV')
    expected_status = case.get('expected_status')
    allowed = case.get('allowed_statuses', (0,))
    if expected_status is not None:
        allowed = (expected_status,)
    oracle_require(expected['status'] in allowed,
                   case['name'] + f": original status {expected['status']} outside {allowed}")
    if case.get('expected_continuation') is not None:
        oracle_require(expected['continuation'] == case['expected_continuation'],
                       case['name'] + ': changed child return target differs')
    if not case.get('divide_error') and expected['status'] == 0:
        if core:
            oracle_require(expected['continuation'] == RET,
                           case['name'] + ': core did not stop at the suffix RET')
        elif case.get('outer_return') is None and case.get('provider_outer_return') is None:
            stack_target = get16(expected['memory'], regs['ss'], regs['sp'])
            oracle_require(expected['continuation'] == stack_target,
                           case['name'] + ': adapter did not consume the live outer RET')
    ds = regs['ds']
    # Exceptional segment/stack aliases deliberately have a different live
    # projection; their complete RAM/device comparison remains authoritative.
    clean = (regs['ds'] != regs['ss'] and regs['ss'] != 0xA000 and
             case.get('provider_glyph_ds') is None)
    if clean:
        oracle_require(get8(expected['memory'], ds, 0x0040) == pct,
                       case['name'] + ': independent percent byte differs')
        digits = percent_digits(pct, get8(initial, ds, 0x209C))
        got = tuple(get8(expected['memory'], ds, offset)
                    for offset in (0x209C, 0x209D, 0x209E))
        oracle_require(got == digits,
                       case['name'] + f': independent percent formatting {got!r}/{digits!r}')

        if expected['status'] == 0:
            old_icon = get8(initial, ds, 0x0083)
            new_icon = get8(initial, ds, 0x0082)
            icon_counter = get8(initial, ds, 0x0084)
            if case.get('provider_old_selector') is not None:
                old_icon = case['provider_old_selector'] & 0xFF
            triples, call_slots, final_icon_snapshot, final_icon_counter, _ = expected_count_rows(
                bytearray(initial), ds, icon_old=old_icon, icon_new=new_icon,
                icon_counter=icon_counter,
                provider_counter=((next(i for i, r in enumerate(COUNT_ROWS)
                                        if r[3] == case['provider_counter'][0]),
                                   case['provider_counter'][1])
                                  if case.get('provider_counter') else None))
            for row in triples:
                oracle_require(get8(expected['memory'], ds, row['snapshot_off']) == row['snapshot'] and
                               get8(expected['memory'], ds, row['counter_off']) == row['counter'],
                               case['name'] + f": independent count triple for slot {row['slot']} differs")
            oracle_require(get8(expected['memory'], ds, 0x0083) == final_icon_snapshot and
                           get8(expected['memory'], ds, 0x0084) == final_icon_counter,
                           case['name'] + ': independent icon acknowledgement differs')

            words = parent_stack_call_words(expected['events'], regs)
            actual_slots = [COUNT_SLOT_BY_CONTINUATION[word] for word in words
                            if word in COUNT_SLOT_BY_CONTINUATION]
            oracle_require(actual_slots == call_slots,
                           case['name'] + f': literal count-slot CALL order {actual_slots}/{call_slots}')
    elif case.get('provider_counter'):
        oracle_require('counter-provider-fired' in expected['used'],
                       case['name'] + ': counter provider did not fire')

    if case.get('provider_glyph_ds') is not None:
        oracle_require('glyph-pop-ds-provider' in expected['used'] and
                       expected['regs']['ds'] == case['provider_glyph_ds'],
                       case['name'] + ': glyph POP DS did not return the provider value')
    if case.get('provider_outer_return') is not None and not core:
        oracle_require(expected['regs']['ip'] == case['provider_outer_return'] and
                       'outer-return-provider' in expected['used'],
                       case['name'] + ': adapter did not read the live outer return word')
    if expected_status is not None:
        oracle_require(expected['status'] == expected_status,
                       case['name'] + ': changed-child status differs')


def verify_actual_div_trap():
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INTR
    from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_CS,
                                   UC_X86_REG_CX, UC_X86_REG_IP)

    oracle_require(DIV_BYTES == b'\xF6\xF1',
                   f'actual byte DIV encoding changed: {DIV_BYTES.hex()}')
    for ax, divisor, name in ((300, 1, 'quotient-overflow'),
                              (0x1234, 0, 'zero-divisor')):
        cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        cpu.mem_map(0, 0x10000)
        cpu.mem_write(0x1000, DIV_BYTES)
        cpu.reg_write(UC_X86_REG_CS, 0)
        cpu.reg_write(UC_X86_REG_IP, 0x1000)
        cpu.reg_write(UC_X86_REG_AX, ax)
        cpu.reg_write(UC_X86_REG_CX, divisor)
        traps = []

        def on_interrupt(machine, number, _user):
            traps.append(number)
            machine.emu_stop()

        cpu.hook_add(UC_HOOK_INTR, on_interrupt)
        try:
            cpu.emu_start(0x1000, 0, count=2)
        except Exception as error:
            raise OracleFailure(f'{name}: tiny original DIV execution failed') from error
        oracle_require(traps == [0], f'{name}: original DIV did not signal INT0: {traps!r}')


def original(case, memory, regs, device, *, core=True):
    return run_reference(case, memory, regs, device, core=core)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        native_case = dict(case, _native=True)
        self.access = DisplayAccess(native_case, memory, regs, device)
        self.events, self.used = self.access.events, self.access.used

        def read(_ctx, _mem, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'status-display read callback failed: {error}')

        def write(_ctx, _mem, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'status-display write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'status-display OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-display-m{mutation}.dll',
                     mutation, 'status_display')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_update_status_display_suffix_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_update_status_display_suffix_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial_memory, initial_regs, initial_device, *, core):
        memory = bytearray(initial_memory)
        regs_dict = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs_dict, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs_dict)
        if core:
            call = Call(*(regs_dict[name] for name in CORE_NAMES))
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
    expected = run_reference(case, initial, regs, device, core=core)
    assert_independent(case, initial, regs, expected, core=core)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    if case.get('divide_error'):
        want_status = 1
    elif case.get('alter_glyph_return') is not None:
        # The leaf oracle reports its raw changed-return status; the parent
        # translates that boundary to CHILD_STOP and preserves the leaf code.
        want_status = 4
    else:
        want_status = expected['status']
    require(actual['status'] == want_status,
            f'{label}: status {actual["status"]}/{want_status}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    for name in REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: provider effects {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': full VGA planes/latches/registers differ')
    if core and case.get('expected_child_entry') is not None:
        require(actual['child_entry'] == case['expected_child_entry'],
                f'{label}: child entry {actual["child_entry"]:04X}/'
                f'{case["expected_child_entry"]:04X}')
        require(actual['child_status'] == case['expected_child_status'],
                f'{label}: child status {actual["child_status"]}/'
                f'{case["expected_child_status"]}')
        require(actual['continuation'] == case['expected_continuation'],
                f'{label}: child continuation {actual["continuation"]:04X}/'
                f'{case["expected_continuation"]:04X}')
    if case.get('divide_error'):
        require(actual['continuation'] == DIVIDE,
                f'{label}: DIVIDE_ERROR did not retain the pre-DIV IP')
    return dict(name=case['name'], core=core, status=actual['status'],
                continuation=actual['continuation'],
                parent_sites=sorted(off for source, off in expected['sites']
                                    if source == 'main' and off in PARENT_SITES),
                parent_edges=[list(edge[1:]) for edge in sorted(expected['edges'])
                              if edge[0] == 'main' and edge[1] in PARENT_SITES],
                child_sites=sorted(off for source, off in expected['sites']
                                   if source == 'main' and off in CHILD_INS),
                steps=expected['steps'], events=len(expected['events']))


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/status_display.asm',
        'src/status_glyphs.asm', 'src/status_icons.asm',
        'src/game_code_before_minimap.asm', 'src/game_code_late_after_selection.asm',
        'src/image_tail.asm',
        'c/status_display.c', 'c/status_display.h', 'c/status_text.c',
        'c/status_text.h', 'c/status_glyph.c', 'c/status_glyph.h',
        'c/status_count.c', 'c/status_count.h', 'c/status_icons.c',
        'c/status_icons.h', 'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/status_display.py', 'tests/status_text.py', 'tests/status_glyph.py',
        'tests/status_count.py', 'tests/status_icons.py', 'tests/entity_interactions.py',
        'tests/minimap_vga.py', 'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tools/resources.py', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/adlib-symbols.json',
        'metadata/adlib-regions.json', 'metadata/tandysnd-symbols.json',
        'metadata/tandysnd-regions.json', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'tools/unpack.py', 'tools/common.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'status-display input hashes missing: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'status-display inputs changed before preflight')
    verify_actual_div_trap()
    rows, sites, edges = [], set(), set()
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = run_reference(case, initial, regs, device, core=core)
            assert_independent(case, initial, regs, expected, core=core)
            own_sites = {off for source, off in expected['sites']
                         if source == 'main' and off in PARENT_SITES}
            own_edges = {edge[1:] for edge in expected['edges']
                         if edge[0] == 'main' and edge[1] in PARENT_SITES}
            rows.append(dict(name=case['name'], core=core, status=expected['status'],
                             sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == PARENT_SITES,
                   f'original suffix sites differ: missing={sorted(PARENT_SITES-sites)}')
    oracle_require(edges == PARENT_EDGES,
                   f'original suffix outcomes differ: missing={sorted(PARENT_EDGES-edges)} '
                   f'extra={sorted(edges-PARENT_EDGES)}')
    oracle_require(before == input_hashes(), 'status-display inputs changed during preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'status-display inputs changed before native worker')
    specs = cases()
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
    oracle_require(sites == PARENT_SITES,
                   f'native suffix site union differs: missing={sorted(PARENT_SITES-sites)}')
    oracle_require(edges == PARENT_EDGES,
                   f'native suffix outcomes differ: missing={sorted(PARENT_EDGES-edges)}')

    lookup = {case['name']: case for case in specs}
    witnesses = {
        1: 'divide-overflow-at-three-over-one',
        2: 'unclamped-255-through-division',
        3: 'selector-snapshot-reread-after-outline-provider',
        4: 'zero-percent-zero-count-forces-all-ten-and-wraps-ff',
        5: 'all-changed-counts-ack-counter-two',
        6: 'mixed-literal-slot-order-and-counter-wrap',
        7: 'changed-parent-text-call-return',
        8: 'returned-ds-from-live-glyph-stack-save',
    }
    mutants = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        case = lookup[name]
        try:
            compare_case(variant, case, core=True)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'status-display mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'status-display inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[0x3ACE, 0x3B08], [0x3B09, 0x3CDE]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(PARENT_SITES),
        static_instruction_addresses=sorted(PARENT_SITES),
        branch_edge_count=len(PARENT_EDGES),
        static_branch_edges=[list(edge) for edge in sorted(PARENT_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutants), mutations=mutants,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(edge) for edge in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domains=[
            '3ACE..3CDD suffix: 527 known bytes/172 sites, excluding UNKNOWN 3B08',
            'percentage numerator 100*completion, live DIV divisor, zero bypass, exact 100 special case and raw unclamped values',
            'DIV overflow status stops at 3AED before the instruction; a separate two-byte original DIV probe observes INT0 without modeling its frame',
            'ten count triples in literal slot order, including zero redraw, snapshot skips, counter-two acknowledgement and byte wrap',
            'selector snapshot/refresh acknowledgement and signed old-icon clear aliases into count triples',
            'text, glyph, outline, restore and count leaves composed under their actual SS:SP CALL frames',
            'whole 1 MiB RAM, logical registers, defined flags, ordered byte/word callbacks and complete four-plane VGA state',
            'DF-sensitive child strings, live providers, DS return, DS:SS alias and VGA-backed stack',
        ]))
    print(f'PASS status display: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)}/172 sites, {len(edges)}/{len(PARENT_EDGES)} edges, '
          f'{total_events} events, {len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-display-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, edges = original_campaign(cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE),
            code_ranges=[[0x3ACE, 0x3B08], [0x3B09, 0x3CDE]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(PARENT_SITES),
            static_instruction_addresses=sorted(PARENT_SITES),
            branch_edge_count=len(PARENT_EDGES), branch_edges=[list(e) for e in sorted(edges)],
            executed_instruction_addresses=sorted(sites), case_count=len(cases()),
            core_adapter_comparisons=len(rows), input_hashes=before, cases=rows,
            domains=['bounded original composition and independent percentage/count projections',
                     'separate two-byte DIV/INT0 probe; no divide-error frame modeled']))
        print(f'PASS status display original preflight: {len(cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_display.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-display-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
