"""Bounded raster-bus checks for the 5DC6 entity-pixel leaf."""
import copy
import ctypes
import gc
import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
import entity_pixel as fixtures
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as x


SIZE = 1 << 20
MASK = SIZE - 1
LOAD = fixtures.LOAD
ENTRY, RET, END = 0x5DC6, 0x5DF7, 0x5DF8
CODE = fixtures.IMAGE[ENTRY:END]
MAX_EVENTS = 64
MAX_INSTRUCTIONS = 100
GUARD_EXIT, CALLBACK_EXIT = 86, 87
ALL_DEFINED_FLAGS = 0x0FD7
MUL_CALLBACK_FLAGS = 0x0F01  # CF/OF from MUL, plus preserved TF/IF/DF.
MUTATION_CASE = 'pinned-mask-index-0'
REPORT = BUILD / 'entity-pixel-bus-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {instruction.address: instruction
       for instruction in MD.disasm(CODE, ENTRY)}
BRANCHES = {pc for pc, instruction in INS.items()
            if instruction.group(capstone.CS_GRP_JUMP)}
REG_ID = fixtures.REG_ID
REGS = fixtures.REGS


READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The bounded original execution or one of its providers failed."""


class Mismatch(AssertionError):
    """A completed native/original bus comparison differs."""


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


def set_word(memory, address, value):
    memory[address & MASK] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def set_plane_word(device, offset, value, plane=0):
    device.planes[plane][offset & 0xFFFF] = value & 0xFF
    device.planes[plane][(offset + 1) & 0xFFFF] = (value >> 8) & 0xFF


def selected_cases():
    old = {case['name']: case for case in fixtures.cases()}
    names = [*(f'pinned-mask-index-{i}' for i in range(8)),
             'y-boundary-0000', 'y-boundary-000f', 'y-boundary-0010',
             'y-boundary-8000', 'y-boundary-800f', 'y-boundary-8010',
             'y-boundary-ffff', 'x-logical-shift-high-bit',
             'row-product-low-word-wrap', 'record-physical-word-wrap',
             'stack-physical-word-wrap', 'stack-sp-ffff', 'ds-ss-x-alias',
             'ds-ss-y-alias', 'ds-ss-table-alias', 'seeded-coordinate-0',
             'seeded-coordinate-3']
    cases = [dict(old[name]) for name in names]
    cases.extend((
        dict(name='vga-ds-record-and-table', seed=0xA501,
             ds=0xA000, ss=0x5200, si=0x1230, sp=0x8000,
             x=0x123B, y=0x0022, vga_ds=True),
        dict(name='vga-ss-push-pop-and-ret', seed=0xA502,
             ds=0x3000, ss=0xA000, si=0x1000, sp=0x5480,
             x=0x0123, y=0x0030, return_word=0xBEEF, vga_ss=True),
        dict(name='provider-y-read-changes-future-x', seed=0xA503,
             ds=0x3000, ss=0x5100, si=0x1000, sp=0x8100,
             x=0x0001, y=0x0022, mutate='y-to-x'),
        dict(name='provider-x-read-changes-future-table', seed=0xA504,
             ds=0x3100, ss=0x5200, si=0x1100, sp=0x8200,
             x=0x0005, y=0x0029,
             table_mode='custom',
             table_bytes=bytes.fromhex('19 A7 33 5C E2 B6 71 0D'),
             mutate='x-to-table'),
        dict(name='provider-ret-low-read-changes-high', seed=0xA505,
             ds=0x3200, ss=0x5300, si=0x1200, sp=0x8300,
             x=0x1357, y=0x0032, return_word=0x3412,
             mutate='ret-low-to-high'),
    ))
    require_count = 30
    if len(cases) != require_count:
        raise OracleFailure(f'Entity pixel bus case count changed: {len(cases)}')
    return cases


def setup_device(case, memory, regs):
    if not case.get('vga_ds') and not case.get('vga_ss'):
        return None
    device = MinimapVga(case['seed'], read_map=0)
    device.seq[2] = 1
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[8] = 0xFF
    if case.get('vga_ds'):
        xvalue = case['x']
        yvalue = case['y']
        ds = regs['ds']
        si = regs['si']
        set_plane_word(device, physical(ds, si) - VGA_BASE, xvalue)
        set_plane_word(device, physical(ds, (si + 2) & 0xFFFF) - VGA_BASE,
                       yvalue)
        device.planes[0][0x547C + (xvalue & 7)] = 0xD3
    if case.get('vga_ss'):
        # Mode-0/map-mask-1 writes let PUSH DX feed the following POP DX.
        sp = regs['sp']
        set_plane_word(device, sp, case['return_word'])
    return device


def prepare(case):
    memory, regs = fixtures.prepare(case)
    device = setup_device(case, memory, regs)
    return memory, regs, device


def side_effects(case, regs):
    ds, ss, si, sp = regs['ds'], regs['ss'], regs['si'], regs['sp']
    if case.get('mutate') == 'y-to-x':
        return [(physical(ds, (si + 2) & 0xFFFF),
                 physical(ds, si), bytes.fromhex('D5 02'))]
    if case.get('mutate') == 'x-to-table':
        index = case['x'] & 7
        return [(physical(ds, si), physical(ds, 0x547C + index), b'\xE9')]
    if case.get('mutate') == 'ret-low-to-high':
        return [(physical(ss, sp), (physical(ss, sp) + 1) & MASK, b'\xAC')]
    return []


class NativeBus:
    """Small callback bus with a hard process-level trace and failure guard."""
    def __init__(self, memory, device, effects):
        self.memory = memory
        self.device = device
        self.effects = list(effects)
        self.events = []
        self.used_effects = set()

        def reserve():
            if len(self.events) >= MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native entity-pixel bus trace cap exhausted')

        def apply_effect(address):
            for n, (trigger, target, data) in enumerate(self.effects):
                if n not in self.used_effects and address == trigger:
                    self.used_effects.add(n)
                    for offset, value in enumerate(data):
                        self.memory[(target + offset) & MASK] = value

        def read(_context, _mem, address, flags):
            try:
                address &= MASK
                reserve()
                if self.device and VGA_BASE <= address < VGA_END:
                    value = self.device.read(self.memory, address, flags)
                else:
                    value = self.memory[address]
                self.events.append(('read', address, value & 0xFF, flags & 0xFFFF))
                apply_effect(address)
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native VGA trace cap exhausted')
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
                if self.device and len(self.device.trace) > MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native VGA trace cap exhausted')
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native write callback failed: {type(error).__name__}: {error}')

        self._read, self._write = READ(read), WRITE(write)
        self._out = OUT()
        self.bus = RasterBus(None, self._read, self._write, self._out)


class OriginalRun:
    def __init__(self, case, memory, regs, device, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.core = device, core
        self.events, self.sites, self.edges = [], set(), set()
        self.previous = None
        self.current_offset = None
        self.current_flags = 0
        self.failure = None
        self.stopped = False
        self.ret_target = None
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

        effects = side_effects(case, regs)
        used_effects = set()

        def apply_effect(address):
            for n, (trigger, target, data) in enumerate(effects):
                if n not in used_effects and address == trigger:
                    used_effects.add(n)
                    for offset, value in enumerate(data):
                        p = (target + offset) & MASK
                        memory[p] = value
                        mirror(p, p, value)

        def add_event(kind, address, value):
            if len(self.events) >= MAX_EVENTS:
                fail(f'{case["name"]}: original bus trace cap exhausted')
                return
            self.events.append((kind, address & MASK, value & 0xFF,
                                self.current_flags & 0xFFFF))

        def code(uc, address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous == RET:
                self.ret_target = off
                self.stopped = True
                uc.emu_stop()
                return
            if self.previous in BRANCHES:
                self.edges.add((self.previous, off))
            if cs != regs['cs'] or off not in INS:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if off == RET and self.core:
                self.stopped = True
                uc.emu_stop()
                return
            if len(self.sites) >= MAX_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.sites.add(off)
            self.current_offset = off
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
                    if self.device and VGA_BASE <= p < VGA_END:
                        value = self.device.read(memory, p, self.current_flags)
                    else:
                        value = memory[p]
                    add_event('read', p, value)
                    if self.failure:
                        return
                    mirror(linear, p, value)
                    apply_effect(p)
            except BaseException as error:
                fail(f'{case["name"]}: original read provider failed: '
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
                        self.device.write(memory, p, byte, self.current_flags)
                    else:
                        memory[p] = byte
                    add_event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
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
            raise OracleFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original did not stop at declared boundary')
        oracle_require(len(self.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original bus budget exhausted')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        if not self.core:
            oracle_require(self.previous == RET and self.ret_target is not None,
                           f'{self.case["name"]}: original RET did not complete')
        return dict(memory=bytes(self.cpu.mem_read(0, SIZE)), state=state,
                    events=self.events, sites=self.sites, edges=self.edges,
                    device=self.device, ret_target=self.ret_target)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-pixel-bus-m{mutation}.dll',
                     mutation, 'entity_pixel')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_prepare_entity_pixel_core
        self.core.argtypes = [MEM, ctypes.POINTER(fixtures.Call)]
        self.core.restype = fixtures.CoreResult
        self.bus_core = self.library.lmn_prepare_entity_pixel_bus_core
        self.bus_core.argtypes = [MEM, ctypes.POINTER(fixtures.Call),
                                  ctypes.POINTER(RasterBus)]
        self.bus_core.restype = fixtures.CoreResult
        self.adapter = self.library.lmn_prepare_entity_pixel_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs)]
        self.adapter.restype = None
        self.bus_adapter = self.library.lmn_prepare_entity_pixel_bus_adapter
        self.bus_adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                     ctypes.POINTER(RasterBus)]
        self.bus_adapter.restype = None


def c_buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


def expected_event_masks(case, regs, *, core):
    y = case.get('y', 0x0027)
    row = (y - 0x10) & 0xFFFF
    push_mask = ALL_DEFINED_FLAGS if not row & 0x8000 else (ALL_DEFINED_FLAGS & ~0x10)
    masks = [ALL_DEFINED_FLAGS] * 2 + [push_mask] * 2
    masks.extend([MUL_CALLBACK_FLAGS] * 4)
    masks.extend([ALL_DEFINED_FLAGS])  # table read follows final ADD BX,547Ch.
    if not core:
        masks.extend([ALL_DEFINED_FLAGS] * 2)
    return masks


def expected_addresses(case, regs, original_state, *, core):
    yaddr = physical(regs['ds'], (regs['si'] + 2) & 0xFFFF)
    pushed = (regs['sp'] - 2) & 0xFFFF
    psp = physical(regs['ss'], pushed)
    xaddr = physical(regs['ds'], regs['si'])
    table = physical(regs['ds'], original_state['bx'])
    entries = [('read', yaddr), ('read', (yaddr + 1) & MASK),
               ('write', psp), ('write', (psp + 1) & MASK),
               ('read', psp), ('read', (psp + 1) & MASK),
               ('read', xaddr), ('read', (xaddr + 1) & MASK),
               ('read', table)]
    if not core:
        ret = physical(regs['ss'], regs['sp'])
        entries.extend((('read', ret), ('read', (ret + 1) & MASK)))
    return entries


def compare_events(case, actual, expected, regs, expected_state, *, core):
    wanted_addresses = expected_addresses(case, regs, expected_state, core=core)
    masks = expected_event_masks(case, regs, core=core)
    require(len(actual) == len(expected) == len(wanted_addresses) == len(masks),
            f'{case["name"]}: bus event count/order shape differs')
    for index, (got, oracle, wanted) in enumerate(zip(actual, expected, wanted_addresses)):
        kind, address, value, flags = got
        exp_kind, exp_address, exp_value, exp_flags = oracle
        want_kind, want_address = wanted
        require((kind, address) == (want_kind, want_address),
                f'{case["name"]}: native bus address/order differs at {index}: {got!r}')
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
                f'{case["name"]}: native bus value differs at {index}')
        require(((flags ^ exp_flags) & masks[index]) == 0,
                f'{case["name"]}: bus flags differ at {index}: '
                f'{flags:04X}/{exp_flags:04X} mask={masks[index]:04X}')


def compare_device(case, actual, expected):
    if expected is None:
        require(actual is None, f'{case["name"]}: unexpected VGA device')
        return
    require(actual is not None and actual.state() == expected.state(),
            f'{case["name"]}: VGA planes/latches/registers differ')


def compare_case(native, case, *, core):
    initial, initial_regs, initial_device = prepare(case)
    oracle_memory = bytearray(initial)
    oracle_device = copy.deepcopy(initial_device)
    oracle = OriginalRun(case, oracle_memory, dict(initial_regs), oracle_device,
                         core=core).run()

    native_memory = bytearray(initial)
    native_device = copy.deepcopy(initial_device)
    callbacks = NativeBus(native_memory, native_device,
                          side_effects(case, initial_regs))
    state = dict(initial_regs)
    if core:
        call = fixtures.Call(state['ds'], state['ss'], state['sp'], state['si'],
                             state['dx'], state['flags'])
        result = native.bus_core(c_buffer(native_memory), ctypes.byref(call),
                                 ctypes.byref(callbacks.bus))
        state.update(ax=result.value, bx=result.table_cursor,
                     cx=result.column_byte, di=result.destination_offset,
                     dx=result.restored_value, es=0xA000,
                     sp=result.stack_offset, flags=result.flags, ip=RET)
    else:
        live = Regs(**{name: state[name] for name in REGS}, flags=state['flags'])
        native.bus_adapter(c_buffer(native_memory), ctypes.byref(live),
                           ctypes.byref(callbacks.bus))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags

    for name in REGS:
        require(state[name] == oracle['state'][name],
                f'{case["name"]} {"core" if core else "adapter"} {name} differs: '
                f'{state[name]:04X}/{oracle["state"][name]:04X}')
    require(((state['flags'] ^ oracle['state']['flags']) & ALL_DEFINED_FLAGS) == 0,
            f'{case["name"]}: final defined flags differ')
    require(bytes(native_memory) == oracle['memory'],
            f'{case["name"]}: full canonical RAM differs')
    compare_device(case, native_device, oracle['device'])
    compare_events(case, callbacks.events, oracle['events'], initial_regs,
                   oracle['state'], core=core)
    oracle_require((oracle['sites'] <= set(INS)) and oracle['edges'] <= {
        (0x5DD1, 0x5DD3), (0x5DD1, 0x5DD5)},
        f'{case["name"]}: original escaped declared sites/edges')
    if not core:
        oracle_require(oracle['state']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       f'{case["name"]}: actual near RET did not consume its word')
    return oracle['sites'], oracle['edges'], len(callbacks.events)


def compare_null_bus(native, case):
    memory, regs, _device = prepare(case)
    old_memory, new_memory = bytearray(memory), bytearray(memory)
    call = fixtures.Call(regs['ds'], regs['ss'], regs['sp'], regs['si'],
                         regs['dx'], regs['flags'])
    old = native.core(c_buffer(old_memory), ctypes.byref(call))
    new = native.bus_core(c_buffer(new_memory), ctypes.byref(call), None)
    require(bytes(old) == bytes(new),
            f'{case["name"]}: old/null-bus core result changed')
    require(old_memory == new_memory,
            f'{case["name"]}: old/null-bus core RAM changed')

    old_memory, new_memory = bytearray(memory), bytearray(memory)
    old_regs = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
    new_regs = Regs(**{name: regs[name] for name in REGS}, flags=regs['flags'])
    native.adapter(c_buffer(old_memory), ctypes.byref(old_regs))
    native.bus_adapter(c_buffer(new_memory), ctypes.byref(new_regs), None)
    require(bytes(old_regs) == bytes(new_regs),
            f'{case["name"]}: old/null-bus adapter registers changed')
    require(old_memory == new_memory,
            f'{case["name"]}: old/null-bus adapter RAM changed')


def worker(directory):
    paths = ('assets/vgalemmi.exe', 'metadata/symbols.json', 'metadata/hints.json',
             'metadata/regions.json', 'metadata/inputs.json', 'c/entity_pixel.c',
             'c/entity_pixel.h', 'c/special_blit.h', 'c/lemmings_sym.h',
             'c/regs.h', 'tests/entity_pixel.py', 'tests/entity_pixel_bus.py',
             'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
             'docs/entity-pixel.md', 'tools/cbuild.py', 'tools/difftest.py',
             'tools/coverage.py', 'tools/bounded_process.py', 'tools/unpack.py',
             'tools/common.py')
    before_hashes = {path: sha((ROOT / path).read_bytes()) for path in paths}
    oracle_require(sha(fixtures.ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(fixtures.IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(CODE) == 50 and len(INS) == 22,
                   'Entity pixel routine accounting changed')
    cases = selected_cases()
    baseline = Native(directory)
    mutant = Native(directory, 5)
    coverage, edges, rows = set(), set(), []
    total_events = 0
    for case in cases:
        compare_null_bus(baseline, case)
        observed_sites, observed_edges, case_events = set(), set(), 0
        for core in (True, False):
            sites, branch_edges, event_count = compare_case(baseline, case, core=core)
            observed_sites.update(sites)
            observed_edges.update(branch_edges)
            case_events += event_count
        coverage.update(observed_sites)
        edges.update(observed_edges)
        total_events += case_events
        rows.append(dict(name=case['name'], bus_events=case_events,
                         executed_instruction_addresses=sorted(observed_sites),
                         branch_edges=sorted(observed_edges),
                         core_and_adapter=True,
                         vga=bool(case.get('vga_ds') or case.get('vga_ss')),
                         provider_mutation=case.get('mutate')))

    mutation_case = next(case for case in cases if case['name'] == MUTATION_CASE)
    try:
        compare_case(mutant, mutation_case, core=True)
    except Mismatch as error:
        mutation = dict(mutation=5, name='bus-bypass', case=MUTATION_CASE,
                        mismatch=str(error), completed=True)
    else:
        raise OracleFailure('Entity pixel bus bypass mutant survived')
    oracle_require(coverage == set(INS),
                   'Entity pixel bus original site coverage differs')
    oracle_require(edges == {(0x5DD1, 0x5DD3), (0x5DD1, 0x5DD5)},
                   f'Entity pixel bus branch edges differ: {sorted(edges)}')

    input_hashes = {path: sha((ROOT / path).read_bytes()) for path in paths}
    oracle_require(input_hashes == before_hashes,
                   'Entity pixel bus inputs changed during the bounded run')
    write_json(REPORT, dict(image='main', image_sha256=sha(fixtures.IMAGE),
        case_count=len(rows), auxiliary_core_cases=len(rows),
        mutation_count=1, mutations=[mutation], cases=rows,
        translated_code_bytes=50, native_code_ranges=[[ENTRY, END]],
        routine_bytes=CODE.hex(), executed_instruction_addresses=sorted(coverage),
        instruction_sites=sorted(coverage), instruction_site_count=len(coverage),
        branch_instruction_addresses=sorted(BRANCHES), branch_edges=sorted(edges),
        total_bus_events=total_events, domains=[
            'optional raster bus on every RAM/VGA byte access; null-bus legacy ABI equality',
            'ordered Y, PUSH DX, POP DX, X, live mask-table and actual RET accesses',
            'low-byte then next physical-byte word accesses with 16-bit offset and 20-bit physical wrap',
            'defined callback flags at SUB/XOR, MUL, final ADD, and retained TF/IF/DF',
            'DS and SS VGA aperture reads/writes through independent four-plane state',
            'provider reads that modify future X, table data, and the high RET byte',
            'complete RAM, returned registers, defined flags, and VGA planes/latches/registers'],
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    native_callback_events=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=input_hashes))
    print(f'PASS entity pixel bus C: {len(rows)} cases, {total_events} bus events, '
          f'{len(coverage)} sites, {len(edges)} JNS edges, 1 completed mutant',
          flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-pixel-bus-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory], cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
