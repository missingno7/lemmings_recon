"""Bus-aware differential checks for the 37C2 object interaction cells."""
import copy
import ctypes
import gc
import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import object_cells as fixtures
from bounded_process import run_bounded, temporary_build_directory
from cbuild import compiler
from common import ROOT, BUILD, sha, read_json, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x


MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAX_BUS_EVENTS = 150_000
MAX_ORIGINAL_INSTRUCTIONS = 2_000_000
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87
DEFINED_FLAGS = 0x0FD7
AF = 0x0010
CF = 0x0001
OF = 0x0800
MUL_FLAGS = DEFINED_FLAGS & ~(0x00D4)  # only CF/OF plus TF/IF/DF are defined
VGA_SIZE = VGA_END - VGA_BASE
RESULT_FIELDS = ('value', 'cell_cursor', 'remaining_records',
                 'dimension_state', 'template_cursor', 'definition_cursor',
                 'object_ordinal', 'stack_offset', 'flags')
REPORT = BUILD / 'object-cells-bus-differential.json'
INPUT_PATHS = (
    'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
    'docs/level-initialize-bus-frontier.md', 'docs/interaction-cells.md',
    'docs/object-cells-bus.md', 'src/level_objects.asm',
    'c/object_cells_bus.c', 'c/object_cells_bus.h', 'c/object_cells.c',
    'c/object_cells.h', 'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
    'tests/object_cells_bus.py', 'tests/object_cells.py',
    'tests/object_graphics_bus.py', 'tests/drawing_caller_oracle.py',
    'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
    'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
    'tools/resources.py', 'tools/unpack.py', 'metadata/symbols.json',
    'metadata/inputs.json', 'assets/vgalemmi.exe',
) + tuple(f'assets/level{n:03d}.dat' for n in range(10)) + tuple(
    f'assets/ground{n}o.dat' for n in range(5))


def local_python_import_paths():
    """Return the loaded local Python import closure under tests/ and tools/."""
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


def current_input_hashes():
    paths = set(INPUT_PATHS)
    paths.update(local_python_import_paths())
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def verify_inputs_unchanged(before):
    after = current_input_hashes()
    if after != before:
        changed = sorted(path for path in (set(before) | set(after))
                         if before.get(path) != after.get(path))
        raise VerificationFailure(
            'test inputs changed during the bounded build/run: ' + ', '.join(changed))


class Call(ctypes.Structure):
    _fields_ = [('data_segment', ctypes.c_uint16),
                ('stack_segment', ctypes.c_uint16),
                ('stack_offset', ctypes.c_uint16),
                ('cell_cursor', ctypes.c_uint16),
                ('flags', ctypes.c_uint16)]


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
    """The original fixture, provider or access budget failed."""


class GuardExhaustion(VerificationFailure):
    """A bound expired; this is never evidence of a differential mutant."""


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MEMORY_MASK


def configure_vga(memory, seed, *, read_plane=1, write_mask=0x05):
    device = MinimapVga(seed, read_map=read_plane)
    aperture = memory[VGA_BASE:VGA_BASE + VGA_SIZE]
    device.planes = [bytearray(aperture) for _ in range(4)]
    device.seq[2] = write_mask & 0x0F
    device.seq[4] = 0x06
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[2] = 0
    device.gc[3] = 0
    device.gc[4] = read_plane & 3
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[7] = 0x0F
    device.gc[8] = 0xFF
    return device


def device_snapshot(device):
    return None if device is None else device.state()


def worker_exit_on_cap(label):
    worker_exit(NATIVE_GUARD_EXIT, f'{label}: native bus-event cap exhausted')


class CallbackBus:
    """Bounded ctypes callbacks; callback failures terminate the worker."""
    def __init__(self, memory, device=None):
        self.memory = memory
        self.device = device
        self.events = []

        def reserve(label):
            if len(self.events) >= MAX_BUS_EVENTS:
                worker_exit_on_cap(label)

        def read(_context, _memory, address, flags):
            try:
                address &= MEMORY_MASK
                reserve('read')
                value = (self.device.read(self.memory, address, flags)
                         if self.device else self.memory[address])
                self.events.append(('read', address, value, flags & 0xFFFF))
                if self.device and len(self.device.trace) > MAX_BUS_EVENTS:
                    worker_exit_on_cap('VGA read trace')
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
                if self.device and len(self.device.trace) > MAX_BUS_EVENTS:
                    worker_exit_on_cap('VGA write trace')
            except BaseException as error:
                worker_exit(NATIVE_CALLBACK_EXIT,
                    f'native write callback failed: {type(error).__name__}: {error}')

        self._read = READ(read)
        self._write = WRITE(write)
        self._out = OUT()
        self.bus = RasterBus(None, self._read, self._write, self._out)


def event_flag_mask(pc, previous, row_flags_mask, first_iteration):
    """Defined flags visible before each instruction's memory operation."""
    if pc in (0x37CB, 0x37CE) and first_iteration:
        return DEFINED_FLAGS & ~AF
    if pc in (0x37E9, 0x37F6, 0x3812, 0x3815, 0x3818):
        return DEFINED_FLAGS & ~AF
    if pc == 0x3802:  # POP AX follows MUL BX; other status flags are undefined.
        return MUL_FLAGS
    if pc == 0x381B:
        return row_flags_mask
    if pc == 0x381C:
        return row_flags_mask
    if pc == 0x381D and previous == 0x381C:
        return row_flags_mask
    return DEFINED_FLAGS


class OriginalRun:
    """Bounded execution with a flattened, instruction-phase bus trace."""
    def __init__(self, case, memory, regs, flags, device=None):
        self.case = case
        self.memory = memory
        self.regs_in = regs
        self.device = device
        self.initial_device = copy.deepcopy(device)
        loaded = fixtures.relocated(fixtures.IMAGE,
            fixtures.ORACLE['relocations'], regs['cs'])
        self.code_values = {
            (((regs['cs'] << 4) + pc + index) & MEMORY_MASK): loaded[pc + index]
            for pc, instruction in fixtures.INS.items()
            for index in range(instruction.size)
        }
        if any(memory[address] != value
               for address, value in self.code_values.items()):
            raise VerificationFailure(
                f'{case["name"]}: entry contains modified relocated instruction bytes')
        self.events = []
        self.sites = set()
        self.edges = set()
        self.previous = None
        self.current_pc = None
        self.current_flags = flags & 0xFFFF
        self.current_flag_mask = DEFINED_FLAGS
        self.row_flags_mask = DEFINED_FLAGS & ~AF
        self.steps = 0
        self.failure = None
        self.done = False
        self.ret_target = None
        self.ret_entry = None
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 1 << 21)
        initial = bytes(memory)
        self.uc.mem_write(0, initial + initial)
        for name, reg in fixtures.oracle.REG.items():
            self.uc.reg_write(reg, regs[name])
        self.uc.reg_write(x.UC_X86_REG_EFLAGS, flags)

        def fail(uc, message, guard=False):
            if self.failure is None:
                self.failure = (guard, message)
            uc.emu_stop()

        def record(kind, address, value):
            if len(self.events) >= MAX_BUS_EVENTS:
                fail(self.uc, f'{case["name"]}: original bus-event cap exhausted', True)
                return False
            self.events.append((kind, address & MEMORY_MASK, value & 0xFF,
                                self.current_flags, self.current_flag_mask))
            return True

        def code(uc, address, _size, _context):
            if self.previous == fixtures.RET:
                self.done = True
                self.ret_target = (address - (regs['cs'] << 4)) & 0xFFFF
                uc.emu_stop()
                return
            off = (address - (regs['cs'] << 4)) & 0xFFFF
            if self.previous in fixtures.BRANCHES:
                self.edges.add((self.previous, off))
            if uc.reg_read(fixtures.oracle.REG['cs']) != regs['cs'] or off not in fixtures.INS:
                fail(uc, f'{case["name"]}: original escaped at {off:04x}')
                return
            self.current_pc = off
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            first_iteration = (uc.reg_read(fixtures.oracle.REG['cx']) == 0x10)
            if off == 0x381B:
                self.row_flags_mask = (DEFINED_FLAGS & ~AF
                    if self.previous == 0x3818 else DEFINED_FLAGS)
            self.current_flag_mask = event_flag_mask(
                off, self.previous, self.row_flags_mask, first_iteration)
            self.steps += 1
            if self.steps > MAX_ORIGINAL_INSTRUCTIONS:
                fail(uc, f'{case["name"]}: original instruction budget exhausted', True)
                return
            self.sites.add(off)
            if off == fixtures.RET:
                registers = {name: uc.reg_read(reg)
                    for name, reg in fixtures.oracle.REG.items()}
                self.ret_entry = dict(registers=registers,
                    flags=self.current_flags, memory=bytes(self.memory),
                    event_count=len(self.events), device=copy.deepcopy(self.device))
            self.previous = off

        def mirror(uc, raw, physical_address, value):
            byte = bytes((value & 0xFF,))
            for location in (raw, physical_address, physical_address + MEMORY_SIZE):
                if 0 <= location < (1 << 21):
                    uc.mem_write(location, byte)

        def memory_read(uc, _access, address, size, _value, _context):
            try:
                for index in range(size):
                    raw = address + index
                    if not 0 <= raw < (1 << 21):
                        fail(uc, f'{case["name"]}: original read escaped mapped memory')
                        return
                    p = raw & MEMORY_MASK
                    value = (self.device.read(self.memory, p, self.current_flags)
                             if self.device else self.memory[p])
                    if not record('read', p, value):
                        return
                    mirror(uc, raw, p, value)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original read provider failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, _access, address, size, value, _context):
            try:
                for index in range(size):
                    raw = address + index
                    if not 0 <= raw < (1 << 21):
                        fail(uc, f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = raw & MEMORY_MASK
                    byte = (value >> (8 * index)) & 0xFF
                    if p in self.code_values and byte != self.code_values[p]:
                        fail(uc, f'{case["name"]}: original write modified decoded code')
                        return
                    if self.device:
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    if not record('write', p, byte):
                        return
                    mirror(uc, raw, p, byte)
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
            self.uc.emu_start(physical(self.regs_in['cs'], fixtures.ENTRY), 0,
                              count=MAX_ORIGINAL_INSTRUCTIONS)
        except BaseException as error:
            raise VerificationFailure(
                f'{self.case["name"]}: bounded original execution failed: {error}')
        if self.failure:
            guard, message = self.failure
            if guard:
                raise GuardExhaustion(message)
            raise VerificationFailure(message)
        if not self.done or self.ret_entry is None:
            raise GuardExhaustion(
                f'{self.case["name"]}: original did not execute and return within '
                f'{MAX_ORIGINAL_INSTRUCTIONS} instructions')
        return dict(events=self.events, sites=self.sites, edges=self.edges,
            ret_entry=self.ret_entry,
            registers={name: self.uc.reg_read(reg)
                       for name, reg in fixtures.oracle.REG.items()},
            flags=self.uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF,
            memory=bytes(self.memory), device=self.device,
            initial_device=self.initial_device,
            ret_target=self.ret_target)


def compare_events(actual, expected, case_name):
    require(len(actual) == len(expected),
            f'{case_name}: ordered bus event count differs ({len(actual)} vs {len(expected)})')
    for index, (got, wanted) in enumerate(zip(actual, expected)):
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags, flag_mask = wanted
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
            f'{case_name}: bus event {index} differs: {got!r} vs {wanted!r}')
        require(((flags ^ exp_flags) & flag_mask) == 0,
            f'{case_name}: defined event flags differ at {index}: '
            f'{flags:04x} vs {exp_flags:04x} mask={flag_mask:04x}')


def result_tuple(result):
    return tuple(getattr(result, name) for name in RESULT_FIELDS)


def call_for(regs, flags):
    return Call(regs['ds'], regs['ss'], regs['sp'], regs['bx'], flags)


def native_view(memory):
    return (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)


def compare_core(lib, case, memory, regs, flags, original, *, bus_enabled=True):
    native_memory = bytearray(memory)
    native_device = copy.deepcopy(original['initial_device']) if bus_enabled else None
    callbacks = CallbackBus(native_memory, native_device) if bus_enabled else None
    call = call_for(regs, flags)
    result = lib.lmn_write_object_interaction_cells_bus_core(
        native_view(native_memory), ctypes.byref(call),
        ctypes.byref(callbacks.bus) if callbacks else None)
    entry = original['ret_entry']
    expected_registers = entry['registers']
    for name, field in (('ax','value'), ('bx','cell_cursor'),
        ('cx','remaining_records'), ('dx','dimension_state'),
        ('si','template_cursor'), ('di','definition_cursor'),
        ('bp','object_ordinal'), ('sp','stack_offset')):
        require(getattr(result, field) == expected_registers[name],
            f'{case["name"]}: direct core {name} differs at RET entry')
    require(((result.flags ^ entry['flags']) & DEFINED_FLAGS) == 0,
        f'{case["name"]}: direct core defined flags differ at RET entry')
    require(bytes(native_memory) == entry['memory'],
        f'{case["name"]}: direct core full RAM differs at RET entry')
    if callbacks:
        compare_events(callbacks.events,
            original['events'][:entry['event_count']], case['name'])
        require(device_snapshot(native_device) == device_snapshot(entry['device']),
            f'{case["name"]}: direct core VGA state differs at RET entry')
    return result, native_memory, callbacks


def compare_adapter(lib, case, memory, regs, flags, original):
    native_memory = bytearray(memory)
    native_device = copy.deepcopy(original['initial_device'])
    callbacks = CallbackBus(native_memory, native_device)
    native_regs = Regs(**regs, flags=flags)
    lib.lmn_write_object_interaction_cells_bus_adapter(
        native_view(native_memory), ctypes.byref(native_regs),
        ctypes.byref(callbacks.bus))
    for name in fixtures.oracle.REG_NAMES:
        require(getattr(native_regs, name) == original['registers'][name],
            f'{case["name"]}: adapter register {name} differs after RET')
    require(((native_regs.flags ^ original['flags']) & DEFINED_FLAGS) == 0,
        f'{case["name"]}: adapter defined flags differ after RET')
    require(native_memory == original['memory'],
        f'{case["name"]}: adapter full canonical RAM differs after RET')
    compare_events(callbacks.events, original['events'], case['name'])
    require(device_snapshot(native_device) == device_snapshot(original['device']),
        f'{case["name"]}: adapter VGA state differs after RET')
    return callbacks


def compare_null_abi(old_lib, bus_lib, case, memory, regs, flags):
    old_memory = bytearray(memory)
    new_memory = bytearray(memory)
    call = call_for(regs, flags)
    old_result = old_lib.lmn_write_object_interaction_cells_core(
        native_view(old_memory), ctypes.byref(call))
    new_result = bus_lib.lmn_write_object_interaction_cells_bus_core(
        native_view(new_memory), ctypes.byref(call), None)
    require(result_tuple(old_result) == result_tuple(new_result),
        f'{case["name"]}: null-bus direct core result changed')
    require(old_memory == new_memory,
        f'{case["name"]}: null-bus direct core RAM changed')

    old_memory = bytearray(memory)
    new_memory = bytearray(memory)
    old_regs = Regs(**regs, flags=flags)
    new_regs = Regs(**regs, flags=flags)
    old_lib.lmn_write_object_interaction_cells_adapter(
        native_view(old_memory), ctypes.byref(old_regs))
    bus_lib.lmn_write_object_interaction_cells_bus_adapter(
        native_view(new_memory), ctypes.byref(new_regs), None)
    require(bytes(old_regs) == bytes(new_regs),
        f'{case["name"]}: null-bus adapter registers changed')
    require(old_memory == new_memory,
        f'{case["name"]}: null-bus adapter RAM changed')


def put_provider_byte(device, segment, offset, value):
    address = physical(segment, offset)
    if not VGA_BASE <= address < VGA_END:
        raise VerificationFailure('provider fixture address is outside A000 aperture')
    device.planes[device.gc[4] & 3][address - VGA_BASE] = value & 0xFF


def extra_cases():
    out = []
    source = dict(name='provider-source-data-in-ds-a000', seed=0xB701,
        definitions=((0, 8, 0, 0),), templates=((0, 0, 1, 2, 1, 0x51),),
        ds=0xA000, ss=0x7000, sp=0x8000, df=False, iflag=True)
    memory, regs, flags = fixtures.prepare(source)
    device = configure_vga(memory, source['seed'], read_plane=1, write_mask=0x05)
    # The provider's width differs from cached RAM, so the DS read must use
    # the selected live plane and mirror that value into canonical memory.
    put_provider_byte(device, regs['ds'], fixtures.template_offset(0) + 0x12, 3)
    out.append((source, memory, regs, flags, device))

    destination = dict(name='vga-destination-and-live-stack', seed=0xB702,
        definitions=((0, 4, 0, 0),),
        templates=(fixtures.target_template(0x8100, 4, 0, 2, 2, 0x62),),
        ds=0x6000, ss=0xA000, sp=0x7F00, df=True, iflag=False)
    memory, regs, flags = fixtures.prepare(destination)
    device = configure_vga(memory, destination['seed'], read_plane=1, write_mask=0x02)
    out.append((destination, memory, regs, flags, device))

    destination_wrap = dict(name='vga-destination-address-wrap', seed=0xB703,
        definitions=((0, 0xFFFC, 0xFFFC, 0),),
        templates=(fixtures.target_template(0xFFFF, 0xFFFC, 0xFFFC, 2, 1, 0x73),),
        ds=0x6000, ss=0xA000, sp=0x0001, df=False, iflag=True)
    memory, regs, flags = fixtures.prepare(destination_wrap)
    device = configure_vga(memory, destination_wrap['seed'], read_plane=1,
                           write_mask=0x02)
    out.append((destination_wrap, memory, regs, flags, device))

    ret_twenty_bit = dict(name='ret-word-straddles-20-bit-ss-ffff-sp-000f',
        seed=0xB704, definitions=((0, 4, 0, 0),),
        templates=(fixtures.target_template(0x0020, 4, 0, 1, 1, 0x44),),
        ds=0x6000, ss=0xFFFF, sp=0x000F, df=False, iflag=True)
    memory, regs, flags = fixtures.prepare(ret_twenty_bit)
    out.append((ret_twenty_bit, memory, regs, flags, None))

    ret_segment_edge = dict(name='ret-word-sp-ffff-physical-high-byte', seed=0xB705,
        ds=0x6000, ss=0x7000, sp=0xFFFF, bx=0x5AA5, df=True, iflag=False)
    memory, regs, flags = fixtures.prepare(ret_segment_edge)
    out.append((ret_segment_edge, memory, regs, flags, None))
    return out


def run_one_case(lib, old_lib, case, memory, regs, flags, device=None):
    try:
        original = OriginalRun(case, bytearray(memory), regs, flags,
                               copy.deepcopy(device)).run()
        compare_null_abi(old_lib, lib, case, memory, regs, flags)
        compare_core(lib, case, memory, regs, flags, original)
        compare_adapter(lib, case, memory, regs, flags, original)
        return original
    finally:
        gc.collect()


def load_library(directory, mutation):
    path = Path(directory) / f'object-cells-bus-m{mutation}.dll'
    lib = ctypes.CDLL(str(path))
    lib.lmn_write_object_interaction_cells_bus_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    lib.lmn_write_object_interaction_cells_bus_core.restype = Result
    lib.lmn_write_object_interaction_cells_bus_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_write_object_interaction_cells_bus_adapter.restype = None
    return lib


def load_old_library(directory):
    lib = ctypes.CDLL(str(Path(directory) / 'object-cells-ram.dll'))
    lib.lmn_write_object_interaction_cells_core.argtypes = [
        MEM, ctypes.POINTER(Call)]
    lib.lmn_write_object_interaction_cells_core.restype = Result
    lib.lmn_write_object_interaction_cells_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs)]
    lib.lmn_write_object_interaction_cells_adapter.restype = None
    return lib


def run_worker(directory, precompile_hashes):
    baseline, consumed_assets = fixtures.cases()
    old_lib = load_old_library(directory)
    bus_lib = load_library(directory, 0)
    observed_sites = set()
    observed_edges = set()
    case_names = []

    for case in baseline:
        memory, regs, flags = fixtures.prepare(case)
        original = run_one_case(bus_lib, old_lib, case, memory, regs, flags)
        observed_sites.update(original['sites'])
        observed_edges.update(original['edges'])
        case_names.append(case['name'])
        del original, memory, regs
        gc.collect()

    extra = extra_cases()
    for case, memory, regs, flags, device in extra:
        original = run_one_case(bus_lib, old_lib, case, memory, regs, flags, device)
        observed_sites.update(original['sites'])
        observed_edges.update(original['edges'])
        case_names.append(case['name'])
        del original, memory, regs, device
        gc.collect()

    require(observed_sites == set(fixtures.INS),
        f'original site coverage differs: missing={sorted(set(fixtures.INS)-observed_sites)}')
    require(observed_edges == fixtures.EDGES,
        f'original branch edges differ: missing={sorted(fixtures.EDGES-observed_edges)}')

    by_name = {case['name']: case for case in baseline}
    mutant_fixtures = {
        1: 'width-zero-means-256-height-one',
        2: 'saved-bx-dx-alias-controls-next-row',
        3: 'unchecked-type-ffff',
        4: 'all-inactive-preserves-bx',
    }
    mutations = []
    for mutation, name in mutant_fixtures.items():
        case = by_name[name]
        original = memory = regs = mutant = None
        try:
            memory, regs, flags = fixtures.prepare(case)
            original = OriginalRun(case, bytearray(memory), regs, flags).run()
            mutant = load_library(directory, mutation)
            compare_core(mutant, case, memory, regs, flags, original)
        except Mismatch as error:
            if mutation == 4 and 'defined event flags differ at' not in str(error):
                raise VerificationFailure(
                    'ADD SI flags mutant was detected outside its ordered bus flags')
            mutations.append(dict(mutation=mutation, case=name,
                                  outcome='completed differential mismatch'))
        else:
            raise VerificationFailure(f'compiled mutation {mutation} survived on {name}')
        finally:
            original = memory = regs = mutant = None
            gc.collect()

    write_json(REPORT, dict(
        image='main', image_sha256=sha(fixtures.IMAGE),
        case_count=len(case_names), case_count_previous=len(baseline),
        baseline_ram_case_count=len(baseline), extra_bus_cases=len(extra),
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in fixtures.INS.values()),
        native_code_ranges=[[0x37C2, 0x3839]],
        native_code_byte_count=119,
        existing_ram_translation_overlap_bytes=119,
        executed_instruction_address_space='CS-relative offsets',
        executed_instruction_addresses=sorted(observed_sites),
        adapter_case_count=len(case_names),
        core_boundary_case_count=len(case_names),
        original_instruction_sites=sorted(observed_sites),
        branch_edges=[list(edge) for edge in sorted(observed_edges)],
        return_site=fixtures.RET, return_consumed_by_core=False,
        case_names=case_names,
        fixture_domains=dict(full_ram_and_registers=True,
            null_bus_core_and_adapter_match_existing_ram_api=True,
            source_provider_ds_a000=True, destination_and_live_stack_ss_a000=True,
            independent_big_endian_byte_reads=True,
            physical_word_high_byte_wrap=True,
            live_stack_push_pop_and_adapter_ret=True,
            per_access_defined_flags=True, undefined_af_excluded=True,
            add_si_phase_flags_mutation_witness=True,
            real_level_sections=80, incoming_df=['clear','set'],
            max_native_bus_events=MAX_BUS_EVENTS),
        input_hashes=precompile_hashes,
        domain=('Bus-aware C11 core and adapter for CS:37C2..3838; canonical '
            'RAM plus callback-owned VGA planes, flags on every sequenced memory '
            'event, unchecked type*28 lookup, live SS row saves, and live RET readback.')))
    print(f'PASS object interaction cells bus C: {len(case_names)} cases, '
          f'{len(observed_sites)} instruction sites, {len(observed_edges)} branch edges, '
          f'{len(mutations)} compiled mutations detected')


def compile_library(output, source, macro, value):
    run_bounded([compiler(), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-shared', f'-D{macro}={value}', '-I', str(ROOT / 'c'),
        str(ROOT / 'c' / source), '-o', str(output)], cwd=ROOT,
        timeout=60, memory_mib=256)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    precompile_hashes = current_input_hashes()
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='object-cells-bus-', parent=BUILD) as directory:
        hash_file = Path(directory) / 'precompile-input-hashes.json'
        write_json(hash_file, precompile_hashes)
        try:
            compile_library(Path(directory) / 'object-cells-ram.dll',
                            'object_cells.c', 'CELL_MUTATION', 0)
            for mutation in range(5):
                compile_library(Path(directory) / f'object-cells-bus-m{mutation}.dll',
                    'object_cells_bus.c', 'OBJECT_CELLS_BUS_MUTATION', mutation)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--worker', directory, str(hash_file)], cwd=ROOT,
                        timeout=120, memory_mib=512)
        finally:
            verify_inputs_unchanged(precompile_hashes)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        run_worker(sys.argv[2], read_json(sys.argv[3]))
    else:
        main()
