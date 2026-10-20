# Bottom-up semantic reconstruction

The permanent oracle is maintained ASM plus ledger-owned names, offsets and
proven data contracts. The original binary is the final authority. The
[semantic audit](semantic-audit.md) defines READY/CONDITIONAL/NOT READY by scope;
C presence, byte classification and semantic readiness are different facts.

## Working loop

1. Choose the uncertainty that would force a translator to guess or prevent the
   next complete game operation. Use [next-work.md](next-work.md), not a byte quota.
2. Follow the original body, callers, shared tails, state producers/consumers and
   hardware/IRQ crossings. `graph.py --asm` ignores C-range truncation; the
   default graph still shows native scopes. Neither view proves reachability.
3. Recover boundaries, state/table/lifetime ownership, then purpose names and
   caller-observed contracts. Local labels and literal naming come afterward.
   Put reusable semantics beside ASM and names/offsets in the ledger. Do not
   leave the only explanation in a C fixture or duplicate a running status table.
4. Run the exact gate. Record a scoped readiness decision. A known leaf may be
   READY while its parent is CONDITIONAL; do not wait for global UNKNOWN closure.
5. Translate or connect a coherent READY operation. Preserve existing C and
   strong adapter evidence. New parent cases check handoffs/shared state rather
   than re-running exhaustive child matrices. Reduce machine-shaped interfaces
   only after proving their actual call/lifetime contract.
6. Run the affected verification tier; record changed evidence, remaining
   uncertainty and the next semantic dependency. No fixed mutation quota.

```powershell
.venv/Scripts/python.exe tools/where.py 03E7 --disasm 24
.venv/Scripts/python.exe tools/graph.py 03E7 --asm --tree --depth 1
.venv/Scripts/python.exe tools/graph.py 03E7 --asm --bottom-up
.venv/Scripts/python.exe tools/graph.py 03E7 --tree
.venv/Scripts/python.exe tools/verify.py
.venv/Scripts/python.exe tools/coverage.py --inventory
```

Default graph C ranges remain scoped. The original-body view follows decoded
branches/shared tails and calls even where C already exists, and reports C byte
overlap without labelling the whole body TESTED. Both retain UNKNOWN,
conditional indirect targets, device sites and protected execution frontiers.
Syntactic DS/ES/SS tags alone do not establish state ownership.

Pre2 contributes the question-driven loop, canonical memory and immediate
semantic feedback into source. Overkill contributes a concrete readiness bar.
Their exact segment/stack models and historical linker modules are not copied.
See the audit for the observed methodology and evidence-domain differences.

## Maintained source ownership

`src/program.asm` includes these files in unchanged physical image order, with
an end assertion after each code module. Every ledger symbol is also asserted.
These are reconstruction boundaries, not claims about historical linker modules.

| Inclusive image range | Source | Ownership status |
|---|---|---|
| 00000..017C6 | entry_services.asm | Entry/service frame; protected views remain separate |
| 017C7..018B1 | game_timer.asm | Timer entry/shared tail, two live return frames and checksum overlap |
| 018B2..01915 | entry_services_after_timer.asm | EOI leaf, critical error handler and UNKNOWN spans |
| 01916..01F18 | resources.asm | Raw files, selection, special setup and DAT/cache cluster; allocation candidate has unresolved reachability |
| 01F19..0314F | game_code.asm | Simulation-state and creation contracts; native domains remain scoped |
| 03150..03633 | entity_actions.asm | Action dispatch, eight selectors and shared sound/RET tails; UNKNOWN preserved |
| 03634..0368D | entity_drawing_calls.asm | Live record loop, child frames and decimal JMP tail; UNKNOWN 366F and provider/IRQ seams retained |
| 0368E..03789 | level_initialize.asm | Drawing initialization, live clear tail, header and level-state caller |
| 0378A..03943 | level_objects.asm | Record copy, interaction cells and coordinate collector |
| 03944..039CD | game_code_late.asm | Object-animation gate and redraw caller; UNKNOWN preserved |
| 039CE..03AC7 | status_initialize.asm | Initial status copies, wrapped release reload, shared snapshots and actual child frames |
| 03AC8..03CDD | status_display.asm | Status display, actual child frames, shared refresh fields and byte-DIV frontier; UNKNOWN preserved |
| 03CDE..03E6E | entity_selection.asm | Candidate scan, live bucket/index ownership and selected display; UNKNOWN preserved |
| 03E6F..04084 | input_commands.asm | Shared command counters/latches, sound boundaries and visibility child |
| 04085..0410E | game_code_late_after_selection.asm | Input edge/selection suffix |
| 0410F..0414E | view_visibility.asm | Shared visibility producer with live DS/ES, relocated marker segment and existing caller frame |
| 0414F..0418B | game_code_after_view_visibility.asm | Display tail and status text |
| 0418C..04333 | input_poll.asm | Connected mouse, keyboard and live callback input |
| 04334..043CD | port201_input.asm | Port-201 wrappers and measurement; two UNKNOWN bytes retained |
| 043CE..04B5B | input_menu_and_retry.asm | Input/menu and retry suffix; physical order and UNKNOWN preserved |
| 04B5C..04BE6 | decimal_fields.asm | Percent wrapper, shared variable-width decimal fields and fixed three-digit helper |
| 04BE7..052D3 | game_code_late_after_decimal.asm | Display setup, timer and palette callers; mixed ownership remains provisional |
| 052D4..0563D | palette_frontends.asm | Palette pointers, writers and transition callers; ownership/frontier contracts remain explicit |
| 0563E..05725 | palette_steps.asm | Packed/RGB rows and channel arithmetic, tested native contracts |
| 05726..057D0 | entity_dirty.asm | Unchecked visibility gate and live SS dirty rows; actual saved CX/SI and post-store bounds |
| 057D1..05B10 | game_code_late_after_palette.asm | Resource/generator callers; mixed ownership and UNKNOWN preserved |
| 05B11..05CC0 | sprite_banks.asm | Three exact sprite-bank leaves; live SS counts/cursors, byte operands and signed folds |
| 05CC1..05D65 | game_code_after_sprite_banks.asm | Word-mask generator prefix and unresolved suffix |
| 05D66..0616F | entity_graphics.asm | Byte masks, pixel setup/address and entity mask drawing contracts |
| 06170..064D8 | entity_sprite_aligned.asm | Ten literal masked/OR sprite rows, forward masks, DF strings and live DS/RET |
| 064D9..066D6 | entity_sprite_shifted.asm | Independent12/13-row callbacks, unchecked shifts, live first-pass saves and OR plane |
| 066D7..06BDA | entity_sprite_planes.asm | Three-plane narrow callbacks; BP/AX row counters and live phase DI saves |
| 06BDB..06CFB | entity_sprite_wide.asm | Three-plane five-byte rows, live CX counts and OUT-before-mirror initial setup |
| 06CFC..06E82 | entity_sprite_four_planes.asm | Four-plane fourteen-row narrow callback; live AX counts and three DI restores |
| 06E83..06F7A | entity_points.asm | Point-cloud leaf, live point/color tables and nested SS saves; table ownership remains UNKNOWN |
| 06F7B..06FE1 | entity_strip.asm | Two-byte strip with incoming CX source segment, DF strings and actual popped LOOP count |
| 06FE2..0706E | entity_minimap.asm | Signed entity minimap pixel guards, live saved X/table and VGA effects |
| 0706F..0715E | entity_sprite_dispatch.asm | Live entity descriptor arithmetic, optional strip and dynamic callback; unresolved715B retained |
| 0715F..075EE | fixed_pattern_drawing.asm | VGA span copies and literal word-pattern passes; UNKNOWN71CA..7217 preserved |
| 075EF..07629 | status_copy.asm | Full DF-sensitive status-region copy, live DS and single-CALL/fallthrough wrapper |
| 0762A..0780C | status_glyphs.asm | Count and character glyph contracts; five UNKNOWN bytes preserved |
| 0780D..078FF | status_icons.asm | Status outline and restoration; signed selector and live VGA frames |
| 07900..0796E | game_code_before_minimap.asm | Status backdrop preparation |
| 0796F..07A59 | minimap.asm | Column, row and population sample contracts |
| 07A5A..07BB7 | minimap_viewport.asm | Live viewport outline, VGA mirrors and saved phase contract |
| 07BB8..07C66 | object_graphics_tick.asm | Object draw loop and shared animation tail; live fields and stale-BX contract |
| 07C67..07EB1 | game_code_late_tail.asm | Terrain, scroll/copy and background bodies; scoped native domains |
| 07EB2..080FC | level_preview.asm | Four-plane source sampling, OR destination latches and live SS saves |
| 080FD..08237 | game_code_after_level_preview.asm | Remaining game display/dirty suffix; UNKNOWN preserved |
| 08238..08342 | special_graphics.asm | Tested strip entries/shared tail |
| 08343..083BE | checksum.asm | Tested checksums, state and code/data overlap |
| 083BF..08821 | code_tail.asm | Overlay storage, layout setter and unresolved spans |
| 08822..09A8F | planar_drawing.asm | Planar renderer, dispatch, row preparation and clip/dirty leaves |
| 09A90..143D9 | image_tail.asm | Data frame; UNKNOWN may contain executable code |

The contiguous 05D66..0616F span groups nine identified mask and pixel helpers
in entity_graphics.asm, with exact start/end assertions and unchanged emission
lines. The earlier word generator and neighboring UNKNOWN bytes remain in the
resource-side prefix. This is physical source ownership, not a historical
linker boundary or an assertion about complete simulation/device readiness.

Shared tails can cross files. All encoding exceptions, UNKNOWN markers and
classifications remain unchanged. The bootstrap generator refuses to overwrite
the maintained modular layout. Refine the actual ASM and keep exact verification.

The contiguous 0378A..03943 object helpers now live in level_objects.asm,
included directly by program.asm at their original position with start/end assertions.
This groups the graphics-record copy, SS interaction rectangles and coordinate
collector while keeping their broader setup and drawing callers outside the module.
Record ownership and preserved quirks are documented in object-records.md.


Source-layout rows describe physical ownership, not C completion or historical
link modules. Detailed contracts belong beside these bodies and in their named
subsystem documents. Historical milestone counts live only in
[convergence-history.md](convergence-history.md).
