"""Bounded original-versus-C checks for the state-0002 interaction parent."""
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
import entity_finish as finish
import entity_interactions as interactions
import entity_mask as mask_tests
import entity_pattern as pattern_tests
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, END, UNKNOWN = 0x2350, 0x23BF, 0x2382
PATTERN_ENTRY, PATTERN_RET = 0x283B, 0x287C
MASK_ENTRY, MASK_RET = 0x5DF8, 0x5EB9
CONTINUATION = 0x1FEB
BUFFER_SEGMENT = mask_tests.BUFFER_SEGMENT
MAX_INSTRUCTIONS, MAX_EVENTS = 2400, 8192
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
ALL_FLAGS = interactions.FLAGS
REPORT = BUILD / 'entity-state2-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, END)
OWN_INS.pop(UNKNOWN, None)
PATTERN_INS = decoded_span(PATTERN_ENTRY, PATTERN_RET + 1)
MASK_INS = decoded_span(MASK_ENTRY, MASK_RET + 1)
FINISH_INS = finish.FINISH_INS
INTEGRATED_INS = dict(OWN_INS)
INTEGRATED_INS.update(PATTERN_INS)
INTEGRATED_INS.update(MASK_INS)
INTEGRATED_INS.update(FINISH_INS)
INTEGRATED_INS.update(interactions.MAIN_INS)

OWN_BRANCHES = {
    address: ins for address, ins in OWN_INS.items()
    if ins.group(capstone.CS_GRP_JUMP)
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


class Mismatch(AssertionError):
    """A completed native comparison differs from the pinned original."""


class OracleFailure(AssertionError):
    """The bounded original or callback contract did not complete."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def map_offset(x, y):
    qx = (x & 0xFFFF) >> 2
    qy = (((y - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12) & 0xFFFF


def pattern_offset(x, y):
    qx = ((x - 4) & 0xFFFF) >> 2
    qy = (((y - 6 - 0x10) & 0xFFFF) >> 2)
    return (qx + qy * 0x1A0 + 0x12) & 0xFFFF


def own_edges(instructions):
    out = set()
    for address, ins in instructions.items():
        if not ins.group(capstone.CS_GRP_JUMP):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            out.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            out.add((address, ins.operands[-1].imm & 0xFFFF))
    return out


STATIC_EDGES = own_edges(OWN_INS)


def cases():
    """Focused threshold, dispatch, child, alias, VGA and provider witnesses."""
    rows = [
        dict(name='cadence-ordinary-nonzero', cadence=0x10),
        dict(name='cadence-byte-wrap-to-zero', cadence=0xFF),
        dict(name='threshold-33-normal', cadence=0x32),
        dict(name='threshold-34-mark-inactive', cadence=0x33),
        dict(name='threshold-33-mutant-witness', cadence=0x32),
        dict(name='sound-disabled', cadence=0, enabled=0xFF),
        dict(name='sound-options-clear', cadence=0, enabled=0, options=0),
        dict(name='sound-pc-command-030c', cadence=0, enabled=0,
             options=1, record_bits=0),
        dict(name='pc-return-live-ds-si', cadence=0, enabled=0,
             options=1, record_bits=0x0100, provider='pc-registers',
             provider_ds=0x6200, provider_si=0x7070, provider_cx=0x3131,
             provider_enabled=0xFF, provider_options=3,
             provider_record_bits=0, provider_x=0x0125, provider_y=30,
             vga=True, seed=0x520E),
        dict(name='pc-unbound-binding', cadence=0, enabled=0,
             options=1, record_bits=0, pc_binding=False),
        dict(name='pc-unbound-vector', cadence=0, enabled=0,
             options=1, record_bits=0, pc_vector=(0x0182, 0x6200)),
        dict(name='pc-untranslated-child', cadence=0, enabled=0,
             options=1, record_bits=0, pc_table_target=0x01B3),
        dict(name='pc-changed-child-return', cadence=0, enabled=0,
             options=1, record_bits=0, provider='pc-child-return'),
        dict(name='pc-changed-iret-return', cadence=0, enabled=0,
             options=1, record_bits=0, provider='pc-interrupt-return'),
        dict(name='pattern-gate-clear', cadence=0, record_bits=0,
             nibble=9),
        dict(name='pattern-bit-0100', cadence=0, record_bits=0x0100,
             nibble=9, vga=True, seed=0x5201),
        dict(name='pattern-other-bit-0200', cadence=0, record_bits=0x0200,
             nibble=9),
        dict(name='pattern-bit-one-mutant-witness', cadence=0,
             record_bits=0x0001, nibble=9, vga=True, seed=0x520B),
        dict(name='pattern-return-overwrite', cadence=0,
             record_bits=0x0100, x=4, y=22, sp=0x0014, nibble=9,
             pattern=bytes((0x01, 0x02, 0x03, 4, 5, 6, 7, 8, 9))),
        dict(name='pattern-df-set', cadence=0, record_bits=0x0100,
             nibble=9, df=True, vga=True, seed=0x520C),
        dict(name='pattern-ds-ss-shared', cadence=0,
             record_bits=0x0100, nibble=9, ds=0x3000, ss=0x3000,
             si=0x4000, sp=0x8A00, vga=True, seed=0x520D),
        dict(name='map-nibble-nine-skip', cadence=0, nibble=9),
        dict(name='map-nibble-five-skip', cadence=0, nibble=5,
             vga=True, seed=0x5202),
        dict(name='map-nibble-other-draw', cadence=0, nibble=1,
             vga=True, independent=True, seed=0x5203),
        dict(name='mask-early-clip-y8', cadence=0, x=0x0125, y=8,
             nibble=1, vga=True, seed=0x5204),
        dict(name='mask-clip-boundary-y9', cadence=0, x=0x0125, y=9,
             nibble=1, vga=True, seed=0x5205),
        dict(name='mask-full-draw-independent', cadence=0,
             x=0x0125, y=30, nibble=1, vga=True, independent=True,
             seed=0x5206),
        dict(name='mask-full-draw-df-set', cadence=0,
             x=0x0126, y=29, nibble=1, vga=True, df=True, seed=0x5207),
        dict(name='mask-live-return-overwrite', cadence=0, x=0x0125,
             y=30, nibble=1, vga=True, provider='mask-ret',
             provider_return=0x4567, seed=0x5208),
        dict(name='map-ss-not-ds-mutant-witness', cadence=0, x=4, y=22,
             nibble=1, ds_nibble=9, ds=0x4100, ss=0x5100,
             vga=True, seed=0x5209),
        dict(name='live-saved-dx-provider', cadence=0, x=4, y=22,
             nibble=9, dx=0xBEEF, provider='saved-dx'),
        dict(name='pattern-return-provider-rewrites-record-and-map',
             cadence=0, record_bits=0x0100, x=0x0125, y=22,
             nibble=9, provider='pattern-ret-record', provider_x=0x0128,
             provider_nibble=1, vga=True, seed=0x520A),
        dict(name='record-offset-word-wrap', cadence=0,
             record_bits=0, ds=0xFFFF, si=0xFFF0, nibble=9),
        dict(name='stack-offset-and-physical-wrap', cadence=0,
             record_bits=0, ds=0xFFFF, si=0xFFF0,
             ss=0xFFFF, sp=0x0001, nibble=9),
        dict(name='stack-map-record-alias', cadence=0, x=0x0125,
             y=30, record_bits=0, ds=0x5000, ss=0x5000,
             si=0x4FC0, sp=0x5000, nibble=9),
    ]
    oracle_require(28 <= len(rows) <= 40,
                   f'Entity state2 fixture count changed: {len(rows)}')
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'Entity state2 fixture names are not unique')
    return rows


def prepare(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('ds', interactions.MAIN_SEG + 0x09A9)
    template.setdefault('ss', 0x5200)
    template.setdefault('si', 0x5000)
    template.setdefault('sp', 0xD000)
    template.setdefault('record_bits', 0)
    template.setdefault('x', 0x0125)
    template.setdefault('y', 30)
    template.setdefault('cadence', 0x10)
    template.setdefault('enabled', 0)
    template.setdefault('options', 0)
    template.setdefault('seed', 0x5200 + len(case['name']))
    interaction_template = dict(template)
    interaction_template.pop('vga', None)
    memory, regs, _device, pc_binding, sound_binding, _ = interactions.setup(
        interaction_template)
    regs.update(cs=template['load'], ip=ENTRY, ds=template['ds'],
                ss=template['ss'], si=template['si'], sp=template['sp'])
    if template.get('df'):
        regs['flags'] |= 0x0400
    else:
        regs['flags'] &= ~0x0400
    ds, ss, si = regs['ds'], regs['ss'], regs['si']
    put16(memory, ds, si, template['x'])
    put16(memory, ds, si + 2, template['y'])
    put16(memory, ds, si + 8, template['record_bits'])
    put8(memory, ds, si + 0x28, template['cadence'])

    pattern = bytes(template.get('pattern',
        bytes((0x31 + (index * 29 + template['seed']) % 0xC0)
              for index in range(9))))
    oracle_require(len(pattern) == 9,
                   case['name'] + ': pattern source must be nine bytes')
    for index, value in enumerate(pattern):
        put8(memory, ds, si + 0x16 + index, value)
    if template.get('provider') == 'pc-registers':
        pds, psi = template['provider_ds'], template['provider_si']
        put16(memory, pds, psi, template.get('provider_x', 0x0125))
        put16(memory, pds, psi + 2, template.get('provider_y', 30))
        put16(memory, pds, psi + 8, template.get('provider_record_bits', 0))
        for index, value in enumerate(pattern):
            put8(memory, pds, psi + 0x16 + index, value ^ 0x5A)

    if case.get('poison'):
        raise OracleFailure('poisoned setup is not part of the state2 fixture contract')
    buffer_segment = template.get('buffer_segment', BUFFER_SEGMENT)
    put16(memory, ds, 0x1FE8, buffer_segment)
    if case.get('vga'):
        device = mask_tests.configure_device(template, template['seed'])
    else:
        device = None
    # The mask child consumes one 8-shift generated 22-row bank. Its bytes are
    # generated independently by the leaf fixture's documented 24-bit shift.
    source_words = mask_tests.fill_generated_banks(
        memory, (buffer_segment,), template['seed'])

    nibble = template.get('nibble', 9)
    index = map_offset(template['x'], template['y'])
    put8(memory, ss, index, nibble)
    if template.get('ds_nibble') is not None:
        put8(memory, ds, index, template['ds_nibble'])
    if device is not None and ss == 0xA000:
        device.gc[4] = 0
        for plane in device.planes:
            plane[index] = nibble & 0xFF
    if device is not None and ds == 0xA000:
        device.gc[4] = 0
        for plane in device.planes:
            plane[index] = (template.get('ds_nibble', nibble) & 0xFF)

    if case.get('provider') == 'pattern-ret-record':
        future_index = map_offset(template['provider_x'], template['y'])
        put8(memory, ss, future_index, template['provider_nibble'])
        if device is not None and ss == 0xA000:
            for plane in device.planes:
                plane[future_index] = template['provider_nibble']

    # A VGA-backed SS source must have a well-defined read-map value. Preserve
    # all four planes for the parent stack slots when SS is the aperture.
    if device is not None and ss == 0xA000:
        device.gc[4] = 0
        for plane in device.planes:
            for offset in range(0xD000, 0xD020):
                plane[offset] = get16(memory, ss, offset) & 0xFF

    return memory, regs, device, pc_binding, sound_binding, source_words, pattern


class State2Access(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []
        self.out_count = 0

    def _provider(self, kind, address):
        super()._provider(kind, address)
        case = self.case
        effect = case.get('provider')
        ss, sp = self.regs['ss'], self.regs['sp']
        if (effect == 'saved-dx' and kind == 'write' and 'saved-dx' not in self.used and
                address == physical(ss, sp - 3)):
            self.used.add('saved-dx')
            if self.native:
                # This is the high-byte bus callback of PUSH DX. Changing its
                # low byte now survives the subsequent high-byte store.
                self.store(physical(ss, sp - 4), 0x13)
            else:
                # Unicorn reports the full PUSH before committing either byte;
                # flush after that instruction to preserve the live provider.
                self.pending.append(('saved-dx', ss, (sp - 4) & 0xFFFF, 0x13))
        if (effect == 'pattern-ret-record' and kind == 'read' and
                'pattern-ret-record' not in self.used and
                address == physical(ss, sp - 2)):
            self.modify_word(self.regs['ds'], (self.regs['si'] + 0) & 0xFFFF,
                             case['provider_x'])
            table = map_offset(case['provider_x'], case['y'])
            self.store(physical(ss, table), case['provider_nibble'])
            if self.device is not None and VGA_BASE <= physical(ss, table) < VGA_END:
                offset = physical(ss, table) - VGA_BASE
                for plane in self.device.planes:
                    plane[offset] = case['provider_nibble'] & 0xFF
            self.used.add('pattern-ret-record')
        if (effect == 'mask-ret' and kind == 'write' and
                'mask-ret' not in self.used and VGA_BASE <= address < VGA_END):
            self.modify_word(ss, sp - 2, case.get('provider_return', 0x4567))
            self.used.add('mask-ret')

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for name, segment, offset, value in pending:
            if name == 'saved-dx':
                self.store(physical(segment, offset), value)

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-state2 callback event budget exhausted')
        if self.device is None:
            raise OracleFailure(f'entity-state2 unexpected OUT {port:04X} without VGA')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        self.out_count += 1


def ret_contracts():
    result = {PATTERN_RET: (0x2386, 5), MASK_RET: (0x23BC, 6)}
    for address, ins in FINISH_INS.items():
        if ins.mnemonic.lower() == 'ret':
            result[address] = (CONTINUATION, 7)
    for address, ins in interactions.MAIN_INS.items():
        if ins.mnemonic.lower() == 'ret':
            result[address] = (CONTINUATION, 7)
    return result


RET_CONTRACTS = ret_contracts()


def original(case, memory, regs, device):
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=ALL_FLAGS,
        main_instructions=INTEGRATED_INS,
        main_ret_continuations=RET_CONTRACTS,
        stop_offsets={CONTINUATION: 0},
        access_factory=State2Access,
        instruction_limit=MAX_INSTRUCTIONS)


def independent_checks(case, initial, regs, device, source_words, pattern, oracle):
    label = case['name']
    if case.get('pattern', True) is not None and case.get('record_bits', 0) & 0x0100:
        if (not case.get('provider') and
                not case.get('df') and regs['ss'] != regs['ds'] and
                regs['sp'] > 0x100 and case.get('name') != 'pattern-return-overwrite'):
            dest = pattern_offset(case.get('x', 0x0125), case.get('y', 30))
            expected = []
            for row in range(3):
                expected.extend((dest + row * 0x1A0 + 0,
                                 dest + row * 0x1A0 + 1,
                                 dest + row * 0x1A0 + 2))
            actual = bytes(oracle['memory'][physical(regs['ss'], offset)]
                           for offset in expected)
            oracle_require(actual == pattern,
                           label + ': independent 283B three-row copy differs')
    if case.get('independent') and device is not None:
        # This assertion is used only on pattern-disabled, unclipped mask
        # cases, so its coordinates and generated bank are the direct inputs.
        oracle_require(not (case.get('record_bits', 0) & 0x0100),
                       label + ': independent VGA case unexpectedly copies pattern')
        oracle_require((case.get('nibble', 9) & 0x0F) not in (5, 9),
                       label + ': independent mask fixture is on a skip branch')
        checked = mask_tests.independent_plane_check(
            dict(case, buffer_segment=case.get('buffer_segment', BUFFER_SEGMENT)),
            source_words, device, oracle['device'], oracle['memory'], regs)
        oracle_require(checked, label + ': independent full-plane check was skipped')
    if case.get('provider'):
        key = ('pc' if case['provider'] in
               ('pc-registers', 'pc-child-return', 'pc-interrupt-return')
               else case['provider'])
        oracle_require(key in oracle['used'], label + ': live provider did not fire')
    if case.get('provider') == 'pattern-ret-record':
        oracle_require(get16(oracle['memory'], regs['ds'], regs['si']) ==
                       case['provider_x'], label + ': RET provider did not replace X')
        oracle_require(oracle['status'] == 0,
                       label + ': provider case did not complete the mask/skip path')
    if case.get('provider') == 'mask-ret':
        oracle_require(oracle['status'] == 6 and
                       oracle['continuation'] == case.get('provider_return', 0x4567),
                       label + ': mask RET did not expose the live changed target')
    if case['name'] == 'pattern-return-overwrite':
        oracle_require(oracle['status'] == 5 and oracle['continuation'] == 0x0201,
                       label + ': pattern RET did not expose overwritten return word')


def expected_path(case, oracle):
    """Assert each fixture reached its declared parent/child branch path."""
    sites = oracle['sites']
    own = {address for source, address in sites
           if source == 'main' and address in OWN_INS}
    cadence = case.get('cadence', 0x10) & 0xFF
    incremented = (cadence + 1) & 0xFF
    marked = incremented == 0x34
    active = cadence == 0 and not marked

    attempt_pc = (active and case.get('enabled', 0) != 0xFF and
                  (case.get('options', 0) & 1) != 0)
    vector = case.get('pc_vector', (interactions.PC_ENTRY, interactions.PC_SEG))
    binding_ok = (case.get('pc_binding', True) is not False and
                  vector == (interactions.PC_ENTRY, interactions.PC_SEG) and
                  case.get('pc_binding_segment', interactions.PC_SEG) == interactions.PC_SEG)
    pc_entry = attempt_pc and binding_ok
    pc_stops = attempt_pc and (
        not binding_ok or 'pc_table_target' in case or
        case.get('provider') in ('pc-child-return', 'pc-interrupt-return'))
    if attempt_pc:
        oracle_require(0x2377 in own,
                       case['name'] + ': planned INT60 producer site was not executed')
    oracle_require((('pc', interactions.PC_ENTRY) in sites) == pc_entry,
                   case['name'] + ': PC dispatcher entry differs from planned binding path')
    if marked:
        oracle_require(0x235C in own and ('main', 0x20E2) in sites and
                       oracle['continuation'] == CONTINUATION,
                       case['name'] + ': threshold did not dispatch through 20E2')
    elif not active:
        oracle_require(oracle['continuation'] == CONTINUATION,
                       case['name'] + ': nonzero residual count did not reach 1FEB')

    if case.get('provider') == 'pc-registers':
        final_bits = case.get('provider_record_bits', 0)
    else:
        final_bits = case.get('record_bits', 0)
    pattern_expected = active and not pc_stops and bool(final_bits & 0x0100)
    oracle_require((('main', PATTERN_ENTRY) in sites) == pattern_expected,
                   case['name'] + ': 283B child entry differs from planned record bit')
    oracle_require((0x2383 in own) == pattern_expected,
                   case['name'] + ': optional 283B CALL site differs from plan')

    can_reach_map = active and not pc_stops and not (
        pattern_expected and oracle['status'] == 5)
    if can_reach_map:
        ds, si = oracle['regs']['ds'], oracle['regs']['si']
        x = get16(oracle['memory'], ds, si)
        y = get16(oracle['memory'], ds, si + 2)
        cell = map_offset(x, y)
        address = physical(oracle['regs']['ss'], cell)
        reads = [event for event in oracle['events']
                 if event[0] == 'read' and event[1] == address]
        oracle_require(bool(reads), case['name'] + ': no planned SS map-byte read')
        nibble = reads[-1][2] & 0x0F
        mask_expected = nibble not in (5, 9)
        oracle_require((('main', MASK_ENTRY) in sites) == mask_expected,
                       case['name'] + ': 5DF8 child entry differs from live SS nibble')
        oracle_require((0x23B9 in own) == mask_expected,
                       case['name'] + ': optional 5DF8 CALL site differs from map byte')
    else:
        oracle_require(('main', MASK_ENTRY) not in sites,
                       case['name'] + ': mask child ran after a declared early seam')


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual.state() == expected.state(), label + ': VGA planes/latches/registers differ')
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


def native_access(case, memory, regs, device):
    access = State2Access(case, memory, regs, device, native=True)

    def read(_context, _ram, address, flags):
        try:
            if len(access.events) >= MAX_EVENTS:
                os._exit(GUARD_EXIT)
            return access.access('read', address, flags, ALL_FLAGS)
        except BaseException as error:
            try:
                os.write(2, (f'entity-state2 read callback: {error}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

    def write(_context, _ram, address, value, flags):
        try:
            if len(access.events) >= MAX_EVENTS:
                os._exit(GUARD_EXIT)
            access.access('write', address, flags, ALL_FLAGS, value)
        except BaseException as error:
            try:
                os.write(2, (f'entity-state2 write callback: {error}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

    def out(_context, port, value, flags):
        try:
            if len(access.events) >= MAX_EVENTS:
                os._exit(GUARD_EXIT)
            access.out_word(port, value, flags, ALL_FLAGS)
        except BaseException as error:
            try:
                os.write(2, (f'entity-state2 OUT callback: {error}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

    callbacks = (interactions.READ(read), interactions.WRITE(write),
                 interactions.OUT(out))
    bus = interactions.Bus(None, *callbacks)
    return access, bus, callbacks


class Native:
    def __init__(self, directory, mutation=0):
        path = Path(directory) / f'entity-state2-m{mutation}.dll'
        if not path.is_file():
            path = build(path, mutation, 'entity_state2')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state2_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state2_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, *, core, null_bus=False):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        access, bus, callbacks = native_access(case, memory, initial_regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        pc_ptr = ct.byref(pc_binding) if pc_binding is not None else None
        bus_ptr = None if null_bus else ct.byref(bus)
        state = dict(initial_regs)
        live = interactions.Regs(**initial_regs)
        if core:
            call = Call(*(initial_regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds',
                'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), pc_ptr, bus_ptr)
            state.update(ax=result.value, bx=result.map_cursor,
                         cx=result.count, dx=result.auxiliary_value,
                         si=result.record_cursor, di=result.object_cursor,
                         bp=result.candidate_y, cs=result.code_segment,
                         ds=result.data_segment, es=result.extra_segment,
                         ss=result.stack_segment, sp=result.stack_offset,
                         flags=result.flags, ip=result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(live), pc_ptr, bus_ptr)
            state = {name: getattr(live, name) for name in interactions.REG_NAMES}
        # Keep all CFUNCTYPE closures alive until the native call has returned.
        assert callbacks
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=access.events, used=access.used,
                    status=status, continuation=state['ip'])


def compare_case(native, case, *, core, null_bus=False):
    initial, regs, device, pc_binding, _sound_binding, words, pattern = prepare(case)
    original_result = original(case, bytearray(initial), dict(regs),
                               copy.deepcopy(device))
    independent_checks(case, initial, regs, device, words, pattern, original_result)
    expected_path(case, original_result)
    actual = native.run(case, initial, regs, device, pc_binding,
                        core=core, null_bus=null_bus)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == original_result['status'],
            f'{label}: status {actual["status"]}/{original_result["status"]}')
    require(actual['continuation'] == original_result['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{original_result["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            defined = original_result['flag_mask']
            require(((actual['regs'][name] ^ original_result['regs'][name]) & defined) == 0,
                    f'{label}: FLAGS {actual["regs"][name]:04X}/'
                    f'{original_result["regs"][name]:04X} under {defined:04X}')
        else:
            require(actual['regs'][name] == original_result['regs'][name],
                    f'{label}: {name} {actual["regs"][name]:04X}/'
                    f'{original_result["regs"][name]:04X}')
    require(actual['memory'] == original_result['memory'],
            label + ': full 1 MiB RAM differs')
    if not null_bus:
        compare_events(label, actual['events'], original_result['events'])
    if device is not None:
        compare_device(label, actual['device'], original_result['device'])
    require(actual['used'] == original_result['used'],
            f'{label}: provider effects {actual["used"]}/{original_result["used"]}')
    return dict(name=case['name'], core=core, status=original_result['status'],
                continuation=original_result['continuation'],
                sites=sorted(address for source, address in original_result['sites']
                             if source == 'main' and address in OWN_INS),
                edges=sorted((source_ip, target)
                             for source, source_ip, target in original_result['edges']
                             if source == 'main' and source_ip in OWN_INS),
                event_count=len(original_result['events']),
                steps=original_result['steps'], provider=case.get('provider'),
                vga=bool(device), null_bus=null_bus)


def original_only():
    specs = cases()
    covered, edges = set(), set()
    rows = []
    for case in specs:
        initial, regs, device, _pc, _sb, words, pattern = prepare(case)
        observed = original(case, bytearray(initial), dict(regs), copy.deepcopy(device))
        independent_checks(case, initial, regs, device, words, pattern, observed)
        expected_path(case, observed)
        own_sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
        own_branch_edges = {(source, source_ip, target)
                            for source, source_ip, target in observed['edges']
                            if source == 'main' and source_ip in OWN_INS}
        covered.update(own_sites)
        edges.update((source_ip, target) for _source, source_ip, target in own_branch_edges)
        rows.append(dict(name=case['name'], sites=sorted(own_sites),
                         edges=[list(item) for item in sorted(
                             (source_ip, target) for _source, source_ip, target
                             in own_branch_edges)],
                         status=observed['status'], continuation=observed['continuation'],
                         events=len(observed['events']), provider=case.get('provider')))
    oracle_require(len(OWN_INS) == 45 and
                   sum(ins.size for ins in OWN_INS.values()) == 110,
                   'state2 static identity changed (expected 110 bytes / 45 sites)')
    oracle_require(UNKNOWN not in OWN_INS,
                   'UNKNOWN byte 2382 entered the translated/original instruction map')
    oracle_require(covered == set(OWN_INS),
                   f'state2 original site union differs: missing={sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == STATIC_EDGES,
                   f'state2 original branch-edge union differs: expected={sorted(STATIC_EDGES)} '
                   f'got={sorted(edges)}')
    print(f'PASS entity state2 original: {len(specs)} cases, {len(covered)} sites, '
          f'{len(edges)} owned edges; bounded original only')
    return rows, edges


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/entity-simulation.md', 'assets/vgalemmi.exe',
        'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json',
        'src/game_code.asm', 'src/entity_graphics.asm',
        'c/entity_state2.c', 'c/entity_state2.h',
        'c/entity_pattern.c', 'c/entity_pattern.h', 'c/entity_mask.c', 'c/entity_mask.h',
        'c/entity_finish.c', 'c/entity_finish.h', 'c/entity_interactions.c',
        'c/entity_interactions.h', 'c/pcspeaker_interrupt.c',
        'c/pcspeaker_interrupt.h', 'c/pcspeaker_dispatch.c',
        'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h', 'c/sound_latches.c',
        'c/sound_latches.h', 'c/sound_latches_sym.h', 'c/pcspeaker_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/entity_state2.py', 'tests/entity_interactions.py',
        'tests/entity_finish.py', 'tests/entity_pattern.py',
        'tests/entity_pattern_bus.py', 'tests/entity_mask.py', 'tests/minimap_vga.py',
        'tests/pcspeaker_dispatch.py', 'tests/pcspeaker_interrupt.py',
        'tests/sound_latches.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/unpack.py',
        'tools/resources.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory, before_path):
    with open(before_path, 'r', encoding='utf-8') as stream:
        before = json.load(stream)
    oracle_require(before == input_hashes(),
                   'state2 inputs changed between build and bounded worker')
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(OWN_INS) == 45 and
                   sum(ins.size for ins in OWN_INS.values()) == 110,
                   'state2 static byte/site accounting changed')
    specs = cases()
    baseline = Native(directory)
    rows, coverage, edges, total_events = [], set(), set(), 0
    by_name = {case['name']: case for case in specs}
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            coverage.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
            rows.append(row)
        gc.collect()

    oracle_require(coverage == set(OWN_INS),
                   f'state2 native case union differs: missing={sorted(set(OWN_INS)-coverage)}')
    oracle_require(edges == STATIC_EDGES,
                   f'state2 owned branch-edge coverage differs: {sorted(edges)}')

    witnesses = (
        (1, 'threshold-33-mutant-witness'),
        (2, 'map-nibble-five-skip'),
        (3, 'pattern-return-overwrite'),
        (4, 'live-saved-dx-provider'),
        (5, 'pattern-bit-one-mutant-witness'),
        (6, 'pc-return-live-ds-si'),
        (7, 'map-ss-not-ds-mutant-witness'),
        (8, 'map-nibble-other-draw'),
    )
    mutations = []
    for mutation_id, case_name in witnesses:
        mutant = Native(directory, mutation_id)
        case = by_name[case_name]
        try:
            compare_case(mutant, case, core=True)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation_id, case=case_name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'state2 mutation {mutation_id} survived {case_name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'state2 inputs changed during bounded campaign')
    oracle_require(len(mutations) == 8,
                   'state2 completed-mutant count changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        asset_sha256=sha(ASSET.read_bytes()), case_count=len(specs),
        boundary_call_count=2 * len(specs), mutation_count=len(mutations),
        mutations=mutations, cases=rows, translated_code_bytes=110,
        native_code_ranges=[[ENTRY, UNKNOWN], [UNKNOWN + 1, END]],
        executed_instruction_addresses=sorted(coverage),
        instruction_site_count=len(coverage), branch_edges=sorted(edges),
        branch_instruction_addresses=sorted(OWN_BRANCHES),
        total_bus_events=total_events,
        domains=[
            '2350..23BE state0002; 110 known bytes / 45 sites; UNKNOWN 2382 excluded',
            'threshold INC/CMP/DEC and 20E2 mark-inactive finish path',
            'optional INT60 AX=030C, live PC returned registers and unbound/untranslated/changed seams',
            'optional 283B pattern copy and 5DF8 mask draw; actual live child RET targets',
            'SS cell-map nibble 9/5 skips and other-nibble mask dispatch',
            'bounded VGA word OUT, planar writes, clipping and independent mask-plane expectations',
            'live DS/SS aliases, provider rewrites of DX, X and future SS table reads',
            'full 1 MiB RAM, complete adapter registers, defined FLAGS and ordered bus accesses',
            '16-bit stack/record wrap and 20-bit physical memory wrap'],
        limits=dict(worker_seconds=WORKER_SECONDS,
                    windows_process_mib=PROCESS_MIB,
                    windows_process_tree_mib=TREE_MIB,
                    original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=after))
    print(f'PASS entity state2 C: {len(specs)} fixtures, {total_events} bus events, '
          f'{len(coverage)} sites, {len(edges)} edges, {len(mutations)} completed mutants',
          flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        original_only()
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-state2 arguments')
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state2-', parent=BUILD) as directory:
        before_path = Path(directory) / 'input-hashes.json'
        before = input_hashes()
        write_json(before_path, before)
        for mutation in range(9):
            build(Path(directory) / f'entity-state2-m{mutation}.dll',
                  mutation, 'entity_state2')
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory), str(before_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB)


if __name__ == '__main__':
    main()
