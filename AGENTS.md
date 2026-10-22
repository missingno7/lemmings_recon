# Purpose

Understanding is the deliverable; C and SDL3 are derived implementations. The
goal is the `asm-semantic-oracle-v1` milestone defined in docs/semantic-audit.md:
a complete, byte-exact, readable ASM specification from which C follows without
guessing. Measure progress by uncertainty closed (evidence-based classification,
closed control flow and dispatch domains, data ownership/lifetimes, caller-
observable contracts), not by C bytes, suite counts or host functionality.
Native C and the host are downstream verification. Their failures report
findings; their success never closes static obligations or chooses priorities.
Primary configuration is DOS VGA + AdLib. Complete reconstruction still accounts
for PC speaker, Tandy, joystick and every other original path; inventory them,
never discard them. Do not play the original, build gameplay bots or explore by
replay. Human-recorded BizHawk/DOSBox-X replays will later be supplementary smoke.

# Reconstruction rules

Target only the pinned DOS VGA Lemmings executable and its executable dependencies.
Read docs/executable.md and docs/next-work.md before changing the oracle.
Priority: static identity, readable exact ASM, complete code/data/CFG accounting,
then portable C11 and bounded differential tests; SDL3 comes last.
Never boot the game for discovery. Bounded execution of the unpacker or identified
routines with constructed state is permitted for independent verification.
Do not modify assets or neighboring projects; never commit assets, binary images,
runtime dumps, or downloaded tool binaries. Do not import the legacy interpreter.
Keep UNKNOWN bytes explicitly unresolved. Classify only from combined evidence:
initialization, readers, writers, execution paths, overlays, aliases and
lifetime; one named consumer or a zero fill never classifies a whole run, and
"not reached by the host" never means dead or unreachable. No INCBIN in reconstructed ASM. Encoding
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
Only delegate independent, bounded investigations or C clusters after static
boundaries are reliable. Workers report the uncertainty resolved, original
evidence, state/contract changes and regressions; derive counts from the ledger
and reports instead of duplicating checkpoint bookkeeping.
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
Choose a coherent semantic operation, not the next CALL instruction or byte gain.
Translate a leaf when it is the missing dependency; compose already-understood
call sequences together. Parent checks concentrate on handoffs and shared state;
do not repeat each child's exhaustive matrix without a new interaction risk.
Carry original live DS/ES/SS effects explicitly; do not copy Pre2's segment/stack
assumptions without proving the same contract here. Bootstrap generation must not overwrite
maintained semantic source. Current dependency order is recorded in docs/next-work.md.

# Semantic readiness before C expansion

Use the scoped gate and matrix in docs/semantic-audit.md. READY requires known
entry/control flow, relevant state owners/producers/consumers, caller-observed
inputs/results/side effects, shared-tail/indirect dependencies and platform/IRQ
seams, with remaining uncertainty stated. CONDITIONAL permits an explicit bounded
domain; NOT READY means resolve the semantic blocker first. TESTED and decoded
leaf status are not readiness. Do not demand global UNKNOWN closure before any C.
For the next cluster, write its short readiness decision beside its ASM contract
before implementation. Move discovered semantics back to ASM/ledger in that batch.
Distinguish real game/platform behavior from raw-entry oracle transport. Preserve
existing alias/flag/stack tests, but do not widen supported artificial provider or
machine-state domains merely to obtain more tests. Narrow native contracts only
after proving caller/lifetime invariants; never erase an observable quirk.

# Static workstreams and integration

Static analysis is the default method; bounded original execution answers one
named question. Parallel workers take independent semantic dependencies (a
frontier's writer domain, a structure's lifetime, a driver's grammar), not byte
quotas. Workers edit only comments in ASM files they own for that task and
return names, classifications and hints as an integration patch with evidence,
resolved dependencies, remaining uncertainty and affected C/tests. The
supervisor alone applies shared ledger/hints/regions/image_tail changes, rules
on overlapping findings and runs the exact gate. A resolution must make the
program more understandable and remove a translator guess; renaming literals or
recreating historical layout is not progress by itself.

# Minimal simulation and progressive nativization

We are not building a DOS/PC emulator. For DF, segments, interrupts, BIOS/DOS,
VGA and timing: first establish their actual effects on game state and
execution, then model only what preserves those effects in the supported
configuration, proving invariants from original code and declared platform
contracts. No arbitrary hardware states, hypothetical interleavings or
unsupported DOS behavior for completeness' sake; but genuine quirks and
reachable edge cases stay, and unresolved dependencies stay explicit. Replace
verified simulated services with native equivalents without changing game
semantics. The C becomes a clean native engine, not a permanent x86
transliteration; every simplification cites the original dependency it rests on.
Results are classed unconditional (original code), platform-conditional (named
profile assumptions listed) or unresolved; a platform profile never closes
interrupt interleavings, stack aliases, callback writers or races.

# Platform substitutions

A host or provider substitution names the original service or region it
bypasses, its input/output/memory/flag/segment contract and its machine
configuration. The bypassed original obligation stays visible beside the ASM.
Classify each as a platform substitution with equivalent observable effect,
omitted/altered original game behavior, or unverified equivalence. Muted sound,
media-probe policies, IRQ-at-poll scheduling and unbound callbacks define
supported integration domains; they never complete protected code, sound engines
or unrestricted interrupt interleavings. Never fabricate success or results.

# Shared verification and native destination

New focused suites use tests/verification.py for original instruction execution,
canonical bus access, guarded native callbacks and state comparison. Add a shared
capability when required; do not add another bespoke engine for a tiny leaf.
Keep fixture providers and independent game expectations outside that engine.
Migrate affected existing consumers incrementally and preserve their contracts.
Choose mutation witnesses by distinct contract risks, not a fixed quota.
Prefer a connected leaf/parent subsystem milestone over isolated byte gains.
ASM names/comments/offset expressions require the fast exact gate and affected
static/accounting checks. If emitted bytes and C behavior do not change, do not
rerun native campaigns just to renew coarse metadata/comment hashes. Their old
reports remain historical until a genuinely required run refreshes them.
Local C changes use the affected suite; connected changes add the directly
affected parent; shared behavior uses affected consumers and --contracts when
original contracts change; --all remains explicit aggregate acceptance.
Current quantitative status lives only in docs/completeness.md, reproducible with
tools/coverage.py --inventory. Current priorities live only in docs/next-work.md;
old checkpoint narratives belong in docs/convergence-history.md. Subsystem docs
describe contracts and recorded domains, not perpetual freshness or another total.
The destination is portable C11 plus explicit platform services and SDL3; no
intermediate DOS-C target is required. Every behavior-affecting code dependency
must be explained and implemented in C; unsupported alternatives do not count as
complete. See docs/architecture.md and docs/verification.md for the native smoke
test and separate evidence dimensions.
