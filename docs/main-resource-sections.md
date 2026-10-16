# Main resource section loader

`LoadMainResourceSections` occupies `58D2..59BA` (233 decoded bytes, 101
instruction sites). This is a static caller contract and composition plan; it
does not claim that this parent is translated or behaviorally accepted. The
known body has one conditional branch, `CMP byte [DS:200E],FFh` at `5976`
followed by `JNZ` at `597B` to the outer `RET` at `59BA`. Startup calls the
routine at `00D5`; the normal return address is `00D8`.

## Calls and normal continuations

The normal call frames and the first instruction after each `RET` are:

| CALL site | Target and role | Normal continuation | Prepared input or next step |
|---|---|---|---|
| `58E0` | `LoadDatResource`, section 0 | `58E3` | `DS:DX` names `main.dat` (`DX=252B`); `ES=[DS:1FE4]`; `SI=DI=0`; `CX=ES`. |
| `58E5` | `GenerateEntitySpriteBanks` | `58E8` | Transforms the section-0 source using live resource and sprite-buffer selectors. |
| `58E8` | `GenerateFixedWordMaskBanks` | `58EB` | Writes the fixed word patterns; the second pass falls through the shared word-shift body. |
| `58F9` | `DecodeDatPreservingSegment`, section 1 | `58FC` | `DS=ES=[DS:1FE4]`; `SI=DI=0`. |
| `58FE` | `GenerateGraphicsMaskBanks` | `5901` | Consumes the just-decoded source and writes the generated-graphics bank. |
| `590F` | `DecodeDatPreservingSegment`, section 2 | `5912` | `DS=ES=[DS:1FE4]`; `SI=DI=0`. |
| `5927` | `CopyResourcePlanesToVga` | `592A` | `DS=[DS:1FE4]`, `SI=0`, `DI=F91F`, `CX=28h`, `AX=2Ch`, `BX=0428h`. |
| `594D` | `DecodeDatPreservingSegment`, section 3 | `5950` | `DS=ES=[DS:1FEE]`; `SI=DI=0`. |
| `5960` | `DecodeDatPreservingSegment`, section 4 | `5963` | `AX=[DS:1FEE]+0F21h` with 16-bit wrap; `DS=ES=AX`; `SI=DI=0`. |
| `5972` | `DecodeDatPreservingSegment`, section 5 | `5975` | `DS=ES=0842h`; `SI=DI=0`. |
| `598A` | `DecodeDatPreservingSegment`, section 6 (conditional) | `598D` | Only on the `200E==FFh` path; `DS=ES=[DS:1FE4]`; `SI=DI=0`. |
| `59A1` | `CopyResourcePlanesToVga` (conditional) | `59A4` | Same literal plane-copy inputs as `5927`. |

There is no explicit section-index operand at the later decoder calls. They
continue the open `main.dat` handle in order: the initial loader decodes section
0, and the direct decoder calls consume subsequent sections. Thus `58F9` and
`590F` are sections 1 and 2; `594D`, `5960`, and `5972` are sections 3, 4,
and 5; section 6 is reached only at `598A`. The known file has seven sections.
The section numbers describe this sequence, not a new index argument to the
decoder.

Static extraction of all seven pinned sections gives these decoded extents.
Extraction is performed in memory and does not create asset dumps.

| Section | Decoded bytes | SHA-256 |
|---:|---:|---|
| 0 | `5270h` | `959341d6dd9e51cfa9877f510909b417c1b4266e3a051742cddc7cf85cd7ad44` |
| 1 | `0184h` | `91071cc7578e3ce8f5f6e692537c230dadde7f564ce7e8d8a14f2f789ee4ab27` |
| 2 | `20C0h` | `7e1b6a0a63f88c37bb9bb6b40d2d4889862ece61aceffc2b6c19961436b9cadd` |
| 3 | `F210h` | `05fa1758775e601d38b00c6120cc597ffae6c598b04caac921bb59d76a80c805` |
| 4 | `8CF0h` | `6880c756be51fd97314e8f2c615baef9218134c58e66eff25a6e3dbab6f0a5f7` |
| 5 | `02F6h` | `bdc1da6ea085bd247ab3060dfc78f522f7b447dcffe7235a3e19bf9938731287` |
| 6 | `2020h` | `0fea37bb7811ab6968bf26fcb22a6b2f5cafd60690386435a69aa35bf05bc6b9` |

Section 1 exactly fills the `0000..0183` source span already established for
`GenerateGraphicsMaskBanks`. Section 3's F210h bytes equal the literal 0F21h
paragraph step before section 4; their normal destinations are contiguous in
physical memory. This arithmetic does not establish their consumer semantics
or make wrapped selectors, overlaps or allocation lifetime safe by assumption.

Section 0 is the 5270h-byte decoded source used by the sprite-bank transform.
Section 1 feeds the mask-bank producer at `58FE`. For section 2, the VGA copy
uses 40 rows, 40 bytes per row, and pitch 44; the following `REP MOVSW` copies
3E0h words (7C0h bytes) from `[1FE4]:1900h` to `[1FEC]:0000h`. The pinned
section-2 output is 20C0h bytes: a 1900h-byte plane prefix followed by that
7C0h-byte copy. Section 3 is decoded at `[1FEE]:0000`; section 4 at the
wrapped selector `[1FEE]+0F21h`, offset zero. Section 5 is decoded at
`0842:0000`; it is independently identified as the 758-byte PC-speaker
payload. The known section-6 output is 2020h bytes: the same 1900h-byte plane
prefix plus 720h bytes. On the nominal DF-clear path, its conditional copy
writes from `[1FE4]:1900h` to `[1FEC]:00A0h`, leaving the earlier first A0h
bytes in the glyph segment in place.

The two VGA calls target four planes at `A000h`, beginning at offset `F91Fh`.
Their row arithmetic and final source/cursor behavior remain those of the
57D1 leaf. The string copies are `REP MOVSW` at `593C` and `REP MOVSB` at
`59B7`; both follow incoming DF. No CLD is performed.

## Segment selectors and normal allocation coordinates

The selector words are read from live memory, in the order shown in the ASM.
The startup allocation path requests 5571h paragraphs. Its normal arithmetic
publishes these segment coordinates relative to the returned base:

| Data word | Selector | Normal segment delta from allocation base |
|---|---|---:|
| `DS:1FE4` | `GraphicsResourceSegment` | `+0000h` paragraphs |
| `DS:1FE6` | `EntitySpriteBufferSegment` | `+1000h` paragraphs |
| `DS:1FE8` | `GeneratedGraphicsBufferSegment` | `+2D0Ch` paragraphs |
| `DS:1FEA` | `GeneratedWordPatternBufferSegment` | `+2E72h` paragraphs |
| `DS:1FEC` | `StatusGlyphBufferSegment` | `+2F02h` paragraphs |
| `DS:1FEE` | `UiGraphicsBufferSegment` | `+2F7Eh` paragraphs |

These are selector values in paragraph units, with the original 16-bit
arithmetic. They are normal-path coordinates, not proven allocation bounds,
non-aliasing guarantees, or initialized extents. In particular, the section-4
`ADD AX,0F21h` wraps as a word before AX is copied to DS and ES. Later code
must reread the selectors at their original sites instead of retaining a
host-side snapshot.

## Live stack and register ownership

`PUSH DS` at `58D2` precedes the first selector read. On a normal first load,
the live `POP DS` at `58E3` restores from that stack word. Further DS saves
and normal restores are `58EC/58FC`, `5902/5912`, `5914/592A`, `592B/593E`,
`5940/5950`, `5951/5963`, `5966/5975`, `597D/598D`, `598E/59A4`, and
`59A5/59B9`. Each restore reads the current SS word. Child writes, selector
aliases, and device callbacks can therefore affect the restored DS.

BX is saved/restored through live words at `58E4/58EB`, `58FD/5901`, and
`5913/593F`. The adjacent `PUSH BX`/`POP BX` at `5964/5965` is a value
no-op on an ordinary stack but still performs real SS writes and reads; keep
it in any exact composition. The BX values flowing between decoder calls
remain the file handle unless an instruction or a live restored word changes
them. Do not hold a cached handle across these saves.

All 12 child CALLs use real near-return words. On normal child completion, the
parent must read and consume the current word at SS:SP, verify the expected
continuation in the table above, and only then execute the next POP, selector
read, or copy. A changed target is an explicit stop with the actual child
state; it does not authorize the parent to resume at its expected label.
Normal parent completion stops before `RET 59BA`; its adapter consumes the
outer caller's live return word only for that ready state. Segmented word
accesses retain 16-bit cursor updates and 20-bit physical addressing, with the
word high byte at physical address plus one.

## Existing core boundaries for composition

The available C interfaces provide these child boundaries; the parent should
use their logical cores to retain stop/fatal information, then compose actual
SS return words in canonical memory:

| Child core | Completion and stop contract |
|---|---|
| `lmn_dat_load_core` | `fatal=0` is a normal return; `fatal=1` transfers to original `1949`; `fatal=2` transfers to decoder-fatal `04D0`. It accepts the declared DOS/file and `LmnDatIo` services. |
| `lmn_dat_decode_preserving_segment_core` | `fatal=0` is a normal return; `fatal=2` transfers to `04D0`. It uses the same live segment bindings and read service. |
| `lmn_generate_entity_sprite_banks_core` | `LMN_ENTITY_SPRITE_BANKS_READY=0`; status 1 is `CHILD_STOP`; status 2 is `CHANGED_CHILD_RETURN`. Preserve its returned roles, child entry/status, and continuation on either stop. |
| `lmn_generate_fixed_word_mask_banks_core` | `LMN_FIXED_WORD_BANKS_READY=0`; status 1 is `CHANGED_CHILD_RETURN` from the shared word-mask child. It stops before the outer `RET 5D17`. |
| `lmn_generate_graphics_mask_banks_core` | `ready_to_return=1` is normal; zero carries a changed child continuation and must stop the parent. |
| `lmn_copy_resource_planes_vga_core` | `LMN_COPY_RESOURCE_PLANES_VGA_READY=0` is ready immediately before the leaf RET; the parent still checks and consumes the actual word at its own call frame. |

`LoadDatResource` retains the `4B1C` retry-screen callback in
`LmnDatFileServices.retry_ui`. It is an explicit untranslated service seam,
not a completed renderer/input implementation; repeated failure can retry
indefinitely. A loader parent must stop and preserve the exact child result on
fatal `1949` or `04D0`, rather than unwinding or running its own POPs. Direct
decoder calls have the `04D0` fatal path as well. The loader core also needs
the original `LmnDatLoadSegments` values used by its adapter, plus file/read
services; graphics children share the raster bus. The adapter reads the four
segment operands at `CheckDatFile+33h`, `SelectCachedDatFile+50h`,
`ReadDatBytes+8`, and `DatReadFailure+1` from code. These platform and fatal
boundaries remain part of the parent contract.

## Remaining uncertainties

The meaning of the live byte `DS:200E` is not established here. The routine
tests whether it equals FFh after decoding section 5; the equal case loads
section 6 and performs the additional plane/glyph copies. Do not assign the
byte a sound or other semantic name without independent evidence. Later
ownership of section 1, the purposes and consumers of sections 3 and
4, arbitrary provider changes to segment selectors, and the usable allocation
bounds remain unresolved. The call sequence and documented section-2, section-5,
and section-6 identities do not classify any unresolved bytes as dead or prove
whole-loader readiness.
