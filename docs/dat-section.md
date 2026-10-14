# DAT section decoder in native C

DecodeDatSection is CS:1BAF..1C81, including its read-error transfer. Its translated
ranges contain 207 instruction bytes; the four skipped bytes at 1C1A/1C37/1C46/1C5B
remain UNKNOWN and are excluded from C accounting. ReadAndCopyReverseMatch begins
at 1C87 with a three-byte CALL ReadReverseBits and then falls into the existing
25-byte CopyReverseMatch tail. Its 28-byte interval overlaps that tested helper;
byte and executed-instruction coverage use unions to avoid counting it twice.
The ledger owns every call continuation used to reproduce live stack residue.

c/dat_section.c translates the original control flow into direct C calls to the
read wrapper and bit/literal/match cores. Its public call contract gives the live
segments, cursors, file handle, stack coordinates and flags; its result records the
original values and segment/cursor effects. The machine-register carrier is used
only by the original-code comparison adapter. No opcode dispatcher, interpreter,
asset snapshot or persistent second game-state store is used.

## Original unchecked semantics

The first read requests ten bytes into DS:SI. The decoder sets BP to incoming DI,
saves BX twice, and sets DF, but ReadDatBytes clears DF and may change ES. The low
output size word at header+4/+5 is added to DI with sixteen-bit wrap. The high size
word at +2/+3 is loaded into AX and immediately discarded by POP AX. The packed
length similarly uses only +8/+9, subtracts ten with word wrap, and requests that
many bytes into the same source buffer. Short reads are not rejected. Byte loads
and cursor arithmetic retain sixteen-bit wrapping.

After the payload read, the saved CH and checksum DH are restored. CH is header
byte zero plus one with byte wrap. The final payload byte seeds DL and is XORed
into DH. The bit reader consumes the stream backward; header bit counts outside
0..8 are not normalized or rejected. Zero is a valid immediate-refill case;
the seeded last byte still joins the checksum. Token branches select short/long literal
runs and two-, three-, four- or variable-length matches. Length/distance arithmetic
and copies use the already tested native leaf cores.

Every token completes before the unsigned DI<=BP termination comparison. A token
can write before the requested output start, or a wrapped output end can cause
early termination. Even a zero output size decodes a token before that comparison.
Live overlapping reads/writes are retained. The decoder exposes final checksum
status through AND DH,DH flags; it does not throw a checksum exception. The normal
exit restores BX from live stack memory, clears DF, and returns. Original pushes,
callee save frames and return-address writes remain observable in canonical memory.

Either read's carry error selects 1C7A: AX and DS become the original relocated
error-data segment and execution jumps to 04D0. No local stack unwind occurs. The
native core reports this as an explicit failed-read exit; the adapter reaches
the same IP with the same stack/register/flag state. The 04D0 cleanup path itself
is still untranslated and must be connected when native error ownership is ported.

## Verification and remaining scope

tests/dat_section.py runs only the identified original decoder, leaf and read
wrapper intervals, stopping at near return or the declared 04D0 boundary. Each
original case has a five-million-instruction budget; tools/difftest.py caps the
section suite process at 120 seconds, including native calls. One hundred twenty-eight cases
compare complete 1 MiB memory, every register, defined final flags and
DOS service requests, including incoming defined flags. All 235 instruction sites
execute. All 32 local decoder/leaf branch edges are covered; read-wrapper branches
are also independently covered by tests/dat_io_c.py. Three compiled section
mutations (forced checksum success, wrong returned ES, unwound read-error frame)
are each detected; dependencies are compiled without their separate mutations.

The cases include all80 original LEVEL sections, compared also with the static
extractor, including13 zero-initial-bit headers. They also include the three original sound payloads through direct reads, cache
hits and cache creation, constructed tokens covering all forms, length/distance
boundaries, zero/oversized output claims, discarded high size words, invalid bit
counts, checksum failure, accepted short reads, both read errors, cache-budget
fallback, aligned file size, provider DF effects, offset wrap and stack-word wrap.
The real sound inputs remain private and pinned; only fixture descriptions/hashes
and source are tracked. No game boot or gameplay discovery is performed.

Only AF after final AND DH,DH is excluded, because it is architecturally undefined.
Read-error exits compare all defined arithmetic flags. Interrupts are quiescent,
TF is clear, mapped physical addresses are twenty-bit, and stack word accesses
remain physically contiguous. Executing instruction bytes and active callee near
return words must remain intact. Saved data slots and source/output buffers remain
live; broader code/return-word self modification and arbitrary DOS register
clobbers are not proven by these cases. The strict static extractor's bounds,
checksum exceptions and host file policies are not part of the native decoder.

Filename preparation, cache selection and startup disabling are now native; see
dat-cache.md. File opening/attribute wrappers are native within dat-files.md's
declared boundaries. The 1B79 caller and shared 1BA9 tail are also native; see
dat-load.md. Next port higher resource ownership, investigate the
UNKNOWN allocation code at 1ED7, and connect level/resource callers and the 04D0
error path. The translated decoder does not by itself make the native game complete.
