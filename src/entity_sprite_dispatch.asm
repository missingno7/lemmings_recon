; Maintained 706F..715E entity sprite parent; physical order unchanged.
times -(($-$$) != 0x706f) db 0 ; module start assertion
; CONTRACT: live DS:DI entity record; +00/+04 form wrapped X for visibility,
; +02/+06 form signed-clamped Y. +28 plus optional +29 selects the frame;
; +27==1 suppresses that add, +2A==FF suppresses eight-way alignment scaling.
; Full MUL by +10 yields paragraph/cursor parts; +0C/1FE6 supply source CX,
; +0A supplies SI and +12 supplies BX. These uses do not prove record bounds.
; Visibility miss bypasses both children. Restored AL from +20 gates the strip.
; +14 is PUSHed at 70F0, then reread from live SS at 7159 before CALL AX 715B.
; Real 7155/715D child returns, saved DI and outer RET remain live; the known
; initialized callback slots do not close changed targets or provider aliases.
DrawObjectSprite:
    push di ; @0706F
    mov bx,[di+EntityRecordX-EntityRecordsBase] ; @07070
    add bx,[di+EntityRecordDrawingXBias-EntityRecordsBase] ; @07072
    jns loc_707B ; @07075
    add bx,0x160 ; @07077
loc_707B:
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @0707B
    shr bx,1 ; @0707D
    shr bx,1 ; @0707F
    shr bx,1 ; @07081
    mov si,ViewVisibilityMapBase-GameDataImage ; @07083
    cmp byte [bx+si],0x1 ; @07086
    jz loc_708E ; @07089
    jmp EntitySpriteRestoreDI ; @0708B
loc_708E:
    mov ax,[LevelViewOriginPixels-GameDataImage] ; @0708E
    sub ax,0x10 ; @07091
    db 0x2b,0xd0 ; ENCODED: sub dx,ax (NASM chooses a different encoding) ; @07094
    jns loc_709C ; @07096
    add dx,0x160 ; @07098
loc_709C:
    db 0x8b,0xda ; ENCODED: mov bx,dx (NASM chooses a different encoding) ; @0709C
    and bx,byte +0x7 ; @0709E
    push bx ; @070A1
    mov al,[di+EntityRecordFrameSelector-EntityRecordsBase] ; @070A2
    cmp byte [di+EntityRecordFrameAddGate-EntityRecordsBase],0x1 ; @070A5
    jz loc_70AE ; @070A9
    add al,[di+EntityRecordFrameAddend-EntityRecordsBase] ; @070AB
loc_70AE:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @070AE
    cmp byte [di+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @070B0
    jz loc_70BE ; @070B4
    shl ax,1 ; @070B6
    shl ax,1 ; @070B8
    shl ax,1 ; @070BA
    db 0x03,0xc3 ; ENCODED: add ax,bx (NASM chooses a different encoding) ; @070BC
loc_70BE:
    push dx ; @070BE
    mov cx,[di+EntityRecordSpriteFrameStride-EntityRecordsBase] ; @070BF
    mul cx ; @070C2
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @070C4
    shr dx,1 ; @070C6
    rcr bp,1 ; @070C8
    shr dx,1 ; @070CA
    rcr bp,1 ; @070CC
    shr dx,1 ; @070CE
    rcr bp,1 ; @070D0
    shr dx,1 ; @070D2
    rcr bp,1 ; @070D4
    add bp,[di+EntityRecordSpriteParagraphOffset-EntityRecordsBase] ; @070D6
    and ax,0xf ; @070D9
    pop dx ; @070DC
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @070DD
    add si,[di+EntityRecordSpriteSourceOffset-EntityRecordsBase] ; @070DF
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @070E2
    add bx,[di+EntityRecordSpriteMaskOffset-EntityRecordsBase] ; @070E4
    shr dx,1 ; @070E7
    shr dx,1 ; @070E9
    shr dx,1 ; @070EB
    mov cx,[di+EntityRecordDrawingYBias-EntityRecordsBase] ; @070ED
    push word [di+EntityRecordSpriteCallback-EntityRecordsBase] ; @070F0
    mov al,[di+EntityRecordStripSelector-EntityRecordsBase] ; @070F3
    mov di,[di+EntityRecordY-EntityRecordsBase] ; @070F6
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @070F9
    jns loc_70FF ; @070FB
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @070FD
loc_70FF:
    push ax ; @070FF
    push dx ; @07100
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @07101
    mov di,0x2c ; @07103
    mul di ; @07106
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07108
    pop dx ; @0710A
    pop ax ; @0710B
    db 0x03,0xfa ; ENCODED: add di,dx (NASM chooses a different encoding) ; @0710C
    add di,[DrawingOrigin-GameDataImage] ; @0710E
    mov cx,[EntitySpriteBufferSegment-GameDataImage] ; @07112
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @07116
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @07118
    jz loc_7159 ; @0711A
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0711C
    pop ax ; @0711E
    pop dx ; @0711F
    push dx ; @07120
    push ax ; @07121
    push di ; @07122
    push cx ; @07123
    push si ; @07124
    push bx ; @07125
    mov cx,[GeneratedGraphicsBufferSegment-GameDataImage] ; @07126
    shl dl,1 ; @0712A
    shl dl,1 ; @0712C
    shl dl,1 ; @0712E
    shl dl,1 ; @07130
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07132
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @07134
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @07136
    and ah,0xf0 ; @07138
    mov al,0x40 ; @0713B
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @0713D
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0713F
    shl ax,1 ; @07141
    shl ax,1 ; @07143
    shl ax,1 ; @07145
    add ax,0x1070 ; @07147
    db 0x03,0xc2 ; ENCODED: add ax,dx (NASM chooses a different encoding) ; @0714A
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @0714C
    sub di,0x15f ; @0714E
    call DrawEntityTwoByteStrip ; @07152
EntitySpriteStripResume:
    pop bx ; @07155
    pop si ; @07156
    pop cx ; @07157
    pop di ; @07158
loc_7159:
    pop ax ; @07159
    pop dx ; @0715A
EntitySpriteIndirectCall:
    call ax ; @0715B
EntitySpriteRestoreDI:
    pop di ; @0715D
EntitySpriteReturn:
    ret ; @0715E
times -(($-$$) != 0x715f) db 0 ; module end assertion
