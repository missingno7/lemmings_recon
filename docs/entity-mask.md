# Clipped generated entity mask

`DrawClippedEntityMask` at 5DF8..5EB9 is a closed 194-byte/91-site leaf called
at 23B9 in the 1F19 simulation body. It draws from the 22-row generated bank
described in generated-graphics.md. This name identifies the drawing operation;
it does not assign a complete simulation-state meaning to the caller.

The routine first writes GC0=0, GC1=0Fh and GC3=0 through the actual SS mirrors
at 000Ah/000Ch/0002h and port 03CEh. Each mirror store precedes its OUT.
ES becomes A000h. Incoming Sequencer map mask, GC read/write modes, read map,
compare/care and aperture state remain live. There is no implicit readback
setup or register normalization in the C routine.

It reads Y at live DS:SI+2 and subtracts 30 decimal (1Eh) with 16-bit wrap.
The sign of that result controls top clipping. A negative result is added to
the initial CX=22; DI is negated and compared unsigned with 21. A larger
value returns immediately, after the setup outputs but before any drawing
save, CLI or STI. Thus the early path preserves entry IF. The boundary at
Y=9 keeps one row, Y=8 returns early, and wrapped large inputs follow the
arithmetic and flags rather than a corrected signed-Y range check.

The drawing path pushes the row count and skipped-row value, then pushes DX
around MUL(D0h,DI). DX is popped from actual SS memory. Its value supplies
all later OUT ports; it is not silently replaced by 03CEh. The first live
record X read, minus eight and shifted right logically three times, is added
to the low product and 4A40h for the destination offset. The skipped-row save
is popped into AX and multiplied by three through two additions. CX is then
popped from its live save. Aliases may change either value. A zero restored
CX still enters the row body and LOOP wraps through 65535; C adds no cap.

PUSH SI precedes a second record X read. The two reads can therefore observe
different values. The source cursor is formed as
`0C60h + 66*((second_X-8)&7) + 3*restored_skipped_rows`, with wrapping at
each original operation. PUSH DS precedes the live DS:1FE8 segment-selector
read. DS then selects the generated buffer and CLI clears IF. The intended
positive-count, DF-clear source lies in the producer's 0C60..0E70 group;
unchecked selectors, aliases and other inputs do not inherit that bound.

Each row loads two source bytes with LODSW into BX. It reads ES:DI to load
VGA latches, replaces AH with BL, writes SS:000E and outputs GC8, then writes
BL with STOSB. The second byte repeats that sequence with BH. Only after
those accesses does LODSB fetch the third source byte, followed by its own
latch read, mirror store, OUT and STOSB. The apparent discarded VGA reads
are observable and remain in C. Source and destination overlap may change
later masks; there is no row prefetch or shadow mask buffer.

LODSW/LODSB and STOSB follow incoming DF. After three destination bytes, ADD
DI,CDh always adds forward: the normal row stride is D0h with DF clear and
CAh with DF set. LOOP decrements the live register CX without changing flags.
After completion, STI sets IF unconditionally, then POP DS and POP SI consume
the actual save words. AX retains the final third mask in both bytes, BX the
last loaded source word, DX its popped value, and ES=A000h. Final arithmetic
flags come from the last ADD DI,CDh; the early path instead retains the clip
comparison flags. BP and SS remain unchanged throughout.

The logical core in c/entity_mask.c stops before the common RET at 5EB9.
Its register adapter reads the actual outer return word after all accesses.
All record, selector, source, stack, mirror and VGA accesses share the same
optional raster bus. Word accesses read or write low byte then physical+1,
with 20-bit physical and 16-bit cursor/SP wrap. Missing memory callbacks
select ordinary RAM, and a missing port callback supplies only a constructed
no-op-port domain. The native game must supply the device backend.

The contract requires intact executing code, TF clear and quiescent IRQs.
It does not establish allocation bounds, initialized device state, interrupt
scheduling, complete simulation readiness or aggregate game acceptance.

`tools/difftest.py entity_mask` passes 43 fixtures at both pre-RET core and
actual-RET adapter boundaries, all 194 bytes/91 sites and seven branch edges,
with 31,608 ordered bus events and six completed mutants. Seventeen independent
plane checks derive the shifted source bank and honor incoming map mask and
write modes 0/1. One fixture runs the native bank producer on constructed raw
source, independently checks its complete 528-byte 0C60..0E70 group, then gives
that same RAM to the original/native consumer. The producer's bytes overlap
its existing translation; this leaf adds only 194 C bytes.

Fixtures cover the clip boundaries and wrapped sign cases, all eight shifts,
incoming DF/IF, both VGA read modes, saved-count and buffer-selector providers,
post-PUSH record/selector aliases, actual saved DX with a constructed no-op port,
DS/SS backed by VGA, record/stack wrapping and a source word straddling physical
FFFFFh/00000h. Mutants complete before detection: changed clip threshold, cached
row count, ignored DF, omitted latch reads, prefetched RET and preserving entry
IF on the drawing path. Timeout, memory exhaustion, callback errors and access
exhaustion fail the campaign and never count as detected mutants.

Workers run with a 180-second deadline and 384 MiB process/640 MiB tree commit
limits. Each original consumer call has a 1,400-instruction cap (the fixtures
reach at most 630), and native callback/device traces have hard 2,048-event
caps. Exhaustion exits 86 and callback errors exit 87. The separate producer
setup uses disjoint RAM, DF clear and intact fixed-count frames in the bounded
worker. Temporary DLL directories are removed after worker exit. The scoped
report build/entity-mask-differential.json records current input hashes;
complete original/native campaigns remain necessary for aggregate acceptance.

## Static sibling contracts

`DrawTenRowEntityMask` at 5FAC..606A (191 bytes/88 sites) and
`DrawThirteenRowEntityMask` at 606B..6140 (214 bytes/99 sites) remain
untranslated. Both inline the same source-word/two masks/source-byte/third-mask
sequence, DF behavior and fixed forward CDh row adjustment. Both select DS
after PUSH DS, retain live SS base/DX/DS/SI/RET words, preserve incoming VGA
state except GC0/1/3/8, and end with unconditional STI. Neither clips.

The ten-row entry computes wrapped `240*incoming_AX` before setup and pushes
that base. It later pops BX from the actual save, adds 03C0h iff record byte
+27h is FFh, and selects `base + 30*((second_X+second_record_4)&7)`.
Its destination is `low16(D0h*(Y+record_6-10h)) +
((first_X+first_record_4)>>3) + 4A40h`, with each original operation wrapping.
The base is saved before mirror outputs; PUSH SI precedes the second X/+4
reads, so the two coordinate pairs need not agree. CX is set to ten immediately
before CLI. BP is unchanged. The caller at 28A1 masks AL to its low nibble,
retains 2..5, subtracts two and uses CBW: that local path supplies AX=0..3.
The callee itself does not enforce a selector range.

The thirteen-row entry pushes wrapped `312*incoming_AX + 0780h`. After a live
POP BX, it adds 0270h iff record byte +27h is FFh. It reads X into CX and Y
into DI. When byte +28h equals two, it increments local DI and adds the sign
extension of byte +27h to CX. Then DI adds record word +6 and subtracts 10h;
the low D0h product and `(CX+record_4)>>3` plus 4A40h select the destination.
BP receives that wrapped sum before the logical shifts, and later becomes
`sum&7`; it is clobbered and not restored. The mask cursor is
`live_base + 39*(sum&7)`. CX is set to thirteen immediately before CLI.

The normal layout matches AX=0..1 for this entry, but the caller at 2B60 does
not prove that invariant for arbitrary record contents. It increments the byte
at +28h, resets only the exact value 18h, and eventually uses signed JL at 2B58.
New AL values 80h..FFh also take that branch. DEC AL/CBW then produces 007Fh
or FF80h..FFFEh, in addition to 0000h/0001h for new AL=1/2. A bounded record
state would require separate initialization/state-transition proof. These
unchecked values must not be rejected, clamped or masked in the later C port.
The broader meanings of record bytes +27h/+28h remain unproven by these leaves.
