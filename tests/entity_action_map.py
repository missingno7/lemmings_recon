"""Bounded original-versus-native checks for selector 5's map producer."""
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
from common import BUILD, sha, write_json
import entity_actions_basic as basic
import entity_action_sound as feedback
import entity_interactions as interactions
import entity_pattern_bus as pattern_bus
from cbuild import build
from minimap_vga import MinimapVga, VGA_BASE, VGA_END

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END = 0x3336, 0x34CE
RECORD_BYTES, ROW_PITCH = 0x2D, 0x1A0
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
INSTRUCTION_LIMIT, EVENT_LIMIT = 768, 8192
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-action-map-differential.json'
IMAGE = interactions.IMAGE

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_EDGES = set()
for address, ins in OWN_INS.items():
    if ins.group(capstone.CS_GRP_JUMP):
        OWN_EDGES.add((address, ins.operands[0].imm & 0xFFFF))
        if ins.mnemonic.lower() != 'jmp':
            OWN_EDGES.add((address, (address + ins.size) & 0xFFFF))
CONDITIONALS = {address for address, ins in OWN_INS.items()
                if ins.group(capstone.CS_GRP_JUMP) and
                ins.mnemonic.lower() != 'jmp'}
MAIN_INS = dict(basic.MAIN_INS)
MAIN_INS.update(OWN_INS)
CORE_STOPS = {0x320B: 0, 0x320C: 0, 0x329A: 0}
MAP_BYTES = END - ENTRY
MAP_SITES = len(OWN_INS)

assert MAP_BYTES == 408
assert MAP_SITES == 158
assert len(OWN_EDGES) == 73


def put8(memory, segment, offset, value):
    memory[interactions.physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = interactions.physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get8(memory, segment, offset):
    return memory[interactions.physical(segment, offset)]


def get16(memory, segment, offset):
    address = interactions.physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def map_offset(memory, regs):
    x = get16(memory, regs['ds'], regs['si'])
    y = get16(memory, regs['ds'], (regs['si'] + 2) & 0xFFFF)
    xq = ((x - 4) & 0xFFFF) >> 2
    yq = ((y - 6 - 0x10) & 0xFFFF) >> 2
    return (xq + yq * ROW_PITCH + 0x12) & 0xFFFF


def cell_offsets(base):
    return tuple((base + row * ROW_PITCH + column) & 0xFFFF
                 for row in range(3) for column in range(3))


class MapCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('entry', 'value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class MapResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status')]


class MapAccess(basic.BasicAccess):
    event_limit = EVENT_LIMIT

    def __init__(self, case, memory, regs, device, *, defer_providers=False):
        super().__init__(case, memory, regs, device,
                         defer_providers=defer_providers)
        self.map_base = case.get('map_base_override')
        if self.map_base is None:
            self.map_base = map_offset(memory, regs)
        self.write_occurrences = {}

    def _word_effect(self, segment, offset, value):
        low = interactions.physical(segment, offset)
        self._apply_or_defer(low, value)
        self._apply_or_defer((low + 1) & MASK, value >> 8)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        result = super().access(kind, address, flags, mask, value)
        provider = self.case.get('provider')
        ss, sp = self.case.get('ss', self.regs['ss']), self.case.get('sp', self.regs['sp'])
        if kind == 'write':
            count = self.write_occurrences.get(address, 0) + 1
            self.write_occurrences[address] = count
            if (provider == 'live-pop-dx' and 'map-dx' not in self.used and
                    address == interactions.physical(ss, sp - 3)):
                self._word_effect(ss, (sp - 4) & 0xFFFF,
                                  self.case.get('provider_word', 0xA6D2))
                self.used.add('map-dx')
            elif (provider == 'live-pop-bx' and 'map-bx' not in self.used and
                  address == interactions.physical(ss, sp - 1)):
                self._word_effect(ss, (sp - 2) & 0xFFFF,
                                  self.case.get('provider_word', 0x0018))
                self.used.add('map-bx')
            elif (provider == 'live-pop-es' and 'map-es' not in self.used and
                  address == interactions.physical(ss, sp - 3) and count >= 2):
                self._word_effect(ss, (sp - 4) & 0xFFFF,
                                  self.case.get('provider_word', 0x6200))
                self.used.add('map-es')
        elif (provider == 'late-map-cell' and 'map-late' not in self.used and
              address == interactions.physical(ss, self.map_base + 1)):
            target = (self.map_base + ROW_PITCH) & 0xFFFF
            self._apply_or_defer(interactions.physical(ss, target), 0x02)
            self.used.add('map-late')
        elif (provider == 'late-callback' and 'map-callback' not in self.used and
              kind == 'read' and address == interactions.physical(
                  ss, self.map_base + 0x342)):
            self._word_effect(self.case.get('ds', self.regs['ds']), 0x2E,
                              self.case.get('provider_callback', 0xD35A))
            self.used.add('map-callback')
        elif (provider == 'late-producer-cell' and
              'map-producer-cell' not in self.used and kind == 'read' and
              address == interactions.physical(
                  self.case.get('ds', self.regs['ds']), 0x2E)):
            self._apply_or_defer(interactions.physical(ss, self.map_base), 0x99)
            self.used.add('map-producer-cell')
        return result


def setup(case):
    memory, regs, _device, pc_binding, sound_binding, _ = interactions.setup(
        dict(case, vga=False))
    regs['ip'] = ENTRY
    ds, ss, si = regs['ds'], regs['ss'], regs['si']
    if 'si' in case:
        regs['si'] = si = case['si'] & 0xFFFF
    if 'ds' in case:
        regs['ds'] = ds = case['ds'] & 0xFFFF
    if 'ss' in case:
        regs['ss'] = ss = case['ss'] & 0xFFFF
    if 'sp' in case:
        regs['sp'] = case['sp'] & 0xFFFF
    put16(memory, ds, si, case.get('x', 4))
    put16(memory, ds, si + 2, case.get('y', 0x16))
    put16(memory, ds, si + 8, case.get('record_bits', 0))
    put8(memory, ds, si + 0x24, case.get('record_flag24', 0xA5))
    put8(memory, ds, 0x73, case.get('count', 2))
    put8(memory, ds, 0x75, case.get('refresh', 0x59))
    put16(memory, ds, 0x2E, case.get('callback', 0x6B4D))

    base = map_offset(memory, regs)
    values = list(case.get('map_values', (0x41, 0x42, 0x43,
                                          0x44, 0x45, 0x46,
                                          0x47, 0x48, 0x49)))
    if len(values) != 9:
        raise AssertionError(case['name'] + ': map_values must contain nine bytes')
    if 'reject_cell' in case:
        values[case['reject_cell']] = case.get('reject_value', 0x02)

    device = None
    if case.get('vga_map'):
        device = MinimapVga(0x3336 ^ case.get('seed', 0), read_map=0)
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[2] = device.gc[3] = 0
        device.gc[4] = 0
        device.gc[5] = 0
        device.gc[6] = 0x05
        device.gc[7] = 0
        device.gc[8] = 0xFF
        if ss != 0xA000:
            raise AssertionError(case['name'] + ': VGA map requires SS=A000')
    for index, offset in enumerate(cell_offsets(base)):
        address = interactions.physical(ss, offset)
        memory[address] = values[index] & 0xFF
        if device is not None and VGA_BASE <= address < VGA_END:
            device.planes[0][address - VGA_BASE] = values[index] & 0xFF

    if 'wrong_y_cell' in case:
        x = get16(memory, ds, si)
        y = get16(memory, ds, (si + 2) & 0xFFFF)
        xq = ((x - 4) & 0xFFFF) >> 2
        wrong_yq = ((y - 6 - 0x0E) & 0xFFFF) >> 2
        wrong_base = (xq + wrong_yq * ROW_PITCH + 0x12) & 0xFFFF
        wrong_values = [0x51, 0x52, 0x53, 0x54, 0x55,
                        0x56, 0x57, 0x58, 0x59]
        wrong_values[case['wrong_y_cell']] = case.get('wrong_y_value', 0x02)
        for index, offset in enumerate(cell_offsets(wrong_base)):
            put8(memory, ss, offset, wrong_values[index])

    if case.get('alt_map_values') is not None:
        alt_base = case.get('alt_map_base', 0x2A)
        for index, offset in enumerate(cell_offsets(alt_base)):
            put8(memory, ss, offset, case['alt_map_values'][index])

    if device is not None:
        # Keep a live outer return word in the selected VGA read plane.
        address = interactions.physical(ss, regs['sp'])
        if VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            ret = case.get('outer_return', interactions.OUTER_RETURN)
            device.planes[0][offset] = ret & 0xFF
            device.planes[0][(offset + 1) & 0xFFFF] = (ret >> 8) & 0xFF
    return memory, regs, device, pc_binding, sound_binding


def original(case, memory, regs, device, *, core):
    regs['ip'] = ENTRY
    factory = lambda c, m, r, d: MapAccess(
        c, m, r, d, defer_providers=True)
    return interactions.original(
        case, memory, regs, device, core,
        entry_flag_mask=FLAGS,
        main_instructions=MAIN_INS,
        stop_offsets=CORE_STOPS if core else None,
        access_factory=factory,
        instruction_limit=INSTRUCTION_LIMIT)


def make_case(name, **kwargs):
    return dict(name=name, selector=5, flags=kwargs.pop('flags', 0x02D7),
                **kwargs)


def cases():
    rows = [
        make_case('map-success', count=2, record_bits=0),
        make_case('map-count-zero', count=0, record_bits=0),
        make_case('map-state-mask-reject', count=2, record_bits=0x0001),
        make_case('map-state-mask-ignored-bit10', count=2,
                  record_bits=0x0010),
        make_case('map-count-wrap', count=1, record_bits=0,
                  refresh=0xA7, record_flag24=0xFF),
    ]
    for cell in range(9):
        for value in (0x02, 0x0A, 0x03):
            rows.append(make_case(f'map-reject-cell-{cell}-{value:02x}',
                                  count=2, record_bits=0,
                                  reject_cell=cell, reject_value=value))
    rows.extend([
        make_case('map-y-subtract-boundary', count=2, record_bits=0,
                  x=4, y=0x20, wrong_y_cell=6),
        make_case('map-live-pop-dx', count=2, record_bits=0,
                  provider='live-pop-dx', provider_word=0xB6D2, dx=0xA5C3),
        make_case('map-live-pop-bx', count=2, record_bits=0,
                  provider='live-pop-bx', provider_word=0x0018,
                  reject_cell=0, reject_value=0x02,
                  alt_map_values=(0x51, 0x52, 0x53, 0x54, 0x55,
                                  0x56, 0x57, 0x58, 0x59)),
        make_case('map-live-probe-reread', count=2, record_bits=0,
                  provider='late-map-cell'),
        make_case('map-live-callback-read', count=2, record_bits=0,
                  provider='late-callback', provider_callback=0xD35A),
        make_case('map-late-producer-cell', count=2, record_bits=0,
                  provider='late-producer-cell'),
        make_case('map-decrement-callback-flags', count=0x80, record_bits=0,
                  flags=0x0ED7),
        make_case('map-and-callback-flags', count=2, record_bits=0,
                  record_flag24=0x00, flags=0x02D7),
        make_case('map-df-set', count=2, record_bits=0,
                  flags=0x04D7),
        make_case('map-live-pop-es', count=2, record_bits=0,
                  provider='live-pop-es', provider_word=0x6200),
        make_case('map-record-map-alias', count=2, record_bits=0,
                  ds=0x5000, ss=0x5000, si=0xFFFC),
        make_case('map-stack-cell-alias', count=2, record_bits=0,
                  ss=0x5000, sp=0x0016),
        make_case('map-physical-word-wrap', count=2, record_bits=0,
                  ss=0xFFFF, x=0x0678, y=0x0012),
        make_case('map-vga-ss-bank', count=2, record_bits=0,
                  ss=0xA000, sp=0x0800, vga_map=True),
        make_case('map-feedback-pc', count=2, record_bits=0,
                  enabled=0, options=1),
        make_case('map-feedback-pc-returned-ds', count=2, record_bits=0,
                  enabled=0, options=1, provider='pc-registers',
                  provider_ds=0x6200, provider_enabled=0xFF,
                  provider_options=3, provider_si=0x4012,
                  provider_cx=0x1357),
        make_case('map-feedback-pc-unbound', count=2, record_bits=0,
                  enabled=0, options=1, pc_vector=(0x0182, 0x6200)),
        make_case('map-feedback-pc-changed-iret', count=2, record_bits=0,
                  enabled=0, options=1, provider='pc-interrupt-return',
                  provider_return=0x329A),
        make_case('map-feedback-adlib', count=2, record_bits=0,
                  enabled=0xFF, options=3, driver='adlib'),
        make_case('map-feedback-tandy', count=2, record_bits=0,
                  enabled=0xFF, options=3, driver='tandysnd'),
        make_case('map-feedback-sound-unbound', count=2, record_bits=0,
                  enabled=0xFF, options=3, sound_vector=(0, 0x6200)),
        make_case('map-feedback-sound-changed-iret', count=2, record_bits=0,
                  enabled=0xFF, options=3, provider='sound-interrupt-return',
                  provider_return=0x31F8),
        make_case('map-outer-stack-wrap', count=2, record_bits=0,
                  ss=0xFFFF, sp=0x000F, outer_return=0xBEEF),
        make_case('map-nonzero-code-segment', count=2, record_bits=0,
                  load=0x1213),
    ])
    return rows


def independent_producer(case, initial_memory, initial_regs):
    """Ordered independent memory projection for selector-5's own writes.

    The model deliberately performs the record writes, source reads, map writes,
    and STOSB saves one at a time. This matters for DS=SS/map overlap and for a
    map cell that aliases the live PUSH SI slot.
    """
    memory = bytearray(initial_memory)
    changed = set()

    def wr8(segment, offset, value):
        address = interactions.physical(segment, offset)
        memory[address] = value & 0xFF
        changed.add(address)

    def wr16(segment, offset, value):
        address = interactions.physical(segment, offset)
        memory[address] = value & 0xFF
        memory[(address + 1) & MASK] = (value >> 8) & 0xFF
        changed.update((address, (address + 1) & MASK))

    def rd8(segment, offset):
        return memory[interactions.physical(segment, offset)]

    def rd16(segment, offset):
        address = interactions.physical(segment, offset)
        return memory[address] | (memory[(address + 1) & MASK] << 8)

    ds, ss = initial_regs['ds'], initial_regs['ss']
    si0, sp0 = initial_regs['si'], initial_regs['sp']
    # Count and eligibility are read before coordinate calculation.
    if rd8(ds, 0x73) == 0 or (rd16(ds, si0 + 8) & 0xF56F) != 0:
        return dict(memory=memory, changed=changed, eligible=False,
                    candidate=None, rejected=None, saved_es=None,
                    returned_si=si0)

    x = rd16(ds, si0)
    y = rd16(ds, (si0 + 2) & 0xFFFF)
    xq = ((x - 4) & 0xFFFF) >> 2
    yq = ((y - 6 - 0x10) & 0xFFFF) >> 2

    # PUSH AX; PUSH DX; MUL; POP DX; POP BX are live stack accesses. The
    # multiply result is the low word of Yq*01A0h, and BX is the saved Xq.
    wr16(ss, sp0 - 2, xq)
    wr16(ss, sp0 - 4, initial_regs['dx'])
    live_dx = rd16(ss, (sp0 - 4) & 0xFFFF)
    del live_dx  # Restored DX is observable in registers, not the map address.
    live_xq = rd16(ss, (sp0 - 2) & 0xFFFF)
    base = (live_xq + ((yq * ROW_PITCH) & 0xFFFF) + 0x12) & 0xFFFF

    rejected = None
    tokens = (0x02, 0x0A, 0x03)
    probe_positions = (0, 1, 2, 3, 4, 5, 6, 7, 8)
    for index in probe_positions:
        off = (base + (index // 3) * ROW_PITCH + (index % 3)) & 0xFFFF
        value = rd8(ss, off)
        if value in tokens:
            rejected = (index, value)
            break
    if rejected is not None:
        return dict(memory=memory, changed=changed, eligible=True,
                    candidate=base, rejected=rejected, saved_es=None,
                    returned_si=si0)

    # DEC global count and all transition stores retain their physical write
    # order, so overlapping fields naturally affect later reads and saves.
    wr8(ds, 0x73, (rd8(ds, 0x73) - 1) & 0xFF)
    wr8(ds, 0x75, 0)
    wr16(ds, si0 + 8, 0x0100)
    wr8(ds, si0 + 0x28, 0)
    wr16(ds, si0 + 0x0A, 0x0008)
    wr16(ds, si0 + 0x0C, 0x0F9B)
    wr16(ds, si0 + 0x10, 0x005A)
    wr16(ds, si0 + 0x12, 0x003C)
    wr8(ds, si0 + 0x29, 0)
    wr16(ds, si0 + 0x04, 0xFFF8)
    wr16(ds, si0 + 0x06, 0xFFF6)
    callback = rd16(ds, 0x2E)
    wr16(ds, si0 + 0x14, callback)
    wr8(ds, si0 + 0x2A, 0)
    wr8(ds, si0 + 0x24, rd8(ds, si0 + 0x24) & 1)

    # PUSH SI; PUSH DS; POP ES use a live SS word. Destination save DI starts
    # at SI+16h and STOSB follows DF; the source SI advances forward explicitly.
    wr16(ss, sp0 - 2, si0)
    wr16(ss, sp0 - 4, ds)
    saved_es = rd16(ss, (sp0 - 4) & 0xFFFF)
    df = bool(initial_regs['flags'] & 0x0400)
    source = base
    dest = (si0 + 0x16) & 0xFFFF
    for index, token in enumerate((0x02, 0x0A, 0x03) * 3):
        old = rd8(ss, source)
        wr8(ss, source, token)
        wr8(saved_es, dest, old)
        dest = (dest - 1 if df else dest + 1) & 0xFFFF
        source = (source + 1) & 0xFFFF
        if index in (2, 5):
            source = (source + 0x019D) & 0xFFFF
    returned_si = rd16(ss, (sp0 - 2) & 0xFFFF)
    return dict(memory=memory, changed=changed, eligible=True,
                candidate=base, rejected=None, saved_es=saved_es,
                returned_si=returned_si)


def assert_independent_producer(case, initial_memory, initial_regs, observed):
    if case.get('provider') or case.get('vga_map'):
        return
    expected = independent_producer(case, initial_memory, initial_regs)
    interactions.oracle_require(expected['eligible'] or expected['rejected'] is None,
        case['name'] + ': inconsistent independent eligibility result')
    # Feedback can reuse the producer's temporary PUSH slots as an INT frame.
    # Compare at the exact map-to-feedback handoff, just before its first live
    # DS:2010 gate read, while retaining stack/map alias effects in the model.
    phase_memory = bytearray(initial_memory)
    cutoff = next((index for index, event in enumerate(observed['events'])
                   if event[0] == 'read' and event[1] ==
                   interactions.physical(initial_regs['ds'], 0x2010)),
                  len(observed['events']))
    for event in observed['events'][:cutoff]:
        if event[0] == 'write':
            phase_memory[event[1] & MASK] = event[2] & 0xFF
    if expected['changed']:
        for address in expected['changed']:
            interactions.oracle_require(
                phase_memory[address] == expected['memory'][address],
                f"{case['name']}: independent producer byte {address:05X} "
                f"{phase_memory[address]:02X}/"
                f"{expected['memory'][address]:02X}")
    if expected['eligible'] and expected['rejected'] is None:
        interactions.oracle_require(
            observed['regs']['si'] == expected['returned_si'],
            f"{case['name']}: independent live POP SI "
            f"{observed['regs']['si']:04X}/{expected['returned_si']:04X}")
        if case.get('name') in ('map-record-map-alias', 'map-stack-cell-alias'):
            interactions.oracle_require(
                observed['regs']['es'] == expected['saved_es'],
                f"{case['name']}: independent live POP ES "
                f"{observed['regs']['es']:04X}/{expected['saved_es']:04X}")


def assert_original_contract(case, observed, *, core):
    """Make each original boundary and handoff explicit before native compare."""
    outer = case.get('outer_return', interactions.OUTER_RETURN)
    expected_providers = {
        'map-live-pop-dx': 'map-dx',
        'map-live-pop-bx': 'map-bx',
        'map-live-probe-reread': 'map-late',
        'map-live-callback-read': 'map-callback',
        'map-late-producer-cell': 'map-producer-cell',
        'map-live-pop-es': 'map-es',
        'map-feedback-pc-returned-ds': 'pc',
        'map-feedback-pc-changed-iret': 'pc',
        'map-feedback-sound-changed-iret': 'sound',
    }
    if case['name'] in expected_providers:
        interactions.oracle_require(expected_providers[case['name']] in observed['used'],
            case['name'] + ': declared provider did not trigger')
    if case['name'] in ('map-feedback-pc-unbound',
                        'map-feedback-sound-unbound'):
        interactions.oracle_require(observed['status'] == 1,
            case['name'] + ': expected the declared unbound vector seam')
    elif case['name'] in ('map-feedback-pc-changed-iret',
                          'map-feedback-sound-changed-iret'):
        interactions.oracle_require(observed['status'] == 4,
            case['name'] + ': expected the declared changed IRET seam')
    elif case['name'].startswith('map-reject-') or case['name'] in (
            'map-count-zero', 'map-state-mask-reject',
            'map-live-probe-reread'):
        interactions.oracle_require(observed['status'] == 0 and
            observed['continuation'] == (0x320C if core else outer),
            case['name'] + ': did not reach the shared failure RET boundary')
    elif case['name'] == 'map-success' or case['name'] in (
            'map-count-wrap', 'map-y-subtract-boundary', 'map-live-pop-dx',
            'map-live-pop-bx',
            'map-state-mask-ignored-bit10',
            'map-live-callback-read', 'map-late-producer-cell',
            'map-decrement-callback-flags',
            'map-and-callback-flags', 'map-live-pop-es', 'map-df-set',
            'map-record-map-alias',
            'map-stack-cell-alias', 'map-physical-word-wrap', 'map-vga-ss-bank',
            'map-feedback-pc', 'map-feedback-pc-returned-ds',
            'map-feedback-adlib', 'map-feedback-tandy',
            'map-outer-stack-wrap', 'map-nonzero-code-segment'):
        interactions.oracle_require(observed['status'] == 0,
            case['name'] + ': expected READY after successful selector-5 path')
        if core:
            interactions.oracle_require(observed['continuation'] == 0x320B,
                case['name'] + f': successful path missed feedback RET boundary '
                f'(status={observed["status"]}, IP={observed["continuation"]:04X})')
        else:
            interactions.oracle_require(observed['continuation'] == outer,
                case['name'] + ': adapter did not consume live outer RET')
    if case['name'] == 'map-late-producer-cell':
        saved = interactions.physical(
            observed['regs']['es'], (case.get('si', 0x4000) + 0x16) & 0xFFFF)
        interactions.oracle_require(observed['memory'][saved] == 0x99,
            'late producer provider did not save its newly written first map cell')


def own_row(case, expected, core):
    sites = {address for source, address in expected['sites']
             if source == 'main' and address in OWN_INS}
    edges = {(source_ip, target)
             for source, source_ip, target in expected['edges']
             if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core, status=expected['status'],
                continuation=expected['continuation'], sites=sorted(sites),
                edges=[list(edge) for edge in sorted(edges)],
                steps=expected['steps'], event_count=len(expected['events']),
                providers=sorted(expected['used']))


def original_only():
    before = input_hashes()
    all_sites, all_edges, rows = set(), set(), []
    specs = cases()
    for case in specs:
        memory, regs, device, _, _ = setup(case)
        for core in (True, False):
            expected = original(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), core=core)
            assert_original_contract(case, expected, core=core)
            assert_independent_producer(case, memory, regs, expected)
            row = own_row(case, expected, core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'original selector-5 site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'original selector-5 edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
    interactions.oracle_require(before == input_hashes(),
        'selector-5 inputs changed during original-only preflight')
    print(f'PASS original selector-5 map: {len(specs)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} outcomes', flush=True)
    handoffs = original_pattern_handoffs()
    print(f'PASS original pattern restoration handoff: {len(handoffs)} states, '
          'all nine producer-saved map cells restored', flush=True)


def _pattern_handoff_input(case):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    base = map_offset(memory, regs)
    parent = original(case, bytearray(memory), dict(regs),
                      copy.deepcopy(device), core=True)
    assert_original_contract(case, parent, core=True)
    pattern_case = dict(name=case['name'] + '-283b-restore', seed=0)
    state = dict(parent['regs'])
    state['ip'] = pattern_bus.ENTRY
    return (pattern_case, memory, base, parent, state,
            copy.deepcopy(parent['device']), regs, device,
            pc_binding, sound_binding)


def original_pattern_handoffs():
    rows = []
    by_name = {case['name']: case for case in cases()}
    for name in ('map-success', 'map-count-wrap'):
        case = by_name[name]
        pattern_case, before, base, parent, state, device, _regs, _device, _, _ = (
            _pattern_handoff_input(case))
        restored = pattern_bus.OriginalRun(
            pattern_case, bytearray(parent['memory']), dict(state), device,
            core=True).run()
        for index, offset in enumerate(cell_offsets(base)):
            address = interactions.physical(state['ss'], offset)
            interactions.oracle_require(
                restored['memory'][address] == before[address],
                f'{name}: 283B did not restore original map cell {index}')
        rows.append(dict(name=name, sites=sorted(restored['sites']),
                         events=len(restored['events'])))
    return rows


def native_pattern_handoffs(directory, map_native):
    native = pattern_bus.Native(directory, 0)
    rows = []
    by_name = {case['name']: case for case in cases()}
    for name in ('map-success', 'map-count-wrap'):
        case = by_name[name]
        (pattern_case, before, base, parent, oracle_state, oracle_device,
         initial_regs, initial_device, pc_binding, sound_binding) = (
            _pattern_handoff_input(case))
        oracle = pattern_bus.OriginalRun(
            pattern_case, bytearray(parent['memory']), dict(oracle_state),
            copy.deepcopy(oracle_device), core=True).run()

        producer = map_native.run(case, bytearray(before), dict(initial_regs),
                                  copy.deepcopy(initial_device), pc_binding,
                                  sound_binding, core=True)
        interactions.require(producer['status'] == parent['status'] and
                             producer['continuation'] == parent['continuation'],
            f'{name}: native producer status/continuation differs from original')
        for role in interactions.REG_NAMES:
            if role == 'flags':
                continue
            interactions.require(producer['regs'][role] == parent['regs'][role],
                f'{name}: native producer {role} differs from original')
        interactions.require(((producer['regs']['flags'] ^ parent['regs']['flags']) &
                              parent['flag_mask']) == 0,
            f'{name}: native producer defined FLAGS differ from original')
        interactions.require(producer['memory'] == parent['memory'],
            f'{name}: native producer RAM differs from original before 283B')
        compare_events(name + ' producer', producer['events'], parent['events'])
        interactions.require(producer['providers'] == parent['used'],
            f'{name}: native producer provider effects differ from original')
        if parent['device'] is not None:
            interactions.require(producer['device'].state() == parent['device'].state(),
                f'{name}: native producer VGA state differs from original')

        # The 283B leaf receives the actual native producer's complete live
        # register/RAM result, with IP set to its declared direct-entry seam.
        state = dict(producer['regs'])
        state['ip'] = pattern_bus.ENTRY
        device = copy.deepcopy(producer['device'])

        memory = bytearray(producer['memory'])
        native_device = copy.deepcopy(device)
        callbacks = pattern_bus.NativeBus(pattern_case, memory,
                                          native_device, state)
        call = pattern_bus.fixtures.Call(
            state['ds'], state['ss'], state['sp'], state['si'],
            state['di'], state['dx'], state['es'], state['flags'])
        result = native.bus_core(pattern_bus.c_buffer(memory),
                                 ct.byref(call), ct.byref(callbacks.bus))
        actual_state = dict(state)
        actual_state.update(ax=result.product, bx=result.map_offset,
                            dx=result.restored_value, si=result.record_cursor,
                            di=result.restored_destination,
                            es=result.restored_segment, sp=result.stack_offset,
                            flags=result.flags, ip=pattern_bus.RET)
        pattern_bus.compare_state(pattern_case, actual_state, oracle['state'],
                                  'selector-5 handoff core')
        pattern_bus.compare_memory(pattern_case, bytes(memory), oracle['memory'],
                                   'selector-5 handoff core')
        pattern_bus.compare_device(pattern_case, native_device, oracle['device'])
        pattern_bus.compare_events(pattern_case, callbacks.events, oracle['events'])
        for index, offset in enumerate(cell_offsets(base)):
            address = interactions.physical(state['ss'], offset)
            interactions.oracle_require(memory[address] == before[address],
                f'{name}: native 283B did not restore original map cell {index}')
        rows.append(dict(name=name, sites=sorted(oracle['sites']),
                         events=len(callbacks.events)))
    return rows


class MapNative(basic.Native):
    cluster = 'entity_action_map'
    core_name = 'lmn_entity_action_map_core'
    adapter_name = 'lmn_entity_action_map_adapter'
    access_type = MapAccess


def compare_events(label, actual, expected):
    basic.compare_events(label, actual, expected)


def compare_case(native, case, *, core):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    assert_original_contract(case, expected, core=core)
    assert_independent_producer(case, memory, regs, expected)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), pc_binding, sound_binding,
                        core=core)
    interactions.require(actual['status'] == expected['status'],
        f'{label}: status {actual["status"]}/{expected["status"]}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        interactions.require(actual['regs'][name] == expected['regs'][name],
            f'{label}: {name} {actual["regs"][name]:04X}/'
            f'{expected["regs"][name]:04X}')
    interactions.require(((actual['regs']['flags'] ^ expected['regs']['flags']) &
                          expected['flag_mask']) == 0,
        f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
        f'{expected["regs"]["flags"]:04X} under {expected["flag_mask"]:04X}')
    interactions.require(actual['memory'] == expected['memory'],
                         label + ': complete 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    interactions.require(actual['providers'] == expected['used'],
        f'{label}: provider effects {actual["providers"]}/{expected["used"]}')
    if expected['device'] is not None:
        interactions.require(actual['device'].state() == expected['device'].state(),
                              label + ': VGA registers/planes/latches differ')
        got_trace = [tuple(event[:3]) for event in actual['device'].trace]
        ref_trace = [tuple(event[:3]) for event in expected['device'].trace]
        interactions.require(got_trace == ref_trace,
                              label + ': ordered VGA trace differs')
    return own_row(case, expected, core)


MUTATION_WITNESSES = {
    1: ('map-y-subtract-boundary', True),
    2: ('map-live-pop-dx', True),
    3: ('map-live-pop-bx', True),
    4: ('map-live-probe-reread', True),
    5: ('map-decrement-callback-flags', True),
    6: ('map-and-callback-flags', True),
    7: ('map-df-set', True),
    8: ('map-live-pop-es', True),
}


def input_hashes():
    paths = set(basic.input_hashes())
    paths.update((
        'docs/entity-actions.md', 'c/entity_action_map.c',
        'c/entity_action_map.h', 'tests/entity_action_map.py',
        'tests/entity_pattern.py', 'tests/entity_pattern_bus.py',
        'c/entity_pattern.c', 'c/entity_pattern.h',
    ))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def worker(directory):
    before = input_hashes()
    interactions.oracle_require(sha(interactions.IMAGE) ==
        'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
        'Pinned static image identity changed')
    interactions.oracle_require(MAP_BYTES == 408 and MAP_SITES == 158 and
                                len(OWN_EDGES) == 73,
        'Selector-5 static byte/site/outcome accounting changed')
    specs = cases()
    by_name = {case['name']: case for case in specs}
    baseline = MapNative(directory, 0)
    rows, all_sites, all_edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
            total_steps += row['steps']
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'native selector-5 site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'native selector-5 edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
    handoffs = native_pattern_handoffs(directory, baseline)
    del baseline
    gc.collect()

    mutations = []
    for mutation, (name, core) in MUTATION_WITNESSES.items():
        mutant = MapNative(directory, mutation)
        try:
            compare_case(mutant, by_name[name], core=core)
        except interactions.Mismatch as error:
            mutations.append(dict(id=mutation, witness=name, core=core,
                                  mismatch=str(error), completed=True))
        else:
            raise interactions.OracleFailure(
                f'entity-action-map mutant {mutation} survived completed witness {name}')
        del mutant
        gc.collect()

    interactions.oracle_require(before == input_hashes(),
        'selector-5 inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(interactions.IMAGE),
        native_code_ranges=[[ENTRY, END]], translated_code_bytes=MAP_BYTES,
        instruction_sites=len(all_sites), static_instruction_addresses=sorted(OWN_INS),
        executed_instruction_addresses=sorted(all_sites),
        own_static_branch_edges=len(OWN_EDGES),
        parent_feasible_branch_edges=len(all_edges),
        branch_edges=[list(edge) for edge in sorted(all_edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        case_count=len(specs), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        cases=rows, pattern_restoration_handoffs=handoffs,
        input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS,
                    process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=INSTRUCTION_LIMIT,
                    ordered_bus_event_limit=EVENT_LIMIT,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domains=[
            'selector-5 map scan and transition 3336h..34CDh with full 1 MiB RAM, all live registers, defined FLAGS, and ordered bus events',
            'nine independent 2/A/3 rejection cells, exact word-before-compare behavior, and 16-bit coordinate/product arithmetic',
            'live POP DX/BX/ES values, callback-driven future map reads, and exact RMW callback FLAGS',
            'forward explicit map cursor with DF-sensitive STOSB, live stack/map and DS=SS record/map aliases, and final POP SI',
            'VGA-backed SS map reads/writes, physical word wrap, feedback INT seams, and actual outer RET']))
    print(f'PASS entity action map: {len(specs)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} outcomes, {total_events} events, '
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
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_action_map.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-action-map-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
