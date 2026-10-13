# Hardware boundary inventory

Observed statically at startup: DOS allocation/file/vector services (INT21), BIOS
time (INT1A), video mode (INT10), PIT programming (ports 43/40), saved INT08/09 vectors,
and an INT24 handler. Code has VGA register I/O and mouse service use.

Legacy leads, not yet complete independently verified models: VGA planar modes 0D/10,
CRTC scrolling, palette changes, PIT/PIC interrupt timing, keyboard and mouse, OPL and
runtime-loaded ADLIB driver. See forged game.json and legacy recovery_facts sources
recorded by the initial investigation. Do not substitute sleeps for timing contracts
or transfer its custom emulator into the C runtime.

No platform service or SDL3 host is implemented at this milestone. Each replacement
will need an explicit narrow interface and independent device contract tests. The
checksum cluster has no DOS/device dependencies and is therefore suitable as the
first differential boundary.
