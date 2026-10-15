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

Next establish the device writer at `sub_5EBA` (5EBA..5F0E), then connect
`sub_5F0F` (5F0F..5FAB) to the native 5DC6 child:

1. For 5EBA, retain VGA latch/read effects, live SS graphics-register mirrors,
   incoming device mode, byte masks from BH/BL/CL, DF-sensitive STOSB, CLI/STI
   and actual RET. The two simulation call paths at 2418/251A first use 5DC6
   for DI but prepare their own masks before calling the writer.
2. For 5F0F, preserve the live saved coordinates and child CALL/RET frame,
   returned native address state and subsequent VGA stores. Focus parent
   cases on handoffs and composed device behavior rather than repeating
   every child boundary case.
3. The sibling 6141 helper uses register coordinates and the same live table,
   with different saves and no sign clamp. Keep it distinct from 5DC6.
   Work through 2E04/2EC0 and remaining 5D94..6141 dependencies before the
   1F19 parent, which still has 3,744 decoded bytes/1,255 sites and is
   untranslated. TESTED child domains do not establish parent readiness.

Use fresh dependency views rather than an accumulated historical task list:

```powershell
.venv\Scripts\python.exe tools\graph.py 1F19 --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 1F19 --bottom-up
.venv\Scripts\python.exe tools\graph.py 5F0F --tree --depth 2
.venv\Scripts\python.exe tools\graph.py 5F0F --bottom-up
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
