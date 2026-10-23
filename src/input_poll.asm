; Connected input module418C..4333; unchanged physical bytes and live state.
; Mode0 tail-jumps to mouse4252; mode1 calls live DS:25A0; others accelerate keys.
; 42A5 is closed to4252/4334/4359 only in the intact-slot domain below.
; Mouse INT33 provider returns full live segments/frame before actual IRET.
; Preserve PUSH/POP saves and actual CALL/RET aliases, signed clamps and wrap.
; Calibrated X uses one more SAR than Y; unchecked scale selector is not fixed.
; Contracts: docs/input-poll.md and docs/architecture.md.
times -(($-$$) != 0x418c) db 0
; V1 D3 constructor gives25A0/1=hi(X),lo(Y),25A6=FF,25A7=04. The actual mode tests choose the non0/non1 keyboard branch;do not infer callback invocation merely from the overlapping target word.
; R3 UNCONDITIONAL branch contract: mode0 observed by418C jumps directly4252,
; bypassing42A5 without reading25A0. This empty per-invocation42A5 domain is not
; pointer immutability:4ABD restores mode0 only, leaving any joystick word.
; Primary mouse configuration is not a write lock on25A6/25A0; indexed/resource,
; saved-frame/provider and IRQ writers require separate lifetime proof.
; PROFILE mouse preservation uses exactly33:AX=0003; no writer/race closure.
PollInputState418C:
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @0418C
    jnz loc_4196 ; @04191
    jmp PollMousePosition ; @04193
loc_4196:
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @04196
    jnz loc_41A0 ; @0419B
    jmp loc_42A1 ; @0419D
loc_41A0:
    mov bx,[InputAccelerationX0016-GameDataImage] ; @041A0
    mov cx,[InputAccelerationY0018-GameDataImage] ; @041A4
    mov ax,[InputKeyMask1FC7-GameDataImage] ; @041A8
    test ax,0xc03 ; @041AB
    jnz loc_41B5 ; @041AE
    mov cx,0x10 ; @041B0
    jmp short loc_41D1 ; @041B3
loc_41B5:
    test ax,0x401 ; @041B5
    jz loc_41C1 ; @041B8
    sub cx,byte +0x1 ; @041BA
    jns loc_41C1 ; @041BD
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @041BF
loc_41C1:
    test ax,0x802 ; @041C1
    jz loc_41D1 ; @041C4
    add cx,byte +0x1 ; @041C6
    cmp cx,byte +0x20 ; @041C9
    jng loc_41D1 ; @041CC
    mov cx,0x20 ; @041CE
loc_41D1:
    test ax,0x300c ; @041D1
    jnz loc_41DB ; @041D4
    mov bx,0x10 ; @041D6
    jmp short loc_41F7 ; @041D9
loc_41DB:
    test ax,0x1004 ; @041DB
    jz loc_41E7 ; @041DE
    sub bx,byte +0x1 ; @041E0
    jns loc_41E7 ; @041E3
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @041E5
loc_41E7:
    test ax,0x2008 ; @041E7
    jz loc_41F7 ; @041EA
    add bx,byte +0x1 ; @041EC
    cmp bx,byte +0x20 ; @041EF
    jng loc_41F7 ; @041F2
    mov bx,0x20 ; @041F4
loc_41F7:
    mov [InputAccelerationX0016-GameDataImage],bx ; @041F7
    mov [InputAccelerationY0018-GameDataImage],cx ; @041FB
    shr bx,1 ; @041FF
    shr cx,1 ; @04201
    shr bx,1 ; @04203
    shr cx,1 ; @04205
    sub bx,byte +0x4 ; @04207
    sub cx,byte +0x4 ; @0420A
    add bx,[0x10] ; @0420D
    cmp bx,byte +0x8 ; @04211
    jg loc_421B ; @04214
    mov bx,0x8 ; @04216
    jmp short loc_4224 ; @04219
loc_421B:
    cmp bx,0x148 ; @0421B
    jng loc_4224 ; @0421F
    mov bx,0x148 ; @04221
loc_4224:
    mov [0x10],bx ; @04224
    add cx,[0x12] ; @04228
    cmp cx,byte +0x8 ; @0422C
    jg loc_4236 ; @0422F
    mov cx,0x8 ; @04231
    jmp short loc_423F ; @04234
loc_4236:
    cmp cx,0xc8 ; @04236
    jng loc_423F ; @0423A
    mov cx,0xc8 ; @0423C
loc_423F:
    mov [0x12],cx ; @0423F
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04243
    test ax,0x4010 ; @04245
    jz loc_424D ; @04248
    or bx,byte +0x1 ; @0424A
loc_424D:
    mov [InputButtonsWord-GameDataImage],bx ; @0424D
PollInputKeyboardReturn4251:
    ret ; @04251
; UNCONDITIONAL local stack: ten PUSH words=20,then INT33 CPU frame6.418C mode0 tail-jumps here;mode1 PUSH DX/CALL42A5 adds4 if live25A0 selects4252. PLATFORM-CONDITIONAL33:AX=0003 preserves declared returned stack/segments only;it has no transient stack-depth bound,mouse callback allocation,or IRQ/alias closure.
PollMousePosition:
    push es ; @04252
    push ds ; @04253
    push bp ; @04254
    push si ; @04255
    push di ; @04256
    push ax ; @04257
    push bx ; @04258
    push cx ; @04259
    push dx ; @0425A
    push ds ; @0425B
    mov ax,0x3 ; @0425C
MousePollInt33:
    int 0x33 ; @0425F
MousePollInt33Return:
    pop ds ; @04261
    cmp byte [MouseButtonSuppression200B-GameDataImage],0xff ; @04262
    jz loc_426D ; @04267
    mov [InputButtonsWord-GameDataImage],bx ; @04269
loc_426D:
    cmp cx,byte +0x8 ; @0426D
    jnl loc_4275 ; @04270
    mov cx,0x8 ; @04272
loc_4275:
    cmp cx,0x148 ; @04275
    jng loc_427E ; @04279
    mov cx,0x148 ; @0427B
loc_427E:
    mov [PointerX-GameDataImage],cx ; @0427E
    cmp dx,byte +0x8 ; @04282
    jnl loc_428A ; @04285
    mov dx,0x8 ; @04287
loc_428A:
    cmp dx,0xc8 ; @0428A
    jng loc_4293 ; @0428E
    mov dx,0xc8 ; @04290
loc_4293:
    mov [PointerY-GameDataImage],dx ; @04293
    pop dx ; @04297
    pop cx ; @04298
    pop bx ; @04299
    pop ax ; @0429A
    pop di ; @0429B
    pop si ; @0429C
    pop bp ; @0429D
    pop ds ; @0429E
    pop es ; @0429F
PollMousePositionReturn42A0:
    ret ; @042A0
; T3 UNCONDITIONAL in the fixed decoded selection/no-other-writer domain: initial (M,P) is
; (0,4252), or (2,4252) after 0F64. Mouse/keyboard/escape retain P; every mode1 publication
; at4A6D/85 first replaces P at4A68/80. Ordinary selection histories call4334/4359 here,
; never initial4252. The broader raw-M1/intact-slot domain still includes4252 and is
; retained. Mode0 observed at418C bypasses this slot. Menu/code/level/session reuse does not
; restore P. Global indexed/resource/renderer/IRQ/frame/provider writers remain UNRESOLVED.
; P is sampled before PUSH DX/CALL; a later memory-only slot change cannot retarget latched
; AX. No mode cancellation recheck occurs. An ordinary foreground selection cannot resume
; inside its own timer poll before IRET; unknown reentry/nesting/aliases remain separate
; obligations, not profile-closed.
; R3 writer refinement: supplied ground0o..ground4o.dat each0420 bytes end1F6A,
; excluding this raw-resource overwrite only; original request remains1000.
; SlotD3 starts259F:30F3 clears259F..25CB,30FB/3100 put X-high/Y-low at25A0/25A1.
; Constructor3134 also sets25A6=FF via record+06=FFF6, so even mode0 persistence
; is not implied by initial selection. Actual survival toD3 remains UNRESOLVED.
; Visibility4131 can reach this word for corrupted origin; nominal DATA-A origin
; 0010..0500 aligned8 excludes it. Stack/segment/provider/IRQ domains remain open.
loc_42A1:
; V2/U02 writer refinement (G.7 classes; full evidence in v2-targets report):
; PROVEN: ordinary complete LEVEL/odd/GROUND outputs stop at17CA/66E5/1F6A;
; the five pinned GROUND files each0420 bytes cannot write2013..201E or25A0..25A6.
; Cache-name padding is not an arbitrary string writer:1E60 count=(k-1)&FFFF
; when a dot follows k<8 basename bytes; k=0 writesFFFF spaces from1F96.
; At1E51 an extension NUL after j<3 bytes gives(j-1)&FFFF; j=0 writesFFFF
; spaces from1F9E. Supplied literal/digit-edited names have k>=4,j=3, excluding
; these two underflows. Cache-enable1F93 and damaged filenames are separate
; concrete inputs;1ED7 has no decoded caller, not a proof of dead code.
; CHARACTERIZED NONDETERMINISM: record B3 owns2013..201E at+14..1F;
; D3 owns25A0..25A6 at+01..07. Apply each actual indexed store to these SAME
; bytes. Completed D3 has P=(X>>8)|((Y&FF)<<8), baselines=(Y>>8)|F800, F6FF,
; and modeFF from3134. It takes keyboard polling, not automatically42A5.
; A later proper joystick selection repairs P before mode1; an IRQ during
; construction may instead see each partially published byte. No atomic record.
; Renderer width0 is a concrete writer, not excluded by nominal nonzero widths:
; A6 at1DB6 leaves type1A width1DDB=0;20E2 can set height1DDC=FF. A following
; GROUND read N<=0290 retains both. LEVEL004 section1 command138(decimal)=24BFFD9A,
; x04BF,y-9,type1A, then admits DX0 through99E2 and selects8D66 (shift7).
; Survival of the spill/earlier commands is a premise, not a new proved edge.
; A complete GROUND reload repairs this example; unchanged pinned terrain has
; no packed-width0 after original clipping. Width0 RCR8DEA visits all DS bytes
; in order BX+1..BX+0000, with SHR8DE5 first; live POPs then read changed saves.
; This first pass can change P, mode, rows and SS saves (SS0 aliases DS:A950).
; Target rule: current AX is the word sampled42A1, including any mixed-byte
; history; only an intervening register/return writer can change it afterwards.
; IRQ4C47 saves AX at interruptedSP-08, keyboard16D4 at interruptedSP-0A;
; corruption of those exact words can change restored AX before42A5. The slot
; write alone cannot. Known-target finite closure still requires last-writer
; ownership; unknown42A5 code, old08/INT62/provider writes remain named seams.
; TARGET/LIFETIME: the second mode read at4196 must equal1; direct entry here
; bypasses both mode tests. With DS=relocated09A9, the stored word is4252;
; 4A65/4A68 installs4334 and4A7D/4A80 installs4359. Menu choice CL1 selects
; the latter, CL2 exits to keyboard mode2, every other CL selects4334.
; Mode1 is published BEFORE calibration and baseline stores; an IRQ may poll
; with old baselines. Escape and mouse/keyboard choices do not reset the word.
; Known-set proof requires that these are the last writes to BOTH slot bytes.
; GROUND1A18 requests DS:1B4B..2B4A: file offsets0A55/0A56 replace25A0/25A1
; at returned lengths>=0A56/>=0A57. Supplied420-byte files stop at1F6A instead.
; Indexed counterexample: creation30F3 at slot211(decimal), SI=259F, clears
; 259F..25CB;30FB/3100 then overlap this word with X-high/Y-low. The byte
; counter/limit equality is not a range guard. This is a raw-entry witness,
; not proof that startup reaches slot211 through earlier overlapping records.
; Also retain1194/1198 unchecked option-marker cursors, decoder/RLE/cache
; ES:DI writers, and arbitrary DS/ES/SS aliases, providers and UNKNOWN paths.
; The startup forward clear0031 ends2011;455B ends0FC9. Neither restores25A0.
; Thus whole-program writer closure remains open; canonical DS and supplied
; GROUND files alone do not establish it. Native unsupported-target status
; is a transport boundary, not an original fallback. See s4 integration report.
; AX samples the word BEFORE PUSH DX/CALL write SS. Aliasing those writes
; with25A0 changes later polls, not this already-latched AX target (assuming
; intact instructions and no intervening IRQ/provider change to registers).
    mov ax,[InputPollCallback-GameDataImage] ; @042A1
    push dx ; @042A4
; S19 input-callback: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Live DS:25A0 supplies target before PUSH DX/CALL. Known mouse/joystick choices do not close
; writers, calibration publication or live segments.
; Profile entries: 33:AX=0003.
; Dependencies: 25A0/DS lifetime; GROUND/request/wrap/alias writers; joystick STI; mode1 before
; complete calibration.
; S17 flow-state: The transfer samples AX from live DS:25A0 before PUSH DX/CALL. The
; analyzer does not recover a global game-DS or slot-lifetime invariant. Known4252 mouse
; service has an undeclared INT33; 4334/4359 retain their actual CLI/STI and returned
; state, not an invented flag-preserving ABI. DS ownership, resource/indexed writers and
; live return/save aliases remain open; target_domain_complete=false.
InputPollCallbackCall42A5:
    call ax ; @042A5
InputPollCallbackReturn42A7:
    pop dx ; @042A7
    cmp dl,0xff ; @042A8
    jnz loc_42B0 ; @042AB
    jmp loc_4333 ; @042AD
loc_42B0:
    sub bx,[InputAxisBaselineX25A2-GameDataImage] ; @042B0
    sub cx,[InputAxisBaselineY25A4-GameDataImage] ; @042B4
    mov al,[InputAxisScaleSelector2005-GameDataImage] ; @042B8
    cmp bx,byte +0x8 ; @042BB
    jg loc_42C5 ; @042BE
    cmp bx,byte -0x8 ; @042C0
    jnl loc_42F8 ; @042C3
loc_42C5:
    cmp al,0x2 ; @042C5
    jz loc_42D3 ; @042C7
    cmp al,0x3 ; @042C9
    jz loc_42D7 ; @042CB
    cmp al,0x4 ; @042CD
    jz loc_42D9 ; @042CF
    sar bx,1 ; @042D1
loc_42D3:
    sar bx,1 ; @042D3
    sar bx,1 ; @042D5
loc_42D7:
    sar bx,1 ; @042D7
loc_42D9:
    sar bx,1 ; @042D9
    sar bx,1 ; @042DB
    add bx,[0x10] ; @042DD
    cmp bx,byte +0x8 ; @042E1
    jg loc_42EB ; @042E4
    mov bx,0x8 ; @042E6
    jmp short loc_42F4 ; @042E9
loc_42EB:
    cmp bx,0x148 ; @042EB
    jng loc_42F4 ; @042EF
    mov bx,0x148 ; @042F1
loc_42F4:
    mov [0x10],bx ; @042F4
loc_42F8:
    cmp cx,byte +0x8 ; @042F8
    jg loc_4302 ; @042FB
    cmp cx,byte -0x8 ; @042FD
    jnl loc_4333 ; @04300
loc_4302:
    cmp al,0x2 ; @04302
    jz loc_4310 ; @04304
    cmp al,0x3 ; @04306
    jz loc_4314 ; @04308
    cmp al,0x4 ; @0430A
    jz loc_4316 ; @0430C
    sar cx,1 ; @0430E
loc_4310:
    sar cx,1 ; @04310
    sar cx,1 ; @04312
loc_4314:
    sar cx,1 ; @04314
loc_4316:
    sar cx,1 ; @04316
    add cx,[0x12] ; @04318
    cmp cx,byte +0x8 ; @0431C
    jg loc_4326 ; @0431F
    mov cx,0x8 ; @04321
    jmp short loc_432F ; @04324
loc_4326:
    cmp cx,0xc8 ; @04326
    jng loc_432F ; @0432A
    mov cx,0xc8 ; @0432C
loc_432F:
    mov [0x12],cx ; @0432F
loc_4333:
InputPollOuterReturn4333:
    ret ; @04333
times -(($-$$) != 0x4334) db 0
