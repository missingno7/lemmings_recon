# Terrain command streams

The retained bounded campaign recorded 192 cases: all 80 pinned LEVEL streams at
both entries plus 32 constructed cases, with 32 auxiliary core comparisons and
two completed mutation witnesses. Its recorded cases cover 1,383 integrated
instruction sites and 195 edges, compare 358,815,156 bus events and perform
23,324 independent body-plane checks. Its historical report is
`build/terrain-stream-differential.json`; acceptance remains tied to its exact
input hashes and the domain below. Check those hashes before treating it as current
acceptance; preserving this narrative does not refresh it. See completeness.md
for the current inventory. This does not promote aggregate game coverage.

## Static boundary

`DrawLevelTerrainStream` begins at `374F` and `RedrawLevelTerrainStream` begins
at `395F`. Each entry initializes `SI` to the ledger-owned
`LevelTerrainDefinitions` offset (`10EB`) and enters the same seven-instruction
command reader. The two complete init-and-loop regions are 27 bytes and ten
sites each:

| Region | SHA-256 | Reader start | Normal piece call | Sentinel continuation |
|---|---|---|---|---|
| `374F..3769` | `bafd85725db0ea1282923fe487caf4e21e7ea4b8e34544cc4008fed8210e0781` | `3752` | `3765` | `376A` |
| `395F..3979` | `9f020bf8d298a5bec587529e8f78cfd63ad79f5f4d8e11f5df321ea2303955cf` | `3962` | `3975` | `397A` |

The reader itself is 19 bytes per loop, at `3752..3764` and `3962..3974`.
Its seven instruction sites are four byte loads, `ADD SI,4`, `CMP AX,FFFF`,
and the conditional jump. The branch at `3763` goes to `3765` or `376A`; the
branch at `3973` goes to `3975` or `397A`. `UNKNOWN` bytes `374E` and `395E`
are outside these regions. The sole discovered outside incoming edges target
the initializer: `3747 -> 374F` and `3957 -> 395F`. The initialized reader
then follows the `MOV SI` fallthrough; its later iterations follow the back jump.

## Command contract

The reader loads `[DS:SI]`, `[DS:SI+1]`, `[DS:SI+2]`, and `[DS:SI+3]` as four
separate bytes. The first pair forms big-endian `AX`; the second forms
big-endian `BX`. Each effective offset wraps at 16 bits before real-mode
physical addressing wraps at 20 bits. It advances live `SI` by four and
compares the complete `AX` with `FFFF`. Thus a command whose high byte is
`FF` still calls `7C67` unless its low byte is also `FF`.

`CMP AX,FFFF` supplies the exit flags, replacing the arithmetic flags from
`ADD SI,4`; `IF`, `DF`, and other unaffected flags remain live. The four reads
are individually visible on `LmnRasterBus`. No command-count cap or corrected
buffer extent is added. The supplied level files contain a sentinel after
their current commands, but that evidence does not limit arbitrary input.

`lmn_read_terrain_command_core` returns the two packed words, advanced cursor,
comparison flags, and full-word sentinel result. Its register adapter changes
only `AX`, `BX`, `SI`, flags, and the boundary `IP`: it selects `3765/376A` or
`3975/397A`. The stream core starts from `SI=10EB`, preserves caller `CX`,
`DX`, `DI`, `BP`, `ES`, and `SP` on an empty stream, and returns at the sentinel
continuation without consuming the outer caller's return address.

## Piece calls and live state

For each non-sentinel command, the loop makes a near call to the existing
`DrawPackedTerrainPiece` core at `7C67`. The outer call pushes `3768` or `3978`
on the live stack. The stream passes the current data segment and cursor into
the piece core and carries the child's returned `DS`, `ES`, `CS`, `SP`, flags,
register state, and continuation into the next iteration. It does not cache
the initial `DS` or `SI` across a child call.

If the piece renderer stops at a continuation or changes its far return, the
stream exposes that state and stops. After a normal piece return, it consumes
the actual near-return word from live `SS:SP`. A target other than `3768` or
`3978` is exposed before the loop continues. A normal target returns to the
command loop, which reads using the child's live `DS:SI`. The existing
terrain-piece and planar-renderer contracts retain their explicit device,
IRQ, alias, and changed-return seams; this module does not stub those children.

## Code mutation remains a separate domain

The native loop, like its currently tested child cores, requires the decoded
instruction bytes to remain intact during the call. Data and saved-return aliases
are covered; stacks that overwrite executable instructions remain unresolved.
This is a precondition of the present C domain, not a conclusion that code aliases
are impossible in every incoming state. At canonical load1010, the initial stack
frame244E begins beyond the static image and cannot reach either loop through a
16-bit stack offset, but broader SS ownership still needs to be established.

The fresh main-image static inventory currently contains15,392 decoded sites
and no explicit MOV/POP destination SS. Its five PUSH SS sites are044A,0456,
066A,2864 and8113 (each byte16). This narrows the known stack-ownership
investigation; it does not establish a whole-program invariant across UNKNOWN
bytes, protected execution views, overlays or external providers.

There is a concrete constructed counterexample: `SS=CS`, `SP=376B` makes the
outer CALL store `3768` at code3769, then the child's saved SI changes the opcode
at3768. After the otherwise normal child return, the next bytes are `10 68 37`
(`ADC`), rather than the original loop JMP. Redraw has the analogous397B/3978
alias. `tests/terrain_code_alias.py` executes the original identified children
and stops before those modified instructions. This original-only evidence is
excluded from C coverage. The native stable loop must not be used to interpret
that modified instruction stream; future caller work must retain this seam.

## Bounded checks

`tests/terrain_commands.py` checks both original read/branch spans against the
native core and adapter. Its 449 cases cover `AX` values `0000`, `7FFF`,
`8000`, `FFFE`, and `FFFF`; varied `BX`; initial `AF`, `IF`, and `DF`; command
cursor wrap at `FFFF..FFFC`; `DS=FFFF` physical wrapping; and reads aliasing
the loaded instruction bytes through both the same and neighboring segments.
Twenty-four separate bounded original runs check both entry `MOV SI` sites at
loads `1010`, `1213`, and `2345`. The suite covers all seven reader sites in
each loop and all four branch edges. It detects three compiled reader mutants:
reversing the packed horizontal bytes, treating any `AH=FF` as EOF, and
advancing `SI` by two. It uses `run_bounded` with a 180-second timeout, a 512
MiB process limit, and a 768 MiB process-tree commit limit. Callback traces
stop at 64 RAM events; exhaustion is a failed run, not a mismatch.

The separate unit regression `tests/test_terrain_command_vga.py` adds24
original-versus-native adapter comparisons with DS=9EF2, SI=10EB: the four
command bytes are device reads at physical A000B..A000E. VGA read maps0/3
provide bytes that differ from canonical RAM and all other planes. Both
entries, both DF values, ordinary/FFFE/FFFF commands, all registers, defined
flags, exact read order, full RAM, device state, latches and untouched planes
are checked. Each run stops before the child/sentinel target executes. The
worker has a60-second timeout and256 MiB process/512 MiB tree ceiling. These
24 auxiliary comparisons are separate from the primary differential report
and its coverage totals; they do not broaden arbitrary provider guarantees.

The full loop-to-renderer connection is tested separately from this prefix
suite in `tests/terrain_stream.py`. Its campaign contains all 80 pinned LEVEL
streams at both entries, paired with the matching GROUND metadata and constructed
source pixels, using the visible 1664 by 164 layout. No stream is shortened and
no viewport is reduced for this campaign. The existing 7C67 suite separately
checks all 320 supplied terrain metadata records.

These fixtures copy each pinned command sequence through its first fullFFFF
sentinel. The sentinel's otherwise unused BX payload is constructed as57AD;
the independent reader suite separately varies that payload. The fixtures are
constructed routine states, not initialized game-memory snapshots.

Constructed stream cases compare both the adapter and logical core, including
empty streams, all eight packed control values, aligned and shifted draws,
both DF directions, stack wrapping, 401 commands, and changed return boundaries.
At `SS=DS, SP=6710`, an eight-pixel shifted scratch row can replace the body's
saved DS with `0018`; the next command must use that returned segment. At load
`0310`, `SS=DS, SP=A94D`, shift three preserves the child's far CS while the
saved-height byte changes restored SI to `1004`. The following sentinel is read
there. These are constructed alias witnesses, not normal level-loading states.
Another alias at `SP=66FC` replaces the piece's near continuation with `0010`;
the stream stops before executing that address. The two extra compiled mutants
cache the initial DS or hide this changed near return. Resource exhaustion cannot
count as mutation detection.

The campaign uses two disposable workers under one Windows job capped at
768 MiB total commit, with a 384 MiB per-worker cap and 300 seconds per case.
Its coordinator has a four-hour deadline. Whole-bus traces hash ordered event
values and retain at most eight million phase-defined flags/masks. VGA event
order is hashed in constant space, capped at three million events; all device
access flags are also checked through the full bus trace. Every ordinary body
gets an independent whole-plane expectation before its original far return.
The final report is written only after every case and mutation passes and all
input hashes remain unchanged. Prefix evidence and a partial campaign do not
constitute a fresh full-stream coverage report.

The oracle still reads live CS, IP and flags at every instruction. Its pinned
Unicorn register-batch binding reuses three scalar buffers rather than rebuilding
Python register wrappers for each read. Each oracle call first checks this ABI
against the public register API; an unavailable binding, API error or disagreement
fails verification. Static mnemonics, sizes and RETF membership are cached; no
instruction sites, event flags, bus accesses or independent plane checks are
sampled or omitted. `tests/test_oracle_registers.py` checks changed live register
values, flags and failing bindings separately from translated-code coverage.

Incoming branches into a stop-before continuation are observed edges; the
destination is not an executed instruction site. The four original-only
regressions in `tests/test_terrain_stream_boundary.py` check empty/nonempty
streams at both entries, including the sentinel branch and the loop-back edge.
The bounded `build/terrain-stream-progress.json` journal retains completed case
diagnostics even if the final gate fails. It is explicitly not an acceptance
report and cannot skip executions or supply coverage totals.

Passing this domain does not establish producer allocation bounds, arbitrary
malformed-stream termination, device/IRQ scheduling, or the wider `36B6`/`394F`
caller contracts. Their remaining object drawing uses additional record fields
and live saves. The 378A copy now also exposes a bus-aware core, verified in
134 original comparisons including planar source/destination and provider-backed
ES/RET reads. Compose that API when connecting397A..39CD; retain its finite
provider and intact-code domains. See object-graphics-bus.md.
