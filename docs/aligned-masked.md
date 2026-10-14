# Aligned masked planar body

`PlanarAlignedMaskedDefaultBody` begins at `93F6` and reaches the far return at
`953D` from the selector's only discovered external edge, `93F1 -> 93F6`. The
physical interval `93F6..953D` is 328 bytes with SHA256
`2d8b7058f1af630f270c7504ed7e1b1c520240be07ba9292b714367a3e490408`. The two
bytes at `94C7` and `9507` remain `UNKNOWN` (`90` each) and are excluded. The
remaining 326 decoded bytes contain 166 instruction sites: 165 sites / 325
bytes in the C core, plus the `RETF` site / one byte in the boundary adapter.
This accounting makes no reachability claim about either UNKNOWN byte.

The logical input and result are in [aligned_masked.h](../c/aligned_masked.h).
The core runs from `93F6` through `POP DS` at `953C`; its live outer far-return
words remain at `SS:SP`. The adapter reads those words in byte order and returns
without executing the destination. The C state is backed by the caller's single
1 MiB memory image, so pushes, popped values, saved cursors, drawing fields and
the far-return frame can alias each other. The initial `PUSH DS` precedes the
read of `DS:1FE4`, which supplies the source segment through the incoming data
segment. The relocated immediate `09A9` is passed explicitly as
`game_data_segment` for the row and plane fields; those segments can differ.

The original `DH` becomes `BP`; `DL` is discarded by the exchange and zeroing.
Limits 1, 2 and 3 stop after that many passes. Limit 0 underflows on the first
decrement, and limits above 4 still reach all four passes. The fourth pass has
no final `BP` decrement. `BX` starts as the mask cursor: the first pass reads
`DS:BX`, increments `BX` unconditionally once per byte, then adds the live
source-row advance once per row. This increment ignores `DF`. `LODSB` and
`STOSB` move `SI` and `DI` according to `DF`; later planes use the live
source-plane extent and do not change `BX`.

The first pass selects all planes, enables set/reset for planes 1 through 3,
and writes a per-byte bit mask from `AH` through the Graphics Controller's
bit-mask register. The source byte replaces selected bits in plane 0 and clears
selected bits in the other three planes, preserving bits outside the mask from
the VGA latches. Every first-pass byte performs `CLI`, the destination latch
read, `LODSB`, `STOSB`, and `STI`. The first pass sets IF after every byte,
including when IF entered clear. For planes 2 through 4, the body selects
GC logical OR with a full bit mask and enables one Sequencer plane at a time.
Those passes use one `CLI`/`STI` pair per row. Ordered port writes and the live
SS mirrors at `0000`, `0002`, `0008`, `000A`, `000C` and `000E` are preserved.

Each row reloads the source-row advance from live `game_data_segment:6702`,
adds it to `SI` (and also `BX` in the first pass), and reloads the active
destination-row advance from `game_data_segment:6704` for `DI`. Each inter-plane
step reloads the source extent from `game_data_segment:66F8`. These are original
memory reads after the row or save pushes; stack aliases can change them. The
code preserves 16-bit cursor, count and stack wrap plus 20-bit physical-memory
wrap. `CL=0` runs 65,536 byte iterations, and `CH=0` runs 256 rows. The final
`AX` is the last source-row advance. A first-pass-only exit leaves `DX=03CE`,
while exits that reach later plane setup leave `DX=03C4`; `ES` is `A000`. The
outer `POP DS` loads the live word at its stack slot, which aliases may have
changed from the incoming data segment.

`tests/aligned_masked.py` compares the original body and native core in 20
constructed cases. It covers all 165 core instruction sites and 26 branch
edges, including both `DF` values, mask preservation, plane limits 0/1/2/3/4/5
and `FF`, zero byte/row counts, segment and cursor wrap, DS/SS aliases, VGA
source reads, `INC BX` crossing `7FFF` to `8000`, incoming `DS=6000` distinct
from relocated game `DS=1BBC`, and `SS=A000` stack writes. The `SP=FFFE` case
checks the return-frame wrap. The independent plane-footprint checks use
`tests/minimap_vga.py` for mode-0 replace/OR, latches, bit masks and port state.
Null-bus parity uses raw RAM callbacks and makes no VGA-equivalence claim.

Four original `RETF` probes execute the unmodified `953D` opcode after removing
the code, read, write, output and physical-wrap hooks at the body boundary.
`SS=A000` and `SP=FFFE` receive explicit adapter checks and are excluded from
that single-step subset. The suite detects three compiled mutants: omitted
first-pass latch reads, failure to restore DS between rows, and a repeated
plane-3 map mask for the last pass. It runs in `run_bounded` with a 180-second
timeout and a 512 MiB process / 768 MiB process-tree commit limit. Callback
traces stop recording at 500,000 whole-bus events and 200,000 VGA events; the
original instruction cap is 3,000,000. A native event-cap hit exits the
disposable worker with a guard status that the parent maps to verification
failure; the original emulator stops and reports the same exhaustion distinctly
from a mismatch. Callback errors retain only their first string. Exhaustion is
never recorded as a detected mutant. DLLs live in an owned temporary directory
that is removed after the bounded worker exits.

The suite report is generated at `build/aligned-masked-differential.json`.
The body assumes intact executing code and quiescent IRQs; it does not establish
VGA timing or asynchronous interrupt behavior. The separately entered `988B`
shared-loop path and the rest of the masked/shifted renderer family remain
outside this core's contract.
