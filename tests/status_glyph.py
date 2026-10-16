"""Bounded original/native tests for DrawStatusGlyph (7708..780C)."""
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
from entity_interactions import OracleFailure, REG_NAMES, Regs
from entity_interactions import original as run_original
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from status_icons import (Call, Result, RasterBus, READ, WRITE, OUT, CORE_NAMES,
                          RESULT_FIELDS, physical, put16, get16, SIZE, MASK,
                          LOAD, DEFINED_FLAGS)
from unpack import ASSET, unpack, relocated

IMAGE, META = unpack(ASSET.read_bytes())
ENTRY, RET_GLYPH, RET_SPACE, END = 0x7708, 0x77FD, 0x780C, 0x780D
DRAWING_ORIGIN = 0x1F76
STATUS_GLYPH_BUFFER_SEGMENT = 0x1FEC
DF, IF, TF = 0x0400, 0x0200, 0x0100
ENTRY_FLAGS = DEFINED_FLAGS & ~TF
MAX_INSTRUCTIONS, MAX_EVENTS = 1024, 2048
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'status-glyph-differential.json'
ORIGINAL_REPORT = BUILD / 'status-glyph-original-differential.json'

# Five individually unresolved bytes are deliberately not disassembled.
KNOWN_RANGES = ((0x7708, 0x7765), (0x7766, 0x776F), (0x7770, 0x7792),
                (0x7793, 0x7799), (0x779A, 0x77A0), (0x77A1, END))
UNKNOWN_BYTES = (0x7765, 0x776F, 0x7792, 0x7799, 0x77A0)


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


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INSTRUCTIONS = {}
for start, stop in KNOWN_RANGES:
    INSTRUCTIONS.update({ins.address: ins for ins in MD.disasm(IMAGE[start:stop], start)})


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
CODE_BYTES = sum(stop - start for start, stop in KNOWN_RANGES)
oracle_require(CODE_BYTES == 256 and len(EXPECTED_SITES) == 118,
               f'status-glyph static boundary changed: {CODE_BYTES} known bytes, '
               f'{len(EXPECTED_SITES)} sites')
oracle_require(not set(UNKNOWN_BYTES) & EXPECTED_SITES,
               'an explicitly UNKNOWN byte entered the glyph instruction map')


def glyph_source_offset(selector):
    selector &= 0xFF
    if selector == 0x25:
        return 0x00A0
    if selector == 0x3A:
        return 0x02B0
    if 0x30 <= selector <= 0x39:
        return 0x00D0 + 0x30 * (selector - 0x30)
    if 0x41 <= selector <= 0x5A:
        return 0x02E0 + 0x30 * (selector - 0x41)
    return None


def cases():
    result = [dict(name=f'al-{value:02x}', al=value,
                   seed=(ENTRY * 257 + value * 0x9E37) & 0xFFFFFFFF)
              for value in range(256)]
    result.extend((
        dict(name='destination-wrap-ah-origin', al=0x25, ah=0x37,
             origin=0xDF40, seed=0x771001),
        dict(name='pop-ax-live-ss-zero-alias', al=0x20, ah=0xA7,
             sp=0x0004, seed=0x771002),
        dict(name='pop-ds-live-map-mirror-alias', al=0x7F, ah=0x31,
             sp=0x000A, seed=0x771003),
        dict(name='pop-di-live-vga-alias', al=0x25, ah=0x24,
             ss=0xA000, origin=0x5196, sp=0x7000, seed=0x771004),
        dict(name='ret-word-overwritten-by-map-mirror', al=0x7F, ah=0x52,
             sp=0x0008, return_word=0x4567, seed=0x771005),
        dict(name='live-source-segment-after-first-out', al=0x3A,
             source_segment=0x4A00, provider_source_segment=0x4B00,
             seed=0x771006),
        dict(name='backward-glyph-reads-and-writes', al=0x25, df=True,
             seed=0x771007),
        dict(name='space-zero-no-aperture-read-if-clear', al=0x20,
             iflag=False, seed=0x771008),
        dict(name='invalid-preserves-clear-if', al=0x7F, iflag=False,
             seed=0x771009),
        dict(name='ds-a000-reads-live-source-pointer', al=0x25,
             ds=0xA000, seed=0x77100A),
        dict(name='ss-a000-vga-backed-stack-and-ret', al=0x3A,
             ss=0xA000, sp=0x5000, seed=0x77100B),
        dict(name='ordinary-ds-ss-alias', al=0x30, ds=0x3500,
             ss=0x3500, sp=0x7000, seed=0x77100C),
        dict(name='gc-setup-and-plane-pass-boundary', al=0x3A,
             seed=0x77100D),
    ))
    oracle_require(len(result) == 269, 'expected complete AL dispatch plus focused fixtures')
    oracle_require(len({case['name'] for case in result}) == len(result),
                   'status-glyph fixtures must have unique names')
    return result


def destination_base(ah, origin):
    return ((ah & 0xFF) + 0x1E40 + (origin & 0xFFFF) + 2) & 0xFFFF


def make_device(seed, read_map=0):
    device = MinimapVga(seed, read_map=read_map)
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[2] = 0
    device.gc[3] = 0
    device.gc[4] = read_map & 3
    device.gc[5] = 0
    device.gc[7] = 0x0F
    device.gc[8] = 0xFF
    return device


def put_device_word(device, offset, value, plane=0):
    device.planes[plane][offset & 0xFFFF] = value & 0xFF
    device.planes[plane][(offset + 1) & 0xFFFF] = (value >> 8) & 0xFF


def setup(case):
    seed = case['seed']
    rng = random.Random(seed)
    memory = bytearray(SIZE)
    loaded = relocated(IMAGE, META['relocations'], LOAD)
    base = LOAD << 4
    memory[base:base + len(loaded)] = loaded

    ds = case.get('ds', 0x3000) & 0xFFFF
    ss = case.get('ss', 0x5200) & 0xFFFF
    sp = case.get('sp', 0x7000) & 0xFFFF
    source_segment = case.get('source_segment', 0x4A00) & 0xFFFF
    source_segments = {source_segment}
    if case.get('provider_source_segment') is not None:
        source_segments.add(case['provider_source_segment'] & 0xFFFF)
    for segment in source_segments:
        for offset in range(0x800):
            memory[physical(segment, offset)] = (
                (offset * 73 + (seed >> 3) * 29 + segment * 11 + 0x35)
                & 0xFF)

    regs = {name: ((seed * (index + 0x17) + 0x51A7) & 0xFFFF)
            for index, name in enumerate(REG_NAMES)}
    ah = case.get('ah', (seed * 17 + 0x83) & 0xFF)
    flags = (2 | (rng.randrange(0x10000) & ENTRY_FLAGS)) & ~TF
    if case.get('df', bool(seed & 1)):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('iflag', bool(seed & 2)):
        flags |= IF
    else:
        flags &= ~IF
    origin = case.get('origin', (seed * 37 + 0x1B7D) & 0xFFFF)
    regs.update(ax=((ah << 8) | case['al']), bx=(0xA700 | (seed & 0xFF)),
                cx=((seed * 19 + 0x10) & 0xFFFF),
                dx=((seed * 23 + 0x0241) & 0xFFFF),
                si=((seed * 31 + 0x4300) & 0xFFFF),
                di=((seed * 7 + 0x1234) & 0xFFFF),
                cs=LOAD, ds=ds, es=0x6300, ss=ss, sp=sp,
                ip=ENTRY, flags=flags & 0xFFFF)

    if ds != 0xA000:
        put16(memory, ds, DRAWING_ORIGIN, origin)
        put16(memory, ds, STATUS_GLYPH_BUFFER_SEGMENT, source_segment)
    return_word = case.get('return_word', (0xA531 + seed * 7) & 0xFFFF)
    put16(memory, ss, sp, return_word)

    device = make_device(seed ^ 0x7708, read_map=(seed >> 5) & 3)
    if ds == 0xA000:
        # The source pointer and origin reads go through the selected VGA plane.
        device.gc[4] = 0
        put_device_word(device, DRAWING_ORIGIN, origin)
        put_device_word(device, STATUS_GLYPH_BUFFER_SEGMENT, source_segment)
    if ss == 0xA000:
        device.gc[4] = 0
        put_device_word(device, sp, return_word)

    # Nonzero, plane-distinct background makes the space path's writes visible.
    if case['al'] == 0x20:
        at = destination_base(ah, origin)
        for row in range(16):
            for plane in range(4):
                device.planes[plane][at] = (0x41 + row * 13 + plane * 29) & 0xFF
            at = (at + (0x2B + (-1 if flags & DF else 1))) & 0xFFFF
    return memory, regs, device


class GlyphAccess:
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events, self.used = [], set()
        self.out_count = 0
        self.mirror = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror is not None:
            self.mirror(address, value & 0xFF)

    def access(self, kind, address, flags, mask=ENTRY_FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('status-glyph callback event budget exhausted')
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
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF, mask))
        return value & 0xFF

    def out_word(self, port, value, flags, mask=ENTRY_FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('status-glyph OUT callback budget exhausted')
        if port not in (0x03C4, 0x03CE):
            raise OracleFailure(f'undeclared status-glyph OUT port {port:04X}')
        if self.device is None:
            raise OracleFailure('status glyph requires the declared VGA device')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        out_index = self.out_count
        self.out_count += 1
        if (self.case.get('provider_source_segment') is not None and
                out_index == 0 and 'source-segment-after-first-out' not in self.used):
            self.used.add('source-segment-after-first-out')
            put16(self.memory, self.regs['ds'], STATUS_GLYPH_BUFFER_SEGMENT,
                  self.case['provider_source_segment'])
            if self.mirror is not None:
                address = physical(self.regs['ds'], STATUS_GLYPH_BUFFER_SEGMENT)
                self.mirror(address, self.case['provider_source_segment'] & 0xFF)
                self.mirror(address + 1, self.case['provider_source_segment'] >> 8)


def independent_device(case, memory, regs, device):
    """Replay the selector map and three VGA passes independently of C/ASM."""
    if device is None or regs['ds'] == 0xA000 or regs['ss'] == 0xA000:
        return None
    if regs['sp'] in (0x0004, 0x0008, 0x000A):
        # Explicit stack/mirror aliases alter saved AX/DS/RET and are checked
        # against the complete CPU and bus oracle instead of a clean-stack model.
        return None
    expected = copy.deepcopy(device)
    replay_memory = bytearray(memory)
    setup_outputs = ((0x03C4, 0x0F02), (0x03CE, 0x0000), (0x03CE, 0x0E01),
                     (0x03CE, 0x0005), (0x03CE, 0x0003), (0x03CE, 0xFF08))
    for port, value in setup_outputs:
        expected.out(port, value, regs['flags'])

    selector = case['al'] & 0xFF
    ah = (regs['ax'] >> 8) & 0xFF
    origin = get16(memory, regs['ds'], DRAWING_ORIGIN)
    destination = destination_base(ah, origin)
    step = -1 if regs['flags'] & DF else 1
    if selector == 0x20:
        cursor = destination
        for _ in range(16):
            expected.write(replay_memory, VGA_BASE + cursor, 0, regs['flags'])
            cursor = (cursor + step + 0x2B) & 0xFFFF
        return expected

    source = glyph_source_offset(selector)
    if source is None:
        return expected
    source_segment = (case.get('provider_source_segment')
                      if case.get('provider_source_segment') is not None
                      else get16(memory, regs['ds'], STATUS_GLYPH_BUFFER_SEGMENT))
    cursor_si = source
    for pass_index in range(3):
        # The first pass uses the setup map mask 0F. Between passes one and
        # two, select GC index 1 before changing the sequencer map mask.
        if pass_index == 1:
            expected.out(0x03CE, 0x0001, regs['flags'])
            expected.out(0x03C4, 0x0202, regs['flags'])
        if pass_index == 2:
            expected.out(0x03C4, 0x0802, regs['flags'])
        cursor_di = destination
        for _ in range(16):
            address = VGA_BASE + cursor_di
            expected.read(replay_memory, address, regs['flags'])
            source_address = physical(source_segment, cursor_si)
            glyph_byte = replay_memory[source_address]
            expected.write(replay_memory, address, glyph_byte, regs['flags'])
            cursor_si = (cursor_si + step) & 0xFFFF
            cursor_di = (cursor_di + step + 0x2B) & 0xFFFF
    return expected


def assert_independent(case, initial_memory, regs, initial_device, expected):
    projected = independent_device(case, initial_memory, regs, initial_device)
    if projected is not None:
        oracle_require(projected.state() == expected['device'].state(),
                       case['name'] + ': independent three-pass plane replay differs')

    selector = case['al'] & 0xFF
    origin = get16(initial_memory, regs['ds'], DRAWING_ORIGIN)
    base = destination_base((regs['ax'] >> 8) & 0xFF, origin)
    step = -1 if regs['flags'] & DF else 1
    is_space = selector == 0x20
    source = glyph_source_offset(selector)
    alias_ax = regs['sp'] == 0x0004
    alias_ds = regs['sp'] == 0x000A
    actual_selector = 0x05 if alias_ax else selector
    is_space = actual_selector == 0x20
    source = glyph_source_offset(actual_selector)
    is_glyph = source is not None

    if (regs['sp'] not in (0x0004, 0x0008, 0x000A) and
            regs['ss'] != 0xA000 and regs['ds'] != 0xA000):
        final_di = (base if not (is_space or is_glyph) else
                    (base + 16 * (step + 0x2B)) & 0xFFFF)
        oracle_require(expected['regs']['di'] == final_di and
                       expected['regs']['es'] == 0xA000 and
                       expected['regs']['cx'] ==
                       (0 if (is_space or is_glyph) else regs['cx']),
                       case['name'] + ': independent destination/count contract differs')
        expected_dx = 0x03C4 if is_glyph else 0x03CE
        oracle_require(expected['regs']['dx'] == expected_dx,
                       case['name'] + ': independent final port cursor differs')
        if is_glyph:
            source_segment = (case.get('provider_source_segment')
                              if case.get('provider_source_segment') is not None
                              else get16(expected['memory'], regs['ds'],
                                         STATUS_GLYPH_BUFFER_SEGMENT))
            source_start = glyph_source_offset(actual_selector)
            source_last = (source_start + 47 * step) & 0xFFFF
            final_ax = 0x0800 | expected['memory'][physical(source_segment, source_last)]
            oracle_require(expected['regs']['ax'] == final_ax and
                           expected['regs']['si'] == (source_start + 48 * step) & 0xFFFF,
                           case['name'] + ': independent source/AX projection differs')
            oracle_require(bool(expected['regs']['flags'] & IF),
                           case['name'] + ': drawn glyph did not set IF')
        elif is_space:
            oracle_require(expected['regs']['si'] == regs['si'] and
                           expected['regs']['ax'] == (regs['ax'] & 0xFF00) and
                           bool(expected['regs']['flags'] & IF),
                           case['name'] + ': independent space path contract differs')
            raster_reads = [event for event in expected['events']
                            if event[0] == 'read' and VGA_BASE <= event[1] < VGA_END]
            oracle_require(not raster_reads,
                           case['name'] + ': space path performed an ES latch read')
        else:
            oracle_require(expected['regs']['si'] == regs['si'] and
                           expected['regs']['ax'] == regs['ax'] and
                           bool(expected['regs']['flags'] & IF) == bool(regs['flags'] & IF),
                           case['name'] + ': invalid selector changed preserved state')
            raster_accesses = [event for event in expected['events']
                               if event[0] in ('read', 'write') and
                               VGA_BASE <= event[1] < VGA_END]
            oracle_require(not raster_accesses,
                           case['name'] + ': invalid selector touched glyph pixels')

    if alias_ds:
        oracle_require(expected['regs']['ds'] == 0x0F02,
                       case['name'] + ': map-mask mirror did not overwrite saved DS')
    if alias_ax:
        oracle_require(expected['regs']['ax'] == 0x0005,
                       case['name'] + ': SS:0000 did not supply the live popped AX')
    if regs['sp'] == 0x0008 and expected['boundary'] == 'adapter-ret':
        oracle_require(expected['regs']['ip'] == 0x0F02,
                       case['name'] + ': adapter RET did not consume the overwritten word')


class NativeBus:
    def __init__(self, case, memory, regs, device):
        self.access = GlyphAccess(case, memory, regs, device)
        self.events, self.used = self.access.events, self.access.used

        def read(_context, _memory, address, flags):
            try:
                return self.access.access('read', address, flags, ENTRY_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'status-glyph read callback failed: {error}')
                return 0

        def write(_context, _memory, address, value, flags):
            try:
                self.access.access('write', address, flags, ENTRY_FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'status-glyph write callback failed: {error}')

        def output(_context, port, value, flags):
            try:
                self.access.out_word(port, value, flags, ENTRY_FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            f'status-glyph OUT callback failed: {error}')

        self.callbacks = (READ(read), WRITE(write), OUT(output))
        self.bus = RasterBus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'status-glyph-m{mutation}.dll',
                     mutation, 'status_glyph')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_draw_status_glyph_core
        self.core.argtypes = [ct.POINTER(ct.c_uint8), ct.POINTER(Call),
                              ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_draw_status_glyph_adapter
        self.adapter.argtypes = [ct.POINTER(ct.c_uint8), ct.POINTER(Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        callback = NativeBus(case, memory, regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(callback.bus))
            for name in CORE_NAMES:
                setattr(state, name, getattr(result, RESULT_FIELDS[name]))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(callback.bus))
        final = {name: getattr(state, name) & 0xFFFF for name in REG_NAMES}
        return dict(memory=bytes(memory), regs=final, device=device,
                    events=callback.events, used=set(callback.used), status=status,
                    continuation=final['ip'])


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: callback event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def compare_case(native, case, *, core):
    initial, regs, device = setup(case)
    expected = run_original(case, bytearray(initial), dict(regs),
                            copy.deepcopy(device), core,
                            entry_flag_mask=ENTRY_FLAGS,
                            main_instructions=INSTRUCTIONS,
                            instruction_limit=MAX_INSTRUCTIONS,
                            access_factory=GlyphAccess)
    assert_independent(case, initial, regs, device, expected)
    actual = native.run(case, initial, regs, device, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'] == 0,
            f'{label}: status {actual["status"]}/{expected["status"]}')
    for name in REG_NAMES:
        if name == 'flags':
            mask = expected['flag_mask']
            require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                    f'{label}: FLAGS {actual["regs"][name]:04X}/'
                    f'{expected["regs"][name]:04X} under {mask:04X}')
        else:
            require(actual['regs'][name] == expected['regs'][name],
                    f'{label}: {name} {actual["regs"][name]:04X}/'
                    f'{expected["regs"][name]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    require(actual['used'] == expected['used'],
            f'{label}: source provider observations {actual["used"]}/{expected["used"]}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA registers, planes or latches differ')
    require(len(actual['device'].trace) == len(expected['device'].trace),
            label + ': VGA-device trace length differs')
    vga_events = [event for event in expected['events']
                  if event[0] == 'out' or VGA_BASE <= event[1] < VGA_END]
    require(len(vga_events) == len(expected['device'].trace),
            label + ': VGA callbacks and device trace are not one-to-one')
    for index, (got, want, event) in enumerate(zip(actual['device'].trace,
                                                  expected['device'].trace,
                                                  vga_events)):
        require(got[:3] == want[:3],
                f'{label}: VGA trace {index} {got[:3]!r}/{want[:3]!r}')
        # Each device operation uses its instruction-entry mask. Later CMP/ADD
        # instructions can redefine flags that were undefined at an earlier OUT.
        require(((got[3] ^ want[3]) & event[4]) == 0,
                f'{label}: VGA trace FLAGS differ at {index}')
    return dict(name=case['name'], core=core,
                sites=sorted(off for source, off in expected['sites'] if source == 'main'),
                edges=[list(edge[1:]) for edge in sorted(expected['edges'])
                       if edge[0] == 'main'], steps=expected['steps'],
                events=len(expected['events']),
                output_words=sum(event[0] == 'out' for event in expected['events']),
                plane_check=('independent three-pass glyph/space replay'
                             if independent_device(case, initial, regs, device) is not None
                             else 'original/native full device state for live segment or stack alias'))


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/status-display.md', 'docs/status-icons.md',
        'assets/vgalemmi.exe', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/status_glyphs.asm',
        'src/status_icons.asm', 'src/game_code_late_after_entities.asm',
        'src/game_code_before_minimap.asm', 'src/image_tail.asm',
        'c/status_glyph.c', 'c/status_glyph.h', 'c/status_icons.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/status_glyph.py', 'tests/status_icons.py',
        'tests/entity_interactions.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/minimap_vga.py',
        'tools/resources.py', 'tools/unpack.py', 'tools/common.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
        'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'required status-glyph inputs missing: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(specs, before):
    oracle_require(before == input_hashes(), 'status-glyph inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    for case in specs:
        initial, regs, device = setup(case)
        for core in (True, False):
            expected = run_original(case, bytearray(initial), dict(regs),
                                    copy.deepcopy(device), core,
                                    entry_flag_mask=ENTRY_FLAGS,
                                    main_instructions=INSTRUCTIONS,
                                    instruction_limit=MAX_INSTRUCTIONS,
                                    access_factory=GlyphAccess)
            assert_independent(case, initial, regs, device, expected)
            own_sites = {off for source, off in expected['sites'] if source == 'main'}
            own_edges = {edge[1:] for edge in expected['edges'] if edge[0] == 'main'}
            rows.append(dict(name=case['name'], core=core, sites=sorted(own_sites),
                             edges=[list(edge) for edge in sorted(own_edges)],
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
    oracle_require(before == input_hashes(), 'status-glyph inputs changed during original preflight')
    return rows, sites, edges


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'status-glyph inputs changed before native worker')
    specs = cases()
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
                   f'native site union differs: missing={sorted(EXPECTED_SITES-sites)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'native branch outcomes differ: missing={sorted(EXPECTED_EDGES-edges)}')

    lookup = {case['name']: case for case in specs}
    witnesses = {
        1: ('pop-ax-live-ss-zero-alias', False),
        2: ('pop-di-live-vga-alias', True),
        3: ('al-80', True),
        4: ('gc-setup-and-plane-pass-boundary', True),
        5: ('space-zero-no-aperture-read-if-clear', True),
        6: ('backward-glyph-reads-and-writes', True),
        7: ('gc-setup-and-plane-pass-boundary', True),
        8: ('invalid-preserves-clear-if', True),
        9: ('ret-word-overwritten-by-map-mirror', False),
    }
    mutants = []
    for mutation, (name, core) in witnesses.items():
        variant = Native(directory, mutation)
        try:
            compare_case(variant, lookup[name], core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'status-glyph mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'status-glyph inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[list(span) for span in KNOWN_RANGES],
        unknown_bytes=list(UNKNOWN_BYTES), translated_code_bytes=CODE_BYTES,
        instruction_sites=len(EXPECTED_SITES),
        static_instruction_addresses=sorted(EXPECTED_SITES),
        branch_edge_count=len(EXPECTED_EDGES),
        static_branch_edges=[list(edge) for edge in sorted(EXPECTED_EDGES)],
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
            'DrawStatusGlyph 7708..780C: all 256 AL selectors at the logical core and actual-RET adapter boundaries',
            'known selector mapping for percent, colon, decimal digits and uppercase letters; five UNKNOWN bytes remain excluded',
            'three 16-row glyph passes with map masks 0F/02/08, live DS:1FEC source selection and 48 ordered source bytes',
            'space writes 16 zero bytes without an ES:DI latch read; invalid selectors preserve IF and perform no raster access',
            'live POP AX/DS/DI and RET aliases, source-provider change, DS/SS A000 cases, wrapped destination and DF-sensitive strings',
            'whole 1 MiB RAM, all logical registers, defined flags, ordered VGA memory/word-port callbacks and four-plane device state',
        ]))
    print(f'PASS status glyph: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='status-glyph-original-', parent=BUILD) as directory:
            before = input_hashes()
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, before)
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rows, sites, edges = original_campaign(cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE),
            code_ranges=[list(span) for span in KNOWN_RANGES],
            unknown_bytes=list(UNKNOWN_BYTES), translated_code_bytes=CODE_BYTES,
            instruction_sites=len(EXPECTED_SITES),
            static_instruction_addresses=sorted(EXPECTED_SITES),
            branch_edge_count=len(EXPECTED_EDGES), branch_edges=[list(e) for e in sorted(edges)],
            executed_instruction_addresses=sorted(sites), case_count=len(cases()),
            core_adapter_comparisons=len(rows), input_hashes=before, cases=rows,
            domain='Bounded original-only all-AL logical core/actual-RET comparisons with independent glyph mapping and VGA replay.'))
        print(f'PASS status glyph original preflight: {len(cases())} fixtures x core/adapter, '
              f'{len(sites)} sites/{len(edges)} edges', flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], str(Path(sys.argv[2]) / 'input-hashes.json'))
        return
    if sys.argv[1:]:
        raise SystemExit('usage: status_glyph.py [--original-only | --worker DIR]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='status-glyph-', parent=BUILD) as directory:
        before = input_hashes()
        hash_path = Path(directory) / 'input-hashes.json'
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
