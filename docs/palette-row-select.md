# Live palette row pointer selection

`SelectAndStepPaletteRow` at5569..55B5 owns77 new decoded bytes/32sites. It
tail-jumps to the tested563E packed or56E2 RGB row core. The original raw graph
body includes both rows (165bytes/79sites); those88 previously translated bytes
are dependencies, not additional prefix coverage. The full native arithmetic
connection includes309bytes/148sites. UNKNOWN55B6 and the pointer-table byte
classifications remain unchanged. The contiguous52D4..563D front ends now live
in maintained palette_frontends.asm; arithmetic remains in palette_steps.asm.

The routine compares the full live DS:1F7C word with4. Equality selects the
CS:52E4 RGB pointer base, while every other word selects CS:52D4 packed pointers.
It pushes DS through SS:SP and pops the actual word into ES before reading
either pointer. A device or alias may change that word; replacing PUSH/POP by
ES=DS loses observable memory and segment effects.

BL is copied to AL, AH is cleared, AX is doubled, and the selected table base
is added into SI. A live CS word supplies the source cursor. BH then undergoes
the same arithmetic independently into DI, whose live CS word supplies the
target cursor. No selector mask, range check or cached table is added. The
word mode, word arithmetic, byte AH XOR and access flags retain their original
widths. Each word reads low then physical-successor high byte on the20bit bus;
SP wraps as16bits between words.

The C connection directly calls the selected row core without adding a near
CALL frame. It returns all twelve transient fields, CS/IP and the row status.
Changed nested channel or row child returns stop at their actual boundary.
The adapter alone consumes the original live nearRET for a ready result.
CL=0 still means65536 iterations. Packed and RGB sticky markers and their
different final sign flags remain the row core's contract.

`tests/palette_row_select.py` requires586 fixtures at both core and adapter
boundaries plus two full65536-iteration zeroCL core cases. The normal matrix
covers every BL and BH byte in both modes, other mode words including0104,
DF, long rows, source/target and stack aliases, actual saved ES, changing word
high bytes, pointer changes between source and target reads, all eight changed
child-return locations, and live outerRET. Ordinary RAM cases also compare an
independent prefix formula and the separate sequential row/channel data model
against full original RAM and CPU state. Ordered bus events compare defined
flags, with RAM fallback and four-plane VGA data/stack cases kept separate.

Seven finite compiled mutants check byte mode comparison, masked selectors,
the wrong target selector, synthesized ES, an early cached target pointer,
an early cached outerRET and ignored child-stop status. Timeout, instruction
or access-budget exhaustion, callback errors and compiler/oracle errors fail
verification and never count as mutant detections. Native workers have time
and process/tree commit limits installed before execution; parent-owned DLL
directories are cleaned after worker exit. Whole instruction coverage is
collected separately from translated byte ranges.

The verified domain requires intact decoded instructions, unchanged CS, TF
clear and quiescent IRQs. Data/table/stack byte-provider effects are explicit;
code-changing providers, hardware segment limits, device timing, valid selector
domains and complete palette-buffer ownership remain open. The initial eight
pointer values are documented in palette-pointer-frontier.md; they do not
establish allocation extents. The fresh dependency graph now leaves531E/536C transition composition next,
retaining4B40 input/IRQ as a separate dependency. Their mirrored pointer setup
uses the now-verified ordering, but must preserve its own savedES and child
frames. The53CA/53F6/53FC/53FE/5401 writer-pointer prefixes remain separate
setup paths. No original game boot is used for discovery.
