"""Bounded original-versus-C checks for the 2B35..2D0E state-0800 parent."""
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
ENTRY, END, MAIN_SEG = 0x2B35, 0x2D0F, interactions.MAIN_SEG
MASK_RET = 0x6140
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9),
                (0x2148, 0x2169))
BUFFER_SEGMENT = 0x7000
CONTINUATION = 0x1FEB
MASK_TABLE = 0x547C
MAX_INSTRUCTIONS, MAX_EVENTS = 4096, 4096
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state800-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state800-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, 0x2B50)
OWN_INS.update(decoded_span(0x2B51, END))
MASK_INS = mask_rows.INS[mask_rows.THIRTEEN]
PIXEL_INS = decoded_span(PIXEL_ENTRY, PIXEL_RET + 1)
FINISH_INS = {ins.address: ins for start, end in FINISH_SPANS
              for ins in MD.disasm(IMAGE[start:end], start)}
INTEGRATED_INS = dict(OWN_INS)
for group in (MASK_INS, PIXEL_INS, FINISH_INS,
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


def interaction_map_offset(x, y):
    qx = (x & 0xFFFF) >> 2
    qy = (((y - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12) & 0xFFFF


def state_map_offset(x, y):
    qx = (x & 0xFFFF) >> 2
    qy = (((y - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12) & 0xFFFF


def cases():
    """Focused parent fixtures plus every signed 13-row selector value."""
    rows = []
    # On entry AL is incremented first.  These are precisely the 130 updated
    # bytes accepted by the signed JL at 2B58 and passed to DEC/CBW at 2B5D.
    for index, updated in enumerate((1, 2, *range(0x80, 0x100))):
        rows.append(dict(name=f'mask-selector-{updated:02x}',
                         phase=(updated - 1) & 0xFF,
                         seed=0x8000 + index * 37))
    rows.extend([
        dict(name='exact-18-resets-and-zero-y-transition', phase=0x17,
             y=0x40),
        dict(name='raw-ff-wraps-to-zero-y-boundary', phase=0xFF,
             y=0xB3),
        dict(name='ordinary-phase-returns-iteration-tail', phase=5),
        dict(name='cadence-three-y-increment-before-pixel', phase=2,
             x=0x40, y=0x40, delta=1, pixel=0),
        dict(name='cadence-three-y-b4-inactive', phase=2,
             x=0x40, y=0xB3, delta=0),
        dict(name='cadence-f-y-increment-not-performed', phase=0x0E,
             x=0x40, y=0x40, delta=1, pixel=0),
        # Both movement modes execute two signed X additions and bounds checks.
        *[dict(name=f'{prefix}-{name}', phase=phase, x=x, delta=delta)
          for prefix, phase in (('f', 0x0E), ('three', 2))
          for name, x, delta in (
              ('lower-first-fail', 0x000F, 0),
              ('lower-second-fail', 0x0011, 0xFF),
              ('lower-equal-in', 0x0010, 0),
              ('upper-first-fail', 0x067F, 1),
              ('upper-second-fail', 0x067E, 1),
              ('upper-equal-in', 0x067F, 0))],
        dict(name='f-pixel-clear-transitions', phase=0x0E,
             x=0x40, y=0x40, delta=1, pixel=0),
        dict(name='f-second-x-add-selects-collision-pixel', phase=0x0E,
             x=0x40, y=0x40, delta=1, pixel=0xFF, map_nibble=1),
        dict(name='three-pixel-clear-transitions', phase=2,
             x=0x40, y=0x40, delta=1, pixel=0),
        dict(name='three-second-x-add-selects-collision-pixel', phase=2,
             x=0x40, y=0x40, delta=1, pixel=0xFF, map_nibble=1),
        *[dict(name=f'map-seven-{sign}', phase=0x0E, x=0x40, y=0x40,
               delta=delta, pixel=0xFF, map_nibble=7)
          for sign, delta in (('positive', 1), ('negative', 0xFF))],
        *[dict(name=f'map-eight-{sign}', phase=0x0E, x=0x40, y=0x40,
               delta=delta, pixel=0xFF, map_nibble=8)
          for sign, delta in (('positive', 1), ('negative', 0xFF))],
        dict(name='map-nibble-zero-falls-to-shared-finish', phase=0x0E,
             x=0x40, y=0x40, delta=0, pixel=0xFF, map_nibble=0),
        dict(name='map-index-stack-alias', phase=0x0E, x=0x40, y=0x40,
             delta=0, pixel=0xFF, map_nibble=9, stack_alias=True),
        dict(name='nibble-nine-disabled-driver', phase=0x0E, x=0x40,
             y=0x40, pixel=0xFF, map_nibble=9, enabled=0),
        dict(name='nibble-nine-options-clear', phase=0x0E, x=0x40,
             y=0x40, pixel=0xFF, map_nibble=9, enabled=0xFF, options=0),
        dict(name='nibble-nine-bound-service', phase=0x0E, x=0x40,
             y=0x40, pixel=0xFF, map_nibble=9, enabled=0xFF, options=3),
        dict(name='nibble-nine-unbound-vector', phase=0x0E, x=0x40,
             y=0x40, pixel=0xFF, map_nibble=9, enabled=0xFF, options=3,
             sound_vector=(0, 0x6200)),
        dict(name='nibble-nine-changed-iret', phase=0x0E, x=0x40,
             y=0x40, pixel=0xFF, map_nibble=9, enabled=0xFF, options=3,
             provider='sound-return', changed_target=0x4567),
        dict(name='nibble-nine-live-returned-ds-before-neg', phase=0x0E,
             x=0x40, y=0x40, delta=1, pixel=0xFF, map_nibble=9,
             enabled=0xFF, options=3, provider='sound-live-ds',
             alternate_ds=0x6100),
        dict(name='nibble-nine-bit-one-alone-enabled', phase=0x0E,
             x=0x40, y=0x40, pixel=0xFF, map_nibble=9,
             enabled=0xFF, options=2),
        dict(name='negative-nibble-one-interaction-pc', phase=0x0E,
             x=0x40, y=0x40, pixel=0xFF, map_nibble=1,
             interaction_nibble=1, record_bits=0, enabled=0, options=1),
        dict(name='pixel-f-call-return-changed', phase=0x0E, x=0x40,
             y=0x40, delta=0, provider='pixel-return-f',
             changed_target=0x2C2B),
        dict(name='pixel-three-call-return-changed', phase=2, x=0x40,
             y=0x40, delta=0, provider='pixel-return-three',
             changed_target=0x2B93),
        dict(name='mask-live-return-changed', phase=0,
             provider='mask-return', changed_target=0x2B93),
        dict(name='live-ds-from-mask-child', phase=0,
             provider='mask-live-ds', alternate_ds=0x6100),
        dict(name='record-stack-ss-ds-alias', phase=5, ds=0x5000,
             ss=0x5000, si=0x8000, sp=0xD000),
        dict(name='physical-word-wrap-stack', phase=0, x=0x40, y=0x40,
             ss=0xFFFF, sp=0x0011, provider='mask-return',
             changed_target=0x4567),
        dict(name='signed-lower-bound-wrap-through-negative-x', phase=0x0E,
             x=0x000A, y=0x40, delta=0xFE),
        dict(name='signed-negative-x-wrap-excluded', phase=0x0E,
             x=0x0000, y=0x40, delta=0xFF),
        dict(name='flags-df-and-rmw-entry-phase', phase=0x0E, x=0x40,
             y=0x40, delta=0x80, pixel=0xFF, map_nibble=8,
             df=True, flags=0x0E47),
        dict(name='parent-sound-vga-register-state', phase=0x0E,
             x=0x40, y=0x40, delta=0, pixel=0xFF, map_nibble=3,
             gc5=0x08, gc7=0x08, gc2=0x08, seq_mask=0x0F,
             read_map=0, vga_mode_one=True),
        dict(name='poisoned-live-registers-and-ram', phase=0x0E,
             poison=True, seed=0x80A0, x=0x40, y=0x40,
             delta=0, pixel=0xFF, map_nibble=3),
    ])
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x8000 + index * 67)
        row.setdefault('enabled', 0)
        row.setdefault('options', 0)
        row.setdefault('driver', 'adlib')
        row.setdefault('record_bits', 0xFFFF)
        row.setdefault('df', False)
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'state800 fixture names must be unique')
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
    put16(memory, segment, si, case.get('x', 0x40))
    put16(memory, segment, si + 2, case.get('y', 0x40))
    put16(memory, segment, si + 4, case.get('record4', 0x0020))
    put16(memory, segment, si + 6, case.get('record6', 0x0010))
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
    put16(memory, ds, 0x002E, case.get('callback_slot', 0x6170))
    put16(memory, ds, 0x0032, case.get('callback_slot32', 0x6172))
    put16(memory, ds, 0x003E, case.get('callback_slot3e', 0x6174))
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
        seed_record(memory, alt, si, dict(case))
        put16(memory, alt, 0x1FE8, case.get('buffer_segment', BUFFER_SEGMENT))
        put16(memory, alt, 0x002E, case.get('callback_slot', 0x6170))

    device = configure_vga(0x2000 ^ case['seed'])
    if case.get('vga_mode_one'):
        device.gc[5] = case.get('gc5', 0x08)
        device.gc[7] = case.get('gc7', 0x08)
        device.gc[2] = case.get('gc2', 0x08)
        device.gc[4] = case.get('read_map', 0) & 3
        device.seq[2] = case.get('seq_mask', 0x0F) & 0x0F
    updated = (case.get('phase', 0) + 1) & 0xFF
    if updated in (3, 0x0F):
        x = (case.get('x', 0x40) + 2 * signed8(case.get('delta', 0))) & 0xFFFF
        y = (case.get('y', 0x40) + (1 if updated == 3 else 0)) & 0xFFFF
        row = (y - 0x10) & 0xFFFF
        if row & 0x8000:
            row = 0
        offset = (0x4A40 + row * 0xD0 + (x >> 3)) & 0xFFFF
        device.planes[0][offset] = case.get('pixel', 0) & 0xFF

    if case.get('sound_vector') is not None:
        ip, cs = case['sound_vector']
        put16(memory, 0, 0x184, ip)
        put16(memory, 0, 0x186, cs)
    if case.get('pc_vector') is not None:
        ip, cs = case['pc_vector']
        put16(memory, 0, 0x180, ip)
        put16(memory, 0, 0x182, cs)

    if case.get('map_nibble') is not None:
        x = (case.get('x', 0x40) + 2 * signed8(case.get('delta', 0))) & 0xFFFF
        y = (case.get('y', 0x40) + (1 if updated == 3 else 0)) & 0xFFFF
        idx = state_map_offset(x, y)
        if case.get('stack_alias'):
            regs['sp'] = (idx + 2) & 0xFFFF
            put16(memory, ss, regs['sp'], case.get('outer_return', 0x7331))
        else:
            put8(memory, ss, idx, case['map_nibble'])
    if case.get('interaction_nibble') is not None:
        put8(memory, ss, interaction_map_offset(case.get('x', 0x40),
             case.get('y', 0x40)),
             case['interaction_nibble'])

    # Signed map nibble 1 reaches the shared 1FE8 -> interaction CALL. Give
    # that path its exact PC-service prerequisites and deterministic object data.
    put16(memory, ds, 0x17CB, case.get('object_word', 0))
    put8(memory, ds, 0x17CB + 0x1B, case.get('object_sound', 1))
    if case.get('provider') == 'sound-live-ds':
        alt = case['alternate_ds']
        seed_record(memory, alt, si, dict(case))
        put16(memory, alt, 0x002E, 0xC0DE)
        put8(memory, alt, 0x2010, 0xFF)
        put8(memory, alt, 0x25A7, 3)

    return memory, regs, device, pc_binding, sound_binding


class State800Access(interactions.Access):
    """Bounded providers for actual 13-row, pixel and INT61 stack words."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.initial_ds = regs['ds']
        self.entry_sp = regs['sp']
        self.saved_ds_address = physical(regs['ss'], (self.entry_sp - 6) & 0xFFFF)
        self.saved_si_address = physical(regs['ss'], (self.entry_sp - 4) & 0xFFFF)
        self.return_address = physical(regs['ss'], (self.entry_sp - 2) & 0xFFFF)
        self.return_armed = False
        self.mask_call_seen = False
        self.mask_saved_ds_pushed = False
        self.pending = []

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for segment, offset, value, label in pending:
            self.modify_word(segment, offset, value)
            self.used.add(label)

    def _provider(self, kind, address):
        super()._provider(kind, address)
        mode = self.case.get('provider')
        address &= MASK
        if (mode == 'mask-live-ds' and self.mask_saved_ds_pushed and kind == 'read' and
                address not in (self.saved_ds_address,
                                (self.saved_ds_address + 1) & MASK) and
                'mask-ds' not in self.used):
            if self.native:
                self.modify_word(self.regs['ss'], (self.entry_sp - 6) & 0xFFFF,
                                 self.case['alternate_ds'])
                self.used.add('mask-ds')
            else:
                self.pending.append((self.regs['ss'], (self.entry_sp - 6) & 0xFFFF,
                                     self.case['alternate_ds'], 'mask-ds'))
        if (mode in ('mask-return', 'pixel-return-f', 'pixel-return-three') and
                kind == 'read' and address == self.return_address and
                self.return_armed and 'return-target' not in self.used):
            self.modify_word(self.regs['ss'], (self.entry_sp - 2) & 0xFFFF,
                             self.case['changed_target'])
            self.used.add('return-target')
        if (mode in ('sound-return', 'sound-live-ds') and kind == 'write' and
                'sound-provider' not in self.used):
            driver = self.case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                if mode == 'sound-return':
                    self.modify_word(self.regs['ss'], (self.regs['sp'] - 6) & 0xFFFF,
                                     self.case.get('changed_target', 0x4567))
                else:
                    self.modify_word(self.regs['ss'], (self.regs['sp'] - 8) & 0xFFFF,
                                     self.case['alternate_ds'])
                self.used.add('sound-provider')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        result = super().access(kind, address, flags, mask, value)
        mode = self.case.get('provider')
        if (mode == 'mask-live-ds' and kind == 'write' and self.mask_call_seen and
                address == ((self.saved_ds_address + 1) & MASK) and
                (value & 0xFF) == (self.initial_ds >> 8) and
                self.memory[self.saved_ds_address] == (self.initial_ds & 0xFF)):
            self.mask_saved_ds_pushed = True
        if kind == 'write' and address == self.return_address:
            low = value & 0xFF
            if low == 0x63 and mode in ('mask-live-ds', 'mask-return'):
                self.mask_call_seen = True
            if mode == 'mask-return' and low == 0x63:
                self.return_armed = True
            if mode == 'pixel-return-f' and low == 0x93:
                self.return_armed = True
            if mode == 'pixel-return-three' and low == 0x2B:
                self.return_armed = True
        return result

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('state800 OUT event budget exhausted')
        if self.device is not None and port in (0x3C4, 0x3CE):
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


CALL_CONTRACTS = {
    0x2B60: ({MASK_RET}, 8),
    0x2B90: ({PIXEL_RET}, 7),
    0x2C28: ({PIXEL_RET}, 7),
    0x1FE8: (set(interactions.MAIN_RETS), 5),
}


def original(case, memory, regs, device):
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=INTEGRATED_INS,
        main_call_returns=CALL_CONTRACTS,
        stop_offsets={CONTINUATION: 0},
        access_factory=lambda c, m, r, d: State800Access(c, m, r, d),
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
    if provider == 'mask-live-ds':
        oracle_require('mask-ds' in oracle['used'] and
                       oracle['regs']['ds'] == case['alternate_ds'] and
                       (oracle['status'], oracle['continuation']) == (0, CONTINUATION),
                       case['name'] + ': live mask POP DS was not observed')
    if provider in ('mask-return', 'pixel-return-f', 'pixel-return-three'):
        expected_status = 8 if provider == 'mask-return' else 7
        oracle_require('return-target' in oracle['used'] and
                       (oracle['status'], oracle['continuation']) ==
                       (expected_status, case['changed_target']),
                       case['name'] + ': actual child RET was not checked')
    if provider == 'sound-return':
        oracle_require('sound-provider' in oracle['used'] and oracle['status'] == 4,
                       case['name'] + ': changed INT61 IRET target was not checked')
    if provider == 'sound-live-ds':
        oracle_require('sound-provider' in oracle['used'] and
                       oracle['regs']['ds'] == case['alternate_ds'] and
                       get8(oracle['memory'], case['alternate_ds'],
                            regs['si'] + 0x27) == ((-signed8(case['delta'])) & 0xFF),
                       case['name'] + ': returned DS did not receive NEG +27')
    if case.get('stack_alias'):
        x = (case['x'] + 2 * signed8(case.get('delta', 0))) & 0xFFFF
        y = (case['y'] + (1 if ((case['phase'] + 1) & 0xFF) == 3 else 0)) & 0xFFFF
        idx = state_map_offset(x, y)
        oracle_require(regs['sp'] == (idx + 2) & 0xFFFF and
                       any(event[0] == 'write' and
                           event[1] == physical(regs['ss'], idx) and
                           event[2] == ((x >> 2) & 0xFF)
                           for event in oracle['events']),
                       case['name'] + ': live PUSH AX/map alias not exercised')
    if case.get('name') == 'negative-nibble-one-interaction-pc':
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
        'c/entity_state800.c', 'c/entity_state800.h',
        'c/special_blit.h',
        'c/entity_mask_rows.c', 'c/entity_mask_rows.h',
        'c/entity_pixel.c', 'c/entity_pixel.h',
        'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/lemmings_sym.h',
        'tests/entity_state800.py', 'tests/entity_interactions.py',
        'tests/entity_mask.py', 'tests/entity_mask_rows.py',
        'tests/entity_pixel.py',
        'tests/entity_finish.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/pcspeaker_interrupt.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/resources.py', 'tools/unpack.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_preflight():
    before = input_hashes()
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 473 and
                    len(OWN_INS) == 157,
                    f'state800 identity changed: {sum(i.size for i in OWN_INS.values())} known bytes/'
                    f'{len(OWN_INS)} sites')
    oracle_require(len(OWN_EDGES) == 70,
                   f'state800 edge accounting changed: {len(OWN_EDGES)}')
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
        if provider == 'mask-return' or provider == 'pixel-return-f' or provider == 'pixel-return-three':
            expected = (8 if provider == 'mask-return' else 7, case['changed_target'])
        elif provider == 'sound-return':
            expected = (4, case['changed_target'])
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
                   'state800 source inputs changed during original-only preflight')
    print(f'PASS original state800 preflight: {len(specs)} fixtures, '
          f'{len(all_sites)} sites, {len(all_edges)} edges; no native code loaded',
          flush=True)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State800Access(case, memory, regs, device, native=True)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_fail(GUARD_EXIT, 'native state800 access cap exhausted')
                return self.access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, f'native state800 read callback failed: {error}')

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_fail(GUARD_EXIT, 'native state800 access cap exhausted')
                self.access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, f'native state800 write callback failed: {error}')

        def out(_context, port, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    worker_fail(GUARD_EXIT, 'native state800 access cap exhausted')
                self.access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, f'native state800 OUT callback failed: {error}')

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state800-m{mutation}.dll',
                     mutation, 'entity_state800')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state800_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state800_adapter
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
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 473 and
                    len(OWN_INS) == 157 and len(OWN_EDGES) == 70,
                    'state800 static byte/site/edge identity changed')
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
                   f'native state800 sites {len(all_sites)}/{len(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'native state800 edges {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')
    witnesses = {
        1: 'mask-selector-80',
        2: 'mask-selector-80',
        3: 'f-second-x-add-selects-collision-pixel',
        4: 'signed-negative-x-wrap-excluded',
        5: 'mask-live-return-changed',
        6: 'pixel-f-call-return-changed',
        7: 'nibble-nine-bound-service',
        8: 'nibble-nine-live-returned-ds-before-neg',
        9: 'map-eight-negative',
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
                   'state800 source inputs changed during native campaign')
    integrated = set().union(*(set(row['integrated_sites']) for row in rows))
    report = dict(image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
                  case_count=len(specs),
                  mutation_count=len(mutations), mutations=mutations,
                  executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  translated_code_bytes=473, instruction_sites=len(OWN_INS),
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
                  domain='2B35..2D0E state-0800 core and adapter; exact cadence; '
                         'all 130 signed thirteen-row mask selector values; two signed X '
                         'additions and bounds; actual mask/pixel CALL/RET; unchecked SS map, '
                         'nibble 7/8 direction and INT61 returned-DS path; shared finish tail; '
                         'full RAM/registers, '
                         'defined FLAGS, VGA state and ordered bus events.')
    write_json(REPORT, report)
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
                  case_count=len(specs), executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  input_hashes=before, c_coverage_claimed=False))
    print(f'PASS entity state800: {len(specs)} fixtures x core/adapter, '
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
    with temporary_build_directory(prefix='entity-state800-', parent=BUILD) as directory:
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
        raise SystemExit('usage: entity_state800.py [--worker DIR | --original-only]')
