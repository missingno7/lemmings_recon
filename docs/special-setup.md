# Connected special graphics setup

`SetupSpecialGraphicsResource` at `1A7B..1B41` now has a C11 core and bounded
near-call adapter in `c/special_setup.c`. All 199 caller bytes are instructions;
the caller has 87 instruction sites and no conditional jumps. It directly calls
the native RLE, four-strip, file/cache/read and DAT decoder cores. No game-callee
hook replaces any of these translated dependencies.

The original callers at `3749` and `3959` select this path when DS:`0FE8` is
nonzero. Their surrounding level setup remains untranslated. The earlier `1A5A`
path selects VGASPEC and loads its first DAT section at input-segment offset 10.
That load is a caller precondition here, not a translated upstream startup path.
The four paired asset cases construct valid caller inputs; they do not prove
which level selects which pair of resources.

## Original transformations

The live input segment is DS:`GraphicsResourceInputSegment` (`1FF4`), and the
working heap is DS:`LevelGraphicsSegment` (`1FF0`). The ledger owns the metadata
and filename offsets. Names describe observed copy destinations, without claiming
complete palette or resource record ownership.

For DF clear, the first 40 input bytes, starting at offset 10, are used as follows:

| Source bytes | Main data destination | Original modification |
|---|---|---|
| 00..17 | 1F23..1F3A | First three bytes become 1F, 1F, 00 |
| 00..17 | 1F53..1F6A | Duplicate copy |
| 18..1F | 1F1B..1F22 | Eight-byte copy |
| 20..27 | 1F0B..1F12 | First byte becomes 06 |

The ASM computes two destinations by adding 18 to the LEA base 1F3B and 08
to the LEA base 1F13. Both additions' original flags are retained. Incoming DF
is not cleared during the prefix copies or RLE/strip calls: backwards traversal
and live overlapping writes remain possible. The native code uses the single
canonical RAM image and reads saved values from the original stack words.

RLE begins at input offset 38, immediately after the 40-byte prefix. Each of the
four calls decodes into working-heap offset 8000, restores DS, saves the advancing
RLE source cursor, draws the corresponding strip and restores that cursor from
live SS. This restore matters because the strip routine replaces SI. Every pass
re-reads both segment slots after pushing saved DS; no heap pointer is cached
across passes. Near-call continuation words and stack residue are preserved.
See [resource RLE](resource-rle.md) and [special strips](special-blit.md) for those
callees' flags, device contract, DF behavior and bugs.

After drawing, the routine loads the first normal VGAGR DAT section into the same
working heap at offset 10, then decodes the next section in place at offset zero.
`GraphicsDatFilename` (`2534`) is the live filename prepared upstream. The test
fixtures set its selector consistently with the resource supplied by their DOS
provider. Drawing results remain in device planes while the RAM heap is reused.
The existing cache/file/decoder contracts apply, including unchecked lengths,
ignored open carry, retry state and fatal frames; see [DAT resource load](dat-load.md).

Both caller DS restores are live. A read provider may overwrite the outer saved
DS word so that the second decode consults a different data frame. Native calls
retain this behavior. After the second decode, AH becomes 3E while AL retains its
previous value. DOS close returns explicit AX/flags under a preserving service
contract. The caller returns immediately, exposing close carry even on failure;
it performs no close-error transfer or cleanup.

## Verification and remaining scope

`tests/special_setup.py` has 20 integrated original-versus-C cases. They execute all
87 caller sites and 621 sites across the connected dependencies. Cases cover
direct/cache-hit/cache-miss paths, incoming DF set with constructed terminated
streams, a wrapped stack word at FFFF, input/working-heap alias, read-provider
saved-DS corruption, retry, ignored open/close carry and a close-provider DF effect.
Four fatal cases cover header and payload errors in each of the two DAT sections.
The original 1949 and 04D0 continuations are explicit exits with their frames intact.

Four cases use all four strips from each pinned VGASPEC0..3 first section and
the first two sections of paired VGAGR0..3. They are statically extracted inputs,
checked against bounded original execution, not a booted game or runtime dump.
Reports contain hashes, source filenames and fixture parameters, never asset bytes.

Comparisons check all RAM, registers, defined exit flags, VGA planes/latches/
registers, complete port/MMIO traces, file service arguments and retry-callee
snapshots. Forward cases additionally check metadata and all four rendered strips
against independent expected values, including untouched video memory. Existing
leaf suites establish the dependencies' larger branch domains. Integrated sites
and bytes are unioned with those suites for coverage; they are not counted twice.
Three compiled mutants are detected: wrong metadata replacement, omitted saved-SI
restore and an invented close-error transfer.

The domain has ordinary RAM for input/working heap/stack, intact instructions and
active return words, narrow DOS providers and the quiescent VGA fixture described
in special-blit.md. DF-set real resources, video-mapped source/stack, IRQ races,
actual DOS behavior, retry rendering/input and fatal cleanup are not claimed
verified. Upstream selection/allocation, full level setup, native VGA ownership
and SDL3 remain open. Full-game completion has not been reached.
