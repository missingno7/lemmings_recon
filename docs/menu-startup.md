# Menu entry, palette publication and resource availability

The maintained startup cluster connects EnterMainMenu43F2, the53F6/53FC/53FE/
5401 palette selectors, CheckMenuResourceAvailability4AC5 and the accepted
4401 menu controller. It reuses c/main_menu.c, c/palette_ports.c and the existing
typed display, timer, renderer, palette and interrupt services. No additional
CPU, bus or state-comparison engine is introduced.
The146 newly accepted code bytes take the main-image C ledger union to29,001.

## Two distinct adjacent bytes

Startup0095 pushes DS, invokes INT21/AH1B, reads AL from the returned DS:BX,
pops the actual saved DS, then writes AL to1FDE at009D. The Microsoft DOS
reference identifies that returned pointer as the default-drive FAT ID byte.
The ledger therefore names this sampled byte StartupFatIdByte1FDE. It is not
the neighboring DatCriticalErrorFlag1FDF, set by the installed INT24 handler.
See [Microsoft's MS-DOS Encyclopedia, system calls](https://www.pcjs.org/documents/books/mspl13/msdos/encyclopedia/section5/),
Function1BH. The producer's failure path does not validate that returned pointer
before reading it; no new validation is invented here.

4AC5 compares the startup sample against exactlyFD. Other values return
immediately without reading input, opening a file or clearing the critical flag.
FD selects a palette/prompt/input/resource check. After both file requests
succeed, the routine clears live DS:1FDF. These distinct ownership contracts
correct the earlier plan's conflation of the media sample and critical flag.
The existing fixed-media comparison at062B also consumes1FDE; its surrounding
startup/protection body remains separate work.

## Palette selectors and shared tails

53F6 sets CX8 and jumps to5401, keeping incoming AL.53FC forces AL2, then
falls through53FE, which sets CX16. The5401 entry preserves incoming CX.
All entries clear AH, double AX, compare the complete mode word1F7C with4,
and fetch a fresh source word through CS. Mode4 uses RgbPalettePointerTable
52E4 and tail-JMPs to the mapped DAC writer54C4. Every other mode uses
PackedPalettePointerTable52D4 and tail-JMPs to the attribute writer5425.
No extra original caller frame exists at either handoff.

Indices remain unchecked, so adjacent code/data bytes remain observable for
large AL. The pointer tables and gaps retain their original classifications;
UNKNOWN bytes at53FB,5417 and5424 are not claimed as translated code. The
KEEP_COUNT boundary preserves CH as the writer's starting index and CL as
its count. A zero low count retains the original full65,536-iteration loop.
Returned registers, stack, DF, flags, and missing-port stops come directly
from the existing writer cores. Only a READY adapter consumes the actual
inherited near return word.

## Resource check and DOS transport

The FD path transitions to palette1 once, then repeats clear/background/text/
page copy/display wait/display start/palette2. Its text is live DS4F00. Each
iteration resets the whole keyboard scan byte and polls either low button
bits0..2 or the whole latch in AH. It does not normalize these bytes to host
booleans. The code then requests DOS open with AX3D00 and current DS:2534,
whose pinned filename is vgagr0.dat. CF failure redraws and retries without
attempting close.

On successful open, the actual returned AX becomes BX. MOV AH,3E preserves
AL, and the following INT21 requests close with that actual handle. Close CF
failure also redraws and retries. There is no synthetic rollback or recovery
of an earlier handle if close fails. Both successful requests are followed by
palette1 and full clear, then a byte write0 to the returned live DS:1FDF.

The shared interrupt_service.c implementation and tests/verification.py own
actual FLAGS/CS/IP pushes, live IVT21 reads, bound pre-IRET callbacks and actual
returned SS:SP frame reads/normalization. Provider stops, unbound services and
changed IRET continuations remain distinct menu statuses. The finite DOS
fixture models open/close errors and handles, records every register packet,
and verifies the canonical filename bytes. Returned DS and moved IRET/caller
frames are consumed by the following code, rather than restored from entry.
This is declared external-service evidence, not execution of DOS internals.

The probe core stops before its4B1B RET. Its adapter consumes that live caller
word only on READY. The startup caller supplies the actual4401 return word;
the following menu entry is original fallthrough, without another CALL/RET.

## Complete startup composition

43F2 calls display setup4BE7, clear4DEF, menu-vector installer5028, palette
publication53FC and resource check4AC5, then falls into4401. Display setup
retains its previously tested logical INT10 service ABI; no new BIOS frame
model replaces that contract. Timer installation uses the existing native
core, including actual saved DS and IVT08 stores. The distinction between
this logical BIOS seam and explicit DOS INT/IRET transport remains visible.

Each child call uses the original near return word and returned fields.
The normal menu still reports actual JMP continuations04D0,4967,4A01 or454C.
Acceptance of this startup/menu domain does not implement the destination
code-entry or level/game bodies, native IRQ scheduling or opaque service
implementations. Inherited RETF selector-EA wrap and artificial VGA-stack
reference limitations remain open.

## Verification and bounded storage

The existing main_menu campaign now includes the selectors, resource retries,
external-service failures, moved stack/DS, actual INT/IRET frames and three-load
startup into the same native menu. Both full zero-count palette loops are
bounded witnesses. The previously accepted controller/input handoff remains
in the same campaign. An early disk-prompt fixture exhausted its event limit
because it supplied a press but no later release; the following original menu
release-wait kept reading the held button. That failed run earned no native
comparison or mutation credit. The corrected finite input schedule releases
the button after the probe and leaves game C's original wait unchanged.

VGA observation lists now reuse verification.py's lossless packed sequence
through a four-field fixture adapter. Every kind/address/value/raw-flags field
is retained, with a hard per-call budget, deep-copy and clear behavior checked
against the unchanged VGA fixture. Complete stage comparisons precede history
consumption; no device latches/registers/planes/counters or game RAM are reset.
The canonical bus, CPU executor and state comparator remain unchanged.

The native worker retains384MiB process-tree commit,900 seconds and a960-second
outer envelope. Main invocations retain4,000,000 instructions/2,000,000 events.
Owned compile/DLL directories stay under build and are reaped on failure too.
Only completed mismatches earn mutation credit. The main compiler/source
resolver now exposes the actual ordered, deduplicated source closure, including
aliases previously selected alongside mutation definitions. All320 unaffected
source/define plans match their earlier values; this is planning evidence, not
compile evidence. Native campaigns still compile their actual numeric variants.
The report hashes the complete resolved source/header set used by this build.

The accepted expanded campaign passes123 fixtures/125 comparisons,all169 own
sites/66 direct outcomes and21 completed mutation witnesses in7,069 known
controller/child bytes. It executes25,415,697 original instructions and compares
18,636,499 ordered events. Supplemental observations count3,940 far-return
accesses and436 declared interrupt-transport accesses;32 BIOS/DOS service
callbacks are recorded separately. The integrated executed union is2,093 sites/
338 outcomes. Peak invocation sizes are2,349,919 instructions/1,664,700 events,
within the unchanged per-call limits. The expanded run finishes in539.55 seconds.

The existing nine controller witnesses are retained. Twelve new witnesses
distinguish exactFD versus nonzero,confusing the adjacent state bytes,ignoring
open/close CF failures,clearing entry rather than returned DS,testing the wrong
keyboard half,losing close AL,uncleared selector AH,wrong table segment,byte
instead of word mode comparison,an omitted forced slot and wrong color count.
All native calls complete before their mismatches are accepted.

Affected native regressions pass independently: menu_timer54 fixtures/108
comparisons/eight mutants and palette_timer67 fixtures/132 comparisons/five
mutants. All81 unit tests and the exact ASM/relocation gate pass. These results
remain scoped evidence for their consumed hashes; full aggregate acceptance
requires its separate original-contract and complete native campaigns.
