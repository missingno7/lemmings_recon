"""Bounded state-0040 parent tests for the 2637..2692 handler."""
import copy
import ctypes as ct
import gc
import json
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
from minimap_vga import VGA_BASE, VGA_END
from unpack import ASSET

SIZE, MASK, ALL_FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END = 0x2637, 0x2693
FINISH_SPANS = ((0x1FE8, 0x1FEB), (0x2148, 0x2169))
CONTINUATION = 0x1FEB
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
MAX_INSTRUCTIONS, MAX_EVENTS = 1600, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state40-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-state40-original-differential.json'

IMAGE, ORACLE = interactions.IMAGE, interactions.ORACLE
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
FINISH_INS = {
    ins.address: ins
    for start, end in FINISH_SPANS
    for ins in MD.disasm(IMAGE[start:end], start)
}
INTERACTION_INS = interactions.MAIN_INS
INTEGRATED_INS = dict(OWN_INS)
INTEGRATED_INS.update(FINISH_INS)
INTEGRATED_INS.update(INTERACTION_INS)


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


class NativeMismatch(AssertionError):
    """Only a completed original/native comparison can credit a mutant."""


class OracleFailure(AssertionError):
    """The bounded original/provider failed to reach its declared boundary."""


def read8(memory, segment, offset):
    return memory[interactions.physical(segment, offset)]


def read16(memory, segment, offset):
    address = interactions.physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def write8(memory, segment, offset, value):
    memory[interactions.physical(segment, offset)] = value & 0xFF


def write16(memory, segment, offset, value):
    address = interactions.physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def branch_edges(instructions):
    edges = set()
    for address, ins in instructions.items():
        if not ins.group(capstone.CS_GRP_JUMP):
            continue
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            edges.add((address, (address + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


OWN_EDGES = branch_edges(OWN_INS)


def cases():
    """Cover modulo cadence, both direct finish entries and live aliases."""
    rows = [
        dict(name='cadence-one-y-minus-two', cadence=0, y=0x0040),
        dict(name='cadence-four-y-minus-two', cadence=3, y=0x0040),
        dict(name='cadence-five-stop', cadence=4, y=0x0040),
        dict(name='cadence-six-stop', cadence=5, y=0x0040),
        dict(name='cadence-seven-stop', cadence=6, y=0x0040),
        dict(name='cadence-wrap-zero-transition', cadence=7, y=0x0040),
        dict(name='transition-zero-state-bits', cadence=7, y=0x0040,
             record_bits=0xFFFF, entity_flags=0xFF),
        dict(name='transition-live-callback-alias', cadence=7, y=0x0040,
             ds=DATA_SEGMENT, si=0x002A, callback_word=0xA55A),
        dict(name='transition-entry-bp-is-not-live-y', cadence=7, y=0x0040,
             candidate_y=0x7777),
        dict(name='subtract-live-y-not-entry-bp', cadence=0, y=0x0040,
             candidate_y=0x7777),
        dict(name='preserve-entity-flag-bit-zero', cadence=7, y=0x0040,
             entity_flags=0xFF),
        dict(name='clear-nonzero-entity-flag-bits', cadence=7, y=0x0040,
             entity_flags=0xFE),
        dict(name='finish-clamp-at-ten', cadence=7, y=0x0014,
             height_delta=0),
        dict(name='finish-no-clamp-after-transition', cadence=7, y=0x0015,
             height_delta=0),
        dict(name='finish-clamp-negative-height-delta', cadence=0, y=0x0040,
             height_delta=0xFFC4, record_delta=0x80),
        dict(name='transition-clamp-low-y', cadence=7, y=0x0008,
             height_delta=0xFFFE, record_delta=0x80),
        dict(name='finish-no-clamp-and-interaction', cadence=0, y=0x0040,
             height_delta=0, record_delta=3),
        dict(name='entry-flags-and-rmw', cadence=0, y=0x0040,
             flags=0x0A47),
        dict(name='df-set-finish-and-interaction', cadence=7, y=0x0040,
             df=True, flags=0x0ED7),
        dict(name='live-ss-vga-interaction-map', cadence=7, y=0x0040,
             ss=0xA000, vga=True),
        dict(name='finish-call-overwrites-live-y', cadence=0, y=0x0040,
             ds=0x5000, ss=0x5000, si=0xCFFC, sp=0xD000),
        dict(name='stack-physical-word-wrap', cadence=7, y=0x0040,
             ss=0xFFFF, sp=0x0011),
        dict(name='record-word-offset-wrap', cadence=0, y=0x0040,
             ds=DATA_SEGMENT, si=0xFFFE),
        dict(name='record-physical-word-wrap', cadence=0, y=0x0040,
             ds=0xFFFF, si=0x000F),
        dict(name='poisoned-transition-and-finish', cadence=7, y=0x0040,
             poison=True, seed=0x2640),
    ]
    oracle_require(20 <= len(rows) <= 30,
                   'state40 focused fixture count changed unexpectedly')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x2640 + index * 43)
        row.setdefault('x', 0x0020)
        row.setdefault('height_delta', 0)
        row.setdefault('record_delta', 1)
        row.setdefault('record_bits', 0xFFFF)
        row.setdefault('entity_flags', 0xA5)
    return rows


def expected_final_y(case):
    """Predict only the exact 2148 signed clamp needed to seed SS map bytes."""
    y = case.get('y', 0x20) & 0xFFFF
    cadence = (case.get('cadence', 0) + 1) & 7
    if cadence and cadence >= 5:
        return None, case.get('record_delta', 1) & 0xFF
    candidate = y if cadence == 0 else (y - 2) & 0xFFFF
    # The zero-cadence transition overwrites +06 with FFF6 before entering
    # 2148; the ordinary subtraction path keeps the caller's live +06 word.
    delta = (0xFFF6 if cadence == 0 else
             case.get('height_delta', 0)) & 0xFFFF
    summed = (candidate + delta) & 0xFFFF
    if signed16(summed) <= 0x000A:
        return (9 - delta) & 0xFFFF, (-case.get('record_delta', 1)) & 0xFF
    return candidate, case.get('record_delta', 1) & 0xFF


def setup(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('sp', 0xD000)
    template.setdefault('bp', case.get('candidate_y', 0xBEEF))
    template.setdefault('outer_return', 0xA55A)
    raw_flags = case.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    template['flags'] = flags
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(template)
    regs.update(ip=ENTRY, cs=template['load'], ds=template['ds'],
                ss=template['ss'], si=template.get('si', regs['si']),
                sp=template['sp'], bp=template['bp'], flags=flags)

    ds, ss, si = regs['ds'], regs['ss'], regs['si']
    x, y = case.get('x', 0x20) & 0xFFFF, case.get('y', 0x20) & 0xFFFF
    write16(memory, ds, si, x)
    write16(memory, ds, (si + 2) & 0xFFFF, y)
    write16(memory, ds, (si + 6) & 0xFFFF,
            case.get('height_delta', 0) & 0xFFFF)
    write16(memory, ds, (si + 8) & 0xFFFF,
            case.get('record_bits', 0xFFFF) & 0xFFFF)
    write8(memory, ds, (si + 0x24) & 0xFFFF,
           case.get('entity_flags', 0xA5))
    write8(memory, ds, (si + 0x27) & 0xFFFF,
           case.get('record_delta', 1))
    write8(memory, ds, (si + 0x28) & 0xFFFF,
           case.get('cadence', 0))
    if 'callback_word' in case:
        write16(memory, ds, 0x002E, case['callback_word'])

    # The direct 2148 path eventually calls 2EC0 through 1FE8. Seed the
    # post-clamp interaction-map observations as zero-nibble normal returns.
    final_y, final_delta = expected_final_y(case)
    if final_y is not None:
        first, second = interactions.map_offsets(x, final_y, final_delta)
        for offset in (first, second):
            address = interactions.physical(ss, offset)
            memory[address] = 0
            if device is not None and VGA_BASE <= address < VGA_END:
                device.planes[0][address - VGA_BASE] = 0

    # The parent entered this state after PUSH ES. State 0040 exits at 1FEB
    # without consuming the saved word.
    write16(memory, ss, regs['sp'], case.get('outer_return', regs['es']))
    return memory, regs, device, pc_binding, sound_binding


def original(case, memory, regs, device):
    ret_map = {address: (CONTINUATION, 5)
               for address, ins in INTERACTION_INS.items()
               if ins.mnemonic.lower() == 'ret'}
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=ALL_FLAGS,
        main_instructions=INTEGRATED_INS,
        main_ret_continuations=ret_map,
        stop_offsets={CONTINUATION: 0},
        instruction_limit=MAX_INSTRUCTIONS)


def original_only():
    specs = cases()
    covered, edges, rows = set(), set(), []
    for case in specs:
        memory, regs, device, _pc, _sound = setup(case)
        result = original(case, bytearray(memory), dict(regs), copy.deepcopy(device))
        oracle_require((result['status'], result['continuation']) ==
                       (0, CONTINUATION),
                       case['name'] + ': did not stop normally at 1FEB')
        independent_checks(case, memory, regs, result)
        own_sites = {address for source, address in result['sites']
                     if source == 'main' and address in OWN_INS}
        own_edges = {(source_ip, target)
                     for source, source_ip, target in result['edges']
                     if source == 'main' and source_ip in OWN_INS}
        next_cadence = (case.get('cadence', 0) + 1) & 7
        expected_site = (0x2654 if next_cadence == 0 else
                         0x264A if next_cadence < 5 else 0x2647)
        oracle_require(expected_site in own_sites,
                       case['name'] + f': expected state path at {expected_site:04X} absent')
        covered.update(own_sites)
        edges.update(own_edges)
        rows.append(dict(name=case['name'], sites=sorted(own_sites),
                         edges=[list(edge) for edge in sorted(own_edges)],
                         continuation=result['continuation'],
                         events=len(result['events']), steps=result['steps']))
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'state40 site union differs: missing={sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'state40 edge union differs: missing={sorted(OWN_EDGES-edges)}')
    print(f'PASS entity state40 original: {len(rows)} cases, {len(covered)} sites, '
          f'{len(edges)} owned edges; bounded original only')
    return rows, edges


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
                 'stack_segment', 'stack_offset', 'flags', 'continuation', 'status')]


class NativeBus:
    """Hard-bounded callbacks for the state and shared interaction accesses."""
    def __init__(self, case, memory, regs, device):
        self.access = interactions.Access(case, memory, regs, device)

        def read(_context, _memory, address, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return self.access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                try:
                    os.write(2, (f'native state40 read callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def write(_context, _memory, address, value, flags):
            try:
                if len(self.access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                self.access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                try:
                    os.write(2, (f'native state40 write callback: {error}\n').encode())
                finally:
                    os._exit(CALLBACK_EXIT)

        def out(_context, port, value, flags):
            try:
                os.write(2, (f'unexpected state40 OUT {port:04X}='
                             f'{value:04X}/{flags:04X}\n').encode())
            finally:
                os._exit(CALLBACK_EXIT)

        self.callbacks = (interactions.READ(read), interactions.WRITE(write),
                          interactions.OUT(out))
        self.bus = interactions.Bus(None, *self.callbacks)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state40-m{mutation}.dll',
                     mutation, 'entity_state40')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state40_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state40_adapter
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
        pc_ptr = ct.byref(pc_binding) if pc_binding is not None else None
        sound_ptr = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = Call(*(initial_regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
                'ss', 'sp', 'flags')))
            out = self.core(ram, ct.byref(call), pc_ptr, sound_ptr,
                            ct.byref(native_bus.bus))
            state = dict(initial_regs)
            state.update(ax=out.value, bx=out.map_cursor, cx=out.count,
                         dx=out.auxiliary_value, si=out.record_cursor,
                         di=out.object_cursor, bp=out.candidate_y,
                         cs=out.code_segment, ds=out.data_segment,
                         es=out.extra_segment, ss=out.stack_segment,
                         sp=out.stack_offset, flags=out.flags,
                         ip=out.continuation)
            status = out.status
        else:
            registers = interactions.Regs(**initial_regs)
            status = self.adapter(ram, ct.byref(registers), pc_ptr, sound_ptr,
                                  ct.byref(native_bus.bus))
            state = {name: getattr(registers, name)
                     for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=state, device=device,
                    events=native_bus.access.events,
                    providers=set(native_bus.access.used), status=status,
                    continuation=state['ip'])


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA device')
        return
    require(actual.state() == expected.state(),
            label + ': VGA registers/latches/planes differ')
    actual_trace = [(event[0], event[1], event[2]) for event in actual.trace]
    expected_trace = [(event[0], event[1], event[2]) for event in expected.trace]
    require(actual_trace == expected_trace, label + ': VGA trace differs')


def compare_events(label, actual, expected):
    require(len(actual) == len(expected),
            f'{label}: event count {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        require(got[:3] == want[:3],
                f'{label}: event {index} {got[:3]!r}/{want[:3]!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{want[3]:04X} '
                f'under mask {want[4]:04X}')


def independent_checks(case, memory, regs, oracle):
    label = case['name']
    ds, si = regs['ds'], regs['si']
    next_cadence = (case.get('cadence', 0) + 1) & 7
    final_y, _final_delta = expected_final_y(case)
    if next_cadence == 0:
        oracle_require(read16(oracle['memory'], ds, si + 8) == 0,
                       label + ': zero cadence did not clear +08 state word')
        oracle_require(read8(oracle['memory'], ds, si + 0x28) == 0,
                       label + ': transition did not reset cadence')
        oracle_require(read8(oracle['memory'], ds, si + 0x24) ==
                       (case.get('entity_flags', 0xA5) & 1),
                       label + ': transition did not preserve only entity flag bit 0')
        oracle_require(final_y is not None and
                       read16(oracle['memory'], ds, si + 2) == final_y,
                       label + ': transition live Y/finish result differs')
        if case.get('name') == 'transition-live-callback-alias':
            oracle_require(read16(oracle['memory'], ds, 0x002E) == 0xFFF8 and
                           read16(oracle['memory'], ds, si + 0x14) == 0xFFF8,
                           label + ': transition did not reread the aliased callback word')
    elif next_cadence < 5:
        if case.get('name') == 'finish-call-overwrites-live-y':
            oracle_require(read16(oracle['memory'], ds, si + 2) == 0x1FEB,
                           label + ': real finish CALL did not overwrite aliased Y')
        else:
            oracle_require(final_y is not None and
                           read16(oracle['memory'], ds, si + 2) == final_y,
                           label + ': movement path did not subtract Y then finish')
    else:
        oracle_require(final_y is None and
                       read16(oracle['memory'], ds, si + 2) ==
                       (case.get('y', 0x20) & 0xFFFF),
                       label + ': cadence stop unexpectedly changed Y')
    writes = [event for event in oracle['events']
              if event[0] == 'write' and
              event[1] == interactions.physical(ds, (si + 0x28) & 0xFFFF)]
    oracle_require(writes and writes[0][2] ==
                   (0 if next_cadence == 0 else next_cadence),
                   label + ': first cadence store/value is missing')
    if case.get('name') == 'finish-call-overwrites-live-y':
        oracle_require(regs['ds'] == regs['ss'] and
                       interactions.physical(ds, si + 2) ==
                       interactions.physical(regs['ss'], regs['sp'] - 2) and
                       read16(oracle['memory'], ds, si + 2) == 0x1FEB,
                       label + ': real finish CALL did not alias live Y')
    if case.get('name') == 'live-ss-vga-interaction-map':
        oracle_require(any(event[0] == 'read' and
                           VGA_BASE <= event[1] < VGA_END
                           for event in oracle['events']),
                       label + ': SS VGA interaction-map read was not observed')


def compare_case(native, case, *, core):
    initial, regs, device, pc_binding, sound_binding = setup(case)
    oracle = original(case, bytearray(initial), dict(regs), copy.deepcopy(device))
    oracle_require((oracle['status'], oracle['continuation']) == (0, CONTINUATION),
                   case['name'] + ': original did not reach normal 1FEB')
    independent_checks(case, initial, regs, oracle)
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
    defined = oracle['flag_mask']
    require(((actual['regs']['flags'] ^ oracle['regs']['flags']) & defined) == 0,
            f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
            f'{oracle["regs"]["flags"]:04X} under {defined:04X}')
    require(actual['memory'] == oracle['memory'], label + ': full RAM differs')
    compare_events(label, actual['events'], oracle['events'])
    compare_device(label, actual['device'], oracle['device'])
    require(actual['providers'] == oracle['used'],
            f'{label}: provider transitions differ')
    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target)
                 for source, source_ip, target in oracle['edges']
                 if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(address for source, address in oracle['sites']
                                        if source == 'main'),
                event_count=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/adlib-symbols.json',
        'metadata/adlib-regions.json', 'metadata/adlib-encodings.json',
        'metadata/tandysnd-symbols.json', 'metadata/tandysnd-regions.json',
        'metadata/tandysnd-encodings.json', 'metadata/pcspeaker-symbols.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json',
        'src/game_code.asm', 'src/entity_graphics.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_state40.c', 'c/entity_state40.h',
        'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/pcspeaker_sym.h', 'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tests/entity_state40.py', 'tests/entity_interactions.py', 'tests/entity_finish.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/pcspeaker_interrupt.py', 'tests/minimap_vga.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/resources.py', 'tools/unpack.py',
        'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory, before_path):
    before = json.loads(Path(before_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(),
                   'state40 inputs changed between provenance snapshot and build')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned static image hash changed')
    oracle_require(len(OWN_INS) == 26 and sum(ins.size for ins in OWN_INS.values()) == 92,
                   'state40 static instruction/byte inventory changed')
    oracle_require(len(OWN_EDGES) == 7 and
                   not any(ins.mnemonic.lower() in ('call', 'int') for ins in OWN_INS.values()),
                   'state40 static edge/call contract changed')

    specs = cases()
    baseline = Native(directory)
    rows, all_sites, all_edges, total_events = [], set(), set(), 0
    for case in specs:
        boundaries = []
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            boundaries.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
            rows.append(row)
        gc.collect()
    oracle_require(all_sites == set(OWN_INS),
                   f'state40 executed-site union differs: {all_sites ^ set(OWN_INS)}')
    oracle_require(all_edges == OWN_EDGES,
                   f'state40 branch-edge union differs: {all_edges ^ OWN_EDGES}')

    witnesses = (
        (1, 'cadence-wrap-zero-transition'),
        (2, 'cadence-four-y-minus-two'),
        (3, 'transition-zero-state-bits'),
        (4, 'transition-live-callback-alias'),
        (5, 'transition-entry-bp-is-not-live-y'),
        (6, 'subtract-live-y-not-entry-bp'),
        (7, 'preserve-entity-flag-bit-zero'),
        (8, 'finish-call-overwrites-live-y'),
    )
    mutations = []
    by_name = {case['name']: case for case in specs}
    for mutation, case_name in witnesses:
        mutant = Native(directory, mutation)
        try:
            compare_case(mutant, by_name[case_name], core=True)
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, case=case_name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'entity state40 mutation {mutation} survived')
        gc.collect()

    oracle_require(before == input_hashes(),
                   'state40 inputs changed during bounded native campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(specs), comparisons=len(rows), cases=rows,
        translated_code_bytes=END - ENTRY, native_code_ranges=[[ENTRY, END]],
        executed_instruction_addresses=sorted(all_sites), branch_edges=sorted(all_edges),
        static_branch_edges=sorted(OWN_EDGES), total_bus_events=total_events,
        mutation_count=len(mutations), mutations=mutations, input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, windows_process_mib=PROCESS_MIB,
                    windows_tree_mib=PROCESS_MIB + 256,
                    original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    native_callback_budget=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='state-0040 parent at 2637..2692; direct 2148 composition through '
               'actual 1FE8 CALL/2EC0 RET or normal 1FEB stop without POP ES; '
               'preserved arithmetic flags, shared interaction-map reads, VGA and '
               'SS/DS/stack aliases; no outer iteration body or gameplay claim'))
    print(f'PASS entity state40: {len(specs)} fixtures at core+adapter; '
          f'{END-ENTRY} bytes/{len(all_sites)} sites/{len(all_edges)} edges; '
          f'{total_events} ordered events; {len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[2] + '/input-hashes.json')
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_state40.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state40-', parent=BUILD) as directory:
        before_path = Path(directory) / 'input-hashes.json'
        write_json(before_path, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                    check=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--original-only']:
        rows, edges = original_only()
        before = input_hashes()
        oracle_require(before == input_hashes(), 'state40 inputs changed in original-only run')
        write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
            case_count=len(rows), executed_instruction_addresses=sorted(
                {address for row in rows for address in row['sites']}),
            branch_edges=sorted(edges), input_hashes=before,
            domain='state-0040 original-only constructed parent cases; no native comparison'))
    else:
        main()
