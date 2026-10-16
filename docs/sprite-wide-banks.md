# Five-byte shifted sprite banks

`GenerateFiveByteSpriteBanks` at 5C06..5CC0 is a 187-byte leaf with 80 sites.
On intact saved words it emits eight 640-byte banks. Each contains three
32-row planes with five bytes per row, followed by a 160-byte OR mask.
The four source bytes form a big-endian 32-bit value extended with a zero byte;
SHR BP/RCR DX/RCR BL performs a 40-bit right shift for alignments zero to seven.

Entry pushes CX, SI and DI. After the planes, POP SI consumes actual saved DI
as the mask source. The later POP SI consumes the saved original source cursor.
Mask rows push SI and CX, use BH=3 samples with pitch 00A0h, and write
AH/AL/CH/CL/DH in order. Actual saved plane and mask CX, mask SI and outer CX
remain authoritative. Outer INC CL/CMP CL,8 determines subsequent shifts and
termination, including aliases and provider changes.

Every byte operand has its own wrapped 16-bit effective address. SS word high
bytes advance the physical address by one with 20-bit wrap. No string operations
occur, so DF survives without changing traversal. Source, destination, masks
and saves share canonical memory. Final signed DI below 0010h skips folding;
otherwise ES adds DI>>4, DI keeps its low nibble and CX receives old ES.
The core stops before RET 5CC0; its adapter consumes the actual caller word.

Focused native acceptance covers 33 fixtures at both APIs: 66 comparisons,
all 80 sites and 17 branch outcomes, 913,554 ordered events and ten completed
mutants. Independent 40-bit equations check 20,480 output bytes across two
full eight-bank inputs at both boundaries. Cases include exact/forward/backward
overlap, every byte position crossing FFFF, physical-top source/stack wrap,
VGA DS/ES/SS, exact signed-fold thresholds, saved DI/SI/CX providers, actual
output-to-save/RET aliases and a full CL=FF shift count.

One actual native producer feeds all eight 640-byte banks into the native wide
drawing callback through the same RAM object. Nine phase comparisons preserve
the full 5,120-byte output hash. Explicit child CALL words and returned segment
and flag roles remain live. The 14,274 producer events and 20,000 consumer
events are separate from the leaf campaign above. The existing consumer's
289 bytes/147 sites/seven edges are not added again to translated coverage.
This is a data handoff with constructed calls; it does not execute 59BB.

Run `tools/difftest.py sprite_wide_banks` or
`tests/sprite_wide_banks.py --original-only`. Limits are 420 seconds/384 MiB
per process, 1,000,000 original hook steps and 180,000 events per invocation.
Exhaustion fails verification and cannot count as a completed mutant. Only
matching report scopes and input hashes establish acceptance. The three
producer leaves now share the maintained sprite_banks.asm physical module;
next connect the 59BB caller.
