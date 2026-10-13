# DAT filename and cache selection cores

Three original closed intervals are now translated in c/dat_cache.c. The symbol
ledger owns names, offsets and maintained ASM references, including the cache base
segment field used by selection. No stored bytes or classification are changed.

| Entry | Inclusive CS range | Bytes | Native core |
|---|---|---:|---|
| PrepareDatCacheName | 1E1C..1E63 | 72 | lmn_dat_prepare_name_core |
| SelectCachedDatFile | 1E64..1ED0 | 109 | lmn_dat_select_cache_core |
| DisableDatCache | 1ED1..1ED6 | 6 | lmn_dat_disable_cache_core |

The cores use explicit transient call contracts and live canonical memory. Saved
register values and stack coordinates are necessary inputs because output writes
can overwrite the saved words. Their register adapters exist only at the original
instruction testing boundary; normal C callers can call these cores directly.
No persistent game-state copy, instruction dispatcher or host filesystem policy
is introduced.

## Filename preparation

The filename is read from incoming DS:DX, with ES set to DS. The first eight name
characters are copied to the FCB name at offset 1F96, unless a dot is encountered
earlier. After eight characters it keeps scanning for a dot without a length or
NUL check. The three extension characters begin at FCB offset 1F9E. LODSB, STOSB
and REP STOSB obey incoming DF; the routine never clears it. Source and output
cursor arithmetic wraps at sixteen bits and operates on live bytes.

The early-dot padding count is (7-CX) modulo 65536, with CX still holding the
unconsumed name count. A first-character dot therefore writes 65,535 spaces; an
`A.` prefix writes none. This is the original subtraction, not conventional 8.3
padding. Extension NUL handling similarly uses (2-CX) modulo 65536: an immediate
extension NUL writes 65,535 spaces, and a NUL after one extension character writes
none. Padding can overwrite the filename and other fields before later reads.
No uppercase conversion, trimming or validation is added.

The routine restores CX, AX, ES and DX from live saved stack words; SI and DI expose
their final cursors. A tested ordinary three-character extension overwrites saved
CX and part of AX when the FCB overlaps their save slots. The original final flags
come from AND AL,AL or the extension-padding SUB AX,CX. AF is excluded only for
the logical operation; the SUB flags are fully compared.

## Cache selection and disabling

Selection loads the live byte record count into CL. With no records, CH and other
scratch values remain as specified by the original partial-register write. With
records, ES becomes caller DS, DS becomes DatCacheBaseSegment, and scanning starts
at offset zero. Each descriptor has eleven name bytes and a length word at +11.
REPE CMPSB obeys DF, but the decision afterward is AND CX,CX rather than the last
comparison's ZF. Consequently a mismatch on the eleventh comparison still counts
as a hit. This behavior is verified and retained.

On a miss, the descriptor offset receives the length and thirteen-byte header in
two separate sixteen-bit additions. Overflow is discarded before the low nibble
and segment adjustment are calculated. The record count loops with its original
save frames. A successful record publishes the restored record offset/segment,
read cursor at offset+13, and selected byte FF in the original relocated main data
frame. It returns that data segment in CX and the cache segment in AX. The caller
DS is popped from live stack memory after publishing fields: a tested alias makes
that pop observe the newly stored read segment. ES remains caller DS.

A miss clears the caller-frame selected byte and sets carry. A hit clears carry
after preserving flags from ADD SI,13. No empty-cache or miss path is relabeled as
dead. DisableDatCache, called by startup, clears only AL and the live enabled byte,
preserving AH and exposing XOR AL,AL flags.

## Bounded verification

tests/dat_cache.py compares native C with only these original intervals in 305
constructed cases, at three loads. All 96 instruction sites and eighteen branch
edges execute. Full 1 MiB memory, every register and defined flags are compared,
including stack residue, both DF values, cursor/stack wrap, all eleven mismatch
positions, first/later hits, exhausted searches, length and segment wrap, aliases
of saved registers/DS, and all 256 incoming AL values on startup disabling.

Three compiled mutations are detected: changing early-dot padding, requiring the
last name byte to match, and restoring the discarded pointer carry. The original
instruction budget is 600,000 per case; the standard differential runner caps the
suite process at 120 seconds, including native calls. Fixtures keep executing code
and active return words intact, use quiescent interrupts and clear TF. Name scans
reach a dot; a missing dot can loop indefinitely in the original and native code.

File opening at 1CB9, attribute/retry handling at 1CD9, resource ownership/callers,
and the UNKNOWN allocation code starting 1ED7 remain untranslated or unresolved.
The 04D0 fatal cleanup also remains open. Cache selection and decoding being native
does not establish a complete loader or game.
