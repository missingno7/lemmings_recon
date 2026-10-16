# Entity display leaves

These contracts belong to the3634 drawing frontier. They do not establish its
whole record loop,706F sprite dispatch, IRQ scheduling or
unchecked allocation extents. All state remains in canonical segmented memory.

## Minimap pixel6FE2

The141-byte6FE2..706E leaf takes a live record in DS:DI. Its signed comparison
rejects Y>=B0; the subsequent wrapped Y-20 sign test is separate. In particular,
Y=8000..801F wraps into a nonnegative row and can draw. The low product of
`((Y-20)&FFFF)>>3` and2C supplies SI; DX retains the product's high word until
the later port setup. X is read afterward, shifted right4 and PUSHed, then
shifted right3 again and added to SI. Live DrawingOrigin and2172+2+2C follow.

Five ordered SS mirror/OUT pairs set map mask0F, set/reset02, enable-set/reset0F,
mode0 and rotate0. The actual saved X word is then POPped: its low3 bits select
the live DS PixelBitMasks byte. The bit-mask mirror/OUT follows that read.
CLI surrounds the real ES=A000 pixel read and AH write; STI finishes drawing.
Early exits preserve entry IF and ES. All paths retain DF, actual stack aliases
and the caller's near-RET word. The incoming general roles and all residual
registers are part of the interface, including returned AL from the pixel read.

## Shared visibility producer410F

The64-byte410F..414E body is called directly and also entered through shared
JMP/fallthrough paths. It adds no frame at its entry. PUSH DS/POP ES reads an
actual stack word; providers or device-backed saves can make ES differ from DS.
It clears68h words at ES:0EA8 in original DF order, then rereads
LevelViewOriginPixels through DS. Three logical shifts, two DEC operations and
ADD0EA8 select the start of29h byte stores of01, again following DF. The named
ViewVisibilityMapBase has no implied allocation extent or matrix shape.

After CLI, AX saves the actual ES. MOV CX loads the relocated143E immediate at
4137 and sets ES from it; that operand is an explicit C input independent of
live CS/SS. DS:0026 selects the first FF marker. Only after that write does
DS:0028 select the second marker. Thus the first write may change the second
offset through an alias. ES is restored from AX, STI forces IF, and RET414E
consumes the preexisting caller word only in the adapter.

The original test uses exact loaded images at loads0/1010/2345. Its scoped code
view applies only the pinned relocation records; no instruction bytes are masked.
The static image hash remains the report identity. A logical RET0000 created by
a clear/stack alias is observed at nonzero CS before executing its target.

## Dirty-row consumer5726

The171-byte5726..57D0 leaf reads record words+0 and+4, wraps their sum and adds
160h once if its sign is set. The logical quotient by8 indexes the live byte
at DS:0EA8; only an exact1 enables output. It then subtracts live view origin,
clamps a negative wrapped result to zero, shifts3 and reads DS:0026 twice.
The first read contributes the output start; the second supplies BP=word+321h.
These are SS offsets. AlternateDrawingDirtyCellMapOffset names the separate0028
producer/swap word without converting either offset into a DS pointer.

Record+6, Y+2 and the nonzero byte+20 supply the original wrapped vertical
arithmetic. The negative adjustment loop adds8 until AX is nonnegative; the
8000 boundary takes4096 iterations. Mask0002 at record+8 selects CH5 instead
of3. CL rounding uses its byte, with no normalized height or row count.

The first row and first inner store are unconditional. Each row PUSHes CX/SI,
writes through SS with literal INC SI and DEC CH, then POPs both actual words.
A restored CH0 therefore means256 stores. After restoring SI it adds28h and
checks unsigned SI>=BP; only otherwise does DEC CL determine continuation.
CL0 can wrap and SS output can overwrite saved words or the outer RET. No
matrix clamp, cached saved state or shadow dirty map is equivalent. DS/ES/SS,
DF/IF and all residual roles remain live. The dirty-row gate covers ordinary
RAM and declared providers. VGA-backed SS remains a separate bus domain;
the producer data handoff supplies additional ordinary-RAM evidence.

## Point-cloud ownership and leaf6E83

The248-byte6E83..6F7A leaf selects a live DS word stream at EntityPointFrames
(2788) plus160 times the wrapped byte `(record[28]-1)`. EntityPointCount at004D
is initialized to50h at042C and read once into CL with CH zero. The first point
is unconditional; zero count means65,536 iterations. Each word's signed low
byte adds to horizontal BP and its signed high byte to vertical DX. Low80h
skips only that word. The3634 caller's signed selector gate admits1..127;
direct entry retains all byte values without a clamp.

Four ordered mirror/OUT pairs set map mask0F, enable-set/reset0F, mode0 and
rotate0 before reading record X/Y and the count. Initial BP is wrapped
`recordX-viewX+10h`; initial DX is `recordY-10h`. The sign tests after each
delta ADD are distinct from the later signed comparisons against150h/A0h.
An accepted point writes a dirty byte through SS before restoring the inner
SI/BP/DX saves. Those actual restored coordinates then form the VGA offset
with the full DX:AX product, live DrawingOrigin and DrawingPageByteOffset.
The live PixelBitMasks byte selects a pixel; EntityPointColors at2778 plus
`CX&0F` selects its color. SS mirrors, OUTs and the saved mask precede CLI,
the actual VGA latch read/write and STI. Outer BX/DX/BP saves and the actual
RET remain live. Rejected/skipped points preserve IF; an accepted point sets it.

With the09A9 data frame, the color base is stored image0C208 and the point base
is0C218. The16-byte color access window is proven, but neither it nor the
point stream establishes exclusive static ownership or total frame extent.
Both remain within UNKNOWN bytes. Startup clears only DS0000..2011 and does
not produce these tables. Resource selection requests up to1000h bytes into
GroundResourceBuffer at1B4B, a range that includes both bases. At leastC2Eh
returned bytes reach the first color byte andC3Eh reach the first point byte.
The pinned420h ground files do not reach either; longer provider reads can.
The base names therefore do not make either stream immutable or bounded.

## Two-byte strip leaf6F7B

The103-byte6F7B..6FE1 leaf receives its source segment in incoming CX. CLI
precedes PUSH DS and five ordered mirror/OUT pairs: map mask0F, set/reset03,
enable-set/reset0E, mode0 and rotate0. DS becomes incoming CX, ES becomesA000,
BP saves incoming DI and CX starts at8. Each row PUSHes CX, reads the first
VGA latch, LODSWs one source word and uses its low/high bytes as sequential
bit masks for two STOSB writes, with a second latch read between them.

LODSW and STOSB follow DF. The literal ADD DI,2Ah gives row stride44 forward
and40 backward. POP CX reads the real saved word before LOOP, so an alias or
provider can change the number of rows; eight is no execution clamp. The
last ADD defines residual arithmetic flags. STI precedes the actual POP DS
and RET. Source words, SS mirrors, VGA writes and saves retain their physical
20-bit aliases and live high-byte accesses.

## Remaining sprite callback frontier

DrawObjectSprite706F..715E owns240 bytes/113 sites. It PUSHes the live record's
callback at70F0, later POPs it into AX at7159, and CALLs AX at715B with actual
return715D. The visibility miss jumps to that same saved-DI/RET suffix. The
optional strip CALL7152 returns7155 and restores real BX/SI/CX/DI saves before
the callback. Its POP DS can change the data segment seen by that callback.

Startup0FC1..0FF1 initializes nine words at DrawingCallbackSlots002E..003E:

| Slot displacement | Target | Known bytes / sites |
|---|---|---|
| 00 | 6170 | 873 / 478 |
| 02 | 64D9 | 255 / 126 |
| 04 | 65D8 | 255 / 126 |
| 06 | 66D7 | 320 / 159 |
| 08 | 6817 | 320 / 159 |
| 0A | 6957 | 320 / 159 |
| 0C | 6A97 | 324 / 163 |
| 0E | 6BDB | 289 / 147 |
| 10 | 6CFC | 391 / 198 |

There are32 observed direct record+14 stores through AX loaded from those slots:
22 use slot00; slots02/04/06/0A/0C/10 have one each;08/0E have two each.
Indexed stores, copies and aliases prevent this from closing the whole target
set. The nine graph leaves total3,347 bytes/1,715 sites. Their source segment
comes from CX=live DS1FE6 plus the computed BP; SI and BX are source cursors,
DI is the destination, and DX receives saved alignment. The strip instead uses
GeneratedGraphicsBufferSegment1FE8. Source allocation/record descriptors and the
6170/64D9/65D8 native contracts are now documented in entity-sprites.md. The
remaining six callback leaves and the broader source/IRQ domains stay open.
These static targets do not resolve every715B execution.

## Scoped verification

The minimap gate passes40 fixtures at both APIs plus4 null-bus repeats:
141 bytes/all58 sites/all5 jump outcomes,2,096 compared ordered events and
eight completed mutants. It includes live RAM/VGA records, stack and table
aliases, providers, signed/wrapped guards, DF/IF and actual near returns.
The producer gate passes28 fixtures at both APIs:64 bytes/all27 sites/no jump
edges,14,672 events and eight completed mutants. Its exact loaded views and
independent RAM/FLAGS projection check both marker writes and live POP ES.
The dirty gate passes33 fixtures at both APIs:171 bytes/all73 sites/all25 jump
outcomes,7,690 events and seven completed mutants. Its ordinary-RAM projection
checks every stack/dirty write, the4096-step adjustment and the256-store row.

Two separately verified native producer cores feed four accepted/rejected
record handoffs at view origins0/0180, with prepared3654->3657 caller frames.
The two producer plus four consumer comparisons add598 actual bus events;
producer events are counted once per execution. These are data-flow cases,
not execution of the3634 caller. The three new code ranges add376 unique main
C bytes, taking the ledger union from18,595 to18,971 without counting handoffs
or existing mask-table bytes again. Reports are build/entity-minimap-differential.json,
build/view-visibility-differential.json and build/entity-dirty-differential.json.
Only their exact recorded scopes and matching input hashes own acceptance;
this checkpoint does not renew full-campaign or whole-game evidence.

DrawEntityPointCloud passes 31 fixtures/62 core and actual RET comparisons: 248 bytes/all 110 sites/all 17 jump outcomes, 292,396 ordered bus events and 10 completed mutants.
DrawEntityTwoByteStrip passes 26 fixtures/52 core and actual RET comparisons: 103 bytes/all 47 sites/all 2 jump outcomes, 6,928 ordered bus events and 8 completed mutants.
The point gate adds four null-bus repeats and completes the original zero-count
65,536-iteration scan at both APIs. The strip gate independently checks
2,816 plane-byte writes and finite saved-count providers, including a nine-row
expansion. Full RAM, returned roles, defined FLAGS and ordered bus/device
state match original ASM. These disjoint leaves add351 unique main C bytes,
taking the ledger union from18,971 to19,322. The live table bases retain
UNKNOWN ownership and no new bounds or immutability claim. Reports are
build/entity-points-differential.json and build/entity-strip-differential.json;
only matching scopes/input hashes establish these focused results. This does
not refresh aggregate campaigns or establish whole-game acceptance.
