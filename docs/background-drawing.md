# Background drawing bridge

The pinned5017 entry clears BX with XOR, then falls through5019's near JMP
to7E76. The5019 entry retains incoming BX. Their shared7E76..7EB1 tail
publishes liveDS:1FEE `UiGraphicsBufferSegment` directly toDS:1FE4
`GraphicsResourceSegment`, without the glyph caller's additional1000 paragraphs.
These are65 unique caller bytes/26 sites, split across5017..501B and7E76..7EB1.
UNKNOWN501C and the intervening unrelated code are outside the translation.

The tail initializes CX=4. Each row pushes BX,CX,BX in that order, calls the
same relocatedCS:8822 renderer for x=0, then restores the innermost live BX
and calls it for x=320. Both requests use SI=0,DX=320,CX=0268 andBP=000C:
two source planes,104 rows, clipping enabled. Incoming DI flows to the child.
The second call is followed by live POP CX,POP BX,ADD BX,104,LOOP. LOOP
changes CX without changing flags. A dirty-map/stack alias can therefore change
the next column's row, the next row's origin, or the number of rows. The
implementation must not replace this with a fixed four-iteration loop.

The two real relocation words at7E93 and7EA8 must retain the pinned targets.
Each far CALL pushes actual CS then7E95/7EAA. Every returned renderer field,
including DS,ES,SP and flags, flows into the caller. A changed child near return
stops inside the renderer; a changed far return stops before caller MOV/POP
effects. The logical core stops before7EB1 RET. The adapter alone consumes the
live outer near-return word. Memory is the canonical1MiB image; high bytes of
words use physical-address+1 with20-bit wrap, and SP wraps16 bits between words.

`tests/background_drawing.py` constructs RAM/source bytes and device planes;
it does not boot the game or infer resource allocation extents. It checks all
three entries, both DF directions, full640x350 drawing, clipped/no-draw tiles,
stack and physical wrapping, distinct DS, VGA source/stack and live saves.
Original caller observations independently check all eight ordinary renderer
requests and returns. Selected ordinary/full/row/layout/DS/A20 fixtures also check each executed
tile body with a separate plane-footprint model. VGA source/stack, live-save
and changed-return fixtures rely on the original/native comparisons. Original/native comparisons cover all CPU fields, phase-defined flags,
full RAM, ordered byte/port accesses and full device state. Device-order hashes
retain IF/DF; the whole-bus trace separately checks arithmetic flags with their
instruction-phase masks. Oracle/guard failures never count as mutant detection.

The test parent owns temporary DLL directories. Workers start suspended until
Windows Job limits are installed:180 seconds,384MiB per process,640MiB per tree;
compilers have60 seconds/256MiB. Each original call has500000 instruction steps,
and traces have600000 bus/200000 device events. Callback guards terminate the
disposable worker; the game's original loop acquires no artificial budget.
Native hardware timing, scheduled interrupts, arbitrary provider changes and
hardware stack-segment-limit faults remain outside these constructed checks.
Scoped acceptance results are recorded only after the corresponding gate passes;
older native reports and full terrain acceptance still require their own refresh.

The scoped native gate passes36 fixtures at both core and adapter boundaries,
covering26 caller/305 integrated sites, all three caller edges and six completed
compiled mutants. On640x350 geometry the first tile is40 bytes wide and the
second39 bytes: the original right-edge test trims another8 pixels on equality.
The bottom row has38 visible lines. These dimensions are asserted independently
of the native output. A16x8 dirty-map fixture changes the saved loop counter to1,
so only one two-tile row executes; separate fixtures alter each saved row word.
