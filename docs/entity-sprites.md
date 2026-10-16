# Entity sprite sources and callback leaves

These are entity descriptors in the unchecked DS:0088 array with a 2Dh record
stride. They are distinct from the 1Ch object records at DS:17CB. The callbacks
receive live registers and canonical segmented memory; they own no host copy of
the entity, source graphics, masks or save frame. Executing code must remain
intact and TF clear in the bounded native domain. Device and IRQ timing remain
separate platform obligations.

The enclosing706F descriptor arithmetic and live child frames are recorded in
entity-sprite-dispatch.md. Its named first-record anchors remain aliases in
canonical memory; they do not establish a converted or bounded record schema.

The complete 59BB transform now has scoped native acceptance with all three
bank helpers, including the pinned MAIN.DAT section-zero image. Its full output
layout and actual frame/segment contracts are in entity-sprite-banks.md.

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

The three-plane narrow entries use 5BB0 dimensions 030Ah/030Dh/030Eh/0310h:
80/104/112/128 bytes respectively, comprising three word planes and a word
mask per row. The four-plane entry uses 040Eh: 112 data bytes and 28 mask bytes,
140 bytes total. The original producer and consumer share these ordinary RAM
bytes directly; no graphics record conversion is required.

5C06 consumes three 32-row planes of four-byte source rows (180h bytes). For
each alignment 0..7 it shifts the 40-bit chain `[b0,b1,b2,b3,0]` right and emits
three 160-byte planes followed by their 160-byte OR mask. Its eight 640-byte
banks occupy 1400h bytes. During mask reduction, the first POP SI consumes the
saved destination DI; the later POP SI restores the source cursor. This is a
normal DF-clear, disjoint RAM contract rather than a bound on unchecked calls.

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

## Three- and four-plane narrow callbacks

66D7..6816, 6817..6956 and 6957..6A96 have 10/13/14 nominal rows and three
planes. The first pass uses the same masked three-byte shift sequence as 64D9;
the live saved BP controls its rows. Between passes, POP DI/PUSH DI preserves
the actual restored destination for the following plane. The second and third
passes use BP row counts and OR map masks 02h/04h. Each pass consumes its own
source words, and the mask cursor advances forward during the first pass.

6A97..6BDA has 16 nominal rows and three planes. 6CFC..6E82 has 14 nominal rows
and four planes. Both save the count with PUSH AX before every row and POP AX
before DEC AX, including each OR pass. BP remains the last first-pass spill
word, rather than a final zero count. The four-plane routine adds a live
POP DI/PUSH DI between planes two and three, then POP DI before map 08h.
These saves are executable state: stack aliases or providers can change the
number of rows, the next source word, the shift or a following plane's start.

All five retain the unchecked 0..255 shift byte, DF-sensitive strings, literal
29h destination increment and separate 16-bit cursor/20-bit physical wrapping.
The later third/fourth-plane setup uses MOV DX,3C4h; the second-plane setup
uses MOV DL,C4h. Final POP DS and the actual return word remain live.

## Wide callback 6BDB..6CFB

This three-plane callback starts CX at 32 and emits five bytes per row. Its
initial five OUTs precede their SS mirror writes. Later setup uses mirror
writes before OUT. DS becomes incoming CX after that initial setup; ES becomes
A000h, and BP holds the destination base for both subsequent OR planes.

Every row PUSHes CX and rereads its actual saved word. The first pass performs
DEC CX followed by JZ/JMP; subsequent passes use LOOP, preserving the flags
from ADD DI,27h. Each first-pass row reads two mask words and one mask byte,
advancing BX with five INCs, while source data uses two LODSWs and one LODSB.
The later OR passes use masks 02h/04h and perform a latch read before each of
their five writes. Source reads from VGA can replace those latches.

The destination row stride is 44 with DF clear and 34 with DF set. Counts are
live stack state, so 32 is an initialization rather than a host loop bound.
MOV DL,C4h preserves DH at each later map selection; final POP DS/RET consume
the actual SS words. The portable core stops immediately before 6CFB.

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

Those three disjoint callbacks added 1,383 main C bytes, taking the ledger union
from19,322 to20,705. The 5B11/5BB0 producers' 245 code bytes remain untranslated.
Reports are build/entity-sprite-aligned-differential.json,
build/entity-sprite-shifted-differential.json and
build/entity-sprite-shifted-original-differential.json. Only their exact scopes
and matching input hashes establish acceptance.

The five new narrow callbacks pass 44 fixtures at both APIs: 1,675 bytes, all
838 sites, all 96 branch outcomes, 68,400 ordered byte-bus events, 32,400
independent projected plane-byte checks and ten completed mutants. Per-entry
fixture counts are 11/10/7/8/8 for 3x10/3x13/3x14/3x16/4x14 respectively.
Five original 5BB0 calls verify all 80/104/112/128/140 output bytes and feed
unchanged source/mask banks at normal shifts 0/1/7/3/5. Their instruction and
memory-transaction totals are recorded separately. The accepted VGA-stack
witness uses a BP counter; ordinary-stack providers exercise live AX counts,
plane-boundary DI and final DS. Unbounded or exhausted fixtures are excluded.

Another 1,280 original-only prefix probes stop before PUSH BX/PUSH CX at
6736/6876/69B6/6AF6/6D5B. They check all 256 shift values at each new entry,
data/mask words, spill bytes, the actual saved SI and instruction-defined FLAGS:
1,027,840 instructions and 34,560 events, excluded from native/C totals.

The wide callback passes 28 fixtures at both APIs: 289 bytes, all 147 sites,
all seven branch outcomes, 135,170 ordered byte-bus events, 103,800 independently
projected plane-byte checks and ten completed mutants. Eight fixtures use every
unchanged 640-byte bank from one bounded original 5C06 call. Its 5,120 output
bytes match the independent 40-bit shift/OR calculation; 80 sites, 38,916
instructions and 13,153 memory transactions remain separate. The finite
VGA-stack fixture explicitly checks 32/1/1 rows; the changed-count provider
checks 1/32/32. Source and return word tests include physical and offset wraps.

These six disjoint callbacks add 1,964 main C bytes, taking the union to 22,669.
All nine initialized sprite callbacks occupy 3,347 translated bytes; this does
not close the live indirect target domain at 715B. The three original producers
5B11/5BB0/5C06 still own 432 untranslated code bytes. New reports are
build/entity-sprite-planes-differential.json,
build/entity-sprite-planes-original-differential.json and
build/entity-sprite-wide-differential.json. Acceptance requires matching scopes
and input hashes. The complete 59BB transform, 3634 record loop, allocation
lifetime, provider/IRQ timing and full gameplay remain outside this checkpoint.
The 706F parent now connects these known child domains with explicit
changed-target and changed-return boundaries; see entity-sprite-dispatch.md
for its separate focused acceptance.
