# Precise next frontier

Current working order follows the Pre2-style semantic ASM/dependency pass in
bottom-up.md. Review source contracts and the fresh graph before expanding C.
WriteDecimalByteDigits (4BC2) and LoadSelectedLevelResources (197D) now have connected
native cores verified in 270 and 59 cases respectively. The closed 378A graphics
record copy and 389F coordinate collector now pass 131 and 159 native cases.
The 37C2/3839 SS cell writers now pass 123/386 cases, and their four-call setup
span with 378A/389F passes 105 integrated cases. The 4DF8/8808 VGA-clear/layout
leaves and 368E/36AD callers now pass
33/151/27 bounded cases. The minimap sample, connected row and column now pass
67/49/62 cases, including two complete thirteen-column cycles. Continue the
terrain/far drawing dependencies of 36B6/394F next. The 9967/9A15 clipping
and dirty-cell leaves now compose in the 882D preparation span with 59/2066/102
cases. Continue the 885E drawing body, preserving its plane/shift/segment state.
Keep the platform/fatal/IRQ seams and broader static obligations
below explicit; module extraction did not resolve UNKNOWN bytes.

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
    tested C cores; see dat.md. The 1BAF decoder and 1C87 shared match entry now
    call native read/bit/copy cores directly, verified in 128 integrated cases;
    see dat-section.md for unchecked sizes, malformed headers and fatal exits.
    The complete 1D2E wrapper now has a C11 core verified in 45 bounded cases
    covering all 106 instructions; see dat-io.md for ignored cache errors,
    returned ES, provider DF effects and wrap. Filename preparation, cache selection
    and startup disabling at 1E1C/1E64/1ED1 now have tested C cores; see dat-cache.md.
    File open/attribute wrappers at 1CB9/1CD9 now call native cache cores and have
    40 bounded differential cases; see dat-files.md for the explicit 4B1C game
    retry seam and 1949 fatal transfer. The 1B79 caller and 1BA9 shared tail now
    connect those cores directly, verified in 24 integrated cases; see dat-load.md.
    Continue startup resource ownership and higher callers next,
    using the tested 1916 raw-resource reader where applicable; see resource-raw.md.
    The 1B42 RLE helper is also native, with 303 cases covering its incoming DF,
    overlaps and rollover AL bug; see resource-rle.md. The four special-resource
    VGA strip entries at 8238/8243/8249/824F now share a tested native core:
    28 cases cover all 122 sites and 22 branch edges, including plane contents,
    port/MMIO order, IF/DF and live stack/heap-pointer aliases; see special-blit.md.
    The higher 1A7B metadata/RLE/strip and two-section normal VGAGR caller now
    connects these native cores in 20 cases, covering all 87 caller sites and
    621 integrated sites; see special-setup.md for live restores and unchecked close.
    The upstream 197D resource-selection caller now directly connects native
    decimal/raw/file/cache/decoder cores in 59 cases (108 caller/560 integrated
    sites, nine caller edges); see resource-select.md. It preserves wrapped order
    bytes, in-place sections, odd overrides, long/short ground reads, live saved
    counters/order/DS, ignored closes and both fatal seams. The 4BC2 decimal leaf
    passes 270 native cases, including controlled live RET aliases; see decimal-digits.md.
    The 378A graphics-record copy and 389F coordinate collector now have C11
    cores with 131/159 cases, including all80 supplied LEVEL sections. Their
    221 original bytes/89 instruction sites preserve stale inactive slots,
    unchecked wrapped ground-type lookup, DF, live saved cursors/counters/RET,
    full type-one comparisons, zero-X acceptance and the repeated+0A default bug.
    See object-records.md and src/level_objects.asm for ownership and bounded domains.
    The 37C2/3839 SS cell writers are native in 123/386 cases, including live
    saved dimensions/base/input/RET aliases and unchecked zero-size loops.
    The 376A..3775 span directly composes all four object cores in 105 cases,
    with independent SS/record checks and explicit changed-return boundaries;
    see interaction-cells.md. This does not translate the entire 36B6 function.
    The 4DF8 clear and 8808 layout leaves are native in 33/151 cases, and 368E/36AD
    connect them in 27 cases; see vga-clear.md, drawing-layout.md and level-drawing.md.
    Keep the isolated Unicorn RETF hook/SP artifacts explicit in future far callers.
    The 7A39 sample and connected 7A25/796F minimap row/column are native in
    67/49/62 cases, with all 96 integrated sites and fourteen edges; see minimap.md.
    The 9967 clipping and 9A15 dirty-cell leaves now have direct native cores,
    verified in 59/2066 cases. Their 882D..885D preparation span passes 102 cases;
    see drawing-clip.md, drawing-dirty.md and drawing-inputs.md. Its 49 bytes
    exclude the seven-site original 8822 prologue and end before 885E drawing,
    88AB RETF or a changed childRET. Continue the 885E plane/shift drawing body,
    then 7C67, after establishing dispatch, VGA access and source-plane contracts.
    Keep DS:66F8/66FA/66FC/66FE and A949 live, including saved words and shifted
    cursor aliases. Preserve original far-return, signed/sign-only clipping,
    segment/offset wrap, self modification and unchecked zero-size behavior.
    Native VGA ownership and asynchronous IRQ behavior remain open.
    Investigate UNKNOWN allocation code at
    1ED7, and recover native ownership of the fatal 04D0 continuation.
    Do not substitute the static extractor's stricter checks. No SDL3
    integration or gameplay milestone is needed to progress these investigations.
