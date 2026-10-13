# C translation contract

Start from maintained, byte-verified ASM and name the exact routine address range.
Use portable C11, original byte/word/segment addressing and explicit modulo behavior.
The DOS memory backing store is authoritative; no shadow globals or guessed structs.
Generate offsets with tools/symtab.py. Semantic names require instruction evidence.
Use direct C functions with explicit inputs/outputs; register carriers belong only
to the oracle boundary. Preserve shared tails, stale registers, flags, segment side
effects, original bugs, overlapping records and code modifications.

Run the smallest original routine in Unicorn from constructed state. Include real
static data, branch fixtures, boundary/wrap values and seeded poison. Compare memory,
register contracts and defined flags. Name every ignored undefined flag/scratch byte
and justify it. Test budgets must fail loudly. Mutation tests must compile and execute
deliberately faulty implementations and show a genuine oracle mismatch.

Report exact addresses/bytes, routines translated, cases, branches/instructions
executed, quirks, unresolved dependencies, files changed and regression results.
TESTED is behavioral evidence within the declared domain, not whole-program closure.
Use statuses TESTED, PARTIALLY_TESTED, IMPLEMENTED_UNTESTED, INLINE, PLATFORM_REPLACED,
ALTERNATIVE_HARDWARE, ERROR_PATH, PROVEN_DEAD, UNRESOLVED, UNTRANSLATED. Never exempt
an alternative hardware or error path from the program inventory.
