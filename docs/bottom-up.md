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
| 00000..017C6 | entry_services.asm | Entry/service frame; protected views remain separate |
| 017C7..018B1 | game_timer.asm | Untranslated prefix, connected native tail, two live return frames and checksum overlap |
| 018B2..01915 | entry_services_after_timer.asm | EOI leaf, critical error handler and UNKNOWN spans |
| 01916..01F18 | resources.asm | Raw files, selection, special setup and DAT/cache cluster; allocation candidate has unresolved reachability |
| 01F19..0314F | game_code.asm | Simulation-state and creation contracts; native domains remain scoped |
| 03150..03633 | entity_actions.asm | Action dispatch, eight selectors and shared sound/RET tails; UNKNOWN preserved |
| 03634..0368D | entity_drawing_calls.asm | Live record loop, child frames and decimal JMP tail; UNKNOWN 366F and provider/IRQ seams retained |
| 0368E..03789 | level_initialize.asm | Drawing initialization, live clear tail, header and level-state caller |
| 0378A..03943 | level_objects.asm | Record copy, interaction cells and coordinate collector |
| 03944..039CD | game_code_late.asm | Object-animation gate and redraw caller; UNKNOWN preserved |
| 039CE..03AC7 | status_initialize.asm | Initial status copies, wrapped release reload, shared snapshots and actual child frames |
| 03AC8..03CDD | status_display.asm | Status display, actual child frames, shared refresh fields and byte-DIV frontier; UNKNOWN preserved |
| 03CDE..03E6E | entity_selection.asm | Candidate scan, live bucket/index ownership and selected display; UNKNOWN preserved |
| 03E6F..04084 | input_commands.asm | Shared command counters/latches, sound boundaries and visibility child |
| 04085..0410E | game_code_late_after_selection.asm | Remaining input edge/selection suffix |
| 0410F..0414E | view_visibility.asm | Shared visibility producer with live DS/ES, relocated marker segment and existing caller frame |
| 0414F..0418B | game_code_after_view_visibility.asm | Display tail and status text |
| 0418C..04333 | input_poll.asm | Connected mouse, keyboard and live callback input |
| 04334..043CD | port201_input.asm | Port-201 wrappers and measurement; two UNKNOWN bytes retained |
| 043CE..04B5B | input_menu_and_retry.asm | Input/menu and retry suffix; physical order and UNKNOWN preserved |
| 04B5C..04BE6 | decimal_fields.asm | Percent wrapper, shared variable-width decimal fields and fixed three-digit helper |
| 04BE7..052D3 | game_code_late_after_decimal.asm | Display setup, timer and palette callers; mixed ownership remains provisional |
| 052D4..0563D | palette_frontends.asm | Palette pointers, writers and transition callers; ownership/frontier contracts remain explicit |
| 0563E..05725 | palette_steps.asm | Packed/RGB rows and channel arithmetic, tested native contracts |
| 05726..057D0 | entity_dirty.asm | Unchecked visibility gate and live SS dirty rows; actual saved CX/SI and post-store bounds |
| 057D1..05B10 | game_code_late_after_palette.asm | Resource/generator callers; mixed ownership and UNKNOWN preserved |
| 05B11..05CC0 | sprite_banks.asm | Three exact sprite-bank leaves; live SS counts/cursors, byte operands and signed folds |
| 05CC1..05D65 | game_code_after_sprite_banks.asm | Word-mask generator prefix and unresolved suffix |
| 05D66..0616F | entity_graphics.asm | Byte masks, pixel setup/address and entity mask drawing contracts |
| 06170..064D8 | entity_sprite_aligned.asm | Ten literal masked/OR sprite rows, forward masks, DF strings and live DS/RET |
| 064D9..066D6 | entity_sprite_shifted.asm | Independent12/13-row callbacks, unchecked shifts, live first-pass saves and OR plane |
| 066D7..06BDA | entity_sprite_planes.asm | Three-plane narrow callbacks; BP/AX row counters and live phase DI saves |
| 06BDB..06CFB | entity_sprite_wide.asm | Three-plane five-byte rows, live CX counts and OUT-before-mirror initial setup |
| 06CFC..06E82 | entity_sprite_four_planes.asm | Four-plane fourteen-row narrow callback; live AX counts and three DI restores |
| 06E83..06F7A | entity_points.asm | Point-cloud leaf, live point/color tables and nested SS saves; table ownership remains UNKNOWN |
| 06F7B..06FE1 | entity_strip.asm | Two-byte strip with incoming CX source segment, DF strings and actual popped LOOP count |
| 06FE2..0706E | entity_minimap.asm | Signed entity minimap pixel guards, live saved X/table and VGA effects |
| 0706F..0715E | entity_sprite_dispatch.asm | Live entity descriptor arithmetic, optional strip and dynamic callback; unresolved715B retained |
| 0715F..075EE | fixed_pattern_drawing.asm | VGA span copies and literal word-pattern passes; UNKNOWN71CA..7217 preserved |
| 075EF..07629 | status_copy.asm | Full DF-sensitive status-region copy, live DS and single-CALL/fallthrough wrapper |
| 0762A..0780C | status_glyphs.asm | Count and character glyph contracts; five UNKNOWN bytes preserved |
| 0780D..078FF | status_icons.asm | Status outline and restoration; signed selector and live VGA frames |
| 07900..0796E | game_code_before_minimap.asm | Untranslated display preparation |
| 0796F..07A59 | minimap.asm | Column, row and population sample contracts |
| 07A5A..07BB7 | minimap_viewport.asm | Live viewport outline, VGA mirrors and saved phase contract |
| 07BB8..07C66 | object_graphics_tick.asm | Object draw loop and shared animation tail; live fields and stale-BX contract |
| 07C67..08237 | game_code_late_tail.asm | Mixed ownership remains provisional |
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
with four completed mutants. See entity-pattern.md. The full1F19 composition is documented below. The 5DC6 pixel preparation leaf now adds 50 C bytes/22 sites,
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
INT/driver transport. State0008 now adds52 bytes/18 sites/all6 edges in18
core/adapter fixtures with eight mutants; state0002 adds110 known bytes/45
sites/all20 edges in35 fixtures with eight mutants. Their actual pixel, pattern,
mask and PC frames retain live DS/ES/SS/FLAGS. The283B optional bus passes28
additional fixtures/four mutants and extends the existing66-byte translation.
UNKNOWN2382 remains unresolved and excluded. States0010/0020/0040 now add672
unique caller bytes/227 sites in48/24/25 core/adapter fixtures,with eight
completed mutants per state. Their owned jump outcomes are33/13/7; LOOP edges
come from actual original CPU transitions. The shared oracle tracks actual
CALL-specific CS:IP returns when a helper serves several callers. State0010's
pixel exchanges and INT61 restored DS remain live; state0020 preserves its
unsigned threshold and register NEG write phase; state0040 retains the late
callback and post-transition signed clamp. See entity-simulation.md.
State0080 now passes50 core/adapter fixtures:337 known caller bytes/115 sites/
all44 actual owned outcomes,8,796 events and eight completed mutants. Four
UNKNOWN holes remain excluded. Its pixel/stroke,dual sound transport,live AX/ES
frames,wrapped+21 counter and late callback transitions compose the tested
children. State0100 passes19 fixtures:83 caller bytes/22 sites/all4 outcomes,
2,726 events and six mutants,retaining separate cadence memory RMWs and actual
pixel/pattern frames. These add420 unique bytes; see entity-simulation.md.
States0200/0400 and the8000/flag80 entries now add938 unique bytes/309 sites/
112 unique owned outcomes in46/24/31 core/adapter fixtures,with9/8/6 completed
mutants. They compose native mask,coordinate,pixel,sound and finish contracts;
UNKNOWN2ABD/2ADB/2AEB and pair-source extent remain unresolved. Same-target
conditional transitions count once while their live reads/flags remain tested.
State0800 now adds473 known caller bytes/157 sites/all70 unique owned outcomes
in177 core/adapter fixtures,with80,208 events and nine completed mutants. All130
signed thirteen-row mask selector handoffs execute; UNKNOWN2B50 remains excluded.
AdvanceEntityRecords1F19 now connects all states in44 core/adapter fixtures:
299 additional outer bytes/108 sites/all81 feasible owned outcomes,6,768 events
and eight completed mutants. The composed3,744-byte/1,255-site body overlaps
existing C scopes; byte/site accounting unions them.
Preserve actual setup/countdown returns, live ES saves/DS counter, cached state
priority and scan candidate RET203B leaving guard/request intact. Only the taken
1FE3-to1FE8 edge is locally infeasible under the frozen nonzero AX/mask union;
shared1FE8 remains executed through state JMPs.
CreateEntityRecordIfDue30A6 now passes273 core/actualRET-adapter fixtures:
170 bytes/54 sites/all13 outcomes,50,262 events and eight completed mutants.
The equality limit,bound50h coordinate-source clear,byte MUL,late callback and
live final bound remain explicit. The31E5/3287 feedback tails add59 unique bytes
in68 core/actualRET-adapter fixtures,all20 sites/12 outcomes,3,786 events and
eight mutants,with native INT60/61 children and live returned-DS gates.
The01B0/01B3 prefix connects creation and update through their actual CALL/RET
frames in17 core/adapter fixtures:6 caller bytes/two sites,5,708 events and five
mutants. It stops01B6 before3944,without claiming the whole main loop.
The basic2/3/4 actions now add107 known bytes/31 sites in39 core/adapter
fixtures,with18 conditional outcomes plus4 directJMPs,1,122 events and seven
mutants. The3150 prefix owns113 known bytes/43 sites/all28 conditional
outcomes. It composes all eight actions and shared feedback without adding
frames; current full-parent evidence is recorded below.
The advanced6/7/8/9 cluster now adds534 known bytes in186 core/adapter
fixtures,all150 sites/66 outcomes,10,154 events and ten mutants. Selector5 adds
408 bytes in56 fixtures,all158 sites/73 outcomes,6,586 events and eight mutants;
two native producer/restorer handoffs check all nine saved map cells. The full
3150 composition passes290 fixtures,43 own sites/28 outcomes,376/402 integrated
sites and six mutants; independent leaf matrices jointly cover all402 known
sites. All eight cores share a typed register boundary and bounded test transport.
Shared feedback and live outer returns retain their explicit segment/IRQ seams.
All31 UNKNOWN bytes remain unresolved. The physical3150..3633 block now lives
in entity_actions.asm,followed by the separate untranslated draw-call module.
The left-aligned4B68/4BBE formatter and393-known-byte3CDE candidate selector
now have scoped native acceptance, detailed below. Stale zero-bound outputs,
last-hit bucket ownership,live count/index and mask0002 selection remain intact.
See entity-actions.md and next-work.md for exact contracts and open platform duties.

Translated byte accounting validates explicit C domains against complete decoded
instructions in the image. Shared tails may precede or follow the physical entry
prefix; entry+size is not a bound on a logical shared body. Partial instructions,
unresolved bytes and image overflow remain errors,with focused regression tests.
This static ledger union does not renew behavioral reports or aggregate acceptance.

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


Candidate selection3CDE and both variable-width formatter entries4B68/4BBE
now have scoped native acceptance:393+90 unique bytes,51 parent fixtures at
both boundaries and1,064 formatter boundary cases. The parent retains live
bucket/index ownership, record182/display overlap and the real formatter
return. See entity-actions.md and decimal-field.md. Their maintained physical
modules are entity_selection.asm and decimal_fields.asm; surrounding suffixes
retain exact image order and all UNKNOWN classifications. The3ACE status
connection is recorded below.
Their live1FEC source-buffer producer/consumer contracts are recorded in
status-display.md. These scopes
do not accept allocation extents, live IRQ scheduling or full main-loop behavior.
Four focused native selection-to3150 data handoffs check preferred and forced
fallback buckets against selectors2/3/4, without claiming the intervening3AC8
display call or adding translated bytes.

The viewport7A5A and two icon leaves780D/789E now have native acceptance over
350+243 unique bytes; the actual column/viewport CALL prefix3AC8..3ACD adds
six caller bytes. The three suites pass46,512 and12 fixtures respectively at
core/adapter boundaries, with nine,nine and five completed mutants. Exact ASM
modules preserve physical order and classifications. The prefix's3ACE exit has
an explicit suffix entry so dependency views retain its separate scope.
At that checkpoint the main-image translated-byte union was17,078,
up599 from16,479; this ledger total is separate from full-campaign acceptance.
See minimap-viewport.md, status-icons.md and status-display.md.

The762A count and7708 character leaves now add478 known C bytes, bringing the
main-image ledger union to17,556. Their maintained status_glyphs.asm module
retains all483 physical bytes, including five UNKNOWN holes excluded from C.
The focused gates pass270 and269 core/adapter fixtures,105/118 sites,12/30 jump
outcomes and seven/nine completed mutants. Actual count/remainder, DI, DS and RET
stack words, the three character passes, signed dispatch and space/invalid IF
contracts remain live. The417B NUL-scan caller now passes18 core/adapter fixtures,
11 own sites/three jump outcomes,34,102 events and seven completed mutants.
Its17 caller bytes take the main ledger union to17,573 without recounting the
child. It retains actual CALL/RET, saved AX/SI/DS, live NUL, DF and AH wrap;
independent planes cover the stored40-byte status line. There is no runtime
40-character bound.
Release/icon snapshot and refresh fields remain shared with input gates as
documented in status-display.md. This checkpoint is scoped evidence only.

The3ACE suffix now passes29 core/adapter fixtures, all172 sites/all73 jump
outcomes,48,738 ordered events and eight completed mutants. The full3AC8
caller passes10 focused handoff fixtures/13 comparisons,163/174 owned sites,
68 observed outcomes,43,068 events and three completed mutants. Its minimap
prefix flows directly into the suffix with no new guest frame and with all
live child-returned segments/registers. Divide overflow stops before3AED;
changed child targets stop before outer RET. UNKNOWN3B08 is excluded.
The suffix adds527 unique main C bytes, taking the union to18,100; full-entry
and child ranges are not counted again. See status-display.md for scope and
input hashes. Fresh views select3944 and shared7C0A..7C66 next (104 bytes/
39 sites), followed by7BB8's32-object draw loop and its native8822 child.
The zero-X stale-BX store, low-byte type gate, live animation flags/frame
fields and actual far-render frames now have the following scoped gates.

The3944 gate and shared7C0A tail pass61 fixtures/134 core, adapter and selected
null-bus comparisons:104 unique bytes/all39 sites/all17 jump outcomes,22,816
native ordered events and eight completed mutants. Its direct tail overlaps
the same93 bytes; no frame is added at the JMP. The7BB8 drawing caller passes
50 constructed fixtures plus one native animation handoff,55 comparisons,
all33 owned sites/all4 jump outcomes,346 integrated sites,30,706 events,109
independent plane checks and six completed mutants. The typed8822 child owns
its platform/IRQ and missing-byte-provider seams. Live returned DS/ES and
actual SI/DI/CX/IP/CS stack words determine every subsequent step.
Only186 unique bytes are added, taking the main C ledger union to18,286.
See object-records.md and the two matching-input reports. No aggregate or
full-tick readiness follows from these scoped gates.

The7602 copy leaf and75EF single-CALL/fallthrough wrapper now pass16 combined
fixtures/32 core and adapter comparisons:59 unique bytes/all22 sites/no jump
edges,155,458 ordered bus events and seven completed mutants. Each pass copies
all06E0 source bytes with DF, live savedDS/RET, VGA overlap and ordered mirrors.
The39CE initializer now composes these copies, ten count calls, decimal field
and icon outline in15 fixtures/30 comparisons:250 new bytes/all70 caller sites/
no owned jump edges,234,488 events and eight completed mutants. Another256
original-only rate prefixes verify the byte arithmetic independently. Live DS,
snapshot/counter order and changed child targets remain explicit, including the
same-IP39D1 nested stop and mirror-induced count return080C.
Together these scopes add309 unique main bytes, taking the ledger union from
18,286 to18,595. See status-display.md and the matching-input native reports;
this does not refresh aggregate campaigns or establish complete gameplay.
The6FE2 minimap pixel now passes40 fixtures at both APIs plus4 null-bus repeats:
141 bytes/all58 sites/all5 jump outcomes,2,096 ordered events and eight mutants.
The410F producer passes28 fixtures at both APIs:64 bytes/all27 sites/no jump
edges,14,672 events and eight mutants, including exact loaded views at0/1010/2345.
The5726 dirty consumer passes33 fixtures at both APIs:171 bytes/all73 sites/
all25 jump outcomes,7,690 events and seven mutants. Two actual native producers
also feed4 accepted/rejected data handoffs (598 additional events), preserving
the original live memory and explicitly prepared caller frames. The handoff is
not execution of3634. The producer's relocated segment, DF, live ES and marker
reads, and the consumer's raw SS output and saved CX/SI remain explicit.
Only376 unique bytes are added, taking the main C union to18,971.
See entity-display.md. That checkpoint selected6E83's live point/color tables
and count; the subsequent leaf acceptance is recorded below.

DrawEntityPointCloud passes 31 fixtures/62 core and actual RET comparisons: 248 bytes/all 110 sites/all 17 jump outcomes, 292,396 ordered bus events and 10 completed mutants.
DrawEntityTwoByteStrip passes 26 fixtures/52 core and actual RET comparisons: 103 bytes/all 47 sites/all 2 jump outcomes, 6,928 ordered bus events and 8 completed mutants.
The point gate adds four null-bus repeats and completes the original zero-count
65,536-iteration scan at both APIs. The strip gate independently checks
2,816 plane-byte writes and finite saved-count providers, including a nine-row
expansion. Full RAM, returned roles, defined FLAGS and ordered bus/device
state match original ASM. These disjoint leaves add351 unique main C bytes,
taking the ledger union from18,971 to19,322. The live table bases retain
UNKNOWN ownership and no new bounds or immutability claim. Reports are
build/entity-points-differential.json and build/entity-strip-differential.json;
only matching scopes/input hashes establish these focused results. This does
not refresh aggregate campaigns or establish whole-game acceptance.
That checkpoint selected6170 source/descriptor ownership; the acceptance below
records its callback and the two shifted siblings before the wider706F/715B domain.

The aligned6170 and shifted64D9/65D8 callbacks add 1,383 unique main C bytes,
taking the ledger union to20,705. Their84/132 core/adapter comparisons cover
730 sites and24 jump outcomes with20 completed mutants. Original5B11/5BB0
output supplies eight aligned and two shifted data handoffs; those producers
remain untranslated and their sites/transactions are recorded separately.
The512 original-only prefix probes verify all256 shifted counts at both entries.
See entity-sprites.md and the matching-input reports for exact native domains.
That checkpoint selected66D7 and its five remaining siblings before706F/715B.

The six remaining callbacks now add 1,964 unique main C bytes, taking the
ledger union to 22,669. Five narrow callbacks share the semantic shifted-row
helpers while preserving distinct BP/AX counters and three/four plane frames.
The five-byte wide callback retains its different OUT/mirror order, live CX
counts, DEC/JZ versus LOOP, and 27h pitch. Their 144 core/adapter comparisons
cover 985 sites/103 branch outcomes with 20 completed mutants. Five independently
checked 5BB0 banks and all eight checked 5C06 banks feed unchanged RAM handoffs;
producer bytes/sites/transactions remain separate from the consumer C union.
Another 1,280 original-only shift-prefix probes check all 256 CL values at each
narrow entry, saved SI and defined FLAGS. See entity-sprites.md for scopes.
That checkpoint selected 706F before the enclosing 3634 loop. Initial callback
slots do not close arbitrary live targets, and finite fixture evidence does
not close IRQ, provider, allocation or complete gameplay domains.

The 706F sprite parent now adds 240 unique main C bytes, taking the ledger
union to 22,909. Its 45 fixtures/90 core and actual-RET comparisons cover all
113 parent sites/15 branch outcomes, with 63,950 ordered events and ten
completed mutants. The integrated nine-callback/strip domain is 3,690 bytes,
1,875 sites and 144 branch outcomes; existing child bytes are counted once.
Actual original producer banks pass through normal record selection unchanged.
Live selector/callback/DS/DI/return-word changes and the physical FFFFF-to-zero
word boundary remain explicit. See entity-sprite-dispatch.md and the matching
report inputs. Next connect the 3634 record loop and its frame-free decimal
tail, preserving UNKNOWN 366F and the live DS:0050 guard.

The 3634 loop now adds 89 unique main C bytes, taking the union to 22,998.
Its existing 86-byte decimal tail is composed without a synthetic frame.
The 37 fixtures/74 comparisons cover all 35 body sites and 12 branch edges,
with 53,510 ordered events and ten completed mutants. The integrated domain
contains 4,425 bytes/2,191 static sites; this scope executes 2,002 sites and
127 edges. Live saved DI/CX, returned DS, the guard and outer caller word
remain authoritative. UNKNOWN 366F is excluded. See entity-drawing.md.
Next audit-to-C acceptance is the 5BB0 copy/OR-mask producer, whose normal
bank witnesses do not establish zero-count, DF, overlap or stack-alias behavior.

The 5BB0 copy/OR-mask producer now adds 86 unique main C bytes, taking the union
to 23,084. Its 35 fixtures/70 comparisons cover 45 sites/eight branch outcomes,
287,970 events and ten mutants, with 4,544 independent output-byte checks. Five
actual native producer/consumer handoffs compare ten additional phases and
retain unchanged banks; their sites/events remain separate. Full zero counters,
DF/overlap, live saves/RET, signed fold and byte-EA versus word-physical wrap
remain explicit. See sprite-bank.md. Next translate the 5B11/5C06 sibling leaves
before the 59BB caller; ordinary producer witnesses do not close alias domains.

The two shifted sprite-bank leaves now add 346 unique main C bytes, taking
its union to 23,430. The 5B11 leaf passes 40 fixtures/80 boundaries, all 74 sites
and 17 outcomes, 236,282 ordered events, 56,016 independent byte checks and
ten completed mutants. The 5C06 leaf passes 33 fixtures/66 boundaries, all 80
sites and 17 outcomes, 913,554 events, 20,480 independent byte checks and ten
mutants. Live saved DI becomes mask SI in the wide leaf; saved counts/cursors,
full 255-bit shifts, byte EA wrap, DF independence and signed folds remain explicit.

Both native producers feed all eight unchanged banks into native callbacks in
nine phases per chain, through the same RAM object. Their 720/5,120 bank bytes
and consumer sites/events are kept separate from producer acceptance. The three
leaves now occupy the exact 432-byte sprite_banks.asm physical module, with
start/end assertions and unchanged emission/classification. See sprite-shift-banks.md
and sprite-wide-banks.md. Next connect their 59BB caller; full resource/provider,
allocation, timing and gameplay domains remain open.

The complete 59BB sprite transform now adds 262 unique main C bytes, taking
its union to 23,692. All three native children share canonical RAM and actual
near frames. The 24 fixtures/48 boundaries cover all 114 parent sites/30 parent
outcomes and 694 integrated bytes/313 sites/70 executed outcomes. Ten completed
mutants, 2,787,712 bus events and 455,752 independent byte checks include two
complete 337-call inputs at both APIs. Pinned MAIN.DAT section zero exactly
fills the 5270h source span and produces 194B8h bytes. Live saves, flowing ES,
changed returns, zero LOOP wrap, DF, overlap and VGA domains remain explicit.

This campaign uses bounded packed traces and separates executable input hashes
from progress prose/the raw symbol ledger, while the generated header and exact
ASM verifier still pin names/offsets and physical bytes. See entity-sprite-banks.md.
Next audit 5CC1's table/selector ownership and frame-free 5CDD tail, then 57D1,
before connecting 58D2; its retry/fatal/provider seams remain open.

The 5CC1 prefix and 57D1 leaf now add 114 unique main C bytes, taking the
union to 23,806. Fixed-word banks pass 15 fixtures/30 boundaries, all 46
integrated sites/ten outcomes, 197,574 events, 23,040 independent output bytes
and ten completed mutants. The prefix adds 28 bytes; its 59-byte shared child
is already counted. The VGA plane copy passes 21 fixtures/42 boundaries,
86 bytes/all 45 sites/four outcomes, 78,878 events, 25,696 independent plane
bytes and ten completed mutants. Both preserve live SS words, DF, wrap, aliases
and actual returns; the fixed generator's final tail adds no frame.

The 1FEA selector, two 96-byte sources, 0900h-byte normal output and 144-byte
consumer slices are statically accounted for without reclassifying UNKNOWN
storage. Sections 2/6 also pass their complete normal VGA copy profiles. All
seven MAIN.DAT section sizes are statically recorded, including section 1's
0184h-byte mask source and the adjacent section 3/4 destinations. See
fixed-word-banks.md, vga-plane-copy.md and main-resource-sections.md.
The next composition at that checkpoint was 58D2's twelve actual CALLs, live
DS/BX saves, no-op stack traffic and neutral 200E gate, retaining retry/fatal
seams. Only matching focused report inputs establish a checkpoint; aggregate
acceptance remains separate.

The 58D2..59BA parent now adds 233 unique main C bytes, taking the union to
24,039. Fourteen fixtures/28 boundaries cover all 101 parent sites/two branch
outcomes, with ten completed mutants. Seven full pinned cases verify the
complete section stream for their gate and all 337 sprite calls. The original
composition exercises 800 sites/147 branch outcomes, without closing all child
domains. Shared references retain both boundaries from one execution:
47,410,976 original instructions and 3,788,588 raster events; the compared
boundary sum is 7,577,160 raster events and 276 DOS events.

Live DS/BX saves, changed loader/top graphics/nested sprite returns, actual outer
RET, second-load relocation, late CS:5968 changes, exact-FF selection and
fatal1949/04D0 all pass. Retry recovery retains the declared 4B1C service and
DAT retains its direct-RAM child domain. ConfigurationOption200E records the
startup/option-parser/configuration provenance without guessing a narrower
semantic meaning. Packed traces, fail-stop callbacks and 1,500-second/512-MiB
worker limits remain mandatory. See main-resource-sections.md.

Next use the generated word bank in its unchanged consumer chain: translate
715F (107 bytes/48 sites), then 7218 (983 bytes/556 sites), then their 5827
caller (88 bytes/33 sites). The static fixed-pattern-drawing.md contract records
the live PUSH DX/POP DX around MUL, PUSH ES/POP DS, DF/IF and VGA ordering,
144-byte slice choice and rotating VGA slots. Pointer-coordinate producers and
the EntitySelectionPresent cross-use are identified; byte1FE0 and wider alias,
allocation and visual semantics remain open. UNKNOWN71CA..7217 stays unresolved.

The fixed-pattern chain now adds 1,178 unique main C bytes, taking the union
to 25,217. Its 715F copy leaf passes 21 fixtures/42 boundaries, all 48 sites/four
LOOP outcomes, 9,156 ordered events, 5,376 independent plane-byte checks and ten
completed mutants. Its 7218 renderer passes 36 fixtures/72 boundaries, all 556
sites/no branches, 28,368 events, 10,560 independent plane bytes and ten mutants.
The native word producer's complete 0900h-byte output supplies 16 bank/shift
consumer fixtures through canonical RAM snapshots, with separate producer,
consumed-byte and plane-check counts. This is not full startup composition.

The 5827 parent passes 43 fixtures/86 boundaries, 33 own sites/two own outcomes
and 637 integrated sites/six outcomes, 53,900 events and ten completed mutants.
It shares canonical RAM with both children, retains changed child/outer words,
the real SS=A000 hardware-return quirk, saved DS, exact-FF selection and live pair
swaps. DF/IF, full MUL, wrapped coordinates and ordered VGA traffic remain
explicit. All suites use 420-second/384-MiB workers and bounded fail-stop traces.
See fixed-pattern-drawing.md. The physical 1,168-byte fixed_pattern_drawing.asm
module retains all 78 UNKNOWN bytes between the leaves and exact assertions.

Next audit/translate 587F's fixed relocated mirror-frame restore and 04F9's
initialization producer. Their fixed ES frame is distinct from live SS, despite
normal startup making them equal. The literal 0549 store overwrites SS:0010
instead of initializing SS:000E. Caller INT62/IRQ/chaining seams remain open;
see vga-mirror-restore.md. No broader interrupt/game acceptance is implied.


The mirror producer/consumer now add 168 unique main C bytes, taking the ledger
union to 25,385. InitializeVgaRegisterMirrors is 85 bytes/25 sites and
RestoreVgaRegisterMirrors is 83 bytes/38 sites, both call-free and branch-free.
Their paired suite passes 30 single fixtures at both boundaries and two direct
same-RAM native chains: 64 comparisons, all 63 sites, 2,064 original instructions,
1,870 ordered events and ten completed mutants. The independent ADD truth table
has 768 original-opcode checks; it is not extra C comparison/site coverage.

The original relocated mirror segment, live SS, late CS operand, actual CX/ES/RET,
ordered ports and flag phases remain distinct contracts. Initialization preserves
its SS:0010 overwrite and untouched SS:000E. A real stack/code overlap has an
independent native-only 31-event witness, explicitly excluded from original
execution counts because Unicorn cannot commit its self-code-page PUSH. No
manual replacement instruction is admitted into the original oracle. See
vga-mirror-restore.md for exact domains and the 420-second/384-MiB limits.

The suite imports its decoder and device fixture directly, keeping its causal
input closure to 21 paths without initializing unrelated sound models. Raw ledger
status/progress prose do not renew or invalidate behavioral evidence; generated
names and offsets still pass the independent exact gate. This is a translated
ledger checkpoint with scoped matching reports, not aggregate acceptance.

Next compose MouseIrqBridge with its external INT62/full-register/live-frame
provider seam. The gate at CS:83BE has a direct zero writer at00FE; neither gate
edge is discarded. Neutral counters2002/2003 retain returned-DS accesses. The
following timer order and overlapping119/116-byte prefix/tail are recorded in
timer-frontier.md; UNKNOWN18B7..18F7, indirect42A5 and IRQ timing remain open.


MouseIrqBridge now adds 48 unique main C bytes, taking the ledger union to 25,433.
Its 35 fixtures/70 core-adapter comparisons cover all 20 parent sites/four JNZ
outcomes, 44 actual mirror calls and two direct same-RAM initializer handoffs.
The 83-site union separates 20 parent/38 child/25 producer sites; the 2,869 original
instructions include 50 producer instructions. Bridge accesses separate 2,988
identified-body, 1,072 declared INT62 transport and 184 provider events, with 52
initializer events reported separately. Ten completed mutants pass detection.

The typed external service stops before IRET and can return full DS/ES/SS/SP/
FLAGS and canonical-memory effects. Real nested/outer frames, current IVT,
returned counter frame, live saved words and changed-target stops are retained.
The constructed VGA-stack case reads the complement of the stored 0F9C child
return after mirror restoration; F063 remains a stop. This does not execute an
external ISR or establish IRQ/debug timing. Reusing the tested mirror oracle
keeps the new report closure to 24 paths; no shared oracle semantics changed.
See mouse-irq-bridge.md for limits, exact scope and the declared vector read order.

Next close 18B2, then known dependencies of 3E6F/418C before the shared 183E timer
tail. The 42A5 frontier, unknown bytes after 18B6, prefix polling/platform seams
and asynchronous execution remain open. The timer-frontier.md split prevents
double-counting its overlapping prefix/tail domains.

The EOI/port-201 cluster now adds 157 unique known C bytes, taking the main
ledger union to 25,590. Its 51 fixtures/102 comparisons cover all 75 sites and
eight edges, 3,444,790 original instructions and 328,314 ordered events, with
ten completed mutation detections. The physical port201_input.asm module keeps
its two UNKNOWN bytes; its 152 known bytes compose the two wrappers and their
measurement child. The input/menu suffix remains separate in physical order.

The contract preserves live DS:0051 after IN, CALL and outer-RET aliases,
DL-only gating, signed halves of wrapped counters, high-only copies and the
zero-byte XOR AH flags. Providers remain finite constructed inputs, with no
hardware timing or IRQ claim. See port-io.md for the scoped 23-input report and
worker limits. Next close 4252's mouse seam and 3E6F's shared-field ownership,
then compose the understood 418C paths while retaining indirect 42A5 explicitly.

The shared-verifier/input milestone now connects 418C to the native mouse and
port children: 576 known bytes/243 sites/91 direct jump outcomes, including 424
new C bytes. The ledger union is 26,014. Its 63 fixtures/126 comparisons and seven
completed mutants cover the supported callback identities and explicit stops.
The port regression retains its original accounting after migration. New focused
suites share tests/verification.py; precise current work is in next-work.md and
older checkpoint narrative is retained in convergence-history.md. Next close
3E6F's shared fields and sound seams before composing the timer tail.

The next checkpoint closes that scoped 3E6F parent: 530 new known C bytes take
the main ledger union to26,544. Its65 fixtures/130 comparisons compose the actual
410F child and cover220 sites/121 feasible direct outcomes; two known comparisons
and three outcomes retain a separate synchronous-entry infeasibility proof.
Five completed mutants and independent map/counter/release expectations pass.
INT33 and INT60/61 now share native interrupt transport and the common verifier;
the relocated4137 operand remains live at its original execution phase. UNKNOWN
bytes and opaque service bodies remain open. Next compose183E with those scoped
children and the saved-INT08 seam; see input-commands.md and next-work.md.

The timer-tail checkpoint now connects that seam and those children in1,374 known
bytes. Its116 new C bytes take the main ledger union to26,660. The48 fixtures/96
comparisons cover all49 own sites/15 direct outcomes,443 integrated sites/101
outcomes and five completed mutants. The shared verifier executes the actual far
JMP and hardware IRET while separating opaque-service return transport. Returned
DS/SS:SP, actual saved words and both frames stay canonical. The119-byte prefix
and asynchronous scheduling remain open; next investigate5473/553D before full
handler composition. See timer-frontier.md for field initialization and limits.

The palette timer checkpoint closes5473/553D with548C and the existing5425 leaf.
Its135 new bytes bring the main C ledger union to26,795. The169-byte connected
domain passes67 fixtures/132 comparisons, all81 sites/20 branch outcomes and
five completed mutants through tests/verification.py. LOOP outcomes now join
the shared branch accounting; original instruction execution is unchanged.
Two full zero-count loops remain bounded under384MiB, with cleanup on failure.

The ownership audit connects transition writes at2638 to both timer RGB halves
2638/2650 and identifies2668 as slot7's live source. Initial UNKNOWN zeros do
not prove initialization or allocations. Actual stack/control reads and tail
returns remain canonical; no palette shadow state is added. Fresh17C7 tree and
bottom-up views leave only its119-byte prefix before connected full-handler
acceptance, retaining the tested5827 domain and input/ISR platform seams.
See next-work.md and palette-pointer-frontier.md for those limits.

The next milestone connects the full17C7 handler using that same machinery.
Its119 new prefix bytes bring the main ledger union to26,914; the235-byte
handler includes the already counted116-byte tail. Actual register saves,
relocated DS operand, CRTC word output, byte-only status-port adjustment, finite
polling, PIT output and palette/pattern CALL frames now reach the tested tail.
The2,840-byte connected domain passes93 fixtures/186 comparisons,109 own sites/
36 outcomes and five completed mutants; integrated coverage is1,223 sites/150
outcomes. Native memory, frames, returned segments and hardware IRET stay live.

The shared verifier now separates word/byte output availability and tracks MUL's
undefined arithmetic flags for the fixed-pattern child. The full-entry suite
reuses the narrower tail's fixture/service and native bindings; it adds no CPU,
bus or comparison engine. The tail regression preserves its original accounting.
Next connect the54-byte menu timer and timer installers as one IRQ lifecycle,
retaining the unknown callback/provider/timing seams. See next-work.md.

The menu lifecycle now connects4C47 and direct installer5028 through the same
shared verifier and native interrupt transport. Its73 new known bytes take the
main C ledger union to26,987. The654-byte connected domain passes54 fixtures/
108 comparisons,42 own sites/three direct outcomes and eight completed mutants.
Three installer/IRQ handoffs use actual same-memory results at separate loads;
hardware entry remains an explicit constructed boundary, not a scheduler.

Unlike the game IRQ, the menu saves eight words without ES or entryFLAGS and
sends EOI only at modulo phase0. Returned DS/SS and live ES remain observable.
The installer writes actual IVT words before popping savedDS, retaining aliases
that change that pop or outerRET. UNKNOWN4C65 is unchanged. Next close1644's DOS
vector/PIT installation and then the keyboard producer/installer lifecycle;
see menu-timer.md and next-work.md.

The1644 lifecycle checkpoint adds82 bytes and takes the main ledger union to
27,069. Its50 fixtures/106 comparisons cover all42 installer and19 cleanup sites,
13 installer outcomes and six completed mutants. Three same-RAM handoffs compose
direct menu installation, DOS game/sound-vector installation, the installed game
IRQ and actual-INT1A cleanup in a2,984-byte known domain. Reused fixtures retain
original instructions and canonical buffers; no new verification engine is added.
Live returnedSS/DS, relocated1653, byte-only port arithmetic, post-poll reload and
IVT/stack aliases remain explicit. Fresh graph views identify17BE's9-byte
port64/LOOPNE wait before17B4's10-byte command parent; the zero CX loop can take
65,536 samples. Next connect those leaves and keyboard producer16D4/installer1562
to the accepted input consumer; see timer-install.md and next-work.md.

The keyboard checkpoint adds275 bytes, taking the main ledger union to27,344.
Wait17BE, command17B4, IRQ16D4 and installer1562 compose EOI/input in856 known bytes.
The592 fixtures/1,205 comparisons cover119 own sites/35 outcomes and seven mutants;
three same-RAM install/IRQ/input handoffs use pinned bindings and four make/break
transitions. ZeroCX permits65,536 busy samples; special7D/7E zeroAX before lookup,
including releases. ReturnedDS/SS, actual saves, repeated reads and bitmap bounds
remain explicit. Fresh4D1A graph views identify the51-byte repeat/character reader
as next connected leaf. Its202E XLAT base overlaps the last201F binding byte;
keep both consumers on canonical RAM. See keyboard-input.md and next-work.md.

Reader4D1A and menu scale span4A9F..4AB4 add73 bytes, taking the main ledger union
to27,417. The existing keyboard campaign now covers961 fixtures/1,938 comparisons,
152 own sites/49 outcomes and11 mutants in947 known connected bytes. IRQ-produced
94 emits through live202E XLAT and leaves93; the actual menu loop consumes19 more
display/read iterations, reloads86 and stores scale1 before JMP4401. Hardware
entry remains constructed; the surrounding43F2/4401 domain is still untranslated.
Both reader RETs, AH, second reads, byte underflow and the shared final binding
byte stay explicit. Fresh43CE graph views identify its36-byte port/latch choice
as the next leaf before controller-selection/calibration composition; see
keyboard-input.md and next-work.md.

The active input-menu checkpoint adds165 unique bytes and takes the main ledger
union to27,582. Choice43CE and4A2E..4AC4 now compose native text/glyph/bitmap,
display, port calibration and input in5,974 known bytes. The1,262 fixtures/2,511
comparisons cover215 own sites/77 outcomes and15 mutants. Actual pinned prompts
render through C; three14-stage same-RAM handoffs reach calibrated pointer motion.
Existing scale/controller spans are unioned once. ExactFF mouse gating, escape
preserving mode, full AL/AH/CH and returned frame/segment effects remain explicit.

The shared verifier now supports declared plainRETF with the established isolated
read-hook workaround while executing the unchanged original instruction. Frame
observations and opaque interrupt transport are separate. Selector-EA wrap at
SPFFFE/FFFF fails explicitly pending independent evidence; it is not a proven C
domain merely because the ordinary far-return tests pass. Next connect screen
preparation4A01..4A2D before broader43F2 composition; see verification.md and
next-work.md for retained platform, callback and UNKNOWN frontiers.


Screen preparation4A01..4A2D adds45 bytes, taking the main C ledger union to27,627.
The complete196-byte input-selection continuation now composes clear, layout,
palettes, background, pinned text, page copy/display and active choice/calibration.
The shared keyboard campaign passes1,289 fixtures/2,541 comparisons,229 own sites/
79 outcomes and17 mutants in6,750 known connected bytes. Six same-RAM handoffs
include prepared screen -> calibration -> input, preserving actual configuration.
Plane equality,640x350 layout, live prompt gating and changed return frames remain
explicit. Peak trace329,527 events stays under the screen's600,000-event limit and
384MiB worker cap; the shared engine is unchanged. No aggregate or SDL3 acceptance
is implied. Fresh4FF8 graph views put its ten-record initializer before4F96's
renderer; audit eleven-byteDS4960 records and upstream graphics producers next.


Menu animation4FF8/4F96 adds129 bytes, taking the main C ledger union to27,756.
The ten eleven-byteDS4960 records now have a connected initializer/countdown/
bitmap contract: exact8000 disable,FFEF reload, paired frames,live savedSI/CX and
actual near/far returns. Its70 fixtures/791 comparisons cover54 own sites/13
outcomes and five mutants in4,835 known bytes. Three same-RAM218-tick cycles
consume initializer output and complete every enabled pinned record's first
reset, without copying game records. BP1 bypasses clipping; extreme coordinates
retain original wrapped drawing. The final record byte and upstream bank extents
remain unresolved. Next audit4F6E/4F4A/4F2B plus4EEF drawing parents and their
CS4F8A table before composing more of43F2; see menu-animation.md and next-work.md.


The4EEF/4F2B/4F4A/4F6E menu drawing cluster adds155 bytes,taking the main C union
to27,911. It reuses the existing menu module and shared suite:112 fixtures/841
comparisons cover118 own sites/15 outcomes and nine mutants in4,990 known bytes.
Actual near/far frames,the second row's fallthrough,live CS words and saved AX/CX
remain explicit. Decoded pinned section3/4 bytes now feed the native drawing.
Compact optional shared traces preserve every event within384MiB; ten shared
native suites regress the storage/default paths. The artificial VGA-stack fixture
still fails its original instruction budget and has no parity/mutation credit.
The long distinct-DS fixture does complete its256-shift behavior. Next close
4E37/4EA2's cached two-page drawing ownership and CS4EE7 table before broader
43F2 composition; see menu-animation.md,next-work.md and verification.md.
