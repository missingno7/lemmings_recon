# Split-palette stepping and briefing fade

The maintained cluster connects five entries in portable C: StepSplitPaletteToSlot1
(5329..534A,34 bytes), StepSplitPaletteToTargets (534B..536B,33 bytes),
PublishUpperEightPaletteColors (53CA..53F5,43 known bytes),
RefreshRasterSplitPalette (46B9..46EA,50 bytes) and FadeAndClearSplitPalette
(46A2..46B8,23 bytes). The unique new total is183 bytes. Shared writer/row/
page-clear tails are existing native dependencies, not additional byte credit.
UNKNOWN53E6 and4DF7 padding remain explicitly excluded.

## Live row-pair packets

5329 pushes DX, sets BX0100 (source0,target1) and calls the existing5569 native
selector using incoming CX. Returned ZF becomes BL0/1 through MOV then optional
DEC. It pops the actual saved DX into CX, pushes the first marker's entire BX,
then forces CX16/BX0107 for source7,target1. The second ZF becomes AL0/1. Final
POP BX consumes the actual saved first-marker word, and OR AL,BL sets final ZF.
The intermediate POP remains observable even though the later MOV CX replaces it.
DX is not restored, and returned BH remains whatever the saved word contains.

534B pushes BX and DX, forces only BL0, and steps source0 toward incoming BH.
It pops actual saved DX into CX and actual saved BX into BX. First ZF becomes
DL0/1; the complete live DX word is pushed. Original BL becomes BH and BL becomes7
for the second step. Final POP BX reads that saved DX/marker word, not original
BX. OR AL,BL uses the complete byte, including unexpected values supplied through
stack aliases. Returning a normalized host boolean or restoring entry registers
would lose both packet and flags behavior.

Both calls compose lmn_select_and_step_palette_row_core directly, with original
near return words and live DS/ES/SS. Each selector independently rereads mode and
CS pointer words. A mode change between children takes effect. Child channel
stops, changed row returns and changed immediate-child returns keep statuses3,
4 and5 respectively. A changed return is consumed as the actual original RET,
then stops at its actual continuation with remaining saves intact.

CL0 retains65,536 row iterations. Slot1's second count is always16; the targets
entry uses actual saved DX as its second count. Four full core witnesses test
first-count and second-count zero forwarding in both packed and RGB modes.
The shared old row cores own the arithmetic and zero-count loop behavior.

## Upper-eight publication

53CA supplies CH8/CL8, clears AH, doubles AL and compares full mode word1F7C
with4. Equality reads the RGB CS52E4 table and advances the selected live source
by24 bytes; every other word uses packed CS52D4 and advances by8. The unchecked
index can read adjacent instruction/data bytes. The tail JMP reuses the existing
attribute or mapped-DAC writer and its caller frame; no extra CALL is created.
The existing publication enum values0..3 remain unchanged; upper-eight is4.

## Raster refresh and connected fade parent

46B9 reads display-controller base1FDA and adds6 to DL alone, retaining DH on
byte overflow. It waits until bit3 is set and then clear, disables interrupts,
pushes actual DX and publishes the first8 colors from slot0. The writer's actual
RET is checked. POP DX reads the live saved status port, CLI executes again,
and CX60 counts low-to-high bit0 cycles. Slot7's first8 colors are then published,
followed by unconditional STI and the caller RET46EA.

This is a timed sequence of palette changes within a frame, rather than a single
final palette value. A future host must retain the sequence when presenting the
raster split. These tests provide finite status-byte schedules and check every
I/O packet and phase flag; they do not claim real device timing or asynchronous
IRQ delivery. The callback may change the saved port or DS base, and the original
word reads and byte-add width remain observable.

46A2 calls the refresh child, publishes slot0's upper8 colors, sets CX/DX16 and
calls the slot1 pair. Its returned ZF immediately decides whether to repeat.
A changing row requests another pass even when that step reaches its target;
there is no recomputation after a wait and no early boolean normalization.
Completion tail-JMPs into the existing full drawing-page clear, leaving the
inherited caller word for clear RET4E36. No synthetic parent return frame is
pushed. The clear child's existing read/write/word-output requirement is retained:
missing clear bus stops at4DF8 with explicit status7; missing word output status6
is distinct from a changed code continuation.

## Shared verification and retained regression

New cases in tests/palette_transition.py use verification.py's exact original
executor, canonical BusAccess, fail-stop guarded NativeCallbacks and full-state
comparator. Fixture setup, finite status ports and independent marker expectations
stay outside that engine. The existing1191 transition cases remain their original
regression campaign, allowing incremental migration without a new bespoke runner.
The native suite runs both and emits separate reports with complete input hashes.

Constructed cases exercise both step entries, three mode words, all four change
combinations, counts, saved markers/counts/ports, live mode/table words, unmasked
selectors, SS/data aliases, near-stack and20-bit wrap, DF, clear-provider failure,
missing byte providers and immediate/internal changed returns. Refresh and fade
are composed with the native publication/row/clear children on one memory image.
All owned sites and direct branch outcomes are required. The four full zero-count
cases run core boundaries once; ordinary cases also consume the actual outer RET.

An initial stable-row fixture put a target at2000, overlapping blanking control
200C. Original flags correctly reported that difference, so the synthetic buffers
were moved before acceptance. The general stack-alias case now aliases saved and
outer return words at source7; a separate3004 source/frame overlap retains the
original changed-child-return stop. No game C or original assets were changed to
hide those fixture effects.

Thirteen completed mutation witnesses cover ignored child returns, normalized
OR/markers, discarded saved counts/registers/ports, wrong byte-add width, a59-cycle
raster split, missing upper-source offset/count, omitted final fade pass, lost CLI,
masked second target and invented tail CALL frame. Resource exhaustion, callback
errors or nontermination never count as detected mutants; all witnesses use
ordinary finite cases, not unbounded native zero-count mutations.

Native workers retain384MiB process-tree commit limits and owned temporary build
contexts. Ordinary calls allow2,000,000 instructions/500,000 events; four zero
calls have explicit30,000,000/6,000,000 ceilings, while the measured runs use much
less. Status reads are capped at24,000. A shared worker has720 seconds; the
unchanged legacy workers keep240 seconds each/660-second campaign envelope.
The enclosing native suite allows1440 seconds for both scopes. Full aggregate
acceptance still requires its independent original-contract and complete native
campaigns. Unrelated report files are not renewed by this focused acceptance.

## Accepted evidence

The shared worker passes185 fixtures /366 comparisons, all88 owned sites /25
direct outcomes and13 completed mutants. Its183 new unique bytes take the main
C ledger union to30,195. The declared connected instruction domain is703 bytes;
executed union is330 sites /60 outcomes. It executes21,732,941 original
instructions and compares7,774,840 ordered events. Peak invocation is8,063,009
instructions /1,769,940 events, from an explicitly bounded full-zero case.
All four zero-count comparisons complete; no exhausted budget earns credit.

The retained transition campaign also passes1191 fixtures at both boundaries
(2,382 comparisons), all82 caller /268 integrated sites,40 outcomes and six
completed mutants. The combined selected suite finishes in527.05 seconds.
Both scoped reports'131 consumed-input hashes match, and all owned build/DLL
directories are reaped. All83 unit tests and the exact ASM/relocation gate pass.
These remain focused results; unrelated historical reports are not renewed.

The dependency graph now displays how much of an untranslated body's decoded
extent already belongs to C ranges, using the same complete-instruction union
validator as coverage.py. The new unit case keeps a native shared tail separate
from the untranslated entry's remaining bytes. For example,4C17 shows72 decoded
bytes with63 already in C and9 outside C ranges;5447 shows133 with90 already in C
and43 outside. Existing traversal, cycles, native scopes and unresolved/platform
seams remain intact; overlap accounting is not whole-program closure.

The final manifest audit found that inherited drawing-fixture hashes included
all of symbols.json, even though palette cases use literal pinned instruction
ranges and generated lemmings_sym.h offsets. Recording acceptance annotations
therefore invalidated the first complete run. The palette consumer now excludes
that unused full-ledger hash while retaining its actual header/ASM/oracle/source
dependencies. An additional unit check prevents reintroducing that dependency.
Both native scopes were rerun after the correction; reports are not rehashed or
renewed from their earlier files. Other consumers retain their own manifests.
