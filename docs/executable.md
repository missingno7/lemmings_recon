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
4. **Initialized runtime memory:** NOT an oracle input. With DF clear, startup clears DS:0000..2011,
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
- Explicit installations cover INT24 at 18F8, keyboard 16D4, game/menu timer
  17C7/4C47, mouse far callback 0F6F and private IRQ wrapper 0F70. Two saved INT08
  chains now have explicit external IRET edges and bounded caller-tail checks.
  DOS/device/provider and alias contracts remain open; see interrupts.md.
- ADLIB.DAT and TANDYSND.DAT are now independently extracted and byte-exact ASM
  images (22,125 and 21,702 bytes). All 16 legacy AdLib signatures at 2911 match;
  the seventeenth external signature is F000:FF53 firmware/environment code.
  Their separate code/data and CFG frontier is in sound-drivers.md.
- MAIN.DAT section 5 is a further executable component: 758 PC-speaker bytes loaded
  over main 08420..08715 before INT60 is installed at relocated 0842:0182. Its
  source payload and stored main zeros are independently reconstructed and verified.
  The complete known component total is now 127,491 ASM bytes; it counts both
  initial storage and the replacement payload. See interrupts.md for dispatch gaps.
- Main 066C invokes INT3 installed at 0DB3 via 0659+075A. The handler negates 59 bytes
  at 0DFF..0E39, installs that address as INT1, changes saved TF/IF, and modifies
  forthcoming instruction words. Separate state-specific ASM and CFG now recover
  372 stream and 29 INT1 instruction sites, independently checked using original
  handlers. Raw decoding remains blocked at these transitions; see protection.md.
  The canonical acceptance image remains unchanged.

## Alternative paths inventory (freeze criterion 1)

Every original alternative stays in the specification even though the primary
native port is VGA + AdLib. Contracts live beside the ASM at the listed entries;
this index only names each path, its selector and its open boundary.

| Path | Selector / entry | Open boundary |
|---|---|---|
| Controller choice and joystick | input menu -> 43CE; callbacks 4334 (low) / 4359 (high), axis 4386, calibration 4A73/4A8B | real game-port timing; 42A5 callback lifetime |
| Mouse / keyboard input modes | menu keys -> 4ABD (mode 0, INT33 4252) / 4AB5 (mode 2); `/n` or no mouse -> 0F64 | INT33 equivalence; 25A0 writers |
| Display probes | 1407 over records 2013: 1410 combination, 1462 EGA, 1490 color CRTC, 14A0 mono variants; finalization 1523/14FA | BIOS/port equivalence; 1407 traversal domain |
| BIOS video modes | startup 106E/00BB (03/0D), game 0FB2, menu 4BE7, restore 0FF8 | literal paths only; no alternate renderer proven |
| Palette modes | `/e` -> 1F7C=2 attribute palette, `/v` or prompt -> 4 DAC palette | 131A/1322 candidates without incoming keys |
| Raster/timer options | `/2` `/4` (2011 word), `/x` `/d` (200E=FF: foreground raster sync), `/p` `/m` `/o` `/n` `/i` | real timing; 1194 marker overlap on 2011/2013 |
| AdLib driver | 054E: allocate 0567, INT61 at AX:0000, load adlib.dat, detect | allocation/vector lifetime |
| Tandy driver | 05B4 after failed AdLib and BIOS page probe 060C | state at 5958 beyond its allocation; dangling INT61 |
| PC-speaker driver | 05FC fallback (`/a`, allocation failure, no AdLib/Tandy); MAIN.DAT section 5 over 8420..8715, INT60 0842:0182 | no INT60/INT61 restore recovered; 0181/tail |
| Protection media probe | 062B: FAT F8 counter wrapper 0E66 or direct 063E | protected stored bytes, alternate BIOS/DOS selectors |

Native substitutions for these paths (unbound joystick, muted drivers, fixed
BIOS answers, media policy) omit or alter original behavior; see AGENTS.md.
