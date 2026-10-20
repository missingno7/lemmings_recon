# Connected main menu controller

c/main_menu.c implements the326 known instruction bytes in4401..454B. Its
four entries are MenuRefresh4401, MainMenuReleaseWait4453, RunMainMenuFrame445B
and ReadMainMenuKeyboard4478. Two intervening NOP bytes at44A3/44AA and the
three-byte44E9 table retain their UNKNOWN classification. Naming and consuming
the table does not classify every interpretation of those bytes.
The main-image translated-code ledger union is now28,855 bytes.

## State and exact actions

Refresh writes drawing/alternate origins0/6D60 and page offset0, then programs
the alternate display start. It sets both graphics cachesFF and sound toggle0.
It does not reset MenuSoundOptionIndex1F71 or SoundOptionBits25A7. Its actual
child order is palette1,clear,background,scroll initialization,animation
initialization,backdrop,decorations,text,group,sound,page copy,display wait,
alternate display start and palette2. MainMenuText is live DS4AD9. Child
DS/ES/SS,flags,return words and alias effects feed the next operation.

Release repeatedly reads the full InputButtonsWord and tests only low bits0..2.
The frame loop then waits for display status,advances scrolling and animation,
refreshes group and sound graphics,and swaps drawing origins/display. Only
after all six children does it reread buttons. A low button bit starts the
level transition without a keyboard read. Other bits do not trigger it.

Keyboard AL80 selects454C,81 selects4967,83 selects4A01 and1B selects04D0.
Other recognized bytes are82(sound),8A/60(group increase),8B/2D(group decrease).
Unrecognized bytes resume the frame loop. Every comparison has its original
byte width and order; every exit is a JMP continuation,not a synthetic RET.

Sound cycling is blocked only by cache byte1F72 equal2. Otherwise it XORs the
complete toggle byte1F70 withFF,reads index1F71 and increments only AL. The
limit is3 only when ExternalSoundDriverEnabled2010 equalsFF; otherwise2.
It resets AL only on exact equality with that limit. Indices above the limit
are not clamped and retain unchecked liveCS:44E9+zero_extended_AL reads. The
three observed values00/01/03 are normal-domain values,not a replacement host
array for all possible reads. The selected byte is written to25A7.

The XOR memory instruction exposes incoming flags during its read/write bus
accesses,then publishes its result flags. C preserves that ordering explicitly.
INC preserves CF and the later XOR BH,BH clears only the high index byte.

Group changes are blocked only by cache1F6F equal4. Increase rejects exactly
current3; decrease rejects exactly0. Unexpected values therefore retain byte
wrap. The literal SHL/ADD sequence computes30*group modulo256 in AH and stores
that byte to LevelResourceSelectionByte1F6B. It leaves the original AX and
arithmetic flags,which a replacement host multiplication would not describe.
These are bounds within the normal0..3 domain,not a clamp for arbitrary bytes.

## C composition and return contracts

Every direct child CALL pushes its actual resume word into canonical SS:SP.
C calls the existing typed core and applies all returned fields. Only READY
consumes the actual child near RET word. Child stops retain their own status,
continuation and pending frames; changed parent-call returns have a separate
menu status. Far/inner near returns inside scroll,animation,renderer,text,
palette and display children retain those children's established contracts.
No persistent menu records,buffers or selector copies are introduced.

Normal output is the actual code segment/IP at04D0,4967,4A01 or454C. This is
the native handoff to the destination domain. Entry43F2's earlier display,
timer,palette and resource-retry setup remains outside this scoped domain;
the remainder of43F2's level/game loop is not declared translated by this work.

## Verification scope

tests/main_menu.py uses tests/verification.py for original CPU execution,
canonical bus access,guarded native callbacks and complete state comparison.
Its call-frame descriptors are boundary policy for identified instructions,
not another instruction engine. Independent expectations cover literal child
order,normal exits,full-byte toggles,exact sound-index wrap,live CS values,
group guards/wrap and group-to-resource selection. Finite providers inject
keyboard/button schedules and specific data/table/frame changes.

The campaign includes refresh at three loads,pinned decoded UI banks and text,
multi-iteration group/sound/input sequences,release waits,DF,stack/word wrap,
missing status input and changed wait/keyboard/scroll/display continuations.
The menu-to-input handoff consumes the actual4A01 result using the existing
native input-selection screen. Its returned4401 state then enters native menu
refresh and reaches454C with the selected mode intact. Neither JMP creates a
caller frame or resets game/device state. Every stage is fully compared before
its observation history is consumed; RAM,latches,registers,planes and counters
remain live. The existing input-screen fixture supplies that stage's finite
provider,so no duplicate keyboard or screen verifier is introduced.

The worker has480 seconds and384MiB process-tree commit inside a540-second
outer envelope,with4,000,000 original instructions/2,000,000 ordered events per
main-menu invocation. Guarded native callbacks fail-stop on exhaustion. Owned
DLL directories remain under build and are reaped by the parent. Timeout,
memory/access failure or an incomplete native call earns no mutation credit.

The accepted local campaign passes48 fixtures/50 comparisons,all118 own
instruction sites/51 direct outcomes and nine completed mutation witnesses.
Its declared controller/child instruction domain contains6,830 known bytes;
the input-screen handoff also executes43 sites outside that domain using its
existing shared-verifier fixture. The complete executed union is2,000 sites/
319 outcomes,with11,720,329 original instructions,7,902,090 ordered events and
2,196 separately counted far-return observations. Refresh and repeated input
sequences run at three loads. The complete campaign finishes in217.17 seconds.

Mutations distinguish ignored cache guards,nonzero versusFF driver tests,
clamping instead of exact sound-index wrap,wrong source segment,clamping
unexpected group bytes,AL instead ofAH resource selection,wrong JMP destination,
ignored changed child return and wrong XOR memory-write flags. Every witness
completes its native call before mismatch detection. Only the326 new code
bytes enter the ledger; previously translated children and input-screen bytes
are not counted again. Scoped normal/child stops do not complete43F2 or its
remaining destination bodies.

The43F2 startup prefix and4967 code-entry/454C level bodies remain separate
frontiers. Native scheduling and opaque platform bodies are not supplied by
these constructed-state comparisons. Inherited RETF selector-EA wrap at
SPFFFE/FFFF and artificial VGA-stack masked-loop exhaustion remain unverified.
Full original contracts and aggregate/native-host acceptance remain separate
from this connected local milestone.

The subsequent startup checkpoint connects43F2's prefix,palette publication
and4AC5's media-gated resource check to this controller. Its146 additional bytes
and expanded campaign are recorded in menu-startup.md. The earlier scoped
controller results above remain historical for their recorded inputs.
