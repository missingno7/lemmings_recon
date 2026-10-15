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
106 unique bytes/65 sites/27 edges across AdLib and Tandy. The 730 fixtures
cover all256 AH values for both drivers plus setter, alias and VGA domains,
at core/IRET/untranslated boundaries, with8,376 events and nine completed
mutants. AH0/1/2 stop at the untranslated update/detect/reset bodies; AH6..FF
retains the five DEC operations and IRET. AdLib byte0014 stays UNKNOWN.
See sound-latches.md. This closes the command4 provider's prefix/setter
behavior, while main INT61 transport, playback and timing remain open.

Next close the two remaining direct untranslated children of 1F19:

1. Translate the statically contracted 2E04 countdown/record transition
   (188 bytes/52 sites), preserving its shared tails, live record/slot/gate
   reads and residual AH; see entity-countdown.md. Its actual AdLib/Tandy
   command4 dispatcher/setter boundary now has scoped C verification. Compose
   INT61 at2E5C/2EB0 through the live vector/frame and actual IRET rather than
   a preserving no-op; changed targets and missing service paths stay explicit.
   Preserve DEC/RMW entry flags and the post-interrupt +8/+22 decision.
2. Then resolve 2EC0 (486 bytes/162 sites), its SS interaction-map reads,
   saved words, record fields and transition tails. The 1F19 parent remains
   3,744 decoded bytes/1,255 sites and untranslated. Tested drawing children
   retain their device/IRQ domains and do not prove complete simulation readiness.

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
- AdLib 01EA, Tandy 02BB and PC-speaker 0196 dispatch, unchecked command indexes,
  mutable tables and unresolved payload bytes: sound-drivers.md. Keep all pinned
  executable dependencies in the inventory, including alternative hardware.
- Source/mask producers, allocation bounds and executable/stack aliases outside
  tested drawing domains: drawing-render.md, terrain-stream.md and the original
  counterexamples in tests/terrain_code_alias.py.

SDL3 remains after the portable core and the required static/accounting work.
No game boot, legacy interpreter import, asset change or neighboring-project
change is part of this work.
