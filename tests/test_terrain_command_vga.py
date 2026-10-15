"""Device-backed command fetches at both pinned terrain-reader entries."""
import copy
import ctypes
import gc
import subprocess
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import terrain_commands as reader
from object_graphics_bus import CallbackBus, configure_vga
from bounded_process import run_bounded, temporary_build_directory
from common import ROOT, BUILD
from dat_io_c import Regs, MEM
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x


def original(memory, registers, flags, redraw, device):
    """Run unchanged original bytes; no child or sentinel target executes."""
    _, start, call, finished = reader.command_spans(redraw)
    allowed = reader.command_sites(redraw)
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 1 << 21)
    uc.mem_write(0, bytes(memory) * 2)
    for name, register in reader.oracle.REG.items():
        uc.reg_write(register, registers[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    seen = set()
    events = []
    failures = []
    done = False

    def fail(cpu, message):
        failures.append(message)
        cpu.emu_stop()

    def code(cpu, address, _size, _context):
        nonlocal done
        offset = address - (registers['cs'] << 4)
        if cpu.reg_read(reader.oracle.REG['cs']) != registers['cs']:
            fail(cpu, 'Original VGA reader changed CS')
        elif offset in (call, finished):
            done = True
            cpu.emu_stop()
        elif offset not in allowed:
            fail(cpu, f'Original VGA reader escaped at {offset:04x}')
        else:
            seen.add(offset)

    def read(cpu, _access, address, size, _value, _context):
        try:
            for index in range(size):
                if len(events) >= 4:
                    fail(cpu, 'Original VGA reader exceeded four byte reads')
                    return
                at = (address + index) & 0xfffff
                current_flags = cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
                value = device.read(memory, at, current_flags)
                events.append(('read', at, value, current_flags))
                byte = bytes((value,))
                cpu.mem_write(at, byte)
                cpu.mem_write(at + (1 << 20), byte)
        except Exception as error:
            fail(cpu, f'Original VGA read provider failed: {error}')

    def write(cpu, *_args):
        fail(cpu, 'Original command reader unexpectedly wrote memory')

    def interrupt(cpu, number, _context):
        fail(cpu, f'Original command reader raised INT{number:02x}')

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, read)
    uc.hook_add(UC_HOOK_MEM_WRITE, write)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    try:
        uc.emu_start((registers['cs'] << 4) + start, 0, count=16)
    except Exception as error:
        raise RuntimeError(f'Original VGA reader emulation failed: {error}') from error
    if failures or not done or seen != set(allowed):
        raise RuntimeError(f'Original VGA reader failed: {failures}; done={done}; sites={seen}')
    actual = {name: uc.reg_read(register) for name, register in reader.oracle.REG.items()}
    actual['flags'] = uc.reg_read(x.UC_X86_REG_EFLAGS)
    if bytes(uc.mem_read(0, 1 << 20)) != memory:
        raise RuntimeError('Original device/canonical-memory views disagree')
    return actual, events


def compare(library, redraw, read_plane, horizontal, backwards, seed):
    case = dict(seed=seed, horizontal=0x1234, vertical=0x5678,
                ds=0x9ef2, cursor=0x10eb, redraw=redraw,
                flags=2 | (0x400 if backwards else 0) |
                      (0x210 if read_plane else 0))
    initial, registers, flags, _load = reader.prepare(case)
    registers['ip'] = reader.command_spans(redraw)[1]
    device = configure_vga(initial, seed, read_plane=read_plane)
    payload = horizontal.to_bytes(2, 'big') + bytes((0x9a, 0xbc))
    addresses = [reader.physical(registers['ds'], 0x10eb + n) for n in range(4)]
    if addresses != [0xa000b + n for n in range(4)]:
        raise RuntimeError('VGA command fixture address changed')
    for at, value in zip(addresses, payload):
        # All planes differ from both canonical RAM and one another. The
        # selected plane alone supplies the command, and every read loads latches.
        initial[at] = value ^ 0xff
        for plane in range(4):
            device.planes[plane][at - 0xa0000] = value ^ ((plane ^ read_plane) * 0x33)
    initial_planes = tuple(bytes(plane) for plane in device.planes)
    native_memory = bytearray(initial)
    native_device = copy.deepcopy(device)
    native_bus = CallbackBus(native_memory, native_device)
    state = Regs(**registers, flags=flags)
    library.lmn_read_terrain_command_adapter(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(native_memory),
        ctypes.byref(state), redraw,
        ctypes.cast(ctypes.byref(native_bus.bus), ctypes.POINTER(reader.Bus)))
    original_memory = bytearray(initial)
    expected, original_events = original(original_memory, registers, flags, redraw, device)
    for name in (*reader.oracle.REG_NAMES, 'flags'):
        mask = reader.FLAG_MASK if name == 'flags' else 0xffff
        if (getattr(state, name) ^ expected[name]) & mask:
            raise AssertionError(f'VGA command {seed}: {name} differs')
    expected_reads = [('read', at, value, flags) for at, value in zip(addresses, payload)]
    if native_bus.events != expected_reads or original_events != expected_reads:
        raise AssertionError('VGA command values/order/incoming flags differ')
    if native_memory != original_memory or native_device.state() != device.state():
        raise AssertionError('VGA command RAM/device state differs')
    if tuple(bytes(plane) for plane in native_device.planes) != initial_planes:
        raise AssertionError('Command reads changed VGA planes')
    if native_device.trace != device.trace:
        raise AssertionError('VGA command device access order differs')
    _, _, call, finished = reader.command_spans(redraw)
    if (state.ax, state.bx, state.si, state.ip) != (
            horizontal, 0x9abc, 0x10ef, finished if horizontal == 0xffff else call):
        raise AssertionError('Independent VGA command expectation differs')


def worker(directory):
    library = reader.library(directory)
    count = 0
    for redraw in (0, 1):
        for plane in (0, 3):
            for horizontal in (0x1234, 0xfffe, 0xffff):
                for backwards in (False, True):
                    compare(library, redraw, plane, horizontal, backwards, count)
                    count += 1
                    gc.collect()
    print(f'PASS terrain VGA commands: {count} original/C comparisons, both entries, '
          'read maps0/3, both DF, four ordered byte reads and live latches')


class TerrainCommandVgaTests(unittest.TestCase):
    def test_device_backed_commands(self):
        BUILD.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='terrain-command-vga-', parent=BUILD) as directory:
            result = run_bounded(
                [sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                cwd=ROOT, timeout=60, memory_mib=256,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertIn('PASS terrain VGA commands: 24', result.stdout)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    else:
        unittest.main()
