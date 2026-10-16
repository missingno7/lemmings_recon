# Connected input contracts

The exact physical input_poll.asm module is [418C,4334): 424 known instruction
bytes / 171 sites. PollMousePosition is [4252,42A1), 79 bytes / 40 sites. The
parent owns [418C,4252) and [42A1,4334), 345 bytes / 131 sites, and shares the
mouse tail. These extents must be unioned, not added twice. Port callbacks add
152 known child bytes, excluding UNKNOWN4395/4398; the EOI leaf is unrelated.

Mode byte DS:25A6 selects a frame-free JMP to mouse for zero, a live indirect
callback for one, and accelerated keyboard input for every other byte. The mode
is read again for the second comparison; memory providers may change it. The
known callback identities in DS:25A0 are 4252 (initial image word), 4334 and 4359
(calibration writes at4A68/4A80). Their target domain is incomplete. C stops before
CALL AX on an unknown target after the preceding PUSH DX has executed; it does
not replace an unknown target or claim the missing code cannot affect gameplay.

The callback CALL writes 42A7 on live SS:SP. Its actual RET is consumed and checked
before POP DX reads the saved word. The following gate compares DL alone with
FF; a nonzero DH does not change that predicate. Port wrapper stops and changed
measurement returns retain their actual child state and status. A mouse callback
uses the same body as the mode-zero tail but has the real callback frame.

Mouse polling pushes ES, DS, BP, SI, DI, AX, BX, CX, DX, DS, then requests INT33
with AX=3. The declared external provider enters the current IVT33 target after
real FLAGS/CS/IP frame writes and returns immediately before IRET. It can change
canonical memory and full register state, including SS:SP. Missing bindings,
provider stops and changed interrupt returns remain explicit. This contract does
not claim to execute a mouse driver or deliver asynchronous interrupts.

The first POP DS after IRET chooses the data frame for button/pointer writes.
Only suppression byte DS:200B exactly FF skips the BX button copy. Returned CX
and DX are clamped with signed comparisons to 8..148 and 8..C8. Even a lower
mouse clamp continues through the upper comparison, whose flags reach the store.
Subsequent pops restore registers and segments from actual live memory; outer
RET consumes the current stack. Original entry registers are not shadow saves.

DS:200B also gates keyboard special button mapping in INT09; 11F4/1358 set FF.
DS:1FC7 is the shared keyboard bitmask: the IRQ producer ORs make bits and ANDs
release bits at176E/1776. Keyboard polling tests the literal groups 0C03/0401/0802
and 300C/1004/2008, plus4010 for button bit0. DS:0016/0018 hold the horizontal and
vertical acceleration step states, not calibration baselines. The startup clear
initializes them. When no direction in an axis group is held, its state resets
to16; held groups decrement or increment with the original sign tests, wrap and
signed upper clamp to32.
After storing both states, two logical shifts and SUB4 produce pointer deltas.
Pointer bounds use signed comparisons; lower keyboard clamps skip the upper
comparison, unlike the mouse path. All these fields remain shared canonical RAM.

The calibrated path subtracts both live baselines DS:25A2/25A4 exactly once before
reading the scale byte DS:2005 into AL. Values within -8..8 leave each pointer
unchanged. The X shift counts are 5/3/2 for selector2/3/4 and6 otherwise; Y uses
4/2/1 and5. These are arithmetic shifts of wrapped 16-bit deltas, with one extra
X shift. Selectors are unchecked; no normalization or symmetry fix is inserted.
Pointer adds, clamps and stores retain their literal flags and alias order.

The shared verification runner and full-state comparator are described in
verification.md. Case providers and independent expected input arithmetic remain
in the focused suite; neither is the game's runtime implementation.

## Focused acceptance

The registered input_poll campaign passes 63 fixtures at both boundaries:
126 original/native comparisons, all 243 connected sites and 91 direct jump
outcomes. It executes 7,486 original instructions and compares 4,644 ordered
events. Those events include 592 declared interrupt-transport accesses and 96
constructed provider accesses across 34 calls; they are not external original
instruction coverage. Seven distinct completed mutants are detected.

The independent expectations cover mouse signed clamps/suppression, keyboard
step and pointer arithmetic, callback button/sample results, wrapped calibration,
scale/dead-zone asymmetry, and live outer returns. Fixtures also exercise moved
interrupt stacks, frame/IVT aliases, changed saved words/targets, missing services,
reserved flag normalization, physical/offset wrap, DF/IF and relocation. Unknown
callbacks stop before CALL; their bodies remain unverified and unresolved.

The report pins 26 consumed inputs. Workers use a 420-second timeout, 384-MiB
process-tree commit cap, 100,000 instructions and 10,000 callback events per
comparison. Budget failures earn no mutation credit. This adds 424 unique main
C bytes, bringing the ledger union to 26,014; previously translated port children
are unioned once. The migrated port-I/O regression separately passes its original
102 comparisons/75 sites/eight edges/ten mutants under the same shared engine.
These are scoped results, not complete timing, interrupt or game acceptance.
