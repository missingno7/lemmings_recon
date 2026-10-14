"""Bounded original/native differential for shifted opaque body 916B..939D."""
import ctypes
import gc
import hashlib
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
    require, physical, put16, put_byte, prime_device_stack, field, MEM,
    DEFINED_FLAGS, UNDEFINED_AF_FLAGS, LOGICAL, ARITH)
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs
from minimap_vga import VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
START = SYMS['PlanarShiftedOpaqueBody']['address']
RETF = SYMS['PlanarShiftedOpaqueFarReturn']['address']
END = RETF + 1
UNKNOWN = {0x9339}
EXPECTED_RANGE_HASH = '800ff83a0fabbcdc59b73266c332f720636d45d26daba6bbd371cca3b360849a'
MAX_STEPS = 8_000_000
MAX_BUS_EVENTS = 2_500_000
MAX_VGA_EVENTS = 400_000
common.MAX_BUS_EVENTS = MAX_BUS_EVENTS
common.MAX_VGA_EVENTS = MAX_VGA_EVENTS

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
ALL_INS = {i.address: i for i in MD.disasm(IMAGE[START:END], START)
           if i.address not in UNKNOWN}
BODY_INS = {a: i for a, i in ALL_INS.items() if a != RETF}
BRANCHES = {pc for pc, ins in BODY_INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or
            ins.mnemonic.startswith('loop')}
EDGES = {(pc, ins.operands[0].imm & 0xffff)
         for pc, ins in BODY_INS.items()
         if pc in BRANCHES}
EDGES |= {(pc, pc + ins.size) for pc, ins in BODY_INS.items()
          if pc in BRANCHES and ins.mnemonic != 'jmp'}


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
                ('mask_cursor', ctypes.c_uint16),
                ('destination_cursor', ctypes.c_uint16),
                ('plane_counter', ctypes.c_uint16),
                ('stack_offset', ctypes.c_uint16),
                ('source_segment', ctypes.c_uint16),
                ('output_segment', ctypes.c_uint16),
                ('flags', ctypes.c_uint16)]


def _library(directory, mutation=0):
    path = build(Path(directory) / f'shifted-opaque-m{mutation}.dll',
                 mutation, 'shifted_opaque')
    lib = ctypes.CDLL(str(path))
    lib.lmn_draw_shifted_opaque_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    lib.lmn_draw_shifted_opaque_core.restype = Result
    lib.lmn_draw_shifted_opaque_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint16, ctypes.POINTER(RasterBus)]
    lib.lmn_draw_shifted_opaque_adapter.restype = None
    return lib


def _cases():
    result = []

    def add(name, **kwargs):
        result.append(dict(name=name, seed=len(result), **kwargs))

    # These witnesses take and fall through each plane-count and row edge.
    for limit in (1, 2, 3, 4, 0, 5, 0xff):
        add(f'plane-limit-{limit:02x}-two-rows', plane_limit=limit,
            width=2 + (limit & 1), height=2, shift=1 + (limit % 7),
            source_row_advance=5 + limit, destination_advance=9 + (limit & 3),
            plane_extent=0x31 + limit, low_state=(0x40 + limit) & 0xff)

    # Independent packed-byte fixtures exercise each ordinary shift count.
    for shift in range(1, 8):
        add(f'independent-four-plane-shift-{shift}', plane_limit=4,
            width=2 + (shift & 1), height=1, shift=shift,
            plane_extent=0x35 + shift, source_row_advance=0x0007,
            destination_advance=0x0009, independent=True,
            source_bytes_per_plane=(
                (0x01, 0x00, 0x80, 0x55),
                (0x80, 0x01, 0x7f, 0xaa),
                (0x55, 0x33, 0xcc, 0x81),
                (0x12, 0x48, 0x84, 0x21)))

    add('zero-shift-byte-wraps-to-256-small-width', plane_limit=1,
        width=2, height=1, shift=0, source_row_advance=3,
        destination_advance=7)
    add('zero-CL-wraps-source-and-mask-loops-to-65536', plane_limit=1,
        width=0, height=1, shift=8, zero_cl_live_shift_control=True,
        source_row_advance=1, destination_advance=1, low_state=0x91)
    add('zero-CH-wraps-to-256-rows', plane_limit=1, width=1, height=0,
        shift=1, source_row_advance=3, destination_advance=5)
    add('CL-FF-inc-wraps-to-65536-draws', plane_limit=1, width=0xff,
        height=1, shift=1, source_row_advance=0x11,
        destination_advance=7, destination_cursor=0xfffe)
    add('DF-reverses-source-copy-and-sentinels-only', plane_limit=2,
        width=3, height=2, shift=3, df=True, source_cursor=0x2110,
        destination_cursor=0x0411, source_row_advance=0x0007,
        destination_advance=0x000b)
    add('20-bit-physical-and-16-bit-cursor-wrap', plane_limit=3,
        width=3, height=2, shift=5, source_segment=0xffff,
        source_cursor=0xfffd, destination_cursor=0xfffe, ss=0xffff,
        sp=0x0004, df=True, source_row_advance=0x0011,
        destination_advance=0x0009, plane_extent=0x0021)
    add('incoming-DS-distinct-from-relocated-game-frame', plane_limit=2,
        width=2, height=2, shift=4, initial_ds=0x6000,
        source_segment=0x7100, source_row_advance=0x000b,
        destination_advance=0x000d)
    add('source-cursor-aliases-live-source-scratch', plane_limit=1,
        width=3, height=1, shift=2, source_is_scratch=True,
        source_cursor=0x6706, source_row_advance=0x0005,
        destination_advance=0x0007)
    add('SS-save-overwrites-live-shift-byte-before-second-read',
        plane_limit=1, width=2, height=1, shift=1,
        same_segments=True, sp=0xa95a, stack_alias=True,
        source_row_advance=0x0005, destination_advance=0x0007)
    add('SS-save-aliases-live-row-fields', plane_limit=1, width=2,
        height=2, shift=2, same_segments=True, sp=0x6708,
        stack_alias=True, source_row_advance=0x0005,
        destination_advance=0x0009)
    add('entry-DS-push-overwritten-by-SS-mirror', plane_limit=1,
        width=1, height=1, shift=2, same_segments=True, sp=0x000a,
        source_row_advance=3, destination_advance=5, stack_alias=True)
    add('stack-in-A000-device-aperture', plane_limit=1, width=2,
        height=1, shift=2, ss=0xa000, sp=0x5000,
        destination_cursor=0x5100, stack_device=True,
        source_row_advance=3, destination_advance=5)
    add('source-segment-is-the-VGA-aperture', plane_limit=1, width=2,
        height=1, shift=3, source_segment=0xa000,
        source_cursor=0x0200, destination_cursor=0x0220,
        source_row_advance=5, destination_advance=7)
    add('outer-return-frame-at-SS-FFFF-wrap', plane_limit=1,
        width=1, height=1, shift=1, ss=0xffff, sp=0xfffe,
        source_row_advance=5, destination_advance=7)

    # The shift byte is sampled before source shifts and again before mask
    # shifts. A live SS push aliases A948 after the first read, keeping both
    # finite counts small while distinguishing stale-count implementations.
    add('second-live-shift-read-sees-stack-alias', plane_limit=1,
        width=2, height=1, shift=1, same_segments=True, sp=0xa95a,
        stack_alias=True, source_row_advance=5, destination_advance=7)
    return result


def _prepare(case):
    rng = random.Random(0x916b + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
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

    # Values at the incoming segment and the relocated 09A9 frame are separate
    # live objects. The first row-advance decrement is through incoming DS.
    put16(memory, initial_ds, field('GraphicsResourceSegment'), source_segment)
    put16(memory, initial_ds, field('DrawingActiveDestinationRowAdvance'),
          case.get('entry_destination_advance',
                   case.get('destination_advance', 0x0009)))
    put16(memory, game_ds, field('DrawingSourceRowAdvance'),
          case.get('source_row_advance', 0x0007))
    put16(memory, game_ds, field('DrawingActiveDestinationRowAdvance'),
          case.get('destination_advance', 0x0009))
    put16(memory, game_ds, field('DrawingSourcePlaneExtent'),
          case.get('plane_extent', 0x0031))
    put_byte(memory, game_ds, field('DrawingLeftBitShiftByte'),
             case.get('shift', 1))

    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=initial_ds, ss=ss, sp=sp,
                cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
                dx=((case['plane_limit'] & 0xff) << 8) |
                   case.get('low_state', 0x6d),
                bx=case.get('mask_cursor', rng.randrange(0x10000)),
                si=case.get('source_cursor', 0x2000),
                di=case.get('destination_cursor', 0x0410),
                bp=rng.randrange(0x10000))
    flags = 2 | ((case['seed'] * 0x95) & 0xad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
          case.get('outer_cs', 0xbabe))

    if source_segment != game_ds:
        # Fill a bounded source neighborhood, including cursor and row/plane
        # advances; wrapped probes still follow the physical bus model.
        for delta in range(-1024, 1024):
            offset = (regs['si'] + delta) & 0xffff
            put_byte(memory, source_segment, offset,
                     (case['seed'] * 37 + delta * 53 + 0x91) & 0xff)

    for plane, values in enumerate(case.get('source_bytes_per_plane', ())):
        for n, value in enumerate(values):
            put_byte(memory, source_segment,
                     (regs['si'] + plane * case.get('plane_extent', 0x31) + n)
                     & 0xffff, value)
    if case.get('zero_cl_live_shift_control'):
        # A zero-width source shift walks all 65,536 offsets after its first
        # SHR. Keep the live shift byte's final value small: the first pass
        # carries one into offset A948 and the next seven forward RCR passes
        # turn its initial value 8 into 1. The second live read then runs one
        # finite mask pass instead of the original 256-pass zero wrap.
        for offset in range(0x6707, 0xa947):
            put_byte(memory, game_ds, offset, 0)
        put_byte(memory, game_ds, 0xa947, 1)
        put_byte(memory, game_ds, 0xa948, 8)
    return memory, regs, flags, game_ds, source_segment


def _call_of(regs, game_ds, flags):
    return Call(regs['ds'], game_ds, regs['ss'], regs['sp'], regs['cx'],
                regs['dx'], regs['si'], regs['di'], flags)


def _oracle_body(case, memory, regs, flags, device):
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
        last_op = BODY_INS[off].mnemonic

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
            port = uc.reg_read(oracle.REG['dx'])
            device.vga.out(port, value, instruction_flags)
            device.events.add('out', port, value, instruction_flags, flag_mask)
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
        u.emu_start((regs['cs'] << 4) + START, 0, count=MAX_STEPS)
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


def _shift_bytes(values, count):
    values = list(values)
    passes = count or 256
    for _ in range(passes):
        carry = values[0] & 1
        values[0] >>= 1
        for index in range(1, len(values)):
            before = values[index]
            values[index] = (before >> 1) | (carry << 7)
            carry = before & 1
    return values


def _independent_planes(initial_planes, memory, regs, game_ds,
                        source_segment, case):
    """Pure packed-bit and plane model for small, non-aliased four-plane draws."""
    width = regs['cx'] & 0xff
    if (not case.get('independent') or width == 0 or width == 0xff or
            regs['cx'] >> 8 != 1 or regs['dx'] >> 8 != 4):
        raise VerificationFailure(f'{case["name"]}: invalid independent fixture')
    if case.get('df') or source_segment == game_ds or case.get('stack_device'):
        raise VerificationFailure(f'{case["name"]}: independent alias domain changed')

    planes = [bytearray(values) for values in initial_planes]
    src_cursor = regs['si']
    destination = regs['di']
    shift = memory[physical(game_ds, field('DrawingLeftBitShiftByte'))]
    plane_extent = case.get('plane_extent', 0x31)
    source_row_advance = case.get('source_row_advance', 0x0007)
    width_plus_sentinel = width + 1
    scratch_source = None
    scratch_mask = None

    for plane_no in range(4):
        for _row in range(1):
            source = [memory[physical(source_segment,
                       (src_cursor + index) & 0xffff)]
                      for index in range(width)]
            scratch_source = _shift_bytes(source + [0], shift)
            scratch_mask = _shift_bytes([0xff] * width + [0], shift)

            for index in range(width_plus_sentinel):
                offset = (destination + index) & 0xffff
                mask = scratch_mask[index]
                data = scratch_source[index]
                if plane_no == 0:
                    # First-pass GC enables set/reset on planes 1..3 with
                    # set/reset value zero; plane 0 receives the source byte.
                    for target_plane in range(4):
                        before = planes[target_plane][offset]
                        source_value = data if target_plane == 0 else 0
                        planes[target_plane][offset] = (
                            (source_value & mask) |
                            (before & (~mask & 0xff)))
                else:
                    before = planes[plane_no][offset]
                    planes[plane_no][offset] = before | data
            src_cursor=(src_cursor+source_row_advance)&0xffff
        if plane_no != 3:
            src_cursor=(src_cursor-source_row_advance+plane_extent)&0xffff

    for index, value in enumerate(scratch_source):
        require(memory[physical(game_ds,
                (field('DrawingSourceRowScratch')+index)&0xffff)] == value,
                f'{case["name"]}: independent shifted source scratch mismatch')
    for index, value in enumerate(scratch_mask):
        require(memory[physical(game_ds,
                (field('DrawingMaskRowScratch')+index)&0xffff)] == value,
                f'{case["name"]}: independent shifted mask scratch mismatch')
    return planes


def _compare_core(lib, case):
    memory, regs, flags, game_ds, source_segment = _prepare(case)
    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + START)
    prime_device_stack(case, c_device)
    starting_planes = [bytearray(plane) for plane in c_device.vga.planes]
    call = _call_of(regs, game_ds, flags)
    c_result = lib.lmn_draw_shifted_opaque_core(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(call), ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' C')

    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + START)
    prime_device_stack(case, o_device)
    u, seen, edges, _hooks = _oracle_body(case, o_memory, regs, flags, o_device)
    for name, want in (
        ('ax', c_result.work_value), ('bx', c_result.mask_cursor),
        ('cx', c_result.packed_counts), ('dx', c_result.port),
        ('si', c_result.source_cursor), ('di', c_result.destination_cursor),
        ('bp', c_result.plane_counter), ('sp', c_result.stack_offset),
        ('ds', c_result.source_segment), ('es', c_result.output_segment),
        ('ss', regs['ss']), ('cs', regs['cs']), ('ip', RETF)):
        require(u.reg_read(oracle.REG[name]) == want,
                f'{case["name"]}: {name} C={want:04x}/ASM='
                f'{u.reg_read(oracle.REG[name]):04x}')
    oracle_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    require(((c_result.flags^oracle_flags)&DEFINED_FLAGS)==0,
            f'{case["name"]}: defined flags C={c_result.flags:04x}/'
            f'ASM={oracle_flags:04x}')
    require(bytes(u.mem_read(0,1<<20))==c_memory,
            f'{case["name"]}: full RAM differs')
    require(c_device.vga.state()==o_device.vga.state(),
            f'{case["name"]}: VGA plane/latch/register state differs')
    common.compare_event_traces(c_device.events,o_device.events,case['name'])
    if case.get('independent'):
        expected=_independent_planes(starting_planes,c_memory,regs,game_ds,
                                     source_segment,case)
        require(c_device.vga.planes==expected,
                f'{case["name"]}: independent packed source/mask/plane expectation differs')
    report=dict(name=case['name'],seed=case['seed'],input=dict(case,
        relocated_game_data_segment=game_ds,
        source_segment_initial=source_segment),
        result={name:getattr(c_result,name) for name,_f in c_result._fields_})
    del u,c_device,o_device
    return seen,edges,c_result,report


def _check_adapter_retf(lib,case):
    memory,regs,flags,game_ds,_source_segment=_prepare(case)
    o_memory=bytearray(memory)
    o_device=TraceDevice(o_memory,case['seed']+START)
    prime_device_stack(case,o_device)
    u,_seen,_edges,hooks=_oracle_body(case,o_memory,regs,flags,o_device)
    code_address=(regs['cs']<<4)+RETF
    require(bytes(u.mem_read(code_address,1))==b'\xcb',
            f'{case["name"]}: RETF byte changed before probe')
    for hook in hooks:
        u.hook_del(hook)
    # Isolated RETF runs without UC read hooks. Cases with VGA-backed or
    # aliased/wrapping stacks are excluded because raw stack reads differ.
    u.ctl_remove_cache(0,2<<20)
    u.emu_start(code_address,0,count=1)
    original_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()}
    original_flags=u.reg_read(x.UC_X86_REG_EFLAGS)

    c_memory=bytearray(memory)
    c_device=TraceDevice(c_memory,case['seed']+START)
    native_regs=Regs(**regs,flags=flags)
    lib.lmn_draw_shifted_opaque_adapter(
        (ctypes.c_uint8*(1<<20)).from_buffer(c_memory),
        ctypes.byref(native_regs),game_ds,ctypes.byref(c_device.bus))
    c_device.check(case['name']+' C core + RETF adapter')
    for name in oracle.REG_NAMES:
        require(getattr(native_regs,name)==original_regs[name],
                f'{case["name"]}: RETF {name} C='
                f'{getattr(native_regs,name):04x}/ASM={original_regs[name]:04x}')
    require((native_regs.flags^original_flags)&DEFINED_FLAGS==0,
            f'{case["name"]}: RETF defined flags differ')
    require(c_memory==bytes(u.mem_read(0,1<<20)),
            f'{case["name"]}: RETF full RAM differs')
    require(c_device.vga.state()==o_device.vga.state(),
            f'{case["name"]}: RETF VGA state differs')
    del u,c_device,o_device


def _accounting():
    raw=IMAGE[START:END]
    if len(raw)!=563 or sha(raw)!=EXPECTED_RANGE_HASH:
        raise VerificationFailure('916B..939D physical range/hash changed')
    if len(ALL_INS)!=317 or len(BODY_INS)!=316:
        raise VerificationFailure(
            f'916B body accounting changed: {len(ALL_INS)} known sites/'
            f'{len(BODY_INS)} core sites')
    if sum(ins.size for ins in ALL_INS.values())!=562:
        raise VerificationFailure('916B decoded-byte accounting changed')
    if RETF not in ALL_INS or 0x9339 not in UNKNOWN:
        raise VerificationFailure('RETF/UNKNOWN accounting changed')


def _worker(build_directory):
    report_path=BUILD/'shifted-opaque-differential.json'
    report_path.unlink(missing_ok=True)
    _accounting()
    baseline=_library(build_directory)
    fixture_cases=_cases()
    seen=set()
    edges=set()
    case_reports=[]
    for case in fixture_cases:
        memory,regs,flags,game_ds,source_segment=_prepare(case)
        if case.get('name','').startswith('incoming-DS-distinct'):
            require(regs['ds']!=game_ds,
                    f'{case["name"]}: incoming DS equals relocated frame')
        del memory
        sites,case_edges,_result,case_report=_compare_core(baseline,case)
        seen|=sites
        edges|=case_edges
        case_reports.append(case_report)
        gc.collect()
    require(seen==set(BODY_INS),
            f'core-site coverage differs: missing={sorted(set(BODY_INS)-seen)}')
    require(edges==EDGES,
            f'direct-edge coverage differs: missing={sorted(EDGES-edges)}, '
            f'extra={sorted(edges-EDGES)}')

    retf_cases=[next(c for c in fixture_cases
                     if c['name']=='plane-limit-01-two-rows'),
                next(c for c in fixture_cases
                     if c['name']=='incoming-DS-distinct-from-relocated-game-frame')]
    for case in retf_cases:
        _check_adapter_retf(baseline,case)
        gc.collect()

    sentinels={
        1: next(c for c in fixture_cases
                if c['name']=='independent-four-plane-shift-1'),
        2: next(c for c in fixture_cases
                if c['name']=='second-live-shift-read-sees-stack-alias'),
        3: next(c for c in fixture_cases
                if c['name']=='independent-four-plane-shift-4'),
    }
    mutations=[]
    for mutation in (1,2,3):
        mutant=_library(build_directory,mutation)
        case=sentinels[mutation]
        detected=None
        try:
            _compare_core(mutant,case)
        except Mismatch as mismatch:
            detected=dict(case=case['name'],reason=str(mismatch)[:300])
        if detected is None:
            raise VerificationFailure(
                f'compiled shifted opaque mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,**detected))
        gc.collect()

    input_paths=(
        'assets/vgalemmi.exe','c/shifted_opaque.c','c/shifted_opaque.h',
        'c/special_blit.h','c/regs.h','c/lemmings_sym.h',
        'tests/shifted_opaque.py','tests/aligned_masked.py',
        'tests/minimap_vga.py','tests/dat_io.py','tests/dat_io_c.py',
        'tools/common.py','tools/unpack.py','tools/cbuild.py',
        'tools/bounded_process.py','metadata/symbols.json',
        'build/unpack.json','src/planar_drawing.asm',
        'docs/shifted-drawing.md','docs/shifted-mask-effects.md')
    body_addresses=sorted(seen)
    retf_exclusions=[c['name'] for c in fixture_cases
        if c.get('stack_device') or c.get('stack_alias') or
           c.get('sp',0x8000)>=0xfffe]
    report=dict(
        image='main',image_sha256=sha(IMAGE),
        ranges={'shifted_opaque':dict(
            inclusive=f'{START:04X}..{RETF:04X}',
            range_sha256=sha(IMAGE[START:END]),
            physical_code_bytes=563,decoded_code_bytes=562,
            translated_code_bytes=sum(ins.size for ins in BODY_INS.values()),
            physical_instruction_sites=317,body_instruction_sites=316,
            body_instruction_addresses=body_addresses,
            branch_edges=sorted([list(edge) for edge in edges]),
            branch_edge_count=len(edges),adapter_instruction_address=RETF,
            unknown_bytes=[0x9339])},
        case_count=len(fixture_cases),cases=case_reports,
        mutation_count=len(mutations),mutations_detected=mutations,
        executed_instruction_addresses=body_addresses+[RETF],
        input_hashes={path:sha((ROOT/path).read_bytes()) for path in input_paths},
        retf_probe_case_count=len(retf_cases),
        retf_probe_cases=[case['name'] for case in retf_cases],
        retf_probe_exclusions=retf_exclusions,
        retf_probe_method='Original body stopped before RETF, then hooks and translated block cache were removed and exactly the unchanged CB at 939D executed once. C adapter runs core then reads the same live SS:SP frame.',
        regression_sentinels=[
            dict(mutation=1,behavior='RCR propagates preceding SHR/RCR carry',
                 case=sentinels[1]['name']),
            dict(mutation=2,behavior='mask shift rereads live DS:A948 after source shifts',
                 case=sentinels[2]['name']),
            dict(mutation=3,behavior='later planes advance SI through live ES:66F8',
                 case=sentinels[3]['name'])],
        dependencies=['metadata/symbols.json','c/special_blit.h','c/regs.h',
                      'tests/minimap_vga.py','tools/bounded_process.py'],
        event_limits=dict(bus_events=MAX_BUS_EVENTS,vga_device_trace=MAX_VGA_EVENTS,
                          original_steps=MAX_STEPS),
        defined_flag_masks=dict(arithmetic='0x0FD7',
                                logical_with_AF_undefined='0x0FC7'),
        device_contract='tests/minimap_vga.py; unchained A000 64KiB aperture, four planes/latches, Sequencer and Graphics Controller word ports, first-pass bit mask/set-reset and later OR passes; IRQs quiescent.',
        quirks=[
            'Entry DEC uses incoming DS; MOV AX,09A9 is relocated and establishes initial ES before the body reads its graphics segment from incoming DS:1FE4.',
            'DX high byte becomes BP plane counter. The first pass always runs; counts 1..3 stop after the matching pass, zero underflows, and the fourth pass has no extra BP test.',
            'REP MOVSB/STOSB source and mask copies plus sentinels follow DF. Scratch SHR/RCR and INC cursor walks proceed forward and preserve carry through INC.',
            'Source scratch shifts first; the mask loop then rereads live DS:A948. First-pass bit-mask OUT at 921E has no SS mirror store.',
            'Later passes use live ES:66F8 source-plane advances. Plane two configures OR mode/FF mask; planes three and four only change the Sequencer map mask.',
            'Width zero makes each RCR LOOP run 65,536 times; shift byte zero wraps to 256 passes; width FF plus INC CL wraps draw count to 65,536; height zero wraps to 256 rows. These are retained finite original paths.'],
        domain='Constructed 1MiB RAM with relocated pinned image and quiescent IRQs. Discovered normal incoming edge 916A->916B; no calls or outgoing direct edges. Core ends at POP DS 939C, adapter consumes live RETF 939D. UNKNOWN 9339 remains excluded. UC RETF probes exclude device-backed, live stack-alias, and 16-bit stack-wrap cases because the isolated RETF has no memory/device hooks.')
    write_json(report_path,report)
    print(f'PASS shifted opaque: {len(fixture_cases)} cases, '
          f'{len(seen)} core sites, {len(edges)} direct edges; '
          f'{len(retf_cases)} original RETF probes; '
          f'{len(mutations)} compiled mutations detected')


def main():
    BUILD.mkdir(parents=True,exist_ok=True)
    (BUILD/'shifted-opaque-differential.json').unlink(missing_ok=True)
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        _worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='shifted-opaque-',parent=BUILD) as temp:
        result=run_bounded([sys.executable,str(Path(__file__).resolve()),
                            '--worker',temp],cwd=ROOT,timeout=180,
                           memory_mib=512,check=False)
        if result.returncode==NATIVE_GUARD_EXIT:
            raise GuardExhaustion('native callback worker exited on a finite trace guard')
        if result.returncode==NATIVE_CALLBACK_EXIT:
            raise VerificationFailure('native callback worker exited on a callback error')
        if result.returncode!=0:
            raise VerificationFailure(
                f'bounded worker exited with status {result.returncode}')


if __name__=='__main__':
    main()
