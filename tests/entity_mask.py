"""Bounded original-vs-C checks for the 5DF8 clipped entity-mask leaf."""
import copy
import ctypes
import gc
import os
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io import REG_NAMES
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN)
from unicorn import x86_const as x


IMAGE, ORACLE = unpack(ASSET.read_bytes())
LOAD = 0x1010
MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
RESOURCE_SEGMENT = 0x6200
BUFFER_SEGMENT = 0x7000
ALTERNATE_BUFFER_SEGMENT = 0x7100
ENTRY, RET, END = 0x5DF8, 0x5EB9, 0x5EBA
CODE = IMAGE[ENTRY:END]
MAX_EVENTS = 2048
MAX_INSTRUCTIONS = 1400
GUARD_EXIT, CALLBACK_EXIT = 86, 87
INITIAL_DEFINED_FLAGS = 0x0FD7
CF, PF, AF, ZF, SF, IF, DF, OF = 0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0200, 0x0400, 0x0800
ARITH_FLAGS = CF | PF | AF | ZF | SF | OF
LOGIC_DEFINED_FLAGS = 0x0FC7
MUL_DEFINED_FLAGS = 0x0F01
REPORT = BUILD / 'entity-mask-differential.json'

REGS = REG_NAMES
REG_ID = {name: getattr(x, 'UC_X86_REG_' + name.upper()) for name in REGS}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(CODE, ENTRY)}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EXPECTED_EDGES = {
    (0x5E22, 0x5E24), (0x5E22, 0x5E34),
    (0x5E2B, 0x5E2D), (0x5E2B, 0x5E30),
    (0x5E2D, 0x5EB9),
    (0x5EB4, 0x5EB6), (0x5EB4, 0x5E7F),
}

READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset',
                 'record_cursor', 'flags')]


class CoreResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'mask_word', 'row_count', 'port', 'source_cursor',
                 'destination_offset', 'data_segment', 'output_segment',
                 'stack_offset', 'flags')]


class ProducerCall(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset',
                 'column_repetitions', 'shift_state', 'flags')]


class ProducerResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'column_repetitions', 'row_count', 'shift_state',
                 'source_cursor', 'output_cursor', 'source_segment',
                 'output_segment', 'stack_offset', 'flags', 'continuation',
                 'ready_to_return')]


class VerificationFailure(RuntimeError):
    """The original fixture or a finite execution/callback budget failed."""


class NativeMismatch(AssertionError):
    """A completed native comparison differs from completed original execution."""


def worker_exit(code, message):
    os.write(2, (message + '\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise VerificationFailure(message)


def flags_defined_after(instruction, prior_mask):
    mnemonic = instruction.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return LOGIC_DEFINED_FLAGS
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return INITIAL_DEFINED_FLAGS
    if mnemonic in ('dec', 'inc'):
        return (INITIAL_DEFINED_FLAGS & ~CF) | (prior_mask & CF)
    if mnemonic == 'mul':
        return MUL_DEFINED_FLAGS
    if mnemonic.startswith(('shl', 'shr')):
        return LOGIC_DEFINED_FLAGS
    return prior_mask


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MEMORY_MASK


def put_word(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MEMORY_MASK] = (value >> 8) & 0xFF


def get_word(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MEMORY_MASK] << 8)


def set_plane_word(device, offset, value, plane=3):
    device.planes[plane][offset & 0xFFFF] = value & 0xFF
    device.planes[plane][(offset + 1) & 0xFFFF] = (value >> 8) & 0xFF


def source_word(seed, row):
    return (0xA5C3 + seed * 0x1F3D + row * 0x9217 + row * row * 17) & 0xFFFF


def shifted_word_mask(value, shift):
    """5CDD's AL/AH/DL right-shift chain, represented as a 24-bit word."""
    chain = (((value & 0xFF) << 16) | (((value >> 8) & 0xFF) << 8))
    shifted = chain >> shift
    return bytes(((shifted >> 16) & 0xFF, (shifted >> 8) & 0xFF,
                  shifted & 0xFF))


def prepare_raw_source(memory, source_segment, seed):
    words = [source_word(seed, row) for row in range(22)]
    for row, word in enumerate(words):
        put_word(memory, source_segment, 0x0108 + row * 2, word)
    return words


def expected_generated_group(words):
    return bytes(byte for shift in range(8) for word in words
                 for byte in shifted_word_mask(word, shift))


def fill_generated_banks(memory, output_segments, seed):
    words = [source_word(seed, row) for row in range(22)]
    payload = expected_generated_group(words)
    for segment in output_segments:
        address = physical(segment, 0x0C60)
        first = min(len(payload), MEMORY_SIZE - address)
        memory[address:address + first] = payload[:first]
        if first < len(payload):
            memory[:len(payload) - first] = payload[first:]
    return payload


def make_cases():
    specs = []
    for index in range(8):
        specs.append((f'generated-shift-{index}', dict(
            x=0x0120 + index, y=30, seed=0x110 + index,
            independent=True)))
    specs.extend((
        ('clip-negative-wrap-y00', dict(x=0x0125, y=0, seed=20)),
        ('clip-exact-zero-count-y08', dict(x=0x0125, y=8, seed=21)),
        ('clip-mutant-boundary-y09', dict(x=0x0125, y=9, seed=22,
                                          independent=True)),
        ('clip-two-rows-y10', dict(x=0x0125, y=10, seed=23,
                                   independent=True)),
        ('clip-last-top-row-y29', dict(x=0x0125, y=29, seed=24,
                                       independent=True)),
        ('clip-zero-top-y30', dict(x=0x0125, y=30, seed=25,
                                   independent=True)),
        ('clip-below-top-y31', dict(x=0x0125, y=31, seed=26,
                                    independent=True)),
        ('signed-wrap-positive-y8000', dict(x=0x0125, y=0x8000, seed=27)),
        ('signed-wrap-negative-y801e', dict(x=0x0125, y=0x801E, seed=28)),
        ('df-set-source-and-destination', dict(x=0x0125, y=30, seed=29,
                                                df=True)),
        ('if-clear-sti-draw', dict(x=0x0125, y=30, seed=30, iflag=False)),
        ('if-clear-preserved-on-early-return', dict(x=0x0125, y=8,
                                                     seed=31, iflag=False)),
        ('readmode-write-mode-one-latch-dependent', dict(
            x=0x0125, y=30, seed=32, gc5=0x01, seq_mask=0x0F,
            gc8=0xFF, read_map=2, independent=True)),
        ('readmode-one-care-and-map-preserved', dict(
            x=0x0125, y=30, seed=33, gc5=0x09, seq_mask=0x05,
            gc2=0x0A, gc7=0x0D, read_map=3, independent=True)),
        ('partial-map-mask-write-mode-zero', dict(
            x=0x0125, y=30, seed=54, gc5=0, seq_mask=0x05,
            independent=True)),
        ('provider-changes-live-saved-count', dict(
            x=0x0125, y=30, seed=34, provider='saved-count')),
        ('provider-replaces-live-buffer-segment', dict(
            x=0x0125, y=30, seed=35, provider='buffer-segment',
            alternate_segment=ALTERNATE_BUFFER_SEGMENT)),
        ('ss-ds-stack-overwrites-y-and-x', dict(
            x=0x0125, y=30, seed=36, ds=0x3000, ss=0x3000,
            si=0x2000, sp=0x2004)),
        ('ss-ds-stack-overwrites-buffer-selector', dict(
            x=0x0125, y=30, seed=37, ds=0x3000, ss=0x3000,
            si=0x3000, sp=0x1FEC, selector_from_stack=True)),
        ('ss-a000-live-save-words', dict(
            x=0x0125, y=30, seed=38, ss=0xA000, sp=0x8000,
            ss_vga_stack=True)),
        ('ds-a000-live-record-and-selector', dict(
            x=0x0125, y=30, seed=39, ds=0xA000, read_map=3,
            ds_vga_record=True)),
        ('return-word-overwritten-by-live-gc8-mirror', dict(
            x=0x0125, y=30, seed=40, sp=0x000E)),
        ('stack-sp-wrap-zero', dict(x=0x0125, y=30, seed=41, sp=0x0000)),
        ('stack-physical-word-wrap', dict(
            x=0x0125, y=30, seed=42, ss=0xFFFF, sp=0x000F)),
        ('record-word-offset-wrap', dict(
            x=0x0125, y=30, seed=43, si=0xFFFE)),
        ('record-word-physical-wrap', dict(
            x=0x0125, y=30, seed=44, ds=0xFFFF, si=0x000F)),
        ('df-clear-if-set-preserved', dict(
            x=0x0125, y=30, seed=45, df=False, iflag=True)),
        ('incoming-map-mask-zero', dict(
            x=0x0125, y=30, seed=46, seq_mask=0x00)),
        ('incoming-readmode-one-empty-care', dict(
            x=0x0125, y=30, seed=47, gc5=0x08, gc7=0x00,
            gc2=0x0F, read_map=1)),
        ('df-set-last-row-clip', dict(
            x=0x0126, y=29, seed=48, df=True)),
        ('large-positive-y-destination-wrap', dict(
            x=0xFFFE, y=0x8000, seed=49)),
        ('stack-alias-record-cursor-y', dict(
            x=0x0125, y=30, seed=50, ds=0x3100, ss=0x3100,
            si=0x4000, sp=0x4004)),
        ('null-device-unexpected-popped-port', dict(
            x=0x0125, y=30, seed=51, null_device=True,
            provider='dx-zero-on-pop')),
        ('producer-core-to-mask-leaf-handoff', dict(
            x=0x0125, y=30, seed=52, producer_handoff=True,
            independent=True)),
        ('source-word-physical-wrap-generated-bank', dict(
            x=14, y=29, seed=53, buffer_segment=0xFF21)),
    ))
    return [dict(name=name, **spec) for name, spec in specs]


def configure_device(case, seed):
    device = MinimapVga(seed, read_map=case.get('read_map', 3))
    default_seq = 0x0F if case.get('independent') else (seed * 7 + 3) & 0x0F
    default_gc5 = 0 if case.get('independent') else (0, 1, 8, 9)[seed & 3]
    device.seq[2] = case.get('seq_mask', default_seq) & 0x0F
    device.gc[0] = case.get('gc0', (seed * 3 + 1) & 0x0F) & 0x0F
    device.gc[1] = case.get('gc1', (seed * 5 + 1) & 0x0F) & 0x0F
    device.gc[2] = case.get('gc2', (seed * 7 + 3) & 0x0F) & 0x0F
    device.gc[3] = case.get('gc3', (seed * 11 + 1) & 0x1F) & 0x1F
    device.gc[4] = case.get('read_map', 3) & 3
    device.gc[5] = case.get('gc5', default_gc5) & 0x0B
    device.gc[6] = 0x05
    device.gc[7] = case.get('gc7', (seed * 13 + 5) & 0x0F) & 0x0F
    device.gc[8] = case.get('gc8', (seed * 17 + 9) & 0xFF)
    return device


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/generated-graphics.md',
        'docs/entity-vga.md', 'docs/entity-mask.md',
        'src/game_code_late_after_palette.asm', 'assets/vgalemmi.exe',
        'metadata/symbols.json', 'metadata/inputs.json', 'metadata/oracle.json',
        'c/entity_mask.c', 'c/entity_mask.h', 'c/generated_graphics.c',
        'c/generated_graphics.h', 'c/mask_generators.c', 'c/mask_generators.h',
        'c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/entity_mask.py', 'tests/entity_stroke.py', 'tests/entity_vga.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/unpack.py', 'tools/coverage.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def providers(case, regs):
    effects = []
    mode = case.get('provider')
    if mode in ('saved-count', 'buffer-segment'):
        target = (physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
                  if mode == 'saved-count' else
                  physical(regs['ds'], 0x1FE8))
        value = (1 if mode == 'saved-count' else
                 case['alternate_segment'])
        effects.append(dict(trigger=physical(regs['ds'], regs['si']),
                            after=0, writes=[(target, bytes((value & 0xFF,
                                                            value >> 8)))]))
    if mode == 'dx-zero-on-pop':
        target = physical(regs['ss'], (regs['sp'] - 6) & 0xFFFF)
        effects.append(dict(trigger=target, after=0,
                            writes=[(target, b'\x00\x00')],
                            replace_read=True))
    return effects


def prepare(case):
    rng = random.Random(0x5DF8 + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    regs = {name: rng.randrange(65536) for name in REGS}
    regs.update(cs=LOAD, ip=ENTRY,
                ds=case.get('ds', DATA_SEGMENT),
                ss=case.get('ss', 0x5200),
                es=rng.randrange(65536), si=case.get('si', 0x5000),
                sp=case.get('sp', 0x8000))
    flags = 2 | (rng.randrange(65536) & (INITIAL_DEFINED_FLAGS & ~0x0100))
    flags &= ~0x0100  # TF must stay clear for intact code.
    flags = flags | DF if case.get('df', False) else flags & ~DF
    if 'iflag' in case:
        flags = flags | IF if case['iflag'] else flags & ~IF
    regs['flags'] = flags

    device = None if case.get('null_device') else configure_device(
        case, 0x5DF8 + case['seed'])
    if case.get('ds_vga_record'):
        device.gc[4] = 3
        device.gc[5] = case.get('gc5', 0) & 0x0B
        set_plane_word(device, regs['si'], case.get('x', 0x0125))
        set_plane_word(device, (regs['si'] + 2) & 0xFFFF,
                       case.get('y', 30))
        set_plane_word(device, 0x1FE8, case.get('buffer_segment', BUFFER_SEGMENT))
    else:
        put_word(memory, regs['ds'], 0x1FE8,
                 case.get('buffer_segment', BUFFER_SEGMENT))

    if case.get('producer_handoff'):
        words = prepare_raw_source(memory, RESOURCE_SEGMENT, case['seed'])
        put_word(memory, regs['ds'], 0x1FE4, RESOURCE_SEGMENT)
    else:
        words = [source_word(case['seed'], row) for row in range(22)]
        if case.get('provider') == 'buffer-segment':
            fill_generated_banks(memory,
                                 (case.get('buffer_segment', BUFFER_SEGMENT),
                                  ALTERNATE_BUFFER_SEGMENT),
                                 case['seed'])
        else:
            fill_generated_banks(memory,
                                 (case.get('buffer_segment', BUFFER_SEGMENT),),
                                 case['seed'])
    if case.get('selector_from_stack'):
        # PUSH BX first writes zero to DS:1FE8, then PUSH DS writes the live DS
        # value there immediately before MOV DS,[1FE8].
        fill_generated_banks(memory, (regs['ds'],), case['seed'])

    if not case.get('ds_vga_record'):
        put_word(memory, regs['ds'], regs['si'], case.get('x', 0x0125))
        put_word(memory, regs['ds'], (regs['si'] + 2) & 0xFFFF,
                 case.get('y', 30))

    return_word = case.get('return_word', (0xE300 | case['seed']) & 0xFFFF)
    put_word(memory, regs['ss'], regs['sp'], return_word)
    if case.get('ss_vga_stack'):
        device.gc[4] = 3
        device.gc[5] = 0
        device.gc[8] = 0
        set_plane_word(device, regs['sp'], return_word)
        # With GC8 zero the PUSH/POP aliases preserve these plane bytes. Their
        # values model the actual save slots consumed at POP DX/AX/CX/DS/SI.
        set_plane_word(device, (regs['sp'] - 2) & 0xFFFF, 22)
        set_plane_word(device, (regs['sp'] - 4) & 0xFFFF, 0)
        set_plane_word(device, (regs['sp'] - 6) & 0xFFFF, 0x03CE)

    if not case.get('producer_handoff'):
        fill_generated_banks(memory,
                             (regs['ds'] if case.get('selector_from_stack')
                              else case.get('buffer_segment', BUFFER_SEGMENT),),
                             case['seed'])
        if case.get('provider') == 'buffer-segment':
            fill_generated_banks(memory, (ALTERNATE_BUFFER_SEGMENT,), case['seed'])
    effects = providers(case, regs)
    return memory, regs, device, words, effects


def make_raster_bus(memory, device, effects, *, no_op_ports=False):
    events = []
    read_counts = {}
    used_effects = set()

    def reserve():
        if len(events) >= MAX_EVENTS:
            worker_exit(GUARD_EXIT, 'native entity-mask callback event cap exhausted')

    def apply_before_read(address):
        count = read_counts.get(address, 0)
        for index, effect in enumerate(effects):
            if (index not in used_effects and address == effect['trigger'] and
                    count == effect['after']):
                used_effects.add(index)
                for target, data in effect['writes']:
                    for offset, byte in enumerate(data):
                        memory[(target + offset) & MEMORY_MASK] = byte
                if effect.get('replace_read') and address == effect['trigger']:
                    return memory[address]
        return None

    def read(_context, _mem, address, flags):
        try:
            reserve()
            address &= MEMORY_MASK
            forced = apply_before_read(address)
            value = forced if forced is not None else (
                device.read(memory, address, flags)
                if device is not None and VGA_BASE <= address < VGA_END
                else memory[address])
            events.append(('read', address, value & 0xFF, flags & 0xFFFF))
            read_counts[address] = read_counts.get(address, 0) + 1
            if device is not None and len(device.trace) > MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native entity-mask VGA trace cap exhausted')
            return value
        except BaseException as error:
            worker_exit(CALLBACK_EXIT, f'native entity-mask read callback failed: {error}')
            return 0

    def write(_context, _mem, address, value, flags):
        try:
            reserve()
            address &= MEMORY_MASK
            value &= 0xFF
            if device is not None and VGA_BASE <= address < VGA_END:
                device.write(memory, address, value, flags)
            else:
                memory[address] = value
            events.append(('write', address, value, flags & 0xFFFF))
            if device is not None and len(device.trace) > MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native entity-mask VGA trace cap exhausted')
        except BaseException as error:
            worker_exit(CALLBACK_EXIT, f'native entity-mask write callback failed: {error}')

    def out(_context, port, value, flags):
        try:
            reserve()
            if device is not None and not no_op_ports:
                device.out(port, value, flags)
            events.append(('out', port & 0xFFFF, value & 0xFFFF, flags & 0xFFFF))
            if device is not None and len(device.trace) > MAX_EVENTS:
                worker_exit(GUARD_EXIT, 'native entity-mask VGA trace cap exhausted')
        except BaseException as error:
            worker_exit(CALLBACK_EXIT, f'native entity-mask OUT callback failed: {error}')

    callbacks = (READ(read), WRITE(write), OUT(out))
    bus = RasterBus(None, *callbacks)
    return callbacks, bus, events, used_effects


class OriginalRun:
    def __init__(self, case, memory, regs, device, effects, *, core):
        self.case, self.memory, self.regs_in = case, memory, regs
        self.device, self.effects, self.core = device, effects, core
        self.events, self.sites, self.edges = [], set(), set()
        self.instruction_count = 0
        self.read_counts = {}
        self.used_effects = set()
        self.previous = None
        self.current_flags = regs['flags']
        self.flag_mask = INITIAL_DEFINED_FLAGS
        self.failure = None
        self.stopped = False
        self.stop_kind = None
        self.continuation = None
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * MEMORY_SIZE)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(MEMORY_SIZE, initial)
        for name in REGS:
            self.cpu.reg_write(REG_ID[name], regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def mirror(linear, p, value):
            byte = bytes((value & 0xFF,))
            for address in (linear, p, p + MEMORY_SIZE):
                if 0 <= address < 2 * MEMORY_SIZE:
                    self.cpu.mem_write(address, byte)

        def apply_effect(address):
            count = self.read_counts.get(address, 0)
            for index, effect in enumerate(self.effects):
                if (index not in self.used_effects and address == effect['trigger'] and
                        count == effect['after']):
                    self.used_effects.add(index)
                    for target, data in effect['writes']:
                        for offset, byte in enumerate(data):
                            p = (target + offset) & MEMORY_MASK
                            self.memory[p] = byte
                            mirror(p, p, byte)

        def code(uc, _address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous in BRANCHES:
                self.edges.add((self.previous, off))
            if self.previous == RET:
                self.continuation = off
                self.stop_kind = 'outer-return'
                self.stopped = True
                uc.emu_stop()
                return
            if cs != regs['cs'] or off not in INS:
                fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if self.core and off == RET:
                self.continuation = off
                self.stop_kind = 'core-boundary'
                self.stopped = True
                uc.emu_stop()
                return
            if self.instruction_count >= MAX_INSTRUCTIONS:
                fail(f'{case["name"]}: original instruction budget exhausted')
                return
            self.instruction_count += 1
            self.sites.add(off)
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.flag_mask = flags_defined_after(INS[off], self.flag_mask)
            self.previous = off

        def add_event(kind, address, value):
            if len(self.events) >= MAX_EVENTS:
                fail(f'{case["name"]}: original bus-event budget exhausted')
                return
            self.events.append((kind, address, value & 0xFFFF,
                                self.current_flags & 0xFFFF,
                                self.flag_mask))

        def memory_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * MEMORY_SIZE:
                        fail(f'{case["name"]}: original read escaped mapped memory')
                        return
                    p = linear & MEMORY_MASK
                    apply_effect(p)
                    value = (device.read(self.memory, p, self.current_flags)
                             if device is not None and VGA_BASE <= p < VGA_END
                             else self.memory[p])
                    add_event('read', p, value)
                    if self.failure:
                        return
                    mirror(linear, p, value)
                    self.read_counts[p] = self.read_counts.get(p, 0) + 1
                    if device is not None and len(device.trace) > MAX_EVENTS:
                        fail(f'{case["name"]}: original VGA callback budget exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original read callback failed: {error}')

        def memory_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * MEMORY_SIZE:
                        fail(f'{case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MEMORY_MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if device is not None and VGA_BASE <= p < VGA_END:
                        device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    add_event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
                    if device is not None and len(device.trace) > MAX_EVENTS:
                        fail(f'{case["name"]}: original VGA callback budget exhausted')
                        return
            except BaseException as error:
                fail(f'{case["name"]}: original write callback failed: {error}')

        def output(uc, port, size, value, _user):
            try:
                if size != 2:
                    fail(f'{case["name"]}: unexpected non-word OUT width {size}')
                    return
                if device is not None and not case.get('null_device'):
                    device.out(port, value, self.current_flags)
                add_event('out', port, value)
                if device is not None and len(device.trace) > MAX_EVENTS:
                    fail(f'{case["name"]}: original VGA OUT budget exhausted')
            except BaseException as error:
                fail(f'{case["name"]}: original OUT provider failed: {error}')

        self._callbacks = (code, memory_read, memory_write, output)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
        self.cpu.hook_add(UC_HOOK_INSN, output, None, 1, 0, x.UC_X86_INS_OUT)

    def run(self):
        try:
            self.cpu.emu_start(physical(self.regs_in['cs'], ENTRY), 0,
                               count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise VerificationFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original missed bounded continuation')
        oracle_require(len(self.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original bus-event budget exhausted')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        return dict(memory=bytes(self.cpu.mem_read(0, MEMORY_SIZE)), state=state,
                    events=self.events, sites=self.sites, edges=self.edges,
                    instruction_count=self.instruction_count,
                    used_effects=set(self.used_effects),
                    device=self.device, stop_kind=self.stop_kind,
                    continuation=self.continuation, flag_mask=self.flag_mask)


class Native:
    def __init__(self, directory, mutation=0, *, producer=False):
        cluster = 'generated_graphics' if producer else 'entity_mask'
        path = Path(directory) / f'entity-mask-m{mutation}.dll'
        if producer:
            path = Path(directory) / 'generated-graphics-producer.dll'
        self.library = ctypes.CDLL(str(path))
        if producer:
            self.core = self.library.lmn_generate_graphics_mask_banks_core
            self.core.argtypes = [MEM, ctypes.POINTER(ProducerCall),
                                  ctypes.c_void_p]
            self.core.restype = ProducerResult
        else:
            self.core = self.library.lmn_draw_clipped_entity_mask_core
            self.core.argtypes = [MEM, ctypes.POINTER(Call),
                                  ctypes.POINTER(RasterBus)]
            self.core.restype = CoreResult
            self.adapter = self.library.lmn_draw_clipped_entity_mask_adapter
            self.adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                     ctypes.POINTER(RasterBus)]
            self.adapter.restype = None


def c_buffer(memory):
    return (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)


def state_from_core(result, initial):
    state = dict(initial)
    state.update(ax=result.value, bx=result.mask_word, cx=result.row_count,
                 dx=result.port, si=result.source_cursor,
                 di=result.destination_offset, ds=result.data_segment,
                 es=result.output_segment, sp=result.stack_offset,
                 ip=RET, flags=result.flags)
    return state


def compare_state(case, actual, expected, label, flag_mask):
    for name in REGS:
        if actual[name] != expected[name]:
            raise NativeMismatch(f'{case["name"]} {label} {name} differs: '
                                 f'{actual[name]:04X}/{expected[name]:04X}')
    if ((actual['flags'] ^ expected['flags']) & flag_mask) != 0:
        raise NativeMismatch(f'{case["name"]} {label} defined flags differ: '
                             f'{actual["flags"]:04X}/{expected["flags"]:04X}')


def compare_memory(case, actual, expected, label):
    if actual == expected:
        return
    at = next((i for i, (got, want) in enumerate(zip(actual, expected))
               if got != want), None)
    raise NativeMismatch(f'{case["name"]} {label} RAM differs at {at:05X}: '
                         f'{actual[at]:02X}/{expected[at]:02X}')


def compare_events(case, actual, expected):
    require(len(actual) == len(expected),
            f'{case["name"]}: callback count differs {len(actual)}/{len(expected)}')
    for index, (got, want) in enumerate(zip(actual, expected)):
        if got[:3] != want[:3]:
            raise NativeMismatch(f'{case["name"]}: callback {index} differs: '
                                 f'{got[:3]!r}/{want[:3]!r}')
        if ((got[3] ^ want[3]) & want[4]) != 0:
            raise NativeMismatch(f'{case["name"]}: callback flags differ at {index}: '
                                 f'{got[3]:04X}/{want[3]:04X}')


def expected_visible_rows(y):
    di = (y - 30) & 0xFFFF
    cx = 22
    if di & 0x8000:
        cx = (cx + di) & 0xFFFF
        clip = (-di) & 0xFFFF
        if clip > 21:
            return 0, clip, True
        return cx, clip, False
    return 22, 0, False


def independent_plane_check(case, words, initial_device, actual_device, memory,
                            initial_regs):
    if (not case.get('independent') or initial_device is None or
            case.get('df') or case.get('provider') or case.get('ds_vga_record') or
            case.get('selector_from_stack')):
        return False
    rows, clipped, early = expected_visible_rows(case.get('y', 30))
    if early:
        return False
    xvalue = case.get('x', 0x0125)
    shift = ((xvalue - 8) & 0xFFFF) & 7
    source = (0x0C60 + 66 * shift + 3 * clipped) & 0xFFFF
    yoffset = 0 if clipped else ((case.get('y', 30) - 30) & 0xFFFF)
    start = ((0x00D0 * yoffset) & 0xFFFF)
    start = (start + (((xvalue - 8) & 0xFFFF) >> 3) + 0x4A40) & 0xFFFF
    expected = [bytearray(plane) for plane in initial_device.planes]
    output_segment = case.get('buffer_segment', BUFFER_SEGMENT)
    map_mask = initial_device.seq[2] & 0x0F
    write_mode = initial_device.gc[5] & 3
    oracle_require(write_mode in (0, 1),
                   f'{case["name"]}: independent checker got unsupported write mode')
    for row in range(rows):
        at = (source + row * 3) & 0xFFFF
        masks = [memory[physical(output_segment, (at + n) & 0xFFFF)]
                 for n in range(3)]
        row_start = (start + row * 0xD0) & 0xFFFF
        for col, mask in enumerate(masks):
            offset = (row_start + col) & 0xFFFF
            for plane in range(4):
                if not (map_mask & (1 << plane)) or write_mode == 1:
                    continue
                expected[plane][offset] &= (~mask) & 0xFF
    for plane in range(4):
        oracle_require(bytes(actual_device.planes[plane]) == bytes(expected[plane]),
                       f'{case["name"]}: independent mask/plane check failed '
                       f'on plane {plane}')
    return True


def producer_handoff(producer, memory, case, words):
    call = ProducerCall(DATA_SEGMENT, 0x5300, 0x8000, 0, 0, 0x0002)
    result = producer.core(c_buffer(memory), ctypes.byref(call), None)
    oracle_require(result.ready_to_return == 1 and result.continuation == 0x5B10,
                   f'{case["name"]}: generated-bank producer missed its core boundary')
    expected = expected_generated_group(words)
    start = physical(BUFFER_SEGMENT, 0x0C60)
    actual = bytes(memory[start:start + len(expected)])
    oracle_require(actual == expected,
                   f'{case["name"]}: producer bank differs from independent 5CDD shift chain')


def native_run(native, case, initial, initial_regs, initial_device, effects, *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    no_op_ports = bool(case.get('null_device'))
    callbacks, bus, events, used_effects = make_raster_bus(
        memory, device, effects, no_op_ports=no_op_ports)
    if core:
        call = Call(initial_regs['ds'], initial_regs['ss'], initial_regs['sp'],
                    initial_regs['si'], initial_regs['flags'])
        result = native.core(c_buffer(memory), ctypes.byref(call), ctypes.byref(bus))
        state = state_from_core(result, initial_regs)
    else:
        live = Regs(**{name: initial_regs[name] for name in REGS},
                    flags=initial_regs['flags'])
        native.adapter(c_buffer(memory), ctypes.byref(live), ctypes.byref(bus))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags
    return dict(memory=bytes(memory), state=state, events=events,
                device=device, callbacks=callbacks, used_effects=used_effects)


def compare_case(native, case, producer=None):
    initial, initial_regs, initial_device, words, effects = prepare(case)
    if case.get('producer_handoff'):
        oracle_require(producer is not None, 'producer handoff library is missing')
        producer_handoff(producer, initial, case, words)
    original_device = copy.deepcopy(initial_device)
    observations = {}
    independent_checked = False
    for core in (True, False):
        original_memory = bytearray(initial)
        original = OriginalRun(case, original_memory, dict(initial_regs),
                              copy.deepcopy(original_device), effects,
                              core=core).run()
        native_result = native_run(native, case, initial, initial_regs,
                                   initial_device, effects, core=core)
        label = 'core' if core else 'adapter'
        oracle_require(original['used_effects'] == set(range(len(effects))),
                       f'{case["name"]}: original did not use every provider effect')
        oracle_require(native_result['used_effects'] == set(range(len(effects))),
                       f'{case["name"]}: native did not use every provider effect')
        compare_state(case, native_result['state'], original['state'], label,
                      original['flag_mask'])
        compare_memory(case, native_result['memory'], original['memory'], label)
        compare_events(case, native_result['events'], original['events'])
        if initial_device is not None:
            require(native_result['device'].state() == original['device'].state(),
                    f'{case["name"]}: {label} VGA planes/latches/registers differ')
            if core:
                independent_checked = independent_plane_check(
                    case, words, original_device, original['device'],
                    original['memory'], initial_regs)
        if core:
            oracle_require(original['stop_kind'] == 'core-boundary' and
                           original['continuation'] == RET,
                           f'{case["name"]}: original missed pre-RET core boundary')
            oracle_require(original['state']['sp'] == initial_regs['sp'],
                           f'{case["name"]}: original core left an unbalanced live stack')
            require(native_result['state']['ip'] == RET,
                    f'{case["name"]}: native core boundary differs')
        else:
            oracle_require(original['stop_kind'] == 'outer-return',
                           f'{case["name"]}: original did not execute actual RET')
            oracle_require(original['state']['sp'] ==
                           ((initial_regs['sp'] + 2) & 0xFFFF),
                           f'{case["name"]}: original RET did not consume live return word')
        observations['core' if core else 'adapter'] = dict(
            sites=original['sites'], edges=original['edges'],
            instruction_count=original['instruction_count'],
            event_count=len(original['events']),
            continuation=original['continuation'],
            stop_kind=original['stop_kind'], flag_mask=original['flag_mask'])
        gc.collect()
    return observations, independent_checked


def worker(directory, before_path):
    before = read_json(before_path)
    oracle_require(before == input_hashes(),
                   'entity mask inputs changed between build and bounded worker')
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(CODE) == 194 and len(INS) == 91,
                   '5DF8 byte/site accounting changed')
    oracle_require(IMAGE[0xEF0C:0xEF14] == bytes.fromhex(
        '80 40 20 10 08 04 02 01'), 'Pinned PixelBitMasks identity changed')

    fixtures = make_cases()
    baseline = Native(directory)
    producer = Native(directory, producer=True)
    coverage, edges, total_events = set(), set(), 0
    rows, independent_count = [], 0
    by_name = {case['name']: case for case in fixtures}
    for case in fixtures:
        observation, checked = compare_case(baseline, case, producer)
        sites = set(observation['core']['sites']) | set(observation['adapter']['sites'])
        case_edges = set(observation['core']['edges']) | set(observation['adapter']['edges'])
        coverage.update(sites)
        edges.update(case_edges)
        total_events += (observation['core']['event_count'] +
                         observation['adapter']['event_count'])
        independent_count += bool(checked)
        rows.append(dict(name=case['name'], x=case.get('x', 0x0125),
                         y=case.get('y', 30), shift_index=(
                             ((case.get('x', 0x0125) - 8) & 0xFFFF) & 7),
                         expected_rows=expected_visible_rows(case.get('y', 30))[0],
                         expected_top_clip=expected_visible_rows(case.get('y', 30))[1],
                         provider=case.get('provider'),
                         producer_handoff=bool(case.get('producer_handoff')),
                         independent_mask_plane_check=checked,
                         boundaries={name: dict(event_count=part['event_count'],
                             instruction_count=part['instruction_count'],
                             stop_kind=part['stop_kind'],
                             continuation=part['continuation'])
                             for name, part in observation.items()}))
        gc.collect()

    oracle_require(coverage == set(INS),
                   f'Original executed-site union differs: missing={sorted(set(INS)-coverage)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'Original branch-edge coverage differs: {sorted(edges)}')

    mutation_witnesses = (
        (1, 'clip-mutant-boundary-y09', '21-row clipping threshold'),
        (2, 'provider-changes-live-saved-count', 'live saved row count'),
        (3, 'df-set-source-and-destination', 'DF-sensitive LODS/STOSB steps'),
        (4, 'readmode-write-mode-one-latch-dependent', 'three latch reads per row'),
        (5, 'return-word-overwritten-by-live-gc8-mirror', 'actual near RET word'),
        (6, 'if-clear-sti-draw', 'unconditional STI on the draw path'),
    )
    mutations = []
    for number, case_name, label in mutation_witnesses:
        mutant = Native(directory, number)
        try:
            compare_case(mutant, by_name[case_name], producer)
        except NativeMismatch as error:
            mutations.append(dict(mutation=number, name=label, case=case_name,
                                  mismatch=str(error), completed=True))
        else:
            raise VerificationFailure(f'Entity-mask mutation {number} survived {case_name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after,
                   'entity mask inputs changed during bounded differential campaign')
    oracle_require(len(fixtures) >= 36 and len(fixtures) <= 44 and
                   len(mutations) == 6,
                   'Entity-mask fixture or completed-mutant scope changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        asset_sha256=sha(ASSET.read_bytes()),
        static_image_sha256=sha(IMAGE),
        case_count=len(fixtures), boundary_call_count=2 * len(fixtures),
        mutation_count=len(mutations), mutations=mutations, cases=rows,
        translated_code_bytes=len(CODE), native_code_ranges=[[ENTRY, END]],
        routine_bytes=CODE.hex(), executed_instruction_addresses=sorted(coverage),
        instruction_sites=sorted(coverage), instruction_site_count=len(coverage),
        branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=sorted(edges), total_bus_events=total_events,
        independent_mask_plane_checks=independent_count,
        generated_bank_handoff=dict(case='producer-core-to-mask-leaf-handoff',
            producer_range=[0x5AC1, 0x5B10], consumer_range=[ENTRY, RET],
            independently_checked_bytes=8 * 22 * 3,
            formula='0C60h + 66*shift + 3*top_clip; 24-bit AL/AH/DL right shift'),
        domains=[
        '5DF8..5EB9 194-byte leaf; core stops before common RET and adapter executes actual RET',
            'all eight generated-bank shifts, independent source-word shift chain and selected-bank offsets',
            'negative wrap, y=8/9/10/29/30 boundaries, positive signed wrap and early-return paths',
            'live DS record and 1FE8 selector, SS saved count/clip/DX/SI/DS words and provider mutation',
            'incoming DF for LODSW/LODSB/STOSB, 16-bit cursor and 20-bit physical wrapping',
            'incoming Sequencer map mask and GC read/write/map/compare/care state; only GC0/1/3/8 are written',
            'ordered latch reads, SS VGA aliases, memory-backed no-op unexpected-port fixture, actual return-word aliases',
            'whole 1 MiB RAM, full register adapter state, defined flags and ordered bounded bus events',
        ],
        limits=dict(worker_seconds=180, windows_process_mib=384, windows_tree_mib=640,
                    original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    original_instruction_counts=dict(total=sum(
                        part['instruction_count']
                        for row in rows for part in row['boundaries'].values()),
                        maximum=max(part['instruction_count']
                                    for row in rows
                                    for part in row['boundaries'].values())),
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=after))
    print(f'PASS entity mask C: {len(fixtures)} fixtures, {total_events} bus events, '
          f'{len(coverage)} instruction sites, {len(edges)} branch edges, '
          f'{len(mutations)} completed mutants, {independent_count} independent plane checks',
          flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity mask arguments')
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-mask-', parent=BUILD) as directory:
        before_path = Path(directory) / 'input-hashes.json'
        before = input_hashes()
        write_json(before_path, before)
        for mutation in range(7):
            build(Path(directory) / f'entity-mask-m{mutation}.dll', mutation,
                  'entity_mask')
        build(Path(directory) / 'generated-graphics-producer.dll', 0,
              'generated_graphics')
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory, str(before_path)], cwd=ROOT, timeout=180,
                    memory_mib=384)


if __name__ == '__main__':
    main()
