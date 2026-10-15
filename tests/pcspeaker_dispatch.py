"""Bounded original-versus-C checks for the PC-speaker INT60 dispatcher."""
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
CF, AF, IF = 0x0001, 0x0010, 0x0200
LOGIC_FLAGS = ALL_FLAGS & ~AF
MUL_FLAGS = 0x0801
IRET_FLAGS = 0x7FD5
ENTRY, IRET, CALL, LOAD_EFFECT, TICK, STOP = 0x0182, 0x01A0, 0x0196, 0x01B0, 0x01D4, 0x024F
PARENT_END, LOAD_END, STOP_END = 0x01B0, 0x01D4, 0x0255
MAX_INSTRUCTIONS, MAX_BUS_EVENTS = 512, 1024
CALLBACK_BUDGET_EXIT, CALLBACK_ERROR_EXIT = 86, 87
IMAGE, IMAGE_META = sound_images()['pcspeaker']
PINNED_IMAGE_SHA256 = 'bdc1da6ea085bd247ab3060dfc78f522f7b447dcffe7235a3e19bf9938731287'
REPORT = BUILD / 'pcspeaker-dispatch-differential.json'
REG_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
             'cs', 'ds', 'es', 'ss', 'ip', 'flags')
REG_IDS = {n: getattr(x, 'UC_X86_REG_' + n.upper()) for n in REG_NAMES if n != 'flags'}
REG_IDS['flags'] = x.UC_X86_REG_EFLAGS
MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)
PARENT_INS, CHILD_INS = {}, {}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
for _ins in MD.disasm(IMAGE[ENTRY:PARENT_END], ENTRY):
    PARENT_INS[_ins.address] = _ins
for _start, _end in ((LOAD_EFFECT, LOAD_END), (STOP, STOP_END)):
    for _ins in MD.disasm(IMAGE[_start:_end], _start):
        CHILD_INS[_ins.address] = _ins
INS = PARENT_INS | CHILD_INS
PARENT_JUMPS = {pc: ins for pc, ins in PARENT_INS.items()
                if ins.group(capstone.CS_GRP_JUMP)}
EXPECTED_PARENT_EDGES = set()
for _pc, _ins in PARENT_JUMPS.items():
    EXPECTED_PARENT_EDGES.add((_pc, _ins.operands[0].imm & 0xFFFF))
    if _ins.mnemonic != 'jmp':
        EXPECTED_PARENT_EDGES.add((_pc, _ins.address + _ins.size))


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in REG_NAMES]


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'base_value', 'count', 'argument', 'source_cursor',
                 'output_cursor', 'data_segment', 'driver_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'base_value', 'count', 'argument', 'source_cursor',
                 'output_cursor', 'data_segment', 'driver_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation', 'status')]


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    """An original execution exceeded or escaped the declared bounded domain."""


class Mismatch(AssertionError):
    """Only a completed native comparison earns mutation evidence."""


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


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def flags_after(instruction, previous_mask):
    mnemonic = instruction.mnemonic.lower()
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


def specs():
    rows = []
    for command in range(256):
        # The recognized LoadEffect service uses a valid selector; all other
        # commands retain a byte-valued low accumulator for raw read/write paths.
        low = 3 if command == 3 else ((command * 37 + 0xA5) & 0xFF)
        rows.append(dict(name=f'ah-{command:02x}', command=command, low=low,
                         seed=0xA600 + command))
    rows += [
        # These are the recovered main INT60 producer values, not just
        # arbitrary effect IDs in the helper's wider byte domain.
        dict(name='main-producer-ax-0302', command=3, low=0x02, seed=0xC010),
        dict(name='main-producer-ax-030c', command=3, low=0x0C, seed=0xC011),
        dict(name='main-producer-ax-0313', command=3, low=0x13, seed=0xC012),
        dict(name='table-remaps-tick-to-effect', command=0, low=2, seed=0xC001,
             table_target=LOAD_EFFECT),
        dict(name='table-remaps-tick-to-stop', command=0, low=0xD3, seed=0xC002,
             table_target=STOP),
        dict(name='table-remaps-tick-to-unknown', command=0, low=0x62, seed=0xC003,
             table_target=0x3456),
        dict(name='live-table-provider-to-stop', command=0, low=0xB4, seed=0xC004,
             table_provider_target=STOP),
        dict(name='changed-child-near-return-provider', command=3, low=2, seed=0xC005,
             return_provider_target=0x3456),
        dict(name='live-temporary-ds-provider', command=3, low=2, seed=0xC01A,
             temporary_ds=0x6300),
        dict(name='live-saved-ds-provider', command=0x20, low=0x6A, seed=0xC006,
             stack_provider=('ds', 0x6300)),
        dict(name='live-saved-bx-provider', command=0x20, low=0x6B, seed=0xC007,
             stack_provider=('bx', 0x4B4B)),
        dict(name='live-saved-cx-provider', command=0x20, low=0x6C, seed=0xC014,
             stack_provider=('cx', 0x5C5C)),
        dict(name='live-saved-dx-provider', command=0x20, low=0x6D, seed=0xC015,
             stack_provider=('dx', 0x6D6D)),
        dict(name='live-saved-si-provider', command=0x20, low=0x6E, seed=0xC016,
             stack_provider=('si', 0x7E7E)),
        dict(name='live-saved-di-provider', command=0x20, low=0x6F, seed=0xC017,
             stack_provider=('di', 0x8F8F)),
        # PUSH CS writes 01B0 at SS:0024, the command-3 table operand. CALL
        # must read that word before it pushes its own 019A return address.
        dict(name='call-operand-is-push-cs-alias', command=3, low=1, seed=0xC008,
             cs=0x01B0, ds=0x01B0, ss=0x01B0, sp=0x0032,
             frame_ip=0x5678, frame_cs=0x2345, frame_flags=0xFAD7),
        dict(name='stack-offset-wrap', command=0x20, low=0x75, seed=0xC009,
             sp=0x0000, frame_flags=0xFFFF),
        dict(name='physical-word-wrap', command=0x20, low=0x76, seed=0xC00A,
             ss=0xFFFF, sp=0x000F, frame_flags=0xFFFF),
        dict(name='physical-high-offset-stack-word', command=0x20, low=0x7D,
             seed=0xC018, ss=0xFFFF, sp=0x0001, frame_flags=0xFAD7),
        dict(name='driver-data-stack-segment-alias', command=0x20, low=0x77,
             seed=0xC00B, ss=0x0842, sp=0x0200, frame_flags=0xBFFF),
        dict(name='vga-interrupt-stack', command=0x20, low=0x78, seed=0xC00C,
             ss=0xA000, sp=0x4000, frame_flags=0xFFFF, vga=True),
        dict(name='iret-fixed-flags', command=0x20, low=0x79, seed=0xC00D,
             frame_flags=0xFFFF),
        dict(name='live-iret-frame-provider', command=0xA0, low=0x78,
             seed=0xC019, cs=0x0842, ss=0x0842, sp=0x0080,
             iret_provider=(0x5678, 0x6543, 0xFFFF)),
        dict(name='raw-read-threshold', command=0x11, low=0x7A, seed=0xC00E,
             flags=0x0002),
        dict(name='raw-write-threshold', command=0x20, low=0x7B, seed=0xC00F,
             flags=0x0202),
        dict(name='raw-write-direction-flag', command=0x20, low=0x7C, seed=0xC013,
             flags=0x0402),
    ]
    return rows


def setup(case):
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    cs = case.get('cs', 0x0842)
    image_start = physical(cs, 0)
    oracle_require(image_start + len(IMAGE) <= SIZE,
                   case['name'] + ': fixture code image crosses physical boundary')
    memory[image_start:image_start + len(IMAGE)] = IMAGE
    table_target = case.get('table_target')
    if table_target is not None:
        put16(memory, cs, 0x001E + 2 * case['command'], table_target)

    if 'temporary_ds' in case:
        put16(memory, case['temporary_ds'], 0x001E + 2 * case['command'], STOP)
        put8(memory, case['temporary_ds'], 1, 0xA5)
        put8(memory, cs, 1, 0x5A)

    values = {name: rng.randrange(0x10000) for name in REG_NAMES}
    values.update(cs=cs, ds=case.get('ds', 0x5100), ss=case.get('ss', 0x7000),
                  sp=case.get('sp', 0x8200), ip=ENTRY,
                  ax=(case['command'] << 8) | case['low'],
                  # TF would asynchronously enter INT 1 after an instruction;
                  # this bounded dispatcher contract has no debug handler.
                  flags=case.get('flags', (2 | rng.randrange(0x10000)) & ~0x0100))
    frame_ip = case.get('frame_ip', 0x4567)
    frame_cs = case.get('frame_cs', 0x2345)
    frame_flags = case.get('frame_flags', 0x0AD7)
    put16(memory, values['ss'], values['sp'], frame_ip)
    put16(memory, values['ss'], values['sp'] + 2, frame_cs)
    put16(memory, values['ss'], values['sp'] + 4, frame_flags)

    device = None
    if case.get('vga'):
        device = MinimapVga(case['seed'], read_map=0)
        # Give interrupt-frame reads a stable read-mode-0 map and make stack
        # pushes land on every plane, so later POP/IRET reads see those stores.
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[4] = device.gc[5] = 0
        device.gc[8] = 0xFF
        for delta, value in ((0, frame_ip), (2, frame_cs), (4, frame_flags)):
            for byte_index, byte in enumerate((value & 0xFF, value >> 8)):
                address = physical(values['ss'], values['sp'] + delta + byte_index)
                offset = address - VGA_BASE
                device.planes[0][offset] = byte
                memory[address] = byte
    return memory, values, device


class Access:
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

    def provider(self, kind, address):
        if kind == 'read' and 'temporary_ds' in self.case and 'temporary-ds' not in self.used:
            slot = (self.regs['sp'] - 14) & 0xFFFF
            if address == physical(self.regs['ss'], slot):
                self.modify_word(self.regs['ss'], slot, self.case['temporary_ds'])
                self.used.add('temporary-ds')

        if kind == 'read' and 'table_provider_target' in self.case and 'table' not in self.used:
            table = physical(self.regs['cs'], 0x001E + 2 * self.case['command'])
            if address == table:
                self.modify_word(self.regs['cs'],
                                 0x001E + 2 * self.case['command'],
                                 self.case['table_provider_target'])
                self.used.add('table')

        if kind == 'write' and 'return_provider_target' in self.case and 'return' not in self.used:
            # LoadEffect's first live DS write happens after CALL has pushed
            # its near return word. Change that word before the child RET reads it.
            active = physical(self.regs['cs'], 0x0001)
            if address == active:
                return_offset = (self.regs['sp'] - 14) & 0xFFFF
                self.modify_word(self.regs['ss'], return_offset,
                                 self.case['return_provider_target'])
                self.used.add('return')

        if kind == 'write' and 'stack_provider' in self.case and 'stack' not in self.used:
            # The seventh push is PUSH CS at S-14; it can update saved words
            # below/above that live frame before the epilogue pops them.
            push_cs = physical(self.regs['ss'], self.regs['sp'] - 14)
            if address == push_cs:
                name, value = self.case['stack_provider']
                slot = {'ds': -12, 'di': -10, 'si': -8, 'dx': -6,
                        'cx': -4, 'bx': -2}[name]
                self.modify_word(self.regs['ss'], self.regs['sp'] + slot, value)
                self.used.add('stack')

        if kind == 'write' and 'iret_provider' in self.case and 'iret' not in self.used:
            # Raw command A0 writes CS:0080, which aliases the IRET frame at
            # SS:SP in this fixture. Replace all three live frame words before
            # the instruction's own byte store and subsequent IRET reads.
            raw_offset = self.case['command'] - 0x20
            if address == physical(self.regs['cs'], raw_offset):
                ip, cs, flags = self.case['iret_provider']
                self.modify_word(self.regs['ss'], self.regs['sp'], ip)
                self.modify_word(self.regs['ss'], self.regs['sp'] + 2, cs)
                self.modify_word(self.regs['ss'], self.regs['sp'] + 4, flags)
                self.used.add('iret')

    def access(self, kind, address, flags, mask, value=None):
        if len(self.events) >= MAX_BUS_EVENTS:
            raise OracleFailure('PC-speaker dispatch bus-event budget exhausted')
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


def original(case, memory, regs, device, core):
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    cpu.mem_write(0, bytes(memory))
    cpu.mem_write(SIZE, bytes(memory))
    for name in REG_NAMES:
        cpu.reg_write(REG_IDS[name], regs[name])
    access = Access(case, memory, regs, device)

    def mirror(address, value):
        cpu.mem_write(address, bytes((value,)))
        cpu.mem_write(address + SIZE, bytes((value,)))

    access.mirror = mirror
    current_flags, current_mask = regs['flags'], ALL_FLAGS
    previous = None
    stopped = False
    status = None
    continuation = None
    sites, edges, call_targets = set(), set(), []
    failure = None
    steps = 0

    def stop(u, result_status, target, reason):
        nonlocal stopped, status, continuation
        stopped, status, continuation = True, result_status, target & 0xFFFF
        u.emu_stop()

    def fail(u, reason):
        nonlocal failure
        failure = reason
        u.emu_stop()

    def code(u, _address, _size, _):
        nonlocal previous, current_flags, current_mask, steps
        steps += 1
        if steps > MAX_INSTRUCTIONS:
            fail(u, 'original instruction-hook budget exhausted')
            return
        cs = u.reg_read(REG_IDS['cs']) & 0xFFFF
        off = u.reg_read(REG_IDS['ip']) & 0xFFFF
        if previous is not None:
            prev_off, prev_ins = previous
            if prev_ins.group(capstone.CS_GRP_JUMP):
                edges.add((prev_off, off))
            current_mask = flags_after(prev_ins, current_mask)
            if prev_ins.address == CALL:
                call_targets.append(off)
                if off not in (LOAD_EFFECT, STOP):
                    stop(u, 1, off, 'untranslated child target')
                    return
            if prev_ins.mnemonic == 'ret' and off != 0x019A:
                stop(u, 2, off, 'changed child return target')
                return
            if prev_ins.mnemonic == 'iret':
                stop(u, 0, off, 'completed IRET')
                return

        if core and cs == regs['cs'] and off == IRET:
            stop(u, 0, IRET, 'core stop before IRET')
            return

        ins = PARENT_INS.get(off) if cs == regs['cs'] else None
        if ins is None:
            ins = CHILD_INS.get(off) if cs == regs['cs'] else None
        if ins is None:
            fail(u, f'original escaped declared code at {cs:04x}:{off:04x}')
            return
        linear = (cs << 4) + off
        actual = bytes(u.mem_read(linear, ins.size))
        expected = IMAGE[off:off + ins.size]
        if actual != expected:
            fail(u, f'original instruction bytes changed at {cs:04x}:{off:04x}: {actual.hex()}/{expected.hex()}')
            return
        current_flags = u.reg_read(REG_IDS['flags']) & 0xFFFF
        sites.add(off)
        previous = (off, ins)

    def read(_u, _kind, address, size, _value, _):
        for delta in range(size):
            access.access('read', address + delta, current_flags, current_mask)

    def write(_u, _kind, address, size, value, _):
        for delta in range(size):
            access.access('write', address + delta, current_flags, current_mask,
                          (value >> (8 * delta)) & 0xFF)

    def interrupt(u, number, _):
        # A caller-supplied IRET frame can restore TF. Unicorn may report its
        # single-step trap before the next code hook; accept it only after the
        # dispatcher IRET has actually executed.
        if (number == 1 and not core and previous is not None and
                previous[1].mnemonic == 'iret'):
            stop(u, 0, u.reg_read(REG_IDS['ip']), 'post-IRET TF boundary')
        else:
            fail(u, f'unexpected original interrupt {number:02x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_INTR, interrupt)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    try:
        cpu.emu_start(physical(regs['cs'], ENTRY), 0, count=MAX_INSTRUCTIONS)
    except UcError as error:
        raise OracleFailure(case['name'] + ': bounded original execution failed') from error
    oracle_require(stopped and failure is None,
                   case['name'] + ': ' + (failure or 'original did not reach declared seam'))
    state = {name: cpu.reg_read(REG_IDS[name]) & 0xFFFF for name in REG_NAMES}
    if status == 0 and not core:
        # IRET restores the caller-supplied frame and normalizes fixed/reserved
        # bits according to this dispatcher adapter's declared real-mode model.
        frame_flags = get16(memory, regs['ss'], regs['sp'] + 4)
        expected_flags = (frame_flags & IRET_FLAGS) | 2
        oracle_require((state['flags'] & ALL_FLAGS) == (expected_flags & ALL_FLAGS),
                       case['name'] + ': original IRET flags differ from frame contract')
        current_mask = ALL_FLAGS
    return dict(memory=bytes(memory), regs=state, device=device, events=access.events,
                used=access.used, status=status, continuation=continuation,
                iret_frame_flags=(get16(memory, regs['ss'], regs['sp'] + 4)
                                  if status == 0 and not core else None),
                sites=sites, edges=edges, call_targets=call_targets,
                flag_mask=current_mask, steps=steps)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'pcspeaker-dispatch-{mutation}.dll',
                     mutation, 'pcspeaker_dispatch')
        self.lib = ct.CDLL(str(path))
        self.lib.lmn_pc_speaker_dispatch_core.argtypes = [
            MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.lib.lmn_pc_speaker_dispatch_core.restype = Result
        self.lib.lmn_pc_speaker_dispatch_adapter.argtypes = [
            MEM, ct.POINTER(Regs), ct.POINTER(Bus)]
        self.lib.lmn_pc_speaker_dispatch_adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, core, null_bus=False):
        access = Access(case, memory, regs, device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, ALL_FLAGS)
            except BaseException as error:
                worker_fail(CALLBACK_BUDGET_EXIT if 'budget exhausted' in str(error)
                            else CALLBACK_ERROR_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                worker_fail(CALLBACK_BUDGET_EXIT if 'budget exhausted' in str(error)
                            else CALLBACK_ERROR_EXIT, error)

        def out(_context, port, value, flags):
            worker_fail(CALLBACK_ERROR_EXIT,
                        f'unexpected dispatcher port output {port:04x}={value:04x} flags={flags:04x}')

        callbacks = READ(read), WRITE(write), OUT(out)
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        bus_ptr = None if null_bus else ct.byref(bus)
        if core:
            call = Call(regs['ax'], regs['bx'], regs['cx'], regs['dx'],
                        regs['si'], regs['di'], regs['ds'], regs['cs'],
                        regs['ss'], regs['sp'], regs['flags'])
            result = self.lib.lmn_pc_speaker_dispatch_core(
                ram, ct.byref(call), bus_ptr)
            state.ax, state.bx, state.cx, state.dx = (
                result.value, result.base_value, result.count, result.argument)
            state.si, state.di = result.source_cursor, result.output_cursor
            state.ds, state.cs, state.ss, state.sp = (
                result.data_segment, result.driver_segment,
                result.stack_segment, result.stack_offset)
            state.flags, state.ip = result.flags, result.continuation
            status = result.status
        else:
            status = self.lib.lmn_pc_speaker_dispatch_adapter(
                ram, ct.byref(state), bus_ptr)
        return dict(memory=bytes(memory), regs={name: getattr(state, name)
                                                for name in REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status)


def compare(native, case, core, null_bus=False):
    memory, regs, device = setup(case)
    expected = original(case, bytearray(memory), dict(regs), copy.deepcopy(device), core)
    actual = native.run(case, bytearray(memory), dict(regs), copy.deepcopy(device), core,
                        null_bus)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    if actual['memory'] != expected['memory']:
        where = next(index for index, (a, b) in enumerate(
            zip(actual['memory'], expected['memory'])) if a != b)
        raise Mismatch(f'{label}: memory {where:05x} {actual["memory"][where]:02x}/'
                       f'{expected["memory"][where]:02x}')
    for name in REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04x}/'
                f'{expected["regs"][name]:04x} under {mask:04x}')
    if not null_bus:
        require(len(actual['events']) == len(expected['events']),
                label + ': ordered bus event count differs')
        for index, (got, ref) in enumerate(zip(actual['events'], expected['events'])):
            require(got[:3] == ref[:3],
                    f'{label}: event {index} payload {got[:3]!r}/{ref[:3]!r}')
            require(((got[3] ^ ref[3]) & ref[4]) == 0,
                    f'{label}: event {index} flags {got[3]:04x}/{ref[3]:04x} '
                    f'under {ref[4]:04x}')
        require(actual['used'] == expected['used'], label + ': provider transition differs')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA planes/latches/registers differ')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(got_trace == ref_trace, label + ': VGA trace differs')
    if 'temporary_ds' in case:
        oracle_require('temporary-ds' in expected['used'] and expected['status'] == 0,
                       label + ': temporary DS fixture did not return through Stop')
        oracle_require(expected['regs']['ax'] == 0xF300 and
                       expected['memory'][physical(case['temporary_ds'], 1)] == 0 and
                       expected['memory'][physical(regs['cs'], 1)] == 0x5A,
                       label + ': temporary DS did not own the Stop write')
    if 'stack_provider' in case:
        name, value = case['stack_provider']
        oracle_require('stack' in expected['used'] and expected['regs'][name] == value,
                       label + ': saved register provider was not exercised')
    if 'iret_provider' in case:
        oracle_require('iret' in expected['used'], label + ': IRET provider was not exercised')
    if not core and expected['status'] == 0:
        original_frame_flags = expected['iret_frame_flags']
        fixed = (original_frame_flags & IRET_FLAGS) | 2
        require(actual['regs']['flags'] == fixed,
                label + f': fixed IRET FLAGS {actual["regs"]["flags"]:04x}/{fixed:04x}')
    return expected


def input_hashes():
    paths = [
        'assets/main.dat', 'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h', 'c/regs.h',
        'c/special_blit.h', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/sound-oracle.json',
        'metadata/toolchain-lock.json',
        'src/sound/pcspeaker.asm', 'tests/minimap_vga.py',
        'tests/pcspeaker_dispatch.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/difftest.py',
        'tools/resources.py', 'tools/unpack.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(len(IMAGE) == 758 and sha(IMAGE) == PINNED_IMAGE_SHA256,
                   'PC-speaker component image identity changed')
    oracle_require(IMAGE_META['section_index'] == 5 and
                   IMAGE_META['entry_offset'] == ENTRY,
                   'PC-speaker section/entry metadata changed')
    oracle_require(len(PARENT_INS) == 29 and len(CHILD_INS) == 18,
                   'PC-speaker dispatcher/child instruction inventory changed')
    oracle_require(len(EXPECTED_PARENT_EDGES) == 6,
                   'PC-speaker dispatcher branch-edge inventory changed')

    baseline = Native(directory)
    rows, parent_sites, child_sites, edges, call_targets = [], set(), set(), set(), set()
    event_count = 0
    cases = specs()
    for case in cases:
        boundary_results = []
        for core in (True, False):
            result = compare(baseline, case, core)
            boundary_results.append(result)
            parent_sites.update(site for site in result['sites'] if site in PARENT_INS)
            child_sites.update(site for site in result['sites'] if site in CHILD_INS)
            edges.update(result['edges'])
            call_targets.update(result['call_targets'])
            event_count += len(result['events'])
        rows.append(dict(name=case['name'], command=case['command'],
                         boundaries=['core-before-iret', 'register-adapter'],
                         table_target=case.get('table_target'),
                         table_provider_target=case.get('table_provider_target'),
                         return_provider_target=case.get('return_provider_target'),
                         stack_provider=case.get('stack_provider'),
                         temporary_ds=case.get('temporary_ds'), vga=case.get('vga', False),
                         iret_provider=case.get('iret_provider'),
                         statuses=[result['status'] for result in boundary_results],
                         continuations=[result['continuation'] for result in boundary_results],
                         providers=[sorted(result['used']) for result in boundary_results]))
        gc.collect()

    oracle_require(parent_sites == set(PARENT_INS),
                   f'dispatch instruction coverage differs: {parent_sites ^ set(PARENT_INS)}')
    oracle_require(edges == EXPECTED_PARENT_EDGES,
                   f'dispatch branch edges differ: {edges ^ EXPECTED_PARENT_EDGES}')
    oracle_require({TICK, 0, STOP, LOAD_EFFECT}.issubset(call_targets),
                   f'tick/effect/stop/unknown CALL seams missing: {call_targets}')
    return_provider = next(item for item in rows
                           if item['name'] == 'changed-child-near-return-provider')
    oracle_require(return_provider['statuses'] == [2, 2] and
                   return_provider['continuations'] == [0x3456, 0x3456] and
                   all('return' in used for used in return_provider['providers']) and
                   return_provider['return_provider_target'] == 0x3456,
                   'changed near-return fixture did not stop at its live target')
    iret_provider = next(item for item in rows
                         if item['name'] == 'live-iret-frame-provider')
    oracle_require(iret_provider['statuses'] == [0, 0] and
                   all('iret' in used for used in iret_provider['providers']),
                   'live IRET frame provider was not observed')

    # A few null-bus repetitions prove the direct-memory path independently of
    # callback ordering; VGA needs its explicit device bus and is not repeated.
    for name in ('ah-00', 'ah-03', 'ah-20'):
        case = next(item for item in cases if item['name'] == name)
        for core in (True, False):
            compare(baseline, case, core, null_bus=True)

    witnesses = [
        (1, 'raw-read-threshold', True),
        (2, 'live-saved-ds-provider', True),
        (3, 'ah-05', True),
        (4, 'changed-child-near-return-provider', True),
        (5, 'call-operand-is-push-cs-alias', True),
        (6, 'live-saved-bx-provider', True),
        (7, 'raw-write-threshold', True),
        (8, 'live-temporary-ds-provider', True),
    ]
    mutations = []
    by_name = {case['name']: case for case in cases}
    for number, name, core in witnesses:
        mutant = Native(directory, number)
        case = by_name[name]
        try:
            compare(mutant, case, core)
        except Mismatch as error:
            mutations.append(dict(mutation=number, case=name, completed=True,
                                  mismatch=str(error)))
        else:
            raise OracleFailure(f'PC-speaker dispatcher mutation {number} survived')
        gc.collect()

    oracle_require(before == input_hashes(),
                   'Inputs changed during bounded PC-speaker dispatcher campaign')
    write_json(REPORT, dict(image='pcspeaker', image_sha256=sha(IMAGE),
        case_count=len(rows), comparisons=len(rows) * 2, cases=rows,
        mutation_count=len(mutations), mutations=mutations,
        translated_code_bytes=PARENT_END - ENTRY,
        native_code_ranges=[[ENTRY, PARENT_END]],
        executed_instruction_addresses=sorted(parent_sites),
        child_instruction_addresses=sorted(child_sites),
        branch_edges=sorted(edges), dynamic_call_targets=sorted(call_targets),
        total_bus_events=event_count,
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_tree_mib=640, original_instruction_hook_limit=MAX_INSTRUCTIONS,
                    native_callback_budget=MAX_BUS_EVENTS,
                    callback_budget_exit=CALLBACK_BUDGET_EXIT,
                    callback_error_exit=CALLBACK_ERROR_EXIT),
        input_hashes=before,
        domain='PC-speaker interrupt dispatcher 0182..01AF at core-before-IRET and adapter boundaries; '
               'all AH byte values; native LoadEffect/Stop composition; tick and other CALL targets stop '
               'before child execution; live table, return, saved-register, IRET, physical-memory and VGA stack aliases; '
               'no playback/IRQ timing or unresolved-child behavior claim'))
    print(f'PASS PC-speaker dispatcher: {len(rows)} fixtures at core+adapter, '
          f'{PARENT_END - ENTRY} bytes/{len(parent_sites)} dispatcher sites/'
          f'{len(edges)} edges, {len(child_sites)} child sites, {event_count} bus events, '
          f'{len(mutations)} completed mutations', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected PC-speaker dispatcher arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='pcspeaker-dispatch-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()
