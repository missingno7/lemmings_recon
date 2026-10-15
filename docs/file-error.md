# File error printing and cleanup tail

`DatFileErrorTransfer` occupies `1949..197C`: 52 decoded bytes and 25 sites.
It is an error continuation, entered with the failing caller's existing saved
frame and a message offset in DX. It does not return to that caller.

The initial PUSH DX happens before loading main DS. `194B` is the relocated
immediate of MOV DX,09A9: at load 1010 its value is19B9. The core receives this
loaded segment explicitly; the register adapter reads the intact instruction
operand without adding a CPU data-bus event. It then pushes the real1952
continuation, calls the video logical core, propagates every returned field,
and consumes the actual near return. A changed video return stops before its
target executes. Otherwise POP DX uses the live returned stack; it can select
a different message pointer from the value pushed on entry.

DOS09 at1955 uses live DS:DX and preserves AL while loading AH. The following
space output changes AH and DL only; DH and other fields remain provider-owned.
Only after that returning DOS02 service does the code read the filename pointer
from live DS:2528 (`LastResourceFilenameOffset`). The loop reads a byte through
current DS:BX, ANDs DL with itself, tests zero, increments BX with16-bit wrap,
then invokes DOS02 with AH02. The provider may change DS and BX before the
next byte. INC preserves CF and defines AF; the zero-ending path retains the
AND's undefined AF until the CR provider returns. CR and LF each carry all
state from the preceding service.

The197A jump invokes the already tested04EA cleanup suffix directly. It does
not push another call frame. Keyboard restoration, live DOS exit-message output
and terminal DOS4C therefore retain the original error caller's stack residue.
Missing services stop at their actual INT boundary. Termination has no returned
CPU state, no outer RET and no execution of04F9.

`c/file_error.c,h` use direct logical cores and canonical memory. Every CPU
data/stack byte uses the optional raster bus in original order. Word high bytes
use physical+1 with20-bit wrap; SP and the filename BX wrap at16 bits separately.
No string copy or C length clamp is added. Arbitrary provider/alias states can
make the original filename walk nonterminating; finite test fixtures and worker
guards do not alter the native game routine.

`tests/file_error.py` compares an independent logical printer model and the
cleanup suffix model against the complete original instruction path before
compiling C. It checks all256 possible first filename bytes, empty and longer
names, returned DS/BX redirects, post-space pointer reads, saved-message changes,
changed video returns, A20/SP/BX wrap, missing services and VGA-backed page,
stack, filename and message accesses. DOS fixtures return all twelve logical
fields and may alter canonical memory. Their output bytes are checked as
provider evidence, not a claim to implement DOS console processing.

The final native matrix has301 adapter and301 auxiliary logical-core cases.
Four VGA profiles retain separate plane/latch checks; the other297 cases also
repeat each native boundary with a NULL bus. The301 original/model executions
provide the expected states for both native ABIs. All25 caller and45 integrated
sites, two conditional outcomes and two unconditional jump edges are required.

The core and adapter compare complete memory, all returned CPU fields, defined
flags, ordered data events, service inputs/outputs, printed bytes and VGA state.
The integrated domain unions the52 caller bytes with46 already translated
video/keyboard/cleanup-suffix bytes:98 bytes and45 sites. Two conditional
outcomes and two unconditional jump edges remain separate from site accounting.

Four compiled mutants substitute entry DX for the live POP, cache the filename
pointer before space output, discard returned DS/BX between filename characters,
or add a spurious CALL frame to the cleanup tail. Only completed mismatches
count. Workers have120 seconds and Windows process/tree commit ceilings of
384/640 MiB. Original execution caps at512 instructions, traces at512 events,
service calls at64 and declared DOS09 strings at64 bytes. Callback budgets hard
exit86; callback errors exit87. Compiler runs have60 seconds/256 MiB. The parent
removes temporary DLL directories after the worker is terminal.

These contracts assume intact decoded code, same-CS service resumes, TF clear
and no delivered asynchronous IRQs. Actual BIOS/DOS/device implementation
remains open. The1916 raw fatal path is now separately connected in resource-raw-full.md.
Other upper resource fatal connections remain open. Byte classification
does not change; global C coverage still requires fresh complete terrain and
other affected reports.
