# `ClearVgaBytes` contract

`ClearVgaBytes` is the exact 63-byte main-image routine at `04DF8..04E36`.
It decodes to 25 straight-line instruction sites and has no branch edges. The
native implementation is in `c/vga_clear.c`; `c/vga_clear.h` exposes a logical
core and a thin register adapter. The current bounded comparison record is
`build/vga-clear-differential.json`.

The routine writes six little-endian words through live `SS` at offsets
`0008`, `000A`, `000C`, `0000`, `0002`, and `000E`. Each mirror write is followed
by the corresponding `OUT DX,AX`. The ordered port/value pairs are:

| Port | Word | Effect |
|---|---:|---|
| `03C4` | `0F02` | Select all VGA sequencer planes |
| `03CE` | `0000` | Clear set/reset |
| `03CE` | `0F01` | Enable set/reset in all planes |
| `03CE` | `0005` | Select graphics-controller mode register with data zero |
| `03CE` | `0003` | Select data-rotate register with data zero |
| `03CE` | `FF08` | Set the graphics bit mask to `FF` |

It then sets `ES=A000`, clears `AL`, and executes `REP STOSB`. The initial `CX`
is the byte count; `CX=0` performs no store. `DF` selects forward or reverse
byte order, and `DI` wraps at 16 bits. The routine leaves `DX=03CE`, returns
`AX=A000`, `CX=0`, and exposes the final `DI`, `ES`, and flags. It does not use
or change `DS`, `SS`, or `SP` in the logical core.

The first `XOR AX,AX` and final `XOR AL,AL` set `PF` and `ZF`, clear `CF` and
`OF`, preserve `IF` and `DF`, and make `AF` undefined. The first mirror write
and first port output still carry incoming flags. The remaining setup outputs
occur after the first XOR; REP stores occur after the final XOR. The adapter
performs the original `RET` after the core by reading the live word at `SS:SP`
through `LmnRasterBus`, then increments `SP` by two. This keeps stack aliases,
including an address in the VGA aperture, visible at the return boundary.

Every mirror byte, store byte, and adapter return byte uses the same 20-bit
physical RAM/VGA bus. Words are byte-contiguous in physical memory, and the
second byte wraps at the 1 MiB bus boundary. The differential fixture models
an unchained planar `A000:0000..FFFF` aperture, graphics-controller read mode
zero and write mode zero, replace operation, and all eight bit-mask bits. The
planes and latches remain device-owned; the CPU aperture bytes are not treated
as a substitute for plane contents. The routine's six outputs establish the
register state used by the clear. The fixture does not model IRQ scheduling or
claim device behavior outside this bounded mode-0 contract.

The suite compares all 1 MiB RAM bytes, all registers, defined exit flags, all
four VGA planes, latches and modeled registers, and the ordered memory/port
trace. Its 33 cases cover zero and nonzero counts, both DF values, `DI` wrap,
large REP counts, `SS:offset=FFFF`, 20-bit wrap, mirrors that target VGA memory,
and live RET words that are fetched from or overwritten in the aperture. Four
maximum-count cases use `CX=FFFF` with `DI=0000` and `FFFF` under both DF
values. Each checks the full plane footprint and verifies that its one
unvisited byte remains unchanged. Plain-RAM stack cases place the live RET word
on, across, and next to the six SS mirror words, including `SP=0008` through
`0010`; this checks the return value after mirror writes. The original routine
is executed only as a bounded instruction range; the game is not booted. The
suite also detects three compiled mutations: a three-plane map mask, ignoring
`DF`, and treating zero count as one store.

The native 368E/36AD callers now connect this leaf to the 8808 layout setter;
see level-drawing.md. Asynchronous VGA ownership and unresolved static regions
elsewhere remain open.
