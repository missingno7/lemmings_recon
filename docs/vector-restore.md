# Keyboard and private interrupt-vector restoration

`RestoreKeyboardVector` (1582..1591,16 bytes/seven sites) and
`RestorePrivateVector` (0FA0..0FB1,18 bytes/eight sites) each push DS before
reading saved vector fields, invoke DOS INT21/AH25, pop DS and return near.
The keyboard function usesAX2509 and the saved pointer atDS:1FBA/1FBC. Startup's
DOS3509 query at0050..0059 and the later1565..156E query populate these words.
The private function reads the mutable selector atDS:1FC6, then the pointer at
DS:1FC2/1FC4. Startup initializes the selector to0C;11E7 and133F assign74.
Names, offsets and old entry aliases belong to the symbol ledger. No stored
bytes or classifications change.

PUSH DS can overwrite a pointer or selector before the following reads. The
original order is push, selector where applicable, pointer offset, pointer
segment, then interrupt. After the explicit returning DOS provider, POP DS uses
the returnedSS:SP. Its value can differ from both entryDS and provider-returnedDS.
The outer RET likewise uses the live stack after that pop. Each machine word
uses low byte then physical+1 with20-bit wrap; SP wraps at16 bits between words.
No instruction in either leaf changes flags; provider flags remain live.

`c/vector_restore.c` implements direct logical cores and boundary adapters.
Twelve transient fields carry the general registers, DS/ES/SS/SP and flags at
the provider boundary without a persistent game-state copy. A provider may
change those fields and canonical memory, returning in the sameCS after INT.
A missing provider leaves the actual pushed frame active and stops at0FAE or
158E, after the pointer reads and DS switch; it does not pop DS or consume RET.
The ready cores stop before the original RET; adapters consume it through the
optional bus. NULL bus accesses the same canonical RAM. These are declared
DOS-provider contracts, not an implementation of DOS or IRQ scheduling.

`tests/vector_restore.py --original-only` compares pinned instructions against
an independent push/read/provider/pop model before native compilation. The
matrix covers every private vector byte, keyboard calls, varied flags and
ready/missing-provider exits, three loads, stack/field aliases, changed provider stacks, provider-written
saved DS and returns, A20/SP boundaries and VGA-backed pointers/stacks. A DOS
provider also writes a real IVT offset/segment pair over the saved DS and near
return words; POP DS and RET must see those new values. Both leaves have no
original branch edges. The same provider/model and complete RAM, register,
defined-flag, bus-order and VGA-state checks apply at the core boundary.

Four finite mutants preload fields before PUSH, ignore returned stack coordinates,
restore entryDS instead of the popped word, or return an entry-time stack word.
Each must complete and disagree at both entries. Resource/provider/oracle errors,
timeouts and budget exhaustion never count as mutant detection. Workers have
120 seconds,384 MiB process/640 MiB tree limits; compilers have60 seconds/256 MiB;
original calls have20 instructions; callback traces cap at64 events and providers
at one call. Callback errors hard-exit87 and exhaustion86. The parent owns each
temporary DLL directory until its worker is terminal. Reports hash dependencies
before work and afterward and contain no memory dumps. Actual DOS/IRQ behavior
and the broader cleanup caller remain open.

The final gate passes328 adapter comparisons and328 auxiliary core probes:
276 private-vector and52 keyboard-vector cases. There are324 NULL-bus adapter
comparisons and324 NULL-bus core comparisons, repeating the ordinary-RAM cases.
All15 original sites execute across34 translated bytes, with no branch edges.
All four compiled mutant variants complete and disagree at both entries: eight
separate observations, counted as four variants. The broader04D0 cleanup still
requires composition with the now separately verified16A9 timer/PIT/time core,
preserving all live provider/stack effects; see timer-restore.md.
Aggregate C coverage remains pending the separate complete terrain acceptance.
