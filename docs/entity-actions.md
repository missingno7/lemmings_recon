# Entity action ownership and shared feedback

The physical3150..3633 block lives in `src/entity_actions.asm`,with start/end
assertions and unchanged emission order. The following3634..368D untranslated
draw-call loop is separate in `src/entity_drawing_calls.asm`. These are maintained
source boundaries,not historical linker modules or additional resolved bytes.

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
|001A|EntitySelectionPresent|3DAF sets00 after a nonzero scan;3DE8 setsFF for a selected index;zero entry leaves it stale|
|0058|EntitySelectedRecordOffset|3DC6/3DDA write SI;317C loads the live selected pointer|
|005A|EntityAlternateRecordOffset|3D9C writes SI;four fallback paths replace SI before a fresh eligibility test|
|005C|EntityPreferredRecordOffset|3D8E writes the last preferred hit;3DD3 reads only when its index is notFF|
|005E|EntitySelectedSlotIndex|3CFB setsFF;3DC3/3DD7 copy the chosen bucket index;3DDE tests its live value|
|005F|EntityAlternateSlotIndex|3D05 setsFF;3D99 stores wrapped0043-CL;action fallbacks require!=FF|
|0060|EntityPreferredSlotIndex|3D00 setsFF;3D8B stores wrapped live0043-CL;FF can collide with a produced index|
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
pattern leaf and selector5 producer now have scoped native acceptance and two
actual producer/restorer handoffs, detailed below. No shadow record, added clamp or
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
exact hashes and per-case paths. Broader input,record-validity and IRQ/device
scheduling contracts remain open; the current action composition is below.

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
bytes. Ordinary returns are31BD and31C3. The native prefix now connects all eight selector cores directly. Its own
byte accounting stays separate from their independently tested domains. All256 selector bytes retain signed JL behavior and
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

The five later action bodies own942 known bytes before shared tails:

| Selector | Physical body | Known bytes | Next dependency |
|---|---|---:|---|
|6|32BD..3335|121|Fresh alternate-record eligibility and ordered transition|
|7|34CE..3556|137|0412 early feedback and alternate-record fallback|
|9|320D..3286|122|Nibble exclusion and alternate-record fallback|
|8|3598..3633|154|Direction/nibble exclusions,0412 path;UNKNOWN35A1/35AB excluded|
|5|3336..34CD|408|SS interaction-map checks,ordered transition and nine-cell producer|

These physical boundaries do not add shared-tail bytes again. Their native
acceptance and common INT/RET contracts are recorded below.

## Transition and alternate-pointer contracts

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
All four failure paths reach320C. Native acceptance is scoped below; no
historical action names or record/table extents are inferred.

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

The complete dispatch composition passes290 fixtures at both boundaries,
including all256 raw selector bytes:113 own known bytes/43 sites/all28 owned
conditional outcomes,8,244 ordered events and six completed mutants. Its own
cases execute376 of402 integrated sites and110 integrated conditional outcomes;
the separate leaf matrices jointly execute all402 known sites. All eight
selector cores and shared feedback use direct logical jumps on canonical RAM,
with actual outer RETs and raw child diagnostics. Independent gate/latch/AX/SI
and event-order checks precede comparison. Latch-write providers retain live
pointer/selector reads; focused cases cover every new action,alternate joins,
early0412 services and DF-sensitive map production. The512-instruction/
4,096-event per-call budgets and240-second/384 MiB process/640 MiB tree limits
are hard. See `build/entity-action-dispatch-differential.json`. The known
1,221-byte body is now composed; all31 UNKNOWN bytes and broader input/record/
IRQ timing contracts remain open. This pass adds942 unique known bytes.

The selector6/7/8/9 cluster now passes186 core/actual-RET-adapter fixtures:
534 unique known bytes/150 sites/all66 owned outcomes,10,154 ordered events
and ten completed mutants. Single-bit eligibility probes cover all16 state
bits; direction-nibble matrices retain high bits and both exact direction
branches. Independent eligibility/transition checks include alternate join
bypasses and rechecks,service paths consuming no count,selector7's intermediate
AND write before OR,late callback aliases and full-word/count overflow. PC,
AdLib,Tandy,unbound/changed-IRET/returned-DS seams,DF,physical stack wrapping
and VGA returns remain explicit. The shared typed Call/Result boundary and
bounded native transport are reused from the basic action suite. Budgets are
2,048 instructions/4,096 events per call and240 seconds/384 MiB process/
640 MiB tree. UNKNOWN35A1/35AB and all other holes remain unresolved. See
`build/entity-actions-advanced-differential.json` for exact input hashes.

Selector5 now passes56 core/actual-RET-adapter fixtures:408 known bytes/
158 sites/all73 owned outcomes,6,586 ordered events and eight completed mutants.
A9x3 rejection matrix checks every map cell against02/0A/03. Independent
ordered memory projection retains map/record overlap and map writes changing
the saved SI word; providers exercise live AX/DX/ES saves,late callback reads
and producer rereads after the checks. DF only reverses the STOSB destination.
Word wrapping,VGA SS access,feedback seams and instruction-phase RMW flags
are checked. Two actual native producer-to283B restoration handoffs restore
all nine original cells with DF clear. Budgets are768 original instructions/
8,192 events per call and240 seconds/384 MiB process/640 MiB tree. See
`build/entity-action-map-differential.json` for exact input hashes. This adds
408 unique bytes; the reused feedback/RET/restoration domains are counted once.

## Candidate selection and formatter composition

`SelectEntityCandidate` at3CDE,called at01BF and returning01C2,owns393 known bytes/140 sites
in physical[3CDE,3E6F). Eight one-byte holes remain UNKNOWN at3D26,3D44,
3D4B,3D57,3D66,3D70,3D77 and3DE7. Its only RET is3E62. A nonzero frozen
entry CL from0043 controls1..255 scans of2D-byte records starting0088; zero
returns before clearing candidate fields,so stale0063/0058 state is possible.
Inactive+26==FF records still consume an iteration. Geometry uses wrapped,
signed comparisons and the original unusual0680-to00D0 X-bound replacement.

After each hit,live record+24 bit80 or state+08&8B90 selects preferred bucket
005C/0060; otherwise005A/005F receives the pointer/index. Later hits overwrite
earlier hits. The index rereads live0043 and subtracts CL;0063 counts both
buckets. Pointer fields are not cleared with the FF index sentinels.
InputButtonsWord mask0002 forces005F/005A; when clear,0060/005C wins if its
index!=FF,otherwise the routine falls back to005F/005A. The chosen pointer
and index become0058/005E. Mask0002 is stated as a value,without assigning
an input meaning or confusing it with bit number2.

A valid selection calls the separate4B68 formatter at3DF3 (return3DF6),then
reloads0058 and copies seven live template bytes to2083..2089. Template
addresses48BF,48C6,48D4,48DB,48E2,48E9,48F0,48F7,48FE and490C remain live
DS data; no historical action names are inferred. Formatting receives the
candidate count in AL and destination208B. The4B68 `WriteDecimalByteField` body is86 bytes/40 sites,
with shared4B91 suffix entered separately from4BBE `WriteDecimalBytePair`
(four additional bytes). The pair entry accepts every AL byte without a
hundreds reduction:255 produces`I5`. Both entries preserve BH and discard AH.
It fills spaces,omits leading zero digits and writes significant digits from
the original SI onward:decimal0 produces`0  `,10 produces`10 `,100 produces
`100`. Digits are left-aligned with trailing spaces; SI advances by their
count,including the final units digit. BL counts emitted prefix digits and
BH is preserved. This differs from the fixed three-digit4BC2 helper.
Both formatter entries now have native acceptance, and3CDE composes the actual
stack frame with an explicit changed-return stop. The physical modules are
entity_selection.asm and decimal_fields.asm; their surrounding suffixes retain
unchanged physical order. See decimal-field.md for the field/flag contract.
Game scheduling and record allocation extents remain open.


`tests/entity_select.py` passes51 fixtures at both logical-core and actual-RET
adapter boundaries:393 own known bytes/140 sites/all69 CFG outcomes,23,800
ordered bus events and nine completed mutants. All ten template choices and
signed geometry rejection/clamp paths are represented. Independent ordered
memory projection checks candidate count, chosen bucket/index/pointer, stale
zero-bound outputs, formatted text and the live saved/CALL return words.
VGA DS/SS, DF, changed selected-pointer/template providers, FF sentinel
collisions and the actual changed formatter return remain explicit. Entry
FLAGS are admissible CPU register values, including the fixed bit1.

The full255-slot constructed scan overlaps the output row:record182 begins
at2086, so clearing2083..208D forces its first four words to2020. In the
dense fixture that record cannot pass the original bounds and the count is
254, with final slot indexFE and formatted`254`. This alias is retained,
not repaired. A separate provider installs FE after count initialization;
the next live INC produces FF and the formatter receives255. No record-array
extent or collision-free count/index domain is inferred.

The native suite keeps20,000 original-instruction and callback-event caps per
call inside240-second/384 MiB process/640 MiB Windows-tree workers. Completed
mutant mismatches are distinct from oracle failures and budget exhaustion.
The report records exact input hashes; broader game scheduling remains open.


Four focused native producer-to3150 handoffs pass in
`tests/entity_select_actions.py`. Each runs the actual selection adapter through
RET to01C2, then feeds that exact memory and every returned register/segment
into dispatch. Only the real near-CALL frame for01C5 is added, with return01C8.
Preferred and mask0002-forced fallback buckets reach selectors2/3/4. Whole
RAM, flags and ordered accesses match the originals; independent checks verify
the selected action's counter/record update and unchanged unselected record.
The union is216 executed sites (157 producer/formatter and59 dispatcher), with
618 bus events. It adds no translated bytes or mutation credit. The intervening
3AC8 display call is omitted explicitly; full main-loop behavior remains open.
