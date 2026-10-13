# Raw resource open/read/close core

ReadRawResourceFile is CS:1916..1948. c/resource_raw.c translates its 49 instruction
bytes, excluding the skipped UNKNOWN bytes at 193F and 1945 through ledger-owned
C ranges. It reads ordinary bytes directly; it does not invoke the DAT decoder.
All original names, offsets and the shared 1949 error continuation remain in the
symbol ledger and byte-exact maintained ASM.

The core takes explicit filename/destination segments and offsets, requested count,
incoming handle, live stack coordinates and flags. It returns the original values,
segment effects and error stage. The register adapter is only an oracle boundary;
normal C callers can use the core directly. No extra persistent game state or CPU
interpreter is introduced.

The original save order is DS, ES, AX, ES, CX. AX initially supplies the destination
offset, ES the destination segment and DS:DX the filename. The live filename offset
is written to the caller's LastResourceFilenameOffset field before DOS open. A
successful open sets BX to returned AX, then pops CX, DS and DX to select the read
count, destination segment and destination offset. DOS read returns AX. The routine
does not compare it with the requested count: short and empty successful reads
are accepted. The close request changes only AH to 3E, retaining read AX's low byte.
On close success, ES and DS are popped from live saved words and the routine returns.

| Error | Message offset | Stack effect at 1949 transfer |
|---|---|---|
| Open carry | 2194 | All five saved words remain; BX and DS retain incoming values |
| Read carry | 21A5 | Three words have been popped; saved ES/DS remain; DS is the read destination |
| Close carry | 21B6 | Saved ES/DS remain; DS is the read destination |

No close is issued after an open/read carry error and no saved frame is unwound
on the error transfer. The 1949 print/cleanup body remains untranslated. These
are explicit native result exits with the same oracle IP, registers, flags and
stack memory, rather than a host exception or corrected cleanup policy.

## Verification domain

tests/resource_raw.py compares only the original identified interval with native
C in 46 constructed cases at three loads. All 27 instruction sites and eight
branch edges execute. Full 1 MiB memory, every register, defined flags and complete
open/read/close request traces are compared. Cases include all three errors, zero
and FFFF requested counts, short/empty reads, destination and stack wrap, zero/FFFF
handles, reads overwriting saved ES/DS, and the filename-global store overwriting
saved DS. Close traces verify the retained low AX byte after the partial AH write.

Three compiled mutations are detected: clearing AL during close setup, restoring
segments from host temporaries, and unwinding a fatal frame. The original instruction
budget is 1,000 per case; the standard runner caps the process at 120 seconds,
including native calls. DOS fixtures preserve registers other than AX and return
explicit flags; all defined exit flags are compared without an AF exclusion.

The domain is quiescent mapped twenty-bit memory with clear TF, intact instruction
and active return words, and physically contiguous stack word accesses. Constructed
read-provider bytes advance with sixteen-bit cursor wrap; this does not establish
actual DOS behavior across a segment end. Real DOS service behavior, interrupts,
broader alias closure and the shared fatal cleanup still require integration.
Only caller code is executed; no game boot or gameplay discovery is used.

Next port higher section-selection and startup callers, file seek/close ownership,
and the resource-dependent data/graphics transformations. The primitive alone is
not a complete native loader or game.
