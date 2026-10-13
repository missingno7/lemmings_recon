# Protected disk-check stream

All addresses are main CS offsets in hex. The canonical 82,906-byte image and
relocation acceptance target are unchanged. The execution-state views are maintained
in src/protection/stream.asm and int1.asm, with their own symbol ledger and CFG.

## Original mechanism

063E saves DS/ES/CX/SI/DI/BP and the first ten IVT words. CALL-next at 0656 supplies
0659; the code adds 075A and installs 0DB3 as INT3. SI receives CS and DS receives SS
before the INT3 at 066C. The original INT3 handler installs INT1 at 0DFF and negates
all 59 bytes through 0E39 on every invocation. It XORs the high saved flag byte with
03, toggling both TF and IF. Entry with TF clear therefore enables single stepping
and exposes the plaintext INT1 handler; entry with TF set reverses both changes.

For a code word at offset p, the transformation is:

```
key(p) = ROL16(NOT16(word(segment, (p - 2) mod 65536)), 1)
word(segment, p) ^= key(p)
```

The handler reads the current memory word, including any overlapping patch. The
static view uses the original stored words only after the previous word has been
restored. This distinction matters for one-byte instructions: at 066D, the runtime
patch exposes bytes 50 E9. After PUSH AX, the handler restores that word and exposes
E8 00 00 at 066E. The stitched view therefore contains 50 E8 00 00. It is a readable
instruction inventory rather than a memory image that exists during execution.

INT1 first restores the previous patched word through the far pointer kept in
IVT vector 0. XCHG leaves the displaced plaintext word in AX. A plaintext AL=CC
skips the next-word patch. Otherwise it loads the interrupted CS:IP from the stack,
patches the next word and updates vector 0. The INT3 disable path has a different
guard: it checks the candidate restored ciphertext AL before conditionally swapping
the word. Both behaviors are preserved and independently checked.

## Recovered control flow

Recursive state-specific discovery finds 372 stream instruction sites occupying
854 bytes: 325 with TF on and 47 with TF off. The INT1 plaintext has 29 instructions
occupying all 59 bytes. Fifteen stream entry candidates are direct-call targets or
the explicit protected entry. They include shared tails and CALL-next constructs.

| Transition | Following state and operation |
|---|---|
| Protected 096F INT3 | TF off at 0970; restore saved IVT and registers, jump to 0E3A |
| Protected 0D9E INT3 | TF off at 0D9F; INT13; raw 0DA1 INT3 resumes protected 0DA2 RET |
| Protected 0DA3 INT3 | TF off at 0DA4; INT25; discard extra flags word; raw 0DA9 INT3 resumes protected 0DAA RET |
| Protected 0DAB INT3 | TF off at 0DAC; INT26; discard extra flags word; raw 0DB1 INT3 resumes protected 0DB2 RET |

0E3A..0E65 checks three AX/BX result pairs and returns CF. The full view preserves
all branch alternatives. Its direct targets close within the view, but BIOS/DOS
returns remain explicit platform contracts. Static branch alternatives do not prove
that every alternative is reachable under the caller's actual input domain.

The sector-buffer pointer originates from 0671+031B=098C. Paragraph alignment and
the low-12-bit segment comparison select either 098C..0B8B or 0B9C..0D9B, two
512-byte buffers. The second avoids a physical 64 KiB DMA boundary. 08CB fills 256
words through this pointer; disk services use it and 094A clears it. Runtime data
use is recorded as overlays. The initial stored bytes still remain UNKNOWN; this
finding does not settle possible alternate code interpretations.

## Independent checks and remaining work

tests/protection.py enters only original INT3 or the transformed INT1 handler with
constructed interrupt frames. Execution is restricted to those identified handler
ranges and stops before the interrupted instruction. Nineteen cases cover TF
enable/disable, both CC guards, overlapping words, branch/call/return destinations,
different old/new segments, rotate carry, offset wrap, stack wrap and varied flags.
An additional 325 cases check the instruction bytes exposed at every derived
TF-on point. All cases compare the full 1 MiB memory, every modeled register and
defined flags, including stack residue. They execute 61 handler instruction sites.
The disk-check body and the BIOS/DOS services have not been executed by these checks.

The transformation contains no relocation sites and gives the same static CFG at
loads 1010, 1213 and 2345. tools/protection.py assembles both maintained views,
checks their complete bytes and named offsets, and checks the pinned derivation
and CFG. tools/verify.py includes these checks and bounded handler verification.
Derived view bytes do not increase the canonical reconstructed-byte total. No
protected routine has been translated to C yet.

Use `tools/where.py ProtectedDiskEntry --state tf_on --disasm 8` or
`tools/where.py ProtectionInt1Handler --state int1_plaintext --disasm 8` to inspect
the state-specific source through its canonical ledger names.

Still open: recover incoming disk-check contracts, prove scratch and stack alias
domains, model all disk-service register/flag/vector effects, and investigate the
skipped five-byte regions 084D..0851 and 087E..0882. The raw-image barriers at 066C
and 0E1C now have explicit state-specific continuations; their canonical bytes must
continue to be decoded through the appropriate transformation. Further C clusters
must preserve original code mutation and vector/stack side effects in shared memory.
