"""Bounded differential checks for DrawEntityWideSprite32 (6BDB..6CFB).

The suite compares the pinned original instruction stream and portable C at
both the pre-RET core boundary and the actual-RET adapter boundary. Its small
instruction-ordered model independently replays the three 32-row plane passes
and checks every planar VGA write.
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
import entity_sprite_layout as sprite_layout
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, RET, END, LOAD = 0x6BDB, 0x6CFB, 0x6CFC, 0x1010
DF, IF, CF, AF = 0x0400, 0x0200, 0x0001, 0x0010
ARITH = 0x08D5
LOGIC = FLAGS & ~AF
MAX_INSTRUCTIONS, MAX_EVENTS = 20_000, 12_000
WORKER_SECONDS, PROCESS_MIB = 300, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-sprite-wide-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-sprite-wide-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())
REG_NAMES = interactions.REG_NAMES
MEM = ct.POINTER(ct.c_uint8)
CORE_NAMES = ('value', 'map_cursor', 'count', 'auxiliary_value',
              'record_cursor', 'object_cursor', 'candidate_y',
              'code_segment', 'data_segment', 'extra_segment',
              'stack_segment', 'stack_offset', 'flags')
REG_FIELDS = dict(value='ax', map_cursor='bx', count='cx',
                  auxiliary_value='dx', record_cursor='si', object_cursor='di',
                  candidate_y='bp', code_segment='cs', data_segment='ds',
                  extra_segment='es', stack_segment='ss', stack_offset='sp',
                  flags='flags')

READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES +
                ('continuation', 'status')]


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """Original/model disagreement, escape or exhausted execution bound."""


class Mismatch(AssertionError):
    """Only a completed native comparison can count as mutation evidence."""


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


def put_physical(memory, device, address, value, *, plane=0):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[plane & 3][address - VGA_BASE] = value


def put_byte(memory, device, segment, offset, value, *, plane=0):
    put_physical(memory, device, physical(segment, offset), value, plane=plane)


def put_word(memory, device, segment, offset, value, *, plane=0):
    address = physical(segment, offset)
    put_physical(memory, device, address, value, plane=plane)
    put_physical(memory, device, address + 1, value >> 8, plane=plane)


def get_byte(memory, segment, offset):
    return memory[physical(segment, offset)]


def source_pattern(seed):
    rng = random.Random(seed)
    return bytes(((index * 73 + (index >> 2) * 19 + rng.randrange(256)) & 0xFF)
                 for index in range(480))


def mask_pattern(seed):
    rng = random.Random(seed ^ 0x6BDB)
    special = (0x00, 0xFF, 0x0F, 0xF0, 0x55, 0xAA, 0x81, 0x18)
    return bytes((special[index % len(special)] ^ rng.randrange(256)) & 0xFF
                 for index in range(160))


def output_offsets(start, df):
    direction = -1 if df else 1
    stride = (0x27 + 5 * direction) & 0xFFFF
    return [((start + row * stride + col * direction) & 0xFFFF)
            for row in range(32) for col in range(5)]


def make_cases(producer):
    """Eight normal 5C06 banks plus focused state, alias, DF and VGA cases."""
    specs = [
        ('ordinary-wide-raster', {}),
        ('df-set-forward-mask-reverse-strings', dict(flags=0x0ED7,
                                                      si=0x3600, di=0x2608)),
        ('incoming-cx-source-not-entry-ds', dict(ds=0x3500, cx=0x6100,
                                                  bx=0x1900, si=0x2B00)),
        ('source-word-physical-top-wrap', dict(cx=0xFFFF, bx=0x0180,
                                                si=0x000F)),
        ('source-logical-offset-wrap-df', dict(flags=0x0ED7, si=0x0007,
                                                di=0x0010)),
        ('mask-cursor-logical-offset-wrap', dict(bx=0xFFB0)),
        ('destination-logical-offset-wrap', dict(di=0xFFE8)),
        ('return-word-physical-top-wrap', dict(ss=0xFFFF, sp=0x000F,
                                                 return_word=0xB35A)),
        ('return-word-logical-offset-wrap', dict(ss=0x5000, sp=0xFFFF,
                                                   return_word=0xC35A)),
        ('mask-word-physical-top-wrap', dict(cx=0xFFFF, bx=0x000F,
                                               si=0x0300)),
        ('initial-out-precedes-live-ds-mirror', dict(sp=0x0008,
                                                       return_word=0xB75C)),
        ('ss-vga-mirrors-and-stack', dict(ss=0xA000, sp=0x6000,
                                            di=0x2700, mask_fill=0xFF,
                                            vga_read_map=0)),
        ('vga-source-overlaps-first-plane-output',
         dict(cx=0xA000, ds=0x3500, bx=0x2100, si=0x2800,
              di=0x2800, source_vga=True, vga_read_map=0)),
        ('vga-read-map-two', dict(vga_read_map=2, di=0x2A10)),
        ('entry-if-set-is-cleared-and-restored', dict(flags=0x0AD7)),
        ('device-registers-start-poisoned', dict(gc_seed=0xA6, seq_seed=0x5B)),
        ('live-first-pass-pop-count-one', dict(provider='short-first-pass')),
        ('provider-changes-forward-mask-after-first-mask',
         dict(provider='next-mask-bytes')),
        ('provider-changes-second-plane-source',
         dict(provider='second-plane-source')),
        ('saved-ds-mirror-and-actual-ret-alias',
         dict(sp=0x000A, ds=0x4321, return_word=0xC35A)),
    ]
    for index, bank in enumerate(producer.banks):
        source_offset = producer.destination_offset + bank.plane_offset
        mask_offset = producer.destination_offset + bank.mask_offset
        specs.append((f'actual-5c06-shift-bank-{index}',
                      dict(cx=producer.destination_segment,
                           si=source_offset, bx=mask_offset,
                           producer_bank=index)))

    cases = []
    for index, (name, fields) in enumerate(specs):
        row = dict(name=name, seed=0x6BDB + index * 97,
                   ds=0x3500, cx=0x6100, ss=0x5000, sp=0x9000,
                   bx=0x1800, si=0x2000, di=0x2400,
                   ax=0xA55A, dx=0xD39B, bp=0xBEEF, es=0x4512,
                   flags=0x0AD7, return_word=0xE000 | index,
                   source_vga=False, vga_read_map=0, gc_seed=0, seq_seed=0,
                   provider=None, producer_bank=None, mask_fill=None)
        row.update(fields)
        cases.append(row)
    oracle_require(24 <= len(cases) <= 40,
                   f'wide-sprite fixture count outside scope: {len(cases)}')
    return cases


def setup(case, producer=None):
    rng = random.Random(0x6BDB + case['seed'] * 0x9E3779B1)
    if case['producer_bank'] is not None:
        oracle_require(producer is not None,
                       case['name'] + ': producer witness missing')
        memory = bytearray(producer.memory)
    else:
        memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = physical(LOAD, 0)
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = MinimapVga(0x6BDB ^ case['seed'], read_map=case['vga_read_map'])
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0x0E
    device.gc[2] = 0
    device.gc[3] = 0
    device.gc[4] = case['vga_read_map']
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[7] = 0
    device.gc[8] = 0xFF
    if case['gc_seed']:
        device.gc[2] = case['gc_seed'] & 0x0F
    if case['seq_seed']:
        device.seq[3] = case['seq_seed'] & 0x0F

    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    flags = ((case['flags'] | 2) & FLAGS) & ~0x0100
    regs.update(cs=LOAD, ip=ENTRY, ax=case['ax'], bx=case['bx'],
                cx=case['cx'], dx=case['dx'], si=case['si'], di=case['di'],
                bp=case['bp'], ds=case['ds'], es=case['es'], ss=case['ss'],
                sp=case['sp'], flags=flags)

    # Give every output location four distinct initial planar bytes so the
    # independent VGA write model can verify each selected-plane result.
    for ordinal, offset in enumerate(output_offsets(regs['di'], bool(flags & DF))):
        vga_offset = physical(0xA000, offset) - VGA_BASE
        for plane_number, plane in enumerate(device.planes):
            plane[vga_offset] = (0x37 + ordinal * 11 + plane_number * 53) & 0xFF
        memory[VGA_BASE + vga_offset] = device.planes[device.gc[4] & 3][vga_offset]

    def seed_sources(segment, start, *, vga=False):
        """Seed actual LODSW/LODSB operands, including DF's odd word pattern."""
        direction = -1 if flags & DF else 1
        cursor = start
        ordinal = 0
        for _phase in range(3):
            for _row in range(32):
                for width in (2, 2, 1):
                    address = physical(segment, cursor)
                    for byte_index in range(width):
                        value = (0x19 + ordinal * 67 + (ordinal >> 3) * 23 +
                                 case['seed']) & 0xFF
                        put_physical(memory, device, address + byte_index, value,
                                     plane=device.gc[4])
                        ordinal += 1
                    cursor = (cursor + direction * width) & 0xFFFF

    if case['producer_bank'] is None:
        if case['source_vga']:
            seed_sources(regs['cx'], regs['si'], vga=True)
            masks = (bytes((case['mask_fill'],)) * 160 if case['mask_fill'] is not None
                     else mask_pattern(case['seed']))
            for index, value in enumerate(masks):
                put_byte(memory, device, regs['cx'], regs['bx'] + index, value,
                         plane=device.gc[4])
        else:
            seed_sources(regs['cx'], regs['si'])
            masks = (bytes((case['mask_fill'],)) * 160 if case['mask_fill'] is not None
                     else mask_pattern(case['seed']))
            for index, value in enumerate(masks):
                put_byte(memory, device, regs['cx'], regs['bx'] + index, value)
    else:
        descriptor = producer.banks[case['producer_bank']]
        bank = producer.bank(case['producer_bank'])
        address = physical(producer.destination_segment,
                           producer.destination_offset + descriptor.output_offset)
        oracle_require(memory[address:address + len(bank)] == bank,
                       case['name'] + ': source setup changed the producer bank')

    put_word(memory, device, regs['ss'], regs['sp'], case['return_word'])
    return memory, regs, device


class WideAccess(interactions.Access):
    """Bounded VGA/byte bus with three deterministic live providers."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def _apply_out_provider(self):
        effect = self.case['provider']
        if effect == 'short-first-pass' and self.out_count == 6 and effect not in self.used:
            address = physical(self.case['ss'], self.case['sp'] - 4)
            self.store(address, 1)
            self.store(address + 1, 0)
            self.used.add(effect)
        elif effect == 'next-mask-bytes' and self.out_count == 6 and effect not in self.used:
            segment = self.case['cx']
            offset = (self.case['bx'] + 2) & 0xFFFF
            for index, value in enumerate((0xE3, 0x1C, 0xA7, 0x5D, 0x82)):
                self.store(physical(segment, (offset + index) & 0xFFFF), value)
            self.used.add(effect)
        elif effect == 'second-plane-source' and self.out_count == 165 and effect not in self.used:
            segment = self.case['cx']
            direction = -1 if self.case['flags'] & DF else 1
            offset = (self.case['si'] + 160 * direction) & 0xFFFF
            address = physical(segment, offset)
            for index, value in enumerate((0xE7, 0x31, 0x8C, 0x42, 0xF0)):
                self.store((address + index) & MASK, value)
            self.used.add(effect)

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('wide-sprite bus event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        self._apply_out_provider()


def add16_flags(flags, left, right):
    left &= 0xFFFF
    right &= 0xFFFF
    wide = left + right
    result = wide & 0xFFFF
    out = 0
    if (result & 0xFF).bit_count() % 2 == 0:
        out |= 0x0004
    if result == 0:
        out |= 0x0040
    if result & 0x8000:
        out |= 0x0080
    if wide > 0xFFFF:
        out |= CF
    if (left ^ right ^ result) & AF:
        out |= AF
    if (~(left ^ right) & (left ^ result) & 0x8000):
        out |= 0x0800
    return ((flags & ~ARITH) | out) & 0xFFFF


def logic16_flags(flags, result):
    result &= 0xFFFF
    out = 0
    if (result & 0xFF).bit_count() % 2 == 0:
        out |= 0x0004
    if result == 0:
        out |= 0x0040
    if result & 0x8000:
        out |= 0x0080
    return ((flags & ~ARITH) | out) & 0xFFFF


def inc16_flags(flags, before):
    return (add16_flags(flags, before, 1) & ~CF) | (flags & CF)


def dec16_flags(flags, before):
    result = (before - 1) & 0xFFFF
    out = 0
    if (result & 0xFF).bit_count() % 2 == 0:
        out |= 0x0004
    if result == 0:
        out |= 0x0040
    if result & 0x8000:
        out |= 0x0080
    if (before ^ 1 ^ result) & AF:
        out |= AF
    if before == 0x8000:
        out |= 0x0800
    return ((flags & ~0x08D4) | out | (flags & CF)) & 0xFFFF


class ModelBus:
    """Byte-ordered RAM/VGA bus and independent per-plane OR projection."""
    def __init__(self, case, memory, device):
        self.case, self.memory, self.device = case, memory, device
        self.events, self.used, self.out_count = [], set(), 0
        self.plane_checks = 0

    def read(self, address, flags, mask):
        address &= MASK
        oracle_require(len(self.events) < MAX_EVENTS,
                       'independent wide-sprite event budget exhausted')
        if self.device is not None and VGA_BASE <= address < VGA_END:
            value = self.device.read(self.memory, address, flags)
        else:
            value = self.memory[address]
        self.memory[address] = value
        self.events.append(('read', address, value, flags & 0xFFFF, mask))
        return value

    def write(self, address, value, flags, mask, *, pixel=False):
        address &= MASK
        value &= 0xFF
        oracle_require(len(self.events) < MAX_EVENTS,
                       'independent wide-sprite event budget exhausted')
        before = None
        offset = None
        if pixel and self.device is not None and VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            before = [plane[offset] for plane in self.device.planes]
            oracle_require((self.device.gc[5] & 3) == 0,
                           'wide sprite requires VGA write mode zero')
        if self.device is not None and VGA_BASE <= address < VGA_END:
            self.device.write(self.memory, address, value, flags)
        else:
            self.memory[address] = value
        self.memory[address] = value
        self.events.append(('write', address, value, flags & 0xFFFF, mask))
        if before is not None:
            expected = self.expected_planes(before, value)
            got = [plane[offset] for plane in self.device.planes]
            oracle_require(got == expected,
                           f'independent plane byte {offset:04X}: {got!r}/{expected!r}')
            self.plane_checks += 4

    def expected_planes(self, before, value):
        gc, seq = self.device.gc, self.device.seq
        rotate = gc[3] & 7
        rotated = value if rotate == 0 else (
            (value >> rotate) | (value << (8 - rotate))) & 0xFF
        operation, bit_mask = (gc[3] >> 3) & 3, gc[8]
        expected = list(before)
        for plane in range(4):
            if not seq[2] & (1 << plane):
                continue
            source = ((0xFF if gc[0] & (1 << plane) else 0)
                      if gc[1] & (1 << plane) else rotated)
            latch = self.device.latches[plane]
            if operation == 1:
                source &= latch
            elif operation == 2:
                source |= latch
            elif operation == 3:
                source ^= latch
            expected[plane] = ((source & bit_mask) |
                               (latch & (~bit_mask & 0xFF))) & 0xFF
        return expected

    def provider(self):
        effect = self.case['provider']
        if effect == 'short-first-pass' and self.out_count == 6 and effect not in self.used:
            address = physical(self.case['ss'], self.case['sp'] - 4)
            self.memory[address] = 1
            self.memory[(address + 1) & MASK] = 0
            self.used.add(effect)
        elif effect == 'next-mask-bytes' and self.out_count == 6 and effect not in self.used:
            segment = self.case['cx']
            offset = (self.case['bx'] + 2) & 0xFFFF
            for index, value in enumerate((0xE3, 0x1C, 0xA7, 0x5D, 0x82)):
                self.memory[physical(segment, (offset + index) & 0xFFFF)] = value
            self.used.add(effect)
        elif effect == 'second-plane-source' and self.out_count == 165 and effect not in self.used:
            segment = self.case['cx']
            direction = -1 if self.case['flags'] & DF else 1
            address = physical(segment,
                               (self.case['si'] + 160 * direction) & 0xFFFF)
            for index, value in enumerate((0xE7, 0x31, 0x8C, 0x42, 0xF0)):
                self.memory[(address + index) & MASK] = value
            self.used.add(effect)

    def out(self, port, value, flags, mask):
        oracle_require(len(self.events) < MAX_EVENTS,
                       'independent wide-sprite event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        self.provider()


def independent(case, initial_memory, initial_regs, initial_device, *, core):
    """Replay the ordered mirrors, live loop stack, and three 32-row passes."""
    memory, device = bytearray(initial_memory), copy.deepcopy(initial_device)
    state = dict(initial_regs)
    bus = ModelBus(case, memory, device)
    flags, flag_mask = state['flags'], FLAGS
    source_reads, mask_reads = [], []
    phase_rows = []
    direction = -1 if flags & DF else 1

    def read8(segment, offset, role=None):
        address = physical(segment, offset)
        if role == 'source':
            source_reads.append(address)
        elif role == 'mask':
            mask_reads.append(address)
        return bus.read(address, flags, flag_mask)

    def read16(segment, offset, role=None):
        address = physical(segment, offset)
        if role == 'source':
            source_reads.extend((address, (address + 1) & MASK))
        elif role == 'mask':
            mask_reads.extend((address, (address + 1) & MASK))
        low = bus.read(address, flags, flag_mask)
        high = bus.read(address + 1, flags, flag_mask)
        return low | (high << 8)

    def write8(segment, offset, value, *, pixel=False):
        bus.write(physical(segment, offset), value, flags, flag_mask, pixel=pixel)

    def write16(segment, offset, value):
        address = physical(segment, offset)
        bus.write(address, value, flags, flag_mask)
        bus.write(address + 1, value >> 8, flags, flag_mask)

    def set_al(value):
        state['ax'] = (state['ax'] & 0xFF00) | (value & 0xFF)

    def set_ah(value):
        state['ax'] = (state['ax'] & 0x00FF) | ((value & 0xFF) << 8)

    def set_cl(value):
        state['cx'] = (state['cx'] & 0xFF00) | (value & 0xFF)

    def set_ch(value):
        state['cx'] = (state['cx'] & 0x00FF) | ((value & 0xFF) << 8)

    def mirror_out(offset, *, out_first=False):
        if out_first:
            bus.out(state['dx'], state['ax'], flags, flag_mask)
            write16(state['ss'], offset, state['ax'])
        else:
            write16(state['ss'], offset, state['ax'])
            bus.out(state['dx'], state['ax'], flags, flag_mask)

    def cli():
        nonlocal flags, flag_mask
        flags &= ~IF
        flag_mask |= IF

    def sti():
        nonlocal flags, flag_mask
        flags |= IF
        flag_mask |= IF

    def inc_bx():
        nonlocal flags, flag_mask
        before = state['bx']
        state['bx'] = (before + 1) & 0xFFFF
        flags = inc16_flags(flags, before)
        flag_mask = (flag_mask & CF) | (FLAGS & ~CF)

    def add_di():
        nonlocal flags, flag_mask
        before = state['di']
        state['di'] = (before + 0x27) & 0xFFFF
        flags = add16_flags(flags, before, 0x27)
        flag_mask = FLAGS

    def push(value):
        state['sp'] = (state['sp'] - 2) & 0xFFFF
        write16(state['ss'], state['sp'], value)

    def pop():
        value = read16(state['ss'], state['sp'])
        state['sp'] = (state['sp'] + 2) & 0xFFFF
        return value

    def lodsw():
        state['ax'] = read16(state['ds'], state['si'], 'source')
        state['si'] = (state['si'] + 2 * direction) & 0xFFFF

    def lodsb():
        set_al(read8(state['ds'], state['si'], 'source'))
        state['si'] = (state['si'] + direction) & 0xFFFF

    def stosb():
        write8(state['es'], state['di'], state['ax'], pixel=True)
        state['di'] = (state['di'] + direction) & 0xFFFF

    def first_pass_row():
        push(state['cx'])
        state['cx'] = read16(state['ds'], state['bx'], 'mask')
        inc_bx(); inc_bx()
        set_al(8); set_ah(state['cx'] & 0xFF)
        mirror_out(0x0E)
        cli(); set_al(read8(state['es'], state['di'])); lodsw(); stosb(); sti()

        old_ch, old_ah = (state['cx'] >> 8) & 0xFF, (state['ax'] >> 8) & 0xFF
        set_ch(old_ah); set_ah(old_ch)
        set_al(8); mirror_out(0x0E)
        cli(); set_al(read8(state['es'], state['di'])); set_al(state['cx'] >> 8); stosb(); sti()

        state['cx'] = read16(state['ds'], state['bx'], 'mask')
        inc_bx(); inc_bx()
        set_al(8); set_ah(state['cx'] & 0xFF)
        mirror_out(0x0E)
        cli(); set_al(read8(state['es'], state['di'])); lodsw(); stosb(); sti()

        old_ch, old_ah = (state['cx'] >> 8) & 0xFF, (state['ax'] >> 8) & 0xFF
        set_ch(old_ah); set_ah(old_ch)
        set_al(8); mirror_out(0x0E)
        cli(); set_al(read8(state['es'], state['di'])); set_al(state['cx'] >> 8); stosb(); sti()

        set_cl(read8(state['ds'], state['bx'], 'mask'))
        inc_bx()
        set_al(8); set_ah(state['cx'] & 0xFF)
        mirror_out(0x0E)
        cli(); set_al(read8(state['es'], state['di'])); lodsb(); stosb(); sti()
        add_di()

    def data_pass_row():
        push(state['cx'])
        cli()
        set_al(read8(state['es'], state['di'])); lodsw(); stosb()
        set_al(read8(state['es'], state['di'])); set_al(state['ax'] >> 8); stosb()
        set_al(read8(state['es'], state['di'])); lodsw(); stosb()
        set_al(read8(state['es'], state['di'])); set_al(state['ax'] >> 8); stosb()
        set_al(read8(state['es'], state['di'])); lodsb(); stosb()
        sti(); add_di()

    # PUSH DS then phase-one setup: this initial map-mask write is OUT first.
    push(state['ds'])
    state['dx'], state['ax'] = 0x03C4, 0x0F02
    mirror_out(0x08, out_first=True)
    state['dx'], state['ax'] = 0x03CE, 0
    flags = logic16_flags(flags, 0)
    flag_mask = LOGIC
    mirror_out(0x0A, out_first=True)
    state['ax'] = 0x0E01; mirror_out(0x0C, out_first=True)
    state['ax'] = 0x0005; mirror_out(0x00, out_first=True)
    state['ax'] = 0x0003; mirror_out(0x02, out_first=True)

    state['ds'] = state['cx']
    state['cx'] = 0xA000
    state['es'] = 0xA000
    state['bp'] = state['di']
    state['cx'] = 0x20
    rows = 0
    while True:
        first_pass_row()
        rows += 1
        state['cx'] = pop()
        before = state['cx']
        state['cx'] = (before - 1) & 0xFFFF
        flags = dec16_flags(flags, before)
        if state['cx'] == 0:
            break
    phase_rows.append(rows)

    state['di'] = state['bp']
    state['ax'] = 0x0001; mirror_out(0x0C)
    state['ax'] = 0x1003; mirror_out(0x02)
    state['ax'] = 0xFF08; mirror_out(0x0E)
    state['dx'] = (state['dx'] & 0xFF00) | 0x00C4
    state['ax'] = 0x0202; mirror_out(0x08)
    state['cx'] = 0x20
    rows = 0
    while True:
        data_pass_row()
        rows += 1
        state['cx'] = pop()
        state['cx'] = (state['cx'] - 1) & 0xFFFF
        if state['cx'] == 0:
            break
    phase_rows.append(rows)

    state['di'] = state['bp']
    state['dx'] = (state['dx'] & 0xFF00) | 0x00C4
    state['ax'] = 0x0402; mirror_out(0x08)
    state['cx'] = 0x20
    rows = 0
    while True:
        data_pass_row()
        rows += 1
        state['cx'] = pop()
        state['cx'] = (state['cx'] - 1) & 0xFFFF
        if state['cx'] == 0:
            break
    phase_rows.append(rows)

    state['ds'] = pop()
    state['ip'] = RET
    if not core:
        state['ip'] = pop()
    state['flags'] = flags & 0xFFFF
    return dict(memory=bytes(memory), regs=state, device=device,
                events=bus.events, used=bus.used,
                source_reads=source_reads, mask_reads=mask_reads,
                plane_checks=bus.plane_checks, phase_rows=phase_rows,
                flag_mask=flag_mask)


def expected_phase_rows(case):
    if case['provider'] == 'short-first-pass':
        return [1, 32, 32]
    if case['name'] == 'ss-vga-mirrors-and-stack':
        # Full mask bytes let the phase-one pushes write all planes. Later
        # map masks omit read-map plane zero, whose final live CX is one.
        return [32, 1, 1]
    return [32, 32, 32]


def compare_regs(label, actual, expected, flag_mask, error_type):
    for name in REG_NAMES:
        if name == 'flags':
            if ((actual[name] ^ expected[name]) & flag_mask) != 0:
                raise error_type(f'{label}: FLAGS {actual[name]:04X}/'
                                 f'{expected[name]:04X} under {flag_mask:04X}')
        elif actual[name] != expected[name]:
            raise error_type(f'{label}: {name} {actual[name]:04X}/{expected[name]:04X}')


def compare_memory(label, actual, expected, error_type):
    if actual == expected:
        return
    at = next(index for index, pair in enumerate(zip(actual, expected))
              if pair[0] != pair[1])
    raise error_type(f'{label}: RAM {at:05X} {actual[at]:02X}/{expected[at]:02X}')


def compare_events(label, actual, expected, error_type):
    if len(actual) != len(expected):
        raise error_type(f'{label}: {len(actual)} events, expected {len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        if got[:3] != want[:3]:
            raise error_type(f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        if ((got[3] ^ want[3]) & want[4]) != 0:
            raise error_type(f'{label}: event {index} FLAGS {got[3]:04X}/'
                             f'{want[3]:04X} under {want[4]:04X}')


def compare_devices(label, actual, expected, error_type):
    if actual is None or expected is None:
        if actual is not expected:
            raise error_type(label + ': VGA presence differs')
        return
    if actual.state() != expected.state():
        raise error_type(label + ': VGA planes/latches/registers differ')
    if [event[:3] for event in actual.trace] != [event[:3] for event in expected.trace]:
        raise error_type(label + ': VGA trace differs')


def run_original(case, memory, regs, device, *, core):
    return interactions.original(
        case, memory, regs, device, core, entry_flag_mask=FLAGS,
        main_instructions=OWN_INS, stop_offsets={RET: 0} if core else None,
        access_factory=WideAccess, instruction_limit=MAX_INSTRUCTIONS)


def check_producer(case, producer, memory, error_type, label):
    if case['producer_bank'] is None:
        return None
    descriptor = producer.banks[case['producer_bank']]
    bank = producer.bank(case['producer_bank'])
    start = physical(producer.destination_segment,
                     producer.destination_offset + descriptor.output_offset)
    if memory[start:start + descriptor.output_length] != bank:
        raise error_type(f'{label}: actual 5C06 bank changed during consumer execution')
    return sha(bank)


def check_producer_reads(case, producer, model, label, error_type):
    if case['producer_bank'] is None:
        return
    descriptor = producer.banks[case['producer_bank']]
    mask_offsets = [((case['bx'] + index) & 0xFFFF) for index in range(160)]
    expected_masks = [physical(case['cx'], offset) for offset in mask_offsets]
    if model['mask_reads'] != expected_masks:
        raise error_type(label + ': mask cursor did not read the actual 5C06 bank')
    if len(model['source_reads']) != 480:
        raise error_type(label + ': actual 5C06 bank did not supply 480 source bytes')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-sprite-wide-m{mutation}.dll',
                     mutation, 'entity_sprite_wide')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_entity_wide_sprite32_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_entity_wide_sprite32_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = WideAccess(case, memory, regs, device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = RasterBus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = Call(*(regs[REG_FIELDS[name]] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for name in CORE_NAMES:
                setattr(state, REG_FIELDS[name], getattr(result, name))
            state.ip = result.continuation
            status, continuation = result.status, result.continuation
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
            continuation = state.ip
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status, continuation=continuation)


def compare_case(native, case, *, core, producer=None):
    initial_memory, initial_regs, initial_device = setup(case, producer)
    model = independent(case, initial_memory, initial_regs, initial_device, core=core)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    expected = run_original(case, bytearray(initial_memory), dict(initial_regs),
                            copy.deepcopy(initial_device), core=core)
    oracle_require(expected['status'] == 0, label + ': original status was not READY')
    compare_regs(label + ' original/model', expected['regs'], model['regs'],
                 expected['flag_mask'], OracleFailure)
    compare_memory(label + ' original/model', expected['memory'], model['memory'], OracleFailure)
    compare_events(label + ' original/model', expected['events'], model['events'], OracleFailure)
    compare_devices(label + ' original/model', expected['device'], model['device'], OracleFailure)
    oracle_require(expected['used'] == model['used'], label + ': provider model differs')
    want_provider = {case['provider']} if case['provider'] else set()
    oracle_require(expected['used'] == want_provider,
                   label + ': declared provider did not fire exactly once')
    check_producer_reads(case, producer, model, label, OracleFailure)
    producer_digest = check_producer(case, producer, model['memory'], OracleFailure,
                                     label + ' model')
    check_producer(case, producer, expected['memory'], OracleFailure, label + ' original')
    oracle_require(model['phase_rows'] == expected_phase_rows(case),
                   label + f': independent phase row counts {model["phase_rows"]!r}')
    expected_pixel_writes = 5 * sum(model['phase_rows'])
    oracle_require(model['plane_checks'] == expected_pixel_writes * 4,
                   label + ': independent plane projection missed a pixel write')

    actual = native.run(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core)
    require(actual['status'] == 0, label + f': C status {actual["status"]}')
    require(actual['continuation'] == expected['continuation'],
            label + f': continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    compare_regs(label, actual['regs'], expected['regs'], expected['flag_mask'], Mismatch)
    compare_memory(label, actual['memory'], expected['memory'], Mismatch)
    compare_events(label, actual['events'], expected['events'], Mismatch)
    require(actual['used'] == expected['used'], label + ': provider effects differ')
    compare_devices(label, actual['device'], expected['device'], Mismatch)
    check_producer(case, producer, actual['memory'], Mismatch, label + ' native')
    if core:
        oracle_require(expected['regs']['ip'] == RET and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core did not stop after live POP DS')
    else:
        oracle_require(expected['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter did not consume actual SS:SP RET')
    return dict(name=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
                edges=sorted([src, dst] for scope, src, dst in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                source_read_bytes=len(model['source_reads']),
                mask_read_bytes=len(model['mask_reads']),
                phase_rows=model['phase_rows'],
                producer_bank=case['producer_bank'],
                producer_bank_sha256=producer_digest,
                plane_checks=model['plane_checks'], providers=sorted(expected['used']))


def static_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
                edges.add((address, (address + ins.size) & 0xFFFF))
            if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
                edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/entity-display.md', 'docs/entity-sprites.md',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/inputs.json', 'metadata/symbols.json',
        'metadata/regions.json', 'metadata/hints.json', 'metadata/sound-oracle.json',
        'metadata/adlib-regions.json', 'metadata/adlib-symbols.json',
        'metadata/adlib-encodings.json', 'metadata/tandysnd-regions.json',
        'metadata/tandysnd-symbols.json', 'metadata/tandysnd-encodings.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/game_code.asm',
        'src/entity_sprite_wide.asm', 'src/entity_sprite_planes.asm',
        'src/game_code_late_after_palette.asm',
        'src/entry_services.asm', 'src/image_tail.asm', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm', 'c/entity_sprite_wide.c',
        'c/entity_sprite_wide.h', 'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/entity_sprite_wide.py', 'tests/entity_interactions.py',
        'tests/entity_sprite_layout.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/minimap_vga.py', 'tools/resources.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/unpack.py', 'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing wide-sprite hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(cases, before, producer):
    oracle_require(before == input_hashes(), 'wide-sprite inputs changed before preflight')
    rows, sites, edges, plane_checks = [], set(), set(), 0
    for case in cases:
        initial, regs, device = setup(case, producer)
        for core in (True, False):
            model = independent(case, initial, regs, device, core=core)
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core=core)
            label = case['name'] + (' core' if core else ' adapter')
            oracle_require(expected['status'] == 0, label + ': original stopped abnormally')
            compare_regs(label + ' independent', expected['regs'], model['regs'],
                         expected['flag_mask'], OracleFailure)
            compare_memory(label + ' independent', expected['memory'], model['memory'],
                           OracleFailure)
            compare_events(label + ' independent', expected['events'], model['events'],
                           OracleFailure)
            compare_devices(label + ' independent', expected['device'], model['device'],
                            OracleFailure)
            oracle_require(expected['used'] == model['used'], label + ': provider differs')
            expected_providers = {case['provider']} if case['provider'] else set()
            oracle_require(expected['used'] == expected_providers,
                           label + ': provider did not fire exactly once')
            check_producer_reads(case, producer, model, label, OracleFailure)
            producer_digest = check_producer(case, producer, model['memory'],
                                              OracleFailure, label + ' model')
            check_producer(case, producer, expected['memory'], OracleFailure,
                            label + ' original')
            oracle_require(model['phase_rows'] == expected_phase_rows(case),
                           label + f': independent phase row counts {model["phase_rows"]!r}')
            expected_pixel_writes = 5 * sum(model['phase_rows'])
            oracle_require(model['plane_checks'] == expected_pixel_writes * 4,
                           label + ': independent plane-byte count changed')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            own_edges = {(src, dst) for scope, src, dst in expected['edges'
                         ] if scope == 'main'}
            rows.append(dict(name=case['name'], boundary='core' if core else 'adapter',
                             sites=sorted(own_sites), edges=[list(edge) for edge in sorted(own_edges)],
                             events=len(expected['events']), steps=expected['steps'],
                             source_read_bytes=len(model['source_reads']),
                             mask_read_bytes=len(model['mask_reads']),
                             phase_rows=model['phase_rows'],
                             producer_bank=case['producer_bank'],
                             producer_bank_sha256=producer_digest,
                             plane_checks=model['plane_checks'],
                             providers=sorted(expected['used'])))
            sites.update(own_sites); edges.update(own_edges)
            plane_checks += model['plane_checks']
        del initial, regs, device
        gc.collect()
    oracle_require(sites == OWN_SITES,
                   f'original site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
                   f'original edges differ: expected={sorted(static_edges())}, got={sorted(edges)}')
    oracle_require(before == input_hashes(), 'wide-sprite inputs changed during preflight')
    return rows, sites, edges, plane_checks


def producer_evidence(producer):
    return dict(entry=producer.entry, output_bytes=len(producer.output_bytes),
                bank_count=len(producer.banks),
                bank_bytes=[len(producer.bank(i)) for i in range(len(producer.banks))],
                sites=sorted(producer.sites), site_count=len(producer.sites),
                branch_edges=[list(edge) for edge in sorted(producer.edges)],
                instruction_steps=producer.steps, memory_transactions=producer.event_count,
                comparisons=1,
                bank_sha256=[sha(producer.bank(i)) for i in range(len(producer.banks))],
                scope=('one bounded original 5C06 run; its 80 sites, 38,916 steps and '
                       '13,153 memory transactions are excluded from consumer totals'))


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'wide-sprite inputs changed before native run')
    oracle_require(CODE_BYTES == 289 and len(OWN_SITES) == 147,
                   f'wide-sprite inventory changed: {CODE_BYTES} bytes/{len(OWN_SITES)} sites')
    producer = sprite_layout.produce_5c06()
    cases = make_cases(producer)
    baseline = Native(directory)
    rows, sites, edges, plane_checks = [], set(), set(), 0
    total_events = total_steps = 0
    for case in cases:
        for core in (True, False):
            row = compare_case(baseline, case, core=core, producer=producer)
            rows.append(row); sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']; total_steps += row['steps']
            plane_checks += row['plane_checks']
        gc.collect()
    oracle_require(sites == OWN_SITES,
                   f'native site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
                   f'native edge union differs: missing={sorted(static_edges()-edges)}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: 'df-set-forward-mask-reverse-strings',
        2: 'df-set-forward-mask-reverse-strings',
        3: 'ordinary-wide-raster',
        4: 'incoming-cx-source-not-entry-ds',
        5: 'saved-ds-mirror-and-actual-ret-alias',
        6: 'ordinary-wide-raster',
        7: 'entry-if-set-is-cleared-and-restored',
        8: 'live-first-pass-pop-count-one',
        9: 'ordinary-wide-raster',
        10: 'ordinary-wide-raster',
    }
    mutations = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=True, producer=producer)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, case=name, completed=True,
                                  mismatch=str(error)))
        else:
            raise OracleFailure(f'wide-sprite mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'wide-sprite inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
        static_instruction_addresses=sorted(OWN_SITES), branch_edge_count=len(static_edges()),
        static_branch_edges=[list(edge) for edge in sorted(static_edges())],
        case_count=len(cases), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        producer_handoff=producer_evidence(producer),
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(edge) for edge in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        independent_plane_byte_checks=plane_checks, input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain=('DrawEntityWideSprite32 6BDB..6CFB: three 32-row, five-byte planar passes; '
                'core stops after live POP DS before RET and adapter consumes actual SS:SP. '
                'All 1 MiB RAM, logical registers, defined FLAGS, ordered RAM/VGA/OUT events, '
                'and full VGA planes/latches/registers are compared. The independent model '
                'checks 480 planar writes per fixture, first-phase live saved-CX/JZ behavior, '
                'DF-sensitive LODS/STOS with forward mask cursor, literal +27h row adjustment, '
                'phase-specific SS mirror/OUT order, live DS restoration, VGA/source and stack '
                'aliases, and the actual RET. Eight further fixtures consume unchanged 640-byte '
                'banks from one bounded original 5C06 output; producer metrics are counted once '
                'and separately from the consumer.')))
    print(f'PASS wide entity sprite: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{plane_checks} independent plane-byte checks, {len(mutations)} mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-sprite-wide-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        producer = sprite_layout.produce_5c06()
        cases = make_cases(producer)
        rows, sites, edges, plane_checks = original_campaign(cases, before, producer)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
            static_instruction_addresses=sorted(OWN_SITES),
            branch_edge_count=len(static_edges()),
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=len(cases), core_adapter_comparisons=len(rows), cases=rows,
            independent_plane_byte_checks=plane_checks,
            producer_handoff=producer_evidence(producer), input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_bus_event_limit=MAX_EVENTS),
            domain='Original-only wide-sprite preflight; no native differential evidence.'))
        print(f'PASS original wide sprite: {len(cases)} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges, {plane_checks} plane checks', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_sprite_wide.py [--original-only | --native-worker DIR HASHES]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-sprite-wide-native-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
