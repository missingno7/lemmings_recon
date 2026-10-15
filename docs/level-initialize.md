# Full level-record initialization caller

The C caller at36B6..3789 covers211 decoded bytes/76 caller sites. UNKNOWN374E
remains excluded. The C core directly composes drawing setup, the137-byte header
fallthrough, special or terrain setup, four object-state calls and the finishing
clear/minimap tail. It never creates invented frames around fallthrough spans.

InitialCALL368E pushes36B9, specialCALL1A7B pushes374C. Every actual return word,
returned DS/ES/CS, flag phase and SP remains live. Selector3742 replaces AL only;
AND AL,AL determines the branch. A ready core leaves ownRET3789 for the adapter.
Missing raster services stop before entry effects; missing special services stop
after its actual CALL push. Special file/decode fatal paths and child changed
returns remain explicit. The special child's ordinary-RAM/DOS assumptions and
all renderer/minimap provider, intact-code and quiescent-IRQ seams are inherited.

The bounded test constructs complete entry states, including declared terrain
streams, coordinate counts, steel cells, DF, stack wraps, header values and live
return/DS aliases. It also uses the supplied special-resource payload pairs and
explicit DOS fixtures. These are not gameplay snapshots or full-game coverage.
All80 complete normal terrain streams at both loop entries retain their separate
pending acceptance gate; constructed full-caller tests do not replace it.

Original execution uses only identified instructions. The existing caller oracle
has an optional per-instruction flag phase callback; this suite uses only the
independently probed37B4 REP/37B6..37B8 POP AF preservation policy. Other flag
differences fail. Full canonical RAM, registers, defined flags, ordered bus/ports,
VGA state and DOS traces are compared. Finite guards/provider/oracle failures
never count as mutant detection. Its bounded gate passes36 adapter and36
auxiliary core comparisons, all76 caller sites/1408 integrated sites and211
observed branch edges, with four completed mutant mismatches. The four supplied
VGASPEC/VGAGR payload pairs run through the full caller. The report is separate
from redraw and the complete terrain campaign. Acceptance requires its current
input hashes. Core probes, overlapping child bytes and sites are not added twice.

The mutations invent a header CALL/RET, branch on wholeAX instead of AL, cache
entryDS for object setup after terrain returns a different DS, and ignore the
initial drawing child's changed return. All finish with actual mismatches; no
timeout, memory/access budget failure, crash or provider error earns credit.
