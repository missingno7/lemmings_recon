"""Bounded composition checks for UpdateFixedWordPattern (5827..587E)."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as oracle
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import relocated

IMAGE, META = oracle.IMAGE, oracle.ORACLE
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
LOAD, DATA_SEGMENT = 0x1010, 0x19B9
PARENT, PARENT_RET, PARENT_END = 0x5827, 0x587E, 0x587F
COPY, COPY_RET, COPY_END = 0x715F, 0x71C9, 0x71CA
DRAW, DRAW_RET, DRAW_END = 0x7218, 0x75EE, 0x75EF
SELECTOR, OFFSET_BIAS, ALT_ORIGIN = 0x1FEA, 0x1FE0, 0x1F78
SOURCE_A, SOURCE_B, DEST_A, DEST_B = 0x2000, 0x2100, 0x3000, 0x4000
WORKER_SECONDS, MEMORY_MIB = 420, 384
MAX_STEPS, MAX_EVENTS = 20_000, 20_000
CALL_COPY_CHANGED, CALL_DRAW_CHANGED = 101, 102
CALL_RETURNS = {
    0x5827: ({COPY_RET}, CALL_COPY_CHANGED),
    0x5866: ({DRAW_RET}, CALL_DRAW_CHANGED),
}
ROLE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'code_segment',
              'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
              'flags')
REG_NAMES = oracle.REG_NAMES
REG_ROLE = dict(zip(ROLE_NAMES, ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp',
                                 'cs', 'ds', 'es', 'ss', 'sp', 'flags')))
MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8,
                     ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)
REPORT = BUILD / 'fixed-pattern-update-differential.json'
ORIGINAL_REPORT = BUILD / 'fixed-pattern-update-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_INS = {ins.address: ins
              for ins in MD.disasm(IMAGE[PARENT:PARENT_END], PARENT)}
COPY_INS = {ins.address: ins
            for ins in MD.disasm(IMAGE[COPY:COPY_END], COPY)}
DRAW_INS = {ins.address: ins
            for ins in MD.disasm(IMAGE[DRAW:DRAW_END], DRAW)}
MAIN_INS = PARENT_INS | COPY_INS | DRAW_INS
PARENT_SITES = set(PARENT_INS)
COPY_SITES = set(COPY_INS)
DRAW_SITES = set(DRAW_INS)
OWN_SITES = PARENT_SITES | COPY_SITES | DRAW_SITES


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in ROLE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16)
                for name in ROLE_NAMES + ('continuation', 'status', 'child_entry')]


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The pinned original escaped a declared span or exhausted a bound."""


class Mismatch(AssertionError):
    """A completed native execution differs from completed original execution."""


def check(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put_bytes(memory, segment, offset, data):
    base = physical(segment, offset)
    for delta, value in enumerate(data):
        memory[(base + delta) & MASK] = value


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def result_word(ref, segment, offset):
    """Read a final stack word through the fixture's live VGA read map."""
    values = []
    for delta in (0, 1):
        address = (physical(segment, offset) + delta) & MASK
        if ref['device'] is not None and VGA_BASE <= address < VGA_END:
            plane = ref['device'].gc[4] & 3
            values.append(ref['device'].planes[plane][address - VGA_BASE])
        else:
            values.append(ref['memory'][address])
    return values[0] | (values[1] << 8)


def seed_vga_ram(memory, device):
    memory[VGA_BASE:VGA_END] = device.planes[0]


def sync_vga_stack(memory, device, segment, offset, length=2):
    """Seed the CPU-visible plane for initial stack words in the VGA aperture."""
    for delta in range(length):
        address = physical(segment, offset + delta)
        if VGA_BASE <= address < VGA_END:
            device.planes[0][address - VGA_BASE] = memory[address]


def cases():
    specs = []
    # All slice alignments crossed with the two ordinary selection values and
    # the exact FF selector. Child fixtures separately own exhaustive leaf
    # matrices; this parent matrix verifies the composed slice/branch choice.
    for selected in (0x00, 0x01, 0xFF):
        for alignment in range(8):
            specs.append((f'align-{alignment}-selection-{selected:02x}', {
                'x': 0x0120 + alignment, 'selection': selected,
                'bias': 0, 'y': 0x0027}))
    specs.extend((
        ('alignment-wrap-ffff-plus-one', {
            'x': 0xFFFF, 'bias': 1, 'y': 0xFFFF, 'origin': 0xFFF1}),
        ('bias-byte-add-wrap', {
            'x': 0xFFFF, 'bias': 0xFF, 'y': 0x7FFF, 'origin': 0xFFF0}),
        ('coordinate-product-and-origin-wrap', {
            'x': 0xFFF8, 'bias': 0x17, 'y': 0xFFFF, 'origin': 0xFFF0}),
        ('df-clear-if-clear', {'flags': 0x08D7}),
        ('df-clear-if-set', {'flags': 0x0AD7}),
        ('df-set-if-clear', {'flags': 0x0CD7}),
        ('df-set-if-set', {'flags': 0x0ED7}),
        ('data-segment-ffff-coordinate-words', {
            'ds': 0xFFFF, 'x': 0xFFF9, 'bias': 0x0B,
            'y': 0xFFFE, 'origin': 0xFFE0}),
        ('selector-read-after-push-alias', {
            'ds': 0x2800, 'ss': 0x2800, 'sp': 0x1FEC,
            'selector': 0x6000, 'x': 0x0100, 'y': 0x0020}),
        ('saved-ds-overwritten-by-draw', {
            'ss': 0x5000, 'sp': 0x9000, 'draw_target': 0x6000,
            'origin': 0x6000, 'x': 0, 'bias': 0, 'y': 0,
            'provider': 'saved-ds',
            'draw_bytes': (0x34, 0x12), 'draw_masks': (0xFF, 0xFF, 0xFF)}),
        ('changed-copy-child-return', {
            'ss': 0x5000, 'sp': 0x9000, 'provider': 'copy-return',
            'source_a': 0x7000, 'dest_a': 0x3000,
            'origin': 0x1800, 'changed_return': True}),
        ('vga-stack-hardware-altered-copy-return', {
            'ss': 0xA000, 'sp': 0x9000, 'changed_return': True,
            'gc8': 0xA5}),
        ('changed-draw-child-return', {
            'ss': 0x5000, 'sp': 0x9000, 'draw_target': 0x6000,
            'origin': 0x6000, 'provider': 'draw-return',
            'x': 0, 'bias': 0, 'y': 0,
            'draw_bytes': (0x34, 0x12), 'draw_masks': (0xFF, 0xFF, 0xFF),
            'changed_return': True}),
        ('outer-ret-overwritten-by-draw', {
            'ss': 0x5000, 'sp': 0x9000, 'draw_target': 0x6000,
            'origin': 0x6000, 'provider': 'outer-return',
            'x': 0, 'bias': 0, 'y': 0,
            'draw_bytes': (0x34, 0x12), 'draw_masks': (0xFF, 0xFF, 0xFF)}),
        ('first-pair-stack-alias', {
            'ds': 0x2800, 'ss': 0x2800, 'sp': 0x0010,
            'selector': 0x6000, 'x': 0x0120, 'y': 0x0020}),
        ('second-pair-stack-alias', {
            'ds': 0x2800, 'ss': 0x2800, 'sp': 0x000C,
            'selector': 0x6000, 'x': 0x0120, 'y': 0x0020}),
        ('outer-ret-word-offset-and-physical-wrap', {
            'ss': 0xFFFF, 'sp': 0xFFFF, 'outer_return': 0xBEEF}),
        ('seeded-live-state-a', {
            'x': 0xA513, 'bias': 0x17, 'y': 0x71E7, 'origin': 0xFEE3,
            'selection': 0xFE, 'flags': 0x08D7, 'gc4': 1, 'gc8': 0x3C}),
        ('seeded-live-state-b', {
            'x': 0xF234, 'bias': 0xE9, 'y': 0x8001, 'origin': 0x0F03,
            'selection': 0xFF, 'flags': 0x0CD7, 'gc4': 3, 'gc8': 0xC3}),
    ))
    base = dict(ds=DATA_SEGMENT, es=0x7200, ss=0x5000, sp=0x9000,
                flags=0x0AD7, ax=0xBEEF, bx=0x7139, cx=0x6A55,
                dx=0x42D3, si=0x4000, di=0xD025, bp=0xA641,
                x=0x0125, y=0x0027, bias=0x03, origin=0x1000,
                selection=0, selector=0x6000, source_a=0x2000,
                dest_a=0x3000, dest_b=0x4000, outer_return=0xD00D,
                seed=0x582700)
    rows = []
    for index, (name, updates) in enumerate(specs):
        row = dict(base, seed=base['seed'] + index * 0x101)
        row.update(updates)
        row['name'] = name
        rows.append(row)
    return rows


def prepare(case):
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    start = LOAD << 4
    memory[start:start + len(loaded)] = loaded

    device = MinimapVga(case['seed'] ^ PARENT, read_map=case.get('gc4', 0))
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[2] = 0
    device.gc[3] = 0
    device.gc[4] = case.get('gc4', 0) & 3
    device.gc[5] = 0
    device.gc[6] = 5
    device.gc[7] = 0
    device.gc[8] = case.get('gc8', 0xA5)
    seed_vga_ram(memory, device)

    regs = dict(ax=case['ax'], bx=case['bx'], cx=case['cx'], dx=case['dx'],
                si=case['si'], di=case['di'], bp=case['bp'], cs=LOAD,
                ds=case['ds'], es=case['es'], ss=case['ss'], sp=case['sp'],
                ip=PARENT, flags=case['flags'] & ~0x0100)

    # The first child copies three-byte spans from A000 to A000. Seed a broad
    # read domain so aliases, signed DF movement and wrapped offsets stay
    # observable without assuming a source-bound invariant.
    source_span = bytearray(rng.randbytes(0x10000))
    src_off = case.get('source_a', SOURCE_A)
    changed_bytes = case.get('first_source_bytes')
    if changed_bytes:
        source_span[src_off & 0xFFFF] = changed_bytes[0]
        source_span[(src_off + 1) & 0xFFFF] = changed_bytes[1]
    device.planes[0][:] = source_span
    seed_vga_ram(memory, device)

    # The generated word bank is treated as a separate live segment. Parent
    # slice choice determines which 90h-byte region the draw leaf reads.
    bank_segment = case.get('selector', 0x6000)
    rng_bank = random.Random(case['seed'] ^ 0x72187518)
    bank = bytearray(rng_bank.randbytes(0x900))
    draw_bytes = case.get('draw_bytes')
    if draw_bytes:
        bank[0:2] = bytes(draw_bytes)
    draw_masks = case.get('draw_masks')
    if draw_masks:
        bank[0x60:0x63] = bytes(draw_masks)
    put_bytes(memory, bank_segment, 0, bank)

    # Also initialize the data-frame view for the selector/stack alias case,
    # where PUSH DS replaces the selector before the MOV DS,[1FEA] read.
    if bank_segment != regs['ds']:
        put_bytes(memory, regs['ds'], 0, bank)

    pointer_x = case.get('x', 0x0125)
    pointer_y = case.get('y', 0x0027)
    put16(memory, regs['ds'], 0x0008, case.get('dest_b', DEST_B))
    put16(memory, regs['ds'], 0x000A, src_off)
    put16(memory, regs['ds'], 0x000C, 0x0000)
    put16(memory, regs['ds'], 0x000E, case.get('dest_a', DEST_A))
    put16(memory, regs['ds'], 0x0010, pointer_x)
    put16(memory, regs['ds'], 0x0012, pointer_y)
    put8(memory, regs['ds'], OFFSET_BIAS, case.get('bias', 0x03))
    put16(memory, regs['ds'], ALT_ORIGIN, case.get('origin', 0x1000))
    put8(memory, regs['ds'], 0x001A, case.get('selection', 0))
    put16(memory, regs['ds'], SELECTOR, bank_segment)

    # Child-return and outer-return alias witnesses intentionally place near
    # frames in the A000 aperture. Keep the corresponding initial CPU-visible
    # words coherent with the independent VGA fixture.
    put16(memory, regs['ss'], regs['sp'], case.get('outer_return', 0xD00D))
    sync_vga_stack(memory, device, regs['ss'], regs['sp'])
    return memory, regs, device


class Access(oracle.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []

    def queue_word(self, segment, offset, value, label):
        self.pending.append((segment & 0xFFFF, offset & 0xFFFF,
                             value & 0xFFFF, label))

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for segment, offset, value, label in pending:
            self.modify_word(segment, offset, value)
            self.used.add(label)

    def provider_after_write(self, address):
        case = self.case
        provider = case.get('provider')
        if not provider or provider in self.used:
            return
        if provider == 'copy-return':
            trigger_offset = case.get('dest_a', DEST_A)
            target_sp = (case['sp'] - 2) & 0xFFFF
        elif provider in ('draw-return', 'saved-ds', 'outer-return'):
            trigger_offset = case.get('draw_target', draw_source_offset(case))
            target_sp = {
                'draw-return': (case['sp'] - 4) & 0xFFFF,
                'saved-ds': (case['sp'] - 2) & 0xFFFF,
                'outer-return': case['sp'],
            }[provider]
        else:
            raise OracleFailure('unknown fixed-pattern provider ' + provider)
        if address != physical(0xA000, trigger_offset):
            return
        self.queue_word(case['ss'], target_sp, 0x1234, provider)
        # The original oracle flushes after the guest instruction in its code
        # hook. Native C callbacks occur inside the instruction, so flush after
        # this byte callback to expose the same live stack word to later code.
        if self.native:
            self.instruction_complete()

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise oracle.OracleFailure('fixed-pattern VGA callback budget exhausted')
        if self.device is None:
            raise oracle.OracleFailure('fixed-pattern port write without VGA fixture')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        if kind == 'write':
            self.provider_after_write(address & MASK)
        return result


def original(case, memory, regs, device, *, core):
    accessors = []
    # This engine executes both real child RETs. The pre-RET core boundary is
    # an explicit parent stop, so a child RET is never mistaken for READY.
    ref = oracle.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=MAIN_INS,
        main_call_returns=CALL_RETURNS,
        stop_offsets={PARENT_RET: 0} if core else None,
        access_factory=lambda c, m, r, d: accessors.append(Access(c, m, r, d))
        or accessors[-1], instruction_limit=MAX_STEPS)
    raw_status = ref['status']
    child_entry = (COPY if raw_status == CALL_COPY_CHANGED else
                   DRAW if raw_status == CALL_DRAW_CHANGED else 0)
    ref['raw_status'] = raw_status
    ref['child_entry'] = child_entry
    ref['status'] = 1 if child_entry else 0
    ref['provider_events'] = set(accessors[0].used)
    return ref


def expected_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.lower() in (
                'loop', 'loope', 'loopne', 'jcxz'):
            target = ins.operands[0].imm & 0xFFFF
            edges.add((address, target))
            if ins.mnemonic.lower() != 'jmp':
                edges.add((address, (address + ins.size) & 0xFFFF))
    return edges


def independent_slot_swaps(case, initial, expected):
    """Check the two numeric parent swaps on the alias-free baseline domain."""
    if case['name'] not in ('align-0-selection-00',
                            'align-7-selection-ff', 'seeded-live-state-a'):
        return False
    ds = case['ds']
    before = [get16(initial, ds, n) for n in (8, 10, 12, 14)]
    after = [get16(expected['memory'], ds, n) for n in (8, 10, 12, 14)]
    x = get16(initial, ds, 0x10)
    bias = initial[physical(ds, OFFSET_BIAS)]
    y = get16(initial, ds, 0x12)
    origin = get16(initial, ds, ALT_ORIGIN)
    source = (((x + bias) & 0xFFFF) >> 3)
    source = (source + y * 0x2C + origin) & 0xFFFF
    wanted = [before[1], before[0], before[3], source]
    check(after == wanted,
          case['name'] + ': independent final offset-pair swap equation differs')
    return True


def draw_source_offset(case):
    coordinate = (case.get('x', 0x0125) + case.get('bias', 0x03)) & 0xFFFF
    return (case.get('origin', 0x1000) + (coordinate >> 3) +
            case.get('y', 0x0027) * 0x2C) & 0xFFFF


def validate(case, initial, initial_device, regs, ref, *, core):
    changed = case.get('changed_return')
    expected_status = 1 if changed else 0
    check(ref['status'] == expected_status,
          case['name'] + ': original status does not match the declared boundary')
    if changed:
        if case.get('provider'):
            check(ref['regs']['ip'] == 0x1234,
                  case['name'] + ': provider child target was not consumed')
        else:
            check(ref['regs']['ip'] != (PARENT + 3),
                  case['name'] + ': VGA stack did not change the CALL return word')
        check(ref['child_entry'] == (COPY if case['name'] in (
              'changed-copy-child-return',
              'vga-stack-hardware-altered-copy-return') else DRAW),
              case['name'] + ': changed child provenance differs')
        check(ref['regs']['sp'] == (regs['sp'] if ref['child_entry'] == COPY
                                    else (regs['sp'] - 2) & 0xFFFF),
              case['name'] + ': changed child frame was not preserved')
    elif core:
        check(ref['regs']['ip'] == PARENT_RET,
              case['name'] + ': core did not stop before the outer RET')
        check(ref['regs']['sp'] == regs['sp'],
              case['name'] + ': core changed the outer stack offset')
    else:
        check(ref['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
              case['name'] + ': adapter did not consume the actual outer RET')
        check(ref['regs']['ip'] == result_word(ref, regs['ss'], regs['sp']),
              case['name'] + ': adapter did not use the live outer RET word')
    if not changed:
        check(ref['regs']['es'] == 0xA000,
              case['name'] + ': composed VGA leaves did not retain ES=A000')
    check((ref['regs']['flags'] & 0x0400) == (regs['flags'] & 0x0400),
          case['name'] + ': DF changed across the composition')
    check(ref['regs']['flags'] & 0x0200,
          case['name'] + ': composition did not force IF on')
    if case['name'] == 'outer-ret-overwritten-by-draw' and not core:
        check(ref['regs']['ip'] == 0x1234,
              case['name'] + ': draw output did not replace the outer RET word')
    expected_provider = {case['provider']} if case.get('provider') else set()
    check(ref['provider_events'] == expected_provider,
          case['name'] + ': provider transition did not occur at its declared access')
    if case['name'] == 'saved-ds-overwritten-by-draw':
        check(ref['regs']['ds'] == 0x1234,
              case['name'] + ': POP DS did not reread the provider-modified word')
    slots_checked = independent_slot_swaps(case, initial, ref)
    return dict(slot_swap_equation=slots_checked)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'fixed-pattern-update-m{mutation}.dll',
                     mutation, 'fixed_pattern_update')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_update_fixed_word_pattern_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_update_fixed_word_pattern_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(oracle.Regs), ct.POINTER(Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)

        def die(error):
            code = 86 if 'budget' in str(error).lower() else 87
            try:
                os.write(2, (str(error) + '\n').encode(
                    'utf-8', errors='backslashreplace'))
            finally:
                os._exit(code)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                die(error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                die(error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                die(error)

        callbacks = READ(read), WRITE(write), OUT(out)
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        child_entry = 0
        if core:
            call = Call(*(regs[REG_ROLE[role]] for role in ROLE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for role in ROLE_NAMES:
                setattr(state, REG_ROLE[role], getattr(result, role))
            state.ip = result.continuation
            status, child_entry = result.status, result.child_entry
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in REG_NAMES},
                    status=status, child_entry=child_entry, events=access.events,
                    providers=set(access.used),
                    device=device)


def compare_result(actual, expected, label, *, core):
    require(actual['status'] == expected['status'],
            label + f': status {actual["status"]}/{expected["status"]}')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    for name in REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    if core:
        require(actual['child_entry'] == expected['child_entry'],
                label + ': changed child entry differs')
    require(actual['providers'] == expected['provider_events'],
            label + ': provider transitions differ')
    require(len(actual['events']) == len(expected['events']),
            label + ': ordered event count differs')
    for index, (got, want) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == want[:3],
                f'{label}: event {index} differs: {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} flags differ under {want[4]:04X}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA state differs')
    require([event[:3] for event in actual['device'].trace] ==
            [event[:3] for event in expected['device'].trace],
            label + ': VGA trace differs')


def compare(native, case, *, core):
    memory, regs, device = prepare(case)
    expected = original(case, memory, regs, device, core=core)
    checks = validate(case, memory, device, regs, expected, core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    compare_result(actual, expected, case['name'] +
                   (' core' if core else ' adapter'), core=core)
    return expected, checks


def hash_inputs():
    paths = {
        'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/inputs.json', 'metadata/oracle.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'src/game_code_late_after_palette.asm', 'src/fixed_pattern_drawing.asm',
        'c/fixed_pattern_update.c', 'c/fixed_pattern_update.h',
        'c/fixed_pattern_copy.c', 'c/fixed_pattern_copy.h',
        'c/fixed_pattern_draw.c', 'c/fixed_pattern_draw.h',
        'c/fixed_word_banks.c', 'c/fixed_word_banks.h',
        'c/mask_generators.c', 'c/mask_generators.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/fixed_pattern_update.py', 'tests/entity_interactions.py',
        'tests/minimap_vga.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/fixed_word_banks.py',
        'tests/sprite_bank.py', 'tests/entity_sprite_layout.py',
        'tests/entity_sprite_planes.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py', 'tools/unpack.py',
    }
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def collect(ref, case, core, checks):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
                status=ref['status'], child_entry=ref['child_entry'],
                parent_sites=sorted(pc for scope, pc in ref['sites']
                                    if scope == 'main' and pc in PARENT_SITES),
                integrated_sites=sorted(pc for scope, pc in ref['sites']
                                        if scope == 'main'),
                parent_edges=sorted([a, b] for scope, a, b in ref['edges']
                                    if scope == 'main' and a in PARENT_SITES),
                integrated_edges=sorted([a, b] for scope, a, b in ref['edges']
                                        if scope == 'main'),
                ordered_events=len(ref['events']), original_steps=ref['steps'],
                slot_swap_equation=checks['slot_swap_equation'])


def publish(path, before, rows, mutants=None):
    sites = {pc for row in rows for pc in row['integrated_sites']}
    parent_sites = {pc for row in rows for pc in row['parent_sites']}
    edges = {tuple(edge) for row in rows for edge in row['integrated_edges']}
    parent_edges = {tuple(edge) for row in rows for edge in row['parent_edges']}
    check(parent_sites == PARENT_SITES, 'missing parent instruction sites')
    check(sites == OWN_SITES,
          f'missing integrated instruction sites: {OWN_SITES - sites}')
    check(edges == expected_edges(MAIN_INS),
          'integrated branch outcomes do not match both copy loops')
    check(parent_edges == {(0x5852, 0x5858), (0x5852, 0x5854)},
          'parent selection branch outcomes differ')
    report = dict(image='main', image_sha256=sha(IMAGE), entry=PARENT,
                  ret=PARENT_RET, end=PARENT_END, case_count=len(cases()),
                  comparison_count=len(rows), translated_code_bytes=PARENT_END-PARENT,
                  instruction_sites=len(PARENT_SITES),
                  integrated_code_bytes=(PARENT_END-PARENT) +
                  (COPY_END-COPY) + (DRAW_END-DRAW),
                  integrated_instruction_sites=len(OWN_SITES),
                  executed_instruction_addresses=sorted(sites),
                  parent_executed_instruction_addresses=sorted(parent_sites),
                  copy_executed_instruction_addresses=sorted(sites & COPY_SITES),
                  draw_executed_instruction_addresses=sorted(sites & DRAW_SITES),
                  branch_edges=sorted([a, b] for a, b in edges),
                  branch_edge_count=len(edges),
                  ordered_events=sum(row['ordered_events'] for row in rows),
                  instruction_steps=sum(row['original_steps'] for row in rows),
                  independent_slot_swap_fixtures=sum(
                      row['slot_swap_equation'] for row in rows),
                  original_only=mutants is None, mutation_count=len(mutants or []),
                  mutations=mutants or [], rows=rows, input_hashes=before,
                  source_a=SOURCE_A, source_b=SOURCE_B,
                  limits=dict(timeout_seconds=WORKER_SECONDS,
                              process_commit_mib=MEMORY_MIB,
                              original_instruction_limit=MAX_STEPS,
                              bus_event_limit=MAX_EVENTS))
    write_json(path, report)
    print(f'PASS fixed-pattern update: {len(cases())} fixtures/{len(rows)} '
          f'boundaries, {len(parent_sites)} parent sites, {len(sites)} integrated '
          f'sites/{len(edges)} edges, {report["ordered_events"]} events, '
          f'{len(mutants or [])} mutants', flush=True)


def original_campaign():
    before, rows = hash_inputs(), []
    for case in cases():
        memory, regs, device = prepare(case)
        for core in (True, False):
            ref = original(case, memory, regs, device, core=core)
            checks = validate(case, memory, device, regs, ref, core=core)
            rows.append(collect(ref, case, core, checks))
            del ref
        gc.collect()
        print('CHECKED original ' + case['name'], flush=True)
    check(before == hash_inputs(), 'inputs changed during original campaign')
    publish(ORIGINAL_REPORT, before, rows)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == hash_inputs(), 'input snapshot differs')
    native = Native(directory)
    rows = []
    for case in cases():
        for core in (True, False):
            ref, checks = compare(native, case, core=core)
            rows.append(collect(ref, case, core, checks))
            del ref
        gc.collect()
        print('CHECKED native ' + case['name'], flush=True)

    by_name = {case['name']: case for case in cases()}
    witnesses = (
        (1, 'changed-copy-child-return', True),
        (2, 'align-7-selection-00', True),
        (3, 'align-7-selection-00', True),
        (4, 'align-0-selection-01', True),
        (5, 'align-0-selection-ff', True),
        (6, 'align-0-selection-00', True),
        (7, 'saved-ds-overwritten-by-draw', True),
        (8, 'align-0-selection-00', True),
        (9, 'outer-ret-overwritten-by-draw', False),
        (10, 'outer-ret-overwritten-by-draw', False),
    )
    mutants = []
    for number, name, core in witnesses:
        try:
            compare(Native(directory, number), by_name[name], core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=number, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'mutation {number} survived its completed witness')
        gc.collect()
    check(before == hash_inputs(), 'inputs changed during native campaign')
    publish(REPORT, before, rows, mutants)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:] == ['--original-worker']:
        original_campaign()
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: fixed_pattern_update.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='fixed-pattern-update-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(hash_inputs(), sort_keys=True))
        run_bounded([sys.executable, __file__, '--worker', directory, str(snapshot)],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB,
                    check=True)


if __name__ == '__main__':
    main()
