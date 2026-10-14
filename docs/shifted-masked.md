# Shifted default masked drawing body

The shifted default masked body at `890E..8B41` now has a logical C11 core and
a register adapter. The core executes the reviewed body through `POP DS` at
`8B40`; the original `RETF` at `8B41` stays in the loaded image and is consumed
by the adapter from the live `SS:SP` frame.

| Range | Physical bytes | Decoded bytes | Known instruction sites | C body sites | Boundary |
|---|---:|---:|---:|---:|---|
| `890E..8B41` | 564 | 563 | 318 | 317 | `UNKNOWN 8ADD` excluded; `RETF 8B41` remains an adapter instruction |

The raw range SHA256 is `b606303fa5acf2be33ce7aee0422b7c8e135ac09a9f54aee7a52b1da2a5f3a2b`.
The discovered normal incoming edge is `8909 -> 890E`. Static analysis found
no calls or outgoing direct edges from this body. That boundary does not rule
out indirect or modified-code entries.

On entry, `DEC word [DS:6704]` uses the incoming DS. The following saved DS is
replaced by the graphics segment read from incoming `DS:1FE4`. `MOV AX,09A9`
is relocated in the loaded executable, so the logical call supplies that loaded
game-data segment. The resulting ES is saved on the live stack. Row code later
restores DS and ES from those stack words, temporarily makes the saved ES live
DS for the source and mask scratch, and sets ES to `A000`. The source-plane
advance at `66F8` reads through the live restored ES. Stack aliases can change
these values and the `6702`, `6704`, and `A948` fields; the core keeps one
canonical RAM image and reads those fields when the original body does.

The first plane copies both source and mask rows into `DS:6706` and `DS:6748`.
REP copies and their zero sentinels follow DF. Each scratch buffer is then
shifted forward: SHR handles its first byte, RCR carries bit zero through the
following CL bytes, and INC advances the scratch cursor while preserving CF.
The shift count is read once for that row. The drawing loop increments CL
before entering LOOP, so it draws width plus one bytes. It reads each mask byte
through DS:BX, writes the bit-mask mirror and port, clears IF for the VGA latch
read and STOSB, then STI sets IF. The mask/source cursors and destination follow
their separate original updates.

The initial VGA setup enables set/reset on planes 1..3 with set/reset zero.
The first pass therefore uses the shifted source under the shifted mask on
plane 0 and clears masked bits on planes 1..3. Later passes select map masks
`02`, `04`, and `08`, switch to OR logic, and draw shifted source rows without a
mask. The first three passes save and restore their outer cursors and counts.
The hard-coded fourth pass has a different row-save layout, does not perform a
final BP test, and returns with its final SI/DI/CX effects visible. Inputs above
four still reach only these four passes; a zero plane count wraps the earlier
DEC guards and also reaches the fourth pass.

The bounded suite runs 29 cases against the original relocated executable with
constructed RAM and a four-plane VGA fixture. It compares full RAM, all returned
registers, defined flags, ordered bus traces, VGA planes/latches/registers, all
317 C body sites and 44 direct branch edges. Cases cover shifts 1..7 and zero, DF,
plane counts 0..5 and FF, multiple widths and rows, CL=0, CH=0, CL=FF, segment
and physical wrap, SP wrap, separate incoming and relocated DS values, live
stack/source/row/shift aliases, and the SS A000 device seam. Independent
byte-level witnesses check both scratch shifts and the resulting VGA plane
footprints. Three compiled mutants check RCR carry, forward scratch increments
under DF, and the live ES plane-stride read. Three isolated RETF probes execute
the unchanged original opcode; VGA-backed and stack-alias probes remain excluded
from that observation because Unicorn reads after hook removal do not preserve
the hooked device view.

The suite uses the bounded worker with a 180-second timeout, 512 MiB process
limit, a 5,000,000-instruction original cap, and finite bus/VGA trace caps.
Guard, callback, timeout, memory, or provider failures fail the suite and never
count as detected mutants. The tests boot no game and make no claim about VGA
timing, asynchronous IRQ ownership, source-buffer allocation extent, or valid
producer domains.
