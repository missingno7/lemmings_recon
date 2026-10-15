# Display status bit cycle

WaitForDisplayStatusBit3Cycle occupies1550..1561:18 bytes,9 instruction sites,
two conditional branches with four outcomes and no game callees. The ledger
owns its names and the live DS:1FDA controller-base field. Startup00503 stores
the word read from0040:0063;0134A/0137C install03D4. The leaf reads this field
once, adds6 toDL alone, waits until input bit3 sets and then until it clears.
DH does not receive the byte carry. No order/bounds check or cached controller
state replaces the original memory read. The retry UI4B1C is one of its callers.

IN replaces only AL, leaves AH and flags intact, and can have declared device
or canonical-memory effects through the byte-port provider. TEST AL,8 follows
every input. It defines CF/OF/SF/ZF/PF, leaves AF undefined and preserves control
flags. The first IN observes the full ADD-DL flags; later inputs observe the
preceding TEST flags. Neither IF nor DF is changed by this leaf.

The logical C core leaves READY at1561 before the actual nearRET. Its adapter
reads the then-live SS:SP word through the optional raster bus and advances SP
in16 bits. Word bytes are low then physical+1 with20-bit wrap. A missing byte
input provider stops before1557 after the base read and ADD, with no invented
input value or outer return. The existing raster byte-port provider type is
reused; only in_byte is required. CPU register effects remain those of IN; the
provider may mutate canonical memory and explicit device context.

Original polling has no timeout. Native C retains both ordinary polling loops.
The tests use finite constructed sequences and separate process/access budgets;
exhaustion fails verification and never counts as a mutant. Tests compare the
original and an independent model before native acceptance, with full RAM,
twelve CPU fields, defined flags, ordered CPU/port events and device planes.
Null-bus repeats apply only where the bus is plain RAM without read effects.
VGA fields/RET and provider effects use explicit device context, not fake CPU
write events. Four compiled mutations must finish with an actual mismatch:
word-sized port addition, skipping the set phase, reloading the base and caching
the entry return. Workers are serial,120 seconds/384MiB process/640MiB tree;
temporary DLLs belong to their parent. Intact code, same CS, clear TF and
quiescent IRQ remain explicit. Physical hardware timing/IRQ ownership is open.
