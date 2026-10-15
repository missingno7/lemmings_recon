# Drawing page copy and full clear

CopyDrawingPageToAlternate (4DC2..4DEE) occupies 45 bytes/18 sites. It writes
0F02 to SS:8 before OUT 3C4, then 0105 to SS:0 before OUT 3CE. It pushes DS
before reading the live source and alternate origin words at DS:1F76/1F78.
AX, DS and ES become A000; CX becomes 6D60. REP MOVSB reads each source byte
before writing its destination and advances both cursors with incoming DF,
wrapping them at 16 bits. Overlap is sequential, including propagation when
the chosen direction overwrites later source bytes. No bulk snapshot is used.

The programmed VGA write mode 1 transfers the four read latches to enabled
destination planes. CPU data, mode-0 rotate/logical/set-reset controls and Bit
Mask do not alter the latch bytes. Reads refresh every plane latch. The device
model follows IBM's VGA/XGA Technical Reference, Figure 2-76, §2-85, Map Mask
§2-51 and latch-save §2-98
([IBM reference](https://bitsavers.trailing-edge.com/pdf/ibm/pc/cards/IBM_VGA_XGA_Technical_Reference_Manual_May92.pdf#page=103)).
Its independent fixture vectors are in tests/test_vga_write_mode1.py.

POP DS reads the actual saved word after copying. Device-backed stacks or
aliases can replace it and the following near-return word. The core leaves
RET at 4DEE for the adapter. All copy flags and BX/BP remain unchanged; AX/ES
are A000, DX is 3CE, CX is zero. Each required OUT is checked at its original
site, after its SS mirror store. Missing providers stop before 4DCC or 4DD7.
Optional copy read/write callbacks fall back to canonical RAM; those repeats
have an explicit RAM provider domain rather than asserting VGA plane behavior.
Their event traces contain only the installed callbacks; full RAM and final
CPU state remain compared. Normal bus cases retain every CPU byte-access event.

ClearFullDrawingPage (4DEF..4DF6) contributes eight caller bytes/three sites.
It loads DI=0 and CX=6D60, then tails into the existing 63-byte ClearVgaBytes
core. No child CALL frame is invented. The unresolved NOP byte at 4DF7 is
skipped and remains UNKNOWN. The child requires read/write/OUT callbacks;
an incomplete bus stops at its 4DF8 entry after the wrapper's two loads.
READY leaves the shared RET at 4E36 for the adapter. The existing clear core
owns its flag, SS-mirror, VGA and DF semantics.

tests/display_pages.py compares an independent instruction/plane model with
the pinned original and native cores/adapters on full-length copies and clears.
It checks all CPU fields, full memory, ordered bus events, phase-defined flags,
VGA state and independent four-plane results. Fixtures include both directions,
overlap, cursor wrap, stack/DS aliases, provider effects and missing providers.
Workers are serial and bounded to 120 seconds, 384 MiB process commit/640 MiB
tree commit, with hard callback budgets. Failures cannot count as mutants;
parent-owned temporary DLLs are removed after termination. Timing, IRQs and
hardware stack-limit behavior remain outside this bounded domain. TF is clear
and IRQ delivery is quiescent during these constructed executions.

The original-only and native gates pass 45 fixtures at both logical-core and
register-adapter boundaries. All 21 caller sites and 25 existing clear-tail
sites execute, with the one wrapper tail edge observed. The new caller union
is 53 bytes; the existing 63-byte clear body is not counted again. Six compiled
mutants test cached origins, ignored DF, a stationary source cursor, cached DS
restoration, an inherited clear cursor and a shortened clear count. Independent
source review found no blocking issue. Aggregate coverage remains unpromoted
until complete terrain acceptance and affected reports are refreshed.
