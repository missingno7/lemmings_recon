# Lemmings DOS VGA reconstruction

Static reconstruction of the pinned original VGALEMMI.EXE, followed by a portable
C11 translation verified against the original instructions. No game emulator or
runtime lifting is used in the native architecture.

The first milestone reconstructs all 82,906 unpacked bytes exactly and verifies 63
relocations against bounded execution of the original PKLITE stub. Recursive
discovery and byte classification are partial. This is **not a complete recovered
program or native game**. See [completeness](docs/completeness.md) and
[next work](docs/next-work.md) for the precise frontier.

The next milestone adds exact static reconstructions of both executable sound
assets: AdLib (22,125 bytes) and Tandy (21,702 bytes), independently checked against
the original DAT decoder. Total reconstructed image bytes: 126,733. Driver
translation and command-dispatch closure remain open; see [sound drivers](docs/sound-drivers.md).

State-specific protection ASM now recovers the disk-check stream and INT1 handler:
401 additional instruction sites, checked against bounded original-handler execution.
See [protection](docs/protection.md) for representation boundaries and open contracts.

The static CFG also records 18 conditional callback edges. Bounded caller tests
check live pointer routing and saved registers; write/alias domains remain open.
See [callback evidence](docs/indirect-callbacks.md).

The PC-speaker executable payload in MAIN.DAT adds a fourth component image:
127,491 exact ASM bytes in total. Installed IRQ handlers and external timer-chain
returns now have bounded checks; see [interrupts and overlay](docs/interrupts.md).

C11 translations cover checksums and DAT
resource/decoder/file/read/cache routines, a raw-resource reader, a resource RLE
decoder, four special-resource VGA strip entries, their connected setup caller,
the decimal helper, connected resource selection, four object-record helpers,
their connected setup span, VGA clear/layout, two drawing callers, three minimap
routines, two clipping/dirty-cell leaves, their scoped drawing preparation span,
destination geometry/shared dispatch and four source-row spans,
all twelve planar drawing bodies and their complete normal-entry connection,
the packed terrain-piece caller and three PC-speaker helpers.
Additional scoped cores connect cleanup/resource failure paths, display setup,
status and start programming, and the glyph/text-stream producers. See
[bottom-up connections](docs/bottom-up.md) and [text records](docs/text-stream.md).
The simulation tree now includes the live [interaction-pattern restore](docs/entity-pattern.md)
and [pixel address/mask preparation](docs/entity-pixel.md) leaves, with original
wrapping, segment and stack-alias contracts.
The complete terrain campaign has scoped acceptance for all 80 pinned LEVEL
streams at both entries. Aggregate C coverage still requires fresh affected
reports; see [terrain evidence](docs/terrain-stream.md).
The DAT suite preserves wrapping counts and live stack aliases; see [DAT C](docs/dat.md).
The sound suite compares registers, full memory, flags and port traces;
see [PC-speaker C](docs/pcspeaker.md).

The complete DAT read wrapper now has bounded contracts for direct DOS reads,
cache creation and cache hits: 45 cases cover 106 original instruction sites,
including ignored cache-fill errors, saved-frame aliases and provider DF effects.
The complete wrapper now has a verified C11 core; see [DAT read contracts](docs/dat-io.md).

The integrated section decoder directly calls these native cores. One hundred twenty-eight
cases include all80 pinned level sections and the original sound sections through direct reads and both cache
paths, all token forms, malformed headers and both fatal read exits;
see [DAT section C](docs/dat-section.md). The scoped resource and fatal-cleanup
connections are recorded in [next work](docs/next-work.md). Filename preparation, cache selection and
startup disabling are now verified in 305 cases; see [DAT cache C](docs/dat-cache.md)
for the preserved padding and last-byte comparison bugs.

File open and attribute/retry wrappers are native in 40 verified cases. The
renderer/input retry callee remains an explicit unported boundary; the fatal
printer has a separate [native connection](docs/file-error.md); see [DAT file C](docs/dat-files.md).

The resource caller now connects check/open/decode through direct native core
calls. Twenty-four integrated cases retain the original ignored-open-carry and
saved-DS behavior; see [DAT resource C](docs/dat-load.md). Higher resource ownership,
retry rendering/input and platform ownership remain open.

The raw-resource open/read/close primitive has 46 differential cases, including
short reads and all three error exits; see [raw resource C](docs/resource-raw.md).

The resource RLE core preserves live overlap, DF and the original repeat-byte
corruption during segment rollover, verified in 303 cases including sixteen original
special-resource streams;
see [resource RLE C](docs/resource-rle.md).

The four special-resource VGA strips now have a verified native core, with 28
cases checking plane contents, port/MMIO order, flags and live stack aliases;
see [special VGA strips](docs/special-blit.md). The native VGA backend and higher
graphics ownership remain open.

The special graphics setup caller now connects metadata, four RLE/strip pairs
and two normal graphics DAT sections through native cores. Twenty integrated
cases include all four VGASPEC inputs and paired VGAGR sections, with independent
metadata/plane checks; see [connected graphics setup](docs/special-setup.md).
Upstream selection/allocation and full level setup remain open.

The VGA clear and drawing layout now connect directly to the 368E initialization
and 36AD tail callers. Their 211 cases preserve live SS/device returns, DF,
truncated drawing geometry and wrapped segment publication; see
[level drawing](docs/level-drawing.md). The layout suite isolates documented
Unicorn RETF artifacts instead of copying them into the native contract.

The minimap sample, row and column now share direct native cores and a dedicated
ASM module. Their 178 cases include full thirteen-column cycles, live stack/cursor
aliases and independent mode1/plane footprints. Exhaustive native population
vectors are counted separately from original comparisons; see [minimap](docs/minimap.md).

The planar clipping and dirty-cell leaves now compose directly in the 882D
preparation span. Their 2,227 original/native cases preserve live field/save/return
aliases and zero-count quirks. These preparation-only suites keep the original
8822 prologue separate; the full-entry suite below translates it. See [drawing preparation](docs/drawing-inputs.md).

The destination geometry, shared path selector and four source-row preparations
now compose with those cores. Their 1,057 bounded cases include an independent
640-case mode/shift/reverse/effect matrix and live control aliases. The planar
ASM family is grouped without changing bytes; selected VGA drawing bodies remain
open. See [connected drawing selection](docs/drawing-plan.md).

The aligned opaque VGA body now connects through the native preparation chain.
Its 55 body cases and 776 connected cases preserve all four plane passes,
latch-before-copy order, DF/count wrap, CLI/STI and live stack/segment/return
aliases. Remaining drawing variants stay open; see
[aligned opaque drawing](docs/aligned-opaque.md) and
[connected rendering](docs/drawing-render.md).

The protected 953E, read-mask 969C and mask effects 9737/97A4 now connect through
the same preparation chain. Their 90 standalone and 226 connected cases preserve
plane-3 protection, explicit byte-port reads, live saved DX/DS and the original
20/40 row-cursor asymmetry. The complete entry also connects shifted bodies. See
[protected drawing](docs/aligned-protected.md), [read-mask drawing](docs/aligned-read-mask.md)
and [mask effects](docs/aligned-mask-effects.md).

The shifted 20/40 effects now add 54 standalone and 349 preparation connections.
They retain DF-sensitive scratch copies, forward SHR/RCR carry chains, the extra
output byte, live DS/ES/SS saves and unchecked count/shift wraps. Their masks are
also checked with independent packed-bit calculations; see
[shifted effects](docs/shifted-mask-effects.md).

The other four shifted bodies now pass 103 standalone cases. The actual 8822
entry composes its native prologue, preparation, all twelve bodies and no-draw
far return in 2,147 cases, preserving live scratch/stride/save aliases. Earlier
APIs keep their scopes. UNKNOWN bytes, source/mask allocation domains, shared
incoming states and IRQ/device ownership remain open; see
[complete drawing entry](docs/drawing-render.md).

The packed terrain-piece caller at7C67 now uses the native renderer directly.
Its609 bounded connections include all320 supplied GROUNDterrain metadata
records with constructed source bytes, full plane expectations, live savedSI
and changed near/far returns. It adds85 unique C bytes; see
[terrain drawing](docs/terrain-drawing.md).

## Reproduce

Supply the original files privately in assets; metadata/inputs.json pins their hashes.
Use Python 3.12 with requirements.txt, NASM/NDISASM and a C11 GCC compiler. The recorded
Windows tool locations/hashes are in metadata/toolchain-lock.json. Set
LEMMINGS_NASM, LEMMINGS_NDISASM or LEMMINGS_CC when tools are elsewhere, and review
the lock deliberately rather than bypassing it.

```powershell
.venv\Scripts\python.exe tools\unpack.py
.venv\Scripts\python.exe tools\verify.py
.venv\Scripts\python.exe tools\verify.py --contracts
.venv\Scripts\python.exe tools\sound.py
.venv\Scripts\python.exe tools\protection.py
.venv\Scripts\python.exe tools\indirect.py
.venv\Scripts\python.exe tools\interrupts.py
.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.venv\Scripts\python.exe tools\difftest.py drawing_clip display_status --plan
.venv\Scripts\python.exe tools\difftest.py drawing_clip display_status
.venv\Scripts\python.exe tools\difftest.py --all
.venv\Scripts\python.exe tools\coverage.py
.venv\Scripts\python.exe tools\where.py InitializeCodeChecksum --disasm 16
.venv\Scripts\python.exe tools\graph.py InitializeCodeChecksum
.venv\Scripts\python.exe tools\graph.py LoadSelectedLevelResources --tree --depth 3
.venv\Scripts\python.exe tools\graph.py LoadSelectedLevelResources --bottom-up
```

For routine edits, run `tools/verify.py` and the affected bounded tests. The
default gate checks pinned inputs/tools, exact ASM for all four components,
relocations, symbols, static inventories and the bounded unpacker. It writes
`build/static-verification.json`. The longer `--contracts` campaign also runs
the original-only behavioral suites and writes `build/verification.json`;
aggregate coverage requires this full report and fresh native reports. A static
run preserves the full report, whose hashes must still match before acceptance.
The existing `--skip-stub` option omits unpacker execution for a static edit check
and cannot be combined with `--contracts`.

Use `tools/difftest.py SUITE [SUITE ...]` for affected native checks. `--list`
shows all suites and bounds; `--plan` previews a selection without execution.
The complete native campaign requires `--all`. An empty or invalid selection
fails before launching workers. Selected suites retain their existing deadlines,
process-tree memory limits and fail-fast behavior. A selected run is evidence
only for those suites; it does not accept the complete campaign.

On this machine the Windows Store python alias is unusable. A local .venv was created
using the available Codex Python 3.12 runtime and populated with pinned Capstone and
Unicorn wheels. MSYS NASM requires execution outside the restricted sandbox because
its shared-object initialization fails inside it. GCC runs normally.

Native differential suites run in child processes with explicit deadlines and,
on Windows, default 512 MiB process / 768 MiB process-tree commit ceilings.
The focused display/text workers use 384 MiB / 640 MiB limits. The clipping
suite also bounds each callback trace and removes temporary DLLs after failure.
Windows children start suspended until the commit limits are attached, including
before a Python redirector can start its runtime child.
Harness regressions verify runaway-loop termination, allocation rejection and
child cleanup, including failed guard setup; see [clipping verification](docs/drawing-clip.md).

## Files and workflow

- src: maintained NASM oracle; build uses no original binary inclusion.
- c: original routines translated to C11, generated symbol offsets.
- tests: bounded Unicorn-vs-native tests and static tool regression checks.
- tools: static unpack, build/verify, recursive discovery, symbols and reports.
- metadata: identity pins, oracle footer/relocations, symbols, evidence and regions.
- docs: representation boundaries, findings, contracts and unresolved work.
- host: reserved SDL3 boundary, no implementation yet.

tools/verify.py never regenerates source or accepted hashes. tools/reconstruct.py
is a bootstrap generator that refuses the maintained modular layout.
tools/inventory.py is a one-time evidence import,
not part of verification. Neither command should be used to bless unexplained drift.
The checked-in ledger and source do not require neighboring projects to build.

The semantic ASM/resource refactoring and dependency order are documented in
[bottom-up convergence](docs/bottom-up.md). Module end assertions keep layout
fixed; the bootstrap generator refuses to overwrite these maintained modules.

The decimal helper passes 270 native/ASM cases, and resource selection now calls
the native resource cores directly in 59 integrated cases. Live stack/segment
aliases, unchecked indexes, in-place decoding and ignored close carry remain
observable; see [decimal helper](docs/decimal-digits.md) and
[resource selection](docs/resource-select.md). The object graphics-record copy and
type-one coordinate collector now pass 131/159 cases, retaining live copies and
the original default-coordinate bug. See [object records](docs/object-records.md).
The SS interaction-cell writers now pass 123/386 cases. Their four-call native
setup span passes 105 integrated cases, including changed callee return targets;
see [interaction cells](docs/interaction-cells.md). The full setup/drawing callers
and VGA/IRQ ownership remain open.

Symbols may be changed with tools/rename.py, data names added with tools/define.py,
and C offsets regenerated with tools/symtab.py. Always run the exact verifier next.
Every ledger symbol is also checked by assembler address assertions.

Original assets, generated binaries and tool binaries are gitignored and never
published by this project. No remote repository has been created or pushed.
