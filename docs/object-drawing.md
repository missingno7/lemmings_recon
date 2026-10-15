# Native object-drawing suffix

`c/object_drawing.c` composes the original `397D..39CD` suffix directly with
the native `8822` planar renderer, using the canonical RAM image and one raster
bus. The suffix contains 81 original bytes and 33 instruction sites; its byte
SHA-256 is `3a4c387885edd2da6c45f8f1f8e41f5ac348ddb2da63c1f8eec9c62eff8dd989`.
The preceding `397A` record-copy CALL belongs to the enclosing redraw caller.
This candidate is verified separately and is not yet added to ledger C coverage.
The static contract remains in [object-drawing-frontier.md](object-drawing-frontier.md).

## State and memory contract

The core initializes SI=`17CB`, DI=`0FEB`, CX=32 and publishes the live
DS:`1FF0` graphics-segment word at DS:`1FE4`. Zero X skips a definition and
leaves its working slot stale. Each active definition saves CX, DI and SI on
live SS before reading its remaining big-endian fields. The renderer receives:

| Value | Original source |
|---|---|
| X / Y | Separate big-endian definition byte loads at `+0/+1`, `+2/+3` |
| Control | Big-endian definition `+6/+7`, AND `FFFE` |
| Width / height | Working-slot bytes `+4/+5`; DX high byte is cleared, CH=4 |
| Source SI | Working-slot little-endian word `+17` |
| Mask DI | Working-slot little-endian word `+8`, plus source SI modulo 65536 |

The far call pushes actual CS followed by `39C2`. The core consumes both live
return words and stops before a changed target. On normal return, live POP SI,
DI and CX control subsequent iterations; there is no substituted 32-pass cap.
DS and ES returned by the child remain live. The final flags come from ADD
SI,`1C`; LOOP and RET preserve them. Separate byte operands wrap their effective
offsets at 16 bits; a word's high byte uses physical address plus one with
20-bit wrap. The adapter alone consumes the suffix's own near RET at `39CD`.

Clearing control bit zero selects the unshifted bodies even for unaligned X.
Widths below eight produce zero byte count; the original word LOOP performs
65,536 iterations per row. The native implementation retains this behavior.
Missing or incomplete byte-port callbacks stop at `969C` before executing that
body. IRQ delivery, timing, arbitrary providers and modified instruction bytes
remain outside the bounded test domain.

## Differential evidence

`tests/object_drawing.py` passes 131 adapter comparisons, 51 additional core
boundary probes, 33 caller / 886 integrated instruction sites and 129 observed
edges. All six aligned body families execute. All 80 pinned LEVEL/GROUND pairs
are represented; fixtures independently model the earlier forward `378A` copy
before entering `397D`. This suite does not execute that copy or all of `394F`.

Checks compare full RAM, all registers, defined flags, ordered byte/port access,
VGA registers/latches/planes and streamed device order. Ordinary cases also
independently check renderer inputs and whole-plane output. Constructed cases
include both DF values, offset/physical wraps, distinct DS, dirty-map returns
and absent/partial providers. Concrete alias witnesses include:

- SS:`000E` VGA-mirror writes change a saved DS to `FF08`; later definitions
  must use that returned segment.
- A live far frame changes to `0000:0802`; another fixture returns CS=`0210`.
  Both stop before executing the changed target.
- SS=DS, SP=`66FA` lets source geometry overwrite saved CX with one and the
  outer near return with `0001`. Restored state, rather than cached loop locals,
  controls the remaining suffix.
- Dirty-map writes change an inner near return to `8801`.

Four compiled mutants are detected by completed behavioral mismatches: retaining
control bit zero, caching DS, hiding a changed far return, and caching saved
loop state. Resource exhaustion and oracle failures do not count as detections.

The parent owns a temporary DLL directory. The native worker has a 300-second
deadline, 512 MiB process / 768 MiB tree commit limits, at most two million bus
events, 1.2 million device events and three million original instructions per
case. Trace values/order stream into SHA-256; flag/mask storage is bounded.
Callback guard errors terminate the disposable worker. Inputs are hashed before
and after the suite; only its final report is acceptance evidence. Temporary
DLLs are removed after worker exit.
