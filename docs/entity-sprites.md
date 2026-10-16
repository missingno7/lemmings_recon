# Entity sprite sources and callback leaves

These are entity descriptors in the unchecked DS:0088 array with a 2Dh record
stride. They are distinct from the 1Ch object records at DS:17CB. The callbacks
receive live registers and canonical segmented memory; they own no host copy of
the entity, source graphics, masks or save frame. Executing code must remain
intact and TF clear in the bounded native domain. Device and IRQ timing remain
separate platform obligations.

## Source ownership

The allocation path at 1007 requests 5571h paragraphs and publishes the returned
segment at GraphicsResourceSegment (1FE4). At 1019 it publishes that segment plus
1000h, with 16-bit wrap, as EntitySpriteBufferSegment (1FE6). At 101F it publishes
another 1D0Ch paragraphs as GeneratedGraphicsBufferSegment (1FE8). These are
coordinates; the arithmetic alone proves neither allocation success nor an
initialized or bounded sub-buffer.

The transform at 59BB selects ES from the live 1FE6 word and DS from the live
GraphicsResourceSegment, then sets SI and DI to zero. It invokes 5B11, 5BB0 and
5C06. With DF clear, disjoint source/destination/code/stack, intact saves and
normal child returns, its fifteen groups read 50F0h source bytes and emit 180B8h
bytes. The final 5C06 call reads another 180h bytes and emits 1400h bytes. The
resulting source end is 5270h and output end is 194B8h. That output ends 3C08h
bytes before the nominal 1FE8 base. This is static normal-path arithmetic, not
proof of resource length, initialized lifetime or the complete provider domain.

For 5B11, DH is the number of source bitplanes and DL is the row count. Each
alignment emits three bytes per plane/row and three bytes per row formed by
OR-reducing those planes. Eight alignments therefore emit
`24 * DL * (DH + 1)` bytes. With DX=020Ah, each bank is 90 decimal bytes:
two ten-row data planes followed by ten three-byte mask rows; all eight banks
occupy 720 bytes. Source words are read as two explicitly ordered bytes, then
extended to three output bytes by the original shift chain.

5BB0 emits one unshifted bank: `2 * DL * (DH + 1)` bytes. It copies DH planes
with REP MOVSW, then OR-reduces them into one word mask per row. DX=020Ch/020Dh
therefore produces 72/78 bytes, with two 12/13-row word planes followed by word
masks. These formats explain the separate DS:SI data and DS:BX mask cursors.
The renderer itself imposes no allocation bounds on either cursor.

The 706F caller adds +29 to the byte +28 selector unless byte +27 equals one.
If +2A differs from FFh, it multiplies that byte by eight and adds alignment.
The full product with the live +10 stride supplies a paragraph offset plus +0C;
adding the live 1FE6 segment supplies CX. The low product nibble plus +0A
supplies SI; adding +12 supplies BX. Direct state setters
rewrite these mutable descriptor fields and +14 callback pointers. The target
at 715B is the actual SS word saved at 70F0 and POPped at 7159. The known nine
initialized callback slots do not close arbitrary copies, indexed writes or
aliases. The existing callback inventory is in entity-display.md.

## Aligned callback 6170..64D8

This 873-byte, 478-site leaf has no guest branches. PUSH DS precedes five ordered
SS mirror/OUT pairs: map mask 0Fh, set/reset zero, enable-set/reset 0Eh, mode zero
and rotate zero. Only then does DS become incoming CX; ES becomes A000h and BP
saves incoming DI. The body spells out ten masked rows and ten second-plane
rows. C may group those identical instruction sequences in fixed host loops;
neither count depends on CX or a stack word.

Each first-pass row reads a mask word at live DS:BX and performs two INC BX
instructions. Its low byte selects the first bit mask. CLI, a destination latch
read, LODSW, STOSB and STI follow. XCHG CH,AH exchanges the held second mask byte
and the loaded data high byte; it does not reread either from memory. The second
masked write then emits CH. A separate live byte read at DS:BX supplies the
third mask, followed by INC BX, a latch read, LODSB and STOSB. Each pixel has its
own CLI/STI phase. ADD DI,29h ends every row.

DI is then reset from BP. Ordered mirror/OUT pairs disable set/reset except
plane zero, select GC3 data10h (logical OR), set bit mask FFh and map mask 02h.
Ten rows read a latch before each of three writes from LODSW/high byte/LODSB.
CLI covers each whole row; STI and literal ADD DI,29h finish it. POP DS reads the
real saved word before RET 64D8. The core stops before RET; the adapter consumes
the actual live SS:SP word.

LODS and STOS follow DF. BX advances forward independently. Row stride is 44
bytes with DF clear and 38 with DF set. A VGA-backed source read can replace the
destination latches before a write, so plane expectations must follow bus order.
SS mirrors can change the saved DS or outer return word. Final arithmetic flags
come from the last ADD; IF is set and DF is preserved.

## Shifted callbacks 64D9..65D7 and 65D8..66D6

Each sibling is 255 bytes/126 sites, with an independent return and 12 or 13 rows.
PUSH DS is followed by DS=CX and XCHG DX,CX. Incoming DL is therefore the
unchecked CL shift count. VGA setup matches the aligned callback. DI is saved
on the real stack before the first pass.

Every masked row PUSHes BP, LODSWs a data word, PUSHes SI, byte-swaps that data
into SI, then reads and byte-swaps a live DS:BX mask word into BP. ADD BX,2 stays
forward even with DF set. CH=CL controls repeated one-bit SHR/RCR operations
that extend each word into three bytes; all 256 shift counts remain valid direct
inputs. The byte loop has no x86-style masked multi-bit shift count.

The row PUSHes BX/CX, emits three mask/CLI/latch/STOSB/STI groups, adds 29h to DI,
then POPs actual CX/BX/SI/BP. DEC BP controls the next row. A changed saved count
or cursor takes effect; there is no fixed host-row cap on this first pass. The
actual saved DI is POPped before the second-plane OR setup. That pass loads its
own 12/13-row BP count, shifts each source word into three bytes and writes the
OR plane under a row-wide CLI/STI phase. Final POP DS and RET remain live.

The normal destination stride is again 44 forward or 38 backward. Each word's
high byte is accessed at physical address +1 with 20-bit wrap, while subsequent
SI/BX/DI/SP changes retain their own 16-bit wrapping. The caller's segments,
FLAGS and actual near-return frames are part of the contract.

## Scoped verification

The aligned native gate passes 42 fixtures at both APIs: all 478 sites, no guest
branch edges, 27,888 ordered byte-bus events, 20,160 independent plane-byte
checks and ten completed mutants. Eight fixtures consume the unchanged 90-byte
banks produced by one bounded original 5B11 call. Its 720 output bytes match an
independent 24-bit shift/OR model; its 74 sites, 7,608 instructions and 2,065
memory transactions are recorded separately from the consumer totals.

The shifted native gate passes 66 entry fixtures at both APIs: all 252 sites
and 24 jump outcomes, 74,092 byte-bus events, 19,200 plane-byte checks and ten
completed mutants. The two original 5BB0 calls independently verify all 72/78
output bytes and feed the corresponding sibling at shifts zero/seven. Their
356/383 instructions and 163/176 memory transactions are counted once each and
remain separate. Source bytes are checked unchanged after each native handoff.

Another 512 original-only prefix probes stop after the first shift loop at6538
or6637. They verify all 256 unchecked shift bytes at each entry, including the
held data/mask words, spill bytes, actual saved SI and instruction-defined FLAGS.
Their 411,136 instructions and 13,824 events do not add native comparisons or
translated bytes. The separate original report records this arithmetic scope.

The three disjoint callbacks add 1,383 main C bytes, taking the ledger union
from19,322 to20,705. The 5B11/5BB0 producers' 245 code bytes remain untranslated.
Reports are build/entity-sprite-aligned-differential.json,
build/entity-sprite-shifted-differential.json and
build/entity-sprite-shifted-original-differential.json. Only their exact scopes
and matching input hashes establish acceptance. They do not accept the six
remaining callbacks, the full59BB transform,715B target closure,3634 record loop,
device timing or complete gameplay. Next examine66D7 with fresh graph views.
