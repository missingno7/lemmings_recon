# Level object records and working state

The loaded LEVEL record begins at DS:0FCB. Its 32-byte header is followed by
32 eight-byte object definitions at DS:0FEB..10EA. Every definition contains
four big-endian words: X, Y, type and drawing flags. The ledger owns
LevelObjectDefinitions and LevelObjectGraphicsRecords; neither is a converted
structure or a second copy of canonical game state.

CopyLevelObjectGraphicsRecords (378A..37C1) initially visits 32 definitions.
A zero X word skips the copy and retains all stale destination bytes. Otherwise,
the full type word multiplies by 28 without a bounds check. The low product and
the source addition wrap in 16 bits, selecting a live source at DS:1B4B+product.
DX retains the high product. The destination starts at DS:17CB, with 28-byte
slots ending at 1B4A immediately before the ground buffer.

DS is pushed and popped into ES; REP MOVSB follows incoming DF. Backward copies
start at the slot/template base, not its final byte. Copies read and write one
byte at a time, retaining overlap and cursor wrap. SI, CX and DI are restored
from live SS stack words after every active copy. Those words can be overwritten
by a destination alias; the restored counter or cursors then determine subsequent
iterations. The original final flags come from ADD DI,28, after BX advances eight.

The working records are mutable: 7C0A changes their animation state and frame
offsets, while 394F and 7BB8 use them for drawing. The inspected fields are:

| Slot offset | Observed use |
|---|---|
| 00, word | Animation flags; bit 1 enables frame advancement |
| 02, byte | Current animation frame |
| 03, byte | Frame limit |
| 04/05, bytes | Width/height passed to the far drawing routine |
| 06, word | Multiplier for the current frame offset |
| 08, word | Base drawing offset |
| 0E/10, words | Interaction rectangle X/Y cell offsets |
| 12/13, bytes | Interaction rectangle width/height |
| 14, byte | Interaction cell kind, ORed with object ordinal shifted four |
| 15, word | Added base for animation frame offset |
| 17, word | Current frame offset added to drawing offset |
| 1B, byte | Value passed to the sound service after a hit |

Words in these ground/working records are little-endian. Definitions remain
big-endian. Other bytes and wider producer/alias domains remain unresolved.
The supplied ground input has 16 consecutive 28-byte records at its start.
The unchecked object type is not restricted to that observed extent.

## Per-tick animation and drawing contracts

AdvanceLevelObjectAnimations3944 tests the live EntityUpdateGate at DS:002B.
Exactly FF returns at394E without visiting records. Otherwise its JMP enters
AdvanceLevelObjectAnimationRecords7C0A; this transfer adds no CALL frame. The
tail initializes SI=17CB, DI=0FEB and CX=32 and visits every slot. It is93 bytes/
35 sites; the gated entry owns104 bytes/39 sites across the two physical ranges.
The7BB8..7C66 block lives in object_graphics_tick.asm, with exact module bounds.

For zero X, the tail jumps directly to7C5C and stores the current BX into the
record flags. BX is stale from entry or the previous processed record; no flags
load occurs for this zero-X slot. This differs from the378A copy's stale-byte
skip and must not become a clean inactive-object test. Nonzero X reads only
definition byte+5 for type. If it equals1 and EntityCreationGate0055 is not FF,
the slot skips all animation and flag stores. A high type byte does not alter
that gate. Other slots load the live flags word; bit1 enables advancement.

Enabled slots read current frame+2 and limit+3, increment AL with byte wrap,
and reset to0 only when the resulting byte equals the limit. Values already
above a nonzero limit keep advancing; limit0 can match FF-to00 wrap. At an
equal-limit wrap, flag bit0 clears bit1, retaining every other bit. The current
frame byte is written before reading live unsigned stride+6. MUL sets DX:AX;
the live base word+15 is added to low AX and written to+17. High DX remains the
product high word. The flags word is then stored at+0. Provider changes between
these accesses must remain visible; no record snapshot or decoded structure
owns the state. Both cursor additions and LOOP retain their original flags.

The tail changes no segment register or DF/IF and has no internal stack frame.
The core boundary is immediately before7C66 RET; the gated early boundary is
before394E RET. An adapter must read the actual live SS:SP word after all stores,
including a flags/frame/offset store that aliases that return word. Arithmetic
flags undefined after logic/MUL remain separate from defined flag observations.
The7BB8 drawing connection retains its actual far8822 frame and live CX/DI/SI
saves rather than copying these records into host-owned state.

Scoped animation acceptance now passes61 fixtures at logical-core and actual
near-RET adapter boundaries, with12 additional null-bus repeats:134 comparisons,
all39 sites/all17 jump outcomes,22,816 compared native bus events and2,110
reference events for the null-bus repeats. Eight compiled mutants complete and
are detected. The direct7C0A tail contributes35 sites/14 outcomes within that
scope. Fixtures cover every single-active position and all256 frame bytes,
separate update/creation gates, equality/over-limit/FF wrap, staleBX and the
retained one-shot bit0, full DX product, post-frame live base provider/stride math,
future definition/type-gate providers, DF/IF, DS=SS record/return aliases,
physical20-bit outerRET wrapping and VGA-backed records/stack. The independent
ordinary-RAM projection uses the exact sequential record behavior.

The report is build/object-animation-differential.json; its input hashes own
acceptance. Gated and direct-tail ranges overlap: only104 unique main C bytes
are added (18,100 to18,204). Initialization, renderer connection, scheduling
and broader allocation/provider domains remain separate.

DrawLevelObjectGraphics7BB8 initializes the same two cursors and CX=32. For
nonzero big-endian X it first saves CX,DI,SI, then computes X-live[DS:0000]+16
with16-bit wrap. Y and drawing flags are big-endian; bit0 of flags is cleared.
That cleared bit forces8822's unshifted selection even for non-byte-aligned X;
do not silently replace it with a coordinate-based shifted dispatch.
Live graphics+4/+5 supply byte width/height, +17 supplies SI, and +8+SI supplies
the mask cursor DI. CH becomes4. The farCALL7BF9 pushes the actual CS and7BFE
return IP; the native child is the existing8822 planar core.

The caller does not initialize GraphicsResourceSegment1FE4. The renderer reads
that live source segment; the explicit game-data segment carries the relocated
09A9 operand used by renderer bodies and need not equal current DS. Child-returned
DS/ES and every general register remain live. Only a normal child boundary
permits reading RETF's actual IP/CS, and only expected CS:7BFE permits POP SI,
DI,CX. Cursor additions and LOOP then use these live values; CX=32 is an initial
value, not a hard iteration cap. Missing byte-port services, changed child near
returns and changed far returns stop before those parent restores. The normal
core boundary is before7C09; the adapter alone consumes its actual outer RET.

The drawing gate now passes50 constructed caller fixtures plus one actual
native animation-to-drawing handoff:55 core/actual-RET comparisons, all33 caller
sites/all4 jump outcomes,346 integrated sites,30,706 ordered bus events and109
independent plane checks. Six compiled mutants complete and are detected.
All32 single-active positions and both full32-object DF passes retain their
complete records. Explicit first-OUT providers rewrite the actual child-saved
DS, parent-saved SI/DI/CX and far return IP; the original preflight proves
DS=7000, the changed two-iteration cursor result, and far target4567. A separate
dirty-map alias proves the child near-return stop. Missing read-mask byte
services stop at969C. DS=SS and physically wrapped stack words remain live.

The handoff first compares the native animation adapter with ASM on complete
RAM/registers/flags/events, then feeds that exact resulting memory and state
into the drawing adapter. Its computed frame source0100 and independent child
inputs/planes are checked without a host graphics-record projection. This
does not accept the enclosing01B6/01B9 CALL sequence or IRQ schedule.
The report is build/object-drawing-tick-differential.json with matching input
hashes. Only82 new caller bytes are added; the renderer and animation overlap
their existing ranges. Together the pair adds186 unique main C bytes, taking
the ledger union from18,100 to18,286. This is scoped acceptance; retained older
reports do not become current aggregate evidence by surviving on disk.

GroundTerrainGraphicsRecords at DS:1D0B..1F0A is the following 64 eight-byte
records. 7C67 masks its terrain selector to six bits, then reads width/height
bytes at +0/+1 and little-endian drawing offsets at +2/+4. Its far drawing callee
at 8822 still owns clipping, overlap, VGA and further source state.

CollectTypeOneObjectCoordinates (389F..3943) scans all 32 definitions and accepts
the full type word equal to one. It does not require nonzero X. Each match writes
wrapped X+24 and Y+30 as little-endian words at DS:0E98, advancing four bytes.
The spawn consumer at 30DB..3100 selects one of the first four pairs using the
active-record index modulo four. This consumer does not bound the producer:
more than four matches still write beyond those four pairs, up to 128 bytes.
TypeOneObjectCoordinates names that maximum write span, not a proved allocation.

With one match, the last pair is repeated three times. With two, the last pair
is followed by the first. With three, the second pair supplies the fourth slot.
With none, X=0100/Y=0010 defaults are written with an original bug: the Y store
at +0A is overwritten by an X store at +0A, leaving +0C stale. No corrected
fourth pair is substituted. With four or more matches, no filling occurs.
The animation consumer at 7C21 checks only the low type byte, unlike this
collector's full-word comparison; malformed high type bytes can take different paths.

## Interaction cells and the remaining callers

37C2 initially processes 16 object definitions. It computes the unchecked
ground template before testing X for zero. Active objects write rectangles
to live SS memory. The wrapped base offset is:

    0012 + (X >> 2) + template_word_0E
         + 416 * ((Y >> 2) + template_word_10 - 1)

The byte value is `(ordinal << 4) | template_byte_14`. Width and height at +12/+13
use decrement loops: zero means 256 columns or rows. Row-base and dimension saves
are live stack words, so aliases can change subsequent writes. No separate cell
map can replace SS: it also holds the stack and VGA-register mirrors.

3839 processes 32 four-byte records at DS:172B. It skips only when both big-endian
words are zero. The first word encodes X as `(byte0 << 1) | (byte1 >> 7)` and row
as `byte1 & 7F`. The high and low nibbles of byte2 encode width and height minus
one, producing 1..16 cells in each dimension. Byte3 participates only in the
zero check. Rectangles write byte 9 at SS:0012+X+416*row with live row saves.

These cell-writing routines now have native cores, and the four object calls
inside 36B6 are connected within their original 376A..3775 span. See
interaction-cells.md for live saves, return transfers and verification. Their
native setup/redraw/render consumers have separate scoped gates; see
level-drawing.md,level-redraw.md and drawing-render.md. Wider allocation,
provider, native-device and asynchronous/alias contracts remain open. Full
level setup is not complete.

## Native leaf verification

c/object_graphics.c and c/object_coordinates.c use logical transient results
and direct access to canonical memory. Register carriers and caller RET consumption
are confined to their oracle adapters. The graphics core keeps its original live
stack saves; the coordinate core has no internal calls or stack saves. No asset
snapshots, interpreter or persistent shadow records are part of either core.

The graphics suite has 265 comparisons: 131 null-bus cases and 134 raster-bus
cases, covering the same 56 original bytes, 26 instruction
sites and four branch edges. All 32 single-active positions, both DF directions,
out-of-table types, wrapped product/source cursors, stale inactive slots, live
source/output overlap and overwritten saved SI/CX/DI are included. A controlled
counter alias terminates after two iterations and also overwrites the active
return word. Another saved-DI alias independently checks final sign/overflow
flags. The 80 supplied LEVEL sections use their matching ground inputs.

The raster-bus backend independently executes the pinned ASM and compares
ordered byte accesses and instruction-boundary flags as well as RAM/registers.
It includes device-backed source/destination and SS stack readback: POP ES can
read a different value from the preceding PUSH DS, and the original RET reads
the provider's live return word. The bus suite passes 49,740 accesses and three
additional mutation checks. It uses the established four-plane VGA fixture and
independent copied-byte expectations; see object-graphics-bus.md for the finite
domain and the explicit Unicorn REP/AF instrumentation diagnostic.

The coordinate suite has 159 cases, covering all 165 original bytes, 63 instruction
sites and 12 branch edges. Counts 0..32, every single-match position, full-word
type checks, zero-X acceptance, wrapped X/Y additions, exact fill patterns,
the repeated +0A bug and stale +0C bytes are checked independently. All 80 LEVEL
sections are included. Observed sections contain one type-one definition in 72
cases, two in four, three in two and four in two; these observations do not prove
a producer bound. Constructed cases retain the zero and greater-than-four paths.

Both suites compare full 1 MiB RAM, all boundary registers and defined final
flags. Only AF on the collector's zero-match AND path is excluded as undefined.
IF/DF, stack offsets 0/1/FFFF, physical address wrap and post-write live RET aliases
are covered. Six distinct compiled mutations detect clearing stale slots, clamping type
lookup, forcing forward DF copies, repairing the default bug, clamping match
counts and rejecting zero X. The three graphics faults are also rechecked
through the raster bus, for nine mutation checks across these two clusters.
C11 compilation treats warnings as errors.

Original execution is limited to the identified routine bytes, with budgets of
100,000 instructions per graphics case and 2,000 per coordinate case. The runner
caps the graphics runner at 180 seconds and the coordinate suite at 120 seconds.
Graphics workers have a 512 MiB process/768 MiB tree commit ceiling and owned
temporary DLL directories. The bus worker hard-exits on callback/budget failure;
these failures and original execution exhaustion cannot count as mutant hits.
TF is clear and asynchronous IRQ delivery
is quiescent. Saved-data and controlled return aliases remain live; arbitrary
instruction-byte self modification and unbounded saved-counter corruption are
outside these finite fixture domains. No original game was booted.

The four adjacent helpers now live in src/level_objects.asm at their original
378A..3943 position. Start/end assertions preserve physical layout. The two
interaction-cell routines are now native within interaction-cells.md's bounded
domains; drawing and larger caller integration remain the next frontier.
