"""Bounded original-versus-native checks for the 2EC0 entity interaction parent."""
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
from resources import sound_images
import pcspeaker_dispatch as pc_dispatch
import sound_latches as sound
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_INTR, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN
from unicorn.x86_const import UC_X86_INS_OUT

SIZE, MASK, FLAGS = sound.SIZE, sound.MASK, sound.FLAGS
CF, AF, IF = 0x0001, 0x0010, 0x0200
LOGIC = FLAGS & ~AF
ARITH = 0x08D5
ENTRY, END, MAIN_SEG = 0x2EC0, 0x30A6, 0x1010
PC_SEG, PC_ENTRY = 0x0842, 0x0182
SOUND_SEG = 0x7000
OUTER_RETURN = 0x1FEB
MAX_INSTRUCTIONS, MAX_BUS_EVENTS = 512, 1024
CALLBACK_BUDGET_EXIT, CALLBACK_ERROR_EXIT = 86, 87
REPORT = BUILD / 'entity-interactions-differential.json'
IMAGE, ORACLE = unpack(ASSET.read_bytes())
PC_IMAGE, PC_META = sound_images()['pcspeaker']
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
MAIN_INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
PC_INS = pc_dispatch.PARENT_INS | pc_dispatch.CHILD_INS
DRIVER_INS = {
    name: {i.address: i for i in MD.disasm(image[:0x3A], 0)}
    for name, (image, _meta) in sound.IMAGES.items() if name in sound.TAILS
}
MAIN_RETS = {address for address, ins in MAIN_INS.items() if ins.mnemonic == 'ret'}

REG_NAMES = sound.NAMES
REG_IDS = sound.IDS
MEM = ct.POINTER(ct.c_uint8)


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in REG_NAMES]


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('count', 'auxiliary_value', 'record_cursor', 'object_cursor',
                 'data_segment', 'code_segment', 'stack_segment', 'stack_offset',
                 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
                 'object_cursor', 'data_segment', 'code_segment', 'stack_segment',
                 'stack_offset', 'flags', 'continuation', 'status')]


class PcBinding(ct.Structure):
    _fields_ = [('driver_segment', ct.c_uint16)]


class SoundBinding(ct.Structure):
    _fields_ = [('driver_segment', ct.c_uint16), ('driver_kind', ct.c_uint16)]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """Original execution escaped the stated code/provider domain or a bound."""


class Mismatch(AssertionError):
    """Only a completed native comparison may produce mutation evidence."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


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


def signed8(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def map_offsets(x, y, delta):
    x_scaled = (x & 0xFFFF) >> 2
    y_scaled = (((y - 0x10) & 0xFFFF) >> 2)
    first = (x_scaled + y_scaled * 0x1A0 + 0x12) & 0xFFFF
    second = (first - 0x340 + signed8(delta) * 2) & 0xFFFF
    return first, second


def flags_after(ins, previous_mask):
    mnemonic = ins.mnemonic.lower()
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return LOGIC
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return FLAGS
    if mnemonic in ('inc', 'dec'):
        return (FLAGS & ~CF) | (previous_mask & CF)
    if mnemonic in ('shl', 'shr', 'sar', 'rol', 'ror'):
        return LOGIC
    if mnemonic in ('rcl', 'rcr'):
        oracle_require(ins.operands[-1].type == capstone.x86.X86_OP_IMM and
                       ins.operands[-1].imm == 1,
                       'original rotate contract requires a one-bit count')
        # One-bit carry rotates define CF/OF and preserve every other flag.
        return previous_mask | 0x0801
    if mnemonic in ('mul', 'imul'):
        return (previous_mask & ~ARITH) | 0x0801
    if mnemonic in ('sti', 'cli'):
        return previous_mask | IF
    if mnemonic == 'int':
        return previous_mask | 0x0300
    if mnemonic == 'iret':
        return FLAGS
    return previous_mask


def code_for_case(case):
    """The common 2EC0 image plus only the two declared interrupt children."""
    load = case.get('load', MAIN_SEG)
    loaded = relocated(IMAGE, ORACLE['relocations'], load)
    return load, loaded


def setup(case):
    rng = random.Random(case.get('seed', 0x2EC000 + case.get('sample', 0)))
    memory = (bytearray(rng.randbytes(SIZE)) if case.get('poison')
              else bytearray(SIZE))
    load, loaded = code_for_case(case)
    base = (load << 4) & MASK
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    memory[:len(loaded) - first] = loaded[first:]

    pc_base = physical(PC_SEG, 0)
    memory[pc_base:pc_base + len(PC_IMAGE)] = PC_IMAGE
    if 'pc_table_target' in case:
        put16(memory, PC_SEG, 0x0024, case['pc_table_target'])
    driver = case.get('driver', 'adlib')
    driver_image = sound.IMAGES[driver][0]
    driver_base = physical(SOUND_SEG, 0)
    memory[driver_base:driver_base + len(driver_image)] = driver_image

    regs = ({name: rng.randrange(0x10000) for name in REG_NAMES} if case.get('poison')
            else {name: ((0x5217 * (index + 3) + 0x39A1) & 0xFFFF)
                  for index, name in enumerate(REG_NAMES)})
    raw_entry_flags = case.get('flags',
        ((rng.randrange(0x10000) & ~0x0100) | 2) if case.get('poison') else 0x0ED7)
    entry_flags = ((raw_entry_flags & 0x7FD5) | 2) & ~0x0100
    oracle_require(entry_flags == ((entry_flags & 0x7FD5) | 2) and
                   not entry_flags & 0x0100,
                   case['name'] + ': constructed entry FLAGS violate the IRET contract')
    regs.update(ax=case.get('ax', rng.randrange(0x10000) if case.get('poison') else 0xBEEF),
                bx=case.get('bx', rng.randrange(0x10000) if case.get('poison') else 0x7139),
                cx=case.get('cx', rng.randrange(0x10000) if case.get('poison') else 0x6A55),
                dx=case.get('dx', rng.randrange(0x10000) if case.get('poison') else 0x42D3),
                bp=case.get('bp', rng.randrange(0x10000) if case.get('poison') else 0xA641),
                cs=load, ds=case.get('ds', 0x3800),
                es=case.get('es', rng.randrange(0x10000) if case.get('poison') else 0x6C20),
                ss=case.get('ss', 0x5000),
                sp=case.get('sp', 0xD000), si=case.get('si', 0x4000),
                ip=ENTRY, flags=entry_flags)
    ds, si, ss, sp = regs['ds'], regs['si'], regs['ss'], regs['sp']

    x = case.get('x', 4)
    y = case.get('y', 0x20)
    record_delta = case.get('record_delta', 0)
    put16(memory, ds, si, x)
    put16(memory, ds, si + 2, y)
    put16(memory, ds, si + 8, case.get('record_bits', 0xFFFF))
    put8(memory, ds, si + 0x27, record_delta)
    put8(memory, ds, si + 0x24, case.get('entity_flags', 0xA5))
    put16(memory, ds, si + 0x14, 0x7654)
    put16(memory, ds, si + 0x28, 0x5A5A)
    put16(memory, ds, si + 0x2A, 0x6B6B)

    first_offset, second_offset = map_offsets(x, y, record_delta)
    first_sample = case.get('sample', 0)
    second_sample = case.get('second_sample', first_sample)
    device = None
    if case.get('vga'):
        device = MinimapVga(0x2EC0 ^ first_sample, read_map=0)
        device.seq[2] = 0x01
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[8] = 0xFF
        for plane in device.planes:
            plane[:]=bytes(65536)
        first_vga = physical(ss, first_offset) - VGA_BASE
        second_vga = physical(ss, second_offset) - VGA_BASE
        device.planes[0][first_vga] = first_sample
        device.planes[0][second_vga] = second_sample
    else:
        put8(memory, ss, first_offset, first_sample)
        put8(memory, ss, second_offset, second_sample)

    # The local object array is initialized only where this fixture's selector
    # may point. Its first word and +1Bh byte are independently chosen.
    object_index = case.get('object_index', 0)
    object_offset = (0x17CB + object_index * 0x1C) & 0xFFFF
    if case.get('object_word') is not None:
        put16(memory, ds, object_offset, case['object_word'])
    if case.get('object_sound') is not None:
        put8(memory, ds, object_offset + 0x1B, case['object_sound'])

    put8(memory, ds, 0x2010, case.get('enabled', 0))
    put8(memory, ds, 0x25A7, case.get('options', 0))
    if 'provider_ds' in case:
        put8(memory, case['provider_ds'], 0x2010,
             case.get('provider_enabled', 0xFF))
        put8(memory, case['provider_ds'], 0x25A7,
             case.get('provider_options', 3))
    put16(memory, ds, 0x2E, case.get('slot2e', 0x6170))
    put16(memory, ds, 0x32, case.get('slot32', 0x6172))
    put16(memory, ds, 0x3E, case.get('slot3e', 0x6174))

    pc_ip, pc_cs = case.get('pc_vector', (PC_ENTRY, PC_SEG))
    sound_ip, sound_cs = case.get('sound_vector', (0, SOUND_SEG))
    put16(memory, 0, 0x180, pc_ip)
    put16(memory, 0, 0x182, pc_cs)
    put16(memory, 0, 0x184, sound_ip)
    put16(memory, 0, 0x186, sound_cs)
    put16(memory, ss, sp, case.get('outer_return', OUTER_RETURN))
    binding_kind = 1 if driver == 'adlib' else 2
    pc_binding = (None if case.get('pc_binding', True) is False
                  else PcBinding(case.get('pc_binding_segment', PC_SEG)))
    sound_binding = (None if case.get('sound_binding', True) is False else
                     SoundBinding(case.get('sound_binding_segment', SOUND_SEG),
                                  case.get('sound_binding_kind', binding_kind)))
    return memory, regs, device, pc_binding, sound_binding, (first_offset, second_offset)


class Access:
    event_limit = MAX_BUS_EVENTS

    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events = []
        self.used = set()
        self.mirror = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.mirror:
            self.mirror(address, value & 0xFF)

    def modify_word(self, segment, offset, value):
        address = physical(segment, offset)
        self.store(address, value & 0xFF)
        self.store(address + 1, value >> 8)

    def _provider(self, kind, address):
        case = self.case
        effect = case.get('provider')
        if effect in ('pc-registers', 'pc-child-return', 'pc-interrupt-return',
                      'pc-second-gate') and kind == 'write' and 'pc' not in self.used:
            if address == physical(PC_SEG, 1):
                ss, sp = self.regs['ss'], self.regs['sp']
                if effect == 'pc-registers':
                    self.modify_word(ss, sp - 18, case['provider_ds'])
                    self.modify_word(ss, sp - 14, case['provider_si'])
                    self.modify_word(ss, sp - 10, case['provider_cx'])
                elif effect == 'pc-child-return':
                    self.modify_word(ss, sp - 20, case.get('provider_return', 0x3456))
                elif effect == 'pc-interrupt-return':
                    self.modify_word(ss, sp - 6, case.get('provider_return', 0x3456))
                    if 'provider_cs' in case:
                        self.modify_word(ss, sp - 4, case['provider_cs'])
                else:
                    self.modify_word(ss, sp - 18, case['provider_ds'])
                    self.modify_word(ss, sp - 2, case.get('provider_flags', 0x0042))
                self.used.add('pc')
                return
        if effect == 'sound-interrupt-return' and kind == 'write' and 'sound' not in self.used:
            driver = case.get('driver', 'adlib')
            latch = sound.TAILS[driver][4][1]
            if address == physical(SOUND_SEG, latch):
                self.modify_word(self.regs['ss'], self.regs['sp'] - 6,
                                 case.get('provider_return', 0x3456))
                self.used.add('sound')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('entity-interactions bus callback budget exhausted')
        address &= MASK
        self._provider(kind, address)
        if kind == 'read':
            if self.device and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
            else:
                value = self.memory[address]
            self.store(address, value)
        else:
            if self.device and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF, mask))
        return value & 0xFF


def original(case, memory, regs, device, core, *, entry_flag_mask=FLAGS,
             main_instructions=None, main_ret_continuations=None,
             main_call_returns=None,
             stop_offsets=None, access_factory=Access,
             instruction_limit=MAX_INSTRUCTIONS):
    """Execute identified original instructions, including optional parent spans.

    Parent RET entries map address -> (expected IP, changed-return status).
    Matching returns continue; stop_offsets maps main IP -> success/seam status.
    main_call_returns maps CALL sites -> (allowed RET sites, changed status).
    These calls track their own actual expected CS:IP, allowing one helper to
    serve several call sites without accepting another caller's return target.
    Sites/edges retain ('main', ...) tags so callers can filter owned ranges.
    The optional access object may flush deferred provider effects in its
    instruction_complete() method, after the actual CPU instruction finishes.
    A declared word-port domain supplies out_word(port, value, flags, mask);
    otherwise OUT fails. Access subclasses may set their own bounded event_limit.
    Defaults preserve the standalone 2EC0 pre-RET/actual-RET boundaries.
    """
    oracle_require(instruction_limit > 0, 'original instruction limit must be positive')
    main_code = MAIN_INS if main_instructions is None else main_instructions
    main_rets = {address for address, ins in main_code.items() if ins.mnemonic == 'ret'}
    return_contracts = {} if main_ret_continuations is None else main_ret_continuations
    call_contracts = {} if main_call_returns is None else main_call_returns
    stops = {} if stop_offsets is None else stop_offsets
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    cpu.mem_write(0, bytes(memory))
    cpu.mem_write(SIZE, bytes(memory))
    for name, value in regs.items():
        cpu.reg_write(REG_IDS[name], value)
    access = access_factory(case, memory, regs, device)

    def mirror(address, value):
        cpu.mem_write(address, bytes((value,)))
        cpu.mem_write(address + SIZE, bytes((value,)))

    access.mirror = mirror
    # Parent oracles carry defined FLAGS across their real CALL boundary.
    current_flags, current_mask = regs['flags'], entry_flag_mask
    previous = None
    stopped, failure, status = False, None, None
    steps = 0
    sites, edges, call_targets = set(), set(), set()
    interrupt_returns = []
    child_returns = []
    main_returns = []

    def stop(u, value):
        nonlocal stopped, status
        stopped, status = True, value
        u.emu_stop()

    def fail(u, message):
        nonlocal failure
        failure = message
        u.emu_stop()

    def read_word(segment, offset):
        address = physical(segment, offset)
        low = access.access('read', address, current_flags, current_mask)
        high = access.access('read', address + 1, current_flags, current_mask)
        return low | (high << 8)

    def write_word(segment, offset, value):
        address = physical(segment, offset)
        access.access('write', address, current_flags, current_mask, value & 0xFF)
        access.access('write', address + 1, current_flags, current_mask, value >> 8)

    def push_word(u, segment, sp, value, flags):
        sp = (sp - 2) & 0xFFFF
        write_word(segment, sp, value)
        u.reg_write(REG_IDS['sp'], sp)
        return sp

    def interrupt(u, number, _):
        nonlocal current_flags, current_mask
        if number not in (0x60, 0x61):
            fail(u, f'unexpected original INT {number:02x}')
            return
        resume_ip = u.reg_read(REG_IDS['ip']) & 0xFFFF
        cs = u.reg_read(REG_IDS['cs']) & 0xFFFF
        ss = u.reg_read(REG_IDS['ss']) & 0xFFFF
        sp = u.reg_read(REG_IDS['sp']) & 0xFFFF
        flags = u.reg_read(REG_IDS['flags']) & 0xFFFF
        current_flags = flags
        # Declared real-mode INT frame order, shared with the C transport.
        sp = (sp - 2) & 0xFFFF
        write_word(ss, sp, flags)
        u.reg_write(REG_IDS['sp'], sp)
        current_flags = flags & ~0x0300
        u.reg_write(REG_IDS['flags'], current_flags)
        sp = push_word(u, ss, sp, cs, current_flags)
        sp = push_word(u, ss, sp, resume_ip, current_flags)
        if number == 0x60:
            target_cs, target_ip = read_word(0, 0x182), read_word(0, 0x180)
            binding = case.get('pc_binding', True)
            bound_seg = case.get('pc_binding_segment', PC_SEG)
            if binding is False or target_cs != bound_seg or target_ip != PC_ENTRY:
                u.reg_write(REG_IDS['cs'], target_cs)
                u.reg_write(REG_IDS['ip'], target_ip)
                stop(u, 1)
                return
            interrupt_returns.append(('pc', cs, resume_ip))
        else:
            target_cs, target_ip = read_word(0, 0x186), read_word(0, 0x184)
            binding = case.get('sound_binding', True)
            bound_seg = case.get('sound_binding_segment', SOUND_SEG)
            if (binding is False or target_cs != bound_seg or target_ip != 0):
                u.reg_write(REG_IDS['cs'], target_cs)
                u.reg_write(REG_IDS['ip'], target_ip)
                stop(u, 1)
                return
            interrupt_returns.append(('sound', cs, resume_ip))
        u.reg_write(REG_IDS['cs'], target_cs)
        u.reg_write(REG_IDS['ip'], target_ip)
        # INT defines cleared IF/TF; it does not define undefined arithmetic bits.
        current_mask |= 0x0300

    def code(u, _address, _size, _):
        nonlocal previous, current_flags, current_mask, steps
        steps += 1
        if steps > instruction_limit:
            fail(u, 'original instruction-hook budget exhausted')
            return
        cs = u.reg_read(REG_IDS['cs']) & 0xFFFF
        off = u.reg_read(REG_IDS['ip']) & 0xFFFF
        if previous is not None:
            source, prev_off, prev_ins = previous
            if (prev_ins.group(capstone.CS_GRP_JUMP) or
                    prev_ins.mnemonic.lower() in ('loop', 'loope', 'loopne', 'jcxz')):
                edges.add((source, prev_off, off))
            current_mask = flags_after(prev_ins, current_mask)
            complete = getattr(access, 'instruction_complete', None)
            if complete is not None:
                complete()
            if source == 'main' and prev_ins.mnemonic == 'ret':
                if main_returns:
                    allowed, expected_cs, expected_ip, changed_status = main_returns.pop()
                    if prev_off not in allowed:
                        fail(u, f'original main RET {prev_off:04x} outside CALL contract')
                        return
                    if cs != expected_cs or off != expected_ip:
                        stop(u, changed_status)
                        return
                elif prev_off in return_contracts:
                    expected_ip, changed_status = return_contracts[prev_off]
                    if cs != regs['cs'] or off != expected_ip:
                        stop(u, changed_status)
                        return
                else:
                    stop(u, 0)
                    return
            if (source == 'main' and prev_ins.mnemonic == 'call' and
                    prev_off in call_contracts):
                allowed, changed_status = call_contracts[prev_off]
                main_returns.append((set(allowed), regs['cs'],
                                     (prev_off + prev_ins.size) & 0xFFFF,
                                     changed_status))
            if source == 'pc-child' and prev_ins.mnemonic == 'ret':
                expected = child_returns.pop() if child_returns else None
                if expected is None or cs != expected[0] or off != expected[1]:
                    stop(u, 3)
                    return
            if prev_ins.mnemonic == 'iret' and source in ('pc', 'sound'):
                expected = interrupt_returns.pop() if interrupt_returns else None
                if expected is None or cs != expected[1] or off != expected[2]:
                    stop(u, 4)
                    return
            if source == 'pc' and prev_ins.mnemonic == 'call':
                call_targets.add(off)
                child_returns.append((PC_SEG, (prev_off + prev_ins.size) & 0xFFFF))
                if off not in (pc_dispatch.LOAD_EFFECT, pc_dispatch.STOP):
                    stop(u, 2)
                    return

        current_flags = u.reg_read(REG_IDS['flags']) & 0xFFFF
        if cs == regs['cs'] and off in stops:
            stop(u, stops[off])
            return
        if cs == regs['cs'] and off in main_code:
            if core and off in main_rets:
                stop(u, 0)
                return
            ins, source = main_code[off], 'main'
        elif cs == PC_SEG and off in pc_dispatch.PARENT_INS:
            ins, source = pc_dispatch.PARENT_INS[off], 'pc'
        elif cs == PC_SEG and off in pc_dispatch.CHILD_INS:
            ins, source = pc_dispatch.CHILD_INS[off], 'pc-child'
        elif cs == SOUND_SEG and off in DRIVER_INS[case.get('driver', 'adlib')]:
            ins, source = DRIVER_INS[case.get('driver', 'adlib')][off], 'sound'
        else:
            fail(u, f'original escaped declared code at {cs:04x}:{off:04x}')
            return

        if source == 'main':
            expected = IMAGE[off:off + ins.size]
        elif source in ('pc', 'pc-child'):
            expected = PC_IMAGE[off:off + ins.size]
        else:
            expected = sound.IMAGES[case.get('driver', 'adlib')][0][off:off + ins.size]
        actual = bytes(u.mem_read(physical(cs, off), ins.size))
        if actual != expected:
            fail(u, f'original code changed at {cs:04x}:{off:04x}: '
                    f'{actual.hex()}/{expected.hex()}')
            return
        previous = (source, off, ins)
        sites.add((source, off))

    def on_read(u, _kind, address, size, _value, _):
        for delta in range(size):
            access.access('read', address + delta, current_flags, current_mask)

    def on_write(u, _kind, address, size, value, _):
        for delta in range(size):
            access.access('write', address + delta, current_flags, current_mask,
                          (value >> (delta * 8)) & 0xFF)

    def on_out(u, port, size, value, _):
        output = getattr(access, 'out_word', None)
        if size != 2 or output is None:
            fail(u, 'unexpected original OUT outside declared word-port domain')
            return
        try:
            output(port, value, current_flags, current_mask)
        except Exception as error:
            fail(u, 'original OUT provider failed: ' + str(error))

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_INTR, interrupt)
    cpu.hook_add(UC_HOOK_MEM_READ, on_read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
    cpu.hook_add(UC_HOOK_INSN, on_out, None, 1, 0, UC_X86_INS_OUT)
    try:
        cpu.emu_start(physical(regs['cs'], regs['ip']), 0, count=instruction_limit)
    except UcError as error:
        raise OracleFailure(case['name'] + ': bounded original execution failed') from error
    oracle_require(stopped and failure is None,
                   case['name'] + ': ' + (failure or 'did not reach the declared boundary'))
    state = {name: cpu.reg_read(REG_IDS[name]) & 0xFFFF for name in REG_NAMES}
    oracle_require(bytes(cpu.mem_read(0, SIZE)) == bytes(memory),
                   case['name'] + ': original RAM mirror diverged')
    return dict(memory=bytes(memory), regs=state, device=device,
                events=access.events, used=access.used, status=status,
                continuation=state['ip'],
                sites=sites, edges=edges, call_targets=call_targets,
                flag_mask=current_mask, steps=steps,
                boundary='core-ret' if core else 'adapter-ret')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-interactions-{mutation}.dll',
                     mutation, 'entity_interactions')
        self.lib = ct.CDLL(str(path))
        self.lib.lmn_entity_interactions_core.argtypes = [
            MEM, ct.POINTER(Call), ct.POINTER(PcBinding),
            ct.POINTER(SoundBinding), ct.POINTER(Bus)]
        self.lib.lmn_entity_interactions_core.restype = Result
        self.lib.lmn_entity_interactions_adapter.argtypes = [
            MEM, ct.POINTER(Regs), ct.POINTER(PcBinding),
            ct.POINTER(SoundBinding), ct.POINTER(Bus)]
        self.lib.lmn_entity_interactions_adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, pc_binding, sound_binding,
            core, null_bus=False):
        access = Access(case, memory, regs, device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_BUDGET_EXIT if 'budget' in str(error)
                            else CALLBACK_ERROR_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_BUDGET_EXIT if 'budget' in str(error)
                            else CALLBACK_ERROR_EXIT, error)

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_ERROR_EXIT,
                        f'unexpected entity-interactions port {port:04x}={value:04x}')

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        pc = ct.byref(pc_binding) if pc_binding is not None else None
        sb = ct.byref(sound_binding) if sound_binding is not None else None
        bus_ptr = None if null_bus else ct.byref(bus)
        if core:
            call = Call(regs['cx'], regs['dx'], regs['si'], regs['di'],
                        regs['ds'], regs['cs'], regs['ss'], regs['sp'], regs['flags'])
            result = self.lib.lmn_entity_interactions_core(
                ram, ct.byref(call), pc, sb, bus_ptr)
            state.ax = result.value
            state.bx = result.map_cursor
            state.cx = result.count
            state.dx = result.auxiliary_value
            state.si = result.record_cursor
            state.di = result.object_cursor
            state.ds = result.data_segment
            state.cs = result.code_segment
            state.ss = result.stack_segment
            state.sp = result.stack_offset
            state.flags = result.flags
            state.ip = result.continuation
            status = result.status
        else:
            status = self.lib.lmn_entity_interactions_adapter(
                ram, ct.byref(state), pc, sb, bus_ptr)
        return dict(memory=bytes(memory), regs={name: getattr(state, name)
                                               for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status)


def compare(native, case, core=True, null_bus=False):
    memory, regs, device, pc_binding, sound_binding, offsets = setup(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs), copy.deepcopy(device), core)
    if 'pc_table_target' in case:
        oracle_require(expected['status'] == 2 and expected['regs']['ip'] == 0x01B3 and
                       expected['regs']['sp'] == ((regs['sp'] - 20) & 0xFFFF) and
                       0x01B3 in expected['call_targets'],
                       label + ': untranslated LoadEffect interior seam was not reached exactly')
    actual = native.run(case, bytearray(memory), dict(regs), copy.deepcopy(device),
                        pc_binding, sound_binding, core, null_bus)
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    for name in REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04x}/'
                f'{expected["regs"][name]:04x} under {mask:04x}')
    if not null_bus:
        require(len(actual['events']) == len(expected['events']),
                f'{label}: event count {len(actual["events"])}/{len(expected["events"])}')
        for index, (got, ref) in enumerate(zip(actual['events'], expected['events'])):
            require(got[:3] == ref[:3],
                    f'{label}: event {index} {got[:3]!r}/{ref[:3]!r} '
                    )
            require(((got[3] ^ ref[3]) & ref[4]) == 0,
                    f'{label}: event {index} flags {got[3]:04x}/{ref[3]:04x} '
                    f'under {ref[4]:04x}')
        require(actual['used'] == expected['used'],
                f'{label}: provider transitions {actual["used"]}/{expected["used"]}')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA state differs')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(got_trace == ref_trace, label + ': VGA trace differs')
    # Independent map arithmetic/store check, separate from native comparison.
    first, second = offsets
    if 'map-check' in case:
        expected_first = case.get('sample', 0)
        expected_second = case.get('second_sample', expected_first)
        oracle_require(get8(expected['memory'], regs['ds'], regs['si'] + 0x2C) == expected_first,
                       label + ': first SS sample was not installed in record+2C')
        oracle_require(get8(expected['memory'], regs['ds'], regs['si'] + 0x2B) == expected_second,
                       label + ': second SS sample was not installed in record+2B')
    if case.get('provider'):
        oracle_require(expected['used'], label + ': requested provider was not observed')
    return expected


def cases():
    rows = [dict(name=f'map-byte-{value:02x}', sample=value,
                 second_sample=value, **{'map-check': True}) for value in range(256)]
    rows += [
        dict(name='early-y-af', y=0x00AF, sample=0),
        dict(name='early-y-b0', y=0x00B0, sample=0),
        dict(name='signed-y-negative-wrap', y=0xFFF0, sample=0x20),
        dict(name='y-underflow-zero', y=0, sample=0x20),
        dict(name='x-low-three', x=3, sample=0x10),
        dict(name='x-ffff-wrap', x=0xFFFF, sample=0x10),
        dict(name='record-offset-wrap', si=0xFFF0, sample=0x20),
        dict(name='physical-source-wrap', ss=0xFFFF, x=0, sample=0x20),
        dict(name='ss-map-record-alias', ds=0x5000, ss=0x5000,
             sample=0x20, second_sample=0x30),
        dict(name='vga-map-read', ss=0x9FFF, sample=0x10, vga=True),
        dict(name='low-one-branch-skip', sample=1, record_bits=4),
        dict(name='low-five-branch-skip', sample=5, record_bits=0x1000),
        dict(name='low-six-branch-skip', sample=6, record_bits=0x4000),
        dict(name='negative-ff-case2', sample=2, record_delta=0xFF),
        dict(name='negative-01-case3', sample=3, record_delta=1),
        dict(name='negative-zero-case2', sample=2, record_delta=0),
        dict(name='negative-80-case3', sample=3, record_delta=0x80),
        dict(name='transition-one-no-sound', sample=1, record_bits=0,
             enabled=0xFF, options=0),
        dict(name='transition-one-pc-only', sample=1, record_bits=0,
             enabled=0, options=1),
        dict(name='transition-one-pc-disabled-option', sample=1, record_bits=0,
             enabled=0, options=0),
        dict(name='transition-one-external-only', sample=1, record_bits=0,
             enabled=0xFF, options=3),
        dict(name='transition-five-sound', sample=5, record_bits=0,
             enabled=0xFF, options=3),
        dict(name='transition-five-enabled-options-off', sample=5, record_bits=0,
             enabled=0xFF, options=0),
        dict(name='transition-five-disabled', sample=5, record_bits=0,
             enabled=0, options=3),
        dict(name='transition-six-sound', sample=6, record_bits=0,
             enabled=0xFF, options=3),
        dict(name='transition-six-enabled-options-off', sample=6, record_bits=0,
             enabled=0xFF, options=0),
        dict(name='transition-six-disabled', sample=6, record_bits=0,
             enabled=0, options=3),
        dict(name='object-live-al-byte', sample=4,
             record_bits=0, enabled=0xFF, options=3, object_word=0,
             object_sound=0x05, object_index=0),
        dict(name='object-bit-already-set', sample=4, record_bits=0,
             enabled=0xFF, options=3, object_word=2, object_sound=0xA5),
        dict(name='object-options-disabled', sample=4, record_bits=0,
             enabled=0xFF, options=0, object_word=0, object_sound=0x05),
        dict(name='object-sound-byte-zero', sample=4, record_bits=0,
             enabled=0xFF, options=3, object_word=0, object_sound=0),
        dict(name='object-entity-store-alias', sample=4, si=0x17C0,
             record_bits=0, enabled=0xFF, options=3, object_word=0,
             object_sound=0x05, object_index=0),
        dict(name='pc-unbound-vector', sample=1, record_bits=0,
             enabled=0, options=1, pc_vector=(0x0182, 0x6200)),
        dict(name='sound-unbound-vector', sample=5, record_bits=0,
             enabled=0xFF, options=3, sound_vector=(0, 0x6200)),
        dict(name='pc-unbound-binding', sample=1, record_bits=0,
             enabled=0, options=1, pc_binding=False),
        dict(name='sound-unbound-binding', sample=5, record_bits=0,
             enabled=0xFF, options=3, sound_binding=False),
        dict(name='pc-changed-child-return', sample=1, record_bits=0,
             enabled=0, options=1, provider='pc-child-return'),
        dict(name='pc-changed-interrupt-return', sample=1, record_bits=0,
             enabled=0, options=1, provider='pc-interrupt-return'),
        dict(name='sound-changed-interrupt-return', sample=5, record_bits=0,
             enabled=0xFF, options=3, provider='sound-interrupt-return'),
        dict(name='pc-live-saved-registers-and-second-gate', sample=1,
             record_bits=0, enabled=0, options=1, provider='pc-registers',
             provider_ds=0x6200, provider_si=0x7070, provider_cx=0x3131,
             provider_enabled=0xFF, provider_options=3),
        dict(name='pc-untranslated-effect-interior', sample=1, record_bits=0,
             enabled=0, options=1, pc_table_target=0x01B3),
        dict(name='pc-second-gate-live-provider', sample=1, record_bits=0,
             enabled=0, options=1, provider='pc-second-gate',
             provider_ds=0x6200, provider_flags=0x0002,
             provider_enabled=0xFF, provider_options=3),
        dict(name='saved-ax-map-alias', sample=4, second_sample=5,
             ds=0x5000, ss=0x5000, sp=0xD000, si=0xCFD3,
             record_bits=0, enabled=0, options=0,
             object_word=0, object_sound=0x05, object_index=0),
        dict(name='low-two-no-sound', sample=2, record_delta=0x80,
             record_bits=0, enabled=0, options=0),
        dict(name='outer-ret-live-stack-alias', sample=0xAA, second_sample=0xBB,
             ds=0x5000, ss=0x5000, sp=0xD000, si=0xCFD4,
             record_bits=0xFFFF),
        dict(name='adlib-0411', sample=5, driver='adlib', record_bits=0,
             enabled=0xFF, options=3),
        dict(name='tandy-040d', sample=6, driver='tandysnd', record_bits=0,
             enabled=0xFF, options=3),
        dict(name='poison-no-op', poison=True, seed=0x2EC101, sample=0,
             flags=0x0A47, ax=0x1357, bx=0xBDF1),
        dict(name='poison-neg-entry-flags', poison=True, seed=0x2EC102,
             sample=2, record_delta=0x80, record_bits=0),
        dict(name='poison-object-alias', poison=True, seed=0x2EC103,
             sample=4, si=0x17C0, record_bits=0, enabled=0xFF, options=3,
             object_word=0, object_sound=0x05, object_index=0),
        dict(name='poison-transition-five', poison=True, seed=0x2EC104,
             sample=5, record_bits=0, enabled=0xFF, options=3, driver='tandysnd'),
        dict(name='poison-pc-saved-registers', poison=True, seed=0x2EC105,
             sample=1, record_bits=0, enabled=0, options=1, provider='pc-registers',
             provider_ds=0x6200, provider_si=0x7070, provider_cx=0x3131,
             provider_enabled=0xFF, provider_options=3),
        dict(name='poison-transition-six', poison=True, seed=0x2EC106,
             sample=6, record_bits=0, enabled=0xFF, options=3),
        dict(name='poison-early-return', poison=True, seed=0x2EC107,
             y=0x00B0, flags=0x0A02),
        dict(name='poison-live-outer-ret', poison=True, seed=0x2EC108,
             sample=0xAA, second_sample=0xBB, ds=0x5000, ss=0x5000,
             sp=0xD000, si=0xCFD4, record_bits=0xFFFF),
    ]
    return rows


def input_hashes():
    paths = [
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'c/entity_interactions.c',
        'c/entity_interactions.h', 'c/pcspeaker_interrupt.c',
        'c/pcspeaker_interrupt.h', 'c/pcspeaker_dispatch.c',
        'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/pcspeaker_sym.h', 'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json', 'metadata/toolchain-lock.json',
        'src/game_code.asm', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/resources.py', 'tools/unpack.py',
        'tools/difftest.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(len(IMAGE) == 82906 and
                   sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'static main image identity changed')
    oracle_require(len(MAIN_INS) == 162 and END - ENTRY == 486,
                   '2EC0 instruction inventory changed')
    oracle_require(len(PC_IMAGE) == 758 and PC_META['section_index'] == 5 and
                   PC_META['entry_offset'] == PC_ENTRY,
                   'PC-speaker image identity/entry changed')

    baseline = Native(directory)
    fixture_rows = cases()
    sites, edges, calls, executed_int_sites = set(), set(), set(), set()
    pc_sites, sound_sites = set(), set()
    event_count = instruction_count = 0
    rows = []
    for case in fixture_rows:
        boundary_results = []
        for core in (True, False):
            result = compare(baseline, case, core)
            boundary_results.append(result)
            sites.update(off for scope, off in result['sites'] if scope == 'main')
            pc_sites.update(off for scope, off in result['sites'] if scope in ('pc', 'pc-child'))
            sound_sites.update(off for scope, off in result['sites'] if scope == 'sound')
            executed_int_sites.update(off for scope, off in result['sites']
                                      if scope == 'main' and MAIN_INS[off].mnemonic == 'int')
            edges.update((src, dst) for scope, src, dst in result['edges'] if scope == 'main')
            calls.update(result['call_targets'])
            event_count += len(result['events'])
            instruction_count += result['steps']
        rows.append(dict(name=case['name'],
                         boundaries=['core-before-ret', 'register-adapter'],
                         status=[result['status'] for result in boundary_results],
                         provider=case.get('provider'), driver=case.get('driver', 'adlib'),
                         first_sample=case.get('sample', 0),
                         second_sample=case.get('second_sample', case.get('sample', 0)),
                         first_offset=map_offsets(case.get('x', 4), case.get('y', 0x20),
                                                  case.get('record_delta', 0))[0],
                         second_offset=map_offsets(case.get('x', 4), case.get('y', 0x20),
                                                   case.get('record_delta', 0))[1]))
        gc.collect()

    expected_sites = set(MAIN_INS)
    oracle_require(sites == expected_sites,
                   f'2EC0 executed-site union differs: {sites ^ expected_sites}')
    static_branches = {address: ins for address, ins in MAIN_INS.items()
                       if ins.group(capstone.CS_GRP_JUMP)}
    expected_branch_sites = set(static_branches)
    observed_branch_sites = {source for source, _destination in edges}
    oracle_require(observed_branch_sites == expected_branch_sites,
                   '2EC0 branch-site coverage differs: '
                   f'{observed_branch_sites ^ expected_branch_sites}')
    static_branch_edges = set()
    for source, ins in static_branches.items():
        if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
            static_branch_edges.add((source, (source + ins.size) & 0xFFFF))
        if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
            static_branch_edges.add((source, ins.operands[-1].imm & 0xFFFF))
    oracle_require(edges == static_branch_edges,
                   '2EC0 branch-edge union differs: '
                   f'missing={static_branch_edges - edges}, extra={edges - static_branch_edges}')
    # All five downstream INT call sites are recovered from the original bytes.
    expected_calls = {0x2F8C, 0x2F9F, 0x2FF5, 0x304C, 0x30A3}
    oracle_require(executed_int_sites == expected_calls,
                   f'not all five original INT sites executed: {executed_int_sites ^ expected_calls}')

    # A direct-memory repetition checks the optional bus path separately.
    for name in ('map-byte-00', 'low-two-no-sound', 'transition-five-sound'):
        case = next(row for row in fixture_rows if row['name'] == name)
        for core in (True, False):
            compare(baseline, case, core, null_bus=True)

    witnesses = [
        (1, 'signed-y-negative-wrap'),
        (2, 'saved-ax-map-alias'),
        (3, 'y-underflow-zero'),
        (4, 'negative-80-case3'),
        (5, 'object-entity-store-alias'),
        (6, 'pc-live-saved-registers-and-second-gate'),
        (7, 'pc-second-gate-live-provider'),
        (8, 'outer-ret-live-stack-alias'),
    ]
    by_name = {case['name']: case for case in fixture_rows}
    mutations = []
    for number, name in witnesses:
        mutant = Native(directory, number)
        case = by_name[name]
        try:
            compare(mutant, case, core=False)
        except Mismatch as error:
            mutations.append(dict(mutation=number, case=name, completed=True,
                                  mismatch=str(error)))
        else:
            raise OracleFailure(f'entity-interactions mutation {number} survived')
        gc.collect()

    oracle_require(before == input_hashes(),
                   'inputs changed during bounded entity-interactions campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        pc_speaker_image_sha256=sha(PC_IMAGE),
        driver_image_sha256={name: sha(sound.IMAGES[name][0]) for name in sound.TAILS},
        case_count=len(rows), comparisons=len(rows) * 2, cases=rows,
        translated_code_bytes=END - ENTRY, native_code_ranges=[[ENTRY, END]],
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        static_branch_sites=sorted(expected_branch_sites),
        static_branch_edges=sorted(static_branch_edges),
        pc_dispatch_instruction_addresses=sorted(pc_sites),
        sound_driver_instruction_addresses=sorted(sound_sites),
        dynamic_pc_call_targets=sorted(calls), total_bus_events=event_count,
        original_instructions_executed=instruction_count,
        mutation_count=len(mutations), mutations=mutations, input_hashes=before,
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_tree_mib=640, original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    native_callback_budget=MAX_BUS_EVENTS,
                    callback_budget_exit=CALLBACK_BUDGET_EXIT,
                    callback_error_exit=CALLBACK_ERROR_EXIT),
        entry_flags_contract='constructed input FLAGS are normalized as '
                             '((raw & 0x7FD5) | 2) with TF cleared; arbitrary saved '
                             'frame words remain unnormalized and are compared byte-for-byte',
        interrupt_flags_diagnostic='Unicorn preserves injected reserved bits 3/5/15 across '
                                    'IRET: entry 002A, saved 0006 -> 002E; entry 0002, '
                                    'saved FFFF -> 7FD7; entry 0002, saved 002A -> 0002',
        domain='2EC0..30A5 original/C composition at pre-RET core and real-RET adapter; '
               'SS interaction-map reads, all map-byte/nibble values, signed wrapped coordinates, '
               'record/object aliases and live transition fields; declared INT60 PC LoadEffect and '
               'INT61 AdLib/Tandy command-4 paths with exact vector/frame/IRET seams; bounded VGA '
               'map and physical memory wrap fixtures; no gameplay readiness, IRQ timing, playback, '
               'or untranslated service behavior claim'))
    print(f'PASS entity interactions: {len(rows)} fixtures at core+adapter; '
          f'{END-ENTRY} bytes/{len(sites)} main sites/{len(edges)} edges; '
          f'{len(pc_sites)} PC sites/{len(sound_sites)} sound sites; '
          f'{event_count} events; {len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-interactions arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-interactions-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
