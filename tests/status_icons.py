"""Bounded original/native tests for the two closed status-icon leaves."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
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
from entity_interactions import original as run_original
from entity_interactions import OracleFailure, REG_NAMES, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
LOAD = 0x1010
SIZE, MASK = 1 << 20, (1 << 20) - 1
DATA_SEG = 0x3000
MIRROR_MAP_MASK = 0x0008
MIRROR_GC_MODE = 0x0000
DRAWING_ORIGIN = 0x1F76
OUTLINE = (0x780D, 0x789D, 0x789E)
RESTORE = (0x789E, 0x78FF, 0x7900)
ROUTINES = {'outline': OUTLINE, 'restore': RESTORE}
DEFINED_FLAGS = 0x0FD7
DF, IF = 0x0400, 0x0200
MAX_INSTRUCTIONS, MAX_EVENTS = 512, 2048
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-icons-differential.json'
ORIGINAL_REPORT = BUILD / 'status-icons-original-differential.json'
CORE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
              'ss', 'sp', 'flags')
RESULT_FIELDS = dict(ax='value', bx='map_cursor', cx='count', dx='auxiliary_value',
                     si='record_cursor', di='object_cursor', bp='candidate_y',
                     cs='code_segment', ds='data_segment', es='extra_segment',
                     ss='stack_segment', sp='stack_offset', flags='flags')
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags', 'continuation', 'status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """A completed C/original comparison differs."""


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INSTRUCTIONS = {}
for routine, (entry, _ret, end) in ROUTINES.items():
    INSTRUCTIONS.update({ins.address: ins for ins in
                         MD.disasm(IMAGE[entry:end], entry)})


def static_edges():
    edges = set()
    for address, ins in INSTRUCTIONS.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.lower() == 'loop'):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


EXPECTED_EDGES = static_edges()
EXPECTED_SITES = set(INSTRUCTIONS)
CODE_BYTES = sum(ins.size for ins in INSTRUCTIONS.values())
oracle_require(CODE_BYTES == 243 and len(EXPECTED_SITES) == 100,
               f'status-icon static boundary changed: {CODE_BYTES} bytes, '
               f'{len(EXPECTED_SITES)} sites')
oracle_require(len(EXPECTED_EDGES) == 6,
               f'status-icon branch map changed: {sorted(EXPECTED_EDGES)}')


def make_cases():
    cases = []
    for routine in ('outline', 'restore'):
        for value in range(256):
            name = f'{routine}-al-{value:02x}'
            case = dict(name=name, routine=routine, al=value,
                        seed=(0x780D if routine == 'outline' else 0x789E) + value)
            if routine == 'outline' and value == 0x30:
                case.update(name='outline-actual-return-overwritten', sp=0x0008)
            elif routine == 'outline' and value == 0x31:
                case.update(name='outline-origin-provider-after-first-port',
                            origin=0xFFDA, provider_origin=0x0137)
            elif routine == 'outline' and value == 0x32:
                case.update(name='outline-vga-stack-mirrors', ss=0xA000,
                            sp=0x3000)
            elif routine == 'outline' and value == 0x33:
                case.update(name='outline-final-ah-latch', final_latch=0x5A)
            elif routine == 'restore' and value == 0x07:
                case.update(name='restore-live-pop-si-mirror-alias', sp=0x000C)
            elif routine == 'restore' and value == 0x08:
                case.update(name='restore-ds-equals-ss', ds=0x5200, ss=0x5200)
            elif routine == 'restore' and value == 0x09:
                case.update(name='restore-vga-backed-stack', ss=0xA000,
                            sp=0x3000)
            elif routine == 'restore' and value == 0x80:
                case.update(name='restore-signed-negative-al-and-stack-wrap',
                            ss=0xFFFF, sp=0xFFFF)
            elif routine == 'restore' and value == 0x81:
                case.update(name='restore-df-backward', df=True)
            elif routine == 'restore' and value == 0x82:
                case.update(name='restore-origin-provider-after-first-port',
                            origin=0xFFE0, provider_origin=0x8001)
            cases.append(case)
    oracle_require(len(cases) == 512, 'expected complete 256-value AL domain per routine')
    return cases


def setup(case):
    rng = random.Random(0x51C0A5 ^ (case['seed'] * 0x9E3779B1))
    memory = bytearray(SIZE)
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    load_base = LOAD << 4
    memory[load_base:load_base + len(loaded)] = loaded

    ds = case.get('ds', DATA_SEG) & 0xFFFF
    ss = case.get('ss', 0x5200) & 0xFFFF
    sp = case.get('sp', 0x7000) & 0xFFFF
    entry, ret, _end = ROUTINES[case['routine']]
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    regs.update(ax=((rng.randrange(256) << 8) | case['al']),
                bx=(0xA700 | rng.randrange(256)),
                cs=LOAD, ip=entry, ds=ds, es=0x6200,
                ss=ss, sp=sp)
    flags = 2 | (rng.randrange(0x10000) & (DEFINED_FLAGS & ~0x0100))
    if case.get('df', bool(case['al'] & 1)):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('iflag', bool(case['al'] & 2)):
        flags |= IF
    else:
        flags &= ~IF
    regs['flags'] = flags & 0xFFFF

    # A byte pattern makes the signed selector's unchecked DS word clear
    # observable while leaving the executable and DrawingOrigin independent.
    for offset in range(0x240):
        memory[physical(ds, offset)] = (offset * 37 + case['seed'] * 11 + 3) & 0xFF
    origin = case.get('origin', (0x0123 + case['seed'] * 19) & 0xFFFF)
    put16(memory, ds, DRAWING_ORIGIN, origin)
    return_word = case.get('return_word', (0xA531 + case['seed'] * 7) & 0xFFFF)
    put16(memory, ss, sp, return_word)

    device = MinimapVga(0x780D ^ (case['seed'] * 17),
                        read_map=(case['seed'] >> 2) & 3)
    device.seq[2] = (case['seed'] * 5 + 3) & 0x0F
    device.gc[0] = (case['seed'] * 3 + 1) & 0x0F
    device.gc[1] = (case['seed'] * 7 + 2) & 0x0F
    device.gc[2] = (case['seed'] * 11 + 4) & 0x0F
    device.gc[3] = (case['seed'] * 13 + 5) & 0x1F
    device.gc[4] = (case['seed'] >> 1) & 3
    device.gc[5] = (0x00, 0x01, 0x08, 0x09)[case['seed'] & 3]
    device.gc[7] = (case['seed'] * 17 + 6) & 0x0F
    device.gc[8] = (case['seed'] * 23 + 0x35) & 0xFF
    if 'final_latch' in case:
        device.gc[4] = 0

    # The stack may itself be VGA-backed. Its RET then comes from the actual
    # read plane through the bus, not from the ordinary RAM seed above.
    if ss == 0xA000:
        device.gc[4] = 0
        device.planes[0][sp] = return_word & 0xFF
        device.planes[0][(sp + 1) & 0xFFFF] = return_word >> 8

    if 'final_latch' in case:
        last = outline_cells(regs, origin)[-1][0]
        device.planes[0][last] = case['final_latch']
    return memory, regs, device


def outline_cells(regs, origin):
    di = (2 * (regs['ax'] & 0xFF) + 0x2100 + origin + 2) & 0xFFFF
    step = -1 if regs['flags'] & DF else 1
    cells = [(di, 0xFF)]
    di = (di + step) & 0xFFFF
    cells.append((di, 0xFF))
    di = (di + step + 0x2A) & 0xFFFF
    for _ in range(22):
        cells.append((di, 0x80))
        di = (di + step) & 0xFFFF
        cells.append((di, 0x01))
        di = (di + step + 0x2A) & 0xFFFF
    cells.append((di, 0xFF))
    cells.append(((di + step) & 0xFFFF, 0xFF))
    return cells


def project_device(case, initial_device, initial_memory, regs):
    """Independent replay of the fixed outline mask and sequential mode-1 copy."""
    if regs['ss'] == 0xA000 or regs['ds'] == 0xA000:
        return None
    expected = copy.deepcopy(initial_device)
    if case['routine'] == 'outline':
        origin = get16(initial_memory, regs['ds'], DRAWING_ORIGIN)
        cells = outline_cells(regs, origin)
        expected.seq[2] = 0x0F
        expected.si = 2
        expected.gc[0] = 0
        expected.gc[1] = 0x0C
        expected.gc[5] = 0
        expected.gc[3] = 0
        expected.gc[8] = 0xFF
        for offset, mask in cells:
            expected.latches = [plane[offset] for plane in expected.planes]
            for plane in range(4):
                source = mask if plane < 2 else 0
                old = expected.latches[plane]
                expected.planes[plane][offset] = (
                    (source & mask) | (old & (~mask & 0xFF)))
        expected.gi = 8
        expected.outcount += 51
        return expected

    # Restoration's stack mirrors are ordinary RAM here. At SP=000C the first
    # SS mirror overwrites the saved DI word; POP SI must consume that live word.
    al = regs['ax'] & 0xFF
    source_di = (2 * al) & 0xFFFF
    live_saved_di = source_di
    if regs['sp'] == 0x000C:
        live_saved_di = 0x0F02
    si = (live_saved_di + 0x02C0 + 0xF91F) & 0xFFFF
    di = (source_di + 0x2100 + get16(initial_memory, regs['ds'], DRAWING_ORIGIN) + 2) & 0xFFFF
    forward = not (regs['flags'] & DF)
    expected.seq[2] = 0x0F
    expected.si = 2
    expected.gc[5] = 1
    expected.gi = 5
    expected.outcount += 2
    for _row in range(24):
        for _byte in range(2):
            offset = si
            expected.latches = [plane[offset] for plane in expected.planes]
            value = expected.latches[expected.gc[4] & 3]
            for plane in range(4):
                if expected.seq[2] & (1 << plane):
                    expected.planes[plane][di] = expected.latches[plane]
            # CPU-visible memory follows the selected read plane; the planar
            # source/destination replay above remains authoritative for pixels.
            _ = value
            delta = 1 if forward else -1
            si = (si + delta) & 0xFFFF
            di = (di + delta) & 0xFFFF
        di = (di + 0x2A) & 0xFFFF
        si = (si + 0x2A) & 0xFFFF
    return expected


class IconAccess:
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events, self.used, self.out_count = [], set(), 0
        self.mirror = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror is not None:
            self.mirror(address, value & 0xFF)

    def access(self, kind, address, flags, mask=DEFINED_FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('status-icon bus callback budget exhausted')
        address &= MASK
        if kind == 'read':
            value = (self.device.read(self.memory, address, flags)
                     if self.device is not None and VGA_BASE <= address < VGA_END
                     else self.memory[address])
            self.store(address, value)
        else:
            value &= 0xFF
            if self.device is not None and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF,
                            flags & 0xFFFF, mask))
        return value & 0xFF

    def out_word(self, port, value, flags, mask=DEFINED_FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('status-icon OUT callback budget exhausted')
        if port not in (0x03C4, 0x03CE):
            raise OracleFailure(f'undeclared status-icon OUT port {port:04X}')
        if self.device is None:
            raise OracleFailure('status-icon routine requires the declared VGA device')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        index = self.out_count
        self.out_count += 1
        if (self.case.get('provider_origin') is not None and index == 0 and
                'origin-after-first-port' not in self.used):
            self.used.add('origin-after-first-port')
            put16(self.memory, self.regs['ds'], DRAWING_ORIGIN,
                  self.case['provider_origin'])
            if self.mirror is not None:
                address = physical(self.regs['ds'], DRAWING_ORIGIN)
                self.mirror(address, self.case['provider_origin'] & 0xFF)
                self.mirror(address + 1, self.case['provider_origin'] >> 8)


def make_instruction_map():
    return INSTRUCTIONS


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = IconAccess(case, memory, regs, device)
        self.events = self.access.events
        self.used = self.access.used

        def read(_ctx, _mem, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-icon read callback failed: {error}')
                return 0

        def write(_ctx, _mem, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-icon write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-icon OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-icons-m{mutation}.dll',
                     mutation, 'status_icons')
        self.library = ct.CDLL(str(path))
        self.outline_core = self.library.lmn_draw_status_icon_outline_core
        self.outline_core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.outline_core.restype = Result
        self.restore_core = self.library.lmn_restore_status_icon_core
        self.restore_core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.restore_core.restype = Result
        self.outline_adapter = self.library.lmn_draw_status_icon_outline_adapter
        self.outline_adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.outline_adapter.restype = ct.c_uint16
        self.restore_adapter = self.library.lmn_restore_status_icon_adapter
        self.restore_adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.restore_adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs_dict = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs_dict, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs_dict)
        if core:
            call = Call(*(regs_dict[name] for name in CORE_NAMES))
            routine = self.outline_core if case['routine'] == 'outline' else self.restore_core
            result = routine(ram, ct.byref(call), ct.byref(callback.bus))
            for name in CORE_NAMES:
                setattr(state, name, getattr(result, RESULT_FIELDS[name]))
            state.ip = result.continuation
            status = result.status
        else:
            routine = (self.outline_adapter if case['routine'] == 'outline'
                       else self.restore_adapter)
            status = routine(ram, ct.byref(state), ct.byref(callback.bus))
        final = {name: getattr(state, name) & 0xFFFF for name in REG_NAMES}
        return dict(memory=bytes(memory), regs=final, events=callback.events,
                    used=set(callback.used), device=device, status=status,
                    continuation=final['ip'], out_count=callback.access.out_count)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered bus event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def assert_independent(case, initial_memory, regs, initial_device, expected):
    routine = case['routine']
    input_origin = get16(initial_memory, regs['ds'], DRAWING_ORIGIN)
    projected = project_device(case, initial_device, initial_memory, regs)
    if projected is not None:
        oracle_require(projected.state() == expected['device'].state(),
                       case['name'] + ': independent VGA plane replay differs')
    if routine == 'outline':
        cells = outline_cells(regs, input_origin)
        oracle_require(len(cells) == 48, case['name'] + ': outline is not 48 ordered pixels')
        last = cells[-1][0]
        if projected is not None:
            last_latch = initial_device.planes[initial_device.gc[4] & 3][last]
            oracle_require(expected['regs']['ax'] == ((last_latch << 8) | 0xFF),
                           case['name'] + ': independent final AX/latch expectation differs')
        final_di = (last + (-1 if regs['flags'] & DF else 1)) & 0xFFFF
        final_sp = (regs['sp'] + (0 if expected['boundary'] == 'core-ret' else 2)) & 0xFFFF
        oracle_require(expected['regs']['cx'] == 0 and
                       expected['regs']['di'] == final_di and
                       expected['regs']['es'] == 0xA000 and
                       expected['regs']['dx'] == 0x03CE and
                       expected['regs']['ds'] == regs['ds'] and
                       expected['regs']['si'] == regs['si'] and
                       expected['regs']['sp'] == final_sp and
                       (expected['regs']['flags'] & IF),
                       case['name'] + ': independent outline register contract differs')
        oracle_require(sum(event[0] == 'out' for event in expected['events']) == 51,
                       case['name'] + ': outline word-port count differs from 51')
    else:
        al = regs['ax'] & 0xFF
        signed = al if al < 0x80 else al - 0x100
        if signed < 10:
            reset = (0x64 + ((3 * al) & 0xFF) + 1) & 0xFFFF
            oracle_require(expected['memory'][physical(regs['ds'], reset)] == 0 and
                           expected['memory'][physical(regs['ds'], (reset + 1) & 0xFFFF)] == 0,
                           case['name'] + ': signed selector did not clear its wrapped word')
        oracle_require(expected['regs']['cx'] == 0 and
                       expected['regs']['es'] == 0xA000 and
                       expected['regs']['dx'] == 0xA000,
                       case['name'] + ': independent restore register contract differs')
        if projected is not None:
            live_saved_di = (0x0F02 if regs['sp'] == 0x000C else
                             (2 * al) & 0xFFFF)
            step = -1 if regs['flags'] & DF else 1
            si = (live_saved_di + 0x02C0 + 0xF91F) & 0xFFFF
            di = (2 * al + 0x2100 + input_origin + 2) & 0xFFFF
            for _row in range(24):
                si = (si + 2 * step + 0x2A) & 0xFFFF
                di = (di + 2 * step + 0x2A) & 0xFFFF
            final_sp = (regs['sp'] + (0 if expected['boundary'] == 'core-ret' else 2)) & 0xFFFF
            oracle_require(expected['regs']['si'] == si and
                           expected['regs']['di'] == di and
                           expected['regs']['ds'] == regs['ds'] and
                           expected['regs']['sp'] == final_sp,
                           case['name'] + ': independent restore cursor/stack projection differs')
        oracle_require(sum(event[0] == 'out' for event in expected['events']) == 2,
                       case['name'] + ': restore word-port count differs from two')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    expected = run_original(case, bytearray(initial), dict(regs),
                            copy.deepcopy(device), core,
                            entry_flag_mask=DEFINED_FLAGS,
                            main_instructions=make_instruction_map(),
                            instruction_limit=MAX_INSTRUCTIONS,
                            access_factory=IconAccess)
    assert_independent(case, initial, regs, device, expected)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == 0, f'{label}: status {actual["status"]}')
    for name in REG_NAMES:
        if name == 'flags':
            require(((actual['regs'][name] ^ expected['regs'][name]) &
                     expected['flag_mask']) == 0,
                    f'{label}: defined FLAGS {actual["regs"][name]:04X}/'
                    f'{expected["regs"][name]:04X}')
        else:
            require(actual['regs'][name] == expected['regs'][name],
                    f'{label}: {name} {actual["regs"][name]:04X}/'
                    f'{expected["regs"][name]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: provider observations {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA planes/latches/registers differ')
    return dict(name=case['name'], routine=case['routine'], core=core,
                sites=sorted(off for source, off in expected['sites'] if source == 'main'),
                edges=[list(edge[1:]) for edge in sorted(expected['edges'])
                       if edge[0] == 'main'],
                steps=expected['steps'], events=len(expected['events']),
                output_words=actual['out_count'],
                plane_check='independent 48-pixel or 24-row sequential replay'
                if project_device(case, device, initial, regs) is not None
                else 'original/native full-device state only for VGA-backed segment alias')


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/status-icons.md', 'assets/vgalemmi.exe',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/inputs.json',
        'metadata/regions.json', 'metadata/hints.json', 'metadata/toolchain-lock.json',
        'src/program.asm', 'src/status_icons.asm', 'src/game_code_before_minimap.asm',
        'c/status_icons.c', 'c/status_icons.h', 'c/special_blit.h',
        'c/regs.h', 'c/lemmings_sym.h', 'tests/status_icons.py',
        'tests/entity_interactions.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tools/resources.py', 'tests/minimap_vga.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/unpack.py',
        'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'required input hashes missing: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'status-icon inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core,
                                    entry_flag_mask=DEFINED_FLAGS,
                                    main_instructions=make_instruction_map(),
                                    instruction_limit=MAX_INSTRUCTIONS,
                                    access_factory=IconAccess)
            assert_independent(case, initial, regs, device, expected)
            own_sites = {off for source, off in expected['sites'] if source == 'main'}
            own_edges = {edge[1:] for edge in expected['edges'] if edge[0] == 'main'}
            rows.append(dict(name=case['name'], routine=case['routine'], core=core,
                             sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == EXPECTED_SITES,
                   f'original site union differs: missing={sorted(EXPECTED_SITES-sites)} '
                   f'extra={sorted(sites-EXPECTED_SITES)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'original branch outcomes differ: missing={sorted(EXPECTED_EDGES-edges)} '
                   f'extra={sorted(edges-EXPECTED_EDGES)}')
    oracle_require(before == input_hashes(), 'status-icon inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'status-icon inputs changed before native worker')
    specs = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == EXPECTED_SITES,
                   f'native-comparison site union differs: missing={sorted(EXPECTED_SITES-sites)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'native-comparison branch outcomes differ: missing={sorted(EXPECTED_EDGES-edges)}')

    by_name = {case['name']: case for case in specs}
    witnesses = {
        1: ('restore-signed-negative-al-and-stack-wrap', 'restore', False),
        2: ('restore-al-ff', 'restore', True),
        3: ('restore-live-pop-si-mirror-alias', 'restore', True),
        4: ('restore-signed-negative-al-and-stack-wrap', 'restore', True),
        5: ('restore-df-backward', 'restore', True),
        6: ('restore-origin-provider-after-first-port', 'restore', True),
        7: ('outline-al-00', 'outline', True),
        8: ('outline-final-ah-latch', 'outline', True),
        9: ('outline-actual-return-overwritten', 'outline', False),
    }
    mutants = []
    for mutation, (name, routine, core) in witnesses.items():
        case = by_name[name]
        oracle_require(case['routine'] == routine,
                       f'mutation {mutation} witness selected the wrong entry')
        variant = Native(directory, mutation)
        try:
            compare_case(variant, case, core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name, routine=routine,
                                core=core, completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'status-icon mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'status-icon inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[0x780D, 0x789E], [0x789E, 0x7900]],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(EXPECTED_SITES),
        static_instruction_addresses=sorted(EXPECTED_SITES),
        branch_edge_count=len(EXPECTED_EDGES),
        static_branch_edges=[list(e) for e in sorted(EXPECTED_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutants), mutations=mutants,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(e) for e in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domains=[
            'DrawStatusIconOutline 780D..789D: all 256 AL values, exact 48 pixel reads/stores, 51 word OUTs and unconditional STI',
            'RestoreStatusIcon 789E..78FF: all 256 signed AL comparisons, byte-wrapped 3*AL reset selector and 24 sequential MOVSB rows',
            'core stops before RET; adapter consumes the actual SS:SP near-return word',
            'whole 1 MiB RAM, all logical registers, defined final flags, ordered byte/word callbacks and complete four-plane VGA state',
            'ordinary RAM-stack cases independently replay all outline pixels or mode-1 row copies; A000-backed stack aliases compare full device state',
            'DF-sensitive STOSB/MOVSB with forward +2A row additions, SS mirror aliases, DS=SS, physical 20-bit stack wrap and VGA-backed stack',
            'DrawingOrigin provider updates after the routine has already read and cached the first destination',
        ]))
    print(f'PASS status icons: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-icons-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, edges = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[0x780D, 0x789E], [0x789E, 0x7900]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(EXPECTED_SITES),
            static_instruction_addresses=sorted(EXPECTED_SITES),
            branch_edge_count=len(EXPECTED_EDGES), branch_edges=[list(e) for e in sorted(edges)],
            executed_instruction_addresses=sorted(sites), case_count=len(make_cases()),
            core_adapter_comparisons=len(rows), input_hashes=before, cases=rows,
            domain='Original-only all-AL core/actual-RET checks with independent plane and memory expectations.'))
        print(f'PASS status icons original preflight: {len(make_cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_icons.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-icons-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
