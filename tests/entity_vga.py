"""Bounded differential checks for the 5D94 and 5EBA VGA helpers."""
import ctypes
import copy
import gc
import os
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN,
                     UC_HOOK_INTR)
from unicorn import x86_const as x
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io_c import MEM, Regs
import dat_io as oracle
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated


IMAGE, UNPACK = unpack(ASSET.read_bytes())
LOAD = 0x1010
MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAX_EVENTS = 128
MAX_INSTRUCTIONS = 100
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87
DEFINED_FLAGS = 0x0FD7
AF = 0x0010
EXCHANGE_FLAGS = DEFINED_FLAGS & ~AF
DF = 0x0400
IF = 0x0200

READBACK_ENTRY, READBACK_RET, READBACK_END = 0x5D94, 0x5DC5, 0x5DC6
EXCHANGE_ENTRY, EXCHANGE_RET, EXCHANGE_END = 0x5EBA, 0x5F0E, 0x5F0F
READBACK_CODE = IMAGE[READBACK_ENTRY:READBACK_END]
EXCHANGE_CODE = IMAGE[EXCHANGE_ENTRY:EXCHANGE_END]
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
ROUTINES = {
    'readback': (READBACK_ENTRY, READBACK_RET, READBACK_END, READBACK_CODE),
    'exchange': (EXCHANGE_ENTRY, EXCHANGE_RET, EXCHANGE_END, EXCHANGE_CODE),
}
INSTRUCTIONS = {}
for routine, (entry, _ret, end, code) in ROUTINES.items():
    INSTRUCTIONS[routine] = {ins.address: ins for ins in MD.disasm(code, entry)}
REPORT = BUILD / 'entity-vga-differential.json'
INPUT_PATHS = (
    'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
    'docs/bottom-up.md', 'docs/entity-vga.md',
    'src/game_code_late_after_palette.asm',
    'c/entity_vga.c', 'c/entity_vga.h', 'c/special_blit.h',
    'c/lemmings_sym.h', 'c/regs.h', 'tests/entity_vga.py',
    'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
    'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
    'tools/difftest.py', 'tools/coverage.py', 'tools/unpack.py',
    'metadata/symbols.json', 'metadata/inputs.json', 'metadata/oracle.json',
    'assets/vgalemmi.exe',
)


class ReadbackResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'output_segment', 'port', 'flags')]


class ExchangeResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'packed_bytes', 'third_byte_word', 'destination_offset',
                 'output_segment', 'port', 'flags')]


READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class VerificationFailure(RuntimeError):
    """The pinned oracle, fixture, callback or a finite budget failed."""


class GuardExhaustion(VerificationFailure):
    """An instruction or callback cap was exhausted."""


class NativeMismatch(AssertionError):
    """A completed native/reference comparison differs."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise VerificationFailure(message)


def physical(segment, offset):
    return ((segment << 4) + offset) & MEMORY_MASK


def put_word(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MEMORY_MASK] = (value >> 8) & 0xFF


def get_word(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MEMORY_MASK] << 8)


def current_hashes():
    return {path: sha((ROOT / path).read_bytes()) for path in INPUT_PATHS}


def readback_cases():
    cases = []
    variants = (
        ('setup-incoming-mode0', dict(gc5=0x00, seq_mask=0x05, read_map=0)),
        ('setup-incoming-write-mode1', dict(gc5=0x01, seq_mask=0x0A, read_map=3)),
        ('setup-incoming-readmode1', dict(gc5=0x08, seq_mask=0x01, read_map=2)),
        ('setup-incoming-mode9', dict(gc5=0x09, seq_mask=0x00, read_map=1)),
    )
    for name, options in variants:
        cases.append(dict(name=name, seed=len(cases), **options))
    for offset in (0x0000, 0x0002, 0x0004, 0x0008):
        cases.append(dict(name=f'setup-return-overwritten-at-{offset:04x}',
                          seed=len(cases), sp=offset))
    cases.extend((
        dict(name='setup-ds-equals-ss-row-pitch-wins-mirror', seed=len(cases),
             ds=0x3000, ss=0x3000, sp=0x7100),
        dict(name='setup-physical-word-wrap-at-fffff', seed=len(cases),
             ss=0xFFFF, sp=0x000F),
        dict(name='setup-physical-word-above-a20', seed=len(cases),
             ss=0xFFFF, sp=0xFFFF),
        dict(name='setup-ss-zero-sp-ffff', seed=len(cases), ss=0x0000,
             sp=0xFFFF),
        dict(name='setup-ss-a000-provider', seed=len(cases), ss=0xA000,
             sp=0x0100, gc5=0x01),
        dict(name='setup-ss-a000-return-alias', seed=len(cases), ss=0xA000,
             sp=0x0008, gc5=0x00),
        dict(name='setup-df-if-set-preserved', seed=len(cases), df=True,
             iflag=True),
        dict(name='setup-if-clear-preserved', seed=len(cases), iflag=False),
    ))
    if len(cases) != 16:
        raise AssertionError('Readback fixture count changed')
    return cases


def exchange_cases():
    cases = []
    mode_specs = (
        ('mode0-full-plane-map', 0x00, 0x0F, 0x00, 0x00),
        ('write-mode1-partial-map', 0x01, 0x05, 0x00, 0x00),
        ('readmode1-full-map', 0x08, 0x0F, 0x08, 0x08),
        ('readmode1-write1-zero-map', 0x09, 0x00, 0x03, 0x05),
    )
    mask_sets = (
        (0x00, 0xFF, 0x55), (0x80, 0x01, 0xFE),
        (0xF0, 0x0F, 0x96), (0xAA, 0x55, 0x33),
        (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF),
        (0x7F, 0x81, 0x3C), (0x01, 0x02, 0x04),
    )
    for name, gc5, seq_mask, compare, care in mode_specs:
        cases.append(dict(name=f'exchange-{name}', seed=len(cases), gc5=gc5,
                          seq_mask=seq_mask, compare=compare, care=care,
                          masks=mask_sets[len(cases) % len(mask_sets)],
                          read_map=len(cases) & 3))
    for index, masks in enumerate(mask_sets):
        gc5, seq_mask, compare, care = mode_specs[index % len(mode_specs)][1:]
        cases.append(dict(name=f'exchange-mask-triple-{index}', seed=len(cases),
                          gc5=gc5, seq_mask=seq_mask, compare=compare, care=care,
                          masks=masks, read_map=(index + 1) & 3,
                          di=0x2100 + index * 3))
    cases.extend((
        dict(name='exchange-readmode1-colorcare-plane3', seed=len(cases),
             gc5=0x08, seq_mask=0x0B, read_map=2, compare=0x08, care=0x08,
             masks=(0x96, 0x69, 0xF0)),
        dict(name='exchange-readmode1-colorcare-complement', seed=len(cases),
             gc5=0x08, seq_mask=0x07, read_map=1, compare=0x07, care=0x0F,
             masks=(0x35, 0xCA, 0x5A)),
        dict(name='exchange-readmode1-empty-care', seed=len(cases),
             gc5=0x08, seq_mask=0x0F, read_map=0, compare=0x0F, care=0x00,
             masks=(0x01, 0x80, 0x7E)),
        dict(name='exchange-latch-dependent-write-mode1', seed=len(cases),
             gc5=0x01, seq_mask=0x05, read_map=2, compare=0x03, care=0x0A,
             masks=(0x12, 0xA5, 0x7E)),
        dict(name='exchange-configured-by-readback-5d94', seed=len(cases),
             preconfigure=True, masks=(0x81, 0x3C, 0xE7), di=0x4140),
        dict(name='exchange-df-forward', seed=len(cases), gc5=0x08,
             seq_mask=0x0F, compare=8, care=8, masks=(0xA1, 0xB2, 0xC3),
             df=False, di=0x3300),
        dict(name='exchange-df-backward', seed=len(cases), gc5=0x08,
             seq_mask=0x0F, compare=8, care=8, masks=(0xA1, 0xB2, 0xC3),
             df=True, di=0x3300),
        dict(name='exchange-df-forward-wraps-ffff', seed=len(cases), gc5=0x00,
             seq_mask=0x05, read_map=1, masks=(0x13, 0x27, 0x4B), di=0xFFFE),
        dict(name='exchange-df-backward-wraps-zero', seed=len(cases), gc5=0x09,
             seq_mask=0x0A, compare=8, care=8, masks=(0xE1, 0x72, 0x35),
             df=True, di=0x0000),
        dict(name='exchange-return-word-overwritten-sp-e', seed=len(cases),
             gc5=0x08, seq_mask=0x0F, compare=8, care=8,
             masks=(0x23, 0x47, 0xD9), sp=0x000E, di=0x4000),
        dict(name='exchange-return-word-near-mirror-sp-a', seed=len(cases),
             gc5=0x01, seq_mask=0x03, masks=(0x14, 0x28, 0x5C),
             sp=0x000A, di=0x4010),
        dict(name='exchange-ss-a000-provider-ret', seed=len(cases), ss=0xA000,
             sp=0x0100, gc5=0x08, seq_mask=0x0F, compare=8, care=8,
             masks=(0x91, 0x62, 0x3C), di=0x5100),
        dict(name='exchange-ss-a000-mirror-alias', seed=len(cases), ss=0xA000,
             sp=0x000E, gc5=0x09, seq_mask=0x05, compare=8, care=8,
             masks=(0x56, 0xA9, 0x31), di=0x5100),
        dict(name='exchange-stack-word-wrap-fffff', seed=len(cases), ss=0xFFFF,
             sp=0x000F, gc5=0x00, seq_mask=0x0F,
             masks=(0xD1, 0x6A, 0x3B), di=0x2400),
        dict(name='exchange-stack-word-above-a20', seed=len(cases), ss=0xFFFF,
             sp=0xFFFF, gc5=0x08, seq_mask=0x0A, compare=8, care=8,
             masks=(0xD2, 0x6B, 0x3C), di=0x2410),
        dict(name='exchange-if-clear-sti-witness', seed=len(cases), gc5=0x08,
             seq_mask=0x0F, compare=8, care=8, masks=(0xF1, 0xA2, 0x53),
             iflag=False),
        dict(name='exchange-if-set-sti', seed=len(cases), gc5=0x09,
             seq_mask=0x05, compare=8, care=8, masks=(0xC1, 0xB2, 0xA3),
             iflag=True),
        dict(name='exchange-null-bus-ram-fallback', seed=len(cases),
             null_bus=True, masks=(0x11, 0x55, 0xAA), di=0x62F0),
        dict(name='exchange-null-bus-df-wrap', seed=len(cases), null_bus=True,
             df=True, di=0x0000, masks=(0x80, 0x40, 0x20)),
    ))
    for n in range(3):
        cases.append(dict(name=f'exchange-seeded-device-state-{n}', seed=len(cases),
             gc5=(0x00, 0x01, 0x08, 0x09)[n],
             seq_mask=(0x01, 0x06, 0x0B, 0x0F)[n],
             read_map=(n + 2) & 3, compare=(n * 5) & 0x0F,
             care=(0x03, 0x0C, 0x0F, 0x09)[n],
             gc0=(n * 3) & 0x0F, gc1=(n * 7) & 0x0F,
             gc3=((n & 3) << 3) | ((n * 3) & 7),
             masks=mask_sets[n + 2], di=0x7000 + n * 0x37))
    if len(cases) != 34:
        raise AssertionError(f'Exchange fixture count changed: {len(cases)}')
    return cases


def configure_device(memory, case, seed):
    device = MinimapVga(seed, read_map=case.get('read_map', seed & 3))
    device.seq[2] = case.get('seq_mask', 0x0F) & 0x0F
    device.gc[0] = case.get('gc0', (seed * 3 + 1) & 0x0F)
    device.gc[1] = case.get('gc1', (seed * 5 + 2) & 0x0F)
    device.gc[2] = case.get('compare', (seed * 7 + 3) & 0x0F)
    device.gc[3] = case.get('gc3', (seed * 11 + 5) & 0x1F)
    device.gc[4] = case.get('read_map', seed & 3) & 3
    device.gc[5] = case.get('gc5', 0) & 0x0B
    device.gc[6] = 0x05
    device.gc[7] = case.get('care', (seed * 13 + 1) & 0x0F)
    device.gc[8] = (seed * 17 + 9) & 0xFF
    return device


def prepare(case, routine):
    rng = random.Random(0x5EBA + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    loaded = relocated(IMAGE, UNPACK['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    regs = {name: rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=LOAD, ip=ROUTINES[routine][0],
                ds=case.get('ds', 0x3000), ss=case.get('ss', 0x5000),
                es=rng.randrange(65536), sp=case.get('sp', 0x7000),
                di=case.get('di', 0x4200))
    flags = 2 | (rng.randrange(65536) & (DEFINED_FLAGS & ~0x0100))
    flags &= ~0x0100  # Keep TF clear for bounded instruction tracing.
    if case.get('df', False):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('iflag', bool(case['seed'] & 1)):
        flags |= IF
    else:
        flags &= ~IF
    regs['flags'] = flags
    if routine == 'exchange':
        masks = case.get('masks', (0x81, 0x42, 0x24))
        regs['bx'] = ((masks[0] & 0xFF) << 8) | (masks[1] & 0xFF)
        regs['cx'] = ((case.get('ch', rng.randrange(256)) & 0xFF) << 8) | (masks[2] & 0xFF)
    return_word = case.get('return_word', (0xA700 | case['seed']) & 0xFFFF)
    put_word(memory, regs['ss'], regs['sp'], return_word)

    device = None if case.get('null_bus') else configure_device(
        memory, case, 0xD4A0 + case['seed'])
    if device is not None and regs['ss'] == 0xA000:
        # RET in read mode 1 observes plane 3; seed a distinct provider word.
        device.planes[3][regs['sp']] = case.get('ret_low', 0x6D)
        device.planes[3][(regs['sp'] + 1) & 0xFFFF] = case.get('ret_high', 0xB2)

    if routine == 'exchange' and case.get('preconfigure'):
        setup_regs = dict(regs)
        setup_regs.update(ip=READBACK_ENTRY, ss=0x6000, sp=0x7200)
        put_word(memory, setup_regs['ss'], setup_regs['sp'], 0xE731)
        setup = OriginalRun(case, 'readback', memory, setup_regs, flags,
                            copy.deepcopy(device)).run()
        memory = bytearray(setup['memory'])
        device = setup['device']
        if device is not None:
            device.trace.clear()
        regs['ss'] = case.get('ss', 0x5000)
        regs['sp'] = case.get('sp', 0x7000)
        regs['ip'] = EXCHANGE_ENTRY
        put_word(memory, regs['ss'], regs['sp'], return_word)
    return memory, regs, flags, device


def flags_mask(routine):
    return DEFINED_FLAGS if routine == 'readback' else EXCHANGE_FLAGS


class BusCallbacks:
    """A hard-capped native callback bridge for ordinary RAM and VGA."""
    def __init__(self, memory, device, routine):
        self.memory = memory
        self.device = device
        self.flag_mask = flags_mask(routine)
        self.events = []

        def reserve(label):
            if len(self.events) >= MAX_EVENTS:
                worker_exit(NATIVE_GUARD_EXIT,
                            f'{label}: native VGA callback cap exhausted')

        def read(_context, _memory, address, flags):
            try:
                reserve('read')
                p = address & MEMORY_MASK
                value = (self.device.read(self.memory, p, flags) if self.device and
                         VGA_BASE <= p < VGA_END else self.memory[p])
                self.events.append(('read', p, value & 0xFF, flags & 0xFFFF))
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(NATIVE_GUARD_EXIT,
                                'native MinimapVga trace cap exhausted')
                return value
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                    f'native VGA read callback failed: {type(error).__name__}: {error}')
                return 0

        def write(_context, _memory, address, value, flags):
            try:
                reserve('write')
                p = address & MEMORY_MASK
                value &= 0xFF
                if self.device and VGA_BASE <= p < VGA_END:
                    self.device.write(self.memory, p, value, flags)
                else:
                    self.memory[p] = value
                self.events.append(('write', p, value, flags & 0xFFFF))
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(NATIVE_GUARD_EXIT,
                                'native MinimapVga trace cap exhausted')
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                    f'native VGA write callback failed: {type(error).__name__}: {error}')

        def out(_context, port, value, flags):
            try:
                reserve('out')
                if self.device:
                    self.device.out(port, value, flags)
                self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                                    flags & 0xFFFF))
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(NATIVE_GUARD_EXIT,
                                'native MinimapVga trace cap exhausted')
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                    f'native VGA OUT callback failed: {type(error).__name__}: {error}')

        self._read = READ(read)
        self._write = WRITE(write)
        self._out = OUT(out)
        self.bus = RasterBus(None, self._read, self._write, self._out)


class OriginalRun:
    """Bounded Unicorn execution, stopping at the target of the actual RET."""
    def __init__(self, case, routine, memory, regs, flags, device):
        self.case = case
        self.routine = routine
        self.entry, self.ret, self.end, self.code = ROUTINES[routine]
        self.ins = INSTRUCTIONS[routine]
        self.memory = memory
        self.regs_in = regs
        self.flags_in = flags
        self.device = device
        self.events = []
        self.sites = set()
        self.edges = set()
        self.previous = None
        self.current_flags = flags
        self.failure = None
        self.boundary = None
        self.done = False
        self.ret_target = None
        self.steps = 0
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 1 << 21)
        initial = bytes(memory)
        self.uc.mem_write(0, initial)
        self.uc.mem_write(MEMORY_SIZE, initial)
        for name, register in oracle.REG.items():
            self.uc.reg_write(register, regs[name])
        self.uc.reg_write(x.UC_X86_REG_EFLAGS, flags)

        def fail(uc, message, guard=False):
            if self.failure is None:
                self.failure = (guard, message)
            uc.emu_stop()

        def record(kind, address, value, event_flags):
            if len(self.events) >= MAX_EVENTS:
                fail(self.uc, f'{case["name"]}: original callback cap exhausted', True)
                return
            self.events.append((kind, address, value & 0xFFFF,
                                event_flags & 0xFFFF))

        def mirror(uc, linear, address, value):
            byte = bytes((value & 0xFF,))
            for location in (linear, address, address + MEMORY_SIZE):
                if 0 <= location < (1 << 21):
                    uc.mem_write(location, byte)

        def code(uc, address, _size, _context):
            cs = uc.reg_read(oracle.REG['cs']) & 0xFFFF
            offset = (address - (cs << 4)) & 0xFFFF
            if self.previous == self.ret:
                self.ret_target = offset
                self.done = True
                uc.emu_stop()
                return
            if cs != regs['cs'] or offset not in self.ins:
                fail(uc, f'{case["name"]}: original escaped at {cs:04X}:{offset:04X}')
                return
            if self.steps >= MAX_INSTRUCTIONS:
                fail(uc, f'{case["name"]}: original instruction cap exhausted', True)
                return
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            actual = bytes(uc.mem_read(address + i, 1)[0]
                           for i in range(self.ins[offset].size))
            expected = self.code[offset - self.entry:
                                 offset - self.entry + self.ins[offset].size]
            if actual != expected:
                fail(uc, f'{case["name"]}: executing code bytes changed at {offset:04X}')
                return
            self.sites.add(offset)
            self.steps += 1
            if offset == self.ret:
                self.boundary = dict(
                    memory=bytes(self.memory),
                    registers={name: uc.reg_read(register) & 0xFFFF
                               for name, register in oracle.REG.items()},
                    flags=self.current_flags, event_count=len(self.events),
                    device=copy.deepcopy(self.device))
            self.previous = offset

        def memory_read(uc, _access, linear, size, _value, _context):
            try:
                for index in range(size):
                    location = linear + index
                    if not 0 <= location < (1 << 21):
                        fail(uc, f'{case["name"]}: original read escaped mapped RAM')
                        return
                    address = location & MEMORY_MASK
                    value = (self.device.read(self.memory, address,
                             self.current_flags) if self.device and
                             VGA_BASE <= address < VGA_END else self.memory[address])
                    if self.device and len(self.device.trace) > MAX_EVENTS:
                        fail(uc, f'{case["name"]}: original VGA trace cap exhausted', True)
                        return
                    record('read', address, value, self.current_flags)
                    if self.failure:
                        return
                    mirror(uc, location, address, value)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original read provider failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, _access, linear, size, value, _context):
            try:
                for index in range(size):
                    location = linear + index
                    if not 0 <= location < (1 << 21):
                        fail(uc, f'{case["name"]}: original write escaped mapped RAM')
                        return
                    address = location & MEMORY_MASK
                    byte = (value >> (8 * index)) & 0xFF
                    if self.device and VGA_BASE <= address < VGA_END:
                        self.device.write(self.memory, address, byte,
                                          self.current_flags)
                        if len(self.device.trace) > MAX_EVENTS:
                            fail(uc, f'{case["name"]}: original VGA trace cap exhausted', True)
                            return
                    else:
                        self.memory[address] = byte
                    record('write', address, byte, self.current_flags)
                    if self.failure:
                        return
                    mirror(uc, location, address, byte)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original write provider failed: '
                     f'{type(error).__name__}: {error}')

        def output(uc, port, size, value, _context):
            if size != 2:
                fail(uc, f'{case["name"]}: expected word OUT, got width {size}')
                return
            try:
                if self.device:
                    self.device.out(port, value, self.current_flags)
                    if len(self.device.trace) > MAX_EVENTS:
                        fail(uc, f'{case["name"]}: original VGA trace cap exhausted', True)
                        return
                record('out', port, value, self.current_flags)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original VGA OUT failed: '
                     f'{type(error).__name__}: {error}')

        def interrupt(uc, number, _context):
            fail(uc, f'{case["name"]}: unexpected original INT{number:02X}')

        self._callbacks = (code, memory_read, memory_write, output, interrupt)
        self.uc.hook_add(UC_HOOK_CODE, code)
        self.uc.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, memory_write)
        self.uc.hook_add(UC_HOOK_INSN, output, None, 1, 0, x.UC_X86_INS_OUT)
        self.uc.hook_add(UC_HOOK_INTR, interrupt)

    def run(self):
        try:
            self.uc.emu_start(physical(self.regs_in['cs'], self.entry), 0,
                              count=MAX_INSTRUCTIONS)
        except BaseException as error:
            raise VerificationFailure(
                f'{self.case["name"]}: bounded original execution failed: {error}') from error
        if self.failure:
            guard, message = self.failure
            if guard:
                raise GuardExhaustion(message)
            raise VerificationFailure(message)
        oracle_require(self.done and self.boundary is not None,
                       f'{self.case["name"]}: original did not execute and return '
                       'within the declared instruction cap')
        oracle_require(self.sites == set(self.ins),
                       f'{self.case["name"]}: original site coverage differs for {self.routine}')
        final_memory = bytes(self.uc.mem_read(0, MEMORY_SIZE))
        oracle_require(final_memory == bytes(self.memory),
                       f'{self.case["name"]}: original physical memory mirrors diverged')
        final_registers = {name: self.uc.reg_read(register) & 0xFFFF
                           for name, register in oracle.REG.items()}
        return dict(memory=final_memory, registers=final_registers,
                    flags=self.uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF,
                    events=self.events, sites=self.sites, edges=self.edges,
                    boundary=self.boundary, device=self.device,
                    ret_target=self.ret_target)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-vga-m{mutation}.dll', mutation,
                     'entity_vga')
        self.library = ctypes.CDLL(str(path))
        lib = self.library
        self.readback_core = lib.lmn_configure_entity_readback_core
        self.readback_core.argtypes = [MEM, ctypes.c_uint16, ctypes.c_uint16,
                                       ctypes.c_uint16, ctypes.POINTER(RasterBus)]
        self.readback_core.restype = ReadbackResult
        self.readback_adapter = lib.lmn_configure_entity_readback_adapter
        self.readback_adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                          ctypes.POINTER(RasterBus)]
        self.readback_adapter.restype = None
        self.exchange_core = lib.lmn_exchange_entity_pixel_bytes_core
        self.exchange_core.argtypes = [MEM, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.POINTER(RasterBus)]
        self.exchange_core.restype = ExchangeResult
        self.exchange_adapter = lib.lmn_exchange_entity_pixel_bytes_adapter
        self.exchange_adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                          ctypes.POINTER(RasterBus)]
        self.exchange_adapter.restype = None


def memory_view(memory):
    return (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)


def bus_pointer(callbacks):
    return ctypes.byref(callbacks.bus) if callbacks is not None else None


def device_state(device):
    return None if device is None else device.state()


def compare_events(actual, expected, routine, case_name):
    mask = flags_mask(routine)
    require(len(actual) == len(expected),
            f'{case_name}: {routine} bus-event count differs '
            f'{len(actual)} != {len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{case_name}: {routine} event {index} differs: {got!r}/{want!r}')
        require(((got[3] ^ want[3]) & mask) == 0,
                f'{case_name}: {routine} event {index} flags differ: '
                f'{got[3]:04X}/{want[3]:04X} mask={mask:04X}')


def compare_registers(case, actual, expected, routine, boundary):
    for name in oracle.REG_NAMES:
        if boundary == 'core' and name == 'ip':
            continue
        require(actual[name] == expected[name],
                f'{case["name"]}: {routine} {boundary} {name} differs: '
                f'{actual[name]:04X}/{expected[name]:04X}')
    mask = flags_mask(routine)
    require(((actual['flags'] ^ expected['flags']) & mask) == 0,
            f'{case["name"]}: {routine} {boundary} flags differ: '
            f'{actual["flags"]:04X}/{expected["flags"]:04X} mask={mask:04X}')


def independent_exchange_planes(case, initial_device, flags, regs):
    """Pure plane/latch reference retaining incoming VGA mode and plane mask."""
    planes = [bytearray(plane) for plane in initial_device.planes]
    latches = list(initial_device.latches)
    seq_mask = initial_device.seq[2] & 0x0F
    gc = list(initial_device.gc)
    # The routine changes only these three Graphics Controller registers.
    gc[0], gc[1], gc[3] = 0, 0x0F, 0
    masks = ((regs['bx'] >> 8) & 0xFF, regs['bx'] & 0xFF, regs['cx'] & 0xFF)
    offset = regs['di']
    step = -1 if flags & DF else 1
    samples = []
    for mask_byte in masks:
        latches = [plane[offset] for plane in planes]
        if gc[5] & 0x08:
            compare = gc[2] & 0x0F
            care = gc[7] & 0x0F
            sample = 0xFF
            for plane in range(4):
                if care & (1 << plane):
                    sample &= (latches[plane] if compare & (1 << plane)
                               else (~latches[plane] & 0xFF))
        else:
            sample = latches[gc[4] & 3]
        samples.append(sample)
        gc[8] = mask_byte
        write_mode = gc[5] & 3
        if write_mode == 1:
            for plane in range(4):
                if seq_mask & (1 << plane):
                    planes[plane][offset] = latches[plane]
        elif write_mode == 0:
            for plane in range(4):
                if not (seq_mask & (1 << plane)):
                    continue
                source = 0xFF if gc[0] & (1 << plane) else 0
                if not (gc[1] & (1 << plane)):
                    source = mask_byte
                planes[plane][offset] = ((source & mask_byte) |
                    (latches[plane] & (~mask_byte & 0xFF)))
        else:
            raise VerificationFailure(
                f'{case["name"]}: fixture supplied unsupported VGA write mode {write_mode}')
        offset = (offset + step) & 0xFFFF
    return tuple(bytes(plane) for plane in planes), samples


def expected_core_regs(routine, initial_regs, result):
    state = dict(initial_regs)
    state['ip'] = ROUTINES[routine][1]
    if routine == 'readback':
        state.update(ax=result.value, es=result.output_segment,
                     dx=result.port, flags=result.flags)
    else:
        state.update(ax=result.value, bx=result.packed_bytes,
                     cx=result.third_byte_word, di=result.destination_offset,
                     es=result.output_segment, dx=result.port, flags=result.flags)
    return state


def run_one(native, case, routine, boundary):
    initial_memory, initial_regs, flags, initial_device = prepare(case, routine)
    reference = OriginalRun(case, routine, bytearray(initial_memory),
                            initial_regs, flags, copy.deepcopy(initial_device)).run()
    expected = (reference['boundary'] if boundary == 'core' else reference)
    native_memory = bytearray(initial_memory)
    native_device = copy.deepcopy(initial_device)
    callbacks = None if case.get('null_bus') else BusCallbacks(
        native_memory, native_device, routine)
    view = memory_view(native_memory)
    lib = native.library
    bus = bus_pointer(callbacks)
    if boundary == 'core':
        if routine == 'readback':
            result = native.readback_core(view, initial_regs['ds'],
                initial_regs['ss'], flags, bus)
            expected_regs = expected_core_regs(routine, initial_regs, result)
        else:
            result = native.exchange_core(view, initial_regs['ss'],
                initial_regs['di'], initial_regs['bx'], initial_regs['cx'],
                flags, bus)
            expected_regs = expected_core_regs(routine, initial_regs, result)
    else:
        live = Regs(**{name: initial_regs[name] for name in oracle.REG_NAMES},
                    flags=flags)
        if routine == 'readback':
            native.readback_adapter(view, ctypes.byref(live), bus)
        else:
            native.exchange_adapter(view, ctypes.byref(live), bus)
        expected_regs = {name: getattr(live, name) for name in oracle.REG_NAMES}
        expected_regs['flags'] = live.flags

    expected_regs['flags'] = (result.flags if boundary == 'core' else
                              expected['flags']) if boundary == 'core' else expected_regs['flags']
    actual_state = dict(expected_regs)
    if boundary == 'core':
        # The result struct is the native boundary state; check it against the
        # original before-RET register snapshot, not against its own projection.
        expected_regs = dict(expected['registers'], flags=expected['flags'])
        compare_registers(case, actual_state, expected_regs, routine, 'core')
        oracle_require(reference['boundary']['registers']['ip'] == ROUTINES[routine][1],
                       f'{case["name"]}: original core boundary missed RET')
        expected_memory = expected['memory']
        expected_device = expected['device']
        expected_events = reference['events'][:expected['event_count']]
    else:
        expected_regs = dict(expected['registers'], flags=expected['flags'])
        compare_registers(case, actual_state, expected_regs, routine, 'adapter')
        expected_memory = expected['memory']
        expected_device = expected['device']
        expected_events = reference['events']

    compare_memory(case, native_memory, expected_memory, routine, boundary)
    if callbacks is not None:
        compare_events(callbacks.events, expected_events, routine, case['name'])
    else:
        oracle_require(not case.get('null_bus', False) or callbacks is None,
                       f'{case["name"]}: null-bus fixture unexpectedly created callbacks')
    require(device_state(native_device) == device_state(expected_device),
            f'{case["name"]}: {routine} {boundary} VGA planes/latches/registers differ')

    if routine == 'exchange' and initial_device is not None and \
            initial_regs['ss'] != 0xA000:
        independent_planes, samples = independent_exchange_planes(
            case, initial_device, flags, initial_regs)
        require(device_state(expected_device)[0] == independent_planes,
                f'{case["name"]}: {boundary} original planes differ from independent '
                'incoming-mode/Seq2/latch model')
        if boundary == 'core':
            require(((result.packed_bytes >> 8) & 0xFF) == samples[0] and
                    (result.packed_bytes & 0xFF) == samples[1] and
                    (result.third_byte_word & 0xFF) == samples[2],
                    f'{case["name"]}: native byte returns differ from independent reads')

    if boundary == 'adapter':
        oracle_require(reference['ret_target'] is not None,
                       f'{case["name"]}: adapter did not stop immediately after RET')
    return dict(sites=reference['sites'], edges=reference['edges'],
                events=len(expected_events), ret_target=reference['ret_target'],
                device=device_state(expected_device))


def compare_memory(case, actual, expected, routine, boundary):
    if actual == expected:
        return
    first = next((index for index, (got, want) in enumerate(zip(actual, expected))
                  if got != want), None)
    raise NativeMismatch(f'{case["name"]}: {routine} {boundary} RAM differs '
                         f'at {first:05X}: {actual[first]:02X}/{expected[first]:02X}')


def compare_case(native, case, routine):
    runs = {}
    for boundary in ('core', 'adapter'):
        result = run_one(native, case, routine, boundary)
        runs[boundary] = result
        gc.collect()
    return runs


def worker(directory, before_path):
    before = read_json(before_path)
    oracle_require(before == current_hashes(),
                   'entity VGA inputs changed between build and bounded worker')
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(READBACK_CODE) == 50 and len(INSTRUCTIONS['readback']) == 18,
                   'Readback byte/site accounting changed')
    oracle_require(len(EXCHANGE_CODE) == 85 and len(INSTRUCTIONS['exchange']) == 39,
                   'Exchange byte/site accounting changed')

    setup = readback_cases()
    exchange = exchange_cases()
    baseline = Native(directory, 0)
    observed = {'readback': set(), 'exchange': set()}
    edges = {'readback': set(), 'exchange': set()}
    cases_report = []
    total_events = 0
    for routine, fixtures in (('readback', setup), ('exchange', exchange)):
        for case in fixtures:
            runs = compare_case(baseline, case, routine)
            observed[routine].update(runs['adapter']['sites'])
            edges[routine].update(runs['adapter']['edges'])
            total_events += runs['core']['events'] + runs['adapter']['events']
            cases_report.append(dict(name=case['name'], routine=routine,
                boundaries=dict(core=dict(event_count=runs['core']['events']),
                    adapter=dict(event_count=runs['adapter']['events'],
                                 ret_target=runs['adapter']['ret_target'])),
                gc5=case.get('gc5'), seq_mask=case.get('seq_mask'),
                read_map=case.get('read_map'), df=bool(case.get('df', False)),
                null_bus=bool(case.get('null_bus', False))))
    expected_sites = {
        'readback': set(INSTRUCTIONS['readback']),
        'exchange': set(INSTRUCTIONS['exchange']),
    }
    for routine in ('readback', 'exchange'):
        oracle_require(observed[routine] == expected_sites[routine],
                       f'{routine}: original instruction coverage differs')
        oracle_require(not edges[routine], f'{routine}: unexpected branch edge')

    mutation_witnesses = (
        (1, 'readback', 'setup-incoming-mode0', 'color-care output'),
        (2, 'exchange', 'exchange-df-backward', 'DF-sensitive destination'),
        (3, 'exchange', 'exchange-latch-dependent-write-mode1', 'read latch'),
        (4, 'exchange', 'exchange-return-word-overwritten-sp-e', 'RET mirror overwrite'),
        (5, 'exchange', 'exchange-if-clear-sti-witness', 'unconditional STI'),
    )
    all_cases = {case['name']: case for case in setup + exchange}
    mutations = []
    for mutation, routine, case_name, label in mutation_witnesses:
        mutant = Native(directory, mutation)
        try:
            compare_case(mutant, all_cases[case_name], routine)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, routine=routine,
                name=label, case=case_name, mismatch=str(error), completed=True))
        else:
            raise VerificationFailure(
                f'Compiled VGA mutation {mutation} survived {case_name}')
        gc.collect()

    after = current_hashes()
    oracle_require(before == after, 'entity VGA inputs changed during bounded run')
    oracle_require(len(setup) == 16 and len(exchange) == 34 and
                   len(mutations) == 5, 'entity VGA report scope changed')
    site_union = sorted(observed['readback'] | observed['exchange'])
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(setup) + len(exchange), readback_case_count=len(setup),
        exchange_case_count=len(exchange), boundary_call_count=2 * (len(setup) + len(exchange)),
        mutation_count=len(mutations), mutations=mutations, cases=cases_report,
        translated_code_bytes=len(READBACK_CODE) + len(EXCHANGE_CODE),
        native_code_ranges=[[READBACK_ENTRY, READBACK_END],
                            [EXCHANGE_ENTRY, EXCHANGE_END]],
        routine_bytes={'readback': READBACK_CODE.hex(), 'exchange': EXCHANGE_CODE.hex()},
        executed_instruction_addresses=site_union, instruction_sites=site_union,
        instruction_site_count=len(site_union), branch_instruction_addresses=[],
        branch_edges=[], total_bus_events=total_events,
        domains=[
            '5D94..5DC5 exact 50-byte/18-site readback setup, 5EBA..5F0E exact 85-byte/39-site exchange',
            'all four SS hardware-register mirrors and ordered word OUT callbacks; final DS:4 row pitch wins when DS=SS',
            'core stops before RET; adapter executes actual near RET and stops at its target',
            '5EBA consumes incoming GC5 read/write mode, Seq2 plane mask, GC2/GC7 read-mode-1 compare and live latches',
            'all three incoming BH/BL/CL masks returned as readback bytes; high CH preserved',
            'DF-clear/set STOSB order, DI wrap at 0000/FFFF, and full 20-bit physical word wrap',
            'SS mirrors alias return word and SS=A000 routes mirrors, VGA aperture reads/writes, and RET through the bus',
            'whole 1 MiB RAM, all registers, VGA planes/latches/ports, and defined final flags',
            'ordinary-RAM null-bus fallback for selected exchange cases'],
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS),
        input_hashes=after))
    print(f'PASS entity VGA C: {len(setup) + len(exchange)} fixtures, '
          f'{len(site_union)} instruction sites, {total_events} bounded bus events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity VGA arguments')
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-vga-', parent=BUILD) as directory:
        before_path = Path(directory) / 'input-hashes.json'
        before = current_hashes()
        write_json(before_path, before)
        for mutation in range(6):
            build(Path(directory) / f'entity-vga-m{mutation}.dll', mutation,
                  'entity_vga')
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory, str(before_path)], cwd=ROOT, timeout=180,
                    memory_mib=384)


if __name__ == '__main__':
    main()
