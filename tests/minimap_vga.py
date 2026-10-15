"""Independent VGA device fixture for the 796F minimap cluster.

Models the unchained A0000-AFFFF planar aperture, Graphics Controller read
modes 0/1 and write modes 0/1. This is a bounded device fixture, not a VGA card
or timing/scanout emulator; see docs/minimap-vga.md for the contract.
"""
from __future__ import annotations

import random


VGA_BASE = 0xA0000
VGA_END = 0xB0000


class MinimapVga:
    """Seedable four-plane VGA fixture with a 64 KiB A000 aperture.

    ``mem`` passed to read/write is the host's 1 MiB physical-memory image.
    Aperture accesses mirror the value seen by the CPU into that image, while
    the display data remains owned by ``planes``. Trace entries preserve raw
    flags so a caller can normalize undefined or phase-specific flag bits.
    """

    def __init__(self, seed, read_map=0):
        rng = random.Random(seed)
        self.planes = [bytearray(rng.randbytes(65536)) for _ in range(4)]
        self.latches = [rng.randrange(256) for _ in range(4)]
        self.seq = [rng.randrange(256) for _ in range(5)]
        self.gc = [rng.randrange(256) for _ in range(9)]
        # Establish the unchained A0000 64 KiB mapping assumed by this fixture.
        self.seq[4] = 0x06  # extended memory; odd/even disabled; chain-4 off
        self.gc[4] = read_map & 3
        self.gc[6] = 0x05  # graphics mode and A0000-AFFFF memory map
        self.si = 0
        self.gi = 0
        self.trace = []
        self.outcount = 0

    def out(self, port, value, flags):
        """Apply one word write to the Sequencer or Graphics Controller pair."""
        port &= 0xFFFF
        value &= 0xFFFF
        self.trace.append(('out', port, value, flags))
        self.outcount += 1
        index = value & 0xFF
        data = (value >> 8) & 0xFF
        if port == 0x3C4:
            if index >= len(self.seq):
                raise AssertionError(f'Unsupported sequencer index {index:02x}')
            self.si = index
            self.seq[index] = data
        elif port == 0x3CE:
            if index >= len(self.gc):
                raise AssertionError(f'Unsupported graphics-controller index {index:02x}')
            self.gi = index
            self.gc[index] = data
        else:
            raise AssertionError(f'Unsupported VGA word port {port:04x}')

    def _check_aperture(self):
        if self.seq[4] & 0x0C != 0x04:
            raise AssertionError('Fixture requires unchained, odd/even-disabled VGA memory')
        if self.gc[6] & 0x0D != 0x05:
            raise AssertionError('Fixture requires graphics mode and the 64 KiB A000 map')

    def read(self, mem, p, flags):
        if not VGA_BASE <= p < VGA_END:
            return mem[p]

        self._check_aperture()
        offset = p - VGA_BASE
        # Every CPU read loads all four latches, including read mode 1.
        self.latches = [plane[offset] for plane in self.planes]
        if self.gc[5] & 0x08:
            compare = self.gc[2] & 0x0F
            care = self.gc[7] & 0x0F
            value = 0xFF
            for plane in range(4):
                if care & (1 << plane):
                    if compare & (1 << plane):
                        value &= self.latches[plane]
                    else:
                        value &= ~self.latches[plane]
            value &= 0xFF
        else:
            value = self.latches[self.gc[4] & 3]

        mem[p] = value
        self.trace.append(('read', offset, value, flags))
        return value

    def write(self, mem, p, value, flags):
        value &= 0xFF
        if VGA_BASE <= p < VGA_END:
            self._check_aperture()
            mode = self.gc[5] & 0x03
            if mode not in (0, 1):
                raise AssertionError('Fixture covers VGA write modes 0 and 1 only')

            offset = p - VGA_BASE
            if mode == 1:
                # IBM VGA TRM, Figure2-76 (2-85): write the read latches.
                # Map Mask still selects planes; CPU data, set/reset, logical
                # operation, rotation and Bit Mask do not modify these bytes.
                for index, plane in enumerate(self.planes):
                    if self.seq[2] & (1 << index):
                        plane[offset] = self.latches[index]
                self.trace.append(('write', offset, value, flags))
                mem[p] = value
                return
            rotate = self.gc[3] & 7
            rotated = value if rotate == 0 else (
                (value >> rotate) | (value << (8 - rotate))) & 0xFF
            operation = (self.gc[3] >> 3) & 3
            bit_mask = self.gc[8]
            plane_mask = self.seq[2] & 0x0F

            for plane in range(4):
                if not plane_mask & (1 << plane):
                    continue
                if self.gc[1] & (1 << plane):
                    source = 0xFF if self.gc[0] & (1 << plane) else 0
                else:
                    source = rotated

                latch = self.latches[plane]
                if operation == 1:
                    result = source & latch
                elif operation == 2:
                    result = source | latch
                elif operation == 3:
                    result = source ^ latch
                else:
                    result = source
                self.planes[plane][offset] = (
                    (result & bit_mask) | (latch & (~bit_mask & 0xFF)))

            # Unicorn's mapped-memory image represents the host-visible bus
            # byte, not the post-GC plane data.
            self.trace.append(('write', offset, value, flags))
        mem[p] = value

    def state(self):
        """Return a detached, deeply comparable snapshot of VGA state."""
        return (tuple(bytes(plane) for plane in self.planes),
                tuple(self.latches), tuple(self.seq), tuple(self.gc),
                self.si, self.gi, self.outcount)


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def fixture_vectors():
    """Run independent truth-table checks for the documented device contract."""
    mem = bytearray(1 << 20)
    vga = MinimapVga(0x796F, read_map=0)

    # Read mode 0: all four plane bytes have a direct selectable read map,
    # with every CPU read refreshing all latches and the aperture cache.
    offset = 0x1234
    plane_bytes = (0x12, 0x34, 0x56, 0x78)
    for plane, byte in zip(vga.planes, plane_bytes):
        plane[offset] = byte
    vga.gc[5] = 0
    for plane_number, expected in enumerate(plane_bytes):
        vga.gc[4] = plane_number
        got = vga.read(mem, VGA_BASE + offset, 0x0202)
        _expect(got == expected, f'read map {plane_number}: {got:02x} != {expected:02x}')
        _expect(vga.latches == list(plane_bytes), 'read mode 0 did not load all plane latches')
        _expect(mem[VGA_BASE + offset] == expected, 'read did not mirror CPU-visible byte')

    # Read mode 1: adjacent bytes encode all sixteen planar color values in
    # their eight bit positions. Exhaust every reference color and every care
    # mask; care=0 must compare vacuously true for every pixel.
    patterns = (tuple(range(8)), tuple(range(8, 16)))
    for byte_index, colors in enumerate(patterns):
        at = offset + 0x20 + byte_index
        for plane_no, plane in enumerate(vga.planes):
            plane[at] = sum(((color >> plane_no) & 1) << bit
                            for bit, color in enumerate(colors))
    vga.gc[5] = 0x08
    for care in range(16):
        vga.gc[7] = care
        for compare in range(16):
            vga.gc[2] = compare
            for byte_index, colors in enumerate(patterns):
                at = offset + 0x20 + byte_index
                expected = sum(
                    (1 << bit) for bit, color in enumerate(colors)
                    if (color & care) == (compare & care))
                got = vga.read(mem, VGA_BASE + at, care * 16 + compare)
                _expect(got == expected,
                        f'read mode 1 care={care:x} compare={compare:x} '
                        f'byte={byte_index}: {got:02x} != {expected:02x}')
                _expect(vga.latches == [plane[at] for plane in vga.planes],
                        'read mode 1 did not load all plane latches')
                _expect(mem[VGA_BASE + at] == expected,
                        'read mode 1 did not mirror comparison result')

    # Write-mode-0 set/reset selection is tested independently from the map
    # mask and bit-mask/latch merge.
    vga.gc[5] = 0
    vga.gc[3] = 0
    vga.gc[8] = 0xFF
    vga.gc[0] = 0x0A
    vga.gc[1] = 0x0F
    vga.seq[2] = 0x0F
    vga.write(mem, VGA_BASE + offset + 0x40, 0x35, 0x0002)
    got = [plane[offset + 0x40] for plane in vga.planes]
    _expect(got == [0x00, 0xFF, 0x00, 0xFF], f'set/reset result: {got!r}')
    _expect(mem[VGA_BASE + offset + 0x40] == 0x35,
            'set/reset write did not retain CPU input in aperture cache')

    # Sequencer map mask controls which planes receive the write.
    at = offset + 0x41
    before = [0x10, 0x20, 0x30, 0x40]
    for plane, byte in zip(vga.planes, before):
        plane[at] = byte
    vga.gc[1] = 0
    vga.seq[2] = 0x05
    vga.write(mem, VGA_BASE + at, 0xA5, 0x0046)
    got = [plane[at] for plane in vga.planes]
    _expect(got == [0xA5, 0x20, 0xA5, 0x40], f'map-mask result: {got!r}')

    # A read followed by a write at the same offset exercises the latch-driven
    # bit-mask merge used by read/modify/write drawing sequences.
    at = offset + 0x42
    before = [0x00, 0x55, 0xAA, 0xFF]
    for plane, byte in zip(vga.planes, before):
        plane[at] = byte
    vga.seq[2] = 0x0F
    vga.gc[1] = 0
    vga.gc[8] = 0x3C
    vga.gc[5] = 0
    vga.gc[4] = 2
    _expect(vga.read(mem, VGA_BASE + at, 0x0100) == before[2],
            'read/modify/write setup selected the wrong plane')
    _expect(vga.latches == before, 'read/modify/write setup loaded wrong latches')
    vga.write(mem, VGA_BASE + at, 0xA5, 0x0101)
    expected = [((0xA5 & 0x3C) | (old & 0xC3)) for old in before]
    got = [plane[at] for plane in vga.planes]
    _expect(got == expected, f'bit-mask/latch merge: {got!r} != {expected!r}')

    # Exercise byte rotation and each documented mode-0 logical operation.
    at = offset + 0x43
    vga.gc[8] = 0xFF
    vga.gc[1] = 0
    vga.seq[2] = 0x0F
    before = [0x0F, 0x33, 0x55, 0xF0]
    for plane, byte in zip(vga.planes, before):
        plane[at] = byte
    vga.read(mem, VGA_BASE + at, 0)
    cpu = 0xD2
    rotated = ((cpu >> 1) | (cpu << 7)) & 0xFF
    for operation in range(4):
        vga.latches = list(before)
        vga.gc[3] = (operation << 3) | 1
        vga.write(mem, VGA_BASE + at, cpu, operation)
        if operation == 0:
            expected = [rotated] * 4
        elif operation == 1:
            expected = [rotated & old for old in before]
        elif operation == 2:
            expected = [rotated | old for old in before]
        else:
            expected = [rotated ^ old for old in before]
        got = [plane[at] for plane in vga.planes]
        _expect(got == expected,
                f'rotate/logical op {operation}: {got!r} != {expected!r}')

    # Non-aperture accesses stay ordinary RAM and do not add device events.
    event_count = len(vga.trace)
    mem[0x7000] = 0x66
    _expect(vga.read(mem, 0x7000, 0xFFFF) == 0x66, 'ordinary RAM read changed')
    vga.write(mem, 0x7001, 0x77, 0xFFFF)
    _expect(mem[0x7001] == 0x77, 'ordinary RAM write changed')
    _expect(len(vga.trace) == event_count, 'ordinary RAM access appeared in VGA trace')


if __name__ == '__main__':
    fixture_vectors()
    print('PASS minimap VGA fixture: mode-0/mode-1 reads and mode-0 writes')
