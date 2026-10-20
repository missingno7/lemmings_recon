# Next semantic work

The current quantitative inventory is [completeness.md](completeness.md), generated
with `tools/coverage.py --inventory`. The [audit/readiness matrix](semantic-audit.md)
explains the current realignment; [bottom-up.md](bottom-up.md) gives the working
loop and physical source map. Old checkpoints are in convergence-history.md.

## Immediate mode

The foreground session operation is now understood and translated as one unit:
InitializeGameSession 03E7..04CF, the frame controller 0105..031D, transition
cues 031E..03E6 and selector/edge scroll 4085/414F (c/game_initialize.c,
c/game_frame.c, c/game_transition.c, c/view_scroll.c). Its contract, timer
handshake and readiness decision sit beside the ASM at 00FB/0186/0462 and in
src/game_timer.asm; result/restart lifecycle at 46EB. The connected suites model
an IRQ only as the tail's foreground-visible stores at explicit polls.
No SDL3 integration is part of this phase.

## Priorities

1. **Native session runner with real INT08 delivery (00FB).** Compose
   lmn_initialize_game_core and lmn_game_frame_core into the 00FB session and
   deliver the native 17C7 handler (input poll 418C, commands 3E6F, mirrors,
   EOI/BIOS chain) at the LmnForegroundPoll sites with a real hardware frame and
   IF honoured; verify against original 17C7 delivery on the same schedule over
   multi-frame scenarios with scripted mouse/keyboard input. This replaces the
   minimal 1FCF/1FCD fixture, exercises IRQ-produced input end to end and is the
   native core the platform/SDL layer will drive. Keep 004A's unknown FF
   producer, preemption inside child bodies and sound-engine bodies explicit.
   Then translate the 46EB result screen to close next-level/retry/menu.
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
