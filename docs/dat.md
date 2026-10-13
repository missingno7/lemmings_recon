# DAT reverse-stream leaf routines

The pinned main image supplies three closed near-call intervals. Names and offsets
are owned by metadata/symbols.json; their maintained ASM still assembles exactly.

| Routine | CS interval, inclusive | Bytes | Instructions | C core |
|---|---|---:|---:|---|
| WriteReverseLiteral | 1C82..1C86 | 5 | 3 | lmn_dat_write_literal_core |
| CopyReverseMatch | 1C8A..1CA2 | 25 | 19 | lmn_dat_copy_match_core |
| ReadReverseBits | 1CA3..1CB8 | 22 | 11 | lmn_dat_read_bits_core |

ReadReverseBits consumes CL bits, assembling AX with SHR DL / RCL AX. CH is the
original counter: it is decremented before each bit; reaching zero decrements SI,
loads DS:SI into DL, XORs the byte into DH and sets CH to eight. CH=0 initially
underflows to FF without loading a byte. CL=0 performs 256 iterations. AX retains
only its low sixteen bits. Final carry is the last RCL carry; final DEC CL supplies
the other arithmetic flags. DS, ES and the other general registers are preserved.

CopyReverseMatch increments BX and uses that word as its count. A zero incremented
count performs 65,536 iterations. Each iteration decrements DI and copies the live
ES byte at (DI+AX+1) modulo 65536 into ES:DI. Overlap is observed immediately.
The final BX combines the incremented count's high byte with the last copied byte.
Final flags come from INC SI, with carry retained from ADD SI,AX. The original
PUSH SI/DS/CX/ES, POP DS and later POP CX/DS/SI are represented by writes and reads
of live stack memory in the adapter. Output can overwrite these saved registers;
they are not restored from host temporaries. The 1C87 CALL ReadReverseBits entry
falls into this helper but its call instruction remains untranslated.

WriteReverseLiteral decrements DI and writes AL to ES:DI. It preserves carry and
supplies the other arithmetic flags from DEC DI, including signed overflow at
8000->7FFF. All three C cores use explicit live memory, counters and results; the
near-call adapters retain machine register effects and stack residue. No persistent
game-state copy or instruction interpreter is introduced.

## Verification domain

tests/dat.py executes only the identified original intervals with constructed
state, at three relocated load segments. Interrupts are quiescent and TF is clear.
The memory contract is a mapped 1 MiB real-mode space with twenty-bit physical
addresses. Byte cursors wrap at sixteen bits between instructions; a stack word's
second byte is physically contiguous even when the starting offset is FFFF.
Executing code and the return word must remain intact. Saved-register stack slots
may alias the copy destination. Wider code/stack self modification is still open.

470 cases compare every register, all defined final arithmetic flags and the
entire memory image, including stack residue. Cases cover every CL value, CH refill
and underflow, cursor/distance wrap, signed flag boundaries, overlapping match
copies, full-word loop wrap, saved-register corruption and return-word crossing.
All 33 original instruction sites and six branch edges execute. Compiled mutations
to zero bit-count handling, match source displacement and literal destination are
each detected. This proves these leaf contracts within the stated domain.

## Remaining resource path

The full section decoder at 1BAF and its cached/DOS-read provider at 1D2E remain
untranslated. Recover their incoming registers, header reads, low-word size behavior,
error transfers, provider effects and memory aliases before connecting these cores
into a native loader. tools/resources.py is a strict static extraction utility;
its validation and host file behavior do not define the original game's runtime
semantics. Asset files remain private and unchanged. No gameplay execution was used.
