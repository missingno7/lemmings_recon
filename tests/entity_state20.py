"""Bounded original-versus-C checks for the 254F..2636 state-0020 parent."""
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

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END, MAIN_SEG = 0x254F, 0x2637, interactions.MAIN_SEG
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x2148, 0x2169))
CONTINUATION = 0x1FEB
ROW_PITCH, MASK_TABLE = 0x0004, 0x547C
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
MAX_INSTRUCTIONS, MAX_EVENTS = 1200, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state20-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state20-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
PIXEL_INS = {ins.address: ins for ins in
             MD.disasm(IMAGE[PIXEL_ENTRY:PIXEL_RET + 1], PIXEL_ENTRY)}
FINISH_INS = {
    ins.address: ins
    for start, end in FINISH_SPANS
    for ins in MD.disasm(IMAGE[start:end], start)
}
INTERACTION_INS = interactions.MAIN_INS
INTEGRATED_INS = dict(OWN_INS)
INTEGRATED_INS.update(PIXEL_INS)
INTEGRATED_INS.update(FINISH_INS)
INTEGRATED_INS.update(INTERACTION_INS)
INTERACTION_RETS = {address for address, ins in INTERACTION_INS.items()
                    if ins.mnemonic.lower() == 'ret'}


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
    """Only a completed original/native mismatch may credit a mutant."""


class OracleFailure(AssertionError):
    """The original/provider missed a declared boundary or exhausted a bound."""


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


def signed8(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


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
    """Focused branch, alias, pixel, return, VGA, and transition fixtures."""
    rows = [
        # The AND 7 cadence keeps 4 and selects the high-timer path.
        dict(name='cadence-high-sample-occupied', cadence=3, y=0x0040,
             x=0x0020, velocity=0, occupied=True, state_bits=0xFFFF),
        dict(name='cadence-seven-wraps-to-zero', cadence=7, y=0x0040,
             x=0x0020, velocity=0, occupied=False),
        dict(name='cadence-byte-ff-wraps-to-zero', cadence=0xFF, y=0x0040,
             x=0x0020, velocity=0, occupied=False),
        dict(name='cadence-fe-wraps-to-seven', cadence=0xFE, y=0x0040,
             x=0x0020, velocity=0, occupied=False),
        dict(name='high-sample-clear', cadence=4, y=0x0040, x=0x0020,
             velocity=0, occupied=False),
        dict(name='early-unsigned-jna', cadence=4, y=0x000B, x=0x0020,
             velocity=0, occupied=False),
        dict(name='unsigned-add-wrap-to-ten', cadence=4, y=0xFFFF,
             height_delta=0x000C, x=0x0020, velocity=0, occupied=False),
        # DEC yields 8000h; unsigned JNA must be false although signed JLE is true.
        dict(name='unsigned-sign-edge', cadence=4, y=0x8001, x=0x0020,
             velocity=0, occupied=False),
        dict(name='low-sample-occupied', cadence=0, y=0x0040, x=0x0020,
             velocity=0, occupied=True),
        dict(name='low-empty-clamped-by-finish', cadence=2, y=0x0040,
             height_delta=0xFF80, x=0x0020, velocity=0, occupied=False),
        dict(name='low-empty-finish-no-clamp', cadence=0, y=0x0040,
             height_delta=0, x=0x0020, velocity=0, occupied=False),
        dict(name='callback-late-read-alias-and-neg-flags', cadence=4,
             y=0x000B, x=0x0020, velocity=0x80, occupied=False,
             si=0x002A, state_bits=0xFFFF, callback_seed=0x1234),
        dict(name='live-pitch-reread-after-pixel-call', cadence=4,
             y=0x0040, x=0x0020, velocity=0, occupied=True,
             provider='pitch-after-table-read', pitch=0x0010,
             pitch_after=0x0020),
        dict(name='first-pixel-call-return-overwrite', cadence=4,
             y=0x0040, x=0x0020, velocity=0, occupied=False,
             provider='pixel-return', changed_target=0x25F0),
        dict(name='second-pixel-call-return-overwrite', cadence=0,
             y=0x0040, x=0x0020, velocity=0, occupied=False,
             provider='pixel-return', changed_target=0x2579),
        # 12*D0h + 4A40h has low byte zero. MOV AL,[ES:DI] must replace it.
        dict(name='mov-al-replaces-zero-product-low-byte', cadence=4,
             y=0x0011, height_delta=0x0006, x=0, velocity=0, occupied=True),
        # CBW makes FFh a -1 displacement, so the child sees X+1.
        dict(name='signed-velocity-cbw', cadence=4, y=0x0040,
             x=0x0020, velocity=0xFF, occupied=True),
        dict(name='clear-bit20-on-occupied-transition', cadence=4,
             y=0x0040, x=0x0020, velocity=0, occupied=True,
             state_bits=0xFFFF),
        dict(name='planar-vga-parent-read-df-set', cadence=4, y=0x0040,
             x=0x0027, velocity=0, occupied=True, vga=True, df=True),
        # CALL and the child's PUSH DX leave the CALL return word across 20-bit wrap.
        dict(name='physical-stack-word-wrap', cadence=4, y=0x0040,
             x=0x0020, velocity=0, occupied=False, ss=0xFFFF, sp=0x0011),
        # The CALL return overwrites the source X before the pixel child reads it.
        dict(name='live-call-return-overwrites-record-x', cadence=4,
             y=0x0040, x=0x0020, velocity=0, occupied=False,
             ds=0x5000, ss=0x5000, si=0x6002, sp=0x6004),
        # The pixel child caches Y before PUSH DX overwrites this aliased word.
        dict(name='pixel-reads-y-before-dx-push-alias', cadence=4,
             y=0x0040, x=0x0020, velocity=0, occupied=False,
             ds=0x5000, ss=0x5000, si=0x6000, sp=0x6006),
        dict(name='df-clear-kept-through-empty-transition', cadence=0,
             y=0x0040, x=0x0020, velocity=0, occupied=False, df=False,
             saved_callback=0xBEEF),
        dict(name='pitch-and-source-offset-wrap', cadence=4,
             y=0x7FFF, x=0xFFFF, velocity=0, occupied=False,
             pitch=0xFFF0, flags=0x7ED7),
    ]
    oracle_require(21 <= len(rows) <= 30,
                   f'state20 focused fixture count changed: {len(rows)}')
    for index, case in enumerate(rows):
        case.setdefault('seed', 0x254F + index * 71)
        case.setdefault('height_delta', 0)
        case.setdefault('state_bits', 0xFFFF)
        case.setdefault('pitch', 0x0050)
        case.setdefault('df', False)
        case.setdefault('saved_callback', 0xA55A)
        case.setdefault('callback_seed', 0x6170)
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


def project_pixel(case, memory, regs, new_cadence):
    """Project the parent's live writes and real CALL/PUSH before child reads."""
    projected = bytearray(memory)
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']
    y = read16(projected, ds, (si + 2) & 0xFFFF)
    x = read16(projected, ds, si)
    if new_cadence <= 3:
        child_y = (y - 7 - new_cadence) & 0xFFFF
        write16(projected, ds, (si + 2) & 0xFFFF, child_y)
        call_return = 0x25F0
        high_path = False
    else:
        child_y = (y - 1) & 0xFFFF
        write16(projected, ds, (si + 2) & 0xFFFF, child_y)
        x = (x - signed8(case['velocity'])) & 0xFFFF
        write16(projected, ds, si, x)
        call_return = 0x2579
        high_path = True
    # The actual CALL writes first; the pixel child then PUSHes DX before it
    # rereads SI. Both words can alias DS:SI or the selected mask-table byte.
    write16(projected, ss, (sp - 2) & 0xFFFF, call_return)
    # 5DCB reads Y before 5DD5 pushes DX; X is read after that push.
    child_y = read16(projected, ds, (si + 2) & 0xFFFF)
    write16(projected, ss, (sp - 4) & 0xFFFF, regs['dx'])
    child_x = read16(projected, ds, si)
    row = (child_y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    product = (row * 0x00D0) & 0xFFFF
    table_offset = (MASK_TABLE + (child_x & 7)) & 0xFFFF
    mask = read8(projected, ds, table_offset)
    raw_di = (product + (child_x >> 3) + 0x4A40) & 0xFFFF
    live_pitch = case.get('pitch_after', case.get('pitch', 0x0050))
    probe = (raw_di - ((live_pitch << 3) if high_path else 0)) & 0xFFFF
    return dict(child_x=child_x, child_y=child_y, row=row, product=product,
                table_offset=table_offset, mask=mask, raw_di=raw_di,
                probe=probe, call_return=call_return, high_path=high_path,
                projected=projected)


def setup(case):
    template = dict(case)
    template.update(vga=False, load=case.get('load', MAIN_SEG),
                    x=case.get('x', 0x0020), y=case.get('y', 0x0040),
                    record_delta=case.get('velocity', 0),
                    enabled=0, options=0, sample=0, second_sample=0)
    template.setdefault('si', 0x4000)
    template.setdefault('ss', 0x5000)
    template.setdefault('sp', 0xD000)
    template.setdefault('ds', 0x3800)
    template.setdefault('es', 0xA000)
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if case.get('df', False) else (flags & ~0x0400)
    template['flags'] = flags
    memory, regs, _device, pc_binding, sound_binding, _ = interactions.setup(template)
    regs.update(ip=ENTRY, cs=template['load'], ds=template['ds'],
                es=template['es'], ss=template['ss'], sp=template['sp'],
                si=template['si'], flags=flags)
    write16(memory, regs['ss'], regs['sp'], case.get('outer_return', 0x7331))

    ds, si = regs['ds'], regs['si']
    for index, value in enumerate(PIXEL_MASKS):
        write8(memory, ds, MASK_TABLE + index, value)
    write16(memory, ds, ROW_PITCH, case.get('pitch', 0x0050))
    write16(memory, ds, si, case.get('x', 0x0020))
    write16(memory, ds, (si + 2) & 0xFFFF, case.get('y', 0x0040))
    write16(memory, ds, (si + 4) & 0xFFFF, case.get('callback_seed', 0x6170))
    write16(memory, ds, (si + 6) & 0xFFFF, case.get('height_delta', 0))
    write16(memory, ds, (si + 8) & 0xFFFF, case.get('state_bits', 0xFFFF))
    write16(memory, ds, (si + 0x14) & 0xFFFF,
            case.get('saved_callback', 0xA55A))
    write8(memory, ds, (si + 0x23) & 0xFFFF, 0x5A)
    write8(memory, ds, (si + 0x24) & 0xFFFF, 0xFF)
    write8(memory, ds, (si + 0x27) & 0xFFFF, case.get('velocity', 0))
    write8(memory, ds, (si + 0x28) & 0xFFFF, case.get('cadence', 0))

    new_cadence = (case.get('cadence', 0) + 1) & 7
    low_timer = new_cadence <= 3
    if not low_timer:
        y_after_dec = (case.get('y', 0x0040) - 1) & 0xFFFF
        compare = (y_after_dec + case.get('height_delta', 0)) & 0xFFFF
        early_transition = compare <= 0x000A
    else:
        early_transition = False
    if low_timer or not early_transition:
        plan = project_pixel(case, memory, regs, new_cadence)
        device = MinimapVga(0x2020 ^ case.get('seed', 0), read_map=0) \
            if case.get('vga') else None
        if device is not None:
            configure_vga(device)
        pixel = plan['mask'] if case.get('occupied', False) else 0
        sample_address = physical(regs['es'], plan['probe'])
        if device is not None:
            oracle_require(VGA_BASE <= sample_address < VGA_END,
                           case['name'] + ': planned sample escaped VGA aperture')
            device.planes[0][sample_address - VGA_BASE] = pixel
        else:
            memory[sample_address] = pixel
        if case.get('provider') == 'pitch-after-table-read':
            decoy = (plan['raw_di'] - (case['pitch'] << 3)) & 0xFFFF
            decoy_address = physical(regs['es'], decoy)
            if device is not None:
                device.planes[0][decoy_address - VGA_BASE] = 0
            else:
                memory[decoy_address] = 0
    else:
        plan, device = None, None

    return memory, regs, device, pc_binding, sound_binding, plan


class State20Access(interactions.Access):
    """Bounded live providers for row-pitch changes and actual CALL returns."""
    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.native = False

    def apply_pitch(self):
        self.modify_word(self.regs['ds'], ROW_PITCH,
                         self.case['pitch_after'] & 0xFFFF)
        self.used.add('pitch')

    def apply_return(self):
        self.modify_word(self.regs['ss'], (self.regs['sp'] - 2) & 0xFFFF,
                         self.case.get('changed_target', 0x4567))
        self.used.add('pixel-ret')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        if (kind == 'read' and
                physical(self.regs['ds'], MASK_TABLE) <= (address & MASK) <=
                physical(self.regs['ds'], MASK_TABLE + 7)):
            if (self.case.get('provider') == 'pitch-after-table-read' and
                    'pitch' not in self.used):
                self.apply_pitch()
            if (self.case.get('provider') == 'pixel-return' and
                    'pixel-ret' not in self.used):
                self.apply_return()
        return result


def original(case, memory, regs, device):
    call_returns = {
        0x2576: ({PIXEL_RET}, 7),
        0x25ED: ({PIXEL_RET}, 7),
        0x1FE8: (INTERACTION_RETS, 5),
    }
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=INTEGRATED_INS,
        main_call_returns=call_returns, stop_offsets={CONTINUATION: 0},
        access_factory=State20Access, instruction_limit=MAX_INSTRUCTIONS)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = State20Access(case, memory, regs, device)
        self.access.native = True

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, FLAGS)
            except BaseException as error:
                try:
                    os.write(2, (f'native state20 read callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                try:
                    os.write(2, (f'native state20 write callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def out(_context, port, value, flags):
            try:
                os.write(2, (f'unexpected state20 OUT {port:04X}={value:04X}/{flags:04X}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state20-m{mutation}.dll',
                     mutation, 'entity_state20')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state20_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state20_adapter
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
            call = Call(*(initial_regs[name] for name in
                          ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs',
                           'ds', 'es', 'ss', 'sp', 'flags')))
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
            state = {name: getattr(registers, name)
                     for name in interactions.REG_NAMES}
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
    a_trace = [(event[0], event[1], event[2]) for event in actual.trace]
    e_trace = [(event[0], event[1], event[2]) for event in expected.trace]
    require(a_trace == e_trace, label + ': VGA ordered trace differs')


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
    name = case['name']
    ds, si = regs['ds'], regs['si']
    if case.get('provider') == 'pitch-after-table-read':
        oracle_require('pitch' in oracle['used'],
                       name + ': pitch provider did not run after the pixel lookup')
        oracle_require(read16(oracle['memory'], ds, ROW_PITCH) ==
                       case['pitch_after'], name + ': live pitch word was not changed')
    if case.get('provider') == 'pixel-return':
        oracle_require('pixel-ret' in oracle['used'] and
                       (oracle['status'], oracle['continuation']) ==
                       (7, case['changed_target']),
                       name + ': actual pixel RET did not stop at its live target')
    if name == 'unsigned-sign-edge':
        oracle_require(('main', 0x256C, 0x256E) in oracle['edges'] and
                       ('main', 0x256C, 0x2591) not in oracle['edges'],
                       name + ': JNA must use the unsigned compare at 256C')
    if name == 'callback-late-read-alias-and-neg-flags':
        address = physical(ds, (si + 4) & 0xFFFF)
        events = oracle['events']
        read_indices = [i for i, event in enumerate(events)
                        if event[0] == 'read' and event[1] == address]
        oracle_require(read_indices, name + ': callback slot 002E was not read')
        callback_read = read_indices[-1]
        preceding_writes = [event for event in events[:callback_read]
                            if event[0] == 'write' and event[1] == address]
        oracle_require(preceding_writes and preceding_writes[-1][2] == 0xF8 and
                       events[callback_read][2] == 0xF8,
                       name + ': callback must observe the prior +04=FFF8 store')
        oracle_require(read16(oracle['memory'], ds, (si + 0x14) & 0xFFFF) == 0xFFF8,
                       name + ': live callback value did not reach record +14')
        neg_write = [event for event in events
                     if event[0] == 'write' and
                     event[1] == physical(ds, (si + 0x27) & 0xFFFF)]
        oracle_require(neg_write and
                       (neg_write[-1][3] & 0x08D5) == 0x0881,
                       name + ': MOV [SI+27] did not expose NEG AL result flags')
    if name == 'low-empty-finish-no-clamp':
        oracle_require(read16(oracle['memory'], ds, (si + 0x14) & 0xFFFF) ==
                       case['saved_callback'],
                       name + ': alternate 25FD route unexpectedly rewrote +14')
        oracle_require(('main', 0x2634, 0x2148) in oracle['edges'],
                       name + ': empty probe did not compose the 2148 finish path')
    if name == 'pixel-reads-y-before-dx-push-alias':
        y_address = physical(ds, (si + 2) & 0xFFFF)
        dx_push_address = physical(regs['ss'], (regs['sp'] - 4) & 0xFFFF)
        oracle_require(y_address == dx_push_address,
                       name + ': fixture lost its Y/PUSH DX physical alias')
        push_indices = [i for i, event in enumerate(oracle['events'])
                        if event[0] == 'write' and event[1] == y_address and
                        event[2] == (regs['dx'] & 0xFF)]
        oracle_require(push_indices and any(
            event[0] == 'read' and event[1] == y_address
            for event in oracle['events'][:push_indices[0]]),
            name + ': pixel child did not read Y before its aliased PUSH DX')
    if name == 'cadence-high-sample-occupied':
        oracle_require(('main', 0x255B, 0x2560) in oracle['edges'] and
                       ('main', 0x256C, 0x256E) in oracle['edges'] and
                       ('main', 0x258C, 0x2591) in oracle['edges'],
                       name + ': high cadence/sample route did not reach transition')
    if name == 'high-sample-clear':
        oracle_require(('main', 0x258C, 0x258E) in oracle['edges'] and
                       ('main', 0x258E, 0x1FE8) in oracle['edges'],
                       name + ': clear high sample did not jump to interaction tail')
    if name == 'low-sample-occupied':
        oracle_require(('main', 0x255B, 0x255D) in oracle['edges'] and
                       ('main', 0x255D, 0x25E1) in oracle['edges'] and
                       ('main', 0x25F8, 0x25FA) in oracle['edges'] and
                       ('main', 0x25FA, 0x1FE8) in oracle['edges'],
                       name + ': occupied low sample did not take the expected route')
    if name == 'low-empty-clamped-by-finish':
        oracle_require(('main', 0x25F8, 0x25FD) in oracle['edges'] and
                       ('main', 0x2634, 0x2148) in oracle['edges'] and
                       ('main', 0x2151, 0x2156) in oracle['edges'],
                       name + ': empty/clamp route did not reach signed finish clamp')
    if name == 'mov-al-replaces-zero-product-low-byte':
        oracle_require(plan is not None and (plan['product'] & 0xFF) == 0 and
                       case['occupied'] and
                       ('main', 0x258C, 0x2591) in oracle['edges'],
                       name + ': occupied mask did not replace residual product AL')
    if name == 'clear-bit20-on-occupied-transition':
        oracle_require((read16(oracle['memory'], ds, si + 8) & 0x0020) == 0,
                       name + ': transition failed to clear state bit 0020')


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding, plan = setup(case)
    oracle = original(case, initial, regs, device)
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
    mask = oracle['flag_mask']
    require(((actual['regs']['flags'] ^ oracle['regs']['flags']) & mask) == 0,
            f'{label}: flags {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {mask:04X}')
    require(actual['memory'] == oracle['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['used'],
            f'{label}: provider transitions differ '
            f'{actual["providers"]}/{oracle["used"]}')
    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target) for source, source_ip, target in oracle['edges']
                 if source == 'main' and source_ip in OWN_INS}
    integrated_sites = {address for source, address in oracle['sites']
                        if source == 'main'}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(integrated_sites),
                event_count=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'src/game_code.asm', 'src/entity_graphics.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/toolchain-lock.json',
        'c/entity_state20.c', 'c/entity_state20.h',
        'c/entity_pixel.c', 'c/entity_pixel.h', 'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/pcspeaker_sym.h', 'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/lemmings_sym.h',
        'tests/entity_state20.py', 'tests/entity_interactions.py', 'tests/entity_finish.py',
        'tests/entity_pixel.py', 'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/common.py', 'tools/resources.py', 'tools/unpack.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_preflight():
    before = input_hashes()
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 0xE8 and
                   len(OWN_INS) == 74,
                   f'state20 identity changed: {sum(i.size for i in OWN_INS.values())} bytes/'
                   f'{len(OWN_INS)} sites')
    oracle_require(len(OWN_EDGES) == 13,
                   f'state20 edge accounting changed: {sorted(OWN_EDGES)}')
    specs = cases()
    all_sites, all_edges = set(), set()
    for case in specs:
        initial, regs, device, _pc, _sound, plan = setup(case)
        result = original(case, initial, regs, device)
        independent_checks(case, initial, regs, plan, result)
        all_sites.update(address for source, address in result['sites']
                         if source == 'main' and address in OWN_INS)
        all_edges.update((source_ip, target)
                         for source, source_ip, target in result['edges']
                         if source == 'main' and source_ip in OWN_INS)
        if case.get('provider') == 'pixel-return':
            oracle_require((result['status'], result['continuation']) ==
                           (7, case['changed_target']),
                           case['name'] + ': changed pixel CALL did not stop at RET target')
        else:
            oracle_require((result['status'], result['continuation']) == (0, CONTINUATION),
                           case['name'] + ': did not reach normal 1FEB continuation')
        gc.collect()
    oracle_require(all_sites == set(OWN_INS),
                   f'original own-site coverage {len(all_sites)}/{len(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'original own-edge coverage {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')
    oracle_require(before == input_hashes(),
                   'state20 source inputs changed during original-only preflight')
    print(f'PASS original state20 preflight: {len(specs)} fixtures, '
          f'{len(all_sites)} sites, {len(all_edges)} edges; no native code loaded',
          flush=True)


def worker(directory):
    before = input_hashes()
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 0xE8 and
                   len(OWN_INS) == 74 and len(OWN_EDGES) == 13,
                   'state20 static byte/site/edge identity changed')
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
                   f'native own-site coverage {len(all_sites)}/{len(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'native own-edge coverage {len(all_edges)}/{len(OWN_EDGES)}; '
                   f'missing={sorted(OWN_EDGES-all_edges)}')

    witnesses = {
        1: 'cadence-high-sample-occupied',
        2: 'live-pitch-reread-after-pixel-call',
        3: 'unsigned-sign-edge',
        4: 'mov-al-replaces-zero-product-low-byte',
        5: 'signed-velocity-cbw',
        6: 'clear-bit20-on-occupied-transition',
        7: 'callback-late-read-alias-and-neg-flags',
        8: 'first-pixel-call-return-overwrite',
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
    oracle_require(len(mutations) == 8, 'state20 mutation witnesses incomplete')
    oracle_require(before == input_hashes(), 'state20 campaign inputs changed during execution')
    integrated = set().union(*(set(row['integrated_sites']) for row in rows))
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(specs),
                  mutation_count=len(mutations), mutations=mutations,
                  executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  translated_code_bytes=0xE8, instruction_sites=len(OWN_INS),
                  own_branch_edges=len(OWN_EDGES), integrated_site_count=len(integrated),
                  core_adapter_cases=len(rows), event_count=total_events,
                  cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                              continuation=row['continuation'], sites=row['sites'],
                              edges=row['edges'], event_count=row['event_count'],
                              steps=row['steps']) for row in rows],
                  limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                              original_instructions=MAX_INSTRUCTIONS,
                              ordered_events=MAX_EVENTS),
                  input_hashes=before,
                  domain='254F..2636 state-0020 original/native core and adapter; '
                         'actual 5DC6 CALL/RET, shared 2148/1FE8 finish and interaction '
                         'tail, unsigned threshold and signed velocity, live row pitch, '
                         'callback/record/stack aliases, VGA reads, full 1 MiB RAM, '
                         'all registers, defined flags and ordered events.')
    write_json(REPORT, report)
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
                  case_count=len(specs), executed_instruction_addresses=sorted(all_sites),
                  branch_edges=[list(edge) for edge in sorted(all_edges)],
                  input_hashes=before, c_coverage_claimed=False))
    print(f'PASS entity state20: {len(specs)} cases x core/adapter, '
          f'{len(OWN_INS)} sites, {len(OWN_EDGES)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 2 and sys.argv[1] == '--original-only':
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    REPORT.unlink(missing_ok=True)
    ORIGINAL_REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state20-', parent=BUILD) as directory:
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
        raise SystemExit('usage: entity_state20.py [--worker DLL_DIRECTORY | --original-only]')
