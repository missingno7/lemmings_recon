"""Bounded differential checks for the 706F DrawObjectSprite parent.

The parent owns 706F..715E (240 bytes/113 sites). Its nine initialized
callbacks and optional strip are composed from their already-tested native
children through the original live CALL/RET words. Unknown callback targets
stop before CALL AX at 715B.
"""
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
import entity_sprite_aligned as aligned
import entity_sprite_shifted as shifted
import entity_sprite_planes as planes
import entity_sprite_wide as wide
import entity_strip as strip
import entity_sprite_layout as sprite_layout
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, RET, END, LOAD = 0x706F, 0x715E, 0x715F, 0x1010
DF, IF = 0x0400, 0x0200
ARITH = 0x08D5
MAX_INSTRUCTIONS, MAX_EVENTS = 60_000, 30_000
WORKER_SECONDS, PROCESS_MIB = 360, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-sprite-dispatch-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-sprite-dispatch-original-differential.json'
PROVIDER_LABELS = {
    'saved-selector-enables-strip': {'selector'},
    'strip-rewrites-callback': {'callback'},
    'strip-rewrites-callback-to-unknown': {'callback'},
    'strip-rewrites-saved-ds': {'saved-ds'},
    'strip-changes-return': {'strip-return'},
    'callback-changes-return': {'callback-return'},
    'callback-rewrites-saved-di': {'saved-di'},
}

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())
INTEGRATED_INS = {}
for module in (aligned, shifted, planes, wide, strip):
    INTEGRATED_INS.update(module.OWN_INS)
MAIN_INS = dict(INTEGRATED_INS)
MAIN_INS.update(OWN_INS)
CHILD_RETURNS = {0x64D8, 0x65D7, 0x66D6, 0x6816, 0x6956,
                 0x6A96, 0x6BDA, 0x6CFB, 0x6E82}
MAIN_CALL_RETURNS = {0x7152: ({0x6FE1}, 2),
                     0x715B: (CHILD_RETURNS, 2)}
REG_NAMES, REG_IDS = interactions.REG_NAMES, interactions.REG_IDS
MEM = ct.POINTER(ct.c_uint8)
CORE_NAMES = ('value', 'map_cursor', 'count', 'auxiliary_value',
              'record_cursor', 'object_cursor', 'candidate_y',
              'code_segment', 'data_segment', 'extra_segment',
              'stack_segment', 'stack_offset', 'flags')
REG_FIELDS = dict(value='ax', map_cursor='bx', count='cx',
                  auxiliary_value='dx', record_cursor='si', object_cursor='di',
                  candidate_y='bp', code_segment='cs', data_segment='ds',
                  extra_segment='es', stack_segment='ss', stack_offset='sp',
                  flags='flags')
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CORE_NAMES +
                ('continuation', 'status')]


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """Original/reference failure; never eligible as mutation evidence."""


class Mismatch(AssertionError):
    """Only a completed native/original difference is mutation evidence."""


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


def put_phys(memory, device, address, value, plane=0):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[plane & 3][address - VGA_BASE] = value


def put8(memory, segment, offset, value, device=None):
    put_phys(memory, device, physical(segment, offset), value)


def put16(memory, segment, offset, value, device=None):
    address = physical(segment, offset)
    put_phys(memory, device, address, value)
    put_phys(memory, device, address + 1, value >> 8)


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


CALLBACKS = {
    'aligned': 0x6170, 'shift12': 0x64D9, 'shift13': 0x65D8,
    '3plane10': 0x66D7, '3plane13': 0x6817, '3plane14': 0x6957,
    '3plane16': 0x6A97, 'wide32': 0x6BDB, '4plane14': 0x6CFC,
}


def make_cases():
    """Parent branch/stack fixtures plus one focused case per child callback."""
    specs = []
    for name, target in CALLBACKS.items():
        specs.append(dict(name='callback-' + name, callback=target))
        specs.append(dict(name='callback-' + name + '-alignment7',
                          callback=target, x=7, view_origin=0x10,
                          align_gate=0, frame=0))
    specs += [
        dict(name='visibility-zero-skips', visible=0),
        dict(name='visibility-two-is-not-one', visible=2),
        dict(name='visibility-index-is-shifted-three-times', x=8,
             map_entries={1: 1, 2: 0}),
        dict(name='first-x-add-wraps-negative-once', x=0xFFF0,
             x_bias=0, visible=1),
        dict(name='relative-view-subtract-wraps-negative-once', x=0,
             view_origin=0x0100, visible=1),
        dict(name='frame-byte-add-wraps', frame=0xFF,
             frame_add=1, frame_gate=0, align_gate=0xFF),
        dict(name='frame-gate-one-suppresses-add', frame=0xFF,
             frame_add=1, frame_gate=1, align_gate=0xFF),
        dict(name='alignment-index-scales-frame', x=7, view_origin=0x10,
             frame=2, align_gate=0, visible=1),
        dict(name='negative-y-clamps-before-row-origin', y=0xFFF0, visible=1),
        dict(name='physical-stack-word-wrap', ss=0xFFFF, sp=0x000F,
             visible=1, load=0x1010),
        dict(name='physical-outer-ret-word-wrap', ss=0xFFFF, sp=0x000F,
             visible=0, load=0x1010),
        dict(name='entry-df-and-if-are-preserved-through-child',
             flags=0x0ED7, visible=1),
        dict(name='unknown-live-callback-stops-before-call',
             callback=0x7000, visible=1, boundary='unknown'),
        dict(name='optional-strip-normal', selector=1, visible=1),
        dict(name='raw-selector-zero-provider-enters-strip', selector=0,
             provider='saved-selector-enables-strip', visible=1),
        dict(name='strip-uses-live-callback-word', selector=1,
             provider='strip-rewrites-callback', visible=1),
        dict(name='strip-uses-live-saved-ds', selector=1,
             provider='strip-rewrites-saved-ds', visible=1),
        dict(name='unknown-callback-replaced-by-known-strip', callback=0x7000,
             selector=1, provider='strip-rewrites-callback', visible=1),
        dict(name='known-callback-replaced-by-unknown-strip', selector=1,
             provider='strip-rewrites-callback-to-unknown', visible=1),
        dict(name='changed-strip-return-stops-before-restores', selector=1,
             provider='strip-changes-return', visible=1),
        dict(name='changed-callback-return-stops-before-pop-di',
             provider='callback-changes-return', visible=1),
        dict(name='final-pop-di-uses-live-saved-word',
             provider='callback-rewrites-saved-di', visible=1),
        dict(name='raw-zero-selector-live-save-enables-strip', selector=0,
             provider='saved-selector-enables-strip', visible=1),
        dict(name='mul-high-word-and-paragraph-wrap', callback=0x6BDB,
             frame=0xFFFF, stride=0xFFFF, paragraph=0xFFF0,
             align_gate=0xFF, visible=1),
    ]
    # These three cases use bytes produced by the identified original producer
    # routines; they are installed unchanged into the same parent RAM.
    specs += [
        dict(name='handoff-5b11-aligned-bank-five', callback=0x6170,
             producer=('5b11', 5), frame=0, stride=90, source_offset=0x0100,
             mask_offset=60, source_length=60,
             buffer_segment=0x6000, view_origin=0x10, x=5,
             align_gate=0, visible=1),
        dict(name='handoff-5bb0-three-plane-thirteen', callback=0x6817,
             producer=('5bb0', 0x030D), frame=0, stride=104,
             source_offset=0x0100, mask_offset=78, source_length=78,
             align_gate=0xFF, buffer_segment=0x6000, view_origin=0x10,
             x=7, visible=1),
        dict(name='handoff-5c06-wide-bank-three', callback=0x6BDB,
             producer=('5c06', 3), frame=0, stride=640,
             source_offset=0x0100, mask_offset=480, source_length=480,
             align_gate=0, buffer_segment=0x6000, view_origin=0x10,
             x=3, visible=1),
    ]
    cases = []
    for index, spec in enumerate(specs):
        row = dict(name='', seed=0x706F00 + index, callback=0x6170,
                   visible=1, x=0, x_bias=0, y=0x20,
                   y_bias=0, view_origin=0x10, selector=0, frame=0,
                   frame_gate=1, frame_add=0, align_gate=0xFF,
                   stride=90, paragraph=0, source_offset=0x0100,
                   mask_offset=0x0200, source_length=90,
                   buffer_segment=0x6000, generated_segment=0x6200,
                   load=LOAD, ds=0x09A9, di=0x2400, si=0xBEEF,
                   ss=0x5000, sp=0x9000, es=0x4137,
                   flags=0x0AD7, outer_return=0xD00D,
                   provider=None, boundary='adapter', map_entries={})
        row.update(spec)
        cases.append(row)
    oracle_require(24 <= len(cases) <= 50,
                   f'dispatch fixture count outside scope: {len(cases)}')
    return cases


def producer_for(case, producers):
    request = case.get('producer')
    if not request:
        return None, None
    name, index = request
    if name == '5b11':
        witness = producers['5b11']
        bank = witness.bank(index)
        descriptor = witness.banks[index]
    elif name == '5bb0':
        witness = producers['5bb0']
        bank = witness.bank(0)
        descriptor = witness.banks[0]
    else:
        witness = producers['5c06']
        bank = witness.bank(index)
        descriptor = witness.banks[index]
    return witness, (descriptor, bank)


def setup(case, producers=None):
    producer, selected_bank = producer_for(case, producers or {})
    rng = random.Random(0xD15A7C + case['seed'] * 0x9E3779B1)
    memory = bytearray(producer.memory if producer is not None
                       else rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], case['load'])
    base = physical(case['load'], 0)
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = MinimapVga(0x706F ^ case['seed'], read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = device.gc[1] = device.gc[3] = 0
    device.gc[4] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    for offset in range(0x10000):
        memory[VGA_BASE + offset] = device.planes[0][offset]

    regs = {name: (0x2B31 * (index + 1) + case['seed']) & 0xFFFF
            for index, name in enumerate(REG_NAMES)}
    regs.update(ax=0xBEEF, bx=0x7139, cx=0x6A55, dx=0x42D3,
                si=case['si'], di=case['di'], bp=0xA641,
                cs=case['load'], ds=case['ds'], es=case['es'],
                ss=case['ss'], sp=case['sp'], ip=ENTRY,
                flags=(case['flags'] | 2) & FLAGS)
    ds, di = regs['ds'], regs['di']
    put16(memory, ds, 0, case['view_origin'])
    put16(memory, ds, 0x1F76, 0x3000)
    put16(memory, ds, 0x1FE6, case['buffer_segment'])
    put16(memory, ds, 0x1FE8, case['generated_segment'])
    # The visibility table is separate from the VGA aperture and deliberately
    # initialized around both the expected and one-step-wrong lookup indices.
    map_base = physical(ds, 0x0EA8)
    memory[map_base:map_base + 0x400] = bytes(0x400)
    xsum = (case['x'] + case['x_bias']) & 0xFFFF
    if xsum & 0x8000:
        xsum = (xsum + 0x0160) & 0xFFFF
    map_index = xsum >> 3
    entries = dict(case.get('map_entries', {}))
    if map_index not in entries:
        entries[map_index] = case['visible']
    for index, value in entries.items():
        put8(memory, ds, 0x0EA8 + index, value, device)

    put16(memory, ds, di + 0x00, case['x'])
    put16(memory, ds, di + 0x02, case['y'])
    put16(memory, ds, di + 0x04, case['x_bias'])
    put16(memory, ds, di + 0x06, case['y_bias'])
    put16(memory, ds, di + 0x0A, case['source_offset'])
    put16(memory, ds, di + 0x0C, case['paragraph'])
    put16(memory, ds, di + 0x10, case['stride'])
    put16(memory, ds, di + 0x12, case['mask_offset'])
    put16(memory, ds, di + 0x14, case['callback'])
    put8(memory, ds, di + 0x20, case['selector'])
    put8(memory, ds, di + 0x27, case['frame_gate'])
    put8(memory, ds, di + 0x28, case['frame'])
    put8(memory, ds, di + 0x29, case['frame_add'])
    put8(memory, ds, di + 0x2A, case['align_gate'])

    # Generated source/mask bytes are finite and distinct. Actual-producer
    # fixtures retain the exact bank bytes and skip this synthetic fill.
    source_segment = case['buffer_segment']
    if selected_bank is None:
        src_off = case['source_offset']
        length = max(case['source_length'], 0x300)
        for n in range(length):
            put8(memory, source_segment, src_off + n,
                 (0x29 + 43 * n + case['seed']) & 0xFF, device)
        for n in range(max(case['mask_offset'] + 0x200, 0x300)):
            put8(memory, source_segment, n,
                 (0x81 + 17 * n + (case['seed'] >> 3)) & 0xFF, device)
    else:
        descriptor, bank = selected_bank
        bank_start = physical(producer.destination_segment,
                              producer.destination_offset + descriptor.output_offset)
        oracle_require(memory[bank_start:bank_start + len(bank)] == bank,
                       case['name'] + ': setup altered original producer bank')

    put16(memory, regs['ss'], regs['sp'], case['outer_return'], device)
    if case.get('callback') == 0x7000:
        # Unknown targets are deliberately finite because the core stops before
        # the indirect CALL and does not push a child frame.
        put16(memory, ds, di + 0x14, 0x7000)
    return memory, regs, device, producer, selected_bank


class DispatchAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, defer=False):
        super().__init__(case, memory, regs, device)
        self.case, self.defer = case, defer
        self.pending = []
        self.out_count = 0
        self.provider_writes = 0

    def _patch_word(self, offset, value):
        self.modify_word(self.case['ss'], offset & 0xFFFF, value)

    def _queue_or_apply(self, offset, value, label):
        if self.defer:
            self.pending.append((offset & 0xFFFF, value & 0xFFFF, label))
        else:
            self._patch_word(offset, value)
            self.used.add(label)

    def instruction_complete(self):
        for offset, value, label in self.pending:
            self._patch_word(offset, value)
            self.used.add(label)
        self.pending.clear()

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        result = super().access(kind, address, flags, mask, value)
        provider = self.case.get('provider')
        ss, sp = self.case['ss'], self.case['sp']
        # The 7100 PUSH DX is the trigger: replace the already-saved AL word
        # so the later live POP AX at 710B enters the strip despite raw +20=0.
        trigger = physical(ss, (sp - 10) & 0xFFFF)
        if (provider == 'saved-selector-enables-strip' and kind == 'write' and
                address == trigger and 'selector' not in self.used and
                'selector' not in {p[2] for p in self.pending}):
            self._queue_or_apply((sp - 8) & 0xFFFF, 0x0010, 'selector')
        return result

    def _strip_out_provider(self):
        provider = self.case.get('provider')
        ss, sp = self.case['ss'], self.case['sp']
        if provider in ('strip-rewrites-callback',
                        'strip-rewrites-callback-to-unknown') and 'callback' not in self.used:
            target = (0x7000 if provider == 'strip-rewrites-callback-to-unknown'
                      else (self.case.get('provider_callback_target', 0x64D9)))
            self._patch_word((sp - 6) & 0xFFFF, target)
            self.used.add('callback')
        elif provider == 'strip-changes-return' and 'strip-return' not in self.used:
            # Before strip CALL, six preserved parent words sit above its
            # return word; the exact live frame is asserted in original preflight.
            self._patch_word((sp - 16) & 0xFFFF, 0x7000)
            self.used.add('strip-return')
        elif provider == 'strip-rewrites-saved-ds' and 'saved-ds' not in self.used:
            self._patch_word((sp - 18) & 0xFFFF, 0x7000)
            self.used.add('saved-ds')
        elif provider == 'callback-changes-return' and 'callback-return' not in self.used:
            self._patch_word((sp - 4) & 0xFFFF, 0x7155)
            self.used.add('callback-return')
        elif provider == 'callback-rewrites-saved-di' and 'saved-di' not in self.used:
            self._patch_word((sp - 2) & 0xFFFF, 0x4567)
            self.used.add('saved-di')

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-sprite-dispatch event budget exhausted')
        self.out_count += 1
        if self.device is not None:
            self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        self._strip_out_provider()


def _original_pass(case, memory, regs, device, stop_offsets):
    return interactions.original(
        case, memory, regs, device, False, entry_flag_mask=FLAGS,
        main_instructions=MAIN_INS, main_call_returns=MAIN_CALL_RETURNS,
        stop_offsets=stop_offsets, access_factory=lambda c, m, r, d:
        DispatchAccess(c, m, r, d, defer=True),
        instruction_limit=MAX_INSTRUCTIONS)


def original(case, memory, regs, device, *, core=True):
    """Inspect the live callback POP, then execute only its known/bound path."""
    probe = _original_pass(case, bytearray(memory), dict(regs),
                           copy.deepcopy(device), {0x715B: 3})
    if probe['status'] != 3:
        if probe['status'] == 1:
            stop_offsets = {0x715B: 1}
        elif core:
            stop_offsets = {RET: 0}
        else:
            stop_offsets = None
        result = _original_pass(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), stop_offsets)
        result['callback_probe'] = probe
        return result
    target = probe['regs']['ax']
    if target not in set(CALLBACKS.values()):
        result = _original_pass(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), {0x715B: 1})
    else:
        result = _original_pass(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), {RET: 0} if core else None)
    result['callback_probe'] = probe
    return result


def independent_projection(case, memory):
    """Closed-form parent coordinate/frame/cursor projection from entry RAM."""
    ds, di = case['ds'], case['di']
    x = (get16(memory, ds, di) + get16(memory, ds, di + 4)) & 0xFFFF
    if x & 0x8000:
        x = (x + 0x0160) & 0xFFFF
    map_index = x >> 3
    map_value = get8(memory, ds, 0x0EA8 + map_index)
    if map_value != 1:
        return dict(visible=False, map_index=map_index, map_value=map_value)
    relative = (x - ((get16(memory, ds, 0) - 0x10) & 0xFFFF)) & 0xFFFF
    if relative & 0x8000:
        relative = (relative + 0x0160) & 0xFFFF
    alignment = relative & 7
    frame = get8(memory, ds, di + 0x28)
    if get8(memory, ds, di + 0x27) != 1:
        frame = (frame + get8(memory, ds, di + 0x29)) & 0xFF
    frame_index = frame if get8(memory, ds, di + 0x2A) == 0xFF else ((frame << 3) + alignment) & 0xFFFF
    product = frame_index * get16(memory, ds, di + 0x10)
    paragraph = (((product >> 4) & 0xFFFF) + get16(memory, ds, di + 0x0C)) & 0xFFFF
    si = ((product & 0xF) + get16(memory, ds, di + 0x0A)) & 0xFFFF
    bx = (si + get16(memory, ds, di + 0x12)) & 0xFFFF
    cx = (get16(memory, ds, 0x1FE6) + paragraph) & 0xFFFF
    dx = relative >> 3
    y = (get16(memory, ds, di + 2) + get16(memory, ds, di + 6)) & 0xFFFF
    if y & 0x8000:
        y = 0
    row_di = (y * 0x2C + dx + get16(memory, ds, 0x1F76)) & 0xFFFF
    return dict(visible=True, map_index=map_index, map_value=map_value,
                x=x, relative=relative, alignment=alignment,
                selector=get8(memory, ds, di + 0x20),
                frame_index=frame_index, product=product,
                paragraph=paragraph, source_cursor=si, mask_cursor=bx,
                source_segment=cx, horizontal_byte_offset=dx,
                y=y, destination_offset=row_di)


def assert_parent_projection(label, probe, projection, regs):
    """Check live parent coordinates and cursors immediately before CALL AX."""
    oracle_require(probe['status'] == 3 and probe['continuation'] == 0x715B,
                   label + ': expected an actual pre-CALL 715B boundary')
    observed = probe['regs']
    expected = {
        'ax': get16(probe['memory'], regs['ds'], regs['di'] + 0x14),
        'bx': projection['mask_cursor'],
        'cx': projection['source_segment'],
        'dx': projection['alignment'],
        'si': projection['source_cursor'],
        'bp': (projection['selector'] if projection['selector'] != 0
               else projection['paragraph']),
        'di': projection['destination_offset'],
    }
    for name, value in expected.items():
        oracle_require(observed[name] == value,
                       f'{label}: parent projection {name} '
                       f'{observed[name]:04X}/{value:04X}')
    oracle_require(observed['sp'] == ((regs['sp'] - 2) & 0xFFFF),
                   label + ': parent pre-CALL SP is not entry SP-2')


def compare_regs(label, actual, expected, flag_mask, error_type):
    for name in REG_NAMES:
        mask = flag_mask if name == 'flags' else 0xFFFF
        if ((actual[name] ^ expected[name]) & mask) != 0:
            raise error_type(f'{label}: {name} {actual[name]:04X}/{expected[name]:04X} '
                             f'under mask {mask:04X}')


def compare_events(label, actual, expected, error_type):
    if len(actual) != len(expected):
        raise error_type(f'{label}: {len(actual)} events, expected {len(expected)}')
    for i, (got, want) in enumerate(zip(actual, expected)):
        if got[:3] != want[:3]:
            raise error_type(f'{label}: event {i} {got[:3]!r}/{want[:3]!r}')
        if ((got[3] ^ want[3]) & want[4]) != 0:
            raise error_type(f'{label}: event {i} FLAGS {got[3]:04X}/{want[3]:04X} '
                             f'under {want[4]:04X}')


def compare_devices(label, actual, expected, error_type):
    if actual.state() != expected.state():
        raise error_type(label + ': VGA plane/latch/register state differs')
    if [event[:3] for event in actual.trace] != [event[:3] for event in expected.trace]:
        raise error_type(label + ': VGA trace differs')


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-sprite-dispatch-m{mutation}.dll',
                     mutation, 'entity_sprite_dispatch')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_draw_entity_sprite_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_entity_sprite_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = DispatchAccess(case, memory, regs, device, defer=False)

        def on_read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as exc:
                worker_exit(GUARD_EXIT if 'budget' in str(exc) else CALLBACK_EXIT, exc)

        def on_write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as exc:
                worker_exit(GUARD_EXIT if 'budget' in str(exc) else CALLBACK_EXIT, exc)

        def on_out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as exc:
                worker_exit(GUARD_EXIT if 'budget' in str(exc) else CALLBACK_EXIT, exc)

        callbacks = (READ(on_read), WRITE(on_write), OUT(on_out))
        bus = RasterBus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = Call(*(regs[REG_FIELDS[name]] for name in CORE_NAMES))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for name in CORE_NAMES:
                setattr(state, REG_FIELDS[name], getattr(result, name))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory), regs={name: getattr(state, name)
                                                for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status, continuation=state.ip)


def expected_status(case, expected):
    if expected['continuation'] == 0x715B and expected['status'] == 1:
        return 1
    if expected['status'] == 2:
        return 2
    return 0


def callback_probe_summary(probe):
    addresses = {off for scope, off in probe['sites'] if scope == 'main'}
    edges = {(src, dst) for scope, src, dst in probe['edges'] if scope == 'main'}
    return dict(status=probe['status'], continuation=probe['continuation'],
                instruction_steps=probe['steps'], ordered_events=len(probe['events']),
                integrated_addresses=sorted(addresses),
                parent_addresses=sorted(addresses & OWN_SITES),
                integrated_edges=sorted([src, dst] for src, dst in edges),
                parent_edges=sorted([src, dst] for src, dst in edges if src in OWN_SITES))


def empty_probe_metrics():
    return dict(pass_count=0, instruction_steps=0, ordered_events=0,
                integrated_site_observations=0, parent_site_observations=0,
                integrated_edge_observations=0, parent_edge_observations=0,
                integrated_addresses=set(), parent_addresses=set(),
                integrated_edges=set(), parent_edges=set(), boundary_counts={})


def accumulate_probe_metrics(metrics, summary):
    metrics['pass_count'] += 1
    metrics['instruction_steps'] += summary['instruction_steps']
    metrics['ordered_events'] += summary['ordered_events']
    metrics['integrated_site_observations'] += len(summary['integrated_addresses'])
    metrics['parent_site_observations'] += len(summary['parent_addresses'])
    metrics['integrated_edge_observations'] += len(summary['integrated_edges'])
    metrics['parent_edge_observations'] += len(summary['parent_edges'])
    metrics['integrated_addresses'].update(summary['integrated_addresses'])
    metrics['parent_addresses'].update(summary['parent_addresses'])
    metrics['integrated_edges'].update(tuple(edge) for edge in summary['integrated_edges'])
    metrics['parent_edges'].update(tuple(edge) for edge in summary['parent_edges'])
    boundary = f"{summary['status']}:{summary['continuation']:04X}"
    metrics['boundary_counts'][boundary] = metrics['boundary_counts'].get(boundary, 0) + 1


def serialized_probe_metrics(metrics):
    return dict(pass_count=metrics['pass_count'],
                instruction_steps=metrics['instruction_steps'],
                ordered_events=metrics['ordered_events'],
                integrated_site_observations=metrics['integrated_site_observations'],
                parent_site_observations=metrics['parent_site_observations'],
                integrated_edge_observations=metrics['integrated_edge_observations'],
                parent_edge_observations=metrics['parent_edge_observations'],
                integrated_executed_instruction_addresses=sorted(metrics['integrated_addresses']),
                parent_executed_instruction_addresses=sorted(metrics['parent_addresses']),
                integrated_branch_edges=[list(edge) for edge in sorted(metrics['integrated_edges'])],
                parent_branch_edges=[list(edge) for edge in sorted(metrics['parent_edges'])],
                boundary_counts=dict(sorted(metrics['boundary_counts'].items())))


def compare_case(native, case, *, core, producers, accounting=None):
    initial_memory, initial_regs, initial_device, producer, selected_bank = setup(case, producers)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    projection = independent_projection(case, initial_memory)
    expected = original(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core)
    probe_summary = callback_probe_summary(expected['callback_probe'])
    if accounting is not None:
        accumulate_probe_metrics(accounting['probe_metrics'], probe_summary)
    status = expected_status(case, expected)
    projection_checked = False
    oracle_require(expected['status'] == status,
                   f'{label}: original status {expected["status"]}, expected {status}')
    if expected['status'] == 1:
        oracle_require(expected['continuation'] == 0x715B and
                       expected['callback_probe']['regs']['ax'] not in CALLBACKS.values(),
                       label + ': unknown target did not stop before CALL/push')
    else:
        if projection['visible']:
            probe = expected['callback_probe']
            if probe['status'] == 3:
                oracle_require(probe['continuation'] == 0x715B,
                               label + ': callback probe missed 715B')
                target = probe['regs']['ax']
                if target in CALLBACKS.values():
                    oracle_require(('main', target) in expected['sites'] or
                                   expected['status'] == 2,
                                   label + ': selected child entry did not execute')
                if not case.get('provider') and case['selector'] == 0:
                    assert_parent_projection(label, probe, projection, regs=initial_regs)
                    projection_checked = True
    if accounting is not None and projection_checked:
        accounting['projection_check_count'] += 1
    expected_providers = set(expected['used'])
    if case.get('provider'):
        oracle_require(expected_providers == PROVIDER_LABELS[case['provider']],
                       label + f': provider transitions {expected_providers} differ from '
                       f'{PROVIDER_LABELS[case["provider"]]}')
    if producer is not None:
        descriptor, bank = selected_bank
        start = physical(producer.destination_segment,
                         producer.destination_offset + descriptor.output_offset)
        oracle_require(expected['memory'][start:start + len(bank)] == bank,
                       label + ': original consumer modified producer bytes')

    actual = native.run(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core)
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    compare_regs(label, actual['regs'], expected['regs'], expected['flag_mask'], Mismatch)
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    compare_events(label, actual['events'], expected['events'], Mismatch)
    require(actual['used'] == expected['used'], label + ': provider use differs')
    compare_devices(label, actual['device'], expected['device'], Mismatch)
    if producer is not None:
        descriptor, bank = selected_bank
        start = physical(producer.destination_segment,
                         producer.destination_offset + descriptor.output_offset)
        require(actual['memory'][start:start + len(bank)] == bank,
                label + ': native consumer modified producer bytes')
    return dict(name=case['name'], boundary='core' if core else 'adapter',
                status=expected['status'], continuation=expected['continuation'],
                own_sites=sorted(off for scope, off in expected['sites']
                                 if scope == 'main' and off in OWN_SITES),
                own_edges=sorted([src, dst] for scope, src, dst in expected['edges']
                                 if scope == 'main' and src in OWN_SITES),
                integrated_addresses=sorted(off for scope, off in expected['sites']
                                            if scope == 'main'),
                integrated_edges=sorted([src, dst] for scope, src, dst in expected['edges']
                                        if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                callback_probe=probe_summary,
                independent_projection_checked=projection_checked,
                providers=sorted(expected['used']),
                producer_bank=(None if selected_bank is None else
                               dict(name=case['producer'][0], index=case['producer'][1],
                                    sha256=sha(selected_bank[1]))),
                projection=projection)


def static_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.lower() in (
                'loop', 'loope', 'loopne', 'jcxz'):
            if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
                edges.add((address, (address + ins.size) & 0xFFFF))
            if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
                edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/entity-display.md', 'docs/entity-vga.md', 'docs/entity-sprites.md',
        'docs/entity-sprite-dispatch.md', 'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat', 'metadata/oracle.json',
        'metadata/inputs.json', 'metadata/symbols.json', 'metadata/regions.json',
        'metadata/hints.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/adlib-regions.json',
        'metadata/adlib-symbols.json', 'metadata/adlib-encodings.json',
        'metadata/tandysnd-regions.json', 'metadata/tandysnd-symbols.json',
        'metadata/tandysnd-encodings.json', 'src/program.asm', 'src/game_code.asm',
        'src/entity_sprite_dispatch.asm', 'src/entity_sprite_aligned.asm',
        'src/entity_graphics.asm', 'src/entity_sprite_planes.asm',
        'src/entity_sprite_shifted.asm', 'src/entity_sprite_wide.asm',
        'src/entity_sprite_four_planes.asm', 'src/entity_strip.asm',
        'src/game_code_late_after_palette.asm', 'src/entry_services.asm',
        'src/image_tail.asm', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_sprite_dispatch.c',
        'c/entity_sprite_dispatch.h', 'c/entity_sprite_aligned.c',
        'c/entity_sprite_aligned.h', 'c/entity_sprite_shifted.c',
        'c/entity_sprite_shifted.h', 'c/entity_sprite_wide.c',
        'c/entity_sprite_wide.h', 'c/entity_strip.c', 'c/entity_strip.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/entity_sprite_dispatch.py', 'tests/entity_interactions.py',
        'tests/entity_sprite_layout.py', 'tests/entity_sprite_aligned.py',
        'tests/entity_sprite_shifted.py', 'tests/entity_sprite_planes.py',
        'tests/entity_sprite_wide.py', 'tests/entity_strip.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/minimap_vga.py', 'tools/resources.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/unpack.py',
        'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [name for name in paths if not (ROOT / name).is_file()]
    oracle_require(not missing, 'missing dispatch hash inputs: ' + ', '.join(missing))
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def original_campaign(cases, producers, before):
    oracle_require(before == input_hashes(), 'dispatch inputs changed before preflight')
    rows, own_sites, own_edges = [], set(), set()
    integrated_sites, integrated_edges = set(), set()
    probe_metrics = empty_probe_metrics()
    projection_check_count = 0
    event_total = step_total = 0
    for case in cases:
        memory, regs, device, producer, selected_bank = setup(case, producers)
        for core in (True, False):
            expected = original(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), core=core)
            probe_summary = callback_probe_summary(expected['callback_probe'])
            accumulate_probe_metrics(probe_metrics, probe_summary)
            status = expected_status(case, expected)
            label = f'{case["name"]} {"core" if core else "adapter"}'
            oracle_require(expected['status'] == status,
                           f'{label}: status {expected["status"]}, expected {status}')
            if case['name'] == 'physical-stack-word-wrap':
                oracle_require(expected['status'] == 2 and
                               expected['continuation'] == 0x0100,
                               label + ': expected changed child RET at 0100')
            if case['name'] == 'physical-outer-ret-word-wrap' and not core:
                return_address = physical(regs['ss'], regs['sp'])
                oracle_require(return_address == 0xFFFFF and
                               memory[0xFFFFF] == (case['outer_return'] & 0xFF) and
                               memory[0] == ((case['outer_return'] >> 8) & 0xFF),
                               label + ': outer RET fixture does not cross FFFFF->00000')
                oracle_require(expected['status'] == 0 and
                               expected['regs']['ip'] == case['outer_return'] and
                               expected['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
                               label + ': outer RET did not consume the wrapped live word')
            projection = independent_projection(case, memory)
            projection_checked = False
            if projection['visible'] and expected['callback_probe']['status'] == 3:
                probe = expected['callback_probe']
                if not case.get('provider') and case['selector'] == 0:
                    assert_parent_projection(label, probe, projection, regs=regs)
                    projection_checked = True
                    projection_check_count += 1
            if case.get('provider'):
                oracle_require(set(expected['used']) == PROVIDER_LABELS[case['provider']],
                               label + ': provider phase/use did not match contract')
            found_sites = {off for scope, off in expected['sites']
                           if scope == 'main' and off in OWN_SITES}
            found_edges = {(src, dst) for scope, src, dst in expected['edges']
                           if scope == 'main' and src in OWN_SITES}
            own_sites.update(found_sites)
            own_edges.update(found_edges)
            integrated_sites.update(off for scope, off in expected['sites']
                                    if scope == 'main')
            integrated_edges.update((src, dst) for scope, src, dst in expected['edges']
                                    if scope == 'main')
            event_total += len(expected['events'])
            step_total += expected['steps']
            rows.append(dict(name=case['name'], boundary='core' if core else 'adapter',
                             status=expected['status'], continuation=expected['continuation'],
                             own_sites=sorted(found_sites), own_edges=[list(x) for x in sorted(found_edges)],
                             integrated_addresses=sorted(off for scope, off in expected['sites']
                                                         if scope == 'main'),
                             integrated_edges=sorted([src, dst]
                                                     for scope, src, dst in expected['edges']
                                                     if scope == 'main'),
                             events=len(expected['events']),
                             steps=expected['steps'], providers=sorted(expected['used']),
                             callback_probe=probe_summary,
                             independent_projection_checked=projection_checked,
                             projection=projection))
        del memory, regs, device
        gc.collect()
    oracle_require(own_sites == OWN_SITES,
                   f'parent site union mismatch: missing={sorted(OWN_SITES-own_sites)}')
    oracle_require(own_edges == static_edges(),
                   f'parent edge union mismatch: expected={sorted(static_edges())}, got={sorted(own_edges)}')
    oracle_require(before == input_hashes(), 'dispatch inputs changed during preflight')
    return (rows, own_sites, own_edges, integrated_sites, integrated_edges,
            event_total, step_total, serialized_probe_metrics(probe_metrics),
            projection_check_count)


def producer_evidence(witness):
    return dict(entry=witness.entry, dx=witness.dx, output_bytes=len(witness.output_bytes),
                bank_count=len(witness.banks), sites=sorted(witness.sites),
                branch_edges=[list(e) for e in sorted(witness.edges)],
                steps=witness.steps, memory_events=witness.event_count,
                bank_sha256=[sha(witness.bank(i)) for i in range(len(witness.banks))],
                scope='one bounded original producer run, separate from parent/child native totals')


def run_original_only():
    before = input_hashes()
    producers = {
        '5b11': sprite_layout.produce_5b11(),
        '5bb0': sprite_layout.produce_5bb0(0x030D, 0xD15A13),
        '5c06': sprite_layout.produce_5c06(),
    }
    fixture_rows = make_cases()
    (rows, sites, edges, integrated, integrated_branch_edges, events, steps,
     prefix_probe_metrics, projection_check_count) = original_campaign(
        fixture_rows, producers, before)
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(fixture_rows),
                  mutation_count=0, input_hashes=before,
                  translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
                  executed_instruction_addresses=sorted(integrated),
                  parent_executed_instruction_addresses=sorted(sites),
                  integrated_code_bytes=CODE_BYTES + sum(ins.size for ins in INTEGRATED_INS.values()),
                  integrated_instruction_sites=len(MAIN_INS),
                  static_instruction_addresses=sorted(OWN_SITES),
                  branch_edge_count=len(edges), branch_edges=[list(e) for e in sorted(edges)],
                  integrated_branch_edge_count=len(integrated_branch_edges),
                  integrated_branch_edges=[list(e) for e in sorted(integrated_branch_edges)],
                  original_only=True, rows=rows, ordered_events=events,
                  instruction_steps=steps,
                  original_prefix_probe_metrics=prefix_probe_metrics,
                  independent_projection_check_count=projection_check_count,
                  accounting_notes=[
                      'Each row includes one bounded original-only callback-target probe '
                      'before the selected original path.',
                      'Probe steps, events, sites, and edges are reported separately and '
                      'excluded from ordered_events and instruction_steps.',
                      'Independent projection checks count only probes that reached the '
                      '715B pre-CALL boundary.'
                  ],
                  producer_evidence={name: producer_evidence(w)
                                     for name, w in producers.items()})
    write_json(ORIGINAL_REPORT, report)
    print(f'PASS original dispatch: {len(fixture_rows)} fixtures x2, '
          f'{len(sites)} parent sites/{len(edges)} edges, {events} events', flush=True)
    return report


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'dispatch input snapshot differs before native build')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned main image hash changed')
    oracle_require(len(OWN_SITES) == 113 and CODE_BYTES == 240,
                   f'parent static inventory changed: {len(OWN_SITES)} sites/{CODE_BYTES} bytes')
    oracle_require(len(MAIN_INS) == len(INTEGRATED_INS) + len(OWN_INS),
                   'main parent/child instruction maps overlap unexpectedly')
    producers = {'5b11': sprite_layout.produce_5b11(),
                 '5bb0': sprite_layout.produce_5bb0(0x030D, 0xD15A13),
                 '5c06': sprite_layout.produce_5c06()}
    fixture_rows = make_cases()
    # First run every original boundary, so fixture/oracle failures cannot be
    # mistaken for a completed native mutant mismatch.
    (original_rows, original_sites, original_edges, original_integrated_sites,
     original_integrated_edges, total_events, total_steps, original_probe_metrics,
     original_projection_checks) = \
        original_campaign(fixture_rows, producers, before)
    rows, native_sites, native_edges = [], set(), set()
    integrated_sites, integrated_edges = set(), set()
    native_accounting = dict(probe_metrics=empty_probe_metrics(),
                             projection_check_count=0)
    mutation_accounting = dict(probe_metrics=empty_probe_metrics(),
                               projection_check_count=0)
    completed_mutants = []
    mutation_witness_rows = []
    total_native_events = 0
    # The baseline completes the full fixture matrix at both C boundaries.
    baseline = Native(directory, 0)
    try:
        for case in fixture_rows:
            for core in (True, False):
                row = compare_case(baseline, case, core=core, producers=producers,
                                   accounting=native_accounting)
                rows.append(row)
                native_sites.update(row['own_sites'])
                native_edges.update(tuple(x) for x in row['own_edges'])
                integrated_sites.update(row['integrated_addresses'])
                integrated_edges.update(tuple(x) for x in row['integrated_edges'])
                total_native_events += row['events']
    finally:
        del baseline
        gc.collect()

    # Every finite mutant gets its own reviewed witness. A passing witness is a
    # surviving mutant and fails the campaign; only a completed mismatch counts.
    witnesses = {
        1: ('visibility-zero-skips', True),
        2: ('optional-strip-normal', True),
        3: ('strip-uses-live-callback-word', True),
        4: ('optional-strip-normal', True),
        5: ('visibility-index-is-shifted-three-times', True),
        6: ('callback-shift12', True),
        7: ('final-pop-di-uses-live-saved-word', True),
        8: ('changed-strip-return-stops-before-restores', True),
        9: ('strip-uses-live-saved-ds', True),
        10: ('callback-aligned', False),
    }
    by_name = {case['name']: case for case in fixture_rows}
    for mutation, (name, core) in witnesses.items():
        native = Native(directory, mutation)
        try:
            compare_case(native, by_name[name], core=core, producers=producers,
                         accounting=mutation_accounting)
        except Mismatch as exc:
            completed_mutants.append(mutation)
            mutation_witness_rows.append(dict(mutation=mutation, case=name,
                                              boundary='core' if core else 'adapter',
                                              completed=True, mismatch=str(exc)))
        else:
            raise OracleFailure(
                f'mutation {mutation} survived its completed witness {name}/'
                f'{"core" if core else "adapter"}')
        finally:
            del native
            gc.collect()
    oracle_require(native_sites == OWN_SITES and native_edges == static_edges(),
                   'baseline native parent coverage differs from original inventory')
    oracle_require(integrated_sites == original_integrated_sites and
                   integrated_edges == original_integrated_edges,
                   'baseline native integrated coverage differs from original')
    oracle_require(completed_mutants == list(range(1, 11)),
                   f'completed mutation witnesses differ: {completed_mutants}')
    after = input_hashes()
    oracle_require(before == after, 'dispatch test inputs changed during native campaign')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(fixture_rows),
                  comparison_count=2 * len(fixture_rows), mutation_count=len(completed_mutants),
                  mutation_comparison_count=len(witnesses),
                  completed_mutations=completed_mutants,
                  mutation_witnesses=mutation_witness_rows, input_hashes=before,
                  translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
                  executed_instruction_addresses=sorted(integrated_sites),
                  parent_executed_instruction_addresses=sorted(native_sites),
                  integrated_code_bytes=CODE_BYTES + sum(ins.size for ins in INTEGRATED_INS.values()),
                  integrated_instruction_sites=len(MAIN_INS),
                  static_instruction_addresses=sorted(OWN_SITES),
                  branch_edge_count=len(native_edges), branch_edges=[list(e) for e in sorted(native_edges)],
                  integrated_branch_edge_count=len(integrated_edges),
                  integrated_branch_edges=[list(e) for e in sorted(integrated_edges)],
                  ordered_events=total_native_events, original_ordered_events=total_events,
                  original_instruction_steps=total_steps,
                  original_prefix_probe_metrics=original_probe_metrics,
                  original_only_independent_projection_check_count=original_projection_checks,
                  native_comparison_prefix_probe_metrics=serialized_probe_metrics(
                      native_accounting['probe_metrics']),
                  native_comparison_independent_projection_check_count=(
                      native_accounting['projection_check_count']),
                  mutation_witness_prefix_probe_metrics=serialized_probe_metrics(
                      mutation_accounting['probe_metrics']),
                  mutation_witness_independent_projection_check_count=(
                      mutation_accounting['projection_check_count']),
                  accounting_notes=[
                      'ordered_events counts native events compared against selected original '
                      'paths; original_ordered_events counts selected original paths.',
                      'The callback-target probes are additional bounded original-only passes '
                      'and are reported separately from both selected-path event totals. '
                      'Mutation-witness oracle probes have their own metric.',
                      'Independent projection counts refer to checks at the parent 715B '
                      'pre-CALL boundary.'
                  ],
                  integrated_instruction_addresses=sorted(integrated_sites), rows=rows,
                  producer_evidence={name: producer_evidence(w) for name, w in producers.items()})
    write_json(REPORT, report)
    oracle_require(input_hashes() == before, 'hash changed before report publication')
    print(f'PASS entity sprite dispatch: {len(fixture_rows)} cases, '
          f'{len(native_sites)} sites/{len(native_edges)} edges, '
          f'{len(completed_mutants)} mutants', flush=True)


def main():
    args = sys.argv[1:]
    if args == ['--original-only']:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=360, memory_mib=384, check=True)
        return
    if args and args[0] == '--original-worker':
        run_original_only()
        return
    if len(args) == 3 and args[0] == '--worker':
        worker(args[1], args[2])
        return
    if not args:
        REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-sprite-dispatch', parent=BUILD) as directory:
            hash_path = Path(directory) / 'entity-sprite-dispatch-inputs.json'
            hash_path.write_text(json.dumps(input_hashes(), sort_keys=True), encoding='utf-8')
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                         str(directory), str(hash_path)],
                        cwd=ROOT, timeout=420, memory_mib=384, check=True)
        return
    raise SystemExit('usage: entity_sprite_dispatch.py [--original-only]')


if __name__ == '__main__':
    main()
