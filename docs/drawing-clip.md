# ClipPlanarDrawingRectangle (9967)

`ClipPlanarDrawingRectangle` is the closed clipping leaf at `09967`. The pinned
executable is `assets/vgalemmi.exe` (SHA-256
`5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d`); its
static decompressed image is SHA-256
`b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e`.

The routine is entered by a near call and returns through the return word in
live `SS:SP`. Its logical C core takes `LmnDrawingClipCall` fields and operates on
the caller's RAM image. The register adapter alone marshals `LmnRegs` and reads
the return IP after the core restores the stack. A null raster bus means
canonical 20-bit RAM; a bus routes each byte access and receives the flags live
at that access. The code has no calls, ports, or video-device accesses.

The routine receives `AX=x`, `BX=y`, `CX=packed height`, `DX=width`, `SI` and
`DI` source/destination cursors, and `BP` control. `BP` bit `0004` enables
horizontal clipping and bit `0008` enables vertical clipping. The input `CH` is
first saved to live `DS:A949`, then cleared so `CL` alone supplies the initial
height. Every return reloads `CH` from that DS byte. The final values of all
these registers remain logical output fields; `SP` is the body exit offset
before the adapter consumes the near return.

Horizontal clipping reads `DS:66F2` (`DrawingWidthPixels`) at each compare and
increments the word at `DS:66FC` (`DrawingHorizontalSkipBytes`) once per clipped
8-pixel step. Negative `x` follows the signed `JNS` path: if `x+width` remains
negative it rejects; otherwise it advances `SI` and `DI` by one per byte,
subtracts eight from `DX`, and adds eight to `AX` until `AX` is nonnegative.
Nonnegative `x` uses signed `JNL`/`JL` comparisons against the live width field,
then subtracts eight from `DX` and the working right edge for each clipped
step. These predicates are intentionally not normalized: the sign-only
`JNS`/`JS` paths differ from signed `JNL`/`JL`, and all register arithmetic
wraps at 16 bits.

At `099B4`, the code pops and pushes `BP` through live `SS`. A preceding DS
write can therefore change the control value used by vertical clipping. With
bit `0008` clear, the routine returns after restoring `CH` and `BP`; the zero
size checks are skipped. For a negative `y`, it rejects when `y+height` remains
negative. Otherwise it adds `y` into `CX`, negates `BX`, reads the live source
pitch at `DS:66FA`, multiplies the clipped row count by that pitch, and adds the
low product word to `SI` and `DI`. It stores that low word at `DS:66FE` as the
vertical skip and clears `BX`. The product high word is discarded, while
`MUL` defines only `CF` and `OF`; the temporary `AX` and `DX` saves are pushed
and restored through live `SS` memory.

For nonnegative `y`, `DS:66F0` (`DrawingHeight`) is read separately at each
original memory instruction. The routine rejects when `y` is signed-greater
than or equal to the live height. If the bottom crosses the height, it replaces
`CX` with `height-y`. Only this path reaches the `DX==0` and `CX==0` checks at
`099FE`; fast vertical-disabled and accepted negative-`y` paths can return zero
dimensions. The reject tail sets `AX=FFFF`, reloads `CH`, and restores `BP`.

All word accesses visit their low then high physical byte. Segment-plus-offset
addresses wrap at 20 bits, while the second byte remains physically contiguous
across offset `FFFF`. Stack offsets wrap at 16 bits. DS and SS aliases are kept
live, including the saved `BP`, saved `CH`, source pitch, temporary multiply
frame, skip fields, and the near return word. The adapter leaves `CS`, `DS`, and
`ES` unchanged, reads the return IP through the bus, and advances `SP` by two.
The bounded suite does not define CPU-family stack-limit faults.

The ledger's declared size is 174 bytes, from `[09967,09A15)`, including the
decoded NOP at `09996` and the final RET at `09A14`. The maintained C range
translates 173 native code bytes; normal entry skips `09996`. This is an
execution observation, not a claim that the NOP or any surrounding UNKNOWN run
is dead. Exact static bytes and SHA-256 values are:

| Address range | Bytes | SHA-256 |
| --- | ---: | --- |
| `09967..09995` | 47 | `ba5da91d031ec0310761a0aefebc4e6ab9966e0f4de5208f85ece79c38152346` |
| `09997..09A14` | 126 | `1854fb803616222836f02009b9e850f9004b391158059c0540a6fc7204684107` |
| `09967..09A14` including `09996` | 174 | `17408b36038da920aeb08960f4d9e6f5323402b17907838aa7ef43092d252d30` |

The complete byte stream, including the unexecuted NOP, is:

```text
55 88 2e 49 a9 32 ed f7 c5 04 00 74 40 8b e8 23 ed 79 1d 03 ea 79 03 e9
8b 00 83 c6 01 83 c7 01 83 06 fc 66 01 83 ea 08 05 08 00 78 ed eb 1e 90
3b 06 f2 66 7d 6f 8b e8 03 ea 3b 2e f2 66 7c 0d 83 06 fc 66 01 83 ea 08
83 ed 08 eb ed 5d 55 f7 c5 08 00 74 26 8b eb 23 ed 79 26 03 e9 78 46 03
cb f7 db 8b 2e fa 66 50 52 8b c3 f7 e5 8b e8 5a 58 03 f5 03 fd 89 2e fe
66 33 db 8a 2e 49 a9 5d c3 3b 1e f0 66 7d 1e 8b eb 03 e9 3b 2e f0 66 7c
06 8b 0e f0 66 2b cb 23 d2 74 0a 23 c9 74 06 8a 2e 49 a9 5d c3 b8 ff ff
8a 2e 49 a9 5d c3
```

`tests/drawing_clip.py` executes only this identified routine with constructed
registers and RAM. Its 59 cases compare all registers, the defined final flag
bits, full 1 MiB RAM, and ordered bus byte accesses between Unicorn and C. The
bus comparison uses the flag state captured at the instruction boundary and
masks only bits the last flag-setting instruction defines. Every case also
runs through the null-bus RAM backend. The suite detects three compiled
mutants: unsigned instead of signed horizontal/vertical `JNL`, and a seven
pixel instead of eight-pixel horizontal step.

The run covered 73 instruction addresses and 29 observed branch edges. It did
not execute `09996`. `translated_code_bytes` is 173 for the maintained C range;
the return instructions are handled by the shared near-return adapter. The
suite writes the exact executed-address and branch-edge lists, plus input
hashes, to `build/drawing-clip-differential.json`.

```text
executed_instruction_addresses:
9967 9968 996c 996e 9972 9974 9976 9978 997a 997c 997e 9981 9984 9987
998c 998f 9992 9994 9997 999b 999d 999f 99a1 99a5 99a7 99ac 99af 99b2
99b4 99b5 99b6 99ba 99bc 99be 99c0 99c2 99c4 99c6 99c8 99ca 99ce 99cf
99d0 99d2 99d4 99d6 99d7 99d8 99da 99dc 99e0 99e2 99e6 99e7 99e8 99ec
99ee 99f0 99f2 99f6 99f8 99fc 99fe 9a00 9a02 9a04 9a06 9a0a 9a0b 9a0c
9a0f 9a13 9a14

branch_edges:
9972->9974 9972->99b4 9978->997a 9978->9997 997c->997e 997c->9981
997e->9a0c 9992->9981 9992->9994 9994->99b4 999b->999d 999b->9a0c
99a5->99a7 99a5->99b4 99b2->99a1 99ba->99bc 99ba->99e2 99c0->99c2
99c0->99e8 99c4->99c6 99c4->9a0c 99ec->99ee 99ec->9a0c 99f6->99f8
99f6->99fe 9a00->9a02 9a00->9a0c 9a04->9a06 9a04->9a0c
```

The leaf's only static caller is `PreparePlanarDrawingInputs` at `0884C`. The
caller-preparation slice `[0882D,0885E)` is maintained as a separate native
scope; the broader far renderer remains untranslated. These tests do not
establish VGA behavior, the caller's source-plane contract, or reachability of
other code in the image.
