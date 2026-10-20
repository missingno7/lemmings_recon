"""Packed fixture observations preserve device behavior and every raw field."""
import copy
import sys
import unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/'tools')]
import verification as base
from main_menu import PackedVgaTrace

class PackedVgaTraceTests(unittest.TestCase):
    def test_device_state_order_flags_copy_and_hard_budget(self):
        plain=base.new_device(0x43F2);packed=copy.deepcopy(plain);packed.trace=PackedVgaTrace(4)
        memories=[bytearray(base.SIZE),bytearray(base.SIZE)]
        for dev,memory in zip((plain,packed),memories):
            dev.out(0x3C4,0x0F02,0x2D7);dev.out(0x3CE,0x0005,0xA02)
            dev.write(memory,0xA0003,0x96,0x6D7);dev.read(memory,0xA0003,0x202)
        self.assertEqual(plain.state(),packed.state());self.assertEqual(memories[0],memories[1])
        self.assertEqual(list(packed.trace),plain.trace);self.assertEqual(packed.trace[-1],plain.trace[-1])
        clone=copy.deepcopy(packed.trace);clone.clear()
        self.assertEqual(len(clone),0);self.assertEqual(list(packed.trace),plain.trace)
        with self.assertRaises(base.OracleFailure):packed.trace.append(('write',0,0,0))

if __name__=='__main__':unittest.main()
