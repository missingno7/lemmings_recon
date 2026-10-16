# Precise next frontier

## Current checkpoint

The main-image translated-code ledger union is 20,705 bytes. The latest scoped
acceptance adds the 6170 aligned sprite and 64D9/65D8 shifted sprite callbacks:
1,383 unique bytes, 730 sites, 216 core/actual-RET comparisons and 20 completed
mutants. The two native reports compare 101,980 ordered byte-bus events and
39,360 independent plane-byte writes. The original-only shift matrix covers all
256 counts at both shifted entries, separately from the native comparisons.

Original 5B11/5BB0 producers independently verify 720/72/78-byte source banks
used unchanged by ten consumer handoffs. Their transactions/sites stay separate
and their code remains untranslated. See entity-sprites.md for layouts, live
segments/stack effects, the static 59BB cursor calculation and report scopes.

Fresh 706F dependency views select the six remaining callbacks, beginning at
66D7 (320 bytes/159 sites). Trace its bitplane/row descriptor inputs and live
saves before translating it; 6817/6957/6A97/6BDB/6CFC follow. These six leaves
own 1,964 known bytes. The parent still has the open CALL AX domain at715B,
the actual saved target/DI words, and the optional7152->7155 strip handoff.
Complete those dependencies before connecting the enclosing3634 record loop.

This is focused acceptance. Full campaigns and matching inputs remain necessary
for aggregate acceptance, and SDL3 follows the portable core.

## Retained terrain campaign

The last complete terrain campaign passed: `tests/terrain_stream.py` verifies 192
cases, including all 80 pinned LEVEL streams at both entries, 32 auxiliary
core-boundary comparisons and two completed mutation witnesses. The report has
1,383 integrated instruction sites and 195 edges, with 23,324 independent body
plane checks in its recorded cases. No stream or viewport was shortened.
See terrain-stream.md and `build/terrain-stream-differential.json` for the exact
input hashes and domain. Partial journals remain diagnostic only.

The affected child gates also pass: 449 terrain-reader cases and 609 packed
terrain-piece cases, with three and five completed mutants respectively. The
fast static gate still reconstructs all four component images exactly. These
are scoped results, not aggregate C coverage or complete gameplay acceptance.
Subsequent ledger/header/runner edits change report input hashes, including
those of the retained terrain report. These completed runs are historical
evidence for their recorded inputs until refreshed; they do not establish
current aggregate acceptance. Do not repeat the long terrain campaign solely
to refresh unrelated leaf work.

## Normal-path convergence

The 283B..287C leaf now has maintained ASM contracts and a logical C core plus
register adapter with focused acceptance: 37 fixtures at both boundaries, all
37 instruction sites and four completed mutants. `CopyEntityPatternToInteractionMap`
retains the live DS record, SS saves and return word, DF-sensitive string order,
wrapped coordinates and literal row adjustments; see entity-pattern.md.
The producer at 3464..34C7 saves the previous interaction cells while installing
02/0A/03 rows. This closes the pattern ownership question without assigning full
semantics to the surrounding simulation states.

The 5DC6..5DF7 `PrepareEntityPixelSample` leaf now has maintained ASM and a
logical C core verified in 39 fixtures at both boundaries, covering all 22
sites, both JNS edges and four completed mutants; see entity-pixel.md. Eight
stored bytes at EF0C..EF13 are identified as `PixelBitMasks`, preserving the
surrounding UNKNOWN regions. Live DS table contents, the post-PUSH X read,
wrapped sign clamp, residual AL and the actual RET remain explicit.

The 5D94 readback setup and 5EBA three-byte exchange now pass 50 combined
fixtures at both boundaries, with 57 sites, 2,180 ordered bus events and five
completed mutants; see entity-vga.md. The live DS row-pitch word and SS mirror
ownership are named. The 5DC6 child now has an optional bus: 30 additional
fixtures compare 600 events, with VGA DS/SS aliases, provider changes and one
bus-bypass mutant; its original RAM API and 50-byte coverage are preserved.

The 5F0F..5FAB `DrawEntityStroke` parent now composes the native child through
actual CALL/RET frames. Forty fixtures at both boundaries cover 89 integrated
sites, eight edges and 5,884 events, with five completed mutants and eight
independent mask/plane checks. Changed child targets stop explicitly; coordinate
restores reread live stack words. Defined flags are checked at each instruction
phase, including the memory decrement's entry-flag observation. See
entity-stroke.md. This adds 157 caller bytes; the child's bytes overlap its
existing translation and are not added again.

The generated-mask leaves and producer now have scoped native acceptance:
44 leaf fixtures at both boundaries cover 105 bytes/66 sites and 20 edges,
with 28,508 events and five completed mutants. Seventeen producer fixtures at
both boundaries cover 80 additional caller bytes/35 sites, 101 integrated sites
and 24 edges, with 592,280 events and five completed mutants. The independent
normal-path calculation verifies all 1370h output bytes from source 0000..0183.
Live SS saves/counts/cursors/DH/DS, ordered selectors, actual child/outer returns,
changed-target stops, DF asymmetry, overlap and device providers remain explicit.
See generated-graphics.md. Child bytes overlap the leaf translations and are
not added again; this is not aggregate acceptance or full resource/game readiness.

The 5DF8 `DrawClippedEntityMask` consumer now passes 43 fixtures at both
boundaries: 194 bytes/91 sites, seven branch edges, 31,608 events and six
completed mutants, plus 17 independent plane checks. An actual native producer
handoff independently checks all 528 bytes in its source bank. Early clipping
retains IF; drawing sets IF after live count/clip/DX/DS/SI saves, ordered source,
latch/mirror/port/pixel accesses and DF-sensitive strings. See entity-mask.md.

The ten/thirteen-row consumers now pass 67 core/adapter fixtures: 405 bytes,
187 sites, ten edges, 33,308 events, nine compiled mutants and 41 independent
plane checks, including two native producer handoffs. The ten-row entry keeps
BP and rereads X/+4 after saving SI; the thirteen-row entry returns BP=sum&7
and applies its signed +27h adjustment when +28h equals two. Their unchecked
selectors, actual base/DX/DS/SI/RET saves and live VGA/DF behavior remain explicit.
The signed thirteen-row caller still admits 130 AX values; its state invariant
remains open. See entity-mask.md.

The 6141 coordinate helper also passes 34 core/adapter fixtures: 47 bytes/23
sites, no edges, 952 events and four completed mutants. It receives BX=Y/CX=X,
keeps the original no-clamp behavior and residual AL, and restores actual SS
BX/CX/DX words after the DS mask read. See coordinate-pixel.md.

These nine identified helpers now form the maintained 05D66..0616F physical
ASM module entity_graphics.asm (1,034 bytes), with exact start/end assertions.
Word generation and neighboring UNKNOWN bytes remain in the prefix. This is
source ownership with scoped C verification, not complete game acceptance.

Both external INT61 dispatcher prefixes now compose six native latch setters:
106 unique bytes/65 sites/27 edges across AdLib and Tandy. The 766 fixtures
cover all256 AH values for both drivers plus setter, alias and VGA domains,
at core/IRET/untranslated boundaries, with9,240 events and ten completed
mutants. AH0/1/2 stop at the untranslated update/detect/reset bodies; AH6..FF
retains the five DEC operations and IRET. AdLib byte0014 stays UNKNOWN.
See sound-latches.md. This closes the command4 provider's prefix/setter
behavior; the connected INT61 transport is described below, while playback
and timing remain open.

The 2E04 countdown transition now composes that command4 path:430 fixtures
at core/adapter boundaries cover188 new bytes/52 sites/14 edges, with20
auxiliary interrupt calls and14 completed mutants. It preserves direct-zero
wrap, residual AH, live record/slot/gate accesses, RMW flags, actual DS/FLAGS
restores and the post-sound +8/+22 decision. Unbound vectors and changed
interrupt returns stop at their actual CS:IP; INT frame/IVT transport remains
a declared platform model. See entity-countdown.md. The sound adapters also
now normalize reserved FLAGS bits after original IRET-frame aliases, with
regression fixtures and a completed raw-FLAGS mutant.

The PC-speaker dependency now has a native dispatcher at0182..01AF:282
fixtures at core/adapter boundaries cover46 new bytes/29 sites/six edges,
18 integrated child sites and18,270 events, with eight completed mutants.
The effect/stop bus gate adds274 fixtures at both boundaries,42 already
translated helper bytes/18 sites/two LOOP edges,20,392 events and five mutants.
The mutable table is read before CALL's push; temporary DS, restored registers,
RET and IRET words remain live. Tick/other targets and changed child returns
stop explicitly. The separate335-case RAM/port regression also passes.
See pcspeaker.md. This does not close Tick's wider bus domain or IRQ timing.

INT60 frame/vector transport now connects the native PC dispatcher:25 focused
fixtures,1,234 ordered events and six completed mutants retain all returned
registers, exact bindings, vector/frame aliases, changed targets and VGA stack
writes suppressed by map mask zero. It adds no original ASM bytes.

`ApplyEntityCellInteractions` at2EC0 now composes all five service sites:311
fixtures at logical-core/RET-adapter boundaries,486 new main bytes/162 sites/
61 branch outcomes,37 PC and28 external-driver sites,17,648 events and eight
completed mutants. Popped AX owns nibble dispatch; live SS, callback slots,
ordered record/object stores and PC-returned DS/SI/CX remain explicit. Unbound
and changed targets stop with the actual state. Entry FLAGS are admissible;
reserved IRET data words remain unrestricted and no memory bytes are masked.
See entity-interactions.md and pcspeaker.md for exact scope and the original-IRET
poison diagnostic.

The1F19 ownership audit now records the slot-bound versus live-pass counter,
scan request/cursor, persistent work guard, exact gate XOR, ordered state-bit
priority and per-record ES save in entity-simulation.md. These are ledger-owned
DS locations; the unchecked record array extent remains unproven. The shared
1FE8/20D6/20E2/2148 JMP tails now have scoped native acceptance:24fixtures at
core/adapter boundaries,55unique bytes/18sites/eight edges,95integrated
interaction sites,2,026events and six completed mutants. Their actual interaction
CALL/RET and changed sound-child seams remain explicit.

The initial zero-state2047 branch now passes37fixtures at core/adapter boundaries:
309unique caller bytes/104sites/all33 owned jump edges,182integrated main sites,
5,094ordered events and eight completed mutants. Its actual5DC6 CALL/RET and
shared finish paths preserve signed/wrapped probes, live pitch/callback/record
and stack aliases, DF and RAM/VGA observations. The focused parent map is neutral;
shared-tail sound seams retain their own gate. Together these two new scopes own
364unique bytes; child and overlapping suffix bytes are not counted again.
This is scoped acceptance, not aggregate game or native-device readiness.

State0004 at21B0..22DE now passes36 core/adapter fixtures:303 new caller bytes,
87 sites/all29 jump edges,151 integrated main sites,16 sites per AdLib/Tandy
prefix,3,910 ordered events and eight completed mutants. Its unsigned raw+23/
+25 gates, signed heights, all three probes, early inactive exits without Y
stores, live callback/pitch/gate reads and actual pixel/INT61 frames remain
explicit. Four cadence entries22DF/22F5/2326/2340 pass23 core/adapter fixtures:
113 new bytes/45 sites/all18 edges,23 coordinate-child sites,654 events and
eight mutants. Another1,024 original-only prefixes verify the four byte
transforms without adding C bytes. The combined416 new bytes preserve overlaps;
see entity-simulation.md. The original-instruction oracle now composes explicit
parent spans/RET/stop contracts in one traced CPU with the existing INT engine.

State0008 at23BF..23F2 now passes18 core/adapter fixtures:52 new caller bytes,
18 sites/all6 jump edges,1,976 events and eight completed mutants. State0002 at
2350..23BE passes35 core/adapter fixtures:110 known caller bytes/45 sites/all20
edges,8,772 events and eight mutants. The two scopes add162 unique caller bytes;
UNKNOWN2382 stays unresolved and excluded. State0008 retains actual5DC6 return
23C2 and direct2148 finish; state0002 composes native INT60 AX030C, optional
283B, live SS nibble selection and full5DF8 mask drawing. Its sound gate requests
INT60 only when DS2010 differs from FF and DS25A7 bit0 is set. Both live child
RET and PC dispatch/IRET seams remain explicit. See entity-simulation.md.

The283B child now has an optional bus verified in28 core/adapter fixtures,
37 sites,2,632 events and four completed mutants; its37-fixture ordinary-RAM
regression also passes. Live PUSH SS/POP ES, saved words, actual RET, DF,
VGA source/destination aliases and instruction-phase FLAGS flow through the
bus. This extends its existing66-byte scope and adds no translated bytes.

States0010/0020/0040 now have scoped native acceptance. State0010 passes48
core/adapter fixtures:348 new caller bytes/127 sites/all33 observed jump
outcomes,264 integrated main sites,11,578 events,eight completed mutants and
three independent plane replays. State0020 passes24 fixtures:232 bytes/74
sites/all13 edges,3,538 events and eight mutants. State0040 passes25 fixtures:
92 bytes/26 sites/all7 edges,2,160 events and eight mutants. Together they add
672 unique caller bytes/227 sites; child/shared-tail bytes are not added again.
Actual CALL-specific return contracts reject another valid caller continuation,
and the original oracle records LOOP edges from actual CPU transitions.
See entity-simulation.md for live mask,callback,segment and flag contracts.

States0080/0100 now add420 unique caller bytes/137 sites/48 actual owned jump
outcomes. State0080 passes50 core/adapter fixtures:337 bytes/115 sites/all44
outcomes,8,796 ordered events and eight completed mutants. The four one-byte
holes26A1/26F6/26FF/2762 remain UNKNOWN and excluded. Its opposite sound gates,
PC-returned DS,actual AX/ES saves,direct/nested pixel/stroke returns,wrapped+21
decrement,late callback and signed third-probe transition remain explicit.
State0100 passes19 fixtures:83 bytes/22 sites/all4 outcomes,2,726 events and
six mutants. It retains separate INC/AND memory RMWs,actual5DC6/283B frames,
live pixel-produced ES and the final1FEB JMP. Child/tail bytes overlap existing
translations and are not added again. See entity-simulation.md. Record+21=0C
at32F2 remains one observed producer,not a proven whole-field domain.

States0200/0400/8000 and the+24-bit80 override now add938 unique caller bytes/
309 sites/112 unique owned jump outcomes. State0200 passes46 core/adapter
fixtures:496 bytes/169 sites/all59 outcomes,12,454 events and nine completed
mutants,including native mask/coordinate/pixel/sound and shared PC handoffs.
State0400 passes24 fixtures:197 known bytes/66 sites/all27 outcomes,2,800
events and eight mutants. Its three UNKNOWN holes and unchecked pair-source
extent remain unresolved; naming DS:2698 assigns no bounds. The late entries
pass31 combined fixtures:245 bytes/74 sites/all26 unique outcomes,2,690 events
and six mutants. Actual returns,returned DS,late callbacks,RMW flags and the
same-target scan comparison remain explicit. See entity-simulation.md.

State0800 now passes177 core/adapter fixtures:473 known caller bytes/157 sites/
all70 unique owned outcomes,80,208 ordered events and nine completed mutants.
Every one of the130 signed thirteen-row selector handoffs executes. Exact18h
reset, signed X guards, actual mask/pixel returns, same-target nibble8 sign
read, returned DS before NEG and shared finish remain original behavior.
UNKNOWN2B50 remains excluded. See entity-simulation.md.

AdvanceEntityRecords at1F19 now composes all state branches in44 core/adapter
fixtures:299 additional caller bytes/108 sites/all81 feasible owned outcomes,
6,768 ordered events and eight completed mutants. The complete composed body
is3,744 known bytes/1,255 sites; those state/shared-tail bytes overlap existing
C scopes and are unioned. The connection observes808 integrated main sites.
The additional caller scope excludes the already tested1FE8 CALL.
Readback/countdown actual returns1F26/1F4F, cached first-match AX, live0042
counter and ES saves, and scan RET203B's persistent guard/request are required
contracts. Of82 static outer jump outcomes, taken1FE3-to1FE8 is locally
infeasible because the frozen nonzero AX has passed tests covering all16 bits.
State JMPs still execute the shared1FE8 CALL. No UNKNOWN or shared tail is
classified as dead. The three actual outer RET sites remain2004/203B/2046.

CreateEntityRecordIfDue at30A6..314F now passes273 core/actualRET-adapter
fixtures:170 known bytes/54 sites/all13 jump outcomes,50,262 ordered events
and eight completed mutants. Its equality limit is not an upper-bound clamp.
At bound50h the45-byte clear overwrites the coordinate source before its reads;
byte MUL preserves DX, the callback read is late and the final bound INC is live.

The31E5/3287 action-feedback tails now pass68 core/actualRET-adapter fixtures:
59 unique bytes/20 sites/all12 outcomes,3,786 events and eight completed mutants.
PC and external enabled gates differ, and the external gate rereads the returned
DS. Native INT60/61 children retain their unbound/untranslated/changed-target
boundaries. See entity-actions.md for the3150 static ownership audit.

The actual01B0/01B3 caller prefix now composes creation and update in17
core/adapter fixtures:6 additional bytes/two CALL sites,5,708 events and five
completed mutants. It observes both actual near-return words, forwards nested
child boundaries and stops01B6 before untranslated CALL3944. New records advance
in the same pass; the boundFF wrap can instead make the update bound zero.
This is not a complete main-loop or timing contract. See entity-simulation.md.

All eight3150 action selectors now compose native cores through the known
1,221-byte/402-site body. The basic2/3/4 suite retains39 fixtures/7 mutants;
advanced6/7/8/9 adds534 unique bytes in186 fixtures,150 sites/all66 owned
outcomes,10,154 events and ten mutants. Selector5 adds408 bytes in56 fixtures,
158 sites/all73 outcomes,6,586 events and eight mutants,plus two actual native
producer-to283B restoration handoffs checking all nine cells with DF clear.
The full dispatch suite passes290 core/actualRET-adapter fixtures including
all256 selectors:43 own sites/all28 own outcomes,376/402 integrated sites,
110 integrated conditional outcomes,8,244 events and six completed mutants.
Leaf matrices jointly cover all402 known sites; shared bytes count once.
No fabricated CALL frame or host record copy was introduced. Sound seams and
all31 UNKNOWN bytes remain explicit; broader scheduling/IRQ acceptance is open.

The physical3150..3633 action block is maintained in entity_actions.asm.
The untranslated3634..368D draw-call loop is separate in entity_drawing_calls.asm;
program/module assertions preserve byte order and every UNKNOWN classification.
The action APIs share an exact typed live-register boundary and bounded native
test transport; independent eligibility/transition/original models stay separate.

The4B68/4BBE variable-width fields now pass1,064 boundary cases,90 unique
bytes/42 sites/all13 jump outcomes and seven completed mutants. Digits are
left-aligned with trailing spaces; the pair entry retains its unnormalized
tens quotient (255 produces I5). Ordered writes, BH, final INC SI flags and
actual SS returns remain live. See decimal-field.md.

SelectEntityCandidate3CDE now composes the formatter through its actual
CALL3DF3/RET4BBD:51 fixtures at core/actualRET-adapter boundaries cover393
known bytes/140 own sites/all69 outcomes,23,800 events and nine mutants.
Zero entry leaves stale candidate state; frozen CL controls scanning while
live0043-CL produces each bucket index. Last hits win and index FF can collide
with the sentinel. The255-slot fixture retains the display-clear/record182
alias and yields254 hits; a separate live count provider reaches FF. Broader
record bounds, initialization and scheduling remain open. Four actual native
selection-to3150 handoffs pass (preferred/forced fallback,selectors2/3/4),
216 integrated sites/618 events and zero additional bytes. The intervening
3AC8 call remains outside their domain. See entity-actions.md.

The7A5A viewport now passes46 core/adapter fixtures,350 bytes/168 sites/ten
outcomes,39,192 events and nine completed mutants. Two icon leaves780D/789E
pass512 fixtures at both boundaries,243 bytes/100 sites/six outcomes,187,432
events and nine completed mutants. The two-CALL3AC8..3ACD prefix passes12
fixtures at both boundaries,two owned/266 integrated sites,54,782 events and
five completed mutants. It carries actual column-returned DS into the viewport
and stops before3ACE; the prefix adapter does not consume an outer RET.
See minimap-viewport.md and status-icons.md. These scopes add599 unique main
bytes, taking the ledger union from16,479 to17,078; this is scoped translation
accounting, not refreshed aggregate acceptance.

The closed glyph leaves762A/7708 now pass270/269 fixtures at both boundaries:
222/256 known bytes,105/118 sites,12/30 jump outcomes,48,512/30,662 ordered
events and seven/nine completed mutants. The main ledger union is17,556 after
these478 additional bytes. The physical status_glyphs.asm module retains the
five UNKNOWN bytes outside their accepted ranges. See status-display.md.

The17-byte417B text caller now connects the glyph core through actual CALL/RET:
18 fixtures at both boundaries,11 own sites/three jump outcomes,34,102 events
and seven completed mutants. Full stored40-byte and46-character AH-wrap scans,
live NUL/source/saved AX/SI/DS, changed child returns, actual outer RET and
independent planes remain covered. This adds17 unique bytes, taking the main
ledger union to17,573 (+495 for count/glyph/text together).

The3ACE status suffix now passes29 fixtures at both boundaries:527 known bytes,
all172 sites/all73 jump outcomes,48,738 events and eight completed mutants.
The complete3AC8 entry composes the two minimap CALLs by fallthrough into that
suffix:10 focused fixtures/13 comparisons,163/174 owned sites,68 observed
outcomes,43,068 events and three completed mutants. The wrapper's remaining
body paths retain the suffix's separate gate; no full174-site execution is
claimed for the handoff matrix. Live returned DS/ES/SS, actual CALL/RET words,
old-icon/count-field overlap, counter wrap, stale leading percentage digit,
full40-byte line and the pre-DIV exception boundary remain explicit. The full
entry and suffix ranges overlap; only527 new unique bytes are added, taking
the main-image C ledger union from17,573 to18,100. See status-display.md.

The3944 gate/shared7C0A animation tail now passes61 fixtures/134 core,
adapter and selected null-bus comparisons:104 known bytes/all39 sites/all17
jump outcomes,22,816 native ordered events and eight completed mutants. The
7BB8 draw caller passes50 constructed fixtures plus one actual native animation
handoff,55 comparisons,all33 caller sites/all4 outcomes,346 integrated sites,
30,706 events,109 independent plane checks and six completed mutants. The pair
adds186 unique main C bytes, taking the ledger union from18,100 to18,286.
Their maintained object_graphics_tick.asm keeps physical byte order. StaleBX,
separate002B/0055 gates, equality-only frame wrap, low-byte type, live MUL/base,
forced-unshifted drawing, actual saved SI/DI/CX and child near/far/provider
boundaries remain explicit. See object-records.md. This does not accept the
enclosing tick CALL sequence, full native device timing or IRQ scheduling.

The7602 leaf and75EF wrapper now pass16 fixtures at both APIs:59 unique bytes/
22 sites/no jump edges,155,458 ordered events and seven completed mutants.
Each pass copies all06E0 bytes with DF, live DS/RET words and mode1 overlap;
the wrapper makes one CALL, then falls through into the second pass.
The39CE initializer passes15 fixtures at both APIs:250 new caller bytes/all70
sites/no owned jump edges,234,488 events and eight completed mutants. The
same-IP39D1 nested child stop, changed copy/count/outer returns, all returned
roles and ordered shared snapshots remain explicit. Another256 original-only
eight-instruction prefixes check all release bytes. The two scopes add309
unique main bytes (18,286 to18,595); child/leaf overlaps are not counted again.
See status-display.md and the two matching-input native reports for scoped
acceptance; the enclosing tick, device timing and IRQ scheduling remain open.
The6FE2 pixel,410F visibility producer and5726 dirty consumer now have scoped
native acceptance:40/28/33 fixtures at both APIs,58/27/73 sites and5/0/25 jump
outcomes, with8/8/7 completed mutants. Minimap also has4 null-bus comparisons.
Two native producers at origins0/0180 feed4 accepted/rejected data handoffs,
with598 additional bus events and explicit3654->3657 caller frames. This is
data-flow evidence, not execution of3634. The exact loaded143E operand remains
separate from liveSS; no guessed visibility extent or bounded dirty matrix is
introduced. See entity-display.md and matching-input reports. These disjoint
scopes add376 unique main C bytes, taking the ledger union to18,971.

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

That checkpoint selected the nine sprite callback leaves before
DrawObjectSprite706F..715E and the enclosing record loop. Start with6170
(873 bytes/478 sites,22 observed direct record+14 producers), tracing the
DS1FE6 source allocation and live descriptor fields first. The known table
contains nine initialized slots, but copies/indexed stores and aliases leave
the715B CALL AX domain open. Its target is the real SS word saved at70F0,
not a late reread of record+14. Preserve helper7152->7155, callback715B->715D,
the shared saved-DI/RET suffix and returned DS/ES/SS. See entity-display.md
for targets, ownership, and source/count quirks. The current checkpoint above
records the subsequent three callback ports and next six dependencies.

StatusGlyphBufferSegment names the live1FEC word. Its
base+2F02 allocation and MAIN.DAT section2/conditional section6 copies are now
statically traced in status-display.md; broader producer verification remains
open. Preserve count values100..255, signed glyph selectors, live saved words,
map-mask passes and reverse DF reads. The stored2083 status line continues40
bytes to NUL20AB; selection's11-byte field is only its prefix and no runtime
scan bound. Keep the100*n byte-DIV exception frontier and input/cadence ownership
explicit. Direct selection/action handoffs remain separate data-flow evidence.

Allocation bounds, the 5CC1 shared-tail caller and UNKNOWN 5D18..5D65 remain
separate frontiers. Full original/native campaigns and matching inputs remain
required before aggregate acceptance.

Use fresh dependency views rather than an accumulated historical task list:

```powershell
.venv\Scripts\python.exe tools\graph.py 7602 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 75EF --bottom-up
.venv\Scripts\python.exe tools\graph.py 39CE --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 39CE --bottom-up
.venv\Scripts\python.exe tools\graph.py 3634 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 3634 --bottom-up
.venv\Scripts\python.exe tools\graph.py 6FE2 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 410F --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 6E83 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 6E83 --bottom-up
.venv\Scripts\python.exe tools\graph.py 3AC8 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 3ACE --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 3ACE --bottom-up
.venv\Scripts\python.exe tools\graph.py 1F19 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 1F19 --bottom-up
.venv\Scripts\python.exe tools\graph.py 2E04 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 2E04 --bottom-up
.venv\Scripts\python.exe tools\graph.py 2EC0 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 2EC0 --bottom-up
```

## Development and acceptance

- Run the fast default `tools/verify.py` plus
  `tools/difftest.py SUITE [SUITE ...]` for local work. `--list` lists suites and
  `--plan` previews their existing deadlines and memory ceilings.
- The complete original-only campaign is `tools/verify.py --contracts`; the
  complete native campaign requires `tools/difftest.py --all`. Aggregate
  acceptance requires the full reports and matching input hashes. Preserving
  a report file does not renew its evidence.
- Keep native workers under the process-tree commit limits, deadlines and hard
  callback budgets in AGENTS.md. Exhaustion is failure, never mutant credit.
  Reap workers and remove owned temporary DLL directories after every outcome.
- Keep parent checks focused on handoffs and composed behavior. Retain exhaustive
  child matrices in their own suites unless parent behavior requires repetition.
  Narrower caller domains require proof; original bugs and live state remain.

## Existing connections and deferred work

The maintained native scopes for resources, cleanup, drawing, object records,
minimap, display, text and palettes are documented in bottom-up.md and their
individual contract notes. The 36B6 initializer and 394F redraw caller have their
own scoped gates; refreshing affected reports remains separate from this terrain
acceptance. Keep provider, allocation, device and IRQ seams explicit.

The 4B1C retry-screen composition is implemented but unverified; see retry-ui.md.
Its children do not establish the complete caller contract. Keep it queued as
error-path work rather than making it the next prerequisite for simulation.
No extra C coverage is claimed for that composition.

## Static and platform obligations that remain open

- Protected disk-check state and skipped 084D/087E regions, the 188F..1898
  code/data overlap, and unresolved 8363 reachability: protection.md and
  executable.md. Keep the canonical stored bytes distinct from execution views.
- All UNKNOWN runs and incomplete code/data/CFG ownership, including bytes
  beyond the provisional data boundary. UNKNOWN is neither padding nor dead.
- Target/write domains of the 18 known conditional callback edges, unchecked
  tables and mutable drawing slots: indirect-callbacks.md and the ledger.
- Record initialization, copying, activation and overlapping buffers, with live
  DS/ES/SS and provider effects: object-records.md and the initialization notes.
- Installed IRQ/device contracts, external IRET chains, input producers and
  scheduling: interrupts.md and hardware.md. Bounded polling fixtures do not
  establish live timing or interrupt delivery.
- AdLib 01EA, Tandy 02BB and PC-speaker 0196 dynamic targets beyond the scoped native entries, unchecked command indexes,
  mutable tables and unresolved payload bytes: sound-drivers.md. Keep all pinned
  executable dependencies in the inventory, including alternative hardware.
- Source/mask producers, allocation bounds and executable/stack aliases outside
  tested drawing domains: drawing-render.md, terrain-stream.md and the original
  counterexamples in tests/terrain_code_alias.py.

SDL3 remains after the portable core and the required static/accounting work.
No game boot, legacy interpreter import, asset change or neighboring-project
change is part of this work.
