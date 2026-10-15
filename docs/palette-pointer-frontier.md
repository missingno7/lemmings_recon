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

The unrelated548C..54C3 DAC writer advances the hardware DAC index rather than
reading CS5507 for each row. It remains untranslated and is needed by52F4 and
other palette setup callers. Do not substitute54C4 for it. Broader native device
models, pointer initialization, palette-buffer ownership and4B40 input/IRQ wait
remain open, as do full terrain acceptance and stale-report refresh before any
aggregate C coverage promotion.
