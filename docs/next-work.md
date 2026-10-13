# Precise next frontier

1. Decode and bind external ADLIB.DAT executable content; independently match the 17
   legacy 2911 entry signatures. Inspect TANDYSND.DAT and other sound variants rather
   than excluding alternative hardware code. Their code is outside current EXE metrics.
2. Resolve indirect transfer 1407: four 3-byte records at DS:2013 (enable byte,
   near function pointer). Verify initial table and all writes before closing it.
3. Resolve 42A5: AX comes from DS:25A0. Recover every assignment and valid target.
4. Resolve 4CC9/4D18: BP callback into the password input loop and tail continuation.
   Trace callers and stack saves; do not guess a single target from one fixture.
5. Resolve 715B: saved AX callback. Establish its incoming call contract.
6. Explain 1899/4C6C far chaining through DS:1FBE (saved INT08 vector); represent an
   external interrupt edge once register/stack contracts are independently reviewed.
7. Review every unknown run in build/analysis.json, especially pre-09A90 gaps and
   post-09A90 area. Locate all handler installs, dispatch tables, read/write crossrefs,
   data initialization, self modification and loaded overlays. Unknown is not padding.
8. Investigate reachability of 8363 (incremental checksum); preserve its tested behavior
   without calling it reachable or dead. Preserve 188F..1898 code/data overlap.
9. Refine ownership modules after dependencies are understood. Replace explicit
   encoding exceptions with reliable NASM encoding syntax where available.
10. Only then assign additional bounded C clusters. Resource decoding/loading is a
    candidate after its original entry and memory contracts are recovered. No SDL3
    integration or gameplay milestone is needed to progress these investigations.
