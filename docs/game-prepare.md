# Palette, sound and drawing-page setup

The six native entries in c/game_prepare.c implement the remaining direct setup
dependencies of 03E7. They add 620 unique known instruction bytes. The 03E7
controller and main loop remain untranslated; this is a connected preparation
milestone, not a runnable game. UNKNOWN483F,531D,8122 and initial lookup bytes
retain their classifications. Native status, palette and far-layout children
retain their documented platform, alias, IRQ and fatal boundaries.
The next controller's static ownership and actual call/IRQ sequence are in
game-initialize.md.

## Palette and sound ownership

52F4 publishes the base palette from live CS pointer slot1. Only the full mode
word equal to four uses RGB. Its first eight DAC colors use a real CALL/RET5317;
the second eight start at bank16 and continue from the actually advanced SI.
Packed modes tail-enter the attribute writer. No extra outer frame is added.

5377 reads CS slots6 and5 into DI/SI, and obtains ES through actual PUSH DS/POP
ES. Source color0 is duplicated into destination color7, then eight source
colors fill destination colors8..15. Packed colors are bytes and use four
MOVSWs; RGB colors use three bytes and twelve MOVSWs. DF, cursor wrap, live
table/stack words and the final option-byte CMP/RET sites remain observable.

482F uses any nonzero external-driver byte2010. A nonzero special-resource
byte selects the unchecked table at4888 using a decremented byte index.
Otherwise success1F6D increments the live cycle byte1F6C, wrapping only exact
17 to zero. With no success, AL remains zero and selects the first ID; it does
not read the stale cycle byte. The normal path saves AX and restores its actual
word after writing sound ID0054, so an alias can change the returned AX. That
ID later feeds the original INT61 consumer03B4. All256 special/cycle byte values
are compared, including reads outside the nominal tables. Tables and code bytes
read as data remain canonical memory, not an instruction fallback.

## Canonical drawing and dirty maps

7900 clears thirteen bytes on all planes, then copies nineteen contiguous
thirteen-byte source rows from A000:D320 to a44-byte destination pitch. It
preserves original map/GC mirror writes, OUT ordering, write-mode1 latches,
live DF and BP's saved DS. Overlapping source/destination and a return word
inside an SS register mirror are explicit fixtures.

80FD sets the live VGA mirrors before observing the leading map byte through
actually popped ES. A nonzero byte selects160 rows of44 copied bytes; source
pitch is208, destination pitch44. Zero selects twenty rows of forty dirty cells.
Only an exact byte1 matches. REPNE finds a run and REPE consumes its first
nonmatching byte as well, so a run normally copies that adjacent clean column.
Each run covers eight pixel rows. Actual saved counts, cursors, AX, ES and DS
remain live, including inner-copy count changes. The final800-byte map clear
starts after an explicit forward INC; DF controls subsequent strings/scans.
There are no shadow dirty maps, cached stack counts or normalized flags.

81CC initializes both origins/maps, marks both leading bytes, copies the first
page, swaps the actual current fields, initializes native status, copies the
second page and far-calls native layout. It then sets the original fixed-pattern
offsets. Child stops preserve their frames; changed near/far returns stop before
continuations. The layout's inherited RETF selector-EA-wrap reference limitation
remains explicit; no newly supplied fixture claims that domain.

## Shared bounded evidence

tests/game_prepare.py uses tests/verification.py for original execution, canonical
bus access, guarded callbacks, near/far frame comparison and packed observations.
Independent sound, palette and full/partial/status plane expectations stay in
the fixture. The shared engine now tracks SCAS comparison flags: zero-count REP
does not define flags, while an executed comparison does. A shared bounded
four-field device trace preserves every field/order without growing tuple lists.
Unit tests exercise both SCAS cases and compare packed/plain VGA device state.

The campaign covers all owned sites/direct outcomes, three loads, both return
boundaries, full-word mode checks, DF, unchecked bytes, live pointers/maps/saves,
port failures, status-child failure and changed far CS. Eight completed numeric
mutants target bank selection, DF, exact17 wrap, map clearing, actual returns,
scan overshoot width, source pitch and cached map pointers. Limits are900 seconds,
384 MiB per process /640 MiB per process tree, two million instructions and one
million bus/device events per case. Exhaustion fails verification and cannot
earn mutant credit; owned DLL contexts are reaped under build/.

External IRQs are quiescent and TF clear. Real device scheduling, the remaining
03E7/startup/frame/game controllers, executable dependencies and aggregate
acceptance remain open. A fresh original-contract campaign is required after
the shared SCAS change; unrelated native reports are not renewed by retention.

The focused gate passes577 fixtures /1154 comparisons,all237 owned sites /34
direct outcomes and eight completed mutants,in1498 connected known bytes. It
executes479,466 original instructions and compares757,480 ordered bus events;
all42 consumed-file hashes match. All86 unit tests pass. Ledger status and
progress prose are excluded from behavioral hashes because this fixture uses
explicit instruction ranges; compiler headers,ASM,helpers and actual native
source closure remain pinned.
