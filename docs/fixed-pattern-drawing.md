# Fixed-pattern drawing frontier

This records the machine contracts for `UpdateFixedWordPattern` and its two
direct children, `CopyFixedPatternVgaSpans` and `DrawFixedWordPattern`. Their
logical C cores and adapters now have focused native acceptance. Names record
the proven copy/draw roles and pointer/offset provenance; the visual meaning of
the source groups remains open. This is scoped machine-contract verification,
not complete game or interrupt acceptance.

## Static boundaries and call graph

Fresh graph views show this direct tree:

```text
caller @00161 or @0183B
  UpdateFixedWordPattern entry @05827
    CALL CopyFixedPatternVgaSpans @05827
    CALL DrawFixedWordPattern @05866
  RET UpdateFixedWordPattern @0587E
```

| Entry | Inclusive bytes | Ledger reachable bytes / sites | Return boundary |
|---|---:|---:|---:|
| `UpdateFixedWordPattern` | `5827..587E` | 88 / 33 | `RET @587E` |
| `CopyFixedPatternVgaSpans` | `715F..71C9` | 107 / 48 | `RET @71C9` |
| `DrawFixedWordPattern` | `7218..75EE` | 983 / 556 | `RET @75EE` |

The ledger records `UpdateFixedWordPattern` callers at `0161` and `183B`, and only `UpdateFixedWordPattern`
as caller of each child. Neither child has outgoing calls. `CopyFixedPatternVgaSpans` is followed
by the unresolved byte span `71CA..7217`; that gap remains `UNKNOWN`. There is
no shared return tail: each entry consumes its own actual near-call return word.
`CopyFixedPatternVgaSpans` has two 16-iteration `LOOP` bodies; `DrawFixedWordPattern` has no row loop or
conditional branch, only two literal 16-row sequences.

## Caller `UpdateFixedWordPattern`

The first instruction is the real `CALL CopyFixedPatternVgaSpans` at `5827`, whose return word
points to `582A`. After that child returns, the caller computes:

```text
a  = (word DS:[0010h] + zero_extend(byte DS:[1FE0h])) & 7
SI = 0090h * a                     ; 144 decimal bytes per shift
if byte DS:[001Ah] == FFh: SI += 480h
BX = SI + 60h
DI = word DS:[000Ch]
```

Only exact equality with `FFh` takes the `ADD SI,480h` at `5854`; all other
values retain the first half. It then executes `PUSH DS @5861`, loads DS from
`GeneratedWordPatternBufferSegment` at DS:`1FEA`, and calls `DrawFixedWordPattern @5866`.
That call's actual return word points to `5869`, where `POP DS` restores the
original DS. The caller swaps the words at DS:`000C`/DS:`000E` and
DS:`0008`/DS:`000A`, then consumes its own actual caller return word at
`RET @587E`.

With the normal generated-buffer layout described in
[`fixed-word-banks.md`](fixed-word-banks.md), the selected slice is 90h bytes:
the consumer reads 30h bytes through SI, 30h through BX=`SI+60h`, then another
30h through SI. The highest normal start is `0870h`; the exclusive end is
`0900h`. This is a byte-use contract only. The branch on DS:`1A` and the other
numeric offsets have no established higher-level meaning here.

The caller's live stack effects are two actual CALL return words and the one
`PUSH DS`/`POP DS` pair. It does not save BP. `CopyFixedPatternVgaSpans` enables interrupts
before the caller's arithmetic; `DrawFixedWordPattern` disables them at entry and enables
them before returning. Thus `UpdateFixedWordPattern` returns with IF set, irrespective of its
entry IF. DF remains live throughout. The child's final flags survive the
caller's post-call MOV/XCHG sequence because those instructions do not change
FLAGS.

## `CopyFixedPatternVgaSpans`: two VRAM string-copy passes

At entry, `MOV BP,DS` at `715F` retains the entry DS value in BP, then `CLI`
executes. The routine writes `0F02h` to sequencer port `3C4h` and `0105h` to
graphics-controller port `3CEh`. These are literal word OUTs: AL selects the
register index and AH supplies its value.

Before changing DS, it reads the first copy's input offsets in this order:

1. `MOV DI,[DS:000Eh] @7170` reads the destination offset.
2. `MOV SI,[DS:000Ah] @7174` reads the source offset.
3. It loads ES with `A000h @717B`, then DS with `A000h @717D`.

With CX=`0010h`, each of the 16 rows performs three consecutive `MOVSB`
instructions followed by `ADD DI,29h` and `LOOP` (`7182..7188`). Each MOVSB
reads DS:SI first, then writes ES:DI. At this point both segments are A000h,
so each source read loads the VGA latches before the corresponding destination
write. The sequencer map mask and GC write-mode setting remain as programmed;
the code does not restore or reprogram them between copies. This preserves
source/destination overlap and any segment or physical-memory alias effects.

After the first pass, `MOV DS,BP @718A` restores the entry data frame before
reading the source offset inputs. The second source is calculated by these
operations, retaining the live SS save around MUL:

```text
DX = zero_extend(byte DS:[1FE0h])
DX = word(DX + word DS:[0010h])       ; wrap to 16 bits
DX = logical_shift_right(DX, 3)
SI = word DS:[0012h]
PUSH DX                           ; @71A0, actual SS word
AX = SI
SI = 002Ch
DX:AX = unsigned_multiply(AX, SI)
SI = AX                           ; low product word
POP DX                            ; @71AA, reread live saved quotient
SI = word(SI + DX)
SI = word(SI + word DS:[AlternateDrawingOrigin])
DS:[000Ch] = SI
```

`AlternateDrawingOrigin` is the existing ledger symbol at DS:`1F78h`. The
addition at `7192` wraps before the three shifts; no seventeenth carry bit is
included. The equation uses the low product word, but MUL also changes DX
and CF/OF before the actual POP DX; its other arithmetic flags are undefined.
The saved quotient remains aliasable SS memory. The later additions into SI also
wrap at 16 bits.

The routine next reads `DI=word DS:[0008h]`, executes `PUSH ES @71B9` and
`POP DS @71BA` (so DS becomes A000h using the live SS stack), and runs a second
16-row body at `71BE..71C4`. Each row again executes three MOVSBs, then
`ADD SI,29h`; SI therefore traverses source rows while DI advances only through
the 48 destination bytes. The second pass also uses source-read/latch-load
before destination-write ordering, with the same VGA register state.

There is no local CLD. For DF=0, each first-pass row advances SI by 3 and DI by
`3+29h=2Ch`; the second-pass row advances SI by 2Ch and DI by 3. For DF=1,
the first-pass SI delta is -3 and its DI delta is `29h-3=26h`; the second-pass
SI delta is 26h and DI delta is -3. The explicit ADD remains positive in either
case. These are cursor effects, not bounds guarantees.

`STI @71C6` forces IF on; `MOV DS,BP @71C7` restores entry DS; `RET @71C9`
consumes the actual return word from the caller's CALL. ES remains A000h, BP
remains entry DS, SS is not changed, and CX reaches zero on the normal 16-row
exit. BP is clobbered rather than preserved. The internal PUSH ES/POP DS pair
uses live SS and writes a stack word; it is not a saved-register frame, and
the PUSH DX/POP DX around MUL is a second live word pair. Aliases among stack,
code, and data remain possible. With intact normal control
flow, the final flags come from the last row's `ADD SI,29h @71C1`; LOOP, STI,
MOV, and RET do not replace them. Other general registers are live/clobbered.

## `DrawFixedWordPattern`: two literal 16-row VGA passes

The routine starts with CLI and writes these register/value pairs in order:

| OUT value | Port | Selected register | Value |
|---:|---:|---|---:|
| `0F02h` | `3C4h` | Sequencer index 2 | `0Fh` |
| `0000h` | `3CEh` | Graphics Controller index 0 | `00h` |
| `0E01h` | `3CEh` | Graphics Controller index 1 | `0Eh` |
| `0005h` | `3CEh` | Graphics Controller index 5 | `00h` |
| `0003h` | `3CEh` | Graphics Controller index 3 | `00h` |

It sets ES=`A000h` and BP=entry DI. The first literal row starts at `7239`;
successive rows are spaced `27h` bytes, with the sixteenth starting at `7482`
and ending at `ADD DI,29h @74A6`. Each row executes the following in order:

1. Read a word at DS:BX into CX and increment BX twice.
2. Write `08h` plus CL to GC index 8; read ES:DI to load latches.
3. LODSW from DS:SI and STOSB the first source byte to ES:DI.
4. Exchange CH/AH; write `08h` plus the saved high mask byte to GC index 8;
   read ES:DI to load latches; STOSB the second LODSW byte from CH.
5. Read one byte at DS:BX into AH, increment BX, write `08h` plus AH to GC
   index 8, then read ES:DI to load latches.
6. LODSB from DS:SI, STOSB the third source byte, and add `29h` to DI.

Thus each row reads three data bytes through SI and three control bytes through
BX. Every first-pass STOSB is preceded by a destination read after the
corresponding GC index-8 write. Across 16 rows, SI and BX each advance 30h for
DF=0; BX advances through explicit INC instructions and is independent of DF.
DI advances 2C0h for DF=0.

At `74A9`, `MOV DI,BP` resets the destination cursor. The second-pass setup is
literal and ordered: write `0001h`, `1003h`, and `FF08h` to port `3CEh`, set
DL=`C4h`, then write `0202h` to port `3C4h`. The second 16-row body begins at
`74BD`, has `13h` bytes per row, and ends at `ADD DI,29h @75EA`. Each row reads
ES:DI to load latches, LODSW/STOSB the first data byte, reads ES:DI again,
STOSB the retained AH byte, reads ES:DI a third time, then LODSB/STOSB the
third data byte and adds `29h` to DI. There are no per-row port writes in this
pass. The final sequence is `STI @75ED; RET @75EE`.

The two SI passes consume 60h total. In the three-group source layout produced
by the generator, the first 30h and last 30h are read through SI; the middle
30h is read through BX=`entry SI+60h`. This identifies which byte groups the
machine reads and how it uses the third group for GC index-8 controls; it does
not name their visual or gameplay meaning.

There is no CLD, PUSH/POP, or child CALL. DS and SS remain unchanged inside the
routine; ES becomes A000h and BP becomes entry DI. With DF=0, BX advances 30h,
SI advances 60h, and final DI is entry DI+2C0h. With DF=1, BX still advances
30h, SI retreats 60h, and each row's three STOSB decrements DI by 3 before
`ADD DI,29h`, for a net +26h per row; DI is reset to BP before the second pass,
so final DI is entry DI+260h. DX ends at 3C4h. The GC index 8 value and
sequencer map mask are left at FFh and 02h respectively; the VGA state is not
restored. IF is set on return regardless of entry IF, DF is preserved, and
normal final flags come from the last `ADD DI,29h` at 75EAh. General registers
are live/clobbered; CX is not restored.

## Data-frame producers and rotating slots

These operands belong to the relocated game-data frame (image segment 09A9),
except while 715F explicitly selects A000 for its string copies. Startup clears
0000..2011 at 002C..0031. The setup call at 048C reaches 81CC, which writes
word [0008]=D2C0 at 822B and word [000A]=D2F0 at 8231. The initial values of
000C/000E come from the startup clear; 715F later writes 000C at 71B1.

| Word slot | Role when 715F begins | Subsequent use |
|---|---|---|
| 0008 | Second-pass destination | Swapped with 000A at 5874..587B |
| 000A | First-pass source | Swapped with 0008 |
| 000C | Replaced with computed second-pass source | Passed as DI to 7218, then swapped with 000E at 586A..5871 |
| 000E | First-pass destination | Swapped with 000C |

This establishes paired rotating VGA offsets, without assigning front/back or
gameplay names. Each read and swap remains relative to the live DS; initialization
does not establish a permanent alias or a valid-range invariant.

Words 0010/0012 carry horizontal/vertical pointer-coordinate inputs. Setup at
03F8/03FE writes 0096/0064, and the startup mouse call uses those constants in
CX/DX with INT33 function 4 at 0475..047E. PollMousePosition selects function 3
at 425C, restores the live saved DS at 4261, clamps CX/DX, then stores them at
427E/4293. Other input paths adjust these words, and entity selection reads them
at 3D10/3D14. These producer/consumer links support pointer-coordinate ownership;
their broader relation to view/world coordinates remains open.

Byte 001A already has the ledger name EntitySelectionPresent. Setup clears it
at 03F3; selection code sets or clears it at 3DAF/3DE8. The exact-FF test at
584D selects the second 480h half of the generated bank. Its visual meaning is
not established by that cross-use. Byte 1FE0 is initially cleared; its only
identified direct reads are 582E and 718C. No direct static writer was found,
so indirect writes and aliases remain open.

Equal numeric offsets in other DS domains are separate state. The protected
setup at 0646/0648 sets DS=0 before the IVT-vector-3 accesses at 0659..0665.
The loaded PC-speaker component also has its own fields at 0008..001A. Neither
set of accesses belongs to these game-data slots.

## Ownership and translation frontier

The generated source is documented in [`fixed-word-banks.md`](fixed-word-banks.md):
the two 96-byte windows `DS:52BC..531B` and `DS:531C..537B` remain `UNKNOWN`,
with the original three groups of 16 words per window. The generated buffer
selector at DS:`1FEA` is named `GeneratedWordPatternBufferSegment`; successful
allocation and the normal 900h-byte output partition are arithmetic/source
facts, not proof of general bounds, lifetime, or non-aliasing. The 5D18..5D65
region remains `UNKNOWN`. The ledger now owns the copy/draw entry names,
PointerX/Y, four FixedPatternVgaOffset slots and the neutral bias-byte name.
No byte classification changes with those names.

Both leaves now retain the actual segments, flags, stack words and memory/device
ordering above. Their APIs in c/fixed_pattern_copy.h and c/fixed_pattern_draw.h
carry thirteen live roles and stop before their actual RETs; adapters consume
the live outer word. The c/fixed_pattern_update.h parent composes both child
cores through real SS frames. READY=0 stops before 587E; CHANGED_CHILD_RETURN=1
preserves the actual target and direct child entry, before any following parent
restore, selector read or pair swap. Only READY consumes the outer RET.

Unresolved ownership includes the semantic meanings of source groups, the
selected bank's visual meaning, byte 1FE0, allocation lifetime and aliases,
and any runtime constraints on DF or the VGA device state. The offset-pair and
pointer-coordinate provenance above does not prove those wider invariants.
No UNKNOWN span is treated as dead or reclassified by this note.

## Focused native acceptance

The three registered suites run under 420-second and 384-MiB process limits,
with bounded callback traces and fail-stop native callbacks. Guard, memory and
timeout failures are never mutation evidence. Both original-only and native
reports match their final consumed-input hashes.

| Suite / entry | New C bytes | Fixtures / boundaries | Executed sites / branch outcomes | Compared bus events | Completed mutants |
|---|---:|---:|---:|---:|---:|
| fixed_pattern_copy / 715F | 107 | 21 / 42 | 48 / 4 | 9,156 | 10 |
| fixed_pattern_draw / 7218 | 983 | 36 / 72 | 556 / 0 | 28,368 | 10 |
| fixed_pattern_update / 5827 | 88 | 43 / 86 | 637 integrated / 6 | 53,900 | 10 |

The parent has 33 own sites and two own branch outcomes. Its 637 sites include
both children, so these domains are unioned rather than added again. This adds
1,178 unique main C bytes, taking the ledger union from 24,039 to 25,217.
The 715F..75EE physical module is now fixed_pattern_drawing.asm, with unchanged
emission order and the 78-byte UNKNOWN71CA..7217 gap retained.

The copy campaign includes 5,376 independent plane-byte checks. Live word
providers are applied after the original PUSH completes; assertions confirm
the provided quotient is read at POP DX and all 48 second-pass reads use the
provided DS=3600. Cases cover DF/IF, coordinate and address wrapping, overlap,
VGA DS/SS and the live outer word.

The literal renderer has 10,560 independent plane-byte checks, including the
second pass's OR operation and explicit setup/pass-boundary/latch ordering.
The native fixed-word producer is separately compared at both boundaries:
2,304 output bytes and 4,608 independent output-byte checks. Its output is
retained as a whole canonical RAM fixture, then supplies both banks' eight
90h-byte slices to 16 consumer cases/32 comparisons. Those repeated boundary
comparisons consume 4,608 source bytes and check 7,680 plane bytes. This is
producer-output fixture coverage, not a complete startup-to-draw runtime path.

The parent covers all eight alignments and selection00/01/FF, live saved DS,
both changed child returns, actual outer RET, coordinate/segment wrapping and
independent pair-swap equations. A real SS=A000 case retains the hardware-induced
changed child return instead of assuming an ordinary stack. Its C children
operate on the parent's same canonical RAM object with flowing returned roles.

Progress prose and the raw ledger do not renew behavioral evidence. The exact
ASM/relocation gate independently pins current names, offsets and bytes; older
unrelated reports remain historical when their input hashes no longer match.
Next read vga-mirror-restore.md for 587F's separate fixed-frame/live-SS contract
and the original initialization overwrite at 0549.
