# Level redraw composition

`c/level_redraw.c` translates the identified `394F..39CD` caller as a direct
composition of existing native cores. There are 50 decoded caller instruction
sites and 126 original instruction bytes. Stored UNKNOWN byte `395E` remains
outside the translation; neither this composition nor its tests classify it.
The ledger names the entry `RedrawLevel` and excludes `395E` from its C ranges.
Global coverage unions its overlapping suffix/terrain bytes and requires fresh
dependency and complete-stream acceptance reports.

## Canonical state and calls

The core carries transient logical register values and live DS/ES/CS/SS/SP over
one canonical physical-memory image. It creates no converted object records,
game-state copies or interpreter fallback. The sequence follows the original:

| Original point | Native composition and live continuation |
|---|---|
| `394F` CALL `368E` | Initialize/clear/layout; consume actual near return `3952` |
| `3952..3957` | Read AL from live DS:`0FE8`; AND AL,AL supplies branch flags |
| `3959` CALL `1A7B` | Special metadata/RLE/strip/DAT setup; consume actual `395C` |
| `395F..3979` | Normal packed terrain command loop; sentinel reaches `397A` |
| `397A` CALL `378A` | Bus-aware object graphics copy; consume actual `397D` |
| `397D..39CD` | Object loop and direct native `8822` drawing composition |

Both special and normal branches reach the record-copy CALL. Initializer and
renderer near/far return changes stop before their targets. The parent also
checks the real return words after special setup and copying. Its core leaves
the final `39CD` near RET unconsumed; only the register adapter reads it. DS
returned by terrain/special children controls subsequent definitions and slots.
Returned ES/CS, arithmetic flags, IF/DF and wrapped SP remain explicit.

See [level-drawing.md](level-drawing.md), [terrain-stream.md](terrain-stream.md),
[special-setup.md](special-setup.md), [object-graphics-bus.md](object-graphics-bus.md)
and [object-drawing.md](object-drawing.md) for inherited child obligations.
The wider `36B6` initialization caller is separate.

## Provider boundaries

A complete parent raster bus is required before executing `394F`: clear/layout
and drawing use it for ordinary memory, stack and VGA effects. Missing callbacks
return a typed service stop at `394F`, with no invented instruction effects.
On the special branch, missing DOS/DAT services stop before `1A7B` after its
`395C` return frame is pushed. The special-services object's raster pointer is
locally replaced by the exact parent bus, preserving one device provider even
when the nested pointer is NULL. The caller does not rewrite the service object.

The special child retains its existing ordinary-RAM input/heap/stack and intact
internal-return preconditions. Its direct RAM accesses remain direct; this
parent does not claim to make that child bus-aware or solve arbitrary aliases.
The DOS fixture supplies explicit register/flag/memory effects; native fatal
outcomes remain transfers to `1949` or `04D0` with their frames intact. The
independently tested retry UI, arbitrary providers, IRQ delivery, timing and
modified executing code remain outside this connected test domain.

Absent/incomplete byte-port providers stop at `969C` if that renderer is selected.
They do not silently call through a NULL host callback or change renderer choice.

## Verification procedure

The fresh differential passes 48 adapter cases and 48 core-boundary probes,
all 50 caller / 1,745 integrated instruction sites, 258 observed edges and
three compiled mutation witnesses. The mutations invert the selector, cache
DS across a terrain child, or hide the record-copy return change. No timeout,
access-budget failure or oracle failure is counted as a detected mutant.

Run `.venv\Scripts\python.exe tests/level_redraw.py`. Each comparison checks the
original identified instructions in constructed state without booting the game.
The matrix includes normal terrain/object paths, both DF values, stack
wraps, a distinct incoming DS, changed clear/layout/copy returns, a terrain
child returning DS=`0018`, service/byte-provider stops, special setup and both
fatal paths, ignored close carry and returned DF, and all four pinned
VGASPEC/VGAGR pairs. Every case checks the adapter and the core's pre-RET/stop
boundary independently.

Whole RAM, registers, defined flags, VGA state and device order are compared.
Parent and bus-aware children also compare ordered raster events and their
phase-defined flags. Special/DAT/RLE ordinary-RAM instruction events are outside
that bus comparison because their native cores access RAM directly; their
memory effects remain in the whole-RAM comparison, and declared DOS effects
have a separate service trace. Strip RET `8342` is consumed directly by the
special child; special RET `1B41` is consumed through this parent's raster bus.
This distinction follows the native API boundaries rather than hiding an
unexplained event difference.

The coordinator has 512 MiB process / 768 MiB tree commit limits. Cases run
serially in fresh 384 MiB workers with a 300-second deadline each, including
separate mutant witnesses. The entire coordinator also has a finite deadline.
Each case permits at most ten million identified original instructions, two
million bus events and 1.2 million device events. Compiler subprocesses have
their own 256 MiB / 60-second bound. Callback failures terminate the disposable
worker; timeout, guard and oracle failures cannot count as mutant detections.
The parent owns and removes temporary DLLs after worker exit. Acceptance requires
all cases, both core/adapter checks, all 50 caller sites, all three mutation
witnesses and unchanged input hashes. The original full LEVEL terrain-stream
acceptance campaign remains an additional gate; a small redraw matrix cannot
replace it.
