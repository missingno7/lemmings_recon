# Main-image callback evidence

All addresses below are hex. Data offsets use the original relative DS frame 09A9;
its flat image start is 09A90. The symbol ledger owns both the segment-relative
offsets and the names. NASM address assertions check every symbol at its flat image
location. C receives SEG09A9_ offsets for data fields. Original live memory remains
the source of callback state.

tools/indirect.py reproduces metadata/indirect-evidence.json from the canonical
bytes and the recovered CFG. It identifies direct accesses, the drawing-slot
constructor and the local AX definition before each object pointer store. Its
indexed-write candidate report is deliberately separate from a proof of aliases.

| Site | Pointer source | Known targets | Remaining domain obligation |
|---|---|---|---|
| 1407 CALL AX | Four enable-byte/word records at DS:2013, stride 3 | 1410, 1462, 1490, 14A0 | Incoming DF, DS and live flag/pointer writes |
| 42A5 CALL AX | Word at DS:25A0 | 4252, 4334, 4359 | Indexed/string writers, segment aliases and unknown code |
| 4CC9 CALL BP | 4C88 LEA BP,503B; saved loop frames | 503B | 4C7E entry, balanced callee returns and stack/buffer aliases |
| 4D18 JMP BP | Outer BP restore at 4CDA | 503B | Same input-loop contract; tail return consumes the caller's frame |
| 715B CALL AX | Object record+14 saved at 70F0 and popped at 7159 | 6170, 64D9, 65D8, 66D7, 6817, 6957, 6A97, 6BDB, 6CFC | Active record lifecycle, clones, slot writes and segment aliases |

These 18 edges are now in the static CFG and callee/caller ledger. Every target
domain remains explicitly incomplete. A decoded known edge does not remove the
unresolved indirect transfer or establish a whole-program finite target set.

## Display and input tables

The initial display records are `00 1014 00 6214 00 9014 00 A014` in byte order.
13DC sets the last three enable bytes to FF and iterates four records. The first
enable byte remains zero in the visible startup path, so discovering 1410 from its
stored pointer does not prove that startup calls it. 1410 clears later enable flags
and can re-enable DS:201C; 1462 also changes enable flags. There are no direct
pointer-word stores in the recovered main code. This fact leaves non-absolute writes
and unknown regions open.

The routine has no CLD. LODSB tests the enable byte; LODSW supplies AX without
changing that test's flags. SI/CX are saved around each callback. With DF set, the
routine traverses backward and reads different words, including a pointer that
overlaps the enable byte. Native code must preserve the incoming direction flag
and the live pointer/enable behavior.

Known table targets add two previously undecoded routines, 1410..1461 and
1490..149F. Their maintained names are ProbeDisplayCombination and ProbeColorCrtc.
The former references CS:1536's visible display-pair words; 1462 uses the six-byte
lookup at CS:1530. Hardware-provided indexes have no local upper-bound check, so
out-of-table reads remain part of the hardware/index contract.

DS:25A0 initially contains 4252, the mouse polling routine. 4A68 writes 4334 and
4A80 writes 4359 for the two joystick paths. 42A5 saves DX, invokes the live word
and restores DX before checking DL. No validity check selects a replacement target.

## Object record producers and input-loop stack

0FC1..0FF1 initializes nine callback slots at DS:002E..003E. All 32 recovered
`MOV [SI+14],AX` object stores have a local AX definition reading one of those
slots; the intervening instruction at 3311 preserves AX. The active object array
starts at DS:0088 with a 2D-byte stride. Generic indexed stores, record cloning
and activation still require an ownership proof before the producer domain closes.

DrawObjectSprite at 706F pushes the record callback before it reuses DI for the
destination address. Both the direct draw path and optional erase path recover
that pointer in AX at 7159. DX receives the saved low-three-bit pixel alignment.
The callback consumes a normal near return; the original outer DI is then restored.
The pointer must continue to be read from the live object record.

ReadCodeInput at 4C7E installs BP=503B. Both loop save sets preserve it even when
the declared callees clobber BP. The final 4D18 transfer is a JMP, so the callback's
RET consumes the original ReadCodeInput caller's return word. It must remain a tail
continuation in translation. There is one recovered direct incoming call to 4C7E,
at 4996; alternate incoming control and buffer/stack aliases remain open.

## Bounded verification

tests/dispatch.py runs only identified caller ranges using constructed memory and
explicit callee boundaries. Thirty-two cases execute 214 original caller instruction
sites. Display fixtures cover ordinary flags, a first-probe enable, clearing later
flags, DF-set traversal and an altered live pointer. Input polling checks DX
save/restore for each known callback and an altered pointer. Code input exercises
repeated waits, cursor blinking, letters, delete and enter while callbacks clobber
saved registers. Object fixtures cover all nine callbacks, both erase paths, an
altered pointer and the visibility skip.

The altered-pointer cases prove that the original callers accept the constructed
live word. They do not prove that an unlisted value is reachable in an unmodified
game run. Callback bodies are intercepted, so these are caller routing/stack tests,
not device, graphics, callee, C or game execution coverage.

The evidence census currently contains 1,453 direct data memory operands and 1,130
indexed write operands in recovered main code. These are operands rather than
distinct functions or alias-resolved writes. Stack effects, implicit memory use,
platform services and unresolved bytes prevent a whole-program write claim.
The saved INT08 vector at DS:1FBE is named and its direct producer is recorded;
the far chains at 1899 and 4C6C now have explicit external IRET edges and bounded
caller checks. Complete provider/timing and memory-alias contracts remain open.
