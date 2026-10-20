# Reconstruction status

Current static inventory, reproducible with `tools/coverage.py --inventory`.
This command does not run or renew behavioral campaigns.
Retained identity evidence checks the image and the report's recorded inputs;
it does not independently certify toolchain freshness or manifest completeness.

| Evidence dimension | Current result |
|---|---|
| Main binary identity | retained exact-image evidence (82,906 main bytes; recorded input hashes match) |
| Canonical main image | 82,906 bytes; SHA256 `b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e` |
| Classified main bytes | 45,768; classification is not semantic closure |
| Decoded main instructions | 15,417 sites / 35,826 bytes |
| UNKNOWN main bytes | 37,138 in 115 runs; 2,032 bytes inside provisional code frame |
| Static control-flow frontier | 7 transfers; known target sets remain conditional |
| Main C implementation union | 33,510 original instruction bytes in explicit ledger ranges; not fresh aggregate acceptance |
| Semantic readiness | Scoped qualitative gate and subsystem matrix in [semantic audit](semantic-audit.md); no numeric semantic-completion claim |
| Differential coverage | Per-suite scope and matching consumed hashes required; aggregate not evaluated by this inventory |
| Whole-game integration | Not established by routine or byte totals; native startup/frame/platform completion remains open |

Loaded executable sound images have separate ledgers and incomplete decoded
inventories; their C columns likewise describe implementation ranges only:

| Component | Image bytes | Classified bytes | Decoded code bytes | C code union | Open transfers |
|---|---:|---:|---:|---:|---:|
| adlib | 22,125 | 1,438 | 1,329 | 57 | 1 |
| tandysnd | 21,702 | 1,890 | 1,802 | 49 | 1 |
| pcspeaker | 758 | 596 | 211 | 211 | 1 |

Their exact byte identities and distinct code/data/CFG obligations are described in
[executable.md](executable.md) and [sound-drivers.md](sound-drivers.md).

`tools/coverage.py` without `--inventory` retains the strict full-contract and
native-report checks. Only a successful complete acceptance run may publish its
aggregate totals. Old reports remain historical for their recorded inputs;
neither a preserved file nor a comment/name change renews their hashes. Current
priorities live only in [next-work.md](next-work.md); prior checkpoint narratives
are retained in [convergence-history.md](convergence-history.md).
