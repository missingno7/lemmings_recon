"""Bounded original-versus-native checks for CreateEntityRecordIfDue."""
from __future__ import annotations

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
from unpack import ASSET, unpack

SIZE, MASK = interactions.SIZE, interactions.MASK
ALL_FLAGS = interactions.FLAGS
ENTRY, END = 0x30A6, 0x3150
RETURN_IP = 0x314F
MAIN_SEG = interactions.MAIN_SEG
DATA_SEGMENT = (MAIN_SEG + 0x09A9) & 0xFFFF
RECORD_BASE, RECORD_SIZE = 0x0088, 0x002D
COORDINATE_BASE = 0x0E98
MAX_INSTRUCTIONS, MAX_EVENTS = 1024, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-create-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-create-original-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if (ins.operands and
                ins.operands[-1].type == capstone.x86.X86_OP_IMM):
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


OWN_EDGES = branch_edges(OWN_INS)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status')]


class OracleFailure(AssertionError):
    """The bounded original/provider failed to reach its declared boundary."""


class NativeMismatch(AssertionError):
    """Only a completed original/native mismatch may credit a mutant."""


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


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


# ---------------------------------------------------------------------------
# Row-54 spill fixture: more than 80 records (see the creation contract at
# 30A6 and EntityRecordsBase). Shared with the >80-record cases of
# view_visibility, entity_update, entity_drawing, keyboard_input,
# object_animation, object_drawing_tick and status_glyph. The DS state is the
# one level start publishes for typed codes 156/158/212/214 (after an odd
# override was loaded): level006 section 6 with oddtable row 54 copied over
# header +00..+17 and the footer +7E0..+7FF by the 197D loader; 36B9 header
# copy (0047=63, 0067=63, 20A7=63+30, origin word +18 0270 -> 0000=0280,
# 0002=0050); 39D1/39E6 countdown 14 and reload 04 for rate 99; 0FC1 callback
# slots; 3773 spawn pairs from the type-1 entrance (0310,0008) -> (0328,0026);
# 0480 visibility rebuild at the initial origin. Records are then appended in
# order by the 30A6 store sequence (independent_memory below), without
# intervening update frames. Nothing here boots the game: every value is the
# documented producer's effect over the pinned assets.
SPILL_LEVEL_ASSET, SPILL_ODD_ASSET = 'assets/level006.dat', 'assets/oddtable.dat'
SPILL_SECTION, SPILL_ODD_ROW, ODD_ROW_SIZE = 6, 54, 0x38
SPILL_LIMIT, SPILL_RELOAD, SPILL_START_COUNTDOWN = 0x63, 0x04, 0x14
SPILL_ORIGIN = 0x0280
SPILL_SPAWN = (0x0328, 0x0026)
LEVEL_RECORD, LEVEL_RECORD_SIZE = 0x0FCB, 0x0800
VISIBILITY_MAP, VISIBILITY_BYTES, VISIBILITY_MARK = 0x0EA8, 0xD0, 0x29
KEY_STATE = 0x0F78
CALLBACK_SLOT_WORDS = (0x6170, 0x64D9, 0x65D8, 0x66D7, 0x6817,
                       0x6957, 0x6A97, 0x6BDB, 0x6CFC)


def spill_level_record():
    """level006 section 6 after the 197D odd-row-54 override (DF0 copy)."""
    from resources import decode_section, section_spans
    level = (ROOT / SPILL_LEVEL_ASSET).read_bytes()
    odd = (ROOT / SPILL_ODD_ASSET).read_bytes()
    start, end = section_spans(level)[SPILL_SECTION]
    record = bytearray(decode_section(level[start:end])[0][:LEVEL_RECORD_SIZE])
    row = odd[ODD_ROW_SIZE * SPILL_ODD_ROW:ODD_ROW_SIZE * (SPILL_ODD_ROW + 1)]
    record[0:0x18] = row[0:0x18]
    record[0x7E0:0x800] = row[0x18:0x38]
    words = [int.from_bytes(record[i:i + 2], 'big') for i in range(0, 0x18, 2)]
    oracle_require(words == [SPILL_LIMIT] * 12 and
                   int.from_bytes(record[0x18:0x1A], 'big') == 0x0270 and
                   record[0x20:0x28] == bytes.fromhex('03100008 0001800f'),
                   'row-54 level image no longer matches the characterized header/entrance')
    return bytes(record)


def spill_visibility(memory, ds, origin):
    """Map effect of the 410F rebuild with DF clear and ES=DS (proved by
    view_visibility): 68h zero words at 0EA8, then 29h bytes 01 at
    0EA6+origin/8. The marker bytes it writes elsewhere are not modelled."""
    for index in range(VISIBILITY_BYTES):
        put8(memory, ds, VISIBILITY_MAP + index, 0)
    start = (((origin & 0xFFFF) >> 3) - 2 + VISIBILITY_MAP) & 0xFFFF
    for index in range(VISIBILITY_MARK):
        put8(memory, ds, start + index, 1)


def create_record(memory, ds, bound):
    """The 30A6 effect after both gates and a due countdown (no providers)."""
    start = (RECORD_BASE + (bound & 0xFF) * RECORD_SIZE) & 0xFFFF
    coordinate = (COORDINATE_BASE + 4 * (bound & 3)) & 0xFFFF
    for index in range(RECORD_SIZE):
        put8(memory, ds, start + index, 0)
    put16(memory, ds, start, get16(memory, ds, coordinate))
    put16(memory, ds, start + 2, get16(memory, ds, coordinate + 2))
    put8(memory, ds, start + 0x27, 1)
    put8(memory, ds, start + 0x25, 0)
    put8(memory, ds, start + 0x24, get8(memory, ds, start + 0x24) & 1)
    put16(memory, ds, start + 0x08, get16(memory, ds, start + 0x08) | 4)
    put16(memory, ds, start + 0x0A, 0)
    put16(memory, ds, start + 0x0C, 0x0A42)
    put16(memory, ds, start + 0x10, 0x005A)
    put16(memory, ds, start + 0x12, 0x003C)
    put8(memory, ds, start + 0x28, 0)
    put8(memory, ds, start + 0x23, 3)
    put16(memory, ds, start + 0x04, 0xFFF8)
    put16(memory, ds, start + 0x06, 0xFFF6)
    put8(memory, ds, start + 0x29, 4)
    put16(memory, ds, start + 0x14, get16(memory, ds, 0x002E))
    put8(memory, ds, start + 0x2A, 0)
    put8(memory, ds, start + 0x24, get8(memory, ds, start + 0x24) & 1)
    return start


def spill_state(memory, ds, *, count=SPILL_LIMIT, origin=SPILL_ORIGIN):
    """Install the row-54 level-start DS and append records 00..count-1."""
    record = spill_level_record()
    for index, value in enumerate(record):
        put8(memory, ds, LEVEL_RECORD + index, value)
    put16(memory, ds, 0x0000, origin)
    put16(memory, ds, 0x0002, (origin >> 3) & 0xFFFF)
    for index, value in enumerate(CALLBACK_SLOT_WORDS):
        put16(memory, ds, 0x002E + 2 * index, value)
    put8(memory, ds, 0x002B, 0)
    put8(memory, ds, 0x0055, 0xFF)
    put8(memory, ds, 0x0043, 0)
    put8(memory, ds, 0x0047, SPILL_LIMIT)
    put8(memory, ds, 0x0064, SPILL_LIMIT)
    put8(memory, ds, 0x0067, SPILL_LIMIT)
    put8(memory, ds, 0x0048, SPILL_START_COUNTDOWN)
    put8(memory, ds, 0x0049, SPILL_RELOAD)
    put8(memory, ds, 0x20A7, (SPILL_LIMIT + 0x30) & 0xFF)
    for pair in range(4):
        put16(memory, ds, COORDINATE_BASE + 4 * pair, SPILL_SPAWN[0])
        put16(memory, ds, COORDINATE_BASE + 4 * pair + 2, SPILL_SPAWN[1])
    spill_visibility(memory, ds, origin)
    for scan in range(0x53):
        put8(memory, ds, KEY_STATE + scan, 0)
    for bound in range(count):
        create_record(memory, ds, bound)
    put8(memory, ds, 0x0043, count)
    if count:
        put8(memory, ds, 0x0048, SPILL_RELOAD)
    return memory


def cases():
    """All raw bounds plus focused gates, aliases, providers and RET seams."""
    rows = [
        dict(name=f'raw-bound-{bound:02X}', bound=bound,
             limit=(bound + 1) & 0xFF)
        for bound in range(256)
    ]
    rows.extend((
        dict(name='update-gate-equals-FF-returns', bound=7,
             update_gate=0xFF),
        dict(name='creation-gate-not-FF-returns', bound=7,
             creation_gate=0x00),
        dict(name='countdown-zero-wraps-without-reload', bound=7,
             countdown=0, reload=0x63),
        dict(name='countdown-decrements-to-nonzero', bound=7,
             countdown=2, reload=0x63),
        dict(name='equal-limit-returns-without-clamping', bound=0x32,
             limit=0x32),
        dict(name='bound-greater-than-limit-still-creates', bound=0x52,
             limit=0x03),
        dict(name='df-set-clear-forward', bound=4, limit=5, df=True),
        dict(name='bound50-clears-coordinate-source', bound=0x50,
             limit=0x51),
        dict(name='reload-provider-runs-after-zero-decrement', bound=9,
             limit=10, reload=0x12, reload_after_countdown=0x5C),
        dict(name='limit-is-read-after-reload', bound=0x24, limit=0x25,
             reload=0x31, limit_after_reload_read=0x24),
        dict(name='bound-selection-is-saved-before-live-change', bound=5,
             limit=6, bound_after_read=0xA0),
        dict(name='callback-changes-live-bound-before-increment', bound=5,
             limit=6, callback_bound_update=0xA0),
        dict(name='bound-read-and-callback-live-alias', bound=5, limit=6,
             bound_after_read=0xA0, callback_bound_update=0x10),
        dict(name='final-bound-inc-rmw-entry-flags', bound=0x7F,
             limit=0x80, flags=0x0ED7),
        dict(name='record-store-overwrites-actual-ret', bound=0,
             limit=1, ds=DATA_SEGMENT, ss=DATA_SEGMENT,
             callback=0x3456, ret_alias=True),
        dict(name='physical-data-and-ret-word-wrap', bound=2, limit=3,
             ds=0xFFFF, ss=0xFFFF, sp=0x000F),
        dict(name='nondefault-entry-flags-and-registers', bound=0x19,
             limit=0x1A, flags=0x0A55, ax=0xDEAD, bx=0xBEEF,
             cx=0x9876, dx=0x1357, si=0x2468, di=0x369A, bp=0xABCD),
    ))
    oracle_require(len(rows) == 273 and
                   len({case['name'] for case in rows}) == len(rows),
                   f'entity-create fixture inventory changed: {len(rows)}')
    for index, case in enumerate(rows):
        case.setdefault('seed', 0x30A600 + index * 97)
        case.setdefault('bound', 3)
        case.setdefault('limit', (case['bound'] + 1) & 0xFF)
        case.setdefault('update_gate', 0)
        case.setdefault('creation_gate', 0xFF)
        case.setdefault('countdown', 1)
        case.setdefault('reload', 0x37)
        case.setdefault('callback', 0x2468)
        case.setdefault('flags', 0x0ED7)
        case.setdefault('df', False)
    return rows


def setup(case):
    template = dict(case, load=MAIN_SEG, poison=False)
    memory, regs, _device, _pc, _sound, _ = interactions.setup(template)
    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    ss = case.get('ss', 0x5000) & 0xFFFF
    sp = case.get('sp', 0xD000) & 0xFFFF
    bound = case['bound'] & 0xFF
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if case.get('df', False) else (flags & ~0x0400)
    regs.update(ax=case.get('ax', 0x1357) & 0xFFFF,
                bx=case.get('bx', 0x2468) & 0xFFFF,
                cx=case.get('cx', 0xACE1) & 0xFFFF,
                dx=case.get('dx', 0x0055) & 0xFFFF,
                si=case.get('si', 0x4000) & 0xFFFF,
                di=case.get('di', 0x3131) & 0xFFFF,
                bp=case.get('bp', 0x7B2D) & 0xFFFF,
                cs=MAIN_SEG, ip=ENTRY, ds=ds, es=case.get('es', 0x6200),
                ss=ss, sp=sp, flags=flags)

    put8(memory, ds, 0x002B, case['update_gate'])
    put8(memory, ds, 0x0055, case['creation_gate'])
    put8(memory, ds, 0x0048, case['countdown'])
    put8(memory, ds, 0x0049, case['reload'])
    put8(memory, ds, 0x0047, case['limit'])
    put8(memory, ds, 0x0043, bound)
    coordinate_words = case.get('coordinates',
                                (0x1234, 0x5678, 0x2345, 0x6789,
                                 0x3456, 0x789A, 0x4567, 0x89AB))
    for index, value in enumerate(coordinate_words):
        put16(memory, ds, COORDINATE_BASE + 2 * index, value)
    put16(memory, ds, 0x002E, case['callback'])

    record_start = (RECORD_BASE + bound * RECORD_SIZE) & 0xFFFF
    # Nonzero sentinels make the 45th clear byte and each stale field visible.
    for index in range(RECORD_SIZE):
        put8(memory, ds, record_start + index,
             (0x81 + index * 13 + case['seed']) & 0xFF)
    if case.get('ret_alias'):
        sp = (record_start + 0x14) & 0xFFFF
        regs['ss'], regs['sp'] = ds, sp
        ss = ds
    put16(memory, ss, sp, case.get('return_word', 0x7A5C))
    return memory, regs, None


def original(case, memory, regs, *, core):
    return interactions.original(
        case, bytearray(memory), dict(regs), None, core,
        entry_flag_mask=ALL_FLAGS, main_instructions=OWN_INS,
        access_factory=CreateAccess, instruction_limit=MAX_INSTRUCTIONS)


class CreateAccess(interactions.Access):
    """Memory event log and finite providers at the original instruction seam."""
    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.native = bool(case.get('_native', False))
        self.pending = []
        self.pending_labels = []
        self.used = set()

    def _replace_byte(self, segment, offset, value, label):
        if self.native:
            self.store(physical(segment, offset), value)
        else:
            self.pending.append((segment, offset, value))
            self.pending_labels.append(label)
        self.used.add(label)

    def _provider(self, kind, address, value=None):
        case, ds = self.case, self.regs['ds']
        address &= MASK
        if (kind == 'write' and address == physical(ds, 0x0048) and
                value == 0 and 'reload-after-dec' not in self.used and
                'reload_after_countdown' in case):
            self._replace_byte(ds, 0x0049, case['reload_after_countdown'],
                               'reload-after-dec')
        if (kind == 'read' and address == physical(ds, 0x0049) and
                'limit-after-reload' not in self.used and
                'limit_after_reload_read' in case):
            self._replace_byte(ds, 0x0047, case['limit_after_reload_read'],
                               'limit-after-reload')
        if (kind == 'read' and address == physical(ds, 0x0043) and
                'bound-after-read' not in self.used and
                'bound_after_read' in case):
            self._replace_byte(ds, 0x0043, case['bound_after_read'],
                               'bound-after-read')
        if (kind == 'read' and address == physical(ds, 0x002E) and
                'callback-bound' not in self.used and
                'callback_bound_update' in case):
            self._replace_byte(ds, 0x0043, case['callback_bound_update'],
                               'callback-bound')

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-create memory event budget exhausted')
        address &= MASK
        if kind == 'read':
            value = self.memory[address]
            self.store(address, value)
        else:
            value &= 0xFF
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF,
                            flags & 0xFFFF, mask))
        self._provider(kind, address, value)
        return value & 0xFF

    def instruction_complete(self):
        for segment, offset, value in self.pending:
            self.store(physical(segment, offset), value)
        self.pending.clear()


def independent_memory(case, initial):
    """Small address/record model independent of translated C and Unicorn."""
    expected = bytearray(initial)
    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    bound_initial = case['bound'] & 0xFF
    info = dict(created=False, record_start=None, selected_bound=bound_initial,
                coordinate_offset=None, callback=None)
    if get8(expected, ds, 0x002B) == 0xFF:
        return expected, info
    if get8(expected, ds, 0x0055) != 0xFF:
        return expected, info

    countdown = (get8(expected, ds, 0x0048) - 1) & 0xFF
    put8(expected, ds, 0x0048, countdown)
    if countdown == 0 and 'reload_after_countdown' in case:
        put8(expected, ds, 0x0049, case['reload_after_countdown'])
    if countdown != 0:
        return expected, info

    reload_value = get8(expected, ds, 0x0049)
    put8(expected, ds, 0x0048, reload_value)
    if 'limit_after_reload_read' in case:
        put8(expected, ds, 0x0047, case['limit_after_reload_read'])
    limit = get8(expected, ds, 0x0047)
    bound = get8(expected, ds, 0x0043)
    if 'bound_after_read' in case:
        put8(expected, ds, 0x0043, case['bound_after_read'])
    if limit == bound:
        return expected, info

    start = (RECORD_BASE + bound * RECORD_SIZE) & 0xFFFF
    coordinate = (COORDINATE_BASE + 4 * (bound & 3)) & 0xFFFF
    info.update(created=True, record_start=start, selected_bound=bound,
                coordinate_offset=coordinate)
    for index in range(RECORD_SIZE):
        put8(expected, ds, start + index, 0)
    coordinate_x = get16(expected, ds, coordinate)
    coordinate_y = get16(expected, ds, coordinate + 2)
    put16(expected, ds, start, coordinate_x)
    put16(expected, ds, start + 2, coordinate_y)
    put8(expected, ds, start + 0x27, 1)
    put8(expected, ds, start + 0x25, 0)
    put8(expected, ds, start + 0x24, get8(expected, ds, start + 0x24) & 1)
    put16(expected, ds, start + 0x08, get16(expected, ds, start + 0x08) | 4)
    put16(expected, ds, start + 0x0A, 0)
    put16(expected, ds, start + 0x0C, 0x0A42)
    put16(expected, ds, start + 0x10, 0x005A)
    put16(expected, ds, start + 0x12, 0x003C)
    put8(expected, ds, start + 0x28, 0)
    put8(expected, ds, start + 0x23, 3)
    put16(expected, ds, start + 0x04, 0xFFF8)
    put16(expected, ds, start + 0x06, 0xFFF6)
    put8(expected, ds, start + 0x29, 4)
    callback = get16(expected, ds, 0x002E)
    info['callback'] = callback
    put16(expected, ds, start + 0x14, callback)
    put8(expected, ds, start + 0x2A, 0)
    put8(expected, ds, start + 0x24, get8(expected, ds, start + 0x24) & 1)
    if 'callback_bound_update' in case:
        put8(expected, ds, 0x0043, case['callback_bound_update'])
    put8(expected, ds, 0x0043, (get8(expected, ds, 0x0043) + 1) & 0xFF)
    return expected, info


def assert_independent(case, initial, observed):
    name = case['name']
    expected_memory, info = independent_memory(case, initial)
    oracle_require(observed['memory'] == expected_memory,
                   name + ': original memory differs from independent record model')
    if not info['created']:
        return

    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    start = info['record_start']
    for displacement, value in ((0x27, 1), (0x25, 0), (0x24, 0),
                                (0x08, 4), (0x0A, 0), (0x0C, 0x0A42),
                                (0x10, 0x005A), (0x12, 0x003C),
                                (0x28, 0), (0x23, 3), (0x04, 0xFFF8),
                                (0x06, 0xFFF6), (0x29, 4), (0x14, info['callback']),
                                (0x2A, 0)):
        width = 2 if displacement in (0x08, 0x0A, 0x0C, 0x10, 0x12,
                                       0x04, 0x06, 0x14) else 1
        got = get16(observed['memory'], ds, start + displacement) if width == 2 \
            else get8(observed['memory'], ds, start + displacement)
        oracle_require(got == value,
                       f'{name}: field +{displacement:02X} is {got:04X}, expected {value:04X}')
    if case['name'] == 'bound50-clears-coordinate-source':
        oracle_require((get16(observed['memory'], ds, start),
                        get16(observed['memory'], ds, start + 2)) == (0, 0),
                       name + ': coordinate source was not read after the 45-byte clear')

    # Find the 45 uninterrupted zero writes produced by MOV [DI],0 / INC DI / LOOP.
    expected_clear = [physical(ds, start + index) for index in range(RECORD_SIZE)]
    events = observed['events']
    clear_start = None
    for index in range(len(events) - RECORD_SIZE + 1):
        run = events[index:index + RECORD_SIZE]
        if all(event[0] == 'write' and event[2] == 0 for event in run) and \
                [event[1] for event in run] == expected_clear:
            clear_start = index
            break
    oracle_require(clear_start is not None,
                   name + ': original did not perform 45 forward byte clears')

    # Verify the post-clear writes retain the assembly's ordered store sequence.
    write_events = [(index, event) for index, event in enumerate(events)
                    if event[0] == 'write']
    clear_write_pos = next(i for i, (event_index, _event) in enumerate(write_events)
                           if event_index == clear_start + RECORD_SIZE - 1)
    post = write_events[clear_write_pos + 1:]
    offsets = [0, 1, 2, 3, 0x27, 0x25, 0x24, 0x08, 0x09,
               0x0A, 0x0B, 0x0C, 0x0D, 0x10, 0x11, 0x12, 0x13,
               0x28, 0x23, 0x04, 0x05, 0x06, 0x07, 0x29,
               0x14, 0x15, 0x2A, 0x24]
    expected_offsets = [physical(ds, start + offset) for offset in offsets]
    actual_offsets = [event[1] for _idx, event in post]
    bound_address = physical(ds, 0x0043)
    oracle_require(actual_offsets == expected_offsets + [bound_address],
                   name + ': ordered post-clear record stores or final bound INC differ')

    callback_reads = [index for index, event in enumerate(events)
                      if event[0] == 'read' and event[1] == physical(ds, 0x002E)]
    clear_end = clear_start + RECORD_SIZE - 1
    callback_write = next((index for index, event in enumerate(events)
                           if index > clear_end and event[0] == 'write' and
                           event[1] == physical(ds, start + 0x14)), None)
    bound_write = next((index for index, event in reversed(list(enumerate(events)))
                        if event[0] == 'write' and event[1] == bound_address), None)
    oracle_require(callback_reads and callback_write is not None and
                   callback_reads[0] > clear_start + RECORD_SIZE - 1 and
                   callback_reads[0] < callback_write < bound_write,
                   name + ': callback read/bound INC order changed')


def create_expected_return(case, expected_memory):
    ss = case.get('ss', 0x5000) & 0xFFFF
    sp = case.get('sp', 0xD000) & 0xFFFF
    if case.get('ret_alias'):
        start = (RECORD_BASE + (case['bound'] & 0xFF) * RECORD_SIZE) & 0xFFFF
        sp = (start + 0x14) & 0xFFFF
        ss = case.get('ds', DATA_SEGMENT) & 0xFFFF
    return get16(expected_memory, ss, sp)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: event count {len(actual)}/{len(expected)}')
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
    def __init__(self, case, memory, regs):
        access_case = dict(case, _native=True)
        self.access = CreateAccess(access_case, memory, regs, None)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_EXIT,
                        f'unexpected entity-create OUT {port:04X}={value:04X}/{flags:04X}')

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-create-m{mutation}.dll',
                     mutation, 'entity_create')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_create_entity_record_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_create_entity_record_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, *, core):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        bus = NativeBus(case, memory, regs)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds',
                'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), ct.byref(bus.bus))
            state.ax, state.bx, state.cx, state.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            state.si, state.di, state.bp = (
                result.record_cursor, result.object_cursor,
                result.candidate_y)
            state.cs, state.ds, state.es = (
                result.code_segment, result.data_segment,
                result.extra_segment)
            state.ss, state.sp, state.flags, state.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus.bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs,
                    events=bus.access.events, used=bus.access.used,
                    status=status, continuation=final_regs['ip'])


def compare_case(native, case, *, core):
    initial, regs, _device = setup(case)
    return compare_prepared(native, case, initial, regs, core=core)


def compare_prepared(native, case, initial, regs, *, core):
    expected_memory, info = independent_memory(case, initial)
    oracle = original(case, initial, regs, core=core)
    assert_independent(case, initial, oracle)
    expected_status = 0
    expected_continuation = RETURN_IP if core else create_expected_return(case, expected_memory)
    oracle_require((oracle['status'], oracle['continuation']) ==
                   (expected_status, expected_continuation),
                   case['name'] + f': original boundary {oracle["status"]}/'
                   f'{oracle["continuation"]:04X}, expected {expected_status}/'
                   f'{expected_continuation:04X}')

    actual = native.run(case, initial, regs, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == oracle['status'],
            f'{label}: status {actual["status"]}/{oracle["status"]}')
    require(actual['continuation'] == oracle['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{oracle["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        require(actual['regs'][name] == oracle['regs'][name],
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{oracle["regs"][name]:04X}')
    flag_mask = oracle['flag_mask']
    require(((actual['regs']['flags'] ^ oracle['regs']['flags']) & flag_mask) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {flag_mask:04X}')
    require(actual['memory'] == oracle['memory'],
            label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    require(actual['used'] == oracle['used'],
            f'{label}: provider effects {actual["used"]}/{oracle["used"]}')

    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target)
                 for source, source_ip, target in oracle['edges']
                 if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                events=len(oracle['events']), steps=oracle['steps'])


SPILL_FIRST = 0x50
SPILL_CHAIN_CALLS = (SPILL_LIMIT - SPILL_FIRST) * SPILL_RELOAD + SPILL_RELOAD
# Spawn source per spill index (creation-only chain: record 50 is not updated
# between creations, so pair 0 is still its creation X/Y).
SPILL_SPAWNS = {0x50: (0x0000, 0x0000), 0x51: (0xFFF8, 0xFFF6),
                0x52: (0x0004, 0x0000), 0x53: (0x0A42, 0x0000),
                0x54: (0x0000, 0x0000)}


def spill_chain_start():
    template = dict(name='row54-chain', bound=SPILL_FIRST, limit=SPILL_LIMIT,
                    update_gate=0, creation_gate=0xFF, countdown=SPILL_RELOAD,
                    reload=SPILL_RELOAD, callback=0x6170, flags=0x0ED7,
                    df=False, seed=0x30A654)
    memory, regs, _ = setup(template)
    spill_state(memory, DATA_SEGMENT, count=SPILL_FIRST)
    return memory, regs


def spill_chain_case(call, bound, countdown):
    return dict(name=f'row54-call-{call:02d}-bound-{bound:02X}', bound=bound,
                limit=SPILL_LIMIT, update_gate=0, creation_gate=0xFF,
                countdown=countdown, reload=SPILL_RELOAD, callback=0x6170,
                flags=0x0ED7, df=False, seed=0x30A654 + call)


def assert_spill_step(case, before, after, info):
    """Characterized row-54 facts (creation contract at 30A6)."""
    ds, name = DATA_SEGMENT, case['name']
    if not info['created']:
        masked = bytearray(after)
        masked[physical(ds, 0x0048)] = before[physical(ds, 0x0048)]
        oracle_require(masked == before,
                       name + ': a non-creating row-54 call changed more than 0048')
        return
    bound = info['selected_bound']
    start = info['record_start']
    oracle_require(start == (RECORD_BASE + bound * RECORD_SIZE) & 0xFFFF,
                   name + ': spill record address is not 0088+2D*n')
    if bound in SPILL_SPAWNS:
        got = (get16(after, ds, start), get16(after, ds, start + 2))
        oracle_require(got == SPILL_SPAWNS[bound],
                       f'{name}: spawn {got[0]:04X},{got[1]:04X} differs from '
                       f'the characterized record-50 source')
    if bound == 0x56:
        oracle_require(bytes(after[physical(ds, LEVEL_RECORD):
                                   physical(ds, LEVEL_RECORD) + 8]) ==
                       bytes.fromhex('0000010004000000'),
                       name + ': record 56 did not overwrite LEVEL header +00..+07')
    if bound == 0x57:
        oracle_require(bytes(after[physical(ds, 0x0FEB):physical(ds, 0x0FF3)]) ==
                       bytes(8), name + ': record 57 did not zero object definition 0')
    if bound == SPILL_LIMIT - 1:
        oracle_require(start + RECORD_SIZE - 1 == 0x11EE and
                       after[physical(ds, 0x11EF)] == before[physical(ds, 0x11EF)],
                       name + ': last row-54 record does not end at 11EE')


def spill_chain(native=None):
    """Sequential original (and optional native) creation calls 50..62 and the
    equality stop at 63, each over the previous call's whole RAM."""
    memory, regs = spill_chain_start()
    rows, created = [], []
    for call in range(SPILL_CHAIN_CALLS):
        bound = get8(memory, DATA_SEGMENT, 0x0043)
        countdown = get8(memory, DATA_SEGMENT, 0x0048)
        case = spill_chain_case(call, bound, countdown)
        expected_memory, info = independent_memory(case, memory)
        assert_spill_step(case, memory, expected_memory, info)
        for core in (True, False):
            if native is not None:
                rows.append(compare_prepared(native, case, memory, regs, core=core))
                continue
            observed = original(case, memory, regs, core=core)
            assert_independent(case, memory, observed)
            expected_continuation = RETURN_IP if core else create_expected_return(
                case, expected_memory)
            oracle_require((observed['status'], observed['continuation']) ==
                           (0, expected_continuation),
                           case['name'] + ': original boundary changed')
            rows.append(dict(name=case['name'], core=core,
                             events=len(observed['events']), steps=observed['steps']))
        if info['created']:
            created.append(info['selected_bound'])
        memory = bytearray(expected_memory)
        gc.collect()
    oracle_require(created == list(range(SPILL_FIRST, SPILL_LIMIT)) and
                   get8(memory, DATA_SEGMENT, 0x0043) == SPILL_LIMIT,
                   f'row-54 chain created {[hex(b) for b in created]}')
    return rows


def input_hashes():
    paths = (
        SPILL_LEVEL_ASSET, SPILL_ODD_ASSET,
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/adlib-symbols.json', 'metadata/adlib-regions.json',
        'metadata/adlib-encodings.json', 'metadata/tandysnd-symbols.json',
        'metadata/tandysnd-regions.json', 'metadata/tandysnd-encodings.json',
        'metadata/pcspeaker-symbols.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'src/game_code.asm', 'c/entity_create.c', 'c/entity_create.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/entity_create.py', 'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/coverage.py', 'tools/difftest.py',
        'tools/resources.py', 'tools/unpack.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_campaign(before):
    oracle_require(before == input_hashes(),
                   'entity-create input hashes changed before original campaign')
    oracle_require(len(OWN_INS) == 54 and
                   sum(ins.size for ins in OWN_INS.values()) == 170 and
                   len(OWN_EDGES) == 13,
                   f'entity-create code accounting changed: {len(OWN_INS)} sites, '
                   f'{sum(ins.size for ins in OWN_INS.values())} bytes, '
                   f'{len(OWN_EDGES)} edges')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed main image hash changed')
    covered, edges, rows = set(), set(), []
    specs = cases()
    for case in specs:
        initial, regs, _device = setup(case)
        expected_memory, _info = independent_memory(case, initial)
        for core in (True, False):
            observed = original(case, initial, regs, core=core)
            assert_independent(case, initial, observed)
            expected_continuation = RETURN_IP if core else create_expected_return(
                case, expected_memory)
            oracle_require((observed['status'], observed['continuation']) ==
                           (0, expected_continuation),
                           case['name'] + f': original boundary {observed["status"]}/'
                           f'{observed["continuation"]:04X}, expected 0/'
                           f'{expected_continuation:04X}')
            sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
            case_edges = {(src, dst) for source, src, dst in observed['edges']
                          if source == 'main' and src in OWN_INS}
            covered.update(sites)
            edges.update(case_edges)
            rows.append(dict(name=case['name'], core=core,
                             sites=sorted(sites), edges=[list(e) for e in sorted(case_edges)],
                             events=len(observed['events']), steps=observed['steps']))
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'entity-create original misses sites {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'entity-create original edge union differs: '
                   f'missing={sorted(OWN_EDGES-edges)} extra={sorted(edges-OWN_EDGES)}')
    spill_rows = spill_chain()
    oracle_require(before == input_hashes(),
                   'entity-create input hashes changed during original campaign')
    print(f'PASS entity create original: {len(specs)} fixtures x core/adapter, '
          f'row-54 chain {len(spill_rows) // 2} calls, '
          f'{len(covered)} sites/{len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} events; bounded original only',
          flush=True)
    return rows, edges


def worker(directory, hash_path):
    import json
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'entity-create inputs changed before native worker')
    original_rows, _ = original_campaign(before)
    specs = cases()
    baseline = Native(directory)
    rows, sites, edges, event_count, step_count = [], set(), set(), 0, 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            event_count += row['events']
            step_count += row['steps']
        gc.collect()
    spill_rows = spill_chain(baseline)
    for row in spill_rows:
        event_count += row['events']
        step_count += row['steps']
    oracle_require(sites == set(OWN_INS),
                   f'entity-create native site union misses {sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == OWN_EDGES,
                   f'entity-create native edge union differs: '
                   f'missing={sorted(OWN_EDGES-edges)} extra={sorted(edges-OWN_EDGES)}')

    witnesses = {
        1: 'df-set-clear-forward',
        2: 'raw-bound-00',
        3: 'bound-greater-than-limit-still-creates',
        4: 'bound50-clears-coordinate-source',
        5: 'raw-bound-FF',
        6: 'reload-provider-runs-after-zero-decrement',
        7: 'bound-read-and-callback-live-alias',
        8: 'final-bound-inc-rmw-entry-flags',
    }
    by_name = {case['name']: case for case in specs}
    mutations = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[name], core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'entity-create mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(len(mutations) == len(witnesses),
                   'entity-create completed mutation count changed')
    oracle_require(before == input_hashes(),
                   'entity-create input hashes changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
        translated_code_bytes=170, instruction_sites=len(OWN_INS),
        own_branch_edges=len(OWN_EDGES), case_count=len(specs),
        core_adapter_comparisons=len(rows),
        row54_chain_calls=len(spill_rows) // 2,
        row54_chain_comparisons=len(spill_rows),
        mutation_count=len(mutations),
        mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        total_bus_events=event_count, original_code_hook_steps=step_count,
        original_only_case_count=len(original_rows), input_hashes=before,
        cases=[dict(name=row['name'], core=row['core'], sites=row['sites'],
                    edges=row['edges'], events=row['events'], steps=row['steps'])
               for row in rows],
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='CreateEntityRecordIfDue at 30A6..314F. All byte bounds 00..FF '
               'are created with a distinct limit; focused cases cover both gates, '
               'countdown wrap/reload, equality without upper clamping, the 50h '
               'coordinate-source alias, DF-independent 45-byte clear, byte MUL, '
               'live callback/bound changes and actual SS:SP RET. Compares full '
               '1 MiB ordinary RAM, all registers, defined FLAGS and ordered '
               'memory bus events at logical pre-RET core and actual-RET adapter '
               'boundaries. No array extent or VGA access is inferred. '
               'Row-54 chain: level006 section 6 with oddtable row 54 and records '
               '00..4F appended in order; 80 sequential calls (reload 04) create '
               '50..62 over spawn pairs, visibility, key bytes, LEVEL header, object '
               'and terrain definitions, then stop on equality at 63, each '
               'compared over the previous whole RAM.'))
    print(f'PASS entity create: {len(specs)} fixtures x core/adapter, '
          f'row-54 chain {len(spill_rows) // 2} calls x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {event_count} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        BUILD.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='entity-create-original-',
                                        parent=BUILD) as directory:
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        import json
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, edges = original_campaign(before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
            known_code_bytes=170, instruction_sites=len(OWN_INS),
            own_branch_edges=len(OWN_EDGES), case_count=len(cases()),
            executed_instruction_addresses=sorted(
                {address for row in rows for address in row['sites']}),
            branch_edges=[list(edge) for edge in sorted(edges)],
            input_hashes=before,
            domain='Bounded original-only CreateEntityRecordIfDue comparison; '
                   'full raw byte-bound domain and focused aliases/providers.'))
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[2] + '/input-hashes.json')
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_create.py [--original-only | --worker DIR]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-create-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
