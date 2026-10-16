# Palette pointer producers and transition ownership

Fresh531E tree and536C bottom-up views put the tested1550 status wait,
5425/54C4 port writers and563E/56E2 row composers below the transition entries.
The graph alone does not close source/target ownership or actual save/return
frames in the pointer producers. Keep the next investigation on those contracts.

The pinned sixteen-byte tables atCS:52D4 andCS:52E4 each read as eight
little-endian DS offsets:

| Slot | Packed base52D4 | RGB base52E4 |
|---|---|---|
|0|2638|2638|
|1|2608|2608|
|2|4920|4930|
|3|1F13|1F3B|
|4|25E8|25F0|
|5|1F0B|1F23|
|6|25A8|25B8|
|7|2668|2668|

These are initial bytes and observed pointer interpretations, not a validated
allocation map or proof of table extent. Source remains explicitly UNKNOWN.
Unchecked byte selectors are zero-extended, doubled and added to the table base;
adjacent bytes can supply pointers. Native code must read live canonical CS words
and preserve physical high-byte ordering. Do not cache these tables or create
converted palette records.

5569..55B5 compares live DS:1F7C with4: equality selects RGB, all other words
select packed. Each path pushes DS and pops ES, reads the source offset using BL,
then independently reads the target offset using BH. It tail-jumps directly to
the corresponding row composer, inheriting its nearRET frame and marker flags.
CL remains the input count. This connection is now native with586fixtures at
both boundaries andtwofullzeroCL cores; see palette-row-select.md. The531E/536C transitions now compose the native writers/rows/status wait in
1,191fixtures at both boundaries, including live pointer/save/return effects;
see palette-transition.md. The writer-pointer prefixes remain separate setup paths.

5401..5423 is the shared writer-pointer prefix: zero-extend AL, double AX, compare
the same mode word, read a CS pointer and tail-jump to5425 or54C4. 53F6 sets
CX=8, 53FE setsCX=16, and53FC suppliesAL=2 before the latter. 53CA is another
prefix withCX=0808, adding8 to a packed source or18hex to an RGB source.
Preserve16bit arithmetic and flag effects even though a child overwrites some.

531E suppliesAL=0,CX=16,BX=0100;536C suppliesAL=0,CX=16,BX=0200. Both jump to
55B7..563D. That shared body saves ES, selects live pointers as above, and runs:
saveCX/SI, output the current source palette, restore actualSI/CX, saveCX/SI/DI,
step toward the target, then test the returned marker. The packed branch waits
three status cycles before another iteration; RGB waits one. All saves and child
returns can alias data/provider writes. Finishing restores the actualDI/SI/CX/ES
words. A marker says whether a component differed at entry to a step, so reaching
the target on a step still requests another output/step pass.

The 548C..54C3 sequential DAC writer and timer callers5473/553D now have scoped
native acceptance in tests/palette_timer.py. They reuse c/palette_ports.c and
the shared verifier, including the actual5555 child return. The169-byte domain
unions135 new bytes with the34-byte attribute leaf; all81 sites/20 branch
outcomes pass132 comparisons and five completed mutants. See palette-ports.md.
Other setup callers, including52F4, remain separate parent work.

## Canonical source ownership

DS:2638,2650 and2668 initially map to UNKNOWN static bytes at image offsets
C0C8,C0E0 andC0F8. Their stored zeros remain UNKNOWN. Startup's DS:0000..2011
clear does not reach them. The neutral ledger names TimerPaletteSource2638,
TimerPaletteSource2650 and TimerPaletteSource2668 describe observed source
roles without asserting allocation extents or complete initialization.

The row composers write back through the source DS:SI selected by BL; BH selects
the target. With the initial pointer tables,531E/536C modify slot0 at2638 toward
slots1/2 for16 iterations. RGB writes cover2638..2667, so2650 is the second half
of that same range. sub_5329 composes0-to-1 then7-to-1, both16 iterations.
sub_534B composes0-to-6 then7-to-4 for16/8 iterations from caller03CE, or0-to-3
then7-to-2 for16/16 from0467. These are observed loop extents, not validated
allocation bounds. Live table mutations can select other locations.

Before the timer display update,5473 selects mode4 RGB source2668 for eight
entries at DAC index10h, or mode2 packed source2668 for eight entries at index8.
Other whole-word modes return. Afterward,553D selects mode4 RGB sources2638 then
2650 for eight entries each, at indexes0 and10h; mode2 sends16 packed entries
from2638 at index0. These consumers read the same canonical storage that the
transition rows modify. No converted palette copy is introduced. The existing
row/selector/transition fixtures include synthetic and pinned-table DS:09A9
cases, but do not establish the entire runtime producer/initialization chain.

DS:200C PaletteBlankingControl is initially zero at image BA9C and is within the
startup clear. Direct writes at1205/1369 storeFF;1099 reads it. Both DAC writers
reread it around output, at548D/54B6 and54C6/54F8 respectively. Live provider
changes verify those separate reads without proving IRQ synchronization.
Broader device models, pointer initialization, source allocation and4B40 input/
IRQ ownership remain open, as do aggregate acceptance and stale-report refresh.
