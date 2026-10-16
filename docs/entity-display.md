# Entity display leaves

These contracts belong to the3634 drawing frontier. They do not establish its
whole record loop,6E83 particle drawing,706F sprite dispatch, IRQ scheduling or
unchecked allocation extents. All state remains in canonical segmented memory.

## Minimap pixel6FE2

The141-byte6FE2..706E leaf takes a live record in DS:DI. Its signed comparison
rejects Y>=B0; the subsequent wrapped Y-20 sign test is separate. In particular,
Y=8000..801F wraps into a nonnegative row and can draw. The low product of
`((Y-20)&FFFF)>>3` and2C supplies SI; DX retains the product's high word until
the later port setup. X is read afterward, shifted right4 and PUSHed, then
shifted right3 again and added to SI. Live DrawingOrigin and2172+2+2C follow.

Five ordered SS mirror/OUT pairs set map mask0F, set/reset02, enable-set/reset0F,
mode0 and rotate0. The actual saved X word is then POPped: its low3 bits select
the live DS PixelBitMasks byte. The bit-mask mirror/OUT follows that read.
CLI surrounds the real ES=A000 pixel read and AH write; STI finishes drawing.
Early exits preserve entry IF and ES. All paths retain DF, actual stack aliases
and the caller's near-RET word. The incoming general roles and all residual
registers are part of the interface, including returned AL from the pixel read.

## Shared visibility producer410F

The64-byte410F..414E body is called directly and also entered through shared
JMP/fallthrough paths. It adds no frame at its entry. PUSH DS/POP ES reads an
actual stack word; providers or device-backed saves can make ES differ from DS.
It clears68h words at ES:0EA8 in original DF order, then rereads
LevelViewOriginPixels through DS. Three logical shifts, two DEC operations and
ADD0EA8 select the start of29h byte stores of01, again following DF. The named
ViewVisibilityMapBase has no implied allocation extent or matrix shape.

After CLI, AX saves the actual ES. MOV CX loads the relocated143E immediate at
4137 and sets ES from it; that operand is an explicit C input independent of
live CS/SS. DS:0026 selects the first FF marker. Only after that write does
DS:0028 select the second marker. Thus the first write may change the second
offset through an alias. ES is restored from AX, STI forces IF, and RET414E
consumes the preexisting caller word only in the adapter.

The original test uses exact loaded images at loads0/1010/2345. Its scoped code
view applies only the pinned relocation records; no instruction bytes are masked.
The static image hash remains the report identity. A logical RET0000 created by
a clear/stack alias is observed at nonzero CS before executing its target.

## Dirty-row consumer5726

The171-byte5726..57D0 leaf reads record words+0 and+4, wraps their sum and adds
160h once if its sign is set. The logical quotient by8 indexes the live byte
at DS:0EA8; only an exact1 enables output. It then subtracts live view origin,
clamps a negative wrapped result to zero, shifts3 and reads DS:0026 twice.
The first read contributes the output start; the second supplies BP=word+321h.
These are SS offsets. AlternateDrawingDirtyCellMapOffset names the separate0028
producer/swap word without converting either offset into a DS pointer.

Record+6, Y+2 and the nonzero byte+20 supply the original wrapped vertical
arithmetic. The negative adjustment loop adds8 until AX is nonnegative; the
8000 boundary takes4096 iterations. Mask0002 at record+8 selects CH5 instead
of3. CL rounding uses its byte, with no normalized height or row count.

The first row and first inner store are unconditional. Each row PUSHes CX/SI,
writes through SS with literal INC SI and DEC CH, then POPs both actual words.
A restored CH0 therefore means256 stores. After restoring SI it adds28h and
checks unsigned SI>=BP; only otherwise does DEC CL determine continuation.
CL0 can wrap and SS output can overwrite saved words or the outer RET. No
matrix clamp, cached saved state or shadow dirty map is equivalent. DS/ES/SS,
DF/IF and all residual roles remain live. The dirty-row gate covers ordinary
RAM and declared providers. VGA-backed SS remains a separate bus domain;
the producer data handoff supplies additional ordinary-RAM evidence.

## Scoped verification

The minimap gate passes40 fixtures at both APIs plus4 null-bus repeats:
141 bytes/all58 sites/all5 jump outcomes,2,096 compared ordered events and
eight completed mutants. It includes live RAM/VGA records, stack and table
aliases, providers, signed/wrapped guards, DF/IF and actual near returns.
The producer gate passes28 fixtures at both APIs:64 bytes/all27 sites/no jump
edges,14,672 events and eight completed mutants. Its exact loaded views and
independent RAM/FLAGS projection check both marker writes and live POP ES.
The dirty gate passes33 fixtures at both APIs:171 bytes/all73 sites/all25 jump
outcomes,7,690 events and seven completed mutants. Its ordinary-RAM projection
checks every stack/dirty write, the4096-step adjustment and the256-store row.

Two separately verified native producer cores feed four accepted/rejected
record handoffs at view origins0/0180, with prepared3654->3657 caller frames.
The two producer plus four consumer comparisons add598 actual bus events;
producer events are counted once per execution. These are data-flow cases,
not execution of the3634 caller. The three new code ranges add376 unique main
C bytes, taking the ledger union from18,595 to18,971 without counting handoffs
or existing mask-table bytes again. Reports are build/entity-minimap-differential.json,
build/view-visibility-differential.json and build/entity-dirty-differential.json.
Only their exact recorded scopes and matching input hashes own acceptance;
this checkpoint does not renew full-campaign or whole-game evidence.
