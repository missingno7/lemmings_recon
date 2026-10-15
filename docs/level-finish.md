# Level initialization clear and minimap tail

The C tail covers20 original bytes/nine sites at3776..3789. It calls36AD,
whose JMP4DF8 introduces no extra frame. The clear RET consumes3779. CX starts
at13, but each iteration pushes it, calls796F, pops the actual SS word and
decrements that live value with16-bit LOOP semantics. The child returns live
DS/ES/SP/flags; the final word read/publish uses that returned DS. OwnRET3789
is left to the adapter, and changed child returns stop before their targets.

Constructed tests cover thirteen-column cycles, DF, signed column boundaries,
stack/physical wrap, graphics-word and outer-RET aliases, clear-return changes,
and CS scratch aliases that rebuild a saved counter and returned DS. Native
callbacks hard-exit on finite trace exhaustion/provider errors. Timeouts and
resource/oracle failures never detect a mutant. Its separate bounded gate passes
22 adapter and22 auxiliary core-boundary comparisons, covering133 integrated
sites and17 branch edges, with four completed mutant mismatches. Acceptance
requires the current input hashes in build/level-finish-differential.json.

The CS-scratch counter fixture uses SS=CS/SP=83C3 and samples the first scratch
word as0001, so the actual POP/LOOP finishes after one column. The returned-DS
fixture uses SP=83C7 and scratch bytes00 60 80 37 01 00 00 ED: POP DS supplies
6000, the child RET supplies3780, POP CX supplies1 and ownRET suppliesED00.
The final graphics word must therefore come from live6000:1FF0, not entry DS.
An additional variant makes that child RET target3789 instead: it must stop
before the caller's own RET, leaving the outer savedCX on the stack. Matching
the normal boundary address does not make this a normal return.
Graphics-input and publication/outer-RET aliases remain live too.

At SS=FFFF/SP=0011, the clear's SS:000E mirror changes its straddling CALL
return to37FF. At SP=000F, SS:000C and000E change the clear return to080F.
These fixtures stop before minimap execution; they do not claim that the outer
RET was reached. The original trace independently observes both return bytes.

Mutants force13 host iterations, cache entryDS for the final read, ignore only
the changed clear return, or reverse CALL byte order. The changed-clear witness
uses a VGA stack that then yields a finite changed inner minimap return. An
earlier broad ignore-return mutant exhausted its guard and was rejected without
mutation credit. Production loops remain unchecked and preserve16-bit wrap.

Full36B6 initialization has its separate connected gate in level-initialize.md.
Complete terrain-stream acceptance and wider device/IRQ ownership remain open.
