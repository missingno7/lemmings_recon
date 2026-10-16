# Entity action ownership and shared feedback

The3150 action body occupies[3150,3634):1,221 known bytes/402 instruction
sites and31 explicitly UNKNOWN bytes. Its210 branch outcomes and three INT
sites are static accounting, not native acceptance. Unknown holes remain3160,
3199,31BC,35A1,35AB and357E..3597. Selector8 jumps directly to3598; that
known edge does not prove the skipped bytes dead. The only known near CALLs
are01AD and01C5, returning01B0/01C8.

## Shared feedback boundaries

RequestEntityActionFeedback at31E5..320B owns39 known bytes/13 sites/eight
jump outcomes. The first gate requires live DS:2010!=FF and DS:25A7&1 before
AX0313 INT60 at31F6. Its actual continuation31F8 rereads the external gate
through the returned DS. This second gate requires DS:2010==FF and DS:25A7&3
before AX0404 INT61 at3209,return320B. Both transport cores retain explicit
unbound-vector,untranslated-child,changed-driver-child and changed-IRET seams.
The PC transport returns every live register and segment; the external
transport returns AX/DS/CS/SP/FLAGS while preserving its other declared roles.

The external-only RequestEntityActionService0412 at3287..329A owns20 known
bytes/seven sites/four outcomes. It uses the latter gate and AX0412 INT61 at
3298,return329A. Combined ownership is59 bytes/20 sites/12 outcomes. Both
entries are JMP/fallthrough tails: no new near CALL frame belongs to them.
Their logical cores stop before their actual near RET; adapters consume the
live SS:SP outer word, including changed segments and physical word wrapping.

Known31E5 entries are fallthrough31E1 and JMPs326E,32B7,331C,34C8,353D,3578,
3619. Known3287 entries are34F3 and35CC. No external interior entry into these
two tails is currently known. The320C single-byte RET is a separate shared
tail, to be composed with the action caller rather than assigned to feedback.

## Selection and action fields

The ledger names live DS fields without creating host copies or proving extents:

| Offset | Name | Producer/consumer contract |
|---|---|---|
|0058|EntitySelectedRecordOffset|3DC6/3DDA write SI;317C loads the live selected pointer|
|005A|EntityAlternateRecordOffset|3D9C writes SI;four fallback paths replace SI before a fresh eligibility test|
|005F|EntityAlternateSlotIndex|3D05 setsFF;3D99 stores wrapped0043-CL;action fallbacks require!=FF|
|0061|EntityActionPressLatch|3170 testsFF;3177 setsFF;31BE clears only after earlier gates pass and input bit0 clears|
|0063|EntityCandidateCount|3CF6 clears;3DA1 byte-INCs on a candidate;3161 tests nonzero|
|0082|EntityActionSelector|0422 initializes2;input updates wrap2..9;3150 retains signed comparisons|

3150 returns when update gate002B==FF,work guard0050==FF,or candidate count
0063==0. Those returns do not clear the press latch. If input word0014 bit0
is clear after those gates,31BE clears the latch and returns31C3. Otherwise,
latchFF suppresses work; the remaining path sets latchFF before selector
validation. Signed AL<2 includes80..FF. Selectors2..9 dispatch to329B,3557,
31C4,3336,32BD,34CE,3598,320D; other values return31BD. Action counts remain
ordinal LevelActionCount0..7 at006A,006D,0070,0073,0076,0079,007C,007F.
ApplyLevelHeader fills their low bytes from header+08..+16. Historical skill
labels and bounded count/index domains have not been inferred.

The candidate producer3CDE initializes its counters/sentinels, walks live
2D-byte records and uses unchecked coordinate tests. DS:005F is a slot index
with FF sentinel; no proven maximum prevents the index/sentinel collision.
Alternate pointers are not prevalidated host objects. Each action's fallback
must use the freshly loaded SI and reread the original eligibility mask.

## Interaction-map producer

The successful selector5 path reaches3464..34CA after the3348..341F map
checks and3422..3463 ordered transition. This103-byte/46-site suffix saves
SI on live SS, sets ES from DS without restoring it, and installs02/0A/03
rows in the SS map while saving nine displaced cells into the record. DF=0
stores at+16..+1E; DF=1 only reverses the STOSB destination while explicit
INC SI and literal019D row advances still move through the map forward.
Its POP SI rereads the live stack word before JMP31E5. The restored283B
pattern leaf is already native; producer and broader action integration stay
open until their own composed verification. No shadow record, added clamp or
corrected DF behavior may replace these aliases.


The shared feedback native gate passes68 fixtures at core/actual-RET-adapter
boundaries:59 unique bytes/20 sites/all12 outcomes,3,786 ordered events and
eight completed mutants. A48-case enable/options matrix checks both entries.
Additional cases cover PC-returned DS/SI/CX and the fresh external gate, both
driver kinds,unbound vectors/bindings,PC's untranslated child target,changed
PC child and INT60/61 returns to another valid tail,DF,word wrapping and VGA
stack frames. These tails always load AH4 before INT61,so an untranslated
external AH0..2 service is not claimed as exercised here. Limits are512
original instructions/2,048 events per call and180 seconds/384 MiB process/
640 MiB Windows tree. See `build/entity-action-sound-differential.json` for
exact hashes and per-case paths. The remainder of3150 and broader input,
record-validity and IRQ/device scheduling contracts remain open.

## Small selector actions and dispatch prefix

The independently understood actions own107 unique known bytes/31 sites
and18 conditional outcomes:selector2[329B,32BD),selector3[3557,357E),
selector4[31C4,31E5) and shared RET320C. Only their dispatch JMPs enter the
three bodies; other actions also reach320C. Success reaches31E5 without a
near CALL,so its native composition must retain the existing SS:SP return.

Selector2 requires count006A!=0,record+24 bit0 clear and +08&0103 clear.
It decrements the live count and replaces the whole +24 byte with01.
Unlike the other consuming action paths,it does not reset refresh counter006C.
Selector3 requires count006D!=0,+25==0 and +08&0103 clear; it stores+25=FF
before decrementing the live count,then clears006F. This order is observable
when the record field aliases the count. Selector4 requires count0070!=0,
+20==0 and +08&C003 clear; it decrements0070,clears0072,then stores+20=4F.
Record/global overlap,wrap and the separate memory RMW flags remain explicit.

The named dispatch prefix[3150,31C4) has113 known bytes/43 sites/28 outcomes,
excluding UNKNOWN3160,3199 and31BC. Its own physical ledger size covers only
that prefix; the complete reachable3150 action graph still has1221 known
bytes. Ordinary returns are31BD and31C3. The native prefix connects
selectors2/3/4 directly and stops at the exact untranslated entries for
selectors5/6/7/8/9. A scoped prefix does not establish those action bodies or
the complete3150 caller. All256 selector bytes retain signed JL behavior and
the sequential CMP flags,including ordinary31BD returns for80..FF and0A..7F.
The latch is set before both pointer and selector reads,even for invalid values.

The eight ordinal action-count triples now have ledger-owned names for their
low count,display snapshot and refresh counter. At39CE snapshots initializeFF
and counters0. The repeated3BA5..3CDD paths skip a nonzero count equal to its
snapshot; otherwise they compare the counter to2,update the snapshot and set
the counterFF only on equality,then byte-INC it before calling762A. That
callee uses AL as the two-byte display slot and AH for decimal digits drawn
through VGA. Action successes reset the corresponding counter as recorded
above; no bounded range or general scheduling invariant follows from this.
The names describe live fields; they do not resolve stored UNKNOWN bytes.

The remaining five action bodies own942 known bytes before shared tails:

| Selector | Physical body | Known bytes | Next dependency |
|---|---|---:|---|
|6|32BD..3335|121|Fresh alternate-record eligibility and ordered transition|
|7|34CE..3556|137|0412 early feedback and alternate-record fallback|
|9|320D..3286|122|Nibble exclusion and alternate-record fallback|
|8|3598..3633|154|Direction/nibble exclusions,0412 path;UNKNOWN35A1/35AB excluded|
|5|3336..34CD|408|SS interaction-map checks,ordered transition and nine-cell producer|

These are static boundaries,not executed or translated coverage. Their common
INT/RET contracts remain those of the already verified feedback tails.

## Remaining transition and alternate-pointer contracts

Selectors6/7/9/8 have32/39/33/46 instruction sites and13/18/13/22 owned
branch outcomes respectively,including unconditional JMPs. Their local bodies
contain no CALL or stack/segment change. All local operands use live DS; SI
may be replaced by the fresh alternate pointer when005F!=FF. Shared feedback
and actual RETs keep their own segment/stack seams.

Selector6 first requires count0076!=0 and the unsigned wrapped sum
word[SI+2]+word[SI+6]>10. Eligibility mask isF5EF. Only a mask failure selects
alternate SI and rechecks that mask; it does not repeat count or sum gates.
The32D6 transition decrements0076,clears0078,sets state+08=0080 and writes the
ordered fields. It reads callback slot+8 before setting+2A=FF and storing the
callback+14,then ANDs+24 with1 before JMP31E5.

Selector7 uses count0079 and eligibility maskF76F. Alternate selection rejoins
34DC before the active record's+2B low-nibble checks. It rejects nibble7 when
+27==1,otherwise8. Nibble9 reaches3287's0412 service before consuming a count
or modifying the record. Normal transition34F6 decrements0079,clears007B,
ANDs state withF56F then ORs0200. After ordered fields and+2A=FF,it reads
callback slot+6,stores+14 and ANDs+24 with1 before JMP31E5. The eligibility
and transition masks deliberately differ.

Selector9 checks count007F and selected+2C low nibble!=9 before eligibility
maskF57F. A mask-failure alternate record joins3224 after just its mask test:
it bypasses the original count and nibble checks. Transition decrements007F,
clears0081,ANDs stateF57F then ORs0010,and writes ordered fields. Callback
slot+0A is read and stored before+1F=8,+2A=FF and+24 AND1,then JMP31E5.

Selector8 uses count007C and maskFD6F; alternate selection rejoins35AC before
+2C low nibble!=9 and the same direction/nibble tests as selector7. Nibble9
at+2B reaches3287 before count consumption. Transition decrements007C,clears
007E,ANDs stateFD6F then ORs0800,and writes ordered fields. It reads callback
slot+8 and stores+14 before+2A=FF,+24 AND1 and a final word INC[SI+2],then
JMP31E5. UNKNOWN35A1/35AB remain excluded; known jumps target35A2/35AC.
All four failure paths reach320C. These are static contracts pending native
translation; no historical action names or record/table extents are inferred.

## Scoped native acceptance

The selector2/3/4 cluster passes39 fixtures at core/actual-RET-adapter
boundaries:107 own bytes/31 sites,all18 conditional outcomes plus four direct
JMP edges,1,122 ordered events and seven completed mutants. Independent memory
projections check eligibility and ordered stores,including whole-byte +24
replacement without a refresh reset,marker/count and refresh/marker aliases.
The count80 cases expose signed DEC overflow before feedback overwrites flags.
PC,AdLib,Tandy,unbound vectors,changed IRET,returned DS,DF,physical stack-word
wrap and a VGA-backed outer return are compared through native feedback.
Limits are1,024 original instructions/2,048 events per call and180 seconds/
384 MiB process/640 MiB Windows tree. See
`build/entity-actions-basic-differential.json` for exact input hashes.

The dispatch prefix passes279 fixtures at both boundaries,including all256
raw selector bytes:113 own known bytes/43 sites/all28 conditional outcomes,
6,964 ordered events and six completed mutants. Independent gate/latch/AX/SI
and event-order checks precede native comparison. A latch-write provider changes
the selected pointer and selector before their later reads. Native basic actions
and feedback retain raw child diagnostics and actual outer returns; supported
paths include unbound/changed PC returns and returned DS. Other selectors stop
at their exact untranslated action entries. The512-instruction/4,096-event
per-call budgets and240-second/384 MiB process/640 MiB tree limits are hard.
See `build/entity-action-dispatch-differential.json`. Shared child bytes are
counted once; these scopes add220 unique known bytes,not the whole3150 body.
All31 UNKNOWN bytes and broader input/record/IRQ timing contracts remain open.
