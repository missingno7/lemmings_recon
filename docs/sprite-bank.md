# Sprite bank copy and mask at 5BB0

`CopySpritePlanesAndAppendMask` is an 86-byte, 45-site leaf at 5BB0..5C05.
Its 59BB caller supplies raw sprite planes; it has no child calls or shared
tails. The ordinary nonzero, DF-clear layout copies DH planes of DL words
from DS:SI to ES:DI, then appends DL word masks formed by OR across the copied
planes. It reads back live ES memory, so overlap and providers remain visible.

The entry pushes SI and keeps the initial DI in BP. Each plane pushes CX,
sets CL=DL and CH=0, executes sequential REP MOVSW, pops actual CX, then
decrements CH. DH=0 therefore means 256 planes; DL=0 makes REP copy no words.
The mask outer loop uses CH=DL as another byte do-while counter, so DL=0
emits 256 masks. Its inner CH=DH loop likewise visits 256 planes for DH=0.
DX=0000 consequently executes 65,536 inner OR iterations, with zero copy words.

MOVSW and STOSW follow DF. The mask source cursor always advances forward:
SI+=2 between masks and SI+=2*DL between plane samples. Each mask pushes SI
and CX and later restores the actual SS words. Source, destination and stack
may overlap; no copied record, cached save or memmove semantics are implied.

Word accesses use physical(low)+1 with 20-bit wrap for the high byte. The mask
instead reads separate byte operands ES:SI and ES:(SI+1), whose effective
offset wraps at 16 bits. This distinction matters at SI=FFFF.

Final POP SI reads its actual save. A signed comparison of DI with 0010h
skips folding when DI is negative or below 10h. Otherwise AX=DI>>4, CX=old ES,
ES=AX+CX with 16-bit wrap, and DI&=0Fh. Thus final CX need not retain entry CL.
BP becomes 2*DL; BL is cleared while BH survives on intact frames. All actual
instruction-defined FLAGS, SS saves and the caller's return word remain live.

The portable core stops before RET 5C05; its adapter consumes the actual SS:SP
word and advances SP by two. The existing original-only bank models establish
ordinary nonzero/disjoint layouts, without proving DF, zero-count or alias
behavior. Native acceptance is recorded separately with exact report inputs.

## Focused acceptance

The producer passes 35 fixtures at both APIs: 70 comparisons, all 45 sites and
eight branch outcomes, 287,970 ordered byte-bus events and ten completed
mutants. Independent output equations check 4,544 bytes across both boundaries,
including ordinary banks, zero-count outputs and the split byte operand wrap.
Full RAM, returned roles, defined FLAGS, accesses and VGA state match original.

The DX=0000 case completes 65,536 inner OR iterations at each API. Its original
core uses 333,330 hook steps/134,660 events; actual RET adds one step/two reads.
These executed original instructions are separate from 45 translated C sites.
Other cases include DF, exact/forward/backward overlap, signed-fold boundaries,
segment wrap, physical/offset word wrap, changed saved SI/CX, and destination
writes into saved words and the caller's return. Exhaustion fails verification.

Five additional data handoffs compare the actual native producer and existing
native consumers in the same RAM: 80/104/112/128/140-byte banks at shifts 0/1/7/3/5.
Their ten native phase comparisons retain unchanged bank hashes, returned
DS/ES/FLAGS and explicit constructed consumer CALL words. Consumer events/sites
are recorded separately; this does not execute 59BB or add its bytes to C.

The leaf adds 86 unique main C bytes, taking the ledger union to 23,084.
Run `tools/difftest.py sprite_bank` or the bounded original-only mode
`tests/sprite_bank.py --original-only`. Limits are 360 seconds/384 MiB per
process, 500,000 original instructions and 160,000 bus events per invocation.
Reports are build/sprite-bank-differential.json and
build/sprite-bank-original-differential.json. Only matching scopes and hashes
establish this acceptance; unrelated campaigns and whole-game readiness remain
outside it. Next translate 5B11 and 5C06 before their 59BB caller.
