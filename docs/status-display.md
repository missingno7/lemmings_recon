# Status display contracts

The current static3AC8 caller has533 known bytes/174 sites in[3AC8,3CDE),
with UNKNOWN3B08 retained. Known callers are01C2 and049E. Its children are
796F (scoped native minimap column),7A5A,417B,762A,780D and789E;417B
calls7708. These dependencies are separate from candidate selection3CDE.
A direct selection-to-action handoff does not verify the intervening3AC8 call.

The7A5A viewport leaf now has scoped native acceptance over350 bytes/168 sites,
and the two-CALL3AC8..3ACD prefix composes it with796F through actual frames.
The prefix stops before3ACE and adds only six caller bytes. The separate
StatusDisplayAfterMinimapViewport entry owns the separate native suffix over
527 known bytes/172 sites, excluding UNKNOWN3B08. The full native entry composes
the prefix and suffix without another guest frame at3ACE.
See minimap-viewport.md for live coordinate/phase, SS, VGA, DF and IF contracts.

The two icon leaves also have scoped native acceptance:780D is145 bytes/60 sites with
RET789D;789E is98 bytes/40 sites with RET78FF, temporarily sets DS=ES=A000
and restores actual saved DS. Its24 pairs of MOVSB retain DF; see status-icons.md.
The closed glyph leaves now have scoped native acceptance:762A is222
bytes/105 sites, with RET76DA/7707. 7708 has256 known bytes/118 sites and
UNKNOWN7765,776F,7792,7799,77A0; its returns are77FD/780C. The last two
routines read their source segment through the live DS:1FEC word. These scoped
leaf checks remain separate from the complete caller gate and live IRQ timing.

## Source buffer and initialization

The successful DOS allocation path1007 requests5571 paragraphs at100C.
It stores the returned base in1FE4/1FF0, then derives successive segment words.
The1FEC word receives base+2F02 (modulo16 bits) at102B;1FEE receives
base+2F7E at1031. Their nominal partition difference is7C paragraphs, or
7C0 bytes. This static partition does not prove successful allocation, writable
extent for every provider/alias, or a permanent bound on unchecked consumers.

In LoadMainResourceSections58D2,LoadDatResource58E0 starts MAIN.DAT. The
following decodes58F9/590F advance to zero-based sections1/2;5972 is the
separately established section5 PC-speaker payload. After the590F decode and
57D1 helper,5931..593C copies3E0 words from the live GraphicsResourceSegment
at1900 to live[1FEC]:0000. After decoding section6 at598A and another57D1
call,59AC..59B7 copies720 bytes from the live source1900 to[1FEC]:00A0.
This latter path is taken when DS:200E equalsFF:597B skips it on JNZ.
With DF clear and nominal segments it overwrites00A0..07BF, preserving the
firstA0 bytes. With DF set, REP strings and actual saved DS must follow the
original order. Do not replace either copy with a host font or cached asset.
Source contents after the intervening helpers, selector-to-glyph mapping,
live segment providers and wider initialization remain to be connected.

## Text and parent state

417B scans bytes with LODSB until a live zero, saving AX/SI around each7708
call and incrementing AH as the display position. Its source2083 begins a
stored40-character status line whose initial terminator is20AB. Selection
clears only2083..208D, then replaces seven label bytes and up to three count
bytes. It does not insert a terminator after its own11-byte field. Therefore
417B must retain the following status fields and live termination/DF behavior;
an eleven-character host string would change the caller contract.

3AC8 builds exactly100*byte[0046] through shifts and additions, then divides
by byte[0047] only when that divisor is nonzero. A byte DIV overflow remains
a processor exception frontier; no percent-domain clamp is justified. If the
divisor is zero, the low byte of the undivided product continues. It stores
0040 and updates209C..209E, then renders2083 through417B. Selector snapshot
0083 and cadence byte0084 are also read by input paths; do not treat them as
private renderer state. Their producers, count/release triples, actual child
returns and platform seams must be accounted for before accepting3AC8.


## Glyph selector contracts for the next leaves

The ledger names the live1FEC segment word StatusGlyphBufferSegment; the
stored word and its surrounding UNKNOWN classification are unchanged.
7708 selects `%` atA0, `:` at2B0, digits at`D0 + 30h*(AL-30h)` and
uppercase letters at`2E0 + 30h*(AL-41h)`. Signed range checks reject80..FF.
Each selected glyph uses three sequential16-byte passes, with Sequencer map
masks0F,02,08; the second pass separately changes Graphics Controller index1.
Z starts at790 and its forward48-byte source ends at7BF. Space instead
blanks16 rows with no glyph reads; other rejected selectors return after
setup and actual POP DS, preserving incoming IF because no raster STI ran.
Drawn glyphs and spaces end with IF set. All three paths retain live saved
DS and actual RET;5 skipped UNKNOWN bytes remain unresolved.

762A receives destination slot in AL and count in AH, restored from actual
POP AX after setup. Nonzero counts use quotient/remainder by ten without
normalization:source halves are`10h*floor(count/10)` and
`8 + 10h*(count mod 10)`, each eight bytes. Values100..255 can read beyond
the nominal ten-digit prefix, into the next initialized graphics; keep those
reads. Zero count blanks both eight-row cells without reading glyph data.
Both routines use live StatusGlyphBufferSegment and never clear DF. The
forward extent calculations above do not bound reverse LODSB reads.

417B's NUL scan now has scoped native acceptance. Its40-byte initial status text is no runtime
bound: live strings, DF, actual saved AX/SI, near child returns and wrapped AH
position count remain visible. Next connect the remaining3AC8 state/exception
contracts. The broader
LoadMainResourceSections decode/copy pipeline remains separate verification.

The glyph destination is `AH + 1E42h + live DrawingOrigin` with16-bit wrap;
there is no doubling. Two passes PUSH/POP DI on live SS, while the third pass
has no save and leaves DI advanced by16 rows. Drawn glyphs read DS from1FEC
after setup; actual POP DS restores the saved word on every path. A drawn glyph returns
DX=3C4, SI advanced by48 DF-sensitive bytes and AH=08; rejected and space
paths retain their own AX/SI/IF residuals. Count destinations instead use
`2*AL + 212Eh + live DrawingOrigin`. Actual second POP AX supplies the remainder
half, so that source can change independently after the first eight rows.

The bounded count gate passes270 fixtures at core/actual-RET adapter boundaries:
all256 AH counts plus focused aliases,105 sites,twelve branch outcomes,48,512
ordered events and seven completed mutants. The character gate passes269
fixtures at both boundaries:all256 AL selectors,118 sites,thirty jump outcomes,
30,662 events and nine completed mutants. Independent source/plane replay checks
both8-row count cells and all three16-row character passes; VGA-stack aliases
retain full CPU/native device comparison. Reports are
build/status-count-differential.json and build/status-glyph-differential.json;
matching input hashes own acceptance. Their478 known bytes exclude all five
UNKNOWN holes and do not accept initialization, allocation, IRQ timing or callers.

The417B connected gate passes18 fixtures at core/actual-RET adapter boundaries:
17 new caller bytes/11 sites/three jump outcomes,34,102 ordered events and seven
completed mutants. It exercises both glyph RET sites, changed child targets
before caller POPs, actual saved AX/SI/DS and source/NUL providers, DF, a physical
FFFFF-to00000 outer-return word, the complete stored40-character line and a
46-character AH-wrap scan. Independent plane replay covers the full stored
line and a mixed glyph/space/digit string. The parent has no scan-length clamp.
The report is build/status-text-differential.json with matching input hashes;
it adds17 bytes without recounting its256-byte child. The resource producer
remains a separate frontier. The connected3ACE caller gate is below.

## Shared display acknowledgement state

The ledger now names the remaining release/icon snapshot and refresh bytes.
0065/0066 belong to the displayed release minimum0064;0068/0069 belong to
the mutable release setting0067. These follow the same three-byte layout as
the already named action-count fields. A nonzero live value equal to its
snapshot skips drawing and leaves the counter unchanged. Otherwise the caller
draws; if the counter was exactly2 it first copies the live value to the snapshot
and writesFF to the counter, then INC makes it0. Other counter values increment
with byte wrap. A zero live count always redraws even when its snapshot is zero.
No elapsed-time or arbitrary-count normalization belongs to this state.

StatusIconDisplaySnapshot0083 stores the old selector used by RestoreStatusIcon;
StatusIconRefreshCounter0084 advances only while the current selector differs.
The caller draws the current outline and restores the old icon before checking
counter2 and acknowledging the new selector. A same-selector pass leaves the
counter untouched. Initializers0427/3A52 set snapshot3;3A1B sets counter0.
The39CE initializer sets both release snapshotsFF and their counters0.

These bytes also own input gates. Mouse3F15/3F5C and keyboard40B5/40CD allow
action selection only when0084 is0; release adjustments403D/406C require0069
to be0. A renderer-private snapshot or counter copy would break that sharing.
The minimum0064 and live setting0067 are header/input-owned values, already
named in the ledger; no new array extent or provider scheduling is inferred.

## Complete caller contract and scoped native verification

The maintained status_display.asm module owns3AC8..3CDD in unchanged physical
order. UNKNOWN3B08 remains outside the known instruction ranges. The suffix
starts3ACE and returns at3CDD; the full entry reaches it by fallthrough after
the two minimap CALLs, without introducing another stack frame.

StatusCompletionDisplayValue names DS:0040, which is also read by results-screen
code471D/48BD/48F6/504A and initialized to100 at0314. StatusPercentDigits names
the three bytes209C..209E inside the shared status line. The exact100 path writes
all three bytes. Other values update only209D/209E, so a leading1 at209C can
persist; the39CE initializer separately writes a space there at3ABD. Do not
silently clear that byte on every display update.

The DIV at3AED is byte sized and uses the live CL loaded from0047. Zero skips
DIV; nonzero quotients above255 fault. The portable boundary must retain the
pre-DIV state and expose this processor exception without inventing an INT0
handler or frame. Successful DIV leaves arithmetic flags undefined until later
instructions define them. Native data/return and device providers remain live
through the subsequent text, icon and ten count CALLs.

The suffix gate passes29 fixtures at both logical-core and actual-RET adapter
boundaries:527 known bytes, all172 sites/all73 jump outcomes,48,738 ordered
bus events and eight completed mutants. It checks the full stored40-byte line,
all ten count slots in literal order0/1/4/9/2/6/5/7/3/8, zero redraw, snapshot
skips, counter2 acknowledgement and byte wrap, live counter/selector providers,
signed old-icon aliases, DF/IF, actual saved DS and changed child returns.
The VGA-backed stack fixture stops at its observed count-return target3BAB;
it does not silently continue a damaged frame. The pre-DIV error boundary is
compared at both APIs; a separate two-byte original probe observes INT0.

The complete3AC8 entry passes10 focused handoff fixtures (13 comparisons),
with163/174 owned sites,68 observed jump outcomes,43,068 ordered events and
three completed mutants. This scope checks actual minimap child frames, all
returned register roles and DS into the suffix, no frame at the fallthrough,
changed prefix/child targets, full-line/count output and the live outer RET.
The suffix's separate exhaustive site/outcome matrix supplies the remaining
body paths; the wrapper report does not claim to execute all174 sites.
MINIMAP_BOUNDARY5 carries the prefix's actual continuation, entry marker3AC8
and raw child status; suffix CHILD_STOP4 keeps its own child entry/status.
Only READY consumes the outer RET. No INT0 handler/frame, IRQ schedule or
native device timing is inferred.

Reports are build/status-display-differential.json and
build/status-display-full-differential.json; their exact input hashes own
acceptance. The two ranges exclude UNKNOWN3B08. The full entry's533 known
bytes overlap the six-byte prefix and527-byte suffix, adding only527 unique
main-image C bytes to the ledger (17,573 to18,100). Shared DS:0040 and the
snapshot/refresh fields stay in canonical memory. This is scoped acceptance,
not a refreshed aggregate campaign or complete gameplay.
