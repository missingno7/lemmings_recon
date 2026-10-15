# Observable memory before full level initialization

`InitializeLevelFromRecord` at `36B6` now composes the bus-aware children in a
separate36-case gate. Its explicit bounded domain inherits their device and
alias contracts; implementation does not establish wider native hardware/IRQ
ownership. See level-initialize.md.
The maintained bytes now live in `src/level_initialize.asm` (`368E..3789`).

The drawing initializer, clear tail, terrain renderer and minimap column already
accept a raster bus. Their callbacks share one canonical memory image and own
VGA planes/latches. The four-call object-state span at `376A..3775` now has a
separate optional-bus composition in `c/object_state_bus.c`. Its RAM API remains
available. The bus variant routes CALL writes, child accesses and actual RET
reads through one canonical bus; see object-state-bus.md for its bounded gate.

| Child or span | Existing boundary | Work before bus composition |
|---|---|---|
| `378A` graphics-record copy | RAM API and separately verified bus API | Use the bus API, including live saves and RET |
| `37C2` object interaction cells | RAM API and128-case bus core/adapter gate | Retain BE byte order, template words, cell writes and live SS saves |
| `3839` steel interaction cells | RAM API and393-case bus core gate; seven added bus adapter probes | Retain packed-byte order, flag phases and restored dimensions |
| `389F` coordinate collection | RAM API and164-case bus core/adapter gate | Retain X store before Y reads and arithmetic flags at accesses |
| `376A..3775` four-call span | RAM API and113-case bus core/adapter gate | Use the same bus for every CALL, child and actual RET |

The RAM tests establish final registers, memory and defined flags in their
declared domains. They do not establish per-access flags or an evaluation order
between C operands that have only ordinary-RAM reads. Adding a callback to a
compound expression is insufficient: calls to that callback must be explicitly
sequenced. The byte reads of a BE word wrap their offsets independently; the high
byte of a machine word uses the next physical byte, with 20-bit address wrap.

## Instruction obligations

| Original sites / bytes | Required order and flag phase |
|---|---|
| `376A E81D00`, `376D E8C900`, `3770 E84F00`, `3773 E82901` | Write live near continuations376D/3770/3773/3776, call the logical child, then reread each actual return word; CALL/RET preserve flags |
| `37CB 8A6504`, `37CE 8A4505` | Read object type high byte before low byte; later MUL defines CF/OF only |
| `37DC 8A25`, `37DE 8A4501`, `37E9 03440E` | Read X bytes before the template X word; the ADD operand sees flags from preceding shifts, before ADD commits |
| `37EC 8A7D02`, `37EF 8A5D03`, `37F6 035C10` | Read Y bytes before the template Y word, preserving intervening shift/address arithmetic |
| `3812 0A4414`, `3815 8A7412`, `3818 8A5413` | Read kind, then width, then height; OR's memory operand sees pre-instruction flags |
| `381B 52`, `381C 53`, `381D 368807`, `3825 5B`, `3826 5A` | Push DX/BX, write cells, pop actual BX/DX; reconstruct INC/DEC/address ADD flags between events |
| `3840 8A25`, `3842 8A4501`, `3845 8A7502`, `3848 8A5503` | Steel definition bytes are read in0/1/2/3 order; byte3 alone can activate the record |
| `3886 36C60709` | Write the SS cell byte9 using flags from the original packed-coordinate and live-dimension path |
| `38B7 8A24`, `38B9 8A4401`, `38BC 051800`, `38BF 8907` | Read X, add18, write X before reading Y at38C1/38C4; current RAM C prefetches Y before X's store |
| `38C1 8A6402`, `38C4 8A4403`, `38C7 051E00`, `38CA 894702` | Read Y after X's output, add1E, then write Y |
| `393A 894F0A`, `393D 89470A` | Preserve both writes at BX+0A; the second overwrites the first and BX+0C stays stale |

The coordinate output starts at `0E98` and at most32 matches advance it128
bytes, ending at `0F18`, before definitions at `0FEB`. Thus its current Y
prefetch is not evidence of a RAM-alias failure in that fixed-layout domain.
It still loses the original bus order, which an observable backend must retain.
The existing final-state RAM comparisons remain useful regression evidence.

The older RAM cell cores model their final flags, not all intermediate MUL,
logical, rotate/shift and row-loop arithmetic phases. The bus extension must
restore defined arithmetic flags wherever exposed by the event trace, and
exclude only architecturally undefined bits. Matching only IF/DF would not
establish the full per-access contract used by the connected drawing tests.

The existing unchecked loops and live row saves must remain. Object dimensions
zero mean 256 iterations; steel dimensions can be changed by a saved-word alias.
Neither production bounds nor disjoint host arrays would preserve these effects.
CALL/RET words can also alias cells, definitions and later inputs. A changed
target remains an explicit continuation before executing that target.

The independent bus cell/coordinate fixtures now record ordered memory events
and defined flags, with device-backed source, destination and stack cases.
They compare optional-bus and existing null-bus paths in ordinary RAM and retain
the old aliases and mutation witnesses. The four-call span and finishing tail
now connect the full parent's nominal thirteen live minimap CALL/PUSH/POP/LOOP
handoffs, including finite aliases that change the saved count.
Full terrain-stream acceptance and the existing platform/IRQ seams remain
separate obligations.

Regression gates are the123 object-cell,386 steel-cell,159 coordinate and105
four-call RAM cases, plus the265 graphics-copy comparisons (131 null-bus and134
bus cases). Their current branch obligations are9/8/12/33 edges for the first
four suites. New bus cases and auxiliary core probes must be reported separately
from those historical adapter counts; physical C bytes and composed executed
sites remain unions rather than sums.
