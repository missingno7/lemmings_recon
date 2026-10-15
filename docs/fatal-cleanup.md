# Fatal cleanup and terminal exit

`DatFatalTransfer` at `04D0` is a cleanup continuation, not a returning
function. Its 41 decoded bytes through `04F8` contain 15 caller sites and
one conditional branch. `ExitAfterKeyboardRestore` at `04EA` is also reached
independently by the error-output path's jump at `106B`. Its 15 bytes overlap
the full caller. No new instruction bytes or reachability are inferred.

The full path calls the timer restore, keyboard vector restore, private vector
restore and video restore cores. Each original near CALL first pushes its
continuation onto live SS:SP. Each child propagates all returned CPU state;
the composer reads and consumes the actual return word through the returned
stack. A changed target stops before that target executes. A missing child
restore provider stops inside that child with its active frame, without a
synthetic return. Missing caller services stop at their own INT boundaries.

The mouse gate is read through the DS returned by video restoration. Only
byte FF at DS:1F73 skips the service; all other 255 values reach AX=000C,
CX=0, INT 33. The CMP defines all arithmetic flags. XOR CX,CX defines its
logic flags and leaves AF undefined. The returning mouse provider may change
all general registers, DS/ES/SS/SP, flags and canonical memory. The second
keyboard restore at `04EA` then runs even after a mouse skip. It must not be
deduplicated with the first keyboard call.

The suffix loads DX=20AC and AH=09, preserving live AL and DS for DOS output.
`CleanupExitMessage` labels the stored dollar-terminated text beginning
“Exiting Lemmings”; arbitrary aliases/providers may change those live bytes.
`MouseServicesDisabledByte` names the FF skip flag: startup's clear supplies
zero, the `138B` option path writes FF and failed/skipped initialization at
`0F69` also writes FF. This name does not prove a hardware driver exists.
The ledger owns all names and offsets; stored bytes/classifications are unchanged.

After DOS09 returns, only AX is replaced with 4C00. DOS termination receives
every other returned register, segment, stack and flag value. The explicit
terminal provider has no returned CPU state. Its host callback returns only
to report `TERMINATED`, with numerical post-INT continuation `04F9`. Neither
the native core nor the original test executes `04F9` or an outer RET. A
missing terminal provider stops before INT at `04F7`. Missing mouse/message
services similarly stop at `04E8`/`04F2`.

`c/fatal_cleanup.c,h` compose the three restore clusters through their logical
cores. `LmnRegs` appears only in the boundary adapter. One canonical memory
image supplies state, fields, active CALL frames and returns; there is no
shadow game state. Optional raster-bus accesses preserve byte order, 20-bit
physical wrap and 16-bit SP wrap between words. Providers resume in the same
CS with intact decoded code, TF clear and no delivered IRQs. Actual device
timing, BIOS/DOS implementations and asynchronous IRQ behavior remain open.

`tests/fatal_cleanup.py --original-only` checks an independent logical model
against the pinned original before native compilation. It exercises every
mouse-gate byte, both entries, missing providers, changed returns at every
child call, IVT/stack aliases, provider changes between children, live message
bytes, A20/SP boundaries and VGA-backed fields, gate, stack and message reads.
The C gate compares the logical core and register adapter, with NULL-bus RAM
repetitions outside VGA cases. Full canonical RAM, all returned CPU state,
defined flags, ordered CPU memory/port events, provider inputs/outputs,
message bytes and VGA planes/latches are checked separately.

The accepted matrix contains 362 adapter and 362 auxiliary logical-core
comparisons: 312 full-entry cases and 50 suffix cases. Five VGA profiles have
device-specific checks; the remaining 357 also repeat each boundary with a
NULL bus. All 256 mouse-gate bytes, 56 integrated sites and both branch edges
are exercised. The original-only report records 362 original/model executions;
the two native ABIs share those expected terminal or continuation states.

Four compiled caller mutants omit the final keyboard call, use an entry-time
mouse gate, ignore a changed child return or discard DOS09's returned stack.
Each must finish and produce a completed differential mismatch. A timeout,
process memory failure, instruction/access budget or callback error cannot
count as detection. Each worker has 120 seconds and Windows process/tree
commit limits of 384/640 MiB; compiler runs have 60 seconds/256 MiB process
limits. Original execution is capped at 80 instructions, traces at 256 events,
ports at three, service calls at nine and the declared DOS09 fixture at 64
bytes. The parent owns and removes temporary DLL directories after termination.

Byte accounting unions the 41 caller bytes with the already translated
92 child bytes: 133 distinct bytes and 56 sites. Repeated keyboard execution
does not add sites. This scoped cleanup contract does not connect every fatal
resource path or prove complete gameplay. Complete terrain acceptance and fresh
global reports remain required before promoting aggregate C coverage.
