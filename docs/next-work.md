# Next semantic work

The current quantitative inventory is [completeness.md](completeness.md), generated
with `tools/coverage.py --inventory`. The [audit/readiness matrix](semantic-audit.md)
explains the current realignment; [bottom-up.md](bottom-up.md) gives the working
loop and physical source map. Old checkpoints are in convergence-history.md.

## Immediate mode

The menu -> level -> session -> result loop is native and continuous:
c/game_loop.c follows the actual JMP transfers between EnterMainMenu/4401,
454C/4551 (resources, briefing), the 00FB session and the 46EB result, with
c/hardware_irq.c delivering the live IVT08 target (menu 4C47 or game 17C7) and
IRQ09 at LmnForegroundPoll sites in every wait loop. tests/game_loop.py replays
a scripted multi-level journey (cheat pass -> next level, time-up -> retry,
menu return) into the original handlers. Explicit loop stops remain: fatal
cleanup 04D0, DOS exit 04F7, and resource retry 4B1C (now native in
c/resource_retry.c but entered from the DAT layer's void retry callback, which
the driver still stops at). No SDL3 in this phase.

## Priorities

1. **Platform layer over the native loop.** Define the explicit platform
   services the loop consumes (VGA planes/CRTC/DAC, PIT/PIC timing, mouse INT33,
   keyboard IRQ09, DOS file I/O, BIOS video) as one C interface and a host
   implementation with a real-time INT08 schedule derived from the recorded
   cadence (display-locked, tick after five IRQs). Route the DAT retry callback
   into lmn_resource_retry_screen_core instead of stopping. Keep the original
   verification domains; this is the step before SDL3.
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
5. **Unify the composition adapters.** The frame parent dispatches thirteen
   differently shaped child adapters. Consolidate packet/helper duplication only
   where a concrete consumer changes and equivalence is checked by its suite.

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
