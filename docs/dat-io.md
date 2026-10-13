# DAT file/cache read contract

ReadDatBytes is CS:1D2E..1E1B, 238 stored bytes. Its closed control flow contains
106 instructions, four conditional branches and four direct jumps (twelve edges).
Its C11 core in c/dat_io.c translates all 237 instruction bytes; the one skipped
UNKNOWN byte is excluded through explicit ledger-owned C ranges.
The NOP at 1D7C remains UNKNOWN: the preceding jump bypasses it, but that alone
does not prove it can never execute. Names and DS offsets belong to the symbol
ledger; maintained ASM uses the generated segment-relative expressions.

The decoder calls it twice, with BX=file handle, CX=request count and DS:DX=target.
The wrapper saves DI/SI/DS/BX/CX/DX in that order, clears DF, and selects the main
data frame. It never saves incoming ES. Its behavior depends on two live bytes:
DatCacheEnabled and DatCacheSelected, each compared specifically with FF.

| Path | Behavior | Returned effects under preserving DOS fixtures |
|---|---|---|
| Enabled != FF | DOS AH=3F into caller DS:DX | AX=read result/error; DOS flags; CX/BX/DX/DS preserved; ES retains provider effects |
| Enabled=FF, Selected=FF | Copy CX live bytes from cached segment:offset | AX=source segment, CX=0, ES=caller DS; DI/SI/BX/DX/DS restored; equal-CMP flags, DF clear |
| Enabled=FF, Selected!=FF, cache does not fit | FCB AH=23, then ordinary DOS read | As direct path; FCB contents and save-frame residue are additionally changed |
| Cache creation fits | One DOS AH=3F request of FFFF bytes, descriptor write, then cached copy | AX=cache source segment, CX=0, ES=caller DS; flags from ADD descriptor offset,0; DF clear |

These are calling contracts, not assertions about arbitrary interrupt clobbers.
The bounded DOS fixtures preserve registers other than AX, and replace arithmetic
flags. Tests also explicitly set DF in two provider returns; copies then run
backward and DF remains set on return. A native DOS boundary must make its
preservation rules explicit. Returned
saved registers can differ if file/cache writes overwrite their live stack slots;
the tests include that case. Neither ES restoration nor untouched saved registers
may be assumed when connecting this wrapper to the native section decoder.

## Cache creation and preserved quirks

The wrapper sets the FCB record size to one and invokes AH=23 using DatCacheFcb.
It reads the resulting DWORD at FCB+33 regardless of the returned AL status. The
required paragraph count is the low word of (size>>4), incremented if size's low
nibble is nonzero; that increment can wrap. Comparison with
DatCacheRemainingParagraphs is unsigned. A fit increments the byte record count
with wrap and subtracts those paragraphs. The thirteen descriptor bytes themselves
are not added to this size reservation.

The descriptor begins at DatCacheFreeSegment:DatCacheFreeOffset. Its first eleven
bytes are copied live from FCB+1; the following word stores the DOS read's AX.
The data begins at (free offset+13) modulo 65536 in the same segment. The wrapper
sets DatCacheSelected=FF before issuing its FFFF-byte read. It treats returned AX
as a length even when carry signals an error. Later arithmetic replaces carry;
cache-fill errors do not propagate as direct-read errors do. No validation or
short-read rejection is added.

The new free pointer uses a sixteen-bit addition of data offset+returned AX,
then adds that wrapped sum divided by sixteen to the old segment and keeps its
low nibble. Overflow discarded by the first addition is not restored. Cached
copies update SI and DI according to live DF, modulo 65536, and never advance their segments when
offsets wrap. They read and write live memory byte by byte, including overlap.
The read pointer is updated through the data segment popped from live stack memory.

The cache-enabled/selected flags, record start, read cursor, free cursor, remaining
paragraphs, record count and FCB now have ledger-owned names. Other cache routines
at 1E1C/1E64 and the UNKNOWN allocation code starting 1ED7 still need contracts.
Naming these fields does not extend the existing byte classification or establish
complete write ownership.

## Independent bounded evidence

tests/dat_io.py executes only the original ReadDatBytes interval, with constructed
DOS AH=23/AH=3F providers and a separate functional cache model. Forty-five cases
cover all 106 instructions and twelve branch edges at three loads.
They compare complete 1 MiB memory, every register, defined flags and the DOS
request trace, including incoming defined flags at each DOS boundary. Input DF
is set; the wrapper clears it before selecting a path. Preserving providers leave
it clear, while the two deliberate DF-clobber fixtures return it set. Cases include zero
counts, three stack-wrap points, return-word crossing, direct errors/short reads,
ignored FCB/cache-read errors, exact and insufficient cache budgets, paragraph and
record-count wrap, cache-pointer overflow, wrapped copy cursors, overlap and writes
into saved-register slots, full FFFF-byte cache fills and full FFFF-byte cached copies.

The mapped-memory domain uses twenty-bit physical addresses and physically
contiguous word accesses. Constructed read-service writes use sixteen-bit cursor
increments; these fixtures do not prove actual DOS behavior across a segment end.
Executing code and the near return word remain intact. TF is clear and interrupts
are quiescent. Real DOS/FCB handling, arbitrary provider clobbers, cache lookup and
allocation are still separate obligations. This suite adds provider evidence,
not C translation coverage or game execution coverage.

## Native translation

lmn_dat_read_core takes an explicit data segment, a transient call contract and
narrow file-size/read services. The call contract includes original live stack
coordinates and saved cursors because aliasing can change their restored values.
It returns explicit values and segment/cursor effects. lmn_dat_read_adapter uses
the machine carrier only at the original-code testing boundary and reads the
original relocated data-segment operand there. Normal C callers can call the core
directly; no interpreter, opcode dispatch or persistent game-state copy is added.

tests/dat_io_c.py independently compares the compiled C core/adapter with original
ReadDatBytes, using the same declared services. All 45 cases compare complete
memory/registers, defined final flags and service traces. They execute all 106
instruction sites and twelve edges. Compiled mutations that retain incoming ES
on cache copies, discard error AX during cache fill, or restore SI/DI from host
temporaries are each detected. The C routine is TESTED only in this stated domain;
the contract-only suite remains separately accounted.

DecodeDatSection now calls these services and cores directly; see dat-section.md.
Full DOS/FCB platform implementation, cache lookup/allocation, the fatal cleanup
continuation and wider incoming aliases remain open. The strict static extractor's bounds and checksum exceptions
must not replace the original wrapper's unchecked behavior.
