"""Bounded original-versus-C checks for the 2D0F late entity states."""
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
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK = interactions.SIZE, interactions.MASK
ENTRY, END = 0x2D0F, 0x2E04
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9))
CONTINUATION = 0x1FEB
STATE_8000, FLAG80 = 0, 1
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
ALL_FLAGS = interactions.FLAGS
MAX_INSTRUCTIONS, MAX_EVENTS = 4096, 4096
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-late-states-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, END)
PIXEL_INS = decoded_span(PIXEL_ENTRY, PIXEL_RET + 1)
FINISH_INS = {ins.address: ins for start, end in FINISH_SPANS
              for ins in MD.disasm(IMAGE[start:end], start)}
INTEGRATED_INS = dict(OWN_INS)
for group in (PIXEL_INS, FINISH_INS, interactions.MAIN_INS):
    INTEGRATED_INS.update(group)


def branch_edges(instructions):
    result = set()
    for address, ins in instructions.items():
        mnemonic = ins.mnemonic.lower()
        if not ins.group(capstone.CS_GRP_JUMP) and mnemonic not in (
                'loop', 'loope', 'loopne', 'jcxz'):
            continue
        if mnemonic not in ('jmp', 'ljmp'):
            result.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            result.add((address, ins.operands[-1].imm & 0xFFFF))
    return result


OWN_EDGES = branch_edges(OWN_INS)
CALL_RETURNS = {
    0x2D83: ({PIXEL_RET}, 7),
    0x1FE8: (set(interactions.MAIN_RETS), 5),
}


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('entry', 'value', 'map_cursor', 'count', 'auxiliary_value',
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
    """The bounded original/provider failed to reach a declared boundary."""


class NativeMismatch(AssertionError):
    """Only a completed original/native comparison can credit a mutant."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def pixel_start(x, y):
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    return (((row * 0xD0) & 0xFFFF) + (x >> 3) + 0x4A40) & 0xFFFF


def observed_own_edges(observed):
    return {(source_ip, target)
            for source, source_ip, target in observed['edges']
            if source == 'main' and source_ip in OWN_INS}


def cases():
    rows = [
        dict(name='state8000-first-pixel-hit', cadence=0, y=0x40, hit=0),
        dict(name='state8000-second-pixel-hit', cadence=1, y=0x40, hit=1),
        dict(name='state8000-third-pixel-hit', cadence=2, y=0x40, hit=2),
        dict(name='state8000-three-probes-clear', cadence=3, y=0x40,
             hit=-1, df=True),
        dict(name='state8000-al5-scan-request-ff', cadence=4, y=0x40,
             scan=0xFF, hit=0),
        dict(name='state8000-al5-scan-request-fe', cadence=4, y=0x40,
             scan=0xFE, hit=0),
        dict(name='state8000-cadence-8-mutant-witness', cadence=7, y=0x40,
             hit=0),
        dict(name='state8000-transition-no-sound', cadence=0x0F,
             record_bits=0, entity_flags=0xA5),
        dict(name='state8000-enabled-driver-options-clear', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=0),
        dict(name='state8000-transition-sound-adlib', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=3, driver='adlib'),
        dict(name='state8000-transition-sound-tandy', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=2, driver='tandysnd'),
        dict(name='state8000-sound-sets-live-record-bit4', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=3,
             provider='sound-sets-record-bit4'),
        dict(name='state8000-live-saved-ds-before-test', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=3,
             provider='state8000-live-saved-ds', provider_ds=0x6100),
        dict(name='state8000-sound-changed-iret', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=3,
             provider='sound-interrupt-return', provider_return=0x4567),
        dict(name='state8000-sound-unbound-vector', cadence=0x0F,
             record_bits=0, enabled=0xFF, options=3,
             sound_vector=(0x1234, 0x7000)),
        dict(name='state8000-callback-slots-distinct', cadence=0x0F,
             record_bits=0, slot2e=0xA55A, slot3c=0xB66B),
        dict(name='state8000-callback-overlaps-transition-store',
             cadence=0x0F, record_bits=0, si=0x0030, slot2e=0xA55A,
             slot3c=0xB66B),
        dict(name='state8000-pixel-ret-changed', cadence=1, y=0x40,
             hit=0, provider='pixel-return', changed_target=0x4567),
        dict(name='state8000-live-pitch-between-probes', cadence=3,
             y=0x40, hit=1, provider='pitch-on-first-pixel', pitch=0xD0,
             pitch_after=0x40),
        dict(name='state8000-probe-es-versus-ds', cadence=0, y=0x40,
             hit=0, ds=0x4000, es_decoy=True),
        dict(name='state8000-height-b3-to-interaction', cadence=0, y=0xB3,
             hit=0),
        dict(name='state8000-height-b4-to-inactive', cadence=0, y=0xB4,
             hit=-1),
        dict(name='state8000-signed-negative-height', cadence=0, y=0xFFFF,
             hit=0),
        dict(name='state8000-physical-stack-wrap', cadence=0, y=0x40,
             hit=0, ss=0xFFFF, sp=1),
        dict(name='state8000-vga-map-finish', cadence=0, y=0x40,
             hit=0, ss=0xA000, vga=True),
        dict(name='flag80-nonzero-cadence', entry=FLAG80, cadence=0,
             record_bits=0x1234),
        dict(name='flag80-seven-step-mutant-witness', entry=FLAG80,
             cadence=7, record_bits=0x1234, entity_flags=0xFF),
        dict(name='flag80-callback-slots-distinct', entry=FLAG80,
             cadence=7, record_bits=0, slot2e=0xA55A, slot3c=0xB66B,
             entity_flags=0xFF),
        dict(name='flag80-callback-cleared-by-record-store', entry=FLAG80,
             cadence=7, si=0x0026, record_bits=0x1234,
             slot2e=0xA55A, slot3c=0xB66B, entity_flags=0xFF),
        dict(name='flag80-sequential-entity-flag-rmw', entry=FLAG80,
             cadence=7, record_bits=0, entity_flags=0xFF),
        dict(name='flag80-vga-map-finish', entry=FLAG80, cadence=7,
             record_bits=0, entity_flags=0x81, ss=0xA000, vga=True),
    ]
    oracle_require(20 <= len(rows) <= 32,
                   f'late-state fixture count changed: {len(rows)}')
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'late-state fixture names are not unique')
    for index, row in enumerate(rows):
        row.setdefault('entry', STATE_8000)
        row.setdefault('seed', 0x2D0F + index * 53)
        row.setdefault('load', interactions.MAIN_SEG)
        row.setdefault('ds', DATA_SEGMENT)
        row.setdefault('ss', 0x5000)
        row.setdefault('si', 0x6000)
        row.setdefault('sp', 0xD000)
        row.setdefault('x', 0x20)
        row.setdefault('y', 0x40)
        row.setdefault('pitch', 0x00D0)
        row.setdefault('cadence', 3)
        row.setdefault('scan', 0xFF)
        row.setdefault('hit', -1)
        row.setdefault('record_bits', 0xFFFF)
        row.setdefault('entity_flags', 0xA5)
        row.setdefault('enabled', 0)
        row.setdefault('options', 0)
        row.setdefault('driver', 'adlib')
        row.setdefault('slot2e', 0x6170)
        row.setdefault('slot3c', 0x6174)
        row.setdefault('flags', 0x0ED7)
    return rows


def setup(case):
    template = dict(case)
    template['vga'] = False
    raw_flags = template.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    if template.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    template['flags'] = flags
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(template)
    regs.update(cs=template['load'], ip=ENTRY, ds=template['ds'],
                es=template.get('es', 0x6200),
                ss=template['ss'], si=template['si'], sp=template['sp'],
                flags=flags)
    regs.update(ax=template.get('ax', 0x1357), bx=template.get('bx', 0x2468),
                cx=template.get('cx', 0xACE1), dx=template.get('dx', 0x0055),
                di=template.get('di', 0x3131), bp=template.get('bp', 0x7B2D))
    entry_offset = ENTRY if template['entry'] == STATE_8000 else 0x2DB5
    regs['ip'] = entry_offset

    ds, ss, si, sp = regs['ds'], regs['ss'], regs['si'], regs['sp']
    put16(memory, ss, sp, template.get('outer_return', 0x7A5C))
    put16(memory, ds, 0x0004, template['pitch'])
    put16(memory, ds, si, template['x'])
    put16(memory, ds, (si + 2) & 0xFFFF, template['y'])
    put16(memory, ds, (si + 6) & 0xFFFF, template.get('height_delta', 0))
    put16(memory, ds, (si + 8) & 0xFFFF, template['record_bits'])
    put16(memory, ds, (si + 0x0E) & 0xFFFF, template.get('record_word_e', 0x2A2A))
    put16(memory, ds, (si + 0x14) & 0xFFFF, template.get('callback_initial', 0x7654))
    put8(memory, ds, (si + 0x24) & 0xFFFF, template['entity_flags'])
    put8(memory, ds, (si + 0x27) & 0xFFFF, template.get('record_delta', 0))
    put8(memory, ds, (si + 0x28) & 0xFFFF, template['cadence'])
    put8(memory, ds, (si + 0x29) & 0xFFFF, template.get('state_29', 0x17))
    put8(memory, ds, (si + 0x2A) & 0xFFFF, template.get('state_2a', 0x6B))
    put8(memory, ds, 0x004B, template['scan'])
    put8(memory, ds, 0x2010, template['enabled'])
    put8(memory, ds, 0x25A7, template['options'])
    put16(memory, ds, 0x002E, template['slot2e'])
    put16(memory, ds, 0x003C, template['slot3c'])
    if 'provider_ds' in template:
        alternate = template['provider_ds']
        put16(memory, alternate, (si + 8) & 0xFFFF,
              template.get('provider_record_bits', 0x0004))
        put8(memory, alternate, (si + 0x22) & 0xFFFF,
             template.get('provider_entity_22', 0x00AA))
    if ds != DATA_SEGMENT:
        for index, value in enumerate(PIXEL_MASKS):
            put8(memory, ds, 0x547C + index, value)

    device = None
    if case.get('vga'):
        device = MinimapVga(template['seed'], read_map=0)
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[5] = 0
        device.gc[8] = 0xFF
        for plane in device.planes:
            plane[:] = bytes(0x10000)

    if case.get('sound_vector') is not None:
        put16(memory, 0, 0x0184, case['sound_vector'][0])
        put16(memory, 0, 0x0186, case['sound_vector'][1])

    if case['entry'] == STATE_8000:
        x, y = get16(memory, ds, si), get16(memory, ds, (si + 2) & 0xFFFF)
        destination = pixel_start(x, y)
        mask = PIXEL_MASKS[x & 7]
        pitch = template['pitch']
        hit = template.get('hit', -1)
        addresses = [destination]
        addresses.append((addresses[-1] + pitch) & 0xFFFF)
        addresses.append((addresses[-1] + pitch) & 0xFFFF)
        for index in range(3):
            value = mask if index == hit else 0
            address = physical(0xA000, addresses[index])
            if device is None:
                memory[address] = value
            else:
                for plane in device.planes:
                    plane[addresses[index]] = value
        if template.get('es_decoy'):
            put8(memory, ds, destination, 0)

    return memory, regs, device, pc_binding, sound_binding


class LateAccess(interactions.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.return_address = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
        self.return_armed = False

    def _provider(self, kind, address):
        super()._provider(kind, address)
        effect = self.case.get('provider')
        if (effect == 'pixel-return' and kind == 'read' and
                address == self.return_address and self.return_armed and
                effect not in self.used):
            self.modify_word(self.regs['ss'], (self.regs['sp'] - 2) & 0xFFFF,
                             self.case.get('changed_target', 0x4567))
            self.used.add(effect)
        if (effect == 'sound-sets-record-bit4' and kind == 'write' and
                effect not in self.used):
            driver = self.case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                offset = (self.regs['si'] + 8) & 0xFFFF
                current = get16(self.memory, self.regs['ds'], offset)
                self.modify_word(self.regs['ds'], offset, current | 4)
                self.used.add(effect)
        if (effect == 'state8000-live-saved-ds' and kind == 'write' and
                effect not in self.used):
            driver = self.case.get('driver', 'adlib')
            latch = interactions.sound.TAILS[driver][4][1]
            if address == physical(interactions.SOUND_SEG, latch):
                self.modify_word(self.regs['ss'],
                                 (self.regs['sp'] - 8) & 0xFFFF,
                                 self.case['provider_ds'])
                self.used.add(effect)

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        effect = self.case.get('provider')
        address &= MASK
        if (effect == 'pitch-on-first-pixel' and kind == 'read' and
                VGA_BASE <= address < VGA_END and effect not in self.used):
            self.modify_word(self.regs['ds'], 4,
                             self.case.get('pitch_after', 0x0040))
            self.used.add(effect)
        result = super().access(kind, address, flags, mask, value)
        if (effect == 'pixel-return' and kind == 'write' and
                address == self.return_address and effect not in self.used and
                (value & 0xFF) == (0x2D86 & 0xFF)):
            self.return_armed = True
        return result


def original(case, memory, regs, device):
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=ALL_FLAGS,
        main_instructions=INTEGRATED_INS,
        main_call_returns=CALL_RETURNS,
        stop_offsets={CONTINUATION: 0},
        access_factory=lambda c, m, r, d: LateAccess(c, m, r, d),
        instruction_limit=MAX_INSTRUCTIONS)


def expected_path(case, observed):
    own = {address for source, address in observed['sites']
           if source == 'main' and address in OWN_INS}
    if case['entry'] == STATE_8000:
        cadence = (case['cadence'] + 1) & 0x0F
        if cadence == 0:
            oracle_require(0x2D1B in own and 0x2D78 not in own,
                           case['name'] + ': cadence zero missed reset transition')
        else:
            oracle_require(0x2D78 in own and 0x2D1B not in own,
                           case['name'] + ': nonzero cadence missed pixel path')
        if cadence == 5:
            oracle_require(0x2D7C in own and 0x2D81 in own,
                           case['name'] + ': AL=5 scan-request compare was skipped')
        if case.get('hit', -1) >= 0 and not case.get('provider') == 'pixel-return':
            oracle_require(observed['status'] == 0,
                           case['name'] + ': expected normal pixel return')
        if case.get('provider') == 'pixel-return':
            oracle_require(observed['status'] == 7 and
                           observed['continuation'] == case['changed_target'] and
                           'pixel-return' in observed['used'],
                           case['name'] + ': live pixel return change was missed')
        if case.get('provider') == 'sound-sets-record-bit4':
            oracle_require(get8(observed['memory'], observed['regs']['ds'],
                                observed['regs']['si'] + 0x22) == 0,
                           case['name'] + ': fresh +8 read did not clear +22')
        if case.get('provider') == 'state8000-live-saved-ds':
            ds = case['provider_ds']
            si = observed['regs']['si']
            oracle_require(observed['regs']['ds'] == ds and
                           get16(observed['memory'], ds, si + 8) & 4 and
                           get8(observed['memory'], ds, si + 0x22) == 0 and
                           get8(observed['memory'], case['ds'], si + 0x22) == 0x0F,
                           case['name'] + ': post-INT test did not use returned DS')
        if case['name'] == 'state8000-callback-overlaps-transition-store':
            oracle_require(get16(observed['memory'], observed['regs']['ds'],
                                 observed['regs']['si'] + 0x14) == 0x180B,
                           case['name'] + ': callback was not read after aliased +0C store')
        if case.get('provider') == 'pitch-on-first-pixel':
            start = pixel_start(case['x'], case['y'])
            pixel_reads = [address for kind, address, _value, _flags, _mask
                           in observed['events']
                           if kind == 'read' and VGA_BASE <= address < VGA_END]
            expected = [physical(0xA000, start),
                        physical(0xA000, (start + case['pitch_after']) & 0xFFFF)]
            oracle_require(pixel_reads[:2] == expected,
                           case['name'] + ': later pixel probe did not use live pitch')
        if case.get('provider') == 'sound-interrupt-return':
            oracle_require(observed['status'] == 4 and
                           observed['continuation'] == case['provider_return'] and
                           'sound' in observed['used'],
                           case['name'] + ': changed sound IRET was missed')
        elif case.get('sound_vector') is not None:
            oracle_require(observed['status'] == 1,
                           case['name'] + ': unbound sound vector was not reported')
        elif case.get('provider') != 'pixel-return':
            oracle_require((observed['status'], observed['continuation']) ==
                           (0, CONTINUATION),
                           case['name'] + ': did not reach the 1FEB tail')
    elif case['entry'] == FLAG80:
        cadence = (case['cadence'] + 1) & 7
        if cadence:
            oracle_require(0x2DBF in own and observed['status'] == 0,
                           case['name'] + ': nonzero flag80 cadence did not exit')
        else:
            oracle_require(0x2DBF in own and 0x2DC4 in own and
                           observed['status'] == 0,
                           case['name'] + ': flag80 reset transition did not finish')
            oracle_require(observed['continuation'] == CONTINUATION,
                           case['name'] + ': flag80 did not join 1FEB')
            if case['name'] == 'flag80-callback-cleared-by-record-store':
                oracle_require(get16(observed['memory'], observed['regs']['ds'],
                                     observed['regs']['si'] + 0x14) == 0,
                               case['name'] + ': callback read preceded +8 clear')
            if case.get('entity_flags') is not None:
                expected_flags = case['entity_flags'] & 0x01 & 0x7F
                oracle_require(get8(observed['memory'], observed['regs']['ds'],
                                    observed['regs']['si'] + 0x24) == expected_flags,
                               case['name'] + ': sequential +24 masks changed')
    if case.get('provider'):
        oracle_require(case['provider'] in observed['used'] or
                       (case['provider'] == 'sound-interrupt-return' and
                        'sound' in observed['used']),
                       case['name'] + ': requested provider did not fire')


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA provider')
        return
    require(actual is not None, label + ': VGA provider missing')
    require(actual.state() == expected.state(), label + ': VGA plane/device state differs')
    got = [(event[0], event[1], event[2]) for event in actual.trace]
    ref = [(event[0], event[1], event[2]) for event in expected.trace]
    require(got == ref, label + ': VGA device trace differs')


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
        self.access = LateAccess(case, memory, regs, device, native=True)

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
                        f'unexpected late-state OUT {port:04X}={value:04X}')

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = Path(directory) / f'entity-late-states-m{mutation}.dll'
        build(path, mutation, 'entity_late_states')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_late_states_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_late_states_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.c_int, ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        regs = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        bus = NativeBus(case, memory, regs, device)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        pc_ptr = ct.byref(pc_binding) if pc_binding is not None else None
        sound_ptr = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = Call(case['entry'], *(regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds',
                'es', 'ss', 'sp', 'flags')))
            out = self.core(ram, ct.byref(call), pc_ptr, sound_ptr,
                            ct.byref(bus.bus))
            regs.update(ax=out.value, bx=out.map_cursor, cx=out.count,
                        dx=out.auxiliary_value, si=out.record_cursor,
                        di=out.object_cursor, bp=out.candidate_y,
                        cs=out.code_segment, ds=out.data_segment,
                        es=out.extra_segment, ss=out.stack_segment,
                        sp=out.stack_offset, flags=out.flags,
                        ip=out.continuation)
            status = out.status
        else:
            state = interactions.Regs(**regs)
            status = self.adapter(ram, ct.byref(state), case['entry'],
                                  pc_ptr, sound_ptr, ct.byref(bus.bus))
            regs = {name: getattr(state, name) & 0xFFFF
                    for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=regs, device=device,
                    events=bus.access.events, used=bus.access.used,
                    continuation=regs['ip'], status=status)


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding = setup(case)
    oracle = original(case, bytearray(initial), dict(regs),
                      copy.deepcopy(device))
    expected_path(case, oracle)
    actual = native.run(case, initial, regs, device, pc_binding, sound_binding,
                        core=core)
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
    require(actual['memory'] == oracle['memory'], label + ': full RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['used'] == oracle['used'],
            f'{label}: provider effects {actual["used"]}/{oracle["used"]}')
    sites = {address for source, address in oracle['sites']
             if source == 'main' and address in OWN_INS}
    edges = observed_own_edges(oracle)
    integrated = {address for source, address in oracle['sites'] if source == 'main'}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(sites),
                edges=[list(edge) for edge in sorted(edges)],
                integrated_sites=sorted(integrated), event_count=len(oracle['events']),
                steps=oracle['steps'])


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'src/game_code.asm', 'src/entity_graphics.asm', 'src/program.asm',
        'c/entity_late_states.c', 'c/entity_late_states.h',
        'c/entity_finish.c', 'c/entity_finish.h', 'c/entity_pixel.c',
        'c/entity_pixel.h', 'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h', 'c/pcspeaker.c',
        'c/pcspeaker.h', 'c/pcspeaker_sym.h', 'c/sound_interrupt.c',
        'c/sound_interrupt.h', 'c/sound_latches.c', 'c/sound_latches.h',
        'c/sound_latches_sym.h', 'c/lemmings_sym.h',
        'c/regs.h', 'c/special_blit.h', 'tests/entity_late_states.py',
        'tests/entity_interactions.py', 'tests/entity_pixel.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/minimap_vga.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py',
        'tools/coverage.py', 'tools/unpack.py', 'tools/resources.py',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/adlib-regions.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-regions.json', 'metadata/tandysnd-symbols.json',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm',
        'src/sound/tandysnd.asm', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_only():
    before = input_hashes()
    oracle_require(len(OWN_INS) == 74 and sum(i.size for i in OWN_INS.values()) == 245,
                   f'late-state identity changed: {len(OWN_INS)} sites / '
                   f'{sum(i.size for i in OWN_INS.values())} bytes')
    oracle_require(len(OWN_EDGES) == 26,
                   f'late-state CFG edge count changed: {sorted(OWN_EDGES)}')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned main code image hash changed')
    specs = cases()
    covered, edges, integrated = set(), set(), set()
    rows = []
    for case in specs:
        initial, regs, device, _pc, _sound = setup(case)
        observed = original(case, bytearray(initial), dict(regs),
                            copy.deepcopy(device))
        expected_path(case, observed)
        if case.get('provider') == 'sound-interrupt-return':
            oracle_require(observed['status'] == 4,
                           case['name'] + ': changed sound return did not stop')
        elif case.get('sound_vector') is not None:
            oracle_require(observed['status'] == 1,
                           case['name'] + ': unbound vector did not stop')
        elif case.get('provider') == 'pixel-return':
            oracle_require(observed['status'] == 7,
                           case['name'] + ': changed pixel return did not stop')
        else:
            oracle_require(observed['status'] == 0,
                           case['name'] + f': unexpected boundary status {observed["status"]}')
        own_sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
        own_edges = observed_own_edges(observed)
        covered.update(own_sites)
        edges.update(own_edges)
        integrated.update(address for source, address in observed['sites']
                          if source == 'main')
        rows.append(dict(name=case['name'], sites=sorted(own_sites),
                         edges=[list(edge) for edge in sorted(own_edges)],
                         status=observed['status'], continuation=observed['continuation'],
                         events=len(observed['events']), steps=observed['steps']))
        del initial, regs, device, observed
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'late-state executed sites missing {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'late-state executed edges differ: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')
    oracle_require(before == input_hashes(),
                   'late-state source/dependency hashes changed during original preflight')
    print(f'PASS entity late states original: {len(specs)} cases, '
          f'{len(covered)} sites, {len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} ordered events; bounded original only')
    return rows


def worker(directory):
    before = input_hashes()
    specs = cases()
    baseline = Native(directory)
    rows, sites, edges, integrated = [], set(), set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            integrated.update(row['integrated_sites'])
            total_events += row['event_count']
            total_steps += row['steps']
        gc.collect()
    oracle_require(sites == set(OWN_INS),
                   f'native executed sites missing {sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == OWN_EDGES,
                   f'native executed edges differ: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')

    witnesses = {
        1: 'state8000-cadence-8-mutant-witness',
        2: 'state8000-al5-scan-request-fe',
        3: 'state8000-probe-es-versus-ds',
        4: 'state8000-callback-slots-distinct',
        5: 'flag80-seven-step-mutant-witness',
        6: 'flag80-callback-slots-distinct',
    }
    mutations = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        case = next(row for row in specs if row['name'] == name)
        try:
            compare_case(variant, case, core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'late-state mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(before == input_hashes(),
                   'late-state inputs changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[[ENTRY, 0x2DB5],
        [0x2DB5, END]], translated_code_bytes=245, instruction_sites=74,
        own_branch_edges=26, case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations, executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        integrated_main_instruction_addresses=sorted(integrated),
        total_bus_events=total_events, original_code_hook_steps=total_steps,
        cases=[dict(name=row['name'], core=row['core'], status=row['status'],
                    continuation=row['continuation'], sites=row['sites'],
                    edges=row['edges'], event_count=row['event_count'],
                    steps=row['steps']) for row in rows],
        input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domain='State8000 and flag80 entity transitions at the two direct-JMP '
               'entries. Composed actual 5DC6 pixel CALL/RET, INT61 sound seam, '
               '20D6 inactive/interaction finish and 1FE8 CALL/RET. Compares '
               'ordinary complete RAM, every register and defined FLAGS, ordered '
               'memory/device events, live callback/pitch/record aliases and both '
               'transition cadence masks.'))
    print(f'PASS entity late states: {len(specs)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--original-worker'], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)
        return
    if sys.argv[1:] == ['--original-worker']:
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity_late_states arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-late-states-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', str(directory)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
