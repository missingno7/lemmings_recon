# Selected resources and fatal tails

The 197D selector now exposes a logical execution result with twelve CPU fields,
a continuation and a status. READY stops before the normal VGAGR RET at 1A59 or
the special VGASPEC RET at 1A7A. Its register adapter consumes that actual outer
return word. FILE_ERROR and CLEANUP stop at 1949 and 04D0 with the failed child's
live stack intact. CHANGED_RETURN consumes the child's actual near return and
stops before any caller continuation, even when its numerical target is 1949 or
04D0. All eight immediate-child call sites use this rule, including decimal
filename writes that alias the decimal child's return word.
The input carries all twelve fields: incoming DX/DI/ES are still live when the
decimal helper changes its return, even though later normal paths overwrite them.

The full API in c/resource_select_full.c directly composes the selector with
the 1949 printer or 04D0 cleanup logical core. The transfer adds no CALL frame,
performs no stack unwind and never executes an outer RET after a fatal result.
Provider-returned DS/ES/SS/SP, general registers, flags and canonical-memory
effects remain live through termination, missing providers or changed returns.
Its adapter reads the four relocated DAT operands and the separate 194B error
printer data-segment operand. A logical caller supplies these values explicitly.

This composition uses RAM throughout. The prefix still requires the existing
preserving DOS service contracts, intact internal DAT returns and the explicit
4B1C retry UI seam. It does not claim a general raster-bus interface, native
DOS/BIOS ownership, IRQ delivery or complete gameplay. The historical result
API retains its intact immediate-child return precondition; new connections use
the execution result instead. No UNKNOWN bytes are newly translated.

tests/resource_select_full.py compares execution and full APIs at both logical
core and register-adapter boundaries against identified original instructions.
Fatal tails additionally have an independent Python model checked from the
original handoff state. Full RAM, twelve CPU fields, defined flags, DOS requests,
printed bytes and ports are compared. Native callbacks have hard finite budgets;
the parent owns temporary DLLs and runs a single worker under a 120-second,
384-MiB process and 640-MiB tree commit limit. Budget exhaustion fails the gate
and cannot count as a detected mutant. Fresh report acceptance is required
before this connection contributes execution evidence; aggregate terrain and
full-game obligations remain separate.

The gate retains all ten paired real selections from the legacy 59-case gate.
Its 72 fixtures also cover all eight changed immediate returns, targets equal
to both fatal entry addresses, all original selector error cases, missing
printer/cleanup services and provider-returned stacks/registers. A separate
incoming data frame verifies that 1949 still selects its relocated main frame.
All nine caller branch outcomes are required. Four completed compiled mutants
must be rejected: ignoring a changed child return, unwinding a failed frame,
adding a synthetic error CALL, or dispatching a changed target as a fatal status.
Real cases run one boundary per serial worker; acceptance requires every chunk,
stable source hashes across all workers and the pinned 55-file input inventory.
