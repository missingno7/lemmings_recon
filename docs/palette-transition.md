# Palette transition callers

531E `TransitionPaletteToSlot1` and536C `TransitionPaletteToSlot2` supply source
slot0, target slot1/2 and count16 to the shared55B7..563D body. The two entry
prefixes and shared body own157 unique bytes/82sites. They compose the tested
5425/54C4 writers,563E/56E2 rows and channel helpers, and1550 status wait.
The integrated union is508bytes/268sites. No UNKNOWN byte is added to C ranges.

The full DS:1F7C mode word is compared once:4 selects RGB and every other word
selects packed data. The body saves actual ES, pushes DS and pops its actual
word into ES, then reads source and target CS pointers separately. Tables,
data buffers and all save/return words remain in canonical memory. Provider
changes to the mode do not change the selected branch on later iterations.

Each pass saves CX/SI, outputs the current source palette, consumes the actual
writer RET and restores actual SI/CX. It then saves CX/SI/DI and calls the row
step. The row's returned ZF decides whether the transition is done. A changing
packed row waits three status cycles; RGB waits one. Those waits replace ZF,
but the original path loops with an unconditional JMP. The C retains the prior
branch decision while preserving the flags actually returned by the waits.
Rechecking ZF after waiting would prematurely terminate the transition.

The row marker records a difference at step entry. Even a step that reaches
the target requests another output/step pass. Conversely, a packed row can
clear unused source bits while reporting no decoded-channel difference; the
transition does not add a corrective output. Writer LODSB follows DF, while
row INC cursors still advance forward. Neither behavior is normalized.

Writer/step/wait returns at55E4/55EC/55F1/55F4/55F7 and5627/562F/5634 are actual
near frames. Changed caller RET targets stop before subsequent caller effects.
The row core's separate internal channel/child-stop statuses are propagated.
Missing byte providers also retain the current child frame and exact state.
Finishing pops the live DI/SI/CX/ES words and stops before5600 or563D; only
the boundary adapter consumes the live outer nearRET. The normal deepest
packed call frame is16bytes below entry SP. Word high bytes use physical+1
with20bit wrap; SP wraps16bits between words.

`tests/palette_transition.py` compares all CPU fields, defined phase flags,
ordered data/stack/I/O events, full RAM and VGA state against pinned original
instructions in 1,191 fixtures at both core and adapter boundaries (2,382
comparisons), covering all 82 caller and 268 integrated instruction sites and
all 10 caller/40 integrated branch edges. Its constructed matrix covers all
source bytes at both entries and modes, signed extremes, overlap, DF, blanking,
mode words beyond2/4, static palette inputs, live saved fields, all eight caller
returns and eight internal row returns, missing providers and control-induced
stack imbalance. A separate scalar model predicts the ordered palette output,
convergence, extra pass and status-cycle counts. It checks the data footprint
outside the16-byte stack window; the independent native/original comparison
still checks every RAM byte without exclusions. NULL-bus repeats retain full
I/O phase-flag comparisons.

Workers run serially with time and process/tree commit ceilings installed before
execution. Instruction/access/callback exhaustion fails verification and never
counts as a mutant mismatch. Packed flag arrays and bounded traces avoid growing
instruction histories; parent-owned temporary DLL directories are cleaned after
workers exit. Six finite mutants cover shortened packed waits, premature finish,
mode rereads, cached saved fields, cached ES and ignored caller RET targets.

The verified domain preserves decoded instructions and CS, with TF clear and
IRQs quiescent. Byte providers are explicit opaque contracts, not a hardware
palette or timing model. Segment-limit exceptions, arbitrary nonconverging data
or providers, pointer/buffer initialization ownership and4B40 input/IRQ remain
open. The original convergence and polling loops remain unbounded in C. No game
boot, runtime snapshot or persistent shadow game state is introduced.

The later split-palette/briefing extension lives in the same C module and native
suite. Its new cases use tests/verification.py; the original1191-case transition
campaign remains an unchanged regression path. See split-palette.md for the
5329/534B row pairs,53CA publication and46B9/46A2 connected raster/fade contracts.
The suite emits a separate scoped report for those new regions; retaining any
older report does not renew its consumed-input evidence.
