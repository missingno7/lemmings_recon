# Connected menu scroll buffer

The exact7CBC..7E75 cluster contains442 instruction bytes and six entries:
InitializeMenuScroll, DrawMenuScroll, AdvanceMenuScroll, CopyMenuScrollTile,
InsertMenuScrollGlyph and DrawMenuScrollEdge. The maintained C implementation
is c/menu_scroll.c. It uses the existing canonical raster bus and renderer,
without a converted text buffer, host glyph model or second game-state copy.
The main-image translated-code ledger union is now28,529 bytes.

## Owners and source layout

| Live DS word | Role in this cluster | Other ownership |
|---|---|---|
| 001D | MenuScrollTextStart | Initialized to49CE by7CBC |
| 001F | MenuScrollTextCursor | Live LODSB cursor, initialized to49CE |
| 0021 | UiScrollPhaseOrPromptPointer | Scroll phase here;48EB stores an end-screen prompt pointer, read at479F |
| 0023 | MenuScrollPauseTicks | Initialized0, FF sets100, nonzero values decrement |
| 1FF0 | LevelGraphicsSegment | Original DOS allocation base from1013; reused as the scroll buffer |
| 1FEE | UiGraphicsBufferSegment | Allocation-derived UI source bank |
| 1FE4 | GraphicsResourceSegment | Published before renderer calls |

The70-byte rows,16 rows and four planes occupy1180 bytes at the start of the
level-graphics allocation. Each plane has stride0460. This is the ES owner
of DI0044 during insertion; it does not consume the game header at DS0044.
The menu uses the static credit stream at DS49CE, FF pause markers and a final
CR restart. Incoming DF controls every LODSB, MOVSW and STOSB; explicit source
INC instructions continue forward even when STOSB runs backward.

Sources use UI+1000 paragraphs, with16-bit segment wrap. Two edge-frame banks
span1C10..3410 and3410..4C10. Each contains16 four-plane48x16 frames of0180
bytes. The phase-derived index is ((phase>>2)&15). The128-byte tile at4C10
contains four16-row two-byte streams and ends at4C90. The four level-group
images from the adjacent cache cluster occupy4C90..5BC0. Glyph addressing
then starts at5BC0+96*((AL-21)&FF), with mask source+40. These are source-layout
contracts, not blanket classification of unresolved bytes or loader execution.

## Literal entry behavior

Initialization sets the four control words, reads the live level segment into
ES and copies35 two-byte tile columns. Each call saves actual CX/AX; the tile
child saves DS and per-plane CX/DI on the live stack. No host variables replace
those saved words. The outer initializer increments only AL and falls directly
through into drawing after LOOP. Tile entry accepts every AL without clamping.

Drawing publishes the level segment and renders560x16 at(48,334), source0,
BP0. It then publishes UI+1000 and enters the shared7E2F tail. The tail calls
the48x16 edge wrapper atx0, rereads phase after the child, derives the second
source and falls through into that wrapper atx592. The second edge has no
invented near CALL frame. The wrapper uses BP0 and y334. Returned DS/ES and
flags remain live across every call and source-selector access.

Tick first draws the old buffer. A nonzero pause then performs DEC [0023] and
returns without advancing phase or shifting pixels. DEC rereads memory; its
bus write exposes the instruction's incoming flags, while its return exposes
the completed decrement flags. The first C comparison with a changed pause
found this ordering error and the C write ordering was corrected.

Otherwise phase advances by4. A zero low nibble copies tile column34, reads
one byte through the live cursor and handles exactly one control marker.
FF writes pause100 and consumes one following byte unconditionally; CR reloads
the start and consumes one byte. FF followed by CR/FF and CR followed by FF do
not recursively interpret that second byte. The updated cursor is stored
before the actual glyph call. Space only saves/restores DS and changes CMP
flags; other bytes wrap after subtracting21, with no printable-range filter.

Glyph insertion makes three two-byte color/mask passes and one mask-only pass.
The mask pointer is source+40, overlapping the third32-byte source extent;
no independent fourth color plane is invented. Actual saved BX/DI/CX words
feed subsequent passes. The shift then scans70 bytes backward in each of16
rows/four planes. SHL and three single-bit RCLs move the source byte left by
four; BL carries its high nibble into the next byte. BL is reset per row.
The original DEC/LOOP/ADD order determines final cursors and flags.

## Boundaries and evidence

C cores stop before the entry's actual near RET, including the shared edge
return. Adapters consume the actual caller word only on READY. Nested near
calls push and consume real continuation words. Renderer calls likewise use
actual far CS/IP words; changed near/far returns and renderer child stops keep
distinct outcomes and pending frames. With SSFFFF/SP000F, original renderer
mirror writes overwrite tightly placed far frames; both sides return the
observed changed IP/CS rather than repairing the frame.

tests/menu_scroll.py supplies finite fixtures and independent tile, glyph/mask,
shift, geometry and pause expectations. tests/verification.py supplies all CPU
execution, canonical bus access, guarded callbacks and comparisons. Lossless
packed traces retain ordered events. The worker is bounded to570 seconds and
384MiB process-tree commit inside a600-second outer envelope; each invocation
has600,000 instructions and220,000 events. Temporary DLL directories remain
under build and are owned and reaped by the parent even after a failure.

A preliminary long handoff hit the384MiB cap because VGA observation lists
accumulated across calls. It failed and earned no accepted report or mutation
credit. The corrected handoff consumes each complete stage trace after the
shared comparison, carrying RAM, latches, registers, planes and counters forward.
No observation is skipped before comparison and no device state is reset.
The connected sequences also call the existing native display-origin swap after
every initializer/tick stage, preserving actual frames and CRTC writes.

The accepted local campaign passes102 fixtures/500 comparisons,all193 own sites/
30 direct outcomes and nine completed mutation witnesses in5,187 known connected
bytes. It executes9,308,645 original instructions and compares5,735,043 ordered
events,with2,916 separately counted far-return observations. Integrated execution
covers476 sites/67 outcomes. All99 individual fixtures compare both the core
and adapter; three same-RAM sequences contribute302 further comparisons,including
an initializer plus112 ticks with the complete100-tick pause and CR restart,
and two pinned-stream sequences at other loads. Every stage has a real display
swap. The accepted complete campaign finishes in154.10 seconds.

Mutations distinguish lost DF, discarded saved DS, omitted mask-only writes,
wrong pause length,lost nibble carry,wrong plane stride,ignored changed near
return,cached phase across the first edge child and incorrect DEC write flags.
No timeout,memory/access exhaustion or incomplete native invocation earns credit.

The inherited RETF selector-EA wrap limit atSPFFFE/FFFF and the earlier
artificial VGA-stack masked-loop exhaustion remain unverified. Constructed
and pinned decoded banks do not establish upstream allocation/loader execution,
menu scheduling, native services or SDL3 integration. Local differential
acceptance and aggregate/full-game acceptance remain separate.
