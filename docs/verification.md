# Shared differential verification

New focused suites use tests/verification.py. Suites declare instruction ranges,
supported entries/returns, finite providers and independent expectations. They do
not implement another CPU runner, memory bus, ctypes callback guard or full-state
comparator. tests/port_io.py is the first migrated consumer; tests/input_poll.py
and tests/ui_commands.py use the same engine for the connected input subsystem.
tests/timer_tail.py composes those domains through the same engine.
tests/palette_timer.py reuses it for the sequential DAC leaf and both timer
palette callers, with finite byte-port providers and independent packet checks.

OriginalMachine runs exact loaded instructions in Unicorn and checks each reached
instruction against the pinned relocated image. It rejects undeclared code writes
and transfers outside the supplied domain. Near RET executes against actual live
SS:SP; child continuations and core/adapter boundaries are declared by the suite.
Declared outer IRET boundaries also execute the original instruction in adapter
mode. A declared far chain must be a decoded far JMP: the runner executes that
instruction, retaining its actual pointer reads and target, then invokes the
bound fixture provider before consuming its returned IRET frame. The provider's
return is not recorded as a direct original jump edge. Opcode guards stay exact.
Instruction and phase limits fail the campaign. Pausing before an unsupported
CALL or missing port provider does not claim execution of that instruction.

Direct branch coverage includes decoded LOOP instructions as well as Capstone's
jump group: Capstone tags LOOP separately. The palette campaign accounts for
both loop outcomes through the same executed-edge observer. This corrects
coverage accounting without replacing or changing original instruction execution.

An explicitly declared mutable code operand must match a complete decoded
immediate, with its source/producer contract documented beside ASM and in the
ledger. The visibility child uses this for the relocated IMM16 at4137. The
runner guards every other instruction byte, observes canonical operand writes,
and invalidates Unicorn's decoded cache before resuming the actual instruction.
It does not emulate that instruction in Python or admit unexplained opcode
changes. Static path infeasibility is reported separately from executed sites;
it does not make UNKNOWN code dead or remove literal C behavior.

Software interrupt transport is explicitly declared: live FLAGS/CS/IP frame
writes, IF/TF clearing, current IVT reads, an opaque provider stopped before IRET,
then the actual returned SS:SP frame. Transport/provider accesses are distinguished
from original executed instructions. This is not discovery of an external ISR or
a model of asynchronous interrupts. Suite-specific providers and expected
algorithms stay outside the shared engine so the C and oracle do not share game
logic. Device models retain their independent known-answer checks.

The native interrupt_service.c transport is shared by the INT33 mouse caller
and INT60/61 command callers. Their provider descriptors carry full returned
registers, including DS/ES/SS:SP. This consolidates frame mechanics without
claiming the opaque service bodies or asynchronous IRQ delivery are translated.
The timer's saved-INT08 chain reuses the same bound-provider/IRET consumer after
its own literal synthetic-frame writes and far-pointer reads; its outer hardware
IRET uses that consumer without imposing the synthetic return target. Word OUT
is accepted only when the fixture supplies its word-port contract.

BusAccess supplies one canonical RAM image, VGA aliases and bounded ordered
observations. NativeCallbacks turns callback errors into immediate worker failure;
Python ctypes exceptions cannot unwind a native loop. compare_states checks all
registers with defined flag masks, canonical RAM, ordered events, provider effects
and VGA state/traffic. Callback, time, instruction or memory exhaustion never
earns mutation credit. Resource limits and temporary-DLL cleanup still belong to
tools/bounded_process.py and the registered tools/difftest.py launcher.

Migrate existing suites when their subsystem changes or a second consumer needs
their machinery; do not rewrite the entire test tree before continuing the game.
Use coherent dependency clusters and test leaf-to-parent handoffs. Choose mutation
witnesses for distinct contracts rather than a fixed count. Preserve previously
proved domains and quirks during migration; rerun affected campaigns and compare
their site/edge/event accounting.

Reports pin consumed code, helpers, headers, oracle inputs and tool semantics.
Do not renew stale evidence merely by retaining a file. Keep status-only ledger
changes and progress prose outside behavioral hashes when they are not consumed.
Do not remove real dependencies to avoid invalidation. Focused acceptance is not
aggregate acceptance: tools/verify.py --contracts and a matching complete native
campaign remain the aggregate gates. The architecture and native smoke-test
completion bar are documented in architecture.md.
