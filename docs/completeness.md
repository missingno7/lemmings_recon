# Reconstruction completeness

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py, tools/difftest.py, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | 82,906 |
| Classified image bytes | 45,694 |
| Decoded instruction bytes | 35,760 |
| Reconstructed ASM bytes | 82,906 |
| Byte-exact ASM bytes | 82,906 |
| Identified routine entry candidates | 273 |
| Translated C routines | 11 |
| Translated C code bytes | 802 |
| Differential cases | 882 |
| Mutation checks detected | 15 |
| Original instruction coverage | 375 / 15,392 decoded (2.436%) |
| Unresolved image bytes / runs | 37,212 / 115 |
| Unresolved runs inside provisional code frame | 112 (2,098 bytes) |
| Resolved static CFG edges, including fallthrough | 16,969 |
| Unresolved direct targets / indirect transfers | 1 / 5 |
| Runtime-modified control-flow frontiers | 2 |
| Additional state-specific main instruction sites | 401 |
| Known conditional indirect edges | 18 |

The decoded instruction denominator is incomplete: unknown runs in the main and
sound-driver images may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are 1,567 main-image decoded instructions expressed as explicit encoding exceptions.

Gate A passes for the main EXE: deterministic static unpack, full byte comparison,
63 independently checked relocations, entry/stack state and input identity. Gate B
has an exact buildable initial ASM image, but remains open for code/data, indirect
transfer, external-driver and semantic closure. Gates C/D have the checksum,
DAT decoder/read/cache/leaf and PC-speaker helper clusters. The two checksum and nine DAT main
routines are TESTED within docs/checksum.md, docs/dat.md, docs/dat-io.md and
docs/dat-section.md and docs/dat-cache.md's domains; remaining
main entry candidates are UNTRANSLATED. CS:8363 reachability remains UNRESOLVED despite
its complete bounded instruction/branch coverage. Gate E is not started.

The checksum tests execute 44/44 cluster instruction addresses and all 10 static
branch edges. They compare registers, defined flags and the entire 1 MiB memory,
including push/pop residue, across poisoned fixtures. AF is excluded only on the
phase-wrap path, where the last XOR makes it architecturally undefined.

The DAT leaf suite covers 33/33 instructions and all six local branch edges in
470 cases. It compares full memory, registers and defined flags, including zero
bit counts (256 iterations), zero incremented match counts (65,536 iterations),
live overlapping copies and overwritten saved registers. Three compiled mutants
are detected. File open/check wrappers and cache allocation remain UNTRANSLATED;
the strict static extractor's validation rules are not substituted for original
runtime behavior. See dat.md.

Loaded sound-component images reconstruct exactly, with separate static accounting:

| Image | Exact ASM bytes | Classified bytes | Decoded instructions | Entry candidates | Unresolved transfers | C routines |
|---|---:|---:|---:|---:|---:|---:|
| adlib | 22,125 | 1,438 | 655 | 17 | 1 | 0 |
| tandysnd | 21,702 | 1,890 | 754 | 40 | 1 | 0 |
| pcspeaker | 758 | 596 | 89 | 4 | 1 | 3 |

Across all four component images, 127,491 ASM bytes are exact and 17,291
instructions have been decoded. C differential coverage is 435 / 17,291
(2.516%) of this still-incomplete decoded inventory. There are
14 tested C routines occupying 967 original code bytes across images,
with 1217 differential cases and 18 compiled mutations detected. Six bounded
DAT extraction checks exercise 145 main-image instructions; these are extractor
verification, not C translation coverage and not driver execution tests.

All 16 legacy AdLib signatures at segment 2911 match the static extraction. The
seventeenth external lead is F000:FF53 firmware/environment code, not a driver entry.
All three sound dispatch tables lack sufficient bounds checks; their out-of-table paths
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

Callback evidence traces all 32 recovered object-record pointer stores to nine
drawing callback slots and identifies four display probes, three input callbacks
and the code-input BP callback. The 18 known indirect edges are present in the CFG,
while all five near-callback target domains remain explicitly incomplete. Thirty-two
bounded caller fixtures cover 214 original caller instruction sites with declared
callee boundaries. They check routing and save/restore behavior, including DF-set
traversal and unlisted live pointers; they are not C coverage or callee tests.
See indirect-callbacks.md for alias and incoming-state obligations.

The PC-speaker image is MAIN.DAT section 5: 758 separately reconstructed payload
bytes loaded over canonical zeros at main 08420..08715. Component byte totals count
both stored main bytes and the payload image; they are not unique runtime-memory
bytes. Original extraction is checked at the actual overlay destination at two loads.
The payload's trailing 161 bytes and single pre-entry byte remain UNKNOWN. Its three
closed helpers (effect selection, tick and stop) now have C11 cores and near-call
adapters. The PC-speaker suite compares full memory/registers, defined flags and
port traces in 335 cases, covers all 60 helper instruction sites and all 17 branches,
and detects three compiled mutations. The IRQ dispatcher remains UNTRANSLATED;
none of its unresolved target paths has been silently replaced. See pcspeaker.md.

Two saved INT08 chains now have explicit external IRET edges and original return
continuations. Nineteen bounded tail cases check complete memory and saved-register/
flag results across loads, stack wrap and external clobbers. Nineteen installed-
handler fixtures check 0F6F/0F70/18F8 and their declared service boundaries. These
are caller/handler checks, not full timer, BIOS, C or game execution coverage.
See interrupts.md for provider contracts and the menu wrapper's unsaved ES effect.

The complete DAT read wrapper at 1D2E..1E1B now has 45
bounded original-code cases, covering all 106 instructions and
12 branch edges under declared DOS fixtures. Full memory/register/flag
checks expose direct-read errors, short reads, cache creation and hits, saved-frame
aliases, ignored cache-fill errors and pointer/count wrap. This is provider-contract
evidence, not C translation or actual DOS execution coverage; see dat-io.md.
The same original wrapper also has a C11 core and near-call adapter, verified in
45 native differential cases covering all 106 sites and 12 branches, with
three compiled mutations detected. Its narrow DOS file-size/read services have
declared register-preservation contracts. The skipped UNKNOWN byte at 1D7C is
excluded from translated-byte accounting. Full DOS/FCB platform behavior and the
other resource-loading routines remain open.

The DAT section decoder and its read-distance/shared-copy entry now call C cores
directly. 48 integrated differential cases execute all 235 decoder,
leaf and read-wrapper sites and all 32 local decoder/leaf branch edges. They
compare full memory, registers, defined flags and service traces, including real
sound sections and malformed constructed headers. Three compiled section mutations
are detected. Only AF after final AND DH,DH is excluded; read-error flags are fully
compared. The fatal jump to 04D0 is an explicit exit with its original saved frame,
not a translated cleanup routine. Four skipped UNKNOWN bytes are excluded from
translated-byte accounting. Direct helper calls retain original return-word residue;
overwriting those active return words is outside the current verification domain.
See dat-section.md for unsigned termination, ignored high size words and aliases.

DAT filename preparation, cache selection and startup cache disabling now have
C11 cores: 305 cases cover all 96 instruction sites and 18 branch edges,
with three compiled mutations detected. Full memory/register/defined-flag checks
preserve wrapped padding counts, DF, the last-byte mismatch hit, record-pointer
wrap and saved-register aliases. No host filename normalization or corrected
string comparison is substituted. File open/attribute wrappers and the UNKNOWN
cache allocation code remain open; see dat-cache.md.
