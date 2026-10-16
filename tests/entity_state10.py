"""Bounded original-versus-C checks for the state-0010 entity handler."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import json
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
ENTRY, END = 0x23F3, 0x254F
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
EXCHANGE_ENTRY, EXCHANGE_RET = 0x5EBA, 0x5F0E
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9),
                (0x2148, 0x2169))
CONTINUATION = 0x1FEB
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
ALL_FLAGS = interactions.FLAGS
MAX_INSTRUCTIONS, MAX_EVENTS = 4096, 4096
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state10-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, END)
PIXEL_INS = decoded_span(PIXEL_ENTRY, PIXEL_RET + 1)
EXCHANGE_INS = decoded_span(EXCHANGE_ENTRY, EXCHANGE_RET + 1)
FINISH_INS = {
    ins.address: ins
    for start, end in FINISH_SPANS
    for ins in MD.disasm(IMAGE[start:end], start)
}
INTEGRATED_INS = dict(OWN_INS)
for group in (PIXEL_INS, EXCHANGE_INS, FINISH_INS, interactions.MAIN_INS):
    INTEGRATED_INS.update(group)

OWN_BRANCHES = {
    address: ins for address, ins in OWN_INS.items()
    if (ins.group(capstone.CS_GRP_JUMP) or
        ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz'))
}


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
    """Focused cadence, pixel, exchange, map, sound, alias and seam fixtures."""
    rows = [
        dict(name='cadence-ordinary-direct-return', cadence=2),
        dict(name='cadence-zero-increment-direct-return', cadence=0),
        dict(name='cadence-eight-phase-normal-zero-loop', cadence=7,
             pixels='empty', shift=0),
        dict(name='cadence-wrap-phase-normal-shift-seven', cadence=15,
             pixels='empty', shift=7, df=True, vga=True),
        dict(name='raw-eleven-special-before-increment', cadence=0x11,
             pixels='empty', shift=0),
        dict(name='raw-eleven-special-shift-seven-df', cadence=0x11,
             pixels='empty', shift=7, df=True, vga=True),
        dict(name='raw-ten-is-not-special', cadence=0x10,
             pixels='empty'),
        dict(name='first-two-pixels-empty', cadence=7,
             pixels='first-two-empty-third-empty', shift=7),
        dict(name='first-pixel-occupied', cadence=7,
             pixels='first-only', shift=7, vga=True),
        dict(name='second-pixel-occupied', cadence=7,
             pixels='second-only', shift=7, vga=True),
        dict(name='third-pixel-occupied', cadence=7,
             pixels='third-only', shift=7),
        dict(name='all-three-pixels-occupied', cadence=7,
             pixels='occupied', shift=7, map_nibble=9),
        dict(name='signed-height-equal-b4-mark', cadence=7,
             y=0x00B3, pixels='empty'),
        dict(name='signed-height-b3-continues', cadence=7,
             y=0x00B2, pixels='empty', shift=3),
        dict(name='signed-negative-height-edge', cadence=7,
             y=0xFFFE, pixels='empty', shift=7),
        dict(name='shift-loop-zero', cadence=7, shift=0, pixels='empty'),
        dict(name='shift-loop-seven-rcr-carry', cadence=7, shift=7,
             pixels='third-only', vga=True),
        dict(name='special-shift-loop-seven', cadence=0x11, shift=7,
             pixels='empty', vga=True),
        dict(name='map-ss-nibble-nine', cadence=7, shift=7,
             pixels='occupied', map_nibble=9),
        dict(name='map-ss-nibble-other', cadence=7, shift=7,
             pixels='occupied', map_nibble=1),
        dict(name='map-ss-not-ds', cadence=7, shift=7, pixels='occupied',
             map_nibble=9, ds_map_nibble=1, vga=True),
        dict(name='sound-gate-disabled', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0),
        dict(name='sound-options-clear', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0xFF, options=0),
        dict(name='sound-int61-adlib-040a', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0xFF, options=1,
             driver='adlib'),
        dict(name='sound-int61-tandy-040a', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0xFF, options=2,
             driver='tandysnd'),
        dict(name='sound-int61-unbound-binding', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0xFF, options=1,
             sound_binding=False),
        dict(name='sound-int61-unbound-vector', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0xFF, options=1,
             sound_vector=(0x0200, 0x7000)),
        dict(name='sound-int61-changed-iret', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, enabled=0xFF, options=1,
             provider='sound-interrupt-return', provider_return=0x4567),
        dict(name='sound-int61-restored-ds-live-stores', cadence=7, shift=7,
             pixels='occupied', map_nibble=9, record_bits=0x0010,
             enabled=0xFF, options=1, provider='sound-restore-ds',
             provider_ds=0x6100, alternate_x=0x0060, alternate_y=0x0042,
             alternate_callback=0xC0DE),
        dict(name='live-pixel-ret-normal-call', cadence=7, shift=4,
             pixels='empty', provider='pixel-return-2418',
             changed_target=0x4567),
        dict(name='cross-pixel-ret-normal-to-special-continuation', cadence=7,
             shift=4, pixels='empty', provider='pixel-return-2418',
             changed_target=0x251D),
        dict(name='live-exchange-ret-normal-call', cadence=7, shift=7,
             pixels='occupied', provider='exchange-return-2441',
             changed_target=0x4567, vga=True),
        dict(name='cross-exchange-ret-normal-to-special-continuation',
             cadence=7, shift=7, pixels='occupied',
             provider='exchange-return-2441', changed_target=0x253D, vga=True),
        dict(name='live-pixel-ret-special-call', cadence=0x11, shift=5,
             pixels='empty', provider='pixel-return-251a',
             changed_target=0x4567),
        dict(name='live-exchange-ret-special-first', cadence=0x11, shift=7,
             pixels='empty', provider='exchange-return-253a',
             changed_target=0x4567, vga=True),
        dict(name='live-exchange-ret-special-second', cadence=0x11, shift=7,
             pixels='empty', provider='exchange-return-2545',
             changed_target=0x4567, vga=True),
        dict(name='live-normal-pushed-x-pop', cadence=7, shift=7,
             pixels='occupied', provider='saved-x', replacement_x=0x1353),
        dict(name='special-second-exchange-plane-state', cadence=0x11,
             shift=4, pixels='empty', vga=True, plane_check=True),
        dict(name='special-pitch-live-before-second-exchange', cadence=0x11,
             shift=3, pixels='empty', vga=True, provider='pitch-on-first-pixel',
             pitch=0x00D0, pitch_after=0x0040),
        dict(name='collision-callback-slot-live', cadence=7, shift=7,
             pixels='empty', provider='callback-on-first-pixel',
             callback_slot=0xA35C),
        dict(name='record-ds-ss-shared', cadence=7, shift=3,
             pixels='empty', ds=0x5000, ss=0x5000, si=0x6000,
             sp=0xD000, vga=True),
        dict(name='ss-vga-stack-and-latches', cadence=7, shift=7,
             pixels='empty', ss=0x9FFF, sp=0xD000, vga=True,
             gc5=0x08, map_mask=0x0F, plane_check=True,
             expect_status=7, expect_continuation=0xDBE4),
        dict(name='ds-record-word-offset-wrap', cadence=7, shift=2,
             pixels='empty', ds=0xFFFF, si=0xFFF0),
        dict(name='ss-stack-offset-physical-wrap', cadence=7, shift=7,
             pixels='empty', ss=0xFFFF, sp=0x0001, vga=True),
        dict(name='entry-flags-df-rmw-phase', cadence=7, shift=7,
             pixels='empty', flags=0x0E47, df=True),
        dict(name='readback-mode-one-incoming-state', cadence=7, shift=7,
             pixels='occupied', vga=True, gc5=0x08, gc7=0x08, gc2=0x08,
             map_nibble=9, plane_check=True),
        dict(name='poisoned-registers-and-ram', cadence=2, poison=True,
             seed=0x23F3),
        dict(name='mutation-special-second-exchange', cadence=0x11,
             shift=7, pixels='empty', vga=True),
    ]
    oracle_require(35 <= len(rows) <= 50,
                   f'state10 fixture count changed: {len(rows)}')
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'state10 fixture names are not unique')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x23F3 + index * 43)
    return rows


def setup(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('si', 0x6000)
    template.setdefault('sp', 0xD000)
    template.setdefault('x', 0x0020 + (case.get('shift', 0) & 7))
    template.setdefault('y', 0x0020)
    template.setdefault('delta_x', 0)
    template.setdefault('cadence', 1)
    template.setdefault('enabled', 0)
    template.setdefault('options', 0)
    template.setdefault('driver', 'adlib')
    template.setdefault('seed', 0x23F3 + len(case['name']))
    raw_flags = template.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    if template.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    template['flags'] = flags

    setup_template = dict(template)
    # The shared interaction fixture's VGA seed helper interprets samples as
    # SS-relative. State-0010 instead exchanges at its actual ES:A000 offsets,
    # so it creates and seeds the planar device below.
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
    # Seed the caller's existing stack word before the record. Deliberate
    # aliases therefore have an explicit fixture precedence: record inputs
    # win initially, then the handler's real PUSH/POP accesses take over.
    put16(memory, ss, sp, template.get('outer_return', 0x7A5C))
    if case.get('poison'):
        import random
        rng = random.Random(case['seed'])
        for index in range(SIZE):
            memory[index] = rng.randrange(256)
        # Restore all loaded pinned components after RAM poisoning.
        load, loaded = interactions.code_for_case(case)
        base = (load << 4) & MASK
        first = min(len(loaded), SIZE - base)
        memory[base:base + first] = loaded[:first]
        memory[:len(loaded) - first] = loaded[first:]
        pc_image = interactions.PC_IMAGE
        memory[physical(interactions.PC_SEG, 0):
               physical(interactions.PC_SEG, 0) + len(pc_image)] = pc_image
        driver_image = interactions.sound.IMAGES[template['driver']][0]
        memory[physical(interactions.SOUND_SEG, 0):
               physical(interactions.SOUND_SEG, 0) + len(driver_image)] = driver_image
        # Restore the public vectors and a deterministic stack/record after poison.
        put16(memory, 0, 0x180, interactions.PC_ENTRY)
        put16(memory, 0, 0x182, interactions.PC_SEG)
        sound_ip, sound_cs = case.get('sound_vector', (0, interactions.SOUND_SEG))
        put16(memory, 0, 0x184, sound_ip)
        put16(memory, 0, 0x186, sound_cs)
        put16(memory, ss, sp, template.get('outer_return', 0x7A5C))

    # Noncanonical DS still receives the observed live pixel-mask table.
    if ds != DATA_SEGMENT:
        for index, value in enumerate(PIXEL_MASKS):
            put8(memory, ds, 0x547C + index, value)
    put16(memory, ds, 0x0004, template.get('pitch', 0x00D0))
    put16(memory, ds, si, template.get('x',
             0x0020 + (case.get('shift', 0) & 7)))
    put16(memory, ds, si + 2, template['y'])
    put16(memory, ds, si + 4, template.get('delta_x', 0))
    put16(memory, ds, si + 6, template.get('delta_y', 0))
    put16(memory, ds, si + 8, template.get('record_bits', 0))
    put16(memory, ds, si + 0x0A, template.get('record_word_a', 0x1919))
    put16(memory, ds, si + 0x0C, template.get('record_word_c', 0x2A2A))
    put16(memory, ds, si + 0x14, template.get('callback_initial', 0x7654))
    put8(memory, ds, si + 0x23, template.get('state_byte_23', 0x05))
    put8(memory, ds, si + 0x24, template.get('entity_flags', 0xA5))
    put8(memory, ds, si + 0x27, template.get('record_delta', 0))
    put8(memory, ds, si + 0x28, template['cadence'])
    put8(memory, ds, si + 0x29, template.get('state_byte_29', 0x17))
    put8(memory, ds, si + 0x2A, template.get('state_byte_2a', 0x6B))
    put16(memory, ds, 0x002E, template.get('callback_slot', 0x6170))
    put8(memory, ds, 0x2010, template['enabled'])
    put8(memory, ds, 0x25A7, template['options'])
    if 'ds_map_nibble' in case:
        # The DS decoy is kept separate from the SS-owned map byte.
        off = map_offset(template['x'], (template['y'] + 1) & 0xFFFF)
        put8(memory, ds, off, case['ds_map_nibble'])
    if case.get('provider') == 'sound-restore-ds':
        alternate = case['provider_ds']
        put16(memory, alternate, si, case['alternate_x'])
        put16(memory, alternate, si + 2, case['alternate_y'])
        put16(memory, alternate, si + 4, 0)
        put16(memory, alternate, si + 6, 0)
        put16(memory, alternate, si + 8, case['record_bits'])
        put16(memory, alternate, si + 0x14, 0x7654)
        put8(memory, alternate, si + 0x23, 0x05)
        put8(memory, alternate, si + 0x24, 0xA5)
        put8(memory, alternate, si + 0x27, 0)
        put8(memory, alternate, si + 0x28, case['cadence'])
        put8(memory, alternate, si + 0x29, 0x17)
        put8(memory, alternate, si + 0x2A, 0x6B)
        put16(memory, alternate, 0x002E, case['alternate_callback'])

    # Construct incoming VGA state without running the setup routine. This
    # makes the mode/read-map assumptions explicit and retains the actual
    # 5EBA latch reads under the incoming configuration.
    if case.get('vga'):
        if device is None:
            device = MinimapVga(template['seed'], read_map=0)
        device.seq[4] = 0x06
        device.seq[2] = case.get('map_mask', 0x0F) & 0x0F
        device.gc[0], device.gc[1], device.gc[3] = 0, 0, 0
        device.gc[2] = case.get('gc2', 0)
        device.gc[4] = case.get('read_map', 0) & 3
        device.gc[5] = case.get('gc5', 0) & 0x0B
        device.gc[6] = 0x05
        device.gc[7] = case.get('gc7', 0x0F) & 0x0F
        device.gc[8] = case.get('gc8', 0xFF) & 0xFF
        fill = 0xFF if case.get('pixels') == 'occupied' else 0
        for plane in device.planes:
            plane[:] = bytes((fill,)) * 0x10000
    else:
        device = None
        fill = 0xFF if case.get('pixels') == 'occupied' else 0

    def seed_pixel_triplet_at(base, values):
        step = -1 if flags & 0x0400 else 1
        for index, value in enumerate(values):
            offset = (base + index * step) & 0xFFFF
            address = physical(0xA000, offset)
            if device is None:
                memory[address] = value & 0xFF
            else:
                if case.get('gc5', 0) & 0x08:
                    for plane in range(4):
                        device.planes[plane][offset] = value & 0xFF
                else:
                    device.planes[device.gc[4] & 3][offset] = value & 0xFF

    actual_x = get16(memory, ds, si)
    actual_y = get16(memory, ds, si + 2)
    delta_x = get16(memory, ds, si + 4)
    normal_x = (actual_x + delta_x) & 0xFFFF
    special_y = (actual_y - 2) & 0xFFFF
    pixel_values = {
        'empty': (0, 0, 0),
        'first-two-empty-third-empty': (0, 0, 0),
        'first-only': (0xFF, 0, 0),
        'second-only': (0, 0xFF, 0),
        'third-only': (0, 0, 0xFF),
        'occupied': (0xFF, 0xFF, 0xFF),
    }.get(case.get('pixels', 'empty'), (0, 0, 0))
    # Place the vector at both potential helper coordinates. Special-path
    # exchanges use the first address plus the live DS row pitch for pass two.
    seed_pixel_triplet_at(pixel_start(normal_x, actual_y), pixel_values)
    if case.get('cadence') == 0x11:
        special_base = pixel_start(normal_x, special_y)
        seed_pixel_triplet_at(special_base, pixel_values)
        seed_pixel_triplet_at((special_base +
                               template.get('pitch', 0x00D0)) & 0xFFFF,
                              pixel_values)

    map_y = (actual_y + 1) & 0xFFFF
    ss_map = map_offset(actual_x, map_y)
    nibble = case.get('map_nibble', 9) & 0x0F
    ss_address = physical(ss, ss_map)
    if device is not None and VGA_BASE <= ss_address < VGA_END:
        device.planes[device.gc[4] & 3][ss_address - VGA_BASE] = nibble
    else:
        memory[ss_address] = nibble
    return memory, regs, device, pc_binding, sound_binding


class State10Access(interactions.Access):
    """Bounded child-return and live-field providers over the shared RAM."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []
        self.return_offsets = {
            'pixel-return-2418': 4,
            'pixel-return-251a': 6,
            'exchange-return-2441': 6,
            'exchange-return-253a': 10,
            'exchange-return-2545': 2,
        }
        self.return_address = physical(regs['ss'],
            (regs['sp'] - self.return_offsets.get(case.get('provider'), 2)) & 0xFFFF)
        initial_x = get16(memory, regs['ds'], regs['si'])
        initial_dx = get16(memory, regs['ds'], (regs['si'] + 4) & 0xFFFF)
        self.table_address = physical(regs['ds'],
            (0x547C + ((initial_x + initial_dx) & 7)) & 0xFFFF)
        self.return_armed = False

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for effect, address, value in pending:
            if effect == 'pitch':
                self.modify_word(self.regs['ds'], 4, value)

    def _provider(self, kind, address):
        super()._provider(kind, address)
        case = self.case
        effect = case.get('provider')
        if effect == 'sound-restore-ds' and kind == 'write' and 'sound-ds' not in self.used:
            driver = case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                self.modify_word(self.regs['ss'], self.regs['sp'] - 8,
                                 case['provider_ds'])
                self.used.add('sound-ds')
        if (effect in self.return_offsets and kind == 'read' and
                address == self.return_address and self.return_armed and
                effect not in self.used):
            self.modify_word(self.regs['ss'],
                (self.regs['sp'] - self.return_offsets[effect]) & 0xFFFF,
                case.get('changed_target', 0x4567))
            self.used.add(effect)
        if effect == 'saved-x' and kind == 'read' and address == self.table_address and effect not in self.used:
            self.modify_word(self.regs['ss'], (self.regs['sp'] - 2) & 0xFFFF,
                             case.get('replacement_x', 0x1357))
            self.used.add(effect)

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        address &= MASK
        effect = self.case.get('provider')
        if effect in self.return_offsets and kind == 'write' and address == self.return_address:
            target = {
                'pixel-return-2418': 0x241B,
                'pixel-return-251a': 0x251D,
                'exchange-return-2441': 0x2444,
                'exchange-return-253a': 0x253D,
                'exchange-return-2545': 0x2548,
            }[effect]
            # Arm only when the call installs its own return word. This
            # avoids mistaking an earlier POP at the same SS:SP address for
            # the later special-path second exchange RET.
            if (value & 0xFF) == (target & 0xFF) and effect not in self.used:
                self.return_armed = True
        if (effect == 'callback-on-first-pixel' and kind == 'read' and
                VGA_BASE <= address < VGA_END and effect not in self.used):
            self.modify_word(self.regs['ds'], 0x002E,
                             self.case.get('callback_slot', 0xA35C))
            self.used.add(effect)
        if (effect == 'pitch-on-first-pixel' and kind == 'write' and
                VGA_BASE <= address < VGA_END and effect not in self.used):
            self.modify_word(self.regs['ds'], 0x0004,
                             self.case.get('pitch_after', 0x0040))
            self.used.add(effect)
        return result

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('state10 OUT event budget exhausted')
        if self.device is not None and port in (0x3C4, 0x3CE):
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


def main_call_contracts():
    result = {
        0x2418: ({PIXEL_RET}, 7),
        0x251A: ({PIXEL_RET}, 7),
        0x2441: ({EXCHANGE_RET}, 8),
        0x253A: ({EXCHANGE_RET}, 8),
        0x2545: ({EXCHANGE_RET}, 8),
        # The finish tail makes the actual CALL to 2EC0 at 1FE8.
        0x1FE8: (set(interactions.MAIN_RETS), 5),
    }
    return result


CALL_CONTRACTS = main_call_contracts()


def original(case, memory, regs, device, *, entry_flag_mask=ALL_FLAGS):
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=entry_flag_mask,
        main_instructions=INTEGRATED_INS,
        main_call_returns=CALL_CONTRACTS,
        stop_offsets={CONTINUATION: 0},
        access_factory=lambda c, m, r, d: State10Access(c, m, r, d),
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
    if case.get('cadence', 1) == 0x11:
        oracle_require(0x23F9 in own,
                       case['name'] + ': raw-11 special path did not execute')
    if case.get('cadence', 1) == 7:
        oracle_require(0x240F in own,
                       case['name'] + ': phase-eight path did not execute')
    if case.get('cadence', 1) == 0x10:
        oracle_require(0x23FC in own and 0x250C not in own and
                       get8(observed['memory'], observed['regs']['ds'],
                            observed['regs']['si'] + 0x28) == 1,
                       case['name'] + ': raw-10 threshold was treated as special')
    if case.get('cadence', 1) == 0x11:
        oracle_require(0x23FC not in own,
                       case['name'] + ': raw-11 special path entered ordinary cadence')
        if not case.get('provider', '').startswith(('pixel-return', 'exchange-return')):
            oracle_require(get8(observed['memory'], observed['regs']['ds'],
                                observed['regs']['si'] + 0x28) == 0,
                           case['name'] + ': completed raw-11 path did not reset cadence')
    if case.get('provider', '').startswith('pixel-return'):
        oracle_require(observed['status'] == 7,
                       case['name'] + ': changed pixel RET was not reported')
    if case.get('provider', '').startswith('exchange-return'):
        oracle_require(observed['status'] == 8,
                       case['name'] + ': changed exchange RET was not reported')
    if case.get('provider') == 'saved-x':
        oracle_require('saved-x' in observed['used'],
                       case['name'] + ': saved-X provider did not fire')
        oracle_require((0x243B, 0x2437) in observed_own_edges(observed),
                       case['name'] + ': live POP CX did not change the shift loop')
    if case.get('provider') == 'sound-interrupt-return':
        oracle_require(observed['status'] == 4 and
                       observed['continuation'] == case.get('provider_return'),
                       case['name'] + ': changed INT61 return was not reported')
    if case.get('provider') == 'sound-restore-ds':
        original_ds = DATA_SEGMENT
        alternate = case['provider_ds']
        si = observed['regs']['si']
        oracle_require('sound-ds' in observed['used'] and
                       observed['regs']['ds'] == alternate,
                       case['name'] + ': live DS POP was not restored from the frame')
        oracle_require(get16(observed['memory'], alternate, si + 0x14) ==
                       case['alternate_callback'],
                       case['name'] + ': callback store did not use restored DS')
        oracle_require(get16(observed['memory'], original_ds, si + 8) == 0x0010,
                       case['name'] + ': stores incorrectly remained on entry DS')
    if case.get('sound_binding') is False or case.get('sound_vector') is not None:
        oracle_require(observed['status'] == 1,
                       case['name'] + ': unbound INT61 seam was not reported')
    if case['name'] == 'collision-callback-slot-live':
        resulting = get16(observed['memory'], observed['regs']['ds'],
                          observed['regs']['si'] + 8)
        oracle_require((resulting & 0x0014) == 0x0004,
                       case['name'] + ': collision-free transition missed state bit 0004')
        oracle_require('callback-on-first-pixel' in observed['used'],
                       case['name'] + ': callback slot provider did not run')
    if case.get('provider', '').startswith(('pixel-return', 'exchange-return')):
        oracle_require(observed['continuation'] == case.get('changed_target'),
                       case['name'] + ': actual child RET target was not preserved')
    if 'expect_status' in case:
        oracle_require((observed['status'], observed['continuation']) ==
                       (case['expect_status'], case['expect_continuation']),
                       case['name'] + ': actual child/device seam changed')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State10Access(case, memory, regs, device, native=True)

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
        path = build(Path(directory) / f'entity-state10-m{mutation}.dll',
                     mutation, 'entity_state10')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_entity_state10_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_entity_state10_adapter
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
    oracle_require(len(OWN_INS) == 127 and sum(i.size for i in OWN_INS.values()) == 348,
                   'state10 static byte/site identity changed')
    oracle_require(len(STATIC_EDGES) == 33,
                   f'state10 static branch edge count changed: {sorted(STATIC_EDGES)}')
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
        if case.get('provider') in ('pixel-return-2418', 'pixel-return-251a'):
            oracle_require(observed['status'] == 7,
                           case['name'] + ': unexpected pixel return status')
        elif case.get('provider') in ('exchange-return-2441',
                                      'exchange-return-253a',
                                      'exchange-return-2545'):
            oracle_require(observed['status'] == 8,
                           case['name'] + ': unexpected exchange return status')
        elif case.get('provider') == 'sound-interrupt-return':
            oracle_require(observed['status'] == 4,
                           case['name'] + ': unexpected INT61 return status')
        elif case.get('sound_binding') is False or case.get('sound_vector') is not None:
            oracle_require(observed['status'] == 1,
                           case['name'] + ': unexpected unbound INT61 status')
        elif 'expect_status' in case:
            oracle_require((observed['status'], observed['continuation']) ==
                           (case['expect_status'], case['expect_continuation']),
                           case['name'] + ': unexpected device-alias seam')
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
    oracle_require(len(OWN_INS) == 127 and sum(i.size for i in OWN_INS.values()) == 348,
                   'state10 static byte/site identity changed')
    oracle_require(covered == set(OWN_INS),
                   f'state10 site union missing {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == STATIC_EDGES,
                   f'state10 edge union differs: missing={sorted(STATIC_EDGES-edges)} '
                   f'extra={sorted(edges-STATIC_EDGES)}')
    oracle_require(before == input_hashes(),
                   'state10 inputs changed during bounded original-only preflight')
    print(f'PASS entity state10 original: {len(specs)} cases, '
          f'{len(covered)} sites, {len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} bus events; bounded original only')
    return rows


def worker(directory):
    before = input_hashes()
    oracle_require(len(OWN_INS) == 127 and sum(i.size for i in OWN_INS.values()) == 348,
                   'state10 static byte/site identity changed')
    oracle_require(len(STATIC_EDGES) == 33,
                   f'state10 static branch edge count changed: {sorted(STATIC_EDGES)}')
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
                   f'state10 executed sites {len(all_sites)}/{len(OWN_INS)}; '
                   f'missing={sorted(set(OWN_INS)-all_sites)}')
    oracle_require(all_edges == STATIC_EDGES,
                   f'state10 executed edges {len(all_edges)}/{len(STATIC_EDGES)}; '
                   f'missing={sorted(STATIC_EDGES-all_edges)}; '
                   f'extra={sorted(all_edges-STATIC_EDGES)}')

    witnesses = {
        1: 'raw-ten-is-not-special',
        2: 'cadence-eight-phase-normal-zero-loop',
        3: 'signed-negative-height-edge',
        4: 'shift-loop-seven-rcr-carry',
        5: 'map-ss-not-ds',
        6: 'live-pixel-ret-normal-call',
        7: 'live-normal-pushed-x-pop',
        8: 'mutation-special-second-exchange',
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
            raise OracleFailure(f'state10 mutation {mutation} survived {case_name}')
        gc.collect()

    oracle_require(len(mutations) == 8,
                   'state10 completed mutation witness count changed')
    oracle_require(before == input_hashes(),
                   'state10 source inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_range=[ENTRY, END], translated_code_bytes=348,
        instruction_sites=127, own_branch_edges=33,
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
        domain='Original 23F3..254E state-0010 handler; logical C core and '
               'Regs-facing adapter. Full 1 MiB RAM, all registers and defined '
               'FLAGS, ordered memory/device bus, VGA planes/latches and live '
               'pixel/exchange CALL/RET, finish, INT61 and stack/provider seams. '
               'The input entry FLAGS are normalized to the declared real-mode '
               'IRET domain (7FD5|2, TF clear).'))
    print(f'PASS entity state10: {len(specs)} fixtures x core/adapter, '
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
        'c/entity_state10.c', 'c/entity_state10.h',
        'c/entity_finish.c', 'c/entity_finish.h', 'c/entity_pixel.c',
        'c/entity_pixel.h', 'c/entity_vga.c', 'c/entity_vga.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c',
        'c/pcspeaker_interrupt.h', 'c/pcspeaker_dispatch.c',
        'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h', 'c/sound_latches.c',
        'c/sound_latches.h', 'c/sound_latches_sym.h', 'c/pcspeaker_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/entity_state10.py', 'tests/entity_interactions.py',
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
        raise SystemExit('Unexpected entity-state10 arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state10-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                    check=True)


if __name__ == '__main__':
    main()
