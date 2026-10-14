# Native SS interaction cells and the object-setup span

WriteObjectInteractionCells occupies 37C2..3838 (119 bytes, 54 instruction sites).
WriteSteelInteractionCells occupies 3839..389E (102 bytes, 47 sites). Both are
closed leaves with no callees. They write directly to the caller's live SS memory,
which also contains the stack and VGA-register mirrors. InteractionCellMapBase
names offset 0012 in the initial runtime SS frame; it supplies an offset, not an
allocation, initialized buffer or assumption that SS remains that initial frame.

The object routine visits only the first 16 big-endian eight-byte definitions.
It multiplies the unchecked type word by 28 and computes the template cursor
before testing the X word for zero. Thus inactive definitions still expose the
product high word in DX and the wrapped source in SI. An all-inactive call also
retains incoming BX. Active definitions use little-endian template X/Y offsets,
width/height bytes and a kind byte. See object-records.md for the address formula.
The cell value ORs the kind into the low byte of the ordinal shifted four.

The row saves are original SS words: PUSH DX, PUSH BX, explicit byte stores,
POP BX, POP DX. Copies of the save values cannot replace those reads. A cell
write can change the next row base or dimensions, alter later input when DS/SS
alias, or overwrite a return word. Width and height decrement in bytes; zero
means 256 iterations. One constructed zero-by-zero case completes 65,536 writes
while leaving its stack words in an untouched gap. No zero-size rejection or
production loop budget is introduced. Final flags come from DEC CX, retaining
CF from the preceding ADD DI,8; BP becomes 16 and DI becomes 106B.

The steel routine visits all 32 packed four-byte definitions at DS:172B. It
skips only if both big-endian words are zero, so byte3 alone activates a record.
X combines byte0 shifted one with byte1 bit7; the row is byte1's low seven bits.
The two nibbles of byte2 produce widths/heights 1..16. The original dimension
save is popped before ADD DX,0101, so a corrupted save can leave those normal
dimension bounds. Rows write byte 9 and retain the same live save behavior.
The final ADD DI,4 defines arithmetic flags; LOOP does not change them. DI is
17AB and CX is zero. DF does not reverse either routine's explicit byte stores.

All word stack accesses are physically contiguous at offset FFFF, while cursor
arithmetic wraps in 16 bits and physical addresses wrap in 20 bits. Neither leaf
consumes its caller RET in its core; the oracle adapter rereads that live word
after all stores. Executing instruction bytes remain intact in the tested domain.

## Connected four-call span

PrepareLevelObjectState is the identified 12-byte span at 376A..3775 inside 36B6.
c/object_state.c directly calls the native graphics-record copy, steel-cell writer,
object-cell writer and coordinate collector in original order. Each call writes
its original near return word, at 376D, 3770, 3773 or 3776. All register effects
flow through logical transient results on one canonical memory image.

After each leaf, the span reads and consumes the live near return word. If it
matches the expected continuation, composition proceeds. If it changed, the
result exposes the actual target and state before executing target code. The
comparison oracle stops at the same transfer boundary, even if that target lies
inside other identified code. No return correction or arbitrary native dispatch
substitutes for the original target. The normal boundary is 3776, before the
untranslated 36AD call. The outer 36B6 return word remains unconsumed.

This is a native setup fragment, not a complete translation of 36B6 or 394F.
Rendering, VGA ownership, the far drawing routine and broader callers remain open.

## Verification

tests/object_cells.py passes 123 original-versus-C cases, covering all 54 sites
and nine branch edges. Cases include all ordinals, only-first-16 behavior, kind
upper bits, big/little-endian fields, unchecked types, wrapped coordinates,
dimensions 0/1/255, 65,536 writes, saved-row and input aliases, overwritten RET,
stack and physical wrap, IF/DF and all 80 supplied LEVEL/ground pairs. A controlled
row-save alias ends with BX=7C32 and DX=F200; another exposes target FF5A.

tests/steel_cells.py passes 386 cases, all 47 sites and eight edges. It covers
all 32 positions, all 256 packed dimension bytes, byte3-only activation, X bit7,
FFFF coordinates, live row-save and input changes, stack/return aliases, IF/DF,
offset/physical wrap and all 80 LEVEL steel spans. Independent cell footprints
also check untouched bytes. Each leaf detects three compiled mutants.

tests/object_state.py passes 105 cases with four caller and 194 integrated sites,
and all 33 integrated edges. All 80 LEVEL/ground pairs are included. Independent
graphics/coordinate results and the full SS window agree; only the eight bytes
below the outer SP are excluded from the independent SS expectation because they
are original call/save residues. The complete 1 MiB RAM still compares against ASM.
Constructed cases check overwrite order, upper objects, DF, stack and physical
wrap, plus changed returns after each of the four different callees. Three
compiled mutants detect the wrong SS, wrong returned match count and ignored
return corruption. Dependency mutation macros remain disabled in this suite.

All suites compare full RAM, all boundary registers and defined final flags.
Only AF after the zero-match coordinate collector's final AND is undefined and
excluded. Original execution stays within identified bytes, stopping after RET
or at the declared span boundary. Process limits are 120 seconds per suite;
per-case original instruction budgets are recorded by each test. TF is clear,
interrupt delivery is quiescent and arbitrary corrupted dimensions may produce
unbounded loops outside these finite fixtures. No original game was booted.

Next close the VGA-clear/layout dependencies at 4DF8/8808 and their 368E/36AD
callers, then the remaining terrain/far drawing and minimap dependencies of
36B6/394F. Static byte/data/CFG and asynchronous alias obligations remain open.
