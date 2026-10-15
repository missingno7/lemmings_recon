"""Bounded original-versus-C checks for the declared INT 60 transport."""
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
from resources import sound_images
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_INTR, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x

SIZE, MASK = 1 << 20, (1 << 20) - 1
ALL_FLAGS = 0x0FD7
IF, TF, CF, AF = 0x0200, 0x0100, 0x0001, 0x0010
LOGIC_FLAGS = ALL_FLAGS & ~AF
MUL_FLAGS = 0x0801
IRET_FLAGS = 0x7FD5
DRIVER_IMAGE, IMAGE_META = sound_images()['pcspeaker']
DRIVER_SEGMENT = IMAGE_META['load_frame']
ENTRY, PARENT_END = 0x0182, 0x01B0
CALL, CALL_RETURN, IRET = 0x0196, 0x019A, 0x01A0
LOAD_EFFECT, LOAD_END = 0x01B0, 0x01D4
STOP, STOP_END = 0x024F, 0x0255
CALLER_SEGMENT, CALLER_IP = 0x3100, 0x0100
MAX_STEPS, MAX_EVENTS = 512, 2048
CALLBACK_BUDGET_EXIT, CALLBACK_ERROR_EXIT = 86, 87
PINNED_IMAGE_SHA256 = 'bdc1da6ea085bd247ab3060dfc78f522f7b447dcffe7235a3e19bf9938731287'
REPORT = BUILD / 'pcspeaker-interrupt-differential.json'

REG_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
             'cs', 'ds', 'es', 'ss', 'ip', 'flags')
REG_IDS = {name: getattr(x, 'UC_X86_REG_' + name.upper())
           for name in REG_NAMES if name != 'flags'}
REG_IDS['flags'] = x.UC_X86_REG_EFLAGS
MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_INS = {ins.address: ins for ins in MD.disasm(
    DRIVER_IMAGE[ENTRY:PARENT_END], ENTRY)}
CHILD_INS = {}
for _start, _end in ((LOAD_EFFECT, LOAD_END), (STOP, STOP_END)):
    CHILD_INS.update({ins.address: ins for ins in MD.disasm(
        DRIVER_IMAGE[_start:_end], _start)})
PARENT_JUMPS = {pc: ins for pc, ins in PARENT_INS.items()
                if ins.group(capstone.CS_GRP_JUMP)}
EXPECTED_EDGES = set()
for _pc, _ins in PARENT_JUMPS.items():
    EXPECTED_EDGES.add((_pc, _ins.operands[0].imm & 0xFFFF))
    if _ins.mnemonic != 'jmp':
        EXPECTED_EDGES.add((_pc, _ins.address + _ins.size))


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in REG_NAMES]


class Binding(ct.Structure):
    _fields_ = [('driver_segment', ct.c_uint16)]


class Call(ct.Structure):
    _fields_ = [('registers', Regs), ('return_offset', ct.c_uint16)]


class Result(ct.Structure):
    _fields_ = [('registers', Regs), ('status', ct.c_uint16)]


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """The original escaped the declared transport/dispatcher budget."""


class Mismatch(AssertionError):
    """Only a completed original/native comparison is mutation evidence."""


def oracle_require(condition, message):
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


def set_vector(memory, instruction_pointer, code_segment):
    put16(memory, 0, 0x0180, instruction_pointer)
    put16(memory, 0, 0x0182, code_segment)


def flags_after(instruction, previous_mask):
    mnemonic = instruction.mnemonic.lower()
    if mnemonic == 'sti':
        return previous_mask | IF
    if mnemonic in ('and', 'or', 'xor', 'test'):
        return LOGIC_FLAGS
    if mnemonic in ('add', 'sub', 'cmp'):
        return ALL_FLAGS
    if mnemonic in ('inc', 'dec'):
        return (ALL_FLAGS & ~CF) | (previous_mask & CF)
    if mnemonic in ('shl', 'shr', 'sar', 'rol', 'ror'):
        return LOGIC_FLAGS
    if mnemonic in ('mul', 'imul'):
        return MUL_FLAGS
    if mnemonic == 'iret':
        return ALL_FLAGS
    return previous_mask


def cases():
    rows = [
        dict(name='producer-ax-0302', command=3, low=0x02, expected=0),
        dict(name='producer-ax-030c', command=3, low=0x0C, expected=0),
        dict(name='producer-ax-0313', command=3, low=0x13, expected=0),
        dict(name='stop-command', command=1, low=0x5A, expected=0),
        dict(name='tick-child-seam', command=0, low=0x07, expected=2),
        dict(name='zero-table-child-seam', command=2, low=0xA5, expected=2),
        dict(name='explicit-unknown-table-child', command=3, low=0x02,
             table_target=0x3456, expected=2),
        dict(name='raw-getter', command=0x11, low=0x3A, expected=0),
        dict(name='raw-setter', command=0x20, low=0x6D, expected=0),
        dict(name='unbound-vector-segment', command=1, low=0x11,
             vector_segment=0x7100, expected=1),
        dict(name='unbound-vector-offset', command=1, low=0x12,
             vector_ip=0x0100, expected=1),
        dict(name='missing-binding', command=1, low=0x13,
             binding=None, expected=1),
        dict(name='binding-segment-mismatch', command=1, low=0x14,
             binding_segment=0x7100, expected=1),
        dict(name='vector-provider-after-frame-push', command=1, low=0x15,
             vector_segment=0x7100, vector_ip=0x1234,
             vector_provider=True, expected=0),
        dict(name='changed-child-near-return', command=3, low=0x02,
             child_return_provider=0x3456, expected=3),
        dict(name='live-restored-ds-provider', command=3, low=0x0C,
             saved_ds_provider=0x6300, expected=0),
        dict(name='all-saved-registers-live', command=1, low=0x26,
             saved_registers_provider={
                 'bx': 0xB101, 'cx': 0xC202, 'dx': 0xD303,
                 'si': 0x5104, 'di': 0xE505, 'ds': 0xD606}, expected=0),
        dict(name='changed-interrupt-iret-frame', command=1, low=0x17,
             iret_provider=(0x5678, 0x2345, 0xFFFF), expected=4),
        dict(name='initial-if-tf-cleared-during-int', command=3, low=0x02,
             flags=0x0302, expected=0),
        dict(name='stack-offset-underflow', command=1, low=0x18,
             sp=0x0000, expected=0),
        dict(name='stack-offset-word-wrap', command=1, low=0x19,
             sp=0x0001, expected=0),
        dict(name='physical-word-boundary', command=1, low=0x1A,
             ss=0xFFFF, sp=0x0011, expected=0),
        dict(name='vga-stack-frame-and-saves', command=1, low=0x1B,
             ss=0xA000, sp=0x8200, vga=True, expected=0),
        dict(name='vga-mapmask-zero-stack-frame', command=1, low=0x27,
             driver_segment=CALL_RETURN, ss=0xA000, sp=0x8200,
             vga=True, vga_mapmask_zero=True,
             vga_stack_values={
                 'bx': 0xB101, 'cx': 0xC202, 'dx': 0xD303,
                 'si': 0x5104, 'di': 0xE505, 'ds': 0xD606},
             expected=0),
        # With SS:SP=0000:0186, the declared INT writes its IP and CS words
        # directly over IVT 60h, producing a valid self-vector to 0842:0182.
        dict(name='interrupt-frame-overwrites-ivt', command=1, low=0x1C,
             caller_segment=DRIVER_SEGMENT, caller_ip=0x0180,
             ss=0, sp=0x0186, expected=0),
    ]
    return rows


def setup(case):
    seed = 0x60A000 + sum(case['name'].encode('ascii'))
    rng = random.Random(seed)
    memory = bytearray(rng.randbytes(SIZE))
    driver_segment = case.get('driver_segment', DRIVER_SEGMENT)
    for offset, value in enumerate(DRIVER_IMAGE):
        memory[(physical(driver_segment, 0) + offset) & MASK] = value

    caller_segment = case.get('caller_segment', CALLER_SEGMENT)
    caller_ip = case.get('caller_ip', CALLER_IP)
    # This synthetic callsite asks Unicorn to raise the declared INT boundary;
    # it is not counted as pinned executable coverage.
    for index, value in enumerate((0xCD, 0x60)):
        memory[(physical(caller_segment, caller_ip) + index) & MASK] = value

    values = {name: rng.randrange(0x10000) for name in REG_NAMES}
    raw_entry_flags = case.get(
        'flags', (2 | rng.randrange(ALL_FLAGS)) & ~TF)
    entry_flags = (raw_entry_flags & 0x7FD5) | 2
    oracle_require((entry_flags & 0x8028) == 0 and (entry_flags & 2) == 2,
                   case['name'] + ': constructed entry FLAGS has invalid fixed bits')
    values.update(
        ax=((case['command'] & 0xFF) << 8) | (case.get('low', 0xA5) & 0xFF),
        cs=caller_segment, ds=case.get('ds', 0x5100), es=0xA123,
        ss=case.get('ss', 0x7000), sp=case.get('sp', 0x8200),
        ip=caller_ip,
        # Avoid asynchronous debug traps except for the explicit IF/TF case;
        # the INT hook immediately models clearing both bits.
        flags=entry_flags)
    return_offset = case.get('return_offset', (caller_ip + 2) & 0xFFFF)

    vector_segment = case.get('vector_segment', driver_segment)
    vector_ip = case.get('vector_ip', ENTRY)
    set_vector(memory, vector_ip, vector_segment)
    if 'table_target' in case:
        put16(memory, driver_segment,
              0x001E + 2 * case['command'], case['table_target'])

    device = None
    if case.get('vga'):
        device = MinimapVga(seed, read_map=0)
        device.seq[2] = 0 if case.get('vga_mapmask_zero') else 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[4] = device.gc[5] = 0
        device.gc[8] = 0xFF
        for plane in device.planes:
            plane[:] = memory[VGA_BASE:VGA_END]
        if 'vga_stack_values' in case:
            saved = case['vga_stack_values']
            handler_segment = case.get('driver_segment', DRIVER_SEGMENT)
            stack = values['sp']
            frame_words = {
                stack - 20: handler_segment,
                stack - 18: saved['ds'], stack - 16: saved['di'],
                stack - 14: saved['si'], stack - 12: saved['dx'],
                stack - 10: saved['cx'], stack - 8: saved['bx'],
                stack - 6: return_offset, stack - 4: caller_segment,
                stack - 2: values['flags'],
            }
            for stack_offset, word in frame_words.items():
                aperture = physical(values['ss'], stack_offset) - VGA_BASE
                device.planes[0][aperture] = word & 0xFF
                device.planes[0][aperture + 1] = (word >> 8) & 0xFF

    binding = None if case.get('binding', 'present') is None else case.get(
        'binding_segment', driver_segment)
    return memory, values, return_offset, binding, device


class Access:
    def __init__(self, case, memory, regs, device, return_offset):
        self.case, self.memory, self.regs = case, memory, regs
        self.device, self.return_offset = device, return_offset
        self.events, self.used = [], set()
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

    def provider(self, kind, address):
        case, regs = self.case, self.regs
        if (kind == 'write' and case.get('vector_provider') and
                'vector' not in self.used and
                address == physical(regs['ss'], regs['sp'] - 2)):
            self.modify_word(0, 0x0180, ENTRY)
            self.modify_word(0, 0x0182, case.get('driver_segment', DRIVER_SEGMENT))
            self.used.add('vector')

        handler_seg = case.get('driver_segment', DRIVER_SEGMENT)
        body_write = physical(handler_seg, 0x0001)
        if kind == 'write' and address == body_write:
            int_frame_sp = (regs['sp'] - 6) & 0xFFFF
            if ('saved_registers_provider' in case and
                    'saved-registers' not in self.used):
                saved = case['saved_registers_provider']
                offsets = {'bx': -2, 'cx': -4, 'dx': -6,
                           'si': -8, 'di': -10, 'ds': -12}
                for name, relative in offsets.items():
                    self.modify_word(regs['ss'], int_frame_sp + relative,
                                     saved[name])
                self.used.add('saved-registers')
            if 'child_return_provider' in case and 'child-return' not in self.used:
                self.modify_word(regs['ss'], int_frame_sp - 14,
                                 case['child_return_provider'])
                self.used.add('child-return')
            if 'saved_ds_provider' in case and 'saved-ds' not in self.used:
                # Six dispatcher PUSHes follow the three-word INT frame;
                # saved DS is the last of those six words.
                self.modify_word(regs['ss'], int_frame_sp - 12,
                                 case['saved_ds_provider'])
                self.used.add('saved-ds')

        if (kind == 'read' and 'iret_provider' in case and 'iret' not in self.used and
                address == physical(regs['ss'], regs['sp'] - 6)):
            ip, cs, flags = case['iret_provider']
            self.modify_word(regs['ss'], regs['sp'] - 6, ip)
            self.modify_word(regs['ss'], regs['sp'] - 4, cs)
            self.modify_word(regs['ss'], regs['sp'] - 2, flags)
            self.used.add('iret')

    def access(self, kind, address, flags, mask=ALL_FLAGS, value=None):
        if len(self.events) >= MAX_EVENTS:
            raise OracleFailure('PC-speaker INT 60 callback budget exhausted')
        address &= MASK
        self.provider(kind, address)
        if kind == 'read':
            if self.device is not None and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
            else:
                value = self.memory[address]
            self.store(address, value)
        else:
            if self.device is not None and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF, mask))
        return value & 0xFF


def original(case, memory, regs, return_offset, binding, device):
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    cpu.mem_write(0, bytes(memory))
    cpu.mem_write(SIZE, bytes(memory))
    for name in REG_NAMES:
        cpu.reg_write(REG_IDS[name], regs[name])
    access = Access(case, memory, regs, device, return_offset)
    handler_segment = case.get('driver_segment', DRIVER_SEGMENT)

    def mirror(address, value):
        cpu.mem_write(address, bytes((value,)))
        cpu.mem_write(address + SIZE, bytes((value,)))

    access.mirror = mirror
    current_flags = regs['flags']
    current_mask = ALL_FLAGS
    previous = None
    stopped = False
    failure = None
    status = None
    continuation = None
    sites, edges, call_targets = set(), set(), []
    steps = 0

    def stop(u, result_status, target, reason):
        nonlocal stopped, status, continuation
        stopped, status, continuation = True, result_status, target & 0xFFFF
        u.emu_stop()

    def fail(u, reason):
        nonlocal failure
        failure = reason
        u.emu_stop()

    def read_word(seg, off, flags, mask):
        address = physical(seg, off)
        low = access.access('read', address, flags, mask)
        high = access.access('read', address + 1, flags, mask)
        return low | (high << 8)

    def push_word(u, segment, sp, value, flags, mask):
        sp = (sp - 2) & 0xFFFF
        address = physical(segment, sp)
        access.access('write', address, flags, mask, value & 0xFF)
        access.access('write', address + 1, flags, mask, (value >> 8) & 0xFF)
        return sp

    def interrupt(u, number, _):
        nonlocal current_flags, status, failure
        if number == 1 and previous is not None and previous[2].mnemonic == 'iret':
            cs = u.reg_read(REG_IDS['cs']) & 0xFFFF
            off = u.reg_read(REG_IDS['ip']) & 0xFFFF
            result_status = 0 if (cs == regs['cs'] and off == return_offset) else 4
            stop(u, result_status, off, 'post-IRET TF boundary')
            return
        if number != 0x60:
            fail(u, f'unexpected original interrupt {number:02x}')
            return
        entry_flags = u.reg_read(REG_IDS['flags']) & 0xFFFF
        caller_cs = u.reg_read(REG_IDS['cs']) & 0xFFFF
        caller_sp = u.reg_read(REG_IDS['sp']) & 0xFFFF
        resume = u.reg_read(REG_IDS['ip']) & 0xFFFF
        if resume != return_offset:
            fail(u, f'INT hook return offset {resume:04x}/{return_offset:04x}')
            return

        caller_sp = push_word(u, regs['ss'], caller_sp, entry_flags,
                              entry_flags, ALL_FLAGS)
        live_flags = entry_flags & ~(IF | TF)
        u.reg_write(REG_IDS['flags'], live_flags)
        caller_sp = push_word(u, regs['ss'], caller_sp, caller_cs,
                              live_flags, ALL_FLAGS)
        caller_sp = push_word(u, regs['ss'], caller_sp, resume,
                              live_flags, ALL_FLAGS)
        u.reg_write(REG_IDS['sp'], caller_sp)

        vector_cs = read_word(0, 0x0182, live_flags, ALL_FLAGS)
        vector_ip = read_word(0, 0x0180, live_flags, ALL_FLAGS)
        u.reg_write(REG_IDS['cs'], vector_cs)
        u.reg_write(REG_IDS['ip'], vector_ip)
        u.reg_write(REG_IDS['flags'], live_flags)
        current_flags = live_flags
        expected_cs = None if binding is None else binding
        if vector_cs != expected_cs or vector_ip != ENTRY:
            stop(u, 1, vector_ip, 'unbound INT 60 vector')

    def code(u, _address, _size, _):
        nonlocal previous, current_flags, current_mask, steps
        steps += 1
        if steps > MAX_STEPS:
            fail(u, 'original instruction-hook budget exhausted')
            return
        cs = u.reg_read(REG_IDS['cs']) & 0xFFFF
        off = u.reg_read(REG_IDS['ip']) & 0xFFFF

        if previous is not None:
            prev_cs, prev_off, prev_ins = previous
            if prev_cs == handler_segment and prev_off == CALL:
                call_targets.append(off)
                if off not in (LOAD_EFFECT, STOP):
                    stop(u, 2, off, 'untranslated dispatcher child')
                    return
            if prev_cs == handler_segment and prev_ins.mnemonic == 'ret' and off != CALL_RETURN:
                stop(u, 3, off, 'changed child near return')
                return
            if prev_cs == handler_segment and prev_off == IRET:
                result_status = 0 if (cs == regs['cs'] and off == return_offset) else 4
                stop(u, result_status, off, 'completed or changed interrupt IRET')
                return
            if prev_cs == handler_segment and prev_ins.group(capstone.CS_GRP_JUMP):
                edges.add((prev_off, off))
            current_mask = flags_after(prev_ins, current_mask)

        current_flags = u.reg_read(REG_IDS['flags']) & 0xFFFF
        if cs == regs['cs'] and off == regs['ip'] and previous is None:
            raw = bytes(u.mem_read((cs << 4) + off, 2))
            if raw != b'\xCD\x60':
                fail(u, f'constructed INT 60 callsite changed: {raw.hex()}')
                return
            ins = next(MD.disasm(raw, off))
            previous = (cs, off, ins)
            return

        if cs != handler_segment:
            fail(u, f'original escaped declared handler at {cs:04x}:{off:04x}')
            return
        ins = PARENT_INS.get(off)
        if ins is None:
            ins = CHILD_INS.get(off)
        if ins is None:
            fail(u, f'original escaped declared dispatcher/child at {cs:04x}:{off:04x}')
            return
        actual = bytes(u.mem_read((cs << 4) + off, ins.size))
        expected = DRIVER_IMAGE[off:off + ins.size]
        if actual != expected:
            fail(u, f'handler bytes changed at {cs:04x}:{off:04x}: '
                 f'{actual.hex()}/{expected.hex()}')
            return
        sites.add(off)
        previous = (cs, off, ins)

    def read(_u, _kind, address, size, _value, _):
        for delta in range(size):
            access.access('read', address + delta, current_flags, current_mask)

    def write(_u, _kind, address, size, value, _):
        for delta in range(size):
            access.access('write', address + delta, current_flags, current_mask,
                          (value >> (8 * delta)) & 0xFF)

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_INTR, interrupt)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    try:
        cpu.emu_start((regs['cs'] << 4) + regs['ip'], 0, count=MAX_STEPS)
    except UcError as error:
        raise OracleFailure(case['name'] + ': bounded original execution failed') from error
    oracle_require(stopped and failure is None,
                   case['name'] + ': ' + (failure or 'original did not reach a declared seam'))
    state = {name: cpu.reg_read(REG_IDS[name]) & 0xFFFF for name in REG_NAMES}
    oracle_require(bytes(cpu.mem_read(0, SIZE)) == bytes(memory),
                   case['name'] + ': original Unicorn and callback RAM diverged')
    return dict(memory=bytes(memory), regs=state, device=device,
                events=access.events, used=access.used, status=status,
                continuation=continuation, sites=sites, edges=edges,
                call_targets=call_targets, flag_mask=current_mask, steps=steps)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'pcspeaker-interrupt-{mutation}.dll',
                     mutation, 'pcspeaker_interrupt')
        self.lib = ct.CDLL(str(path))
        self.lib.lmn_pc_speaker_interrupt60_core.argtypes = [
            MEM, ct.POINTER(Call), ct.POINTER(Binding), ct.POINTER(Bus)]
        self.lib.lmn_pc_speaker_interrupt60_core.restype = Result

    def run(self, case, memory, regs, return_offset, binding, device):
        access = Access(case, memory, regs, device, return_offset)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags)
            except BaseException as error:
                worker_fail(CALLBACK_BUDGET_EXIT if 'budget exhausted' in str(error)
                            else CALLBACK_ERROR_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, value=value)
            except BaseException as error:
                worker_fail(CALLBACK_BUDGET_EXIT if 'budget exhausted' in str(error)
                            else CALLBACK_ERROR_EXIT, error)

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_ERROR_EXIT,
                        f'unexpected PC-speaker INT 60 port output '
                        f'{port:04x}={value:04x} flags={flags:04x}')

        callbacks = READ(read), WRITE(write), OUT(out)
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        call = Call(state, return_offset)
        bound = None if binding is None else Binding(binding)
        result = self.lib.lmn_pc_speaker_interrupt60_core(
            ram, ct.byref(call), None if bound is None else ct.byref(bound),
            ct.byref(bus))
        returned = result.registers
        return dict(memory=bytes(memory),
                    regs={name: getattr(returned, name) for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=result.status)


def compare(native, case):
    memory, regs, return_offset, binding, device = setup(case)
    expected = original(case, bytearray(memory), dict(regs), return_offset,
                        binding, copy.deepcopy(device))
    oracle_require(expected['status'] == case['expected'],
                   case['name'] + f': original status {expected["status"]} '
                   f'differs from declared {case["expected"]}')
    actual = native.run(case, bytearray(memory), dict(regs), return_offset,
                        binding, copy.deepcopy(device))
    label = case['name']
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    if actual['memory'] != expected['memory']:
        where = next(index for index, (got, ref) in enumerate(
            zip(actual['memory'], expected['memory'])) if got != ref)
        raise Mismatch(f'{label}: RAM {where:05x} {actual["memory"][where]:02x}/'
                       f'{expected["memory"][where]:02x}')
    for name in REG_NAMES:
        mask = (0xFFFF if name != 'flags' or expected['status'] in (0, 4)
                else ALL_FLAGS)
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04x}/'
                f'{expected["regs"][name]:04x} under {mask:04x}')
    require(len(actual['events']) == len(expected['events']),
            label + ': ordered access count differs')
    for index, (got, ref) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == ref[:3],
                f'{label}: access {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: access {index} flags {got[3]:04x}/{ref[3]:04x} '
                f'under {ref[4]:04x}')
    require(actual['used'] == expected['used'], label + ': provider trigger differs')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA planes/latches/registers differ')
        got_trace = [(event[0], event[1], event[2])
                     for event in actual['device'].trace]
        ref_trace = [(event[0], event[1], event[2])
                     for event in expected['device'].trace]
        require(got_trace == ref_trace, label + ': VGA access trace differs')

    if expected['status'] == 0:
        want_ip = case.get('return_offset', (regs['ip'] + 2) & 0xFFFF)
        require(expected['regs']['ip'] == want_ip and
                expected['regs']['cs'] == regs['cs'] and
                expected['regs']['sp'] == regs['sp'],
                label + ': original IRET did not restore caller CS:IP:SP')
        saved_registers = case.get('saved_registers_provider',
                                   case.get('vga_stack_values', {}))
        for name in ('bx', 'cx', 'dx', 'si', 'di', 'bp', 'es', 'ss'):
            wanted = saved_registers.get(name, regs[name])
            oracle_require(expected['regs'][name] == wanted,
                           label + f': original failed to preserve {name}')
        oracle_require(expected['regs']['ds'] ==
                       saved_registers.get('ds',
                           case.get('saved_ds_provider', regs['ds'])),
                       label + ': original DS did not follow its live saved word')
        if 'iret_provider' not in case:
            frame_sp = (regs['sp'] - 6) & 0xFFFF
            oracle_require(get16(expected['memory'], regs['ss'], frame_sp) == want_ip and
                           get16(expected['memory'], regs['ss'], frame_sp + 2) == regs['cs'] and
                           get16(expected['memory'], regs['ss'], frame_sp + 4) == regs['flags'],
                           label + ': independent INT frame layout differs')
    if case['name'] == 'changed-child-near-return':
        oracle_require(expected['continuation'] == case['child_return_provider'],
                       label + ': original did not stop at changed child RET target')
    if case['name'] == 'changed-interrupt-iret-frame':
        oracle_require((expected['regs']['cs'], expected['regs']['ip']) ==
                       (case['iret_provider'][1], case['iret_provider'][0]),
                       label + ': original did not consume changed IRET frame')
    for source_name in ('saved_registers_provider', 'vga_stack_values'):
        if source_name in case:
            for register, value in case[source_name].items():
                require(actual['regs'][register] == value,
                        f'{label}: returned {register} did not use live stack word')
    if 'saved_registers_provider' in case:
        oracle_require('saved-registers' in expected['used'],
                       label + ': saved-register provider did not run')
    if 'vga_stack_values' in case:
        oracle_require(expected['device'].seq[2] == 0,
                       label + ': VGA map mask was not zero')
        stack = regs['sp']
        vga_words = {
            stack - 20: case.get('driver_segment', DRIVER_SEGMENT),
            stack - 18: case['vga_stack_values']['ds'],
            stack - 16: case['vga_stack_values']['di'],
            stack - 14: case['vga_stack_values']['si'],
            stack - 12: case['vga_stack_values']['dx'],
            stack - 10: case['vga_stack_values']['cx'],
            stack - 8: case['vga_stack_values']['bx'],
            stack - 6: return_offset, stack - 4: regs['cs'],
            stack - 2: regs['flags'],
        }
        for stack_offset, word in vga_words.items():
            aperture = physical(regs['ss'], stack_offset) - VGA_BASE
            observed = expected['device'].planes[0][aperture:aperture + 2]
            oracle_require(observed == bytes((word & 0xFF, word >> 8)),
                           label + f': map-mask-zero plane changed at {stack_offset:04x}')
    return expected


def input_hashes():
    paths = [
        'assets/main.dat', 'c/lemmings_sym.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/pcspeaker_sym.h', 'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h', 'c/regs.h',
        'c/special_blit.h', 'metadata/hints.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/regions.json',
        'metadata/sound-oracle.json', 'metadata/toolchain-lock.json',
        'src/game_code.asm', 'src/image_tail.asm', 'src/sound/pcspeaker.asm',
        'tests/minimap_vga.py', 'tests/pcspeaker_interrupt.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(len(DRIVER_IMAGE) == 758 and sha(DRIVER_IMAGE) == PINNED_IMAGE_SHA256,
                   'PC-speaker component image identity changed')
    oracle_require(IMAGE_META['section_index'] == 5 and
                   IMAGE_META['entry_offset'] == ENTRY and
                   DRIVER_SEGMENT == 0x0842,
                   'PC-speaker section/load/entry identity changed')
    oracle_require(len(PARENT_INS) == 29 and len(CHILD_INS) == 18,
                   'dispatcher/child instruction inventory changed')
    oracle_require(len(EXPECTED_EDGES) == 6,
                   'dispatcher static edge inventory changed')

    caseset = cases()
    baseline = Native(directory)
    rows, sites, child_sites, edges, call_targets = [], set(), set(), set(), set()
    event_count = 0
    for case in caseset:
        result = compare(baseline, case)
        sites.update(site for site in result['sites'] if site in PARENT_INS)
        child_sites.update(site for site in result['sites'] if site in CHILD_INS)
        edges.update(result['edges'])
        call_targets.update(result['call_targets'])
        event_count += len(result['events'])
        rows.append(dict(name=case['name'], command=case['command'],
                         expected_status=case['expected'], actual_status=result['status'],
                         continuation=result['continuation'],
                         final_data_segment=result['regs']['ds'],
                         observed_providers=sorted(result['used']),
                         vector_provider=case.get('vector_provider', False),
                         saved_ds_provider=case.get('saved_ds_provider'),
                         child_return_provider=case.get('child_return_provider'),
                         iret_provider=case.get('iret_provider'),
                         vga=case.get('vga', False)))
        gc.collect()

    oracle_require(sites == set(PARENT_INS),
                   f'dispatch instruction coverage differs: {sites ^ set(PARENT_INS)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'dispatch branch edges differ: {edges ^ EXPECTED_EDGES}')
    oracle_require({0, STOP, LOAD_EFFECT, 0x01D4}.issubset(call_targets),
                   f'Tick/Stop/LoadEffect/unknown child seams missing: {call_targets}')
    for name, status, continuation, provider in (
            ('vector-provider-after-frame-push', 0, (CALLER_IP + 2) & 0xFFFF, 'vector'),
            ('changed-child-near-return', 3, 0x3456, 'child-return'),
            ('live-restored-ds-provider', 0, (CALLER_IP + 2) & 0xFFFF, 'saved-ds'),
            ('changed-interrupt-iret-frame', 4, 0x5678, 'iret')):
        row = next(item for item in rows if item['name'] == name)
        oracle_require(row['actual_status'] == status,
                       name + ': declared status witness was not reached')
        oracle_require(row['continuation'] == continuation and
                       provider in row['observed_providers'],
                       name + ': live provider/continuation witness was not observed')
    ds_row = next(item for item in rows if item['name'] == 'live-restored-ds-provider')
    oracle_require(ds_row['final_data_segment'] == 0x6300,
                   'PUSH DS/POP DS did not return the provider-updated saved word')

    mutations = []
    by_name = {case['name']: case for case in caseset}
    witnesses = [
        (1, 'vector-provider-after-frame-push'),
        (2, 'initial-if-tf-cleared-during-int'),
        (3, 'live-restored-ds-provider'),
        (4, 'changed-interrupt-iret-frame'),
        (5, 'interrupt-frame-overwrites-ivt'),
        (6, 'unbound-vector-offset'),
    ]
    for number, name in witnesses:
        mutant = Native(directory, number)
        try:
            compare(mutant, by_name[name])
        except Mismatch as error:
            mutations.append(dict(mutation=number, case=name,
                                  completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'PC-speaker INT 60 mutation {number} survived')
        gc.collect()

    oracle_require(before == input_hashes(),
                   'Inputs changed during bounded PC-speaker INT 60 campaign')
    write_json(REPORT, dict(image='pcspeaker', image_sha256=sha(DRIVER_IMAGE),
        case_count=len(rows), comparisons=len(rows), cases=rows,
        mutation_count=len(mutations), mutations=mutations,
        translated_code_bytes=PARENT_END - ENTRY,
        native_code_ranges=[[ENTRY, PARENT_END]],
        executed_instruction_addresses=sorted(sites),
        child_instruction_addresses=sorted(child_sites),
        branch_edges=sorted(edges), dynamic_call_targets=sorted(call_targets),
        total_bus_events=event_count,
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_tree_mib=640, original_instruction_limit=MAX_STEPS,
                    native_callback_budget=MAX_EVENTS,
                    callback_budget_exit=CALLBACK_BUDGET_EXIT,
                    callback_error_exit=CALLBACK_ERROR_EXIT),
        input_hashes=before,
        domain='Declared INT 60 FLAGS/CS/IP frame and IVT vector model, composed with '
               'the pinned 0182 PC-speaker dispatcher and translated LoadEffect/Stop '
               'children. Tick and other child targets stop before body execution; '
               'Unicorn interrupt hooks supply the architecture boundary, not CPU '
               'microcode/timing. Covers exact binding, live frame/vector/register '
               'providers, wrap and VGA stack cases.'))
    print(f'PASS PC-speaker INT 60 transport: {len(rows)} fixtures, '
          f'{PARENT_END - ENTRY} dispatcher bytes/{len(sites)} sites/{len(edges)} edges, '
          f'{len(child_sites)} child sites, {event_count} bus events, '
          f'{len(mutations)} completed mutations', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected PC-speaker INT 60 arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='pcspeaker-interrupt-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
