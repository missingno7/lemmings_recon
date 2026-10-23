"""Bounded differential checks for the two shifted entity-sprite siblings.

The 12-row body is 64D9..65D7 and the 13-row body is 65D8..66D6. Both cores
stop after their live POP DS and before the actual near RET; adapters consume
the caller's live SS:SP word.
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
SIZE, MASK = interactions.SIZE, interactions.MASK
FLAGS = interactions.FLAGS
DF, IF = 0x0400, 0x0200
ARITH = 0x08D5
ENTRY12, RET12, END12 = 0x64D9, 0x65D7, 0x65D8
ENTRY13, RET13, END13 = 0x65D8, 0x66D6, 0x66D7
SHIFT12_BOUNDARY, SHIFT13_BOUNDARY = 0x6538, 0x6637
LOAD = 0x1010
MAX_INSTRUCTIONS, MAX_EVENTS = 50000, 10000
WORKER_SECONDS, PROCESS_MIB = 240, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-sprite-shifted-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-sprite-shifted-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY12:END13], ENTRY12)}
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
PRODUCER_WITNESSES = None

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
    """Only completed native comparisons may count as mutation evidence."""


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


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def put16(memory, segment, offset, value):
    # A real physical word wraps at 1 MiB, independently of segment offset wrap.
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def seed_physical(memory, device, address, value):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        vga_offset = address - VGA_BASE
        # Make the selected read plane agree with the CPU-visible source byte.
        # Other planes retain distinct poison unless this is a destination.
        device.planes[device.gc[4] & 3][vga_offset] = value


def seed_word(memory, device, segment, offset, value):
    address = physical(segment, offset)
    seed_physical(memory, device, address, value)
    seed_physical(memory, device, address + 1, value >> 8)


def source_pattern(rows, seed):
    return [((0x8193 + index * 0x2D71 + seed * 0x0103) ^
             (0xA55A >> (index & 7))) & 0xFFFF
            for index in range(rows * 2)]


def mask_pattern(rows, seed):
    return [((0xF03D ^ (index * 0x197B) ^ (seed * 0x0311)) & 0xFFFF)
            for index in range(rows)]


def make_cases():
    """Focused shift, direction, live-stack, VGA and provider fixtures."""
    specs = []
    for index, shift in enumerate((0, 1, 7, 8, 15, 16, 17, 31, 32, 127, 255)):
        words = ([0x0080, 0x8101, 0x0180, 0xA55A] * 8
                 if shift == 8 else None)
        masks = ([0x0080, 0xFFFF, 0x0101, 0xA55A] * 4
                 if shift == 8 else None)
        specs.append(dict(name=f'shift-{shift:03d}', seed=index + 1,
                          shift=shift, source_words=words, mask_words=masks,
                          plane_check=True))
    specs.extend((
        dict(name='df-reverse-shift17', seed=20, shift=17, df=True,
             si=0x1200, di=0x3400, plane_check=True),
        dict(name='df-reverse-offset-wrap-shift255', seed=21, shift=255, df=True,
             source_segment=0xFFFF, si=0x0003, di=0x0001),
        dict(name='incoming-cx-source-not-entry-ds', seed=22, shift=8,
             ds=0x3500, source_segment=0x6100, plane_check=True),
        dict(name='entry-if-set-before-first-cli', seed=23, shift=7,
             iflag=True, plane_check=True),
        dict(name='saved-ds-read-from-final-mirror', seed=24, shift=8,
             sp=0x0010),
        dict(name='adapter-ret-read-from-final-mirror', seed=25, shift=8,
             sp=0x000E, return_word=0xC37A),
        dict(name='physical-return-word-wrap', seed=26, shift=8,
             ss=0xFFFF, sp=0x000F, return_word=0x4321),
        dict(name='source-word-physical-wrap', seed=27, shift=17,
             source_segment=0xFFFF, si=0x000F),
        dict(name='source-word-offset-boundary', seed=41, shift=17, si=0xFFFF),
        dict(name='mask-word-physical-wrap', seed=28, shift=17,
             source_segment=0xFFFF, bx=0x000F),
        dict(name='mask-word-offset-boundary', seed=42, shift=17, bx=0xFFFF),
        dict(name='destination-offset-wrap', seed=29, shift=8, di=0xFFF0),
        dict(name='vga-source-overlaps-output', seed=30, shift=17,
             source_segment=0xA000, si=0x2400, di=0x2400),
        dict(name='vga-read-map-one', seed=31, shift=17, read_map=1,
             plane_check=True),
        dict(name='vga-stack-safe-shift8', seed=32, shift=8,
             ss=0xA000, sp=0x3010, di=0x5000,
             mask_words=[0xFFFF] * 13, source_words=[0xFFFF] * 26),
        dict(name='provider-changes-second-mask', seed=33, shift=0,
             mask_words=[0xFFFF] * 13,
             providers=[dict(trigger=8, segment=0x6100, offset=0x2202,
                             before=0xFFFF, after=0x0001,
                             tag='second-mask@out8')]),
        dict(name='provider-changes-saved-bx', seed=34, shift=8,
             providers=[dict(trigger=8, segment=0x5000, offset=0x8FF6,
                             before=0x2202, after=0x2300,
                             tag='saved-bx@out8')],
             alternate_mask_offset=0x2300),
        dict(name='stack-mirror-overwrites-live-cx', seed=35, shift=8,
             sp=0x001A),
        dict(name='stack-mirror-overwrites-live-si', seed=37, shift=8,
             sp=0x0016),
        dict(name='stack-mirror-overwrites-live-di', seed=38, shift=8,
             sp=0x0012),
        dict(name='stack-mirror-overwrites-live-bp-bounded', seed=39, shift=8,
             sp=0x0014,
             mask_words=[0x0000] * 13,
             providers=[dict(trigger=8, segment=0x5000, offset=0x000E,
                             before=0x0008, after=0x0001,
                             tag='saved-bp@out8')]),
        dict(name='producer-5bb0-shift12', seed=60, shift=0,
             producer_dx=sprite_layout.DX_5BB0_12, entry_only=ENTRY12,
             source_segment=sprite_layout.DESTINATION_SEGMENT,
             si=sprite_layout.DESTINATION_OFFSET,
             bx=sprite_layout.DESTINATION_OFFSET + 4 * 12,
             plane_check=True),
        dict(name='producer-5bb0-shift13', seed=61, shift=7,
             producer_dx=sprite_layout.DX_5BB0_13, entry_only=ENTRY13,
             source_segment=sprite_layout.DESTINATION_SEGMENT,
             si=sprite_layout.DESTINATION_OFFSET,
             bx=sprite_layout.DESTINATION_OFFSET + 4 * 13,
             plane_check=True),
    ))
    rows = []
    for spec in specs:
        row = dict(seed=0, shift=0, ds=0x3500, source_segment=0x6100,
                   ss=0x5000, sp=0x9000, si=0x1200, di=0x2000,
                   ax=0xB45A, bx=0x2200, dx=0xC400, bp=0x51A3,
                   es=0x4123, flags=(FLAGS & ~DF), df=None, iflag=None,
                   return_word=0xE000, read_map=0, source_words=None,
                   mask_words=None, providers=[], plane_check=False,
                   alternate_mask_offset=None, producer_dx=None,
                   entry_only=None)
        row.update(spec)
        rows.append(row)
    oracle_require(24 <= len(rows) <= 36,
                   f'shifted-sprite fixture count outside scope: {len(rows)}')
    return rows


def configure_vga(seed, read_map):
    device = MinimapVga(0x64D9 ^ seed, read_map=read_map)
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0x0E
    device.gc[3] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    return device


def prepare_producer_handoffs():
    """Run each bounded original producer once and retain its validated RAM."""
    global PRODUCER_WITNESSES
    if PRODUCER_WITNESSES is not None:
        return PRODUCER_WITNESSES
    witnesses = {
        sprite_layout.DX_5BB0_12: sprite_layout.produce_5bb0(
            sprite_layout.DX_5BB0_12, 0x5BB012),
        sprite_layout.DX_5BB0_13: sprite_layout.produce_5bb0(
            sprite_layout.DX_5BB0_13, 0x5BB013),
    }
    for dx, witness in witnesses.items():
        rows = dx & 0xFF
        bank = witness.banks[0]
        oracle_require(witness.entry == sprite_layout.ENTRY_5BB0 and
                       witness.dx == dx and bank.plane_length == 4 * rows and
                       bank.plane_stride == 2 * rows and
                       bank.mask_length == 2 * rows and
                       bank.output_length == 6 * rows,
                       f'5BB0 DX={dx:04X}: producer bank geometry differs')
        start = physical(witness.destination_segment, witness.destination_offset)
        actual = bytes(witness.memory[start:start + bank.output_length])
        oracle_require(actual == witness.bank() == witness.output_bytes,
                       f'5BB0 DX={dx:04X}: generated bank does not match post-run RAM')
    PRODUCER_WITNESSES = witnesses
    return PRODUCER_WITNESSES


def producer_handoff_report():
    rows = []
    for dx, witness in sorted(prepare_producer_handoffs().items()):
        bank = witness.banks[0]
        rows.append(dict(entry=witness.entry, dx=dx,
                         destination_segment=witness.destination_segment,
                         destination_offset=witness.destination_offset,
                         bank_bytes=bank.output_length,
                         plane_bytes=bank.plane_length,
                         plane_stride=bank.plane_stride,
                         mask_bytes=bank.mask_length,
                         producer_steps=witness.steps,
                         producer_memory_transactions=witness.event_count,
                         bank_sha256=sha(witness.output_bytes),
                         scope='one original producer run; excluded from consumer byte events/sites',
                         producer_instruction_addresses=sorted(witness.sites),
                         producer_branch_edges=[list(edge)
                                                for edge in sorted(witness.edges)]))
    return rows


def fixture_entries(case):
    entry = case.get('entry_only')
    return (entry,) if entry is not None else (ENTRY12, ENTRY13)


def setup(case, entry):
    rows = 12 if entry == ENTRY12 else 13
    rng = random.Random(0x64D9 + case['seed'] * 0x9E3779B1 + entry)
    producer = None
    if case['producer_dx'] is not None:
        oracle_require(entry == case['entry_only'],
                       case['name'] + ': producer handoff used the wrong sibling')
        producer = prepare_producer_handoffs()[case['producer_dx']]
        memory = bytearray(producer.memory)
    else:
        memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = physical(LOAD, 0)
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]
    device = configure_vga(case['seed'], case['read_map'])
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    flags = ((case['flags'] | 2) & FLAGS) & ~0x0100
    if case['df'] is not None:
        flags = (flags | DF) if case['df'] else (flags & ~DF)
    if case['iflag'] is not None:
        flags = (flags | IF) if case['iflag'] else (flags & ~IF)
    regs.update(cs=LOAD, ip=entry, ax=case['ax'], bx=case['bx'],
                cx=case['source_segment'], dx=(case['dx'] & 0xFF00) | case['shift'],
                si=case['si'], di=case['di'], bp=case['bp'], ds=case['ds'],
                es=case['es'], ss=case['ss'], sp=case['sp'], flags=flags)

    if producer is None:
        sources = list(case['source_words'] or source_pattern(rows, case['seed']))
        masks = list(case['mask_words'] or mask_pattern(rows, case['seed']))
    else:
        bank = producer.banks[0]
        bank_bytes = producer.bank()
        copied = bank_bytes[bank.plane_offset:bank.plane_offset + bank.plane_length]
        mask_bytes = bank_bytes[bank.mask_offset:bank.mask_offset + bank.mask_length]
        sources = [int.from_bytes(copied[index:index + 2], 'little')
                   for index in range(0, len(copied), 2)]
        masks = [int.from_bytes(mask_bytes[index:index + 2], 'little')
                 for index in range(0, len(mask_bytes), 2)]
        oracle_require(len(sources) == rows * 2 and len(masks) == rows,
                       case['name'] + ': producer bank has the wrong consumer shape')
    oracle_require(len(sources) >= rows * 2,
                   case['name'] + ': two-pass source image is incomplete')
    oracle_require(len(masks) >= rows,
                   case['name'] + ': first-pass mask image is incomplete')
    direction = -1 if flags & DF else 1
    if producer is None:
        for index, value in enumerate(sources[:rows * 2]):
            offset = (regs['si'] + index * direction * 2) & 0xFFFF
            seed_word(memory, device, regs['cx'], offset, value)
            if regs['ds'] != regs['cx']:
                seed_word(memory, device, regs['ds'], offset,
                          value ^ (0x5D3A + index * 0x0101))
        mask_offset = case.get('alternate_mask_offset') or regs['bx']
        for index, value in enumerate(masks[:rows]):
            seed_word(memory, device, regs['cx'], mask_offset + index * 2, value)
        if case.get('alternate_mask_offset') is not None:
            for index, value in enumerate(masks[:rows]):
                seed_word(memory, device, regs['cx'], regs['bx'] + index * 2,
                          value ^ (0xA55A + index * 0x0311))
    else:
        bank_start = physical(producer.destination_segment,
                              producer.destination_offset)
        actual_bank = bytes(memory[bank_start:bank_start +
                                   producer.banks[0].output_length])
        oracle_require(actual_bank == producer.output_bytes,
                       case['name'] + ': setup changed producer handoff bytes')

    # Distinct initial plane contents make both masked writes and plane-1 OR
    # effects observable. Source/output aliases are intentionally left live.
    for row in range(rows):
        row_offset = (regs['di'] + row * (0x29 + 3 * direction)) & 0xFFFF
        for column in range(3):
            offset = (row_offset + column * direction) & 0xFFFF
            address = physical(0xA000, offset)
            if VGA_BASE <= address < VGA_END:
                vga_offset = address - VGA_BASE
                for plane_no, plane in enumerate(device.planes):
                    plane[vga_offset] = (0x31 + row * 19 + column * 7 +
                                         plane_no * 53 + case['seed']) & 0xFF
                memory[address] = device.planes[device.gc[4] & 3][vga_offset]

    # Also seed the second-pass destinations, beginning at the same DI after
    # the original POP DI. Each pass shares a footprint by design.
    put16(memory, regs['ss'], regs['sp'], case['return_word'])
    for provider in case['providers']:
        # Provider slots that are ordinary RAM are asserted at firing time;
        # do not prewrite them because the actual PUSH sequence owns them.
        if provider['trigger'] == 8 and provider['tag'] == 'saved-bx@out8':
            provider['segment'] = regs['ss']
            provider['offset'] = (regs['sp'] - 10) & 0xFFFF
        elif provider['trigger'] == 8 and provider['tag'] == 'saved-bp@out8':
            provider['segment'] = regs['ss']
            provider['offset'] = (regs['sp'] - 6) & 0xFFFF
    case['_rows'] = rows
    case['_sources'] = sources
    case['_masks'] = masks
    return memory, regs, device


class ShiftedAccess(interactions.Access):
    """Bounded physical/VGA bus plus finite event-triggered live-memory changes."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('shifted-sprite event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        for provider in self.case['providers']:
            if self.out_count != provider['trigger'] or provider['tag'] in self.used:
                continue
            actual = get16(self.memory, provider['segment'], provider['offset'])
            oracle_require(actual == provider['before'],
                f'{self.case["name"]}: {provider["tag"]} saw {actual:04X}, '
                f'expected {provider["before"]:04X}')
            self.modify_word(provider['segment'], provider['offset'], provider['after'])
            self.used.add(provider['tag'])


def swap_word(value):
    return (((value & 0xFF) << 8) | ((value >> 8) & 0xFF))


def shift_word(value, count):
    current = swap_word(value)
    spill = 0
    for _ in range(count & 0xFF):
        carry = current & 1
        current >>= 1
        spill = (spill >> 1) | (carry << 7)
    return current, spill


def independent_plane_projection(case, initial_memory, initial_device, entry):
    """Replay the two declared shift chains into an independent VGA fixture."""
    oracle_require(case['plane_check'] and not case['providers'] and
                   case['source_segment'] != 0xA000 and case['ss'] != 0xA000,
                   case['name'] + ': independent plane domain was not disjoint')
    memory = bytearray(initial_memory)
    device = copy.deepcopy(initial_device)
    rows = 12 if entry == ENTRY12 else 13
    shift = case['shift'] & 0xFF
    direction = -1 if case['df'] else 1
    dest0 = case['di'] & 0xFFFF
    sources = case['_sources']
    masks = case['_masks']
    flags = ((case['flags'] | 2) & FLAGS) & ~0x0100
    if case['df']:
        flags |= DF
    if case['iflag']:
        flags |= IF

    # Initial GC/SEQ word writes are reproduced from the literal original OUTs.
    for port, word in ((0x3C4, 0x0F02), (0x3CE, 0x0000),
                       (0x3CE, 0x0E01), (0x3CE, 0x0005), (0x3CE, 0x0003)):
        device.out(port, word, flags)

    def pixel(offset, value):
        address = physical(0xA000, offset)
        device.read(memory, address, flags & ~IF)
        device.write(memory, address, value, flags & ~IF)

    plane_checks = 0
    for row in range(rows):
        src_value, src_spill = shift_word(sources[row], shift)
        mask_value, mask_spill = shift_word(masks[row], shift)
        out_data = (src_value >> 8, src_value & 0xFF, src_spill)
        out_mask = (mask_value >> 8, mask_value & 0xFF, mask_spill)
        start = (dest0 + row * (0x29 + 3 * direction)) & 0xFFFF
        for column, (data, mask_byte) in enumerate(zip(out_data, out_mask)):
            device.out(0x3CE, (mask_byte << 8) | 8, flags)
            pixel((start + column * direction) & 0xFFFF, data)
            plane_checks += 4

    for port, word in ((0x3CE, 0x0001), (0x3CE, 0x1003),
                       (0x3CE, 0xFF08), (0x3C4, 0x0202)):
        device.out(port, word, flags)
    source_start = rows
    for row in range(rows):
        src_value, src_spill = shift_word(sources[source_start + row], shift)
        out_data = (src_value >> 8, src_value & 0xFF, src_spill)
        start = (dest0 + row * (0x29 + 3 * direction)) & 0xFFFF
        for column, data in enumerate(out_data):
            pixel((start + column * direction) & 0xFFFF, data)
            plane_checks += 4
    return device, plane_checks


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
    if actual.state() != expected.state():
        raise error_type(label + ': VGA plane/latch/register state differs')
    if [event[:3] for event in actual.trace] != [event[:3] for event in expected.trace]:
        raise error_type(label + ': VGA device trace differs')


def run_original(case, entry, memory, regs, device, *, core, stop_offsets=None):
    ret = RET12 if entry == ENTRY12 else RET13
    stops = ({ret: 0} if core else None) if stop_offsets is None else stop_offsets
    return interactions.original(
        case, memory, regs, device, core, entry_flag_mask=FLAGS,
        main_instructions=OWN_INS, stop_offsets=stops,
        access_factory=ShiftedAccess, instruction_limit=MAX_INSTRUCTIONS)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-sprite-shifted-m{mutation}.dll',
                     mutation, 'entity_sprite_shifted')
        self.library = ct.CDLL(str(path))
        self.cores = {}
        self.adapters = {}
        for entry, suffix in ((ENTRY12, '12'), (ENTRY13, '13')):
            core = getattr(self.library, f'lmn_draw_entity_shifted_sprite{suffix}_core')
            core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
            core.restype = Result
            adapter = getattr(self.library,
                              f'lmn_draw_entity_shifted_sprite{suffix}_adapter')
            adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                ct.POINTER(RasterBus)]
            adapter.restype = ct.c_uint16
            self.cores[entry], self.adapters[entry] = core, adapter

    def run(self, case, entry, memory, regs, device, *, core):
        access = ShiftedAccess(case, memory, regs, device)

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
            result = self.cores[entry](ram, ct.byref(call), ct.byref(bus))
            for name in CORE_NAMES:
                setattr(state, REG_FIELDS[name], getattr(result, name))
            state.ip = result.continuation
            status, continuation = result.status, result.continuation
        else:
            status = self.adapters[entry](ram, ct.byref(state), ct.byref(bus))
            continuation = state.ip
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status, continuation=continuation)


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


def original_shift_prefix_sweep():
    """Probe each unchecked CL value through the first shift loop only.

    The stop is immediately before PUSH BX/PUSH CX at 6538 or 6637, after the
    actual source/mask SHR-RCR chains have completed. It avoids repeating the
    second-pass renderer 512 times while still executing every shift count in
    each original entry.
    """
    template = copy.deepcopy(next(case for case in make_cases()
                                 if case['name'] == 'shift-000'))
    rows, sites = [], set()
    total_steps = total_events = 0
    for entry, boundary in ((ENTRY12, SHIFT12_BOUNDARY),
                            (ENTRY13, SHIFT13_BOUNDARY)):
        for shift in range(256):
            case = copy.deepcopy(template)
            case['name'] = f'prefix-shift-{entry:04X}-{shift:03d}'
            case['shift'] = shift
            memory, regs, device = setup(case, entry)
            expected = run_original(case, entry, bytearray(memory), dict(regs),
                                    copy.deepcopy(device), core=False,
                                    stop_offsets={boundary: 2})
            oracle_require(expected['status'] == 2 and
                           expected['regs']['ip'] == boundary,
                           case['name'] + ': did not stop at post-shift boundary')
            result = expected['regs']
            source, source_spill = shift_word(case['_sources'][0], shift)
            mask, mask_spill = shift_word(case['_masks'][0], shift)
            checks = {
                'ds': regs['cx'], 'dx': 0x03CE, 'es': 0xA000,
                'bx': (regs['bx'] + 2) & 0xFFFF,
                'cx': shift & 0xFF,
                'si': source, 'bp': mask,
                'ax': ((mask_spill << 8) | source_spill),
                'di': regs['di'], 'sp': (regs['sp'] - 8) & 0xFFFF,
            }
            for name, value in checks.items():
                oracle_require(result[name] == value,
                    f'{case["name"]}: {name}={result[name]:04X}, expected {value:04X}')
            carry_out = (((swap_word(case['_masks'][0]) << 8) >> (shift - 1)) & 1
                         if shift else 0)
            expected_flags = (regs['flags'] & ~ARITH) | 0x0044 | carry_out
            oracle_require(((result['flags'] ^ expected_flags) &
                            expected['flag_mask']) == 0,
                f'{case["name"]}: FLAGS={result["flags"]:04X}, expected '
                f'{expected_flags:04X} under {expected["flag_mask"]:04X}')
            direction = -1 if regs['flags'] & DF else 1
            saved_si = (regs['si'] + direction * 2) & 0xFFFF
            oracle_require(get16(expected['memory'], regs['ss'], result['sp']) == saved_si,
                           case['name'] + ': first live saved-SI word differs')
            oracle_require(expected['steps'] <= 2500 and
                           len(expected['events']) <= MAX_EVENTS,
                           case['name'] + ': prefix probe exceeded its bound')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            sites.update(own_sites)
            rows.append(dict(entry=entry, shift=shift, steps=expected['steps'],
                             events=len(expected['events']), sites=sorted(own_sites)))
            total_steps += expected['steps']
            total_events += len(expected['events'])
            del memory, regs, device, expected
            if shift % 32 == 31:
                gc.collect()
    oracle_require({row['shift'] for row in rows if row['entry'] == ENTRY12} == set(range(256)) and
                   {row['shift'] for row in rows if row['entry'] == ENTRY13} == set(range(256)),
                   'original shift-prefix sweep did not cover all 256 counts per entry')
    return rows, sites, total_steps, total_events


def check_provider_use(case, used, error_type):
    wanted = {provider['tag'] for provider in case['providers']}
    if used != wanted:
        raise error_type(f'{case["name"]}: provider set {used!r}, expected {wanted!r}')


def producer_bank_digest(case, memory, error_type):
    if case['producer_dx'] is None:
        return None
    witness = prepare_producer_handoffs()[case['producer_dx']]
    address = physical(witness.destination_segment, witness.destination_offset)
    actual = bytes(memory[address:address + len(witness.output_bytes)])
    if actual != witness.output_bytes:
        raise error_type(case['name'] + ': actual producer bank changed during consumer')
    return sha(actual)


def compare_case(native, case, entry, *, core):
    initial_memory, initial_regs, initial_device = setup(case, entry)
    label = f'{case["name"]} entry={entry:04X} {"core" if core else "adapter"}'
    expected = run_original(case, entry, bytearray(initial_memory),
                            dict(initial_regs), copy.deepcopy(initial_device), core=core)
    oracle_require(expected['status'] == 0,
                   label + ': original did not complete at declared boundary')
    bank_digest = producer_bank_digest(case, expected['memory'], interactions.OracleFailure)
    oracle_require(expected['steps'] <= MAX_INSTRUCTIONS and
                   len(expected['events']) <= MAX_EVENTS,
                   label + ': original exceeded a declared finite bound')
    check_provider_use(case, expected['used'], interactions.OracleFailure)
    if case['plane_check']:
        projected, checks = independent_plane_projection(
            case, initial_memory, initial_device, entry)
        oracle_require([bytes(p) for p in expected['device'].planes] ==
                       [bytes(p) for p in projected.planes],
                       label + ': independent shifted-byte/plane projection differs')
    else:
        checks = 0

    actual = native.run(case, entry, bytearray(initial_memory),
                        dict(initial_regs), copy.deepcopy(initial_device), core=core)
    require(actual['status'] == 0, label + f': status {actual["status"]}')
    require(actual['continuation'] == expected['continuation'],
            label + f': continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    compare_regs(label, actual['regs'], expected['regs'], expected['flag_mask'], Mismatch)
    compare_memory(label, actual['memory'], expected['memory'], Mismatch)
    producer_bank_digest(case, actual['memory'], Mismatch)
    compare_events(label, actual['events'], expected['events'], Mismatch)
    compare_devices(label, actual['device'], expected['device'], Mismatch)
    require(actual['used'] == expected['used'],
            label + f': provider effects {actual["used"]!r}/{expected["used"]!r}')
    if case['providers']:
        check_provider_use(case, actual['used'], Mismatch)
    if core:
        oracle_require(expected['regs']['ip'] == (RET12 if entry == ENTRY12 else RET13) and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core did not stop before its RET with caller SP')
    else:
        oracle_require(expected['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter failed to consume its actual RET word')
    if case['name'] == 'saved-ds-read-from-final-mirror':
        oracle_require(expected['regs']['ds'] == 0xFF08,
                       label + ': live POP DS did not observe final SS:000E mirror')
    if case['name'] == 'adapter-ret-read-from-final-mirror' and not core:
        oracle_require(expected['regs']['ip'] == 0xFF08,
                       label + ': adapter did not read the mirror-overwritten RET')
    return dict(name=case['name'], entry=entry, boundary='core' if core else 'adapter',
                sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
                edges=sorted([src, dst] for scope, src, dst in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                plane_byte_checks=checks, providers=sorted(expected['used']),
                producer_bank_sha256=bank_digest)


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/inputs.json', 'metadata/symbols.json',
        'metadata/regions.json', 'metadata/hints.json', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/game_code.asm',
        'src/entity_sprite_shifted.asm', 'src/entity_graphics.asm',
        'src/entity_sprite_planes.asm', 'src/entity_sprite_wide.asm',
        'src/entity_sprite_four_planes.asm', 'src/image_tail.asm',
        'src/game_code_late_after_palette.asm', 'src/entry_services.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_sprite_shifted.c', 'c/entity_sprite_shifted.h', 'c/regs.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'tests/entity_sprite_shifted.py',
        'tests/entity_interactions.py', 'tests/entity_strip.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/minimap_vga.py',
        'tests/entity_sprite_layout.py', 'tools/resources.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py', 'tools/unpack.py',
        'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'missing shifted-sprite hash inputs: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(cases, before):
    oracle_require(before == input_hashes(), 'shifted-sprite inputs changed before preflight')
    producer_handoffs = producer_handoff_report()
    rows, sites, edges = [], set(), set()
    for case in cases:
        for entry in fixture_entries(case):
            for core in (True, False):
                memory, regs, device = setup(case, entry)
                label = (f'{case["name"]} entry={entry:04X} '
                         f'{"core" if core else "adapter"}')
                expected = run_original(case, entry, bytearray(memory), dict(regs),
                                        copy.deepcopy(device), core=core)
                oracle_require(expected['status'] == 0,
                    label + ': original did not reach its advertised boundary')
                check_provider_use(case, expected['used'], interactions.OracleFailure)
                bank_digest = producer_bank_digest(case, expected['memory'],
                                                   interactions.OracleFailure)
                checks = 0
                if case['plane_check']:
                    projected, checks = independent_plane_projection(
                        case, memory, device, entry)
                    oracle_require([bytes(p) for p in expected['device'].planes] ==
                                   [bytes(p) for p in projected.planes],
                        label + ': independent shifted-byte/plane projection differs')
                if core:
                    ret = RET12 if entry == ENTRY12 else RET13
                    oracle_require(expected['regs']['ip'] == ret and
                                   expected['regs']['sp'] == regs['sp'],
                                   label + ': incorrect core seam')
                else:
                    oracle_require(expected['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
                                   label + ': outer RET did not advance live SP')
                if case['name'] == 'saved-ds-read-from-final-mirror':
                    oracle_require(expected['regs']['ds'] == 0xFF08,
                                   label + ': live POP DS did not read the final mirror')
                if case['name'] == 'adapter-ret-read-from-final-mirror' and not core:
                    oracle_require(expected['regs']['ip'] == 0xFF08,
                                   label + ': adapter RET ignored the final mirror')
                own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
                own_edges = {(src, dst) for scope, src, dst in expected['edges']
                             if scope == 'main'}
                rows.append(dict(name=case['name'], entry=entry,
                    boundary='core' if core else 'adapter', sites=sorted(own_sites),
                    edges=[list(edge) for edge in sorted(own_edges)],
                    events=len(expected['events']), steps=expected['steps'],
                    plane_byte_checks=checks, providers=sorted(expected['used']),
                    producer_bank_sha256=bank_digest))
                sites.update(own_sites)
                edges.update(own_edges)
                del memory, regs, device, expected
                gc.collect()
    oracle_require(sites == OWN_SITES,
        f'original site union differs: missing={sorted(OWN_SITES-sites)} '
        f'extra={sorted(sites-OWN_SITES)}')
    expected_edges = static_edges()
    oracle_require(edges == expected_edges,
        f'original edge union differs: missing={sorted(expected_edges-edges)} '
        f'extra={sorted(edges-expected_edges)}')
    oracle_require(before == input_hashes(), 'shifted-sprite inputs changed during preflight')
    sweep_rows, sweep_sites, sweep_steps, sweep_events = original_shift_prefix_sweep()
    oracle_require(before == input_hashes(),
                   'shifted-sprite inputs changed during prefix sweep')
    return (rows, sites, edges, sweep_rows, sweep_sites, sweep_steps,
            sweep_events, producer_handoffs)


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'shifted-sprite inputs changed before native run')
    oracle_require(CODE_BYTES == 510 and len(OWN_SITES) == 252,
        f'shifted-sprite inventory changed: {CODE_BYTES} bytes/{len(OWN_SITES)} sites')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned executable image identity changed')
    cases = make_cases()
    producer_handoffs = producer_handoff_report()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = plane_checks = 0
    for case in cases:
        for entry in fixture_entries(case):
            for core in (True, False):
                row = compare_case(baseline, case, entry, core=core)
                rows.append(row)
                sites.update(row['sites'])
                edges.update(tuple(edge) for edge in row['edges'])
                total_events += row['events']
                total_steps += row['steps']
                plane_checks += row['plane_byte_checks']
            gc.collect()
    oracle_require(sites == OWN_SITES,
                   f'native site union differs: missing={sorted(OWN_SITES-sites)}')
    oracle_require(edges == static_edges(),
                   f'native edge union differs: missing={sorted(static_edges()-edges)}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: 'df-reverse-shift17',
        2: 'df-reverse-shift17',
        3: 'incoming-cx-source-not-entry-ds',
        4: 'shift-008',
        5: 'provider-changes-second-mask',
        6: 'shift-008',
        7: 'shift-008',
        8: 'provider-changes-saved-bx',
        9: 'entry-if-set-before-first-cli',
        10: 'saved-ds-read-from-final-mirror',
    }
    mutations = []
    for mutation, name in witnesses.items():
        case = by_name[name]
        variant = Native(directory, mutation)
        try:
            compare_case(variant, case, ENTRY12, core=True)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, case=name, entry=ENTRY12,
                                  completed=True, mismatch=str(error)))
        else:
            raise interactions.OracleFailure(
                f'shifted-sprite mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'shifted-sprite inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[ENTRY12, END12], [ENTRY13, END13]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
        static_instruction_addresses=sorted(OWN_SITES),
        branch_edge_count=len(static_edges()),
        static_branch_edges=[list(edge) for edge in sorted(static_edges())],
        case_count=sum(len(fixture_entries(case)) for case in cases),
        core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(edge) for edge in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        independent_plane_byte_checks=plane_checks, input_hashes=after,
        producer_handoffs=producer_handoffs,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain=('DrawEntityShiftedSprite12/13, 64D9..66D6. Both cores stop after live '
                'POP DS and before their actual RET; adapters read the live SS:SP word. '
                'Comparisons cover all RAM, the 13 logical roles plus IP, defined FLAGS, '
                'ordered RAM/VGA/OUT events and complete VGA planes/latches/registers. '
                'Independent bit-chain replay checks both the three-byte source/mask shift '
                'and the second-pass plane-1 OR pixels. The fixtures retain unchecked 8-bit '
                'shift counts, DF-sensitive LODSW/STOSB, physical word wrap, live CX/BX/SI/DI/BP/DS/RET '
                'stack effects, latch reads, IF transitions and finite callback changes.')))
    print(f'PASS shifted sprite: '
          f'{sum(len(fixture_entries(case)) for case in cases)} entry fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{plane_checks} independent plane-byte checks, {len(mutations)} mutants',
          flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-sprite-shifted-original-', parent=BUILD) as directory:
            before = input_hashes()
            hashes = Path(directory) / 'input-hashes.json'
            write_json(hashes, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hashes)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        (rows, sites, edges, sweep_rows, sweep_sites, sweep_steps,
         sweep_events, producer_handoffs) = \
            original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE),
            code_ranges=[[ENTRY12, END12], [ENTRY13, END13]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
            static_instruction_addresses=sorted(OWN_SITES),
            branch_edge_count=len(static_edges()),
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=sum(len(fixture_entries(case)) for case in make_cases()),
            core_adapter_comparisons=len(rows),
            original_only_shift_prefix_probe_count=len(sweep_rows),
            original_only_shift_prefix_values_per_entry=256,
            original_only_shift_prefix_instruction_addresses=sorted(sweep_sites),
            original_only_shift_prefix_steps=sweep_steps,
            original_only_shift_prefix_events=sweep_events,
            original_only_shift_prefix_probes=sweep_rows,
            cases=rows, input_hashes=before,
            producer_handoffs=producer_handoffs,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_bus_event_limit=MAX_EVENTS),
            domain='Original-only shifted-sprite preflight; no native evidence.'))
        print(f'PASS original shifted sprite: '
              f'{sum(len(fixture_entries(case)) for case in make_cases())} entries, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_sprite_shifted.py [--original-only | --native-worker DIR HASHES]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-sprite-shifted-native-', parent=BUILD) as directory:
        before = input_hashes()
        hashes = Path(directory) / 'input-hashes.json'
        write_json(hashes, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hashes)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
