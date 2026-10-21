# Next semantic work

The current quantitative inventory is [completeness.md](completeness.md), generated
with `tools/coverage.py --inventory`. The [audit/readiness matrix](semantic-audit.md)
explains the current realignment; [bottom-up.md](bottom-up.md) gives the working
loop and physical source map. Old checkpoints are in convergence-history.md.

## Immediate mode

The host boots the original program natively: host/ supplies only DOS entry
inputs (unpacked image, PSP and command line, stack, IVT, services) and runs
c/startup.c (with c/protection.c and c/sound_driver_init.c) into the verified
menu -> level -> session -> result loop. The floppy media probe 063E is an
explicit policy (`--media-probe=assume-original|reject|unsupported`). Parity:
tests/startup.py, tests/protection.py, tests/host_journey.py, tests/game_loop.py.
Sound is a muted sink; no SDL3 yet.

## Priorities

1. **Executable sound engines.** The INT60/61 targets (PC speaker 0182,
   AdLib/Tandy driver images) are the remaining behavior-affecting runtime
   dependency of the native game. Follow their dispatch, tables and command
   formats in their separate images and translate them so the host can produce
   audio instead of a muted sink.
2. **SDL3 presentation over host/.** Interactive window, real-time scheduling,
   mouse/keyboard mapping and audio output once sound engines exist; the host
   interface is the boundary. Keep headless parity runs as the acceptance gate.
3. **Record/graphics lifecycle and callback writers (30A6,1F19,3150,3634,706F).**
   Trace the same 2D-byte record from per-level clear through creation, action,
   state transitions and drawing. Preserve shared +20/+26/+27 roles and sample
   order +2C then +2B; establish allocation/slot and callback-source invariants
   from producers. Resolve the domain of 715B before narrowing raw adapters or
   treating the nine initialized callbacks as an exhaustive target proof. The
   source now names key fields; broader lifetime closure is still CONDITIONAL.
4. **Protected body and gap 098C..0D9D.** Startup is native except the encoded
   INT1/INT3 media probe body, which stays a platform outcome. Its sector
   buffers are runtime overlays and 0D9C..0D9D a proven decode seed; classify the
   rest only from writer/user evidence. Never linear-sweep or call it dead.
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
