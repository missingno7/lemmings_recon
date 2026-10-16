"""Bounded differential checks for the 01B0..01B5 create/update prefix."""
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
import entity_create as create_leaf
import entity_interactions as interactions
import entity_update as update
from unpack import ASSET, unpack

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
LOAD = interactions.MAIN_SEG
ENTRY, CREATE_CALL, UPDATE_CALL, BOUNDARY = 0x01B0, 0x01B0, 0x01B3, 0x01B6
CREATE_RET, UPDATE_RETS = create_leaf.RETURN_IP, set(update.RETURNS)
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
RECORD_BASE, RECORD_SIZE = 0x0088, 0x002D
COORDINATE_BASE = 0x0E98
MAX_INSTRUCTIONS, MAX_EVENTS = 12000, 8192
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-batch-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-batch-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, BOUNDARY)


def merge_main_maps(*groups):
    result = {}
    for group in groups:
        for address, ins in group.items():
            prior = result.get(address)
            if prior is not None and (prior.bytes != ins.bytes or
                                      prior.size != ins.size):
                raise RuntimeError(f'main instruction-map conflict at {address:04X}')
            result[address] = ins
    return result


INTEGRATED_INS = merge_main_maps(OWN_INS, create_leaf.OWN_INS,
                                 update.INTEGRATED_INS)
MAIN_CALL_RETURNS = dict(update.MAIN_CALL_RETURNS)
MAIN_CALL_RETURNS[CREATE_CALL] = ({CREATE_RET}, 1)
MAIN_CALL_RETURNS[UPDATE_CALL] = (UPDATE_RETS, 1)
MAIN_RET_CONTINUATIONS = update.MAIN_RET_CONTINUATIONS
OWN_EDGES = set()


class BatchCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class BatchResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status', 'child_entry', 'child_status')]


class OracleFailure(AssertionError):
    """A bounded original/provider failed to reach a declared boundary."""


class NativeMismatch(AssertionError):
    """A completed native result differs from the original execution."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def cases():
    """Focused two-child handoffs; child matrices remain owned by their suites."""
    rows = [
        dict(name='create-then-advance-new-record', bound=0, limit=1,
             create_countdown=1, vga=True, visit_new=True),
        dict(name='old-inactive-then-new-record-visited', bound=1, limit=2,
             existing_inactive=0xFF, create_countdown=1, vga=True,
             visit_new=True),
        dict(name='creation-gate-skips-before-existing-update', bound=1,
             limit=2, creation_gate=0, existing_inactive=0xFF, vga=True),
        dict(name='countdown-nonzero-skips-before-existing-update', bound=1,
             limit=2, create_countdown=3, existing_inactive=0xFF, vga=True),
        dict(name='countdown-zero-wrap-skips-before-existing-update', bound=1,
             limit=2, create_countdown=0, existing_inactive=0xFF, vga=True),
        dict(name='equal-limit-skips-before-existing-update', bound=1,
             limit=1, create_countdown=1, existing_inactive=0xFF, vga=True),
        dict(name='update-gate-ff-skips-create-and-update', bound=1,
             update_gate=0xFF, limit=2, existing_inactive=0xFF, vga=True),
        dict(name='bound-ff-create-wraps-zero-update-bound', bound=0xFF,
             limit=0, create_countdown=1, cx=0xA55A, vga=True),
        dict(name='bound-50-clears-coordinate-alias-and-visits-slot-80',
             bound=0x50, limit=0x51, create_countdown=1,
             inactive_prefix=0x50, existing_inactive=0xFF,
             vga=True, visit_new=True),
        dict(name='create-call-return-alias-changes-to-update-continuation',
             bound=0, limit=1, create_countdown=1, create_ret_alias=True,
             callback=BOUNDARY, expected='changed-create'),
        dict(name='update-call-return-provider-changes-to-create-continuation',
             bound=0, limit=1, create_countdown=1,
             provider='readback-return', changed_return=CREATE_CALL,
             expected='changed-update', vga=True),
        dict(name='unbound-sound-child-status-forwarded', bound=1, limit=2,
             create_countdown=1, existing_state=0x8000, cadence=0x0F,
             enabled=0xFF, options=3, sound_vector=(0x1234, 0x7000),
             expected='child', vga=True),
        dict(name='sound-returned-ds-owns-live-update-tail', bound=1,
             limit=2, create_countdown=1, existing_state=0x8000,
             cadence=0x0F, enabled=0xFF, options=3,
             provider='batch-sound-live-ds', alternate_ds=0x7100,
             driver='adlib', vga=True),
        dict(name='physical-stack-word-wrap-through-both-calls', bound=0,
             limit=1, create_countdown=1, ss=0xFFFF, sp=0x11, vga=True,
             visit_new=True),
        dict(name='df-set-create-loop-and-update-pixel-path', bound=0,
             limit=1, create_countdown=1, df=True, vga=True, visit_new=True),
        dict(name='update-call-live-registers-and-defined-flags', bound=0,
             limit=1, create_countdown=1, flags=0x7ED7, ax=0xA51C,
             bx=0x73D2, cx=0xC321, dx=0x15B7, si=0x99A0, di=0x6C4E,
             bp=0xB3E1, vga=True, visit_new=True),
        dict(name='new-record-callback-and-stack-aliases', bound=0,
             limit=1, create_countdown=1, ds=DATA_SEGMENT, ss=DATA_SEGMENT,
             sp=0xD000, callback=0x5A73, vga=True, visit_new=True),
    ]
    for index, row in enumerate(rows):
        row.setdefault('update_gate', 0)
        row.setdefault('creation_gate', 0xFF)
        row.setdefault('create_countdown', 1)
        row.setdefault('reload', 1)
        row.setdefault('limit', (row.get('bound', 0) + 1) & 0xFF)
        row.setdefault('callback', 0x6170)
        row.setdefault('outer_return', 0x7A5C)
        row.setdefault('existing_state', 0x0001)
        row.setdefault('existing_cadence', row.get('cadence', 3))
        row.setdefault('existing_inactive', 0)
        row.setdefault('existing_countdown', 0)
        row.setdefault('x', 0x20)
        row.setdefault('y', 0x20)
        row.setdefault('create_x', 0x20)
        row.setdefault('create_y', 0x20)
        row.setdefault('pitch', 0x00D0)
        row.setdefault('flags', 0x0ED7)
        row.setdefault('ds', DATA_SEGMENT)
        row.setdefault('ss', 0x5000)
        row.setdefault('sp', 0xD000)
        row.setdefault('enabled', 0)
        row.setdefault('options', 0)
        row.setdefault('driver', 'adlib')
        row.setdefault('vga', False)
        row.setdefault('seed', 0x1B0000 + index * 131)
    oracle_require(len(rows) == 17 and
                   len({row['name'] for row in rows}) == len(rows),
                   'entity-batch fixture inventory changed')
    return rows


def setup(case):
    """Use one canonical memory image for both children and their live frames."""
    template = dict(case)
    template.update(load=LOAD, gate=case.get('update_gate', 0),
                    bound=case.get('bound', 0),
                    state_bits=case.get('existing_state', 1),
                    cadence=case.get('existing_cadence', 3),
                    countdown=case.get('existing_countdown', 0),
                    inactive=case.get('existing_inactive', 0),
                    x=case.get('x', 0x20), y=case.get('y', 0x20),
                    vga=bool(case.get('vga', False)),
                    poison=bool(case.get('poison', False)))
    memory, regs, device, pc_binding, sound_binding = update.setup(template)
    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    ss = case.get('ss', 0x5000) & 0xFFFF
    sp = case.get('sp', 0xD000) & 0xFFFF
    regs.update(cs=LOAD, ip=ENTRY, ds=ds, ss=ss, sp=sp,
                ax=case.get('ax', regs['ax']) & 0xFFFF,
                bx=case.get('bx', regs['bx']) & 0xFFFF,
                cx=case.get('cx', regs['cx']) & 0xFFFF,
                dx=case.get('dx', regs['dx']) & 0xFFFF,
                si=case.get('si', RECORD_BASE) & 0xFFFF,
                di=case.get('di', regs['di']) & 0xFFFF,
                bp=case.get('bp', regs['bp']) & 0xFFFF)
    raw_flags = case.get('flags', regs['flags'])
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if case.get('df') else (flags & ~0x0400)
    regs['flags'] = flags
    put16(memory, ss, sp, case.get('outer_return', 0x7A5C))

    put8(memory, ds, 0x002B, case.get('update_gate', 0))
    put8(memory, ds, 0x0055, case.get('creation_gate', 0xFF))
    put8(memory, ds, 0x0048, case.get('create_countdown', 1))
    put8(memory, ds, 0x0049, case.get('reload', 1))
    put8(memory, ds, 0x0047, case.get('limit', 1))
    initial_bound = case.get('bound', 0) & 0xFF
    put8(memory, ds, 0x0043, initial_bound)
    put8(memory, ds, 0x0042, initial_bound)
    put8(memory, ds, 0x004B, 0)
    put8(memory, ds, 0x004C, 0)
    put8(memory, ds, 0x0050, 0)
    put16(memory, ds, 0x0004, case.get('pitch', 0x00D0))
    put16(memory, ds, 0x002E, case.get('callback', 0x6170))

    # The destination clear intentionally precedes the coordinate reads. At
    # bound 50h the destination overlaps the coordinate table itself.
    target = (RECORD_BASE + initial_bound * RECORD_SIZE) & 0xFFFF
    for index in range(RECORD_SIZE):
        put8(memory, ds, target + index,
             (0xD3 + index * 19 + case['seed']) & 0xFF)
    coordinate_words = case.get(
        'coordinates', (case.get('create_x', 0x20), case.get('create_y', 0x20)) * 4)
    for index, value in enumerate(coordinate_words):
        put16(memory, ds, COORDINATE_BASE + index * 2, value)

    # Creation's new record can be preceded by arbitrary live slots. The
    # 50h witness keeps the first eighty old slots inactive and proves that
    # the newly created slot is still visited without inventing an extent.
    inactive_prefix = case.get('inactive_prefix', 0)
    for index in range(min(inactive_prefix, initial_bound)):
        put8(memory, ds, RECORD_BASE + index * RECORD_SIZE + 0x26, 0xFF)
    if case.get('existing_inactive') is not None and initial_bound:
        put8(memory, ds, RECORD_BASE + 0x26,
             case.get('existing_inactive', 0) & 0xFF)

    # A deterministic first sample can drive the existing state-0800 sound
    # paths used by the parent's explicit child-boundary fixtures.
    if case.get('existing_state') == 0x8000:
        slot = RECORD_BASE
        put16(memory, ds, slot, case.get('x', 0x20))
        put16(memory, ds, slot + 2, case.get('y', 0x40))
        put16(memory, ds, slot + 8, 0x8000)
        put8(memory, ds, slot + 0x28, case.get('existing_cadence', 0x0F))

    if case.get('create_ret_alias'):
        regs['ds'] = regs['ss'] = ds
        regs['sp'] = (target + 0x16) & 0xFFFF
        put16(memory, regs['ss'], regs['sp'], case.get('outer_return', 0x7A5C))

    if case.get('provider') == 'batch-sound-live-ds':
        alternate = case['alternate_ds'] & 0xFFFF
        put8(memory, alternate, 0x0042, 1)
        put8(memory, alternate, 0x004B, 0)
        put8(memory, alternate, 0x0050, 0xFF)
        put16(memory, alternate, RECORD_BASE, case.get('x', 0x20))
        put16(memory, alternate, RECORD_BASE + 2, case.get('y', 0x40))

    if case.get('sound_vector') is not None:
        ip, cs = case['sound_vector']
        put16(memory, 0, 0x0184, ip)
        put16(memory, 0, 0x0186, cs)

    oracle_require(len(memory) == SIZE and len(regs) == len(interactions.REG_NAMES),
                   case['name'] + ': fixture memory/register shape changed')
    return memory, regs, device, pc_binding, sound_binding


class BatchAccess(update.UpdateAccess):
    """The update access model with the extra caller PUSH at 01B3."""
    event_limit = MAX_EVENTS

    def _provider(self, kind, address):
        super()._provider(kind, address)
        if self.case.get('provider') != 'batch-sound-live-ds' or kind != 'write':
            return
        if 'batch-sound-live-ds' in self.used:
            return
        driver = self.case.get('driver', 'adlib')
        latch = interactions.sound.TAILS[driver][4][1]
        if address & MASK == physical(interactions.SOUND_SEG, latch):
            # The caller's actual 01B3 CALL contributes one extra word below
            # the standalone 1F19 stack layout.
            self.modify_word(self.case.get('ss', 0x5000),
                             self.case.get('sp', 0xD000) - 12,
                             self.case['alternate_ds'])
            self.used.add('batch-sound-live-ds')


def original(case, memory, regs, device):
    return interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=INTEGRATED_INS,
        main_ret_continuations=MAIN_RET_CONTINUATIONS,
        main_call_returns=MAIN_CALL_RETURNS,
        stop_offsets={BOUNDARY: 0}, access_factory=BatchAccess,
        instruction_limit=MAX_INSTRUCTIONS)


def creation_expected(case, memory):
    create_case = dict(case)
    create_case.update(update_gate=case.get('update_gate', 0),
                       creation_gate=case.get('creation_gate', 0xFF),
                       countdown=case.get('create_countdown', 1),
                       reload=case.get('reload', 1),
                       bound=case.get('bound', 0),
                       limit=case.get('limit', 1),
                       callback=case.get('callback', 0x6170),
                       ds=case.get('ds', DATA_SEGMENT), ss=case.get('ss', 0x5000),
                       sp=case.get('sp', 0xD000))
    expected_memory, info = create_leaf.independent_memory(create_case, memory)
    should_create = (case.get('update_gate', 0) != 0xFF and
                     case.get('creation_gate', 0xFF) == 0xFF and
                     ((case.get('create_countdown', 1) - 1) & 0xFF) == 0 and
                     case.get('limit', 1) != case.get('bound', 0))
    oracle_require(bool(info['created']) == should_create,
                   case['name'] + ': independent creation gate projection disagrees')
    return expected_memory, info


def assert_clear_footprint(case, observed, info):
    if not info['created']:
        return
    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    start = info['record_start']
    addresses = [physical(ds, (start + index) & 0xFFFF)
                 for index in range(RECORD_SIZE)]
    events = observed['events']
    clear_start = None
    for index in range(len(events) - RECORD_SIZE + 1):
        run = events[index:index + RECORD_SIZE]
        if ([event[1] for event in run] == addresses and
                all(event[0] == 'write' and event[2] == 0 for event in run)):
            clear_start = index
            break
    oracle_require(clear_start is not None,
                   case['name'] + ': original lacks the exact 45-byte create clear')
    callback_at = next((i for i, event in enumerate(events)
                        if i > clear_start and event[0] == 'read' and
                        event[1] == physical(ds, 0x002E)), None)
    oracle_require(callback_at is not None and callback_at > clear_start + 44,
                   case['name'] + ': callback was read before record clear completed')
    if case.get('bound') == 0x50:
        source_at = next((i for i, event in enumerate(events)
                          if event[0] == 'read' and
                          event[1] == physical(ds, COORDINATE_BASE)), None)
        oracle_require(source_at is not None and source_at > clear_start + 44,
                       case['name'] + ': coordinate alias was read before the clear')


def validate_original(case, initial, observed):
    expected_memory, info = creation_expected(case, initial)
    assert_clear_footprint(case, observed, info)
    expected_boundary = case.get('expected', 'ready')
    if expected_boundary == 'ready':
        wanted = (0, BOUNDARY)
    elif expected_boundary == 'changed-create':
        wanted = (1, BOUNDARY)
    elif expected_boundary == 'changed-update':
        wanted = (1, case.get('changed_return', CREATE_CALL))
    elif expected_boundary == 'child':
        wanted = (1, case['sound_vector'][0])
    else:
        raise OracleFailure(case['name'] + ': unknown expected prefix boundary')
    oracle_require((observed['status'], observed['continuation']) == wanted,
                   case['name'] + f': original boundary {observed["status"]}/'
                   f'{observed["continuation"]:04X} != {wanted[0]}/{wanted[1]:04X}')

    if expected_boundary == 'changed-create':
        entry_sp = case.get('sp', 0xD000) & 0xFFFF
        if case.get('create_ret_alias'):
            target = (RECORD_BASE + (case.get('bound', 0) & 0xFF) *
                      RECORD_SIZE) & 0xFFFF
            entry_sp = (target + 0x16) & 0xFFFF
        oracle_require(observed['regs']['ip'] == BOUNDARY and
                       observed['regs']['sp'] == entry_sp,
                       case['name'] + ': create RET mismatch did not stop before update')
    if expected_boundary == 'child':
        oracle_require(observed['regs']['cs'] == 0x7000 and
                       observed['regs']['ip'] == 0x1234,
                       case['name'] + ': unbound child vector state changed')

    if info['created']:
        ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
        initial_bound = case.get('bound', 0) & 0xFF
        target = info['record_start']
        expected_bound = (initial_bound + 1) & 0xFF
        oracle_require(get8(observed['memory'], ds, 0x0043) == expected_bound,
                       case['name'] + ': creation did not publish wrapped live bound')
        # Fields not owned by the selected state transition remain exact
        # creation outputs. The X/direction/callback bytes expose touched data.
        oracle_require(get16(observed['memory'], ds, target) ==
                       get16(expected_memory, ds, target),
                       case['name'] + ': update changed the independent created X')
        oracle_require(get8(observed['memory'], ds, target + 0x27) == 1,
                       case['name'] + ': created direction byte changed unexpectedly')
        if case.get('visit_new') and expected_boundary == 'ready':
            oracle_require(get8(observed['memory'], ds, target + 0x28) == 1,
                           case['name'] + ': newly created record did not take state 0004')
            oracle_require(get8(observed['memory'], ds, target + 0x23) == 6,
                           case['name'] + ': three clear samples did not advance +23')
            oracle_require(get16(observed['memory'], ds, target + 2) ==
                           ((get16(expected_memory, ds, target + 2) + 3) & 0xFFFF),
                           case['name'] + ': new-record Y did not reflect its three probes')
    if case.get('provider') == 'batch-sound-live-ds':
        oracle_require(observed['used'] == {'batch-sound-live-ds'} and
                       observed['regs']['ds'] == case['alternate_ds'] and
                       get8(observed['memory'], case['alternate_ds'], 0x0042) == 0,
                       case['name'] + ': sound-returned DS did not own the live update tail')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered event count {len(actual)}/{len(expected)}')
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
        self.access = BatchAccess(dict(case, _native=True), memory,
                                  dict(regs), device)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            try:
                self.access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-batch-m{mutation}.dll',
                     mutation, 'entity_batch')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_entity_batch_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(BatchCall),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = BatchResult
        self.adapter = self.lib.lmn_entity_batch_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        native_bus = NativeBus(case, memory, initial_regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**initial_regs)
        pc = ct.byref(pc_binding) if pc_binding is not None else None
        sound = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = BatchCall(*(initial_regs[name] for name in
                               ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp',
                                'cs', 'ds', 'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), pc, sound,
                               ct.byref(native_bus.bus))
            regs.ax, regs.bx, regs.cx, regs.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            regs.si, regs.di, regs.bp = (result.record_cursor,
                                         result.object_cursor,
                                         result.candidate_y)
            regs.cs, regs.ds, regs.es = (result.code_segment,
                                         result.data_segment,
                                         result.extra_segment)
            regs.ss, regs.sp, regs.flags, regs.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
            child_entry, child_status = result.child_entry, result.child_status
        else:
            status = self.adapter(ram, ct.byref(regs), pc, sound,
                                  ct.byref(native_bus.bus))
            child_entry = child_status = None
        return dict(memory=bytes(memory),
                    regs={name: getattr(regs, name) & 0xFFFF
                          for name in interactions.REG_NAMES},
                    device=device, events=native_bus.access.events,
                    providers=set(native_bus.access.used), status=status,
                    continuation=regs.ip & 0xFFFF,
                    child_entry=child_entry, child_status=child_status)


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual is not None, label + ': missing VGA device')
    require(actual.state() == expected.state(),
            label + ': VGA planes/registers/latches differ')
    got_trace = [(a, b, c) for a, b, c, _ in actual.trace]
    ref_trace = [(a, b, c) for a, b, c, _ in expected.trace]
    require(got_trace == ref_trace, label + ': VGA trace differs')


def expected_batch_state(case, observed):
    boundary = case.get('expected', 'ready')
    if boundary == 'ready':
        return 0, BOUNDARY, 0, 0xFFFF
    if boundary == 'changed-create':
        return 1, BOUNDARY, 0x30A6, 0
    if boundary == 'changed-update':
        return 1, case.get('changed_return', CREATE_CALL), 0x1F19, 0
    if boundary == 'child':
        return 2, observed['continuation'], 0x2D0F, 1
    raise OracleFailure(case['name'] + ': invalid boundary expectation')


def compare_case(native, case, initial=None, regs=None, device=None,
                 pc_binding=None, sound_binding=None, observed=None, *, core):
    if initial is None:
        initial, regs, device, pc_binding, sound_binding = setup(case)
    if observed is None:
        observed = original(case, initial, regs, device)
        validate_original(case, initial, observed)
    label = case['name'] + (' core' if core else ' adapter')
    actual = native.run(case, initial, regs, device, pc_binding,
                        sound_binding, core=core)
    wanted_status, wanted_continuation, child_entry, child_status = \
        expected_batch_state(case, observed)
    require(actual['status'] == wanted_status,
            f'{label}: status {actual["status"]}/{wanted_status}')
    require(actual['continuation'] == wanted_continuation,
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{wanted_continuation:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        require(actual['regs'][name] == observed['regs'][name],
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{observed["regs"][name]:04X}')
    flag_mask = observed['flag_mask']
    require(((actual['regs']['flags'] ^ observed['regs']['flags']) & flag_mask) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{observed["regs"]["flags"]:04X} under {flag_mask:04X}')
    require(actual['memory'] == observed['memory'],
            label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], observed['events'])
    require(actual['providers'] == observed['used'],
            f'{label}: provider effects {actual["providers"]}/'
            f'{observed["used"]}')
    compare_device(label, actual['device'], observed['device'])
    if core:
        require((actual['child_entry'], actual['child_status']) ==
                (child_entry, child_status),
                f'{label}: child entry/status '
                f'{actual["child_entry"]:04X}/{actual["child_status"]:04X} '
                f'!= {child_entry:04X}/{child_status:04X}')
    own_sites = {address for source, address in observed['sites']
                 if source == 'main' and address in OWN_INS}
    return dict(name=case['name'], core=core, status=actual['status'],
                continuation=actual['continuation'], sites=sorted(own_sites),
                event_count=len(observed['events']), steps=observed['steps'],
                providers=sorted(observed['used']))


def input_hashes():
    paths = set(update.input_hashes())
    paths.update((
        'src/entry_services.asm', 'docs/entity-simulation.md',
        'tests/entity_create.py',
        'tests/entity_batch.py', 'c/entity_create.c', 'c/entity_create.h',
        'c/entity_batch.c', 'c/entity_batch.h'))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def verify_static_identity():
    oracle_require(sum(ins.size for ins in OWN_INS.values()) == 6 and
                   len(OWN_INS) == 2 and
                   {ins.mnemonic.lower() for ins in OWN_INS.values()} == {'call'},
                   f'prefix identity changed: {len(OWN_INS)} sites/'
                   f'{sum(ins.size for ins in OWN_INS.values())} bytes')
    oracle_require(not OWN_EDGES,
                   'the two-call prefix unexpectedly gained a branch')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned main image identity changed')
    calls = {address for address, ins in INTEGRATED_INS.items()
             if ins.mnemonic.lower() == 'call'}
    oracle_require(calls <= set(MAIN_CALL_RETURNS),
                   f'original CALL contracts missing {sorted(calls-set(MAIN_CALL_RETURNS))}')


def original_campaign(before):
    oracle_require(before == input_hashes(),
                   'entity-batch inputs changed before original preflight')
    verify_static_identity()
    specs = cases()
    rows, sites = [], set()
    total_events = total_steps = 0
    for case in specs:
        memory, regs, device, _pc, _sound = setup(case)
        observed = original(case, memory, regs, device)
        validate_original(case, memory, observed)
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
                   f'prefix site union {sorted(sites)} != {sorted(OWN_INS)}')
    oracle_require(before == input_hashes(),
                   'entity-batch inputs changed during original preflight')
    print(f'PASS entity batch original: {len(specs)} fixtures, {len(sites)} sites, '
          f'{total_events} events, {total_steps} steps; bounded original only',
          flush=True)
    return rows


def worker(directory):
    before = input_hashes()
    original_rows = original_campaign(before)
    specs = cases()
    native = Native(directory)
    rows, sites = [], set()
    total_events = total_steps = 0
    for case in specs:
        memory, regs, device, pc_binding, sound_binding = setup(case)
        observed = original(case, memory, regs, device)
        validate_original(case, memory, observed)
        for core in (True, False):
            row = compare_case(native, case, memory, regs, device,
                               pc_binding, sound_binding, observed, core=core)
            rows.append(row)
            sites.update(row['sites'])
            total_events += row['event_count']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == set(OWN_INS),
                   f'native prefix sites {sorted(sites)} != {sorted(OWN_INS)}')

    witnesses = {
        1: 'create-then-advance-new-record',
        2: 'bound-ff-create-wraps-zero-update-bound',
        3: 'create-call-return-alias-changes-to-update-continuation',
        4: 'unbound-sound-child-status-forwarded',
        5: 'sound-returned-ds-owns-live-update-tail',
    }
    by_name = {case['name']: case for case in specs}
    mutations = []
    for mutation, case_name in witnesses.items():
        mutant = Native(directory, mutation)
        case = by_name[case_name]
        memory, regs, device, pc_binding, sound_binding = setup(case)
        observed = original(case, memory, regs, device)
        validate_original(case, memory, observed)
        try:
            compare_case(mutant, case, memory, regs, device,
                         pc_binding, sound_binding, observed, core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=case_name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'entity-batch mutation {mutation} survived '
                                f'completed witness {case_name}')
        gc.collect()
    oracle_require(len(mutations) == len(witnesses),
                   'entity-batch mutation witness count changed')
    oracle_require(before == input_hashes(),
                   'entity-batch inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, BOUNDARY],
        translated_code_bytes=6, instruction_sites=len(OWN_INS),
        own_static_branch_edges=0, case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations, executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS), branch_edges=[],
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        original_only_case_count=len(original_rows), input_hashes=before,
        cases=rows,
        limits=dict(worker_seconds=WORKER_SECONDS,
                    process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    ordered_bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domain='Only the 01B0 and 01B3 caller instructions are owned. The original '
               'executes the real CALL 30A6/RET 314F followed by CALL 1F19 and '
               'stops at 01B6 before untranslated CALL 3944. Both caller RET '
               'contracts use their own live SS:SP words. Child instruction '
               'domains are borrowed from the maintained creation and update '
               'oracles; this suite adds no child coverage claim. Comparison '
               'includes full RAM, registers, flowing defined FLAGS, ordered '
               'VGA/port/memory events, child status and actual CALL returns.'))
    print(f'PASS entity batch: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} caller sites, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


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
        raise SystemExit('usage: entity_batch.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-batch-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
