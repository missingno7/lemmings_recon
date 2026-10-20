# Next semantic work

The current quantitative inventory is [completeness.md](completeness.md), generated
with `tools/coverage.py --inventory`. The [audit/readiness matrix](semantic-audit.md)
explains the current realignment; [bottom-up.md](bottom-up.md) gives the working
loop and physical source map. Old checkpoints are in convergence-history.md.

## Immediate mode

Finish semantic readiness of the session and shared-state lifetimes before broad
C expansion. Existing C/tests remain valuable and intact. The current C initializer
stops at 046E, but the next job is understanding the enclosing operation, not
turning that one branch into another isolated translation milestone. No SDL3
integration is part of this phase.

## Priorities

1. **Session/frame/timer contract (00FB..04CF,17C7/183E).** Use the named wait
   producer/consumer and transition state to specify the scheduled INT08 edges,
   signed tick gate, double action dispatch, page/map swaps, end/result path and
   child-returned DS/ES/SS. Include the per-level 4551 clear versus 03E7/header
   initialization. Decide which caller registers/flags are actually live. This
   unblocks one coherent foreground controller instead of serial three-byte CALL
   promotions. Readiness: full controller NOT READY until those seams are stated.
2. **Record/graphics lifecycle and callback writers (30A6,1F19,3150,3634,706F).**
   Trace the same 2D-byte record from per-level clear through creation, action,
   state transitions and drawing. Preserve shared +20/+26/+27 roles and sample
   order +2C then +2B; establish allocation/slot and callback-source invariants
   from producers. Resolve the domain of 715B before narrowing raw adapters or
   treating the nine initialized callbacks as an exhaustive target proof. The
   source now names key fields; broader lifetime closure is still CONDITIONAL.
3. **Startup/protection/allocation (054E..13DB).** Recover service and segment
   provenance and investigate the 1,042-byte 098C..0D9D UNKNOWN gap by its actual
   writers/users. Keep canonical/protected views distinct. Do not linear-sweep
   or call unreferenced bytes dead. These paths determine valid runtime memory
   domains and can remove many future translation guesses.
4. **Executable sound engines.** Follow AdLib 01EA, Tandy 02BB and PC-speaker 0196
   dynamic dispatch, tables, initialization and command formats in their separate
   images. Classify executable versus stream data with evidence. The tiny scoped
   C entries/latches are not full alternative-hardware support; this is required
   game completion work, not an optional backend polish task.
5. **Resume C on a READY connected operation.** Once the session/lifetime gate
   permits it, batch the known initializer/frame children and validate a constructed
   resource -> level -> foreground-tick handoff. Preserve provider/fatal/changed
   return seams. Use targeted suites plus focused parent cases; leave exhaustive
   renderer/terrain matrices in their owning suites unless interaction changes.
   Consolidate packet/helper duplication only where this operation proves it safe.

## Evidence and persistent open obligations

ASM-only names/comments/offset changes use exact/static checks. Local C changes
use affected suites; connected behavior adds directly affected handoffs. Shared
behavior changes require affected consumers, plus `verify.py --contracts` when
original contracts change. Full `difftest.py --all` and aggregate reporting stay
explicit acceptance steps. Metadata/comment edits can stale old manifests without
altering behavior; do not relaunch unrelated campaigns solely to refresh them.

Keep all UNKNOWN runs, protected transitions, 18 conditional callback edges,
unchecked resource/record tables, RETF selector-EA wrap limitation and explicit
processor faults unresolved until evidence closes them. Keep real IRQ scheduling,
BIOS/DOS/device contracts, code/stack aliases and executable dependencies visible.
Known test stops do not prove full-game behavior. Never boot the original for
discovery, import the legacy interpreter, or alter assets/neighboring projects.

The destination remains exact readable ASM -> portable C11 game logic with
explicit platform services -> native platform -> SDL3. Complete native startup,
scripted input, bounded state/frame/audio checkpoints and longer session checks
are eventual acceptance requirements; a smoke run is not exhaustive parity.
