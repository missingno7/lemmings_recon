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
it does not establish hardware bus timing or IRQ scheduling. Mutable unknown
targets, 162 unresolved payload bytes, broader sound playback and timing remain
open. Helper or dispatcher acceptance does not establish whole-game readiness.

## INT60 frame/vector connection

`c/pcspeaker_interrupt.c` composes the dispatcher with the declared real-mode INT
boundary also used for INT61 (see entity-countdown.md). It saves entry FLAGS,
clears IF/TF for subsequent operations, pushes the interrupted CS and supplied
return IP, then reads the live IVT CS word at 0182 followed by IP at 0180. Frame
stores can alias the vector, so the lookup is not cached before the saves. Words
use the next physical byte and 20-bit wrap. The original-code harness supplies
this architecture boundary while executing the identified driver independently;
it does not claim CPU microcode or physical bus timing verification.

An exact bound segment and offset0182 enter the native dispatcher. An absent
binding or other vector returns its actual CS:IP and built stack frame as an
explicit unbound exit. The dispatcher may restore any of its six saved registers
from changed stack words, so the connector carries every returned register.
Untranslated child and changed near-return exits retain their actual states.
A completed IRET is checked against the interrupted CS and supplied return IP;
a changed destination is reported without resuming the caller. The binding
requires the pinned instruction domain; code-mutating stack/data aliases stay
outside these bodies rather than being repaired or interpreted.

The focused transport suite passes25 fixtures with1,234 ordered byte events,
29 dispatcher sites, six dispatcher edges and18 integrated child sites. Six
compiled mutants complete with mismatches. Cases include all three recovered
effect IDs, Stop/Tick/unknown seams, changed vectors after frame writes, the
frame overwriting its own IVT entry, changed child/interrupt returns, all six
saved-register values, real word wraps and a VGA stack with map mask zero.
The latter leaves preseeded frame words intact despite the attempted pushes.
This connector adds no original ASM bytes beyond the already translated driver.

Constructed entry FLAGS obey `(raw & 7FD5h) | 2`; the parent also clears TF to
keep its asynchronous debug-handler seam quiescent. This constrains entry CPU
state, not stack data: saved IRET words such as FFFF remain unrestricted and
completed transport IRET cases compare all16 restored flag bits. With invalid
reserved bits injected through `reg_write`, Unicorn keeps bits3/5/15 sticky
across IRET: initial002A with saved0006 returns002E, whereas admissible initial0002
with savedFFFF returns7FD7 and saved002A returns0002. A two-interrupt poison case
exposed that artifact by saving FLAGS again after IRET. No memory/event byte
mask was added; ordinary full canonical-memory comparison remains in force.
