"""Bounded differential checks for DrawEntityTwoByteStrip (6F7B..6FE1)."""
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

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
FLAGS = interactions.FLAGS
ENTRY, RET, END = 0x6F7B, 0x6FE1, 0x6FE2
LOAD = 0x1010
DF, IF = 0x0400, 0x0200
ARITH = 0x08D5
MAX_INSTRUCTIONS, MAX_EVENTS = 1024, 2048
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-strip-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-strip-original-differential.json'

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


class Mismatch(AssertionError):
    """A completed native result differs from the completed original."""


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


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def configured_vga(seed):
    device = MinimapVga(0x6F7B ^ seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = device.gc[1] = device.gc[3] = 0
    device.gc[4] = device.gc[5] = 0
    device.gc[8] = 0xFF
    device.gc[6] = 0x05
    return device


def seed_physical(memory, device, address, value):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        offset = address - VGA_BASE
        for plane in device.planes:
            plane[offset] = value


def seed_word(memory, device, segment, offset, value):
    address = physical(segment, offset)
    seed_physical(memory, device, address, value)
    seed_physical(memory, device, address + 1, value >> 8)


def make_cases():
    """Focused direction, source-segment, stack and provider witnesses."""
    words = [0x11A3, 0x22B4, 0x33C5, 0x44D6,
             0x55E7, 0x66F8, 0x7709, 0x5A3C]
    specs = [
        dict(name='ordinary-vga-eight-rows', seed=1),
        dict(name='source-ds-is-incoming-cx', seed=2, ds=0x3500,
             source_segment=0x6100, source_words=words),
        dict(name='df-set-lodsw-and-stosb', seed=3, df=True,
             source_words=words, di=0x3100),
        dict(name='df-clear-explicit', seed=4, df=False, flags=0x0AD7),
        dict(name='first-and-second-latch-reads', seed=5,
             source_words=words, di=0x4200),
        dict(name='source-physical-word-wrap', seed=6, source_segment=0xFFFF,
             si=0x000F, source_words=words),
        dict(name='source-offset-wrap-df', seed=7, df=True, si=0x0003,
             source_words=words),
        dict(name='destination-offset-wrap-forward', seed=8, di=0xFFF0),
        dict(name='df-stosb-offset-wrap', seed=9, di=0x0000, df=True),
        dict(name='push-ds-word-crosses-physical-top', seed=10, ss=0xFFFF,
             sp=0x0011, source_words=words, providers=[(7, 0x0808, 1)]),
        dict(name='outer-ret-word-crosses-physical-top', seed=11,
             ss=0xFFFC, sp=0x003F, return_word=0xC37A),
        dict(name='mirror-overwrites-saved-ds', seed=12, sp=0x0010,
             source_words=words),
        dict(name='mirror-overwrites-actual-ret', seed=13, sp=0x000E,
             source_words=words),
        dict(name='provider-reduces-to-one-row', seed=14,
             providers=[(7, 8, 1)]),
        dict(name='provider-expands-to-two-rows', seed=15,
             providers=[(7, 8, 3), (9, 2, 1)]),
        dict(name='provider-controls-three-rows', seed=16,
             providers=[(7, 8, 4), (9, 3, 2)]),
        dict(name='provider-expands-live-loop-to-nine', seed=26,
             providers=[(7, 8, 9)], source_words=words + [0x9ABC]),
        dict(name='vga-source-overlaps-first-destination', seed=17,
             source_segment=0xA000, si=0x2400, di=0x2400,
             source_words=words),
        dict(name='vga-stack-and-mirrors', seed=18, ss=0xA000, sp=0x3000,
             source_words=[0xFFFF] * 8),
        dict(name='stack-and-source-segments-alias', seed=19, ss=0x5000,
             source_segment=0x5000, ds=0x3500, si=0x0100,
             source_words=words),
        dict(name='entry-if-clear-final-sti', seed=20, iflag=False),
        dict(name='entry-if-set-final-sti', seed=21, iflag=True),
        dict(name='entry-register-poison', seed=22, ax=0xD35A, bx=0xB17E,
             bp=0x7A91, es=0x4152, flags=0x0A02),
        dict(name='ram-only-memory-path', seed=23, vga=False,
             source_words=words),
        dict(name='ss-ds-alias-with-live-pop', seed=24, ss=0x3500,
             ds=0x3500, source_segment=0x6100, source_words=words),
        dict(name='df-set-physical-source-wrap', seed=25, df=True,
             source_segment=0xFFFF, si=0x000F, di=0x7FFE,
             source_words=words),
    ]
    rows = []
    for spec in specs:
        row = dict(name='', seed=0, ds=0x3500, source_segment=0x6000,
                   ss=0x5000, sp=0x9000, si=0x1200, di=0x2000,
                   ax=0x4B27, bx=0xB316, dx=0xC4D9, bp=0x5193,
                   es=0x4123, flags=0x0AD7, df=None, iflag=None,
                   return_word=0xE000, vga=True, source_words=None,
                   providers=[])
        row.update(spec)
        rows.append(row)
    oracle_require(20 <= len(rows) <= 35,
                   f'entity-strip fixture count outside scope: {len(rows)}')
    return rows


def setup(case):
    rng = random.Random(0x6F7B + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = physical(LOAD, 0)
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = configured_vga(case['seed']) if case['vga'] else None
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    flags = ((case['flags'] | 2) & FLAGS) & ~0x0100
    if case['df'] is not None:
        flags = (flags | DF) if case['df'] else (flags & ~DF)
    if case['iflag'] is not None:
        flags = (flags | IF) if case['iflag'] else (flags & ~IF)
    regs.update(cs=LOAD, ip=ENTRY, ax=case['ax'], bx=case['bx'],
                cx=case['source_segment'], dx=case['dx'], si=case['si'],
                di=case['di'], bp=case['bp'], ds=case['ds'], es=case['es'],
                ss=case['ss'], sp=case['sp'], flags=flags)

    # Construct distinct destination planes so every STOSB has an independent
    # expected byte for all four planes after the original VGA register setup.
    direction = -1 if flags & DF else 1
    row_stride = 0x2A + 2 * direction
    for row_index in range(9):
        row = (regs['di'] + row_index * row_stride) & 0xFFFF
        for pos in (row, (row + direction) & 0xFFFF):
            address = physical(0xA000, pos)
            if device is not None:
                offset = address - VGA_BASE
                for plane_no, plane in enumerate(device.planes):
                    plane[offset] = (0x19 + row_index * 17 + pos +
                                     plane_no * 53) & 0xFF
                memory[address] = device.planes[device.gc[4] & 3][offset]
            else:
                memory[address] = (0x91 + row_index * 11 + pos) & 0xFF

    words = case['source_words'] or [((0x31 + 0x17 * i) << 8) |
                                     (0xA3 + 0x0D * i) & 0xFF
                                     for i in range(8)]
    oracle_require(len(words) >= 8, case['name'] + ': at least eight source words required')
    delta = -2 if flags & DF else 2
    for index, word in enumerate(words[:9]):
        seed_word(memory, device, regs['cx'], (regs['si'] + index * delta) & 0xFFFF,
                  word)
        # The distinct entry-DS bytes make mutation 3 a guaranteed wrong source.
        if regs['ds'] != regs['cx']:
            seed_word(memory, device, regs['ds'],
                      (regs['si'] + index * delta) & 0xFFFF,
                      word ^ (0x5D3A + index * 0x0101))

    seed_word(memory, device, regs['ss'], regs['sp'], case['return_word'])
    return memory, regs, device


class StripAccess(interactions.Access):
    """Bounded physical bus, VGA effects and a live saved-CX provider."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('entity-strip bus event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        for trigger, before, after in self.case['providers']:
            marker = f'saved-cx@out{trigger}'
            if self.out_count == trigger and marker not in self.used:
                slot = (self.regs['sp'] - 4) & 0xFFFF
                actual = get16(self.memory, self.regs['ss'], slot)
                oracle_require(actual == before,
                    f'{self.case["name"]}: provider out#{trigger} saw saved CX '
                    f'{actual:04X}, expected {before:04X}')
                self.modify_word(self.regs['ss'], slot, after)
                self.used.add(marker)


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
        out |= 0x0001
    if (left ^ right ^ result) & 0x0010:
        out |= 0x0010
    if (~(left ^ right) & (left ^ result) & 0x8000):
        out |= 0x0800
    return ((flags & ~ARITH) | out) & 0xFFFF


class ModelBus:
    def __init__(self, case, memory, device, entry_regs):
        self.case, self.memory, self.device = case, memory, device
        self.entry_regs = entry_regs
        self.events, self.used, self.out_count = [], set(), 0

    def read(self, address, flags):
        address &= MASK
        if len(self.events) >= MAX_EVENTS:
            raise interactions.OracleFailure('independent strip event budget exhausted')
        if self.device is not None and VGA_BASE <= address < VGA_END:
            value = self.device.read(self.memory, address, flags)
        else:
            value = self.memory[address]
        self.memory[address] = value
        self.events.append(('read', address, value, flags & 0xFFFF, FLAGS))
        return value

    def write(self, address, value, flags):
        address &= MASK
        value &= 0xFF
        if len(self.events) >= MAX_EVENTS:
            raise interactions.OracleFailure('independent strip event budget exhausted')
        if self.device is not None and VGA_BASE <= address < VGA_END:
            self.device.write(self.memory, address, value, flags)
        else:
            self.memory[address] = value
        self.memory[address] = value
        self.events.append(('write', address, value, flags & 0xFFFF, FLAGS))

    def write_provider_word(self, segment, offset, value):
        address = physical(segment, offset)
        self.memory[address] = value & 0xFF
        self.memory[(address + 1) & MASK] = (value >> 8) & 0xFF

    def out(self, port, value, flags):
        if len(self.events) >= MAX_EVENTS:
            raise interactions.OracleFailure('independent strip event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, FLAGS))
        for trigger, before, after in self.case['providers']:
            marker = f'saved-cx@out{trigger}'
            if self.out_count == trigger and marker not in self.used:
                slot = (self.entry_regs['sp'] - 4) & 0xFFFF
                actual = get16(self.memory, self.entry_regs['ss'], slot)
                oracle_require(actual == before,
                    f'{self.case["name"]}: independent provider out#{trigger} '
                    f'saw {actual:04X}, expected {before:04X}')
                self.write_provider_word(self.entry_regs['ss'], slot, after)
                self.used.add(marker)


def plane_write_expected(device, value):
    gc, seq = device.gc, device.seq
    rotate = gc[3] & 7
    rotated = value if rotate == 0 else ((value >> rotate) | (value << (8 - rotate))) & 0xFF
    operation, bit_mask = (gc[3] >> 3) & 3, gc[8]
    expected = []
    for plane in range(4):
        if not (seq[2] & (1 << plane)):
            expected.append(device.planes[plane])
            continue
        source = ((0xFF if gc[0] & (1 << plane) else 0)
                  if gc[1] & (1 << plane) else rotated)
        latch = device.latches[plane]
        if operation == 1:
            source &= latch
        elif operation == 2:
            source |= latch
        elif operation == 3:
            source ^= latch
        expected.append(((source & bit_mask) | (latch & (~bit_mask & 0xFF))) & 0xFF)
    return expected


def independent(case, initial_memory, initial_regs, initial_device, *, core):
    """Instruction-ordered replay, including an independent VGA write equation."""
    memory, device = bytearray(initial_memory), copy.deepcopy(initial_device)
    state = dict(initial_regs)
    bus = ModelBus(case, memory, device, initial_regs)
    flags = state['flags']
    plane_checks = 0

    def read8(segment, offset):
        return bus.read(physical(segment, offset), flags)

    def write8(segment, offset, value, *, pixel=False):
        nonlocal plane_checks
        address = physical(segment, offset)
        expected = None
        if (pixel and device is not None and VGA_BASE <= address < VGA_END):
            oracle_require((device.gc[5] & 3) == 0,
                           case['name'] + ': output did not use VGA write mode 0')
            expected = plane_write_expected(device, value)
        bus.write(address, value, flags)
        if expected is not None:
            offset_vga = address - VGA_BASE
            for plane_no, plane in enumerate(device.planes):
                oracle_require(plane[offset_vga] == expected[plane_no],
                    f'{case["name"]}: independent plane {plane_no} write differs')
            plane_checks += 4

    def read16(segment, offset):
        address = physical(segment, offset)
        return bus.read(address, flags) | (bus.read(address + 1, flags) << 8)

    def write16(segment, offset, value):
        address = physical(segment, offset)
        bus.write(address, value, flags)
        bus.write(address + 1, value >> 8, flags)

    state['flags'] &= ~IF
    flags = state['flags']
    state['sp'] = (state['sp'] - 2) & 0xFFFF
    write16(state['ss'], state['sp'], state['ds'])
    state['dx'], state['ax'] = 0x03C4, 0x0F02
    write16(state['ss'], 0x0008, state['ax']); bus.out(state['dx'], state['ax'], flags)
    state['dx'], state['ax'] = 0x03CE, 0x0300
    write16(state['ss'], 0x000A, state['ax']); bus.out(state['dx'], state['ax'], flags)
    state['ax'] = 0x0E01
    write16(state['ss'], 0x000C, state['ax']); bus.out(state['dx'], state['ax'], flags)
    state['ax'] = 0x0005
    write16(state['ss'], 0x0000, state['ax']); bus.out(state['dx'], state['ax'], flags)
    state['ax'] = 0x0003
    write16(state['ss'], 0x0002, state['ax']); bus.out(state['dx'], state['ax'], flags)

    state['ds'] = state['cx']
    state['cx'] = 0xA000
    state['es'] = state['cx']
    state['bp'] = state['di']
    state['cx'] = 8
    direction = -1 if flags & DF else 1
    source_step = -2 if flags & DF else 2
    rows = 0
    while True:
        rows += 1
        oracle_require(rows <= 16, case['name'] + ': independent loop guard exhausted')
        state['sp'] = (state['sp'] - 2) & 0xFFFF
        write16(state['ss'], state['sp'], state['cx'])

        _first_latch = read8(state['es'], state['di'])
        source = read16(state['ds'], state['si'])
        state['si'] = (state['si'] + source_step) & 0xFFFF
        state['ax'] = source
        state['cx'] = source
        state['ax'] = ((state['ax'] & 0x00FF) << 8) | (state['ax'] & 0x00FF)
        state['ax'] = (state['ax'] & 0xFF00) | 0x08
        write16(state['ss'], 0x000E, state['ax'])
        bus.out(state['dx'], state['ax'], flags)
        state['ax'] = (state['ax'] & 0xFF00) | ((state['ax'] >> 8) & 0xFF)
        write8(state['es'], state['di'], state['ax'] & 0xFF, pixel=True)
        state['di'] = (state['di'] + direction) & 0xFFFF

        _second_latch = read8(state['es'], state['di'])
        state['ax'] = (state['ax'] & 0xFF00) | 0x08
        state['ax'] = ((state['cx'] & 0xFF00) | (state['ax'] & 0x00FF))
        write16(state['ss'], 0x000E, state['ax'])
        bus.out(state['dx'], state['ax'], flags)
        state['ax'] = (state['ax'] & 0xFF00) | ((state['ax'] >> 8) & 0xFF)
        write8(state['es'], state['di'], state['ax'] & 0xFF, pixel=True)
        state['di'] = (state['di'] + direction) & 0xFFFF

        before = state['di']
        state['di'] = (state['di'] + 0x2A) & 0xFFFF
        flags = add16_flags(flags, before, 0x2A)
        state['sp'] = state['sp'] & 0xFFFF
        state['cx'] = read16(state['ss'], state['sp'])
        state['sp'] = (state['sp'] + 2) & 0xFFFF
        state['cx'] = (state['cx'] - 1) & 0xFFFF
        if state['cx'] == 0:
            break

    flags |= IF
    state['flags'] = flags & 0xFFFF
    state['ds'] = read16(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 0xFFFF
    state['ip'] = RET
    if not core:
        state['ip'] = read16(state['ss'], state['sp'])
        state['sp'] = (state['sp'] + 2) & 0xFFFF
    return dict(memory=bytes(memory), regs=state, device=device,
                events=bus.events, used=bus.used, rows=rows,
                plane_checks=plane_checks)


def compare_regs(label, actual, expected, flag_mask, error_type):
    for name in REG_NAMES:
        if name == 'flags':
            if ((actual[name] ^ expected[name]) & flag_mask) != 0:
                raise error_type(f'{label}: FLAGS {actual[name]:04X}/{expected[name]:04X} '
                                 f'under {flag_mask:04X}')
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
            raise error_type(f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                             f'under {want[4]:04X}')


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
    stops = {RET: 0} if core else None
    return interactions.original(case, memory, regs, device, core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        stop_offsets=stops, access_factory=StripAccess,
        instruction_limit=MAX_INSTRUCTIONS)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-strip-m{mutation}.dll',
                     mutation, 'entity_strip')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_draw_entity_two_byte_strip_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_draw_entity_two_byte_strip_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = StripAccess(case, memory, regs, device)

        def read(_ctx, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def write(_ctx, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def out(_ctx, port, value, flags):
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


def compare_case(native, case, *, core):
    initial_memory, initial_regs, initial_device = setup(case)
    model = independent(case, initial_memory, initial_regs, initial_device, core=core)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    expected = run_original(case, bytearray(initial_memory), dict(initial_regs),
                            copy.deepcopy(initial_device), core=core)
    oracle_require(expected['status'] == 0, label + ': unexpected original status')
    compare_regs(label + ' original/model', expected['regs'], model['regs'],
                 expected['flag_mask'], interactions.OracleFailure)
    compare_memory(label + ' original/model', expected['memory'], model['memory'],
                   interactions.OracleFailure)
    compare_events(label + ' original/model', expected['events'], model['events'],
                   interactions.OracleFailure)
    compare_devices(label + ' original/model', expected['device'], model['device'],
                    interactions.OracleFailure)
    oracle_require(expected['used'] == model['used'],
                   label + ': provider effects differ')
    if case['providers']:
        oracle_require(expected['used'] == {f'saved-cx@out{row[0]}'
                                            for row in case['providers']},
                       label + f': provider did not fire: {expected["used"]}')

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

    if core:
        oracle_require(expected['regs']['ip'] == RET and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core boundary did not retain caller SP')
    else:
        oracle_require(expected['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter did not consume live RET')
    if case['name'] == 'mirror-overwrites-saved-ds':
        oracle_require(expected['regs']['ds'] == 0x5A08,
                       label + ': live POP DS did not read final SS:E word')
    if case['name'] == 'mirror-overwrites-actual-ret' and not core:
        oracle_require(expected['regs']['ip'] == 0x5A08,
                       label + ': adapter did not read mirror-overwritten RET')
    return dict(name=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
                edges=sorted([src, dst] for scope, src, dst in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                rows=model['rows'], plane_checks=model['plane_checks'],
                providers=sorted(expected['used']))


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
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/inputs.json',
        'metadata/symbols.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json', 'metadata/toolchain-lock.json',
        'src/program.asm', 'src/game_code.asm', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm', 'src/entity_strip.asm',
        'src/entity_sprite_dispatch.asm', 'src/fixed_pattern_drawing.asm',
        'src/entity_sprite_planes.asm', 'src/entity_sprite_wide.asm',
        'src/entity_sprite_four_planes.asm', 'src/entity_graphics.asm',
        'src/image_tail.asm',
        'c/entity_strip.c', 'c/entity_strip.h', 'c/regs.h', 'c/special_blit.h',
        'c/lemmings_sym.h', 'tests/entity_strip.py', 'tests/entity_interactions.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/minimap_vga.py', 'tools/resources.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/unpack.py',
        'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing entity-strip hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(cases, before):
    oracle_require(before == input_hashes(), 'entity-strip inputs changed before preflight')
    rows, sites, edges = [], set(), set()
    for case in cases:
        initial, regs, device = setup(case)
        for core in (True, False):
            model = independent(case, initial, regs, device, core=core)
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core=core)
            label = case['name'] + (' core' if core else ' adapter')
            oracle_require(expected['status'] == 0, label + ': original stopped abnormally')
            compare_regs(label + ' independent model', expected['regs'], model['regs'],
                         expected['flag_mask'], interactions.OracleFailure)
            compare_memory(label + ' independent model', expected['memory'], model['memory'],
                           interactions.OracleFailure)
            compare_events(label + ' independent model', expected['events'], model['events'],
                           interactions.OracleFailure)
            compare_devices(label + ' independent model', expected['device'], model['device'],
                            interactions.OracleFailure)
            oracle_require(expected['used'] == model['used'], label + ': provider differs')
            if case['name'] == 'mirror-overwrites-saved-ds':
                oracle_require(expected['regs']['ds'] == 0x5A08,
                    label + ': live POP DS did not read the final SS:E mirror')
            if case['name'] == 'mirror-overwrites-actual-ret' and not core:
                oracle_require(expected['regs']['ip'] == 0x5A08,
                    label + ': adapter did not read the mirror-overwritten RET')
            if case['providers']:
                oracle_require(expected['used'] == {f'saved-cx@out{row[0]}'
                                                    for row in case['providers']},
                               label + ': live saved-CX provider was not used')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            own_edges = {(src, dst) for scope, src, dst in expected['edges']
                         if scope == 'main'}
            rows.append(dict(name=case['name'], boundary='core' if core else 'adapter',
                             sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                             events=len(expected['events']), steps=expected['steps'],
                             loop_rows=model['rows'], plane_checks=model['plane_checks'],
                             providers=sorted(expected['used'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == OWN_SITES,
        f'original site union differs: missing={sorted(OWN_SITES-sites)} '
        f'extra={sorted(sites-OWN_SITES)}')
    expected_edges = static_edges()
    oracle_require(edges == expected_edges,
        f'original edge union differs: missing={sorted(expected_edges-edges)} '
        f'extra={sorted(edges-expected_edges)}')
    oracle_require(before == input_hashes(), 'entity-strip inputs changed during preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'entity-strip inputs changed before native run')
    oracle_require(CODE_BYTES == 103 and len(OWN_SITES) == 47,
                   f'strip inventory changed: {CODE_BYTES} bytes/{len(OWN_SITES)} sites')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned executable image identity changed')
    cases = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = plane_checks = 0
    for case in cases:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
            plane_checks += row['plane_checks']
        gc.collect()
    oracle_require(sites == OWN_SITES,
                   f'native site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
                   f'native edge union differs: missing={sorted(static_edges()-edges)}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: 'df-set-lodsw-and-stosb',
        2: 'df-set-lodsw-and-stosb',
        3: 'source-ds-is-incoming-cx',
        4: 'first-and-second-latch-reads',
        5: 'first-and-second-latch-reads',
        6: 'ordinary-vga-eight-rows',
        7: 'entry-if-clear-final-sti',
        8: 'mirror-overwrites-saved-ds',
    }
    mutations = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=True)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, case=name, completed=True,
                                  mismatch=str(error)))
        else:
            raise interactions.OracleFailure(
                f'entity-strip mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'entity-strip inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
        static_instruction_addresses=sorted(OWN_SITES),
        branch_edge_count=len(static_edges()),
        static_branch_edges=[list(e) for e in sorted(static_edges())],
        case_count=len(cases), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(edge) for edge in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        independent_plane_byte_checks=plane_checks, input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain=('DrawEntityTwoByteStrip 6F7B..6FE1. The core stops after STI and live '
                'POP DS before the actual RET; the adapter reads the live near-return word. '
                'The suite compares all RAM, 13 logical register roles plus IP, defined FLAGS, '
                'ordered RAM/VGA/OUT events and full VGA plane/latch/register state. Its '
                'independent replay checks each VGA plane byte with the configured write-mode '
                'equation and covers DF-sensitive LODSW/STOSB, literal +2Ah pitch, incoming-CX '
                'source segment, live saved CX/DS/RET, physical word wrap, SS mirrors and STI.')))
    print(f'PASS entity strip: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{plane_checks} plane-byte checks, {len(mutations)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-strip-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        rows, sites, edges = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
            static_instruction_addresses=sorted(OWN_SITES),
            branch_edge_count=len(static_edges()),
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=len(make_cases()), core_adapter_comparisons=len(rows),
            cases=rows, input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_bus_event_limit=MAX_EVENTS),
            domain='Original-only strip preflight; no native differential evidence.'))
        print(f'PASS original entity strip: {len(make_cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_strip.py [--original-only | --native-worker DIR HASHES]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-strip-native-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
