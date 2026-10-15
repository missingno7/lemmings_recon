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

Next resolve and translate the 5CDD/5D66 generator contracts, connect 5AC1,
then close the source and save-frame contracts of 5DF8/5FAC/606B. Preserve
their live DS replacement, saved DS/SI/count words, incoming DF and unchanged
VGA state. Their fixed-looking initial loops do not rule out larger wrapped
counts after aliases. This note is static evidence, not a new behavioral or
C-coverage report.
