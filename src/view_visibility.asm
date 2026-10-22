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
; S17 flow-state: Entry410F retains incoming DF and SS through both4119 and4131 and sets
; ES from incoming DS. 4119 has AX0,CX0068,DI0EA8: DF0 clears0EA8..0F77; DF1
; clears0DDA..0EA9. The following29-byte fill4131 also retains DF. Timer-local service
; changes to DF can affect this body before outer saved FLAGS are restored; an intact
; outer IRET does not export that change to foreground FLAGS. Global DF and writer
; closure remain open.
; CALLBACK FOOTPRINT: DF0 zero0EA8..0F77 and marker01 from0EA6+(unsigned(origin)>>3) cannot touch nominal entity prefix0088..0E97, but index50+14=0EAC overlaps. DF1 clear0DDA..0EA9 zeros callback words of slots4C..4F; following29h marker cannot reach4C..4E (remain0000), and4F becomes0101 for origin>>3=0/1,0100 for2,0000 for>=3. Nominal header50 does not protect against DF1 or4013 publication race. These are RAM values, not asserted executable targets.
; With stable ES=DS and AX=0,104 STOSW write0EA8..0F77 for DF=0 or0DDA..0EA9 for DF=1. The backward range includes record indices4C..4F callbacks (0DF8/0E25/0E52/0E7F); forward range includes index50 callback0EAC if that unchecked slot exists. No CLD here.4131 writes29 bytes from0EA8+(unsigned(view_origin)>>3)-2 following DF, with16-bit cursor wrap. Do not infer record noninterference from a visibility-only name.
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
