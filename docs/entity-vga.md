# Entity pixel VGA helpers

`ConfigureEntityPixelReadback` at 5D94..5DC5 (50 bytes, 18 sites) and
`ExchangeThreeEntityPixelBytes` at 5EBA..5F0E (85 bytes, 39 sites) are closed
leaves in the normal simulation tree. The setup call at 1F23 precedes the
record loop. The exchange calls at 2441, 253A and 2545 follow pixel-address
preparation and the callers' own mask construction. Neither leaf has a branch.
The 5F0F drawing caller uses the same address child but has its own stores and
save frames; these helpers do not establish complete parent readiness.

The setup writes and outputs these word pairs in order: SS:0008=0F02h to
03C4h, SS:0000=0805h to 03CEh, SS:0006=0807h to 03CEh, and SS:0004=0802h
to 03CEh. These select all four write planes, VGA read mode 1/write mode 0,
plane-3 care and plane-3 comparison. Each actual SS store precedes its OUT;
other device registers remain live. AX and ES become A000h and DX returns
03CEh. Finally the live DS word `EntityPixelRowPitchBytes` at 0004 receives
00D0h. This is the stride read by the simulation's vertical pixel tests;
it is distinct from the general renderer field at 66F4h. Flags and remaining
registers are unchanged. DS/SS aliases can overwrite mirror or return words.
With DS=SS, the last stride store makes the SS:0004 mirror differ from the
already-programmed VGA compare register. The port is not output a second time.

The exchange sets GC0=0, GC1=0Fh and GC3=0 using the live SS mirrors at
000Ah/000Ch/0002h, then sets ES=A000h and clears IF. Its three original masks
are incoming BH, BL and CL. For each byte it reads ES:DI, retains that read
value in the corresponding register byte, sends the original mask through
SS:000Eh and GC8, then writes that same mask with STOSB. DI steps with DF.
Incoming VGA mode, read map/compare/care and Sequencer map mask are not reset.
The read loads latches before the mirror writes, OUT and pixel write; those
intermediate writes can themselves hit VGA through SS aliases. No read or
mirror access may be removed as redundant.

BX returns the first and second read bytes in BH/BL; CL returns the third
read byte and CH is unchanged. AH and AL both return the original third mask.
DI advances or retreats three bytes with 16-bit wrap, ES=A000h, DX=03CEh.
DS, SI, BP, SS and SP remain unchanged at the core boundary. XOR AX,AX sets
the final arithmetic flags (AF is undefined); the trailing STI always sets
IF, including when entry IF was clear. All device callbacks see flags at
their original instruction phase. Live provider/device changes to RAM remain
visible to later memory reads.

The logical cores stop immediately before near RET. Adapters read the actual
SS:SP return word after all stores and outputs; mirror, DS-stride, VGA and
provider aliases can affect that word. Word accesses issue low then high
physical bytes with 20-bit wrap, including at offset FFFFh. Offsets and SP
otherwise wrap at 16 bits. The optional `LmnRasterBus` preserves registers
and owns planes/latches and ports; missing memory callbacks fall back to RAM
and a missing OUT callback provides only a constructed no-op-port domain.
It does not implement a VGA card. The native game must supply its device.

The C contract covers intact executing code, TF clear and quiescent IRQs.
Installed interrupt scheduling and physical VGA timing remain separate work.
All record, mirror and stack accesses use the canonical memory image, without
converted state or a cache of emulated game memory.

`tools/difftest.py entity_vga` passes 50 fixtures: 16 setup and 34 exchange,
each at the pre-RET core boundary and actual-RET adapter boundary. All 57
original instruction sites execute, with no branch edges and 2,180 ordered
bus events compared. The gate checks every register, defined flags, complete
1 MiB RAM and four-plane device state. Independent plane calculations cover
disjoint exchange cases with the live mode/map/compare state. Fixtures also
cover actual setup followed by exchange, SS=A000 mirrors and returns, stale
DS=SS mirrors, overwritten RET, DF and DI/physical wrapping, and null-bus RAM.
Five completed mutants cover care output, DF, omitted latch reads, prefetched
RET and preserving entry IF instead of the original STI behavior.

The worker has a 180-second deadline and 384 MiB process/640 MiB tree commit
limits. Original calls stop within 100 instructions. Callback/device traces
are capped at 128 events; native exhaustion exits 86 and callback errors exit
87. Neither failure can count as mutant detection. Temporary DLL directories
are removed after workers exit, including failures. The scoped report is
build/entity-vga-differential.json with exact input hashes; it does not renew
older aggregate reports or establish complete simulation/device acceptance.
