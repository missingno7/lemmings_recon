# Timer, vector and BIOS clock restoration

`RestoreTimerState` is the pinned straight-line `16A9..16D3` routine: 43
decoded bytes, 19 sites, no branches. Its callers are `02FB`, `04D0` and
`0EDF`. The nearby unresolved bytes `1696..16A8` remain unresolved.

Startup clears AH and invokes INT 1A at `0016`, then stores DX at DS:259E
and CX at DS:259C. The ledger names these two words `SavedBiosClockLow`
and `SavedBiosClockHigh`. The clear at `0031` covers DS:0000..2011 and
does not include them. These names identify the stored service result,
not elapsed-time ownership or a validated clock range. Startup's DOS
3508 query at `005D/0060` supplies `SavedTimerVector` at DS:1FBE.

The restore sequence is observable in this order:

1. Push incoming DS to live SS:(SP-2), clear IF, load AL=36 and output
   that byte to port 43. Incoming AH and arithmetic flags survive this output.
2. XOR AL with itself, output zero twice to port 40, then XOR AX with itself.
   PF/ZF become set and CF/SF/OF clear; AF is undefined. No divisor validation
   is added. The device implementation and resulting tick rate remain open.
3. Read the vector offset and segment through live incoming DS, in that order.
   Set DS=0, write offset at physical 20..21 and segment at 22..23. All reads
   precede the IVT stores; ES retains the loaded segment until the BIOS service.
4. Set IF unconditionally, then pop DS from live SS:SP. An IVT write may
   have replaced this saved word. Read high and low clock words through the
   actual popped DS, load AH=1 and invoke INT 1A.
5. Propagate the returning provider's general registers, DS/ES/SS/SP and
   defined flags. The adapter executes the actual near RET through that
   returned stack. The core stops immediately before RET and creates no
   additional stack frame.

`c/timer_restore.c,h` use transient logical values and the canonical memory
image, with `LmnRegs` confined to the adapter. Optional raster-bus callbacks
own every CPU data/stack byte. Words access low byte then physical+1 with
20-bit wrap; SP wraps at 16 bits between words. VGA read plane 2 and write
plane 0 fixtures retain the difference between PUSH stores and POP reads.

The byte-output provider preserves register and flag values but may change
device state and canonical memory through its context. The clock provider
models a returning INT 1A boundary and may update all twelve logical fields
and canonical memory. Providers resume in the same CS with intact decoded
code, TF clear and no delivered IRQs. Missing byte-output service stops
before `16AD` with DS pushed and IF clear. Missing clock service stops
before `16D1` after all port outputs, IVT writes, STI, POP and clock reads.
These continuations expose an unimplemented service; they do not skip it.

`tests/timer_restore.py` first compares an independent event/state model with
the original instructions, before compiling C. Its matrix has 291 primary
and 291 auxiliary core-boundary cases: all 256 incoming AH bytes, 26 alias,
wrap, device and provider profiles, and nine missing-provider cases at three
loads. Four VGA profiles have separate plane/latch checks; the other 287
cases also compare the NULL-bus RAM path at each boundary. The native gate
requires four completed mutant mismatches: conditional STI, cached entry DS,
reversed IVT stores, and a cached entry-stack RET target. A guard, callback
failure, timeout or memory-limit failure cannot count as a mutant mismatch.

The worker has a 120-second bound and Windows process/tree commit limits of
384/640 MiB. The original has a 24-instruction limit; traces cap at 64 events,
port calls at three and BIOS calls at one. Callback exhaustion exits the worker
with 86 and callback errors with 87. Compilers have a 60-second/256-MiB
process limit. Parent-owned temporary DLL directories are removed after
terminal completion or failure. Reports contain source hashes and separate
original-only and native evidence. No broad native campaign is required.

Hardware timing, STI's interrupt shadow, asynchronous IRQ delivery, actual BIOS
clock implementation, broader `04D0` cleanup and full-game reachability remain
open. Testing this already decoded leaf does not classify additional bytes.
