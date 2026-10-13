# Completeness at the first verified milestone

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py, tools/difftest.py, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | 82,906 |
| Classified image bytes | 43,777 |
| Decoded instruction bytes | 35,546 |
| Reconstructed ASM bytes | 82,906 |
| Byte-exact ASM bytes | 82,906 |
| Identified routine entry candidates | 266 |
| Translated C routines | 2 |
| Translated C code bytes | 116 |
| Differential cases | 12 |
| Mutation checks detected | 3 |
| Original instruction coverage | 44 / 15,309 decoded (0.287%) |
| Unresolved image bytes / runs | 39,129 / 116 |
| Unresolved runs inside provisional code frame | 113 (4,015 bytes) |
| Resolved static CFG edges, including fallthrough | 16,858 |
| Unresolved direct targets / indirect transfers | 0 / 7 |

The decoded instruction denominator is incomplete: unknown runs and external sound
driver code may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are 1,556 decoded instructions expressed as explicit encoding exceptions.

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

External executable inventory is still open: 17 legacy entry signatures at historical
segment2911 are recorded, but their reconstructed bytes and tested coverage are zero.
No public executable or proprietary asset is tracked. See executable.md for local
provenance, control-frontier.json for addresses, and next-work.md for proof obligations.
