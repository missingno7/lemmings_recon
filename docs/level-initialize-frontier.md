# Full initialization caller frontier

The fresh `tools/graph.py InitializeLevelFromRecord --tree --depth 2` and `--bottom-up` views
identify `36B6..3789` as 211 decoded bytes / 76 sites. Stored UNKNOWN `374E`
is excluded. This is a separate caller from redraw `394F`; translating redraw
does not initialize level header state, interaction cells or the minimap.
The complete caller now has a native logical composition with36 adapter and36
auxiliary core cases,76 caller/1408 integrated sites and211 edges. Its137-byte
header prefix retains its separate92-case contract; overlapping bytes/sites are
counted once. See level-initialize.md for the explicit bounded domain and the
still-pending complete terrain-stream acceptance gate.

## Header ownership to recover before translation

`36B6` calls `InitializeLevelDrawing`; the linear `36B9..3741` prefix then sets
DI to ledger-owned `LoadedLevelRecord` (`0FCB`). Every header word below is
read as separate MOV AH / MOV AL byte instructions, high byte first. Most
destinations receive only AL, even if the stored header high byte is nonzero:

| Header offset | Original consumer/store | Width/operation |
|---|---|---|
| `+00` | `36C1 -> DS:0064`, `36C4 -> DS:0067` | Same low byte stored twice |
| `+02` | `36CD -> DS:0047` | Low byte |
| `+04` | `36D6 -> DS:0044` | Low byte |
| `+06` | `36DF` ADD AX,`30`; `36E2 -> DS:20A7` | Wrapped word add, then low byte |
| `+08` | `36EB -> DS:006A` | Low byte |
| `+0A` | `36F4 -> DS:006D` | Low byte |
| `+0C` | `36FD -> DS:0070` | Low byte |
| `+0E` | `3706 -> DS:0073` | Low byte |
| `+10` | `370F -> DS:0076` | Low byte |
| `+12` | `3718 -> DS:0079` | Low byte |
| `+14` | `3721 -> DS:007C` | Low byte |
| `+16` | `372A -> DS:007F` | Low byte |
| `+18` | `3733` ADD AX,`10`; `3736 -> DS:0000`; three SHR AX,1; `373F -> DS:0002` | Wrapped word, then shifted word |

These addresses are observed storage contracts, not proposed historical field
names. The ledger now owns source-word anchors and destination names, including
neutral `LevelHeaderWord04LowByte` and ordinal `LevelActionCount0..7`.
The maintained `src/level_initialize.asm` groups the unchanged `368E..3789`
bytes, with physical module-end assertions. Original-only header checks cover
92 cases and all47 prefix sites; this evidence alone adds no C coverage.
Do not infer full destination widths, validation or an abstract converted header
from the disk format. Both high-byte reads and original stores remain observable
through the canonical bus. Three separate SHR instructions also have their own
flag semantics; replacing them with one multi-bit shift would need justification.

## Remaining composition

`3742..3747` reads/tests `LevelSpecialGraphicsSetByte`. A nonzero byte calls
`SetupSpecialGraphicsResource`, then jumps to `376A`; zero enters the terrain
loop at `374F`. Keep UNKNOWN `374E` unresolved. The native terrain stream's
sentinel continuation is inside this caller, not an outer return.

`376A..3775` already has a connected object-state core: graphics copy, steel
cells, object interaction cells and coordinate collection. `3776` then calls
the tail `36AD -> 4DF8`. That tail has no extra internal CALL frame: it sets
DI=`CC40`, CX=`0340` and jumps to the clear helper, whose RET consumes the
`3779` frame. Compose logical cores and live stack effects rather than routing
through a register adapter or adding an invented return frame.

`3779` loads CX=13. Each iteration pushes CX, calls `UpdateMinimapColumn` at
`377D`, then restores the actual SS word before LOOP at `3781`. The column's
live DS/ES/provider and IRQ seams remain inherited; a cached host loop counter
would lose stack aliases. Finally `3783..3786` reads live `LevelGraphicsSegment`
and publishes `GraphicsResourceSegment`, then executes its own near RET.

The four-call object-state span now also has a separately verified bus variant
with113 cases. The finishing tail3776..3789 composes the live clear return,
nominal thirteen minimap calls, returnedDS graphics publication and ownRET in
22 cases/133 integrated sites, including aliases that finish after one column.
See level-initialize-bus-frontier.md and level-finish.md. The full caller now
connects these children with its initial drawing CALL, header fallthrough and
special/terrain selector, retaining all child/provider/alias seams. Its36-case
gate and the separate complete terrain-stream gate must remain fresh.
See [level-redraw.md](level-redraw.md), [interaction-cells.md](interaction-cells.md),
[level-drawing.md](level-drawing.md) and [minimap.md](minimap.md).
