; Palette pointers, byte-port writers and transition front ends, original52D4..563D.
; Native contracts: docs/palette-row-select.md and docs/palette-ports.md.
; Initial table bytes remain UNKNOWN; unchecked selectors and buffer ownership stay open.
; Transition loops and sequential DAC writer548C are not yet translated.
; UNKNOWN: unresolved bytes
PackedPalettePointerTable:
    db 0x38,0x26,0x08,0x26,0x20,0x49,0x13,0x1f,0xe8,0x25,0x0b,0x1f,0xa8,0x25,0x68,0x26 ; @052D4
; UNKNOWN: unresolved bytes
RgbPalettePointerTable:
    db 0x38,0x26,0x08,0x26,0x30,0x49,0x3b,0x1f,0xf0,0x25,0x23,0x1f,0xb8,0x25,0x68,0x26 ; @052E4
sub_52F4:
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @052F4
    jz loc_5309 ; @052F9
    lea si,[PackedPalettePointerTable] ; @052FB
    mov si,[cs:si+0x2] ; @052FF
    mov cx,0x10 ; @05303
    jmp WriteAttributePalette ; @05306
loc_5309:
    lea si,[RgbPalettePointerTable] ; @05309
    mov si,[cs:si+0x2] ; @0530D
    mov cx,0x8 ; @05311
    call sub_548C ; @05314
    mov cx,0x1008 ; @05317
    jmp sub_548C ; @0531A
; UNKNOWN: unresolved bytes
    db 0xc3 ; @0531D
TransitionPaletteToSlot1:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0531E
    mov cx,0x10 ; @05320
    mov bx,0x100 ; @05323
    jmp PaletteTransitionSharedBody ; @05326
sub_5329:
    push dx ; @05329
    mov bx,0x100 ; @0532A
    call SelectAndStepPaletteRow ; @0532D
    mov bl,0x1 ; @05330
    jnz loc_5336 ; @05332
    dec bl ; @05334
loc_5336:
    pop cx ; @05336
    push bx ; @05337
    mov cx,0x10 ; @05338
    mov bx,0x107 ; @0533B
    call SelectAndStepPaletteRow ; @0533E
    mov al,0x1 ; @05341
    jnz loc_5347 ; @05343
    dec al ; @05345
loc_5347:
    pop bx ; @05347
    db 0x0a,0xc3 ; ENCODED: or al,bl (NASM chooses a different encoding) ; @05348
    ret ; @0534A
sub_534B:
    push bx ; @0534B
    push dx ; @0534C
    mov bl,0x0 ; @0534D
    call SelectAndStepPaletteRow ; @0534F
    pop cx ; @05352
    pop bx ; @05353
    mov dl,0x1 ; @05354
    jnz loc_535A ; @05356
    dec dl ; @05358
loc_535A:
    push dx ; @0535A
    db 0x8a,0xfb ; ENCODED: mov bh,bl (NASM chooses a different encoding) ; @0535B
    mov bl,0x7 ; @0535D
    call SelectAndStepPaletteRow ; @0535F
    mov al,0x1 ; @05362
    jnz loc_5368 ; @05364
    dec al ; @05366
loc_5368:
    pop bx ; @05368
    db 0x0a,0xc3 ; ENCODED: or al,bl (NASM chooses a different encoding) ; @05369
    ret ; @0536B
TransitionPaletteToSlot2:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0536C
    mov cx,0x10 ; @0536E
    mov bx,0x200 ; @05371
    jmp PaletteTransitionSharedBody ; @05374
sub_5377:
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @05377
    jz loc_53A1 ; @0537C
    push ds ; @0537E
    pop es ; @0537F
    lea si,[PackedPalettePointerTable] ; @05380
    mov di,[cs:si+0xc] ; @05384
    mov si,[cs:si+0xa] ; @05388
    mov al,[si] ; @0538C
    mov [di+0x7],al ; @0538E
    add di,byte +0x8 ; @05391
    mov cx,0x4 ; @05394
    rep movsw ; @05397
    cmp byte [0x200e],0xff ; @05399
    jnz loc_53C9 ; @0539E
    ret ; @053A0
loc_53A1:
    push ds ; @053A1
    pop es ; @053A2
    lea si,[RgbPalettePointerTable] ; @053A3
    mov di,[cs:si+0xc] ; @053A7
    mov si,[cs:si+0xa] ; @053AB
    mov ax,[si] ; @053AF
    mov [di+0x15],ax ; @053B1
    mov al,[si+0x2] ; @053B4
    mov [di+0x17],al ; @053B7
    add di,byte +0x18 ; @053BA
    mov cx,0xc ; @053BD
    rep movsw ; @053C0
    cmp byte [0x200e],0xff ; @053C2
    jnz loc_53C9 ; @053C7
loc_53C9:
    ret ; @053C9
sub_53CA:
    mov cx,0x808 ; @053CA
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @053CD
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @053CF
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @053D1
    jz loc_53E7 ; @053D6
    lea si,[PackedPalettePointerTable] ; @053D8
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @053DC
    mov si,[cs:si] ; @053DE
    add si,byte +0x8 ; @053E1
    jmp short WriteAttributePalette ; @053E4
; UNKNOWN: unresolved bytes
    db 0x90 ; @053E6
loc_53E7:
    lea si,[RgbPalettePointerTable] ; @053E7
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @053EB
    mov si,[cs:si] ; @053ED
    add si,byte +0x18 ; @053F0
    jmp WriteMappedDacPalette ; @053F3
sub_53F6:
    mov cx,0x8 ; @053F6
    jmp short loc_5401 ; @053F9
; UNKNOWN: unresolved bytes
    db 0x90 ; @053FB
sub_53FC:
    mov al,0x2 ; @053FC
sub_53FE:
    mov cx,0x10 ; @053FE
loc_5401:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05401
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05403
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @05405
    jz loc_5418 ; @0540A
    lea si,[PackedPalettePointerTable] ; @0540C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @05410
    mov si,[cs:si] ; @05412
    jmp short WriteAttributePalette ; @05415
; UNKNOWN: unresolved bytes
    db 0x90 ; @05417
loc_5418:
    lea si,[RgbPalettePointerTable] ; @05418
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0541C
    mov si,[cs:si] ; @0541E
    jmp WriteMappedDacPalette ; @05421
; UNKNOWN: unresolved bytes
    db 0xc3 ; @05424
; 5425: CH first index, CL count (zero ->65536), DS:SI bytes follow DF.
; ADD DL6 retains DH; live savedDX selects final status IN. Unconditional STI.
; Byte ports may mutate canonical data/stack; no hardware timing assumed.
WriteAttributePalette:
    cli ; @05425
    db 0x8a,0xdd ; ENCODED: mov bl,ch (NASM chooses a different encoding) ; @05426
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05428
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @0542A
    add dl,0x6 ; @0542E
    in al,dx ; @05431
    push dx ; @05432
    mov dl,0xc0 ; @05433
loc_5435:
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05435
    out dx,al ; @05437
    lodsb ; @05438
    out dx,al ; @05439
    inc bl ; @0543A
    loop loc_5435 ; @0543C
    pop dx ; @0543E
    in al,dx ; @0543F
    mov dl,0xc0 ; @05440
    mov al,0x20 ; @05442
    out dx,al ; @05444
    sti ; @05445
AttributePaletteReturn5446:
    ret ; @05446
sub_5447:
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @05447
    jz loc_5456 ; @0544C
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x2 ; @0544E
    jz loc_546A ; @05453
    ret ; @05455
loc_5456:
    lea si,[0x2608] ; @05456
    mov cx,0x8 ; @0545A
    call sub_548C ; @0545D
    lea si,[0x2608] ; @05460
    mov cx,0x1008 ; @05464
    jmp short sub_548C ; @05467
; UNKNOWN: unresolved bytes
    db 0x90 ; @05469
loc_546A:
    lea si,[0x2608] ; @0546A
    mov cx,0x10 ; @0546E
    jmp short WriteAttributePalette ; @05471
sub_5473:
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @05473
    jz loc_5485 ; @05478
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x2 ; @0547A
    jnz loc_5484 ; @0547F
    jmp loc_5533 ; @05481
loc_5484:
    ret ; @05484
loc_5485:
    lea si,[0x2668] ; @05485
    mov cx,0x1008 ; @05489
sub_548C:
    cli ; @0548C
    cmp byte [PaletteBlankingControl-GameDataImage],0xff ; @0548D
    jz loc_54A1 ; @05492
    mov dx,0x3c4 ; @05494
    mov al,0x1 ; @05497
    out dx,al ; @05499
    inc dx ; @0549A
    in al,dx ; @0549B
    or al,0x20 ; @0549C
    out dx,al ; @0549E
    push ax ; @0549F
    push dx ; @054A0
loc_54A1:
    mov dx,0x3c8 ; @054A1
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @054A4
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @054A6
    out dx,al ; @054A8
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @054A9
    inc dx ; @054AB
loc_54AC:
    lodsb ; @054AC
    out dx,al ; @054AD
    lodsb ; @054AE
    out dx,al ; @054AF
    lodsb ; @054B0
    out dx,al ; @054B1
    inc ah ; @054B2
    loop loc_54AC ; @054B4
    cmp byte [PaletteBlankingControl-GameDataImage],0xff ; @054B6
    jz loc_54C2 ; @054BB
    pop dx ; @054BD
    pop ax ; @054BE
    and al,0xdf ; @054BF
    out dx,al ; @054C1
loc_54C2:
    sti ; @054C2
    ret ; @054C3
; 54C4: CH unchecked CS5507 byte index, CL count (zero ->65536).
; DS:SI RGB triples follow DF; CS:DI indexes advance forward. PUSH DI precedes CLI.
; Reread live DS200C after output: changed blanking control changes POP sequence.
; Saved DX/AX/DI and outerRET remain live. See docs/palette-ports.md.
WriteMappedDacPalette:
    push di ; @054C4
    cli ; @054C5
    cmp byte [PaletteBlankingControl-GameDataImage],0xff ; @054C6
    jz loc_54DA ; @054CB
    mov dx,0x3c4 ; @054CD
    mov al,0x1 ; @054D0
    out dx,al ; @054D2
    inc dx ; @054D3
    in al,dx ; @054D4
    or al,0x20 ; @054D5
    out dx,al ; @054D7
    push ax ; @054D8
    push dx ; @054D9
loc_54DA:
    mov dx,0x3c8 ; @054DA
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @054DD
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @054DF
    lea di,[MappedDacPaletteIndexes] ; @054E1
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @054E5
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @054E7
loc_54E9:
    mov al,[cs:di] ; @054E9
    inc di ; @054EC
    out dx,al ; @054ED
    inc dx ; @054EE
    lodsb ; @054EF
    out dx,al ; @054F0
    lodsb ; @054F1
    out dx,al ; @054F2
    lodsb ; @054F3
    out dx,al ; @054F4
    dec dx ; @054F5
    loop loc_54E9 ; @054F6
    cmp byte [PaletteBlankingControl-GameDataImage],0xff ; @054F8
    jz loc_5504 ; @054FD
    pop dx ; @054FF
    pop ax ; @05500
    and al,0xdf ; @05501
    out dx,al ; @05503
loc_5504:
    sti ; @05504
    pop di ; @05505
MappedDacPaletteReturn5506:
    ret ; @05506
; UNKNOWN: unresolved bytes
MappedDacPaletteIndexes:
    db 0x00,0x01,0x02,0x03,0x04,0x05,0x14,0x07,0x38,0x39,0x3a,0x3b,0x3c,0x3d,0x3e,0x3f ; @05507
; UNKNOWN: unresolved bytes
    db 0xbb,0x11,0x03,0x8b,0x16,0xda,0x1f,0x80,0xc2,0x06,0xec,0x52,0xb2,0xc0,0x8a,0xc3 ; @05517
; UNKNOWN: unresolved bytes
    db 0xee,0x8a,0xc7,0xee,0x5a,0xec,0xb2,0xc0,0xb0,0x20,0xee,0xc3 ; @05527
loc_5533:
    lea si,[0x2668] ; @05533
    mov cx,0x808 ; @05537
    jmp WriteAttributePalette ; @0553A
sub_553D:
    mov ax,[PaletteDisplayModeWord-GameDataImage] ; @0553D
    cmp ax,0x4 ; @05540
    jz loc_554B ; @05543
    cmp ax,0x2 ; @05545
    jz loc_555F ; @05548
    ret ; @0554A
loc_554B:
    lea si,[0x2638] ; @0554B
    mov cx,0x8 ; @0554F
    call sub_548C ; @05552
    lea si,[0x2650] ; @05555
    mov cx,0x1008 ; @05559
    jmp sub_548C ; @0555C
loc_555F:
    lea si,[0x2638] ; @0555F
    mov cx,0x10 ; @05563
    jmp WriteAttributePalette ; @05566
; 5569: full DS modeword==4 selects RGB, all other words select packed.
; Actual PUSH DS/POP ES precedes independent unchecked BL/BH CS pointer reads.
; Tail jump inherits row RET/status/markers, without adding a CALL frame.
; The77-byte prefix excludes UNKNOWN55B6. See docs/palette-row-select.md.
SelectAndStepPaletteRow:
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @05569
    jz loc_5593 ; @0556E
    push ds ; @05570
    pop es ; @05571
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05572
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05574
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05576
    lea si,[PackedPalettePointerTable] ; @05578
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0557C
    mov si,[cs:si] ; @0557E
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @05581
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05583
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05585
    lea di,[PackedPalettePointerTable] ; @05587
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @0558B
    mov di,[cs:di] ; @0558D
    jmp StepPackedPaletteRow ; @05590
loc_5593:
    push ds ; @05593
    pop es ; @05594
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05595
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05597
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05599
    lea si,[RgbPalettePointerTable] ; @0559B
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0559F
    mov si,[cs:si] ; @055A1
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @055A4
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @055A6
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @055A8
    lea di,[RgbPalettePointerTable] ; @055AA
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @055AE
    mov di,[cs:di] ; @055B0
    jmp StepRgbPaletteRow ; @055B3
; UNKNOWN: unresolved bytes
    db 0xc3 ; @055B6
; Shared transition selects mode once. JZ is tested before status waits;
; waits replace ZF, but each changing branch returns by unconditional JMP.
; Live CX/SI/DI/ES saves and all eight child RET words remain observable.
; Output precedes every step, including the final no-change pass.
PaletteTransitionSharedBody:
    cmp word [PaletteDisplayModeWord-GameDataImage],byte +0x4 ; @055B7
    jz loc_5601 ; @055BC
    push es ; @055BE
    push ds ; @055BF
    pop es ; @055C0
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @055C1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @055C3
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @055C5
    lea si,[PackedPalettePointerTable] ; @055C7
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @055CB
    mov si,[cs:si] ; @055CD
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @055D0
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @055D2
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @055D4
    lea di,[PackedPalettePointerTable] ; @055D6
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @055DA
    mov di,[cs:di] ; @055DC
loc_55DF:
    push cx ; @055DF
    push si ; @055E0
    call WriteAttributePalette ; @055E1
PackedTransitionAfterOutput55E4:
    pop si ; @055E4
    pop cx ; @055E5
    push cx ; @055E6
    push si ; @055E7
    push di ; @055E8
    call StepPackedPaletteRow ; @055E9
PackedTransitionAfterStep55EC:
    jz loc_55FC ; @055EC
    call WaitForDisplayStatusBit3Cycle ; @055EE
PackedTransitionAfterWait1:
    call WaitForDisplayStatusBit3Cycle ; @055F1
PackedTransitionAfterWait2:
    call WaitForDisplayStatusBit3Cycle ; @055F4
PackedTransitionAfterWait3:
    pop di ; @055F7
    pop si ; @055F8
    pop cx ; @055F9
    jmp short loc_55DF ; @055FA
loc_55FC:
    pop di ; @055FC
    pop si ; @055FD
    pop cx ; @055FE
    pop es ; @055FF
PackedPaletteTransitionReturn5600:
    ret ; @05600
loc_5601:
    push es ; @05601
    push ds ; @05602
    pop es ; @05603
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05604
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05606
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05608
    lea si,[RgbPalettePointerTable] ; @0560A
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0560E
    mov si,[cs:si] ; @05610
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @05613
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05615
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05617
    lea di,[RgbPalettePointerTable] ; @05619
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @0561D
    mov di,[cs:di] ; @0561F
loc_5622:
    push cx ; @05622
    push si ; @05623
    call WriteMappedDacPalette ; @05624
RgbTransitionAfterOutput5627:
    pop si ; @05627
    pop cx ; @05628
    push cx ; @05629
    push si ; @0562A
    push di ; @0562B
    call StepRgbPaletteRow ; @0562C
RgbTransitionAfterStep562F:
    jz loc_5639 ; @0562F
    call WaitForDisplayStatusBit3Cycle ; @05631
RgbTransitionAfterWait5634:
    pop di ; @05634
    pop si ; @05635
    pop cx ; @05636
    jmp short loc_5622 ; @05637
loc_5639:
    pop di ; @05639
    pop si ; @0563A
    pop cx ; @0563B
    pop es ; @0563C
RgbPaletteTransitionReturn563D:
    ret ; @0563D
