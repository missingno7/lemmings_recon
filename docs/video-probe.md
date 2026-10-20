# Video probes and raster/PIT calibration

c/video_probe.c connects the complete 13DC display detector, its four native
probe callbacks and store/CRTC children, 15AD timer-reload calibration with its
1602 measurement child, and the 0FB2 game-video/sprite-slot initializer. Their
instruction-byte union is 560 bytes. UNKNOWN 14C1 remains excluded. All BIOS
calls use the existing full-register INT10/IRET service, canonical frames and
live returned DS/ES/SS/SP. This does not supply a native BIOS or timed platform.

## Detector ownership

DS:2006/2008 are raw primary/secondary adapter pairs. The detector zeros both,
enables the EGA, color-CRTC and monochrome-CRTC records, then traverses four
three-byte records at DS:2013. Each row holds an enable byte and a near target.
The first enable byte belongs to its caller and is not enabled by the detector.
LODSB/LODSW follow DF; loading the word does not destroy TEST's flag result.
The actual SI and CX words are saved around CALL AX. Returned fields, saved
words and live records are never replaced by a cached list or shadow state.

The four recognized callbacks are 1410,1462,1490,14A0. An unrecognized target
stops before CALL1407 with its SI/CX saves intact. This is an explicit open
target domain, not evidence that other targets are dead. The existing static
unresolved-transfer count is unchanged. Known bodies consume each actual child
return and stop on a changed target before executing its continuation.

The 1410 DCC probe consumes BIOS1A00 and unchecked CS word lookups, clears later
probe flags on success, and re-enables monochrome probing when a pair's low byte
is one. EGA BIOS1210 uses an unchecked CS byte lookup at 1530 plus CL/2. These
tables are read live; out-of-range values are neither clamped nor normalized.
Color and monochrome probes write CRTC register0F, delay 256 LOOP iterations,
read back 66 and restore the observed old byte. Carry reports failure. Mono
then polls bit7 up to 8000h samples, distinguishing ordinary monochrome and the
80/81/82 raw types. Its no-transition path tail-enters the same pair store.

After probing, signed low-byte comparisons and BIOS0F may swap the pairs.
The class values are raw bytes; FF and 80 are negative in these branches.
The store helper fills the primary slot if its low byte is zero, otherwise
overwrites the secondary slot. It does not search for an unused second slot.

## Reload calibration and game video

Only DS:200E equal to FF selects the fixed reload4000. Otherwise word2011,
written by command-line producers132A/1332, selects explicit 200/400 modes or
real adapter detection. The primary pair's high byte is compared as signed
against three to select 160 or 320 horizontal cycles. The measured result is
BP=FFFF-CX and is written to DS:1FC9. The actual popped prior nonzero reload
then overrides that write; BP retains the new measurement. STI is unconditional.
Naming the word2011 does not reclassify the UNKNOWN byte2012 or close its wider
storage/initialization context.

Measurement uses ADD DL,6, retaining DH on wrap. It waits for bit3 set then
clear, programs PIT command30 and countFFFF, and observes BX bit0 clear/set
cycles. Zero BX means 65,536 cycles. Commands06/36 precede low/high reads from
40h. LOOP and IN do not replace the last TEST flags. There is no synthetic
native game timeout. Real timing, clock advancement and asynchronous IRQ
delivery remain platform obligations; the verifier supplies finite schedules.

0FB2 performs CLI, BIOS mode008D, a live returned-DS controller-port read and
word OUT1613 before STI. It initializes nine literal drawing callback words
at DS:002E..003E, the existing sprite dispatcher's canonical slots. It does
not restore incoming DS or manufacture an outer return. Core entry points stop
before the actual RET; adapters consume the current SS:SP word on success.

## Evidence scope

tests/video_probe.py uses tests/verification.py for original execution, bus,
guarded callbacks, INT/IRET and state comparison. CRTC/raster/PIT/BIOS fixtures
remain outside that engine. The campaign compares full RAM/registers, defined
flags, ordered accesses, service packets and fixture device state. Three loads,
both return boundaries, raw lookup indexes, signed classes, all polling exits,
full zero-count loops, changed stack words, returned BIOS segments/stack/flags,
unbound services/targets and exact missing-port stops are included.

Workers allow 600 seconds, 384 MiB per process / 640 MiB per tree, two million
original instructions and one million events per case. Exhaustion fails the
gate and earns no mutant credit. DLL contexts are owned and reaped under build/.
Eight numeric mutants cover IF ordering, DF traversal, signed selection, old
reload restoration, changed returns, CRTC restoration, CLI and full-byte equality.
External IRQs are quiescent and TF is clear; BIOS frame witnesses vary DF/IF
and arithmetic flags. Gameplay03E7, remaining setup/drawing dependencies, actual
device behavior and aggregate/full-game acceptance remain open.

The accepted campaign passes 93 fixtures / 186 comparisons, all 228 known
instruction sites and 69 direct branch outcomes, and eight completed mutants.
It executes 1,796,255 original instructions and compares 486,690 ordered bus
events. All 21 consumed-file hashes match. The report deliberately does not pin
ledger status/progress prose, which the fixture does not read; compiler-consumed
symbol/header offsets, ASM, native sources and shared machinery remain pinned.
All 84 unit tests and the exact ASM/relocation gate pass. The actual callback
slot/outer-return alias reaches the overwritten target through the adapter's RET.
