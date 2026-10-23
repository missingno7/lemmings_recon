"""Bounded differential checks for the 3AC8 two-call minimap status prefix."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as interactions
import minimap_connected as column_leaf
from minimap_vga import MinimapVga, VGA_BASE
from unpack import ASSET, unpack

SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, BOUNDARY = 0x3AC8, 0x3ACE
COLUMN, COLUMN_RET = 0x796F, 0x7A24
VIEWPORT, VIEWPORT_RET = 0x7A5A, 0x7BB7
COLUMN_AFTER, VIEWPORT_AFTER = 0x3ACB, 0x3ACE
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
DEFINED_FLAGS = interactions.FLAGS | 0x0400  # DF is preserved by both children.
MAX_INSTRUCTIONS, MAX_EVENTS = 32768, 8192
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'minimap-status-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, BOUNDARY)
COLUMN_INS = {pc: ins for part in column_leaf.PART.values()
              for pc, ins in part.items()}
VIEWPORT_INS = decoded_span(VIEWPORT, VIEWPORT_RET + 1)
INTEGRATED_INS = dict(OWN_INS)
for group in (COLUMN_INS, VIEWPORT_INS):
    for pc, ins in group.items():
        prior = INTEGRATED_INS.get(pc)
        if prior is not None and (prior.bytes != ins.bytes or
                                  prior.size != ins.size):
            raise RuntimeError(f'minimap-status instruction conflict at {pc:04X}')
        INTEGRATED_INS[pc] = ins

MAIN_CALL_RETURNS = {
    ENTRY: ({COLUMN_RET}, 2),
    COLUMN_AFTER: ({VIEWPORT_RET}, 2),
    0x79F8: ({0x7A38}, 1),
    0x7A2C: ({0x7A54, 0x7A59}, 1),
}


CORE_FIELDS = (
    'value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
    'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
    'extra_segment', 'stack_segment', 'stack_offset', 'flags',
)
CORE_REGS = (
    'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es', 'ss', 'sp',
    'flags',
)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_FIELDS]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                CORE_FIELDS +
                ('continuation', 'status', 'child_entry', 'child_status')]


class OracleFailure(AssertionError):
    """The original or a bounded provider failed to reach a declared boundary."""


class NativeMismatch(AssertionError):
    """A completed native call differs from the bounded original."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def cases():
    rows = [
        dict(name='normal-zero-alignment-all-ones', seed=0x3AC800,
             column=0, viewport_word=0, drawing_origin=0x1800,
             all_ones=True, flags=0x02D7, independent=True),
        dict(name='normal-seven-pixel-offset-if-clear', seed=0x3AC801,
             column=0x40, viewport_word=0x0070, drawing_origin=0x2100,
             flags=0x00D7, independent=True),
        dict(name='normal-df-set-if-set', seed=0x3AC802,
             column=0x7FF0, viewport_word=0x4050, drawing_origin=0xF000,
             df=True, flags=0x06D7, independent=True),
        dict(name='normal-column-signed-negative-wrap', seed=0x3AC803,
             column=0x8000, viewport_word=0xFFFF, drawing_origin=0xE100,
             flags=0x04D7, independent=True),
        dict(name='normal-nonzero-column-and-retained-planes', seed=0x3AC804,
             column=0x00C0, viewport_word=0x0020, drawing_origin=0x3100,
             flags=0x08D7, independent=True),
        dict(name='stack-mirror-live-pop-ds-feeds-viewport',
             seed=0x3AC805, column=0, ss=0x5000, sp=0x000C,
             provider='stack-mirror-return-restores',
             viewport_segment=0x0F02, viewport_word=0x7050,
             drawing_origin=0xF000, entry_viewport_word=0x0010,
             entry_drawing_origin=0x2000, expected='ds-mirror'),
        dict(name='inner-column-sample-return-changed', seed=0x3AC806,
             column=0, provider='inner-column-return',
             changed_return=0x7A38, expected='inner-column'),
        dict(name='column-call-live-return-word-changed', seed=0x3AC807,
             column=0, provider='column-call-return',
             changed_return=0x4567, expected='column-call'),
        dict(name='viewport-call-live-return-word-changed', seed=0x3AC808,
             column=0, provider='viewport-call-return',
             changed_return=0x3456, expected='viewport-call'),
        dict(name='low-stack-offset-wrap-through-nested-frames',
             seed=0x3AC809, column=0x30, ss=0xFFFF, sp=0x0004,
             provider='column-call-return', changed_return=0x0003,
             viewport_word=0x0030, drawing_origin=0x2200,
             flags=0x02D7, expected='column-call'),
        dict(name='signed-column-upper-bound-is-reset', seed=0x3AC80A,
             column=0x00C0, viewport_word=0x0010, drawing_origin=0x2300,
             flags=0x0AD7, independent=True),
        dict(name='viewport-destination-wraps-offset', seed=0x3AC80B,
             column=0x50, viewport_word=0x7070, drawing_origin=0xF100,
             flags=0x0ED7, independent=True),
    ]
    for index, case in enumerate(rows):
        case.setdefault('column', 0)
        case.setdefault('flags', 0x0ED7)
        case.setdefault('ss', 0x5000)
        case.setdefault('sp', 0xD000)
        case.setdefault('viewport_word', 0x0020)
        case.setdefault('drawing_origin', 0x2000)
        case.setdefault('outer_return', 0x6B6B)
        case.setdefault('changed_return', 0x4321)
        case.setdefault('expected', 'ready')
        case.setdefault('independent', False)
        case.setdefault('seed', 0x3AC900 + index)
    oracle_require(len(rows) == 12 and
                   len({case['name'] for case in rows}) == len(rows),
                   'minimap-status fixture inventory changed')
    return rows


def setup(case):
    # Reuse the column leaf's canonical relocated RAM/source-plane preparation,
    # then enter at the actual 3AC8 caller with all thirteen live registers.
    mem, regs, flags = column_leaf.prepare(case, True)
    regs.update(ip=ENTRY, ss=case['ss'] & 0xFFFF, sp=case['sp'] & 0xFFFF)
    flags = ((case['flags'] & DEFINED_FLAGS) | 2) & ~0x0100
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    regs['flags'] = flags
    put16(mem, regs['ds'], 0x0000,
          case.get('entry_viewport_word', case['viewport_word']))
    put16(mem, regs['ds'], 0x1F76,
          case.get('entry_drawing_origin', case['drawing_origin']))
    if 'viewport_segment' in case:
        put16(mem, case['viewport_segment'], 0x0000, case['viewport_word'])
        put16(mem, case['viewport_segment'], 0x1F76, case['drawing_origin'])
    put16(mem, regs['ss'], regs['sp'], case['outer_return'])
    device = column_leaf.devices(case, regs, True)
    oracle_require(len(mem) == SIZE and len(regs) == len(interactions.REG_NAMES),
                   case['name'] + ': setup memory/register shape changed')
    return mem, regs, flags, device


class StatusAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def _provider(self, kind, address):
        super()._provider(kind, address)
        effect = self.case.get('provider')
        if (effect is None or kind != 'read' or
                self.device is None or not VGA_BASE <= (address & MASK) < VGA_BASE + 0x10000):
            return
        count = self.device.outcount
        if effect == 'stack-mirror-return-restores' and count == 9 and \
                'column-alias-return-restore' not in self.used:
            offset, value, key = self.case['sp'] - 2, COLUMN_AFTER, \
                'column-alias-return-restore'
        elif effect == 'stack-mirror-return-restores' and count == 15 and \
                'viewport-alias-return-restore' not in self.used:
            offset, value, key = self.case['sp'] - 2, VIEWPORT_AFTER, \
                'viewport-alias-return-restore'
        elif effect == 'inner-column-return' and count == 8 and effect not in self.used:
            # Parent CALL, column PUSH DS, row CALL, row PUSH CX/SI, sample CALL.
            offset, value, key = self.case['sp'] - 12, \
                self.case['changed_return'], effect
        elif effect == 'column-call-return' and count == 9 and effect not in self.used:
            offset, value, key = self.case['sp'] - 2, \
                self.case['changed_return'], effect
        elif effect == 'viewport-call-return' and count == 15 and effect not in self.used:
            offset, value, key = self.case['sp'] - 2, \
                self.case['changed_return'], effect
        else:
            return
        self.modify_word(self.case['ss'], offset, value)
        self.used.add(key)

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('minimap-status OUT event budget exhausted')
        if self.device is None:
            raise OracleFailure('minimap-status VGA port write lacks a device')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


def original(case, memory, regs, device):
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=DEFINED_FLAGS,
        main_instructions=INTEGRATED_INS,
        main_call_returns=MAIN_CALL_RETURNS,
        stop_offsets={BOUNDARY: 0}, access_factory=StatusAccess,
        instruction_limit=MAX_INSTRUCTIONS)


def validate_original(case, observed):
    expected = case['expected']
    if expected == 'ready':
        status, continuation, child_entry, child_status = 0, BOUNDARY, 0, 0xFFFF
        oracle_require(('main', COLUMN) in observed['sites'] and
                       ('main', VIEWPORT) in observed['sites'],
                       case['name'] + ': normal path missed a child entry; '
                       f'status={observed["status"]} '
                       f'continuation={observed["continuation"]:04X} '
                       f'sites={observed["sites"]!r}')
        oracle_require(('main', COLUMN_RET) in observed['sites'] and
                       ('main', VIEWPORT_RET) in observed['sites'],
                       case['name'] + ': normal path missed a child RET')
    elif expected == 'inner-column':
        status, continuation, child_entry, child_status = (
            1, case['changed_return'], COLUMN, 1)
        oracle_require('inner-column-return' in observed['used'] and
                       continuation == case['changed_return'],
                       case['name'] + ': live inner column return provider did not fire')
    elif expected == 'column-call':
        status, continuation, child_entry, child_status = (
            2, case['changed_return'], COLUMN, 0)
        oracle_require('column-call-return' in observed['used'],
                       case['name'] + ': column CALL return provider did not fire')
        oracle_require(('main', VIEWPORT) not in observed['sites'],
                       case['name'] + ': changed first CALL incorrectly reached viewport')
    elif expected == 'viewport-call':
        status, continuation, child_entry, child_status = (
            2, case['changed_return'], VIEWPORT, 0)
        oracle_require('viewport-call-return' in observed['used'] and
                       ('main', VIEWPORT) in observed['sites'],
                       case['name'] + ': live viewport CALL return was not changed')
    elif expected == 'ds-mirror':
        status, continuation, child_entry, child_status = (0, BOUNDARY, 0, 0xFFFF)
        oracle_require({'column-alias-return-restore',
                        'viewport-alias-return-restore'} <= observed['used'] and
                       ('main', VIEWPORT) in observed['sites'] and
                       observed['regs']['ds'] == 0x0F02,
                       case['name'] + ': live mirror POP DS did not reach viewport')
    else:
        raise OracleFailure(case['name'] + ': unknown expected status boundary')
    oracle_require((observed['status'], observed['continuation']) ==
                   (status, continuation),
                   case['name'] + f': original status/continuation '
                   f'{observed["status"]}/{observed["continuation"]:04X} != '
                   f'{status}/{continuation:04X}')
    if expected == 'ready':
        oracle_require(observed['regs']['sp'] == case['sp'],
                       case['name'] + ': two actual CALL frames did not balance')
    return status, continuation, child_entry, child_status


def shifted_pair_bytes(high, low, count):
    value = ((high & 0xFFFF) << 16) | (low & 0xFFFF)
    value >>= count
    high, low = (value >> 16) & 0xFFFF, value & 0xFFFF
    return (high >> 8, high & 0xFF, low >> 8, low & 0xFF)


def independent_viewport_planes(memory, data_segment, flags, device):
    """Project the 7A5A source/destination math onto independent VGA planes."""
    device.out(0x3C4, 0x0F02, flags)
    for value in (0x0000, 0x0C01, 0x0005, 0x0003):
        device.out(0x3CE, value, flags)
    coordinate = get16(memory, data_segment, 0)
    origin = get16(memory, data_segment, 0x1F76)
    di = ((coordinate >> 7) + 0x2172 + origin + 2) & 0xFFFF
    shift = (coordinate >> 4) & 7
    step = -1 if flags & 0x0400 else 1

    def paint_group(start, masks):
        nonlocal di
        for mask_byte in masks:
            device.out(0x3CE, ((mask_byte & 0xFF) << 8) | 8, flags)
            address = VGA_BASE + (di & 0xFFFF)
            device.read(memory, address, flags)
            device.write(memory, address, mask_byte, flags)
            di = (di + step) & 0xFFFF

    first = shifted_pair_bytes(0xFFFF, 0xFF00, shift)
    paint_group(di, first)
    di = (di + 0x340) & 0xFFFF
    paint_group(di, first)
    di = (di - 0x30) & 0xFFFF

    masks = shifted_pair_bytes(0x8000, 0x0100, shift)
    for _ in range(18):
        paint_group(di, masks)
        di = (di - 0x30) & 0xFFFF


def independent_planes(case, memory, regs, flags, device):
    memory = bytearray(memory)
    device = copy.deepcopy(device)
    column, _bits, planes, _dest, _stored = column_leaf.independent_column(
        memory, regs, flags, device)
    device.planes = [bytearray(plane) for plane in planes]
    independent_viewport_planes(memory, regs['ds'], flags, device)
    return device.planes


def validate_independent_original(case, memory, regs, flags, device, observed):
    if case.get('independent'):
        expected = independent_planes(case, memory, regs, flags, device)
        oracle_require(observed['device'].planes == expected,
                       case['name'] + ': independent original plane projection differs')
        return expected
    return None


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: bus event count {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        require(got[:3] == ref[:3],
                f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
                f'under {ref[4]:04X}')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = StatusAccess(dict(case, _native=True), memory,
                                   dict(regs), copy.deepcopy(device))

        def read(_context, _memory, address, flags):
            try:
                return self.access.access('read', address, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def write(_context, _memory, address, value, flags):
            try:
                self.access.access('write', address, flags, DEFINED_FLAGS, value)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def output(_context, port, value, flags):
            try:
                self.access.out_word(port, value, flags, DEFINED_FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(output))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'minimap-status-m{mutation}.dll',
                     mutation, 'minimap_status')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_update_minimap_status_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_update_minimap_status_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        bus = NativeBus(case, memory, initial_regs, initial_device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**initial_regs)
        if core:
            call = Call(*(initial_regs[name] for name in CORE_REGS))
            out = self.core(ram, ct.byref(call), ct.byref(bus.bus))
            values = {reg: getattr(out, field) & 0xFFFF
                      for field, reg in zip(CORE_FIELDS, CORE_REGS)}
            values['ip'] = out.continuation & 0xFFFF
            status, child_entry, child_status = (
                out.status, out.child_entry, out.child_status)
        else:
            status = self.adapter(ram, ct.byref(regs), ct.byref(bus.bus))
            values = {name: getattr(regs, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
            child_entry = child_status = None
        return dict(memory=bytes(memory), regs=values, device=bus.access.device,
                    events=bus.access.events, providers=set(bus.access.used),
                    status=status, child_entry=child_entry,
                    child_status=child_status)


def compare_device(label, actual, expected):
    require(actual is not None and expected is not None,
            label + ': VGA device is required')
    require(actual.state() == expected.state(),
            label + ': VGA planes/latches/registers differ')


def compare_case(native, case, memory=None, regs=None, flags=None, device=None,
                 observed=None, *, core):
    if memory is None:
        memory, regs, flags, device = setup(case)
    if observed is None:
        observed = original(case, memory, regs, device)
        validate_original(case, observed)
    independent = validate_independent_original(case, memory, regs, flags,
                                                device, observed)
    label = case['name'] + (' core' if core else ' adapter')
    actual = native.run(case, memory, regs, device, core=core)
    wanted_status, wanted_continuation, child_entry, child_status = \
        validate_original(case, observed)
    require(actual['status'] == wanted_status,
            f'{label}: status {actual["status"]}/{wanted_status}')
    require(actual['regs']['ip'] == wanted_continuation,
            f'{label}: continuation {actual["regs"]["ip"]:04X}/'
            f'{wanted_continuation:04X}')
    for name in interactions.REG_NAMES:
        flag_mask = observed['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ observed['regs'][name]) & flag_mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{observed["regs"][name]:04X} under {flag_mask:04X}')
    require(actual['memory'] == observed['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], observed['events'])
    require(actual['providers'] == observed['used'],
            f'{label}: providers {actual["providers"]}/{observed["used"]}')
    compare_device(label, actual['device'], observed['device'])
    if core:
        require((actual['child_entry'], actual['child_status']) ==
                (child_entry, child_status),
                f'{label}: child metadata '
                f'{actual["child_entry"]:04X}/{actual["child_status"]:04X} != '
                f'{child_entry:04X}/{child_status:04X}')
    if independent is not None:
        require(actual['device'].planes == independent,
                label + ': independent column/viewport whole-plane projection differs')
    own_sites = {address for source, address in observed['sites']
                 if source == 'main' and address in OWN_INS}
    return dict(name=case['name'], core=core, status=wanted_status,
                continuation=wanted_continuation,
                sites=sorted(own_sites), integrated_sites=len(observed['sites']),
                edges=len(observed['edges']), events=len(observed['events']),
                steps=observed['steps'], independent_planes=bool(independent))


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/symbols.json',
        'src/program.asm', 'src/game_code_late.asm',
        'src/minimap.asm', 'src/minimap_viewport.asm',
        'c/minimap_status.c', 'c/minimap_status.h',
        'c/minimap_column.c', 'c/minimap_column.h',
        'c/minimap_viewport.c', 'c/minimap_viewport.h',
        'c/minimap_row.c', 'c/minimap_row.h',
        'c/minimap_sample.c', 'c/minimap_sample.h', 'c/minimap_helpers.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/minimap_status.py', 'tests/minimap_connected.py',
        'tests/minimap_vga.py', 'tests/minimap_sample.py',
        'tests/minimap_row.py', 'tests/minimap_column.py',
        'tests/entity_interactions.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tools/resources.py',
        'tools/common.py', 'tools/unpack.py', 'tools/cbuild.py',
        'tools/bounded_process.py', 'tools/difftest.py', 'tools/coverage.py',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'missing input hash dependencies: ' + repr(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def verify_static_identity():
    oracle_require(len(OWN_INS) == 2 and
                   sum(ins.size for ins in OWN_INS.values()) == 6 and
                   all(ins.mnemonic.lower() == 'call' for ins in OWN_INS.values()),
                   'the 3AC8 prefix is not the exact two-CALL six-byte span')
    oracle_require(COLUMN_RET in COLUMN_INS and VIEWPORT_RET in VIEWPORT_INS,
                   'minimap child RET boundary is missing from integrated map')
    oracle_require(set(MAIN_CALL_RETURNS) ==
                   {ENTRY, COLUMN_AFTER, 0x79F8, 0x7A2C},
                   'actual minimap CALL contracts changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed image identity changed')


def original_campaign(before):
    oracle_require(before == input_hashes(),
                   'minimap-status inputs changed before original preflight')
    verify_static_identity()
    rows, sites = [], set()
    total_events = total_steps = 0
    for case in cases():
        memory, regs, flags, device = setup(case)
        observed = original(case, memory, regs, device)
        validate_original(case, observed)
        validate_independent_original(case, memory, regs, flags, device, observed)
        own_sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
        sites.update(own_sites)
        total_events += len(observed['events'])
        total_steps += observed['steps']
        rows.append(dict(name=case['name'], status=observed['status'],
                         continuation=observed['continuation'],
                         sites=sorted(own_sites), events=len(observed['events']),
                         steps=observed['steps']))
        gc.collect()
    oracle_require(sites == set(OWN_INS),
                   f'parent instruction-site union {sorted(sites)} != {sorted(OWN_INS)}')
    oracle_require(before == input_hashes(),
                   'minimap-status inputs changed during original-only preflight')
    print(f'PASS minimap status original: {len(rows)} fixtures, {len(sites)} own sites, '
          f'{total_events} events, {total_steps} steps; bounded original only',
          flush=True)
    return rows


def worker(directory):
    before = input_hashes()
    original_rows = original_campaign(before)
    native = Native(directory)
    rows, own_sites, integrated_sites, edges = [], set(), set(), set()
    total_events = total_steps = 0
    fixture_map = {case['name']: case for case in cases()}
    for case in cases():
        memory, regs, flags, device = setup(case)
        observed = original(case, memory, regs, device)
        validate_original(case, observed)
        for core in (True, False):
            row = compare_case(native, case, memory, regs, flags, device,
                               observed, core=core)
            rows.append(row)
            own_sites.update(row['sites'])
            total_events += row['events']
            total_steps += row['steps']
        integrated_sites.update(address for source, address in observed['sites']
                                if source == 'main')
        edges.update(observed['edges'])
        gc.collect()

    witnesses = {
        1: 'normal-zero-alignment-all-ones',
        2: 'stack-mirror-live-pop-ds-feeds-viewport',
        3: 'column-call-live-return-word-changed',
        4: 'inner-column-sample-return-changed',
        5: 'viewport-call-live-return-word-changed',
    }
    mutations = []
    for mutation, name in witnesses.items():
        case = fixture_map[name]
        memory, regs, flags, device = setup(case)
        observed = original(case, memory, regs, device)
        validate_original(case, observed)
        try:
            compare_case(Native(directory, mutation), case, memory, regs, flags,
                         device, observed, core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'minimap-status mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(len(mutations) == len(witnesses),
                   'minimap-status mutation witness inventory changed')
    oracle_require(before == input_hashes(),
                   'minimap-status inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, BOUNDARY],
        translated_code_bytes=6, instruction_sites=len(OWN_INS),
        integrated_child_ranges=[[COLUMN, COLUMN_RET + 1],
                                 [VIEWPORT, VIEWPORT_RET + 1]],
        case_count=len(fixture_map), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(own_sites),
        static_instruction_addresses=sorted(OWN_INS),
        integrated_instruction_addresses=sorted(integrated_sites),
        branch_edges=sorted(edges), total_bus_events=total_events,
        original_instruction_hook_steps=total_steps,
        original_only_case_count=len(original_rows), input_hashes=before,
        cases=rows, limits=dict(worker_seconds=WORKER_SECONDS,
                                process_memory_mib=PROCESS_MIB,
                                windows_tree_memory_mib=TREE_MIB,
                                original_instruction_limit=MAX_INSTRUCTIONS,
                                ordered_bus_event_limit=MAX_EVENTS,
                                callback_budget_exit=GUARD_EXIT,
                                callback_error_exit=CALLBACK_EXIT),
        domain='Only the two CALL instructions at 3AC8 and 3ACB are owned. '
               'The original runs the actual 796F column CALL and 7A5A viewport '
               'CALL, including live nested 79F8/7A2C child frames, then stops '
               'at 3ACE before the untranslated status-count body. Comparisons '
               'include full RAM, thirteen registers, defined FLAGS, ordered '
               'VGA/port/access events, child status and live return words. '
               'Independent normal-path plane projection covers column rows and '
               'the viewport paint footprint; child-only matrices remain scoped '
               'to their leaf reports.'))
    print(f'PASS minimap status: {len(fixture_map)} fixtures x core/adapter, '
          f'{len(own_sites)} owned sites, {len(integrated_sites)} integrated sites, '
          f'{total_events} events, {len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--original-worker'], cwd=ROOT,
                             timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                             check=True)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return
    if sys.argv[1:] == ['--original-worker']:
        original_campaign(input_hashes())
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('usage: minimap_status.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='minimap-status-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
