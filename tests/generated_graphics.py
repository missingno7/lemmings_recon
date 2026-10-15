"""Bounded composition checks for the 5AC1 generated-graphics producer."""
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
from common import ROOT, BUILD, sha, read_json, write_json
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
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
BUFFER_SELECTOR = 0x1FE8
SOURCE_SELECTOR = 0x1FE4
PARENT_ENTRY, PARENT_RET, PARENT_END = 0x5AC1, 0x5B10, 0x5B11
WORD_ENTRY, WORD_RET, WORD_END = 0x5CDD, 0x5D17, 0x5D18
BYTE_ENTRY, BYTE_RET, BYTE_END = 0x5D66, 0x5D93, 0x5D94
PARENT_CODE = IMAGE[PARENT_ENTRY:PARENT_END]
WORD_CODE = IMAGE[WORD_ENTRY:WORD_END]
BYTE_CODE = IMAGE[BYTE_ENTRY:BYTE_END]
MAX_CALLBACK_EVENTS = 65536
MAX_ORIGINAL_INSTRUCTIONS = 120000
GUARD_EXIT, CALLBACK_EXIT = 86, 87
DEFINED_FLAGS = 0x0FD7
CF, PF, AF, ZF, SF, TF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800
ARITH = CF | PF | AF | ZF | SF | OF
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
REPORT = BUILD / 'generated-graphics-differential.json'
EXPECTED_IMAGE_SHA256 = 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e'
EXPECTED_ASSET_SHA256 = '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_INS = {ins.address: ins for ins in MD.disasm(PARENT_CODE, PARENT_ENTRY)}
WORD_INS = {ins.address: ins for ins in MD.disasm(WORD_CODE, WORD_ENTRY)}
BYTE_INS = {ins.address: ins for ins in MD.disasm(BYTE_CODE, BYTE_ENTRY)}
INS = dict(PARENT_INS)
INS.update(WORD_INS)
INS.update(BYTE_INS)
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EXPECTED_CHILD_RETURNS = {
    0x5AD7: 0x5ADA, 0x5AE9: 0x5AEC,
    0x5AF7: 0x5AFA, 0x5B06: 0x5B09,
}

INPUT_PATHS = (
    'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
    'docs/bottom-up.md', 'docs/generated-graphics.md',
    'src/game_code_late_after_palette.asm',
    'c/generated_graphics.c', 'c/generated_graphics.h',
    'c/mask_generators.c', 'c/mask_generators.h', 'c/lemmings_sym.h',
    'c/regs.h', 'c/special_blit.h', 'tests/generated_graphics.py',
    'tests/mask_generators.py', 'tests/minimap_vga.py',
    'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/bounded_process.py',
    'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py',
    'tools/coverage.py', 'tools/unpack.py', 'metadata/symbols.json',
    'metadata/inputs.json', 'metadata/oracle.json', 'assets/vgalemmi.exe',
)


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
                 'column_repetitions', 'shift_state', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'column_repetitions', 'row_count', 'shift_state',
                 'source_cursor', 'output_cursor', 'source_segment',
                 'output_segment', 'stack_offset', 'flags', 'continuation',
                 'ready_to_return')]


class OracleFailure(AssertionError):
    """The bounded original/provider failed to complete its declared path."""


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


def put_word(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 0xFF
    memory[(p + 1) & MASK] = (value >> 8) & 0xFF


def word_at(memory, segment, offset):
    p = physical(segment, offset)
    return memory[p] | (memory[(p + 1) & MASK] << 8)


def current_hashes():
    return {path: sha((ROOT / path).read_bytes()) for path in INPUT_PATHS}


def cases():
    rows = [
        dict(name='normal-full-output', seed=0x5AC1),
        dict(name='df-set-asymmetric-source-output', seed=0x5AC2, df=True),
        dict(name='provider-changes-live-source-selector', seed=0x5AC3,
             source=0x3100, source_after=0x3200, output=0x4200,
             effect='source-selector'),
        dict(name='source-selector-equals-data-segment', seed=0x5AC4,
             source=DATA_SEGMENT, output=0x4300),
        dict(name='source-output-sequential-overlap', seed=0x5AC5,
             source=0x3100, output=0x3100),
        dict(name='source-physical-wrap', seed=0x5AC6,
             source=0xFFFF, output=0x4400),
        dict(name='output-physical-wrap', seed=0x5AC7,
             source=0x3300, output=0xFFFF),
        dict(name='stack-offset-wrap', seed=0x5AC8,
             source=0x3400, output=0x4500, ss=0x5100, sp=0x0000),
        dict(name='stack-physical-word-wrap', seed=0x5AC9,
             source=0x3500, output=0x4600, ss=0xFFFF, sp=0x0011),
        dict(name='push-ds-overwrites-buffer-selector', seed=0x5ACA,
             ds=DATA_SEGMENT, source=0x3600, output=0x4700,
             ss=DATA_SEGMENT, sp=0x1FEA),
        dict(name='provider-shortens-live-first-group-count', seed=0x5ACB,
             source=0x3700, output=0x4800, effect='first-group-count'),
        dict(name='provider-shortens-live-second-group-count', seed=0x5ACC,
             source=0x3800, output=0x4900, effect='second-group-count'),
        dict(name='provider-changes-child-return', seed=0x5ACD,
             source=0x3900, output=0x4A00, effect='child-return'),
        dict(name='provider-changes-outer-return', seed=0x5ACE,
             source=0x3A00, output=0x4B00, effect='outer-return'),
        dict(name='output-overwrites-saved-count-and-return', seed=0x5ACF,
             source=0x3B00, output_from_ss=True, ss=0x4000, sp=0x0004,
             first_word=0x0001),
        dict(name='source-vga-provider', seed=0x5AD0,
             source=0xA000, output=0x4C00, vga=True),
        dict(name='output-vga-provider', seed=0x5AD1,
             source=0x3C00, output=0xA000, vga=True),
    ]
    oracle_require(len(rows) == 17, 'Generated-graphics fixture count changed')
    return rows


def pattern(seed, length):
    return bytes(((seed * 29 + i * 73 + (i >> 2) * 19 + (i >> 5) * 7) & 0xFF)
                 for i in range(length))


def set_linear_word(memory, device, segment, offset, value):
    p = physical(segment, offset)
    data = (value & 0xFF, (value >> 8) & 0xFF)
    for i, byte in enumerate(data):
        at = (p + i) & MASK
        memory[at] = byte
        if device is not None and VGA_BASE <= at < VGA_END:
            device.planes[device.gc[4] & 3][at - VGA_BASE] = byte


def set_linear_bytes(memory, device, segment, offset, values):
    p = physical(segment, offset)
    for i, byte in enumerate(values):
        at = (p + i) & MASK
        memory[at] = byte
        if device is not None and VGA_BASE <= at < VGA_END:
            device.planes[device.gc[4] & 3][at - VGA_BASE] = byte


def setup_device(case):
    if not case.get('vga'):
        return None
    device = MinimapVga(case['seed'], read_map=0)
    device.seq[2] = 0x0F
    device.seq[4] = 0x06
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[2] = 0
    device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[7] = 0x0F
    device.gc[8] = 0xFF
    return device


def make_effects(case, regs, source_segment):
    """Provider writes are applied after a selected byte has been read."""
    kind = case.get('effect')
    if not kind:
        return []
    ss, sp = regs['ss'], regs['sp']
    if kind == 'source-selector':
        trigger = physical(regs['ds'], BUFFER_SELECTOR + 1)
        target = physical(regs['ds'], SOURCE_SELECTOR)
        value = case['source_after']
        return [(trigger, 1, [(target, bytes((value & 0xFF, value >> 8)))])]
    if kind == 'first-group-count':
        trigger = physical(source_segment, 0)
        target = physical(ss, (sp - 4) & 0xFFFF)
        return [(trigger, 1, [(target, b'\x01\x00')])]
    if kind == 'second-group-count':
        trigger = physical(source_segment, 0x00A0)
        target = physical(ss, (sp - 4) & 0xFFFF)
        return [(trigger, 1, [(target, b'\x01\x00')])]
    if kind == 'child-return':
        trigger = physical(source_segment, 0)
        target = physical(ss, (sp - 6) & 0xFFFF)
        return [(trigger, 1, [(target, b'\x10\x5B')])]
    if kind == 'outer-return':
        trigger = physical(source_segment, 0)
        target = physical(ss, sp)
        return [(trigger, 1, [(target, b'\xEF\xBE')])]
    raise OracleFailure(f'Unknown provider fixture effect: {kind}')


def prepare(case):
    rng = random.Random(0x5AC1 + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    device = setup_device(case)

    ds = case.get('ds', DATA_SEGMENT)
    source_segment = case.get('source', 0x3000)
    output_segment = case.get('output', 0x4000)
    if case.get('output_from_ss'):
        output_segment = case.get('ss', 0x5000)
    put_word(memory, ds, BUFFER_SELECTOR, output_segment)
    put_word(memory, ds, SOURCE_SELECTOR, source_segment)

    regs = {name: rng.randrange(0x10000) for name in REGS}
    regs.update(cs=LOAD, ip=PARENT_ENTRY, ds=ds, es=rng.randrange(0x10000),
                ss=case.get('ss', 0x5000), sp=case.get('sp', 0x8000),
                si=rng.randrange(0x10000), di=rng.randrange(0x10000),
                bx=case.get('bx', (rng.randrange(256) << 8) | 0x006D),
                dx=case.get('dx', rng.randrange(0x10000)))
    flags = (rng.randrange(0x10000) & DEFINED_FLAGS) | 2
    flags &= ~TF
    flags = (flags | DF) if case.get('df', False) else (flags & ~DF)
    regs['flags'] = flags

    return_word = case.get('return_word', (0xE500 | (case['seed'] & 0xFF)))
    put_word(memory, regs['ss'], regs['sp'], return_word)

    source_data = bytearray(pattern(case['seed'], 0x184))
    if 'first_word' in case:
        source_data[0] = case['first_word'] & 0xFF
        source_data[1] = case['first_word'] >> 8
    set_linear_bytes(memory, device, source_segment, 0, source_data)
    if case.get('effect') == 'source-selector':
        alternate = pattern(case['seed'] ^ 0x31A7, 0x184)
        set_linear_bytes(memory, device, case['source_after'], 0, alternate)

    effects = make_effects(case, regs, source_segment)
    meta = dict(source_segment=source_segment, output_segment=output_segment,
                return_word=return_word, source_bytes=bytes(source_data))
    return memory, regs, device, effects, meta


def flags_defined_after(ins, prior_mask):
    mnemonic = ins.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return DEFINED_FLAGS & ~AF
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return DEFINED_FLAGS
    if mnemonic in ('inc', 'dec'):
        return (DEFINED_FLAGS & ~CF) | (prior_mask & CF)
    if mnemonic in ('shr', 'shl', 'sar', 'sal'):
        return DEFINED_FLAGS & ~AF
    if mnemonic in ('rcr', 'rcl', 'ror', 'rol'):
        return (prior_mask & ~(AF | CF | OF)) | CF | OF
    return prior_mask


class NativeBus:
    def __init__(self, memory, device, effects):
        self.memory, self.device = memory, device
        self.effects = list(effects)
        self.used_effects = set()
        self.read_counts = {}
        self.events = []
        self.access_count = 0

        def reserve():
            if self.access_count >= MAX_CALLBACK_EVENTS:
                worker_exit(GUARD_EXIT,
                            'native generated-graphics callback budget exhausted')
            self.access_count += 1

        def apply_effect(address):
            count = self.read_counts.get(address, 0)
            for index, (trigger, after, writes) in enumerate(self.effects):
                if (index not in self.used_effects and address == trigger and
                        count == after):
                    self.used_effects.add(index)
                    for target, data in writes:
                        for n, value in enumerate(data):
                            p = (target + n) & MASK
                            self.memory[p] = value
                            if self.device is not None and VGA_BASE <= p < VGA_END:
                                self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = value

        def read(_context, _mem, address, flags):
            try:
                reserve()
                address &= MASK
                value = (self.device.read(self.memory, address, flags)
                         if self.device is not None and VGA_BASE <= address < VGA_END
                         else self.memory[address])
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                self.read_counts[address] = self.read_counts.get(address, 0) + 1
                apply_effect(address)
                if self.device is not None and len(self.device.trace) > MAX_CALLBACK_EVENTS:
                    worker_exit(GUARD_EXIT, 'native VGA callback budget exhausted')
                return value
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native read callback failed: {type(error).__name__}: {error}')
                return 0

        def write(_context, _mem, address, value, flags):
            try:
                reserve()
                address &= MASK
                value &= 0xFF
                if self.device is not None and VGA_BASE <= address < VGA_END:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                if self.device is not None and len(self.device.trace) > MAX_CALLBACK_EVENTS:
                    worker_exit(GUARD_EXIT, 'native VGA callback budget exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native write callback failed: {type(error).__name__}: {error}')

        def unexpected_out(_context, _port, _value, _flags):
            worker_exit(CALLBACK_EXIT,
                        'generated-graphics parent unexpectedly emitted a port write')

        self._read, self._write = READ(read), WRITE(write)
        self._out = OUT(unexpected_out)
        self.bus = RasterBus(None, self._read, self._write, self._out)


class OriginalRun:
    """Run the intact parent and its two called leaves under hard limits."""
    def __init__(self, case, memory, regs, device, effects, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.effects, self.core = device, effects, core
        self.events, self.sites, self.edges = [], set(), set()
        self.read_counts = {}
        self.used_effects = set()
        self.previous = None
        self.previous_child_return = None
        self.expected_child_return = None
        self.continuation = None
        self.stop_kind = None
        self.failure = None
        self.stopped = False
        self.instruction_count = 0
        self.current_flags = regs['flags']
        self.flag_mask = DEFINED_FLAGS
        self.current_mask = DEFINED_FLAGS
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
            count = self.read_counts.get(address, 0)
            for index, (trigger, after, writes) in enumerate(self.effects):
                if (index not in self.used_effects and address == trigger and
                        count == after):
                    self.used_effects.add(index)
                    for target, data in writes:
                        for n, value in enumerate(data):
                            p = (target + n) & MASK
                            mirror(p, p, value)
                            if self.device is not None and VGA_BASE <= p < VGA_END:
                                self.device.planes[self.device.gc[4] & 3][p - VGA_BASE] = value

        def event(kind, address, value):
            if len(self.events) >= MAX_CALLBACK_EVENTS:
                fail(f'{case["name"]}: original callback event budget exhausted')
                return
            self.events.append((kind, address & MASK, value & 0xFF,
                                self.current_flags & 0xFFFF, self.current_mask))

        def code(uc, _address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous in (WORD_RET, BYTE_RET):
                self.continuation = off
                if off != self.expected_child_return:
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
            if self.previous in BRANCHES:
                self.edges.add((self.previous, off))
            if self.previous is not None:
                self.flag_mask = flags_defined_after(INS[self.previous], self.flag_mask)
            if cs != regs['cs'] or off not in INS:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if self.core and off == PARENT_RET:
                self.continuation = off
                self.stop_kind = 'core-boundary'
                self.stopped = True
                uc.emu_stop()
                return
            if self.instruction_count >= MAX_ORIGINAL_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.instruction_count += 1
            self.sites.add(off)
            if off in EXPECTED_CHILD_RETURNS:
                self.expected_child_return = EXPECTED_CHILD_RETURNS[off]
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.current_mask = self.flag_mask
            self.previous = off

        def memory_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original read escaped mapped RAM')
                        return
                    p = linear & MASK
                    value = (self.device.read(self.memory, p, self.current_flags)
                             if self.device is not None and VGA_BASE <= p < VGA_END
                             else self.memory[p])
                    event('read', p, value)
                    if self.failure:
                        return
                    mirror(linear, p, value)
                    self.read_counts[p] = self.read_counts.get(p, 0) + 1
                    apply_effect(p)
                    if self.device is not None and len(self.device.trace) > MAX_CALLBACK_EVENTS:
                        fail(f'{case["name"]}: original VGA callback budget exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original read callback failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original write escaped mapped RAM')
                        return
                    p = linear & MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if self.device is not None and VGA_BASE <= p < VGA_END:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
                    if self.device is not None and len(self.device.trace) > MAX_CALLBACK_EVENTS:
                        fail(f'{case["name"]}: original VGA callback budget exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original write callback failed: '
                     f'{type(error).__name__}: {error}')

        self._callbacks = (code, memory_read, memory_write)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs_in['cs'], PARENT_ENTRY), 0,
                               count=MAX_ORIGINAL_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original missed bounded continuation')
        oracle_require(self.instruction_count < MAX_ORIGINAL_INSTRUCTIONS,
                       f'{self.case["name"]}: original instruction budget exhausted')
        oracle_require(len(self.events) <= MAX_CALLBACK_EVENTS,
                       f'{self.case["name"]}: original callback event budget exhausted')
        oracle_require(len(self.used_effects) == len(self.effects),
                       f'{self.case["name"]}: provider effect was not exercised')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        return dict(memory=bytes(self.cpu.mem_read(0, SIZE)), state=state,
                    events=self.events, sites=self.sites, edges=self.edges,
                    device=self.device, stop_kind=self.stop_kind,
                    continuation=self.continuation, flag_mask=self.flag_mask,
                    instruction_count=self.instruction_count,
                    access_count=len(self.events),
                    used_effect_count=len(self.used_effects))


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'generated-graphics-m{mutation}.dll',
                     mutation, 'generated_graphics')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_generate_graphics_mask_banks_core
        self.core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_generate_graphics_mask_banks_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
        self.adapter.restype = None


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


def compare_result(case, actual, expected, label):
    fields = ('value', 'column_repetitions', 'row_count', 'shift_state',
              'source_cursor', 'output_cursor', 'source_segment',
              'output_segment', 'stack_offset', 'continuation',
              'ready_to_return')
    for name in fields:
        if getattr(actual, name) != expected[name]:
            raise Mismatch(f'{case["name"]} {label} {name} differs: '
                           f'{getattr(actual, name):04X}/{expected[name]:04X}')
    if ((actual.flags ^ expected['flags']) & expected['flag_mask']) != 0:
        raise Mismatch(f'{case["name"]} {label} flags differ: '
                       f'{actual.flags:04X}/{expected["flags"]:04X} '
                       f'mask={expected["flag_mask"]:04X}')


def compare_memory(case, actual, expected, label, error_type=Mismatch):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    raise error_type(f'{case["name"]} {label} RAM differs at {mismatch:05X}: '
                     f'{actual[mismatch]:02X}/{expected[mismatch]:02X}')


def compare_events(case, actual, expected, label):
    require(len(actual) == len(expected),
            f'{case["name"]} {label} callback count differs: '
            f'{len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        if got[:3] != want[:3]:
            raise Mismatch(f'{case["name"]} {label} callback {index} differs: '
                           f'{got[:3]!r}/{want[:3]!r}')
        if ((got[3] ^ want[3]) & want[4]) != 0:
            raise Mismatch(f'{case["name"]} {label} callback flags differ at '
                           f'{index}: {got[3]:04X}/{want[3]:04X} '
                           f'mask={want[4]:04X}')


def compare_device(case, actual, expected, label):
    if expected is None:
        require(actual is None, f'{case["name"]} {label} unexpected VGA device')
        return
    require(actual is not None and actual.state() == expected.state(),
            f'{case["name"]} {label} VGA planes/latches/registers differ')
    require(actual.trace == expected.trace,
            f'{case["name"]} {label} VGA device trace differs')


def expected_stop(oracle_run):
    state = oracle_run['state']
    return dict(value=state['ax'], column_repetitions=state['bx'],
                row_count=state['cx'], shift_state=state['dx'],
                source_cursor=state['si'], output_cursor=state['di'],
                source_segment=state['ds'], output_segment=state['es'],
                stack_offset=state['sp'], flags=state['flags'],
                flag_mask=oracle_run['flag_mask'],
                continuation=oracle_run['continuation'],
                ready_to_return=int(oracle_run['stop_kind'] == 'core-boundary'))


def native_run(native, case, initial, initial_regs, effects, initial_device, *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    callbacks = NativeBus(memory, device, effects)
    if core:
        call = Call(initial_regs['ds'], initial_regs['ss'], initial_regs['sp'],
                    initial_regs['bx'], initial_regs['dx'], initial_regs['flags'])
        result = native.core(c_buffer(memory), ctypes.byref(call),
                             ctypes.byref(callbacks.bus))
        state = dict(initial_regs)
        state.update(ax=result.value, bx=result.column_repetitions,
                     cx=result.row_count, dx=result.shift_state,
                     si=result.source_cursor, di=result.output_cursor,
                     ds=result.source_segment, es=result.output_segment,
                     sp=result.stack_offset, flags=result.flags,
                     ip=result.continuation)
        result_fields = dict(value=result.value,
                             column_repetitions=result.column_repetitions,
                             row_count=result.row_count, shift_state=result.shift_state,
                             source_cursor=result.source_cursor,
                             output_cursor=result.output_cursor,
                             source_segment=result.source_segment,
                             output_segment=result.output_segment,
                             stack_offset=result.stack_offset, flags=result.flags,
                             continuation=result.continuation,
                             ready_to_return=result.ready_to_return)
    else:
        live = Regs(**{name: initial_regs[name] for name in REGS},
                    flags=initial_regs['flags'])
        native.adapter(c_buffer(memory), ctypes.byref(live),
                       ctypes.byref(callbacks.bus))
        state = {name: getattr(live, name) & 0xFFFF for name in REGS}
        state['flags'] = live.flags & 0xFFFF
        result_fields = None
    return dict(memory=bytes(memory), state=state, events=callbacks.events,
                device=device, access_count=callbacks.access_count,
                used_effect_count=len(callbacks.used_effects),
                result=result_fields)


def independent_full_output(case, initial_memory, meta, oracle_run):
    """Check the disjoint DF-clear bank bytes using the original bit chain."""
    if case['name'] != 'normal-full-output':
        return None
    source_segment = meta['source_segment']
    destination_segment = meta['output_segment']
    source_cursor = 0
    destination = bytearray()
    groups = ((8, 10, 2, 0x14, True),
              (4, 13, 2, 0x1A, True),
              (1, 22, 2, 0x2C, True),
              (10, 8, 1, 0x08, False))
    for calls, rows, source_width, advance, word_generator in groups:
        for _call in range(calls):
            for shift in range(8):
                for row in range(rows):
                    source_at = (source_cursor + row * source_width) & 0xFFFF
                    p = physical(source_segment, source_at)
                    a = initial_memory[p]
                    if word_generator:
                        b = initial_memory[(p + 1) & MASK]
                        conceptual = ((a << 16) | (b << 8)) >> shift
                        destination.extend(((conceptual >> 16) & 0xFF,
                                            (conceptual >> 8) & 0xFF,
                                            conceptual & 0xFF))
                    else:
                        conceptual = (a << 8) >> shift
                        destination.extend(((conceptual >> 8) & 0xFF,
                                            conceptual & 0xFF))
            source_cursor = (source_cursor + advance) & 0xFFFF
    oracle_require(len(destination) == 0x1370,
                   f'{case["name"]}: independent output has wrong span')
    final = oracle_run['memory']
    expected = bytearray(destination)
    start = physical(destination_segment, 0)
    actual = bytes(final[(start + n) & MASK] for n in range(len(expected)))
    oracle_require(actual == expected,
                   f'{case["name"]}: original full output differs from independent '
                   'MSB-first mask model')
    oracle_require(source_cursor == 0x0184,
                   f'{case["name"]}: source cursor did not end at 0184')
    return dict(output_bytes=len(destination), source_end=source_cursor,
                output_sha256=__import__('hashlib').sha256(destination).hexdigest())


def check_completed(native, case, initial, regs, effects, device, *, core, oracle_run):
    oracle_require(oracle_run['used_effect_count'] == len(effects),
                   f'{case["name"]}: oracle provider effect was not exercised')
    actual = native_run(native, case, initial, regs, effects, device, core=core)
    label = 'core' if core else 'adapter'
    require(actual['used_effect_count'] == len(effects),
            f'{case["name"]} {label} native provider effect was not exercised')
    if core:
        compare_result(case, Result(*[actual['result'][field] for field in
                                      ('value', 'column_repetitions', 'row_count',
                                       'shift_state', 'source_cursor', 'output_cursor',
                                       'source_segment', 'output_segment', 'stack_offset',
                                       'flags', 'continuation', 'ready_to_return')]),
                       expected_stop(oracle_run), label)
    compare_state(case, actual['state'], oracle_run['state'], label,
                  flag_mask=oracle_run['flag_mask'])
    compare_memory(case, actual['memory'], oracle_run['memory'], label)
    compare_events(case, actual['events'], oracle_run['events'], label)
    compare_device(case, actual['device'], oracle_run['device'], label)
    return actual


def run_case(native, case):
    initial, regs, device, effects, meta = prepare(case)
    outcomes = {}
    observed_sites, observed_edges = set(), set()
    initial_bytes = bytes(initial)
    for core in (True, False):
        oracle_memory = bytearray(initial_bytes)
        oracle_device = copy.deepcopy(device)
        oracle_runner = OriginalRun(case, oracle_memory, dict(regs), oracle_device,
                                    effects, core=core)
        oracle_run = oracle_runner.run()
        observed_sites.update(oracle_run['sites'])
        observed_edges.update(oracle_run['edges'])
        if core:
            known = independent_full_output(case, initial_bytes, meta, oracle_run)
        actual = check_completed(native, case, initial_bytes, regs, effects,
                                 device, core=core, oracle_run=oracle_run)
        outcomes['core' if core else 'adapter'] = dict(
            event_count=len(oracle_run['events']),
            instruction_count=oracle_run['instruction_count'],
            continuation=oracle_run['continuation'],
            stop_kind=oracle_run['stop_kind'],
            native_access_count=actual['access_count'],
            provider_effects_used=len(effects))
        del oracle_runner, oracle_memory, oracle_device, oracle_run, actual
        gc.collect()
    return dict(case=dict(name=case['name'], effect=case.get('effect'),
                          df=case.get('df', False), vga=case.get('vga', False),
                          source=meta['source_segment'], output=meta['output_segment'],
                          ss=regs['ss'], sp=regs['sp']),
                boundaries=outcomes,
                instruction_addresses=sorted(observed_sites),
                branch_edges=[list(edge) for edge in sorted(observed_edges)],
                independent=known if case['name'] == 'normal-full-output' else None)


def mutation_trials(directory):
    witnesses = (
        (1, 'provider-changes-live-source-selector', True),
        (2, 'provider-shortens-live-first-group-count', True),
        (3, 'provider-changes-child-return', True),
        (4, 'provider-changes-outer-return', False),
        (5, 'normal-full-output', True),
    )
    evidence = []
    all_cases = {case['name']: case for case in cases()}
    for mutation, name, core in witnesses:
        case = all_cases[name]
        initial, regs, device, effects, _meta = prepare(case)
        oracle_memory = bytearray(initial)
        oracle_device = copy.deepcopy(device)
        expected = OriginalRun(case, oracle_memory, dict(regs), oracle_device,
                               effects, core=core).run()
        native = Native(directory, mutation)
        try:
            check_completed(native, case, bytes(initial), regs, effects, device,
                            core=core, oracle_run=expected)
        except Mismatch as error:
            evidence.append(dict(mutation=mutation, case=name, boundary=('core' if core else 'adapter'),
                                 completed=True, mismatch=str(error)))
        else:
            raise AssertionError(f'Mutation {mutation} survived completed witness {name}')
        finally:
            del native
            gc.collect()
    return evidence


def worker(directory):
    before = current_hashes()
    launched = read_json(Path(directory) / 'input-hashes.json')
    oracle_require(before == launched,
                   'Generated-graphics inputs changed between launch and worker')
    oracle_require(sha(IMAGE) == EXPECTED_IMAGE_SHA256 and
                   sha(ASSET.read_bytes()) == EXPECTED_ASSET_SHA256,
                   'Pinned executable or static image hash changed')
    oracle_require(IMAGE[PARENT_ENTRY:PARENT_END] == PARENT_CODE and
                   IMAGE[WORD_ENTRY:WORD_END] == WORD_CODE and
                   IMAGE[BYTE_ENTRY:BYTE_END] == BYTE_CODE,
                   'Generated-graphics original byte slices changed')
    fixtures = cases()
    oracle_require(len(PARENT_INS) == 35 and len(WORD_INS) == 36 and
                   len(BYTE_INS) == 30,
                   'Integrated generated-graphics instruction-site count changed')
    native = Native(directory, 0)
    case_records = []
    all_sites, all_edges = set(), set()
    total_events = 0
    for case in fixtures:
        record = run_case(native, case)
        case_records.append(record)
        all_sites.update(record['instruction_addresses'])
        all_edges.update(tuple(edge) for edge in record['branch_edges'])
        for boundary in ('core', 'adapter'):
            total_events += record['boundaries'][boundary]['event_count']
        # The normal fixture visits every loop arm. The union of both runs is
        # the full integrated dynamic instruction/address evidence.
    del native
    gc.collect()
    expected_edges = {
        (0x5ADE, 0x5AD1), (0x5ADE, 0x5AE0),
        (0x5AF0, 0x5AE3), (0x5AF0, 0x5AF2),
        (0x5B0D, 0x5B00), (0x5B0D, 0x5B0F),
        (0x5CEA, 0x5CF8), (0x5CEA, 0x5CEC),
        (0x5CF6, 0x5CEE), (0x5CF6, 0x5CF8),
        (0x5D05, 0x5CE4), (0x5D05, 0x5D07),
        (0x5D0B, 0x5D0D), (0x5D15, 0x5CDF), (0x5D15, 0x5D17),
        (0x5D73, 0x5D7F), (0x5D73, 0x5D75),
        (0x5D7D, 0x5D77), (0x5D7D, 0x5D7F),
        (0x5D81, 0x5D6D), (0x5D81, 0x5D83),
        (0x5D87, 0x5D89), (0x5D91, 0x5D68), (0x5D91, 0x5D93),
    }
    oracle_require(all_sites == set(INS),
                   f'Original did not execute every integrated instruction site: '
                   f'{sorted(set(INS) - all_sites)}')
    oracle_require(all_edges == expected_edges,
                   f'Original branch edge set changed: missing '
                   f'{sorted(expected_edges - all_edges)}; extra '
                   f'{sorted(all_edges - expected_edges)}')
    mutations = mutation_trials(directory)
    oracle_require(current_hashes() == before,
                   'Generated-graphics inputs changed during bounded campaign')
    report = dict(
        image='main', image_sha256=sha(IMAGE),
        case_count=len(fixtures), boundary_call_count=2 * len(fixtures),
        translated_caller_bytes=len(PARENT_CODE),
        integrated_code_bytes=len(PARENT_CODE)+len(WORD_CODE)+len(BYTE_CODE),
        mutation_count=len(mutations), mutations=mutations, cases=case_records,
        byte_ranges=[[PARENT_ENTRY, PARENT_END], [WORD_ENTRY, WORD_END],
                     [BYTE_ENTRY, BYTE_END]],
        routine_bytes={'parent': PARENT_CODE.hex(), 'word_child': WORD_CODE.hex(),
                       'byte_child': BYTE_CODE.hex()},
        instruction_sites=sorted(INS), instruction_site_count=len(INS),
        executed_instruction_addresses=sorted(all_sites),
        executed_instruction_count=len(all_sites),
        branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=[list(edge) for edge in sorted(all_edges)],
        total_bus_events=total_events,
        domains=[
            '5AC1..5B10 producer composed with 5CDD..5D17 word and 5D66..5D93 byte generators',
            'full DF-clear 1370h output span from source bytes 0000..0183; final source cursor 0184',
            'parent selector reads remain ordered and provider-visible; DS and ES are live selections',
            'actual child CALL/RET frames, child return-word changes and real outer RET target',
            'outer LOOP counts reread from live SS saves after child returns',
            'DF-set source LODSW and byte-child STOSW direction with wrapped SI/DI',
            'source/output overlap, selector/stack aliases and 20-bit physical wrapping',
            'VGA A000 source/output access through the bounded planar provider',
            'whole 1 MiB RAM, full registers, per-instruction defined flags and bounded bus callbacks',
        ],
        limits=dict(worker_seconds=180, windows_process_mib=384, windows_tree_mib=640,
                    callback_exhaustion_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT,
                    original_instruction_hook_limit=MAX_ORIGINAL_INSTRUCTIONS,
                    native_callback_event_limit=MAX_CALLBACK_EVENTS),
        input_hashes=before)
    write_json(REPORT, report)
    print(f'PASS generated graphics C: {len(fixtures)} fixtures, '
          f'{len(INS)} integrated instruction sites, {total_events} bounded bus events, '
          f'{len(mutations)} completed mutants')


def main():
    if len(sys.argv) != 1:
        raise SystemExit('Unexpected generated-graphics arguments')
    REPORT.unlink(missing_ok=True)
    inputs = current_hashes()
    with temporary_build_directory(prefix='generated-graphics-', parent=BUILD) as directory:
        write_json(Path(directory) / 'input-hashes.json', inputs)
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', str(directory)],
                    cwd=ROOT, timeout=180, memory_mib=384, check=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    else:
        main()
