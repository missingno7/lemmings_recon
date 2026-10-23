"""Bounded differential tests for DrawEntityMinimapPixel (6FE2..706E)."""
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
LOAD = 0x1010
ENTRY, RET, END = 0x6FE2, 0x706E, 0x706F
TABLE, ORIGIN = 0x547C, 0x1F76
MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
CODE = IMAGE[ENTRY:END]
FLAGS = interactions.FLAGS
CF, PF, AF, ZF, SF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x200, 0x400, 0x800
ARITH = CF | PF | AF | ZF | SF | OF
LOGIC = CF | PF | ZF | SF | OF
TF = 0x100
MAX_INSTRUCTIONS, MAX_EVENTS = 300, 128
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-minimap-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-minimap-original-differential.json'

DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(CODE, ENTRY)}
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
RESULT_FIELDS = {machine: role for role, machine in REG_FIELDS.items()}

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


def put8(memory, segment, offset, value, device=None):
    address = physical(segment, offset)
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[device.gc[4] & 3][address - VGA_BASE] = value


def put16(memory, segment, offset, value, device=None):
    address = physical(segment, offset)
    for delta, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
        target = (address + delta) & MASK
        memory[target] = byte
        if device is not None and VGA_BASE <= target < VGA_END:
            device.planes[device.gc[4] & 3][target - VGA_BASE] = byte


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def szp16(value):
    value &= 0xFFFF
    out = 0
    if (value & 0xFF).bit_count() % 2 == 0:
        out |= PF
    if value == 0:
        out |= ZF
    if value & 0x8000:
        out |= SF
    return out


def sub_flags(flags, left, right):
    result = (left - right) & 0xFFFF
    out = szp16(result)
    if (left & 0xFFFF) < (right & 0xFFFF):
        out |= CF
    if ((left ^ right ^ result) & AF) != 0:
        out |= AF
    if ((left ^ right) & (left ^ result) & 0x8000) != 0:
        out |= OF
    return ((flags & ~ARITH) | out) & 0xFFFF


def add_flags(flags, left, right):
    wide = (left & 0xFFFF) + (right & 0xFFFF)
    result = wide & 0xFFFF
    out = szp16(result)
    if wide > 0xFFFF:
        out |= CF
    if ((left ^ right ^ result) & AF) != 0:
        out |= AF
    if ((~(left ^ right) & (left ^ result)) & 0x8000) != 0:
        out |= OF
    return ((flags & ~ARITH) | out) & 0xFFFF


def shr1(value, flags):
    value &= 0xFFFF
    result = value >> 1
    out = szp16(result)
    if value & 1:
        out |= CF
    if value & 0x8000:
        out |= OF
    flags = (flags & ~(CF | PF | ZF | SF | OF)) | out
    return result, flags & 0xFFFF


def and_flags(flags, result):
    out = szp16(result)
    return ((flags & ~LOGIC) | out) & 0xFFFF


def make_cases():
    """Keep each case tied to a boundary, alias, device path or mutant."""
    specs = [
        ('y-valid-lower', dict(x=0x1234, y=0x0020)),
        ('y-valid-upper', dict(x=0x2A55, y=0x00AF)),
        ('y-upper-equal-early', dict(x=0x1111, y=0x00B0)),
        ('y-upper-positive-early', dict(x=0xABCD, y=0x00B1)),
        ('y-large-positive-early', dict(x=0xFFFF, y=0x7FFF)),
        ('y-underflow-js', dict(x=0x4A57, y=0x001F)),
        ('y-wrapped-positive-row', dict(x=0x8317, y=0x8000)),
        ('y-wrapped-row-last', dict(x=0x701F, y=0x801F)),
        ('y-wrapped-negative-js', dict(x=0xA513, y=0x8020)),
        ('y-ffff-negative-js', dict(x=0xEC29, y=0xFFFF)),
    ]
    for index in range(8):
        specs.append((f'x-mask-index-{index}', dict(x=index << 4, y=0x0041,
                                                    origin=0x1021 + index)))
    specs.extend((
        ('x-shift-three-vs-four', dict(x=0x0080, y=0x0031, origin=0x0F03)),
        ('origin-add-and-si-wrap', dict(x=0x7FFF, y=0x8000, origin=0xF91B)),
        ('table-custom-mask-byte', dict(x=0x0050, y=0x0042,
                                        table_bytes=bytes.fromhex('80 40 20 10 08 B6 02 01'))),
        ('table-provider-before-read', dict(x=0x0020, y=0x0050,
                    table_bytes=bytes.fromhex('80 40 20 10 08 04 02 01'),
                    provider='table-after-out', provider_after_out=2,
                    provider_value=0x36)),
        ('origin-provider-after-coordinate-read', dict(x=0x0030, y=0x0053,
                    origin=0x0001, provider='origin-after-record-read',
                    provider_origin=0x8F04)),
        ('live-pop-from-ss-0002', dict(x=0x0060, y=0x0044, sp=0x0004,
                                       table_bytes=bytes.fromhex('11 22 33 44 55 66 77 88'))),
        ('live-ret-from-ss-0008-mirror', dict(x=0x0027, y=0x0030,
                                               sp=0x0008, return_word=0x9876)),
        ('table-alias-ss-000c', dict(x=0, y=0x0038, ds=0x3000, ss=0x3547,
                                    table_bytes=bytes.fromhex('AA 40 20 10 08 04 02 01'))),
        ('record-offset-wrap', dict(x=0x5A3D, y=0x0020, di=0xFFFE)),
        ('physical-source-word-wrap', dict(x=0xA1B2, y=0x0077,
                                           ds=0xFFFF, di=0x000F)),
        ('physical-return-word-wrap', dict(x=0x11A5, y=0x0040,
                                           ss=0xFFFF, sp=0x000F,
                                           return_word=0xBEEF)),
        ('early-if-clear-cmp', dict(x=0x4444, y=0x00B0, iflag=False)),
        ('early-if-clear-sub', dict(x=0x3333, y=0x001F, iflag=False)),
        ('normal-if-set-cli-phase', dict(x=0xA2B3, y=0x0064, iflag=True)),
        ('df-clear', dict(x=0xD715, y=0x0020, df=False)),
        ('df-set', dict(x=0x69A1, y=0x0062, df=True)),
        ('missing-ss-0008-mirror-witness', dict(x=0x11B0, y=0x0033,
                                                sentinel8=0x5A)),
        ('vga-ds-record-and-table', dict(x=0x04B5, y=0x0055, ds=0xA000,
                                         vga=True,
                                         table_bytes=bytes.fromhex('10 21 32 43 54 C6 76 87'))),
        ('vga-ss-mirrors-stack-ret', dict(x=0xB1C2, y=0x0047, ss=0xA000,
                                          sp=0x2000, vga=True,
                                          return_word=0xA55A)),
        ('vga-source-and-stack', dict(x=0x2037, y=0x8000, ds=0xA000,
                                      ss=0xA000, sp=0x3000, vga=True,
                                      table_bytes=bytes.fromhex('80 31 42 53 64 75 86 97'),
                                      origin=0x12A7)),
        ('no-device-null-bus-domain', dict(x=0x7195, y=0x0023, vga=False)),
        ('ram-only-null-bus-domain', dict(x=0x0A67, y=0x00AF, vga=False,
                                          origin=0xFE31, df=True)),
    ))
    rows = []
    for seed, (name, fields) in enumerate(specs):
        row = dict(name=name, seed=seed, x=0x1375, y=0x0031,
                   di=0x4000, ds=DATA_SEGMENT, ss=0x5000, sp=0x9000,
                   origin=0x2143, return_word=0xE000 | seed,
                   table_bytes=None, flags=0x0ED7, iflag=None, df=None,
                   vga=True, provider=None, provider_after_out=0,
                   provider_value=0, provider_origin=0, sentinel8=None)
        row.update(fields)
        rows.append(row)
    oracle_require(30 <= len(rows) <= 45,
                   f'entity-minimap fixture count out of scope: {len(rows)}')
    return rows


def configured_vga(seed):
    device = MinimapVga(0x6FE2 ^ seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = device.gc[1] = device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[8] = 0xFF
    device.gc[6] = 0x05
    return device


def setup(case):
    rng = random.Random(0x6FE2 + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = (LOAD << 4) & MASK
    first = min(len(loaded), SIZE - image_base)
    memory[image_base:image_base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = configured_vga(case['seed']) if case['vga'] else None
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    flags = ((case['flags'] | 2) & FLAGS) & ~TF
    if case['iflag'] is not None:
        flags = (flags | IF) if case['iflag'] else (flags & ~IF)
    if case['df'] is not None:
        flags = (flags | DF) if case['df'] else (flags & ~DF)
    regs.update(cs=LOAD, ip=ENTRY, ds=case['ds'], ss=case['ss'],
                es=0x6C20 + case['seed'], sp=case['sp'], di=case['di'],
                flags=flags)

    if case['table_bytes'] is None and regs['ds'] == DATA_SEGMENT:
        actual = bytes(memory[physical(regs['ds'], TABLE + index)]
                       for index in range(8))
        oracle_require(actual == MASKS,
                       case['name'] + ': pinned DS:547C bytes changed')
        if device is not None and physical(regs['ds'], TABLE) >= VGA_BASE:
            for index, value in enumerate(MASKS):
                put8(memory, regs['ds'], TABLE + index, value, device)
    else:
        table = case['table_bytes'] or MASKS
        oracle_require(len(table) == 8, case['name'] + ': mask table must be eight bytes')
        for index, value in enumerate(table):
            put8(memory, regs['ds'], TABLE + index, value, device)

    put16(memory, regs['ds'], ORIGIN, case['origin'], device)
    put16(memory, regs['ds'], regs['di'], case['x'], device)
    put16(memory, regs['ds'], (regs['di'] + 2) & 0xFFFF, case['y'], device)
    if case['sentinel8'] is not None:
        put8(memory, regs['ss'], 8, case['sentinel8'], device)
    put16(memory, regs['ss'], regs['sp'], case['return_word'], device)
    return memory, regs, device


class Access(interactions.Access):
    """Bounded RAM/VGA bus plus the two declared live-read providers."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def _provider_write(self, address, value):
        address &= MASK
        value &= 0xFF
        if self.device and VGA_BASE <= address < VGA_END:
            self.device.planes[self.device.gc[4] & 3][address - VGA_BASE] = value
            self.memory[address] = value
            if self.mirror:
                self.mirror(address, value)
        else:
            self.store(address, value)

    def _provider(self, kind, address):
        super()._provider(kind, address)
        y_address = physical(self.regs['ds'], (self.regs['di'] + 2) & 0xFFFF)
        if (self.case.get('provider') == 'origin-after-record-read' and
                kind == 'read' and address == y_address and 'origin' not in self.used):
            value = self.case['provider_origin']
            origin_address = physical(self.regs['ds'], ORIGIN)
            self._provider_write(origin_address, value)
            self._provider_write((origin_address + 1) & MASK, value >> 8)
            self.used.add('origin')

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('entity-minimap event budget exhausted')
        self.out_count += 1
        if self.device:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        if (self.case.get('provider') == 'table-after-out' and
                self.out_count == self.case['provider_after_out'] and
                'table' not in self.used):
            index = (self.case['x'] >> 4) & 7
            address = physical(self.regs['ds'], TABLE + index)
            self._provider_write(address, self.case['provider_value'])
            self.used.add('table')


def independent(case, initial_memory, initial_regs, initial_device, *, core):
    """Replay the short instruction sequence with independent ordered effects."""
    memory = bytearray(initial_memory)
    device = copy.deepcopy(initial_device)
    state = dict(initial_regs)
    used = set()
    flags = state['flags']
    out_count = 0

    def write_phys(address, value):
        address &= MASK
        value &= 0xFF
        if device and VGA_BASE <= address < VGA_END:
            device.write(memory, address, value, flags)
        else:
            memory[address] = value

    def provider_write(address, value):
        address &= MASK
        value &= 0xFF
        if device and VGA_BASE <= address < VGA_END:
            device.planes[device.gc[4] & 3][address - VGA_BASE] = value
            memory[address] = value
        else:
            memory[address] = value

    def before_read(address):
        y_address = physical(state['ds'], (state['di'] + 2) & 0xFFFF)
        if (case.get('provider') == 'origin-after-record-read' and
                address == y_address and 'origin' not in used):
            value = case['provider_origin']
            origin_address = physical(state['ds'], ORIGIN)
            provider_write(origin_address, value)
            provider_write((origin_address + 1) & MASK, value >> 8)
            used.add('origin')

    def read_phys(address):
        address &= MASK
        before_read(address)
        if device and VGA_BASE <= address < VGA_END:
            return device.read(memory, address, flags)
        return memory[address]

    def write_word(segment, offset, value):
        address = physical(segment, offset)
        write_phys(address, value)
        write_phys((address + 1) & MASK, value >> 8)

    def read_word(segment, offset):
        address = physical(segment, offset)
        return read_phys(address) | (read_phys((address + 1) & MASK) << 8)

    def output(port, value):
        nonlocal out_count
        out_count += 1
        if device:
            device.out(port, value, flags)
        if (case.get('provider') == 'table-after-out' and
                out_count == case['provider_after_out'] and 'table' not in used):
            index = (case['x'] >> 4) & 7
            provider_write(physical(state['ds'], TABLE + index),
                           case['provider_value'])
            used.add('table')

    def add_si(amount):
        nonlocal flags
        before = state['si']
        state['si'] = (before + amount) & 0xFFFF
        flags = add_flags(flags, before, amount)

    def mirror_and_out(offset, port, value):
        write_word(state['ss'], offset, value)
        output(port, value)

    y = read_word(state['ds'], (state['di'] + 2) & 0xFFFF)
    flags = sub_flags(flags, y, 0x00B0)
    state['ax'] = y
    if signed16(y) >= signed16(0x00B0):
        state['flags'] = flags
        state['ip'] = RET
        if not core:
            state['ip'] = read_word(state['ss'], state['sp'])
            state['sp'] = (state['sp'] + 2) & 0xFFFF
        return dict(memory=bytes(memory), regs=state, device=device, used=used,
                    path='cmp-early')

    row = (y - 0x20) & 0xFFFF
    flags = sub_flags(flags, y, 0x20)
    state['ax'] = row
    if row & 0x8000:
        state['flags'] = flags
        state['ip'] = RET
        if not core:
            state['ip'] = read_word(state['ss'], state['sp'])
            state['sp'] = (state['sp'] + 2) & 0xFFFF
        return dict(memory=bytes(memory), regs=state, device=device, used=used,
                    path='sub-early')

    row >>= 3
    product = row * 0x2C
    state['ax'] = product & 0xFFFF
    state['dx'] = (product >> 16) & 0xFFFF
    flags = (flags & ~(CF | OF)) | ((CF | OF) if product >> 16 else 0)
    state['si'] = state['ax']

    state['ax'] = read_word(state['ds'], state['di'])
    for _ in range(4):
        state['ax'], flags = shr1(state['ax'], flags)
    state['sp'] = (state['sp'] - 2) & 0xFFFF
    write_word(state['ss'], state['sp'], state['ax'])
    for _ in range(3):
        state['ax'], flags = shr1(state['ax'], flags)
    add_si(state['ax'])
    add_si(read_word(state['ds'], ORIGIN))
    add_si(0x2172)
    add_si(0x0002)
    add_si(0x002C)

    state['dx'], state['ax'] = 0x03C4, 0x0F02
    mirror_and_out(0x0008, state['dx'], state['ax'])
    state['dx'], state['ax'] = 0x03CE, 0x0200
    mirror_and_out(0x000A, state['dx'], state['ax'])
    state['ax'] = 0x0F01
    mirror_and_out(0x000C, state['dx'], state['ax'])
    state['ax'] = 0x0005
    mirror_and_out(0x0000, state['dx'], state['ax'])
    state['ax'] = 0x0003
    mirror_and_out(0x0002, state['dx'], state['ax'])
    state['es'] = 0xA000

    state['ax'] = read_word(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 0xFFFF
    state['bx'] = TABLE
    state['ax'] &= 7
    flags = and_flags(flags, state['ax'])
    before_bx = state['bx']
    state['bx'] = (state['bx'] + state['ax']) & 0xFFFF
    flags = add_flags(flags, before_bx, state['ax'])
    mask_byte = read_phys(physical(state['ds'], state['bx']))
    state['ax'] = ((mask_byte << 8) | 8)
    mirror_and_out(0x000E, state['dx'], state['ax'])

    flags &= ~IF
    target = physical(state['es'], state['si'])
    previous = read_phys(target)
    state['ax'] = (state['ax'] & 0xFF00) | previous
    if device is not None:
        oracle_require(VGA_BASE <= target < VGA_END,
                       case['name'] + ': ES pixel target escaped A000 aperture')
        oracle_require((device.gc[5] & 3) == 0 and device.gc[3] == 0 and
                       (device.seq[2] & 0x0F) == 0x0F,
                       case['name'] + ': expected VGA write-mode-0 setup was not programmed')
        latches = tuple(device.latches)
        bit_mask = device.gc[8]
        projected = []
        for plane in range(4):
            if device.gc[1] & (1 << plane):
                source = 0xFF if device.gc[0] & (1 << plane) else 0
            else:
                source = state['ax'] >> 8
            projected.append(((source & bit_mask) |
                              (latches[plane] & (~bit_mask & 0xFF))) & 0xFF)
    write_phys(target, state['ax'] >> 8)
    if device is not None:
        plane_offset = target - VGA_BASE
        for plane, expected_byte in enumerate(projected):
            oracle_require(device.planes[plane][plane_offset] == expected_byte,
                case['name'] + f': independent VGA plane {plane} write differs')
    flags |= IF

    state['flags'] = flags & 0xFFFF
    state['ip'] = RET
    if not core:
        state['ip'] = read_word(state['ss'], state['sp'])
        state['sp'] = (state['sp'] + 2) & 0xFFFF
    return dict(memory=bytes(memory), regs=state, device=device, used=used,
                path='pixel')


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
    offset = next(index for index, pair in enumerate(zip(actual, expected))
                  if pair[0] != pair[1])
    raise error_type(f'{label}: RAM at {offset:05X} is {actual[offset]:02X}/'
                     f'{expected[offset]:02X}')


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
            raise error_type(label + ': VGA device presence differs')
        return
    if actual.state() != expected.state():
        raise error_type(label + ': VGA planes/latches/register state differs')
    left = [event[:3] for event in actual.trace]
    right = [event[:3] for event in expected.trace]
    if left != right:
        raise error_type(label + ': VGA read/write/output trace differs')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-minimap-m{mutation}.dll',
                     mutation, 'entity_minimap')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_draw_entity_minimap_pixel_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_draw_entity_minimap_pixel_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core, null_bus=False):
        access = Access(case, memory, regs, device)

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
        bus_pointer = None if null_bus else ct.byref(bus)
        if core:
            call = Call(*(regs[REG_FIELDS[name]] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), bus_pointer)
            for role in CORE_NAMES:
                setattr(state, REG_FIELDS[role], getattr(result, role))
            state.ip = result.continuation
            status, continuation = result.status, result.continuation
        else:
            status = self.adapter(ram, ct.byref(state), bus_pointer)
            continuation = state.ip
        return dict(memory=bytes(memory), regs={name: getattr(state, name)
                                                for name in REG_NAMES},
                    events=access.events, used=access.used, device=device,
                    status=status, continuation=continuation)


def run_original(case, memory, regs, device, *, core):
    return interactions.original(case, memory, regs, device, core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        access_factory=Access, instruction_limit=MAX_INSTRUCTIONS)


def compare_case(native, case, *, core, null_bus=False):
    initial_memory, initial_regs, initial_device = setup(case)
    expected_model = independent(case, initial_memory, initial_regs,
                                 initial_device, core=core)
    expected = run_original(case, bytearray(initial_memory), dict(initial_regs),
                            copy.deepcopy(initial_device), core=core)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    oracle_require(expected['status'] == 0,
                   label + f': unexpected original boundary status {expected["status"]}')
    compare_regs(label + ' original/model', expected['regs'], expected_model['regs'],
                 FLAGS, interactions.OracleFailure)
    compare_memory(label + ' original/model', expected['memory'],
                   expected_model['memory'], interactions.OracleFailure)
    compare_devices(label + ' original/model', expected['device'],
                    expected_model['device'], interactions.OracleFailure)
    oracle_require(expected['used'] == expected_model['used'],
                   label + ': independent provider order differs')
    if case.get('provider'):
        marker = ('origin' if case['provider'] == 'origin-after-record-read'
                  else 'table')
        oracle_require(expected['used'] == {marker},
                       label + f': requested provider did not fire: {expected["used"]}')

    actual = native.run(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core, null_bus=null_bus)
    require(actual['status'] == 0, label + f': status {actual["status"]}')
    require(actual['continuation'] == expected['continuation'],
            label + f': continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    compare_regs(label, actual['regs'], expected['regs'], expected['flag_mask'], Mismatch)
    compare_memory(label, actual['memory'], expected['memory'], Mismatch)
    if not null_bus:
        compare_events(label, actual['events'], expected['events'], Mismatch)
        require(actual['used'] == expected['used'],
                label + f': provider transitions {actual["used"]}/{expected["used"]}')
        compare_devices(label, actual['device'], expected['device'], Mismatch)
    else:
        require(not actual['events'], label + ': null-bus native call reported events')
    if core:
        oracle_require(expected['regs']['ip'] == RET and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core did not stop before RET with balanced SP')
    else:
        oracle_require(expected['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter did not consume the actual RET word')
    return dict(name=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
                edges=sorted([src, dst] for scope, src, dst in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                provider_used=sorted(expected['used']), path=expected_model['path'])


def static_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if not ins.group(capstone.CS_GRP_JUMP):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat', 'metadata/oracle.json',
        'metadata/symbols.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/hints.json', 'metadata/toolchain-lock.json', 'src/program.asm',
        'src/entity_minimap.asm', 'src/entity_sprite_dispatch.asm', 'src/fixed_pattern_drawing.asm',
        'src/image_tail.asm',
        'c/entity_minimap.c', 'c/entity_minimap.h', 'c/regs.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'tests/entity_minimap.py',
        'tests/entity_interactions.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tools/resources.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/unpack.py',
        'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing entity-minimap hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(cases, before):
    oracle_require(before == input_hashes(), 'entity-minimap inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in cases:
        initial, regs, device = setup(case)
        for core in (True, False):
            model = independent(case, initial, regs, device, core=core)
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core=core)
            label = case['name'] + (' core' if core else ' adapter')
            oracle_require(expected['status'] == 0, label + ': original stopped abnormally')
            compare_regs(label + ' model', expected['regs'], model['regs'],
                         FLAGS, interactions.OracleFailure)
            compare_memory(label + ' model', expected['memory'], model['memory'],
                           interactions.OracleFailure)
            compare_devices(label + ' model', expected['device'], model['device'],
                            interactions.OracleFailure)
            oracle_require(expected['used'] == model['used'],
                           label + ': provider transitions differ')
            if case.get('provider'):
                marker = ('origin' if case['provider'] == 'origin-after-record-read'
                          else 'table')
                oracle_require(expected['used'] == {marker},
                               label + f': requested provider did not fire: {expected["used"]}')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            own_edges = {(src, dst) for scope, src, dst in expected['edges']
                         if scope == 'main'}
            rows.append(dict(name=case['name'], boundary='core' if core else 'adapter',
                             sites=sorted(own_sites), edges=[list(edge) for edge in sorted(own_edges)],
                             events=len(expected['events']), steps=expected['steps'],
                             path=model['path'], provider_used=sorted(expected['used'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == OWN_SITES,
        f'original executed-site union differs: missing={sorted(OWN_SITES-sites)} '
        f'extra={sorted(sites-OWN_SITES)}')
    expected_edges = static_edges()
    oracle_require(edges == expected_edges,
        f'original branch outcomes differ: missing={sorted(expected_edges-edges)} '
        f'extra={sorted(edges-expected_edges)}')
    oracle_require(before == input_hashes(), 'entity-minimap inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'entity-minimap inputs changed before native worker')
    oracle_require(CODE_BYTES == 141 and len(OWN_INS) == 58,
                   f'6FE2 static scope changed: {CODE_BYTES} bytes/{len(OWN_INS)} sites')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned executable image identity changed')
    cases = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in cases:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()

    # Repeat two ordinary-RAM cases with the optional bus pointer absent.
    for name in ('no-device-null-bus-domain', 'ram-only-null-bus-domain'):
        case = next(row for row in cases if row['name'] == name)
        for core in (True, False):
            compare_case(baseline, case, core=core, null_bus=True)
        gc.collect()

    oracle_require(sites == OWN_SITES,
        f'native comparison site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
        f'native comparison branch outcomes differ: missing={sorted(static_edges()-edges)}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: 'x-shift-three-vs-four',
        2: 'early-if-clear-cmp',
        3: 'normal-if-set-cli-phase',
        4: 'origin-add-and-si-wrap',
        5: 'missing-ss-0008-mirror-witness',
        6: 'y-wrapped-positive-row',
        7: 'live-pop-from-ss-0002',
        8: 'table-custom-mask-byte',
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
                f'entity-minimap mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'entity-minimap inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
        static_instruction_addresses=sorted(OWN_SITES),
        branch_edge_count=len(static_edges()),
        static_branch_edges=[list(edge) for edge in sorted(static_edges())],
        case_count=len(cases), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(edge) for edge in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after, null_bus_comparisons=4,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain=('DrawEntityMinimapPixel 6FE2..706E. The core stops before the actual '
                'near RET and the adapter reads live SS:SP. Comparisons include full RAM, '
                '13 logical registers plus IP, instruction-defined FLAGS, ordered RAM/VGA '
                'bus events, and all VGA planes/latches/registers. Independent ordered '
                'replay covers signed Y gates, wrapped row multiplication, X shifts and live '
                'stack pop, DrawingOrigin, PixelBitMasks, SS mirrors, CLI/STI and VGA latch '
                'read/write.')))
    print(f'PASS entity minimap: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-minimap-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        cases = make_cases()
        rows, sites, edges = original_campaign(cases, before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
            static_instruction_addresses=sorted(OWN_SITES),
            branch_edge_count=len(static_edges()), branch_edges=[list(e) for e in sorted(edges)],
            executed_instruction_addresses=sorted(sites), case_count=len(cases),
            core_adapter_comparisons=len(rows), cases=rows, input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_callback_event_limit=MAX_EVENTS),
            domain='Original-only DrawEntityMinimapPixel preflight; no native evidence.'))
        print(f'PASS original entity minimap: {len(cases)} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_minimap.py [--original-only | --native-worker DIR HASHES]')
    with temporary_build_directory(prefix='entity-minimap-native-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
