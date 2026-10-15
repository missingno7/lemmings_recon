# Raw-resource bus and fatal connection

The1916 raw reader now has optional-bus CPU access through its existing logical
call/result fields. The old APIs pass a NULL bus and retain their ABI. All five
saved words, the DS:2528 filename-offset store, live stack pops and adapter RET
use sequenced bytes: low then physical+1 with20-bit wrap. SP wraps at16 bits
between words. The bus owns CPU accesses; raw DOS provider memory writes are
separate service effects on the canonical memory/device fixture.

Raw DOS services remain required complete providers with the established
contract: return AX and explicit flags, preserve other general registers,
segments and SP. This does not introduce an arbitrary all-register DOS domain.
Short and empty successful reads remain accepted. Close setup replaces AH with
3E while retaining read AL. Failure DX selects2194/21A5/21B6; open failure leaves
five saved words, read/close failure two. No failure frame is unwound.

`c/resource_raw_full.c,h` compose the bus core directly with the1949 file-error
logical core. SI/DI/BP/SS pass through the raw result under its provider contract;
all fields returned by error-print/video/cleanup services remain live afterward.
The fatal transfer adds no CALL frame. The core's normal READY exit stops before
RET1939; the full adapter consumes the actual outer word. Fatal termination,
missing printer services and changed child returns propagate distinct statuses
without an outer RET. The loaded main-data segment comes from the relocated194B
instruction operand at the boundary adapter or an explicit logical core argument.

The original raw decoded range still has49 bytes/27 sites, excluding unresolved
193F and1945. The connected domain includes the already tested1949 printer,
video restore,04EA suffix and keyboard restore:147 distinct decoded bytes and
72 sites. Eight raw branch/jump edges plus four printer/tail edges are required.
No new instruction classification or global reachability is claimed.

`tests/resource_raw_full.py` first checks an independent raw event/state model
and the existing printer/suffix models against actual original instructions.
Each fixture is checked at four boundaries: standalone bus adapter, standalone
bus core, connected adapter and connected core. The matrix covers normal and
all three errors, count/handle boundaries, SP/A20 wrap, saved segment/return
overwrites, filename-store/stack aliases, missing printer services, changed video
returns, and VGA-backed stack/global stores or provider destination writes.
Provider device writes are declared fixture effects, not fabricated CPU events.

Every native boundary repeats with NULL bus outside the VGA profiles. Full RAM,
all returned CPU state, defined flags, ordered CPU bytes, raw DOS arguments and
AX/flags results, printer inputs/outputs, printed bytes and VGA state must match.
Four completed mutants reverse the filename-word store order, restore cached
segments, unwind a fatal frame or add a synthetic CALL before1949. Timeouts,
callback budgets/errors, memory ceilings and oracle failures cannot count.

The accepted matrix has87 cases at each of four native boundaries, with75
NULL-bus repetitions at each boundary and12 VGA profiles. Original execution
also checks four boundaries per fixture. The standalone legacy RAM API retains
its46-case/three-mutant regression, now in a bounded worker whose parent owns
and removes the temporary DLL directory.

Workers are bounded to120 seconds and384 MiB process/640 MiB tree commit on
Windows. Original runs have512 instructions, traces512 events, raw services
three calls and printer services64 calls. Callback exhaustion hard-exits86 and
errors87. Compiler runs have60 seconds/256 MiB process bounds. The parent removes
owned temporary DLL directories only after the worker terminates.

The domain remains intact code, same-CS service resumes, TF clear and quiescent
IRQs. Broader provider ownership, resource-selection parent connections, sound,
protection, unresolved static code and native gameplay remain open. Global C
coverage awaits fresh complete terrain acceptance and affected reports.
