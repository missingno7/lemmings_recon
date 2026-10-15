# Driver command latch setters

AdLib 0022/002A/0032 and Tandy 0019/0021/0029 each own eight bytes:
PUSH DS; PUSH CS; POP DS; MOV [moffs16],AL; POP DS; IRET. Commands
3/4/5 select those entries from each installed INT61 dispatcher. Their stored
bytes are respectively ED/F0/EE and 4A/4C/4B. These are byte latches; their
names do not establish complete music/effect stream semantics.

The setter cores stop before IRET. DS is selected by the actual temporary
stack POP, and restored by a second live POP, rather than cached entry values.
Before IRET, the setter bodies preserve arithmetic flags and IF/DF.
AX/BX/CX/DX/SI/DI/BP/ES/SS stay unchanged throughout.
The adapters read IP, CS and FLAGS sequentially from the live SS frame and
advance SP by six modulo 65536. Each word starts at its 16-bit offset; its
second byte is the next physical byte with 20-bit wrap. Optional raster bus
accesses apply to both saves and the latch. No tail performs port I/O.

Both entry dispatcher prefixes now have direct C cores. The initial AND AH,AH
clears CF/OF and defines PF/ZF/SF; AF is undefined on the AH0 exit. Up to five
DEC AH operations preserve CF and define the other arithmetic flags. AH0/1/2
stop explicitly at the untranslated update/detection/reset bodies, without
consuming the interrupt frame. AH3/4/5 directly compose the setter cores and
leave AH zero. AH6..FF executes all five decrements and IRET with AH reduced
by five; these commands are not silently rejected or clamped. Each core reports
its continuation and exit kind. The adapters consume IRET only for IRET exits.

The exact native ranges are AdLib 0000..0013 and 0015..0039 (57 bytes), and
Tandy 0000..0030 (49 bytes). AdLib byte0014 remains UNKNOWN and outside C
accounting. Entry-prefix and setter byte ranges do not overlap in the ledger.
The other driver services, playback, port timing and command stream dispatch
remain untranslated.

The native campaign is `tools/difftest.py sound_latches`. Its report is
build/sound-latches-differential.json and is valid only for its recorded hashes.
It compares 730 fixtures at core and IRET/untranslated boundaries: 126 focused
setter fixtures, all 256 AH selectors for both drivers, 90 live-stack/bus
dispatcher connections and an exact AX0405 request for each driver. The AH4
selector fixtures already use AX040C. All 106 bytes/65 sites and 27 branch
edges are covered,
with 8,376 ordered byte events and nine completed mutation witnesses. Six
additional original-prefix-to-native-setter handoffs retain their own boundary.
RAM/null-bus repeats, independent ordinary stack/latch and dispatcher arithmetic
expectations, full canonical RAM/register/defined-flag comparison, actual IRET,
VGA stack/latch state and before-read/after-write provider changes are checked.
Each original call has a 64-instruction budget; native callbacks have a hard
64-event exit. The worker has 180 seconds and 384/640 MiB process/tree limits;
temporary libraries are removed after every outcome. Guard exhaustion and
compiler/oracle errors are failures, never mutation credit.

Main 2E04 uses AH=4 with AL=05 or 0C when live DS:2010 equals FF and DS:25A7
has either low bit set. The dispatcher decrements AH to zero before entering
the setter. The original interrupt frame restores caller flags only when its
live SS words survive. A latch/stack alias can alter restored DS, CS, IP or
FLAGS. Main 2EB2 then rereads DS:[SI+8], so these effects must remain explicit
when composing the countdown transition. AdLib 051C reads/clears F0, and Tandy
071B reads/clears 4C before their separate effect stream dispatch. That supports
the request-latch handoff; it does not verify those consumers. Driver code/stack
aliases that
modify forthcoming instructions, asynchronous interrupts, untested VGA modes
and full playback/dispatch ownership remain open.
