# Timer installation and cleanup lifecycle

Game installer1644..1695 contains82 known bytes/42 sites. Its C entry in
c/timer_tail.c composes the existing timer implementation and the shared
c/interrupt_service.c transport. UNKNOWN1696..16A8 remains unresolved.

CLI precedes PUSH DS. PUSH CS/POP DS supplies the actual frame for DOS21
AX=2508, DX=17C7. The software interrupt constructs its real FLAGS/CS/IP frame
and reads IVT21 after those stores. A bound provider returns before IRET and may
change every register, canonical memory and SS:SP. Provider absence, explicit
stop and changed IRET target remain distinct stopped states. No DOS body is
inferred or translated by this seam.

POP DS1650 consumes the actual post-service stack. Its value is pushed again,
then MOV AX's complete relocated immediate at1653 supplies the sound-driver DS.
Canonical load1010 normally gives1852; the stored operand0842 and later provider
changes remain live. AX=2560, DX=0182 installs vector60 through the same DOS seam.
This establishes the vector request without claiming the driver payload was
loaded or selecting an unsupported executable dependency. The second returned
SS:SP supplies POP DS165F. No entry-DS or entry-stack snapshot replaces either pop.

The popped DS supplies the CRTC base word1FDA. ADD DL,6 wraps only DL and leaves
DH unchanged. The first bit3 poll waits for set; the second waits for clear.
Both reuse the computed DX. The caller does not enable interrupts before these
polls; DOS-returned FLAGS remain live until CLI1671. Finite status providers fail
on exhaustion. The single reload1FC9 word read follows polling, with no divisor
validation. Outputs43=36,40=CL,40=CH retain the literal delay jumps' unchanged
state. STI1694 unconditionally enables IF before the actual nearRET1695.

Port/reload ownership and identified startup/configuration/calibration writers
remain documented in timer-frontier.md. They do not establish real PIT timing.

## Full-register cleanup

The already counted43-byte16A9 cleanup now also has a full-register API,
lmn_restore_timer_interrupt_core/adapter, in c/timer_tail.c. Its actual INT1A
transport is compatible with the installer/IRQ lifecycle. c/timer_restore.c
retains its older, narrower abstract BIOS service API and tests; its evidence
must not be mistaken for actual interrupt-frame transport.

PUSH DS precedes live LES of saved vector1FBE/1FC0. PIT43:36/40:00/40:00 and
IVT08 offset-then-segment writes precede STI and POP DS. IVT/stack aliases can
replace the saved DS or outer nearRET. The popped frame owns clock259C/259E;
AH=1/AL=0 requests BIOS clock restoration. The later actual INT1A frame can
overwrite IVT08 again if SS=0. The bound BIOS provider returns before IRET,
including a changed stack and register state; the adapter consumes its actual
nearRET word. See timer-restore.md for the underlying instruction contract.

## Bounded evidence

tests/timer_install.py uses tests/verification.py for original execution, bus
access, guarded callbacks and comparison. Finite DOS vector and BIOS clock
fixtures remain outside that engine.47 single fixtures run at core and actual
nearRET boundaries. Three four-stage handoffs retain each side's actual RAM
buffer and device: direct menu installation5028, game installation1644, entry
through its installed IVT08 target17C7, then cleanup16A9. Hardware entry and
caller frames are explicitly constructed; no scheduler or startup proof is
implied. The IRQ uses independently constructed input/palette/generated-bank
state and restores its actual interrupted registers before cleanup.

The50 fixtures/106 comparisons execute all42 installer and19 cleanup sites,
all13 installer jump outcomes,901 integrated sites/76 outcomes and6,012 original
instructions. The2,984-byte known connected domain includes previously accepted
children; only82 bytes are new. Ordered events total7,283, separating2,344 declared
interrupt-transport events and588 provider accesses across145 calls. Six completed
mutants cover the live relocated sound operand, aliased savedDS, byte-only ADD,
unconditional STI, IVT store order and reload-after-poll timing.

Independent checks cover DOS vector requests, PIT byte/CLI packets, status DX,
live clock-frame selection, IVT store order, actual nearRET and interrupted-state
restoration. Cases retain changed services/IRETs, returned stacks/registers,
stack/vector/LES aliases, missing ports, three loads, VGA-backed stack and
16-bit offset/20-bit physical word wrap. Worker limits are420 seconds/384MiB
process-tree commit. Installer/cleanup comparisons allow2,000 instructions and
2,000 events; reused game/menu stages retain their100,000-instruction and
30,000/20,000-event limits. Callback/budget failures fail verification and never
count as mutation detection. Temporary DLL directories are removed after workers.

This is scoped C evidence. Opaque DOS/BIOS/ISR bodies, unsupported callback
domains, asynchronous delivery/reentrancy, hardware timing and executable
dependency loading remain open. Aggregate acceptance requires fresh full
original contracts and a complete native campaign with matching input hashes.
