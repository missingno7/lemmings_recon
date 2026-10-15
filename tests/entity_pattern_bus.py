"""Bounded bus/device differential checks for the 283B entity-pattern leaf."""
from __future__ import annotations

import copy
import ctypes
import gc
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
import entity_pattern as fixtures
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x


SIZE = 1 << 20
MASK = SIZE - 1
ENTRY, RET, END = fixtures.ENTRY, fixtures.RET, fixtures.END
LOAD = fixtures.LOAD
CODE = fixtures.CODE
REGS = fixtures.REGS
REG_ID = fixtures.REG_ID
DEFINED_FLAGS = 0x0FD7
SHR_FLAGS = DEFINED_FLAGS & ~0x0010  # AF is undefined by SHR.
MUL_FLAGS = (DEFINED_FLAGS & ~0x08D5) | 0x0801  # Keep CF/OF and untouched flags.
EVENT_CAP = 96
INSTRUCTION_CAP = 100
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-pattern-bus-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {instruction.address: instruction
       for instruction in MD.disasm(CODE, ENTRY)}
BRANCHES = {address for address, instruction in INS.items()
            if instruction.group(capstone.CS_GRP_JUMP)}

READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """A completed native execution differs from completed original execution."""


class OracleFailure(AssertionError):
    """The pinned original or a hard harness contract failed to complete."""


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


def mirror(memory, cpu, linear, address, value):
    byte = bytes((value & 0xFF,))
    for at in (linear, address & MASK, (address & MASK) + SIZE):
        if 0 <= at < 2 * SIZE:
            cpu.mem_write(at, byte)
    memory[address & MASK] = value & 0xFF


def selected_cases():
    old = {case['name']: case for case in fixtures.cases()}
    names = (
        'geometric-known', 'x-underflow', 'high-coordinate-wrap',
        'low-word-product-wrap', 'source-offset-wrap',
        'physical-source-word-wrap', 'physical-destination-word-wrap',
        'df-clear', 'df-set', 'stack-sp-ffff', 'physical-stack-wrap',
        'coordinates-before-push', 'saved-es-alias', 'saved-di-alias',
        'saved-si-alias', 'ret-overwrite', 'physical-ret-overwrite',
        'sequential-source-destination-overlap', 'ds-ss-last-push-source',
    )
    cases = [dict(old[name]) for name in names]
    cases.extend((
        dict(name='provider-next-pattern-byte', seed=0xB501,
             ds=0x3100, ss=0x5200, si=0x1100, sp=0x8200,
             x=0x0004, y=0x0016, provider='next-pattern-byte'),
        dict(name='provider-live-dx-save', seed=0xB502,
             ds=0x3200, ss=0x5300, si=0x1200, sp=0x8300,
             x=0x0004, y=0x0016, provider='live-dx-save'),
        dict(name='provider-live-push-ss-es', seed=0xB503,
             ds=0x3300, ss=0x5400, si=0x1300, sp=0x8400,
             x=0x0004, y=0x0016, provider='live-push-ss-es'),
        dict(name='flags-write-phase', seed=0xB504,
             ds=0x3400, ss=0x5500, si=0x1400, sp=0x8500,
             x=0x0004, y=0x0016, flags=0x0202),
        dict(name='vga-destination', seed=0xB505,
             ds=0x3500, ss=0xA000, si=0x1500, sp=0x8000,
             x=0x0004, y=0x0016, vga='destination'),
        dict(name='vga-pattern-source', seed=0xB506,
             ds=0xA000, ss=0x5600, si=0x1600, sp=0x8600,
             x=0x0004, y=0x0016, vga='source', read_map=2),
        dict(name='vga-source-destination-overlap', seed=0xB507,
             ds=0xA000, ss=0xA000, si=0x0000, sp=0x7000,
             x=0x0014, y=0x0016, vga='source-destination', read_map=1),
        dict(name='seeded-df-wrap-0', seed=0xB508,
             ds=0x5700, ss=0x6200, si=0xFFF8, sp=0x0001,
             x=0xFA78, y=0x01F2, df=True),
        dict(name='seeded-independent-1', seed=0xB509,
             ds=0x5800, ss=0x6300, si=0x1FF0, sp=0xFFFE,
             x=0x7FFD, y=0x800F, df=False),
    ))
    oracle_require(24 <= len(cases) <= 30,
                   f'Entity pattern bus fixture count changed: {len(cases)}')
    oracle_require(len({case['name'] for case in cases}) == len(cases),
                   'Entity pattern bus fixture names are not unique')
    return cases


def provider_effects(case, regs):
    provider = case.get('provider')
    ds, ss, si, sp = regs['ds'], regs['ss'], regs['si'], regs['sp']
    if provider == 'next-pattern-byte':
        return [('read', physical(ds, (si + 0x18) & 0xFFFF),
                 physical(ds, (si + 0x19) & 0xFFFF), b'\xE7')]
    if provider == 'live-dx-save':
        slot = (sp - 4) & 0xFFFF
        return [('write', physical(ss, (slot + 1) & 0xFFFF),
                 physical(ss, slot), b'\xA9')]
    if provider == 'live-push-ss-es':
        slot = (sp - 8) & 0xFFFF
        return [('write', physical(ss, (slot + 1) & 0xFFFF),
                 physical(ss, slot), b'\x01')]
    return []


def put_plane_byte(device, offset, value, plane):
    if 0 <= offset < 0x10000:
        device.planes[plane][offset] = value & 0xFF


def setup_device(case, memory, regs, pattern):
    if not case.get('vga'):
        return None
    read_map = case.get('read_map', 0)
    device = MinimapVga(0x283B + case['seed'], read_map=read_map)
    device.seq[2] = 0x0F
    device.seq[4] = 0x06
    device.gc[0] = device.gc[1] = device.gc[2] = device.gc[3] = 0
    device.gc[4] = read_map
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[7] = 0
    device.gc[8] = 0xFF

    if case['vga'] in ('source', 'source-destination'):
        ds, si = regs['ds'], regs['si']
        xcoord, ycoord = case.get('x', 4), case.get('y', 22)
        for index, byte in enumerate((xcoord & 0xFF, xcoord >> 8,
                                      ycoord & 0xFF, ycoord >> 8)):
            offset = physical(ds, (si + index) & 0xFFFF) - VGA_BASE
            put_plane_byte(device, offset, byte, read_map)
        source = (si + 0x16) & 0xFFFF
        for index, byte in enumerate(pattern):
            offset = physical(ds, (source + index) & 0xFFFF) - VGA_BASE
            put_plane_byte(device, offset, byte, read_map)

    if regs['ss'] == 0xA000:
        # The CPU consumes the VGA-backed live RET word after the row writes.
        sp_address = physical(regs['ss'], regs['sp']) - VGA_BASE
        ret_word = fixtures.getword(memory, regs['ss'], regs['sp'])
        put_plane_byte(device, sp_address, ret_word & 0xFF, read_map)
        put_plane_byte(device, sp_address + 1, ret_word >> 8, read_map)
    return device


def prepare(case):
    memory, regs, pattern = fixtures.prepare(case)
    if 'flags' in case:
        flags = case['flags'] & DEFINED_FLAGS
        flags |= 2
        flags &= ~0x0100  # Keep the declared quiescent, trap-clear boundary.
        if case.get('df', False):
            flags |= 0x0400
        elif case.get('df') is False:
            flags &= ~0x0400
        regs['flags'] = flags
    device = setup_device(case, memory, regs, pattern)
    return memory, regs, pattern, device


def flag_mask_for_site(site):
    if site in (0x2851, 0x2852):
        return SHR_FLAGS
    if site in (0x285A, 0x285B):
        return MUL_FLAGS
    return DEFINED_FLAGS


class OriginalRun:
    def __init__(self, case, memory, regs, device, *, core):
        self.case = case
        self.memory = memory
        self.regs_in = regs
        self.device = device
        self.core = core
        self.events = []
        self.sites = set()
        self.edges = set()
        self.previous = None
        self.current_site = None
        self.current_flags = 0
        self.steps = 0
        self.failure = None
        self.stopped = False
        self.ret_target = None
        self.used_effects = set()
        self.pending_effects = []
        self.effects = provider_effects(case, regs)
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * SIZE)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(SIZE, initial)
        for name in REGS:
            if name != 'flags':
                self.cpu.reg_write(REG_ID[name], regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def add_event(kind, address, value):
            if len(self.events) >= EVENT_CAP:
                fail(f'{case["name"]}: original bus trace cap exhausted')
                return
            self.events.append((kind, address & MASK, value & 0xFF,
                                self.current_flags & 0xFFFF,
                                self.current_site))

        def apply_effect(kind, address):
            for n, (trigger_kind, trigger, target, data) in enumerate(self.effects):
                if n in self.used_effects or kind != trigger_kind or address != trigger:
                    continue
                self.used_effects.add(n)
                self.pending_effects.append((target, data))

        def flush_effects(uc):
            # Unicorn's write hook reports a whole word before the CPU commits
            # it. Applying a provider update immediately could be overwritten
            # by the remaining byte(s); the modeled bus update lands after the
            # triggering instruction and before the next instruction begins.
            for target, data in self.pending_effects:
                for offset, value in enumerate(data):
                    p = (target + offset) & MASK
                    self.memory[p] = value
                    for linear in (p, p + SIZE):
                        if linear < 2 * SIZE:
                            uc.mem_write(linear, bytes((value,)))
            self.pending_effects.clear()

        def on_code(uc, _address, _size, _user):
            flush_effects(uc)
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous == RET:
                self.ret_target = off
                self.stopped = True
                uc.emu_stop()
                return
            if cs != LOAD or off not in INS:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            instruction = INS[off]
            code_address = physical(LOAD, off)
            if bytes(uc.mem_read(code_address, instruction.size)) != bytes(instruction.bytes):
                fail(f'{case["name"]}: executing pinned bytes changed at {off:04X}')
                return
            if off == RET and core:
                self.stopped = True
                uc.emu_stop()
                return
            if self.steps >= INSTRUCTION_CAP:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.steps += 1
            self.sites.add(off)
            self.current_site = off
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.previous = off

        def on_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original read escaped mapped memory')
                        return
                    p = linear & MASK
                    value = (self.device.read(self.memory, p, self.current_flags)
                             if self.device is not None and VGA_BASE <= p < VGA_END
                             else self.memory[p])
                    mirror(self.memory, uc, linear, p, value)
                    add_event('read', p, value)
                    if self.failure:
                        return
                    apply_effect('read', p)
            except BaseException as error:
                fail(f'{case["name"]}: original read provider failed: '
                     f'{type(error).__name__}: {error}')

        def on_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * SIZE:
                        fail(f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if self.device is not None:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    mirror(self.memory, uc, linear, p, byte)
                    add_event('write', p, byte)
                    if self.failure:
                        return
                    apply_effect('write', p)
            except BaseException as error:
                fail(f'{case["name"]}: original write provider failed: '
                     f'{type(error).__name__}: {error}')

        self._callbacks = (on_code, on_read, on_write)
        self.cpu.hook_add(UC_HOOK_CODE, on_code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, on_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)

    def run(self):
        try:
            self.cpu.emu_start(physical(LOAD, ENTRY), 0, count=INSTRUCTION_CAP)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original did not stop at declared boundary')
        oracle_require(not self.pending_effects,
                       f'{self.case["name"]}: provider queue was not flushed')
        oracle_require(len(self.events) <= EVENT_CAP,
                       f'{self.case["name"]}: original bus budget exhausted')
        expected_sites = set(INS) - ({RET} if self.core else set())
        oracle_require(self.sites == expected_sites,
                       f'{self.case["name"]}: original site coverage differs at boundary')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF
                 for name in REGS if name != 'flags'}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        canonical_memory = bytes(self.memory)
        actual_memory = bytes(self.cpu.mem_read(0, SIZE))
        oracle_require(actual_memory == canonical_memory,
                       f'{self.case["name"]}: original canonical RAM diverged from Unicorn RAM')
        code_physical = physical(LOAD, ENTRY)
        oracle_require(canonical_memory[code_physical:code_physical + len(CODE)] == CODE,
                       f'{self.case["name"]}: original modified executing leaf bytes')
        if self.core:
            oracle_require(state['ip'] == RET and len(self.sites) == 36,
                           f'{self.case["name"]}: core did not stop before RET')
        else:
            oracle_require(self.previous == RET and self.ret_target is not None,
                           f'{self.case["name"]}: adapter did not execute actual RET')
            oracle_require(state['sp'] == ((self.regs_in['sp'] + 2) & 0xFFFF),
                           f'{self.case["name"]}: actual RET did not consume live SS:SP')
        oracle_require(self.used_effects == set(range(len(self.effects))),
                       f'{self.case["name"]}: provider did not trigger: '
                       f'{self.used_effects!r}/{len(self.effects)}')
        return dict(memory=actual_memory, state=state,
                    events=self.events, sites=self.sites, edges=self.edges,
                    device=self.device, ret_target=self.ret_target,
                    used_effects=set(self.used_effects), steps=self.steps)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-pattern-bus-m{mutation}.dll',
                     mutation, 'entity_pattern_bus')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_copy_entity_pattern_core
        self.core.argtypes = [MEM, ctypes.POINTER(fixtures.Call)]
        self.core.restype = fixtures.CoreResult
        self.adapter = self.library.lmn_copy_entity_pattern_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs)]
        self.adapter.restype = None
        self.bus_core = self.library.lmn_copy_entity_pattern_bus_core
        self.bus_core.argtypes = [MEM, ctypes.POINTER(fixtures.Call),
                                  ctypes.POINTER(RasterBus)]
        self.bus_core.restype = fixtures.CoreResult
        self.bus_adapter = self.library.lmn_copy_entity_pattern_bus_adapter
        self.bus_adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                     ctypes.POINTER(RasterBus)]
        self.bus_adapter.restype = None


def c_buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


class NativeBus:
    def __init__(self, case, memory, device, regs):
        self.case = case
        self.memory = memory
        self.device = device
        self.effects = provider_effects(case, regs)
        self.used_effects = set()
        self.events = []

        def reserve():
            if len(self.events) >= EVENT_CAP:
                worker_exit(GUARD_EXIT,
                            f'{case["name"]}: native entity-pattern bus cap exhausted')

        def apply_effect(kind, address):
            for n, (trigger_kind, trigger, target, data) in enumerate(self.effects):
                if n in self.used_effects or kind != trigger_kind or address != trigger:
                    continue
                self.used_effects.add(n)
                for offset, byte in enumerate(data):
                    self.memory[(target + offset) & MASK] = byte

        def read(_context, _memory, address, flags):
            try:
                address &= MASK
                reserve()
                value = (self.device.read(self.memory, address, flags)
                         if self.device is not None and VGA_BASE <= address < VGA_END
                         else self.memory[address])
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                apply_effect('read', address)
                if self.device and len(self.device.trace) > EVENT_CAP:
                    worker_exit(GUARD_EXIT, 'native entity-pattern VGA trace cap exhausted')
                return value
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native pattern read callback failed: '
                            f'{type(error).__name__}: {error}')
                return 0

        def write(_context, _memory, address, value, flags):
            try:
                address &= MASK
                value &= 0xFF
                reserve()
                if self.device is not None:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                apply_effect('write', address)
                if self.device and len(self.device.trace) > EVENT_CAP:
                    worker_exit(GUARD_EXIT, 'native entity-pattern VGA trace cap exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native pattern write callback failed: '
                            f'{type(error).__name__}: {error}')

        self._read, self._write = READ(read), WRITE(write)
        self._out = OUT()
        self.bus = RasterBus(None, self._read, self._write, self._out)


def compare_state(case, actual, expected, label):
    for name in REGS:
        require(actual[name] == expected[name],
                f'{case["name"]} {label} {name} differs: '
                f'{actual[name]:04X}/{expected[name]:04X}')
    require(((actual['flags'] ^ expected['flags']) & DEFINED_FLAGS) == 0,
            f'{case["name"]} {label} defined flags differ: '
            f'{actual["flags"]:04X}/{expected["flags"]:04X}')


def compare_memory(case, actual, expected, label):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    raise Mismatch(f'{case["name"]} {label} RAM differs at {mismatch:05X}: '
                   f'{actual[mismatch]:02X}/{expected[mismatch]:02X}')


def compare_events(case, native, expected):
    require(len(native) == len(expected),
            f'{case["name"]}: bus event count differs {len(native)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(native, expected)):
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags, site = want
        require((kind, address) == (exp_kind, exp_address),
                f'{case["name"]}: bus order/address differs at {index}: {got!r}/{want!r}')
        require(value == exp_value,
                f'{case["name"]}: bus byte differs at {index}: {value:02X}/{exp_value:02X}')
        mask = flag_mask_for_site(site)
        require(((flags ^ exp_flags) & mask) == 0,
                f'{case["name"]}: callback FLAGS differ at event {index} site {site:04X}: '
                f'{flags:04X}/{exp_flags:04X} mask={mask:04X}')


def compare_device(case, actual, expected):
    if expected is None:
        require(actual is None, f'{case["name"]}: unexpected native VGA device')
        return
    require(actual is not None, f'{case["name"]}: native VGA device missing')
    require(actual.state() == expected.state(),
            f'{case["name"]}: VGA planes/latches/registers differ')
    native_trace = [tuple(event[:3]) for event in actual.trace]
    expected_trace = [tuple(event[:3]) for event in expected.trace]
    require(native_trace == expected_trace,
            f'{case["name"]}: ordered VGA read/write trace differs')


def independent_geometry(case, result, initial, pattern):
    if case['name'] != 'geometric-known':
        return
    ss = initial['ss']
    offsets = [0x12 + row * 0x1A0 + column
               for row in range(3) for column in range(3)]
    for index, offset in enumerate(offsets):
        address = physical(ss, offset)
        require(result['memory'][address] == pattern[index],
                f'geometric-known independent pattern byte {index} differs')


def compare_case(native, case, *, core):
    initial_memory, initial, pattern, initial_device = prepare(case)
    effects = provider_effects(case, initial)
    oracle_device = copy.deepcopy(initial_device)
    oracle = OriginalRun(case, bytearray(initial_memory), dict(initial),
                         oracle_device, core=core).run()

    native_memory = bytearray(initial_memory)
    native_device = copy.deepcopy(initial_device)
    callbacks = NativeBus(case, native_memory, native_device, initial)
    state = dict(initial)
    if core:
        call = fixtures.Call(state['ds'], state['ss'], state['sp'], state['si'],
                             state['di'], state['dx'], state['es'], state['flags'])
        result = native.bus_core(c_buffer(native_memory), ctypes.byref(call),
                                 ctypes.byref(callbacks.bus))
        state.update(ax=result.product, bx=result.map_offset,
                     dx=result.restored_value, si=result.record_cursor,
                     di=result.restored_destination, es=result.restored_segment,
                     sp=result.stack_offset, flags=result.flags, ip=RET)
    else:
        live = Regs(**{name: state[name] for name in REGS}, flags=state['flags'])
        native.bus_adapter(c_buffer(native_memory), ctypes.byref(live),
                           ctypes.byref(callbacks.bus))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags

    boundary = 'core' if core else 'adapter'
    compare_state(case, state, oracle['state'], boundary)
    compare_memory(case, bytes(native_memory), oracle['memory'], boundary)
    compare_device(case, native_device, oracle['device'])
    compare_events(case, callbacks.events, oracle['events'])
    require(callbacks.used_effects == oracle['used_effects'],
            f'{case["name"]}: native provider phase differs')
    oracle_require(not oracle['edges'] and not BRANCHES,
                   f'{case["name"]}: unexpected branch in linear leaf')
    if case.get('vga') == 'destination':
        oracle_require(any(kind == 'write' and VGA_BASE <= address < VGA_END
                           for kind, address, _value, _flags, _site in oracle['events']),
                       'VGA destination case did not access the aperture')
    elif case.get('vga') == 'source':
        oracle_require(any(kind == 'read' and VGA_BASE <= address < VGA_END
                           for kind, address, _value, _flags, _site in oracle['events']),
                       'VGA source case did not read the aperture')
    elif case.get('vga') == 'source-destination':
        oracle_require(any(kind == 'read' and VGA_BASE <= address < VGA_END
                           for kind, address, _value, _flags, _site in oracle['events']) and
                       any(kind == 'write' and VGA_BASE <= address < VGA_END
                           for kind, address, _value, _flags, _site in oracle['events']),
                       'VGA overlap case did not both read and write the aperture')
    independent_geometry(case, oracle, initial, pattern)
    if not core and case['name'] == 'ret-overwrite':
        expected_target = pattern[0] | (pattern[1] << 8)
        oracle_require(oracle['ret_target'] == expected_target,
                       'ret-overwrite fixture did not consume the map-written RET word')
    sites = set(oracle['sites'])
    require(sites == set(INS) - ({RET} if core else set()),
            f'{case["name"]}: executed site union changed at {boundary}')
    gc.collect()
    return sites, len(callbacks.events), oracle['ret_target']


def compare_null_bus(native, case):
    memory, regs, _pattern, _device = prepare(case)
    old_memory, new_memory = bytearray(memory), bytearray(memory)
    call = fixtures.Call(regs['ds'], regs['ss'], regs['sp'], regs['si'],
                         regs['di'], regs['dx'], regs['es'], regs['flags'])
    old = native.core(c_buffer(old_memory), ctypes.byref(call))
    new = native.bus_core(c_buffer(new_memory), ctypes.byref(call), None)
    require(bytes(old) == bytes(new),
            f'{case["name"]}: null-bus core result differs from RAM API')
    require(old_memory == new_memory,
            f'{case["name"]}: null-bus core RAM differs from RAM API')

    old_memory, new_memory = bytearray(memory), bytearray(memory)
    old_regs = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
    new_regs = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
    native.adapter(c_buffer(old_memory), ctypes.byref(old_regs))
    native.bus_adapter(c_buffer(new_memory), ctypes.byref(new_regs), None)
    require(bytes(old_regs) == bytes(new_regs),
            f'{case["name"]}: null-bus adapter registers differ from RAM API')
    require(old_memory == new_memory,
            f'{case["name"]}: null-bus adapter RAM differs from RAM API')


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/toolchain-lock.json',
        'src/game_code.asm', 'c/entity_pattern.c', 'c/entity_pattern.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'c/regs.h',
        'tests/entity_pattern.py', 'tests/entity_pattern_bus.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/bounded_process.py', 'tools/unpack.py', 'tools/common.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(sha(fixtures.ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(fixtures.IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(CODE) == 66 and len(INS) == 37 and len(BRANCHES) == 0,
                   'Entity pattern byte/site/branch accounting changed')

    specs = selected_cases()
    baseline = Native(directory)
    coverage, cases, total_events = set(), [], 0
    for case in specs:
        compare_null_bus(baseline, case)
        observed, event_count, boundaries = set(), 0, {}
        for core in (True, False):
            sites, count, ret_target = compare_case(baseline, case, core=core)
            observed.update(sites)
            event_count += count
            boundaries['core' if core else 'adapter'] = dict(
                site_count=len(sites), ret_target=ret_target)
        coverage.update(observed)
        total_events += event_count
        cases.append(dict(name=case['name'], bus_events=event_count,
                          executed_instruction_addresses=sorted(observed),
                          branch_edges=[], core_and_adapter=True,
                          provider=case.get('provider'), vga=case.get('vga'),
                          boundaries=boundaries))

    witnesses = (
        (1, 'vga-destination', True, 'bus-bypass'),
        (2, 'provider-live-push-ss-es', True, 'live-pop-es-segment'),
        (3, 'flags-write-phase', True, 'instruction-phase-flags'),
        (4, 'ret-overwrite', False, 'live-ret-after-map-write'),
    )
    mutations = []
    for mutation_id, case_name, core, label in witnesses:
        variant = Native(directory, mutation_id)
        case = next(row for row in specs if row['name'] == case_name)
        try:
            compare_case(variant, case, core=core)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation_id, name=label,
                                  case=case_name, completed=True,
                                  mismatch=str(error)))
        else:
            raise OracleFailure(f'Entity pattern bus mutant {mutation_id} survived '
                                f'its completed witness {case_name}')
        gc.collect()

    expected_sites = set(INS)
    oracle_require(coverage == expected_sites,
                   'Entity pattern bus original site coverage differs')
    oracle_require(total_events <= len(specs) * 2 * EVENT_CAP,
                   'Entity pattern bus aggregate trace unexpectedly exceeded bounds')
    oracle_require(len(cases) == len(specs) and len(mutations) == 4,
                   'Entity pattern bus report scope changed')
    after = input_hashes()
    oracle_require(before == after,
                   'Entity pattern bus inputs changed during bounded campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(fixtures.IMAGE),
        case_count=len(cases), mutation_count=len(mutations), mutations=mutations,
        cases=cases, translated_code_bytes=len(CODE),
        native_code_ranges=[[ENTRY, END]], routine_bytes=CODE.hex(),
        instruction_sites=len(coverage),
        executed_instruction_addresses=sorted(coverage), branch_edges=[],
        branch_instruction_addresses=sorted(BRANCHES), total_bus_events=total_events,
        domains=[
            'bus-aware byte reads/writes with instruction-phase FLAGS; null-bus legacy API equality',
            'VGA reads and writes through source, destination, and aliased source/destination segments',
            'live SS stack values for DX, ES, DI, SI, and the actual adapter RET',
            'provider updates between row reads and during live stack save writes',
            'DF-sensitive MOVSW/MOVSB, word read-before-write, sequential overlap, and literal row pitch',
            '16-bit offset wrap, 20-bit physical word wrap, and complete canonical RAM comparison',
            'all 36 core sites and all 37 adapter sites; this straight-line leaf has no branch edges'],
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_process_tree_mib=640,
                    original_instruction_hook_limit=INSTRUCTION_CAP,
                    native_callback_event_limit=EVENT_CAP,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=after))
    print(f'PASS entity pattern bus C: {len(cases)} cases, {total_events} events, '
          f'{len(coverage)} sites, {len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-pattern-bus-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory], cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
