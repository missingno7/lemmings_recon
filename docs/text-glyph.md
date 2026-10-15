# Text glyph producer at 4D78

DrawTextGlyph occupies 74 bytes at 4D78..4DC1, with 32 caller sites and one
conditional branch. A space (AL=20) returns after CMP, preserving every incoming
field except arithmetic flags. Other bytes subtract 21 with byte wrap, clear AH,
and select source offset `(5BC0 + 96 * index) & FFFF`. There is no character range
check. DI is source+40, also wrapped. The graphics segment is the live DS:1FEE
word plus 1000 paragraphs, written to live DS:1FE4 before BP is pushed.

CH and CL supply top and left cells. Each is extended to 16 bits and shifted
left four: coordinates are multiples of 16. CX becomes 0310 (16 rows, three
planes), DX becomes 0010 (16 pixels), and BP retains the caller's control bits.
SHL by four leaves OF/AF undefined; tests must not claim either bit. The other
defined flags and all control bits remain observable at stack/bus accesses.

PUSH BP precedes the far CALL at 4DBB. The far segment operand at 4DBE is a real
unpacker relocation targeting 8822 in the loaded code segment. The native caller
uses the existing logical planar core on canonical memory. It consumes the live
IP and CS return words, stopping at any changed target. Only a nominal return
to 4DC0 executes the live POP BP. READY leaves the outer RET at 4DC1 for the
register adapter. Renderer continuations, changed inner near returns, missing
byte-port providers and native hardware/IRQ ownership retain their explicit seams.

UiGraphicsBufferSegment names the DS:1FEE word assigned at 1031 and consumed by
5945/5949, the screen producers and glyph paths. Its allocation starts at the
DOS-returned block plus 2F7E paragraphs. This name does not establish the full
resource extent, successful allocation or all buffer ownership. It is not a
shadow copy of graphics state. The renderer may subsequently replace DS/ES.

The separate original-only and native gates in tests/text_glyph.py use 264 prefix
fixtures (including all 256 byte selectors and null-bus native repeats) and 45
integrated fixtures at both core and adapter boundaries. They compare the
pinned instructions with constructed RAM. They cover all byte selectors at the
prefix, then the composed renderer, live frames, full memory, ordered accesses,
defined flags, VGA/device state and independent whole-plane drawing footprints.
The existing read-hook-free original RETF observation is retained without opcode
or target patching. Stack-limit faults are outside this bounded domain.

Each disposable worker is capped at 120 seconds, 384 MiB process commit and
640 MiB tree commit. Native callbacks exit on access/service failure or exhaustion;
these failures never count as mutant detections. Parent-owned DLL scratch is
removed after success or failure. Aggregate C coverage and complete terrain
acceptance remain separate obligations.

Four compiled mutants test the glyph stride, segment addition, live saved BP and
changed far return. The caller contributes 74 bytes/32 sites, with both JZ
outcomes observed; the integrated executed-site union is reported separately.
An unrestricted VGA-stack drawing fixture exhausted the finite access budget and
was rejected. The accepted VGA-stack case takes the finite clipping/no-draw path;
this does not accept arbitrary device-backed stacks or a full VGA hardware model.
