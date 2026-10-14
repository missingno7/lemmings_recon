# Packed terrain-piece caller

`DrawPackedTerrainPiece` is the closed caller cluster at `7C67..7CBB` in the
pinned `main` image. Its 85-byte range has SHA-256
`ce45f1424864d5c54fb12b3538c56d62ade4fba0893102c230cbae9f75b12f16`.
The prefix through `7CB4` is 78 bytes and 33 decoded instructions. The remaining
seven bytes are the far call at `7CB5`, the caller's `POP SI` at `7CBA`, and its
near `RET` at `7CBB`. There are 36 instruction sites and four conditional branch
edges across the full range. The only incoming calls found outside the region
are at `3765` and `3975`; there are no incoming edges into its interior. The
far child is `8822` (`DrawPlanarBitmap`), which returns normally to `7CBA`.

The prefix converts the packed input in `AX` and `BX` into a logical drawing
call. `AX` supplies `left = AX & 1FFFh`; `BX` supplies a signed arithmetic
shift by seven followed by subtraction of four for `top`. The low six bits of
`BX` select one of 64 eight-byte ground records, while bit 6 is ignored. The
record begins at the ledger-owned `GroundTerrainRecordWidthByte` field
(`DS:1D0B`, offset zero within `GroundTerrainGraphicsRecords`): byte `+0` is width,
`+1` is height, `+2..+3` is source offset, and `+4..+5` is mask offset.
This caller does not read bytes `+6..+7`; ordinary distinct-stack/source cases
leave them untouched. Live aliases can overwrite record bytes. The child receives packed height
`0400h | record.height`, source in `SI`, mask in `DI`, and width zero-extended
in `DL`.

The control word in `BP` starts as `((AX >> 7) & 00C0h) | 000Fh`. When bit
`40h` is set, the routine also sets `0F00h`; the carry out of `RCL AX,1` adds
`8000h`. `TEST DX,40h` clears carry before that rotate. The routine leaves
`DF`, `IF`, and other unaffected flags live; the prefix's final `XOR DH,DH`
sets `ZF` and `PF`, clears `CF`, `SF` and `OF`, and leaves `AF` undefined.

The three stack saves are observable memory, not cached temporaries. The code
pushes incoming `SI`, then computed `BX`/top, then computed `AX`/left. It reads
the record fields through live `DS`, then pops the saved coordinates from live
`SS:SP`; stack and data segments may alias the record. Segment arithmetic wraps
the offset at 16 bits and physical addresses at 20 bits. The wrap fixtures use
the established permissive real-mode model; CPU-family segment-limit faults
remain outside their claim. The native API keeps
these aliases on one RAM image and emits reads and writes in instruction order.

`lmn_prepare_terrain_piece_core` stops immediately before the far call and
returns the prepared `LmnPlanarBitmapCall`; the saved `SI` is still on the live
stack. Its register adapter exposes the same boundary at `IP=7CB5`. The full
`lmn_draw_terrain_piece_core` pushes the live far-call frame and invokes the
existing planar-bitmap core on the same RAM. When that child body returns, it
consumes the actual live return `IP` then `CS`. A changed target is exposed at
that point before execution continues there. On the normal `7CBA` return, it
performs the live `POP SI` and stops before `7CBB`; the full register adapter
also consumes the near `RET` to its caller. Drawing continuations and a child
that did not return remain explicit in the result. Passing no raster ports
preserves the planar core's `969C` pointer-check seam; complete ports are
required to execute the aligned read-mask body.

The prefix suite compares all registers, RAM, defined flags, and ordered stack
and record accesses against the original routine in bounded constructed-state
runs. Its 265 cases include every record selector with bit 6 both ways, the
ten-by-seven packed-boundary matrix, eight initial flag patterns across six
control inputs, segment and stack wrapping, live record/stack aliases, and
adapter probes. It covers all 33 prefix instruction sites and all four branch
edges. Three compiled mutations are detected: using selector bit 6, using a
logical instead of signed shift for vertical input, and omitting `0F00h` when
control bit `40h` is set. The full caller suite reports 609 cases, covering all
36 caller instruction sites and 1,366 integrated sites across 198 branch edges,
plus six direct-core boundary/status probes. It supplies all 320 ground-record
metadata entries and checks complete constructed source bytes and whole-plane
footprints. The cases include 606 normal outer returns, two changed child-near
returns (`8801h` and `015Eh`), one changed child-far `CS=0210h`, and a live
saved-`SI=1000h` alias; all five compiled full-path mutations are detected.

For the original routine's `RETF`, the oracle records the actual stack words
through the read hook, removes the hook only while executing that unchanged
`RETF` opcode, then reinstalls hooks before resuming the caller's `POP SI` and
`RET`. This preserves the actual live return frame while still checking its
ordered bus reads. These are bounded differential checks; they do not boot the
game or establish producer allocation, IRQ/device ownership, or unresolved
behavior outside this cluster.

## Next terrain-command producers

Fresh CFG review gives two identical instruction patterns at3752..3769 and
3962..3979, each24 decoded bytes/nine sites. The only discovered outside incoming
edge is fallthrough from the preceding MOV SI at374F/395F. The loop reads four
big-endian command bytes, advances liveSI by4, checks AX=FFFF, then calls7C67
and jumps back. The normal near-return sites are3768/3978; sentinel exits are
376A/397A. UNKNOWN374E/395E remain outside these spans and unresolved.

- `3752..3769` SHA-256: `757e10fa7e829dc6739ca029131ed2a8c30a4246847fce1beacd2d5ab3558d56`.
- `3962..3979` SHA-256: `9198d8a01e480812d225b54a6957a689b6e505a6e5c18025eb272ce143b65e14`.

Static decoding of all80 pinned LEVEL sections finds a FFFF sentinel within
each400-slot terrain area:0..399 preceding commands, with four empty streams.
This is evidence about the supplied files, not permission to add a400-command
limit or validate arbitrary input. Live DS/SS, iterator/return aliases, malformed
streams, the preceding setup instructions and wider36B6/394F contracts still
need independent closure. No original terrain loop was executed for this review.
