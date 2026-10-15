# Original-only level header prefix contract

`tests/level_header_contract.py` checks only the original x86 prefix
`36B9..3741`, ending before `3742`. It executes the pinned bytes through the
bounded `drawing_caller_oracle.original` with a 64-instruction limit. The
instruction map contains only these 137 bytes (47 decoded sites); the only
continuation is `3742`, and there are no declared far calls. The test compares
the original against a separate, compact field model over one canonical RAM
image and the existing `TraceDevice`/`MinimapVga` fixture. It does not call C,
the legacy interpreter, or later level setup code. Unicorn executes the original
x86 instructions; no opcode is replaced.

The prefix sets `DI=0FCB` and reads thirteen big-endian words as 26 individual
high-byte then low-byte reads. It copies only the low byte for these fields:

| Header word | Destination and operation |
|---|---|
| `+00` | Same low byte to `DS:0064` and `DS:0067` |
| `+02` | Low byte to `DS:0047` |
| `+04` | Low byte to `DS:0044` |
| `+06` | 16-bit `ADD AX,0030`, then low byte to `DS:20A7` |
| `+08..+16` | Low bytes to `DS:006A,006D,0070,0073,0076,0079,007C,007F` |
| `+18` | 16-bit `ADD AX,0010`; word store to `DS:0000`; three separate `SHR AX,1`; word store to `DS:0002` |

The check poisons destination bytes before execution. That exposes which byte
stores truncate values and which two stores write full words. Constructed words
also use nonzero, distinct high bytes, so the test still verifies their reads
and the original bus ordering even when consumers use only the low byte. The
view vectors `FFF4` and `FFF0` wrap at the 16-bit addition: after the three
single-bit shifts, the first ends with CF=1 and OF=0, and the second ends with
CF=0. AF is excluded from the post-shift flag comparison because SHR leaves it
undefined. Initial DF and IF vary across the 80 pinned headers and the
constructed cases.

The full pinned set is extracted from eight sections in each of the ten
`assets/levelNNN.dat` files. Additional cases use `DS=FFFF` to exercise 20-bit
physical wrap and `DS=A000` to route the header reads and low destinations
through the four-plane VGA fixture. Each side gets its own memory image and
device; the model reads and mutates that image as it proceeds. The check compares
registers, defined flags, every original instruction site, the ordered byte
read/write trace, the final RAM image, and VGA state.

Eight additional arithmetic-boundary cases cover zero, signed overflow and the
last values before/after unsigned addition wraps for both adjusted words. Each
case also checks AX and defined flags at all three individual SHR entries and
the following store, including the first shift's OF and the final shift's CF.
The report hashes the full local Python import closure before execution and
requires every input hash to remain unchanged before publishing acceptance.

The destinations are observed storage behavior, not new historical field
names. `+00` later supplies a lower adjustment bound at `0064` and current
setting at `0067`; `+02` is a mutable creation limit at `0047`; and `+06` feeds
an ASCII countdown byte at `20A7`. The `+08..+16` values are consumable action
counts. `+18` supplies a biased view origin at `0000` and its shifted byte
offset at `0002`. The downstream meaning of `+04` remains unresolved. These
roles and their evidence are detailed in
[`level-header-ownership.md`](level-header-ownership.md).

The ownership evidence also shows why the source must remain ordinary shared
RAM: record index 86 starts at `0FA6`, and its 45-byte clear reaches `0FD2`,
overlapping `LoadedLevelRecord` at `0FCB`. This test makes no assumption that
host records are disjoint or that `0FCB` is a closed allocation boundary.

Run the script directly to launch its worker with a 120-second timeout and a
512 MiB process limit (768 MiB Windows process-tree commit limit). The generated
`build/level-header-contract-original.json` records original-only execution and
input hashes. Its results do not add translated-code or C-execution coverage,
and they do not establish full `36B6..3789` caller readiness.
