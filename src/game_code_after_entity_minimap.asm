; Maintained suffix after entity_minimap.asm; physical order unchanged.
times -(($-$$) != 0x706f) db 0 ; module start assertion
DrawObjectSprite:
    push di ; @0706F
    mov bx,[di] ; @07070
    add bx,[di+0x4] ; @07072
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
    jmp sub_715D ; @0708B
loc_708E:
    mov ax,[0x0] ; @0708E
    sub ax,0x10 ; @07091
    db 0x2b,0xd0 ; ENCODED: sub dx,ax (NASM chooses a different encoding) ; @07094
    jns loc_709C ; @07096
    add dx,0x160 ; @07098
loc_709C:
    db 0x8b,0xda ; ENCODED: mov bx,dx (NASM chooses a different encoding) ; @0709C
    and bx,byte +0x7 ; @0709E
    push bx ; @070A1
    mov al,[di+0x28] ; @070A2
    cmp byte [di+0x27],0x1 ; @070A5
    jz loc_70AE ; @070A9
    add al,[di+0x29] ; @070AB
loc_70AE:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @070AE
    cmp byte [di+0x2a],0xff ; @070B0
    jz loc_70BE ; @070B4
    shl ax,1 ; @070B6
    shl ax,1 ; @070B8
    shl ax,1 ; @070BA
    db 0x03,0xc3 ; ENCODED: add ax,bx (NASM chooses a different encoding) ; @070BC
loc_70BE:
    push dx ; @070BE
    mov cx,[di+0x10] ; @070BF
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
    add bp,[di+0xc] ; @070D6
    and ax,0xf ; @070D9
    pop dx ; @070DC
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @070DD
    add si,[di+0xa] ; @070DF
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @070E2
    add bx,[di+0x12] ; @070E4
    shr dx,1 ; @070E7
    shr dx,1 ; @070E9
    shr dx,1 ; @070EB
    mov cx,[di+0x6] ; @070ED
    push word [di+0x14] ; @070F0
    mov al,[di+0x20] ; @070F3
    mov di,[di+0x2] ; @070F6
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
    pop bx ; @07155
    pop si ; @07156
    pop cx ; @07157
    pop di ; @07158
loc_7159:
    pop ax ; @07159
    pop dx ; @0715A
    call ax ; @0715B
sub_715D:
    pop di ; @0715D
    ret ; @0715E
sub_715F:
    mov bp,ds ; @0715F
    cli ; @07161
    mov dx,0x3c4 ; @07162
    mov ax,0xf02 ; @07165
    out dx,ax ; @07168
    mov dx,0x3ce ; @07169
    mov ax,0x105 ; @0716C
    out dx,ax ; @0716F
    mov di,[0xe] ; @07170
    mov si,[0xa] ; @07174
    mov dx,0xa000 ; @07178
    mov es,dx ; @0717B
    mov ds,dx ; @0717D
    mov cx,0x10 ; @0717F
loc_7182:
    movsb ; @07182
    movsb ; @07183
    movsb ; @07184
    add di,byte +0x29 ; @07185
    loop loc_7182 ; @07188
    mov ds,bp ; @0718A
    mov dl,[0x1fe0] ; @0718C
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07190
    add dx,[0x10] ; @07192
    shr dx,1 ; @07196
    shr dx,1 ; @07198
    shr dx,1 ; @0719A
    mov si,[0x12] ; @0719C
    push dx ; @071A0
    db 0x8b,0xc6 ; ENCODED: mov ax,si (NASM chooses a different encoding) ; @071A1
    mov si,0x2c ; @071A3
    mul si ; @071A6
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @071A8
    pop dx ; @071AA
    db 0x03,0xf2 ; ENCODED: add si,dx (NASM chooses a different encoding) ; @071AB
    add si,[AlternateDrawingOrigin-GameDataImage] ; @071AD
    mov [0xc],si ; @071B1
    mov di,[0x8] ; @071B5
    push es ; @071B9
    pop ds ; @071BA
    mov cx,0x10 ; @071BB
loc_71BE:
    movsb ; @071BE
    movsb ; @071BF
    movsb ; @071C0
    add si,byte +0x29 ; @071C1
    loop loc_71BE ; @071C4
    sti ; @071C6
    mov ds,bp ; @071C7
    ret ; @071C9
; UNKNOWN: unresolved bytes
    db 0x8c,0xdd,0xfa,0xba,0xc4,0x03,0xb8,0x02,0x0f,0xef,0xba,0xce,0x03,0xb8,0x05,0x01 ; @071CA
; UNKNOWN: unresolved bytes
    db 0xef,0x8b,0x16,0x10,0x00,0xd1,0xea,0xd1,0xea,0xd1,0xea,0x8b,0x36,0x12,0x00,0x52 ; @071DA
; UNKNOWN: unresolved bytes
    db 0x8b,0xc6,0xbe,0x2c,0x00,0xf7,0xe6,0x8b,0xf0,0x5a,0x03,0xf2,0x03,0x36,0x78,0x1f ; @071EA
; UNKNOWN: unresolved bytes
    db 0x89,0x36,0x0c,0x00,0x8b,0x3e,0x08,0x00,0xba,0x00,0xa0,0x8e,0xc2,0x8e,0xda,0xb9 ; @071FA
; UNKNOWN: unresolved bytes
    db 0x10,0x00,0xa4,0xa4,0xa4,0x83,0xc6,0x29,0xe2,0xf8,0xfb,0x8e,0xdd,0xc3 ; @0720A
sub_7218:
    cli ; @07218
    mov dx,0x3c4 ; @07219
    mov ax,0xf02 ; @0721C
    out dx,ax ; @0721F
    mov dx,0x3ce ; @07220
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07223
    out dx,ax ; @07225
    mov ax,0xe01 ; @07226
    out dx,ax ; @07229
    mov ax,0x5 ; @0722A
    out dx,ax ; @0722D
    mov ax,0x3 ; @0722E
    out dx,ax ; @07231
    mov cx,0xa000 ; @07232
    mov es,cx ; @07235
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @07237
    mov cx,[bx] ; @07239
    inc bx ; @0723B
    inc bx ; @0723C
    mov al,0x8 ; @0723D
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0723F
    out dx,ax ; @07241
    mov al,[es:di] ; @07242
    lodsw ; @07245
    stosb ; @07246
    xchg ch,ah ; @07247
    mov al,0x8 ; @07249
    out dx,ax ; @0724B
    mov al,[es:di] ; @0724C
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0724F
    stosb ; @07251
    mov ah,[bx] ; @07252
    inc bx ; @07254
    mov al,0x8 ; @07255
    out dx,ax ; @07257
    mov al,[es:di] ; @07258
    lodsb ; @0725B
    stosb ; @0725C
    add di,byte +0x29 ; @0725D
    mov cx,[bx] ; @07260
    inc bx ; @07262
    inc bx ; @07263
    mov al,0x8 ; @07264
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07266
    out dx,ax ; @07268
    mov al,[es:di] ; @07269
    lodsw ; @0726C
    stosb ; @0726D
    xchg ch,ah ; @0726E
    mov al,0x8 ; @07270
    out dx,ax ; @07272
    mov al,[es:di] ; @07273
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07276
    stosb ; @07278
    mov ah,[bx] ; @07279
    inc bx ; @0727B
    mov al,0x8 ; @0727C
    out dx,ax ; @0727E
    mov al,[es:di] ; @0727F
    lodsb ; @07282
    stosb ; @07283
    add di,byte +0x29 ; @07284
    mov cx,[bx] ; @07287
    inc bx ; @07289
    inc bx ; @0728A
    mov al,0x8 ; @0728B
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0728D
    out dx,ax ; @0728F
    mov al,[es:di] ; @07290
    lodsw ; @07293
    stosb ; @07294
    xchg ch,ah ; @07295
    mov al,0x8 ; @07297
    out dx,ax ; @07299
    mov al,[es:di] ; @0729A
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0729D
    stosb ; @0729F
    mov ah,[bx] ; @072A0
    inc bx ; @072A2
    mov al,0x8 ; @072A3
    out dx,ax ; @072A5
    mov al,[es:di] ; @072A6
    lodsb ; @072A9
    stosb ; @072AA
    add di,byte +0x29 ; @072AB
    mov cx,[bx] ; @072AE
    inc bx ; @072B0
    inc bx ; @072B1
    mov al,0x8 ; @072B2
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @072B4
    out dx,ax ; @072B6
    mov al,[es:di] ; @072B7
    lodsw ; @072BA
    stosb ; @072BB
    xchg ch,ah ; @072BC
    mov al,0x8 ; @072BE
    out dx,ax ; @072C0
    mov al,[es:di] ; @072C1
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @072C4
    stosb ; @072C6
    mov ah,[bx] ; @072C7
    inc bx ; @072C9
    mov al,0x8 ; @072CA
    out dx,ax ; @072CC
    mov al,[es:di] ; @072CD
    lodsb ; @072D0
    stosb ; @072D1
    add di,byte +0x29 ; @072D2
    mov cx,[bx] ; @072D5
    inc bx ; @072D7
    inc bx ; @072D8
    mov al,0x8 ; @072D9
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @072DB
    out dx,ax ; @072DD
    mov al,[es:di] ; @072DE
    lodsw ; @072E1
    stosb ; @072E2
    xchg ch,ah ; @072E3
    mov al,0x8 ; @072E5
    out dx,ax ; @072E7
    mov al,[es:di] ; @072E8
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @072EB
    stosb ; @072ED
    mov ah,[bx] ; @072EE
    inc bx ; @072F0
    mov al,0x8 ; @072F1
    out dx,ax ; @072F3
    mov al,[es:di] ; @072F4
    lodsb ; @072F7
    stosb ; @072F8
    add di,byte +0x29 ; @072F9
    mov cx,[bx] ; @072FC
    inc bx ; @072FE
    inc bx ; @072FF
    mov al,0x8 ; @07300
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07302
    out dx,ax ; @07304
    mov al,[es:di] ; @07305
    lodsw ; @07308
    stosb ; @07309
    xchg ch,ah ; @0730A
    mov al,0x8 ; @0730C
    out dx,ax ; @0730E
    mov al,[es:di] ; @0730F
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07312
    stosb ; @07314
    mov ah,[bx] ; @07315
    inc bx ; @07317
    mov al,0x8 ; @07318
    out dx,ax ; @0731A
    mov al,[es:di] ; @0731B
    lodsb ; @0731E
    stosb ; @0731F
    add di,byte +0x29 ; @07320
    mov cx,[bx] ; @07323
    inc bx ; @07325
    inc bx ; @07326
    mov al,0x8 ; @07327
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07329
    out dx,ax ; @0732B
    mov al,[es:di] ; @0732C
    lodsw ; @0732F
    stosb ; @07330
    xchg ch,ah ; @07331
    mov al,0x8 ; @07333
    out dx,ax ; @07335
    mov al,[es:di] ; @07336
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07339
    stosb ; @0733B
    mov ah,[bx] ; @0733C
    inc bx ; @0733E
    mov al,0x8 ; @0733F
    out dx,ax ; @07341
    mov al,[es:di] ; @07342
    lodsb ; @07345
    stosb ; @07346
    add di,byte +0x29 ; @07347
    mov cx,[bx] ; @0734A
    inc bx ; @0734C
    inc bx ; @0734D
    mov al,0x8 ; @0734E
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07350
    out dx,ax ; @07352
    mov al,[es:di] ; @07353
    lodsw ; @07356
    stosb ; @07357
    xchg ch,ah ; @07358
    mov al,0x8 ; @0735A
    out dx,ax ; @0735C
    mov al,[es:di] ; @0735D
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07360
    stosb ; @07362
    mov ah,[bx] ; @07363
    inc bx ; @07365
    mov al,0x8 ; @07366
    out dx,ax ; @07368
    mov al,[es:di] ; @07369
    lodsb ; @0736C
    stosb ; @0736D
    add di,byte +0x29 ; @0736E
    mov cx,[bx] ; @07371
    inc bx ; @07373
    inc bx ; @07374
    mov al,0x8 ; @07375
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07377
    out dx,ax ; @07379
    mov al,[es:di] ; @0737A
    lodsw ; @0737D
    stosb ; @0737E
    xchg ch,ah ; @0737F
    mov al,0x8 ; @07381
    out dx,ax ; @07383
    mov al,[es:di] ; @07384
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07387
    stosb ; @07389
    mov ah,[bx] ; @0738A
    inc bx ; @0738C
    mov al,0x8 ; @0738D
    out dx,ax ; @0738F
    mov al,[es:di] ; @07390
    lodsb ; @07393
    stosb ; @07394
    add di,byte +0x29 ; @07395
    mov cx,[bx] ; @07398
    inc bx ; @0739A
    inc bx ; @0739B
    mov al,0x8 ; @0739C
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0739E
    out dx,ax ; @073A0
    mov al,[es:di] ; @073A1
    lodsw ; @073A4
    stosb ; @073A5
    xchg ch,ah ; @073A6
    mov al,0x8 ; @073A8
    out dx,ax ; @073AA
    mov al,[es:di] ; @073AB
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @073AE
    stosb ; @073B0
    mov ah,[bx] ; @073B1
    inc bx ; @073B3
    mov al,0x8 ; @073B4
    out dx,ax ; @073B6
    mov al,[es:di] ; @073B7
    lodsb ; @073BA
    stosb ; @073BB
    add di,byte +0x29 ; @073BC
    mov cx,[bx] ; @073BF
    inc bx ; @073C1
    inc bx ; @073C2
    mov al,0x8 ; @073C3
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @073C5
    out dx,ax ; @073C7
    mov al,[es:di] ; @073C8
    lodsw ; @073CB
    stosb ; @073CC
    xchg ch,ah ; @073CD
    mov al,0x8 ; @073CF
    out dx,ax ; @073D1
    mov al,[es:di] ; @073D2
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @073D5
    stosb ; @073D7
    mov ah,[bx] ; @073D8
    inc bx ; @073DA
    mov al,0x8 ; @073DB
    out dx,ax ; @073DD
    mov al,[es:di] ; @073DE
    lodsb ; @073E1
    stosb ; @073E2
    add di,byte +0x29 ; @073E3
    mov cx,[bx] ; @073E6
    inc bx ; @073E8
    inc bx ; @073E9
    mov al,0x8 ; @073EA
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @073EC
    out dx,ax ; @073EE
    mov al,[es:di] ; @073EF
    lodsw ; @073F2
    stosb ; @073F3
    xchg ch,ah ; @073F4
    mov al,0x8 ; @073F6
    out dx,ax ; @073F8
    mov al,[es:di] ; @073F9
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @073FC
    stosb ; @073FE
    mov ah,[bx] ; @073FF
    inc bx ; @07401
    mov al,0x8 ; @07402
    out dx,ax ; @07404
    mov al,[es:di] ; @07405
    lodsb ; @07408
    stosb ; @07409
    add di,byte +0x29 ; @0740A
    mov cx,[bx] ; @0740D
    inc bx ; @0740F
    inc bx ; @07410
    mov al,0x8 ; @07411
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07413
    out dx,ax ; @07415
    mov al,[es:di] ; @07416
    lodsw ; @07419
    stosb ; @0741A
    xchg ch,ah ; @0741B
    mov al,0x8 ; @0741D
    out dx,ax ; @0741F
    mov al,[es:di] ; @07420
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07423
    stosb ; @07425
    mov ah,[bx] ; @07426
    inc bx ; @07428
    mov al,0x8 ; @07429
    out dx,ax ; @0742B
    mov al,[es:di] ; @0742C
    lodsb ; @0742F
    stosb ; @07430
    add di,byte +0x29 ; @07431
    mov cx,[bx] ; @07434
    inc bx ; @07436
    inc bx ; @07437
    mov al,0x8 ; @07438
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0743A
    out dx,ax ; @0743C
    mov al,[es:di] ; @0743D
    lodsw ; @07440
    stosb ; @07441
    xchg ch,ah ; @07442
    mov al,0x8 ; @07444
    out dx,ax ; @07446
    mov al,[es:di] ; @07447
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0744A
    stosb ; @0744C
    mov ah,[bx] ; @0744D
    inc bx ; @0744F
    mov al,0x8 ; @07450
    out dx,ax ; @07452
    mov al,[es:di] ; @07453
    lodsb ; @07456
    stosb ; @07457
    add di,byte +0x29 ; @07458
    mov cx,[bx] ; @0745B
    inc bx ; @0745D
    inc bx ; @0745E
    mov al,0x8 ; @0745F
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07461
    out dx,ax ; @07463
    mov al,[es:di] ; @07464
    lodsw ; @07467
    stosb ; @07468
    xchg ch,ah ; @07469
    mov al,0x8 ; @0746B
    out dx,ax ; @0746D
    mov al,[es:di] ; @0746E
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07471
    stosb ; @07473
    mov ah,[bx] ; @07474
    inc bx ; @07476
    mov al,0x8 ; @07477
    out dx,ax ; @07479
    mov al,[es:di] ; @0747A
    lodsb ; @0747D
    stosb ; @0747E
    add di,byte +0x29 ; @0747F
    mov cx,[bx] ; @07482
    inc bx ; @07484
    inc bx ; @07485
    mov al,0x8 ; @07486
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07488
    out dx,ax ; @0748A
    mov al,[es:di] ; @0748B
    lodsw ; @0748E
    stosb ; @0748F
    xchg ch,ah ; @07490
    mov al,0x8 ; @07492
    out dx,ax ; @07494
    mov al,[es:di] ; @07495
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07498
    stosb ; @0749A
    mov ah,[bx] ; @0749B
    inc bx ; @0749D
    mov al,0x8 ; @0749E
    out dx,ax ; @074A0
    mov al,[es:di] ; @074A1
    lodsb ; @074A4
    stosb ; @074A5
    add di,byte +0x29 ; @074A6
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @074A9
    mov ax,0x1 ; @074AB
    out dx,ax ; @074AE
    mov ax,0x1003 ; @074AF
    out dx,ax ; @074B2
    mov ax,0xff08 ; @074B3
    out dx,ax ; @074B6
    mov dl,0xc4 ; @074B7
    mov ax,0x202 ; @074B9
    out dx,ax ; @074BC
    mov al,[es:di] ; @074BD
    lodsw ; @074C0
    stosb ; @074C1
    mov al,[es:di] ; @074C2
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @074C5
    stosb ; @074C7
    mov al,[es:di] ; @074C8
    lodsb ; @074CB
    stosb ; @074CC
    add di,byte +0x29 ; @074CD
    mov al,[es:di] ; @074D0
    lodsw ; @074D3
    stosb ; @074D4
    mov al,[es:di] ; @074D5
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @074D8
    stosb ; @074DA
    mov al,[es:di] ; @074DB
    lodsb ; @074DE
    stosb ; @074DF
    add di,byte +0x29 ; @074E0
    mov al,[es:di] ; @074E3
    lodsw ; @074E6
    stosb ; @074E7
    mov al,[es:di] ; @074E8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @074EB
    stosb ; @074ED
    mov al,[es:di] ; @074EE
    lodsb ; @074F1
    stosb ; @074F2
    add di,byte +0x29 ; @074F3
    mov al,[es:di] ; @074F6
    lodsw ; @074F9
    stosb ; @074FA
    mov al,[es:di] ; @074FB
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @074FE
    stosb ; @07500
    mov al,[es:di] ; @07501
    lodsb ; @07504
    stosb ; @07505
    add di,byte +0x29 ; @07506
    mov al,[es:di] ; @07509
    lodsw ; @0750C
    stosb ; @0750D
    mov al,[es:di] ; @0750E
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @07511
    stosb ; @07513
    mov al,[es:di] ; @07514
    lodsb ; @07517
    stosb ; @07518
    add di,byte +0x29 ; @07519
    mov al,[es:di] ; @0751C
    lodsw ; @0751F
    stosb ; @07520
    mov al,[es:di] ; @07521
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @07524
    stosb ; @07526
    mov al,[es:di] ; @07527
    lodsb ; @0752A
    stosb ; @0752B
    add di,byte +0x29 ; @0752C
    mov al,[es:di] ; @0752F
    lodsw ; @07532
    stosb ; @07533
    mov al,[es:di] ; @07534
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @07537
    stosb ; @07539
    mov al,[es:di] ; @0753A
    lodsb ; @0753D
    stosb ; @0753E
    add di,byte +0x29 ; @0753F
    mov al,[es:di] ; @07542
    lodsw ; @07545
    stosb ; @07546
    mov al,[es:di] ; @07547
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0754A
    stosb ; @0754C
    mov al,[es:di] ; @0754D
    lodsb ; @07550
    stosb ; @07551
    add di,byte +0x29 ; @07552
    mov al,[es:di] ; @07555
    lodsw ; @07558
    stosb ; @07559
    mov al,[es:di] ; @0755A
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0755D
    stosb ; @0755F
    mov al,[es:di] ; @07560
    lodsb ; @07563
    stosb ; @07564
    add di,byte +0x29 ; @07565
    mov al,[es:di] ; @07568
    lodsw ; @0756B
    stosb ; @0756C
    mov al,[es:di] ; @0756D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @07570
    stosb ; @07572
    mov al,[es:di] ; @07573
    lodsb ; @07576
    stosb ; @07577
    add di,byte +0x29 ; @07578
    mov al,[es:di] ; @0757B
    lodsw ; @0757E
    stosb ; @0757F
    mov al,[es:di] ; @07580
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @07583
    stosb ; @07585
    mov al,[es:di] ; @07586
    lodsb ; @07589
    stosb ; @0758A
    add di,byte +0x29 ; @0758B
    mov al,[es:di] ; @0758E
    lodsw ; @07591
    stosb ; @07592
    mov al,[es:di] ; @07593
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @07596
    stosb ; @07598
    mov al,[es:di] ; @07599
    lodsb ; @0759C
    stosb ; @0759D
    add di,byte +0x29 ; @0759E
    mov al,[es:di] ; @075A1
    lodsw ; @075A4
    stosb ; @075A5
    mov al,[es:di] ; @075A6
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @075A9
    stosb ; @075AB
    mov al,[es:di] ; @075AC
    lodsb ; @075AF
    stosb ; @075B0
    add di,byte +0x29 ; @075B1
    mov al,[es:di] ; @075B4
    lodsw ; @075B7
    stosb ; @075B8
    mov al,[es:di] ; @075B9
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @075BC
    stosb ; @075BE
    mov al,[es:di] ; @075BF
    lodsb ; @075C2
    stosb ; @075C3
    add di,byte +0x29 ; @075C4
    mov al,[es:di] ; @075C7
    lodsw ; @075CA
    stosb ; @075CB
    mov al,[es:di] ; @075CC
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @075CF
    stosb ; @075D1
    mov al,[es:di] ; @075D2
    lodsb ; @075D5
    stosb ; @075D6
    add di,byte +0x29 ; @075D7
    mov al,[es:di] ; @075DA
    lodsw ; @075DD
    stosb ; @075DE
    mov al,[es:di] ; @075DF
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @075E2
    stosb ; @075E4
    mov al,[es:di] ; @075E5
    lodsb ; @075E8
    stosb ; @075E9
    add di,byte +0x29 ; @075EA
    sti ; @075ED
    ret ; @075EE
times -(($-$$) != 0x75ef) db 0 ; module end assertion
