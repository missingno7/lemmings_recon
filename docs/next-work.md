# Precise next frontier

1. Complete the protected disk-check contracts after the recovered state-specific
   stream. The 372 stream and 29 INT1 instruction sites have exact maintained views,
   checked against original handlers at all 325 TF-on points. Review incoming state,
   scratch/stack aliases, BIOS/DOS effects and skipped 084D/087E regions; see
   protection.md. Keep canonical 066D bytes in their stored representation.
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
9. Close AdLib 01EA and Tandy 02BB command dispatches. Known visible tables cover
   commands 80..87 and 80..97 respectively, but unchecked higher commands can read
   code/state as pointers. Recover producer domains and classify music/effect data.
   Both driver images already assemble exactly; see sound-drivers.md. Their C
   implementation and behavioral coverage are still zero.
10. Refine ownership modules after dependencies are understood. Replace explicit
   encoding exceptions with reliable NASM encoding syntax where available.
11. Only then assign additional bounded C clusters. Resource decoding/loading is a
    candidate after its original entry and memory contracts are recovered. No SDL3
    integration or gameplay milestone is needed to progress these investigations.
