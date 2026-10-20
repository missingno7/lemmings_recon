# Menu graphic caches and two-page handoff

RefreshMenuSoundGraphic at4E37..4EA1 and RefreshMenuLevelGroupGraphic at
4EA2..4EE6 now compose the native8822 renderer in c/menu_cache.c. Their176
instruction bytes add once to the main-image C union, now28,087 bytes. The
shared tests/verification.py engine supplies execution, canonical bus access,
guarded native callbacks and comparison; this campaign introduces no new engine.

## State ownership

| Live DS byte | Ledger name | Producers and consumers |
|---|---|---|
| 1F70 | MenuSoundRedrawToggle | Reset0 at4420; XOR FF at44BA; read by4E37 |
| 1F72 | MenuSoundRedrawCache | ResetFF at441B; update by4E37; marker2 gates44B3 |
| 1F6E | MenuLevelGroupIndex | Normal0..3 increment/decrement bounds at4502/4532; unexpected bytes wrap (main-menu.md); quotient of level selection divided by30 at52A1; read by4EA2 |
| 1F6F | MenuLevelGroupRedrawCache | ResetFF at4416; update by4EA2; marker4 gates44EC/451C |

These are original bytes in canonical RAM. There is no host-side valid bit or
page-state copy. A mismatching cache becomes marker2/4 and draws once. On the
following call the marker becomes the current byte and draws again. Subsequent
equal bytes return without drawing. Swapping the actual drawing origins between
calls therefore updates both pages. A current value equal to the marker forces
drawing on every call; sentinel values are not disjoint from the input domain.
No-draw paths preserve incoming AH and leave AL holding the cached byte. Their
last arithmetic operation is a byte CMP, with byte-width flags.

Menu input44BA toggles the complete sound redraw byte, rather than a boolean.
The separate selector1F71 chooses CS:44E9's00/01/03 values for SoundOptionBits
at25A7. The drawing routine tests bits0..1, then bit1. Only an exactFF at
ExternalSoundDriverEnabled2010 selects sourceEA50; a nonzeroFE does not.

## Source contracts

Sound drawing publishes UiGraphicsBufferSegment1FEE to GraphicsResourceSegment
1FE4. A zero low-two-bit sound option draws the120x61 four-plane background
at sourceB120, maskBBD9, (x,y)=(324,120), BP3. Other options draw a64x31
four-plane icon atEA50 orEE30, (351,146), BP1. Incoming DI is still passed to
the opaque renderer even when that body does not consume it as a mask.

Each icon occupies03E0 bytes; the two icons close section3 atF210. Together
with the two-plane320x104 prefix0000..2080, backdrop2080..9488 and six
four-plane120x61 decorations9488..EA50, these source extents partition the
decoded section3 bank. This is static source-layout evidence; it does not
execute the loader or resolve all other interpretations of those bytes.

Level-group drawing publishes UI+1000 paragraphs, then rereads the live group
byte after the comparison/cache write. It clears BH, doubles BX and fetches
the source word through live CS:4EE7+BX. The four observed words are
57F4,5428,505C,4C90, separated by03CC bytes (four72x27 planes). The request
uses (486,145), CX041B, DX72 and BP1. No index clamp is present: indices4,
127 and255 still read adjacent original bytes. The eight table bytes retain
their UNKNOWN storage classification; naming a consumer does not classify
every possible interpretation. Graphics selection and the table address keep
the original16-bit and20-bit wrap rules.

## Frames and verification boundaries

The relocated intact far operands at4E7E,4E9C and4EE1 target same-CS:8822.
The C core pushes actual CS and return IP, composes the tested renderer and
consumes the actual far-return words. It retains returned registers, live DS/ES,
SS:SP and flags. Renderer stops retain pending frames; changed far return words
produce a distinct stop at the observed continuation. READY stops before the
parent's own near RET. Only the adapter consumes that actual near caller word.
Stack/data aliases, physical high bytes and cached-byte writes into return
frames are observable rather than repaired.

The local campaign passes571 fixtures/1,202 comparisons: all60 own instruction
sites and16 direct branch outcomes,845 integrated sites/118 outcomes in4,921
known connected bytes. It executes7,527,855 original instructions and compares
4,386,706 ordered events, with448 separately counted far-return observations.
Seven completed mutation witnesses distinguish lost AH, premature marker return,
nonzero versusFF sound gate, a cached group reread, uncleared BH, wrong table
segment and an ignored changed far return. Exhaustion never earns mutant credit.

Both boundaries cover all256 equal-byte values for both entries, marker and
mismatch paths, three loads, DF, distinct DS, word/physical wrap, VGA data,
live index/table/source changes, dirty positive/changed inner return, changed
far returns and cache/near-return aliasing. Pinned decoded sections3/4 are used
in memory without asset dumps. Six same-RAM handoffs (two entries at three
loads) each run six draws and six actual display swaps. Original-produced cache
bytes are carried forward, and all four page planes agree after each second
update. The caller constructs only the next actual near frame and input change.

The initial live-current fixture changed the very byte being serviced by a
reference read hook, causing the canonical-RAM self-check to fail. It earned no
report or mutation credit. Moving the injection to the following cache write
keeps it between the two reads under test and preserves a consistent oracle;
no game C change or comparison masking was needed.

Every invocation is bounded at500,000 instructions/200,000 events. The worker
has240 seconds and384MiB process-tree commit inside a270-second outer envelope,
leaving cleanup time for parent-owned temporary DLL directories. Compact traces
use the existing lossless shared engine capability. The accepted run completes
in125.70 seconds. The inherited RETF selector-EA wrap limitation atSPFFFE/FFFF
and the earlier artificial VGA-stack masked-loop exhaustion remain unverified.
Upstream menu coordination, loader execution, scheduling and native services
remain open. This is local connected evidence, not aggregate/full-game acceptance.
