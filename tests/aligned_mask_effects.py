"""Bounded differential for aligned masked 20/40 VGA effect bodies."""
import ctypes
import gc
import os
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

from aligned_masked import (TraceDevice, RasterBus, MAX_STEPS,
    MAX_BUS_EVENTS, MAX_VGA_EVENTS, DEFINED_FLAGS, NATIVE_GUARD_EXIT,
    NATIVE_CALLBACK_EXIT, VerificationFailure, GuardExhaustion, Mismatch,
    require, exit_worker, compare_event_traces, physical, put16, put_byte,
    prime_device_stack, field, MEM, READ, WRITE, OUT)
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs
from minimap_vga import VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
STARTS = {0: SYMS['PlanarAlignedMasked20Body']['address'],
          1: SYMS['PlanarAlignedMasked40Body']['address']}
RETURNS = {0: SYMS['PlanarAlignedMask20FarReturn']['address'],
           1: SYMS['PlanarAlignedMask40FarReturn']['address']}
ENDS = {mode: RETURNS[mode] + 1 for mode in STARTS}
EXPECTED_RANGE_HASHES = {
    0: '256c2fda581e791cf65e4f8f648793d2b7e2e05aaa922e02f9fca0604acec8a1',
    1: '0782d7c3bc45cdd5e649268f45a7c3a5fe1f3a81f1a9db69d8311bcd50054f31',
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
    path = build(Path(directory) / f'aligned-mask-effects-m{mutation}.dll',
                 mutation, 'aligned_mask_effects')
    lib = ctypes.CDLL(str(path))
    for mode in STARTS:
        suffix = '20' if mode == 0 else '40'
        core = getattr(lib, f'lmn_draw_aligned_mask{suffix}_core')
        core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
        core.restype = Result
        adapter = getattr(lib, f'lmn_draw_aligned_mask{suffix}_adapter')
        adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.c_uint16,
                            ctypes.POINTER(RasterBus)]
        adapter.restype = None
    return lib


def _cases():
    result = []

    def add(mode, name, **kwargs):
        result.append(dict(mode=mode, name=name, seed=len(result), **kwargs))

    # Every high BP nibble selects the corresponding set/reset enable plane bit.
    for mode in (0, 1):
        for nibble in range(16):
            add(mode, f'{20 if mode == 0 else 40}-BP-high-nibble-{nibble:x}',
                width=2, height=2, control=(nibble << 8) | 0x00a7,
                row_advance=0x0007 + nibble, destination_advance=0x0009,
                df=bool(nibble & 1), read_map=(nibble + mode) & 3,
                independent=nibble in (0, 5, 10, 15))

    add(0, '20-DF-does-not-reverse-BX-and-mask-cursor-wraps', width=2,
        height=2, control=0xf021, df=True, mask_cursor=0x7fff,
        source_cursor=0x2468, destination_cursor=0x0400,
        row_advance=0x0005, independent=True)
    add(1, '40-DF-does-not-reverse-BX-and-mask-cursor-wraps', width=2,
        height=2, control=0xa055, df=True, mask_cursor=0xfffe,
        source_cursor=0x1357, destination_cursor=0x0500,
        row_advance=0x0003, independent=True)
    add(0, '20-zero-CL-wraps-to-65536-mask-reads', width=0, height=1,
        control=0x8002, mask_cursor=0x1000, row_advance=0,
        destination_advance=0, low_flags=0x202)
    add(1, '40-zero-CL-wraps-to-65536-mask-reads', width=0, height=1,
        control=0x4003, mask_cursor=0x1000, row_advance=0,
        destination_advance=0, low_flags=0x202)
    add(0, '20-zero-CH-wraps-to-256-rows', width=1, height=0,
        control=0x2004, row_advance=0x0007, destination_advance=0x0009)
    add(1, '40-zero-CH-wraps-to-256-rows', width=1, height=0,
        control=0x1005, row_advance=0x0007, destination_advance=0x0009)
    add(0, '20-relocated-game-DS-differs-from-incoming-DS', width=2,
        height=2, initial_data_segment=0x6000, game_data_segment_distinct=True,
        row_advance=0x000b, independent=True)
    add(1, '40-relocated-game-DS-differs-from-incoming-DS', width=2,
        height=2, initial_data_segment=0x6000, game_data_segment_distinct=True,
        row_advance=0x000b, independent=True)
    add(0, '20-physical-wrap-in-mask-and-live-SS', width=2, height=2,
        control=0x7006, source_segment=0xffff, mask_cursor=0xfffe,
        destination_cursor=0xfffe, ss=0xffff, sp=0x0010, df=True)
    add(1, '40-physical-wrap-in-mask-and-live-SS', width=2, height=2,
        control=0x9007, source_segment=0xffff, mask_cursor=0xffff,
        destination_cursor=0xfffd, ss=0xffff, sp=0x0010, df=True)
    add(0, '20-entry-PUSH-DS-overwrites-graphics-segment-word', width=2,
        height=2, same_segments=True, sp=0x1fe6, control=0x8008)
    add(1, '40-entry-PUSH-DS-overwrites-graphics-segment-word', width=2,
        height=2, same_segments=True, sp=0x1fe6, control=0xa009)
    add(0, '20-live-stack-overwrites-row-stride-words', width=2,
        height=2, same_segments=True, sp=0x6708, control=0x400a)
    add(1, '40-live-stack-overwrites-row-stride-words', width=2,
        height=2, same_segments=True, sp=0x6708, control=0x200b)
    add(0, '20-mask-read-aliases-VGA-aperture', width=2, height=2,
        source_segment=0xa000, mask_cursor=0x0120, destination_cursor=0x0120,
        control=0x300c, read_map=2)
    add(1, '40-mask-read-aliases-VGA-aperture', width=2, height=2,
        source_segment=0xa000, mask_cursor=0x0240, destination_cursor=0x0240,
        control=0x600d, read_map=1)
    add(0, '20-SS-aperture-stack-events', width=2, height=2,
        ss=0xa000, sp=0x5000, destination_cursor=0x5100,
        stack_device=True, control=0x500e)
    add(1, '40-SS-aperture-stack-events', width=2, height=2,
        ss=0xa000, sp=0x5000, destination_cursor=0x5100,
        stack_device=True, control=0x900f)
    add(0, '20-live-SP-wrap-at-far-return-frame', width=2, height=2,
        sp=0xfffe, return_boundary=True, control=0xf010)
    add(1, '40-live-SP-wrap-at-far-return-frame', width=2, height=2,
        sp=0xfffe, return_boundary=True, control=0xe011)
    return result


def _prepare(case):
    rng = random.Random(0x9737 + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    memory = bytearray(rng.randbytes(1 << 20))
    memory[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    game_ds = (load + 0x09a9) & 0xffff
    initial_ds = case.get('initial_data_segment', game_ds)
    if case.get('game_data_segment_distinct') and initial_ds == game_ds:
        raise VerificationFailure('incoming DS unexpectedly equals relocated game DS')
    ss = case.get('ss', 0x7000)
    sp = case.get('sp', 0x8000)
    source_segment = case.get('source_segment', 0x5000)
    if case.get('same_segments'):
        ss = game_ds
        initial_ds = game_ds
    row_advance = case.get('row_advance', 0x0007)
    destination_advance = case.get('destination_advance', 0x0009)
    put16(memory, game_ds, field('DrawingSourceRowAdvance'), row_advance)
    put16(memory, game_ds, field('DrawingActiveDestinationRowAdvance'),
          destination_advance)
    put16(memory, initial_ds, field('GraphicsResourceSegment'), source_segment)
    mode = case['mode']
    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=STARTS[mode], ds=initial_ds,
                ss=ss, sp=sp,
                cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
                dx=rng.randrange(0x10000),
                bx=case.get('mask_cursor', 0x1000),
                si=case.get('source_cursor', 0x2345),
                di=case.get('destination_cursor', 0x0400),
                bp=case.get('control', 0x1200))
    if case.get('same_segments'):
        regs['ds'] = game_ds
    flags = 2 | ((case['seed'] * 0x95) & 0xad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    if 'low_flags' in case:
        flags = case['low_flags'] & 0xffff
    put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
          case.get('outer_cs', 0xbabe))
    return memory, regs, flags, game_ds, source_segment


def _call_of(regs, game_ds, flags):
    return Call(regs['ds'], game_ds, regs['ss'], regs['sp'], regs['cx'],
                regs['bx'], regs['di'], regs['bp'], flags)


def _oracle_body(case, memory, regs, flags, device):
    mode = case['mode']
    start, retf = STARTS[mode], RETURNS[mode]
    body_ins, branches = BODY_INS[mode], BRANCHES[mode]
    u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 2 << 20)
    u.mem_write(0, bytes(memory) * 2)
    for name, reg in oracle.REG.items():
        u.reg_write(reg, regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS, flags)
    seen, edges = set(), set()
    previous = None
    finished = False
    steps = 0
    instruction_flags = flags
    flag_mask = DEFINED_FLAGS
    last_op = None
    callback_failure = []

    def stop(uc, message):
        if not callback_failure:
            callback_failure.append(message[:240])
        uc.emu_stop()

    def code(uc, pc, _size, _):
        nonlocal previous, finished, steps, instruction_flags, flag_mask, last_op
        off = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in branches:
            edges.add((previous, off))
        if off == retf:
            finished = True
            uc.emu_stop()
            return
        if off not in body_ins or uc.reg_read(oracle.REG['cs']) != regs['cs']:
            stop(uc, f'{case["name"]}: original escaped at {off:04x}')
            return
        if last_op in LOGICAL:
            flag_mask = 0x0fc7
        elif last_op in ARITH:
            flag_mask = DEFINED_FLAGS
        instruction_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        seen.add(off)
        previous = off
        steps += 1
        if steps > MAX_STEPS:
            stop(uc, f'{case["name"]}: original instruction cap exhausted')
            return
        last_op = body_ins[off].mnemonic

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
                device.record_error(error)
                stop(uc, f'{case["name"]}: original read callback failed: {error}')
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
                device.record_error(error)
                stop(uc, f'{case["name"]}: original write callback failed: {error}')
                return
            if device.events.exhausted or device.vga_exhausted:
                uc.emu_stop()
                return

    def out(uc, _port, size, value, _):
        if size != 2:
            stop(uc, f'{case["name"]}: original used non-word VGA output')
            return
        port = uc.reg_read(oracle.REG['dx'])
        try:
            device.vga.out(port, value, instruction_flags)
            device.events.add('out', port, value, instruction_flags, flag_mask)
            if len(device.vga.trace) > MAX_VGA_EVENTS:
                device.vga.trace.pop()
                device.vga_exhausted = True
        except BaseException as error:
            device.record_error(error)
            stop(uc, f'{case["name"]}: original output callback failed: {error}')

    def intr(uc, number, _):
        stop(uc, f'{case["name"]}: unexpected INT{number:02x}')

    hooks = [
        u.hook_add(UC_HOOK_CODE, code),
        u.hook_add(UC_HOOK_MEM_READ, mem_read),
        u.hook_add(UC_HOOK_MEM_WRITE, mem_write),
        u.hook_add(UC_HOOK_INSN, out, None, 1, 0, x.UC_X86_INS_OUT),
        u.hook_add(UC_HOOK_INTR, intr),
        u.hook_add(UC_HOOK_MEM_READ, lambda uc, a, p, n, v, d:
                   _wrap_read(uc, p, n)),
        u.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, p, n, v, d:
                   _wrap_write(uc, p, n, v)),
    ]
    try:
        u.emu_start((regs['cs'] << 4) + start, 0, count=MAX_STEPS)
    except BaseException as error:
        raise VerificationFailure(
            f'{case["name"]}: original bounded execution failed: {error}')
    if callback_failure:
        if 'cap' in callback_failure[0]:
            raise GuardExhaustion(callback_failure[0])
        raise VerificationFailure(callback_failure[0])
    device.check(case['name'] + ' original')
    if not finished:
        raise VerificationFailure(f'{case["name"]}: original did not stop at RETF')
    if steps >= MAX_STEPS:
        raise GuardExhaustion(f'{case["name"]}: original instruction cap exhausted')
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
            uc.mem_write(raw & 0xfffff, bytes(((value >> (8 * index)) & 0xff,)))


def _independent_planes(initial_planes, memory, regs, flags, case, source_segment):
    expected = [bytearray(plane) for plane in initial_planes]
    mode = case['mode']
    cx = regs['cx']
    width = cx & 0xff or 65536
    rows = (cx >> 8) & 0xff or 256
    mask = regs['bx']
    destination = regs['di']
    direction = -1 if flags & 0x0400 else 1
    # The fixture marks independent only when source and output/stack are disjoint.
    # The source-row word may be live-mutable, so these cases supply a simple value.
    row_advance = case.get('row_advance', 0x0007)
    destination_advance = case.get('destination_advance', 0x0009)
    enable = (regs['bp'] >> 8) & 0x0f
    set_reset = 0x0f if mode == 0 else 0
    for _ in range(rows):
        for _ in range(width):
            p = physical(source_segment, mask)
            mask_byte = memory[p]
            mask = (mask + 1) & 0xffff
            target = destination & 0xffff
            for plane in range(4):
                source = 0xff
                if enable & (1 << plane):
                    source = 0xff if set_reset & (1 << plane) else 0
                old = expected[plane][target]
                expected[plane][target] = (
                    (source & mask_byte) | (old & (~mask_byte & 0xff)))
            destination = (destination + direction) & 0xffff
        destination = (destination + destination_advance) & 0xffff
        if mode == 1:
            mask = (mask + row_advance) & 0xffff
    return expected


def _compare_core(lib, case):
    memory, regs, flags, game_ds, source_segment = _prepare(case)
    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + STARTS[case['mode']],
                           case.get('read_map', 0))
    prime_device_stack(case, c_device)
    starting_planes = [bytearray(plane) for plane in c_device.vga.planes]
    call = _call_of(regs, game_ds, flags)
    suffix = '20' if case['mode'] == 0 else '40'
    c_result = getattr(lib, f'lmn_draw_aligned_mask{suffix}_core')(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(call), ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' C')

    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + STARTS[case['mode']],
                           case.get('read_map', 0))
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
    code_start = (regs['cs'] << 4) + STARTS[case['mode']]
    relocated_image = relocated(IMAGE, ORACLE['relocations'], regs['cs'])
    require(actual[code_start:code_start + ENDS[case['mode']] -
                   STARTS[case['mode']]] ==
            relocated_image[STARTS[case['mode']]:ENDS[case['mode']]],
            f'{case["name"]}: executing body modified its source bytes')
    require(c_device.vga.state() == o_device.vga.state(),
            f'{case["name"]}: VGA plane/latch/register state differs')
    compare_event_traces(c_device.events, o_device.events, case['name'])
    if case.get('independent'):
        expected = _independent_planes(starting_planes, memory, regs, flags,
                                       case, source_segment)
        require(c_device.vga.planes == expected,
                f'{case["name"]}: independent whole-plane expectation differs')
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
    o_device = TraceDevice(o_memory, case['seed'] + STARTS[case['mode']],
                           case.get('read_map', 0))
    prime_device_stack(case, o_device)
    u, _seen, _edges, hooks = _oracle_body(case, o_memory, regs, flags, o_device)
    for hook in hooks:
        u.hook_del(hook)
    u.ctl_remove_cache(0, 2 << 20)
    u.emu_start((regs['cs'] << 4) + RETURNS[case['mode']], 0, count=1)
    original_regs = {name: u.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = u.reg_read(x.UC_X86_REG_EFLAGS)

    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + STARTS[case['mode']],
                           case.get('read_map', 0))
    prime_device_stack(case, c_device)
    native_regs = Regs(**regs, flags=flags)
    suffix = '20' if case['mode'] == 0 else '40'
    getattr(lib, f'lmn_draw_aligned_mask{suffix}_adapter')(
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
    expected_sites = {0: 49, 1: 49}
    expected_bytes = {0: 109, 1: 108}
    for mode in STARTS:
        raw = IMAGE[STARTS[mode]:ENDS[mode]]
        if len(raw) != expected_bytes[mode] or len(ALL_INS[mode]) != expected_sites[mode]:
            raise VerificationFailure(
                f'{20 if mode == 0 else 40} body accounting changed: '
                f'{len(raw)} bytes/{len(ALL_INS[mode])} sites')
        if sha(raw) != EXPECTED_RANGE_HASHES[mode]:
            raise VerificationFailure(
                f'{20 if mode == 0 else 40} body range hash changed')
        if len(BODY_INS[mode]) != 48:
            raise VerificationFailure('expected body must stop before its RETF')


def _worker(build_directory):
    report_path = BUILD / 'aligned-mask-effects-differential.json'
    report_path.unlink(missing_ok=True)
    _accounting()
    baseline = _library(build_directory)
    fixture_cases = _cases()
    seen = {mode: set() for mode in STARTS}
    edges = {mode: set() for mode in STARTS}
    case_reports = []
    result_by_name = {}
    for case in fixture_cases:
        load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
        game_ds = (load + 0x09a9) & 0xffff
        memory, regs, _flags, actual_game_ds, _source = _prepare(case)
        require(actual_game_ds == game_ds,
                f'{case["name"]}: relocated game DS selection changed')
        if case.get('game_data_segment_distinct'):
            require(regs['ds'] != game_ds,
                    f'{case["name"]}: incoming DS is not distinct from game DS')
        sites, case_edges, result, case_report = _compare_core(baseline, case)
        mode = case['mode']
        seen[mode] |= sites
        edges[mode] |= case_edges
        case_reports.append(case_report)
        result_by_name[case['name']] = result
        del memory
        gc.collect()
    for mode in STARTS:
        require(seen[mode] == set(BODY_INS[mode]),
                f'{20 if mode == 0 else 40} body-site coverage differs: '
                f'missing={sorted(set(BODY_INS[mode])-seen[mode])}')
        require(edges[mode] == EDGES[mode],
                f'{20 if mode == 0 else 40} branch-edge coverage differs: '
                f'missing={sorted(EDGES[mode]-edges[mode])}, '
                f'extra={sorted(edges[mode]-EDGES[mode])}')

    retf_cases = [case for case in fixture_cases
                  if not case.get('stack_device') and
                  not case.get('return_boundary') and
                  case['width'] > 0 and case['height'] > 0 and
                  case['name'] in {
                      '20-BP-high-nibble-5', '40-BP-high-nibble-a',
                      '20-relocated-game-DS-differs-from-incoming-DS',
                      '40-relocated-game-DS-differs-from-incoming-DS'}]
    for case in retf_cases:
        _check_adapter_retf(baseline, case)
        gc.collect()

    sentinels = {
        1: next(case for case in fixture_cases
                if case['name'] == '20-DF-does-not-reverse-BX-and-mask-cursor-wraps'),
        2: next(case for case in fixture_cases
                if case['name'] == '20-live-stack-overwrites-row-stride-words'),
        3: next(case for case in fixture_cases
                if case['name'] == '40-BP-high-nibble-a'),
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
                f'compiled effect mutation {mutation} survived')
        mutations.append(dict(mutation=mutation, **detected))
        gc.collect()

    regression_sentinels = [
        dict(mutation=1, behavior='BX advances independently of DF',
             case=sentinels[1]['name']),
        dict(mutation=2, behavior='20 adds the row stride to SI only',
             case=sentinels[2]['name']),
        dict(mutation=3, behavior='40 adds the row stride to BX only',
             case=sentinels[3]['name'])]

    input_paths = (
        'assets/vgalemmi.exe', 'c/aligned_mask_effects.c',
        'c/aligned_mask_effects.h', 'c/special_blit.h', 'c/regs.h',
        'c/lemmings_sym.h', 'tests/aligned_mask_effects.py',
        'tests/aligned_masked.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tools/common.py', 'tools/unpack.py',
        'tools/cbuild.py', 'tools/bounded_process.py', 'metadata/symbols.json',
        'build/unpack.json', 'src/planar_drawing.asm',
        'docs/aligned-mask-effects.md')
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
        retf_probe_exclusions=[case['name'] for case in fixture_cases
            if case.get('stack_device') or case.get('return_boundary')],
        regression_sentinels=regression_sentinels,
        dependencies=['metadata/symbols.json', 'c/special_blit.h',
                      'c/regs.h', 'tests/minimap_vga.py',
                      'tools/bounded_process.py'],
        event_limits=dict(bus_events=MAX_BUS_EVENTS,
                          vga_device_trace=MAX_VGA_EVENTS,
                          original_steps=MAX_STEPS),
        defined_flag_masks=dict(arithmetic='0x0FD7',
                                logical_with_AF_undefined='0x0FC7'),
        device_contract='tests/minimap_vga.py; unchained A000 64KiB aperture, read mode 0, write mode 0 set/reset and bit mask, four latches, Sequencer/Graphics Controller word ports; no IRQ scheduling',
        quirks=[
            '20 increments mask BX for every byte regardless of DF, and adds the live source-row word to SI only.',
            '40 increments mask BX for every byte regardless of DF, adds the live source-row word to BX, and leaves SI at its initial BX copy.',
            'Both paths overwrite SI from BX, select the set/reset enable mask from BP high byte, use live SS save words/return words, and wrap 16-bit offsets plus 20-bit physical addresses.',
            'CH=0 executes 256 rows and CL=0 executes 65,536 bytes in each row; these are finite tested counts.'],
        domain='Constructed RAM and quiescent IRQs. Normal incoming edges are static dispatch jumps 93EA->9737 and 93F3->97A4. The body runs through POP DS and stops before its RETF adapter; other modified-code or indirect incoming-state domains remain unproven.')
    write_json(report_path, report)
    print(f'PASS aligned mask effects: {len(fixture_cases)} cases, '
          f'{sum(map(len, seen.values()))} body sites, '
          f'{sum(map(len, edges.values()))} branch edges; '
          f'{len(retf_cases)} original RETF probes; '
          f'{len(mutations)} compiled mutations detected')


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'aligned-mask-effects-differential.json').unlink(missing_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        _worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='aligned-mask-effects-', parent=BUILD) as temp:
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
