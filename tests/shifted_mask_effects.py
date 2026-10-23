"""Bounded original/native differential for shifted masked effect bodies."""
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR,
                     UC_HOOK_INSN)
from unicorn import x86_const as x

import aligned_masked as common
from aligned_masked import (TraceDevice, RasterBus, NATIVE_GUARD_EXIT,
    NATIVE_CALLBACK_EXIT, VerificationFailure, GuardExhaustion, Mismatch,
    require, physical, put16, put_byte, prime_device_stack, field, MEM)
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs
from minimap_vga import VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
import dat_io as oracle


# The finite CL=FF witness performs 65,536 VGA byte cycles. Raise the imported
# shared fixture caps for this test while retaining explicit bounded traces.
MAX_STEPS = 8_000_000
MAX_BUS_EVENTS = 1_000_000
MAX_VGA_EVENTS = 400_000
common.MAX_BUS_EVENTS = MAX_BUS_EVENTS
common.MAX_VGA_EVENTS = MAX_VGA_EVENTS

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
STARTS = {0: SYMS['PlanarShiftedMasked20Body']['address'],
          1: SYMS['PlanarShiftedMasked40Body']['address']}
RETURNS = {0: SYMS['PlanarShiftedMask20FarReturn']['address'],
           1: SYMS['PlanarShiftedMask40FarReturn']['address']}
ENDS = {mode: RETURNS[mode] + 1 for mode in STARTS}
EXPECTED_RANGE_HASHES = {
    0: '1be10dcca6b33ee3819d774b209fa4e18e4c760c9c93b9c884b67ec1e0a3c41b',
    1: '3bf36e4682b479a6842d87bd055ec981156ac0874b944dceba05f2111a065577',
}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
ALL_INS = {mode: {i.address: i for i in MD.disasm(
    IMAGE[STARTS[mode]:ENDS[mode]], STARTS[mode])}
    for mode in STARTS}
BODY_INS = {mode: {a: i for a, i in ALL_INS[mode].items()
                   if a != RETURNS[mode]} for mode in STARTS}
BRANCHES = {mode: {pc for pc, ins in BODY_INS[mode].items()
                   if ins.group(capstone.CS_GRP_JUMP) or
                   ins.mnemonic.startswith('loop')}
            for mode in STARTS}
EDGES = {}
for _mode in STARTS:
    _edges = {(pc, ins.operands[0].imm & 0xffff)
              for pc, ins in BODY_INS[_mode].items()
              if pc in BRANCHES[_mode]}
    _edges |= {(pc, pc + ins.size) for pc, ins in BODY_INS[_mode].items()
               if pc in BRANCHES[_mode] and ins.mnemonic != 'jmp'}
    EDGES[_mode] = _edges
LOGICAL = {'and', 'or', 'xor', 'test'}
ARITH = {'add', 'sub', 'dec', 'inc', 'mul', 'neg'}
DEFINED_FLAGS = 0x0fd7
UNDEFINED_AF_FLAGS = 0x0fc7


class Call(ctypes.Structure):
    _fields_ = [('initial_data_segment', ctypes.c_uint16),
                ('game_data_segment', ctypes.c_uint16),
                ('stack_segment', ctypes.c_uint16),
                ('stack_offset', ctypes.c_uint16),
                ('packed_counts', ctypes.c_uint16),
                ('mask_cursor', ctypes.c_uint16),
                ('destination_cursor', ctypes.c_uint16),
                ('control', ctypes.c_uint16),
                ('flags', ctypes.c_uint16)]


class Result(ctypes.Structure):
    _fields_ = [('work_value', ctypes.c_uint16),
                ('packed_counts', ctypes.c_uint16),
                ('port', ctypes.c_uint16),
                ('source_cursor', ctypes.c_uint16),
                ('mask_cursor', ctypes.c_uint16),
                ('destination_cursor', ctypes.c_uint16),
                ('control', ctypes.c_uint16),
                ('stack_offset', ctypes.c_uint16),
                ('source_segment', ctypes.c_uint16),
                ('output_segment', ctypes.c_uint16),
                ('flags', ctypes.c_uint16)]


def _library(directory, mutation=0):
    path = build(Path(directory) / f'shifted-mask-effects-m{mutation}.dll',
                 mutation, 'shifted_mask_effects')
    lib = ctypes.CDLL(str(path))
    for mode in STARTS:
        suffix = '20' if mode == 0 else '40'
        core = getattr(lib, f'lmn_draw_shifted_mask{suffix}_core')
        core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
        core.restype = Result
        adapter = getattr(lib, f'lmn_draw_shifted_mask{suffix}_adapter')
        adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.c_uint16,
                            ctypes.POINTER(RasterBus)]
        adapter.restype = None
    return lib


def _cases():
    result = []

    def add(mode, name, **kwargs):
        result.append(dict(mode=mode, name=name, seed=len(result), **kwargs))

    # Every BP enable nibble, all shift counts 1..7, and both taken/fallthrough
    # outcomes of the inner and outer row loops.
    for mode in (0, 1):
        for nibble in range(16):
            add(mode, f'{20 if mode == 0 else 40}-enable-{nibble:x}-shift-{nibble % 7 + 1}',
                width=2 + nibble % 3,
                height=1 if nibble in (0, 5, 10, 15) else 2,
                control=(nibble << 8) | (0x31 + nibble),
                shift=nibble % 7 + 1, row_advance=0x0007 + nibble,
                destination_advance=0x0009 + (nibble & 3),
                mask_bytes=(0x01, 0x00) if nibble == 0 else (),
                independent=nibble in (0, 5, 10, 15))

    for mode in (0, 1):
        prefix = 20 if mode == 0 else 40
        add(mode, f'{prefix}-DF-reverses-copy-and-STOS-sentinel-only',
            width=3, height=2, control=0xb051, shift=3, df=True,
            row_advance=0x0005, destination_advance=0x000b,
            mask_bytes=(0x01, 0x80, 0x55), independent=False)
        add(mode, f'{prefix}-shift-byte-zero-wraps-to-256', width=2,
            height=1, control=0x7002, shift=0, row_advance=0x0003,
            destination_advance=0x0007, mask_bytes=(0x01, 0x00),
            independent=True)
        add(mode, f'{prefix}-zero-CL-wraps-to-65536-RCR-steps', width=0,
            height=1, control=0x5003, shift=1, load=0x2345,
            row_advance=0x0001, destination_advance=0x0001)
        add(mode, f'{prefix}-zero-CH-wraps-to-256-rows', width=1,
            height=0, control=0x9004, shift=1, row_advance=0x0003,
            destination_advance=0x0005)
        add(mode, f'{prefix}-CL-FF-draw-count-wraps-to-65536', width=0xff,
            height=1, control=0xf005, shift=1, load=0x2345,
            destination_cursor=0xfffe, row_advance=0x0007,
            destination_advance=0x0003, independent=False)
        add(mode, f'{prefix}-20-bit-physical-and-offset-wrap', width=3,
            height=2, control=0xd006, shift=4, source_segment=0xffff,
            mask_cursor=0xfffe, destination_cursor=0xfffe,
            source_cursor=0xfffe, df=True, ss=0xffff, sp=0x0002,
            row_advance=0x0011, destination_advance=0x0009)
        add(mode, f'{prefix}-live-stack-overwrites-row-strides', width=2,
            height=2, control=0x8007, shift=2, same_segments=True,
            source_is_scratch=True, sp=0x6706,
            row_advance=0x0013, destination_advance=0x0019)
        add(mode, f'{prefix}-entry-save-overwrites-shift-byte', width=2,
            height=1, control=0xa008, shift=1, same_segments=True,
            source_segment=0x5000, sp=0xa94a,
            row_advance=0x0003, destination_advance=0x0005)
        add(mode, f'{prefix}-incoming-DS-distinct-from-relocated-frame',
            width=2, height=2, control=0x4009, shift=5,
            initial_ds=0x6000, source_segment=0x7100,
            row_advance=0x000b, destination_advance=0x000d)
        add(mode, f'{prefix}-SS-A000-stack-device', width=2, height=1,
            control=0x300a, shift=2, ss=0xa000, sp=0x5000,
            destination_cursor=0x5100, stack_device=True,
            row_advance=0x0003, destination_advance=0x0005)
        add(mode, f'{prefix}-source-segment-is-scratch-frame', width=3,
            height=2, control=0x600b, shift=2, source_is_scratch=True,
            mask_cursor=0x6748, source_cursor=0x6748,
            row_advance=0x0005, destination_advance=0x0007)

    return result


def _prepare(case):
    mode = case['mode']
    start = STARTS[mode]
    seed = case['seed']
    rng = random.Random(0x8ff7 + seed)
    load = case.get('load', (0x1010, 0x1213, 0x2345)[seed % 3])
    memory = bytearray(rng.randbytes(1 << 20))
    memory[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    game_ds = (load + 0x09a9) & 0xffff
    initial_ds = case.get('initial_ds', game_ds)
    ss = case.get('ss', 0x7000)
    sp = case.get('sp', 0x8000)
    if case.get('same_segments'):
        initial_ds = game_ds
        ss = game_ds
    source_segment = (game_ds if case.get('source_is_scratch') else
                      case.get('source_segment', 0x5000))

    # The shifted body's relocated MOV AX,09A9 switches to the relocated game
    # frame. Keep incoming DS distinct where requested; later saved ES/DS values
    # still decide which live frame supplies the scratch and row fields.
    put16(memory, initial_ds, field('GraphicsResourceSegment'), source_segment)
    put16(memory, initial_ds, field('DrawingActiveDestinationRowAdvance'),
          case.get('entry_destination_advance',
                   case.get('destination_advance', 0x0009)))
    put16(memory, game_ds, field('DrawingSourceRowAdvance'),
          case.get('row_advance', 0x0007))
    put16(memory, game_ds, field('DrawingActiveDestinationRowAdvance'),
          case.get('destination_advance', 0x0009))
    put_byte(memory, game_ds, field('DrawingLeftBitShiftByte'),
             case.get('shift', 1))

    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=start, ds=initial_ds, ss=ss, sp=sp,
                cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
                bx=case.get('mask_cursor', 0x1000),
                si=case.get('source_cursor', 0x2000),
                di=case.get('destination_cursor', 0x0410),
                bp=case.get('control', 0x5a31))
    flags = 2 | ((seed * 0x95) & 0xad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
          case.get('outer_cs', 0xbabe))
    for n, value in enumerate(case.get('mask_bytes', ())):
        put_byte(memory, source_segment, (regs['bx'] + n) & 0xffff, value)
    return memory, regs, flags, game_ds, source_segment


def _call_of(regs, game_ds, flags):
    return Call(regs['ds'], game_ds, regs['ss'], regs['sp'], regs['cx'],
                regs['bx'], regs['di'], regs['bp'], flags)


def _oracle_body(case, memory, regs, flags, device):
    u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 2 << 20)
    u.mem_write(0, bytes(memory) * 2)
    for name, reg in oracle.REG.items():
        u.reg_write(reg, regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS, flags)
    mode = case['mode']
    start = STARTS[mode]
    retf = RETURNS[mode]
    seen, edges = set(), set()
    previous = None
    finished = False
    steps = 0
    instruction_flags = flags
    flag_mask = DEFINED_FLAGS
    last_op = None
    callback_failure = []

    def stop_failure(uc, message):
        if not callback_failure:
            callback_failure.append(message)
        uc.emu_stop()

    def code(uc, pc, _size, _):
        nonlocal previous, finished, steps, instruction_flags, flag_mask, last_op
        off = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in BRANCHES[mode]:
            edges.add((previous, off))
        if off == retf:
            finished = True
            uc.emu_stop()
            return
        if off not in BODY_INS[mode] or uc.reg_read(oracle.REG['cs']) != regs['cs']:
            stop_failure(uc, f'{case["name"]}: original escaped at {off:04x}')
            return
        if last_op in LOGICAL:
            flag_mask = UNDEFINED_AF_FLAGS
        elif last_op in ARITH:
            flag_mask = DEFINED_FLAGS
        instruction_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        seen.add(off)
        previous = off
        steps += 1
        if steps > MAX_STEPS:
            stop_failure(uc, f'{case["name"]}: original step cap exhausted')
            return
        last_op = BODY_INS[mode][off].mnemonic

    def mem_read(uc, _access, address, size, _value, _):
        for index in range(size):
            raw = address + index
            p = raw & 0xfffff
            try:
                value = device.vga.read(device.memory, p, instruction_flags)
                device.events.add('read', p, value, instruction_flags, flag_mask)
                if len(device.vga.trace) > MAX_VGA_EVENTS:
                    device.vga.trace.pop()
                    device.vga_exhausted = True
                if raw >= (1 << 20) or VGA_BASE <= p < VGA_END:
                    uc.mem_write(raw, bytes((value,)))
            except BaseException as error:
                stop_failure(uc, f'{case["name"]}: original read callback failed: {error}')
                return
            if device.events.exhausted or device.vga_exhausted:
                uc.emu_stop()
                return

    def mem_write(uc, _access, address, size, value, _):
        for index in range(size):
            raw = address + index
            p = raw & 0xfffff
            byte = (value >> (8 * index)) & 0xff
            try:
                device.vga.write(device.memory, p, byte, instruction_flags)
                device.events.add('write', p, byte, instruction_flags, flag_mask)
                if len(device.vga.trace) > MAX_VGA_EVENTS:
                    device.vga.trace.pop()
                    device.vga_exhausted = True
                if raw >= (1 << 20):
                    uc.mem_write(p, bytes((byte,)))
            except BaseException as error:
                stop_failure(uc, f'{case["name"]}: original write callback failed: {error}')
                return
            if device.events.exhausted or device.vga_exhausted:
                uc.emu_stop()
                return

    def out(uc, _port, size, value, _):
        if size != 2:
            stop_failure(uc, f'{case["name"]}: original used non-word VGA output')
            return
        try:
            device.vga.out(uc.reg_read(oracle.REG['dx']), value, instruction_flags)
            device.events.add('out', uc.reg_read(oracle.REG['dx']), value,
                              instruction_flags, flag_mask)
            if len(device.vga.trace) > MAX_VGA_EVENTS:
                device.vga.trace.pop()
                device.vga_exhausted = True
        except BaseException as error:
            stop_failure(uc, f'{case["name"]}: original output callback failed: {error}')
            return
        if device.events.exhausted or device.vga_exhausted:
            uc.emu_stop()

    def intr(uc, number, _):
        stop_failure(uc, f'{case["name"]}: unexpected INT{number:02x}')

    hooks = [
        u.hook_add(UC_HOOK_CODE, code),
        u.hook_add(UC_HOOK_MEM_READ, mem_read),
        u.hook_add(UC_HOOK_MEM_WRITE, mem_write),
        u.hook_add(UC_HOOK_INSN, out, None, 1, 0, x.UC_X86_INS_OUT),
        u.hook_add(UC_HOOK_INTR, intr),
        u.hook_add(UC_HOOK_MEM_READ,
                   lambda uc, _a, p, n, _v, _d: _wrap_read(uc, p, n)),
        u.hook_add(UC_HOOK_MEM_WRITE,
                   lambda uc, _a, p, n, v, _d: _wrap_write(uc, p, n, v)),
    ]
    try:
        u.emu_start((regs['cs'] << 4) + start, 0, count=MAX_STEPS)
    except BaseException as error:
        raise VerificationFailure(
            f'{case["name"]}: bounded original execution failed: {error}')
    if callback_failure:
        if 'cap' in callback_failure[0]:
            raise GuardExhaustion(callback_failure[0])
        raise VerificationFailure(callback_failure[0])
    if device.events.exhausted or device.vga_exhausted:
        raise GuardExhaustion(f'{case["name"]}: original bus/device trace cap exhausted')
    device.check(case['name'] + ' original')
    if not finished:
        if steps >= MAX_STEPS:
            raise GuardExhaustion(f'{case["name"]}: original step cap exhausted')
        raise VerificationFailure(f'{case["name"]}: original did not stop at RETF')
    return u, seen, edges, hooks


def _wrap_read(uc, address, size):
    for index in range(size):
        raw = address + index
        if raw >= (1 << 20):
            uc.mem_write(raw, bytes(uc.mem_read(raw & 0xfffff, 1)))


def _wrap_write(uc, address, size, value):
    for index in range(size):
        raw = address + index
        if raw >= (1 << 20):
            uc.mem_write(raw & 0xfffff,
                         bytes(((value >> (8 * index)) & 0xff,)))


def _independent_planes(initial_planes, memory, regs, flags, case,
                        source_segment, game_ds):
    """Independent finite scratch shift and VGA set/reset footprint oracle."""
    mode = case['mode']
    width = regs['cx'] & 0xff
    rows = (regs['cx'] >> 8) & 0xff
    if width == 0 or rows != 1 or case.get('df') or case.get('stack_device'):
        raise VerificationFailure(f'{case["name"]}: invalid independent fixture')
    expected_memory = bytearray(memory)
    direction = -1 if flags & 0x0400 else 1
    cursor = regs['bx']
    scratch = 0x6748
    for _ in range(width):
        value = expected_memory[physical(source_segment, cursor)]
        expected_memory[physical(game_ds, scratch)] = value
        cursor = (cursor + direction) & 0xffff
        scratch = (scratch + direction) & 0xffff
    expected_memory[physical(game_ds, scratch)] = 0
    shift_count = expected_memory[physical(game_ds,
        field('DrawingLeftBitShiftByte'))]
    shift_count = shift_count or 256
    for _ in range(shift_count):
        address = physical(game_ds, 0x6748)
        first = expected_memory[address]
        carry = first & 1
        expected_memory[address] = first >> 1
        cursor = (0x6748 + 1) & 0xffff
        for _ in range(width):
            address = physical(game_ds, cursor)
            before = expected_memory[address]
            expected_memory[address] = (before >> 1) | (carry << 7)
            carry = before & 1
            cursor = (cursor + 1) & 0xffff

    planes = [bytearray(p) for p in initial_planes]
    destination = regs['di']
    enable = (regs['bp'] >> 8) & 0x0f
    set_reset = 0 if mode else 0x0f
    for _ in range(width + 1):
        mask = expected_memory[physical(game_ds, 0x6748 + (_ % 0x10000))]
        for plane in range(4):
            target = destination & 0xffff
            old = planes[plane][target]
            source = ((0xff if set_reset & (1 << plane) else 0)
                      if enable & (1 << plane) else 0xff)
            planes[plane][target] = ((source & mask) |
                                     (old & (~mask & 0xff)))
        destination = (destination + 1) & 0xffff
    return planes


def _compare_core(lib, case):
    memory, regs, flags, game_ds, source_segment = _prepare(case)
    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + STARTS[case['mode']])
    prime_device_stack(case, c_device)
    starting_planes = [bytearray(p) for p in c_device.vga.planes]
    call = _call_of(regs, game_ds, flags)
    suffix = '20' if case['mode'] == 0 else '40'
    c_result = getattr(lib, f'lmn_draw_shifted_mask{suffix}_core')(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(call), ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' C')

    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + STARTS[case['mode']])
    prime_device_stack(case, o_device)
    u, seen, edges, _hooks = _oracle_body(case, o_memory, regs, flags, o_device)
    for name, want in (
        ('ax', c_result.work_value), ('bx', c_result.mask_cursor),
        ('cx', c_result.packed_counts), ('dx', c_result.port),
        ('si', c_result.source_cursor), ('di', c_result.destination_cursor),
        ('bp', c_result.control), ('sp', c_result.stack_offset),
        ('ds', c_result.source_segment), ('es', c_result.output_segment),
        ('ss', regs['ss']), ('cs', regs['cs']),
        ('ip', RETURNS[case['mode']])):
        require(u.reg_read(oracle.REG[name]) == want,
                f'{case["name"]}: {name} C={want:04x}/ASM='
                f'{u.reg_read(oracle.REG[name]):04x}')
    oracle_flags = u.reg_read(x.UC_X86_REG_EFLAGS)
    require(((c_result.flags ^ oracle_flags) & DEFINED_FLAGS) == 0,
            f'{case["name"]}: defined flags C={c_result.flags:04x}/'
            f'ASM={oracle_flags:04x}')
    actual = bytes(u.mem_read(0, 1 << 20))
    require(actual == c_memory, f'{case["name"]}: full RAM differs')
    require(c_device.vga.state() == o_device.vga.state(),
            f'{case["name"]}: VGA plane/latch/register state differs')
    common.compare_event_traces(c_device.events, o_device.events, case['name'])
    if case.get('independent'):
        expected = _independent_planes(starting_planes, memory, regs, flags,
                                       case, source_segment, game_ds)
        require(c_device.vga.planes == expected,
                f'{case["name"]}: independent scratch/VGA expectation differs')
    report = dict(name=case['name'], mode=20 if case['mode'] == 0 else 40,
                  seed=case['seed'], input=dict(case,
                      relocated_game_data_segment=game_ds,
                      source_segment_initial=source_segment),
                  result={name: getattr(c_result, name)
                          for name, _field in c_result._fields_})
    del u, c_device, o_device
    return seen, edges, c_result, report


def _check_adapter_retf(lib, case):
    memory, regs, flags, game_ds, _source_segment = _prepare(case)
    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + STARTS[case['mode']])
    prime_device_stack(case, o_device)
    u, _seen, _edges, hooks = _oracle_body(case, o_memory, regs, flags, o_device)
    for hook in hooks:
        u.hook_del(hook)
    # Unicorn observes RETF's stack reads differently after hook removal. The
    # test keeps the isolated probe away from VGA/alias stacks and checks only
    # the direct instruction's architectural result against the C adapter.
    u.ctl_remove_cache(0, 2 << 20)
    u.emu_start((regs['cs'] << 4) + RETURNS[case['mode']], 0, count=1)
    original_regs = {name: u.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = u.reg_read(x.UC_X86_REG_EFLAGS)

    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + STARTS[case['mode']])
    native_regs = Regs(**regs, flags=flags)
    suffix = '20' if case['mode'] == 0 else '40'
    getattr(lib, f'lmn_draw_shifted_mask{suffix}_adapter')(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(native_regs), game_ds, ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' native core plus RETF adapter')
    for name in oracle.REG_NAMES:
        require(getattr(native_regs, name) == original_regs[name],
                f'{case["name"]}: live original RETF {name} C='
                f'{getattr(native_regs, name):04x}/ASM={original_regs[name]:04x}')
    require((native_regs.flags ^ original_flags) & DEFINED_FLAGS == 0,
            f'{case["name"]}: isolated original RETF flags differ')
    require(c_memory == bytes(u.mem_read(0, 1 << 20)),
            f'{case["name"]}: isolated original RETF RAM differs')
    require(c_device.vga.state() == o_device.vga.state(),
            f'{case["name"]}: isolated original RETF VGA state differs')
    del u, c_device, o_device


def _accounting():
    expected_sites = {0: 84, 1: 84}
    expected_bytes = {0: 165, 1: 164}
    for mode in STARTS:
        raw = IMAGE[STARTS[mode]:ENDS[mode]]
        if len(raw) != expected_bytes[mode] or len(ALL_INS[mode]) != expected_sites[mode]:
            raise VerificationFailure(
                f'{20 if mode == 0 else 40} body accounting changed: '
                f'{len(raw)} bytes/{len(ALL_INS[mode])} sites')
        if sha(raw) != EXPECTED_RANGE_HASHES[mode]:
            raise VerificationFailure(
                f'{20 if mode == 0 else 40} body range hash changed')
        if len(BODY_INS[mode]) != 83:
            raise VerificationFailure('expected body must stop before RETF')


def _worker(build_directory):
    report_path = BUILD / 'shifted-mask-effects-differential.json'
    report_path.unlink(missing_ok=True)
    _accounting()
    baseline = _library(build_directory)
    fixture_cases = _cases()
    seen = {mode: set() for mode in STARTS}
    edges = {mode: set() for mode in STARTS}
    case_reports = []
    for case in fixture_cases:
        if case.get('name', '').endswith('incoming-DS-distinct-from-relocated-frame'):
            load = case.get('load', (0x1010, 0x1213, 0x2345)[case['seed'] % 3])
            if case['initial_ds'] == ((load + 0x09a9) & 0xffff):
                raise VerificationFailure('incoming-DS fixture is not distinct')
        sites, case_edges, result, case_report = _compare_core(baseline, case)
        mode = case['mode']
        seen[mode] |= sites
        edges[mode] |= case_edges
        case_reports.append(case_report)
        gc.collect()

    for mode in STARTS:
        require(seen[mode] == set(BODY_INS[mode]),
                f'{20 if mode == 0 else 40} body-site coverage differs: '
                f'missing={sorted(set(BODY_INS[mode])-seen[mode])}')
        require(edges[mode] == EDGES[mode],
                f'{20 if mode == 0 else 40} branch-edge coverage differs: '
                f'missing={sorted(EDGES[mode]-edges[mode])}, '
                f'extra={sorted(edges[mode]-EDGES[mode])}')

    retf_names = {
        '20-enable-5-shift-6', '40-enable-a-shift-4',
        '20-incoming-DS-distinct-from-relocated-frame',
        '40-incoming-DS-distinct-from-relocated-frame'}
    retf_cases = [c for c in fixture_cases if c['name'] in retf_names]
    for case in retf_cases:
        _check_adapter_retf(baseline, case)
        gc.collect()

    sentinels = {
        1: next(c for c in fixture_cases
                if c['name'] == '20-enable-0-shift-1'),
        2: next(c for c in fixture_cases
                if c['name'] == '20-DF-reverses-copy-and-STOS-sentinel-only'),
        3: next(c for c in fixture_cases
                if c['name'] == '40-enable-5-shift-6'),
    }
    mutations = []
    for mutation in (1, 2, 3):
        mutant = _library(build_directory, mutation)
        case = sentinels[mutation]
        detected = None
        try:
            _compare_core(mutant, case)
        except Mismatch as mismatch:
            detected = dict(case=case['name'], reason=str(mismatch)[:300])
        if detected is None:
            raise VerificationFailure(
                f'compiled shifted effect mutation {mutation} survived')
        mutations.append(dict(mutation=mutation, **detected))
        gc.collect()

    regression_sentinels = [
        dict(mutation=1, behavior='RCR propagates the preceding SHR/RCR carry',
             case=sentinels[1]['name']),
        dict(mutation=2, behavior='scratch carry walk increments BX forward under DF',
             case=sentinels[2]['name']),
        dict(mutation=3, behavior='both shifted variants advance SI per row',
             case=sentinels[3]['name'])]

    input_paths = (
        'assets/vgalemmi.exe', 'c/shifted_mask_effects.c',
        'c/shifted_mask_effects.h', 'c/special_blit.h', 'c/regs.h',
        'c/lemmings_sym.h', 'tests/shifted_mask_effects.py',
        'tests/aligned_masked.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tools/common.py', 'tools/unpack.py',
        'tools/cbuild.py', 'tools/bounded_process.py', 'metadata/symbols.json',
        'build/unpack.json', 'src/planar_drawing.asm')
    report = dict(
        image='main', image_sha256=sha(IMAGE),
        ranges={str(20 if mode == 0 else 40): dict(
            inclusive=f'{STARTS[mode]:04X}..{RETURNS[mode]:04X}',
            range_sha256=sha(IMAGE[STARTS[mode]:ENDS[mode]]),
            physical_code_bytes=ENDS[mode]-STARTS[mode],
            translated_code_bytes=sum(ins.size for ins in BODY_INS[mode].values()),
            physical_instruction_sites=len(ALL_INS[mode]),
            body_instruction_sites=len(BODY_INS[mode]),
            body_instruction_addresses=sorted(seen[mode]),
            branch_edges=sorted([list(edge) for edge in edges[mode]]),
            branch_edge_count=len(edges[mode]),
            adapter_instruction_address=RETURNS[mode])
            for mode in STARTS},
        case_count=len(fixture_cases), cases=case_reports,
        mutation_count=len(mutations), mutations_detected=mutations,
        executed_instruction_addresses=sorted(
            set().union(*seen.values()) |
            {RETURNS[case['mode']] for case in retf_cases}),
        input_hashes={path: sha((ROOT / path).read_bytes())
                      for path in input_paths},
        retf_probe_case_count=len(retf_cases),
        retf_probe_cases=[case['name'] for case in retf_cases],
        retf_probe_exclusions=[c['name'] for c in fixture_cases
            if c.get('stack_device') or 'live-stack-overwrites' in c['name'] or
            'entry-save-overwrites-shift' in c['name']],
        regression_sentinels=regression_sentinels,
        dependencies=['metadata/symbols.json', 'c/special_blit.h',
                      'c/regs.h', 'tests/minimap_vga.py',
                      'tools/bounded_process.py'],
        event_limits=dict(bus_events=MAX_BUS_EVENTS,
                          vga_device_trace=MAX_VGA_EVENTS,
                          original_steps=MAX_STEPS),
        defined_flag_masks=dict(arithmetic='0x0FD7',
                                logical_with_AF_undefined='0x0FC7'),
        device_contract='tests/minimap_vga.py; unchained A000 64KiB aperture, four VGA planes/latches, Sequencer/Graphics Controller word ports, write mode zero replace with bit mask and set/reset; IRQs quiescent',
        quirks=[
            'Both bodies decrement active destination advance through incoming DS, then fetch the graphics segment from incoming DS:1FE4. The MOV AX,09A9 operand relocates to game_data_segment; saved ES/DS values and stack aliases determine the later live scratch/row segments.',
            'REP MOVSB and its zero sentinel follow DF; SHR/RCR scratch propagation and BX increments proceed forward, with INC preserving carry.',
            'The shift byte is unchecked: zero wraps its DEC loop to 256 passes. CL zero makes the RCR LOOP run 65,536 times; CL FF wraps the drawing count to 65,536. CH zero runs 256 rows.',
            'Both variants advance SI by the live DS:6702 word and DI by the live DS:6704 word after each row. 20 selects set/reset F; 40 selects zero. SS saves and VGA mirror writes remain live.'],
        domain='Constructed 1MiB RAM and quiescent IRQs. Discovered normal entries are static jumps 8902->8FF7 and 890B->909C; other indirect/modified-code incoming domains remain open. C cores stop after POP DS at 909A/913E, and adapters consume live RETF 909B/913F. The MOV AX,09A9 immediate is relocated in the loaded image; live stack aliases can alter restored DS/ES. Isolated RETF probes exclude VGA-backed and stack/frame-alias cases because Unicorn reads after hook removal do not reproduce the hooked device view.')
    write_json(report_path, report)
    print(f'PASS shifted mask effects: {len(fixture_cases)} cases, '
          f'{sum(map(len, seen.values()))} body sites, '
          f'{sum(map(len, edges.values()))} branch edges; '
          f'{len(retf_cases)} original RETF probes; '
          f'{len(mutations)} compiled mutations detected')


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'shifted-mask-effects-differential.json').unlink(missing_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        _worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='shifted-mask-effects-', parent=BUILD) as temp:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--worker', temp], cwd=ROOT, timeout=180,
                             memory_mib=512, check=False)
        if result.returncode == NATIVE_GUARD_EXIT:
            raise GuardExhaustion(
                'native callback worker exited on a finite trace guard')
        if result.returncode == NATIVE_CALLBACK_EXIT:
            raise VerificationFailure(
                'native callback worker exited on a callback error')
        if result.returncode != 0:
            raise VerificationFailure(
                f'bounded worker exited with status {result.returncode}')


if __name__ == '__main__':
    main()
