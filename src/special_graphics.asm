; Maintained image span 08238..08342; reconstruction module, not a historical linker claim.
BlitSpecialResourceStrip0:
    mov ax,[LevelGraphicsSegment-GameDataImage] ; @08238
    mov [GraphicsResourceSegment-GameDataImage],ax ; @0823B
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @0823E
    jmp short loc_8252 ; @08240
; S14 U093: [08242,08243) stored bytes remain UNKNOWN.
; Neighbours: P 08240 jmp 0x8252; N 08243 mov bx, 0x28.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @08242
BlitSpecialResourceStrip1:
    mov bx,0x28 ; @08243
    jmp short loc_8252 ; @08246
; S14 U094: [08248,08249) stored bytes remain UNKNOWN.
; Neighbours: P 08246 jmp 0x8252; N 08249 mov bx, 0x50.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @08248
BlitSpecialResourceStrip2:
    mov bx,0x50 ; @08249
    jmp short loc_8252 ; @0824C
; S14 U095: [0824E,0824F) stored bytes remain UNKNOWN.
; Neighbours: P 0824C jmp 0x8252; N 0824F mov bx, 0x78.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @0824E
BlitSpecialResourceStrip3:
    mov bx,0x78 ; @0824F
loc_8252:
    mov di,0xb840 ; @08252
    mov si,0x8000 ; @08255
    mov es,[LevelGraphicsSegment-GameDataImage] ; @08258
    mov cx,0x960 ; @0825C
loc_825F:
    mov ax,[es:si] ; @0825F
    or ax,[es:si+0x12c0] ; @08262
    or ax,[es:si+0x2580] ; @08267
    stosw ; @0826C
    add si,byte +0x2 ; @0826D
    loop loc_825F ; @08270
    mov ax,0xd0 ; @08272
    mul bx ; @08275
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @08277
    add di,0x4a40 ; @08279
    add di,byte +0x28 ; @0827D
    mov si,0x8000 ; @08280
    push ds ; @08283
    mov ds,[LevelGraphicsSegment-GameDataImage] ; @08284
    mov ax,0xa000 ; @08288
    mov es,ax ; @0828B
    mov dx,0x3c4 ; @0828D
    mov ax,0xf02 ; @08290
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @08293
    out dx,ax ; @08297
    mov dx,0x3ce ; @08298
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0829B
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @0829D
    out dx,ax ; @082A1
    mov ax,0xe01 ; @082A2
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @082A5
    out dx,ax ; @082A9
    mov ax,0x5 ; @082AA
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @082AD
    out dx,ax ; @082B1
    mov ax,0x3 ; @082B2
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @082B5
    out dx,ax ; @082B9
    mov ax,0xff08 ; @082BA
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @082BD
    out dx,ax ; @082C1
    mov cx,0x2878 ; @082C2
    push di ; @082C5
    push cx ; @082C6
loc_82C7:
    push cx ; @082C7
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @082C8
    cli ; @082CA
loc_82CB:
    mov al,[es:di] ; @082CB
    movsb ; @082CE
    loop loc_82CB ; @082CF
    sti ; @082D1
    add di,byte +0x58 ; @082D2
    pop cx ; @082D5
    dec ch ; @082D6
    jz loc_82DC ; @082D8
    jmp short loc_82C7 ; @082DA
loc_82DC:
    pop cx ; @082DC
    pop di ; @082DD
    mov ax,0x1 ; @082DE
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @082E1
    out dx,ax ; @082E5
    mov dl,0xc4 ; @082E6
    mov ax,0x202 ; @082E8
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @082EB
    out dx,ax ; @082EF
    push di ; @082F0
    push cx ; @082F1
loc_82F2:
    push cx ; @082F2
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @082F3
    cli ; @082F5
loc_82F6:
    mov al,[es:di] ; @082F6
    movsb ; @082F9
    loop loc_82F6 ; @082FA
    sti ; @082FC
    add di,byte +0x58 ; @082FD
    pop cx ; @08300
    dec ch ; @08301
    jnz loc_82F2 ; @08303
    pop cx ; @08305
    pop di ; @08306
    mov ax,0x402 ; @08307
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @0830A
    out dx,ax ; @0830E
    push di ; @0830F
    push cx ; @08310
loc_8311:
    push cx ; @08311
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @08312
    cli ; @08314
loc_8315:
    mov al,[es:di] ; @08315
    movsb ; @08318
    loop loc_8315 ; @08319
    sti ; @0831B
    add di,byte +0x58 ; @0831C
    pop cx ; @0831F
    dec ch ; @08320
    jnz loc_8311 ; @08322
    pop cx ; @08324
    pop di ; @08325
    mov ax,0x802 ; @08326
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @08329
    out dx,ax ; @0832D
loc_832E:
    push cx ; @0832E
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0832F
    cli ; @08331
loc_8332:
    mov al,[es:di] ; @08332
    movsb ; @08335
    loop loc_8332 ; @08336
    sti ; @08338
    add di,byte +0x58 ; @08339
    pop cx ; @0833C
    dec ch ; @0833D
    jnz loc_832E ; @0833F
    pop ds ; @08341
    ret ; @08342
