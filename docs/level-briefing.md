# Connected level briefing

ShowLevelBriefing at4566 composes the existing portable formatting, palette,
display, redraw, preview, background and text cores on one canonical memory
image. The new physical controller extent is316 bytes, excluding UNKNOWN469A
from its315 known instruction bytes. WritePercentageByteField4B5C,
ClearBelowLevelPreview4C17 and PublishBasePaletteBothBanks5447 add12,9 and43
unique bytes. Their shared tails remain counted once. This is the briefing
body;454C's preceding state clear/resource selector and the subsequent game
controller remain separate.

## Fields and arithmetic

The selected level field uses byte arithmetic throughout: increment selection,
subtract the low byte of30*group, then call the existing two-character formatter.
It does not normalize a wrapped result or restrict the rating/group row. Header
low bytes at0FCE,0FD0,0FCC and0FD2 feed population, the percentage numerator,
release setting and time respectively. Existing header-word symbols retain
their ownership; this consumer proves a role for word+04 without inventing a
separate host header or claiming every later use of its0044 destination.

The percentage path multiplies AL by100 into AX, rereads population into CL,
then performs unsigned byte DIV. Zero divisor and quotient greater than255
retain an explicit processor-fault boundary at459C. C never divides by zero,
clamps the quotient or widens the original successful result. The result stores
AL at0041 and uses the percentage wrapper at4B57. DIV's arithmetic flags are
undefined; the shared original verifier now invalidates all six arithmetic
flags after an actual DIV, with a focused original-instruction unit test.
The native result exposes the preceding state and fault site for platform
exception handling; it does not implement an INT0 handler or resume past a fault.

WritePercentageByteField writes a space at incoming SI+3 before pushing its
actual4B63 decimal return. It consumes that live return, writes a percent sign
at the returned SI and increments SI forward regardless of DF. All256 byte
values are exercised through the shared decimal core and an independent text
expectation. The wrapper can stop on a changed child return before writing
the percent sign.

Time adds30hex to a byte and selects a space instead of's' only when the
result equals'1'. There is no general host pluralization or range check. A real
PUSH DS/POP ES precedes the32-byte DF-sensitive title copy from LoadedLevelFooterBytes
17AB to4B19. The six-byte rating copy uses the unchecked row at4C01+6*group;
its explicit INC operations always go forward. Text destinations are named
in the ledger, retaining their aliases with the original image data.

## Display and input connection

The first palette loop calls5329 until its returned ZF is set, then publishes
slot1. Display origins become zero before the native swap and RedrawLevel.
The redraw services object passes its existing optional special/DOS services
while the parent binds the same canonical bus and byte ports locally. Missing,
fatal, changed and unsupported redraw results remain child stops. The tests use
constructed ordinary definitions, an empty stream or a real nonempty constructed
terrain command; a selected special path without services stops at1A7B with its
actual return frame intact.

The parent resets live drawing coordinates, calls DrawLevelPreview7EB2, resets
them again and calls ClearBelowLevelPreview. That wrapper loads DI15E0/CX5780
and tail-enters the existing clear, preserving the top70 ordinary display rows
when DF is clear. DF remains live; the backwards path is not converted into a
rectangle clear. The inherited4E36 caller return is retained. A missing clear
capability stops at4DF8 after the two loads.

Display layout, four-row background publication and both text streams then run
through their existing C cores and actual near/far frames. Both input-mode
comparisons reread the live byte25A6. The input-release loop reads the complete
button word and tests only bits0..2. Split refresh, upper-eight publication and
534B row steps preserve their order and actual returned flags.

The final wait distinguishes buttons, command20hex and command40hex. Button or
40hex tail-enters the existing fade/clear, inheriting the original caller RET.
Command20hex CALLs the fade with return469E, consumes that return, POPs the
actual caller word into AX and JMPs4401. The native adapter consumes an outer
RET only for the normal clear-tail result; it never pops again on the menu
continuation. No original game boot or runtime instruction fallback is used.

PublishBasePaletteBothBanks is the additional parent needed by the game display
path's02CD/0319 callers. Only full modeword4 performs two sequential DAC banks,
CH0 andCH10hex/count8, each starting at the same live DS2608 source. The first
CALL has a live5460 return; the second is a tail jump. The packed mode2 test
rereads the mode word and publishes16 entries through the attribute writer;
all other words return at5455. UNKNOWN5469 remains unresolved. Provider cases
change the second mode read, base source and first return, so neither the
mode nor the source rows can be cached into a shadow palette.

## Verification scope

tests/level_briefing.py uses tests/verification.py's original executor,
BusAccess, guarded NativeCallbacks, complete-state comparator and hard limits.
Instruction domains are pinned literal ranges; fixture construction, pinned
font/UI banks and packed trace storage are reused from the existing menu
fixtures. No new CPU, bus or comparator is introduced. The build resolver
deduplicates the actual transitive C sources instead of inventing new copies
of tested children.

Native calls have a900-second worker and384MiB Windows process-tree commit
limit, with4,000,000 original instructions and2,000,000 ordered events per
comparison. Raster and input providers have finite independent schedules.
Callback/budget failures terminate the worker and never count as mutant
detection. The parent owns the temporary DLL directory and removes it after
worker termination. Full report acceptance requires matching consumed inputs;
retained unrelated reports are not renewed.

The full-body cases retain the existing redraw/renderer/provider domains.
VGA-backed stack and arbitrary nonterminating aliases, special-resource service
alternatives not exercised here, hardware timing/IRQ scheduling,454C resource
composition and native platform/SDL3 integration remain explicit frontiers.
The original-only campaign is required after the shared DIV flag contract
changes; it remains separate from aggregate/full-game acceptance.

## Accepted native evidence

The selected campaign passes 295 fixtures / 590 core and actual-RET comparisons,
all 132 owned sites / 29 direct outcomes and five completed mutants. It executes
22,596,518 original instructions and compares 13,208,554 ordered events. Peak
invocation is 956,684 instructions / 545,912 events, below the fixed caps. All
148 consumed hashes match. The suite finishes in 350.07 seconds and removes
its owned temporary DLL directories. All 84 unit tests pass. The 379 new unique
bytes take the main C union to 31,161.

Twelve briefing fixtures reach the full display/input/fade flow; five additional
briefing cases verify prefix fault/provider boundaries. The first run completed
588 comparisons but failed its outcome gate because its palettes were already
stable. A separate bounded nonstable-palette comparison proved both backedges,
then a fresh complete campaign included that fixture. No report was accepted
from the incomplete run. All five numeric mutation builds/witnesses completed
in a bounded preflight before the final campaign.

The derived 0041 byte also feeds the later 4720 completion comparison, with
signed JNL at4724, and 48C7/48FB statistics paths. This is a static consumer
contract, not native acceptance of those untranslated controllers. Word+04's
raw briefing-numerator role is explained; its separate0044 runtime consumer
domain remains open. The full original-contract campaign is a separate gate
after the shared DIV change; this local evidence makes no aggregate or
full-game acceptance claim.

The full tools/verify.py --contracts gate passes in 479.67 seconds after the
shared DIV change. All 180 recorded inputs match. Main82,906 ASM bytes and all
63 relocations remain exact, as do the three executable sound dependencies.
The static frontier stays at115 UNKNOWN byte runs / seven unresolved transfers.
This is fresh original-contract evidence; unrelated native reports are not
renewed, and aggregate/full-game acceptance remains open.
