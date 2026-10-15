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

These contracts leave table extents, state initialization, IRQ timing and whole
simulation readiness open. The next state0010 body is23F3..254E,348 bytes/
127 sites. Its special+28==11 path temporarily adjusts X/Y, samples a pixel,
performs two three-byte exchanges and joins240F after resetting+28. The ordinary
path advances+28 modulo16 and enters240F only at0/8. Two CX&7 mask-shift loops,
five actual child CALL frames, live stack/record aliases and optional AX040A
INT61 must flow into the existing finish/interactions tails. A backward join
at254C is not a repeated pass through the special path. No known interior
cross-entry currently splits this state into separately owned handlers.
