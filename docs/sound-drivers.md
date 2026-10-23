# Static external sound images

The original routine at main CS:054E installs INT61 at allocated-segment:0000
(0576..057B), loads `adlib.dat` through 1B79 with DS=ES=the allocated segment,
SI=DI=0, and invokes its AH=1 detection service. The fallback reloads `tandysnd.dat`
at the same destination (05BD..05CA). Both are executable DAT assets. The main
loader allocates 0567 paragraphs (22,128 bytes); the driver load segment is a runtime
DOS allocation result, not intrinsically 2911h.

## Reproducible extraction and identity

tools/resources.py statically implements the original decoder at 1BAF..1CB8.
The ten-byte header contains initial valid bits, XOR checksum, big-endian decoded
length and packed section length. Bits are read from the last payload byte toward
the first, LSB first within a byte, with each requested field accumulated MSB first.
Output is written backward. Six token forms are preserved: literals of 1..8 or
9..264 bytes; matches of length 2/3/4 with 8/9/10-bit distances; variable match length
1..256 with a 12-bit distance. Encoded distances are incremented by one. Reverse
overlap copies read already decoded higher addresses. The original bit reader XORs
each fetched payload byte into DH and the final AND DH,DH reports checksum success.

This extractor rejects lengths above 65535 and invalid token bounds. The original
uses only the low size words in this path; apparent 32-bit header fields do not
establish support for larger sections. Rejection policy is tooling validation,
not a modification of the original decoder or a claim about malformed-file behavior.

| Image | Packed bytes | Static bytes | SHA256 of decoded image |
|---|---:|---:|---|
| AdLib | 12,988 | 22,125 | `ad4f33eb383c60b5a67945987f27580fc0540e38558d4c158efe1a672db5f490` |
| Tandy | 12,399 | 21,702 | `20214a92f2466945c108f0ba1a36522d6542f2e34aadbb72027492051da3c659` |

metadata/sound-oracle.json pins packed and decoded identities separately. Each
driver has its own hints, region partition, relative symbol ledger, and encoding
exceptions. src/sound contains maintained NASM sources; tools/sound.py checks every
byte and each named label without regenerating them. There is no MZ header and no
load-segment fixup table for these extracted sections. No initialization is needed
to reproduce the 16 legacy AdLib signatures, all of which match exactly.

Correction to the first milestone: the legacy list has 17 *external* records, but
only 16 belong to 2911h. The other is F000:FF53 with an IRET signature, a separate
firmware/environment lead. It must not inflate the sound-driver routine inventory.

tests/sound_unpack.py enters only original main CS:1BAF. The fixture supplies the
DOS read service and disables the optional cached-file path. At two destination
segments with different memory poison, the original performs exactly two reads
(10-byte header, then payload), returns to the sentinel, reports a valid checksum,
and matches every output byte. These four extraction checks execute 145 main-image
instructions; no driver service or game startup is executed. They are not C tests.

## Dispatch and remaining proof obligations

AdLib entry 0000 dispatches AH=0..5. Recognized services include update 0115,
hardware detection 00A3, reset 003A and three byte-setting IRET paths. OPL writes go
through 0559, which preserves the explicit IN delays and takes its base from 08A3.
The 27 reset register/value words at 006D..00A2 are a proven data table.

AdLib command dispatch 01EA indexes table 03EA using doubled AL. Eight visible
entries at 03EA..03F9 cover commands 80..87. However the preceding comparisons allow
80..AF; commands 88..AF would read pointers from following instruction bytes. The
table is not silently expanded into code, and no bounds check or bug fix is added.
The legitimate domain is closed: the shipped streams and every main-image INT61
request reach 01EA only with 80..82 and 84..87. Tokens 88..AF are a characterized
corrupted-control escape (they need an externally written stream byte or pointer,
a song header read with DF=1, for which no producer exists, or a raw engine
entry); a native port reports them as an explicit runtime failure. The complete
engine, song, instrument and command specification is the header of
src/sound/adlib.asm.

Tandy dispatch 02BB indexes 076B. Twenty-four visible entries at 076B..079A cover
80..97; control flow allows 80..9F, so 98..9F remain unresolved. The table adds targets
that entry-only recursive descent misses. Both drivers still contain unclassified
tables, music/effect streams, and data. Out-of-image accesses such as Tandy 0629's
write to 5958 require allocation/state analysis; do not add a shadow variable or
assume the static image length bounds every runtime access.

Both AdLib/Tandy entry dispatcher prefixes and six command3/4/5 latch setters
now have scoped native C verification:106 unique bytes,65 sites and27 edges.
The766 fixtures cover all256 AH values for both drivers, live stack/IRET and
VGA aliases, with ten completed mutants. AH6..FF preserves five DEC AH
operations and actual IRET. See sound-latches.md.

The complete AdLib engine (update 0115, detection 00A3, reset 003A, stream
commands, instruments, pitch, song/effect requests and the OPL write path 0559)
is translated in c/adlib_engine.c over the driver's own memory: all 1,329 decoded
AdLib bytes are in C (UNKNOWN 0014 and 05A0..05A7 excluded). `lmn_adlib_int61_adapter`
composes the existing dispatcher with the service bodies. OPL access goes through
an explicit port boundary (`LmnOplPorts`): each register write is OUT base,reg;
12 IN base; OUT base+1,value; 47 IN base+1, with the base reread from [08A3].
Tokens 88..AF return an explicit stream-escape status. tests/adlib_engine.py
compares original and C per INT61 call (memory, ordered RAM/port events,
registers and flags) over shipped songs and effects, detection, reset and
constructed stream states. A native OPL backend must keep the original
spacing of the writes: the delay reads in 0559 are what separate a key-off from
the following key-on, so rendering all writes of one update at a single instant
silences every retriggered note (host/README.md, Sound). It feeds the (register,
value) writes to a synthesis core and calls AH=00 at the game timer cadence (main 1872,
plus once after each AH=03 request). The Tandy engine remains untranslated.

Further installation analysis identified MAIN.DAT section 5 as a 758-byte
PC-speaker component loaded over main zero storage at relative frame 0842. It now
has a separate exact source and inventory under src/sound/pcspeaker.asm and
metadata/pcspeaker-*. See interrupts.md for its load, entry, mutable dispatch and
unresolved trailing bytes. The known executable-component inventory has four images.

Three closed PC-speaker helpers now have verified C11 cores: 165 bytes, 60
instruction sites, 335 differential cases and three compiled mutations detected.
The dispatcher remains untranslated. See pcspeaker.md for preserved sound behavior,
flag/port contracts and the remaining target-domain obligations.
