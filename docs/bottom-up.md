# Bottom-up convergence from the ASM oracle

Pre2's transferable strengths are evidence-supported state names, contracts next
to the ASM, direct native calls on one memory image, and choosing the next region
by the uncertainty it would force into C. Its historical link modules and single
flowing ES model are specific to Pre2. Lemmings has loaded sound overlays,
protected execution views, several flowing segments and live stack aliases.

## Maintained source ownership

`src/program.asm` includes these files in unchanged physical image order, with
an end assertion after each code module. Every ledger symbol is also asserted.
These are reconstruction boundaries, not claims about historical linker modules.

| Inclusive image range | Source | Ownership status |
|---|---|---|
| 00000..01915 | entry_services.asm | Entry/service frame; protected views remain separate |
| 01916..01ED6 | resources.asm | Raw files, selection, special setup and DAT/cache cluster |
| 01ED7..03789 | game_code.asm | Mixed ownership remains provisional |
| 0378A..03943 | level_objects.asm | Record copy, interaction cells and coordinate collector |
| 03944..08237 | game_code_late.asm | Mixed ownership remains provisional |
| 08238..08342 | special_graphics.asm | Tested strip entries/shared tail |
| 08343..083BE | checksum.asm | Tested checksums, state and code/data overlap |
| 083BF..09A8F | code_tail.asm | Overlay storage, drawing code and unresolved spans |
| 09A90..143D9 | image_tail.asm | Data frame; UNKNOWN may contain executable code |

Shared tails can cross files. All encoding exceptions, UNKNOWN markers and
classifications remain unchanged. The bootstrap generator refuses to overwrite
the maintained modular layout. Refine the actual ASM and keep exact verification.

The contiguous 0378A..03943 object helpers now live in level_objects.asm,
included directly by program.asm at their original position with start/end assertions.
This groups the graphics-record copy, SS interaction rectangles and coordinate
collector while keeping their broader setup and drawing callers outside the module.
Record ownership and preserved quirks are documented in object-records.md.

## Resource and state handoff

`LoadSelectedLevelResources` (197D) reads an unchecked selection byte at DS:1F6B
through order bytes at 54EE. After wrapping decrement, the high nibble selects
the LEVEL filename group, bits1..3 select its section, and bit0 selects odd-table
overrides. The order table's extent and valid input domain remain unresolved.

The selected section fills `LoadedLevelRecord` at DS:0FCB. All 80 pinned sections
decode to 2,048 bytes and match bounded original/native decoding. Odd overrides
replace the first 24 bytes and last 32 bytes using a selected 56-byte slice.
Record bytes FE6/FE8 select normal/special graphics. Ground definitions load at
1B4B. Normal graphics use two DAT sections; VGASPEC feeds the already connected
1A7B metadata/RLE/strip/VGAGR chain. The 36B6/394F consumers still need object,
terrain, initialization and segment contracts.

The ledger now names these record fields, buffers, filenames and selector digits.
They are aliases in canonical memory. No converted records or shadow state were
introduced. Buffer names do not validate short reads, malformed indexes or aliases.

The object handoff at378A uses32 eight-byte definitions at0FEB..10EA and32
28-byte graphics slots at17CB..1B4A. A zero first definition word skips copying
and leaves the destination slot stale. The unchecked big-endian type word selects
a ground record with wrapped multiply/add; incoming DF still controls the copy.
These graphics slots end exactly where the ground load starts.

The five supplied ground files are1,056 bytes, ending at1F6A when loaded at1B4B.
That span includes the special metadata coordinates1F0B..1F6A: their ownership
overlaps the normal ground input. The ledger's0x1000 GroundResourceBuffer size is
the original maximum read request, not an allocation boundary. Longer/shorter
providers may affect adjacent state; neither ASM nor C adds a corrected limit.

## Dependency-driven working loop

```powershell
.venv\Scripts\python.exe tools\graph.py LoadSelectedLevelResources --tree --depth 3
.venv\Scripts\python.exe tools\graph.py LoadSelectedLevelResources --bottom-up
.venv\Scripts\python.exe tools\where.py WriteDecimalByteDigits --disasm 24
```

The graph uses fresh static edges: branches/shared tails form bodies, calls form
dependencies. Native views use ledger C ranges and expose exits, unported calls
and device/IRQ sites. Pending translation order stops at native domains, while
printing their open seams. Decoded leaves and C presence are investigation
evidence, not readiness proofs. Syntactic operand tags do not establish DS/ES/SS
ownership. Full protection and sound frontiers retain their separate inventories.

The independent leaf `WriteDecimalByteDigits` (4BC2..4BE6) is now native. AL
produces three ASCII digits, incoming AH is ignored, AX returns tens/units ASCII,
and SI advances two. Writes go forward even with DF set. The original-only
contract suite covers 260 cases, all 19 sites and four branch edges, comparing
whole RAM, registers and defined flags. That suite remains separate from C coverage.
The native suite adds 270 comparisons, including physical wrap and controlled live
return aliases, with three compiled mutants detected; see decimal-digits.md.

The 197D caller now composes that leaf and native file/decoder/raw cores directly:
59 cases cover 108 caller/560 integrated sites, nine caller edges and three mutants.
Live saved order/counter/DS words, unchecked closes, in-place decoding and paired
original resources are verified; see resource-select.md for fatal/platform seams.
The 378A graphics-record copy and 389F coordinate collector are also native,
with 131/159 cases and the live-copy/default-coordinate quirks documented in
object-records.md. Recover the 37C2/3839 live SS interaction-cell contracts next,
then close the remaining 36B6/394F setup dependencies before translating those
parents. For each cluster, resolve the state/table/target
uncertainty that would force guessing, document its live segment/flag contract,
verify exact ASM, and translate with logical parameters and direct native calls.
Keep register adapters at the oracle boundary. Recheck parents when dependencies
connect, using bounded original comparisons and independent data/device checks.

The pass exposed a static extractor gap: zero initial bits are legal. The original
CH increment/decrement causes immediate backward refill, while the seeded last
payload byte still joins the checksum. Thirteen real level sections use it. The
extractor now accepts zero, with a known-answer test and all 80 level records in
the original/native/static comparison. Original instructions and native decoder
behavior were unchanged.

Full classification, native devices, IRQ scheduling, gameplay and SDL3 remain
open. No original game was booted, and assets/neighbors remain untouched.
