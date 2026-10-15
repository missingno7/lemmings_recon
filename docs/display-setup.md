# Display setup and shared layout entries

SetupDisplayModeAndLayout4BE7..4C16 comprises48 bytes/14 caller sites. It writes
FF toCS:83BE (the last byte of the shared checksum-storage window), executes
NOP andCLI, setsAX=0090 and callsBIOS10. All twelve returned CPU fields remain
live; the provider returns in the sameCS. STI is unconditional. The shared
InitializeDisplayOrigins4BF5 entry skips the earlier store/BIOS/STI and writes
DS:1F76=0,1F78=6D60,1F7A=0 in order. SetupDisplayLayout4C07 skips those stores
as well, setsAX=0280/BX=015E and reads the liveDS:1F76 intoDX.

The original farCALL at4C11 targets8808 in the same loaded code segment. Its
segment operand at4C14 is one of the63 unpacker relocations. A constructed
intact loaded image supplies this operand; no runtime game snapshot is used.
The native connection calls the logical layout core, preserving the original
pushCS/push4C16 frame. The layout leaf stores width,height,origin, truncated
pitch and low product extent into the returned/liveDS. MUL usesBX, not a
reloaded height field, and definesCF/OF only. Other arithmetic flags become
undefined; controls and all other preserved state remain explicit.

The actual farRET consumes liveIP thenCS words. A changed target stops before
4C16, including targets with the same numericIP but changedCS. READY stops
before4C16; only the register adapter consumes the live outer nearRET. Missing
BIOS mode service stops before4BF2 after theCS store/CLI/AX setup and retains
all frames. A missing provider is irrelevant to shared entries that skipBIOS.
Words access low byte thenphysical+1 with20-bit wrap, andSP wraps16 bits between
words. Bus callbacks own CPU memory access and may expose RAM/VGA effects;
the BIOS provider may mutate canonical memory and explicit device context.

tests/display_setup.py passes55 fixtures across all three entries and both
logical-core/adapter boundaries, with51 null-bus repeats at each entry/boundary
and four completed mutants. It checks the original caller and child instructions against
an independent model before native acceptance. It compares full RAM, twelve
CPU fields,CS/IP,definedflags,ordered byte accesses,BIOS requests and VGA state.
The original RETF executes read-hook-free after the documented Unicorn hook
observation; no instruction or target is patched. Segment-limit probes keep
the candidateCS words equal and are identified separately: they do not settle
hardware stack-limit behavior or the emulator's batch-read choice. Other cases
exercise the actual ordinary far return, plus controlled live return aliases.
The three overlapping entries and existing26 child bytes are counted once.
Intact code, sameCS BIOS return, clearTF and quiescentIRQ define the bounded
domain. No BIOS hardware/timing or full retry UI ownership is claimed.

Native workers are serial and bounded to120 seconds,384MiB per process and
640MiB per tree. Callbacks have hard access/service budgets and fail the worker
on exhaustion or error; failures never count as mutant evidence. Temporary
DLLs belong to the parent. Four completed mutants must reveal real mismatches:
discarded BIOS-returnedDS, omittedSTI, ignored changed farRET and reversed far
CALL push order. Global C coverage and complete terrain acceptance are separate.
