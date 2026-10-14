# Planar drawing dispatch

The lmn_prepare_planar_drawing_dispatch_core translates the logical prefix at
CS:885E through the dispatches ending at 88BF, 9140, 93A7 or 9810. It also
returns 88AB when entered directly at the incoming-ZF gate 88A6. The shared
selector at 939E is a separate typed core and is called directly by the 885E
core. The renderer bodies and the outer far return remain outside this scope.

The call fields represent AX=left, BX=top, CX=packed height, DX=width, SI and
DI source/destination cursors, BP control, DS, SS:SP and incoming flags. The
result fields map back to AX, BX, CX, DX, SI, DI, BP, SP and flags. The adapter
alone uses LmnRegs; the cores use the typed parameters and the same canonical
1 MiB memory.

At 885E, the routine exchanges AX/BX, stores left & 7 at DS:A948 through the
16-bit AND BX,7, and then restores BX with a live POP from SS. It shifts that
restored BX right three bits. It next pushes DX, reads the current word at
DS:66F4 for MUL, and restores DX from the live stack. A stack alias can change
the pitch read; a store to DS:A948 can also change the saved BX before POP.
These accesses retain their original order.

Destination offset is the wrapped sum of (top * pitch), left >> 3, the
live DS:1F76 origin and the live DS:1F7A page offset. The routine stores
pitch - (width >> 3) at DS:6700 and DS:6704. It then packs the original
CH into DH, original CL into CH, and shifted DL into CL, before loading the
live DS:66F8 source extent into AX. The two stride stores are observed in order
even though this scope has not established a consumer for DS:6700; DS:6704 is
the active destination stride used by the later drawing bodies.

Control bit 0 clear jumps to the 939E selector. When bit 0 is set, the normal
885E path reaches 88A6 with ZF clear, continues through the live compare at
DS:A948, and either selects the aligned path or exits to the shifted opaque or
masked preparation boundary according to control bit 1. A direct 88A6 entry
preserves its incoming ZF, including the branch to 88AB. A direct 939E entry
tests control bit 1 and stops at 9810 or 93A7. No target instruction at any
continuation is run.

Every word bus access transfers the low physical byte before the high byte.
Physical addresses wrap at 20 bits, stack offsets wrap at 16 bits, and each
word's high byte is the next physical byte. DS, SS and all non-output
registers retain their original effects. The cores preserve arithmetic flags
at each instruction boundary, including MUL's defined CF/OF result; undefined
bits after logical operations and shifts remain representative.

tests/drawing_dispatch.py compares the original instruction paths and native
adapter across 77 cases. It checks the whole 1 MiB RAM image, all registers,
defined flags, and ordered byte accesses through the RAM callback and null-bus
paths. Coverage includes all 38 primary caller sites and all 3 shared-selector
sites, 29 entry-tagged branch observations and 15 unique static branch edges,
all eight left residues, control-bit
routes, high-bit coordinates and widths, stack/data aliases at A948 and 66F4,
physical wrap, stack-offset wrap, and arithmetic wrap. Three compiled
mutations for the shift mask, page addition, and DX restore are detected. The
machine-readable report is build/drawing-dispatch-differential.json.

The report records the raw Unicorn 2.1.4 memory-hook flags during the MUL
operand read alongside its instruction-boundary flags. Differential flag
checks use the original instruction boundary. The separate transient
CF/OF discrepancy observed inside the post-MUL memory-write hook is documented
in drawing-inputs.md; no defined instruction-boundary difference is masked.
This dispatch test executes no VGA body and establishes only ordinary RAM
callback behavior, not asynchronous device or IRQ ownership.
