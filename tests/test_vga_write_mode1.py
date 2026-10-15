"""Independent latch-copy vectors; retain the existing mode-0/read vectors."""
import unittest
from minimap_vga import MinimapVga, VGA_BASE, fixture_vectors


class WriteModeOneTests(unittest.TestCase):
    def test_existing_mode_zero_and_read_vectors(self):
        fixture_vectors()

    def test_all_map_masks_and_cpu_bytes_ignore_mode_zero_controls(self):
        memory = bytearray(1 << 20)
        vga = MinimapVga(0x4dc2)
        vga.gc[5] = 1
        vga.gc[0] = vga.gc[1] = 15
        vga.gc[3] = 0x1f
        vga.gc[8] = 0
        latched, old = [0x12, 0x34, 0x56, 0x78], [0xa5, 0x5a, 0xc3, 0x3c]
        for mask in range(16):
            vga.seq[2] = mask
            for cpu_byte in range(256):
                for index, plane in enumerate(vga.planes): plane[0x1000] = old[index]
                vga.latches = list(latched)
                vga.write(memory, VGA_BASE + 0x1000, cpu_byte, 0x602)
                self.assertEqual([p[0x1000] for p in vga.planes],
                    [latched[n] if mask & (1 << n) else old[n] for n in range(4)])
                self.assertEqual(vga.latches, latched)
                self.assertEqual(memory[VGA_BASE + 0x1000], cpu_byte)

    def test_reads_refresh_all_latches_and_writes_retain_them(self):
        memory = bytearray(1 << 20)
        vga = MinimapVga(0x6d60)
        vga.gc[5] = 1; vga.seq[2] = 15
        for n, plane in enumerate(vga.planes):
            plane[0x100] = 0x21 + n; plane[0x101] = 0xa1 + n
        for read_map in range(4):
            vga.gc[4] = read_map
            self.assertEqual(vga.read(memory, VGA_BASE + 0x100, 2), 0x21 + read_map)
            vga.write(memory, VGA_BASE + 0x200, 0, 2)
            vga.write(memory, VGA_BASE + 0x201, 255, 2)
            for plane, value in zip(vga.planes, range(0x21, 0x25)):
                self.assertEqual((plane[0x200], plane[0x201]), (value, value))
            vga.read(memory, VGA_BASE + 0x101, 2)
            vga.write(memory, VGA_BASE + 0x202, 0x55, 2)
            self.assertEqual([p[0x202] for p in vga.planes], list(range(0xa1, 0xa5)))

    def test_unsupported_modes_still_fail(self):
        memory = bytearray(1 << 20)
        vga = MinimapVga(0x4def)
        for mode in (2, 3):
            vga.gc[5] = mode
            with self.assertRaisesRegex(AssertionError, 'write modes 0 and 1'):
                vga.write(memory, VGA_BASE, 0, 2)


if __name__ == '__main__': unittest.main()
