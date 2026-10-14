# Level drawing initialization and clear tail

`InitializeLevelDrawing` at `368E..36AC` is 31 bytes and 11 instruction sites.
It sets DI=4A40 and CX=8880, calls the native `ClearVgaBytes`, then far-calls
`SetDrawingLayout` with width 1664, height 164 and origin 4A40. The resulting
pitch is 208 and the low extent word is 8540. It reads the live DS input graphics
segment at 1FF4, increments it with 16-bit wrap, and publishes it at 1FE4.
The final INC defines arithmetic flags except CF, which remains clear from MUL.

`ClearLevelDrawingTail` at `36AD..36B5` is nine bytes and three instruction
sites. It sets DI=CC40 and CX=0340 and jumps to the same clear leaf. It does
not push an additional return word. Both entries preserve incoming DF and IF;
the clear changes ES to A000 and clears all four planes in the original order.
The forward initialization footprint is 4A40..D2BF; the reverse footprint wraps
through 0000. The tail footprint is CC40..CF7F forward and C901..CC40 backward.

The native core composes the two leaves directly on canonical memory. Near
CALL writes its return IP to live SS; far CALL writes CS first and IP second.
Each callee reads the resulting frame after its stores, so mirrors, layout
fields and aperture aliases can change the actual return. The core exposes a
changed inner IP/CS before executing that target. Normal returns reach the
original segment publication and outer RET. The tail reads only the outer RET.
No saved record or device state is copied into a shadow game state.

The 27 bounded cases compare all RAM, registers, defined flags, four planes,
latches, device registers and ordered port/MMIO events. Independent checks cover
the entire plane footprint including untouched bytes, all five layout fields,
the six exact port words and live segment publication. Cases cover both DF
values, segment increment zero/overflow, three relocation loads, SP wrap,
physical 20-bit wrap, live CALL frames aliasing the input segment, DS/SS layout-return
aliases, aperture returns and early changed near/far exits. All 14 caller sites,
49 integrated sites and the single tail JMP edge execute. Three compiled
mutants corrupt publication, tail count and changed-far-return handling.

Unicorn 2.1.4 has an independently reproduced RETF hook artifact: a memory-read
hook covering its stack leaves IP at the RETF instruction even when the stack
contains the correct return. The harness stops at that opcode, refreshes the
device/A20 stack-read boundary, removes the read hook, and executes the original
RETF once. It compares the actual resulting IP/CS rather than replacing them.
It then refreshes the translation cache before restoring observation hooks.
The connected fixtures keep the inner RETF SP below FFFE; the isolated layout
suite separately records Unicorn's SP-boundary discrepancy against the
project's permissive two-POP adapter model. CPU-family stack-limit faults remain
outside this domain. See [drawing-layout.md](drawing-layout.md).

The domain requires intact executing code, quiescent IRQs, and the documented
unchained mode 0 VGA fixture. Layout DS stores in these connected cases use
ordinary RAM; aperture stack accesses remain device-owned. This closes these
two callers without translating their broader 36B6/394F level consumers,
terrain, minimap or asynchronous VGA ownership.
