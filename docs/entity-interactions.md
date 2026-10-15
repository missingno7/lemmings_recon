# Entity interaction cells and transitions

`ApplyEntityCellInteractions` at2EC0..30A5 has a maintained C core and actual
near-RET adapter:486 original bytes/162 sites, caller1FE8 and no decoded CALL
children. The five interrupt services remain explicit composed dependencies.
This is scoped native acceptance, not complete simulation or game acceptance.

The entry reads DS:[SI] and [SI+2]. Signed Y>=00B0 returns at2F3A. Otherwise,
it subtracts0010 from Y, logically shifts both words twice, saves X/4 and DX
through live SS, and multiplies the shifted Y by01A0. After actual POP DX/BX,
it adds low AX and0012 to BX and samples SS:[BX] at2EE6. The byte is stored
to record+2C, with AX saved on SS first. It then reads and sign-extends byte
record+27, subtracts0340 from BX, adds that signed word twice, samples SS:[BX]
again and stores it to record+2B. All offset arithmetic wraps at16 bits.
Neither signed coordinates nor the SS address are clamped. SS is live, with
stack/map aliases; it is not interchangeable with ES.

POP AX at2EFF rereads the saved word after those stores. The code copies AL
to AH and splits it into low/high nibbles. In an aliasing state these can differ
from the first sampled byte. The low nibble selects:

| Low nibble | Original continuation |
|---|---|
| 0 or7..F | RET2F3A |
| 1 | 2F3B transition, unless record+08 bit0004 is set |
| 2 | If record+27 differs from FF, NEG that byte; RET2FAB |
| 3 | If record+27 differs from01, NEG that byte; RET2FB5 |
| 4 | 2FB6 object-record path |
| 5 | 2FF8 transition, unless record+08 bit1000 is set |
| 6 | 304F transition, unless record+08 bit4000 is set |

The transition blocks set record+08 to2000/1000/4000 respectively and fill
different layout/animation fields. Their live callback-slot loads are0032 at
2F6D,002E at302D and003E at3084. They copy the selected word into record+14,
write +2A as FF/00/FF, and AND byte+24 with01. Preserve their store order,
sound-gate rereads and separate return tails, rather than sharing an invented
initialization structure. Field meanings beyond observed use remain open.

The object path forms DI=17CB+(popped high nibble)*001C using wrapped MUL/ADD.
It tests and sets word[DI] bit0002, sets entity byte+26=FF, and later reads
the live object byte[DI+1B] for sound AL. The nibble bounds this local selector
to0..15; it does not prove broader object-array/stack/record non-overlap.

The exact service sites are INT60 AX0302 at2F8C; INT61 AX0410 at2F9F;
INT61 AH04 with AL from[DI+1B] at2FF5; INT61 AX0411 at304C; and INT61 AX040D
at30A3. The existing native INT61 connector can compose the four latter
paths, retaining unbound vectors and changed IRET targets. The PC-speaker
INT60 dispatcher at loaded0842:0182 now has scoped C, composing the exact
LoadEffect/Stop targets through live table, temporary DS, near-return and IRET
words. The declared INT60 frame/vector connector now carries all changed
registers and actual CS:IP into this parent. Tick and other targets remain explicit
bus-domain seams. See pcspeaker.md and interrupts.md. Loaded overlays and initial
main zero storage remain separate.

## Native acceptance

The logical core takes count, auxiliary value, record/object cursors, DS/CS/SS,
stack offset and flags; it returns named results and an actual continuation.
AX/BX are overwritten at entry, while BP/ES are preserved by this body and every
composed pinned sound prefix. They are therefore absent from the logical call.
The oracle adapter retains BP/ES and consumes the actual outer RET only on a
ready result. Register packets at the INT60 boundary are transient CPU-boundary
values, not a permanent interface between normal game functions or shadow state.

`tests/entity_interactions.py` passes311 fixtures at both boundaries: all256
map bytes plus signed Y and logical-shift/wrap cases, both direction guards,
all transition masks and sound gates, live callback/object/record/frame aliases,
VGA map reads and seeded poison. It covers every one of the162 main sites and
all61 decoded conditional/unconditional branch outcomes. All five original INT
sites execute, integrating37 PC-speaker sites and28 AdLib/Tandy sites;17,648
ordered bus events compare byte values and instruction-phase defined flags.
Six direct-memory repetitions separately exercise the optional NULL-bus path.
Eight separately compiled mutants must complete with a mismatch. Deadline,
process/tree commit and hard callback limits fail verification rather than
counting as mutant evidence; owned temporary DLL directories are removed.

A strong stack/record fixture uses DS=SS=5000, SP=D000, SI=CFD3. The second
sample's store at record+2B overwrites saved AX's low byte at CFFE. First cell04
and second cell05 therefore select transition5 from popped AL; caching04 would
select the object path. An object fixture aliases record+26 with object+1B, so
the entity store changes the later sound byte toFF. A PC-speaker saved-DS change
selects a different live second gate and then calls INT61 through that returned
DS, while saved SI/CX changes survive the parent. Unbound vectors, a command-table
pointer into LoadEffect at01B3, changed child RET and changed IRET targets stop
with their actual state rather than resuming a guessed continuation.

Entry FLAGS are admissible CPU values, `(raw & 7FD5h) | 2` with TF clear. Saved
frame words remain unrestricted; full RAM and event byte values are compared.
The reserved-bit injection artifact and independent original-IRET diagnostic are
recorded in pcspeaker.md. No memory mask hides a difference. Writes changing
forthcoming code, asynchronous debug/IRQ handlers, device timing and unknown
service execution remain outside the current bodies. The311-case proof does not
close the broader1F19 state machine or full game. Child bytes overlap existing
translations and are not added to the486 main bytes.
