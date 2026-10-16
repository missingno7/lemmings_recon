# Entity drawing loop at 3634

`DrawEntityRecords` owns 89 known body bytes and 35 instruction sites in
3634..366E and 3670..368D. Byte366F remains UNKNOWN. Its static caller at001BC
pushes001BF; that caller word remains live throughout this routine. The existing
decimal writer at4B68..4BBD is a shared tail, adding86 reachable bytes without
adding new translated bytes when the loop is ported.

## Record loop and state ownership

DI starts at `EntityRecordsBase`, DS:0088. Only CL receives the live
`EntitySlotBound` byte. A zero bound returns at368D without clearing CH,
`EntityDrawingPassCount`, or the output field. Otherwise CH and the pass count
are cleared, then each iteration pushes CX followed by DI onto live SS.

Only an exactFF byte at record+26 (`EntityRecordDrawingSkipGate`) skips the
record. Other values increment the live byte pass count, with byte wrap and
INC's preserved CF, before calling minimap and dirty marking. DS:0045 is the
drawing pass count; it is distinct from the completion counter at0046.

The live word at `DrawingCallbackSlots+0E`, DS:003C, is compared with the
current record callback at+14. Equality plus signed byte frame+28 >=1 selects
the point path: frame values01..7F qualify; 00 and80..FF do not. This comparison
does not perform a callback dispatch. The point path pushes DI, exchanges SI
and DI, and directly calls6E83. It restores the actual saved DI afterward.

The other active path sets `EntityWorkGuard` at live DS:0050 toFF and calls
706F. Only a successful return to3678 clears that guard, using the returned DS.
On a child stop the parent does not execute that clear; provider changes to
the stored byte remain observable. Children may return a different DS; no parent save restores
DS or ES. All subsequent global and record reads use the actual returned roles.

The shared restore pops DI then CX. DI advances by2Dh with 16-bit wrap and ADD
flags. LOOP decrements the actual restored CX without changing those flags.
Neither a cached host record index nor the initial bound owns later iterations.
The field anchors describe observed uses; they do not prove a complete schema,
allocation, initialization, lifetime or maximum extent.

## Child frames and decimal tail

| CALL site | Child | Expected resume |
|---|---|---|
| 3651 | DrawEntityMinimapPixel,6FE2 | 3654 |
| 3654 | MarkEntityDrawingDirty,5726 | 3657 |
| 3669 | DrawEntityPointCloud,6E83 | 366C |
| 3675 | DrawObjectSprite,706F | 3678 |

Each CALL pushes its actual return word and executes the child's adapter. A
changed child return stops before any assumed parent continuation. A sprite
child's unknown callback or changed nested return likewise stops with all its
live state, including the work guard and stack frame.

After LOOP finishes, AL receives the live pass count and SI receives2095h,
`StatusEntityCountField`. JMP368A enters `WriteDecimalByteField` directly.
There is no synthetic CALL word. Its full decimal core writes through live DS,
updates AX/BX/SI/FLAGS, and reaches RET4BBD with the original caller word still
on SS:SP. Output/provider aliases may change that word before the actual RET.

The native logical core stops before RET368D or RET4BBD on READY=0. Its register
adapter consumes that live return only on READY. CHILD_STOP=1 propagates a
nonzero child status; CHANGED_CHILD_RETURN=2 retains a READY child's changed
CS:IP. Result child_entry/child_status identify a stopped child, with0/FFFF on
READY. Offsets and SP wrap at16 bits; a word's high byte follows its physical
low address by one, wrapping at20 bits.

This contract leaves UNKNOWN366F, arbitrary sprite targets, device providers,
IRQ timing and complete gameplay unresolved. Native acceptance requires the
bounded differential campaign and matching input hashes.

## Focused acceptance

The native campaign passes37 fixtures at both APIs:74 comparisons, all35 body
sites and all12 branch edges,53,510 ordered byte-bus events and ten completed
mutation witnesses. Full RAM, returned roles, defined FLAGS, ordered accesses
and VGA state match the pinned original. The separately retained original-only
campaign executes70,141 hook steps with no native calls. Its callback-word bus
observations do not add instruction sites or native comparisons.

The integrated static domain contains4,425 bytes/2,191 sites. These fixtures
execute2,002 sites and127 edges; they do not cover every child path. The parent
domain contains89 body bytes plus the existing86-byte shared decimal tail.
Only89 unique main C bytes are new, taking the ledger union to22,998.

Independent assertions check stale output on the zero bound, skipped and active
255-record bounds, the byte count wrap and decimal bytes. Large constructed
record ranges alias other mapped data; fixtures set their intended skip gates
after other inputs, without a second record/state copy. Other fixtures verify
saved DI/CX, changed direct and nested returns, known then unknown callbacks,
returned DS with count200, output/RET aliasing and physical20-bit return wrap.

Run `tools/difftest.py entity_drawing` for the native campaign, or
`tests/entity_drawing.py --original-only` for its reference scope. The suite
uses420 seconds/384 MiB per process, with120,000 instructions and50,000 events
per original pass. Callback exhaustion, timeout or commit-limit failure cannot
count as a mutant mismatch. Reports are build/entity-drawing-differential.json
and build/entity-drawing-original-differential.json; acceptance requires their
exact matching scopes/input hashes. This does not renew aggregate evidence.
