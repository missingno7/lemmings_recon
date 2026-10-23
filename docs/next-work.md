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

## Freeze status (re-audit 2026-10-23; classes and escape rule in semantic-audit.md G)

`asm-semantic-oracle-v1` is not attained. Criteria 4-7 are BLOCKED for both the
complete specification and VGA + AdLib; classification discipline itself is
satisfied. Criteria 1-3: inventory met for the main image and protected views;
classification and control flow blocked (criteria 1-3 re-audit was cut off by
a provider content flag; its boundary packets are in u2a-freeze-v2.json).
Working detail: build/static/u2b-freeze-v2.md (not a status source).

Characterized, outside the supported native runtime domain (class 3; preserve,
never repair or replace with success):
- Control escapes closed by the G rule, each with a full boundary packet:
  no-strip sprite escape at 715B (Packet S), first corrupted detector call to
  CS:0061 at 1407 (D), partial 25A0 clear calling CS:0000 at 42A5 (I), steel
  near return to 3709 (R), one-row dirty width-0 return to 0101 (Z).
- N01 creation race (30CC..314B via 1874 -> 3E6F -> 4013).
- N06 AdLib request/update ordering (03B9/03BE, F0 last writer wins).
- W01 width-0 RCR sweep before 8DF1; W02 stale/overlong resource, palette,
  template and stream relations (these continue into normal gameplay).
- Level 7 stack crossing mechanism to SP=49B6.

Platform-conditional (class 2, metadata/platform-profile.json): PC01 startup
clear, PC02 1407 detector, PC03 INT33 AX=0003, PC04 DAT/cache file
continuation, PC05 process-lived AdLib, PC06 startup marker, PC07 graphics
arena, PC08 completed floppy/protection seam.

Genuine class-4 blockers (B01-B14), impact order for VGA + AdLib:
- B01/B02 ordinary spill evolution and surviving count; descriptor/strip/
  legitimate 715B target domains.
- B03/B04/B05 ordinary 42A5/1407 writers, editor saves and external register
  writers, provenance of the named changed cursors and cache paths.
- B06/B07 caller-rooted stack, IRQ and service survival; renderer/scratch/heap
  aliases where they affect ordinary gameplay.
- B08 UNKNOWN storage roles (main + AdLib), 2698/4768/6706 extents, 004A FF
  producer, 8363 caller; B09 opaque LEVEL/GROUND/terrain fields and 1FF8..1FFD;
  B10 1FF2 tail and provider memory footprints; B11 protected stored roles.
- B12 AdLib 01EA domains, allocation failure/preload vectors, BIOS 0621/0626,
  real OPL/PIT/VGA timing.
- B13 alternatives (block full freeze, not an AdLib-only port).
- B14 ordinary processor faults/returns outside the accepted packets.

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
