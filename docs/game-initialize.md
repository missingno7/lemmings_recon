# 03E7 initializer frontier

This is a static contract for the next C connection, not an implementation or
new execution claim. The exact 03E7..04CF controller has233 known bytes and72
sites. Its direct children now have scoped native implementations. It is the
first CALL from the still untranslated game entry00FB.

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
81CC,39CE,1644,3944,7BB8,7900,3AC8. Each needs its actual CALL return and
returned registers/segments. Current APIs differ in whether they leave or
consume the outer RET, so bridge each declared boundary explicitly. The
relocated game/visibility segment operands remain distinct from live DS/SS.

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
