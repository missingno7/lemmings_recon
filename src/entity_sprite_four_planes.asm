; Maintained sprite callbacks 6CFC..6E82; physical order unchanged.

times -(($-$$) != 0x6cfc) db 0 ; module start assertion
; CONTRACT: four planes, fourteen nominal rows, source DS=incoming CX.
; CL shift is unchecked; each row PUSHes/POPs live AX count. Masked first pass
; uses BP spills; OR passes map02/04/08 with actual DI restores/saves.
; DF strings, literal +29h pitch, physical word-high wrap, SS aliases,
; defined FLAGS and ordered VGA phases include final live POP DS/RET.
DrawEntityShiftedSprite4Plane14:
    push ds ; @06CFC
    mov ds,cx ; @06CFD
    xchg dx,cx ; @06CFF
    mov dx,0x3c4 ; @06D01
    mov ax,0xf02 ; @06D04
    mov [ss:0x8],ax ; @06D07
    out dx,ax ; @06D0B
    mov dx,0x3ce ; @06D0C
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06D0F
    mov [ss:0xa],ax ; @06D11
    out dx,ax ; @06D15
    mov ax,0xe01 ; @06D16
    mov [ss:0xc],ax ; @06D19
    out dx,ax ; @06D1D
    mov ax,0x5 ; @06D1E
    mov [ss:0x0],ax ; @06D21
    out dx,ax ; @06D25
    mov ax,0x3 ; @06D26
    mov [ss:0x2],ax ; @06D29
    out dx,ax ; @06D2D
    mov ax,0xa000 ; @06D2E
    mov es,ax ; @06D31
    push di ; @06D33
    mov ax,0xe ; @06D34
loc_6D37:
    push ax ; @06D37
    lodsw ; @06D38
    push si ; @06D39
    xchg al,ah ; @06D3A
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06D3C
    mov ax,[bx] ; @06D3E
    add bx,byte +0x2 ; @06D40
    xchg al,ah ; @06D43
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06D45
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06D47
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06D49
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06D4B
    jz loc_6D5B ; @06D4D
loc_6D4F:
    shr si,1 ; @06D4F
    rcr al,1 ; @06D51
    shr bp,1 ; @06D53
    rcr ah,1 ; @06D55
    dec ch ; @06D57
    jnz loc_6D4F ; @06D59
loc_6D5B:
    push bx ; @06D5B
    push cx ; @06D5C
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06D5D
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @06D5F
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06D61
    mov al,0x8 ; @06D63
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06D65
    mov [ss:0xe],ax ; @06D67
    out dx,ax ; @06D6B
    cli ; @06D6C
    mov al,[es:di] ; @06D6D
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06D70
    stosb ; @06D72
    sti ; @06D73
    mov al,0x8 ; @06D74
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06D76
    mov [ss:0xe],ax ; @06D78
    out dx,ax ; @06D7C
    cli ; @06D7D
    mov al,[es:di] ; @06D7E
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @06D81
    stosb ; @06D83
    sti ; @06D84
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06D85
    mov al,0x8 ; @06D87
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06D89
    mov [ss:0xe],ax ; @06D8B
    out dx,ax ; @06D8F
    cli ; @06D90
    mov al,[es:di] ; @06D91
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06D94
    stosb ; @06D96
    sti ; @06D97
    add di,byte +0x29 ; @06D98
    pop cx ; @06D9B
    pop bx ; @06D9C
    pop si ; @06D9D
    pop ax ; @06D9E
    dec ax ; @06D9F
    jnz loc_6D37 ; @06DA0
    pop di ; @06DA2
    push di ; @06DA3
    mov ax,0x1 ; @06DA4
    mov [ss:0xc],ax ; @06DA7
    out dx,ax ; @06DAB
    mov ax,0x1003 ; @06DAC
    mov [ss:0x2],ax ; @06DAF
    out dx,ax ; @06DB3
    mov ax,0xff08 ; @06DB4
    mov [ss:0xe],ax ; @06DB7
    out dx,ax ; @06DBB
    mov dl,0xc4 ; @06DBC
    mov ax,0x202 ; @06DBE
    mov [ss:0x8],ax ; @06DC1
    out dx,ax ; @06DC5
    mov ax,0xe ; @06DC6
loc_6DC9:
    push ax ; @06DC9
    lodsw ; @06DCA
    xchg al,ah ; @06DCB
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06DCD
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06DCF
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06DD1
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06DD3
    jz loc_6DDF ; @06DD5
loc_6DD7:
    shr bx,1 ; @06DD7
    rcr al,1 ; @06DD9
    dec ch ; @06DDB
    jnz loc_6DD7 ; @06DDD
loc_6DDF:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06DDF
    cli ; @06DE1
    mov al,[es:di] ; @06DE2
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06DE5
    stosb ; @06DE7
    mov al,[es:di] ; @06DE8
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06DEB
    stosb ; @06DED
    mov al,[es:di] ; @06DEE
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06DF1
    stosb ; @06DF3
    sti ; @06DF4
    add di,byte +0x29 ; @06DF5
    pop ax ; @06DF8
    dec ax ; @06DF9
    jnz loc_6DC9 ; @06DFA
    pop di ; @06DFC
    push di ; @06DFD
    mov dx,0x3c4 ; @06DFE
    mov ax,0x402 ; @06E01
    mov [ss:0x8],ax ; @06E04
    out dx,ax ; @06E08
    mov ax,0xe ; @06E09
loc_6E0C:
    push ax ; @06E0C
    lodsw ; @06E0D
    xchg al,ah ; @06E0E
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06E10
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06E12
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06E14
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06E16
    jz loc_6E22 ; @06E18
loc_6E1A:
    shr bx,1 ; @06E1A
    rcr al,1 ; @06E1C
    dec ch ; @06E1E
    jnz loc_6E1A ; @06E20
loc_6E22:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06E22
    cli ; @06E24
    mov al,[es:di] ; @06E25
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06E28
    stosb ; @06E2A
    mov al,[es:di] ; @06E2B
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06E2E
    stosb ; @06E30
    mov al,[es:di] ; @06E31
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06E34
    stosb ; @06E36
    sti ; @06E37
    add di,byte +0x29 ; @06E38
    pop ax ; @06E3B
    dec ax ; @06E3C
    jnz loc_6E0C ; @06E3D
    pop di ; @06E3F
    mov dx,0x3c4 ; @06E40
    mov ax,0x802 ; @06E43
    mov [ss:0x8],ax ; @06E46
    out dx,ax ; @06E4A
    mov ax,0xe ; @06E4B
loc_6E4E:
    push ax ; @06E4E
    lodsw ; @06E4F
    xchg al,ah ; @06E50
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06E52
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06E54
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06E56
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06E58
    jz loc_6E64 ; @06E5A
loc_6E5C:
    shr bx,1 ; @06E5C
    rcr al,1 ; @06E5E
    dec ch ; @06E60
    jnz loc_6E5C ; @06E62
loc_6E64:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06E64
    cli ; @06E66
    mov al,[es:di] ; @06E67
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06E6A
    stosb ; @06E6C
    mov al,[es:di] ; @06E6D
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06E70
    stosb ; @06E72
    mov al,[es:di] ; @06E73
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06E76
    stosb ; @06E78
    sti ; @06E79
    add di,byte +0x29 ; @06E7A
    pop ax ; @06E7D
    dec ax ; @06E7E
    jnz loc_6E4E ; @06E7F
    pop ds ; @06E81
EntitySprite4Plane14Return:
    ret ; @06E82
times -(($-$$) != 0x6e83) db 0 ; module end assertion
