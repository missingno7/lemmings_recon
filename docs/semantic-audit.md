# Semantic oracle freeze bar and completeness measures

Methodology: AGENTS.md. Current counts: [completeness.md](completeness.md)
(`tools/coverage.py --inventory`). Open blockers and priorities:
[next-work.md](next-work.md). The audits and freeze rules that preceded the
2026-10-23 simplification are archived in
[convergence-history.md](convergence-history.md).

## Freeze bar: `asm-semantic-oracle-v1`

The ASM is frozen as the semantic oracle when all of these hold. `tools/verify.py`
checks the first item; the rest are recorded beside the ASM and in the ledgers.

1. **Exact.** Main image, relocations, protected views and the AdLib, Tandy and
   PC-speaker images rebuild byte for byte; no masked differences.
2. **Inventory.** Every executable component, runtime-installed vector and
   self-modified operand is identified with its installer, extent and lifetime.
3. **Classification.** Every byte is classified by the AGENTS.md rule. Any
   remaining UNKNOWN run carries the reason its kind cannot yet be decided.
4. **Control flow.** Every legitimate direct, indirect, shared-tail, interrupt,
   nonlocal and dispatch transfer has its legitimate target set and the writers
   that produce it. Transfers reached only through characterized corruption end
   at their stated control-transfer expression.
5. **Routines.** Every routine has a purpose-level or deliberately conservative
   name, and a contract wherever callers depend on registers, flags, segments,
   shared tails or side effects.
6. **State and formats.** Game state, the entity and object records with their
   field roles, record lifecycles, tables and buffers are written down with
   initialization, producers, consumers and lifetime (startup, level, session,
   frame). The same holds for level/terrain/ground/resource formats, the DAT
   decoder, graphics formats and the sound-driver song, instrument and command
   formats.
7. **Seams.** Gameplay/platform crossings are marked at the seam: timer IRQ,
   keyboard and mouse, VGA and DAC, DOS files, INT60/61 sound services,
   protection and media probes.
8. **Quirks.** Original bugs, wraps, signed/unsigned compares, stale fields,
   out-of-table reads, aliases and races are written at their sites (search words:
   quirk, stale, wraps, unsigned, equality, reads past, race, alias).
9. **Residue.** Every remaining behavior is in exactly one class: proven,
   platform-conditional (metadata/platform-profile.json), characterized
   (race/overflow/alias/corruption with cause, trigger, write order, affected
   memory and resulting transfer expression), or unresolved. Unresolved items are
   listed in next-work.md with the scope they block.

Not required: names for every literal; historical identifiers or module layout;
meanings for bytes no code reads; enumeration of arbitrary corrupted machine
states, interrupt arrival schedules or execution after a characterized escape;
proof that a characterized original race or overflow cannot happen.

**Scopes.** The freeze is declared first for the VGA + AdLib scope: the main
image, the protected views and the AdLib image. The full freeze adds the Tandy
and PC-speaker images, joystick and alternate display paths. Those stay
inventoried and classified throughout, but they do not block the VGA + AdLib
freeze or the primary native port.

## Completeness measures

These are separate dimensions. Byte coverage, executed-instruction coverage,
semantic understanding and runtime completeness never stand in for one another.

**ASM completeness.** Exact identity; classified bytes and the remaining UNKNOWN
runs with reasons; decoded code; open control-flow transfers; routines with
placeholder names; open semantic blockers in next-work.md. Inventory counts
describe discovered code, not closure.

**C translation completeness.** Every original routine ends in exactly one
status. The ledger currently records TESTED (bounded differential suite), STATIC
(static evidence only) and UNTRANSLATED (no C yet). The target statuses, as in
Pre2, are:

- translated: TESTED, PARTIAL or UNTESTED;
- INLINE (translated inside a caller);
- PLATFORM (replaced by a named platform service with a stated contract);
- ALTERNATIVE (an original hardware path outside the native configuration);
- ERROR_PATH (DOS/BIOS failure handling the native services never raise);
- UNRESOLVED.

There are no fake success paths, silent no-ops, unexplained placeholders or
original-instruction fallbacks, and every C operation is traceable to the ASM.

**Native runtime completeness.** A feature matrix for the supported
configuration with statuses VERIFIED, PARTIALLY_VERIFIED, IMPLEMENTED_UNTESTED,
INTENTIONALLY_UNSUPPORTED, BLOCKED or UNRESOLVED. It covers startup, menus, level
load, gameplay, results, progression, failure and exit, plus rendering, music,
effects, input and timing. Unsupported alternatives are listed explicitly.
Human-recorded replays later add end-to-end smoke; they do not replace routine
evidence.

## Translation readiness

A cluster is READY when its entry, branches, relevant state, caller-observed
results and platform seams are known; CONDITIONAL when a named dependency bounds
the translatable domain; NOT READY when a control-flow, ownership or format
question would force a guess. Record the decision as one line beside the ASM
contract only when it is not obvious. TESTED C and a decoded leaf are not
readiness by themselves; global UNKNOWN closure is not required before local C.
