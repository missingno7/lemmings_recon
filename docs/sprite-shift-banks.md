# Three-byte shifted sprite banks

`GenerateThreeByteSpriteBanks` at 5B11..5BAF is a 159-byte leaf with 74 sites.
For ordinary nonzero DH/DL, it generates eight banks. Each bank contains DH
planes of DL three-byte rows, followed by DL three-byte OR-mask rows. The source
pair is big endian; a 24-bit right shift of `(first<<16)|(second<<8)` produces
the three output bytes. Masks reread live ES, with plane pitch 3*DL.

Every cursor adjustment is explicit arithmetic. DF survives without reversing
source, destination or mask traversal. Separate byte operands wrap offsets at
16 bits; actual SS word accesses instead advance physical addresses by one,
with 20-bit wrap. Source, destination and saved words may alias.

Entry clears CL. Each bank pushes CX and SI; each plane additionally pushes CX.
The byte CH loops are do-while loops: zero DH means 256 planes, zero DL means
256 source and mask rows. AH:AL:BL shifts through SHR/RCR/RCR; BH counts the
one-bit steps. The mask pushes SI, CX and DX. Pitch uses DL before POP DX;
the restored actual DX owns subsequent masks and banks. All saved counts and
cursors are reread from canonical SS memory. The outer POP CX, INC CL and
CMP CL,8 determine subsequent shifts and termination, including provider edits.

After the final bank, signed DI below 0010h skips normalization. Otherwise
ES adds DI>>4 with wrap, DI keeps its low nibble and CX receives the old ES.
The core stops before RET 5BAF; the adapter consumes the actual caller word.
No child calls or platform instructions occur in the leaf.

Focused native acceptance covers 40 fixtures at both APIs: 80 comparisons,
all 74 sites and 17 branch outcomes, 236,282 ordered events and ten completed
mutants. Separate output equations check 56,016 bytes, including complete
eight-bank zero-DH and zero-DL cases. Providers also drive a full 255-bit
shift and the outer CL wrap; VGA stack words remain on the live bus. The
combined DX=0000 work is described by the literal loops but is outside this
retained fixture campaign.

One native producer hands all eight unchanged 90-byte banks into the native
aligned drawing callback through canonical RAM and constructed CALL words.
The nine phase comparisons include 2,610 producer and 2,664 consumer events.
Consumer sites/events remain separate from the 159-byte leaf acceptance;
this does not execute the 59BB caller. Returned DS/ES/FLAGS remain live.

Run `tools/difftest.py sprite_shift_banks` or
`tests/sprite_shift_banks.py --original-only`. Limits are 420 seconds/384 MiB
per process, 1,000,000 original hook steps and 180,000 bus events per invocation.
The largest retained case completes in 115,605 original steps and 47,202 events.
Exhaustion fails verification and cannot count as a completed mutant.
Reports record exact input hashes; retained reports do not establish current
acceptance after input changes. The sibling 5C06 is also verified; next connect the shared 59BB caller.
