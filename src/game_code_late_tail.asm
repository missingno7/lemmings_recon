; Maintained image span07C67..08237; mixed ownership remains provisional.
times -(($-$$) != 0x7c67) db 0 ; module start assertion
; TERRAIN: packed AX x/flags, BX signed-y/type; index low6 selects liveGROUNDrecord.
; Preserve live SS savedSI/coordinates, relocated farCALL frame, returnedDS/ES/flags.
; Prefix7C67..7CB4, farcallee8822, livePOPSI7CBA andnearRET7CBB; no hidden state.
DrawPackedTerrainPiece:
    push si ; @07C67
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @07C68
    mov cl,0x7 ; @07C6A
    shr dx,cl ; @07C6C
    and dx,0xc0 ; @07C6E
    or dx,byte +0xf ; @07C72
    test dx,0x40 ; @07C75
    jz loc_7C7F ; @07C79
    or dx,0xf00 ; @07C7B
loc_7C7F:
    rcl ax,1 ; @07C7F
    jnc loc_7C87 ; @07C81
    or dx,0x8000 ; @07C83
loc_7C87:
    shr ax,1 ; @07C87
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @07C89
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @07C8B
    and dx,byte +0x3f ; @07C8D
    sar bx,cl ; @07C90
    sub bx,byte +0x4 ; @07C92
    and ax,0x1fff ; @07C95
    push bx ; @07C98
    push ax ; @07C99
    mov ax,0x8 ; @07C9A
    mul dx ; @07C9D
    add ax,GroundTerrainGraphicsRecords-GameDataImage ; @07C9F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @07CA2
    mov dl,[bx+GroundTerrainRecordWidthByte-GroundTerrainGraphicsRecords] ; @07CA4
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07CA6
    mov cl,[bx+GroundTerrainRecordHeightByte-GroundTerrainGraphicsRecords] ; @07CA8
    mov si,[bx+GroundTerrainRecordSourceOffset-GroundTerrainGraphicsRecords] ; @07CAB
    mov di,[bx+GroundTerrainRecordMaskOffset-GroundTerrainGraphicsRecords] ; @07CAE
    pop ax ; @07CB1
    pop bx ; @07CB2
    mov ch,0x4 ; @07CB3
TerrainPieceBitmapCall:
    call 0x0:0x8822 ; @07CB5
TerrainPieceAfterBitmap:
    pop si ; @07CBA
TerrainPieceReturn:
    ret ; @07CBB
sub_7CBC:
    lea ax,[0x49ce] ; @07CBC
    mov [0x1d],ax ; @07CC0
    mov [0x1f],ax ; @07CC3
    mov word [0x21],0x4 ; @07CC6
    mov word [0x23],0x0 ; @07CCC
    mov es,[0x1ff0] ; @07CD2
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @07CD6
    mov cx,0x23 ; @07CD8
loc_7CDB:
    push cx ; @07CDB
    push ax ; @07CDC
    call sub_7D8D ; @07CDD
    pop ax ; @07CE0
    pop cx ; @07CE1
    inc al ; @07CE2
    loop loc_7CDB ; @07CE4
sub_7CE6:
    mov ax,[0x1ff0] ; @07CE6
    mov [GraphicsResourceSegment-GameDataImage],ax ; @07CE9
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @07CEC
    mov ax,0x30 ; @07CEE
    mov bx,0x14e ; @07CF1
    mov dx,0x230 ; @07CF4
    mov cx,0x410 ; @07CF7
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @07CFA
    call 0x0:0x8822 ; @07CFC
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07D01
    add ax,0x1000 ; @07D04
    mov [GraphicsResourceSegment-GameDataImage],ax ; @07D07
    jmp loc_7E2F ; @07D0A
sub_7D0D:
    call sub_7CE6 ; @07D0D
    mov ax,[0x23] ; @07D10
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07D13
    jz loc_7D1C ; @07D15
    dec word [0x23] ; @07D17
    ret ; @07D1B
loc_7D1C:
    mov es,[0x1ff0] ; @07D1C
    mov ax,[0x21] ; @07D20
    add ax,0x4 ; @07D23
    mov [0x21],ax ; @07D26
    and ax,0xf ; @07D29
    jnz loc_7D54 ; @07D2C
    mov al,0x22 ; @07D2E
    call sub_7D8D ; @07D30
    mov si,[0x1f] ; @07D33
    lodsb ; @07D37
    cmp al,0xff ; @07D38
    jnz loc_7D44 ; @07D3A
    mov word [0x23],0x64 ; @07D3C
    jmp short loc_7D4C ; @07D42
loc_7D44:
    cmp al,0xd ; @07D44
    jnz loc_7D4D ; @07D46
    mov si,[0x1d] ; @07D48
loc_7D4C:
    lodsb ; @07D4C
loc_7D4D:
    mov [0x1f],si ; @07D4D
    call sub_7DB7 ; @07D51
loc_7D54:
    mov di,0x45 ; @07D54
    mov cx,0x4 ; @07D57
loc_7D5A:
    push cx ; @07D5A
    push di ; @07D5B
    mov cx,0x10 ; @07D5C
loc_7D5F:
    push cx ; @07D5F
    push di ; @07D60
    mov cx,0x46 ; @07D61
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @07D64
loc_7D66:
    mov al,[es:di] ; @07D66
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07D69
    shl ax,1 ; @07D6B
    rcl ax,1 ; @07D6D
    rcl ax,1 ; @07D6F
    rcl ax,1 ; @07D71
    db 0x0a,0xc3 ; ENCODED: or al,bl (NASM chooses a different encoding) ; @07D73
    mov [es:di],al ; @07D75
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM chooses a different encoding) ; @07D78
    dec di ; @07D7A
    loop loc_7D66 ; @07D7B
    pop di ; @07D7D
    pop cx ; @07D7E
    add di,byte +0x46 ; @07D7F
    loop loc_7D5F ; @07D82
    pop di ; @07D84
    pop cx ; @07D85
    add di,0x460 ; @07D86
    loop loc_7D5A ; @07D8A
    ret ; @07D8C
sub_7D8D:
    push ds ; @07D8D
    mov si,0x4c10 ; @07D8E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07D91
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07D93
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07D95
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07D97
    add ax,0x1000 ; @07D9A
    mov ds,ax ; @07D9D
    mov cx,0x4 ; @07D9F
loc_7DA2:
    push cx ; @07DA2
    push di ; @07DA3
    mov cx,0x10 ; @07DA4
loc_7DA7:
    movsw ; @07DA7
    add di,byte +0x44 ; @07DA8
    loop loc_7DA7 ; @07DAB
    pop di ; @07DAD
    pop cx ; @07DAE
    add di,0x460 ; @07DAF
    loop loc_7DA2 ; @07DB3
    pop ds ; @07DB5
    ret ; @07DB6
sub_7DB7:
    push ds ; @07DB7
    cmp al,0x20 ; @07DB8
    jz loc_7E2D ; @07DBA
    sub al,0x21 ; @07DBC
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07DBE
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC0
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC2
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC4
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC6
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC8
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @07DCA
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DCC
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07DCE
    add si,0x5bc0 ; @07DD0
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @07DD4
    add bx,byte +0x40 ; @07DD6
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07DD9
    add ax,0x1000 ; @07DDC
    mov ds,ax ; @07DDF
    mov di,0x44 ; @07DE1
    mov cx,0x3 ; @07DE4
loc_7DE7:
    push cx ; @07DE7
    push di ; @07DE8
    push bx ; @07DE9
    mov cx,0x10 ; @07DEA
loc_7DED:
    mov al,[bx] ; @07DED
    not al ; @07DEF
    and al,[es:di] ; @07DF1
    or al,[si] ; @07DF4
    stosb ; @07DF6
    inc si ; @07DF7
    inc bx ; @07DF8
    mov al,[bx] ; @07DF9
    not al ; @07DFB
    and al,[es:di] ; @07DFD
    or al,[si] ; @07E00
    stosb ; @07E02
    inc si ; @07E03
    inc bx ; @07E04
    add di,byte +0x44 ; @07E05
    loop loc_7DED ; @07E08
    pop bx ; @07E0A
    pop di ; @07E0B
    pop cx ; @07E0C
    add di,0x460 ; @07E0D
    loop loc_7DE7 ; @07E11
    mov cx,0x10 ; @07E13
loc_7E16:
    mov al,[bx] ; @07E16
    not al ; @07E18
    and al,[es:di] ; @07E1A
    stosb ; @07E1D
    inc bx ; @07E1E
    mov al,[bx] ; @07E1F
    not al ; @07E21
    and al,[es:di] ; @07E23
    stosb ; @07E26
    inc bx ; @07E27
    add di,byte +0x44 ; @07E28
    loop loc_7E16 ; @07E2B
loc_7E2D:
    pop ds ; @07E2D
    ret ; @07E2E
loc_7E2F:
    mov si,0x1c10 ; @07E2F
    mov ax,[0x21] ; @07E32
    shr ax,1 ; @07E35
    shr ax,1 ; @07E37
    and ax,0xf ; @07E39
    xchg al,ah ; @07E3C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E3E
    shr ax,1 ; @07E40
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E42
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07E44
    call sub_7E65 ; @07E46
    mov si,0x1c10 ; @07E49
    mov ax,[0x21] ; @07E4C
    shr ax,1 ; @07E4F
    shr ax,1 ; @07E51
    and ax,0xf ; @07E53
    xchg al,ah ; @07E56
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E58
    shr ax,1 ; @07E5A
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E5C
    add si,0x1800 ; @07E5E
    mov ax,0x250 ; @07E62
sub_7E65:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @07E65
    mov dx,0x30 ; @07E67
    mov cx,0x410 ; @07E6A
    mov bx,0x14e ; @07E6D
    call 0x0:0x8822 ; @07E70
    ret ; @07E75
; Publish the UI graphics segment once, then two320x104/two-plane calls per row.
; Saved BX,CX,BX remain live: dirty/stack aliases can change rows and loop count.
; Relocated far frames return to7E95/7EAA; preserve all child DS/ES/flag effects.
DrawScreenBackgroundTiles:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07E76
    mov [GraphicsResourceSegment-GameDataImage],ax ; @07E79
    mov cx,0x4 ; @07E7C
BackgroundRowLoop:
    push bx ; @07E7F
    push cx ; @07E80
    push bx ; @07E81
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07E82
    mov bp,0xc ; @07E84
    mov dx,0x140 ; @07E87
    mov cx,0x268 ; @07E8A
    mov si,0x0 ; @07E8D
    call 0x0:0x8822 ; @07E90
BackgroundFirstAfterBitmap:
    mov ax,0x140 ; @07E95
    pop bx ; @07E98
    mov bp,0xc ; @07E99
    mov dx,0x140 ; @07E9C
    mov cx,0x268 ; @07E9F
    mov si,0x0 ; @07EA2
    call 0x0:0x8822 ; @07EA5
BackgroundSecondAfterBitmap:
    pop cx ; @07EAA
    pop bx ; @07EAB
    add bx,byte +0x68 ; @07EAC
    loop BackgroundRowLoop ; @07EAF
BackgroundReturn:
    ret ; @07EB1
sub_7EB2:
    push ds ; @07EB2
    mov di,[DrawingOrigin-GameDataImage] ; @07EB3
    add di,[DrawingPageByteOffset-GameDataImage] ; @07EB7
    add di,0x64f ; @07EBB
    mov si,0x4f22 ; @07EBF
    mov dx,0x3c4 ; @07EC2
    mov ax,0xf02 ; @07EC5
    mov [ss:0x8],ax ; @07EC8
    out dx,ax ; @07ECC
    mov dx,0x3ce ; @07ECD
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07ED0
    mov [ss:0xa],ax ; @07ED2
    out dx,ax ; @07ED6
    mov ax,0x1 ; @07ED7
    mov [ss:0xc],ax ; @07EDA
    out dx,ax ; @07EDE
    mov ax,0x5 ; @07EDF
    mov [ss:0x0],ax ; @07EE2
    out dx,ax ; @07EE6
    mov ax,0x1003 ; @07EE7
    mov [ss:0x2],ax ; @07EEA
    out dx,ax ; @07EEE
    mov ax,0xff08 ; @07EEF
    mov [ss:0xe],ax ; @07EF2
    out dx,ax ; @07EF6
    mov ax,0xa000 ; @07EF7
    mov es,ax ; @07EFA
    mov ds,ax ; @07EFC
    mov cx,0x27 ; @07EFE
loc_7F01:
    push cx ; @07F01
    push si ; @07F02
    push di ; @07F03
    mov cx,0x34 ; @07F04
loc_7F07:
    push cx ; @07F07
    push dx ; @07F08
    mov dx,0x3c4 ; @07F09
    mov ax,0x102 ; @07F0C
    mov [ss:0x8],ax ; @07F0F
    out dx,ax ; @07F13
    pop dx ; @07F14
    mov ax,0x4 ; @07F15
    mov [ss:0x10],ax ; @07F18
    out dx,ax ; @07F1C
    mov ch,[si] ; @07F1D
    mov cl,[si+0x1] ; @07F1F
    mov bh,[si+0x2] ; @07F22
    mov bl,[si+0x3] ; @07F25
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07F28
    rol al,1 ; @07F2A
    rol al,1 ; @07F2C
    and al,0x80 ; @07F2E
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @07F30
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07F32
    ror al,1 ; @07F34
    ror al,1 ; @07F36
    ror al,1 ; @07F38
    and al,0x40 ; @07F3A
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F3C
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07F3E
    and al,0x20 ; @07F40
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F42
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07F44
    rol al,1 ; @07F46
    rol al,1 ; @07F48
    rol al,1 ; @07F4A
    and al,0x10 ; @07F4C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F4E
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07F50
    ror al,1 ; @07F52
    ror al,1 ; @07F54
    and al,0x8 ; @07F56
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F58
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07F5A
    rol al,1 ; @07F5C
    and al,0x4 ; @07F5E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F60
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07F62
    rol al,1 ; @07F64
    rol al,1 ; @07F66
    rol al,1 ; @07F68
    rol al,1 ; @07F6A
    and al,0x2 ; @07F6C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F6E
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07F70
    ror al,1 ; @07F72
    and al,0x1 ; @07F74
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F76
    cli ; @07F78
    mov al,[di] ; @07F79
    mov [di],ah ; @07F7B
    sti ; @07F7D
    push dx ; @07F7E
    mov dx,0x3c4 ; @07F7F
    mov ax,0x202 ; @07F82
    mov [ss:0x8],ax ; @07F85
    out dx,ax ; @07F89
    pop dx ; @07F8A
    mov ax,0x104 ; @07F8B
    mov [ss:0x10],ax ; @07F8E
    out dx,ax ; @07F92
    mov ch,[si] ; @07F93
    mov cl,[si+0x1] ; @07F95
    mov bh,[si+0x2] ; @07F98
    mov bl,[si+0x3] ; @07F9B
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07F9E
    rol al,1 ; @07FA0
    rol al,1 ; @07FA2
    and al,0x80 ; @07FA4
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @07FA6
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07FA8
    ror al,1 ; @07FAA
    ror al,1 ; @07FAC
    ror al,1 ; @07FAE
    and al,0x40 ; @07FB0
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FB2
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07FB4
    and al,0x20 ; @07FB6
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FB8
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07FBA
    rol al,1 ; @07FBC
    rol al,1 ; @07FBE
    rol al,1 ; @07FC0
    and al,0x10 ; @07FC2
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FC4
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07FC6
    ror al,1 ; @07FC8
    ror al,1 ; @07FCA
    and al,0x8 ; @07FCC
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FCE
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07FD0
    rol al,1 ; @07FD2
    and al,0x4 ; @07FD4
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FD6
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07FD8
    rol al,1 ; @07FDA
    rol al,1 ; @07FDC
    rol al,1 ; @07FDE
    rol al,1 ; @07FE0
    and al,0x2 ; @07FE2
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FE4
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07FE6
    ror al,1 ; @07FE8
    and al,0x1 ; @07FEA
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FEC
    cli ; @07FEE
    mov al,[di] ; @07FEF
    mov [di],ah ; @07FF1
    sti ; @07FF3
    push dx ; @07FF4
    mov dx,0x3c4 ; @07FF5
    mov ax,0x402 ; @07FF8
    mov [ss:0x8],ax ; @07FFB
    out dx,ax ; @07FFF
    pop dx ; @08000
    mov ax,0x204 ; @08001
    mov [ss:0x10],ax ; @08004
    out dx,ax ; @08008
    mov ch,[si] ; @08009
    mov cl,[si+0x1] ; @0800B
    mov bh,[si+0x2] ; @0800E
    mov bl,[si+0x3] ; @08011
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @08014
    rol al,1 ; @08016
    rol al,1 ; @08018
    and al,0x80 ; @0801A
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0801C
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0801E
    ror al,1 ; @08020
    ror al,1 ; @08022
    ror al,1 ; @08024
    and al,0x40 ; @08026
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @08028
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0802A
    and al,0x20 ; @0802C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0802E
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @08030
    rol al,1 ; @08032
    rol al,1 ; @08034
    rol al,1 ; @08036
    and al,0x10 ; @08038
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0803A
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @0803C
    ror al,1 ; @0803E
    ror al,1 ; @08040
    and al,0x8 ; @08042
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @08044
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @08046
    rol al,1 ; @08048
    and al,0x4 ; @0804A
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0804C
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @0804E
    rol al,1 ; @08050
    rol al,1 ; @08052
    rol al,1 ; @08054
    rol al,1 ; @08056
    and al,0x2 ; @08058
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0805A
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @0805C
    ror al,1 ; @0805E
    and al,0x1 ; @08060
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @08062
    cli ; @08064
    mov al,[di] ; @08065
    mov [di],ah ; @08067
    sti ; @08069
    push dx ; @0806A
    mov dx,0x3c4 ; @0806B
    mov ax,0x802 ; @0806E
    mov [ss:0x8],ax ; @08071
    out dx,ax ; @08075
    pop dx ; @08076
    mov ax,0x304 ; @08077
    mov [ss:0x10],ax ; @0807A
    out dx,ax ; @0807E
    mov ch,[si] ; @0807F
    mov cl,[si+0x1] ; @08081
    mov bh,[si+0x2] ; @08084
    mov bl,[si+0x3] ; @08087
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0808A
    rol al,1 ; @0808C
    rol al,1 ; @0808E
    and al,0x80 ; @08090
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @08092
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @08094
    ror al,1 ; @08096
    ror al,1 ; @08098
    ror al,1 ; @0809A
    and al,0x40 ; @0809C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0809E
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @080A0
    and al,0x20 ; @080A2
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080A4
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @080A6
    rol al,1 ; @080A8
    rol al,1 ; @080AA
    rol al,1 ; @080AC
    and al,0x10 ; @080AE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080B0
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @080B2
    ror al,1 ; @080B4
    ror al,1 ; @080B6
    and al,0x8 ; @080B8
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080BA
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @080BC
    rol al,1 ; @080BE
    and al,0x4 ; @080C0
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080C2
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @080C4
    rol al,1 ; @080C6
    rol al,1 ; @080C8
    rol al,1 ; @080CA
    rol al,1 ; @080CC
    and al,0x2 ; @080CE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080D0
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @080D2
    ror al,1 ; @080D4
    and al,0x1 ; @080D6
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080D8
    cli ; @080DA
    mov al,[di] ; @080DB
    mov [di],ah ; @080DD
    sti ; @080DF
    inc di ; @080E0
    add si,byte +0x4 ; @080E1
    pop cx ; @080E4
    dec cx ; @080E5
    jz loc_80EB ; @080E6
    jmp loc_7F07 ; @080E8
loc_80EB:
    pop di ; @080EB
    pop si ; @080EC
    add di,byte +0x50 ; @080ED
    add si,0x340 ; @080F0
    pop cx ; @080F4
    dec cx ; @080F5
    jz loc_80FB ; @080F6
    jmp loc_7F01 ; @080F8
loc_80FB:
    pop ds ; @080FB
    ret ; @080FC
sub_80FD:
    mov dx,0x3c4 ; @080FD
    mov ax,0xf02 ; @08100
    mov [ss:0x8],ax ; @08103
    out dx,ax ; @08107
    mov dx,0x3ce ; @08108
    mov ax,0x105 ; @0810B
    mov [ss:0x0],ax ; @0810E
    out dx,ax ; @08112
    push ss ; @08113
    pop es ; @08114
    mov di,[DrawingDirtyCellMapOffset-GameDataImage] ; @08115
    mov al,[es:di] ; @08119
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0811C
    jz loc_8123 ; @0811E
    jmp short loc_819D ; @08120
; UNKNOWN: unresolved bytes
    db 0x90 ; @08122
loc_8123:
    push ds ; @08123
    inc di ; @08124
    mov bp,[DrawingOrigin-GameDataImage] ; @08125
    add bp,0x2c2 ; @08129
    mov si,0x4a40 ; @0812D
    mov ax,[0x2] ; @08130
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @08133
    mov dx,0xa000 ; @08135
    mov ds,dx ; @08138
    mov al,0x1 ; @0813A
    mov cx,0x14 ; @0813C
loc_813F:
    push cx ; @0813F
    mov cx,0x28 ; @08140
loc_8143:
    repne scasb ; @08143
    jz loc_8160 ; @08145
loc_8147:
    pop cx ; @08147
    add bp,0x160 ; @08148
    add si,0x680 ; @0814C
    loop loc_813F ; @08150
    pop ds ; @08152
    mov di,[DrawingDirtyCellMapOffset-GameDataImage] ; @08153
    inc di ; @08157
    mov cx,0x320 ; @08158
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0815B
    rep stosb ; @0815D
    ret ; @0815F
loc_8160:
    push cx ; @08160
    repe scasb ; @08161
    pop bx ; @08163
    inc bx ; @08164
    push cx ; @08165
    push di ; @08166
    push si ; @08167
    push bp ; @08168
    push ax ; @08169
    push es ; @0816A
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @0816B
    mov ax,0x28 ; @0816D
    db 0x2b,0xc3 ; ENCODED: sub ax,bx (NASM chooses a different encoding) ; @08170
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @08172
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @08174
    db 0x2b,0xd9 ; ENCODED: sub bx,cx (NASM chooses a different encoding) ; @08176
    db 0x8b,0xcb ; ENCODED: mov cx,bx (NASM chooses a different encoding) ; @08178
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @0817A
    add dx,byte -0x2c ; @0817C
    add bx,0xff30 ; @0817F
    push ds ; @08183
    pop es ; @08184
    mov al,0x8 ; @08185
loc_8187:
    push cx ; @08187
    rep movsb ; @08188
    pop cx ; @0818A
    db 0x2b,0xf3 ; ENCODED: sub si,bx (NASM chooses a different encoding) ; @0818B
    db 0x2b,0xfa ; ENCODED: sub di,dx (NASM chooses a different encoding) ; @0818D
    dec al ; @0818F
    jnz loc_8187 ; @08191
    pop es ; @08193
    pop ax ; @08194
    pop bp ; @08195
    pop si ; @08196
    pop di ; @08197
    pop cx ; @08198
    jcxz loc_8147 ; @08199
    jmp short loc_8143 ; @0819B
loc_819D:
    mov byte [es:di],0x0 ; @0819D
    mov bp,ds ; @081A1
    mov di,[DrawingOrigin-GameDataImage] ; @081A3
    add di,0x2c2 ; @081A7
    mov si,0x4a40 ; @081AB
    mov ax,[0x2] ; @081AE
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @081B1
    mov dx,0xa000 ; @081B3
    mov es,dx ; @081B6
    mov ds,dx ; @081B8
    mov dx,0xa0 ; @081BA
loc_81BD:
    mov cx,0x2c ; @081BD
    rep movsb ; @081C0
    add si,0xa4 ; @081C2
    dec dx ; @081C6
    jnz loc_81BD ; @081C7
    mov ds,bp ; @081C9
    ret ; @081CB
sub_81CC:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @081CC
    mov word [AlternateDrawingOrigin-GameDataImage],0x2520 ; @081D2
    mov word [DrawingPageByteOffset-GameDataImage],0x2c0 ; @081D8
    mov word [DrawingDirtyCellMapOffset-GameDataImage],0x42b2 ; @081DE
    mov word [AlternateDrawingDirtyCellMapOffset-GameDataImage],0x45d3 ; @081E4
    mov bx,[DrawingDirtyCellMapOffset-GameDataImage] ; @081EA
    mov byte [ss:bx],0xff ; @081EE
    mov bx,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @081F2
    mov byte [ss:bx],0xff ; @081F6
    mov byte [DrawingDirtyCellsEnabledByte-GameDataImage],0xff ; @081FA
    call sub_80FD ; @081FF
    mov ax,[AlternateDrawingOrigin-GameDataImage] ; @08202
    xchg [DrawingOrigin-GameDataImage],ax ; @08205
    mov [AlternateDrawingOrigin-GameDataImage],ax ; @08209
    mov ax,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @0820C
    xchg [DrawingDirtyCellMapOffset-GameDataImage],ax ; @0820F
    mov [AlternateDrawingDirtyCellMapOffset-GameDataImage],ax ; @08213
    call InitializeStatusDisplay ; @08216
    call sub_80FD ; @08219
    mov ax,0x160 ; @0821C
    mov bx,0xa0 ; @0821F
    mov dx,[DrawingOrigin-GameDataImage] ; @08222
    call 0x0:SetDrawingLayout ; @08226
    mov word [0x8],0xd2c0 ; @0822B
    mov word [0xa],0xd2f0 ; @08231
    ret ; @08237
