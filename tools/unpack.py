"""Static decoder for the pinned PKLITE 1.03 extra/large VGALEMMI variant.

Derived from its own stub (PSP:0148..0357). This deliberately is not a generic
PKLITE implementation. No execution, snapshots, or initialized state is used.
"""
import struct
from common import ROOT, BUILD, sha, write_json

TARGET_SHA = '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d'
ASSET = ROOT / 'assets' / 'vgalemmi.exe'

def word(data, pos):
    return struct.unpack_from('<H', data, pos)[0]

class Stream:
    def __init__(self, data, pos):
        self.data, self.pos = data, pos
        self.bits, self.left = self.u16(), 16

    def byte(self):
        if self.pos >= len(self.data):
            raise ValueError('Truncated packed stream')
        b = self.data[self.pos]
        self.pos += 1
        return b

    def u16(self):
        return self.byte() | self.byte() << 8

    def bit(self):
        b = self.bits & 1
        self.bits >>= 1
        self.left -= 1
        # The original eagerly fetches a word while preserving carry, even if
        # the next token reads a literal byte instead of another control bit.
        if not self.left:
            self.bits, self.left = self.u16(), 16
        return b

def unpack(data):
    if sha(data) != TARGET_SHA:
        raise ValueError('EXE does not match the audited VGA target')
    fields = ('magic last_page pages relocations header_paragraphs min_extra '
              'max_extra ss sp checksum ip cs relocation_offset overlay').split()
    header = dict(zip(fields, struct.unpack_from('<14H', data)))
    # Relocated stub's CS:0210 points at original PSP:0358, file offset 02A8.
    table = data[0x2a8:0x2e6]
    s = Stream(data, 0x2f0)
    out = bytearray()
    tokens = dict(literals=0, matches=0, segment_markers=0)
    while True:
        if not s.bit():
            out.append(s.byte() ^ s.left)
            tokens['literals'] += 1
            continue
        b = (s.bit() << 1) | s.bit()
        if b < 2:
            b = (b << 1) | s.bit()
            if b:
                b = (b << 1) | s.bit()
                if b >= 5:
                    b = (b << 1) | s.bit()
            if b <= 12:
                length = table[b]
            else:
                b = ((b & 3) << 1) | s.bit()
                if b >= 5:
                    b = (b << 1) | s.bit()
                if b <= 12:
                    length = table[11 + b]
                else:
                    b = ((b & 3) << 1) | s.bit()
                    if b >= 5:
                        b = (b << 1) | s.bit()
                    length = table[22 + b]
                if length == 25:
                    extra = s.byte()
                    if extra == 255:
                        break
                    if extra == 254:
                        tokens['segment_markers'] += 1
                        continue
                    length += extra
        else:
            length = b
        high = 0
        if length != 2 and not s.bit():
            b = (s.bit() << 2) | (s.bit() << 1) | s.bit()
            if b >= 2:
                b = (b << 1) | s.bit()
                if b >= 8:
                    b = (b << 1) | s.bit()
                    if b >= 23:
                        b = (b << 1) | s.bit()
                        high = b & 0xdf
                    else:
                        high = table[38 + b]
                else:
                    high = table[38 + b]
            else:
                high = table[38 + b]
        distance = (high << 8) | s.byte()
        if distance == 0 or distance > len(out) or length < 2:
            raise ValueError(f'Invalid backreference at packed {s.pos:x}')
        for _ in range(length):
            out.append(out[-distance])
        tokens['matches'] += 1
        if len(out) > 0x100000:
            raise ValueError('Decompression size bound exceeded')
    relocation_start = s.pos
    relocs, segment = [], 0
    while True:
        count = s.u16()
        if count == 0xffff:
            break
        if count == 0:
            continue
        for _ in range(count):
            offset = s.u16()
            site = segment * 16 + offset
            if site + 2 > len(out):
                raise ValueError('Relocation outside static image')
            relocs.append(dict(segment=segment, offset=offset, linear=site))
        segment += 0xfff
    footer_offset = s.pos
    ss, sp, cs, ip = (s.u16() for _ in range(4))
    manifest = dict(schema=1, packed_sha256=sha(data), packed_size=len(data),
                    packed_mz=header, pklite_version='1.03', extra=True, large=True,
                    stream_offset=0x2f0, relocation_stream_offset=relocation_start,
                    footer_offset=footer_offset, consumed_bytes=s.pos,
                    trailing_bytes=len(data)-s.pos, image_size=len(out),
                    image_sha256=sha(out), entry=dict(cs=cs, ip=ip),
                    stack=dict(ss=ss, sp=sp), relocations=relocs, tokens=tokens)
    return bytes(out), manifest

def relocated(image, relocations, load_segment):
    result = bytearray(image)
    for r in relocations:
        site = r['linear']
        struct.pack_into('<H', result, site, (word(result, site) + load_segment) & 0xffff)
    return bytes(result)

def main():
    image, manifest = unpack(ASSET.read_bytes())
    BUILD.mkdir(exist_ok=True)
    (BUILD / 'canonical.bin').write_bytes(image)
    write_json(BUILD / 'unpack.json', manifest)
    print(f"Static image: {len(image)} bytes, SHA256 {sha(image)}")
    print(f"Entry {manifest['entry']}, stack {manifest['stack']}, relocations {len(manifest['relocations'])}")

if __name__ == '__main__':
    main()
