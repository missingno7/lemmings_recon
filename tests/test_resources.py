"""Static DAT decoder acceptance/rejection and reverse-bit ordering checks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import ROOT,read_json
from resources import decode_section,ReverseBits,sound_images,section_spans

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

    def test_zero_initial_bits_refills_but_checksums_seed_byte(self):
        bits=ReverseBits(bytes([0x81,0x06]),0)
        self.assertEqual(bits.read(8),0x81)
        self.assertEqual(bits.checksum,0x87)
        with self.assertRaises(ValueError):bits.read(1)

    def test_all_pinned_level_sections_are_2048_bytes(self):
        count=zero=0
        for path in sorted((ROOT/'assets').glob('level*.dat')):
            data=path.read_bytes()
            for start,end in section_spans(data):
                image,meta=decode_section(data[start:end])
                self.assertEqual(len(image),2048)
                count+=1;zero+=data[start]==0
        self.assertEqual((count,zero),(80,13))

    def test_legacy_segments_are_not_conflated(self):
        records=read_json(ROOT/'metadata/legacy-seeds.json')['external']
        image=sound_images()['adlib'][0]
        driver=[r for r in records if r['segment']==0x2911]
        self.assertEqual(len(driver),16)
        for r in driver:
            sig=bytes.fromhex(r['signature']);off=r['offset']
            self.assertEqual(image[off:off+len(sig)],sig)
        self.assertEqual([(r['segment'],r['offset']) for r in records if r not in driver],[(0xf000,0xff53)])

    def test_main_section_boundary_is_executable_overlay_source(self):
        data=(ROOT/'assets/main.dat').read_bytes()
        spans=section_spans(data)
        self.assertEqual(len(spans),7)
        self.assertEqual(spans[5],(0xd17a,0xd419))
        image,meta=sound_images()['pcspeaker']
        self.assertEqual(len(image),758)
        self.assertEqual(image[0x182],0xfb)
        self.assertEqual(meta['load_frame']*16+meta['entry_offset'],0x85a2)
        with self.assertRaises(ValueError):section_spans(data[:-1])

if __name__=='__main__':
    unittest.main()
