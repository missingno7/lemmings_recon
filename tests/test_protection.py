"""State-specific static closure and representation-boundary regressions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import ROOT,read_json
from unpack import unpack,ASSET,relocated
from protection import derive,discover_stream,decode_word

class ProtectionTests(unittest.TestCase):
    def test_pinned_views_and_complete_handler(self):
        image,view,handler,stream,rows=derive()
        self.assertEqual(len(handler),59)
        self.assertEqual(sum(r['size'] for r in rows),59)
        self.assertEqual(bytes((-b)&255 for b in handler),image[0xdff:0xe3a])
        self.assertEqual(rows[0]['mnemonic'],'sti')
        self.assertEqual(rows[-1]['mnemonic'],'iret')
        self.assertEqual(stream,read_json(ROOT/'metadata/protection-cfg.json'))
        self.assertNotEqual(view,image)

    def test_overlap_requires_separate_execution_views(self):
        image,view,_,stream,_=derive()
        # Decoding the first word also changes the following instruction byte.
        word=decode_word(image,0x66d).to_bytes(2,'little')
        self.assertEqual(word,b'\x50\xe9')
        self.assertEqual(view[0x66d:0x671],b'\x50\xe8\x00\x00')
        self.assertNotEqual(word,view[0x66d:0x66f])
        self.assertEqual([r['address'] for r in stream['instructions'][:3]],[0x66d,0x66e,0x671])

    def test_disk_services_have_explicit_tf_transitions(self):
        stream=derive()[3]
        toggles=[(e['source'],e['state'],e['target'],e['target_state'])
                 for e in stream['edges'] if e['kind']=='protection_toggle']
        self.assertEqual(set(toggles),{
            (0x96f,'tf_on',0x970,'tf_off'),(0xd9e,'tf_on',0xd9f,'tf_off'),
            (0xda1,'tf_off',0xda2,'tf_on'),(0xda3,'tf_on',0xda4,'tf_off'),
            (0xda9,'tf_off',0xdaa,'tf_on'),(0xdab,'tf_on',0xdac,'tf_off'),
            (0xdb1,'tf_off',0xdb2,'tf_on')})
        services=[e for e in stream['edges'] if e['kind']=='platform_interrupt']
        self.assertEqual({e['vector'] for e in services},{0x13,0x25,0x26})
        self.assertTrue(all(e['state']=='tf_off' and e['return_contract'] for e in services))
        covered={p for r in stream['instructions'] for p in range(r['address'],r['address']+r['size'])}
        self.assertFalse(covered.intersection(range(0x98c,0xd9e)))

    def test_relocations_do_not_change_protection_words(self):
        image,oracle=unpack(ASSET.read_bytes())
        original=discover_stream(image)
        self.assertFalse(any(0x66b<=r['linear']<0xe66 for r in oracle['relocations']))
        for seg in (0x1010,0x1213,0x2345):
            self.assertEqual(discover_stream(relocated(image,oracle['relocations'],seg)),original)

if __name__=='__main__':unittest.main()
