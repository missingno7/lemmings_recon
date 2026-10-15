# Palette row composition

`563E..566B` steps one packed palette byte per iteration through the high,
middle and low channel helpers. `56E2..570B` steps three sequential RGB bytes
per iteration. These are 88 caller bytes/47 sites; the previously translated
channels add 144 shared bytes/69 sites, producing a 232-byte/116-site union.

Both entries clear CH once. Their LOOP instruction retains the original
16-bit decrement: initial CL=0 executes 65,536 iterations. They use explicit
INC SI and INC DI, so DF does not reverse the cursors. Byte addresses wrap at
16 bits before physical 20-bit translation. All data remains in canonical RAM.

The packed loop clears BP, pushes live CX before loading DS:SI and DS:DI,
then keeps DL/CL as that byte's source/target across three real near CALLs.
The results are ORed into DH and written to DS:SI before POP CX. A source
store can therefore change the saved counter; a PUSH can change the bytes
that will be read. Each child uses its actual SS frame. The final AND BP,BP
reports the sticky 00FF change marker, with a clear sign flag.

The RGB loop clears only BL, preserving BH. Each component reads the live
source and target, calls the signed two-step helper, writes its result and
increments both cursors before the next component. It must not snapshot the
target triple or convert either buffer. BL remains FF after any change,
including later equal components. The final AND BL,BL sets SF when BL=FF.
The differing BP/BL marker widths and final flags are intentional.

The core stops before the caller's RET. All six caller child returns and the
two nested packed-wrapper returns remain live. A changed return stops before
later caller effects; the adapter alone consumes the live outer return word.
Optional byte callbacks fall back to RAM. Word high bytes use physical+1,
with SP wrapping only between words. Intact code, quiescent IRQs and the
permissive 20-bit word bus are explicit verification conditions.

The test has a sequential scalar model for ordinary RAM rows, full CPU/RAM,
phase-defined flags, ordered byte accesses, device state and NULL-bus repeats.
Fixtures cover overlap, cursor/stack/physical wrapping, VGA buffers and stack,
PUSH-before-read effects, saved counters and all child-return positions.
Oracle/model failures and time/memory/access guards never count as mutants.

The full zero-count cases execute 65,536 iterations at each core entry.
Data writes in their disjoint, zero-filled RAM layout cannot change code or
return frames. CALL/PUSH still write the original live stack words.
Selective tracing observes caller and stack-frame instructions while every
data access still receives its original flags and an instruction-derived
defined-bit mask. Small sanity cases require exact equality with the ordinary
full-instruction oracle, including event masks and order. Executed-site coverage
comes from the ordinary fixtures, separately from these long-loop results.

The campaign has a 600-second deadline with cleanup margin; disposable workers
have at most 240 seconds, 384 MiB per process and 640 MiB per Windows job tree.
Normal originals have 100,000 instruction steps; zero-count originals have
12,000,000. Long traces stop at 2,000,000 events and do not retain instruction
histories. Parents own temporary DLL directories. Palette allocation/pointer
ownership, actual palette devices, scheduled IRQs and hardware stack-limit
faults remain separate obligations before the higher transition loops close.

The scoped native gate passes 89 fixtures at both boundaries and two full
65,536-iteration core cases, with all 47 caller/116 integrated sites and
four caller/18 integrated edges observed. Six compiled mutants complete and
mismatch. The maintained ASM groups these 232 palette-step bytes in
`src/palette_steps.asm`, preserving physical order and every original encoding.
The palette port writers and the higher transition loops remain untranslated.
