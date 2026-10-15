# Palette channel steps

Five pinned entries share 144 decoded bytes and 69 instruction sites:
`566C..5684`, `5685..5695`, `5696..56E1` (including the shared `569B` suffix),
and `570C..5725`. They make no DOS or device calls. The two wrappers make real
near calls to `569B`; their return words remain live in canonical SS memory.

The packed channel helper decodes bits 3 and 0 of AL and BL as a two-bit value,
with bit 0 carrying the high component bit. It moves the current value one
unsigned step toward the target and repacks AL. AH contains the new high bit;
BL retains the decoded target, and BH retains `(incoming BL << 1) & 2`.
A difference writes BP=00FF; equality preserves incoming BP. The low entry at
`5696` first masks AL and BL with 09. The high/middle wrappers shift their
inputs right two/one bits, mask, call the helper, then shift AL and BL left
two/one bits. AH and BH retain the helper's side effects.

The RGB helper at `570C` compares AL and AH with signed JG, even for bytes
outside the usual DAC range. On an initial difference it takes one step,
sets BL=FF while preserving BH, compares again, and takes a second step if
needed. Equality leaves BL unchanged. BP is preserved. It returns at `571E`
except for a second decrement, which returns at `5725`. Flags come from the
last CMP or INC/DEC; INC/DEC preserve carry from the immediately preceding
CMP. The implementation must not use an unsigned clamp or clear the sticky
change marker on an equal component.

The logical core stops before the outer RET. The wrappers push `567C`/`5691`,
consume the actual child near return, and stop before post-call shifts when
the target changes. The adapter alone consumes the outer return. Bus callbacks
are optional, with canonical RAM fallback. Stack words use low then high byte
at physical-address+1 with 20-bit wrap; SP wraps at 16 bits between words.
The code bytes must remain intact. These routines do not establish palette
buffer ownership or valid indices for the higher `531E/536C` transitions.

`tests/palette_channels.py` checks all 65,536 input-byte pairs at each of the
five core entries against the original ASM and an independent channel/flag
model. One reused Unicorn machine per entry avoids allocating a memory image
or retaining an instruction trace per pair. Matrix workers guard data accesses
to the wrappers' two-byte frame, stop before the outer RET, and compare whole
RAM at matrix completion. Instruction coverage is measured separately by the
boundary fixtures, which execute the original instructions with full phase
flag and ordered byte-access observation.

The boundary fixtures compare full RAM, all CPU fields, defined flags, device
state and bus events at both core and adapter exits. They include stack offset
and physical wrap, varied incoming IF/DF, VGA stack words and changed child
returns. The changed-return provider changes one stored frame byte in the
constructed VGA fixture; it is an explicit provider test, not a hardware claim.
Ordinary RAM fixtures also repeat with a NULL bus. Callback budgets, timeout,
compiler failures and oracle/model failures never count as mutant detection.

The campaign has a 330-second deadline, leaving cleanup time before its
360-second supervisor. Each disposable worker has a 120-second bound and Windows limits of 384 MiB
per process and 640 MiB per tree; compilation has 60 seconds/256 MiB. Matrices
have at most 128 instructions per pair and constant-sized state. Boundary bus
traces have 256 events. The parent owns temporary DLL directories and removes
them after workers terminate. Hardware segment-limit faults, IRQ scheduling,
palette devices and the higher palette loops remain separate obligations.

The native gate passes all 327,680 byte pairs and 88 fixtures at both core and
adapter boundaries, including 81 NULL-bus repeats per boundary. All 69 sites
and 14 branch edges execute in the boundary suite; six compiled mutants finish
and mismatch. The exhaustive matrices and executed-site coverage are distinct
measurements. The packed helper's byte/marker behavior and the RGB helper's
signed comparisons remain explicit when connecting the `563E` and `56E2` rows.
