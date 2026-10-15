# Installed handlers, executable overlay and timer chains

The original byte evidence is pinned in metadata/interrupt-evidence.json and
reproduced by tools/interrupts.py. This is an inventory of identified installations;
generic memory writes and aliases still require review before claiming completeness.
All main addresses and data offsets below are hex.

| Installation | Original producer | Destination or dependency |
|---|---|---|
| INT09 keyboard handler | DOS AH25 at 157C | Main CS:16D4 |
| INT08 game timer | DOS AH25 at 164E | Main CS:17C7 |
| INT08 menu timer | IVT writes at 502E/5034 | Main CS:4C47 |
| INT24 critical error | DOS AH25 at 008D | Main CS:18F8 |
| Selected private IRQ | DOS AH25 at 0F60, AL from DS:1FC6 | Main CS:0F70; startup sets selector 0C |
| Mouse event callback | INT33 AX000C at 0F53 | Main CS:0F6F; one-byte RETF |
| INT60 PC speaker | DOS AH25 at 165D | Relocated frame 0842:0182; loaded MAIN.DAT component |
| INT61 AdLib/Tandy | DOS AH25 at 057B | Allocated driver segment:0000 |
| INT62 forwarding vector | DOS AH25 at 0081 | Original selected private IRQ saved at DS:1FC2 |

Known restoration sites are 158E for INT09, 16BD/16C1 for INT08 and 0FAE for the
selected private IRQ. The protection INT1/INT3 mechanism has its separate state
inventory in protection.md.

## Additional executable dependency: PC-speaker component

The INT60 destination is absent from the stored code image: main 085A2 is initially
zero. LoadMainResourceSections at 58D2 opens the literal filename `main.dat` and
decodes six sections. Its calls are 58E0, 58F9, 590F, 594D, 5960 and 5972. The
recovered graphics-helper call graphs between these decodes contain no file-reader
entries. The sixth decode loads section index 5 at relative segment 0842, offset 0.
Both loader frame word 5968 and install frame word 1653 have original relocations.

The source container has seven sections. Section 5 begins at file 0D17A and ends
at 0D419: 671 packed bytes produce 758 bytes, SHA256
`bdc1da6ea085bd247ab3060dfc78f522f7b447dcffe7235a3e19bf9938731287`.
The component occupies main-relative runtime bytes 08420..08715 and installs its
entry 0182 at flat runtime offset 085A2. The stored main zeros retain their exact
canonical bytes and are classified as overlay storage. src/sound/pcspeaker.asm is
the separate payload reconstruction, not a replacement canonical main image.

The earlier three-image inventory omitted this loaded executable dependency.
There are now four reconstructed component images totaling 127,491 exact ASM bytes.
This total counts both initial main storage and the loaded payload, rather than
unique memory addresses after initialization.

PC-speaker discovery currently has 89 instruction sites occupying 211 bytes and
four entry candidates. Mutable header data occupies 0000..001D, followed by five
visible near-pointer words at 001E..0027. Twenty-three 15-byte effect records occupy
0028..0180; the selector at 01B6 uses signed AL*15 without a bounds check. Byte 0181
and trailing 0255..02F5 remain UNKNOWN. The trailing bytes resemble fragments of
other code but have no established entry or ownership; they are not called dead.

The dispatcher at 0196 admits AH=00..10, including zero pointers for commands
02/04 and indexes beyond the visible table. Known nonzero services are 00 at 01D4,
01 at 024F and 03 at 01B0. Commands 11..1F read data indexes 1..0F; commands 20..FF
write data indexes 00..DF, including the dispatch table. AX is an output, while the
entry saves BX/CX/DX/SI/DI/DS. These unchecked and mutable paths remain explicit
control/producer obligations; no clamp or substitute callback is added.

The three closed helper bodies now have separately verified C11 cores. The IRQ
dispatcher remains untranslated; see pcspeaker.md for exact byte/coverage domains.

tests/sound_unpack.py verifies this payload with original main CS:1BAF at two
loads, writing directly into the corresponding overlay destination. Both cases
match all 758 bytes after the original header and payload reads. No PC-speaker
service or original game startup runs in these extraction checks.

## Saved INT08 chains

DOS get-vector INT08 at 0060 returns ES:BX, stored at DS:1FBE/1FC0. Both 1899 and
4C6C read that live far pointer. Before jumping, each pushes FLAGS, CS and a return
IP (189D or 4C70) so an external IRET continues the original caller. The CFG now
represents each as an external interrupt chain plus a conditional IRET return edge.
An external provider must consume the supplied frame; it must not silently replace
the live pointer with a guessed original code target.

tests/timer_chain.py runs only the identified caller tails using constructed saved
register/interrupt frames and fixture external IRET code. Nineteen cases compare
complete memory, saved registers and final flags at three loads and with stack
wrap. External register/DS/ES clobbers and declared input-poll clobbers are explicit.
The original BIOS ISR, complete timer handler and game body are outside this check.

Two preserved contracts matter for C translation. First, the menu timer wrapper
does not save ES: an external or input-poll ES change survives its final IRET. The
game timer restores its saved ES. Second, the game tail writes DS:1FCF and DS:1FCD
using the DS returned by the external ISR before restoring its original saved DS.
A changed external DS redirects those writes. The menu input poll also receives
the returned DS. Tests expose these effects instead of normalizing registers.

The visible counter branches differ: the game timer chains on phase zero after
incrementing DS:1FE3 modulo four; the menu timer chains on the other three phases.
The complete timing, provider and asynchronous-interrupt domains remain open.

## Newly accounted main handler bodies

MouseEventReturn at 0F6F is a RETF callback with no register changes. MouseIrqBridge
at 0F70 loads the relocated game DS, increments DS:2002/2003, invokes INT62, then
decrements through the DS returned by that service. If CS:83BE and the resulting
DS:2002 are both zero, it calls 587F with DX saved around that callback. Byte
counters wrap normally, and the handler restores saved AX/DS and returns with IRET.

CriticalErrorHandler at 18F8 sets DS:1FDF to FF, then zeroes AL after loading AX with
the game data segment. Its returned AX high byte therefore comes from that relocated
segment, rather than the interrupted AX. DS and the interrupted flags are restored.

tests/interrupts.py covers these three handlers with 19 constructed frames. It
compares all memory, registers and defined flags, including stack residue, byte
wrap, guard alternatives, stack wrap and changed external DS. INT62 frame/IRET
transport and the 587F cursor service are declared boundaries. The tests execute
29 original handler sites and do not establish BIOS, cursor-rendering or C coverage.

The external INT61 entry prefixes and six command latch setters now have
scoped C cores and actual IRET adapters; see sound-latches.md. All256 AH
values are covered for each driver, but AH0/1/2 remain explicit untranslated
service exits. Main2E04 requests command4 and rereads its record afterward;
entity-countdown.md records that caller contract. Installing/selecting the
live INT61 vector and composing its frame with main remain separate work.

Remaining work includes the provider contracts, further vector writes/aliases,
PC-speaker dispatch/producer closure and the component's unexplained trailing bytes.

The retry UI input wait and its shared DS:0014 button word / DS:1FD0 scan-code
latch are documented in retry-input.md. Its512 original-only16FE..1759 prefix
cases check every raw scan byte at both200B gates before bitmap lookup. This
producer evidence does not translate the keyboard handler or close its IRQ,
port, bitmap and scheduling domains.
