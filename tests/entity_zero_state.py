"""Bounded original-versus-C checks for the composed 2047 zero-state path."""
import copy
import ctypes as ct
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
from common import BUILD, sha, write_json
from dat_io import REG_NAMES
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as ux
from unpack import ASSET, unpack, relocated


IMAGE, ORACLE = unpack(ASSET.read_bytes())
LOAD = 0x1010
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
SIZE, MASK = 1 << 20, (1 << 20) - 1
ENTRY, CONTINUATION = 0x2047, 0x1FEB
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
INTERACTION_ENTRY, INTERACTION_RET = 0x2EC0, 0x2F3A
TABLE, ROW_PITCH, CALLBACKS = 0x547C, 0x0004, 0x002E
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
ALL_FLAGS, LOGIC_FLAGS = 0x0FD7, 0x0FC7
CF, IF, DF, TF = 0x0001, 0x0200, 0x0400, 0x0100
MAX_INSTRUCTIONS, MAX_EVENTS = 2000, 2048
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-zero-state-differential.json'

OWN_SPANS = ((0x2047, 0x20D6), (0x20E9, 0x2148), (0x2169, 0x21B0))
FINISH_SPANS = ((0x20D6, 0x20E9), (0x2148, 0x2169))
INTERACTION_CALL_SPAN = (0x1FE8, 0x1FEB)
PIXEL_SPAN = (PIXEL_ENTRY, PIXEL_RET + 1)
INTERACTION_SPAN = (INTERACTION_ENTRY, 0x30A6)

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


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
                 'stack_segment', 'stack_offset', 'flags',
                 'continuation', 'status')]


class PcBinding(ct.Structure):
    _fields_ = [('driver_segment', ct.c_uint16)]


class SoundBinding(ct.Structure):
    _fields_ = [('driver_segment', ct.c_uint16), ('driver_kind', ct.c_uint16)]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32,
                     ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The bounded original or a fixture/provider did not complete correctly."""


class NativeMismatch(AssertionError):
    """A completed native execution differs from its completed original."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def read8(memory, segment, offset):
    return memory[physical(segment, offset)]


def write8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def read16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def write16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def sign8(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def map_offsets(xvalue, yvalue, delta):
    x_scaled = (xvalue & 0xFFFF) >> 2
    y_scaled = ((yvalue - 0x10) & 0xFFFF) >> 2
    first = (x_scaled + y_scaled * 0x1A0 + 0x12) & 0xFFFF
    second = (first - 0x340 + sign8(delta) * 2) & 0xFFFF
    return first, second


def flag_mask_after(instruction, prior_mask):
    mnemonic = instruction.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return LOGIC_FLAGS
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return ALL_FLAGS
    if mnemonic in ('inc', 'dec'):
        return (ALL_FLAGS & ~CF) | (prior_mask & CF)
    if mnemonic in ('shr', 'shl', 'sar', 'rol', 'ror'):
        return LOGIC_FLAGS
    if mnemonic == 'mul':
        return (prior_mask & ~0x08D5) | 0x0801
    return prior_mask


def in_span(address, span):
    return span[0] <= address < span[1]


def instruction_maps():
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    own, finish, interaction_call, pixel, interaction = {}, {}, {}, {}, {}
    for address_range, target in ((OWN_SPANS[0], own), (OWN_SPANS[1], own),
                                  (OWN_SPANS[2], own), (FINISH_SPANS[0], finish),
                                  (FINISH_SPANS[1], finish),
                                  (INTERACTION_CALL_SPAN, interaction_call),
                                  (PIXEL_SPAN, pixel),
                                  (INTERACTION_SPAN, interaction)):
        start, end = address_range
        target.update((i.address, i) for i in MD.disasm(IMAGE[start:end], start))
    integrated = dict(own)
    integrated.update(finish)
    integrated.update(interaction_call)
    integrated.update(pixel)
    integrated.update(interaction)
    return loaded, own, finish, interaction_call, pixel, interaction, integrated


LOADED, OWN_INS, FINISH_INS, INTERACTION_CALL_INS, PIXEL_INS, INTERACTION_INS, INTEGRATED_INS = instruction_maps()


def branch_edges(instructions):
    result = set()
    for address, instruction in instructions.items():
        if not instruction.group(capstone.CS_GRP_JUMP):
            continue
        mnemonic = instruction.mnemonic.lower()
        if mnemonic not in ('jmp', 'ljmp'):
            result.add((address, (address + instruction.size) & 0xFFFF))
        if instruction.operands and instruction.operands[-1].type == capstone.x86.X86_OP_IMM:
            result.add((address, instruction.operands[-1].imm & 0xFFFF))
    return result


OWN_EDGES = branch_edges(OWN_INS)


def flags_for(seed, df):
    value = ((0x0A57 ^ (seed * 0x0173)) & ALL_FLAGS) | 2
    value &= ~TF
    return (value | DF) if df else (value & ~DF)


def cases():
    """Focused edge, geometry, ownership, stack, and provider fixtures."""
    rows = [
        dict(name='bounds-lower-zero', x=0x0000, delta=0x00),
        dict(name='bounds-lower-signed-cross', x=0x0010, delta=0xFF),
        dict(name='bounds-low-inclusive', x=0x0010, delta=0x00),
        dict(name='bounds-high-last-pixel', x=0x067F, delta=0x00),
        dict(name='bounds-upper-exclusive', x=0x0680, delta=0x00),
        dict(name='bounds-signed-overflow-sf-of', x=0x7FFF, delta=0x01),
        dict(name='bounds-word-wrap-low', x=0xFFFF, delta=0x01),
        dict(name='empty-form-normal', x=0x0120, delta=0x00,
             up=(0, 0, 0), entity_flags=0xA4, state=0x0100),
        dict(name='empty-form-inactive-edge', x=0x0120, y=0x00B0, delta=0,
             up=(0, 0, 0), entity_flags=0x41, state=0x0020),
        dict(name='up-probe-one-hit', x=0x0120, delta=0,
             up=(1, 0, 0), entity_flags=0),
        dict(name='up-probe-two-hit', x=0x0120, delta=0,
             up=(0, 1, 0), entity_flags=0),
        dict(name='up-probe-three-hit', x=0x0120, delta=0,
             up=(0, 0, 1), entity_flags=0),
        dict(name='residual-low-zero-mask-occupied', x=0x0100, y=0x0010,
             delta=0, initial=1, down=(0, 0, 0, 0, 0, 0, 0), vga=True),
        dict(name='reverse-first-zero', x=0x0200, y=0x0030, delta=0,
             initial=1, down=(0, 1, 1, 1, 1, 1, 1)),
        dict(name='reverse-loop-zero-0', x=0x0200, delta=0,
             initial=1, down=(1, 0, 1, 1, 1, 1, 1)),
        dict(name='reverse-loop-zero-1', x=0x0200, delta=0,
             initial=1, down=(1, 1, 0, 1, 1, 1, 1)),
        dict(name='reverse-loop-zero-2', x=0x0200, delta=0,
             initial=1, down=(1, 1, 1, 0, 1, 1, 1)),
        dict(name='reverse-loop-zero-3', x=0x0200, delta=0,
             initial=1, down=(1, 1, 1, 1, 0, 1, 1)),
        dict(name='reverse-loop-zero-4', x=0x0200, delta=0,
             initial=1, down=(1, 1, 1, 1, 1, 0, 1)),
        dict(name='reverse-loop-zero-5', x=0x0200, delta=0,
             initial=1, down=(1, 1, 1, 1, 1, 1, 0), entity_flags=0),
        dict(name='reverse-transition-bit-clear', x=0x0200, delta=0,
             initial=1, down=(1, 1, 1, 1, 1, 1, 1), entity_flags=0),
        dict(name='reverse-climb-transition', x=0x0200, delta=0,
             initial=1, down=(1, 1, 1, 1, 1, 1, 1), entity_flags=0xA1),
        dict(name='height-signed-jng-overflow', x=0x0200, y=0x8000,
             delta=0, step=0, initial=1, down=(0, 1, 1, 1, 1, 1, 1), vga=True),
        dict(name='height-jng-not-taken', x=0x0200, y=0x0040,
             delta=0, step=0x0010, initial=1, down=(0, 1, 1, 1, 1, 1, 1)),
        dict(name='empty-last-probe-occupied', x=0x0200, delta=0,
             up=(0, 0, 1)),
        dict(name='live-row-pitch-provider', x=0x0200, delta=0,
             up=(0, 0, 0), pitch=0x0050, pitch_after=0x0070,
             provider='pitch-on-first-row-read', vga=True),
        dict(name='live-pixel-ret-word', x=0x0200, delta=0,
             initial=0, up=(0, 0, 0), provider='pixel-return',
             changed_target=0x3456),
        dict(name='live-finish-call-ret-word', x=0x0000, y=0x0030,
             delta=0, provider='finish-return', changed_target=0x4567),
        dict(name='record-offset-wrap', x=0x0200, delta=0,
             ds=0x3100, si=0xFFFE, up=(0, 0, 0)),
        dict(name='record-physical-word-wrap', x=0x0200, delta=0,
             ds=0xFFFF, si=0x000F, up=(0, 0, 0)),
        dict(name='stack-physical-word-wrap', x=0x0200, delta=0,
             ss=0xFFFF, sp=0x0011, up=(0, 0, 0)),
        dict(name='ds-ss-call-push-record-alias', x=0x0200, y=0x0040,
             delta=0, ds=0x5000, ss=0x5000, si=0x6000, sp=0x6004,
             dx=0x0010, up=(0, 0, 0)),
        dict(name='record-row-pitch-alias', x=0x0050, delta=0,
             ds=0x3200, si=0x0004, pitch=0x0050, up=(0, 0, 0)),
        dict(name='record-callback-slot-alias', x=0x0200, delta=0,
             ds=0x3300, si=0x001A, up=(0, 0, 0), entity_flags=0xA5),
        dict(name='df-clear-vga', x=0x0237, delta=0, up=(0, 0, 0),
             df=False, vga=True),
        dict(name='df-set-vga', x=0x0237, delta=0, up=(0, 0, 0),
             df=True, vga=True),
        dict(name='row-product-word-wrap', x=0x0200, y=0x7FFF,
             delta=0, initial=0, up=(0, 0, 0), vga=True),
    ]
    rows = [dict(seed=index, **row) for index, row in enumerate(rows)]
    oracle_require(len(rows) == 37, f'Entity zero-state fixture count changed: {len(rows)}')
    return rows


def initial_registers(case):
    rng = random.Random(0x2047 + case['seed'] * 0x9E3779B1)
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    regs.update(ax=case.get('ax', rng.randrange(0x10000)),
                bx=case.get('bx', rng.randrange(0x10000)),
                cx=case.get('cx', rng.randrange(0x10000)),
                dx=case.get('dx', rng.randrange(0x10000)),
                bp=case.get('bp', rng.randrange(0x10000)),
                cs=LOAD, ip=ENTRY,
                ds=case.get('ds', DATA_SEGMENT),
                es=case.get('es', 0x6200),
                ss=case.get('ss', 0x5000),
                si=case.get('si', 0x5000),
                sp=case.get('sp', 0x8000),
                flags=flags_for(case['seed'], case.get('df', False)))
    return regs


def configure_device(seed):
    device = MinimapVga(seed, read_map=0)
    device.seq[2] = 0x0F
    device.seq[4] = 0x06
    device.gc[0] = device.gc[1] = device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    device.planes[0][:] = bytes(65536)
    return device


def set_plane_word(device, offset, value, plane=0):
    device.planes[plane][offset & 0xFFFF] = value & 0xFF
    device.planes[plane][(offset + 1) & 0xFFFF] = (value >> 8) & 0xFF


def setup(case):
    rng = random.Random(0x5A1E + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    memory[LOAD << 4:(LOAD << 4) + len(LOADED)] = LOADED
    regs = initial_registers(case)
    # Interaction-cell reads are deliberately neutral, so the integrated
    # 1FE8 -> 2EC0 CALL returns without entering sound/device services.
    ssbase = regs['ss'] << 4
    for offset in range(0x10000):
        memory[(ssbase + offset) & MASK] = 0
    ds, si = regs['ds'], regs['si']
    write16(memory, ds, si, case.get('x', 0x0200))
    write16(memory, ds, (si + 2) & 0xFFFF, case.get('y', 0x0030))
    write16(memory, ds, (si + 4) & 0xFFFF, case.get('record_word_4', 0x1234))
    write16(memory, ds, (si + 6) & 0xFFFF, case.get('step', 0))
    write16(memory, ds, (si + 8) & 0xFFFF, case.get('state', 0))
    write8(memory, ds, (si + 0x23) & 0xFFFF, case.get('marker', 0x59))
    write8(memory, ds, (si + 0x24) & 0xFFFF, case.get('entity_flags', 0))
    write8(memory, ds, (si + 0x26) & 0xFFFF, case.get('active', 0))
    write8(memory, ds, (si + 0x27) & 0xFFFF, case.get('delta', 0))
    write8(memory, ds, (si + 0x28) & 0xFFFF, case.get('animation', 0xFD))
    write8(memory, ds, (si + 0x29) & 0xFFFF, case.get('frame', 0xA7))
    write8(memory, ds, (si + 0x2A) & 0xFFFF, case.get('palette', 0x34))
    write8(memory, ds, (si + 0x2B) & 0xFFFF, 0)
    write8(memory, ds, (si + 0x2C) & 0xFFFF, 0)
    write16(memory, ds, ROW_PITCH, case.get('pitch', 0x0050))
    write16(memory, ds, CALLBACKS, case.get('callback0', 0x1ABC))
    write16(memory, ds, CALLBACKS + 2, case.get('callback1', 0x2BCD))
    if ds == DATA_SEGMENT:
        oracle_require(bytes(memory[physical(ds, TABLE) + n] for n in range(8)) ==
                       PIXEL_MASKS,
                       'Pinned pixel mask table identity changed')
    else:
        for index, value in enumerate(case.get('masks', PIXEL_MASKS)):
            write8(memory, ds, TABLE + index, value)

    # The real 2EC0 child examines two SS interaction bytes after a finish
    # CALL. Seed the entire ordinary-RAM map segment to zero, then restore
    # any record/stack values that intentionally alias it.
    first_map, second_map = map_offsets(case.get('x', 0x0200),
                                        case.get('y', 0x0030),
                                        case.get('delta', 0))
    write8(memory, regs['ss'], first_map, 0)
    write8(memory, regs['ss'], second_map, 0)
    put_return = case.get('return_word', 0x7777)
    write16(memory, regs['ss'], regs['sp'], put_return)

    device = configure_device(0x2047 + case['seed']) if case.get('vga') else None
    plan = pixel_plan(case, memory, regs)
    if plan is not None:
        addresses = sample_addresses(case, plan)
        samples = sample_values(case)
        for address, occupied in addresses:
            raw = plan['mask'] if occupied else 0
            if device is not None:
                device.planes[0][address & 0xFFFF] = raw
            else:
                memory[(VGA_BASE + (address & 0xFFFF)) & MASK] = raw

    # Map cells need to be zero even in cases where SS:SI overlaps the map.
    # Re-seed only the actual cell bytes after record/pixel fixture construction.
    if case.get('provider') == 'finish-return':
        final_x = (case.get('x', 0x0200) + sign8(case.get('delta', 0))) & 0xFFFF
        final_delta = (-case.get('delta', 0)) & 0xFF
        map_first, _ = map_offsets(final_x, case.get('y', 0x0030), final_delta)
        write8(memory, regs['ss'], map_first, 0)
    return memory, regs, device, plan


def pixel_plan(case, memory, regs):
    """Compute the child byte/mask from the live stack aliases it will see."""
    projected = bytearray(memory)
    ds, si = regs['ds'], regs['si']
    xvalue = read16(projected, ds, si)
    marker = read8(projected, ds, (si + 0x27) & 0xFFFF)
    x_after = (xvalue + sign8(marker)) & 0xFFFF
    write16(projected, ds, si, x_after)
    if not (0x0010 <= x_after < 0x0680):
        return None

    call_sp = (regs['sp'] - 2) & 0xFFFF
    write16(projected, regs['ss'], call_sp, 0x206B)
    yvalue = read16(projected, ds, (si + 2) & 0xFFFF)
    child_sp = (call_sp - 2) & 0xFFFF
    write16(projected, regs['ss'], child_sp, regs['dx'])
    child_x = read16(projected, ds, si)
    row = (yvalue - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    product = (row * 0x00D0) & 0xFFFF
    mask = read8(projected, ds, TABLE + (child_x & 7))
    start = (product + (child_x >> 3) + 0x4A40) & 0xFFFF
    return dict(x=child_x, y=yvalue, product=product, mask=mask, start=start,
                return_stack=call_sp, child_stack=child_sp)


def sample_values(case):
    # Index zero is the first sample, then the three forward or seven reverse
    # candidates. Occupied values are the exact live mask from the table.
    return (case.get('initial', 0), tuple(case.get('up', (0, 0, 0))),
            tuple(case.get('down', (0, 0, 0, 0, 0, 0, 0))))


def sample_addresses(case, plan):
    initial, up, down = sample_values(case)
    pitch = case.get('pitch', 0x0050)
    after = case.get('pitch_after', pitch)
    schedule = [pitch] + [after] * 8
    addresses = [(plan['start'], initial)]
    cursor = plan['start']
    for value, step in zip(up, schedule):
        cursor = (cursor + step) & 0xFFFF
        addresses.append((cursor, value))
    cursor = plan['start']
    for index, value in enumerate(down):
        step = schedule[min(index, len(schedule) - 1)]
        cursor = (cursor - step) & 0xFFFF
        addresses.append((cursor, value))
    return addresses


class Access:
    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events, self.used, self.pending = [], set(), []
        self.mirror = None
        self.read_counts = {}
        ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']
        self.pitch_high = physical(ds, ROW_PITCH + 1)
        self.table = physical(ds, TABLE + (case.get('x', 0x0200) & 7))
        self.call_word = physical(ss, (sp - 2) & 0xFFFF)
        if case.get('provider') == 'finish-return':
            xvalue = (case.get('x', 0x0200) + sign8(case.get('delta', 0))) & 0xFFFF
            changed_delta = (-case.get('delta', 0)) & 0xFF
            first, _ = map_offsets(xvalue, case.get('y', 0x0030), changed_delta)
            self.finish_map = physical(ss, first)
        else:
            self.finish_map = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror:
            self.mirror(address, value & 0xFF)

    def apply_provider(self, name):
        case = self.case
        if name in self.used:
            return
        if name == 'pitch-on-first-row-read':
            self.store(physical(self.regs['ds'], ROW_PITCH),
                       case.get('pitch_after', 0x0070) & 0xFF)
            self.store(physical(self.regs['ds'], ROW_PITCH + 1),
                       (case.get('pitch_after', 0x0070) >> 8) & 0xFF)
        elif name in ('pixel-return', 'finish-return'):
            self.store(self.call_word, case.get('changed_target', 0x3456) & 0xFF)
            self.store(self.call_word + 1,
                       (case.get('changed_target', 0x3456) >> 8) & 0xFF)
        self.used.add(name)

    def apply_pending(self):
        pending, self.pending = self.pending, []
        for name in pending:
            self.apply_provider(name)

    def access(self, kind, address, flags, flag_mask, value=None, *, deferred=False):
        if len(self.events) >= MAX_EVENTS:
            raise OracleFailure('original/native memory access budget exhausted')
        address &= MASK
        case = self.case
        if kind == 'read':
            if self.device and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
            else:
                value = self.memory[address]
        else:
            value &= 0xFF
            if self.device and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            else:
                self.memory[address] = value
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF,
                            flag_mask & 0xFFFF))
        if kind == 'read':
            count = self.read_counts.get(address, 0) + 1
            self.read_counts[address] = count
            provider = case.get('provider')
            if (provider == 'pitch-on-first-row-read' and address == self.pitch_high and
                    'pitch-on-first-row-read' not in self.used):
                if deferred:
                    self.pending.append('pitch-on-first-row-read')
                else:
                    self.apply_provider('pitch-on-first-row-read')
            elif provider == 'pixel-return' and address == self.table and 'pixel-ret' not in self.used:
                if deferred:
                    self.pending.append('pixel-return')
                else:
                    self.apply_provider('pixel-return')
                self.used.add('pixel-ret')
            elif provider == 'finish-return' and address == self.finish_map and 'finish-ret' not in self.used:
                if deferred:
                    self.pending.append('finish-return')
                else:
                    self.apply_provider('finish-return')
                self.used.add('finish-ret')
        return value & 0xFF


class OriginalRun:
    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, SIZE * 2)
        self.cpu.mem_write(0, bytes(memory))
        self.cpu.mem_write(SIZE, bytes(memory))
        for name in REG_NAMES:
            self.cpu.reg_write(getattr(ux, f'UC_X86_REG_{name.upper()}'), regs[name])
        self.cpu.reg_write(ux.UC_X86_REG_EFLAGS, regs['flags'])
        self.access = Access(case, memory, regs, device)
        self.access.mirror = self.mirror
        self.previous = None
        self.current_flags, self.current_mask = regs['flags'], ALL_FLAGS
        self.sites, self.own_sites, self.edges, self.own_edges = set(), set(), set(), set()
        self.steps, self.stopped, self.failure = 0, False, None
        self.status, self.continuation = None, None

        def code(uc, _address, _size, _user):
            self.on_code(uc)

        def on_read(uc, _kind, address, size, _value, _user):
            try:
                for delta in range(size):
                    linear = address + delta
                    if not 0 <= linear < SIZE * 2:
                        raise OracleFailure('original read outside mapped memory')
                    p = linear & MASK
                    value = self.access.access('read', p, self.current_flags,
                                               self.current_mask, deferred=True)
                    self.mirror(p, value)
                if self.access.pending:
                    # Providers fire only after the memory operand has read.
                    # The next code hook is after this instruction completes.
                    pass
            except BaseException as error:
                self.failure = f'original read provider failed: {error}'
                uc.emu_stop()

        def on_write(uc, _kind, address, size, value, _user):
            try:
                for delta in range(size):
                    linear = address + delta
                    if not 0 <= linear < SIZE * 2:
                        raise OracleFailure('original write outside mapped memory')
                    p = linear & MASK
                    byte = (value >> (delta * 8)) & 0xFF
                    self.access.access('write', p, self.current_flags,
                                        self.current_mask, byte)
                    self.mirror(p, byte)
            except BaseException as error:
                self.failure = f'original write provider failed: {error}'
                uc.emu_stop()

        self.callbacks = (code, on_read, on_write)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, on_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)

    def mirror(self, address, value):
        address &= MASK
        self.cpu.mem_write(address, bytes((value & 0xFF,)))
        self.cpu.mem_write(address + SIZE, bytes((value & 0xFF,)))

    def stop(self, status, continuation):
        self.status, self.continuation = status, continuation & 0xFFFF
        self.stopped = True
        self.cpu.emu_stop()

    def on_code(self, cpu):
        self.steps += 1
        if self.steps > MAX_INSTRUCTIONS:
            self.failure = 'original instruction hook budget exhausted'
            cpu.emu_stop()
            return
        cs = cpu.reg_read(ux.UC_X86_REG_CS) & 0xFFFF
        ip = cpu.reg_read(ux.UC_X86_REG_IP) & 0xFFFF
        if self.previous is not None:
            previous = self.previous
            if previous.group(capstone.CS_GRP_JUMP):
                self.edges.add((previous.address, ip))
                if previous.address in OWN_INS:
                    self.own_edges.add((previous.address, ip))
            self.current_mask = flag_mask_after(previous, self.current_mask)
            if previous.mnemonic.lower() == 'ret':
                if previous.address == PIXEL_RET and ip != 0x206B:
                    self.stop(7, ip)
                    return
                if previous.address == INTERACTION_RET and ip != CONTINUATION:
                    self.stop(5, ip)
                    return
            self.access.apply_pending()

        if cs != LOAD:
            self.failure = f'original escaped main CS at {cs:04x}:{ip:04x}'
            cpu.emu_stop()
            return
        if ip == CONTINUATION:
            self.stop(0, ip)
            return
        instruction = INTEGRATED_INS.get(ip)
        if instruction is None:
            self.failure = f'original escaped declared code at {cs:04x}:{ip:04x}'
            cpu.emu_stop()
            return
        expected = LOADED[ip:ip + instruction.size]
        actual = bytes(cpu.mem_read(physical(cs, ip), instruction.size))
        if actual != expected:
            self.failure = (f'original code changed at {cs:04x}:{ip:04x}: '
                            f'{actual.hex()}/{expected.hex()}')
            cpu.emu_stop()
            return
        self.current_flags = cpu.reg_read(ux.UC_X86_REG_EFLAGS) & 0xFFFF
        self.sites.add(ip)
        if ip in OWN_INS:
            self.own_sites.add(ip)
        self.previous = instruction

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs['cs'], ENTRY), 0,
                               count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: original Unicorn failed: {error}') from error
        oracle_require(self.stopped and self.failure is None,
                       f'{self.case["name"]}: {self.failure or "original did not reach a boundary"}')
        state = {name: self.cpu.reg_read(getattr(ux, f'UC_X86_REG_{name.upper()}')) & 0xFFFF
                 for name in REG_NAMES}
        state['flags'] = self.cpu.reg_read(ux.UC_X86_REG_EFLAGS) & 0xFFFF
        final_memory = bytes(self.cpu.mem_read(0, SIZE))
        oracle_require(final_memory == bytes(self.memory),
                       f'{self.case["name"]}: original RAM mirror differs')
        oracle_require(len(self.access.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original access budget exhausted')
        if self.case.get('provider'):
            provider_key = {'pitch-on-first-row-read': 'pitch-on-first-row-read',
                            'pixel-return': 'pixel-ret',
                            'finish-return': 'finish-ret'}[self.case['provider']]
            oracle_require(provider_key in self.access.used,
                           f'{self.case["name"]}: declared provider did not fire')
        return dict(memory=final_memory, regs=state, events=self.access.events,
                    device=self.device, sites=self.sites, own_sites=self.own_sites,
                    edges=self.edges, own_edges=self.own_edges,
                    status=self.status, continuation=self.continuation,
                    flag_mask=self.current_mask, steps=self.steps,
                    providers=sorted(self.access.used))


class NativeBus:
    def __init__(self, memory, device, case, regs):
        self.memory, self.device = memory, device
        self.access = Access(case, memory, regs, device)

        def read(_context, _mem, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native entity-zero-state access budget exhausted')
                return self.access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                worker_exit(CALLBACK_EXIT, f'native read callback failed: {error}')
                return 0

        def write(_context, _mem, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native entity-zero-state access budget exhausted')
                self.access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                worker_exit(CALLBACK_EXIT, f'native write callback failed: {error}')

        def out(_context, port, value, flags):
            worker_exit(CALLBACK_EXIT,
                        f'unexpected zero-state raster OUT {port:04x}={value:04x}/{flags:04x}')

        self.callbacks = (READ(read), WRITE(write), OUT(out))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-zero-state-m{mutation}.dll',
                     mutation, 'entity_zero_state')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_zero_state_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(PcBinding),
                              ct.POINTER(SoundBinding), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_zero_state_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(PcBinding),
                                 ct.POINTER(SoundBinding), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16


def c_buffer(memory):
    return (ct.c_uint8 * SIZE).from_buffer(memory)


def native_run(native, case, initial, initial_regs, initial_device, *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    bus = NativeBus(memory, device, case, initial_regs)
    ram = c_buffer(memory)
    if core:
        call = Call(*(initial_regs[name] for name in
            ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')))
        result = native.core(ram, ct.byref(call), None, None, ct.byref(bus.bus))
        state = dict(initial_regs)
        state.update(ax=result.value, bx=result.map_cursor, cx=result.count,
                     dx=result.auxiliary_value, si=result.record_cursor,
                     di=result.object_cursor, bp=result.candidate_y,
                     cs=result.code_segment, ds=result.data_segment,
                     es=result.extra_segment, ss=result.stack_segment,
                     sp=result.stack_offset, ip=result.continuation,
                     flags=result.flags)
        status = result.status
        continuation = result.continuation
    else:
        live = Regs(**{name: initial_regs[name] for name in REG_NAMES},
                    flags=initial_regs['flags'])
        status = native.adapter(ram, ct.byref(live), None, None,
                                ct.byref(bus.bus))
        state = {name: getattr(live, name) for name in REG_NAMES}
        state['flags'] = live.flags
        continuation = state['ip']
    return dict(memory=bytes(memory), regs=state, device=device,
                events=bus.access.events, providers=sorted(bus.access.used),
                status=status, continuation=continuation)


def compare_events(case, actual, expected):
    require(len(actual) == len(expected),
            f'{case["name"]}: memory-event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        if got[:3] != want[:3]:
            raise NativeMismatch(f'{case["name"]}: memory event {index} differs: '
                                 f'{got[:3]!r}/{want[:3]!r}')
        if ((got[3] ^ want[3]) & want[4]) != 0:
            raise NativeMismatch(f'{case["name"]}: event {index} flags differ: '
                                 f'{got[3]:04X}/{want[3]:04X} under {want[4]:04X}')


def compare_device(case, actual, expected):
    if expected is None:
        require(actual is None, f'{case["name"]}: unexpected VGA device')
        return
    require(actual.state() == expected.state(),
            f'{case["name"]}: planar VGA state differs')
    got = [(event[0], event[1], event[2]) for event in actual.trace]
    wanted = [(event[0], event[1], event[2]) for event in expected.trace]
    require(got == wanted, f'{case["name"]}: VGA read trace differs')


def independent_observations(case, initial, regs, plan, original):
    """Small geometric/record checks independent from the C-vs-Unicorn diff."""
    name = case['name']
    if name == 'residual-low-zero-mask-occupied':
        oracle_require(plan is not None and plan['product'] & 0xFF == 0 and
                       plan['mask'] == 0x80 and plan['y'] == 0x0010,
                       name + ': fixture does not preserve zero product AL plus mask AH')
        oracle_require(0x2073 in original['own_sites'] and
                       (0x2073, 0x20E9) in original['own_edges'],
                       name + ': original did not take the occupied initial-pixel branch')
    if name == 'empty-form-normal':
        output = original['memory']
        ds, si = regs['ds'], regs['si']
        expected = {0x08: 0x0004, 0x0A: 0, 0x0C: 0x0A42,
                    0x10: 0x005A, 0x12: 0x003C, 0x04: 0xFFF8,
                    0x06: 0xFFF6}
        expected[0x08] |= case.get('state', 0)
        for displacement, value in expected.items():
            oracle_require(read16(output, ds, (si + displacement) & 0xFFFF) == value,
                           name + f': independent empty-state field +{displacement:02X} differs')
        oracle_require(read16(output, ds, (si + 0x14) & 0xFFFF) ==
                       case.get('callback0', 0x1ABC),
                       name + ': transition did not copy callback slot zero')
    if name == 'reverse-climb-transition':
        output = original['memory']
        ds, si = regs['ds'], regs['si']
        oracle_require(read16(output, ds, (si + 8) & 0xFFFF) & 0x20 and
                       read16(output, ds, (si + 0x0C) & 0xFFFF) == 0x039A and
                       read16(output, ds, (si + 0x14) & 0xFFFF) ==
                       case.get('callback1', 0x2BCD),
                       name + ': independent climb-transition fields differ')
    if name == 'bounds-signed-overflow-sf-of':
        x_after = (case['x'] + sign8(case['delta'])) & 0xFFFF
        result = (x_after - 0x10) & 0xFFFF
        overflow = bool(((x_after ^ 0x10) & (x_after ^ result) & 0x8000))
        oracle_require(x_after == 0x8000 and result == 0x7FF0 and overflow and
                       not (result & 0x8000),
                       name + ': fixture misses CMP SF=0 / OF=1 signed edge')
    if name == 'height-signed-jng-overflow':
        oracle_require(original['continuation'] == CONTINUATION and
                       (0x2151, 0x2156) in original['edges'],
                       name + ': expected signed JNG overflow edge was not observed')


def compare_case(native, case, *, core):
    initial, regs, device, plan = setup(case)
    oracle = OriginalRun(case, bytearray(initial), dict(regs),
                         copy.deepcopy(device)).run()
    independent_observations(case, initial, regs, plan, oracle)
    actual = native_run(native, case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == oracle['status'],
            f'{label}: status {actual["status"]}/{oracle["status"]}')
    require(actual['continuation'] == oracle['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{oracle["continuation"]:04X}')
    for name in REG_NAMES:
        got = actual['regs'][name]
        want = oracle['regs'][name]
        require(got == want,
                f'{label}: {name} {got:04X}/{want:04X}')
    flags_mask = oracle['flag_mask']
    require(((actual['regs']['flags'] ^ oracle['regs']['flags']) & flags_mask) == 0,
            f'{label}: flags {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {flags_mask:04X}')
    require(actual['memory'] == oracle['memory'], label + ': full 1 MiB RAM differs')
    compare_events(case, actual['events'], oracle['events'])
    compare_device(case, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['providers'],
            f'{label}: provider use differs {actual["providers"]}/{oracle["providers"]}')
    if case.get('provider') == 'pixel-return':
        oracle_require(oracle['status'] == 7 and oracle['continuation'] ==
                       case.get('changed_target'),
                       case['name'] + ': actual pixel RET alias was not observed')
    if case.get('provider') == 'finish-return':
        oracle_require(oracle['status'] == 5 and oracle['continuation'] ==
                       case.get('changed_target'),
                       case['name'] + ': actual finish CALL return alias was not observed')
    return oracle


def input_hashes():
    paths = (
        'src/game_code.asm', 'src/program.asm', 'assets/vgalemmi.exe',
        'metadata/symbols.json', 'metadata/hints.json', 'metadata/regions.json',
        'metadata/inputs.json',
        'c/entity_zero_state.c', 'c/entity_zero_state.h',
        'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_pixel.c', 'c/entity_pixel.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'c/regs.h',
        'tests/entity_zero_state.py', 'tests/minimap_vga.py',
        'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/bounded_process.py', 'tools/unpack.py', 'tools/common.py',
        'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(len(IMAGE) == 82906 and sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(sum(end - start for start, end in OWN_SPANS) == 309 and
                   len(OWN_INS) == 104,
                   f'Owned zero-state accounting changed: {len(OWN_INS)} sites')
    oracle_require(len(OWN_EDGES) == 33,
                   f'Owned zero-state direct CFG edge count changed: {len(OWN_EDGES)}')
    oracle_require(IMAGE[0xEF0C:0xEF14] == PIXEL_MASKS,
                   'Pinned live pixel mask table bytes changed')

    fixtures = cases()
    baseline = Native(directory)
    coverage, edges, integrated_sites, integrated_edges = set(), set(), set(), set()
    total_events, rows = 0, []
    for case in fixtures:
        row_sites, row_edges, row_integrated, row_integrated_edges = set(), set(), set(), set()
        case_events = 0
        for core in (True, False):
            oracle = compare_case(baseline, case, core=core)
            row_sites.update(oracle['own_sites'])
            row_edges.update(oracle['own_edges'])
            row_integrated.update(oracle['sites'])
            row_integrated_edges.update(oracle['edges'])
            case_events += len(oracle['events'])
            del oracle
        coverage.update(row_sites)
        edges.update(row_edges)
        integrated_sites.update(row_integrated)
        integrated_edges.update(row_integrated_edges)
        total_events += case_events
        rows.append(dict(name=case['name'], core_and_adapter=True,
                         own_instruction_addresses=sorted(row_sites),
                         own_branch_edges=sorted(row_edges),
                         integrated_main_sites=sorted(row_integrated),
                         integrated_branch_edges=sorted(row_integrated_edges),
                         memory_events=case_events, vga=bool(case.get('vga')),
                         df=bool(case.get('df', False)),
                         provider=case.get('provider')))
        gc.collect()

    oracle_require(coverage == set(OWN_INS),
                   f'Original zero-state site coverage differs: missing={sorted(set(OWN_INS)-coverage)}')
    oracle_require(edges == OWN_EDGES,
                   f'Original zero-state branch union differs: missing={sorted(OWN_EDGES-edges)}, '
                   f'extra={sorted(edges-OWN_EDGES)}')

    witnesses = {
        1: 'empty-last-probe-occupied',
        2: 'live-row-pitch-provider',
        3: 'reverse-loop-zero-5',
        4: 'reverse-climb-transition',
        5: 'height-signed-jng-overflow',
        6: 'empty-form-normal',
        7: 'empty-form-normal',
        8: 'live-pixel-ret-word',
    }
    mutations = []
    for mutation, case_name in witnesses.items():
        mutant = Native(directory, mutation)
        case = next(item for item in fixtures if item['name'] == case_name)
        try:
            compare_case(mutant, case, core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=case_name,
                                  mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'Entity zero-state mutation {mutation} survived its '
                                f'completed witness {case_name}')
        del mutant
        gc.collect()

    after = input_hashes()
    oracle_require(after == before, 'Hashed source, oracle, or runner inputs changed during campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        case_count=len(fixtures), comparisons=len(fixtures) * 2,
        cases=rows, translated_code_bytes=309, instruction_site_count=104,
        native_code_ranges=[[start, end] for start, end in OWN_SPANS],
        executed_instruction_addresses=sorted(coverage),
        branch_edges=sorted(edges), static_branch_edges=sorted(OWN_EDGES),
        integrated_main_instruction_addresses=sorted(integrated_sites),
        integrated_main_branch_edges=sorted(integrated_edges),
        total_memory_events=total_events, mutation_count=len(mutations),
        mutations_detected=mutations, input_hashes=before,
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_tree_mib=640,
                    original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    original_and_native_access_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        entry_flags_contract='normalized fully represented FLAGS; TF clear; DF varied and preserved; '
                             'final flags compared only under the original instruction-defined mask',
        stop_contract='Core and adapter comparisons stop before shared 1FEB; changed actual pixel '
                      'RET and finish CALL return stop before the provider-selected target',
        domain='2047..20D5, 20E9..2147 and 2169..21AF (309 owned bytes, 104 sites, 33 direct '
               'edges), composed through actual 5DC6 CALL/RET and shared 20D6/20E2/2148 finish '
               'paths plus neutral-map 1FE8/2EC0 CALL/RET. Covers signed X bounds, wrapped pixel '
               'coordinates and row pitch, all forward/reverse probe branch outcomes, empty/climb '
               'record writes, live stack/record aliases, provider-updated pitch/return words, '
               'DF-preserving RAM/VGA samples, full 1 MiB RAM and ordered access traces. '
               'No gameplay readiness, sound/interrupt service, or VGA mode-setup claim.'))
    print(f'PASS entity zero state: {len(fixtures)} fixtures at core+adapter; '
          f'309 bytes/{len(coverage)} owned sites/{len(edges)} edges; '
          f'{len(integrated_sites)} integrated main sites/{total_events} events; '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-zero-state arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-zero-state-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
