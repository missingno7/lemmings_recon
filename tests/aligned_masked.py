"""Bounded original/native checks for the aligned masked planar body."""
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

from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs, MEM
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
START = SYMS['PlanarAlignedMaskedDefaultBody']['address']
END = SYMS['PlanarAlignedMaskedFarReturn']['address'] + 1
RETF = SYMS['PlanarAlignedMaskedFarReturn']['address']
UNKNOWN = {0x94c7, 0x9507}
MAX_STEPS = 3_000_000
# The CL=0, one-row witness performs 65,536 first-plane iterations. Each one
# emits seven bounded RAM/VGA bus events; 500,000 covers that finite trace.
MAX_BUS_EVENTS = 500_000
# The same witness emits three VGA-device trace items per byte plus setup.
MAX_VGA_EVENTS = 200_000
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87
DEFINED_FLAGS = 0x0fd7
UNDEFINED_AF_FLAGS = 0x0fc7
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
ALL_INS = {i.address: i for i in MD.disasm(IMAGE[START:END], START)
           if i.address not in UNKNOWN}
BODY_INS = {a: i for a, i in ALL_INS.items() if a != RETF}
BRANCHES = {pc for pc, i in BODY_INS.items()
            if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES = {(pc, i.operands[0].imm & 0xffff) for pc, i in BODY_INS.items()
         if pc in BRANCHES}
EDGES |= {(pc, pc + i.size) for pc, i in BODY_INS.items()
          if pc in BRANCHES and i.mnemonic != 'jmp'}
LOGICAL = {'and', 'or', 'xor', 'test'}
ARITH = {'add', 'sub', 'dec', 'inc', 'mul', 'neg'}


class VerificationFailure(RuntimeError):
    """An oracle, fixture, resource, or control-flow guard failed."""


class GuardExhaustion(VerificationFailure):
    """A finite access/step budget was reached; this is never a mutant hit."""


class Mismatch(AssertionError):
    """A completed bounded C/original comparison found a behavioral difference."""


def exit_worker(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


class EventTrace:
    """Bounded streaming event record; hashes order, stores flags for exact masks."""
    _KINDS = {'read': 0, 'write': 1, 'out': 2}

    def __init__(self):
        self.digest = hashlib.sha256()
        self.count = 0
        self.flag_bytes = bytearray()
        self.mask_bytes = bytearray()
        self.exhausted = False
        self.prefix = []

    def add(self, kind, address, value, flags, mask=0xffff):
        self.count += 1
        if self.count > MAX_BUS_EVENTS:
            self.exhausted = True
            return
        code = self._KINDS[kind]
        address &= 0xffffffff
        value &= 0xffff
        self.digest.update(struct.pack('<BIH', code, address, value))
        self.flag_bytes.extend(struct.pack('<H', flags & 0xffff))
        self.mask_bytes.extend(struct.pack('<H', mask & 0xffff))
        if len(self.prefix) < 16:
            self.prefix.append((kind, address, value, flags & 0xffff, mask & 0xffff))

    def check(self, label):
        if self.exhausted:
            raise GuardExhaustion(
                f'{label}: bus-event cap {MAX_BUS_EVENTS} exhausted')


READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class TraceDevice:
    """The independent four-plane fixture and a finite whole-bus trace."""
    def __init__(self, memory, seed, read_map=0):
        self.memory = memory
        self.vga = MinimapVga(seed, read_map)
        # A000 stack aliases can write before this body programs the VGA.
        self.vga.seq[2] = 0x0f
        self.vga.gc[0] = 0
        self.vga.gc[1] = 0
        self.vga.gc[3] = 0
        self.vga.gc[5] = 0
        self.vga.gc[8] = 0xff
        self.events = EventTrace()
        self.errors = []
        self.vga_exhausted = False

        def guard_vga_trace():
            if len(self.vga.trace) > MAX_VGA_EVENTS:
                self.vga.trace.pop()
                self.vga_exhausted = True

        def stop_on_guard(label):
            if self.events.exhausted or self.vga_exhausted:
                exit_worker(NATIVE_GUARD_EXIT,
                            f'{label}: native bus/VGA trace guard exhausted')

        def record_callback_error(error, label):
            self.record_error(error)
            exit_worker(NATIVE_CALLBACK_EXIT,
                        f'{label}: native callback failed: {self.errors[0]}')

        def read(_ctx, _mem, address, flags):
            p = address & 0xfffff
            try:
                value = (self.vga.read(self.memory, p, flags)
                         if VGA_BASE <= p < VGA_END else self.memory[p])
                self.events.add('read', p, value, flags)
                guard_vga_trace()
                stop_on_guard('native read')
                return value
            except BaseException as error:
                record_callback_error(error, 'native read')
                return 0

        def write(_ctx, _mem, address, value, flags):
            p = address & 0xfffff
            try:
                if VGA_BASE <= p < VGA_END:
                    self.vga.write(self.memory, p, value, flags)
                    guard_vga_trace()
                else:
                    self.memory[p] = value
                self.events.add('write', p, value, flags)
                stop_on_guard('native write')
            except BaseException as error:
                record_callback_error(error, 'native write')

        def out(_ctx, port, value, flags):
            try:
                self.vga.out(port, value, flags)
                guard_vga_trace()
                self.events.add('out', port, value, flags)
                stop_on_guard('native out')
            except BaseException as error:
                record_callback_error(error, 'native out')

        self._read = READ(read)
        self._write = WRITE(write)
        self._out = OUT(out)
        self.bus = RasterBus(None, self._read, self._write, self._out)

    def check(self, label):
        self.events.check(label)
        if self.vga_exhausted:
            raise GuardExhaustion(
                f'{label}: VGA trace cap {MAX_VGA_EVENTS} exhausted')
        if self.errors:
            raise VerificationFailure(f'{label}: bounded VGA callback failed: '
                                      f'{self.errors[0]}')

    def record_error(self, error):
        if not self.errors:
            self.errors.append(f'{type(error).__name__}: {error}')


def physical(segment, offset):
    return (((segment << 4) + offset) & 0xfffff)


def put_byte(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xff


def put16(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 0xff
    memory[(p + 1) & 0xfffff] = (value >> 8) & 0xff


def prime_device_stack(case, device):
    if not case.get('stack_device'):
        return
    plane = device.vga.gc[4] & 3
    sp = case.get('sp', 0x8000)
    ip = case.get('outer_ip', 0xedd1)
    cs = case.get('outer_cs', 0xbabe)
    for n, value in enumerate((ip & 0xff, ip >> 8, cs & 0xff, cs >> 8)):
        device.vga.planes[plane][(sp + n) & 0xffff] = value & 0xff


def field(name):
    return SYMS[name]['address']


def cases():
    result = []

    def add(name, **kwargs):
        result.append(dict(name=name, seed=len(result), **kwargs))

    add('masked-first-plane-partial-latch-merge', plane_limit=1, width=1,
        height=1, independent=True, mask_bytes=(0x0f,), source_bytes=(0xa5,),
        read_map=2)
    add('two-planes-multibyte-multiline', plane_limit=2, width=2,
        height=2, independent=True)
    add('three-planes-last-plane-three', plane_limit=3, width=2,
        height=1, independent=True)
    add('four-planes-final-plane-four', plane_limit=4, width=3,
        height=2, independent=True, read_map=3)
    add('zero-plane-limit-underflows-to-four-passes', plane_limit=0, width=2,
        height=1)
    add('above-four-plane-limit-still-four-passes', plane_limit=5, width=1,
        height=1)
    add('ff-plane-limit-still-four-passes', plane_limit=0xff, width=1,
        height=2)
    add('DF-one-source-and-destination-reverse-mask-forward', plane_limit=4,
        width=2, height=2, df=True, source_cursor=0x2100,
        destination_cursor=0x0430)
    add('zero-CL-wraps-to-65536-bytes-one-plane', plane_limit=1, width=0,
        height=1)
    add('zero-CH-wraps-to-256-rows-one-plane', plane_limit=1, width=1,
        height=0, independent=True)
    add('twenty-bit-source-stack-and-cursor-wrap', plane_limit=2, width=2,
        height=1, source_segment=0xffff, source_cursor=0xfffe,
        mask_cursor=0xffff, destination_cursor=0xfffe, ss=0xffff, sp=0x0010,
        df=True)
    add('entry-push-overwrites-live-graphics-segment', plane_limit=1,
        width=1, height=1, same_segments=True, sp=0x1fe6)
    add('live-save-words-alias-source-and-destination-strides', plane_limit=1,
        width=1, height=1, same_segments=True, sp=0x6708)
    add('live-save-word-aliases-plane-extent', plane_limit=2,
        width=1, height=1, same_segments=True, sp=0x6700)
    add('source-and-destination-share-vga-aperture', plane_limit=1,
        width=1, height=1, source_segment=0xa000, source_cursor=0x0200,
        mask_cursor=0x0100, destination_cursor=0x0200)
    add('SS-aperture-stack-writes', plane_limit=1, width=1, height=1,
        ss=0xa000, sp=0x5000, destination_cursor=0x5100, stack_device=True)
    add('SP-FFFE-return-frame-wrap', plane_limit=1, width=1, height=1,
        sp=0xfffe, return_boundary=True)
    add('first-plane-two-rows-expose-DS-restore', plane_limit=1, width=1,
        height=2, source_bytes=(0x12, 0x34), source_row_advance=0x0007,
        mask_bytes=(0xff, 0xff))
    add('mask-cursor-INC-BX-7fff-to-8000', plane_limit=1, width=1,
        height=1, mask_cursor=0x7fff, source_row_advance=0)
    add('incoming-DS-distinct-from-relocated-game-DS', plane_limit=1,
        width=1, height=1, initial_data_segment=0x6000)
    return result


def prepare(case):
    rng = random.Random(0x93f6 + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    memory = bytearray(rng.randbytes(1 << 20))
    memory[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    game_ds = (load + 0x09a9) & 0xffff
    data_ds = game_ds
    initial_ds = case.get('initial_data_segment', data_ds)
    ss = case.get('ss', 0x7000)
    sp = case.get('sp', 0x8000)
    source_segment = case.get('source_segment', 0x5000)
    if case.get('same_segments'):
        ss = data_ds
        initial_ds = data_ds
    put16(memory, data_ds, field('DrawingSourcePlaneExtent'), 0x0023)
    put16(memory, data_ds, field('DrawingSourceRowAdvance'),
          case.get('source_row_advance', 0x0007))
    put16(memory, data_ds, field('DrawingActiveDestinationRowAdvance'), 0x0009)
    put16(memory, initial_ds, field('GraphicsResourceSegment'), source_segment)
    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=initial_ds,
                ss=ss, sp=sp,
                cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
                dx=((case['plane_limit'] & 0xff) << 8) |
                   case.get('low_state', 0x6d),
                bx=case.get('mask_cursor', 0x1000),
                si=case.get('source_cursor', 0x2000),
                di=case.get('destination_cursor', 0x0410))
    if case.get('same_segments'):
        regs['ds'] = data_ds
    flags = 2 | ((case['seed'] * 0x95) & 0xad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
          case.get('outer_cs', 0xbabe))
    for n, value in enumerate(case.get('mask_bytes', ())):
        put_byte(memory, source_segment, (regs['bx'] + n) & 0xffff, value)
    for n, value in enumerate(case.get('source_bytes', ())):
        put_byte(memory, source_segment, (regs['si'] + n) & 0xffff, value)
    return memory, regs, flags, game_ds


def library(build_directory, mutation=0):
    path = build(Path(build_directory) / f'aligned-masked-m{mutation}.dll',
                 mutation, 'aligned_masked')
    lib = ctypes.CDLL(str(path))

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

    lib.lmn_draw_aligned_masked_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    lib.lmn_draw_aligned_masked_core.restype = Result
    lib.lmn_draw_aligned_masked_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint16, ctypes.POINTER(RasterBus)]
    lib.lmn_draw_aligned_masked_adapter.restype = None
    lib._MaskedCall = Call
    lib._MaskedResult = Result
    return lib


def call_of(lib, regs, game_ds, flags):
    return lib._MaskedCall(regs['ds'], game_ds, regs['ss'], regs['sp'],
                           regs['cx'], regs['dx'], regs['si'], regs['bx'],
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
        if last_op in LOGICAL:
            flag_mask = UNDEFINED_AF_FLAGS
        elif last_op in ARITH:
            flag_mask = DEFINED_FLAGS
        instruction_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        seen.add(off)
        previous = off
        steps += 1
        if steps > MAX_STEPS:
            stop_failure(uc, f'{case["name"]}: original step cap {MAX_STEPS} exhausted')
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
                stop_failure(uc, f'{case["name"]}: original memory-read callback failed')
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
                stop_failure(uc, f'{case["name"]}: original memory-write callback failed')
                return
            if device.events.exhausted or device.vga_exhausted:
                uc.emu_stop()
                return

    def out(uc, _port, size, value, _):
        port = uc.reg_read(x.UC_X86_REG_DX)
        try:
            if size == 1 and hasattr(device, 'out_port_byte'):
                device.out_port_byte(port, value, instruction_flags, flag_mask)
            elif size == 2:
                device.vga.out(port, value, instruction_flags)
                device.events.add('out', port, value, instruction_flags, flag_mask)
            else:
                stop_failure(uc, f'{case["name"]}: unsupported original port output')
                return
            if len(device.vga.trace) > MAX_VGA_EVENTS:
                device.vga.trace.pop()
                device.vga_exhausted = True
        except BaseException as error:
            device.record_error(error)
            stop_failure(uc, f'{case["name"]}: original VGA output callback failed')

    def inp(uc, port, size, _):
        if size != 1 or not hasattr(device, 'in_port_byte'):
            stop_failure(uc, f'{case["name"]}: unsupported original port input')
            return 0
        try:
            return device.in_port_byte(port, instruction_flags, flag_mask, uc)
        except BaseException as error:
            device.record_error(error)
            stop_failure(uc, f'{case["name"]}: original byte input callback failed')
            return 0

    def intr(uc, number, _):
        stop_failure(uc, f'{case["name"]}: unexpected INT{number:02x}')

    code_hook = u.hook_add(UC_HOOK_CODE, code)
    read_hook = u.hook_add(UC_HOOK_MEM_READ, mem_read)
    write_hook = u.hook_add(UC_HOOK_MEM_WRITE, mem_write)
    out_hook = u.hook_add(UC_HOOK_INSN, out, None, 1, 0,
                          x.UC_X86_INS_OUT)
    in_hook = u.hook_add(UC_HOOK_INSN, inp, None, 1, 0, x.UC_X86_INS_IN)
    intr_hook = u.hook_add(UC_HOOK_INTR, intr)
    wrap_read_hook = u.hook_add(UC_HOOK_MEM_READ, lambda uc, a, p, n, v, d:
                                _wrap_read(uc, p, n))
    wrap_write_hook = u.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, p, n, v, d:
                                 _wrap_write(uc, p, n, v))
    try:
        u.emu_start((regs['cs'] << 4) + START, 0, count=MAX_STEPS)
    except BaseException as error:
        raise VerificationFailure(f'{case["name"]}: original execution failed: {error}')
    if callback_failure:
        if 'cap' in callback_failure[0]:
            raise GuardExhaustion(callback_failure[0])
        raise VerificationFailure(callback_failure[0])
    device.check(case['name'] + ' original')
    if not finished:
        raise VerificationFailure(f'{case["name"]}: original did not stop before RETF')
    if steps >= MAX_STEPS:
        raise GuardExhaustion(f'{case["name"]}: original step cap exhausted')
    return u, seen, edges, (code_hook, read_hook, write_hook, out_hook, in_hook,
                            intr_hook, wrap_read_hook, wrap_write_hook)


def _wrap_read(uc, address, size):
    for i in range(size):
        raw = address + i
        if raw >= (1 << 20):
            uc.mem_write(raw, bytes(uc.mem_read(raw & 0xfffff, 1)))


def _wrap_write(uc, address, size, value):
    for i in range(size):
        raw = address + i
        if raw >= (1 << 20):
            uc.mem_write(raw & 0xfffff, bytes(((value >> (8 * i)) & 0xff,)))


def compare_event_traces(c_trace, o_trace, name):
    c_trace.check(name + ' C')
    o_trace.check(name + ' original')
    require(c_trace.count == o_trace.count,
            f'{name}: ordered bus event count differs '
            f'{c_trace.count}/{o_trace.count}')
    require(c_trace.digest.digest() == o_trace.digest.digest(),
            f'{name}: ordered bus kind/address/value digest differs '
            f'C-prefix={c_trace.prefix!r}/ASM-prefix={o_trace.prefix!r}')
    for n in range(c_trace.count):
        offset = n * 2
        mask = o_trace.mask_bytes[offset] | (o_trace.mask_bytes[offset + 1] << 8)
        c_flags = c_trace.flag_bytes[offset] | (c_trace.flag_bytes[offset + 1] << 8)
        o_flags = o_trace.flag_bytes[offset] | (o_trace.flag_bytes[offset + 1] << 8)
        if (c_flags ^ o_flags) & mask:
            require(False, f'{name}: bus flags differ at event {n}: '
                    f'C={c_flags:04x}/ASM={o_flags:04x}, mask={mask:04x}')


def independent_planes(initial_planes, memory, regs, case, flags):
    expected = [bytearray(plane) for plane in initial_planes]
    source_segment = oracle.get16(memory, regs['ds'], field('GraphicsResourceSegment'))
    extent = oracle.get16(memory, (regs['cs'] + 0x09a9) & 0xffff,
                          field('DrawingSourcePlaneExtent'))
    source_advance = case.get('source_row_advance', 0x0007)
    destination_advance = 0x0009
    width = regs['cx'] & 0xff
    rows_byte = (regs['cx'] >> 8) & 0xff
    rows = rows_byte if rows_byte else 256
    direction = -1 if flags & 0x0400 else 1
    limit = (regs['dx'] >> 8) & 0xff
    passes = limit if 1 <= limit <= 3 else 4
    initial_source = regs['si']
    initial_mask = regs['bx']
    initial_destination = regs['di']
    for pass_index in range(passes):
        source = (initial_source + pass_index * extent) & 0xffff
        mask = initial_mask
        destination = initial_destination
        for _ in range(rows):
            for _ in range(width):
                source_byte = memory[physical(source_segment, source)]
                target = destination & 0xffff
                if pass_index == 0:
                    mask_byte = memory[physical(source_segment, mask)]
                    keep = (~mask_byte) & 0xff
                    old = expected[0][target]
                    expected[0][target] = (source_byte & mask_byte) | (old & keep)
                    for plane in range(1, 4):
                        expected[plane][target] &= keep
                    mask = (mask + 1) & 0xffff
                else:
                    expected[pass_index][target] = (
                        source_byte | expected[pass_index][target])
                source = (source + direction) & 0xffff
                destination = (destination + direction) & 0xffff
            source = (source + source_advance) & 0xffff
            destination = (destination + destination_advance) & 0xffff
            if pass_index == 0:
                mask = (mask + source_advance) & 0xffff
    return expected


def compare_core(lib, case):
    memory, regs, flags, game_ds = prepare(case)
    c_memory = bytearray(memory)
    c_device = TraceDevice(c_memory, case['seed'] + 0x93f6,
                           case.get('read_map', 0))
    prime_device_stack(case, c_device)
    starting_planes = [bytearray(p) for p in c_device.vga.planes]
    call = call_of(lib, regs, game_ds, flags)
    c_result = lib.lmn_draw_aligned_masked_core(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(call), ctypes.byref(c_device.bus))
    c_device.check(case['name'] + ' C')

    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + 0x93f6,
                           case.get('read_map', 0))
    prime_device_stack(case, o_device)
    u, seen, edges, hooks = oracle_body(case, o_memory, regs, flags, o_device)
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
        expected = independent_planes(starting_planes, memory, regs, case, flags)
        if c_device.vga.planes != expected:
            diff = next((p, n) for p in range(4)
                        for n, (a, b) in enumerate(zip(c_device.vga.planes[p],
                                                       expected[p])) if a != b)
            plane, offset = diff
            raise Mismatch(f'{case["name"]}: independent VGA plane footprint '
                           f'differs at {plane}:{offset:04x}')
    del u, c_device, o_device
    return seen, edges, c_result


def check_adapter(lib, case):
    memory, regs, flags, game_ds = prepare(case)
    native_memory = bytearray(memory)
    native_device = TraceDevice(native_memory, case['seed'] + 0x93f6,
                                case.get('read_map', 0))
    prime_device_stack(case, native_device)
    native_regs = Regs(**regs, flags=flags)
    lib.lmn_draw_aligned_masked_adapter(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(native_memory),
        ctypes.byref(native_regs), game_ds, ctypes.byref(native_device.bus))
    native_device.check(case['name'] + ' adapter')

    logical_memory = bytearray(memory)
    logical_device = TraceDevice(logical_memory, case['seed'] + 0x93f6,
                                 case.get('read_map', 0))
    prime_device_stack(case, logical_device)
    call = call_of(lib, regs, game_ds, flags)
    result = lib.lmn_draw_aligned_masked_core(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(logical_memory),
        ctypes.byref(call), ctypes.byref(logical_device.bus))
    logical_device.check(case['name'] + ' logical adapter reference')

    def read8(segment, offset):
        p = physical(segment, offset)
        return (logical_device.vga.read(logical_memory, p, result.flags)
                if VGA_BASE <= p < VGA_END else logical_memory[p])

    sp = result.stack_offset
    ip = read8(regs['ss'], sp) | (read8(regs['ss'], (sp + 1) & 0xffff) << 8)
    sp = (sp + 2) & 0xffff
    cs = read8(regs['ss'], sp) | (read8(regs['ss'], (sp + 1) & 0xffff) << 8)
    sp = (sp + 2) & 0xffff
    logical_device.check(case['name'] + ' manual far return')
    expected = dict(ip=ip, cs=cs, sp=sp, ax=result.work_value,
                    bx=result.mask_cursor, cx=result.packed_counts,
                    dx=result.port, si=result.source_cursor,
                    di=result.destination_cursor, bp=result.plane_counter,
                    ds=result.source_segment, es=result.output_segment,
                    ss=regs['ss'], flags=result.flags)
    for name, want in expected.items():
        require(getattr(native_regs, name) == want,
                f'{case["name"]}: adapter {name} C={getattr(native_regs, name):04x}/'
                f'manual={want:04x}')
    require(native_memory == logical_memory,
            f'{case["name"]}: adapter memory/VGA mirror differs')
    require(native_device.vga.state() == logical_device.vga.state(),
            f'{case["name"]}: adapter VGA state differs from sequenced pops')


def isolated_original_retf(lib, case):
    """Single-step the untouched RETF opcode after removing every read hook."""
    memory, regs, flags, game_ds = prepare(case)
    o_memory = bytearray(memory)
    o_device = TraceDevice(o_memory, case['seed'] + 0x93f6,
                           case.get('read_map', 0))
    u, _seen, _edges, hooks = oracle_body(case, o_memory, regs, flags, o_device)
    for hook in hooks:
        u.hook_del(hook)
    u.ctl_remove_cache(0, 2 << 20)
    u.emu_start((regs['cs'] << 4) + RETF, 0, count=1)
    original_regs = {name: u.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = u.reg_read(x.UC_X86_REG_EFLAGS)

    native_memory = bytearray(memory)
    native_device = TraceDevice(native_memory, case['seed'] + 0x93f6,
                                case.get('read_map', 0))
    native_regs = Regs(**regs, flags=flags)
    lib.lmn_draw_aligned_masked_adapter(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(native_memory),
        ctypes.byref(native_regs), game_ds, ctypes.byref(native_device.bus))
    native_device.check(case['name'] + ' adapter RETF probe')
    for name in oracle.REG_NAMES:
        require(getattr(native_regs, name) == original_regs[name],
                f'{case["name"]}: isolated original RETF {name} C='
                f'{getattr(native_regs, name):04x}/ASM={original_regs[name]:04x}')
    require(native_memory == bytes(u.mem_read(0, 1 << 20)),
            f'{case["name"]}: isolated original RETF RAM differs')
    require((native_regs.flags ^ original_flags) & DEFINED_FLAGS == 0,
            f'{case["name"]}: isolated RETF flags differ')


def raw_bus_parity(lib):
    case = dict(name='nullbus-rawram-parity', seed=0x4d, plane_limit=2,
                width=2, height=1)
    memory, regs, flags, game_ds = prepare(case)
    null_memory = bytearray(memory)
    raw_memory = bytearray(memory)
    call = call_of(lib, regs, game_ds, flags)
    null_result = lib.lmn_draw_aligned_masked_core(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(null_memory),
        ctypes.byref(call), None)

    @READ
    def raw_read(_ctx, _mem, address, _flags):
        return raw_memory[address & 0xfffff]

    @WRITE
    def raw_write(_ctx, _mem, address, value, _flags):
        raw_memory[address & 0xfffff] = value

    @OUT
    def raw_out(_ctx, _port, _value, _flags):
        pass

    bus = RasterBus(None, raw_read, raw_write, raw_out)
    raw_result = lib.lmn_draw_aligned_masked_core(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(raw_memory),
        ctypes.byref(call), ctypes.byref(bus))
    require(null_memory == raw_memory and bytes(null_result) == bytes(raw_result),
            'null-bus and raw-RAM callback parity differs')


def worker(build_directory):
    (BUILD / 'aligned-masked-differential.json').unlink(missing_ok=True)
    if len(ALL_INS) != 166 or sum(i.size for i in ALL_INS.values()) != 326:
        raise VerificationFailure(f'unexpected static accounting: '
                                  f'{len(ALL_INS)} sites/{sum(i.size for i in ALL_INS.values())} bytes')
    if any(IMAGE[a] != 0x90 for a in UNKNOWN):
        raise VerificationFailure('Excluded UNKNOWN NOP bytes changed')
    baseline = library(build_directory)
    fixture_cases = cases()
    seen = set()
    edges = set()
    case_reports = []
    for case in fixture_cases:
        load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
        game_ds = (load + 0x09a9) & 0xffff
        if (case['name'] == 'incoming-DS-distinct-from-relocated-game-DS' and
                case['initial_data_segment'] == game_ds):
            raise VerificationFailure('incoming DS case no longer differs from game DS')
        sites, case_edges, result = compare_core(baseline, case)
        seen |= sites
        edges |= case_edges
        case_reports.append(dict(name=case['name'], seed=case['seed'],
                                 input=dict(case, relocated_game_data_segment=game_ds),
                                 result={n: getattr(result, n)
                                         for n, _ in result._fields_}))
        gc.collect()
    if seen != set(BODY_INS):
        raise VerificationFailure(f'C body site coverage differs: '
                                  f'missing={sorted(set(BODY_INS)-seen)}')
    if edges != EDGES:
        raise VerificationFailure(f'C branch-edge coverage differs: '
                                  f'missing={sorted(EDGES-edges)}, '
                                  f'extra={sorted(edges-EDGES)}')

    adapter_cases = [fixture_cases[3], fixture_cases[15], fixture_cases[16]]
    for case in adapter_cases:
        check_adapter(baseline, case)
        gc.collect()
    retf_cases = [case for case in fixture_cases
                  if not case.get('stack_device') and
                  not case.get('return_boundary') and
                  case['name'] in {
                      'masked-first-plane-partial-latch-merge',
                      'two-planes-multibyte-multiline',
                      'four-planes-final-plane-four',
                      'first-plane-two-rows-expose-DS-restore'}]
    for case in retf_cases:
        isolated_original_retf(baseline, case)
        gc.collect()
    raw_bus_parity(baseline)

    mutation_sentinels = {
        1: next(c for c in fixture_cases
                if c['name'] == 'masked-first-plane-partial-latch-merge'),
        2: next(c for c in fixture_cases
                if c['name'] == 'first-plane-two-rows-expose-DS-restore'),
        3: next(c for c in fixture_cases
                if c['name'] == 'four-planes-final-plane-four'),
    }
    mutations = []
    for mutation in (1, 2, 3):
        mutant = library(build_directory, mutation)
        detected = None
        try:
            compare_core(mutant, mutation_sentinels[mutation])
        except Mismatch as mismatch:
            detected = dict(case=mutation_sentinels[mutation]['name'],
                            reason=str(mismatch))
        if detected is None:
            raise VerificationFailure(f'compiled masked mutation {mutation} survived')
        mutations.append(dict(mutation=mutation, **detected))
        gc.collect()

    input_paths = (
        'assets/vgalemmi.exe', 'c/aligned_masked.c', 'c/aligned_masked.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/aligned_masked.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tools/common.py', 'tools/unpack.py',
        'tools/cbuild.py', 'tools/bounded_process.py',
        'metadata/symbols.json', 'build/unpack.json', 'src/planar_drawing.asm',
        'tools/difftest.py', 'tools/coverage.py', 'docs/aligned-masked.md')
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
        physical_code_bytes=END-START, translated_code_bytes=sum(i.size for i in ALL_INS.values()),
        c_body_code_bytes=sum(i.size for i in BODY_INS.values()),
        adapter_code_bytes=1, physical_instruction_sites=len(ALL_INS),
        c_body_instruction_sites=len(BODY_INS), adapter_instruction_sites=1,
        adapter_instruction_addresses=[RETF],
        original_retf_probe_address=RETF,
        original_retf_probe_case_count=len(retf_cases),
        original_retf_probe_cases=[c['name'] for c in retf_cases],
        original_retf_probe_exclusions=[c['name'] for c in fixture_cases
            if c.get('stack_device') or c.get('return_boundary')],
        unknown_sites_excluded=sorted(UNKNOWN),
        branch_edge_count=len(edges),
        event_limits=dict(bus_events=MAX_BUS_EVENTS, vga_device_trace=MAX_VGA_EVENTS,
                          original_steps=MAX_STEPS),
        defined_flag_masks=dict(arithmetic='0x0FD7',
                                logical_with_AF_undefined='0x0FC7'),
        input_hashes={p: sha((ROOT / p).read_bytes()) for p in input_paths},
        device_contract='tests/minimap_vga.py; unchained A000 64KiB aperture, read mode 0, write mode 0 replace/OR and bit mask, four latches, Sequencer/Graphics Controller word ports; no IRQ scheduling',
        domain='Constructed RAM and quiescent IRQs. Normal entry93F6 has one discovered external static edge93F1->93F6; other indirect/modified-code incoming domains remain unproven. The body stops after POP DS953C, and only its boundary adapter consumes live RETF953D. UNKNOWN94C7/9507 are excluded. SS=A000 and SP=FFFE retain explicit adapter domains excluded from the original RETF single-step subset.')
    write_json(BUILD / 'aligned-masked-differential.json', report)
    print(f'PASS aligned masked: {len(fixture_cases)} cases, {len(seen)} body sites, '
          f'{len(edges)} branch edges; {len(retf_cases)} original RETF probes; '
          f'{len(mutations)} compiled mutations detected')


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'aligned-masked-differential.json').unlink(missing_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='aligned-masked-', parent=BUILD) as temp:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--worker', temp], cwd=ROOT, timeout=180,
                              memory_mib=512, check=False)
        if result.returncode == NATIVE_GUARD_EXIT:
            raise GuardExhaustion('native callback worker exited on a finite trace guard')
        if result.returncode == NATIVE_CALLBACK_EXIT:
            raise VerificationFailure('native callback worker exited on a callback error')
        if result.returncode != 0:
            raise VerificationFailure(f'bounded worker exited with status {result.returncode}')


if __name__ == '__main__':
    main()
