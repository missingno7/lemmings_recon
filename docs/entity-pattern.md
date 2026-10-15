# Live entity interaction pattern

`CopyEntityPatternToInteractionMap` at 283B..287C is a 66-byte, 37-site
leaf. Calls at 2383 and 2835 belong to the normal simulation body at 1F19.
The former is guarded by record word +8 bit 0100h. The latter follows a
state transition that clears words +8/+A/+C and resets several drawing fields.
These observations do not establish complete simulation-state semantics.

The simulation advances its live DS:SI records by 2Dh at 1FEC. The producer
at 3464..34C7 saves nine old interaction cells into record offsets 16h..1Eh,
while writing three rows of 02h, 0Ah, 03h into the SS-backed interaction map.
With DF clear, its source advances three cells then 019Dh, giving the map's
416-cell row stride. Its explicit INC SI differs from its DF-sensitive STOSB;
DF set does not produce the same forward saved pattern. No general DF-clear
precondition is assumed for the leaf. The creation path at 30C9..314B selects
DS:0088 + an unchecked byte index times 2Dh, explicitly clears 45 bytes, then
writes coordinates and other fields; the pattern therefore starts cleared on
that path. The array extent, other indexed writers, cloning and broader
activation ownership remain unresolved. Creation and the containing
producer/consumer parents remain separate translation work.

The leaf first reads X and Y words from DS:SI/+2. It wraps the subtractions
X-4 and Y-6-10h to 16 bits before two logical single-bit shifts each. It saves
the shifted X and incoming DX on the live stack, multiplies shifted Y by
01A0h, restores DX and pops shifted X into BX, then adds the low product and
0012h. There is no clipping, signed division or validation of coordinates.

It saves SI, DI and ES in live SS memory, selects ES through PUSH SS/POP ES,
and copies three MOVSW/MOVSB pairs from live DS:SI+16h to ES:BX. Each pair
is followed, except the last, by literal ADD DI,019Dh. Word reads complete
before their writes; later reads observe earlier writes. DF controls both
string cursors. In the backward case the row start advances 410, and source
word/byte accesses overlap; this is not a reversed nine-byte block copy.

Map writes may overwrite the saved SI/DI/ES words and the near return word.
The core returns at the boundary before RET; the adapter then reads the live
SS:SP return word. AX retains the low product, BX the computed map offset,
and DX its popped save. CX, BP, DS and SS are unchanged. Final arithmetic
flags come from the second ADD DI,019Dh at 2873; control flags are preserved.
Offsets and SP wrap at 16 bits; a word's high byte uses physical address+1,
with 20-bit physical wrapping, rather than rewrapping its segment offset.

`c/entity_pattern.c` keeps coordinates and saved cells in the canonical memory
image and exposes a logical core plus an oracle register adapter. Its declared
domain is ordinary RAM, intact executing code and quiescent interrupts with TF
clear. Device memory, provider side effects, executing-code aliases and complete
parent reachability are outside this leaf's C acceptance. No new code/data
classification or whole-game acceptance follows from translating it.

The focused `tools/difftest.py entity_pattern` gate passes 37 fixtures at both
boundaries, comparing all registers, final defined flags and the complete 1 MiB
RAM image. All 37 original sites execute; this leaf has no branch edges. Cases
cover coordinate underflow, low-product/offset/physical wrapping, both DF states,
sequential source/destination overlap, coordinates read before stack writes,
source/save aliases, overwritten saved ES/DI/SI and live return words. A separate
known-answer case checks the nine forward row positions. Four completed mutants
exercise signed shifts, row adjustment, ignored DF and prefetched RET.

Each worker has a 180-second deadline and 384 MiB process commit limit (640 MiB
tree); each original call has a 100-instruction bound. Native calls have a fixed
three-row body with no callbacks. Timeout or budget exhaustion fails the gate
and cannot count as mutant detection. DLLs live in an owned temporary directory
removed after the worker exits, including failed runs. Evidence is retained in
build/entity-pattern-differential.json with input hashes; acceptance is scoped
to this RAM leaf, separately from aggregate coverage and parent readiness.
