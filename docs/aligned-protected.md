# Aligned protected planar body

`PlanarAlignedMasked8000Body` at 953E is a closed effect body ending at POP DS
969A. Its one-byte RETF adapter boundary is 969B. The physical range
953E..969B is 350 bytes; 349 bytes decode to 177 instruction sites after the
UNKNOWN NOP at 9659 is excluded. The body has 176 decoded sites, 26 observed
branch edges, and the sole discovered external static edge is 93E1->953E.
Other indirect or modified-code entry domains remain open.

The entry saves live DS, loads the graphics source segment through the incoming
DS, and selects A000:0000 as ES. It derives BP from the input DX high byte by
swapping DL/DH and clearing DH. The VGA setup selects plane 0, enables set/reset
with zero set/reset data, selects rotate count zero with logical OR, then sets
read mode 1, color-care mask 08 and color-compare value 08. The read-mode-1 byte
at ES:DI is therefore the set-bit pattern from plane 3. `NOT AH` makes its
complement the write bit mask. Each source byte is ORed into selected planes at
bits where plane 3 was clear; the fourth pass targets plane 3 and fills those
bits. The read-modify-write cycle refreshes all four VGA latches before each
write.

The first, second and third passes save and restore DI, SI and CX through live
SS memory and decrement BP. The fourth pass does not save those registers and
does not decrement BP. An initial plane count of zero underflows and still
reaches all four passes; counts greater than four also stop after four. Rows
clear CH while retaining CL, process a full 16-bit LOOP count, set IF with STI
at each row end, then add the live 6702 source-row advance and 6704 destination
row advance. Source planes advance through live DS:66F8. Incoming DF controls
the per-byte SI/DI direction, while row advances remain original 16-bit additions.

Later-plane setup temporarily changes DL to C4 for the Sequencer map-mask
write, then restores DX from its live stack save before the per-byte Graphics
Controller output. SS aliases can therefore change the restored DX, saved
cursors, row count, DS, and returned far frame. The C core models every push,
pop, and word read/write against the same 20-bit RAM and VGA callback path.
It leaves BX untouched and returns AX after the final row advance, along with
the live CX, DX, SI, DI, BP, SP, DS, ES, and flags. IF, DF, arithmetic flags,
logical flags, and the undefined AF value from XOR are retained according to
the original instruction effects. The adapter consumes the live IP:CS frame
with ordered reads and does not execute its target.

The differential fixture in `tests/aligned_protected.py` compares full RAM,
all registers, defined flags, ordered RAM/VGA events, and VGA planes, latches,
registers, and port state against the original routine in bounded Unicorn
execution. Independent plane-footprint cases exercise the read-mode-1
protection truth table. `tests/minimap_vga.py` supplies the separate VGA device
fixture: unchained A000 64 KiB aperture, four latches, read modes 0/1 and
write-mode-0 replace/OR/bit-mask behavior. This fixture does not model scanout,
timing, or asynchronous IRQ scheduling.

Cases cover plane limits 0, 1, 2, 3, 4, 5 and FF; DF; zero CL and CH wrap;
16-bit source/destination wrap; distinct incoming and game DS; source and
destination VGA aliases; SS aperture stack writes; a live PUSHDX/POP DX alias;
and the RETF adapter. VGA-stack cases seed only the plane-3 bytes that control
the read-mode-1 values of saved row counts, DS, or DX, so they stay finite while
exercising the actual aliases. These are constructed-state domains, not claims
about the complete caller or device environment.
