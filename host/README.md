# Headless native platform

`platform_host.c` binds the existing `LmnGameLoopServices` graph. The release
executable uses C11, the native pinned PKLITE decoder, and ordinary read-only C
file I/O. It has no Python, Unicorn, SDL, original-instruction execution or legacy
interpreter dependency. `tools/hostbuild.py` is a build convenience, using the
existing compiler source closures and bounded compiler launcher.

```
.venv/Scripts/python.exe tools/hostbuild.py
# Create the output directory first.
build/lemmings-headless.exe assets host/smoke.script 20 build/host-smoke --media-probe=assume-original
# Or build, run with external limits, and check the three frames and cadence:
.venv/Scripts/python.exe tools/host_smoke.py
```

Runner arguments are assets directory, script, maximum session-frame count,
existing output directory, required media-policy flag, optional stop-poll hex address, and optional CSV of
additional session-frame captures (`0 5,10,20` for no stop-poll and those frames).
Script lines are `MILLISECONDS mouse X Y BUTTONS` or
`MILLISECONDS key DECIMAL_SET1_SCAN`; comments start with `#`. Events must be in
nondecreasing time order, relative to the completed startup handoff. Make and break codes are separate events. At most8192
events are retained. Captures are `menu.ppm`, `briefing.ppm`, `gameplay.ppm` (at
frame16 or the requested limit if smaller), and requested `frame-NNNNNN.ppm`.
`frames.csv` records each0105 observation, PIT-clock time, IP and a specified
FNV-1a64 hash of RAM, four planes, DAC and CRTC bytes. Capture failure fails the
runner. A frame/poll stop is terminal for this invocation, not a coroutine save.
Safety budgets scale with the requested frames: 100,000 + 2,000 per frame
foreground polls and 500M + 10M per frame bus accesses. A screen waiting for
input the script never supplies (for example the level result screen) ends
the run when the poll budget is exhausted.
Run this executable under `run_bounded` for external time/process-commit limits.

## Native startup and media policy

The host loads the pinned EXE through the native PKLITE decoder and all63
relocations. It establishes a DOS PSP at load-10h, a length-counted command line,
entry DS/ES=PSP, SS:SP=load+143E:4AF4, external IVT services and BIOS inputs.
`lmn_host_boot` then calls `lmn_startup_core` at0000 and admits the game loop only
at43F2. There is no post-startup constructor or repeated MAIN.DAT load.
The runner uses `/v /o /a` by default: VGA palette, preset options and the
original 01/01 PC-speaker fallback. `--sound=adlib` drops `/a`, so native
startup (054E) allocates the driver block, installs INT61 and loads adlib.dat;
`--audio` writes `OUTPUT_DIR/audio.wav`. Tandy and joystick profiles remain
bounded seams.

DOS owns the initial PSP allocation; native startup shrinks it with4A. Its48
request allocates one5571-paragraph block at3000, below9000: graphics3000,
sprites4000, generated graphics5D0C, patterns5E72, glyphs5F02, UI5F7E/6E9F,
input7971 and end8571. Native1007 publishes every selector. Native startup owns
clearing, configuration, vector saves, hooks, checksum patches, measured timer
reload, keyboard tables, DAT cache/retry and58D2 MAIN.DAT generation. The host
supplies the display/PIT inputs; it does not substitute a fixed reload.

The required flag is `--media-probe=assume-original`, `--media-probe=reject` or
`--media-probe=unsupported`; the API uses matching named enum policies. There is
no implicit admission policy. `assume-original` explicitly assumes recognized
original media; it supplies the first recognized AX/BX signature and preserved
register roles. `reject` supplies the original early BIOS-failure result and
runs native0EDF cleanup/DOS exit. `unsupported` stops at063E when a probe is
requested. No encoded INT1/INT3 body or physical-floppy test runs in the host.
For either completed outcome the native wrapper clears the selected512-byte
buffer, preserving the other buffer, decode seed, IVT/table and encoded code.
The semantic provider does not reproduce discarded internal probe stack residue;
raw probe parity belongs to the independently original-built test fixtures.

DOS AH1B declares a fixed-disk FAT ID F8. The native wrapper opens the supplied
`russell.dat`, reads one byte, increments/modulos the live counter, and performs
its original unchecked create/write/close requests. Files are read-only:3C/40
return access denied, and assets are never changed. The installed file's byte8
therefore becomes9 and skips the probe on the standard smoke run. A zero cycle
or open failure requests the explicitly selected media policy. Tests overlay a
borrowed one-byte9 counter to exercise PASS, rejection and unsupported policies
without changing an asset. The256-byte writer always uses live DS:252A.

This is a CONDITIONAL native startup/game-loop domain: normal disjoint RAM,
TF/DF clear, quiescent IRQs during startup, declared platform services and IRQs
at foreground polls afterward. No global UNKNOWN closure or unrestricted
raw-machine/protected-body equivalence is claimed.

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

INT33 implements reset/show/hide/query/position/ranges, mickey ratios and the
startup callback registration at CS:0F6F. That exact callback is a RETF with no
body effects; other callback targets are unsupported. Private-vector installation
remains native. Mouse/keyboard input and IRQs are delivered at declared polls.
INT10 implements the reached mode/page and adapter-identification requests.
INT1A implements tick get/set. INT21 supports read-only open/attributes/read/close,
the reached FCB size query for the current file, get/set vector, bounded arena
allocation/LIFO release/resize and headless console/termination. Basenames are
restricted to one component; create/write requests return access denied. The file overlay API
is a borrowed read-only fixture input, used for the existing zero-minute second
level case, never a patch to live game state or an asset file.

## Unsupported and verification limits

## SDL3 front end

`.venv/Scripts/python.exe tools/hostbuild.py --sdl` builds `build/lemmings.exe`
with the pinned SDL3 release (metadata/sdl3.json, fetched and hash-checked by
tools/fetch_sdl3.py into build/third_party; nothing downloaded is committed).
Run it from the repository root (`build\lemmings.exe`; `--assets DIR`,
`--sound=speaker`, `--media-probe=reject` are optional). The game runs exactly
as in the headless runner; host/sdl_main.c adds only devices at foreground
polls: the scanout is rendered once per emulated display period and scaled to
4:3, SDL scancodes become set-1 make/break bytes on IRQ09 (E0 prefix for
extended keys, SDL repeats as typematic makes), the mouse maps into the INT33
range the game set, PIT time is paced to the wall clock, and OPL output streams
to SDL audio. Alt+Enter toggles fullscreen; closing the window stops the game.
`--script/--frames/--log` drive it like the headless runner, and
`tools/host_smoke.py --sdl` checks under the offscreen/dummy drivers that it
reproduces the headless AdLib run frame for frame. Limits: the raster palette
split is presented with the DAC at present time, the PC speaker is silent and
the joystick is unbound.

## Sound

When the game installs INT61 at its driver allocation:0000 (DOS AH25 at 057B),
the host binds that live vector to `lmn_adlib_int61_core` (c/adlib_engine.c),
which runs the translated AdLib driver over the loaded driver bytes. The
provider checks the pinned AdLib dispatcher prefix at that segment; a Tandy
image (its engine is untranslated) stops the host explicitly. The timer IRQ
(1872), startup detection and the entity sound requests (AH=04 effect latch,
through the frame services' AdLib and PC-speaker bindings) all reach the
driver this way.

Platform substitution, OPL ports 0388/0389: the engine's OPL writes go in call
order to the pinned Nuked OPL3 core (third_party/Nuked-OPL3, LGPL-2.1, git
submodule) in OPL2-compatible mode, rendered at its native 49,716 Hz and timed
by an OPL bus clock. The driver's delay reads (12 after each address write, 47
after each data write) are not idle time: they space the register writes so
the chip latches each one. Every music note is written as key-off, frequency,
key-on within one update, and only that spacing (about 6 OPL samples) lets the
envelope see the key-off and restart the note. The host therefore advances
the OPL bus clock by one AT-bus I/O cycle (assumed 1 us) per original port
access and renders audio up to it before each write; between services the
clock follows the PIT. Register 04 (timers) is handled by a minimal status model,
since the core has no timers: a started, unmasked timer reports expiry (C0/A0)
by the next status read, and bit 7 clears the flags. This assumes the
detection delay outlasts 80us*(256-T1), as on the machines the driver targeted;
on real hardware the outcome depends on CPU speed. Reads of either port return
the status byte. Remaining OPL2/OPL3 differences of the core (for example the
OPL2 waveform-select enable) are unverified equivalence.

INT60 (PC speaker) is a muted sink: requests are counted and CPU state is
preserved, but PC-speaker audio is not rendered. The native-installed
PC-speaker vector at (load+0842):0182 has an explicit muted binding; other
installed vectors must match their own providers. A game-installed vector that does not match a bound provider stops;
the host does not silently redirect it. Other video modes, chain4/odd-even memory,
arbitrary BIOS/DOS calls, joystick ports, asynchronous callback bodies, nested
IRQs, instruction-boundary preemption and cycle-exact timing remain unsupported. The arena allocator is this constructed machine, not a full
DOS MCB/fragmentation implementation. PPM snapshots do not reproduce mid-screen
palette changes. These limitations do not classify unresolved code as dead.

`tools/difftest.py host_vga host_journey` runs bounded workers with temporary DLL
directories under build and cleanup after failure. `host_vga` compares generated
device traffic with `tests/minimap_vga.py`, known DAC/CRTC/clock/service vectors,
native startup, forced probe-policy profiles and independently recorded sprite-bank output hashes.
`host_journey` reuses `game_loop.setup`, `Access.script`, `Reference` and the shared
original instruction engine; only its platform provider profile changes to these
register devices and DOS/BIOS effects. It compares every loop boundary and poll,
including canonical RAM, defined CPU state, planes/latches/registers, DAC and CRTC.
It preserves the scripted cheat/next, time-up/retry and menu-return journey. Its
report is scoped to that schedule, not equivalence to arbitrary hardware timing.
The constructed journey keeps its established reference; an additional native
startup-to-menu case compares every boundary/poll through446D against original
menu instructions from the returned handoff state, including the01 sound fields.
The host journey records checkpoint state rather than ordered C bus traffic;
empty trace projections are explicit on both sides of the shared comparator.
