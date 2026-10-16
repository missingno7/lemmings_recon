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
