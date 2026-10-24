# Purpose

Understanding is the deliverable. The byte-exact semantic ASM is the permanent
specification of the pinned DOS VGA Lemmings executable and its executable
dependencies (protected views, AdLib, Tandy and PC-speaker images). Portable C11
and the SDL3 host are derived implementations and downstream verification:

```
VGALEMMI.EXE + sound images <- byte exact -> semantic ASM <- bounded differential tests -> C11 -> native/SDL3
```

Priorities: 1. exact identity (absolute); 2. semantic clarity for a translator;
3. game/platform separation where the program really has it; 4. historical
resemblance (secondary). Measure progress by how much more of the actual game is
understood and faithfully reconstructable, not by bytes, suites or test counts.
Primary configuration is DOS VGA + AdLib. PC speaker, Tandy, joystick and every
other original path stay inventoried and are eventually understood; they never
block the primary port and are never discarded.

# Execution policy

Static analysis is the default. Never boot or play the original for discovery; no
gameplay bots, no replay exploration. Run original code (the unpacker or one
routine at a known boundary with constructed state) only to settle a named
question static work cannot. Human-recorded BizHawk/DOSBox-X replays will later be
supplementary end-to-end smoke; they never replace static or routine evidence.

# The loop

1. Pick the uncertainty that would force a C translator to guess
   (docs/next-work.md): an unknown function or edge, record/table, resource format,
   state transition, sound/render algorithm or behavior-affecting platform effect.
2. Investigate: `tools/where.py ADDR --disasm N`, `tools/graph.py ADDR --asm`,
   grep. Use `flowstate.py`, `indirect.py`, `protection.py` when they answer that
   concrete question; they are not mandatory stages.
3. Improve the source, in order of value: classify UNKNOWN bytes; state, records,
   fields, tables, dispatch, buffers, state machines; routine contracts (inputs,
   results, flags/registers/segments callers consume, side effects, shared tails,
   nonlocal exits, interrupt context); platform vs game; local labels last.
4. `tools/verify.py` (about 8 s). If it fails, fix or revert before continuing.
5. Translate understood, coherent operations into C; check them with the affected
   bounded suite. Compose already-understood children; do not re-prove them.

There is no separate audit or proof stage between these steps. When a cluster's
translation readiness is not obvious, put one READY/CONDITIONAL line naming the
bounding dependency beside its ASM contract.

# Classification

Classification (what kind of bytes) and semantics (what they mean) are separate.

- Data: classify when evidence shows the kind: readers/writers, a consumer's
  stride or index arithmetic, or self-evident content (DOS `$` strings, text,
  scancode/character maps, zero storage that every decoded accessor writes before
  reading). Unread bytes inside a proven structure belong to that structure. Data
  with no identified reader is still data: give it a conservative name (`Unused*`,
  `*Slack`) and say "no reader identified"; its meaning may stay open.
- Code: only with a proven incoming edge (direct, table, vector, overlay load).
  Code-looking bytes without one stay UNKNOWN unless their content proves data.
- UNKNOWN only where the kind genuinely cannot be decided yet (for example
  protected or self-modified bytes whose runtime decode is unresolved). A zero
  fill alone, or one consumer of one field, never classifies a long run.
- Never call unresolved code dead or unreachable. Keep overlapping roles explicit.

# Exceptional behavior and blockers

Every behavior is in one class: proven from original code; platform-conditional
under metadata/platform-profile.json; characterized original race, overflow,
alias or corruption; or unresolved. A characterization states cause, trigger,
write order, affected memory and resulting control-transfer expression. Then:

- A corrupted-control escape ends the specification at "control transfers to
  CS:F(state) with the characterized machine state". Do not decode bytes reached
  only that way or follow arbitrary later machine states. Natively it is an
  explicit runtime limitation, never success, a no-op or invented recovery.
- Corruption that continues through ordinary code is preserved by translating
  that ordinary code over the same memory layout. It needs no separate proof of
  every later state, damaging writer or surviving count.
- Not blockers: arbitrary interrupt arrival schedules, unbounded stack/memory
  corruption outcomes, hypothetical DF/segment/register states with no legitimate
  producer, re-investigation of an already characterized race. Study them only to
  resolve a concrete semantic ambiguity of the legitimate program.
- Real blockers: unknown legitimate callback or dispatch targets, unresolved
  ordinary control flow, missing behavior-affecting data or format knowledge.

# Fixed constraints

- Read docs/executable.md before changing the oracle. Never modify assets/,
  metadata/inputs.json or neighbouring projects; never commit assets, binary
  images, runtime dumps or downloaded tool binaries; never import the legacy
  interpreter.
- No INCBIN or byte includes. Encoding exceptions explain the instruction; never
  mask differences.
- The symbol ledgers own names and offsets (`rename.py`, `define.py`; `symtab.py`
  regenerates C headers). Bootstrap generators (`reconstruct.py`,
  `sound.py --generate`) never overwrite maintained source.
- Preserve original wrap, flags, segment effects, self modification, shared tails
  and bugs, documented at their sites. No shadow game-state copies: C works over
  the canonical original memory layout.
- Comments explain purpose, contracts, state meaning, hardware effects, quirks and
  real uncertainty in plain readable English. No per-instruction narration, test
  checkpoint narratives or audit evidence codes in maintained source.

# Verification

- ASM names/comments/classification: `tools/verify.py`, plus static/accounting
  tests only if their inputs changed.
- C change: the affected suite, `tools/difftest.py SUITE` (`--plan`, `--list`).
  A connected change adds only the directly affected parent's handoff checks.
- Changed original extraction/unpacker contracts: `tools/verify.py --contracts`.
- `tools/difftest.py --all` plus `tools/coverage.py` is explicit aggregate
  acceptance only. Comment or metadata edits never require rerunning campaigns;
  old reports remain historical until a genuinely required run refreshes them.
- Choose mutation witnesses by distinct contract risk, not quota. Do not widen
  artificial provider or machine-state domains to gain tests. New suites use
  tests/verification.py; no new CPU engines.
- Native safety: run native suites only through difftest.py or
  `bounded_process.run_bounded` with a timeout and process-tree commit limit; keep
  callback traces bounded; timeouts and limit exhaustion fail (never count as a
  detected mutant); reap workers; temporary build dirs stay under build/ via
  `temporary_build_directory(..., parent=BUILD)`. Compile-only mutation preflights
  use `cbuild.build()` with numeric IDs (or `-Wundef -Werror`) and keep argv/exit.

# Progressive nativization

We are not building a DOS emulator. Model DF, segments, stack, interrupts,
BIOS/DOS, VGA and timing only as far as they affect game state and output, then
replace them with native equivalents once the observable effects and ordering are
shown equivalent; every simplification cites the original dependency. Never add
locks, bounds checks, fixes or reordered writes; model characterized out-of-range
accesses explicitly instead of relying on C undefined behavior. A platform
substitution names the original service it bypasses, its contract and whether it
is equivalent, altered or unverified, and the bypassed obligation stays visible
beside the ASM. Never fabricate success.

The platform models one declared real machine (host/README.md, Declared
machine). Derive device answers and timing from that machine's registers and
datasheet behavior; never pick values, schedules or overrides because a run then
looks right, and never compensate one invented answer with another. Devices run
continuously in emulated time (raster, PIT, OPL, scanout), not only when the CPU
touches them; delay loops, port-read counts and raster waits are part of the
original's timing and stay observable. A reference model in a test must not
simply copy the host's assumption it is meant to check.

# Parallel workers

Workers take independent semantic problems with disjoint file ownership and edit
only files they own for the task. Shared metadata (hints.json, symbols.json,
regions) comes back as patch files under build/proposals/; the supervisor rules
on overlaps, integrates, runs the exact gate and commits. A worker reports the
uncertainty it resolved, its evidence, what remains uncertain and the affected
C/tests. Audits, test infrastructure or documentation are not worker products by
themselves.

# Documents

Status: docs/completeness.md (`tools/coverage.py --inventory`). Priorities:
docs/next-work.md. Freeze bar and completeness measures: docs/semantic-audit.md.
History: docs/convergence-history.md. Subsystem docs describe contracts, not
progress. One source of truth: never copy counts or narratives between documents;
every tool, report and metadata file needs a current consumer.
