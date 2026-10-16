# Mouse private IRQ bridge

`MouseIrqBridge` occupies 0F70..0F9F: 48 bytes, 20 instruction sites and
four outcomes at two conditional branches. This is a static contract; its
external INT62 and asynchronous interrupt behavior are not a verified C domain.

Startup selects private vector 0C at 0040, captures its old ES:BX through DOS35
at 006A..0075, and installs that pointer as vector 62 through DOS25 at 0081.
`InitializeMouseDriverHooks` later installs CS:0F70 at the live selected private
vector at 0F55..0F60. The INT33 callback CS:0F6F is a separate RETF stub.
The live IVT entry controls INT62 dispatch, rather than a cached SavedPrivateVector.

The bridge pushes DS and AX through live SS before reading the relocated MOV
immediate at CS:0F73. Stack/code aliases can therefore change its data frame.
It increments bytes DS:2002 and DS:2003, invokes INT62, then decrements 2003
and 2002 through the returned DS. Startup's clear of DS:0000..2011 initializes these
counter bytes; their wider ownership and nesting meaning remain unresolved.
Both counters wrap as bytes. INC/DEC preserve CF and define their other
arithmetic flags; the service can observe the incremented values.

The first gate reads live CS:83BE and tests AL. This byte aliases
ChecksumCursor+3 in the emitted four-byte window; its ledger name does not
reclassify surrounding bytes. Stores 00B4/4BE7 write FF, and 00FE writes zero.
Nonzero skips the mirror restoration. Otherwise CMP returned DS:2002,0 supplies
the second gate. The zero path is explicitly present and must remain testable.

On that path, PUSH DX/CALL 587F/POP DX uses the actual returned stack. The
restorer preserves entry ES and unconditionally sets IF; the bridge does not
save ES around INT62. POP AX, POP DS and IRET also use live returned SS:SP.
Final IRET restores IP, CS and FLAGS from actual memory, without restoring ES.

A future C composition needs an opaque external INT62 provider with full
LmnRegs, canonical RAM and an explicit frame contract. Software INT pushes
FLAGS, CS and return IP 0F81 on the current stack, clears IF/TF and samples the
current IVT target after these writes. A normal provider IRET consumes the
live nested frame; changed SS/SP, frame words, DS/ES and flags must flow back.
Changed continuation targets stop at an explicit boundary. Do not assume a
known handler body or normalize the stack to its entry values. The existing
pcspeaker interrupt frame model is a closer starting point than the narrower
sound interrupt result, which omits returned ES/SS.

`tests/interrupts.py` has original-only bridge fixtures with a stubbed INT62
and 587F. Their historical evidence does not establish native composition,
returned-stack/ES contracts, actual IVT dispatch, IRQ scheduling or gameplay.
The next parent work should compose the verified mirror leaf at this declared
provider/frame seam and retain the STI/RET interrupt window explicitly.
