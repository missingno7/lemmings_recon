"""Bounded original/native checks for the literal 7218 fixed-pattern leaf."""
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
import entity_interactions as oracle
import fixed_word_banks as producer
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated


IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
LOAD = 0x1010
ENTRY, RET, END = 0x7218, 0x75EE, 0x75EF
DATA_SEGMENT, OUTPUT_SEGMENT = 0x2000, 0x6000
MAX_STEPS, MAX_EVENTS = 600, 1024
MAX_PROVIDER_EVENTS = 20_000
WORKER_SECONDS, MEMORY_MIB = 420, 384
REPORT = BUILD / 'fixed-pattern-draw-differential.json'
ORIGINAL_REPORT = BUILD / 'fixed-pattern-draw-original-differential.json'
CALL_REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')
CALL_FIELDS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'code_segment',
               'data_segment', 'extra_segment', 'stack_segment',
               'stack_offset', 'flags')
ROLE_TO_REG = dict(zip(CALL_FIELDS, CALL_REGS))

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
OWN_RETURNS = {pc for pc, ins in OWN_INS.items() if ins.mnemonic == 'ret'}

MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32,
                     ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CALL_FIELDS]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                CALL_FIELDS + ('continuation', 'status')]


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The original fixture escaped its stated code or access budget."""


class Mismatch(AssertionError):
    """A completed native comparison differs from the original."""


def check(value, message):
    if not value:
        raise OracleFailure(message)


def require(value, message):
    if not value:
        raise Mismatch(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def read_physical(memory, address):
    return memory[address & MASK]


def read_word_physical(memory, segment, offset):
    address = physical(segment, offset)
    return read_physical(memory, address) | (read_physical(memory, address + 1) << 8)


def put_physical(memory, address, value):
    memory[address & MASK] = value & 0xFF


def sync_vga_byte(memory, device, address, value, plane=None):
    address &= MASK
    memory[address] = value & 0xFF
    if device is not None and VGA_BASE <= address < VGA_END:
        index = address - VGA_BASE
        targets = range(4) if plane is None else (plane,)
        for plane_index in targets:
            device.planes[plane_index][index] = value & 0xFF


def put_word_physical(memory, segment, offset, value, device=None):
    address = physical(segment, offset)
    sync_vga_byte(memory, device, address, value)
    sync_vga_byte(memory, device, address + 1, value >> 8)


def stream_byte(seed, index, group):
    return (0x43 + seed * 29 + index * (37 + group * 2) +
            (index >> 1) * (11 + group * 5) + index * index * 3) & 0xFF


def case_specs():
    base = dict(ds=DATA_SEGMENT, si=0x2800, bx=0x2860, di=0x3100,
                ss=0x8000, sp=0x9000, flags=0x0AD7, seed=0x721800,
                read_map=0, provider=None, independent=False)
    cases = [
        dict(name='forward-independent-if-set', independent=True),
        dict(name='forward-independent-if-clear', flags=0x08D7,
             independent=True),
        dict(name='backward-independent-df-if-set', flags=0x0ED7,
             independent=True),
        dict(name='partial-mask-latch-equation', seed=0x721803,
             independent=True),
        dict(name='inc-bx-wrap-preserves-cf', bx=0xFFFE, flags=0x0AD7,
             seed=0x721804, independent=True, assert_inc_flags=True),
        dict(name='low-ds-frame', ds=0x0000, si=0x6100, bx=0x6160,
             seed=0x721805, independent=True),
        dict(name='bx-word-ea-ffff-physical-plus-one', ds=0x1234,
             si=0x2300, bx=0xFFFF, seed=0x721806),
        dict(name='si-word-ea-ffff-physical-plus-one', ds=0x3456,
             si=0xFFFF, bx=0x2000, seed=0x721807),
        dict(name='a20-wrap-si-and-bx', ds=0xF000, si=0xFFFF, bx=0xFF00,
             seed=0x721808),
        dict(name='segment-wrap-control-word', ds=0xFFFF, si=0x3100,
             bx=0xFFFF, seed=0x721809),
        dict(name='source-and-destination-vga-alias', ds=0xA000,
             si=0x3000, bx=0x0000, di=0x0003, read_map=0,
             seed=0x72180A),
        dict(name='provider-changes-next-source-byte', provider='data',
             seed=0x72180B),
        dict(name='provider-changes-next-mask-byte', provider='mask',
             seed=0x72180C),
        dict(name='vga-provider-changes-next-si-cursor', ds=0xA000,
             si=0x2000, bx=0x2060, di=0x4100, read_map=0,
             provider='vga-cursor', seed=0x72180D),
        dict(name='vga-data-segment-stack', ss=0xA000, sp=0xE000,
             di=0x1000, seed=0x72180E),
        dict(name='outer-ret-overwritten-by-output', ss=0xA000,
             sp=0x1200, di=0x1200, seed=0x72180F,
             outer_return=0xD00D),
        dict(name='outer-ret-word-physical-wrap', ss=0xF000, sp=0xFFFF,
             seed=0x721810, outer_return=0x1234),
        dict(name='outer-ret-stack-offset-wrap', ss=0x1234, sp=0xFFFF,
             seed=0x721811, outer_return=0x5678),
        dict(name='ordinary-source-output-overlap', ds=0x3000,
             si=0x4200, bx=0x4260, di=0x4200, seed=0x721812),
        dict(name='source-destination-physical-alias-distinct-segments',
             ds=0x9E00, si=0x2000, bx=0x2060, di=0x2000,
             read_map=0, seed=0x721813),
    ]
    result = []
    for index, item in enumerate(cases):
        merged = dict(base)
        merged.update(item)
        merged.setdefault('seed', base['seed'] + index)
        result.append(merged)
    return result


def make_consumer_case(name, *, data_segment, si, bx, bank, shift):
    return dict(name=name, ds=data_segment, si=si, bx=bx, di=0x3500,
                ss=0x8100, sp=0x9100, flags=0x0AD7,
                seed=0x730000 + bank * 0x100 + shift,
                read_map=0, provider=None, independent=True,
                producer_bank=bank, producer_shift=shift)


def all_cases():
    cases = case_specs()
    for bank in range(2):
        for shift in range(8):
            start = bank * 0x480 + shift * 0x90
            cases.append(make_consumer_case(
                f'producer-bank-{bank}-shift-{shift}',
                data_segment=OUTPUT_SEGMENT, si=start, bx=start + 0x60,
                bank=bank, shift=shift))
    return cases


def setup(case, base_memory=None):
    seed = case['seed']
    if base_memory is None:
        memory = bytearray(random.Random(seed).randbytes(SIZE))
    else:
        memory = bytearray(base_memory)
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    code_base = physical(LOAD, 0)
    first = min(len(loaded), SIZE - code_base)
    memory[code_base:code_base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = MinimapVga(seed, read_map=case.get('read_map', 0))
    # The fixture's host-visible aperture mirrors the selected read-map plane.
    device.gc[4] = case.get('read_map', 0) & 3
    memory[VGA_BASE:VGA_END] = device.planes[0]

    regs = dict(cs=LOAD, ip=ENTRY, ax=0xA59B,
                bx=case['bx'], cx=0x6E31, dx=0x7A2D,
                si=case['si'], di=case['di'], bp=0x6B6B,
                ds=case['ds'], es=0x5A5A, ss=case['ss'], sp=case['sp'],
                flags=case['flags'])

    if 'producer_bank' not in case:
        direction = -1 if regs['flags'] & 0x0400 else 1
        source_plane = device.gc[4] & 3
        for index in range(0x60):
            offset = (regs['si'] + direction * index) & 0xFFFF
            address = physical(regs['ds'], offset)
            if VGA_BASE <= address < VGA_END:
                sync_vga_byte(memory, device, address,
                              stream_byte(seed, index, 1), source_plane)
            else:
                put_physical(memory, address, stream_byte(seed, index, 1))
        for index in range(0x30):
            offset = (regs['bx'] + index) & 0xFFFF
            address = physical(regs['ds'], offset)
            if VGA_BASE <= address < VGA_END:
                sync_vga_byte(memory, device, address,
                              stream_byte(seed, index, 2), source_plane)
            else:
                put_physical(memory, address, stream_byte(seed, index, 2))
        memory[VGA_BASE:VGA_END] = device.planes[0]

        # Make both candidates visibly different at segment-offset and A20
        # boundaries.  The real word read takes its high byte at physical+1.
        if case['name'] in ('bx-word-ea-ffff-physical-plus-one',
                            'segment-wrap-control-word'):
            control_address = physical(regs['ds'], regs['bx'])
            put_physical(memory, control_address, 0x35)
            put_physical(memory, control_address + 1, 0xE1)
            put_physical(memory, physical(regs['ds'], 0), 0x7B)
        if case['name'] == 'si-word-ea-ffff-physical-plus-one':
            source_address = physical(regs['ds'], regs['si'])
            put_physical(memory, source_address, 0x42)
            put_physical(memory, source_address + 1, 0xD6)
            put_physical(memory, physical(regs['ds'], 0), 0x23)
        if case['name'] == 'a20-wrap-si-and-bx':
            source_address = physical(regs['ds'], regs['si'])
            put_physical(memory, source_address, 0x51)
            put_physical(memory, source_address + 1, 0xA7)
            put_physical(memory, physical(regs['ds'], 0), 0x38)
        if case['name'] == 'outer-ret-overwritten-by-output':
            for index in range(0x60):
                put_physical(memory,
                    physical(regs['ds'], regs['si'] + index),
                    (0x42 + index * 7) & 0xFF)
            for index in range(0x30):
                put_physical(memory,
                    physical(regs['ds'], regs['bx'] + index), 0xFF)

    put_word_physical(memory, regs['ss'], regs['sp'],
                      case.get('outer_return', 0xD00D), device)
    return memory, regs, device


class Access:
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.native = native
        self.events = []
        self.used = set()
        self.mirror = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror:
            self.mirror(address, value & 0xFF)

    def modify_physical(self, address, value):
        self.store(address, value)
        if self.device is not None and VGA_BASE <= (address & MASK) < VGA_END:
            self.device.planes[0][(address & MASK) - VGA_BASE] = value & 0xFF

    def provider_after_event(self, kind, address):
        effect = self.case.get('provider')
        if kind != 'write' or not effect or effect in self.used:
            return
        # ES is an output register assigned inside the routine.  The oracle's
        # register dict is the entry snapshot, so use the documented live VGA
        # destination segment and entry DI to recognize the first STOSB.
        if address != physical(0xA000, self.case['di']):
            return
        ds, si, bx = self.regs['ds'], self.regs['si'], self.regs['bx']
        if effect == 'data':
            target = physical(ds, si + 3)
            self.modify_physical(target, 0xD3)
        elif effect == 'mask':
            target = physical(ds, bx + 3)
            self.modify_physical(target, 0xA9)
        elif effect == 'vga-cursor':
            target = physical(ds, si + 3)
            if self.device is None or not VGA_BASE <= target < VGA_END:
                raise OracleFailure('VGA cursor provider target escaped aperture')
            offset = target - VGA_BASE
            value = 0xB7
            for plane in self.device.planes:
                plane[offset] = value
            self.modify_physical(target, value)
        else:
            raise OracleFailure('unknown fixed-pattern provider ' + effect)
        self.used.add(effect)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('fixed-pattern draw bus callback budget exhausted')
        address &= MASK
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
        self.provider_after_event(kind, address)
        return value & 0xFF

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('fixed-pattern draw bus callback budget exhausted')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


def original(case, memory, regs, device, *, core):
    accessors = []
    ref = oracle.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        instruction_limit=MAX_STEPS,
        access_factory=lambda c, m, r, d: accessors.append(
            Access(c, m, r, d)) or accessors[-1])
    ref['providers'] = set(accessors[0].used)
    return ref


def expected_final_add_flags(flags, left, right=0x29):
    wide = left + right
    result = wide & 0xFFFF
    out = flags & ~0x08D5
    parity = bin(result & 0xFF).count('1') % 2 == 0
    if wide > 0xFFFF:
        out |= 0x0001
    if parity:
        out |= 0x0004
    if (left ^ right ^ result) & 0x10:
        out |= 0x0010
    if result == 0:
        out |= 0x0040
    if result & 0x8000:
        out |= 0x0080
    if (~(left ^ right) & (left ^ result) & 0x8000) != 0:
        out |= 0x0800
    return out & 0xFFFF


def independent_planes(case, initial_memory, initial_device):
    if not case.get('independent'):
        return 0
    check(case['ds'] != 0xA000,
          case['name'] + ': independent RAM source must not alias VGA')
    planes = [bytearray(plane) for plane in initial_device.planes]
    latches = list(initial_device.latches)
    source_cursor = case['si']
    control = case['bx']
    destination = case['di']
    direction = -1 if case['flags'] & 0x0400 else 1
    memory = initial_memory
    written_plane_bytes = 0

    def fetch_source_byte(offset):
        return read_physical(memory, physical(case['ds'], offset))

    def fetch_source_word(offset):
        address = physical(case['ds'], offset)
        return (read_physical(memory, address) |
                (read_physical(memory, address + 1) << 8))

    def lodsw(cursor):
        address = physical(case['ds'], cursor)
        low = read_physical(memory, address)
        high = read_physical(memory, address + 1)
        return low, high, (cursor + direction * 2) & 0xFFFF

    def lodsb(cursor):
        return (fetch_source_byte(cursor), (cursor + direction) & 0xFFFF)

    def write_first(offset, data, bit_mask):
        nonlocal latches, written_plane_bytes
        offset &= 0xFFFF
        latches = [plane[offset] for plane in planes]
        for plane_index in range(4):
            source_value = data if plane_index == 0 else 0
            planes[plane_index][offset] = (
                (source_value & bit_mask) |
                (latches[plane_index] & (~bit_mask & 0xFF)))
            written_plane_bytes += 1

    # The first literal pass selects GC write mode zero, set/reset on planes
    # 1..3, and a per-pixel bit mask.  Its destination read supplies all four
    # old plane bytes for the independent masked-write equation.
    for _row in range(16):
        word = fetch_source_word(control)
        mask_low, mask_high = word & 0xFF, word >> 8
        control = (control + 2) & 0xFFFF
        data_low, data_high, source_cursor = lodsw(source_cursor)
        write_first(destination, data_low, mask_low)
        destination = (destination + direction) & 0xFFFF
        write_first(destination, data_high, mask_high)
        destination = (destination + direction) & 0xFFFF
        third_mask = fetch_source_byte(control)
        control = (control + 1) & 0xFFFF
        data_third, source_cursor = lodsb(source_cursor)
        write_first(destination, data_third, third_mask)
        destination = (destination + direction) & 0xFFFF
        destination = (destination + 0x29) & 0xFFFF

    # The second pass resets DI, uses GC bit mask FF, GC data-rotate/logical
    # operation 10h (OR), and map mask 02.  Each read reloads the latches, so
    # plane 1 receives the source byte ORed with its old destination byte.
    destination = case['di']
    for _row in range(16):
        data_low, data_high, source_cursor = lodsw(source_cursor)
        for data in (data_low, data_high):
            offset = destination & 0xFFFF
            latches = [plane[offset] for plane in planes]
            planes[1][offset] = data | latches[1]
            written_plane_bytes += 1
            destination = (destination + direction) & 0xFFFF
        data_third, source_cursor = lodsb(source_cursor)
        offset = destination & 0xFFFF
        latches = [plane[offset] for plane in planes]
        planes[1][offset] = data_third | latches[1]
        written_plane_bytes += 1
        destination = (destination + direction) & 0xFFFF
        destination = (destination + 0x29) & 0xFFFF

    return planes, written_plane_bytes


def validate_bus_protocol(case, ref):
    events = ref['events']
    outputs = [(index, event) for index, event in enumerate(events)
               if event[0] == 'out']
    setup = [(0x03C4, 0x0F02), (0x03CE, 0x0000), (0x03CE, 0x0E01),
             (0x03CE, 0x0005), (0x03CE, 0x0003)]
    second_pass_setup = [(0x03CE, 0x0001), (0x03CE, 0x1003),
                         (0x03CE, 0xFF08), (0x03C4, 0x0202)]
    output_values = [(event[1], event[2]) for _, event in outputs]
    check(len(outputs) == 57 and output_values[:5] == setup and
          output_values[-4:] == second_pass_setup,
          case['name'] + ': literal VGA setup or pass-boundary ports changed')

    direction = -1 if case['flags'] & 0x0400 else 1
    row_pitch = 0x26 if direction < 0 else 0x2C
    offsets = [(case['di'] + row * row_pitch + column * direction) & 0xFFFF
               for row in range(16) for column in range(3)]
    destinations = [physical(0xA000, offset) for offset in offsets]
    second_setup_start = outputs[-4][0]
    boundary_index = outputs[-1][0]
    first_mask_outputs = outputs[5:-4]
    check(len(first_mask_outputs) == 48 and all(
          event[1] == 0x03CE and (event[2] & 0xFF) == 8
          for _, event in first_mask_outputs),
          case['name'] + ': first pass did not issue 3 GC8 writes per row')

    for ordinal, (index, _) in enumerate(first_mask_outputs):
        destination = destinations[ordinal]
        check(index + 1 < len(events) and events[index + 1][0] == 'read' and
              events[index + 1][1] == destination,
              case['name'] + ': first-pass STOSB lacks its latch read')
        next_out = (first_mask_outputs[ordinal + 1][0]
                    if ordinal + 1 < len(first_mask_outputs) else
                    second_setup_start)
        check(any(event[0] == 'write' and event[1] == destination
                  for event in events[index + 2:next_out]),
              case['name'] + ': GC8/latch setup did not reach matching STOSB')

    check(boundary_index + 1 < len(events) and
          events[boundary_index + 1][0] == 'read' and
          events[boundary_index + 1][1] == destinations[0],
          case['name'] + ': second pass did not begin with its first latch read')
    first_writes = [event[1] for event in events[:second_setup_start]
                    if event[0] == 'write']
    second_writes = [event[1] for event in events[boundary_index + 1:]
                     if event[0] == 'write']
    check(first_writes == destinations and second_writes == destinations,
          case['name'] + ': either 16-row pass has an unexpected STOSB order')
    check(not any(event[0] == 'out' for event in events[boundary_index + 1:]),
          case['name'] + ': second pass contains an unexpected port write')

    source_offsets = [((case['si'] + direction * index) & 0xFFFF)
                      for index in range(0x60)]
    source_offsets.extend((case['bx'] + index) & 0xFFFF
                          for index in range(0x30))
    source_addresses = [physical(case['ds'], offset)
                        for offset in source_offsets]
    source_in_vga = any(VGA_BASE <= address < VGA_END
                        for address in source_addresses)
    if not source_in_vga:
        last_output_write = max(index for index, event in enumerate(events)
                                if event[0] == 'write')
        second_pass_reads = [event[1] for event in
            events[boundary_index + 1:last_output_write + 1]
            if event[0] == 'read' and VGA_BASE <= event[1] < VGA_END]
        check(second_pass_reads == destinations,
              case['name'] + ': second-pass STOSB latch-read sequence changed')
        last_vga_read = None
        for event in events[boundary_index + 1:last_output_write + 1]:
            if event[0] == 'read' and VGA_BASE <= event[1] < VGA_END:
                last_vga_read = event[1]
            elif event[0] == 'write' and event[1] in set(destinations):
                check(last_vga_read == event[1],
                      case['name'] + ': second-pass STOSB lacks its latch read')


def validate(case, initial_memory, initial_device, regs, ref, *, core):
    validate_bus_protocol(case, ref)
    check(ref['status'] == 0, case['name'] + ': original status')
    check(ref['regs']['es'] == 0xA000, case['name'] + ': ES must remain VGA')
    check(ref['regs']['ds'] == regs['ds'], case['name'] + ': live DS changed')
    check(ref['regs']['ss'] == regs['ss'], case['name'] + ': live SS changed')
    check(ref['regs']['bp'] == regs['di'], case['name'] + ': BP did not retain entry DI')
    check(ref['regs']['dx'] == 0x03C4, case['name'] + ': final port cursor')
    check(ref['regs']['si'] == ((regs['si'] +
          (-0x60 if regs['flags'] & 0x0400 else 0x60)) & 0xFFFF),
          case['name'] + ': LODSW/LODSB cursor delta')
    check(ref['regs']['bx'] == ((regs['bx'] + 0x30) & 0xFFFF),
          case['name'] + ': three INC BX operations per row')
    backwards = bool(regs['flags'] & 0x0400)
    row_pitch = 0x26 if backwards else 0x2C
    expected_di = (regs['di'] + 16 * row_pitch) & 0xFFFF
    check(ref['regs']['di'] == expected_di,
          case['name'] + ': final second-pass DI cursor')
    check(ref['regs']['flags'] & 0x0200,
          case['name'] + ': STI did not force IF on return')
    check((ref['regs']['flags'] & 0x0400) == (regs['flags'] & 0x0400),
          case['name'] + ': DF changed')
    if core:
        check(ref['regs']['ip'] == RET, case['name'] + ': pre-RET boundary')
        check(ref['regs']['sp'] == regs['sp'], case['name'] + ': core SP changed')
    else:
        check(ref['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
              case['name'] + ': actual RET did not advance SP')
        target = read_word_physical(ref['memory'], regs['ss'], regs['sp'])
        check(ref['regs']['ip'] == target, case['name'] + ': actual RET target')
        if case['name'] == 'outer-ret-overwritten-by-output':
            check(target != case.get('outer_return', 0xD00D),
                  case['name'] + ': output did not replace the live RET word')
        if case['name'] in ('outer-ret-word-physical-wrap',
                            'outer-ret-stack-offset-wrap'):
            addresses = [event[1] for event in ref['events'][-2:]]
            stack_address = physical(regs['ss'], regs['sp'])
            check(addresses == [stack_address, (stack_address + 1) & MASK],
                  case['name'] + ': RET did not read the physical high byte')
    check(ref['providers'] == ({case['provider']} if case.get('provider') else set()),
          case['name'] + ': live provider effect')

    # The final flags are from the last ADD DI,29 instruction.  Its operands
    # can be reconstructed from the independent row cursor equation.
    final_row_start = (regs['di'] + 15 * row_pitch) & 0xFFFF
    before_final_add = (final_row_start + (-3 if backwards else 3)) & 0xFFFF
    expected_flags = expected_final_add_flags(ref['regs']['flags'], before_final_add)
    check((ref['regs']['flags'] & 0x08D5) == (expected_flags & 0x08D5),
          case['name'] + ': final ADD DI flags')

    if case['name'] in ('bx-word-ea-ffff-physical-plus-one',
                        'segment-wrap-control-word',
                        'a20-wrap-si-and-bx'):
        low_address = physical(regs['ds'], regs['bx'])
        addresses = [event[1] for event in ref['events'][:7]
                     if event[0] == 'read']
        check(addresses[:2] == [low_address, (low_address + 1) & MASK],
              case['name'] + ': BX word high byte was not physical+1')
    if case['name'] in ('si-word-ea-ffff-physical-plus-one',
                        'a20-wrap-si-and-bx'):
        source_address = physical(regs['ds'], regs['si'])
        pair = any(event[0] == 'read' and event[1] == source_address and
                   index + 1 < len(ref['events']) and
                   ref['events'][index + 1][0] == 'read' and
                   ref['events'][index + 1][1] == ((source_address + 1) & MASK)
                   for index, event in enumerate(ref['events']))
        check(pair, case['name'] + ': LODSW high byte was not physical+1')

    if case.get('assert_inc_flags'):
        # XOR AX,AX clears entry CF before the word is read.  The first mask
        # OUT observes BX=0000 after two INCs wrap from FFFEh; INC must retain
        # the cleared carry instead of setting it like ADD BX,1 would.
        mask_outs = [event for event in ref['events']
                     if event[0] == 'out' and event[1] == 0x03CE and
                     (event[2] & 0xFF) == 8 and ((event[2] >> 8) & 0xFF) ==
                     initial_memory[physical(regs['ds'], regs['bx'])]]
        check(mask_outs, case['name'] + ': first mask OUT not found')
        mask_flags = mask_outs[0][3]
        check(not (mask_flags & 0x0001),
              case['name'] + ': INC BX incorrectly changed cleared CF')
        check(mask_flags & 0x0040, case['name'] + ': final word INC did not set ZF')

    plane_count = 0
    if case.get('independent'):
        expected_planes, plane_count = independent_planes(
            case, initial_memory, initial_device)
        for plane_index, plane in enumerate(expected_planes):
            check(bytes(plane) == bytes(ref['device'].planes[plane_index]),
                  f"{case['name']}: independent plane {plane_index} equation")
    return plane_count


def compare_result(actual, expected, label):
    require(actual['status'] == expected['status'], label + ': status differs')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    for name in oracle.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f"{label}: {name} {actual['regs'][name]:04X}/"
                f"{expected['regs'][name]:04X} mask={mask:04X}")
    require(actual['providers'] == expected['providers'], label + ': providers differ')
    require(len(actual['events']) == len(expected['events']),
            label + ': event count differs')
    for index, (got, want) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == want[:3],
                f'{label}: event {index} differs: {got!r}/{want!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS differ {got[3]:04X}/{want[3]:04X}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA state differs')
    require([event[:3] for event in actual['device'].trace] ==
            [event[:3] for event in expected['device'].trace],
            label + ': VGA trace differs')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'fixed-pattern-draw-m{mutation}.dll',
                     mutation, 'fixed_pattern_draw')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_fixed_word_pattern_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_fixed_word_pattern_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(oracle.Regs), ct.POINTER(Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)

        def die(error):
            code = 86 if 'budget' in str(error).lower() else 87
            try:
                os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
            finally:
                os._exit(code)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags)
            except BaseException as error:
                die(error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, value=value)
            except BaseException as error:
                die(error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags)
            except BaseException as error:
                die(error)

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in CALL_REGS))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for role, reg in zip(CALL_FIELDS, CALL_REGS):
                setattr(state, reg, getattr(result, role))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in oracle.REG_NAMES},
                    status=status, events=access.events, providers=set(access.used),
                    device=device)


def compare(native, case, *, core, base_memory=None):
    memory, regs, device = setup(case, base_memory)
    expected = original(case, memory, regs, device, core=core)
    independent_bytes = validate(case, memory, device, regs, expected, core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    compare_result(actual, expected, case['name'] + (' core' if core else ' adapter'))
    return expected, independent_bytes


def run_producer(directory, *, native_enabled):
    case = next(case for case in producer.cases()
                if case['name'] == 'constructed-source')
    initial, regs, device = producer.setup(case)
    expected_rows = []
    native = producer.Native(directory) if native_enabled else None
    output_memory = None
    for core in (True, False):
        ref = producer.original(case, initial, regs, device, core=core)
        independent_bytes = producer.validate(case, initial, regs, ref, core=core)
        if native_enabled:
            got = native.run(case, bytearray(initial), dict(regs),
                             copy.deepcopy(device), core=core)
            producer.shared.equal(got, ref, 'fixed word producer ' +
                                  ('core' if core else 'adapter'))
            if core:
                require(got['child_entry'] == ref['child_entry'],
                        'fixed word producer core child entry differs')
        else:
            got = ref
        expected_rows.append(dict(boundary='core' if core else 'adapter',
                                  sites=sorted(pc for scope, pc in ref['sites']
                                               if scope == 'main'),
                                  edges=sorted([a, b] for scope, a, b in ref['edges']
                                               if scope == 'main'),
                                  steps=ref['steps'],
                                  ordered_events=len(ref['events']),
                                  independent_output_bytes=independent_bytes))
        if not core:
            output_memory = got['memory']
        del ref
        gc.collect()
    check(output_memory is not None, 'producer adapter output was not retained')
    return dict(rows=expected_rows, memory=output_memory)


def case_edges(rows):
    return {tuple(edge) for row in rows for edge in row['edges']}


def input_hashes():
    paths = {
        'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/inputs.json', 'metadata/oracle.json',
        'metadata/sound-oracle.json', 'metadata/toolchain-lock.json',
        'src/fixed_pattern_drawing.asm',
        'c/fixed_pattern_draw.c', 'c/fixed_pattern_draw.h',
        'c/fixed_word_banks.c', 'c/fixed_word_banks.h',
        'c/mask_generators.c', 'c/mask_generators.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/fixed_pattern_draw.py', 'tests/fixed_word_banks.py',
        'tests/entity_interactions.py', 'tests/sprite_bank.py',
        'tests/entity_sprite_layout.py', 'tests/entity_sprite_planes.py',
        'tests/entity_sprite_shifted.py', 'tests/minimap_vga.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py', 'tools/unpack.py',
    }
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def collect(ref, case, core, independent_bytes):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(pc for scope, pc in ref['sites'] if scope == 'main'),
                edges=sorted([a, b] for scope, a, b in ref['edges'] if scope == 'main'),
                steps=ref['steps'], ordered_events=len(ref['events']),
                independent_plane_bytes=independent_bytes,
                output_segment=ref['regs']['es'], output_offset=ref['regs']['di'],
                producer_bank=case.get('producer_bank'),
                producer_shift=case.get('producer_shift'))


def publish(path, before, rows, producer_rows, mutations=None):
    sites = {pc for row in rows for pc in row['sites']}
    edges = case_edges(rows)
    check(sites == OWN_SITES,
          'campaign did not execute all 556 fixed-pattern instruction sites')
    check(edges == set(), 'fixed-pattern leaf unexpectedly grew a branch edge')
    consumer_handoff = [row for row in rows if row['producer_bank'] is not None]
    report = dict(image='main', image_sha256=sha(IMAGE), entry=ENTRY, ret=RET,
        end=END, translated_code_bytes=END - ENTRY,
        instruction_sites=len(OWN_SITES),
        executed_instruction_addresses=sorted(sites), branch_edges=[],
        branch_edge_count=0, case_count=len(all_cases()), comparison_count=len(rows),
        ordered_events=sum(row['ordered_events'] for row in rows),
        instruction_steps=sum(row['steps'] for row in rows),
        independent_plane_bytes=sum(row['independent_plane_bytes'] for row in rows),
        producer=dict(source='fixed_word_banks', comparison_count=len(producer_rows),
            output_bytes=0x900,
            instruction_sites=sorted({pc for row in producer_rows for pc in row['sites']}),
            branch_edges=sorted([a, b] for a, b in
                                case_edges(producer_rows)),
            ordered_events=sum(row['ordered_events'] for row in producer_rows),
            independent_output_bytes=sum(row['independent_output_bytes']
                                         for row in producer_rows)),
        producer_handoff=dict(bank_count=2, shifts_per_bank=8,
            handoff_case_count=len({row['case'] for row in consumer_handoff}),
            comparison_count=len(consumer_handoff),
            consumed_bytes=sum(0x90 for _ in consumer_handoff),
            independent_plane_bytes=sum(row['independent_plane_bytes']
                                        for row in consumer_handoff)),
        original_only=mutations is None, mutation_count=len(mutations or []),
        mutations=mutations or [], rows=rows, producer_rows=producer_rows,
        input_hashes=before,
        limits=dict(timeout_seconds=WORKER_SECONDS, process_commit_mib=MEMORY_MIB,
                    original_instruction_limit=MAX_STEPS,
                    bus_event_limit=MAX_EVENTS,
                    producer_bus_event_limit=MAX_PROVIDER_EVENTS))
    write_json(path, report)
    print(f"PASS fixed pattern draw: {len(all_cases())} fixtures/{len(rows)} "
          f"boundaries, {len(sites)} sites/{len(edges)} edges, "
          f"{report['ordered_events']} events, "
          f"{len(mutations or [])} mutants", flush=True)


def run_original_campaign():
    before = input_hashes()
    produced = run_producer(None, native_enabled=False)
    rows = []
    for case in all_cases():
        base_memory = produced['memory'] if case.get('producer_bank') is not None else None
        for core in (True, False):
            ref, independent_bytes = compare_original(case, core=core,
                                                       base_memory=base_memory)
            rows.append(collect(ref, case, core, independent_bytes))
            del ref
            gc.collect()
        print('CHECKED original ' + case['name'], flush=True)
    check(before == input_hashes(), 'inputs changed during original campaign')
    publish(ORIGINAL_REPORT, before, rows, produced['rows'])


def compare_original(case, *, core, base_memory=None):
    memory, regs, device = setup(case, base_memory)
    ref = original(case, memory, regs, device, core=core)
    independent_bytes = validate(case, memory, device, regs, ref, core=core)
    return ref, independent_bytes


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == input_hashes(), 'input snapshot differs')
    produced = run_producer(directory, native_enabled=True)
    native = Native(directory)
    rows = []
    for case in all_cases():
        base_memory = produced['memory'] if case.get('producer_bank') is not None else None
        for core in (True, False):
            expected, independent_bytes = compare(native, case, core=core,
                                                   base_memory=base_memory)
            rows.append(collect(expected, case, core, independent_bytes))
            del expected
            gc.collect()
        print('CHECKED native ' + case['name'], flush=True)

    by_name = {case['name']: case for case in all_cases()}
    witnesses = (
        (1, 'forward-independent-if-set', True),
        (2, 'partial-mask-latch-equation', True),
        (3, 'segment-wrap-control-word', True),
        (4, 'backward-independent-df-if-set', True),
        (5, 'partial-mask-latch-equation', True),
        (6, 'producer-bank-1-shift-7', True),
        (7, 'forward-independent-if-set', True),
        (8, 'forward-independent-if-set', True),
        (9, 'forward-independent-if-set', True),
        (10, 'outer-ret-overwritten-by-output', False),
    )
    mutations = []
    handoff_memory = produced['memory']
    for number, name, core in witnesses:
        try:
            compare(Native(directory, number), by_name[name], core=core,
                    base_memory=(handoff_memory if name.startswith('producer-') else None))
        except Mismatch as error:
            mutations.append(dict(mutation=number, case=name, core=core,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'mutation {number} survived its bounded witness')
        gc.collect()
    check(before == input_hashes(), 'inputs changed during native campaign')
    publish(REPORT, before, rows, produced['rows'], mutations)


def main():
    args = sys.argv[1:]
    BUILD.mkdir(exist_ok=True)
    if args == ['--original-worker']:
        run_original_campaign()
        return
    if len(args) == 3 and args[0] == '--worker':
        worker(args[1], args[2])
        return
    if args == ['--original-only']:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    if args:
        raise SystemExit('usage: fixed_pattern_draw.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='fixed-pattern-draw-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(input_hashes(), sort_keys=True))
        run_bounded([sys.executable, __file__, '--worker', str(directory), str(snapshot)],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB,
                    check=True)


if __name__ == '__main__':
    main()
