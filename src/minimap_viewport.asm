; Maintained7A5A..7BB7 viewport outline; exact physical span, no UNKNOWN bytes.
times -(($-$$) != 0x7a5a) db 0 ; module start assertion
; CONTRACT: first live DS:0000 read owns destination, later read owns phase.
; The phase is saved on live SS; POP AX controls the second shift via AND AX/DEC AL.
; Nonzero AH with AL=0 executes256 shifts. No phase normalization follows POP.
; VGA mirrors precede OUT; latch reads precede every DF-sensitive STOSB.
; IF is cleared only around each read/write pair and set afterward; ES=A000.
; Normal DF0 geometry is24 pixels by20 rows. See docs/minimap-viewport.md.
DrawMinimapViewport:
    mov di,[LevelViewOriginPixels-GameDataImage] ; @07A5A
    shr di,1 ; @07A5E
    shr di,1 ; @07A60
    shr di,1 ; @07A62
    shr di,1 ; @07A64
    shr di,1 ; @07A66
    shr di,1 ; @07A68
    shr di,1 ; @07A6A
    add di,0x2172 ; @07A6C
    add di,[DrawingOrigin-GameDataImage] ; @07A70
    add di,byte +0x2 ; @07A74
    mov dx,0xa000 ; @07A77
    mov es,dx ; @07A7A
    mov dx,0x3c4 ; @07A7C
    mov ax,0xf02 ; @07A7F
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @07A82
    out dx,ax ; @07A86
    mov dx,0x3ce ; @07A87
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07A8A
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @07A8C
    out dx,ax ; @07A90
    mov ax,0xc01 ; @07A91
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @07A94
    out dx,ax ; @07A98
    mov ax,0x5 ; @07A99
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @07A9C
    out dx,ax ; @07AA0
    mov ax,0x3 ; @07AA1
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @07AA4
    out dx,ax ; @07AA8
    mov cx,0xffff ; @07AA9
    mov bx,0xff00 ; @07AAC
    mov ax,[LevelViewOriginPixels-GameDataImage] ; @07AAF
    shr ax,1 ; @07AB2
    shr ax,1 ; @07AB4
    shr ax,1 ; @07AB6
    shr ax,1 ; @07AB8
    and ax,0x7 ; @07ABA
    push ax ; @07ABD
    jz loc_7AC8 ; @07ABE
loc_7AC0:
    shr cx,1 ; @07AC0
    rcr bx,1 ; @07AC2
    dec al ; @07AC4
    jnz loc_7AC0 ; @07AC6
loc_7AC8:
    mov al,0x8 ; @07AC8
    db 0x8a,0xe5 ; ENCODED: mov ah,ch (NASM chooses a different encoding) ; @07ACA
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07ACC
    out dx,ax ; @07AD0
    cli ; @07AD1
    mov al,[es:di] ; @07AD2
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07AD5
    stosb ; @07AD7
    sti ; @07AD8
    mov al,0x8 ; @07AD9
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07ADB
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07ADD
    out dx,ax ; @07AE1
    cli ; @07AE2
    mov ah,[es:di] ; @07AE3
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07AE6
    stosb ; @07AE8
    sti ; @07AE9
    mov al,0x8 ; @07AEA
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @07AEC
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07AEE
    out dx,ax ; @07AF2
    cli ; @07AF3
    mov ah,[es:di] ; @07AF4
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07AF7
    stosb ; @07AF9
    sti ; @07AFA
    mov al,0x8 ; @07AFB
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @07AFD
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07AFF
    out dx,ax ; @07B03
    cli ; @07B04
    mov ah,[es:di] ; @07B05
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07B08
    stosb ; @07B0A
    sti ; @07B0B
    add di,0x340 ; @07B0C
    mov al,0x8 ; @07B10
    db 0x8a,0xe5 ; ENCODED: mov ah,ch (NASM chooses a different encoding) ; @07B12
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B14
    out dx,ax ; @07B18
    cli ; @07B19
    mov al,[es:di] ; @07B1A
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07B1D
    stosb ; @07B1F
    sti ; @07B20
    mov al,0x8 ; @07B21
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07B23
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B25
    out dx,ax ; @07B29
    cli ; @07B2A
    mov ah,[es:di] ; @07B2B
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07B2E
    stosb ; @07B30
    sti ; @07B31
    mov al,0x8 ; @07B32
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @07B34
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B36
    out dx,ax ; @07B3A
    cli ; @07B3B
    mov ah,[es:di] ; @07B3C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07B3F
    stosb ; @07B41
    sti ; @07B42
    mov al,0x8 ; @07B43
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @07B45
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B47
    out dx,ax ; @07B4B
    cli ; @07B4C
    mov ah,[es:di] ; @07B4D
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07B50
    stosb ; @07B52
    sti ; @07B53
    sub di,byte +0x30 ; @07B54
    mov cx,0x8000 ; @07B57
    mov bx,0x100 ; @07B5A
    pop ax ; @07B5D
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07B5E
    jz loc_7B6A ; @07B60
loc_7B62:
    shr cx,1 ; @07B62
    rcr bx,1 ; @07B64
    dec al ; @07B66
    jnz loc_7B62 ; @07B68
loc_7B6A:
    mov bp,0x12 ; @07B6A
loc_7B6D:
    mov al,0x8 ; @07B6D
    db 0x8a,0xe5 ; ENCODED: mov ah,ch (NASM chooses a different encoding) ; @07B6F
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B71
    out dx,ax ; @07B75
    cli ; @07B76
    mov al,[es:di] ; @07B77
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07B7A
    stosb ; @07B7C
    sti ; @07B7D
    mov al,0x8 ; @07B7E
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07B80
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B82
    out dx,ax ; @07B86
    cli ; @07B87
    mov al,[es:di] ; @07B88
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07B8B
    stosb ; @07B8D
    sti ; @07B8E
    mov al,0x8 ; @07B8F
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @07B91
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07B93
    out dx,ax ; @07B97
    cli ; @07B98
    mov al,[es:di] ; @07B99
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07B9C
    stosb ; @07B9E
    sti ; @07B9F
    mov al,0x8 ; @07BA0
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @07BA2
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07BA4
    out dx,ax ; @07BA8
    cli ; @07BA9
    mov al,[es:di] ; @07BAA
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07BAD
    stosb ; @07BAF
    sti ; @07BB0
    sub di,byte +0x30 ; @07BB1
    dec bp ; @07BB4
    jnz loc_7B6D ; @07BB5
MinimapViewportReturn:
    ret ; @07BB7
times -(($-$$) != 0x7bb8) db 0 ; module end assertion
