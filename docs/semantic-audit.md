# Semantic reconstruction audit — 2026-10-20

Baseline: `37cf145`. This is a bounded strategic audit and four-subsystem source
sample, not certification of every instruction. Current counters are generated
in [completeness.md](completeness.md); current priorities belong only in
[next-work.md](next-work.md). Findings below are evidence at this checkpoint.

## A. Diagnosis and reference comparison

The premature-translation hypothesis is **partly supported**, but it does not
explain the difference by itself. Lemmings began C while its global semantic
oracle was immature; subsequent translation frequently performed the missing
state/contract recovery. Much of that knowledge remained spread across tests,
role-named C packets and long milestone narratives. Yet sampled translated
algorithms have strong evidence, and early leaf translation was useful. A restart
or blanket C rewrite would discard working knowledge without solving the blockers.

The graph also previously clipped every C-labelled entry to its tested C range,
hiding the remaining original body during dependency selection. The new `--asm`
view exposes 03E7 as 233 original bytes / 72 sites, 135 already in C and 98 outside
C ranges, including all 15 direct children. Its old default view remains useful
for native scopes but could not establish semantic readiness of that whole body.

The references do not share one chronology or verification domain:

| Reference | Observed method and limits |
|---|---|
| Overkill | Semantic oracle tag `asm-semantic-oracle-v1` at `0f67c9b`, 2026-09-26 21:42. First DOS-C movement cluster `be4db94` at 22:54. The freeze bar includes classification, purpose contracts, record lifecycle, tables, platform seams and quirks. Prior C-readiness work existed; the tag was not a ban on all prior C activity. |
| Pre2 | Exact bootstrap `5d2bb42` at 19:23, complete code decode `1da469e` at 19:33, hand-maintenance freeze `8f21cee` at 19:37, first C `67924f3` at 20:02 on 2026-10-12. This is a generated-source freeze, not Overkill's global semantic bar. C later corrected comments (`cd34b6c`). |
| Lemmings | First commit `fd5895a` combined the exact oracle with checksum C on 2026-10-13; semantic-source workflow followed in `78d4289` on Oct 14. The full semantic gate remains open. Shared verification arrived in `ae7abac` on Oct 16 after many bespoke suites already existed. |

Sources: [Overkill freeze criteria](https://github.com/missingno7/overkill_recon/blob/0f67c9b5416f2414624193f138619dbaea8f43ec/docs/next-work.md),
[first Overkill C cluster](https://github.com/missingno7/overkill_recon/commit/be4db94053515dca458829f183e5c7fed42457d8),
[Pre2 first C](https://github.com/missingno7/pre2_recon/commit/67924f3), and local histories.
The local checkouts inspected were `D:/Prog/pre2_recon` and
`D:/Games/DOS/dos_recosystem/overkill_recon`; neither was modified.

Pre2 does use original memory: a 1 MiB backing image, named offsets and no shadow
records. Its C adapter carries AX..BP,DS,ES,FLAGS, but omits SS/SP; stack scratch
is excluded from memory equality (`tools/difftest.py:10,19`). Its player cases
also start from real loaded-level and earlier-frame-produced states
(`tests/player.py:1..17`). Overkill retains more register/segment effects and
stack depth, but likewise excludes stack scratch from equality. Both projects
test quirks and poisoning; neither claims equivalence for every arbitrary
machine state. Pre2's flowing ES and Overkill's DOS hybrid are game-specific.

Intrinsic Lemmings costs include packed-image recovery, protected execution views,
multiple live segment frames, executable sound overlays, twelve VGA renderer
variants, overlapping scratch/stack/map storage, and unresolved callback writers.
They cannot be removed by adopting another project's ES or stack assumptions.

Avoidable costs are the granularity of accepted work and its observation domain.
The four initializer commits `cc5b41c..37cf145` span about 79 wall-clock minutes;
the last three add three already-understood CALL instructions, while expanding
full-register/stack/provider compositions around them. That is valuable handoff
evidence, but it need not be the mandatory unit of progress. Commit timestamps
are not active engineering-time measurements. There is no reliable time ledger
for discovery versus C versus fixtures/docs, so numerical effort percentages
would be invented.

## B. ASM maturity and blocking uncertainty

A competent engineer can translate many local leaves from the ASM. They cannot
yet reconstruct the whole game's architecture confidently from it alone.
The physical modules, exact encodings and many contracts are strong; lifecycle,
dispatch-domain and platform assumptions remain uneven. Several header comments
describe native test checkpoints instead of purpose and caller obligations.

Baseline static accounting: 82,906 exact main bytes; 45,768 classified; 35,826
decoded instruction bytes at 15,417 sites; 37,138 UNKNOWN bytes in 115 runs, with
2,032 UNKNOWN bytes inside the provisional code frame. The decoded denominator
is incomplete. There are 1,569 explicit main-source encoding exceptions: valid
instruction spellings recorded beside `db`, not 1,569 unexplained code regions.
They preserve opcode alternatives; replacing them cosmetically is lower value
than recovering state ownership. No incorrect code-as-data classification was
established in the four sampled traces. Exact output is not semantic maturity.

The largest UNKNOWN code-frame gap is 098C..0D9D (1,042 bytes). Its arbitrary
linear decode contains implausible far transfers and later-CPU spellings; this
is no proof of passive data or of a valid executable stream. Protection/write
provenance must decide it. Other gaps include 5D18..5D65 and 71CA..7217; isolated
NOP-looking bytes between known branches stay UNKNOWN until classified by evidence.
The large post-09A90 spans likewise cannot be declared non-executable by location.

Seven main CFG frontiers comprise two protected-code transitions and five
conditional indirect transfers: 1407,42A5,4CC9,4D18,715B. Known target sets are
not proof of closed write domains. The sound images have separate unresolved
dispatch targets and much unclassified payload; main-C progress does not finish them.

## C. Representative C-to-binary traces and debt

Addresses below refer to the pinned main image; `tools/where.py ADDR --disasm N`
reads those original bytes. The exact ASM gate establishes the maintained source
mapping independently of C. These traces inspect algorithms and ownership, not
just status labels.

| Operation and trace | Assessment |
|---|---|
| `c/entity_update.c` -> `src/game_code.asm`1F19/1F5E/1FEB -> original1F5E `8B4408` loads+08 once -> create30A6 and action3150 producers | First-match mask priority, inactive gate, countdown and shared POP ES tail are understood. `LmnEntityUpdateCall` still carries a nearly complete register packet under role names. Record bounds, lifecycle aliases and sound dependencies remain conditional. |
| `c/entity_action_dispatch.c` and action cores -> `src/entity_actions.asm`3150 -> selection3CDE and calls01AD/01C5 | Press latch is set before selector validation; selectors 2..9 are inventory ordinals, not state masks. Tested signed-selector and fallback behavior is genuine logic. Full input/record validity and IRQ timing are not established by the leaf matrices. |
| `c/entity_interactions.c` -> ASM2EE6..2EFF -> original`368A07`, `50`, `88442C`, then second sample and`88442B` | First cell is stored at +2C, second at +2B, then saved AX is popped. Record/SS alias can change the dispatched value. This is essential behavior, not removable stack noise. |
| `c/terrain_stream.c` -> `src/level_initialize.asm`3752..3763 -> original four byte loads,`83C604`,`3DFFFF` ->7C67 ->8822 | Big-endian command words, live cursor and whole-word FFFF sentinel are semantic. The command API is reasonably named; returned CPU FLAGS preserve the raw boundary. The renderer's C `scope` ladder retains older partial-entry APIs; repeated packet conversions are compatibility debt, not an unproved reason to rewrite pixel math. |
| `c/resource_select.c` -> `src/resources.asm`197D -> original`8A1E6B1F`,`8D36EE54`,`8A08` -> raw/DAT children | Unchecked selection/order lookup, in-place LEVEL at0FCB, odd overrides and normal/special graphics are understood. Provider-preserving DOS, short reads, retries and fatal cleanup constrain acceptance. |
| `c/resource_rle.c` -> ASM1B42 -> original`AC`,`3C80`,`7431` -> special resource1A7B | Closed bounded leaf with DF, overlapping copy and segment-rollover repeat-byte corruption preserved. The surrounding file/platform path does not inherit unconditional readiness. |
| `c/game_initialize.c` -> ASM03E7..046D -> level36B6; remaining ASM04B6..04CF -> original`49`,`7501`,`4A`, then`03C9 13D2 F7DA` -> consumer0164 | The connected C prefix is strong scoped evidence. The final wait producer uses ADD/ADC/NEG-high, not a conventional 32-bit negation; the consumer has its own borrow/zero rule. Real timer delivery and full controller are still missing. |

Classification of complexity:

- **A — essential:** ordered shared-memory reads/writes, observed map/record/SS
  aliases, signed/wrapped math, first-match states, returned segments, VGA
  latches, self-modification, actual nonlocal returns and original bugs.
- **B — boundary machinery:** full machine-state adapters, IP continuation tags,
  actual RET/IRET transport, defined-FLAGS reconstruction and byte-bus tracing.
  Existing raw-entry contracts require them. That does not prove every native
  C-to-C operation must expose them after caller invariants are established.
- **C — accidental:** duplicated physical/address/flag/stack helpers, repeated
  register-role packet conversion, historical renderer-scope wrappers and
  copying milestone totals into several documents. Consolidate only when a
  concrete consumer is being changed and equivalence can be checked.

No sampled evidence justifies dropping registers or aliases indiscriminately.
Nor does renaming AX to `value` establish a semantic interface. The next safe
simplification needs a caller/producer proof and comparison of observable outputs;
it must not silently narrow the old adapter domain. Existing C is retained.

Constructed alias witnesses prove behavior under their declared entries, not
that startup can reach every such state. In particular, this audit found no
whole-program proof making arbitrary DS=SS or VGA-backed stacks a normal native
game requirement. Their instruction effects stay preserved in existing adapters;
the obligation to expose them throughout native logic is still a caller/lifetime
question. Do not confuse an adversarial test's reachability with its correctness.

## D. Verification cost and proportionality

The retained terrain campaign log records 1,666.01s (27m46s). 192 adapter cases
include 160 pinned LEVEL/entry combinations and 32 constructed cases; 32 core
comparisons are separate. Per-case intervals sum to 3,206.4s because two workers
overlap; 396.1s of that is labelled native execution/trace validation. These sums
are not wall time or a compiler profile. Whole-RAM/bus/VGA plane checks settle
real risks. Repeating this matrix in each new parent would not.

The terrain baseline/two mutants compile a 19-source closure three times; the
drawing-render baseline/three mutants compile 17 sources four times
(`tools/cbuild.py`). No object reuse exists. Compiler share was not measured,
so this audit adds no caching/build framework. Terrain also rewrites its entire
accumulating case journal at each completion; final report and journal are each
about 4.7 MB. That is avoidable I/O when that campaign next changes.

The initializer hashes 224 inputs and builds a baseline plus eight DLL variants.
The preceding measured run in this chat took 93.12s. An older, smaller retained
run took 21.01s for 22 comparisons and five mutants, versus the current 27
comparisons and eight mutants. These are not comparable benchmarks. The registry
has 177 suites with summed timeout ceilings of 25.35h; this is a safety bound, not a
measurement of full-campaign runtime. Tests count many boundary entries as
cases; case/site/mutation totals cannot stand in for game completion.

At baseline the terrain report had 5/84 stale hashes, including coverage and
launcher files; drawing-render had 7/51. The initializer had 0/224. Later semantic
source/ledger changes invalidate coarse manifests without changing executable
instructions. Existing reports are not renewed by this audit. Tests may pin
unused aggregator files: move that dependency only after proving it is reporting
policy rather than an execution dependency; preserve prior accepted manifests.

Use four tiers: exact/static checks for ASM-only changes; affected local C
suite; directly connected parent with handoff/state cases; affected shared
consumers and full original contracts when contracts change. Full native
campaign plus aggregate reporting remains an explicit acceptance event. Keep
the existing strongest witnesses; stop inventing new artificial provider domains
without a concrete contract risk. No fixed mutant quota and no new CPU model.

## E. Bounded improvements in this change

1. `src/entry_services.asm`: purpose-named frame/fade/calibration blocks and
   actual session/control/timer contracts. Ledger-owned globals replace numeric
   transition/countdown/wait operands. `4551` clear, 03E7 initialization and startup
   clear now have distinct lifetimes; the matching 4551 comment is in
   `src/input_menu_and_retry.asm`.
2. `src/game_code.asm`, `src/entity_actions.asm`, `src/image_tail.asm`: shared
   record-field operands, state/behavior/cell anchors and role aliases. Countdown
   and strip names resolve to the same +20; horizontal step and frame gate to +27;
   inactive marker and drawing skip to +26. Source states priority, producer order,
   first/second sample order and alias effects. No complete record extent or
   historical skill names are invented.
3. `metadata/symbols.json` owns the names and evidence; `c/lemmings_sym.h` is
   regenerated. No C algorithm, code range, asset, classification or binary byte
   is added, removed or normalized.
4. `tools/graph.py --asm` restores an original-CFG view independent of C ranges;
   it retains frontiers and does not relabel a whole ASM body TESTED.
   `tools/coverage.py --inventory` provides a current, cheap main/sound inventory
   separately from strict aggregate acceptance. Accounting tests reject stale
   identity evidence and accidental aggregate execution. `docs/completeness.md`
   is the quantitative summary; old narratives are archived once in
   `docs/convergence-history.md`. Roadmap and method no longer copy running totals.
5. AGENTS, architecture and verification guidance now use the scoped gate and
   proportionate run tiers. The existing tests/framework remain intact.

Validation: exact main 82,906 bytes / 63 relocations, sound 22,125+21,702+758 bytes,
and protected views retain exact output; no masking. UNKNOWN runs and all seven
main frontiers remain explicit. The static/accounting/unit suite passes 89 tests.
No native behavior was modified, so long native campaigns are deliberately not
rerun solely for renamed metadata/comments. Their retained acceptance hashes
remain historical. This is an ASM-understanding improvement, not new C coverage.

## F. Lightweight semantic readiness gate

Before a cluster is expanded, put a short decision beside its ASM contract:

1. Known entry/boundaries and reachable branches, including shared/nonlocal tails.
2. Relevant fields/tables/buffers with initialization, producers and consumers.
3. Actual inputs/results and caller-consumed flags/register/segment effects.
4. Indirect targets/writers and dependencies; state which closure is unproved.
5. Hardware/IRQ/service seam, scheduling assumptions and observable memory effects.
6. Explicit remaining uncertainties and the domain they permit or block.

**READY** means no major semantic guess inside that stated operation/domain.
**CONDITIONAL** means named dependency/provider/alias seams bound translation.
**NOT READY** means a fundamental owner/control-flow/platform question still
forces a guess. A global zero-UNKNOWN bar is unnecessary for a local READY leaf.
TESTED C, decoded leaf and apparent normal execution are not readiness proofs.

| Actual subsystem/domain | Readiness | Limitation / next proof |
|---|---|---|
| Decimal 4BC2, DAT bit/copy leaves, RLE 1B42 | READY as bounded leaves | Keep exact wrap/DF/rollover and adapter contracts; parent readiness is separate. |
| DAT/resource selection 1916..1F18,454C/4551 | CONDITIONAL | Known formats; unchecked table/short-read/DOS/retry/fatal domains remain declared. |
| Planar 8822..9A8F and terrain 374F/395F/7C67 | CONDITIONAL | Normal dispatcher/bodies understood; source allocation, code/stack aliases and hardware state need caller lifetime closure. |
| Entity state/action blocks 1F19..368D | CONDITIONAL | Strong local transitions; whole-array bound, callback writer domain, shared roles and services prevent global READY. |
| Record producer 30A6 and object 378A/7C0A | CONDITIONAL | Equality limits, stale slots and overlap understood; general segment/allocation/unchecked-index invariants unproved. |
| Game loop 43F2/4401 -> 454C/4551 -> 00FB -> 46EB, retry screen 4B1C | READY and translated in the IRQ-at-poll domain | Real 4C47/17C7/16D4 delivery at polls (tests/game_loop.py). 004A FF producer, preemption inside children, sound bodies, startup/protection remain. |
| Startup/protection 054E..13DB | NOT READY as a whole | Dynamic protected views, gap 098C..0D9D and segment/allocation provenance. |
| Complete executable sound engines | NOT READY as a whole | Only scoped entries/latches/PC routines translated; unresolved dispatch and unclassified payload remain. |
| Native whole game/platform/SDL3 | NOT READY as complete | Host runs the verified loop in a declared domain. Omitted/altered original behavior: NULL entity sound bindings stop sound-enabled actions; special-graphics briefing redraw unbound; INT61 not rebound after 057B; media probe outcomes fabricate registers and russell.dat persistence; chosen timer schedule; private IRQ 0F70 never delivered; joystick unbound. |

Working loop: choose the highest-cost guess -> inspect binary/callers/state ->
record the semantic contract in ASM/ledger -> exact gate -> readiness decision ->
translate one coherent READY operation -> targeted/handoff checks -> record only
changed evidence and next uncertainty. See next-work.md for the five priorities.

## G. Semantic oracle freeze: `asm-semantic-oracle-v1`

The milestone is independent of C or host playability. It is declared only when
all of the following hold, each recorded beside the ASM or in the ledger:

1. **Executable inventory.** Every original executable component is identified:
   main image, protected execution views, PC-speaker overlay, AdLib and Tandy
   driver images, runtime-installed vectors and self-modified operands, each
   with its installer, extent, lifetime and restore contract.
2. **Evidence-based classification.** Every stored byte of every component is
   classified from initialization, readers, writers, execution paths, overlays,
   aliases and lifetime. No speculative code/data calls; a zero fill, a named
   prefix or a linear decode never classifies a run. Overlapping roles (code as
   checksum data, buffers over stored bytes) stay explicit.
3. **Closed control flow.** Every reachable direct, indirect, shared-tail,
   interrupt, nonlocal and dispatch transfer is accounted for, with the
   producer/writer domain that bounds each indirect target set.
4. **State ownership.** Records, tables, buffers and globals have documented
   initialization, producers, consumers, extents or explicitly unchecked access,
   and lifetimes across startup, level, session and frame.
5. **Translatable contracts.** Routine contracts state caller-observable inputs,
   results, flags, segments, stack and side effects well enough that C needs no
   invented behavior.
6. **Preserved quirks.** Bugs, wrapping, aliasing, interrupt and hardware
   dependencies are stated where observable.
7. **Classified residue.** Every remaining behavior is in exactly one class:
   (1) proven from original instructions; (2) platform-conditional, fully
   understood under the declared machine contract (metadata/platform-profile.json);
   (3) characterized original nondeterminism: races, interrupt interleavings,
   overflows and aliases whose mechanism, trigger conditions, affected memory
   and later observable consequences are understood well enough to reproduce;
   (4) unresolved semantics: unknown executable targets, unknown effects or
   missing behavior-affecting dependencies. Class 4 blocks the completeness claim
   it touches; a named unknown is not a contract. Unrecoverable detail
   (historical names, layout) is listed separately and never blocks.

Control-escape completion rule. A corruption-induced control escape is class 3
when (a) the trigger, affected state, write order, memory footprint and the
control-transfer expression are proven; (b) the CPU state at the escape boundary
(registers, FLAGS, segments, stack, committed memory) is characterized; (c) the
escape is shown to follow from the characterized corruption, not from an
unresolved legitimate callback or dispatch path; and (d) every effect before
the escape that can influence later normal gameplay is accounted for. The
specification then ends that path with "control transfers to CS:F(state) with
the characterized machine state; execution continues in the original image and
machine environment" and does not enumerate instructions reached only that way.
This closes the semantic characterization, not the native implementation: a
characterized but unsupported escape is an explicit runtime equivalence
limitation, never replaced by success, a no-op, recovery or invented logic.
It never dismisses genuine unknown callbacks, ordinary reachable code,
corruption that continues through normal gameplay, or behavior-affecting
UNKNOWN storage.

The freeze does not require proving that original races, aliases or overflows
are impossible. If the original permits them, the specification characterizes
them and implementations preserve them. Keep three layers distinct: the
complete semantic specification, the supported VGA + AdLib runtime
configuration, and the techniques of the current C/native host.

Priority order for the freeze is the DOS VGA game with the AdLib driver; the
PC-speaker and Tandy images, joystick and alternate display paths remain in the
inventory and must be classified before the freeze, but do not block the
primary native port. A local READY decision permits work only in its domain; a
complete partition, known target list or zero decoder errors alone does not
satisfy this bar. Inventory counts describe discovered code, not closure.
