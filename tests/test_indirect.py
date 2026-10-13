"""Fail-closed local definitions and memory-operand audit regressions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from indirect import local_ax_definition,accesses

class IndirectTests(unittest.TestCase):
    def decode(self,data):
        md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);md.detail=True
        return md,{i.address:i for i in md.disasm(bytes.fromhex(data),0)}

    def test_incoming_edge_blocks_a_preceding_ax_definition(self):
        _,ins=self.decode('b87061 894414 c3')
        self.assertEqual(local_ax_definition(3,ins,{0}).address,0)
        self.assertIsNone(local_ax_definition(3,ins,{0,3}))

    def test_calls_and_partial_register_assignments_are_not_skipped(self):
        _,ins=self.decode('b87061 e80000 894414 c3')
        self.assertIsNone(local_ax_definition(6,ins,set()))
        _,ins=self.decode('b87061 b4ff 894414 c3')
        definition=local_ax_definition(5,ins,set())
        self.assertEqual(definition.address,3)
        self.assertEqual(definition.op_str,'ah, 0xff')

    def test_segment_and_string_accesses_are_explicit(self):
        md,ins=self.decode('8d5e14 894614 a5 368904')
        self.assertEqual(accesses(md,ins[0])[0]['access'],'address')
        self.assertEqual(accesses(md,ins[3])[0]['segment'],'ss')
        string=accesses(md,ins[6])
        self.assertEqual([(r['segment'],r['access']) for r in string],[('es','write'),('ds','read')])
        self.assertEqual(accesses(md,ins[7])[0]['segment'],'ss')

if __name__=='__main__':unittest.main()
