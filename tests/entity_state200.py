"""Bounded original-versus-C checks for the 287D..2A6C state-0200 parent."""
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
import entity_mask as mask_leaf
import entity_mask_rows as mask_rows
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END, MAIN_SEG = 0x287D, 0x2A6D, interactions.MAIN_SEG
MASK_ENTRY, MASK_RET = 0x5FAC, 0x606A
COORD_ENTRY, COORD_RET = 0x6141, 0x616F
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9),
                (0x2148, 0x2169))
BUFFER_SEGMENT = 0x7000
CONTINUATION = 0x1FEB
ROW_PITCH, MASK_TABLE = 0x0004, 0x547C
MAX_INSTRUCTIONS, MAX_EVENTS = 4096, 4096
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state200-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state200-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, END)
MASK_INS = mask_rows.INS[mask_rows.TEN]
COORD_INS = decoded_span(COORD_ENTRY, COORD_RET + 1)
PIXEL_INS = decoded_span(PIXEL_ENTRY, PIXEL_RET + 1)
FINISH_INS = {ins.address: ins for start, end in FINISH_SPANS
              for ins in MD.disasm(IMAGE[start:end], start)}
INTEGRATED_INS = dict(OWN_INS)
for group in (MASK_INS, COORD_INS, PIXEL_INS, FINISH_INS,
              interactions.MAIN_INS):
    INTEGRATED_INS.update(group)


def own_edges(instructions):
    result = set()
    for address, ins in instructions.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            result.add((address, (address + ins.size) & 0xFFFF))
        if (ins.operands and
                ins.operands[-1].type == capstone.x86.X86_OP_IMM):
            result.add((address, ins.operands[-1].imm & 0xFFFF))
    return result


OWN_EDGES = own_edges(OWN_INS)


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
    """A bounded original/provider did not reach its declared boundary."""


class NativeMismatch(AssertionError):
    """Only a completed original/native mismatch can credit a mutant."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


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


def signed8(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def map_offset(x, y, delta):
    qx = (x & 0xFFFF) >> 2
    qy = (((y - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12 - 0x340 + 2 * signed8(delta)) & 0xFFFF


def interaction_map_offset(x, y):
    qx = (x & 0xFFFF) >> 2
    qy = (((y - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12) & 0xFFFF


def pixel_offset(x, y):
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    return ((row * 0xD0) + ((x & 0xFFFF) >> 3) + 0x4A40) & 0xFFFF


def coordinate_offset(x, y):
    return (((y - 0x10) & 0xFFFF) * 0xD0 +
            ((x & 0xFFFF) >> 3) + 0x4A40) & 0xFFFF


def cases():
    """Focused cadence, three-sample, map, child and interrupt fixtures."""
    rows = [
        dict(name='cadence-increment-ordinary-return', phase=0),
        dict(name='cadence-exact-two-masks-and-returns', phase=1),
        dict(name='cadence-three-mask-return', phase=2),
        dict(name='cadence-four-mask-return', phase=3),
        dict(name='cadence-five-four-clear-coordinates-transition', phase=4,
             x=4, y=0x40, delta=1, coord_hit=-1),
        dict(name='cadence-five-first-coordinate-hit', phase=4,
             x=4, y=0x40, delta=1, coord_hit=0),
        dict(name='cadence-five-second-coordinate-hit', phase=4,
             x=4, y=0x40, delta=1, coord_hit=1),
        dict(name='cadence-five-third-coordinate-hit', phase=4,
             x=4, y=0x40, delta=1, coord_hit=2),
        dict(name='cadence-five-fourth-coordinate-hit', phase=4,
             x=4, y=0x40, delta=1, coord_hit=3),
        dict(name='ten-row-mask-incoming-readback-mode-one', phase=1,
             x=0x20, y=0x40, gc5=0x08, gc7=0x08, gc2=0x08,
             seq_mask=0x0F, read_map=0, vga_mode_one=True),
        dict(name='cadence-six-mask-is-skipped', phase=5),
        dict(name='cadence-onef-mask-wraps-low', phase=0x1E),
        dict(name='cadence-byte-wrap', phase=0xFF),
        dict(name='separate-rmw-rereads-live-cadence', phase=3,
             provider='cadence-rewrite', replacement_phase=9),
        dict(name='mask-returned-ds-raw-phase-reread', phase=4,
             provider='mask-live-ds', alternate_ds=0x6100),
        dict(name='mask-actual-call-return-changed', phase=3,
             provider='mask-return', changed_target=0x616F),
        dict(name='coordinate-live-saved-registers', phase=4,
             x=4, y=0x40, delta=1, coord_hit=0,
             provider='coordinate-pop-bx', replacement_bx=0xBEEF),
        dict(name='coordinate-actual-call-return-changed', phase=4,
             x=4, y=0x40, delta=1, coord_hit=0,
             provider='coordinate-return', changed_target=0x28D6),
        dict(name='high-boundary-underflow-x', phase=0x0A, x=0x000F,
             delta=0),
        dict(name='high-boundary-lower-equal', phase=0x0A, x=0x0010,
             delta=0),
        dict(name='high-boundary-upper-equal', phase=0x0A, x=0x067F,
             delta=0),
        dict(name='high-boundary-upper-exclusive', phase=0x0A, x=0x0680,
             delta=0),
        dict(name='signed-record-delta-negative-one', phase=0x0A,
             x=0x20, y=0x40, delta=0xFF, first_pixel=True,
             map_nibble=7),
        dict(name='first-pixel-clear-second-collision', phase=0x0A,
             x=0x20, y=0x40, delta=0, pixel_samples=(0, 0xFF, 0),
             map_nibble=1),
        dict(name='first-two-pixels-clear-third-collision', phase=0x0A,
             x=0x20, y=0x40, delta=0, pixel_samples=(0, 0, 0xFF),
             map_nibble=1),
        dict(name='all-three-pixels-clear-transition', phase=0x0A,
             x=0x20, y=0x40, delta=0, pixel_samples=(0, 0, 0)),
        dict(name='pitch-reread-after-pixel-call', phase=0x0A,
             x=0x20, y=0x40, delta=0, pitch=0x10,
             pitch_after=0x20, pixel_samples=(0, 0xFF, 0),
             provider='pitch-after-pixel-table'),
        dict(name='map-nibble-seven-positive-direction', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True, map_nibble=7),
        dict(name='map-nibble-seven-negative-direction', phase=0x0A,
             x=0x20, y=0x40, delta=0xFF, first_pixel=True, map_nibble=7),
        dict(name='map-nibble-eight-positive-direction', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True, map_nibble=8),
        dict(name='map-nibble-eight-negative-direction', phase=0x0A,
             x=0x20, y=0x40, delta=0xFF, first_pixel=True, map_nibble=8),
        dict(name='map-nibble-other-shared-interaction', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True, map_nibble=3),
        dict(name='map-index-aliases-live-push-ax', phase=0x0A,
             x=0x24, y=0x40, delta=0, first_pixel=True,
             map_nibble=9, ss=0x6000),
        dict(name='nibble-nine-disabled-driver', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0, options=3),
        dict(name='nibble-nine-options-clear', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0xFF, options=0),
        dict(name='nibble-nine-bound-sound-service', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0xFF, options=3),
        dict(name='nibble-nine-unbound-sound-vector', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0xFF, options=3,
             sound_vector=(0, 0x6200)),
        dict(name='nibble-nine-changed-sound-iret', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0xFF, options=3,
             provider='sound-return', changed_target=0x4567),
        dict(name='nibble-nine-sound-returned-ds-before-neg', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0xFF, options=3,
             provider='sound-live-ds', alternate_ds=0x6100),
        dict(name='nibble-nine-second-option-bit', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=9, enabled=0xFF, options=2),
        dict(name='finish-interaction-pc-service', phase=0x0A,
             x=0x20, y=0x40, delta=1, first_pixel=True,
             map_nibble=1, interaction_nibble=1, record_bits=0,
             enabled=0, options=1),
        dict(name='pixel-call-live-ret-overwrite', phase=0x0A,
             x=0x20, y=0x40, delta=0, first_pixel=True,
             provider='pixel-return', changed_target=0x616F),
        dict(name='entry-df-and-rmw-flags', phase=0x0A,
             x=0x20, y=0x40, delta=0x80, first_pixel=True,
             map_nibble=7, df=True, flags=0x0E47),
        dict(name='word-and-physical-stack-wrap', phase=4, x=4, y=0x40,
             delta=1, coord_hit=0, ss=0xFFFF, sp=0x0011),
        dict(name='record-and-stack-ss-ds-alias', phase=4, x=4, y=0x40,
             delta=1, coord_hit=-1, ds=0x5000, ss=0x5000,
             si=0x8000, sp=0xD000),
        dict(name='poisoned-live-registers-and-ram', phase=0x0A,
             poison=True, seed=0x200A, x=0x20, y=0x40, delta=0,
             first_pixel=True, map_nibble=3),
    ]
    oracle_require(32 <= len(rows) <= 50,
                   f'state200 fixture count changed: {len(rows)}')
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'state200 fixture names must be unique')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x287D + index * 67)
        row.setdefault('pitch', 0x00D0)
        row.setdefault('enabled', 0)
        row.setdefault('options', 0)
        row.setdefault('driver', 'adlib')
        row.setdefault('record_bits', 0xFFFF)
        row.setdefault('df', False)
    return rows


def configure_vga(seed):
    device = MinimapVga(seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = device.gc[1] = device.gc[2] = device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[7] = 0x0F
    device.gc[8] = 0xFF
    for plane in device.planes:
        plane[:] = bytes(0x10000)
    return device


def seed_record(memory, segment, si, case):
    put16(memory, segment, si, case.get('x', 0x20))
    put16(memory, segment, si + 2, case.get('y', 0x40))
    put16(memory, segment, si + 4, case.get('record4', 0x1234))
    put16(memory, segment, si + 6, case.get('record6', 0x0020))
    put16(memory, segment, si + 8, case.get('record_bits', 0xFFFF))
    put16(memory, segment, si + 0x0A, 0x1919)
    put16(memory, segment, si + 0x0C, 0x2A2A)
    put16(memory, segment, si + 0x10, 0x5555)
    put16(memory, segment, si + 0x12, 0x3333)
    put16(memory, segment, si + 0x14, case.get('callback', 0x7654))
    put8(memory, segment, si + 0x23, case.get('state_byte_23', 0x05))
    put8(memory, segment, si + 0x24, case.get('entity_flags', 0xA5))
    put8(memory, segment, si + 0x26, case.get('state_byte_26', 0x00))
    put8(memory, segment, si + 0x27, case.get('delta', 0))
    put8(memory, segment, si + 0x28, case.get('phase', 0))
    put8(memory, segment, si + 0x29, case.get('state_byte_29', 0x17))
    put8(memory, segment, si + 0x2A, case.get('state_byte_2a', 0x6B))


def setup(case):
    template = dict(case)
    template.update(vga=False, load=case.get('load', MAIN_SEG),
                    x=case.get('x', 0x20), y=case.get('y', 0x40),
                    record_delta=case.get('delta', 0), sample=0,
                    second_sample=0, enabled=case.get('enabled', 0),
                    options=case.get('options', 0), driver=case.get('driver', 'adlib'))
    template.setdefault('si', 0x4000)
    template.setdefault('ss', 0x5000)
    template.setdefault('sp', 0xD000)
    template.setdefault('ds', 0x3800)
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if case.get('df', False) else (flags & ~0x0400)
    template['flags'] = flags
    memory, regs, _unused_device, pc_binding, sound_binding, _ = interactions.setup(template)
    regs.update(ip=ENTRY, cs=template['load'], ds=template['ds'],
                es=case.get('es', 0xA000), ss=template['ss'], sp=template['sp'],
                si=template['si'], flags=flags,
                ax=case.get('ax', 0x1357), bx=case.get('bx', 0x2468),
                cx=case.get('cx', 0xACE1), dx=case.get('dx', 0x0055),
                di=case.get('di', 0x3131), bp=case.get('bp', 0x7B2D))
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']
    put16(memory, ss, sp, case.get('outer_return', 0x7331))
    seed_record(memory, ds, si, case)
    put16(memory, ds, ROW_PITCH, case.get('pitch', 0x00D0))
    put16(memory, ds, 0x002E, case.get('callback_slot', 0x6170))
    put8(memory, ds, 0x2010, case.get('enabled', 0))
    put8(memory, ds, 0x25A7, case.get('options', 0))
    put16(memory, ds, 0x1FE8, case.get('buffer_segment', BUFFER_SEGMENT))
    for index, value in enumerate(bytes.fromhex('80 40 20 10 08 04 02 01')):
        put8(memory, ds, MASK_TABLE + index, value)
    mask_leaf.fill_generated_banks(memory,
        (case.get('buffer_segment', BUFFER_SEGMENT),
         case.get('alternate_buffer_segment', 0x7100)), case['seed'])

    if case.get('provider') == 'mask-live-ds':
        alt = case['alternate_ds']
        seed_record(memory, alt, si, dict(case, phase=4))
        put8(memory, alt, si + 0x28, 4)  # returned raw phase is deliberately not 5
        put16(memory, alt, 0x1FE8, case.get('buffer_segment', BUFFER_SEGMENT))
        put16(memory, alt, ROW_PITCH, case.get('pitch', 0x00D0))
        put16(memory, alt, 0x002E, case.get('callback_slot', 0x6170))
        for index, value in enumerate(bytes.fromhex('80 40 20 10 08 04 02 01')):
            put8(memory, alt, MASK_TABLE + index, value)

    device = configure_vga(0x2000 ^ case['seed'])
    if case.get('vga_mode_one'):
        device.gc[5] = case.get('gc5', 0x08)
        device.gc[7] = case.get('gc7', 0x08)
        device.gc[2] = case.get('gc2', 0x08)
        device.gc[4] = case.get('read_map', 0) & 3
        device.seq[2] = case.get('seq_mask', 0x0F) & 0x0F
    # Pixel leaves use read-map zero. The ten-row mask's OUT sequence changes
    # VGA registers in original order; the planar state starts deterministically.
    if case.get('phase', 0) == 0x0A:
        x = (case.get('x', 0x20) + signed8(case.get('delta', 0))) & 0xFFFF
        y = case.get('y', 0x40)
        di = pixel_offset(x, y)
        pixels = case.get('pixel_samples')
        if pixels is None:
            pixels = (0xFF, 0, 0) if case.get('first_pixel') else (0, 0, 0)
        pitch = case.get('pitch', 0x00D0)
        for index, pixel in enumerate(pixels):
            offset = (di + index * pitch) & 0xFFFF
            device.planes[0][offset] = pixel & 0xFF
        if case.get('provider') == 'pitch-after-pixel-table':
            # The old pitch location stays clear; the provider-selected pitch
            # reaches the independently seeded second sample.
            new_offset = (di + case['pitch_after']) & 0xFFFF
            device.planes[0][new_offset] = 0xFF

    if case.get('phase') == 4:
        x = case.get('x', 4)
        y = case.get('y', 0x40)
        delta = signed8(case.get('delta', 1))
        first_x = (x + 8 * delta) & 0xFFFF
        hit = case.get('coord_hit', -1)
        for index in range(4):
            col = (first_x + index * delta) & 0xFFFF
            row = (y - 6) & 0xFFFF
            offset = coordinate_offset(col, row)
            if index == hit:
                device.planes[0][offset] = 0x80 >> (col & 7)

    if case.get('sound_vector') is not None:
        ip, cs = case['sound_vector']
        put16(memory, 0, 0x184, ip)
        put16(memory, 0, 0x186, cs)
    if case.get('pc_vector') is not None:
        ip, cs = case['pc_vector']
        put16(memory, 0, 0x180, ip)
        put16(memory, 0, 0x182, cs)

    # Map reads are unchecked SS:[BX] bytes, after AX/DX have been pushed and
    # restored. The stack-alias case intentionally leaves the map byte unset:
    # PUSH AX writes nibble 9 at precisely that live offset.
    if case.get('map_nibble') is not None:
        x = (case.get('x', 0x20) + signed8(case.get('delta', 0))) & 0xFFFF
        y = case.get('y', 0x40)
        if case.get('pixel_samples'):
            cleared_before_collision = next((n for n, px in enumerate(
                case['pixel_samples']) if px), 0)
            y = (y + cleared_before_collision) & 0xFFFF
        idx = map_offset(x, y, case.get('delta', 0))
        if case.get('name') == 'map-index-aliases-live-push-ax':
            regs['sp'] = (idx + 2) & 0xFFFF
            # Re-seed the actual return at the changed caller SP.
            put16(memory, ss, regs['sp'], case.get('outer_return', 0x7331))
        else:
            put8(memory, ss, idx, case['map_nibble'])
    if case.get('interaction_nibble') is not None:
        x = (case.get('x', 0x20) + signed8(case.get('delta', 0))) & 0xFFFF
        y = case.get('y', 0x40)
        if case.get('pixel_samples'):
            cleared_before_collision = next((n for n, px in enumerate(
                case['pixel_samples']) if px), 0)
            y = (y + cleared_before_collision) & 0xFFFF
        put8(memory, ss, interaction_map_offset(x, y),
             case['interaction_nibble'])

    # Signed map nibble 1 reaches the shared 1FE8 -> interaction CALL. Give
    # that path its exact PC-service prerequisites and deterministic object data.
    put16(memory, ds, 0x17CB, case.get('object_word', 0))
    put8(memory, ds, 0x17CB + 0x1B, case.get('object_sound', 1))
    if case.get('provider') == 'sound-live-ds':
        alt = case['alternate_ds']
        seed_record(memory, alt, si, dict(case, phase=0x0A, delta=1))
        put8(memory, alt, si + 0x27, case.get('delta', 1))
        put16(memory, alt, ROW_PITCH, case.get('pitch', 0x00D0))
        put16(memory, alt, 0x002E, 0xC0DE)
        put8(memory, alt, 0x2010, 0xFF)
        put8(memory, alt, 0x25A7, 3)

    return memory, regs, device, pc_binding, sound_binding


class State200Access(interactions.Access):
    """Bounded bus providers for cadence RMW, live child words and sound DS."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []
        self.initial_ds = regs['ds']
        self.phase_address = physical(regs['ds'], (regs['si'] + 0x28) & 0xFFFF)
        self.mask_ds_address = physical(regs['ss'], (regs['sp'] - 6) & 0xFFFF)
        self.coord_bx_address = physical(regs['ss'], (regs['sp'] - 4) & 0xFFFF)
        self.return_address = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
        self.return_armed = False
        self.mask_ds_armed = False
        self.coord_bx_armed = False
        self.mask_call_seen = False
        self.coordinate_call_seen = False
        self.pixel_table_address = physical(regs['ds'],
            (MASK_TABLE + ((case.get('x', 0x20) + signed8(case.get('delta', 0))) & 7)) & 0xFFFF)

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for segment, offset, value, label in pending:
            self.modify_word(segment, offset, value)
            self.used.add(label)

    def _change_word(self, segment, offset, value, label):
        if self.native:
            self.modify_word(segment, offset, value)
            self.used.add(label)
        else:
            self.pending.append((segment, offset, value, label))

    def _provider(self, kind, address):
        super()._provider(kind, address)
        case = self.case
        mode = case.get('provider')
        address &= MASK

        if (mode == 'mask-live-ds' and kind == 'read' and self.mask_call_seen and
                address == self.mask_ds_address and self.mask_ds_armed and
                'mask-ds' not in self.used):
            self.modify_word(self.regs['ss'], (self.regs['sp'] - 6) & 0xFFFF,
                             case['alternate_ds'])
            self.used.add('mask-ds')
        if (mode == 'coordinate-pop-bx' and kind == 'read' and
                self.coordinate_call_seen and
                address == self.coord_bx_address and self.coord_bx_armed and
                'coord-bx' not in self.used):
            self.modify_word(self.regs['ss'], (self.regs['sp'] - 4) & 0xFFFF,
                             case['replacement_bx'])
            self.used.add('coord-bx')

        return_names = {'mask-return', 'coordinate-return', 'pixel-return'}
        if (mode in return_names and kind == 'read' and
                address == self.return_address and self.return_armed and
                mode not in self.used):
            self.modify_word(self.regs['ss'], (self.regs['sp'] - 2) & 0xFFFF,
                             case.get('changed_target', 0x4567))
            self.used.add(mode)

        if (mode in ('sound-return', 'sound-live-ds') and kind == 'write' and
                'sound-provider' not in self.used):
            driver = case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                if mode == 'sound-return':
                    # INT61's real-mode frame is IP, CS, FLAGS at SP-6,-4,-2.
                    self.modify_word(self.regs['ss'], (self.regs['sp'] - 6) & 0xFFFF,
                                     case.get('changed_target', 0x4567))
                else:
                    # Driver command 4 pushes DS then CS; after POP DS=CS,
                    # the live driver DS word is at entry SP-8.
                    self.modify_word(self.regs['ss'], (self.regs['sp'] - 8) & 0xFFFF,
                                     case['alternate_ds'])
                self.used.add('sound-provider')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        mode = self.case.get('provider')
        result = super().access(kind, address, flags, mask, value)

        if (mode == 'cadence-rewrite' and kind == 'write' and
                address == self.phase_address and 'cadence' not in self.used):
            self._change_word(self.regs['ds'],
                (self.regs['si'] + 0x28) & 0xFFFF,
                self.case['replacement_phase'], 'cadence')

        if (mode == 'mask-live-ds' and kind == 'write' and
                self.mask_call_seen and 'mask-ds' not in self.used):
            # The mask child's second push to SS:SP-6 is PUSH DS. Its earlier
            # save there is BX, selected so it does not equal the caller DS.
            target = self.mask_ds_address
            high = (target + 1) & MASK
            if (address == high and self.memory[target] == (self.initial_ds & 0xFF) and
                    (value & 0xFF) == (self.initial_ds >> 8)):
                self.mask_ds_armed = True

        if (mode == 'coordinate-pop-bx' and kind == 'write' and
                address == self.coord_bx_address and
                self.coordinate_call_seen and 'coord-bx' not in self.used):
            self.coord_bx_armed = True

        return_sites = {'mask-return': (0x28A4, 'mask-return'),
                        'coordinate-return': (0x28C7, 'coordinate-return'),
                        'pixel-return': (0x294E, 'pixel-return')}
        if kind == 'write' and address == self.return_address:
            low = value & 0xFF
            if mode == 'mask-live-ds' and low == 0xA4:
                self.mask_call_seen = True
            if mode == 'coordinate-pop-bx' and low in (0xC7, 0xD6, 0xE5, 0xF4):
                self.coordinate_call_seen = True
        if mode in return_sites and kind == 'write' and address == self.return_address:
            expected, label = return_sites[mode]
            if (value & 0xFF) == (expected & 0xFF):
                self.return_armed = True
                if label == 'mask-return':
                    self.mask_call_seen = True
                elif label == 'coordinate-return':
                    self.coordinate_call_seen = True

        if (mode == 'pitch-after-pixel-table' and kind == 'read' and
                address == self.pixel_table_address and 'pitch' not in self.used):
            self.modify_word(self.regs['ds'], ROW_PITCH,
                             self.case['pitch_after'])
            self.used.add('pitch')
        return result

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('state200 OUT event budget exhausted')
        if self.device is not None and port in (0x3C4, 0x3CE):
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


CALL_CONTRACTS = {
    0x28A1: ({MASK_RET}, 9),
    0x28C4: ({COORD_RET}, 8),
    0x28D3: ({COORD_RET}, 8),
    0x28E2: ({COORD_RET}, 8),
    0x28F1: ({COORD_RET}, 8),
    0x294B: ({PIXEL_RET}, 7),
    0x1FE8: (set(interactions.MAIN_RETS), 5),
}


def original(case, memory, regs, device):
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=INTEGRATED_INS,
        main_call_returns=CALL_CONTRACTS,
        stop_offsets={CONTINUATION: 0},
        access_factory=lambda c, m, r, d: State200Access(c, m, r, d),
        instruction_limit=MAX_INSTRUCTIONS)


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual.state() == expected.state(),
            label + ': VGA register/latch/plane state differs')
    got = [(event[0], event[1], event[2]) for event in actual.trace]
    want = [(event[0], event[1], event[2]) for event in expected.trace]
    require(got == want, label + ': VGA trace differs')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under {want[4]:04X}')


def independent_checks(case, memory, regs, oracle):
    provider = case.get('provider')
    if provider == 'cadence-rewrite':
        oracle_require('cadence' in oracle['used'] and
                       get8(oracle['memory'], regs['ds'], regs['si'] + 0x28) ==
                       case['replacement_phase'],
                       case['name'] + ': cadence provider did not alter the live byte')
    if provider == 'mask-live-ds':
        oracle_require('mask-ds' in oracle['used'] and
                       oracle['regs']['ds'] == case['alternate_ds'] and
                       (oracle['status'], oracle['continuation']) == (0, CONTINUATION),
                       case['name'] + ': returned DS/raw phase reread was not observed')
    if provider == 'coordinate-pop-bx':
        oracle_require('coord-bx' in oracle['used'] and
                       oracle['regs']['bx'] == case['replacement_bx'],
                       case['name'] + ': coordinate child did not restore live BX')
    if provider in ('mask-return', 'coordinate-return', 'pixel-return'):
        expected_status = {'mask-return': 9, 'coordinate-return': 8,
                           'pixel-return': 7}[provider]
        oracle_require(provider in oracle['used'] and
                       (oracle['status'], oracle['continuation']) ==
                       (expected_status, case['changed_target']),
                       case['name'] + ': actual child RET was not checked')
    if provider == 'pitch-after-pixel-table':
        oracle_require('pitch' in oracle['used'] and
                       get16(oracle['memory'], regs['ds'], ROW_PITCH) ==
                       case['pitch_after'],
                       case['name'] + ': live pitch provider did not run')
    if provider == 'sound-return':
        oracle_require('sound-provider' in oracle['used'] and oracle['status'] == 4,
                       case['name'] + ': changed INT61 IRET target was not checked')
    if provider == 'sound-live-ds':
        oracle_require('sound-provider' in oracle['used'] and
                       oracle['regs']['ds'] == case['alternate_ds'] and
                       get8(oracle['memory'], case['alternate_ds'],
                            regs['si'] + 0x27) == ((-signed8(case['delta'])) & 0xFF),
                       case['name'] + ': returned DS did not receive NEG +27')
    if case.get('name') == 'map-index-aliases-live-push-ax':
        x = case['x']
        idx = map_offset(x, case['y'], case['delta'])
        oracle_require(regs['sp'] == (idx + 2) & 0xFFFF and
                       any(event[0] == 'write' and
                           event[1] == physical(regs['ss'], idx) and
                           event[2] == ((x >> 2) & 0xFF)
                           for event in oracle['events']),
                       case['name'] + ': live PUSH AX/map alias not exercised')
    if case.get('name') == 'word-and-physical-stack-wrap':
        oracle_require((oracle['status'], oracle['continuation']) == (9, 0x288A) and
                       any(event[0] == 'write' and event[1] == 0xFFFFF
                           for event in oracle['events']),
                       case['name'] + ': VGA stack mirror did not change the live mask RET')
    if case.get('name') == 'finish-interaction-pc-service':
        oracle_require(any(source == 'pc' for source, _ in oracle['sites']),
                       case['name'] + ': shared finish did not enter PC service')


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding = setup(case)
    oracle = original(case, initial, regs, device)
    independent_checks(case, initial, regs, oracle)
    actual = native.run(case, initial, regs, device, pc_binding, sound_binding,
                        core=core)
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
    flag_mask = oracle['flag_mask']
    require(((actual['regs']['flags'] ^ oracle['regs']['flags']) & flag_mask) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {flag_mask:04X}')
    require(actual['memory'] == oracle['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['used'],
            f'{label}: provider set differs {actual["providers"]}/{oracle["used"]}')
    sites = {address for source, address in oracle['sites']
             if source == 'main' and address in OWN_INS}
    edges = {(source_ip, target) for source, source_ip, target in oracle['edges']
             if source == 'main' and source_ip in OWN_INS}
    integrated = {address for source, address in oracle['sites'] if source == 'main'}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(sites),
                edges=[list(edge) for edge in sorted(edges)],
                integrated_sites=sorted(integrated),
                event_count=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'src/game_code.asm', 'src/entity_graphics.asm', 'src/program.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/inputs.json',
        'metadata/sound-oracle.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json', 'metadata/toolchain-lock.json',
        'c/entity_state200.c', 'c/entity_state200.h',
        'c/special_blit.h',
        'c/entity_mask_rows.c', 'c/entity_mask_rows.h',
        'c/coordinate_pixel.c', 'c/coordinate_pixel.h',
        'c/entity_pixel.c', 'c/entity_pixel.h',
        'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/lemmings_sym.h',
        'tests/entity_state200.py', 'tests/entity_interactions.py',
        'tests/entity_mask.py', 'tests/entity_mask_rows.py',
        'tests/coordinate_pixel.py', 'tests/entity_pixel.py',
        'tests/entity_finish.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/pcspeaker_interrupt.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/resources.py', 'tools/unpack.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_preflight():
    before = input_hashes()
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 0x1F0 and
                    len(OWN_INS) == 169,
                    f'state200 identity changed: {sum(i.size for i in OWN_INS.values())} bytes/'
                    f'{len(OWN_INS)} sites')
    oracle_require(len(OWN_EDGES) == 59,
                   f'state200 edge accounting changed: {len(OWN_EDGES)}')
    specs = cases()
    all_sites, all_edges = set(), set()
    for case in specs:
        initial, regs, device, _pc, _sound = setup(case)
        result = original(case, initial, regs, device)
        independent_checks(case, initial, regs, result)
        all_sites.update(address for source, address in result['sites']
                         if source == 'main' and address in OWN_INS)
        all_edges.update((source_ip, target) for source, source_ip, target in result['edges']
                         if source == 'main' and source_ip in OWN_INS)
        provider = case.get('provider')
        if provider == 'mask-return':
            expected = (9, case['changed_target'])
        elif provider == 'coordinate-return':
            expected = (8, case['changed_target'])
        elif provider == 'pixel-return':
            expected = (7, case['changed_target'])
        elif provider == 'sound-return':
            expected = (4, case['changed_target'])
        elif case.get('name') == 'word-and-physical-stack-wrap':
            expected = (9, 0x288A)
        elif case.get('sound_vector') == (0, 0x6200):
            expected = (1, 0)
        else:
            expected = (0, CONTINUATION)
        oracle_require((result['status'], result['continuation']) == expected,
                       f'{case["name"]}: status/continuation '
                       f'{result["status"]}/{result["continuation"]:04X} != {expected}')
        oracle_require(len(result['events']) <= MAX_EVENTS,
                       case['name'] + ': event cap accounting failed')
        gc.collect()
    oracle_require(all_sites == set(OWN_INS),
                   f'original own sites {len(all_sites)}/{len(OWN_INS)}; '
                   f'missing={sorted(set(OWN_INS)-all_sites)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'original own edges {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')
    oracle_require(before == input_hashes(),
                   'state200 source inputs changed during original-only preflight')
    print(f'PASS original state200 preflight: {len(specs)} fixtures, '
          f'{len(all_sites)} sites, {len(all_edges)} edges; no native code loaded',
          flush=True)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State200Access(case, memory, regs, device, native=True)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_fail(GUARD_EXIT, 'native state200 access cap exhausted')
                return self.access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, f'native state200 read callback failed: {error}')

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_fail(GUARD_EXIT, 'native state200 access cap exhausted')
                self.access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, f'native state200 write callback failed: {error}')

        def out(_context, port, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_fail(GUARD_EXIT, 'native state200 access cap exhausted')
                self.access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, f'native state200 OUT callback failed: {error}')

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state200-m{mutation}.dll',
                     mutation, 'entity_state200')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state200_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state200_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        bus = NativeBus(case, memory, initial_regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        pc_ptr = ct.byref(pc_binding) if pc_binding is not None else None
        sound_ptr = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = Call(*(initial_regs[name] for name in
                          ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs',
                           'ds', 'es', 'ss', 'sp', 'flags')))
            out = self.core(ram, ct.byref(call), pc_ptr, sound_ptr,
                            ct.byref(bus.bus))
            state = dict(initial_regs)
            state.update(ax=out.value, bx=out.map_cursor, cx=out.count,
                         dx=out.auxiliary_value, si=out.record_cursor,
                         di=out.object_cursor, bp=out.candidate_y,
                         cs=out.code_segment, ds=out.data_segment,
                         es=out.extra_segment, ss=out.stack_segment,
                         sp=out.stack_offset, flags=out.flags,
                         ip=out.continuation)
            status = out.status
        else:
            registers = interactions.Regs(**initial_regs)
            status = self.adapter(ram, ct.byref(registers), pc_ptr, sound_ptr,
                                  ct.byref(bus.bus))
            state = {name: getattr(registers, name) for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=bus.access.events, providers=set(bus.access.used),
                    status=status, continuation=state['ip'])


def worker(directory):
    before = input_hashes()
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 0x1F0 and
                    len(OWN_INS) == 169 and len(OWN_EDGES) == 59,
                    'state200 static byte/site/edge identity changed')
    specs = cases()
    native = Native(directory)
    rows, all_sites, all_edges, total_events = [], set(), set(), 0
    for case in specs:
        for core in (True, False):
            row = compare_case(native, case, core=core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
        gc.collect()
    oracle_require(all_sites == set(OWN_INS),
                   f'native state200 sites {len(all_sites)}/{len(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'native state200 edges {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')
    witnesses = {
        1: 'separate-rmw-rereads-live-cadence',
        2: 'mask-returned-ds-raw-phase-reread',
        3: 'coordinate-live-saved-registers',
        4: 'pitch-reread-after-pixel-call',
        5: 'mask-actual-call-return-changed',
        6: 'coordinate-actual-call-return-changed',
        7: 'pixel-call-live-ret-overwrite',
        8: 'nibble-nine-bound-sound-service',
        9: 'nibble-nine-sound-returned-ds-before-neg',
    }
    mutations = []
    for mutation, witness in witnesses.items():
        variant = Native(directory, mutation)
        case = next(item for item in specs if item['name'] == witness)
        try:
            compare_case(variant, case, core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=witness,
                                  mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'mutant {mutation} survived completed witness {witness}')
        gc.collect()
    oracle_require(before == input_hashes(),
                   'state200 source inputs changed during native campaign')
    integrated = set().union(*(set(row['integrated_sites']) for row in rows))
    report = dict(image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
                  case_count=len(specs),
                  mutation_count=len(mutations), mutations=mutations,
                  executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  translated_code_bytes=0x1F0, instruction_sites=len(OWN_INS),
                  own_branch_edges=len(OWN_EDGES),
                  static_instruction_addresses=sorted(OWN_INS),
                  static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
                  integrated_main_instruction_addresses=sorted(integrated),
                  core_adapter_comparisons=len(rows), total_bus_events=total_events,
                  original_code_hook_steps=sum(row['steps'] for row in rows),
                  cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                              continuation=row['continuation'], sites=row['sites'],
                              edges=row['edges'], event_count=row['event_count'],
                              steps=row['steps']) for row in rows],
                  limits=dict(worker_seconds=WORKER_SECONDS,
                              process_memory_mib=PROCESS_MIB,
                              windows_tree_memory_mib=TREE_MIB,
                              original_instruction_limit=MAX_INSTRUCTIONS,
                              native_callback_event_limit=MAX_EVENTS,
                              callback_budget_exit=GUARD_EXIT,
                              callback_error_exit=CALLBACK_EXIT),
                  input_hashes=before,
                  domain='287D..2A6C state-0200 core and adapter; live cadence '
                         'RMW and returned DS:SI reread; actual ten-row-mask/coordinate/pixel '
                         'CALL/RET; three probes and reread pitch; unchecked SS map; '
                         'INT61 and shared 1FE8 interaction tail; full RAM/registers, '
                         'defined FLAGS, VGA state and ordered bus events.')
    write_json(REPORT, report)
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
                  case_count=len(specs), executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  input_hashes=before, c_coverage_claimed=False))
    print(f'PASS entity state200: {len(specs)} fixtures x core/adapter, '
          f'{len(OWN_INS)} sites, {len(OWN_EDGES)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 2 and sys.argv[1] == '--original-only':
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                    check=True)
        return
    REPORT.unlink(missing_ok=True)
    ORIGINAL_REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state200-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                    check=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == '--original-worker':
        original_preflight()
    elif len(sys.argv) in (1, 2) and (len(sys.argv) == 1 or sys.argv[1] == '--original-only'):
        main()
    else:
        raise SystemExit('usage: entity_state200.py [--worker DIR | --original-only]')
