# Text records at 4D4D

DrawTextStream occupies 43 bytes/26 instruction sites at 4D4D..4D77. It reads
each byte through live DS:SI with LODSB and advances SI according to incoming
DF, wrapping SI to 16 bits. The header is a one-based column byte, row byte and
style byte. A zero column terminates the whole stream; zero style selects BP=2,
and every nonzero style selects BP=0. CL becomes column-1 and CH becomes row.

Text ends at carriage return 0D, which restarts header reading. Zero inside a
text run is passed to DrawTextGlyph and does not terminate the stream. Each
glyph receives the current CX/BP. The caller saves CX, BX and SI in that order,
then pushes 4D70 for the near call. The glyph core composes the renderer directly.
The returned CPU state, including DS/ES, feeds the continuation before the
subsequent saved-register pops; the stream never caches its original DS. The actual glyph near-return word is consumed first. Any changed target
stops before the saved-register pops. A normal return executes live POP SI,
POP BX and POP CX, followed by byte INC CL. CH does not receive carry from CL,
and INC preserves the returned CF. READY leaves RET at 4D77 for the adapter.

The stream has no intrinsic length limit or added gameplay budget. Unterminated
or aliased streams retain original behavior. Differential workers have finite
instruction/access/commit/time budgets, and an unterminated space-only probe
must terminate the disposable native worker with exit 86. A budget or callback
failure cannot count as a detected mutant. Temporary DLLs belong to the parent.

tests/text_stream.py compares all CPU fields, defined flags at each bus phase,
whole canonical RAM, ordered byte accesses/ports and VGA state. Independent
record parsing checks the glyph requests; ordinary draws also receive an
independent per-glyph whole-plane footprint check. The fixtures include all
256 style bytes, forward/backward reads, NUL versus CR, byte column wrap,
cursor/physical wrap, live DS and dirty-map aliases, changed glyph/renderer
returns, null-bus RAM repeats and six pinned static text record slices.
It uses the existing original RETF observation without opcode/target patching.
The tests do not settle hardware stack-limit faults, IRQ timing, arbitrary
device-backed stacks, complete terrain acceptance or the full retry UI.

The separate original-only and native gates pass 295 fixtures at both the
logical-core and register-adapter boundaries. All 26 caller sites and eight
caller branch edges execute; the integrated executed-site union is 455. The
caller contributes only its 43 bytes; glyph/renderer bytes already belong to
their existing translations. Null-bus comparisons repeat the eligible RAM-only
fixtures. Five completed mutants distinguish embedded NUL, DF, live saved SI,
changed glyph near return and byte-only column increment. A guard exhaustion
is never a mutant hit. Ordinary glyphs preserve a distinct incoming DS; later
stream reads still use the actual returned DS rather than a cached entry frame.
