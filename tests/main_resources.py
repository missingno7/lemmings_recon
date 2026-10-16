"""Bounded parent/original/native campaign for LoadMainResourceSections."""
from __future__ import annotations

from array import array
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
import dat_files as files
import dat_io as io_oracle
import dat_io_c as io_c
import dat_load as loader
import dat_section as decoder
import entity_interactions as oracle
import entity_sprite_bank_layout as sprite_layout
import entity_sprite_banks as sprite_parent
import fixed_word_banks as fixed_words
import generated_graphics as graphics_parent
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from resources import decode_section, section_spans
import sprite_bank as sprite_leaf
import sprite_shift_banks as sprite_shift
import sprite_wide_banks as sprite_wide
import vga_plane_copy as plane_copy
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_INTR, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                     UC_HOOK_INSN)
from unicorn import x86_const as x


IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
LOAD, STATIC_DS = 0x1010, 0x19B9
ENTRY, RET, END = 0x58D2, 0x59BA, 0x59BB
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
MAIN_DATA = (ROOT / 'assets' / 'main.dat').read_bytes()
SPANS = section_spans(MAIN_DATA)
SECTIONS = tuple(decode_section(MAIN_DATA[a:b])[0] for a, b in SPANS)
MAX_STEPS, MAX_EVENTS, MAX_DOS_EVENTS = 16_000_000, 2_000_000, 4096
WORKER_SECONDS, MEMORY_MIB = 1500, 512
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'main-resources-differential.json'
ORIGINAL_REPORT = BUILD / 'main-resources-original-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True

OWN_INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
TAIL = loader.TAIL
TAIL_INS = {i.address: i for i in MD.disasm(IMAGE[TAIL:TAIL + 6], TAIL)}
PARENT_INS = OWN_INS | TAIL_INS

# The parent invokes these intact, identified routines. Keeping their original
# instruction maps here bounds Unicorn to the translated composition only.
MAIN_INS = (PARENT_INS | loader.INS | sprite_parent.MAIN_INS |
            fixed_words.MAIN_INS | graphics_parent.INS | plane_copy.OWN_INS)
MAIN_INS = dict(MAIN_INS)
BRANCHES = {pc for pc, ins in MAIN_INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or
            ins.mnemonic.lower().startswith(('loop', 'jcxz'))}
PARENT_BRANCHES = {pc for pc, ins in OWN_INS.items()
                   if ins.group(capstone.CS_GRP_JUMP) or
                   ins.mnemonic.lower().startswith(('loop', 'jcxz'))}

CALL_TARGETS = {
    0x58E0: (0x1B79, 0x58E3),
    0x58E5: (0x59BB, 0x58E8),
    0x58E8: (0x5CC1, 0x58EB),
    0x58F9: (0x1BA9, 0x58FC),
    0x58FE: (0x5AC1, 0x5901),
    0x590F: (0x1BA9, 0x5912),
    0x5927: (0x57D1, 0x592A),
    0x594D: (0x1BA9, 0x5950),
    0x5960: (0x1BA9, 0x5963),
    0x5972: (0x1BA9, 0x5975),
    0x598A: (0x1BA9, 0x598D),
    0x59A1: (0x57D1, 0x59A4),
}
FATAL_OFFSETS = {0x1949, 0x04D0}

ROLE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'code_segment',
              'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
              'flags')
REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
        'ss', 'sp', 'ip', 'flags')
CALL_REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')
REG_ID = {name: getattr(x, 'UC_X86_REG_' + name.upper()) for name in REGS}
MEM = ct.POINTER(ct.c_uint8)


class MainCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in ROLE_NAMES]


class MainResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ROLE_NAMES + ('continuation', 'status', 'child_entry',
                              'child_status')]


class CompactEvents:
    """Bounded exact event tuples, packed as five 32-bit words (20 bytes)."""
    def __init__(self):
        self.data = array('I')

    def __len__(self):
        return len(self.data) // 5

    def append(self, event):
        kind, address, value, flags, mask = event
        self.data.extend(({'read': 0, 'write': 1, 'out': 2}[kind],
                          address, value, flags, mask))

    def __iter__(self):
        for n in range(0, len(self.data), 5):
            kind = ('read', 'write', 'out')[self.data[n]]
            yield (kind, *self.data[n + 1:n + 5])


class OracleFailure(AssertionError):
    """The bounded original/provider failed to complete its declared path."""


class Mismatch(AssertionError):
    """A completed native/original comparison differs."""


def check(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get16(memory, segment, offset):
    p = physical(segment, offset)
    return memory[p] | (memory[(p + 1) & MASK] << 8)


def put16(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 0xFF
    memory[(p + 1) & MASK] = (value >> 8) & 0xFF


def put_bytes(memory, segment, offset, values):
    p = physical(segment, offset)
    for n, value in enumerate(values):
        memory[(p + n) & MASK] = value


def validate_static():
    check(len(SPANS) == 7, 'pinned MAIN.DAT must contain seven sections')
    check(tuple(map(len, SECTIONS)) ==
          (0x5270, 0x0184, 0x20C0, 0xF210, 0x8CF0, 0x02F6, 0x2020),
          'pinned MAIN.DAT decoded section extents changed')
    check(len(OWN_INS) == 101 and END - ENTRY == 0xE9,
          'LoadMainResourceSections static boundary changed')
    check(len(TAIL_INS) == 4 and set(CALL_TARGETS) ==
          {pc for pc, ins in OWN_INS.items() if ins.mnemonic == 'call'},
          'parent CALL inventory or shared DAT-return map changed')
    check(IMAGE[0x5967:0x5969] == b'\xB8\x42' and
          any(r.get('offset') == 0x5968 for r in META.get('relocations', [])),
          'section-5 immediate must retain the declared relocation at CS:5968')
    check(len(sprite_layout.GROUPS) == 15 and
          sum(row['count'] for row in sprite_layout.GROUPS) + 1 == 337,
          'section-zero parent must execute all 337 pinned sprite calls')


def cases():
    """Full pinned paths plus focused live-provider/return witnesses."""
    base = dict(load_segment=LOAD, data_segment=None,
                stack_segment=0x9000, stack_offset=0xF000,
                allocation_segment=0x3000, option=0, provider=None,
                seed=0x58D200)
    specs = [
        dict(name='pinned-main-gate-clear', full=True, gate=0),
        dict(name='pinned-main-gate-ff', full=True, gate=0xFF),
        dict(name='pinned-main-gate-one', full=True, gate=1),
        dict(name='provider-live-saved-ds-and-bx', full=True, gate=0,
             providers=('saved-ds', 'saved-bx')),
        dict(name='provider-changed-loader-return', gate=0,
             provider='changed-loader-return'),
        dict(name='provider-changed-top-graphics-return', gate=0,
             provider='graphics-return'),
        dict(name='provider-nested-sprite-return', gate=0,
             provider='nested-sprite-return'),
        dict(name='provider-outer-ret', full=True, gate=0,
             provider='outer-return'),
        dict(name='live-code-segment-operand', full=True, gate=0,
             provider='sound-segment', sound_segment=0x2200),
        dict(name='load-segment-1213', full=True, gate=0,
             load_segment=0x1213, data_segment=0x1BBC),
        dict(name='attribute-error-fatal', gate=0,
             attribute_errors=1, retry_enabled=0),
        dict(name='first-header-read-fatal', gate=0,
             read_error_index=0),
        dict(name='payload-read-fatal', gate=0,
             read_error_index=1),
        dict(name='attribute-retry-recovers', gate=0,
             attribute_errors=1, retry_enabled=0xFF, retry_count=1),
    ]
    return [dict(base, seed=base['seed'] + n * 0x101, **spec)
            for n, spec in enumerate(specs)]


def setup(case):
    """Build one relocated executable and ordinary selector-backed RAM image."""
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    code = relocated(IMAGE, META['relocations'], case['load_segment'])
    code_base = case['load_segment'] << 4
    memory[code_base:code_base + len(code)] = code

    allocation = case['allocation_segment']
    selectors = {
        0x1FE4: allocation,
        0x1FE6: (allocation + 0x1000) & 0xFFFF,
        0x1FE8: (allocation + 0x2D0C) & 0xFFFF,
        0x1FEA: (allocation + 0x2E72) & 0xFFFF,
        0x1FEC: (allocation + 0x2F02) & 0xFFFF,
        0x1FEE: (allocation + 0x2F7E) & 0xFFFF,
    }
    data_segment = case.get('data_segment')
    if data_segment is None:
        data_segment = (case['load_segment'] + 0x09A9) & 0xFFFF
    for offset, value in selectors.items():
        put16(memory, data_segment, offset, value)
    put16(memory, data_segment, 0x1FE4, selectors[0x1FE4])
    # Keep the code's relocated paragraph operand live; normal execution reads
    # LOAD+0842 from 5968, while this explicit provider changes only that word.
    sound_segment = case.get('sound_segment',
                             (case['load_segment'] + 0x0842) & 0xFFFF)

    # The file loader is deliberately direct: the complete pinned raw stream is
    # provided by DOS AH=3F below; no cache state or decoded shadow is used.
    for name, value in dict(
            DatCacheEnabled=0, DatCacheSelected=0, DatCacheRecordCount=0,
            DatCriticalErrorFlag=0,
            DatRetryEnabled=case.get('retry_enabled', 0)).items():
        memory[physical(data_segment, loader.field(name))] = value
    for name, value in dict(
            DatCacheBaseSegment=allocation, DatCacheFreeSegment=allocation,
            DatCacheFreeOffset=0, DatCacheRemainingParagraphs=0x5571).items():
        put16(memory, data_segment, loader.field(name), value)
    memory[physical(data_segment, 0x200E)] = case['gate']

    filename = b'main.dat\0'
    put_bytes(memory, data_segment, 0x252B, filename)
    regs = dict(ax=0xBEEF, bx=0xC17D, cx=0x4A93, dx=0xB271,
                si=0x1234, di=0xABCD, bp=0x79A3,
                cs=case['load_segment'], ds=data_segment,
                es=0x3510, ss=case['stack_segment'],
                sp=case['stack_offset'], ip=ENTRY, flags=0x0AD7)
    put16(memory, regs['ss'], regs['sp'], 0xD00D)

    if 'saved-ds' in case.get('providers', ()):
        # The live DS provider points to a second complete, valid frame.
        # Copy only static data, before the loaded output allocation at 3000.
        source, target = physical(data_segment, 0), physical(0x2500, 0)
        memory[target:target + 0x537C] = memory[source:source + 0x537C]

    device = MinimapVga(case['seed'] ^ 0x57D1, read_map=0)
    device.seq[2] = 0x0F
    device.seq[4] = 0x06
    for index in (0, 1, 3, 4, 5):
        device.gc[index] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    memory[VGA_BASE:VGA_END] = device.planes[0]
    # DATA relocation words used by Loader, CheckDatFile and ReadDatBytes are
    # live code operands.  The normal DS happens to equal the first one.
    return memory, regs, device, selectors, sound_segment


GRAPHICS_DOMAINS = (sprite_parent.MAIN_INS | fixed_words.MAIN_INS |
                    graphics_parent.INS | plane_copy.OWN_INS)
LOGGED_SITES = set(OWN_INS) | {TAIL + 5} | set(GRAPHICS_DOMAINS)
PARENT_RETURN_SITES = {
    0x58E0: 0x1BAE, 0x58E5: 0x5AC0, 0x58E8: 0x5D17,
    0x58F9: 0x1BAE, 0x58FE: 0x5B10, 0x590F: 0x1BAE,
    0x5927: 0x5826, 0x594D: 0x1BAE, 0x5960: 0x1BAE,
    0x5972: 0x1BAE, 0x598A: 0x1BAE, 0x59A1: 0x5826,
}


class Access:
    """The parent's declared raster bus, shared by original and C runs."""
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.native = native
        self.events = CompactEvents()
        self.used = set()
        self.enabled = False
        self.mirror = None
        self.pending = []
        self.low = {}
        self.call_return_low = None
        self.call_return_seen = False
        self.stack_return_lows = set()

    def _write(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror:
            self.mirror(address, value & 0xFF)

    def modify_word(self, segment, offset, value):
        address = physical(segment, offset)
        self._write(address, value)
        self._write(address + 1, value >> 8)
        if self.device is not None:
            for delta, byte in enumerate((value & 255, (value >> 8) & 255)):
                at = (address + delta) & MASK
                if VGA_BASE <= at < VGA_END:
                    self.device.planes[0][at - VGA_BASE] = byte

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for segment, offset, value, tag in pending:
            self.modify_word(segment, offset, value)
            self.used.add(tag)

    def queue(self, segment, offset, value, tag):
        self.pending.append((segment, offset & 0xFFFF, value & 0xFFFF, tag))
        if self.native:
            self.instruction_complete()

    def _provider(self, kind, address, value):
        provider = self.case.get('provider')
        tags = set(self.case.get('providers', ()))
        if provider:
            tags.add(provider)
        if not tags or kind != 'write':
            return
        ss, sp = self.case['stack_segment'], self.case['stack_offset']
        if 'saved-ds' in tags and 'saved-ds' not in self.used:
            slot = physical(ss, sp - 2)
            if address == slot:
                self.low['saved-ds'] = value
            elif address == ((slot + 1) & MASK) and 'saved-ds' in self.low:
                old = self.low.pop('saved-ds')
                if (old | (value << 8)) == self.regs['ds']:
                    self.queue(ss, (sp - 2) & 0xFFFF, 0x2500, 'saved-ds')
        if 'saved-bx' in tags and 'saved-bx' not in self.used and self.call_return_seen:
            self.queue(ss, (sp - 2) & 0xFFFF, 0xABCD, 'saved-bx')
        if provider == 'graphics-return' and 'graphics-return' not in self.used and self.call_return_seen:
            self.queue(ss, (sp - 4) & 0xFFFF, 0x1234, provider)
        if provider == 'nested-sprite-return' and provider not in self.used:
            if value == 0xD2:
                self.stack_return_lows.add(address)
            if value == 0x59 and ((address - 1) & MASK) in self.stack_return_lows:
                slot = (address - 1) & MASK
                self.queue(ss, (slot - physical(ss, 0)) & 0xFFFF,
                           0x1234, provider)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        if len(self.events) >= self.event_limit:
            raise OracleFailure('main resource raster callback budget exhausted')
        if kind == 'read':
            if self.device is not None and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
                value = self.memory[address]
            else:
                value = self.memory[address]
            self._write(address, self.memory[address] if self.device is not None and
                        VGA_BASE <= address < VGA_END else value)
        else:
            value &= 0xFF
            if self.device is not None and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
                value = self.memory[address]
            self._write(address, value)
        self.events.append((kind, address, value, flags, mask))
        self._provider(kind, address, value)
        if kind == 'write':
            # Detect the 58FE CALL push. The nested graphics-return fixture
            # mutates that live slot only after the native push completes.
            slot = physical(self.case['stack_segment'], self.case['stack_offset'] - 4)
            if address == slot:
                self.call_return_low = value
            elif address == ((slot + 1) & MASK) and self.call_return_low is not None:
                word = self.call_return_low | (value << 8)
                if word == 0x5901:
                    self.call_return_seen = True
                    if self.case.get('provider') == 'graphics-return':
                        self.queue(self.case['stack_segment'],
                                   self.case['stack_offset'] - 4, 0x1234,
                                   'graphics-return')
                self.call_return_low = None
        return value & 0xFF

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('main resource OUT callback budget exhausted')
        if self.device is None:
            raise OracleFailure('main resource VGA OUT requires a seeded device')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


class DosProvider:
    """One pinned MAIN.DAT stream and explicit DOS/retry seams."""
    def __init__(self, case, memory, regs):
        self.case, self.memory, self.regs = case, memory, regs
        self.position = 0
        self.attributes = 0
        self.reads = 0
        self.opens = 0
        self.retries = 0
        self.events = []
        self.used = set()
        self.calls = 0
        self.data_segment = (case['load_segment'] + 0x09A9) & 0xFFFF
        self.mirror = None

    def callback_entry(self):
        self.calls += 1
        if self.calls > MAX_DOS_EVENTS:
            raise OracleFailure('main resource DOS callback budget exhausted')

    def _live_provider(self, tag):
        if tag in self.used:
            return
        case = self.case
        if tag == 'changed-loader-return':
            offset = (case['stack_offset'] - 4) & 0xFFFF
            put16(self.memory, case['stack_segment'], offset, 0x1234)
            if self.mirror:
                p = physical(case['stack_segment'], offset)
                self.mirror(p, 0x34); self.mirror(p + 1, 0x12)
            self.used.add(tag)
        elif tag == 'outer-return':
            put16(self.memory, case['stack_segment'], case['stack_offset'], 0x1234)
            if self.mirror:
                p = physical(case['stack_segment'], case['stack_offset'])
                self.mirror(p, 0x34); self.mirror(p + 1, 0x12)
            self.used.add(tag)
        elif tag == 'sound-segment':
            put16(self.memory, case['load_segment'], 0x5968,
                  case['sound_segment'])
            if self.mirror:
                p = physical(case['load_segment'], 0x5968)
                self.mirror(p, case['sound_segment'] & 0xFF)
                self.mirror(p + 1, case['sound_segment'] >> 8)
            self.used.add(tag)

    def file_service(self, function, segment, offset, flags, *, count=0,
                     handle=None):
        self.callback_entry()
        case = self.case
        failed = False
        if function == 0x43:
            failed = self.attributes < case.get('attribute_errors', 0)
            self.attributes += 1
            value, returned_count = (5 if failed else 0), 0x1234
            if case.get('provider') in ('changed-loader-return', 'outer-return',
                                        'sound-segment'):
                self._live_provider(case['provider'])
        elif function == 0x3D:
            failed = self.opens < case.get('open_errors', 0)
            self.opens += 1
            value, returned_count = (5 if failed else 7), 0
            if not failed:
                self.position = 0
        elif function == 0x3F:
            failed = self.reads == case.get('read_error_index', -1)
            self.reads += 1
            amount = min(count, max(0, len(MAIN_DATA) - self.position))
            value, returned_count = ((5, 0) if failed else (amount, amount))
        else:
            raise OracleFailure(f'unsupported DOS AH={function:02X}')
        event = dict(function=function, segment=segment, offset=offset,
            count=count, input_flags=flags & (0x0FD7 if function != 0x43 else 0x0FC7),
            failed=failed, cursor=self.position, value=value,
            returned_count=returned_count)
        if function == 0x3F:
            event['handle'] = handle
        self.events.append(event)
        out_flags = (flags & ~0x08D5) | 0x0894 | int(failed)
        if function == 0x3F and not failed:
            self.position += returned_count
        return value, returned_count, out_flags, failed

    def retry(self, view):
        self.callback_entry()
        self.retries += 1
        self.events.append(dict(function='retry', view={k: view[k] for k in
            ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'ds', 'es', 'ss', 'sp', 'flags')}))
        self.memory[physical(self.data_segment,
            loader.field('DatCriticalErrorFlag'))] = 0
        if self.mirror:
            self.mirror(physical(self.data_segment,
                loader.field('DatCriticalErrorFlag')), 0)
        return 0x1111, 0x4567, 0x6789, (view['flags'] & ~0x08D5) | 0x0891


def _copy_stream_read(provider, segment, offset, count):
    start = provider.position
    value, returned, flags, failed = provider.file_service(
        0x3F, segment, offset, 0x0AD7, count=count)
    if not failed:
        data = MAIN_DATA[start:start + returned]
        for index, byte in enumerate(data):
            provider.memory[physical(segment, offset + index)] = byte
    return value, returned, flags, failed


def original(case, initial, entry_regs, initial_device):
    """Delegate the pinned Unicorn composition oracle to the root-owned helper."""
    import main_resources_oracle
    return main_resources_oracle.original(
        sys.modules[__name__], case, initial, entry_regs, initial_device)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'main-resources-m{mutation}.dll',
                     mutation, 'main_resources')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_load_main_resource_sections_core
        self.core.argtypes = [MEM, ct.POINTER(MainCall),
            ct.POINTER(files.Services), ct.POINTER(io_c.Io),
            ct.POINTER(plane_copy.Bus)]
        self.core.restype = MainResult
        self.adapter = self.lib.lmn_load_main_resource_sections_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(io_c.Regs),
            ct.POINTER(files.Services), ct.POINTER(io_c.Io),
            ct.POINTER(plane_copy.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, entry_regs, initial_device, *, core):
        memory = bytearray(initial)
        regs = dict(entry_regs)
        device = copy.deepcopy(initial_device)
        access = Access(case, memory, regs, device, native=True)
        dos = DosProvider(case, memory, regs)
        errors = []

        def die(error):
            code = GUARD_EXIT if 'budget' in str(error).lower() else CALLBACK_EXIT
            try:
                os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
            finally:
                os._exit(code)

        def raster_read(_context, _ram, address, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    raise OracleFailure('native main resource callback budget exhausted')
                return access.access('read', address, flags)
            except BaseException as error:
                die(error)

        def raster_write(_context, _ram, address, value, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    raise OracleFailure('native main resource callback budget exhausted')
                access.access('write', address, flags, value=value)
            except BaseException as error:
                die(error)

        def raster_out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags)
            except BaseException as error:
                die(error)

        def file_result(function, segment, filename, flags):
            try:
                value, count, out_flags, _failed = dos.file_service(
                    function, segment, filename, flags)
                return value, count, out_flags
            except BaseException as error:
                die(error)

        @files.FILE
        def open_readonly(_context, _ram, segment, filename, flags, out):
            try:
                out.contents.value, out.contents.count, out.contents.flags = \
                    file_result(0x3D, segment, filename, flags)
            except BaseException as error:
                die(error)

        @files.FILE
        def attributes(_context, _ram, segment, filename, flags, out):
            try:
                out.contents.value, out.contents.count, out.contents.flags = \
                    file_result(0x43, segment, filename, flags)
            except BaseException as error:
                die(error)

        @files.RETRY_FN
        def retry_ui(_context, _ram, call, out):
            try:
                view = {register: getattr(call.contents, field)
                        for field, register in files.MAPPING.items()}
                value, handle, base, flags = dos.retry(view)
                out.contents.value, out.contents.handle = value, handle
                out.contents.base_cursor, out.contents.flags = base, flags
            except BaseException as error:
                die(error)

        @io_c.QUERY
        def query_size(_context, _ram, segment, offset, flags, out):
            try:
                dos.callback_entry()
                # DatCacheEnabled is zero in the fixtures, so this is a fatal
                # contract guard rather than a second resource source.
                raise OracleFailure('unexpected cached DAT size query')
            except BaseException as error:
                die(error)

        @io_c.READ
        def read_file(_context, _ram, handle, segment, offset, count, flags, out):
            try:
                value, returned, out_flags, failed = dos.file_service(
                    0x3F, segment, offset, flags, count=count, handle=handle)
                if not failed:
                    start = dos.position - returned
                    payload = MAIN_DATA[start:start + returned]
                    base = physical(segment, offset)
                    for index, byte in enumerate(payload):
                        memory[(base + index) & MASK] = byte
                out.contents.value, out.contents.flags = value, out_flags
            except BaseException as error:
                die(error)

        services = files.Services(None, open_readonly, attributes, retry_ui)
        io = io_c.Io(None, query_size, read_file)
        bus_callbacks = (plane_copy.READ(raster_read),
                         plane_copy.WRITE(raster_write),
                         plane_copy.OUT(raster_out))
        bus = plane_copy.Bus(None, *bus_callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = io_c.Regs(**regs)
        if core:
            call = MainCall(*(regs[name] for name in CALL_REGS))
            result = self.core(ram, ct.byref(call), ct.byref(services),
                               ct.byref(io), ct.byref(bus))
            for role, name in zip(ROLE_NAMES, CALL_REGS):
                target = {'code_segment': 'cs', 'data_segment': 'ds',
                          'extra_segment': 'es', 'stack_segment': 'ss',
                          'stack_offset': 'sp'}.get(role, role)
                setattr(state, target, getattr(result, role))
            state.ip = result.continuation
            status = result.status
            meta = dict(continuation=result.continuation,
                        child_entry=result.child_entry,
                        child_status=result.child_status)
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(services),
                                  ct.byref(io), ct.byref(bus))
            meta = {}
        return dict(memory=bytes(memory),
            regs={name: getattr(state, name) for name in oracle.REG_NAMES},
            status=status, **meta, events=access.events,
            dos_events=dos.events, dos_used=set(dos.used),
            providers=set(access.used), device=device)


def compare_state(actual, expected, label):
    require(actual['status'] == expected['status'], label + ': status differs')
    for name in oracle.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f"{label}: {name} {actual['regs'][name]:04X}/"
                f"{expected['regs'][name]:04X} mask={mask:04X}")
    if 'continuation' in actual:
        require(actual['continuation'] == expected['continuation'],
                label + ': continuation differs')
        require(actual['child_entry'] == expected['child_entry'],
                label + ': child entry differs')
        require(actual['child_status'] == expected['child_status'],
                label + ': child status differs')
    require(actual['memory'] == expected['memory'], label + ': full RAM differs')
    require(actual['dos_events'] == expected['dos_events'], label + ': DOS events differ')
    require(actual['dos_used'] == expected['dos_used'], label + ': DOS provider effects differ')
    require(actual['providers'] == expected['providers'], label + ': bus provider effects differ')
    got, want = actual['events'], expected['events']
    count = expected['events_count']
    require(len(got) == count, label + ': raster event count differs')
    for index in range(count):
        # Packed storage avoids allocating millions of Python tuples for the
        # two full pinned paths.
        base = index * 5
        left = tuple(got.data[base:base + 5])
        right = tuple(want.data[base:base + 5])
        left = (('read', 'write', 'out')[left[0]], *left[1:])
        right = (('read', 'write', 'out')[right[0]], *right[1:])
        require(left[:3] == right[:3],
                f'{label}: raster event {index} differs: {left!r}/{right!r}')
        require(((left[3] ^ right[3]) & right[4]) == 0,
                f'{label}: raster FLAGS differ at event {index}: '
                f'{left[3]:04X}/{right[3]:04X} mask={right[4]:04X} '
                f'event={left[:3]!r}/{right[:3]!r}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA state differs')
    require([row[:3] for row in actual['device'].trace] ==
            [row[:3] for row in expected['device'].trace],
            label + ': VGA event trace differs')


def branch_edges(ins):
    result = set()
    for address, insn in ins.items():
        if insn.group(capstone.CS_GRP_JUMP) or insn.mnemonic.lower().startswith(('loop', 'jcxz')):
            target = insn.operands[0].imm & 0xFFFF
            result.add((address, target))
            if insn.mnemonic.lower() != 'jmp':
                result.add((address, (address + insn.size) & 0xFFFF))
    return result


def hashes():
    """Causal source closure for this parent, its original children and inputs."""
    paths = {
        'tests/main_resources.py',
        'tests/main_resources_oracle.py',
        'tests/dat_load.py', 'tests/dat_section.py', 'tests/dat_files.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tests/entity_interactions.py',
        'tests/entity_sprite_banks.py', 'tests/entity_sprite_bank_layout.py',
        'tests/sprite_shift_banks.py', 'tests/sprite_bank.py',
        'tests/sprite_wide_banks.py', 'tests/fixed_word_banks.py',
        'tests/generated_graphics.py', 'tests/vga_plane_copy.py',
        'tests/minimap_vga.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py',
        'tools/resources.py', 'tools/unpack.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py',
        'metadata/oracle.json', 'metadata/inputs.json',
        'metadata/toolchain-lock.json', 'assets/vgalemmi.exe',
        'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'src/game_code_late_after_palette.asm', 'src/resources.asm',
        'src/sprite_banks.asm', 'src/game_code_after_sprite_banks.asm',
        'src/entity_graphics.asm',
        'c/main_resources.c', 'c/main_resources.h', 'c/lemmings_sym.h',
        'c/regs.h', 'c/special_blit.h',
    }
    for name in ('dat_load', 'dat_files', 'dat_cache', 'dat_section', 'dat_io',
                 'dat', 'entity_sprite_banks', 'sprite_shift_banks', 'sprite_bank',
                 'sprite_wide_banks', 'fixed_word_banks', 'generated_graphics',
                 'mask_generators', 'vga_plane_copy'):
        paths.add(f'c/{name}.c')
        paths.add(f'c/{name}.h')
    # The immutable ledger and prose are validated by the static gate; reports
    # use the generated symbol header and exact executable/asset hashes.
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def _case_reference(case):
    memory, regs, device, _selectors, _sound_segment = setup(case)
    expected = original(case, memory, regs, device)
    if case.get('full'):
        layout = tuple(sprite_layout.GROUPS) + (sprite_layout.FINAL_CHILD,)
        expected_sprite_calls = [
            (row['call_site'], row['child_entry'])
            for row in sprite_layout.GROUPS for _ in range(row['count'])]
        expected_sprite_calls.append((sprite_layout.FINAL_CHILD['call_site'],
                                      sprite_layout.FINAL_CHILD['child_entry']))
        sprite_sites = {row['call_site'] for row in layout}
        actual_sprite_calls = [tuple(call) for call in
            expected['adapter']['calls'] if call[0] in sprite_sites]
        check(actual_sprite_calls == expected_sprite_calls and
              len(actual_sprite_calls) == 337,
              f"{case['name']}: expected all 337 ordered section-zero sprite calls")
        events = expected['adapter']['dos_events']
        consumed = sum(event['returned_count'] for event in events
                       if event['function'] == 0x3F and not event['failed'])
        required = len(MAIN_DATA) if case['gate'] == 0xFF else SPANS[6][0]
        check(consumed == required,
              f"{case['name']}: expected complete pinned DAT stream {required:#x}, got {consumed:#x}")
    return memory, regs, device, expected


def _boundary_row(case, boundary, expected):
    state = expected[boundary]
    sites = set(state.get('sites', expected.get('sites', ())))
    edges = set(state.get('edges', expected.get('edges', ())))
    integrated_sites = set(state.get('integrated_sites',
                                     expected.get('integrated_sites', ())))
    integrated_edges = set(state.get('integrated_edges',
                                     expected.get('integrated_edges', ())))
    calls = state.get('calls', expected.get('calls', ()))
    top_calls = sum(call_site in CALL_TARGETS for call_site, _entry in calls)
    events = state['events_count']
    return dict(case=case['name'], boundary=boundary,
        status=state['status'], child_entry=state.get('child_entry', 0),
        child_status=state.get('child_status', 0),
        sites=sorted(sites), edges=sorted([a, b] for a, b in edges),
        integrated_sites=sorted(integrated_sites),
        integrated_edges=sorted([a, b] for a, b in integrated_edges),
        calls=[list(call) for call in calls], top_call_count=top_calls,
        nested_call_count=len(calls) - top_calls,
        events=events, steps=state.get('steps', expected.get('steps', 0)),
        dos_events=len(state['dos_events']))


def _compare_native(native, case, memory, regs, device, expected, boundary):
    core = boundary == 'core'
    actual = native.run(case, memory, regs, device, core=core)
    compare_state(actual, expected[boundary],
                  case['name'] + (' core' if core else ' adapter'))
    return actual


def _coverage(rows):
    sites = {address for row in rows for address in row['sites']
             if address in OWN_INS}
    edges = {(source, target) for row in rows for source, target in row['edges']
             if source in PARENT_BRANCHES}
    expected = branch_edges(OWN_INS)
    check(sites == set(OWN_INS),
          f'missing parent sites {set(OWN_INS) - sites}')
    check(edges == expected,
          f'missing parent branch outcomes {expected - edges}')
    return sites, edges


def _publish(path, before, rows, mutants=None):
    sites, edges = _coverage(rows)
    event_count = sum(row['events'] for row in rows)
    steps = sum(row['steps'] for row in rows)
    dos_events = sum(row['dos_events'] for row in rows)
    report = dict(image='main', image_sha256=sha(IMAGE),
        routine='LoadMainResourceSections', entry=ENTRY, end=RET,
        translated_code_bytes=RET + 1 - ENTRY,
        core_code_bytes=RET - ENTRY, adapter_ret_bytes=1,
        instruction_sites=len(OWN_INS),
        executed_instruction_addresses=sorted(sites),
        executed_instruction_bytes=sum(OWN_INS[site].size for site in sites),
        branch_edges=sorted([source, target] for source, target in edges),
        branch_edge_count=len(edges), case_count=len(cases()),
        comparison_count=len(rows), full_pinned_cases=sum(bool(c.get('full')) for c in cases()),
        ordered_raster_events=event_count,
        unique_execution_raster_events=sum(row['events'] for row in rows
                                            if row['boundary'] == 'adapter'),
        dos_service_events=dos_events,
        unique_execution_dos_events=sum(row['dos_events'] for row in rows
                                        if row['boundary'] == 'adapter'),
        boundary_step_sum=steps,
        original_instruction_steps=sum(row['steps'] for row in rows
                                       if row['boundary'] == 'adapter'),
        original_only=mutants is None,
        mutation_count=len(mutants or []), mutations=mutants or [], rows=rows,
        input_hashes=before,
        sections=[dict(index=index, decoded_bytes=len(section),
                       sha256=sha(section)) for index, section in enumerate(SECTIONS)],
        limits=dict(timeout_seconds=WORKER_SECONDS,
                    process_commit_mib=MEMORY_MIB,
                    original_instruction_limit=MAX_STEPS,
                    raster_callback_limit=MAX_EVENTS,
                    dos_callback_limit=MAX_DOS_EVENTS))
    write_json(path, report)
    print(f'PASS main resources: {len(cases())} cases/{len(rows)} boundaries, '
          f'{len(sites)} sites/{len(edges)} edges, {event_count} raster events, '
          f'{dos_events} DOS events, {len(mutants or [])} mutants', flush=True)


def original_worker():
    before = hashes()
    rows = []
    for case in cases():
        print(f"CHECKED original {case['name']}", flush=True)
        _memory, _regs, _device, expected = _case_reference(case)
        rows.extend(_boundary_row(case, boundary, expected)
                    for boundary in ('core', 'adapter'))
        gc.collect()
    check(before == hashes(), 'inputs changed during original campaign')
    _publish(ORIGINAL_REPORT, before, rows)


def preflight_worker(directory):
    native = Native(directory)
    selected = {'attribute-error-fatal', 'first-header-read-fatal',
                'payload-read-fatal', 'provider-nested-sprite-return'}
    for case in cases():
        if case['name'] not in selected:
            continue
        print(f"CHECKED bounded native preflight {case['name']}", flush=True)
        memory, regs, device, expected = _case_reference(case)
        if case['name'] == 'provider-nested-sprite-return':
            core_state = expected['core']
            check(core_state['status'] == 2 and
                  core_state['child_entry'] == 0x59BB and
                  core_state['child_status'] == 2,
                  'nested sprite-return fixture did not stop at the 59BB child frame')
        for boundary in ('core', 'adapter'):
            _compare_native(native, case, memory, regs, device,
                            expected, boundary)
        gc.collect()


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == hashes(), 'input hash snapshot differs')
    native = Native(directory)
    rows, references = [], {}
    for case in cases():
        print(f"CHECKED native baseline {case['name']}", flush=True)
        memory, regs, device, expected = _case_reference(case)
        references[case['name']] = (case, memory, regs, device, expected)
        for boundary in ('core', 'adapter'):
            _compare_native(native, case, memory, regs, device, expected, boundary)
            rows.append(_boundary_row(case, boundary, expected))
        gc.collect()
        print(f"PASS native baseline {case['name']}", flush=True)

    witness_cases = {
        1: ('provider-live-saved-ds-and-bx', 'core'),
        2: ('provider-live-saved-ds-and-bx', 'core'),
        3: ('pinned-main-gate-ff', 'core'),
        4: ('pinned-main-gate-ff', 'core'),
        5: ('pinned-main-gate-clear', 'core'),
        6: ('pinned-main-gate-clear', 'core'),
        7: ('pinned-main-gate-one', 'core'),
        8: ('provider-changed-top-graphics-return', 'core'),
        9: ('provider-outer-ret', 'adapter'),
        10: ('pinned-main-gate-clear', 'adapter'),
    }
    mutants = []
    for mutation, (name, boundary) in witness_cases.items():
        case, memory, regs, device, expected = references[name]
        print(f'CHECKED completed mutation {mutation} on {name}', flush=True)
        mutant = Native(directory, mutation)
        try:
            _compare_native(mutant, case, memory, regs, device, expected, boundary)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name,
                                boundary=boundary, completed=True,
                                mismatch=str(error)))
        else:
            raise OracleFailure(f'main resource mutation {mutation} survived')
        print(f'PASS completed mutation {mutation}', flush=True)
        gc.collect()
    check(before == hashes(), 'inputs changed during native campaign')
    _publish(ORIGINAL_REPORT, before, rows)
    _publish(REPORT, before, rows, mutants)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    validate_static()
    if args == ['--static-only']:
        print(f'PASS MAIN resource static inputs: {len(SECTIONS)} sections, '
              f'{len(OWN_INS)} parent sites, {len(CALL_TARGETS)} calls, '
              f'{sum(row["count"] for row in sprite_layout.GROUPS)+1} sprite calls')
        return 0
    BUILD.mkdir(exist_ok=True)
    if args == ['--original-worker']:
        original_worker()
        return 0
    if len(args) == 3 and args[0] == '--worker':
        worker(args[1], args[2])
        return 0
    if args == ['--original-only']:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return 0
    if args == ['--preflight']:
        with temporary_build_directory(prefix='main-resources-preflight-',
                                       parent=BUILD) as directory:
            run_bounded([sys.executable, __file__, '--preflight-worker',
                         str(directory)], cwd=ROOT, timeout=180,
                        memory_mib=MEMORY_MIB, check=True)
        return 0
    if len(args) == 2 and args[0] == '--preflight-worker':
        preflight_worker(args[1])
        return 0
    if args:
        raise SystemExit('usage: main_resources.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='main-resources-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(hashes(), sort_keys=True))
        run_bounded([sys.executable, __file__, '--worker', str(directory),
                     str(snapshot)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=MEMORY_MIB, check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
