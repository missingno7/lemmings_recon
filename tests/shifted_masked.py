"""Bounded original/native differential for the 890E shifted masked body."""
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
    require, physical, put16, put_byte, prime_device_stack)
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs, MEM
from minimap_vga import VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
START = SYMS['PlanarShiftedMaskedDefaultBody']['address']
RETF = SYMS['PlanarShiftedMaskedFarReturn']['address']
END = RETF + 1
UNKNOWN = {0x8ADD}
EXPECTED_RANGE_SHA = 'b606303fa5acf2be33ce7aee0422b7c8e135ac09a9f54aee7a52b1da2a5f3a2b'
MAX_STEPS = 5_000_000
MAX_BUS_EVENTS = 1_200_000
MAX_VGA_EVENTS = 600_000
common.MAX_BUS_EVENTS = MAX_BUS_EVENTS
common.MAX_VGA_EVENTS = MAX_VGA_EVENTS
DEFINED_FLAGS = 0x0fd7
UNDEFINED_AF_FLAGS = 0x0fc7
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
ALL_INS = {i.address: i for i in MD.disasm(IMAGE[START:END], START)
           if i.address not in UNKNOWN}
BODY_INS = {a: i for a, i in ALL_INS.items() if a != RETF}
BRANCHES = {pc for pc, ins in BODY_INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EDGES = {(pc, ins.operands[0].imm & 0xffff)
         for pc, ins in BODY_INS.items() if pc in BRANCHES}
EDGES |= {(pc, pc + ins.size) for pc, ins in BODY_INS.items()
          if pc in BRANCHES and ins.mnemonic != 'jmp'}
LOGICAL = {'and', 'or', 'xor', 'test'}
ARITH = {'add', 'sub', 'dec', 'inc', 'mul', 'neg'}


class Call(ctypes.Structure):
    _fields_ = [('initial_data_segment', ctypes.c_uint16),
                ('game_data_segment', ctypes.c_uint16),
                ('stack_segment', ctypes.c_uint16),
                ('stack_offset', ctypes.c_uint16),
                ('packed_counts', ctypes.c_uint16),
                ('width_state', ctypes.c_uint16),
                ('source_cursor', ctypes.c_uint16),
                ('mask_cursor', ctypes.c_uint16),
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
    path = build(Path(directory) / f'shifted-masked-m{mutation}.dll',
                 mutation, 'shifted_masked')
    lib = ctypes.CDLL(str(path))
    core = lib.lmn_draw_shifted_masked_core
    core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    core.restype = Result
    adapter = lib.lmn_draw_shifted_masked_adapter
    adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.c_uint16,
                        ctypes.POINTER(RasterBus)]
    adapter.restype = None
    return lib


def _cases():
    cases = []

    def add(name, **kwargs):
        cases.append(dict(name=name, seed=len(cases), **kwargs))

    # Plane inputs are the high byte that becomes BP after XCHG DL,DH/XOR DH.
    # Values above four still take the hard-coded final-plane tail; zero wraps
    # the earlier DEC guards and also reaches that tail.
    for planes in (0, 1, 2, 3, 4, 5, 0xff):
        add(f'plane-count-{planes:02x}', width=2, height=1, planes=planes,
            shift=(planes % 7) + 1, source_advance=5,
            destination_advance=9, plane_extent=17,
            source_bytes=(0x81, 0x36, 0xc0), mask_bytes=(0x80, 0x55, 0x01),
            independent=planes in (1, 2, 3, 4))

    # The complete shift domain and several width/height branch patterns.
    for shift in range(1, 8):
        add(f'shift-{shift}', width=1 + shift % 3,
            height=1 + (shift % 2), planes=1 + shift % 4,
            shift=shift, source_advance=3 + shift,
            destination_advance=7 + (shift & 1), plane_extent=11 + shift)

    add('DF-copy-and-sentinel-follow-direction', width=3, height=2,
        planes=2, shift=3, df=True, source_advance=5,
        destination_advance=11, plane_extent=19,
        source_segment=0x5100)
    add('shift-zero-wraps-to-256', width=2, height=1, planes=1, shift=0,
        source_advance=3, destination_advance=7, plane_extent=13,
        source_bytes=(0x01, 0x80, 0x55), mask_bytes=(0x01, 0x00, 0x80))
    add('CL-zero-rcr-loop-wraps-65536', width=0, height=1, planes=1,
        shift=1, source_advance=1, destination_advance=1, plane_extent=3)
    add('CH-zero-wraps-to-256-rows', width=1, height=0, planes=1,
        shift=2, source_advance=3, destination_advance=5, plane_extent=7)
    add('CL-FF-draw-count-wraps-65536', width=0xff, height=1, planes=1,
        shift=1, source_advance=7, destination_advance=3, plane_extent=9,
        destination_cursor=0xfffe)
    add('physical-and-SP-wrap', width=3, height=2, planes=2, shift=4,
        source_segment=0xffff, source_cursor=0xfffe, mask_cursor=0xfffe,
        destination_cursor=0xfffe, df=True, ss=0xffff, sp=0x0002,
        source_advance=0x11, destination_advance=9, plane_extent=0x13)
    add('live-SS-save-overwrites-source-scratch', width=2, height=2,
        planes=1, shift=2, same_segments=True, ss_at_scratch=True,
        sp=0x6706, source_advance=0x13, destination_advance=0x19,
        plane_extent=0x17)
    add('entry-push-aliases-live-shift-byte', width=2, height=1,
        planes=1, shift=1, same_segments=True, sp=0xa94a,
        source_advance=3, destination_advance=5, plane_extent=7)
    add('incoming-DS-distinct-from-relocated-frame', width=2, height=2,
        planes=2, shift=5, initial_ds=0x6000, source_segment=0x7100,
        source_advance=0x0b, destination_advance=0x0d, plane_extent=0x21,
        source_bytes=(0x81, 0x42, 0x24, 0x18),
        mask_bytes=(0x80, 0x01, 0xaa, 0x55))
    add('plane-stride-uses-live-ES', width=2, height=1, planes=2,
        shift=2, initial_ds=0x6000, source_segment=0x7100,
        source_advance=3, destination_advance=5, plane_extent=0x10,
        source_bytes=(0x80, 0x41, 0x20), mask_bytes=(0xff, 0xff, 0xff),
        source_extent_override=0x2b)
    add('SS-A000-device-stack', width=2, height=1, planes=1, shift=2,
        ss=0xa000, sp=0x5100, destination_cursor=0x5200,
        stack_device=True, source_advance=3, destination_advance=5,
        plane_extent=7)
    add('source-and-mask-share-live-segment', width=3, height=2,
        planes=1, shift=3, source_is_game=True, mask_cursor=0x6748,
        source_cursor=0x6748, source_advance=5, destination_advance=7,
        plane_extent=9)

    # Distinct, independently calculated packed-byte and VGA-plane witnesses.
    for planes, width, shift in ((1, 1, 1), (2, 2, 3), (4, 3, 6)):
        add(f'independent-footprint-p{planes}-w{width}-s{shift}',
            width=width, height=1, planes=planes, shift=shift,
            source_advance=5, destination_advance=7, plane_extent=13,
            source_bytes=(0x81, 0x5a, 0xc3, 0x7e),
            mask_bytes=(0x80, 0x01, 0xa5, 0x42), independent=True)

    return cases


def _prepare(case):
    seed = case['seed']
    rng = random.Random(0x890e + seed)
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
    if case.get('ss_at_scratch'):
        ss = game_ds
    source_segment = (game_ds if case.get('source_is_game') else
                      case.get('source_segment', 0x5000))

    put16(memory, initial_ds, SYMS['GraphicsResourceSegment']['address'],
          source_segment)
    put16(memory, initial_ds,
          SYMS['DrawingActiveDestinationRowAdvance']['address'],
          case.get('entry_destination_advance',
                   case.get('destination_advance', 9)))
    put16(memory, game_ds, SYMS['DrawingSourceRowAdvance']['address'],
          case.get('source_advance', 7))
    put16(memory, game_ds,
          SYMS['DrawingActiveDestinationRowAdvance']['address'],
          case.get('destination_advance', 9))
    put16(memory, game_ds, SYMS['DrawingSourcePlaneExtent']['address'],
          case.get('plane_extent', 13))
    if 'source_extent_override' in case:
        put16(memory, source_segment,
              SYMS['DrawingSourcePlaneExtent']['address'],
              case['source_extent_override'])
    put_byte(memory, game_ds, SYMS['DrawingLeftBitShiftByte']['address'],
             case.get('shift', 1))

    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=initial_ds, ss=ss, sp=sp,
                cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
                dx=((case.get('planes', 1) & 0xff) << 8) |
                   (case.get('width_low', seed * 19 + 3) & 0xff),
                bx=case.get('mask_cursor', 0x1000),
                si=case.get('source_cursor', 0x2000),
                di=case.get('destination_cursor', 0x0410))
    flags = 2 | ((seed * 0x95) & 0xad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
          case.get('outer_cs', 0xbabe))
    for n, value in enumerate(case.get('source_bytes', ())):
        put_byte(memory, source_segment, (regs['si'] + n) & 0xffff, value)
    for n, value in enumerate(case.get('mask_bytes', ())):
        put_byte(memory, source_segment, (regs['bx'] + n) & 0xffff, value)
    return memory, regs, flags, game_ds, source_segment


def _call_of(regs, game_ds, flags):
    return Call(regs['ds'], game_ds, regs['ss'], regs['sp'], regs['cx'],
                regs['dx'], regs['si'], regs['bx'], regs['di'], flags)


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


def _independent_footprint(initial_planes, memory, regs, flags, case,
                           source_segment, game_ds):
    """Separate byte-level shift and VGA write model for clean small cases."""
    require(case['height'] == 1 and not case.get('df'),
            f'{case["name"]}: independent witness is outside its domain')
    width = regs['cx'] & 0xff
    require(0 < width < 0xff,
            f'{case["name"]}: independent witness needs finite output count')
    source_row = oracle.get16(memory, game_ds,
        SYMS['DrawingSourceRowAdvance']['address'])
    destination_row = oracle.get16(memory, game_ds,
        SYMS['DrawingActiveDestinationRowAdvance']['address'])
    if regs['ds'] == game_ds:
        destination_row=(destination_row-1)&0xffff
    plane_extent=oracle.get16(memory, game_ds,
        SYMS['DrawingSourcePlaneExtent']['address'])
    shift=memory[physical(game_ds,SYMS['DrawingLeftBitShiftByte']['address'])]
    shifts=shift or 256
    passes={1:1,2:2,3:3}.get((regs['dx']>>8)&0xff,4)
    direction=-1 if flags&0x400 else 1
    expected_memory=bytearray(memory)

    def source_copy(source_cursor, source_base, count):
        cursor=source_cursor
        for index in range(count):
            expected_memory[physical(game_ds,(source_base+index)&0xffff)] = \
                memory[physical(source_segment,cursor)]
            cursor=(cursor+direction)&0xffff
        expected_memory[physical(game_ds,(source_base+count)&0xffff)] = 0
        return cursor

    def shift_buffer(base):
        for _ in range(shifts):
            at=physical(game_ds,base)
            first=expected_memory[at]
            carry=first&1
            expected_memory[at]=first>>1
            for index in range(1,width+1):
                at=physical(game_ds,(base+index)&0xffff)
                before=expected_memory[at]
                expected_memory[at]=(before>>1)|(carry<<7)
                carry=before&1

    expected_planes=[bytearray(p) for p in initial_planes]
    destination=regs['di']
    # The first pass separately shifts copied source and mask rows, then uses
    # the shifted mask as a bit mask while source bytes drive plane zero.
    source_copy(regs['si'],SYMS['DrawingSourceRowScratch']['address'],width)
    source_copy(regs['bx'],SYMS['DrawingMaskRowScratch']['address'],width)
    shift_buffer(SYMS['DrawingSourceRowScratch']['address'])
    shift_buffer(SYMS['DrawingMaskRowScratch']['address'])
    for index in range(width+1):
        src=expected_memory[physical(game_ds,
            (SYMS['DrawingSourceRowScratch']['address']+index)&0xffff)]
        mask=expected_memory[physical(game_ds,
            (SYMS['DrawingMaskRowScratch']['address']+index)&0xffff)]
        target=(destination+index)&0xffff
        old=expected_planes[0][target]
        expected_planes[0][target]=(src&mask)|(old&(~mask&0xff))
        for plane in range(1,4):
            expected_planes[plane][target]&=(~mask&0xff)

    # Later selected planes read a fresh source row at the ES:66F8 extent and
    # apply logical OR to the selected VGA plane.
    for plane_index in range(1,passes):
        source_cursor=(regs['si']+plane_extent*plane_index)&0xffff
        source_copy(source_cursor,SYMS['DrawingSourceRowScratch']['address'],width)
        shift_buffer(SYMS['DrawingSourceRowScratch']['address'])
        for index in range(width+1):
            src=expected_memory[physical(game_ds,
                (SYMS['DrawingSourceRowScratch']['address']+index)&0xffff)]
            target=(regs['di']+index)&0xffff
            expected_planes[plane_index][target] |= src

    return expected_memory,expected_planes


def _compare_core(lib, case):
    memory, regs, flags, game_ds, source_segment = _prepare(case)
    c_memory=bytearray(memory)
    c_device=TraceDevice(c_memory,case['seed']+START)
    prime_device_stack(case,c_device)
    initial_planes=[bytearray(p) for p in c_device.vga.planes]
    call=_call_of(regs,game_ds,flags)
    c_result=lib.lmn_draw_shifted_masked_core(
        (ctypes.c_uint8*(1<<20)).from_buffer(c_memory),
        ctypes.byref(call),ctypes.byref(c_device.bus))
    c_device.check(case['name']+' C')

    o_memory=bytearray(memory)
    o_device=TraceDevice(o_memory,case['seed']+START)
    prime_device_stack(case,o_device)
    u,seen,edges,_hooks=_oracle_body(case,o_memory,regs,flags,o_device)
    for name,want in (
        ('ax',c_result.work_value),('bx',c_result.mask_cursor),
        ('cx',c_result.packed_counts),('dx',c_result.port),
        ('si',c_result.source_cursor),('di',c_result.destination_cursor),
        ('bp',c_result.plane_counter),('sp',c_result.stack_offset),
        ('ds',c_result.source_segment),('es',c_result.output_segment),
        ('ss',regs['ss']),('cs',regs['cs']),('ip',RETF)):
        require(u.reg_read(oracle.REG[name])==want,
                f'{case["name"]}: {name} C={want:04x}/ASM='
                f'{u.reg_read(oracle.REG[name]):04x}')
    oracle_flags=u.reg_read(x.UC_X86_REG_EFLAGS)
    require(((c_result.flags^oracle_flags)&DEFINED_FLAGS)==0,
            f'{case["name"]}: defined flags C={c_result.flags:04x}/'
            f'ASM={oracle_flags:04x}')
    actual=bytes(u.mem_read(0,1<<20))
    require(actual==c_memory,f'{case["name"]}: full RAM differs')
    code_start=(regs['cs']<<4)+START
    require(actual[code_start:code_start+END-START]==
            relocated(IMAGE,ORACLE['relocations'],regs['cs'])[START:END],
            f'{case["name"]}: original drawing bytes changed')
    require(actual[code_start+0x8add-START]==IMAGE[0x8add],
            f'{case["name"]}: UNKNOWN 8ADD byte changed')
    require(c_device.vga.state()==o_device.vga.state(),
            f'{case["name"]}: VGA plane/latch/register state differs')
    common.compare_event_traces(c_device.events,o_device.events,case['name'])
    if case.get('independent'):
        expected_memory,expected_planes=_independent_footprint(
            initial_planes,memory,regs,flags,case,source_segment,game_ds)
        for plane in range(4):
            require(c_device.vga.planes[plane]==expected_planes[plane],
                    f'{case["name"]}: independent VGA plane {plane} differs')
        for offset in (0x6706,0x6748):
            for index in range((regs['cx']&0xff)+1):
                p=physical(game_ds,(offset+index)&0xffff)
                require(c_memory[p]==expected_memory[p],
                        f'{case["name"]}: independent scratch byte '
                        f'{offset+index:04x} differs')
    report=dict(name=case['name'],seed=case['seed'],input=dict(case,
        relocated_game_data_segment=game_ds,source_segment_initial=source_segment),
        result={name:getattr(c_result,name) for name,_field in c_result._fields_})
    del u,c_device,o_device
    return seen,edges,report


def _check_adapter_retf(lib,case):
    memory,regs,flags,game_ds,_source_segment=_prepare(case)
    o_memory=bytearray(memory)
    o_device=TraceDevice(o_memory,case['seed']+START)
    prime_device_stack(case,o_device)
    u,_seen,_edges,hooks=_oracle_body(case,o_memory,regs,flags,o_device)
    for hook in hooks:
        u.hook_del(hook)
    u.ctl_remove_cache(0,2<<20)
    u.emu_start((regs['cs']<<4)+RETF,0,count=1)
    original_regs={name:u.reg_read(reg) for name,reg in oracle.REG.items()}
    original_flags=u.reg_read(x.UC_X86_REG_EFLAGS)

    c_memory=bytearray(memory)
    c_device=TraceDevice(c_memory,case['seed']+START)
    native_regs=Regs(**regs,flags=flags)
    lib.lmn_draw_shifted_masked_adapter(
        (ctypes.c_uint8*(1<<20)).from_buffer(c_memory),
        ctypes.byref(native_regs),game_ds,ctypes.byref(c_device.bus))
    c_device.check(case['name']+' native RETF adapter')
    for name in oracle.REG_NAMES:
        require(getattr(native_regs,name)==original_regs[name],
                f'{case["name"]}: actual RETF {name} C='
                f'{getattr(native_regs,name):04x}/ASM={original_regs[name]:04x}')
    require((native_regs.flags^original_flags)&DEFINED_FLAGS==0,
            f'{case["name"]}: actual RETF defined flags differ')
    require(c_memory==bytes(u.mem_read(0,1<<20)),
            f'{case["name"]}: actual RETF RAM differs')
    require(c_device.vga.state()==o_device.vga.state(),
            f'{case["name"]}: actual RETF VGA state differs')
    del u,c_device,o_device


def _accounting():
    raw=IMAGE[START:END]
    if len(raw)!=564 or len(ALL_INS)!=318 or len(BODY_INS)!=317:
        raise VerificationFailure(
            f'890E accounting changed: {len(raw)} bytes, '
            f'{len(ALL_INS)} known sites, {len(BODY_INS)} body sites')
    if sha(raw)!=EXPECTED_RANGE_SHA:
        raise VerificationFailure('890E..8B41 raw range hash changed')
    if 0x8add in ALL_INS or IMAGE[0x8add]!=0x90:
        raise VerificationFailure('UNKNOWN 8ADD accounting/preserved byte changed')
    if RETF not in ALL_INS or BODY_INS.get(0x8b40) is None:
        raise VerificationFailure('expected POP DS / RETF boundary is missing')


def _worker(build_directory):
    report_path=BUILD/'shifted-masked-differential.json'
    report_path.unlink(missing_ok=True)
    _accounting()
    baseline=_library(build_directory)
    cases=_cases()
    seen=set()
    edges=set()
    case_reports=[]
    for case in cases:
        if case['name']=='incoming-DS-distinct-from-relocated-frame':
            load=case.get('load',(0x1010,0x1213,0x2345)[case['seed']%3])
            if case['initial_ds']==((load+0x09a9)&0xffff):
                raise VerificationFailure('incoming-DS case is not distinct')
        sites,case_edges,case_report=_compare_core(baseline,case)
        seen|=sites
        edges|=case_edges
        case_reports.append(case_report)
        gc.collect()

    require(seen==set(BODY_INS),
            f'890E body-site coverage differs: missing='
            f'{sorted(set(BODY_INS)-seen)}')
    require(edges==EDGES,
            f'890E branch-edge coverage differs: missing='
            f'{sorted(EDGES-edges)}, extra={sorted(edges-EDGES)}')

    retf_names={'plane-count-02','incoming-DS-distinct-from-relocated-frame',
                'independent-footprint-p2-w2-s3'}
    retf_cases=[case for case in cases if case['name'] in retf_names]
    for case in retf_cases:
        _check_adapter_retf(baseline,case)
        gc.collect()

    sentinels={
        1: next(c for c in cases if c['name']=='shift-5'),
        2: next(c for c in cases if c['name']=='DF-copy-and-sentinel-follow-direction'),
        3: next(c for c in cases if c['name']=='plane-stride-uses-live-ES'),
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
                f'compiled shifted masked mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,**detected))
        gc.collect()

    input_paths=(
        'assets/vgalemmi.exe','c/shifted_masked.c','c/shifted_masked.h',
        'c/special_blit.h','c/regs.h','c/lemmings_sym.h',
        'tests/shifted_masked.py','tests/aligned_masked.py',
        'tests/minimap_vga.py','tests/dat_io.py','tests/dat_io_c.py',
        'tools/common.py','tools/unpack.py','tools/cbuild.py',
        'tools/bounded_process.py','metadata/symbols.json','build/unpack.json',
        'src/planar_drawing.asm')
    report=dict(image='main',image_sha256=sha(IMAGE),
        ranges={'890E..8B41':dict(inclusive='890E..8B41',
            range_sha256=sha(IMAGE[START:END]),physical_code_bytes=564,
            decoded_code_bytes=563,translated_code_bytes=sum(
                ins.size for ins in BODY_INS.values()),
            physical_instruction_sites=318,body_instruction_sites=317,
            body_instruction_addresses=sorted(seen),
            branch_edges=sorted([list(edge) for edge in edges]),
            branch_edge_count=len(edges),unknown_bytes=['8ADD'],
            adapter_instruction_address=RETF)},
        case_count=len(cases),cases=case_reports,mutation_count=len(mutations),
        mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen|{RETF}),
        input_hashes={path:sha((ROOT/path).read_bytes()) for path in input_paths},
        retf_probe_case_count=len(retf_cases),
        retf_probe_cases=[case['name'] for case in retf_cases],
        retf_probe_exclusions=[case['name'] for case in cases
            if case.get('stack_device') or case.get('same_segments') or
            case.get('ss_at_scratch') or case.get('source_is_game')],
        regression_sentinels=[
            dict(mutation=1,behavior='RCR carries the previous SHR/RCR low bit',
                 case=sentinels[1]['name']),
            dict(mutation=2,behavior='scratch INC SI/BX moves forward under DF',
                 case=sentinels[2]['name']),
            dict(mutation=3,behavior='later plane extent comes from live ES:66F8',
                 case=sentinels[3]['name'])],
        dependencies=['metadata/symbols.json','c/special_blit.h','c/regs.h',
                      'tests/minimap_vga.py','tools/bounded_process.py'],
        event_limits=dict(bus_events=MAX_BUS_EVENTS,
                          vga_device_trace=MAX_VGA_EVENTS,
                          original_steps=MAX_STEPS,
                          timeout_seconds=180,memory_mib=512),
        defined_flag_masks=dict(arithmetic='0x0FD7',
                                logical_with_AF_undefined='0x0FC7'),
        device_contract='Constructed 1MiB RAM and quiescent IRQs; tests/minimap_vga.py models four unchained VGA planes, latches, Sequencer and Graphics Controller word ports. No hardware timing or IRQ scheduling is claimed.',
        quirks=[
            'Entry DEC word [DS:6704] uses incoming DS; the relocated MOV AX,09A9 supplies the initial ES. Live stack-restored DS/ES then select scratch, row fields, and the later ES:66F8 plane extent.',
            'The first plane copies source and mask rows through DF, writes directional zero sentinels, then shifts each buffer forward with SHR/RCR. INC preserves the carry; the mask cursor and draw cursor have different stepping rules.',
            'The source and mask shift loops read A948 once per plane. Zero shift runs 256 iterations; CL zero gives the RCR LOOP 65,536 iterations and CL FF makes the output LOOP run 65,536 times.',
            'The initial masked plane uses bit-mask writes and clears planes 1..3 where the mask is set. Later hard-coded map-mask passes OR source bytes into selected planes. The fourth pass has no outer SI/DI/CX restore or BP test.',
            'UNKNOWN 8ADD is outside C byte/site accounting and remains in the hashed original range. Core ends after POP DS at 8B40; the adapter consumes the unchanged RETF at 8B41.'],
        domain='Constructed register and RAM states only. Static analysis reports the discovered incoming jump 8909->890E and no direct outgoing edges or calls. This does not close indirect or modified-code entry domains, valid producer ranges, asynchronous IRQ ownership, or VGA hardware timing.')
    write_json(report_path,report)
    print(f'PASS shifted masked: {len(cases)} cases, {len(seen)} body sites, '
          f'{len(edges)} direct branch edges, {len(retf_cases)} actual RETF probes, '
          f'{len(mutations)} compiled mutations detected')


def main():
    BUILD.mkdir(parents=True,exist_ok=True)
    (BUILD/'shifted-masked-differential.json').unlink(missing_ok=True)
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        _worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='shifted-masked-',parent=BUILD) as temp:
        result=run_bounded([sys.executable,str(Path(__file__).resolve()),
                            '--worker',temp],cwd=ROOT,timeout=180,
                           memory_mib=512,check=False)
        if result.returncode==NATIVE_GUARD_EXIT:
            raise GuardExhaustion('native callback worker hit a finite trace guard')
        if result.returncode==NATIVE_CALLBACK_EXIT:
            raise VerificationFailure('native callback worker callback failed')
        if result.returncode!=0:
            raise VerificationFailure(
                f'bounded worker exited with status {result.returncode}: '
                f'{result.stderr!r}')


if __name__=='__main__':
    main()
