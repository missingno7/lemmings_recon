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
Next translate21B0..22DE while retaining the distinct direct20E2 inactive exit,
real5DC6 return2205 and optional INT61 return22A0. Continue other state blocks
and the live iteration/scan parent with all platform and changed-target seams.
