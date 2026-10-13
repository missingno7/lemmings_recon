# Reconstruction completeness

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py, tools/difftest.py, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | 82,906 |
| Classified image bytes | 44,757 |
| Decoded instruction bytes | 35,613 |
| Reconstructed ASM bytes | 82,906 |
| Byte-exact ASM bytes | 82,906 |
| Identified routine entry candidates | 268 |
| Translated C routines | 2 |
| Translated C code bytes | 116 |
| Differential cases | 12 |
| Mutation checks detected | 3 |
| Original instruction coverage | 44 / 15,335 decoded (0.287%) |
| Unresolved image bytes / runs | 38,149 / 118 |
| Unresolved runs inside provisional code frame | 115 (3,035 bytes) |
| Resolved static CFG edges, including fallthrough | 16,886 |
| Unresolved direct targets / indirect transfers | 1 / 7 |
| Runtime-modified control-flow frontiers | 2 |
| Additional state-specific main instruction sites | 401 |

The decoded instruction denominator is incomplete: unknown runs in the main and
sound-driver images may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are 1,558 main-image decoded instructions expressed as explicit encoding exceptions.

Gate A passes for the main EXE: deterministic static unpack, full byte comparison,
63 independently checked relocations, entry/stack state and input identity. Gate B
has an exact buildable initial ASM image, but remains open for code/data, indirect
transfer, external-driver and semantic closure. Gates C/D have only the checksum
cluster: both routines are TESTED within docs/checksum.md's domain; all other main
entry candidates are UNTRANSLATED. CS:8363 reachability remains UNRESOLVED despite
its complete bounded instruction/branch coverage. Gate E is not started.

The checksum tests execute 44/44 cluster instruction addresses and all 10 static
branch edges. They compare registers, defined flags and the entire 1 MiB memory,
including push/pop residue, across poisoned fixtures. AF is excluded only on the
phase-wrap path, where the last XOR makes it architecturally undefined.

External driver images now reconstruct exactly, with separate static accounting:

| Image | Exact ASM bytes | Classified bytes | Decoded instructions | Entry candidates | Unresolved transfers | C routines |
|---|---:|---:|---:|---:|---:|---:|
| adlib | 22,125 | 1,438 | 655 | 17 | 1 | 0 |
| tandysnd | 21,702 | 1,890 | 754 | 40 | 1 | 0 |

Across all three images, 126,733 ASM bytes are exact and 17,145
instructions have been decoded. C differential coverage remains 44 / 17,145
(0.257%) of this still-incomplete decoded inventory. Four bounded
DAT extraction checks exercise 145 main-image instructions; these are extractor
verification, not C translation coverage and not driver execution tests.

All 16 legacy AdLib signatures at segment 2911 match the static extraction. The
seventeenth external lead is F000:FF53 firmware/environment code, not a driver entry.
Both sound dispatch tables lack sufficient bounds checks; their out-of-table paths
remain unresolved. Driver code/data closure and behavioral translation are open.
Main INT3 protection has independently checked state-specific views: 372 stream
instructions (325 TF-on, 47 TF-off) and 29 transformed INT1 instructions. The
original handlers pass 19 constructed-frame cases and checks at every one of the
325 derived TF-on instruction points, comparing full memory, registers and defined
flags. These checks execute only 61 handler instruction sites; the disk-check body
has not been executed. The two raw-image control frontiers remain represented in
the separate protection CFG. Platform contracts, memory aliases and skipped code
still need review; see protection.md. No protected routine has been translated to C.
No public executable or proprietary asset is tracked. See executable.md for local
provenance, control-frontier.json for addresses, and next-work.md for proof obligations.
