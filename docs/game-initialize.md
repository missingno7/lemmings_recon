# 03E7 initializer frontier

The exact 03E7..04CF controller has233 known bytes and72 sites. Its direct
children now have scoped native implementations. It is the first CALL from the
still untranslated game entry00FB; the controller and full gameplay remain open.

## Tested parent/child checkpoint (03E7..046A)

The native `lmn_initialize_game_core` implements132 bytes of this controller
and composes its actual0462/0465/0468 CALL/RETs through video, base-palette and
timer-calibration cores. It stops at046B before level initialization.
Twenty-four bounded comparisons cover37 parent sites,295 decoded dependency
sites and six completed numeric mutants. They preserve ordered DS stores, both
live PUSH SS/POP ES frames, incoming DF, DS/SS aliases,20-bit physical wrap,
planar VGA reads/writes, BIOS frames, packed/RGB palette output and timer
reloads. In SS-alias cases, timer calibration reaches the still-unbound dynamic
display-probe target at1407; that stop remains explicit. The two string
clears retain their literal ranges and leave CX exhausted.

Connected coverage is823 known bytes:132 newly translated parent bytes plus691
already translated video, detector, timer and palette code. The24
original/native comparisons execute451,671 original instructions and compare
451,201 ordered bus events. When the forward clear wraps through physical
address zero, it clears the live INT10 vector before the first child call; the
resulting unbound BIOS stop is preserved.

The rest of the controller remains untranslated. Continue from046B through
level initialization and later children, carrying each live frame and platform
service. This checkpoint does not initialize a complete game session.

## Memory ownership before the child calls

The controller sets view origin pixels/bytes to0218/0043 and pointer position
to150/100, then writes creation, action, status and foreground state. Preserve
every original byte store and its order rather than replacing this with a host
state structure. It clears AL while retaining AH before both SS clear loops.

At044A, actual PUSH SS/POP ES selects the first destination: offset0012 with
count42A0. With DF clear, this clears SS:0012..42B1, the existing interaction
cell-map region. Its length is41*416 bytes, matching the cell writers' row
stride; it is not the entity-record array, which starts at DS:0088. This
arithmetic does not establish coordinate bounds for unchecked cell consumers.

At0456 another actual PUSH SS/POP ES selects offset42B2 with count0642.
That length is2*(1+800), precisely the two dirty maps at42B2 and45D3, each with
a leading byte and800 cells. The clear ends at48F3, not at the initial stack
top4AF4. Incoming DF reverses strings from their actual starting offsets and
must remain live. Saved words can be changed by aliases; ES is the popped word.

## Child and platform sequence

The near calls, in order, are0FB2,52F4,15AD,36B6; then410F,30A6,5377,482F,
81CC,39CE,1644,3944,7BB8,7900,3AC8. The first three now compose with their
actual CALL/RET words;36B6 is next. Carry returned registers/segments and
bridge each declared boundary explicitly. The relocated game/visibility segment operands
remain distinct from live DS/SS.

Between36B6 and410F, only an exact FF mouse-disabled byte skips BIOS mouse
service33h. Otherwise AX4/CX150/DX100 are supplied and returned state stays live.
The game-timer installer uses its full DOS/IRET/PIT contract. Existing special
resource, fatal, changed-return and unsupported-provider seams remain scoped.

## Final foreground wait words

The controller zeros CX/DX and clears TimerChainFlag1FCF, waits for exact FF,
clears it again, then decrements CX and decrements DX only when CX becomes zero.
It polls the live flag after each decrement. After the next FF it performs
ADD CX,CX, ADC DX,DX, NEG DX, and stores CX/DX to DS:1FFE/2000. This is the
literal split-word sequence; do not replace it with an assumed32-bit negation.
The actual RET is at04CF. The foreground0164..0183 consumer reads both words
and has an installer fallback when its low-word loop reaches a zero high word.

Constructed IRQ schedules should cover both flag waits, counter wrap, actual
carry into ADC, the final high-word NEG and live frame changes. Test bounds
must fail verification rather than introduce a timeout into the game. Native
device scheduling and the complete00FB/frame loop remain separate obligations.
