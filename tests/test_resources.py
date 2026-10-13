"""Static DAT decoder acceptance/rejection and reverse-bit ordering checks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import ROOT,read_json
from resources import decode_section,ReverseBits,sound_images

class ResourceTests(unittest.TestCase):
    def test_pinned_drivers(self):
        pins=read_json(ROOT/'metadata/sound-oracle.json')
        for name,(image,meta) in sound_images().items():
            self.assertEqual(meta,pins[name])
            self.assertEqual(len(image),meta['image_size'])

    def test_read_order_and_refill(self):
        bits=ReverseBits(bytes([0x81,0x06]),3)
        self.assertEqual(bits.read(3),3) # first three low bits:0,1,1
        self.assertEqual(bits.read(8),0x81)
        self.assertEqual(bits.checksum,0x87)
        with self.assertRaises(ValueError):
            bits.read(1)

    def test_invalid_containers(self):
        data=(ROOT/'assets/adlib.dat').read_bytes()
        bad_checksum=data[:1]+bytes([data[1]^1])+data[2:]
        bad_count=bytes([9])+data[1:]
        zero_size=data[:2]+bytes(4)+data[6:]
        oversized=data[:2]+bytes.fromhex('00010000')+data[6:]
        for bad in (data[:9],data[:-1],bad_checksum,bad_count,zero_size,oversized):
            with self.subTest(prefix=bad[:10].hex()),self.assertRaises(ValueError):
                decode_section(bad)

    def test_legacy_segments_are_not_conflated(self):
        records=read_json(ROOT/'metadata/legacy-seeds.json')['external']
        image=sound_images()['adlib'][0]
        driver=[r for r in records if r['segment']==0x2911]
        self.assertEqual(len(driver),16)
        for r in driver:
            sig=bytes.fromhex(r['signature']);off=r['offset']
            self.assertEqual(image[off:off+len(sig)],sig)
        self.assertEqual([(r['segment'],r['offset']) for r in records if r not in driver],[(0xf000,0xff53)])

if __name__=='__main__':
    unittest.main()
