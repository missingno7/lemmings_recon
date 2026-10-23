# Aligned opaque planar drawing body

`PlanarAlignedOpaqueBody` at `983B..9966` is the first aligned opaque VGA
body selected by the translated `885E/939E` dispatch. The pinned static image
range is 300 bytes with SHA256
`7ec5a5c38a03eee4062954918712e47d8c102ca1ece91d96496530c2d3f4edd0`. The
two bytes at `98F4` and `9932` remain explicitly `UNKNOWN` and are excluded
from the C accounting. The remaining 298 bytes comprise 149 instruction
sites: 297 bytes/148 sites in the logical body and the final `RETF` at `9966`
in its register adapter. This accounting does not classify either UNKNOWN
byte as dead.

The logical API in [aligned_opaque.h](../c/aligned_opaque.h) carries only the
state the body reads: incoming DS, the relocated game-data segment, SS:SP,
packed CX counts, the original DX word, SI, DI and flags. `width_state` keeps
the original DX lanes together: incoming DH becomes the plane counter after
`XCHG DL,DH` and `XOR DH,DH`; incoming DL is discarded by those instructions.
The byte count comes from CL. The body overwrites AX, ES and BP before their
incoming values matter, leaves BX and SS unchanged, and returns AX/CX/DX/SI/DI/
BP/SP/DS/ES/flags. It keeps every push, pop, segment change and word alias in
the caller's single 1 MiB memory image.

The first `PUSH DS` happens before the body reads `DS:1FE4`, so a stack write
can change the graphics segment that is loaded. The later literal `MOV AX,09A9`
uses its relocated value, `load_segment+09A9`; the caller passes that value as
`game_data_segment`. Each row and each inter-plane source-extent adjustment
executes the original live `PUSH DS`, `MOV AX,game_data_segment`, `MOV DS,AX`,
memory read, arithmetic, and `POP DS` sequence. Those writes and reads can
alias SS save words, drawing fields, the far-return frame, or device memory.

The body sets ES to A000 and emits the original mirrored word writes in SS at
offsets `0008`, `000A`, `000C`, `0000`, `0002`, and `000E`, with ordered
Sequencer/Graphics Controller port writes. Each pixel first reads ES:DI to
load VGA latches and AL, then executes `MOVSB` from DS:SI to ES:DI. The source
and destination cursors follow DF. CLI runs before each row's byte loop and
STI follows it, so the body sets IF even when IF entered clear. It does not
repair zero counts: CL=0 makes `LOOP` execute 65,536 byte copies, and CH=0
iterates 256 rows through the decrement wrap.

The first three passes save and restore the live SI/DI/CX words and decrement
BP after the pass. The fourth pass does not save those cursors or test BP
again. Thus DH values 1, 2, and 3 stop after that many passes; zero underflows
on the first decrement and values above four still execute all four passes.
The first pass selects all planes with set/reset enabled for planes 1..3;
later map masks select planes 1, 2, and 3 in order. The final pass leaves its
updated cursors live. The result's AX is the relocated game-data segment
loaded by the final row's original `MOV AX`.

`lmn_draw_aligned_opaque_core` stops after the final `POP DS` at `9965` with
the outer IP:CS words still live at SS:SP. Only the `LmnRegs` boundary adapter
consumes the far return. It reads each low/high byte in order, wraps each
physical address at 20 bits, advances SP by two with 16-bit wrap, and returns
without executing the target. The bounded RETF comparison uses an isolated
single-instruction probe after removing Unicorn's memory-read hook, as required
by the RETF observation limit documented in [level-drawing.md](level-drawing.md).
That probe executes `9966` on 52 of the 55 cases. The two `SS=A000` device-stack
cases are excluded from the original-instruction probe, while their live-frame
adapter reads remain compared by the native bus model. The `SP=FFFE` case is a
separate permissive two-pop adapter check; it does not establish a CPU-family
stack-fault contract. Thus the static 149-site accounting consists of 148 body
sites plus the RETF site, with the RETF single-step subset and boundary-only
case called out separately in the generated report.

`tests/aligned_opaque.py` runs 55 constructed cases against the original body.
It compares all registers at the pre-RETF boundary, full RAM, defined flags,
ordered byte reads/writes and port events, plus all four VGA planes, latches
and device registers. The union covers all 148 logical-body instruction sites
and 26 branch edges; the isolated RETF probe covers the adapter's 149th site in
52 original-instruction probes.
Ordered access-event flag checks use the per-instruction defined mask: `0x0FD7`
at entry and after arithmetic/DEC, and `0x0FC7` after logical operations where
AF is undefined. This retains the defined AF checks following the row and
extent `ADD` and plane-counter `DEC` instructions.
Cases include DF in both directions, plane limits 0..5 and FF, widths 1/2/7,
zero CL and CH, 20-bit physical and 16-bit cursor/stack wrap, DS/SS save and
return aliases, and SS=A000 stack writes. Independent plane-footprint checks
cover normal DF=0 and DF=1 rows. Null-bus parity is checked separately against
a raw-RAM callback and makes no VGA-equivalence claim.

Three compiled mutations are detected: omitting the latch read, leaving DS at
the temporary game segment after a row, and selecting the wrong final plane
mask. The complete case list, branch edges, executed addresses and input hashes
are in `build/aligned-opaque-differential.json`. The body requires intact code,
constructed memory and quiescent IRQs. It does not translate the arbitrary
incoming `PlanarAlignedOpaqueFirstPassLoop` block (the first-pass LOOP, not a separate routine entry), and the far renderer entry at `8822`
remains `UNTRANSLATED`.
