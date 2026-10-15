# Steel interaction cells on the observable memory bus

`WriteSteelInteractionCells` at CS:3839..389E is a 102-byte, 47-site leaf that
scans 32 four-byte definitions at DS:172B and writes byte 09 to the live SS cell
map. The bus-aware source is `c/steel_cells_bus.c`; its interface is declared in
`c/steel_cells_bus.h`. The existing RAM core and its result structure remain the
reference API.

The direct bus core takes the existing `LmnSteelInteractionCellsCall` and
returns the existing `LmnSteelInteractionCellsResult`. It does not consume the
near return. The adapter consumes the word at the returned live SS:SP through
the same bus, assigns that value to IP, and increments SP with 16-bit wrap.
Both paths use one canonical 1 MiB memory image, so a cell write can change a
later definition, a saved row word, or the return word.

Definition bytes are read separately in byte0, byte1, byte2, byte3 order. A
machine word is two physically consecutive bytes, with its high byte at
`(physical + 1) & 0xFFFFF`; this differs from wrapping the segment offset first.
PUSH decrements SP before its low-byte then high-byte writes. POP reads the low
byte and then the physically adjacent high byte before incrementing SP. Cell
stores remain explicit forward byte writes even when DF is set.

The C flag path models the arithmetic phases that can be observed by later
memory callbacks. OR/AND/XOR and one-bit SHR define CF, PF, ZF, SF and OF while
AF remains undefined. ROL and RCL define CF and OF while preserving the other
flag values. MUL changes only CF and OF, according to whether DX is nonzero;
the other arithmetic bits are undefined. ADD defines all six arithmetic flags.
INC and DEC define all arithmetic flags except CF, which they preserve. The
live packed-dimension adjustment remains the original word `ADD DX,0101` after
POP DX, so carry between the low and high bytes is retained.

The independent runner in `tests/steel_cells_bus.py` retains all 386 RAM
fixtures from `tests/steel_cells.py`. It compares null-bus results against the
existing core and adapter, then compares byte-ordered direct-core events, full
RAM, registers and defined flags against bounded execution of the pinned code.
Its additional finite cases put definition reads, cell writes, SS saves, and
return reads through the VGA provider; cover SP wrap and live saved-DX/RET
aliases; and check both `SS:000F` at `SS=FFFF` (the return word straddles
physical FFFFF/00000) and the separate `SP=FFFF` physical-successor case.
Together the original cases must cover all 47 sites and eight branch edges.
Four separately compiled mutations have completed-mismatch witnesses,
including a probe that omits the live `ADD DX,0101` flag update and observes
the changed flags at the following `PUSH DX`; a
timeout, callback guard, provider failure, or original-oracle failure is not a
mutation detection.

The runner has a 1,000,000-instruction per-call bound, a 50,000-byte-event cap,
60-second/256 MiB compiler bounds, and a 120-second/512 MiB worker bound. The
Windows process-tree limit is provided by `tools/bounded_process.py`. Its
report is separate from the existing steel RAM report. The bounded suite passes
393 direct-core cases:386 established RAM and seven added bus fixtures, covering
47 sites/eight edges and four completed mutant mismatches. The bus adapter is
checked in the seven added fixtures; the386 RAM cases compare null-bus core and
adapter compatibility. These counts are separate, and overlap the existing102
translated bytes. The VGA saved-DX witness uses first cell1004/SP1006; the RET
witness uses first cell1002/SP1002, where the base is12h (18decimal).
