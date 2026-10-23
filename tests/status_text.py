"""Bounded original/native checks for the live 417B status-text caller."""
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
from entity_interactions import OracleFailure, REG_NAMES, REG_IDS, Regs
from entity_interactions import original as run_original
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
import status_glyph as glyph_test
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
LOAD = 0x1010
LOADED = relocated(IMAGE, META['relocations'], LOAD)
ENTRY, AFTER_GLYPH, RET, END = 0x417B, 0x4185, 0x418B, 0x418C
GLYPH_RETURNS = {0x77FD, 0x780C}
DRAWING_ORIGIN = 0x1F76
BUFFER_SEGMENT = 0x1FEC
DATA_SEGMENT = 0x3500
SOURCE_SEGMENT = 0x4A00
ALT_SOURCE_SEGMENT = 0x4B00
DF, IF, TF, CF = 0x0400, 0x0200, 0x0100, 0x0001
ENTRY_FLAGS = (FLAGS | DF) & ~TF
MAX_INSTRUCTIONS, MAX_EVENTS = 20000, 16384
WORKER_SECONDS, PROCESS_MIB = 240, 384
TREE_MIB = PROCESS_MIB + 256
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-text-differential.json'
ORIGINAL_REPORT = BUILD / 'status-text-original-differential.json'

MEM = ct.POINTER(ct.c_uint8)


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
                 'stack_segment', 'stack_offset', 'flags',
                 'continuation', 'status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


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


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_INS = {ins.address: ins for ins in
              MD.disasm(IMAGE[ENTRY:END], ENTRY)}
GLYPH_INS = glyph_test.INSTRUCTIONS
MAIN_INS = PARENT_INS | GLYPH_INS
PARENT_SITES = set(PARENT_INS)

# When mutation 6 ignores a changed child RET it must still reach a finite,
# valid NUL without changing any executable byte. The 0014 stack alias loads
# DS=0E01 from the VGA mirror; this finds a zero in the pinned relocated image
# at 0E01:(SI+1), then chooses the entry SI that reaches it after LODSB.
SAFE_IMAGE_ZERO = next(index for index, value in enumerate(LOADED[:0xD010])
                       if value == 0)
SAFE_SEAM_NEXT_SI = (SAFE_IMAGE_ZERO + 0x20F0) & 0xFFFF


def static_edges(instructions):
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


PARENT_EDGES = static_edges(PARENT_INS)
oracle_require(sum(ins.size for ins in PARENT_INS.values()) == 17 and
               len(PARENT_SITES) == 11,
               'status-text parent static boundary changed')
oracle_require(len(PARENT_EDGES) == 3,
               f'status-text branch map changed: {sorted(PARENT_EDGES)}')


def make_cases():
    line40 = IMAGE[0x09A90 + 0x2083:0x09A90 + 0x20AB].decode('ascii')
    oracle_require(len(line40) == 40, '40-byte status fixture construction changed')
    long_line = 'VALUE:' + '0123456789' * 4
    oracle_require(len(long_line) > 40, 'long status fixture must exceed 40 bytes')
    return [
        dict(name='empty-string', text='', ah=0x28, seed=0x417B01),
        dict(name='single-space-child-return', text=' ', ah=0x31, seed=0x417B02),
        dict(name='single-rejected-selector', text='?', ah=0x45, seed=0x417B03),
        dict(name='normal-40-character-status-line', text=line40, ah=0x20,
             seed=0x417B04, plane_projection=True),
        dict(name='over-40-ah-wrap', text=long_line, ah=0xFE, seed=0x417B05),
        dict(name='integrated-vga-plane-sequence', text='A: 5', ah=0x72,
             seed=0x417B06, plane_projection=True),
        dict(name='df-reverse-source-scan', text='ABC', ah=0x5A, df=True,
             seed=0x417B07),
        dict(name='and-clears-incoming-carry', text='A', ah=0x17, flags=0x02D7,
             seed=0x417B08),
        dict(name='live-nul-provider-extends-string', text='A\x00Z', ah=0x46,
             patch_next=ord('B'), seed=0x417B09),
        dict(name='live-nul-provider-truncates-string', text='AB', ah=0x46,
             patch_next=0, seed=0x417B0A),
        dict(name='live-font-segment-after-output', text='A', ah=0x38,
             provider_buffer_segment=ALT_SOURCE_SEGMENT, seed=0x417B0B),
        dict(name='live-parent-pop-ax-si-provider', text='AB', ah=0xFE,
             parent_pop_ax=0xFE7F, parent_pop_si=0x4002, seed=0x417B0C),
        dict(name='nested-mirror-changes-child-return', text='AB', ah=0x30,
             sp=0x0012, post_scan_offset=0xFF08, seed=0x417B0D,
             expected_status=1),
        dict(name='live-pop-ds-changes-next-scan', text='AB', ah=0x30, sp=0x0016,
             alt_source_segment=0xFF08, seed=0x417B0E),
        dict(name='changed-child-ret-is-a-seam', text='A', ah=0x30, sp=0x0014,
             si=(SAFE_SEAM_NEXT_SI - 1) & 0xFFFF,
             seed=0x417B0F, expected_status=1),
        dict(name='actual-outer-ret-after-provider', text='A', ah=0x42,
             provider_outer_return=0x4567, seed=0x417B10),
        dict(name='physical-word-wrap-at-outer-ret', text='', ah=0x20,
             ss=0xFFFF, sp=0x000F, seed=0x417B11),
        dict(name='ordinary-data-stack-alias', text='A:Z', ah=0x10,
             ds=0x5200, ss=0x5200, seed=0x417B12),
    ] + spill_cases(line40)


# Row-54 header word +06 is 0063, so 36E2 stores minutes 63+30=93 at 20A7
# (040E/0413 set the tens/ones to '0'); the 01FA..0246 countdown then walks
# the high byte 93..30 over 99 minutes. The status line at canonical
# DS:2083 is drawn with the glyph selector contract: 93..5B and 40..3B are
# skipped (stale pixels stay), 5A..41 draw capitals, 3A draws ':'.
SPILL_MINUTES = ((0x93, '00'), (0x5A, '30'), (0x3A, '05'))


def spill_cases(line40):
    rows = []
    for index, (minute, seconds) in enumerate(SPILL_MINUTES):
        text = line40[:0x24] + chr(minute) + ':' + seconds + line40[0x28:]
        oracle_require(len(text) == 40 and line40[0x25] == ':',
                       'row-54 status line construction changed')
        rows.append(dict(name=f'row54-status-time-minute-{minute:02x}', text=text,
                         ah=0x20, ds=(LOAD + 0x09A9) & 0xFFFF, si=0x2083,
                         ss=(LOAD + 0x143E) & 0xFFFF, sp=0x4AF2, flags=0x0246,
                         df=False, seed=0x417B54 + index, plane_projection=True))
    return rows


def make_device(seed):
    return glyph_test.make_device(seed, read_map=seed & 3)


def setup(case):
    seed = case['seed']
    rng = random.Random(seed)
    memory = bytearray(SIZE)
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    base = LOAD << 4
    memory[base:base + len(loaded)] = loaded

    ds = case.get('ds', DATA_SEGMENT) & 0xFFFF
    ss = case.get('ss', 0x5200) & 0xFFFF
    sp = case.get('sp', 0x7000) & 0xFFFF
    source_segments = {SOURCE_SEGMENT, ALT_SOURCE_SEGMENT}
    source_segments.add(case.get('alt_source_segment', 0xFF08) & 0xFFFF)
    for source_segment in source_segments:
        for offset in range(0x800):
            put8(memory, source_segment, offset,
                 (offset * 73 + seed * 29 + source_segment * 11 + 0x35) & 0xFF)

    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    flags = (case.get('flags', 2 | (rng.randrange(0x10000) & ENTRY_FLAGS)) &
             ENTRY_FLAGS) | 2
    flags &= ~TF
    if case.get('df', bool(seed & 1)):
        flags |= DF
    else:
        flags &= ~DF
    regs.update(ax=(((case.get('ah', 0x35) & 0xFF) << 8) | 0xA5),
                bx=(0xA700 | (seed & 0xFF)), cx=(seed * 19 + 0x10) & 0xFFFF,
                dx=(seed * 23 + 0x0241) & 0xFFFF,
                si=case.get('si', 0x4000) & 0xFFFF,
                di=(seed * 7 + 0x1234) & 0xFFFF,
                bp=(seed * 13 + 0x51A7) & 0xFFFF,
                cs=LOAD, ds=ds, es=0x6300, ss=ss, sp=sp,
                ip=ENTRY, flags=flags)

    origin = case.get('origin', (seed * 37 + 0x1B7D) & 0xFFFF)
    put16(memory, ds, DRAWING_ORIGIN, origin)
    put16(memory, ds, BUFFER_SEGMENT, case.get('source_segment', SOURCE_SEGMENT))
    if case.get('provider_buffer_segment') is not None:
        put16(memory, ds, BUFFER_SEGMENT, SOURCE_SEGMENT)

    direction = -1 if flags & DF else 1
    for index, character in enumerate(case['text']):
        put8(memory, ds, regs['si'] + direction * index, ord(character))
    put8(memory, ds, regs['si'] + direction * len(case['text']), 0)

    if case.get('alt_source_segment') is not None:
        # The live DS-save mirror fixture reaches this segment after its first glyph.
        put8(memory, case['alt_source_segment'], regs['si'] + direction, 0)
    if case.get('post_scan_offset') is not None:
        put8(memory, ds, case['post_scan_offset'], 0)

    # The font partition is deliberately patterned in both provider targets.
    return_word = case.get('outer_return', 0xA531 + seed * 7 & 0xFFFF)
    put16(memory, ss, sp, return_word)
    device = make_device(seed ^ 0x7708)
    if ss == 0xA000:
        device.gc[4] = 0
        device.planes[0][sp] = return_word & 0xFF
        device.planes[0][(sp + 1) & 0xFFFF] = return_word >> 8
    oracle_require(memory[(LOAD << 4) + ENTRY:(LOAD << 4) + END] ==
                   LOADED[ENTRY:END] and
                   memory[(LOAD << 4) + 0x7708:(LOAD << 4) + 0x780D] ==
                   LOADED[0x7708:0x780D],
                   case['name'] + ': fixture setup modified pinned caller/child code')
    return memory, regs, device


class StatusTextAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.out_count = 0
        self.pending = []
        self.native = bool(case.get('_native', False))

    def _write_word(self, segment, offset, value):
        address = physical(segment, offset)
        self.store(address, value & 0xFF)
        self.store(address + 1, value >> 8)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        case = self.case
        if (kind == 'read' and case.get('patch_next') is not None and
                'source-byte-patched' not in self.used and
                address == physical(self.regs['ds'], self.regs['si'])):
            step = -1 if self.regs['flags'] & DF else 1
            target = physical(self.regs['ds'], self.regs['si'] + step)
            patch = (target, case['patch_next'] & 0xFF)
            if self.native:
                self.store(*patch)
            else:
                self.pending.append(patch)
            self.used.add('source-byte-patched')
        return result

    def instruction_complete(self):
        while self.pending:
            self.store(*self.pending.pop(0))

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('status-text word-port callback budget exhausted')
        if self.device is None:
            raise OracleFailure('status-text glyph requires the declared VGA device')
        if port not in (0x03C4, 0x03CE):
            raise OracleFailure(f'undeclared status-text OUT port {port:04X}')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        index = self.out_count
        self.out_count += 1
        if (index == 0 and self.case.get('provider_buffer_segment') is not None and
                'font-segment-updated' not in self.used):
            self._write_word(self.regs['ds'], BUFFER_SEGMENT,
                             self.case['provider_buffer_segment'])
            self.used.add('font-segment-updated')
        if index == 0 and 'parent_pop_ax' in self.case:
            self._write_word(self.regs['ss'], self.regs['sp'] - 2,
                             self.case['parent_pop_ax'])
            self._write_word(self.regs['ss'], self.regs['sp'] - 4,
                             self.case['parent_pop_si'])
            self.used.add('parent-saves-updated')
        if index == 0 and 'provider_outer_return' in self.case:
            self._write_word(self.regs['ss'], self.regs['sp'],
                             self.case['provider_outer_return'])
            self.used.add('outer-return-updated')


def run_reference(case, memory, regs, device, *, core):
    return run_original(
        case, memory, regs, device, False,
        entry_flag_mask=ENTRY_FLAGS, main_instructions=MAIN_INS,
        main_call_returns={0x4182: (GLYPH_RETURNS, 1)},
        stop_offsets={RET: 0} if core else None,
        access_factory=StatusTextAccess,
        instruction_limit=MAX_INSTRUCTIONS)


def independent_planes(case, memory, regs, device):
    """Compose the already-independent glyph-plane replay over a clean text."""
    if not case.get('plane_projection'):
        return None
    projected = copy.deepcopy(device)
    ah = (regs['ax'] >> 8) & 0xFF
    direction = -1 if regs['flags'] & DF else 1
    cursor = regs['si']
    for index, character in enumerate(case['text']):
        actual = memory[physical(regs['ds'], cursor)]
        oracle_require(actual == ord(character),
                       case['name'] + ': independent text projection input changed')
        glyph_regs = dict(regs)
        glyph_regs['ax'] = (ah << 8) | actual
        glyph_regs['sp'] = (regs['sp'] - 6) & 0xFFFF
        projected_case = {'al': actual}
        result = glyph_test.independent_device(projected_case, memory,
                                               glyph_regs, projected)
        oracle_require(result is not None,
                       case['name'] + ': expected clean independent glyph plane domain')
        projected = result
        cursor = (cursor + direction) & 0xFFFF
        ah = (ah + 1) & 0xFF
    return projected


def assert_independent(case, memory, regs, initial_device, expected, *, core):
    projected = independent_planes(case, memory, regs, initial_device)
    if projected is not None:
        oracle_require(projected.state() == expected['device'].state(),
                       case['name'] + ': independent integrated glyph-plane replay differs')
    oracle_require(expected['status'] == case.get('expected_status', 0),
                   case['name'] + ': original did not reach its declared completion/seam')
    if 'parent_pop_ax' in case:
        oracle_require('parent-saves-updated' in expected['used'] and
                       ('main', AFTER_GLYPH) in expected['sites'] and
                       ('main', 0x4186) in expected['sites'],
                       case['name'] + ': original did not consume the changed parent saves')
    if case['name'] == 'changed-child-ret-is-a-seam':
        oracle_require(expected['regs']['ip'] == 0xFF08 and
                       expected['regs']['sp'] == ((regs['sp'] - 4) & 0xFFFF),
                       case['name'] + ': live child RET did not stop before parent POPs')
    if case['name'] == 'actual-outer-ret-after-provider' and not core:
        oracle_require(expected['regs']['ip'] == case['provider_outer_return'] and
                       'outer-return-updated' in expected['used'],
                       case['name'] + ': outer RET did not consume the live provider word')


def native_fail(code, error):
    worker_exit(code, f'status-text native callback failed: {error}')


class NativeBus:
    def __init__(self, case, memory, regs, device):
        native_case = dict(case)
        native_case['_native'] = True
        self.access = StatusTextAccess(native_case, memory, regs, device)
        self.events = self.access.events
        self.used = self.access.used

        def read(_ctx, _mem, address, flags):
            try:
                return self.access.access('read', address, flags, FLAGS)
            except BaseException as error:
                native_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)
                return 0

        def write(_ctx, _mem, address, value, flags):
            try:
                self.access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                native_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        def output(_ctx, port, value, flags):
            try:
                self.access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                native_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-text-m{mutation}.dll',
                     mutation, 'status_text')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_status_text_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_status_text_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial_memory, initial_regs, initial_device, *, core):
        memory = bytearray(initial_memory)
        regs_dict = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs_dict, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs_dict)
        if core:
            call = Call(*(regs_dict[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
                'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), ct.byref(callback.bus))
            for name, field in zip(
                    ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
                     'ss', 'sp', 'flags'),
                    ('value', 'map_cursor', 'count', 'auxiliary_value',
                     'record_cursor', 'object_cursor', 'candidate_y',
                     'code_segment', 'data_segment', 'extra_segment',
                     'stack_segment', 'stack_offset', 'flags')):
                setattr(state, name, getattr(result, field))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(callback.bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) & 0xFFFF for name in REG_NAMES},
                    device=device, events=callback.events, used=set(callback.used),
                    status=status)


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: ordered bus event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    expected = run_reference(case, bytearray(initial), dict(regs),
                             copy.deepcopy(device), core=core)
    assert_independent(case, initial, regs, device, expected, core=core)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    for name in REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: provider use {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA registers, latches or planes differ')
    return dict(name=case['name'], core=core,
                status=expected['status'], continuation=expected['continuation'],
                parent_sites=sorted(off for source, off in expected['sites']
                                    if source == 'main' and off in PARENT_SITES),
                parent_edges=[list(edge[1:]) for edge in sorted(expected['edges'])
                              if edge[0] == 'main' and edge[1] in PARENT_SITES],
                integrated_glyph_sites=sorted(off for source, off in expected['sites']
                                              if source == 'main' and off in GLYPH_INS),
                steps=expected['steps'], events=len(expected['events']),
                output_words=sum(event[0] == 'out' for event in expected['events']),
                plane_check=('independent composed glyph replay'
                             if case.get('plane_projection') else
                             'full original/native device state'))


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'src/program.asm',
        'src/game_code_late_after_selection.asm', 'src/status_glyphs.asm',
        'c/status_text.c', 'c/status_text.h', 'c/status_glyph.c', 'c/status_glyph.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/status_text.py', 'tests/status_glyph.py', 'tests/status_icons.py',
        'tests/entity_interactions.py', 'tests/minimap_vga.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tools/resources.py', 'tools/unpack.py',
        'tools/common.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'required status-text input hashes missing: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(),
                   'status-text inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = run_reference(case, bytearray(initial), dict(regs),
                                     copy.deepcopy(device), core=core)
            assert_independent(case, initial, regs, device, expected, core=core)
            own_sites = {off for source, off in expected['sites']
                         if source == 'main' and off in PARENT_SITES}
            own_edges = {edge[1:] for edge in expected['edges']
                         if edge[0] == 'main' and edge[1] in PARENT_SITES}
            rows.append(dict(name=case['name'], core=core,
                             status=expected['status'],
                             sites=sorted(own_sites),
                             edges=[list(edge) for edge in sorted(own_edges)],
                             steps=expected['steps'], events=len(expected['events'])))
            sites.update(own_sites)
            edges.update(own_edges)
        del initial, regs, device
        gc.collect()
    oracle_require(sites == PARENT_SITES,
                   f'parent site union differs: missing={sorted(PARENT_SITES-sites)}')
    oracle_require(edges == PARENT_EDGES,
                   f'parent edge union differs: missing={sorted(PARENT_EDGES-edges)} '
                   f'extra={sorted(edges-PARENT_EDGES)}')
    oracle_require(before == input_hashes(),
                   'status-text inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'status-text inputs changed before native worker')
    specs = make_cases()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['parent_sites'])
            edges.update(tuple(edge) for edge in row['parent_edges'])
            total_events += row['events']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == PARENT_SITES,
                   f'native parent site union differs: missing={sorted(PARENT_SITES-sites)}')
    oracle_require(edges == PARENT_EDGES,
                   f'native parent edge union differs: missing={sorted(PARENT_EDGES-edges)}')

    by_name = {case['name']: case for case in specs}
    witnesses = {
        1: 'df-reverse-source-scan',
        2: 'and-clears-incoming-carry',
        3: 'over-40-ah-wrap',
        4: 'live-parent-pop-ax-si-provider',
        5: 'live-pop-ds-changes-next-scan',
        6: 'changed-child-ret-is-a-seam',
        7: 'single-space-child-return',
    }
    mutants = []
    for mutation, case_name in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[case_name], core=True)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=case_name,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'status-text mutation {mutation} survived {case_name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'status-text inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_range=[ENTRY, END], translated_code_bytes=END - ENTRY,
        instruction_sites=len(PARENT_SITES),
        static_instruction_addresses=sorted(PARENT_SITES),
        branch_edge_count=len(PARENT_EDGES), static_branch_edges=[list(e) for e in sorted(PARENT_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutants), mutations=mutants,
        executed_instruction_addresses=sorted(sites), branch_edges=[list(e) for e in sorted(edges)],
        cases=rows, total_bus_events=total_events, original_instruction_steps=total_steps,
        input_hashes=after,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domains=[
            'DrawStatusText 417B..418B: live NUL scan, DF-sensitive LODSB, AH byte wrap and actual outer RET',
            'real CALL 7708 with per-call allowed child returns 77FD/780C and live SS return-word seam',
            '40-byte stored status line plus a 46-byte line through the unchanged NUL scan, invalid selectors, spaces and reverse scans',
            'live source-byte/provider changes, DS:1FEC font segment reread and SS mirror aliases for saved AX/SI/DS/RET',
            'whole 1 MiB RAM, all logical registers, defined FLAGS, ordered memory/OUT callbacks and VGA state',
            'independent integrated glyph-plane replay for the 40-byte and short mixed-selector strings',
        ]))
    print(f'PASS status text: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} parent sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-text-original-', parent=BUILD) as directory:
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
            image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
            translated_code_bytes=END - ENTRY, instruction_sites=len(PARENT_SITES),
            static_instruction_addresses=sorted(PARENT_SITES),
            branch_edge_count=len(PARENT_EDGES), branch_edges=[list(e) for e in sorted(edges)],
            executed_instruction_addresses=sorted(sites), case_count=len(make_cases()),
            core_adapter_comparisons=len(rows), input_hashes=before, cases=rows,
            domain='Bounded original-only status-text parent/core/actual-RET comparisons with integrated glyph replay.'))
        print(f'PASS status text original preflight: {len(make_cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_text.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-text-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
