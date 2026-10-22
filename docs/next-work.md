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

## Priorities (independent workstreams; supervisor integrates shared metadata)

1. **Entity record lifetime and the 715B callback domain.** Producer/writer
   matrix for record+14 across creation 30A6, update 1F19, clone/bulk copies,
   activation and the 70F0 PUSH / 7159 POP handoff; 2Dh-record allocation and
   reuse bounds. Largest main control-flow risk.
2. **AdLib driver grammar and state.** Engine [0000,05A8): INT61 dispatch, 01EA
   target formula, stream grammar, OPL register writes and timing; state/tables
   [05A8,0B6E). Then score [0B6E,54E3) and effects [54E3,566D) once the grammar
   is fixed. Recover original music logic; never approximate it.
3. **Resource lifetimes.** GROUND request 1000h at DS:1B4B can reach DS:2B4A
   over 2011/2013/201F/25A0/2608/2778 while supplied files end at 1F6A; order
   bytes 54EE and override storage 5566..66E5 bounds. Underpins 42A5 and 1407.
4. **Remaining main transfers.** 42A5 input callback lifetime; 4CC9/4D18 saved-BP
   invariants; 1407 probe traversal (DF, DS, records) and the 2011/2012 word.
5. **Renderer storage.** DS 66F0..6748, A948/A949 initialization before use,
   row footprints and DS/ES/SS handoffs; minimap DF=1 clear over checksum code
   83AF..83C2 versus DF=0 83C1..83D4.
6. **Consumed but unclassified tables.** Palette pointer tables 52D4/52E4 and
   rows; point/pair/word-pattern tables 2698/2778/2788/52BC/531C; UI text,
   keyboard tables (202E overlap), filenames and menu/result streams; CS tables
   44E9/4877/4EE7/4F8A/5507 (keep 5517..5532 separate).
7. **Protected storage and transport.** Overlays 098C/0B9C, 16-byte gap, seed
   0D9C, dynamic INT1/INT3 frames; smallest service model that removes guesses.
8. **Alternative executables.** Tandy and PC-speaker images classified to the
   same bar; inventory joystick/port201 and alternate display paths.
9. **Tooling truth.** graph.py must address C-domain labels and print every
   frontier/provider seam in bottom-up views; coverage must reconcile its
   receipts with the difftest registry; verify.py must record its full input and
   resolved-tool closure.

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
