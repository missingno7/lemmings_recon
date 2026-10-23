"""Bounded differential harness for the 1F19 entity-update caller."""
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
import entity_cadence as cadence
import entity_countdown as countdown
import entity_interactions as interactions
import entity_late_states as late_states
import entity_state2 as state2
import entity_state4 as state4
import entity_state8 as state8
import entity_state10 as state10
import entity_state20 as state20
import entity_state40 as state40
import entity_state80 as state80
import entity_state100 as state100
import entity_state200 as state200
import entity_state400 as state400
import entity_state800 as state800
import entity_vga as vga_tests
import entity_zero_state as zero_state
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
LOAD, ENTRY = interactions.MAIN_SEG, 0x1F19
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
RECORD = 0x0088
RETURNS = {0x2004, 0x203B, 0x2046}
INFEASIBLE_EDGE = (0x1FE3, 0x1FE8)
EVENT_LIMIT, INSTRUCTION_LIMIT = 8192, 20000
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-update-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_spans(spans):
    result = {}
    for start, end in spans:
        for ins in MD.disasm(IMAGE[start:end], start):
            if ins.address in result:
                raise RuntimeError(f'duplicate instruction at {ins.address:04X}')
            result[ins.address] = ins
    return result


OWN_SPANS = ((0x1F19, 0x1FE8), (0x1FEB, 0x2047))
OWN_INS = decoded_spans(OWN_SPANS)


def integrated_instructions():
    groups = [
        OWN_INS,
        decoded_spans(((0x1FE8, 0x1FEB),)),
        interactions.MAIN_INS,
        countdown.INS,
        vga_tests.INSTRUCTIONS['readback'],
        cadence.OWN_INS, cadence.SHARED_INS, cadence.PIXEL_INS,
        zero_state.INTEGRATED_INS,
        state2.INTEGRATED_INS, state4.INTEGRATED_INS, state8.INTEGRATED_INS,
        state10.INTEGRATED_INS, state20.INTEGRATED_INS,
        state40.INTEGRATED_INS, state80.INTEGRATED_INS,
        state100.INTEGRATED_INS, state200.INTEGRATED_INS,
        state400.INTEGRATED_INS, state800.INTEGRATED_INS,
        late_states.INTEGRATED_INS,
    ]
    result = {}
    for group in groups:
        for address, ins in group.items():
            prior = result.get(address)
            if prior is not None and (prior.bytes != ins.bytes or
                                      prior.size != ins.size):
                raise RuntimeError(f'instruction-map conflict at {address:04X}')
            result[address] = ins
    return result


INTEGRATED_INS = integrated_instructions()


def branch_edges(instructions):
    result = set()
    for address, ins in instructions.items():
        if not ins.group(capstone.CS_GRP_JUMP):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            result.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            result.add((address, ins.operands[-1].imm & 0xFFFF))
    return result


OWN_EDGES = branch_edges(OWN_INS)
EXPECTED_OWN_SITES = 108
EXPECTED_OWN_BYTES = 299
EXPECTED_OWN_EDGES = 82


def merge_contracts():
    call_returns, ret_continuations = {}, {}

    def add_call(address, contract, owner):
        allowed, changed = contract
        value = (set(allowed), changed)
        old = call_returns.get(address)
        if old is not None and old != value:
            raise RuntimeError(f'call-contract conflict at {address:04X}: '
                               f'{owner} {value!r} vs {old!r}')
        call_returns[address] = value

    def add_ret(address, contract, owner):
        value = tuple(contract)
        old = ret_continuations.get(address)
        if old is not None and old != value:
            raise RuntimeError(f'return-contract conflict at {address:04X}: '
                               f'{owner} {value!r} vs {old!r}')
        ret_continuations[address] = value

    modules = (state2, state4, state8, state10, state20, state40, state80,
               state100, state200, state400, state800, late_states, zero_state)
    for module in modules:
        for name in ('CALL_RETURNS', 'CALL_CONTRACTS'):
            for address, contract in getattr(module, name, {}).items():
                add_call(address, contract, module.__name__ + '.' + name)
        for address, contract in getattr(module, 'RET_CONTRACTS', {}).items():
            add_ret(address, contract, module.__name__ + '.RET_CONTRACTS')

    # The outer caller's two real CALL frames are part of this parent scope.
    add_call(0x1F23, ({vga_tests.READBACK_RET}, 2), 'entity-update readback')
    add_call(0x1F4C, (set(countdown.RETURNS), 2), 'entity-update countdown')

    # Keep the original instruction oracle running through every child RET.
    # The composed C parent calls these maintained cores directly, while the
    # original executes their actual RET instruction and consumes the live
    # CALL word. The first ret address is the leaf's known normal RET site.
    leaf_rets = {
        0x2EC0: (set(interactions.MAIN_RETS), 5),
        0x5DC6: ({0x5DF7}, 2),
        0x6141: ({0x616F}, 2),
        0x283B: ({0x287C}, 2),
        0x5DF8: ({0x5EB9}, 2),
        0x5EBA: ({0x5F0E}, 2),
        0x5F0F: ({0x5FAB}, 2),
        0x5FAC: ({0x606A}, 2),
        0x606B: ({0x6140}, 2),
    }
    for address, ins in INTEGRATED_INS.items():
        if ins.mnemonic.lower() != 'call':
            continue
        target = ins.operands[-1].imm & 0xFFFF
        if address not in call_returns:
            if target not in leaf_rets:
                raise RuntimeError(f'uncontracted parent CALL {address:04X}->{target:04X}')
            add_call(address, leaf_rets[target], 'entity-update composed leaf')
    return call_returns, ret_continuations


MAIN_CALL_RETURNS, MAIN_RET_CONTINUATIONS = merge_contracts()


class OracleFailure(AssertionError):
    """The bounded original/provider failed to complete its declared path."""


class Mismatch(AssertionError):
    """A completed native result differs from completed original execution."""


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


def cases():
    """Cover all dispatches, outer seams, scan outcomes and live providers."""
    rows = [
        dict(name='gate-ff-bypasses-scan', gate=0xFF, scan_request=0xFF),
        dict(name='zero-bound-bypasses-scan', bound=0, scan_request=0xFF),
        dict(name='inactive-only-tail', inactive=0xFF),
        dict(name='zero-state-dispatch', state_bits=0),
        dict(name='state-priority-2-before-4', state_bits=0x0006),
        dict(name='state-priority-8000-before-4', state_bits=0x8004,
             cadence=0x0F, enabled=0xFF, options=3, vga=True),
        dict(name='flag80-before-state-4', entity_flags=0x80, state_bits=0x0004),
        dict(name='dispatch-0002-pc-command', state_bits=0x0002,
             cadence=0, enabled=0, options=1, vga=True),
        dict(name='countdown-expiry-skips-dispatch', countdown=1,
             state_bits=0x0001),
        dict(name='countdown-nonzero-dispatch', countdown=2,
             state_bits=0x0001),
        dict(name='two-slots-tail-loop', bound=2, second_inactive=0xFF,
             state_bits=0x0001),
        dict(name='live-pass-counter-extends-original-bound', bound=1,
             state_bits=0x0001, second_inactive=0xFF, provider='live-counter'),
        dict(name='scan-inactive-then-arm', bound=2, scan_request=0xFF,
             scan_cursor=0, scan_first_inactive=0xFF,
             scan_second_bits=0, scan_second_countdown=0),
        dict(name='scan-occupied-early-return', bound=1, scan_request=1,
             scan_cursor=2, scan_candidate_bits=3),
        dict(name='scan-countdown-early-return', bound=1, scan_request=1,
             scan_cursor=2, scan_candidate_countdown=1),
        dict(name='scan-eligible-outside-pass', bound=1, scan_request=1,
             scan_cursor=2, scan_candidate_bits=0),
        dict(name='scan-equal-bound-clears', bound=1, scan_request=1,
             scan_cursor=1),
        dict(name='readback-live-return-provider', provider='readback-return'),
        dict(name='countdown-live-return-provider', countdown=2,
             state_bits=0x0001, provider='countdown-return'),
        dict(name='state0008-vga-call', state_bits=0x0008,
             vga=True),
        dict(name='state8000-sound-adlib', state_bits=0x8000,
             cadence=0x0F, enabled=0xFF, options=3),
        dict(name='sound-returned-ds-owns-outer-tail', state_bits=0x8000,
             cadence=0x0F, enabled=0xFF, options=3,
             provider='sound-live-ds', alternate_ds=0x7100),
        dict(name='state8000-sound-tandy', state_bits=0x8000,
             cadence=0x0F, enabled=0xFF, options=3, driver='tandysnd'),
        dict(name='state8000-sound-unbound', state_bits=0x8000,
             cadence=0x0F, enabled=0xFF, options=3,
             sound_vector=(0x1234, 0x7000)),
        dict(name='stack-save-live-countdown-alias', state_bits=0,
             countdown=1, ds=DATA_SEGMENT, ss=DATA_SEGMENT,
             sp=RECORD + 0x21),
        dict(name='stack-word-offset-wrap', bound=0, sp=0),
        dict(name='stack-physical-word-wrap', bound=0, ss=0xFFFF, sp=0x0011),
        dict(name='gate-data-physical-wrap', gate=0xFF, ds=0xFFFF),
    ]
    cadence_by_state = {
        0x0001: 2, 0x1000: 1, 0x2000: 1, 0x4000: 1,
        0x0002: 0x10, 0x8000: 3, 0x0004: 3, 0x0400: 3,
        0x0008: 5, 0x0010: 2, 0x0020: 3, 0x0040: 0,
        0x0080: 1, 0x0100: 7, 0x0200: 0, 0x0800: 0,
    }
    for bit in (0x0002, 0x8000, 0x0004, 0x0400, 0x0001, 0x0008,
                0x0010, 0x0020, 0x0040, 0x0080, 0x0100, 0x0200,
                0x0800, 0x1000, 0x2000, 0x4000):
        rows.append(dict(name=f'dispatch-{bit:04x}', state_bits=bit,
                         cadence=cadence_by_state[bit], vga=True))
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x1F19 + index * 71)
        row.setdefault('gate', 0)
        row.setdefault('bound', 1)
        row.setdefault('state_bits', 0x0001)
        row.setdefault('entity_flags', 0)
        row.setdefault('countdown', 0)
        row.setdefault('cadence', 3)
        row.setdefault('inactive', 0)
        row.setdefault('second_inactive', 0)
        row.setdefault('scan_request', 0)
        row.setdefault('scan_cursor', 0)
        row.setdefault('scan_second_bits', 0)
        row.setdefault('scan_second_countdown', 0)
        row.setdefault('scan_candidate_bits', 0)
        row.setdefault('scan_candidate_countdown', 0)
        row.setdefault('x', 0x0020)
        row.setdefault('y', 0x0040)
        row.setdefault('pitch', 0x00D0)
        row.setdefault('flags', 0x0ED7)
        row.setdefault('ds', DATA_SEGMENT)
        row.setdefault('ss', 0x5000)
        row.setdefault('sp', 0xD000)
        row.setdefault('outer_return', 0x7A5C)
        row.setdefault('slot2e', 0x6170)
        row.setdefault('slot3c', 0x6174)
        row.setdefault('driver', 'adlib')
        row.setdefault('enabled', 0)
        row.setdefault('options', 0)
        row.setdefault('vga', False)
    return rows


def setup(case):
    """Build the executable and one or two live records for 1F19."""
    template = dict(case)
    template.setdefault('load', LOAD)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('si', RECORD)
    template.setdefault('sp', 0xD000)
    template.setdefault('seed', 0x1F1900 + len(case['name']))
    template.setdefault('enabled', 0)
    template.setdefault('options', 0)
    wants_vga = bool(template.get('vga'))
    template['vga'] = False
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(template)
    ds, ss = template['ds'] & 0xFFFF, template['ss'] & 0xFFFF
    si, sp = template['si'] & 0xFFFF, template['sp'] & 0xFFFF
    regs.update(cs=template['load'], ip=ENTRY, ds=ds, ss=ss,
                si=si, sp=sp, es=template.get('es', regs['es']))
    if template.get('df'):
        regs['flags'] |= 0x0400
    else:
        regs['flags'] &= ~0x0400

    put8(memory, ds, 0x2B, template.get('gate', 0))
    put8(memory, ds, 0x42, template.get('bound', 1))
    put8(memory, ds, 0x43, template.get('bound', 1))
    put8(memory, ds, 0x4B, template.get('scan_request', 0))
    put8(memory, ds, 0x4C, template.get('scan_cursor', 0))
    put8(memory, ds, 0x50, 0)
    put8(memory, ds, 0x2010, template.get('enabled', 0))
    put8(memory, ds, 0x25A7, template.get('options', 0))
    put16(memory, ss, sp, template.get('outer_return', 0x7A5C))

    def seed_record(offset, *, bits=0, countdown=0, flags=0, inactive=0,
                    cadence=3, x=0x20, y=0x40, height=0x10):
        put16(memory, ds, offset + 6, height)
        put16(memory, ds, offset + 8, bits)
        put8(memory, ds, offset + 0x20, countdown)
        put8(memory, ds, offset + 0x24, flags)
        put8(memory, ds, offset + 0x26, inactive)
        put8(memory, ds, offset + 0x28, cadence)
        put16(memory, ds, offset, x)
        put16(memory, ds, offset + 2, y)

    seed_record(si, bits=template.get('state_bits', 1),
                countdown=template.get('countdown', 0),
                flags=template.get('entity_flags', 0),
                inactive=template.get('inactive', 0),
                cadence=template.get('cadence', 3), x=template.get('x', 0x20),
                y=template.get('y', 0x40), height=template.get('height', 0x10))
    if template.get('bound', 1) > 1 or template.get('provider') == 'live-counter':
        seed_record((si + 0x2D) & 0xFFFF,
                    bits=template.get('second_bits', 1),
                    countdown=template.get('second_countdown', 0),
                    flags=template.get('second_flags', 0),
                    inactive=template.get('second_inactive', 0),
                    cadence=template.get('second_cadence', 3))

    if template.get('provider') == 'sound-live-ds':
        alternate = template['alternate_ds']
        put8(memory, alternate, 0x42, 1)
        put8(memory, alternate, 0x4B, 0)
        put8(memory, alternate, 0x50, 0xFF)
        put16(memory, alternate, si, template['x'])
        put16(memory, alternate, si + 2, template['y'])

    cursor = template.get('scan_cursor', 0)
    if template.get('scan_request', 0):
        target = (si + cursor * 0x2D) & 0xFFFF
        # The scan examines the cursor-selected record after the active pass.
        if cursor == 0 and 'scan_first_inactive' in template:
            seed_record(target, bits=template.get('scan_second_bits', 0),
                        countdown=template.get('scan_second_countdown', 0),
                        inactive=template.get('scan_first_inactive', 0))
        else:
            seed_record(target, bits=template.get('scan_candidate_bits', 0),
                        countdown=template.get('scan_candidate_countdown', 0),
                        inactive=0)

    if wants_vga:
        # Parent readback configures this independent device through its word
        # OUTs; interaction.setup's VGA initializer is specific to SS=A000.
        device = MinimapVga(template['seed'], read_map=0)
        device.seq[4] = 0x06
        device.gc[6] = 0x05
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[8] = 0xFF
        for plane in device.planes:
            plane[:] = bytes(65536)
    return memory, regs, device, pc_binding, sound_binding


class UpdateAccess(interactions.Access):
    """Bounded ordered bus plus the two outer live-CALL-word providers."""
    event_limit = EVENT_LIMIT

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.countdown_frame_armed = False

    def _provider(self, kind, address):
        super()._provider(kind, address)
        effect = self.case.get('provider')
        address &= MASK
        ss, sp = self.case.get('ss', 0x5000), self.case.get('sp', 0xD000)
        if (effect == 'live-counter' and kind == 'read' and
                address == physical(self.regs['ds'], 0x42) and effect not in self.used):
            self.store(address, 2)
            self.used.add(effect)
        if effect == 'sound-live-ds' and kind == 'write' and effect not in self.used:
            latch = interactions.sound.TAILS[self.case['driver']][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                # Outer PUSH ES, INT's six bytes, then the driver's PUSH DS.
                self.modify_word(ss, sp - 10, self.case['alternate_ds'])
                self.used.add(effect)
        if effect == 'countdown-return':
            frame = physical(ss, sp - 4)
            if kind == 'write' and address in (frame, (frame + 1) & MASK):
                self.countdown_frame_armed = True
            if (kind == 'read' and self.countdown_frame_armed and
                    address == physical(self.case.get('ds', DATA_SEGMENT),
                                        self.case.get('si', RECORD) + 0x20) and
                    effect not in self.used):
                self.modify_word(ss, sp - 4, self.case.get('changed_return', 0x4567))
                self.used.add(effect)

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-update OUT callback budget exhausted')
        if self.device is not None and port in (0x3C4, 0x3CE):
            self.device.out(port, value, flags)
        if self.case.get('provider') == 'readback-return' and 'readback-return' not in self.used:
            self.modify_word(self.case.get('ss', 0x5000),
                             self.case.get('sp', 0xD000) - 2,
                             self.case.get('changed_return', 0x4567))
            self.used.add('readback-return')
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


class UpdateCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class UpdateResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status', 'child_entry', 'child_status')]


def original(case, memory, regs, device, *, core):
    stops = {address: 0 for address in RETURNS} if core else None
    observed = interactions.original(
        case, memory, regs, device, False,
        main_instructions=INTEGRATED_INS,
        main_ret_continuations=MAIN_RET_CONTINUATIONS,
        main_call_returns=MAIN_CALL_RETURNS,
        stop_offsets=stops, access_factory=UpdateAccess,
        instruction_limit=INSTRUCTION_LIMIT)
    if case.get('provider') == 'live-counter':
        oracle_require('live-counter' in observed['used'] and
                       observed['regs']['si'] == RECORD + 2 * 0x2D and
                       get8(observed['memory'], regs['ds'], 0x42) == 0,
                       case['name'] + ': live counter did not add the second slot')
    if case.get('provider') == 'sound-live-ds':
        alternate = case['alternate_ds']
        oracle_require('sound-live-ds' in observed['used'] and
                       observed['regs']['ds'] == alternate and
                       get8(observed['memory'], alternate, 0x42) == 0 and
                       get8(observed['memory'], alternate, 0x50) == 0 and
                       get8(observed['memory'], regs['ds'], 0x42) == 1 and
                       get8(observed['memory'], regs['ds'], 0x50) == 0xFF,
                       case['name'] + ': returned DS did not own the outer tail')
    return observed


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-update-m{mutation}.dll',
                     mutation, 'entity_update')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_entity_update_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(UpdateCall),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = UpdateResult
        self.adapter = self.lib.lmn_entity_update_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        access = UpdateAccess(case, memory, dict(initial_regs), device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        callbacks = (interactions.READ(read), interactions.WRITE(write),
                     interactions.OUT(out))
        bus = interactions.Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**initial_regs)
        pc = ct.byref(pc_binding) if pc_binding is not None else None
        sound = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = UpdateCall(*(initial_regs[name] for name in
                                ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp',
                                 'cs', 'ds', 'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), pc, sound, ct.byref(bus))
            regs.ax, regs.bx, regs.cx, regs.dx = (result.value, result.map_cursor,
                                                   result.count, result.auxiliary_value)
            regs.si, regs.di, regs.bp = (result.record_cursor, result.object_cursor,
                                          result.candidate_y)
            regs.cs, regs.ds, regs.es = (result.code_segment, result.data_segment,
                                          result.extra_segment)
            regs.ss, regs.sp, regs.flags, regs.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
            child_entry, child_status = result.child_entry, result.child_status
        else:
            status = self.adapter(ram, ct.byref(regs), pc, sound, ct.byref(bus))
            child_entry = child_status = None
        return dict(memory=bytes(memory), regs={name: getattr(regs, name)
                                               for name in interactions.REG_NAMES},
                    device=device, events=access.events, providers=set(access.used),
                    status=status, continuation=regs.ip,
                    child_entry=child_entry, child_status=child_status)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered event count {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        require(got[:3] == ref[:3],
                f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
                f'under {ref[4]:04X}')


def expected_child(case, observed):
    if case.get('provider') == 'readback-return':
        return 0x5D94, 0xFFFF
    if case.get('provider') == 'countdown-return':
        return 0x2E04, 0
    if case.get('sound_binding') is False or case.get('sound_vector') is not None:
        return 0x2D0F, 1
    if case.get('pc_binding') is False or case.get('pc_vector') is not None:
        return 0x2350, 1
    return 0, 0xFFFF


def compare_case(native, case, *, core):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), pc_binding, sound_binding, core=core)
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        require(actual['regs'][name] == expected['regs'][name],
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X}')
    flag_mask = expected['flag_mask']
    require(((actual['regs']['flags'] ^ expected['regs']['flags']) & flag_mask) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{expected["regs"]["flags"]:04X} under {flag_mask:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    require(actual['providers'] == expected['used'],
            f'{label}: provider effects {actual["providers"]}/{expected["used"]}')
    if core:
        child_entry, child_status = expected_child(case, expected)
        require((actual['child_entry'], actual['child_status']) ==
                (child_entry, child_status),
                f'{label}: child seam {actual["child_entry"]:04X}/'
                f'{actual["child_status"]:04X} expected {child_entry:04X}/'
                f'{child_status:04X}')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA planes/registers/latches differ')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(got_trace == ref_trace, label + ': VGA trace differs')
    if case.get('provider'):
        oracle_require(case['provider'] in expected['used'],
                       label + ': declared provider was not observed')
    own_sites = {address for source, address in expected['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target) for source, source_ip, target in expected['edges']
                 if source == 'main' and source_ip in OWN_INS}
    integrated_sites = {address for source, address in expected['sites']
                        if source == 'main'}
    return dict(name=case['name'], core=core, status=expected['status'],
                continuation=expected['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(integrated_sites),
                event_count=len(expected['events']), steps=expected['steps'],
                providers=sorted(expected['used']))


def input_hashes():
    source_names = (
        'entity_update', 'entity_vga', 'entity_countdown', 'entity_zero_state',
        'entity_state2', 'entity_state4', 'entity_cadence', 'entity_state8',
        'entity_state10', 'entity_state20', 'entity_state40', 'entity_state80',
        'entity_state100', 'entity_state200', 'entity_state400', 'entity_state800',
        'entity_late_states', 'entity_finish', 'entity_pixel', 'entity_stroke',
        'entity_mask', 'entity_mask_rows', 'coordinate_pixel', 'entity_pattern',
        'entity_interactions', 'pcspeaker_interrupt', 'pcspeaker_dispatch',
        'pcspeaker', 'sound_interrupt', 'sound_latches')
    paths = [
        'src/game_code.asm', 'src/entity_graphics.asm', 'src/program.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'requirements.txt',
        'tests/entity_update.py', 'tests/entity_interactions.py',
        'tests/entity_cadence.py', 'tests/entity_countdown.py',
        'tests/entity_zero_state.py', 'tests/entity_state2.py',
        'tests/entity_state4.py', 'tests/entity_state8.py',
        'tests/entity_state10.py', 'tests/entity_state20.py',
        'tests/entity_state40.py', 'tests/entity_state80.py',
        'tests/entity_state100.py', 'tests/entity_state200.py',
        'tests/entity_state400.py', 'tests/entity_state800.py',
        'tests/entity_late_states.py', 'tests/entity_finish.py',
        'tests/entity_vga.py', 'tests/entity_pixel.py', 'tests/entity_stroke.py',
        'tests/entity_mask.py', 'tests/entity_mask_rows.py',
        'tests/entity_pattern.py', 'tests/coordinate_pixel.py',
        'tests/minimap_vga.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/sound_latches.py',
        'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/resources.py',
        'tools/unpack.py',
    ]
    for name in source_names:
        paths.extend((f'c/{name}.c', f'c/{name}.h'))
    paths.extend(('c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
                  'c/pcspeaker_sym.h', 'c/sound_latches_sym.h'))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(set(paths))}


def verify_static_identity():
    oracle_require(len(OWN_INS) == EXPECTED_OWN_SITES and
                   sum(ins.size for ins in OWN_INS.values()) == EXPECTED_OWN_BYTES,
                   'entity-update byte/site identity changed')
    oracle_require(len(OWN_EDGES) == EXPECTED_OWN_EDGES,
                   f'entity-update static edge count changed: {sorted(OWN_EDGES)}')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned main code image identity changed')
    calls = {address for address, ins in INTEGRATED_INS.items()
             if ins.mnemonic.lower() == 'call'}
    oracle_require(calls <= set(MAIN_CALL_RETURNS),
                   f'original CALL contracts missing {sorted(calls-set(MAIN_CALL_RETURNS))}')


def original_only():
    before = input_hashes()
    verify_static_identity()
    specs = cases()
    covered, edges = set(), set()
    rows = []
    for case in specs:
        memory, regs, device, _pc, _sound = setup(case)
        observed = original(case, bytearray(memory), dict(regs),
                            copy.deepcopy(device), core=False)
        own_sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
        own_edges = {(source_ip, target) for source, source_ip, target in observed['edges']
                     if source == 'main' and source_ip in OWN_INS}
        covered.update(own_sites)
        edges.update(own_edges)
        if case.get('provider') in ('readback-return', 'countdown-return'):
            oracle_require(observed['status'] == 2,
                           case['name'] + ': live CALL return provider did not stop at changed target')
        elif case.get('sound_binding') is False or case.get('sound_vector') is not None:
            oracle_require(observed['status'] == 1,
                           case['name'] + ': unbound sound vector seam was not reached')
        else:
            oracle_require(observed['status'] == 0,
                           case['name'] + f': parent boundary status {observed["status"]}')
        if case['name'] in ('gate-ff-bypasses-scan', 'zero-bound-bypasses-scan'):
            executed_main = {address for source, address in observed['sites']
                             if source == 'main'}
            oracle_require(not any(0x2005 <= address <= 0x2046
                                   for address in executed_main),
                           case['name'] + ': bypass path entered scan code')
            oracle_require(get8(observed['memory'], regs['ds'], 0x4B) == 0xFF,
                           case['name'] + ': bypass path changed pending scan request')
            oracle_require(observed['continuation'] == case.get('outer_return', 0x7A5C),
                           case['name'] + ': live outer return value changed')
        if case['name'] == 'dispatch-0002-pc-command':
            oracle_require(any(source in ('pc', 'pc-child')
                               for source, _address in observed['sites']),
                           case['name'] + ': declared PC dispatch was not executed')
        if case['name'] in ('state8000-sound-adlib', 'state8000-sound-tandy'):
            oracle_require(any(source == 'sound' for source, _address in observed['sites']),
                           case['name'] + ': declared sound driver was not entered')
        if case.get('provider'):
            oracle_require(case['provider'] in observed['used'],
                           case['name'] + ': declared provider was not observed')
        rows.append(dict(name=case['name'], status=observed['status'],
                         continuation=observed['continuation'], sites=sorted(own_sites),
                         edges=[list(edge) for edge in sorted(own_edges)],
                         events=len(observed['events']), steps=observed['steps']))
        gc.collect()
    expected_edges = OWN_EDGES - {INFEASIBLE_EDGE}
    oracle_require(covered == set(OWN_INS),
                   f'parent site union {len(covered)}/{len(OWN_INS)}; '
                   f'missing={sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == expected_edges,
                   f'parent feasible edges {len(edges)}/{len(expected_edges)}; '
                   f'missing={sorted(expected_edges-edges)} extra={sorted(edges-expected_edges)}')
    oracle_require(before == input_hashes(),
                   'entity-update inputs changed during original-only preflight')
    print(f'PASS entity update original: {len(specs)} fixtures, {len(covered)} sites, '
          f'{len(edges)} feasible edges, {sum(row["events"] for row in rows)} bus events',
          flush=True)
    return rows


def worker(directory):
    before = input_hashes()
    verify_static_identity()
    specs = cases()
    native = Native(directory)
    rows, sites, edges, integrated_sites = [], set(), set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(native, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            integrated_sites.update(row['integrated_sites'])
            total_events += row['event_count']
            total_steps += row['steps']
        gc.collect()
    expected_edges = OWN_EDGES - {INFEASIBLE_EDGE}
    oracle_require(sites == set(OWN_INS),
                   f'native original site union {len(sites)}/{len(OWN_INS)}; '
                   f'missing={sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == expected_edges,
                   f'native original feasible edge union {len(edges)}/{len(expected_edges)}; '
                   f'missing={sorted(expected_edges-edges)} extra={sorted(edges-expected_edges)}')

    witnesses = {
        1: 'state-priority-8000-before-4',
        2: 'flag80-before-state-4',
        3: 'stack-save-live-countdown-alias',
        4: 'scan-eligible-outside-pass',
        5: 'scan-inactive-then-arm',
        6: 'readback-live-return-provider',
        7: 'countdown-live-return-provider',
        8: 'dispatch-8000',
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
            raise OracleFailure(f'entity-update mutation {mutation} survived completed witness {case_name}')
        gc.collect()
    oracle_require(len(mutations) == 8, 'entity-update mutation witness count changed')
    oracle_require(before == input_hashes(),
                   'entity-update source inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[0x1F19, 0x1FE8],
                                                             [0x1FEB, 0x2047]],
        translated_code_bytes=EXPECTED_OWN_BYTES, instruction_sites=EXPECTED_OWN_SITES,
        own_static_branch_edges=EXPECTED_OWN_EDGES,
        parent_feasible_branch_edges=len(expected_edges), case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations, executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        infeasible_edge=[list(INFEASIBLE_EDGE)],
        integrated_main_instruction_addresses=sorted(integrated_sites),
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                    continuation=row['continuation'], sites=row['sites'],
                    edges=row['edges'], event_count=row['event_count'],
                    steps=row['steps'], providers=row['providers']) for row in rows],
        input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=INSTRUCTION_LIMIT,
                    ordered_bus_event_limit=EVENT_LIMIT,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='1F19..2046 entity-update caller; own spans exclude the shared '
               '1FE8..1FEB finish CALL and child implementations. Composed original '
               'CALL/RET execution covers readback, countdown, entity state, finish, '
               'pixel, mask, pattern, stroke, PC-speaker and AdLib/Tandy child seams. '
               'The adapter executes all three live outer RETs; the logical core '
               'stops before them. Comparison includes full 1 MiB RAM, all registers, '
               'defined FLAGS, ordered VGA/port bus events, live stack returns and '
               'VGA planes/latches.'))
    print(f'PASS entity update: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} feasible edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--original-worker'], cwd=ROOT,
                             timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                             check=True)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return
    if sys.argv[1:] == ['--original-worker']:
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_update.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-update-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
