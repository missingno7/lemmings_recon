# Headless native platform

`platform_host.c` binds the existing `LmnGameLoopServices` graph. The release
executable uses C11, the native pinned PKLITE decoder, and ordinary read-only C
file I/O. It has no Python, Unicorn, SDL, original-instruction execution or legacy
interpreter dependency. `tools/hostbuild.py` is a build convenience, using the
existing compiler source closures and bounded compiler launcher.

```
.venv/Scripts/python.exe tools/hostbuild.py
# Create the output directory first.
build/lemmings-headless.exe assets host/smoke.script 20 build/host-smoke
# Or build, run with external limits, and check the three frames and cadence:
.venv/Scripts/python.exe tools/host_smoke.py
```

Runner arguments are assets directory, script, maximum session-frame count,
existing output directory, optional stop-poll hex address, and optional CSV of
additional session-frame captures (`0 5,10,20` for no stop-poll and those frames).
Script lines are `MILLISECONDS mouse X Y BUTTONS` or
`MILLISECONDS key DECIMAL_SET1_SCAN`; comments start with `#`. Events must be in
nondecreasing time order. Make and break codes are separate events. At most8192
events are retained. Captures are `menu.ppm`, `briefing.ppm`, `gameplay.ppm` (at
frame16 or the requested limit if smaller), and requested `frame-NNNNNN.ppm`.
`frames.csv` records each0105 observation, PIT-clock time, IP and a specified
FNV-1a64 hash of RAM, four planes, DAC and CRTC bytes. Capture failure fails the
runner. A frame/poll stop is terminal for this invocation, not a coroutine save.
Run this executable under `run_bounded` for external time/process-commit limits.

## State construction and readiness

CONDITIONAL READY: the existing game-loop poll/provider domain, load1010 and a
constructed post-startup handoff at43F2. The unresolved startup/protection paths
are not executed or replaced with guessed instruction semantics. Scratch RAM and
registers without a producer are deterministically zero, rather than fixture
poison; no runtime dump is loaded. DS is relocated load+09A9, independently of
SS. The selected stack is9000:8000, the same isolated constructed stack used in
`tests/game_loop.py`, not a claim about startup's final SS:SP.

`lmn_host_post_startup` constructs the fixture's documented producer fields:

* Native PKLITE static image plus all returned relocation words, in stream order
  (`docs/executable.md`). The decoder independently checks the pinned identity.
* DS:0000..2011 clear from0027..0031, configuration/blanking gates, keyboard
  defaults preserved at201F/202E (image BAAF/BABE), code83BE from00B4, canonical
  IVT09 from1562 and the menu IVT08 target from5028. Opaque external services use
  declared B000 entries; IRQ delivery always reads live IVT memory.
* VGA CRTC base from0512 and selected BIOS geometry, input mode0 from static data,
  saved timer chain from005D..0066, nonzero calibrated1FC9, disabled DAT cache
  and enabled retry from00D8..00DB. The reload4567 is a chosen calibrated-machine
  input, not a measurement of modern wall time.
* MAIN.DAT sections3/4 decoded by the maintained native DAT decoder into the same
  isolated UI fixture banks4000/4F21 used by `tests/main_menu.py`. Static palettes
  are preserved: the fixture's constant palette poison is not a startup producer.

The runner then calls `lmn_host_prepare_resources`: it chooses one conventional
5571-paragraph allocation at3000 and publishes the literal1007..1043 selector
arithmetic (`docs/main-resource-sections.md`). This replaces the fixture's
isolated arenas with one consistent lifetime: graphics3000, sprites4000,
generated graphics5D0C, patterns5E72, glyphs5F02, UI5F7E/6E9F, input7971, end8571.
It composes the maintained58D2 MAIN.DAT loader and all its bank/plane/glyph
producers in C. The fixture entry and complete resource preparation are separate
APIs so the differential journey can retain its original seeded RAM unchanged.
No bootstrap generator overwrites maintained source.

## Devices and cadence

One1MiB canonical memory owns RAM, IVT, stack, records and self modifications.
VGA owns four64KiB planes and four latches; aperture RAM records CPU-visible bus
bytes. Byte and word register I/O share sequencer/GC/CRTC state. Unchained A000
read modes0/1 and write modes0..3 implement map mask, set/reset, rotation, logical
function, read map, compare/care and bit mask. DAC components are six bits with
independent read/write cursors and rollover. Mode0D uses the BIOS200-line
attribute map0..7/16..23; mode10 uses the350-line EGA map including14/38..3F.
PPM scans the current CRTC start and offset, attribute map, PEL mask and DAC.
It is an instantaneous page/palette capture, not a retained raster-color history.

The virtual clock is in1193182Hz PIT units. Its stated display machine has
17044-unit frames,54-unit horizontal lines and a10% vertical retrace interval.
IN3DA advances8 units and reports horizontal display disable independently of
vertical retrace. Ordinary foreground polls advance128 units in automatic mode;
no IRQ is delivered inside a child or ISR. Status and foreground time advance the
same clock. Channel0 implements reload low/high programming and count latching;
PIC masking, in-service state and EOI gate delivery. Pending IRQs coalesce as a
PIC request; deferred keys remain queued.

For200E!=FF in mode0D, a reload expires just before the next retrace, and the
game IRQ waits through retrace before re-arming. The host preserves that actual
guest re-arm; it does not add another full frame after the handler returns.
Menu and FF-mode PIT requests retain their free-running divisor phase.
For FF the deadline uses the programmed PIT divisor (normally4000). The native
timer itself owns the four-IRQ BIOS chain and signed counter/tick gate after five
IRQs; the host never synthesizes those game-state writes. The saved BIOS provider
increments0040:006C and acknowledges the PIC. Scripted verification disables the
automatic scheduler and submits ordered IRQ08/09 events at explicit virtual times.

INT33 implements reset/show/hide/query/position/ranges and callback disable.
INT10 implements the reached mode/page and adapter-identification requests.
INT1A implements tick get/set. INT21 supports read-only open/attributes/read/close,
the reached FCB size query for the current file, get/set vector, bounded arena
allocation/LIFO release/resize and headless console/termination. Basenames are
restricted to one component; no create/write service exists. The file overlay API
is a borrowed read-only fixture input, used for the existing zero-minute second
level case, never a patch to live game state or an asset file.

## Unsupported and verification limits

INT60/61 are explicitly muted sinks: requests are counted, returned CPU state is
preserved, and actual AdLib/Tandy/PC-speaker command semantics and audio are
unsupported. A game-installed vector that does not match a bound provider stops;
the host does not silently redirect it. Other video modes, chain4/odd-even memory,
arbitrary BIOS/DOS calls, joystick ports, asynchronous mouse callbacks, nested
IRQs, instruction-boundary preemption, cycle-exact timing and full native startup
remain unsupported. The arena allocator is this constructed machine, not a full
DOS MCB/fragmentation implementation. PPM snapshots do not reproduce mid-screen
palette changes. These limitations do not classify unresolved code as dead.

`tools/difftest.py host_vga host_journey` runs bounded workers with temporary DLL
directories under build and cleanup after failure. `host_vga` compares generated
device traffic with `tests/minimap_vga.py`, known DAC/CRTC/clock/service vectors,
the fixture constructor and independently recorded sprite-bank output hashes.
`host_journey` reuses `game_loop.setup`, `Access.script`, `Reference` and the shared
original instruction engine; only its platform provider profile changes to these
register devices and DOS/BIOS effects. It compares every loop boundary and poll,
including canonical RAM, defined CPU state, planes/latches/registers, DAC and CRTC.
It preserves the scripted cheat/next, time-up/retry and menu-return journey. Its
report is scoped to that schedule, not equivalence to arbitrary hardware timing.
The host journey records checkpoint state rather than ordered C bus traffic;
empty trace projections are explicit on both sides of the shared comparator.
