# Entity pixel address and mask preparation

`PrepareEntityPixelSample` at 5DC6..5DF7 has 50 bytes and 22 decoded sites.
The normal simulation calls it with the live 2Dh record cursor in DS:SI.
Words +0/+2 supply coordinates. Callers such as 27EF read ES:DI and AND the
byte with AH; the helper itself performs no VGA read, port operation or wait.
Full simulation-state and device behavior remain separate parent contracts.

`PixelBitMasks` is the eight-byte table at DS:547C (stored image EF0C..EF13):
80h, 40h, 20h, 10h, 08h, 04h, 02h, 01h. Index formation and reads at
5DEE/5DF1/5DF5, 6164/6167/616B, 6F40/6F43/6F47/6F49 and
7054/7058/705B/705D establish the eight-byte access span. The last two readers
also send the selected mask through VGA register 08h. Only those eight stored
bytes are newly classified; adjoining bytes remain UNKNOWN. This data use
does not exclude other executable interpretations or prove runtime immutability.
The core reads the actual live DS table byte, including stack aliases or a
different incoming DS, rather than recomputing a constant mask.

The helper sets ES=A000h, reads Y at DS:SI+2 and subtracts 10h with 16-bit
wrap. JNS tests that result's sign: Y=8000h therefore yields positive 7FF0h
and is not clamped. A negative result is replaced with zero. It pushes DX
to live SS:SP, multiplies the resulting row by literal D0h (208), and pops
DX before reading X at DS:SI. That ordering lets the stack save change X.
The low product supplies DI, then logical X/8 and literal 4A40h are added
with 16-bit wrapping. The original does not consult a mutable row-pitch or
origin field here.

CX returns logical X/8. BX returns 547Ch+(X&7). AH is replaced by the byte
read from live DS:BX; AL retains the product's low byte. Returning only a
mask or clearing AX would lose an original output. DX is popped from live
SS, SI/BP/DS/SS are unchanged, and ES returns A000h. Flags come from the final
ADD BX,547Ch: after AND 7 its result cannot carry, overflow, become negative
or zero, while AF and PF depend on the index. DF and other control flags
are preserved. The branch has two paths at 5DD1: sign clear reaches 5DD5,
and sign set passes through XOR DI,DI at 5DD3.

The C core ends immediately before RET; the register adapter consumes the
actual near return word from SS:SP. Stack and source offsets wrap at 16 bits;
word high bytes use physical address+1 with 20-bit wrap. The only memory
write is PUSH DX at incoming SP-2. In ordinary RAM it cannot overwrite the
same frame's RET word, but it can alter a later X or table read. The tested
domain retains all such RAM aliases, intact executing code, TF clear and
quiescent interrupts. Provider/device-backed memory and full parent closure
are separate obligations. Coordinates and masks remain in canonical memory;
no converted entity state is introduced.

The focused `tools/difftest.py entity_pixel` suite passes 39 fixtures at both
core and actual-RET boundaries, comparing the complete 1 MiB RAM image, every
register and final defined flags against original execution. An independent
ordered arithmetic/state model checks each original result. All 22 sites and
both JNS edges execute. Fixtures cover all eight pinned masks, changed live
table bytes, wrapped sign boundaries, residual AL, logical X shifts, product
wrap, both DF states, record/stack/physical wrap and DS/SS X/Y/table aliases.
Four completed mutants exercise an incorrect Y clamp, reading X before PUSH,
replacing the table with constants and clearing AL.

The worker has a 180-second deadline and a 384 MiB process commit limit
(640 MiB tree). Original execution is limited to 100 instructions per call;
native calls have no callbacks or data-dependent loops. Exhaustion fails the
gate and cannot count as mutant detection. Owned DLL directories are removed
after the worker exits, including failure paths. The retained report at
build/entity-pixel-differential.json contains its exact input hashes and scope.
This closes the leaf's ordinary-RAM contract, not parent/device acceptance or
aggregate whole-game coverage.

The bus-aware core/adapter now route every Y, stack, X, table and return byte
through the optional raster bus; the original RAM APIs delegate with a null bus.
The memory order remains Y, PUSH DX, POP DX, X, table, actual RET. SUB/XOR flags
are visible at the push, only MUL's defined CF/OF at the pop and X read, and
the final ADD flags at table/return reads. Undefined MUL flags are not compared
as defined outputs. The bus preserves registers and can change later memory.

`tools/difftest.py entity_pixel_bus` passes 30 fixtures at both boundaries,
with 600 ordered bus events, all 22 sites, both JNS edges and one completed
bus-bypass mutant. Null-bus calls preserve the existing ABI. Additional cases
route DS records/table or SS saves/RET through the independent VGA fixture,
and provider reads change a future X word, table byte or high RET byte. This
extends the earlier RAM domain without adding translated bytes. Worker limits
remain 180 seconds/384 MiB process/640 MiB tree, original calls 100 instructions,
and bus/device traces 64 events with hard exits 86/87 on exhaustion/error.
DLL cleanup and fresh input hashes are required for the retained scoped report
at build/entity-pixel-bus-differential.json. No OUT is introduced by this leaf.
