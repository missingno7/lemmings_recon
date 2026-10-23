"""Bounded original-versus-C checks for the state-0100 entity handler."""
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
ENTRY, END = 0x27E8, 0x283B
PIXEL_ENTRY, PIXEL_RET = 0x5DC6, 0x5DF7
PATTERN_ENTRY, PATTERN_RET = 0x283B, 0x287C
CONTINUATION = 0x1FEB
DATA_SEGMENT = (interactions.MAIN_SEG + 0x09A9) & 0xFFFF
PIXEL_TABLE = 0x547C
PIXEL_MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
ALL_FLAGS = interactions.FLAGS
MAX_INSTRUCTIONS, MAX_EVENTS = 2048, interactions.MAX_BUS_EVENTS
WORKER_SECONDS, PROCESS_MIB = 180, 384
TREE_MIB = 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-state100-differential.json'

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def decoded_span(start, end):
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)}


OWN_INS = decoded_span(ENTRY, END)
PIXEL_INS = decoded_span(PIXEL_ENTRY, PIXEL_RET + 1)
PATTERN_INS = decoded_span(PATTERN_ENTRY, PATTERN_RET + 1)
INTEGRATED_INS = dict(OWN_INS)
INTEGRATED_INS.update(PIXEL_INS)
INTEGRATED_INS.update(PATTERN_INS)
INTEGRATED_INS.update(interactions.MAIN_INS)


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
CALL_RETURNS = {
    0x27EF: ({PIXEL_RET}, 1),
    0x2835: ({PATTERN_RET}, 2),
}


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
    """A bounded original/provider failed to reach a declared boundary."""


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


def pixel_offset(x, y):
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    return ((row * 0xD0) + (x >> 3) + 0x4A40) & 0xFFFF


def pattern_offset(x, y):
    qx = ((x - 4) & 0xFFFF) >> 2
    y_adjusted = (y - 6 - 0x10) & 0xFFFF
    qy = y_adjusted >> 2
    return (qx + ((qy * 0x1A0) & 0xFFFF) + 0x12) & 0xFFFF


def expected_edges(observed):
    return {(source_ip, target)
            for source, source_ip, target in observed['edges']
            if source == 'main' and source_ip in OWN_INS}


def cases():
    """Focused cadence, pixel branch, ordered transition, DF and CALL seams."""
    rows = [
        # The set sample leaves cadence 8 visible and exercises both the
        # conditional fallthrough and the direct JMP to 1FEB.
        dict(name='cadence-mask-and-pixel-set', cadence=7, x=4, y=22,
             sample=0x08),
        dict(name='cadence-byte-wrap-pixel-set', cadence=0xFF, x=0, y=22,
             sample=0x80),
        dict(name='cadence-provider-reread-after-inc', cadence=4, x=4, y=22,
             sample=0x08, provider='cadence-reread',
             cadence_replacement=0x1D),
        dict(name='geometric-known-three-rows', cadence=2, x=4, y=22,
             sample=0),
        dict(name='df-set-three-rows', cadence=6, x=4, y=22, sample=0,
             df=True),
        # Destination=source+1; the first MOVSW changes the byte the following
        # MOVSB reads.  This is instruction-ordered behavior, not memcpy.
        dict(name='sequential-overlap-ds-ss', x=0x18, y=0x16, ds=0x3000,
             ss=0x3000, si=0, sample=0),
        dict(name='custom-ds-mask-table', x=0x002B, y=0x0022, ds=0x3000,
             sample=0),
        dict(name='wrapped-map-product', x=0xFA78, y=0x01F2, sample=0),
        dict(name='record-offset-wrap', x=4, y=22, ds=0x3000,
             si=0xFFF0, sample=0),
        dict(name='physical-stack-word-wrap', x=4, y=22, ss=0xFFFF,
             sp=0x0001, sample=0),
        dict(name='callback-aliases-transition-store', x=4, y=22,
             ds=0x3000, si=0x002A, callback=0x1234, sample=0),
        dict(name='vga-aperture-pixel-read', x=4, y=22, sample=0x08,
             vga=True),
        dict(name='pixel-return-changed-to-pattern-continuation', x=4, y=22,
             sample=0, provider='pixel-return', changed_target=0x2838),
        dict(name='pattern-return-changed-to-pixel-continuation', x=4, y=22,
             sample=0, provider='pattern-return', changed_target=0x27F2),
        # Pattern destination 12h overlaps the live pattern CALL return word.
        # The state transition writes 005A at the first source byte, so RET
        # consumes that actual copied word and stops before executing it.
        dict(name='pattern-output-overwrites-return', x=4, y=22, ds=0x3000,
             ss=0x3000, si=0, sp=0x0014, sample=0),
        dict(name='live-pixel-es-is-saved-for-pattern', x=4, y=22,
             es=0x6200, sample=0),
        dict(name='entry-flags-df-clear', x=0x0027, y=0x0040,
             flags=0x0E47, sample=0),
        dict(name='entry-flags-df-set', x=0x0027, y=0x0040,
             flags=0x0E47, df=True, sample=0),
        dict(name='poisoned-ram-registers', x=0x0123, y=0x0037,
             poison=True, seed=0x27100, sample=0),
    ]
    oracle_require(15 <= len(rows) <= 25,
                   f'state100 fixture count changed: {len(rows)}')
    oracle_require(len({row['name'] for row in rows}) == len(rows),
                   'state100 fixture names are not unique')
    for index, row in enumerate(rows):
        row.setdefault('seed', 0x27100 + index * 47)
        row.setdefault('callback', 0x6170)
        row.setdefault('cadence', 3)
    return rows


class State100Access(interactions.Access):
    """Provider-aware bus for live pixel/pattern return-word changes."""
    def __init__(self, case, memory, regs, device):
        super().__init__(case, memory, regs, device)
        self.native = False
        self.pending = False
        self.pending_cadence = False

    def _provider(self, kind, address):
        super()._provider(kind, address)
        effect = self.case.get('provider')
        ss, sp = self.regs['ss'], self.regs['sp']
        if (effect == 'pixel-return' and kind == 'read' and
                address == physical(self.regs['ds'], self.regs['si'])) and \
                effect not in self.used:
            self.modify_word(ss, sp - 2, self.case['changed_target'])
            self.used.add(effect)

    def _pattern_provider(self, kind, address):
        if self.case.get('provider') != 'pattern-return' or kind != 'write':
            return
        ss, sp = self.regs['ss'], self.regs['sp']
        destination = pattern_offset(self.case.get('x', 4),
                                     self.case.get('y', 22))
        # The high byte of the first forward MOVSW is the last bus byte of
        # that instruction. Flush after MOVSW for Unicorn; native C callbacks
        # own the write synchronously and can update the word immediately.
        if address == physical(ss, destination + 1) and 'pattern-return' not in self.used:
            if self.native:
                self.modify_word(ss, sp - 2, self.case['changed_target'])
                self.used.add('pattern-return')
            else:
                self.pending = True

    def _cadence_provider(self, kind, address):
        if (self.case.get('provider') != 'cadence-reread' or kind != 'write' or
                'cadence-reread' in self.used):
            return
        offset = (self.regs['si'] + 0x28) & 0xFFFF
        if address != physical(self.regs['ds'], offset):
            return
        self.used.add('cadence-reread')
        if self.native:
            self.store(address, self.case['cadence_replacement'])
        else:
            self.pending_cadence = True

    def access(self, kind, address, flags, mask=interactions.FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        self._cadence_provider(kind, address)
        self._pattern_provider(kind, address)
        return result

    def instruction_complete(self):
        if self.pending:
            self.modify_word(self.regs['ss'], self.regs['sp'] - 2,
                             self.case['changed_target'])
            self.used.add('pattern-return')
            self.pending = False
        if self.pending_cadence:
            offset = (self.regs['si'] + 0x28) & 0xFFFF
            self.store(physical(self.regs['ds'], offset),
                       self.case['cadence_replacement'])
            self.pending_cadence = False


def setup(case):
    template = dict(case)
    template.setdefault('load', interactions.MAIN_SEG)
    template.setdefault('ds', DATA_SEGMENT)
    template.setdefault('ss', 0x5000)
    template.setdefault('si', 0x4000)
    template.setdefault('sp', 0xD000)
    template.setdefault('x', 4)
    template.setdefault('y', 22)
    template.setdefault('es', 0x6200)
    template.setdefault('cadence', 1)
    template.setdefault('seed', 0x27100 + len(case['name']))
    raw_flags = template.get('flags', 0x0ED7)
    flags = ((raw_flags & 0x7FD5) | 2) & ~0x0100
    flags = (flags | 0x0400) if template.get('df', False) else (flags & ~0x0400)
    template['flags'] = flags

    # The shared fixture supplies the relocated image, vectors and canonical
    # register ABI. Pixel data is initialized separately in the A000 aperture.
    setup_template = dict(template)
    # The shared fixture seeds samples relative to SS for interaction probes.
    # This handler reads ES:A000 directly, so seed its pixel aperture below.
    setup_template['vga'] = False
    memory, regs, device, _pc, _sound, _ = interactions.setup(setup_template)
    regs.update(cs=template['load'], ip=ENTRY, ds=template['ds'],
                es=template['es'], ss=template['ss'], si=template['si'],
                sp=template['sp'], flags=flags,
                ax=template.get('ax', 0x1357), bx=template.get('bx', 0x2468),
                cx=template.get('cx', 0xACE1), dx=template.get('dx', 0x0055),
                di=template.get('di', 0x3131), bp=template.get('bp', 0x7B2D))
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']

    # Make the table contract explicit even for a noncanonical live DS.
    for index, value in enumerate(PIXEL_MASKS):
        put8(memory, ds, PIXEL_TABLE + index, value)
    put16(memory, ds, si, template['x'])
    put16(memory, ds, si + 2, template['y'])
    put16(memory, ds, 0x002E, template['callback'])
    put8(memory, ds, si + 0x28, template['cadence'])

    # Seed bytes in both directions so DF=1 is a valid copy contract.
    source = (si + 0x16) & 0xFFFF
    seed = template['seed']
    pattern_source = {}
    for delta in range(-8, 16):
        value = (0x31 + ((seed * 13 + delta * 29) & 0x3F)) & 0xFF
        offset = (source + delta) & 0xFFFF
        put8(memory, ds, offset, value)
        pattern_source[offset] = value

    # The routine uses the pixel child's live ES=A000. Store the raw sample in
    # ordinary RAM or in VGA plane zero according to the selected fixture.
    sample_offset = pixel_offset(template['x'], template['y'])
    sample_address = physical(0xA000, sample_offset)
    if template.get('vga'):
        device = MinimapVga(template['seed'] ^ 0xA100, read_map=0)
        device.seq[4], device.seq[2] = 0x06, 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[2], device.gc[4], device.gc[5] = 0, 0, 0
        device.gc[6], device.gc[7], device.gc[8] = 0x05, 0x0F, 0xFF
        for plane in device.planes:
            plane[:] = bytes(65536)
        device.planes[0][sample_offset] = template.get('sample', 0) & 0xFF
        memory[sample_address] = template.get('sample', 0) & 0xFF
    else:
        device = None
        memory[sample_address] = template.get('sample', 0) & 0xFF

    # The entry return is not consumed by this leaf; still initialize it so
    # stack/record aliases have deterministic precedence.
    put16(memory, ss, sp, template.get('outer_return', 0x7A5C))
    return memory, regs, device, pattern_source


def configure_access(case, memory, regs, device):
    return State100Access(case, memory, regs, device)


def original(case, memory, regs, device):
    return interactions.original(
        case, memory, regs, device, False,
        main_instructions=INTEGRATED_INS,
        main_call_returns=CALL_RETURNS,
        stop_offsets={CONTINUATION: 0},
        access_factory=configure_access,
        instruction_limit=MAX_INSTRUCTIONS)


def independent_expectations(case, initial, observed, pattern_source):
    name = case['name']
    if name in ('cadence-mask-and-pixel-set', 'cadence-byte-wrap-pixel-set'):
        expected_cadence = ((case.get('cadence', 1) + 1) & 0xFF) & 0x0F
        oracle_require(get8(observed['memory'], initial['ds'],
                            initial['si'] + 0x28) == expected_cadence,
                       name + ': INC/AND cadence byte mismatch')
    if case.get('provider') == 'cadence-reread':
        oracle_require(get8(observed['memory'], initial['ds'],
                            initial['si'] + 0x28) ==
                       (case['cadence_replacement'] & 0x0F) and
                       'cadence-reread' in observed['used'],
                       name + ': AND did not reread the provider-updated byte')
    if name == 'geometric-known-three-rows':
        # Independent geometry for x=4,y=22: BX=0012h and three rows of
        # MOVSW/MOVSB output at +0000h,+01A0h,+0340h.
        destination = 0x0012
        expected = [pattern_source[(initial['si'] + 0x16 + i) & 0xFFFF]
                    for i in range(9)]
        offsets = [destination + row * 0x1A0 + column
                   for row in range(3) for column in range(3)]
        actual = [get8(observed['memory'], initial['ss'], offset)
                  for offset in offsets]
        oracle_require(actual == expected,
                       name + f': independent 9-byte copy differs {actual!r}/{expected!r}')
    if case.get('provider') == 'pixel-return':
        oracle_require(observed['status'] == 1 and
                       observed['continuation'] == case['changed_target'] and
                       'pixel-return' in observed['used'],
                       name + ': changed pixel return was not consumed live')
    if case.get('provider') == 'pattern-return':
        oracle_require(observed['status'] == 2 and
                       observed['continuation'] == case['changed_target'] and
                       'pattern-return' in observed['used'],
                       name + ': changed pattern return was not consumed live')
    if name == 'pattern-output-overwrites-return':
        source = (initial['si'] + 0x16) & 0xFFFF
        expected = (pattern_source[source] |
                    (pattern_source[(source + 1) & 0xFFFF] << 8))
        oracle_require(observed['status'] == 2 and
                       observed['continuation'] == expected,
                       name + ': pattern copy did not overwrite its live CALL word')
    if name == 'live-pixel-es-is-saved-for-pattern':
        oracle_require(observed['regs']['es'] == 0xA000,
                       name + ': pattern did not restore the pixel child ES value')
    if name == 'callback-aliases-transition-store':
        oracle_require(get16(observed['memory'], initial['ds'], 0x002E) == 0xFFF8 and
                       get16(observed['memory'], initial['ds'], initial['si'] + 0x14) == 0xFFF8,
                       name + ': callback was not read after the aliased +4 store')


def compare_device(label, actual, expected):
    if expected is None:
        require(actual is None, label + ': unexpected VGA provider')
        return
    require(actual is not None, label + ': VGA provider missing')
    require(actual.state() == expected.state(), label + ': VGA state differs')
    got = [(kind, address, value) for kind, address, value, _flags in actual.trace]
    ref = [(kind, address, value) for kind, address, value, _flags in expected.trace]
    require(got == ref, label + ': VGA access trace differs')


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


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-state100-m{mutation}.dll',
                     mutation, 'entity_state100')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_state100_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(Call),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_state100_adapter
        self.adapter.argtypes = [interactions.MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial_memory, initial_regs, initial_device, *, core):
        memory = bytearray(initial_memory)
        regs = dict(initial_regs)
        device = copy.deepcopy(initial_device)
        access = State100Access(case, memory, regs, device)
        access.native = True

        def read(_context, _memory, address, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                return access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    os._exit(GUARD_EXIT)
                access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_EXIT, error)

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_EXIT,
                        f'unexpected state100 OUT {port:04X}={value:04X}')

        callbacks = (interactions.READ(read), interactions.WRITE(write),
                     interactions.OUT(out))
        bus = interactions.Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        if core:
            call = Call(*(regs[name] for name in (
                'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds',
                'es', 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            state.ax, state.bx, state.cx, state.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            state.si, state.di, state.bp = (
                result.record_cursor, result.object_cursor, result.candidate_y)
            state.cs, state.ds, state.es = (
                result.code_segment, result.data_segment, result.extra_segment)
            state.ss, state.sp, state.flags, state.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        final_regs = {name: getattr(state, name) & 0xFFFF
                      for name in interactions.REG_NAMES}
        return dict(memory=bytes(memory), regs=final_regs, device=device,
                    events=access.events, used=access.used,
                    continuation=final_regs['ip'], status=status)


def compare_case(native, case, *, core):
    memory, regs, device, pattern_source = setup(case)
    oracle = original(case, bytearray(memory), dict(regs),
                      copy.deepcopy(device))
    independent_expectations(case, regs, oracle, pattern_source)
    actual = native.run(case, memory, regs, device, core=core)
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
    own_sites = {address for source, address in oracle['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = expected_edges(oracle)
    integrated_sites = {address for source, address in oracle['sites']
                        if source == 'main'}
    return dict(name=case['name'], core=core, status=oracle['status'],
                continuation=oracle['continuation'], sites=sorted(own_sites),
                edges=[list(edge) for edge in sorted(own_edges)],
                integrated_sites=sorted(integrated_sites),
                event_count=len(oracle['events']), steps=oracle['steps'])


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'src/game_code.asm', 'src/entity_graphics.asm', 'src/program.asm',
        'c/entity_state100.c', 'c/entity_state100.h',
        'c/entity_pixel.c', 'c/entity_pixel.h', 'c/entity_pattern.c',
        'c/entity_pattern.h', 'c/lemmings_sym.h', 'c/special_blit.h', 'c/regs.h',
        'tests/entity_state100.py', 'tests/entity_interactions.py',
        'tests/entity_pattern.py', 'tests/entity_pixel.py',
        'tests/minimap_vga.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/unpack.py',
        'tools/resources.py', 'requirements.txt',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_only():
    before = input_hashes()
    oracle_require(len(OWN_INS) == 22 and sum(i.size for i in OWN_INS.values()) == 83,
                   f'state100 identity changed: {len(OWN_INS)} sites, '
                   f'{sum(i.size for i in OWN_INS.values())} bytes')
    oracle_require(len(OWN_EDGES) == 4,
                   f'state100 branch edge count changed: {sorted(OWN_EDGES)}')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed image hash changed')
    specs = cases()
    covered, edges, integrated = set(), set(), set()
    rows = []
    for case in specs:
        memory, regs, device, pattern_source = setup(case)
        observed = original(case, bytearray(memory), dict(regs),
                            copy.deepcopy(device))
        independent_expectations(case, regs, observed, pattern_source)
        if case.get('provider') == 'pixel-return':
            oracle_require((observed['status'], observed['continuation']) ==
                           (1, case['changed_target']),
                           case['name'] + ': wrong pixel CALL return seam')
        elif case.get('provider') == 'pattern-return':
            oracle_require((observed['status'], observed['continuation']) ==
                           (2, case['changed_target']),
                           case['name'] + ': wrong pattern CALL return seam')
        elif case['name'] == 'pattern-output-overwrites-return':
            source = (regs['si'] + 0x16) & 0xFFFF
            expected_return = (pattern_source[source] |
                               (pattern_source[(source + 1) & 0xFFFF] << 8))
            oracle_require((observed['status'], observed['continuation']) ==
                           (2, expected_return),
                           case['name'] + ': live overwritten RET not consumed')
        else:
            oracle_require((observed['status'], observed['continuation']) ==
                           (0, CONTINUATION),
                           case['name'] + f': boundary {observed["status"]}/'
                           f'{observed["continuation"]:04X}')
        own_sites = {address for source, address in observed['sites']
                     if source == 'main' and address in OWN_INS}
        own_edges = expected_edges(observed)
        covered.update(own_sites)
        edges.update(own_edges)
        integrated.update(address for source, address in observed['sites']
                          if source == 'main')
        rows.append(dict(name=case['name'], sites=sorted(own_sites),
                         edges=[list(edge) for edge in sorted(own_edges)],
                         status=observed['status'],
                         continuation=observed['continuation'],
                         events=len(observed['events']), steps=observed['steps']))
        gc.collect()
    oracle_require(covered == set(OWN_INS),
                   f'state100 missing sites {sorted(set(OWN_INS)-covered)}')
    oracle_require(edges == OWN_EDGES,
                   f'state100 edge union differs: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')
    oracle_require(before == input_hashes(),
                   'state100 inputs changed during original-only preflight')
    print(f'PASS entity state100 original: {len(specs)} cases, '
          f'{len(covered)} sites, {len(edges)} edges, '
          f'{sum(row["events"] for row in rows)} events; bounded original only')
    return rows


def worker(directory):
    before = input_hashes()
    oracle_require(len(OWN_INS) == 22 and sum(i.size for i in OWN_INS.values()) == 83,
                   'state100 byte/site accounting changed')
    oracle_require(len(OWN_EDGES) == 4,
                   'state100 owned CFG edge count changed')
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned decompressed image identity changed')
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
                   f'state100 executed site union missing {sorted(set(OWN_INS)-sites)}')
    oracle_require(edges == OWN_EDGES,
                   f'state100 edge union differs: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')

    witnesses = {
        1: 'cadence-mask-and-pixel-set',
        2: 'pixel-return-changed-to-pattern-continuation',
        3: 'pattern-return-changed-to-pixel-continuation',
        4: 'live-pixel-es-is-saved-for-pattern',
        5: 'callback-aliases-transition-store',
        6: 'cadence-mask-and-pixel-set',
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
            raise OracleFailure(f'state100 mutation {mutation} survived {name}')
        gc.collect()
    oracle_require(len(mutations) == 6,
                   'state100 completed mutation witness count changed')
    oracle_require(before == input_hashes(),
                   'state100 input hashes changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_range=[ENTRY, END],
        translated_code_bytes=83, instruction_sites=len(OWN_INS),
        own_branch_edges=len(OWN_EDGES), case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations,
        executed_instruction_addresses=sorted(sites),
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
        domain='Original 27E8..283A state-0100 handler with the actual '
               '5DC6 pixel and 283B pattern CALL/RET frames; logical C core '
               'and register adapter. Ordinary full 1 MiB RAM and optional '
               'A000 VGA read provider, all registers and defined FLAGS, '
               'ordered memory/device events, DF-sensitive pattern copy, '
               'live callback/record aliases, changed RET targets and SS '
               'return-word overwrite seams.'))
    print(f'PASS entity state100: {len(specs)} fixtures x core/adapter, '
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
        raise SystemExit('Unexpected entity-state100 arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-state100-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', directory], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()
