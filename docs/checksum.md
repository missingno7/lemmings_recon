# Checksum routines

This cluster translates the canonical image ranges `CS:8343..8362` and
`CS:8363..83B6` (exclusive ends `8363` and `83B7`). The byte ranges are 32 and
84 bytes, respectively. The core C functions use the generated
`c/lemmings_sym.h` symbol ledger and take a mutable 1 MiB DOS physical-memory
image plus CS and the live register values needed by each routine. They return
AX/BX/CX, flags, and a defined-flags mask. Boundary adapters separately model
the DOS register and near-call stack effects. Segment:offset access wraps at
20 bits; 16-bit offsets wrap independently.

`CS:8343` preserves the incoming DS on the stack, loads DS from CS, and XORs the
ten bytes at `CS:188F..1898`. It initializes phase `CS:83B9` and accumulator
`CS:83BA` to zero and cursor `CS:83BB` to `188F`, while returning the XOR in AL,
the advanced cursor in BX, and zero in CX. The `push cs` / `pop ds` sequence
leaves the temporary CS word in stack memory at `SS:SP-4`; the routine restores
DS and returns through the caller's near-return word.

`CS:8363` increments the phase byte. When it wraps to zero, it sets the cursor
to zero, clears the accumulator, exchanges the prior accumulator into AL,
clears AH, and returns. For a nonzero phase it processes at most `0800` bytes
from `DS:[BX]` (DS is temporarily CS), updating the accumulator and cursor.
Before each byte it stops only if BX equals `CS:83B7`. That path stores the
accumulator, sets AL/AH and the phase to `FF`, and leaves the cursor as-is. A
cursor already greater than `83B7` does not satisfy the equality check and
continues through the full 2048-byte chunk, with 16-bit BX wrap. The normal
chunk path returns AL as the updated accumulator, AH as `FF`, CX as zero, and
stores both accumulator and cursor. Its `inc bx` determines the final arithmetic
flags; `loop` does not alter those flags on the target ISA.

The bounded differential runner is `tests/checksum.py`; it compiles the C as a
Windows DLL using `tools/cbuild.py`, executes only these identified routines
under Unicorn against constructed register and memory state. Each run unpacks
the pinned EXE and applies relocations for load segment `1010`; it does not use
the cached `build/canonical.bin`. The runner compares all registers and the
full 1 MiB memory image, and records input hashes and coverage in the ignored
generated file `build/differential.json`. The constructed SS:SP return word and
saved-register stack slots stay outside the checksum state and scan ranges, so
pathological stack aliasing is not covered. Fourteen cases cover the phase-wrap
branch, both sides of the cursor-limit branch, both `loop` outcomes, a full
chunk, 16-bit pointer wrap, and final BX values `7FFF` and `8000`. Three cases
vary the checksum window; another scans across the phase byte after it has been
updated. AF is compared for every case except phase wrap, which ends in XOR
AH,AH and leaves AF undefined. Three separately compiled C mutations are
required to fail against the same oracle cases. The 8363 routine's static
reachability remains unresolved; these tests establish bounded behavior only.

Two stack fixtures cross the segment end with an odd return word at SP=FFFF and
a saved DS word after a push from SP=0001. Word bytes remain physically contiguous;
only the offset update between instructions wraps. The previous C adapter wrapped
the second byte back to segment offset zero. Both new cases fail against that
prior implementation and pass after correcting word access. Stack residue is
compared byte-for-byte rather than excluding the discrepancy.
