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

## Freeze status (audit 2026-10-22; classes in semantic-audit.md G.7)

`asm-semantic-oracle-v1` is not attained. Criteria 1-3 are met for the main
executable inventory and protected views only; every other component/criterion
cell, and criteria 4-7 for both the full specification and VGA + AdLib, are
NOT MET. Detailed matrices: build/static/u2a-freeze.md and u2b-freeze.md
(working reports, not a status source).

Characterized original nondeterminism (class 3, preserve, never repair):
- N01 creation race: F12/Delete/panel command via IRQ 1874 -> 3E6F -> 4013
  between limit load 30CC and publication 314B sets 0047 to the old count and
  bypasses the equality stop; spill footprint per index is recorded.
- N06 AdLib request/update ordering: an IRQ between song request 03B9 and
  update 03BE can consume the request first; effect latch F0 is last-writer-wins.
- Level 7 stack crossing mechanism: frame 32 + keyboard scan 16 + eight retained
  timer tails of 26 + a ninth (62) reach SP=49B6; overwritten words are known.
  Whether hardware timing realizes it, and what providers add, is U03/U04.

Platform-conditional (class 2): PC01 startup clear, PC02 1407 detector DF0/DS,
PC03 INT33 AX=0003 preservation, PC04 DOS file-service continuations, PC05
process-lived AdLib binding, PC06 startup marker recurrence.

Genuine semantic blockers (class 4), in impact order for VGA + AdLib:
- U01 715B values and control after record spill.
- U02 42A5/1407/4CC9/4D18 target and writer domains.
- U03 global lowest SP and saved-frame/segment alias survival.
- U04 actual IRQ/PIC/old INT08/INT62/mouse/INT24 nesting and schedules.
- U05 remaining UNKNOWN storage (code frame, DS, protected, sound), 2698 extent,
  point suffix 4768+, scratch allocation, 004A FF producer, 8363 caller.
- U06 resource/terrain/object field ownership and allocation/short-read effects.
- U07 AdLib 01EA under DF=1/transformed pointers, failure/preload vector cases,
  dynamic BIOS selector 0621/0626, real OPL/PIT/VGA timing.
- U08 alternatives: Tandy 02BB/5958, PC-speaker 0196 and tail, joystick timing,
  alternate display/palette/option routes (block full freeze, not the AdLib port).
- U09 protected-view composition, stored 098C..0D9D roles, media/persistence.
- U10 effects of reachable processor faults and changed returns.

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
