# Port I/O contracts

The master-PIC EOI leaf at 18B2..18B6 has five bytes/three sites: MOV AL,20,
OUT 20,AL, then a live near RET. AH, FLAGS and other registers are preserved.
Byte-port providers own hardware effects; this helper supplies no IRQ scheduler.

The physical port201_input.asm module spans 4334..43CD (154 bytes). It retains
UNKNOWN4395 and UNKNOWN4398, skipped by two unconditional jumps. Known code is
152 bytes: low wrapper37, high wrapper45, measurement70. No UNKNOWN byte is
reclassified or translated.

The wrappers store 03/0C through live DS:0051 before testing DL. Only DL=FF skips
the measurement CALL. The low wrapper uses BX/CX; the high wrapper copies SI/DI
to BX/CX only after its actual child RET returns to4366. Both then execute CLI,
IN201, STI, NOT AL, four/six one-bit RORs, AND AL,3 and XOR AH,AH. Consequently
AX is0..3, IF is set, and the final arithmetic flags describe zero AH even when
AL is nonzero. DF and all segment registers survive. The actual outer RET can
alias the mask store: DS=SS,SP0051 changes its low byte to03/0C.

MeasurePort201Axes executes CLI, zeros BX/CX/SI/DI, sets DX201 and emits incoming
AL as the pulse. Each iteration reads the byte port, then rereads live DS:0051.
The whole masked byte becomes BP and controls JNZ; bits4..7 can prolong the loop
without adding to any axis. Bit0 adds1 to BX, bit1 adds2 to CX, bit2 adds1 to SI
and bit3 adds2 to DI. All sums wrap16. The terminal zero sample still executes
the arithmetic sequence. STI precedes signed SAR CX,1 and SAR DI,1. These are
signed shifts of wrapped sums, not unsigned division of unbounded counts.
AX and BP finish zero; counts and final shift flags remain live. The original
poll is unbounded. Verification supplies finite input sequences and hard worker
limits rather than changing the C loop's termination condition.

DS:0051 is startup-cleared and has direct writes at4334/4359 and a read at439A.
It is not cached, nibble-limited or treated as timer-private state. With DS=SS
and entry SP0053, the CALL word at0051 replaces the mask with41/66 before the
child reads it. Providers may also change the mask during IN. The high/low
return words, wrapper saves and outer RETs remain actual canonical memory.

The input configuration at25A6 selects mouse0, indirect callback1, and keyboard
acceleration otherwise. Calibration at4A68/4A80 installs the two wrapper offsets
and stores returned BX/CX as baselines25A2/25A4. The parent at42A5 remains an
explicit indirect frontier. Its scale selector2005 is unchecked, and the X/Y
SAR chains are asymmetric; do not normalize them when that parent is translated.

The C API uses existing LmnRasterBytePorts and LmnRasterBus callbacks, which
preserve CPU registers while they can update canonical memory. Missing providers
stop at the actual IN/OUT after preceding instructions. Core boundaries stop
before the outer RET; adapters consume it only on READY. A changed child target
stops before the wrapper resumes. Hardware timing and asynchronous IRQs remain
outside these declared provider contracts.

## Scoped verification

`tools/difftest.py port_io` passes 51 fixtures at both core and adapter
boundaries: 102 comparisons, all 75 known instruction sites and eight branch
edges. The known code union is 157 bytes including the EOI leaf. The campaign
executes 3,444,790 original instructions and compares 328,314 ordered bus/port
events. Ten mutants complete and are detected; resource exhaustion is a failure.

Independent checks cover the four button results, high-wrapper skipped copies,
per-bit wrapped counters, 16,384-sample negative signed halves, 65,536-sample
counter wrap, live mask changes, CALL/mask and outer-RET/mask aliases, real
return words, missing providers, relocation, physical/EA wrap, VGA memory and
DF/IF. The original runner guards exact loaded instructions and rejects code
writes. No self-modifying execution, UNKNOWN-byte execution, hardware timing or
asynchronous interrupt behavior is claimed.

Workers have a 420-second timeout, a 384-MiB process-tree commit limit, three
million instructions and 150,000 callback events per comparison. Callbacks fail
the worker immediately on exceptions; temporary DLL directories are removed by
the parent. The retained report pins 23 consumed inputs. This is a focused
translation checkpoint; full original contracts and a matching complete native
campaign are still required for aggregate acceptance.
