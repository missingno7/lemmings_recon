# Bus-aware object interaction cells

`WriteObjectInteractionCells` at CS:37C2..3838 is a closed 119-byte leaf with
54 instruction sites and nine branch edges. Its bus-aware C source is
`c/object_cells_bus.c`; the public declarations are in
`c/object_cells_bus.h`. The existing RAM-only implementation remains the
reference for the established 123-case compatibility suite and was not
changed by this work.

The core consumes the same `LmnObjectCellsCall` and returns the existing
`LmnObjectCellsResult`. It uses one canonical 1 MiB image and routes each byte
read or write through `LmnRasterBus` when supplied. A null callback falls back
to that image. The adapter writes back the logical register results, then reads
the live RET word through the bus and advances SP by two; the core leaves RET
unconsumed.

## Memory and flag contract

The type, X and Y definition words remain separate high-byte-first reads. Their
second byte uses the independently wrapped 16-bit effective offset. Template
offsets, the saved X word, row saves and RET are little-endian machine words:
the high byte is read or written at the next 20-bit physical address, including
when the first byte is at physical FFFFF. Pushes write low then high; pops read
low then high. Every SS push, pop, cell byte and adapter RET byte is observable.

The implementation commits each instruction's flags before later observable
accesses. It models the initial XOR, both unsigned MULs, the ADD SI,AX after
type selection, the individual SHR/SHL steps, remaining ADD/AND/OR, INC and
DEC, including CF preservation for INC/DEC. Reads of a memory operand see
pre-instruction flags; writes see the current instruction phase. Tests compare
every defined flag bit at each event and omit AF only while the preceding
instruction leaves AF undefined. MUL callback checks retain its defined CF/OF
and control flags.

The unchecked type-times-28 lookup happens before the inactive-X test. Only
the first 16 definitions are visited. Zero X skips drawing after exposing the
product and template cursor; zero width or height means 256 loop iterations.
PUSH/POP row words remain live in SS, so cell writes can redirect later rows,
change source data through DS/SS aliasing, and overwrite RET. Stores proceed in
the explicit forward order regardless of DF. No records are copied into a
shadow array and no production loop cap was added.

## Differential fixture design

`tests/object_cells_bus.py` reuses the existing 123 RAM fixtures from
`tests/object_cells.py`, compares both null-bus entry points with the original
RAM API, and checks the direct bus core at RET entry plus the adapter after
RET. The original oracle trace is byte ordered and compares address, value,
access kind and all defined phase flags. It also compares full RAM, boundary
registers, and complete VGA state for provider-backed cases.
Before each oracle run it verifies every relocated decoded byte against the
pinned image. A write that changes a decoded instruction byte fails as a
verification error, never as a native differential mutant.

Five extra fixtures cover a changed VGA provider byte read through DS=A000,
VGA destination and live SS stack traffic through SS=A000, a wrapped VGA
destination, the near-RET word split across physical FFFFF/00000 with
SS=FFFF:SP=000F, and the separate SP=FFFF word whose high byte is at the next
physical address rather than segment offset zero. The established 80 real
LEVEL sections remain in the 123-case baseline. Site and edge acceptance stays
54/54 and 9/9.

Four compiled source mutations are assigned finite witnesses: zero-width
early exit, ignoring the live row-save values, clamping the unchecked type
index, and omitting the ADD SI,AX flag phase while retaining the correct SI
value. The latter uses an all-inactive fixture whose first X read distinguishes
the ADD-produced flags from the earlier MUL flags. Only a completed
differential mismatch counts as detection; that flag mutant specifically must
fail the ordered per-access flag comparison. Original instruction, callback
and access-budget exhaustion is a verification failure.
Callbacks exit with status 86 on trace exhaustion and 87 on callback failure.
The test's outer process owns the temporary DLL directory; compiler calls are
bounded to 60 seconds/256 MiB and the worker to 120 seconds/512 MiB with the
Windows process-tree ceiling at 768 MiB. The outer process snapshots all
fixture, source, documentation and loaded local Python-module hashes before
compilation, deletes a stale report first, and requires the inputs to remain
unchanged when the bounded run ends. The report declares the native code range
`[0x37C2, 0x3839)`, 119 translated bytes, executed instruction addresses, and
separate adapter/core boundary case counts; instruction addresses are
CS-relative offsets. Those 119 bytes cover the same executable interval as the
existing RAM-only translation, so they are an overlap and not additional
original-code coverage.

## Dependencies and review boundary

The bus API depends on the existing `object_cells.h`, `special_blit.h`,
`regs.h`, generated symbol ledger, pinned executable/level resources, and the
existing bounded Unicorn/VGA fixtures. This leaf still does not translate or
close `PrepareLevelObjectState` at 376A..3775, the 3839 steel writer, the 389F
coordinate collector, or the complete 36B6 initializer. The bytes outside
37C2..3838 and asynchronous VGA/IRQ ownership remain separate obligations.

The bounded suite passes128 cases (123 established RAM and five added bus
fixtures), through both core and adapter, covering54 sites/nine edges and four
completed mutant mismatches. Its separate report is
`build/object-cells-bus-differential.json`; acceptance requires current input hashes.
