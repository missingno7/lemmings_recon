# Next semantic work

The current quantitative inventory is [completeness.md](completeness.md), generated
with `tools/coverage.py --inventory`. The [audit/readiness matrix](semantic-audit.md)
explains the current realignment; [bottom-up.md](bottom-up.md) gives the working
loop and physical source map. Old checkpoints are in convergence-history.md.

## Immediate mode

The game is playable headless in native C: host/ (platform_host.c, main.c)
supplies VGA planar/DAC/CRTC, a virtual-time PIT/PIC INT08 scheduler at the
recorded cadence, IRQ09/port 60, INT33, INT21 file/vector services, BIOS
INT10/1A and the PKLITE unpack (c/pklite_unpack.c) with no Python or Unicorn,
under c/game_loop.c (menu -> level -> session -> result, DAT retry routed into
c/resource_retry.c). tests/host_journey.py matches the original journey at every
loop boundary and poll; tools/host_smoke.py renders menu/briefing/gameplay PPMs.
Sound INT60/61 is an explicit muted sink. The post-startup state is still built
by a C constructor from documented producers, not by translated startup code.

## Priorities

1. **Boot the host through native startup.** c/startup.c now runs 0000..00FA
   (command line, option screen, arena, sound driver load c/sound_driver_init.c,
   mouse hooks, calibration, MAIN.DAT) to JMP 43F2, stopping at the protection
   seam 062B. Translate the protection wrapper (russell.dat run counter, 0EC2
   writer quirks, 0EDF failure) with the floppy media probe 063E as an explicit
   PASS/FAIL/unsupported outcome provider, then replace host/'s post-startup
   constructor with native startup (its 25A7/1F71=00 sound substitute differs
   from the original fallback 01/01, likely the blank F3 menu sign).
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
4. **Startup/protection/allocation (054E..13DB).** Recover service and segment
   provenance and investigate the 1,042-byte 098C..0D9D UNKNOWN gap by its actual
   writers/users. Keep canonical/protected views distinct. Do not linear-sweep
   or call unreferenced bytes dead. These paths determine valid runtime memory
   domains and can remove many future translation guesses.
5. **Executable sound engines.** Follow AdLib 01EA, Tandy 02BB and PC-speaker 0196
   dynamic dispatch, tables, initialization and command formats in their separate
   images. Classify executable versus stream data with evidence. The tiny scoped
   C entries/latches are not full alternative-hardware support; this is required
   game completion work, not an optional backend polish task.
6. **Unify the composition adapters.** The frame parent dispatches thirteen
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
