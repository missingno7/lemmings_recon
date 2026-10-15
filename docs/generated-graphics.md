# Generated graphics buffer frontier

The live DS word `GeneratedGraphicsBufferSegment` at 1FE8 is initialized at
101F from a DOS allocation result plus 1000h and 1D0Ch paragraphs, with 16-bit
wrap. The request at 1009 is 5571h paragraphs. The next segment word at 1FEA
is another 166h paragraphs later. These establish allocation coordinates,
not a proven usable buffer extent, non-aliasing guarantee or zeroed contents.

The producer at 5AC1, called from the resource-load path at 58FE, selects
ES from that word and DS from `GraphicsResourceSegment`, then sets SI=DI=0.
It invokes the eight-shift generators at 5CDD and 5D66. With DF clear and
ordinary disjoint memory, intact code and unmodified save/count frames,
the fixed loops produce these spans (ends exclusive):

| Producer group | Source span | Output span | Per-shift rows/bytes |
|---|---|---|---|
| Eight calls to 5CDD | 0000..00A0 | 0000..0780 | 10 rows × 3 bytes |
| Four calls to 5CDD | 00A0..0108 | 0780..0C60 | 13 rows × 3 bytes |
| One call to 5CDD | 0108..0134 | 0C60..0E70 | 22 rows × 3 bytes |
| Ten calls to 5D66 | 0134..0184 | 0E70..1370 | 8 rows × 2 bytes |

Each generator restores its source cursor for the next of eight bit shifts;
the caller advances SI by 14h, 1Ah, 2Ch or 08h respectively. Thus this path
reads source bytes 0000..0183 and produces 1370h bytes under those conditions.
5CDD uses explicit forward destination increments while its LODSW follows DF;
5D66 uses DF-sensitive STOSW as well. Backward operation, changed live saved
counts/cursors and aliasing do not inherit the forward span proof.

The identified consumers select DS through the same live segment word:

- 5DF8 selects `0C60h + 66*((X-8)&7) + 3*top_clipped_rows` and reads three
  bytes per remaining row, up to 22. Here 66 and 3 are decimal. This matches
  the 0C60..0E70 producer group for the intended unclipped/positive-row path.
- 5FAC selects `240*AX + (record[27h]==FFh ? 03C0h : 0) +
  30*((X+record[4])&7)` for ten three-byte rows. The scale and 30 are decimal;
  AX 0..3 with both direction banks matches 0000..0780.
- 606B selects `0780h + 312*AX + (record[27h]==FFh ? 0270h : 0) +
  39*((X+record[4])&7)` for thirteen three-byte rows. The scale 312 (138h)
  follows the actual shifts/subtraction; AX 0..1 matches 0780..0C60.

Those selector ranges are layout matches, not validated input limits: the
original selectors, arithmetic, source words and restores remain unchecked.
The additional load at 7126 and the final producer group retain open consumer
ownership; no span is declared dead or unused. Reaching allocation alone does
not establish that the later resource producer ran or completed.

## Native generator contracts

`GenerateWordMaskShifts` (5CDD..5D17, 59 bytes/36 sites) and
`GenerateByteMaskShifts` (5D66..5D93, 46 bytes/30 sites) have logical C cores
and register adapters in c/mask_generators.c. Both take live DS:SI source,
ES:DI destination, BL repetitions and CX rows. They clear DH at entry, save
DX/BX/SI for each shift pass and save BX/CX again around the repetition loop.
Every row pushes and pops CX. All of these are actual SS words, including
the restored source cursor and shift/repetition controls. There is no cached
copy of a save frame and no artificial loop cap in the native core.

The word generator loads AL/AH in source order, clears DL, then shifts the
AL/AH/DL bit chain right DH times. It writes AL, AH and DL with three explicit
INC DI instructions, independently of DF. The byte generator clears AH and
shifts AL/AH right DH times, then uses DF-sensitive STOSW. LODSW/LODSB follow
DF in both leaves. Their live restored DH is incremented and compared with
eight; altered save words can change the number of passes. CX=0 and BL=0
retain the original wrapping LOOP/DEC behavior. Neither is an empty loop.

`GenerateGraphicsMaskBanks` (5AC1..5B10, 80 bytes/35 sites) composes the
leaves directly in c/generated_graphics.c. PUSH DS precedes the ES selector
read, which precedes the source DS selector read. A stack alias or provider
side effect can therefore change those selectors. Each native child call
writes the original near return word, and the caller reads that actual word
after child completion. A changed child target returns an explicit continuation
without executing the trailing parent instructions. On normal completion the
live outer CX words control the loops, SI advances by the original literal,
and POP DS reads the actual saved value. Final flags come from the last ADD
SI,8; DS restores from its save and ES remains the selected output segment.

Core boundaries stop before the leaves' RET or the parent's normal 5B10 RET.
Adapters consume the outer return word only at a normal core boundary. Every
source, destination, selector and stack access uses the same optional raster
bus; null selects ordinary RAM. Callbacks preserve registers and may change
later memory/device reads. Word accesses observe the low byte before the high
byte at physical+1, with 20-bit physical wrap and 16-bit cursor/SP wrap. The
domain requires intact executing code and TF clear; it does not establish
device initialization or IRQ scheduling.

The 5CC1 caller shares the 5CDD body by fallthrough after its first child call;
that caller remains untranslated. The adjacent 5D18..5D65 bytes remain UNKNOWN.
No classification, allocation bound or whole-game acceptance follows from the
three scoped translations.

`tools/difftest.py mask_generators generated_graphics` verifies the leaves in
44 fixtures at both core/adapter boundaries: all 105 bytes/66 sites, 20 branch
edges and 28,508 ordered callbacks, with five completed mutants. Independent
bit-chain answers cover both output forms. Finite provider-controlled cases
exercise zero CX and BL without running enormous wrapped loops or changing
native semantics.

The producer passes 17 fixtures at both boundaries: 80 additional caller bytes,
101 integrated sites, 24 expected edges and 592,280 callbacks, with five completed
mutants. The two untaken repetition edges in this caller's constructed BL=1
fixtures are covered in the separate leaf suite; they are not declared dead.
The independent normal-path calculation checks every one of the 1370h output
bytes. Other cases exercise live selectors/counts, actual changed child and outer
returns, source/destination overlap, DF and wrapped or VGA-backed accesses.
The child bytes overlap their existing translations and are not counted twice.

Each worker has a 180-second deadline, 384 MiB process and 640 MiB tree commit
limits. Original leaf calls are capped at 65,536 instructions and producer calls
at 120,000; every native call has a hard 65,536-callback limit. Exhaustion exits
86 and callback errors exit 87; neither counts as a detected mutant. Workers
exit before temporary DLL directories are removed. Reports retain exact domains
and input hashes in build/mask-generators-differential.json and
build/generated-graphics-differential.json. These are local acceptance results;
the full original/native campaigns remain prerequisites for aggregate acceptance.

The 5DF8 consumer now has scoped native acceptance in entity-mask.md: 43
fixtures at both boundaries cover all 194 bytes/91 sites, seven branch edges
and six completed mutants. Seventeen independent plane checks and an actual
native-producer handoff retain the 0C60..0E70 bank contract. The live clipped
count, DS/SI/DX/clip saves, source/destination DF behavior, incoming VGA state,
early IF preservation and drawing-only STI remain explicit.

The 5FAC/606B consumers now pass 67 core/adapter fixtures: 405 bytes/187 sites,
ten branch edges, 33,308 events and nine completed mutants, with 41 independent
plane checks and two native producer handoffs. Their live base/DX/DS/SI saves,
record reads, unchecked selectors, BP difference and incoming VGA state remain
explicit in entity-mask.md. The thirteen-row caller still admits 130 AX values
for arbitrary record contents; native translation preserves that open state
invariant instead of narrowing it to the intended 0..1 layout subset.
