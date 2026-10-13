# Special-resource VGA strips

The original entries `8238`, `8243`, `8249`, `824F` now share the native
`lmn_blit_special_strip_core` in `c/special_blit.c`. The ledger names them
`BlitSpecialResourceStrip0..3`. Their union is 264 original code bytes and
122 instruction sites, including the shared `8252..8342` tail. The skipped bytes
at `8242`, `8248`, `824E` remain UNKNOWN and are excluded from C accounting.
The higher `1A7B` resource/setup caller is still untranslated.

## Memory and geometry

Entry zero publishes DS:`LevelGraphicsSegment` (`1FF0`) to
`GraphicsResourceSegment` (`1FE4`) and selects vertical offset zero. The other
entries select offsets 40, 80, 120. All four build 2,400 words at heap:`B840`
by ORing the three 4,800-byte banks at `8000`, `92C0`, `A580`.
The working heap is the live segment stored in DS:`1FF0`.

For incoming DF clear, the four passes write a 40-row by 120-byte rectangle,
starting at VGA offset `4A68 + 208*vertical_offset`, with 208 bytes per row.
The first three planes receive the three input banks; the fourth receives their
OR mask. This is the original memory layout, not an inferred screen viewport.
The CPU reads each destination byte before MOVSB, preserving the VGA latch read
and returned AL. The remaining 88 bytes per row are untouched.

DF is preserved. It changes STOSW/MOVSB direction while the mask source still
advances by two and each row still adds 88 to DI. Backward mask writes can alter
future input; source and output are never staged in temporary game-state copies.
After PUSH DS, the routine re-reads DS:`1FF0` to switch DS. A saved-DS alias can
therefore redirect the passes after mask construction has used a different heap.
Original word accesses use contiguous physical bytes, including at offset FFFF.

## Device boundary

`LmnRasterBus` exposes physical byte reads/writes and word port outputs. The
callbacks preserve the caller's registers. Device planes and latches belong to
the backend; ordinary RAM remains in the single canonical memory image. The
native VGA backend and IRQ scheduler have not been implemented.

The bounded fixture follows VGA read mode zero, which loads four latches and
returns the selected read-map plane, and write mode zero with rotation zero,
replace operation and bit mask FF. Set/reset enable and the sequencer map mask
determine which planes receive CPU data or fixed bits. This narrow device contract
is based on [FreeVGA memory operations](https://web.stanford.edu/class/cs140/projects/pintos/specs/freevga/vga/vgamem.htm).
Unsupported modes are rejected by the fixture.

The original port sequence is preserved: sequencer map mask F, set/reset zero,
enable set/reset E, graphics mode zero, data rotate zero, bit mask FF. The first
pass writes plane zero and clears the other planes. Then enable set/reset becomes
zero and map masks 2, 4, 8 select the remaining passes. Every word is written to
its original SS mirror before OUT. The ledger names SS offsets `0`, `2`, `8`,
`A`, `C`, `E`; ASM runtime equates allocate no image bytes and imply no initial
contents. These are original hardware mirrors in live RAM, not new C shadow state.

Each row disables interrupts during byte transfer and enables them afterwards,
regardless of incoming IF. The boundary exposes those flag states. Tests compare
defined arithmetic flags at port outputs and transfers, excluding AF only after
the original XOR that leaves it undefined. All defined exit flags are compared.
Actual asynchronous interrupt delivery is outside this verification domain.

## Bounded verification

`tests/special_blit.py` compares the native core/near-call adapter with the original
instructions in 28 cases, executing all 122 sites and 22 branch edges. It checks
the entire 1 MiB RAM/aperture cache, registers, defined flags, four device planes,
latches, indexed registers and complete port/MMIO traces. The aperture cache is
only the CPU's flat access window; device planes are authoritative video memory.

Cases cover all entries with both DF values, varied VGA read-map selection,
three stack wrap/mirror aliases and the saved-DS/heap-pointer alias. With SP=0010,
the bit-mask mirror overwrites saved DS; POP DS returns FF08. This original effect
is retained. Sixteen cases use statically decoded, pinned VGASPEC0..3 streams,
each containing 14,400 output bytes. Only hashes and stream spans enter reports.
Forward cases also compare with an independent expected-plane calculation,
including every byte outside the rectangle. Device fixture vectors separately
check read-map/latches, set/reset and map masks.

Three compiled mutants are detected: omitted third-bank OR, incorrect row gap,
and incorrect last-plane map mask. C compiles as C11 with warnings treated as
errors. Reports record input hashes so stale results cannot inflate coverage.

The domain uses ordinary RAM for source and stack, intact instructions and active
return words, and a quiescent unchained 64 KiB A000 aperture. Sources/stack mapped
through video memory, asynchronous interrupts and the higher setup caller are
not claimed verified. Real special-resource bytes do not establish full gameplay
coverage. No original game was booted for this investigation.
