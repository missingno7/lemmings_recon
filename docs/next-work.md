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
4. Complete provider, timing and alias contracts for installed handlers and the
   explicit external IRET chains at 1899/4C6C. Bounded tails expose the menu's unsaved
   ES and returned-DS dependencies; keep those original effects. See interrupts.md.
5. Review every unknown run in build/analysis.json, especially pre-09A90 gaps and
   post-09A90 area. Locate all handler installs, dispatch tables, read/write crossrefs,
   data initialization, self modification and loaded overlays. Unknown is not padding.
6. Investigate reachability of 8363 (incremental checksum); preserve its tested behavior
   without calling it reachable or dead. Preserve 188F..1898 code/data overlap.
7. Close AdLib 01EA, Tandy 02BB and PC-speaker 0196 command dispatches. The latter
   is MAIN.DAT section 5, loaded into main frame 0842; it has mutable table words,
   unchecked command/record indexes and 162 unresolved payload bytes.
   AdLib/Tandy visible tables cover
   commands 80..87 and 80..97 respectively, but unchecked higher commands can read
   code/state as pointers. Recover producer domains and classify music/effect data.
   All three component images already assemble exactly; see sound-drivers.md and
   interrupts.md. Three closed PC-speaker helpers now have tested C11 cores, while
   its dispatcher and the AdLib/Tandy code remain untranslated. Verify producers,
   writes and aliases before replacing any live indirect target with a native call.
8. Refine ownership modules after dependencies are understood. Replace explicit
   encoding exceptions with reliable NASM encoding syntax where available.
9. Continue bounded C clusters after their static boundaries and contracts are
    reliable. Three resource decoder leaf routines at 1C82/1C8A/1CA3 now have
    tested C cores; see dat.md. Recover the full 1BAF decoder and 1D2E cached/DOS
    read provider integration next, including malformed sizes, errors and aliases.
    The complete 1D2E wrapper now has a C11 core verified in 45 bounded cases
    covering all 106 instructions; see dat-io.md for ignored cache errors,
    returned ES, provider DF effects and wrap. Connect the 1BAF decoder to it next.
    Do not substitute the static extractor's stricter checks. No SDL3
    integration or gameplay milestone is needed to progress these investigations.
