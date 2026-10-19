# Precise next frontier

## Current checkpoint

The main-image translated-code ledger union is27,344 bytes. The keyboard cluster
connects wait17BE, command17B4, IRQ16D4 and installer1562 to native EOI/input in856
known bytes. Its592 fixtures/1,205 comparisons cover119 own sites/35 outcomes and
seven completed mutants. Three same-RAM installation/make-break/input handoffs
use pinned bindings. Full zero-count waits, special AX-zero behavior, actual
saves/RET/IRET and returned DOS DS/SS remain live. See keyboard-input.md;
scheduling and opaque platform bodies remain open.

The preceding82-byte1644
installer now connects direct menu installation, actual DOS vector08/60 requests,
the installed game IRQ and full-register cleanup16A9 on the same canonical RAM.
The50 fixtures/106 comparisons cover42 installer and19 cleanup sites,13 installer
outcomes and six completed mutants. Integrated coverage is901 sites/76 outcomes
in a2,984-byte known domain. Relocated1653, returnedSS:SP, actualPOPDS, byte-only
status adjustment, live reload and BIOS/IVT aliases remain explicit. See
timer-install.md; this does not supply scheduling or opaque DOS/BIOS bodies.

The preceding54-byte menu
timer4C47 and19-byte direct IVT08 installer5028 now compose the native input/EOI
and external saved-INT08 seams in a654-byte known domain. Their54 fixtures/108
comparisons cover all42 own sites/three direct outcomes and detect eight completed
mutants. Three same-memory handoffs retain actual installer output before a
constructed hardware entry. Live ES, returned DS/SS, eight actual saves, opposite
modulo-four phase and IVT/stack aliases stay explicit. UNKNOWN4C65 remains open.
See menu-timer.md; native scheduling and opaque service bodies are not supplied.

The preceding full17C7 timer
now connects2,840 known bytes through the actual palette, fixed-pattern, input,
command, mirror and interrupt-return paths. Its93 fixtures/186 comparisons cover
all109 timer sites/36 direct outcomes and detect five completed mutants. The
integrated run executes1,223 sites/150 outcomes and92,618 original instructions,
comparing72,572 events (640 declared interrupt transport and520 provider accesses
across54 calls). Only119 prefix bytes are new; the116-byte tail counts once.
Opaque ISR bodies, unknown callback domains, generated-bank initialization and
asynchronous timing remain open. See timer-frontier.md.

The preceding timer palette
callers5473/553D and sequential DAC leaf548C add135 bytes in a169-byte domain,
including the previously tested34-byte attribute child. The shared-verifier
campaign passes67 fixtures/132 comparisons, all81 sites/20 outcomes and five
completed mutants, including both full zero-count loops. Canonical sources2638,
2650 and2668 retain overlapping transition writes and unresolved initialization/
allocation. See palette-ports.md and palette-pointer-frontier.md.

The timer tail at
183E adds 116 known C bytes and connects the input, command, visibility, VGA
mirror and EOI children in a 1,374-byte domain. Its 48 fixtures/96 comparisons
cover all 49 tail sites/15 direct outcomes and detect five completed mutants.
The integrated run executes 443 sites/101 outcomes and 11,712 instructions,
comparing 8,634 events (616 declared IRET/INT transport and 264 provider accesses
across 50 calls). Its prefix is now composed above; opaque ISR bodies and
asynchronous timing remain open.
See timer-frontier.md for the two live return frames and shared phase ownership.

Input commands at
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
report is a checkpoint for its recorded inputs; additive shared header/tool
changes can make that retained report stale. Exact ASM identity is unchanged.

The connected input campaign passes 63 fixtures/126 original-native comparisons,
all 243 sites/91 direct jump outcomes, and seven completed mutants. Its 576
known bytes combine 345 parent, 79 mouse and 152 previously translated port
bytes; only 424 new bytes enter the ledger. It executes 7,486 original
instructions and compares 4,644 events, separating 592 declared INT transport
and 96 provider accesses across 34 service calls. Its checkpoint report pins the shared
native interrupt transport as well as the original campaign inputs.
Known 4252/4334/4359 callbacks are supported; 42A5's target domain remains
explicitly incomplete. See input-poll.md and verification.md.

## Next connected subsystem

1. Close the51-byte4D1A repeat/character reader over produced83-byte0F78 state,
   then compose its input/menu callers. Its202E XLAT base overlaps the final201F
   binding byte. Preserve live repeat bytes, first-ready scanning, counter quirks,
   AL/AH and actual nearRET; extend the shared keyboard campaign. Retain42A5 and
   UNKNOWN4C65/1696..16A8.
2. Connect startup/resource/level/frame coordination, complete the remaining
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
