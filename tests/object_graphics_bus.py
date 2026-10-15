"""Bounded bus-aware checks for the live 378A graphics-record copy core."""
import ctypes
import copy
import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import object_graphics as fixtures
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x


MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAX_BUS_EVENTS = 50_000
MAX_ORIGINAL_INSTRUCTIONS = 100_000
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87
RESULT_FIELDS = ('value', 'definition_cursor', 'count', 'product_high',
                 'source_cursor', 'output_cursor', 'extra_segment',
                 'stack_offset', 'flags')
DEFINED_FLAGS = 0x0FD7
AND_PHASE_MASK = DEFINED_FLAGS & ~0x0010
DF = 0x0400
VGA_SIZE = VGA_END - VGA_BASE


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in RESULT_FIELDS]


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
    """Fixture, provider or finite-access guard failed."""


class GuardExhaustion(VerificationFailure):
    """A trace or model bound was exhausted; this is never a mutant hit."""


class Mismatch(AssertionError):
    """A completed native/reference comparison differs."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MEMORY_MASK


def configure_vga(memory, seed, read_plane=1, write_mask=0x05):
    device = MinimapVga(seed, read_map=read_plane)
    aperture = memory[VGA_BASE:VGA_BASE + VGA_SIZE]
    device.planes = [bytearray(aperture) for _ in range(4)]
    device.seq[2] = write_mask & 0x0F
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[4] = read_plane & 3
    device.gc[5] = 0
    device.gc[8] = 0xFF
    return device


def device_snapshot(device):
    if device is None:
        return None
    if isinstance(device, MinimapVga):
        return device.state()
    return device.snapshot()


class CallbackBus:
    """CTypes bus with a hard callback cap and process-level failure exits."""
    def __init__(self, memory, device=None):
        self.memory = memory
        self.device = device
        self.events = []

        def reserve(label):
            if len(self.events) >= MAX_BUS_EVENTS:
                worker_exit(NATIVE_GUARD_EXIT,
                            f'{label}: native bus-event cap exhausted')

        def read(_context, _memory, address, flags):
            try:
                address &= MEMORY_MASK
                reserve('read')
                value = (self.device.read(self.memory, address, flags) if self.device
                         else self.memory[address])
                self.events.append(('read', address, value, flags & 0xFFFF))
                if self.device and len(getattr(self.device, 'trace', ())) > MAX_BUS_EVENTS:
                    worker_exit(NATIVE_GUARD_EXIT,
                                'native VGA trace cap exhausted')
                return value
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                            f'native read callback failed: {type(error).__name__}: {error}')
                return 0

        def write(_context, _memory, address, value, flags):
            try:
                address &= MEMORY_MASK
                value &= 0xFF
                reserve('write')
                if self.device:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xFFFF))
                if self.device and len(getattr(self.device, 'trace', ())) > MAX_BUS_EVENTS:
                    worker_exit(NATIVE_GUARD_EXIT,
                                'native VGA trace cap exhausted')
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                            f'native write callback failed: {type(error).__name__}: {error}')

        self._read = READ(read)
        self._write = WRITE(write)
        self._out = OUT()
        self.bus = RasterBus(None, self._read, self._write, self._out)


def result_tuple(result):
    return tuple(getattr(result, field) for field in RESULT_FIELDS)


def compare_bus_events(actual, expected, case_name):
    require(len(actual) == len(expected),
            f'{case_name}: bus event count differs')
    for index, (got, wanted) in enumerate(zip(actual, expected)):
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags, flag_mask = wanted
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
                f'{case_name}: bus event {index} differs')
        require(((flags ^ exp_flags) & flag_mask) == 0,
                f'{case_name}: defined callback flags differ at event {index}: '
                f'{flags:04x} vs {exp_flags:04x} mask={flag_mask:04x}; '
                f'got={got!r} expected={wanted!r}')


def callback_flag_mask(instruction_offset):
    if instruction_offset in (0x37A4, 0x37A7, 0x37AA, 0x37AB, 0x37AC):
        return AND_PHASE_MASK
    return 0xFFFF


class OriginalRun:
    """Bounded Unicorn execution of the pinned interval with bus hooks."""
    def __init__(self, case, memory, regs, flags, device=None):
        self.case = case
        self.memory = memory
        self.regs_in = regs
        self.flags_in = flags
        self.device = device
        self.events = []
        self.sites = set()
        self.edges = set()
        self.previous = None
        self.current_offset = None
        self.current_flags = 0
        self.rep_flags = None
        self.steps = 0
        self.stopped_after_ret = False
        self.ret_target = None
        self.boundary = None
        self.rep_probes = []
        self.current_rep_probe = None
        self.failure = None
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 1 << 21)
        initial = bytes(memory)
        self.uc.mem_write(0, initial)
        self.uc.mem_write(MEMORY_SIZE, initial)
        for name, register in fixtures.oracle.REG.items():
            self.uc.reg_write(register, regs[name])
        self.uc.reg_write(x.UC_X86_REG_EFLAGS, flags)

        def fail(uc, message, guard=False):
            if self.failure is None:
                self.failure = (guard, message)
            uc.emu_stop()

        def record(kind, p, value, current_flags):
            if len(self.events) >= MAX_BUS_EVENTS:
                fail(self.uc, f'{case["name"]}: original bus-event cap exhausted', True)
                return
            self.events.append((kind, p, value & 0xFF, current_flags & 0xFFFF,
                                callback_flag_mask(self.current_offset)))

        def mirrors(uc, address, p, value):
            byte = bytes((value & 0xFF,))
            for location in (address, p, p + MEMORY_SIZE):
                if 0 <= location < (1 << 21):
                    uc.mem_write(location, byte)

        def code(uc, address, size, _context):
            cs = uc.reg_read(fixtures.oracle.REG['cs'])
            off = (address - (cs << 4)) & 0xFFFF
            repeated_rep = off == 0x37B4 and self.current_offset == off
            raw_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.current_offset = off
            if off == 0x37B4:
                if not repeated_rep:
                    self.rep_flags = raw_flags
                    self.current_rep_probe = dict(
                        entry_flags=raw_flags, repeated_codehook_flags=None,
                        memory_hook_flags=[], first_pop_flags=None,
                        first_pop_event_flags=None)
                    if len(self.rep_probes) < 2:
                        self.rep_probes.append(self.current_rep_probe)
                elif (self.current_rep_probe is not None and
                      self.current_rep_probe['repeated_codehook_flags'] is None):
                    self.current_rep_probe['repeated_codehook_flags'] = raw_flags
                self.current_flags = self.rep_flags
            elif off == 0x37B6 and self.current_rep_probe is not None:
                self.current_rep_probe['first_pop_flags'] = raw_flags
                self.current_flags = self.rep_flags
            elif off in (0x37B6, 0x37B7, 0x37B8) and self.rep_flags is not None:
                self.current_flags = self.rep_flags
            else:
                self.current_flags = raw_flags
            if self.previous == fixtures.RET:
                self.ret_target = off
                self.stopped_after_ret = True
                uc.emu_stop()
                return
            if self.previous in fixtures.BRANCHES:
                self.edges.add((self.previous, off))
            if off == fixtures.RET:
                if cs != regs['cs']:
                    fail(uc, f'{case["name"]}: CS changed before near RET')
                    return
                self.sites.add(off)
                self.steps += 1
                if self.steps > MAX_ORIGINAL_INSTRUCTIONS:
                    fail(uc, f'{case["name"]}: original instruction budget exhausted', True)
                    return
                registers = {name: uc.reg_read(register)
                             for name, register in fixtures.oracle.REG.items()}
                self.boundary = dict(memory=bytes(self.memory),
                    registers=registers, flags=self.current_flags,
                    event_count=len(self.events), device=copy.deepcopy(self.device))
                self.previous = off
                return
            if cs != regs['cs'] or off not in fixtures.INS:
                fail(uc, f'{case["name"]}: original escaped at {off:04x}')
                return
            self.steps += 1
            if self.steps > MAX_ORIGINAL_INSTRUCTIONS:
                fail(uc, f'{case["name"]}: original instruction budget exhausted', True)
                return
            self.sites.add(off)
            self.previous = off

        def memory_read(uc, access, address, size, _value, _context):
            raw_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            current_flags = self.current_flags
            if (self.current_offset == 0x37B4 and self.current_rep_probe is not None and
                    len(self.current_rep_probe['memory_hook_flags']) < 4):
                self.current_rep_probe['memory_hook_flags'].append(
                    ('read', raw_flags, current_flags))
            if (self.current_offset == 0x37B6 and self.current_rep_probe is not None and
                    self.current_rep_probe['first_pop_event_flags'] is None):
                self.current_rep_probe['first_pop_event_flags'] = current_flags
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < (1 << 21):
                        fail(uc, f'{case["name"]}: original read escaped mapped memory')
                        return
                    p = linear & MEMORY_MASK
                    if device and VGA_BASE <= p < VGA_END:
                        value = device.read(memory, p, current_flags)
                        if len(device.trace) > MAX_BUS_EVENTS:
                            fail(uc, f'{case["name"]}: original VGA trace cap exhausted', True)
                            return
                    else:
                        value = memory[p]
                    record('read', p, value, current_flags)
                    if self.failure:
                        return
                    mirrors(uc, linear, p, value)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original read provider failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, access, address, size, value, _context):
            raw_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            current_flags = self.current_flags
            if (self.current_offset == 0x37B4 and self.current_rep_probe is not None and
                    len(self.current_rep_probe['memory_hook_flags']) < 4):
                self.current_rep_probe['memory_hook_flags'].append(
                    ('write', raw_flags, current_flags))
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < (1 << 21):
                        fail(uc, f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MEMORY_MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if device and VGA_BASE <= p < VGA_END:
                        device.write(memory, p, byte, current_flags)
                        if len(device.trace) > MAX_BUS_EVENTS:
                            fail(uc, f'{case["name"]}: original VGA trace cap exhausted', True)
                            return
                    else:
                        memory[p] = byte
                    record('write', p, byte, current_flags)
                    if self.failure:
                        return
                    mirrors(uc, linear, p, byte)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original write provider failed: '
                     f'{type(error).__name__}: {error}')

        def interrupt(uc, number, _context):
            fail(uc, f'{case["name"]}: unexpected original INT{number:02x}')

        self._callbacks = (code, memory_read, memory_write, interrupt)
        self.uc.hook_add(UC_HOOK_CODE, code)
        self.uc.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, memory_write)
        self.uc.hook_add(UC_HOOK_INTR, interrupt)

    def run(self):
        try:
            self.uc.emu_start(physical(self.regs_in['cs'], fixtures.ENTRY),
                              0, count=MAX_ORIGINAL_INSTRUCTIONS)
        except BaseException as error:
            raise VerificationFailure(
                f'{self.case["name"]}: bounded Unicorn execution failed: {error}')
        if self.failure:
            guard, message = self.failure
            if guard:
                raise GuardExhaustion(message)
            raise VerificationFailure(message)
        if not self.stopped_after_ret or self.boundary is None:
            raise GuardExhaustion(
                f'{self.case["name"]}: original did not execute near RET and stop '
                f'before its target within '
                f'{MAX_ORIGINAL_INSTRUCTIONS} instructions')
        memory_after = bytes(self.uc.mem_read(0, MEMORY_SIZE))
        if memory_after != bytes(self.memory):
            raise VerificationFailure(
                f'{self.case["name"]}: Unicorn aperture/mirror memory did not reconcile')
        registers = {name: self.uc.reg_read(register)
                     for name, register in fixtures.oracle.REG.items()}
        return dict(memory=memory_after, registers=registers,
                    flags=self.uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF,
                    events=self.events, sites=self.sites, edges=self.edges,
                    device=self.device, boundary=self.boundary,
                    ret_target=self.ret_target, rep_probes=self.rep_probes)


def independent_vga_planes(case, device, flags):
    planes = [bytearray(plane) for plane in device.planes]
    read_plane = device.gc[4] & 3
    step = -1 if flags & DF else 1
    for index, object_type in case.get('definitions', ()):
        source = (fixtures.GROUND + ((object_type * 28) & 0xFFFF)) & 0xFFFF
        destination = (fixtures.GRAPHICS + 28 * index) & 0xFFFF
        for _ in range(28):
            value = device.planes[read_plane][source]
            for plane in (0, 2):
                planes[plane][destination] = value
            source = (source + step) & 0xFFFF
            destination = (destination + step) & 0xFFFF
    return tuple(bytes(plane) for plane in planes)


def compare_native_to_original(lib, case, memory, regs, flags, device=None):
    original_memory = bytearray(memory)
    original_device = copy.deepcopy(device)
    original = OriginalRun(case, original_memory, regs, flags,
                           original_device).run()

    native_memory = bytearray(memory)
    native_device = copy.deepcopy(device)
    callbacks = CallbackBus(native_memory, native_device)
    result = native_core(lib, True, native_memory, regs, flags, callbacks)
    state = dict(zip(RESULT_FIELDS, result_tuple(result)))
    native_registers = dict(regs)
    native_registers.update(ax=state['value'], bx=state['definition_cursor'],
        cx=state['count'], dx=state['product_high'], si=state['source_cursor'],
        di=state['output_cursor'], es=state['extra_segment'],
        sp=state['stack_offset'])

    boundary = original['boundary']
    for name in fixtures.oracle.REG_NAMES:
        if name == 'ip':
            require(boundary['registers'][name] == fixtures.RET,
                    f"{case['name']}: near RET boundary IP differs")
            continue
        require(boundary['registers'][name] == native_registers[name],
                f"{case['name']}: {name} native/original register differs")
    require(((result.flags ^ boundary['flags']) & DEFINED_FLAGS) == 0,
            f"{case['name']}: defined final flags differ")
    require(native_memory == boundary['memory'],
            f"{case['name']}: full canonical RAM differs")
    core_events = original['events'][:boundary['event_count']]
    compare_bus_events(callbacks.events, core_events, case['name'])
    if device:
        require(device_snapshot(native_device) == device_snapshot(boundary['device']),
                f"{case['name']}: original/native VGA device state differs")
        if case.get('definitions'):
            expected_planes = independent_vga_planes(case, device, flags)
            require(device_snapshot(native_device)[0] == expected_planes,
                    f"{case['name']}: VGA planes differ from independent copy vectors")
    return dict(events=len(callbacks.events), sites=original['sites'],
                edges=original['edges'], memory=boundary['memory'],
                rep_probes=original['rep_probes'],
                ret_target=original['ret_target'])


def load_library(directory, mutation):
    path = Path(directory) / f'object-graphics-bus-m{mutation}.dll'
    lib = ctypes.CDLL(str(path))
    lib.lmn_copy_object_graphics_core.argtypes = [MEM] + [ctypes.c_uint16] * 5
    lib.lmn_copy_object_graphics_core.restype = Result
    lib.lmn_copy_object_graphics_bus_core.argtypes = [MEM] + [ctypes.c_uint16] * 5 + [ctypes.POINTER(RasterBus)]
    lib.lmn_copy_object_graphics_bus_core.restype = Result
    lib.lmn_copy_object_graphics_adapter.argtypes = [MEM, ctypes.POINTER(Regs)]
    lib.lmn_copy_object_graphics_adapter.restype = None
    lib.lmn_copy_object_graphics_bus_adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_copy_object_graphics_bus_adapter.restype = None
    return lib


def native_core(lib, bus_aware, memory, regs, flags, callbacks=None):
    view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)
    if bus_aware:
        bus = ctypes.byref(callbacks.bus) if callbacks else None
        result = lib.lmn_copy_object_graphics_bus_core(
            view, regs['ds'], regs['ss'], regs['sp'], regs['dx'], flags, bus)
    else:
        result = lib.lmn_copy_object_graphics_core(
            view, regs['ds'], regs['ss'], regs['sp'], regs['dx'], flags)
    return result


def compare_null_abi(old_lib, new_lib, case, memory, regs, flags):
    old_memory = bytearray(memory)
    new_memory = bytearray(memory)
    old_result = native_core(old_lib, False, old_memory, regs, flags)
    new_result = native_core(new_lib, True, new_memory, regs, flags)
    require(result_tuple(old_result) == result_tuple(new_result),
            f"{case['name']}: null-bus core ABI changed")
    require(old_memory == new_memory,
            f"{case['name']}: null-bus core RAM changed")

    old_memory = bytearray(memory)
    new_memory = bytearray(memory)
    old_regs = Regs(**regs, flags=flags)
    new_regs = Regs(**regs, flags=flags)
    old_view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(old_memory)
    new_view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(new_memory)
    old_lib.lmn_copy_object_graphics_adapter(old_view, ctypes.byref(old_regs))
    new_lib.lmn_copy_object_graphics_bus_adapter(new_view, ctypes.byref(new_regs), None)
    require(bytes(old_regs) == bytes(new_regs),
            f"{case['name']}: null-bus adapter registers changed")
    require(old_memory == new_memory,
            f"{case['name']}: null-bus adapter RAM changed")


def make_vga_es_fixture():
    case = dict(name='provider-pop-es-and-ret-readback', seed=0x661,
                definitions=((0, 0),), ds=0x7500, ss=0xA000, sp=0x8000)
    memory, regs, flags = fixtures.prepare(case)
    device = configure_vga(memory, case['seed'], read_plane=1, write_mask=0x01)
    device.planes[1][0x7FFE] = 0x00
    device.planes[1][0x7FFF] = 0x70  # Initial POP ES returns 7000.
    device.planes[1][0x7FFC] = 0x01  # Saved CX=1 ends the 32-record LOOP early.
    device.planes[1][0x7FFD] = 0x00
    device.planes[1][0x7FFA] = 0xCB  # Saved DI=17CB.
    device.planes[1][0x7FFB] = 0x17
    device.planes[1][0x8000] = 0x00  # Adapter RET reads ED00 through the bus.
    device.planes[1][0x8001] = 0xED
    return case, memory, regs, flags, device


def run_adapter_fixture(lib, case, memory, regs, flags, device):
    original_memory = bytearray(memory)
    original_device = copy.deepcopy(device)
    original = OriginalRun(case, original_memory, regs, flags,
                           original_device).run()
    expected_memory = bytearray(original['memory'])
    expected_device = original['device']

    native_memory = bytearray(memory)
    native_device = copy.deepcopy(device)
    callbacks = CallbackBus(native_memory, native_device)
    native_regs = Regs(**regs, flags=flags)
    view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(native_memory)
    lib.lmn_copy_object_graphics_bus_adapter(
        view, ctypes.byref(native_regs), ctypes.byref(callbacks.bus))
    got_regs = {name: getattr(native_regs, name)
                for name in fixtures.oracle.REG_NAMES + ('flags',)}
    expected_registers = dict(original['registers'])
    expected_registers['flags'] = original['flags']
    for name in fixtures.oracle.REG_NAMES:
        require(got_regs[name] == expected_registers[name],
                f"{case['name']}: adapter {name} differs from original+near-RET")
    require(((got_regs['flags'] ^ expected_registers['flags']) & DEFINED_FLAGS) == 0,
            f"{case['name']}: adapter defined flags differ")
    require(native_memory == expected_memory,
            f"{case['name']}: adapter full canonical RAM differs from original+near-RET")
    compare_bus_events(callbacks.events, original['events'], case['name'])
    require(device_snapshot(native_device) == device_snapshot(expected_device),
            f"{case['name']}: adapter VGA device state differs from original+near-RET")
    require(native_device.planes[1] == device.planes[1],
            f"{case['name']}: adapter altered provider read-map plane 1")
    for offset, value in ((0x7FFE, 0x4B), (0x7FFF, 0x1B),
                          (0x7FFC, 0x20), (0x7FFD, 0x00),
                          (0x7FFA, 0xCB), (0x7FFB, 0x17)):
        require(native_device.planes[0][offset] == value,
                f"{case['name']}: expected live push byte at plane0:{offset:04x}")
    expected_copy = bytes(memory[physical(regs['ds'], fixtures.GROUND + n)]
                          for n in range(28))
    got_copy = bytes(native_memory[physical(0x7000, 0x17CB + n)]
                     for n in range(28))
    require(got_copy == expected_copy,
            f"{case['name']}: ES=7000 output differs from independent source bytes")
    require(native_regs.es == 0x7000 and native_regs.ip == 0xED00 and
            original['ret_target'] == 0xED00,
            f"{case['name']}: actual near-RET provider readback was not preserved")
    return dict(events=len(callbacks.events), sites=original['sites'],
                edges=original['edges'], memory=original['memory'],
                ret_target=original['ret_target'])


def run_worker(directory):
    baseline = fixtures.cases()
    old_lib = load_library(directory, 0)
    bus_lib = load_library(directory, 0)
    cases_report = []
    total_events = 0
    observed_sites = set()
    observed_edges = set()
    for case in baseline:
        memory, regs, flags = fixtures.prepare(case)
        compare_null_abi(old_lib, bus_lib, case, memory, regs, flags)
        result = compare_native_to_original(bus_lib, case, memory, regs, flags)
        total_events += result['events']
        observed_sites.update(result['sites'])
        observed_edges.update(result['edges'])
        if not case.get('stack_alias'):
            expected = fixtures.expected_copy_region(memory, case, regs, flags)
            start = fixtures.GRAPHICS - 0x1B
            end = fixtures.GRAPHICS + 32 * 28
            for offset in range(start, end):
                address = physical(regs['ds'], offset)
                require(result['memory'][address] == expected[address],
                        f"{case['name']}: independent copy bytes differ at DS:{offset:04x}")
        cases_report.append(dict(name=case['name'], event_count=result['events'],
                                 observed_site_count=len(result['sites']),
                                 observed_edge_count=len(result['edges']),
                                 real_level=bool(case.get('real')),
                                 near_ret_target=result['ret_target'],
                                 df=bool(flags & DF),
                                 rep_flag_probe=(result['rep_probes']
                                     if case['name'] in ('all-active-forward',
                                                         'all-active-backward')
                                     else None)))
        if case['name'] in ('all-active-forward', 'all-active-backward'):
            probes = result['rep_probes']
            require(len(probes) >= 2,
                    f"{case['name']}: missing AF0/AF1 original REP probes")
            require((probes[0]['entry_flags'] & 0x10) == 0 and
                    (probes[1]['entry_flags'] & 0x10) != 0,
                    f"{case['name']}: original REP probes do not cover AF=0/AF=1")
            for probe in probes:
                require(probe['repeated_codehook_flags'] is not None and
                        len(probe['memory_hook_flags']) == 4 and
                        probe['first_pop_flags'] is not None and
                        probe['first_pop_event_flags'] is not None,
                        f"{case['name']}: incomplete original REP/POP flag diagnostic")
                entry = probe['entry_flags']
                require(all(event[2] == entry
                            for event in probe['memory_hook_flags']) and
                        probe['first_pop_event_flags'] == entry,
                        f"{case['name']}: instruction-entry bus flags changed across REP")
                require(not (probe['repeated_codehook_flags'] & 0x10) and
                        all(not (event[1] & 0x10)
                            for event in probe['memory_hook_flags']) and
                        not (probe['first_pop_flags'] & 0x10),
                        f"{case['name']}: Unicorn REP AF instrumentation changed")

    extra_cases = [
        dict(name='indexed-vga-source-destination-forward', seed=0x701,
             definitions=tuple((i, i % 8) for i in range(8)), ds=0xA000),
        dict(name='indexed-vga-source-destination-backward', seed=0x702,
             definitions=tuple((i, (i * 3) % 8) for i in range(8)),
             ds=0xA000, df=True),
    ]
    for case in extra_cases:
        memory, regs, flags = fixtures.prepare(case)
        device = configure_vga(memory, case['seed'], read_plane=1,
                               write_mask=0x05)
        result = compare_native_to_original(bus_lib, case, memory, regs,
                                            flags, device)
        total_events += result['events']
        observed_sites.update(result['sites'])
        observed_edges.update(result['edges'])
        cases_report.append(dict(name=case['name'], event_count=result['events'],
                                 observed_site_count=len(result['sites']),
                                 observed_edge_count=len(result['edges']),
                                 near_ret_target=result['ret_target'],
                                 device='mode-0 indexed VGA source/destination',
                                 df=bool(flags & DF)))

    adapter_case, memory, regs, flags, device = make_vga_es_fixture()
    adapter_result = run_adapter_fixture(bus_lib, adapter_case, memory,
                                         regs, flags, device)
    total_events += adapter_result['events']
    observed_sites.update(adapter_result['sites'])
    observed_edges.update(adapter_result['edges'])
    cases_report.append(dict(name=adapter_case['name'],
        event_count=adapter_result['events'],
        observed_site_count=len(adapter_result['sites']),
        observed_edge_count=len(adapter_result['edges']),
        near_ret_target=adapter_result['ret_target'],
        device='SS=A000 read-map/write-map split',
        es=0x7000, ret=0xED00))

    mutation_fixtures = {
        1: next(case for case in baseline if case['name'] == 'all-inactive'),
        2: next(case for case in baseline if case['name'] == 'type-ffff'),
        3: next(case for case in baseline if case['name'] == 'all-active-backward'),
    }
    mutations = []
    for mutation, case in mutation_fixtures.items():
        memory, regs, flags = fixtures.prepare(case)
        mutant = load_library(directory, mutation)
        try:
            compare_native_to_original(mutant, case, memory, regs, flags)
        except Mismatch:
            mutations.append(dict(mutation=mutation, case=case['name']))
        else:
            raise AssertionError(f'Compiled mutation {mutation} survived')

    assets = tuple(f'assets/level{n:03d}.dat' for n in range(10)) + tuple(
        f'assets/ground{n}o.dat' for n in range(5))
    paths = ('c/object_graphics.c', 'c/object_graphics.h', 'c/special_blit.h',
        'c/regs.h', 'c/lemmings_sym.h', 'tests/object_graphics_bus.py',
        'docs/object-graphics-bus.md', 'tests/object_graphics.py',
        'tests/minimap_vga.py',
        'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/resources.py', 'tools/unpack.py', 'metadata/symbols.json',
        'metadata/inputs.json', 'assets/vgalemmi.exe') + assets
    expected_edges = {tuple(edge) for edge in fixtures.EDGES}
    require(observed_edges == expected_edges,
            f'original execution edge coverage differs: observed={sorted(observed_edges)}, '
            f'expected={sorted(expected_edges)}')
    expected_sites = set(fixtures.INS)
    require(observed_sites == expected_sites,
            f'original execution site coverage differs: observed={sorted(observed_sites)}, '
            f'expected={sorted(expected_sites)}')
    edges = sorted([list(edge) for edge in observed_edges])
    site_addresses = sorted(observed_sites)
    write_json(BUILD / 'object-graphics-bus-differential.json', dict(
        image='main', image_sha256=fixtures.sha(fixtures.IMAGE),
        case_count=len(cases_report), case_count_previous=len(baseline),
        mutation_count=len(mutations), mutations_detected=mutations,
        cases=cases_report, total_bus_events=total_events,
        translated_code_bytes=sum(i.size for i in fixtures.INS.values()),
        original_instruction_sites=site_addresses, branch_edges=edges,
        original_observed_instruction_sites=site_addresses,
        original_observed_branch_edges=edges,
        original_core_instruction_sites=sorted(observed_sites - {fixtures.RET}),
        original_ret_executed=True,
        stop_point='code hook at near-RET target, before target instruction executes',
        routine=dict(name=fixtures.ROUTINE['symbol_name'],
                     start=fixtures.ENTRY, end=fixtures.END),
        fixture_domains=dict(null_bus_core_and_adapter_abi=True,
            original_fixture_matrix=True, real_level_sections=80,
            incoming_df=['clear', 'set'], physical_and_effective_address_wrap=True,
            live_saved_cursor_count_and_return_aliases=True,
            indexed_vga_source_and_destination=True,
            ss_a000_provider_es_and_ret_readback=True,
            max_native_bus_events=MAX_BUS_EVENTS),
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        domain=('Bus-aware C11 core and adapter for bounded CS:378A..37C1; '
            'live canonical RAM and SS aliases, bus-visible PUSH/POP/RET, '
            'separate big-endian byte reads, fullword physical high-byte wrap, '
            'incoming DF, per-instruction callback flags, and four-plane source/destination access')))
    print(f'PASS object graphics bus C: {len(cases_report)} cases, '
          f'{total_events} bus events, 80 real LEVEL sections, '
          f'{len(mutations)} compiled mutations detected')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        run_worker(sys.argv[2])
        return
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'object-graphics-bus-differential.json').unlink(missing_ok=True)
    with temporary_build_directory(prefix='object-graphics-bus-', parent=BUILD) as directory:
        for mutation in range(4):
            build(Path(directory) / f'object-graphics-bus-m{mutation}.dll',
                  mutation, 'object_graphics')
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', directory], cwd=ROOT, timeout=180,
                    memory_mib=512)


if __name__ == '__main__':
    main()
