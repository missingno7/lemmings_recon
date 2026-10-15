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
interaction-cells.md for live saves, return transfers and verification. The
36B6/394F setup consumers, native VGA ownership, far blit 8822 and broader
asynchronous/alias contracts remain unported. Full level setup is not complete.

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
