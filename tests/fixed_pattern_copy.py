"""Bounded original/native checks for the 715F fixed-pattern VGA copy leaf."""
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
from unpack import ASSET, unpack, relocated
import entity_interactions as oracle
from minimap_vga import MinimapVga, VGA_BASE, VGA_END


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
ENTRY, RET, END = 0x715F, 0x71C9, 0x71CA
LOAD = 0x1010
MAX_STEPS, MAX_EVENTS = 2_000, 4_096
WORKER_SECONDS, MEMORY_MIB = 420, 384
CALLBACK_BUDGET_EXIT, CALLBACK_ERROR_EXIT = 86, 87
REPORT = BUILD / 'fixed-pattern-copy-differential.json'
ORIGINAL_REPORT = BUILD / 'fixed-pattern-copy-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
REG_NAMES = oracle.REG_NAMES
CALL_REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')
CALL_FIELDS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'code_segment',
               'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
               'flags')
RESULT_FIELDS = CALL_FIELDS + ('continuation', 'status')
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CALL_FIELDS]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in RESULT_FIELDS]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8,
                     ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The pinned original or a bounded guard failed to complete."""


class Mismatch(AssertionError):
    """A completed native result differs from original execution."""


def check(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


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


def sync_seed(memory, device, segment, offset, value):
    """Seed RAM and every plane consistently when a fixture uses VGA as RAM."""
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    if VGA_BASE <= address < VGA_END:
        vga_offset = address - VGA_BASE
        for plane in device.planes:
            plane[vga_offset] = value & 0xFF


def cases():
    specs = [
        dict(name='normal-three-byte-spans', independent=True),
        dict(name='entry-if-set-cli-visible', flags=0x0AD7),
        dict(name='df-backward-two-passes', flags=0x0CD7,
             first_source=0x4300, first_destination=0x4700,
             second_destination=0x5100, independent=True),
        dict(name='first-source-destination-overlap',
             first_source=0x3400, first_destination=0x3400,
             second_destination=0x3800, independent=True),
        dict(name='first-pass-source-offset-wrap', first_source=0xFFFE,
             first_destination=0x7E00, independent=True),
        dict(name='first-pass-destination-offset-wrap', first_source=0x7A00,
             first_destination=0xFFFF, independent=True),
        dict(name='coordinate-add-wraps-before-shr', coordinate_x=0xFFF0,
             byte_1fe0=0x30, coordinate_y=0xFF03, origin=0xFFFC,
             independent=True),
        dict(name='mul-defined-cf-of-at-pop', coordinate_x=0x1234,
             byte_1fe0=0x57, coordinate_y=0xFF01, origin=0x1257),
        dict(name='ds-is-vga-live-fields', ds=0xA000, first_source=0x1500,
             first_destination=0x1A00, second_destination=0x2400),
        dict(name='ds-physical-top-wrap', ds=0xFFFF, first_source=0x2200,
             first_destination=0x2A00, second_destination=0x3100),
        dict(name='ss-vga-stack', ss=0xA000, sp=0x7A00,
             first_source=0x1800, first_destination=0x2100,
             second_destination=0x2800),
        dict(name='ss-word-crosses-physical-top', ss=0xFFFF, sp=0x0011,
             first_source=0x1800, first_destination=0x2100,
             second_destination=0x2800),
        dict(name='ds-ss-live-origin-stack-alias', ds=0x3000, ss=0x3000,
             sp=0x1F7A, first_source=0x1400, first_destination=0x1A00,
             second_destination=0x2500),
        dict(name='input-read-order-provider', provider='read-destination',
             provider_source=0x2880, first_source=0x1200,
             first_destination=0x1A00),
        dict(name='late-first-pass-fields-provider', provider='late-fields',
             provider_first_source=0x2C00,
             provider_first_destination=0x3A00,
             first_source=0x1200, first_destination=0x1A00),
        dict(name='late-origin-inputs-provider', provider='late-origin',
             provider_byte_1fe0=0xD3, provider_coordinate_x=0xFFF0,
             provider_coordinate_y=0xFE19, provider_origin=0x7E01,
             coordinate_x=0x96, coordinate_y=0x64, byte_1fe0=0x02,
             origin=0x0410),
        dict(name='live-push-dx-pop-provider', provider='push-dx',
             provider_saved_dx=0xD134, coordinate_x=0xFFFF,
             byte_1fe0=0x02, coordinate_y=0xF121, origin=0x0009),
        dict(name='live-push-es-pop-ds-provider', provider='push-es',
             provider_saved_es=0x3600, first_source=0x1200,
             first_destination=0x1A00, second_destination=0x2900),
        dict(name='outer-ret-overwritten-by-first-pass-vga', ss=0xA000,
             sp=0x9000, first_source=0x1234, first_destination=0x9000,
             second_destination=0x2600, outer_return=0xD00D),
        dict(name='outer-ret-live-final-store-provider',
             provider='outer-ret', provider_return=0x4B1C,
             first_source=0x1200, first_destination=0x1800,
             second_destination=0x2000),
        dict(name='ordinary-stack-provider-free', ss=0x5200, sp=0xFFFE,
             independent=True),
    ]
    rows = []
    for index, spec in enumerate(specs):
        row = dict(name=spec['name'], seed=0x715F01 + index * 0x101,
                   ax=0x29B7, bx=0xD18E, cx=0x5073, dx=0xA4C1,
                   si=0x6142, di=0xFA38, bp=0x9C25, cs=LOAD, ds=0x3000,
                   es=0x6400, ss=0x5000, sp=0x9000, flags=0x08D7,
                   first_source=0x1200, first_destination=0x1800,
                   second_destination=0x2200, coordinate_x=0x0096,
                   coordinate_y=0x0064, byte_1fe0=0x02, origin=0x0410,
                   outer_return=0xD00D, provider=None)
        row.update(spec)
        rows.append(row)
    check(len(rows) == 21, 'fixed-pattern fixture count changed')
    return rows


def setup(case):
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    code_start = LOAD << 4
    memory[code_start:code_start + len(loaded)] = loaded

    device = MinimapVga(case['seed'] ^ 0x715F, read_map=case.get('read_map', 0))
    # 715F establishes these two registers through literal OUT word writes.
    # Keep all other initial device bits seeded so the read map and latch input
    # remain live wherever the routine has not selected a value.
    memory[VGA_BASE:VGA_END] = device.planes[0]

    regs = dict(ax=case['ax'], bx=case['bx'], cx=case['cx'], dx=case['dx'],
                si=case['si'], di=case['di'], bp=case['bp'], cs=case['cs'],
                ds=case['ds'], es=case['es'], ss=case['ss'], sp=case['sp'],
                ip=ENTRY, flags=case['flags'])
    for offset, value in ((0x0008, case['second_destination']),
                          (0x000A, case['first_source']),
                          (0x000C, 0xA55A),
                          (0x000E, case['first_destination']),
                          (0x0010, case['coordinate_x']),
                          (0x0012, case['coordinate_y']),
                          (0x1F78, case['origin'])):
        sync_seed(memory, device, regs['ds'], offset, value & 0xFFFF)
    sync_seed(memory, device, regs['ds'], 0x1FE0, case['byte_1fe0'])
    sync_seed(memory, device, regs['ss'], regs['sp'], case['outer_return'])
    return memory, regs, device


class Access(oracle.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.stack_target = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
        self.stack_low = None
        self.stack_pairs = 0
        self.pending_stack_words = []
        self.origin_provider_done = False
        self.return_target = physical(regs['ss'], regs['sp'])
        destination_direction = -1 if regs['flags'] & 0x0400 else 1
        final_destination = (case['second_destination'] +
                             destination_direction * 0x2F) & 0xFFFF
        self.final_second_pass_byte = physical(0xA000, final_destination)

    def _set_word(self, segment, offset, value):
        self.modify_word(segment, offset & 0xFFFF, value & 0xFFFF)

    def _apply_late_fields(self):
        case = self.case
        ds = self.regs['ds']
        self._set_word(ds, 0x000A, case['provider_first_source'])
        self._set_word(ds, 0x000E, case['provider_first_destination'])

    def _apply_origin(self):
        case = self.case
        ds = self.regs['ds']
        put8(self.memory, ds, 0x1FE0, case['provider_byte_1fe0'])
        self._set_word(ds, 0x0010, case['provider_coordinate_x'])
        self._set_word(ds, 0x0012, case['provider_coordinate_y'])
        self._set_word(ds, 0x1F78, case['provider_origin'])
        if self.mirror:
            for offset, value, width in (
                    (0x1FE0, case['provider_byte_1fe0'], 1),
                    (0x0010, case['provider_coordinate_x'], 2),
                    (0x0012, case['provider_coordinate_y'], 2),
                    (0x1F78, case['provider_origin'], 2)):
                address = physical(ds, offset)
                for delta in range(width):
                    self.mirror((address + delta) & MASK,
                                self.memory[(address + delta) & MASK])

    def _provider(self, kind, address, value=None):
        case = self.case
        provider = case.get('provider')
        if (provider == 'read-destination' and kind == 'read' and
                address == physical(self.regs['ds'], 0x000E) and
                provider not in self.used):
            self._set_word(self.regs['ds'], 0x000A, case['provider_source'])
            self.used.add(provider)

        if (provider == 'late-origin' and kind == 'write' and
                VGA_BASE <= address < VGA_END and provider not in self.used):
            self._apply_origin()
            self.used.add(provider)

        if (provider == 'outer-ret' and kind == 'write' and
                address == self.final_second_pass_byte and provider not in self.used):
            self._set_word(self.regs['ss'], self.regs['sp'],
                           case['provider_return'])
            self.used.add(provider)

        if provider in ('push-dx', 'push-es') and kind == 'write':
            # oracle.Access invokes _provider before it mirrors a CPU write.
            # Only the post-write call made by access() carries a value, so
            # ignore the pre-write notification and patch a completed word.
            if value is None:
                return
            high_address = (self.stack_target + 1) & MASK
            if address == self.stack_target:
                self.stack_low = value
            elif address == high_address and self.stack_low is not None:
                self.stack_pairs += 1
                if ((provider == 'push-dx' and self.stack_pairs == 1) or
                        (provider == 'push-es' and self.stack_pairs == 2)):
                    replacement = (case['provider_saved_dx'] if provider == 'push-dx'
                                   else case['provider_saved_es'])
                    offset = (self.regs['sp'] - 2) & 0xFFFF
                    if self.native:
                        self._set_word(self.regs['ss'], offset, replacement)
                    else:
                        self.pending_stack_words.append(
                            (self.regs['ss'], offset, replacement))
                    self.used.add(provider)
                self.stack_low = None

    def instruction_complete(self):
        # Unicorn's write hook runs before its instruction finishes. Apply a
        # live stack-word replacement only after PUSH has committed both bytes.
        pending, self.pending_stack_words = self.pending_stack_words, []
        for segment, offset, value in pending:
            self._set_word(segment, offset, value)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('fixed-pattern callback event budget exhausted')
        address &= MASK
        result = super().access(kind, address, flags, mask, value)
        self._provider(kind, address, result)
        return result

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('fixed-pattern callback event budget exhausted')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        if self.case.get('provider') == 'late-fields' and 'late-fields' not in self.used:
            self._apply_late_fields()
            self.used.add('late-fields')


def original(case, memory, regs, device, *, core):
    observers = []
    result = oracle.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        access_factory=lambda c, m, r, d: observers.append(
            Access(c, m, r, d)) or observers[-1],
        instruction_limit=MAX_STEPS)
    result['providers'] = set(observers[0].used)
    result['access'] = observers[0]
    return result


def expected_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.lower().startswith('loop'):
            target = ins.operands[0].imm & 0xFFFF
            edges.add((address, target))
            if ins.mnemonic.lower() != 'jmp':
                edges.add((address, (address + ins.size) & 0xFFFF))
    return edges


def direct_byte(memory, segment, offset):
    return memory[physical(segment, offset)]


def direct_word(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def independent_planes(case, initial, initial_device, expected):
    """Simulate the ordinary-stack 16x3 source/destination equations alone."""
    if not case.get('independent'):
        return 0
    memory = bytearray(initial)
    planes = [bytearray(plane) for plane in initial_device.planes]
    latches = list(initial_device.latches)
    read_map = initial_device.gc[4] & 3
    seq_mask = 0x0F
    ds = case['ds']
    df = -1 if case['flags'] & 0x0400 else 1

    def read_physical(address):
        address &= MASK
        if VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            latches[:] = [plane[offset] for plane in planes]
            value = latches[read_map]
            memory[address] = value
            return value
        return memory[address]

    def read8(segment, offset):
        return read_physical(physical(segment, offset))

    def read16(segment, offset):
        address = physical(segment, offset)
        return read_physical(address) | (read_physical(address + 1) << 8)

    def write_external_word(segment, offset, value):
        address = physical(segment, offset)
        memory[address] = value & 0xFF
        memory[(address + 1) & MASK] = (value >> 8) & 0xFF

    def write8(segment, offset, value):
        address = physical(segment, offset)
        if VGA_BASE <= address < VGA_END:
            target = address - VGA_BASE
            for plane_index, plane in enumerate(planes):
                if seq_mask & (1 << plane_index):
                    plane[target] = latches[plane_index]
        memory[address] = value & 0xFF

    # The two setup OUTs select Map Mask=0F and Graphics Controller write mode 1.
    if case.get('provider') == 'late-fields':
        write_external_word(ds, 0x000A, case['provider_first_source'])
        write_external_word(ds, 0x000E, case['provider_first_destination'])

    first_destination = read16(ds, 0x000E)
    if case.get('provider') == 'read-destination':
        write_external_word(ds, 0x000A, case['provider_source'])
    source = read16(ds, 0x000A)
    destination = first_destination
    origin_provider_pending = case.get('provider') == 'late-origin'
    plane_writes = 0
    for _row in range(16):
        for _column in range(3):
            byte = read8(0xA000, source)
            write8(0xA000, destination, byte)
            plane_writes += 4
            source = (source + df) & 0xFFFF
            destination = (destination + df) & 0xFFFF
            if origin_provider_pending:
                put8(memory, ds, 0x1FE0, case['provider_byte_1fe0'])
                write_external_word(ds, 0x0010, case['provider_coordinate_x'])
                write_external_word(ds, 0x0012, case['provider_coordinate_y'])
                write_external_word(ds, 0x1F78, case['provider_origin'])
                origin_provider_pending = False
        destination = (destination + 0x29) & 0xFFFF

    x_value = read16(ds, 0x0010)
    dx = (read8(ds, 0x1FE0) + x_value) & 0xFFFF
    dx >>= 3
    y_value = read16(ds, 0x0012)
    source = ((y_value * 0x2C) & 0xFFFF)
    # PUSH DX/POP DX keeps this quotient in live SS memory. These independent
    # fixtures use an ordinary, non-aliasing stack and no stack provider.
    source = (source + dx) & 0xFFFF
    source = (source + read16(ds, 0x1F78)) & 0xFFFF
    write_external_word(ds, 0x000C, source)
    destination = read16(ds, 0x0008)
    source_segment = 0xA000

    for _row in range(16):
        for _column in range(3):
            byte = read8(source_segment, source)
            write8(0xA000, destination, byte)
            plane_writes += 4
            source = (source + df) & 0xFFFF
            destination = (destination + df) & 0xFFFF
        source = (source + 0x29) & 0xFFFF

    for plane_index in range(4):
        check(bytes(planes[plane_index]) ==
              bytes(expected['device'].planes[plane_index]),
              f"{case['name']}: independent VGA plane {plane_index} differs")
    check(latches == expected['device'].latches,
          case['name'] + ': independent VGA latches differ')
    return plane_writes


def validate(case, initial, initial_device, regs, expected, *, core):
    check(expected['status'] == 0, case['name'] + ': original did not reach READY')
    wanted_providers = {case['provider']} if case.get('provider') else set()
    check(expected['providers'] == wanted_providers,
          case['name'] + ': provider transition differs')
    check(expected['regs']['bp'] == regs['ds'],
          case['name'] + ': BP did not retain entry DS')
    check(expected['regs']['es'] == 0xA000,
          case['name'] + ': ES did not retain the VGA aperture')
    check(expected['regs']['ds'] == regs['ds'],
          case['name'] + ': DS was not restored from BP')
    check(expected['regs']['cx'] == 0,
          case['name'] + ': a sixteen-row pass did not finish')
    check((expected['regs']['flags'] & 0x0400) == (regs['flags'] & 0x0400),
          case['name'] + ': DF changed')
    check(expected['regs']['flags'] & 0x0200,
          case['name'] + ': routine did not force IF on')
    if core:
        check(expected['regs']['ip'] == RET,
              case['name'] + ': core did not stop immediately before RET')
        check(expected['regs']['sp'] == regs['sp'],
              case['name'] + ': core did not restore entry SP')
    else:
        check(expected['regs']['ip'] == get16(expected['memory'],
              expected['regs']['ss'], regs['sp']),
              case['name'] + ': actual outer RET did not use the live word')
        check(expected['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
              case['name'] + ': actual outer RET did not advance SP')
        if case['name'] == 'outer-ret-overwritten-by-first-pass-vga':
            check(expected['regs']['ip'] != case['outer_return'],
                  case['name'] + ': VGA copy did not overwrite the outer RET')
        if case.get('provider') == 'outer-ret':
            check(expected['regs']['ip'] == case['provider_return'],
                  case['name'] + ': final-store provider missed the live RET')
    if case['name'] == 'mul-defined-cf-of-at-pop':
        target = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
        pop_reads = [event for event in expected['events']
                     if event[0] == 'read' and event[1] == target]
        check(pop_reads and (pop_reads[0][4] & 0x08D5) == 0x0801,
              'MUL CF/OF contract was not captured at POP DX')
    if case.get('provider') == 'push-dx':
        target = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
        wanted = case['provider_saved_dx']
        pop_reads = [event for event in expected['events']
                     if event[0] == 'read' and
                     event[1] in (target, (target + 1) & MASK)]
        check([(event[1], event[2]) for event in pop_reads[:2]] ==
              [(target, wanted & 0xFF),
               ((target + 1) & MASK, wanted >> 8)],
              case['name'] + ': POP DX did not consume the live provider word')
    if case.get('provider') == 'push-es':
        stack_offset = (regs['sp'] - 2) & 0xFFFF
        check(direct_word(expected['memory'], regs['ss'], stack_offset) ==
              case['provider_saved_es'],
              case['name'] + ': PUSH ES stack word was not replaced live')
        source = get16(expected['memory'], regs['ds'], 0x000C)
        df = -1 if regs['flags'] & 0x0400 else 1
        expected_reads = []
        for _row in range(16):
            for _column in range(3):
                expected_reads.append(physical(0x3600, source))
                source = (source + df) & 0xFFFF
            source = (source + 0x29) & 0xFFFF
        expected_addresses = set(expected_reads)
        observed_reads = [event[1] for event in expected['events']
                          if event[0] == 'read' and
                          event[1] in expected_addresses]
        check(observed_reads == expected_reads,
              case['name'] + ': second MOVSB pass did not read from live DS')
    return independent_planes(case, initial, initial_device, expected)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'fixed-pattern-copy-m{mutation}.dll',
                     mutation, 'fixed_pattern_copy')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_copy_fixed_pattern_vga_spans_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_copy_fixed_pattern_vga_spans_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(oracle.Regs), ct.POINTER(Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)

        def die(error):
            code = CALLBACK_BUDGET_EXIT if 'budget' in str(error).lower() else CALLBACK_ERROR_EXIT
            try:
                os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
            finally:
                os._exit(code)

        def read(_context, _memory, address, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    raise OracleFailure('fixed-pattern callback event budget exhausted')
                return access.access('read', address, flags)
            except BaseException as error:
                die(error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    raise OracleFailure('fixed-pattern callback event budget exhausted')
                access.access('write', address, flags, value=value)
            except BaseException as error:
                die(error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags)
            except BaseException as error:
                die(error)

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        if core:
            call = Call(*[regs[name] for name in CALL_REGS])
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for role, name in zip(CALL_FIELDS, CALL_REGS):
                target = {'code_segment': 'cs', 'data_segment': 'ds',
                          'extra_segment': 'es', 'stack_segment': 'ss',
                          'stack_offset': 'sp'}.get(role, role)
                setattr(state, target, getattr(result, role))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in REG_NAMES},
                    status=status, events=access.events, providers=set(access.used),
                    device=device)


def compare_result(actual, expected, label):
    require(actual['status'] == expected['status'], label + ': status differs')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    for name in REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f"{label}: {name} {actual['regs'][name]:04X}/"
                f"{expected['regs'][name]:04X} mask={mask:04X}")
    require(actual['providers'] == expected['providers'], label + ': providers differ')
    require(len(actual['events']) == len(expected['events']),
            label + ': ordered bus event count differs')
    for index, (got, want) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == want[:3],
                f'{label}: event {index} differs: {got!r}/{want!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS differ '
                f'{got[3]:04X}/{want[3]:04X} mask={want[4]:04X}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA state differs')
    require([event[:3] for event in actual['device'].trace] ==
            [event[:3] for event in expected['device'].trace],
            label + ': ordered VGA device trace differs')


def compare(native, case, *, core):
    memory, regs, device = setup(case)
    expected = original(case, memory, regs, device, core=core)
    independent_bytes = validate(case, memory, device, regs, expected, core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    compare_result(actual, expected,
                   case['name'] + (' core' if core else ' adapter'))
    return expected, independent_bytes


def edges_for(rows):
    return {tuple(edge) for row in rows for edge in row['edges']}


def collect(expected, case, core, independent_bytes):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(address for scope, address in expected['sites']
                             if scope == 'main'),
                edges=sorted([source, target]
                             for scope, source, target in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                independent_plane_bytes=independent_bytes)


def input_hashes():
    paths = {
        'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat',
        'src/fixed_pattern_drawing.asm',
        'c/fixed_pattern_copy.c', 'c/fixed_pattern_copy.h',
        'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/fixed_pattern_copy.py', 'tests/entity_interactions.py',
        'tests/minimap_vga.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py', 'tools/unpack.py',
    }
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def rows_original():
    before = input_hashes()
    check(len(IMAGE) == 82_906 and
          sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
          'static main image identity changed')
    check(len(OWN_INS) == 48 and END - ENTRY == 107 and
          ENTRY in OWN_SITES and RET in OWN_SITES,
          '715F byte or instruction inventory changed')
    rows = []
    for case in cases():
        print(f"CHECKED original {case['name']}", flush=True)
        memory, regs, device = setup(case)
        for core in (True, False):
            expected = original(case, memory, regs, device, core=core)
            independent_bytes = validate(case, memory, device, regs,
                                          expected, core=core)
            rows.append(collect(expected, case, core, independent_bytes))
        gc.collect()
    sites = {address for row in rows for address in row['sites']}
    check(sites == OWN_SITES, 'original campaign did not execute all 48 sites')
    check(edges_for(rows) == expected_edges(),
          'original campaign did not cover both LOOP edges in each pass')
    check(before == input_hashes(), 'inputs changed during original campaign')
    return before, rows


def publish(path, before, rows, mutants=None):
    sites = {address for row in rows for address in row['sites']}
    branches = edges_for(rows)
    check(sites == OWN_SITES, f'missing instruction sites: {OWN_SITES - sites}')
    check(branches == expected_edges(),
          f'missing branch outcomes: {expected_edges() - branches}')
    if mutants is not None:
        check(len(mutants) == 10 and
              {item['mutation'] for item in mutants} == set(range(1, 11)),
              'native campaign did not complete all ten mutation witnesses')
    report = dict(image='main', image_sha256=sha(IMAGE), entry=ENTRY, ret=RET,
        end=END, case_count=len(cases()), comparison_count=len(rows),
        translated_code_bytes=END - ENTRY, instruction_site_count=len(OWN_SITES),
        routine_bytes=IMAGE[ENTRY:END].hex(),
        executed_instruction_addresses=sorted(sites),
        unique_executed_instruction_addresses=sorted(sites),
        branch_instruction_addresses=sorted({source for source, _target in branches}),
        branch_edges=sorted([source, target] for source, target in branches),
        branch_edge_count=len(branches),
        unique_branch_edges=sorted([source, target] for source, target in branches),
        unique_branch_edge_count=len(branches),
        boundary_instruction_site_sum=sum(len(row['sites']) for row in rows),
        boundary_branch_edge_sum=sum(len(row['edges']) for row in rows),
        ordered_bus_event_boundary_sum=sum(row['events'] for row in rows),
        instruction_step_boundary_sum=sum(row['steps'] for row in rows),
        independent_plane_byte_sum=sum(row['independent_plane_bytes'] for row in rows),
        original_only=mutants is None, mutation_count=len(mutants or []),
        mutations=mutants or [], rows=rows, input_hashes=before,
        dependencies=sorted(before),
        exact_asm_source='src/fixed_pattern_drawing.asm',
        exact_asm_sha256=before['src/fixed_pattern_drawing.asm'],
        domains=[
            '715F..71C9 core before RET and adapter through the actual live RET',
            '48 instruction sites and both LOOP edges for each 16-row pass',
            'DF clear/set across all 16 rows, with three MOVSB operations per row',
            'live DS/ES/SS, 16-bit offsets, physical top wrap, VGA segment aliases',
            'ordered sequencer/graphics-controller OUTs and source-read/latch/write order',
            'live PUSH DX/POP DX quotient and PUSH ES/POP DS segment words',
            'wrapped coordinate addition before SHR, low-word MUL and defined CF/OF at POP',
            'provider changes to first-pass fields, late origin fields and live RET word',
            'whole RAM, all registers, defined FLAGS, ordered bus events and VGA state',
            'independent four-plane byte equations for ordinary-stack source/destination spans',
        ],
        quirks=[
            'BP retains entry DS; final MOV DS,BP restores entry DS after the second pass',
            'ES remains A000 and STI forces IF on; DF remains live',
            'the live SS quotient word carries DX across MUL, whose defined flags are CF and OF',
            'the live PUSH ES word supplies POP DS and remains aliasable stack memory',
            'first-pass rows add 29h to DI; second-pass rows add 29h to SI',
            'normal final flags come from the last ADD SI,29h before LOOP/STI/MOV/RET',
        ],
        limits=dict(timeout_seconds=WORKER_SECONDS, process_commit_mib=MEMORY_MIB,
                    original_instruction_hook_limit=MAX_STEPS,
                    bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=CALLBACK_BUDGET_EXIT,
                    callback_error_exit=CALLBACK_ERROR_EXIT))
    write_json(path, report)
    print(f"PASS fixed-pattern copy: {len(cases())} fixtures/{len(rows)} boundaries, "
          f"{len(sites)} unique sites/{len(branches)} unique edges, "
          f"{report['ordered_bus_event_boundary_sum']} boundary events, "
          f"{len(mutants or [])} mutants", flush=True)


def original_worker():
    before, rows = rows_original()
    publish(ORIGINAL_REPORT, before, rows)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == input_hashes(), 'input hash snapshot differs')
    native = Native(directory)
    rows = []
    by_name = {case['name']: case for case in cases()}
    for case in cases():
        for core in (True, False):
            expected, independent_bytes = compare(native, case, core=core)
            rows.append(collect(expected, case, core, independent_bytes))
        gc.collect()

    witnesses = (
        (1, 'entry-if-set-cli-visible', True),
        (2, 'input-read-order-provider', True),
        (3, 'df-backward-two-passes', True),
        (4, 'normal-three-byte-spans', True),
        (5, 'live-push-es-pop-ds-provider', True),
        (6, 'live-push-dx-pop-provider', True),
        (7, 'first-source-destination-overlap', True),
        (8, 'df-backward-two-passes', True),
        (9, 'entry-if-set-cli-visible', True),
        (10, 'outer-ret-overwritten-by-first-pass-vga', False),
    )
    mutants = []
    for number, name, core in witnesses:
        try:
            compare(Native(directory, number), by_name[name], core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=number, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'FIXED_PATTERN_COPY_MUTATION={number} survived')
        gc.collect()
    check(before == input_hashes(), 'inputs changed during native campaign')
    publish(REPORT, before, rows, mutants)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:] == ['--original-worker']:
        original_worker()
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--original-worker'], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: fixed_pattern_copy.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='fixed-pattern-copy-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(input_hashes(), sort_keys=True))
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory, str(snapshot)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)


if __name__ == '__main__':
    main()
