# Hardware boundary inventory

Observed statically at startup: DOS allocation/file/vector services (INT21), BIOS
time (INT1A), video mode (INT10), PIT programming (ports 43/40), saved INT08/09 vectors,
and an INT24 handler. Code has VGA register I/O and mouse service use.

Legacy leads, not yet complete independently verified models: VGA planar modes 0D/10,
CRTC scrolling, palette changes, PIT/PIC interrupt timing, keyboard and mouse, OPL and
runtime-loaded ADLIB driver. See forged game.json and legacy recovery_facts sources
recorded by the initial investigation. Do not substitute sleeps for timing contracts
or transfer its custom emulator into the C runtime.

Native resource/file cores have narrow DOS interfaces, and the special-resource
strip core has a physical-memory/word-port raster interface. Its bounded VGA
fixture verifies mode-zero plane writes, register/mirror order, latch reads and
interrupt-enable states; see [special strips](special-blit.md) for the documented
device contract and tested aliases. This fixture is not a native platform backend.
VGA mode setup, palette/scrolling, IRQ delivery and actual DOS ownership remain
open. No SDL3 host is implemented.
