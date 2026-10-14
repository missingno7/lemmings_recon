# Shifted read-mask drawing body

`PlanarShiftedMasked4000Body` is the closed normal-entry body at `8D66..8FF6` in the
pinned DOS VGA image. It is 657 physical bytes: 656 bytes decode after the
explicitly unresolved `UNKNOWN` byte at `8F8D` is excluded, and one of those
decoded bytes is the adapter-owned `RETF` at `8FF6`. The C core models the 368
decoded sites through `POP DS` at `8FF5`; the adapter consumes the original
return frame with the unchanged instruction at `8FF6`. Static review found
one normal incoming edge, `88F0 -> 8D66`, and no direct calls or outgoing
direct edges. Indirect or modified-code entries are not proved absent.

The header gives the core an explicit call/result contract. Inputs include the
incoming and relocated game-data segments, live stack segment/offset, packed
row/width counts, DX state, source/mask/destination cursors and flags. Results
return AX/CX/DX/SI/BX/DI/BP, SP, DS/ES and flags. `lmn_draw_shifted_read_mask_core`
executes through the final `POP DS`; `lmn_draw_shifted_read_mask_adapter`
then reads the live far-return words and publishes IP/CS/SP. The relocated
`MOV AX,09A9` value comes from the supplied game-data segment. The routine has
no byte `IN` or `OUT` instructions and accepts no byte-I/O provider.

Entry first decrements the row-advance word at incoming `DS:6704`, including
its memory write and `DEC` flags, before saving DS. DS then becomes the source
segment loaded from incoming `DS:1FE4`, while ES becomes the relocated game
data segment. `XCHG DL,DH` followed by `XOR DH,DH` leaves the incoming high
byte as BP's plane limit. Setup disables interrupts and writes all planes to
Sequencer port `03C4`, then writes the initial Graphics Controller words to
`03CE`: `0000`, `0E01`, `0003`, `0805`, `0807`, and `0802`. Each output keeps
the original SS mirror store and order.

The first pass caches the mask at game-data `DS:6748`. For each source row,
`REP MOVSB` copies CL bytes from the live mask cursor through DF, and `STOSB`
adds the zero sentinel through the same DF direction. The row's scratch end
updates BP. DS is then restored from the saved game ES and ES becomes A000.
The body reads the live shift byte at `DS:A948` and shifts the cache forward:
`SHR` on the first byte, then `RCR` on each of the next CL bytes. `INC BX`
preserves the carry between bytes. After restoring the original packed CX, the
body clears CH and increments CL, so the following cache pass processes width
plus one bytes. Each byte reads A000 in VGA read mode 1, ANDs that result into
the cache, and advances BX and DI forward regardless of DF. With GC compare
`08` and care `08`, read mode 1 supplies the plane-3 byte as a per-pixel bit
mask; it is not a scalar all-pixels match. At row end, the mask-source cursor
advances by the live game-data word at `DS:6702`, and DI advances by the live
`DS:6704` value that entry already decremented. The cache pass restores its
outer registers and leaves BX at `6748`.

Each drawing row copies CL source bytes to game-data `DS:6706` through DF and
writes a direction-sensitive zero sentinel. It switches DS to game data and
ES to A000, rereads `DS:A948`, shifts the scratch bytes forward with the same
SHR/RCR carry chain, then processes width plus one bytes. The first plane
reads a mask byte from BX, writes `mask<<8 | 08` to port `03CE` and the SS bit
mask mirror, reads A000 at DI to load the VGA latches, then loads the shifted
source byte and ANDs it with the mask before STOSB. Setup's `AX=0003` writes
zero to GC3 (replace, no rotation); the index value `03` is not the data byte.
The first-pass read/modify/write therefore preserves the unmasked latch bits
while set/reset supplies zero to the enabled planes.

If BP remains nonzero after the first pass, the body adds the live
`ES:66F8` plane extent to SI, configures GC3 for OR, sets the bit mask to FF,
and selects sequencer map mask `02` through DX=`03C4`. The next source pass
software-ANDs its shifted source with the cached mask. The third and fourth
passes repeat the live plane-extent advance and select map masks `04` and
`08`. The second pass alone brackets each row with CLI/STI. The first pass
uses DX=`03CE`; after a later pass is entered, DX remains `03C4` through the
shared exit. The routine does not save or restore DX. The final pass at `8F9B`
has no outer DI/SI/CX/BX save frame, so its final live cursors/counts escape;
the earlier pass bodies restore that frame. BP is decremented only after the
first three passes. A zero limit underflows and reaches the fourth pass; any
limit of four or more also reaches it. The shared `STI` at `8FF4` sets IF
before the final `POP DS`.

The translation preserves 16-bit offset wrap, 20-bit physical RAM wrap,
direction-sensitive string copies, forward scratch shifts under DF, changing
live strides/extent/shift reads, stack aliases, scratch overlaps, and the
original RMW flags observed at bus callbacks. It keeps AF physically unchanged
where the source instruction leaves AF undefined; differential flag comparison
uses the documented arithmetic (`0x0FD7`) and logical (`0x0FC7`) masks.

## Bounded differential evidence

`tests/shifted_read_mask.py` runs the relocated original body and native C in a
worker limited to 180 seconds and 512 MiB process commit (768 MiB Windows job
tree commit). It caps the original at 8,000,000 instructions, ordered bus
events at 4,000,000, and retained VGA-device events at 400,000. Bus event
digests stream; only the bounded device trace and a small event prefix are
retained. Callback failures and guards hard-exit the worker and fail
verification; neither is recorded as a killed mutant. The suite garbage
collects between cases and the temporary DLL directory is removed after the
worker exits.

The completed run covers 25 constructed cases, all 368 core sites and 53
branch edges, and detects all three compiled mutations (lost RCR carry, omitted
mask-source row advance, and omitted source-plane extent). It compares full
RAM, registers, defined flags, SS mirrors, ordered reads/writes/word outputs,
VGA registers/latches/planes, and the adapter contract. Thirteen ordinary
DF-clear, nonalias fixtures also compare the VGA footprint against independent
packed-byte mask-cache, source-shift and plane-write calculations. Other cases
exercise shifts 1..7, DF, zero shift, plane limits 0..5 and FF, zero CH, CL=FF,
distinct incoming/game DS, stack/scratch field aliases, scratch/source/mask
overlap, physical wrap and SP wrap.

For the width-zero case, `LOOP` really wraps to 65,536 iterations. Its
constructed game-data segment is zeroed and seeds `A947=01`, `A948=08`; this
makes the mask's full-segment carry sweep leave the next live A948 read at one,
so the following source sweep is also bounded. This is an explicit finite
memory domain, not a repair or general guarantee for the unchecked caller
path. The CL=FF case likewise preserves the `INC CL` wrap and 65,536-byte
drawing loop under the hard limits. Arbitrary shift/width combinations can
modify A948 through the live scratch sweep and may exceed those limits; such
exhaustion fails the run.

Four adapter comparisons and three single-step original RETF probes pass.
The RETF probes remove Unicorn's memory hooks before stepping the original
opcode and use ordinary RAM return stacks; SS=A000/device-backed return words
and the wrapped SP boundary are excluded from that subset. A separate adapter
probe starts with `SS=FFFF, SP=0002` and exercises stack pushes through the
16-bit and 20-bit wraps before reading the far-return words. The fixture models the
documented four-plane VGA device and quiescent IRQs, not scanout or asynchronous
interrupt timing. The one decoded-but-unresolved byte `8F8D` remains UNKNOWN;
no behavior or dead-code claim is made for it.
