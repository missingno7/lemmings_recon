"""Bounded original-versus-native checks for SelectEntityCandidate."""
from __future__ import annotations

import copy
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
from common import BUILD, sha, write_json
import entity_interactions as interactions
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK = interactions.SIZE, interactions.MASK
FLAGS = interactions.FLAGS
ENTRY, END, OUTER_RET = 0x3CDE, 0x3E6F, 0x3E62
FORMAT_ENTRY, FORMAT_END, FORMAT_RET = 0x4B68, 0x4BBE, 0x4BBD
MAIN_SEG = interactions.MAIN_SEG
DATA_SEG = (MAIN_SEG + 0x09A9) & 0xFFFF
RECORD_BASE, RECORD_SIZE = 0x0088, 0x002D
MAX_INSTRUCTIONS, MAX_EVENTS = 20000, 20000
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-select-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-select-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
UNKNOWN = {0x3D26, 0x3D44, 0x3D4B, 0x3D57,
           0x3D66, 0x3D70, 0x3D77, 0x3DE7}
KNOWN_RANGES = ((0x3CDE, 0x3D26), (0x3D27, 0x3D44),
                (0x3D45, 0x3D4B), (0x3D4C, 0x3D57),
                (0x3D58, 0x3D66), (0x3D67, 0x3D70),
                (0x3D71, 0x3D77), (0x3D78, 0x3DE7),
                (0x3DE8, 0x3E63), (0x3E63, 0x3E6F))


def disassemble(ranges):
    out = {}
    for start, end in ranges:
        for ins in MD.disasm(IMAGE[start:end], start):
            if ins.address in out:
                raise AssertionError(f'duplicate instruction {ins.address:04X}')
            out[ins.address] = ins
    return out


OWN_INS = disassemble(KNOWN_RANGES)
FORMAT_INS = disassemble(((FORMAT_ENTRY, FORMAT_END),))
MAIN_INS = dict(OWN_INS)
MAIN_INS.update(FORMAT_INS)


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
    """The independent original/provider did not reach its declared boundary."""


class NativeMismatch(AssertionError):
    """A completed original/native comparison differed."""


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


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def record_offset(index):
    return (RECORD_BASE + ((index & 0xFFFF) * RECORD_SIZE)) & 0xFFFF


def put_record(memory, ds, index, record, device=None):
    """Seed one live record, writing equal plane values for the A000 fixture."""
    base = record_offset(index)
    x, y = record.get('x', 0x40), record.get('y', 0x40)
    width, height = record.get('width', 0x40), record.get('height', 0x40)
    values = bytearray((0x31 + index * 17 + i * 7) & 0xFF
                       for i in range(RECORD_SIZE))
    values[0:2] = (x & 0xFFFF).to_bytes(2, 'little')
    values[2:4] = (y & 0xFFFF).to_bytes(2, 'little')
    values[4:6] = (width & 0xFFFF).to_bytes(2, 'little')
    values[6:8] = (height & 0xFFFF).to_bytes(2, 'little')
    values[8:10] = (record.get('state', 0) & 0xFFFF).to_bytes(2, 'little')
    values[0x24] = record.get('entity_flags', 0) & 0xFF
    values[0x25] = record.get('byte25', 0) & 0xFF
    values[0x26] = record.get('active', 0) & 0xFF
    for i, value in enumerate(values):
        seed_byte(memory, ds, (base + i) & 0xFFFF, value, device)


def seed_byte(memory, segment, offset, value, device=None):
    address = physical(segment, offset)
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        plane_offset = address - VGA_BASE
        for plane in device.planes:
            plane[plane_offset] = value


def cases():
    """Focused selection semantics, full short-count domain and hard edges."""
    dense_hits = {i: {'entity_flags': 0x80} for i in range(0xFF)}
    # The pre-scan display clear overwrites record 182 at DS:2086. That
    # record's post-clear geometry cannot hit; the remaining 254 still do.
    rows = [
        dict(name='zero-bound-stale-output', bound=0, hits={0: {}}, selected=0x3333,
             selected_index=0x22, preferred=0x4444, preferred_index=0x11,
             alternate=0x5555, alternate_index=0x33, count=7,
             present=0xA5, output=b'OLD-OUTPUT!'),
        dict(name='one-bound-all-inactive', bound=1),
        dict(name='full-255-inactive-scan', bound=0xFF),
        dict(name='full-255-scan-254-hits-display-alias', bound=0xFF,
             hits=dense_hits, x=0x20, xdelta=0x70, y=0x78),
        dict(name='alternate-fallback-one-hit', bound=1,
             hits={0: {}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='preferred-flags80-one-hit', bound=1,
             hits={0: {'entity_flags': 0x80}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='force-alternate-button-mask2', bound=2,
             hits={0: {'entity_flags': 0x80}, 1: {}}, button=2,
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='last-hit-wins-both-buckets', bound=4,
             hits={0: {}, 1: {'entity_flags': 0x80},
                   2: {}, 3: {'entity_flags': 0x80}},
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='forced-alternate-missing-does-not-use-preferred', bound=2,
             hits={0: {'entity_flags': 0x80}}, button=2,
             selected=0x1111, x=0x20, xdelta=0x70, y=0x78),
        dict(name='preferred-index-live-bound-reread', bound=3,
             hits={1: {'entity_flags': 0x80}}, bound_after_entry=0x20,
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='preferred-hit-live-index-wraps-to-sentinel', bound=1,
             hits={0: {'entity_flags': 0x80}}, bound_after_entry=0,
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='alternate-hit-live-index-wraps-to-sentinel', bound=1,
             hits={0: {}}, bound_after_entry=0,
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='second-hit-uses-live-loop-count', bound=3,
             hits={0: {'entity_flags': 0x80}, 1: {'entity_flags': 0x80}},
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='push-ax-store-pop-alias', bound=2,
             hits={0: {'entity_flags': 0x80},
                   1: {'x': 0, 'y': 0x40, 'width': 0x20}},
             x=0x20, xdelta=0x70, y=0x78, ss=DATA_SEG, sp=0x0062),
        dict(name='inactive-hole-before-hit', bound=5,
             hits={4: {}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='box-low-edge-inclusive', bound=1, hits={0: {}},
             screen_x=0x7C, screen_y=0x7F),
        dict(name='box-high-edge-inclusive', bound=1, hits={0: {}},
             screen_x=0x88, screen_y=0x8B),
        dict(name='vertical-lower-reject-after-x-pass', bound=1,
             hits={0: {'y': 0x60, 'height': 0x40}},
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='vertical-upper-reject-after-x-pass', bound=1,
             hits={0: {'y': 0x40, 'height': 0x40}},
             x=0x20, xdelta=0x70, y=0x88),
        dict(name='signed-negative-x-geometry', bound=1, hits={0: {}},
             screen_x=0xF000, screen_y=0x80,
             x=0, width=0x100, y=0x78),
        dict(name='x-upper-clamp-0680-to-00d0', bound=1,
             screen_x=0x067F, screen_y=0x80,
             hits={0: {'x': 0x80, 'width': 0x600}},
             x=0x80, width=0x600, y=0x78),
        dict(name='x-upper-clamp-boundary-below', bound=1,
             hits={0: {'x': 0x80, 'width': 0x5F7}},
             screen_x=0x067F, screen_y=0x80,
             x=0x80, width=0x5F7, y=0x78),
        dict(name='y-upper-clamp-b0', bound=1,
             hits={0: {'y': 0x00A8, 'height': 1}},
             screen_x=0x80, y=0x00A8, height=1, screen_y=0x00B0),
        dict(name='wrapped-negative-left-clamps-zero', bound=1,
             hits={0: {'x': 0xFF00, 'width': 4, 'y': 0x40}},
             screen_x=0x0C, screen_y=0x80, x=0x1C, xdelta=0, y=0x78),
        dict(name='wrapped-negative-top-clamps-zero', bound=1,
             hits={0: {'x': 0x40, 'y': 0xFF00, 'height': 1}},
             screen_x=0x80, x=0x90, xdelta=0, screen_y=0x0C),
        dict(name='state-preference-8000', bound=1,
             hits={0: {'state': 0x8000}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='state-preference-0800', bound=1,
             hits={0: {'state': 0x0800}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='state-preference-0100', bound=1,
             hits={0: {'state': 0x0100}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='state-preference-0080', bound=1,
             hits={0: {'state': 0x0080}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='state-preference-0010', bound=1,
             hits={0: {'state': 0x0010}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-class-state-priority', bound=1,
             hits={0: {'state': 0x0B94}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-bit1-zero-byte25', bound=1,
             hits={0: {'entity_flags': 1, 'byte25': 0}},
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-bit1-nonzero-byte25', bound=1,
             hits={0: {'entity_flags': 1, 'byte25': 7}},
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-byte25-without-bit1', bound=1,
             hits={0: {'byte25': 7}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-state-bit-0100', bound=1,
             hits={0: {'state': 0x0100}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-state-bit-0080', bound=1,
             hits={0: {'state': 0x0080}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-state-bit-0200', bound=1,
             hits={0: {'state': 0x0200}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-state-bit-0800', bound=1,
             hits={0: {'state': 0x0800}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-state-bit-0010', bound=1,
             hits={0: {'state': 0x0010}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-state-bit-0004', bound=1,
             hits={0: {'state': 0x0004}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-default-state', bound=1,
             hits={0: {}}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-provider-live-pointer', bound=1,
             hits={0: {'entity_flags': 0x80}}, extra_records={9: {'state': 4}},
             provider='selected-pointer', provider_pointer=record_offset(9),
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='template-provider-rereads-later-byte', bound=1,
             hits={0: {'entity_flags': 0x80}}, provider='template-byte',
             provider_template_offset=0x48DB, provider_template_byte=0xE7,
             x=0x20, xdelta=0x70, y=0x78),
        dict(name='formatted-count-10', bound=10,
             hits={i: {} for i in range(10)}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='formatted-count-100', bound=100,
             hits={i: {} for i in range(100)}, x=0x20, xdelta=0x70, y=0x78),
        dict(name='actual-formatter-return-alias', bound=1,
             hits={0: {}}, x=0x20, xdelta=0x70, y=0x78,
             ss=DATA_SEG, sp=0x208D),
        dict(name='outer-ret-physical-20bit-wrap', bound=1,
             ss=0xFFFF, sp=0x000F, outer_return=0xA55A),
        dict(name='vga-ds-data-and-template', bound=1, ds=0xA000,
             hits={0: {'entity_flags': 0x80}}, x=0x20, xdelta=0x70, y=0x78,
             vga=True),
        dict(name='vga-ss-live-stack-df-set', bound=2,
             hits={0: {'entity_flags': 0x80}}, x=0x20, xdelta=0x70, y=0x78,
             ss=0xA000, sp=0xC000, vga=True, flags=0x04D7),
        dict(name='nondefault-live-registers', bound=1,
             hits={0: {}}, x=0x20, xdelta=0x70, y=0x78,
             ax=0xDEAD, bx=0xBEEF, cx=0xA500, dx=0x1357,
             si=0x2468, di=0x369A, bp=0xABCD, es=0x3456,
             flags=0x0A55),
        dict(name='count-provider-reaches-ff', bound=1, hits={0: {}},
             provider='count-before-inc', provider_count=0xFE,
             x=0x20, xdelta=0x70, y=0x78),
    ]
    oracle_require(len(rows) == 51 and
                   len({case['name'] for case in rows}) == len(rows),
                   f'entity-select fixture inventory changed: {len(rows)}')
    for index, case in enumerate(rows):
        case.setdefault('seed', 0x3CDE00 + index * 313)
        case.setdefault('bound', 1)
        case.setdefault('hits', {})
        case.setdefault('extra_records', {})
        case.setdefault('x', 0x20)
        if 'xdelta' not in case:
            case['xdelta'] = ((case['screen_x'] - case['x'] + 0x10) & 0xFFFF
                              if 'screen_x' in case else 0x70)
        case.setdefault('screen_x',
                         (case['x'] - 0x10 + case['xdelta']) & 0xFFFF)
        if 'y' not in case:
            case['y'] = ((case['screen_y'] - 8) & 0xFFFF
                         if 'screen_y' in case else 0x78)
        case.setdefault('screen_y', (case['y'] + 8) & 0xFFFF)
        case.setdefault('button', 0)
        case.setdefault('selected', 0x7777)
        case.setdefault('selected_index', 0x66)
        case.setdefault('preferred', 0x8888)
        case.setdefault('preferred_index', 0x55)
        case.setdefault('alternate', 0x9999)
        case.setdefault('alternate_index', 0x44)
        case.setdefault('count', 0x22)
        case.setdefault('present', 0x7E)
        case.setdefault('output', b'KEEP-THIS!!')
        case.setdefault('flags', 0x02D7)
        case.setdefault('ds', DATA_SEG)
        case.setdefault('ss', 0x5000)
        case.setdefault('sp', 0xD000)
        case.setdefault('es', 0x6200)
        case.setdefault('outer_return', 0x6A5C)
    return rows


TEMPLATES = (0x48BF, 0x48C6, 0x48D4, 0x48DB, 0x48E2,
             0x48E9, 0x48F0, 0x48F7, 0x48FE, 0x490C)


def setup(case):
    # The interactions fixture's VGA setup assumes SS itself is the VGA
    # segment. This test owns the device and may map VGA through DS instead.
    template = dict(case, load=MAIN_SEG, poison=False, vga=False)
    memory, regs, _device, _pc, _sound, _ = interactions.setup(template)
    ds, ss, sp = case['ds'] & 0xFFFF, case['ss'] & 0xFFFF, case['sp'] & 0xFFFF
    device = (MinimapVga(case['seed'] ^ 0xA000, read_map=0)
              if case.get('vga') else None)
    if device is not None:
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[4] = 0
        device.gc[6] = 0x05
        device.gc[8] = 0xFF
        for plane in device.planes:
            plane[:] = bytes(65536)

    regs.update(ax=case.get('ax', 0x1357) & 0xFFFF,
                bx=case.get('bx', 0x2468) & 0xFFFF,
                cx=case.get('cx', 0xA5E1) & 0xFFFF,
                dx=case.get('dx', 0x0055) & 0xFFFF,
                si=case.get('si', 0x4000) & 0xFFFF,
                di=case.get('di', 0x3131) & 0xFFFF,
                bp=case.get('bp', 0x7B2D) & 0xFFFF,
                cs=MAIN_SEG, ip=ENTRY, ds=ds, es=case['es'] & 0xFFFF,
                ss=ss, sp=sp, flags=(case['flags'] | 2) & 0xFFFF)

    for offset, value in ((0x0000, case['x']), (0x0010, case['xdelta']),
                          (0x0012, case['y']), (0x0014, case['button']),
                          (0x0043, case['bound']), (0x0058, case['selected']),
                          (0x005A, case['alternate']), (0x005C, case['preferred']),
                          (0x005E, case['selected_index']),
                          (0x005F, case['alternate_index']),
                          (0x0060, case['preferred_index']),
                          (0x0063, case['count']), (0x001A, case['present'])):
        width = 2 if offset in (0, 0x10, 0x12, 0x14, 0x58, 0x5A, 0x5C) else 1
        if offset == 0:
            value = case['x']
        elif offset == 0x10:
            value = case['xdelta']
        elif offset == 0x12:
            value = case['y']
        if width == 2:
            seed_byte(memory, ds, offset, value & 0xFF, device)
            seed_byte(memory, ds, offset + 1, value >> 8, device)
        else:
            seed_byte(memory, ds, offset, value, device)
    output = bytes(case['output'])[:11].ljust(11, b'!')
    for i, value in enumerate(output):
        seed_byte(memory, ds, 0x2083 + i, value, device)
    for template_offset in TEMPLATES:
        for i in range(7):
            value = (template_offset * 3 + i * 29 + 0x41) & 0xFF
            seed_byte(memory, ds, template_offset + i, value, device)

    for index in range(case['bound']):
        put_record(memory, ds, index, {'active': 0xFF}, device)
    for index, record in case['hits'].items():
        put_record(memory, ds, index, {'active': 0, **record}, device)
    for index, record in case['extra_records'].items():
        put_record(memory, ds, index, {'active': 0xFF, **record}, device)
    if ds == DATA_SEG:
        # The synthetic DS input coordinates are globals and must remain distinct
        # from the 2D-byte record pool in ordinary-memory fixtures.
        pass
    seed_byte(memory, ss, sp, case['outer_return'] & 0xFF, device)
    seed_byte(memory, ss, sp + 1, case['outer_return'] >> 8, device)
    return memory, regs, device


class SelectAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.pending = []
        self.native = bool(case.get('_native', False))

    def _queue_byte(self, segment, offset, value, label):
        address = physical(segment, offset)
        self.pending.append((address, value & 0xFF, label))

    def _queue_word(self, segment, offset, value, label):
        address = physical(segment, offset)
        self.pending.append((address, value & 0xFF, label + '-lo'))
        self.pending.append(((address + 1) & MASK, (value >> 8) & 0xFF,
                             label + '-hi'))

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for address, value, label in pending:
            self.store(address, value)
            self.used.add(label)

    def _provider_before(self, kind, address, value=None):
        case, ds = self.case, self.regs['ds']
        if (kind == 'write' and case.get('provider') == 'count-before-inc' and
                address == physical(ds, 0x0063) and value == 0 and
                'count-before-inc' not in self.used):
            self._queue_byte(ds, 0x0063, case['provider_count'],
                             'count-before-inc')
        if (kind == 'read' and case.get('provider') == 'template-byte' and
                address == physical(ds, case['provider_template_offset']) and
                'template-byte' not in self.used):
            self._queue_byte(ds, case['provider_template_offset'] + 1,
                             case['provider_template_byte'], 'template-byte')
        if (kind == 'write' and case.get('provider') == 'selected-pointer' and
                address == physical(ds, 0x001A) and value == 0xFF and
                'selected-pointer' not in self.used):
            self._queue_word(ds, 0x0058, case['provider_pointer'],
                             'selected-pointer')
            self.used.add('selected-pointer')
        if (kind == 'read' and address == physical(ds, 0x0043) and
                case.get('bound_after_entry') is not None and
                'bound-after-entry' not in self.used):
            self._queue_byte(ds, 0x0043, case['bound_after_entry'],
                             'bound-after-entry')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-select callback event budget exhausted')
        address &= MASK
        self._provider_before(kind, address, value)
        if kind == 'read':
            if self.device is not None and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
            else:
                value = self.memory[address]
            self.store(address, value)
        else:
            value &= 0xFF
            if self.device is not None and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF,
                            flags & 0xFFFF, mask))
        if self.native and self.pending:
            self.instruction_complete()
        return value & 0xFF


def original(case, memory, regs, device, *, core):
    ret_contracts = {0x3DF3: ({FORMAT_RET}, 1)}
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=MAIN_INS,
        main_call_returns=ret_contracts, access_factory=SelectAccess,
        stop_offsets={OUTER_RET: 0} if core else None,
        instruction_limit=MAX_INSTRUCTIONS)


def independent_projection(case, initial, initial_regs, *, core):
    """Small independent geometry/bucket/template projection, with live aliases."""
    mem = bytearray(initial)
    ds = case['ds'] & 0xFFFF
    ss = case['ss'] & 0xFFFF
    sp = case['sp'] & 0xFFFF

    def r8(off):
        return get8(mem, ds, off)

    def w8(off, value):
        put8(mem, ds, off, value)

    def r16(off):
        return get16(mem, ds, off)

    def w16(off, value):
        put16(mem, ds, off, value)

    bound = r8(0x43)
    if case.get('bound_after_entry') is not None:
        w8(0x43, case['bound_after_entry'])
    out = dict(memory=mem, status=0, continuation=OUTER_RET,
               selected=None, selected_index=None, candidate_count=None,
               expected_template=None, format_return=None)
    if not bound:
        out['continuation'] = (case['outer_return'] & 0xFFFF) if not core else OUTER_RET
        if not core:
            out['continuation'] = get16(mem, ss, sp)
        return out

    # MOV/INC/DEC clear the fixed 11-byte display row before scanning.
    for i in range(11):
        w8(0x2083 + i, 0x20)
    w8(0x0063, 0)
    if case.get('provider') == 'count-before-inc':
        w8(0x0063, case['provider_count'])
    w8(0x005E, 0xFF)
    w8(0x0060, 0xFF)
    w8(0x005F, 0xFF)
    ax = (r16(0) - 0x10 + r16(0x10)) & 0xFFFF
    bx = (r16(0x12) + 8) & 0xFFFF
    loop_count = bound
    si = RECORD_BASE
    while loop_count:
        record = si
        if r8((record + 0x26) & 0xFFFF) != 0xFF:
            left = (get16(mem, ds, record) + get16(mem, ds,
                    (record + 4) & 0xFFFF) - 4) & 0xFFFF
            if left & 0x8000:
                left = 0
            top = (get16(mem, ds, (record + 2) & 0xFFFF) +
                   get16(mem, ds, (record + 6) & 0xFFFF) - 1) & 0xFFFF
            if top & 0x8000:
                top = 0
            if signed16(ax) >= signed16(left) and signed16(bx) >= signed16(top):
                right = (left + 0x0C) & 0xFFFF
                if signed16(right) >= signed16(0x0680):
                    right = 0x00D0
                bottom = (top + 0x0C) & 0xFFFF
                if signed16(bottom) >= signed16(0x00B0):
                    bottom = 0x00B0
                if signed16(ax) <= signed16(right) and signed16(bx) <= signed16(bottom):
                    sp = (sp - 2) & 0xFFFF
                    put16(mem, ss, sp, ax)
                    preferred = ((r8((record + 0x24) & 0xFFFF) & 0x80) != 0 or
                                 (get16(mem, ds, (record + 8) & 0xFFFF) & 0x8B90) != 0)
                    live_bound = r8(0x43)
                    index = (live_bound - loop_count) & 0xFF
                    if preferred:
                        w8(0x0060, index)
                        w16(0x005C, record)
                    else:
                        w8(0x005F, index)
                        w16(0x005A, record)
                    ax = get16(mem, ss, sp)
                    sp = (sp + 2) & 0xFFFF
                    w8(0x0063, r8(0x0063) + 1)
        si = (si + RECORD_SIZE) & 0xFFFF
        loop_count = (loop_count - 1) & 0xFF

    w8(0x001A, 0)
    if get16(mem, ds, 0x0014) & 2:
        index = r8(0x005F)
        selected = r16(0x005A)
        w8(0x005E, index)
        w16(0x0058, selected)
    else:
        index = r8(0x0060)
        if index == 0xFF:
            index = r8(0x005F)
            selected = r16(0x005A)
        else:
            selected = r16(0x005C)
        w8(0x005E, index)
        w16(0x0058, selected)
    selected_index = r8(0x005E)
    out.update(selected=r16(0x0058), selected_index=selected_index,
               candidate_count=r8(0x0063))
    if selected_index == 0xFF:
        out['continuation'] = OUTER_RET if core else get16(mem, ss, sp)
        out['memory'] = mem
        return out

    w8(0x001A, 0xFF)
    count = r8(0x0063)
    out['candidate_count'] = count

    # CALL 4B68 pushes the actual return; the formatter's live RET reads it back.
    sp = (sp - 2) & 0xFFFF
    put16(mem, ss, sp, 0x3DF6)
    for i in range(3):
        w8(0x208B + i, 0x20)
    display = f'{count:d}'.encode('ascii').ljust(3, b' ')
    for i, value in enumerate(display):
        w8(0x208B + i, value)
    fmt_return = get16(mem, ss, sp)
    sp = (sp + 2) & 0xFFFF
    out['format_return'] = fmt_return
    if fmt_return != 0x3DF6:
        out.update(status=1, continuation=fmt_return, memory=mem)
        return out

    if case.get('provider') == 'selected-pointer':
        w16(0x0058, case['provider_pointer'])
    # 3DF6 rereads the pointer; no selection snapshot is carried into copying.
    selected = r16(0x0058)
    entity_flags = r8((selected + 0x24) & 0xFFFF)
    state = get16(mem, ds, (selected + 8) & 0xFFFF)
    byte25 = r8((selected + 0x25) & 0xFFFF)
    if entity_flags & 0x80:
        template = 0x48DB
    elif entity_flags & 1:
        template = 0x490C if byte25 else 0x48BF
    elif byte25:
        template = 0x48C6
    elif state & 0x0100:
        template = 0x48D4
    elif state & 0x0080:
        template = 0x48DB
    elif state & 0x0200:
        template = 0x48E2
    elif state & 0x0800:
        template = 0x48E9
    elif state & 0x0010:
        template = 0x48F0
    elif state & 0x0004:
        template = 0x48FE
    else:
        template = 0x48F7
    out['expected_template'] = template
    for i in range(7):
        if (case.get('provider') == 'template-byte' and i == 0 and
                template == case.get('provider_template_offset')):
            w8(template + 1, case['provider_template_byte'])
        value = r8(template + i)
        w8(0x2083 + i, value)
    out['selected'] = selected
    out['memory'] = mem
    out['continuation'] = OUTER_RET if core else get16(mem, ss, sp)
    if not core:
        sp = (sp + 2) & 0xFFFF
    return out


def assert_independent(case, initial, regs, observed, *, core):
    expected = independent_projection(case, initial, regs, core=core)
    name = case['name']
    oracle_require((observed['status'], observed['continuation']) ==
                   (expected['status'], expected['continuation']),
                   f'{name}: independent boundary {observed["status"]}/'
                   f'{observed["continuation"]:04X} != '
                   f'{expected["status"]}/{expected["continuation"]:04X}')
    # The independent state/format model checks all bytes it owns. The CPU
    # oracle remains authoritative for unspecified frame and register effects.
    oracle_require(observed['memory'] == bytes(expected['memory']),
                   name + ': independent candidate/template projection differs')
    if expected['selected_index'] is not None:
        ds = case['ds'] & 0xFFFF
        oracle_require(get8(observed['memory'], ds, 0x005E) ==
                       expected['selected_index'], name + ': selected index mismatch')
    semantic = {
        'zero-bound-stale-output': (7, 0x22, 0x3333, 0xA5),
        'full-255-scan-254-hits-display-alias': (0xFE, 0xFE,
                                             record_offset(0xFE), 0xFF),
        'alternate-fallback-one-hit': (1, 0, record_offset(0), 0xFF),
        'preferred-flags80-one-hit': (1, 0, record_offset(0), 0xFF),
        'force-alternate-button-mask2': (2, 1, record_offset(1), 0xFF),
        'last-hit-wins-both-buckets': (4, 3, record_offset(3), 0xFF),
        'forced-alternate-missing-does-not-use-preferred':
            (1, 0xFF, 0x9999, 0),
        'preferred-index-live-bound-reread': (1, 0x1E,
                                                record_offset(1), 0xFF),
        'preferred-hit-live-index-wraps-to-sentinel': (1, 0xFF, 0x9999, 0),
        'alternate-hit-live-index-wraps-to-sentinel':
            (1, 0xFF, record_offset(0), 0),
        'second-hit-uses-live-loop-count': (2, 1, record_offset(1), 0xFF),
        'inactive-hole-before-hit': (1, 4, record_offset(4), 0xFF),
        'box-low-edge-inclusive': (1, 0, record_offset(0), 0xFF),
        'box-high-edge-inclusive': (1, 0, record_offset(0), 0xFF),
        'template-byte25-without-bit1': (1, 0, record_offset(0), 0xFF),
        'signed-negative-x-geometry': (0, 0xFF, 0x9999, 0),
        'vertical-lower-reject-after-x-pass': (0, 0xFF, 0x9999, 0),
        'vertical-upper-reject-after-x-pass': (0, 0xFF, 0x9999, 0),
        'x-upper-clamp-0680-to-00d0': (0, 0xFF, 0x9999, 0),
        'x-upper-clamp-boundary-below': (1, 0, record_offset(0), 0xFF),
        'y-upper-clamp-b0': (1, 0, record_offset(0), 0xFF),
        'wrapped-negative-left-clamps-zero': (1, 0, record_offset(0), 0xFF),
        'wrapped-negative-top-clamps-zero': (1, 0, record_offset(0), 0xFF),
    }
    if name in semantic:
        expected_count, expected_index, expected_pointer, expected_present = semantic[name]
        ds = case['ds'] & 0xFFFF
        oracle_require(get8(observed['memory'], ds, 0x0063) == expected_count,
                       name + ': fixture candidate-count intent did not hold')
        oracle_require(get8(observed['memory'], ds, 0x005E) == expected_index,
                       name + ': fixture selected-index intent did not hold')
        oracle_require(get16(observed['memory'], ds, 0x0058) == expected_pointer,
                       name + ': fixture selected-pointer intent did not hold')
        oracle_require(get8(observed['memory'], ds, 0x001A) == expected_present,
                       name + ': fixture selection-present intent did not hold')
    if name == 'full-255-scan-254-hits-display-alias':
        ds = case['ds'] & 0xFFFF
        oracle_require(observed['memory'][physical(ds, 0x208B):
                                           physical(ds, 0x208B) + 3] == b'254',
                       name + ': aliased scan count did not format 254')
        oracle_require(get8(observed['memory'], ds, 0x0063) == 0xFE,
                       name + ': clear/record alias did not leave 254 live hits')
    if name == 'count-provider-reaches-ff':
        ds = case['ds'] & 0xFFFF
        oracle_require(get8(observed['memory'], ds, 0x0063) == 0xFF and
                       observed['memory'][physical(ds, 0x208B):
                                           physical(ds, 0x208B) + 3] == b'255',
                       name + ': live count provider did not reach/formatted FF')
    if name == 'zero-bound-stale-output':
        ds = case['ds'] & 0xFFFF
        oracle_require(get8(observed['memory'], ds, 0x0063) == 7 and
                       get8(observed['memory'], ds, 0x005E) == 0x22 and
                       get16(observed['memory'], ds, 0x0058) == 0x3333 and
                       get8(observed['memory'], ds, 0x001A) == 0xA5 and
                       bytes(get8(observed['memory'], ds, 0x2083 + i)
                             for i in range(11)) == b'OLD-OUTPUT!',
                       name + ': zero-bound path changed stale candidate outputs')
    if case.get('bound_after_entry') is not None:
        oracle_require('bound-after-entry' in observed['used'],
                       name + ': live-bound provider did not fire')
    if case.get('provider') == 'selected-pointer':
        oracle_require('selected-pointer' in observed['used'],
                       name + ': selected-pointer provider did not fire')
    if case.get('provider') == 'template-byte':
        oracle_require('template-byte' in observed['used'],
                       name + ': template provider did not fire')
    if case.get('provider') == 'count-before-inc':
        oracle_require('count-before-inc' in observed['used'],
                       name + ': candidate-count provider did not fire')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under {want[4]:04X}')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, interactions.MEM,
                    ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, interactions.MEM,
                     ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class NativeBus:
    def __init__(self, case, memory, regs, device):
        access_case = dict(case, _native=True)
        self.access = SelectAccess(access_case, memory, regs, device)

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
                        f'unexpected selector OUT {port:04X}={value:04X}/{flags:04X}')

        self.callbacks = (READ(read), WRITE(write), OUT(out))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-select-m{mutation}.dll',
                     mutation, 'entity_select')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_select_entity_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_select_entity_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callbacks = NativeBus(case, memory, regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds',
                'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), ct.byref(callbacks.bus))
            state.ax, state.bx, state.cx, state.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            state.si, state.di, state.bp = (
                result.record_cursor, result.object_cursor,
                result.candidate_y)
            state.cs, state.ds, state.es = (
                result.code_segment, result.data_segment, result.extra_segment)
            state.ss, state.sp, state.flags, state.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(callbacks.bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs,
                    events=callbacks.access.events, used=callbacks.access.used,
                    device=device, status=status, continuation=final_regs['ip'])


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    oracle = original(case, initial, regs, device, core=core)
    assert_independent(case, initial, regs, oracle, core=core)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == oracle['status'],
            f'{label}: status {actual["status"]}/{oracle["status"]}')
    require(actual['continuation'] == oracle['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{oracle["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        require(actual['regs'][name] == oracle['regs'][name],
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{oracle["regs"][name]:04X}')
    require(((actual['regs']['flags'] ^ oracle['regs']['flags']) &
             oracle['flag_mask']) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {oracle["flag_mask"]:04X}')
    require(actual['memory'] == oracle['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    require(actual['used'] == oracle['used'],
            f'{label}: provider effects {actual["used"]}/{oracle["used"]}')
    if oracle['device'] is None:
        require(actual['device'] is None, label + ': unexpected VGA device')
    else:
        require(actual['device'] is not None and
                actual['device'].state() == oracle['device'].state(),
                label + ': VGA planes/latches/registers differ')
    sites = {address for source, address in oracle['sites']
             if source == 'main' and address in OWN_INS}
    edges = {(source_ip, target) for source, source_ip, target in oracle['edges']
             if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(sites),
                edges=[list(edge) for edge in sorted(edges)],
                events=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-actions.md', 'docs/decimal-field.md',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/adlib-regions.json',
        'metadata/adlib-encodings.json', 'metadata/tandysnd-symbols.json',
        'metadata/tandysnd-regions.json', 'metadata/tandysnd-encodings.json',
        'metadata/pcspeaker-symbols.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'src/entity_selection.asm', 'src/decimal_fields.asm',
        'c/entity_select.c', 'c/entity_select.h', 'c/decimal_field.c',
        'c/decimal_field.h', 'c/lemmings_sym.h', 'c/regs.h',
        'c/special_blit.h', 'tests/entity_select.py',
        'tests/entity_interactions.py', 'tests/pcspeaker_dispatch.py',
        'tests/sound_latches.py', 'tests/minimap_vga.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/coverage.py', 'tools/difftest.py', 'tools/resources.py',
        'tools/unpack.py', 'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'entity-select hash inputs missing: ' + repr(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(before):
    oracle_require(before == input_hashes(),
                   'entity-select input hashes changed before original campaign')
    oracle_require(len(OWN_INS) == 140 and
                   sum(ins.size for ins in OWN_INS.values()) == 393 and
                   len(OWN_EDGES) == 69,
                   f'entity-select accounting changed: {len(OWN_INS)} sites, '
                   f'{sum(ins.size for ins in OWN_INS.values())} bytes, '
                   f'{len(OWN_EDGES)} edges')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed main image hash changed')
    covered, edges, rows = set(), set(), []
    specs = cases()
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            observed = original(case, initial, regs, device, core=core)
            assert_independent(case, initial, regs, observed, core=core)
            sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
            case_edges = {(src, dst) for source, src, dst in observed['edges']
                          if source == 'main' and src in OWN_INS}
            covered.update(sites)
            edges.update(case_edges)
            rows.append(dict(name=case['name'], core=core,
                             status=observed['status'],
                             continuation=observed['continuation'],
                             sites=sorted(sites),
                             edges=[list(edge) for edge in sorted(case_edges)],
                             events=len(observed['events']), steps=observed['steps']))
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'entity-select original misses sites {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'entity-select original edge union differs: '
                   f'missing={sorted(OWN_EDGES-edges)} extra={sorted(edges-OWN_EDGES)}')
    oracle_require(before == input_hashes(),
                   'entity-select input hashes changed during original campaign')
    print(f'PASS entity select original: {len(specs)} fixtures x core/adapter, '
          f'{len(covered)} sites/{len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} events; bounded original only',
          flush=True)
    return rows, edges


def worker(directory, hash_path):
    import json
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'entity-select inputs changed before native worker')
    original_rows, _ = original_campaign(before)
    specs = cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    event_count = step_count = 0
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
                   f'entity-select native site union misses {sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == OWN_EDGES,
                   f'entity-select native edge union differs: '
                   f'missing={sorted(OWN_EDGES-edges)} extra={sorted(edges-OWN_EDGES)}')
    witnesses = {
        1: 'zero-bound-stale-output',
        2: 'preferred-index-live-bound-reread',
        3: 'second-hit-uses-live-loop-count',
        4: 'signed-negative-x-geometry',
        5: 'x-upper-clamp-0680-to-00d0',
        6: 'nondefault-live-registers',
        7: 'push-ax-store-pop-alias',
        8: 'last-hit-wins-both-buckets',
        9: 'actual-formatter-return-alias',
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
            raise OracleFailure(f'entity-select mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(before == input_hashes(),
                   'entity-select input hashes changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        known_code_bytes=sum(ins.size for ins in OWN_INS.values()),
        instruction_sites=len(OWN_INS), own_branch_edges=len(OWN_EDGES),
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        total_bus_events=event_count, original_code_hook_steps=step_count,
        original_only_case_count=len(original_rows), input_hashes=before,
        cases=[dict(name=row['name'], core=row['core'], sites=row['sites'],
                    edges=row['edges'], events=row['events'], steps=row['steps'])
               for row in rows],
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='SelectEntityCandidate 3CDE..3E6E and composed decimal formatter '
               'CALL 3DF3/RET 4BBD. The 8 UNKNOWN bytes remain excluded. Compares '
               'full 1 MiB RAM, all registers, original-defined FLAGS, ordered '
               'bus events, VGA plane/latch state, live stack/formatter return, '
               'and core-before-outer-RET versus adapter actual-RET behavior. '
               'Covers byte-bound loops, signed geometry/clamps, last-hit buckets, '
               'live bound/pointer/template providers and all template classes.'))
    print(f'PASS entity select: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {event_count} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        BUILD.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='entity-select-original-',
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
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            known_code_bytes=sum(ins.size for ins in OWN_INS.values()),
            instruction_sites=len(OWN_INS), own_branch_edges=len(OWN_EDGES),
            case_count=len(cases()),
            executed_instruction_addresses=sorted(
                {address for row in rows for address in row['sites']}),
            branch_edges=[list(edge) for edge in sorted(edges)], input_hashes=before,
            domain='Bounded original-only SelectEntityCandidate and formatter '
                   'CALL/RET comparison; focused aliases, providers, all template '
                   'classes and the complete 255-hit count path.'))
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_select.py [--original-only | --worker DIR]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-select-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
