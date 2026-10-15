# Selected level resources in native C

LoadSelectedLevelResources occupies CS:197D..1A7A. Its 253 translated instruction
bytes exclude the skipped UNKNOWN byte at 1A2F. The core in c/resource_select.c
calls the native decimal, raw-file, file/cache and DAT decoder cores directly.
The register carrier is confined to the comparison adapter. Logical call/result
fields describe transient execution state; game data stays in canonical memory.

The unchecked selection byte DS:1F6B indexes order bytes at DS:54EE. Decrement
wraps in a byte, so zero becomes FF. The high nibble chooses the LEVEL filename
group, bits 1..3 choose section 0..7, and bit 0 chooses an odd override. No table
extent or valid producer domain has been proved. The decimal helper writes the
three filename digits at DS:2551 and leaves its original AX/SI/flag effects.

The first section and each skipped section decode in place at DS:0FCB, replacing
the 2,048-byte loaded record. The section counter and decremented order word are
saved in live stack memory; provider writes can change either before its POP.
The decoder's original overlap behavior is retained: a constructed compressed
prefix must stay behind expanding output to yield its static decoded bytes.
There is no separate record or decompression buffer introduced by the port.

Odd selection reads at most 1180h bytes into DS:5566, then uses only the popped
AL, shifted right one and multiplied by 56. Incoming AH is discarded by MUL DH.
Twelve words replace the record header and sixteen words replace its footer at
DS:17AB. REP MOVSW follows the returned DF, wraps cursors in 16 bits and accesses
word bytes physically contiguously. The selected slice is not bounds checked.

Record bytes DS:0FE6/0FE8 select ground and normal/special graphics. The ground
read requests 1000h bytes at DS:1B4B, although supplied ground files contain only
1,056 bytes. Short reads leave stale bytes; longer reads can overwrite adjacent
state or saved stack words. The returned live DS/ES are retained. Tests include
a ground read changing saved DS to another configured frame, which determines
the subsequent graphics filename and segment pointers.

Normal selection loads the first VGAGR section at input-segment:0010 and the
second at level-graphics-segment:0000. Nonzero special selection loads only the
first VGASPEC section at input-segment:0010. Selector additions wrap in a byte:
a nonzero special value can produce a NUL filename digit without changing the
already selected branch. Partial AH=3Eh writes retain AL for close calls.
The level and final graphics closes ignore carry; raw-file closes retain their
original fatal behavior. Every saved word and call continuation is written to
the original stack, preserving residue, aliases and distinct error frames.

tests/resource_select.py runs 59 bounded integrated cases against original
instructions, comparing full RAM, all registers, defined flags and ordered DOS
requests. All 108 caller sites and nine branch edges execute. Cases cover every
section with and without overrides, zero/order-domain probes, direct/cache paths,
retry and fatal exits, DF, offset/stack wrap, wrapped filename digits, accepted
ground sizes, stack-offset underflow and overwritten saved counter/order/DS words.
Nine paired original selections cover distinct graphics/special combinations,
and a tenth explicitly verifies a supplied odd-table override read. Forward record
and override bytes also have independent expected checks. Three compiled mutants
clamp a zero order byte, restore an overwritten DS, or reject ignored close carry;
all are detected. Dependencies compile without their separate mutations.

The original comparison is confined to identified routine intervals, with a
ten-million-instruction budget per case and a 120-second suite process limit.
DOS providers and the rendering/input retry callee at 4B1C remain declared seams.
The historical result API stops fatal transfers at 1949/04D0 with live frames
and requires intact immediate child returns. The new execution API reports the
actual consumed child target; the full RAM connection directly composes the
verified printer/cleanup bodies. See resource-select-full.md for its separate
gate, twelve-field input and both normal return boundaries. Internal DAT callee
returns and instruction bytes remain intact in this domain. IRQ delivery is
quiescent. Actual DOS/provider behavior, order
producer bounds, allocation and the 36B6/378A/394F object/terrain consumers remain
open. This caller does not complete native startup or the game.
