"""Bounded parent/child differential checks for the 5F0F entity stroke."""
import copy
import ctypes
import gc
import os
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
import entity_pixel as pixel
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN)
from unicorn import x86_const as x


IMAGE, UNPACK = pixel.IMAGE, pixel.ORACLE
LOAD = pixel.LOAD
SIZE = 1 << 20
MASK = SIZE - 1
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
TABLE = 0x547C
MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
PARENT_ENTRY, PARENT_RET, PARENT_END = 0x5F0F, 0x5FAB, 0x5FAC
CHILD_ENTRY, CHILD_RET, CHILD_END = 0x5DC6, 0x5DF7, 0x5DF8
MAX_EVENTS, MAX_INSTRUCTIONS = 256, 300
GUARD_EXIT, CALLBACK_EXIT = 86, 87
INITIAL_DEFINED_FLAGS = 0x0FD7
CF, PF, AF, ZF, SF, OF = 0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0800
ARITH_FLAGS = CF | PF | AF | ZF | SF | OF
LOGIC_DEFINED_FLAGS = 0x0FC7  # Logic/shift defined flags plus preserved control.
MUL_DEFINED_FLAGS = 0x0F01  # MUL defines CF/OF; TF/IF/DF remain preserved.
REPORT = BUILD / 'entity-stroke-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_CODE = IMAGE[PARENT_ENTRY:PARENT_END]
CHILD_CODE = IMAGE[CHILD_ENTRY:CHILD_END]
PARENT_INS = {i.address: i for i in MD.disasm(PARENT_CODE, PARENT_ENTRY)}
CHILD_INS = {i.address: i for i in MD.disasm(CHILD_CODE, CHILD_ENTRY)}
INS = dict(CHILD_INS)
INS.update(PARENT_INS)
BRANCHES = {pc for pc, ins in INS.items()
            if (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.startswith('loop'))}
EXPECTED_EDGES = {
    (0x5F49, 0x5F4B), (0x5F49, 0x5F4E),
    (0x5F65, 0x5F67), (0x5F65, 0x5F6D),
    (0x5F6B, 0x5F67), (0x5F6B, 0x5F6D),
    (0x5DD1, 0x5DD3), (0x5DD1, 0x5DD5),
}
REGS = pixel.REGS
REG_ID = pixel.REG_ID

READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset',
                 'record_cursor', 'flags')]


class CoreResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'mask_word', 'spill_word', 'destination_offset',
                 'output_segment', 'port', 'stack_offset', 'flags',
                 'continuation', 'ready_to_return')]


class OracleFailure(AssertionError):
    """The pinned original failed to complete the declared bounded span."""


class Mismatch(AssertionError):
    """A completed native result differs from completed original execution."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def flags_defined_after(instruction, prior_mask):
    """Track flag definedness through this instruction, not routine-wide."""
    mnemonic = instruction.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return LOGIC_DEFINED_FLAGS
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return INITIAL_DEFINED_FLAGS
    if mnemonic in ('dec', 'inc'):
        # DEC/INC preserve CF exactly, including whether that bit was defined.
        return (INITIAL_DEFINED_FLAGS & ~CF) | (prior_mask & CF)
    if mnemonic == 'mul':
        return MUL_DEFINED_FLAGS
    if mnemonic.startswith('shl') or mnemonic.startswith('shr'):
        return LOGIC_DEFINED_FLAGS
    if mnemonic.startswith('rcl') or mnemonic.startswith('rcr'):
        # RCR replaces CF/OF and preserves the definedness of the other flags
        # (notably PF/ZF/SF produced by the preceding SHR); AF is undefined.
        return (prior_mask & ~(AF | CF | OF)) | CF | OF
    return prior_mask


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


def putword(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def getword(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def set_plane_word(device, offset, value, plane=3):
    device.planes[plane][offset & 0xFFFF] = value & 0xFF
    device.planes[plane][(offset + 1) & 0xFFFF] = (value >> 8) & 0xFF


def cases():
    """Parent-focused cases; the child is composed but not re-matrixed."""
    specs = []
    for index in range(8):
        specs.append((f'shift-index-{index}', {
            'x': 0x0120 + index, 'add': 0, 'y': 0x0027}))
    specs.extend((
        ('marker-nonnegative', {'x': 0x1234, 'add': 3, 'marker': 0x7F}),
        ('marker-negative', {'x': 0x1234, 'add': 3, 'marker': 0x80}),
        ('child-y-0000', {'x': 0x0312, 'y': 0x0000}),
        ('child-y-0010', {'x': 0x0312, 'y': 0x0010}),
        ('child-y-0011', {'x': 0x0312, 'y': 0x0011}),
        ('child-y-7fff', {'x': 0x0312, 'y': 0x7FFF}),
        ('child-y-8000', {'x': 0x0312, 'y': 0x8000}),
        ('child-y-8010', {'x': 0x0312, 'y': 0x8010}),
        ('child-y-ffff', {'x': 0x0312, 'y': 0xFFFF}),
        ('negative-marker-coordinate-wrap', {
            'x': 2, 'add': 1, 'marker': 0xFF, 'y': 0x0022}),
        ('df-clear', {'x': 0x0125, 'df': False, 'vga': True}),
        ('df-set', {'x': 0x0125, 'df': True, 'vga': True}),
        ('record-offset-wrap', {'si': 0xFFFE, 'x': 0xA137, 'y': 0x7FFF}),
        ('record-physical-word-wrap', {
            'ds': 0xFFFF, 'si': 0x000F, 'x': 0xA137, 'y': 0x0031}),
        ('stack-sp-zero', {'sp': 0x0000}),
        ('stack-sp-one', {'sp': 0x0001}),
        ('stack-sp-ffff', {'sp': 0xFFFF}),
        ('stack-physical-wrap', {'ss': 0xFFFF, 'sp': 0x0011}),
        # PUSH Y writes DS:SI+4 before the later ADD reads that word.
        ('ds-ss-live-offset-after-push', {
            'ds': 0x3000, 'ss': 0x3000, 'si': 0x1000,
            'sp': 0x1006, 'x': 0x0123, 'add': 0x0035, 'y': 0x0040}),
        # The child reads a table byte which the live parent's temp-X save
        # has placed over DS:547C+4.
        ('stack-overwrites-live-mask-table', {
            'ds': 0x3000, 'ss': 0x3000, 'si': 0x1000,
            'sp': 0x5486, 'x': 0x1234, 'y': 0x0030}),
        ('ss-vga-stack-and-mirrors', {
            'ss': 0xA000, 'sp': 0x5480, 'vga': True}),
        ('ds-vga-record-and-table', {
            'ds': 0xA000, 'ss': 0x5200, 'si': 0x1230,
            'x': 0x1285, 'y': 0x0034, 'add': 2, 'vga': True}),
        ('vga-read-mode-one', {
            'gc5': 0x08, 'gc2': 0x05, 'gc7': 0x0F, 'vga': True}),
        ('vga-write-mode-one', {'gc5': 0x01, 'vga': True}),
        # The child's second read of Y changes the saved X/Y words before the
        # caller's POP [SI] / POP [SI+2] consume them.
        ('provider-changes-live-saved-coordinates', {
            'ds': 0x3100, 'ss': 0x5200, 'si': 0x1000, 'sp': 0x8100,
            'x': 0x1357, 'y': 0x0032, 'mutate': 'saved-coordinates'}),
        # Change the actual near-CALL return word during the child's live Y
        # read. The original stops at the new continuation before executing it.
        ('provider-changes-child-return', {
            'ds': 0x3200, 'ss': 0x5300, 'si': 0x1200, 'sp': 0x8300,
            'x': 0x1357, 'y': 0x0032, 'mutate': 'child-return'}),
        # SS:0008 is also the live Sequencer-2 mirror and therefore replaces
        # the outer near-RET word before the adapter consumes it.
        ('outer-ret-sequencer-mirror-alias', {
            'ds': 0x3000, 'ss': 0x3000, 'si': 0x1000, 'sp': 0x0008,
            'x': 0x0131, 'y': 0x0024}),
        ('outer-ret-arbitrary-target', {'return_word': 0xBEEF}),
    ))
    for n in range(4):
        specs.append((f'seeded-state-{n}', {
            'x': (0xA513 + n * 0x211) & 0xFFFF,
            'add': (0x17D + n * 0x329) & 0xFFFF,
            'y': (0x71E7 + n * 0x37D) & 0xFFFF,
            'df': bool(n & 1), 'ds': 0x3100 + n * 0x101,
            'ss': 0x5200 + n * 0x113, 'gc5': (0, 1, 8, 9)[n],
            'gc2': (0, 5, 10, 15)[n], 'gc7': (15, 8, 3, 0)[n],
            'vga': True}))
    rows = [dict(name=name, seed=i, **updates)
            for i, (name, updates) in enumerate(specs)]
    if len(rows) != 40:
        raise OracleFailure(f'Entity stroke case count changed: {len(rows)}')
    return rows


def configure_device(case, seed):
    device = MinimapVga(seed, read_map=case.get('read_map', 3))
    device.seq[2] = case.get('seq_mask', 0x0F) & 0x0F
    device.gc[0] = case.get('gc0', 0x03) & 0x0F
    device.gc[1] = case.get('gc1', 0x05) & 0x0F
    device.gc[2] = case.get('gc2', (seed * 7 + 3) & 0x0F) & 0x0F
    device.gc[3] = case.get('gc3', (seed * 5 + 1) & 0x1F) & 0x1F
    device.gc[4] = case.get('read_map', 3) & 3
    device.gc[5] = case.get('gc5', 0) & 0x0B
    device.gc[6] = 0x05
    device.gc[7] = case.get('gc7', (seed * 11 + 5) & 0x0F) & 0x0F
    device.gc[8] = case.get('gc8', (seed * 13 + 7) & 0xFF)
    return device


def prepare(case):
    rng = random.Random(0x5F0F + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = pixel.relocated(IMAGE, UNPACK['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    regs = {name: rng.randrange(65536) for name in REGS}
    regs.update(cs=LOAD, ip=PARENT_ENTRY,
                ds=case.get('ds', DATA_SEGMENT),
                ss=case.get('ss', 0x5000),
                es=rng.randrange(65536), si=case.get('si', 0x5000),
                sp=case.get('sp', 0x8000))
    if case.get('outer_ret_sequencer_alias'):
        regs['sp'] = 8
    flags = 2 | (rng.randrange(65536) & (0x0FD7 & ~0x0100))
    flags &= ~0x0100  # Keep TF clear for a bounded intact-code execution.
    flags = flags | 0x0400 if case.get('df', False) else flags & ~0x0400
    regs['flags'] = flags

    device = configure_device(case, 0x5F0F + case['seed'])
    xvalue, yvalue = case.get('x', 0x1237), case.get('y', 0x0027)
    addvalue = case.get('add', 0)
    marker = case.get('marker', 0x01)
    if regs['ds'] == 0xA000:
        # The device, not the aperture cache, owns record/table bytes here.
        set_plane_word(device, regs['si'], xvalue)
        set_plane_word(device, (regs['si'] + 2) & 0xFFFF, yvalue)
        set_plane_word(device, (regs['si'] + 4) & 0xFFFF, addvalue)
        device.planes[3][(regs['si'] + 0x27) & 0xFFFF] = marker
        for index, value in enumerate(MASKS):
            device.planes[3][(TABLE + index) & 0xFFFF] = value
    else:
        putword(memory, regs['ds'], regs['si'], xvalue)
        putword(memory, regs['ds'], (regs['si'] + 2) & 0xFFFF, yvalue)
        putword(memory, regs['ds'], (regs['si'] + 4) & 0xFFFF, addvalue)
        memory[physical(regs['ds'], (regs['si'] + 0x27) & 0xFFFF)] = marker
        if regs['ds'] != DATA_SEGMENT:
            for index, value in enumerate(MASKS):
                memory[physical(regs['ds'], TABLE + index)] = value
        else:
            actual = bytes(memory[physical(regs['ds'], TABLE + i)]
                           for i in range(8))
            oracle_require(actual == MASKS,
                           'Canonical DS:547C mask table identity changed')

    return_word = case.get('return_word', (0xE300 | case['seed']) & 0xFFFF)
    putword(memory, regs['ss'], regs['sp'], return_word)
    if regs['ss'] == 0xA000:
        set_plane_word(device, regs['sp'], return_word)
    return memory, regs, device


def mutation_effects(case, regs):
    ds, ss, si, sp = regs['ds'], regs['ss'], regs['si'], regs['sp']
    trigger = physical(ds, (si + 2) & 0xFFFF)
    if case.get('mutate') == 'saved-coordinates':
        # The parent reads Y once, then DEC [SI+2] performs its own read;
        # the child's subsequent MOV reads Y for the third time.
        return [(trigger, 3, [
            (physical(ss, (sp - 4) & 0xFFFF), bytes.fromhex('B2 A1')),
            (physical(ss, (sp - 2) & 0xFFFF), bytes.fromhex('D4 C3')),
        ])]
    if case.get('mutate') == 'child-return':
        return [(trigger, 3, [
            (physical(ss, (sp - 8) & 0xFFFF), bytes.fromhex('9F 5F')),
        ])]
    return []


class NativeBus:
    def __init__(self, memory, device, effects):
        self.memory, self.device = memory, device
        self.effects = list(effects)
        self.used_effects = set()
        self.read_counts = {}
        self.events = []

        def reserve():
            if len(self.events) >= MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native entity-stroke bus trace cap exhausted')

        def apply_effect(address):
            count = self.read_counts.get(address, 0)
            for index, (trigger, after, writes) in enumerate(self.effects):
                if (index not in self.used_effects and address == trigger and
                        count == after):
                    self.used_effects.add(index)
                    for target, data in writes:
                        for offset, value in enumerate(data):
                            self.memory[(target + offset) & MASK] = value

        def read(_context, _mem, address, flags):
            try:
                reserve()
                address &= MASK
                value = (self.device.read(self.memory, address, flags)
                         if VGA_BASE <= address < VGA_END else self.memory[address])
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                self.read_counts[address] = self.read_counts.get(address, 0) + 1
                apply_effect(address)
                if len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native MinimapVga trace cap exhausted')
                return value
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native entity-stroke read callback failed: {error}')
                return 0

        def write(_context, _mem, address, value, flags):
            try:
                reserve()
                address &= MASK
                value &= 0xFF
                if VGA_BASE <= address < VGA_END:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                if len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native MinimapVga trace cap exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native entity-stroke write callback failed: {error}')

        def out(_context, port, value, flags):
            try:
                reserve()
                self.device.out(port, value, flags)
                self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                                    flags & 0xFFFF))
                if len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native MinimapVga trace cap exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native entity-stroke OUT callback failed: {error}')

        self._read, self._write, self._out = READ(read), WRITE(write), OUT(out)
        self.bus = RasterBus(None, self._read, self._write, self._out)


class OriginalRun:
    """Run only the parent and its direct pixel child, stopping at real RETs."""
    def __init__(self, case, memory, regs, device, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.core = device, core
        self.events, self.sites, self.edges = [], set(), set()
        self.read_counts = {}
        self.previous = None
        self.current_offset = None
        self.current_flags = regs['flags']
        self.flag_mask = INITIAL_DEFINED_FLAGS
        self.current_mask = INITIAL_DEFINED_FLAGS
        self.failure = None
        self.stopped = False
        self.stop_kind = None
        self.continuation = None
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * SIZE)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(SIZE, initial)
        for name in REGS:
            self.cpu.reg_write(REG_ID[name], regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])
        self.effects = mutation_effects(case, regs)
        self.used_effects = set()

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def mirror(linear, physical_address, value):
            byte = bytes((value & 0xFF,))
            for address in (linear, physical_address,
                            physical_address + SIZE):
                if 0 <= address < 2 * SIZE:
                    self.cpu.mem_write(address, byte)

        def add_event(kind, address, value):
            if len(self.events) >= MAX_EVENTS:
                fail(f'{case["name"]}: original bus event budget exhausted')
                return
            self.events.append((kind, address, value & 0xFFFF,
                                self.current_flags & 0xFFFF,
                                self.current_mask))

        def apply_effect(address):
            count = self.read_counts.get(address, 0)
            for index, (trigger, after, writes) in enumerate(self.effects):
                if (index not in self.used_effects and address == trigger and
                        count == after):
                    self.used_effects.add(index)
                    for target, data in writes:
                        for offset, value in enumerate(data):
                            p = (target + offset) & MASK
                            memory[p] = value
                            mirror(p, p, value)

        def code(uc, _address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous in BRANCHES:
                self.edges.add((self.previous, off))
            if self.previous == CHILD_RET:
                self.continuation = off
                if off != 0x5F57:
                    self.stop_kind = 'changed-child-return'
                    self.stopped = True
                    uc.emu_stop()
                    return
            if self.previous == PARENT_RET:
                self.continuation = off
                self.stop_kind = 'outer-return'
                self.stopped = True
                uc.emu_stop()
                return
            if cs != regs['cs'] or off not in INS:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if self.core and off == PARENT_RET:
                self.continuation = off
                self.stop_kind = 'core-boundary'
                self.stopped = True
                uc.emu_stop()
                return
            if len(self.sites) >= MAX_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.sites.add(off)
            self.current_offset = off
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.current_mask = self.flag_mask
            self.flag_mask = flags_defined_after(INS[off], self.flag_mask)
            self.previous = off

        def memory_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original read escaped mapped RAM')
                        return
                    p = linear & MASK
                    value = (device.read(memory, p, self.current_flags)
                             if VGA_BASE <= p < VGA_END else memory[p])
                    add_event('read', p, value)
                    if self.failure:
                        return
                    mirror(linear, p, value)
                    self.read_counts[p] = self.read_counts.get(p, 0) + 1
                    apply_effect(p)
                    if len(device.trace) > MAX_EVENTS:
                        fail(f'{case["name"]}: original VGA event budget exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original read provider failed: {error}')

        def memory_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original write escaped mapped RAM')
                        return
                    p = linear & MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if VGA_BASE <= p < VGA_END:
                        device.write(memory, p, byte, self.current_flags)
                    else:
                        memory[p] = byte
                    add_event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
                    if len(device.trace) > MAX_EVENTS:
                        fail(f'{case["name"]}: original VGA event budget exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original write provider failed: {error}')

        def output(uc, port, size, value, _user):
            try:
                if size != 2:
                    fail(f'{case["name"]}: unexpected non-word OUT size {size}')
                    return
                device.out(port, value, self.current_flags)
                add_event('out', port, value)
                if len(device.trace) > MAX_EVENTS:
                    fail(f'{case["name"]}: original VGA OUT budget exhausted')
            except BaseException as error:
                fail(f'{case["name"]}: original OUT provider failed: {error}')

        self._callbacks = (code, memory_read, memory_write, output)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
        self.cpu.hook_add(UC_HOOK_INSN, output, None, 1, 0, x.UC_X86_INS_OUT)

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs_in['cs'], PARENT_ENTRY), 0,
                               count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original missed bounded continuation')
        oracle_require(len(self.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original bus budget exhausted')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        return dict(memory=bytes(self.cpu.mem_read(0, SIZE)), state=state,
                    events=self.events, sites=self.sites, edges=self.edges,
                    device=self.device, stop_kind=self.stop_kind,
                    continuation=self.continuation,
                    flag_mask=self.flag_mask)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-stroke-m{mutation}.dll',
                     mutation, 'entity_stroke')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_draw_entity_stroke_core
        self.core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
        self.core.restype = CoreResult
        self.adapter = self.library.lmn_draw_entity_stroke_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
        self.adapter.restype = None


def c_buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


def compare_state(case, actual, expected, label, error_type=Mismatch,
                  flag_mask=INITIAL_DEFINED_FLAGS):
    for name in REGS:
        if actual[name] != expected[name]:
            raise error_type(f'{case["name"]} {label} {name} differs: '
                             f'{actual[name]:04X}/{expected[name]:04X}')
    if ((actual['flags'] ^ expected['flags']) & flag_mask) != 0:
        raise error_type(f'{case["name"]} {label} flags differ: '
                         f'{actual["flags"]:04X}/{expected["flags"]:04X}')


def compare_memory(case, actual, expected, label, error_type=Mismatch):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    raise error_type(f'{case["name"]} {label} RAM differs at {mismatch:05X}: '
                     f'{actual[mismatch]:02X}/{expected[mismatch]:02X}')


def compare_events(case, actual, expected):
    require(len(actual) == len(expected),
            f'{case["name"]}: bus event count differs {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        if got[:3] != want[:3]:
            raise Mismatch(f'{case["name"]}: bus event {index} differs: '
                           f'{got[:3]!r}/{want[:3]!r}')
        if ((got[3] ^ want[3]) & want[4]) != 0:
            raise Mismatch(f'{case["name"]}: bus flags differ at event {index}: '
                           f'{got[3]:04X}/{want[3]:04X}')


def compare_device(case, actual, expected):
    require(actual.state() == expected.state(),
            f'{case["name"]}: VGA planes/latches/registers differ')


def check_known_shift(case, initial_device, result):
    if not case['name'].startswith('shift-index-'):
        return
    index = int(case['name'].rsplit('-', 1)[1])
    xvalue = case.get('x', 0x1237)
    temporary_x = (xvalue + case.get('add', 0)) & 0xFFFF
    yvalue = case.get('y', 0x0027)
    row = (yvalue - 17) & 0xFFFF
    if row & 0x8000:
        row = 0
    start = (((row * 208) & 0xFFFF) + (temporary_x >> 3) + 0x4A40) & 0xFFFF
    mask24 = 0xFC00 >> index
    expected_masks = ((mask24 >> 16) & 0xFF,
                      (mask24 >> 8) & 0xFF, mask24 & 0xFF)
    expected_planes = [bytes(plane) for plane in initial_device.planes]
    plane3 = bytearray(expected_planes[3])
    for step, mask in enumerate(expected_masks):
        at = (start + step) & 0xFFFF
        plane3[at] |= mask
    expected_planes[3] = bytes(plane3)
    for plane in range(4):
        oracle_require(bytes(result['device'].planes[plane]) == expected_planes[plane],
                       f'{case["name"]}: original plane {plane} violates the '
                       '24-bit shifted-mask placement')
    oracle_require(result['state']['di'] == ((start + 3) & 0xFFFF),
                   f'{case["name"]}: original final DI differs from known address')
    oracle_require(result['device'].seq[2] == 0x0F and
                   result['device'].gc[0] == 0x08 and
                   result['device'].gc[1] == 0x08 and
                   result['device'].gc[3] == 0x00 and
                   result['device'].gc[8] == expected_masks[2],
                   f'{case["name"]}: original programmed VGA registers differ')


def native_run(native, case, initial, initial_regs, initial_device, *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    callbacks = NativeBus(memory, device, mutation_effects(case, initial_regs))
    state = dict(initial_regs)
    if core:
        call = Call(state['ds'], state['ss'], state['sp'], state['si'], state['flags'])
        result = native.core(c_buffer(memory), ctypes.byref(call),
                             ctypes.byref(callbacks.bus))
        state.update(ax=result.value, bx=result.mask_word, cx=result.spill_word,
                     di=result.destination_offset, es=result.output_segment,
                     dx=result.port, sp=result.stack_offset, flags=result.flags,
                     ip=result.continuation)
        return dict(memory=bytes(memory), state=state, events=callbacks.events,
                    device=device, ready=result.ready_to_return,
                    continuation=result.continuation)
    live = Regs(**{name: state[name] for name in REGS}, flags=state['flags'])
    native.adapter(c_buffer(memory), ctypes.byref(live), ctypes.byref(callbacks.bus))
    state = {name: getattr(live, name) for name in REGS}
    state['flags'] = live.flags
    return dict(memory=bytes(memory), state=state, events=callbacks.events,
                device=device, ready=None, continuation=state['ip'])


def compare_case(native, case, *, core):
    initial, initial_regs, initial_device = prepare(case)
    oracle_memory = bytearray(initial)
    oracle = OriginalRun(case, oracle_memory, dict(initial_regs),
                        copy.deepcopy(initial_device), core=core).run()
    check_known_shift(case, initial_device, oracle)
    native_result = native_run(native, case, initial, initial_regs,
                               initial_device, core=core)
    label = 'core' if core else 'adapter'
    compare_state(case, native_result['state'], oracle['state'], label,
                  flag_mask=oracle['flag_mask'])
    compare_memory(case, native_result['memory'], oracle['memory'], label)
    compare_events(case, native_result['events'], oracle['events'])
    compare_device(case, native_result['device'], oracle['device'])
    if oracle['stop_kind'] == 'changed-child-return':
        if case.get('mutate') == 'child-return':
            oracle_require(oracle['continuation'] == 0x5F9F,
                           case['name'] + ': provider-set child return differs')
        oracle_require(native_result['state']['ip'] == oracle['continuation'],
                       case['name'] + ': native did not stop at changed child target')
        if core:
            require(native_result['ready'] == 0,
                    case['name'] + ': changed child return was marked ready')
    elif core:
        oracle_require(oracle['stop_kind'] == 'core-boundary' and
                       oracle['continuation'] == PARENT_RET,
                       case['name'] + ': core boundary differs')
        require(native_result['ready'] == 1 and
                native_result['continuation'] == PARENT_RET,
                case['name'] + ': normal core boundary differs')
        oracle_require(oracle['state']['sp'] == initial_regs['sp'],
                       case['name'] + ': normal core left a live save word')
    else:
        oracle_require(oracle['stop_kind'] == 'outer-return',
                       case['name'] + ': adapter did not execute outer near RET')
        oracle_require(oracle['state']['sp'] ==
                       ((initial_regs['sp'] + 2) & 0xFFFF),
                       case['name'] + ': actual outer RET did not consume its word')
    return oracle['sites'], oracle['edges'], len(native_result['events']), oracle


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-stroke.md',
        'src/entity_graphics.asm', 'src/program.asm', 'assets/vgalemmi.exe', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json',
        'c/entity_stroke.c', 'c/entity_stroke.h', 'c/entity_pixel.c',
        'c/entity_pixel.h', 'c/special_blit.h', 'c/lemmings_sym.h', 'c/regs.h',
        'tests/entity_stroke.py', 'tests/entity_pixel.py',
        'tests/entity_pixel_bus.py', 'tests/minimap_vga.py', 'tests/dat_io_c.py',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/bounded_process.py', 'tools/unpack.py', 'tools/common.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    paths_before = input_hashes()
    oracle_require(sha(pixel.ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(PARENT_CODE) == 157 and len(PARENT_INS) == 67 and
                   len(CHILD_CODE) == 50 and len(CHILD_INS) == 22,
                   'Parent/child byte or instruction accounting changed')
    oracle_require(IMAGE[0xEF0C:0xEF14] == MASKS,
                   'Pinned DS:547C pixel-mask table bytes changed')

    rows, coverage, edges, total_events = [], set(), set(), 0
    baseline = Native(directory)
    specs = cases()
    by_name = {case['name']: case for case in specs}
    for case in specs:
        observed_sites, observed_edges = set(), set()
        event_count = 0
        for core in (True, False):
            sites, branch_edges, count, original = compare_case(
                baseline, case, core=core)
            observed_sites.update(sites)
            observed_edges.update(branch_edges)
            event_count += count
            if case.get('mutate') == 'child-return':
                oracle_require(original['stop_kind'] == 'changed-child-return',
                               'Provider did not alter the actual child return')
        coverage.update(observed_sites)
        edges.update(observed_edges)
        total_events += event_count
        rows.append(dict(name=case['name'], bus_events=event_count,
                         executed_instruction_addresses=sorted(observed_sites),
                         branch_edges=sorted(observed_edges),
                         core_and_adapter=True,
                         provider_mutation=case.get('mutate'),
                         vga_state=True))
        gc.collect()

    oracle_require(coverage == set(INS),
                   'Integrated parent/child original site coverage differs')
    oracle_require(edges == EXPECTED_EDGES,
                   f'Integrated branch edges differ: {sorted(edges)}')

    mutation_specs = (
        (1, 'marker-negative', True, 'negative-marker adjustment'),
        (2, 'provider-changes-live-saved-coordinates', True,
         'live saved-coordinate words'),
        (3, 'df-set', True, 'DF-sensitive STOSB cursor'),
        (4, 'provider-changes-child-return', True,
         'changed child RET continuation'),
        (5, 'vga-write-mode-one', True, 'Sequencer map-mask restore'),
    )
    mutations = []
    for number, name, core, label in mutation_specs:
        mutant = Native(directory, number)
        try:
            compare_case(mutant, by_name[name], core=core)
        except Mismatch as error:
            mutations.append(dict(mutation=number, name=label, case=name,
                                  mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'STROKE_MUTATION={number} survived {name}')
        gc.collect()

    hashes_after = input_hashes()
    oracle_require(hashes_after == paths_before,
                   'Entity stroke source inputs changed during bounded campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), mutation_count=len(mutations), mutations=mutations,
        cases=rows, translated_code_bytes=len(PARENT_CODE),
        native_code_ranges=[[PARENT_ENTRY, PARENT_END]],
        integrated_child_ranges=[[CHILD_ENTRY, CHILD_END]],
        routine_bytes=PARENT_CODE.hex(),
        executed_instruction_addresses=sorted(coverage),
        instruction_sites=sorted(coverage), instruction_site_count=len(coverage),
        branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=sorted(edges), total_bus_events=total_events,
        domains=[
            '5F0F parent core and register adapter with composed 5DC6 child',
            'both record-marker JNS edges, both child row-sign JNS edges, '
            'both mask-zero JZ edges and LOOP back/fallthrough edges',
            'live DS record, live SS save/call/RET frames and provider mutations',
            'full RAM, returned registers, defined flags, ordered RAM/OUT events',
            'independent planar VGA planes/latches and incoming read/write modes',
            'DF-dependent STOSB, wrapped coordinates/stack and VGA SS mirrors',
        ], limits=dict(worker_seconds=180, windows_process_mib=384,
                       original_instruction_hook_limit=MAX_INSTRUCTIONS,
                       native_callback_events=MAX_EVENTS,
                       callback_budget_exit=GUARD_EXIT,
                       callback_error_exit=CALLBACK_EXIT),
        input_hashes=hashes_after))
    print(f'PASS entity stroke C: {len(rows)} cases, {total_events} bus events, '
          f'{len(coverage)} integrated sites, {len(edges)} branch edges, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-stroke-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory], cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
