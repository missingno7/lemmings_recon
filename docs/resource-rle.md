# Resource byte-run decoder

DecodeResourceRle is CS:1B42..1B78: 55 instruction bytes with closed local control
flow. c/resource_rle.c provides its explicit segment/cursor/value/count/flag core
and a machine-register adapter only for original-code tests. The maintained ASM
and all references use its ledger-owned name and remain byte exact. The higher
1A7B caller invokes it repeatedly between resource-dependent transformations;
those caller/data-layout contracts are still open.

The control byte is loaded with LODSB. 80 terminates immediately, preserving the
incoming CX if no packet has run. Controls 00..7F copy control+1 live bytes using
MOVSB. Controls 81..FF repeat the following byte (1-control) modulo 256 times,
which gives counts 128..2. CX reaches zero after a complete packet. Input bytes,
including future controls, are read from live memory rather than staged buffers.

The routine preserves incoming DF. SI and DI update by +1 or -1 modulo 65536;
DS never advances when SI wraps. After each output byte, a zero DI causes ES to
increase by 1000 modulo 65536. The check is specifically DI==0 after the update,
including when DF is set; it is not a generalized backward-segment rollover.

The original segment update is MOV AX,ES / ADD AX,1000 / MOV ES,AX. It replaces
the entire AX value. In a repeat run, later STOSB instructions therefore emit
the low byte of the updated segment instead of the original repeated byte.
For example, ES=4513 and DI=FFFF with forward DF emits the first byte from the
packet, advances ES to 5513, and emits 13 for the rest of that same repeat run.
The next repeat packet reloads its byte normally. The native core retains this
bug, and also retains the resulting high AX byte after the final terminator load.

Final flags come from CMP AL,80 equality: CF/AF/SF/OF clear, PF/ZF set, while
nonarithmetic flags including DF remain unchanged. No final arithmetic flag is
excluded from comparison. BX/DX/BP/DS/SS/CS are unchanged; SI/DI/ES/AX/CX expose
the original outputs. Near return reads the caller's live word with physically
contiguous second-byte addressing even if its starting offset is FFFF.

## Bounded verification and remaining scope

tests/resource_rle.py compares the original identified interval with native C
in 303 constructed cases at three loads. All 29 instruction sites and fourteen
branch edges execute. Full 1 MiB memory, every register and all defined flags are
compared. Cases include every control byte, both DF directions, source and output
boundary offsets, multiple segment rollovers, segment-word wrap, literal and repeat
overlap, mixed packets and three stack-wrap points. A live literal overlap changes
an unread input byte while keeping the terminator intact; staged copying would
produce a different result.

Sixteen cases use statically extracted real VGASPEC0..3.DAT streams. The 1A5A
filename selection and section destination at offset10, followed by 1A7B's source
offset38, identify image offset28. A static packet parser locates four terminated
streams in each first DAT section; each expands to 14,400 bytes and the fourth
ends exactly at the image end. Cases use the original cursor positions and output
offset8000. Assets stay private; reports record hashes/spans rather than proprietary
stream bytes. This evidence verifies these streams, not the surrounding renderer.

Three compiled mutations are detected: shortening literals, omitting the segment
advance, and preserving the repeat byte across that advance. Original execution
has a one-million-instruction budget; the standard runner caps the suite process
at 120 seconds including native calls. Streams terminate, TF is clear, interrupts
are quiescent, and instruction/active-return bytes remain intact. The domain uses
twenty-bit mapped addresses and original sixteen-bit cursor/segment effects.

The original and native decoder have no missing-terminator or output-size guard;
none is silently added. These fixtures establish the local instruction contract,
not complete real-resource format or graphics ownership. Static VGAGR section
identities alone do not establish RLE input offsets; the verified special-resource
streams above are selected by a separate original filename/caller path.
Higher resource metadata, transformations, alias closure, rendering, retry UI and
fatal cleanup remain unported or unresolved. No original game boot is used.
