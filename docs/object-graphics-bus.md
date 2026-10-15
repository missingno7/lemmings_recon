# 378A graphics-copy bus contract

`CopyLevelObjectGraphicsRecords` remains the exact 56-byte interval
0378A..037C1: 26 instruction sites and four control-flow edges. Its C core now
has a bus-aware entry point, while the original core and register adapter keep
their existing signatures and delegate through the null-bus path. The bus
adapter uses the same `LmnRasterBus` contract as the graphics routines.

Every instruction memory access can reach the provider: initial PUSH DS and
POP ES, separate definition and type byte reads, each source and destination
byte in REP MOVSB, live SI/CX/DI saves and restores, and the adapter's RET word
read. The provider receives the same 1 MiB canonical memory image used by the
core. There are no cached stack words or shadow object records. A fullword
stack access reads or writes its high byte at physical-address-plus-one with
20-bit wrap. The high byte of each big-endian definition/type value instead
comes from a separate byte instruction whose effective offset wraps at 16 bits
before segment translation.

Callbacks retain original access order and instruction flags. Initial PUSH
DS/POP ES use incoming flags. Definition bytes use flags left by the preceding
instruction. AND AX,AX defines CF/PF/ZF/SF/OF and leaves AF undefined; active
type reads and SI/CX/DI pushes see those flags. ADD SI,AX defines arithmetic
flags before REP MOVSB and the following pops. ADD BX,8 and ADD DI,28 execute
in order; ADD DI leaves the final arithmetic flags because LOOP changes CX
without changing flags. Stale slots, unchecked big-endian type multiplication,
wrapped source cursors, incoming-DF copy direction, overlapping byte copies,
and live saved-cursor/counter/RET aliases remain intact. ES is the value
actually read by POP ES, including provider-owned stack behavior.

`tests/object_graphics_bus.py` compares the compiled bus core against the
pinned original bytes executed in bounded Unicorn. It hooks each executed
instruction and every original memory read/write, compares full canonical RAM,
registers, defined flags, ordered bus events, callback flags and VGA device
state, and stops at a code hook on the actual near-RET target before that target
instruction executes. The actual RET and its provider-backed word read are
executed. The report separates the 25 core instructions before RET from all 26
executed sites, and records the observed four branch edges and each RET target.
The worker uses `run_bounded` with a 180-second timeout, a 512 MiB process cap
and a 768 MiB Windows process-tree cap. Each native callback has a 50,000-event
hard limit; callback failures exit with code 87 and budget exhaustion exits
with code 86, so neither can count as a mutation witness.

The suite reuses the 131-case original graphics matrix, including all 80 real
LEVEL sections and paired GROUND data, forward/backward DF, physical and
effective-address wrap, live cursor/counter/return aliases, and null-bus core
and adapter ABI checks. It adds indexed source/destination cases against the
existing mode-0 planar `MinimapVga` fixture with read-map 1 and write map 05,
plus an SS=A000 provider case that reads ES=7000 from the stack and ED00 through
the actual RET. The VGA cases compare independent expected copy vectors for
planes 0 and 2 while checking that planes 1 and 3 remain unchanged. The ES
readback fixture independently checks the copied bytes and plane-0 saved words.
Three compiled mutations from `OBJECT_MUTATION1/2/3` are detected by completed
original-versus-C mismatches.

The original-only REP diagnostic runs both DF directions with the first active
type producing AF=0 and the second producing AF=1. It records EFLAGS at the
first REP code hook, a repeated REP code hook, the first four REP memory hooks,
and the first POP code and memory hooks. In this Unicorn build, REP's repeated
code hook and later memory/POP hooks report AF cleared after an ADD SI,AX that
set AF; for example the AF=1 probe enters REP at 0212, while repeated and first
POP hooks report 0202. REP MOVSB and POP preserve flags architecturally, so the
oracle records callback flags from the first REP instruction-boundary snapshot
and keeps them through REP and its pops. It compares those defined flags to C
without masking AF. The diagnostic preserves both raw Unicorn hook values and
the instruction-boundary values used for bus comparisons.

The finite fixtures do not establish arbitrary provider behavior, code-byte
self-modification, arbitrary saved-counter termination, or asynchronous VGA
timing ownership. The 36B6/394F callers and wider object-producer domains remain
separate frontiers; see `object-records.md` and `next-work.md`.
