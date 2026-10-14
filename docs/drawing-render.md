# Connected aligned opaque planar rendering

`drawing_render.c` composes the native `882D` preparation with the aligned,
opaque `983B` VGA body. The adapter is entered after the original `8822` caller
prologue has executed its seven instructions and left three live words on SS.
The render core first runs preparation against the same canonical 1 MiB RAM; it
enters the body only when preparation leaves continuation `983B` and has not
reported a changed child return. Other selected VGA bodies, `88AB`, and changed
child returns remain explicit stops. The wrapper adds no original bytes to
translation accounting.

The body consumes the prepared source/destination cursors, packed row and byte
counts, plane counter, flags, live stack offset and original DS. Its separate
`game_data_segment` supplies the live row/plane advance words. The graphics
segment is read through initial DS after its live push; the fixture uses the relocated image's `load + 09A9` segment even when
the original DS is aliased. The body starts with a live push of original DS,
uses ES=`A000` for planar VGA accesses, selects plane masks for up to four
passes, and restores DS at `9965`. The C core stops before original
`RETF` at `9966`; the adapter reads the live far-return IP and CS bytes through
the ordered bus and advances SP as the original return does. It does not infer
the target from a static continuation.

`tests/drawing_render.py` executes the real relocated `8822` prologue, then
compares the C adapter against original instructions from `882D`. Its 776
bounded cases include 290 complete `983B..9966` body executions, 483 ordinary
continuation stops, and three changed-child-return stops. The added aligned
opaque matrix covers plane limits 0, 1, 2, 3, 4, 5 and `FF`, widths 8/16/24,
both DF values, source reversal, and one to three rows. Limits outside 1..4
retain the original four-pass behavior. Additional cases cover a right-edge
clip that leaves one byte, a controlled CL=0 `LOOP` of 65,536 iterations, and
a DS=SS alias of the saved BP word. Inherited preparation cases also exercise
the other live-register, dirty-map, clipping and return boundaries. The
`stack-FFFF` case is excluded because Unicorn models that far-return stack
boundary differently from the permissive adapter; no return-target bytes are
changed to accommodate the emulator.

All 287 preparation instruction sites and 149 known aligned-body sites execute,
covering 123 branch edges. Seven original-only `8822` prologue sites are
reported separately and are not C coverage. The preparation edge `88A6 ->
88AB` is excluded from the normal-entry edge set. UNKNOWN bytes at `98F4` and
`9932` remain unresolved and outside the decoded body spans. The report records
`translated_code_bytes: 0`; the test does not infer that any other body or
unresolved region is dead.

Each case compares all 1 MiB of canonical RAM, registers, dynamically defined
flags, ordered byte reads/writes, VGA planes, latches and registers, and ordered
port/MMIO traces. Flag masks follow the last original setter: arithmetic
instructions include AF, logical instructions omit undefined AF, and MUL
checks its defined CF/OF pair plus preserved TF/IF/DF. Independent whole-plane
footprints check the explicit matrix and right-clipped row, including untouched
plane bytes. The seeded fixture models unchained mode-0 VGA with quiescent IRQs;
code remains intact and 20-bit physical wrapping is observed.

The harness also records the isolated Unicorn RETF/read-hook observation from
`level_drawing.py`. At the body boundary it records the actual four stack bytes,
removes the memory-read hooks, and executes the original `RETF` once. It then
compares actual CS:IP and SP with the live frame. This keeps the emulator hook
artifact visible without patching the instruction or replacing its target.
Three compiled mutations are detected: skipping the body, clearing DF before
the body, and leaving the outer far return unconsumed. The generated
`build/drawing-render-differential.json` contains the case list, executed sites,
branch edges, mutation results, RETF observation and hashes of the C/test/oracle
dependencies.

## Default aligned masked connection

`lmn_draw_prepared_planar_core` and its adapter compose native preparation with
either 983B opaque or 93F6 default masked drawing. The existing opaque-scoped API
retains its explicit 93F6 seam. The new mask cursor is the preparation result
second_source_cursor (BX); the core returns its live first-pass progress.

`tests/drawing_masked_render.py` passes 100 constructed original/native cases:
90 complete masked draws, 8 complete opaque draws through the general API, and
2 source-row/saved-BP aliases that select the unported 969C effect body. The suite
covers 535 integrated instruction sites and 98 edges, with 3 compiled mutants.
It checks all RAM/registers/defined flags, ordered byte/port/VGA accesses and
independent whole-plane expectations across DF, reverse-source preparation,
plane limits 0..5/FF, clipping and dirty marking. Both original far-return opcodes
are single-stepped with the documented read-hook observation. Prologue sites
remain original-only evidence; connection coverage is unioned with other suites.

Both connection verifiers run in disposable bounded workers with the Windows
512 MiB process/768 MiB tree cap, 180-second deadline and a 1,000,000-byte-access
trace limit. DLL directories are cleaned after termination; completed Unicorn
callback cycles are collected between cases. Guard exhaustion fails verification.
Selected shifted/effect bodies, asynchronous IRQ delivery and native VGA timing
remain unresolved. No complete 8822 C entry or full game is claimed.
