# MarkDrawingDirtyCells contract

`MarkDrawingDirtyCells` at CS:9A15..9A8E is a 122-byte, 63-instruction leaf
with no recovered call dependencies. Its exact bytes have SHA-256
`ae044d5d888d921c6786e83d2c4bc7898ebc3988c395451e57e8e88b00c8641d`.
`DrawingDirtyCellMapOffset` is the live word at DS:0026; its value is an SS
offset, not a DS pointer.

At entry the routine pushes SI, DI, BP, AX, BX, CX and DX, in that order. Those
seven writes happen before it reads DS:0026. Therefore DS and SS may alias, and
the map word can already contain a pushed register by the time it is read. The
logical C call records the input registers and segments, while the core performs
all stack and map accesses against one 20-bit memory image. A null raster bus
uses ordinary RAM; a supplied bus receives every byte read and write in order.
The adapter alone performs the final RET read and advances SP.

The routine subtracts 0010h from AX and clamps AX to zero when the result's sign
flag is set. This is the original SF test, including its behavior for values
whose high bit is set. It reads the map word after the pushes, sets BP to
`map + 0321h` with 16-bit wrap, and starts SI at:

```text
map + 1 + (clamped_AX >> 3) + 5 * (BX & FFF8h)    (all arithmetic wraps at 16 bits)
```

AX's low three bits add eight to DX before DX is reduced; DX therefore encodes
the rounded byte width. The low byte of CX is rounded in two byte additions:
BX's low three bits may add eight to CL, then CL's own low three bits may add
another eight. Both additions wrap within CL. The routine clears CH and shifts
CX right three times to get the row count. DX equal to zero remains zero until
the first row's `DEC DX`; that inner do/while loop then writes 65,536 bytes.

Each row pushes DX and SI, writes AL=1 to SS:SI while incrementing SI and
decrementing DX, then restores SI and DX from the live SS words. It advances SI
by 40 and compares SI with BP as unsigned words. SI at or above BP exits before
`LOOP`; otherwise LOOP decrements CX, including wrapping zero to FFFF. The
unsigned comparison and 16-bit wrap determine the stop point. The implementation
does not impose a row count or repair zero-size inputs.

Finally it pops DX, CX, BX, AX, BP, DI and SI from live SS memory. Dirty writes
can change the row saves, these register saves, or the active RET word. The core
returns those post-POP values; the adapter reads the possibly changed RET word
through SS and advances SP by two. CMP SI,BP supplies the final arithmetic
flags on every bounded path. IF and DF remain unchanged. AF is omitted only from
intermediate access-flag comparisons where the original instruction leaves it
undefined.

`tests/drawing_dirty.py` compares the whole 1 MiB RAM image, all registers at
the RET boundary, defined flags and ordered byte accesses against the original.
Its 2,066 constructed cases cover all 256 input CL values at all eight BX low
three-bit residues, all 63 instruction sites and 16 branch edges. Additional
cases cover the map read after pushes, DS/SS aliasing, live row/register/RET
aliases, SP values 0000h/0001h/FFFFh, 20-bit physical wrap, a zero-height
one-byte row walk, and the 65,536-store zero-width case. In the constructed
full-SS overwrite case, the live saved registers and RET word become 0101h.
Three compiled mutants
for CL byte rounding, using DS for dirty writes, and stale saved-register
restoration are detected. The checks use RAM callbacks only; they do not model
VGA devices or establish behavior for device-mapped aliases.

Zero width with zero height is excluded: the inner 65,536-store loop combines
with LOOP's zero-to-FFFF wrap, and arbitrary SS aliases can make the resulting
execution extremely large. That untested input remains unresolved; it is not
evidence of dead code or a corrected input domain.
