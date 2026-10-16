"""Bounded original/native checks for DrawEntityPointCloud (6E83..6F7A)."""
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
ENTRY, RET, END = 0x6E83, 0x6F7A, 0x6F7B
POINTS, COLORS, MASK_TABLE = 0x2788, 0x2778, 0x547C
ORIGIN, PAGE, DIRTY_BASE, POINT_COUNT = 0x1F76, 0x1F7A, 0x0026, 0x004D
CODE = IMAGE[ENTRY:END]
FLAGS = interactions.FLAGS
CF, PF, AF, ZF, SF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x200, 0x400, 0x800
MAX_INSTRUCTIONS, MAX_EVENTS = 600_000, 150_000
WORKER_SECONDS, PROCESS_MIB = 240, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-points-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-points-original-differential.json'
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
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES + ('continuation', 'status')]


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """A completed native comparison differs from the original."""


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


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def signed8(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def table_start(selector):
    return (POINTS + (((selector - 1) & 0xFF) * 0xA0)) & 0xFFFF


def dirty_offset(base, x, y):
    qx = (x - 0x10) & 0xFFFF
    qx = 0 if qx & 0x8000 else qx >> 3
    qy = y & 0xFFF8
    return (base + 1 + qx + qy + (qy << 2)) & 0xFFFF


def point_words(points):
    return [word & 0xFFFF for word in points]


def make_cases():
    """Focused fixtures for gates, live inputs, aliases and finite zero-count wrap."""
    specs = [
        ('ordinary-valid-pixel', dict(points=[0x0101], base_x=0x30, base_y=0x30,
                                      project=True)),
        ('signed-x-negative-skip', dict(points=[0x00FF], base_x=0x00, base_y=0x30)),
        ('signed-y-negative-skip', dict(points=[0x8001], base_x=0x30, base_y=0x30)),
        ('x-equal-150-skip', dict(points=[0], base_x=0x150, base_y=0x30)),
        ('y-equal-a0-skip', dict(points=[0], base_x=0x30, base_y=0xA0)),
        ('dirty-x-negative-clamp', dict(points=[0], base_x=0x0F, base_y=0x30,
                                         project=True)),
        ('signed-low-x-mutant-witness', dict(points=[0x00FF], base_x=0x00, base_y=0x30)),
        ('signed-high-y-mutant-witness', dict(points=[0xFF01], base_x=0x30, base_y=0x30)),
        ('swapped-axis-mutant-witness', dict(points=[0x0020], base_x=0x20, base_y=0x20)),
        ('sentinel-skips-one-point', dict(points=[0x1280, 0x0101], count=2,
                                          base_x=0x30, base_y=0x30,
                                          project=True)),
        ('live-color-second-pixel', dict(points=[0x0101, 0x0202], count=2,
                                         base_x=0x30, base_y=0x30,
                                         colors=bytes([0, 1, 2, 3] + [0] * 12),
                                         project=True)),
        ('live-color-provider-after-mask', dict(points=[0x0101, 0x0202], count=2,
                    base_x=0x30, base_y=0x30, provider='color-after-mask-out',
                    provider_color_index=2, provider_color=9)),
        ('live-mask-custom-byte', dict(points=[0x0004], base_x=0x30, base_y=0x30,
                                       masks=bytes([0x80, 0x40, 0x20, 0x10,
                                                    0x02, 0x04, 0x02, 0x01]))),
        ('live-count-after-vga-setup', dict(points=[0x0101, 0x0202], count=1,
                    base_x=0x30, base_y=0x30, provider='count-after-setup',
                    provider_count=2)),
        ('live-next-point-after-first-read', dict(points=[0x1280, 0x1280], count=2,
                    base_x=0x30, base_y=0x30, provider='future-point',
                    provider_point=0x0202)),
        ('live-page-after-dirty-write', dict(points=[0x0101], base_x=0x30, base_y=0x30,
                    page=0, provider='page-after-dirty-write', provider_page=0x0100)),
        ('dirty-store-aliases-inner-saved-si', dict(points=[0], base_x=0x20, base_y=0x20,
                    dirty_alias=True, sp=0x8000)),
        ('two-hit-color-and-full-count', dict(points=[(i % 0x20) | (((i % 0x20) + 1) << 8)
                                                        for i in range(0xFF)],
                    count=0xFF, base_x=0x40, base_y=0x30)),
        ('selector-zero-wraps-table', dict(selector=0, points=[0x0101],
                                           base_x=0x30, base_y=0x30)),
        ('selector-ff-wraps-table', dict(selector=0xFF, points=[0x0101],
                                         base_x=0x30, base_y=0x30)),
        ('record-and-table-share-ds-ss', dict(ds=0x3500, ss=0x3500, points=[0x0101],
                                              base_x=0x30, base_y=0x30)),
        ('record-word-crosses-physical-wrap', dict(ds=0xFFFF, si=0x000F,
                    points=[0x0101], base_x=0x30, base_y=0x30)),
        ('outer-ret-word-crosses-physical-wrap', dict(ss=0xFFFF, sp=0x000F,
                    points=[0x0101], base_x=0x30, base_y=0x30)),
        ('outer-ret-overwritten-by-live-mask-mirror', dict(sp=0x000E,
                    points=[0x0101], base_x=0x30, base_y=0x30)),
        ('vga-data-segment-source', dict(ds=0xA000, vga=True,
                    points=[0x0101], base_x=0x30, base_y=0x30)),
        ('vga-stack-mirrors-and-dirty-map', dict(ss=0xA000, vga=True,
                    points=[0x0101], base_x=0x30, base_y=0x30)),
        ('entry-if-set-cli-pixel-phase', dict(points=[0x0101], base_x=0x30,
                    base_y=0x30, flags=0x0AD7, project=True)),
        ('entry-if-clear-no-pixel', dict(points=[0x00FF], base_x=0x00,
                    base_y=0x30, flags=0x08D7)),
        ('df-clear-pixel', dict(points=[0x0202], base_x=0x30, base_y=0x30,
                                flags=0x0AD7, project=True)),
        ('df-set-pixel', dict(points=[0x0202], base_x=0x30, base_y=0x30,
                              flags=0x0ED7, project=True)),
        ('point-count-zero-full-65536-scan', dict(count=0, points=[], selector=1,
                    zero_full=True, base_x=0x10, base_y=0x70, vga=False, si=0x0028,
                    value=0x0080, view_x=0x1280, record_y=0x0080,
                    dirty_base=0x8080, origin=0x8080, page=0x8080,
                    masks=bytes([0x80] * 8), colors=bytes([0x80] * 16))),
    ]
    rows = []
    for index, (name, fields) in enumerate(specs):
        row = dict(name=name, seed=0x6E8300 + index, ds=0x3500, ss=0x5000,
                   es=0x6200, si=0x0100, sp=0x9000, selector=1, count=None,
                   points=[0x0101], base_x=0x30, base_y=0x30, view_x=0x0100,
                   dirty_base=0x6000, origin=0x0230, page=0x0010,
                   masks=bytes([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]),
                   colors=bytes([0x01, 0x02, 0x04, 0x08] + [0] * 12),
                   flags=0x0AD7, return_word=0xE000 | index, vga=True,
                   provider=None, project=False, zero_full=False,
                   provider_count=2, provider_point=0x0202,
                   provider_color_index=2, provider_color=9, provider_page=0x0100,
                   dirty_alias=False, value=0xBEEF)
        row.update(fields)
        if row['count'] is None:
            row['count'] = len(row['points'])
        rows.append(row)
    oracle_require(len(rows) == 31, f'entity-points fixture count changed: {len(rows)}')
    return rows


def configured_vga(seed):
    device = MinimapVga(0x6E83 ^ seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
    device.gc[4] = 0
    device.gc[8] = 0xFF
    device.gc[6] = 0x05
    return device


def setup(case):
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = (LOAD << 4) & MASK
    first = min(len(loaded), SIZE - image_base)
    memory[image_base:image_base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = configured_vga(case['seed']) if case['vga'] else None
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    flags = (case['flags'] | 2) & FLAGS
    regs.update(cs=LOAD, ip=ENTRY, ds=case['ds'], es=case['es'], ss=case['ss'],
                si=case['si'], sp=case['sp'], flags=flags)
    ds, si = regs['ds'], regs['si']

    if case['zero_full']:
        base = physical(ds, 0)
        for offset in range(0, 0x10000, 2):
            address = (base + offset) & MASK
            memory[address] = 0x80
            memory[(address + 1) & MASK] = 0
    else:
        start = table_start(case['selector'])
        count = case['count']
        for index in range(max(count, len(case['points']))):
            word = case['points'][index] if index < len(case['points']) else 0x0080
            put16(memory, ds, start + index * 2, word, device)

    # Per-record fields and live tables are written after the source bank so
    # intentional DS/table/record aliases remain observable in source order.
    view_x = case['view_x']
    record_x = (view_x + case['base_x'] - 0x10) & 0xFFFF
    record_y = case.get('record_y', (case['base_y'] + 0x10) & 0xFFFF)
    if case['zero_full']:
        record_x = view_x
    put16(memory, ds, 0, view_x, device)
    put16(memory, ds, si, record_x, device)
    put16(memory, ds, (si + 2) & 0xFFFF, record_y, device)
    put8(memory, ds, (si + 0x28) & 0xFFFF, case['selector'], device)
    put8(memory, ds, POINT_COUNT, case['count'], device)
    put16(memory, ds, DIRTY_BASE, case['dirty_base'], device)
    put16(memory, ds, ORIGIN, case['origin'], device)
    put16(memory, ds, PAGE, case['page'], device)
    for index, value in enumerate(case['masks']):
        put8(memory, ds, MASK_TABLE + index, value, device)
    for index, value in enumerate(case['colors']):
        put8(memory, ds, COLORS + index, value, device)

    if case['zero_full']:
        # The sole nonsentinel word preserves the record's selector byte. Its
        # signed Y delta rejects the point after exercising the inner path.
        put16(memory, ds, (si + 0x28) & 0xFFFF, 0x8001, device)
    if case['dirty_alias']:
        x = case['base_x'] + signed8(case['points'][0] & 0xFF)
        y = case['base_y'] + signed8((case['points'][0] >> 8) & 0xFF)
        # The temporary outer AX has already been POPped before the inner frame.
        saved_si = (case['sp'] - 12) & 0xFFFF
        alias_base = (saved_si - 1 - ((max(0, x - 0x10) >> 3)) -
                      ((y & 0xFFF8) * 5)) & 0xFFFF
        put16(memory, ds, DIRTY_BASE, alias_base, device)

    put16(memory, regs['ss'], regs['sp'], case['return_word'], device)
    return memory, regs, device


class Access(interactions.Access):
    """Bounded word-port and live-table providers for the point-cloud scope."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0
        self.start = table_start(case['selector'])
        self.dirty_trigger = None
        if case.get('provider') == 'page-after-dirty-write' and case['points']:
            point = case['points'][0]
            x = case['base_x'] + signed8(point & 0xFF)
            y = case['base_y'] + signed8(point >> 8)
            self.dirty_trigger = physical(regs['ss'], dirty_offset(
                case['dirty_base'], x, y))

    def provider_write(self, address, value):
        address &= MASK
        value &= 0xFF
        if self.device and VGA_BASE <= address < VGA_END:
            self.device.planes[self.device.gc[4] & 3][address - VGA_BASE] = value
            self.memory[address] = value
            if self.mirror:
                self.mirror(address, value)
        else:
            self.store(address, value)

    def provider_word(self, segment, offset, value):
        address = physical(segment, offset)
        self.provider_write(address, value)
        self.provider_write(address + 1, value >> 8)

    def _provider(self, kind, address):
        case = self.case
        effect = case.get('provider')
        if effect == 'count-after-setup' and kind == 'read' and \
                address == physical(self.regs['ds'], POINT_COUNT) and \
                self.out_count >= 4 and 'count' not in self.used:
            self.provider_write(address, case['provider_count'])
            self.used.add('count')
        elif effect == 'future-point' and kind == 'read' and \
                address == physical(self.regs['ds'], self.start + 1) and \
                'future-point' not in self.used:
            self.provider_word(self.regs['ds'], self.start + 2,
                               case['provider_point'])
            self.used.add('future-point')
        elif effect == 'page-after-dirty-write' and kind == 'write' and \
                address == self.dirty_trigger and 'page' not in self.used:
            self.provider_word(self.regs['ds'], PAGE, case['provider_page'])
            self.used.add('page')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        self._provider(kind, address & MASK)
        return super().access(kind, address, flags, mask, value)

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('entity-points bus callback budget exhausted')
        self.out_count += 1
        if self.device:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        case = self.case
        if case.get('provider') == 'color-after-mask-out' and \
                self.out_count == 5 and 'color' not in self.used:
            index = case['provider_color_index']
            self.provider_write(physical(self.regs['ds'], COLORS + index),
                                case['provider_color'])
            self.used.add('color')


def independent_projection(case, initial_memory, initial_device):
    """Independent pixel/dirty projection for nonalias, provider-free cases."""
    oracle_require(case['project'] and case['provider'] is None and
                   case['ss'] != case['ds'] and case['ss'] != 0xA000,
                   case['name'] + ': invalid independent-projection fixture')
    memory = bytearray(initial_memory)
    device = copy.deepcopy(initial_device)
    for port, value in ((0x3C4, 0x0F02), (0x3CE, 0x0F01),
                        (0x3CE, 0x0005), (0x3CE, 0x0003)):
        device.out(port, value, 0)

    count = case['count']
    source = table_start(case['selector'])
    view_x = get16(memory, case['ds'], 0)
    record_x = get16(memory, case['ds'], case['si'])
    record_y = get16(memory, case['ds'], (case['si'] + 2) & 0xFFFF)
    base_x = (record_x - view_x + 0x10) & 0xFFFF
    base_y = (record_y - 0x10) & 0xFFFF
    dirty_base = get16(memory, case['ds'], DIRTY_BASE)
    origin = get16(memory, case['ds'], ORIGIN)
    page = get16(memory, case['ds'], PAGE)
    dirty_addresses = set()
    pixel_count = 0

    for index in range(count):
        word = get16(memory, case['ds'], (source + index * 2) & 0xFFFF)
        low = word & 0xFF
        if low == 0x80:
            continue
        x = (base_x + signed8(low)) & 0xFFFF
        y = (base_y + signed8(word >> 8)) & 0xFFFF
        if x & 0x8000 or y & 0x8000 or x >= 0x150 or y >= 0xA0:
            continue

        dirty = dirty_offset(dirty_base, x, y)
        dirty_address = physical(case['ss'], dirty)
        memory[dirty_address] = 1
        dirty_addresses.add(dirty_address)

        pixel_offset = ((0x2C * y) + (x >> 3) + origin + page) & 0xFFFF
        target = physical(0xA000, pixel_offset)
        mask_byte = get8(memory, case['ds'], MASK_TABLE + (x & 7))
        color = get8(memory, case['ds'], COLORS + (count - index) % 16)
        device.out(0x3CE, ((mask_byte << 8) | 8) & 0xFFFF, 0)
        device.out(0x3CE, (color << 8) & 0xFFFF, 0)
        device.read(memory, target, 0)
        device.write(memory, target, mask_byte, 0)
        pixel_count += 1

    return dict(memory=bytes(memory), device=device,
                dirty_addresses=sorted(dirty_addresses), pixel_count=pixel_count)


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
            raise error_type(f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                             f'under {want[4]:04X}')


def compare_devices(label, actual, expected, error_type):
    if actual is None or expected is None:
        if actual is not expected:
            raise error_type(label + ': VGA device presence differs')
        return
    if actual.state() != expected.state():
        raise error_type(label + ': VGA plane/latch/register state differs')
    left, right = [event[:3] for event in actual.trace], [event[:3] for event in expected.trace]
    if left != right:
        raise error_type(label + ': VGA trace differs')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-points-m{mutation}.dll',
                     mutation, 'entity_points')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_draw_entity_point_cloud_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_draw_entity_point_cloud_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core, null_bus=False):
        access = Access(case, memory, regs, device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

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
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in REG_NAMES},
                    events=access.events, used=access.used, device=device,
                    status=status, continuation=continuation)


def run_original(case, memory, regs, device, *, core):
    return interactions.original(case, memory, regs, device, core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS, access_factory=Access,
        instruction_limit=MAX_INSTRUCTIONS)


def compare_case(native, case, *, core, null_bus=False):
    initial_memory, initial_regs, initial_device = setup(case)
    expected = run_original(case, bytearray(initial_memory), dict(initial_regs),
                            copy.deepcopy(initial_device), core=core)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    oracle_require(expected['status'] == 0, label + ': original stopped abnormally')
    oracle_require(expected['regs']['cs'] == initial_regs['cs'], label + ': CS changed')
    if core:
        oracle_require(expected['continuation'] == RET and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core did not stop before RET with balanced SP')
    else:
        oracle_require(expected['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter did not consume its live RET word')
    if case['project']:
        projection = independent_projection(case, initial_memory, initial_device)
        for address in projection['dirty_addresses']:
            oracle_require(expected['memory'][address] == 1,
                           label + f': projected dirty byte {address:05X} is not set')
        oracle_require(expected['device'].planes == projection['device'].planes,
                       label + ': independent full-plane projection differs')
    else:
        projection = None
    if case['zero_full']:
        oracle_require(expected['steps'] >= 65_536 * 8,
                       label + ': did not execute the complete zero-count scan')
        oracle_require(expected['regs']['cx'] == 0 and
                       expected['regs']['bx'] == table_start(case['selector']),
                       label + ': final CX/BX does not establish 65,536 iterations')
    if case['dirty_alias']:
        oracle_require(expected['regs']['si'] == ((initial_regs['si'] & 0xFF00) | 1),
                       label + ': dirty write did not alter actual saved SI')
    if case.get('provider'):
        provider_names = {'count-after-setup': 'count',
                          'future-point': 'future-point',
                          'color-after-mask-out': 'color',
                          'page-after-dirty-write': 'page'}
        expected_used = {provider_names[case['provider']]}
        oracle_require(expected['used'] == expected_used,
                       label + f': provider did not fire: {expected["used"]}')

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
        require(not actual['events'], label + ': null-bus call reported callback events')
    row = dict(name=case['name'], boundary='core' if core else 'adapter',
               sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
               edges=sorted([src, dst] for scope, src, dst in expected['edges']
                            if scope == 'main'),
               events=len(expected['events']), steps=expected['steps'],
               provider_used=sorted(expected['used']))
    if projection is not None:
        row['independent_projection'] = dict(pixel_writes=projection['pixel_count'],
                                             dirty_addresses=projection['dirty_addresses'])
    if case['zero_full']:
        row['zero_count_proof'] = dict(iterations=65_536,
            final_cx=expected['regs']['cx'], final_bx=expected['regs']['bx'])
    return row


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
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/entity-display.md', 'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/regions.json',
        'metadata/inputs.json', 'metadata/hints.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/adlib-symbols.json',
        'metadata/adlib-regions.json', 'metadata/adlib-encodings.json',
        'metadata/tandysnd-symbols.json', 'metadata/tandysnd-regions.json',
        'metadata/tandysnd-encodings.json', 'metadata/pcspeaker-symbols.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json',
        'src/program.asm', 'src/image_tail.asm', 'src/entity_points.asm',
        'src/game_code_late_after_entities.asm',
        'c/entity_points.c', 'c/entity_points.h', 'c/regs.h', 'c/special_blit.h',
        'c/lemmings_sym.h', 'c/pcspeaker_sym.h', 'c/sound_latches_sym.h',
        'tests/entity_points.py', 'tests/entity_interactions.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/unpack.py', 'tools/resources.py', 'tools/difftest.py',
        'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing entity-points hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(cases, before):
    oracle_require(before == input_hashes(), 'entity-points inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in cases:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core=core)
            label = case['name'] + (' core' if core else ' adapter')
            oracle_require(expected['status'] == 0, label + ': original stopped abnormally')
            if core:
                oracle_require(expected['continuation'] == RET and
                               expected['regs']['sp'] == regs['sp'],
                               label + ': core boundary/SP mismatch')
            else:
                oracle_require(expected['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
                               label + ': adapter RET/SP mismatch')
            if case['project']:
                projection = independent_projection(case, initial, device)
                for address in projection['dirty_addresses']:
                    oracle_require(expected['memory'][address] == 1,
                                   label + f': projected dirty byte {address:05X} is not set')
                oracle_require(expected['device'].planes == projection['device'].planes,
                               label + ': independent full-plane projection differs')
            if case['zero_full']:
                oracle_require(expected['steps'] >= 65_536 * 8,
                               label + ': did not execute the complete zero-count scan')
                oracle_require(expected['regs']['cx'] == 0 and
                               expected['regs']['bx'] == table_start(case['selector']),
                               label + ': final CX/BX does not establish 65,536 iterations')
            if case['dirty_alias']:
                oracle_require(expected['regs']['si'] == ((regs['si'] & 0xFF00) | 1),
                               label + ': dirty write did not alter actual saved SI')
            if case.get('provider'):
                provider_names = {'count-after-setup': 'count',
                                  'future-point': 'future-point',
                                  'color-after-mask-out': 'color',
                                  'page-after-dirty-write': 'page'}
                oracle_require(expected['used'] == {provider_names[case['provider']]},
                               label + ': requested provider did not fire')
            if case['name'] == 'entry-if-clear-no-pixel':
                oracle_require(not expected['regs']['flags'] & IF,
                               label + ': early return unexpectedly set IF')
                oracle_require(not any(VGA_BASE <= event[1] < VGA_END
                                       for event in expected['events']
                                       if event[0] in ('read', 'write')),
                               label + ': early return performed an ES pixel access')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            own_edges = {(src, dst) for scope, src, dst in expected['edges'] if scope == 'main'}
            row = dict(name=case['name'], boundary='core' if core else 'adapter',
                       sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                       steps=expected['steps'], events=len(expected['events']),
                       provider_used=sorted(expected['used']))
            if case['project']:
                row['independent_projection'] = dict(
                    pixel_writes=projection['pixel_count'],
                    dirty_addresses=projection['dirty_addresses'])
            if case['zero_full']:
                row['zero_count_proof'] = dict(iterations=65_536,
                    final_cx=expected['regs']['cx'], final_bx=expected['regs']['bx'])
            rows.append(row)
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    expected_edges = static_edges()
    oracle_require(sites == OWN_SITES,
        f'original executed-site union differs: missing={sorted(OWN_SITES-sites)} '
        f'extra={sorted(sites-OWN_SITES)}')
    oracle_require(edges == expected_edges,
        f'original branch outcomes differ: missing={sorted(expected_edges-edges)} '
        f'extra={sorted(edges-expected_edges)}')
    oracle_require(before == input_hashes(), 'entity-points inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'entity-points inputs changed before native worker')
    oracle_require(END - ENTRY == 248 and CODE_BYTES == 248 and len(OWN_SITES) == 110,
                   f'6E83 static scope changed: {END-ENTRY} bytes/{CODE_BYTES} bytes/'
                   f'{len(OWN_SITES)} sites')
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

    # The bus is optional for ordinary RAM-only calls; no device/provider side
    # effect is claimed in these four comparisons.
    for name in ('ordinary-valid-pixel', 'signed-x-negative-skip'):
        case = dict(next(item for item in cases if item['name'] == name),
                    vga=False, provider=None, project=False)
        for core in (True, False):
            compare_case(baseline, case, core=core, null_bus=True)

    oracle_require(sites == OWN_SITES,
        f'native compared-site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
        f'native compared-edge union differs: missing={sorted(static_edges()-edges)}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: 'signed-low-x-mutant-witness',
        2: 'signed-high-y-mutant-witness',
        3: 'swapped-axis-mutant-witness',
        4: 'dirty-store-aliases-inner-saved-si',
        5: 'live-color-second-pixel',
        6: 'live-mask-custom-byte',
        7: 'entry-if-set-cli-pixel-phase',
        8: 'point-count-zero-full-65536-scan',
        9: 'sentinel-skips-one-point',
        10: 'live-page-after-dirty-write',
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
                f'entity-points mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'entity-points inputs changed during native campaign')
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
        domain=('DrawEntityPointCloud 6E83..6F7A. The logical core stops before RET; '
                'the register adapter consumes the live SS:SP word. Comparisons cover '
                'all RAM, thirteen logical register roles plus IP, instruction-defined '
                'FLAGS, ordered RAM/VGA callbacks, VGA planes/latches/registers, live '
                'point/color/mask/page reads, dirty-map writes, stack aliases and the '
                'complete count-zero 65,536-iteration scan.')))
    print(f'PASS entity points: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-points-original-', parent=BUILD) as directory:
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
            static_branch_edges=[list(edge) for edge in sorted(static_edges())],
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=len(make_cases()), core_adapter_comparisons=len(rows), cases=rows,
            input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_callback_event_limit=MAX_EVENTS),
            domain='Original-only entity point-cloud preflight; no native evidence.'))
        print(f'PASS original entity points: {len(make_cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_points.py [--original-only | --native-worker DIR HASHES]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-points-native-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
