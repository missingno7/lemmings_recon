# Planar drawing preparation

`PreparePlanarDrawingInputs` covers CS:882D..885D, 49 original bytes and 18
instruction sites. It begins after the original far-entry prologue at 8822 has
pushed AX,DX,CX and placed width >> 3 in AX. The C11 core receives logical inputs,
uses the same canonical memory as its native clipping and dirty-cell children,
and returns a continuation. Only its verification adapter uses `LmnRegs`.
The broader `DrawPlanarBitmap` entry remains UNTRANSLATED.

The prefix writes DS:66FA source pitch, clears CH, multiplies pitch by CL and
writes the low product to DS:66F8 source plane extent. It then pops CX,DX,AX
from their live SS saves before clearing DS:66FE vertical and 66FC horizontal
skips. The stores may overwrite pending prologue saves when DS and SS alias;
C rereads each word at the original point. MUL defines CF/OF; the remaining
arithmetic bits are representative until a later flag-setting instruction.

BP bits 000C select a direct native clipping call. After consuming its live
near-return word, the prefix tests AX's sign and exits to 88AB on rejection.
That far-return instruction is outside this C scope. DS:002A equal to FF then
selects the direct native dirty-cell call; other byte values skip it. Each child
return is read through live SS. A changed return exposes its actual target
before executing any target instruction. Normal preparation ends before 885E's
XCHG and the planar renderer body. The original outer far-return frame remains
live and unconsumed. See drawing-clip.md and drawing-dirty.md for child contracts.

Every word access reads or writes the low then high physical byte. Physical
addresses wrap at 20 bits; stack offsets wrap at 16 bits and the second byte is
physically contiguous even at offset FFFF. Optional raster callbacks and null-bus
RAM give identical results. This scope has no ports or VGA instructions, and
its tests use RAM callbacks. Device-mapped aliases, asynchronous IRQ delivery,
executing-code corruption and CPU-family segment-limit faults remain open.

The 102 differential cases first execute the seven original 8822 prologue sites,
then supply that exact memory/register/flag state to the C prefix. These seven
sites and 11 bytes are recorded separately and excluded from C coverage. Tests
compare the entire 1 MiB memory, all registers, defined flags and ordered byte
accesses. They cover all 18 prefix sites and 154 integrated sites, with 51 branch
edges. The child site unions include 73 clip sites and 63 dirty sites. The decoded
NOP 9996 remains unexecuted by these entry paths without a dead-code claim.

Cases cover clipping control combinations, negative and boundary coordinates,
zero dimensions, byte-rounded height, overflowing plane extent, DS/SS physical
wrap and SP 0000/0001/FFFF. Constructed aliases overwrite the pending saved
height, width and left words; overwrite DS:0026 during the dirty child's pushes;
change each byte of its near-return address; and fill its whole SS segment so
all seven restored registers and the return become 0101. Three compiled mutants
for skipping the dirty call, stale height restoration and discarded changed
return are detected. No guard or corrected input clamp is added to the cores.

## Original instruction and memory-hook flags

An independent two-instruction observation executes original MUL CX at 8832 and
MOV DS:66F8,AX at 8834 with AX=3, CX=8, DX=24. The product 24 has a zero high word,
so CF/OF must be clear. Unicorn 2.1.4 reports EFLAGS 0006 at the MOV instruction
boundary and after it, but 0807 inside its write hook. The memory word is 0018.
The report records the version and all observations, including whether that
transient discrepancy occurs; this probe adds no C case or coverage.

Ordered access comparisons therefore capture flags from the original instruction
boundary, including read/modify/write instruction entry flags. They check every
architecturally defined bit and exclude only undefined bits following MUL,
logical instructions or shifts. No C flags replace oracle flags and no defined
CF/OF mismatch is masked. The preparation core retains the hardware-defined
MUL behavior. Reproduce with tests/drawing_inputs.py; the report is
build/drawing-inputs-differential.json.
