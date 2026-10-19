# Menu timer and direct vector installation

The menu IRQ at4C47 has54 known bytes/33 sites, split around UNKNOWN4C65.
Its direct IVT08 installer at5028 has19 bytes/nine sites. Both are implemented
in c/timer_tail.c using the existing canonical memory, flags, stack and interrupt
services. UNKNOWN4C65 remains unresolved; skipping it from this entry does not
establish any broader reachability or data ownership.

## Live frames and state

4C47 pushes AX,BX,CX,DX,SI,DI,BP,DS on actual SS:SP before fetching the relocated
IMM16 at4C50 into AX and DS. At canonical load1010, that operand selects19B9;
other loads and declared operand changes remain live. The saved frame is
DS,BP,DI,SI,DX,CX,BX,AX, followed by hardware IP,CS,FLAGS. ES and entry FLAGS
are not saved. Input or the external saved handler can therefore leave ES live;
the outer hardware IRET supplies the final FLAGS. No game-timer save layout is
substituted for this frame.

Shared DS:1FE3 TimerChainPhase1FE3 is read after the pushes, incremented and
masked modulo4, then written before branching. Startup clears this field;
game1882/1889 and menu4C54/4C5B are distinct producers/consumers. Menu phase0
sends the native EOI child through actual return4C63, while other phases chain
to saved INT08. The game handler chains at phase0 instead. No time unit is
inferred. A saved AX/phase alias can change both the phase read and restored AX.

The chain pushes FLAGS,CS,4C70 and far-jumps at4C6C through live DS:1FBE/1FC0.
The original observation reads IP then CS; the external service returns before
IRET, with full returned registers and canonical-memory effects. Its actual
SS:SP owns synthetic-frame consumption, subsequent input frames and the eight
final pops. Returned DS owns the following input accesses until POP DS. There
is no local STI or entry-POPF in this handler.

At4C70, MOV DL,FF preserves DH. The actual CALL418C pushes4C75 and composes the
tested mouse, keyboard and known port201 paths. Unknown42A5 callback targets
remain explicit stops. Child/provider errors and changed RET/IRET targets keep
separate parent, child and service status. The core stops before4C7D; its adapter
executes the actual hardware IRET.

## Installer and handoff

5028 executes CLI and PUSH DS before zeroing AX and DS. It writes IVT08 offset
4C47 at0000:0020, then current CS at0000:0022. Actual POP DS follows both writes;
STI is unconditional before outer RET503A. An IVT/stack alias can change the
saved DS, the outer target or only one byte of a straddling word. Word high bytes
follow physical+1 masked20, while SP wraps16 between stack operations.

The fixture handoffs retain the installer's actual C/original memory and
register results, check the installed CS:IP, then construct a hardware-entry
frame and run the identified menu IRQ on that same memory. This establishes
the installer/handler handoff without claiming interrupt delivery or scheduling.
The separate timer-install.md campaign now composes installer1644, the installed
game IRQ and cleanup using the same RAM; keyboard producer16D4 remains open.

## Focused acceptance

tests/menu_timer.py reuses tests/verification.py and the input fixture/provider
contracts. Its51 single fixtures run at core and adapter boundaries, plus three
two-stage same-memory installer/IRQ handoffs:54 fixtures/108 comparisons. All42
own sites/three direct outcomes pass, with166 integrated sites/28 outcomes in a
654-byte known domain. The campaign executes4,945 original instructions and
compares5,633 ordered events, separating312 declared interrupt-transport events
and124 provider accesses across44 service calls.

Eight completed mutants cover opposite chain phase, DL/DH, live ES, returned SS,
actual child RET, zero DS for IVT writes, aliased POP DS and unconditional STI.
Independent checks cover IVT/saved-memory effects, actual saved registers,
modulo phase, live ES and hardware frame extent/targets/flags. Cases retain
relocation, late operands/vectors, provider stops, changed frames, missing ports,
VGA-backed stack and offset/physical word wrap. Workers are bounded by420 seconds,
384MiB process-tree commit,100,000 instructions and20,000 events per comparison.
Callback or budget failures fail the campaign and never earn mutation credit;
parent-owned temporary DLL directories are removed after workers exit.

This is scoped C acceptance, not aggregate or whole-game acceptance. Opaque
service bodies, unsupported callbacks, asynchronous timing, reentrancy and the
remaining installers/producers are still open. No original game boot is used.
