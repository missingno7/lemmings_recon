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

    def test_known_indirect_target_does_not_close_its_domain(self):
        hints=dict(entries=[{'offset':0}],regions=[],code_limit=4,
                   indirect_transfers=[dict(address=0,bytes='ffd0',targets=[3],
                       evidence='Constructed callback slot',closure='Aliased pointer domain pending')])
        result=discover(bytes.fromhex('ffd0c3c3'),hints,{'accepted':[]})
        known=[e for e in result['edges'] if e['kind']=='indirect_call']
        self.assertEqual(len(known),1)
        self.assertEqual(known[0]['target'],3)
        self.assertTrue(known[0]['resolved'])
        self.assertFalse(known[0]['target_domain_complete'])
        self.assertEqual(result['unresolved'][0]['known_targets'],[3])
        self.assertFalse(result['unresolved'][0]['target_domain_complete'])
        hints['indirect_transfers'][0]['bytes']='ffe0'
        with self.assertRaises(ValueError):
            discover(bytes.fromhex('ffd0c3c3'),hints,{'accepted':[]})

    def test_external_iret_chain_has_explicit_conditional_return(self):
        hints=dict(entries=[{'offset':0}],regions=[],code_limit=5,
            external_transfers=[dict(address=0,bytes='ff2e0000',pointer={'frame':0,'offset':0},
                                     return_target=4,evidence='Constructed saved ISR pointer',contract='IRET through supplied frame')])
        result=discover(bytes.fromhex('ff2e0000cf'),hints,{'accepted':[]})
        self.assertEqual(result['unresolved'],[])
        external=[e for e in result['edges'] if e['kind']=='external_interrupt_chain']
        self.assertEqual(len(external),1)
        self.assertIsNone(external[0]['target'])
        returns=[e for e in result['edges'] if e['kind']=='external_interrupt_return']
        self.assertEqual(returns[0]['target'],4)
        self.assertTrue(returns[0]['resolved'])
        self.assertTrue(returns[0]['contract'])

    def test_complete_byte_partition(self):
        result=analyze()
        end=0
        for r in result['regions']:
            self.assertEqual(r['start'],end)
            self.assertGreater(r['end'],r['start'])
            end=r['end']
        self.assertEqual(end,82906)
        self.assertGreater(result['metrics']['unresolved_byte_runs'],0)

    def test_runtime_modified_target_is_not_decoded(self):
        image=bytes.fromhex('eb00 c3')
        hints=dict(entries=[{'offset':0}],regions=[{'start':2,'end':3,'class':'runtime_modified_code'}],
                   code_limit=3,blocked_decode_ranges=[{'start':2,'end':3,'evidence':'fixture transformation'}])
        result=discover(image,hints,{'accepted':[]})
        self.assertEqual([i['address'] for i in result['instructions']],[0])
        self.assertEqual(result['unresolved'][0]['kind'],'runtime_modified_target')
        self.assertFalse(result['edges'][0]['resolved'])

    def test_protection_interrupt_stops_static_fallthrough(self):
        hints=dict(entries=[{'offset':0}],regions=[],code_limit=3,
                   runtime_frontiers=[{'address':0,'evidence':'fixture INT3 changes return code'}])
        result=discover(bytes.fromhex('cc90c3'),hints,{'accepted':[]})
        self.assertEqual([i['address'] for i in result['instructions']],[0])
        self.assertEqual(result['unresolved'][0]['continuation'],1)

if __name__=='__main__':
    unittest.main()
