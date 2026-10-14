"""Bounded source-row preparation tests for four planar draw continuations."""
import ctypes
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from unpack import ASSET, unpack, relocated

MEMORY_SIZE = 1 << 20
MAPPED_SIZE = 2 * MEMORY_SIZE
MEMORY_MASK = MEMORY_SIZE - 1
LOADS = (0x1010, 0x1213, 0x2345)
IMAGE, UNPACK_ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row
        for row in read_json(ROOT / 'metadata/symbols.json')}
ROUTINES = (
    ('PrepareShiftedMaskedPlanarRows', 0x88bf, 79, 29, True, True),
    ('PrepareShiftedOpaquePlanarRows', 0x9140, 43, 17, True, False),
    ('PrepareAlignedMaskedPlanarRows', 0x93a7, 79, 29, False, True),
    ('PrepareAlignedOpaquePlanarRows', 0x9810, 43, 17, False, False),
)
MASK_ORDER = (0x4000, 0x8000, 0x0020, 0x0040)
MASK_TARGETS = {
    0x88bf: {0x4000: 0x8d66, 0x8000: 0x8b42,
             0x0020: 0x8ff7, 0x0040: 0x909c},
    0x93a7: {0x4000: 0x969c, 0x8000: 0x953e,
             0x0020: 0x9737, 0x0040: 0x97a4},
}
MASKED_ENDS = {0x88bf: 0x890e, 0x93a7: 0x93f6}
OPAQUE_ENDS = {0x9140: 0x916b, 0x9810: 0x983b}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {}
ENTRY_END = {}
for _name, _entry, _size, _sites, _shifted, _masked in ROUTINES:
    _row = SYMS[_name]
    if _row['address'] != _entry or _row['size'] != _size:
        raise AssertionError(f'{_name}: pinned span changed')
    _part = {ins.address: ins
             for ins in MD.disasm(IMAGE[_entry:_entry + _size], _entry)}
    if len(_part) != _sites or sum(i.size for i in _part.values()) != _size:
        raise AssertionError(f'{_name}: instruction boundary accounting changed')
    INS.update(_part)
    ENTRY_END[_entry] = _entry + _size
LOCAL_SITES = set(INS)
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EXPECTED_EDGES = set()
for _pc, _ins in INS.items():
    if _pc not in BRANCHES:
        continue
    EXPECTED_EDGES.add((_pc, _ins.operands[0].imm & 0xffff))
    if _ins.mnemonic != 'jmp':
        EXPECTED_EDGES.add((_pc, _pc + _ins.size))

CF, PF, AF, ZF, SF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x200, 0x400, 0x800
FLAGS_DEFINED = CF | PF | AF | ZF | SF | IF | DF | OF
FLAGS_NO_TEST_AF = FLAGS_DEFINED & ~AF
ARITH_MNEMONICS = {'add', 'sub'}
LOGIC_MNEMONICS = {'test'}
REG_NAMES = oracle.REG_NAMES
MEM = ctypes.POINTER(ctypes.c_uint8)


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in REG_NAMES + ('flags',)]


class DrawingSourceCall(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'data_segment', 'stack_segment', 'stack_offset', 'work_value',
        'second_source_cursor', 'packed_counts', 'width_state',
        'source_cursor', 'destination_cursor', 'control', 'flags', 'entry')]


class DrawingSourceResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'work_value', 'second_source_cursor', 'packed_counts', 'width_state',
        'source_cursor', 'destination_cursor', 'control', 'stack_offset',
        'flags', 'continuation')]


READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


def physical(segment, offset):
    return ((segment << 4) + offset) & MEMORY_MASK


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xff
    memory[(address + 1) & MEMORY_MASK] = (value >> 8) & 0xff


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MEMORY_MASK] << 8)


def add_case(output, name, **fields):
    output.append(dict(name=name, seed=len(output), **fields))


def cases():
    output = []
    # Full Cartesian dispatch matrix. Opaque entries intentionally retain BP
    # priority bits without testing them; both flip and cursor directions run.
    for name, entry, _size, _sites, shifted, masked in ROUTINES:
        for flip in (0, 0x80):
            for priority_bits in range(16):
                priority = sum(MASK_ORDER[bit]
                               for bit in range(4)
                               if priority_bits & (1 << bit))
                add_case(output, f'{name}-{flip:02x}-{priority:04x}',
                         entry=entry, control=flip | priority)

    # Exercise arithmetic wrap and extreme skip/pitch/extent combinations on
    # every entry and in both source directions.
    extremes = (
        (0, 0, 0, 0), (0xffff, 0xffff, 0xffff, 0xffff),
        (0x0001, 0xfffe, 0x8000, 0x8001),
        (0xfffe, 0x0001, 0x7fff, 0x8001),
        (0x8000, 0x7fff, 0x0001, 0xffff),
        (0x7fff, 0x8000, 0xffff, 0x0001),
        (0x0101, 0x1234, 0xabcd, 0x7654),
        (0xfff0, 0x0011, 0x000f, 0xfffe),
    )
    for _name, entry, _size, _sites, _shifted, _masked in ROUTINES:
        for flip in (0, 0x80):
            for index, (horizontal, vertical, extent, pitch) in enumerate(extremes):
                add_case(output, f'{_name}-extreme-{flip:02x}-{index}',
                         entry=entry, control=flip, horizontal=horizontal,
                         vertical=vertical, extent=extent, pitch=pitch,
                         second_source=(0xffff if index & 1 else 0),
                         source=(0x8000 if index & 1 else 0xffff))

    # Stack wrapping, a stack word crossing 20-bit physical zero, and direct
    # and differently-segmented DS/SS aliases of each live field.
    for name, entry, _size, _sites, _shifted, _masked in ROUTINES:
        for sp in (0, 1, 0xffff):
            add_case(output, f'{name}-SP-{sp:04x}', entry=entry,
                     control=0x80, stack_offset=sp, pitch=0xffff,
                     vertical=0x7fff, extent=0x8001)
        add_case(output, f'{name}-DS-wrap', entry=entry, control=0x80,
                 data_segment=0xffff, stack_segment=0xf000,
                 stack_offset=1, vertical=0x8000, pitch=0xfffe,
                 extent=0x0001)
        add_case(output, f'{name}-SS-word-crosses-20-bit-zero', entry=entry,
                 control=0x80, stack_segment=0xf000, stack_offset=1,
                 data_segment=0xffff, horizontal=0xffff)

    # PUSH BP overwrites, respectively, horizontal skip, extent, pitch, and
    # vertical skip before the following live DS loads.
    for entry in (0x88bf, 0x9140, 0x93a7, 0x9810):
        for label, sp in (('horizontal', 0x66fe), ('extent', 0x66fa),
                          ('pitch', 0x66fc), ('vertical', 0x6700)):
            add_case(output, f'push-overwrites-{label}-{entry:04x}',
                     entry=entry, data_segment=0x6000,
                     stack_segment=0x6000, stack_offset=sp,
                     control=0x0080 | 0x0020, horizontal=0x1234,
                     vertical=0x2345, extent=0x4567, pitch=0x6789)

    # DS and SS have different segment values but PUSH still aliases DS:66FC.
    for entry in (0x88bf, 0x9140, 0x93a7, 0x9810):
        add_case(output, f'different-segments-alias-horizontal-{entry:04x}',
                 entry=entry, data_segment=0x6001, stack_segment=0x6000,
                 stack_offset=0x670e, control=0x0080 | 0x0040,
                 horizontal=0x0123, vertical=0x1111, extent=0x4567,
                 pitch=0x0101)

    # DS:6702 overwrites the live saved BP; the restored BP must choose the
    # priority route based on the value the store placed on the stack.
    for entry in (0x88bf, 0x93a7):
        add_case(output, f'store-overwrites-saved-BP-{entry:04x}',
                 entry=entry, data_segment=0x6000, stack_segment=0x6000,
                 stack_offset=0x6704, control=0, horizontal=0x4000)

    # Separate probe cases are the kill inputs for the three compiled mutants.
    add_case(output, 'mutant-one-vertical-skip', entry=0x88bf, control=0x80,
             horizontal=0x3210, vertical=0x1234, extent=0xabcd, pitch=0x1111,
             source=0x3000, second_source=0x5000)
    add_case(output, 'mutant-missed-pitch-sub', entry=0x93a7, control=0x80,
             horizontal=0x4321, vertical=0x0102, extent=0x7654, pitch=0x2345,
             source=0x8000, second_source=0xfff0)
    return output


def prepare(case):
    rng = random.Random(0x88bf + case['seed'])
    load = LOADS[case['seed'] % len(LOADS)]
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    image = relocated(IMAGE, UNPACK_ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(image)] = image
    data_segment = case.get('data_segment', (load + 0x09a9) & 0xffff)
    stack_segment = case.get('stack_segment', 0x7000)
    stack_offset = case.get('stack_offset', 0x8100)
    entry = case.get('entry', ROUTINES[case['seed'] % 4][1])
    control = case.get('control', 0)
    registers = {name: rng.randrange(65536) for name in REG_NAMES}
    registers.update(cs=load, ip=entry, ds=data_segment, ss=stack_segment,
                     sp=stack_offset, ax=rng.randrange(65536),
                     bx=case.get('second_source', rng.randrange(65536)),
                     cx=rng.randrange(65536), dx=rng.randrange(65536),
                     si=case.get('source', rng.randrange(65536)),
                     di=rng.randrange(65536), bp=control)
    for field, default in (('horizontal', 0x1234), ('vertical', 0x0021),
                           ('extent', 0x1357), ('pitch', 0x0123)):
        offset = {'horizontal': 0x66fc, 'vertical': 0x66fe,
                  'extent': 0x66f8, 'pitch': 0x66fa}[field]
        put16(memory, data_segment, offset, case.get(field, default))
    # Keep a recognizable unconsumed caller word and deterministic neighbors.
    put16(memory, stack_segment, stack_offset, 0xbeef)
    flags = 2 | (rng.randrange(1 << 12) & 0x0fd5)
    if rng.randrange(2):
        flags |= IF
    else:
        flags &= ~IF
    if rng.randrange(2):
        flags |= DF
    else:
        flags &= ~DF
    # A set TF dispatches INT 1 after each original instruction. Its handler
    # is outside this bounded source-preparation continuation.
    flags &= ~0x0100
    return memory, registers, flags, load


def library(mutation=0):
    path = build(BUILD / f'drawing-source-m{mutation}.dll', mutation,
                 'drawing_source')
    lib = ctypes.CDLL(str(path))
    lib.lmn_prepare_planar_source_rows_core.argtypes = [
        MEM, ctypes.POINTER(DrawingSourceCall), ctypes.POINTER(RasterBus)]
    lib.lmn_prepare_planar_source_rows_core.restype = DrawingSourceResult
    lib.lmn_prepare_planar_source_rows_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_prepare_planar_source_rows_adapter.restype = None
    return lib


def make_bus(memory):
    events = []
    errors = []

    @READ
    def read(_context, _memory, address, flags):
        try:
            address &= MEMORY_MASK
            value = memory[address]
            events.append(('read', address, value, flags & 0xffff))
            return value
        except Exception as error:
            errors.append(error)
            return 0

    @WRITE
    def write(_context, _memory, address, value, flags):
        try:
            address &= MEMORY_MASK
            value &= 0xff
            memory[address] = value
            events.append(('write', address, value, flags & 0xffff))
        except Exception as error:
            errors.append(error)

    @OUT
    def out(_context, port, value, flags):
        errors.append(AssertionError(
            f'unexpected port output {port:04x}={value:04x} flags={flags:04x}'))

    return RasterBus(None, read, write, out), events, errors


def make_call(registers, flags):
    return DrawingSourceCall(registers['ds'], registers['ss'], registers['sp'],
        registers['ax'], registers['bx'], registers['cx'], registers['dx'],
        registers['si'], registers['di'], registers['bp'], flags,
        registers['ip'])


def expected_route(entry, restored_bp):
    if entry in MASKED_ENDS:
        for bit in MASK_ORDER:
            if restored_bp & bit:
                return MASK_TARGETS[entry][bit]
        return MASKED_ENDS[entry]
    return OPAQUE_ENDS[entry]


def independent_row_expectation(memory, case, registers):
    """Small state-level model for row advance, cursors, and live BP alias."""
    memory = bytearray(memory)
    ds, ss, sp = registers['ds'], registers['ss'], registers['sp']
    entry, original_bp = registers['ip'], registers['bp']
    pushed = (sp - 2) & 0xffff
    put16(memory, ss, pushed, original_bp)
    bp = get16(memory, ds, 0x66fc)
    ax = original_bp
    bx, si = registers['bx'], registers['si']
    if original_bp & 0x80:
        ax = get16(memory, ds, 0x66f8)
        ax = (ax - get16(memory, ds, 0x66fe)) & 0xffff
        ax = (ax - get16(memory, ds, 0x66fe)) & 0xffff
        bx = (bx + ax) & 0xffff
        si = (si + ax) & 0xffff
        ax = get16(memory, ds, 0x66fa)
        bx = (bx - ax) & 0xffff
        si = (si - ax) & 0xffff
        bp = (bp - ax - ax) & 0xffff
    put16(memory, ds, 0x6702, bp)
    restored_bp = get16(memory, ss, pushed)
    return dict(work_value=ax, second_source_cursor=bx, source_cursor=si,
                control=restored_bp, stack_offset=sp,
                continuation=expected_route(entry, restored_bp),
                row_advance=get16(memory, ds, 0x6702))


def compare(lib, case):
    memory, initial_regs, flags, load = prepare(case)
    instruction_snapshots = {
        entry: bytes(memory[(load << 4) + entry:(load << 4) + entry + size])
        for _name, entry, size, _sites, _shifted, _masked in ROUTINES
    }
    expected = independent_row_expectation(memory, case, initial_regs)
    c_memory = bytearray(memory)
    call = make_call(initial_regs, flags)
    bus, c_events, c_errors = make_bus(c_memory)
    c_call_result = lib.lmn_prepare_planar_source_rows_core(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_memory),
        ctypes.byref(call), ctypes.byref(bus))
    if c_errors:
        raise c_errors[0]

    # Check the adapter over the same logical call and separately prove that
    # callback RAM and direct RAM have the same byte effects.
    adapter_memory = bytearray(memory)
    adapter_regs = Regs(**initial_regs, flags=flags)
    adapter_bus, adapter_events, adapter_errors = make_bus(adapter_memory)
    lib.lmn_prepare_planar_source_rows_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(adapter_memory),
        ctypes.byref(adapter_regs), ctypes.byref(adapter_bus))
    if adapter_errors:
        raise adapter_errors[0]
    direct_memory = bytearray(memory)
    direct_call_result = lib.lmn_prepare_planar_source_rows_core(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(direct_memory),
        ctypes.byref(call), None)
    if direct_memory != c_memory or bytes(direct_call_result) != bytes(c_call_result):
        raise AssertionError(f'{case["name"]}: null bus and callback RAM differ')
    if adapter_memory != c_memory or adapter_events != c_events:
        raise AssertionError(f'{case["name"]}: register adapter effects differ')

    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, MAPPED_SIZE)
    uc.mem_write(0, bytes(memory) + bytes(memory))
    for name, reg in oracle.REG.items():
        uc.reg_write(reg, initial_regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    u_events = []
    u_masks = []
    sites = set()
    edges = set()
    previous = None
    instruction_flags = flags
    instruction_mask = FLAGS_DEFINED
    flags_defined_after_previous = FLAGS_DEFINED
    stop_targets = set(MASK_TARGETS.get(initial_regs['ip'], {}).values())
    stop_targets.add(MASKED_ENDS.get(initial_regs['ip'],
                                    OPAQUE_ENDS.get(initial_regs['ip'])))
    stopped = False

    def code(machine, pc, _size, _user):
        nonlocal previous, instruction_flags, instruction_mask
        nonlocal flags_defined_after_previous, stopped
        offset = (pc - (initial_regs['cs'] << 4)) & 0xffff
        if previous in BRANCHES:
            edges.add((previous, offset))
        if offset in stop_targets:
            stopped = True
            machine.emu_stop()
            return
        if offset not in INS or machine.reg_read(oracle.REG['cs']) != load:
            raise AssertionError(f'{case["name"]}: original escaped at {offset:04x}')
        sites.add(offset)
        instruction_flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
        instruction_mask = flags_defined_after_previous
        ins = INS[offset]
        if ins.mnemonic in LOGIC_MNEMONICS:
            flags_defined_after_previous = FLAGS_NO_TEST_AF
        elif ins.mnemonic in ARITH_MNEMONICS:
            flags_defined_after_previous = FLAGS_DEFINED
        previous = offset

    def memory_read(machine, _access, address, size, _value, _user):
        for index in range(size):
            linear = address + index
            if linear >= MEMORY_SIZE:
                machine.mem_write(linear,
                    bytes(machine.mem_read(linear & MEMORY_MASK, 1)))
            event_address = linear & MEMORY_MASK
            value = machine.mem_read(linear, 1)[0]
            u_events.append(('read', event_address, value, instruction_flags))
            u_masks.append(instruction_mask)

    def memory_write(machine, _access, address, size, value, _user):
        for index in range(size):
            linear = address + index
            byte = (value >> (8 * index)) & 0xff
            u_events.append(('write', linear & MEMORY_MASK, byte,
                             instruction_flags))
            u_masks.append(instruction_mask)
            mirror = linear - MEMORY_SIZE if linear >= MEMORY_SIZE else linear + MEMORY_SIZE
            machine.mem_write(mirror, bytes((byte,)))

    def interrupt(_machine, number, _user):
        raise AssertionError(f'{case["name"]}: unexpected INT{number:02x}')

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, memory_read)
    uc.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(physical(load, initial_regs['ip']), 0, count=1000)
    if not stopped:
        raise AssertionError(f'{case["name"]}: original exceeded bounded execution')

    original_regs = {name: uc.reg_read(reg) & 0xffff
                     for name, reg in oracle.REG.items()}
    original_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    original_memory = bytes(uc.mem_read(0, MEMORY_SIZE))
    state_map = {
        'ax': c_call_result.work_value,
        'bx': c_call_result.second_source_cursor,
        'cx': c_call_result.packed_counts,
        'dx': c_call_result.width_state,
        'si': c_call_result.source_cursor,
        'di': c_call_result.destination_cursor,
        'bp': c_call_result.control,
        'sp': c_call_result.stack_offset,
        'ip': c_call_result.continuation,
    }
    c_registers = dict(initial_regs)
    c_registers.update(state_map)
    for name in REG_NAMES:
        actual = c_registers[name]
        if actual != original_regs[name]:
            raise AssertionError(f'{case["name"]}: {name} C={actual:04x}/ASM={original_regs[name]:04x}')
        if getattr(adapter_regs, name) != actual:
            raise AssertionError(f'{case["name"]}: adapter {name} differs from core')
    final_mask = flags_defined_after_previous
    if (c_call_result.flags ^ original_flags) & final_mask:
        raise AssertionError(f'{case["name"]}: defined flags C={c_call_result.flags:04x}/ASM={original_flags:04x}, mask={final_mask:04x}')
    if (adapter_regs.flags ^ c_call_result.flags) & final_mask:
        raise AssertionError(f'{case["name"]}: adapter flags differ from core')
    if c_memory != original_memory:
        address = next(i for i, (left, right) in enumerate(zip(c_memory, original_memory))
                       if left != right)
        raise AssertionError(f'{case["name"]}: whole RAM differs at {address:05x}')
    for entry, snapshot in instruction_snapshots.items():
        address = (load << 4) + entry
        if (c_memory[address:address + len(snapshot)] != snapshot or
                original_memory[address:address + len(snapshot)] != snapshot):
            raise AssertionError(f'{case["name"]}: executing source-preparation bytes changed at {entry:04x}')
    if len(c_events) != len(u_events):
        raise AssertionError(f'{case["name"]}: byte event count C/ASM={len(c_events)}/{len(u_events)}')
    for index, (native, original, mask) in enumerate(zip(c_events, u_events, u_masks)):
        if native[:3] != original[:3] or (native[3] ^ original[3]) & mask:
            raise AssertionError(f'{case["name"]}: byte event {index} differs {native}/{original}, mask={mask:04x}')
    for name in ('work_value', 'second_source_cursor', 'source_cursor',
                 'control', 'stack_offset', 'continuation'):
        if getattr(c_call_result, name) != expected[name]:
            raise AssertionError(f'{case["name"]}: independent {name} expected {expected[name]:04x}, got {getattr(c_call_result, name):04x}')
    row_address = physical(initial_regs['ds'], 0x6702)
    row_value = c_memory[row_address] | (c_memory[(row_address + 1) & MEMORY_MASK] << 8)
    if row_value != expected['row_advance']:
        raise AssertionError(f'{case["name"]}: independent row advance differs')
    return sites, edges


def check_trap_flag_preservation(lib):
    """TF is preserved by the core; original stepping would need INT 1."""
    memory, registers, flags, _load = prepare(cases()[0])
    call = make_call(registers, flags)
    trapped = DrawingSourceCall.from_buffer_copy(bytes(call))
    trapped.flags |= 0x0100
    plain_memory = bytearray(memory)
    trapped_memory = bytearray(memory)
    plain = lib.lmn_prepare_planar_source_rows_core(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(plain_memory),
        ctypes.byref(call), None)
    with_tf = lib.lmn_prepare_planar_source_rows_core(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(trapped_memory),
        ctypes.byref(trapped), None)
    if plain_memory != trapped_memory or (with_tf.flags ^ plain.flags) != 0x0100:
        raise AssertionError('source-row core did not preserve incoming TF')
    if bytes(plain)[:16] != bytes(with_tf)[:16] or \
            bytes(plain)[18:] != bytes(with_tf)[18:]:
        raise AssertionError('TF changed a non-flag source-row result')


def main():
    report = BUILD / 'drawing-source-differential.json'
    report.unlink(missing_ok=True)
    baseline = cases()
    native = library()
    sites, edges = set(), set()
    for case in baseline:
        found_sites, found_edges = compare(native, case)
        sites.update(found_sites)
        edges.update(found_edges)
    if sites != LOCAL_SITES or edges != EXPECTED_EDGES:
        raise AssertionError(
            f'coverage mismatch: missing sites={sorted(LOCAL_SITES-sites)}, '
            f'extra sites={sorted(sites-LOCAL_SITES)}, '
            f'missing edges={sorted(EXPECTED_EDGES-edges)}, '
            f'extra edges={sorted(edges-EXPECTED_EDGES)}')

    mutation_cases = (
        (1, 'store-overwrites-saved-BP-88bf', 'stale saved BP'),
        (2, 'mutant-one-vertical-skip', 'one vertical skip'),
        (3, 'mutant-missed-pitch-sub', 'missed source-cursor pitch subtraction'),
    )
    detected = []
    for mutation, case_name, label in mutation_cases:
        target = next(case for case in baseline if case['name'] == case_name)
        try:
            compare(library(mutation), target)
        except AssertionError as error:
            detected.append(dict(mutation=mutation, case=case_name,
                                 mutant=label, reason=str(error)))
        else:
            raise AssertionError(f'SOURCE_MUTATION={mutation} survived its kill case')
    if len(detected) != 3:
        raise AssertionError('not every compiled mutant was detected')
    check_trap_flag_preservation(native)

    paths = (
        'c/drawing_source.c', 'c/drawing_source.h', 'c/special_blit.h',
        'c/regs.h', 'c/lemmings_sym.h', 'tests/drawing_source.py',
        'tests/drawing_clip.py', 'tests/drawing_dirty.py',
        'tests/drawing_inputs.py', 'tests/special_blit.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/common.py',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/unpack.py', 'metadata/symbols.json', 'docs/drawing-source.md',
    )
    input_hashes = {path: sha((ROOT / path).read_bytes()) for path in paths}
    write_json(report, dict(
        image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), mutation_count=3,
        cases=baseline, mutations_detected=detected,
        core_only_tf_preserved=True,
        executed_instruction_addresses=sorted(sites),
        instruction_site_count=len(sites),
        branch_edges=[list(edge) for edge in sorted(edges)],
        branch_edge_count=len(edges), translated_code_bytes=244,
        original_instruction_snapshots=[
            dict(entry=entry, byte_count=size, sha256=sha(IMAGE[entry:entry + size]))
            for _name, entry, size, _sites, _shifted, _masked in ROUTINES],
        scoped_entries=[dict(name=name, entry=entry, byte_count=size,
                             instruction_sites=site_count,
                             bytes=IMAGE[entry:entry + size].hex(),
                             sha256=sha(IMAGE[entry:entry + size]))
                        for name, entry, size, site_count, _shifted, _masked
                        in ROUTINES],
        input_hashes=input_hashes,
        domain=('88BF..890D, 9140..916A, 93A7..93F5, 9810..983A source-row '
                'preparation only; live DS/SS and PUSH/store/POP aliases; '
                '20-bit contiguous word bytes; 16-bit SP/cursor arithmetic; '
                'no VGA setup, ports, target renderer execution, or RET')))
    print(f'PASS drawing source: {len(baseline)} cases, {len(sites)} sites, '
          f'{len(edges)} branch edges, 244 bytes, 3 compiled mutants detected')


if __name__ == '__main__':
    main()
