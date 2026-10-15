"""Bounded differential checks for the 6141 coordinate-pixel leaf."""
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
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as x


IMAGE, ORACLE = unpack(ASSET.read_bytes())
LOAD = 0x1010
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
ENTRY, RET, END = 0x6141, 0x616F, 0x6170
CODE = IMAGE[ENTRY:END]
TABLE = 0x547C
MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
SIZE = 1 << 20
MASK = SIZE - 1
MAX_EVENTS = 128
MAX_INSTRUCTIONS = 80
GUARD_EXIT, CALLBACK_EXIT = 86, 87
CF, PF, AF, ZF, SF, TF, IF, DF, OF = (
    0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0100, 0x0200, 0x0400, 0x0800)
ARITH = CF | PF | AF | ZF | SF | OF
ALL_DEFINED_FLAGS = 0x0FD7
MUL_FLAGS = (ALL_DEFINED_FLAGS & ~ARITH) | CF | OF
REPORT = BUILD / 'coordinate-pixel-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {instruction.address: instruction
       for instruction in MD.disasm(CODE, ENTRY)}
BRANCHES = {pc for pc, instruction in INS.items()
            if instruction.group(capstone.CS_GRP_JUMP)}
REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp', 'cs', 'ds', 'es', 'ss', 'ip')
REG_ID = {
    'ax': x.UC_X86_REG_AX, 'bx': x.UC_X86_REG_BX,
    'cx': x.UC_X86_REG_CX, 'dx': x.UC_X86_REG_DX,
    'si': x.UC_X86_REG_SI, 'di': x.UC_X86_REG_DI,
    'bp': x.UC_X86_REG_BP, 'sp': x.UC_X86_REG_SP,
    'cs': x.UC_X86_REG_CS, 'ds': x.UC_X86_REG_DS,
    'es': x.UC_X86_REG_ES, 'ss': x.UC_X86_REG_SS,
    'ip': x.UC_X86_REG_IP,
}

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
                 'column_value', 'row_value', 'saved_value', 'flags')]


class CoreResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'row_value', 'column_value', 'restored_value',
                 'destination_offset', 'output_segment', 'stack_offset', 'flags')]


class Mismatch(AssertionError):
    """A completed native result differs from completed original execution."""


class OracleFailure(AssertionError):
    """The pinned original failed to complete its bounded declared call."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


def putword(memory, address, value):
    memory[address & MASK] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def getword(memory, address):
    return memory[address & MASK] | (memory[(address + 1) & MASK] << 8)


def add16_flags(flags, left, right):
    total = left + right
    value = total & 0xFFFF
    status = 0
    if (value & 0xFF).bit_count() % 2 == 0:
        status |= PF
    if value == 0:
        status |= ZF
    if value & 0x8000:
        status |= SF
    if total > 0xFFFF:
        status |= CF
    if (left ^ right ^ value) & 0x10:
        status |= AF
    if (~(left ^ right) & (left ^ value) & 0x8000) != 0:
        status |= OF
    return ((flags & ~ARITH) | status) & 0xFFFF


def cases():
    """Small fixtures target every mask index, wrap rule and live stack seam."""
    specs = []
    for index in range(8):
        specs.append((f'pinned-mask-index-{index}', {
            'x': 0x948 + index, 'y': 0x22 + index,
            'ds': DATA_SEGMENT, 'table_mode': 'pinned'}))
    specs.extend((
        ('negative-row-no-clamp', {'x': 0x1357, 'y': 0x000F}),
        ('zero-row-no-clamp', {'x': 0x0000, 'y': 0x0010}),
        ('wrapped-positive-row', {'x': 0x8007, 'y': 0x8000}),
        ('largest-positive-row', {'x': 0xFFFF, 'y': 0x800F}),
        ('wrapped-negative-row', {'x': 0x3245, 'y': 0x8010}),
        ('negative-row-ffff', {'x': 0xA5D7, 'y': 0xFFFF}),
        ('residual-al-00d0', {'x': 0x2A35, 'y': 0x0011}),
        ('residual-al-00a0', {'x': 0x7123, 'y': 0x0012}),
        ('logical-x-high-bit', {'x': 0xFFFF, 'y': 0x0027}),
        ('destination-offset-wrap', {'x': 0xFFFF, 'y': 0x800F}),
        ('df-clear', {'x': 0x1265, 'y': 0x0023, 'df': False}),
        ('df-set', {'x': 0x1265, 'y': 0x0023, 'df': True}),
        ('stack-sp-zero', {'x': 0x1123, 'y': 0x0040, 'sp': 0x0000}),
        ('stack-sp-one', {'x': 0xA111, 'y': 0x0050, 'sp': 0x0001}),
        ('stack-sp-ffff', {'x': 0x5456, 'y': 0x0070, 'sp': 0xFFFF}),
        ('stack-physical-wrap', {'x': 0x7612, 'y': 0x0032,
                                 'ss': 0xFFFF, 'sp': 0x0011}),
        ('data-physical-wrap', {'x': 0x1356, 'y': 0x0022,
                                'ds': 0xFFFF}),
        ('ds-ss-table-alias', {'x': 0x0003, 'y': 0x0050,
                               'ds': 0x3000, 'ss': 0x3000,
                               'sp': 0x5485, 'dx': 0xA57C}),
        ('provider-table-read-changes-saves', {
            'x': 0xB123, 'y': 0x0040, 'ds': 0x3100, 'ss': 0x5200,
            'sp': 0x8200, 'effect': 'pop-alias'}),
        ('provider-table-read-changes-ret', {
            'x': 0x0002, 'y': 0x0022, 'ds': 0x3200, 'ss': 0x3200,
            'sp': TABLE + 2, 'return_word': 0x3412, 'effect': 'ret-high'}),
        ('vga-ds-live-table', {'x': 0xABC5, 'y': 0x0032,
                               'ds': 0xA000, 'ss': 0x5200, 'vga_ds': True,
                               'table_bytes': bytes.fromhex('11 22 33 44 55 B6 77 88')}),
        ('vga-ss-push-pop-ret', {'x': 0x0041, 'y': 0x0044,
                                 'ds': 0x3300, 'ss': 0xA000,
                                 'sp': 0x8200, 'vga_ss': True,
                                 'return_word': 0xBEEF}),
        ('vga-ds-ss-table-stack', {'x': 0x0000, 'y': 0x0055,
                                  'ds': 0xA000, 'ss': 0xA000,
                                  'sp': TABLE + 6, 'vga_ds': True,
                                  'vga_ss': True, 'dx': 0xC380,
                                  'table_bytes': MASKS}),
    ))
    for index in range(3):
        specs.append((f'seeded-coordinate-{index}', {
            'x': (0xA513 + index * 0x211) & 0xFFFF,
            'y': (0x71E7 + index * 0x37D) & 0xFFFF,
            'ds': 0x3400 + index * 0x109,
            'ss': 0x5400 + index * 0x123,
            'sp': 0x8100 + index * 4,
            'df': bool(index & 1), 'table_mode': 'custom',
            'table_bytes': bytes((index * 37 + i * 29 + 3) & 0xFF
                                 for i in range(8))}))

    rows = []
    for seed, (name, values) in enumerate(specs):
        rows.append(dict(name=name, seed=seed, x=values.get('x', 0x1237),
                         y=values.get('y', 0x0027), ds=values.get('ds', DATA_SEGMENT),
                         ss=values.get('ss', 0x5000), sp=values.get('sp', 0x8200),
                         dx=values.get('dx', 0xA55A ^ (seed * 0x113)),
                         df=values.get('df', bool(seed & 1)),
                         table_mode=values.get('table_mode', 'custom'),
                         table_bytes=values.get('table_bytes', MASKS),
                         return_word=values.get('return_word', 0xE100 | seed),
                         vga_ds=values.get('vga_ds', False),
                         vga_ss=values.get('vga_ss', False),
                         effect=values.get('effect')))
    oracle_require(len(rows) == 34, f'Coordinate-pixel fixture count changed: {len(rows)}')
    return rows


def setup_vga(case, memory, regs):
    if not case['vga_ds'] and not case['vga_ss']:
        return None
    device = MinimapVga(0x6141 + case['seed'], read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[8] = 0xFF
    device.gc[6] = 0x05
    if case['vga_ds']:
        base = physical(regs['ds'], TABLE)
        oracle_require(VGA_BASE <= base < VGA_END,
                       case['name'] + ': DS table is outside VGA aperture')
        offset = base - VGA_BASE
        for n, value in enumerate(case['table_bytes']):
            device.planes[0][(offset + n) & 0xFFFF] = value
    if case['vga_ss']:
        base = physical(regs['ss'], regs['sp'])
        oracle_require(VGA_BASE <= base < VGA_END,
                       case['name'] + ': SS stack is outside VGA aperture')
        offset = base - VGA_BASE
        device.planes[0][offset] = case['return_word'] & 0xFF
        device.planes[0][(offset + 1) & 0xFFFF] = case['return_word'] >> 8
    return device


def prepare(case):
    rng = random.Random(0x6141 + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    regs = {name: rng.randrange(0x10000) for name in REGS}
    regs.update(cs=LOAD, ip=ENTRY, ds=case['ds'], ss=case['ss'],
                es=rng.randrange(0x10000), sp=case['sp'],
                bx=case['y'], cx=case['x'], dx=case['dx'])
    flags = (rng.randrange(0x10000) & ALL_DEFINED_FLAGS) | 2
    flags &= ~TF
    flags = (flags | DF) if case['df'] else (flags & ~DF)
    regs['flags'] = flags

    if case['table_mode'] != 'pinned' or regs['ds'] != DATA_SEGMENT:
        base = physical(regs['ds'], TABLE)
        for n, value in enumerate(case['table_bytes']):
            memory[(base + n) & MASK] = value
    else:
        actual = bytes(memory[physical(regs['ds'], TABLE) + n] for n in range(8))
        oracle_require(actual == MASKS,
                       case['name'] + ': pinned PixelBitMasks bytes changed')

    ret = physical(regs['ss'], regs['sp'])
    putword(memory, ret, case['return_word'])
    device = setup_vga(case, memory, regs)
    return memory, regs, device


def side_effects(case, regs):
    index = regs['cx'] & 7
    trigger = physical(regs['ds'], TABLE + index)
    if case['effect'] == 'pop-alias':
        return [(trigger,
                 ((physical(regs['ss'], (regs['sp'] - 4) & 0xFFFF),
                   bytes.fromhex('DE C0')),
                  (physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF),
                   bytes.fromhex('EF BE'))))]
    if case['effect'] == 'ret-high':
        return [(trigger,
                 ((physical(regs['ss'], (regs['sp'] + 1) & 0xFFFF), b'\xBE'),))]
    return []


def independent(case, initial, regs, effects, *, core):
    """Independent register/stack calculation for ordinary-RAM fixtures."""
    memory = bytearray(initial)
    sp = regs['sp']
    bx, cx, dx = regs['bx'], regs['cx'], regs['dx']
    for value in (bx, cx, dx):
        sp = (sp - 2) & 0xFFFF
        putword(memory, physical(regs['ss'], sp), value)
    row = (bx - 0x10) & 0xFFFF
    product = row * 0xD0
    destination = ((product & 0xFFFF) + (cx >> 3) + 0x4A40) & 0xFFFF
    table_cursor = TABLE + (cx & 7)
    table_address = physical(regs['ds'], table_cursor)
    value = memory[table_address]
    for trigger, stores in effects:
        if trigger == table_address:
            for target, data in stores:
                for n, byte in enumerate(data):
                    memory[(target + n) & MASK] = byte
            break
    # The saved DX is popped before the table read and cannot be changed by it.
    restored_dx = getword(memory, physical(regs['ss'], sp))
    sp = (sp + 2) & 0xFFFF
    restored_cx = getword(memory, physical(regs['ss'], sp))
    sp = (sp + 2) & 0xFFFF
    restored_bx = getword(memory, physical(regs['ss'], sp))
    sp = (sp + 2) & 0xFFFF
    flags = add16_flags(regs['flags'], cx & 7, TABLE)
    state = dict(regs)
    state.update(ax=((value << 8) | (product & 0xFF)),
                 bx=restored_bx, cx=restored_cx, dx=restored_dx,
                 di=destination, es=0xA000, sp=sp, flags=flags, ip=RET)
    if not core:
        state['ip'] = getword(memory, physical(regs['ss'], sp))
        state['sp'] = (sp + 2) & 0xFFFF
    return memory, state


def flags_defined_after(instruction, mask):
    mnemonic = instruction.mnemonic.lower()
    if mnemonic in ('add', 'sub', 'cmp'):
        return ALL_DEFINED_FLAGS
    if mnemonic in ('xor', 'and', 'or', 'test', 'shr', 'shl', 'sar', 'sal'):
        return ALL_DEFINED_FLAGS & ~AF
    if mnemonic == 'mul':
        return (mask & ~ARITH) | CF | OF
    return mask


class NativeBus:
    """Raster callbacks with hard event/error exits for native loops."""
    def __init__(self, memory, device, effects):
        self.memory, self.device = memory, device
        self.effects = list(effects)
        self.used_effects = set()
        self.events = []

        def reserve():
            if len(self.events) >= MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native coordinate-pixel callback budget exhausted')

        def write_effect(target, data):
            for n, byte in enumerate(data):
                p = (target + n) & MASK
                self.memory[p] = byte
                if self.device and VGA_BASE <= p < VGA_END:
                    self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = byte

        def apply_effect(address):
            for n, (trigger, stores) in enumerate(self.effects):
                if n not in self.used_effects and address == trigger:
                    self.used_effects.add(n)
                    for target, data in stores:
                        write_effect(target, data)

        def read(_context, _mem, address, flags):
            try:
                address &= MASK
                reserve()
                value = (self.device.read(self.memory, address, flags)
                         if self.device and VGA_BASE <= address < VGA_END
                         else self.memory[address])
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                apply_effect(address)
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native coordinate-pixel VGA trace exhausted')
                return value
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native read callback failed: {type(error).__name__}: {error}')
                return 0

        def write(_context, _mem, address, value, flags):
            try:
                address &= MASK
                value &= 0xFF
                reserve()
                if self.device and VGA_BASE <= address < VGA_END:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native coordinate-pixel VGA trace exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native write callback failed: {type(error).__name__}: {error}')

        def unexpected_out(_context, _port, _value, _flags):
            worker_exit(CALLBACK_EXIT, 'coordinate-pixel leaf unexpectedly used a port')

        self._read, self._write, self._out = READ(read), WRITE(write), OUT(unexpected_out)
        self.bus = RasterBus(None, self._read, self._write, self._out)


class OriginalRun:
    """Execute only the original 23-site leaf with bounded hooks."""
    def __init__(self, case, memory, regs, device, effects, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.effects, self.core = device, effects, core
        self.events, self.sites, self.edges = [], set(), set()
        self.previous = None
        self.current_flags = regs['flags']
        self.current_flag_mask = ALL_DEFINED_FLAGS
        self.failure = None
        self.stopped = False
        self.ret_target = None
        self.instructions = 0
        self.used_effects = set()
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * SIZE)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(SIZE, initial)
        for name in REGS:
            self.cpu.reg_write(REG_ID[name], regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def mirror(linear, p, value):
            value &= 0xFF
            self.memory[p] = value
            for address in (linear, p, p + SIZE):
                if 0 <= address < 2 * SIZE:
                    self.cpu.mem_write(address, bytes((value,)))

        def apply_effect(address):
            for number, (trigger, stores) in enumerate(self.effects):
                if number in self.used_effects or trigger != address:
                    continue
                self.used_effects.add(number)
                for target, data in stores:
                    for offset, byte in enumerate(data):
                        p = (target + offset) & MASK
                        mirror(p, p, byte)
                        if self.device and VGA_BASE <= p < VGA_END:
                            self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = byte

        def add_event(kind, address, value):
            if len(self.events) >= MAX_EVENTS:
                fail(f'{case["name"]}: original callback event budget exhausted')
                return
            self.events.append((kind, address & MASK, value & 0xFF,
                                self.current_flags & 0xFFFF,
                                self.current_flag_mask))

        def code(uc, _address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous == RET:
                self.ret_target = off
                self.stopped = True
                uc.emu_stop()
                return
            if self.previous in BRANCHES:
                self.edges.add((self.previous, off))
            if self.previous is not None:
                self.current_flag_mask = flags_defined_after(
                    INS[self.previous], self.current_flag_mask)
            if cs != LOAD or off not in INS:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if self.core and off == RET:
                self.stopped = True
                uc.emu_stop()
                return
            if self.instructions >= MAX_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.instructions += 1
            self.sites.add(off)
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.previous = off

        def memory_read(uc, _access, address, size, _value, _user):
            try:
                for offset in range(size):
                    linear = address + offset
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original read escaped mapped memory')
                        return
                    p = linear & MASK
                    value = (self.device.read(self.memory, p, self.current_flags)
                             if self.device and VGA_BASE <= p < VGA_END
                             else self.memory[p])
                    add_event('read', p, value)
                    if self.failure:
                        return
                    mirror(linear, p, value)
                    apply_effect(p)
                    if self.device and len(self.device.trace) > MAX_EVENTS:
                        fail(f'{case["name"]}: original VGA trace cap exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original read provider failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, _access, address, size, value, _user):
            try:
                for offset in range(size):
                    linear = address + offset
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MASK
                    byte = (value >> (8 * offset)) & 0xFF
                    if self.device and VGA_BASE <= p < VGA_END:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    add_event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
                    if self.device and len(self.device.trace) > MAX_EVENTS:
                        fail(f'{case["name"]}: original VGA trace cap exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original write provider failed: '
                     f'{type(error).__name__}: {error}')

        self._callbacks = (code, memory_read, memory_write)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs_in['cs'], ENTRY), 0,
                               count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: bounded Unicorn call failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original did not reach declared boundary')
        oracle_require(len(self.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original callback budget exhausted')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        canonical = bytes(self.memory)
        emulated = bytes(self.cpu.mem_read(0, SIZE))
        oracle_require(canonical == emulated,
                       f'{self.case["name"]}: canonical RAM differs from Unicorn mirror')
        if self.core:
            oracle_require(state['ip'] == RET and state['sp'] == self.regs_in['sp'],
                           f'{self.case["name"]}: core boundary did not restore SP')
        else:
            oracle_require(self.ret_target is not None and
                           state['sp'] == ((self.regs_in['sp'] + 2) & 0xFFFF),
                           f'{self.case["name"]}: adapter did not complete live near RET')
        return dict(memory=canonical, state=state, events=self.events,
                    sites=self.sites, edges=self.edges, device=self.device,
                    ret_target=self.ret_target, used_effects=self.used_effects,
                    instruction_count=self.instructions)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'coordinate-pixel-m{mutation}.dll',
                     mutation, 'coordinate_pixel')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_prepare_coordinate_pixel_core
        self.core.argtypes = [MEM, ctypes.POINTER(Call),
                              ctypes.POINTER(RasterBus)]
        self.core.restype = CoreResult
        self.adapter = self.library.lmn_prepare_coordinate_pixel_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                 ctypes.POINTER(RasterBus)]
        self.adapter.restype = None


def c_buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


def compare_state(case, actual, expected, label, error_type=Mismatch):
    for name in REGS:
        if actual[name] != expected[name]:
            raise error_type(f'{case["name"]} {label} {name} differs: '
                             f'{actual[name]:04X}/{expected[name]:04X}')
    if ((actual['flags'] ^ expected['flags']) & ALL_DEFINED_FLAGS) != 0:
        raise error_type(f'{case["name"]} {label} defined flags differ: '
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
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags, flag_mask = want
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
                f'{case["name"]}: bus event {index} differs: '
                f'{got[:3]!r}/{want[:3]!r}')
        require(((flags ^ exp_flags) & flag_mask) == 0,
                f'{case["name"]}: callback flags differ at event {index}: '
                f'{flags:04X}/{exp_flags:04X}, mask={flag_mask:04X}')


def compare_device(case, actual, expected):
    if expected is None:
        require(actual is None, f'{case["name"]}: unexpected VGA device')
    else:
        require(actual is not None and actual.state() == expected.state(),
                f'{case["name"]}: VGA plane/latch/register state differs')


def run_native(native, case, initial, regs, initial_device, effects, *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    callbacks = NativeBus(memory, device, effects)
    if core:
        call = Call(regs['ds'], regs['ss'], regs['sp'], regs['cx'], regs['bx'],
                    regs['dx'], regs['flags'])
        result = native.core(c_buffer(memory), ctypes.byref(call),
                             ctypes.byref(callbacks.bus))
        state = dict(regs)
        state.update(ax=result.value, bx=result.row_value, cx=result.column_value,
                     dx=result.restored_value, di=result.destination_offset,
                     es=result.output_segment, sp=result.stack_offset,
                     flags=result.flags, ip=RET)
    else:
        live = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
        native.adapter(c_buffer(memory), ctypes.byref(live),
                       ctypes.byref(callbacks.bus))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags
    return dict(memory=bytes(memory), state=state, events=callbacks.events,
                device=device, effects=callbacks.used_effects)


def compare_case(native, case, *, core):
    initial, regs, initial_device = prepare(case)
    effects = side_effects(case, regs)
    original = OriginalRun(case, bytearray(initial), dict(regs),
                          copy.deepcopy(initial_device), effects, core=core).run()
    if initial_device is None:
        model_memory, model_state = independent(case, initial, regs, effects, core=core)
        compare_state(case, original['state'], model_state, 'original/model', OracleFailure)
        compare_memory(case, original['memory'], model_memory,
                       'original/model', OracleFailure)
    actual = run_native(native, case, initial, regs, initial_device, effects, core=core)
    label = 'core' if core else 'adapter'
    compare_state(case, actual['state'], original['state'], label)
    compare_memory(case, actual['memory'], original['memory'], label)
    compare_events(case, actual['events'], original['events'])
    compare_device(case, actual['device'], original['device'])
    oracle_require(set(original['used_effects']) == set(range(len(effects))),
                   case['name'] + ': original provider effect did not fire')
    require(set(actual['effects']) == set(range(len(effects))),
            case['name'] + ': native provider effect did not fire')
    return original


def compare_null_bus(native, case):
    initial, regs, device = prepare(case)
    oracle_require(device is None, 'Null-bus ABI check requires ordinary RAM')
    old_memory, new_memory = bytearray(initial), bytearray(initial)
    call = Call(regs['ds'], regs['ss'], regs['sp'], regs['cx'], regs['bx'],
                regs['dx'], regs['flags'])
    old = native.core(c_buffer(old_memory), ctypes.byref(call), None)
    bus_callbacks = NativeBus(new_memory, None, [])
    new = native.core(c_buffer(new_memory), ctypes.byref(call),
                      ctypes.byref(bus_callbacks.bus))
    require(bytes(old) == bytes(new), 'Null-bus core result ABI differs')
    require(old_memory == new_memory, 'Null-bus core canonical RAM differs')
    old_memory, new_memory = bytearray(initial), bytearray(initial)
    old_regs = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
    new_regs = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
    native.adapter(c_buffer(old_memory), ctypes.byref(old_regs), None)
    bus_callbacks = NativeBus(new_memory, None, [])
    native.adapter(c_buffer(new_memory), ctypes.byref(new_regs),
                   ctypes.byref(bus_callbacks.bus))
    require(bytes(old_regs) == bytes(new_regs), 'Null-bus adapter register ABI differs')
    require(old_memory == new_memory, 'Null-bus adapter canonical RAM differs')


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-pixel.md', 'docs/coordinate-pixel.md',
        'assets/vgalemmi.exe', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'src/program.asm',
        'src/entity_graphics.asm', 'c/coordinate_pixel.c',
        'c/coordinate_pixel.h', 'c/lemmings_sym.h', 'c/regs.h',
        'c/special_blit.h', 'tests/coordinate_pixel.py', 'tests/minimap_vga.py',
        'tests/dat_io_c.py', 'tests/dat_io.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/coverage.py', 'tools/bounded_process.py', 'tools/unpack.py',
        'tools/common.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(CODE) == 47 and len(INS) == 23,
                   'Coordinate-pixel byte/site accounting changed')
    oracle_require(IMAGE[ENTRY:END] == CODE,
                   'Coordinate-pixel bytes differ from pinned image')

    specs = cases()
    baseline = Native(directory)
    coverage, edges, rows = set(), set(), []
    total_events = 0
    for case in specs:
        observed_sites, observed_edges = set(), set()
        case_events = 0
        for core in (True, False):
            original = compare_case(baseline, case, core=core)
            observed_sites.update(original['sites'])
            observed_edges.update(original['edges'])
            case_events += len(original['events'])
        coverage.update(observed_sites)
        edges.update(observed_edges)
        total_events += case_events
        rows.append(dict(name=case['name'], core_and_adapter=True,
                         executed_instruction_addresses=sorted(observed_sites),
                         branch_edges=sorted(observed_edges),
                         bus_events=case_events,
                         vga=bool(case['vga_ds'] or case['vga_ss']),
                         provider_effect=case['effect']))
        gc.collect()

    oracle_require(coverage == set(INS),
                   f'Coordinate-pixel site coverage differs: {sorted(coverage)}')
    oracle_require(not BRANCHES and not edges,
                   f'Unexpected branch accounting: {sorted(edges)}')
    compare_null_bus(baseline, next(case for case in specs
                                    if case['name'] == 'residual-al-00d0'))

    by_name = {case['name']: case for case in specs}
    witnesses = (
        (1, 'negative-row-no-clamp', True, 'do not clamp negative wrapped Y'),
        (2, 'provider-table-read-changes-saves', True, 'live popped BX/CX'),
        (3, 'residual-al-00d0', True, 'preserve low product byte in AL'),
        (4, 'provider-table-read-changes-ret', False, 'adapter reads live RET'),
    )
    mutations = []
    for number, name, core, label in witnesses:
        mutant = Native(directory, number)
        try:
            compare_case(mutant, by_name[name], core=core)
        except Mismatch as error:
            mutations.append(dict(mutation=number, name=label, case=name,
                                  boundary='core' if core else 'adapter',
                                  mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'Coordinate-pixel mutation {number} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after,
                   'Coordinate-pixel inputs changed during bounded campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), mutation_count=len(mutations), mutations=mutations,
        cases=rows, translated_code_bytes=len(CODE),
        native_code_ranges=[[ENTRY, END]], routine_bytes=CODE.hex(),
        executed_instruction_addresses=sorted(coverage),
        instruction_sites=sorted(coverage), instruction_site_count=len(coverage),
        branch_instruction_addresses=sorted(BRANCHES), branch_edges=sorted(edges),
        total_bus_events=total_events, domains=[
            '6141..616F register-input coordinate helper; no record reads and no clamp',
            'BX=Y and CX=X; low-word D0h product, logical X/8 and wrapped DI additions',
            'all eight live DS PixelBitMasks indexes, including changed table contents',
            'PUSH BX/CX/DX and live POP DX/CX/BX through SS with 16-bit SP wrap',
            'provider table reads that update future popped values or the near RET word',
            'optional raster bus for DS/SS VGA backing; no port operation or ES write',
            '20-bit physical word wrap, canonical RAM, register and defined-flag comparison',
            'core boundary before RET and adapter actual near RET consumption'],
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_tree_mib=640,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_budget=MAX_EVENTS,
                    callback_exhaustion_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=after))
    print(f'PASS coordinate pixel: {len(rows)} fixtures at both boundaries, '
          f'{len(CODE)} bytes, {len(coverage)} sites, {len(mutations)} completed '
          f'mutants, {total_events} callback events', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected coordinate-pixel arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='coordinate-pixel-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
