# Precise next frontier

## Current checkpoint

The main-image translated-code ledger union is 26,544 bytes. Input commands at
3E6F add 530 known C bytes and compose the tested 64-byte visibility child.
The campaign passes 65 fixtures/130 comparisons, all 220 reachable sites and
121 feasible direct jump outcomes, with five completed mutants. Two known
comparisons and three static outcomes are infeasible from this entry under
synchronous providers; their literal C remains implemented. Four UNKNOWN bytes
remain unresolved. The report records 8,407 original instructions and 6,044
events (484 declared INT transport, 44 provider accesses across 28 calls).
See input-commands.md for state ownership, proof and remaining sound boundaries.

The EOI/port-201 cluster passes 51 fixtures/102 comparisons, all 75 sites/eight edges and ten
completed mutation detections after migration to tests/verification.py. Its
report retains matching consumed-input hashes. Exact ASM identity is unchanged.

The connected input campaign passes 63 fixtures/126 original-native comparisons,
all 243 sites/91 direct jump outcomes, and seven completed mutants. Its 576
known bytes combine 345 parent, 79 mouse and 152 previously translated port
bytes; only 424 new bytes enter the ledger. It executes 7,486 original
instructions and compares 4,644 events, separating 592 declared INT transport
and 96 provider accesses across 34 service calls. Its report now pins the shared
native interrupt transport as well as the original campaign inputs.
Known 4252/4334/4359 callbacks are supported; 42A5's target domain remains
explicitly incomplete. See input-poll.md and verification.md.

## Next connected subsystem

1. Compose the 183E timer tail with the tested command, input, mirror and EOI
   children and explicit INT60/61 and saved-INT08 provider seams. Preserve its live stack and
   checksum overlap. The 119-byte prefix and 116-byte tail overlap the 235-byte
   full handler: count shared bytes/sites once. See timer-frontier.md.
2. Close prefix dependencies 5473/553D, finite status-port input and the tested
   5827 fixed-pattern child, then compose the 17C7 full handler.
3. Connect startup/resource/level/frame coordination, complete the remaining
   executable dependencies, then supply native platform services and SDL3.

The destination is portable C11 directly from the exact ASM oracle, with one
canonical memory image and explicit platform boundaries. An intermediate DOS-C
hybrid is not required. Every behavior-affecting code dependency remains in
scope; an unsupported alternative is not completion. Native startup-to-gameplay,
scripted input and bounded state/frame/audio checkpoints are final integration
requirements. See architecture.md; a smoke run alone is not exhaustive parity.

## Development and evidence

Use tests/verification.py for new focused suites; add shared capabilities rather
than another bespoke CPU/bus/callback/comparison engine. Keep independent expected
algorithms and fixture providers separate. Migrate existing consumers when their
subsystem changes; no project-wide harness rewrite is a prerequisite. Choose
mutations for distinct contracts and batch a leaf with its parent where practical.

Run tools/verify.py and affected tools/difftest.py suites. Native workers retain
hard time/memory/access limits, fail-stop callbacks and owned-DLL cleanup. Reports
are accepted only for matching consumed inputs. Translation bytes, executed
sites, connected C domains and full-game acceptance remain separate. Aggregate
acceptance still requires tools/verify.py --contracts and a matching complete
native campaign; do not rerun unrelated long suites to refresh a local edit.

The retained terrain campaign covers all 80 pinned LEVEL streams in 192 fixtures,
with 1,383 integrated sites/195 edges. It and older campaigns are historical for
their recorded inputs when current hashes differ. Detailed prior checkpoints and
regressions are preserved in convergence-history.md and the subsystem documents.
The implemented 4B1C retry UI remains unverified and must not count as accepted C.

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
