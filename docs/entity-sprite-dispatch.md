# Entity sprite dispatch at 706F

`DrawObjectSprite` is the existing ledger name for the entity-record parent at
706F..715E: 240 known bytes and 113 instruction sites. Its normal caller at
3634 starts DI at `EntityRecordsBase` (DS:0088) and advances by 2Dh. These are
distinct from the 1Ch object graphics records at DS:17CB. The parent takes a
live DS:DI record, with no converted record or host-owned game state.

## Record and source ownership

The ledger names first-record field anchors. An operand such as
`DI + EntityRecordSpriteCallback - EntityRecordsBase` still uses the actual DI
and DS; the anchor does not validate a record index, lifetime or allocation.

| Record offset | Width | Ledger field | Observed role in 706F |
|---|---|---|---|
| 00 | word | EntityRecordX | First horizontal addend |
| 02 | word | EntityRecordY | First vertical addend |
| 04 | word | EntityRecordDrawingXBias | Second horizontal addend |
| 06 | word | EntityRecordDrawingYBias | Second vertical addend |
| 0A | word | EntityRecordSpriteSourceOffset | Adds to product low nibble for SI |
| 0C | word | EntityRecordSpriteParagraphOffset | Adds to shifted product for BP |
| 10 | word | EntityRecordSpriteFrameStride | Multiplies frame/alignment index |
| 12 | word | EntityRecordSpriteMaskOffset | Adds to SI for BX |
| 14 | word | EntityRecordSpriteCallback | Initially pushed callback target |
| 20 | byte | EntityRecordStripSelector | Gates optional strip and forms its source offset |
| 27 | byte | EntityRecordFrameAddGate | Value 1 suppresses the byte at29 |
| 28 | byte | EntityRecordFrameSelector | Initial frame byte |
| 29 | byte | EntityRecordFrameAddend | Optional wrapping byte addend |
| 2A | byte | EntityRecordAlignmentGate | FF suppresses eight-way scaling |

The first wrapped X sum receives one 160h addition if negative. Its logical
quotient by eight indexes the live byte at `ViewVisibilityMapBase`; only an
exact 1 draws. A miss restores the actual saved DI and returns without reading
the callback field or entering a child.

The visible path subtracts `LevelViewOriginPixels - 10h` from X and adds 160h
once if the wrapped result is negative. Its low three bits are saved as the
alignment. The byte frame addition wraps before AH is cleared. Unless the
alignment gate equals FF, three one-bit SHLs and an ADD select eight frames
per original frame byte.

The full unsigned product with the live frame-stride word is shifted right
four through DX:BP. Its low 16 paragraph bits plus the paragraph offset supply
BP. Independently, the product low nibble plus the source offset supplies SI;
adding the mask offset supplies BX. Carries from these cursor additions are
not normalized into the segment. The live `EntitySpriteBufferSegment` plus BP
supplies CX. These calculations identify coordinates, not resource bounds.

The Y add wraps; a signed-negative result becomes zero. Its full MUL by 2Ch
leaves the low product in DI before adding the saved horizontal quotient and
live `DrawingOrigin`. Intermediate saves, residual roles and instruction-defined
flags remain observable. All offset/SP updates wrap at 16 bits, whereas a word's
high byte is read or written at physical address +1 with 20-bit wrap.

## Live frames and child boundaries

Entry PUSH DI preserves the caller's record cursor. The visible path also saves
alignment and pushes the callback field at70F0. That field is read before the
later Y/selector/global reads; subsequent alias or provider writes can change
the saved target before POP AX at7159.

If the restored selector AL is nonzero, the strip path preserves alignment,
callback and DI/CX/SI/BX through actual SS words, selects the live generated
graphics segment, forms its literal1070h-based source offset, subtracts15Fh
from DI, and CALLs6F7B with the actual7155 return word. Its returned DS/ES and
flags flow into the parent. The four restores at7155..7158 reread live words.
An altered child return must stop before assuming these restores ran.

POP AX/POP DX at7159/715A supply the actual callback and alignment. The near
CALL at715B pushes715D. Nine initialized callback slots supply known native
children, but arbitrary writes or copies leave this target domain open.
An unknown target remains an explicit boundary before that CALL; no guest
return word has yet been pushed. A recognized callback consumes its actual
return; a changed target stops before the715D restore. Normal return restores
DI from SS, then the outer RET715E consumes the original caller word.

The C core/adapter statuses are READY=0 at pre-RET715E, UNKNOWN_CALLBACK=1 at
pre-CALL715B, and CHILD_RETURN=2 at a changed child target. Only READY permits
the adapter to consume the outer return. These boundaries preserve evidence
without claiming target closure, IRQ timing or complete gameplay acceptance.

## Verification scope

The bounded native campaign passes 45 fixtures at both APIs: 90 comparisons,
all 113 parent sites and 15 branch outcomes, 63,950 ordered byte-bus events and
ten completed mutation witnesses. Full RAM, returned roles, defined FLAGS,
ordered accesses and VGA planes/latches/registers match the pinned original.
All nine callbacks run at alignment zero and seven. The integrated domain
contains 3,690 bytes, all 1,875 sites and 144 branch outcomes. Only the parent
adds 240 unique translated bytes, taking the main-image ledger union from
22,669 to 22,909.

Closed-form entry-RAM calculations independently check coordinates, the full
frame product, paragraph segment, source/mask cursors, destination, callback,
alignment and SP at the original pre-CALL715B boundary. These checks exclude
provider paths that deliberately change saved inputs. Three handoffs use
unchanged bytes from original 5B11, 5BB0 and 5C06 producers: aligned bank five,
raw three-plane/thirteen-row data at shift seven, and wide bank three. Their
producer sites and transactions remain separate; producer code is untranslated.

Provider witnesses change the saved selector despite raw record selector zero,
replace known/unknown callback words, replace saved DS and DI, and change both
child return words. A physical-wrap SS fixture returns from the callback to
0100 after mirror writes alter its return word; a visibility miss independently
reads the outer return across physical FFFFF..00000. Timeout, commit-limit or
access-budget exhaustion fails the gate and cannot count as a mutant mismatch.

Run `tools/difftest.py entity_sprite_dispatch` for the native gate or
`tests/entity_sprite_dispatch.py --original-only` for the original-only scope.
The registered runner caps the suite at 420 seconds and 384 MiB per process;
each original pass has a 60,000-instruction and 30,000-event budget. Reports
are build/entity-sprite-dispatch-differential.json and the separate
entity-sprite-dispatch-original-differential.json. Only matching scopes and
input hashes establish this acceptance; it does not refresh broad campaigns
or establish complete gameplay.
