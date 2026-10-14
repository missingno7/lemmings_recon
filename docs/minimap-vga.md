# 796F minimap VGA fixture

`tests/minimap_vga.py` defines `MinimapVga`, an independent device model for
the bounded minimap tests around the 796F cluster. It models four device-owned
64 KiB planes behind an unchained A0000-AFFFF aperture, Graphics Controller
read modes 0 and 1, and write mode 0. CPU-visible aperture bytes are copied to
the provided physical-memory image; they are not aliases for the planar image.
The fixture records raw flags with each ordered word-port and aperture event.

Read mode 0 selects one of the four latched plane bytes with Graphics
Controller register 4. Read mode 1 compares each bit position's four-plane
color against register 2, using register 7 as the per-plane care mask. A zero
care mask therefore matches every pixel and returns `FF`. Every aperture read
loads all four latches. Write mode 0 rotates the CPU byte, selects host data or
per-plane set/reset, applies the Graphics Controller logical operation, merges
the result with the old latch through register 8's bit mask, and writes only
planes enabled by Sequencer register 2.

The fixture requires chain-4 and odd/even addressing to be disabled, graphics
mode and the 64 KiB A000 aperture to be selected, and write mode 0 for writes.
It does not model display scanout, timing, palette/attribute-controller state,
IRQ behavior, or VGA variants. It supports the mode-0 rotate and logical
operation fields needed for truth-table validation; no claim is made that the
796F routine uses nonzero rotation or a non-replace operation. The current
796F setup of read mode 1, color compare `08`, care mask `08`, set/reset `06`,
set/reset enable `08`, replace operation, map mask `0F`, and bit mask `FF`
makes reads return plane 3 and writes CPU data to planes 0-2 plus zero to
plane 3.

The register and plane behavior follows the FreeVGA primary reference pages:
[Graphics Registers](https://www.osdever.net/FreeVGA/vga/graphreg.htm),
[Accessing VGA Display Memory](https://www.osdever.net/FreeVGA/vga/vgamem.htm),
and [Sequencer Registers](https://www.osdever.net/FreeVGA/vga/seqreg.htm).
`fixture_vectors()` checks all 16 color-compare values against all 16 care
masks over pixels encoding every four-plane color, the four read-map choices,
latch loading, set/reset, plane map mask, bit-mask read/modify/write, rotation,
and the four logical operations.
