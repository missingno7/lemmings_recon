# VGA mirror restoration frontier

This is a static contract for `sub_587F` at `587F..58D1`: 83 bytes, 38
instruction sites, no child calls or branches. It is not yet a C domain.
The direct callers are MouseIrqBridge at 0F99 (return 0F9C) and the timer
tail at 187E (return 1881). Keep this leaf's fixed relocated mirror segment
separate from the supplied live SS used by the drawing cores and stack.

## Segment, port and stack order

The entry sequence is `CLI; PUSH CX; MOV CX,ES; MOV AX,143Eh; MOV ES,AX`.
The MOV opcode is at 5883 and its word operand at 5884..5885 (`3E 14` in the
static image) is an original relocation. At load 1010 the operand is 244E;
loads 1213/2345 produce 2651/3783, with word wrapping. A C translation must
read the current code operand at its actual MOV phase, after PUSH CX. It
must not replace it with live SS or a cached load-segment calculation.

The routine reads these words in order. Each read is followed by replacing
AL with the indicated index, then emitting the complete word to the port.
AH is therefore the live mirror's high byte; the stored low byte is ignored.

| Offset in relocated mirror frame | Existing ledger name | Port / index |
|---|---|---|
| 0008 | VgaMapMaskMirror | 3C4 / 02 |
| 0000 | VgaGraphicsModeMirror | 3CE / 05 |
| 0002 | VgaDataRotateMirror | 3CE / 03 |
| 0004 | VgaColorCompareMirror | 3CE / 02 |
| 0006 | VgaColorCareMirror | 3CE / 07 |
| 000A | VgaSetResetMirror | 3CE / 00 |
| 000C | VgaEnableSetResetMirror | 3CE / 01 |
| 000E | VgaBitMaskMirror | 3CE / 08 |
| 0010 | VgaReadMapMirror | 3CE / 04 |

`XOR AL,AL` at 58B5 supplies index zero; it is the only arithmetic instruction.
It defines CF=0, PF=1, ZF=1, SF=0 and OF=0, with AF undefined. Other index
changes use MOV and preserve FLAGS. All mirror accesses and OUTs run with IF
clear; DF/TF remain unchanged. The leaf does not write back mirror words.

Finally `MOV ES,CX @58CD` restores entry ES, `POP CX @58CF` rereads the live
saved word, and `STI @58D0` forces IF on before the actual near RET at 58D1.
DS, SS, CS, BX, BP, SI and DI remain unchanged. DX ends at 3CE; AX is the
last mirror word with AL replaced by 04. A PUSH alias can alter a mirror
before it is read: with SS equal to the fixed frame and entry SP=000A,
the initial save overwrites offset 0008. A provider can alter saved CX and
the outer RET independently. Segmented words retain physical high-byte +1.

## Mirror initialization and original quirks

RuntimeStackFrame is at image-relative 143E0, six bytes beyond the static
image's exclusive end 143DA. Initial mirror contents are unspecified until
written. Startup calls `sub_04F9` at 0037; that helper writes live SS words:

| Store site | SS offset | Word value |
|---|---|---|
| 0511 | 0008 | 0002 |
| 0518 | 000A | 0000 |
| 051F | 000C | 0001 |
| 0526 | 0004 | 0002 |
| 052D | 0002 | 0003 |
| 0534 | 0010 | 0004 |
| 053B | 0000 | 0005 |
| 0542 | 0006 | 0F07 |
| 0549 | 0010 | FF08 |

The last store overwrites offset 0010 again. It does **not** initialize 000E.
Consequently the initial read-map high byte is FF, while the bit-mask word
remains unspecified until another writer. These are literal original stores;
do not redirect the last one to 000E or synthesize a corrected mirror image.
Normal footer/startup SS equals relocated 143E, but arbitrary live SS need
not match the fixed segment loaded by 587F.

Later drawing helpers write the named mirrors through live SS. Producers span
the planar, entity, minimap, status and special-graphics modules. Some hardware
changes, including the fixed-pattern leaves, do not update every mirror. The
restorer therefore consumes live, possibly stale mirror values; they are not
a validated copy of the current device state.

## Caller boundaries and next verification

MouseIrqBridge saves DS/AX, invokes INT62, then uses the returned DS for its
gates and calls 587F after saving DX. It does not save ES around INT62; the
restorer must preserve whichever ES the external provider returned. The
bridge's IRET restores FLAGS/CS/IP, not ES.

GameTimerIrqHandler saves the interrupted registers including ES. Its optional
fixed-pattern CALL at 183B falls into the common 183E tail, which calls 418C
and 3E6F before conditionally calling 587F at 187E. The next instruction at
1881 is CLI. The interrupt tail later restores saved ES and other registers,
then IRETs or chains to the saved INT08 handler. Preserve the STI/RET window;
this static contract does not close asynchronous IRQ or INT62 behavior.

Next translate 587F as a bounded leaf with current CS-operand binding, nine
ordered mirror reads/OUTs, actual SS save/pop/RET, IF/DF/defined flags, aliases,
relocation and the startup overwrite/missing-initialization witnesses. Only
then connect its interrupt callers at their explicit platform/frame seams.
