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


## Connected backdrop and decoration drawing

The same maintained C module and shared campaign now include4EEF..4F89:
DrawMenuBackdropLayers, DrawMenuDecorationRows, DrawMenuDecorationRow and
DrawMenuDecorationBitmap. The physical union adds155 code bytes. The saved
bitmap wrapper is shared by the row parent; no new verifier engine or native
suite is introduced for its small entry.

The backdrop publishes the live UI selector1FEE to graphics selector1FE4. It
makes two actual far8822 calls: (AX,BX,BP)=(0,20,0F42) then(8,10,2), both with
CX045E,DX0278,SI2080,DI7786. No parent saves restore the first child's returned
DS/ES/registers/flags before the second set of original MOVs. Geometry is632x94;
plane size1D02 and the mask-source difference5706 is three plane extents. Four
planes end exactly atUI:9488, the first decoration source.

The six little-endian words at liveCS:4F8A are9488,A2D4,B120,BF6C,CDB8,DC04.
Their0E4C spacing equals four120x61 planes of0393 bytes. The mask cursor is source
plus0AB9, three plane extents. The final four-plane source ends atEA50, within
section3'sF210 bytes. This is a proven layout interpretation; table storage
remains UNKNOWN, and unchecked adjacent table reads retain their original values.
Animation's first source,UI+0800 paragraphs+7210, equalsUI:F210: the physical start
of section4 at the normal wrappedUI+0F21 selector. These coordinates explain the
relationship without assuming allocation bounds, non-aliasing or initialization.

4F2B first CALLs the row withAX0044,BX0078,CX4,DI4F8A. After its actual nearRET,
MOVs supplyAX00C4,BX00C5,CX2 and fall directly through into the row. There is no
second game CALL frame. Each row iteration pushesCX, reads the next source via
CS, advancesDI by2, pushesAX/BX, and draws at(x-8,y+8,BP0F43). The actual POPBX/
POPAX then feed a second draw at(x,y,BP3). POPCX and ADDAX,80 precede LOOP. Live
CS table changes and overwritten saved words cannot be replaced with host lists.
EntryCX0 still executes the body; a bounded provider changes its saved count to1
in that fixture. The complete unmodified65,536-iteration zero-count run is not
claimed as executed evidence.

4F6E pushesAX,BX,BP,SI,DI in that order, setsCX043D/DX0078, derivesDI=SI+0AB9,
and makes its actual far call. POPDI/SI/BP/BX/AX read live words; CX,DX,DS,ES and
flags are left as actually returned. A changed nested nearRET stops at its real
continuation. The separate far-return and renderer-stop statuses remain intact.
Core and adapter tests include ordinary and pinned decoded section3/4 banks;
static decoding stays in memory, creates no asset dump, and does not execute the
upstream loader or boot the game.


The adjacent4E37 caller provides a further static boundary: its two64x31,
four-plane sources atEA50 andEE30 each occupy03E0 bytes, ending exactly atF210.
Together with the background's two-plane320x104 prefix0000..2080, the backdrop
2080..9488 and six decorations9488..EA50, these dimensions partition section3's
full decoded extent. This is source-layout evidence, not execution coverage of
4E37 or closure of every interpretation of those bytes. Its two-page cache
bytes1F70/1F72 and4EA2's1F6E/1F6F remain the next native parent contracts.

Compact observation storage in tests/verification.py retains every event as five
uint32 words, including its kind, address, value, flags and defined-mask value.
Indexing, slicing and comparison still expose the same tuples. It is opt-in;
existing consumers keep list storage. Both paths keep the same hard exhaustion
failure. The drawing fixtures use1,500,000 instructions/750,000 events, with an
explicit20,000,000/5,000,000 allowance for the long distinct-DS shift fixture.
The worker retains384MiB and570 seconds inside a600-second outer envelope,
leaving time for parent-owned DLL cleanup after an inner timeout. The long fixture actually completes
6,724,921 instructions/3,157,223 events; it preserves an original zero-byte
shift count's256 iterations through the relocated game scratch frame.

An artificial SS=A000 bitmap-wrapper fixture exhausted1,500,000 original
instructions at89A3. Its exact input is retained in UNVERIFIED_CASES and a failed
original-only diagnostic in build/menu-vga-stack-frontier.json. It has no completed
native comparison or mutation credit and is excluded from accepted case totals.
VGA-plane stack aliasing remains open; no C shortcut or claimed dead path hides
that failure. The selector-EA wrap frontier atSPFFFE/FFFF also remains open.

The intact relocated same-CS:8822 operand precondition applies to4F0A,4F25 and
4F7F as well as4FEB. Instruction fetches are not invented data-bus reads.

The first expanded campaign hit its420-second outer timeout and earned no report
or mutation credit. Its killed worker tree was reaped and its exact owned DLL
directory removed. The revised campaign avoids replaying identical drawing bodies
at both public boundaries for every data variant: every fixture retains adapter
comparison, while every entry,ordinary core and changed-return stop also gets a
direct core comparison. Instruction sites/outcomes and native mutations stay
mandatory; this reduces redundant execution without accepting incomplete calls.


The accepted expanded local campaign passes112 fixtures/841 comparisons,all118
own sites/15 direct outcomes,1,357 integrated sites/190 outcomes and nine completed
mutants in4,990 known bytes. It executes27,151,440 original instructions and
compares15,214,969 events,including2,144 separately counted far-return observations.
Four new witnesses detect cached wrapper AX,wrong table segment,an omitted second
row and wrong UI selector publication. The failed VGA-stack fixture is outside
those accepted totals. Only155 new unique main-image code bytes are added; the
main translated union is27,911. Full original contracts and fresh affected native
reports remain separate from complete aggregate coverage and full-game acceptance.
