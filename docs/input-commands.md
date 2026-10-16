# Input command and visibility composition

ProcessInputCommands3E6F occupies [3E6F,4085): 534 physical bytes, 530 known
instruction bytes / 195 sites. UNKNOWN3EE3,3EED,3F14,3F91 remain unresolved;
known jumps skip them. The neighboring4085 input-edge routine is separate.
The only near child is RebuildViewVisibilityMap at410F, 64 bytes / 27 sites.
The parent's CALL at3FDE pushes3FE1 on actual SS:SP before invoking that child.
The resulting C domain has594 known bytes, with child bytes unioned once.

The routine handles a literal scan-code comparison ladder and primary-button
panel regions. Shared fields and arithmetic remain canonical and unchecked.
Function-key selectors, release settings, scan requests, viewport changes and
the common latch-store/RET tails retain their original register and flag effects.
The routine saves no registers or segments around sound or visibility calls.

## Shared byte ownership

| Offset | Ledger name | Evidence and limits |
|---|---|---|
| 0052 | ForegroundCounter0052 | Increment01A3, reset0444; also read0365 for phase comparisons0F/23/37. No wall-clock period is inferred. |
| 0053 | InputToggleSnapshot0053 | Snapshot402D after wrapped unsigned0052-0053 >=2. Differences0/1 return without updating it; no per-level reset identified. |
| 0062 | PanelClickLatch0062 | Startup clear; FF stores3F38/3F92/3FE9, zero store3FE3. Suppresses repeated panel clicks but is also set by key-command tails. Not reset by03E7. |
| 1FD3 | ForegroundCounter1FD3 | Separately incremented0199, reset043B. Its co-rate does not make it an alias of0052. |
| 1FD4 | InputActionSnapshot1FD4 | Reset0438; updated4002 before a wrapped byte subtraction and signed CMP5. Only signed results6..127 reject; the snapshot advances even on rejection. |
| 1FCF | TimerChainFlag1FCF | Cleared by foreground/setup paths; timer-chain return writesFF. The viewport path tests exact zero, not a normalized Boolean. |

StatusIconRefreshCounter gates selection; LevelReleaseSettingRefreshCounter gates
release changes. Increasing tests equality with99, while decreasing tests only
equality with the minimum. Neither is a general range check. Reload arithmetic
is the literal byte SUB/SHR/NEG/ADD/NEG/ADD sequence; its value is
`4 + (((99 - setting) & 255) >> 1)`, but its final FLAGS still follow the original
instructions. Source-side state names do not assert pause or bulk-action meaning
beyond the identified producer/consumer behavior.

## Sound boundaries

The first gate tests live DS:2010 exactlyFF and DS:25A7 bits03, then requests
AX0401 through INT61 at3F7A (resume3F7C). The next gate rereads2010 and25A7 through
the returned DS; if the driver byte is notFF and bit0 is set, AX0313 requests
INT60 at3F8D (resume3F8F). A changed returned DS can therefore enable both calls.
The option byte remains a mask; sound setup's usual FF/03 or00/01 values do not
close all values or aliases.

Both calls use interrupt_service.c's shared transport: actual FLAGS/CS/IP writes,
current IVT binding, a full-register opaque provider stopped before IRET, actual
returned SS:SP consumption, and changed-target validation. The narrower older
INT61 native result is not substituted for this contract. Unbound vectors,
provider stops and changed returns remain explicit. No asynchronous scheduler or
untranslated sound-driver body is claimed by this parent campaign.

## Visibility child and code operand

The parent stores the byte/pixel origins before CALL410F. The child clears and
fills through live DS/ES with DF-sensitive REP order, then marks through the
relocated segment encoded in MOV CX at4136. That immediate is read at its actual
phase, after the stores; it is independent of live SS. The new live adapter shares
the existing child implementation while retaining its older explicit-segment API.
Code-operand fetches read canonical bytes and are not extra raster data reads.
The actual child RET must return to3FE1 before the parent stores the final latch.

The shared oracle can declare exactly4137..4138 as this decoded IMM16 operand.
Opcode bytes retain the exact guard. Only those identified operand bytes may be
changed by declared providers or known original writes. On a changed immediate,
the runner pauses, invalidates Unicorn's decoded cache and resumes the actual
MOV; it never supplies a Python replacement instruction. This is an explained
code/data use, not permission to mask unrelated differences or execute UNKNOWN.

## Feasible paths and remaining obligations

Two known sites, CMP at3FB9 and JL at3FBC, are infeasible from3E6F under the
declared synchronous provider contract. BX becomes `(word_at_DS0 >> 4) + 0xD0`,
so it lies in0xD0..0x10CF. If signed AX is below BX at3FB0, adding0x18 to BX cannot
wrap or change its sign and AX is still below it. Thus3FB7 always jumps when
reached; its fallthrough and both3FBC outcomes are not parent-entry execution
coverage. The literal C comparisons remain implemented. This proof does not
classify any UNKNOWN byte as dead, or cover asynchronous register changes.

## Scoped acceptance

tests/ui_commands.py passes 65 fixtures at core and actual outer-RET adapter
boundaries: 130 original/native comparisons, 220 executed sites of222 static
sites, and all121 feasible direct jump outcomes of124 static outcomes. It
executes8,407 original instructions and compares6,044 ordered events, separating
484 declared interrupt-transport events and44 provider accesses across28 calls.
Five completed mutations detect signed-counter, returned-DS, release-equality,
actual-child-return and unsigned-toggle regressions. Resource exhaustion earns
no mutation credit. The report pins26 consumed inputs.

The 530 parent bytes join the main translated-code ledger once, taking its union
to26,544; the64 child bytes were already counted. The two infeasible comparisons
remain known translated code without parent-entry execution credit. The shared
input, port-I/O and older visibility API regressions pass after consolidation;
this is focused acceptance, not a complete game or aggregate campaign result.
