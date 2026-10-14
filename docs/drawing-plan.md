# Connected planar drawing selection

`drawing_plan.c` composes the tested `882D` preparation, `885E` destination
geometry, shared `939E` selector and four source-row preparation spans directly
on canonical memory. Its logical call consumes the three live prologue saves;
its result contains the selected continuation and any changed child-return
boundary. Only the register adapter uses `LmnRegs`. The wrapper adds no original
code bytes to translation accounting: its constituent ranges are counted once.

The bounded oracle first executes the seven original `8822` prologue sites and
feeds their exact RAM/register/flag state to the native composition. Those seven
sites remain separate from C coverage. The outer far-return frame stays live;
the composition stops before a selected drawing body, `88AB` far return, or a
changed clipping/dirty child-return target. The aligned opaque selection now continues in drawing_render.c; other drawing
bodies remain explicit boundaries. The renderer entry remains UNTRANSLATED until its drawing bodies and platform contracts are closed.

The geometry stores `left & 7` in live DS:A948, then rereads the pushed left
word. It multiplies the row by live destination pitch, restores width through
SS, and adds the shifted left, drawing origin and page offset to the destination.
It writes pitch-minus-rendered-byte-width to DS:6700 and 6704, and repacks the
height and low byte width between CX/DX. No byte count or signed coordinate is
normalized. `BP` mask `0001` and the live left-shift byte select shifted versus aligned
paths; mask `0002` selects paired-mask versus opaque source preparation.

The source spans push and restore control through SS. Mask `0080` changes the two
source cursors by `extent - verticalSkip - verticalSkip - sourcePitch`, with each
word read and arithmetic step at its original point. The live source-row advance
becomes `horizontalSkip - sourcePitch - sourcePitch`. Its store at DS:6702 may
overwrite saved control before POP. Masked paths then select 4000, 8000, 20, 40 in
that priority order. The body names identify the original selector masks; their
VGA and drawing effects remain to be translated. No guard repairs zero counts,
wrap, corrupted saved registers or changed return targets.

`tests/drawing_plan.py` compares whole 1 MiB RAM, all registers, defined flags,
ordered byte accesses and null-bus parity. Its 640-case independent matrix spans
all eight left residues, the four low-bit modes, reverse traversal and overlapping
effect flags. Independent expectations cover destination position, repacked
counts, source cursors, row advances, shift byte and selected body. Additional
cases retain the preparation suite's clipping, live saves and changed-return
aliases. Two connection-specific aliases demonstrate that a dirty-cell write
can change masked-path selection and that the source-row store can overwrite
saved control before effect selection. Compiled wrapper mutations omit source
preparation, restore stale packed height, or select the path from stale control.

The normal 885E entry reaches 88A6 with ZF clear because of the preceding TEST and
taken JNZ. Its JZ-to-88AB edge therefore has a separate constructed incoming-state
test in drawing-dispatch.py. The integrated normal-entry report lists that edge
as excluded, without a whole-program dead-code claim. The UNKNOWN byte 88AA and
decoded but entry-skipped NOP 9996 retain their original classifications. Bus flag
checks use original instruction-boundary snapshots; the MUL write-hook observation
from drawing-inputs.md remains independent evidence.

All scopes use constructed RAM and quiescent IRQ state. Device-mapped aliases,
asynchronous delivery, executing-code corruption, CPU-family segment-limit
faults and the selected drawing bodies remain open. The maintained ASM family
is grouped in `src/planar_drawing.asm`, directly included by program.asm with
unchanged bytes, physical order and end assertions. See drawing-dispatch.md and
drawing-source.md for exact range, case, branch and dependency accounting.
