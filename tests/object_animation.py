"""Bounded differential tests for the gated object-animation tick and tail."""
from __future__ import annotations

import ctypes as ct
import copy
import gc
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, read_json, sha, write_json
from dat_io_c import MEM, Regs
import entity_interactions as interactions
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
from unicorn import x86_const as x


IMAGE, META = unpack(ASSET.read_bytes())
SIZE = 1 << 20
MASK = SIZE - 1
LOAD = 0x1010
GATE_ENTRY, GATE_END = 0x3944, 0x394F
TAIL_ENTRY, TAIL_END = 0x7C0A, 0x7C67
DEFINITIONS = 0x0FEB
GRAPHICS = 0x17CB
UPDATE_GATE = 0x002B
TYPE_ONE_GATE = 0x0055
EARLY_RET = 0x394E
TAIL_RET = 0x7C66
DEFINED_FLAGS = 0x0FD7
ARITH_FLAGS = 0x08D5
LOGIC_FLAGS = DEFINED_FLAGS & ~0x0010
MAX_ORIGINAL_INSTRUCTIONS = 3000
MAX_BUS_EVENTS = 5000
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'object-animation-differential.json'
ORIGINAL_REPORT = BUILD / 'object-animation-original-differential.json'
CORE_NAMES = ('value', 'object_flags', 'count', 'auxiliary_value',
              'graphics_cursor', 'definition_cursor', 'frame_stride',
              'code_segment', 'data_segment', 'extra_segment',
              'stack_segment', 'stack_offset', 'flags')
RESULT_NAMES = CORE_NAMES + ('continuation', 'status')
REG_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'ip', 'flags')
REG_IDS = {
    'ax': x.UC_X86_REG_AX, 'bx': x.UC_X86_REG_BX,
    'cx': x.UC_X86_REG_CX, 'dx': x.UC_X86_REG_DX,
    'si': x.UC_X86_REG_SI, 'di': x.UC_X86_REG_DI,
    'bp': x.UC_X86_REG_BP, 'cs': x.UC_X86_REG_CS,
    'ds': x.UC_X86_REG_DS, 'es': x.UC_X86_REG_ES,
    'ss': x.UC_X86_REG_SS, 'sp': x.UC_X86_REG_SP,
    'ip': x.UC_X86_REG_IP, 'flags': x.UC_X86_REG_EFLAGS,
}
REG_FIELDS = dict(ax='value', bx='object_flags', cx='count', dx='auxiliary_value',
                  si='graphics_cursor', di='definition_cursor', bp='frame_stride',
                  cs='code_segment', ds='data_segment', es='extra_segment',
                  ss='stack_segment', sp='stack_offset', flags='flags')
MEM = ct.POINTER(ct.c_uint8)

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
GATE_INS = {i.address: i for i in MD.disasm(IMAGE[GATE_ENTRY:GATE_END], GATE_ENTRY)}
TAIL_INS = {i.address: i for i in MD.disasm(IMAGE[TAIL_ENTRY:TAIL_END], TAIL_ENTRY)}
OWN_INS = GATE_INS | TAIL_INS
OWN_SITES = set(OWN_INS)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in RESULT_NAMES]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(RuntimeError):
    """The original escaped its bounded code/provider contract."""


class GuardExhaustion(OracleFailure):
    """A finite execution/access bound was reached, never a mutant hit."""


class Mismatch(AssertionError):
    """A completed C/reference comparison differs."""


def oracle_require(ok, message):
    if not ok:
        raise OracleFailure(message)


def require(ok, message):
    if not ok:
        raise Mismatch(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


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


OWN_EDGES = static_edges()
oracle_require(len(OWN_INS) == 39 and sum(i.size for i in OWN_INS.values()) == 104,
              'object-animation static identity changed')
oracle_require(len(GATE_INS) == 4 and len(TAIL_INS) == 35,
              'object-animation split site inventory changed')


def code_bytes(load):
    image = relocated(IMAGE, META['relocations'], load)
    base = (load << 4) & MASK
    return base, image


def make_case(name, *, entry='tail', records=(), gate=0x00,
              type_gate=0x00, flags=0x0ED7, ds=None, ss=0x6000,
              sp=0xD000, outer_return=0xA55A, bx=0xA55A, provider=None,
              vga=False, seed=0):
    return dict(name=name, entry=entry, records=tuple(records), gate=gate,
                type_gate=type_gate, flags=flags, ds=ds, ss=ss, sp=sp,
                outer_return=outer_return, bx=bx, provider=provider,
                vga=vga, seed=seed)


def cases():
    """Small targeted set plus complete slot/frame-byte matrices."""
    rows = [
        make_case('gate-disabled-stale-state', entry='gate', gate=0xFF,
                  flags=0x02D7, seed=1),
        make_case('gate-enabled-one-active', entry='gate', gate=0xFE,
                  records=((0, dict(x=0x1234, type=0x0002, flags=2,
                                   frame=4, limit=10, stride=7, base=0x100)),),
                  seed=2),
        make_case('all-zero-stale-bx', records=(), flags=0x06D7, seed=3),
        make_case('one-shot-equal-limit', records=((0, dict(x=0x1234, type=2,
                  flags=3, frame=5, limit=6, stride=7, base=0x100)),), seed=4),
        make_case('over-limit-is-not-greater-or-equal', records=((0, dict(x=1,
                  type=2, flags=2, frame=8, limit=6, stride=9, base=0xFFFE)),), seed=5),
        make_case('frame-wrap-limit-zero', records=((0, dict(x=1, type=2,
                  flags=3, frame=0xFF, limit=0, stride=0xFFFF, base=0xFFFF)),), seed=6),
        make_case('frame-wrap-limit-one', records=((0, dict(x=1, type=2,
                  flags=2, frame=0xFF, limit=1, stride=0xFFFF, base=0xFFFF)),), seed=7),
        make_case('frame-equal-limit-ff', records=((0, dict(x=1, type=2,
                  flags=3, frame=0xFE, limit=0xFF, stride=0x1234, base=0x4567)),), seed=20),
        make_case('mul-high-dx', records=((0, dict(x=1, type=2,
                  flags=2, frame=3, limit=0x20, stride=0xFFFF, base=0x2345)),), seed=21),
        make_case('type-low-byte-one-skips', records=((0, dict(x=1,
                  type=0x0101, flags=2, frame=5, limit=8, stride=3, base=4)),),
                  gate=0xFF, type_gate=0x00, seed=8),
        make_case('type-low-byte-one-enabled', records=((0, dict(x=1,
                  type=0x0101, flags=2, frame=5, limit=8, stride=3, base=4)),),
                  type_gate=0xFF, seed=9),
        make_case('type-high-byte-ignored', records=((0, dict(x=1,
                  type=0x0202, flags=2, frame=5, limit=8, stride=3, base=4)),),
                  type_gate=0x00, seed=10),
        make_case('type-one-gate-live-provider', records=((0, dict(x=1,
                  type=1, flags=2, frame=5, limit=8, stride=3, base=4)),),
                  type_gate=0, provider='enable-type-one-gate', seed=11),
        make_case('future-definition-live-provider', records=(
                  (0, dict(x=1, type=2, flags=0, frame=0, limit=0, stride=0, base=0)),),
                  provider='activate-next-definition', seed=12),
        make_case('frame-write-live-base-provider', records=((0, dict(x=1,
                  type=2, flags=2, frame=2, limit=20, stride=5, base=1)),),
                  provider='change-frame-base', seed=13),
        make_case('ds-ss-frame-ret-alias', records=((0, dict(x=1,
                  type=2, flags=2, frame=0, limit=5, stride=3, base=0)),),
                  ds=0x5000, ss=0x5000, sp=GRAPHICS + 2,
                  outer_return=0x0405, seed=14),
        make_case('ds-ss-offset-ret-alias', records=((0, dict(x=1,
                  type=2, flags=2, frame=4, limit=10, stride=0x1200, base=0xFF00)),),
                  ds=0x5000, ss=0x5000, sp=GRAPHICS + 0x17,
                  outer_return=0xBEEF, seed=15),
        make_case('ds-ss-stale-bx-ret-alias', records=(), bx=0x1234,
                  ds=0x5000, ss=0x5000, sp=GRAPHICS,
                  outer_return=0x5678, seed=18),
        make_case('physical-ret-word-wrap', records=((0, dict(x=1, type=2,
                  flags=2, frame=2, limit=9, stride=4, base=0x100)),),
                  ss=0xFFFF, sp=0x000F, outer_return=0x1357, seed=19),
        make_case('vga-backed-state', records=((0, dict(x=1, type=2,
                  flags=3, frame=5, limit=6, stride=0x12, base=0x120)),),
                  ds=0xA000, ss=0xA000, sp=0xD000, vga=True,
                  flags=0x02D7, seed=16),
        make_case('flags-df-if', records=((31, dict(x=0xFFFF, type=2,
                  flags=2, frame=0xFF, limit=0xFF, stride=0xFFFF, base=1)),),
                  flags=0x06D7, seed=17),
    ]

    # Each slot is independently the only nonzero definition; zero-X siblings
    # retain and repeatedly write the original live BX value.
    for index in range(32):
        rows.append(make_case(f'single-active-slot-{index:02d}', records=((index,
            dict(x=(0x1101 + index * 37) & 0xFFFF, type=2,
                 flags=2, frame=(index * 7) & 0xFF, limit=(index * 7 + 1) & 0xFF,
                 stride=(0xFF01 + index * 13) & 0xFFFF,
                 base=(0xA000 + index * 0x1021) & 0xFFFF)),),
            flags=(0x0ED7 if index & 1 else 0x02D7), seed=100 + index))

    # Across eight dense 32-record passes every possible current frame byte is
    # visited. Each frame's limit differs from its wrapped increment.
    for group in range(8):
        batch = []
        for slot in range(32):
            frame = group * 32 + slot
            batch.append((slot, dict(x=0x0100 + slot, type=2, flags=2,
                frame=frame, limit=(frame + 2) & 0xFF,
                stride=(0xF123 + frame * 31) & 0xFFFF,
                base=(0xE000 + frame * 257) & 0xFFFF)))
        rows.append(make_case(f'all-frame-bytes-{group}', records=tuple(batch),
                              flags=(0x0ED7 if group & 1 else 0x02D7),
                              seed=200 + group))
    rows.append(dict(make_case('row54-spill-overlapped-definitions', entry='gate',
                               gate=0x00, type_gate=0xFF, flags=0x0246,
                               ss=(LOAD + 0x143E) & 0xFFFF, sp=0x4AF2,
                               outer_return=0x01B9, seed=0x7C54),
                     spill=SPILL_ORIGIN))
    rows.append(dict(make_case('row54-spill-after-record-57', entry='gate',
                               gate=0x00, type_gate=0xFF, flags=0x0246,
                               ss=(LOAD + 0x143E) & 0xFFFF, sp=0x4AF2,
                               outer_return=0x01B9, seed=0x7C57),
                     spill=SPILL_ORIGIN, spill_count=0x58))
    return rows


# Row-54 spill (creation contract at 30A6): records 57..5D overlay object
# definitions 0FEB..10EA. State = entity_update.spill_after_update(0280): the
# level-start records 00..62 after one original 1F19 pass with the unscrolled
# view; the frame then reaches 01B6 -> 3944 -> 7C0A. Working records G_j for
# the nine level006 s6 objects are the 378A copies of their GROUND (ground2o)
# templates, made at level start from the unspilled definitions; G_9..G_31
# keep their startup image bytes (no earlier level in this constructed
# session). Definition 0 (entrance) has X=0 after record 57, so the stale BX
# is stored into G_0; definitions 9..31 become nonzero record bytes. The
# second case is the reachable four-frame window after record 57 and before
# record 58 (records 00..57): definitions 0/1 zero, 2 partly record bytes.
SPILL_ORIGIN = 0x0280
SPILL_COPY_RANGES = ((0x0000, 0x0004), (0x002B, 0x002C), (0x0043, 0x004A),
                     (0x0055, 0x0056), (0x0088, 0x11EF))


def install_spill(case, memory, ds):
    import entity_update
    import entity_create as spill
    post, post_ds = entity_update.spill_after_update(
        case['spill'], case.get('spill_count', spill.SPILL_LIMIT))
    oracle_require(post_ds == ds, case['name'] + ': spill DS differs')
    for start, end in SPILL_COPY_RANGES:
        for offset in range(start, end):
            put8(memory, ds, offset, get8(post, post_ds, offset))
    level = spill.spill_level_record()
    ground = (ROOT / f'assets/ground{level[0x1B]}o.dat').read_bytes()
    ground_buffer = 0x1B4B
    for index, value in enumerate(ground):
        put8(memory, ds, ground_buffer + index, value)
    image_ds = 0x09A9 << 4
    active = []
    for index in range(32):
        definition = level[0x20 + 8 * index:0x28 + 8 * index]
        record = GRAPHICS + index * 0x1C
        if definition[0] or definition[1]:
            kind = (definition[4] << 8) | definition[5]
            template = ground[kind * 0x1C:(kind + 1) * 0x1C]
            oracle_require(len(template) == 0x1C,
                           case['name'] + f': GROUND template {kind} is short')
            active.append(index)
        else:
            template = IMAGE[image_ds + record:image_ds + record + 0x1C]
        for offset, value in enumerate(template):
            put8(memory, ds, record + offset, value)
    oracle_require(active == list(range(9)),
                   case['name'] + f': level006 s6 active objects {active}')


def verify_spill_contract(case, initial, result):
    """Characterized row-54 animation facts over the overlapped definitions."""
    ds = result['regs']['ds']
    xs = [(get8(initial, ds, DEFINITIONS + 8 * j) << 8) |
          get8(initial, ds, DEFINITIONS + 8 * j + 1) for j in range(32)]
    oracle_require(xs[0] == 0 and get16(result['memory'], ds, GRAPHICS) == case['bx'],
                   case['name'] + ': entrance definition did not store the stale BX into G_0')
    if case.get('spill_count', 0x63) == 0x63:
        oracle_require(any(xs[9:]),
                       case['name'] + ': no definition 9..31 became nonzero')
    else:
        oracle_require(xs[1] == 0 and not any(xs[9:]) and all(xs[3:9]),
                       case['name'] + ': record-57 window definitions differ')


def setup(case):
    rng = random.Random(0x7C0A + case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    data_segment = case['ds'] if case['ds'] is not None else (LOAD + 0x09A9) & 0xFFFF
    code_base, loaded = code_bytes(LOAD)
    first = min(len(loaded), SIZE - code_base)
    memory[code_base:code_base + first] = loaded[:first]
    memory[:len(loaded) - first] = loaded[first:]

    regs = {name: ((0x5217 * (index + 3) + 0x39A1) & 0xFFFF)
            for index, name in enumerate(REG_NAMES)}
    entry = GATE_ENTRY if case['entry'] == 'gate' else TAIL_ENTRY
    regs.update(ax=0xBEEF, bx=case['bx'], cx=0xBEEF, dx=0x7139,
                si=0x1234, di=0x5678, bp=0x9ABC, cs=LOAD, ds=data_segment,
                es=0x6C20, ss=case['ss'], sp=case['sp'], ip=entry,
                flags=(case['flags'] | 2) & 0x0FD7)

    # Deterministic poison makes untouched bytes part of the complete RAM check.
    put8(memory, data_segment, UPDATE_GATE, case['gate'])
    put8(memory, data_segment, TYPE_ONE_GATE, case['type_gate'])
    put16(memory, data_segment, DEFINITIONS, 0)  # overwritten below as records
    for index in range(32):
        base = DEFINITIONS + index * 8
        for off in range(8):
            put8(memory, data_segment, base + off, 0)
        gfx = GRAPHICS + index * 0x1C
        for off in range(0x1C):
            put8(memory, data_segment, gfx + off,
                 (index * 41 + off * 73 + 0x5B) & 0xFF)
        put16(memory, data_segment, gfx, 0xA5C3 ^ (index * 0x0101))
        put8(memory, data_segment, gfx + 2, (index * 11 + 3) & 0xFF)
        put8(memory, data_segment, gfx + 3, (index * 13 + 7) & 0xFF)
        put16(memory, data_segment, gfx + 6, (0x3107 + index * 0x321) & 0xFFFF)
        put16(memory, data_segment, gfx + 0x15, (0x7721 + index * 0x431) & 0xFFFF)
        put16(memory, data_segment, gfx + 0x17, 0xD00D ^ index)

    for index, spec in case['records']:
        definition = DEFINITIONS + index * 8
        xword = spec.get('x', 1) & 0xFFFF
        put8(memory, data_segment, definition, xword >> 8)
        put8(memory, data_segment, definition + 1, xword)
        typeword = spec.get('type', 2) & 0xFFFF
        put8(memory, data_segment, definition + 4, typeword >> 8)
        put8(memory, data_segment, definition + 5, typeword)
        gfx = GRAPHICS + index * 0x1C
        put16(memory, data_segment, gfx, spec.get('flags', 2))
        put8(memory, data_segment, gfx + 2, spec.get('frame', 0))
        put8(memory, data_segment, gfx + 3, spec.get('limit', 0))
        put16(memory, data_segment, gfx + 6, spec.get('stride', 1))
        put16(memory, data_segment, gfx + 0x15, spec.get('base', 0))

    if case.get('spill'):
        install_spill(case, memory, data_segment)
    put16(memory, regs['ss'], regs['sp'], case['outer_return'])
    device = None
    if case['vga']:
        device = MinimapVga(0x7C0A ^ case['seed'], read_map=0)
        aperture = memory[VGA_BASE:VGA_END]
        device.planes = [bytearray(aperture) for _ in range(4)]
        device.seq[2] = 0x05
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[4] = 0
        device.gc[5] = 0
        device.gc[8] = 0xFF
    return memory, regs, device


def verify_independent_projection(case, initial, actual):
    """Sequential byte/word projection for ordinary nonalias RAM fixtures."""
    if case['vga'] or case['provider'] or case['ds'] == case['ss']:
        return
    expected = bytearray(initial)
    ds = case['ds'] if case['ds'] is not None else (LOAD + 0x09A9) & 0xFFFF
    bx = case['bx']
    if case['entry'] == 'gate' and case['gate'] == 0xFF:
        oracle_require(bytes(expected) == actual['memory'],
                       case['name'] + ': early gate changed memory')
        return
    gate_value = case['type_gate']
    for index in range(32):
        definition = DEFINITIONS + index * 8
        graphics = GRAPHICS + index * 0x1C
        xword = (get8(expected, ds, definition) << 8) | get8(expected, ds, definition + 1)
        if xword == 0:
            put16(expected, ds, graphics, bx)
            continue
        low_type = get8(expected, ds, definition + 5)
        if low_type == 1 and gate_value != 0xFF:
            continue
        bx = get16(expected, ds, graphics)
        if bx & 2:
            frame = get8(expected, ds, graphics + 2)
            limit = get8(expected, ds, graphics + 3)
            frame = (frame + 1) & 0xFF
            if frame == limit:
                frame = 0
                if bx & 1:
                    bx &= 0xFFFD
            put8(expected, ds, graphics + 2, frame)
            stride = get16(expected, ds, graphics + 6)
            base = get16(expected, ds, graphics + 0x15)
            frame_offset = ((frame * stride) + base) & 0xFFFF
            put16(expected, ds, graphics + 0x17, frame_offset)
        put16(expected, ds, graphics, bx)
    oracle_require(bytes(expected) == actual['memory'],
                   case['name'] + ': independent sequential record projection differs')


def verify_case_contract(case, result, *, core):
    """Check entry/return seams and the hand-picked live-memory aliases."""
    expected_core_ip = EARLY_RET if case['entry'] == 'gate' and case['gate'] == 0xFF else TAIL_RET
    if core:
        oracle_require(result['continuation'] == expected_core_ip,
                       case['name'] + ': core stopped at the wrong pre-RET boundary')
    if case['name'] == 'ds-ss-frame-ret-alias' and not core:
        oracle_require(result['regs']['ip'] == 0x0406,
                       'frame write did not update the live outer RET word')
    elif case['name'] == 'ds-ss-offset-ret-alias' and not core:
        oracle_require(result['regs']['ip'] == 0x5900,
                       'frame-offset write did not update the live outer RET word')
    elif case['name'] == 'ds-ss-stale-bx-ret-alias' and not core:
        oracle_require(result['regs']['ip'] == 0x1234,
                       'zero-X stale-BX store did not update the live outer RET word')
    elif case['name'] == 'physical-ret-word-wrap' and not core:
        oracle_require(result['regs']['ip'] == 0x1357 and
                       result['regs']['sp'] == 0x0011,
                       'adapter did not consume the physical 20-bit wrapped RET word')
    if case.get('provider'):
        expected_name = {
            'change-frame-base': 'base',
            'activate-next-definition': 'future',
            'enable-type-one-gate': 'typegate',
        }[case['provider']]
        oracle_require(expected_name in result['used'],
                       case['name'] + ': planned live provider did not fire')
    if case['name'] == 'frame-write-live-base-provider':
        oracle_require(get16(result['memory'], result['regs']['ds'], GRAPHICS + 0x17)
                       == 0xBEFE,
                       'frame-offset did not use the provider-updated live base word')
    if case['name'] == 'enable-type-one-gate-live-provider':
        oracle_require(get8(result['memory'], result['regs']['ds'], GRAPHICS + 2) == 6,
                       'type-one row did not observe the provider-updated gate byte')


class Access:
    event_limit = MAX_BUS_EVENTS

    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events, self.used, self.mirror = [], set(), None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror:
            self.mirror(address, value & 0xFF)

    def put16(self, segment, offset, value):
        address = physical(segment, offset)
        self.store(address, value)
        self.store(address + 1, value >> 8)

    def _provider(self, kind, address):
        name = self.case.get('provider')
        ds = self.regs['ds']
        if name == 'change-frame-base' and kind == 'write' and 'base' not in self.used:
            if address == physical(ds, GRAPHICS + 2):
                self.put16(ds, GRAPHICS + 0x15, 0xBEEF)
                self.used.add('base')
        elif name == 'activate-next-definition' and kind == 'read' and 'future' not in self.used:
            if address == physical(ds, DEFINITIONS):
                self.put16(ds, DEFINITIONS + 8, 1)
                self.used.add('future')
        elif name == 'enable-type-one-gate' and kind == 'read' and 'typegate' not in self.used:
            if address == physical(ds, DEFINITIONS):
                self.store(physical(ds, TYPE_ONE_GATE), 0xFF)
                self.used.add('typegate')

    def access(self, kind, address, flags, mask=DEFINED_FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise GuardExhaustion('object-animation bus callback budget exhausted')
        address &= MASK
        self._provider(kind, address)
        if kind == 'read':
            value = (self.device.read(self.memory, address, flags)
                     if self.device and VGA_BASE <= address < VGA_END
                     else self.memory[address])
            self.store(address, value)
        else:
            value &= 0xFF
            if self.device and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF, mask))
        return value & 0xFF


def run_original(case, memory, regs, device, core):
    """Run the shared, bounded original engine with this region's instruction map."""
    result = interactions.original(
        case, memory, regs, device, core, main_instructions=OWN_INS,
        access_factory=Access, instruction_limit=MAX_ORIGINAL_INSTRUCTIONS)
    return dict(memory=result['memory'], regs=result['regs'], device=result['device'],
                events=result['events'], used=result['used'], status=result['status'],
                continuation=result['continuation'],
                sites={address for scope, address in result['sites'] if scope == 'main'},
                edges={(source, target) for scope, source, target in result['edges']
                       if scope == 'main'},
                steps=result['steps'], flags_mask=result['flag_mask'],
                boundary=result['boundary'])


def input_hashes():
    paths = [
        'src/game_code_late.asm', 'src/object_graphics_tick.asm', 'src/program.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'requirements.txt', 'c/object_animation.c', 'c/object_animation.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/object_animation.py', 'tests/entity_interactions.py',
        'tests/entity_create.py', 'tests/entity_update.py', 'assets/level006.dat',
        'assets/oddtable.dat', 'assets/ground2o.dat',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/minimap_vga.py',
        'tests/dat_io_c.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/coverage.py', 'tools/resources.py',
        'tools/unpack.py', 'tools/difftest.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(set(paths))}


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'object-animation-m{mutation}.dll',
                     mutation, 'object_animation')
        self.lib = ct.CDLL(str(path))
        self.functions = {}
        for entry, prefix in (('gate', 'lmn_advance_level_object_animations'),
                              ('tail', 'lmn_advance_level_object_animation_records')):
            core = getattr(self.lib, prefix + '_core')
            core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
            core.restype = Result
            adapter = getattr(self.lib, prefix + '_adapter')
            adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
            adapter.restype = ct.c_uint16
            self.functions[entry] = (core, adapter)

    def run(self, case, initial, initial_regs, initial_device, *, core, null_bus=False):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        access = Access(case, memory, dict(initial_regs), device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            'native read callback failed: ' + str(error))
                return 0

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, value=value)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            'native write callback failed: ' + str(error))

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_EXIT,
                        f'unexpected object-animation OUT {port:04X}={value:04X}')

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = RasterBus(None, *callbacks)
        bus_pointer = None if null_bus else ct.byref(bus)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = Regs(**initial_regs)
        native_core, adapter = self.functions[case['entry']]
        if core:
            call = Call(*(initial_regs[name] for name in REG_FIELDS))
            result = native_core(ram, ct.byref(call), bus_pointer)
            for machine_name, field_name in REG_FIELDS.items():
                setattr(regs, machine_name, getattr(result, field_name))
            regs.ip = result.continuation
            status = result.status
        else:
            status = adapter(ram, ct.byref(regs), bus_pointer)
        return dict(memory=bytes(memory),
                    regs={name: getattr(regs, name) for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status, continuation=regs.ip)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered access count {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        require(got[:3] == ref[:3],
                f'{label}: ordered access {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: access {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
                f'under {ref[4]:04X}')


def compare_case(native, case, *, core, null_bus=False):
    memory, regs, device = setup(case)
    label = case['name'] + (' core' if core else ' adapter') + \
        (' null-bus' if null_bus else ' bus')
    expected = run_original(case, bytearray(memory), dict(regs),
                            copy.deepcopy(device), core)
    verify_case_contract(case, expected, core=core)
    verify_independent_projection(case, memory, expected)
    if case.get('spill'):
        verify_spill_contract(case, memory, expected)
    actual = native.run(case, memory, regs, device, core=core, null_bus=null_bus)
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: IP {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    for name in REG_NAMES:
        if name == 'flags':
            continue
        require(actual['regs'][name] == expected['regs'][name],
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X}')
    require(((actual['regs']['flags'] ^ expected['regs']['flags']) &
             expected['flags_mask']) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{expected["regs"]["flags"]:04X} under {expected["flags_mask"]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    if null_bus:
        require(not actual['events'] and not actual['used'],
                label + ': null bus unexpectedly called a callback')
    else:
        compare_events(label, actual['events'], expected['events'])
        require(actual['used'] == expected['used'],
                f'{label}: live provider effects {actual["used"]}/{expected["used"]}')
    if expected['device'] is None:
        require(actual['device'] is None, label + ': unexpected VGA device')
    else:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA planes/latches/registers differ')
        actual_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        expected_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(actual_trace == expected_trace, label + ': VGA trace differs')
    return dict(name=case['name'], core=core, null_bus=null_bus,
                sites=sorted(expected['sites']),
                edges=[list(edge) for edge in sorted(expected['edges'])],
                event_count=len(expected['events']), steps=expected['steps'],
                providers=sorted(expected['used']))


MUTATION_WITNESSES = {
    1: ('gate-disabled-stale-state', True),
    2: ('all-zero-stale-bx', False),
    3: ('type-low-byte-one-skips', False),
    4: ('over-limit-is-not-greater-or-equal', False),
    5: ('frame-wrap-limit-zero', False),
    6: ('one-shot-equal-limit', False),
    7: ('mul-high-dx', False),
    8: ('frame-write-live-base-provider', False),
}


def original_only():
    before = input_hashes()
    all_sites, all_edges = set(), set()
    rows = cases()
    for case in rows:
        memory, regs, device = setup(case)
        for core in (True, False):
            expected = run_original(case, bytearray(memory), dict(regs),
                                    copy.deepcopy(device), core)
            verify_case_contract(case, expected, core=core)
            verify_independent_projection(case, memory, expected)
            if case.get('spill'):
                verify_spill_contract(case, memory, expected)
            all_sites.update(expected['sites'])
            all_edges.update(expected['edges'])
    oracle_require(all_sites == OWN_SITES,
                   f'original object-animation sites {len(all_sites)}/{len(OWN_SITES)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'original object-animation edges {len(all_edges)}/{len(OWN_EDGES)}')
    oracle_require(before == input_hashes(),
                   'object-animation inputs changed during original preflight')
    print(f'PASS original object animation: {len(rows)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges', flush=True)


def worker(directory):
    before = input_hashes()
    specs = cases()
    by_name = {case['name']: case for case in specs}
    baseline = Native(directory, 0)
    rows, all_sites, all_edges = [], set(), set()
    total_events = total_steps = 0
    null_bus_names = {'gate-disabled-stale-state', 'all-zero-stale-bx',
                      'one-shot-equal-limit', 'all-frame-bytes-0',
                      'ds-ss-stale-bx-ret-alias', 'physical-ret-word-wrap'}
    for case in specs:
        null_modes = (False, True) if case['name'] in null_bus_names else (False,)
        for core in (True, False):
            for null_bus in null_modes:
                row = compare_case(baseline, case, core=core, null_bus=null_bus)
                rows.append(row)
                all_sites.update(row['sites'])
                all_edges.update(tuple(edge) for edge in row['edges'])
                total_events += row['event_count']
                total_steps += row['steps']
    oracle_require(all_sites == OWN_SITES,
                   f'native object-animation sites {len(all_sites)}/{len(OWN_SITES)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'native object-animation edges {len(all_edges)}/{len(OWN_EDGES)}')
    del baseline
    gc.collect()

    mutations = []
    for mutation, (name, core) in MUTATION_WITNESSES.items():
        mutant = Native(directory, mutation)
        try:
            compare_case(mutant, by_name[name], core=core)
        except Mismatch as error:
            mutations.append(dict(id=mutation, witness=name, core=core,
                                  mismatch=str(error), completed=True))
        else:
            raise AssertionError(f'object-animation mutant {mutation} survived on {name}')
        del mutant
        gc.collect()
    oracle_require(len(mutations) == len(MUTATION_WITNESSES),
                   'object-animation mutation witness count changed')
    oracle_require(before == input_hashes(),
                   'object-animation inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[GATE_ENTRY, GATE_END], [TAIL_ENTRY, TAIL_END]],
        translated_code_bytes=sum(ins.size for ins in OWN_INS.values()),
        instruction_sites=len(OWN_INS), own_static_branch_edges=len(OWN_EDGES),
        executed_instruction_addresses=sorted(all_sites),
        branch_edges=[list(edge) for edge in sorted(all_edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        cases=rows, input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_ORIGINAL_INSTRUCTIONS,
                    ordered_bus_event_limit=MAX_BUS_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        flag_notes='All live register values and FLAGS are compared; FLAGS and bus-event '
                   'FLAGS use instruction-defined masks from the shared original engine. '
                   'MUL only defines CF/OF. Incoming DF/IF remain live.',
        domain='The 3944 gate and direct 7C0A 32-record animation tail. Cases compare '
               'the full 1 MiB RAM, all 13 register roles plus IP, defined FLAGS, ordered '
               'byte bus events and VGA device state. Core stops before 394E/7C66; '
               'adapters consume the live outer RET. Coverage includes each record slot, '
               'all 256 frame bytes, wrap/equality/greater-than limits, stale BX, low-byte '
               'type gating, live providers, stack/record aliases, physical 20-bit RET '
               'wrap, DF/IF, VGA aperture, and selected null-bus calls. Row-54 spill: '
               'definitions overlaid by records 57..5D after one original update '
               'pass, GROUND-copied working records for the nine real objects.'))
    print(f'PASS object animation: {len(specs)} fixtures, {len(all_sites)} sites/'
          f'{len(all_edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--original-worker'], cwd=ROOT,
                             timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return
    if sys.argv[1:] == ['--original-worker']:
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('usage: object_animation.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='object-animation-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
