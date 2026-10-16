"""Original-only bounded witnesses for the 5B11/5BB0 sprite-bank producers.

The helper runs only the identified producer entry from the exact relocated main
image.  It returns the resulting RAM and separates producer coverage from any
consumer fixture that imports these bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]

import capstone
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                     UC_MEM_READ, UC_MEM_WRITE)
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX,
                               UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI,
                               UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS,
                               UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP,
                               UC_X86_REG_IP, UC_X86_REG_EFLAGS)


MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
LOAD_SEGMENT = 0x1010
SOURCE_SEGMENT = 0x7000
SOURCE_OFFSET = 0x0100
DESTINATION_SEGMENT = 0x6000
DESTINATION_OFFSET = 0x0100
STACK_SEGMENT = 0x5000
ENTRY_SP = 0xF000
RETURN_TARGET = 0xF000
INSTRUCTION_LIMIT = 20_000

ENTRY_5B11, END_5B11 = 0x5B11, 0x5BB0
ENTRY_5BB0, END_5BB0 = 0x5BB0, 0x5C06
DX_5B11 = 0x020A
DX_5BB0_12 = 0x020C
DX_5BB0_13 = 0x020D

IMAGE, ORACLE = unpack(ASSET.read_bytes())
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
WORKER_SECONDS, PROCESS_MIB = 60, 384


class ProducerFailure(AssertionError):
    """The bounded original producer escaped its domain or disagreed with its model."""


def require(condition, message):
    if not condition:
        raise ProducerFailure(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MEMORY_MASK


@dataclass(frozen=True)
class DataBank:
    """A generated bank's copied/shifted rows and trailing OR mask."""

    index: int
    shift: int | None
    output_offset: int
    output_length: int
    plane_offset: int
    plane_length: int
    plane_count: int
    plane_stride: int
    mask_offset: int
    mask_length: int


@dataclass(frozen=True)
class ProducerWitness:
    """Actual original output plus independently checked provenance and coverage."""

    entry: int
    dx: int
    source_segment: int
    source_offset: int
    source_bytes: bytes
    destination_segment: int
    destination_offset: int
    output_bytes: bytes
    banks: tuple[DataBank, ...]
    memory: bytearray
    registers: dict[str, int]
    sites: frozenset[int]
    edges: frozenset[tuple[int, int]]
    steps: int
    events: tuple[tuple[str, int, int, int | None], ...]
    event_count: int

    def bank(self, index=0):
        """Return one bank copied from the actual post-run original RAM."""
        descriptor = self.banks[index]
        start = descriptor.output_offset
        return self.output_bytes[start:start + descriptor.output_length]

    @property
    def output_physical(self):
        return physical(self.destination_segment, self.destination_offset)


class Access:
    """Bounded data-memory trace for one producer invocation."""

    event_limit = 10_000

    def __init__(self):
        self.events = []
        self.failure = None

    def hook(self, cpu, access, address, size, value, _user_data):
        if len(self.events) >= self.event_limit:
            self.failure = f'data access event budget {self.event_limit} exhausted'
            cpu.emu_stop()
            return
        if access == UC_MEM_READ:
            kind, observed = 'read', None
        elif access == UC_MEM_WRITE:
            kind = 'write'
            observed = value & ((1 << (8 * size)) - 1)
        else:
            self.failure = f'unexpected Unicorn memory access kind {access}'
            cpu.emu_stop()
            return
        self.events.append((kind, address & MEMORY_MASK, size, observed))


_REGISTERS = {
    'ax': UC_X86_REG_AX, 'bx': UC_X86_REG_BX, 'cx': UC_X86_REG_CX,
    'dx': UC_X86_REG_DX, 'si': UC_X86_REG_SI, 'di': UC_X86_REG_DI,
    'bp': UC_X86_REG_BP, 'cs': UC_X86_REG_CS, 'ds': UC_X86_REG_DS,
    'es': UC_X86_REG_ES, 'ss': UC_X86_REG_SS, 'sp': UC_X86_REG_SP,
    'ip': UC_X86_REG_IP, 'flags': UC_X86_REG_EFLAGS,
}


def _instruction_map(entry, end):
    return {ins.address: ins
            for ins in MD.disasm(IMAGE[entry:end], entry)}


def _source_bytes(word_count, seed):
    """Deterministic varied rows, including carries and sparse/dense words."""
    special = (0x0000, 0x0001, 0x8000, 0xFFFF, 0x0101, 0x8080,
               0x7FFF, 0x00FF, 0xFF00, 0xA55A, 0x5AA5, 0xC33C)
    rng = random.Random(seed)
    payload = bytearray()
    for index in range(word_count):
        word = special[index % len(special)] ^ rng.randrange(0x10000)
        payload.extend((word >> 8, word & 0xFF))
    return bytes(payload)


def expected_5b11(source, dx=DX_5B11):
    """Independent 24-bit shift and row-OR model for the eight 5B11 banks."""
    dh, dl = (dx >> 8) & 0xFF, dx & 0xFF
    require(len(source) == 2 * dh * dl,
            '5B11 expected model received a source span of the wrong size')
    banks = []
    for shift in range(8):
        planes = []
        for row in range(dh):
            plane = bytearray()
            for column in range(dl):
                source_index = 2 * (row * dl + column)
                chain = (source[source_index] << 16) | (source[source_index + 1] << 8)
                shifted = chain >> shift
                plane.extend(((shifted >> 16) & 0xFF,
                              (shifted >> 8) & 0xFF,
                              shifted & 0xFF))
            planes.append(bytes(plane))
        mask = bytearray(3 * dl)
        for plane in planes:
            for index, value in enumerate(plane):
                mask[index] |= value
        banks.append(b''.join(planes) + bytes(mask))
    return tuple(banks)


def expected_5bb0(source, dx):
    """Independent word-row copy and per-column OR model for 5BB0."""
    dh, dl = (dx >> 8) & 0xFF, dx & 0xFF
    copied_size = 2 * dh * dl
    require(len(source) == copied_size,
            '5BB0 expected model received a source span of the wrong size')
    mask = bytearray()
    for column in range(dl):
        word = 0
        for row in range(dh):
            offset = 2 * (row * dl + column)
            word |= source[offset] | (source[offset + 1] << 8)
        mask.extend((word & 0xFF, word >> 8))
    return source + bytes(mask)


def _run_original(entry, end, dx, source, *, seed):
    """Run one original leaf with actual SS return memory and hard local bounds."""
    instructions = _instruction_map(entry, end)
    require(instructions and min(instructions) == entry,
            f'{entry:04X}: custom original instruction map is incomplete')
    expected_return_site = end - 1
    require(instructions[expected_return_site].mnemonic.lower() == 'ret',
            f'{entry:04X}: expected actual near RET is not at {expected_return_site:04X}')

    memory = bytearray([0xCC]) * MEMORY_SIZE
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD_SEGMENT)
    image_base = physical(LOAD_SEGMENT, 0)
    memory[image_base:image_base + len(loaded)] = loaded
    source_address = physical(SOURCE_SEGMENT, SOURCE_OFFSET)
    memory[source_address:source_address + len(source)] = source
    destination_address = physical(DESTINATION_SEGMENT, DESTINATION_OFFSET)
    maximum_output = 24 * (dx & 0xFF) * (((dx >> 8) & 0xFF) + 1) \
        if entry == ENTRY_5B11 else 2 * (dx & 0xFF) * (((dx >> 8) & 0xFF) + 1)
    require(destination_address + maximum_output < MEMORY_SIZE,
            'constructed destination wraps the one-MiB RAM fixture')
    stack_address = physical(STACK_SEGMENT, ENTRY_SP)
    memory[stack_address] = RETURN_TARGET & 0xFF
    memory[stack_address + 1] = (RETURN_TARGET >> 8) & 0xFF

    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, MEMORY_SIZE)
    cpu.mem_write(0, bytes(memory))
    initial = {
        'ax': 0xA531, 'bx': 0xB642, 'cx': 0xC753, 'dx': dx,
        'si': SOURCE_OFFSET, 'di': DESTINATION_OFFSET, 'bp': 0xD864,
        'cs': LOAD_SEGMENT, 'ds': SOURCE_SEGMENT,
        'es': DESTINATION_SEGMENT, 'ss': STACK_SEGMENT,
        'sp': ENTRY_SP, 'ip': entry, 'flags': 0x0002,
    }
    for name, value in initial.items():
        cpu.reg_write(_REGISTERS[name], value)

    access = Access()
    visited, edge_set = set(), set()
    steps = 0
    previous_ip = None
    stopped = False
    hook_failure = None

    def code_hook(machine, _address, _size, _user_data):
        nonlocal steps, previous_ip, stopped, hook_failure
        cs = machine.reg_read(UC_X86_REG_CS) & 0xFFFF
        ip = machine.reg_read(UC_X86_REG_IP) & 0xFFFF
        if cs == LOAD_SEGMENT and ip == RETURN_TARGET:
            if previous_ip != expected_return_site:
                hook_failure = (f'{entry:04X}: reached stop target after '
                                f'{previous_ip!r}, not actual RET {expected_return_site:04X}')
            stopped = hook_failure is None
            machine.emu_stop()
            return
        if cs != LOAD_SEGMENT or ip not in instructions:
            hook_failure = f'{entry:04X}: escaped custom instruction map at {cs:04X}:{ip:04X}'
            machine.emu_stop()
            return
        instruction = instructions[ip]
        actual_code = bytes(machine.mem_read(physical(cs, ip), instruction.size))
        if actual_code != loaded[ip:ip + instruction.size]:
            hook_failure = f'{entry:04X}: loaded instruction bytes changed at {ip:04X}'
            machine.emu_stop()
            return
        if previous_ip is not None:
            previous = instructions[previous_ip]
            if previous.group(capstone.CS_GRP_JUMP) or previous.mnemonic.lower().startswith('loop'):
                edge_set.add((previous_ip, ip))
        visited.add(ip)
        previous_ip = ip
        steps += 1
        if steps > INSTRUCTION_LIMIT:
            hook_failure = f'{entry:04X}: instruction budget {INSTRUCTION_LIMIT} exhausted'
            machine.emu_stop()

    cpu.hook_add(UC_HOOK_CODE, code_hook)
    cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, access.hook)
    cpu.emu_start(physical(LOAD_SEGMENT, entry), 0, count=INSTRUCTION_LIMIT)
    require(access.failure is None,
            f'{entry:04X}: {access.failure or "data access trace failed"}')
    require(hook_failure is None, hook_failure or 'original instruction hook failed')
    require(stopped, f'{entry:04X}: original leaf did not reach its bounded RET target')
    require(steps <= INSTRUCTION_LIMIT,
            f'{entry:04X}: original instruction budget exhausted')
    require(len(access.events) <= Access.event_limit,
            f'{entry:04X}: original data access budget exhausted')

    final_registers = {name: cpu.reg_read(register) & 0xFFFF
                       for name, register in _REGISTERS.items()}
    require(final_registers['cs'] == LOAD_SEGMENT and
            final_registers['ip'] == RETURN_TARGET and
            final_registers['sp'] == ((ENTRY_SP + 2) & 0xFFFF),
            f'{entry:04X}: actual near RET did not consume the constructed SS word')
    require(not (final_registers['flags'] & 0x0400),
            f'{entry:04X}: DF changed despite normal DF=0 fixture')

    # The ordinary fixture admits only source reads, generated-buffer traffic,
    # and actual stack traffic. It deliberately excludes VGA/provider aliases.
    stack_low = physical(STACK_SEGMENT, ENTRY_SP - 0x100)
    stack_high = physical(STACK_SEGMENT, ENTRY_SP + 2)
    output_end = destination_address + maximum_output
    for kind, address, size, _value in access.events:
        last = address + size - 1
        in_source = source_address <= address and last < source_address + len(source)
        in_output = destination_address <= address and last < output_end
        in_stack = stack_low <= address and last < stack_high
        if kind == 'write':
            require(in_output or in_stack,
                    f'{entry:04X}: write escaped output/stack at {address:05X}+{size}')
        else:
            require(in_source or in_output or in_stack,
                    f'{entry:04X}: read escaped source/output/stack at {address:05X}+{size}')

    final_memory = bytearray(cpu.mem_read(0, MEMORY_SIZE))
    output_bytes = bytes(final_memory[destination_address:output_end])
    return (final_memory, output_bytes, final_registers, frozenset(visited),
            frozenset(edge_set), steps, tuple(access.events))


def produce_5b11(seed=0x5B11, *, dx=DX_5B11):
    """Produce and independently validate all eight normal 5B11 shift banks."""
    dh, dl = (dx >> 8) & 0xFF, dx & 0xFF
    source = _source_bytes(dh * dl, seed)
    expected_banks = expected_5b11(source, dx)
    output_expected = b''.join(expected_banks)
    memory, output, registers, sites, edges, steps, events = _run_original(
        ENTRY_5B11, END_5B11, dx, source, seed=seed)
    require(output == output_expected,
            '5B11 actual producer output differs from independent eight-shift model')
    bank_length = len(expected_banks[0])
    banks = tuple(DataBank(index=index, shift=index,
                           output_offset=index * bank_length,
                           output_length=bank_length,
                           plane_offset=index * bank_length,
                           plane_length=dh * dl * 3,
                           plane_count=dh, plane_stride=dl * 3,
                           mask_offset=index * bank_length + dh * dl * 3,
                           mask_length=dl * 3)
                  for index in range(8))
    require(len(output) == 720 if dx == DX_5B11 else len(output) == len(output_expected),
            '5B11 output length differs from the requested dimensions')
    return ProducerWitness(ENTRY_5B11, dx, SOURCE_SEGMENT, SOURCE_OFFSET,
                           source, DESTINATION_SEGMENT, DESTINATION_OFFSET,
                           output, banks, memory, registers, sites, edges,
                           steps, events, len(events))


def produce_5bb0(dx=DX_5BB0_12, seed=0x5BB0):
    """Produce and independently validate one normal 5BB0 copied/mask bank."""
    dh, dl = (dx >> 8) & 0xFF, dx & 0xFF
    source = _source_bytes(dh * dl, seed)
    expected = expected_5bb0(source, dx)
    memory, output, registers, sites, edges, steps, events = _run_original(
        ENTRY_5BB0, END_5BB0, dx, source, seed=seed)
    require(output == expected,
            f'5BB0 DX={dx:04X} actual producer differs from independent copy/OR model')
    plane_length = 2 * dh * dl
    mask_length = 2 * dl
    bank = DataBank(index=0, shift=None, output_offset=0,
                    output_length=len(expected), plane_offset=0,
                    plane_length=plane_length, plane_count=dh,
                    plane_stride=2 * dl, mask_offset=plane_length,
                    mask_length=mask_length)
    return ProducerWitness(ENTRY_5BB0, dx, SOURCE_SEGMENT, SOURCE_OFFSET,
                           source, DESTINATION_SEGMENT, DESTINATION_OFFSET,
                           output, (bank,), memory, registers, sites, edges,
                           steps, events, len(events))


def original_only():
    """Run bounded producer-only validation; no C code or consumer is invoked."""
    witnesses = (produce_5b11(),
                 produce_5bb0(DX_5BB0_12, 0x5BB012),
                 produce_5bb0(DX_5BB0_13, 0x5BB013))
    for witness in witnesses:
        print(f'PASS original sprite producer {witness.entry:04X} '
              f'DX={witness.dx:04X}: {len(witness.output_bytes)} bytes, '
              f'{len(witness.sites)} sites, {witness.steps} steps, '
              f'{witness.event_count} memory events', flush=True)
    return witnesses


if __name__ == '__main__':
    if sys.argv[1:] == ['--original-worker']:
        original_only()
    elif not sys.argv[1:]:
        from bounded_process import run_bounded
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
    else:
        raise SystemExit('usage: entity_sprite_layout.py [--original-worker]')
