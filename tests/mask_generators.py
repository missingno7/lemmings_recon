"""Bounded differential checks for the 5CDD/5D66 generated-mask leaves."""
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
SIZE = 1 << 20
MASK = SIZE - 1
WORD_ENTRY, WORD_RET, WORD_END = 0x5CDD, 0x5D17, 0x5D18
BYTE_ENTRY, BYTE_RET, BYTE_END = 0x5D66, 0x5D93, 0x5D94
WORD_CODE = IMAGE[WORD_ENTRY:WORD_END]
BYTE_CODE = IMAGE[BYTE_ENTRY:BYTE_END]
MAX_CALLBACK_EVENTS = 65536
MAX_ORIGINAL_INSTRUCTIONS = 65536
GUARD_EXIT, CALLBACK_EXIT = 86, 87
ARITH = 0x08D5
CF, PF, AF, ZF, SF, TF, IF, DF, OF = 0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0100, 0x0200, 0x0400, 0x0800
DEFINED_FLAGS = 0x0FD7 | IF
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
REPORT = BUILD / 'mask-generators-differential.json'
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
WORD_INS = {i.address: i for i in MD.disasm(WORD_CODE, WORD_ENTRY)}
BYTE_INS = {i.address: i for i in MD.disasm(BYTE_CODE, BYTE_ENTRY)}
WORD_BRANCHES = {pc for pc, ins in WORD_INS.items()
                 if ins.group(capstone.CS_GRP_JUMP) or
                 ins.mnemonic.lower().startswith('loop')}
BYTE_BRANCHES = {pc for pc, ins in BYTE_INS.items()
                 if ins.group(capstone.CS_GRP_JUMP) or
                 ins.mnemonic.lower().startswith('loop')}


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
                ('source_segment', 'output_segment', 'stack_segment',
                 'stack_offset', 'source_cursor', 'output_cursor',
                 'column_repetitions', 'row_count', 'shift_state', 'flags')]


class CoreResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'column_repetitions', 'row_count', 'shift_state',
                 'source_cursor', 'output_cursor', 'stack_offset', 'flags')]


class Mismatch(AssertionError):
    """A completed native result differs from completed original execution."""


class OracleFailure(AssertionError):
    """The pinned original failed to complete its declared bounded call."""


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


def putword(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 0xFF
    memory[(p + 1) & MASK] = (value >> 8) & 0xFF


def getword(memory, segment, offset):
    p = physical(segment, offset)
    return memory[p] | (memory[(p + 1) & MASK] << 8)


def cases():
    """Keep counts small while crossing the live segment/save boundaries."""
    word = [
        ('word-known-answer', dict(rows=3, columns=2, source_values=(0xA55A, 0x8001, 0x1234, 0x00FF, 0xC301, 0x5AA5), known=True)),
        ('word-single', dict(rows=1, columns=1, source_values=(0xA55A,))),
        ('word-three-columns', dict(rows=2, columns=3, source_values=(0x10F1, 0x8001, 0xA55A, 0x09C3, 0x55AA, 0xF00D), known=True)),
        ('word-df-clear', dict(rows=2, columns=2, df=False, source_values=(0x8001, 0x55AA, 0x00FF, 0xA55A))),
        ('word-df-set', dict(rows=3, columns=2, df=True, source_values=(0xA55A, 0x8001, 0x1234, 0x00FF, 0xC301, 0x5AA5))),
        ('word-source-offset-wrap', dict(rows=2, columns=1, si=0xFFFE, source_values=(0xA55A, 0x1234))),
        ('word-source-physical-wrap', dict(rows=2, columns=1, ds=0xFFFF, si=0x000F, source_values=(0x8001, 0xC301))),
        ('word-output-offset-wrap', dict(rows=2, columns=1, di=0xFFFE, source_values=(0x8001, 0x1234))),
        ('word-output-physical-wrap', dict(rows=2, columns=1, es=0xFFFF, di=0x000F, source_values=(0xA55A, 0xC301))),
        ('word-output-flags-0080', dict(rows=1, columns=1, di=0x007F, source_values=(0x8001,))),
        ('word-output-flags-0100', dict(rows=1, columns=1, di=0x00FE, source_values=(0xA55A,))),
        ('word-sequential-overlap', dict(rows=3, columns=1, ds=0x6000, es=0x6000, si=0x0100, di=0x0100, source_values=(0xA55A, 0x8001, 0x1234))),
        ('word-provider-read-side-effect', dict(rows=2, columns=1, source_values=(0x1101, 0x2222), effect_next=True)),
        # ES:DI overwrites the outer saved DX high byte. The live POP gives
        # DH=07, so INC DH reaches the terminal value 08 after one pass.
        ('word-live-shift-count-alias', dict(rows=1, columns=1, ss=0x4000, es=0x4000, sp=0x8200, di=0x81FF, source_values=(0x0007,))),
        ('word-return-alias', dict(rows=1, columns=1, ss=0x4000, es=0x4000, sp=0x8200, di=0x8200, source_values=(0xA55A,))),
        ('word-zero-row-provider-count', dict(rows=0, columns=1, ss=0x4000, es=0x4000, sp=0x8200, di=0x81F4, source_values=(0x0000,), finite_zero='row')),
        ('word-zero-column-provider-count', dict(rows=1, columns=0, ss=0x4000, es=0x4000, sp=0x8200, di=0x81F8, source_values=(0x0000,), finite_zero='column')),
        ('word-stack-offset-wrap', dict(rows=1, columns=1, ss=0x4100, sp=0x0000, source_values=(0x3141,))),
        ('word-stack-physical-wrap', dict(rows=1, columns=1, ss=0xFFFF, sp=0x0011, source_values=(0xC301,))),
        ('word-provider-vga-source-destination', dict(rows=2, columns=1, ds=0xA000, es=0xA000, si=0x1200, di=0x3200, vga=True, source_values=(0xA55A, 0x8001))),
        ('word-vga-stack-source-destination', dict(rows=1, columns=1, ds=0xA000, es=0xA000, ss=0xA000, si=0x1400, di=0x3400, sp=0x8200, vga=True, source_values=(0x5AA5,))),
        ('word-seeded-state-0', dict(rows=2, columns=2, df=False, source_values=(0x0275, 0xD083, 0x5A31, 0x8877))),
        ('word-seeded-state-1', dict(rows=2, columns=1, df=True, source_values=(0xABCD, 0x8301))),
        ('word-seeded-state-2', dict(rows=1, columns=3, df=False, source_values=(0x8000, 0x0001, 0x7E91))),
    ]
    byte = [
        ('byte-known-answer', dict(rows=3, columns=2, source_values=(0xA5, 0x80, 0x12, 0xFF, 0xC3, 0x5A), known=True)),
        ('byte-single', dict(rows=1, columns=1, source_values=(0xA5,))),
        ('byte-three-columns', dict(rows=2, columns=3, source_values=(0xF1, 0x81, 0x5A, 0xC3, 0xAA, 0x0D), known=True)),
        ('byte-df-clear', dict(rows=2, columns=2, df=False, source_values=(0x80, 0x55, 0xFF, 0xA5))),
        ('byte-df-set', dict(rows=3, columns=2, df=True, source_values=(0xA5, 0x80, 0x12, 0xFF, 0xC3, 0x5A))),
        ('byte-source-offset-wrap', dict(rows=2, columns=1, si=0xFFFF, source_values=(0xA5, 0x34))),
        ('byte-source-physical-wrap', dict(rows=2, columns=1, ds=0xFFFF, si=0x000F, source_values=(0x80, 0xC3))),
        ('byte-output-offset-wrap', dict(rows=2, columns=1, di=0xFFFE, source_values=(0x81, 0x34))),
        ('byte-output-physical-wrap', dict(rows=2, columns=1, es=0xFFFF, di=0x000F, source_values=(0xA5, 0xC3))),
        ('byte-sequential-overlap', dict(rows=3, columns=1, ds=0x6000, es=0x6000, si=0x0100, di=0x0100, source_values=(0xA5, 0x80, 0x12))),
        ('byte-provider-read-side-effect', dict(rows=2, columns=1, source_values=(0x11, 0x22), effect_next=True)),
        # With DF set, STOSW's first byte reaches saved DH at SP-1. LODSB
        # supplies seven, so the live POP makes INC DH terminate after pass 1.
        ('byte-live-shift-count-alias', dict(rows=1, columns=1, df=True, ss=0x4000, es=0x4000, sp=0x8200, di=0x81FF, source_values=(0x07,))),
        ('byte-return-alias', dict(rows=1, columns=1, ss=0x4000, es=0x4000, sp=0x8200, di=0x8200, source_values=(0xA5,))),
        ('byte-stack-offset-wrap', dict(rows=1, columns=1, ss=0x4100, sp=0x0000, source_values=(0x41,))),
        ('byte-stack-physical-wrap', dict(rows=1, columns=1, ss=0xFFFF, sp=0x0011, source_values=(0xC3,))),
        ('byte-provider-vga-source-destination', dict(rows=2, columns=1, ds=0xA000, es=0xA000, si=0x1200, di=0x3200, vga=True, source_values=(0xA5, 0x80))),
        ('byte-vga-stack-source-destination', dict(rows=1, columns=1, ds=0xA000, es=0xA000, ss=0xA000, si=0x1400, di=0x3400, sp=0x8200, vga=True, source_values=(0x5A,))),
        ('byte-seeded-state-0', dict(rows=2, columns=2, df=False, source_values=(0x75, 0x83, 0x31, 0x77))),
        ('byte-seeded-state-1', dict(rows=2, columns=1, df=True, source_values=(0xCD, 0x83))),
        ('byte-seeded-state-2', dict(rows=1, columns=3, df=False, source_values=(0x80, 0x01, 0x91))),
    ]
    rows = []
    for index, (name, settings) in enumerate(word + byte):
        kind = 'word' if name.startswith('word-') else 'byte'
        rows.append(dict(name=name, kind=kind, seed=index,
                         ds=settings.get('ds', 0x3000), es=settings.get('es', 0x5000),
                         ss=settings.get('ss', 0x4000), sp=settings.get('sp', 0x8200),
                         si=settings.get('si', 0x0100), di=settings.get('di', 0x4000),
                         rows=settings['rows'], columns=settings['columns'],
                         df=settings.get('df', False),
                         source_values=settings['source_values'],
                         effect_next=settings.get('effect_next', False),
                         finite_zero=settings.get('finite_zero'),
                         vga=settings.get('vga', False),
                         known=settings.get('known', False)))
    return rows


def put_source_byte(memory, device, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[device.gc[4] & 3][address - VGA_BASE] = value & 0xFF


def prepare(case):
    rng = random.Random(0x5CDD + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    device = MinimapVga(0x5D66 + case['seed']) if case['vga'] else None
    if device is not None:
        device.seq[2] = 0x0F
        device.gc[0] = 0
        device.gc[1] = 0
        device.gc[3] = 0
        device.gc[5] = 0
        device.gc[8] = 0xFF
        device.gc[4] = 0
        device.gc[6] = 0x05

    regs = {name: rng.randrange(0x10000) for name in REGS}
    entry = WORD_ENTRY if case['kind'] == 'word' else BYTE_ENTRY
    regs.update(cs=LOAD, ip=entry, ds=case['ds'], es=case['es'],
                ss=case['ss'], sp=case['sp'], si=case['si'], di=case['di'],
                bx=((rng.randrange(0x100) << 8) | case['columns']),
                cx=case['rows'])
    regs['dx'] = rng.randrange(0x10000)
    flags = (rng.randrange(0x10000) & 0x0FD7) | 2
    flags &= ~TF
    flags = (flags | DF) if case['df'] else (flags & ~DF)
    regs['flags'] = flags

    return_word = 0xE100 | (case['seed'] & 0xFF)
    putword(memory, regs['ss'], regs['sp'], return_word)
    if device is not None:
        stack = physical(regs['ss'], regs['sp'])
        if VGA_BASE <= stack < VGA_END:
            device.planes[device.gc[4] & 3][stack - VGA_BASE] = return_word & 0xFF
            device.planes[device.gc[4] & 3][(stack + 1 - VGA_BASE) & 0xFFFF] = (return_word >> 8) & 0xFF

    unit = 2 if case['kind'] == 'word' else 1
    direction = -1 if case['df'] else 1
    cursor = regs['si']
    values = case['source_values']
    needed = max(1, case['rows'] * case['columns'])
    oracle_require(len(values) >= needed,
                   case['name'] + ': fixture source list is too short')
    for index in range(needed):
        value = values[index]
        if case['kind'] == 'word':
            put_source_byte(memory, device, regs['ds'], cursor, value)
            put_source_byte(memory, device, regs['ds'], (cursor + 1) & 0xFFFF, value >> 8)
        else:
            put_source_byte(memory, device, regs['ds'], cursor, value)
        cursor = (cursor + direction * unit) & 0xFFFF

    effect = None
    if case['effect_next']:
        next_cursor = (regs['si'] + direction * unit) & 0xFFFF
        target = physical(regs['ds'], next_cursor)
        data = (bytes((0x5A, 0xC3)) if case['kind'] == 'word'
                else bytes((0xD6,)))
        effect = (physical(regs['ds'], regs['si']), target, data)
    write_effect = None
    if case['finite_zero'] == 'row':
        write_effect = (physical(regs['es'], regs['di']), (
            (physical(regs['ss'], (regs['sp'] - 12) & 0xFFFF), b'\x01\x00'),
            (physical(regs['ss'], (regs['sp'] - 1) & 0xFFFF), b'\x07')))
    elif case['finite_zero'] == 'column':
        write_effect = (physical(regs['es'], regs['di']), (
            (physical(regs['ss'], (regs['sp'] - 8) & 0xFFFF), b'\x01'),
            (physical(regs['ss'], (regs['sp'] - 1) & 0xFFFF), b'\x07')))
    return memory, regs, device, effect, write_effect


def flag_defined_after(instruction, mask):
    mnemonic = instruction.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return DEFINED_FLAGS & ~AF
    if mnemonic in ('add', 'sub', 'cmp', 'neg', 'inc', 'dec'):
        return DEFINED_FLAGS
    if mnemonic in ('shr', 'shl', 'sar', 'sal'):
        return DEFINED_FLAGS & ~AF
    if mnemonic in ('rcr', 'rcl', 'ror', 'rol'):
        return (mask & ~(AF | CF | OF)) | CF | OF
    return mask


def instructions_for(kind):
    return WORD_INS if kind == 'word' else BYTE_INS


def entry_for(kind):
    return WORD_ENTRY if kind == 'word' else BYTE_ENTRY


def ret_for(kind):
    return WORD_RET if kind == 'word' else BYTE_RET


class NativeBus:
    """Bound every native callback and preserve provider read side effects."""
    def __init__(self, memory, device, effect, write_effect):
        self.memory, self.device, self.effect = memory, device, effect
        self.write_effect = write_effect
        self.used_effect = False
        self.used_write_effect = False
        self.events = []
        self.access_count = 0

        def reserve():
            if self.access_count >= MAX_CALLBACK_EVENTS:
                worker_exit(GUARD_EXIT, 'native mask-generator callback budget exhausted')
            self.access_count += 1

        def apply_effect(address):
            if self.effect and not self.used_effect and address == self.effect[0]:
                self.used_effect = True
                _trigger, target, data = self.effect
                for offset, value in enumerate(data):
                    p = (target + offset) & MASK
                    self.memory[p] = value
                    if self.device and VGA_BASE <= p < VGA_END:
                        self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = value

        def apply_write_effect(address):
            if self.write_effect and address == self.write_effect[0]:
                self.used_write_effect = True
                _trigger, stores = self.write_effect
                for target, data in stores:
                    for offset, value in enumerate(data):
                        p = (target + offset) & MASK
                        self.memory[p] = value
                        if self.device and VGA_BASE <= p < VGA_END:
                            self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = value

        def read(_context, _mem, address, flags):
            try:
                address &= MASK
                reserve()
                value = (self.device.read(self.memory, address, flags)
                         if self.device and VGA_BASE <= address < VGA_END
                         else self.memory[address])
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                apply_effect(address)
                if self.device and len(self.device.trace) > MAX_CALLBACK_EVENTS:
                    worker_exit(GUARD_EXIT, 'native mask-generator VGA trace cap exhausted')
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
                if self.device:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                apply_write_effect(address)
                if self.device and len(self.device.trace) > MAX_CALLBACK_EVENTS:
                    worker_exit(GUARD_EXIT, 'native mask-generator VGA trace cap exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native write callback failed: {type(error).__name__}: {error}')

        def unexpected_out(_context, _port, _value, _flags):
            worker_exit(CALLBACK_EXIT, 'mask generator unexpectedly used a port callback')

        self._read, self._write = READ(read), WRITE(write)
        self._out = OUT(unexpected_out)
        self.bus = RasterBus(None, self._read, self._write, self._out)


class OriginalRun:
    """Run only the identified generator body with a hard instruction limit."""
    def __init__(self, case, memory, regs, device, effect, write_effect, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.effect, self.write_effect, self.core = device, effect, write_effect, core
        self.events, self.sites, self.edges = [], set(), set()
        self.previous = None
        self.current_flags = regs['flags']
        self.current_flag_mask = DEFINED_FLAGS
        self.instructions = 0
        self.failure = None
        self.stopped = False
        self.ret_target = None
        self.used_effect = False
        self.used_write_effect = False
        self.pending_write_effect = None
        self.ins = instructions_for(case['kind'])
        self.branches = WORD_BRANCHES if case['kind'] == 'word' else BYTE_BRANCHES
        self.entry, self.ret = entry_for(case['kind']), ret_for(case['kind'])
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
            byte = bytes((value & 0xFF,))
            for address in (linear, p, p + SIZE):
                if 0 <= address < 2 * SIZE:
                    self.cpu.mem_write(address, byte)
            self.memory[p] = value & 0xFF

        def apply_effect(address):
            if self.effect and not self.used_effect and address == self.effect[0]:
                self.used_effect = True
                _trigger, target, data = self.effect
                for offset, value in enumerate(data):
                    p = (target + offset) & MASK
                    mirror(p, p, value)
                    if self.device and VGA_BASE <= p < VGA_END:
                        self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = value

        def apply_write_effect(address):
            if self.write_effect and address == self.write_effect[0]:
                self.used_write_effect = True
                self.pending_write_effect = self.write_effect[1]

        def flush_write_effect():
            if self.pending_write_effect is None:
                return
            for target, data in self.pending_write_effect:
                for offset, value in enumerate(data):
                    p = (target + offset) & MASK
                    mirror(p, p, value)
                    if self.device and VGA_BASE <= p < VGA_END:
                        self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = value
            self.pending_write_effect = None

        def add_event(kind, address, value):
            if len(self.events) >= MAX_CALLBACK_EVENTS:
                fail(f'{case["name"]}: original callback event budget exhausted')
                return
            self.events.append((kind, address & MASK, value & 0xFF,
                                self.current_flags & 0xFFFF,
                                self.current_flag_mask))

        def code(uc, _address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous == self.ret:
                self.ret_target = off
                self.stopped = True
                uc.emu_stop()
                return
            flush_write_effect()
            if self.previous in self.branches:
                self.edges.add((self.previous, off))
            if self.previous is not None:
                self.current_flag_mask = flag_defined_after(
                    self.ins[self.previous], self.current_flag_mask)
            if cs != LOAD or off not in self.ins:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if self.core and off == self.ret:
                self.stopped = True
                uc.emu_stop()
                return
            if self.instructions >= MAX_ORIGINAL_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.instructions += 1
            self.sites.add(off)
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.previous = off

        def memory_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
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
            except BaseException as error:
                fail(f'{case["name"]}: original read callback failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if self.device:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    add_event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
                    apply_write_effect(p)
            except BaseException as error:
                fail(f'{case["name"]}: original write callback failed: '
                     f'{type(error).__name__}: {error}')

        self._callbacks = (code, memory_read, memory_write)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)

    def run(self):
        try:
            self.cpu.emu_start(physical(LOAD, self.entry), 0,
                               count=MAX_ORIGINAL_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: bounded Unicorn run failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original did not reach bounded boundary')
        oracle_require(len(self.events) <= MAX_CALLBACK_EVENTS,
                       f'{self.case["name"]}: original event budget exhausted')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        canonical = bytes(self.memory)
        emulated = bytes(self.cpu.mem_read(0, SIZE))
        oracle_require(canonical == emulated,
                       f'{self.case["name"]}: callback and Unicorn canonical RAM diverged')
        result = dict(memory=canonical, state=state,
                      events=self.events, sites=self.sites, edges=self.edges,
                      device=self.device, ret_target=self.ret_target,
                      instruction_count=self.instructions,
                      read_effect=self.used_effect,
                      write_effect=self.used_write_effect)
        return result


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'mask-generators-m{mutation}.dll',
                     mutation, 'mask_generators')
        self.library = ctypes.CDLL(str(path))
        self.word_core = self.library.lmn_generate_word_mask_shifts_core
        self.word_core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
        self.word_core.restype = CoreResult
        self.byte_core = self.library.lmn_generate_byte_mask_shifts_core
        self.byte_core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
        self.byte_core.restype = CoreResult
        self.word_adapter = self.library.lmn_generate_word_mask_shifts_adapter
        self.word_adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
        self.word_adapter.restype = None
        self.byte_adapter = self.library.lmn_generate_byte_mask_shifts_adapter
        self.byte_adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
        self.byte_adapter.restype = None


def c_buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


def compare_state(case, actual, expected, label, flag_mask=DEFINED_FLAGS,
                  error_type=Mismatch):
    for name in REGS:
        if actual[name] != expected[name]:
            raise error_type(f'{case["name"]} {label} {name} differs: '
                             f'{actual[name]:04X}/{expected[name]:04X}')
    if ((actual['flags'] ^ expected['flags']) & flag_mask) != 0:
        raise error_type(f'{case["name"]} {label} flags differ: '
                         f'{actual["flags"]:04X}/{expected["flags"]:04X} '
                         f'mask={flag_mask:04X}')


def compare_memory(case, actual, expected, label, error_type=Mismatch):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    raise error_type(f'{case["name"]} {label} RAM differs at {mismatch:05X}: '
                     f'{actual[mismatch]:02X}/{expected[mismatch]:02X}')


def compare_events(case, native_events, original_events):
    require(len(native_events) == len(original_events),
            f'{case["name"]}: callback event count differs '
            f'{len(native_events)}/{len(original_events)}')
    for index, (got, want) in enumerate(zip(native_events, original_events)):
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags, flag_mask = want
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
                f'{case["name"]}: callback event {index} differs '
                f'{got[:3]!r}/{want[:3]!r}')
        require(((flags ^ exp_flags) & flag_mask) == 0,
                f'{case["name"]}: callback flags differ at {index}: '
                f'{flags:04X}/{exp_flags:04X}, mask={flag_mask:04X}')


def compare_device(case, actual, expected):
    if expected is None:
        require(actual is None, f'{case["name"]}: unexpected VGA device')
        return
    require(actual is not None and actual.state() == expected.state(),
            f'{case["name"]}: independent VGA plane/latch state differs')


def run_native(native, case, initial, initial_regs, initial_device, effect,
               write_effect, *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    callbacks = NativeBus(memory, device, effect, write_effect)
    if core:
        call = Call(initial_regs['ds'], initial_regs['es'], initial_regs['ss'],
                    initial_regs['sp'], initial_regs['si'], initial_regs['di'],
                    initial_regs['bx'], initial_regs['cx'], initial_regs['dx'],
                    initial_regs['flags'])
        fn = native.word_core if case['kind'] == 'word' else native.byte_core
        result = fn(c_buffer(memory), ctypes.byref(call), ctypes.byref(callbacks.bus))
        state = dict(initial_regs)
        state.update(ax=result.value, bx=result.column_repetitions,
                     cx=result.row_count, dx=result.shift_state,
                     si=result.source_cursor, di=result.output_cursor,
                     sp=result.stack_offset, flags=result.flags,
                     ip=ret_for(case['kind']))
    else:
        live = Regs(**{name: initial_regs[name] for name in REGS},
                    flags=initial_regs['flags'])
        fn = native.word_adapter if case['kind'] == 'word' else native.byte_adapter
        fn(c_buffer(memory), ctypes.byref(live), ctypes.byref(callbacks.bus))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags
    return dict(memory=bytes(memory), state=state, events=callbacks.events,
                device=device, access_count=callbacks.access_count)


def known_output(case, initial):
    """Independent conceptual MSB-first mask bit chain for disjoint fixtures."""
    is_word = case['kind'] == 'word'
    step = 2 if is_word else 1
    source_step = -step if case['df'] else step
    destination = case['di']
    writes = {}
    for shift in range(8):
        source = case['si']
        for _column in range(case['columns']):
            for _row in range(case['rows']):
                source_address = physical(case['ds'], source)
                if is_word:
                    word = initial[source_address] | (
                        initial[(source_address + 1) & MASK] << 8)
                    mask_word = ((word & 0xFF) << 16) | ((word >> 8) << 8)
                    mask_word >>= shift
                    values = ((mask_word >> 16) & 0xFF,
                              (mask_word >> 8) & 0xFF,
                              mask_word & 0xFF)
                    for value in values:
                        writes[physical(case['es'], destination)] = value
                        destination = (destination + 1) & 0xFFFF
                else:
                    source_byte = initial[source_address]
                    mask_word = (source_byte << 8) >> shift
                    writes[physical(case['es'], destination)] = (mask_word >> 8) & 0xFF
                    writes[(physical(case['es'], destination) + 1) & MASK] = mask_word & 0xFF
                    destination = (destination + (-2 if case['df'] else 2)) & 0xFFFF
                source = (source + source_step) & 0xFFFF
    return writes


def compare_case(native, case, *, core):
    initial, initial_regs, initial_device, effect, write_effect = prepare(case)
    oracle_device = copy.deepcopy(initial_device)
    original = OriginalRun(case, bytearray(initial), dict(initial_regs),
                          oracle_device, effect, write_effect, core=core).run()
    native_result = run_native(native, case, initial, initial_regs,
                               initial_device, effect, write_effect, core=core)
    label = 'core' if core else 'adapter'
    compare_state(case, native_result['state'], original['state'], label)
    compare_memory(case, native_result['memory'], original['memory'], label)
    compare_events(case, native_result['events'], original['events'])
    compare_device(case, native_result['device'], original['device'])
    if core:
        oracle_require(original['state']['ip'] == ret_for(case['kind']) and
                       original['state']['sp'] == initial_regs['sp'],
                       case['name'] + ': core boundary did not preserve RET/SP')
    else:
        oracle_require(original['ret_target'] is not None and
                       original['state']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       case['name'] + ': adapter did not consume live RET')
    if case['known']:
        expected_writes = known_output(case, initial)
        for address, value in expected_writes.items():
            oracle_require(original['memory'][address] == value,
                           f'{case["name"]}: original output differs from independent '
                           f'bit-chain answer at {address:05X}')
    if effect:
        oracle_require(original['read_effect'],
                       case['name'] + ': source provider side effect did not run')
    if write_effect:
        oracle_require(original['write_effect'],
                       case['name'] + ': stack provider write did not run')
    return original


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/generated-graphics.md',
        'assets/vgalemmi.exe', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json',
        'src/game_code_late_after_palette.asm', 'c/mask_generators.c',
        'c/mask_generators.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'c/regs.h', 'tests/mask_generators.py', 'tests/minimap_vga.py',
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
    oracle_require(len(WORD_CODE) == 59 and len(WORD_INS) == 36 and
                   len(BYTE_CODE) == 46 and len(BYTE_INS) == 30,
                   'Mask-generator byte/site accounting changed')
    oracle_require(WORD_CODE[-1] == 0xC3 and BYTE_CODE[-1] == 0xC3,
                   'Generator RET boundary differs')

    baseline = Native(directory)
    specs = cases()
    oracle_require(len(specs) == 44, 'Focused mask-generator fixture count changed')
    coverage = {'word': set(), 'byte': set()}
    edges = {'word': set(), 'byte': set()}
    rows = []
    total_events = 0
    for case in specs:
        observed, branch_edges, event_count = set(), set(), 0
        for core in (True, False):
            original = compare_case(baseline, case, core=core)
            observed.update(original['sites'])
            branch_edges.update(original['edges'])
            event_count += len(original['events'])
        coverage[case['kind']].update(observed)
        edges[case['kind']].update(branch_edges)
        total_events += event_count
        rows.append(dict(name=case['name'], kind=case['kind'], core_and_adapter=True,
                         executed_instruction_addresses=sorted(observed),
                         branch_edges=sorted(branch_edges), callback_events=event_count,
                         provider_read_side_effect=case['effect_next'],
                         provider_write_side_effect=bool(case['finite_zero']),
                         independent_vga=case['vga']))
        gc.collect()

    oracle_require(coverage['word'] == set(WORD_INS),
                   f'Word-generator site coverage differs: {sorted(coverage["word"])}')
    oracle_require(coverage['byte'] == set(BYTE_INS),
                   f'Byte-generator site coverage differs: {sorted(coverage["byte"])}')
    oracle_require(len(edges['word']) == 10,
                   f'Word-generator branch edge coverage differs: {sorted(edges["word"])}')
    oracle_require(len(edges['byte']) == 10,
                   f'Byte-generator branch edge coverage differs: {sorted(edges["byte"])}')
    for kind, branch_sites in (('word', WORD_BRANCHES), ('byte', BYTE_BRANCHES)):
        covered_branches = {source for source, _target in edges[kind]}
        oracle_require(branch_sites <= covered_branches,
                       f'{kind} branch-site coverage differs: '
                       f'{sorted(branch_sites - covered_branches)}')

    by_name = {case['name']: case for case in specs}
    witnesses = (
        (1, 'word-df-set', True, 'word destination honors DF asymmetry'),
        (2, 'byte-df-set', True, 'byte LODS/STOS honor DF'),
        (3, 'word-live-shift-count-alias', True, 'live popped DH controls passes'),
        (4, 'word-known-answer', True, 'three-byte carry spill chain'),
        (5, 'word-return-alias', False, 'adapter reads live RET after stores'),
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
            raise OracleFailure(f'Mask-generator mutation {number} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after,
                   'Mask-generator inputs changed during bounded native campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), mutation_count=len(mutations), mutations=mutations,
        cases=rows, translated_code_bytes=len(WORD_CODE) + len(BYTE_CODE),
        native_code_ranges=[[WORD_ENTRY, WORD_END], [BYTE_ENTRY, BYTE_END]],
        routine_bytes=dict(word=WORD_CODE.hex(), byte=BYTE_CODE.hex()),
        executed_instruction_addresses=sorted(coverage['word'] | coverage['byte']),
        executed_sites_by_generator={
            'word': sorted(coverage['word']), 'byte': sorted(coverage['byte'])},
        instruction_site_count=sum(map(len, coverage.values())),
        branch_edges={kind: sorted(items) for kind, items in edges.items()},
        total_callback_events=total_events, domains=[
            '5CDD word masks and 5D66 byte masks; each core and actual-RET adapter',
            'direct canonical 1 MiB memory with real-mode physical word wrap',
            'live SS save slots, outer popped cursor/count/shift values and RET aliases',
            'source LODS follows DF; 5CDD byte stores advance, 5D66 STOSW follows DF',
            'sequential source/destination overlap and provider read/write side effects',
            'constructed unchained VGA source, stack and destination accesses',
            'finite zero-CX/zero-BL provider witnesses; full wrapped semantics remain uncapped',
            'independent conceptual 24-bit and 16-bit mask-chain known answers'],
        limits=dict(worker_seconds=180, windows_process_mib=384, windows_tree_mib=640,
                    original_instruction_limit=MAX_ORIGINAL_INSTRUCTIONS,
                    native_callback_budget=MAX_CALLBACK_EVENTS,
                    callback_exhaustion_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=after))
    print(f'PASS mask generators: {len(rows)} fixtures at both boundaries, '
          f'{len(WORD_CODE) + len(BYTE_CODE)} bytes, '
          f'{sum(map(len, coverage.values()))} sites, '
          f'{len(mutations)} completed mutants, {total_events} callback events', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected mask-generator arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='mask-generators-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
