# Level header prefix

The native `ApplyLevelHeader` core covers the original straight-line prefix at
CS:`36B9..3741`: 137 bytes and 47 instruction sites. It stops at `3742`, before
the caller reads the special-graphics selector. The static ownership evidence
and original-only contract are in [level-header-ownership.md](level-header-ownership.md)
and [level-header-contract.md](level-header-contract.md).

`lmn_apply_level_header_core` accepts the one live 1 MiB memory image, DS,
incoming flags, and an optional `LmnRasterBus`. It returns `value` (AX),
`header_cursor` (DI), and flags. The register adapter writes those fields and
sets IP to `CS_LevelAfterHeader`; all other registers remain unchanged. The
prefix has no stack access, call, return, or control-flow branch.

The source header stays in the same memory image as the destinations. Each
big-endian field is fetched by two separate bus reads, high byte first and low
byte second. The first low byte is stored to both release-setting fields. The
creation limit, unresolved word `+04`, adjusted countdown byte, and eight
action counts are byte stores. The view-origin path adds `0010` with 16-bit
arithmetic, stores the full word, performs three individual logical right
shifts, then stores the full shifted word. Word stores are two ordered byte
writes at consecutive physical addresses.

The ADD updates CF/PF/AF/ZF/SF/OF while preserving DF, IF, and other flags.
Each SHR updates CF/PF/ZF/SF/OF individually and preserves AF's representative
value because AF is undefined for SHR. The final result exposes the flags after
the third shift. Bus callbacks receive the flags in force at each read or
write; a null bus uses ordinary RAM at the same wrapped 20-bit physical
addresses.

The implementation does not construct a host header object or separate level
records. This preserves source/destination aliases in the canonical RAM image,
including the documented record-index-86 overlap. `LevelHeaderWord04` remains
an observed storage role; its downstream meaning is unresolved. This prefix
does not establish readiness of all of `36B6..3789` or translate later level
setup and minimap calls.

`tests/level_header.py` passes92 adapter cases and92 auxiliary logical-core
checks, covering all80 pinned headers and12 constructed inputs. Ninety cases
also compare the null-bus RAM path; two cases use VGA-backed header and output
accesses. All47 original sites, whole RAM, defined flags, registers, ordered
memory events and plane/latch state agree. The separate original-only suite
also checks each individual SHR phase. Four compiled mutants detect reversed
source-read order, an incorrect word store at the byte-only+04 destination,
an incorrect view bias and incorrect final carry. Resource or oracle failures
cannot count as mutant detections. Workers have a120-second timeout and512MiB
process/768MiB tree ceiling; the outer parent owns disposable DLLs.
