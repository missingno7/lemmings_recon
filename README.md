# Lemmings DOS VGA reconstruction

Reconstruct the pinned VGALEMMI.EXE as exact, readable semantic ASM, derive
behaviorally equivalent portable C11, then connect native platform services and
SDL3. The original binary is the final oracle. The native game will execute C;
original instruction execution is confined to bounded verification.

**The complete game is not runnable yet.** Exact binary identity, classification,
semantic readiness, C ranges, differential evidence and whole-game integration
are separate. See the reproducible [current status](docs/completeness.md),
[freeze bar and completeness measures](docs/semantic-audit.md), and
[next work](docs/next-work.md). Historical counts are archived in
[convergence history](docs/convergence-history.md).

## Development commands

```powershell
.venv/Scripts/python.exe tools/verify.py
.venv/Scripts/python.exe tools/coverage.py --inventory
.venv/Scripts/python.exe tools/where.py 03E7 --disasm 24
.venv/Scripts/python.exe tools/graph.py 03E7 --asm --tree --depth 1
.venv/Scripts/python.exe tools/graph.py 03E7 --asm --bottom-up
.venv/Scripts/python.exe tools/difftest.py --list
.venv/Scripts/python.exe tools/difftest.py SUITE --plan
.venv/Scripts/python.exe tools/difftest.py SUITE
```

`--asm` shows original CFG bodies independently of C-tested ranges. The default
graph view retains native scopes. The fast exact gate is the normal ASM edit
loop; affected bounded suites check C changes. Full original contracts use
`verify.py --contracts`; aggregate C acceptance additionally requires matching
reports from the complete `difftest.py --all` campaign and `coverage.py` without
`--inventory`. Routine-local evidence does not establish a full game or timing.

## Maintained source

- `src/`: byte-exact ASM with UNKNOWN and encoding exceptions explicit; separate
  executable sound and protected-state views. Bootstrap output never overwrites it.
- `metadata/symbols.json`: authoritative names, offsets, aliases and C extents;
  classifications and conditional CFG evidence have separate pinned inventories.
- `c/`: existing portable C over canonical original memory, with boundary adapters.
- `tests/`: retained differential suites and the shared verification engine.
- `tools/`: exact build/discovery/symbol tools and bounded suite orchestration.
- `docs/`: executable/architecture/contracts, current status and current roadmap.

The working method is in [AGENTS.md](AGENTS.md).
[Executable scope](docs/executable.md) pins the packed EXE, decompressed/relocated
representations and three loaded sound images. [Source map](docs/bottom-up.md)
records physical module ownership; [architecture](docs/architecture.md) and
[verification](docs/verification.md) explain native boundaries and evidence.
All original assets and historical tools are private local inputs. Never boot
the game for discovery, modify assets or neighboring projects, import the old
interpreter, classify unexplained bytes speculatively, or erase original quirks.
