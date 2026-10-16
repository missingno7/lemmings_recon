# Status display dependency frontier

The current static3AC8 caller has533 known bytes/174 sites in[3AC8,3CDE),
with UNKNOWN3B08 retained. Known callers are01C2 and049E. Its children are
796F (scoped native minimap column),7A5A,417B,762A,780D and789E;417B
calls7708. These dependencies are separate from candidate selection3CDE.
A direct selection-to-action handoff does not verify the intervening3AC8 call.

The next independent leaf is7A5A:350 known bytes/168 sites in[7A5A,7BB8),
no child calls or UNKNOWN holes, and RET7BB7. It reads live DS:0000 and
DrawingOrigin at1F76, sets ES=A000, programs VGA through3C4/3CE and live SS
mirror words, and draws through the declared VGA bus. CLI/STI phases, incoming
DF, actual stack aliases and returned ES remain part of the contract. It needs
no font table. Check fresh graph tree/bottom-up views before implementing it.

The other UI leaves retain separate domains:780D is145 bytes/60 sites with
RET789D;789E is98 bytes/40 sites with RET78FF, temporarily sets DS=ES=A000
and restores actual saved DS. Its18 pairs of MOVSB retain DF. 762A is222
bytes/105 sites, with RET76DA/7707. 7708 has256 known bytes/118 sites and
UNKNOWN7765,776F,7792,7799,77A0; its returns are77FD/780C. The last two
routines read their source segment through the live DS:1FEC word. None of
these facts establish native rendering or IRQ timing acceptance.

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
