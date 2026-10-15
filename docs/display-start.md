# Display-start outputs and live origin swap

ProgramAlternateDisplayStart4C32 loadsBX fromDS:1F78 and enters the shared
ProgramDisplayStartFromValue4C36. CLI precedes the liveDS:1FDA word read.
Two wordOUTs use that one DX: AH=BH/AL=0C, thenAH=BL/INCAL=0D. OUT preserves
CPU state; its provider can mutate canonical memory or explicit device context.
BX and DX are not reloaded between outputs. INC defines all ordinary arithmetic
flags except preservedCF. STI is unconditional, even when incomingIF is clear.
The shared core stops before the actual nearRET at4C46.

SwapDrawingOriginsAndDisplay4C20 readsDrawingOrigin1F76 intoBX, pushes the
real4C27 continuation and calls the shared logical core. Missing output leaves
that child frame intact. A normal child consumes the then-live return word;
a changed word stops before any4C27 instruction. Otherwise MOVAX rereads1F76,
XCHG reads1F78 and writes the liveAX there, thenMOV stores the old1F78 at1F76.
Provider writes and SS aliases can therefore change the eventual origin swap.
The caller core stops before4C31, and only its boundary adapter consumes the
live outerRET. XCHG does not change flags. No copied page/origin state is stored.

The three entries cover39 unique bytes/17 instruction sites with no conditional
ASM branch. The4C36 suffix overlaps17 of the21 bytes from4C32 and is counted
once. Word CPU accesses use optional raster callbacks, low byte thenphysical+1
with20-bit wrap; SP wraps16 bits between words. A missing word-output provider
stops before4C3F withIF still clear. A bus with no read/write callbacks uses RAM
while retaining its output provider. The actual controller/timing and IRQ
ownership remain platform dependencies. Finite constructed provider effects,
sameCS/intactcode/TFclear and quiescentIRQ define the differential domain.

tests/display_start.py independently models the outputs, live swap and frames,
then compares original instructions and C at both core/adapter boundaries for
all three entries. It checks full RAM, twelve fields, flags, ordered byte/word
events, device state, overwritten child/outer returns, VGA origins/stack and
RAM fallback. Worker and callback guards fail verification rather than count
as mutation evidence. Four completed mutants must expose a real mismatch:
omittedSTI, reloadedBX, cached pre-provider origins and ignored changed return.
