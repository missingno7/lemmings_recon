# DAT open and attribute/retry wrappers

OpenDatFile at CS:1CB9..1CD8 (32 bytes) and CheckDatFile at 1CD9..1D2D (85 bytes)
now have native C cores in c/dat_files.c. All 117 wrapper bytes are decoded
instructions. Names, call continuations, critical-error/retry flags and the error
message offset are ledger-owned. Stored bytes and region classifications remain
unchanged. Their C contracts use transient values and live canonical memory;
machine-register adapters are confined to the original-code testing boundary.

OpenDatFile saves DS/DX/ES/DI/CX/SI, tests incoming DS cache-enabled/selected bytes,
and skips DOS open only when both equal FF. A skip retains incoming AX and returns
the equal-CMP flags. Otherwise it requests DOS AH=3D, AL=00 using DS:DX and exposes
the returned AX/flags. Restores come from live stack words, including any provider
writes to those slots. No file-error correction or cache-based handle fabrication
is added.

CheckDatFile uses the same outer save frame. With enabled=FF it calls the native
filename preparation and cache-selection cores, retaining original near-call
return-word residue. A cache hit returns before DOS attributes. Otherwise it sets
AX=4300, clears CX, and requests DOS attributes. A carry error or nonzero live
critical-error flag selects the retry/fatal branch; success restores the outer
save frame. The returned attribute CX is hidden by that restore, just as in ASM.

The error branch saves DX/CX/ES/DS/DI/SI in a second frame and selects the original
relocated main data segment. A nonzero retry-enabled byte calls game routine 4B1C
and then restores that inner frame before repeating the attribute request. It
does not repeat cache lookup. The callee may clobber saved registers, while BX/BP
and nonarithmetic flags survive into the resumed caller. AX is reset to 4300 before
the next attribute service. Both inner and outer restores read live stack memory.

With retries disabled, only the inner frame is restored. DX becomes the original
2194 message offset and execution jumps to 1949. The outer twelve-byte save frame
is deliberately left on the stack. That print/cleanup path now has a separately
tested native core (file-error.md); this wrapper's native result and oracle
adapter still expose the matching fatal exit until composed error ownership.

## Declared boundaries and verification

DOS AH3D/AH43 have narrow preserving callback contracts; the latter returns explicit
AX/CX/flags. The retry callback is an explicit **untranslated game-callee seam**
at 4B1C, not a completed native retry screen or platform replacement. It receives
the original live call inputs/save-frame coordinates and returns the caller-visible
BX/BP/flags; memory effects remain live. Its renderer/input body must be translated
and connected for full native completion. Active near-return words and instruction
bytes stay intact in this verification domain; arbitrary segment/stack-control
clobbers and interrupt races are not proved by these tests.

The INT24 critical-error callback CriticalErrorHandler (18F8) is translated in
c/dat_files.c. DOS invokes it on its own stack inside a failing AH3D/AH43 service;
it sets 1FDF = FF and returns AL = 00 (ignore). The native file-service provider
calls `lmn_dat_critical_error_core` during the service; the wrappers never set the
flag themselves. Whether DOS then reports success or CF=1/AX=53 is DOS behavior;
both outcomes reach the retry route through the live flag. 0090, 4B16 and 4B56
clear it. IRQ nesting after its STI is not modelled.

tests/dat_files.py compares original wrappers/cache helpers and the INT24 callback
against compiled C, both on direct INT24 frames and connected AH3D/AH43 failures
delivered by the DOS fixture. All 69 wrapper instruction sites and sixteen wrapper branch
edges execute. It compares full 1 MiB memory, all registers, defined exit flags,
DOS service arguments and complete retry-callee input snapshots. Cases cover every
cache-enable/select decision, both DF values on direct/open paths, open errors,
cache hit/miss/empty, DOS/critical attribute failures, one/two retries, retries
disabled by a callee, stack wrap and provider/callee writes to saved words. The
second retry observes a changed saved SI, which would expose host-temporary restores.

The retry fixture returns through the actual original pushed continuation with
deliberate AX/BX/BP/SI/DI/DS/ES/CX/DX and flag clobbers. It executes no original
4B1C body. Compiled mutations cover opening on a cache hit, ignoring the
critical-error byte, unwinding the fatal outer frame, and the callback's AL value,
flag store segment, DS restore and IRET flags. Dependencies
are compiled without their own mutation macros. Original execution has a
one-million-instruction budget per case; the suite process has a 120-second cap in
the standard runner, including native calls. Repeated permanent failures can loop
indefinitely in the original and native wrappers; no attempt limit is added.

AF is excluded only at the incoming AH43 service boundary because XOR CX,CX makes
it undefined. All defined exit flags are compared. Existing cache helper suites
independently establish their other branches and undefined-AF contracts. The tests
use declared DOS/callee effects, not actual DOS or a booted game.

The 1B79 caller now connects these cores directly; see dat-load.md. Next port higher
section-selection/seek/close ownership, recover retry-screen and
fatal print/cleanup ownership, and investigate UNKNOWN cache allocation at 1ED7.
Real file services, timing, alias closure and complete game integration remain open.
