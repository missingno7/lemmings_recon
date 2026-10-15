# Retry input wait and its producers

The original retry UI at4B1C reaches a five-byte scan-code reset at4B3B,
then the16-byte/six-instruction wait at4B40..4B4F. Both exits stop before the
CALL at4B50. These are fallthrough/branch boundaries, not original near-call
functions; neither core nor adapter creates or consumes a target stack frame.

Each iteration reads the whole live `InputButtonsWord` at DS:0014 into AX and
tests AX with7. A nonzero result exits immediately without reading the scan
byte. Otherwise MOV AH reads `KeyboardScanCodeByte` at DS:1FD0, retaining AL
from the earlier word, and AND AH,AH decides whether to repeat. Upper word
bits are retained in AX on a button exit; the input word is never normalized.
TEST defines word SZP and clears CF/OF; AND defines byte SZP and clears CF/OF.
AF is undefined after either instruction. Incoming AX is overwritten by the
first word read, so it is not an input parameter to the logical C core. DF/IF and other unaffected state
remain live, including the flags observed by every byte-provider event.

The reset writes zero through the same optional RAM/VGA bus. Word reads visit
low then high physical bytes with20-bit wrap. There is no stack access,
polling service call or internal timeout. A snapshot with no future input can
wait forever, exactly as the original does. C providers may change canonical
memory between accesses; they do not return replacement CPU registers.

Recovered fixed-displacement producers establish the field interpretations:

| Field | Original producers |
|---|---|
| DS:0014 word | INT09 OR at171E/172F, AND at1749/1755; full input-poll stores424D/4269/4355/4382 |
| DS:1FD0 byte | INT09 make store1707, break clear1736, special clears1717/1728 and mapped-release clear177A; explicit clears0194/3FF6/4AE8/4B3B |

INT09 is installed by157C at CS:16D4 and loads relocated game DS. It stores
the make scan code masked with7F, clears the latch on breaks, and under the
DS:200B==FF gate maps7D/7E makes/releases into button-word bits1/0. These are
word read/modify/writes preserving other bits. The latch is neither a queue
nor an event boolean; a later release can clear it before the wait observes it.

Game/menu timer handlers call418C at1840/4C72, with DL=0/FF respectively.
Its live DS:25A6 choice selects mouse polling, the unchecked DS:25A0 callback,
or another input path. Mouse4252 calls INT33 AX=3 and stores the full returned
BX word at4269 unless DS:200B==FF. Callbacks4334/4359 sample port201 and store
full words at4355/4382. The wait itself does not invoke these producers.
See interrupts.md for installed-vector and external-chain contracts. In
particular, the menu timer does not save ES, and external returned DS remains
observable. This leaf does not implement an interrupt scheduler.

Startup00027..00031 selects ES from DS and executes REP STOSB with DI=0,
CX=2012 and AL=0. It initializes both fields in the forward span only when
DF is clear; the visible entry does not establish a universal DF-clear rule.
Fixed-displacement cross references are not a complete writer inventory:
indexed/physical aliases, UNKNOWN code and broader input ownership remain open.

The native core and original contract use intact decoded instructions, the
same CS, TF clear and quiescent IRQ scheduling, with finite constructed memory
updates. A scalar model checks access order, flags, AX and the full RAM/VGA
footprint independently of the native target. No original game is booted.
Verification limits belong to disposable workers and never alter the C wait.
Budget/timeout/provider failure is a failed verification, not mutant credit.
Parent-owned temporary DLL directories are removed after workers terminate.

The separate gate in tests/retry_input.py checks all65,536 button-word values
against a scalar formula and the original read-only loop. Its791 fixtures
compare native core and adapter boundaries, whole RAM/registers/defined
flags, ordered byte events and VGA planes/latches. All256 button low bytes,
all255 nonzero scan bytes and all256 reset input bytes are included.767
ordinary-RAM fixtures repeat with NULL, empty, read-only and write-only buses;
the VGA mode0/1 fixtures use the full bus. Provider changes can alter the high
word byte after the low read or change a byte after its current value is
returned. The original harness injects returned bytes for that instruction
and publishes overlapping canonical changes at the next instruction boundary;
the final full Unicorn RAM mirror must still match canonical RAM.

Seven completed finite mutants cover a missing button bit, testing the whole
word, an extra scan read, cached button state, word instead of byte flags/test,
skipped reset and an invented RET. A1024-access guard must exit86, and a NULL
bus no-event probe must enter native code before its five-second deadline
terminates it. Neither event is credited as a mutant. Workers have120-second
deadlines and Windows384MiB process/640MiB tree commit limits; final reports
are published only after worker success, guard probes and source freshness.

Another512 original-only cases execute16FE..1759 for every raw scan byte and
both DS:200B gates. They check make/break/special button and latch updates,
AX and the bounded write/instruction domains before bitmap lookup175A. They
do not execute IRQ entry/IRET, port services or bitmap lookup, and their
instruction sites remain separate from translated/executed C accounting.
