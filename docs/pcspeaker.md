# Verified PC-speaker C cores

This cluster translates three closed helpers in the independently verified
MAIN.DAT section-5 component. Addresses below are relative to its loaded segment.

| Helper | Original range | Code bytes | C core |
|---|---|---:|---|
| LoadEffect | 01B0..01D3 | 36 | lmn_pc_sound_effect_core |
| Tick | 01D4..024E | 123 | lmn_pc_sound_tick_core |
| Stop | 024F..0254 | 6 | lmn_pc_sound_stop_core |

The 165 original bytes contain 60 instruction sites and 17 static branch edges.
All are covered by tests/pcspeaker.py. c/pcspeaker.c operates on the original live
data segment in the shared 1 MiB memory store. It does not create a parallel sound
state struct. LmnPort8 declares byte-port read/write services; register and near-RET
effects are verified through separate adapters. c/pcspeaker_sym.h is generated
from the component's symbol ledger, including its field names and record stride.

LoadEffect uses signed AL*15 followed by a 16-bit unsigned address addition. It
copies each byte directly from live source memory to offsets 000A..0018, sets the
countdown pair from word 0017, and changes the active byte from 0 to FF. Negative
or oversized selectors are not clamped. Source offsets wrap at 16 bits, and sources
may overlap live header fields or include code bytes. The final carry comes from
the initial address addition; subsequent INC/DEC instructions preserve it. The
remaining arithmetic flags reflect DEC 0 -> FF.

Tick advances the noise phase, duration, two countdowns, period and rotating
modulation/gate patterns exactly as the original. If the active byte is zero or
duration expires, the selected divisor is 2. Otherwise the pattern selects the
current period or that same divisor. PIT writes to ports 43/42 occur only when the
divisor differs from the stored word at 001A. The final IN/OR/OUT on port 61 always
sets its low two bits, including the inactive path. Stop only clears the active
byte; it does not directly disable the speaker. These original behaviors remain.

The bounded suite freshly decodes the pinned source section and relocates the main
image into constructed memory at three loads. It enters only the original helper,
with a near-return fixture and declared byte-port services. Comparisons include
the full 1 MiB memory, all modeled registers, defined flags and the complete ordered
port trace. There are 335 cases: every AL byte value, data/header/code-source overlap,
different DS, odd stack words across FFFF, countdown/period wrap, both rotations,
both PIT-update paths and seeded poison. Three separately compiled mutants must
fail: unsigned effect selection, wrong active-byte initialization and altered
speaker gate output. All three are detected by the oracle.

AF is excluded only for Tick's final OR and Stop's XOR, where it is architecturally
undefined. LoadEffect compares all modeled arithmetic flags. The declared domain
has quiescent interrupts and mapped memory; data writes do not alias the executing
helper or its return frame. The helper tests do not execute the IRQ dispatcher,
unexplained component tail or original game startup.

metadata/pcspeaker-producers.json records the ten recovered main INT60 sites. Each
has an immediately preceding MOV AX: commands are 00/01/03 and effect IDs are
02/0C/13. The raw canonical CD60 candidates match those sites. This is producer
evidence for recovered code, not a proof against all mutations, external callers
or additional transformed code.

## Live bus and dispatcher contracts

The effect and stop helpers now also expose optional `LmnRasterBus` cores and
near-call adapters. The existing APIs use the same implementations with a NULL
bus. Every data/stack access carries its instruction-entry flags; words access
the low byte followed by the next physical byte, with 20-bit wrap. The effect
copy uses explicit INC, so DF does not reverse it. Its reload word is read after
the copy, DEC rereads the live active byte, and the adapter reads RET after the
body. Device providers can therefore change the values used by these operations.
The earlier RAM-only fixtures describe the narrower quiescent domain in which
the cleared active byte stays zero until DEC.

`c/pcspeaker_dispatch.c` implements the 46-byte interrupt entry at 0182..01AF.
STI precedes six live register saves and PUSH CS / POP DS. Original AH 00..10
indexes a live near-pointer table at 001E without a bounds correction. Only its
first five words are identified; later selectors read effect-record bytes.
AH 11..1F reads header offsets 01..0F, and AH 20..FF writes offsets 00..DF. Both
retain the residual AH from SUB AH,10. Raw setters can overwrite the table.

The focused bus suite passes 274 fixtures at both core/adapter boundaries,
covering 42 helper bytes, 18 sites, both LOOP edges, 20,392 byte events and five
completed mutants. Its ordinary-RAM cases also check an independent sequential
copy/reload calculation. The dispatcher suite passes 282 fixtures at both
boundaries: all 256 AH values plus recovered producer values, live temporary DS,
all six saved-register providers, mutable tables, actual RET/IRET words, real
word-boundary wraps and a VGA stack. It covers 46 new bytes/29 sites/six branch
edges, 18 integrated child sites and 18,270 events, with eight completed mutants.
Child bytes overlap the previously translated helpers and are not added again.
The original 335-case RAM/port suite remains a separate regression gate. All
native workers have process/tree commit limits, deadlines, callback budgets and
a temporary-DLL lifecycle. Budget or execution failures do not earn mutant credit.

The native dispatcher composes LoadEffect and Stop only when the actual table
word names their exact entries. Tick and other targets stop with the built CALL
frame and actual CS:IP as explicit `UNTRANSLATED_CHILD` exits. Tick's existing
RAM/port proof does not establish the instruction-phase bus contract needed here.
Undefined AF after XOR/SHL is excluded from flag comparisons; fixture providers
do not branch on undefined flag bits. A changed child RET stops before the
restore tail. Normal restores and IRET read
the live stack words, with fixed FLAGS bits normalized by the register adapter.
The core boundary is immediately before IRET at 01A0.

CALL reads its target before pushing 019A. An important alias fixture places
CS=DS=SS=01B0 and entry SP=0032: PUSH CS supplies the table word at 0024, then
CALL overwrites that word with 019A after capturing target 01B0. Treating the
stack or table as a separate state copy would change the executed child.

The dispatcher and bus suites use constructed states and quiescent asynchronous
interrupts. Their acceptance is scoped to the declared entry/body/exit contracts;
it does not establish hardware bus timing or IRQ scheduling. INT60 frame/vector
transport must still connect this entry to the main 2EC0 caller. Mutable unknown
targets, 162 unresolved payload bytes, broader sound playback and timing remain
open. Helper or dispatcher acceptance does not establish whole-game readiness.
