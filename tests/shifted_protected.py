"""Bounded original/native checks for the shifted protected VGA body."""
import ctypes
import gc
import hashlib
import os
import random
import struct
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR,
                     UC_HOOK_INSN)
from unicorn import x86_const as x

import aligned_protected as common
from aligned_protected import (TraceDevice, RasterBus, READ, WRITE, OUT,
    NATIVE_GUARD_EXIT, NATIVE_CALLBACK_EXIT, VerificationFailure,
    GuardExhaustion, Mismatch, require, physical, put16, put_byte,
    prime_device_stack, field, compare_event_traces, DEFINED_FLAGS,
    UNDEFINED_AF_FLAGS, LOGICAL, ARITH, VGA_BASE, VGA_END)
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs, MEM
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
START = SYMS['PlanarShiftedMasked8000Body']['address']
RETF = SYMS['PlanarShiftedProtectedFarReturn']['address']
END = RETF + 1
UNKNOWN = {0x8cf4}
EXPECTED_RANGE_HASH = '1f8b94951806ed0b13a5638a2699eef347de12914571472a78ba5b611b7cf558'
MAX_STEPS = 8_000_000
MAX_BUS_EVENTS = 1_000_000
MAX_VGA_EVENTS = 300_000
common.MAX_BUS_EVENTS = MAX_BUS_EVENTS
common.MAX_VGA_EVENTS = MAX_VGA_EVENTS
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
RAW_INS = {i.address: i for i in MD.disasm(IMAGE[START:END], START)}
KNOWN_INS = {a: i for a, i in RAW_INS.items() if a not in UNKNOWN}
BODY_INS = {a: i for a, i in KNOWN_INS.items() if a != RETF}
BRANCHES = {pc for pc, ins in BODY_INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or
            ins.mnemonic.startswith('loop')}
EDGES = {(pc, ins.operands[0].imm & 0xffff)
         for pc, ins in BODY_INS.items() if pc in BRANCHES}
EDGES |= {(pc, pc + ins.size) for pc, ins in BODY_INS.items()
          if pc in BRANCHES and ins.mnemonic != 'jmp'}


def exit_worker(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def _wrap_read(uc, address, size):
    for i in range(size):
        raw = address + i
        if raw >= (1 << 20):
            uc.mem_write(raw, bytes(uc.mem_read(raw & 0xfffff, 1)))


def _wrap_write(uc, address, size, value):
    for i in range(size):
        raw = address + i
        if raw >= (1 << 20):
            uc.mem_write(raw & 0xfffff,
                         bytes(((value >> (8 * i)) & 0xff,)))


def cases():
    result = []

    def add(name, **kwargs):
        result.append(dict(name=name, seed=len(result), **kwargs))

    add('two-planes-shifted-source-protection-footprint', plane_limit=2,
        width=2, height=2, shift_count=1, independent=True,
        source_bytes=(0x01, 0xc3, 0x6d, 0x92))
    add('three-planes-OR-with-read-mode-one-mask', plane_limit=3,
        width=3, height=1, shift_count=2, independent=True)
    add('four-planes-protects-existing-plane-three-pixels', plane_limit=4,
        width=3, height=2, shift_count=2, independent=True,
        plane3_seed=0xaa)
    add('one-plane-ORs-source-only-where-plane-three-is-clear', plane_limit=1,
        width=2, height=1, shift_count=1, independent=True)
    add('zero-plane-count-underflows-through-four-passes', plane_limit=0,
        width=2, height=1, shift_count=1, independent=True)
    add('five-plane-count-still-stops-after-four', plane_limit=5,
        width=1, height=1, shift_count=1)
    add('ff-plane-count-still-stops-after-four', plane_limit=0xff,
        width=1, height=2, shift_count=1)
    add('DF-reverses-copy-sentinel-and-output-cursors', plane_limit=3,
        width=2, height=2, shift_count=2, df=True,
        source_cursor=0x2100, destination_cursor=0x0430,
        independent=True)
    add('zero-shift-byte-wraps-to-256-shifts', plane_limit=2,
        width=1, height=1, shift_count=0, independent=True)
    add('zero-CL-wraps-to-65536-RCR-iterations', plane_limit=1,
        width=0, height=1, shift_count=1)
    add('zero-CH-wraps-to-256-rows', plane_limit=1, width=1,
        height=0, shift_count=1, independent=True)
    add('CL-FF-wraps-output-loop-to-65536-bytes', plane_limit=1,
        width=0xff, height=1, shift_count=1)
    add('seven-source-shifts-and-multiline-carry', plane_limit=2,
        width=3, height=2, shift_count=7)
    add('twenty-bit-source-and-stack-wrap-with-DF', plane_limit=2,
        width=2, height=1, shift_count=1, source_segment=0xffff,
        source_cursor=0xfffe, destination_cursor=0xfffe, ss=0xffff,
        sp=0x0010, df=True)
    add('entry-push-overwrites-graphics-segment-word', plane_limit=1,
        width=1, height=1, shift_count=1, same_segments=True, sp=0x1fe6)
    add('live-stack-saves-alias-row-and-scratch-fields', plane_limit=1,
        width=1, height=1, shift_count=1, same_segments=True, sp=0x670a)
    add('source-overlaps-shift-scratch-buffer', plane_limit=2,
        width=2, height=1, shift_count=1, source_segment='game_ds',
        source_cursor=0x6706)
    add('incoming-DS-distinct-from-relocated-game-DS', plane_limit=2,
        width=2, height=1, shift_count=1, initial_data_segment=0x6000,
        independent=True)
    add('SS-aperture-saves-restored-from-plane-three', plane_limit=1,
        width=1, height=1, shift_count=1, ss=0xa000, sp=0x5000,
        destination_cursor=0x5100, stack_device=True,
        vga_stack_plane3=((0x4ff2, 0x01), (0x4ff3, 0x01),
                          (0x4ff4, 0xb9), (0x4ff5, 0x19),
                          (0x4ff6, 0x00), (0x4ff7, 0x50),
                          (0x4ff8, 0x01), (0x4ff9, 0x01),
                          (0x4ffa, 0x00), (0x4ffb, 0x20),
                          (0x4ffc, 0x00), (0x4ffd, 0x51),
                          (0x4ffe, 0xb9), (0x4fff, 0x19)))
    add('SP-FFFE-return-frame-wrap', plane_limit=1, width=1,
        height=1, shift_count=1, sp=0xfffe, return_boundary=True)
    return result


def prepare(case):
    rng = random.Random(0x8b42 + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    memory = bytearray(rng.randbytes(1 << 20))
    memory[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    game_ds = (load + 0x09a9) & 0xffff
    initial_ds = case.get('initial_data_segment', game_ds)
    ss = case.get('ss', 0x7000)
    sp = case.get('sp', 0x8000)
    source_segment = case.get('source_segment', 0x5000)
    if source_segment == 'game_ds':
        source_segment = game_ds
    if case.get('same_segments'):
        ss = game_ds
        initial_ds = game_ds
    put16(memory, game_ds, field('DrawingSourcePlaneExtent'),
          case.get('plane_extent', 0x0023))
    put16(memory, game_ds, field('DrawingSourceRowAdvance'),
          case.get('source_row_advance', 0x0007))
    put16(memory, game_ds, field('DrawingActiveDestinationRowAdvance'),
          case.get('destination_row_advance', 0x0009))
    put_byte(memory, game_ds, field('DrawingLeftBitShiftByte'),
             case.get('shift_count', 1))
    put16(memory, initial_ds, field('GraphicsResourceSegment'), source_segment)
    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=initial_ds, ss=ss, sp=sp,
                cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
                dx=((case['plane_limit'] & 0xff) << 8) |
                   case.get('low_state', 0x6d),
                si=case.get('source_cursor', 0x2000),
                di=case.get('destination_cursor', 0x0410))
    flags = 2 | ((case['seed'] * 0x95) & 0xad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
          case.get('outer_cs', 0xbabe))
    step = -1 if flags & 0x0400 else 1
    for n, value in enumerate(case.get('source_bytes', ())):
        put_byte(memory, source_segment, (regs['si'] + n * step) & 0xffff,
                 value)
    return memory, regs, flags, game_ds


def library(build_directory, mutation=0):
    path = build(Path(build_directory) / f'shifted-protected-m{mutation}.dll',
                 mutation, 'shifted_protected')
    lib = ctypes.CDLL(str(path))

    class Call(ctypes.Structure):
        _fields_ = [('initial_data_segment', ctypes.c_uint16),
                    ('game_data_segment', ctypes.c_uint16),
                    ('stack_segment', ctypes.c_uint16),
                    ('stack_offset', ctypes.c_uint16),
                    ('packed_counts', ctypes.c_uint16),
                    ('width_state', ctypes.c_uint16),
                    ('source_cursor', ctypes.c_uint16),
                    ('destination_cursor', ctypes.c_uint16),
                    ('flags', ctypes.c_uint16)]

    class Result(ctypes.Structure):
        _fields_ = [('work_value', ctypes.c_uint16),
                    ('packed_counts', ctypes.c_uint16),
                    ('port', ctypes.c_uint16),
                    ('source_cursor', ctypes.c_uint16),
                    ('destination_cursor', ctypes.c_uint16),
                    ('plane_counter', ctypes.c_uint16),
                    ('stack_offset', ctypes.c_uint16),
                    ('source_segment', ctypes.c_uint16),
                    ('output_segment', ctypes.c_uint16),
                    ('flags', ctypes.c_uint16)]

    lib.lmn_draw_shifted_protected_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    lib.lmn_draw_shifted_protected_core.restype = Result
    lib.lmn_draw_shifted_protected_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint16, ctypes.POINTER(RasterBus)]
    lib.lmn_draw_shifted_protected_adapter.restype = None
    lib._ProtectedCall = Call
    return lib


def call_of(lib, regs, game_ds, flags):
    return lib._ProtectedCall(regs['ds'], game_ds, regs['ss'], regs['sp'],
                              regs['cx'], regs['dx'], regs['si'],
                              regs['di'], flags)


def oracle_body(case, memory, regs, flags, device):
    u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 2 << 20)
    u.mem_write(0, bytes(memory) * 2)
    for name, reg in oracle.REG.items():
        u.reg_write(reg, regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS, flags)
    seen = set()
    edges = set()
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
        if previous in BRANCHES:
            edges.add((previous, off))
        if off == RETF:
            finished = True
            uc.emu_stop()
            return
        if off not in BODY_INS or uc.reg_read(oracle.REG['cs']) != regs['cs']:
            stop_failure(uc, f'{case["name"]}: original escaped at {off:04x}')
            return
        if last_op in LOGICAL or last_op in {'shr', 'rcr'}:
            flag_mask = UNDEFINED_AF_FLAGS
        elif last_op in ARITH:
            flag_mask = DEFINED_FLAGS
        instruction_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        seen.add(off)
        previous = off
        steps += 1
        if steps > MAX_STEPS:
            stop_failure(uc,
                f'{case["name"]}: original step cap {MAX_STEPS} exhausted')
            return
        last_op = BODY_INS[off].mnemonic

    def mem_read(uc, _access, address, size, _value, _):
        for i in range(size):
            raw = address + i
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
                device.record_error(error)
                stop_failure(uc,
                    f'{case["name"]}: original read callback failed: {error}')
                return
            if device.events.exhausted or device.vga_exhausted:
                uc.emu_stop()
                return

    def mem_write(uc, _access, address, size, value, _):
        for i in range(size):
            raw = address + i
            p = raw & 0xfffff
            byte = (value >> (8 * i)) & 0xff
            try:
                device.vga.write(device.memory, p, byte, instruction_flags)
                device.events.add('write', p, byte, instruction_flags, flag_mask)
                if len(device.vga.trace) > MAX_VGA_EVENTS:
                    device.vga.trace.pop()
                    device.vga_exhausted = True
                if raw >= (1 << 20):
                    uc.mem_write(p, bytes((byte,)))
            except BaseException as error:
                device.record_error(error)
                stop_failure(uc,
                    f'{case["name"]}: original write callback failed: {error}')
                return
            if device.events.exhausted or device.vga_exhausted:
                uc.emu_stop()
                return

    def out(uc, _port, size, value, _):
        if size != 2:
            stop_failure(uc, f'{case["name"]}: non-word VGA output')
            return
        port = uc.reg_read(x.UC_X86_REG_DX)
        try:
            device.vga.out(port, value, instruction_flags)
            device.events.add('out', port, value, instruction_flags, flag_mask)
            if len(device.vga.trace) > MAX_VGA_EVENTS:
                device.vga.trace.pop()
                device.vga_exhausted = True
        except BaseException as error:
            device.record_error(error)
            stop_failure(uc,
                f'{case["name"]}: original VGA output failed: {error}')

    def intr(uc, number, _):
        stop_failure(uc, f'{case["name"]}: unexpected INT{number:02x}')

    hooks = (
        u.hook_add(UC_HOOK_CODE, code),
        u.hook_add(UC_HOOK_MEM_READ, mem_read),
        u.hook_add(UC_HOOK_MEM_WRITE, mem_write),
        u.hook_add(UC_HOOK_INSN, out, None, 1, 0, x.UC_X86_INS_OUT),
        u.hook_add(UC_HOOK_INTR, intr),
        u.hook_add(UC_HOOK_MEM_READ,
                   lambda uc, a, p, n, v, d: _wrap_read(uc, p, n)),
        u.hook_add(UC_HOOK_MEM_WRITE,
                   lambda uc, a, p, n, v, d: _wrap_write(uc, p, n, v)))
    try:
        u.emu_start((regs['cs'] << 4) + START, 0, count=MAX_STEPS)
    except BaseException as error:
        raise VerificationFailure(
            f'{case["name"]}: bounded original execution failed: {error}')
    if callback_failure:
        if 'cap' in callback_failure[0]:
            raise GuardExhaustion(callback_failure[0])
        raise VerificationFailure(callback_failure[0])
    device.check(case['name'] + ' original')
    if not finished:
        raise VerificationFailure(f'{case["name"]}: original did not stop at RETF')
    if steps >= MAX_STEPS:
        raise GuardExhaustion(f'{case["name"]}: original step budget exhausted')
    return u, seen, edges, hooks


def _read16(memory, segment, offset):
    p = physical(segment, offset)
    return memory[p] | (memory[(p + 1) & 0xfffff] << 8)


def independent_shifted_planes(initial_planes, memory, regs, flags, case,
                                game_ds):
    """Independent packed-byte shift and plane-3 protection expectation."""
    work = bytearray(memory)
    expected = [bytearray(p) for p in initial_planes]
    initial_ds = regs['ds']
    source_segment = _read16(work, initial_ds, field('GraphicsResourceSegment'))
    active_field = physical(initial_ds,
        field('DrawingActiveDestinationRowAdvance'))
    work[active_field] = (work[active_field] - 1) & 0xff
    high = (active_field + 1) & 0xfffff
    borrow = 1 if work[active_field] == 0xff else 0
    work[high] = (work[high] - borrow) & 0xff
    width = regs['cx'] & 0xff
    row_count = (regs['cx'] >> 8) & 0xff or 256
    direction = -1 if flags & 0x0400 else 1
    input_limit = (regs['dx'] >> 8) & 0xff
    pass_count = input_limit if 1 <= input_limit <= 3 else 4
    first_source = regs['si']
    first_destination = regs['di']

    for plane_index in range(pass_count):
        source = first_source
        for _ in range(plane_index):
            source = (source + _read16(
                work, game_ds, field('DrawingSourcePlaneExtent'))) & 0xffff
        destination = first_destination
        for _row in range(row_count):
            copy_cursor = source
            scratch = 0x6706
            for _ in range(width):
                value = work[physical(source_segment, copy_cursor)]
                work[physical(game_ds, scratch)] = value
                copy_cursor = (copy_cursor + direction) & 0xffff
                scratch = (scratch + direction) & 0xffff
            work[physical(game_ds, scratch)] = 0

            shift_count = work[physical(game_ds,
                field('DrawingLeftBitShiftByte'))]
            shift_passes = shift_count or 256
            for _ in range(shift_passes):
                base = physical(game_ds, 0x6706)
                first = work[base]
                carry = first & 1
                work[base] = first >> 1
                cursor = 0x6707
                for _ in range(width):
                    at = physical(game_ds, cursor)
                    before = work[at]
                    work[at] = (before >> 1) | (carry << 7)
                    carry = before & 1
                    cursor = (cursor + 1) & 0xffff

            draw_count = (width + 1) & 0xff or 0x10000
            cursor = 0x6706
            for _ in range(draw_count):
                target = destination & 0xffff
                allow = (~expected[3][target]) & 0xff
                value = work[physical(game_ds, cursor)]
                expected[plane_index][target] |= value & allow
                cursor = (cursor + direction) & 0xffff
                destination = (destination + direction) & 0xffff
            source = (copy_cursor + _read16(
                work, game_ds, field('DrawingSourceRowAdvance'))) & 0xffff
            destination = (destination + _read16(
                work, game_ds, field('DrawingActiveDestinationRowAdvance'))) & 0xffff
    return expected


def compare_core(lib, case):
    memory, regs, flags, game_ds = prepare(case)
    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + START)
    c_device.label = case['name']
    prime_device_stack(case, c_device)
    starting_planes = [bytearray(p) for p in c_device.vga.planes]
    call = call_of(lib, regs, game_ds, flags)
    c_result = lib.lmn_draw_shifted_protected_core(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(call), ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' C')

    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + START)
    prime_device_stack(case, o_device)
    u, seen, edges, _hooks = oracle_body(case, o_memory, regs, flags, o_device)
    for name, want in (
        ('ax', c_result.work_value), ('bx', regs['bx']),
        ('cx', c_result.packed_counts), ('dx', c_result.port),
        ('si', c_result.source_cursor), ('di', c_result.destination_cursor),
        ('bp', c_result.plane_counter), ('sp', c_result.stack_offset),
        ('ds', c_result.source_segment), ('es', c_result.output_segment),
        ('ss', regs['ss']), ('cs', regs['cs']), ('ip', RETF)):
        require(u.reg_read(oracle.REG[name]) == want,
                f'{case["name"]}: {name} C={want:04x}/ASM='
                f'{u.reg_read(oracle.REG[name]):04x}')
    oracle_flags = u.reg_read(x.UC_X86_REG_EFLAGS)
    require(((c_result.flags ^ oracle_flags) & DEFINED_FLAGS) == 0,
            f'{case["name"]}: defined flags C={c_result.flags:04x}/'
            f'ASM={oracle_flags:04x}')
    actual = bytes(u.mem_read(0, 1 << 20))
    require(actual == c_memory, f'{case["name"]}: full RAM differs')
    relocated_image = relocated(IMAGE, ORACLE['relocations'], regs['cs'])
    code_start = (regs['cs'] << 4) + START
    require(actual[code_start:code_start + END - START] ==
            relocated_image[START:END],
            f'{case["name"]}: executing planar bytes changed')
    require(c_device.vga.state() == o_device.vga.state(),
            f'{case["name"]}: VGA planes/latches/registers differ')
    compare_event_traces(c_device.events, o_device.events, case['name'])
    if case.get('independent'):
        expected = independent_shifted_planes(starting_planes, memory, regs,
                                              flags, case, game_ds)
        if c_device.vga.planes != expected:
            diff = next((p, n) for p in range(4)
                        for n, (a, b) in enumerate(zip(c_device.vga.planes[p],
                                                       expected[p])) if a != b)
            plane, offset = diff
            raise Mismatch(f'{case["name"]}: independent shifted/protection '
                           f'footprint differs at {plane}:{offset:04x}')
    report = dict(name=case['name'], seed=case['seed'], input=dict(
        case, relocated_game_data_segment=game_ds),
        result={name: getattr(c_result, name)
                for name, _field in c_result._fields_})
    del u, c_device, o_device
    return seen, edges, c_result, report


def check_adapter_retf(lib, case):
    memory, regs, flags, game_ds = prepare(case)
    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + START)
    prime_device_stack(case, o_device)
    u, _seen, _edges, hooks = oracle_body(case, o_memory, regs, flags, o_device)
    for hook in hooks:
        u.hook_del(hook)
    u.ctl_remove_cache(0, 2 << 20)
    u.emu_start((regs['cs'] << 4) + RETF, 0, count=1)
    original_regs = {name: u.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = u.reg_read(x.UC_X86_REG_EFLAGS)

    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + START)
    prime_device_stack(case, c_device)
    native_regs = Regs(**regs, flags=flags)
    lib.lmn_draw_shifted_protected_adapter(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(native_regs), game_ds, ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' core plus RETF adapter')
    for name in oracle.REG_NAMES:
        require(getattr(native_regs, name) == original_regs[name],
                f'{case["name"]}: original RETF {name} C='
                f'{getattr(native_regs, name):04x}/ASM='
                f'{original_regs[name]:04x}')
    require((native_regs.flags ^ original_flags) & DEFINED_FLAGS == 0,
            f'{case["name"]}: original RETF flags differ')
    require(c_memory == bytes(u.mem_read(0, 1 << 20)),
            f'{case["name"]}: original RETF RAM differs')
    require(c_device.vga.state() == o_device.vga.state(),
            f'{case["name"]}: RETF VGA state differs')
    del u, c_device, o_device


def _accounting():
    if len(IMAGE[START:END]) != 548:
        raise VerificationFailure('protected8B42 physical range changed size')
    if len(RAW_INS) != 307 or len(KNOWN_INS) != 306 or len(BODY_INS) != 305:
        raise VerificationFailure(
            f'protected8B42 site accounting changed: {len(RAW_INS)} raw, '
            f'{len(KNOWN_INS)} known, {len(BODY_INS)} body')
    if sum(i.size for i in RAW_INS.values()) != 548:
        raise VerificationFailure('protected8B42 decoded byte accounting changed')
    if sha(IMAGE[START:END]) != EXPECTED_RANGE_HASH:
        raise VerificationFailure('protected8B42 static range hash changed')
    if IMAGE[0x8cf4] != 0x90:
        raise VerificationFailure('UNKNOWN 8CF4 byte changed')


def worker(build_directory):
    report_path = BUILD / 'shifted-protected-differential.json'
    report_path.unlink(missing_ok=True)
    _accounting()
    baseline = library(build_directory)
    fixture_cases = cases()
    seen = set()
    edges = set()
    case_reports = []
    for case in fixture_cases:
        sites, case_edges, _result, report = compare_core(baseline, case)
        seen |= sites
        edges |= case_edges
        case_reports.append(report)
        gc.collect()
    if seen != set(BODY_INS):
        raise VerificationFailure(f'C body site coverage differs: '
            f'missing={sorted(set(BODY_INS)-seen)}, '
            f'extra={sorted(seen-set(BODY_INS))}')
    if edges != EDGES:
        raise VerificationFailure(f'branch edge coverage differs: '
            f'missing={sorted(EDGES-edges)}, extra={sorted(edges-EDGES)}')

    retf_names = {
        'two-planes-shifted-source-protection-footprint',
        'four-planes-protects-existing-plane-three-pixels',
        'incoming-DS-distinct-from-relocated-game-DS'}
    retf_cases = [c for c in fixture_cases if c['name'] in retf_names]
    for case in retf_cases:
        check_adapter_retf(baseline, case)
        gc.collect()

    mutation_sentinels = {
        1: next(c for c in fixture_cases
                if c['name'] == 'two-planes-shifted-source-protection-footprint'),
        2: next(c for c in fixture_cases
                if c['name'] == 'DF-reverses-copy-sentinel-and-output-cursors'),
        3: next(c for c in fixture_cases
                if c['name'] == 'four-planes-protects-existing-plane-three-pixels')}
    mutations = []
    for mutation in (1, 2, 3):
        mutant = library(build_directory, mutation)
        case = mutation_sentinels[mutation]
        detected = None
        try:
            compare_core(mutant, case)
        except Mismatch as mismatch:
            detected = dict(case=case['name'], reason=str(mismatch)[:300])
        if detected is None:
            raise VerificationFailure(
                f'compiled shifted protected mutation {mutation} survived')
        mutations.append(dict(mutation=mutation, **detected))
        gc.collect()

    input_paths = (
        'assets/vgalemmi.exe', 'c/shifted_protected.c',
        'c/shifted_protected.h', 'c/special_blit.h', 'c/regs.h',
        'c/lemmings_sym.h', 'tests/shifted_protected.py',
        'tests/aligned_protected.py', 'tests/minimap_vga.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/common.py',
        'tools/unpack.py', 'tools/cbuild.py', 'tools/bounded_process.py',
        'metadata/symbols.json', 'build/unpack.json',
        'src/planar_drawing.asm', 'docs/shifted-drawing.md',
        'docs/shifted-protected.md')
    report = dict(
        image='main', image_sha256=sha(IMAGE),
        range_inclusive=f'{START:04X}..{RETF:04X}',
        range_sha256=sha(IMAGE[START:END]),
        unknown_bytes=[dict(address=a, value=IMAGE[a]) for a in sorted(UNKNOWN)],
        case_count=len(fixture_cases), cases=case_reports,
        mutation_count=len(mutations), mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen | ({RETF} if retf_cases else set())),
        body_instruction_addresses=sorted(seen),
        branch_edges=sorted([list(e) for e in edges]),
        physical_code_bytes=548, decoded_code_bytes=547,
        translated_code_bytes=sum(i.size for i in BODY_INS.values()),
        c_body_code_bytes=sum(i.size for i in BODY_INS.values()),
        adapter_code_bytes=1, physical_instruction_sites=306,
        c_body_instruction_sites=305, adapter_instruction_sites=1,
        adapter_instruction_addresses=[RETF], branch_edge_count=len(edges),
        retf_probe_case_count=len(retf_cases),
        retf_probe_cases=[c['name'] for c in retf_cases],
        retf_probe_exclusions=[c['name'] for c in fixture_cases
            if c.get('stack_device') or c.get('return_boundary') or
            'live-stack' in c['name']],
        unknown_sites_excluded=sorted(UNKNOWN),
        event_limits=dict(bus_events=MAX_BUS_EVENTS,
                          vga_device_trace=MAX_VGA_EVENTS,
                          original_steps=MAX_STEPS),
        defined_flag_masks=dict(arithmetic='0x0FD7',
                                logical_or_shift_AF_undefined='0x0FC7'),
        input_hashes={p: sha((ROOT / p).read_bytes()) for p in input_paths},
        dependencies=['metadata/symbols.json', 'c/special_blit.h',
                      'c/regs.h', 'tests/minimap_vga.py',
                      'tools/bounded_process.py'],
        device_contract='tests/minimap_vga.py; unchained A000 64KiB aperture, four VGA planes/latches, Sequencer and Graphics Controller word ports, read mode 1 plane-3 comparison, write mode 0 OR with bit-mask merge; IRQs quiescent',
        quirks=[
            'The immediate MOV AX,09A9 is relocated to game_data_segment. Initial DS supplies the first 6704 decrement and graphics segment at DS:1FE4; saved/live DS and ES then route scratch, row, plane-extent and shift reads.',
            'The source copy and zero sentinel follow incoming DF. SHR/RCR scratch propagation increments SI forward, preserving carry through INC; output LODS/STOS follow DF.',
            'The read-mode-1 comparison reads plane 3 with compare/care 08, NOT AH becomes the mask, and the bit-mask cycle ORs source data only into currently clear plane-3 bits. Set/reset data is zero with set/reset disabled; later passes select planes 1, 2 and 3.',
            'Input plane count 0 underflows and still executes four passes; counts above four also stop after the fourth. The fourth pass has no BP test or decrement. Plane-source advances use live ES:66F8.',
            'Shift count 0 wraps to 256 shifts. CL 0 makes each RCR LOOP iterate 65,536 times; CL FF wraps the output loop to 65,536 bytes. CH 0 runs 256 rows. These unchecked cases remain bounded fixtures only.',
            'Every row reads live DS:6702 and DS:6704 after source copy and output. The entry decrement to DS:6704 occurs through incoming DS, and SS saves can alias those words and scratch state. BX is untouched.'],
        domain='Constructed one-MiB RAM and a quiescent VGA fixture. Static analysis found one normal incoming edge, 88F9->8B42, no calls or outgoing direct edges, and UNKNOWN 8CF4 remains unresolved/excluded even though its stored byte is 90. The C core stops after POP DS at 8D64; the unchanged RETF at 8D65 is consumed only by the adapter. RETF probes exclude VGA-backed stacks, wrapped SP, and SS/save aliases because Unicorn reads after hook removal cannot preserve the prior device/access view. Indirect and modified-code entries, scratch allocation limits, source producer validity, and asynchronous IRQ ownership remain open.')
    write_json(report_path, report)
    print(f'PASS shifted protected: {len(fixture_cases)} cases, '
          f'{len(seen)} body sites, {len(edges)} branch edges; '
          f'{len(retf_cases)} original RETF probes; '
          f'{len(mutations)} compiled mutations detected')


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'shifted-protected-differential.json').unlink(missing_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='shifted-protected-', parent=BUILD) as temp:
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
