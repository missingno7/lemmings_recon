"""Bounded raster-bus checks for the live 389F coordinate collector."""
import copy
import ctypes
import gc
import os
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import object_coordinates as fixtures
from bounded_process import run_bounded, temporary_build_directory
from cbuild import compiler
from common import ROOT, BUILD, sha, read_json, write_json
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x


MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAX_BUS_EVENTS = 4096
MAX_ORIGINAL_INSTRUCTIONS = 2000
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87
DEFINED_FLAGS = 0x0FD7
AF = 0x0010
DF = 0x0400
IF = 0x0200
VGA_SIZE = VGA_END - VGA_BASE
MEM = ctypes.POINTER(ctypes.c_uint8)
REPORT = BUILD / 'object-coordinates-bus-differential.json'
INPUT_PATHS = (
    'src/level_objects.asm',
    'c/object_coordinates_bus.c', 'c/object_coordinates_bus.h',
    'c/object_coordinates.c', 'c/object_coordinates.h', 'c/special_blit.h',
    'c/regs.h', 'c/lemmings_sym.h', 'tests/object_coordinates_bus.py',
    'tests/object_coordinates.py', 'tests/object_graphics_bus.py',
    'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
    'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
    'tools/resources.py', 'tools/unpack.py', 'metadata/symbols.json',
    'metadata/inputs.json', 'metadata/oracle.json', 'assets/vgalemmi.exe',
) + tuple(f'assets/level{n:03d}.dat' for n in range(10))


def local_python_import_paths():
    roots = ((ROOT / 'tests').resolve(), (ROOT / 'tools').resolve())
    found = set()
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        try:
            path = Path(filename).resolve()
        except (OSError, RuntimeError):
            continue
        if path.suffix != '.py':
            continue
        try:
            relative = path.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            continue
        if any(path.is_relative_to(root) for root in roots):
            found.add(relative)
    return found


def current_input_hashes(consumed_assets=()):
    paths = set(INPUT_PATHS) | set(consumed_assets)
    paths.update(local_python_import_paths())
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def verify_inputs_unchanged(before, consumed_assets=()):
    after = current_input_hashes(consumed_assets)
    if after != before:
        changed = sorted(path for path in (set(before) | set(after))
                         if before.get(path) != after.get(path))
        raise VerificationFailure(
            'test inputs changed during the bounded build/run: ' + ', '.join(changed))
    return after


class Call(ctypes.Structure):
    _fields_ = [('data_segment', ctypes.c_uint16), ('flags', ctypes.c_uint16)]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'count', 'definition_cursor', 'output_cursor',
                 'selected_count', 'flags')]


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
    """An oracle, fixture, callback, or finite-access guard failed."""


class GuardExhaustion(VerificationFailure):
    """A bounded trace or execution budget was exhausted."""


class Mismatch(AssertionError):
    """A completed native/reference comparison differs."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def callback_flag_mask(instruction_offset, xor_phase=False,
                       selected_count=None):
    if xor_phase and instruction_offset in (0x38ac, 0x38af):
        return DEFINED_FLAGS & ~AF
    if instruction_offset in (0x392c, 0x392e, 0x3931, 0x3934, 0x3937,
                              0x393a, 0x393d, 0x3940):
        return DEFINED_FLAGS & ~AF
    if instruction_offset == 0x3943 and selected_count == 0:
        return DEFINED_FLAGS & ~AF
    return DEFINED_FLAGS


def configure_vga(memory, seed, read_plane=1, write_mask=0x05):
    device = MinimapVga(seed, read_map=read_plane)
    aperture = memory[VGA_BASE:VGA_BASE + VGA_SIZE]
    device.planes = [bytearray(aperture) for _ in range(4)]
    device.seq[2] = write_mask & 0x0f
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[4] = read_plane & 3
    device.gc[5] = 0
    device.gc[8] = 0xff
    return device


def device_snapshot(device):
    return None if device is None else device.state()


def expected_vga_planes(initial_device, events):
    planes = [bytearray(plane) for plane in initial_device.planes]
    plane_mask = initial_device.seq[2] & 0x0f
    for kind, address, value, _flags, _mask in events:
        if kind == 'write' and VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            for plane in range(4):
                if plane_mask & (1 << plane):
                    planes[plane][offset] = value
    return tuple(bytes(plane) for plane in planes)


class CallbackBus:
    """Native callbacks use a hard access cap and process-level failure exits."""
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
                value = (self.device.read(self.memory, address, flags)
                         if self.device else self.memory[address])
                self.events.append(('read', address, value, flags & 0xffff))
                if self.device and len(self.device.trace) > MAX_BUS_EVENTS:
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
                value &= 0xff
                reserve('write')
                if self.device:
                    self.device.write(self.memory, address, value, flags)
                else:
                    self.memory[address] = value
                self.events.append(('write', address, value, flags & 0xffff))
                if self.device and len(self.device.trace) > MAX_BUS_EVENTS:
                    worker_exit(NATIVE_GUARD_EXIT,
                                'native VGA trace cap exhausted')
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                    f'native write callback failed: {type(error).__name__}: {error}')

        self._read = READ(read)
        self._write = WRITE(write)
        self._out = OUT()
        self.bus = RasterBus(None, self._read, self._write, self._out)


def compare_bus_events(actual, expected, case_name):
    require(len(actual) == len(expected),
            f'{case_name}: bus event count differs: {len(actual)} != {len(expected)}')
    for index, (got, wanted) in enumerate(zip(actual, expected)):
        exp_kind, exp_address, exp_value, exp_flags, flag_mask = wanted
        kind, address, value, flags = got
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
            f'{case_name}: ordered byte event {index} differs: '
            f'{got!r} != {wanted!r}')
        require(((flags ^ exp_flags) & flag_mask) == 0,
            f'{case_name}: defined callback flags differ at event {index}: '
            f'{flags:04x} vs {exp_flags:04x}, mask={flag_mask:04x}')


class OriginalRun:
    """Bounded execution of the pinned routine with bus and RET hooks."""
    def __init__(self, case, memory, regs, flags, device=None):
        self.case = case
        self.memory = memory
        self.regs_in = regs
        self.device = device
        self.events = []
        self.sites = set()
        self.edges = set()
        self.previous = None
        self.current_offset = None
        self.current_flags = 0
        self.current_selected_count = 0
        self.xor_phase = False
        self.steps = 0
        self.failure = None
        self.boundary = None
        self.done = False
        self.ret_target = None
        self.final_registers = None
        self.final_flags = None
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 1 << 21)
        loaded_image = fixtures.relocated(fixtures.IMAGE,
            fixtures.ORACLE['relocations'], regs['cs'])
        self.code_values = {
            physical(regs['cs'], pc + index): loaded_image[pc + index]
            for pc, instruction in fixtures.INS.items()
            for index in range(instruction.size)
        }
        if any(memory[address] != value
               for address, value in self.code_values.items()):
            raise VerificationFailure(
                f'{case["name"]}: entry contains modified relocated instruction bytes')
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

        def record(kind, address, value, event_flags):
            if len(self.events) >= MAX_BUS_EVENTS:
                fail(self.uc, f'{case["name"]}: original bus-event cap exhausted', True)
                return
            self.events.append((kind, address, value & 0xff,
                event_flags & 0xffff,
                callback_flag_mask(self.current_offset, self.xor_phase,
                                   self.current_selected_count)))

        def mirror(uc, linear, address, value):
            byte = bytes((value & 0xff,))
            for location in (linear, address, address + MEMORY_SIZE):
                if 0 <= location < (1 << 21):
                    uc.mem_write(location, byte)

        def code(uc, address, _size, _context):
            cs = uc.reg_read(fixtures.oracle.REG['cs'])
            offset = (address - (cs << 4)) & 0xffff
            self.current_offset = offset
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
            self.current_selected_count = uc.reg_read(fixtures.oracle.REG['bp'])
            if offset == 0x38aa:
                self.xor_phase = True
            elif offset == 0x38b2:
                self.xor_phase = False
            if self.previous in fixtures.BRANCHES:
                self.edges.add((self.previous, offset))
            if self.previous in fixtures.RETS:
                self.ret_target = offset
                self.done = True
                self.final_registers = {name: uc.reg_read(register)
                    for name, register in fixtures.oracle.REG.items()}
                self.final_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
                uc.emu_stop()
                return
            if cs != regs['cs'] or offset not in fixtures.INS:
                fail(uc, f'{case["name"]}: original escaped at {offset:04x}')
                return
            instruction = fixtures.INS[offset]
            code_address = address & MEMORY_MASK
            actual_code = bytes(uc.mem_read(address + index, 1)[0]
                                for index in range(instruction.size))
            expected_code = bytes(self.code_values[
                (code_address + index) & MEMORY_MASK]
                for index in range(instruction.size))
            if actual_code != expected_code:
                fail(uc, f'{case["name"]}: original decoded instruction bytes changed')
                return
            self.steps += 1
            if self.steps > MAX_ORIGINAL_INSTRUCTIONS:
                fail(uc, f'{case["name"]}: original instruction cap exhausted', True)
                return
            self.sites.add(offset)
            if offset in fixtures.RETS:
                self.boundary = dict(memory=bytes(self.memory),
                    registers={name: uc.reg_read(register)
                        for name, register in fixtures.oracle.REG.items()},
                    flags=self.current_flags, event_count=len(self.events),
                    device=copy.deepcopy(self.device))
            self.previous = offset

        def memory_read(uc, _access, linear, size, _value, _context):
            try:
                for index in range(size):
                    location = linear + index
                    if not 0 <= location < (1 << 21):
                        fail(uc, f'{case["name"]}: original read escaped mapped memory')
                        return
                    address = location & MEMORY_MASK
                    value = (self.device.read(self.memory, address,
                             self.current_flags)
                             if self.device and VGA_BASE <= address < VGA_END
                             else self.memory[address])
                    if self.device and len(self.device.trace) > MAX_BUS_EVENTS:
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
                        fail(uc, f'{case["name"]}: original write escaped mapped memory')
                        return
                    address = location & MEMORY_MASK
                    byte = (value >> (8 * index)) & 0xff
                    if address in self.code_values and byte != self.code_values[address]:
                        fail(uc, f'{case["name"]}: original write modified decoded code')
                        return
                    if self.device and VGA_BASE <= address < VGA_END:
                        self.device.write(self.memory, address, byte,
                                          self.current_flags)
                        if len(self.device.trace) > MAX_BUS_EVENTS:
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

        self._callbacks = (code, memory_read, memory_write)
        self.uc.hook_add(UC_HOOK_CODE, code)
        self.uc.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, memory_write)

    def run(self):
        try:
            self.uc.emu_start(physical(self.regs_in['cs'], fixtures.ENTRY), 0,
                              count=MAX_ORIGINAL_INSTRUCTIONS)
        except BaseException as error:
            raise VerificationFailure(
                f'{self.case["name"]}: bounded Unicorn execution failed: {error}')
        if self.failure:
            guard, message = self.failure
            if guard:
                raise GuardExhaustion(message)
            raise VerificationFailure(message)
        if not self.done or self.boundary is None:
            raise GuardExhaustion(
                f'{self.case["name"]}: original did not reach near RET within '
                f'{MAX_ORIGINAL_INSTRUCTIONS} instructions')
        memory_after = bytes(self.uc.mem_read(0, MEMORY_SIZE))
        if memory_after != bytes(self.memory):
            raise VerificationFailure(
                f'{self.case["name"]}: 20-bit memory mirrors did not reconcile')
        return dict(memory=memory_after, registers=self.final_registers,
            flags=self.final_flags, events=self.events, sites=self.sites,
            edges=self.edges, device=self.device, boundary=self.boundary,
            ret_target=self.ret_target)


def load_library(path):
    lib = ctypes.CDLL(str(path))
    lib.lmn_collect_type_one_object_coordinates_core.argtypes = [
        MEM, ctypes.POINTER(Call)]
    lib.lmn_collect_type_one_object_coordinates_core.restype = Result
    lib.lmn_collect_type_one_object_coordinates_adapter.argtypes = [
        MEM, ctypes.POINTER(fixtures.Regs)]
    lib.lmn_collect_type_one_object_coordinates_adapter.restype = None
    lib.lmn_collect_type_one_object_coordinates_bus_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    lib.lmn_collect_type_one_object_coordinates_bus_core.restype = Result
    lib.lmn_collect_type_one_object_coordinates_bus_adapter.argtypes = [
        MEM, ctypes.POINTER(fixtures.Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_collect_type_one_object_coordinates_bus_adapter.restype = None
    return lib


def result_tuple(result):
    return tuple(getattr(result, name) for name in
        ('value', 'count', 'definition_cursor', 'output_cursor',
         'selected_count', 'flags'))


def compare_flags(actual, expected, case_name, mask=DEFINED_FLAGS):
    require(((actual ^ expected) & mask) == 0,
        f'{case_name}: defined flags differ: {actual:04x} vs {expected:04x}, '
        f'mask={mask:04x}')


def compare_registers(actual, expected, case_name):
    for name in fixtures.oracle.REG_NAMES:
        require(actual[name] == expected[name],
            f'{case_name}: {name} differs: {actual[name]:04x} vs {expected[name]:04x}')


def native_core(lib, memory, regs, flags, callbacks=None, bus_aware=True):
    view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)
    call = Call(regs['ds'], flags)
    if bus_aware:
        bus = ctypes.byref(callbacks.bus) if callbacks else None
        return lib.lmn_collect_type_one_object_coordinates_bus_core(
            view, ctypes.byref(call), bus)
    return lib.lmn_collect_type_one_object_coordinates_core(
        view, ctypes.byref(call))


def native_adapter(lib, memory, regs, flags, callbacks=None, bus_aware=True):
    view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)
    native_regs = fixtures.Regs(**regs, flags=flags)
    if bus_aware:
        bus = ctypes.byref(callbacks.bus) if callbacks else None
        lib.lmn_collect_type_one_object_coordinates_bus_adapter(
            view, ctypes.byref(native_regs), bus)
    else:
        lib.lmn_collect_type_one_object_coordinates_adapter(
            view, ctypes.byref(native_regs))
    return native_regs


def compare_core_and_adapter(old_lib, bus_lib, bus_case, initial_memory,
                             regs, flags, original, check_previous,
                             verify_reference=True, reference=None):
    case = bus_case['case']
    name = case['name']
    if reference is None:
        reference = fixtures.independent_result(initial_memory, regs, flags)
    expected_memory, expected_regs, expected_flags = reference
    if verify_reference:
        require(original['memory'] == bytes(expected_memory),
            f'{name}: original whole RAM differs from independent contract')
        compare_registers(original['registers'], expected_regs, name)
        compare_flags(original['flags'], expected_flags, name,
            DEFINED_FLAGS & (~AF if expected_regs['bp'] == 0 else 0xffff))
        if bus_case['device'] is not None:
            expected_planes = expected_vga_planes(
                bus_case['device'], original['events'])
            require(tuple(original['device'].planes) == expected_planes,
                f'{name}: VGA planes differ from independent map-mask writes')

    if check_previous:
        old_core_memory = bytearray(initial_memory)
        new_core_memory = bytearray(initial_memory)
        old_core = native_core(old_lib, old_core_memory, regs, flags,
                               bus_aware=False)
        new_core = native_core(bus_lib, new_core_memory, regs, flags,
                               bus_aware=True)
        require(result_tuple(old_core) == result_tuple(new_core),
            f'{name}: null-bus core ABI differs from the original C core')
        require(old_core_memory == new_core_memory,
            f'{name}: null-bus core RAM differs from the original C core')
        require(old_core_memory == expected_memory,
            f'{name}: existing C core differs from independent RAM contract')

        old_adapter_memory = bytearray(initial_memory)
        new_adapter_memory = bytearray(initial_memory)
        old_adapter = native_adapter(old_lib, old_adapter_memory, regs, flags,
                                     bus_aware=False)
        new_adapter = native_adapter(bus_lib, new_adapter_memory, regs, flags,
                                     bus_aware=True)
        require(bytes(old_adapter) == bytes(new_adapter),
            f'{name}: null-bus adapter registers differ from the original C adapter')
        require(old_adapter_memory == new_adapter_memory,
            f'{name}: null-bus adapter RAM differs from the original C adapter')
        require(old_adapter_memory == expected_memory,
            f'{name}: existing C adapter differs from independent RAM contract')
        compare_registers({r: getattr(old_adapter, r)
                           for r in fixtures.oracle.REG_NAMES}, expected_regs, name)
        compare_flags(old_adapter.flags, expected_flags, name,
            DEFINED_FLAGS & (~AF if expected_regs['bp'] == 0 else 0xffff))

    boundary = original['boundary']
    core_memory = bytearray(initial_memory)
    core_device = copy.deepcopy(bus_case['device'])
    core_callbacks = CallbackBus(core_memory, core_device)
    core_result = native_core(bus_lib, core_memory, regs, flags,
                              core_callbacks, bus_aware=True)
    require((core_result.value, core_result.count,
             core_result.definition_cursor, core_result.output_cursor,
             core_result.selected_count) ==
            (boundary['registers']['ax'], boundary['registers']['cx'],
             boundary['registers']['si'], boundary['registers']['bx'],
             boundary['registers']['bp']),
        f'{name}: bus core logical result differs at the RET boundary')
    compare_flags(core_result.flags, boundary['flags'], name,
        DEFINED_FLAGS & (~AF if boundary['registers']['bp'] == 0 else 0xffff))
    require(core_memory == boundary['memory'],
        f'{name}: bus core canonical RAM differs at the RET boundary')
    compare_bus_events(core_callbacks.events,
        original['events'][:boundary['event_count']], name + ' core')
    require(device_snapshot(core_device) == device_snapshot(boundary['device']),
        f'{name}: bus core VGA state differs at the RET boundary')

    adapter_memory = bytearray(initial_memory)
    adapter_device = copy.deepcopy(bus_case['device'])
    adapter_callbacks = CallbackBus(adapter_memory, adapter_device)
    adapter_regs = native_adapter(bus_lib, adapter_memory, regs, flags,
                                  adapter_callbacks, bus_aware=True)
    actual_regs = {r: getattr(adapter_regs, r) for r in fixtures.oracle.REG_NAMES}
    compare_registers(actual_regs, original['registers'], name)
    compare_flags(adapter_regs.flags, original['flags'], name,
        DEFINED_FLAGS & (~AF if expected_regs['bp'] == 0 else 0xffff))
    require(adapter_memory == original['memory'],
        f'{name}: bus adapter full canonical RAM differs after near RET')
    compare_bus_events(adapter_callbacks.events, original['events'], name + ' adapter')
    require(device_snapshot(adapter_device) == device_snapshot(original['device']),
        f'{name}: bus adapter VGA state differs after near RET')

    return dict(events=len(adapter_callbacks.events),
        sites=original['sites'], edges=original['edges'],
        ret_target=original['ret_target'],
        device=bus_case['device_name'])


def put_plane_bytes(device, memory, segment, offset, data, plane):
    for index, value in enumerate(data):
        address = physical(segment, (offset + index) & 0xffff)
        aperture_offset = address - VGA_BASE
        device.planes[plane][aperture_offset] = value
        memory[address] = value


def prepare_bus_cases():
    cases = []

    case = dict(name='vga-source-and-destination', seed=0x701,
        definitions=fixtures.synthetic_definitions(0x701, range(32)),
        ds=0xa000)
    memory, regs, flags = fixtures.prepare(case)
    device = configure_vga(memory, case['seed'], read_plane=2, write_mask=0x05)
    put_plane_bytes(device, memory, regs['ds'], fixtures.DATA['definitions'],
                    case['definitions'], 2)
    for index, value in enumerate(case['definitions']):
        address = physical(regs['ds'], fixtures.DATA['definitions'] + index)
        aperture_offset = address - VGA_BASE
        for plane in (0, 1, 3):
            device.planes[plane][aperture_offset] = value ^ (plane * 0x35)
    cases.append(dict(case=case, memory=memory, regs=regs, flags=flags,
        device=device, device_name='read-plane-2 source, map-mask destination'))

    case = dict(name='destination-crosses-vga-end', seed=0x702,
        definitions=fixtures.synthetic_definitions(0x702, range(32)),
        ds=0xaf16)
    memory, regs, flags = fixtures.prepare(case)
    device = configure_vga(memory, case['seed'], read_plane=1, write_mask=0x05)
    require(physical(regs['ds'], fixtures.DATA['coordinates']) == 0xafff8,
            'destination-crosses-vga-end fixture lost its aperture boundary')
    cases.append(dict(case=case, memory=memory, regs=regs, flags=flags,
        device=device, device_name='destination AFFF8 across VGA/RAM boundary'))

    case = dict(name='provider-vga-near-ret', seed=0x703,
        definitions=fixtures.synthetic_definitions(0x703, (5,)),
        ds=0x7200, ss=0xa000, sp=0x1234, return_word=0xed00)
    memory, regs, flags = fixtures.prepare(case)
    device = configure_vga(memory, case['seed'], read_plane=1, write_mask=0x05)
    put_plane_bytes(device, memory, regs['ss'], regs['sp'],
                    bytes((0x00, 0xed)), 1)
    cases.append(dict(case=case, memory=memory, regs=regs, flags=flags,
        device=device, device_name='read-plane-1 provider stack RET'))

    case = dict(name='vga-output-overwrites-live-return', seed=0x704,
        definitions=fixtures.synthetic_definitions(0x704), ds=0xa000,
        ss=0xa000, sp=fixtures.DATA['coordinates'], return_word=0xaaaa)
    memory, regs, flags = fixtures.prepare(case)
    device = configure_vga(memory, case['seed'], read_plane=0, write_mask=0x0f)
    cases.append(dict(case=case, memory=memory, regs=regs, flags=flags,
        device=device, device_name='default VGA stores alias the live RET word'))

    case = dict(name='ret-word-straddles-20-bit-bus', seed=0x705,
        definitions=fixtures.synthetic_definitions(0x705, (2,)), ds=0x7200,
        ss=0xffff, sp=0x000f, return_word=0x6a31)
    memory, regs, flags = fixtures.prepare(case)
    require(physical(regs['ss'], regs['sp']) == 0xfffff,
            '20-bit RET fixture low byte is not at FFFFF')
    cases.append(dict(case=case, memory=memory, regs=regs, flags=flags,
        device=None, device_name='RET high byte wraps FFFFF to 00000'))

    return cases


def build_native(directory, mutation):
    output = Path(directory) / f'object-coordinates-bus-m{mutation}.dll'
    command = [compiler(), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-shared', '-DCOORD_MUTATION=0', f'-DCOORD_BUS_MUTATION={mutation}',
        '-I', str(ROOT / 'c'), str(ROOT / 'c/object_coordinates.c'),
        str(ROOT / 'c/object_coordinates_bus.c'), '-o', str(output)]
    run_bounded(command, cwd=ROOT, timeout=60, memory_mib=256)
    return output


def run_worker(directory, hash_file):
    baseline, consumed_assets = fixtures.cases()
    precompile_hashes = read_json(hash_file)
    old_lib = load_library(Path(directory) / 'object-coordinates-bus-m0.dll')
    bus_lib = old_lib
    bus_cases = [dict(case=case, memory=None, regs=None, flags=None,
                      device=None, device_name='ordinary RAM')
                 for case in baseline]
    bus_cases.extend(prepare_bus_cases())
    cases_report = []
    observed_sites = set()
    observed_edges = set()
    total_events = 0

    for entry in bus_cases:
        case = entry['case']
        if entry['memory'] is None:
            memory, regs, flags = fixtures.prepare(case)
        else:
            memory, regs, flags = entry['memory'], entry['regs'], entry['flags']
        original_memory = bytearray(memory)
        original_device = copy.deepcopy(entry['device'])
        original_runner = OriginalRun(case, original_memory, regs, flags,
                                      original_device)
        original = original_runner.run()
        del original_runner
        result = compare_core_and_adapter(old_lib, bus_lib, entry, memory,
            regs, flags, original, check_previous=entry['device'] is None)
        total_events += result['events']
        observed_sites.update(result['sites'])
        observed_edges.update(result['edges'])
        cases_report.append(dict(name=case['name'], event_count=result['events'],
            observed_site_count=len(result['sites']),
            observed_edge_count=len(result['edges']),
            device=result['device'], ret_target=result['ret_target']))
        del original, original_memory, original_device, result
        gc.collect()

    require(len(baseline) == 159 and len(bus_cases) == 164,
            f'normalized fixture counts changed: {len(baseline)} + '
            f'{len(bus_cases) - len(baseline)} != 159 + 5')

    mutations = []
    mutation_fixtures = {
        1: 'vga-source-and-destination',
        2: 'vga-source-and-destination',
        3: 'vga-output-overwrites-live-return',
        4: 'vga-source-and-destination',
    }
    by_name = {entry['case']['name']: entry for entry in bus_cases}
    for mutation, name in mutation_fixtures.items():
        entry = by_name[name]
        case = entry['case']
        memory, regs, flags = entry['memory'], entry['regs'], entry['flags']
        original_runner = OriginalRun(case, bytearray(memory), regs, flags,
            copy.deepcopy(entry['device']))
        original = original_runner.run()
        del original_runner
        expected_memory, expected_regs, expected_flags = \
            fixtures.independent_result(memory, regs, flags)
        require(original['memory'] == bytes(expected_memory),
            f'{name}: original whole RAM differs from independent contract')
        compare_registers(original['registers'], expected_regs, name)
        compare_flags(original['flags'], expected_flags, name,
            DEFINED_FLAGS & (~AF if expected_regs['bp'] == 0 else 0xffff))
        mutant = load_library(Path(directory) /
                              f'object-coordinates-bus-m{mutation}.dll')
        try:
            compare_core_and_adapter(old_lib, mutant, entry, memory, regs,
                                     flags, original, check_previous=False,
                                     verify_reference=False,
                                     reference=(expected_memory, expected_regs,
                                                expected_flags))
        except Mismatch:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise VerificationFailure(
                f'completed bus mismatch mutation {mutation} survived')
        del original, expected_memory, expected_regs, expected_flags, mutant
        gc.collect()

    expected_sites = set(fixtures.INS)
    expected_edges = {tuple(edge) for edge in fixtures.EDGES}
    require(observed_sites == expected_sites,
        f'instruction site coverage differs: missing={sorted(expected_sites-observed_sites)}, '
        f'extra={sorted(observed_sites-expected_sites)}')
    require(observed_edges == expected_edges,
        f'branch coverage differs: missing={sorted(expected_edges-observed_edges)}, '
        f'extra={sorted(observed_edges-expected_edges)}')
    require((fixtures.ENTRY, fixtures.END) == (0x389f, 0x3944) and
            len(fixtures.INS) == 63 and len(fixtures.EDGES) == 12,
            'pinned coordinate interval/site/edge counts changed')
    require(len(fixtures.IMAGE[fixtures.ENTRY:fixtures.END]) == 165,
            'original interval is not 165 bytes')
    require(len(mutations) == 4,
            f'expected four completed bus mutations, found {len(mutations)}')

    current_hashes = verify_inputs_unchanged(precompile_hashes, consumed_assets)
    sites = sorted(observed_sites)
    edges = sorted([list(edge) for edge in observed_edges])
    write_json(REPORT, dict(
        image='main', image_sha256=sha(fixtures.IMAGE),
        case_count=164, normalized_case_count=164,
        adapter_case_count=len(bus_cases),
        core_case_count=len(bus_cases), core_boundary_case_count=len(bus_cases),
        case_count_previous=len(baseline),
        case_count_bus=len(bus_cases) - len(baseline), cases=cases_report,
        mutation_count=len(mutations), mutations_detected=mutations,
        total_bus_events=total_events, translated_code_bytes=165,
        native_code_byte_count=165,
        existing_ram_translation_overlap_bytes=165,
        executed_instruction_address_space='CS-relative offsets',
        original_instruction_site_count=len(observed_sites),
        branch_edge_count=len(observed_edges),
        original_instruction_addresses=sorted(fixtures.INS),
        executed_instruction_addresses=sites,
        branch_instruction_addresses=sorted(fixtures.BRANCHES),
        branch_edges=edges,
        native_code_ranges=[[fixtures.ENTRY, fixtures.END]],
        routine=dict(name=fixtures.ROUTINE['symbol_name'], start=fixtures.ENTRY,
            end=fixtures.END, byte_count=fixtures.END-fixtures.ENTRY,
            bytes=fixtures.IMAGE[fixtures.ENTRY:fixtures.END].hex(),
            byte_sha256=sha(fixtures.IMAGE[fixtures.ENTRY:fixtures.END])),
        auxiliary_core_case_count=len(bus_cases),
        fixture_domains=dict(previous_159_ram_cases=True,
            null_bus_core_and_adapter_compared=True,
            vga_source_and_destination=True,
            destination_crosses_aperture_to_ram=True,
            provider_vga_near_ret=True, live_vga_return_alias=True,
            ret_word_20bit_wrap=True, defined_bus_flags=True,
            max_native_bus_events=MAX_BUS_EVENTS,
            original_instruction_limit=MAX_ORIGINAL_INSTRUCTIONS),
        input_hashes=current_hashes,
        flag_notes=('ADD16/CMP16/INC16 phases and DF/IF are compared at each '
            'access. AF is excluded only on byte reads after XOR BP,BP and on '
            'zero-count stores/RET after AND BP,BP, where it is undefined.'),
        domain=('Bus-aware C11 core and near-RET adapter for the independently '
            'understood 389F..3943 coordinate collector. One canonical 1 MiB '
            'memory image; separate high-first BE byte reads and LE machine-word '
            'physical+1 bytes; X store precedes Y source reads; exact flag phases, '
            'VGA provider reads/writes, live RET aliases and the original +0A '
            'default overwrite remain observable.')))
    print(f'PASS object coordinate bus C: {len(baseline)} previous RAM cases, '
          f'{len(bus_cases)-len(baseline)} bus cases, {total_events} bus events, '
          f'{len(observed_sites)} instruction sites, {len(observed_edges)} edges, '
          f'{len(mutations)} completed mutations detected')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        run_worker(sys.argv[2], sys.argv[3])
        return
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    _baseline, consumed_assets = fixtures.cases()
    precompile_hashes = current_input_hashes(consumed_assets)
    try:
        with temporary_build_directory(prefix='object-coordinates-bus-', parent=BUILD) as directory:
            hash_file = Path(directory) / 'precompile-input-hashes.json'
            write_json(hash_file, precompile_hashes)
            for mutation in range(5):
                build_native(directory, mutation)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--worker', directory, str(hash_file)], cwd=ROOT,
                        timeout=120, memory_mib=512)
    finally:
        verify_inputs_unchanged(precompile_hashes, consumed_assets)


if __name__ == '__main__':
    main()
