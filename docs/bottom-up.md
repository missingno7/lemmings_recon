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
| 03944..0796E | game_code_late.asm | Mixed ownership remains provisional |
| 0796F..07A59 | minimap.asm | Column, row and population sample contracts |
| 07A5A..08237 | game_code_late_tail.asm | Mixed ownership remains provisional |
| 08238..08342 | special_graphics.asm | Tested strip entries/shared tail |
| 08343..083BE | checksum.asm | Tested checksums, state and code/data overlap |
| 083BF..08821 | code_tail.asm | Overlay storage, layout setter and unresolved spans |
| 08822..09A8F | planar_drawing.asm | Planar renderer, dispatch, row preparation and clip/dirty leaves |
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
with 265/159 comparisons and the live-copy/default-coordinate quirks documented in
object-records.md. The 37C2/3839 SS cell writers are also native, verified in
123/386 cases. Their four-call 376A setup span passes 105 integrated cases with
explicit normal/changed-return boundaries; see interaction-cells.md. Close the
4DF8/8808 VGA-clear/layout contracts and remaining 36B6/394F dependencies before translating those
parents. For each cluster, resolve the state/table/target
uncertainty that would force guessing, document its live segment/flag contract,
verify exact ASM, and translate with logical parameters and direct native calls.
Keep register adapters at the oracle boundary. Recheck parents when dependencies
connect, using bounded original comparisons and independent data/device checks.

The graphics-copy gate includes131 null-bus and134 raster-bus comparisons of
the same56-byte span. Its bus-aware core preserves original access/flag order,
live PUSH/POP/RET and independent VGA plane/readback effects. This supplies the
copy dependency for the statically mapped397A..39CD object-drawing suffix;
the suffix and the complete394F parent remain untranslated. See
object-graphics-bus.md and object-drawing-frontier.md.

The pass exposed a static extractor gap: zero initial bits are legal. The original
CH increment/decrement causes immediate backward refill, while the seeded last
payload byte still joins the checksum. Thirteen real level sections use it. The
extractor now accepts zero, with a known-answer test and all 80 level records in
the original/native/static comparison. Original instructions and native decoder
behavior were unchanged.

Full classification, native devices, IRQ scheduling, gameplay and SDL3 remain
open. No original game was booted, and assets/neighbors remain untouched.

The 4DF8 VGA clear and 8808 layout setter now feed native 368E/36AD callers.
They operate on live SS mirrors, device planes, DS layout fields and original
near/far CALL frames. See level-drawing.md for changed-return exits and the
explicit Unicorn RETF observation limits before connecting broader drawing code.

The closed 796F..7A59 minimap cluster now has its own flat ASM module and
direct native column/row/sample cores. Its CS scratch window, live SS saves,
signed column update, DF-sensitive clear and VGA compare/care contract are
documented in minimap.md. The surrounding modules retain their provisional
ownership and UNKNOWN classifications.

The far drawing entry 8822 now exposes a scoped native preparation continuation
at 882D, with direct clipping 9967 and dirty-cell 9A15 children. The scoped API
gives the 49-byte span its own exits at 885E/88AB. Live source pitch/extent/skips
and saved CH names belong to the ledger. Its tests consume original-prologue state and keep those seven sites
outside those C reports. The preparation-only tests retain their historical
scope; see drawing-inputs.md.
The complete normal-entry connection is described below.

The 8822..9A8F planar family now lives in planar_drawing.asm, included directly
between the unchanged code-tail and data-frame modules. Destination geometry
and dispatch at 885E/939E compose with four native source-row prefixes. Their
77/236/744 cases preserve live shift/pitch/page words, packed counts, reversed
cursors and control changed by dirty or source-row stores. The preparation-only
suites execute the original 8822 prologue separately.
Their prologue evidence is excluded from those C reports; see drawing-plan.md.

The aligned opaque 983B..9966 body now has a native core and live far-return
adapter. Its 55 body/776 connection cases check all four plane passes, ordered
latch reads and mirrored ports, IF/DF/count wrap and live DS/SS frames. Two
UNKNOWN NOP bytes stay outside C accounting; the 988B shared entry retains
separate incoming-state obligations. The older connection keeps prologue
execution evidence separate. See aligned-opaque.md and drawing-render.md.

The default aligned masked 93F6 body now has its own logical C API. Its BX mask
cursor advances forward even with DF set, and its later passes use VGA logical OR.
The general preparation/drawing API composes both default aligned bodies while
retaining its effect/shift seams and live SS control aliases. See aligned-masked.md
and drawing-render.md for tested scopes, original far returns and bounded guards.

All four other aligned bodies now have native cores: 953E protection, 969C
read-mask and 9737/97A4 mask effects. Their 21/17/52 standalone cases establish
live segment/stack behavior, VGA comparison/latch ordering and the original
effect cursor asymmetry. The new all-aligned API directly composes preparation
and all six bodies in 226 cases. It requires an explicit byte OUT/IN provider
to enter 969C; without one that continuation remains visible. The older APIs
retain their scopes. UNKNOWN 9659 stays outside C accounting, alongside the
previous aligned UNKNOWN bytes. The actual-entry connection below adds shifted
bodies and the prologue; IRQ ownership and native device timing remain open.

The shifted 20/40 effects at8FF7/909C now have native cores in54 standalone
cases and349 preparation connections. Both use the relocated09A9 operand for
initial scratch ES, then follow live stack-restored DS/ES between rows. Mask
copies and their sentinel follow DF; the carry chain and mask reads advance
forward. Both variants advance SI per row. The ledger names6706/6748 scratch
bases without claiming allocation extents or resolving their stored UNKNOWN
bytes. The four other shifted bodies now have native cores and actual-entry
connections; see shifted-drawing.md and drawing-render.md.

The 8822 API now runs its native seven-instruction prologue, preparation, all
twelve planar bodies and the no-draw 88AB far return on canonical memory.
The full-entry matrix checks 2,147 constructed cases, including prologue/live-save
aliases, changed child return seams and the missing 969C byte-provider seam.
The four new leaves preserve forward SHR/RCR with backward copies, independent
mask/source shift-byte reads, first-pass VGA masks and later OR passes. Backward
scratch stores can overwrite live row fields; neither C nor its independent
packed-bit expectations cache those fields. UNKNOWN bytes and allocation extents
stay unresolved. The 7C67 connection below closes its normal caller domain;
source/mask producer domains and device/IRQ ownership remain open.

The 7C67..7CBB DrawPackedTerrainPiece caller now has a logical C11 prefix and
complete native renderer connection. It derives signed y and control/x bits
from two packed words, reads one of64 live GROUNDrecords and builds the original
far-call frame. The connection passes609 cases with all320 supplied terrain
metadata records, constructed source bytes and independent whole-plane checks.
Six directcore boundary probes verify normal/changednear/changedfar statuses.
No converted terrain or shadow game state was introduced.

SS aliases can overwrite metadata, saved coordinates, savedSI and the child's
far frame. A finite alias preserves the expected farCS while changing restored
SI to1000; another returnsCS0210 and stops before caller continuation. Two dirty
map aliases expose near targets8801/015E. The actual original RETF is executed
with the documented read-hook observation, then hooks are restored before
continuing. Next close the two big-endian terrain-command loops3752..3769 and
3962..3979 inside36B6/394F, including their FFFF sentinel, live iterator and
changed-return domains. See terrain-drawing.md.
