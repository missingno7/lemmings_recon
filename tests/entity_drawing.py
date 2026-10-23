"""Bounded original/native checks for DrawEntityRecords (3634..368D)."""
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
import decimal_field
import entity_dirty
import entity_create as spill
import entity_interactions as interactions
import entity_minimap
import entity_points
import entity_sprite_dispatch as sprite
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
LOAD = 0x1010
ENTRY, END, UNKNOWN = 0x3634, 0x368E, 0x366F
EARLY_RET, DECIMAL_RET = 0x368D, 0x4BBD
RECORDS, SLOT_BOUND, PASS_COUNT = 0x0088, 0x0043, 0x0045
GUARD, CALLBACK_SLOT, STATUS_FIELD = 0x0050, 0x003C, 0x2095
CALLBACKS = (0x6170, 0x64D9, 0x65D8, 0x66D7, 0x6817,
             0x6957, 0x6A97, 0x6BDB, 0x6CFC)
READY, CHILD_STOP, CHANGED_CHILD_RETURN = range(3)
NO_CHILD_STATUS = 0xFFFF
MAX_INSTRUCTIONS, MAX_EVENTS = 120_000, 50_000
WORKER_SECONDS, PROCESS_MIB = 420, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-drawing-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-drawing-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def disassemble(address, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[address:end], address)}


# Keep the physical UNKNOWN byte out of Capstone's input so nothing downstream
# acquires an accidental interpretation for 366F.
OWN_INS = disassemble(ENTRY, UNKNOWN) | disassemble(0x3670, END)
OWN_SITES = set(OWN_INS)
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())


def compose_instructions():
    rows = {}
    for module in (entity_minimap, entity_dirty, entity_points, sprite):
        source = module.MAIN_INS if module is sprite else module.OWN_INS
        for address, ins in source.items():
            previous = rows.get(address)
            if previous is not None and (previous.bytes != ins.bytes or
                                         previous.size != ins.size):
                raise AssertionError(f'conflicting instruction maps at {address:04X}')
            rows[address] = ins
    for address, ins in decimal_field.INS.items():
        if 0x4B68 <= address <= DECIMAL_RET:
            previous = rows.get(address)
            if previous is not None and previous.bytes != ins.bytes:
                raise AssertionError(f'conflicting decimal instruction at {address:04X}')
            rows[address] = ins
    for address, ins in OWN_INS.items():
        if address in rows:
            raise AssertionError(f'drawing parent overlaps child map at {address:04X}')
        rows[address] = ins
    return rows


MAIN_INS = compose_instructions()


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not (ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


OWN_EDGES = branch_edges(OWN_INS)
OWN_CONDITIONALS = {address for address, ins in OWN_INS.items()
                    if (ins.group(capstone.CS_GRP_JUMP) or
                        ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')) and
                    ins.mnemonic.lower() not in ('jmp', 'ljmp')}
UNCONDITIONAL_EDGES = {(0x366D, 0x367D), (0x368A, 0x4B68)}

MAIN_CALL_RETURNS = {
    0x3651: ({entity_minimap.RET}, 101),
    0x3654: ({entity_dirty.RETURN_IP}, 102),
    0x3669: ({entity_points.RET}, 103),
    0x3675: ({sprite.RET}, 104),
    0x7152: ({0x6FE1}, 105),
    0x715B: (set(sprite.CHILD_RETURNS), 106),
}
CALL_ENTRY = {101: (0x6FE2, 0x3651),
              102: (0x5726, 0x3654),
              103: (0x6E83, 0x3669),
              104: (0x706F, 0x3675),
              105: (0x706F, 0x7152),
              106: (0x706F, 0x715B),
              107: (0x706F, 0x715B)}
KNOWN_CALLBACKS = set(CALLBACKS)

CORE_NAMES = ('value', 'map_cursor', 'count', 'auxiliary_value',
              'record_cursor', 'object_cursor', 'candidate_y',
              'code_segment', 'data_segment', 'extra_segment',
              'stack_segment', 'stack_offset', 'flags')
REG_FIELDS = dict(value='ax', map_cursor='bx', count='cx',
                  auxiliary_value='dx', record_cursor='si', object_cursor='di',
                  candidate_y='bp', code_segment='cs', data_segment='ds',
                  extra_segment='es', stack_segment='ss', stack_offset='sp',
                  flags='flags')
MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                CORE_NAMES + ('continuation', 'status', 'child_entry', 'child_status')]


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """A bounded constructed original execution did not meet its contract."""


class Mismatch(AssertionError):
    """A completed native result differs from the completed original."""


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
    return ((((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK)


def put8(memory, segment, offset, value, device=None):
    address = physical(segment, offset)
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[device.gc[4] & 3][address - VGA_BASE] = value


def put16(memory, segment, offset, value, device=None):
    put8(memory, segment, offset, value, device)
    put8_phys(memory, (physical(segment, offset) + 1) & MASK,
              value >> 8, device)


def put8_phys(memory, address, value, device=None):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[device.gc[4] & 3][address - VGA_BASE] = value


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


class DrawingAccess(interactions.Access):
    """Bounded bus plus live child-frame, count, and callback observers."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, stops, native=False):
        super().__init__(case, memory, regs, device)
        self.stops = stops
        self.native = native
        self.callback_bytes = {}
        self.callback_observations = 0
        self.write_bytes = {}
        self.callback_call_bytes = {}
        self.callback_entered = False
        self.pending = []
        self.entry_sp = case['sp'] & 0xFFFF
        self.entry_ss = case['ss'] & 0xFFFF
        self.expected_calls = {
            101: (self.entry_sp - 6, 0x3654),
            102: (self.entry_sp - 6, 0x3657),
            103: (self.entry_sp - 8, 0x366C),
            104: (self.entry_sp - 6, 0x3678),
        }

    def _provider(self, kind, address):
        super()._provider(kind, address)
        case = self.case
        effect = case.get('provider')
        address &= MASK
        if (effect == 'pass-count-wrap' and kind == 'read' and
                address == physical(case['ds'], PASS_COUNT) and
                'pass-count-wrap' not in self.used):
            self.store(address, 0xFF)
            self.used.add('pass-count-wrap')

    def _queue_word(self, segment, offset, value, label):
        self.pending.append((segment & 0xFFFF, offset & 0xFFFF,
                             value & 0xFFFF, label))

    def _flush_pending(self):
        queued, self.pending = self.pending, []
        for segment, offset, value, label in queued:
            self.modify_word(segment, offset, value)
            self.used.add(label)

    def instruction_complete(self):
        self._flush_pending()

    def _observe_callback_word(self, address, value):
        case = self.case
        low_address = physical(self.entry_ss, self.entry_sp - 12)
        high_address = (low_address + 1) & MASK
        if address == low_address:
            self.callback_bytes.clear()
            self.callback_bytes['low'] = value & 0xFF
        elif address == high_address:
            self.callback_bytes['high'] = value & 0xFF
        else:
            return
        if 'low' not in self.callback_bytes or 'high' not in self.callback_bytes:
            return
        self.callback_observations += 1
        target = self.callback_bytes['low'] | (self.callback_bytes['high'] << 8)
        if target in KNOWN_CALLBACKS:
            self.stops.pop(0x715B, None)
        else:
            self.stops[0x715B] = 107
        self.used.add('callback-target-observer')

    def _observe_stack_write(self, address, value):
        callback_low = physical(self.entry_ss, self.entry_sp - 10)
        callback_high = (callback_low + 1) & MASK
        if address == callback_low:
            self.callback_call_bytes.clear()
            self.callback_call_bytes['low'] = value & 0xFF
        elif address == callback_high:
            self.callback_call_bytes['high'] = value & 0xFF
            if (self.callback_call_bytes.get('low') == 0x5D and
                    self.callback_call_bytes['high'] == 0x71):
                self.callback_entered = True
        if self.case.get('provider') not in {
                'changed-minimap-return', 'changed-dirty-return',
                'changed-points-return', 'changed-sprite-return',
                'changed-strip-return', 'saved-di-rewrite', 'saved-cx-shorten',
                'changed-callback-return'}:
            return
        # The CALL push is two bus writes. Identify it by its real return word
        # and frame offset, then apply providers only after both bytes exist.
        targets = list(self.expected_calls.items())
        provider = self.case.get('provider')
        if provider == 'changed-strip-return':
            targets.append((105, (self.entry_sp - 22, 0x7155)))
        if provider == 'changed-callback-return':
            targets.append((106, (self.entry_sp - 10, 0x715D)))
        if provider in self.used:
            return
        for code, (offset, return_word) in targets:
            lo = physical(self.entry_ss, offset)
            hi = (lo + 1) & MASK
            if address not in (lo, hi):
                continue
            slot = self.write_bytes.setdefault(code, {})
            if address == lo:
                slot.clear()
                slot['low'] = value & 0xFF
                continue
            slot['high'] = value & 0xFF
            if slot.get('low') != (return_word & 0xFF) or \
                    slot['high'] != ((return_word >> 8) & 0xFF):
                continue
            expected_provider = {
                101: 'changed-minimap-return', 102: 'changed-dirty-return',
                103: 'changed-points-return', 104: 'changed-sprite-return',
                105: 'changed-strip-return', 106: 'changed-callback-return'}
            if expected_provider.get(code) == provider:
                self._queue_word(self.entry_ss, offset,
                                 self.case.get('changed_return', 0x7000), provider)
            elif code == 101 and provider in ('saved-di-rewrite', 'saved-cx-shorten'):
                if provider == 'saved-di-rewrite':
                    self._queue_word(self.entry_ss, self.entry_sp - 4,
                                     self.case.get('saved_di', 0xFFFE), provider)
                else:
                    self._queue_word(self.entry_ss, self.entry_sp - 2,
                                     self.case.get('saved_cx', 1), provider)
            else:
                continue
            # Native callbacks run synchronously after the second byte. The
            # original Unicorn hook defers the patch until its CALL completes.
            if self.native:
                self._flush_pending()
            return

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-drawing bus event cap exhausted')
        address &= MASK
        result = super().access(kind, address, flags, mask, value)
        if kind == 'read':
            self._observe_callback_word(address, result)
        elif kind == 'write':
            self._observe_stack_write(address, result)
        return result

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-drawing event budget exhausted')
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        nested_return = get16(self.memory, self.entry_ss,
                              self.entry_sp - 10)
        saved_ds = get16(self.memory, self.entry_ss,
                         self.entry_sp - 12)
        if (self.case.get('provider') == 'returned-ds-count-200' and
                'returned-ds' not in self.used and self.callback_entered and
                nested_return == 0x715D and
                saved_ds == (self.regs['ds'] & 0xFFFF)):
            new_ds = self.case.get('returned_ds', 0x2000)
            self.modify_word(self.entry_ss, self.entry_sp - 12, new_ds)
            self.store(physical(new_ds, PASS_COUNT), 200)
            self.used.add('returned-ds')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-drawing-m{mutation}.dll',
                     mutation, 'entity_drawing')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_entity_records_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_entity_records_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        stops = {}
        access = DrawingAccess(dict(case, _native=True), memory, regs,
                               device, stops=stops, native=True)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'cap exhausted' in str(error)
                            else CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'cap exhausted' in str(error)
                            else CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_exit(CALLBACK_EXIT, error)

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = RasterBus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        if core:
            call = Call(*(regs[REG_FIELDS[name]] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            state = {name: getattr(result, name) for name in CORE_NAMES}
            state.update(continuation=result.continuation, status=result.status,
                         child_entry=result.child_entry,
                         child_status=result.child_status)
            for role, machine in REG_FIELDS.items():
                regs[machine] = state[role]
            regs['ip'] = result.continuation
            return dict(memory=bytes(memory), regs=regs, device=device,
                        events=access.events, used=access.used,
                        status=result.status, continuation=result.continuation,
                        child_entry=result.child_entry,
                        child_status=result.child_status,
                        observer_count=access.callback_observations)
        machine_regs = interactions.Regs(**regs)
        status = self.adapter(ram, ct.byref(machine_regs), ct.byref(bus))
        final_regs = {name: getattr(machine_regs, name)
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs, device=device,
                    events=access.events, used=access.used, status=status,
                    continuation=final_regs['ip'], child_entry=None,
                    child_status=None,
                    observer_count=access.callback_observations)


def make_cases():
    """Finite loop, branch, child seam, byte-wrap, and shared-tail fixtures."""
    specs = [
        dict(name='zero-bound-preserves-stale-count', bound=0,
             initial_count=0xA500, initial_pass_count=0xA5,
             expected_pass_count=0xA5, expected_field_unchanged=True),
        dict(name='one-record-skipped', bound=1, records=[dict(skip=0xFF)],
             expected_pass_count=0, expected_ascii=(0x30, 0x20, 0x20)),
        dict(name='three-records-all-skipped', bound=3,
             records=[dict(skip=0xFF)] * 3, expected_pass_count=0,
             expected_ascii=(0x30, 0x20, 0x20)),
        dict(name='255-records-all-skipped-finite', bound=255,
             records=[dict(skip=0xFF)] * 255, expected_pass_count=0,
             expected_ascii=(0x30, 0x20, 0x20)),
        dict(name='255-active-pass-count', bound=255, all_active=True,
             map_visible=False, expected_pass_count=255,
             expected_ascii=(0x32, 0x35, 0x35)),
        dict(name='skip-gate-open-minimap-early-return', bound=1,
             records=[dict(y=0x00B0, callback=0x7000, frame=0)]),
        dict(name='signed-frame-selector-one-enters-points', bound=1,
             records=[dict(callback=0x6F00, callback_slot=0x6F00,
                           frame=1, point_selector=1)]),
        dict(name='signed-frame-selector-7f-enters-points', bound=1,
             records=[dict(callback=0x6F00, callback_slot=0x6F00,
                           frame=0x7F, point_selector=0x7F)]),
        dict(name='signed-frame-selector-zero-enters-sprite', bound=1,
             records=[dict(callback=0x6170, callback_slot=0x6170, frame=0)]),
        dict(name='signed-frame-selector-80-enters-sprite', bound=1,
             records=[dict(callback=0x6170, callback_slot=0x6170, frame=0x80)]),
        dict(name='signed-frame-selector-ff-enters-sprite', bound=1,
             records=[dict(callback=0x6170, callback_slot=0x6170, frame=0xFF)]),
    ]
    for index, target in enumerate(CALLBACKS):
        specs.append(dict(name=f'callback-{index + 1:02d}-{target:04x}', bound=1,
                          records=[dict(callback=target, frame=0)],
                          map_visible=True))
    specs += [
        dict(name='known-then-unknown-callback-live-observer', bound=2,
             records=[dict(callback=0x6170, frame=0),
                      dict(callback=0x7000, frame=0)], map_visible=True),
        dict(name='unknown-callback-stops-with-guard-ff', bound=1,
             records=[dict(callback=0x7000, frame=0)], map_visible=True),
        dict(name='changed-minimap-child-return', bound=1,
             records=[dict(y=0x00B0, callback=0x7000)],
             provider='changed-minimap-return'),
        dict(name='changed-dirty-child-return', bound=1,
             records=[dict(y=0x00B0, callback=0x7000)],
             provider='changed-dirty-return'),
        dict(name='changed-points-child-return', bound=1,
             records=[dict(y=0x00B0, callback=0x6F00, callback_slot=0x6F00,
                           frame=1, point_selector=1)],
             provider='changed-points-return'),
        dict(name='changed-sprite-outer-return', bound=1,
             records=[dict(y=0x00B0, callback=0x6170)],
             provider='changed-sprite-return'),
        dict(name='changed-nested-strip-return', bound=1,
             records=[dict(callback=0x6170, frame=0, strip=1)],
             provider='changed-strip-return', map_visible=True),
        dict(name='changed-nested-callback-return', bound=1,
             records=[dict(callback=0x6170, frame=0)],
             provider='changed-callback-return', map_visible=True),
        dict(name='saved-cx-shortens-parent-loop-live', bound=3,
             records=[dict(y=0x00B0, callback=0x7000)] * 3,
             provider='saved-cx-shorten', saved_cx=1,
             expected_pass_count=1, expected_ascii=(0x31, 0x20, 0x20)),
        dict(name='saved-di-rewrite-selects-next-record', bound=2,
             records=[dict(y=0x00B0, callback=0x7000),
                      dict(y=0x00B0, callback=0x7000)],
             provider='saved-di-rewrite', saved_di=0x0100,
             record_offsets=[0x0088, 0x012D]),
        dict(name='pass-count-live-byte-wrap', bound=1,
             records=[dict(y=0x00B0, callback=0x7000)],
             provider='pass-count-wrap', expected_pass_count=0,
             expected_ascii=(0x30, 0x20, 0x20)),
        dict(name='returned-ds-clears-guard-and-formats-200', bound=1,
             records=[dict(callback=0x6170, frame=0)],
             provider='returned-ds-count-200', map_visible=True,
             expected_pass_count=200, expected_ascii=(0x32, 0x30, 0x30)),
        dict(name='dirty-visible-two-row-bound', bound=1,
             records=[dict(callback=0x6170, frame=0, dirty_visible=True,
                           y=0x20, dirty_height=0xFFF8)]),
        dict(name='df-set-preserves-live-direction-contract', bound=1,
             flags=0x0ED7, df=True,
             records=[dict(y=0x00B0, callback=0x7000)]),
        dict(name='ds-ss-record-return-alias', bound=1, ds=0x5000, ss=0x5000,
             sp=0xD000, records=[dict(skip=0xFF)]),
        dict(name='decimal-store-overwrites-outer-return', bound=1,
             ds=0x5000, ss=0x5000, sp=0x2095,
             records=[dict(skip=0xFF)]),
        dict(name='outer-return-word-physical-fffff-wrap', bound=1,
             ss=0xFFFF, sp=0x000F, records=[dict(skip=0xFF)]),
    ]

    cases = []
    for index, spec in enumerate(specs):
        row = dict(name='', seed=0x363400 + index * 97,
                   bound=1, initial_count=0xABCD,
                   initial_pass_count=0x5A, load=LOAD,
                   ds=0x09A9, ss=0x5000, sp=0x9000,
                   es=0x6200, si=0xBEEF, flags=0x0AD7,
                   outer_return=(0xD100 + index) & 0xFFFF,
                   map_visible=False, all_active=False,
                   provider=None, records=None, record_offsets=None,
                   saved_di=0x0100, saved_cx=1, returned_ds=0x2000)
        row.update(spec)
        if row['records'] is None:
            if row['all_active']:
                row['records'] = [dict(callback=0x6170, callback_slot=0xDEAD,
                                       frame=0, y=0x00B0)] * row['bound']
            else:
                row['records'] = [dict(y=0x00B0, callback=0x7000)
                                  for _ in range(row['bound'])]
        if row['record_offsets'] is None:
            row['record_offsets'] = [0x0088 + index * 0x2D
                                     for index in range(len(row['records']))]
        cases.append(row)
    oracle_require(30 <= len(cases) <= 45,
                   f'entity-drawing fixture count outside scope: {len(cases)}')
    return cases


# Row-54 spill frame slice, stage 3: records 00..62 (entity_create.spill_state)
# after the 410F rebuild at a characterized origin (view_visibility) and one
# original 1F19 pass (entity_update.spill_after_update). The record/global
# bytes 0000..0003, 002E..0044 and 0088..11EE of that original RAM replace this
# suite's constructed record table; sprite banks, dirty-map base 1F76=3000,
# point tables and VGA stay the suite's finite fixtures. Expected: the first
# drawn record with a non-callback +14 stops at 715B (C: unknown callback)
# with AX=+14 and the record pointer in the 706F PUSH DI word at entry SP-8
# (DI itself already holds the computed VGA offset); otherwise the pass
# completes.
SPILL_DRAW_ORIGINS = {
    0x0160: (0x0E98, 0x0000),   # record 50 alive, column 2B marked
    0x01B8: (0x0EF2, 0x0000),   # record 52, rebuilt +14
    0x01C0: (0x0EF2, 0x0001),
    0x01C8: (0x0EF2, 0x0101),
    0x0210: (0x0EF2, 0x0101),
    0x0218: None,               # record 52 column 40 unmarked
    0x0280: None,               # 51/52 countdowns repair, nothing escapes
    0x0098: (0x0E98, 0x0000),   # record 50 +20=00
    0x0090: None,               # record 50 +20=01 expired and repaired
}
SPILL_COPY_RANGES = ((0x0000, 0x0004), (0x002E, 0x0045), (0x0088, 0x11EF))
# Keyboard channel: after the 0090 rebuild and update, an IRQ make stores 94
# at 0F78+scan (proved over these bytes by keyboard_input's row-54 IRQ cases):
# scan 15/16 rewrite record 55's +14 to 6194/9470 and record 55 (column 2A,
# marked at 0090) is the first record drawn with a non-callback word.
SPILL_KEY_CASES = {0x15: (0x0F79, 0x6194), 0x16: (0x0F79, 0x9470)}


def spill_cases():
    rows = []
    for index, (origin, escape) in enumerate(SPILL_DRAW_ORIGINS.items()):
        rows.append(dict(
            name=f'row54-spill-draw-origin-{origin:04X}', seed=0x363454 + index,
            bound=1, initial_count=0xABCD, initial_pass_count=0x5A, load=LOAD,
            ds=(LOAD + 0x09A9) & 0xFFFF, ss=(LOAD + 0x143E) & 0xFFFF, sp=0x4AF2,
            es=0x6200, si=0xBEEF, flags=0x0246, outer_return=0x01BF,
            map_visible=False, all_active=False, provider=None,
            records=[dict(skip=0xFF)], record_offsets=[RECORDS],
            saved_di=0x0100, saved_cx=1, returned_ds=0x2000,
            spill_origin=origin, spill_escape=escape))
    for index, (scan, escape) in enumerate(SPILL_KEY_CASES.items()):
        rows.append(dict(rows[-1], name=f'row54-spill-draw-origin-0090-key-{scan:02X}-make',
                         seed=0x3634A0 + index, spill_key=scan, spill_escape=escape))
    return rows


def install_spill(case, memory, device):
    import entity_update
    post, post_ds = entity_update.spill_after_update(case['spill_origin'])
    oracle_require(post_ds == case['ds'], case['name'] + ': spill DS differs')
    for start, end in SPILL_COPY_RANGES:
        for offset in range(start, end):
            put8(memory, case['ds'], offset, get8(post, post_ds, offset), device)
    if case.get('spill_key') is not None:
        put8(memory, case['ds'], spill.KEY_STATE + case['spill_key'], 0x94, device)


def assert_spill_draw(case, expected, *, core):
    name, escape = case['name'], case['spill_escape']
    if escape is None:
        oracle_require(expected['status'] == READY,
                       f'{name}: row-54 draw pass did not complete ({expected["status"]})')
        oracle_require(get8(expected['memory'], expected['regs']['ds'], PASS_COUNT) != 0,
                       name + ': row-54 draw pass visited no record')
        return
    record, target = escape
    oracle_require(expected['raw_status'] == 107 and expected['status'] == CHILD_STOP and
                   expected['child_entry'] == 0x706F and expected['child_status'] == 1,
                   f'{name}: row-54 draw did not stop at the 715B unknown-callback seam '
                   f'({expected["raw_status"]})')
    saved = get16(expected['memory'], case['ss'], (case['sp'] - 8) & 0xFFFF)
    oracle_require(expected['continuation'] == 0x715B and
                   expected['regs']['ax'] == target and saved == record and
                   get16(expected['memory'], expected['regs']['ds'], record + 0x14) == target,
                   f'{name}: 715B stop AX/record {expected["regs"]["ax"]:04X}/'
                   f'{saved:04X}, expected {target:04X}/{record:04X}')


def configured_vga(seed):
    device = MinimapVga(0x3634 ^ seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = device.gc[1] = device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    return device


def sprite_seed(case, first_record):
    first = case['records'][0] if case['records'] else {}
    return dict(name=case['name'], seed=case['seed'],
        callback=first.get('callback', 0x6170), visible=int(case['map_visible']),
        x=first.get('x', 0x20), x_bias=first.get('x_bias', 0),
        y=first.get('y', 0x20), y_bias=first.get('y_bias', 0),
        view_origin=0x10, selector=first.get('strip', 0),
        frame=first.get('frame', 0), frame_gate=1, frame_add=0,
        align_gate=0xFF, stride=90, paragraph=0, source_offset=0x0100,
        mask_offset=0x0200, source_length=90, buffer_segment=0x6000,
        generated_segment=0x6200, load=LOAD, ds=case['ds'], di=first_record,
        si=case['si'], ss=case['ss'], sp=case['sp'], es=case['es'],
        flags=case['flags'], outer_return=case['outer_return'], provider=None,
        map_entries={})


def setup(case):
    """Compose finite parent records and bounded child data in one RAM image."""
    first_record = case['record_offsets'][0] if case['record_offsets'] else RECORDS
    memory, regs, device, _producer, _bank = sprite.setup(
        sprite_seed(case, first_record))
    regs.update(cs=LOAD, ip=ENTRY, ds=case['ds'], es=case['es'],
                ss=case['ss'], sp=case['sp'], si=case['si'],
                cx=case['initial_count'], flags=((case['flags'] | 2) & FLAGS))

    # Clear the child visibility map before the longer bounded record tables
    # are laid down; the 255-record fixture spans DS:0EA8.
    vis_base = physical(case['ds'], 0x0EA8)
    memory[vis_base:vis_base + 0x400] = bytes(0x400)

    # Install every loop record after sprite setup so record/global aliases are
    # deliberate and record inputs remain stable across all child calls.
    for index, offset in enumerate(case['record_offsets']):
        record = case['records'][index]
        if index and case['records']:
            template = case['record_offsets'][0]
            for delta in range(0x2D):
                put8(memory, case['ds'], offset + delta,
                     get8(memory, case['ds'], template + delta), device)
        callback = record.get('callback', 0x7000)
        put16(memory, case['ds'], offset + 0x14, callback, device)
        put16(memory, case['ds'], offset + 0x00, record.get('x', 0x20), device)
        put16(memory, case['ds'], offset + 0x02, record.get('y', 0x20), device)
        put16(memory, case['ds'], offset + 0x04, record.get('x_bias', 0), device)
        put16(memory, case['ds'], offset + 0x06, record.get('dirty_height',
                                                               record.get('y_bias', 0)), device)
        put16(memory, case['ds'], offset + 0x08, record.get('dirty_flags', 0), device)
        put8(memory, case['ds'], offset + 0x20, record.get('strip', 0), device)
        put8(memory, case['ds'], offset + 0x26, record.get('skip', 0), device)
        put8(memory, case['ds'], offset + 0x27, 1, device)
        put8(memory, case['ds'], offset + 0x28,
             record.get('point_selector', record.get('frame', 0)), device)
        put8(memory, case['ds'], offset + 0x29, 0, device)
        put8(memory, case['ds'], offset + 0x2A, 0xFF, device)

    put8(memory, case['ds'], SLOT_BOUND, case['bound'], device)
    put8(memory, case['ds'], PASS_COUNT, case['initial_pass_count'], device)
    put16(memory, case['ds'], CALLBACK_SLOT,
          case['records'][0].get('callback_slot', 0xDEAD)
          if case['records'] else 0xDEAD, device)
    put16(memory, case['ds'], 0x0000, 0x0010, device)
    put16(memory, case['ds'], 0x1F76, 0x3000, device)
    put16(memory, case['ds'], 0x1FE6, 0x6000, device)
    put16(memory, case['ds'], 0x1FE8, 0x6200, device)
    put16(memory, case['ds'], 0x0026, 0x3000, device)
    put8(memory, case['ds'], 0x002A, 0, device)
    put8(memory, case['ds'], 0x004D, 1, device)
    put16(memory, case['ds'], 0x1F7A, 0x0010, device)
    for index, value in enumerate(bytes([0x80, 0x40, 0x20, 0x10,
                                         0x08, 0x04, 0x02, 0x01])):
        put8(memory, case['ds'], 0x547C + index, value, device)
    for index, value in enumerate(bytes([1, 2, 4, 8] + [0] * 12)):
        put8(memory, case['ds'], 0x2778 + index, value, device)

    # Bound each point visit to one sentinel; selectors 1 and 7F therefore
    # exercise signed parent selection and child table bounds without pixels.
    for record in case['records']:
        selector = record.get('point_selector', record.get('frame', 1)) & 0xFF
        point_start = (0x2788 + (((selector - 1) & 0xFF) * 0xA0)) & 0xFFFF
        put16(memory, case['ds'], point_start, 0x0080, device)

    # Dirty visibility and sprite visibility use separate index calculations.
    for index, record in enumerate(case['records']):
        x = record.get('x', 0x20)
        if case['map_visible']:
            map_index = ((x + record.get('x_bias', 0)) & 0xFFFF) >> 3
            put8(memory, case['ds'], 0x0EA8 + map_index, 1, device)
        if record.get('dirty_visible'):
            dirty_index = ((x + record.get('x_bias', 0)) & 0xFFFF) >> 3
            put8(memory, case['ds'], 0x0EA8 + dirty_index, 1, device)

    put16(memory, case['ds'], first_record + 0x0A, 0x0100, device)
    put16(memory, case['ds'], first_record + 0x0C, 0, device)
    put16(memory, case['ds'], first_record + 0x10, 90, device)
    put16(memory, case['ds'], first_record + 0x12, 0x0200, device)
    put16(memory, case['ds'], 0x1F76, 0x3000, device)
    for n in range(0x300):
        put8(memory, 0x6000, 0x0100 + n, (0x29 + 43 * n + case['seed']) & 0xFF, device)
        put8(memory, 0x6000, n, (0x81 + 17 * n + (case['seed'] >> 3)) & 0xFF, device)
    put16(memory, case['ss'], case['sp'], case['outer_return'], device)
    if case['ds'] == case['ss'] and case['sp'] == 0x2095:
        # Keep decimal destination/outer word as a live alias after all child
        # data initialization has completed.
        put16(memory, case['ss'], case['sp'], case['outer_return'], device)

    # Tables at 2778h and the point sentinels can alias later records in the
    # 255-slot fixtures. Restore each declared skip gate after all setup writes.
    for index, offset in enumerate(case['record_offsets']):
        put8(memory, case['ds'], offset + 0x26,
             case['records'][index].get('skip', 0), device)
    if case.get('provider') == 'saved-di-rewrite':
        # If the saved-DI rewrite is ignored, the ordinary next record is B5h.
        put8(memory, case['ds'], 0x00DB, 0xFF, device)
    if case.get('spill_origin') is not None:
        install_spill(case, memory, device)
    return memory, regs, device


def normalize_original(result, core):
    raw = result['status']
    result['raw_status'] = raw
    if raw in (101, 102, 103, 104):
        result.update(status=CHANGED_CHILD_RETURN,
                      child_entry=CALL_ENTRY[raw][0], child_status=0)
    elif raw in (105, 106):
        result.update(status=CHILD_STOP, child_entry=0x706F,
                      child_status=2)
    elif raw == 107:
        result.update(status=CHILD_STOP, child_entry=0x706F,
                      child_status=1)
    else:
        result.update(child_entry=0 if core else None,
                      child_status=NO_CHILD_STATUS if core else None)
    return result


def run_original(case, memory, regs, device, *, core):
    stops = {EARLY_RET: 0, DECIMAL_RET: 0} if core else {}
    observers = []
    result = interactions.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=MAIN_INS,
        main_call_returns=MAIN_CALL_RETURNS, stop_offsets=stops,
        access_factory=lambda c, m, r, d: observers.append(
            DrawingAccess(c, m, r, d, stops=stops)) or observers[-1],
        instruction_limit=MAX_INSTRUCTIONS)
    oracle_require(len(observers) == 1,
                   case['name'] + ': original access observer was not unique')
    result['observer_count'] = observers[0].callback_observations
    return normalize_original(result, core)


def assert_oracle_contract(case, expected, initial_memory, *, core):
    """Check fixture facts independently of any C/native comparison."""
    name = case['name']
    if 'expected_pass_count' in case:
        actual = get8(expected['memory'], expected['regs']['ds'], PASS_COUNT)
        oracle_require(actual == case['expected_pass_count'],
                       f'{name}: pass count {actual:02x}/'
                       f'{case["expected_pass_count"]:02x}')
    if 'expected_ascii' in case:
        actual = tuple(get8(expected['memory'], expected['regs']['ds'],
                            0x2095 + offset) for offset in range(3))
        oracle_require(actual == case['expected_ascii'],
                       f'{name}: decimal field {actual!r}/'
                       f'{case["expected_ascii"]!r}')
    if case.get('expected_field_unchanged'):
        before = tuple(get8(initial_memory, case['ds'], 0x2095 + offset)
                       for offset in range(3))
        after = tuple(get8(expected['memory'], expected['regs']['ds'],
                           0x2095 + offset) for offset in range(3))
        oracle_require(after == before,
                       f'{name}: zero-bound path modified decimal output {before!r}/{after!r}')

    provider = case.get('provider')
    required_provider = ('returned-ds' if provider == 'returned-ds-count-200'
                         else provider)
    if required_provider:
        oracle_require(required_provider in expected['used'],
                       f'{name}: provider {required_provider!r} was not used')
    if name in ('unknown-callback-stops-with-guard-ff',
                'known-then-unknown-callback-live-observer'):
        if core:
            oracle_require(expected['status'] == CHILD_STOP and
                           expected['child_entry'] == 0x706F and
                           expected['child_status'] == 1,
                           f'{name}: unknown callback seam changed')
            oracle_require(get8(expected['memory'], expected['regs']['ds'], GUARD) == 0xFF,
                           f'{name}: stopped sprite child cleared the work guard')
        oracle_require(expected['observer_count'] > 0 and
                       'callback-target-observer' in expected['used'],
                       f'{name}: callback target observer did not run')
    if name == 'known-then-unknown-callback-live-observer':
        oracle_require(expected['observer_count'] >= 2,
                       'mixed known/unknown fixture did not observe both callbacks')
    if core:
        expected_seams = {
            'changed-minimap-child-return': (CHANGED_CHILD_RETURN, 0x6FE2, 0),
            'changed-dirty-child-return': (CHANGED_CHILD_RETURN, 0x5726, 0),
            'changed-points-child-return': (CHANGED_CHILD_RETURN, 0x6E83, 0),
            'changed-sprite-outer-return': (CHANGED_CHILD_RETURN, 0x706F, 0),
            'changed-nested-strip-return': (CHILD_STOP, 0x706F, 2),
            'changed-nested-callback-return': (CHILD_STOP, 0x706F, 2),
        }
        if name in expected_seams:
            status, entry, child_status = expected_seams[name]
            oracle_require(expected['status'] == status and
                           expected['child_entry'] == entry and
                           expected['child_status'] == child_status,
                           f'{name}: child continuation/status contract changed')


def compare(native, case, *, core):
    initial_memory, initial_regs, initial_device = setup(case)
    expected = run_original(case, initial_memory, initial_regs,
                            initial_device, core=core)
    assert_oracle_contract(case, expected, initial_memory, core=core)
    if case.get('spill_origin') is not None:
        assert_spill_draw(case, expected, core=core)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    actual = native.run(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core)
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    flag_mask = expected['flag_mask']
    for name in interactions.REG_NAMES:
        mask = flag_mask if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04x}/'
                f'{expected["regs"][name]:04x} under {mask:04x}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04x}/'
            f'{expected["continuation"]:04x}')
    if core:
        require(actual['child_entry'] == expected['child_entry'] and
                actual['child_status'] == expected['child_status'],
                f'{label}: child seam '
                f'{actual["child_entry"]:04x}/{actual["child_status"]:04x}/'
                f'{expected["child_entry"]:04x}/{expected["child_status"]:04x}')
    require(actual['used'] == expected['used'],
            f'{label}: provider transitions {actual["used"]}/{expected["used"]}')
    require(len(actual['events']) == len(expected['events']),
            f'{label}: bus event count {len(actual["events"])}/'
            f'{len(expected["events"])}')
    for index, (got, ref) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == ref[:3],
                f'{label}: bus event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: bus event {index} FLAGS {got[3]:04x}/{ref[3]:04x} '
                f'under {ref[4]:04x}')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA device state differs')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(got_trace == ref_trace, label + ': VGA trace differs')
    return expected


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/adlib-regions.json', 'metadata/adlib-symbols.json',
        'metadata/adlib-encodings.json', 'metadata/tandysnd-regions.json',
        'metadata/tandysnd-symbols.json', 'metadata/tandysnd-encodings.json',
        'src/entity_drawing_calls.asm', 'src/game_code.asm',
        'src/game_code_late_after_palette.asm', 'src/entity_sprite_dispatch.asm',
        'src/entity_minimap.asm', 'src/entity_dirty.asm',
        'src/entity_points.asm', 'src/entity_sprite_four_planes.asm',
        'src/decimal_fields.asm', 'src/entry_services.asm',
        'src/entity_sprite_aligned.asm', 'src/entity_sprite_shifted.asm',
        'src/entity_sprite_planes.asm', 'src/entity_sprite_wide.asm',
        'src/entity_strip.asm', 'src/program.asm', 'src/image_tail.asm',
        'c/entity_drawing.c', 'c/entity_drawing.h',
        'c/entity_minimap.c', 'c/entity_minimap.h',
        'c/entity_dirty.c', 'c/entity_dirty.h',
        'c/entity_points.c', 'c/entity_points.h',
        'c/entity_sprite_dispatch.c', 'c/entity_sprite_dispatch.h',
        'c/entity_sprite_aligned.c', 'c/entity_sprite_aligned.h',
        'c/entity_sprite_shifted.c', 'c/entity_sprite_shifted.h',
        'c/entity_sprite_wide.c', 'c/entity_sprite_wide.h',
        'c/entity_strip.c', 'c/entity_strip.h',
        'c/decimal_field.c', 'c/decimal_field.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/entity_drawing.py', 'tests/entity_interactions.py',
        'tests/entity_create.py', 'tests/entity_update.py',
        'assets/level006.dat', 'assets/oddtable.dat',
        'tests/entity_minimap.py', 'tests/entity_dirty.py',
        'tests/entity_points.py', 'tests/entity_sprite_dispatch.py',
        'tests/entity_sprite_aligned.py', 'tests/entity_sprite_shifted.py',
        'tests/entity_sprite_planes.py', 'tests/entity_sprite_wide.py',
        'tests/entity_strip.py', 'tests/entity_sprite_layout.py',
        'tests/decimal_field.py', 'tests/minimap_vga.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py', 'tools/unpack.py',
        'tools/coverage.py',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing drawing hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def verify_static_inventory():
    oracle_require(len(IMAGE) == 82906 and
                   sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'static main image identity changed')
    oracle_require(CODE_BYTES == 89 and len(OWN_INS) == 35 and
                   len(OWN_CONDITIONALS) == 5 and
                   len(UNCONDITIONAL_EDGES) == 2,
                   'DrawEntityRecords 3634..368D static inventory changed')
    decimal_sites = {address: ins for address, ins in decimal_field.INS.items()
                     if 0x4B68 <= address <= DECIMAL_RET}
    oracle_require(sum(ins.size for ins in decimal_sites.values()) == 86 and
                   len(decimal_sites) == 40,
                   'shared decimal byte tail inventory changed')
    oracle_require(sum(ins.size for ins in MAIN_INS.values()) == 4425 and
                   len(MAIN_INS) == 2191,
                   'integrated entity-drawing instruction union changed')
    return decimal_sites


def original_campaign(hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'entity-drawing inputs changed before original-only campaign')
    decimal_sites = verify_static_inventory()
    fixture_rows = make_cases()
    parent_sites, parent_edges = set(), set()
    integrated_sites, integrated_edges = set(), set()
    total_steps = total_events = total_observer_reads = 0
    rows = []
    for case in fixture_rows + spill_cases():
        boundaries = []
        for core in (True, False):
            memory, regs, device = setup(case)
            expected = run_original(case, memory, regs, device, core=core)
            assert_oracle_contract(case, expected, memory, core=core)
            if case.get('spill_origin') is not None:
                assert_spill_draw(case, expected, core=core)
            boundaries.append(dict(core=core, status=expected['status'],
                                   raw_status=expected['raw_status'],
                                   continuation=expected['continuation'],
                                   steps=expected['steps'],
                                   bus_events=len(expected['events']),
                                   callback_observations=expected['observer_count'],
                                   providers=sorted(expected['used'])))
            for scope, address in expected['sites']:
                if scope == 'main':
                    integrated_sites.add(address)
                    if address in OWN_SITES:
                        parent_sites.add(address)
            for scope, source, destination in expected['edges']:
                if scope == 'main':
                    integrated_edges.add((source, destination))
                    if source in OWN_INS:
                        parent_edges.add((source, destination))
            total_steps += expected['steps']
            total_events += len(expected['events'])
            total_observer_reads += expected['observer_count']
        rows.append(dict(name=case['name'], bound=case['bound'],
                         provider=case.get('provider'), boundaries=boundaries))
        gc.collect()

    oracle_require(parent_sites == OWN_SITES,
                   f'original parent site coverage differs: {parent_sites ^ OWN_SITES}')
    oracle_require(parent_edges == OWN_EDGES,
                   f'original parent branch edges differ: '
                   f'missing={OWN_EDGES - parent_edges}, '
                   f'extra={parent_edges - OWN_EDGES}')
    after = input_hashes()
    oracle_require(before == after,
                   'entity-drawing inputs changed during original-only campaign')
    write_json(ORIGINAL_REPORT, dict(
        image='main', image_sha256=sha(IMAGE), original_only=True,
        native_execution_count=0, c_coverage_claimed=False,
        case_count=len(rows), comparisons=len(rows) * 2, cases=rows,
        parent_body_code_bytes=CODE_BYTES,
        parent_body_instruction_sites=len(OWN_INS),
        parent_body_code_ranges=[[ENTRY, UNKNOWN], [0x3670, END]],
        parent_body_instruction_addresses=sorted(OWN_SITES),
        existing_decimal_tail_code_bytes=sum(ins.size for ins in decimal_sites.values()),
        existing_decimal_tail_instruction_sites=len(decimal_sites),
        translated_code_bytes=0,
        integrated_static_code_bytes=sum(ins.size for ins in MAIN_INS.values()),
        integrated_static_instruction_sites=len(MAIN_INS),
        executed_instruction_addresses=sorted(integrated_sites),
        parent_executed_instruction_addresses=sorted(parent_sites),
        parent_executed_branch_edges=[list(edge) for edge in sorted(parent_edges)],
        integrated_executed_branch_edges=[list(edge) for edge in sorted(integrated_edges)],
        total_original_instruction_hook_steps=total_steps,
        total_bus_events=total_events,
        callback_observer_snapshots=total_observer_reads,
        mutation_count=0, mutations=[], input_hashes=after,
        limits=dict(worker_seconds=360, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=PROCESS_MIB + 256,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    callback_event_limit=MAX_EVENTS),
        domain='Original-only preflight of DrawEntityRecords 3634..368D, '
               'excluding UNKNOWN 366F; finite loop, child seam, provider, '
               'and shared decimal-tail fixtures'))
    print(f'PASS entity drawing original-only: {len(rows)} cases at core+adapter; '
          f'{CODE_BYTES} parent bytes/{len(parent_sites)} sites/'
          f'{len(parent_edges)} edges; {total_events} bus events', flush=True)


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'entity-drawing inputs changed before native campaign')
    decimal_sites = verify_static_inventory()

    fixture_rows = make_cases()
    baseline = Native(directory)
    parent_sites, parent_edges = set(), set()
    integrated_sites, integrated_edges = set(), set()
    total_steps = total_events = total_observer_reads = 0
    rows = []
    for case in fixture_rows + spill_cases():
        boundaries = []
        for core in (True, False):
            expected = compare(baseline, case, core=core)
            boundaries.append(dict(core=core, status=expected['status'],
                                   raw_status=expected['raw_status'],
                                   continuation=expected['continuation'],
                                   steps=expected['steps'],
                                   bus_events=len(expected['events']),
                                   callback_observations=expected['observer_count']))
            for scope, address in expected['sites']:
                if scope == 'main':
                    integrated_sites.add(address)
                    if address in OWN_SITES:
                        parent_sites.add(address)
            for scope, source, destination in expected['edges']:
                if scope == 'main':
                    integrated_edges.add((source, destination))
                    if source in OWN_INS:
                        parent_edges.add((source, destination))
            total_steps += expected['steps']
            total_events += len(expected['events'])
            total_observer_reads += expected['observer_count']
        rows.append(dict(name=case['name'], bound=case['bound'],
                         provider=case.get('provider'), boundaries=boundaries))
        gc.collect()

    oracle_require(parent_sites == OWN_SITES,
                   f'parent executed-site coverage differs: {parent_sites ^ OWN_SITES}')
    expected_edges = set(OWN_EDGES)
    oracle_require(parent_edges == expected_edges,
                   f'parent branch-edge coverage differs: '
                   f'missing={expected_edges - parent_edges}, '
                   f'extra={parent_edges - expected_edges}')

    witnesses = [
        (1, 'zero-bound-preserves-stale-count', True),
        (2, 'one-record-skipped', True),
        (3, '255-active-pass-count', True),
        (4, 'signed-frame-selector-80-enters-sprite', True),
        (5, 'saved-di-rewrite-selects-next-record', True),
        (6, 'saved-cx-shortens-parent-loop-live', True),
        (7, 'unknown-callback-stops-with-guard-ff', True),
        (8, 'changed-minimap-child-return', True),
        (9, 'one-record-skipped', True),
        (10, 'zero-bound-preserves-stale-count', False),
    ]
    by_name = {case['name']: case for case in fixture_rows}
    mutations = []
    for number, name, core in witnesses:
        mutant = Native(directory, number)
        try:
            compare(mutant, by_name[name], core=core)
        except Mismatch as error:
            mutations.append(dict(mutation=number, case=name, core=core,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'entity-drawing mutation {number} survived')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after,
                   'entity-drawing inputs changed during bounded campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), case_count=len(rows),
        comparisons=len(rows) * 2, cases=rows,
        parent_body_code_bytes=CODE_BYTES, parent_body_instruction_sites=len(OWN_INS),
        parent_body_code_ranges=[[ENTRY, UNKNOWN], [0x3670, END]],
        parent_body_instruction_addresses=sorted(OWN_SITES),
        existing_decimal_tail_code_bytes=sum(ins.size for ins in decimal_sites.values()),
        existing_decimal_tail_instruction_sites=len(decimal_sites),
        translated_code_bytes=CODE_BYTES +
            sum(ins.size for ins in decimal_sites.values()),
        integrated_static_code_bytes=sum(ins.size for ins in MAIN_INS.values()),
        integrated_static_instruction_sites=len(MAIN_INS),
        parent_executed_instruction_addresses=sorted(parent_sites),
        parent_executed_branch_edges=[list(edge) for edge in sorted(parent_edges)],
        executed_instruction_addresses=sorted(integrated_sites),
        integrated_executed_instruction_addresses=sorted(integrated_sites),
        integrated_executed_branch_edges=[list(edge) for edge in sorted(integrated_edges)],
        total_original_instruction_hook_steps=total_steps,
        total_bus_events=total_events,
        callback_observer_snapshots=total_observer_reads,
        mutation_count=len(mutations), mutations=mutations, input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=PROCESS_MIB + 256,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domain='DrawEntityRecords 3634..368D, excluding UNKNOWN 366F; finite '
               'record bounds, signed selector gates, all nine known sprite targets, '
               'point/minimap/dirty/sprite child seams, changed nested returns, live '
               'SS providers, guard and DS flow, and the shared frame-free decimal tail. '
               'Row-54 spill slice: records 00..62 after the original 410F rebuild '
               'and 1F19 pass at nine characterized origins; the first non-callback '
               '+14 stops both sides at 715B (C unknown-callback status) with equal '
               'machine state, otherwise the 63h-slot pass completes; two key-channel '
               'cases (scan 15/16 make at origin 0090) stop at record 55'))
    print(f'PASS entity drawing: {len(rows)} cases at core+adapter; '
          f'{CODE_BYTES} parent bytes/{len(parent_sites)} sites/'
          f'{len(parent_edges)} edges; {total_events} bus events; '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        original_campaign(sys.argv[2])
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:] == ['--original-only']:
        BUILD.mkdir(exist_ok=True)
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-drawing-original-',
                                        parent=BUILD) as directory:
            hash_path = Path(directory) / 'entity-drawing-inputs.json'
            hash_path.write_text(json.dumps(input_hashes(), sort_keys=True),
                                 encoding='utf-8')
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=360, memory_mib=PROCESS_MIB, check=True)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_drawing.py')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-drawing-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'entity-drawing-inputs.json'
        hash_path.write_text(json.dumps(input_hashes(), sort_keys=True),
                             encoding='utf-8')
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory, str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
