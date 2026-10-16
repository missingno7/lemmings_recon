; Maintained 410F..414E leaf.
times -(($-$$) != 0x410f) db 0 ; module start assertion
; CONTRACT: shared JMP/fallthrough/CALL target adds no frame of its own.
; PUSH DS/POP ES and both DF-sensitive REP stores remain live. No map extent
; is inferred. The143E operand is relocated separately from liveSS; DS0026/28
; select marker offsets in that frame. Restore actual prior ES via AX, then STI.
RebuildViewVisibilityMap:
    push ds ; @0410F
    pop es ; @04110
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04111
    mov di,ViewVisibilityMapBase-GameDataImage ; @04113
    mov cx,0x68 ; @04116
    rep stosw ; @04119
    mov di,[LevelViewOriginPixels-GameDataImage] ; @0411B
    shr di,1 ; @0411F
    shr di,1 ; @04121
    shr di,1 ; @04123
    dec di ; @04125
    dec di ; @04126
    add di,ViewVisibilityMapBase-GameDataImage ; @04127
    mov cx,0x29 ; @0412B
    mov ax,0x101 ; @0412E
    rep stosb ; @04131
    cli ; @04133
    mov ax,es ; @04134
ViewVisibilityStackSegmentOperand equ $+1 ; relocated immediate in MOV CX
    mov cx,0x143e ; @04136
    mov es,cx ; @04139
    mov bx,[DrawingDirtyCellMapOffset-GameDataImage] ; @0413B
    mov byte [es:bx],0xff ; @0413F
    mov bx,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @04143
    mov byte [es:bx],0xff ; @04147
    mov es,ax ; @0414B
    sti ; @0414D
ViewVisibilityReturn:
    ret ; @0414E
times -(($-$$) != 0x414f) db 0 ; module end assertion
