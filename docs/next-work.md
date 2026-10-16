# Precise next frontier

## Current checkpoint

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

Next port state0080 at2693..27E7:337 known bytes/115 sites/44 jump outcomes.
The four one-byte holes26A1/26F6/26FF/2762 remain UNKNOWN and excluded. Only
known external entry is1FB5; no known interior cross-entry splits the body.
Preserve modulo16 cadence,phaseA's unchecked+21<=3 gates and live PUSH AX/ES,
INT60 AX0313 return26C2,then fresh DS2010/DS25A7 gates for INT61 AX0412
return26D5,followed by actual POP ES/AX. Phase9 CALLs5F0F(return26E1), whose
nested5DC6 return is5F57. The zero phase has three direct5DC6 returns2703/
2713/272F,signed X/height tests,live pitch and a wrapped+21 decrement after
two clear samples. Transitions read callback002E late and JMP2148; other exits
JMP1FE8/1FEB. All direct children retain their scoped native contracts.
Record+21=0C at32F2 is one observed producer,not a proven whole-field domain.
The1F19 parent's eleven direct CALL children retain platform/fatal seams;
broader initialization,IRQ timing and record/scan composition stay open.

Allocation bounds, the 5CC1 shared-tail caller and UNKNOWN 5D18..5D65 remain
separate frontiers. Full original/native campaigns and matching inputs remain
required before aggregate acceptance.

Use fresh dependency views rather than an accumulated historical task list:

```powershell
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
