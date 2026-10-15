# Observable type-one coordinate collection

CollectTypeOneObjectCoordinates occupies CS:389F..3943 (end exclusive):
165 original bytes, 63 decoded instruction sites and 12 branch edges. The
bus-aware implementation exercises the same 165 C bytes as the RAM-only core
in c/object_coordinates.c. These overlapping variants count once in byte
coverage. The bounded suite passes164 adapter and164 auxiliary core cases,
63 sites/12 edges and four completed mutant mismatches. This leaf's evidence
does not establish the full36B6 initializer's bus domain.

lmn_collect_type_one_object_coordinates_bus_core takes the live DS and entry
flags plus an optional LmnRasterBus. Its result carries AX, CX, SI, BX, BP
and flags as logical values. It operates on one canonical 1 MiB memory image;
the bus owns observable device behavior, not a second record image. A null bus
uses ordinary RAM and is compared with the existing core. The adapter maps the
logical result to the live registers and reads the actual near-RET word only
after the output stores.

The core scans all 32 eight-byte definitions at DS:0FEB. It compares the
complete big-endian type word at +4 with one, without requiring a nonzero X.
Each match reads X and adds 18h, writes that little-endian word, then reads Y
and adds 1Eh before writing the second word. The output cursor advances by
four and the definition cursor by eight. More than four matches are not
clamped.

The bus makes instruction order observable. Each BE word is two high-then-low
byte reads, with each DS:offset computed independently modulo 16 bits.
Machine-word accesses use little-endian byte order at one physical address and
its next byte, wrapped modulo 20 bits. For a matching definition, the X output
write completes before either Y source byte is read. The final near RET also
reads its live stack bytes through the optional bus.

The exact flag phase is passed to every callback. CMP, ADD, and INC produce
their individual 16-bit arithmetic flags; INC BP preserves CF. LOOP preserves
flags. IF and DF remain live. AF is not asserted after the initial XOR BP,BP
or the later zero-count AND BP,BP, where it is undefined.
The count-specific fill code remains intact: one match repeats its last pair,
two matches produce last then first, and three use the second pair for the
fourth slot. With no matches, the default sequence writes Y at +0A, then
overwrites the same +0A word with X and leaves +0C stale.

tests/object_coordinates_bus.py retains all 159 existing RAM fixtures and
adds five bus-focused cases, for 164 normalized cases each through the adapter
and core boundaries. It compares the old and new null-bus cores and adapters,
then checks the original instruction stream against ordered native byte events,
defined callback flags, the whole memory image, registers and VGA device state.
The added cases cover a VGA source and destination, a destination that crosses
from VGA into RAM, a provider-backed near RET, VGA output that overwrites the
live return word, and a return word straddling physical FFFFF..00000. The old
and added case counts are reported separately. The native range is
389F..3943, and the 165-byte interval overlaps the RAM-only translation rather
than adding a second coverage span.

The harness includes four deliberate bus mutations: read Y before storing X,
reverse the BE byte-read order, repair the repeated +0A store, and omit the X
ADD flag update while retaining its correct value. The last mutation is
witnessed by the VGA source-and-destination case, where the type CMP is equal
but the X ADD changes ZF before the store and later Y reads. A mutation counts
only when a completed comparison raises a differential mismatch. A timeout,
callback failure, access cap, or memory limit is a failed run.
Callbacks hard-exit with code 86 on a finite-access guard and 87 on a callback
exception, so Python callback exceptions cannot leave native code looping.
Compiler processes are bounded to 60 seconds and 256 MiB. The isolated worker
is bounded to 120 seconds, 512 MiB process memory and the helper's 768 MiB
process-tree commit limit. The outer process owns the temporary DLL directory
and removes it after worker success or failure.

The dependency closure includes the maintained bus and RAM C sources, their
headers, the original fixture and bus test, the VGA device fixture,
unpack/resource helpers, symbol/input metadata, the pinned executable, loaded
local Python imports, and the ten LEVEL assets used by the 159-case matrix.
Hashes are captured before compilation and checked again after the worker. This
leaf preserves the existing RAM-only suite as a regression gate; it does not
claim that its records, callers, or broader bus domain are closed.
