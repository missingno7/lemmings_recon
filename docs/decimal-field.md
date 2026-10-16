# Variable-width byte fields

`WriteDecimalByteField` at4B68 owns86 known bytes/40 instruction sites through
its RET at4BBD. `WriteDecimalBytePair` at4BBE owns an additional4 bytes/two
sites and jumps into the4B91 suffix. Their physical union is90 bytes/42 sites;
the pair reaches49 bytes/24 sites including shared code. Neither entry calls
another routine or changes DS/ES/SS. The adjacent4B5C percent wrapper and
fixed three-digit4BC2 helper have separate contracts and are not included.

The full entry first writes three spaces at DS:SI, SI+1 and SI+2, with16-bit
offset wrapping. It discards incoming AH, clears only BL, and computes hundreds
and tens with unsigned repeated subtraction. A nonzero hundreds digit is
written at the current SI and advances SI. The shared suffix writes two spaces
at the current SI and SI+1 before computing tens. Tens are emitted when nonzero
or when a hundreds prefix was emitted; the units digit is always emitted.
Thus decimal0 writes`0  `,10 writes`10 ` and100 writes`100`. Digits are
left-aligned with trailing spaces. The pair entry clears BL before entering
the suffix; it does not reduce AL modulo100. Values100..255 can therefore
emit a nondecimal tens character:255 writes`I5`.

AX returns ASCII tens in AH, or a space when tens are omitted, and ASCII units
in AL. BX preserves BH; BL counts emitted prefix characters, excluding units.
SI advances past the units digit by one to three bytes for the full entry and
one to two bytes for the pair. All increments are explicit forward INC SI,
independent of DF. The remaining registers and segment values are preserved.

Space and digit writes remain distinct, ordered accesses to canonical memory,
including when the same address is written repeatedly. A VGA/provider bus can
observe every access and its instruction-entry defined flags. XOR/AND leave
AF undefined. The units ADD AL,30 defines arithmetic flags before its store;
the final INC SI then replaces PF/AF/ZF/SF/OF according to16-bit SI while
preserving CF and the control flags. This differs from4BC2, which ends after
its units store without that final cursor increment.

The logical C boundary returns before the shared RET. The register adapter
then reads the actual post-write SS:SP return word, using two consecutive
physical bytes with20-bit wrapping, and advances SP by two with16-bit wrapping.
DS/SS aliases may alter either byte; no prefetched return or isolated output
buffer is valid. Code modification and live IRQ delivery remain outside these
constructed routine checks.

Candidate selection calls the full entry at3DF3 with return3DF6, AL equal to
live candidate count and SI=208B. It subsequently reloads its selected pointer
and copies a live seven-byte template. The formatter has other static callers;
its verification does not establish their complete contracts.

## Scoped native acceptance

`tests/decimal_field.py` passes1,064 boundary cases:1,024 cover every AL value
at both entries and both core/adapter boundaries;40 cover aliases, wrapping,
DF/flags, planar writes and null buses. All90 known bytes/42 sites and all13
jump outcomes are represented, including the pair entry JMP and shared tails.
Seven compiled mutations complete and differ in output, write order, cursor,
BH, flags or actual return behavior. Original-only independent format, flag,
whole-memory and plane expectations pass before native comparisons.

The suite owns its DLL directory through an outer bounded worker wrapper;
limits are240 seconds,384 MiB process/640 MiB Windows tree commit,128 original
instructions and32 native callback events per call. Callback exceptions or
budget exhaustion terminate the worker and cannot count as mutant detection.
The retained report records exact input hashes. This scope establishes these
two routines; it is not aggregate C or complete caller/game acceptance.
