# Object drawing frontier

This is a static contract map for the object-drawing suffix of `sub_394F`.
It does not translate code or claim that arbitrary segment aliases are solved.

## Closed suffix and control flow

The useful closed range is `397A..39CD` inclusive (`397A..39CE` exclusive):
84 bytes, 34 decoded instruction sites, SHA-256
`3f2e244bb959b0f66a02dd70b8da6a81b09e7540095df8a01881607a29cad47e`.
Its bytes are:

```text
e8 0d fe 8d 36 cb 17 8d 3e eb 0f b9 20 00 a1 f0 1f a3 e4 1f
8a 25 8a 45 01 23 c0 74 2e 51 57 56 8a 7d 02 8a 5d 03 8a 75 06
8a 55 07 8b ea 83 e5 fe 8a 54 04 32 f6 8a 4c 05 8b 7c 08 8b 74
17 03 fe b5 04 9a 22 88 00 00 5e 5f 59 83 c7 08 83 c6 1c e2 c1 c3
```

There is no graph-discovered outside entry into the suffix interior. The two
parent paths to its first byte are the special-resource jump `395C -> 397A`
and the normal terrain-stream sentinel branch `3973 -> 397A`. The first
instruction calls `CopyLevelObjectGraphicsRecords` at `378A`; normal return
continues at `397D`. Within the loop, `JZ` at `3995` skips a zero-X definition
to `39C5`; `LOOP` at `39CB` goes back to `398E` or falls through to `39CD`.
The final `RET` is a near return. No shared tail was found for this suffix.

The enclosing parent remains `394F..39CD`: it calls `InitializeLevelDrawing`
(`368E`), chooses special resource setup (`1A7B`) or the packed terrain
stream (`7C67`, which also calls `8822`), then reaches this suffix. Its only
graph-discovered outside call is `4612 -> 394F`. The parent therefore depends
on the setup, resource, terrain, record-copy, and far-renderer contracts; the
84-byte suffix alone is not a full level-redraw implementation.

## Record producer and call inputs

The loaded LEVEL record starts at `DS:0FCB`. Its 32 definitions are at
`DS:0FEB`, eight bytes each, with four big-endian words: X at `+0`, Y at `+2`,
type at `+4`, and drawing flags at `+6`. The mutable 28-byte working slots
start at `DS:17CB`; the ground resource input starts at `DS:1B4B`.

`378A..37C1` walks all 32 definitions. It skips copying when the X word is
zero, leaving the destination slot stale. Otherwise it takes the full
big-endian type word, computes `type * 28`, adds the low product to the live
source offset with 16-bit wrap, and copies 28 bytes to the next working slot.
There is no type bound check. `MUL` leaves the product high word in DX; the
source cursor uses only AX. The helper copies from DS to ES after its live
`PUSH DS / POP ES`, follows incoming DF, and starts backward copies at the
record base rather than at its last byte. Its SI/CX/DI saves and the return
word remain live on SS. Those details are recorded in
[object-records.md](object-records.md).

The drawing loop itself never reads the definition's type. It tests X only;
when active, it reloads the raw big-endian coordinates and drawing flags and
builds the far-call inputs as follows:

| Input | Construction at `398E..39BB` |
|---|---|
| `AX` | Definition X word, unchanged |
| `BX` | Definition Y word, unchanged |
| `BP` | Definition flags word AND `FFFEh`; bit 0 is always cleared, other bits survive |
| `DX` | `00h:width`, with width from working slot `+04` |
| `CX` | `04h:height`, with height from working slot `+05` |
| `SI` | Little-endian current-frame/source offset word at slot `+17` |
| `DI` | Little-endian mask-source offset at `+08`, plus SI with 16-bit wrap |

Before the loop, it copies the live word at `DS:1FF0` (`LevelGraphicsSegment`)
to `DS:1FE4` (`GraphicsResourceSegment`). The 28-byte working record fields
read here are therefore width `+04`, height `+05`, mask-source offset `+08`, and
current frame offset `+17`. Other known fields and their animation/interaction
consumers are listed in [object-records.md](object-records.md). The renderer
at `8822` tests BP bit 0 at `889D`; with an intact saved control word, clearing
it takes the direct unshifted selection at `88A3`, even for unaligned X. Child
stack aliases can change the live BP before this test and retain their existing
seams. DI is the incoming mask cursor, not the pixel destination: `8822` derives
the latter from coordinates and live drawing-layout fields before exchanging
the incoming DI into the mask cursor at `887E`.

Under ordinary intact-stack execution, CX starts at 32 and each pass advances
definition DI by 8 and working-record SI by 28. The active path saves CX/DI/SI
on SS, then restores them with live pops at `39C2..39C4` after the far call.
If those stack words are aliased and changed, the restored cursors/count
control later reads and `LOOP`; there is no hard 32-iteration guard. A zero-X
definition is skipped by the draw loop even though `378A` leaves its working
slot untouched.

## Segment, stack, and flags

The `378A` near call uses the current SS and leaves DS unchanged. With ordinary
RAM stack readback, its PUSH DS / POP ES sets ES to DS. A device-backed stack
can return a different live word; the instruction contract is the actual pop,
not a cached assignment of DS. It does not restore the caller's previous ES.
The later `8822` far call pushes and consumes a live far-return frame;
its original entry first pushes AX, DX, and CX. The loop only restores SI, DI,
and CX, and does not save DS, ES, BP, or flags around the far child. Preserve
the child’s live segment and stack effects rather than assuming these values
are cached or reset between objects. `CS` returns through the far frame on a
normal child return; altered return bytes can redirect it.

The object loop uses DS for both its definitions and working records after
each child return. `378A`'s REP MOVSB is DS-read/ES-write, not an abstract
record assignment. The `lmn_copy_object_graphics_bus_core` extension now has
134 original-versus-C cases, including independent device evidence for source,
destination and SS stack readback; see object-graphics-bus.md. A concrete
VGA-aperture example with ordinary stack readback is DS=`A000h`:
the source is physical `A1B4Bh` and the first destination is `A17CBh`, both
inside the `A0000h..AFFFFh` aperture. By contrast DS=`08E0h` gives physical
`0A94Bh` and `0A5CBh`, outside that aperture. Keep the device-mapped DS/ES
case explicit when composing the parent; the finite bus cases do not establish
every incoming provider or alias domain.

The far call and all loop saves also use live SS. The canonical load state
derives SS=`244E` from load segment `1010` plus initial SS delta `143E`; that
segment lies beyond the static image. It is evidence for the ordinary caller
stack location, not a proof for arbitrary SS=DS/CS aliases, stack/data overlap,
or device-backed stack accesses. The caller itself installs no SS policy.

On the normal return path, `ADD DI,8` and then `ADD SI,1Ch` set arithmetic
flags after the pops; `LOOP` and `RET` preserve them. Thus the final status
flags come from the last `ADD SI,1Ch` (CF/PF/AF/ZF/SF/OF), while DF/IF/TF and
other unaffected flags remain live from the child/caller. For the next
iteration, the `AND AX,AX` at `3993` replaces the arithmetic status flags;
its AF is undefined. Any changed far return or overwritten saved count can
prevent the ordinary final path, so this flag description is conditional on
the loop reaching `39CD` normally.

## Supplied LEVEL/GROUND observations

Static parsing of the 80 pinned LEVEL sections and their referenced GROUND
files found 453 nonzero-X definitions (3..15 per section). Referenced ground
indices are 0:19, 1:21, 2:19, 3:15, and 4:6 sections. The active type domain
is `{0,1,3,4,5,6,7,8,9,10}`; the active flag words are `000Fh`, `400Fh`,
`800Fh`, and `C00Fh`, and all 453 have bit 0 set. X spans 16..1552 and Y
spans 0..172, with 13 active Y values equal to zero.

Across the 453 active definitions, the selected source-template width values
at `+04` occur as 16:13, 32:106, 48:262, 64:62, 80:10. Height values at
`+05` occur as 8:60, 15:7, 16:53, 17:50, 19:15, 20:19, 21:21, 24:24,
25:114, 26:2, 28:24, 32:50, 34:6, 38:1, 41:4, 42:2, 71:1. The little-endian
word at `+17` in those selected source templates is `0100h`:251, `0200h`:33,
`0600h`:31, `0800h`:66, `0E00h`:3, `0F00h`:7, and `1000h`:62.

Each supplied `ground0o.dat` through `ground4o.dat` is 1056 bytes. Its first
16 records are the 448-byte object-template span. The following 64 terrain
records occupy 512 bytes beginning at `DS:1D0B`; 96 trailing bytes begin at
`DS:1F0B`. These fixture counts describe the pinned inputs only. `378A` still
accepts an unchecked 16-bit type and can index beyond the first 16 templates;
the observed dimensions and offsets are not C-side bounds or safe maxima.
Also, `7C0A` can mutate working animation/frame state after the copy, so the
`+17` histogram above is for source templates, not a bound on the live word
at the later draw.

## Remaining unknowns for parent composition

The full `394F` path still needs its setup/resource and terrain-stream state
ownership composed with this loop and `8822`. Static evidence here does not
close arbitrary VGA/provider semantics for `378A`, code/data aliases, stack
aliases or return-word corruption, or the full incoming DS/ES/SS domain. It
also does not prove that width, height, current-frame offset, type, or iteration
count are bounded beyond the supplied fixture observations. Do not turn these
unknowns into clamps or into claims that unreachable bytes are dead.
