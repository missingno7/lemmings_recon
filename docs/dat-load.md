# Native DAT resource-loading caller

LoadDatResource at CS:1B79..1BAE now directly calls the native CheckDatFile,
OpenDatFile and DecodeDatSection cores. Its 53 translated instruction bytes exclude
the skipped UNKNOWN byte at 1B97. DecodeDatPreservingSegment at 1BA9..1BAE is a
separately callable six-byte shared tail; its bytes and sites overlap the loader
and are counted once. The symbol ledger owns names and original call continuations.

c/dat_load.c takes the explicit transient file/cursor/stack call contract, the
original data-segment bindings, and existing file/read service contracts. It uses
direct C calls rather than machine-register adapters between normal functions.
The register adapters are only original-code testing boundaries. Canonical memory
remains the sole persistent state; original save/return-word effects remain live.

## Original caller behavior

The caller saves CX before checking the file, then restores it from the stack.
CX supplies the compressed-buffer segment. A returned carry or nonzero caller-
frame critical-error byte selects the original retry screen at 4B1C. Otherwise it
opens the file, tests the critical-error byte again, copies returned AX into BX,
and selects DS=CX before decoding. It **does not test carry from file opening**.
An open error without a critical flag therefore becomes the decoder's file handle;
no host error correction is added.

The outer retry path saves DX/CX/ES/DS/DI/SI, calls 4B1C, restores those values from
live words, and repeats the complete check/open path. AX/BX/BP/flags from the callee
remain live into that repetition. The shared retry contract now exposes AX as
well as BX/BP/flags: even when the next check overwrites AX, its original value
can be observed in subsequent save-frame residue. CheckDatFile's own retry loop
still resets AX before its next attribute request.

The decoder tail pushes incoming DS, calls the native section core, pops DS from
live memory, and returns. This preserves the tail's entry DS, which is the loader's
new compressed-buffer segment rather than its original filename/data segment.
A tested literal write changes the saved DS high byte without changing either
active return word; the final POP observes that change. The tail performs no
automatic DOS file close.

File-check failure transfers to 1949 with the check/loader save frames intact.
Decoder-read failure transfers to 04D0 without consuming the decoder return word
or restoring the tail's saved DS. These are distinct explicit result exits and
matching oracle IPs; their print/cleanup bodies are still untranslated.

## Bounded integrated verification

tests/dat_load.py compares original caller/file/cache/read/decoder instructions
with the connected native C cores in 24 cases. All thirty caller instruction sites
and eight branch edges execute. It compares full 1 MiB memory, every register,
defined flags and complete DOS/retry-call input traces. Cases include the three
original sound packets through direct reads, cache hits and cache creation, ignored
open carry, critical-error retries, inner file-check retry/fatal paths, both decoder
fatal paths, direct shared-tail calls, saved-DS corruption and three stack-wrap
points. Two additional cases begin at the constructed 1B7D post-check continuation
with its saved CX word to exercise carry/critical caller routing independently.
They do not prove that a normal quiescent CheckDatFile call returns carry or that
the branch is dead under all other states.

Three compiled caller mutations are detected: retrying on open carry, restoring
DS from a host temporary, and unwinding the tail on decoder failure. Dependencies
are compiled without their other mutation macros. Original execution is capped
at five million instructions per case; the standard runner caps the suite process
at 120 seconds including native calls. Only final AND's undefined AF is excluded
on normal decoded returns; defined fatal-exit flags are compared fully.

The mapped, twenty-bit memory domain uses quiescent interrupts and clear TF.
Instruction bytes and active callee return words remain intact; data save slots
may alias outputs. File and retry-screen bodies remain declared verification seams,
not completed native DOS or rendering/input implementations. The 4B1C fixture
returns through the original pushed word with deliberate register clobbers and
clear critical-error state. No original game boot or gameplay discovery is used.

Next connect the higher section-selection/seek/close callers and startup resource
ownership, investigate UNKNOWN cache allocation at 1ED7, and translate retry UI
and fatal cleanup. The connected load pipeline is not a complete native game.
