"""Regression checks for canonical identity and non-sweeping discovery."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import ROOT,read_json
from unpack import ASSET,unpack,relocated,Stream
from explore import discover,analyze

class StaticTests(unittest.TestCase):
    def test_pinned_extraction(self):
        image,meta=unpack(ASSET.read_bytes())
        self.assertEqual(meta,read_json(ROOT/'metadata/oracle.json'))
        self.assertEqual(len(image),82906)
        self.assertEqual(meta['consumed_bytes'],len(ASSET.read_bytes()))

    def test_reject_changed_target(self):
        original=ASSET.read_bytes()
        for bad in (original[:-1],original[:100]+bytes([original[100]^1])+original[101:]):
            with self.assertRaises(ValueError):
                unpack(bad)

    def test_relocation_wrap_and_unrelated_bytes(self):
        original=b'\x41\xfe\xff\x99'
        self.assertEqual(relocated(original,[{'linear':1}],3),b'\x41\x01\x00\x99')
        self.assertEqual(original,b'\x41\xfe\xff\x99')

    def test_bit_refill_is_eager(self):
        s=Stream(b'\x00\x80\x34\x12\xab',0)
        self.assertEqual([s.bit() for _ in range(16)],[0]*15+[1])
        self.assertEqual(s.pos,4)
        self.assertEqual(s.left,16)
        self.assertEqual(s.byte(),0xab)

    def test_recursive_discovery_does_not_sweep_jump_gap(self):
        image=bytes.fromhex('eb02 9090 c3')
        result=discover(image,dict(entries=[{'offset':0}],regions=[],code_limit=len(image)),{'accepted':[]})
        self.assertEqual([i['address'] for i in result['instructions']],[0,4])
        self.assertEqual(result['regions'][1],dict(start=2,end=4,classification='unresolved'))

    def test_indirect_is_reported_not_guessed(self):
        result=discover(bytes.fromhex('ffd0c3'),dict(entries=[{'offset':0}],regions=[],code_limit=3),{'accepted':[]})
        self.assertEqual(result['unresolved'][0]['kind'],'indirect_or_far_transfer')
        self.assertEqual(result['unresolved'][0]['address'],0)

    def test_complete_byte_partition(self):
        result=analyze()
        end=0
        for r in result['regions']:
            self.assertEqual(r['start'],end)
            self.assertGreater(r['end'],r['start'])
            end=r['end']
        self.assertEqual(end,82906)
        self.assertGreater(result['metrics']['unresolved_byte_runs'],0)

if __name__=='__main__':
    unittest.main()
