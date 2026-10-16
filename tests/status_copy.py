"""Bounded original/native checks for the 7602 status-copy leaf and 75EF wrapper."""
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
import entity_interactions as interactions
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
LOAD = 0x1010
WRAPPER_ENTRY, LEAF_ENTRY, END = 0x75EF, 0x7602, 0x762A
INNER_CALL, INNER_RETURN, LEAF_RETURN = 0x75F7, 0x75FA, 0x7629
DRAWING_ORIGIN, ALTERNATE_ORIGIN = 0x1F76, 0x1F78
COPY_BYTES = 0x06E0
DEFINED_FLAGS = 0x0FD7
ARITH_FLAGS = 0x08D5
DF = 0x0400
MAX_INSTRUCTIONS, MAX_EVENTS = 4000, 16000
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-copy-differential.json'
ORIGINAL_REPORT = BUILD / 'status-copy-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[WRAPPER_ENTRY:END], WRAPPER_ENTRY)}
LEAF_INS = {address: ins for address, ins in OWN_INS.items() if address >= LEAF_ENTRY}
SITES = set(OWN_INS)
LEAF_SITES = set(LEAF_INS)
EDGES = set()
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())

interactions.oracle_require(CODE_BYTES == 59 and len(SITES) == 22,
    f'status-copy static scope changed: {CODE_BYTES} bytes/{len(SITES)} sites')
interactions.oracle_require(sum(ins.size for ins in LEAF_INS.values()) == 40 and
                            len(LEAF_SITES) == 17,
    'status-copy leaf static scope changed')

CORE_NAMES = ('value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
              'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
              'extra_segment', 'stack_segment', 'stack_offset', 'flags')
REG_FIELDS = dict(value='ax', map_cursor='bx', count='cx', auxiliary_value='dx',
                  record_cursor='si', object_cursor='di', candidate_y='bp',
                  code_segment='cs', data_segment='ds', extra_segment='es',
                  stack_segment='ss', stack_offset='sp', flags='flags')
RESULT_FIELDS = {machine: role for role, machine in REG_FIELDS.items()}
REG_NAMES, REG_IDS = interactions.REG_NAMES, interactions.REG_IDS
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                CORE_NAMES + ('continuation', 'status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """Only a completed native comparison can produce mutation evidence."""


def oracle_require(condition, message):
    if not condition:
        raise interactions.OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return ((((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK)


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def canonical_flags(case):
    flags = (case.get('flags', 0x0ED7) | 2) & DEFINED_FLAGS
    if case.get('df', False):
        flags |= DF
    else:
        flags &= ~DF
    return flags & 0xFFFF


def make_cases():
    """Focused fixtures for live DS/RET aliases, DF, overlap and both origins."""
    return [
        dict(name='leaf-forward', entry='leaf', di=0x2800, seed=0x760201),
        dict(name='leaf-backward-df', entry='leaf', di=0x2A00, df=True,
             seed=0x760202),
        dict(name='leaf-di-forward-wrap', entry='leaf', di=0xFF80,
             seed=0x760203),
        dict(name='leaf-di-backward-wrap', entry='leaf', di=0x0180, df=True,
             seed=0x760204),
        dict(name='leaf-live-ds-pop-mirror', entry='leaf', sp=0x000A,
             seed=0x760205),
        dict(name='leaf-live-ret-overwritten-by-mirror', entry='leaf', sp=0x0008,
             seed=0x760206),
        dict(name='leaf-physical-ret-word-wrap', entry='leaf', ss=0xFFFF,
             sp=0x000F, seed=0x760207),
        dict(name='leaf-vga-backed-stack', entry='leaf', ss=0xA000,
             sp=0xF925, di=0x3400, seed=0x760208),
        dict(name='leaf-overlap-sequential-movsb', entry='leaf', di=0xF920,
             seed=0x760209),
        dict(name='wrapper-two-origins-forward', entry='wrapper',
             origin=0x2800, alternate=0x5800, seed=0x75EF01),
        dict(name='wrapper-live-ds-alias-to-second-origin', entry='wrapper',
             sp=0x000C, second_ds=0x0F02, second_ds_origin=0x6600,
             origin=0x2A00, alternate=0x3C00, seed=0x75EF02),
        dict(name='wrapper-first-child-ret-changed', entry='wrapper',
             sp=0x000A, origin=0x3000, alternate=0x6000, seed=0x75EF03),
        dict(name='wrapper-late-alternate-origin-provider', entry='wrapper',
             origin=0x3400, alternate=0x4A00, provider_alternate=0x5200,
             seed=0x75EF04),
        dict(name='wrapper-add-di-wraps-flags', entry='wrapper',
             origin=0xF200, alternate=0x5200, seed=0x75EF05),
        dict(name='wrapper-df-backward-both-passes', entry='wrapper', df=True,
             origin=0x3300, alternate=0x6200, seed=0x75EF06),
        dict(name='wrapper-outer-ret-physical-wrap', entry='wrapper',
             ss=0xFFFF, sp=0x000F, origin=0x3800, alternate=0x6800,
             seed=0x75EF07),
    ]


def setup(case):
    seed = case['seed'] & 0xFFFFFFFF
    rng = random.Random(seed)
    memory = bytearray(SIZE)
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    base = (LOAD << 4) & MASK
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    memory[:len(loaded) - first] = loaded[first:]

    ds = case.get('ds', 0x3500) & 0xFFFF
    ss = case.get('ss', 0x5200) & 0xFFFF
    sp = case.get('sp', 0xC000) & 0xFFFF
    regs = {name: ((0x392B * (index + 1) + seed * 7 + 0x51A3) & 0xFFFF)
            for index, name in enumerate(REG_NAMES)}
    regs.update(ax=0xBEEF, bx=0x7139, cx=0x6A55, dx=0x42D3,
                si=0x5123, di=case.get('di', 0x2800), bp=0xA641,
                cs=LOAD, ds=ds, es=0x6C20, ss=ss, sp=sp,
                ip=WRAPPER_ENTRY if case['entry'] == 'wrapper' else LEAF_ENTRY,
                flags=canonical_flags(case))

    if case['entry'] == 'wrapper':
        put16(memory, ds, DRAWING_ORIGIN, case.get('origin', 0x2800))
        put16(memory, ds, ALTERNATE_ORIGIN, case.get('alternate', 0x5800))
        if 'second_ds' in case:
            put16(memory, case['second_ds'], ALTERNATE_ORIGIN,
                  case.get('second_ds_origin', 0x6600))
    put16(memory, ss, sp, case.get('outer_return', 0x6A35))

    device = MinimapVga(seed ^ 0x7602, read_map=0)
    # The prologue can write stack words into A000 before changing VGA modes.
    device.seq[2], device.seq[4] = 0x0F, 0x06
    device.gc[0], device.gc[1], device.gc[3] = 0, 0, 0
    device.gc[4], device.gc[5], device.gc[6], device.gc[8] = 0, 0, 0x05, 0xFF
    outer_return = case.get('outer_return', 0x6A35)
    for offset, value in (((sp, outer_return & 0xFF),
                           ((sp + 1) & 0xFFFF, outer_return >> 8))):
        address = physical(ss, offset)
        if VGA_BASE <= address < VGA_END:
            device.planes[0][address - VGA_BASE] = value
    if case['entry'] == 'wrapper':
        inner_offset = (sp - 2) & 0xFFFF
        inner_address = physical(ss, inner_offset)
        if VGA_BASE <= inner_address < VGA_END:
            device.planes[0][inner_address - VGA_BASE] = INNER_RETURN & 0xFF
        if VGA_BASE <= inner_address + 1 < VGA_END:
            device.planes[0][inner_address + 1 - VGA_BASE] = INNER_RETURN >> 8
    return memory, regs, device


class CopyAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0

    def access(self, kind, address, flags, mask=DEFINED_FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('status-copy bus event budget exhausted')
        return super().access(kind, address, flags, mask, value)

    def out_word(self, port, value, flags, mask=DEFINED_FLAGS):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure('status-copy OUT event budget exhausted')
        if port not in (0x03C4, 0x03CE) or self.device is None:
            raise interactions.OracleFailure(f'unexpected status-copy OUT {port:04X}')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        if (self.case.get('provider_alternate') is not None and
                self.out_count == 0 and self.case.get('entry') == 'wrapper'):
            target = self.case['provider_alternate']
            put16(self.memory, self.regs['ds'], ALTERNATE_ORIGIN, target)
            if self.mirror is not None:
                address = physical(self.regs['ds'], ALTERNATE_ORIGIN)
                self.mirror(address, target & 0xFF)
                self.mirror((address + 1) & MASK, target >> 8)
            self.used.add('alternate-origin-after-first-out')
        self.out_count += 1


def _original_one(case, memory, regs, device, *, core, access_factory,
                  call_returns=None, stop_offsets=None, entry_flag_mask=DEFINED_FLAGS):
    return interactions.original(
        case, bytearray(memory), dict(regs), device, core,
        entry_flag_mask=entry_flag_mask, main_instructions=OWN_INS,
        main_call_returns=call_returns, stop_offsets=stop_offsets,
        instruction_limit=MAX_INSTRUCTIONS, access_factory=access_factory)


def original(case, memory, regs, device, *, core):
    if case['entry'] == 'leaf':
        return _original_one(case, memory, regs, copy.deepcopy(device), core=core,
                             access_factory=CopyAccess)

    holder = {}

    def reuse_access(case_arg, memory_arg, regs_arg, device_arg):
        access = holder.get('access')
        if access is None:
            access = CopyAccess(case_arg, memory_arg, regs_arg, device_arg)
            holder['access'] = access
        else:
            access.case, access.memory = case_arg, memory_arg
            access.regs, access.device = regs_arg, device_arg
        return access

    phase1 = _original_one(
        case, memory, regs, copy.deepcopy(device), core=False,
        access_factory=reuse_access,
        call_returns={INNER_CALL: ({LEAF_RETURN}, 1)},
        stop_offsets={INNER_RETURN: 0})
    if phase1['status'] != 0:
        return phase1

    phase2 = _original_one(
        case, phase1['memory'], phase1['regs'], phase1['device'], core=core,
        access_factory=reuse_access, entry_flag_mask=phase1['flag_mask'])
    combined = dict(phase2)
    combined.update(
        sites=phase1['sites'] | phase2['sites'],
        edges=phase1['edges'] | phase2['edges'],
        call_targets=phase1['call_targets'] | phase2['call_targets'],
        steps=phase1['steps'] + phase2['steps'],
        events=holder['access'].events,
        used=holder['access'].used,
        flag_mask=phase2['flag_mask'])
    return combined


def _sim_read(memory, device, address, flags):
    address &= MASK
    if device is not None and VGA_BASE <= address < VGA_END:
        return device.read(memory, address, flags)
    return memory[address]


def _sim_write(memory, device, address, value, flags):
    address &= MASK
    value &= 0xFF
    if device is not None and VGA_BASE <= address < VGA_END:
        device.write(memory, address, value, flags)
    memory[address] = value


def _sim_read16(memory, device, segment, offset, flags):
    address = physical(segment, offset)
    low = _sim_read(memory, device, address, flags)
    high = _sim_read(memory, device, (address + 1) & MASK, flags)
    return low | (high << 8)


def _sim_write16(memory, device, segment, offset, value, flags):
    address = physical(segment, offset)
    _sim_write(memory, device, address, value, flags)
    _sim_write(memory, device, (address + 1) & MASK, value >> 8, flags)


def _add16_flags(flags, left, right):
    result = (left + right) & 0xFFFF
    wide = left + right
    low = result & 0xFF
    even = (low.bit_count() & 1) == 0
    status = (0x0004 if even else 0) | (0x0040 if result == 0 else 0)
    status |= 0x0080 if result & 0x8000 else 0
    status |= 0x0001 if wide > 0xFFFF else 0
    status |= 0x0010 if (left ^ right ^ result) & 0x0010 else 0
    status |= 0x0800 if (~(left ^ right) & (left ^ result) & 0x8000) else 0
    return ((flags & ~ARITH_FLAGS) | status) & 0xFFFF


def _simulate_leaf(memory, regs, device, *, initial_di, case, provider_state):
    flags = regs['flags']
    regs['sp'] = (regs['sp'] - 2) & 0xFFFF
    _sim_write16(memory, device, regs['ss'], regs['sp'], regs['ds'], flags)
    regs['dx'], regs['ax'] = 0x03C4, 0x0F02
    _sim_write16(memory, device, regs['ss'], 0x0008, regs['ax'], flags)
    device.out(regs['dx'], regs['ax'], flags)
    if (not provider_state['alternate_fired'] and
            case.get('provider_alternate') is not None and
            case.get('entry') == 'wrapper'):
        put16(memory, regs['ds'], ALTERNATE_ORIGIN, case['provider_alternate'])
        provider_state['alternate_fired'] = True
    regs['dx'], regs['ax'] = 0x03CE, 0x0105
    _sim_write16(memory, device, regs['ss'], 0x0000, regs['ax'], flags)
    device.out(regs['dx'], regs['ax'], flags)
    regs['si'], regs['dx'], regs['es'], regs['ds'] = 0xF91F, 0xA000, 0xA000, 0xA000
    regs['di'], regs['cx'] = initial_di & 0xFFFF, COPY_BYTES
    step = -1 if flags & DF else 1
    while regs['cx']:
        source = physical(regs['ds'], regs['si'])
        value = _sim_read(memory, device, source, flags)
        destination = physical(regs['es'], regs['di'])
        _sim_write(memory, device, destination, value, flags)
        regs['si'] = (regs['si'] + step) & 0xFFFF
        regs['di'] = (regs['di'] + step) & 0xFFFF
        regs['cx'] = (regs['cx'] - 1) & 0xFFFF
    regs['ds'] = _sim_read16(memory, device, regs['ss'], regs['sp'], flags)
    regs['sp'] = (regs['sp'] + 2) & 0xFFFF


def independent(case, initial_memory, initial_regs, initial_device, *, core):
    """Replay the two real MOVSB phases and VGA plane/latch effects independently."""
    memory = bytearray(initial_memory)
    device = copy.deepcopy(initial_device)
    regs = dict(initial_regs)
    status, continuation = 0, LEAF_RETURN
    provider_state = {'alternate_fired': False}

    def finish_return():
        nonlocal continuation
        continuation = _sim_read16(memory, device, regs['ss'], regs['sp'], regs['flags'])
        regs['sp'] = (regs['sp'] + 2) & 0xFFFF
        regs['ip'] = continuation

    def add_di():
        before = regs['di']
        regs['di'] = (before + 0x1E42) & 0xFFFF
        regs['flags'] = _add16_flags(regs['flags'], before, 0x1E42)

    if case['entry'] == 'leaf':
        _simulate_leaf(memory, regs, device, initial_di=regs['di'],
                       case=case, provider_state=provider_state)
    else:
        first_origin = _sim_read16(memory, device, regs['ds'], DRAWING_ORIGIN,
                                   regs['flags'])
        regs['di'] = first_origin
        add_di()
        regs['sp'] = (regs['sp'] - 2) & 0xFFFF
        _sim_write16(memory, device, regs['ss'], regs['sp'], INNER_RETURN,
                     regs['flags'])
        _simulate_leaf(memory, regs, device, initial_di=regs['di'],
                       case=case, provider_state=provider_state)
        child_target = _sim_read16(memory, device, regs['ss'], regs['sp'],
                                   regs['flags'])
        regs['sp'] = (regs['sp'] + 2) & 0xFFFF
        regs['ip'] = child_target
        if child_target != INNER_RETURN:
            status, continuation = 1, child_target
        else:
            alternate = _sim_read16(memory, device, regs['ds'], ALTERNATE_ORIGIN,
                                     regs['flags'])
            regs['di'] = alternate
            add_di()
            _simulate_leaf(memory, regs, device, initial_di=regs['di'],
                           case=case, provider_state=provider_state)

    if status == 0:
        if core:
            regs['ip'] = LEAF_RETURN
            continuation = LEAF_RETURN
        else:
            finish_return()
    return dict(memory=bytes(memory), regs=regs, device=device,
                status=status, continuation=continuation)


def assert_independent(case, memory, regs, device, observed, *, core):
    projected = independent(case, memory, regs, device, core=core)
    oracle_require(observed['status'] == projected['status'],
                   f"{case['name']}: original status {observed['status']}/"
                   f"{projected['status']} from independent live-return replay")
    oracle_require(observed['continuation'] == projected['continuation'],
                   f"{case['name']}: original continuation "
                   f"{observed['continuation']:04X}/{projected['continuation']:04X}")
    oracle_require(observed['memory'] == projected['memory'],
                   f"{case['name']}: independent byte-ordered VGA/RAM projection differs")
    oracle_require(observed['device'].state() == projected['device'].state(),
                   f"{case['name']}: independent VGA plane/latch projection differs")
    for name in REG_NAMES:
        if name == 'flags':
            mask = observed['flag_mask']
            oracle_require(((observed['regs'][name] ^ projected['regs'][name]) & mask) == 0,
                           f"{case['name']}: independent FLAGS projection differs")
        else:
            oracle_require(observed['regs'][name] == projected['regs'][name],
                           f"{case['name']}: independent {name} projection differs "
                           f"{observed['regs'][name]:04X}/{projected['regs'][name]:04X}")


def original_case(case, memory, regs, device, *, core):
    expected = original(case, memory, regs, device, core=core)
    assert_independent(case, memory, regs, device, expected, core=core)
    if case['entry'] == 'leaf':
        expected_ret = (LEAF_RETURN if core else
                        (0x0F02 if not core and case.get('sp') == 0x0008
                         else case.get('outer_return', 0x6A35)))
        oracle_require(expected['continuation'] == expected_ret,
                       f"{case['name']}: direct leaf did not reach the selected RET boundary")
    elif expected['status'] == 0:
        oracle_require(expected['continuation'] ==
                       (LEAF_RETURN if core else case.get('outer_return', 0x6A35)),
                       f"{case['name']}: wrapper did not reach the actual fallthrough/outer RET")
    else:
        oracle_require(case.get('sp', 0xC000) == 0x000A and
                       expected['continuation'] == 0x0F02,
                       f"{case['name']}: intended overwritten inner RET was not observed")
    return expected


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/status-display.md', 'assets/vgalemmi.exe',
        'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/inputs.json',
        'metadata/regions.json', 'metadata/hints.json', 'metadata/toolchain-lock.json',
        'src/program.asm', 'src/image_tail.asm', 'src/status_copy.asm',
        'src/game_code_late_after_entities.asm',
        'c/status_copy.c', 'c/status_copy.h', 'c/special_blit.h', 'c/regs.h',
        'c/lemmings_sym.h', 'tests/status_copy.py', 'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tools/resources.py',
        'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/unpack.py', 'tools/difftest.py', 'tools/coverage.py',
        'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'required input hashes missing: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def _sites(result):
    return {off for source, off in result['sites'] if source == 'main'}


def _edges(result):
    return {edge[1:] for edge in result['edges'] if edge[0] == 'main'}


def original_campaign(cases, before):
    oracle_require(before == input_hashes(), 'status-copy inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in cases:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = original_case(case, initial, regs, device, core=core)
            own_sites, own_edges = _sites(expected), _edges(expected)
            rows.append(dict(name=case['name'], core=core,
                             sites=sorted(own_sites), edges=[list(edge) for edge in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events']),
                             status=expected['status'], continuation=expected['continuation'],
                             provider_used=sorted(expected['used'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == SITES,
        f'original executed site union differs: missing={sorted(SITES-sites)} '
        f'extra={sorted(sites-SITES)}')
    oracle_require(edges == EDGES,
        f'original branch outcomes differ: missing={sorted(EDGES-edges)} '
        f'extra={sorted(edges-EDGES)}')
    oracle_require(before == input_hashes(), 'status-copy inputs changed during original preflight')
    return rows, sites, edges


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = CopyAccess(case, memory, regs, device)
        self.events, self.used = self.access.events, self.access.used

        def read(_ctx, _memory, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-copy read callback failed: {error}')
                return 0

        def write(_ctx, _memory, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-copy write callback failed: {error}')

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'native status-copy OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-copy-m{mutation}.dll',
                     mutation, 'status_copy')
        self.lib = ct.CDLL(str(path))
        for suffix in ('vga', 'both_origins'):
            core = getattr(self.lib, f'lmn_copy_status_region_to_{suffix}_core')
            core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
            core.restype = Result
            adapter = getattr(self.lib, f'lmn_copy_status_region_to_{suffix}_adapter')
            adapter.argtypes = [MEM, ct.POINTER(interactions.Regs), ct.POINTER(RasterBus)]
            adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs_dict = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs_dict, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**regs_dict)
        suffix = 'vga' if case['entry'] == 'leaf' else 'both_origins'
        if core:
            call = Call(*(regs_dict[REG_FIELDS[name]] for name in CORE_NAMES))
            result = getattr(self.lib, f'lmn_copy_status_region_to_{suffix}_core')(
                ram, ct.byref(call), ct.byref(callback.bus))
            for role in CORE_NAMES:
                setattr(regs, REG_FIELDS[role], getattr(result, role))
            regs.ip = result.continuation
            status = result.status
        else:
            status = getattr(self.lib,
                f'lmn_copy_status_region_to_{suffix}_adapter')(
                    ram, ct.byref(regs), ct.byref(callback.bus))
        final = {name: getattr(regs, name) & 0xFFFF for name in REG_NAMES}
        return dict(memory=bytes(memory), regs=final, events=callback.events,
                    used=set(callback.used), device=device, status=status,
                    continuation=final['ip'])


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered bus event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    expected = original_case(case, initial, regs, device, core=core)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
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
    return dict(name=case['name'], core=core, sites=sorted(_sites(expected)), edges=[],
                steps=expected['steps'], events=len(expected['events']),
                status=expected['status'], continuation=expected['continuation'],
                provider_used=sorted(expected['used']))


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'status-copy inputs changed before native worker')
    cases = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in cases:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == SITES,
        f'native site union differs: missing={sorted(SITES-sites)}')
    oracle_require(edges == EDGES,
        f'native branch outcomes differ: missing={sorted(EDGES-edges)}')

    cases_by_name = {case['name']: case for case in cases}
    witnesses = {
        1: ('leaf-backward-df', True),
        2: ('leaf-live-ds-pop-mirror', True),
        3: ('leaf-overlap-sequential-movsb', True),
        4: ('wrapper-two-origins-forward', True),
        5: ('wrapper-late-alternate-origin-provider', True),
        6: ('wrapper-first-child-ret-changed', True),
        7: ('leaf-forward', True),
    }
    mutants = []
    for mutation, (name, core) in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, cases_by_name[name], core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise interactions.OracleFailure(
                f'status-copy mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'status-copy inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[WRAPPER_ENTRY, END]], leaf_code_range=[LEAF_ENTRY, END],
        translated_code_bytes=CODE_BYTES, instruction_sites=len(SITES),
        static_instruction_addresses=sorted(SITES), branch_edge_count=0,
        static_branch_edges=[], case_count=len(cases),
        core_adapter_comparisons=len(rows), mutation_count=len(mutants),
        mutations=mutants, executed_instruction_addresses=sorted(sites),
        branch_edges=[], cases=rows, total_bus_events=total_events,
        original_instruction_steps=total_steps, input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain=('Status region copy: leaf 7602..7629 and wrapper 75EF..7629. '
                'The wrapper executes its real 75F7 CALL/7629 RET to 75FA, then '
                'continues by fallthrough for the alternate-origin pass. Fixtures '
                'cover DF, sequential overlap, live POP DS, overwritten inner RET, '
                'late alternate-origin reads, VGA stack/source/destination aliases, '
                'and 20-bit physical stack-word wrap.')))
    print(f'PASS status copy: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/0 edges, {total_events} events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-copy-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        rows, sites, edges = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_ranges=[[WRAPPER_ENTRY, END]],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(SITES),
            static_instruction_addresses=sorted(SITES), branch_edge_count=0,
            branch_edges=[], executed_instruction_addresses=sorted(sites),
            case_count=len(make_cases()), core_adapter_comparisons=len(rows),
            cases=rows, input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_callback_event_limit=MAX_EVENTS),
            domain='Original-only status-copy preflight; no native evidence.'))
        print(f'PASS original status copy: {len(make_cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/0 edges', flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    with temporary_build_directory(prefix='status-copy-native-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', directory, str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
