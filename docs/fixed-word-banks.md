# Fixed word-pattern banks

This note records the static source and caller contract around `5CC1`, with
the focused C acceptance described below.

## Static ownership

The ledger names are `FixedWordPatternA` at DS offset `52BC` and
`FixedWordPatternB` at `531C`. The 192-byte source span is contiguous:
`DS:52BC..537B`. With the startup data frame `DS=relocated 09A9`, these are
image offsets `ED4C..EDAB` and `EDAC..EE0B`, respectively. They contain 48
little-endian words apiece, arranged as three consecutive groups of 16 words:

```text
FixedWordPatternA, groups 0 / 1 / 2:
0000 0001 0000 0001 0000 0001 0000 AA01 8055 0000 8000 0000 8000 0000 8000 0000
0000 8001 0000 8001 0000 8001 0000 2A54 2A54 0000 8001 0000 8001 0000 8001 0000
0000 8001 0000 8001 0000 8001 0000 AA55 AA55 0000 8001 0000 8001 0000 8001 0000

FixedWordPatternB, groups 0 / 1 / 2:
0000 9819 0000 0240 0240 0000 0000 0240 0240 0000 0000 0240 0240 0000 9819 0000
0000 1E78 0240 0240 0240 0000 0000 0000 0000 0000 0000 0240 0240 0240 1E78 0000
0000 9E79 0240 0240 0240 0000 0000 0240 0240 0000 0000 0240 0240 0000 9E79 0000
```

These word values are the exact bytes in `image_tail.asm`, decoded little
endian. The current region ledger still classifies the containing
`0C032..0EF0C` span as unresolved, and the assembly keeps these bytes marked
`UNKNOWN`. The reads below establish these two source windows' role; they do
not reclassify them or their neighbors.

`ProgramEntry` loads DS from the relocated `09A9` immediate at `0000` and clears
`DS:0000..2011` at `002C..0031`. The relocation is at image offset `0001`;
the table offsets and the word at `DS:1FEA` have no relocation fixups. The
`1FEA` word is initially zero and is assigned at runtime by `sub_1007`:
successful DOS allocation (`AH=48h`, `BX=5571h`) stores the base at `1FE4`,
then adds `1000h` for `1FE6`, `1D0Ch` for `1FE8`, and `166h` for `1FEA`.
The carry path at `0100E` goes to the allocation error path. The following
`+90h` paragraph step initializes `StatusGlyphBufferSegment` at `1FEC`.

The ledger name for the selector at `1FEA` is
`GeneratedWordPatternBufferSegment`. Its value is live DS memory: `5CC1` loads
it into ES at `05CC4`, while `5827` later loads it into DS at `05862`. The
`5CC1` output occupies offsets `0000..08FF` in that segment under the normal
path. The `+90h` selector step is exactly 900h bytes, but these arithmetic
coordinates alone do not establish allocation lifetime, non-aliasing, or a
general memory-safety bound.

## Generator and shared tail

`sub_5CC1` is the 28-byte setup at `5CC1..5CDC`. It sets
`SI=52BC`, `ES=DS:[1FEA]`, `DI=0`, `CX=16`, and `BL=3`, then makes the actual
near CALL to `GenerateWordMaskShifts` at `5CCF`. The child's RET at `5D17`
returns to `5CD2`. The second setup sets `SI=531C`, `DI=480h`, `BL=3`, and
`CX=16`, then falls through into the same body at `5CDD`; there is no second
CALL and no second child return word. The final RET at `5D17` consumes the
outer return word created by `LoadMainResourceSections` at `58E8`, returning to
`58EB`.

`GenerateWordMaskShifts` occupies `5CDD..5D17` (59 bytes). It clears DH, then
for each shift loads words with `LODSW`, clears DL, and shifts the `AL:AH:DL`
bit chain right DH times using `SHR AL,1; RCR AH,1; RCR DL,1`. It stores
`AL`, `AH`, and `DL` to ES:DI with three explicit `INC DI` instructions.
`LODSW` follows DF; those destination increments always move forward. The
outer shift loop saves and restores DX, BX, and SI on the live SS stack. The
repetition and row loops also use live saved BX/CX words. A stack alias can
therefore change restored controls, source cursors, counts, and return flow.
There are no artificial loop caps.

With DF clear and intact, disjoint code, data, and stack frames, each source
pass consumes the three consecutive groups of 16 words. For each of eight
shifts it emits `3 groups * 16 words * 3 bytes = 144 bytes (90h)`. Each source
therefore produces `8 * 90h = 480h` bytes: A at ES:`0000..047F`, B at
ES:`0480..08FF`, for `2 * 480h = 900h` total. Within each 90h shift slice,
each source group becomes a 30h-byte plane of 16 rows by 3 output bytes. These
are the normal-path equations; live DF, stack contents, aliases, and segment
wrapping remain part of the original contract.

For a word memory access, the low byte is accessed at the current physical
address and the high byte at physical address plus one, with 20-bit physical
wrap. The string cursor itself advances or retreats by two with 16-bit SI
wrap. Thus the physical high-byte address is not derived by wrapping the
offset to `0000` first. Byte stores use the current ES:DI physical address;
their explicit DI increments wrap at 16 bits.

On the intact normal exit, the final `CMP DH,8` at `5D12` supplies the
generator's flags; RET does not change them. Save-word aliases can alter that
path and its flags. DS, ES, SS, and BP are not changed by the shared body;
AX, BX, CX, DX, SI, DI, and FLAGS are live outputs. `5D18..5D65` remains
UNKNOWN and outside this contract.

## Consumer slice

`sub_5827` selects one 144-byte slice from the generated buffer. It computes
`a = (word DS:[0010h] + zero-extended byte DS:[1FE0h]) & 7`, then
`SI = 144 * a`. It adds `480h` only when byte `DS:[001Ah]` is exactly `FFh`;
all other values select the first half. It sets `BX=SI+60h`, loads
`DI=word DS:[000Ch]`, saves DS, loads DS from `DS:[1FEA]`, and calls
`sub_7218` at `5866`. The largest normal slice starts at `0870h` and ends at
`0900h` exclusive.

`sub_7218` consumes the full selected 90h slice. Its first 16 unrolled rows
read 30h bytes through SI with `LODSW`/`LODSB`; its next 16 rows consume the
following 30h bytes. In the first pass, each row also reads three bytes
through BX, beginning at `SI+60h`: a word and then a byte. Those third-plane
values are written to VGA Graphics Controller index 8 as per-byte bit-mask
controls. The first two planes provide the three-byte-per-row data streams.
The routine sets ES to A000h, performs latch reads and VGA writes, resets DI
to its saved base between passes, and advances rows with `ADD DI,29h`. This
describes the byte use and device operations without assigning higher-level
game meaning to the patterns.

There is no local CLD: DF remains live through both the generator and
consumer. In `sub_7218`, the final `STI; RET` at `75ED..75EE` enables
interrupts and returns through the actual near-call word. Under DF clear, SI
has advanced by 60h and BX by 30h; BP retains the entry DI and DI is entry DI
plus 2C0h. ES remains A000h. `5827` restores DS with its live `POP DS` at
`5869`, then performs the original memory exchanges at `586A..587B` and
returns through its actual outer RET at `587E`. Its post-call MOV/XCHG
instructions do not change the flags left by the consumer's final `ADD DI`.

The startup call at `00D5` reaches `LoadMainResourceSections`; that routine
restores DS around the resource loader, and the preceding sprite-bank parent
saves and restores DS before the `58E8` call to `5CC1`. Consumers therefore
depend on the bank having been initialized after successful allocation. The
allocation request, segment arithmetic, and selected slices establish the
normal coordinates, but broader allocation bounds, later mutation, and buffer
lifetime remain open.

## Scoped C acceptance

`c/fixed_word_banks.c` adds the 28-byte prefix and composes the existing
59-byte native word generator. The core stops before the final shared RET;
the adapter consumes the actual outer word only on READY. A changed first
child return stops with its returned registers and child-entry provenance.
The second pass uses the child core without a synthetic CALL frame.

`tests/fixed_word_banks.py` passes 15 fixtures at both boundaries: 30 comparisons,
87 integrated bytes, all 46 sites and ten branch outcomes, 197,574 ordered bus
events and 642,524 original instruction steps. Independent equations check
23,040 output bytes across static, constructed, DF, selector and wrapped-output
cases. All ten numeric mutants finish and are detected; exhaustion earns no
credit. The suite preserves live selector and saved BX/DX/SI/count/return
providers, source/output/stack overlap, a VGA stack, physical word wrap and
16-bit cursor wrap. The child bytes overlap its prior translation and are
counted once in the main C union.

The native and original-only reports are
`build/fixed-word-banks-differential.json` and
`build/fixed-word-banks-original-differential.json`. Only their matching input
hashes and recorded cases establish this result. The process-tree cap is
384 MiB, the worker deadline is 420 seconds, the original step budget is
250,000 per invocation and the callback budget is 150,000. Ordered traces use
20-byte records. This does not refresh unrelated campaigns or establish full
resource, allocation, timing or game acceptance.
