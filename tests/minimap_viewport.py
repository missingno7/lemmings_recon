"""Bounded original/native checks for DrawMinimapViewport (7A5A..7BB7).

This exercises the actual closed leaf and its live stack/VGA bus boundary. It
does not execute the surrounding 3AC8 status renderer or boot the game.
"""
from __future__ import annotations

import copy
import ctypes as ct
import gc
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
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN)
from unicorn import x86_const as x


IMAGE, ORACLE = unpack(ASSET.read_bytes())
LOAD = 0x1010
SIZE, MASK = 1 << 20, (1 << 20) - 1
DATA_SEG = (LOAD + 0x09A9) & 0xFFFF
ENTRY, RET, END = 0x7A5A, 0x7BB7, 0x7BB8
DRAWING_ORIGIN = 0x1F76
CODE = IMAGE[ENTRY:END]
MAX_INSTRUCTIONS, MAX_EVENTS = 8192, 2048
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'minimap-viewport-differential.json'
ORIGINAL_REPORT = BUILD / 'minimap-viewport-original-differential.json'

REG_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
             'cs', 'ds', 'es', 'ss', 'ip')
STATE_NAMES = REG_NAMES + ('flags',)
CORE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp',
              'cs', 'ds', 'es', 'ss', 'sp', 'flags')
REG_ID = {name: getattr(x, 'UC_X86_REG_' + name.upper()) for name in REG_NAMES}
DEFINED_FLAGS = 0x0FD7
LOGIC_FLAGS = 0x0FC7
CF, PF, AF, ZF, SF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x200, 0x400, 0x800
ARITH_FLAGS = CF | PF | AF | ZF | SF | OF
BRANCH_MNEMONICS = {'loop', 'loope', 'loopne', 'jcxz'}

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(CODE, ENTRY)}
BRANCHES = {address for address, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or
            ins.mnemonic.lower() in BRANCH_MNEMONICS}


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in STATE_NAMES]


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES +
                ('continuation', 'status')]


MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32,
                     ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(RuntimeError):
    """Invalid or over-budget original/provider fixture; never mutant credit."""


class Mismatch(AssertionError):
    """A completed native comparison differs from the original contract."""


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get16(memory, segment, offset):
    address = physical(segment, offset)
    lo = memory[address]
    hi = memory[(address + 1) & MASK]
    return lo | (hi << 8)


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        name = ins.mnemonic.lower()
        if not (ins.group(capstone.CS_GRP_JUMP) or name in BRANCH_MNEMONICS):
            continue
        if name not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


EXPECTED_EDGES = branch_edges(INS)


def flags_defined_after(instruction, prior):
    name = instruction.mnemonic.lower()
    if name in ('and', 'or', 'xor', 'test'):
        return LOGIC_FLAGS
    if name in ('add', 'sub', 'cmp'):
        return DEFINED_FLAGS
    if name in ('inc', 'dec'):
        return (DEFINED_FLAGS & ~CF) | (prior & CF)
    if name == 'shr':
        return LOGIC_FLAGS
    if name == 'rcr':
        return (prior & ~(CF | OF)) | CF | OF
    return prior


def make_cases():
    out = []

    def add(name, **spec):
        out.append(dict(name=name, seed=len(out), **spec))

    # The byte phase is bits 4..6 of DS:0000. Exercise every carry path under
    # both incoming DF and IF values; the routine must finish with IF set.
    for phase in range(8):
        for df in (False, True):
            for incoming_if in (False, True):
                add(f'phase-{phase}-df-{int(df)}-if-{int(incoming_if)}',
                    phase_word=phase << 4, phase=phase, df=df,
                    incoming_if=incoming_if, origin=0x0137 + phase * 3)

    add('geometry-origin-wrap-high', phase_word=0xFF90, df=False,
        incoming_if=False, origin=0xFEE0, vga=True, read_map=3)
    add('geometry-origin-wrap-low', phase_word=0x7F70, df=True,
        incoming_if=True, origin=0xE8A1, vga=True, read_map=1)
    add('phase-reread-provider', phase_word=0x0320, df=False,
        incoming_if=True, origin=0x0040, provider='phase-reread',
        provider_value=0x7F70, vga=True, read_map=2)
    add('provider-origin-after-port', phase_word=0x0410, phase=1,
        origin=0x0280, provider='origin-after-first-mask-port',
        provider_origin=0xFFF0, vga=True, read_map=0)

    # The live second POP controls an unchecked DEC/LOOP: AX=0100 with AL=0
    # executes 256 shifts. A separate FF witness exercises its 255-count case.
    add('saved-phase-pop-alias-mirror', phase_word=0, phase=0,
        origin=0x0080, ss=0x5200, sp=0x0010, vga=True, read_map=0)
    add('saved-phase-pop-provider-low', phase_word=0, phase=0,
        origin=0x0100, provider='saved-phase-on-first-mask-port',
        provider_word=0x0003, vga=True, read_map=1)
    add('saved-phase-pop-provider-ff', phase_word=0, phase=0,
        origin=0x0180, provider='saved-phase-on-first-mask-port',
        provider_word=0x00FF, vga=True, read_map=2)
    add('saved-phase-pop-provider-ah-0100', phase_word=0, phase=0,
        origin=0x0200, provider='saved-phase-on-first-mask-port',
        provider_word=0x0100, vga=True, read_map=3)

    # Live SS mirror/RET locations cross the 20-bit aperture boundary, and one
    # deliberately places all saves and the return inside the mapped A000 VGA.
    add('ds-is-ss-live-mirrors', phase_word=0x0060, phase=6,
        origin=0x00C0, ds=0x5300, ss=0x5300, sp=0xD000,
        df=True, incoming_if=False, vga=True, read_map=0)
    add('stack-physical-wrap', phase_word=0x0010, phase=1,
        origin=0x0100, ss=0xFFFF, sp=0xF000,
        incoming_if=True, vga=True, read_map=3)
    add('stack-word-wrap-20bit', phase_word=0x0030, phase=3,
        origin=0x00D0, ss=0xFFFF, sp=0x000F,
        incoming_if=False, vga=True, read_map=1)
    add('stack-and-return-in-vga', phase_word=0x0020, phase=2,
        origin=0x0090, ss=0xA000, sp=0xE000, gc5=0,
        incoming_if=False, vga=True, read_map=0)
    add('return-changed-after-last-port', phase_word=0x0040, phase=4,
        origin=0x0060, provider='return-on-last-mask-port',
        return_before=0x6C31, return_after=0x6C32, vga=True, read_map=2)
    add('ram-aperture-with-null-device', phase_word=0x0050, phase=5,
        origin=0x1000, vga=False, incoming_if=True)

    return out


def setup(case):
    rng = random.Random(0x7A5A ^ (case['seed'] * 0x9E3779B1))
    memory = bytearray(rng.randbytes(SIZE))
    memory[LOAD << 4:(LOAD << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], LOAD)

    ds = case.get('ds', DATA_SEG) & 0xFFFF
    ss = case.get('ss', 0x5200) & 0xFFFF
    sp = case.get('sp', 0xD000) & 0xFFFF
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    regs.update(cs=LOAD, ip=ENTRY, ds=ds, es=0x6200, ss=ss, sp=sp)
    flags = 0x0002 | (rng.randrange(0x1000) & DEFINED_FLAGS)
    flags &= ~0x0100  # The contract holds TF clear.
    if case.get('df', False):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('incoming_if', False):
        flags |= IF
    else:
        flags &= ~IF
    regs['flags'] = flags

    phase_word = case.get('phase_word', (case.get('phase', 0) & 7) << 4) & 0xFFFF
    put16(memory, ds, 0, phase_word)
    put16(memory, ds, DRAWING_ORIGIN, case.get('origin', 0) & 0xFFFF)
    ret = case.get('return_before', 0x6A31 + case['seed']) & 0xFFFF
    put16(memory, ss, sp, ret)

    device = None
    if case.get('vga', True):
        device = MinimapVga(0x7A5A + case['seed'] * 13,
                            read_map=case.get('read_map', case['seed'] & 3))
        device.seq[2] = case.get('initial_map_mask', 0x05) & 0x0F
        device.gc[0] = 0xFF
        device.gc[1] = 0x03
        device.gc[2] = (case['seed'] * 17 + 5) & 0x0F
        device.gc[3] = 0x17
        device.gc[4] = case.get('read_map', case['seed'] & 3) & 3
        device.gc[5] = case.get('gc5', 0x0A) & 0x1F
        device.gc[7] = (case['seed'] * 7 + 3) & 0x0F
        device.gc[8] = 0x5A
        device.gc[6] = 0x05
        if ss == 0xA000:
            # The safe RET lives outside the viewport; reads in mode 0 select
            # plane zero and therefore return this actual live word.
            device.gc[4] = 0
            at = sp
            device.planes[0][at] = ret & 0xFF
            device.planes[0][(at + 1) & 0xFFFF] = ret >> 8
    return memory, regs, device


def phase_after_first_read(case, memory, regs):
    value = get16(memory, regs['ds'], 0)
    if case.get('provider') == 'phase-reread':
        value = case['provider_value']
    elif regs['ds'] == regs['ss']:
        # The setup sequence writes 0005 to SS:0000 before its second live
        # DS:0000 read. With DS=SS, that stack mirror is the value consumed by
        # the shift loop; geometry still uses the earlier read in output_cells.
        value = 0x0005
    return (value >> 4) & 7


def live_popped_phase(case, memory, regs):
    provider = case.get('provider')
    if provider == 'saved-phase-on-first-mask-port':
        return case['provider_word'] & 0xFFFF
    if regs['sp'] == 0x0010 and regs['ss'] == 0x5200:
        # The saved AX at SS:000E aliases the final initial-stage bit-mask
        # mirror (BL:08), which is the last value stored there before POP AX.
        first_phase = phase_after_first_read(case, memory, regs)
        shifted = 0xFFFFFF00 >> first_phase
        # The final initial-stage mask word is BL:08, so the mirror's low
        # byte (and therefore the saved AX low byte) is the low byte of the
        # shifted mask, not its high byte.
        return (((shifted & 0xFF) << 8) | 8)
    return phase_after_first_read(case, memory, regs)


def viewport_masks(case, memory, regs):
    phase = phase_after_first_read(case, memory, regs)
    first = 0xFFFFFF00 >> phase
    popped = live_popped_phase(case, memory, regs)
    loops = popped & 0xFF
    if popped == 0:
        loops = 0
    elif loops == 0:
        loops = 256
    second = 0x80000100
    for _ in range(loops):
        second >>= 1
    return [((first >> shift) & 0xFF) for shift in (24, 16, 8, 0)], \
        [((second >> shift) & 0xFF) for shift in (24, 16, 8, 0)], loops


def output_cells(case, memory, regs):
    initial_phase_word = get16(memory, regs['ds'], 0)
    # Destination DI is fixed by the first DS:0000 read. Providers may change
    # that word only after this read; the initial geometry remains authoritative.
    if case.get('provider') == 'phase-reread':
        initial_phase_word = case['phase_word']
    origin = case.get('origin', 0)
    start = ((initial_phase_word >> 7) + 0x2172 + origin + 2) & 0xFFFF
    df = bool(regs['flags'] & DF)
    first, later, loops = viewport_masks(case, memory, regs)
    cells = []
    di = start
    for mask in first:
        cells.append((di, mask, 'top'))
        di = (di - 1 if df else di + 1) & 0xFFFF
    di = (di + 0x340) & 0xFFFF
    for mask in first:
        cells.append((di, mask, 'bottom'))
        di = (di - 1 if df else di + 1) & 0xFFFF
    di = (di - 0x30) & 0xFFFF
    for row in range(18):
        for mask in later:
            cells.append((di, mask, f'side-{row}'))
            di = (di - 1 if df else di + 1) & 0xFFFF
        di = (di - 0x30) & 0xFFFF
    return cells, loops


def check_independent(case, initial_memory, regs, initial_device, original):
    cells, loops = output_cells(case, initial_memory, regs)
    oracle_require(len(cells) == 80,
                   f'{case["name"]}: independent viewport paint count {len(cells)}')
    oracle_require(original['state']['es'] == 0xA000,
                   f'{case["name"]}: viewport did not leave ES=A000')
    oracle_require((original['state']['flags'] & IF) != 0,
                   f'{case["name"]}: viewport did not leave IF set')
    oracle_require(original['state']['si'] == regs['si'],
                   f'{case["name"]}: SI was not preserved')
    oracle_require(original['state']['ds'] == regs['ds'],
                   f'{case["name"]}: DS was not preserved')
    if initial_device is None or regs['ss'] == 0xA000:
        return dict(paint_cells=len(cells), inner_shift_iterations=loops,
                    plane_check='device/state differential only for VGA-backed stack')

    expected = copy.deepcopy(initial_device)
    for offset, mask, _row in cells:
        offset &= 0xFFFF
        for plane in (0, 1):
            old = expected.planes[plane][offset]
            expected.planes[plane][offset] = (old & (~mask & 0xFF)) | mask
        for plane in (2, 3):
            expected.planes[plane][offset] &= ~mask & 0xFF
    oracle_require(expected.planes == original['device'].planes,
                   f'{case["name"]}: independent 32-bit mask/80-cell plane replay differs')
    return dict(paint_cells=len(cells), inner_shift_iterations=loops,
                plane_check='independent 32-bit mask and sequential 80-cell replay')


class OriginalRun:
    def __init__(self, case, memory, regs, device, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.core = device, core
        self.events, self.sites, self.edges = [], set(), set()
        self.steps, self.read_counts, self.out_count = 0, {}, 0
        self.pending, self.used = [], set()
        self.previous = None
        self.current_flags = regs['flags']
        self.flag_mask = DEFINED_FLAGS
        self.failure = None
        self.stopped = False
        self.continuation = None
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * SIZE)
        data = bytes(memory)
        self.cpu.mem_write(0, data)
        self.cpu.mem_write(SIZE, data)
        for name in REG_NAMES:
            self.cpu.reg_write(REG_ID[name], regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def mirror(linear, physical_address, value):
            byte = bytes((value & 0xFF,))
            for address in (linear, physical_address, physical_address + SIZE):
                if 0 <= address < 2 * SIZE:
                    self.cpu.mem_write(address, byte)

        def flush_provider():
            while self.pending:
                segment, offset, value = self.pending.pop(0)
                for n in range(2):
                    p = physical(segment, (offset + n) & 0xFFFF)
                    byte = (value >> (8 * n)) & 0xFF
                    self.memory[p] = byte
                    mirror(p, p, byte)

        def provider(kind, address):
            c = self.case
            if c.get('provider') == 'phase-reread' and kind == 'read':
                high = physical(regs['ds'], 1)
                if address == high and address not in self.read_counts and 'phase-reread' not in self.used:
                    self.used.add('phase-reread')
                    self.pending.append((regs['ds'], 0, c['provider_value']))

        def on_code(uc, _address, _size, _user):
            flush_provider()
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous in BRANCHES:
                self.edges.add((self.previous, off))
            if self.previous == RET:
                self.continuation = off
                self.stopped = True
                uc.emu_stop()
                return
            if cs != regs['cs'] or off not in INS:
                fail(f'{case["name"]}: original escaped to {cs:04X}:{off:04X}')
                return
            ins = INS[off]
            p = physical(cs, off)
            if bytes(uc.mem_read(p, ins.size)) != bytes(ins.bytes):
                fail(f'{case["name"]}: executing bytes changed at {off:04X}')
                return
            if self.core and off == RET:
                self.continuation = off
                self.stopped = True
                uc.emu_stop()
                return
            if self.steps >= MAX_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction cap exhausted')
                return
            if self.previous is not None:
                self.flag_mask = flags_defined_after(INS[self.previous], self.flag_mask)
            self.steps += 1
            self.sites.add(off)
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.previous = off

        def add_event(kind, address, value):
            if len(self.events) >= MAX_EVENTS:
                fail(f'{case["name"]}: original bus event cap exhausted')
                return
            self.events.append((kind, address, value & (0xFFFF if kind == 'out' else 0xFF),
                                self.current_flags & 0xFFFF, self.flag_mask))

        def on_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original read escaped mapped memory')
                        return
                    p = linear & MASK
                    provider('read', p)
                    value = (self.device.read(self.memory, p, self.current_flags)
                             if self.device is not None and VGA_BASE <= p < VGA_END
                             else self.memory[p])
                    mirror(linear, p, value)
                    add_event('read', p, value)
                    self.read_counts[p] = self.read_counts.get(p, 0) + 1
            except BaseException as error:
                fail(f'{case["name"]}: original read callback failed: {error}')

        def on_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if self.device is not None and VGA_BASE <= p < VGA_END:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    mirror(linear, p, byte)
                    add_event('write', p, byte)
            except BaseException as error:
                fail(f'{case["name"]}: original write callback failed: {error}')

        def on_out(uc, port, size, value, _user):
            try:
                if size != 2:
                    fail(f'{case["name"]}: expected VGA word OUT, got width {size}')
                    return
                if self.device is not None:
                    self.device.out(port, value, self.current_flags)
                add_event('out', port, value)
                index = self.out_count
                self.out_count += 1
                c = self.case
                if (c.get('provider') == 'saved-phase-on-first-mask-port' and
                        index == 5 and 'saved-phase-on-first-mask-port' not in self.used):
                    self.used.add('saved-phase-on-first-mask-port')
                    put16(self.memory, regs['ss'], (regs['sp'] - 2) & 0xFFFF,
                          c['provider_word'])
                    put16(uc_memory_proxy(self.cpu), regs['ss'],
                          (regs['sp'] - 2) & 0xFFFF, c['provider_word'])
                elif (c.get('provider') == 'origin-after-first-mask-port' and
                      index == 5 and 'origin-after-first-mask-port' not in self.used):
                    self.used.add('origin-after-first-mask-port')
                    put16(self.memory, regs['ds'], DRAWING_ORIGIN,
                          c['provider_origin'])
                    put16(uc_memory_proxy(self.cpu), regs['ds'], DRAWING_ORIGIN,
                          c['provider_origin'])
                elif (c.get('provider') == 'return-on-last-mask-port' and
                      index == 84 and 'return-on-last-mask-port' not in self.used):
                    self.used.add('return-on-last-mask-port')
                    put16(self.memory, regs['ss'], regs['sp'], c['return_after'])
                    put16(uc_memory_proxy(self.cpu), regs['ss'], regs['sp'],
                          c['return_after'])
            except BaseException as error:
                fail(f'{case["name"]}: original OUT callback failed: {error}')

        self.callbacks = (on_code, on_read, on_write, on_out)
        self.cpu.hook_add(UC_HOOK_CODE, on_code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, on_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
        self.cpu.hook_add(UC_HOOK_INSN, on_out, None, 1, 0,
                          x.UC_X86_INS_OUT)

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs_in['cs'], ENTRY), 0,
                               count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original failed')
        oracle_require(self.stopped, f'{self.case["name"]}: did not reach the declared boundary')
        oracle_require(len(self.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original event budget exhausted')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REG_NAMES}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        ram = bytes(self.cpu.mem_read(0, SIZE))
        oracle_require(ram == bytes(self.memory),
                       f'{self.case["name"]}: Unicorn and canonical RAM differ')
        expected_sites = set(INS) - ({RET} if self.core else set())
        oracle_require(self.sites <= expected_sites,
                       f'{self.case["name"]}: executed site escaped the body')
        if self.core:
            oracle_require(state['ip'] == RET,
                           f'{self.case["name"]}: core did not stop before RET')
        else:
            oracle_require(self.previous == RET and self.continuation is not None,
                           f'{self.case["name"]}: actual RET was not observed')
            state['ip'] = self.continuation
        code_p = LOAD << 4
        oracle_require(ram[code_p + ENTRY:code_p + END] == CODE,
                       f'{self.case["name"]}: executing viewport bytes changed')
        oracle_require(self.out_count == 85,
                       f'{self.case["name"]}: VGA OUT count {self.out_count}, expected 85')
        return dict(memory=ram, state=state, events=self.events, sites=self.sites,
                    edges=self.edges, steps=self.steps, device=self.device,
                    continuation=state['ip'], flag_mask=self.flag_mask,
                    used=set(self.used))


def uc_memory_proxy(cpu):
    """Tiny proxy for provider writes that must be visible to the next fetch."""
    class Proxy:
        def __setitem__(self, index, value):
            cpu.mem_write(index, bytes((value & 0xFF,)))
    return Proxy()


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events, self.used, self.out_count = [], set(), 0

        def reserve():
            if len(self.events) >= MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native minimap viewport callback cap exhausted')

        def read(_ctx, _ram, address, flags):
            try:
                reserve()
                p = address & MASK
                value = (self.device.read(self.memory, p, flags)
                         if self.device is not None and VGA_BASE <= p < VGA_END
                         else self.memory[p])
                self.events.append(('read', p, value & 0xFF,
                                    flags & 0xFFFF, DEFINED_FLAGS))
                if (case.get('provider') == 'phase-reread' and
                        p == physical(regs['ds'], 1) and
                        'phase-reread' not in self.used):
                    self.used.add('phase-reread')
                    put16(self.memory, regs['ds'], 0, case['provider_value'])
                return value
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native minimap viewport read callback failed: {error}')
                return 0

        def write(_ctx, _ram, address, value, flags):
            try:
                reserve()
                p, value = address & MASK, value & 0xFF
                if self.device is not None and VGA_BASE <= p < VGA_END:
                    self.device.write(self.memory, p, value, flags)
                else:
                    self.memory[p] = value
                self.events.append(('write', p, value,
                                    flags & 0xFFFF, DEFINED_FLAGS))
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native minimap viewport write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                reserve()
                if self.device is not None:
                    self.device.out(port, value, flags)
                self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                                    flags & 0xFFFF, DEFINED_FLAGS))
                index = self.out_count
                self.out_count += 1
                if (case.get('provider') == 'saved-phase-on-first-mask-port' and
                        index == 5 and 'saved-phase-on-first-mask-port' not in self.used):
                    self.used.add('saved-phase-on-first-mask-port')
                    put16(self.memory, regs['ss'], (regs['sp'] - 2) & 0xFFFF,
                          case['provider_word'])
                elif (case.get('provider') == 'origin-after-first-mask-port' and
                      index == 5 and 'origin-after-first-mask-port' not in self.used):
                    self.used.add('origin-after-first-mask-port')
                    put16(self.memory, regs['ds'], DRAWING_ORIGIN,
                          case['provider_origin'])
                elif (case.get('provider') == 'return-on-last-mask-port' and
                      index == 84 and 'return-on-last-mask-port' not in self.used):
                    self.used.add('return-on-last-mask-port')
                    put16(self.memory, regs['ss'], regs['sp'], case['return_after'])
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native minimap viewport OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'minimap-viewport-m{mutation}.dll',
                     mutation, 'minimap_viewport')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_draw_minimap_viewport_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_draw_minimap_viewport_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callbacks = NativeBus(case, memory, regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(callbacks.bus))
            for name in CORE_NAMES:
                setattr(state, name, getattr(result, name))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(callbacks.bus))
        final = {name: getattr(state, name) & 0xFFFF for name in STATE_NAMES}
        return dict(memory=bytes(memory), state=final, events=callbacks.events,
                    used=callbacks.used, device=device, status=status,
                    continuation=final['ip'], out_count=callbacks.out_count)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    original_device = copy.deepcopy(device)
    expected = OriginalRun(case, bytearray(initial), dict(regs),
                           copy.deepcopy(device), core=core).run()
    independent = check_independent(case, initial, regs, original_device, expected)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == 0, f'{label}: native status {actual["status"]}')
    for name in STATE_NAMES:
        if name == 'flags':
            require(((actual['state'][name] ^ expected['state'][name]) &
                     expected['flag_mask']) == 0,
                    f'{label}: defined FLAGS differ')
        else:
            require(actual['state'][name] == expected['state'][name],
                    f'{label}: {name} {actual["state"][name]:04X}/'
                    f'{expected["state"][name]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full RAM differs')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: provider effects {actual["used"]}/{expected["used"]}')
    if expected['device'] is None:
        require(actual['device'] is None, label + ': unexpected VGA device')
    else:
        require(actual['device'] is not None and
                actual['device'].state() == expected['device'].state(),
                label + ': VGA planes/latches/register state differs')
    return dict(name=case['name'], core=core, sites=sorted(expected['sites']),
                edges=[list(edge) for edge in sorted(expected['edges'])],
                events=len(expected['events']), steps=expected['steps'],
                paint_cells=independent['paint_cells'],
                inner_shift_iterations=independent['inner_shift_iterations'],
                independent_plane_check=independent['plane_check'])


def input_hashes():
    paths = (
        'assets/vgalemmi.exe',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'src/program.asm',
        'src/minimap_viewport.asm', 'src/game_code_late_tail.asm',
        'src/minimap.asm', 'c/minimap_viewport.c', 'c/minimap_viewport.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/minimap_viewport.py', 'tests/minimap_vga.py',
        'tests/dat_io.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/unpack.py', 'tools/difftest.py',
        'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'required input hashes missing: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'viewport inputs changed before preflight')
    rows, sites, edges = [], set(), set()
    for case in specs:
        initial, regs, device = setup(case)
        original_device = copy.deepcopy(device)
        for core in (True, False):
            expected = OriginalRun(case, bytearray(initial), dict(regs),
                                   copy.deepcopy(device), core=core).run()
            independent = check_independent(case, initial, regs,
                                            original_device, expected)
            rows.append(dict(name=case['name'], core=core,
                             sites=sorted(expected['sites']),
                             edges=[list(edge) for edge in sorted(expected['edges'])],
                             events=len(expected['events']), steps=expected['steps'],
                             paint_cells=independent['paint_cells'],
                             inner_shift_iterations=independent['inner_shift_iterations'],
                             independent_plane_check=independent['plane_check']))
            sites.update(expected['sites'])
            edges.update(expected['edges'])
        gc.collect()
    oracle_require(sites == set(INS),
                   f'original site union differs: missing={sorted(set(INS)-sites)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'original branch outcomes differ: missing={sorted(EXPECTED_EDGES-edges)} '
                   f'extra={sorted(edges-EXPECTED_EDGES)}')
    oracle_require(before == input_hashes(), 'viewport inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    import json
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'viewport inputs changed before native worker')
    specs = make_cases()
    original_rows, _, _ = original_campaign(specs, before)
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == set(INS),
                   f'native site union differs: missing={sorted(set(INS)-sites)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'native edge union differs: missing={sorted(EXPECTED_EDGES-edges)} '
                   f'extra={sorted(edges-EXPECTED_EDGES)}')

    witness_cases = {
        1: ('geometry-origin-wrap-high', True),
        2: ('phase-reread-provider', True),
        3: ('saved-phase-pop-provider-low', True),
        4: ('saved-phase-pop-provider-ah-0100', True),
        5: ('phase-7-df-1-if-1', True),
        6: ('phase-3-df-0-if-0', True),
        7: ('phase-5-df-0-if-1', True),
        8: ('phase-7-df-0-if-0', True),
        9: ('return-changed-after-last-port', False),
    }
    by_name = {case['name']: case for case in specs}
    detected = []
    for mutation, (name, core) in witness_cases.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=core)
        except Mismatch as error:
            detected.append(dict(mutation=mutation, case=name, core=core,
                                 completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'minimap viewport mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(before == input_hashes(), 'viewport inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
        translated_code_bytes=sum(ins.size for ins in INS.values()),
        instruction_sites=len(INS), static_instruction_addresses=sorted(INS),
        branch_edge_count=len(EXPECTED_EDGES), static_branch_edges=[list(e) for e in sorted(EXPECTED_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(detected), mutations=detected,
        executed_instruction_addresses=sorted(sites), branch_edges=[list(e) for e in sorted(edges)],
        total_bus_events=total_events, original_instruction_steps=total_steps,
        original_only_comparisons=len(original_rows), cases=rows, input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='DrawMinimapViewport 7A5A..7BB7, complete closed body. Compares '
               'full 1 MiB RAM, all 13 logical roles, original-defined FLAGS, '
               'ordered RAM/VGA bus events and VGA planes/latches/registers. '
               'Core stops before RET; adapter consumes the live SS:SP word. '
               'Independent calculation replays the two 32-bit masks and all '
               '80 paint cells; provider, DF, IF, geometry-wrap and VGA-backed '
               'stack fixtures remain explicit.'))
    print(f'PASS minimap viewport: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(detected)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        BUILD.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='minimap-viewport-original-',
                                        parent=BUILD) as directory:
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        import json
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        specs = make_cases()
        rows, sites, edges = original_campaign(specs, before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, END]],
            translated_code_bytes=sum(ins.size for ins in INS.values()),
            instruction_sites=len(INS), static_instruction_addresses=sorted(INS),
            branch_edge_count=len(EXPECTED_EDGES), executed_instruction_addresses=sorted(sites),
            branch_edges=[list(e) for e in sorted(edges)], case_count=len(specs),
            core_adapter_comparisons=len(rows), input_hashes=before, cases=rows,
            domain='Bounded original-only complete viewport core/RET-adapter campaign; '
                   'provider, 20-bit stack, DF/IF and independent mask/plane checks.'))
        print(f'PASS minimap viewport original preflight: {len(specs)} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} actual edges', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: minimap_viewport.py [--original-only | --worker DIR]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='minimap-viewport-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
