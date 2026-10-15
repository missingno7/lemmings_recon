# Reconstruction completeness

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py --contracts, tools/difftest.py --all, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | 82,906 |
| Classified image bytes | 45,694 |
| Decoded instruction bytes | 35,760 |
| Reconstructed ASM bytes | 82,906 |
| Byte-exact ASM bytes | 82,906 |
| Identified routine entry candidates | 273 |
| Translated C routines | 59 |
| Translated C code bytes | 7438 |
| Differential cases | 11123 |
| Mutation checks detected | 143 |
| Original instruction coverage | 3680 / 15,392 decoded (23.909%) |
| Unresolved image bytes / runs | 37,212 / 115 |
| Unresolved runs inside provisional code frame | 112 (2,098 bytes) |
| Resolved static CFG edges, including fallthrough | 16,969 |
| Unresolved direct targets / indirect transfers | 1 / 5 |
| Runtime-modified control-flow frontiers | 2 |
| Additional state-specific main instruction sites | 401 |
| Known conditional indirect edges | 18 |

The decoded instruction denominator is incomplete: unknown runs in the main and
sound-driver images may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are 1,567 main-image decoded instructions expressed as explicit encoding exceptions.

Gate A passes for the main EXE: deterministic static unpack, full byte comparison,
63 independently checked relocations, entry/stack state and input identity. Gate B
has an exact buildable initial ASM image, but remains open for code/data, indirect
transfer, external-driver and semantic closure. Gates C/D have the checksum,
resource/decoder/file/read/cache/leaf, special VGA strip and PC-speaker helper clusters.
The two checksum, thirteen DAT, raw-resource, RLE, four special VGA strip and
special graphics setup, decimal helper, resource selection, four object-record
main routines, the four-call object-state span, VGA clear, drawing-layout setter
and connected level-drawing/minimap callers, clipping/dirty leaves and the scoped
planar preparation/geometry/dispatch/source spans, all six aligned bodies and
all six shifted bodies, the actual8822 entry and packed terrain caller
are TESTED within docs/checksum.md,
docs/dat.md, docs/dat-io.md, docs/dat-section.md, docs/dat-cache.md, docs/dat-files.md,
docs/dat-load.md, docs/resource-raw.md, docs/resource-rle.md, docs/special-blit.md,
docs/special-setup.md, docs/decimal-digits.md, docs/resource-select.md and
docs/object-records.md, docs/interaction-cells.md, docs/vga-clear.md,
docs/drawing-layout.md, docs/level-drawing.md, docs/minimap.md,
docs/drawing-clip.md, docs/drawing-dirty.md, docs/drawing-inputs.md,
docs/drawing-dispatch.md, docs/drawing-source.md, docs/drawing-plan.md,
docs/aligned-opaque.md, docs/aligned-masked.md, docs/aligned-protected.md,
docs/aligned-read-mask.md, docs/aligned-mask-effects.md, docs/shifted-mask-effects.md
docs/shifted-opaque.md, docs/shifted-masked.md, docs/shifted-protected.md,
docs/shifted-read-mask.md and docs/drawing-render.md's domains; remaining
main entry candidates are UNTRANSLATED. CS:8363 reachability remains UNRESOLVED despite
its complete bounded instruction/branch coverage. Gate E is not started.

The checksum tests execute 44/44 cluster instruction addresses and all 10 static
branch edges. They compare registers, defined flags and the entire 1 MiB memory,
including push/pop residue, across poisoned fixtures. AF is excluded only on the
phase-wrap path, where the last XOR makes it architecturally undefined.

The DAT leaf suite covers 33/33 instructions and all six local branch edges in
470 cases. It compares full memory, registers and defined flags, including zero
bit counts (256 iterations), zero incremented match counts (65,536 iterations),
live overlapping copies and overwritten saved registers. Three compiled mutants
are detected. Cache allocation, retry UI and fatal cleanup remain UNTRANSLATED;
the strict static extractor's validation rules are not substituted for original
runtime behavior. See dat.md.

Loaded sound-component images reconstruct exactly, with separate static accounting:

| Image | Exact ASM bytes | Classified bytes | Decoded instructions | Entry candidates | Unresolved transfers | C routines |
|---|---:|---:|---:|---:|---:|---:|
| adlib | 22,125 | 1,438 | 655 | 17 | 1 | 0 |
| tandysnd | 21,702 | 1,890 | 754 | 40 | 1 | 0 |
| pcspeaker | 758 | 596 | 89 | 4 | 1 | 3 |

Across all four component images, 127,491 ASM bytes are exact and 17,291
instructions have been decoded. C differential coverage is 3740 / 17,291
(21.630%) of this still-incomplete decoded inventory. There are
62 tested C routines occupying 7603 original code bytes across images,
with 11458 differential cases and 146 compiled mutations detected. Six bounded
DAT extraction checks exercise 145 main-image instructions; these are extractor
verification, not C translation coverage and not driver execution tests.

All 16 legacy AdLib signatures at segment 2911 match the static extraction. The
seventeenth external lead is F000:FF53 firmware/environment code, not a driver entry.
All three sound dispatch tables lack sufficient bounds checks; their out-of-table paths
remain unresolved. Driver code/data closure and behavioral translation are open.
Main INT3 protection has independently checked state-specific views: 372 stream
instructions (325 TF-on, 47 TF-off) and 29 transformed INT1 instructions. The
original handlers pass 19 constructed-frame cases and checks at every one of the
325 derived TF-on instruction points, comparing full memory, registers and defined
flags. These checks execute only 61 handler instruction sites; the disk-check body
has not been executed. The two raw-image control frontiers remain represented in
the separate protection CFG. Platform contracts, memory aliases and skipped code
still need review; see protection.md. No protected routine has been translated to C.
No public executable or proprietary asset is tracked. See executable.md for local
provenance, control-frontier.json for addresses, and next-work.md for proof obligations.

Callback evidence traces all 32 recovered object-record pointer stores to nine
drawing callback slots and identifies four display probes, three input callbacks
and the code-input BP callback. The 18 known indirect edges are present in the CFG,
while all five near-callback target domains remain explicitly incomplete. Thirty-two
bounded caller fixtures cover 214 original caller instruction sites with declared
callee boundaries. They check routing and save/restore behavior, including DF-set
traversal and unlisted live pointers; they are not C coverage or callee tests.
See indirect-callbacks.md for alias and incoming-state obligations.

The PC-speaker image is MAIN.DAT section 5: 758 separately reconstructed payload
bytes loaded over canonical zeros at main 08420..08715. Component byte totals count
both stored main bytes and the payload image; they are not unique runtime-memory
bytes. Original extraction is checked at the actual overlay destination at two loads.
The payload's trailing 161 bytes and single pre-entry byte remain UNKNOWN. Its three
closed helpers (effect selection, tick and stop) now have C11 cores and near-call
adapters. The PC-speaker suite compares full memory/registers, defined flags and
port traces in 335 cases, covers all 60 helper instruction sites and all 17 branches,
and detects three compiled mutations. The IRQ dispatcher remains UNTRANSLATED;
none of its unresolved target paths has been silently replaced. See pcspeaker.md.

Two saved INT08 chains now have explicit external IRET edges and original return
continuations. Nineteen bounded tail cases check complete memory and saved-register/
flag results across loads, stack wrap and external clobbers. Nineteen installed-
handler fixtures check 0F6F/0F70/18F8 and their declared service boundaries. These
are caller/handler checks, not full timer, BIOS, C or game execution coverage.
See interrupts.md for provider contracts and the menu wrapper's unsaved ES effect.

The complete DAT read wrapper at 1D2E..1E1B now has 45
bounded original-code cases, covering all 106 instructions and
12 branch edges under declared DOS fixtures. Full memory/register/flag
checks expose direct-read errors, short reads, cache creation and hits, saved-frame
aliases, ignored cache-fill errors and pointer/count wrap. This is provider-contract
evidence, not C translation or actual DOS execution coverage; see dat-io.md.
The same original wrapper also has a C11 core and near-call adapter, verified in
45 native differential cases covering all 106 sites and 12 branches, with
three compiled mutations detected. Its narrow DOS file-size/read services have
declared register-preservation contracts. The skipped UNKNOWN byte at 1D7C is
excluded from translated-byte accounting. Full DOS/FCB platform behavior and the
other resource-loading routines remain open.

The DAT section decoder and its read-distance/shared-copy entry now call C cores
directly. 128 integrated differential cases execute all 235 decoder,
leaf and read-wrapper sites and all 32 local decoder/leaf branch edges. They
compare full memory, registers, defined flags and service traces, including real
sound sections and malformed constructed headers. Three compiled section mutations
are detected. Only AF after final AND DH,DH is excluded; read-error flags are fully
compared. The fatal jump to 04D0 is an explicit exit with its original saved frame,
not a translated cleanup routine. Four skipped UNKNOWN bytes are excluded from
translated-byte accounting. Direct helper calls retain original return-word residue;
overwriting those active return words is outside the current verification domain.
See dat-section.md for unsigned termination, ignored high size words and aliases.

DAT filename preparation, cache selection and startup cache disabling now have
C11 cores: 305 cases cover all 96 instruction sites and 18 branch edges,
with three compiled mutations detected. Full memory/register/defined-flag checks
preserve wrapped padding counts, DF, the last-byte mismatch hit, record-pointer
wrap and saved-register aliases. No host filename normalization or corrected
string comparison is substituted. The UNKNOWN cache allocation code remains
open; see dat-cache.md.

File open/check wrappers now have C cores: 40 cases cover all 69
wrapper sites and 16 wrapper edges, with three compiled mutations detected.
Native cache calls are exercised inside CheckDatFile. DOS open/attributes and
the original game retry callee at 4B1C are declared verification boundaries;
the retry callee's rendering/input body is not translated or counted as executed.
The 1949 fatal transfer preserves the original outer save frame and message offset.
See dat-files.md for clobbers, aliases and remaining caller/platform ownership.

The resource-loader caller and its shared segment-preserving decoder tail now
call native file and decoder cores directly. 24 integrated cases
cover all 30 caller instruction sites and eight caller branch edges, with three
compiled mutations detected. Full memory/register/defined-flag and service/callee
traces preserve ignored open carry, live saved-DS corruption and both fatal frames.
Two cases start at the constructed post-check continuation to test caller branches
without asserting that a normal CheckDatFile return can produce carry. The UNKNOWN
1B97 byte is excluded; overlapping shared-tail bytes/sites are counted once.
DOS and 4B1C retry bodies remain declared seams; fatal cleanup and higher resource
ownership are still open. See dat-load.md.

The raw-resource open/read/close routine at 1916 now has a C11 core: 46
cases cover all 27 instruction sites and eight branch edges, with three compiled
mutations detected. Full memory/register/defined-flag and service traces preserve
short reads, partial AH writes, live restored-segment corruption and all three
distinct fatal frames/message offsets. Its 49 C-covered bytes exclude two UNKNOWN
skipped bytes; the shared 1949 error-print path remains untranslated. Actual DOS
behavior across segment ends and higher resource ownership remain open.
See resource-raw.md.

The resource RLE routine at 1B42 has a C11 core: 303 cases cover all
29 instruction sites and 14 branch edges, with three compiled mutations detected.
Full memory/register/defined-flag checks preserve all 256 control-byte meanings,
DF, live input/output overlap, cursor/segment wrap and repeat-byte corruption
when the original segment update replaces AL. These are constructed terminated
streams; complete graphics/resource ownership remains open. See resource-rle.md.

The four special-resource strip entries at 8238/8243/8249/824F share a C11 core.
28 cases cover all 122 original instruction sites and 22 branch edges,
with three compiled mutations detected. Full RAM, registers, defined flags,
device planes/latches/registers and port/MMIO traces preserve the four-plane strip
layout, mask construction, incoming DF, interrupt-enable changes and live stack
aliases. Sixteen cases use the pinned VGASPEC streams; an independent expected
plane check also verifies untouched video memory in the forward cases. The three
skipped UNKNOWN bytes remain excluded; shared bytes and sites are counted once.
This is a bounded device fixture, not a native VGA backend or IRQ scheduler.
Platform ownership and SDL3 remain open. See special-blit.md.

The special graphics setup caller at 1A7B now connects metadata copies, four
RLE/strip calls and two normal graphics DAT sections through direct native cores.
20 integrated cases execute all 87 caller sites and 621 dependency/caller
sites. Full RAM/register/defined-flag/device/service-trace comparisons include
four paired VGASPEC/VGAGR inputs, both DF values in declared fixtures, cache paths,
stack wrap, saved-DS corruption, retry and four decoder fatal exits. Independent
expected metadata and four-strip plane contents also pass in the forward cases.
Three compiled mutations are detected. The unchecked final close result remains
unchecked; original fatal frames stay live. This adds 199 C-covered caller bytes;
dependency bytes/sites are counted once. DOS, retry UI, VGA backend and IRQ delivery
remain declared seams. Allocation and full native startup are
still open. See special-setup.md.

The decimal filename helper at 4BC2..4BE6 now has a native C11 core. Its
270 original-versus-C cases cover all 19 sites and four branch edges,
all AL values, poisoned AH/control flags, cursor/stack/physical wrap and overwritten
live return words. Three compiled mutations are detected. The separate 260-case
original-only contract check remains extractor evidence and is not added to C coverage.
See decimal-digits.md. The source is split into
maintained physical modules with exact end assertions, and fresh call/dependency
views guide the next cluster. See bottom-up.md. All80 pinned LEVEL sections also
match static extraction and bounded original/native decoding, including13 valid
zero-initial-bit headers; these cases are part of the DAT section C suite above.

The resource selection caller at 197D..1A7A now composes the native decimal,
raw-resource, file/cache and section decoder cores directly. Its
59 integrated cases cover all 108 caller sites and nine branch edges.
Full memory/register/defined-flag/service comparisons preserve unchecked order-byte
wrap, repeated in-place level decoding, odd override copies, DF, short/long ground
reads, live saved-counter/order/DS aliases, unchecked closes and distinct fatal frames.
Paired original LEVEL/ground/odd/VGAGR/VGASPEC inputs also pass, with independent
record expectations. Three compiled mutations are detected. The 253 C-covered
caller bytes exclude the skipped UNKNOWN NOP; dependency bytes/sites are counted
once. DOS, 4B1C retry UI and 1949/04D0 fatal bodies remain explicit unported seams.
Object/terrain ownership and native startup remain open; see resource-select.md.

Two closed level-object helpers now have native C11 cores. The graphics-record
copy at 378A has 131 cases covering all 26 sites and four edges;
the type-one coordinate collector at 389F has 159 cases
covering all 63 sites and 12 edges. Each suite includes all 80 supplied LEVEL
sections; the graphics copy also uses the matching GROUND inputs. Full RAM,
registers and defined-flag comparisons retain stale slots, incoming DF, wrapped
unchecked type lookup, live saved-cursor/counter and return aliases, counts 0..32,
zero-X acceptance, and the original default repeated+0A store/+0C stale bug.
Six compiled mutations are detected. These disjoint 221 bytes add 89 original
instruction sites; shared upstream dependencies remain counted once. The helper
ASM is grouped at its unchanged physical position in level_objects.asm with
start/end assertions. The larger 36B6/394F setup/drawing pipelines remain
untranslated. See object-records.md.

The SS interaction-cell writers at 37C2/3839 now have native cores with
123/386 cases, 54/47 sites and 9/8 branch edges.
Zero object dimensions mean 256 iterations; all 256 packed steel dimensions,
byte3-only presence, unchecked template lookup, live row-save/input/return aliases,
offset and 20-bit wrap are retained. Each suite includes all 80 original LEVEL
sections; object cases pair their GROUND inputs. Six compiled mutants are detected.
No separate cell map replaces SS, which also owns the stack and VGA mirrors.

The 376A..3775 span now connects the four native object helpers directly in
105 cases, covering four caller/194 integrated sites and 33 integrated
edges. Independent SS-window and graphics/coordinate output checks pass all 80
LEVEL/GROUND pairs. Changed callee RET words after each of the four calls expose
their actual target before any target instruction executes. Normal continuation
is 3776; the outer 36B6 RET remains live. Three compiled mutants are detected.
This adds 12 caller bytes without claiming a complete 36B6 translation. Full setup,
VGA/IRQ ownership and far drawing remain open; see interaction-cells.md.

The VGA clear at 4DF8 and far drawing-layout setter at 8808 now have native
cores in 33/151 cases, covering 25/10 sites.
The 368E initialization and 36AD clear tail connect them directly in
27 cases, covering 14 caller/49 integrated sites and the
single tail-JMP edge. Full RAM/register/defined-flag and device comparisons
preserve live SS mirrors/CALL frames/RET targets, incoming DF and IF,
truncated pitch/low extent, wrapped segment publication and aperture aliases.
Independent plane footprints, untouched bytes, port words and layout fields pass.
These four entries add 129 unique C bytes and 49 sites; nine compiled mutants
are detected. The layout suite isolates two SP-boundary cases as body comparison
plus permissive adapter-model checks, not original-hardware far-return equivalence.
The connected suite independently records and isolates Unicorn's RETF read-hook
artifact without patching return targets. CPU-family stack-limit faults, IRQ
delivery, minimap, terrain and the broader level consumers remain open. See
vga-clear.md, drawing-layout.md and level-drawing.md.

The closed minimap sample/row/column at 7A39/7A25/796F now compose native cores
in 67/49/62 cases, covering all 96 sites and fourteen
integrated edges. Two complete thirteen-call cycles compare original and native
on the same evolving RAM/device state with both DF values. Full RAM/register/
defined-flag, ordered port/MMIO and independent whole-plane checks preserve the
population>8 threshold, separate ES byte wrap, live SS save/RET/counter aliases,
signed column comparison, DF-sensitive CS clear, twenty accumulated/nineteen
displayed rows and final latch reads. Nine compiled mutants are detected. The
65,536 native source-population vectors remain separate from original differential
and instruction coverage. This adds 235 unique C bytes; the dedicated flat
minimap.asm module keeps byte order and UNKNOWN classifications unchanged.
IRQ/device timing, executing-code corruption, CPU-family segment-limit faults,
terrain/far drawing and broader level consumers remain open; see minimap.md and
minimap-vga.md.

The clipping and dirty-cell leaves at 9967/9A15 now compose directly in the
scoped 882D..885D preparation span, with 59/2066/102 original/native cases.
The leaves cover 73/63 sites and 29/16 edges; the connected span covers 18 caller/
154 integrated sites and 51 edges. Full RAM/register/defined-flag and ordered byte
checks retain signed versus sign-only clipping, byte-rounded zero counts, live
DS/SS field/save aliases and changed childRET targets. Nine compiled mutants are
detected. These add 344 unique C bytes and 154 sites. The original 8822 prologue's
seven sites are separate evidence in these preparation-only suites; 885E dispatch
and88AB RETF remain boundaries of that API. The actual-entry suite below verifies
the native prologue and abort return. The decoded 9996 NOP remains outside
the normal-entry tests without a dead-code claim. An independent original MUL/
MOV observation records Unicorn's transient memory-hook CF/OF artifact; bus
flags use original instruction-boundary snapshots, with all defined bits checked.
VGA devices, IRQ delivery, executing-code corruption and CPU-family faults
remain open for this RAM scope. See drawing-clip.md, drawing-dirty.md and
drawing-inputs.md.

The destination-positioning and path selector at 885E, shared 939E tail and
four source-row spans at 88BF/9140/93A7/9810 now compose directly with the
native 882D preparation. The dispatch/source/connection suites pass
77/236/744 original/native cases, with 41/92/287 original sites.
They retain live page/pitch/shift words, packed count truncation, reverse-source
wrap, two separate vertical-skip reads, PUSH/store/POP control aliases and
4000/8000/20/40 priority. Independent geometry/cursor/stride/body expectations
cover all eight residues and low-bit modes, overlapping effect flags and both
reverse states. Nine compiled mutants are detected. This adds 348 unique bytes
and 133 sites; the connected wrapper adds no caller bytes. Original 8822 prologue
sites remain separate. Incoming 88A6 ZF-to-88AB is tested as its own bounded entry
state and excluded from the normal-entry connection without a dead-code claim.
The planar family now has a flat physical module at 8822..9A8F with exact end
assertions. Selected VGA bodies, far returns, IRQ/device semantics, self
modification and broader level consumers retain explicit domains. The complete
normal-entry connection is described below. See drawing-dispatch.md, drawing-source.md and drawing-plan.md.

The aligned opaque body at 983B now has a native core composed with drawing
preparation. The body/connection suites pass 55/776 original/native cases,
including four plane passes, count wrap, DF, live segment/stack aliases, latch
reads, ordered port/MMIO/SS accesses and CLI/STI effects. The 149 normal-entry
body sites add 298 unique C bytes; UNKNOWN 98F4/9932 remain excluded without
dead-code claims, and the 988B shared entry retains separate incoming-state
obligations. The connection adds no bytes and keeps original 8822 prologue sites
outside this older scoped suite. Six compiled mutants are detected.
Asynchronous IRQ delivery, executing-code mutation and CPU-family faults remain
outside the native domains; the actual8822 connection is described below. See aligned-opaque.md and
drawing-render.md for the exact tested domains and return-oracle observations.

The default aligned masked body at 93F6 has a native core in
20 standalone cases and a preparation connection in
100 cases. Its 326 unique bytes/166 sites exclude
UNKNOWN 94C7/9507. The first pass advances BX independently of DF and uses a
live per-byte VGA mask; later passes OR source bytes into destination latches.
Original CLI/STI timing, INC/ADD flags, DS/SS saves and far-return words remain
live. The general renderer API also retains the opaque 983B branch; the older
opaque-scoped API preserves its explicit masked-body seam. The connection runs
90 masked draws and
8 opaque draws; two saved-BP aliases select
the explicit 969C effect seam in this API. Six compiled mutants are detected. Original 8822
prologue sites remain excluded from this older suite. See aligned-masked.md and
drawing-render.md.

The four other aligned bodies add 721 unique translated bytes: protected953E
(349, excluding UNKNOWN9659), read-mask969C (155), effect20 (109) and effect40
(108). They pass 21/17/52
standalone cases and 226 all-aligned preparation
connections. The connection covers 759
integrated sites and 117 edges; sites are unioned,
not summed. All original body RETFs receive actual single-step probes. Plane-3
comparison/protection, live savedDX/DS, explicit byte OUT/IN replies and the
20/40 row-cursor asymmetry remain original behavior. Missing byte providers
leave969C explicit. These four suites detect twelve compiled mutants. See
aligned-protected.md, aligned-read-mask.md, aligned-mask-effects.md and
drawing-render.md for constructed-state domains and IRQ/device timing limits.
The original8822 prologue and other shifted bodies remain outside these older
scoped suites; the new full-entry report verifies them below.

The shifted20/40 bodies at8FF7/909C add329 translated bytes/168 original sites,
including their two far-return adapters. They pass
54 standalone original/native cases and
349 preparation connections. Their scratch masks are
copied through live DS/ES with incoming DF, then shifted forward through SHR/RCR
carry chains. Both variants advance SI between rows. The relocated09A9 operand,
live saves, decremented destination-row word and unchecked count/shift wraps
remain original behavior. The connection covers seven shift residues, DF,
reversal, enable masks and the preserved older API/provider/unported-body seams.
The two suites detect six compiled mutants. See shifted-mask-effects.md,
shifted-drawing.md and drawing-render.md. Scratch names identify runtime bases,
not proven allocation extents; their stored UNKNOWN bytes remain unresolved.

The shifted default masked890E, protected8B42, read-mask8D66 and opaque916B
bodies add2,328 decoded C bytes/1,310 known sites, including far-return adapters.
Their standalone suites pass 29/20/25/29
cases and detect twelve mutants. UNKNOWN8ADD/8CF4/8F8D/9339 stay excluded.
Copies and sentinels follow DF while carry chains and mask reads go forward.
Source shifts and mask shifts reread the live shift byte separately; backward
copies may overwrite live row fields. The read-mask path caches all rows before
drawing and keeps its word-port DX changes; protection leaves BX untouched.
See shifted-masked.md, shifted-protected.md, shifted-read-mask.md and
shifted-opaque.md for boundary hashes, return probes and unchecked domains.

The actual8822 native entry now composes its seven-instruction prologue,
preparation, all twelve bodies and88AB no-draw far return in 2147
cases. It covers 2424 integrated
original sites and 378 observed edges, and detects three
renderer mutants. The prologue and88AB add12 unique translated bytes/eight sites;
shared body sites/bytes are unioned with leaf and earlier connection evidence.
Independent packed-bit models verify whole-plane footprints, including live
stride changes caused by backward scratch copies. Full RAM/register/defined
flags and ordered bus/ports/VGA state match original execution. Older scopes,
changed child return and missing aligned969C byte-provider seams remain visible.
UNKNOWN bytes, shared988B other incoming states, allocation/producer domains,
asynchronous IRQ/device scheduling and broader gameplay integration remain open.

DrawPackedTerrainPiece at7C67 now derives the original control/coordinates and
reads a live eightbyte GROUNDterrain record before calling the native8822 core.
Its 265 prefix cases cover all33 caller-prefix sites/four
conditional edges; 609 connected cases cover36 caller sites and
1366 integrated sites. The full connection
uses every supplied GROUNDterrain record (320 metadata records) with constructed
source bytes. Independent packed-input, whole-plane and untouched-record checks
complement whole RAM/register/defined-flag/orderedbus/VGA comparison. Six direct
core-boundary probes verify ready/changednear/changedfar statuses. Eight mutation
checks are detected across the prefix/connection suites. This adds85 unique C
bytes; shared renderer sites/bytes are unioned, not summed.
The far CALL writes CS then7CBA; changed live IP/CS stop before any target executes.
Normal return pops live savedSI before the caller's nearRET. Tests retain signed
SAR-y, ignored selectorbit6, x/control bits, reversal, scratch/stack aliases and
physical/offset wraps. The actual original RETF is executed with its documented
read-hook observation, then hooks are restored before caller continuation. IRQ,
device/producer/allocation ownership and higher terrain loops remain open. See
terrain-drawing.md; no game was booted and no assets were changed.
