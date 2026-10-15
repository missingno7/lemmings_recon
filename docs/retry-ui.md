# Resource retry screen composition: work in progress

`ShowResourceRetryScreen` at `4B1C..4B5B` occupies 64 decoded bytes and
21 instruction sites. Its maintained ASM and ledger names describe the original
caller. The C implementation in `c/retry_ui.c,h` is an unverified composition;
the ledger deliberately retains `UNTRANSLATED`, and no C coverage or full-caller
differential acceptance is claimed. The separate child reports do not verify
this composition.

The caller invokes display setup, palette slot 1, full-page clear, background
drawing, text drawing, page copy, display-status wait, alternate display-start
programming and palette slot 2. It then resets the scan-code byte and polls the
button word or scan-code byte through the frame-free retry-input boundary.
After input it invokes palette slot 1 and full-page clear again, clears the
live `DS:1FDF` byte and returns.

`ResourceRetryPromptText` names 49 pinned bytes at `DS:4ECF`: two text records
containing "Insert Disk into Drive" and "Then press any key". The text stream
uses live DS and incoming DF. Its renderer's separate game-data segment must
not replace that DS. BIOS-returned register, segment and stack state must flow
through every child, and each actual CALL/RET word remains observable in the
canonical memory image. Missing providers and changed returns stop before
later caller effects.

Acceptance still requires a dedicated bounded original-versus-C suite for
the complete caller: ordered bus/port effects, RAM and VGA state, defined flags,
all live registers, returned segments and stack, each child stop and changed
return, finite input updates, and finite mutation witnesses. The source mutation
switches are test scaffolding, not evidence of detected mutants. Installed IRQ
scheduling, device timing and broader resource ownership remain open.
