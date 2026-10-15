; Maintained image span 01F19..0368D; reconstruction module, not a historical linker claim.
; Mixed ownership remains provisional; UNKNOWN bytes and overlay storage keep their classifications.
sub_1F19:
    cmp byte [0x2b],0xff ; @01F19
    jnz loc_1F23 ; @01F1E
    jmp loc_1FFF ; @01F20
loc_1F23:
    call sub_5D94 ; @01F23
    mov byte [0x50],0xff ; @01F26
    mov si,0x88 ; @01F2B
    mov al,[0x43] ; @01F2E
    mov [0x42],al ; @01F31
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01F34
    jnz loc_1F3B ; @01F36
    jmp loc_1FFF ; @01F38
loc_1F3B:
    push es ; @01F3B
    cmp byte [si+0x26],0xff ; @01F3C
    jnz loc_1F45 ; @01F40
    jmp loc_1FEB ; @01F42
loc_1F45:
    mov al,[si+0x20] ; @01F45
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01F48
    jz loc_1F54 ; @01F4A
    call sub_2E04 ; @01F4C
    jnz loc_1F54 ; @01F4F
    jmp loc_1FEB ; @01F51
loc_1F54:
    mov al,[si+0x24] ; @01F54
    test al,0x80 ; @01F57
    jz loc_1F5E ; @01F59
    jmp loc_2DB5 ; @01F5B
loc_1F5E:
    mov ax,[si+0x8] ; @01F5E
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @01F61
    jnz loc_1F68 ; @01F63
    jmp loc_2047 ; @01F65
loc_1F68:
    test ax,0x2 ; @01F68
    jz loc_1F70 ; @01F6B
    jmp loc_2350 ; @01F6D
loc_1F70:
    test ax,0x8000 ; @01F70
    jz loc_1F78 ; @01F73
    jmp loc_2D0F ; @01F75
loc_1F78:
    test ax,0x4 ; @01F78
    jz loc_1F80 ; @01F7B
    jmp loc_21B0 ; @01F7D
loc_1F80:
    test ax,0x400 ; @01F80
    jz loc_1F88 ; @01F83
    jmp loc_2A6D ; @01F85
loc_1F88:
    test ax,0x1 ; @01F88
    jz loc_1F90 ; @01F8B
    jmp loc_22DF ; @01F8D
loc_1F90:
    test ax,0x8 ; @01F90
    jz loc_1F98 ; @01F93
    jmp loc_23BF ; @01F95
loc_1F98:
    test ax,0x10 ; @01F98
    jz loc_1FA0 ; @01F9B
    jmp loc_23F3 ; @01F9D
loc_1FA0:
    test ax,0x20 ; @01FA0
    jz loc_1FA8 ; @01FA3
    jmp loc_254F ; @01FA5
loc_1FA8:
    test ax,0x40 ; @01FA8
    jz loc_1FB0 ; @01FAB
    jmp loc_2637 ; @01FAD
loc_1FB0:
    test ax,0x80 ; @01FB0
    jz loc_1FB8 ; @01FB3
    jmp loc_2693 ; @01FB5
loc_1FB8:
    test ax,0x100 ; @01FB8
    jz loc_1FC0 ; @01FBB
    jmp loc_27E8 ; @01FBD
loc_1FC0:
    test ax,0x200 ; @01FC0
    jz loc_1FC8 ; @01FC3
    jmp loc_287D ; @01FC5
loc_1FC8:
    test ax,0x800 ; @01FC8
    jz loc_1FD0 ; @01FCB
    jmp loc_2B35 ; @01FCD
loc_1FD0:
    test ax,0x1000 ; @01FD0
    jz loc_1FD8 ; @01FD3
    jmp loc_22F5 ; @01FD5
loc_1FD8:
    test ax,0x2000 ; @01FD8
    jz loc_1FE0 ; @01FDB
    jmp loc_2326 ; @01FDD
loc_1FE0:
    test ax,0x4000 ; @01FE0
    jz loc_1FE8 ; @01FE3
    jmp loc_2340 ; @01FE5
loc_1FE8:
    call sub_2EC0 ; @01FE8
loc_1FEB:
    pop es ; @01FEB
    add si,byte +0x2d ; @01FEC
    dec byte [0x42] ; @01FEF
    jz loc_1FF8 ; @01FF3
    jmp loc_1F3B ; @01FF5
loc_1FF8:
    cmp byte [0x4b],0x0 ; @01FF8
    jnz loc_2005 ; @01FFD
loc_1FFF:
    mov byte [0x50],0x0 ; @01FFF
    ret ; @02004
loc_2005:
    mov al,[0x4c] ; @02005
    cmp al,[0x43] ; @02008
    jz loc_203C ; @0200C
    mov cx,0x2d ; @0200E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @02011
    mul cx ; @02013
    add ax,0x88 ; @02015
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @02018
    cmp byte [si+0x20],0x0 ; @0201A
    jnz loc_2037 ; @0201E
    cmp byte [si+0x26],0xff ; @02020
    jnz loc_202C ; @02024
    inc byte [0x4c] ; @02026
    jmp short loc_2005 ; @0202A
loc_202C:
    test word [si+0x8],0x3 ; @0202C
    jnz loc_2037 ; @02031
    mov byte [si+0x20],0x4f ; @02033
loc_2037:
    inc byte [0x4c] ; @02037
    ret ; @0203B
loc_203C:
    mov byte [0x4b],0x0 ; @0203C
    mov byte [0x50],0x0 ; @02041
    ret ; @02046
loc_2047:
    mov al,[si+0x28] ; @02047
    inc al ; @0204A
    and al,0x7 ; @0204C
    mov [si+0x28],al ; @0204E
    mov al,[si+0x27] ; @02051
    cbw ; @02054
    add [si],ax ; @02055
    cmp word [si],byte +0x10 ; @02057
    jnl loc_205F ; @0205A
    jmp loc_2142 ; @0205C
loc_205F:
    cmp word [si],0x680 ; @0205F
    jl loc_2068 ; @02063
    jmp loc_2142 ; @02065
loc_2068:
    call PrepareEntityPixelSample ; @02068
    mov bp,[si+0x2] ; @0206B
    mov al,[es:di] ; @0206E
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02071
    jnz loc_20E9 ; @02073
    inc bp ; @02075
    add di,[0x4] ; @02076
    mov al,[es:di] ; @0207A
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0207D
    jnz loc_20D6 ; @0207F
    inc bp ; @02081
    add di,[0x4] ; @02082
    mov al,[es:di] ; @02086
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02089
    jnz loc_20D6 ; @0208B
    inc bp ; @0208D
    add di,[0x4] ; @0208E
    mov al,[es:di] ; @02092
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02095
    jnz loc_20D6 ; @02097
    inc bp ; @02099
    or word [si+0x8],byte +0x4 ; @0209A
    mov word [si+0xa],0x0 ; @0209E
    mov word [si+0xc],0xa42 ; @020A3
    mov word [si+0x10],0x5a ; @020A8
    mov word [si+0x12],0x3c ; @020AD
    mov byte [si+0x28],0x0 ; @020B2
    mov byte [si+0x23],0x3 ; @020B6
    mov word [si+0x4],0xfff8 ; @020BA
    mov word [si+0x6],0xfff6 ; @020BF
    mov byte [si+0x29],0x4 ; @020C4
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @020C8
    mov [si+0x14],ax ; @020CB
    mov byte [si+0x2a],0x0 ; @020CE
    and byte [si+0x24],0x1 ; @020D2
loc_20D6:
    mov [si+0x2],bp ; @020D6
    cmp bp,0xb4 ; @020D9
    jnl loc_20E2 ; @020DD
    jmp loc_1FE8 ; @020DF
loc_20E2:
    mov byte [si+0x26],0xff ; @020E2
    jmp loc_1FEB ; @020E6
loc_20E9:
    sub di,[0x4] ; @020E9
    mov al,[es:di] ; @020ED
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @020F0
    jz loc_2148 ; @020F2
    dec bp ; @020F4
    sub di,[0x4] ; @020F5
    mov al,[es:di] ; @020F9
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @020FC
    jz loc_2148 ; @020FE
    dec bp ; @02100
    sub di,[0x4] ; @02101
    mov al,[es:di] ; @02105
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02108
    jz loc_2148 ; @0210A
    dec bp ; @0210C
    sub di,[0x4] ; @0210D
    mov al,[es:di] ; @02111
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02114
    jz loc_2169 ; @02116
    dec bp ; @02118
    sub di,[0x4] ; @02119
    mov al,[es:di] ; @0211D
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02120
    jz loc_2169 ; @02122
    dec bp ; @02124
    sub di,[0x4] ; @02125
    mov al,[es:di] ; @02129
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0212C
    jz loc_2169 ; @0212E
    dec bp ; @02130
    sub di,[0x4] ; @02131
    mov al,[es:di] ; @02135
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02138
    jz loc_2169 ; @0213A
    test byte [si+0x24],0x1 ; @0213C
    jnz loc_2179 ; @02140
loc_2142:
    neg byte [si+0x27] ; @02142
    jmp loc_1FE8 ; @02145
loc_2148:
    mov [si+0x2],bp ; @02148
    add bp,[si+0x6] ; @0214B
    cmp bp,byte +0xa ; @0214E
    jng loc_2156 ; @02151
    jmp loc_1FE8 ; @02153
loc_2156:
    mov bp,0x9 ; @02156
    sub bp,[si+0x6] ; @02159
    mov [si+0x2],bp ; @0215C
    neg byte [si+0x27] ; @0215F
    and word [si+0x8],byte -0x9 ; @02162
    jmp loc_1FE8 ; @02166
loc_2169:
    or word [si+0x8],byte +0x8 ; @02169
    mov byte [si+0x28],0x8 ; @0216D
    mov bp,[si+0x2] ; @02171
    sub bp,byte +0x2 ; @02174
    jmp short loc_2148 ; @02177
loc_2179:
    mov byte [si+0x28],0x0 ; @02179
    mov word [si+0xa],0x0 ; @0217D
    mov word [si+0xc],0x39a ; @02182
    or word [si+0x8],byte +0x20 ; @02187
    mov word [si+0x10],0x48 ; @0218B
    mov word [si+0x12],0x30 ; @02190
    mov word [si+0x4],0xfff8 ; @02195
    mov word [si+0x6],0xfff4 ; @0219A
    mov ax,[DrawingCallbackSlots-GameDataImage+0x2] ; @0219F
    mov [si+0x14],ax ; @021A2
    mov byte [si+0x2a],0xff ; @021A5
    mov byte [si+0x29],0x8 ; @021A9
    jmp loc_1FE8 ; @021AD
loc_21B0:
    mov al,[si+0x28] ; @021B0
    inc al ; @021B3
    and al,0x3 ; @021B5
    mov [si+0x28],al ; @021B7
    cmp byte [si+0x23],0x10 ; @021BA
    jna loc_2202 ; @021BE
    cmp byte [si+0x25],0x0 ; @021C0
    jz loc_2202 ; @021C4
    mov word [si+0x8],0x400 ; @021C6
    mov word [si+0xa],0x0 ; @021CB
    mov word [si+0xc],0xbaa ; @021D0
    mov word [si+0x10],0x80 ; @021D5
    mov word [si+0x12],0x60 ; @021DA
    mov byte [si+0x28],0x0 ; @021DF
    mov word [si+0xe],0x0 ; @021E3
    mov word [si+0x6],0xfff0 ; @021E8
    mov byte [si+0x29],0x8 ; @021ED
    mov ax,[DrawingCallbackSlots-GameDataImage+0xc] ; @021F1
    mov [si+0x14],ax ; @021F4
    mov byte [si+0x2a],0xff ; @021F7
    and byte [si+0x24],0x1 ; @021FB
    jmp loc_1FE8 ; @021FF
loc_2202:
    call PrepareEntityPixelSample ; @02202
    mov bp,[si+0x2] ; @02205
    mov al,[es:di] ; @02208
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0220B
    jnz loc_224D ; @0220D
    inc bp ; @0220F
    cmp bp,0xb4 ; @02210
    jl loc_2219 ; @02214
    jmp loc_20E2 ; @02216
loc_2219:
    add di,[0x4] ; @02219
    mov al,[es:di] ; @0221D
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02220
    jnz loc_224D ; @02222
    inc bp ; @02224
    cmp bp,0xb4 ; @02225
    jl loc_222E ; @02229
    jmp loc_20E2 ; @0222B
loc_222E:
    add di,[0x4] ; @0222E
    mov al,[es:di] ; @02232
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02235
    jnz loc_224D ; @02237
    inc bp ; @02239
    add byte [si+0x23],0x3 ; @0223A
    mov [si+0x2],bp ; @0223E
    cmp bp,0xb4 ; @02241
    jnl loc_224A ; @02245
    jmp loc_1FE8 ; @02247
loc_224A:
    jmp loc_20E2 ; @0224A
loc_224D:
    mov [si+0x2],bp ; @0224D
    cmp byte [si+0x23],0x3c ; @02250
    jna loc_22A3 ; @02254
    mov word [si+0x8],0x1 ; @02256
    mov word [si+0xa],0x0 ; @0225B
    mov word [si+0xc],0xc2a ; @02260
    mov word [si+0x10],0x5a ; @02265
    mov word [si+0x12],0x3c ; @0226A
    mov byte [si+0x28],0x0 ; @0226F
    mov byte [si+0x27],0x0 ; @02273
    mov byte [si+0x20],0x0 ; @02277
    mov byte [si+0x29],0x0 ; @0227B
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0227F
    mov [si+0x14],ax ; @02282
    mov byte [si+0x2a],0x0 ; @02285
    and byte [si+0x24],0x1 ; @02289
    cmp byte [0x2010],0xff ; @0228D
    jnz loc_22A0 ; @02292
    test byte [0x25a7],0x3 ; @02294
    jz loc_22A0 ; @02299
    mov ax,0x408 ; @0229B
    int 0x61 ; @0229E
loc_22A0:
    jmp loc_1FE8 ; @022A0
loc_22A3:
    mov word [si+0x8],0x0 ; @022A3
    mov word [si+0xa],0x0 ; @022A8
    mov word [si+0xc],0x0 ; @022AD
    mov word [si+0x10],0x5a ; @022B2
    mov word [si+0x12],0x3c ; @022B7
    mov byte [si+0x28],0x0 ; @022BC
    mov word [si+0x4],0xfff8 ; @022C0
    mov word [si+0x6],0xfff6 ; @022C5
    mov byte [si+0x29],0x9 ; @022CA
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @022CE
    mov [si+0x14],ax ; @022D1
    mov byte [si+0x2a],0x0 ; @022D4
    and byte [si+0x24],0x1 ; @022D8
    jmp loc_1FE8 ; @022DC
loc_22DF:
    mov al,[si+0x28] ; @022DF
    inc al ; @022E2
    and al,0xf ; @022E4
    mov [si+0x28],al ; @022E6
    jz loc_22EE ; @022E9
    jmp loc_1FEB ; @022EB
loc_22EE:
    mov byte [si+0x26],0xff ; @022EE
    jmp loc_1FEB ; @022F2
loc_22F5:
    mov al,[si+0x28] ; @022F5
    inc al ; @022F8
    and al,0xf ; @022FA
    mov [si+0x28],al ; @022FC
    jz loc_2323 ; @022FF
    mov al,[si+0x27] ; @02301
    cbw ; @02304
    push ax ; @02305
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @02306
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @02308
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0230A
    mov cx,[si] ; @0230C
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @0230E
    mov bx,[si+0x2] ; @02310
    call sub_6141 ; @02313
    pop bx ; @02316
    mov al,[es:di] ; @02317
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0231A
    jnz loc_2320 ; @0231C
    add [si],bx ; @0231E
loc_2320:
    jmp loc_1FEB ; @02320
loc_2323:
    jmp loc_20E2 ; @02323
loc_2326:
    mov al,[si+0x28] ; @02326
    inc al ; @02329
    and al,0x7 ; @0232B
    mov [si+0x28],al ; @0232D
    jz loc_2335 ; @02330
    jmp loc_1FEB ; @02332
loc_2335:
    inc byte [0x46] ; @02335
    mov byte [si+0x26],0xff ; @02339
    jmp loc_1FEB ; @0233D
loc_2340:
    inc byte [si+0x28] ; @02340
    mov al,[si+0x28] ; @02343
    cmp al,0xe ; @02346
    jnz loc_234D ; @02348
    jmp loc_20E2 ; @0234A
loc_234D:
    jmp loc_1FEB ; @0234D
loc_2350:
    mov al,[si+0x28] ; @02350
    inc al ; @02353
    mov [si+0x28],al ; @02355
    cmp al,0x34 ; @02358
    jnz loc_235F ; @0235A
    jmp loc_20E2 ; @0235C
loc_235F:
    dec al ; @0235F
    jz loc_2366 ; @02361
    jmp loc_1FEB ; @02363
loc_2366:
    cmp byte [0x2010],0xff ; @02366
    jz loc_2379 ; @0236B
    test byte [0x25a7],0x1 ; @0236D
    jz loc_2379 ; @02372
    mov ax,0x30c ; @02374
    int 0x60 ; @02377
loc_2379:
    test word [si+0x8],0x100 ; @02379
    jnz loc_2383 ; @0237E
    jmp short loc_2386 ; @02380
; UNKNOWN: unresolved bytes
    db 0x90 ; @02382
loc_2383:
    call CopyEntityPatternToInteractionMap ; @02383
loc_2386:
    mov ax,[si] ; @02386
    mov bx,[si+0x2] ; @02388
    sub bx,byte +0x10 ; @0238B
    shr ax,1 ; @0238E
    shr ax,1 ; @02390
    shr bx,1 ; @02392
    shr bx,1 ; @02394
    push ax ; @02396
    push dx ; @02397
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02398
    mov dx,0x1a0 ; @0239A
    mul dx ; @0239D
    pop dx ; @0239F
    pop bx ; @023A0
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @023A1
    add bx,byte +0x12 ; @023A3
    mov al,[ss:bx] ; @023A6
    and al,0xf ; @023A9
    cmp al,0x9 ; @023AB
    jnz loc_23B2 ; @023AD
    jmp loc_1FEB ; @023AF
loc_23B2:
    cmp al,0x5 ; @023B2
    jnz loc_23B9 ; @023B4
    jmp loc_1FEB ; @023B6
loc_23B9:
    call sub_5DF8 ; @023B9
    jmp loc_1FEB ; @023BC
loc_23BF:
    call PrepareEntityPixelSample ; @023BF
    dec word [si+0x2] ; @023C2
    sub di,[0x4] ; @023C5
    mov al,[es:di] ; @023C9
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @023CC
    jz loc_23E4 ; @023CE
    dec word [si+0x2] ; @023D0
    sub di,[0x4] ; @023D3
    mov al,[es:di] ; @023D7
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @023DA
    jz loc_23E4 ; @023DC
    mov bp,[si+0x2] ; @023DE
    jmp loc_2148 ; @023E1
loc_23E4:
    and word [si+0x8],byte -0x9 ; @023E4
    mov byte [si+0x28],0x0 ; @023E8
    mov bp,[si+0x2] ; @023EC
    inc bp ; @023EF
    jmp loc_2148 ; @023F0
loc_23F3:
    cmp byte [si+0x28],0x11 ; @023F3
    jnz loc_23FC ; @023F7
    jmp loc_250C ; @023F9
loc_23FC:
    mov al,[si+0x28] ; @023FC
    inc al ; @023FF
    and al,0xf ; @02401
    mov [si+0x28],al ; @02403
    jz loc_240F ; @02406
    cmp al,0x8 ; @02408
    jz loc_240F ; @0240A
    jmp loc_1FEB ; @0240C
loc_240F:
    mov bp,[si] ; @0240F
    mov ax,[si+0x4] ; @02411
    add [si],ax ; @02414
    push word [si] ; @02416
    call PrepareEntityPixelSample ; @02418
    mov [si],bp ; @0241B
    inc word [si+0x2] ; @0241D
    pop cx ; @02420
    mov bp,[si+0x2] ; @02421
    cmp bp,0xb4 ; @02424
    jl loc_242D ; @02428
    jmp loc_20E2 ; @0242A
loc_242D:
    mov bx,0xff8 ; @0242D
    mov dl,0x0 ; @02430
    and cx,byte +0x7 ; @02432
    jz loc_243D ; @02435
loc_2437:
    shr bx,1 ; @02437
    rcr dl,1 ; @02439
    loop loc_2437 ; @0243B
loc_243D:
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @0243D
    push bx ; @0243F
    push cx ; @02440
    call sub_5EBA ; @02441
    pop ax ; @02444
    pop dx ; @02445
    test dx,bx ; @02446
    jnz loc_2491 ; @02448
    test ax,cx ; @0244A
    jnz loc_2491 ; @0244C
    and word [si+0x8],byte -0x11 ; @0244E
    or word [si+0x8],byte +0x4 ; @02452
    mov word [si+0xa],0x0 ; @02456
    mov word [si+0xc],0xa42 ; @0245B
    mov word [si+0x10],0x5a ; @02460
    mov word [si+0x12],0x3c ; @02465
    mov byte [si+0x28],0x0 ; @0246A
    mov byte [si+0x23],0x3 ; @0246E
    mov word [si+0x4],0xfff8 ; @02472
    mov word [si+0x6],0xfff6 ; @02477
    mov byte [si+0x29],0x4 ; @0247C
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02480
    mov [si+0x14],ax ; @02483
    mov byte [si+0x2a],0x0 ; @02486
    and byte [si+0x24],0x1 ; @0248A
    jmp loc_1FE8 ; @0248E
loc_2491:
    mov ax,[si] ; @02491
    mov bx,[si+0x2] ; @02493
    sub bx,byte +0x10 ; @02496
    shr ax,1 ; @02499
    shr ax,1 ; @0249B
    shr bx,1 ; @0249D
    shr bx,1 ; @0249F
    push ax ; @024A1
    push dx ; @024A2
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @024A3
    mov dx,0x1a0 ; @024A5
    mul dx ; @024A8
    pop dx ; @024AA
    pop bx ; @024AB
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @024AC
    add bx,byte +0x12 ; @024AE
    mov al,[ss:bx] ; @024B1
    and al,0xf ; @024B4
    cmp al,0x9 ; @024B6
    jz loc_24BD ; @024B8
    jmp loc_1FE8 ; @024BA
loc_24BD:
    cmp byte [0x2010],0xff ; @024BD
    jnz loc_24D0 ; @024C2
    test byte [0x25a7],0x3 ; @024C4
    jz loc_24D0 ; @024C9
    mov ax,0x40a ; @024CB
    int 0x61 ; @024CE
loc_24D0:
    mov word [si+0x8],0x0 ; @024D0
    mov word [si+0xa],0x0 ; @024D5
    mov word [si+0xc],0x0 ; @024DA
    mov word [si+0x10],0x5a ; @024DF
    mov word [si+0x12],0x3c ; @024E4
    mov byte [si+0x28],0x0 ; @024E9
    mov word [si+0x4],0xfff8 ; @024ED
    mov word [si+0x6],0xfff6 ; @024F2
    mov byte [si+0x29],0x9 ; @024F7
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @024FB
    mov [si+0x14],ax ; @024FE
    mov byte [si+0x2a],0x0 ; @02501
    and byte [si+0x24],0x1 ; @02505
    jmp loc_1FE8 ; @02509
loc_250C:
    push word [si] ; @0250C
    push word [si+0x2] ; @0250E
    mov ax,[si+0x4] ; @02511
    add [si],ax ; @02514
    sub word [si+0x2],byte +0x2 ; @02516
    call PrepareEntityPixelSample ; @0251A
    mov cx,[si] ; @0251D
    pop word [si+0x2] ; @0251F
    pop word [si] ; @02522
    mov bx,0xff8 ; @02524
    mov dl,0x0 ; @02527
    and cx,byte +0x7 ; @02529
    jz loc_2534 ; @0252C
loc_252E:
    shr bx,1 ; @0252E
    rcr dl,1 ; @02530
    loop loc_252E ; @02532
loc_2534:
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @02534
    push di ; @02536
    push cx ; @02537
    push bx ; @02538
    push bp ; @02539
    call sub_5EBA ; @0253A
    pop bp ; @0253D
    pop bx ; @0253E
    pop cx ; @0253F
    pop di ; @02540
    add di,[0x4] ; @02541
    call sub_5EBA ; @02545
    mov byte [si+0x28],0x0 ; @02548
    jmp loc_240F ; @0254C
loc_254F:
    mov al,[si+0x28] ; @0254F
    inc al ; @02552
    and al,0x7 ; @02554
    mov [si+0x28],al ; @02556
    cmp al,0x3 ; @02559
    jg loc_2560 ; @0255B
    jmp loc_25E1 ; @0255D
loc_2560:
    dec word [si+0x2] ; @02560
    mov ax,[si+0x2] ; @02563
    add ax,[si+0x6] ; @02566
    cmp ax,0xa ; @02569
    jna loc_2591 ; @0256C
    mov bp,[si] ; @0256E
    mov al,[si+0x27] ; @02570
    cbw ; @02573
    sub [si],ax ; @02574
    call PrepareEntityPixelSample ; @02576
    mov [si],bp ; @02579
    mov dx,[0x4] ; @0257B
    shl dx,1 ; @0257F
    shl dx,1 ; @02581
    shl dx,1 ; @02583
    db 0x2b,0xfa ; ENCODED: sub di,dx (NASM chooses a different encoding) ; @02585
    mov al,[es:di] ; @02587
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0258A
    jnz loc_2591 ; @0258C
    jmp loc_1FE8 ; @0258E
loc_2591:
    and word [si+0x8],byte -0x21 ; @02591
    or word [si+0x8],byte +0x4 ; @02595
    mov word [si+0xa],0x0 ; @02599
    mov word [si+0xc],0xa42 ; @0259E
    mov word [si+0x10],0x5a ; @025A3
    mov word [si+0x12],0x3c ; @025A8
    mov byte [si+0x28],0x0 ; @025AD
    mov byte [si+0x23],0x3 ; @025B1
    mov word [si+0x4],0xfff8 ; @025B5
    mov word [si+0x6],0xfff6 ; @025BA
    mov byte [si+0x29],0x4 ; @025BF
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @025C3
    mov [si+0x14],ax ; @025C6
    mov byte [si+0x2a],0x0 ; @025C9
    and byte [si+0x24],0x1 ; @025CD
    mov al,[si+0x27] ; @025D1
    neg al ; @025D4
    mov [si+0x27],al ; @025D6
    cbw ; @025D9
    add [si],ax ; @025DA
    add [si],ax ; @025DC
    jmp loc_1FE8 ; @025DE
loc_25E1:
    mov bp,[si+0x2] ; @025E1
    sub word [si+0x2],byte +0x7 ; @025E4
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @025E8
    sub [si+0x2],ax ; @025EA
    call PrepareEntityPixelSample ; @025ED
    mov [si+0x2],bp ; @025F0
    mov al,[es:di] ; @025F3
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @025F6
    jz loc_25FD ; @025F8
    jmp loc_1FE8 ; @025FA
loc_25FD:
    add word [si+0x2],byte +0x2 ; @025FD
    mov al,[si+0x28] ; @02601
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @02604
    sub [si+0x2],ax ; @02606
    and word [si+0x8],byte -0x21 ; @02609
    or word [si+0x8],byte +0x40 ; @0260D
    mov word [si+0xa],0x0 ; @02611
    mov word [si+0xc],0x6b2 ; @02616
    mov word [si+0x10],0x48 ; @0261B
    mov word [si+0x12],0x30 ; @02620
    mov byte [si+0x28],0x0 ; @02625
    mov byte [si+0x29],0x8 ; @02629
    and byte [si+0x24],0x1 ; @0262D
    mov bp,[si+0x2] ; @02631
    jmp loc_2148 ; @02634
loc_2637:
    mov al,[si+0x28] ; @02637
    inc al ; @0263A
    and al,0x7 ; @0263C
    mov [si+0x28],al ; @0263E
    jz loc_2654 ; @02641
    cmp al,0x5 ; @02643
    jl loc_264A ; @02645
    jmp loc_1FEB ; @02647
loc_264A:
    sub word [si+0x2],byte +0x2 ; @0264A
    mov bp,[si+0x2] ; @0264E
    jmp loc_2148 ; @02651
loc_2654:
    mov word [si+0x8],0x0 ; @02654
    mov word [si+0xa],0x0 ; @02659
    mov word [si+0xc],0x0 ; @0265E
    mov word [si+0x10],0x5a ; @02663
    mov word [si+0x12],0x3c ; @02668
    mov byte [si+0x28],0x0 ; @0266D
    mov word [si+0x4],0xfff8 ; @02671
    mov word [si+0x6],0xfff6 ; @02676
    mov byte [si+0x29],0x9 ; @0267B
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0267F
    mov [si+0x14],ax ; @02682
    mov byte [si+0x2a],0x0 ; @02685
    and byte [si+0x24],0x1 ; @02689
    mov bp,[si+0x2] ; @0268D
    jmp loc_2148 ; @02690
loc_2693:
    mov al,[si+0x28] ; @02693
    inc al ; @02696
    and al,0xf ; @02698
    mov [si+0x28],al ; @0269A
    jnz loc_26A2 ; @0269D
    jmp short loc_26E4 ; @0269F
; UNKNOWN: unresolved bytes
    db 0x90 ; @026A1
loc_26A2:
    cmp al,0xa ; @026A2
    jnz loc_26D7 ; @026A4
    mov al,[si+0x21] ; @026A6
    cmp al,0x3 ; @026A9
    ja loc_26D7 ; @026AB
    push ax ; @026AD
    push es ; @026AE
    cmp byte [0x2010],0xff ; @026AF
    jz loc_26C2 ; @026B4
    test byte [0x25a7],0x1 ; @026B6
    jz loc_26C2 ; @026BB
    mov ax,0x313 ; @026BD
    int 0x60 ; @026C0
loc_26C2:
    cmp byte [0x2010],0xff ; @026C2
    jnz loc_26D5 ; @026C7
    test byte [0x25a7],0x3 ; @026C9
    jz loc_26D5 ; @026CE
    mov ax,0x412 ; @026D0
    int 0x61 ; @026D3
loc_26D5:
    pop es ; @026D5
    pop ax ; @026D6
loc_26D7:
    cmp al,0x9 ; @026D7
    jz loc_26DE ; @026D9
    jmp loc_1FE8 ; @026DB
loc_26DE:
    call sub_5F0F ; @026DE
    jmp loc_1FEB ; @026E1
loc_26E4:
    mov al,[si+0x27] ; @026E4
    cbw ; @026E7
    add [si],ax ; @026E8
    dec word [si+0x2] ; @026EA
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @026ED
    cmp word [si],byte +0x10 ; @026EF
    jg loc_26F7 ; @026F2
    jmp short loc_2763 ; @026F4
; UNKNOWN: unresolved bytes
    db 0x90 ; @026F6
loc_26F7:
    cmp word [si],0x680 ; @026F7
    jl loc_2700 ; @026FB
    jmp short loc_2763 ; @026FD
; UNKNOWN: unresolved bytes
    db 0x90 ; @026FF
loc_2700:
    call PrepareEntityPixelSample ; @02700
    sub di,[0x4] ; @02703
    mov al,[es:di] ; @02707
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0270A
    jnz loc_2763 ; @0270C
    add [si],bp ; @0270E
    call PrepareEntityPixelSample ; @02710
    sub di,[0x4] ; @02713
    mov al,[es:di] ; @02717
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0271A
    jnz loc_2763 ; @0271C
    dec byte [si+0x21] ; @0271E
    jnz loc_2726 ; @02721
    jmp loc_27A5 ; @02723
loc_2726:
    push word [si] ; @02726
    add [si],bp ; @02728
    add [si],bp ; @0272A
    call PrepareEntityPixelSample ; @0272C
    pop word [si] ; @0272F
    push ax ; @02731
    mov ax,[0x4] ; @02732
    db 0x2b,0xf8 ; ENCODED: sub di,ax (NASM chooses a different encoding) ; @02735
    shl ax,1 ; @02737
    shl ax,1 ; @02739
    shl ax,1 ; @0273B
    db 0x2b,0xf8 ; ENCODED: sub di,ax (NASM chooses a different encoding) ; @0273D
    pop ax ; @0273F
    mov al,[es:di] ; @02740
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02743
    jnz loc_2763 ; @02745
    cmp word [si],byte +0x10 ; @02747
    jng loc_2763 ; @0274A
    cmp word [si],0x680 ; @0274C
    jnl loc_2763 ; @02750
    mov ax,[si+0x2] ; @02752
    add ax,[si+0x6] ; @02755
    cmp ax,0xa ; @02758
    jng loc_2760 ; @0275B
    jmp loc_1FE8 ; @0275D
loc_2760:
    jmp short loc_2766 ; @02760
; UNKNOWN: unresolved bytes
    db 0x90 ; @02762
loc_2763:
    neg byte [si+0x27] ; @02763
loc_2766:
    mov word [si+0x8],0x0 ; @02766
    mov word [si+0xa],0x0 ; @0276B
    mov word [si+0xc],0x0 ; @02770
    mov word [si+0x10],0x5a ; @02775
    mov word [si+0x12],0x3c ; @0277A
    mov byte [si+0x28],0x0 ; @0277F
    mov word [si+0x4],0xfff8 ; @02783
    mov word [si+0x6],0xfff6 ; @02788
    mov byte [si+0x29],0x9 ; @0278D
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02791
    mov [si+0x14],ax ; @02794
    mov byte [si+0x2a],0x0 ; @02797
    and byte [si+0x24],0x1 ; @0279B
    mov bp,[si+0x2] ; @0279F
    jmp loc_2148 ; @027A2
loc_27A5:
    mov word [si+0x8],0x0 ; @027A5
    mov word [si+0xa],0x8 ; @027AA
    mov word [si+0xc],0x126b ; @027AF
    mov word [si+0x10],0x5a ; @027B4
    mov word [si+0x12],0x3c ; @027B9
    mov byte [si+0x28],0x0 ; @027BE
    mov word [si+0x4],0xfff8 ; @027C2
    mov word [si+0x6],0xfff6 ; @027C7
    mov byte [si+0x29],0x8 ; @027CC
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @027D0
    mov [si+0x14],ax ; @027D3
    mov byte [si+0x2a],0x0 ; @027D6
    and byte [si+0x24],0x1 ; @027DA
    or byte [si+0x24],0x80 ; @027DE
    mov bp,[si+0x2] ; @027E2
    jmp loc_2148 ; @027E5
loc_27E8:
    inc byte [si+0x28] ; @027E8
    and byte [si+0x28],0xf ; @027EB
    call PrepareEntityPixelSample ; @027EF
    mov al,[es:di] ; @027F2
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @027F5
    jz loc_27FC ; @027F7
    jmp loc_1FEB ; @027F9
loc_27FC:
    mov word [si+0x8],0x0 ; @027FC
    mov word [si+0xa],0x0 ; @02801
    mov word [si+0xc],0x0 ; @02806
    mov word [si+0x10],0x5a ; @0280B
    mov word [si+0x12],0x3c ; @02810
    mov byte [si+0x28],0x0 ; @02815
    mov word [si+0x4],0xfff8 ; @02819
    mov word [si+0x6],0xfff6 ; @0281E
    mov byte [si+0x29],0x9 ; @02823
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02827
    mov [si+0x14],ax ; @0282A
    mov byte [si+0x2a],0x0 ; @0282D
    and byte [si+0x24],0x1 ; @02831
    call CopyEntityPatternToInteractionMap ; @02835
    jmp loc_1FEB ; @02838
; 283B..287C: copy the live record pattern back to the interaction map.
; DS:SI words +0/+2 feed wrapped (x-4)>>2 and (y-6-10h)>>2;
; MUL keeps its low word, map offset = 0012h + qx + 01A0h*qy.
; Producer 3464..34C7 saves old cells at record+16h while installing
; 02/0A/03 rows. Records advance 2Dh at 1FEC; no shadow pattern exists.
; PUSH/POP use live SS:SP: map writes may change restored ES/DI/SI/RET.
; Three MOVSW/MOVSB pairs retain DF and sequential overlap. Each literal
; 019Dh adjustment follows a pair; DF=1 is not a reversed 9-byte copy.
; AX=low product, BX=map offset, DX=live restored save; CX/BP/DS/SS unchanged.
; Last defined arithmetic flags are ADD DI,019Dh at 2873. See entity-pattern.md.
CopyEntityPatternToInteractionMap:
sub_283B:
    mov ax,[si] ; @0283B
    mov bx,[si+0x2] ; @0283D
    sub ax,0x4 ; @02840
    sub bx,byte +0x6 ; @02843
    sub bx,byte +0x10 ; @02846
    shr ax,1 ; @02849
    shr ax,1 ; @0284B
    shr bx,1 ; @0284D
    shr bx,1 ; @0284F
    push ax ; @02851
    push dx ; @02852
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02853
    mov dx,0x1a0 ; @02855
    mul dx ; @02858
    pop dx ; @0285A
    pop bx ; @0285B
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0285C
    add bx,byte +0x12 ; @0285E
    push si ; @02861
    push di ; @02862
    push es ; @02863
    push ss ; @02864
    pop es ; @02865
    db 0x8b,0xfb ; ENCODED: mov di,bx (NASM chooses a different encoding) ; @02866
    add si,byte +0x16 ; @02868
    movsw ; @0286B
    movsb ; @0286C
    add di,0x19d ; @0286D
    movsw ; @02871
    movsb ; @02872
    add di,0x19d ; @02873
    movsw ; @02877
    movsb ; @02878
    pop es ; @02879
    pop di ; @0287A
    pop si ; @0287B
    ret ; @0287C
loc_287D:
    inc byte [si+0x28] ; @0287D
    and byte [si+0x28],0x1f ; @02880
    mov al,[si+0x28] ; @02884
    and al,0xf ; @02887
    cmp al,0xb ; @02889
    jl loc_2890 ; @0288B
    jmp loc_293A ; @0288D
loc_2890:
    cmp al,0x2 ; @02890
    jnl loc_2897 ; @02892
    jmp loc_1FEB ; @02894
loc_2897:
    cmp al,0x5 ; @02897
    jng loc_289E ; @02899
    jmp loc_1FEB ; @0289B
loc_289E:
    sub al,0x2 ; @0289E
    cbw ; @028A0
    call sub_5FAC ; @028A1
    mov al,[si+0x28] ; @028A4
    cmp al,0x5 ; @028A7
    jz loc_28AE ; @028A9
    jmp loc_1FEB ; @028AB
loc_28AE:
    mov cx,[si] ; @028AE
    mov bx,[si+0x2] ; @028B0
    sub bx,byte +0x6 ; @028B3
    mov al,[si+0x27] ; @028B6
    cbw ; @028B9
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @028BA
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @028BC
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @028BE
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @028C0
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @028C2
    call sub_6141 ; @028C4
    mov al,[es:di] ; @028C7
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028CA
    jz loc_28D1 ; @028CC
    jmp loc_1FEB ; @028CE
loc_28D1:
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @028D1
    call sub_6141 ; @028D3
    mov al,[es:di] ; @028D6
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028D9
    jz loc_28E0 ; @028DB
    jmp loc_1FEB ; @028DD
loc_28E0:
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @028E0
    call sub_6141 ; @028E2
    mov al,[es:di] ; @028E5
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028E8
    jz loc_28EF ; @028EA
    jmp loc_1FEB ; @028EC
loc_28EF:
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @028EF
    call sub_6141 ; @028F1
    mov al,[es:di] ; @028F4
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028F7
    jz loc_28FE ; @028F9
    jmp loc_1FEB ; @028FB
loc_28FE:
    mov word [si+0x8],0x0 ; @028FE
    mov word [si+0xa],0x0 ; @02903
    mov word [si+0xc],0x0 ; @02908
    mov word [si+0x10],0x5a ; @0290D
    mov word [si+0x12],0x3c ; @02912
    mov byte [si+0x28],0x0 ; @02917
    mov word [si+0x4],0xfff8 ; @0291B
    mov word [si+0x6],0xfff6 ; @02920
    mov byte [si+0x29],0x9 ; @02925
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02929
    mov [si+0x14],ax ; @0292C
    mov byte [si+0x2a],0x0 ; @0292F
    and byte [si+0x24],0x1 ; @02933
    jmp loc_1FEB ; @02937
loc_293A:
    mov al,[si+0x27] ; @0293A
    cbw ; @0293D
    add [si],ax ; @0293E
    cmp word [si],byte +0x10 ; @02940
    jl loc_29C1 ; @02943
    cmp word [si],0x680 ; @02945
    jnl loc_29C1 ; @02949
    call PrepareEntityPixelSample ; @0294B
    mov al,[es:di] ; @0294E
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02951
    jz loc_2958 ; @02953
    jmp loc_2A00 ; @02955
loc_2958:
    inc word [si+0x2] ; @02958
    add di,[0x4] ; @0295B
    mov al,[es:di] ; @0295F
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02962
    jz loc_2969 ; @02964
    jmp loc_2A00 ; @02966
loc_2969:
    inc word [si+0x2] ; @02969
    add di,[0x4] ; @0296C
    mov al,[es:di] ; @02970
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02973
    jz loc_297A ; @02975
    jmp loc_2A00 ; @02977
loc_297A:
    inc word [si+0x2] ; @0297A
    or word [si+0x8],byte +0x4 ; @0297D
    mov word [si+0xa],0x0 ; @02981
    mov word [si+0xc],0xa42 ; @02986
    mov word [si+0x10],0x5a ; @0298B
    mov word [si+0x12],0x3c ; @02990
    mov byte [si+0x28],0x0 ; @02995
    mov byte [si+0x23],0x3 ; @02999
    mov word [si+0x4],0xfff8 ; @0299D
    mov word [si+0x6],0xfff6 ; @029A2
    mov byte [si+0x29],0x4 ; @029A7
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @029AB
    mov [si+0x14],ax ; @029AE
    mov byte [si+0x2a],0x0 ; @029B1
    and byte [si+0x24],0x1 ; @029B5
    and word [si+0x8],0xfdff ; @029B9
    jmp loc_1FE8 ; @029BE
loc_29C1:
    neg byte [si+0x27] ; @029C1
    mov word [si+0x8],0x0 ; @029C4
    mov word [si+0xa],0x0 ; @029C9
    mov word [si+0xc],0x0 ; @029CE
    mov word [si+0x10],0x5a ; @029D3
    mov word [si+0x12],0x3c ; @029D8
    mov byte [si+0x28],0x0 ; @029DD
    mov word [si+0x4],0xfff8 ; @029E1
    mov word [si+0x6],0xfff6 ; @029E6
    mov byte [si+0x29],0x9 ; @029EB
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @029EF
    mov [si+0x14],ax ; @029F2
    mov byte [si+0x2a],0x0 ; @029F5
    and byte [si+0x24],0x1 ; @029F9
    jmp loc_1FE8 ; @029FD
loc_2A00:
    mov ax,[si] ; @02A00
    mov bx,[si+0x2] ; @02A02
    sub bx,byte +0x10 ; @02A05
    shr ax,1 ; @02A08
    shr ax,1 ; @02A0A
    shr bx,1 ; @02A0C
    shr bx,1 ; @02A0E
    push ax ; @02A10
    push dx ; @02A11
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02A12
    mov dx,0x1a0 ; @02A14
    mul dx ; @02A17
    pop dx ; @02A19
    pop bx ; @02A1A
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02A1B
    add bx,byte +0x12 ; @02A1D
    sub bx,0x340 ; @02A20
    mov al,[si+0x27] ; @02A24
    cbw ; @02A27
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02A28
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02A2A
    mov al,[ss:bx] ; @02A2C
    and al,0xf ; @02A2F
    cmp al,0x9 ; @02A31
    jz loc_2A57 ; @02A33
    cmp al,0x7 ; @02A35
    jnz loc_2A43 ; @02A37
    mov al,[si+0x27] ; @02A39
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02A3C
    jns loc_29C1 ; @02A3E
    jmp loc_1FE8 ; @02A40
loc_2A43:
    cmp al,0x8 ; @02A43
    jz loc_2A4A ; @02A45
    jmp loc_1FE8 ; @02A47
loc_2A4A:
    mov al,[si+0x27] ; @02A4A
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02A4D
    jns loc_2A54 ; @02A4F
    jmp loc_29C1 ; @02A51
loc_2A54:
    jmp loc_1FE8 ; @02A54
loc_2A57:
    cmp byte [0x2010],0xff ; @02A57
    jnz loc_2A6A ; @02A5C
    test byte [0x25a7],0x3 ; @02A5E
    jz loc_2A6A ; @02A63
    mov ax,0x40a ; @02A65
    int 0x61 ; @02A68
loc_2A6A:
    jmp loc_29C1 ; @02A6A
loc_2A6D:
    mov bx,0x2698 ; @02A6D
    add bx,[si+0xe] ; @02A70
    mov al,[bx] ; @02A73
    mov [si+0x28],al ; @02A75
    mov al,[bx+0x1] ; @02A78
    add word [si+0xe],byte +0x2 ; @02A7B
    cbw ; @02A7F
    cmp al,0x3 ; @02A80
    jz loc_2A92 ; @02A82
    cmp al,0x2 ; @02A84
    jz loc_2ABE ; @02A86
    cmp al,0x1 ; @02A88
    jz loc_2ADC ; @02A8A
    add [si+0x2],ax ; @02A8C
    jmp loc_2B28 ; @02A8F
loc_2A92:
    call PrepareEntityPixelSample ; @02A92
    mov al,[es:di] ; @02A95
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02A98
    jnz loc_2AEC ; @02A9A
    inc word [si+0x2] ; @02A9C
    add di,[0x4] ; @02A9F
    mov al,[es:di] ; @02AA3
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AA6
    jnz loc_2AEC ; @02AA8
    inc word [si+0x2] ; @02AAA
    add di,[0x4] ; @02AAD
    mov al,[es:di] ; @02AB1
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AB4
    jnz loc_2AEC ; @02AB6
    inc word [si+0x2] ; @02AB8
    jmp short loc_2B28 ; @02ABB
; UNKNOWN: unresolved bytes
    db 0x90 ; @02ABD
loc_2ABE:
    call PrepareEntityPixelSample ; @02ABE
    mov al,[es:di] ; @02AC1
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AC4
    jnz loc_2AEC ; @02AC6
    inc word [si+0x2] ; @02AC8
    add di,[0x4] ; @02ACB
    mov al,[es:di] ; @02ACF
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AD2
    jnz loc_2AEC ; @02AD4
    inc word [si+0x2] ; @02AD6
    jmp short loc_2B28 ; @02AD9
; UNKNOWN: unresolved bytes
    db 0x90 ; @02ADB
loc_2ADC:
    call PrepareEntityPixelSample ; @02ADC
    mov al,[es:di] ; @02ADF
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AE2
    jnz loc_2AEC ; @02AE4
    inc word [si+0x2] ; @02AE6
    jmp short loc_2B28 ; @02AE9
; UNKNOWN: unresolved bytes
    db 0x90 ; @02AEB
loc_2AEC:
    mov word [si+0x8],0x0 ; @02AEC
    mov word [si+0xa],0x0 ; @02AF1
    mov word [si+0xc],0x0 ; @02AF6
    mov word [si+0x10],0x5a ; @02AFB
    mov word [si+0x12],0x3c ; @02B00
    mov byte [si+0x28],0x0 ; @02B05
    mov word [si+0x4],0xfff8 ; @02B09
    mov word [si+0x6],0xfff6 ; @02B0E
    mov byte [si+0x29],0x9 ; @02B13
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02B17
    mov [si+0x14],ax ; @02B1A
    mov byte [si+0x2a],0x0 ; @02B1D
    and byte [si+0x24],0x1 ; @02B21
    jmp loc_1FE8 ; @02B25
loc_2B28:
    cmp word [si+0x2],0xb4 ; @02B28
    jnl loc_2B32 ; @02B2D
    jmp loc_1FE8 ; @02B2F
loc_2B32:
    jmp loc_20E2 ; @02B32
loc_2B35:
    mov al,[si+0x28] ; @02B35
    inc al ; @02B38
    cmp al,0x18 ; @02B3A
    jnz loc_2B40 ; @02B3C
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @02B3E
loc_2B40:
    mov [si+0x28],al ; @02B40
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02B43
    jnz loc_2B4A ; @02B45
    jmp loc_2BE1 ; @02B47
loc_2B4A:
    cmp al,0xf ; @02B4A
    jnz loc_2B51 ; @02B4C
    jmp short loc_2B66 ; @02B4E
; UNKNOWN: unresolved bytes
    db 0x90 ; @02B50
loc_2B51:
    cmp al,0x3 ; @02B51
    jnz loc_2B58 ; @02B53
    jmp loc_2BF1 ; @02B55
loc_2B58:
    jl loc_2B5D ; @02B58
    jmp loc_1FEB ; @02B5A
loc_2B5D:
    dec al ; @02B5D
    cbw ; @02B5F
    call sub_606B ; @02B60
    jmp loc_1FEB ; @02B63
loc_2B66:
    mov al,[si+0x27] ; @02B66
    cbw ; @02B69
    add [si],ax ; @02B6A
    cmp word [si],byte +0x10 ; @02B6C
    jnl loc_2B74 ; @02B6F
    jmp loc_2CBB ; @02B71
loc_2B74:
    cmp word [si],0x680 ; @02B74
    jl loc_2B7D ; @02B78
    jmp loc_2CBB ; @02B7A
loc_2B7D:
    add [si],ax ; @02B7D
    cmp word [si],byte +0x10 ; @02B7F
    jnl loc_2B87 ; @02B82
    jmp loc_2CBB ; @02B84
loc_2B87:
    cmp word [si],0x680 ; @02B87
    jl loc_2B90 ; @02B8B
    jmp loc_2CBB ; @02B8D
loc_2B90:
    call PrepareEntityPixelSample ; @02B90
    mov al,[es:di] ; @02B93
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02B96
    jz loc_2B9D ; @02B98
    jmp loc_2C76 ; @02B9A
loc_2B9D:
    or word [si+0x8],byte +0x4 ; @02B9D
    mov word [si+0xa],0x0 ; @02BA1
    mov word [si+0xc],0xa42 ; @02BA6
    mov word [si+0x10],0x5a ; @02BAB
    mov word [si+0x12],0x3c ; @02BB0
    mov byte [si+0x28],0x0 ; @02BB5
    mov byte [si+0x23],0x3 ; @02BB9
    mov word [si+0x4],0xfff8 ; @02BBD
    mov word [si+0x6],0xfff6 ; @02BC2
    mov byte [si+0x29],0x4 ; @02BC7
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02BCB
    mov [si+0x14],ax ; @02BCE
    mov byte [si+0x2a],0x0 ; @02BD1
    and byte [si+0x24],0x1 ; @02BD5
    and word [si+0x8],0xf7ff ; @02BD9
    jmp loc_1FE8 ; @02BDE
loc_2BE1:
    inc word [si+0x2] ; @02BE1
    cmp word [si+0x2],0xb4 ; @02BE4
    jl loc_2BEE ; @02BE9
    jmp loc_20E2 ; @02BEB
loc_2BEE:
    jmp loc_1FE8 ; @02BEE
loc_2BF1:
    mov al,[si+0x27] ; @02BF1
    cbw ; @02BF4
    add [si],ax ; @02BF5
    cmp word [si],byte +0x10 ; @02BF7
    jnl loc_2BFF ; @02BFA
    jmp loc_2CBB ; @02BFC
loc_2BFF:
    cmp word [si],0x680 ; @02BFF
    jl loc_2C08 ; @02C03
    jmp loc_2CBB ; @02C05
loc_2C08:
    add [si],ax ; @02C08
    cmp word [si],byte +0x10 ; @02C0A
    jnl loc_2C12 ; @02C0D
    jmp loc_2CBB ; @02C0F
loc_2C12:
    cmp word [si],0x680 ; @02C12
    jl loc_2C1B ; @02C16
    jmp loc_2CBB ; @02C18
loc_2C1B:
    inc word [si+0x2] ; @02C1B
    cmp word [si+0x2],0xb4 ; @02C1E
    jl loc_2C28 ; @02C23
    jmp loc_20E2 ; @02C25
loc_2C28:
    call PrepareEntityPixelSample ; @02C28
    mov al,[es:di] ; @02C2B
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02C2E
    jnz loc_2C76 ; @02C30
    or word [si+0x8],byte +0x4 ; @02C32
    mov word [si+0xa],0x0 ; @02C36
    mov word [si+0xc],0xa42 ; @02C3B
    mov word [si+0x10],0x5a ; @02C40
    mov word [si+0x12],0x3c ; @02C45
    mov byte [si+0x28],0x0 ; @02C4A
    mov byte [si+0x23],0x3 ; @02C4E
    mov word [si+0x4],0xfff8 ; @02C52
    mov word [si+0x6],0xfff6 ; @02C57
    mov byte [si+0x29],0x4 ; @02C5C
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02C60
    mov [si+0x14],ax ; @02C63
    mov byte [si+0x2a],0x0 ; @02C66
    and byte [si+0x24],0x1 ; @02C6A
    and word [si+0x8],0xf7ff ; @02C6E
    jmp loc_1FE8 ; @02C73
loc_2C76:
    mov ax,[si] ; @02C76
    mov bx,[si+0x2] ; @02C78
    sub bx,byte +0x10 ; @02C7B
    shr ax,1 ; @02C7E
    shr ax,1 ; @02C80
    shr bx,1 ; @02C82
    shr bx,1 ; @02C84
    push ax ; @02C86
    push dx ; @02C87
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02C88
    mov dx,0x1a0 ; @02C8A
    mul dx ; @02C8D
    pop dx ; @02C8F
    pop bx ; @02C90
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02C91
    add bx,byte +0x12 ; @02C93
    mov al,[ss:bx] ; @02C96
    and al,0xf ; @02C99
    cmp al,0x9 ; @02C9B
    jz loc_2CFA ; @02C9D
    cmp al,0x7 ; @02C9F
    jnz loc_2CAD ; @02CA1
    mov al,[si+0x27] ; @02CA3
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02CA6
    jns loc_2CBB ; @02CA8
    jmp loc_1FE8 ; @02CAA
loc_2CAD:
    cmp al,0x8 ; @02CAD
    jz loc_2CB4 ; @02CAF
    jmp loc_1FE8 ; @02CB1
loc_2CB4:
    mov al,[si+0x27] ; @02CB4
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02CB7
    jns loc_2CBB ; @02CB9
loc_2CBB:
    neg byte [si+0x27] ; @02CBB
    mov word [si+0x8],0x0 ; @02CBE
    mov word [si+0xa],0x0 ; @02CC3
    mov word [si+0xc],0x0 ; @02CC8
    mov word [si+0x10],0x5a ; @02CCD
    mov word [si+0x12],0x3c ; @02CD2
    mov byte [si+0x28],0x0 ; @02CD7
    mov word [si+0x4],0xfff8 ; @02CDB
    mov word [si+0x6],0xfff6 ; @02CE0
    mov byte [si+0x29],0x9 ; @02CE5
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02CE9
    mov [si+0x14],ax ; @02CEC
    mov byte [si+0x2a],0x0 ; @02CEF
    and byte [si+0x24],0x1 ; @02CF3
    jmp loc_1FE8 ; @02CF7
loc_2CFA:
    cmp byte [0x2010],0xff ; @02CFA
    jnz loc_2D0D ; @02CFF
    test byte [0x25a7],0x3 ; @02D01
    jz loc_2D0D ; @02D06
    mov ax,0x40a ; @02D08
    int 0x61 ; @02D0B
loc_2D0D:
    jmp short loc_2CBB ; @02D0D
loc_2D0F:
    mov al,[si+0x28] ; @02D0F
    inc al ; @02D12
    and al,0xf ; @02D14
    mov [si+0x28],al ; @02D16
    jnz loc_2D78 ; @02D19
    or word [si+0x8],byte +0x2 ; @02D1B
    mov word [si+0xa],0x8 ; @02D1F
    mov word [si+0xc],0x180b ; @02D24
    mov word [si+0x10],0x280 ; @02D29
    mov word [si+0x12],0x1e0 ; @02D2E
    mov byte [si+0x28],0x0 ; @02D33
    mov word [si+0x6],0xffe7 ; @02D37
    mov word [si+0x4],0xfff0 ; @02D3C
    mov byte [si+0x29],0x0 ; @02D41
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @02D45
    mov [si+0x14],ax ; @02D48
    mov byte [si+0x2a],0x0 ; @02D4B
    mov byte [si+0x22],0xf ; @02D4F
    and byte [si+0x24],0x1 ; @02D53
    cmp byte [0x2010],0xff ; @02D57
    jnz loc_2D6A ; @02D5C
    test byte [0x25a7],0x3 ; @02D5E
    jz loc_2D6A ; @02D63
    mov ax,0x40c ; @02D65
    int 0x61 ; @02D68
loc_2D6A:
    test word [si+0x8],0x4 ; @02D6A
    jz loc_2D75 ; @02D6F
    mov byte [si+0x22],0x0 ; @02D71
loc_2D75:
    jmp loc_1FEB ; @02D75
loc_2D78:
    cmp al,0x5 ; @02D78
    jnz loc_2D83 ; @02D7A
    cmp byte [0x4b],0xff ; @02D7C
    jnz loc_2D83 ; @02D81
loc_2D83:
    call PrepareEntityPixelSample ; @02D83
    mov bp,[si+0x2] ; @02D86
    mov al,[es:di] ; @02D89
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02D8C
    jz loc_2D93 ; @02D8E
    jmp loc_20D6 ; @02D90
loc_2D93:
    inc bp ; @02D93
    add di,[0x4] ; @02D94
    mov al,[es:di] ; @02D98
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02D9B
    jz loc_2DA2 ; @02D9D
    jmp loc_20D6 ; @02D9F
loc_2DA2:
    inc bp ; @02DA2
    add di,[0x4] ; @02DA3
    mov al,[es:di] ; @02DA7
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02DAA
    jz loc_2DB1 ; @02DAC
    jmp loc_20D6 ; @02DAE
loc_2DB1:
    inc bp ; @02DB1
    jmp loc_20D6 ; @02DB2
loc_2DB5:
    mov al,[si+0x28] ; @02DB5
    inc al ; @02DB8
    and al,0x7 ; @02DBA
    mov [si+0x28],al ; @02DBC
    jz loc_2DC4 ; @02DBF
    jmp loc_1FEB ; @02DC1
loc_2DC4:
    mov word [si+0x8],0x0 ; @02DC4
    mov word [si+0xa],0x0 ; @02DC9
    mov word [si+0xc],0x0 ; @02DCE
    mov word [si+0x10],0x5a ; @02DD3
    mov word [si+0x12],0x3c ; @02DD8
    mov byte [si+0x28],0x0 ; @02DDD
    mov word [si+0x4],0xfff8 ; @02DE1
    mov word [si+0x6],0xfff6 ; @02DE6
    mov byte [si+0x29],0x9 ; @02DEB
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02DEF
    mov [si+0x14],ax ; @02DF2
    mov byte [si+0x2a],0x0 ; @02DF5
    and byte [si+0x24],0x1 ; @02DF9
    and byte [si+0x24],0x7f ; @02DFD
    jmp loc_1FE8 ; @02E01
sub_2E04:
    mov al,0x1 ; @02E04
    dec byte [si+0x20] ; @02E06
    jnz loc_2E60 ; @02E09
    test word [si+0x8],0x5404 ; @02E0B
    jnz loc_2E63 ; @02E10
    or word [si+0x8],0x8000 ; @02E12
    mov word [si+0xa],0x8 ; @02E17
    mov word [si+0xc],0x153b ; @02E1C
    mov word [si+0x10],0x5a ; @02E21
    mov word [si+0x12],0x3c ; @02E26
    mov byte [si+0x28],0x0 ; @02E2B
    mov word [si+0x4],0xfff8 ; @02E2F
    mov word [si+0x6],0xfff6 ; @02E34
    mov byte [si+0x29],0x0 ; @02E39
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02E3D
    mov [si+0x14],ax ; @02E40
    mov byte [si+0x2a],0x0 ; @02E43
    and byte [si+0x24],0x1 ; @02E47
    cmp byte [0x2010],0xff ; @02E4B
    jnz loc_2E5E ; @02E50
    test byte [0x25a7],0x3 ; @02E52
    jz loc_2E5E ; @02E57
    mov ax,0x405 ; @02E59
    int 0x61 ; @02E5C
loc_2E5E:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @02E5E
loc_2E60:
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02E60
    ret ; @02E62
loc_2E63:
    or word [si+0x8],byte +0x2 ; @02E63
    mov word [si+0xa],0x8 ; @02E67
    mov word [si+0xc],0x180b ; @02E6C
    mov word [si+0x10],0x280 ; @02E71
    mov word [si+0x12],0x1e0 ; @02E76
    mov byte [si+0x28],0x0 ; @02E7B
    mov word [si+0x6],0xffe7 ; @02E7F
    mov word [si+0x4],0xfff0 ; @02E84
    mov byte [si+0x29],0x0 ; @02E89
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @02E8D
    mov [si+0x14],ax ; @02E90
    mov byte [si+0x2a],0x0 ; @02E93
    mov byte [si+0x22],0xf ; @02E97
    and byte [si+0x24],0x1 ; @02E9B
    cmp byte [0x2010],0xff ; @02E9F
    jnz loc_2EB2 ; @02EA4
    test byte [0x25a7],0x3 ; @02EA6
    jz loc_2EB2 ; @02EAB
    mov ax,0x40c ; @02EAD
    int 0x61 ; @02EB0
loc_2EB2:
    test word [si+0x8],0x4 ; @02EB2
    jz loc_2EBD ; @02EB7
    mov byte [si+0x22],0x0 ; @02EB9
loc_2EBD:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @02EBD
    ret ; @02EBF
sub_2EC0:
    mov ax,[si] ; @02EC0
    mov bx,[si+0x2] ; @02EC2
    cmp bx,0xb0 ; @02EC5
    jnl loc_2F3A ; @02EC9
    sub bx,byte +0x10 ; @02ECB
    shr ax,1 ; @02ECE
    shr ax,1 ; @02ED0
    shr bx,1 ; @02ED2
    shr bx,1 ; @02ED4
    push ax ; @02ED6
    push dx ; @02ED7
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02ED8
    mov dx,0x1a0 ; @02EDA
    mul dx ; @02EDD
    pop dx ; @02EDF
    pop bx ; @02EE0
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02EE1
    add bx,byte +0x12 ; @02EE3
    mov al,[ss:bx] ; @02EE6
    push ax ; @02EE9
    mov [si+0x2c],al ; @02EEA
    mov al,[si+0x27] ; @02EED
    cbw ; @02EF0
    sub bx,0x340 ; @02EF1
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02EF5
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02EF7
    mov al,[ss:bx] ; @02EF9
    mov [si+0x2b],al ; @02EFC
    pop ax ; @02EFF
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @02F00
    and al,0xf ; @02F02
    shr ah,1 ; @02F04
    shr ah,1 ; @02F06
    shr ah,1 ; @02F08
    shr ah,1 ; @02F0A
    and ah,0xf ; @02F0C
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02F0F
    jz loc_2F3A ; @02F11
    dec al ; @02F13
    jz loc_2F3B ; @02F15
    dec al ; @02F17
    jnz loc_2F1E ; @02F19
    jmp loc_2FA2 ; @02F1B
loc_2F1E:
    dec al ; @02F1E
    jnz loc_2F25 ; @02F20
    jmp loc_2FAC ; @02F22
loc_2F25:
    dec al ; @02F25
    jnz loc_2F2C ; @02F27
    jmp loc_2FB6 ; @02F29
loc_2F2C:
    dec al ; @02F2C
    jnz loc_2F33 ; @02F2E
    jmp loc_2FF8 ; @02F30
loc_2F33:
    dec al ; @02F33
    jnz loc_2F3A ; @02F35
    jmp loc_304F ; @02F37
loc_2F3A:
    ret ; @02F3A
loc_2F3B:
    test word [si+0x8],0x4 ; @02F3B
    jnz loc_2F3A ; @02F40
    mov word [si+0x8],0x2000 ; @02F42
    mov word [si+0xa],0x0 ; @02F47
    mov word [si+0xc],0xefa ; @02F4C
    mov word [si+0x10],0x4e ; @02F51
    mov word [si+0x12],0x34 ; @02F56
    mov byte [si+0x28],0x0 ; @02F5B
    mov word [si+0x4],0xfff8 ; @02F5F
    mov word [si+0x6],0xfff3 ; @02F64
    mov byte [si+0x29],0x0 ; @02F69
    mov ax,[DrawingCallbackSlots-GameDataImage+0x4] ; @02F6D
    mov [si+0x14],ax ; @02F70
    mov byte [si+0x2a],0xff ; @02F73
    and byte [si+0x24],0x1 ; @02F77
    cmp byte [0x2010],0xff ; @02F7B
    jz loc_2F8E ; @02F80
    test byte [0x25a7],0x1 ; @02F82
    jz loc_2F8E ; @02F87
    mov ax,0x302 ; @02F89
    int 0x60 ; @02F8C
loc_2F8E:
    cmp byte [0x2010],0xff ; @02F8E
    jnz loc_2FA1 ; @02F93
    test byte [0x25a7],0x3 ; @02F95
    jz loc_2FA1 ; @02F9A
    mov ax,0x410 ; @02F9C
    int 0x61 ; @02F9F
loc_2FA1:
    ret ; @02FA1
loc_2FA2:
    cmp byte [si+0x27],0xff ; @02FA2
    jz loc_2F3A ; @02FA6
    neg byte [si+0x27] ; @02FA8
    ret ; @02FAB
loc_2FAC:
    cmp byte [si+0x27],0x1 ; @02FAC
    jz loc_2F3A ; @02FB0
    neg byte [si+0x27] ; @02FB2
    ret ; @02FB5
loc_2FB6:
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @02FB6
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @02FB8
    mov dx,0x1c ; @02FBA
    mul dx ; @02FBD
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @02FBF
    add di,LevelObjectGraphicsRecords-GameDataImage ; @02FC1
    test word [di],0x2 ; @02FC5
    jz loc_2FCE ; @02FC9
    jmp loc_2F3A ; @02FCB
loc_2FCE:
    or word [di],byte +0x2 ; @02FCE
    mov byte [si+0x26],0xff ; @02FD1
    cmp byte [0x2010],0xff ; @02FD5
    jz loc_2FDF ; @02FDA
    jmp loc_2F3A ; @02FDC
loc_2FDF:
    test byte [0x25a7],0x3 ; @02FDF
    jnz loc_2FE9 ; @02FE4
    jmp loc_2F3A ; @02FE6
loc_2FE9:
    mov al,[di+0x1b] ; @02FE9
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02FEC
    jnz loc_2FF3 ; @02FEE
    jmp loc_2F3A ; @02FF0
loc_2FF3:
    mov ah,0x4 ; @02FF3
    int 0x61 ; @02FF5
    ret ; @02FF7
loc_2FF8:
    test word [si+0x8],0x1000 ; @02FF8
    jz loc_3002 ; @02FFD
    jmp loc_2F3A ; @02FFF
loc_3002:
    mov word [si+0x8],0x1000 ; @03002
    mov word [si+0xa],0x0 ; @03007
    mov word [si+0xc],0x3e2 ; @0300C
    mov word [si+0x10],0x5a ; @03011
    mov word [si+0x12],0x3c ; @03016
    mov byte [si+0x28],0x0 ; @0301B
    mov word [si+0x4],0xfff8 ; @0301F
    mov word [si+0x6],0xfff6 ; @03024
    mov byte [si+0x29],0x0 ; @03029
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0302D
    mov [si+0x14],ax ; @03030
    mov byte [si+0x2a],0x0 ; @03033
    and byte [si+0x24],0x1 ; @03037
    cmp byte [0x2010],0xff ; @0303B
    jnz loc_304E ; @03040
    test byte [0x25a7],0x3 ; @03042
    jz loc_304E ; @03047
    mov ax,0x411 ; @03049
    int 0x61 ; @0304C
loc_304E:
    ret ; @0304E
loc_304F:
    test word [si+0x8],0x4000 ; @0304F
    jz loc_3059 ; @03054
    jmp loc_2F3A ; @03056
loc_3059:
    mov word [si+0x8],0x4000 ; @03059
    mov word [si+0xa],0x0 ; @0305E
    mov word [si+0xc],0xf21 ; @03063
    mov word [si+0x10],0x8c ; @03068
    mov word [si+0x12],0x70 ; @0306D
    mov byte [si+0x28],0x0 ; @03072
    mov word [si+0x4],0xfff8 ; @03076
    mov word [si+0x6],0xfff2 ; @0307B
    mov byte [si+0x29],0x0 ; @03080
    mov ax,[DrawingCallbackSlots-GameDataImage+0x10] ; @03084
    mov [si+0x14],ax ; @03087
    mov byte [si+0x2a],0xff ; @0308A
    and byte [si+0x24],0x1 ; @0308E
    cmp byte [0x2010],0xff ; @03092
    jnz loc_30A5 ; @03097
    test byte [0x25a7],0x3 ; @03099
    jz loc_30A5 ; @0309E
    mov ax,0x40d ; @030A0
    int 0x61 ; @030A3
loc_30A5:
    ret ; @030A5
sub_30A6:
    cmp byte [0x2b],0xff ; @030A6
    jnz loc_30B0 ; @030AB
    jmp loc_314F ; @030AD
loc_30B0:
    cmp byte [0x55],0xff ; @030B0
    jz loc_30BA ; @030B5
    jmp loc_314F ; @030B7
loc_30BA:
    dec byte [0x48] ; @030BA
    jz loc_30C3 ; @030BE
    jmp loc_314F ; @030C0
loc_30C3:
    mov al,[0x49] ; @030C3
    mov [0x48],al ; @030C6
    mov si,0x88 ; @030C9
    mov al,[0x47] ; @030CC
    mov ah,[0x43] ; @030CF
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @030D3
    jz loc_314F ; @030D5
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM chooses a different encoding) ; @030D7
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @030D9
    and bx,byte +0x3 ; @030DB
    shl bx,1 ; @030DE
    shl bx,1 ; @030E0
    add bx,TypeOneObjectCoordinates-GameDataImage ; @030E2
    mov cl,0x2d ; @030E6
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @030E8
    mul cl ; @030EA
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @030EC
    mov cx,0x2d ; @030EE
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @030F1
loc_30F3:
    mov byte [di],0x0 ; @030F3
    inc di ; @030F6
    loop loc_30F3 ; @030F7
    mov ax,[bx] ; @030F9
    mov [si],ax ; @030FB
    mov ax,[bx+0x2] ; @030FD
    mov [si+0x2],ax ; @03100
    mov byte [si+0x27],0x1 ; @03103
    mov byte [si+0x25],0x0 ; @03107
    and byte [si+0x24],0x1 ; @0310B
    or word [si+0x8],byte +0x4 ; @0310F
    mov word [si+0xa],0x0 ; @03113
    mov word [si+0xc],0xa42 ; @03118
    mov word [si+0x10],0x5a ; @0311D
    mov word [si+0x12],0x3c ; @03122
    mov byte [si+0x28],0x0 ; @03127
    mov byte [si+0x23],0x3 ; @0312B
    mov word [si+0x4],0xfff8 ; @0312F
    mov word [si+0x6],0xfff6 ; @03134
    mov byte [si+0x29],0x4 ; @03139
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0313D
    mov [si+0x14],ax ; @03140
    mov byte [si+0x2a],0x0 ; @03143
    and byte [si+0x24],0x1 ; @03147
    inc byte [0x43] ; @0314B
loc_314F:
    ret ; @0314F
sub_3150:
    cmp byte [0x2b],0xff ; @03150
    jz loc_31BD ; @03155
    cmp byte [0x50],0xff ; @03157
    jnz loc_3161 ; @0315C
    jmp short loc_31BD ; @0315E
; UNKNOWN: unresolved bytes
    db 0x90 ; @03160
loc_3161:
    cmp byte [0x63],0x0 ; @03161
    jz loc_31BD ; @03166
    mov ax,[InputButtonsWord-GameDataImage] ; @03168
    and ax,0x1 ; @0316B
    jz loc_31BE ; @0316E
    cmp byte [0x61],0xff ; @03170
    jz loc_31BD ; @03175
    mov byte [0x61],0xff ; @03177
    mov si,[0x58] ; @0317C
    mov al,[0x82] ; @03180
    cmp al,0x2 ; @03183
    jl loc_31BD ; @03185
    jnz loc_318C ; @03187
    jmp loc_329B ; @03189
loc_318C:
    cmp al,0x3 ; @0318C
    jnz loc_3193 ; @0318E
    jmp loc_3557 ; @03190
loc_3193:
    cmp al,0x4 ; @03193
    jnz loc_319A ; @03195
    jmp short loc_31C4 ; @03197
; UNKNOWN: unresolved bytes
    db 0x90 ; @03199
loc_319A:
    cmp al,0x5 ; @0319A
    jnz loc_31A1 ; @0319C
    jmp loc_3336 ; @0319E
loc_31A1:
    cmp al,0x6 ; @031A1
    jnz loc_31A8 ; @031A3
    jmp loc_32BD ; @031A5
loc_31A8:
    cmp al,0x7 ; @031A8
    jnz loc_31AF ; @031AA
    jmp loc_34CE ; @031AC
loc_31AF:
    cmp al,0x8 ; @031AF
    jnz loc_31B6 ; @031B1
    jmp loc_3598 ; @031B3
loc_31B6:
    cmp al,0x9 ; @031B6
    jnz loc_31BD ; @031B8
    jmp short loc_320D ; @031BA
; UNKNOWN: unresolved bytes
    db 0x90 ; @031BC
loc_31BD:
    ret ; @031BD
loc_31BE:
    mov byte [0x61],0x0 ; @031BE
    ret ; @031C3
loc_31C4:
    cmp byte [0x70],0x0 ; @031C4
    jz loc_320C ; @031C9
    cmp byte [si+0x20],0x0 ; @031CB
    jnz loc_320C ; @031CF
    test word [si+0x8],0xc003 ; @031D1
    jnz loc_320C ; @031D6
    dec byte [0x70] ; @031D8
    mov byte [0x72],0x0 ; @031DC
    mov byte [si+0x20],0x4f ; @031E1
loc_31E5:
    cmp byte [0x2010],0xff ; @031E5
    jz loc_31F8 ; @031EA
    test byte [0x25a7],0x1 ; @031EC
    jz loc_31F8 ; @031F1
    mov ax,0x313 ; @031F3
    int 0x60 ; @031F6
loc_31F8:
    cmp byte [0x2010],0xff ; @031F8
    jnz loc_320B ; @031FD
    test byte [0x25a7],0x3 ; @031FF
    jz loc_320B ; @03204
    mov ax,0x404 ; @03206
    int 0x61 ; @03209
loc_320B:
    ret ; @0320B
loc_320C:
    ret ; @0320C
loc_320D:
    cmp byte [0x7f],0x0 ; @0320D
    jz loc_3285 ; @03212
    mov al,[si+0x2c] ; @03214
    and al,0xf ; @03217
    cmp al,0x9 ; @03219
    jz loc_3285 ; @0321B
    test word [si+0x8],0xf57f ; @0321D
    jnz loc_3271 ; @03222
loc_3224:
    dec byte [0x7f] ; @03224
    mov byte [0x81],0x0 ; @03228
    and word [si+0x8],0xf57f ; @0322D
    or word [si+0x8],byte +0x10 ; @03232
    mov word [si+0xa],0x0 ; @03236
    mov word [si+0xc],0x32a ; @0323B
    mov word [si+0x10],0x70 ; @03240
    mov word [si+0x12],0x54 ; @03245
    mov byte [si+0x28],0x11 ; @0324A
    mov word [si+0x4],0xfff8 ; @0324E
    mov word [si+0x6],0xfff4 ; @03253
    mov byte [si+0x29],0x0 ; @03258
    mov ax,[DrawingCallbackSlots-GameDataImage+0xa] ; @0325C
    mov [si+0x14],ax ; @0325F
    mov byte [si+0x1f],0x8 ; @03262
    mov byte [si+0x2a],0xff ; @03266
    and byte [si+0x24],0x1 ; @0326A
    jmp loc_31E5 ; @0326E
loc_3271:
    cmp byte [0x5f],0xff ; @03271
    jz loc_3285 ; @03276
    mov si,[0x5a] ; @03278
    test word [si+0x8],0xf57f ; @0327C
    jnz loc_3285 ; @03281
    jmp short loc_3224 ; @03283
loc_3285:
    jmp short loc_320C ; @03285
loc_3287:
    cmp byte [0x2010],0xff ; @03287
    jnz loc_329A ; @0328C
    test byte [0x25a7],0x3 ; @0328E
    jz loc_329A ; @03293
    mov ax,0x412 ; @03295
    int 0x61 ; @03298
loc_329A:
    ret ; @0329A
loc_329B:
    cmp byte [0x6a],0x0 ; @0329B
    jz loc_32BA ; @032A0
    test byte [si+0x24],0x1 ; @032A2
    jnz loc_32BA ; @032A6
    test word [si+0x8],0x103 ; @032A8
    jnz loc_32BA ; @032AD
    dec byte [0x6a] ; @032AF
    mov byte [si+0x24],0x1 ; @032B3
    jmp loc_31E5 ; @032B7
loc_32BA:
    jmp loc_320C ; @032BA
loc_32BD:
    cmp byte [0x76],0x0 ; @032BD
    jz loc_331F ; @032C2
    mov ax,[si+0x2] ; @032C4
    add ax,[si+0x6] ; @032C7
    cmp ax,0xa ; @032CA
    jna loc_331F ; @032CD
    test word [si+0x8],0xf5ef ; @032CF
    jnz loc_3322 ; @032D4
loc_32D6:
    dec byte [0x76] ; @032D6
    mov byte [0x78],0x0 ; @032DA
    mov word [si+0x8],0x80 ; @032DF
    mov word [si+0x4],0xfff8 ; @032E4
    mov word [si+0x6],0xfff3 ; @032E9
    mov byte [si+0x28],0x0 ; @032EE
    mov byte [si+0x21],0xc ; @032F2
    mov word [si+0xa],0x0 ; @032F6
    mov word [si+0xc],0x6fa ; @032FB
    mov word [si+0x10],0x68 ; @03300
    mov word [si+0x12],0x4e ; @03305
    mov byte [si+0x29],0x10 ; @0330A
    mov ax,[DrawingCallbackSlots-GameDataImage+0x8] ; @0330E
    mov byte [si+0x2a],0xff ; @03311
    mov [si+0x14],ax ; @03315
    and byte [si+0x24],0x1 ; @03318
    jmp loc_31E5 ; @0331C
loc_331F:
    jmp loc_320C ; @0331F
loc_3322:
    cmp byte [0x5f],0xff ; @03322
    jz loc_331F ; @03327
    mov si,[0x5a] ; @03329
    test word [si+0x8],0xf5ef ; @0332D
    jnz loc_331F ; @03332
    jmp short loc_32D6 ; @03334
loc_3336:
    cmp byte [0x73],0x0 ; @03336
    jz loc_3345 ; @0333B
    mov ax,[si+0x8] ; @0333D
    and ax,0xf56f ; @03340
    jz loc_3348 ; @03343
loc_3345:
    jmp loc_320C ; @03345
loc_3348:
    mov ax,[si] ; @03348
    mov bx,[si+0x2] ; @0334A
    sub ax,0x4 ; @0334D
    sub bx,byte +0x6 ; @03350
    sub bx,byte +0x10 ; @03353
    shr ax,1 ; @03356
    shr ax,1 ; @03358
    shr bx,1 ; @0335A
    shr bx,1 ; @0335C
    push ax ; @0335E
    push dx ; @0335F
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @03360
    mov dx,0x1a0 ; @03362
    mul dx ; @03365
    pop dx ; @03367
    pop bx ; @03368
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @03369
    add bx,byte +0x12 ; @0336B
    mov ax,[ss:bx] ; @0336E
    cmp al,0x2 ; @03371
    jz loc_3345 ; @03373
    cmp al,0xa ; @03375
    jz loc_3345 ; @03377
    cmp al,0x3 ; @03379
    jz loc_3345 ; @0337B
    cmp ah,0x2 ; @0337D
    jz loc_3345 ; @03380
    cmp ah,0xa ; @03382
    jz loc_3345 ; @03385
    cmp ah,0x3 ; @03387
    jz loc_3345 ; @0338A
    mov al,[ss:bx+0x2] ; @0338C
    cmp al,0x2 ; @03390
    jz loc_3345 ; @03392
    cmp al,0xa ; @03394
    jz loc_3345 ; @03396
    cmp al,0x3 ; @03398
    jz loc_3345 ; @0339A
    mov ax,[ss:bx+0x1a0] ; @0339C
    cmp al,0x2 ; @033A1
    jz loc_3345 ; @033A3
    cmp al,0xa ; @033A5
    jz loc_3345 ; @033A7
    cmp al,0x3 ; @033A9
    jz loc_3345 ; @033AB
    cmp ah,0x2 ; @033AD
    jz loc_3345 ; @033B0
    cmp ah,0xa ; @033B2
    jz loc_3345 ; @033B5
    cmp ah,0x3 ; @033B7
    jz loc_3345 ; @033BA
    mov al,[ss:bx+0x1a2] ; @033BC
    cmp al,0x2 ; @033C1
    jnz loc_33C8 ; @033C3
    jmp loc_3345 ; @033C5
loc_33C8:
    cmp al,0xa ; @033C8
    jnz loc_33CF ; @033CA
    jmp loc_34CB ; @033CC
loc_33CF:
    cmp al,0x3 ; @033CF
    jnz loc_33D6 ; @033D1
    jmp loc_34CB ; @033D3
loc_33D6:
    mov ax,[ss:bx+0x340] ; @033D6
    cmp al,0x2 ; @033DB
    jnz loc_33E2 ; @033DD
    jmp loc_34CB ; @033DF
loc_33E2:
    cmp al,0xa ; @033E2
    jnz loc_33E9 ; @033E4
    jmp loc_34CB ; @033E6
loc_33E9:
    cmp al,0x3 ; @033E9
    jnz loc_33F0 ; @033EB
    jmp loc_34CB ; @033ED
loc_33F0:
    cmp ah,0x2 ; @033F0
    jnz loc_33F8 ; @033F3
    jmp loc_34CB ; @033F5
loc_33F8:
    cmp ah,0xa ; @033F8
    jnz loc_3400 ; @033FB
    jmp loc_34CB ; @033FD
loc_3400:
    cmp ah,0x3 ; @03400
    jnz loc_3408 ; @03403
    jmp loc_34CB ; @03405
loc_3408:
    mov al,[ss:bx+0x342] ; @03408
    cmp al,0x2 ; @0340D
    jnz loc_3414 ; @0340F
    jmp loc_34CB ; @03411
loc_3414:
    cmp al,0xa ; @03414
    jnz loc_341B ; @03416
    jmp loc_34CB ; @03418
loc_341B:
    cmp al,0x3 ; @0341B
    jnz loc_3422 ; @0341D
    jmp loc_34CB ; @0341F
loc_3422:
    dec byte [0x73] ; @03422
    mov byte [0x75],0x0 ; @03426
    mov word [si+0x8],0x100 ; @0342B
    mov byte [si+0x28],0x0 ; @03430
    mov word [si+0xa],0x8 ; @03434
    mov word [si+0xc],0xf9b ; @03439
    mov word [si+0x10],0x5a ; @0343E
    mov word [si+0x12],0x3c ; @03443
    mov byte [si+0x29],0x0 ; @03448
    mov word [si+0x4],0xfff8 ; @0344C
    mov word [si+0x6],0xfff6 ; @03451
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @03456
    mov [si+0x14],ax ; @03459
    mov byte [si+0x2a],0x0 ; @0345C
    and byte [si+0x24],0x1 ; @03460
; Save replaced interaction cells in this live record. BX is the candidate
; SS map offset checked at 3348..341F; ES becomes DS for STOSB below.
; DF=0 saves nine bytes at +16h..+1Eh; DF=1 decrements only the destination
; while explicit INC SI still scans map rows forwards. Restore is 283B.
    push si ; @03464
    push ds ; @03465
    pop es ; @03466
    db 0x8b,0xfb ; ENCODED: mov di,bx (NASM chooses a different encoding) ; @03467
    add si,byte +0x16 ; @03469
    xchg si,di ; @0346C
    mov al,[ss:si] ; @0346E
    mov byte [ss:si],0x2 ; @03471
    inc si ; @03475
    stosb ; @03476
    mov al,[ss:si] ; @03477
    mov byte [ss:si],0xa ; @0347A
    inc si ; @0347E
    stosb ; @0347F
    mov al,[ss:si] ; @03480
    mov byte [ss:si],0x3 ; @03483
    inc si ; @03487
    stosb ; @03488
    add si,0x19d ; @03489
    mov al,[ss:si] ; @0348D
    mov byte [ss:si],0x2 ; @03490
    inc si ; @03494
    stosb ; @03495
    mov al,[ss:si] ; @03496
    mov byte [ss:si],0xa ; @03499
    inc si ; @0349D
    stosb ; @0349E
    mov al,[ss:si] ; @0349F
    mov byte [ss:si],0x3 ; @034A2
    inc si ; @034A6
    stosb ; @034A7
    add si,0x19d ; @034A8
    mov al,[ss:si] ; @034AC
    mov byte [ss:si],0x2 ; @034AF
    inc si ; @034B3
    stosb ; @034B4
    mov al,[ss:si] ; @034B5
    mov byte [ss:si],0xa ; @034B8
    inc si ; @034BC
    stosb ; @034BD
    mov al,[ss:si] ; @034BE
    mov byte [ss:si],0x3 ; @034C1
    inc si ; @034C5
    stosb ; @034C6
    pop si ; @034C7
    jmp loc_31E5 ; @034C8
loc_34CB:
    jmp loc_320C ; @034CB
loc_34CE:
    cmp byte [0x79],0x0 ; @034CE
    jz loc_3540 ; @034D3
    test word [si+0x8],0xf76f ; @034D5
    jnz loc_3543 ; @034DA
loc_34DC:
    mov al,[si+0x2b] ; @034DC
    and al,0xf ; @034DF
    mov ah,0x7 ; @034E1
    cmp byte [si+0x27],0x1 ; @034E3
    jz loc_34EB ; @034E7
    mov ah,0x8 ; @034E9
loc_34EB:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @034EB
    jz loc_3540 ; @034ED
    cmp al,0x9 ; @034EF
    jnz loc_34F6 ; @034F1
    jmp loc_3287 ; @034F3
loc_34F6:
    dec byte [0x79] ; @034F6
    mov byte [0x7b],0x0 ; @034FA
    and word [si+0x8],0xf56f ; @034FF
    or word [si+0x8],0x200 ; @03504
    mov word [si+0x4],0xfff8 ; @03509
    mov word [si+0x6],0xfff6 ; @0350E
    mov byte [si+0x28],0x0 ; @03513
    mov word [si+0xa],0x0 ; @03517
    mov word [si+0xc],0x7ca ; @0351C
    mov word [si+0x10],0x50 ; @03521
    mov word [si+0x12],0x3c ; @03526
    mov byte [si+0x29],0x20 ; @0352B
    mov byte [si+0x2a],0xff ; @0352F
    mov ax,[DrawingCallbackSlots-GameDataImage+0x6] ; @03533
    mov [si+0x14],ax ; @03536
    and byte [si+0x24],0x1 ; @03539
    jmp loc_31E5 ; @0353D
loc_3540:
    jmp loc_320C ; @03540
loc_3543:
    cmp byte [0x5f],0xff ; @03543
    jz loc_3540 ; @03548
    mov si,[0x5a] ; @0354A
    test word [si+0x8],0xf76f ; @0354E
    jnz loc_3540 ; @03553
    jmp short loc_34DC ; @03555
loc_3557:
    cmp byte [0x6d],0x0 ; @03557
    jz loc_357B ; @0355C
    cmp byte [si+0x25],0x0 ; @0355E
    jnz loc_357B ; @03562
    test word [si+0x8],0x103 ; @03564
    jnz loc_357B ; @03569
    mov byte [si+0x25],0xff ; @0356B
    dec byte [0x6d] ; @0356F
    mov byte [0x6f],0x0 ; @03573
    jmp loc_31E5 ; @03578
loc_357B:
    jmp loc_320C ; @0357B
; UNKNOWN: unresolved bytes
    db 0x80,0x3e,0x5f,0x00,0xff,0x74,0xf6,0x8b,0x36,0x5a,0x00,0x80,0x7c,0x25,0x00,0x75 ; @0357E
; UNKNOWN: unresolved bytes
    db 0xec,0xf7,0x44,0x08,0x03,0x01,0x75,0xe5,0xeb,0xd3 ; @0358E
loc_3598:
    cmp byte [0x7c],0x0 ; @03598
    jnz loc_35A2 ; @0359D
    jmp short loc_361C ; @0359F
; UNKNOWN: unresolved bytes
    db 0x90 ; @035A1
loc_35A2:
    test word [si+0x8],0xfd6f ; @035A2
    jz loc_35AC ; @035A7
    jmp short loc_361F ; @035A9
; UNKNOWN: unresolved bytes
    db 0x90 ; @035AB
loc_35AC:
    mov al,[si+0x2c] ; @035AC
    and al,0xf ; @035AF
    cmp al,0x9 ; @035B1
    jz loc_361C ; @035B3
    mov al,[si+0x2b] ; @035B5
    and al,0xf ; @035B8
    mov ah,0x7 ; @035BA
    cmp byte [si+0x27],0x1 ; @035BC
    jz loc_35C4 ; @035C0
    mov ah,0x8 ; @035C2
loc_35C4:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @035C4
    jz loc_361C ; @035C6
    cmp al,0x9 ; @035C8
    jnz loc_35CF ; @035CA
    jmp loc_3287 ; @035CC
loc_35CF:
    dec byte [0x7c] ; @035CF
    mov byte [0x7e],0x0 ; @035D3
    and word [si+0x8],0xfd6f ; @035D8
    or word [si+0x8],0x800 ; @035DD
    mov word [si+0x4],0xfff8 ; @035E2
    mov word [si+0x6],0xfff3 ; @035E7
    mov byte [si+0x28],0x0 ; @035EC
    mov word [si+0xa],0x0 ; @035F0
    mov word [si+0xc],0x90a ; @035F5
    mov word [si+0x10],0x68 ; @035FA
    mov word [si+0x12],0x4e ; @035FF
    mov byte [si+0x29],0x18 ; @03604
    mov ax,[DrawingCallbackSlots-GameDataImage+0x8] ; @03608
    mov [si+0x14],ax ; @0360B
    mov byte [si+0x2a],0xff ; @0360E
    and byte [si+0x24],0x1 ; @03612
    inc word [si+0x2] ; @03616
    jmp loc_31E5 ; @03619
loc_361C:
    jmp loc_320C ; @0361C
loc_361F:
    cmp byte [0x5f],0xff ; @0361F
    jz loc_361C ; @03624
    mov si,[0x5a] ; @03626
    test word [si+0x8],0xfd6f ; @0362A
    jnz loc_361C ; @0362F
    jmp loc_35AC ; @03631
sub_3634:
    mov di,0x88 ; @03634
    mov cl,[0x43] ; @03637
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @0363B
    jz loc_368D ; @0363D
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0363F
    mov [0x45],ch ; @03641
loc_3645:
    push cx ; @03645
    push di ; @03646
    cmp byte [di+0x26],0xff ; @03647
    jz loc_367D ; @0364B
    inc byte [0x45] ; @0364D
    call sub_6FE2 ; @03651
    call sub_5726 ; @03654
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @03657
    cmp ax,[di+0x14] ; @0365A
    jnz loc_3670 ; @0365D
    mov al,[di+0x28] ; @0365F
    cmp al,0x1 ; @03662
    jl loc_3670 ; @03664
    push di ; @03666
    xchg si,di ; @03667
    call sub_6E83 ; @03669
    pop di ; @0366C
    jmp short loc_367D ; @0366D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0366F
loc_3670:
    mov byte [0x50],0xff ; @03670
    call DrawObjectSprite ; @03675
sub_3678:
    mov byte [0x50],0x0 ; @03678
loc_367D:
    pop di ; @0367D
    pop cx ; @0367E
    add di,byte +0x2d ; @0367F
    loop loc_3645 ; @03682
    mov al,[0x45] ; @03684
    mov si,0x2095 ; @03687
    jmp sub_4B68 ; @0368A
loc_368D:
    ret ; @0368D
