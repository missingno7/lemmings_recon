# Minimap sample, row and column

The closed `796F..7A59` cluster now lives in `src/minimap.asm`, included directly
by `program.asm` at its unchanged physical position. Start/end assertions retain
its exact 235 bytes. Surrounding modules keep their provisional ownership and
UNKNOWN classifications.

The native column calls the native row, which calls the native sample on one
canonical memory and VGA byte bus. `LmnRegs` appears only in boundary adapters.
CS scratch, DS state, live SS frames and device-owned planes retain their
original address domains.

| Entry | Bytes/sites | Behavior |
|---|---:|---|
| `AccumulateMinimapSample` 7A39 | 33/16 | Read two ES bytes after saving CX; count 16 bits; OR DL into CS:BX only above eight |
| `AccumulateMinimapRow` 7A25 | 20/11 | Save CX/SI, call the sample with masks 80..01, restore live saves |
| `UpdateMinimapColumn` 796F | 182/69 | Clear scratch, advance the live column, collect 20 rows, copy 19 to VGA |

The sample reads `ES:SI` and `ES:(SI+1)&FFFF` separately. These are not a
physical-word read at SI=FFFF. Its PUSH can change source bytes; its OR can
change the saved CX or RET. AX returns zero and DH returns population. CMP
defines arithmetic flags when population is at most eight; the OR path leaves
AF undefined. See [minimap-sample.md](minimap-sample.md).

The row has eight iterations only when the saved counter is intact. One
constructed CS/SS alias extends it to 260 calls. Its final POP SI/CX can return
changed values. A changed inner RET exposes the actual target before executing
it; normal completion consumes the live outer RET. The last SHR DL leaves AF
undefined. No fixed-count loop or stale save replaces the original behavior.

The column pushes DS, pushes CS and pops ES through the bus. An aperture stack
can return an ES different from CS. It clears ten words with incoming DF. With
ordinary ES=CS, forward clearing covers CS:83C1..83D4. Reverse clearing covers
83AF..83C2, leaving other scratch rows stale and writing earlier checksum bytes.
Tests preserve those writes without executing the checksum.

Only then does it read DS:0056, `MinimapSourceColumnByteOffset`. It adds 16 with
16-bit wrap and compares the result to 208 with signed JL. Negative results can
pass. It publishes the word through live DS. DS can alias CS scratch: clearing
can change the input, and later samples can change the published word again.

Sampling starts at A000:`(column+5740)&FFFF`. Each of twenty rows advances 0680
bytes and samples eight two-byte groups. Output starts at
`(D320+(column>>4))&FFFF`, advances 13 bytes per row and copies nineteen scratch
bytes. The twentieth row is still read and accumulated.

Eight setup OUT words establish map mask 0F, set/reset 06, enable 08, mode 08,
rotate 00, care 08, compare 08 and bit mask FF. Each follows its live SS mirror
store. Read mode 1 returns plane 3 and loads all four latches. A ninth OUT sets
mode 00. Each display write is preceded by the original mode 0 read, then puts
the scratch byte in planes 0..2 and zero in plane 3. The read affects both
latches and returned AL. See [minimap-vga.md](minimap-vga.md).

Normal completion pops DS from the live stack, leaves ES=A000, DX=03CE, CX=0,
BX=83D4, SI=`(column+D940)&FFFF` and
DI=`(D320+(column>>4)+19*13)&FFFF`, subject to live-save aliases. AH is the final
scratch byte and AL the previously selected plane byte. Final INC BX defines
arithmetic flags except CF, retained from ADD DI,13. IF/DF remain incoming and
the outer RET stays live.

The suites pass 67 sample, 49 row and 62 column cases, covering all 96 sites and
fourteen integrated edges. Full RAM/register/defined-flag checks cover wrap,
source/PUSH aliases, changed saves/RET targets, signed column boundaries and
aperture stacks. Independent checks cover every plane byte, scratch population
masks, untouched rows and port order. Both DF values complete a thirteen-call
cycle on the same evolving memory/device state. Nine compiled mutants are
detected. All 65,536 source words also pass native population/flag vectors;
those add no original differential cases or executed-ASM coverage.

The domain requires intact executing minimap instructions, quiescent IRQs,
the documented unchained VGA fixture and the existing permissive 20-bit
bus/stack adapter model. CPU-family segment-limit faults, aliases overwriting
executing instructions, scanout/timing and asynchronous VGA ownership remain
outside this domain. The broader 36B6/394F level consumers and terrain/far
drawing remain untranslated. These checks never boot the original game.
