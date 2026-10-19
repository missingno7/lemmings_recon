# Keyboard producer and controller lifecycle

The cluster adds275 main-code bytes: wait17BE (9 bytes/five sites), command17B4
(10/seven), IRQ16D4 (224/91), installer1562 (32/16). c/port_io.c owns the two
controller leaves; c/keyboard_input.c owns IRQ/installer. Native EOI/input children
bring the known connected domain to856 bytes. Canonical RAM owns every field,
binding, saved word and interrupt frame.

## Controller leaves

17BE XORs CX with itself, reads port64, TESTs AL with2, then LOOPNEs. CX decrements
even on the first clear sample: immediate readiness leavesFFFF. A continuously
busy provider consumes65,536 samples and leavesCX0. Neither timeout nor invented
failure replaces fallthrough. AL retains the last sample; LOOPNE preserves TEST
flags. Core before RET17C6; adapter consumes its actual near-return word.

17B4 pushes AX, clears IF, CALLs17BE through actual17B9, then POPs AX from the
returned stack. OUT64 sends restored AL; STI unconditionally setsIF before RET17BD.
CX/wait flags stay outputs. Missing ports stop at the reached instruction; changed
child RET stops without forcing17B9. Providers may change canonical memory.

## IRQ state and quirks

16D4 saves DS,AX,BX,CX, then fetches the complete relocated immediate16D9 into
AX/DS. Incoming ES,DX,SI,DI,BP and entry flags are not locally saved. Hardware
IP/CS/FLAGS already occupy liveSS:SP. Core before17B3; adapter executes actualIRET.

Any nonzero200A enables commandAD before scan input. A fresh read after EOI decides
commandAE, so providers may change that decision. Port60 supplies the raw scan;
actual PUSHAX/POPAX saves surround port61 input and its bit7-set/clear outputs.
The raw AX is pushed again before lookup. All these saved words can alias fields.

Raw bit7 selects make/break; AH receives low7 bits. Makes storeAH in latch1FD0;
breaks clear it. Only exactFF at200B enables special7D/7E word-button paths:
makes OR bits1/0 into0014, releases AND them out. Each matching path clears AX
before binding lookup. A special release can therefore match scan0 as a make.
No repaired scan copy substitutes for this original behavior.

Sixteen live bindings201F..202E map to masks0001..8000. FF skips equality; other
entries are read again for CMP AH,[BX]. The first match wins. Make ORs CX into
keymask1FC7; break NOTs CX, ANDs1FC7 and clears the latch. Miss increments BX and
shifts CX until carry ends the16-entry scan. Repeated reads remain observable.

The second raw AX pop independently supplies state array0F78. XORAH,AH and
ANDAL,7F precede signed CMP/JNL53. Make writes94, break00, only within83 bytes;
53..7F do not write. EOI, the fresh controller gate and optionalAE precede four
actual pops. No saved-register shadow replaces canonical stack words.

Startup's forward clear covers0F78,1FC7,1FD0,200A/200B when DF is clear;
configuration11E2/133A can set200A=FF. Bindings are outside that clear. Pinned
image0BAAF contains10 1E 18 19 39 01 1C 02 03 04 7C 7B 7A 79 77 4C.
This establishes their live consumer/extent; the existing UNKNOWN storage
classification remains pending broader code/data ownership. It is not a complete
writer inventory or exclusion of physical aliases.

Next consumer4D1A scans83 state bytes, changes held-key repeat values and XLATs
from DS:202E. That table starts at the final binding byte: disjoint copied arrays
would lose the overlap. Callers4478/4A31/4AA2/4CCE remain untranslated.

## Installer

1562 clearsIF and pushes DS then ES before DOS21 AX3509. Shared interrupt transport
constructs actual FLAGS/CS/IP, reads IVT21 after stores and consumes returned IRET.
The bound provider may change all registers, memory and SS:SP. Returned ES is
stored at live DS:1FBC, then BX at1FBA; entryDS is not forced back. Current CS
passes through DX into DS; DX16D4/AX2509 requests installation. ReturnedSS:SP
owns POPES/POPDS/nearRET1581. STI is unconditional. Unbound, provider-stop and
changed-IRET states remain distinct; IVT/stack/saved-vector aliases stay live.

## Focused evidence

tests/keyboard_input.py reuses tests/verification.py original execution, bus,
guarded callbacks and comparator.589 single fixtures include all256 raw scans at
both200B gates, disabled/duplicate/changing/pinned bindings, both full65,536-sample
waits, changed saves/returns, returned DOS state, wrap, VGA stacks and missing ports.

Three nine-stage handoffs reuse each side's same RAM/device at1010/1213/2345:
installation, then four raw10/90/39/B9 IRQs each followed by input418C. The first
produces vertical delta-1; release resets acceleration;39 produces button1 andB9
releases it. All interrupted registers/flags restore. Hardware entry and caller
frames are explicitly constructed, not scheduler/startup execution.

The592 fixtures/1,205 comparisons cover119 own sites/35 outcomes,169 integrated
sites/51 outcomes,957,185 original instructions and342,228 ordered events.
Declared interrupt transport accounts for1,296 events; provider accesses456
across80 calls. Seven completed mutants cover zeroCX extent, unconditionalSTI,
specialAX-zero behavior, bitmap bound, relocatedDS, actual RET and returnedDS stores.

Workers have420-second/384MiB process-tree bounds; comparisons allow500,000
instructions/150,000 events. The input consumer retains100,000/10,000 bounds.
Callback or budget failures never count as mutation detection. Owned DLL directories
are removed after workers exit. This is scoped C evidence: opaque services,
scheduling/reentrancy, repeat/character callers and unresolved code/data remain
open. Aggregate acceptance requires fresh full original/native campaigns.
