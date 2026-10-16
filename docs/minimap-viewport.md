# Minimap viewport outline and status prefix

DrawMinimapViewport7A5A..7BB7 owns350 known bytes/168 instruction sites.
It has five conditional branches (ten outcomes), no CALLs or UNKNOWN bytes,
and one nearRET at7BB7. Its maintained physical module is minimap_viewport.asm;
game_code_late_tail.asm now starts at7BB8. Names and continuations belong to
the symbol ledger. The refactor preserves every original byte/classification.

The first live word read at DS:0000 owns destination DI:
`((word >> 7) + 2174h + live DrawingOrigin) & FFFFh`.
The seven SHR instructions are unsigned. After programming the initial VGA
registers through live SS mirrors and OUTs, the routine rereads DS:0000 and
uses `(word >> 4) & 7` as the first shift count. The two reads can differ,
including when SS mirror0000 aliases the DS word. No viewport snapshot or
cached phase belongs to the original contract.

The first masks are CX=FFFF/BX=FF00. Each shift is SHR CX,1 then RCR BX,1,
with the resulting CF preserved by DEC AL. The full AX phase word is pushed
on the real SS stack before this shift loop. Four mask bytes CH/CL/BH/BL
control the top and bottom raster bands. Each byte writes the live SS bit-mask
mirror before OUT3CE, clears IF, reads the current ES:DI to load latches,
then STOSB writes the mask byte and advances DI according to DF. STI follows
each pair unconditionally. The second through fourth reads of these two
bands target AH, preserving their residual value until it is overwritten.

After the first four STOSB operations DI adds0340; after the second four it
subtracts0030. CX/BX become8000/0100, and POP AX rereads the real saved word.
AND AX,AX determines whether the side-mask shift loop starts; DEC AL determines
when it ends. A changed high byte with low byte zero therefore runs256 shifts.
The popped value is not reduced to the original0..7 domain. SS bit-mask mirror
writes can themselves overwrite that save. Subsequent drawing repeats four
mask bytes for18 iterations, subtracting0030 after each four STOSB operations.
Unlike the horizontal-band reads, all side-band latch reads target AL.

With DF clear and ordinary live state this is a24-pixel-wide,20-row outline:
top row0, bottom row19 and sides descending18..1 at44 bytes per row. Exactly
80 ordered read/STOSB pairs occur. DF set reverses only string movement;
the literal0340 and0030 adjustments retain their values. No corrected stride
or rectangle buffer may replace that behavior.

DS, SS, CS and SI remain unchanged locally. ES returnsA000; BP becomes zero;
DX returns3CE. AX/BX/CX/DI and flags retain actual arithmetic and latch-read
residuals. Every memory/port callback observes instruction-entry defined flags,
including CLI/STI phases. SHR/RCR by one have their defined OF behavior;
logic leaves AF undefined. The final DEC BP defines PF/AF/ZF/SF/OF while CF
comes from the preceding SUB DI,30. The logical core stops before RET; the
adapter fetches the actual post-write SS:SP word with20-bit physical wrapping.

UpdateStatusDisplay at3AC8 first CALLs UpdateMinimapColumn796F, returning
3ACB, then CALLs DrawMinimapViewport7A5A, returning3ACE. The scoped two-call
prefix owns only six bytes. It carries all returned registers and live DS/ES/SS
into the next child and uses actual near-CALL words in canonical memory.
An explicit child boundary must propagate before fetching any outer RET;
a changed nested return may numerically equal an outer continuation. Changed
outer returns also stop at their actual target. READY at3ACE stops before the
separately implemented status body; the prefix adapter has no outer RET.
A shared VGA bus with word-port output is required by the existing column
child. The viewport's RAM/no-op-port fallback only supports constructed leaf
calls and is not a VGA backend. Real device timing and IRQ delivery remain open.

Scoped native acceptance passes46 viewport fixtures at core/actual-RET adapter
boundaries:168 sites,ten branch outcomes,39,192 ordered bus events and nine
completed mutants. Independent replay checks all80 raster cells. The prefix
passes12 fixtures at both boundaries:two owned CALL sites,266 integrated sites,
54,782 events and five completed mutants, including actual changed nested/outer
returns and a live POP DS value passed into the viewport. Reports are
build/minimap-viewport-differential.json and build/minimap-status-differential.json;
their recorded input hashes own acceptance. These scopes add350+6 unique main
bytes. The3ACE suffix and complete3AC8 caller now have separate native gates;
see status-display.md. This prefix API retains its six-byte scope.
