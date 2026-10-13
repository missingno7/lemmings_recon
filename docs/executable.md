# Canonical executable and load model

Target: locally supplied `assets/vgalemmi.exe`, 32,749 bytes, SHA256
`5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d`.
This matches both the legacy boot manifest and forged game manifest. The complete
55-file local inventory and matching legacy file paths are in metadata/inputs.json.
Historical distribution provenance is unknown; local matching copies are not proof
of an original retail release. Assets are private and gitignored.

## Four different representations

1. **Packed disk file:** 80-byte MZ header, zero DOS relocations, entry FFF0:0100
   relative to the load segment (physically its first image byte), SS:SP=07FF:0400.
   Minimum extra allocation 10F4 paragraphs, maximum FFFF. No overlay or trailing
   bytes. Descriptor bytes 03 31 identify PKLITE 1.03 with extra/large flags.
2. **Static decompressed image:** 82,906 bytes, image-relative entry 0000:0000,
   SS:SP=143E:4AF4, SHA256
   `b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e`.
   It has not undergone relocations, initialization, BIOS calls or game logic.
3. **Loaded image:** copy static bytes to `load_segment*16`, then add load_segment
   modulo 65536 to each of the 63 little-endian words listed in oracle.json, in
   recorded order. Canonical load 1010 gives code 1010, DS frame 19B9 and stack 244E.
   The decoder's relocated output is independently checked at loads 1010,1213,2345.
4. **Initialized runtime memory:** NOT an oracle input. Startup clears DS:0000..2011,
   installs vectors, patches code state and accesses devices. Memory beyond the
   static image and the PSP have separate initialization contracts. The legacy
   boot image has intentionally poisoned code and is not usable as static source.

All addresses below are hex. The static image ends at 143DA (exclusive); stack
frame 143E begins six bytes later and extends beyond the disk image. Its initial
contents are unspecified. DS frame 09A9 starts at 09A90. This is a provisional
code/data partition inferred from startup's relocated segment operand, not proof
that no executable bytes exist in the rest of the image.

## Decoder derived from the original stub

tools/unpack.py implements only this pinned variant. Packed stream starts at file
02F0. Control bits are LSB first in 16-bit words; the stub eagerly refills on the
last consumed bit. Literal bytes are XORed with the remaining-bit count. Huffman
length/distance tables are read from the original stub at file 02A8. Backreferences
copy forward with overlap. Extended lengths FE/FF mark segment rollover/end.
Segment rollover changes real-mode addressing, not the linear decoded byte stream.

The relocation stream begins at file 07F63. A word count is followed by that many
word offsets in the current relocation frame, initially 0000. Nonzero groups advance
the frame by 0FFF paragraphs. Zero retries the same frame; FFFF terminates. This file
contains 63 fixups in its first group. Footer at 07FE5 gives SS,SP,CS,IP (four words),
ending exactly at EOF. No original unpacked MZ header is present in extra mode.

The acceptance target is the raw static image plus footer and relocation semantics;
we do not invent an original MZ header or replicate PKLITE compressor output.
tools/check_unpack.py executes only the packed stub, with a 2,000,000-instruction
budget and stops before the first original game instruction. All 82,906 bytes and
CS:IP/SS:SP/DS/ES match at three loads with different initial memory poison. No bytes
are masked and no initialized game snapshot is involved.

## Known special cases

- Startup calls 8343 twice. It XORs CS:188F..1898, a ten-byte window starting inside
  the CALL operand at 188E, and stores results at 83B8/83BD. This is a proven overlapping
  code/data interpretation; source and region inventory preserve it.
- 8363..83B6 is a coherent incremental checksum routine sharing 83B9..83BC. Its current
  static callers are unknown; decoding and testing it does not establish reachability.
- INT24 vector 18F8 is explicit at 008A. Timer/keyboard handler leads 16D4/17C7 and
  chained far vectors require further contract work. DOS and hardware edges remain
  platform boundaries, not unexplained direct branch targets.
- External code at historical segment 2911 has 17 legacy entry signatures. ADLIB.DAT
  is compressed executable content according to legacy evidence; extraction and
  independent binding of every driver entry remain required. It is not counted as
  reconstructed merely because the main EXE is byte-exact.
