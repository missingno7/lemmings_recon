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
provider composition. Prefix dependencies 5473/553D, finite status-port input
and full-handler composition using the tested 5827 child remain. The unresolved
indirect/far frontier at 42A5 stays explicit. Existing timer_chain.py cases
cover the external return seam, not the full handler or asynchronous IRQs.
The narrower INT61 result and timer_restore cleanup helper do not supply
this handler's full returned segment/frame contract.

## Connected tail acceptance

GameTimerTail183E is implemented in c/timer_tail.c. The physical module
src/game_timer.asm preserves the untranslated prefix and the tail in order;
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

Only116 new bytes join the C ledger, now26,660 main-image bytes; previously
translated children are unioned once. The full handler's119-byte prefix remains
untranslated, along with opaque external ISR bodies and asynchronous delivery.
Next close5473/553D and finite status-port input, then connect17C7 to this tail.
