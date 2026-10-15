# Observable four-call object state

The optional-bus candidate composes the four calls at `376A..3775`, stopping at
`3776` or before a changed near-return target. It uses one canonical memory and
the existing graphics, steel-cell, object-cell and coordinate logical bus cores.
CALL and RET bytes use physical-successor word addressing with 20-bit wrap;
stack offsets wrap at16 bits. All actual return words remain live. This span
does not consume the outer initializer's return word.

`tests/object_state_bus.py` compares the original instructions with both the
logical core and register adapter, including full RAM, registers, defined flags,
ordered byte accesses and VGA state. Historical RAM cases also compare the
previous API. Fixtures include all80 pinned LEVEL/GROUND pairs, changed child
returns, VGA source/stack and stack/physical wrap. Four caller mutations are
required to finish with mismatches; budget or provider failures fail verification.

The original observer retains the independently identified pre-REP flags during
`37B4` and `37B6..37B8`: Unicorn can clear AF at repeated MOVSB hooks although
REP and POP preserve it. Differences beyond that specific AF artifact fail.
All other event masks track architecturally defined flags through each instruction.

The bounded gate passes105 existing RAM cases and eight added bus fixtures,
each through the logical core and adapter, plus four completed mutant mismatches.
A plane-preserving stack fixture supplies ES=6000 and a changed return5000
despite intervening PUSH/CALL writes, proving the second child is never invoked.
A second variant changes the first return to3776: IP alone matches the normal
end, but only the first CALL has run and the core must still report changed-return.
Its12 bytes overlap
the existing RAM span; auxiliary core probes add no physical byte or site coverage.
The complete36B6 initializer, thirteen live minimap calls, full terrain-stream
acceptance, native device ownership and IRQ contracts remain open.
