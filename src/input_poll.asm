; Connected input module418C..4333; unchanged physical bytes and live state.
; Mode0 tail-jumps to mouse4252; mode1 calls live DS:25A0; others accelerate keys.
; Callback target domain is incomplete: known4252/4334/4359, no invented bounds.
; Mouse INT33 provider returns full live segments/frame before actual IRET.
; Preserve PUSH/POP saves and actual CALL/RET aliases, signed clamps and wrap.
; Calibrated X uses one more SAR than Y; unchecked scale selector is not fixed.
; Contracts: docs/input-poll.md and docs/architecture.md.
times -(($-$$) != 0x418c) db 0
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
loc_42A1:
    mov ax,[InputPollCallback-GameDataImage] ; @042A1
    push dx ; @042A4
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
