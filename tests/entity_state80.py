"""Bounded original-versus-C checks for the state-0080 entity handler."""
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
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, END = 0x2693, 0x27E8
UNKNOWN_BYTES = {0x26A1, 0x26F6, 0x26FF, 0x2762}
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
STROKE_ENTRY, STROKE_RET = 0x5F0F, 0x5FAB
STROKE_PIXEL_RET = 0x5F57
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9),
                (0x2148, 0x2169))
CONTINUATION = 0x1FEB
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
ALL_FLAGS = interactions.FLAGS
MAX_INSTRUCTIONS, MAX_EVENTS = 4096, 4096
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state80-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = {address: ins for address, ins in decoded_span(ENTRY, END).items()
           if address not in UNKNOWN_BYTES}
PIXEL_INS = decoded_span(PIXEL_ENTRY, PIXEL_RET + 1)
STROKE_INS = decoded_span(STROKE_ENTRY, STROKE_RET + 1)
FINISH_INS = {
    ins.address: ins
    for start, end in FINISH_SPANS
    for ins in MD.disasm(IMAGE[start:end], start)
}
INTEGRATED_INS = dict(OWN_INS)
for group in (PIXEL_INS, STROKE_INS, FINISH_INS, interactions.MAIN_INS):
    INTEGRATED_INS.update(group)

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
                 'stack_segment', 'stack_offset', 'flags', 'continuation', 'status')]


class OracleFailure(AssertionError):
    """The bounded original/provider failed to reach a declared boundary."""


class Mismatch(AssertionError):
    """Only a completed original/native comparison can credit a mutant."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def pixel_start(x, y):
    row = ((y - 0x10) & 0xFFFF)
    if row & 0x8000:
        row = 0
    return ((row * 0xD0) + ((x & 0xFFFF) >> 3) + 0x4A40) & 0xFFFF


def map_offset(x, y):
    qx = (x & 0xFFFF) >> 2
    qy = (((y - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12) & 0xFFFF


def branch_edges(instructions):
    result = set()
    for address, ins in instructions.items():
        mnemonic = ins.mnemonic.lower()
        if not ins.group(capstone.CS_GRP_JUMP) and mnemonic not in (
                'loop', 'loope', 'loopne', 'jcxz'):
            continue
        if mnemonic not in ('jmp', 'ljmp'):
            result.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            result.add((address, ins.operands[-1].imm & 0xFFFF))
    return result


STATIC_EDGES = branch_edges(OWN_INS)


def observed_own_edges(observed):
    """Return only branch transitions actually observed by the oracle."""
    return {(source_ip, target)
            for source, source_ip, target in observed['edges']
            if source == 'main' and source_ip in OWN_INS}


def cases():
    """Focused phase, three-probe, transition, stroke and interrupt fixtures."""
    rows = [
        dict(name='phase-nonzero-finish', phase=0, status_byte=4),
        dict(name='cadence-mask-retains-bit3', phase=7, counter=4),
        dict(name='phase-zero-wrap-enters-probe-path', phase=15,
             x=0x0120, y=0x0040, counter=2, delta=8, pixels=(0, 0, 0)),
        dict(name='phase-a-stage-outside-range', phase=9, counter=4),
        dict(name='phase-a-no-sound-options', phase=9, counter=2,
             enabled=0xFF, options=0),
        dict(name='phase-a-pc-options-clear', phase=9, counter=1,
             enabled=0, options=0),
        dict(name='phase-a-pc0313-adlib', phase=9, counter=1,
             enabled=0, options=1, driver='adlib'),
        dict(name='phase-a-pc0313-tandy', phase=9, counter=1,
             enabled=0, options=1, driver='tandysnd'),
        dict(name='phase-a-pc0313-unbound-vector', phase=9, counter=1,
             enabled=0, options=1, pc_vector=(0x1234, 0x7000)),
        dict(name='phase-a-external0412-adlib', phase=9, counter=2,
             enabled=0xFF, options=3, driver='adlib'),
        dict(name='phase-a-int61-second-option-bit', phase=9, counter=2,
             enabled=0xFF, options=2),
        dict(name='phase-a-external0412-changed-iret', phase=9, counter=1,
             enabled=0xFF, options=3, provider='state80-sound-interrupt-return',
             provider_return=0x4567),
        dict(name='phase-a-external0412-unbound-vector', phase=9, counter=1,
             enabled=0xFF, options=3, sound_vector=(0x1234, 0x7000)),
        dict(name='phase-a-external0412-unbound-binding', phase=9, counter=1,
             enabled=0xFF, options=3, sound_binding=False),
        dict(name='phase-a-pc-unbound-binding', phase=9, counter=1,
             enabled=0, options=1, pc_binding=False),
        dict(name='phase-a-pc-live-ds-second-gate-and-saved-words',
             phase=9, counter=1, enabled=0, options=1,
             provider='pc-stack-live-gates', provider_ds=0x6100,
             provider_enabled=0xFF, provider_options=3,
             saved_ax=0x1209, saved_es=0x7200),
        dict(name='phase-a-sound-modifies-saved-ax-es', phase=9, counter=1,
             enabled=0xFF, options=3, provider='sound-save-words',
             saved_ax=0x2309, saved_es=0x7300),
        dict(name='phase-nine-stage-hands-to-stroke', phase=8, counter=9,
             x=0x0120, y=0x0040, pixels=(0xFF, 0, 0), vga=True),
        dict(name='stroke-df-set-full-byte-order', phase=8, counter=9,
             x=0x0127, y=0x0040, delta=0x80, df=True, pixels=(0, 0xFF, 0),
             vga=True, plane_check=True),
        dict(name='stroke-nested-pixel-ret-changed', phase=8, counter=9,
             x=0x0120, y=0x0040, provider='stroke-pixel-return',
             changed_target=0x4567, vga=True),
        dict(name='stroke-cross-pixel-ret-other-valid-return', phase=8,
             counter=9, x=0x0120, y=0x0040,
             provider='stroke-pixel-return', changed_target=0x2703, vga=True),
        dict(name='stroke-outer-ret-changed', phase=8, counter=9,
             x=0x0120, y=0x0040, provider='stroke-call-return',
             changed_target=0x4567, vga=True),
        dict(name='direct-pixel-ret-first-call', phase=15, x=0x0120,
             y=0x0040, counter=2, delta=8, pixels=(0, 0, 0),
             provider='pixel-return-2700', changed_target=0x4567),
        dict(name='direct-pixel-ret-second-call', phase=15, x=0x0120,
             y=0x0040, counter=2, delta=8, pixels=(0, 0, 0),
             provider='pixel-return-2710', changed_target=0x4567),
        dict(name='direct-pixel-ret-third-call', phase=15, x=0x0120,
             y=0x0040, counter=2, delta=8, pixels=(0, 0, 0),
             provider='pixel-return-272c', changed_target=0x4567),
        dict(name='direct-pixel-cross-return-other-site', phase=15,
             x=0x0120, y=0x0040, counter=2, delta=8, pixels=(0, 0, 0),
             provider='pixel-return-2700', changed_target=0x2713),
        dict(name='three-probes-all-clear-transition-a', phase=15,
             x=0x0120, y=0x0011, counter=2, y_delta=0xFFF0,
             delta=8, pixels=(0, 0, 0), callback=0xA35C),
        dict(name='three-probes-third-hit-resets', phase=15,
             x=0x0120, y=0x0040, counter=2, delta=8,
             pixels=(0, 0, 0xFF)),
        dict(name='first-probe-hit-resets', phase=15, x=0x0120,
             y=0x0040, counter=2, delta=8, pixels=(0xFF, 0, 0)),
        dict(name='second-probe-hit-resets', phase=15, x=0x0120,
             y=0x0040, counter=2, delta=8, pixels=(0, 0xFF, 0)),
        dict(name='counter-zero-decrement-wraps-to-ff', phase=15,
             x=0x0120, y=0x0040, counter=0, delta=8, pixels=(0, 0, 0)),
        dict(name='counter-one-takes-transition-b', phase=15, x=0x0120,
             y=0x0040, counter=1, pixels=(0, 0, 0)),
        dict(name='counter-two-third-pixel-clear', phase=15, x=0x0120,
             y=0x0040, counter=2, delta=8, pixels=(0, 0, 0), vga=True),
        dict(name='signed-left-limit-equal', phase=15, x=0x0010,
             delta=0, y=0x0040, counter=1),
        dict(name='signed-left-limit-above', phase=15, x=0x0011,
             delta=0, y=0x0040, counter=1, pixels=(0, 0, 0)),
        dict(name='signed-right-limit-equal', phase=15, x=0x0680,
             delta=0, y=0x0040, counter=1),
        dict(name='signed-negative-x-wrap', phase=15, x=0xFFFE,
             delta=0xFF, y=0x0040, counter=1),
        dict(name='signed-height-threshold-equal', phase=15, x=0x0120,
             y=0x0011, y_delta=0xFFF0, counter=2, pixels=(0, 0, 0)),
        dict(name='signed-height-threshold-above', phase=15, x=0x0120,
             y=0x0020, y_delta=0xFFF0, counter=2, pixels=(0, 0, 0)),
        dict(name='post-third-pop-x-at-lower-bound', phase=15,
             x=0x0120, y=0x0040, counter=2, delta=8, pixels=(0, 0, 0),
             provider='third-pop-x-lower'),
        dict(name='post-third-pop-x-at-upper-bound', phase=15,
             x=0x0120, y=0x0040, counter=2, delta=8, pixels=(0, 0, 0),
             provider='third-pop-x-upper'),
        dict(name='pitch-zero-wrap-on-probe-subtract', phase=15,
             x=0x0120, y=0x0040, counter=2, pitch=1,
             pixels=(0, 0, 0)),
        dict(name='live-pitch-update-between-probes', phase=15,
             x=0x0120, y=0x0040, counter=2, pitch=0x00D0,
             pitch_after=0x0040, provider='pitch-on-first-pixel',
             pixels=(0, 0, 0)),
        dict(name='live-callback-slot-at-transition', phase=15,
             x=0x0120, y=0x0011, y_delta=0xFFF0, counter=2,
             provider='callback-on-first-pixel', callback=0xC0DE,
             pixels=(0, 0, 0)),
        dict(name='ds-ss-record-stack-alias', phase=15, x=0x0120,
             y=0x0040, counter=2, ds=0x5000, ss=0x5000,
             si=0xCFC0, sp=0xD000, pixels=(0, 0, 0), df=True),
        dict(name='record-offset-word-wrap', phase=15, x=0x0120,
             y=0x0040, counter=2, ds=0xFFFF, si=0xFFF0,
             pixels=(0, 0, 0)),
        dict(name='stack-offset-physical-wrap', phase=15, x=0x0120,
             y=0x0040, counter=1, ss=0xFFFF, sp=1, pixels=(0, 0, 0)),
        dict(name='entry-rmw-defined-flags-df', phase=15, x=0x0120,
             y=0x0040, counter=2, pixels=(0, 0, 0), flags=0x0E47,
             df=True, vga=True),
        dict(name='readback-mode-one-vga-preservation', phase=15,
             x=0x0120, y=0x0040, counter=2, pixels=(0, 0, 0), vga=True,
             gc5=0x08, gc7=0x08, gc2=0x08, plane_check=True),
        dict(name='poisoned-registers-and-memory', phase=1,
             counter=4, poison=True, seed=0x2693),
    ]
    oracle_require(28 <= len(rows) <= 50,
                   f'state80 fixture count changed: {len(rows)}')
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'state80 fixture names are not unique')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x2693 + index * 43)
    return rows


def setup(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('si', 0x6000)
    template.setdefault('sp', 0xD000)
    template.setdefault('x', 0x0120)
    template.setdefault('y', 0x0040)
    template.setdefault('delta_x', 8)
    template.setdefault('delta_y', template.get('y_delta', 0))
    template.setdefault('record_delta', template.get('delta', 0))
    template.setdefault('counter', 2)
    template.setdefault('phase', 15)
    template.setdefault('enabled', 0)
    template.setdefault('options', 0)
    template.setdefault('driver', 'adlib')
    template.setdefault('pitch', 0x00D0)
    template.setdefault('callback', 0x7654)
    template.setdefault('seed', 0x2693 + len(case['name']))
    raw_flags = template.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    if template.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    template['flags'] = flags

    setup_template = dict(template)
    if template.get('vga'):
        setup_template['vga'] = False
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(setup_template)
    regs.update(cs=template['load'], ip=ENTRY, ds=template['ds'],
                ss=template['ss'], si=template['si'], sp=template['sp'],
                flags=flags)
    regs.update(ax=template.get('ax', 0x1357), bx=template.get('bx', 0x2468),
                cx=template.get('cx', 0xACE1), dx=template.get('dx', 0x0055),
                di=template.get('di', 0x3131), bp=template.get('bp', 0x7B2D),
                es=template.get('es', 0x6200))

    ds, ss, si, sp = regs['ds'], regs['ss'], regs['si'], regs['sp']
    put16(memory, ss, sp, template.get('outer_return', 0x7A5C))
    if ds != DATA_SEGMENT:
        for index, value in enumerate(PIXEL_MASKS):
            put8(memory, ds, 0x547C + index, value)
    put16(memory, ds, 0x0004, template['pitch'])
    put16(memory, ds, si, template['x'])
    put16(memory, ds, si + 2, template['y'])
    put16(memory, ds, si + 4, template.get('x_aux', 0))
    put16(memory, ds, si + 6, template['delta_y'])
    put16(memory, ds, si + 8, template.get('record_word_8', 0x1919))
    put16(memory, ds, si + 0x0A, template.get('record_word_a', 0x2A2A))
    put16(memory, ds, si + 0x0C, template.get('record_word_c', 0x3B3B))
    put16(memory, ds, si + 0x14, template.get('callback_initial', 0x7654))
    put8(memory, ds, si + 0x21, template['counter'])
    put8(memory, ds, si + 0x23, template.get('state_byte_23', 0x05))
    put8(memory, ds, si + 0x24, template.get('entity_flags', 0xA5))
    put8(memory, ds, si + 0x27, template['record_delta'])
    put8(memory, ds, si + 0x28, template['phase'])
    put8(memory, ds, si + 0x29, template.get('state_byte_29', 0x17))
    put8(memory, ds, si + 0x2A, template.get('state_byte_2a', 0x6B))
    put16(memory, ds, 0x002E, template['callback'])
    put8(memory, ds, 0x2010, template['enabled'])
    put8(memory, ds, 0x25A7, template['options'])

    if 'provider_ds' in template:
        alternate = template['provider_ds']
        put16(memory, alternate, si + 4, 0)
        put16(memory, alternate, si + 6, 0)
        put8(memory, alternate, si + 0x21, template['counter'])
        put8(memory, alternate, si + 0x27, template['record_delta'])
        put8(memory, alternate, si + 0x28, template['phase'])
        put16(memory, alternate, si, template.get('alternate_x', template['x']))
        put16(memory, alternate, si + 2,
              template.get('alternate_y', template['y']))
        put16(memory, alternate, 0x002E, template.get('alternate_callback', 0xC0DE))
        put8(memory, alternate, 0x2010,
             template.get('provider_enabled', 0xFF))
        put8(memory, alternate, 0x25A7,
             template.get('provider_options', 3))

    if template.get('vga'):
        if device is None:
            device = MinimapVga(template['seed'], read_map=0)
        device.seq[4] = 0x06
        device.seq[2] = template.get('map_mask', 0x0F) & 0x0F
        device.gc[0], device.gc[1], device.gc[3] = 0, 0, 0
        device.gc[2] = template.get('gc2', 0) & 0x0F
        device.gc[4] = template.get('read_map', 0) & 3
        device.gc[5] = template.get('gc5', 0) & 0x0B
        device.gc[6] = 0x05
        device.gc[7] = template.get('gc7', 0x0F) & 0x0F
        device.gc[8] = template.get('gc8', 0xFF) & 0xFF
        for plane in device.planes:
            plane[:] = bytes(0x10000)
    else:
        device = None

    def seed_pixel(offset, value):
        offset &= 0xFFFF
        address = physical(0xA000, offset)
        if device is None:
            memory[address] = value & 0xFF
        else:
            for plane in range(4):
                device.planes[plane][offset] = value & 0xFF

    actual_x = get16(memory, ds, si)
    actual_y = get16(memory, ds, si + 2)
    delta = template['record_delta']
    if delta & 0x80:
        delta -= 0x100
    pitch = get16(memory, ds, 4)
    pixel_values = template.get('pixels', (0, 0, 0))
    if template['phase'] == 15:
        # The phase counter wraps to zero, decrements Y once, and probes the
        # live X offsets after one, two, and four signed record-delta steps.
        probe_y = (actual_y - 1) & 0xFFFF
        probe_offsets = (
            pixel_start((actual_x + delta) & 0xFFFF, probe_y) - pitch,
            pixel_start((actual_x + 2 * delta) & 0xFFFF, probe_y) - pitch,
            pixel_start((actual_x + 4 * delta) & 0xFFFF, probe_y) - 9 * pitch,
        )
        for offset, value in zip(probe_offsets, pixel_values):
            seed_pixel(offset, value)
    if template['phase'] == 8 and template['counter'] == 9:
        stroke_x = (actual_x + delta) & 0xFFFF
        if delta < 0:
            stroke_x = (stroke_x - 4) & 0xFFFF
        stroke_y = (actual_y - 1) & 0xFFFF
        stroke_offset = pixel_start(stroke_x, stroke_y)
        step = -1 if flags & 0x0400 else 1
        for index, value in enumerate(pixel_values):
            seed_pixel(stroke_offset + index * step, value)
    return memory, regs, device, pc_binding, sound_binding


class State80Access(interactions.Access):
    """Finite stack, pitch, callback and child-return providers."""
    event_limit = MAX_EVENTS

    RETURN_OFFSETS = {
        'pixel-return-2700': 2,
        'pixel-return-2710': 2,
        'pixel-return-272c': 4,
        'stroke-pixel-return': 10,
        'stroke-call-return': 2,
        'third-pop-x-lower': 4,
        'third-pop-x-upper': 4,
    }
    RETURN_WORDS = {
        'pixel-return-2700': 0x2703,
        'pixel-return-2710': 0x2713,
        'pixel-return-272c': 0x272F,
        'stroke-pixel-return': 0x5F57,
        'stroke-call-return': 0x26E1,
        'third-pop-x-lower': 0x272F,
        'third-pop-x-upper': 0x272F,
    }
    RETURN_MUTATORS = {
        'pixel-return-2700', 'pixel-return-2710', 'pixel-return-272c',
        'stroke-pixel-return', 'stroke-call-return',
    }

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.return_offset = self.RETURN_OFFSETS.get(case.get('provider'))
        self.return_address = (physical(regs['ss'],
            (regs['sp'] - self.return_offset) & 0xFFFF)
            if self.return_offset is not None else None)
        self.return_armed = False
        self.third_return_consumed = False
        self.pending = []
        self.saved_ax_address = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for kind, segment, offset, value in pending:
            if kind == 'word':
                self.modify_word(segment, offset, value)

    def _provider(self, kind, address):
        case = self.case
        effect = case.get('provider')
        super()._provider(kind, address)
        if (effect in self.RETURN_OFFSETS and kind == 'read' and
                address == self.return_address and self.return_armed and
                effect in self.RETURN_MUTATORS and effect not in self.used):
            self.modify_word(self.regs['ss'],
                (self.regs['sp'] - self.return_offset) & 0xFFFF,
                case.get('changed_target', 0x4567))
            self.used.add(effect)
        if (effect in ('third-pop-x-lower', 'third-pop-x-upper') and
                kind == 'read' and address == self.return_address and
                self.return_armed):
            self.third_return_consumed = True
        if (effect in ('third-pop-x-lower', 'third-pop-x-upper') and
                kind == 'read' and self.third_return_consumed and
                address == self.saved_ax_address and effect not in self.used):
            changed_x = 0x0010 if effect.endswith('lower') else 0x0680
            self.modify_word(self.regs['ss'],
                              (self.regs['sp'] - 2) & 0xFFFF, changed_x)
            self.used.add(effect)
        if effect == 'pc-stack-live-gates' and kind == 'write' and \
                address == physical(interactions.PC_SEG, 1) and effect not in self.used:
            ss, sp = self.regs['ss'], self.regs['sp']
            self.modify_word(ss, sp - 22, case['provider_ds'])
            self.modify_word(ss, sp - 2, case['saved_ax'])
            self.modify_word(ss, sp - 4, case['saved_es'])
            self.used.add(effect)
        if effect == 'sound-save-words' and kind == 'write' and effect not in self.used:
            driver = case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                self.modify_word(self.regs['ss'], self.regs['sp'] - 2,
                                 case.get('saved_ax', 0x2309))
                self.modify_word(self.regs['ss'], self.regs['sp'] - 4,
                                 case.get('saved_es', 0x7300))
                self.used.add(effect)
        if effect == 'sound-restore-ds' and kind == 'write' and effect not in self.used:
            driver = case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                self.modify_word(self.regs['ss'], self.regs['sp'] - 12,
                                 case['provider_ds'])
                self.used.add(effect)
        if (effect == 'state80-sound-interrupt-return' and kind == 'write' and
                'sound80' not in self.used):
            driver = case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                self.modify_word(self.regs['ss'], self.regs['sp'] - 10,
                                 case.get('provider_return', 0x4567))
                self.used.add('sound80')

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        address &= MASK
        effect = self.case.get('provider')
        # Update an already-consumed first pitch before the next pixel probe.
        if (effect == 'pitch-on-first-pixel' and kind == 'read' and
                VGA_BASE <= address < VGA_END and effect not in self.used):
            if self.native:
                self.modify_word(self.regs['ds'], 4,
                                 self.case.get('pitch_after', 0x0040))
            else:
                self.pending.append(('word', self.regs['ds'], 4,
                                     self.case.get('pitch_after', 0x0040)))
            self.used.add(effect)
        if (effect == 'callback-on-first-pixel' and kind == 'read' and
                VGA_BASE <= address < VGA_END and effect not in self.used):
            self.modify_word(self.regs['ds'], 0x002E,
                             self.case.get('callback', 0xC0DE))
            self.used.add(effect)
        result = super().access(kind, address, flags, mask, value)
        if effect in self.RETURN_OFFSETS and kind == 'write' and \
                address == self.return_address and effect not in self.used:
            expected = self.RETURN_WORDS[effect]
            if (value & 0xFF) == (expected & 0xFF):
                self.return_armed = True
        return result

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('state80 OUT event budget exhausted')
        if self.device is not None and port in (0x3C4, 0x3CE):
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


def main_call_contracts():
    return {
        0x2700: ({0x5DF7}, 7),
        0x2710: ({0x5DF7}, 7),
        0x272C: ({0x5DF7}, 7),
        0x26DE: ({STROKE_RET}, 9),
        0x5F54: ({PIXEL_RET}, 8),
        0x1FE8: (set(interactions.MAIN_RETS), 5),
    }


CALL_CONTRACTS = main_call_contracts()


def original(case, memory, regs, device, *, entry_flag_mask=ALL_FLAGS):
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=entry_flag_mask,
        main_instructions=INTEGRATED_INS,
        main_call_returns=CALL_CONTRACTS,
        stop_offsets={CONTINUATION: 0},
        access_factory=lambda c, m, r, d: State80Access(c, m, r, d),
        instruction_limit=MAX_INSTRUCTIONS)


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual.state() == expected.state(),
            label + ': VGA planes/latches/registers differ')
    got = [(event[0], event[1], event[2]) for event in actual.trace]
    want = [(event[0], event[1], event[2]) for event in expected.trace]
    require(got == want, label + ': VGA device trace differs')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered bus events {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under {want[4]:04X}')


def independent_vga_replay(initial, events):
    """Replay VGA register/latch/plane effects from ordered CPU bus events."""
    planes = [bytearray(plane) for plane in initial.planes]
    latches = list(initial.latches)
    seq, gc = list(initial.seq), list(initial.gc)
    si, gi = initial.si, initial.gi
    out_count = initial.outcount
    scratch = bytearray(SIZE)
    for event in events:
        kind, address, value = event[:3]
        flags = event[3]
        if kind == 'out':
            index, data = value & 0xFF, (value >> 8) & 0xFF
            if address == 0x3C4:
                si, seq[index] = index, data
            elif address == 0x3CE:
                gi, gc[index] = index, data
            else:
                raise OracleFailure(f'independent VGA replay saw port {address:04X}')
            out_count += 1
            continue
        if not VGA_BASE <= address < VGA_END:
            continue
        offset = address - VGA_BASE
        if kind == 'read':
            latches = [plane[offset] for plane in planes]
            if gc[5] & 0x08:
                sample = 0xFF
                for plane in range(4):
                    if gc[7] & (1 << plane):
                        sample &= (latches[plane] if gc[2] & (1 << plane)
                                   else (~latches[plane] & 0xFF))
            else:
                sample = latches[gc[4] & 3]
            oracle_require(sample == (value & 0xFF),
                           'independent VGA read value differs from bus trace')
            scratch[address] = sample
            continue
        if kind != 'write':
            raise OracleFailure(f'independent VGA replay saw event kind {kind}')
        mode = gc[5] & 3
        if mode == 1:
            for plane in range(4):
                if seq[2] & (1 << plane):
                    planes[plane][offset] = latches[plane]
        elif mode == 0:
            rotate = gc[3] & 7
            cpu_value = value & 0xFF
            rotated = cpu_value if rotate == 0 else (
                (cpu_value >> rotate) | (cpu_value << (8 - rotate))) & 0xFF
            operation = (gc[3] >> 3) & 3
            for plane in range(4):
                if not seq[2] & (1 << plane):
                    continue
                source = (0xFF if gc[0] & (1 << plane) else 0) if gc[1] & (1 << plane) else rotated
                latch = latches[plane]
                if operation == 1:
                    result = source & latch
                elif operation == 2:
                    result = source | latch
                elif operation == 3:
                    result = source ^ latch
                else:
                    result = source
                planes[plane][offset] = ((result & gc[8]) |
                                         (latch & (~gc[8] & 0xFF)))
        else:
            raise OracleFailure(f'independent VGA replay lacks write mode {mode}')
        scratch[address] = value & 0xFF
    return (tuple(bytes(plane) for plane in planes), tuple(latches),
            tuple(seq), tuple(gc), si, gi, out_count)


def check_independent_planes(case, initial_device, observed):
    if not case.get('plane_check') or initial_device is None:
        return False
    expected = independent_vga_replay(initial_device, observed['events'])
    actual = observed['device'].state()
    oracle_require(expected == actual,
                   case['name'] + ': independent exchange plane replay differs')
    return True


def expected_path(case, observed):
    own = {address for source, address in observed['sites']
           if source == 'main' and address in OWN_INS}
    provider = case.get('provider', '')
    if case['phase'] == 15:
        oracle_require(0x269F in own and 0x26E4 in own,
                       case['name'] + ': wrapped phase did not enter update path')
    if case['phase'] == 8 and case['counter'] == 9:
        oracle_require(0x26DE in own and observed['status'] in (0, 8, 9),
                       case['name'] + ': phase-nine stroke handoff was missed')
    if case.get('counter') == 9 and case['phase'] == 8:
        oracle_require(0x26D9 in own and
                       (0x26DE in own or observed['status'] in (8, 9)),
                       case['name'] + ': AL=9 did not reach DrawEntityStroke')
    if provider.startswith('pixel-return-'):
        oracle_require(observed['status'] == 7 and
                       observed['continuation'] == case['changed_target'],
                       case['name'] + ': direct live pixel RET was not honored')
    if provider == 'stroke-pixel-return':
        oracle_require(observed['status'] == 8 and
                       observed['continuation'] == case['changed_target'],
                       case['name'] + f': nested stroke pixel RET was not honored '
                       f'({observed["status"]}/{observed["continuation"]:04X}, '
                       f'used={observed["used"]})')
    if provider == 'stroke-call-return':
        oracle_require(observed['status'] == 9 and
                       observed['continuation'] == case['changed_target'],
                       case['name'] + ': actual stroke CALL return was not honored')
    if provider == 'pc-stack-live-gates':
        oracle_require('pc-stack-live-gates' in observed['used'] and
                       0x26C0 in own and 0x26D3 in own,
                       case['name'] + ': PC state or live second gate was not used')
        oracle_require(observed['regs']['ds'] == case['provider_ds'],
                       case['name'] + ': live PC-returned DS was not preserved')
    if provider == 'pitch-on-first-pixel':
        oracle_require(provider in observed['used'],
                       case['name'] + ': pitch provider did not fire')
    if provider == 'callback-on-first-pixel':
        oracle_require(provider in observed['used'],
                       case['name'] + ': callback provider did not fire')
    if provider == 'sound-save-words':
        oracle_require(provider in observed['used'],
                       case['name'] + ': sound stack-word provider did not fire')
    if provider == 'state80-sound-interrupt-return':
        oracle_require(observed['status'] == 4 and
                       observed['continuation'] == case['provider_return'],
                       case['name'] + ': changed external IRET was not reported')
    if case.get('sound_vector') is not None or case.get('sound_binding') is False:
        oracle_require(observed['status'] == 1,
                       case['name'] + ': external INT61 seam was not reported')
    if case.get('pc_vector') is not None or case.get('pc_binding') is False:
        oracle_require(observed['status'] == 1,
                       case['name'] + ': PC INT60 seam was not reported')
    if case['name'] == 'counter-one-takes-transition-b':
        oracle_require(0x2723 in own and 0x27A5 in own,
                       case['name'] + ': zero counter did not select transition B')
    if case['name'] == 'three-probes-all-clear-transition-a':
        oracle_require(0x272C in own and 0x2760 in own and 0x2766 in own,
                       case['name'] + ': signed <=10 height did not select transition A')
    if case['name'] == 'three-probes-third-hit-resets':
        oracle_require(0x2745 in own and 0x2763 in own,
                       case['name'] + ': third occupied probe did not take reset')
    if 'expect_status' in case:
        oracle_require((observed['status'], observed['continuation']) ==
                       (case['expect_status'], case['expect_continuation']),
                       case['name'] + ': bounded boundary changed')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State80Access(case, memory, regs, device, native=True)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            try:
                self.access.out_word(port, value, flags, ALL_FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state80-m{mutation}.dll',
                     mutation, 'entity_state80')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_entity_state80_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_entity_state80_adapter
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
            call = Call(*(initial_regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
                'ss', 'sp', 'flags')))
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
            state = {name: getattr(registers, name)
                     for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=bus.access.events, providers=set(bus.access.used),
                    status=status, continuation=state['ip'])


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding = setup(case)
    oracle = original(case, bytearray(initial), dict(regs),
                      copy.deepcopy(device))
    expected_path(case, oracle)
    check_independent_planes(case, device, oracle)
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
    require(actual['memory'] == oracle['memory'], label + ': full RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['used'],
            f'{label}: provider effects {actual["providers"]}/{oracle["used"]}')
    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = observed_own_edges(oracle)
    integrated_sites = {address for source, address in oracle['sites']
                        if source == 'main'}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(integrated_sites),
                event_count=len(oracle['events']), steps=oracle['steps'])


def original_only():
    before = input_hashes()
    oracle_require(len(OWN_INS) == 115 and sum(i.size for i in OWN_INS.values()) == 337,
                   'state80 static byte/site identity changed')
    oracle_require(len(STATIC_EDGES) == 44,
                   f'state80 static branch edge count changed: {sorted(STATIC_EDGES)}')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned main code image hash changed')
    specs = cases()
    covered, edges, integrated = set(), set(), set()
    rows = []
    for case in specs:
        initial, regs, device, _pc, _sound = setup(case)
        observed = original(case, bytearray(initial), dict(regs),
                            copy.deepcopy(device))
        expected_path(case, observed)
        check_independent_planes(case, device, observed)
        if 'expect_status' in case:
            oracle_require((observed['status'], observed['continuation']) ==
                           (case['expect_status'], case['expect_continuation']),
                           case['name'] + ': unexpected declared seam')
        elif case.get('provider', '').startswith('pixel-return-'):
            oracle_require(observed['status'] == 7,
                           case['name'] + ': unexpected direct pixel RET status')
        elif case.get('provider') == 'stroke-pixel-return':
            oracle_require(observed['status'] == 8,
                           case['name'] + ': unexpected nested stroke pixel RET status')
        elif case.get('provider') == 'stroke-call-return':
            oracle_require(observed['status'] == 9,
                           case['name'] + ': unexpected stroke CALL RET status')
        elif case.get('provider') == 'state80-sound-interrupt-return':
            oracle_require(observed['status'] == 4,
                           case['name'] + ': unexpected changed INT61 return status')
        elif case.get('sound_binding') is False or case.get('sound_vector') is not None:
            oracle_require(observed['status'] == 1,
                           case['name'] + ': unexpected unbound INT61 status')
        elif case.get('pc_binding') is False or case.get('pc_vector') is not None:
            oracle_require(observed['status'] == 1,
                           case['name'] + ': unexpected unbound INT60 status')
        else:
            oracle_require((observed['status'], observed['continuation']) ==
                           (0, CONTINUATION),
                           case['name'] + f': boundary was {observed["status"]}/'
                           f'{observed["continuation"]:04X}, not normal 1FEB')
        own_sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
        own_edges = observed_own_edges(observed)
        covered.update(own_sites)
        edges.update(own_edges)
        integrated.update(address for source, address in observed['sites']
                          if source == 'main')
        rows.append(dict(name=case['name'], sites=sorted(own_sites),
                         edges=[list(edge) for edge in sorted(own_edges)],
                         status=observed['status'],
                         continuation=observed['continuation'],
                         events=len(observed['events']), steps=observed['steps'],
                         provider=case.get('provider')))
        gc.collect()
    oracle_require(len(OWN_INS) == 115 and sum(i.size for i in OWN_INS.values()) == 337,
                   'state80 static byte/site identity changed')
    oracle_require(covered == set(OWN_INS),
                   f'state80 site union missing {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == STATIC_EDGES,
                   f'state80 edge union differs: missing={sorted(STATIC_EDGES-edges)} '
                   f'extra={sorted(edges-STATIC_EDGES)}')
    oracle_require(before == input_hashes(),
                   'state80 inputs changed during bounded original-only preflight')
    print(f'PASS entity state80 original: {len(specs)} cases, '
          f'{len(covered)} sites, {len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} bus events; bounded original only')
    return rows


def worker(directory):
    before = input_hashes()
    oracle_require(len(OWN_INS) == 115 and sum(i.size for i in OWN_INS.values()) == 337,
                   'state80 static byte/site identity changed')
    oracle_require(len(STATIC_EDGES) == 44,
                   f'state80 static branch edge count changed: {sorted(STATIC_EDGES)}')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned main code image hash changed')
    specs = cases()
    native = Native(directory)
    rows, all_sites, all_edges, integrated_sites = [], set(), set(), set()
    total_events, total_steps = 0, 0
    for case in specs:
        for core in (True, False):
            row = compare_case(native, case, core=core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            integrated_sites.update(row['integrated_sites'])
            total_events += row['event_count']
            total_steps += row['steps']
        gc.collect()
    oracle_require(all_sites == set(OWN_INS),
                   f'state80 executed sites {len(all_sites)}/{len(OWN_INS)}; '
                   f'missing={sorted(set(OWN_INS)-all_sites)}')
    oracle_require(all_edges == STATIC_EDGES,
                   f'state80 executed edges {len(all_edges)}/{len(STATIC_EDGES)}; '
                   f'missing={sorted(STATIC_EDGES-all_edges)}; '
                   f'extra={sorted(all_edges-STATIC_EDGES)}')

    witnesses = {
        1: 'cadence-mask-retains-bit3',
        2: 'phase-a-pc-live-ds-second-gate-and-saved-words',
        3: 'phase-a-int61-second-option-bit',
        4: 'live-pitch-update-between-probes',
        5: 'first-probe-hit-resets',
        6: 'counter-one-takes-transition-b',
        7: 'first-probe-hit-resets',
        8: 'stroke-nested-pixel-ret-changed',
    }
    mutations = []
    for mutation, case_name in witnesses.items():
        mutant = Native(directory, mutation)
        case = next(item for item in specs if item['name'] == case_name)
        try:
            compare_case(mutant, case, core=True)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, case=case_name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'state80 mutation {mutation} survived {case_name}')
        gc.collect()

    oracle_require(len(mutations) == 8,
                   'state80 completed mutation witness count changed')
    oracle_require(before == input_hashes(),
                   'state80 source inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_range=[ENTRY, END], translated_code_bytes=337,
        instruction_sites=115, own_branch_edges=44,
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(all_sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(all_edges)],
        static_branch_edges=[list(edge) for edge in sorted(STATIC_EDGES)],
        integrated_main_instruction_addresses=sorted(integrated_sites),
        total_bus_events=total_events, original_code_hook_steps=total_steps,
        cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                    continuation=row['continuation'], sites=row['sites'],
                    edges=row['edges'], event_count=row['event_count'],
                    steps=row['steps']) for row in rows],
        input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domain='Original 2693..27E7 state-0080 known handler bytes; four '
               'UNKNOWN one-byte holes are excluded. Logical C core and '
               'Regs-facing adapter compare full 1 MiB RAM, all registers and '
               'defined FLAGS, ordered memory/device bus, VGA planes/latches, '
               'live direct and nested pixel/stroke CALL/RET, shared finish, '
               'INT60/INT61 and stack/provider seams. '
               'The input entry FLAGS are normalized to the declared real-mode '
               'IRET domain (7FD5|2, TF clear).'))
    print(f'PASS entity state80: {len(specs)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'src/game_code.asm', 'src/entity_graphics.asm', 'src/program.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_state80.c', 'c/entity_state80.h', 'c/entity_stroke.c',
        'c/entity_stroke.h',
        'c/entity_finish.c', 'c/entity_finish.h', 'c/entity_pixel.c',
        'c/entity_pixel.h', 'c/entity_vga.c', 'c/entity_vga.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c',
        'c/pcspeaker_interrupt.h', 'c/pcspeaker_dispatch.c',
        'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h', 'c/sound_latches.c',
        'c/sound_latches.h', 'c/sound_latches_sym.h', 'c/pcspeaker_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/entity_state80.py', 'tests/entity_interactions.py',
        'tests/entity_stroke.py',
        'tests/entity_finish.py', 'tests/entity_pixel.py', 'tests/entity_vga.py',
        'tests/minimap_vga.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/sound_latches.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py',
        'tools/coverage.py', 'tools/unpack.py', 'tools/resources.py',
        'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def main():
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                    check=True)
        return
    if len(sys.argv) == 2 and sys.argv[1] == '--original-worker':
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-state80 arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state80-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                    check=True)


if __name__ == '__main__':
    main()
