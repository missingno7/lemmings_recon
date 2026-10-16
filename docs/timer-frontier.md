# Timer handler convergence frontier

Static regions, with exclusive ends:

| Region | Range | Decoded bytes / sites |
|---|---|---|
| GameTimerIrqHandler | 17C7..18B2 | 235 / 109 |
| Prefix | 17C7..183E | 119 / 60 |
| Shared tail | 183E..18B2 | 116 / 49 |
| Master PIC EOI leaf | 18B2..18B7 | 5 / 3 |

The subentry at 183E falls inside the full handler; union its bytes and sites
once. UNKNOWN18B7..18F7 remains unresolved. Startup's checksum window
CS:188F..1898 starts inside the CALL operand at 188E and includes the short
jump, MOV AX,189D and the synthetic frame's PUSHF/PUSH CS/PUSH AX. The far
jump at 1899 follows the window. Preserve both code and data interpretations.

Startup captures the old INT08 pointer in DS:1FBE/1FC0, and installation at
1644..1650 selects CS:17C7. The handler pushes AX, DS, ES, CX, DX, BX, BP,
SI, DI and FLAGS on live SS before loading DS from the relocated immediate
at 17D2. Its original hardware IP/CS/FLAGS frame remains below these saves.

The configuration byte DS:200E selects whether the prefix runs. The prefix
calls 5473, programs the CRTC from live origins and the display-page offset,
and uses ADD DL,6 before two status-port polling loops. Keep the IN provider
finite and the STI windows explicit. It programs the PIT from DS:1FC9,
calls 553D and the tested fixed-pattern parent at 5827, then falls through.

The shared tail clears DL only, calls 418C, increments DS:001C, conditionally
invokes INT60/61 through live sound gates, and calls 3E6F. If returned
DS:2002 is zero it calls the VGA mirror restorer. It then executes CLI,
advances DS:1FE3 modulo four and either calls the EOI leaf or chains to the
saved timer handler. These fields are shared with foreground code; no
timer-private state copy or scheduling interpretation is established.

The chain path pushes actual FLAGS, CS and IP=189D, then far-jumps through
the live saved pointer. An external IRET consumes that synthetic frame;
the local epilogue later consumes the original hardware frame. Returned DS
controls the stores to 1FCF and 1FCD before saved DS is popped. Returned ES
is later replaced by the live saved ES word. Carry returned SS:SP, memory,
registers and FLAGS through both boundaries, including changed-target stops.

The mouse bridge, 18B2 EOI leaf and 4334/4359/4386 port-201 cluster now have
scoped C acceptance. The 4252 mouse-provider contract and connected 418C input
paths now have focused acceptance through the shared verifier. The 3E6F command
parent now composes the visibility child with proved shared-state ownership;
INT33 and INT60/61 callers reuse interrupt_service.c's full-register transport.
See input-commands.md for the scoped 594-byte domain and remaining sound seams.
The connected tail below supplies the INT60/61, mirror-restorer and saved-INT08
provider composition. Prefix dependencies5473/553D now have scoped native
acceptance below. Finite status-port input and full-handler composition using
the tested5827 child remain. The unresolved
indirect/far frontier at 42A5 stays explicit. Existing timer_chain.py cases
cover the external return seam, not the full handler or asynchronous IRQs.
The narrower INT61 result and timer_restore cleanup helper do not supply
this handler's full returned segment/frame contract.

## Connected tail acceptance

GameTimerTail183E is implemented in c/timer_tail.c. The physical module
src/game_timer.asm preserves the prefix and the tail in order;
entry_services_after_timer.asm owns the following EOI/critical-error suffix.
No checksum bytes or UNKNOWN classifications changed.

| Canonical DS field | Ownership and initialization |
|---|---|
| 001C TimerCadenceCounter001C | Startup clear at0031; INC1843 and a distinct read1847, then bit0 gates INT60. No time unit inferred. |
| 1FE3 TimerChainPhase1FE3 | Startup clear; game read1882/write1889 and menu read4C54/write4C5B. Both increment modulo4, with opposite chain phases. |
| 1FCD TimerForegroundCounter1FCD | Startup clear, foreground reset018F and reads0186/01DC/01DF; increment18A3 through returned DS. Separate from CS:1FCD code. |

The tail entry inherits ten saved words (FLAGS,DI,SI,BP,BX,DX,CX,ES,DS,AX),
followed by the three hardware-return words. The core consumes the ten saved
words and stops before18B1; the adapter executes the actual hardware return.
The chain at1893 adds its own FLAGS/CS/189D words. Its far JMP reads IP then CS
in the bounded original observation; the fixture provider returns before IRET.
Returned SS:SP owns both subsequent frame consumption and the local saved words.
Returned DS owns1FCF/1FCD until the actual POP DS; no entry segment is substituted.
Unknown input callbacks and child/provider failures propagate with separate
parent, child and service status, without executing an unexplained destination.

tests/timer_tail.py passes48 fixtures/96 comparisons, all49 tail sites/15 direct
outcomes, and five completed mutation detections. The connected domain contains
1,374 known bytes; this campaign executes443 integrated sites/101 jump outcomes
and11,712 original instructions, comparing8,634 events. It separates616 declared
interrupt-return/INT transport events and264 provider accesses across50 calls.
Independent checks cover saved register order, outer targets and flags, live
frame extent, modulo phase and returned-DS stores. Constructed cases include
relocation, stack/word wrap, late vector writes, nested unsupported targets,
changed child returns, sound-returned DS, VGA restoration and actual visibility.

Logical AF is architecturally undefined. The pinned Unicorn execution clears it;
the native tail retains that concrete zero when PUSHF stores FLAGS in canonical
RAM. Defined flag comparisons still distinguish undefined AF, and saved memory
is compared without masking. This is an explicit oracle convention, not proof of
the unspecified bit on every historical CPU.

At the tail checkpoint,116 new bytes joined the C ledger at26,660 main-image
bytes; previously translated children were unioned once. Full entry composition
below now closes the119-byte prefix; opaque external ISR bodies and asynchronous
delivery remain open.
The subsequent palette checkpoint added135 bytes, taking the ledger to26,795.
5473/553D now compose the56-byte sequential DAC leaf548C and existing34-byte
attribute leaf5425. tests/palette_timer.py passes132 comparisons, all81 sites/
20 outcomes and five completed mutants. The shared169-byte domain preserves
live source/control reads, DF, unchecked CH/zero CL, unconditional STI and the
actual5555 child return. Source2638/2650 shares a transition-written RGB range;
2668 is another live source. Initialization/allocation remains partly unknown.
See palette-pointer-frontier.md. That checkpoint left the119-byte17C7 prefix;
the full-entry acceptance below now connects it to those children and the tail.

## Full handler acceptance

lmn_game_timer_core/adapter in c/timer_tail.c now execute that prefix and compose
the actual existing tail core. Its235 own bytes/109 sites overlap the116-byte
tail, so only119 new bytes enter the main C ledger, now26,914. The connected
union is2,840 known bytes. tests/game_timer.py passes93 fixtures/186 comparisons,
all109 timer sites/36 direct outcomes,1,223 integrated sites/150 outcomes and
five completed mutants. It executes92,618 original instructions and compares
72,572 ordered events:640 declared interrupt transport accesses and520 provider
accesses across54 calls. These are separate evidence dimensions.

The campaign reuses timer_tail.py's service/frame and native bindings plus the
shared verifier. Independent checks cover actual saved registers and hardware
frame extent/targets/flags, wrapped CRTC packets, PIT byte order and CLI phases.
Fixtures include all tail seams, both palette modes, the generated-bank child,
DF/IF, relocation, actual saved DI changes, late17D2/PIT/source providers,
changed parent/nested returns, missing byte/word providers and physical/offset
stack wrap. The93 includes an alternate entry-DS trap so the relocation mutant
returns through a bounded supported stop; callback failure cannot count as a
mutation detection. Worker limits are420seconds/384MiB,100,000 instructions and
30,000 events per comparison; temporary DLL directories are parent-owned.

The separate timer_tail regression retains48 fixtures/96 comparisons,49 own
sites/15 outcomes and five completed mutants. It remains a useful narrower
boundary. No original game boot, real scheduling, IRQ reentrancy, CRTC/PIT timing,
complete generated-bank initialization or unexplained callback body is claimed.

## Full entry contract

The119-byte prefix saves AX,DS,ES,CX,DX,BX,BP,SI,DI,FLAGS before the relocated
MOV AX immediate at17D2 loads DS. The canonical loaded operand is fetched after
those writes, including a declared provider change; it is an instruction
operand rather than a raster data read. Saved register words stay in canonical
SS:SP. No prebuilt copy substitutes for them. The exactFF gate200E bypasses all
palette, CRTC, polling, PIT and fixed-pattern work; other bytes take that path.

The prefix reads DS:1FDA,1F78,1F7A in order and computes the16-bit sum of the
alternate origin, page offset and2. Word OUTs17F4/17F9 send index0C/high byte,
then index0D/low byte to the same DX. ADD DL,6 wraps the low byte alone and
retains DH. STI17FD exposes the two inline bit3 polls; the first waits for set
and the second for clear, including all six delay JMPs. The status DX is retained
from the earlier CRTC base; unlike1550, neither poll rereads the DS port word.
Finite fixture samples fail on exhaustion. No asynchronous reentrancy is modeled.

CLI1814 precedes the single live DS:1FC9 word read at1815. TimerPitReload1FC9
retains zero and every unchecked word. PIT byte outputs are43=36,40=CL,40=CH,
with their literal delay JMPs and unchanged intervening flags. STI1837 precedes
CALL553D, then CALL5827. Palette returns17E0/183B and pattern return183E consume
actual words. Nested or parent return changes propagate distinct statuses before
any following instruction. Normal5827 restores DS, leaves ES=A000 and sets IF;
the bypass reaches183E with entry IF. The tail restores the live saved ES later.

Startup clears all prefix DS fields. Mirror initialization stores the BIOS
0040:0063 CRTC base at0503; configuration134A/137C can set03D4. Display setup
writes alternate origin6D60/page0; gameplay81D2/81D8 supplies2520/02C0 before
subsequent swaps. Reload1FC9 has configuration writes3468 at11EC/1344, parsed
BX at139A and calibration4000/derived/restored values at15B4/15F4/15FD. These
identified producers do not prove device timing, valid allocation or every
runtime producer. Generated pattern-bank initialization remains a separate scope.
