# Reconstruction completeness

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py, tools/difftest.py, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | 82,906 |
| Classified image bytes | 45,694 |
| Decoded instruction bytes | 35,760 |
| Reconstructed ASM bytes | 82,906 |
| Byte-exact ASM bytes | 82,906 |
| Identified routine entry candidates | 273 |
| Translated C routines | 29 |
| Translated C code bytes | 2283 |
| Differential cases | 2656 |
| Mutation checks detected | 54 |
| Original instruction coverage | 1060 / 15,392 decoded (6.887%) |
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
main routines and the four-call object-state span are TESTED within docs/checksum.md,
docs/dat.md, docs/dat-io.md, docs/dat-section.md, docs/dat-cache.md, docs/dat-files.md,
docs/dat-load.md, docs/resource-raw.md, docs/resource-rle.md, docs/special-blit.md,
docs/special-setup.md, docs/decimal-digits.md, docs/resource-select.md and
docs/object-records.md and docs/interaction-cells.md's domains; remaining
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
instructions have been decoded. C differential coverage is 1120 / 17,291
(6.477%) of this still-incomplete decoded inventory. There are
32 tested C routines occupying 2448 original code bytes across images,
with 2991 differential cases and 57 compiled mutations detected. Six bounded
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
