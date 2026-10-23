"""Bounded original-versus-C checks for the 21B0 state-0004 handler."""
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

SIZE = 1 << 20
MASK = SIZE - 1
ENTRY, END = 0x21B0, 0x22DF
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9), (0x2148, 0x2169))
CONTINUATION = 0x1FEB
DATA_SEGMENT = 0x19B9
TABLE = 0x547C
ROW_PITCH = 0x0004
ALL_FLAGS = interactions.FLAGS
LOGIC_FLAGS = ALL_FLAGS & ~0x0010
MAX_INSTRUCTIONS, MAX_EVENTS = 2000, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state4-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state4-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
PIXEL_INS = {i.address: i for i in MD.disasm(IMAGE[PIXEL_ENTRY:PIXEL_RET + 1], PIXEL_ENTRY)}
FINISH_INS = {
    i.address: i
    for start, end in FINISH_SPANS
    for i in MD.disasm(IMAGE[start:end], start)
}
INTERACTION_INS = interactions.MAIN_INS
INTEGRATED_INS = dict(OWN_INS)
INTEGRATED_INS.update(PIXEL_INS)
INTEGRATED_INS.update(FINISH_INS)
INTEGRATED_INS.update(INTERACTION_INS)


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


class NativeMismatch(AssertionError):
    """Only a completed original/native comparison can credit a mutant."""


class OracleFailure(AssertionError):
    """The original/provider did not complete within its declared boundary."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return ((segment & 0xFFFF) * 16 + (offset & 0xFFFF)) & MASK


def read8(memory, segment, offset):
    return memory[physical(segment, offset)]


def read16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def write8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def write16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not ins.group(capstone.CS_GRP_JUMP):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


OWN_EDGES = branch_edges(OWN_INS)


def cases():
    """Focused thresholds, probe edges, aliases, callbacks and return seams."""
    rows = [
        dict(name='cadence-three-wrap', cadence=3, threshold=0x10, gate25=0,
             y=0x00B3, samples=(0, 0, 0)),
        dict(name='threshold-inclusive-10', threshold=0x10, gate25=0),
        dict(name='threshold-exclusive-11', threshold=0x11, gate25=1),
        dict(name='gate25-zero-to-pixel', threshold=0x11, gate25=0),
        dict(name='gate25-nonzero-transition-slot-c', threshold=0x11,
             gate25=1, slot_c=0xA5C3),
        dict(name='first-empty-stops-at-b4', threshold=0x10, gate25=0,
             y=0x00B3, samples=(0, 0, 0)),
        dict(name='first-empty-probes-second', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 0, 0)),
        dict(name='second-empty-stops-at-b4', threshold=0x10, gate25=0,
             y=0x00B2, samples=(0, 0, 0)),
        dict(name='third-empty-interaction', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 0, 0), record_bits=0xFFFF),
        dict(name='third-empty-mark-at-b4', threshold=0x10, gate25=0,
             y=0x00B1, samples=(0, 0, 0)),
        dict(name='first-occupied-stable', threshold=0x10, gate25=0,
             y=0x0020, samples=(1, 0, 0)),
        dict(name='second-occupied-stable', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 1, 0)),
        dict(name='third-occupied-stable', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 0, 1)),
        dict(name='occupied-threshold-inclusive-3c', threshold=0x3C,
             gate25=0, y=0x0020, samples=(1, 0, 0)),
        dict(name='occupied-threshold-transition-3d', threshold=0x3D,
             gate25=0, y=0x0020, samples=(1, 0, 0), slot0=0xCC21),
        dict(name='sound-gate-disabled', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0),
        dict(name='sound-options-clear', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0xFF, options=0),
        dict(name='sound-adlib-command-four', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0xFF, options=3,
             driver='adlib'),
        dict(name='sound-tandy-command-four', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0xFF, options=3,
             driver='tandysnd'),
        dict(name='sound-unbound-vector', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0xFF, options=3,
             sound_vector=(0x0200, 0x7000)),
        dict(name='sound-unbound-binding', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0xFF, options=3,
             sound_binding=False),
        dict(name='sound-changed-iret', threshold=0x40, gate25=0,
             y=0x0020, samples=(1, 0, 0), enabled=0xFF, options=3,
             provider='sound-interrupt-return', provider_return=0x3456),
        dict(name='signed-bp-negative-after-inc', threshold=0x10, gate25=0,
             y=0xFFFE, samples=(0, 0, 0)),
        dict(name='signed-bp-sf-of-overflow', threshold=0x10, gate25=0,
             y=0x8000, samples=(0, 0, 0)),
        dict(name='third-empty-add-byte-wrap', threshold=0xFD, gate25=0,
             y=0x0020, samples=(0, 0, 0), provider='plus23-on-first-pixel'),
        dict(name='live-row-pitch-provider', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 1, 0), provider='pitch-on-first-row-read',
             pitch=0x0050, pitch_after=0x0070),
        dict(name='callback-slot-zero-live', threshold=0x3D, gate25=0,
             y=0x0020, samples=(1, 0, 0), slot0=0x3210),
        dict(name='callback-slot-c-live', threshold=0x11, gate25=1,
             slot_c=0x7654),
        dict(name='pixel-call-return-overwrite', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 0, 0), provider='pixel-return',
             changed_target=0x4567),
        dict(name='data-and-stack-record-alias', threshold=0x10, gate25=0,
             y=0x0040, samples=(0, 0, 0), ds=DATA_SEGMENT,
             ss=DATA_SEGMENT, si=0x6000, sp=0x6004, dx=0x0001),
        dict(name='stack-physical-word-wrap', threshold=0x10, gate25=0,
             y=0x00B3, samples=(0, 0, 0), ss=0xFFFF, sp=0x0011),
        dict(name='record-physical-word-wrap', threshold=0x11, gate25=1,
             ds=0xFFFF, si=0x000F),
        dict(name='df-clear-vga-plane', threshold=0x10, gate25=0,
             y=0x00B3, samples=(0, 0, 0), vga=True, ss=0x9FFF, sp=0xD000),
        dict(name='df-set-ordinary-ram', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 1, 0), df=True),
        dict(name='entry-flags-high-defined', threshold=0x10, gate25=0,
             y=0x0020, samples=(0, 0, 0), flags=0x7ED7),
        dict(name='random-poisoned-nonalias', threshold=0x11, gate25=1,
             poison=True, seed=0x4D31),
    ]
    oracle_require(32 <= len(rows) <= 40,
                   'state4 focused fixture count changed unexpectedly')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x21B0 + index * 31)
    return rows


def pixel_plan(case, memory, regs):
    """Project the real CALL/PUSH aliases before deriving sample locations."""
    projected = bytearray(memory)
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']
    call_sp = (sp - 2) & 0xFFFF
    write16(projected, ss, call_sp, 0x2205)
    child_sp = (call_sp - 2) & 0xFFFF
    write16(projected, ss, child_sp, regs['dx'])
    x = read16(projected, ds, si)
    y = read16(projected, ds, (si + 2) & 0xFFFF)
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    product = (row * 0xD0) & 0xFFFF
    table_offset = (TABLE + (x & 7)) & 0xFFFF
    mask = read8(projected, ds, table_offset)
    start = (product + (x >> 3) + 0x4A40) & 0xFFFF
    pitch = case.get('pitch', 0x0050) & 0xFFFF
    return dict(x=x, y=y, row=row, product=product, table_offset=table_offset,
                mask=mask, start=start, pitch=pitch,
                call_sp=call_sp, child_sp=child_sp)


def setup(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('x', 0x0020)
    template.setdefault('y', 0x0020)
    template.setdefault('sample', 0)
    template.setdefault('second_sample', 0)
    template.setdefault('record_bits', 0xFFFF)
    template.setdefault('enabled', 0)
    template.setdefault('options', 0)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('sp', 0xD000)
    template.setdefault('driver', 'adlib')
    template.setdefault('slot2e', case.get('slot0', 0x6170))
    raw_flags = case.get('flags', 0x0ED7)
    # Entry admits documented flags and excludes TF; DF is varied explicitly.
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    template['flags'] = flags
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(template)
    regs['ip'] = ENTRY
    regs['cs'] = template['load']
    regs['ds'] = template['ds']
    regs['ss'] = template['ss']
    regs['si'] = template.get('si', regs['si'])
    regs['sp'] = template['sp']
    regs['flags'] = flags

    ds, si = regs['ds'], regs['si']
    write8(memory, ds, si + 0x23, case.get('threshold', 0x10))
    write8(memory, ds, si + 0x25, case.get('gate25', 0))
    write8(memory, ds, si + 0x28, case.get('cadence', 2))
    write8(memory, ds, si + 0x24, case.get('entity_flags', 0xFF))
    write16(memory, ds, ROW_PITCH, case.get('pitch', 0x0050))
    write16(memory, ds, 0x3A, case.get('slot_c', 0x6C42))
    # The pinned table is static data at 09A9:547C; noncanonical DS fixtures
    # receive the same live bytes without changing code or the pinned image.
    if ds != DATA_SEGMENT:
        for index, value in enumerate(bytes.fromhex('80 40 20 10 08 04 02 01')):
            write8(memory, ds, TABLE + index, value)
    oracle_require(bytes(read8(memory, ds, TABLE + i) for i in range(8)) ==
                   bytes.fromhex('80 40 20 10 08 04 02 01'),
                   case['name'] + ': pinned live pixel-mask table differs')

    plan = pixel_plan(case, memory, regs)
    sample_flags = tuple(case.get('samples', (0, 0, 0)))
    if len(sample_flags) != 3:
        raise OracleFailure(case['name'] + ': pixel sample vector must have three entries')
    addresses = [plan['start']]
    pitch = plan['pitch']
    addresses.append((addresses[-1] + pitch) & 0xFFFF)
    addresses.append((addresses[-1] + pitch) & 0xFFFF)
    if case.get('vga'):
        oracle_require(device is not None, case['name'] + ': VGA fixture lacks device')
        device.seq[4] = 0x06
        device.seq[2] = 0x01
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[4] = 0
        device.gc[5] = 0
        device.gc[6] = 0x05
        device.gc[8] = 0xFF
        for index, occupied in zip(addresses, sample_flags):
            device.planes[0][index] = plan['mask'] if occupied else 0
    else:
        for index, occupied in zip(addresses, sample_flags):
            memory[(VGA_BASE + index) & MASK] = plan['mask'] if occupied else 0

    # Keep the outer caller word deterministic. The handler returns at 1FEB;
    # this word is not consumed by the scoped boundary.
    write16(memory, regs['ss'], regs['sp'], case.get('outer_return', 0x7A5C))
    if case.get('provider') == 'pixel-return':
        oracle_require((regs['ss'], regs['sp']) != (regs['ds'], regs['si']),
                       case['name'] + ': provider fixture unexpectedly aliases the record')
    return memory, regs, device, pc_binding, sound_binding, plan


class State4Access(interactions.Access):
    """Bounded live providers for the pixel RET, row pitch and +23 RMW."""
    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.plan = None
        self.pitch_high = physical(regs['ds'], ROW_PITCH + 1)
        self.table = physical(regs['ds'], TABLE + (case.get('x', 0x20) & 7))
        self.pixel_addresses = set()
        self.pixel_count = 0
        self.native = False
        self.pending = []

    def modify_word(self, segment, offset, value):
        address = physical(segment, offset)
        self.store(address, value)
        self.store(address + 1, value >> 8)

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        case = self.case
        address &= MASK
        if kind == 'read' and VGA_BASE <= address < VGA_END:
            self.pixel_count += 1
            if case.get('provider') == 'plus23-on-first-pixel' and 'plus23' not in self.used:
                self.store(physical(self.regs['ds'], self.regs['si'] + 0x23), 0xFD)
                self.used.add('plus23')
        if (kind == 'read' and address == self.pitch_high and
                case.get('provider') == 'pitch-on-first-row-read' and
                'pitch' not in self.used):
            if self.native:
                self.apply_pitch_provider()
            else:
                self.pending.append('pitch')
        if kind == 'read' and address == self.table and case.get('provider') == 'pixel-return' and 'pixel-ret' not in self.used:
            self.modify_word(self.regs['ss'], self.regs['sp'] - 2,
                             case.get('changed_target', 0x4567))
            self.used.add('pixel-ret')
        return result

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for name in pending:
            if name == 'pitch':
                self.apply_pitch_provider()

    def apply_pitch_provider(self):
        pitch = self.case.get('pitch_after', 0x0070) & 0xFFFF
        self.modify_word(self.regs['ds'], ROW_PITCH, pitch)
        self.used.add('pitch')


def own_main_map():
    return INTEGRATED_INS


def original(case, memory, regs, device, entry_flag_mask=ALL_FLAGS):
    ret_map = {PIXEL_RET: (0x2205, 7)}
    for address, ins in INTERACTION_INS.items():
        if ins.mnemonic.lower() == 'ret':
            ret_map[address] = (CONTINUATION, 5)
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=entry_flag_mask,
        main_instructions=own_main_map(),
        main_ret_continuations=ret_map,
        stop_offsets={CONTINUATION: 0},
        access_factory=State4Access,
        instruction_limit=MAX_INSTRUCTIONS)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State4Access(case, memory, regs, device)
        self.access.native = True

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                try:
                    os.write(2, (f'native state4 read callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                try:
                    os.write(2, (f'native state4 write callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def out(_context, port, value, flags):
            try:
                os.write(2, (f'unexpected state4 OUT {port:04X}={value:04X}/{flags:04X}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state4-m{mutation}.dll',
                     mutation, 'entity_state4')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state4_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state4_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        native_bus = NativeBus(case, memory, initial_regs, device)
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
            state = interactions.Regs(**initial_regs)
            status = self.adapter(ram, ct.byref(state), pc_ptr, sound_ptr,
                                  ct.byref(native_bus.bus))
            state = {name: getattr(state, name) for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=native_bus.access.events,
                    providers=set(native_bus.access.used), status=status,
                    continuation=state['ip'])


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual.state() == expected.state(), label + ': VGA plane/register/latch state differs')
    actual_trace = [(e[0], e[1], e[2]) for e in actual.trace]
    expected_trace = [(e[0], e[1], e[2]) for e in expected.trace]
    require(actual_trace == expected_trace, label + ': VGA ordered trace differs')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered memory event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} flags {got[3]:04X}/{want[3]:04X} under {want[4]:04X}')


def independent_checks(case, initial, regs, plan, oracle):
    label = case['name']
    ds, si = regs['ds'], regs['si']
    if case['name'] == 'gate25-nonzero-transition-slot-c':
        oracle_require(read16(oracle['memory'], ds, si + 0x14) == 0xA5C3,
                       label + ': +0C callback slot was not copied')
        oracle_require(read16(oracle['memory'], ds, si + 0x08) == 0x0400,
                       label + ': +23 transition did not write first state word')
    if case['name'] == 'callback-slot-zero-live':
        oracle_require(read16(oracle['memory'], ds, si + 0x14) == 0x3210,
                       label + ': stable occupied path did not use callback slot zero')
    if case['name'] == 'third-empty-add-byte-wrap':
        oracle_require(read8(oracle['memory'], ds, si + 0x23) == 0x00,
                       label + ': third clear probe did not wrap +23 by three')
        oracle_require(read16(oracle['memory'], ds, si + 2) == ((case['y'] + 3) & 0xFFFF),
                       label + ': third clear probe did not store incremented Y')
    if case['name'] == 'first-empty-stops-at-b4':
        oracle_require(read16(oracle['memory'], ds, si + 2) == case['y'],
                       label + ': early clear-probe path unexpectedly stored Y')
    if case.get('provider'):
        provider_key = {'sound-interrupt-return': 'sound',
                        'pixel-return': 'pixel-ret',
                        'pitch-on-first-row-read': 'pitch',
                        'plus23-on-first-pixel': 'plus23'}[case['provider']]
        oracle_require(provider_key in oracle['used'],
                       label + ': selected live provider was not observed')
    if case.get('provider') == 'pixel-return':
        oracle_require((oracle['status'], oracle['continuation']) == (7, case['changed_target']),
                       label + ': actual pixel RET did not stop at changed target')
    if case.get('provider') == 'sound-interrupt-return':
        oracle_require(oracle['status'] == 4 and oracle['continuation'] == case['provider_return'],
                       label + ': sound IRET did not expose changed return')
    if case['name'] == 'signed-bp-negative-after-inc':
        oracle_require(('main', 0x2214, 0x2219) in oracle['edges'],
                       label + ': signed JL did not take the negative BP edge')


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding, plan = setup(case)
    oracle = original(case, bytearray(initial), dict(regs), copy.deepcopy(device),
                      entry_flag_mask=ALL_FLAGS)
    independent_checks(case, initial, regs, plan, oracle)
    actual = native.run(case, initial, regs, device, pc_binding, sound_binding,
                        core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == oracle['status'],
            f'{label}: status {actual["status"]}/{oracle["status"]}')
    require(actual['continuation'] == oracle['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/{oracle["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            mask = oracle['flag_mask']
            require(((actual['regs'][name] ^ oracle['regs'][name]) & mask) == 0,
                    f'{label}: flags {actual["regs"][name]:04X}/'
                    f'{oracle["regs"][name]:04X} under {mask:04X}')
        else:
            require(actual['regs'][name] == oracle['regs'][name],
                    f'{label}: {name} {actual["regs"][name]:04X}/{oracle["regs"][name]:04X}')
    require(actual['memory'] == oracle['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['used'],
            f'{label}: provider transitions differ {actual["providers"]}/{oracle["used"]}')
    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target) for source, source_ip, target in oracle['edges']
                 if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(address for source, address in oracle['sites']
                                        if source == 'main'),
                driver=case.get('driver', 'adlib'),
                driver_sites=sorted(address for source, address in oracle['sites']
                                    if source == 'sound'),
                event_count=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'src/game_code.asm', 'src/entity_graphics.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/toolchain-lock.json',
        'c/entity_state4.c', 'c/entity_state4.h',
        'c/entity_finish.c', 'c/entity_finish.h', 'c/entity_pixel.c', 'c/entity_pixel.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/pcspeaker_sym.h', 'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/entity_state4.py', 'tests/entity_interactions.py', 'tests/entity_finish.py',
        'tests/entity_zero_state.py', 'tests/pcspeaker_dispatch.py',
        'tests/sound_latches.py', 'tests/minimap_vga.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/common.py', 'tools/resources.py', 'tools/unpack.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(len(OWN_INS) == 87 and sum(i.size for i in OWN_INS.values()) == 303,
                   'state4 byte/site identity changed')
    oracle_require(len(OWN_EDGES) == 29, 'state4 static branch-edge accounting changed')
    expected_image = 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e'
    oracle_require(sha(IMAGE) == expected_image, 'pinned static image hash changed')
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
                   f'own instruction-site coverage {len(all_sites)}/{len(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'own branch-edge coverage {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')

    witnesses = {
        1: 'cadence-three-wrap',
        2: 'threshold-exclusive-11',
        3: 'gate25-nonzero-transition-slot-c',
        4: 'signed-bp-negative-after-inc',
        5: 'third-empty-add-byte-wrap',
        6: 'gate25-nonzero-transition-slot-c',
        7: 'third-empty-add-byte-wrap',
        8: 'pixel-call-return-overwrite',
    }
    mutations = []
    for mutation, case_name in witnesses.items():
        variant = Native(directory, mutation)
        case = next(row for row in specs if row['name'] == case_name)
        try:
            compare_case(variant, case, core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=case_name,
                                  mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'mutant {mutation} survived completed witness {case_name}')
        gc.collect()
    oracle_require(len(mutations) == 8, 'state4 mutation witnesses incomplete')
    oracle_require(before == input_hashes(), 'state4 campaign inputs changed during execution')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(specs),
                  mutation_count=len(mutations), mutations=mutations,
                  executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  translated_code_bytes=303, instruction_sites=87,
                  own_branch_edges=29, integrated_site_count=len(set().union(
                      *(set(row['integrated_sites']) for row in rows))),
                  driver_instruction_addresses={
                      driver: sorted(set().union(*(
                          set(row['driver_sites']) for row in rows
                          if row['driver'] == driver)))
                      for driver in ('adlib', 'tandysnd')},
                  core_adapter_cases=len(rows), event_count=total_events,
                  cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                              continuation=row['continuation'], sites=row['sites'],
                              edges=row['edges'], event_count=row['event_count'],
                              steps=row['steps']) for row in rows],
                  limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                              original_instructions=MAX_INSTRUCTIONS, ordered_events=MAX_EVENTS),
                  input_hashes=before,
                  domain='21B0..22DE state-0004 original and native core/adapter; '
                         'live DS record and stack aliases; 5DC6 pixel CALL/RET; '
                         'shared 1FE8/20E2 finishes and 2EC0 interaction child; '
                         'INT 61h command 0408 with pinned AdLib/Tandy setter paths; '
                         '1 MiB RAM, all registers, defined flags, ordered accesses and VGA state.')
    write_json(REPORT, report)
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
                  case_count=len(specs), executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  input_hashes=before, c_coverage_claimed=False))
    print(f'PASS entity state4: {len(specs)} cases x core/adapter, 87 sites, '
          f'29 edges, {total_events} events, 8 completed mutants', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    ORIGINAL_REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state4-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit('usage: entity_state4.py [--worker DLL_DIRECTORY]')
