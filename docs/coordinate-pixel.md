# Coordinate pixel sample

`PrepareCoordinatePixelSample` at 6141..616F is a closed 47-byte/23-site leaf.
Its five known callers are 2313, 28C4, 28D3, 28E2 and 28F1. It receives Y in
BX and X in CX, whereas the 5DC6 sibling reads a record through DS:SI. This
helper does not clamp a negative wrapped row result.

PUSH BX and PUSH CX save the original coordinates in actual SS memory before
ES becomes A000h. DI receives BX-10h with 16-bit wrap. PUSH DX precedes the
D0h multiplication, then POP DX consumes the live word. DI receives the low
product, and BX receives the still-live input CX. Three logical shifts divide
CX by eight for the horizontal byte offset. ADD DI,CX and ADD DI,4A40h form
the wrapped destination offset.

AND BX,7 selects the live DS `PixelBitMasks` table. ADD BX,547Ch supplies the
final arithmetic flags; the subsequent byte read replaces AH while AL retains
the low product byte. POP CX and POP BX then consume their actual save words.
They do not restore cached input coordinates. A push or provider/device access
can change the table, a later restore or the outer return word. The table index
comes from the original register CX, before the coordinate restores.

The logical core stops before RET at 616F, returning AX, the live restored
BX/CX/DX, DI, ES, SP and flags. The register adapter consumes the actual near
return word. DS, SI, BP and SS remain unchanged. IF and DF remain unchanged;
there are no string operations, ports or branches in this leaf. No VGA latch
read is implied merely by setting ES=A000h, but DS or SS may themselves select
VGA-backed memory through the optional raster bus.

All table and stack accesses use the same canonical memory and optional bus.
Word high bytes use physical+1 with 20-bit wrap, while SP and address arithmetic
wrap at 16 bits. Missing memory callbacks fall back to ordinary RAM. Intact
executing code, TF clear and quiescent IRQs are the verification domain; live
interrupt scheduling and complete parent-state initialization remain separate.

`tools/difftest.py coordinate_pixel` passes 34 fixtures at both pre-RET and
actual-RET boundaries, all 47 bytes/23 sites and no branch edges, with 952
ordered callback events and four completed mutants. Fixtures cover all eight
mask indexes, negative/wrapped Y without a clamp, residual AL, DS table
changes, live BX/CX/DX/RET restores, provider writes during table reads,
DS/SS VGA backing, physical/offset word wrap and null-bus ABI equality.
Mutants exercise an incorrect clamp, cached coordinate restores, discarded AL
and a prefetched return word. Exhaustion and callback errors fail verification
and cannot count as detection.

The worker uses a 180-second deadline, 384 MiB process/640 MiB tree commit,
80 original instructions and a hard 128-event callback/device budget per call.
Guard exits are 86 for exhaustion and 87 for callback error. Workers exit
before temporary DLL directories are removed. Exact scope and current input
hashes are in build/coordinate-pixel-differential.json. Its 47 translated bytes
are separate from the record-input sibling and do not close its callers.
