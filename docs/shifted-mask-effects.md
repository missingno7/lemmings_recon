# Shifted masked 20/40 effects

The two shifted set/reset effect bodies now have C11 cores with live-memory
adapters for their original far returns. Their independently bounded suite
compares the loaded executable against the native cores at 8FF7..909A and
909C..913E. The untouched RETF instructions remain at 909B and 913F and are
consumed only by the boundary adapters.

| Body | Inclusive executable range | Bytes | Decoded sites | C body sites | Normal discovered entry |
|---|---:|---:|---:|---:|---|
| `PlanarShiftedMasked20Body` | 8FF7..909B | 165 | 84 | 83 | 8902 -> 8FF7 |
| `PlanarShiftedMasked40Body` | 909C..913F | 164 | 84 | 83 | 890B -> 909C |

The static range hashes are `1be10dcca6b33ee3819d774b209fa4e18e4c760c9c93b9c884b67ec1e0a3c41b`
and `3bf36e4682b479a6842d87bd055ec981156ac0874b944dceba05f2111a065577`.
All 83 C-accounted sites in each body and all 18 direct branch edges were
observed in the standalone suite. The RETF adapter sites are separate from C
body coverage.

Incoming DS remains live at entry. The first instruction decrements the word at
DS:6704, then the code pushes DS and reads the graphics segment from DS:1FE4.
The `MOV AX,09A9` operand is a relocation site in the packed executable, so the
loaded segment is the relocated game-data segment supplied in the logical call.
The body saves that value in ES for the mask-row scratch. During each row,
`PUSH ES / POP DS` makes the saved, live ES value the segment for the shift byte
and row advances. Saved SS words can alias these fields and the scratch row, so
the core reads the memory-backed stack and carries restored DS/ES values between
rows. The initial incoming DS can differ from the relocated game-data segment.

The mask copy uses the original CL count. `REP MOVSB` and the following zero
sentinel both follow DF; the carry-propagation pass and BX increments always
move forward. Each shift pass applies SHR to the first scratch byte, then RCR
through CL subsequent bytes. INC BX preserves CF between bytes. The shift byte
is unchecked: zero wraps the DEC loop to 256 passes. CL zero makes the RCR LOOP
run 65,536 times, then draws one byte; CL FF makes the drawing count wrap and
the byte loop run 65,536 times. CH zero runs 256 rows. Both variants add the
live source-row advance to SI and the active destination-row advance to DI after
every row.

The VGA bus uses the original ordered word-port writes and SS mirrors. Variant
20 selects set/reset F; variant 40 selects zero. BP's high-byte low nibble
controls enable-set/reset. Every output byte programs bit mask 8, clears IF,
reads the VGA latch through ES:DI, writes FF with STOSB direction from DF, and
executes STI. The fixture models the four VGA planes, latches, Sequencer and
Graphics Controller registers without scheduling IRQs.

The bounded suite ran 54 constructed cases with whole 1MiB RAM, registers,
defined flags, ordered bus events, VGA planes/latches, instruction sites and
branch edges compared. Cases cover shift values 0..7, all 16 enable nibbles,
DF-sensitive copies, multiple rows, the zero/FF count loops, physical and SP
wrap, a relocated game-data segment distinct from incoming DS, scratch/source
overlap, and SS saves that overwrite row or shift fields. Four isolated RETF
probes compare the actual unchanged opcode through the adapter. They exclude
VGA-backed and stack/frame-alias cases because Unicorn reads after hook removal
do not reproduce the hooked device view. Three finite compiled mutants for lost
carry, DF-directed scratch walking, and incorrect 40 cursor adjustment were
detected. Access, instruction, event, and memory limits are hard failures, not
mutant detections.

This closes the two body translations, not every possible alias or incoming
state. Static analysis found only the two normal dispatch jumps listed above;
indirect or modified-code entries remain open. Source-buffer ownership,
arbitrary stack/scratch overlap, native VGA timing, and asynchronous IRQ
ownership remain caller/device obligations. The standalone suite boots no game
and uses only constructed state.
