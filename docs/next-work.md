# Precise next frontier

1. Complete the protected disk-check contracts after the recovered state-specific
   stream. The 372 stream and 29 INT1 instruction sites have exact maintained views,
   checked against original handlers at all 325 TF-on points. Review incoming state,
   scratch/stack aliases, BIOS/DOS effects and skipped 084D/087E regions; see
   protection.md. Keep canonical 066D bytes in their stored representation.
2. Close write/alias and incoming-state obligations for the 18 known callback edges.
   All five near sites have conditional target lists, and bounded caller tests cover
   original pointer routing/save frames. See indirect-callbacks.md and
   metadata/indirect-evidence.json. 1407 depends on incoming DF and live enable bytes;
   42A5 uses an unchecked live DS:25A0 word; 4CC9/4D18 depend on the input-loop stack;
   715B depends on active object ownership, clones and nine mutable drawing slots.
3. Resolve record initialization/copy/activation and DS/ES/SS aliases. All 32
   recovered object callback stores trace locally to DS:002E..003E, but this is
   not a proof that all possible writes have been identified.
4. Explain 1899/4C6C far chaining through DS:1FBE (saved INT08 vector); represent an
   external interrupt edge once register/stack contracts are independently reviewed.
5. Review every unknown run in build/analysis.json, especially pre-09A90 gaps and
   post-09A90 area. Locate all handler installs, dispatch tables, read/write crossrefs,
   data initialization, self modification and loaded overlays. Unknown is not padding.
6. Investigate reachability of 8363 (incremental checksum); preserve its tested behavior
   without calling it reachable or dead. Preserve 188F..1898 code/data overlap.
7. Close AdLib 01EA and Tandy 02BB command dispatches. Known visible tables cover
   commands 80..87 and 80..97 respectively, but unchecked higher commands can read
   code/state as pointers. Recover producer domains and classify music/effect data.
   Both driver images already assemble exactly; see sound-drivers.md. Their C
   implementation and behavioral coverage are still zero.
8. Refine ownership modules after dependencies are understood. Replace explicit
   encoding exceptions with reliable NASM encoding syntax where available.
9. Only then assign additional bounded C clusters. Resource decoding/loading is a
    candidate after its original entry and memory contracts are recovered. No SDL3
    integration or gameplay milestone is needed to progress these investigations.
