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

The component's interrupt dispatcher remains UNTRANSLATED. Its mutable pointer
table, zero targets, out-of-table commands and 162 unresolved payload bytes still
need closure. AdLib/Tandy translation is also open. TESTED helper status does not
claim completion of the sound subsystem or whole game.
