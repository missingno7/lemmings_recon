"""Bounded ordered-bus checks for the 3839..389E steel-cell leaf.

The runner compiles a private C cluster and compares byte events against the
pinned original while preserving the existing 386-case RAM regression suite.
"""
import copy
import ctypes
import gc
import json
import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import steel_cells as fixtures
from bounded_process import run_bounded, temporary_build_directory
from cbuild import compiler
from common import ROOT, BUILD, sha, write_json
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x


MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAX_BUS_EVENTS = 50_000
MAX_ORIGINAL_INSTRUCTIONS = 1_000_000
NATIVE_GUARD_EXIT = 86
NATIVE_CALLBACK_EXIT = 87
CF, PF, AF, ZF, SF, OF = 0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0800
ARITH = CF | PF | AF | ZF | SF | OF
LOGIC_FLAGS = CF | PF | ZF | SF | OF
DEFINED_FLAGS = 0x0FD7
MEM = ctypes.POINTER(ctypes.c_uint8)
RESULT_FIELDS = ('value', 'cell_cursor', 'records_remaining', 'dimensions',
                 'definition_cursor', 'stack_offset', 'flags')
RET = next(iter(fixtures.RETS))
INPUT_PATHS = (
    'src/level_objects.asm',
    'c/steel_cells_bus.c', 'c/steel_cells_bus.h', 'c/steel_cells.c',
    'c/steel_cells.h', 'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
    'tests/steel_cells_bus.py', 'tests/steel_cells.py', 'tests/dat_io.py',
    'tests/dat_io_c.py', 'tests/minimap_vga.py',
    'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
    'tools/resources.py', 'tools/unpack.py',
    'docs/executable.md', 'docs/next-work.md',
    'docs/level-initialize-bus-frontier.md', 'docs/interaction-cells.md',
    'docs/steel-cells-bus.md',
    'metadata/symbols.json', 'metadata/inputs.json', 'requirements.txt',
    'assets/vgalemmi.exe',
) + tuple(f'assets/level{group:03d}.dat' for group in range(10))


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in RESULT_FIELDS]


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
                 'cs', 'ds', 'es', 'ss', 'ip', 'flags')]


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
    """The original oracle, fixture or provider failed before comparison."""


class GuardExhaustion(VerificationFailure):
    """A finite instruction or event budget was exhausted."""


class Mismatch(AssertionError):
    """A completed original/native comparison differs."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def collect_input_hashes():
    return {path: sha((ROOT / path).read_bytes()) for path in INPUT_PATHS}


def verify_input_hashes(expected):
    current = collect_input_hashes()
    if current != expected:
        changed = sorted(path for path in set(current) | set(expected)
                         if current.get(path) != expected.get(path))
        raise VerificationFailure(
            f'input sources changed during steel-cell bus run: {changed}')
    return current


def device_snapshot(device):
    return None if device is None else device.state()


def configure_vga(memory, case):
    device = MinimapVga(case['seed'], read_map=1)
    device.seq[2] = 0x0f
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[4] = 1
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xff

    if case.get('provider_source'):
        # The definition bytes are supplied by the selected VGA read plane.
        start = fixtures.DEFINITIONS
        for index, value in enumerate(case['definitions']):
            device.planes[1][start + index] = value

    if case.get('ss') == 0xa000:
        # Pushes and POPs go through all four planes. Seed the untouched live
        # return word so the adapter must obtain it through the same provider.
        offset = case.get('sp', 0xf000)
        word = case.get('return_word', 0xff00)
        if offset < 0x10000:
            for plane in device.planes:
                plane[offset] = word & 0xff
                if offset != 0xffff:
                    plane[offset + 1] = (word >> 8) & 0xff

    return device


class CallbackBus:
    """Byte-ordered C callbacks with process-level failure and event guards."""
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
                         if self.device and VGA_BASE <= address < VGA_END
                         else self.memory[address])
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
                if self.device and VGA_BASE <= address < VGA_END:
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


def advance_flag_mask(previous, known):
    """Track only status bits defined at the next instruction boundary."""
    instruction = fixtures.INS.get(previous)
    if instruction is None:
        return known
    mnemonic = instruction.mnemonic
    if mnemonic in ('or', 'and', 'xor', 'shr', 'shl'):
        return (known & ~ARITH) | LOGIC_FLAGS
    if mnemonic == 'mul':
        return (known & ~ARITH) | CF | OF
    if mnemonic == 'add':
        return known | ARITH
    if mnemonic in ('inc', 'dec'):
        return known | (ARITH & ~CF)
    if mnemonic in ('rol', 'rcl'):
        return known | CF | OF
    return known


class OriginalRun:
    """Execute only the identified routine and stop just after its live RET."""
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
        self.current_flags = flags & 0xffff
        self.current_mask = DEFINED_FLAGS
        self.known_mask = DEFINED_FLAGS
        self.steps = 0
        self.failure = None
        self.before_ret = None
        self.after_ret = None
        self.ret_target = None
        relocated = fixtures.relocated(
            fixtures.IMAGE, fixtures.ORACLE['relocations'], regs['cs'])
        self.code_bytes = {
            physical(regs['cs'], offset + index): relocated[offset + index]
            for offset, instruction in fixtures.INS.items()
            for index in range(instruction.size)
        }
        for address, expected in self.code_bytes.items():
            if memory[address] != expected:
                raise VerificationFailure(
                    f'{case["name"]}: pinned routine byte differs at {address:05x}')
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

        def record(kind, address, value):
            if len(self.events) >= MAX_BUS_EVENTS:
                fail(self.uc, f'{case["name"]}: original bus-event cap exhausted', True)
                return
            self.events.append((kind, address & MEMORY_MASK, value & 0xff,
                                self.current_flags & 0xffff,
                                self.current_mask, self.current_offset))

        def code(uc, pc, _size, _context):
            if self.previous in fixtures.RETS:
                self.ret_target = uc.reg_read(fixtures.oracle.REG['ip'])
                self.after_ret = dict(
                    registers={name: uc.reg_read(register)
                               for name, register in fixtures.oracle.REG.items()},
                    flags=uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff,
                    memory=bytes(self.memory), device=device_snapshot(self.device),
                    event_count=len(self.events))
                uc.emu_stop()
                return

            if self.previous is not None:
                self.known_mask = advance_flag_mask(self.previous, self.known_mask)
                if self.previous in fixtures.BRANCHES:
                    destination = (pc - (regs['cs'] << 4)) & 0xffff
                    self.edges.add((self.previous, destination))

            cs = uc.reg_read(fixtures.oracle.REG['cs'])
            offset = (pc - (regs['cs'] << 4)) & 0xffff
            if cs != regs['cs'] or offset not in fixtures.INS:
                fail(uc, f'{case["name"]}: original escaped at {cs:04x}:{offset:04x}')
                return
            self.current_offset = offset
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
            self.current_mask = self.known_mask
            if self.steps >= MAX_ORIGINAL_INSTRUCTIONS:
                fail(uc, f'{case["name"]}: original instruction budget exhausted', True)
                return
            self.steps += 1
            self.sites.add(offset)
            if offset in fixtures.RETS:
                self.before_ret = dict(
                    registers={name: uc.reg_read(register)
                               for name, register in fixtures.oracle.REG.items()},
                    flags=self.current_flags, memory=bytes(self.memory),
                    device=device_snapshot(self.device),
                    event_count=len(self.events))
            self.previous = offset

        def mirror_byte(uc, raw, p, value):
            byte = bytes((value & 0xff,))
            for location in (raw, p, p + MEMORY_SIZE):
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
                    value = (self.device.read(memory, p, self.current_flags)
                             if self.device and VGA_BASE <= p < VGA_END
                             else memory[p])
                    record('read', p, value)
                    if self.failure:
                        return
                    mirror_byte(uc, raw, p, value)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original provider read failed: '
                     f'{type(error).__name__}: {error}')

        def memory_write(uc, _access, address, size, value, _context):
            try:
                for index in range(size):
                    raw = address + index
                    if not 0 <= raw < (1 << 21):
                        fail(uc, f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = raw & MEMORY_MASK
                    byte = (value >> (8 * index)) & 0xff
                    expected = self.code_bytes.get(p)
                    if expected is not None and byte != expected:
                        fail(uc, f'{case["name"]}: original modified pinned code '
                             f'at {p:05x}: {expected:02x}->{byte:02x}')
                        return
                    if self.device and VGA_BASE <= p < VGA_END:
                        self.device.write(memory, p, byte, self.current_flags)
                    else:
                        memory[p] = byte
                    record('write', p, byte)
                    if self.failure:
                        return
                    mirror_byte(uc, raw, p, byte)
            except BaseException as error:
                fail(uc, f'{case["name"]}: original provider write failed: '
                     f'{type(error).__name__}: {error}')

        def interrupt(uc, number, _context):
            fail(uc, f'{case["name"]}: unexpected INT{number:02x}')

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
        if self.before_ret is None or self.after_ret is None:
            raise GuardExhaustion(
                f'{self.case["name"]}: original did not reach and return from RET')
        if bytes(self.uc.mem_read(0, MEMORY_SIZE)) != bytes(self.memory):
            raise VerificationFailure(
                f'{self.case["name"]}: original low-memory view did not reconcile')
        if bytes(self.uc.mem_read(MEMORY_SIZE, MEMORY_SIZE)) != bytes(self.memory):
            raise VerificationFailure(
                f'{self.case["name"]}: 20-bit memory mirror did not reconcile')
        return dict(events=self.events, sites=self.sites, edges=self.edges,
                    before_ret=self.before_ret, after_ret=self.after_ret,
                    ret_target=self.ret_target)


def compare_events(actual, expected, case_name):
    require(len(actual) == len(expected),
            f'{case_name}: ordered bus event count differs '
            f'({len(actual)} native, {len(expected)} original)')
    for index, (got, wanted) in enumerate(zip(actual, expected)):
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags, flag_mask, _pc = wanted
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
                f'{case_name}: bus event {index} differs: {got!r} vs {wanted!r}')
        require(((flags ^ exp_flags) & flag_mask) == 0,
                f'{case_name}: defined bus flags differ at event {index}: '
                f'{flags:04x} vs {exp_flags:04x}, mask={flag_mask:04x}')


def load_library(directory, mutation):
    path = Path(directory) / f'steel-cells-bus-m{mutation}.dll'
    lib = ctypes.CDLL(str(path))
    lib.lmn_write_steel_interaction_cells_core.argtypes = [
        MEM, ctypes.POINTER(Call)]
    lib.lmn_write_steel_interaction_cells_core.restype = Result
    lib.lmn_write_steel_interaction_cells_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs)]
    lib.lmn_write_steel_interaction_cells_adapter.restype = None
    lib.lmn_write_steel_interaction_cells_bus_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(RasterBus)]
    lib.lmn_write_steel_interaction_cells_bus_core.restype = Result
    lib.lmn_write_steel_interaction_cells_bus_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_write_steel_interaction_cells_bus_adapter.restype = None
    return lib


def result_tuple(result):
    return tuple(getattr(result, field) for field in RESULT_FIELDS)


def memory_view(memory):
    return (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)


def compare_null_abi(old_lib, bus_lib, case, memory, regs, flags):
    old_memory = bytearray(memory)
    new_memory = bytearray(memory)
    call = Call(regs['ds'], regs['ss'], regs['sp'], flags)
    old_result = old_lib.lmn_write_steel_interaction_cells_core(
        memory_view(old_memory), ctypes.byref(call))
    new_result = bus_lib.lmn_write_steel_interaction_cells_bus_core(
        memory_view(new_memory), ctypes.byref(call), None)
    require(result_tuple(old_result) == result_tuple(new_result),
            f'{case["name"]}: null-bus core result changed')
    require(old_memory == new_memory,
            f'{case["name"]}: null-bus core RAM changed')

    old_memory = bytearray(memory)
    new_memory = bytearray(memory)
    old_regs = Regs(**regs, flags=flags)
    new_regs = Regs(**regs, flags=flags)
    old_lib.lmn_write_steel_interaction_cells_adapter(
        memory_view(old_memory), ctypes.byref(old_regs))
    bus_lib.lmn_write_steel_interaction_cells_bus_adapter(
        memory_view(new_memory), ctypes.byref(new_regs), None)
    require(bytes(old_regs) == bytes(new_regs),
            f'{case["name"]}: null-bus adapter registers changed')
    require(old_memory == new_memory,
            f'{case["name"]}: null-bus adapter RAM changed')


def expected_core_registers(original):
    return dict(original['before_ret']['registers'])


def compare_bus_core(lib, case, memory, regs, flags, device, original):
    native_memory = bytearray(memory)
    native_device = copy.deepcopy(device)
    callbacks = CallbackBus(native_memory, native_device)
    call = Call(regs['ds'], regs['ss'], regs['sp'], flags)
    result = lib.lmn_write_steel_interaction_cells_bus_core(
        memory_view(native_memory), ctypes.byref(call), ctypes.byref(callbacks.bus))
    state = dict(zip(RESULT_FIELDS, result_tuple(result)))
    actual_registers = dict(regs)
    actual_registers.update(ax=state['value'], bx=state['cell_cursor'],
        cx=state['records_remaining'], dx=state['dimensions'],
        di=state['definition_cursor'], sp=state['stack_offset'])
    expected_registers = expected_core_registers(original)
    for name in fixtures.oracle.REG_NAMES:
        if name == 'ip':
            continue
        require(actual_registers[name] == expected_registers[name],
                f'{case["name"]}: core {name} differs: '
                f'{actual_registers[name]:04x} vs {expected_registers[name]:04x}')
    require(((result.flags ^ original['before_ret']['flags']) & DEFINED_FLAGS) == 0,
            f'{case["name"]}: core final defined flags differ')
    require(native_memory == original['before_ret']['memory'],
            f'{case["name"]}: core whole RAM differs before RET')
    expected_events = [event for event in original['events']
                       if event[5] != RET]
    compare_events(callbacks.events, expected_events, case['name'])
    actual_device = device_snapshot(native_device)
    expected_device = original['before_ret']['device']
    require(actual_device == expected_device,
            f'{case["name"]}: core provider state differs before RET: '
            f'actual controls/latches={actual_device[1:] if actual_device else None}, '
            f'original={expected_device[1:] if expected_device else None}')
    return dict(events=len(callbacks.events), sites=original['sites'],
                edges=original['edges'])


def compare_bus_adapter(lib, case, memory, regs, flags, device, original):
    native_memory = bytearray(memory)
    native_device = copy.deepcopy(device)
    callbacks = CallbackBus(native_memory, native_device)
    native_regs = Regs(**regs, flags=flags)
    lib.lmn_write_steel_interaction_cells_bus_adapter(
        memory_view(native_memory), ctypes.byref(native_regs),
        ctypes.byref(callbacks.bus))
    expected = original['after_ret']
    for name in fixtures.oracle.REG_NAMES:
        got = getattr(native_regs, name)
        wanted = expected['registers'][name]
        require(got == wanted,
                f'{case["name"]}: adapter {name} differs: {got:04x} vs {wanted:04x}')
    require(((native_regs.flags ^ expected['flags']) & DEFINED_FLAGS) == 0,
            f'{case["name"]}: adapter defined flags differ')
    require(native_memory == expected['memory'],
            f'{case["name"]}: adapter whole RAM differs after RET')
    require(device_snapshot(native_device) == expected['device'],
            f'{case["name"]}: adapter provider state differs after RET')
    compare_events(callbacks.events, original['events'], case['name'])
    return dict(events=len(callbacks.events), ret_target=original['ret_target'])


def extra_cases():
    record = fixtures.record
    definitions = fixtures.definitions_with
    return [
        dict(name='vga-provider-steel-definitions', seed=0xA381,
             definitions=definitions(((0, record(0x12, 0x85, 0x21, 1)),
                                     (17, record(0x08, 0x03, 0xf0, 0x80))),),
             ds=0xa000, ss=0x7000, sp=0xf000, provider_source=True,
             df=True, iflag=True),
        dict(name='vga-ss-cells-and-live-stack', seed=0xA382,
             definitions=definitions(((0, record(0x12, 0x85, 0x21, 1)),)),
             ds=0x6000, ss=0xa000, sp=0x8000, vga=True,
             return_word=0xed00),
        dict(name='vga-ss-word-physical-wrap', seed=0xA383,
             definitions=definitions(((0, record(0x03, 0x85, 0x11, 0)),)),
             ds=0x6000, ss=0xa000, sp=0x0001, vga=True,
             return_word=0xbeef, df=True),
        dict(name='vga-live-saved-dx-alias', seed=0xA384,
             definitions=definitions(((0, record(0xa9, 0x09, 0x00, 0)),)),
             # 12h + 2*A9h + 416*9 = 1004h, the saved DX low byte.
             ds=0x6000, ss=0xa000, sp=0x1006, vga=True,
             return_word=0xd00d),
        dict(name='vga-live-ret-overwrite', seed=0xA385,
             definitions=definitions(((0, record(0xa8, 0x09, 0, 0)),)),
             # 12h + 2*A8h + 416*9 = 1002h, the live outer RET word.
             ds=0x6000, ss=0xa000, sp=0x1002, vga=True,
             return_word=0xed00, expected_ret_target=0xed09),
        dict(name='ret-20-bit-wrap-fffff-to-00000', seed=0xA386,
             definitions=definitions(()), ds=0x6000, ss=0xffff, sp=0x000f,
             return_word=0xcafe),
        dict(name='ret-ss-ffff-sp-ffff-physical-successor', seed=0xA387,
             definitions=definitions(()), ds=0x6000, ss=0xffff, sp=0xffff,
             return_word=0x91ab),
    ]


def prepared(case):
    memory, regs, flags = fixtures.prepare(case)
    device = configure_vga(memory, case) if case.get('vga') or case.get('provider_source') else None
    return memory, regs, flags, device


def compile_library(output, mutation):
    command = [compiler(), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-shared', f'-DSTEEL_BUS_MUTATION={mutation}', '-I', str(ROOT / 'c'),
        str(ROOT / 'c/steel_cells_bus.c'), str(ROOT / 'c/steel_cells.c'),
        '-o', str(output)]
    run_bounded(command, cwd=ROOT, timeout=60, memory_mib=256)


def run_worker(directory):
    hashes_path = Path(directory) / 'steel-cells-bus-input-hashes.json'
    expected_hashes = json.loads(hashes_path.read_text(encoding='utf-8'))
    verify_input_hashes(expected_hashes)
    baseline, consumed_assets = fixtures.cases()
    if len(baseline) != 386:
        raise VerificationFailure(f'RAM regression fixture count changed: {len(baseline)}')
    if fixtures.ROUTINE['address'] != 0x3839 or fixtures.ROUTINE['size'] != 102:
        raise VerificationFailure('Unexpected WriteSteelInteractionCells ledger boundary')
    if len(fixtures.INS) != 47 or sum(i.size for i in fixtures.INS.values()) != 102:
        raise VerificationFailure('Unexpected decoded steel routine sites or byte count')

    old_lib = load_library(directory, 0)
    bus_lib = load_library(directory, 0)
    observed_sites, observed_edges = set(), set()
    total_events = 0
    report_cases = []

    for index, case in enumerate(baseline):
        memory, regs, flags, device = prepared(case)
        compare_null_abi(old_lib, bus_lib, case, memory, regs, flags)
        original = OriginalRun(case, bytearray(memory), regs, flags,
                               copy.deepcopy(device)).run()
        result = compare_bus_core(bus_lib, case, memory, regs, flags, device, original)
        total_events += result['events']
        observed_sites.update(result['sites'])
        observed_edges.update(result['edges'])

        # Preserve the old independent footprint check for ordinary RAM inputs.
        if not case.get('stack_alias') and device is None:
            footprint, stale = fixtures.independent_cells(memory, regs)
            after = original['before_ret']['memory']
            for address in footprint:
                require(after[address] == 0x09,
                        f'{case["name"]}: independent SS cell value differs at {address:05x}')
            for address in stale - footprint:
                if address not in (physical(regs['ss'], regs['sp'] - 2),
                                   physical(regs['ss'], regs['sp'] - 1),
                                   physical(regs['ss'], regs['sp'] - 4),
                                   physical(regs['ss'], regs['sp'] - 3)):
                    require(after[address] == memory[address],
                            f'{case["name"]}: stale SS byte changed at {address:05x}')

        report_cases.append(dict(name=case['name'], events=result['events'],
            sites=len(result['sites']), edges=len(result['edges']),
            real_level=bool(case.get('real')), df=bool(flags & fixtures.DF)))
        del original, result, memory, regs, device
        if index % 8 == 7:
            gc.collect()

    if observed_sites != set(fixtures.INS):
        raise VerificationFailure(
            f'Original site coverage differs: missing={sorted(set(fixtures.INS)-observed_sites)}')
    if observed_edges != fixtures.EDGES:
        raise VerificationFailure(
            f'Original edge coverage differs: missing={sorted(fixtures.EDGES-observed_edges)}')

    extra_reports = []
    extras = extra_cases()
    for case in extras:
        memory, regs, flags, device = prepared(case)
        original = OriginalRun(case, bytearray(memory), regs, flags,
                               copy.deepcopy(device)).run()
        expected_target = case.get('expected_ret_target',
                                    case.get('return_word', 0xff00))
        if original['ret_target'] != expected_target:
            raise VerificationFailure(
                f'{case["name"]}: original RET read {original["ret_target"]:04x}, '
                f'expected live word {expected_target:04x}')
        core = compare_bus_core(bus_lib, case, memory, regs, flags, device, original)
        if case['name'] == 'vga-live-saved-dx-alias':
            first_cell = 0x1004
            saved_dx_low = physical(case['ss'], case['sp'] - 2)
            cell_writes = [event for event in original['events']
                           if event[0] == 'write' and event[5] == 0x3886]
            expected_addresses = [
                physical(0xa000, (first_cell + row * 0x1a0) & 0xffff)
                for row in range(9)]
            if (expected_addresses[0] != saved_dx_low or
                    [event[1] for event in cell_writes] != expected_addresses):
                raise VerificationFailure(
                    f'{case["name"]}: expected nine cell writes after the '
                    f'saved-DX alias, in row order; observed '
                    f'{[hex(event[1]) for event in cell_writes]}, expected '
                    f'{[hex(address) for address in expected_addresses]}')
        adapter = compare_bus_adapter(bus_lib, case, memory, regs, flags,
                                      device, original)
        total_events += core['events'] + adapter['events']
        observed_sites.update(core['sites'])
        observed_edges.update(core['edges'])
        extra_reports.append(dict(name=case['name'], core_events=core['events'],
            adapter_events=adapter['events'], ret_target=adapter['ret_target'],
            device=('A0000 planar provider' if device is not None else 'RAM'),
            df=bool(flags & fixtures.DF)))
        del original, core, adapter, memory, regs, device
        gc.collect()

    witnesses = {
        1: 'byte3-alone-keeps-record-active',
        2: 'x-bit7-contributes-one',
        3: 'dimensions-01',
        4: 'byte3-alone-keeps-record-active',
    }
    by_name = {case['name']: case for case in baseline}
    mutations = []
    for mutation, name in witnesses.items():
        case = by_name[name]
        memory, regs, flags, device = prepared(case)
        original = OriginalRun(case, bytearray(memory), regs, flags,
                               copy.deepcopy(device)).run()
        mutant = load_library(directory, mutation)
        try:
            compare_bus_core(mutant, case, memory, regs, flags, device, original)
        except Mismatch:
            mutations.append(dict(mutation=mutation, case=name,
                                  outcome='completed differential mismatch'))
        else:
            raise VerificationFailure(f'Compiled mutation {mutation} survived on {name}')
        del original, memory, regs, device, mutant
        gc.collect()

    if len(mutations) != 4:
        raise VerificationFailure('Not all four compiled steel-cell mutations were detected')

    current_hashes = verify_input_hashes(expected_hashes)
    if not set(consumed_assets).issubset(current_hashes):
        raise VerificationFailure('not all consumed level assets were hashed')
    write_json(BUILD / 'steel-cells-bus-differential.json', dict(
        image='main', image_sha256=sha(fixtures.IMAGE),
        case_count=len(baseline) + len(extras),
        historical_ram_case_count=len(baseline), extra_provider_case_count=len(extras),
        bus_core_case_count=len(baseline) + len(extras),
        null_bus_core_case_count=len(baseline),
        null_bus_adapter_case_count=len(baseline),
        bus_adapter_case_count=len(extras),
        compiled_mutation_probe_count=len(mutations),
        probe_count=len(mutations),
        provider_case_count=len(extras),
        cases=report_cases, provider_cases=extra_reports,
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in fixtures.INS.values()),
        executed_instruction_addresses=sorted(observed_sites),
        native_code_ranges=[[0x3839, 0x389f]],
        original_instruction_sites=sorted(observed_sites),
        original_branch_edges=sorted([list(edge) for edge in observed_edges]),
        total_bus_events=total_events,
        routine=dict(name=fixtures.ROUTINE['symbol_name'], start=fixtures.ENTRY,
            end=fixtures.END, byte_count=fixtures.END-fixtures.ENTRY,
            bytes=fixtures.IMAGE[fixtures.ENTRY:fixtures.END].hex(),
            byte_sha256=sha(fixtures.IMAGE[fixtures.ENTRY:fixtures.END])),
        input_hashes=current_hashes,
        fixture_domains=dict(null_bus_core_and_adapter_abi=True,
            direct_bus_core=True, adapter_consumes_live_ret=True,
            real_level_sections=80, VGA_provider_reads=True,
            VGA_SS_cell_and_stack_writes=True, SS_offset_wrap=True,
            live_saved_DX_alias=True, live_return_word_overwrite=True,
            all_47_sites=True, all_8_edges=True, max_bus_events=MAX_BUS_EVENTS),
        flag_contract=('Ordered byte callbacks receive instruction-entry flags. '
            'The trace masks AF only while architecturally undefined, checks only '
            'CF/OF after MUL, retains CF across INC/DEC, and checks all arithmetic '
            'bits again after ADD DI,4.'),
        domain=('Bus-aware direct core and adapter for CS:3839..389E; canonical '
            'RAM/VGA/SS stack, definition bytes in 0/1/2/3 order, physical word '
            'adjacency, live PUSH/POP/RET aliases, instruction-phase flags and '
            'unchecked packed row/dimension arithmetic.')))
    print(f'PASS steel interaction cells bus C: {len(baseline)} RAM cases, '
          f'{len(extras)} VGA/provider cases, {len(observed_sites)} sites, '
          f'{len(observed_edges)} edges, {len(mutations)} compiled mutations')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        run_worker(sys.argv[2])
        return

    BUILD.mkdir(parents=True, exist_ok=True)
    input_hashes = collect_input_hashes()
    (BUILD / 'steel-cells-bus-differential.json').unlink(missing_ok=True)
    with temporary_build_directory(prefix='steel-cells-bus-', parent=BUILD) as directory:
        (Path(directory) / 'steel-cells-bus-input-hashes.json').write_text(
            json.dumps(input_hashes, sort_keys=True), encoding='utf-8')
        for mutation in range(5):
            compile_library(Path(directory) / f'steel-cells-bus-m{mutation}.dll',
                            mutation)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', directory], cwd=ROOT, timeout=120,
                    memory_mib=512)


if __name__ == '__main__':
    main()
