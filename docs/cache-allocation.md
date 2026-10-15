# DAT cache allocation

`src/resources.asm` names the 66-byte routine at `CS:1ED7..1F18`
`AllocateDatCache`; the symbol ledger records 25 instruction sites. Its pinned
bytes are checked against the unpacked executable identity
`b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e` and a
literal interval in the contract test. The ledger names `DS:1F8E` as
`DatCacheRequestedParagraphs`. These static classifications do not establish
that the routine is reachable; the known startup call reaches the separate
`DisableDatCache` stub at `1ED1`.

The routine sets `AH=48h`, `BX=FFFFh`, and invokes `INT 21h`. The provider's
returned `BX` is compared unsigned with `0C80h`; the first carry flag is ignored.
`MOV AH,48h` preserves the incoming `AL`. When the returned `BX` is below the
threshold, the routine clears only `DS:1F93`, clears `AL` while retaining the
returned `AH`, and returns with the remaining cache fields stale.

At or above the threshold, the routine stores the first returned `BX` at
`DS:1F8E` and `DS:1F90`, then makes another `AH=48h` request with that `BX` and
the previous return's `AL`. It publishes the second returned `AX` at
`DS:1F80`, `1F84`, `1F88`, and `1F8C`; clears words at `1F82`, `1F86`, and
`1F8A`; clears bytes at `1F92` and `1F94`; and writes `FFh` to `1F93`. Both
carry results are ignored, so a second result of `AX=0008h` is still published
and enables the cache.

There is no internal call frame. Each path's actual near `RET` reads the live
word at `SS:SP` after the stores. Aliases where `DS=SS` can therefore alter the
return target; `SP` advances by two modulo 16 bits, and the high byte is read
from physical address plus one with 20-bit wrap.

`tests/cache_allocation_contract.py` checks this routine in the original image
with a constructed `INT 21h/AH=48h` provider and an independent logical model.
It covers returned `BX` values `0000h`, `0C7Fh`, `0C80h`, and `FFFFh`; both carry
values; both input DF/IF states; second results `AX=0008h` and successful
values; and three relocated load segments. Additional cases alias selected
large-path stores (`1F80`, `1F82`, `1F8E`, `1F92`, `1F93`, `1F94`) and the
small-path enable byte with the live return word, wrap `SP` at `FFFFh`, and
cross the physical 20-bit boundary with `SS=FFFFh:SP=000Fh`. The matrix has 267
cases: 51 below-threshold and 216 allocation-path executions.

For each case, the provider records incoming `AX`, `BX`, and flags, returns
explicit `AX`, `BX`, and flags, and preserves all other registers without
memory side effects. The model checks all registers, defined flags, the actual
return target, provider-call order, and the complete 1 MiB RAM image. Each
execution is limited to 100 instructions. The script's coordinator uses
`run_bounded` with a 60-second timeout, 256 MiB per-process limit, and the
helper's 512 MiB whole-job commit limit. Its report is written to
`build/cache-allocation-contract-original.json` without a memory dump and
records the input hashes, cases, decoded/executed sites, branches, and provider
calls. This is original-only evidence: it adds no C coverage, performs no byte
reclassification, and proves no reachability.

The bounded gate passes267 cases:51 below-threshold and216 allocation-path
executions across the three loads. All25 sites and both branch outcomes execute.
The full verifier runs this gate separately before accepting its final report.
The explicit static seed removes66 formerly UNKNOWN bytes; global reachability
remains unresolved.

The native core in `c/cache_allocation.c` now implements this leaf directly with
logical AX-value, paragraph-count and flag outputs. It creates no synthetic call
frame and leaves its actual near return to the boundary adapter. The optional
raster bus owns all data stores and return reads; the NULL bus operates directly
on the same canonical RAM. Word stores issue the low byte before the physical
successor. The core preserves the original CMP flags before the second provider
and all defined flags at subsequent accesses. A missing provider stops before
the first INT at1EDC after the two MOVs, consuming no return word.

`tests/cache_allocation.py` passes282 adapter and282 auxiliary core comparisons:
the267 original-contract cases, three VGA cases, three provider-memory-effect
cases, three first-result probes and six missing-provider stops. There are273
NULL-bus adapter comparisons;
they repeat the applicable RAM cases rather than adding original-byte coverage.
The VGA cases separate read plane2 from write plane0, including a live VGA return
word. Provider effects can change a return or a field initialized before the
second request; those writes remain live. All25 original sites and both branch
edges execute. The provider seam preserves registers other than AX/BX/flags;
instructions remain intact, TF is clear and interrupts are quiescent.
The first-result probes also return AX0000/0008/FFFF, checking partial AH writes
before the second request and the retained high byte on the low path.

Four compiled mutants complete and disagree: testing the first carry result,
replacing the second failure result, clearing the whole AX on the low path, and
returning an entry-time stack word after the stores changed it. Guard exhaustion,
provider errors, crashes and timeouts fail the gate without mutant credit. The
parent owns a temporary DLL directory until the120-second worker is terminal;
the worker has384 MiB process/640 MiB tree commit limits, each compiler has60
seconds/256 MiB, each original execution has100 instructions, callback traces
have128 events, and each native provider trace has at most two calls. Reports
hash their dependency closure before compilation and after all comparisons.
This verifies a declared callable domain, not a new startup path or a full game.
