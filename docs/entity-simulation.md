# Simulation ownership and state convergence

The identified parent at `1F19` has 3,744 decoded bytes and 1,255 instruction
sites in the fresh static graph. Its eleven direct CALL children have scoped
native implementations. Those contracts retain their platform, IRQ, mutable
target and changed-return seams; they do not establish full simulation readiness.

## Live owners

The ledger owns the following original DS locations. These names do not create
host state or establish bounds for unchecked record accesses.

| DS offset | Ledger name | Observed owner and behavior |
|---|---|---|
| 002B | EntityUpdateGate | Exact `==FF` tests at1F19,30A6,3150,3944,3F52,3FEF,4032;4028 XORs FF |
| 0042 | EntitySlotsRemaining | 1F31 copies0043;1FEF decrements this live byte after each slot |
| 0043 | EntitySlotBound | 30CF selects `0088+[0043]*2D`;314B increments;1F2E loads the pass bound |
| 0046 | EntityCompletionCounter | 2335 increments before marking a state2000 slot;3ACE derives its displayed ratio over0047 |
| 004B | EntityScanRequest | 400B writes FF;1FF8 enables scan;203C clears on cursor equality |
| 004C | EntityScanCursor | 2005/2008 tests against0043;2026/2037 increments; no explicit reset at400B/203C |
| 0050 | EntityWorkGuard | 1F26/3670 set FF;1FFF/2041/3678 clear;3157 tests exact FF |
| 0088 | EntityRecordsBase | First2D-byte slot;30C9..30F3 selects and clears a slot;1FEC advances by2D |

Startup sets DS to09A9 and clears0000..2011 through the REP STOSB at002C..0031.
That establishes an initial zero on that path, not a permanent value domain.
There is no proven maximum slot count or whole-array extent. Records with
`+26==FF` remain inside the slot bound. The direct increment at314B does not
prove that aliases or unresolved code cannot write0043.

The scan checks live record+20, +26 and +08&3. An eligible slot receives
`+20=4F` at2033. The selected-slot RET at203B can leave0050 set. Neither004C
nor0050 may be replaced with a lexical counter or a function-local guard.
Driver-relative offsets such as Tandy's CS:004B belong to another segment.

## State priority and shared continuations

After the inactive/countdown/+24-bit80 gates,1F5E reads state word+08. Zero
selects2047. Otherwise the first matching mask wins in this order:

| Mask | Target | Mask | Target |
|---|---|---|---|
| 0002 | 2350 | 8000 | 2D0F |
| 0004 | 21B0 | 0400 | 2A6D |
| 0001 | 22DF | 0008 | 23BF |
| 0010 | 23F3 | 0020 | 254F |
| 0040 | 2637 | 0080 | 2693 |
| 0100 | 27E8 | 0200 | 287D |
| 0800 | 2B35 | 1000 | 22F5 |
| 2000 | 2326 | 4000 | 2340 |

State bodies OR/AND bits, so composite-word priority is observable. Historical
skill names are not inferred from masks alone. UNKNOWN/indirect edges remain
unresolved.

`FinishEntityInteractions` at1FE8 performs the real near CALL to2EC0. It pushes
1FEB through live SS and consumes the child's actual return word. The child
may return changed registers or segments, or stop at a declared sound seam.
`EntityIterationTail` at1FEB POPs ES from live SS, adds2D to SI and decrements
live DS:0042 before choosing another slot. It has no independent CALL frame.

`StoreEntityProbeHeight` at20D6 stores BP to+02 and uses a signed B4 threshold.
Its shared20E2 suffix writes+26=FF and jumps directly to1FEB. Other state
JMPs enter20E2 without performing the store or CMP. `FinishEntityStepHeight`
at2148 stores BP, adds live+06, and uses signed `<=0A` to select a clamp:
BP=9, subtract a fresh+06 read, store Y, negate+27 and clear+08 bit0008.
Otherwise it preserves the unclamped candidate. Both interaction paths compose
1FE8 directly, without invented frames for the original JMP entries.

These shared ranges own55 unique bytes/18 sites:1FE8..1FEA,20D6..20E8,
2148..2168. The20E2 entry overlaps its20D6 owner; bytes are counted once.

## Zero-state branch

`AdvanceEntityZeroState` at2047 increments+28 modulo8, adds signed+27 to X,
then checks signed X in[0010,0680). A bound failure negates+27. Otherwise an
actual CALL/RET to5DC6 returns at206B, with ES=A000 and the computed DI/AH.
The body samples the initial pixel and up to three lower pixels, incrementing
BP before each lower probe. Four empty samples select the ordered transition
stores at209A..20D2 and the20D6 tail. An occupied initial sample probes upward,
rereading DS:0004 before each step. Early clear samples enter2148; later clear
samples set bit0008, select frame8 and recompute BP from live Y-2. Seven occupied
upper samples test+24 mask01, selecting either NEG+27 or the2179 transition.

Transition stores and callback word reads at DS:002E/0030 retain their original
order. RMW callbacks observe entry FLAGS; arithmetic updates follow the write.
The branch has no RET and does not POP the parent's saved ES. Its361-byte/121-site
physical span includes52 bytes/17 sites owned by the shared tails. Its own C
ranges are2047..20D5,20E9..2147,2169..21AF:309 bytes/104 sites. Combined new
ownership is364 unique bytes, including the separate1FE8 CALL instruction.

The shared-tail suite `tests/entity_finish.py` passes24 fixtures at both logical
core and JMP-adapter boundaries: all18 owned sites/eight jump edges,95 integrated
interaction sites,2,026 ordered events and six completed mutants. It compares
whole RAM, every returned register, defined FLAGS and ordered bus/device state.
Fixtures cover both signed thresholds, wrapped additions, the clamp's fresh+06
read, byte-only inactive marking, physical/offset wrap, real CALL/RET aliases,
VGA and explicit sound-child statuses. Defined flag masks flow into the child
oracle across the real CALL. A constructed provider changes+06 after its first
complete word read; the original observation changes it at the next instruction
boundary so that both models consume the same first word.

The zero-state suite `tests/entity_zero_state.py` passes37 fixtures at both
boundaries:309 owned bytes/104 sites/all33 owned jump edges,182 integrated main
sites,5,094 ordered events and eight completed mutants. It checks every probe
edge, signed and wrapped coordinates/heights, transition stores, live pitch,
callback/record/stack aliases, changed actual pixel and interaction returns,
DF, full RAM and VGA bus/device results. The interaction-map fixtures are neutral;
sound/interrupt domains remain in the shared-tail and child gates. Raw-entry
fixtures also exercise nonzero initial state words without claiming parent
reachability for those constructed states.

Both workers use180-second/384-MiB process/640-MiB tree bounds and hard callback
limits. Original limits are64 shared-prefix instructions plus512 child instructions,
or2,000 zero-state integrated instructions; event limits are1,024 and2,048
respectively. Callback errors and exhaustion fail verification and earn no mutant
credit. Input hashes must match the retained reports; file preservation does not
refresh evidence. No game boot or native timing claim is involved.

This is scoped verification, not full original/native campaign acceptance.
The following five entries continue that bottom-up composition. The live
iteration/scan parent and remaining states retain their platform and
changed-target seams.

## State0004 and neighboring cadence entries

The21B0 entry owns303 bytes/87 sites through22DE. Parent1F7D selects it after
earlier-priority masks. Its+28 cadence is modulo4. The unsigned+23<=10 test,
or a zero+25 byte, selects the actual5DC6 CALL at2202 (return2205). Otherwise
the ordered21C6..21FB stores select state0400 and live callback DS:003A.

After pixel setup, BP is read from live+02. An empty first sample increments
BP, checks signed BP<B4, then advances DI by live DS:0004. The second empty
sample repeats that threshold and step. Either early threshold failure JMPs
20E2 without storing Y. A third empty sample increments BP and byte+23 by3,
stores Y, then checks signed BP>=B4. An occupied sample stores Y first and
uses unsigned+23<=3C to choose the22A3 state-zero transition versus the2256
state-one transition. Callback words at DS:002E and all later fields remain
live. The state-one branch tests DS:2010 exactly FF and DS:25A7&3 before
AX=0408 INT61. Only matching CS:22A0 continues to1FE8; other service/return
seams stay explicit. No branch POPs the parent's saved ES or performs a RET.

The separate cadence entries own113 bytes/45 sites and18 direct jump edges:

| Entry | State mask | Span | Observed behavior |
|---|---|---|---|
| 22DF | 0001 | 22DF..22F4 | +28 modulo16; zero marks+26=FF inline |
| 22F5 | 1000 | 22F5..2325 | +28 modulo16; zero JMPs20E2; other values probe a displaced pixel |
| 2326 | 2000 | 2326..233F | +28 modulo8; zero INCs DS:0046 then marks+26 inline |
| 2340 | 4000 | 2340..234F | Memory INC+28, fresh AL read, equality with0E selects20E2 |

The displaced probe sign-extends+27, PUSHes AX, doubles AX three times and adds
it to live X in CX. Live Y supplies BX to6141. The actual CALL at2313 pushes
2316. Only after consuming its actual return word does POP BX consume the
original signed-delta save. The coordinate child also restores its own BX/CX/DX
from live SS words and sets ES=A000. A clear masked pixel adds the popped BX
to live X; an occupied pixel skips that addition. Both paths continue1FEB.
SS/DS aliases may change saves, source fields, masks and returned values.

The0046 name records the increment and the3ACE..3AEF ratio calculation; it does
not establish historical state names, an array extent or a global byte domain.
Startup zeroing and these direct references do not exclude aliases or UNKNOWN
writers. The four entrypoints have no known direct interior cross-entries;
their parent dispatch JMPs are1F8D,1FD5,1FDD,1FE5. The next handler at2350 is
outside these scopes.

`tests/entity_state4.py` passes36 fixtures at both logical-core/JMP-adapter
boundaries:303 new caller bytes/87 sites/all29 jump edges,151 integrated main
sites,16 sites in each pinned external driver,3,910 ordered events and eight
completed mutants. It covers all three probe outcomes, early inactive exits
without Y stores, byte+23 wrap, signed heights versus unsigned field tests,
live pitch/callbacks/stack/record aliases, normal AdLib/Tandy command0408,
unbound vectors/bindings and changed pixel/IRET targets. AH is fixed04 at229E;
the bound dispatcher path is supported, while wider driver commands retain
their existing untranslated seams. Constructed entry FLAGS use7FD5|2 with TF
clear; saved frame bytes remain live and unrestricted.

`tests/entity_cadence.py` passes23 fixtures at both boundaries:113 new bytes/
45 sites/all18 jump edges,23 integrated coordinate-child sites,654 ordered
events and eight completed mutants. These include signed displacement scaling,
actual6141 RET followed by the live POP BX, post-INC fresh reread, counter wrap
and store order, DF, RAM/VGA samples and physical/offset aliases. Another1,024
original-only prefixes execute all256 input bytes at each entry, comparing+28,
AL/AH and ZF with independent formulas. Each prefix executes four instructions
(three for2340) and stops before its conditional branch. This is separate from
the native fixture count and adds no C bytes.

The two scopes add416 unique bytes/132 sites; shared helpers are counted once.
Both workers retain180-second/384-MiB process/640-MiB tree caps. State0004 has
a2,000-instruction/1,024-event limit; cadence has256 instructions/512 events.
Unicorn hook cycles are collected during the prefix matrix, and worker/temp-DLL
cleanup remains mandatory after every outcome.

The state0004 oracle uses the existing independent original-instruction engine
with explicit main instruction spans, RET expectations, stop offsets and access
providers. It executes original bytes with one flowing defined-FLAGS mask;
INT clears IF/TF without defining arithmetic flags that were already undefined.
This avoids duplicating INT/driver transport between parent harnesses. It does
not introduce a game interpreter or replace original execution with C results.

## State0008 and state0002

State0008 at23BF..23F2 owns52 bytes/18 sites. Its actual5DC6 CALL returns at
23C2 before the first memory DEC of Y. Each of up to two upward probes rereads
DS:0004, replaces AL from ES:DI and ANDs AL,AH. A clear probe clears bit0008,
resets+28, and uses live Y+1 in BP; two occupied probes use live Y. Both paths
JMP2148 without adding a frame. Entry FLAGS reach the memory DEC/AND writes;
those instructions define their results only after the write phase.

State0002 at2350..23BE owns110 known bytes/45 sites. UNKNOWN2382 is excluded
from its C ranges and remains unresolved. The full-byte INC/write of+28 leads
to20E2 when AL equals34. Otherwise DEC AL preserves its residual value; only
zero enters the first-frame work. Live DS:2010 other than FF and DS:25A7 bit0
request AX030C INT60, whose actual IRET must return CS:2379. The live PC table
selects its scoped LoadEffect child; unbound vectors, untranslated table targets
and changed child/IRET targets stop explicitly. Returned registers and segments
feed every later record access.

TEST word+08,0100 selects the actual283B CALL with return2386. Its optional bus
preserves device access and live saved DX/ES/DI/SI; only after its actual RET
does the parent reread X/Y. Wrapped SUB/SHR/MUL arithmetic and live SS saves
select the unchecked SS interaction nibble. Nibbles9 and5 skip drawing; others
CALL5DF8 with return23BC. The full drawing path preserves its setup OUTs,
source/latch/mirror/pixel order, CLI/STI, live saved DS/SI and defined FLAGS.
Even an early clipped child changes registers and performs setup OUTs. Normal
state0002 paths JMP1FEB; no interaction CALL or parent POP ES is invented.

`tests/entity_state8.py` passes18 fixtures at logical-core/JMP-adapter
boundaries:52 new caller bytes/18 sites/all6 jump edges,1,976 ordered events
and eight completed mutants. It checks actual pixel and interaction returns,
first/second occupied and clear paths, signed height clamping, live pitch/mask,
stack/record/word-wrap aliases and VGA reads. Child byte ranges are not added
again. Each worker retains180 seconds/384 MiB process/640 MiB tree limits;
original calls have1,200 instructions and1,024 ordered events as hard bounds.

`tests/entity_state2.py` passes35 fixtures at both boundaries:110 new caller
bytes/45 sites/all20 jump edges,8,772 ordered events and eight completed
mutants. It includes independent complete-plane expectations for full drawing,
clipping boundaries, DF, pattern-to-mask handoff, both skip nibbles, all scoped
PC dispatch seams, live returned DS/SI, saved DX and changed pattern/mask returns.
The full drawing body and viewport are not shortened. Its hard bounds are
2,400 original instructions/8,192 events per call and180 seconds/384 MiB process/
640 MiB tree per worker. Callback exhaustion/errors fail verification rather
than crediting a mutant. Shared original execution now permits an explicitly
declared word-OUT provider and per-access-class event cap; existing defaults
and undeclared-OUT rejection remain intact.

Together these two parent scopes add162 unique caller bytes/63 sites. The
pattern bus extension adds no bytes to its existing66-byte translation. This
is scoped acceptance; full original/native campaigns with matching input hashes
remain required before aggregate coverage acceptance.

Table extents, state initialization, IRQ timing and whole-simulation readiness
remain open for the following three scopes.

## States0010,0020 and0040

The0010 body at23F3..254E owns348 bytes/127 sites and33 direct jump outcomes.
The raw+28==11 path begins before the cadence update. It saves live X and Y,
temporarily adds+04/subtracts Y by2, samples a pixel, then reads X before
restoring the two words through actual SS pops. Two pixel exchanges preserve
DI/CX/BX/BP saves; the second destination adds the fresh DS:0004 pitch. Resetting
+28 joins240F once;254C is a backward join, not a repeat of the special path.
The ordinary path increments+28 modulo16 and admits0/8 to240F.

The common0010 path saves BP=X, adds live+04 to X, pushes the altered X and
calls5DC6. Only after its actual RET does it restore X, increment live Y and
pop the saved X into CX. Signed Y>=B4 marks inactive through20E2. Both mask
loops are bounded by CX&7; SHR BX transfers CF into RCR DL, which defines only
CF/OF and preserves SZP/AF. LOOP changes CX without affecting FLAGS. The three
5EBA calls retain actual return words, DF stepping, live SS mirrors, pixel
samples and ordered OUTs; STI sets IF. A collision either selects state0004
or an unchecked SS map nibble. Nibble9 may issue native INT61 AX040A when
DS:2010==FF and DS:25A7&3 is nonzero; only the expected CS:24D0 resumes.
Transition callback002E is read after earlier stores. All finishes compose the
original JMPs without inventing a frame.

The0020 body at254F..2636 owns232 bytes/74 sites and13 jump outcomes. Its AL
cadence is modulo8. Values0..3 temporarily probe Y-7-AL; a clear pixel restores
Y, adds2, subtracts a fresh+28 and transitions to state0040 before2148. That
transition preserves callback+14. Values4..7 decrement Y and compare wrapped
Y+height against0A using unsigned JNA. Otherwise sign-extended+27 temporarily
shifts X around a5DC6 call, then restores X and probes eight live DS:0004 rows
upward. A state0004 transition clears bit0020, writes fields in original order,
reads callback002E late, NEGates AL from+27 and stores it with post-NEG FLAGS,
then adds the signed result to X twice. This is register NEG followed by MOV,
not a memory NEG. Both pixel calls check their own live near return words.

The0040 body at2637..2692 owns92 bytes/26 sites and7 jump outcomes. It reads
+28 into AL, INCs/ANDs AL with7 and performs one store with post-AND FLAGS.
Values5..7 continue at1FEB. Values1..4 subtract2 from live Y and reread BP before
2148. Zero performs ordered transition stores, including+06=FFF6, before a
late DS:002E callback read and a live Y-to-BP load. Thus the zero-path signed
clamp sees Y-10: Y20 clamps to19, while Y21 does not clamp. A record at SI002A
aliases the earlier+04=FFF8 store with callback002E; prefetching it is incorrect.

`tests/entity_state40.py` passes25 fixtures at both boundaries:92 new caller
bytes/26 sites/all7 jump outcomes,2,160 ordered events and eight completed
mutants. Its constructed RAM/VGA,DF,offset/physical-wrap and live stack/record
aliases retain the actual1FE8 interaction frame and normal1FEB boundary.
Workers have180-second/384-MiB process/640-MiB tree bounds; each original call
has1,600 instructions/1,024 events as hard limits. These are scoped results.

The shared original engine can now associate allowed RET sites with each
actual CALL site. It derives the expected CS:IP from that CALL, so a corrupted
return to another valid continuation of the same helper still stops. Its
one-bit carry-rotate mask retains prior defined SZP/AF and defines CF/OF.
Existing single-call contracts keep their original behavior.


`tests/entity_state10.py` passes48 fixtures at both logical-core/JMP-adapter
boundaries:348 new caller bytes/127 sites/all33 observed jump outcomes,
264 integrated main sites,11,578 ordered events and eight completed mutants.
Three independent plane replays check the composed exchanges, including the
known readback-mode-one register state. Changed targets are checked per actual
CALL, including a corrupted return to another valid caller continuation. An
INT61 saved-DS provider proves that stores after24D0 use the actual restored
segment and its live callback002E. The full original body and all three exchange
calls remain intact. Hard limits are4,096 instructions/4,096 events per original
call and180 seconds/384 MiB process/640 MiB tree per worker.

`tests/entity_state20.py` passes24 fixtures at both boundaries:232 new caller
bytes/74 sites/all13 jump outcomes,3,538 ordered events and eight completed
mutants. These cover both pixel calls, cross-continuation corrupted returns,
unsigned height wrap, signed velocity, cadence wrapping, live pitch, callback
aliasing, NEG-result write flags, alternate callback preservation and the real
shared-tail interaction frame. Its hard limits are1,200 instructions/1,024
events per call and180 seconds/384 MiB process/640 MiB tree per worker.

The three new scopes add672 unique caller bytes/227 sites and53 observed jump
outcomes. Child and shared-tail bytes are counted once. This is scoped native
acceptance, separate from full-game readiness or aggregate coverage acceptance.

## States0080 and0100

The0080 body is2693..27E7:337 known code bytes/115 sites and44 jump outcomes.
UNKNOWN holes26A1/26F6/26FF/2762 remain unresolved and excluded. Its sole known
external incoming edge is1FB5 to2693. Cadence increments AL modulo16 before
writing+28. PhaseA replaces AL with the unchecked record byte+21 and admits
unsigned values0..3 to the sound gates. Actual PUSH AX/PUSH ES precede optional
INT60 AX0313(return26C2); the returned registers and segments flow into fresh
DS:2010/DS:25A7 gates for optional INT61 AX0412(return26D5). POP ES/POP AX read
the returned SS:SP. Thus stack aliases can select AL9 after the sound path,
even though the earlier+21 comparison admitted only0..3. Phase9 calls5F0F
through return26E1, including its own nested5DC6 return5F57.

Zero cadence sign-extends+27, updates X/Y, saves velocity in BP and uses signed
X bounds10<X<680. The first two5DC6 calls return2703/2713 and sample a fresh
DS:0004 pitch above their pixel address. Only two clear samples decrement+21;
zero wraps to FF, while a result of zero takes the27A5 transition. The32F2
store of0C is one observed producer, not complete field ownership or bounds.
The third sample saves live X, adds BP twice and CALLs5DC6(return272F), then
restores X through actual SS memory. A saved AX surrounds a fresh pitch read
and three SHLs: the total subtraction is nine pitches. Failed samples or X
bounds NEG memory+27 before the2766 transition. With a clear third sample and
valid X, signed Y+height<=0A reaches2766 without NEG; a larger sum JMPs1FE8.
Both transitions read callback002E after earlier stores, load BP from live Y
and JMP2148 without adding a frame. Other exits retain1FE8/1FEB contracts.

The0100 body at27E8..283A owns83 known bytes/22 sites/four jump outcomes, with
sole known external edge1FBD to27E8. INC byte+28 and AND byte+28,0F are separate
memory RMW instructions: their accesses observe incoming FLAGS and the AND
rereads live memory. The actual5DC6 return27F2 precedes MOV AL,[ES:DI]/AND AL,AH.
A nonzero sample JMPs1FEB. A clear sample performs the ordered zero-state
stores and late callback002E read, then CALLs283B through actual return2838.
The pattern child retains live DS/SS saves, popped ES/DI/SI and DF-sensitive
string order. This handler has no2148 height update or interaction-tail call;
its normal exits both JMP1FEB.

The0080 native gate passes50 fixtures at both logical-core/JMP-adapter
boundaries:337 new caller bytes/115 sites/all44 actual owned jump outcomes,
254 integrated main sites,8,796 ordered events and eight completed mutants.
Two VGA fixtures also replay the register/latch/plane effects independently.
Fixtures retain opposite sound-gate polarities, PC-returned DS and live saved
AX/ES, changed IRET and direct/nested CALL returns, the wrapped zero counter,
three distinct probes, post-third-call live X restores, late callback and pitch
providers, signed limits and memory NEG's entry-FLAGS write. Per-call limits
are4,096 original instructions/4,096 events; worker bounds are180 seconds,
384 MiB process and640 MiB Windows process tree. See
`build/entity-state80-differential.json` for exact hashes and case boundaries.

The0100 gate passes19 fixtures at both boundaries:83 new bytes/22 sites/all4
actual owned outcomes,80 integrated main sites,2,726 events and six completed
mutants. A provider changes cadence after INC and proves AND rereads it; other
fixtures cover DF, sequential overlap, callback aliasing, RAM/VGA observations,
live pixel-produced ES, a naturally overwritten pattern RET and changed returns
to another valid caller continuation. Per-call limits are2,048 instructions/
1,024 events, with the same180-second/384-MiB process/640-MiB tree bounds. See
`build/entity-state100-differential.json`. Together these two scopes add420
unique caller bytes/137 sites/48 actual owned outcomes. Children and shared
tails overlap existing translations and are not added again. These are scoped
native results; the full1F19 parent and aggregate game acceptance remain open.

The following0200 frontier at287D..2A6C owns496 known bytes/169 sites, with
20 conditional and19 unconditional jumps:59 owned outcomes including conditional
fallthroughs. Its sole known external direct edge is1FC5 to287D; no interior
cross-entry or UNKNOWN hole is currently known. It CALLs5FAC(return28A4),6141
four times(28C7/28D6/28E5/28F4) and5DC6(return294E). INT61 AX040A returns2A6A
and flows into29C1, including returned DS. The2A00 nibble calculation reads
unchecked SS:[BX] only after live AX/DX pushes and pops. Its children have
scoped native contracts, while the0200 caller remains untranslated. The separate
0400 handler begins2A6D and precedes0200 in dispatch priority.
