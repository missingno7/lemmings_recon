"""C port of the pinned, static PKLITE decoder."""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cbuild
from bounded_process import temporary_build_directory

ASSET = ROOT / 'assets' / 'vgalemmi.exe'
OK, WRONG_IDENTITY, MALFORMED, CAPACITY = range(4)


class Header(ctypes.Structure):
    _fields_ = [('mz', ctypes.c_uint16 * 14),
                ('entry_cs', ctypes.c_uint16), ('entry_ip', ctypes.c_uint16),
                ('stack_ss', ctypes.c_uint16), ('stack_sp', ctypes.c_uint16),
                ('relocation_stream_offset', ctypes.c_size_t),
                ('footer_offset', ctypes.c_size_t), ('consumed_bytes', ctypes.c_size_t)]


@unittest.skipUnless(ASSET.is_file(), 'assets/vgalemmi.exe is absent; local decoder comparison skipped')
class PkliteUnpackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = temporary_build_directory(prefix='pklite-unpack-', parent=ROOT / 'build')
        path = Path(cls.directory.__enter__()) / 'pklite_unpack.dll'
        cbuild.build(path, cluster='pklite_unpack')
        cls.dll = ctypes.CDLL(str(path))
        cls.unpack = cls.dll.lmn_pklite_unpack
        cls.unpack.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_uint16), ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(Header)]
        cls.unpack.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        if sys.platform == 'win32' and getattr(cls, 'dll', None):
            ctypes.windll.kernel32.FreeLibrary(ctypes.c_void_p(cls.dll._handle))
            cls.dll = None
        cls.directory.__exit__(None, None, None)

    def call_c(self, data, image_capacity=0x100000, relocation_capacity=4096):
        source = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        image = (ctypes.c_uint8 * (image_capacity + 16))()
        relocations = (ctypes.c_uint16 * relocation_capacity)()
        image_size = ctypes.c_size_t()
        relocation_count = ctypes.c_size_t()
        header = Header()
        ctypes.memset(ctypes.byref(image, image_capacity), 0xA5, 16)
        status = self.unpack(source, len(data), image, image_capacity,
                             ctypes.byref(image_size), relocations, relocation_capacity,
                             ctypes.byref(relocation_count), ctypes.byref(header))
        return status, bytes(image[:image_size.value]), list(relocations[:relocation_count.value]), header, image

    def test_image_relocations_and_header_match_python_oracle(self):
        import unpack as oracle
        packed = ASSET.read_bytes()
        expected_image, manifest = oracle.unpack(packed)
        status, image, relocs, header, _ = self.call_c(packed)
        self.assertEqual(status, OK)
        self.assertEqual(image, expected_image)
        self.assertEqual(relocs, [item['linear'] for item in manifest['relocations']])
        self.assertEqual(list(header.mz), list(manifest['packed_mz'].values()))
        self.assertEqual((header.entry_cs, header.entry_ip),
                         (manifest['entry']['cs'], manifest['entry']['ip']))
        self.assertEqual((header.stack_ss, header.stack_sp),
                         (manifest['stack']['ss'], manifest['stack']['sp']))
        self.assertEqual(header.relocation_stream_offset, manifest['relocation_stream_offset'])
        self.assertEqual(header.footer_offset, manifest['footer_offset'])
        self.assertEqual(header.consumed_bytes, manifest['consumed_bytes'])

    def test_identity_rejection_and_output_bounds(self):
        packed = ASSET.read_bytes()
        damaged = bytearray(packed)
        damaged[0x2f0] ^= 1
        status, _, _, _, guarded = self.call_c(bytes(damaged))
        self.assertEqual(status, WRONG_IDENTITY)
        self.assertEqual(bytes(guarded[-16:]), b'\xa5' * 16)
        status, _, _, _, _ = self.call_c(packed[:-1])
        self.assertEqual(status, WRONG_IDENTITY)

        status, _, _, _, guarded = self.call_c(packed, image_capacity=32)
        self.assertEqual(status, CAPACITY)
        self.assertEqual(bytes(guarded[32:]), b'\xa5' * 16)
        status, _, _, _, _ = self.call_c(packed, relocation_capacity=1)
        self.assertEqual(status, CAPACITY)


if __name__ == '__main__':
    unittest.main()
