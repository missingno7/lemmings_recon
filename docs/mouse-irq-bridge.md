# Mouse private IRQ bridge

`MouseIrqBridge` occupies 0F70..0F9F: 48 bytes, 20 instruction sites and
four outcomes at two conditional branches. Its maintained C11 core and outer
IRET adapter are in c/mouse_irq_bridge.c. They compose the native mirror child
at a declared external INT62 provider seam. External handler instructions and
asynchronous interrupt behavior remain outside this C domain.

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

The C composition uses an opaque external INT62 provider with full
LmnRegs, canonical RAM and an explicit frame contract. Software INT pushes
FLAGS, CS and return IP 0F81 on the current stack, clears IF/TF and samples the
current IVT target after these writes. A normal provider IRET consumes the
live nested frame; changed SS/SP, frame words, DS/ES and flags must flow back.
Changed continuation targets stop at an explicit boundary. Do not assume a
known handler body or normalize the stack to its entry values. The existing
pcspeaker interrupt frame model is a closer starting point than the narrower
sound interrupt result, which omits returned ES/SS.

The provider API binds a callback to one exact current CS:IP target. Missing
or mismatching bindings stop after the frame/vector accesses with the live
target state. The callback returns zero immediately before its external IRET;
the bridge then consumes the actual frame through returned SS:SP. A nonzero
return preserves the full callback state and service status without IRET.
Changed nested IRET and child RET targets stop before further bridge cleanup.
The core stops before the outer IRET; its adapter consumes the actual outer
IP/CS/FLAGS words only on READY. IRET FLAGS use `(word & 7FD5h) | 2` as in the
existing PC-speaker model. This transport declares CS-before-IP IVT reads
after frame writes; it does not establish historical CPU bus-cycle order.

## Scoped verification

tests/mouse_irq_bridge.py passes 35 constructed fixtures at both boundaries:
70 bridge comparisons, all 20 parent sites/four JNZ outcomes, 44 actual native
mirror calls, and two direct initializer comparisons sharing the same runtime
RAM/device with the bridge. Site accounting separates 20 parent, 38 mirror and
25 initializer sites (83 unique total); the 48 parent bytes are added once.
The original instruction count is 2,869, including 50 initializer instructions.

The bridge comparisons cover 4,244 ordered accesses: 2,988 identified-body
accesses, 1,072 declared INT62 transport accesses and 184 constructed provider
accesses. Initialization adds 52 separately compared accesses. Provider and
transport effects earn no external original instruction coverage. Independent
assertions predict all nested/saved/outer frame words, service-entry registers,
byte INC flags and the post-write IVT read order. Ten numeric C mutants are
detected only after their native calls complete.

Profiles cover three relocations, a late MOV operand, both gates and byte wrap,
provider-written gate/flags, returned DS/ES/SS/SP, changed saved AX/DS, actual
child/outer words, reserved IRET flags, effective and physical wrap, and VGA
stack aliasing. The VGA case writes the literal child return 0F9C into all
planes; the restored read-mode-one comparison against zero makes the CPU read
its complement F063. The original and C both stop at that changed child target,
before POP DX. This is preserved device behavior, not a corrected stack value.

Workers have 420-second/384-MiB process-tree limits and bounded instruction/bus
traces. Native callbacks fail-stop; budget/fault/timeout failures earn no mutant
credit. Owned DLL directories are removed after workers exit. The matching
reports pin 24 consumed input paths, including the reused mirror oracle and C
child. The exact gate separately pins ledger/header/ASM identity. These results
close the declared bridge composition; external body, IRQ/debug delivery,
scheduling and gameplay acceptance remain open. The older interrupts.py suite
still supplies its distinct original-only stubbed-handler regression coverage.
