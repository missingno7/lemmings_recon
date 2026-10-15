# Video mode and page restoration

`RestoreVideoModeAndPage` at0FF8..1006 contains15 bytes and seven straight-line
instruction sites. Four decoded callers enter it at04D9,0EE8,1046 and194F.
The ledger retains the old `sub_0FF8` alias. Startup queries INT10 withAH0F at00A2
and stores returnedAL atDS:1FE1 andBH atDS:1FE2. These bytes are named
`SavedVideoMode` and `SavedVideoPage`; the maintained ASM retains all original
bytes, including the direction-encoding exception forXOR AH,AH at0FFB.

The routine reads the mode byte through incomingDS, clearsAH withXOR and invokes
INT10. It then writesAH05 and reads the page byte through the DS returned by that
first provider before invoking INT10 again. It saves no registers and creates no
internal call frame. Returned general registers, DS/ES/SS/SP and flags remain
live. The final nearRET consumes the actual returnedSS:SP word, low byte then
physical successor with20-bit wrap; SP advances modulo16 bits.

`c/video_restore.c` implements the two calls directly. Its twelve transient
ABI fields describe input/output values at these platform boundaries; they are
not a persistent game-state copy. Providers may change all twelve fields and
canonical memory, return in the sameCS at the next original instruction, and
leaveTF clear with interrupts quiescent. This is an explicit returning-provider
domain, not a BIOS implementation or proof about arbitrary interrupt handlers.
An absent mode provider stops at0FFD after the mode read andXOR. An absent page
provider stops at1004 after the first result and the live page read. Neither stop
consumes the outer return. The core stops beforeRET1006; the adapter consumes it.
Optional bus callbacks own the field and return reads. NULL bus reads canonical
RAM directly, with identical cursor and physical-word conventions.

`tests/video_restore.py --original-only` runs pinned instructions against an
independent two-stage logical model. The native gate first completes this
original-only phase before compilation. Each original invocation has20
instructions; each worker has120 seconds,384 MiB process/640 MiB tree limits;
compiler subprocesses have60 seconds/256 MiB limits. Bus traces cap at32 events,
provider traces at two calls. Callback errors exit87 and budget exhaustion exits86;
neither can count as a mutant mismatch. The parent removes owned temporary DLLs
only after the worker is terminal. Dependency hashes are captured before the gate
and checked afterward. No game boot, runtime dump or asset change is used.

The matrix covers all256 mode and page bytes, three loads, all general register
outputs, live returnedDS and changedSS/SP, provider-written page/return words,
physicalA20 andSP boundaries, VGA-backed fields and return reads, and separate
missing-provider boundaries. UndefinedAF afterXOR AH,AH is excluded only until
the first provider supplies explicit flags. Other modeled flags are checked at
every bus/provider boundary. Four finite mutants target cachedDS, discarded
provider flags, an early cached page byte and a stale entry-time return word.
Acceptance counts and completed mutant evidence belong to the final reports in
`build/video-restore-contract-original.json` and `build/video-restore-differential.json`.
The broader04D0 cleanup still depends on timer/vector restore providers.

The gate passes279 adapter comparisons and279 auxiliary core probes, with276
NULL-bus comparisons at each boundary. All seven original sites execute and
there are no original branch edges. All four mutants complete and disagree.
The matrix includes270 ready cases and nine missing-service boundaries. These
15 native bytes overlap no other translated leaf. Aggregate coverage remains
pending the separate complete terrain-stream and global acceptance campaign.
