# Menu animation records and native renderer connection

`InitializeMenuAnimations` at `4FF8..5016` is 31 bytes/12 instruction sites.
`AdvanceMenuAnimations` at `4F96..4FF7` is 98 bytes/42 sites. The two original
callers in the enclosing menu remain at `4431` and `4461`. Their scoped C cores
and actual-RET adapters live in `c/menu_animation.c`; they do not implement
the surrounding `43F2` menu or its scheduling.

## State and initialization

The original instructions establish ten 11-byte records at live `DS:4960`:

| Offset | Proven use |
|---|---|
| `+0` | Current countdown; exact `8000` disables the tick path. |
| `+2` | Reset value and initializer's exact `8000` disable test. |
| `+4` | Renderer AX, horizontal coordinate. |
| `+6` | Renderer BX, vertical coordinate. |
| `+8` | Base source offset for animation frames. |
| `+10` | Untouched byte; meaning unresolved. |

Initial records in the pinned image have these words. The source classification
remains UNKNOWN; recognizing consumers does not explain the final record bytes
or neighboring data automatically.

| Record | Countdown | Reset | X | Y | Source |
|---|---:|---:|---:|---:|---:|
| 0 | `0028` | `0190` | `0020` | `0031` | `7210` |
| 1 | `0050` | `01B8` | `0100` | `002F` | `7810` |
| 2 | `0078` | `01E0` | `01F0` | `0028` | `7E10` |
| 3 | `00A0` | `0208` | `006A` | `0084` | `8410` |
| 4 | `00C8` | `0230` | `00EB` | `0084` | `9010` |
| 5 | `8000` | `8000` | `016B` | `0084` | `9610` |
| 6 | `8000` | `8000` | `01EF` | `0082` | `9610` |
| 7 | `8000` | `8000` | `00AF` | `00CF` | `9610` |
| 8 | `8000` | `8000` | `012A` | `00D1` | `8410` |
| 9 | `8000` | `8000` | `002A` | `0009` | `9610` |

The initializer starts BX at 40 and advances it by 40 for every record,
including disabled records. A reset equal to `8000` writes that sentinel to
`+0`; every other reset writes the current BX. It changes no other field.
SI advances by 11, CX reaches zero, and the final SI ADD supplies the flags.
Word reads/writes retain physical high-byte ordering and 20-bit wrap. The outer
near RET is live, including when a record write aliases its frame.

## Tick and drawing contract

The tick publishes `[DS:1FEE]+0800` modulo 16 bits to `[DS:1FE4]`. The UI selector
is assigned at `1031` in the `1007` allocation path. The normal allocation-relative
coordinate is documented in `main-resource-sections.md`; it is not a proof of
allocation bounds. Main resource section 3 is decoded at `594D` to the UI bank,
and section 4 at `5960` to its wrapped `+0F21` selector. This campaign constructs
source/mask bytes rather than claiming that the upstream loader/bank connection
has already been verified for these menu consumers.

For each record, the original pushes CX, reads `+0`, and skips exact `8000`.
Otherwise it decrements and writes the counter before comparing with `FFEF`.
Equality reads the live `+2` reset, writes it, and skips drawing. All other
negative results render; zero and positive results do not. Thus the normal
sequence draws at `FFFF..FFF0` and resets on the following tick. The disable
test occurs before decrement: entry `8001` decrements to `8000` and still draws.
Reset words, source arithmetic and negative values are not clamped.

The frame offset follows literal NEG, DEC, SHR, byte exchange, SHR/ADD and
SHR/ADD operations. In the ordinary `-1..-16` domain this selects eight frames
twice each at a `00C0` stride. The mask cursor is source plus `0090`, wrapping.
The actual bitmap call has CX=`040C`, DX=`0020`, BP=`0001`, and the record's
coordinates. BP=1 bypasses the renderer's clipping call; negative or outside
viewport coordinates retain the original wrapped accesses. This is not a
new clipped animation policy.

The far CALL at `4FEB` uses its intact relocated same-CS `8822` operand. Its CS/IP
words, the saved SI and the saved loop CX occupy actual canonical SS memory.
Returned DS/ES/SS/registers/flags feed the rest of the parent. A changed inner
renderer return stops at its actual continuation; a changed outer renderer RETF
stops after consuming its actual IP and CS. Only READY reaches the parent near
RET. POP SI and POP CX reread live words, and LOOP decrements the popped CX
without changing flags. No record or palette copy shadows canonical game state.

## Verification and remaining obligations

`tests/menu_animation.py` uses `tests/verification.py` for original instruction
execution, canonical bus events, guarded native callbacks and comparison. It
reuses existing renderer instruction maps, not another execution engine.
`tools/difftest.py menu_animation` retains a 300-second, 384 MiB process-tree
commit limit, 200,000 instructions and 100,000 ordered events per call. Compile
and DLL directories are owned build temporaries and reaped on failure.

The campaign passes 70 fixtures/791 comparisons: 67 single fixtures at both
boundaries plus three same-RAM initialization/218-tick handoffs. They cover all
54 own sites/13 direct outcomes and execute 649 integrated sites/98 outcomes in
4,835 known bytes. Independent checks cover counters, untouched fields, literal
bitmap requests, selector wrap and final reset counters. After 218 ticks the
five enabled pinned records contain 239, 319, 399, 479 and 559; all five disabled
records remain `8000`. The caller frame between bounded calls is constructed;
this is not asynchronous timer delivery or execution of the whole menu.

Other fixtures cover all normal frame pairs, extreme counter/source/coordinate
values, distinct DS, VGA and A20 data, stack wrap, dirty-map calls, changed live
SI/CX saves, changed near/far returns, DF and three relocation loads. Five
completed mutants detect a lost initializer sentinel, early reset, wrong mask
cursor, cached saved CX and hidden changed RETF. Exhaustion is failure and cannot
earn mutation credit. Peak size is 16,390 instructions/13,216 events; the complete
campaign executes 1,199,956 original instructions and compares 953,800 ordered
events, including 1,336 separately counted declared far-return observations.

The shared RETF reference still rejects selector-EA wrap at SP=`FFFE/FFFF`
pending independent evidence. Byte `+10`, upstream allocation/graphics extents,
broader menu initialization, native scheduling and SDL3 services remain open.
Only the 129 unique code bytes enter the C ledger; this is a connected local
checkpoint, not aggregate coverage or whole-game acceptance.
