# Aligned read-mask effect and byte ports

`PlanarAlignedMasked4000Body` spans `969C..9736`: 155 bytes and 76 decoded
instruction sites, including its final `RETF`. Its only discovered external
static edge is `93D8 -> 969C`; other incoming indirect or modified-code states
remain unproven. The range SHA256 is
`bf138ce12dd8fa1647ecfa2ffd5a7a1a4a8c6a364b7b2a4cfef48a4c886a5ead`.
All bytes are classified code here, including the known NOPs at `9702/970B/970C`.

The core saves incoming DS before reading its graphics-segment pointer, selects
A000 as ES, and derives BP from incoming DH. The VGA setup selects all planes,
set/reset value 04 with enable mask 0E, replace logic, and read mode 1 comparing
plane 3 against one. It writes the original read-map word 0804 through live
SS:0010, now named `VgaReadMapMirror`; read mode 1 does not use the read-map index.

Each row saves CX, clears IF, and pushes DX. Byte OUT selects GC register 5;
INC DX changes the arithmetic flags while preserving CF; byte IN obtains a
provider value. CMP with 08 skips only a NOP. It does not retry or repair the
mode. POP DX reads the live saved word, which a provider or stack alias may
change before every following word output. The separate `LmnRasterBytePorts`
interface requires both callbacks; the core never invents a hardware input.
The raster bus continues to own RAM, MMIO and word-port writes.

Each pixel reads the destination comparison byte and VGA latches, ANDs that
byte with DS:BX, writes the resulting bit mask, then MOVSB copies the source.
BX always increments forward; SI and DI follow DF. STI follows the whole row.
The live source-row word is read separately for BX and SI, then the destination
row word is read for DI. The outer saved BX/DI/SI/CX and DS words are popped
live; aliases can change them. The core stops after POP DS at 9735. Only its
adapter consumes the live IP:CS frame at 9736.

The bounded suite has 17 cases covering all 75 body sites and six branch edges,
with three actual original RETF probes. It checks full RAM, all registers,
defined flags, ordered RAM and byte/word port events, VGA state, and independent
whole-plane footprints. Replies 08/09/00/FF exercise both mode-check paths.
Other cases cover zero-count wraps, DF, distinct incoming/game DS, physical and
cursor wrap, INC BX overflow, graphics-pointer and row-field stack aliases,
and a provider changing saved DX to 03CF. That changed word-port case records
an external provider seam; it makes no foreign-device or VGA equivalence claim.
SP=FFFE receives an adapter check and is excluded from original RETF probes.
Three finite mutants omit the latch read, change AND to OR, or retain game DS
after a row. Guard/provider failures do not count as detected mutants.

The original and C runs use the existing streaming whole-bus oracle and seeded
VGA fixture. Disposable workers have a 180-second deadline and Windows commit
limits of 512 MiB per process and 768 MiB per tree. Bus/device trace limits and
callback failures terminate or stop verification explicitly. IRQ scheduling,
VGA timing, arbitrary foreign-port effects and full-game ownership remain open.
