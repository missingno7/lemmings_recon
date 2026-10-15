"""Bounded original-versus-C checks for the 23BF state-0008 handler."""
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
ENTRY, END = 0x23BF, 0x23F3
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x2148, 0x2169))
CONTINUATION = 0x1FEB
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
TABLE, ROW_PITCH = 0x547C, 0x0004
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
ALL_FLAGS = interactions.FLAGS
MAX_INSTRUCTIONS, MAX_EVENTS = 1200, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state8-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state8-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
PIXEL_INS = {i.address: i for i in MD.disasm(
    IMAGE[PIXEL_ENTRY:PIXEL_RET + 1], PIXEL_ENTRY)}
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
    """Only a completed original/native mismatch can credit a mutant."""


class OracleFailure(AssertionError):
    """The original/provider failed to reach a declared bounded boundary."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


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


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


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
    """Exercise both probes, reset/flag effects, child frames and live aliases."""
    rows = [
        dict(name='first-probe-clear-second-occupied', x=0x0020, y=0x0040,
             samples=(0, 1), state_word=0x0018, cadence=5),
        dict(name='second-probe-clear', x=0x0029, y=0x0040,
             samples=(1, 0), state_word=0x0088, cadence=9),
        dict(name='both-probes-occupied', x=0x0030, y=0x0042,
             samples=(1, 1), state_word=0x0018, cadence=6),
        dict(name='height-clamp-signed-edge', x=0x0031, y=0x0040,
             samples=(1, 1), state_word=0x0018, height_delta=0xFFCC),
        dict(name='residual-al-zero-occupied', x=0x0020, y=0x0010,
             samples=(1, 0), state_word=0x0008),
        dict(name='live-row-pitch-provider', x=0x0020, y=0x0040,
             samples=(1, 0), provider='pitch-on-first-row-read',
             pitch=0x0050, pitch_after=0x0030, old_pitch_decoy=1),
        dict(name='pixel-return-overwrite', x=0x0020, y=0x0040,
             samples=(1, 1), provider='pixel-return', changed_target=0x4567),
        dict(name='interaction-return-word-alias', x=0x0020, y=0x0040,
             samples=(0, 0), ds=0x5000, ss=0x5000, si=0xCFD3,
             sp=0xD000, state_word=0x0018),
        dict(name='record-and-stack-y-alias', x=0x0020, y=0x0040,
             samples=(0, 1), ds=DATA_SEGMENT, ss=DATA_SEGMENT,
             si=0x6000, sp=0x6004, dx=0x0040),
        dict(name='stack-overwrites-live-mask-table', x=0x0004, y=0x0040,
             samples=(1, 1), ds=DATA_SEGMENT, ss=DATA_SEGMENT,
             si=0x6000, sp=0x5480, dx=0x0080, mask_override=0x0031),
        dict(name='row-pitch-record-alias', x=0x0020, y=0x0040,
             samples=(0, 1), ds=0x3100, si=0x0002, pitch=0x0040),
        dict(name='record-offset-wrap', x=0x0120, y=0x0040,
             samples=(1, 1), ds=0x3100, si=0xFFFE),
        dict(name='record-physical-word-wrap', x=0x0120, y=0x0040,
             samples=(0, 0), ds=0xFFFF, si=0x000F),
        dict(name='stack-physical-word-wrap', x=0x0020, y=0x0040,
             samples=(1, 0), ss=0xFFFF, sp=0x0011),
        dict(name='df-set-vga-probes', x=0x0027, y=0x0040,
             samples=(1, 0), vga=True, df=True, ss=0xA000),
        dict(name='entry-flags-and-rmw-order', x=0x0021, y=0x0040,
             samples=(0, 0), flags=0x0E47, df=False),
        dict(name='pitch-boundary-wrapped-sub', x=0xFFFF, y=0x8000,
             samples=(1, 1), pitch=0xFFF0, height_delta=0x0001,
             flags=0x7ED7),
        dict(name='random-poisoned-ordinary-ram', x=0x1137, y=0x0055,
             samples=(1, 1), poison=True, seed=0x23BF),
    ]
    oracle_require(15 <= len(rows) <= 25,
                   'state8 focused fixture count changed unexpectedly')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x23BF + index * 37)
        row.setdefault('height_delta', 0)
        row.setdefault('state_word', 0xFFFF)
        row.setdefault('cadence', 3)
    return rows


def pixel_plan(case, memory, regs):
    """Project CALL/PUSH aliases and the two live row-pitch reads."""
    projected = bytearray(memory)
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']
    call_sp = (sp - 2) & 0xFFFF
    write16(projected, ss, call_sp, 0x23C2)
    y = read16(projected, ds, (si + 2) & 0xFFFF)
    child_sp = (call_sp - 2) & 0xFFFF
    write16(projected, ss, child_sp, regs['dx'])
    x = read16(projected, ds, si)
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    product = (row * 0x00D0) & 0xFFFF
    table_offset = (TABLE + (x & 7)) & 0xFFFF
    mask = read8(projected, ds, table_offset)
    start = (product + (x >> 3) + 0x4A40) & 0xFFFF

    # Keep the projected buffer at the actual post-child state. Parent probes
    # are simulated separately so a clear first sample cannot gain a
    # speculative second decrement in downstream fixture calculations.
    after_child_y = read16(projected, ds, (si + 2) & 0xFFFF)
    probes = bytearray(projected)
    first_y = (after_child_y - 1) & 0xFFFF
    write16(probes, ds, (si + 2) & 0xFFFF, first_y)
    pitch1 = read16(probes, ds, ROW_PITCH)
    first_probe = (start - pitch1) & 0xFFFF
    if case.get('provider') == 'pitch-on-first-row-read':
        write16(probes, ds, ROW_PITCH, case['pitch_after'])
    second_y = (first_y - 1) & 0xFFFF
    write16(probes, ds, (si + 2) & 0xFFFF, second_y)
    pitch2 = read16(probes, ds, ROW_PITCH)
    second_probe = (first_probe - pitch2) & 0xFFFF
    return dict(x=x, y=y, row=row, product=product, table_offset=table_offset,
                mask=mask, start=start, first_probe=first_probe,
                second_probe=second_probe, pitch1=pitch1, pitch2=pitch2,
                after_child_y=after_child_y, first_y=first_y, second_y=second_y,
                call_sp=call_sp, child_sp=child_sp, projected=projected)


def predicted_interaction_y(case, memory, regs, plan):
    """Compute the Y word visible to 2EC0 after the real finish CALL push."""
    ds, si = regs['ds'], regs['si']
    y = plan['after_child_y']
    first = read8(memory, regs['es'], plan['first_probe']) & plan['mask']
    if first:
        second = read8(memory, regs['es'], plan['second_probe']) & plan['mask']
        candidate = plan['second_y'] if second else (plan['second_y'] + 1) & 0xFFFF
    else:
        candidate = (plan['first_y'] + 1) & 0xFFFF
    delta = read16(plan['projected'], ds, (si + 6) & 0xFFFF)
    summed = (candidate + delta) & 0xFFFF
    final_y = ((9 - delta) & 0xFFFF) if signed16(summed) <= 10 else candidate
    # Finish's real near CALL pushes 1FEB at entry SP-2. Preserve an intentional
    # DS:SI+2 alias so 2EC0 sees the live pushed word rather than a cached Y.
    if (ds == regs['ss'] and
            physical(ds, (si + 2) & 0xFFFF) ==
            physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)):
        return 0x1FEB
    return final_y


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


def setup(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('x', 0x0020)
    template.setdefault('y', 0x0040)
    template.setdefault('sample', 0)
    template.setdefault('second_sample', 0)
    template.setdefault('record_bits', 0)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('sp', 0xD000)
    template.setdefault('es', 0xA000)
    template.setdefault('driver', 'adlib')
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    template['flags'] = flags
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(template)
    regs.update(ip=ENTRY, cs=template['load'], ds=template['ds'],
                es=template['es'], ss=template['ss'], sp=template['sp'],
                flags=flags)
    write16(memory, regs['ss'], regs['sp'], case.get('outer_return', 0x7331))

    ds, si = regs['ds'], regs['si']
    if ds != DATA_SEGMENT:
        for index, value in enumerate(PIXEL_MASKS):
            write8(memory, ds, TABLE + index, value)

    # Set the aliased row-pitch word before the record fields. In the explicit
    # SI=2 case, Y and DS:0004 deliberately begin as the same live word.
    pitch = case.get('pitch', 0x0050) & 0xFFFF
    write16(memory, ds, ROW_PITCH, pitch)
    x = case.get('x', 0x0020) & 0xFFFF
    y = case.get('y', 0x0040) & 0xFFFF
    write16(memory, ds, si, x)
    write16(memory, ds, (si + 2) & 0xFFFF, y)
    write16(memory, ds, (si + 6) & 0xFFFF, case.get('height_delta', 0))
    write16(memory, ds, (si + 8) & 0xFFFF, case.get('state_word', 0xFFFF))
    write8(memory, ds, (si + 0x27) & 0xFFFF, case.get('velocity', 1))
    write8(memory, ds, (si + 0x28) & 0xFFFF, case.get('cadence', 3))

    plan = pixel_plan(case, memory, regs)
    selected_mask = read8(memory, ds, plan['table_offset'])
    expected_mask = case.get('mask_override', PIXEL_MASKS[x & 7])
    oracle_require(selected_mask == expected_mask,
                   case['name'] + ': selected live PixelBitMasks byte differs')
    samples = tuple(case.get('samples', (0, 0)))
    oracle_require(len(samples) == 2,
                   case['name'] + ': exactly two parent probe values are required')
    if device is not None:
        configure_vga(device)
    for offset, occupied in ((plan['first_probe'], samples[0]),
                             (plan['second_probe'], samples[1])):
        value = plan['mask'] if occupied else 0
        if device is not None:
            device.planes[0][offset] = value
        else:
            memory[physical(regs['es'], offset)] = value
    if case.get('old_pitch_decoy'):
        decoy = (plan['first_probe'] - plan['pitch1']) & 0xFFFF
        value = plan['mask']
        if device is not None:
            device.planes[0][decoy] = value
        else:
            memory[physical(regs['es'], decoy)] = value

    # The finish tail calls the 2EC0 interaction body. Seed its first SS map
    # byte from the post-parent Y so the child takes its zero-nibble return,
    # except that the return-word alias fixture intentionally corrupts RET.
    final_y = predicted_interaction_y(case, memory, regs, plan)
    record_delta = read8(memory, ds, (si + 0x27) & 0xFFFF)
    first_map, _ = interactions.map_offsets(x, final_y, record_delta)
    map_address = physical(regs['ss'], first_map)
    if device is not None and VGA_BASE <= map_address < VGA_END:
        device.planes[0][map_address - VGA_BASE] = 0
    else:
        memory[map_address] = 0

    # CALL frames below the preserved caller word may intentionally alias the
    # record or the physical 20-bit wrap.
    return memory, regs, device, pc_binding, sound_binding, plan


class State8Access(interactions.Access):
    """Live row-pitch and actual child-return providers with bounded traces."""
    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        projected = bytearray(memory)
        write16(projected, regs['ss'], regs['sp'] - 2, 0x23C2)
        write16(projected, regs['ss'], regs['sp'] - 4, regs['dx'])
        x = read16(projected, regs['ds'], regs['si'])
        self.table = physical(regs['ds'], TABLE + (x & 7))
        self.pitch_high = physical(regs['ds'], ROW_PITCH + 1)
        self.pixel_call_word = physical(regs['ss'], regs['sp'] - 2)
        self.native = False
        self.pending = []

    def modify_word(self, segment, offset, value):
        address = physical(segment, offset)
        self.store(address, value)
        self.store(address + 1, value >> 8)

    def apply_pitch_provider(self):
        self.modify_word(self.regs['ds'], ROW_PITCH,
                         self.case.get('pitch_after', 0x0030) & 0xFFFF)
        self.used.add('pitch')

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for name in pending:
            if name == 'pitch':
                self.apply_pitch_provider()

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        address &= MASK
        if (kind == 'read' and address == self.pitch_high and
                self.case.get('provider') == 'pitch-on-first-row-read' and
                'pitch' not in self.used):
            if self.native:
                self.apply_pitch_provider()
            else:
                self.pending.append('pitch')
        if (kind == 'read' and address == self.table and
                self.case.get('provider') == 'pixel-return' and
                'pixel-ret' not in self.used):
            self.modify_word(self.regs['ss'], self.regs['sp'] - 2,
                             self.case.get('changed_target', 0x4567))
            self.used.add('pixel-ret')
        return result


def original(case, memory, regs, device):
    ret_map = {PIXEL_RET: (0x23C2, 7)}
    for address, ins in INTERACTION_INS.items():
        if ins.mnemonic.lower() == 'ret':
            ret_map[address] = (CONTINUATION, 5)
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=ALL_FLAGS,
        main_instructions=INTEGRATED_INS,
        main_ret_continuations=ret_map,
        stop_offsets={CONTINUATION: 0},
        access_factory=State8Access,
        instruction_limit=MAX_INSTRUCTIONS)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State8Access(case, memory, regs, device)
        self.access.native = True

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                try:
                    os.write(2, (f'native state8 read callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                try:
                    os.write(2, (f'native state8 write callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def out(_context, port, value, flags):
            try:
                os.write(2, (f'unexpected state8 OUT {port:04X}={value:04X}/{flags:04X}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state8-m{mutation}.dll',
                     mutation, 'entity_state8')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state8_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state8_adapter
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
            registers = interactions.Regs(**initial_regs)
            status = self.adapter(ram, ct.byref(registers), pc_ptr, sound_ptr,
                                  ct.byref(native_bus.bus))
            state = {name: getattr(registers, name) for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=native_bus.access.events,
                    providers=set(native_bus.access.used), status=status,
                    continuation=state['ip'])


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual.state() == expected.state(),
            label + ': VGA plane/register/latch state differs')
    actual_trace = [(event[0], event[1], event[2]) for event in actual.trace]
    expected_trace = [(event[0], event[1], event[2]) for event in expected.trace]
    require(actual_trace == expected_trace, label + ': VGA ordered trace differs')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} flags {got[3]:04X}/{want[3]:04X} '
                f'under {want[4]:04X}')


def independent_checks(case, memory, regs, plan, oracle):
    label = case['name']
    ds, si = regs['ds'], regs['si']
    samples = tuple(case['samples'])
    if case.get('provider') == 'pitch-on-first-row-read':
        oracle_require('pitch' in oracle['used'],
                       label + ': live pitch provider did not fire')
        oracle_require(plan['pitch1'] == case['pitch'] and
                       plan['pitch2'] == case['pitch_after'],
                       label + ': projected pitch reads do not reflect provider order')
    if case.get('provider') == 'pixel-return':
        oracle_require('pixel-ret' in oracle['used'] and
                       (oracle['status'], oracle['continuation']) ==
                       (7, case['changed_target']),
                       label + ': live pixel RET did not stop at its actual target')
    if label == 'first-probe-clear-second-occupied':
        oracle_require(('main', 0x23CE, 0x23E4) in oracle['edges'] and
                       ('main', 0x23DC, 0x23E4) not in oracle['edges'],
                       label + ': first clear probe did not skip the second read')
        oracle_require(read16(oracle['memory'], ds, si + 8) ==
                       (case['state_word'] & 0xFFF7) and
                       read8(oracle['memory'], ds, si + 0x28) == 0,
                       label + ': clear path did not clear bit 3 and reset cadence')
    if label == 'second-probe-clear':
        oracle_require(('main', 0x23CE, 0x23D0) in oracle['edges'] and
                       ('main', 0x23DC, 0x23E4) in oracle['edges'],
                       label + ': second clear-probe path differs')
    if label in ('both-probes-occupied', 'height-clamp-signed-edge'):
        oracle_require(('main', 0x23CE, 0x23D0) in oracle['edges'] and
                       ('main', 0x23DC, 0x23DE) in oracle['edges'],
                       label + ': occupied probes did not reach the second sample')
    if label == 'interaction-return-word-alias':
        oracle_require(oracle['status'] == 5 and oracle['continuation'] != CONTINUATION,
                       label + ': child did not consume the modified finish CALL word')
    if label == 'residual-al-zero-occupied':
        oracle_require(plan['product'] & 0xFF == 0 and samples[0] == 1 and
                       read16(oracle['memory'], ds, si + 2) != case['y'],
                       label + ': occupied sample did not replace residual AL')
    if label == 'height-clamp-signed-edge':
        oracle_require(0x2156 in {address for source, address in oracle['sites']
                                  if source == 'main'},
                       label + ': signed <= 10 clamp edge was not taken')
    if label == 'row-pitch-record-alias':
        oracle_require(regs['si'] == 2 and
                       physical(ds, (si + 2) & 0xFFFF) == physical(ds, ROW_PITCH),
                       label + ': fixture no longer aliases Y and row pitch')


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding, plan = setup(case)
    oracle = original(case, bytearray(initial), dict(regs), copy.deepcopy(device))
    independent_checks(case, initial, regs, plan, oracle)
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
            f'{label}: flags {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {flag_mask:04X}')
    require(actual['memory'] == oracle['memory'],
            label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['used'],
            f'{label}: provider transitions differ '
            f'{actual["providers"]}/{oracle["used"]}')
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
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'src/game_code.asm', 'src/entity_graphics.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/toolchain-lock.json',
        'c/entity_state8.c', 'c/entity_state8.h',
        'c/entity_finish.c', 'c/entity_finish.h', 'c/entity_pixel.c', 'c/entity_pixel.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/pcspeaker_sym.h', 'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/entity_state8.py', 'tests/entity_interactions.py', 'tests/entity_finish.py',
        'tests/entity_pixel.py', 'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/common.py', 'tools/resources.py', 'tools/unpack.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(len(OWN_INS) == 18 and sum(i.size for i in OWN_INS.values()) == 52,
                   'state8 byte/site identity changed')
    oracle_require(len(OWN_EDGES) == 6,
                   f'state8 static branch-edge accounting changed: {sorted(OWN_EDGES)}')
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
                   f'own CFG-edge coverage {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')

    witnesses = {
        1: 'both-probes-occupied',
        2: 'live-row-pitch-provider',
        3: 'residual-al-zero-occupied',
        4: 'first-probe-clear-second-occupied',
        5: 'first-probe-clear-second-occupied',
        6: 'first-probe-clear-second-occupied',
        7: 'entry-flags-and-rmw-order',
        8: 'pixel-return-overwrite',
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
    oracle_require(len(mutations) == 8, 'state8 mutation witnesses incomplete')
    oracle_require(before == input_hashes(), 'state8 campaign inputs changed during execution')
    integrated = set().union(*(set(row['integrated_sites']) for row in rows))
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(specs),
                  mutation_count=len(mutations), mutations=mutations,
                  executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  translated_code_bytes=52, instruction_sites=18, own_branch_edges=6,
                  integrated_site_count=len(integrated), core_adapter_cases=len(rows),
                  event_count=total_events,
                  cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                              continuation=row['continuation'], sites=row['sites'],
                              edges=row['edges'], event_count=row['event_count'],
                              steps=row['steps']) for row in rows],
                  limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                              original_instructions=MAX_INSTRUCTIONS,
                              ordered_events=MAX_EVENTS),
                  input_hashes=before,
                  domain='23BF..23F2 state-0008 original/native core and adapter; '
                         'actual 5DC6 CALL/RET and direct 2148 finish; live row pitch, '
                         'record/stack aliases, VGA reads, 1 MiB RAM, all registers, '
                         'defined flags and ordered memory/device events.')
    write_json(REPORT, report)
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
                  case_count=len(specs), executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  input_hashes=before, c_coverage_claimed=False))
    print(f'PASS entity state8: {len(specs)} cases x core/adapter, 18 sites, '
          f'6 edges, {total_events} events, 8 completed mutants', flush=True)


def original_preflight():
    """Exercise every declared fixture against the bounded original only."""
    before = input_hashes()
    oracle_require(len(OWN_INS) == 18 and sum(i.size for i in OWN_INS.values()) == 52,
                   'state8 byte/site identity changed')
    oracle_require(len(OWN_EDGES) == 6,
                   f'state8 static branch-edge accounting changed: {sorted(OWN_EDGES)}')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned static image hash changed')
    specs = cases()
    all_sites, all_edges = set(), set()
    for case in specs:
        initial, regs, device, _pc, _sound, plan = setup(case)
        result = original(case, bytearray(initial), dict(regs), copy.deepcopy(device))
        independent_checks(case, initial, regs, plan, result)
        all_sites.update(address for source, address in result['sites']
                         if source == 'main' and address in OWN_INS)
        all_edges.update((source_ip, target)
                         for source, source_ip, target in result['edges']
                         if source == 'main' and source_ip in OWN_INS)
        if case['name'] == 'both-probes-occupied':
            oracle_require((result['status'], result['continuation']) == (0, CONTINUATION),
                           'normal finish/interaction return contract changed')
            oracle_require(('main', 0x2F11, 0x2F3A) in result['edges'] and
                           ('main', 0x2F3A) in result['sites'],
                           'zero interaction nibble no longer reaches its RET')
        elif case['name'] == 'pixel-return-overwrite':
            oracle_require((result['status'], result['continuation']) ==
                           (7, case['changed_target']),
                           'actual pixel RET target contract changed')
        elif case['name'] == 'interaction-return-word-alias':
            oracle_require(result['status'] == 5 and
                           result['continuation'] != CONTINUATION,
                           'actual interaction RET overwrite contract changed')
        else:
            oracle_require((result['status'], result['continuation']) == (0, CONTINUATION),
                           case['name'] + ': unexpected original boundary')
        gc.collect()
    oracle_require(all_sites == set(OWN_INS),
                   f'original own-site coverage {len(all_sites)}/{len(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'original own-edge coverage {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')
    oracle_require(before == input_hashes(),
                   'state8 source inputs changed during original-only preflight')
    print(f'PASS original state8 preflight: {len(specs)} fixtures, '
          f'{len(all_sites)} sites, {len(all_edges)} edges; no native code loaded',
          flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 2 and sys.argv[1] == '--original-only':
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    REPORT.unlink(missing_ok=True)
    ORIGINAL_REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state8-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == '--original-worker':
        original_preflight()
    elif len(sys.argv) == 2 and sys.argv[1] == '--original-only':
        main()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit('usage: entity_state8.py [--worker DLL_DIRECTORY]')
