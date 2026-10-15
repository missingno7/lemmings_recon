# Entity stroke and native pixel-address child

`DrawEntityStroke` at 5F0F..5FAB is a 157-byte, 67-site drawing caller reached
from 26DE. Its only direct child is `PrepareEntityPixelSample` at 5DC6, now
available through a bus-aware logical core. The connected instruction union
has 89 sites/207 bytes; the child's 50 bytes overlap its existing translation
and must not be counted again. Full simulation and device initialization remain
separate contracts. This routine does not call the 5EBA exchange writer.

The routine clears IF, writes Sequencer 2=08h, Graphics Controller 0=08h,
GC1=08h and GC3=00h through their actual SS mirrors and ports, and selects
ES=A000h. Thus its writes select plane 3 with plane-3 set/reset; incoming
VGA mode, read map/compare/care and aperture addressing remain live. It leaves
the final GC settings in place, then restores Sequencer 2 to 0Fh at the tail.
Every mirror write precedes its OUT and may itself hit VGA through SS aliases.

It pushes the live record Y and X words, then rereads X and adds the live
word at record+4. A negative byte at record+27h subtracts another four from
that wrapped result. It stores the temporary X, pushes that word, decrements
live Y, and calls 5DC6 through a real SS return frame containing 5F57h.
The child reads live DS/SS memory and the mask table through the same bus.
The caller consumes the child's actual RET word. A changed target is returned
as an explicit continuation boundary before executing that target; it is never
silently treated as a normal child return.

On normal return it pops CX, pops a live word into record X, then another
into record Y. These stores do not restore cached coordinate copies. The save
frame, record fields, table and outer return word can alias, and callbacks may
change later reads. The restored SI/DS/SS registers themselves remain unchanged.

BX starts at 00FCh and DL at zero. The popped temporary X word, masked with
seven, controls up to seven SHR BX/RCR DL iterations. LOOP decrements CX
without changing flags. CL then receives the shifted spill byte from DL.
Those BX/CX bytes supply three bit masks. For each, a read of ES:DI loads VGA
latches before the SS:000E mask word, GC8 output and STOSB. DF controls DI;
the reads are not redundant merely because their CPU byte is overwritten.
The flags from the final shift/rotate pair, or the zero-count AND, survive
until the unconditional trailing STI sets IF. Final AX=0F02h, DX=03C4h and
ES=A000h; BX/CX retain their mask/spill values and DI moves by three bytes.

The logical core ends before the outer RET at 5FAB, unless the child returns
elsewhere first. Its result carries the live modified values and continuation;
the register adapter consumes the outer RET only for the normal core boundary.
Physical memory addresses wrap at 20 bits, offsets/SP at 16 bits, and word
high bytes use physical+1. The same optional raster bus owns all record, stack,
mirror, table and VGA accesses. A null bus provides only constructed RAM with
no-op ports. The supported device fixture is the documented unchained A000
aperture with read/write modes 0/1; physical timing, active IRQ scheduling and
executing-code aliases remain outside this intact-code/TF-clear contract.

`tools/difftest.py entity_stroke` passes 40 fixtures at both core/adapter
boundaries, all 89 integrated sites and eight branch edges, with 5,884 ordered
bus events. It compares every register, complete 1 MiB RAM, device planes,
latches/registers and each instruction's defined callback flags. The memory
decrement observes entry flags at both bus accesses, then publishes its result
before CALL; these defined arithmetic bits are checked. Only architecturally
undefined bits, such as MUL's PF/AF/ZF/SF, are omitted at their actual phases.

Eight disjoint cases independently derive the masks from `0FC00h >> (X&7)`
and check plane-3 placement. Other fixtures cover signed adjustment, wrap,
DF, DS/SS/VGA save and table aliases, changed saved coordinates, changed child
returns and the overwritten outer return word. Five completed mutants exercise
the negative adjustment, cached coordinate restores, DF, continuation after a
changed child target and the Sequencer restore. Their witnesses complete;
timeout, access exhaustion and callback errors cannot count as detection.

The worker runs under 180 seconds/384 MiB process/640 MiB tree limits. Original
execution is capped at 300 instructions per call, and callback/device traces at
256 events with hard exits 86/87 for exhaustion/error. All temporary DLLs are
removed after worker exit. The exact retained scope and input hashes are in
build/entity-stroke-differential.json. This is a connected drawing contract,
not full simulation or aggregate game acceptance.
