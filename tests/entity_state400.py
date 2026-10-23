"""Bounded original-versus-C checks for the sparse state-0400 handler."""
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

SIZE, MASK, ALL_FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END = 0x2A6D, 0x2B35
OWN_SPANS = ((0x2A6D, 0x2ABD), (0x2ABE, 0x2ADB),
             (0x2ADC, 0x2AEB), (0x2AEC, 0x2B35))
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20E2, 0x20E9))
CONTINUATION = 0x1FEB
PAIR_BASE, ROW_PITCH, MASK_TABLE = 0x2698, 0x0004, 0x547C
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
MAX_INSTRUCTIONS, MAX_EVENTS = 2000, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state400-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state400-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_spans(spans):
    return {ins.address: ins for start, end in spans
            for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_spans(OWN_SPANS)
PIXEL_INS = {ins.address: ins for ins in
             MD.disasm(IMAGE[PIXEL_ENTRY:PIXEL_RET + 1], PIXEL_ENTRY)}
FINISH_INS = decoded_spans(FINISH_SPANS)
INTERACTION_INS = interactions.MAIN_INS
INTEGRATED_INS = dict(OWN_INS)
INTEGRATED_INS.update(PIXEL_INS)
INTEGRATED_INS.update(FINISH_INS)
INTEGRATED_INS.update(INTERACTION_INS)
INTERACTION_RETS = {address for address, ins in INTERACTION_INS.items()
                    if ins.mnemonic.lower() == 'ret'}
CALL_RETURNS = {
    0x2A92: ({PIXEL_RET}, 7),
    0x2ABE: ({PIXEL_RET}, 7),
    0x2ADC: ({PIXEL_RET}, 7),
    0x1FE8: (INTERACTION_RETS, 5),
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
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status')]


class NativeMismatch(AssertionError):
    """Only a completed original/native comparison can credit a mutant."""


class OracleFailure(AssertionError):
    """The bounded original/provider failed to reach a declared boundary."""


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


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def pixel_offset(x, y):
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    return ((row * 0xD0) + ((x & 0xFFFF) >> 3) + 0x4A40) & 0xFFFF


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if (ins.operands and
                ins.operands[-1].type == capstone.x86.X86_OP_IMM):
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


OWN_EDGES = branch_edges(OWN_INS)


def cases():
    """Exercise each dispatch/probe edge, live aliases, and integration seams."""
    rows = [
        dict(name='three-clear-all-increments', dispatch=3, y=0x0040),
        dict(name='three-occupied-first', dispatch=3, y=0x0040, occupied=0),
        dict(name='three-occupied-second', dispatch=3, y=0x0040, occupied=1),
        dict(name='three-occupied-third', dispatch=3, y=0x0040, occupied=2),
        dict(name='two-clear-all-increments', dispatch=2, y=0x0040),
        dict(name='two-occupied-first', dispatch=2, y=0x0040, occupied=0),
        dict(name='two-occupied-second', dispatch=2, y=0x0040, occupied=1),
        dict(name='one-clear-increments', dispatch=1, y=0x0040),
        dict(name='one-occupied', dispatch=1, y=0x0040, occupied=0),
        dict(name='unknown-signed-minus-one-wrap', dispatch=0xFF, y=0x0000),
        dict(name='unknown-byte-add-no-carry-through-alias', dispatch=0,
             y=0x0040, si=0x2789, pair_index=0x00FF,
             pair_first=0xFF, pair_second=0x00),
        dict(name='unknown-signed-negative-below-height', dispatch=0,
             y=0xFFFF),
        dict(name='clear-reaches-signed-inactive-height', dispatch=1,
             y=0x00B3),
        dict(name='first-store-changes-second-pair-byte', dispatch=2,
             y=0x0040, pair_index=0x198F, pair_first=3, pair_second=2,
             si=0x4000),
        dict(name='unchecked-pair-offset-logical-wrap', dispatch=1,
             y=0x0040, pair_index=0xFFFF, pair_first=0x12,
             pair_second=1),
        dict(name='live-row-pitch-between-second-and-third', dispatch=3,
             y=0x0040, occupied=2, pitch=0x0010, pitch_after=0x0060,
             provider='pitch-after-second-sample'),
        dict(name='pixel-return-live-other-continuation', dispatch=1,
             y=0x0040, provider='pixel-return', changed_target=0x2AC1),
        dict(name='transition-callback-read-after-overlap-store',
             dispatch=2, y=0x0040, occupied=0, si=0x002A,
             callback_seed=0x1234),
        dict(name='vga-three-probe-df-set', dispatch=3, y=0x0040,
             occupied=2, vga=True, df=True, x=0x0027),
        dict(name='pixel-call-physical-word-wrap', dispatch=2, y=0x0040,
             ss=0xFFFF, sp=0x0011, occupied=1),
        dict(name='record-and-pair-pointer-wrap', dispatch=0,
             y=0xFFF0, si=0xFFF0, pair_index=0xFFFE,
             pair_first=0x21, pair_second=0x00),
        dict(name='record-data-stack-same-segment', dispatch=1,
             y=0x0040, ds=0x5000, ss=0x5000),
        dict(name='direct-positive-add-crosses-height', dispatch=0,
             y=0x00B0, pair_second=4),
        dict(name='direct-signed-overflow-stays-active', dispatch=0,
             y=0x7FFF, pair_second=4),
    ]
    oracle_require(20 <= len(rows) <= 30,
                   f'state400 focused fixture count changed: {len(rows)}')
    for index, case in enumerate(rows):
        case.setdefault('seed', 0x2A6D + index * 83)
        case.setdefault('x', 0x0020)
        case.setdefault('pitch', 0x0050)
        case.setdefault('pair_index', 0)
        case.setdefault('pair_first', 0x05)
        case.setdefault('dispatch', 0x03)
        case.setdefault('pair_second', case['dispatch'])
        case.setdefault('occupied', None)
        case.setdefault('callback_seed', 0x6170)
        case.setdefault('df', False)
    return rows


def configure_vga(device):
    device.seq[4] = 0x06
    device.seq[2] = 0x01
    device.gc[0] = device.gc[1] = device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    for plane in device.planes:
        plane[:] = bytes(65536)


def expected_y_before_finish(case, dispatch=None):
    y = case.get('y', 0x0040) & 0xFFFF
    dispatch = (case.get('dispatch', 3) if dispatch is None else dispatch) & 0xFF
    occupied = case.get('occupied')
    if dispatch in (1, 2, 3):
        return (y + (dispatch if occupied is None else occupied)) & 0xFFFF
    return (y + signed8(case.get('pair_second', dispatch))) & 0xFFFF


def setup(case):
    template = dict(case)
    template.update(load=case.get('load', interactions.MAIN_SEG), vga=False,
                    sample=0, second_sample=0,
                    x=case.get('x', 0x0020), y=case.get('y', 0x0040),
                    record_delta=0)
    template.setdefault('si', 0x4000)
    template.setdefault('ds', (interactions.MAIN_SEG + 0x09A9) & 0xFFFF)
    template.setdefault('es', 0xA000)
    template.setdefault('ss', 0x5000)
    template.setdefault('sp', 0xD000)
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if case.get('df', False) else (flags & ~0x0400)
    template['flags'] = flags

    memory, regs, _ignored, pc_binding, sound_binding, _ = interactions.setup(template)
    regs.update(ip=ENTRY, cs=template['load'], ds=template['ds'],
                es=template['es'], ss=template['ss'], sp=template['sp'],
                si=template['si'], flags=flags)
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']
    x, y = case.get('x', 0x0020) & 0xFFFF, case.get('y', 0x0040) & 0xFFFF

    # Make original-only fixtures independent of whatever bytes preceded the
    # record. A poison case still checks that only declared fields are used.
    put16(memory, ds, (si + 0x00) & 0xFFFF, x)
    put16(memory, ds, (si + 0x02) & 0xFFFF, y)
    put16(memory, ds, (si + 0x04) & 0xFFFF, case.get('callback_seed', 0x6170))
    put16(memory, ds, (si + 0x06) & 0xFFFF, case.get('height_word', 0x2345))
    put16(memory, ds, (si + 0x08) & 0xFFFF, case.get('state8', 0xA55A))
    put16(memory, ds, (si + 0x0A) & 0xFFFF, case.get('stateA', 0xB66B))
    put16(memory, ds, (si + 0x0C) & 0xFFFF, case.get('stateC', 0xC77C))
    put16(memory, ds, (si + 0x0E) & 0xFFFF, case.get('pair_index', 0))
    put16(memory, ds, (si + 0x10) & 0xFFFF, case.get('state10', 0xD88D))
    put16(memory, ds, (si + 0x12) & 0xFFFF, case.get('state12', 0xE99E))
    put16(memory, ds, (si + 0x14) & 0xFFFF, case.get('saved_callback', 0xA55A))
    put8(memory, ds, (si + 0x27) & 0xFFFF, case.get('record_delta', 0))
    put8(memory, ds, (si + 0x24) & 0xFFFF, case.get('state24', 0xA5))
    put8(memory, ds, (si + 0x28) & 0xFFFF, 0xCC)
    put8(memory, ds, (si + 0x29) & 0xFFFF, 0xDD)
    put8(memory, ds, (si + 0x2A) & 0xFFFF, 0xEE)
    put16(memory, ds, ROW_PITCH, case.get('pitch', 0x0050))

    pair_index = case.get('pair_index', 0) & 0xFFFF
    pair_offset = (PAIR_BASE + pair_index) & 0xFFFF
    put8(memory, ds, pair_offset, case.get('pair_first', 0x05))
    put8(memory, ds, (pair_offset + 1) & 0xFFFF,
         case.get('pair_second', case.get('dispatch', 3)))
    # Project just the architecturally ordered first-byte store and second-byte
    # fetch to choose a safe interaction-map result even when they alias.
    projected_pair = bytearray(memory)
    first_byte = get8(projected_pair, ds, pair_offset)
    put8(projected_pair, ds, (si + 0x28) & 0xFFFF, first_byte)
    effective_dispatch = get8(projected_pair, ds, (pair_offset + 1) & 0xFFFF)
    case['_effective_dispatch'] = effective_dispatch
    put16(memory, ss, sp, case.get('outer_return', 0x7331))

    pixel_base = pixel_offset(x, y)
    pitch_before = case.get('pitch', 0x0050) & 0xFFFF
    pitch_after = case.get('pitch_after', pitch_before) & 0xFFFF
    sample_offsets = [pixel_base]
    sample_offsets.append((sample_offsets[-1] + pitch_before) & 0xFFFF)
    sample_offsets.append((sample_offsets[-1] + pitch_after) & 0xFFFF)
    # For ordinary cases the two pitches are equal. The provider fixture makes
    # its second sample before changing the word, then uses the new pitch.
    if case.get('provider') != 'pitch-after-second-sample':
        sample_offsets = [(pixel_base + i * pitch_before) & 0xFFFF
                          for i in range(3)]
    device = None
    if case.get('vga'):
        device = MinimapVga(0x4000 ^ case.get('seed', 0), read_map=0)
        configure_vga(device)
    for index, offset in enumerate(sample_offsets):
        value = (PIXEL_MASKS[x & 7]
                 if case.get('occupied') == index else 0)
        address = physical(regs['es'], offset)
        if device is not None:
            oracle_require(VGA_BASE <= address < VGA_END,
                           case['name'] + ': VGA sample escaped the aperture')
            device.planes[0][address - VGA_BASE] = value
        else:
            memory[address] = value

    # 1FE8 invokes the interaction map using the record's post-body Y. The
    # canonical map fixture is zero in both slots so it returns without
    # entering any untranslated service path.
    final_y = expected_y_before_finish(case, effective_dispatch)
    if effective_dispatch in (1, 2, 3) and case.get('occupied') is not None:
        # The collision transition keeps the Y produced by preceding clears.
        final_y = (y + case['occupied']) & 0xFFFF
    live_record_delta = get8(memory, ds, (si + 0x27) & 0xFFFF)
    first_map, second_map = interactions.map_offsets(x, final_y, live_record_delta)
    for offset in (first_map, second_map):
        address = physical(ss, offset)
        memory[address] = 0
        if device is not None and VGA_BASE <= address < VGA_END:
            device.planes[0][address - VGA_BASE] = 0

    return memory, regs, device, pc_binding, sound_binding, sample_offsets


class State400Access(interactions.Access):
    """Bounded live pitch and CALL-return providers for the parent fixture."""
    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.sample_reads = 0
        self.sample_addresses = {
            physical(regs['es'], offset) for offset in case.get('sample_offsets', ())
        }

    def set_pitch(self):
        self.modify_word(self.regs['ds'], ROW_PITCH,
                         self.case.get('pitch_after', 0x0050) & 0xFFFF)
        self.used.add('pitch')

    def change_pixel_return(self):
        self.modify_word(self.regs['ss'], (self.regs['sp'] - 2) & 0xFFFF,
                         self.case.get('changed_target', 0x2AC1))
        self.used.add('pixel-ret')

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        if kind != 'read':
            return result
        address &= MASK
        if address in self.sample_addresses:
            self.sample_reads += 1
            if (self.case.get('provider') == 'pitch-after-second-sample' and
                    self.sample_reads == 2 and 'pitch' not in self.used):
                self.set_pitch()
        table_offset = (MASK_TABLE + (self.case.get('x', 0x20) & 7)) & 0xFFFF
        if (self.case.get('provider') == 'pixel-return' and
                address == physical(self.regs['ds'], table_offset) and
                'pixel-ret' not in self.used):
            self.change_pixel_return()
        return result


def original(case, memory, regs, device, sample_offsets):
    call_returns = dict(CALL_RETURNS)
    oracle_case = dict(case, sample_offsets=sample_offsets)
    return interactions.original(
        oracle_case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=ALL_FLAGS, main_instructions=INTEGRATED_INS,
        main_call_returns=call_returns, stop_offsets={CONTINUATION: 0},
        access_factory=State400Access, instruction_limit=MAX_INSTRUCTIONS)


class NativeBus:
    def __init__(self, case, memory, regs, device, sample_offsets):
        native_case = dict(case, sample_offsets=sample_offsets)
        self.access = State400Access(native_case, memory, regs, device)

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
            worker_fail(CALLBACK_EXIT,
                        f'unexpected state400 OUT {port:04X}={value:04X}/{flags:04X}')

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state400-m{mutation}.dll',
                     mutation, 'entity_state400')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state400_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state400_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, sample_offsets, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        native_bus = NativeBus(case, memory, initial_regs, device, sample_offsets)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        pc_ptr = ct.byref(pc_binding) if pc_binding is not None else None
        sound_ptr = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = Call(*(initial_regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
                'ss', 'sp', 'flags')))
            out = self.core(ram, ct.byref(call), pc_ptr, sound_ptr,
                            ct.byref(native_bus.bus))
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
                                  ct.byref(native_bus.bus))
            state = {name: getattr(registers, name) & 0xFFFF
                     for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=native_bus.access.events,
                    used=native_bus.access.used, status=status,
                    continuation=state['ip'])


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA provider')
        return
    require(actual is not None, label + ': VGA provider missing')
    require(actual.state() == expected.state(), label + ': VGA plane/register/latch state differs')
    got = [(kind, address, value) for kind, address, value, _flags in actual.trace]
    ref = [(kind, address, value) for kind, address, value, _flags in expected.trace]
    require(got == ref, label + ': VGA ordered access trace differs')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: event count {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        require(got[:3] == ref[:3],
                f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
                f'under {ref[4]:04X}')


def independent_checks(case, regs, sample_offsets, observed):
    name, ds, si = case['name'], regs['ds'], regs['si']
    if case.get('provider') == 'pitch-after-second-sample':
        oracle_require('pitch' in observed['used'] and
                       get16(observed['memory'], ds, ROW_PITCH) ==
                       case['pitch_after'],
                       name + ': row-pitch provider was not applied live')
    if case.get('provider') == 'pixel-return':
        oracle_require('pixel-ret' in observed['used'] and
                       (observed['status'], observed['continuation']) ==
                       (7, case['changed_target']),
                       name + ': actual pixel RET target was not consumed')
    if name == 'first-store-changes-second-pair-byte':
        oracle_require(get8(observed['memory'], ds, si + 0x28) == 3 and
                       0x2A92 in {address for source, address in observed['sites']
                                  if source == 'main'},
                       name + ': stored first byte did not select three probes')
    if name == 'unknown-byte-add-no-carry-through-alias':
        pair_hi = physical(ds, (PAIR_BASE + 0x0100) & 0xFFFF)
        pair_read = [i for i, event in enumerate(observed['events'])
                     if event[0] == 'read' and event[1] == pair_hi]
        index_write = [i for i, event in enumerate(observed['events'])
                       if event[0] == 'write' and
                       event[1] == physical(ds, si + 0x0F) and event[2] == 1]
        oracle_require(pair_read and index_write and pair_read[0] < index_write[-1] and
                       get16(observed['memory'], ds, si + 0x0E) == 0x0101 and
                       get16(observed['memory'], ds, si + 2) ==
                       case['y'],
                       name + ': pair byte was not read before aliased ADD')
    if name == 'transition-callback-read-after-overlap-store':
        callback_address = physical(ds, 0x002E)
        events = observed['events']
        reads = [i for i, event in enumerate(events)
                 if event[0] == 'read' and event[1] == callback_address]
        writes = [i for i, event in enumerate(events)
                  if event[0] == 'write' and event[1] == callback_address and
                  event[2] == 0xF8]
        oracle_require(reads and writes and writes[-1] < reads[-1] and
                       events[reads[-1]][2] == 0xF8 and
                       get16(observed['memory'], ds, si + 0x14) == 0xFFF8,
                       name + ': callback read did not observe the ordered +4 store')
    if name == 'clear-reaches-signed-inactive-height':
        oracle_require(('main', 0x2B2D, 0x2B32) in observed['edges'] and
                       ('main', 0x20E2) in observed['sites'],
                       name + ': signed height threshold did not take inactive path')
    if name == 'unknown-signed-negative-below-height':
        oracle_require(('main', 0x2B2D, 0x2B2F) in observed['edges'] and
                       ('main', 0x2B2D, 0x2B32) not in observed['edges'],
                       name + ': negative signed Y must remain below B4')
    if case.get('vga'):
        oracle_require(any(event[0] == 'read' and
                           VGA_BASE <= event[1] < VGA_END
                           for event in observed['events']),
                       name + ': VGA-backed pixel read was not observed')


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding, sample_offsets = setup(case)
    oracle = original(case, initial, regs, device, sample_offsets)
    independent_checks(case, regs, sample_offsets, oracle)
    if case.get('provider') == 'pixel-return':
        oracle_require((oracle['status'], oracle['continuation']) ==
                       (7, case['changed_target']),
                       case['name'] + ': original did not stop at changed RET target')
    else:
        oracle_require((oracle['status'], oracle['continuation']) ==
                       (0, CONTINUATION),
                       case['name'] + ': original missed normal 1FEB boundary: '
                       f'{oracle["status"]}/{oracle["continuation"]:04X}')
    actual = native.run(case, initial, regs, device, pc_binding,
                        sound_binding, sample_offsets, core=core)
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
    require(actual['used'] == oracle['used'],
            f'{label}: provider transitions {actual["used"]}/{oracle["used"]}')
    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target) for source, source_ip, target in oracle['edges']
                 if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(address for source, address in oracle['sites']
                                        if source == 'main'),
                event_count=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/adlib-symbols.json',
        'metadata/adlib-regions.json', 'metadata/adlib-encodings.json',
        'metadata/tandysnd-symbols.json', 'metadata/tandysnd-regions.json',
        'metadata/tandysnd-encodings.json', 'metadata/pcspeaker-symbols.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json',
        'src/game_code.asm', 'src/entity_graphics.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_state400.c', 'c/entity_state400.h',
        'c/entity_pixel.c', 'c/entity_pixel.h',
        'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/entity_state400.py', 'tests/entity_interactions.py',
        'tests/entity_finish.py', 'tests/entity_pixel.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/minimap_vga.py',
        'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/resources.py', 'tools/unpack.py',
        'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(before):
    oracle_require(before == input_hashes(),
                   'state400 inputs changed before original-only campaign')
    oracle_require(len(OWN_INS) == 66 and
                   sum(ins.size for ins in OWN_INS.values()) == 197 and
                   len(OWN_EDGES) == 27,
                   f'state400 known-code accounting changed: {len(OWN_INS)} sites, '
                   f'{sum(ins.size for ins in OWN_INS.values())} bytes, '
                   f'{len(OWN_EDGES)} edges')
    oracle_require(not ({0x2ABD, 0x2ADB, 0x2AEB} & set(OWN_INS)),
                   'unresolved bytes entered the owned instruction map')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed main-image hash changed')
    covered, edges, rows = set(), set(), []
    for case in cases():
        memory, regs, device, _pc, _sound, offsets = setup(case)
        result = original(case, memory, regs, device, offsets)
        independent_checks(case, regs, offsets, result)
        if case.get('provider') == 'pixel-return':
            oracle_require((result['status'], result['continuation']) ==
                           (7, case['changed_target']),
                           case['name'] + ': changed pixel RET boundary differs')
        else:
            oracle_require((result['status'], result['continuation']) ==
                           (0, CONTINUATION),
                           case['name'] + ': normal stop boundary differs')
        own_sites = {address for source, address in result['sites']
                     if source == 'main' and address in OWN_INS}
        own_edges = {(src, dst) for source, src, dst in result['edges']
                     if source == 'main' and src in OWN_INS}
        covered.update(own_sites)
        edges.update(own_edges)
        rows.append(dict(name=case['name'], sites=sorted(own_sites),
                         edges=[list(edge) for edge in sorted(own_edges)],
                         status=result['status'], continuation=result['continuation'],
                         events=len(result['events']), steps=result['steps']))
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'state400 original misses sites {sorted(set(OWN_INS) - covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'state400 edge union differs: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')
    oracle_require(before == input_hashes(),
                   'state400 inputs changed during original-only campaign')
    print(f'PASS entity state400 original: {len(rows)} fixtures, '
          f'{len(covered)} sites/{len(edges)} owned edges, '
          f'{sum(row["events"] for row in rows)} events; bounded original only',
          flush=True)
    return rows, edges


def worker(directory, before_path):
    import json
    before = json.loads(Path(before_path).read_text(encoding='utf-8'))
    rows_original, _ = original_campaign(before)
    specs = cases()
    baseline = Native(directory)
    rows, sites, edges, integrated, event_count, step_count = [], set(), set(), set(), 0, 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            integrated.update(row['integrated_sites'])
            event_count += row['event_count']
            step_count += row['steps']
        gc.collect()
    oracle_require(sites == set(OWN_INS),
                   f'state400 native campaign misses sites {sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == OWN_EDGES,
                   f'state400 native edge union differs: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')

    witnesses = {
        1: 'first-store-changes-second-pair-byte',
        2: 'unknown-signed-minus-one-wrap',
        3: 'pixel-return-live-other-continuation',
        4: 'live-row-pitch-between-second-and-third',
        5: 'three-clear-all-increments',
        6: 'transition-callback-read-after-overlap-store',
        7: 'unknown-signed-negative-below-height',
        8: 'two-clear-all-increments',
    }
    mutations = []
    by_name = {case['name']: case for case in specs}
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'entity state400 mutation {mutation} survived {name}')
        gc.collect()

    oracle_require(len(mutations) == 8, 'state400 mutation witnesses incomplete')
    oracle_require(before == input_hashes(),
                   'state400 input hashes changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
        translated_code_bytes=197, instruction_sites=66, own_branch_edges=27,
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        integrated_main_instruction_addresses=sorted(integrated),
        total_bus_events=event_count, original_code_hook_steps=step_count,
        cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                    continuation=row['continuation'], sites=row['sites'],
                    edges=row['edges'], event_count=row['event_count'], steps=row['steps'])
               for row in rows],
        original_only_case_count=len(rows_original), input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='Sparse state-0400 parent at 2A6D..2B34 with UNKNOWN bytes '
               '2ABD/2ADB/2AEB excluded; actual 5DC6 pixel CALL/RET frames, '
               '1FE8 interaction finish and direct 20E2 inactive path. Covers '
               'unchecked live DS pair indexing, first-byte-before-second-read '
               'aliasing, signed CBW delta, all 1/2/3 probe branches, live row '
               'pitch and callback reads, signed B4 threshold, VGA-backed samples, '
               'full RAM/register/defined-FLAGS and ordered bus comparison. '
               'The pair-table extent remains unresolved; no gameplay claim.'))
    print(f'PASS entity state400: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {event_count} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        BUILD.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='entity-state400-original-',
                                        parent=BUILD) as directory:
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                        check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        import json
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, edges = original_campaign(before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
            known_code_bytes=197, instruction_sites=66, own_branch_edges=27,
            case_count=len(rows), executed_instruction_addresses=sorted(
                {address for row in rows for address in row['sites']}),
            branch_edges=[list(edge) for edge in sorted(edges)],
            input_hashes=before,
            domain='Sparse original-only state-0400 cases; unknown bytes excluded; no native comparison'))
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[2] + '/input-hashes.json')
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_state400.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state400-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', directory], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
