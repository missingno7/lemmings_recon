"""Bounded original-versus-C checks for the variable-width decimal writers."""
from __future__ import annotations

import argparse
import ctypes as ct
import copy
import gc
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x


SIZE = 1 << 20
MASK = SIZE - 1
LOADS = (0x1010, 0x1213, 0x2345)
ENTRY_FULL = 0x4B68
ENTRY_PAIR = 0x4BBE
PAIR_END = 0x4BC2
RET = 0x4BBD
INSTRUCTION_CAP = 128
EVENT_CAP = 32
DEFINED_FLAGS = 0x0FD7
ARITH_FLAGS = 0x08D5
INC_FLAGS = 0x08D4
LOGIC_FLAGS = DEFINED_FLAGS & ~0x0010
CALLBACK_BUDGET_EXIT = 86
CALLBACK_ERROR_EXIT = 87
REPORT = BUILD / 'decimal-field-differential.json'

IMAGE, IMAGE_META = unpack(ASSET.read_bytes())
LOADED_IMAGES = {load: relocated(IMAGE, IMAGE_META['relocations'], load)
                 for load in LOADS}
PATTERN_MEMORY = bytes((index * 73 + 0xA5) & 0xFF for index in range(SIZE))
CODE = IMAGE[ENTRY_FULL:PAIR_END]
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(CODE, ENTRY_FULL)}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP)}
UNCONDITIONAL = {'jmp', 'ljmp'}
EXPECTED_EDGES = set()
for _pc, _ins in INS.items():
    if _pc not in BRANCHES:
        continue
    EXPECTED_EDGES.add((_pc, _ins.operands[0].imm & 0xFFFF))
    if _ins.mnemonic.lower() not in UNCONDITIONAL:
        EXPECTED_EDGES.add((_pc, (_pc + _ins.size) & 0xFFFF))

REG_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
             'cs', 'ds', 'es', 'ss', 'ip', 'flags')
REG_IDS = {name: getattr(x, 'UC_X86_REG_' + name.upper())
           for name in REG_NAMES if name != 'flags'}
MEM = ct.POINTER(ct.c_uint8)


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in REG_NAMES]


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('data_segment', 'value', 'prefix_value', 'cursor', 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'prefix_value', 'cursor', 'flags')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32,
                     ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """A constructed original execution or an oracle bound did not complete."""


class Mismatch(AssertionError):
    """A completed native execution differs from the completed original."""


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
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def put_physical_word(memory, address, value):
    address &= MASK
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def flags_after(ins, previous_mask):
    mnemonic = ins.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return LOGIC_FLAGS
    if mnemonic in ('add', 'sub', 'cmp'):
        return DEFINED_FLAGS
    if mnemonic in ('inc', 'dec'):
        return (DEFINED_FLAGS & ~0x0001) | (previous_mask & 0x0001)
    return previous_mask


def parity_even(value):
    return (value & 0xFF).bit_count() % 2 == 0


def inc16_flags(flags, before):
    after = (before + 1) & 0xFFFF
    bits = 0
    if parity_even(after):
        bits |= 0x0004
    if after == 0:
        bits |= 0x0040
    if after & 0x8000:
        bits |= 0x0080
    if before & 0x000F == 0x000F:
        bits |= 0x0010
    if before == 0x7FFF:
        bits |= 0x0800
    return ((flags & ~INC_FLAGS) | bits) & 0xFFFF


def decimal_add_flags(flags, value):
    result = ((value & 0xFF) + 0x30) & 0xFF
    bits = 0
    if parity_even(result):
        bits |= 0x0004
    if result == 0:
        bits |= 0x0040
    if result & 0x80:
        bits |= 0x0080
    if ((value ^ 0x30 ^ result) & 0x10) != 0:
        bits |= 0x0010
    if ((~(value ^ 0x30) & (value ^ result)) & 0x80) != 0:
        bits |= 0x0800
    if value + 0x30 > 0xFF:
        bits |= 0x0001
    return ((flags & ~ARITH_FLAGS) | bits) & 0xFFFF


def format_contract(entry, value):
    value &= 0xFF
    unit = value % 10 + 0x30
    quotient = value // 10
    if entry == ENTRY_PAIR:
        if quotient:
            tens = (quotient + 0x30) & 0xFF
            return (tens, unit), tens, 1
        return (unit, 0x20), 0x20, 0

    hundreds = value // 100
    tens_value = (value // 10) % 10
    if hundreds:
        tens = tens_value + 0x30
        return (hundreds + 0x30, tens, unit), tens, 2
    if tens_value:
        tens = tens_value + 0x30
        return (tens, unit, 0x20), tens, 1
    return (unit, 0x20, 0x20), 0x20, 0


def output_stores(entry, value, cursor):
    """Return the literal ordered MOV stores and the post-INC SI value."""
    output, _ah, _prefix = format_contract(entry, value)
    values = value & 0xFF
    stores = []
    current = cursor & 0xFFFF
    if entry == ENTRY_FULL:
        stores.extend(((current, 0x20), ((current + 1) & 0xFFFF, 0x20),
                       ((current + 2) & 0xFFFF, 0x20)))
        if values >= 100:
            stores.append((current, values // 100 + 0x30))
            current = (current + 1) & 0xFFFF
        stores.extend(((current, 0x20), ((current + 1) & 0xFFFF, 0x20)))
        if values >= 100 or values % 100 >= 10:
            stores.append((current, (values // 10) % 10 + 0x30))
            current = (current + 1) & 0xFFFF
        stores.append((current, values % 10 + 0x30))
        current = (current + 1) & 0xFFFF
    else:
        stores.extend(((current, 0x20), ((current + 1) & 0xFFFF, 0x20)))
        quotient = values // 10
        if quotient:
            stores.append((current, (quotient + 0x30) & 0xFF))
            current = (current + 1) & 0xFFFF
        stores.append((current, values % 10 + 0x30))
        current = (current + 1) & 0xFFFF
    return stores, current, output


def make_cases():
    out = []

    def add(name, entry, value, mode, **spec):
        out.append(dict(name=name, entry=entry, value=value & 0xFF,
                        mode=mode, seed=len(out) + 0x4B6800, **spec))

    # Every AL input is checked at both logical boundaries and through both
    # real register adapters. AH/BH, control flags, and load addresses vary.
    for entry, label in ((ENTRY_FULL, 'full'), (ENTRY_PAIR, 'pair')):
        for mode in ('core', 'adapter'):
            for value in range(256):
                add(f'{label}-{mode}-{value:03d}', entry, value, mode)

    add('full-df-forward', ENTRY_FULL, 42, 'adapter', df=True)
    add('pair-df-forward', ENTRY_PAIR, 255, 'adapter', df=True)
    add('full-final-inc-of', ENTRY_FULL, 255, 'adapter', si=0x7FFD)
    add('pair-final-inc-of', ENTRY_PAIR, 10, 'adapter', si=0x7FFE)
    add('full-offset-wrap', ENTRY_FULL, 255, 'core', si=0xFFFE)
    add('pair-offset-wrap', ENTRY_PAIR, 5, 'adapter', si=0xFFFF)
    add('physical-data-wrap', ENTRY_FULL, 100, 'adapter', ds=0xFFFF, si=0x0020)
    add('physical-stack-word-wrap', ENTRY_PAIR, 255, 'adapter',
        ss=0xFFFF, sp=0x000F)
    add('stack-pointer-wrap', ENTRY_PAIR, 255, 'adapter',
        ss=0x7000, sp=0xFFFF)
    add('saved-return-low-alias', ENTRY_FULL, 7, 'adapter',
        ds=0x7000, ss=0x7000, si=0x8100, sp=0x8100)
    add('saved-return-high-alias', ENTRY_PAIR, 10, 'adapter',
        ds=0x7000, ss=0x7000, si=0x8101, sp=0x8100)
    add('postwrite-live-return', ENTRY_FULL, 7, 'adapter',
        ds=0x7000, ss=0x7000, si=0x8100, sp=0x8100,
        provider=True, outer_return=0x1345, provider_return=0xCAFE)
    add('vga-mode0-full', ENTRY_FULL, 100, 'core',
        ds=0xA000, si=0x1234, vga=True, write_mode=0, map_mask=0x05)
    add('vga-mode1-pair', ENTRY_PAIR, 255, 'core',
        ds=0xA000, si=0x4321, vga=True, write_mode=1, map_mask=0x0A)
    add('vga-offset-wrap', ENTRY_FULL, 9, 'core',
        ds=0xA000, si=0xFFFF, vga=True, write_mode=0, map_mask=0x0F)
    add('vga-live-ret-read', ENTRY_PAIR, 7, 'adapter',
        ds=0x5100, ss=0xA000, si=0x2210, sp=0x8000,
        vga=True, write_mode=0, map_mask=0x03, outer_return=0x1234)
    for entry, label in ((ENTRY_FULL, 'full'), (ENTRY_PAIR, 'pair')):
        for mode in ('core', 'adapter'):
            for value in (0, 7, 10, 99, 100, 255):
                add(f'{label}-nullbus-{mode}-{value:03d}', entry, value, mode,
                    bus=False)

    oracle_require(len(out) == 1064,
                   f'decimal fixture count changed unexpectedly: {len(out)}')
    oracle_require(len({case['name'] for case in out}) == len(out),
                   'decimal fixture names are not unique')
    return out


def prepare(case):
    rng = random.Random(case['seed'])
    memory = bytearray(PATTERN_MEMORY)
    load = LOADS[case['seed'] % len(LOADS)]
    loaded = LOADED_IMAGES[load]
    code_base = physical(load, 0)
    memory[code_base:code_base + len(loaded)] = loaded

    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    raw_flags = (2 | (rng.randrange(0x1000) & 0x0ED5)) & ~0x0100
    if case.get('df'):
        raw_flags |= 0x0400
    elif case.get('df') is False:
        raw_flags &= ~0x0400
    regs.update(cs=load, ip=case['entry'], ds=case.get('ds', 0x4513),
                ss=case.get('ss', 0x7000), sp=case.get('sp', 0x8000),
                si=case.get('si', 0x1200),
                ax=((case.get('ah', rng.randrange(256)) << 8) | case['value']),
                bx=((case.get('bh', 0xA5 if case['entry'] == ENTRY_FULL and
                              case['mode'] == 'core' and case['value'] == 9
                              else rng.randrange(256)) << 8) |
                    case.get('bl', rng.randrange(256))),
                flags=raw_flags)

    device = None
    if case.get('vga'):
        device = MinimapVga(0x4B6800 + case['seed'], read_map=0)
        device.seq[2] = case.get('map_mask', 0x0F)
        device.seq[4] = 0x06
        device.gc[0] = device.gc[1] = device.gc[2] = 0
        device.gc[3] = 0
        device.gc[4] = 0
        device.gc[5] = case.get('write_mode', 0)
        device.gc[6] = 0x05
        device.gc[7] = 0
        device.gc[8] = 0xFF
        device.latches = [0x13, 0x57, 0x9B, 0xDF]

    # Seed the actual physical return word. A word at SS:FFFF is consecutive
    # physical bytes, with the second byte wrapping at the 20-bit boundary.
    return_address = physical(regs['ss'], regs['sp'])
    outer = case.get('outer_return', 0xCAFE)
    put_physical_word(memory, return_address, outer)
    if device is not None and VGA_BASE <= return_address < VGA_END:
        offset = return_address - VGA_BASE
        device.planes[device.gc[4] & 3][offset] = outer & 0xFF
        next_address = (return_address + 1) & MASK
        if VGA_BASE <= next_address < VGA_END:
            device.planes[device.gc[4] & 3][next_address - VGA_BASE] = outer >> 8

    return memory, regs, device


def expected_flags(case, regs, next_cursor):
    _out, _ah, _prefix = format_contract(case['entry'], case['value'])
    flags = decimal_add_flags(regs['flags'], case['value'] % 10)
    return inc16_flags(flags, (next_cursor - 1) & 0xFFFF)


def expected_contract(case, initial_memory, initial_regs, initial_device):
    entry, value = case['entry'], case['value']
    stores, next_cursor, output = output_stores(entry, value, initial_regs['si'])
    _out, tens, prefix = format_contract(entry, value)
    expected_memory = bytearray(initial_memory)
    expected_planes = ([bytearray(plane) for plane in initial_device.planes]
                       if initial_device is not None else None)
    expected_latches = (list(initial_device.latches)
                        if initial_device is not None else None)

    for offset, byte in stores:
        address = physical(initial_regs['ds'], offset)
        expected_memory[address] = byte
        if expected_planes is not None and VGA_BASE <= address < VGA_END:
            vga_offset = address - VGA_BASE
            if initial_device.gc[5] & 0x03 == 1:
                source = initial_device.latches
                for plane in range(4):
                    if initial_device.seq[2] & (1 << plane):
                        expected_planes[plane][vga_offset] = source[plane]
            else:
                for plane in range(4):
                    if initial_device.seq[2] & (1 << plane):
                        expected_planes[plane][vga_offset] = byte

        if (case.get('provider') and byte == 0x37 and
                address == physical(initial_regs['ds'], initial_regs['si'])):
            provider_address = physical(initial_regs['ss'], initial_regs['sp'])
            target = case.get('provider_return', 0xCAFE)
            put_physical_word(expected_memory, provider_address, target)

    expected_regs = dict(initial_regs)
    unit = value % 10 + 0x30
    expected_regs['ax'] = ((tens & 0xFF) << 8) | unit
    expected_regs['bx'] = (initial_regs['bx'] & 0xFF00) | prefix
    expected_regs['si'] = next_cursor
    expected_regs['flags'] = expected_flags(case, initial_regs, next_cursor)
    if case['mode'] == 'core':
        expected_regs['ip'] = RET
    else:
        ret_address = physical(initial_regs['ss'], initial_regs['sp'])
        ret_bytes = []
        for delta in (0, 1):
            address = (ret_address + delta) & MASK
            if initial_device is not None and VGA_BASE <= address < VGA_END:
                offset = address - VGA_BASE
                read_map = initial_device.gc[4] & 3
                read_value = expected_planes[read_map][offset]
                expected_memory[address] = read_value
                if expected_planes is not None:
                    # Read loads all latches, but does not modify a plane.
                    expected_latches = [expected_planes[p][offset]
                                        for p in range(4)]
                ret_bytes.append(read_value)
            else:
                ret_bytes.append(expected_memory[address])
        expected_regs['ip'] = ret_bytes[0] | (ret_bytes[1] << 8)
        expected_regs['sp'] = (initial_regs['sp'] + 2) & 0xFFFF
    return expected_memory, expected_regs, expected_planes, expected_latches, stores


class OriginalRun:
    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs_in, self.device = case, memory, regs, device
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * SIZE)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(SIZE, initial)
        for name, register in REG_IDS.items():
            self.cpu.reg_write(register, regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])
        self.sites = set()
        self.edges = set()
        self.events = []
        self.previous = None
        self.previous_mask = DEFINED_FLAGS
        self.current_mask = DEFINED_FLAGS
        self.current_flags = regs['flags']
        self.current_site = None
        self.steps = 0
        self.failure = None
        self.stopped = False
        self.ret_target = None
        self.provider_used = False
        self.pending_provider = None
        self.provider_address = (physical(regs['ds'], regs['si'])
                                 if case.get('provider') else None)

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def mirror(linear, value):
            address = linear & MASK
            byte = bytes((value & 0xFF,))
            self.memory[address] = value & 0xFF
            self.cpu.mem_write(address, byte)
            self.cpu.mem_write(address + SIZE, byte)

        def flush_provider():
            if self.pending_provider is None:
                return
            address, value = self.pending_provider
            put_physical_word(self.memory, address, value)
            for delta in (0, 1):
                at = (address + delta) & MASK
                byte = bytes((self.memory[at],))
                self.cpu.mem_write(at, byte)
                self.cpu.mem_write(at + SIZE, byte)
            self.pending_provider = None

        def record(kind, address, value):
            if len(self.events) >= EVENT_CAP:
                fail(f"{case['name']}: original bus trace cap exhausted")
                return
            self.events.append((kind, address & MASK, value & 0xFF,
                                self.current_flags & self.current_mask,
                                self.current_mask, self.current_site))

        def read_value(address):
            address &= MASK
            if self.device is not None and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, self.current_flags)
            else:
                value = self.memory[address]
            return value & 0xFF

        def on_code(uc, _address, _size, _user):
            try:
                flush_provider()
                off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
                cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
                if self.previous == RET:
                    self.ret_target = off
                    self.stopped = True
                    uc.emu_stop()
                    return
                if self.previous is not None:
                    if self.previous in BRANCHES:
                        self.edges.add((self.previous, off))
                    self.current_mask = flags_after(INS[self.previous],
                                                    self.previous_mask)
                    self.previous_mask = self.current_mask
                if cs != regs['cs'] or off not in INS:
                    fail(f"{case['name']}: original escaped at {cs:04X}:{off:04X}")
                    return
                ins = INS[off]
                code_address = physical(regs['cs'], off)
                if bytes(uc.mem_read(code_address, ins.size)) != bytes(ins.bytes):
                    fail(f"{case['name']}: executing pinned bytes changed at {off:04X}")
                    return
                if off == RET and case['mode'] == 'core':
                    self.stopped = True
                    uc.emu_stop()
                    return
                if self.steps >= INSTRUCTION_CAP:
                    fail(f"{case['name']}: original instruction cap exhausted")
                    return
                self.steps += 1
                self.sites.add(off)
                self.current_site = off
                self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
                self.previous = off
            except BaseException as error:
                fail(f"{case['name']}: original code hook failed: "
                     f"{type(error).__name__}: {error}")

        def on_read(uc, _access, address, size, _value, _user):
            try:
                for delta in range(size):
                    linear = address + delta
                    if not 0 <= linear < 2 * SIZE:
                        fail(f"{case['name']}: original read outside mapped memory")
                        return
                    p = linear & MASK
                    value = read_value(p)
                    mirror(linear, value)
                    record('read', p, value)
                    if self.failure:
                        return
            except BaseException as error:
                fail(f"{case['name']}: original read hook failed: "
                     f"{type(error).__name__}: {error}")

        def on_write(uc, _access, address, size, value, _user):
            try:
                for delta in range(size):
                    linear = address + delta
                    if not 0 <= linear < 2 * SIZE:
                        fail(f"{case['name']}: original write outside mapped memory")
                        return
                    p = linear & MASK
                    byte = (value >> (8 * delta)) & 0xFF
                    if self.device is not None:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    mirror(linear, byte)
                    record('write', p, byte)
                    if self.failure:
                        return
                    if (case.get('provider') and not self.provider_used and
                            p == self.provider_address and byte == 0x37):
                        self.provider_used = True
                        self.pending_provider = (
                            physical(regs['ss'], regs['sp']),
                            case.get('provider_return', 0xCAFE))
            except BaseException as error:
                fail(f"{case['name']}: original write hook failed: "
                     f"{type(error).__name__}: {error}")

        self._callbacks = (on_code, on_read, on_write)
        self.cpu.hook_add(UC_HOOK_CODE, on_code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, on_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs_in['cs'], self.case['entry']),
                               0, count=INSTRUCTION_CAP + 2)
        except UcError as error:
            raise OracleFailure(f"{self.case['name']}: Unicorn failed: {error}") from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f"{self.case['name']}: original did not stop at the declared boundary")
        oracle_require(self.pending_provider is None,
                       f"{self.case['name']}: provider effect was not flushed")
        oracle_require(len(self.events) <= EVENT_CAP,
                       f"{self.case['name']}: original event cap exhausted")
        oracle_require(self.sites <= set(INS),
                       f"{self.case['name']}: original executed outside decoded sites: "
                       f"{self.sites - set(INS)}")
        oracle_require(self.case['entry'] in self.sites,
                       f"{self.case['name']}: entry instruction did not execute")
        oracle_require((RET in self.sites) == (self.case['mode'] == 'adapter'),
                       f"{self.case['name']}: RET execution differs from boundary mode")
        state = {name: self.cpu.reg_read(register) & 0xFFFF
                 for name, register in REG_IDS.items()}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        actual_memory = bytes(self.cpu.mem_read(0, SIZE))
        oracle_require(actual_memory == bytes(self.memory),
                       f"{self.case['name']}: Unicorn RAM and canonical RAM diverged")
        oracle_require(self.provider_used == bool(self.case.get('provider')),
                       f"{self.case['name']}: provider witness did not fire")
        if self.case['mode'] == 'core':
            oracle_require(state['ip'] == RET and self.previous is not None,
                           f"{self.case['name']}: core did not stop before RET")
            oracle_require(self.previous != RET,
                           f"{self.case['name']}: core executed RET")
        else:
            oracle_require(self.previous == RET and self.ret_target is not None,
                           f"{self.case['name']}: adapter did not execute real RET")
            oracle_require(state['sp'] == ((self.regs_in['sp'] + 2) & 0xFFFF),
                           f"{self.case['name']}: adapter RET did not pop live SS:SP")
        return dict(memory=actual_memory, state=state, events=self.events,
                    sites=self.sites, edges=self.edges, device=self.device,
                    ret_target=self.ret_target, steps=self.steps,
                    provider_used=self.provider_used)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'decimal-field-m{mutation}.dll',
                     mutation, 'decimal_field')
        self.library = ct.CDLL(str(path))
        self.full_core = self.library.lmn_write_decimal_field_core
        self.full_core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.full_core.restype = Result
        self.pair_core = self.library.lmn_write_decimal_pair_core
        self.pair_core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.pair_core.restype = Result
        self.full_adapter = self.library.lmn_write_decimal_field_adapter
        self.full_adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.full_adapter.restype = None
        self.pair_adapter = self.library.lmn_write_decimal_pair_adapter
        self.pair_adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.pair_adapter.restype = None


class NativeBus:
    def __init__(self, case, memory, device, regs):
        self.case, self.memory, self.device = case, memory, device
        self.events = []
        self.provider_used = False
        self.trigger_address = physical(regs['ds'], regs['si'])
        self.target_address = physical(regs['ss'], regs['sp'])

        def reserve():
            if len(self.events) >= EVENT_CAP:
                worker_exit(CALLBACK_BUDGET_EXIT,
                            f"{case['name']}: native bus callback cap exhausted")

        def apply_provider(kind, address, value=None):
            if (case.get('provider') and not self.provider_used and
                    kind == 'write' and address == self.trigger_address and
                    value == 0x37):
                self.provider_used = True
                put_physical_word(self.memory, self.target_address,
                                  case.get('provider_return', 0xCAFE))

        def read(_context, _native_memory, address, flags):
            try:
                address &= MASK
                reserve()
                value = (self.device.read(self.memory, address, flags)
                         if self.device is not None and VGA_BASE <= address < VGA_END
                         else self.memory[address])
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                if self.device is not None and len(self.device.trace) > EVENT_CAP:
                    worker_exit(CALLBACK_BUDGET_EXIT,
                                f"{case['name']}: native VGA trace cap exhausted")
                return value & 0xFF
            except BaseException as error:
                worker_exit(CALLBACK_ERROR_EXIT,
                            f"{case['name']}: native read callback failed: "
                            f"{type(error).__name__}: {error}")
                return 0

        def write(_context, _native_memory, address, value, flags):
            try:
                address &= MASK
                value &= 0xFF
                reserve()
                if self.device is not None:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                apply_provider('write', address, value)
                if self.device is not None and len(self.device.trace) > EVENT_CAP:
                    worker_exit(CALLBACK_BUDGET_EXIT,
                                f"{case['name']}: native VGA trace cap exhausted")
            except BaseException as error:
                worker_exit(CALLBACK_ERROR_EXIT,
                            f"{case['name']}: native write callback failed: "
                            f"{type(error).__name__}: {error}")

        self._read = READ(read)
        self._write = WRITE(write)
        self._out = OUT()
        self.bus = RasterBus(None, self._read, self._write, self._out)


def c_buffer(memory):
    return (ct.c_uint8 * SIZE).from_buffer(memory)


def compare_memory(case, actual, expected, label):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    raise Mismatch(f"{case['name']} {label} RAM differs at {mismatch:05X}: "
                   f"{actual[mismatch]:02X}/{expected[mismatch]:02X}")


def compare_events(case, actual, expected):
    want_events = [(kind, address, value, flags & mask)
                   for kind, address, value, flags, mask, _site in expected]
    require(len(actual) == len(want_events),
            f"{case['name']}: event count differs {len(actual)}/{len(want_events)}")
    for index, (got, want) in enumerate(zip(actual, want_events)):
        kind, address, value, flags = got
        require((kind, address, value, flags & expected[index][4]) == want,
                f"{case['name']}: event {index} differs: {got!r}/{want!r}")


def compare_regs(case, actual, expected, label):
    for name in REG_NAMES:
        if name == 'flags':
            require(((actual[name] ^ expected[name]) & DEFINED_FLAGS) == 0,
                    f"{case['name']} {label} defined FLAGS differ: "
                    f"{actual[name]:04X}/{expected[name]:04X}")
        else:
            require(actual[name] == expected[name],
                    f"{case['name']} {label} {name} differs: "
                    f"{actual[name]:04X}/{expected[name]:04X}")


def assert_independent(case, initial_memory, initial_regs, initial_device, result):
    expected_memory, expected_regs, expected_planes, expected_latches, stores = expected_contract(
        case, initial_memory, initial_regs, initial_device)
    try:
        compare_regs(case, result['state'], expected_regs, 'original independent')
        compare_memory(case, result['memory'], expected_memory, 'original independent')
    except Mismatch as error:
        raise OracleFailure(f"{case['name']}: independent original contract failed: {error}") from error
    if expected_planes is not None:
        oracle_require(tuple(bytes(p) for p in result['device'].planes) ==
                       tuple(bytes(p) for p in expected_planes),
                       f"{case['name']}: original VGA planes differ from byte-write model")
        oracle_require((tuple(bytes(p) for p in result['device'].planes),
                        tuple(result['device'].latches),
                        tuple(result['device'].seq), tuple(result['device'].gc),
                        result['device'].si, result['device'].gi,
                        result['device'].outcount) ==
                       (tuple(bytes(p) for p in expected_planes),
                        tuple(expected_latches), tuple(initial_device.seq),
                        tuple(initial_device.gc), initial_device.si,
                        initial_device.gi, initial_device.outcount),
            f"{case['name']}: original VGA latch/controller state differs independently")
    if case['mode'] == 'adapter':
        oracle_require(result['ret_target'] == expected_regs['ip'],
                       f"{case['name']}: original RET target differs from live word model")
    oracle_require(len(result['events']) <= EVENT_CAP,
                   f"{case['name']}: original access count exceeded hard cap")


def run_original(case):
    memory, regs, device = prepare(case)
    initial_memory = bytes(memory)
    initial_regs = dict(regs)
    initial_device = copy.deepcopy(device)
    original = OriginalRun(case, memory, regs, device).run()
    assert_independent(case, initial_memory, initial_regs, initial_device, original)
    return original, memory, regs, device


def input_paths():
    paths = (
        'assets/vgalemmi.exe', 'metadata/inputs.json', 'metadata/symbols.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/decimal_fields.asm',
        'src/entity_selection.asm', 'src/game_code_late_after_selection.asm',
        'src/game_code_late_after_decimal.asm', 'src/image_tail.asm',
        'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/entity-actions.md', 'docs/decimal-field.md',
        'c/decimal_field.c', 'c/decimal_field.h', 'c/regs.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'tests/decimal_field.py',
        'tests/minimap_vga.py', 'tools/unpack.py', 'tools/common.py',
        'tools/cbuild.py', 'tools/bounded_process.py', 'tools/difftest.py',
        'tools/coverage.py',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise OracleFailure('missing required decimal-field inputs: ' + ', '.join(missing))
    return paths


def input_hashes():
    return {path: sha((ROOT / path).read_bytes()) for path in input_paths()}


def run_original_campaign(cases):
    sites, edges = set(), set()
    for index, case in enumerate(cases):
        result, _memory, _regs, _device = run_original(case)
        sites |= result['sites']
        edges |= result['edges']
        if index % 32 == 31:
            gc.collect()
    oracle_require(sites == set(INS),
                   f"decimal coverage sites differ: missing={set(INS) - sites}, "
                   f"extra={sites - set(INS)}")
    oracle_require(edges == EXPECTED_EDGES,
                   f"decimal branch edges differ: missing={EXPECTED_EDGES - edges}, "
                   f"extra={edges - EXPECTED_EDGES}")
    return sites, edges


def run_native_case(native, case):
    initial_memory, initial_regs, initial_device = prepare(case)
    initial_snapshot = bytes(initial_memory)
    initial_regs_snapshot = dict(initial_regs)
    initial_device_snapshot = copy.deepcopy(initial_device)
    original = OriginalRun(case, initial_memory, initial_regs, initial_device).run()
    assert_independent(case, initial_snapshot, initial_regs_snapshot,
                       initial_device_snapshot, original)

    c_memory = bytearray(initial_snapshot)
    c_device = copy.deepcopy(initial_device_snapshot)
    call = Call(initial_regs['ds'], initial_regs['ax'], initial_regs['bx'],
                initial_regs['si'], initial_regs['flags'])
    regs = Regs(**initial_regs)
    bus_state = None
    if case.get('bus', True):
        bus_state = NativeBus(case, c_memory, c_device, initial_regs)
        bus_pointer = ct.byref(bus_state.bus)
    else:
        bus_pointer = None
    pointer = c_buffer(c_memory)

    if case['entry'] == ENTRY_FULL and case['mode'] == 'core':
        output = native.full_core(pointer, ct.byref(call), bus_pointer)
        actual_state = dict(initial_regs)
        actual_state.update(ax=output.value, bx=output.prefix_value,
                            si=output.cursor, flags=output.flags, ip=RET)
        actual_events = bus_state.events if bus_state is not None else None
    elif case['entry'] == ENTRY_PAIR and case['mode'] == 'core':
        output = native.pair_core(pointer, ct.byref(call), bus_pointer)
        actual_state = dict(initial_regs)
        actual_state.update(ax=output.value, bx=output.prefix_value,
                            si=output.cursor, flags=output.flags, ip=RET)
        actual_events = bus_state.events if bus_state is not None else None
    elif case['entry'] == ENTRY_FULL:
        native.full_adapter(pointer, ct.byref(regs), bus_pointer)
        actual_state = {name: getattr(regs, name) for name in REG_NAMES}
        actual_events = bus_state.events if bus_state is not None else None
    else:
        native.pair_adapter(pointer, ct.byref(regs), bus_pointer)
        actual_state = {name: getattr(regs, name) for name in REG_NAMES}
        actual_events = bus_state.events if bus_state is not None else None

    compare_regs(case, actual_state, original['state'], 'native')
    compare_memory(case, bytes(c_memory), original['memory'], 'native')
    if bus_state is not None:
        compare_events(case, actual_events, original['events'])
        require(bus_state.provider_used == original['provider_used'],
                f"{case['name']}: native/provider activation differs")
        if c_device is not None:
            require(c_device.state() == original['device'].state(),
                    f"{case['name']}: native VGA device state differs")
    elif c_device is not None:
        raise OracleFailure(f"{case['name']}: null-bus VGA case is not in the contract")
    return original


def native_worker(directory, before):
    cases = make_cases()
    sites, edges = set(), set()
    total_events = total_steps = 0
    baseline = Native(directory, 0)
    for index, case in enumerate(cases):
        result = run_native_case(baseline, case)
        sites |= result['sites']
        edges |= result['edges']
        total_events += len(result['events'])
        total_steps += result['steps']
        if index % 32 == 31:
            gc.collect()
    oracle_require(sites == set(INS),
                   f'native coverage sites differ: missing={set(INS) - sites}, '
                   f'extra={sites - set(INS)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'native branch edges differ: missing={EXPECTED_EDGES - edges}, '
                   f'extra={edges - EXPECTED_EDGES}')

    witnesses = {
        1: next(c for c in cases if c['name'] == 'full-core-007'),
        2: next(c for c in cases if c['name'] == 'pair-core-255'),
        3: next(c for c in cases if c['name'] == 'full-core-000'),
        4: next(c for c in cases if c['name'] == 'full-df-forward'),
        5: next(c for c in cases if c['name'] == 'full-core-009'),
        6: next(c for c in cases if c['name'] == 'full-final-inc-of'),
        7: next(c for c in cases if c['name'] == 'postwrite-live-return'),
    }
    detected = []
    for mutation, case in witnesses.items():
        mutant = Native(directory, mutation)
        try:
            run_native_case(mutant, case)
        except Mismatch as error:
            detected.append(dict(mutation=mutation, case=case['name'],
                                 mismatch=str(error)))
        else:
            raise OracleFailure(f'completed decimal mutation {mutation} survived')

    end_hashes = input_hashes()
    oracle_require(before == end_hashes,
                   'source inputs changed during decimal-field campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY_FULL, PAIR_END],
        translated_code_bytes=len(CODE), instruction_sites=len(sites),
        static_instruction_addresses=sorted(INS),
        case_count=len(cases), mutation_count=len(detected),
        mutations_detected=detected,
        executed_instruction_addresses=sorted(sites),
        branch_edge_count=len(edges), branch_edges=[list(e) for e in sorted(edges)],
        static_branch_edges=[list(e) for e in sorted(EXPECTED_EDGES)],
        routines=[dict(name='WriteDecimalByteField', start=ENTRY_FULL,
                       end=RET + 1, instruction_sites=sum(
                           ENTRY_FULL <= pc <= RET for pc in sites)),
                  dict(name='WriteDecimalBytePair', start=ENTRY_PAIR,
                       end=PAIR_END, instruction_sites=sum(
                           ENTRY_PAIR <= pc < PAIR_END for pc in sites))],
        total_bus_events=total_events, original_code_hook_steps=total_steps,
        cases=[case['name'] for case in cases], input_hashes=end_hashes,
        limits=dict(worker_seconds=240, process_memory_mib=384,
                    windows_tree_memory_mib=640,
                    original_instruction_limit=INSTRUCTION_CAP,
                    native_callback_event_limit=EVENT_CAP,
                    callback_budget_exit=CALLBACK_BUDGET_EXIT,
                    callback_error_exit=CALLBACK_ERROR_EXIT),
        domain='Full left-aligned decimal field at 4B68 and two-byte unnormalized pair at 4BBE; both logical cores and actual-RET adapters; all AL values; live DS:SI stores, 16-bit SI and 20-bit physical wrap, DF-independent forward INC, final flags, VGA memory writes, null bus, DS/SS aliases, and provider-mutated live return words'))
    print(f'PASS decimal field native: {len(cases)} cases, {len(sites)} sites, '
          f'{len(edges)} edges, {len(detected)} completed mutations', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original-only', action='store_true')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--original-worker', action='store_true')
    parser.add_argument('--build-dir')
    parser.add_argument('--hash-file')
    args = parser.parse_args()
    if args.worker or args.original_worker:
        if not args.hash_file:
            raise SystemExit('worker requires --hash-file')
        before = json.loads(Path(args.hash_file).read_text(encoding='utf-8'))
        if args.original_worker:
            cases = make_cases()
            sites, edges = run_original_campaign(cases)
            end_hashes = input_hashes()
            oracle_require(before == end_hashes,
                           'source inputs changed during original-only preflight')
            write_json(BUILD / 'decimal-field-original-preflight.json', dict(
                image='main', image_sha256=sha(IMAGE), code_range=[ENTRY_FULL, PAIR_END],
                translated_code_bytes=len(CODE), instruction_sites=len(sites),
                static_instruction_addresses=sorted(INS),
                executed_instruction_addresses=sorted(sites),
                case_count=len(cases), branch_edge_count=len(edges),
                branch_edges=[list(e) for e in sorted(edges)], input_hashes=end_hashes,
                domain='Original-only decimal field/pair formatting, final flags, exact stores, physical wrap, VGA planes, and live RET accesses'))
            print(f'PASS decimal original preflight: {len(cases)} cases, '
                  f'{len(sites)} sites, {len(edges)} actual edges', flush=True)
        else:
            if not args.build_dir:
                raise SystemExit('native worker requires --build-dir')
            native_worker(Path(args.build_dir), before)
        return
    if args.build_dir or args.hash_file:
        raise SystemExit('worker arguments require --worker')

    BUILD.mkdir(exist_ok=True)
    from bounded_process import run_bounded
    if args.original_only:
        preflight = BUILD / 'decimal-field-original-preflight.json'
        preflight.unlink(missing_ok=True)
        with temporary_build_directory(prefix='decimal-field-original-', parent=BUILD) as directory:
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', '--hash-file', str(hash_path)],
                        cwd=ROOT, timeout=240, memory_mib=384, check=True)
        return

    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='decimal-field-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     '--build-dir', directory, '--hash-file', str(hash_path)],
                    cwd=ROOT, timeout=240, memory_mib=384, check=True)


if __name__ == '__main__':
    main()
