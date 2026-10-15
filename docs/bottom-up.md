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
| 01916..01F18 | resources.asm | Raw files, selection, special setup and DAT/cache cluster; allocation candidate has unresolved reachability |
| 01F19..0368D | game_code.asm | Mixed ownership remains provisional |
| 0368E..03789 | level_initialize.asm | Drawing initialization, live clear tail, header and level-state caller |
| 0378A..03943 | level_objects.asm | Record copy, interaction cells and coordinate collector |
| 03944..052D3 | game_code_late.asm | Mixed ownership remains provisional |
| 052D4..0563D | palette_frontends.asm | Palette pointers, writers and transition callers; ownership/frontier contracts remain explicit |
| 0563E..05725 | palette_steps.asm | Packed/RGB rows and channel arithmetic, tested native contracts |
| 05726..05D65 | game_code_late_after_palette.asm | Resource/generator ownership remains mixed; UNKNOWN preserved |
| 05D66..0616F | entity_graphics.asm | Byte masks, pixel setup/address and entity mask drawing contracts |
| 06170..0796E | game_code_late_after_entities.asm | Mixed ownership remains provisional |
| 0796F..07A59 | minimap.asm | Column, row and population sample contracts |
| 07A5A..08237 | game_code_late_tail.asm | Mixed ownership remains provisional |
| 08238..08342 | special_graphics.asm | Tested strip entries/shared tail |
| 08343..083BE | checksum.asm | Tested checksums, state and code/data overlap |
| 083BF..08821 | code_tail.asm | Overlay storage, layout setter and unresolved spans |
| 08822..09A8F | planar_drawing.asm | Planar renderer, dispatch, row preparation and clip/dirty leaves |
| 09A90..143D9 | image_tail.asm | Data frame; UNKNOWN may contain executable code |

The contiguous 05D66..0616F span groups nine identified mask and pixel helpers
in entity_graphics.asm, with exact start/end assertions and unchanged emission
lines. The earlier word generator and neighboring UNKNOWN bytes remain in the
resource-side prefix. This is physical source ownership, not a historical
linker boundary or an assertion about complete simulation/device readiness.

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
1A7B metadata/RLE/strip/VGAGR chain. RedrawLevel at394F now composes native
initialization, special/terrain, record-copy and object drawing within the
declared child domains. Its126 C bytes exclude UNKNOWN395E and overlap the
27-byte terrain loop and81-byte suffix; coverage unions these bytes and all
shared instruction sites. The36B6 initializer now composes its header, selection,
object state and live minimap handoffs in36 bounded cases; see level-initialize.md.
Broader field/provider/IRQ ownership remains open. The complete terrain stream
has scoped acceptance documented in terrain-stream.md.

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

The normal simulation tree now has its first maintained native leaf at
283B..287C, `CopyEntityPatternToInteractionMap`. The producer at 3464..34C7
saves the old interaction cells in the live 2Dh record before installing
02/0A/03 rows. The leaf restores through DF-sensitive word/byte strings and
live SS saves; 37 fixtures at both core/adapter boundaries cover all 37 sites
with four completed mutants. See entity-pattern.md. The 1F19 parent remains
untranslated. The 5DC6 pixel preparation leaf now adds 50 C bytes/22 sites,
verified in 39 fixtures at both boundaries with two JNS edges and four completed
mutants. Its eight-byte bit-mask table is explicitly classified and named;
post-PUSH X/table aliases, wrapped sign clamp and residual AL remain live.
See entity-pixel.md. The 5D94/5EBA VGA setup/exchange now pass 50 combined
fixtures at both boundaries, while the bus-aware 5DC6 retains its RAM API.
The 5F0F stroke directly composes that child through actual return frames in
40 fixtures, with 89 integrated sites/eight edges and five completed mutants.
See entity-vga.md and entity-stroke.md. The 5CDD/5D66 generated-mask leaves now
pass 44 fixtures at both boundaries, all 105 bytes/66 sites, 20 edges and five
completed mutants. Their 5AC1 producer directly composes the native leaves:
17 fixtures cover 80 additional bytes/35 sites, 101 integrated sites/24 edges
and five completed mutants. An independent calculation checks the complete
1370h bank. Live segment selectors, SS counts/cursors/DH/DS, child/outer returns,
DF and bus providers remain explicit. See generated-graphics.md. The 5DF8
consumer now passes 43 core/adapter fixtures, all 194 bytes/91 sites and seven
edges, with six completed mutants, 17 independent plane checks and an actual
native producer handoff. Its live clipped count, saves, DF/latch ordering and
early IF/drawing STI distinction remain explicit. The ten/thirteen-row sibling
entries now pass 67 fixtures at both boundaries, 405 bytes/187 sites, ten
edges and nine compiled mutants, with 41 independent plane checks and two
producer handoffs. The 6141 register-input coordinate helper passes another
34 fixtures at both boundaries, 47 bytes/23 sites and four mutants; its Y
subtraction has no clamp. See entity-mask.md and coordinate-pixel.md. All nine
identified helpers in entity_graphics.asm now have scoped C implementations.
The thirteen-row caller's signed-selector seam and broader initialization
remain open. Fresh 1F19 graphs now leave2EC0 as its sole direct untranslated child,
ahead of the parent at that checkpoint. The shared-tail 5CC1 caller remains untranslated.

The sound boundary for 2E04 now has native AdLib/Tandy dispatcher prefixes and
six latch setters:106 unique bytes/65 sites/27 edges, verified in766 fixtures
with ten completed mutants. Every AH byte is checked. Update/detect/reset
remain explicit untranslated exits; command4 uses the actual temporary DS
and saved IRET words. Do not replace that service with a preserving no-op.
The countdown now composes those cores through a declared live INT61
frame/vector model:430 fixtures at both boundaries,20 auxiliary transport
calls,188 new caller bytes/52 sites/14 edges and14 completed mutants.
Actual saved DS and IRET CS:IP/FLAGS remain live; an unbound vector or changed
return stops explicitly. Residual AH, field producers, callback slots and
the post-sound +8/+22 read are documented in entity-countdown.md. The model
is not hardware INT microcode or IRQ timing verification. Next resolve2EC0's
SS interaction map, record transitions and five interrupt seams. Its PC-speaker
dependency now has a scoped native0182..01AF dispatcher:282 core/adapter
fixtures,46 new bytes/29 sites/six edges and eight mutants. Effect/Stop bus
composition has274 additional fixtures/18 sites/two LOOP edges/five mutants.
Temporary DS and actual table/stack/RET/IRET words stay live; Tick and other
targets remain explicit exits. The declared INT60 connector now passes25
focused fixtures and six mutants. Its2EC0 parent now composes all five service
sites in311 fixtures,486 new main bytes/162 sites/all61 branch outcomes and
eight mutants. Actual popped AX and returned DS/SI/CX own the later behavior.
The normal C interface uses explicit inputs/results; the full-register adapter
is confined to the oracle and the INT architecture boundary. See pcspeaker.md
and entity-interactions.md. The1F19 state priority and live record/counter/scan
ownership are now recorded in entity-simulation.md. Shared1FE8/20D6/20E2/2148
JMP tails pass24 fixtures/55 unique bytes/18 sites/eight edges/six mutants.
Their zero-state2047 parent passes37 fixtures/309 additional bytes/104 sites/
33 owned edges/eight mutants, including actual5DC6 and interaction CALL/RETs.
The combined364 new bytes retain overlap, segment, stack and device contracts.
State0004 at21B0 now adds303 bytes/87 sites/29 edges in36 core/adapter fixtures
with eight mutants; its early20E2 exits skip the Y store, while real5DC6 and
INT61 frames remain live. Four neighboring cadence entries add113 bytes/45
sites/18 edges in23 core/adapter fixtures with eight mutants; a separate1,024
original-only prefix matrix covers their byte transforms. See entity-simulation.md.
The shared original-instruction oracle now accepts explicit parent spans and
RET/stop contracts, retaining one live defined-FLAGS mask and the existing
INT/driver transport. Next connect23BF state0008, then2350 state0002 with2382
still UNKNOWN and excluded. The remaining states and live1FEB iteration/scan
parent retain their initialization, table, platform and IRQ obligations.

Keep the edit loop small: the default `tools/verify.py` checks exact identity and
ASM, followed by `tools/difftest.py SUITE [SUITE ...]` for affected bounded native
suites. Preview limits with `--plan`; use `--all` only for the complete native
campaign. Focused execution does not promote global coverage. The complete original-only
campaign is `tools/verify.py --contracts`; aggregate coverage still requires
that report and fresh native evidence. A parent needs focused contract-handoff
and composed cases; exhaustive child matrices remain in the child suite unless
new parent behavior warrants repeating them. Preserve every declared live
segment, flag, stack and device effect. Narrower caller domains require proof.

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
copy dependency for the397A..39CD object-drawing suffix and394F parent;
their scoped native implementations require fresh acceptance reports. See
object-graphics-bus.md and object-drawing-frontier.md.

The pass exposed a static extractor gap: zero initial bits are legal. The original
CH increment/decrement causes immediate backward refill, while the seeded last
payload byte still joins the checksum. Thirteen real level sections use it. The
extractor now accepts zero, with a known-answer test and all 80 level records in
the original/native/static comparison. Original instructions and native decoder
behavior were unchanged.

The16A9 timer restore leaf now has a logical native core with291 adapter and
291 core-boundary comparisons,19 sites/43 bytes and four completed mutants.
Its PIT outputs precede live LES/IVT stores; unconditionalSTI and actualPOPDS
select the clock reads before a returning BIOS service. See timer-restore.md.
The04D0 full cleanup and04EA suffix now compose those cores in362 adapter
and362 logical-core comparisons with four completed mutants. The 41 caller
bytes/15 sites overlap no new child bytes; the integrated union is133 bytes/56
sites. Live childreturns, mousegate, duplicatekeyboard and terminalDOS remain
explicit. See fatal-cleanup.md. The1949 file-error printer now connects video
and04EA directly in301 adapter and301 core comparisons,25 caller/45 integrated
sites,four edges and four completed mutants; see file-error.md. The filename
walk keeps live provider-returnedDSBX and the tail adds no CALL frame. Continue
upper resource-selection/DAT error interfaces next. The1916 optional-bus reader
and direct1949 fatal path now pass87 fixtures across four boundaries,72 integrated
sites/12edges and four completed mutants, retaining each failed-call save frame
and the narrow DOS preservation contract. See resource-raw-full.md. Those49 raw
bytes overlap the prior RAM translation; no extra translated bytes are claimed.

Full classification, native devices, IRQ scheduling, gameplay and SDL3 remain
open. No original game was booted, and assets/neighbors remain untouched.

The retry UI dependency1550 now has a native bit3-cycle wait, retaining one live
base-port read, byte-onlyDL addition and both unbounded original loops. Its280
adapter/core fixtures and four mutants use finite byte-port providers; missing
providers and actualRET/VGA effects stay explicit. The4C32/4C36 word outputs and
4C20 origin swap now compose directly, with277 fixtures at all three entries and
both boundaries. This adds57 unique decoded C bytes across26 sites, with shared
suffix bytes counted once. See display-status.md/display-start.md for separate
gates and original-only evidence. The4BE7/4BF5/4C07 setup entries now connect
native8808 layout in55 fixtures across three entries and both boundaries, with
51 null-bus repeats each and four completed mutants. Their48 unique caller
bytes/14 sites preserve all-state BIOS, unconditionalSTI and live far/near
returns; see display-setup.md for the explicit segment-limit seam. The4D78
glyph producer now connects8822 in45 integrated fixtures at both boundaries,
with264 prefix fixtures for all256 byte selectors and null-bus repeats, and
four completed mutants. Its74 caller bytes/32 sites retain unchecked96-byte
indexing, liveDS segment selection, all returned renderer fields and savedBP;
see text-glyph.md for the definedflag and device-stack domains. The4D4D
stream now composes the glyph core in295 fixtures at both boundaries, including
all256 style bytes and six pinned record slices. Its43 caller bytes/26 sites
and eight caller edges preserve the live DF/DS/cursor/save-frame effects and
CR/header-zero distinction; five mutants and a separate guard86 probe pass.
See text-stream.md. The4DC2 page copy and4DEF fixed-clear wrapper now
compose in45 fixtures at both boundaries with six completed mutants. Their
53 new caller bytes/21 sites retain full6D60 counts, sequential overlap,DF,
liveorigin/DS/RET and provider seams. Four mode1 device regressions and
independent four-plane results support the latch-copy fixture; see
display-pages.md. The5017/5019/7E76 background bridge now connects8822
in36 fixtures at both boundaries,26 caller/305 integrated sites and six mutants,
preserving live row/counter saves and full640x350 clipping; see
background-drawing.md. The531E/536C palette transitions now compose those writers, row/channel and
status cores in1,191fixtures at both boundaries,82caller/268integratedsites,
40integratededges and six completed mutants. Their157unique caller bytes retain
once-selected mode, before-wait JZ, live saves and actual child returns; see
palette-transition.md. The4B3B/4B40 frame-free input wait now has21unique C bytes/7sites/4edges,
all65,536 button words,791fixtures at both boundaries and seven completed
mutants. Its512 original-only keyboard prefix cases add no C coverage; see
retry-input.md for scan-code releases, shared button word and live memory
updates. Continue full4B1C composition with explicit provider/IRQ seams.
Native hardware timing remains open. Older reports affected by the
fixture extension require refresh before aggregate coverage promotion.

The cache-allocation candidate1ED7..1F18 now has explicit ASM and an investigation
seed covering66 bytes/25 sites. Its two DOS calls, unsigned paragraph threshold,
unchecked allocation result, partial AL updates and live near return are recorded
in cache-allocation.md. Startup calls the separate1ED1 disabling stub and returns
before this candidate; no known incoming execution edge is established. The new
seed closes static accounting of that interval without adding C coverage or
claiming global reachability. Requested paragraphs atDS:1F8E belong to the ledger;
the name does not imply that DOS successfully allocated the requested block.
The separate native allocation core now passes282 comparisons plus282 auxiliary
core probes and four completed mutants. It preserves the live DOS AX/BX/flags
boundary, optional RAM/VGA bus order and actual near returns; it introduces no
startup call. The267-case original-only contract remains separate evidence.

The15-byte0FF8 video mode/page restore leaf now has its own279-case original
contract and native gate. The BIOS mode result's liveDS selects the page byte;
all declared general/segment/stack/flag effects flow to the second provider and
actual nearRET. See video-restore.md for missing-service and RAM/VGA boundaries.
This closes one cleanup dependency, not the04D0 timer/vector/platform caller.
The1582 keyboard and0FA0 private-vector restore leaves now add a separate native
gate over34 bytes/15 sites. PUSHDS precedes live pointer reads; returnedSS:SP
controls POPDS and RET, including a DOS IVT update that overwrites both words.
Their328 primary cases and four variants at both entries remain separate from
the16A9 timer dependency and the unported04D0 cleanup caller; see vector-restore.md.

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

The five palette channel entries at566C/5685/5696/569B/570C now have native
cores over144 unique bytes/69 sites, retaining the shared569B suffix and live
wrapper near returns. All327680 byte pairs match originalASM and independent
channel/flag mathematics;88 fixtures at both boundaries cover14 edges,81
NULL-bus repeats each and six completed mutants. Preserve signedJG versus
unsigned channel ordering and sticky BP/BL; see palette-channels.md. The next
parents are563E packed rows and56E2 RGB rows, followed by5425/54C4 port writers
and the531E/536C palette loop. Palette pointer/buffer/device ownership and the
separate4B40 input/IRQ wait remain open.

The563E packed and56E2 RGB row composers now connect the channel cores over
88 additional bytes/47 caller sites. Their89 fixtures at both boundaries and
two full65536-iteration zeroCL core cases preserve sequential buffer overlap,
live savedCX, sticky markers, actual child returns and explicit forward cursors
withDF set. The232-byte palette-step cluster now has a maintained flat ASM
module, with unchanged classifications/encodings and physical module assertions.
See palette-rows.md. Continue5425/54C4 port writers and palette table/buffer
ownership before531E/536C and the separate4B40 input/IRQ wait.

The5425 attribute and54C4 mappedDAC port writers now have separate native cores
for101bytes/61sites. Their577boundary fixtures plus2fullzeroCL corecases
keep DF-dependent source reads, uncheckedCSindexes, byteADD, live saved words,
and independently reread DS200C control. See palette-ports.md. The remaining
531E/536C uncertainty is pointer/buffer ownership and live producer frames;
palette-pointer-frontier.md records the pinned tables and next connection order.

The5569 pointer prefix now connects both row cores through actual PUSH DS/POP ES
and live unchecked CS word reads, without introducing a CALL frame. Its77new
bytes/32sites are separate from the232-byte arithmetic cluster, with586fixtures
at both boundaries andtwofull65536-iterationzeroCL cores. See palette-row-select.md.
The contiguous52D4..563D front ends now live in palette_frontends.asm, preserving
all UNKNOWN markers and physical byte order. Transition callers531E/536C remain the next dependencies to connect, preserving
their own live frames; writer prefixes stay separate setup paths.
