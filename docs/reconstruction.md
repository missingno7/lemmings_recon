# Reconstruction status and source conventions

The canonical byte target is tools/unpack.py's static image with metadata/oracle.json
as an immutable acceptance pin. src/program.asm includes code.asm and image_tail.asm.
These are modern organization units, not claims about the original linker modules.
The frame split is provisional. There are no INCBINs or binary includes.

tools/explore.py follows immediate calls/branches, conditional fallthrough and
relocated far calls. Sources: original entry, an explicit INT24 installation,
signature-matched legacy main-image leads, and the manually investigated 8363 region.
It halts linear descent at returns/unconditional transfers, tracks byte ownership,
reports overlapping decodes, and does not assume skipped bytes are padding.

All 264 main-image legacy signatures match the explicitly relocated canonical image
at load 1010. Earlier raw-image mismatches were relocated operands, not permission to
mask bytes. The 17 external signatures remain separate and do not expand the EXE
census. Main-image analysis now has 268 entry candidates, not 268 proven disjoint
functions. Shared tails and seed boundaries can overlap; the ledger records reachable
bytes per entry without summing them into a fictitious program coverage total.

NDISASM provides assembler spelling only for recursively discovered instruction
ranges. A separate NASM probe assembles every spelling at a fixed slot and compares
its original bytes. The 1,558 main-image mismatches are preserved as annotated ENCODED db rows,
usually opposite direction-bit forms of register/register instructions. They are
decoded instructions, not UNKNOWN data. Improving their source notation is open work.
The final whole-image comparison is independent of those probes.

Every image byte belongs to exactly one region in metadata/regions.json. Proven
code-as-data overlays are separate. Startup's explicitly cleared DS:0000..2011 region,
the four callback records at DS:2013, and DS:25A0 callback pointer are classified from
instructions. Initial classification does not prove those ranges never execute.
Other unreadable or zero-filled runs remain UNKNOWN until evidence exists.

metadata/control-frontier.json records current indirect-transfer leads and proof
obligations. Static callbacks are not marked fully resolved until writes, aliases
and incoming contracts have been checked. Sound driver code, code mutation, and
all data/indirect-target closure remain Gate B obligations.

Runtime-state barriers stop descent after INT3 at 066C and prevent raw decoding of
the negated INT1 handler 0DFF..0E39. The explicitly installed plain INT3 handler 0DB3
is decoded independently. This corrects the earlier assumption that ordinary static
fallthrough was valid after 066C; reported decoded instructions are still a partial
inventory, not proof that every opcode executes unmodified.

Sound drivers have independent source, symbol and region inventories under
src/sound and metadata/adlib-*/tandysnd-*. Main-image metrics exclude them; the
completeness report also gives totals across all three byte-exact images.
