# SetDrawingLayout (8808)

`SetDrawingLayout` is the 26-byte leaf at main-image offsets `08808..08821`
(10 instruction sites, no branches or internal calls). Its pinned bytes are:

```text
A3 F2 66 89 1E F0 66 89 16 76 1F D1 E8 D1 E8 D1 E8
A3 F4 66 F7 E3 A3 F6 66 CB
```

The three input registers are stored in live DS memory in order: `AX` to
`DrawingWidthPixels` (`DS:66F2`), `BX` to `DrawingHeight` (`DS:66F0`), and `DX`
to `DrawingOrigin` (`DS:1F76`). The routine then shifts AX right three times
and stores the resulting floor-divided byte pitch at `DS:66F4`:

```text
pitch = width_pixels >> 3
```

It multiplies that 16-bit pitch by the stored height with unsigned `MUL BX`.
`DS:66F6` receives the low 16 bits; the returned `AX` is that same low word and
`DX` is the high word. Widths are not rounded up to a byte boundary. The origin
is only stored; it does not participate in the product.

The first three stores preserve entry flags. The three `SHR AX,1` instructions
set their normal flags, then `MUL BX` defines only CF and OF: both are set when
the high product word is nonzero, otherwise both are clear. PF, AF, ZF and SF
are undefined after MUL. IF, DF and the other non-arithmetic flags are
preserved. The native result keeps a concrete representative for undefined
arithmetic bits; differential comparisons claim only the defined mask.

`RETF` pops IP from `SS:SP`, advances the 16-bit SP by two, then pops CS from
the new `SS:SP`; the final SP is `(SP + 4) & FFFF`. Each word uses contiguous
physical bytes with 20-bit wrap under the project's permissive bus model.
Intel's real-address RET pseudocode (`EIP ← Pop(); CS ← Pop()`) and its 16-bit POP definition
(`DEST ← SS:SP; SP ← SP + 2`) in the [Intel SDM, Volume 2B](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2b-manual.pdf),
RET pp. 4-555..556 and POP p. 4-387, describe the two pops. RET also checks that
the top four stack bytes fit the stack limit and specifies a stack fault when
they do not. The adapter's permissive wrap cases do not establish CPU-family
stack-limit/fault behavior; that behavior remains outside this TESTED domain.
Since DS writes happen before these pops,
DS/SS aliases can replace either return word. The C core accepts logical width,
height, origin, segment, flags and an optional `LmnRasterBus`; the adapter
alone owns registers and the far-return frame. With a null bus it uses
canonical 20-bit RAM. With a bus, DS stores and return-frame reads go through
byte callbacks in original order.

The bounded differential suite covers 151 cases at loads `1010`, `1213` and
`2345`. Each fixture runs through both the null-bus RAM path and a byte-callback
RAM bus. It checks all eight low-three-bit width residues, explicit widths 0,
1, 7, 8 and FFFF, zero and overflowing products, all registers, complete
20-bit RAM, ordered DS byte writes, bus flags, and defined MUL/control flags.
Alias and wrap cases include DS=SS return words changed by the five stores, SP
crossing FFFF, and physical 20-bit wrap. A fixture guard rejects any DS output
byte that aliases a known main-CS instruction byte. At SP=FFFF and SP=FFFE, Unicorn's
read-free `RETF` path reads the CS word contiguously at `SS:SP+2` before it
updates SP; the permissive two-POP adapter wraps SP after the IP word, so the
CS read starts at `SS:0001` or `SS:0000`. The fixtures give those two addresses
different words (`B22E` for Unicorn's batch read and `7F00` for the sequential
POP). The suite compares the original instructions through the byte before
`RETF` for those two cases, verifies the Unicorn observation explicitly, and
checks the adapter's return against the explicit permissive two-POP model.
These two cases establish body equivalence and adapter-model regression coverage,
not original-hardware return equivalence across a segment limit.
All other cases execute and compare the complete original far return. All 10
original sites execute overall; there are no branch edges. Three compiled
mutants (rounded pitch, wrong height product, and pixel-width product) are
detected.

The routine itself has no dependencies. Static callers include `036A0`,
`04C11` and `08226`; their larger drawing and VGA contracts remain separate.
The leaf suite establishes no device-specific VGA behavior or broader caller
readiness.
