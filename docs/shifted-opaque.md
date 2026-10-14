# Shifted opaque planar body

`PlanarShiftedOpaqueBody` now has an independent C11 core and a far-return
adapter. The core covers `916B..939C`; the unchanged `RETF` at `939D` is read
from the caller's live `SS:SP` by the adapter. The physical range
`916B..939D` is 563 bytes (`800ff83a0fabbcdc59b73266c332f720636d45d26daba6bbd371cca3b360849a`),
of which 562 decode. The range has 317 known instruction sites, including
`RETF`; the C body translates all 316 core sites and 561 instruction bytes.
`UNKNOWN 9339` remains unresolved and outside execution. The fresh graph has
one discovered incoming edge, `916A -> 916B`, and no calls or outgoing direct
edges from the body.

The public logical input and output are `LmnShiftedOpaqueCall` and
`LmnShiftedOpaqueResult` in [shifted_opaque.h](../c/shifted_opaque.h). Inputs
carry incoming DS, relocated game-data DS, live stack SS:SP, packed CX/DX,
source and destination cursors, and flags. Results return AX/BX/CX/DX/SI/DI/BP,
SP, DS/ES, and flags. The core accepts one 1 MiB memory image and the explicit
raster bus. The adapter takes and returns `LmnRegs`; no shadow RAM or core
register packet is introduced.

At entry, the decrement of `DS:6704` uses incoming DS. The next push saves that
DS, and `DS:1FE4` supplies the graphics-resource segment. The relocated
`MOV AX,09A9` establishes initial ES from the call's game-data segment. Row
copies then use live DS/ES values restored from the memory-backed stack. All
SS pushes, pops, mirror stores, 16-bit stack wrap, 16-bit cursor arithmetic,
and 20-bit physical address wrap operate on the same RAM image.

The first plane copies `CL` source bytes into `ES:6706` and fills `ES:6748`
with `FF` bytes; each copy's zero sentinel follows DF as well. The source
scratch is shifted first with SHR followed by the forward RCR/INC/LOOP carry
chain. Mask shifting then samples live `DS:A948` again, so source writes and
stack aliases can change the number of mask passes. The first-plane drawing
count is `INC CL`; each byte reads the VGA latch, emits its live mask through
`OUT DX,AX`, and writes the shifted source. That `OUT` at `921E` has no SS
bit-mask mirror store. Later planes do not initialize, shift, or consume the
mask. They use OR-mode VGA writes and add the live `ES:66F8` plane extent to SI.
The second plane sets OR mode and `FF` bit mask; the third and fourth only
change the Sequencer map mask. The fourth plane is the shared tail: it has no
outer DI/SI/CX save/pop and no further BP decrement or test.

The standalone suite, [shifted_opaque.py](../tests/shifted_opaque.py), runs the
loaded original and native core through `run_bounded` with a 180-second
timeout, a 512 MiB process limit (768 MiB job-tree limit), and an automatically
removed temporary build directory. It completed 29 constructed cases,
observed all 316 core sites and 46 direct branch edges, and detected all three
compiled mutants. Two cases also executed the original unchanged `RETF` after
removing Unicorn hooks and the translated block cache. Those isolated RETF
probes exclude device-backed stacks, stack aliases, and 16-bit SP wrap because
the unhooked Unicorn return cannot reproduce the bus-backed stack reads.

The differential cases compare the full 1 MiB RAM image, all registers,
defined flags, ordered whole-bus digest, and four-plane VGA state. Independent
packed-bit expectations check source/mask shifts and final plane contents for
the four-plane shift-1-through-7 fixtures. Other cases cover all plane-limit
control shapes (`1..5`, zero, and `FF`), multiple rows, DF, distinct incoming
and relocated DS, source/scratch overlap, live SS aliases of the shift byte and
row fields, stack writes in the VGA aperture, physical and cursor wrap, shift
zero, zero CL/CH, and `CL=FF`.

The zero-CL case executes the original 65,536-iteration source and mask RCR
loops. Its constructed forward DS span makes the first source pass inject one
carry into the live shift byte, then seven more shifts reduce that byte from
eight to one. The second live read therefore takes one finite mask pass. This
fixture selects memory contents; the C core retains the original wrap and live
read behavior. The shift-zero case executes all 256 outer shift passes, the
zero-CH case executes 256 rows, and `CL=FF` executes all 65,536 drawing
iterations. These are completed finite paths rather than reduced loop counts.

The three regression mutants discard an incoming RCR carry, reuse the source
shift count instead of rereading `DS:A948`, or omit the live `ES:66F8` source
plane advance. The implementation depends on `special_blit.h` for the raster
bus and `lemmings_sym.h` for ledger-owned offsets; the verifier uses the loaded
executable, `dat_io.py`, `minimap_vga.py`, `cbuild.py`, and
`bounded_process.py`. IRQs remain quiescent. The standalone tests establish
this bounded constructed domain; indirect or modified-code entries, hardware
timing, asynchronous IRQ ownership, and the higher renderer contract remain
open.
