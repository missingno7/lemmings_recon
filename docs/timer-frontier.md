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

After the mouse bridge, the dependency order is: 18B2; understood children
of 3E6F and 418C; the 183E shared tail with explicit INT60/61, mirror-restorer
and saved-INT08 provider seams; prefix dependencies 5473/553D; the prefix
using the tested 5827 child; then full-handler composition. The unresolved
indirect/far frontier at 42A5 stays explicit. Existing timer_chain.py cases
cover the external return seam, not the full handler or asynchronous IRQs.
The narrower INT61 result and timer_restore cleanup helper do not supply
this handler's full returned segment/frame contract.
