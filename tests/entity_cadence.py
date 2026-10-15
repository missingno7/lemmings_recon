"""Bounded differential checks for the four entity cadence JMP entries."""
import copy
import ctypes as ct
import gc
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
from dat_io import REG_NAMES
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as ux


IMAGE, ORACLE = unpack(ASSET.read_bytes())
LOADED = relocated(IMAGE, ORACLE['relocations'], 0x1010)
LOAD = 0x1010
DATA_SEGMENT = 0x5200
SIZE, MASK = 1 << 20, (1 << 20) - 1
TABLE, COMPLETION_COUNTER = 0x547C, 0x0046
CADENCE_SPANS = ((0x22DF, 0x22F5), (0x22F5, 0x2326),
                 (0x2326, 0x2340), (0x2340, 0x2350))
SHARED_SPANS = ((0x20E2, 0x20E9),)
PIXEL_SPAN = (0x6141, 0x6170)
BOUNDARY, PIXEL_RETURN = 0x1FEB, 0x2316
ALL_FLAGS, LOGIC_FLAGS = 0x0FD7, 0x0FC7
CF, PF, AF, ZF, SF, TF, IF, DF, OF = (
    0x0001, 0x0004, 0x0010, 0x0040, 0x0080, 0x0100, 0x0200, 0x0400, 0x0800)
ARITH = CF | PF | AF | ZF | SF | OF
MAX_INSTRUCTIONS, MAX_EVENTS = 256, 512
WORKER_SECONDS, PROCESS_MIB = 180, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-cadence-differential.json'

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


def disassemble(spans):
    result = {}
    for start, end in spans:
        for ins in MD.disasm(IMAGE[start:end], start):
            if ins.address in result:
                raise RuntimeError(f'duplicate instruction at {ins.address:04X}')
            result[ins.address] = ins
    return result


OWN_INS = disassemble(CADENCE_SPANS)
SHARED_INS = disassemble(SHARED_SPANS)
PIXEL_INS = disassemble((PIXEL_SPAN,))
OWN_SITES = set(OWN_INS)
OWN_BRANCHES = set()
OWN_EDGES = set()
for _address, _ins in OWN_INS.items():
    if not _ins.group(capstone.CS_GRP_JUMP):
        continue
    OWN_BRANCHES.add(_address)
    if _ins.mnemonic.lower() != 'jmp':
        OWN_EDGES.add((_address, (_address + _ins.size) & 0xFFFF))
    if _ins.operands and _ins.operands[-1].type == capstone.x86.X86_OP_IMM:
        OWN_EDGES.add((_address, _ins.operands[-1].imm & 0xFFFF))


class OracleFailure(AssertionError):
    """The pinned original or its constructed inputs failed to complete."""


class Mismatch(AssertionError):
    """A completed native result differs from the completed original."""


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


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


def flag_mask_after(ins, mask):
    mnemonic = ins.mnemonic.lower()
    if mnemonic == 'inc':
        return ALL_FLAGS
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return ALL_FLAGS
    if mnemonic in ('and', 'or', 'xor', 'test', 'shr', 'shl', 'sar', 'sal'):
        return LOGIC_FLAGS
    if mnemonic == 'mul':
        return (mask & ~ARITH) | CF | OF
    return mask


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('entry', 'value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags')]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags', 'continuation', 'status')]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32,
                     ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class RasterBus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


ENTRY_IDS = {'state-0001': 0, 'state-1000': 1,
             'state-2000': 2, 'state-4000': 3}
REG_IDS = {name: getattr(ux, 'UC_X86_REG_' + name.upper()) for name in REG_NAMES}
REG_IDS.update(ip=ux.UC_X86_REG_IP, flags=ux.UC_X86_REG_EFLAGS)
RESULT_MAP = {
    'ax': 'value', 'bx': 'map_cursor', 'cx': 'count', 'dx': 'auxiliary_value',
    'si': 'record_cursor', 'di': 'object_cursor', 'bp': 'candidate_y',
    'cs': 'code_segment', 'ds': 'data_segment', 'es': 'extra_segment',
    'ss': 'stack_segment', 'sp': 'stack_offset', 'flags': 'flags',
}


def calc_pixel_offset(x_value, y_value):
    row = (y_value - 0x10) & 0xFFFF
    product = (row * 0x00D0) & 0xFFFF
    return (product + (x_value >> 3) + 0x4A40) & 0xFFFF


def cases():
    """Focused witnesses cover all four transforms, branch edges and aliases."""
    return [
        dict(name='state0001-mod16-completes', entry='state-0001', animation=0x0F),
        dict(name='state0001-retains-bit3', entry='state-0001', animation=0x07),
        dict(name='state0001-mod16-continues', entry='state-0001', animation=0x00),
        dict(name='state1000-mod16-completes', entry='state-1000', animation=0x0F),
        dict(name='state1000-empty-pixel-adds-live-delta', entry='state-1000',
             animation=0x00, delta=0x01, pixel=0x00),
        dict(name='state1000-occupied-pixel-skips-add', entry='state-1000',
             animation=0x00, delta=0x01, pixel=0x80),
        dict(name='state1000-negative-delta-df', entry='state-1000',
             animation=0x01, delta=0xFF, pixel=0x00, flags=0x0647),
        dict(name='state1000-scale-eight-wrap-x', entry='state-1000',
             animation=0x02, delta=0x7F, x=0xFFFA, pixel=0x00),
        dict(name='state1000-live-return-provider-alias', entry='state-1000',
             animation=0x00, delta=0x01, ds=0x5100, ss=0x5100,
             sp=TABLE + 4, provider='pixel-return', changed_target=0x3456),
        dict(name='state1000-live-pop-provider-alias', entry='state-1000',
             animation=0x00, delta=0x01, ds=0x5100, ss=0x5100,
             sp=TABLE + 2, provider='saved-ax', provider_word=0x0003,
             pixel=0x00),
        dict(name='state1000-stack-offset-physical-wrap', entry='state-1000',
             animation=0x03, delta=0xFE, ss=0xFFFF, sp=0x0001,
             pixel=0x00, flags=0x0447),
        dict(name='state1000-record-offset-wrap', entry='state-1000',
             animation=0x04, delta=0x80, si=0xFFF0, pixel=0x00),
        dict(name='state1000-vga-aperture-sample', entry='state-1000',
             animation=0x05, delta=0x01, pixel=0x80, vga=True),
        dict(name='state2000-mod8-completes-and-counter', entry='state-2000',
             animation=0x07, completion=0x7F, flags=0x0647),
        dict(name='state2000-mod8-continues', entry='state-2000', animation=0x00),
        dict(name='state2000-counter-physical-wrap', entry='state-2000',
             animation=0x07, completion=0xFF, ds=0xFFFF),
        dict(name='state4000-equality-mark', entry='state-4000', animation=0x0D),
        dict(name='state4000-below-threshold', entry='state-4000', animation=0x0B),
        dict(name='state4000-above-threshold', entry='state-4000', animation=0x0E),
        dict(name='state4000-fresh-read-provider', entry='state-4000',
             animation=0x20, provider='increment-reread', provider_byte=0x0E),
        dict(name='state4000-entry-flags-on-rmw', entry='state-4000',
             animation=0x7F, flags=0x0207),
        dict(name='state4000-record-wrap', entry='state-4000',
             animation=0x0D, si=0xFFFA, ds=0xFFFF),
        dict(name='poisoned-registers-and-ram', entry='state-0001',
             animation=0x31, poison=0x6E77, flags=0x0A43),
    ]


def setup(case, seed):
    rng = random.Random(0x22DF + seed * 0x9E3779B1 + case.get('poison', 0))
    memory = bytearray(rng.randbytes(SIZE))
    memory[LOAD << 4:(LOAD << 4) + len(LOADED)] = LOADED
    regs = {name: rng.randrange(0x10000) for name in REG_NAMES}
    regs.update(cs=LOAD, ip={'state-0001': 0x22DF, 'state-1000': 0x22F5,
                            'state-2000': 0x2326, 'state-4000': 0x2340}[case['entry']],
                ds=case.get('ds', DATA_SEGMENT), ss=case.get('ss', 0x5000),
                si=case.get('si', 0x6000), sp=case.get('sp', 0xDFFE))
    flags = case.get('flags', ((rng.randrange(0x10000) & ALL_FLAGS) | 2) & ~TF)
    regs['flags'] = (flags & ALL_FLAGS) | 2
    regs['flags'] &= ~TF

    ds, si = regs['ds'], regs['si']
    put16(memory, ds, si, case.get('x', 0x0200))
    put16(memory, ds, (si + 2) & 0xFFFF, case.get('y', 0x0040))
    put16(memory, ds, (si + 4) & 0xFFFF, rng.randrange(0x10000))
    put16(memory, ds, (si + 6) & 0xFFFF, rng.randrange(0x10000))
    put16(memory, ds, (si + 8) & 0xFFFF, rng.randrange(0x10000))
    put8(memory, ds, (si + 0x23) & 0xFFFF, rng.randrange(0x100))
    put8(memory, ds, (si + 0x24) & 0xFFFF, rng.randrange(0x100))
    put8(memory, ds, (si + 0x26) & 0xFFFF, rng.randrange(0x100))
    put8(memory, ds, (si + 0x27) & 0xFFFF, case.get('delta', 0x01))
    put8(memory, ds, (si + 0x28) & 0xFFFF, case.get('animation', 0))
    put8(memory, ds, (si + 0x29) & 0xFFFF, rng.randrange(0x100))
    put8(memory, ds, COMPLETION_COUNTER, case.get('completion', 0x35))
    table = case.get('table', bytes.fromhex('80 40 20 10 08 04 02 01'))
    for index, value in enumerate(table):
        put8(memory, ds, TABLE + index, value)

    device = None
    if case.get('vga'):
        device = MinimapVga(seed + 0x6141, read_map=0)
        device.seq[2], device.seq[4] = 0x0F, 0x06
        device.gc[0] = device.gc[1] = device.gc[3] = 0
        device.gc[4], device.gc[5], device.gc[6], device.gc[8] = 0, 0, 0x05, 0xFF

    if case['entry'] == 'state-1000' and case['animation'] != 0x0F:
        delta = case.get('delta', 0x01)
        signed_delta = delta - 0x100 if delta & 0x80 else delta
        column = (case.get('x', 0x0200) + 8 * signed_delta) & 0xFFFF
        offset = calc_pixel_offset(column, case.get('y', 0x0040))
        address = VGA_BASE + offset
        value = case.get('pixel', 0)
        if device is not None:
            device.planes[0][offset] = value
        else:
            memory[address] = value

    return memory, regs, device


def provider_plan(case, regs):
    provider = case.get('provider')
    if not provider:
        return None
    if provider in ('pixel-return', 'saved-ax'):
        delta = case.get('delta', 1)
        signed_delta = delta - 0x100 if delta & 0x80 else delta
        column = (get_case_x(case) + 8 * signed_delta) & 0xFFFF
        index = column & 7
        trigger = physical(regs['ds'], TABLE + index)
        if provider == 'pixel-return':
            target = physical(regs['ss'], (regs['sp'] - 4) & 0xFFFF)
            data = int(case.get('changed_target', 0x3456)).to_bytes(2, 'little')
            key = 'pixel-return'
        else:
            target = physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF)
            data = int(case.get('provider_word', 3)).to_bytes(2, 'little')
            key = 'saved-ax'
        return dict(trigger=trigger, target=target, data=data, key=key,
                    phase='read')
    if provider == 'increment-reread':
        target = physical(regs['ds'], (regs['si'] + 0x28) & 0xFFFF)
        return dict(trigger=target, target=target,
                    data=bytes((case.get('provider_byte', 0x0E),)),
                    key=provider, phase='inc-write')
    raise OracleFailure(f'unknown cadence provider {provider!r}')


def get_case_x(case):
    return case.get('x', 0x0200) & 0xFFFF


class Access:
    def __init__(self, case, memory, regs, device, plan, *, defer_write_provider=False):
        self.case, self.memory, self.regs = case, memory, regs
        self.device, self.plan = device, plan
        self.defer_write_provider = defer_write_provider
        self.events, self.used, self.pending = [], set(), []
        self.mirror = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value & 0xFF
        if self.device and VGA_BASE <= address < VGA_END:
            self.device.planes[self.device.gc[4] & 3][address - VGA_BASE] = value & 0xFF
        if self.mirror:
            self.mirror(address, value)

    def apply_provider(self):
        if not self.plan or self.plan['key'] in self.used:
            return
        for offset, value in enumerate(self.plan['data']):
            self.store(self.plan['target'] + offset, value)
        self.used.add(self.plan['key'])

    def access(self, kind, address, flags, flag_mask, value=None):
        address &= MASK
        if len(self.events) >= MAX_EVENTS:
            raise OracleFailure('cadence oracle/native access budget exhausted')
        if kind == 'read':
            value = (self.device.read(self.memory, address, flags)
                     if self.device and VGA_BASE <= address < VGA_END
                     else self.memory[address])
        else:
            value &= 0xFF
            if self.device and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            else:
                self.memory[address] = value
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF,
                            flag_mask & 0xFFFF))
        if self.plan and self.plan['key'] not in self.used:
            if (self.plan['phase'] == 'read' and kind == 'read' and
                    address == self.plan['trigger']):
                self.pending.append(self.plan['key'])
            elif (self.plan['phase'] == 'inc-write' and kind == 'write' and
                  address == self.plan['trigger']):
                if self.defer_write_provider:
                    self.pending.append(self.plan['key'])
                else:
                    self.apply_provider()
        return value & 0xFF

    def apply_pending(self):
        if self.pending:
            self.pending.clear()
            self.apply_provider()


class Original:
    def __init__(self, case, memory, regs, device, plan, *, stop_at=None):
        self.case, self.memory, self.regs = case, memory, regs
        self.device, self.plan = device, plan
        self.access = Access(case, memory, regs, device, plan,
                             defer_write_provider=True)
        self.stop_at = stop_at
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, SIZE * 2)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(SIZE, initial)
        for name in REG_NAMES:
            self.cpu.reg_write(REG_IDS[name], regs[name])
        self.cpu.reg_write(ux.UC_X86_REG_IP, regs['ip'])
        self.cpu.reg_write(ux.UC_X86_REG_EFLAGS, regs['flags'])
        self.access.mirror = self.mirror
        self.previous = None
        self.current_flags, self.current_mask = regs['flags'], ALL_FLAGS
        self.sites, self.shared_sites, self.pixel_sites = set(), set(), set()
        self.edges, self.shared_edges = set(), set()
        self.steps, self.stopped, self.failure = 0, False, None
        self.status, self.continuation = None, None

        self.cpu.hook_add(UC_HOOK_CODE, self.on_code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.on_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.on_write)

    def mirror(self, address, value):
        p = address & MASK
        for target in (address, p, p + SIZE):
            if 0 <= target < SIZE * 2:
                self.cpu.mem_write(target, bytes((value & 0xFF,)))

    def fail(self, message):
        if self.failure is None:
            self.failure = message
        self.cpu.emu_stop()

    def on_read(self, cpu, _kind, address, size, _value, _user):
        try:
            for offset in range(size):
                linear = address + offset
                if not 0 <= linear < SIZE * 2:
                    self.fail('original read outside 2 MiB map')
                    return
                p = linear & MASK
                value = self.access.access('read', p, self.current_flags,
                                           self.current_mask)
                self.mirror(linear, value)
        except BaseException as error:
            self.fail(f'original read callback failed: {type(error).__name__}: {error}')

    def on_write(self, cpu, _kind, address, size, value, _user):
        try:
            for offset in range(size):
                linear = address + offset
                if not 0 <= linear < SIZE * 2:
                    self.fail('original write outside 2 MiB map')
                    return
                p = linear & MASK
                self.access.access('write', p, self.current_flags,
                                   self.current_mask, value >> (8 * offset))
                self.mirror(linear, value >> (8 * offset))
        except BaseException as error:
            self.fail(f'original write callback failed: {type(error).__name__}: {error}')

    def on_code(self, cpu, _address, _size, _user):
        self.steps += 1
        if self.steps > MAX_INSTRUCTIONS:
            self.fail('original cadence instruction budget exhausted')
            return
        cs = cpu.reg_read(ux.UC_X86_REG_CS) & 0xFFFF
        ip = cpu.reg_read(ux.UC_X86_REG_IP) & 0xFFFF
        if self.previous is not None:
            previous = self.previous
            if previous.group(capstone.CS_GRP_JUMP):
                edge = (previous.address, ip)
                if previous.address in OWN_INS:
                    self.edges.add(edge)
                elif previous.address in SHARED_INS:
                    self.shared_edges.add(edge)
            self.current_mask = flag_mask_after(previous, self.current_mask)
            if previous.address == 0x616F and ip != PIXEL_RETURN:
                self.stop(1, ip)
                return
            self.access.apply_pending()

        if cs != LOAD:
            self.fail(f'original escaped code segment at {cs:04X}:{ip:04X}')
            return
        if ip == self.stop_at:
            self.stop(2, ip)
            return
        if ip == BOUNDARY:
            self.stop(0, ip)
            return
        ins = OWN_INS.get(ip) or SHARED_INS.get(ip) or PIXEL_INS.get(ip)
        if ins is None:
            self.fail(f'original escaped declared cadence/child code at {cs:04X}:{ip:04X}')
            return
        if bytes(cpu.mem_read(physical(cs, ip), ins.size)) != LOADED[ip:ip + ins.size]:
            self.fail(f'original code changed at {cs:04X}:{ip:04X}')
            return
        self.current_flags = cpu.reg_read(ux.UC_X86_REG_EFLAGS) & 0xFFFF
        if ip in OWN_INS:
            self.sites.add(ip)
        elif ip in SHARED_INS:
            self.shared_sites.add(ip)
        else:
            self.pixel_sites.add(ip)
        self.previous = ins

    def stop(self, status, continuation):
        self.status, self.continuation = status, continuation & 0xFFFF
        self.stopped = True
        self.cpu.emu_stop()

    def run(self):
        start = physical(self.regs['cs'], self.regs['ip'])
        try:
            self.cpu.emu_start(start, 0, count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise OracleFailure(f'{self.case["name"]}: bounded original failed: {error}') from error
        oracle_require(self.stopped and self.failure is None,
                       f'{self.case["name"]}: {self.failure or "no declared boundary"}')
        state = {name: self.cpu.reg_read(REG_IDS[name]) & 0xFFFF for name in REG_NAMES}
        state['ip'] = self.cpu.reg_read(ux.UC_X86_REG_IP) & 0xFFFF
        state['flags'] = self.cpu.reg_read(ux.UC_X86_REG_EFLAGS) & 0xFFFF
        canonical = bytes(self.memory)
        oracle_require(canonical == bytes(self.cpu.mem_read(0, SIZE)),
                       f'{self.case["name"]}: original canonical RAM mirror diverged')
        oracle_require(len(self.access.events) <= MAX_EVENTS,
                       f'{self.case["name"]}: original bus event budget exhausted')
        if self.plan:
            oracle_require(self.plan['key'] in self.access.used,
                           f'{self.case["name"]}: provider did not fire')
        return dict(memory=canonical, regs=state, events=list(self.access.events),
                    device=self.device, used=set(self.access.used), status=self.status,
                    continuation=self.continuation, sites=set(self.sites),
                    shared_sites=set(self.shared_sites), pixel_sites=set(self.pixel_sites),
                    edges=set(self.edges), shared_edges=set(self.shared_edges),
                    steps=self.steps, flag_mask=self.current_mask)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-cadence-m{mutation}.dll',
                     mutation, 'entity_cadence')
        self.library = ct.CDLL(str(path))
        self.core = self.library.lmn_entity_cadence_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_entity_cadence_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(Regs), ct.c_int, ct.POINTER(RasterBus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, plan, *, core):
        access = Access(case, memory, regs, device, plan)

        def read(_context, _mem, address, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native cadence access callback budget exhausted')
                value = access.access('read', address, flags, ALL_FLAGS)
                access.apply_pending()
                return value
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native cadence read callback failed: {type(error).__name__}: {error}')
                return 0

        def write(_context, _mem, address, value, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    worker_exit(GUARD_EXIT, 'native cadence access callback budget exhausted')
                access.access('write', address, flags, ALL_FLAGS, value)
            except BaseException as error:
                worker_exit(CALLBACK_EXIT,
                            f'native cadence write callback failed: {type(error).__name__}: {error}')

        def unexpected_out(_context, _port, _value, _flags):
            worker_exit(CALLBACK_EXIT, 'cadence path unexpectedly used an output port')

        callbacks = (READ(read), WRITE(write), OUT(unexpected_out))
        bus = RasterBus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**{name: regs[name] for name in REG_NAMES}, flags=regs['flags'])
        entry_id = ENTRY_IDS[case['entry']]
        status = 0
        if core:
            call = Call(entry_id, regs['ax'], regs['bx'], regs['cx'], regs['dx'],
                        regs['si'], regs['di'], regs['bp'], regs['cs'], regs['ds'],
                        regs['es'], regs['ss'], regs['sp'], regs['flags'])
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for name, field in RESULT_MAP.items():
                setattr(state, name, getattr(result, field))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), entry_id, ct.byref(bus))
        return dict(memory=bytes(memory), regs={name: getattr(state, name)
                                               for name in (*REG_NAMES, 'ip', 'flags')},
                    events=list(access.events), device=device,
                    used=set(access.used), status=status,
                    continuation=state.ip)


def compare_case(native, case, seed, core):
    initial_memory, entry_regs, entry_device = setup(case, seed)
    plan = provider_plan(case, entry_regs)
    expected = Original(case, bytearray(initial_memory), dict(entry_regs),
                        copy.deepcopy(entry_device), plan).run()
    actual = native.run(case, bytearray(initial_memory), dict(entry_regs),
                        copy.deepcopy(entry_device), plan, core=core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['continuation'] == expected['continuation'],
            f'{label}: continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    require(actual['memory'] == expected['memory'], label + ': full RAM differs')
    for name in (*REG_NAMES, 'ip', 'flags'):
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    require(len(actual['events']) == len(expected['events']),
            f'{label}: bus event count {len(actual["events"])}/'
            f'{len(expected["events"])}')
    for index, (got, ref) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == ref[:3],
                f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
                f'under {ref[4]:04X}')
    require(actual['used'] == expected['used'],
            f'{label}: provider effects {actual["used"]}/{expected["used"]}')
    if expected['device']:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA plane/latch state differs')
        actual_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        expected_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(actual_trace == expected_trace, label + ': VGA trace differs')
    return expected


def original_only_sweep():
    """Execute only each entry's cadence prefix for all 256 input bytes."""
    prefixes = {'state-0001': (0x22DF, 0x22E9, 4, 0x0F),
                'state-1000': (0x22F5, 0x22FF, 4, 0x0F),
                'state-2000': (0x2326, 0x2330, 4, 0x07),
                'state-4000': (0x2340, 0x2348, 3, 0xFF)}
    checks = 0
    prefix_sites = {}
    for entry, (start, stop_at, expected_count, mask) in prefixes.items():
        observed_counts = set()
        for initial in range(256):
            memory = bytearray(SIZE)
            memory[LOAD << 4:(LOAD << 4) + len(LOADED)] = LOADED
            regs = {name: 0 for name in REG_NAMES}
            flags = ((initial * 37 + 0x0207) & ALL_FLAGS) | 2
            flags &= ~TF
            regs.update(cs=LOAD, ip=start, ds=DATA_SEGMENT, es=0x6200,
                        ss=0x5000, si=0x6000, sp=0xDFFE, flags=flags,
                        ax=(((initial * 53 + 0xA1) & 0xFF) << 8) | 0x5A)
            put16(memory, DATA_SEGMENT, 0x6000, 0x0200)
            put16(memory, DATA_SEGMENT, 0x6002, 0x0040)
            put8(memory, DATA_SEGMENT, 0x6026, 0x35)
            put8(memory, DATA_SEGMENT, 0x6027, 0)
            put8(memory, DATA_SEGMENT, 0x6028, initial)
            case = dict(name=f'sweep-{entry}-{initial:02X}', entry=entry)
            result = Original(case, memory, regs, None, None,
                             stop_at=stop_at).run()
            stored = (initial + 1) & mask
            expected_zf = stored == (0x0E if entry == 'state-4000' else 0)
            observed = result['regs']
            oracle_require(result['status'] == 2 and result['continuation'] == stop_at,
                           f'{case["name"]}: cadence prefix missed {stop_at:04X}')
            oracle_require(len(result['sites']) == expected_count,
                           f'{case["name"]}: prefix executed {len(result["sites"])} sites, '
                           f'expected {expected_count}')
            oracle_require(get16(result['memory'], DATA_SEGMENT, 0x6028) == stored,
                           f'{case["name"]}: stored cadence byte differs')
            oracle_require((observed['ax'] & 0xFF) == stored and
                           (observed['ax'] >> 8) == (regs['ax'] >> 8),
                           f'{case["name"]}: prefix AL/AH differs from independent result')
            oracle_require(bool(observed['flags'] & ZF) == expected_zf,
                           f'{case["name"]}: prefix ZF differs from independent result')
            observed_counts.add(len(result['sites']))
            checks += 1
            if checks % 32 == 0:
                gc.collect()  # Reap Unicorn hook cycles within the worker cap.
        prefix_sites[entry] = next(iter(observed_counts))
    oracle_require(checks == 1024, f'original-only sweep covered {checks}/1024 values')
    return dict(stored_byte_values=256, executions=checks,
                prefix_instruction_counts=prefix_sites,
                compared=['record +28', 'AL', 'AH', 'ZF'],
                stop_before=['22E9', '22FF', '2330', '2348'])


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/regions.json', 'metadata/toolchain-lock.json',
        'src/program.asm', 'src/game_code.asm', 'src/entity_graphics.asm',
        'c/entity_cadence.c', 'c/entity_cadence.h', 'c/entity_finish.c',
        'c/entity_finish.h', 'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/coordinate_pixel.c', 'c/coordinate_pixel.h', 'c/special_blit.h',
        'c/regs.h', 'c/lemmings_sym.h', 'c/pcspeaker_interrupt.c',
        'c/pcspeaker_interrupt.h', 'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h', 'c/sound_interrupt.c',
        'c/sound_interrupt.h', 'c/sound_latches.c', 'c/sound_latches.h',
        'c/sound_latches_sym.h',
        'tests/entity_cadence.py', 'tests/entity_finish.py',
        'tests/entity_interactions.py', 'tests/coordinate_pixel.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/unpack.py', 'tools/common.py', 'tools/cbuild.py',
        'tools/bounded_process.py', 'tools/difftest.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned static image identity changed')
    oracle_require(sum(end - start for start, end in CADENCE_SPANS) == 113 and
                   len(OWN_INS) == 45 and len(OWN_EDGES) == 18,
                   f'cadence static inventory changed: bytes={sum(b-a for a,b in CADENCE_SPANS)} '
                   f'sites={len(OWN_INS)} edges={len(OWN_EDGES)}')
    oracle_require(IMAGE[0x22DF:0x2350] == LOADED[0x22DF:0x2350],
                   'cadence code unexpectedly depends on relocation')

    specs = cases()
    baseline = Native(directory)
    coverage, edges, child_sites, shared_sites, shared_edges = set(), set(), set(), set(), set()
    total_events = instruction_count = comparisons = 0
    rows = []
    for seed, case in enumerate(specs):
        expected = None
        for core in (True, False):
            result = compare_case(baseline, case, seed, core)
            if expected is None:
                expected = result
            coverage.update(result['sites'])
            edges.update(result['edges'])
            child_sites.update(result['pixel_sites'])
            shared_sites.update(result['shared_sites'])
            shared_edges.update(result['shared_edges'])
            total_events += len(result['events'])
            instruction_count += result['steps']
            comparisons += 1
        rows.append(dict(name=case['name'], entry=case['entry'],
                         provider=case.get('provider'),
                         status=expected['status'], continuation=expected['continuation'],
                         sites=sorted(expected['sites']), edges=sorted(expected['edges']),
                         pixel_child_sites=sorted(expected['pixel_sites']),
                         bus_events=len(expected['events']),
                         vga=bool(case.get('vga'))))
        gc.collect()

    oracle_require(coverage == OWN_SITES,
                   f'cadence executed sites differ: missing={sorted(OWN_SITES-coverage)} '
                   f'extra={sorted(coverage-OWN_SITES)}')
    oracle_require(edges == OWN_EDGES,
                   f'cadence CFG edges differ: missing={sorted(OWN_EDGES-edges)} '
                   f'extra={sorted(edges-OWN_EDGES)}')
    sweep = original_only_sweep()

    witnesses = ((1, 'state0001-retains-bit3'),
                 (2, 'state1000-empty-pixel-adds-live-delta'),
                 (3, 'state2000-mod8-completes-and-counter'),
                 (4, 'state4000-equality-mark'),
                 (5, 'state1000-live-return-provider-alias'),
                 (6, 'state1000-live-pop-provider-alias'),
                 (7, 'state4000-fresh-read-provider'),
                 (8, 'state4000-entry-flags-on-rmw'))
    mutation_rows = []
    by_name = {case['name']: (index, case) for index, case in enumerate(specs)}
    for mutation, name in witnesses:
        seed, witness = by_name[name]
        mutant = Native(directory, mutation)
        try:
            compare_case(mutant, witness, seed, core=False)
        except Mismatch as error:
            mutation_rows.append(dict(mutation=mutation, case=name,
                                      completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'cadence mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'cadence inputs changed during the bounded campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[list(span) for span in CADENCE_SPANS],
        translated_code_bytes=sum(end-start for start, end in CADENCE_SPANS),
        case_count=len(specs), comparisons=comparisons,
        mutation_count=len(mutation_rows), mutations=mutation_rows, cases=rows,
        executed_instruction_addresses=sorted(coverage),
        static_instruction_addresses=sorted(OWN_SITES),
        instruction_site_count=len(coverage),
        branch_instruction_addresses=sorted(OWN_BRANCHES),
        branch_edges=sorted(edges), static_branch_edges=sorted(OWN_EDGES),
        shared_mark_instruction_addresses=sorted(shared_sites),
        shared_mark_branch_edges=sorted(shared_edges),
        coordinate_pixel_child_instruction_addresses=sorted(child_sites),
        total_bus_events=total_events, original_instructions_executed=instruction_count,
        original_only_sweep=sweep,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=PROCESS_MIB + 256,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        input_hashes=after,
        domain='Four raw state entries 22DF..234F; original cadence byte transforms, '
               'mark exits through shared 20E2, and the 1000 state actual CALL/RET to '
               '6141. Compares whole RAM, returned registers, defined FLAGS and ordered '
               'memory/VGA events. Parent JMP dispatch and iteration after 1FEB remain '
               'outside this test. An original-only bounded prefix sweep covers all '
               '256 stored-byte values at each of the four entries, stopping before '
               'the cadence Jcc and independently checking +28, AL/AH and ZF.'))
    print(f'PASS entity cadence: {len(specs)} fixtures at core+adapter; '
          f'{len(coverage)} sites/{len(edges)} edges; {len(child_sites)} child sites; '
          f'{total_events} events; {len(mutation_rows)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-cadence arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-cadence-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB)


if __name__ == '__main__':
    main()
