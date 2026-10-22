# Next semantic work

The current quantitative inventory is [completeness.md](completeness.md), generated
with `tools/coverage.py --inventory`. The [audit/readiness matrix](semantic-audit.md)
explains the current realignment; [bottom-up.md](bottom-up.md) gives the working
loop and physical source map. Old checkpoints are in convergence-history.md.

## Immediate mode

Static semantic closure toward `asm-semantic-oracle-v1` (semantic-audit.md G),
VGA game plus AdLib driver first. C already covers nearly all decoded main code,
so further C or host work adds little understanding; the binding constraint is
classification, transfer domains and state ownership. The existing C and
headless host stay as downstream verification only. Evidence base: the read-only
audits of 2026-10-22 (static risk map, sound images, native integration,
methodology), whose findings are folded into the items below; their working
reports are in build/ and are not a status source.

## Freeze residue (asm-semantic-oracle-v1, VGA + AdLib first)

Verdict classes and the platform profile are defined in AGENTS.md and
metadata/platform-profile.json; per-site verdicts sit beside the ASM
(tools/flowstate.py, both modes).

Closed by original code: loader hands DF=0/IF=1; the only decoded STD (1BB0)
is reversed before every decoder return; protected POPFs restore their PUSHFs;
drivers never change DF; AdLib is installed once (00AB->054E) with no reload,
free or INT61 restore afterwards and cannot be re-entered while executing;
mode 0 never calls 42A5; exact DF0/DF1 footprints of every DF-sensitive writer.
So DF=1 has no known origin: it would need control reaching undecoded bytes or
corrupted saved FLAGS.

Closed only under the platform profile: forward startup clear; DF0/game DS at
the 1407 detector; AdLib bound as one process-lived instance at IVT61; mode 0
input DF preservation through INT33 AX=0003. Under the named data assumption
(original GROUND files are 0420 bytes): no GROUND overwrite of 25A0/2013.

Also closed by original code (2026-10-22 round): the exact 4013 race (commands,
vulnerable boundaries, count/limit recurrence, byte-address bound); owners of
every spill index 50..FF and which record consumers accept them; proper mode-1
entry always rewrites 25A0 (no stale joystick pointer by reentry); the
detector runs every session after 455D; stack collision thresholds from SS:4AF4.
Data-conditional: level007 object data writes SS:49B6..49C5, leaving only 302
bytes of stack headroom above that row.

Open, ordered by impact on a faithful VGA + AdLib translation:
1. **Target domains:** exhaustive 715B values after spill and the maximal
   surviving record count; 42A5/1407 against resource, indexed, renderer
   (width 0), physical-alias and UNKNOWN writers; AdLib 01EA under DF=1.
2. **Concurrency:** IRQ arrival, PIC/old INT08/INT62 nesting (post-EOI frames
   retain 26 bytes per level), the 4013 race exclusion and survival.
3. **Saved-stack aliases:** global lowest SP over foreground, IRQ, driver and
   provider paths against the 302-byte headroom; saved-frame survival.
4. **Residual UNKNOWN storage:** 1,902 code-frame bytes, DS residue, protected
   stored bytes, driver residue, 2698 pair extent, 004A FF producer.
5. **Alternatives** (inventory in executable.md): Tandy 02BB, PC-speaker 0196,
   joystick timing, alternate display paths.

Native follow-ups recorded for later, not current priorities: bind entity sound
services, special-graphics briefing redraw, INT61 rebinding, private IRQ 0F70
delivery, protection persistence, validated timing; then SDL3.

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
