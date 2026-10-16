"""Decoded C domains can share tails beyond a physical entry prefix."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from coverage import translated_code_bytes


class CoverageRangeTests(unittest.TestCase):
    def symbol(self,start,size,ranges):
        return dict(symbol_name='example',address=start,size=size,
                    c_implementation='c/example.c',c_code_ranges=ranges)

    def test_shared_tails_before_and_after_entry_union_once(self):
        ins=[dict(address=0x10,size=2),dict(address=0x20,size=3),
             dict(address=0x30,size=1)]
        rows=[self.symbol(0x20,3,[(0x10,0x12),(0x20,0x23),(0x30,0x31)]),
              self.symbol(0x30,1,[(0x10,0x12),(0x30,0x31)])]
        self.assertEqual(translated_code_bytes(rows,ins,0x40),
                         {0x10,0x11,0x20,0x21,0x22,0x30})

    def test_partial_instruction_endpoints_are_rejected(self):
        ins=[dict(address=0x10,size=3)]
        for span in [(0x11,0x13),(0x10,0x12)]:
            with self.subTest(span=span):
                with self.assertRaisesRegex(ValueError,'Partial instruction'):
                    translated_code_bytes([self.symbol(0x10,3,[span])],ins,0x20)

    def test_mixed_endpoints_of_overlapping_decodes_are_not_a_complete_instruction(self):
        ins=[dict(address=0x10,size=3),dict(address=0x11,size=3)]
        with self.assertRaisesRegex(ValueError,'Partial instruction'):
            translated_code_bytes([self.symbol(0x11,2,[(0x11,0x13)])],ins,0x20)

    def test_unresolved_gap_between_valid_endpoints_is_rejected(self):
        ins=[dict(address=0x10,size=1),dict(address=0x12,size=1)]
        with self.assertRaisesRegex(ValueError,'Unresolved/non-instruction'):
            translated_code_bytes([self.symbol(0x10,3,[(0x10,0x13)])],ins,0x20)

    def test_image_bounds_are_checked(self):
        ins=[dict(address=0x10,size=1)]
        for span in [(-1,0x11),(0x10,0x21),(0x10,0x10)]:
            with self.subTest(span=span):
                with self.assertRaisesRegex(ValueError,'outside image'):
                    translated_code_bytes([self.symbol(0x10,1,[span])],ins,0x20)


if __name__=='__main__':
    unittest.main()
