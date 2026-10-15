# Palette byte-port writers

The pinned leaves `WriteAttributePalette` at5425..5446 (34bytes/21sites) and
`WriteMappedDacPalette` at54C4..5506 (67bytes/40sites) have no callees. Their
canonical state is the original memory image plus transient CPU fields. The C
core stops before each actual nearRET; its adapter consumes the live word only
for a ready result. Missing IN/OUT providers stop before that instruction,
retaining all prior stack, data and flag effects. Byte providers may mutate
canonical memory; they do not return CPU registers. The verified domain requires
intact decoded instruction bytes, unchanged CS, TF clear and quiescent IRQs.
Provider writes to data and table bytes are tested; writes that change decoded
instructions are rejected by the oracle and remain outside this contract.

5425 executes CLI, copies CH into BL, clears CH, reads the live DS:1FDA base,
and adds6 to DL alone. It reads status, pushes DX, changes DL toC0, then outputs
BL followed by one DS:SI byte per iteration. LODSB follows DF; INC BL wraps as
a byte and defines flags while preserving CF. LOOP uses the full word CX, so
initial CL=0 executes65536 iterations. The actual popped DX selects the second
status read. The final output uses its DH with DL=C0 and AL=20; STI is
unconditional. BH, AH and other untouched fields remain live.

54C4 pushes DI before CLI. A live DS:200C byte equal toFF skips sequencer
blanking. Otherwise it writes index1 to3C4, increments DX, reads3C5, sets AL
bit5, writes it and pushes AX followed by DX. It zero-extends incoming CH,
adds it to CS:5507 in DI, and clears CH. Each iteration reads a fresh CS:DI
index byte, increments DI forward, writes3C8, increments DX, then reads and
writes three sequential DS:SI bytes through3C9. These LODSB operations follow
DF. DEC DX and full-word LOOP complete the iteration.

The second DS:200C read is independent of the first. If it differs fromFF,
the routine pops actual DX and AX, clears AL bit5 and outputs it. Changing the
control between reads can therefore cause previously unpushed words to be
consumed or saved words to remain on the stack. After unconditional STI it pops
the actual DI. The C preserves that imbalance, including its effect on outerRET.

`PaletteBlankingControl` names DS:200C's observed role, not an IRQ synchronization
guarantee. The `MappedDacPaletteIndexes` base atCS:5507 has sixteen apparent
bytes `00 01 02 03 04 05 14 07 38 39 3A 3B 3C 3D 3E 3F`. Initial CH and iteration
count are unchecked. Reads can continue into adjacent code or UNKNOWN bytes,
with DI wrapping at16bits. Those classifications remain unchanged and this
base/size does not establish a valid table domain. CS52D4/52E4 palette pointer
producers, source-buffer ownership, 531E/536C transitions and4B40 input/IRQ
ownership remain separate work.

`tests/palette_ports.py` requires577 fixtures at both boundaries, two full
zero-count core cases, all61 sites/eight branch outcomes and six completed
mutants. It compares the pinned original instructions with the C
core and adapter. Normal disjoint RAM cases also use an independent port-stream,
cursor, save-frame and full-memory formula. Constructed providers test live
source, table, save, outerRET and control effects; ordered events compare defined
flags at each access. RAM fallback, physical20bit wrap, offset16 cursor/SP wrap,
and four-plane VGA-backed data/stack cases stay explicit. Word high bytes use
physical+1, wrapping at20bits, while SP wraps between words.

The two zero-count core fixtures execute all65536 iterations with instruction
and access limits. Event order is hashed and phase flags are stored in bounded
packed arrays. Native workers receive process/tree memory ceilings before
execution and hard-exit on callback or access-budget failures. Such failures,
timeouts, compiler errors and oracle errors never count as mutant detections.
Parent-owned DLL directories are removed after worker exit. Six compiled mutants
exercise byte versus word ADD, DF, control caching, saved DI, unconditional STI
and incorrectly masked indexes.

These are byte-port provider contracts. No hardware palette/register model,
device timing, IRQ scheduling, hardware segment-limit behavior or complete caller
ownership is claimed. No original game boot is used for discovery.
