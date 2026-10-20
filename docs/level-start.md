# Selected level start: 454C / 4551

The portable destination is C11 with explicit platform services, then SDL3.
This connection adds the 26 known bytes at 454C..4565; its 4551 entry shares
the last 21 bytes. It composes existing C children on canonical memory and
stops before the still untranslated gameplay body at 00FB. Nothing here boots
the original game, supplies a legacy interpreter, or resolves UNKNOWN bytes.

## Parent ownership

MainMenuStartLevel resets DS:1F6D (LevelOutcomeSuccessByte), then falls through
LoadAndStartSelectedLevel. The latter also has a direct caller at 47DD and
does not reset the outcome byte. Its other proven producers are 4729 (FF) and
4778 (zero); 4840 reads it. The remaining result/game controller is open.

The parent performs actual PUSH DS / POP ES, sets DI=0, CX=0FCA, and XORs AL
without clearing AH. REP STOSB follows live DF and the actually popped ES;
word bytes cross the 20-bit boundary contiguously. The clear excludes the
loaded record starting at DS:0FCB. It neither invents host initialization nor
keeps a shadow copy of game state.

CALL 197D writes the actual return 4560. A READY selector core leaves its
outer RET pending; the parent consumes that word through the bus, stopping
on a changed target. Its next CALL writes 4563 and invokes the native briefing.
The normal briefing tail leaves the clear routine's actual RET pending. After
consuming it, the parent JMPs 00FB. Neither parent entry has an outer RET.
Cancellation is different: the briefing calls fade, consumes its own caller
word into AX, then JMPs 4401. The parent must not pop a second word.

The API returns all fourteen registers plus status, child_status and detail.
An unavailable resource binding stops at 197D after pushing 4560; unavailable
briefing stops at 4566 after pushing 4563. Resource, briefing and changed-return
stops preserve the child's live fields and frames. The relocated segment
operands are explicit load bindings, not synthetic bus instruction reads.

## Selector bus and retained child contracts

The selector has an optional bus execution core; legacy APIs call it with a
null bus and retain their ABI. Its own reads, writes, actual saved words,
immediate-child CALL/RET words, three decimal digit stores and odd-override
REP MOVSW use the bus. Both reads of DS:1FF0 remain separate observations.
XOR BH and XOR CH precede their observed accesses. The decimal core presents
the defined flags of each actual ADD before its digit store; its cursor always
increments independently of DF.

DAT/cache/decompressor and raw-file children retain their ordinary-RAM,
preserving typed DOS and intact internal-return contracts. Passing a bus does
not widen those children to arbitrary VGA/executable/stack aliases or actual
INT21/IRET transport. The 4B1C retry UI remains a separate unverified boundary.
The full selector bus entry also forwards its bus to the already implemented
printer/cleanup tails, preserving fatal transfers and actual frames. Fatal
and retry regressions remain in the existing resource-select-full campaign.

## Bounded evidence

tests/level_start.py uses tests/verification.py for original instruction
execution, canonical memory/device access, fail-stop native callbacks and
comparison. It executes the original DAT/raw descendants continuously, while
omitting only their RAM-event projection to match the declared legacy C ABI.
Every omitted access is separately counted and budgeted; reaching VGA fails.
All RAM, registers, defined flags, DOS requests, parent/selector/briefing bus
events and device state are compared. No instruction engine or comparator is
duplicated. Fixture providers and a small backwards-output file encoder stay
outside the shared engine, with decoded records checked independently.

The campaign covers both entries, DF, stack/physical wrap, a live popped ES
including VGA, byte-wrapped order/sections, odd overrides, cache allocation,
special-resource loading up to the briefing boundary, changed decimal and
parent returns, and DIV fault propagation. Constructed valid files connect
loading, redraw, preview, text, palette/input and game/menu jumps at three
loads. Pinned MAIN.DAT supplies only UI/font fixtures. Finite service/input
schedules and instruction/access/process limits fail verification on exhaustion;
only completed differential mismatches count as mutant detections.
IRQ delivery is quiescent and TF is clear in this constructed-state domain.

The 00FB gameplay body, real device scheduling, executable dependencies,
unsupported child domains and aggregate/full-game acceptance remain open.
Reports require matching scope and consumed hashes; a retained file does not
renew earlier evidence.

The accepted campaign has 286 comparisons: 27 parent/connection fixtures and
259 decimal-bus fixtures. All ten parent instruction sites and its direct jump
outcome execute; four completed numeric mutants are rejected. It executes
8,233,345 original instructions and compares 4,460,253 bus events, with 179,408
separately budgeted legacy RAM events omitted from the projection. The largest
case has 958,946 steps / 547,677 bus events. The worker allows 600 seconds and
384 MiB per process / 640 MiB of process-tree commit; each case allows four
million instructions and two million bus events, plus a separate two-million
legacy-RAM-access cap.

All 84 unit tests and the fast identity/ASM/relocation gate pass. The unchanged
legacy boundaries also pass their affected regressions: 270 decimal fixtures,
59 selector fixtures, and 72 full-resource/error fixtures at four boundaries,
including all ten paired real selections. This is focused acceptance; it does
not refresh unrelated native or original-contract reports.
