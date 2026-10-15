"""The faster observation path must read the same live architectural state."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16
import terrain_drawing as piece


class OracleRegisterTests(unittest.TestCase):
    def test_flag_comparison_preserves_masks_and_mismatch_diagnostics(self):
        native, original = piece.common.EventTrace(), piece.common.EventTrace()
        native.add('read', 0x12345, 0x67, 0x10)
        original.add('read', 0x12345, 0x67, 0, 0x40)
        piece.common.compare_event_traces(native, original, 'undefined AF')
        original.mask_bytes[:] = b'\x10\x00'
        with self.assertRaisesRegex(piece.common.Mismatch, 'bus flags differ at event 0'):
            piece.common.compare_event_traces(native, original, 'defined AF')

    def test_reused_snapshot_matches_public_reads_after_state_changes(self):
        machine = Uc(UC_ARCH_X86, UC_MODE_16)
        read = piece.instruction_state_reader(machine)
        registers = (piece.oracle.REG['cs'], piece.oracle.REG['ip'], piece.x.UC_X86_REG_EFLAGS)
        for cs, ip in ((0, 0), (0x1010, 0x374f), (0xffff, 0xffff),
                       (0x2345, 1), (0x0310, 0x3979), (0, 0)):
            for flags in (0, 2, 0xfd7, 0xffff, 0x400, 0x200):
                with self.subTest(cs=cs, ip=ip, flags=flags):
                    for register, value in zip(registers, (cs, ip, flags)):
                        machine.reg_write(register, value)
                    self.assertEqual(read(), tuple(machine.reg_read(r) for r in registers))

    def test_binding_errors_and_abi_mismatches_fail_closed(self):
        machine = Uc(UC_ARCH_X86, UC_MODE_16)
        with patch.object(machine, '_do_reg_read_batch', return_value=7):
            with self.assertRaisesRegex(piece.common.VerificationFailure, 'read failed'):
                piece.instruction_state_reader(machine)
        machine.reg_write(piece.oracle.REG['cs'], 0x1010)
        with patch.object(machine, '_do_reg_read_batch', return_value=0):
            with self.assertRaisesRegex(piece.common.VerificationFailure, 'ABI disagrees'):
                piece.instruction_state_reader(machine)


if __name__ == '__main__':
    unittest.main()
