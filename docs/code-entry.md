# Connected code-entry editor and validation screen

The maintained cluster adds FormatSelectedLevelAndGroup488C (36 bytes), the
MainMenuCodeTransition4967 screen (154 bytes), ReadCodeInput4C7E (156 prefix bytes),
and the seven-byte DrawCodeInputText503B tail. ReadCodeInput owns156 new
physical bytes; its206-byte graph includes the50-byte shared text tail, itself
seven bridge bytes plus43 already translated text bytes. The unique new total
is353 bytes, not the sum of overlapping graph extents. It composes the accepted encoder/
decoder, display setup, palettes, page operations, keyboard character reader,
text/glyph rendering and variable-width decimal field on the same canonical RAM.
No original instruction executor or legacy runtime is used by game C.

## Editor ownership and frames

Entry4C7E initializes SI/DI to input4DF2, DX to its exclusive ten-byte end,
BX to5A41, BP to503B and CX to5F2E (underscore/dot). DS:491E starts at20.
The outer edit frame saves SI, DI, BX, CX, DX and BP. Each wait and drawing cycle
saves DI, SI, CX, DX and BP again. POPs reread actual live SS words; child cores
carry actual returned registers and stack fields. A changed saved bound, cursor
or callback therefore changes the following original operation.

Each wait decrements the byte countdown. The memory write observes incoming
flags; result flags are installed after the write and control JNZ. Zero reloads
20 and compares the current cursor byte to CL: equality stores underscore CH,
inequality restores CL. Cursor text is redrawn, display origins are swapped,
and the native keyboard character reader consumes the live held/repeat bytes.
FF keeps the outer frame and repeats the inner wait cycle.

Ready input restores the outer frame. DEL7F first writes a dot at the current
cursor, then moves left and remembers the preceding byte; that preceding byte
is not immediately erased. CR clears the entire1FC7 action word, restores CL at
the cursor and tail-JMPs through BP. Other inputs use signed AL versus live BL/BH
bounds. Normal bounds accept A..Z. If DI equals the exclusive end, insertion is
ignored; otherwise it stores AL, increments DI and rereads CL. Reaching the end
moves back one slot, so additional letters replace the tenth character.

The known BP target is503B, supported by existing static indirect evidence.
DrawCodeInputText sets SI to4DEF and JMPs into the existing text-stream core.
It shares the text RET4D77 and inherited caller word. There is no invented CALL
frame at either final tail. Cores leave that RET pending; adapters
consume it only on success. Ordinary inner CALL BP supplies the actual4CCB
return word and checks the text core's real return.

A changed BP outside the known domain returns UNSUPPORTED_CODE_CALLBACK6 before
CALL4CC9 or JMP4D18, preserving all actual saves and writes. The original oracle
stops before the same unresolved transfer. Those alternatives remain unresolved;
translation of the known editor path does not close either whole target domain.
Missing services and changed actual child returns keep their existing distinct
statuses. No callback pointer is silently normalized to503B.

## Formatter and screen

The488C helper pushes CX, reads selection1F6B, increments AL as a byte, divides
by30, and uses MUL to derive the group base. It then rereads live selection,
increments CL as a byte and subtracts that base. Zero remainder becomes level30
and decrements AH. It pops actual CX. Stable selectionFF therefore returns
AX=FF1E; a changed second read remains observable. Its core leaves RET48AF live.

Screen4967 clears, initializes origins, transitions palette, clears again and
draws the background. It fills exactly ten input bytes with dots, displays the
prompt and enters the real native editor. Decode51A2's returned ZF selects the
actual499C branch; validity is not inferred from a host boolean or service status.

A valid code formats the one-based level into4E10 through the existing native
decimal-field core. The actual saved AX is popped afterward. Its AH supplies
an unchecked six-byte rating-row index: source4C01+6*group. DS is pushed and
popped into ES, and the original REP MOVSB copies six bytes with live DF and
16-bit offset wrap. SelectionFF's formatter groupFF reaches row51FB; no clamp
to the menu's four ordinary ratings is introduced. The result text is displayed,
then up to120 wait cycles inspect low three button bits, action20 and action40.
The predicates short-circuit in original order; timeout decrements live CX.

An invalid code draws the rejection text and waits60 cycles. Both paths JMP4401
without an outer RET. This screen preserves decoder side effects, including the
BILLANDTED latch on invalid input, selected-level writes and in-place rotations.
Native main-menu refresh can immediately consume the resulting live group and
selection. Startup/gameplay bodies beyond454C remain separate work.

## Verification structure and resource limits

The existing main_menu suite uses tests/verification.py for original execution,
canonical bus access, guarded native callbacks and comparison. The new fixture
provider supplies a finite keyboard-state schedule at actual editor waits, plus
optional button/action events during result waits. It does not implement an
editor, replace the character reader or supply translated child results.

Focused cases cover all256 formatter selections, both reads, changed saved CX,
stack alias/wrap, every owned site and branch, cursor blink, signed bounds,
last-slot replacement, deferred backspace, initial non-dot input, modified saved
bounds/end pointer, both unsupported BP transfers, missing input and changed
child returns. Screen cases run at three loads and cover success/rejection,
special input, all three early-exit predicates and timeout, unchecked rating
rows, and DF-sensitive copies with deliberately empty text headers. Constructed
headers/rows are fixture memory, not changes to original assets.

Three same-RAM sequences run menu key81 ->4967 -> real typed code -> decoded
success ->4401 refresh ->454C. No synthetic outer CALL/RET replaces either menu
JMP. External action20 exits the success prompt while leaving buttons released;
subsequent refresh consumes live state. Completed stage comparisons precede
clearing observation histories; game RAM, VGA planes/latches and state persist.
The earlier input-selection and transform handoffs remain in the same campaign.

Distinct completed mutation witnesses exercise formatter byte wrap and reread,
actual CX, blink period and memory-write flag timing, deferred erase, last-slot
replacement, signed bounds, live CALL/JMP pointers, full action-word clear,
decoder branch wiring, DF, unchecked rating index and final action40 predicate.
Timeout, memory or access exhaustion never earns mutation credit.

The per-invocation4,000,000-step /2,000,000-event limits and384MiB process-tree
commit cap are unchanged. The expanded campaign uses1200 seconds inside a1260-
second outer suite envelope: measured added focused work and three full refresh
handoffs increase total campaign work. Compile/DLL directories remain owned
contexts under build and are reaped after failure too. The compiler source
resolver adds the already maintained decimal_field.c dependency to main_menu;
other cluster selections are unchanged. Shared oracle contracts are unchanged.

## Next level-start frontier

Fresh4566 tree and5329 bottom-up views identify a broad2,021-byte /704-site
original graph body with recursive/shared game and menu paths. It is not a single
independent leaf. MainMenuStartLevel454C first clears byte1F6D, then4551 pushes DS
and pops actual ES, sets DI0/CX0FCA/AL0, and runs DF-sensitive REP STOSB. It calls
the accepted197D resource selector, calls4566, then JMPs00FB. Preserve the clear
boundary and live segments rather than replacing them with a host state reset.

The resource_select_full API deliberately uses RAM throughout and exposes DOS,
retry and fatal-service seams; it has no raster-bus parameter. Its actual child
returns and1949/04D0 fatal tails remain part of that existing contract. Connecting
454C must keep that boundary explicit or migrate the affected capability before
claiming bus/device/IRQ behavior. The loaded-header and record aliases described
in level-header-ownership.md remain relevant to the later game-state handoff.

Two palette callers are the next narrow dependencies of the briefing path.
5329 saves DX and steps the incoming CX row with BX0100. It converts returned ZF
to BL0/1 without changing that test via MOV, pops actual saved DX into CX, saves
BX, then steps16 colors with BX0107. Finally it pops BX and ORs AL with BL. The
intermediate POP remains observable even though the second MOV CX overwrites it.
The routine does not restore DX or return a normalized host boolean packet.

534B saves BX and DX, forces BL0 for its first step, then pops actual saved DX
into CX and actual saved BX into BX. The first returned ZF becomes DL0/1. It
pushes that live DX, moves original BL into BH and sets BL7 for the second step.
Its final POP restores that saved DX word into BX before OR AL,BL. Both callers
must compose the existing5569 selector/row core with actual near frames and
return all child-produced fields. CL0 retains the row core's65,536-iteration
contract; the original POPs are not interchangeable with host local variables.

The53CA writer prefix supplies CH8/CL8, doubles zero-extended AL and selects a
live CS pointer using mode word4 for RGB. It advances packed source by8 or RGB
source by24, then tail-JMPs into the existing attribute/mapped-DAC writer. Its
UNKNOWN53E6 padding remains unresolved. The4C17 prefix sets DI15E0/CX5780 and
tail-JMPs to the existing ClearVgaBytes core. The broader4566 body also retains
other unported children, signed/header/division contracts and game-loop seams;
these narrow dependencies do not complete the whole caller or SDL3 host.

Supplemental full-screen comparisons also pass at mode word4 (464,141 original
instructions /472,529 events) and0104 (469,701 /472,637), using the existing
code-screen-valid-1010 fixture with only that word changed. The latter retains
the original non-RGB branch despite its low byte4. The supplemental report keeps
the complete fixture dictionaries and consumed source hashes; it does not renew
unrelated historical reports or aggregate acceptance.

## Accepted evidence

The expanded main_menu campaign passes967 fixtures /978 comparisons, all601
own sites /130 direct outcomes and46 completed mutants. The new regions add
160 own sites /43 outcomes and353 unique code bytes; the main-image C ledger
union is30,012. Seven handoff sequences include three actual menu/editor/
validation/refresh journeys at different loads. All81 unit tests pass.

The full campaign executes39,102,777 original instructions and compares
30,200,773 ordered events. Its integrated executed union is2,561 sites /412
outcomes. Supplemental observations count17,272 far-return accesses,436 declared
interrupt-transport accesses and32 service callbacks. Peak invocation sizes stay
2,349,919 instructions /1,664,700 events, within the unchanged per-call limits.
The worker completes in1001.37 seconds inside the1200-second /384MiB envelope.
All151 consumed source hashes match for both the main and supplemental reports.
Owned temporary compile/DLL directories are empty after worker exit.

The raw report's known-connected-byte metric is8,163. Its inherited boundary
filter conservatively omits the three-byte4967 CALL, which now also belongs to
the owned screen range; the corresponding instruction domain with that boundary adjustment is8,166. Owned ranges, executed
sites and the30,012-byte C ledger already include that instruction. This is an
explicit accounting limitation, not a masked byte difference or renewed report;
correct that report filter when the campaign is next changed. All115 main
UNKNOWN runs /seven unresolved transfers remain open. Exact ASM/relocation and
full original-contract/native aggregate gates remain separate.
