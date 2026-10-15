# Countdown transition at 2E04

This is a static contract for the 188-byte/52-site routine at 2E04..2EBF.
It remains untranslated. The normal caller is 1F19's 2Dh-record loop: SI starts
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
sound-latches.md. Actual INT61 vector/frame transport and its return target
still need composition with this routine. A missing or changed vector must
remain visible, rather than become a preserving no-op sound callback.

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

Next translate this routine on canonical memory and compose the verified
driver command4 path through the actual interrupt frame. Test callback-slot,
sound-gate and near/interrupt-return aliases, all countdown bytes, both
transition masks, post-interrupt +08/+22 effects and defined flag phases.
