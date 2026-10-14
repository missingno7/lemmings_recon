# AccumulateMinimapSample (7A39)

`AccumulateMinimapSample` is the 33-byte leaf at main-image offsets
`07A39..07A59` (16 instruction sites). Its exact pinned bytes are:

```text
51 26 8A 24 26 8A 44 01 B9 10 00 32 F6 D1 E8 73 02 FE C6
E2 F8 80 FE 08 7F 02 59 C3 2E 08 17 59 C3
```

The routine first pushes the incoming `CX`, then reads `ES:SI` into `AH` and
`ES:(SI+1)&FFFF` into `AL` as two separate byte accesses. It shifts `AX` right
once for each of 16 bits and increments `DH` when the outgoing carry is set.
`DL` remains the caller's mask. `CMP DH,8` selects the write path only when the
population is greater than eight. That path ORs the live byte at `CS:BX` with
`DL`; both paths then pop `CX` from the live `SS` word and execute the live near
return. `AX` is zero on either exit. The result is therefore
`AX=0`, `DX=(population<<8)|incoming_DL`, `CX=word SS:(SP-2)`, and final
`SP=(entry_SP+2)&FFFF` after the adapter consumes `RET`.

The byte reads and stack accesses retain distinct address rules. The second
source byte wraps its 16-bit offset before applying `ES`, while each pushed,
popped, or returned word uses contiguous physical bytes with 20-bit wrap. The
push happens before source reads, so `ES:SI` may alias the saved `CX`. The OR
may alias the saved `CX` or outer return word, changing the values later read
by `POP CX` or `RET`. The C core accepts logical `CS`, `ES`, `SS`, `SP`, `SI`,
`BX`, `DL`, `CX`, and flags; the register adapter handles the live near return.
An optional `LmnRasterBus` carries ordered byte accesses, while a null bus uses
20-bit RAM directly.

On the skip path, `CMP DH,8` defines all arithmetic flags and preserves the
other flag bits. On the write path, the OR defines `CF`, `PF`, `ZF`, `SF`, and
`OF`; `AF` is undefined. The target byte read and write observe the preceding
CMP flags. Later stack reads observe the post-OR flags, with `AF` excluded from
the defined comparison. The test runs with TF clear and no interrupt provider;
IRQ scheduling is outside this leaf contract.

`tests/minimap_sample.py` compares the complete original leaf and both native
RAM paths in 67 bounded cases. It covers every population from 0 through 16,
the exact eight/nine threshold, SI offset wrap, ES and SS physical wrap, stack
offset wrap, source-to-push aliasing, saved-CX byte aliases, and both bytes of
the live return word. Each comparison checks all registers, whole 1 MiB RAM,
defined flags, intact executing bytes, and ordered callback accesses. All 16
sites and six branch edges execute. The native core also checks all 65,536
possible source words against an independent population/flag contract. Three
compiled mutations detect an inclusive threshold, contiguous physical source
continuation at `SI=FFFF`, and stale rather than live `CX` restoration. The
generated report is `build/minimap-sample-differential.json`.

The parent `AccumulateMinimapRow` calls this leaf at `07A2C`; the row and column
now connect native cores directly. See [minimap.md](minimap.md) for their domains.
