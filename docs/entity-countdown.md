# Countdown transition at 2E04

The 188-byte/52-site routine at 2E04..2EBF now has a logical C core and near-return
adapter in c/entity_countdown.[ch]. The normal caller is 1F19's 2Dh-record loop: SI starts
at 0088, and 1F45 checks live record+20 before CALL1F4C. A nonzero returned AL
continues record dispatch at1F54; zero skips to1FEB, which restores ES and
advances SI. The CALL save is between the caller's precheck and child DEC,
so a stack alias can change the countdown before it is consumed.

The child sets AL=1 and decrements byte DS:[SI+20] modulo256. Nonzero reaches
the shared AND AL,AL/RET at2E60/2E62: AL=1/ZF=0, with incoming AH retained.
A direct call with initial countdown zero therefore wraps to FF. DEC's memory
read/write phase observes entry flags; the following branch uses its new ZF.

On expiry, the test at2E0B selects one of two transitions from live +8 &5404.
The stores are ordered, and every field address uses live DS:SI with16-bit
offset and20-bit physical wrapping. Do not turn them into a copied C record.

| Record field | Mask clear (2E12) | Mask set (2E63) |
|---|---|---|
| +08 word | OR8000 | OR0002 |
| +0A word | 0008 | 0008 |
| +0C word | 153B | 180B |
| +10/+12 words | 005A/003C | 0280/01E0 |
| +28 byte | 00 | 00 |
| +04/+06 words | FFF8/FFF6 | FFF0/FFE7; +06 stored first |
| +29 byte | 00 | 00 |
| +14 word | live DS:002E | live DS:003C |
| +2A byte | 00 | 00 |
| +22 byte | unchanged | 0F, then conditionally zero |
| +24 byte | AND01 | AND01 |

The two callback loads use DrawingCallbackSlots indexes0 and7. Initialization
0FC1/0FEB writes 6170/6BDB there. Other slot writers and alias closure are not
fully established; these remain live words, including when earlier record
stores overlap them. The slot range and pointer stores are documented in
indirect-callbacks.md. For example SI=002A makes the first branch's +04 store
overlap slot002E before its load; a translator must not substitute 6170.

Both sound gates compare DS:2010 to FF and test DS:25A7 &03. Both bytes are
reread after the record writes. The mask-clear branch requests AX0405 at2E5C;
the mask-set branch requests AX040C at2EB0. The installed AdLib/Tandy driver
prefixes and command4 setters now have scoped native verification; see
sound-latches.md. c/sound_interrupt.[ch] composes those cores through the live
INT61 vector and frame. The host supplies a binding for the actual loaded driver
segment and kind; it does not substitute the vector from that binding. An
unbound segment/nonzero offset/missing binding stops after the frame stores,
at the actual vector target. Untranslated driver services retain the frame;
changed IRET CS:IP stops before any caller continuation. Only an exact return
to the calling main CS and2E5E/2EB2 resumes the countdown. The outer adapter
performs RET only when the core reports ready, using the actual live SS word.

After the second branch's interrupt, 2EB2 rereads DS:[SI+08] &0004; a nonzero
result clears byte +22. This read and the later RET use actual live memory.
An SS/latch alias can change restored DS or interrupt IP/CS/FLAGS even though
the ordinary driver path preserves DS. Both expiry paths finally set AL=0,
ZF=1. AX is not generally zero: without sound AH retains the loaded callback's
high byte; an ordinary command4 driver path leaves AH=0. The first expiry path
shares the 2E60 AND/RET tail with non-expiry; the second uses2EBD XOR/2EBF RET.

The explicit +20 producers are the record clear at30F3..30F8, the arm at2033,
the inventory/input arm at31E1, and the clear at2277. Both arms write4F.
The2033 arm requires +20=0, +26!=FF and +08 &0003=0; the31E1 arm additionally
consumes DS:70 and requires +08 &C003=0. Indexed writes, cloned records and
UNKNOWN paths prevent a claim that this list closes every possible writer.

## Verification boundary

`tools/difftest.py entity_countdown` compares 430 fixtures at core/adapter
boundaries and20 auxiliary interrupt calls. It covers all256 countdown bytes,
each of the16 record-flag bits, all14 branch edges and52 parent instruction
sites. The native driver cores execute directly; their already translated
106 bytes are not added again. Twenty auxiliary calls check untranslated
services, other AH commands and TF clearing. Eight countdown and six interrupt
mutants must complete before a mismatch receives credit. All tests have a
180-second/384 MiB process/640 MiB tree bound,180 original instructions per
call and a hard256 callback budget. Temporary DLL directories are reaped.

The campaign compares full canonical RAM, registers, phase-defined flags,
ordered byte accesses and VGA state. It also checks independent ordinary
record/frame layouts and countdown arithmetic. Cases include slot/write and
gate aliases, data/stack offset and20-bit physical wrap, VGA record/stack
accesses, map-mask-zero stack reads, saved DS changes, FLAGS and near/interrupt
return aliases, live post-sound record reads, IF/DF combinations and null-bus
repeats. The saved FLAGS word is data: IRET fixes bit1 and clears reserved
bits3/5/15 in the represented real-mode CPU contract, including AL05 overwrites.

Unicorn exposes software INT through a hook. Its frame/vector transport is
therefore a declared platform boundary, while main and driver instructions,
including driver IRET, execute independently. The model follows the real-address
INT operation in [Intel's SDM, Volume2A, instruction INT](https://cdrdv2-public.intel.com/868140/253666-089-sdm-vol-2a.pdf#page=581):
save FLAGS; clear IF/TF; push CS and return IP; then fetch the IVT target.
The CS-word-then-IP-word read order follows that pseudocode. It is not a claim
about hardware bus timing, interrupt delivery or 8086/286-specific fault behavior.
The original-only interrupt harness does not import the C transport algorithm.

Bindings require the pinned, unmodified driver instruction domain. Code/stack
aliases that alter forthcoming instructions remain outside these C bodies.
For example SS6000:SP0001 makes the high byte of a wrapped FLAGS save reach
physical70000, the constructed fixture's driver entry. That case is a code
mutation, not an ordinary data-stack wrap; bounded tests use disjoint code
backing for their wrap cases. No native instruction interpreter or repaired
instruction bytes are introduced. General vector installation/aliases, mutable
code, asynchronous IRQ delivery, playback and the broader untranslated1F19 simulation
remain open. The report's input hashes must match before retaining acceptance.
