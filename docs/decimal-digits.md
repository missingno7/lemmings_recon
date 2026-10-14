# Decimal filename helper in native C

WriteDecimalByteDigits occupies CS:4BC2..4BE6, 37 instruction bytes. The core in
c/decimal_digits.c takes the live memory, DS segment, SI cursor, unsigned AL value
and incoming flags. It writes three ASCII digits for 000..255 directly into
canonical memory. Incoming AH is discarded. AX returns tens ASCII in AH and
units ASCII in AL; SI advances two, despite writing three bytes. Other registers
and segments are preserved. Writes advance forward even when DF is set.

The original repeated-subtraction loops are expressed as decimal quotient and
remainder operations. Final arithmetic flags come from ADD AL,30h: only parity
varies among the possible result characters; CF/AF/OF/SF/ZF are clear. Control
flags remain live. Cursor arithmetic wraps at 16 bits and physical byte addresses
wrap at 20 bits. The comparison adapter reads the active RET word after the
writes, retaining return-word corruption through a DS/SS alias. Word accesses
are physically contiguous, including a word starting at offset FFFF.

tests/decimal_digits_c.py compares full 1 MiB memory, all registers and defined
flags against bounded execution of the original 19 instructions. Its 270 cases
cover all 256 AL values, poisoned AH, DF/control flags, cursor and stack wrap,
physical wrap and three controlled active-return aliases. All four branch edges
execute. Three compiled mutations change the number, cursor or DF direction;
all are detected. GCC compiles the core as C11 with warnings treated as errors.

The independent 260-case original-only contract suite remains in
tests/decimal_digits.py. It does not contribute to C coverage. The connected
197D caller invokes the core directly, with its original live call-frame writes;
see resource-select.md. Broader asynchronous interrupts and instruction-byte
self modification remain outside the bounded native domain.
