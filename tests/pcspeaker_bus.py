"""Bounded original-vs-C checks for the PC-speaker effect and stop bus APIs."""
from __future__ import annotations

import copy
import ctypes as ct
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from resources import sound_images
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x

SIZE = 1 << 20
PHYSICAL_MASK = SIZE - 1
FLAG_MASK = 0x0FD7
EFFECT_FLAGS = 0x0FD7
STOP_FLAGS = 0x0FC7
EVENT_CAP = 96
INSTRUCTION_CAP = 128
REPORT = BUILD / 'pcspeaker-bus-differential.json'
IMAGE, IMAGE_META = sound_images()['pcspeaker']

REG_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
             'cs', 'ds', 'es', 'ss', 'ip', 'flags')
REG_IDS = {name: getattr(x, 'UC_X86_REG_' + name.upper())
           for name in REG_NAMES if name != 'flags'}
REG_IDS['flags'] = x.UC_X86_REG_EFLAGS
MEM = ct.POINTER(ct.c_uint8)


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in REG_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('ax', 'bx', 'cx', 'dx', 'si', 'flags', 'defined_flags_mask')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32,
                     ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """A completed C-vs-original comparison found different behavior."""


class CallbackLimit(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & PHYSICAL_MASK


def put_byte(memory, address, value):
    memory[address & PHYSICAL_MASK] = value & 0xFF


def put_word(memory, address, value):
    address &= PHYSICAL_MASK
    memory[address] = value & 0xFF
    memory[(address + 1) & PHYSICAL_MASK] = (value >> 8) & 0xFF


def get_word(memory, address):
    address &= PHYSICAL_MASK
    return memory[address] | (memory[(address + 1) & PHYSICAL_MASK] << 8)


def flags_mask(kind):
    return EFFECT_FLAGS if kind == 'effect' else STOP_FLAGS


def setup(case):
    rng = random.Random(0x5A6D + case['seed'] * 19)
    memory = bytearray(rng.randbytes(SIZE))
    cs = case.get('cs', 0x3400)
    ds = case.get('ds', 0x5100)
    ss = case.get('ss', 0x6200)
    sp = case.get('sp', 0x8000)
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    regs.update(cs=cs, ds=ds, ss=ss, es=0x4600, sp=sp,
                ip=case['entry'], flags=case.get('flags',
                    2 | (rng.randrange(0x10000) & 0x0ED5)))
    if case.get('df'):
        regs['flags'] |= 0x0400
    else:
        regs['flags'] &= ~0x0400
    regs['flags'] |= 2
    if case['kind'] == 'effect':
        regs['ax'] = (rng.randrange(0x100) << 8) | case['effect']
    else:
        regs['ax'] = (rng.randrange(0x100) << 8) | rng.randrange(0x100)

    # Only the two identified leaves need executable backing.
    start = physical(cs, 0)
    memory[start:start + len(IMAGE)] = IMAGE
    return_ip = case.get('return_ip', 0xE321)
    put_word(memory, physical(ss, sp), return_ip)

    if case.get('provider') == 'reload-last-byte':
        put_byte(memory, physical(ds, 0x17), 0x34)
        put_byte(memory, physical(ds, 0x18), 0x12)
        # LoadEffect(0) copies source byte 0x32 to destination byte 0x18.
        put_byte(memory, physical(ds, 0x32), 0x56)

    device = None
    if case.get('vga'):
        device = MinimapVga(0x5A00 + case['seed'], read_map=case.get('read_map', 0))
        device.seq[2] = 0x0F
        device.seq[4] = 0x06
        device.gc[0] = device.gc[1] = device.gc[2] = device.gc[3] = 0
        device.gc[4] = case.get('read_map', 0)
        device.gc[5] = 0
        device.gc[6] = 0x05
        device.gc[7] = 0
        device.gc[8] = 0xFF
        if ss == 0xA000:
            offset = sp & 0xFFFF
            plane = device.planes[case.get('read_map', 0)]
            plane[offset] = return_ip & 0xFF
            plane[(offset + 1) & 0xFFFF] = (return_ip >> 8) & 0xFF
    return memory, regs, device


def cases():
    result = [dict(name=f'effect-al-{effect:02x}', kind='effect', effect=effect,
                   seed=effect, entry=0x01B0)
              for effect in range(256)]
    result.extend([
        dict(name='effect-reload-provider', kind='effect', effect=0, seed=300,
             entry=0x01B0, provider='reload-last-byte'),
        dict(name='effect-live-active-provider', kind='effect', effect=0, seed=301,
             entry=0x01B0, provider='active-after-first-copy'),
        dict(name='effect-return-provider', kind='effect', effect=0, seed=302,
             entry=0x01B0, provider='return-after-active'),
        dict(name='effect-return-provider-wrap', kind='effect', effect=0, seed=303,
             entry=0x01B0, provider='return-after-active', ss=0xFFFF, sp=0x000F),
        dict(name='effect-destination-stack-overlap', kind='effect', effect=0,
             seed=304, entry=0x01B0, ds=0x5300, ss=0x5300, sp=0x000A),
        dict(name='effect-source-destination-alias', kind='effect', effect=0xFE,
             seed=305, entry=0x01B0),
        dict(name='effect-physical-memory-wrap', kind='effect', effect=0xFE,
             seed=306, entry=0x01B0, ds=0xFFFF),
        dict(name='effect-vga-data-segment', kind='effect', effect=0, seed=307,
             entry=0x01B0, ds=0xA000, vga=True, read_map=2),
        dict(name='effect-vga-return-stack', kind='effect', effect=1, seed=308,
             entry=0x01B0, ss=0xA000, sp=0x0300, vga=True, read_map=1),
        dict(name='effect-physical-return-wrap', kind='effect', effect=0, seed=309,
             entry=0x01B0, ss=0xFFFF, sp=0x000F),
        dict(name='effect-df-set', kind='effect', effect=0, seed=310,
             entry=0x01B0, df=True),
        dict(name='effect-ds-ss-shared', kind='effect', effect=0xFE, seed=311,
             entry=0x01B0, ds=0x5400, ss=0x5400, sp=0x2000),
        dict(name='stop-basic', kind='stop', seed=400, entry=0x024F),
        dict(name='stop-vga-data-segment', kind='stop', seed=401, entry=0x024F,
             ds=0xA000, vga=True, read_map=3),
        dict(name='stop-active-stack-alias', kind='stop', seed=402, entry=0x024F,
             ds=0x5500, ss=0x5500, sp=0x0001),
        dict(name='stop-vga-return-stack', kind='stop', seed=403, entry=0x024F,
             ss=0xA000, sp=0x0200, vga=True, read_map=2),
        dict(name='stop-physical-return-wrap', kind='stop', seed=404, entry=0x024F,
             ss=0xFFFF, sp=0x000F),
        dict(name='stop-return-provider', kind='stop', seed=405, entry=0x024F,
             provider='return-on-stop-active'),
    ])
    return result


class Access:
    def __init__(self, case, memory, regs, device):
        self.case = case
        self.memory = memory
        self.regs = regs
        self.device = device
        self.events = []
        self.used = set()
        self.mirror = None
        self.active_writes = 0

    def store(self, address, value):
        address &= PHYSICAL_MASK
        self.memory[address] = value & 0xFF
        if self.mirror is not None:
            self.mirror(address, value & 0xFF)

    def provider(self, name):
        if name in self.used:
            return
        self.used.add(name)
        ds = self.regs['ds']
        ss = self.regs['ss']
        sp = self.regs['sp']
        if name == 'reload-last-byte':
            self.store(physical(ds, 0x17), 0xA5)
        elif name == 'active-after-first-copy':
            self.store(physical(ds, 0x01), 0x27)
        elif name in ('return-after-active', 'return-on-stop-active'):
            value = 0xC0DE
            low = physical(ss, sp)
            self.store(low, value & 0xFF)
            self.store((low + 1) & PHYSICAL_MASK, value >> 8)

    def access(self, kind, address, flags, value=None):
        if len(self.events) >= EVENT_CAP:
            raise CallbackLimit('native PC-speaker byte-event budget exhausted')
        address &= PHYSICAL_MASK
        if kind == 'read':
            if self.device is not None and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
            else:
                value = self.memory[address]
            self.store(address, value)
        else:
            if self.device is not None and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF,
                            flags & flags_mask(self.case['kind'])))

        provider = self.case.get('provider')
        if kind == 'write' and provider == 'reload-last-byte' and \
                address == physical(self.regs['ds'], 0x18):
            self.provider(provider)
        elif kind == 'write' and provider == 'active-after-first-copy' and \
                address == physical(self.regs['ds'], 0x0A):
            self.provider(provider)
        elif kind == 'write' and address == physical(self.regs['ds'], 0x01):
            self.active_writes += 1
            if provider == 'return-after-active' and self.active_writes == 2:
                self.provider(provider)
            elif provider == 'return-on-stop-active' and self.active_writes == 1:
                self.provider(provider)
        return value


def normalized_device_trace(device, kind):
    if device is None:
        return None
    mask = flags_mask(kind)
    return tuple(tuple(row[:-1]) + (row[-1] & mask,) for row in device.trace)


def original(case, memory, regs, device, core):
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    image = bytes(memory)
    cpu.mem_write(0, image)
    cpu.mem_write(SIZE, image)
    for name, value in regs.items():
        cpu.reg_write(REG_IDS[name], value)

    access = Access(case, memory, regs, device)

    def mirror(address, value):
        address &= PHYSICAL_MASK
        cpu.mem_write(address, bytes((value,)))
        cpu.mem_write(address + SIZE, bytes((value,)))

    access.mirror = mirror
    start = case['entry']
    ret = 0x01D3 if case['kind'] == 'effect' else 0x0254
    sites, edges = set(), set()
    previous = None
    reached_ret = False
    current_flags = regs['flags']
    instruction_count = 0
    failures = []

    def stop_with(error):
        failures.append(error)
        cpu.emu_stop()

    def code(uc, address, _size, _user):
        nonlocal previous, current_flags, instruction_count, reached_ret
        try:
            off = uc.reg_read(REG_IDS['ip']) & 0xFFFF
            cs = uc.reg_read(REG_IDS['cs']) & 0xFFFF
            if previous == ret:
                reached_ret = True
                uc.emu_stop()
                return
            if previous == 0x01C7:
                edges.add((previous, off))
            if cs != regs['cs']:
                raise RuntimeError(f'original left code segment at {cs:04x}:{off:04x}')
            if core and off == ret:
                reached_ret = True
                uc.emu_stop()
                return
            if not start <= off <= ret:
                raise RuntimeError(f'original escaped leaf at {cs:04x}:{off:04x}')
            if instruction_count >= INSTRUCTION_CAP:
                raise RuntimeError('original instruction cap reached')
            instruction_count += 1
            sites.add(off)
            current_flags = uc.reg_read(REG_IDS['flags']) & 0xFFFF
            previous = off
        except BaseException as error:
            stop_with(error)

    def read(uc, _kind, address, size, _value, _user):
        try:
            for index in range(size):
                at = address + index
                value = access.access('read', at, current_flags)
                # Reads above 1 MiB alias the same physical byte in this fixture.
                mirror(at, value)
        except BaseException as error:
            stop_with(error)

    def write(_uc, _kind, address, size, value, _user):
        try:
            for index in range(size):
                access.access('write', address + index, current_flags,
                              (value >> (8 * index)) & 0xFF)
        except BaseException as error:
            stop_with(error)

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    try:
        cpu.emu_start(physical(regs['cs'], start), 0, count=INSTRUCTION_CAP)
    except UcError as error:
        raise RuntimeError(case['name'] + ': original bounded emulation failed') from error
    if failures:
        raise RuntimeError(case['name'] + ': original callback/escape failure') from failures[0]
    if not reached_ret:
        raise RuntimeError(case['name'] + ': original did not reach the real RET boundary')
    result_regs = {name: cpu.reg_read(REG_IDS[name]) & 0xFFFF for name in REG_NAMES}
    if core:
        result_regs['ip'] = ret
    return dict(memory=bytes(memory), regs=result_regs, device=device,
                events=access.events, used=access.used, sites=sites, edges=edges,
                instruction_count=instruction_count)


class Native:
    def __init__(self, directory, mutation=0):
        path = Path(directory) / f'pcspeaker-bus-m{mutation}.dll'
        self.lib = ct.CDLL(str(build(path, mutation, 'pcspeaker_bus')))
        for kind in ('effect', 'stop'):
            core = getattr(self.lib, f'lmn_pc_sound_{kind}_bus_core')
            adapter = getattr(self.lib, f'lmn_pc_sound_{kind}_bus_adapter')
            if kind == 'effect':
                core.argtypes = [MEM, ct.c_uint16, ct.c_uint8, ct.c_uint16,
                                 ct.c_uint16, ct.POINTER(RasterBus)]
            else:
                core.argtypes = [MEM, ct.c_uint16, ct.c_uint16, ct.c_uint16,
                                 ct.c_uint16, ct.c_uint16, ct.c_uint16,
                                 ct.c_uint16, ct.POINTER(RasterBus)]
            core.restype = Result
            adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
            adapter.restype = None

    def run(self, case, memory, regs, device, core):
        access = Access(case, memory, regs, device)

        def die(error):
            code = 86 if isinstance(error, CallbackLimit) else 87
            try:
                os.write(2, (str(error) + '\n').encode('utf-8', 'replace'))
            finally:
                os._exit(code)

        @READ
        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags)
            except BaseException as error:
                die(error)

        @WRITE
        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, value)
            except BaseException as error:
                die(error)

        @OUT
        def out(_context, port, value, flags):
            die(RuntimeError(f'unexpected port callback {port:04x}/{value:04x}/{flags:04x}'))

        callbacks = (read, write, out)
        bus = RasterBus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        if core:
            if case['kind'] == 'effect':
                result = self.lib.lmn_pc_sound_effect_bus_core(
                    ram, regs['ds'], case['effect'], regs['dx'], regs['flags'],
                    ct.byref(bus))
            else:
                result = self.lib.lmn_pc_sound_stop_bus_core(
                    ram, regs['ds'], regs['ax'], regs['bx'], regs['cx'], regs['dx'],
                    regs['si'], regs['flags'], ct.byref(bus))
            expected_mask = EFFECT_FLAGS if case['kind'] == 'effect' else STOP_FLAGS
            if result.defined_flags_mask != expected_mask:
                raise RuntimeError(f'{case["name"]}: C result flag mask changed')
            for name in ('ax', 'bx', 'cx', 'dx', 'si', 'flags'):
                setattr(state, name, getattr(result, name))
            state.ip = 0x01D3 if case['kind'] == 'effect' else 0x0254
        else:
            getattr(self.lib, f'lmn_pc_sound_{case["kind"]}_bus_adapter')(
                ram, ct.byref(state), ct.byref(bus))
        # Keep callback objects alive through the completed native call.
        assert callbacks and bus.read_byte
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in REG_NAMES},
                    device=device, events=access.events, used=access.used)


def compare(native, case, core):
    memory, regs, device = setup(case)
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core)
    require(actual['memory'] == expected['memory'],
            case['name'] + ': full physical memory differs')
    mask = EFFECT_FLAGS if case['kind'] == 'effect' else STOP_FLAGS
    for name in REG_NAMES:
        reg_mask = mask if name == 'flags' else 0xFFFF
        require((actual['regs'][name] & reg_mask) ==
                (expected['regs'][name] & reg_mask),
                f'{case["name"]}: {name} differs '
                f'{actual["regs"][name]:04x}/{expected["regs"][name]:04x}')
    require(actual['events'] == expected['events'],
            case['name'] + ': ordered RAM/VGA byte bus trace differs\n'
            + str(expected['events']) + '\n' + str(actual['events']))
    require(actual['used'] == expected['used'], case['name'] + ': provider effects differ')
    if case.get('provider'):
        require(case['provider'] in expected['used'],
                case['name'] + ': constructed provider was not exercised')
        require(case['provider'] in actual['used'],
                case['name'] + ': native provider was not exercised')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                case['name'] + ': VGA planes/latches/registers differ')
        require(normalized_device_trace(actual['device'], case['kind']) ==
                normalized_device_trace(expected['device'], case['kind']),
                case['name'] + ': ordered VGA device trace differs')
    return expected


def independent_effect(memory, regs, effect):
    """Sequential byte-copy and post-copy reload expectation for ordinary RAM."""
    wanted = bytearray(memory)
    ds = regs['ds']
    source = (0x28 + ((effect if effect < 0x80 else effect - 0x100) * 15)) & 0xFFFF
    put_byte(wanted, physical(ds, 0x01), 0)
    for index in range(15):
        value = wanted[physical(ds, (source + index) & 0xFFFF)]
        put_byte(wanted, physical(ds, 0x0A + index), value)
    reload_value = get_word(wanted, physical(ds, 0x17))
    put_word(wanted, physical(ds, 0x08), reload_value)
    active = (wanted[physical(ds, 0x01)] - 1) & 0xFF
    put_byte(wanted, physical(ds, 0x01), active)
    return wanted, source, reload_value, active


def independent_stop(memory, regs):
    wanted = bytearray(memory)
    put_byte(wanted, physical(regs['ds'], 0x01), 0)
    return wanted


def input_hashes():
    paths = (
        'assets/main.dat', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-symbols.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-encodings.json',
        'metadata/toolchain-lock.json', 'src/sound/pcspeaker.asm',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h', 'c/regs.h',
        'c/special_blit.h', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/bounded_process.py', 'tools/common.py', 'tools/resources.py',
        'tools/pcspeaker_symtab.py', 'tests/minimap_vga.py',
        'tests/pcspeaker_bus.py',
    )
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def worker(directory):
    before = input_hashes()
    pins = json.loads((ROOT / 'metadata/sound-oracle.json').read_text())
    if IMAGE_META != pins['pcspeaker']:
        raise AssertionError('PC-speaker component identity does not match pinned metadata')

    baseline = Native(directory, 0)
    fixture_rows = []
    sites, edges = set(), set()
    total_events = 0
    total_instructions = 0
    max_instructions = 0
    fixtures = cases()
    for case in fixtures:
        for core in (True, False):
            expected = compare(baseline, case, core)
            sites.update(expected['sites'])
            edges.update(expected['edges'])
            total_events += len(expected['events'])
            total_instructions += expected['instruction_count']
            max_instructions = max(max_instructions, expected['instruction_count'])
            memory, regs, device = setup(case)
            if device is None and case.get('provider') is None:
                if case['kind'] == 'effect':
                    wanted, source, reload_value, active = independent_effect(
                        memory, regs, case['effect'])
                    if expected['memory'] != bytes(wanted):
                        raise AssertionError(case['name'] + ': independent sequential-copy answer differs')
                    if expected['regs']['bx'] != ((source + 15) & 0xFFFF) or \
                            expected['regs']['cx'] != 0 or expected['regs']['si'] != 0x19 or \
                            expected['regs']['ax'] != reload_value or \
                            expected['memory'][physical(regs['ds'], 0x01)] != active:
                        raise AssertionError(case['name'] + ': independent effect outputs differ')
                else:
                    wanted = independent_stop(memory, regs)
                    if expected['memory'] != bytes(wanted) or \
                            expected['regs']['ax'] != (regs['ax'] & 0xFF00):
                        raise AssertionError(case['name'] + ': independent stop answer differs')
            fixture_rows.append(dict(name=case['name'], kind=case['kind'],
                                     effect=case.get('effect'), provider=case.get('provider'),
                                     vga=bool(case.get('vga')), boundary='core' if core else 'adapter',
                                     events=len(expected['events']),
                                     original_instructions=expected['instruction_count']))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    md.detail = True
    leaf_ranges = {'LoadEffect': (0x01B0, 0x01D4), 'Stop': (0x024F, 0x0255)}
    leaf_ins = {}
    for name, (start, end) in leaf_ranges.items():
        leaf_ins[name] = list(md.disasm(IMAGE[start:end], start))
    expected_sites = {ins.address for rows in leaf_ins.values() for ins in rows}
    expected_edges = {(ins.address, ins.operands[0].imm & 0xFFFF)
                      for ins in leaf_ins['LoadEffect'] if ins.mnemonic == 'loop'}
    expected_edges |= {(ins.address, ins.address + ins.size)
                       for ins in leaf_ins['LoadEffect'] if ins.mnemonic == 'loop'}
    if sites != expected_sites:
        raise AssertionError(f'Executed site set differs: missing={expected_sites-sites}, extra={sites-expected_sites}')
    if edges != expected_edges:
        raise AssertionError(f'Loop edges differ: missing={expected_edges-edges}, extra={edges-expected_edges}')

    mutation_witnesses = {
        1: ('effect-al-00', True),
        2: ('effect-reload-provider', True),
        3: ('effect-live-active-provider', True),
        4: ('effect-return-provider', False),
        5: ('effect-df-set', True),
    }
    mutation_rows = []
    for mutation, (case_name, core) in mutation_witnesses.items():
        mutant = Native(directory, mutation)
        case = next(case for case in fixtures if case['name'] == case_name)
        try:
            compare(mutant, case, core)
        except Mismatch as error:
            mutation_rows.append(dict(mutation=mutation, witness=case_name,
                                      boundary='core' if core else 'adapter',
                                      completed_comparison=True, mismatch=str(error)))
        else:
            raise AssertionError(f'PC-speaker bus mutation {mutation} survived')

    after = input_hashes()
    if before != after:
        raise AssertionError('Input sources changed during bounded PC-speaker campaign')
    load_start, load_end = leaf_ranges['LoadEffect']
    stop_start, stop_end = leaf_ranges['Stop']
    report = dict(
        image='pcspeaker', image_sha256=sha(IMAGE), pinned_asset_sha256=before['assets/main.dat'],
        case_count=len(fixtures), boundary_call_count=len(fixture_rows), cases=fixture_rows,
        mutation_count=len(mutation_rows), mutations=mutation_rows,
        source_domains=[dict(name='LoadEffect', start=load_start, end_exclusive=load_end,
                             byte_count=load_end-load_start),
                       dict(name='Stop', start=stop_start, end_exclusive=stop_end,
                            byte_count=stop_end-stop_start)],
        translated_code_bytes=(load_end-load_start)+(stop_end-stop_start),
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        total_original_instructions=total_instructions,
        max_original_instructions=max_instructions, total_bus_events=total_events,
        limits=dict(worker_seconds=180, process_commit_mib=384,
                    original_instruction_cap=INSTRUCTION_CAP,
                    native_callback_event_cap=EVENT_CAP),
        input_hashes=before,
        domain=('Identified PC-speaker LoadEffect and Stop leaves through the real near RET; '
                'all signed AL values, byte-addressed RAM/VGA bus callbacks, bounded constructed '
                'providers, and quiescent synchronous execution.'),
        limitations=('No INT60 dispatcher, asynchronous IRQ, timer, PIT waveform, or full VGA timing claim; '
                     'VGA fixtures cover the existing planar mode-0/1 bus model only.'))
    write_json(REPORT, report)
    print(f'PASS PC-speaker bus: {len(fixtures)} fixtures, {len(fixture_rows)} core/adapter calls, '
          f'{len(sites)} instruction sites, {len(edges)} branch edges, '
          f'{total_events} byte events, {len(mutation_rows)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected PC-speaker bus arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='pcspeaker-bus-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
