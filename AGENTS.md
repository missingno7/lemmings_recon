# Reconstruction rules

Target only the pinned DOS VGA Lemmings executable and its executable dependencies.
Read docs/executable.md and docs/next-work.md before changing the oracle.
Priority: static identity, readable exact ASM, complete code/data/CFG accounting,
then portable C11 and bounded differential tests; SDL3 comes last.
Never boot the game for discovery. Bounded execution of the unpacker or identified
routines with constructed state is permitted for independent verification.
Do not modify assets or neighboring projects; never commit assets, binary images,
runtime dumps, or downloaded tool binaries. Do not import the legacy interpreter.
Keep UNKNOWN bytes explicitly unresolved. No INCBIN in reconstructed ASM. Encoding
exceptions must explain the instruction; no masking unexplained differences.
The symbol ledger owns names and offsets. Preserve original wrap, flags, segment
effects, self modification, shared tails and bugs. No shadow game-state copies.
Run tools/verify.py and relevant tests after changes. Coverage of bytes, translated
code and executed instructions are separate. Never claim unresolved code is dead.
Only delegate independent C clusters after static boundaries are reliable. Workers
must report addresses, bytes, cases, branches, quirks, dependencies and regressions.
