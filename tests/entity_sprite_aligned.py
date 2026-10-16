"""Bounded differential checks for DrawEntityAlignedSprite (6170..64D8)."""
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
ENTRY, RET, END, LOAD = 0x6170, 0x64D8, 0x64D9, 0x1010
DF, IF, CF, AF = 0x0400, 0x0200, 0x0001, 0x0010
ARITH = 0x08D5
LOGIC = FLAGS & ~AF
MAX_INSTRUCTIONS, MAX_EVENTS = 2000, 4096
WORKER_SECONDS, PROCESS_MIB = 240, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-sprite-aligned-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-sprite-aligned-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())
REG_NAMES, REG_IDS = interactions.REG_NAMES, interactions.REG_IDS
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
    """Original/model mismatch, escaped code or failed execution bound."""


class Mismatch(AssertionError):
    """A completed native result differs from the original."""


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


def put_byte(memory, device, segment, offset, value, *, plane=0):
    address = physical(segment, offset)
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[plane & 3][address - VGA_BASE] = value


def put_word(memory, device, segment, offset, value, *, plane=0):
    address = physical(segment, offset)
    put_physical(memory, device, address, value, plane=plane)
    put_physical(memory, device, address + 1, value >> 8, plane=plane)


def put_physical(memory, device, address, value, *, plane=0):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[plane & 3][address - VGA_BASE] = value


def get_byte(memory, segment, offset):
    return memory[physical(segment, offset)]


def get_word(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def row_masks():
    patterns = ((0x0F, 0x01, 0x02), (0x04, 0x08, 0x0A),
                (0x02, 0x05, 0x08), (0x01, 0x0C, 0x03),
                (0x0A, 0x04, 0x01), (0x08, 0x02, 0x05),
                (0x03, 0x09, 0x04), (0x05, 0x02, 0x0C),
                (0x06, 0x01, 0x08), (0x0C, 0x0A, 0x01))
    return bytes(value for row in patterns for value in row)


def output_offsets(start, df):
    direction = -1 if df else 1
    stride = (0x29 + 3 * direction) & 0xFFFF
    return [((start + row * stride + col * direction) & 0xFFFF)
            for row in range(10) for col in range(3)]


def make_cases(producer):
    """Focused direction, aliases, source segments, mirrors and VGA fixtures."""
    specs = [
        ('ordinary-raster-baseline', {}),
        ('df-set-lods-and-stos', dict(flags=0x0ED7)),
        ('df-set-live-mask-table-stays-forward',
         dict(flags=0x0ED7, bx=0x2180, si=0x22A0,
              masks_forward=True)),
        ('incoming-cx-source-differs-from-entry-ds',
         dict(source_segment=0x6300, ds=0x3500, bx=0x1000, si=0x1800)),
        ('source-bytes-overlap-mask-table',
         dict(source_segment=0x6100, bx=0x1800, si=0x1802,
              overlap_table=True)),
        ('provider-changes-next-row-mask-after-first-output',
         dict(provider='next-row-mask')),
        ('provider-changes-source-between-raster-passes',
         dict(provider='source-after-first-pass')),
        ('destination-offset-wrap-forward', dict(di=0xFFF0)),
        ('destination-offset-wrap-df', dict(flags=0x0ED7, di=0x0004)),
        ('source-offset-wrap-forward', dict(si=0xFFEC)),
        ('source-word-offset-ffff-boundary', dict(si=0xFFFF)),
        ('source-word-physical-wrap', dict(source_segment=0xFFFF, si=0x000F)),
        ('ss-mirror-overwrites-live-saved-ds-and-return', dict(sp=0x000E)),
        ('return-word-crosses-physical-memory-top',
         dict(ss=0xFFFF, sp=0x000F, return_word=0xB35A)),
        ('return-word-offset-ffff-boundary',
         dict(ss=0x5000, sp=0xFFFF, return_word=0xC35A)),
        ('ss-is-vga-aperture', dict(ss=0xA000, sp=0x6000)),
        ('source-is-vga-plane-zero',
         dict(source_segment=0xA000, bx=0x3000, si=0x2000, di=0x4800)),
        ('vga-source-overlaps-destination',
         dict(source_segment=0xA000, bx=0x3000, si=0x4200, di=0x4200)),
        ('ss-and-source-segments-alias',
         dict(ss=0x6100, source_segment=0x6100, bx=0x0100, si=0x0500)),
        ('first-descriptor-is-at-ss-bitmask-mirror',
         dict(ss=0x5000, source_segment=0x5000, bx=0x000E, si=0x1200)),
        ('initial-if-clear-cli-and-sti', dict(flags=0x08D7)),
        ('initial-if-set-cli-and-sti', dict(flags=0x0AD7)),
        ('poisoned-replaced-entry-registers',
         dict(ax=0xDEAD, dx=0xBEEF, bp=0xFEED, es=0x1234)),
        ('mask-selectors-cover-all-four-planes', dict(mask_set=1)),
        ('zero-map-mask-and-all-map-mask', dict(mask_set=2)),
        ('live-ds-pop-from-stack-alias', dict(sp=0x0010)),
        ('source-segment-equals-entry-ds',
         dict(ds=0x6100, source_segment=0x6100)),
        ('df-set-source-offset-physical-wrap',
         dict(flags=0x0ED7, source_segment=0xFFFF, si=0x0010)),
        ('df-clear-with-vga-read-plane-two',
         dict(vga_read_map=2, di=0x2A00)),
        ('arithmetic-flags-carry-at-row-advance', dict(di=0xFFD8)),
        ('vga-destination-low-offset-and-live-latches', dict(di=0x0000)),
        ('provider-and-df-set',
         dict(provider='next-row-mask', flags=0x0ED7)),
        ('device-register-entry-poison', dict(gc_seed=0xA6, seq_seed=0x5B)),
        ('stack-return-and-source-segments-share-vga',
         dict(ss=0xA000, source_segment=0xA000, sp=0x7000,
              bx=0x3100, si=0x2300)),
    ]
    for bank_index, bank in enumerate(producer.banks):
        source_offset = producer.destination_offset + bank.plane_offset
        mask_offset = producer.destination_offset + bank.mask_offset
        specs.append((f'5b11-produced-alignment-bank-{bank_index}',
                      dict(source_segment=producer.destination_segment,
                           cx=producer.destination_segment, si=source_offset,
                           bx=mask_offset, producer_bank=bank_index)))
    cases = []
    for index, (name, fields) in enumerate(specs):
        row = dict(name=name, seed=0x617000 + index, ds=0x3500,
                   source_segment=0x6100, ss=0x5000, sp=0x9000,
                   bx=0x1000, si=0x1800, di=0x2400,
                   ax=0xBEEF, dx=0xC4D9, bp=0x7123, es=0x4123,
                   cx=None, flags=0x0AD7, return_word=0xE000 | index,
                   masks=row_masks(), provider=False, overlap_table=False,
                   masks_forward=False, mask_set=0, vga_read_map=0,
                   gc_seed=0, seq_seed=0)
        row.update(fields)
        if row['cx'] is None:
            row['cx'] = row['source_segment']
        cases.append(row)
    oracle_require(28 <= len(cases) <= 50,
                   f'aligned-sprite fixture count outside scope: {len(cases)}')
    return cases


def setup(case, producer=None):
    rng = random.Random(0x6170 + case['seed'] * 0x9E3779B1)
    if 'producer_bank' in case:
        oracle_require(producer is not None,
                       case['name'] + ': actual producer witness was not supplied')
        memory = bytearray(producer.memory)
    else:
        memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = physical(LOAD, 0)
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = MinimapVga(0x6170 ^ case['seed'], read_map=case['vga_read_map'])
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0x0E
    device.gc[3] = 0
    device.gc[4] = case['vga_read_map']
    device.gc[5] = 0
    device.gc[6] = 0x05
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

    direction = -1 if flags & DF else 1
    # Distinct incoming plane bytes make every later write independently
    # checkable. The device's read-map byte mirrors plane selected on reads.
    for index, offset in enumerate(output_offsets(regs['di'], bool(flags & DF))):
        physical_offset = physical(0xA000, offset) - VGA_BASE
        for plane_no, plane in enumerate(device.planes):
            plane[physical_offset] = (0x19 + index * 7 + plane_no * 43) & 0xFF
        memory[VGA_BASE + physical_offset] = device.planes[
            device.gc[4] & 3][physical_offset]

    # Seed exactly the physical bytes reached by the two source passes. A word
    # operand at offset FFFF reads its high byte at physical(base)+1, without
    # wrapping the segment offset to zero.
    def seed_source_operands():
        cursor = regs['si']
        ordinal = 0
        for _phase in range(2):
            for _row in range(10):
                address = physical(regs['cx'], cursor)
                put_physical(memory, device, address,
                             (0x31 + ordinal * 29 + case['seed']) & 0xFF)
                ordinal += 1
                put_physical(memory, device, address + 1,
                             (0x31 + ordinal * 29 + case['seed']) & 0xFF)
                ordinal += 1
                cursor = (cursor + 2 * direction) & 0xFFFF
                put_physical(memory, device, physical(regs['cx'], cursor),
                             (0x31 + ordinal * 29 + case['seed']) & 0xFF)
                ordinal += 1
                cursor = (cursor + direction) & 0xFFFF

    def seed_table():
        masks = case['masks']
        for index, value in enumerate(masks):
            put_byte(memory, device, regs['cx'], regs['bx'] + index, value)

    if 'producer_bank' in case:
        descriptor = producer.banks[case['producer_bank']]
        bank_start = physical(producer.destination_segment,
                              producer.destination_offset + descriptor.output_offset)
        bank = producer.bank(case['producer_bank'])
        oracle_require(memory[bank_start:bank_start + len(bank)] == bank,
                       case['name'] + ': consumer setup changed producer bank bytes')
    else:
        if case['overlap_table']:
            seed_table()
            seed_source_operands()
        else:
            seed_source_operands()
            seed_table()

        if case['mask_set'] == 1:
            values = bytes([0x0F, 0x0E, 0x0D] * 10)
            for index, value in enumerate(values):
                put_byte(memory, device, regs['cx'], regs['bx'] + index, value)
        elif case['mask_set'] == 2:
            values = bytes([0x00, 0x0F, 0x00] * 10)
            for index, value in enumerate(values):
                put_byte(memory, device, regs['cx'], regs['bx'] + index, value)

    # The called leaf receives a live near-return word at SS:SP. Stack and VGA
    # segment aliases intentionally use the same physical byte helpers.
    put_word(memory, device, regs['ss'], regs['sp'], case['return_word'])
    return memory, regs, device


class SpriteAccess(interactions.Access):
    """Bounded byte/word port bus with a live descriptor provider."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('aligned-sprite bus event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        if self.case['provider'] == 'next-row-mask' and self.out_count == 6 and \
                'next-row-mask' not in self.used:
            segment = self.regs['cx']
            offset = (self.regs['bx'] + 3) & 0xFFFF
            old = tuple(get_byte(self.memory, segment, offset + delta)
                        for delta in range(3))
            oracle_require(old != (0x08, 0x02, 0x04),
                           self.case['name'] + ': provider witness is not distinct')
            for delta, byte in enumerate((0x08, 0x02, 0x04)):
                self.store(physical(segment, offset + delta), byte)
            self.used.add('next-row-mask')
        if self.case['provider'] == 'source-after-first-pass' and \
                self.out_count == 36 and 'source-after-first-pass' not in self.used:
            segment = self.regs['cx']
            direction = -1 if self.regs['flags'] & DF else 1
            offset = (self.regs['si'] + 30 * direction) & 0xFFFF
            first = physical(segment, offset)
            third = physical(segment, offset + 2 * direction)
            old = (self.memory[first], self.memory[(first + 1) & MASK],
                   self.memory[third])
            oracle_require(old != (0xD3, 0x6A, 0xB1),
                           self.case['name'] + ': source provider did not change its bytes')
            for address, byte in ((first, 0xD3), ((first + 1) & MASK, 0x6A),
                                  (third, 0xB1)):
                self.store(address, byte)
            self.used.add('source-after-first-pass')


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


class ModelBus:
    """Independent byte/port replay and VGA plane write projection."""
    def __init__(self, case, memory, device, entry_regs):
        self.case, self.memory, self.device = case, memory, device
        self.entry_regs = entry_regs
        self.events, self.used, self.out_count = [], set(), 0
        self.plane_checks = 0

    def read(self, address, flags, mask):
        address &= MASK
        oracle_require(len(self.events) < MAX_EVENTS,
                       'independent aligned-sprite event budget exhausted')
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
                       'independent aligned-sprite event budget exhausted')
        before = None
        offset = None
        if pixel and self.device is not None and VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            before = [plane[offset] for plane in self.device.planes]
            oracle_require((self.device.gc[5] & 3) == 0,
                           'aligned sprite uses an unsupported VGA write mode')
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
                           f'independent plane write at {offset:04X}: {got!r}/{expected!r}')
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
        if self.case['provider'] == 'next-row-mask':
            segment = self.entry_regs['cx']
            offset = (self.entry_regs['bx'] + 3) & 0xFFFF
            old = tuple(get_byte(self.memory, segment, offset + delta)
                        for delta in range(3))
            oracle_require(old != (0x08, 0x02, 0x04),
                           self.case['name'] + ': independent mask provider did not change bytes')
            for delta, byte in enumerate((0x08, 0x02, 0x04)):
                self.memory[physical(segment, offset + delta)] = byte
            self.used.add('next-row-mask')
        elif self.case['provider'] == 'source-after-first-pass':
            segment = self.entry_regs['cx']
            direction = -1 if self.entry_regs['flags'] & DF else 1
            offset = (self.entry_regs['si'] + 30 * direction) & 0xFFFF
            first = physical(segment, offset)
            third = physical(segment, offset + 2 * direction)
            old = (self.memory[first], self.memory[(first + 1) & MASK],
                   self.memory[third])
            oracle_require(old != (0xD3, 0x6A, 0xB1),
                           self.case['name'] + ': independent source provider did not change bytes')
            for address, byte in ((first, 0xD3), ((first + 1) & MASK, 0x6A),
                                  (third, 0xB1)):
                self.memory[address] = byte
            self.used.add('source-after-first-pass')

    def out(self, port, value, flags, mask):
        oracle_require(len(self.events) < MAX_EVENTS,
                       'independent aligned-sprite event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        if self.case['provider'] == 'next-row-mask' and self.out_count == 6 and \
                'next-row-mask' not in self.used:
            self.provider()
        if self.case['provider'] == 'source-after-first-pass' and \
                self.out_count == 36 and 'source-after-first-pass' not in self.used:
            self.provider()


def independent(case, initial_memory, initial_regs, initial_device, *, core):
    """Instruction-ordered projection of both ten-row VGA passes."""
    memory, device = bytearray(initial_memory), copy.deepcopy(initial_device)
    state = dict(initial_regs)
    bus = ModelBus(case, memory, device, initial_regs)
    flags, flag_mask = state['flags'], FLAGS
    table_reads, source_reads = [], []
    direction = -1 if flags & DF else 1

    def record_role(address, role):
        if role == 'table':
            table_reads.append(address & MASK)
        elif role == 'source':
            source_reads.append(address & MASK)

    def read8(segment, offset, *, role=None):
        address = physical(segment, offset)
        record_role(address, role)
        return bus.read(address, flags, flag_mask)

    def read16(segment, offset, *, role=None):
        address = physical(segment, offset)
        record_role(address, role)
        record_role(address + 1, role)
        low = bus.read(address, flags, flag_mask)
        high = bus.read(address + 1, flags, flag_mask)
        return low | (high << 8)

    def write8(segment, offset, value, *, pixel=False):
        bus.write(physical(segment, offset), value, flags, flag_mask, pixel=pixel)

    def write16(segment, offset, value):
        address = physical(segment, offset)
        bus.write(address, value, flags, flag_mask)
        bus.write(address + 1, value >> 8, flags, flag_mask)

    def mirror_out(offset):
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

    def add_di_row():
        nonlocal flags, flag_mask
        before = state['di']
        state['di'] = (before + 0x29) & 0xFFFF
        flags = add16_flags(flags, before, 0x29)
        flag_mask = FLAGS

    def lodsw():
        state['ax'] = read16(state['ds'], state['si'], role='source')
        state['si'] = (state['si'] + 2 * direction) & 0xFFFF

    def lodsb():
        set_al(read8(state['ds'], state['si'], role='source'))
        state['si'] = (state['si'] + direction) & 0xFFFF

    def set_al(value):
        state['ax'] = (state['ax'] & 0xFF00) | (value & 0xFF)

    def set_ah(value):
        state['ax'] = (state['ax'] & 0x00FF) | ((value & 0xFF) << 8)

    def stosb():
        write8(state['es'], state['di'], state['ax'], pixel=True)
        state['di'] = (state['di'] + direction) & 0xFFFF

    # Entry PUSH DS, then the five setup mirror/port pairs.
    state['sp'] = (state['sp'] - 2) & 0xFFFF
    write16(state['ss'], state['sp'], state['ds'])
    state['dx'], state['ax'] = 0x03C4, 0x0F02
    mirror_out(0x08)
    state['dx'], state['ax'] = 0x03CE, 0
    flags = logic16_flags(flags, state['ax'])
    flag_mask = LOGIC
    mirror_out(0x0A)
    state['ax'] = 0x0E01
    mirror_out(0x0C)
    state['ax'] = 0x0005
    mirror_out(0x00)
    state['ax'] = 0x0003
    mirror_out(0x02)

    state['ds'] = state['cx']
    state['cx'] = 0xA000
    state['es'] = 0xA000
    state['bp'] = state['di']

    for _row in range(10):
        state['cx'] = read16(state['ds'], state['bx'], role='table')
        inc_bx()
        inc_bx()
        set_al(0x08)
        set_ah(state['cx'] & 0xFF)
        mirror_out(0x0E)
        cli()
        set_al(read8(state['es'], state['di']))
        lodsw()
        stosb()
        sti()

        old_ch, old_ah = (state['cx'] >> 8) & 0xFF, (state['ax'] >> 8) & 0xFF
        state['cx'] = (state['cx'] & 0x00FF) | (old_ah << 8)
        set_ah(old_ch)
        set_al(0x08)
        mirror_out(0x0E)
        cli()
        set_al(read8(state['es'], state['di']))
        set_al((state['cx'] >> 8) & 0xFF)
        stosb()
        sti()

        set_ah(read8(state['ds'], state['bx'], role='table'))
        inc_bx()
        set_al(0x08)
        mirror_out(0x0E)
        cli()
        set_al(read8(state['es'], state['di']))
        lodsb()
        stosb()
        sti()
        add_di_row()

    state['di'] = state['bp']
    state['ax'] = 0x0001
    mirror_out(0x0C)
    state['ax'] = 0x1003
    mirror_out(0x02)
    state['ax'] = 0xFF08
    mirror_out(0x0E)
    state['dx'] = (state['dx'] & 0xFF00) | 0x00C4
    state['ax'] = 0x0202
    mirror_out(0x08)
    for _row in range(10):
        cli()
        set_al(read8(state['es'], state['di']))
        lodsw()
        stosb()
        set_al(read8(state['es'], state['di']))
        set_al((state['ax'] >> 8) & 0xFF)
        stosb()
        set_al(read8(state['es'], state['di']))
        lodsb()
        stosb()
        sti()
        add_di_row()

    state['ds'] = read16(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 0xFFFF
    state['ip'] = RET
    if not core:
        state['ip'] = read16(state['ss'], state['sp'])
        state['sp'] = (state['sp'] + 2) & 0xFFFF
    state['flags'] = flags & 0xFFFF
    return dict(memory=bytes(memory), regs=state, device=device,
                events=bus.events, used=bus.used,
                table_reads=table_reads, source_reads=source_reads,
                plane_checks=bus.plane_checks, flag_mask=flag_mask)


def compare_regs(label, actual, expected, flag_mask, error_type):
    for name in REG_NAMES:
        if name == 'flags':
            if ((actual[name] ^ expected[name]) & flag_mask) != 0:
                raise error_type(f'{label}: FLAGS {actual[name]:04X}/'
                                 f'{expected[name]:04X} under {flag_mask:04X}')
        elif actual[name] != expected[name]:
            raise error_type(f'{label}: {name} {actual[name]:04X}/'
                             f'{expected[name]:04X}')


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
        raise error_type(label + ': VGA plane/latch/register state differs')
    if [event[:3] for event in actual.trace] != [event[:3] for event in expected.trace]:
        raise error_type(label + ': VGA trace differs')


def run_original(case, memory, regs, device, *, core):
    return interactions.original(
        case, memory, regs, device, core, entry_flag_mask=FLAGS,
        main_instructions=OWN_INS, stop_offsets={RET: 0} if core else None,
        access_factory=SpriteAccess, instruction_limit=MAX_INSTRUCTIONS)


def check_producer_bank(case, producer, memory, error_type, label):
    if 'producer_bank' not in case:
        return None
    index = case['producer_bank']
    bank = producer.bank(index)
    descriptor = producer.banks[index]
    address = physical(producer.destination_segment,
                       producer.destination_offset + descriptor.output_offset)
    if memory[address:address + len(bank)] != bank:
        raise error_type(f'{label}: producer bank {index} changed in consumer memory')
    return sha(bank)


def check_producer_roles(case, producer, model, label, error_type):
    if 'producer_bank' not in case:
        return
    table = [physical(case['cx'], (case['bx'] + index) & 0xFFFF)
             for index in range(30)]
    source = [physical(case['cx'], (case['si'] + index) & 0xFFFF)
              for index in range(60)]
    if model['table_reads'] != table:
        raise error_type(label + ': consumer did not read the actual producer mask bank')
    if model['source_reads'] != source:
        raise error_type(label + ': consumer did not read the actual producer plane bytes')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-sprite-aligned-m{mutation}.dll',
                     mutation, 'entity_sprite_aligned')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_entity_aligned_sprite_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_entity_aligned_sprite_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = SpriteAccess(case, memory, regs, device)

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
    compare_memory(label + ' original/model', expected['memory'], model['memory'],
                   OracleFailure)
    compare_events(label + ' original/model', expected['events'], model['events'],
                   OracleFailure)
    compare_devices(label + ' original/model', expected['device'], model['device'],
                    OracleFailure)
    check_producer_roles(case, producer, model, label, OracleFailure)
    producer_digest = check_producer_bank(case, producer, model['memory'],
                                           OracleFailure, label + ' model')
    check_producer_bank(case, producer, expected['memory'], OracleFailure,
                        label + ' original')
    oracle_require(expected['used'] == model['used'], label + ': provider differs')
    expected_providers = ({case['provider']} if case['provider'] else set())
    oracle_require(expected['used'] == expected_providers,
                   label + ': declared live provider did not fire exactly once')
    oracle_require(len(model['table_reads']) == 30 and
                   len(model['source_reads']) == 60,
                   label + ': source and forward mask-table read roles changed')
    if case['masks_forward']:
        expected_addresses = [physical(case['cx'], (case['bx'] + index) & 0xFFFF)
                              for index in range(30)]
        oracle_require(model['table_reads'] == expected_addresses,
                       label + ': modeled mask reads were not forward/byte-complete')
        table_addresses = set(expected_addresses)
        observed = [event[1] for event in expected['events']
                    if event[0] == 'read' and event[1] in table_addresses]
        oracle_require(observed == expected_addresses,
                       label + ': original mask-table accesses were not forward')

    actual = native.run(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core)
    require(actual['status'] == 0, label + f': status {actual["status"]}')
    require(actual['continuation'] == expected['continuation'],
            label + f': continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    compare_regs(label, actual['regs'], expected['regs'], expected['flag_mask'], Mismatch)
    compare_memory(label, actual['memory'], expected['memory'], Mismatch)
    compare_events(label, actual['events'], expected['events'], Mismatch)
    require(actual['used'] == expected['used'],
            label + f': provider effects {actual["used"]}/{expected["used"]}')
    compare_devices(label, actual['device'], expected['device'], Mismatch)
    check_producer_bank(case, producer, actual['memory'], Mismatch, label + ' native')
    if core:
        oracle_require(expected['regs']['ip'] == RET and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core did not stop after live POP DS')
    else:
        oracle_require(expected['regs']['sp'] ==
                       ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter did not consume actual near RET')
    if case['name'] == 'ss-mirror-overwrites-live-saved-ds-and-return':
        oracle_require(expected['regs']['ds'] == 0x0001,
                       label + ': POP DS did not use the live SS:000C mirror')
        if not core:
            oracle_require(expected['regs']['ip'] != case['return_word'],
                           label + ': mirror did not overwrite the actual RET word')
    return dict(name=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
                edges=sorted([src, dst] for scope, src, dst in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                table_read_bytes=len(model['table_reads']),
                source_read_bytes=len(model['source_reads']),
                producer_bank=case.get('producer_bank'),
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
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/inputs.json',
        'metadata/symbols.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/sound-oracle.json', 'metadata/adlib-regions.json',
        'metadata/adlib-symbols.json', 'metadata/adlib-encodings.json',
        'metadata/tandysnd-regions.json', 'metadata/tandysnd-symbols.json',
        'metadata/tandysnd-encodings.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/toolchain-lock.json',
        'src/program.asm', 'src/game_code.asm', 'src/game_code_late_after_entities.asm',
        'src/game_code_late_after_palette.asm', 'src/entry_services.asm',
        'src/entity_sprite_aligned.asm', 'src/entity_graphics.asm', 'src/image_tail.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_sprite_aligned.c', 'c/entity_sprite_aligned.h', 'c/lemmings_sym.h',
        'c/regs.h', 'c/special_blit.h', 'tests/entity_sprite_aligned.py',
        'tests/entity_interactions.py', 'tests/entity_sprite_layout.py',
        'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/minimap_vga.py',
        'tools/resources.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/unpack.py', 'tools/difftest.py',
        'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing aligned-sprite hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(cases, before, producer):
    oracle_require(before == input_hashes(), 'aligned-sprite inputs changed before preflight')
    rows, sites, edges, plane_checks = [], set(), set(), 0
    for case in cases:
        initial, regs, device = setup(case, producer)
        for core in (True, False):
            model = independent(case, initial, regs, device, core=core)
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core=core)
            label = case['name'] + (' core' if core else ' adapter')
            oracle_require(expected['status'] == 0, label + ': original stopped abnormally')
            compare_regs(label + ' independent model', expected['regs'], model['regs'],
                         expected['flag_mask'], OracleFailure)
            compare_memory(label + ' independent model', expected['memory'], model['memory'],
                           OracleFailure)
            compare_events(label + ' independent model', expected['events'], model['events'],
                           OracleFailure)
            compare_devices(label + ' independent model', expected['device'], model['device'],
                            OracleFailure)
            check_producer_roles(case, producer, model, label, OracleFailure)
            bank_digest = check_producer_bank(case, producer, model['memory'],
                                               OracleFailure, label + ' model')
            check_producer_bank(case, producer, expected['memory'], OracleFailure,
                                label + ' original')
            oracle_require(expected['used'] == model['used'], label + ': provider differs')
            expected_providers = ({case['provider']} if case['provider'] else set())
            oracle_require(expected['used'] == expected_providers,
                           label + ': declared provider did not fire exactly once')
            oracle_require(len(model['table_reads']) == 30 and
                           len(model['source_reads']) == 60,
                           label + ': source/table read role accounting changed')
            if case['masks_forward']:
                expected_addresses = [physical(case['cx'],
                                               (case['bx'] + index) & 0xFFFF)
                                      for index in range(30)]
                oracle_require(model['table_reads'] == expected_addresses,
                               label + ': table cursor projection differs')
                table_addresses = set(expected_addresses)
                observed = [event[1] for event in expected['events']
                            if event[0] == 'read' and event[1] in table_addresses]
                oracle_require(observed == expected_addresses,
                               label + ': original table reads did not stay forward')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            own_edges = {(src, dst) for scope, src, dst in expected['edges']
                         if scope == 'main'}
            rows.append(dict(name=case['name'], boundary='core' if core else 'adapter',
                             sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                             events=len(expected['events']), steps=expected['steps'],
                             table_read_bytes=len(model['table_reads']),
                             source_read_bytes=len(model['source_reads']),
                             producer_bank=case.get('producer_bank'),
                             producer_bank_sha256=bank_digest,
                             plane_checks=model['plane_checks'],
                             providers=sorted(expected['used'])))
            sites.update(own_sites)
            edges.update(own_edges)
            plane_checks += model['plane_checks']
        del initial, regs, device
        gc.collect()
    oracle_require(sites == OWN_SITES,
                   f'original site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
                   f'original edges differ: expected {sorted(static_edges())}, got {sorted(edges)}')
    oracle_require(before == input_hashes(), 'aligned-sprite inputs changed during preflight')
    return rows, sites, edges, plane_checks


def producer_evidence(producer):
    return dict(entry=producer.entry, output_bytes=len(producer.output_bytes),
                bank_count=len(producer.banks),
                bank_bytes=[len(producer.bank(index))
                            for index in range(len(producer.banks))],
                sites=sorted(producer.sites), site_count=len(producer.sites),
                branch_edges=[list(edge) for edge in sorted(producer.edges)],
                instruction_steps=producer.steps,
                memory_transactions=producer.event_count,
                comparisons=1,
                bank_sha256=[sha(producer.bank(index))
                             for index in range(len(producer.banks))],
                scope='one bounded original 5B11 producer run; excluded from consumer sites, '
                      'steps and byte-bus event totals')


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'aligned-sprite inputs changed before native run')
    oracle_require(CODE_BYTES == 873 and len(OWN_SITES) == 478,
                   f'aligned-sprite inventory changed: {CODE_BYTES} bytes/{len(OWN_SITES)} sites')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned executable image identity changed')
    producer = sprite_layout.produce_5b11()
    cases = make_cases(producer)
    baseline = Native(directory)
    rows, sites, edges, plane_checks = [], set(), set(), 0
    total_events = total_steps = 0
    for case in cases:
        for core in (True, False):
            row = compare_case(baseline, case, core=core, producer=producer)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
            plane_checks += row['plane_checks']
        del case
        gc.collect()
    oracle_require(sites == OWN_SITES,
                   f'native site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
                   f'native edge union differs: missing={sorted(static_edges()-edges)}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: 'df-set-lods-and-stos',
        2: 'df-set-lods-and-stos',
        3: 'ordinary-raster-baseline',
        4: 'incoming-cx-source-differs-from-entry-ds',
        5: 'ss-mirror-overwrites-live-saved-ds-and-return',
        6: 'ordinary-raster-baseline',
        7: 'initial-if-set-cli-and-sti',
        8: 'ordinary-raster-baseline',
        9: 'ordinary-raster-baseline',
        10: 'ordinary-raster-baseline',
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
            raise OracleFailure(f'aligned-sprite mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'aligned-sprite inputs changed during native campaign')
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
        domain=('DrawEntityAlignedSprite 6170..64D8. The logical core executes PUSH DS, '
                'both ten-row phases and live POP DS, stopping before RET; the adapter reads '
                'the actual SS near-return word. Full 1 MiB RAM, all logical registers, '
                'defined FLAGS, ordered RAM/VGA/OUT events and full VGA planes/latches/registers '
                'are compared. An independent row model checks all 60 planar writes per fixture, '
                'forward DS:BX masks under either DF direction, DF-sensitive LODS/STOS, live '
                'incoming-CX source, fixed +29h row advance, phase mirrors, VGA source aliases, '
                'stack/RET aliases and the actual ten-row boundaries. Eight additional cases '
                'consume unchanged 90-byte banks from one bounded original 5B11 output: each '
                'provenance bank is 60 plane bytes plus 30 OR-mask bytes. These cases verify '
                'data flow from actual output RAM, not execution of the full producer caller.')))
    print(f'PASS aligned entity sprite: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{plane_checks} independent plane-byte checks, {len(mutations)} completed mutants',
          flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-sprite-aligned-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        producer = sprite_layout.produce_5b11()
        cases = make_cases(producer)
        rows, sites, edges, plane_checks = original_campaign(cases, before, producer)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
            static_instruction_addresses=sorted(OWN_SITES),
            branch_edge_count=len(static_edges()),
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=len(cases), core_adapter_comparisons=len(rows),
            cases=rows, independent_plane_byte_checks=plane_checks,
            producer_handoff=producer_evidence(producer),
            input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_bus_event_limit=MAX_EVENTS),
            domain='Original-only aligned-sprite preflight; no native differential evidence.'))
        print(f'PASS original aligned sprite: {len(cases)} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges, {plane_checks} plane checks', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_sprite_aligned.py '
                         '[--original-only | --native-worker DIR HASHES]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-sprite-aligned-native-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
