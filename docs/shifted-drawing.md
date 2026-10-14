# Shifted drawing frontier

The aligned bodies are native; the six shifted bodies remain untranslated.
The fresh `DrawPlanarBitmap --tree` and `--bottom-up` views retain the complete
8822 entry as UNTRANSLATED. Calls to clipping/dirty-cell helpers do not prove
the remaining drawing contracts. This review is static evidence, not C or
execution coverage.

The two shifted set/reset effects form the smallest next independent cluster.
The current analysis finds no calls or outgoing direct edges inside either
body and only the following incoming edges. Indirect and modified-code incoming
states remain unproven.

| Body | Inclusive bytes | Decoded sites | Discovered incoming edge | SHA256 |
|---|---:|---:|---|---|
| `PlanarShiftedMasked20Body` | 8FF7..909B, 165 | 84 | 8902 -> 8FF7 | `1be10dcca6b33ee3819d774b209fa4e18e4c760c9c93b9c884b67ec1e0a3c41b` |
| `PlanarShiftedMasked40Body` | 909C..913F, 164 | 84 | 890B -> 909C | `3bf36e4682b479a6842d87bd055ec981156ac0874b944dceba05f2111a065577` |

All bytes in these two ranges decode, including their four known NOPs each.
The core boundaries would end after POP DS at 909A/913E; RETF at 909B/913F
belongs to an adapter. Those boundaries have not yet been verified natively.

Both bodies first decrement incoming DS:6704, then push incoming DS and read
the graphics-source segment through DS:1FE4. ES becomes the relocated game
segment. VGA setup selects all planes, write mode zero and replace logic.
Set/reset is F for 20 and zero for 40; enable bits are BP's high-byte low nibble.
SI starts at BX. Each row uses live SS saves of DS, ES, CX, DI and advanced SI.

REP MOVSB copies CL mask bytes through incoming DF into ES:6748; STOSB writes
a zero sentinel immediately after the copy in that same direction. PUSH ES /
POP DS then makes the scratch segment live DS, while ES becomes A000. BX starts
at 6748, independently of DF. The unchecked byte at DS:A948 supplies the shift
count. SHR on the first scratch byte followed by RCR over subsequent bytes
preserves its carry through INC BX and LOOP. Saved BX/CX restore between shifts.
No corrected width, buffer extent or validated shift domain may be invented.

XOR CH,CH and INC CL establish the drawing LOOP count. Each mask byte increments
BX forward, programs the bit-mask mirror, and performs a CLI/latch-read/FF
STOSB/STI cycle; DI alone follows DF. POP SI recovers the advanced mask-source
cursor. Both shifted variants add live DS:6702 to SI and DS:6704 to DI before
restoring CX, ES and DS and decrementing CH. This differs from the aligned
20/40 row-cursor asymmetry and must be translated separately.

Before C promotion, verify zero CL/CH and shift-count behavior, CF/OF definedness
for SHR/RCR, forward carry propagation under DF, scratch/source overlap, physical
and SP wrap, live saved DS/ES/cursors/counts, and SS aliases of source/stride/shift
fields. For CL=0, REP copies no bytes but the subsequent RCR LOOP underflows;
for CL=FF, INC CL wraps the drawing count to zero. A zero shift byte wraps the
outer decrement loop. These are unchecked original paths, not validated caller
domains. Scratch stores may change live fields when the constructed ranges
overlap. The exact valid producer/buffer domain and asynchronous IRQ/device
ownership remain open. Use the bounded worker limits for every native case and
mutant, and treat any exhausted guard as a failed check.
