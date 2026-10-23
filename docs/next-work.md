# Next work

Choose by: what would force a C translator, or now a port maintainer, to guess?
Addresses are main-image offsets unless a component or DS frame is named;
`tools/where.py ADDR` finds the line. Counts: [completeness.md](completeness.md).
Freeze bar: [semantic-audit.md](semantic-audit.md). Method: AGENTS.md.

## Immediate mode

The VGA + AdLib scope is close to classification and control-flow closure: the
main image has 450 UNKNOWN bytes (12 code-looking routines with no incoming edge,
three stored RETs, two protected write-selector MOVs), every legitimate indirect
transfer has a closed target set, and the AdLib driver has a complete engine
specification with 9 UNKNOWN bytes and a closed dispatch domain. The binding work
is now translating that understanding: the AdLib engine, the remaining
untranslated entries and whole-game composition.

## Closed exceptional behavior (no further investigation)

These are characterized original behavior. Implementations preserve them by
translating the ordinary code over the original memory layout, or report them as
explicit unsupported-runtime limitations. Reopen one only if a legitimate
(non-corrupted) path is found to depend on it.

| Item | Class | What implementations preserve |
|---|---|---|
| Control escapes S (no-strip sprite, 715B), D (first corrupted detector call to CS:0061 at 1407), I (partial 25A0 clear calling CS:0000 at 42A5), R (steel near return to 3709), Z (one-row dirty width-0 return to 0101) | characterized corruption escape | Specification ends at the stated transfer; native reports an unsupported escape, never success |
| N01 creation race (30CC..314B via 1874 -> 3E6F -> 4013) and the record spill it causes | characterized race | Creation and timer IRQ write order over the same record array; later spill evolution is ordinary code over that memory (no surviving-count proof needed) |
| N06 AdLib request/update ordering (03B9/03BE, FF/F0 last writer wins) | characterized race | Request latch write order |
| W01 width-0 RCR sweep before 8DF1; W02 stale/overlong resource, palette, template and stream relations | characterized overflow/alias | Renderer and loaders translated over canonical memory, including the out-of-range writes |
| Level 7 stack crossing to SP=49B6 | characterized alias | Physical stack placement while the stack is modelled; later its observed effect |
| Former blockers B02-B07, B10, B14 parts that ask for every damaging writer, arbitrary IRQ/stack survival, arbitrary renderer aliases, provider footprints or corrupted returns | not blockers (AGENTS.md) | Nothing beyond the items above |
| RETF selector-EA limitation of the verification executor | verification transport debt | Not an original semantic question |

Platform-conditional assumptions stay in metadata/platform-profile.json
(PC01..PC08: startup clear, 1407 detector, INT33 AX=0003, DAT/cache file
continuation, process-lived AdLib, startup marker, graphics arena, completed
floppy/protection seam).

## Open semantic items (VGA + AdLib), in impact order

1. **Typed level codes selecting 120..255.** DecodeLevelCode accepts any
   self-consistent code, so a player can reach selection 120..255 and group 4..8
   (1F6E). 4EBC then indexes the four-entry sign table CS:4EE7 past its end and
   uses code bytes as UI+1000 offsets; 197D reads order bytes past DS:5565 into
   the odd-table buffer. This is an ordinary user-input path: characterize what
   each such code loads and draws, beside the ASM, so C can model it exactly.
2. **Code-frame UNKNOWN with no incoming edge** (450 bytes): number formatter
   1250, parser arms 131A, vector install 1592, timer reload 1696, PIC EOI 18B7,
   floppy motor off 1908, 357E, 48B0, tick wait 501C, overscan colour 5517,
   pre-shift 5D18, block copy 71CA; stored RETs 531D/5424/55B6; 084E/087F. They
   stay UNKNOWN with these reasons unless an edge is found; nothing ordinary
   depends on them. AdLib 0014 and 05A0..05A7 are the same kind.
3. **Remaining untranslated main entries:** CriticalErrorHandler 18F8 (READY;
   host in c/dat_files.c as the DOS critical-error callback), MouseEventReturn
   0F6F, CopyReverseMatchReturn 1C9F, and the protection entries 063E, 0659,
   0DB3, 0DBD (startup/protection as a whole, 054E..13DB, beside the derived
   protected views).
4. **Protected transitions 066C/0E1C** are hand-offs into the fully derived
   protected streams; they stay listed until startup/protection composition is
   translated.

Closed in the 2026-10-23 round (details beside the ASM and in the ledgers): DS
storage (all 18,026 DS-frame bytes classified; the stack lies outside the image
at SS = load+143E), legitimate targets of 1407/42A5/4CC9/4D18/715B, opaque
LEVEL/GROUND/terrain fields (unread), divide sites (none can fault), the 1FF2
arena tail (unused), the 004A FF producer (none), checksum 8363 (no caller),
legacy block splits that were miscounted as untranslated routines, and the
AdLib engine, song titles and command domain.

## Native work after closure, in order

1. AdLib music/FX engine in C over the driver memory (READY: src/sound/adlib.asm
   header), with an OPL register sink and native synthesis; tokens 88..AF are an
   explicit runtime failure.
2. Bind entity sound services (today NULL bindings stop sound-enabled actions).
3. Special-graphics briefing redraw, INT61 rebinding after 057B, private IRQ 0F70
   delivery, protection persistence (russell.dat), validated timing.
4. Whole-game lifecycle in the native host: startup, menus, level load, gameplay,
   results, progression, failure and exit, with a feature matrix
   (semantic-audit.md).
5. SDL3.

## Alternatives (inventoried; do not block VGA + AdLib)

Tandy driver (raw dispatch 98..9F, out-of-allocation state 5958, score bytes),
PC-speaker dispatcher and trailing bytes, joystick (port 201), alternate
display/BIOS paths, mode 1 controller alternatives. They complete the full
freeze and are translated or marked ALTERNATIVE in the C status accounting.
