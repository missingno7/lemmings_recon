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

Twenty-five original routine entries now have verified C11 cores: two checksums, thirteen DAT
resource/decoder/file/read/cache routines, a raw-resource reader, a resource RLE
decoder, four special-resource VGA strip entries, their connected setup caller and
three PC-speaker helpers, totaling 1,704 original
code bytes.
The DAT suite preserves wrapping counts and live stack aliases; see [DAT C](docs/dat.md).
The sound suite compares registers, full memory, flags and port traces;
see [PC-speaker C](docs/pcspeaker.md).

The complete DAT read wrapper now has bounded contracts for direct DOS reads,
cache creation and cache hits: 45 cases cover 106 original instruction sites,
including ignored cache-fill errors, saved-frame aliases and provider DF effects.
The complete wrapper now has a verified C11 core; see [DAT read contracts](docs/dat-io.md).

The integrated section decoder directly calls these native cores. Forty-eight
cases include the original sound sections through direct reads and both cache
paths, all token forms, malformed headers and both fatal read exits;
see [DAT section C](docs/dat-section.md). Resource callers and fatal
cleanup still require translation. Filename preparation, cache selection and
startup disabling are now verified in 305 cases; see [DAT cache C](docs/dat-cache.md)
for the preserved padding and last-byte comparison bugs.

File open and attribute/retry wrappers are native in 40 verified cases. The
renderer/input retry callee and fatal print path remain explicit unported
boundaries; see [DAT file C](docs/dat-files.md).

The resource caller now connects check/open/decode through direct native core
calls. Twenty-four integrated cases retain the original ignored-open-carry and
saved-DS behavior; see [DAT resource C](docs/dat-load.md). Higher resource ownership,
retry rendering/input and fatal cleanup remain open.

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

## Reproduce

Supply the original files privately in assets; metadata/inputs.json pins their hashes.
Use Python 3.12 with requirements.txt, NASM/NDISASM and a C11 GCC compiler. The recorded
Windows tool locations/hashes are in metadata/toolchain-lock.json. Set
LEMMINGS_NASM, LEMMINGS_NDISASM or LEMMINGS_CC when tools are elsewhere, and review
the lock deliberately rather than bypassing it.

```powershell
.venv\Scripts\python.exe tools\unpack.py
.venv\Scripts\python.exe tools\verify.py
.venv\Scripts\python.exe tools\sound.py
.venv\Scripts\python.exe tools\protection.py
.venv\Scripts\python.exe tools\indirect.py
.venv\Scripts\python.exe tools\interrupts.py
.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.venv\Scripts\python.exe tools\difftest.py
.venv\Scripts\python.exe tools\coverage.py
.venv\Scripts\python.exe tools\where.py InitializeCodeChecksum --disasm 16
.venv\Scripts\python.exe tools\graph.py InitializeCodeChecksum
```

On this machine the Windows Store python alias is unusable. A local .venv was created
using the available Codex Python 3.12 runtime and populated with pinned Capstone and
Unicorn wheels. MSYS NASM requires execution outside the restricted sandbox because
its shared-object initialization fails inside it. GCC runs normally.

## Files and workflow

- src: maintained NASM oracle; build uses no original binary inclusion.
- c: original routines translated to C11, generated symbol offsets.
- tests: bounded Unicorn-vs-native tests and static tool regression checks.
- tools: static unpack, build/verify, recursive discovery, symbols and reports.
- metadata: identity pins, oracle footer/relocations, symbols, evidence and regions.
- docs: representation boundaries, findings, contracts and unresolved work.
- host: reserved SDL3 boundary, no implementation yet.

tools/verify.py never regenerates source or accepted hashes. tools/reconstruct.py
is an explicit bootstrap generator and overwrites generated ASM; preserve hand
annotations before running it. tools/inventory.py is a one-time evidence import,
not part of verification. Neither command should be used to bless unexplained drift.
The checked-in ledger and source do not require neighboring projects to build.

Symbols may be changed with tools/rename.py, data names added with tools/define.py,
and C offsets regenerated with tools/symtab.py. Always run the exact verifier next.
Every ledger symbol is also checked by assembler address assertions.

Original assets, generated binaries and tool binaries are gitignored and never
published by this project. No remote repository has been created or pushed.
