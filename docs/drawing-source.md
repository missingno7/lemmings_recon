# Planar source-row preparation

`drawing_source.c` owns four bounded continuations from the still-untranslated
`DrawPlanarBitmap` body. The maintained instruction bytes are in
[`src/planar_drawing.asm`](../src/planar_drawing.asm); this C scope ends before
each renderer's VGA setup and does not include a return instruction.

| Entry | Bytes | Sites | Normal stop | Masked routes |
|---|---:|---:|---|---|
| `PrepareShiftedMaskedPlanarRows` 88BF | 79 | 29 | 890E | 4000→8D66, 8000→8B42, 20→8FF7, 40→909C |
| `PrepareShiftedOpaquePlanarRows` 9140 | 43 | 17 | 916B | none |
| `PrepareAlignedMaskedPlanarRows` 93A7 | 79 | 29 | 93F6 | 4000→969C, 8000→953E, 20→9737, 40→97A4 |
| `PrepareAlignedOpaquePlanarRows` 9810 | 43 | 17 | 983B | none |

Each entry copies BP to AX, pushes the live BP on SS, and reads the horizontal
skip from DS:66FC into BP. AX bit 80 selects reverse-source adjustment. That
path reads DS:66F8 extent, subtracts the live DS:66FE vertical skip twice as
separate operations, adds the result to BX and SI, reads DS:66FA pitch, then
subtracts pitch once from BX and once from SI, and twice from BP. The routine
writes BP to DS:6702
before popping BP from the live stack. The masked entries then test restored BP
bits in priority order 4000, 8000, 20, 40. The default and opaque stops are the
next original instruction; routed stops are the selected renderer target before
that target executes.

AX retains the incoming BP value when bit 80 is clear. When set, AX contains
the loaded pitch at the stop. BX and SI change only on the reverse path. CX, DX,
and DI remain live. BP comes from the pop after the DS:6702 store, so DS/SS
aliases can make that store change the restored control bits and the route.
Likewise, PUSH BP happens before any skip, extent, pitch, or vertical-skip read,
so a stack alias can replace those live operands. The core uses one memory image
throughout; only the boundary adapter reads and writes `LmnRegs`.

Words use the low byte at the 20-bit physical address and the high byte at the
next physical address, wrapping at 1 MiB. SP and cursor arithmetic wraps at 16
bits. RAM can be accessed directly or through `LmnRasterBus` byte callbacks;
the scoped routines issue no ports or VGA accesses. All other registers and
non-arithmetic flags stay live. TEST leaves AF undefined; comparisons exclude
only that undefined flag when TEST is the last defining instruction. Original
comparison inputs keep TF clear because TF would dispatch INT 1 after each
instruction and require the out-of-scope handler; the C core preserves TF as an
unmodified flag bit.

`tests/drawing_source.py` checks 236 original/native cases. The entry × reverse
bit × all 16 masked-priority combinations are covered, including priority bits
on the opaque entries. Additional inputs cover cursor and 16-bit arithmetic
wrap, extreme pitch/skip/extent values, SP values 0000/0001/FFFF, a stack word
crossing 20-bit physical zero, DS/SS aliases to every source operand, and the
DS:6702 saved-BP alias. The suite compares whole RAM, all registers, defined
flags, and ordered byte bus events, checks an independent row/cursor model,
verifies that all four executing instruction snapshots stay intact, and compares
the logical core, register adapter, callback RAM, and null-bus RAM. It covers the
92-site union and 32 branch edges across 244 translated bytes.
Three compiled mutants for stale BP restore, one vertical-skip subtraction, and
a missed SI pitch subtraction are detected. The report is
[`build/drawing-source-differential.json`](../build/drawing-source-differential.json)
with integer instruction addresses and fresh input hashes.

The fresh `DrawPlanarBitmap` graph remains UNTRANSLATED (4,411 decoded bytes,
2,303 sites); its native clip and dirty-cell dependencies retain their tested
seams. These source-row continuations do not establish the renderer bodies as
dead or resolve device-mapped memory aliases, VGA ownership, asynchronous IRQs,
or CPU-family segment-limit faults. Run the bounded suite with
`.venv\Scripts\python.exe tests\drawing_source.py`.
