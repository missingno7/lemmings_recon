# Reconstruction rules

Target only the pinned DOS VGA Lemmings executable and its executable dependencies.
Read docs/executable.md and docs/next-work.md before changing the oracle.
Priority: static identity, readable exact ASM, complete code/data/CFG accounting,
then portable C11 and bounded differential tests; SDL3 comes last.
Never boot the game for discovery. Bounded execution of the unpacker or identified
routines with constructed state is permitted for independent verification.
Do not modify assets or neighboring projects; never commit assets, binary images,
runtime dumps, or downloaded tool binaries. Do not import the legacy interpreter.
Keep UNKNOWN bytes explicitly unresolved. No INCBIN in reconstructed ASM. Encoding
exceptions must explain the instruction; no masking unexplained differences.
The symbol ledger owns names and offsets. Preserve original wrap, flags, segment
effects, self modification, shared tails and bugs. No shadow game-state copies.
Run tools/verify.py and relevant tests after changes. Coverage of bytes, translated
code and executed instructions are separate. Never claim unresolved code is dead.
The default verifier is the fast identity/ASM/relocation gate. Run
tools/verify.py --contracts for the full original-only behavioral campaign before
aggregate coverage acceptance, or when its shared contracts change. Use the
affected bounded native suites with tools/difftest.py SUITE [SUITE ...] during
development; --plan previews limits and --list lists suites. The complete native
campaign requires tools/difftest.py --all; do not restart the whole
campaign merely to refresh an unrelated edit. A retained report is accepted only
when its scope and input hashes match; file preservation does not renew evidence.
Run native differential suites through tools/difftest.py or the run_bounded helper
in tools/bounded_process.py with a timeout and Windows process-tree commit limit. Keep native
callback traces bounded; ctypes callback exceptions cannot stop a C loop.
Timeout, memory-limit or access-budget exhaustion fails verification and must not
count as a detected differential mutant. Reap workers and remove owned temporary
DLL directories even after failure. Do not launch unbounded native mutant calls.
Keep compile and DLL temporary directories under build/ with
tools/bounded_process.py's temporary_build_directory(..., parent=BUILD).
Only delegate independent C clusters after static boundaries are reliable. Workers
must report addresses, bytes, cases, branches, quirks, dependencies and regressions.
For compile-only mutation preflights, use tools/cbuild.py's build() with numeric
mutation IDs, or include -Wundef with -Werror and retain effective argv/exit for
every variant. Placeholder macro values and artifact names are not build evidence.

# Bottom-up convergence

Read docs/bottom-up.md when selecting the next region. Use fresh tools/graph.py
--tree and --bottom-up views; TESTED C domains retain their platform/fatal seams.
Choose the uncertainty that would force a future C translator to guess. Prioritize
state ownership, record fields, tables, initialization, segment/flag contracts and
shared tails before local-label cleanup. Keep contracts beside the ASM and names
in the ledger. Refine physical modules without changing byte order or classifications.
Translate an independently understood leaf, then connect and recheck its parent.
Carry original live DS/ES/SS effects explicitly; do not copy Pre2's ES-only model
without proving the same contract here. Bootstrap generation must not overwrite
maintained semantic source. Current dependency order is recorded in docs/next-work.md.

# Shared verification and native destination

New focused suites use tests/verification.py for original instruction execution,
canonical bus access, guarded native callbacks and state comparison. Add a shared
capability when required; do not add another bespoke engine for a tiny leaf.
Keep fixture providers and independent game expectations outside that engine.
Migrate affected existing consumers incrementally and preserve their contracts.
Choose mutation witnesses by distinct contract risks, not a fixed quota.
Prefer a connected leaf/parent subsystem milestone over isolated byte gains.
The destination is portable C11 plus explicit platform services and SDL3; no
intermediate DOS-C target is required. Every behavior-affecting code dependency
must be explained and implemented in C; unsupported alternatives do not count as
complete. See docs/architecture.md and docs/verification.md for the native smoke
test and separate evidence dimensions.
