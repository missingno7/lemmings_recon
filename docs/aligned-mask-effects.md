# Aligned masked 20/40 effects

The native leaf cores cover the two independently dispatched aligned masked
effects. Static body boundaries are 9737..97A2 and 97A4..980E. Each body has
48 decoded instruction sites. Their following RETF instructions remain explicit
boundary adapters at 97A3 and 980F.

| Variant | Full byte span including RETF | SHA256 | Bytes/sites in core | Edges |
|---|---:|---|---:|---:|
| 20 | 9737..97A3, 109 bytes | `256c2fda581e791cf65e4f8f648793d2b7e2e05aaa922e02f9fca0604acec8a1` | 108 / 48 | 5 |
| 40 | 97A4..980F, 108 bytes | `0782d7c3bc45cdd5e649268f45a7c3a5fe1f3a81f1a9db69d8311bcd50054f31` | 107 / 48 | 5 |

The setup pushes the incoming DS before reading the graphics resource segment
from incoming `DS:1FE4`. That segment becomes the mask source. The body loads
the set/reset enable mask from BP's high-byte low nibble (the 20 path's reset
value is F and the 40 path's is zero), programs VGA word ports,
and sets `SI = BX`. Each inner iteration reads the mask at `DS:BX`, increments
BX regardless of DF, writes the mask to the VGA bit-mask register, reads the
destination to load VGA latches, and stores `FF` through `ES:DI`; DF controls DI.
CLI/STI surrounds every byte.

The row cursors preserve an original asymmetry. Variant 20 adds live
`gameDS:6702` to SI and leaves BX on its contiguous mask walk. Variant 40 adds
that word to BX and leaves SI at its initial copy of BX. Both add live
`gameDS:6704` to DI. Row words are read after live SS pushes, so SS aliases can
change the values before use. CH=0 means 256 rows and CL=0 means 65,536 bytes
per row. All 16-bit cursor and SP arithmetic wraps, with physical memory
addresses reduced modulo 1 MiB.

The core result exposes AX, CX, DX, SI, BX, DI, BP, SP, DS, ES and FLAGS. AX
finishes with the relocated game data segment, DX with 03CE, BP unchanged, DS
loaded from the live saved word (which aliases may change), and ES set to A000. The adapters then consume the
live far-return words at SS:SP in order. They use the same byte bus as core
memory operations, preserving stack aliases and the original return target.

`tests/aligned_mask_effects.py` runs 52 bounded cases over both variants. It
checks all 96 body sites and ten conditional branch edges, compares whole RAM,
registers, defined flags, ordered bus events, VGA planes/latches/registers, and
independent plane expectations. Cases include every BP high nibble, DF, both
zero-count loops, incoming DS distinct from game DS, 20-bit source and stack
wrap, live stack aliases of the segment and row-stride words, a VGA-aperture
mask source, SS in A000, and the RETF SP boundary. Four uncomplicated cases
single-step the original RETF after removing the read hooks; device-backed and
SP-boundary cases are recorded as exclusions.

The three compiled mutation checks detect a DF-based BX step, adding the 20
source stride to BX, and adding the 40 source stride to SI. The test report at
`build/aligned-mask-effects-differential.json` records the image digest, both
range hashes and address sets, case inputs/results, branch edges, input hashes,
device contract, RETF probe limits, and the detected mutations. The bus digest
is streamed; event flags and the original instruction's defined-flag mask are
retained per event, including for each 65,536-iteration zero-CL witness.

Dependencies are limited to the reconstructed symbol ledger, the existing
`LmnRasterBus` and `LmnRegs` layouts, and the bounded `MinimapVga` fixture.
This domain assumes constructed memory and quiescent IRQs. It does not establish
other indirect or modified-code incoming states, asynchronous VGA ownership,
or behavior outside the two static bodies and their return adapters.
