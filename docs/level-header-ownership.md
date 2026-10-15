# Header destinations and their consumers

This static ownership pass supplements level-initialize-frontier.md. It does
records names through the symbol ledger without adding C coverage. Offsets refer to the original
live DS frame; the source header is `LoadedLevelRecord` at `0FCB`.

## Adjustable release setting: header +00

`36C1/36C4` publish the same low byte at `0064/0067`. Later consumers distinguish
them. `4046..404F` increments `0067` until it equals `63`; `4068..407F` compares
it with `0064` before decrementing it. Thus `0064` supplies the lower adjustment
bound and `0067` is the current setting. Both feed the display helper `762A`
with selector AL=0/1 at `3A57..3A66`.

`39D6..39E6` and `4053..4063` derive byte `0049` from `0067` through the exact
wrapped SUB/SHR/NEG/ADD sequence. `30BA` decrements byte `0048`; when it reaches
zero, `30C3..30C6` reload it from `0049` before attempting to create a record.
These are timing and adjustment contracts. Keep the original byte arithmetic
and equality tests; the source does not validate the header against a host range.

## Created-record limit: header +02

`36CD` stores the low byte at `0047`. `30CC..30D5` compares it with `0043` and
skips record creation on equality. Otherwise `30D7..30EC` uses that byte counter
to select one of four `TypeOneObjectCoordinates` and compute `0088 + counter*2D`.
The routine clears 45 bytes at that address, initializes the live record and
increments `0043` at `314B`. The later `3634` loop visits `0043` records at the
same base/stride and counts records not marked `FF` at field `+26` into `0045`.

The limit is mutable: `4010..4013` replaces `0047` with current `0043`. The
main loop at `01E7..01F7` tests limit equality plus the active count. This supports
separate names for the current creation counter, mutable creation limit and
active-record count; it does not prove an allocation extent or safe host-array
bound. `3AC8..3AF4` separately divides a value derived from `0046` by `0047`,
skipping DIV only when the divisor is zero.

The address arithmetic exposes an important phase/alias obligation. Record index
86 begins at `0FA6` and its 45-byte clear reaches `0FD2`, intersecting the loaded
header at `0FCB`. Index 87 starts at `0FD3`. This follows from the static base and
stride; it is not a claim that those indexes occur in the supplied game states.
Do not introduce disjoint host records or retain a shadow header without proving
the producer domain and temporal ownership. The original code has one RAM image.

## Other header stores

Header `+06` becomes byte `20A7` after a wrapped word addition of `30` at `36DF`.
`021F..0246` treats it together with `20A9/20AA` as an ASCII countdown: it borrows
through `2F`, restores `39/35`, and clamps all three digits to `30`. The termination
test at `01FA..0209` also observes all three bytes. Initialization of the other
two digits is separate; a C header helper must not synthesize or reset them.

Header `+08..+16` populates eight low-byte counts at `006A/006D/0070/0073/0076/
0079/007C/007F`. The assignment routines at `31C4`, `320D`, `329B`, `32BD`,
`3336`, `34CE`, `3557` and `3598` test/decrement individual counts, clear their
associated display-dirty byte, and change live record fields/callbacks. This
establishes consumable per-action counts; historical action names need the
record-state/callback evidence, not just the file-format order.

Header `+18` is published as a wrapped word plus `10` at DS:`0000`, then its
logical right shift by three at DS:`0002`. `7BCF` subtracts `0000` from an object
X coordinate before adding `10`; `7A5A/7AAF` shift the same word for display
addressing. `8130/81AE` add `0002` to source offset `4A40`. These observations
support pixel/byte view-origin roles while retaining the explicit `+10` bias.

Header `+04` is stored at `0044`, but this direct-operand search has not closed
its downstream meaning. Missing a direct read is not evidence that it is dead:
indexed access, other segment ownership and unresolved code still require review.

The apparent `DI=0044` at `7DE1` is a different owner: `7D1C` loads ES from the
DOS-allocated segment at `1FF0`, and `7DD9..7DDF` selects a graphics source DS.
`7DF1` reads `ES:[DI]` and `7DF6 STOSB` writes ES:DI. It does not establish a
consumer of the header destination. The ledger therefore keeps
`LevelHeaderWord04LowByte` neutral. Its original `36D0 8A6504`, `36D3 8A4505`,
`36D6 A24400` read/read/store sequence stays intact.
