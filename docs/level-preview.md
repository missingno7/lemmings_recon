# Level preview sampling, 7EB2..80FC

DrawLevelPreview is the 587-byte, 278-instruction leaf called at4621 after
RedrawLevel. Its caller sets DrawingOrigin1F76 and DrawingPageByteOffset1F7A
to zero before entry, then preserves the upper screen while drawing briefing
text below it. This is a preview producer, distinct from the minimap routines.
The native leaf does not yet supply the surrounding4566 briefing controller.

## Canonical source, destination and VGA contract

PUSH DS occurs before both live DS coordinate reads. DI becomes their wrapped
sum plus064F; SI starts at4F22. Six literal word outputs establish Sequencer
map mask0F, set/reset0, enable set/reset0, graphics mode0, OR operation10 and
bit maskFF. Each SS mirror write precedes its output. DS and ES becomeA000.

The ordinary path has39 rows of52 output bytes. Every output position visits
planes0..3, sets Sequencer map mask1/2/4/8 and Graphics Controller read map0/1/2/3,
then reads four consecutive source bytes into CH,CL,BH,BL. Source bits5 and1
become successive output pixels, starting at bit7. In source-byte order:

```
output = (a[5], a[1], b[5], b[1], c[5], c[1], d[5], d[1])
```

After the final OR sets byte-result flags, CLI precedes the destination read
and write. That read loads the four VGA latches; the write ORs the sampled byte
with the selected plane's old destination. The read is not redundant. STI is
unconditional after each plane store. Source/destination overlap remains live:
the native code reads the selected plane at each actual phase, without a
precomputed image or source snapshot. An external fixture changes plane3 while
plane0 is being published to witness this ordering independently.

SI advances four bytes and DI one per output position, even with DF set. After
each row, actual saved SI and DI are popped and incremented by0340 and0050.
For an ordinary entry this samples39 groups of four source rows and writes a
416-pixel-wide,39-row preview at screen byte15,row20. Literal addresses and
pitches are retained, including reads across any logical image-row boundary;
there is no added crop or clipping. DF remains unchanged.

## Live saves and boundary state

The outer count, row source, row destination, inner count and word-output port
are actual SS stack words. Counts are popped before DEC/JZ, so C uses their
returned values instead of fixed host loop bounds. Each plane's Sequencer
output temporarily changes DX to03C4; the popped DX selects the subsequent
read-map output, including a provider-altered port. Mirrors at SS0000/0002/
0008/000A/000C/000E/0010 retain their original order and alias effects.

The final POP DS consumes the original live saved word. ES staysA000 and BP
is preserved. CX is zero at normal completion; flags are those of the final
DEC, with CF inherited from the last source-row ADD and IF set by STI. AX and
BX retain the last plane's sampled/destination and source bytes. Returned SI,
DI,DX and DS depend on actual saves, not an entry-state restoration shortcut.
Word accesses retain physical20-bit wrapping of the high byte; address
calculations retain16-bit offset wrapping.

The normal core returns before RET80FC. Its adapter consumes the actual outer
near word and advances SP. Missing word output stops before the first actual
OUT7ECC, after PUSH DS, both coordinate reads/arithmetic and the SS0008 mirror
write; it does not invent a return. Read/write callbacks use the existing
canonical RasterBus ABI and ordinary-RAM fallback. A native VGA service remains
required for planar hardware semantics; this leaf does not implement scanout.

## Verification and open domains

tests/level_preview.py supplies fixtures, finite external memory changes and an
independent pixel-index/whole-plane model. Original instruction execution,
canonical access, guarded native callbacks and state/event comparison all use
tests/verification.py. No additional CPU, bus or comparison engine was added.

Full ordinary geometry runs at three loads and with DF/IF variations, exact and
forward source overlap, wrapped destination and wrapped coordinate sums. Every
source lane in each plane sees all256 byte values at the ordinary three-load
entries. The pixel model updates live expected planes in phase order and checks
every plane byte, including untouched bytes and OR-preserved destination bits.
Core and actual near-RET boundaries also compare all canonical RAM, returned
registers, defined flags, ordered bus/ports and final VGA state/latches.

Additional finite providers shorten the actual saved initial39/52 counts to2,
leaving subsequent1 saves intact. They exercise changed DS/SI/DI/DX saves, live
page reads, a later plane's source, changed outer RET, stack/data20-bit wrapping,
near-stack offset wrapping, coordinate/stack and mirror/stack aliases, and the
missing-output stop. These are constructed contract cases, not game discovery.

Two preliminary fixtures failed and earn no native or mutation credit. SSFFFF,
SP0011 put a saved inner count across the VGA mirror atSS0008; its repeated
overwrite exhausted the original access budget. The accepted physical-wrap
witness uses SSFFFE,SP0021 to isolate the same high-byte wrap from that alias.
A VGA-backed stack produced saved output ports outside the finite fixture's
declared device domain. That device/stack domain remains unverified; game C was
not changed to normalize its saves, suppress outputs or conceal the failure.

Native work uses the shared bounded launcher with600 seconds per worker,
384MiB process-tree commit,1,000,000 original instructions and250,000 events per
comparison. Callback failures terminate the worker; exhaustion never counts as
a mutant mismatch. The owning build context reaps its temporary DLL directory
after success or failure. The suite is registered with tools/difftest.py and
aggregate coverage, without renewing unrelated historical evidence.

The ASM body now resides in src/level_preview.asm, with physical boundary
assertions at7EB2/80FD. The preceding and following bytes remain in their own
maintained modules in unchanged order. Names and exact offsets remain ledger
owned; classifications, UNKNOWN bytes and relocation order are unchanged.

Broader4566/454C composition, arbitrary nonterminating save aliases, VGA-backed
stack provider domains, hardware/IRQ timing, native services and SDL3 remain
open. The next connection is the briefing path through its preserved preview,
partial clear4C17, palette wrapper5447 and text-field wrapper4B5C. The197D
resource selector retains its RAM-only service contract until its shared bus
capability is deliberately extended.

## Accepted evidence

The selected suite passes25 fixtures /50 original-native core/actualRET
comparisons, all278 instruction sites /six direct outcomes and nine completed
mutants. It executes8,616,454 original instructions and compares2,500,888 ordered
events. Peak invocation is477,039 instructions /138,400 events. All18 consumed
input hashes match. The suite completes in81.42 seconds; owned temporary DLL
directories are reaped. All83 unit tests and the exact ASM/relocation gate pass.
The587 new unique bytes take the main C instruction-byte union to30,782.

Mutation witnesses cover wrong sampled bits, omitted destination latch read,
replace instead of OR, wrong plane mask, wrong source/destination row pitch,
missing STI, restoring entry DS instead of its actual saved word, and discarding
the saved inner count. An initial mutation-only expression was rejected by
-Werror; it earned no detection credit. All nine numeric builds and witnesses
then passed a bounded preflight, followed by a fresh complete selected campaign
on the final source. Reports were not rehashed from an earlier run. Full-game,
original-contract and aggregate acceptance remain separate.
