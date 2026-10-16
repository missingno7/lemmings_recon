# Resource plane copy

`CopyResourcePlanesToVga` is the exact 86-byte leaf at `57D1..5826`, with
45 instruction sites. Its logical C core stops before the near RET at `5826`;
the adapter consumes the current SS:SP word. There are no child calls.
Focused behavioral acceptance is recorded below.

## Live input and device contract

The routine selects ES=A000 and copies from live DS:SI. BH controls planes,
CX controls rows, BL controls bytes per row, and AX is the literal row pitch.
It saves AX before configuring the VGA Graphics Controller. The four ordered
word writes to live SS mirrors precede their corresponding OUT instructions:
index/value pairs `0001`, `0005`, `0003`, `FF08` at offsets `000C`, `0000`,
`0002`, `000E`. It then pops AX from actual memory. A mirror/stack alias can
replace that saved pitch.

Each plane pushes DI, CX, AX and DX, writes the Sequencer map-mask word to
SS:0008 before OUT 03C4, and pops DX and AX. DX starts at 0102; its high byte
shifts left after each plane, including shifts beyond the four VGA planes.
Each row pushes CX, DI and BX, clears CH, copies BL bytes with REP MOVSB,
pops the live BX, DI and CX, adds AX to restored DI, and executes LOOP.
SI flows through every row and plane. DI and CX are restored from live plane
saves before SHL DH and DEC BH. DS, SS and BP are unchanged; ES remains A000.

BH=0 executes 256 planes with intact saves. Row CX=0 enters the body before
LOOP and wraps through FFFF. BL=0 makes REP perform zero byte transfers;
the surrounding row and plane loops still execute. REP follows live DF,
while ADD DI,AX retains its original direction. No C loop cap changes these
contracts. Bounded tests must construct finite witnesses or use explicit
providers when exercising zero counters.

All memory and device callbacks occur in original order with the flags at
that phase. XOR CH,CH leaves AF undefined. ADD DI,AX updates arithmetic flags;
SHL DH,1 leaves AF undefined; DEC BH preserves the shift's CF and supplies the
other final arithmetic flags. LOOP, POP and RET do not alter those flags.
Stack words use the high byte at physical address plus one with 20-bit wrap;
their stack cursor wraps independently at 16 bits. Byte string accesses use
the current 16-bit source and destination offsets. Saved values and return
words are never cached across accesses which can modify them.

## Resource ownership

The two direct callers at `5927` and `59A1` supply DI=F91F, SI=0, CX=0028,
AX=002C and BX=0428, with DS selected from `GraphicsResourceSegment`. Under
DF=0 and intact disjoint saves, this copies four planes of forty rows of
forty bytes: 1900h source bytes. Each plane writes offsets F91F..FFFA in its
selected VGA plane. SI ends at 1900h, DI returns to F91F, CX returns to 0028,
BH is zero and DX is 1002. These coordinates do not establish allocation,
aliasing, initialization or interrupt timing bounds.

The first path decodes pinned MAIN.DAT section 2. Its static decoded size is
20C0h (8,384 bytes), SHA-256
`7e1b6a0a63f88c37bb9bb6b40d2d4889862ece61aceffc2b6c19961436b9cadd`.
The 1900h-byte plane prefix is followed by the 07C0h status-glyph copy at
593C, exactly accounting for that decoded section under normal DF=0.
The conditional second path decodes section 6, size 2020h (8,224 bytes),
SHA-256 `0fea37bb7811ab6968bf26fcb22a6b2f5cafd60690386435a69aa35bf05bc6b9`.
Its 1900h-byte prefix is followed by the 0720h byte copy at 59B7, exactly
accounting for that section. These sizes and hashes come from bounded static
DAT extraction in memory; no asset or decoded dump was written.

The enclosing `LoadMainResourceSections` routine remains a separate composition
frontier, including live restored DS/BX, the actual return words, retry UI at
4B1C and fatal decoder exits. This leaf does not establish complete resource
loading or gameplay acceptance.

## Scoped C acceptance

`tests/vga_plane_copy.py` passes 21 fixtures at both boundaries: 42 comparisons,
all 45 sites and four branch outcomes, 78,878 ordered events and 49,179 original
instruction steps. Independent equations check 25,696 VGA plane bytes,
including the complete normal copies from pinned sections 2 and 6. All ten
numeric mutants complete and are detected. Callback or worker exhaustion is
a verification failure and earns no mutation credit.

Fixtures cover zero BH, BL and a finite live-stack witness for zero CX, DF,
saved AX overwritten by mirrors, live row BX/DI/CX words, SS in VGA, source
offset and physical wrap, stack SP=0001/FFFF, physical FFFFF word crossings,
mirror/port order and the actual outer return overwritten to 1234h. Full RAM,
returned registers, defined flags at boundaries and bus phases, ordered events,
VGA planes, latches and device traces match the original instructions.

The native and original-only reports are
`build/vga-plane-copy-differential.json` and
`build/vga-plane-copy-original-differential.json`. Acceptance requires their
matching input hashes and recorded scope. The worker deadline is 420 seconds
with a 384 MiB process-tree commit cap, a one-million original instruction
budget and 180,000 callback events per invocation. This adds 86 unique main
C bytes; byte identity, translated code and executed sites remain separate
metrics.
