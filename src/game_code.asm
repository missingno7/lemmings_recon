; Maintained image span 01ED7..08237; reconstruction module, not a historical linker claim.
; Mixed ownership remains provisional; UNKNOWN bytes and overlay storage keep their classifications.
; UNKNOWN: unresolved bytes
    db 0xb4,0x48,0xbb,0xff,0xff,0xcd,0x21,0x81,0xfb,0x80,0x0c,0x72,0x2f,0x89,0x1e,0x8e ; @01ED7
; UNKNOWN: unresolved bytes
    db 0x1f,0x89,0x1e,0x90,0x1f,0xb4,0x48,0xcd,0x21,0xa3,0x80,0x1f,0xa3,0x84,0x1f,0xa3 ; @01EE7
; UNKNOWN: unresolved bytes
    db 0x88,0x1f,0xa3,0x8c,0x1f,0x33,0xc0,0xa3,0x82,0x1f,0xa3,0x86,0x1f,0xa3,0x8a,0x1f ; @01EF7
; UNKNOWN: unresolved bytes
    db 0xa2,0x92,0x1f,0xa2,0x94,0x1f,0xb0,0xff,0xa2,0x93,0x1f,0xc3,0x32,0xc0,0xa2,0x93 ; @01F07
; UNKNOWN: unresolved bytes
    db 0x1f,0xc3 ; @01F17
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
    call sub_5DC6 ; @02068
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
    call sub_5DC6 ; @02202
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
    call sub_283B ; @02383
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
    call sub_5DC6 ; @023BF
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
    call sub_5DC6 ; @02418
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
    call sub_5DC6 ; @0251A
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
    call sub_5DC6 ; @02576
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
    call sub_5DC6 ; @025ED
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
    call sub_5DC6 ; @02700
    sub di,[0x4] ; @02703
    mov al,[es:di] ; @02707
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0270A
    jnz loc_2763 ; @0270C
    add [si],bp ; @0270E
    call sub_5DC6 ; @02710
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
    call sub_5DC6 ; @0272C
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
    call sub_5DC6 ; @027EF
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
    call sub_283B ; @02835
    jmp loc_1FEB ; @02838
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
    call sub_5DC6 ; @0294B
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
    call sub_5DC6 ; @02A92
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
    call sub_5DC6 ; @02ABE
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
    call sub_5DC6 ; @02ADC
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
    call sub_5DC6 ; @02B90
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
    call sub_5DC6 ; @02C28
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
    call sub_5DC6 ; @02D83
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
    add di,0x17cb ; @02FC1
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
    add bx,0xe98 ; @030E2
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
    mov ax,[0x14] ; @03168
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
sub_368E:
    mov di,0x4a40 ; @0368E
    mov cx,0x8880 ; @03691
    call sub_4DF8 ; @03694
    mov ax,0x680 ; @03697
    mov bx,0xa4 ; @0369A
    mov dx,0x4a40 ; @0369D
    call 0x0:0x8808 ; @036A0
    mov ax,[0x1ff4] ; @036A5
    inc ax ; @036A8
    mov [0x1fe4],ax ; @036A9
    ret ; @036AC
sub_36AD:
    mov di,0xcc40 ; @036AD
    mov cx,0x340 ; @036B0
    jmp sub_4DF8 ; @036B3
; LEVEL-RECORD CONSUMER: main DS, LoadedLevelRecord big-endian header words.
; Copies low bytes to64/67,47,44 and eight skill counters; time word+30 contributes
; only AL to20A7. Camera word+10 feeds pixel and byte offsets.
; Selects special setup or sentinel-terminated terrain records, then object helpers
; and13 calls to796F. Callee state/alias contracts remain open; no C closure claimed.
sub_36B6:
    call sub_368E ; @036B6
    mov di,LoadedLevelRecord-GameDataImage ; @036B9
    mov ah,[di] ; @036BC
    mov al,[di+0x1] ; @036BE
    mov [0x64],al ; @036C1
    mov [0x67],al ; @036C4
    mov ah,[di+0x2] ; @036C7
    mov al,[di+0x3] ; @036CA
    mov [0x47],al ; @036CD
    mov ah,[di+0x4] ; @036D0
    mov al,[di+0x5] ; @036D3
    mov [0x44],al ; @036D6
    mov ah,[di+0x6] ; @036D9
    mov al,[di+0x7] ; @036DC
    add ax,0x30 ; @036DF
    mov [0x20a7],al ; @036E2
    mov ah,[di+0x8] ; @036E5
    mov al,[di+0x9] ; @036E8
    mov [0x6a],al ; @036EB
    mov ah,[di+0xa] ; @036EE
    mov al,[di+0xb] ; @036F1
    mov [0x6d],al ; @036F4
    mov ah,[di+0xc] ; @036F7
    mov al,[di+0xd] ; @036FA
    mov [0x70],al ; @036FD
    mov ah,[di+0xe] ; @03700
    mov al,[di+0xf] ; @03703
    mov [0x73],al ; @03706
    mov ah,[di+0x10] ; @03709
    mov al,[di+0x11] ; @0370C
    mov [0x76],al ; @0370F
    mov ah,[di+0x12] ; @03712
    mov al,[di+0x13] ; @03715
    mov [0x79],al ; @03718
    mov ah,[di+0x14] ; @0371B
    mov al,[di+0x15] ; @0371E
    mov [0x7c],al ; @03721
    mov ah,[di+0x16] ; @03724
    mov al,[di+0x17] ; @03727
    mov [0x7f],al ; @0372A
    mov ah,[di+0x18] ; @0372D
    mov al,[di+0x19] ; @03730
    add ax,0x10 ; @03733
    mov [0x0],ax ; @03736
    shr ax,1 ; @03739
    shr ax,1 ; @0373B
    shr ax,1 ; @0373D
    mov [0x2],ax ; @0373F
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @03742
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @03745
    jz loc_374F ; @03747
    call SetupSpecialGraphicsResource ; @03749
    jmp short loc_376A ; @0374C
; UNKNOWN: unresolved bytes
    db 0x90 ; @0374E
loc_374F:
    mov si,0x10eb ; @0374F
loc_3752:
    mov ah,[si] ; @03752
    mov al,[si+0x1] ; @03754
    mov bh,[si+0x2] ; @03757
    mov bl,[si+0x3] ; @0375A
    add si,byte +0x4 ; @0375D
    cmp ax,0xffff ; @03760
    jz loc_376A ; @03763
    call sub_7C67 ; @03765
    jmp short loc_3752 ; @03768
loc_376A:
    call sub_378A ; @0376A
    call sub_3839 ; @0376D
    call sub_37C2 ; @03770
    call sub_389F ; @03773
    call sub_36AD ; @03776
    mov cx,0xd ; @03779
loc_377C:
    push cx ; @0377C
    call sub_796F ; @0377D
    pop cx ; @03780
    loop loc_377C ; @03781
    mov ax,[LevelGraphicsSegment-GameDataImage] ; @03783
    mov [GraphicsResourceSegment-GameDataImage],ax ; @03786
    ret ; @03789
; RECORD HANDOFF: main DS is also copied to ES.32 eight-byte definitions at0FEB
; select28-byte ground records by their big-endian word at+4. Low16-bit MUL/add
; chooses the live source; no type-index check. Destination17CB..1B4A is32 slots.
; A zero first definition word skips the copy, leaving stale destination bytes.
; Incoming DF controls REP MOVSB; SI/DI/CX restores read the original live stack.
; This working array adjoins the ground load at1B4B; it is not separate C state.
sub_378A:
    push ds ; @0378A
    pop es ; @0378B
    lea bx,[0xfeb] ; @0378C
    lea si,[0x1b4b] ; @03790
    lea di,[0x17cb] ; @03794
    mov cx,0x20 ; @03798
loc_379B:
    mov ah,[bx] ; @0379B
    mov al,[bx+0x1] ; @0379D
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @037A0
    jz loc_37B9 ; @037A2
    mov ah,[bx+0x4] ; @037A4
    mov al,[bx+0x5] ; @037A7
    push si ; @037AA
    push cx ; @037AB
    push di ; @037AC
    mov cx,0x1c ; @037AD
    mul cx ; @037B0
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @037B2
    rep movsb ; @037B4
    pop di ; @037B6
    pop cx ; @037B7
    pop si ; @037B8
loc_37B9:
    add bx,byte +0x8 ; @037B9
    add di,byte +0x1c ; @037BC
    loop loc_379B ; @037BF
    ret ; @037C1
sub_37C2:
    lea di,[0xfeb] ; @037C2
    mov cx,0x10 ; @037C6
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @037C9
loc_37CB:
    mov ah,[di+0x4] ; @037CB
    mov al,[di+0x5] ; @037CE
    mov dx,0x1c ; @037D1
    mul dx ; @037D4
    lea si,[0x1b4b] ; @037D6
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @037DA
    mov ah,[di] ; @037DC
    mov al,[di+0x1] ; @037DE
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @037E1
    jz loc_382F ; @037E3
    shr ax,1 ; @037E5
    shr ax,1 ; @037E7
    add ax,[si+0xe] ; @037E9
    mov bh,[di+0x2] ; @037EC
    mov bl,[di+0x3] ; @037EF
    shr bx,1 ; @037F2
    shr bx,1 ; @037F4
    add bx,[si+0x10] ; @037F6
    dec bx ; @037F9
    push ax ; @037FA
    mov ax,0x1a0 ; @037FB
    mul bx ; @037FE
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @03800
    pop ax ; @03802
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @03803
    add bx,byte +0x12 ; @03805
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @03808
    shl ax,1 ; @0380A
    shl ax,1 ; @0380C
    shl ax,1 ; @0380E
    shl ax,1 ; @03810
    or al,[si+0x14] ; @03812
    mov dh,[si+0x12] ; @03815
    mov dl,[si+0x13] ; @03818
loc_381B:
    push dx ; @0381B
    push bx ; @0381C
loc_381D:
    mov [ss:bx],al ; @0381D
    inc bx ; @03820
    dec dh ; @03821
    jnz loc_381D ; @03823
    pop bx ; @03825
    pop dx ; @03826
    add bx,0x1a0 ; @03827
    dec dl ; @0382B
    jnz loc_381B ; @0382D
loc_382F:
    add di,byte +0x8 ; @0382F
    inc bp ; @03832
    dec cx ; @03833
    jz loc_3838 ; @03834
    jmp short loc_37CB ; @03836
loc_3838:
    ret ; @03838
sub_3839:
    lea di,[0x172b] ; @03839
    mov cx,0x20 ; @0383D
loc_3840:
    mov ah,[di] ; @03840
    mov al,[di+0x1] ; @03842
    mov dh,[di+0x2] ; @03845
    mov dl,[di+0x3] ; @03848
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @0384B
    db 0x0b,0xda ; ENCODED: or bx,dx (NASM chooses a different encoding) ; @0384D
    jz loc_3899 ; @0384F
    db 0x8a,0xd6 ; ENCODED: mov dl,dh (NASM chooses a different encoding) ; @03851
    and dl,0xf ; @03853
    shr dh,1 ; @03856
    shr dh,1 ; @03858
    shr dh,1 ; @0385A
    shr dh,1 ; @0385C
    and dh,0xf ; @0385E
    push dx ; @03861
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @03862
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @03864
    and bl,0x7f ; @03866
    db 0x8a,0xd0 ; ENCODED: mov dl,al (NASM chooses a different encoding) ; @03869
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0386B
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0386D
    rol dl,1 ; @0386F
    rcl ax,1 ; @03871
    push ax ; @03873
    mov ax,0x1a0 ; @03874
    mul bx ; @03877
    pop bx ; @03879
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0387A
    add bx,byte +0x12 ; @0387C
    pop dx ; @0387F
    add dx,0x101 ; @03880
loc_3884:
    push dx ; @03884
    push bx ; @03885
loc_3886:
    mov byte [ss:bx],0x9 ; @03886
    inc bx ; @0388A
    dec dh ; @0388B
    jnz loc_3886 ; @0388D
    pop bx ; @0388F
    pop dx ; @03890
    add bx,0x1a0 ; @03891
    dec dl ; @03895
    jnz loc_3884 ; @03897
loc_3899:
    add di,byte +0x4 ; @03899
    loop loc_3840 ; @0389C
    ret ; @0389E
sub_389F:
    lea si,[0xfeb] ; @0389F
    lea bx,[0xe98] ; @038A3
    mov cx,0x20 ; @038A7
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @038AA
loc_38AC:
    mov ah,[si+0x4] ; @038AC
    mov al,[si+0x5] ; @038AF
    cmp ax,0x1 ; @038B2
    jnz loc_38D1 ; @038B5
    mov ah,[si] ; @038B7
    mov al,[si+0x1] ; @038B9
    add ax,0x18 ; @038BC
    mov [bx],ax ; @038BF
    mov ah,[si+0x2] ; @038C1
    mov al,[si+0x3] ; @038C4
    add ax,0x1e ; @038C7
    mov [bx+0x2],ax ; @038CA
    add bx,byte +0x4 ; @038CD
    inc bp ; @038D0
loc_38D1:
    add si,byte +0x8 ; @038D1
    loop loc_38AC ; @038D4
    db 0x23,0xed ; ENCODED: and bp,bp (NASM chooses a different encoding) ; @038D6
    jz loc_3926 ; @038D8
    cmp bp,byte +0x1 ; @038DA
    jz loc_38EA ; @038DD
    cmp bp,byte +0x2 ; @038DF
    jz loc_3902 ; @038E2
    cmp bp,byte +0x3 ; @038E4
    jz loc_391A ; @038E7
    ret ; @038E9
loc_38EA:
    mov ax,[bx-0x4] ; @038EA
    mov cx,[bx-0x2] ; @038ED
    mov [bx],ax ; @038F0
    mov [bx+0x2],cx ; @038F2
    mov [bx+0x4],ax ; @038F5
    mov [bx+0x6],cx ; @038F8
    mov [bx+0x8],ax ; @038FB
    mov [bx+0xa],cx ; @038FE
    ret ; @03901
loc_3902:
    mov ax,[bx-0x4] ; @03902
    mov cx,[bx-0x2] ; @03905
    mov [bx],ax ; @03908
    mov [bx+0x2],cx ; @0390A
    mov ax,[bx-0x8] ; @0390D
    mov cx,[bx-0x6] ; @03910
    mov [bx+0x4],ax ; @03913
    mov [bx+0x6],cx ; @03916
    ret ; @03919
loc_391A:
    mov ax,[bx-0x8] ; @0391A
    mov cx,[bx-0x6] ; @0391D
    mov [bx],ax ; @03920
    mov [bx+0x2],cx ; @03922
    ret ; @03925
loc_3926:
    mov ax,0x100 ; @03926
    mov cx,0x10 ; @03929
    mov [bx],ax ; @0392C
    mov [bx+0x2],cx ; @0392E
    mov [bx+0x4],ax ; @03931
    mov [bx+0x6],cx ; @03934
    mov [bx+0x8],ax ; @03937
    mov [bx+0xa],cx ; @0393A
    mov [bx+0xa],ax ; @0393D
    mov [bx+0xe],cx ; @03940
    ret ; @03943
sub_3944:
    cmp byte [0x2b],0xff ; @03944
    jz loc_394E ; @03949
    jmp loc_7C0A ; @0394B
loc_394E:
    ret ; @0394E
; LEVEL-DISPLAY REBUILD: reuses the special/terrain path and record-derived
; object definitions; traverses32 entries and28-byte working records before far
; blit8822. No bounds/type ownership proof or full callee contract is established.
sub_394F:
    call sub_368E ; @0394F
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @03952
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @03955
    jz loc_395F ; @03957
    call SetupSpecialGraphicsResource ; @03959
    jmp short loc_397A ; @0395C
; UNKNOWN: unresolved bytes
    db 0x90 ; @0395E
loc_395F:
    mov si,0x10eb ; @0395F
loc_3962:
    mov ah,[si] ; @03962
    mov al,[si+0x1] ; @03964
    mov bh,[si+0x2] ; @03967
    mov bl,[si+0x3] ; @0396A
    add si,byte +0x4 ; @0396D
    cmp ax,0xffff ; @03970
    jz loc_397A ; @03973
    call sub_7C67 ; @03975
    jmp short loc_3962 ; @03978
loc_397A:
    call sub_378A ; @0397A
    lea si,[0x17cb] ; @0397D
    lea di,[0xfeb] ; @03981
    mov cx,0x20 ; @03985
    mov ax,[0x1ff0] ; @03988
    mov [0x1fe4],ax ; @0398B
loc_398E:
    mov ah,[di] ; @0398E
    mov al,[di+0x1] ; @03990
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @03993
    jz loc_39C5 ; @03995
    push cx ; @03997
    push di ; @03998
    push si ; @03999
    mov bh,[di+0x2] ; @0399A
    mov bl,[di+0x3] ; @0399D
    mov dh,[di+0x6] ; @039A0
    mov dl,[di+0x7] ; @039A3
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @039A6
    and bp,byte -0x2 ; @039A8
    mov dl,[si+0x4] ; @039AB
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @039AE
    mov cl,[si+0x5] ; @039B0
    mov di,[si+0x8] ; @039B3
    mov si,[si+0x17] ; @039B6
    db 0x03,0xfe ; ENCODED: add di,si (NASM chooses a different encoding) ; @039B9
    mov ch,0x4 ; @039BB
    call 0x0:0x8822 ; @039BD
    pop si ; @039C2
    pop di ; @039C3
    pop cx ; @039C4
loc_39C5:
    add di,byte +0x8 ; @039C5
    add si,byte +0x1c ; @039C8
    loop loc_398E ; @039CB
    ret ; @039CD
sub_39CE:
    call sub_75EF ; @039CE
    mov byte [0x48],0x14 ; @039D1
    mov al,0x63 ; @039D6
    sub al,[0x67] ; @039D8
    shr al,1 ; @039DC
    neg al ; @039DE
    add al,0x35 ; @039E0
    neg al ; @039E2
    add al,0x39 ; @039E4
    mov [0x49],al ; @039E6
    mov byte [0x66],0x0 ; @039E9
    mov byte [0x69],0x0 ; @039EE
    mov byte [0x72],0x0 ; @039F3
    mov byte [0x81],0x0 ; @039F8
    mov byte [0x6c],0x0 ; @039FD
    mov byte [0x78],0x0 ; @03A02
    mov byte [0x75],0x0 ; @03A07
    mov byte [0x7b],0x0 ; @03A0C
    mov byte [0x6f],0x0 ; @03A11
    mov byte [0x7e],0x0 ; @03A16
    mov byte [0x84],0x0 ; @03A1B
    mov byte [0x65],0xff ; @03A20
    mov byte [0x68],0xff ; @03A25
    mov byte [0x71],0xff ; @03A2A
    mov byte [0x80],0xff ; @03A2F
    mov byte [0x6b],0xff ; @03A34
    mov byte [0x77],0xff ; @03A39
    mov byte [0x74],0xff ; @03A3E
    mov byte [0x7a],0xff ; @03A43
    mov byte [0x6e],0xff ; @03A48
    mov byte [0x7d],0xff ; @03A4D
    mov byte [0x83],0x3 ; @03A52
    mov ah,[0x64] ; @03A57
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @03A5B
    call sub_762A ; @03A5D
    mov ah,[0x67] ; @03A60
    mov al,0x1 ; @03A64
    call sub_762A ; @03A66
    mov ah,[0x70] ; @03A69
    mov al,0x4 ; @03A6D
    call sub_762A ; @03A6F
    mov ah,[0x7f] ; @03A72
    mov al,0x9 ; @03A76
    call sub_762A ; @03A78
    mov ah,[0x6a] ; @03A7B
    mov al,0x2 ; @03A7F
    call sub_762A ; @03A81
    mov ah,[0x76] ; @03A84
    mov al,0x6 ; @03A88
    call sub_762A ; @03A8A
    mov ah,[0x73] ; @03A8D
    mov al,0x5 ; @03A91
    call sub_762A ; @03A93
    mov ah,[0x79] ; @03A96
    mov al,0x7 ; @03A9A
    call sub_762A ; @03A9C
    mov ah,[0x6d] ; @03A9F
    mov al,0x3 ; @03AA3
    call sub_762A ; @03AA5
    mov ah,[0x7c] ; @03AA8
    mov al,0x8 ; @03AAC
    call sub_762A ; @03AAE
    mov al,[0x45] ; @03AB1
    mov si,0x2095 ; @03AB4
    call sub_4B68 ; @03AB7
    mov si,0x209d ; @03ABA
    mov byte [si-0x1],0x20 ; @03ABD
    mov al,[0x82] ; @03AC1
    call sub_780D ; @03AC4
    ret ; @03AC7
sub_3AC8:
    call sub_796F ; @03AC8
    call sub_7A5A ; @03ACB
    mov al,[0x46] ; @03ACE
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03AD1
    shl ax,1 ; @03AD3
    shl ax,1 ; @03AD5
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @03AD7
    shl ax,1 ; @03AD9
    shl ax,1 ; @03ADB
    shl ax,1 ; @03ADD
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @03ADF
    shl ax,1 ; @03AE1
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @03AE3
    mov cl,[0x47] ; @03AE5
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @03AE9
    jz loc_3AEF ; @03AEB
    div cl ; @03AED
loc_3AEF:
    mov si,0x209d ; @03AEF
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03AF2
    mov [0x40],al ; @03AF4
    cmp al,0x64 ; @03AF7
    jnz loc_3B09 ; @03AF9
    mov byte [si-0x1],0x31 ; @03AFB
    mov byte [si],0x30 ; @03AFF
    mov byte [si+0x1],0x30 ; @03B02
    jmp short loc_3B21 ; @03B06
; UNKNOWN: unresolved bytes
    db 0x90 ; @03B08
loc_3B09:
    inc ah ; @03B09
    sub al,0xa ; @03B0B
    jnc loc_3B09 ; @03B0D
    add al,0x3a ; @03B0F
    dec ah ; @03B11
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B13
    jnz loc_3B19 ; @03B15
    mov ah,0xf0 ; @03B17
loc_3B19:
    add ah,0x30 ; @03B19
    mov [si],ah ; @03B1C
    mov [si+0x1],al ; @03B1E
loc_3B21:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03B21
    mov si,0x2083 ; @03B23
    call sub_417B ; @03B26
    mov ah,[0x82] ; @03B29
    cmp [0x83],ah ; @03B2D
    jz loc_3B57 ; @03B31
    mov al,[0x82] ; @03B33
    call sub_780D ; @03B36
    mov al,[0x83] ; @03B39
    call sub_789E ; @03B3C
    cmp byte [0x84],0x2 ; @03B3F
    jnz loc_3B53 ; @03B44
    mov ah,[0x82] ; @03B46
    mov [0x83],ah ; @03B4A
    mov byte [0x84],0xff ; @03B4E
loc_3B53:
    inc byte [0x84] ; @03B53
loc_3B57:
    mov ah,[0x64] ; @03B57
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B5B
    jz loc_3B65 ; @03B5D
    cmp [0x65],ah ; @03B5F
    jz loc_3B7E ; @03B63
loc_3B65:
    cmp byte [0x66],0x2 ; @03B65
    jnz loc_3B75 ; @03B6A
    mov [0x65],ah ; @03B6C
    mov byte [0x66],0xff ; @03B70
loc_3B75:
    inc byte [0x66] ; @03B75
    mov al,0x0 ; @03B79
    call sub_762A ; @03B7B
loc_3B7E:
    mov ah,[0x67] ; @03B7E
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B82
    jz loc_3B8C ; @03B84
    cmp [0x68],ah ; @03B86
    jz loc_3BA5 ; @03B8A
loc_3B8C:
    cmp byte [0x69],0x2 ; @03B8C
    jnz loc_3B9C ; @03B91
    mov [0x68],ah ; @03B93
    mov byte [0x69],0xff ; @03B97
loc_3B9C:
    inc byte [0x69] ; @03B9C
    mov al,0x1 ; @03BA0
    call sub_762A ; @03BA2
loc_3BA5:
    mov ah,[0x70] ; @03BA5
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BA9
    jz loc_3BB3 ; @03BAB
    cmp [0x71],ah ; @03BAD
    jz loc_3BCC ; @03BB1
loc_3BB3:
    cmp byte [0x72],0x2 ; @03BB3
    jnz loc_3BC3 ; @03BB8
    mov [0x71],ah ; @03BBA
    mov byte [0x72],0xff ; @03BBE
loc_3BC3:
    inc byte [0x72] ; @03BC3
    mov al,0x4 ; @03BC7
    call sub_762A ; @03BC9
loc_3BCC:
    mov ah,[0x7f] ; @03BCC
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BD0
    jz loc_3BDA ; @03BD2
    cmp [0x80],ah ; @03BD4
    jz loc_3BF3 ; @03BD8
loc_3BDA:
    cmp byte [0x81],0x2 ; @03BDA
    jnz loc_3BEA ; @03BDF
    mov [0x80],ah ; @03BE1
    mov byte [0x81],0xff ; @03BE5
loc_3BEA:
    inc byte [0x81] ; @03BEA
    mov al,0x9 ; @03BEE
    call sub_762A ; @03BF0
loc_3BF3:
    mov ah,[0x6a] ; @03BF3
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BF7
    jz loc_3C01 ; @03BF9
    cmp [0x6b],ah ; @03BFB
    jz loc_3C1A ; @03BFF
loc_3C01:
    cmp byte [0x6c],0x2 ; @03C01
    jnz loc_3C11 ; @03C06
    mov [0x6b],ah ; @03C08
    mov byte [0x6c],0xff ; @03C0C
loc_3C11:
    inc byte [0x6c] ; @03C11
    mov al,0x2 ; @03C15
    call sub_762A ; @03C17
loc_3C1A:
    mov ah,[0x76] ; @03C1A
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C1E
    jz loc_3C28 ; @03C20
    cmp [0x77],ah ; @03C22
    jz loc_3C41 ; @03C26
loc_3C28:
    cmp byte [0x78],0x2 ; @03C28
    jnz loc_3C38 ; @03C2D
    mov [0x77],ah ; @03C2F
    mov byte [0x78],0xff ; @03C33
loc_3C38:
    inc byte [0x78] ; @03C38
    mov al,0x6 ; @03C3C
    call sub_762A ; @03C3E
loc_3C41:
    mov ah,[0x73] ; @03C41
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C45
    jz loc_3C4F ; @03C47
    cmp [0x74],ah ; @03C49
    jz loc_3C68 ; @03C4D
loc_3C4F:
    cmp byte [0x75],0x2 ; @03C4F
    jnz loc_3C5F ; @03C54
    mov [0x74],ah ; @03C56
    mov byte [0x75],0xff ; @03C5A
loc_3C5F:
    inc byte [0x75] ; @03C5F
    mov al,0x5 ; @03C63
    call sub_762A ; @03C65
loc_3C68:
    mov ah,[0x79] ; @03C68
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C6C
    jz loc_3C76 ; @03C6E
    cmp [0x7a],ah ; @03C70
    jz loc_3C8F ; @03C74
loc_3C76:
    cmp byte [0x7b],0x2 ; @03C76
    jnz loc_3C86 ; @03C7B
    mov [0x7a],ah ; @03C7D
    mov byte [0x7b],0xff ; @03C81
loc_3C86:
    inc byte [0x7b] ; @03C86
    mov al,0x7 ; @03C8A
    call sub_762A ; @03C8C
loc_3C8F:
    mov ah,[0x6d] ; @03C8F
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C93
    jz loc_3C9D ; @03C95
    cmp [0x6e],ah ; @03C97
    jz loc_3CB6 ; @03C9B
loc_3C9D:
    cmp byte [0x6f],0x2 ; @03C9D
    jnz loc_3CAD ; @03CA2
    mov [0x6e],ah ; @03CA4
    mov byte [0x6f],0xff ; @03CA8
loc_3CAD:
    inc byte [0x6f] ; @03CAD
    mov al,0x3 ; @03CB1
    call sub_762A ; @03CB3
loc_3CB6:
    mov ah,[0x7c] ; @03CB6
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03CBA
    jz loc_3CC4 ; @03CBC
    cmp [0x7d],ah ; @03CBE
    jz loc_3CDD ; @03CC2
loc_3CC4:
    cmp byte [0x7e],0x2 ; @03CC4
    jnz loc_3CD4 ; @03CC9
    mov [0x7d],ah ; @03CCB
    mov byte [0x7e],0xff ; @03CCF
loc_3CD4:
    inc byte [0x7e] ; @03CD4
    mov al,0x8 ; @03CD8
    call sub_762A ; @03CDA
loc_3CDD:
    ret ; @03CDD
sub_3CDE:
    mov cl,[0x43] ; @03CDE
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @03CE2
    jnz loc_3CE9 ; @03CE4
    jmp loc_3E62 ; @03CE6
loc_3CE9:
    mov si,0x2083 ; @03CE9
    mov ah,0xb ; @03CEC
loc_3CEE:
    mov byte [si],0x20 ; @03CEE
    inc si ; @03CF1
    dec ah ; @03CF2
    jnz loc_3CEE ; @03CF4
    mov byte [0x63],0x0 ; @03CF6
    mov byte [0x5e],0xff ; @03CFB
    mov byte [0x60],0xff ; @03D00
    mov byte [0x5f],0xff ; @03D05
    mov ax,[0x0] ; @03D0A
    sub ax,0x10 ; @03D0D
    add ax,[0x10] ; @03D10
    mov bx,[0x12] ; @03D14
    add bx,byte +0x8 ; @03D18
    mov si,0x88 ; @03D1B
loc_3D1E:
    cmp byte [si+0x26],0xff ; @03D1E
    jnz loc_3D27 ; @03D22
    jmp short loc_3DA5 ; @03D24
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D26
loc_3D27:
    mov bp,[si] ; @03D27
    add bp,[si+0x4] ; @03D29
    sub bp,byte +0x4 ; @03D2C
    jns loc_3D33 ; @03D2F
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @03D31
loc_3D33:
    mov di,[si+0x2] ; @03D33
    add di,[si+0x6] ; @03D36
    dec di ; @03D39
    jns loc_3D3E ; @03D3A
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @03D3C
loc_3D3E:
    db 0x3b,0xc5 ; ENCODED: cmp ax,bp (NASM chooses a different encoding) ; @03D3E
    jnl loc_3D45 ; @03D40
    jmp short loc_3DA5 ; @03D42
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D44
loc_3D45:
    db 0x3b,0xdf ; ENCODED: cmp bx,di (NASM chooses a different encoding) ; @03D45
    jnl loc_3D4C ; @03D47
    jmp short loc_3DA5 ; @03D49
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D4B
loc_3D4C:
    add bp,byte +0xc ; @03D4C
    cmp bp,0x680 ; @03D4F
    jnl loc_3D58 ; @03D53
    jmp short loc_3D5B ; @03D55
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D57
loc_3D58:
    mov bp,0xd0 ; @03D58
loc_3D5B:
    add di,byte +0xc ; @03D5B
    cmp di,0xb0 ; @03D5E
    jnl loc_3D67 ; @03D62
    jmp short loc_3D6A ; @03D64
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D66
loc_3D67:
    mov di,0xb0 ; @03D67
loc_3D6A:
    db 0x3b,0xc5 ; ENCODED: cmp ax,bp (NASM chooses a different encoding) ; @03D6A
    jng loc_3D71 ; @03D6C
    jmp short loc_3DA5 ; @03D6E
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D70
loc_3D71:
    db 0x3b,0xdf ; ENCODED: cmp bx,di (NASM chooses a different encoding) ; @03D71
    jng loc_3D78 ; @03D73
    jmp short loc_3DA5 ; @03D75
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D77
loc_3D78:
    push ax ; @03D78
    test byte [si+0x24],0x80 ; @03D79
    jnz loc_3D86 ; @03D7D
    test word [si+0x8],0x8b90 ; @03D7F
    jz loc_3D94 ; @03D84
loc_3D86:
    mov al,[0x43] ; @03D86
    db 0x2a,0xc1 ; ENCODED: sub al,cl (NASM chooses a different encoding) ; @03D89
    mov [0x60],al ; @03D8B
    mov [0x5c],si ; @03D8E
    jmp short loc_3DA0 ; @03D92
loc_3D94:
    mov al,[0x43] ; @03D94
    db 0x2a,0xc1 ; ENCODED: sub al,cl (NASM chooses a different encoding) ; @03D97
    mov [0x5f],al ; @03D99
    mov [0x5a],si ; @03D9C
loc_3DA0:
    pop ax ; @03DA0
    inc byte [0x63] ; @03DA1
loc_3DA5:
    add si,byte +0x2d ; @03DA5
    dec cl ; @03DA8
    jz loc_3DAF ; @03DAA
    jmp loc_3D1E ; @03DAC
loc_3DAF:
    mov byte [0x1a],0x0 ; @03DAF
    mov ax,[0x14] ; @03DB4
    test ax,0x2 ; @03DB7
    jz loc_3DCC ; @03DBA
loc_3DBC:
    mov al,[0x5f] ; @03DBC
    mov si,[0x5a] ; @03DBF
    mov [0x5e],al ; @03DC3
    mov [0x58],si ; @03DC6
    jmp short loc_3DDE ; @03DCA
loc_3DCC:
    mov al,[0x60] ; @03DCC
    cmp al,0xff ; @03DCF
    jz loc_3DBC ; @03DD1
    mov si,[0x5c] ; @03DD3
    mov [0x5e],al ; @03DD7
    mov [0x58],si ; @03DDA
loc_3DDE:
    cmp byte [0x5e],0xff ; @03DDE
    jnz loc_3DE8 ; @03DE3
    jmp short loc_3E62 ; @03DE5
; UNKNOWN: unresolved bytes
    db 0x90 ; @03DE7
loc_3DE8:
    mov byte [0x1a],0xff ; @03DE8
    mov si,0x208b ; @03DED
    mov al,[0x63] ; @03DF0
    call sub_4B68 ; @03DF3
    mov si,[0x58] ; @03DF6
    mov bx,0x48db ; @03DFA
    mov al,[si+0x24] ; @03DFD
    test al,0x80 ; @03E00
    jnz loc_3E53 ; @03E02
    mov bx,0x48bf ; @03E04
    test al,0x1 ; @03E07
    jnz loc_3E63 ; @03E09
    mov bx,0x48c6 ; @03E0B
    cmp byte [si+0x25],0x0 ; @03E0E
    jnz loc_3E53 ; @03E12
    mov bx,0x48d4 ; @03E14
    test word [si+0x8],0x100 ; @03E17
    jnz loc_3E53 ; @03E1C
    mov bx,0x48db ; @03E1E
    test word [si+0x8],0x80 ; @03E21
    jnz loc_3E53 ; @03E26
    mov bx,0x48e2 ; @03E28
    test word [si+0x8],0x200 ; @03E2B
    jnz loc_3E53 ; @03E30
    mov bx,0x48e9 ; @03E32
    test word [si+0x8],0x800 ; @03E35
    jnz loc_3E53 ; @03E3A
    mov bx,0x48f0 ; @03E3C
    test word [si+0x8],0x10 ; @03E3F
    jnz loc_3E53 ; @03E44
    mov bx,0x48fe ; @03E46
    test word [si+0x8],0x4 ; @03E49
    jnz loc_3E53 ; @03E4E
    mov bx,0x48f7 ; @03E50
loc_3E53:
    mov si,0x2083 ; @03E53
    mov ah,0x7 ; @03E56
loc_3E58:
    mov al,[bx] ; @03E58
    mov [si],al ; @03E5A
    inc si ; @03E5C
    inc bx ; @03E5D
    dec ah ; @03E5E
    jnz loc_3E58 ; @03E60
loc_3E62:
    ret ; @03E62
loc_3E63:
    cmp byte [si+0x25],0x0 ; @03E63
    jz loc_3E53 ; @03E67
    lea bx,[0x490c] ; @03E69
    jmp short loc_3E53 ; @03E6D
sub_3E6F:
    mov al,[0x1fd0] ; @03E6F
    cmp al,0x3b ; @03E72
    jnz loc_3E79 ; @03E74
    jmp loc_4068 ; @03E76
loc_3E79:
    cmp al,0x3c ; @03E79
    jnz loc_3E80 ; @03E7B
    jmp loc_403D ; @03E7D
loc_3E80:
    cmp al,0x4e ; @03E80
    jnz loc_3E87 ; @03E82
    jmp loc_4018 ; @03E84
loc_3E87:
    cmp al,0x57 ; @03E87
    jnz loc_3E8E ; @03E89
    jmp loc_4018 ; @03E8B
loc_3E8E:
    cmp al,0x58 ; @03E8E
    jnz loc_3E95 ; @03E90
    jmp loc_3FEF ; @03E92
loc_3E95:
    cmp al,0x53 ; @03E95
    jnz loc_3E9C ; @03E97
    jmp loc_3FEF ; @03E99
loc_3E9C:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @03E9C
    mov al,0x2 ; @03E9E
    cmp ah,0x3d ; @03EA0
    jnz loc_3EA8 ; @03EA3
    jmp loc_3F5C ; @03EA5
loc_3EA8:
    inc al ; @03EA8
    cmp ah,0x3e ; @03EAA
    jnz loc_3EB2 ; @03EAD
    jmp loc_3F5C ; @03EAF
loc_3EB2:
    inc al ; @03EB2
    cmp ah,0x3f ; @03EB4
    jnz loc_3EBC ; @03EB7
    jmp loc_3F5C ; @03EB9
loc_3EBC:
    inc al ; @03EBC
    cmp ah,0x40 ; @03EBE
    jnz loc_3EC6 ; @03EC1
    jmp loc_3F5C ; @03EC3
loc_3EC6:
    inc al ; @03EC6
    cmp ah,0x41 ; @03EC8
    jnz loc_3ED0 ; @03ECB
    jmp loc_3F5C ; @03ECD
loc_3ED0:
    inc al ; @03ED0
    cmp ah,0x42 ; @03ED2
    jnz loc_3EDA ; @03ED5
    jmp loc_3F5C ; @03ED7
loc_3EDA:
    inc al ; @03EDA
    cmp ah,0x43 ; @03EDC
    jnz loc_3EE4 ; @03EDF
    jmp short loc_3F5C ; @03EE1
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EE3
loc_3EE4:
    inc al ; @03EE4
    cmp ah,0x44 ; @03EE6
    jnz loc_3EEE ; @03EE9
    jmp short loc_3F5C ; @03EEB
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EED
loc_3EEE:
    mov ax,[0x14] ; @03EEE
    test ax,0x1 ; @03EF1
    jnz loc_3EF9 ; @03EF4
    jmp loc_3FE3 ; @03EF6
loc_3EF9:
    mov ax,[0x12] ; @03EF9
    add ax,0x8 ; @03EFC
    cmp ax,0xc0 ; @03EFF
    jnl loc_3F07 ; @03F02
    jmp loc_3FE9 ; @03F04
loc_3F07:
    mov ax,[0x10] ; @03F07
    add ax,0xfff8 ; @03F0A
    cmp ax,0xd0 ; @03F0D
    jl loc_3F15 ; @03F10
    jmp short loc_3F92 ; @03F12
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F14
loc_3F15:
    cmp byte [0x84],0x0 ; @03F15
    jz loc_3F1F ; @03F1A
    jmp loc_3FE9 ; @03F1C
loc_3F1F:
    shr ax,1 ; @03F1F
    shr ax,1 ; @03F21
    shr ax,1 ; @03F23
    shr ax,1 ; @03F25
    cmp al,0x2 ; @03F27
    jnl loc_3F2E ; @03F29
    jmp loc_4032 ; @03F2B
loc_3F2E:
    cmp byte [0x62],0xff ; @03F2E
    jnz loc_3F38 ; @03F33
    jmp loc_3FE9 ; @03F35
loc_3F38:
    mov byte [0x62],0xff ; @03F38
    cmp al,0xa ; @03F3D
    jnz loc_3F44 ; @03F3F
    jmp loc_4018 ; @03F41
loc_3F44:
    cmp al,0xb ; @03F44
    jnz loc_3F4B ; @03F46
    jmp loc_3FEF ; @03F48
loc_3F4B:
    cmp al,0xc ; @03F4B
    jnz loc_3F52 ; @03F4D
    jmp loc_3FEE ; @03F4F
loc_3F52:
    cmp byte [0x2b],0xff ; @03F52
    jnz loc_3F5C ; @03F57
    jmp loc_3FE9 ; @03F59
loc_3F5C:
    cmp byte [0x84],0x0 ; @03F5C
    jz loc_3F66 ; @03F61
    jmp loc_3FE9 ; @03F63
loc_3F66:
    mov [0x82],al ; @03F66
    cmp byte [0x2010],0xff ; @03F69
    jnz loc_3F7C ; @03F6E
    test byte [0x25a7],0x3 ; @03F70
    jz loc_3F7C ; @03F75
    mov ax,0x401 ; @03F77
    int 0x61 ; @03F7A
loc_3F7C:
    cmp byte [0x2010],0xff ; @03F7C
    jz loc_3F8F ; @03F81
    test byte [0x25a7],0x1 ; @03F83
    jz loc_3F8F ; @03F88
    mov ax,0x313 ; @03F8A
    int 0x60 ; @03F8D
loc_3F8F:
    jmp short loc_3FE9 ; @03F8F
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F91
loc_3F92:
    mov byte [0x62],0xff ; @03F92
    cmp byte [0x1fcf],0x0 ; @03F97
    jnz loc_3FEE ; @03F9C
    mov bx,[0x0] ; @03F9E
    shr bx,1 ; @03FA2
    shr bx,1 ; @03FA4
    shr bx,1 ; @03FA6
    shr bx,1 ; @03FA8
    add bx,0xd0 ; @03FAA
    db 0x3b,0xc3 ; ENCODED: cmp ax,bx (NASM chooses a different encoding) ; @03FAE
    jnl loc_3FBE ; @03FB0
    add bx,byte +0x18 ; @03FB2
    db 0x3b,0xc3 ; ENCODED: cmp ax,bx (NASM chooses a different encoding) ; @03FB5
    jl loc_3FBE ; @03FB7
    cmp ax,0xd0 ; @03FB9
    jl loc_3FE9 ; @03FBC
loc_3FBE:
    sub ax,0xda ; @03FBE
    jns loc_3FC5 ; @03FC1
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @03FC3
loc_3FC5:
    cmp ax,0x4f ; @03FC5
    jng loc_3FCD ; @03FC8
    mov ax,0x4f ; @03FCA
loc_3FCD:
    shl ax,1 ; @03FCD
    add ax,0x2 ; @03FCF
    mov [0x2],ax ; @03FD2
    shl ax,1 ; @03FD5
    shl ax,1 ; @03FD7
    shl ax,1 ; @03FD9
    mov [0x0],ax ; @03FDB
    call sub_410F ; @03FDE
    jmp short loc_3FE9 ; @03FE1
loc_3FE3:
    mov byte [0x62],0x0 ; @03FE3
    ret ; @03FE8
loc_3FE9:
    mov byte [0x62],0xff ; @03FE9
loc_3FEE:
    ret ; @03FEE
loc_3FEF:
    cmp byte [0x2b],0xff ; @03FEF
    jz loc_3FEE ; @03FF4
    mov byte [0x1fd0],0x0 ; @03FF6
    mov al,[0x1fd3] ; @03FFB
    mov ah,[0x1fd4] ; @03FFE
    mov [0x1fd4],al ; @04002
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @04005
    cmp al,0x5 ; @04007
    jg loc_3FEE ; @04009
    mov byte [0x4b],0xff ; @0400B
    mov al,[0x43] ; @04010
    mov [0x47],al ; @04013
    jmp short loc_3FEE ; @04016
loc_4018:
    mov al,[0x52] ; @04018
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @0401B
    sub bl,[0x53] ; @0401D
    cmp bl,0x2 ; @04021
    jnc loc_4028 ; @04024
    jmp short loc_3FEE ; @04026
loc_4028:
    xor byte [0x2b],0xff ; @04028
    mov [0x53],al ; @0402D
    jmp short loc_3FEE ; @04030
loc_4032:
    cmp byte [0x2b],0xff ; @04032
    jz loc_3FEE ; @04037
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04039
    jz loc_4068 ; @0403B
loc_403D:
    cmp byte [0x69],0x0 ; @0403D
    jz loc_4046 ; @04042
    jmp short loc_3FE9 ; @04044
loc_4046:
    cmp byte [0x67],0x63 ; @04046
    jnz loc_404F ; @0404B
    jmp short loc_3FE9 ; @0404D
loc_404F:
    inc byte [0x67] ; @0404F
loc_4053:
    mov al,0x63 ; @04053
    sub al,[0x67] ; @04055
    shr al,1 ; @04059
    neg al ; @0405B
    add al,0x35 ; @0405D
    neg al ; @0405F
    add al,0x39 ; @04061
    mov [0x49],al ; @04063
    jmp short loc_3FE9 ; @04066
loc_4068:
    mov bl,[0x64] ; @04068
    cmp byte [0x69],0x0 ; @0406C
    jz loc_4076 ; @04071
    jmp loc_3FE9 ; @04073
loc_4076:
    cmp [0x67],bl ; @04076
    jnz loc_407F ; @0407A
    jmp loc_3FE9 ; @0407C
loc_407F:
    dec byte [0x67] ; @0407F
    jmp short loc_4053 ; @04083
sub_4085:
    mov al,[0x1fd0] ; @04085
    cmp al,0x2c ; @04088
    jnz loc_408F ; @0408A
    jmp short loc_40B5 ; @0408C
; UNKNOWN: unresolved bytes
    db 0x90 ; @0408E
loc_408F:
    cmp al,0x2d ; @0408F
    jnz loc_4096 ; @04091
    jmp short loc_40CD ; @04093
; UNKNOWN: unresolved bytes
    db 0x90 ; @04095
loc_4096:
    mov ax,[0x12] ; @04096
    add ax,0x8 ; @04099
    cmp ax,0xc0 ; @0409C
    jnl loc_40B4 ; @0409F
    mov ax,[0x10] ; @040A1
    cmp ax,0x8 ; @040A4
    jnz loc_40AC ; @040A7
    jmp loc_414F ; @040A9
loc_40AC:
    cmp ax,0x148 ; @040AC
    jnz loc_40B4 ; @040AF
    jmp short loc_40E5 ; @040B1
; UNKNOWN: unresolved bytes
    db 0x90 ; @040B3
loc_40B4:
    ret ; @040B4
loc_40B5:
    cmp byte [0x84],0x0 ; @040B5
    jnz loc_40CC ; @040BA
    dec byte [0x82] ; @040BC
    cmp byte [0x82],0x1 ; @040C0
    jnz loc_40CC ; @040C5
    mov byte [0x82],0x9 ; @040C7
loc_40CC:
    ret ; @040CC
loc_40CD:
    cmp byte [0x84],0x0 ; @040CD
    jnz loc_40CC ; @040D2
    inc byte [0x82] ; @040D4
    cmp byte [0x82],0xa ; @040D8
    jnz loc_40CC ; @040DD
    mov byte [0x82],0x2 ; @040DF
    ret ; @040E4
loc_40E5:
    mov ax,[0x0] ; @040E5
    cmp ax,0x500 ; @040E8
    jz sub_410F ; @040EB
    add ax,0x8 ; @040ED
    test word [0x14],0x2 ; @040F0
    jz loc_4100 ; @040F6
    cmp ax,0x500 ; @040F8
    jz loc_4100 ; @040FB
    add ax,0x8 ; @040FD
loc_4100:
    mov [0x0],ax ; @04100
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @04103
    shr dx,1 ; @04105
    shr dx,1 ; @04107
    shr dx,1 ; @04109
    mov [0x2],dx ; @0410B
sub_410F:
    push ds ; @0410F
    pop es ; @04110
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04111
    mov di,0xea8 ; @04113
    mov cx,0x68 ; @04116
    rep stosw ; @04119
    mov di,[0x0] ; @0411B
    shr di,1 ; @0411F
    shr di,1 ; @04121
    shr di,1 ; @04123
    dec di ; @04125
    dec di ; @04126
    add di,0xea8 ; @04127
    mov cx,0x29 ; @0412B
    mov ax,0x101 ; @0412E
    rep stosb ; @04131
    cli ; @04133
    mov ax,es ; @04134
    mov cx,0x143e ; @04136
    mov es,cx ; @04139
    mov bx,[0x26] ; @0413B
    mov byte [es:bx],0xff ; @0413F
    mov bx,[0x28] ; @04143
    mov byte [es:bx],0xff ; @04147
    mov es,ax ; @0414B
    sti ; @0414D
    ret ; @0414E
loc_414F:
    mov ax,[0x0] ; @0414F
    cmp ax,0x10 ; @04152
    jng loc_4179 ; @04155
    sub ax,0x8 ; @04157
    test word [0x14],0x2 ; @0415A
    jz loc_416A ; @04160
    cmp ax,0x10 ; @04162
    jng loc_4179 ; @04165
    sub ax,0x8 ; @04167
loc_416A:
    mov [0x0],ax ; @0416A
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @0416D
    shr dx,1 ; @0416F
    shr dx,1 ; @04171
    shr dx,1 ; @04173
    mov [0x2],dx ; @04175
loc_4179:
    jmp short sub_410F ; @04179
sub_417B:
    lodsb ; @0417B
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0417C
    jz loc_418B ; @0417E
    push ax ; @04180
    push si ; @04181
    call sub_7708 ; @04182
    pop si ; @04185
    pop ax ; @04186
    inc ah ; @04187
    jmp short sub_417B ; @04189
loc_418B:
    ret ; @0418B
sub_418C:
    cmp byte [0x25a6],0x0 ; @0418C
    jnz loc_4196 ; @04191
    jmp PollMousePosition ; @04193
loc_4196:
    cmp byte [0x25a6],0x1 ; @04196
    jnz loc_41A0 ; @0419B
    jmp loc_42A1 ; @0419D
loc_41A0:
    mov bx,[0x16] ; @041A0
    mov cx,[0x18] ; @041A4
    mov ax,[0x1fc7] ; @041A8
    test ax,0xc03 ; @041AB
    jnz loc_41B5 ; @041AE
    mov cx,0x10 ; @041B0
    jmp short loc_41D1 ; @041B3
loc_41B5:
    test ax,0x401 ; @041B5
    jz loc_41C1 ; @041B8
    sub cx,byte +0x1 ; @041BA
    jns loc_41C1 ; @041BD
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @041BF
loc_41C1:
    test ax,0x802 ; @041C1
    jz loc_41D1 ; @041C4
    add cx,byte +0x1 ; @041C6
    cmp cx,byte +0x20 ; @041C9
    jng loc_41D1 ; @041CC
    mov cx,0x20 ; @041CE
loc_41D1:
    test ax,0x300c ; @041D1
    jnz loc_41DB ; @041D4
    mov bx,0x10 ; @041D6
    jmp short loc_41F7 ; @041D9
loc_41DB:
    test ax,0x1004 ; @041DB
    jz loc_41E7 ; @041DE
    sub bx,byte +0x1 ; @041E0
    jns loc_41E7 ; @041E3
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @041E5
loc_41E7:
    test ax,0x2008 ; @041E7
    jz loc_41F7 ; @041EA
    add bx,byte +0x1 ; @041EC
    cmp bx,byte +0x20 ; @041EF
    jng loc_41F7 ; @041F2
    mov bx,0x20 ; @041F4
loc_41F7:
    mov [0x16],bx ; @041F7
    mov [0x18],cx ; @041FB
    shr bx,1 ; @041FF
    shr cx,1 ; @04201
    shr bx,1 ; @04203
    shr cx,1 ; @04205
    sub bx,byte +0x4 ; @04207
    sub cx,byte +0x4 ; @0420A
    add bx,[0x10] ; @0420D
    cmp bx,byte +0x8 ; @04211
    jg loc_421B ; @04214
    mov bx,0x8 ; @04216
    jmp short loc_4224 ; @04219
loc_421B:
    cmp bx,0x148 ; @0421B
    jng loc_4224 ; @0421F
    mov bx,0x148 ; @04221
loc_4224:
    mov [0x10],bx ; @04224
    add cx,[0x12] ; @04228
    cmp cx,byte +0x8 ; @0422C
    jg loc_4236 ; @0422F
    mov cx,0x8 ; @04231
    jmp short loc_423F ; @04234
loc_4236:
    cmp cx,0xc8 ; @04236
    jng loc_423F ; @0423A
    mov cx,0xc8 ; @0423C
loc_423F:
    mov [0x12],cx ; @0423F
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04243
    test ax,0x4010 ; @04245
    jz loc_424D ; @04248
    or bx,byte +0x1 ; @0424A
loc_424D:
    mov [0x14],bx ; @0424D
    ret ; @04251
PollMousePosition:
    push es ; @04252
    push ds ; @04253
    push bp ; @04254
    push si ; @04255
    push di ; @04256
    push ax ; @04257
    push bx ; @04258
    push cx ; @04259
    push dx ; @0425A
    push ds ; @0425B
    mov ax,0x3 ; @0425C
    int 0x33 ; @0425F
    pop ds ; @04261
    cmp byte [0x200b],0xff ; @04262
    jz loc_426D ; @04267
    mov [0x14],bx ; @04269
loc_426D:
    cmp cx,byte +0x8 ; @0426D
    jnl loc_4275 ; @04270
    mov cx,0x8 ; @04272
loc_4275:
    cmp cx,0x148 ; @04275
    jng loc_427E ; @04279
    mov cx,0x148 ; @0427B
loc_427E:
    mov [0x10],cx ; @0427E
    cmp dx,byte +0x8 ; @04282
    jnl loc_428A ; @04285
    mov dx,0x8 ; @04287
loc_428A:
    cmp dx,0xc8 ; @0428A
    jng loc_4293 ; @0428E
    mov dx,0xc8 ; @04290
loc_4293:
    mov [0x12],dx ; @04293
    pop dx ; @04297
    pop cx ; @04298
    pop bx ; @04299
    pop ax ; @0429A
    pop di ; @0429B
    pop si ; @0429C
    pop bp ; @0429D
    pop ds ; @0429E
    pop es ; @0429F
    ret ; @042A0
loc_42A1:
    mov ax,[InputPollCallback-GameDataImage] ; @042A1
    push dx ; @042A4
    call ax ; @042A5
    pop dx ; @042A7
    cmp dl,0xff ; @042A8
    jnz loc_42B0 ; @042AB
    jmp loc_4333 ; @042AD
loc_42B0:
    sub bx,[0x25a2] ; @042B0
    sub cx,[0x25a4] ; @042B4
    mov al,[0x2005] ; @042B8
    cmp bx,byte +0x8 ; @042BB
    jg loc_42C5 ; @042BE
    cmp bx,byte -0x8 ; @042C0
    jnl loc_42F8 ; @042C3
loc_42C5:
    cmp al,0x2 ; @042C5
    jz loc_42D3 ; @042C7
    cmp al,0x3 ; @042C9
    jz loc_42D7 ; @042CB
    cmp al,0x4 ; @042CD
    jz loc_42D9 ; @042CF
    sar bx,1 ; @042D1
loc_42D3:
    sar bx,1 ; @042D3
    sar bx,1 ; @042D5
loc_42D7:
    sar bx,1 ; @042D7
loc_42D9:
    sar bx,1 ; @042D9
    sar bx,1 ; @042DB
    add bx,[0x10] ; @042DD
    cmp bx,byte +0x8 ; @042E1
    jg loc_42EB ; @042E4
    mov bx,0x8 ; @042E6
    jmp short loc_42F4 ; @042E9
loc_42EB:
    cmp bx,0x148 ; @042EB
    jng loc_42F4 ; @042EF
    mov bx,0x148 ; @042F1
loc_42F4:
    mov [0x10],bx ; @042F4
loc_42F8:
    cmp cx,byte +0x8 ; @042F8
    jg loc_4302 ; @042FB
    cmp cx,byte -0x8 ; @042FD
    jnl loc_4333 ; @04300
loc_4302:
    cmp al,0x2 ; @04302
    jz loc_4310 ; @04304
    cmp al,0x3 ; @04306
    jz loc_4314 ; @04308
    cmp al,0x4 ; @0430A
    jz loc_4316 ; @0430C
    sar cx,1 ; @0430E
loc_4310:
    sar cx,1 ; @04310
    sar cx,1 ; @04312
loc_4314:
    sar cx,1 ; @04314
loc_4316:
    sar cx,1 ; @04316
    add cx,[0x12] ; @04318
    cmp cx,byte +0x8 ; @0431C
    jg loc_4326 ; @0431F
    mov cx,0x8 ; @04321
    jmp short loc_432F ; @04324
loc_4326:
    cmp cx,0xc8 ; @04326
    jng loc_432F ; @0432A
    mov cx,0xc8 ; @0432C
loc_432F:
    mov [0x12],cx ; @0432F
loc_4333:
    ret ; @04333
sub_4334:
    mov byte [0x51],0x3 ; @04334
    cmp dl,0xff ; @04339
    jz loc_4341 ; @0433C
    call sub_4386 ; @0433E
loc_4341:
    cli ; @04341
    mov dx,0x201 ; @04342
    in al,dx ; @04345
    sti ; @04346
    not al ; @04347
    ror al,1 ; @04349
    ror al,1 ; @0434B
    ror al,1 ; @0434D
    ror al,1 ; @0434F
    and al,0x3 ; @04351
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04353
    mov [0x14],ax ; @04355
    ret ; @04358
sub_4359:
    mov byte [0x51],0xc ; @04359
    cmp dl,0xff ; @0435E
    jz loc_436A ; @04361
    call sub_4386 ; @04363
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @04366
    db 0x8b,0xcf ; ENCODED: mov cx,di (NASM chooses a different encoding) ; @04368
loc_436A:
    cli ; @0436A
    mov dx,0x201 ; @0436B
    in al,dx ; @0436E
    sti ; @0436F
    not al ; @04370
    ror al,1 ; @04372
    ror al,1 ; @04374
    ror al,1 ; @04376
    ror al,1 ; @04378
    ror al,1 ; @0437A
    ror al,1 ; @0437C
    and al,0x3 ; @0437E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04380
    mov [0x14],ax ; @04382
    ret ; @04385
sub_4386:
    cli ; @04386
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04387
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @04389
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0438B
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0438D
    mov dx,0x201 ; @0438F
    out dx,al ; @04392
    jmp short loc_4396 ; @04393
; UNKNOWN: unresolved bytes
    db 0x90 ; @04395
loc_4396:
    jmp short loc_4399 ; @04396
; UNKNOWN: unresolved bytes
    db 0x90 ; @04398
loc_4399:
    in al,dx ; @04399
    and al,[0x51] ; @0439A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0439E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @043A0
    and ax,0x1 ; @043A2
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @043A5
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043A7
    and ax,0x2 ; @043A9
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @043AC
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043AE
    and ax,0x4 ; @043B0
    shr ax,1 ; @043B3
    shr ax,1 ; @043B5
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @043B7
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043B9
    and ax,0x8 ; @043BB
    shr ax,1 ; @043BE
    shr ax,1 ; @043C0
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @043C2
    db 0x0b,0xed ; ENCODED: or bp,bp (NASM chooses a different encoding) ; @043C4
    jnz loc_4399 ; @043C6
    sti ; @043C8
    sar cx,1 ; @043C9
    sar di,1 ; @043CB
    ret ; @043CD
sub_43CE:
    mov al,[0x1fd0] ; @043CE
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @043D1
    jz loc_43D9 ; @043D3
    cmp al,0x77 ; @043D5
    jz loc_43EE ; @043D7
loc_43D9:
    cli ; @043D9
    mov dx,0x201 ; @043DA
    in al,dx ; @043DD
    sti ; @043DE
    not al ; @043DF
    test al,0xf0 ; @043E1
    jz sub_43CE ; @043E3
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @043E5
    test al,0x30 ; @043E7
    jnz loc_43ED ; @043E9
    inc cl ; @043EB
loc_43ED:
    ret ; @043ED
loc_43EE:
    mov cl,0x2 ; @043EE
    jmp short loc_43ED ; @043F0
sub_43F2:
    call sub_4BE7 ; @043F2
    call sub_4DEF ; @043F5
    call InstallMenuTimerVector ; @043F8
    call sub_53FC ; @043FB
    call sub_4AC5 ; @043FE
loc_4401:
    mov word [0x1f76],0x0 ; @04401
    mov word [0x1f78],0x6d60 ; @04407
    mov word [0x1f7a],0x0 ; @0440D
    call sub_4C32 ; @04413
    mov byte [0x1f6f],0xff ; @04416
    mov byte [0x1f72],0xff ; @0441B
    mov byte [0x1f70],0x0 ; @04420
    call sub_531E ; @04425
    call sub_4DEF ; @04428
    call sub_5017 ; @0442B
    call sub_7CBC ; @0442E
    call sub_4FF8 ; @04431
    call sub_4EEF ; @04434
    call sub_4F2B ; @04437
    lea si,[0x4ad9] ; @0443A
    call sub_4D4D ; @0443E
    call sub_4EA2 ; @04441
    call sub_4E37 ; @04444
    call sub_4DC2 ; @04447
    call sub_1550 ; @0444A
    call sub_4C32 ; @0444D
    call sub_536C ; @04450
loc_4453:
    mov ax,[0x14] ; @04453
    test ax,0x7 ; @04456
    jnz loc_4453 ; @04459
loc_445B:
    call sub_1550 ; @0445B
    call sub_7D0D ; @0445E
    call sub_4F96 ; @04461
    call sub_4EA2 ; @04464
    call sub_4E37 ; @04467
    call sub_4C20 ; @0446A
    mov ax,[0x14] ; @0446D
    test ax,0x7 ; @04470
    jz loc_4478 ; @04473
    jmp loc_454C ; @04475
loc_4478:
    call sub_4D1A ; @04478
    cmp al,0x80 ; @0447B
    jnz loc_4482 ; @0447D
    jmp loc_454C ; @0447F
loc_4482:
    cmp al,0x81 ; @04482
    jz loc_44AD ; @04484
    cmp al,0x82 ; @04486
    jz loc_44B3 ; @04488
    cmp al,0x83 ; @0448A
    jz loc_44B0 ; @0448C
    cmp al,0x1b ; @0448E
    jnz loc_4495 ; @04490
    jmp loc_04D0 ; @04492
loc_4495:
    cmp al,0x8a ; @04495
    jz loc_44EC ; @04497
    cmp al,0x60 ; @04499
    jz loc_44EC ; @0449B
    cmp al,0x8b ; @0449D
    jnz loc_44A4 ; @0449F
    jmp short loc_451C ; @044A1
; UNKNOWN: unresolved bytes
    db 0x90 ; @044A3
loc_44A4:
    cmp al,0x2d ; @044A4
    jnz loc_44AB ; @044A6
    jmp short loc_451C ; @044A8
; UNKNOWN: unresolved bytes
    db 0x90 ; @044AA
loc_44AB:
    jmp short loc_445B ; @044AB
loc_44AD:
    jmp loc_4967 ; @044AD
loc_44B0:
    jmp loc_4A01 ; @044B0
loc_44B3:
    cmp byte [0x1f72],0x2 ; @044B3
    jz loc_445B ; @044B8
    xor byte [0x1f70],0xff ; @044BA
    mov al,[0x1f71] ; @044BF
    inc al ; @044C2
    mov ah,0x3 ; @044C4
    cmp byte [0x2010],0xff ; @044C6
    jz loc_44CF ; @044CB
    mov ah,0x2 ; @044CD
loc_44CF:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @044CF
    jnz loc_44D5 ; @044D1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @044D3
loc_44D5:
    mov [0x1f71],al ; @044D5
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @044D8
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @044DA
    add bx,0x44e9 ; @044DC
    mov al,[cs:bx] ; @044E0
    mov [0x25a7],al ; @044E3
    jmp loc_445B ; @044E6
; UNKNOWN: unresolved bytes
    db 0x00,0x01,0x03 ; @044E9
loc_44EC:
    cmp byte [0x1f6f],0x4 ; @044EC
    jnz loc_44F6 ; @044F1
    jmp loc_445B ; @044F3
loc_44F6:
    mov al,[0x1f6e] ; @044F6
    cmp al,0x3 ; @044F9
    jnz loc_4500 ; @044FB
    jmp loc_445B ; @044FD
loc_4500:
    inc al ; @04500
    mov [0x1f6e],al ; @04502
    shl al,1 ; @04505
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @04507
    shl al,1 ; @04509
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0450B
    shl al,1 ; @0450D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0450F
    shl al,1 ; @04511
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04513
    mov [LevelResourceSelectionByte-GameDataImage],ah ; @04515
    jmp loc_445B ; @04519
loc_451C:
    cmp byte [0x1f6f],0x4 ; @0451C
    jnz loc_4526 ; @04521
    jmp loc_445B ; @04523
loc_4526:
    mov al,[0x1f6e] ; @04526
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04529
    jnz loc_4530 ; @0452B
    jmp loc_445B ; @0452D
loc_4530:
    dec al ; @04530
    mov [0x1f6e],al ; @04532
    shl al,1 ; @04535
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @04537
    shl al,1 ; @04539
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0453B
    shl al,1 ; @0453D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0453F
    shl al,1 ; @04541
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04543
    mov [LevelResourceSelectionByte-GameDataImage],ah ; @04545
    jmp loc_445B ; @04549
loc_454C:
    mov byte [0x1f6d],0x0 ; @0454C
loc_4551:
    push ds ; @04551
    pop es ; @04552
    mov di,0x0 ; @04553
    mov cx,0xfca ; @04556
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04559
    rep stosb ; @0455B
    call LoadSelectedLevelResources ; @0455D
    call sub_4566 ; @04560
    jmp loc_00FB ; @04563
sub_4566:
    mov al,[0x1f6e] ; @04566
    shl al,1 ; @04569
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0456B
    shl al,1 ; @0456D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0456F
    shl al,1 ; @04571
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04573
    shl al,1 ; @04575
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04577
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @04579
    inc al ; @0457C
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @0457E
    lea si,[0x4b13] ; @04580
    call sub_4BBE ; @04584
    mov al,[0xfce] ; @04587
    lea si,[0x4b50] ; @0458A
    call sub_4B68 ; @0458E
    mov al,[0xfd0] ; @04591
    mov cl,0x64 ; @04594
    mul cl ; @04596
    mov cl,[0xfce] ; @04598
    div cl ; @0459C
    mov [0x41],al ; @0459E
    lea si,[0x4b57] ; @045A1
    call sub_4B5C ; @045A5
    mov al,[0xfcc] ; @045A8
    lea si,[0x4b78] ; @045AB
    call sub_4BBE ; @045AF
    mov al,[0xfd2] ; @045B2
    add al,0x30 ; @045B5
    mov [0x4b83],al ; @045B7
    mov ah,0x73 ; @045BA
    cmp al,0x31 ; @045BC
    jnz loc_45C2 ; @045BE
    mov ah,0x20 ; @045C0
loc_45C2:
    mov [0x4b8b],ah ; @045C2
    lea si,[0x17ab] ; @045C6
    lea di,[0x4b19] ; @045CA
    push ds ; @045CE
    pop es ; @045CF
    mov cx,0x10 ; @045D0
    rep movsw ; @045D3
    mov al,[0x1f6e] ; @045D5
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @045D8
    mov cx,0x6 ; @045DA
    mul cx ; @045DD
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @045DF
    lea si,[0x4b98] ; @045E1
loc_45E5:
    mov al,[bx+0x4c01] ; @045E5
    mov [si],al ; @045E9
    inc bx ; @045EB
    inc si ; @045EC
    loop loc_45E5 ; @045ED
    call sub_4DEF ; @045EF
loc_45F2:
    mov cx,0x10 ; @045F2
    mov dx,0x10 ; @045F5
    call sub_5329 ; @045F8
    jnz loc_45F2 ; @045FB
    mov al,0x1 ; @045FD
    nop ; @045FF
    call sub_53FE ; @04600
    mov word [0x1f76],0x0 ; @04603
    mov word [0x1f78],0x0 ; @04609
    call sub_4C20 ; @0460F
    call sub_394F ; @04612
    mov word [0x1f76],0x0 ; @04615
    mov word [0x1f7a],0x0 ; @0461B
    call sub_7EB2 ; @04621
    mov word [0x1f76],0x0 ; @04624
    mov word [0x1f7a],0x0 ; @0462A
    call sub_4C17 ; @04630
    call sub_4C07 ; @04633
    mov bx,0x4e ; @04636
    call sub_5019 ; @04639
    lea si,[0x4b0a] ; @0463C
    call sub_4D4D ; @04640
    lea si,[0x4ba0] ; @04643
    cmp byte [0x25a6],0x0 ; @04647
    jz loc_465D ; @0464C
    lea si,[0x4bc3] ; @0464E
    cmp byte [0x25a6],0x1 ; @04652
    jz loc_465D ; @04657
    lea si,[0x4be5] ; @04659
loc_465D:
    call sub_4D4D ; @0465D
loc_4660:
    mov ax,[0x14] ; @04660
    test ax,0x7 ; @04663
    jnz loc_4660 ; @04666
loc_4668:
    call sub_46B9 ; @04668
    mov al,0x0 ; @0466B
    nop ; @0466D
    call sub_53CA ; @0466E
    mov cx,0x10 ; @04671
    mov dx,0x10 ; @04674
    mov bx,0x302 ; @04677
    nop ; @0467A
    call sub_534B ; @0467B
    jnz loc_4668 ; @0467E
loc_4680:
    call sub_46B9 ; @04680
    mov ax,[0x14] ; @04683
    test ax,0x7 ; @04686
    jnz sub_46A2 ; @04689
    mov ax,[0x1fc7] ; @0468B
    test ax,0x20 ; @0468E
    jnz loc_469B ; @04691
    test ax,0x40 ; @04693
    jz loc_4680 ; @04696
    jmp short sub_46A2 ; @04698
; UNKNOWN: unresolved bytes
    db 0x90 ; @0469A
loc_469B:
    call sub_46A2 ; @0469B
    pop ax ; @0469E
    jmp loc_4401 ; @0469F
sub_46A2:
    call sub_46B9 ; @046A2
    mov al,0x0 ; @046A5
    nop ; @046A7
    call sub_53CA ; @046A8
    mov cx,0x10 ; @046AB
    mov dx,0x10 ; @046AE
    call sub_5329 ; @046B1
    jnz sub_46A2 ; @046B4
    jmp sub_4DEF ; @046B6
sub_46B9:
    mov dx,[0x1fda] ; @046B9
    add dl,0x6 ; @046BD
loc_46C0:
    in al,dx ; @046C0
    test al,0x8 ; @046C1
    jz loc_46C0 ; @046C3
loc_46C5:
    in al,dx ; @046C5
    test al,0x8 ; @046C6
    jnz loc_46C5 ; @046C8
    cli ; @046CA
    push dx ; @046CB
    mov al,0x0 ; @046CC
    nop ; @046CE
    call sub_53F6 ; @046CF
    pop dx ; @046D2
    cli ; @046D3
    mov cx,0x3c ; @046D4
loc_46D7:
    in al,dx ; @046D7
    test al,0x1 ; @046D8
    jnz loc_46D7 ; @046DA
loc_46DC:
    in al,dx ; @046DC
    test al,0x1 ; @046DD
    jz loc_46DC ; @046DF
    loop loc_46D7 ; @046E1
    mov al,0x7 ; @046E3
    nop ; @046E5
    call sub_53F6 ; @046E6
    sti ; @046E9
    ret ; @046EA
loc_46EB:
    call sub_4DEF ; @046EB
    call sub_4BE7 ; @046EE
    call sub_53FC ; @046F1
    call sub_531E ; @046F4
    call sub_4DEF ; @046F7
    call InstallMenuTimerVector ; @046FA
    call sub_5017 ; @046FD
    call sub_48BD ; @04700
    lea si,[0x4c19] ; @04703
    mov al,[0x20a7] ; @04707
    mov bx,[0x20a9] ; @0470A
    db 0x0a,0xd8 ; ENCODED: or bl,al (NASM chooses a different encoding) ; @0470E
    cmp bx,0x3030 ; @04710
    jz loc_471A ; @04714
    lea si,[0x4c2e] ; @04716
loc_471A:
    call sub_4D4D ; @0471A
    mov al,[0x40] ; @0471D
    cmp al,[0x41] ; @04720
    jnl loc_4729 ; @04724
    jmp short loc_4778 ; @04726
; UNKNOWN: unresolved bytes
    db 0x90 ; @04728
loc_4729:
    mov byte [0x1f6d],0xff ; @04729
    inc byte [LevelResourceSelectionByte-GameDataImage] ; @0472E
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @04732
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04735
    mov cl,0x1e ; @04737
    div cl ; @04739
    mov [0x1f6e],al ; @0473B
    cmp byte [LevelResourceSelectionByte-GameDataImage],0x78 ; @0473E
    jc loc_4748 ; @04743
    jmp loc_47E0 ; @04745
loc_4748:
    call sub_488C ; @04748
    lea si,[0x4d5d] ; @0474B
    call sub_4B68 ; @0474F
    call sub_5042 ; @04752
    lea si,[0x4d3f] ; @04755
    call sub_4D4D ; @04759
    lea bx,[0x4d75] ; @0475C
    cmp byte [0x25a6],0x0 ; @04760
    jz loc_4776 ; @04765
    lea bx,[0x4da0] ; @04767
    cmp byte [0x25a6],0x1 ; @0476B
    jz loc_4776 ; @04770
    lea bx,[0x4dc2] ; @04772
loc_4776:
    jmp short loc_4797 ; @04776
loc_4778:
    mov byte [0x1f6d],0x0 ; @04778
    lea bx,[0x4cd3] ; @0477D
    cmp byte [0x25a6],0x0 ; @04781
    jz loc_4797 ; @04786
    lea bx,[0x4cfe] ; @04788
    cmp byte [0x25a6],0x1 ; @0478C
    jz loc_4797 ; @04791
    lea bx,[0x4d20] ; @04793
loc_4797:
    push bx ; @04797
    call sub_48F6 ; @04798
    pop si ; @0479B
    call sub_4D4D ; @0479C
    mov si,[0x21] ; @0479F
    call sub_4D4D ; @047A3
    call sub_536C ; @047A6
loc_47A9:
    mov ax,[0x14] ; @047A9
    test ax,0x7 ; @047AC
    jnz loc_47A9 ; @047AF
loc_47B1:
    mov ax,[0x14] ; @047B1
    test ax,0x1 ; @047B4
    jnz loc_47D7 ; @047B7
    test ax,0x2 ; @047B9
    jnz loc_47CB ; @047BC
    mov ax,[0x1fc7] ; @047BE
    test ax,0x20 ; @047C1
    jnz loc_47CB ; @047C4
    test ax,0x40 ; @047C6
    jz loc_47B1 ; @047C9
loc_47CB:
    call sub_531E ; @047CB
    call sub_4DEF ; @047CE
    call sub_4BE7 ; @047D1
    jmp loc_4401 ; @047D4
loc_47D7:
    call sub_531E ; @047D7
    call sub_4DEF ; @047DA
    jmp loc_4551 ; @047DD
loc_47E0:
    call sub_5017 ; @047E0
    lea si,[0x51cb] ; @047E3
    call sub_4D4D ; @047E7
    lea si,[0x4ba0] ; @047EA
    cmp byte [0x25a6],0x0 ; @047EE
    jz loc_4804 ; @047F3
    lea si,[0x4bc3] ; @047F5
    cmp byte [0x25a6],0x1 ; @047F9
    jz loc_4804 ; @047FE
    lea si,[0x4be5] ; @04800
loc_4804:
    call sub_4D4D ; @04804
    call sub_536C ; @04807
loc_480A:
    mov ax,[0x14] ; @0480A
    test ax,0x7 ; @0480D
    jnz loc_481F ; @04810
    mov ax,[0x1fc7] ; @04812
    test ax,0x20 ; @04815
    jnz loc_481F ; @04818
    test ax,0x40 ; @0481A
    jz loc_480A ; @0481D
loc_481F:
    call sub_531E ; @0481F
    mov byte [LevelResourceSelectionByte-GameDataImage],0x0 ; @04822
    mov byte [0x1f6e],0x0 ; @04827
    jmp loc_4401 ; @0482C
sub_482F:
    cmp byte [0x2010],0x0 ; @0482F
    jz loc_4865 ; @04834
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @04836
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04839
    jz loc_4840 ; @0483B
    jmp short loc_4866 ; @0483D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0483F
loc_4840:
    cmp byte [0x1f6d],0x0 ; @04840
    jz loc_4855 ; @04845
    mov al,[0x1f6c] ; @04847
    inc al ; @0484A
    cmp al,0x11 ; @0484C
    jnz loc_4852 ; @0484E
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04850
loc_4852:
    mov [0x1f6c],al ; @04852
loc_4855:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04855
    push ax ; @04857
    lea bx,[0x4877] ; @04858
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0485C
    mov al,[cs:bx] ; @0485E
    mov [0x54],al ; @04861
    pop ax ; @04864
loc_4865:
    ret ; @04865
loc_4866:
    dec al ; @04866
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04868
    lea bx,[0x4888] ; @0486A
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0486E
    mov al,[cs:bx] ; @04870
    mov [0x54],al ; @04873
    ret ; @04876
; UNKNOWN: unresolved bytes
    db 0x06,0x07,0x08,0x0a,0x0b,0x04,0x0c,0x0d,0x0e,0x0f,0x05,0x10,0x11,0x12,0x13,0x14 ; @04877
; UNKNOWN: unresolved bytes
    db 0x15,0x01,0x09,0x03,0x02 ; @04887
sub_488C:
    push cx ; @0488C
    mov cl,0x1e ; @0488D
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @0488F
    inc al ; @04892
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04894
    div cl ; @04896
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @04898
    mul cl ; @0489A
    mov cl,[LevelResourceSelectionByte-GameDataImage] ; @0489C
    inc cl ; @048A0
    db 0x2a,0xc8 ; ENCODED: sub cl,al (NASM chooses a different encoding) ; @048A2
    db 0x8b,0xc1 ; ENCODED: mov ax,cx (NASM chooses a different encoding) ; @048A4
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @048A6
    jnz loc_48AE ; @048A8
    mov al,0x1e ; @048AA
    dec ah ; @048AC
loc_48AE:
    pop cx ; @048AE
    ret ; @048AF
; UNKNOWN: unresolved bytes
    db 0x51,0xb1,0x1e,0x8a,0xe8,0x8a,0xc4,0xf6,0xe1,0x02,0xc5,0x59,0xc3 ; @048B0
sub_48BD:
    mov al,[0x40] ; @048BD
    lea si,[0x4c5d] ; @048C0
    call sub_4B5C ; @048C4
    mov al,[0x41] ; @048C7
    lea si,[0x4c71] ; @048CA
    call sub_4B5C ; @048CE
    lea si,[0x4c77] ; @048D1
    cmp byte [0x25a6],0x0 ; @048D5
    jz loc_48EB ; @048DA
    lea si,[0x4c9d] ; @048DC
    cmp byte [0x25a6],0x1 ; @048E0
    jz loc_48EB ; @048E5
    lea si,[0x4cb9] ; @048E7
loc_48EB:
    mov [0x21],si ; @048EB
    lea si,[0x4c4e] ; @048EF
    jmp sub_4D4D ; @048F3
sub_48F6:
    mov al,[0x40] ; @048F6
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @048F9
    mov dl,[0x41] ; @048FB
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @048FF
    mov bx,0x10 ; @04901
    cmp ax,0x64 ; @04904
    jz loc_494D ; @04907
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04909
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @0490B
    jz loc_494D ; @0490D
    add bx,byte +0x2 ; @0490F
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04912
    shr cx,1 ; @04914
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04916
    jl loc_494D ; @04918
    add bx,byte +0x2 ; @0491A
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @0491D
    sub cx,byte +0x5 ; @0491F
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04922
    jl loc_494D ; @04924
    add bx,byte +0x2 ; @04926
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04929
    dec cx ; @0492B
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @0492C
    jl loc_494D ; @0492E
    add bx,byte +0x2 ; @04930
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04933
    jz loc_494D ; @04935
    add bx,byte +0x2 ; @04937
    db 0x3b,0xc2 ; ENCODED: cmp ax,dx (NASM chooses a different encoding) ; @0493A
    jz loc_494D ; @0493C
    add bx,byte +0x2 ; @0493E
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04941
    add cx,byte +0x14 ; @04943
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04946
    jl loc_494D ; @04948
    add bx,byte +0x2 ; @0494A
loc_494D:
    mov si,[cs:bx+0x4955] ; @0494D
    jmp sub_4D4D ; @04952
; UNKNOWN: unresolved bytes
    db 0x33,0x4f,0x77,0x4f,0xbc,0x4f,0x03,0x50,0x4e,0x50,0x91,0x50,0xde,0x50,0x2c,0x51 ; @04955
; UNKNOWN: unresolved bytes
    db 0x7a,0x51 ; @04965
loc_4967:
    call sub_4DEF ; @04967
    call sub_4BF5 ; @0496A
    call sub_531E ; @0496D
    call sub_4DEF ; @04970
    call sub_5017 ; @04973
    lea si,[0x4df2] ; @04976
    mov cx,0xa ; @0497A
loc_497D:
    mov byte [si],0x2e ; @0497D
    inc si ; @04980
    loop loc_497D ; @04981
    lea si,[0x4de1] ; @04983
    call sub_4D4D ; @04987
    call sub_4DC2 ; @0498A
    call sub_1550 ; @0498D
    call sub_4C32 ; @04990
    call sub_536C ; @04993
    call ReadCodeInput ; @04996
    call sub_51A2 ; @04999
    jnz loc_49EC ; @0499C
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @0499E
    call sub_488C ; @049A1
    push ax ; @049A4
    lea si,[0x4e10] ; @049A5
    call sub_4B68 ; @049A9
    pop ax ; @049AC
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @049AD
    lea di,[0x4e1f] ; @049AF
    lea si,[0x4c01] ; @049B3
    push ds ; @049B7
    pop es ; @049B8
    mov cx,0x6 ; @049B9
    mul cl ; @049BC
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @049BE
    rep movsb ; @049C0
    lea si,[0x4dfe] ; @049C2
    call sub_4D4D ; @049C6
    call sub_4C20 ; @049C9
    mov cx,0x78 ; @049CC
loc_49CF:
    call sub_1550 ; @049CF
    mov ax,[0x14] ; @049D2
    test ax,0x7 ; @049D5
    jnz loc_49E9 ; @049D8
    mov ax,[0x1fc7] ; @049DA
    test ax,0x20 ; @049DD
    jnz loc_49E9 ; @049E0
    test ax,0x40 ; @049E2
    jnz loc_49E9 ; @049E5
    loop loc_49CF ; @049E7
loc_49E9:
    jmp loc_4401 ; @049E9
loc_49EC:
    lea si,[0x4e27] ; @049EC
    call sub_4D4D ; @049F0
    call sub_4C20 ; @049F3
    mov cx,0x3c ; @049F6
loc_49F9:
    call sub_1550 ; @049F9
    loop loc_49F9 ; @049FC
    jmp loc_4401 ; @049FE
loc_4A01:
    call sub_4DEF ; @04A01
    call sub_4BF5 ; @04A04
    call sub_531E ; @04A07
    call sub_5017 ; @04A0A
    lea si,[0x4e3a] ; @04A0D
    call sub_4D4D ; @04A11
    cmp byte [0x1f73],0xff ; @04A14
    jz loc_4A22 ; @04A19
    lea si,[0x4e6e] ; @04A1B
    call sub_4D4D ; @04A1F
loc_4A22:
    call sub_4DC2 ; @04A22
    call sub_1550 ; @04A25
    call sub_4C32 ; @04A28
    call sub_536C ; @04A2B
loc_4A2E:
    call sub_1550 ; @04A2E
    call sub_4D1A ; @04A31
    cmp byte [0x1f73],0xff ; @04A34
    jz loc_4A3F ; @04A39
    cmp al,0x31 ; @04A3B
    jz loc_4ABD ; @04A3D
loc_4A3F:
    cmp al,0x32 ; @04A3F
    jz loc_4A4E ; @04A41
    cmp al,0x33 ; @04A43
    jz loc_4AB5 ; @04A45
    cmp al,0x1b ; @04A47
    jnz loc_4A2E ; @04A49
    jmp loc_4401 ; @04A4B
loc_4A4E:
    lea si,[0x4e85] ; @04A4E
    call sub_4D4D ; @04A52
    call sub_4C20 ; @04A55
    call sub_43CE ; @04A58
    cmp cl,0x2 ; @04A5B
    jz loc_4AB5 ; @04A5E
    cmp cl,0x1 ; @04A60
    jz loc_4A7D ; @04A63
    mov ax,0x4334 ; @04A65
    mov [InputPollCallback-GameDataImage],ax ; @04A68
    mov al,0x1 ; @04A6B
    mov [0x25a6],al ; @04A6D
    call sub_4334 ; @04A70
    mov [0x25a2],bx ; @04A73
    mov [0x25a4],cx ; @04A77
    jmp short loc_4A95 ; @04A7B
loc_4A7D:
    mov ax,0x4359 ; @04A7D
    mov [InputPollCallback-GameDataImage],ax ; @04A80
    mov al,0x1 ; @04A83
    mov [0x25a6],al ; @04A85
    call sub_4359 ; @04A88
    mov [0x25a2],bx ; @04A8B
    mov [0x25a4],cx ; @04A8F
    jmp short loc_4A95 ; @04A93
loc_4A95:
    lea si,[0x4ea9] ; @04A95
    call sub_4D4D ; @04A99
    call sub_4C20 ; @04A9C
loc_4A9F:
    call sub_1550 ; @04A9F
    call sub_4D1A ; @04AA2
    cmp al,0x31 ; @04AA5
    jc loc_4A9F ; @04AA7
    cmp al,0x34 ; @04AA9
    ja loc_4A9F ; @04AAB
    sub al,0x30 ; @04AAD
    mov [0x2005],al ; @04AAF
    jmp loc_4401 ; @04AB2
loc_4AB5:
    mov byte [0x25a6],0x2 ; @04AB5
    jmp loc_4401 ; @04ABA
loc_4ABD:
    mov byte [0x25a6],0x0 ; @04ABD
    jmp loc_4401 ; @04AC2
sub_4AC5:
    cmp byte [0x1fde],0xfd ; @04AC5
    jnz loc_4B1B ; @04ACA
    call sub_531E ; @04ACC
loc_4ACF:
    call sub_4DEF ; @04ACF
    call sub_5017 ; @04AD2
    lea si,[0x4f00] ; @04AD5
    call sub_4D4D ; @04AD9
    call sub_4DC2 ; @04ADC
    call sub_1550 ; @04ADF
    call sub_4C32 ; @04AE2
    call sub_536C ; @04AE5
    mov byte [0x1fd0],0x0 ; @04AE8
loc_4AED:
    mov ax,[0x14] ; @04AED
    test ax,0x7 ; @04AF0
    jnz loc_4AFD ; @04AF3
    mov ah,[0x1fd0] ; @04AF5
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04AF9
    jz loc_4AED ; @04AFB
loc_4AFD:
    lea dx,[0x2534] ; @04AFD
    mov ax,0x3d00 ; @04B01
    int 0x21 ; @04B04
    jc loc_4ACF ; @04B06
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @04B08
    mov ah,0x3e ; @04B0A
    int 0x21 ; @04B0C
    jc loc_4ACF ; @04B0E
    call sub_531E ; @04B10
    call sub_4DEF ; @04B13
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @04B16
loc_4B1B:
    ret ; @04B1B
sub_4B1C:
    call sub_4BE7 ; @04B1C
    call sub_531E ; @04B1F
    call sub_4DEF ; @04B22
    call sub_5017 ; @04B25
    lea si,[0x4ecf] ; @04B28
    call sub_4D4D ; @04B2C
    call sub_4DC2 ; @04B2F
    call sub_1550 ; @04B32
    call sub_4C32 ; @04B35
    call sub_536C ; @04B38
    mov byte [0x1fd0],0x0 ; @04B3B
loc_4B40:
    mov ax,[0x14] ; @04B40
    test ax,0x7 ; @04B43
    jnz loc_4B50 ; @04B46
    mov ah,[0x1fd0] ; @04B48
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04B4C
    jz loc_4B40 ; @04B4E
loc_4B50:
    call sub_531E ; @04B50
    call sub_4DEF ; @04B53
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @04B56
    ret ; @04B5B
sub_4B5C:
    mov byte [si+0x3],0x20 ; @04B5C
    call sub_4B68 ; @04B60
    mov byte [si],0x25 ; @04B63
    inc si ; @04B66
    ret ; @04B67
sub_4B68:
    mov byte [si],0x20 ; @04B68
    mov byte [si+0x1],0x20 ; @04B6B
    mov byte [si+0x2],0x20 ; @04B6F
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04B73
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @04B75
loc_4B77:
    inc ah ; @04B77
    sub al,0x64 ; @04B79
    jnc loc_4B77 ; @04B7B
    add al,0x64 ; @04B7D
    dec ah ; @04B7F
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04B81
    jnz loc_4B89 ; @04B83
    mov ah,0x20 ; @04B85
    jmp short loc_4B91 ; @04B87
loc_4B89:
    add ah,0x30 ; @04B89
    inc bl ; @04B8C
    mov [si],ah ; @04B8E
    inc si ; @04B90
loc_4B91:
    mov byte [si],0x20 ; @04B91
    mov byte [si+0x1],0x20 ; @04B94
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04B98
loc_4B9A:
    inc ah ; @04B9A
    sub al,0xa ; @04B9C
    jnc loc_4B9A ; @04B9E
    add al,0xa ; @04BA0
    dec ah ; @04BA2
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04BA4
    jnz loc_4BB0 ; @04BA6
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @04BA8
    jnz loc_4BB0 ; @04BAA
    mov ah,0x20 ; @04BAC
    jmp short loc_4BB8 ; @04BAE
loc_4BB0:
    add ah,0x30 ; @04BB0
    inc bl ; @04BB3
    mov [si],ah ; @04BB5
    inc si ; @04BB7
loc_4BB8:
    add al,0x30 ; @04BB8
    mov [si],al ; @04BBA
    inc si ; @04BBC
    ret ; @04BBD
sub_4BBE:
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @04BBE
    jmp short loc_4B91 ; @04BC0
; CONTRACT: AL unsigned byte ->three ASCII digits atDS:SI; incoming AH discarded.
; AX returns tens ASCII inAH, units ASCII inAL; SI advances2 with16-bit wrap.
; Writes are live and increment forwards even withDF set. Other registers/segments
; are unchanged; final ADD AL,30 defines arithmetic flags, preserves control flags.
; Native C and active-return alias checks: tests/decimal_digits_c.py.
; Separate original-only contract check: tests/decimal_digits.py; docs/decimal-digits.md.
WriteDecimalByteDigits:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04BC2
loc_4BC4:
    inc ah ; @04BC4
    sub al,0x64 ; @04BC6
    jnc loc_4BC4 ; @04BC8
    add al,0x64 ; @04BCA
    add ah,0x2f ; @04BCC
    mov [si],ah ; @04BCF
    inc si ; @04BD1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04BD2
loc_4BD4:
    inc ah ; @04BD4
    sub al,0xa ; @04BD6
    jnc loc_4BD4 ; @04BD8
    add al,0xa ; @04BDA
    add ah,0x2f ; @04BDC
    mov [si],ah ; @04BDF
    inc si ; @04BE1
    add al,0x30 ; @04BE2
    mov [si],al ; @04BE4
    ret ; @04BE6
sub_4BE7:
    mov byte [cs:0x83be],0xff ; @04BE7
    nop ; @04BED
    cli ; @04BEE
    mov ax,0x90 ; @04BEF
    int 0x10 ; @04BF2
    sti ; @04BF4
sub_4BF5:
    mov word [0x1f76],0x0 ; @04BF5
    mov word [0x1f78],0x6d60 ; @04BFB
    mov word [0x1f7a],0x0 ; @04C01
sub_4C07:
    mov ax,0x280 ; @04C07
    mov bx,0x15e ; @04C0A
    mov dx,[0x1f76] ; @04C0D
    call 0x0:0x8808 ; @04C11
    ret ; @04C16
sub_4C17:
    mov di,0x15e0 ; @04C17
    mov cx,0x5780 ; @04C1A
    jmp sub_4DF8 ; @04C1D
sub_4C20:
    mov bx,[0x1f76] ; @04C20
    call sub_4C36 ; @04C24
    mov ax,[0x1f76] ; @04C27
    xchg [0x1f78],ax ; @04C2A
    mov [0x1f76],ax ; @04C2E
    ret ; @04C31
sub_4C32:
    mov bx,[0x1f78] ; @04C32
sub_4C36:
    cli ; @04C36
    mov dx,[0x1fda] ; @04C37
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @04C3B
    mov al,0xc ; @04C3D
    out dx,ax ; @04C3F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @04C40
    inc al ; @04C42
    out dx,ax ; @04C44
    sti ; @04C45
    ret ; @04C46
MenuTimerIrqHandler:
    push ax ; @04C47
    push bx ; @04C48
    push cx ; @04C49
    push dx ; @04C4A
    push si ; @04C4B
    push di ; @04C4C
    push bp ; @04C4D
    push ds ; @04C4E
    mov ax,0x9a9 ; @04C4F
    mov ds,ax ; @04C52
    mov al,[0x1fe3] ; @04C54
    inc al ; @04C57
    and al,0x3 ; @04C59
    mov [0x1fe3],al ; @04C5B
    jnz loc_4C66 ; @04C5E
    call sub_18B2 ; @04C60
    jmp short loc_4C70 ; @04C63
; UNKNOWN: unresolved bytes
    db 0x90 ; @04C65
loc_4C66:
    mov ax,0x4c70 ; @04C66
    pushf ; @04C69
    push cs ; @04C6A
    push ax ; @04C6B
    jmp far [SavedTimerVector-GameDataImage] ; @04C6C
loc_4C70:
    mov dl,0xff ; @04C70
    call sub_418C ; @04C72
    pop ds ; @04C75
    pop bp ; @04C76
    pop di ; @04C77
    pop si ; @04C78
    pop dx ; @04C79
    pop cx ; @04C7A
    pop bx ; @04C7B
    pop ax ; @04C7C
    iret ; @04C7D
ReadCodeInput:
    lea si,[0x4df2] ; @04C7E
    mov cx,0xa ; @04C82
    mov bx,0x5a41 ; @04C85
    lea bp,[0x503b] ; @04C88
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04C8C
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @04C8E
    db 0x03,0xd1 ; ENCODED: add dx,cx (NASM chooses a different encoding) ; @04C90
    mov cx,0x5f2e ; @04C92
    mov byte [0x491e],0x14 ; @04C95
loc_4C9A:
    push si ; @04C9A
    push di ; @04C9B
    push bx ; @04C9C
    push cx ; @04C9D
    push dx ; @04C9E
    push bp ; @04C9F
loc_4CA0:
    push di ; @04CA0
    push si ; @04CA1
    push cx ; @04CA2
    push dx ; @04CA3
    push bp ; @04CA4
    call sub_1550 ; @04CA5
    pop bp ; @04CA8
    pop dx ; @04CA9
    pop cx ; @04CAA
    pop si ; @04CAB
    pop di ; @04CAC
    dec byte [0x491e] ; @04CAD
    jnz loc_4CC4 ; @04CB1
    mov byte [0x491e],0x14 ; @04CB3
    mov al,[di] ; @04CB8
    db 0x3a,0xc1 ; ENCODED: cmp al,cl (NASM chooses a different encoding) ; @04CBA
    jz loc_4CC2 ; @04CBC
    mov [di],cl ; @04CBE
    jmp short loc_4CC4 ; @04CC0
loc_4CC2:
    mov [di],ch ; @04CC2
loc_4CC4:
    push di ; @04CC4
    push si ; @04CC5
    push cx ; @04CC6
    push dx ; @04CC7
    push bp ; @04CC8
    call bp ; @04CC9
    call sub_4C20 ; @04CCB
    call sub_4D1A ; @04CCE
    pop bp ; @04CD1
    pop dx ; @04CD2
    pop cx ; @04CD3
    pop si ; @04CD4
    pop di ; @04CD5
    cmp al,0xff ; @04CD6
    jz loc_4CA0 ; @04CD8
    pop bp ; @04CDA
    pop dx ; @04CDB
    pop cx ; @04CDC
    pop bx ; @04CDD
    pop di ; @04CDE
    pop si ; @04CDF
    cmp al,0x7f ; @04CE0
    jz loc_4D02 ; @04CE2
    cmp al,0xd ; @04CE4
    jz loc_4D10 ; @04CE6
    db 0x3a,0xc3 ; ENCODED: cmp al,bl (NASM chooses a different encoding) ; @04CE8
    jl loc_4C9A ; @04CEA
    db 0x3a,0xc7 ; ENCODED: cmp al,bh (NASM chooses a different encoding) ; @04CEC
    jg loc_4C9A ; @04CEE
    db 0x3b,0xfa ; ENCODED: cmp di,dx (NASM chooses a different encoding) ; @04CF0
    jz loc_4C9A ; @04CF2
    mov [di],al ; @04CF4
    inc di ; @04CF6
    mov cl,[di] ; @04CF7
    db 0x3b,0xfa ; ENCODED: cmp di,dx (NASM chooses a different encoding) ; @04CF9
    jnz loc_4C9A ; @04CFB
    dec di ; @04CFD
    mov cl,[di] ; @04CFE
    jmp short loc_4C9A ; @04D00
loc_4D02:
    mov byte [di],0x2e ; @04D02
    mov cl,0x2e ; @04D05
    db 0x3b,0xfe ; ENCODED: cmp di,si (NASM chooses a different encoding) ; @04D07
    jz loc_4C9A ; @04D09
    dec di ; @04D0B
    mov cl,[di] ; @04D0C
    jmp short loc_4C9A ; @04D0E
loc_4D10:
    mov word [0x1fc7],0x0 ; @04D10
    mov [di],cl ; @04D16
    jmp bp ; @04D18
sub_4D1A:
    lea si,[0xf78] ; @04D1A
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04D1E
    mov cx,0x53 ; @04D20
loc_4D23:
    test byte [bx+si],0x80 ; @04D23
    jnz loc_4D2E ; @04D26
loc_4D28:
    inc bx ; @04D28
    loop loc_4D23 ; @04D29
    mov al,0xff ; @04D2B
    ret ; @04D2D
loc_4D2E:
    mov al,[bx+si] ; @04D2E
    and al,0x7f ; @04D30
    dec al ; @04D32
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D34
    jz loc_4D42 ; @04D36
    or al,0x80 ; @04D38
    mov [bx+si],al ; @04D3A
    cmp al,0x93 ; @04D3C
    jz loc_4D45 ; @04D3E
    jmp short loc_4D28 ; @04D40
loc_4D42:
    mov byte [bx+si],0x86 ; @04D42
loc_4D45:
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @04D45
    lea bx,[0x202e] ; @04D47
    xlatb ; @04D4B
    ret ; @04D4C
sub_4D4D:
    lodsb ; @04D4D
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D4E
    jz loc_4D77 ; @04D50
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @04D52
    dec cl ; @04D54
    lodsb ; @04D56
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @04D57
    lodsb ; @04D59
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D5A
    jnz loc_4D63 ; @04D5C
    mov bp,0x2 ; @04D5E
    jmp short loc_4D65 ; @04D61
loc_4D63:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @04D63
loc_4D65:
    lodsb ; @04D65
    cmp al,0xd ; @04D66
    jz sub_4D4D ; @04D68
    push cx ; @04D6A
    push bx ; @04D6B
    push si ; @04D6C
    call sub_4D78 ; @04D6D
    pop si ; @04D70
    pop bx ; @04D71
    pop cx ; @04D72
    inc cl ; @04D73
    jmp short loc_4D65 ; @04D75
loc_4D77:
    ret ; @04D77
sub_4D78:
    cmp al,0x20 ; @04D78
    jz loc_4DC1 ; @04D7A
    sub al,0x21 ; @04D7C
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04D7E
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D80
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D82
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D84
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D86
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D88
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @04D8A
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D8C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @04D8E
    add si,0x5bc0 ; @04D90
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04D94
    add di,byte +0x40 ; @04D96
    mov bx,[0x1fee] ; @04D99
    add bx,0x1000 ; @04D9D
    mov [0x1fe4],bx ; @04DA1
    db 0x8a,0xdd ; ENCODED: mov bl,ch (NASM chooses a different encoding) ; @04DA5
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @04DA7
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @04DA9
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04DAB
    mov cl,0x4 ; @04DAD
    shl bx,cl ; @04DAF
    shl ax,cl ; @04DB1
    mov cl,0x10 ; @04DB3
    mov ch,0x3 ; @04DB5
    mov dx,0x10 ; @04DB7
    push bp ; @04DBA
    call 0x0:0x8822 ; @04DBB
    pop bp ; @04DC0
loc_4DC1:
    ret ; @04DC1
sub_4DC2:
    mov dx,0x3c4 ; @04DC2
    mov ax,0xf02 ; @04DC5
    mov [ss:0x8],ax ; @04DC8
    out dx,ax ; @04DCC
    mov dx,0x3ce ; @04DCD
    mov ax,0x105 ; @04DD0
    mov [ss:0x0],ax ; @04DD3
    out dx,ax ; @04DD7
    push ds ; @04DD8
    mov si,[0x1f76] ; @04DD9
    mov di,[0x1f78] ; @04DDD
    mov ax,0xa000 ; @04DE1
    mov ds,ax ; @04DE4
    mov es,ax ; @04DE6
    mov cx,0x6d60 ; @04DE8
    rep movsb ; @04DEB
    pop ds ; @04DED
    ret ; @04DEE
sub_4DEF:
    mov di,0x0 ; @04DEF
    mov cx,0x6d60 ; @04DF2
    jmp short sub_4DF8 ; @04DF5
; UNKNOWN: unresolved bytes
    db 0x90 ; @04DF7
sub_4DF8:
    mov dx,0x3c4 ; @04DF8
    mov ax,0xf02 ; @04DFB
    mov [ss:0x8],ax ; @04DFE
    out dx,ax ; @04E02
    mov dx,0x3ce ; @04E03
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04E06
    mov [ss:0xa],ax ; @04E08
    out dx,ax ; @04E0C
    mov ax,0xf01 ; @04E0D
    mov [ss:0xc],ax ; @04E10
    out dx,ax ; @04E14
    mov ax,0x5 ; @04E15
    mov [ss:0x0],ax ; @04E18
    out dx,ax ; @04E1C
    mov ax,0x3 ; @04E1D
    mov [ss:0x2],ax ; @04E20
    out dx,ax ; @04E24
    mov ax,0xff08 ; @04E25
    mov [ss:0xe],ax ; @04E28
    out dx,ax ; @04E2C
    mov ax,0xa000 ; @04E2D
    mov es,ax ; @04E30
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04E32
    rep stosb ; @04E34
    ret ; @04E36
sub_4E37:
    mov al,[0x1f72] ; @04E37
    cmp al,0x2 ; @04E3A
    jnz loc_4E46 ; @04E3C
    mov al,[0x1f70] ; @04E3E
    mov [0x1f72],al ; @04E41
    jmp short loc_4E51 ; @04E44
loc_4E46:
    cmp [0x1f70],al ; @04E46
    jz loc_4E83 ; @04E4A
    mov byte [0x1f72],0x2 ; @04E4C
loc_4E51:
    mov ax,[0x1fee] ; @04E51
    mov [0x1fe4],ax ; @04E54
    mov si,0xee30 ; @04E57
    mov al,[0x25a7] ; @04E5A
    test al,0x3 ; @04E5D
    jz loc_4E84 ; @04E5F
    test al,0x2 ; @04E61
    jz loc_4E6F ; @04E63
    cmp byte [0x2010],0xff ; @04E65
    jnz loc_4E6F ; @04E6A
    mov si,0xea50 ; @04E6C
loc_4E6F:
    mov ax,0x15f ; @04E6F
    mov bx,0x92 ; @04E72
    mov dx,0x40 ; @04E75
    mov cx,0x41f ; @04E78
    mov bp,0x1 ; @04E7B
    call 0x0:0x8822 ; @04E7E
loc_4E83:
    ret ; @04E83
loc_4E84:
    mov bx,0x78 ; @04E84
    mov ax,0x144 ; @04E87
    mov si,0xb120 ; @04E8A
    mov bp,0x3 ; @04E8D
    mov cx,0x43d ; @04E90
    mov dx,0x78 ; @04E93
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04E96
    add di,0xab9 ; @04E98
    call 0x0:0x8822 ; @04E9C
    ret ; @04EA1
sub_4EA2:
    mov al,[0x1f6f] ; @04EA2
    cmp al,0x4 ; @04EA5
    jnz loc_4EB1 ; @04EA7
    mov al,[0x1f6e] ; @04EA9
    mov [0x1f6f],al ; @04EAC
    jmp short loc_4EBC ; @04EAF
loc_4EB1:
    cmp [0x1f6e],al ; @04EB1
    jz loc_4EE6 ; @04EB5
    mov byte [0x1f6f],0x4 ; @04EB7
loc_4EBC:
    mov ax,[0x1fee] ; @04EBC
    add ax,0x1000 ; @04EBF
    mov [0x1fe4],ax ; @04EC2
    mov bl,[0x1f6e] ; @04EC5
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @04EC9
    shl bx,1 ; @04ECB
    mov si,[cs:bx+0x4ee7] ; @04ECD
    mov ax,0x1e6 ; @04ED2
    mov bx,0x91 ; @04ED5
    mov dx,0x48 ; @04ED8
    mov cx,0x41b ; @04EDB
    mov bp,0x1 ; @04EDE
    call 0x0:0x8822 ; @04EE1
loc_4EE6:
    ret ; @04EE6
; UNKNOWN: unresolved bytes
    db 0xf4,0x57,0x28,0x54,0x5c,0x50,0x90,0x4c ; @04EE7
sub_4EEF:
    mov ax,[0x1fee] ; @04EEF
    mov [0x1fe4],ax ; @04EF2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04EF5
    mov bx,0x14 ; @04EF7
    mov bp,0xf42 ; @04EFA
    mov cl,0x5e ; @04EFD
    mov ch,0x4 ; @04EFF
    mov dx,0x278 ; @04F01
    mov si,0x2080 ; @04F04
    mov di,0x7786 ; @04F07
    call 0x0:0x8822 ; @04F0A
    mov ax,0x8 ; @04F0F
    mov bx,0xa ; @04F12
    mov bp,0x2 ; @04F15
    mov cl,0x5e ; @04F18
    mov ch,0x4 ; @04F1A
    mov dx,0x278 ; @04F1C
    mov si,0x2080 ; @04F1F
    mov di,0x7786 ; @04F22
    call 0x0:0x8822 ; @04F25
    ret ; @04F2A
sub_4F2B:
    mov ax,[0x1fee] ; @04F2B
    mov [0x1fe4],ax ; @04F2E
    mov bx,0x78 ; @04F31
    mov ax,0x44 ; @04F34
    mov cx,0x4 ; @04F37
    lea di,[0x4f8a] ; @04F3A
    call sub_4F4A ; @04F3E
    mov bx,0xc5 ; @04F41
    mov ax,0xc4 ; @04F44
    mov cx,0x2 ; @04F47
sub_4F4A:
    push cx ; @04F4A
    mov si,[cs:di] ; @04F4B
    add di,byte +0x2 ; @04F4E
    mov bp,0xf43 ; @04F51
    push ax ; @04F54
    push bx ; @04F55
    sub ax,0x8 ; @04F56
    add bx,byte +0x8 ; @04F59
    call sub_4F6E ; @04F5C
    pop bx ; @04F5F
    pop ax ; @04F60
    mov bp,0x3 ; @04F61
    call sub_4F6E ; @04F64
    pop cx ; @04F67
    add ax,0x80 ; @04F68
    loop sub_4F4A ; @04F6B
    ret ; @04F6D
sub_4F6E:
    push ax ; @04F6E
    push bx ; @04F6F
    push bp ; @04F70
    push si ; @04F71
    push di ; @04F72
    mov cx,0x43d ; @04F73
    mov dx,0x78 ; @04F76
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04F79
    add di,0xab9 ; @04F7B
    call 0x0:0x8822 ; @04F7F
    pop di ; @04F84
    pop si ; @04F85
    pop bp ; @04F86
    pop bx ; @04F87
    pop ax ; @04F88
    ret ; @04F89
; UNKNOWN: unresolved bytes
    db 0x88,0x94,0xd4,0xa2,0x20,0xb1,0x6c,0xbf,0xb8,0xcd,0x04,0xdc ; @04F8A
sub_4F96:
    mov ax,[0x1fee] ; @04F96
    add ax,0x800 ; @04F99
    mov [0x1fe4],ax ; @04F9C
    lea si,[0x4960] ; @04F9F
    mov cx,0xa ; @04FA3
loc_4FA6:
    push cx ; @04FA6
    mov ax,[si] ; @04FA7
    cmp ax,0x8000 ; @04FA9
    jz loc_4FF1 ; @04FAC
    dec ax ; @04FAE
    mov [si],ax ; @04FAF
    cmp ax,0xffef ; @04FB1
    jnz loc_4FBD ; @04FB4
    mov ax,[si+0x2] ; @04FB6
    mov [si],ax ; @04FB9
    jmp short loc_4FF1 ; @04FBB
loc_4FBD:
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @04FBD
    jns loc_4FF1 ; @04FBF
    neg ax ; @04FC1
    dec ax ; @04FC3
    shr ax,1 ; @04FC4
    xchg al,ah ; @04FC6
    mov bp,[si+0x8] ; @04FC8
    shr ax,1 ; @04FCB
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @04FCD
    shr ax,1 ; @04FCF
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @04FD1
    mov ax,[si+0x4] ; @04FD3
    mov bx,[si+0x6] ; @04FD6
    push si ; @04FD9
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @04FDA
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04FDC
    add di,0x90 ; @04FDE
    mov bp,0x1 ; @04FE2
    mov cx,0x40c ; @04FE5
    mov dx,0x20 ; @04FE8
    call 0x0:0x8822 ; @04FEB
    pop si ; @04FF0
loc_4FF1:
    pop cx ; @04FF1
    add si,byte +0xb ; @04FF2
    loop loc_4FA6 ; @04FF5
    ret ; @04FF7
sub_4FF8:
    lea si,[0x4960] ; @04FF8
    mov cx,0xa ; @04FFC
    mov bx,0x28 ; @04FFF
loc_5002:
    mov ax,[si+0x2] ; @05002
    cmp ax,0x8000 ; @05005
    jz loc_500C ; @05008
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @0500A
loc_500C:
    mov [si],ax ; @0500C
    add bx,byte +0x28 ; @0500E
    add si,byte +0xb ; @05011
    loop loc_5002 ; @05014
    ret ; @05016
sub_5017:
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @05017
sub_5019:
    jmp loc_7E76 ; @05019
; UNKNOWN: unresolved bytes
    db 0x32,0xc0,0xa2,0xcd,0x1f,0x3a,0x06,0xcd,0x1f,0x74,0xfa,0xc3 ; @0501C
InstallMenuTimerVector:
    cli ; @05028
    push ds ; @05029
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0502A
    mov ds,ax ; @0502C
    mov word [0x20],0x4c47 ; @0502E
    mov [0x22],cs ; @05034
    pop ds ; @05038
    sti ; @05039
    ret ; @0503A
DrawCodeInputText:
    lea si,[0x4def] ; @0503B
    jmp sub_4D4D ; @0503F
sub_5042:
    mov dl,[LevelResourceSelectionByte-GameDataImage] ; @05042
    mov dh,[0x491d] ; @05046
    mov cl,[0x40] ; @0504A
    lea si,[0x4913] ; @0504E
    lea di,[0x4d68] ; @05052
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05056
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05058
    and ax,0x101 ; @0505A
    and ch,0x1 ; @0505D
    shl al,1 ; @05060
    shl al,1 ; @05062
    shl al,1 ; @05064
    shl ah,1 ; @05066
    shl ch,1 ; @05068
    shl ch,1 ; @0506A
    or al,[si] ; @0506C
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @0506E
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05070
    mov [di],al ; @05072
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05074
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05076
    and al,0x2 ; @05078
    and ch,0x2 ; @0507A
    shl al,1 ; @0507D
    shr ch,1 ; @0507F
    or al,[si+0x1] ; @05081
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05084
    mov [di+0x1],al ; @05086
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05089
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @0508B
    and ax,0x204 ; @0508D
    and ch,0x4 ; @05090
    shr ah,1 ; @05093
    shr ch,1 ; @05095
    or al,[si+0x2] ; @05097
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @0509A
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @0509C
    mov [di+0x2],al ; @0509E
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @050A1
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050A3
    and al,0x8 ; @050A5
    and ch,0x8 ; @050A7
    shr al,1 ; @050AA
    shr al,1 ; @050AC
    shr al,1 ; @050AE
    shr ch,1 ; @050B0
    shr ch,1 ; @050B2
    or al,[si+0x3] ; @050B4
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @050B7
    mov [di+0x3],al ; @050B9
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @050BC
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050BE
    and ax,0x410 ; @050C0
    and ch,0x10 ; @050C3
    shr al,1 ; @050C6
    shr al,1 ; @050C8
    shr al,1 ; @050CA
    shr ah,1 ; @050CC
    shr ah,1 ; @050CE
    shr ch,1 ; @050D0
    or al,[si+0x4] ; @050D2
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @050D5
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @050D7
    mov [di+0x4],al ; @050D9
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @050DC
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050DE
    and al,0x20 ; @050E0
    and ah,0x8 ; @050E2
    and ch,0x20 ; @050E5
    shr al,1 ; @050E8
    shr al,1 ; @050EA
    shr al,1 ; @050EC
    shr al,1 ; @050EE
    shr al,1 ; @050F0
    shr ah,1 ; @050F2
    shr ah,1 ; @050F4
    shr ch,1 ; @050F6
    shr ch,1 ; @050F8
    shr ch,1 ; @050FA
    or al,[si+0x5] ; @050FC
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @050FF
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05101
    mov [di+0x5],al ; @05103
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05106
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05108
    and al,0xc0 ; @0510A
    and ch,0x40 ; @0510C
    shr al,1 ; @0510F
    shr al,1 ; @05111
    shr al,1 ; @05113
    shr al,1 ; @05115
    shr ch,1 ; @05117
    shr ch,1 ; @05119
    shr ch,1 ; @0511B
    shr ch,1 ; @0511D
    shr ch,1 ; @0511F
    shr ch,1 ; @05121
    or al,[si+0x6] ; @05123
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05126
    mov [di+0x6],al ; @05128
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @0512B
    and al,0xf ; @0512D
    add al,[si+0x7] ; @0512F
    mov [di+0x7],al ; @05132
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05135
    and al,0xf0 ; @05137
    shr al,1 ; @05139
    shr al,1 ; @0513B
    shr al,1 ; @0513D
    shr al,1 ; @0513F
    add al,[si+0x8] ; @05141
    mov [di+0x8],al ; @05144
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @05147
    add al,[di] ; @05149
    add al,[di+0x1] ; @0514B
    add al,[di+0x2] ; @0514E
    add al,[di+0x3] ; @05151
    add al,[di+0x4] ; @05154
    add al,[di+0x5] ; @05157
    add al,[di+0x6] ; @0515A
    add al,[di+0x7] ; @0515D
    add al,[di+0x8] ; @05160
    and al,0xf ; @05163
    add al,[si+0x9] ; @05165
    mov [di+0x9],al ; @05168
    mov dh,0x7 ; @0516B
    db 0x22,0xd6 ; ENCODED: and dl,dh (NASM chooses a different encoding) ; @0516D
    db 0x2a,0xf2 ; ENCODED: sub dh,dl (NASM chooses a different encoding) ; @0516F
    lea si,[0x4d6e] ; @05171
loc_5175:
    mov al,[si] ; @05175
    mov ah,[si-0x1] ; @05177
    mov [si],ah ; @0517A
    mov ah,[si-0x2] ; @0517C
    mov [si-0x1],ah ; @0517F
    mov ah,[si-0x3] ; @05182
    mov [si-0x2],ah ; @05185
    mov ah,[si-0x4] ; @05188
    mov [si-0x3],ah ; @0518B
    mov ah,[si-0x5] ; @0518E
    mov [si-0x4],ah ; @05191
    mov ah,[si-0x6] ; @05194
    mov [si-0x5],ah ; @05197
    mov [si-0x6],al ; @0519A
    dec dh ; @0519D
    jns loc_5175 ; @0519F
    ret ; @051A1
sub_51A2:
    lea si,[0x4df2] ; @051A2
    cmp word [si],0x4942 ; @051A6
    jnz loc_51CD ; @051AA
    cmp word [si+0x2],0x4c4c ; @051AC
    jnz loc_51CD ; @051B1
    cmp word [si+0x4],0x4e41 ; @051B3
    jnz loc_51CD ; @051B8
    cmp word [si+0x6],0x5444 ; @051BA
    jnz loc_51CD ; @051BF
    cmp word [si+0x8],0x4445 ; @051C1
    jnz loc_51CD ; @051C6
    mov byte [0x1f74],0xff ; @051C8
loc_51CD:
    lea di,[0x4913] ; @051CD
    mov cx,0x9 ; @051D1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @051D4
    push si ; @051D6
loc_51D7:
    add al,[si] ; @051D7
    inc si ; @051D9
    loop loc_51D7 ; @051DA
    pop si ; @051DC
    and al,0xf ; @051DD
    mov ah,[si+0x9] ; @051DF
    db 0x2a,0xe0 ; ENCODED: sub ah,al (NASM chooses a different encoding) ; @051E2
    cmp [di+0x9],ah ; @051E4
    jz loc_51EC ; @051E7
    jmp loc_52D3 ; @051E9
loc_51EC:
    mov al,[si+0x7] ; @051EC
    sub al,[di+0x7] ; @051EF
    mov ah,[si+0x8] ; @051F2
    sub ah,[di+0x8] ; @051F5
    and ax,0xf0f ; @051F8
    shl ah,1 ; @051FB
    shl ah,1 ; @051FD
    shl ah,1 ; @051FF
    shl ah,1 ; @05201
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @05203
    mov [LevelResourceSelectionByte-GameDataImage],al ; @05205
    mov dh,0x7 ; @05208
    db 0x22,0xc6 ; ENCODED: and al,dh (NASM chooses a different encoding) ; @0520A
    db 0x2a,0xf0 ; ENCODED: sub dh,al (NASM chooses a different encoding) ; @0520C
loc_520E:
    mov al,[si] ; @0520E
    mov ah,[si+0x1] ; @05210
    mov [si],ah ; @05213
    mov ah,[si+0x2] ; @05215
    mov [si+0x1],ah ; @05218
    mov ah,[si+0x3] ; @0521B
    mov [si+0x2],ah ; @0521E
    mov ah,[si+0x4] ; @05221
    mov [si+0x3],ah ; @05224
    mov ah,[si+0x5] ; @05227
    mov [si+0x4],ah ; @0522A
    mov ah,[si+0x6] ; @0522D
    mov [si+0x5],ah ; @05230
    mov [si+0x6],al ; @05233
    dec dh ; @05236
    jns loc_520E ; @05238
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0523A
    mov al,[si] ; @0523C
    shr al,1 ; @0523E
    shr al,1 ; @05240
    shr al,1 ; @05242
    and al,0x1 ; @05244
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05246
    mov al,[si+0x1] ; @05248
    shr al,1 ; @0524B
    and al,0x2 ; @0524D
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0524F
    mov al,[si+0x2] ; @05251
    and al,0x4 ; @05254
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05256
    mov al,[si+0x3] ; @05258
    shl al,1 ; @0525B
    shl al,1 ; @0525D
    shl al,1 ; @0525F
    and al,0x8 ; @05261
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05263
    mov al,[si+0x4] ; @05265
    shl al,1 ; @05268
    shl al,1 ; @0526A
    shl al,1 ; @0526C
    and al,0x10 ; @0526E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05270
    mov al,[si+0x5] ; @05272
    shl al,1 ; @05275
    shl al,1 ; @05277
    shl al,1 ; @05279
    shl al,1 ; @0527B
    shl al,1 ; @0527D
    and al,0x20 ; @0527F
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05281
    mov al,[si+0x6] ; @05283
    shl al,1 ; @05286
    shl al,1 ; @05288
    shl al,1 ; @0528A
    shl al,1 ; @0528C
    and al,0xc0 ; @0528E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05290
    cmp ah,[LevelResourceSelectionByte-GameDataImage] ; @05292
    jnz loc_52D3 ; @05296
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @05298
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0529B
    mov cl,0x1e ; @0529D
    div cl ; @0529F
    mov [0x1f6e],al ; @052A1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @052A4
    mov al,[si] ; @052A6
    shr al,1 ; @052A8
    and al,0x1 ; @052AA
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052AC
    mov al,[si+0x2] ; @052AE
    shl al,1 ; @052B1
    and al,0x2 ; @052B3
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052B5
    mov al,[si+0x4] ; @052B7
    shl al,1 ; @052BA
    shl al,1 ; @052BC
    and al,0x4 ; @052BE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052C0
    mov al,[si+0x5] ; @052C2
    shl al,1 ; @052C5
    shl al,1 ; @052C7
    and al,0x8 ; @052C9
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052CB
    mov [0x491d],ah ; @052CD
    db 0x2a,0xe4 ; ENCODED: sub ah,ah (NASM chooses a different encoding) ; @052D1
loc_52D3:
    ret ; @052D3
; UNKNOWN: unresolved bytes
    db 0x38,0x26,0x08,0x26,0x20,0x49,0x13,0x1f,0xe8,0x25,0x0b,0x1f,0xa8,0x25,0x68,0x26 ; @052D4
; UNKNOWN: unresolved bytes
    db 0x38,0x26,0x08,0x26,0x30,0x49,0x3b,0x1f,0xf0,0x25,0x23,0x1f,0xb8,0x25,0x68,0x26 ; @052E4
sub_52F4:
    cmp word [0x1f7c],byte +0x4 ; @052F4
    jz loc_5309 ; @052F9
    lea si,[0x52d4] ; @052FB
    mov si,[cs:si+0x2] ; @052FF
    mov cx,0x10 ; @05303
    jmp sub_5425 ; @05306
loc_5309:
    lea si,[0x52e4] ; @05309
    mov si,[cs:si+0x2] ; @0530D
    mov cx,0x8 ; @05311
    call sub_548C ; @05314
    mov cx,0x1008 ; @05317
    jmp sub_548C ; @0531A
; UNKNOWN: unresolved bytes
    db 0xc3 ; @0531D
sub_531E:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0531E
    mov cx,0x10 ; @05320
    mov bx,0x100 ; @05323
    jmp loc_55B7 ; @05326
sub_5329:
    push dx ; @05329
    mov bx,0x100 ; @0532A
    call sub_5569 ; @0532D
    mov bl,0x1 ; @05330
    jnz loc_5336 ; @05332
    dec bl ; @05334
loc_5336:
    pop cx ; @05336
    push bx ; @05337
    mov cx,0x10 ; @05338
    mov bx,0x107 ; @0533B
    call sub_5569 ; @0533E
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
    call sub_5569 ; @0534F
    pop cx ; @05352
    pop bx ; @05353
    mov dl,0x1 ; @05354
    jnz loc_535A ; @05356
    dec dl ; @05358
loc_535A:
    push dx ; @0535A
    db 0x8a,0xfb ; ENCODED: mov bh,bl (NASM chooses a different encoding) ; @0535B
    mov bl,0x7 ; @0535D
    call sub_5569 ; @0535F
    mov al,0x1 ; @05362
    jnz loc_5368 ; @05364
    dec al ; @05366
loc_5368:
    pop bx ; @05368
    db 0x0a,0xc3 ; ENCODED: or al,bl (NASM chooses a different encoding) ; @05369
    ret ; @0536B
sub_536C:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0536C
    mov cx,0x10 ; @0536E
    mov bx,0x200 ; @05371
    jmp loc_55B7 ; @05374
sub_5377:
    cmp word [0x1f7c],byte +0x4 ; @05377
    jz loc_53A1 ; @0537C
    push ds ; @0537E
    pop es ; @0537F
    lea si,[0x52d4] ; @05380
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
    lea si,[0x52e4] ; @053A3
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
    cmp word [0x1f7c],byte +0x4 ; @053D1
    jz loc_53E7 ; @053D6
    lea si,[0x52d4] ; @053D8
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @053DC
    mov si,[cs:si] ; @053DE
    add si,byte +0x8 ; @053E1
    jmp short sub_5425 ; @053E4
; UNKNOWN: unresolved bytes
    db 0x90 ; @053E6
loc_53E7:
    lea si,[0x52e4] ; @053E7
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @053EB
    mov si,[cs:si] ; @053ED
    add si,byte +0x18 ; @053F0
    jmp sub_54C4 ; @053F3
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
    cmp word [0x1f7c],byte +0x4 ; @05405
    jz loc_5418 ; @0540A
    lea si,[0x52d4] ; @0540C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @05410
    mov si,[cs:si] ; @05412
    jmp short sub_5425 ; @05415
; UNKNOWN: unresolved bytes
    db 0x90 ; @05417
loc_5418:
    lea si,[0x52e4] ; @05418
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0541C
    mov si,[cs:si] ; @0541E
    jmp sub_54C4 ; @05421
; UNKNOWN: unresolved bytes
    db 0xc3 ; @05424
sub_5425:
    cli ; @05425
    db 0x8a,0xdd ; ENCODED: mov bl,ch (NASM chooses a different encoding) ; @05426
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05428
    mov dx,[0x1fda] ; @0542A
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
    ret ; @05446
sub_5447:
    cmp word [0x1f7c],byte +0x4 ; @05447
    jz loc_5456 ; @0544C
    cmp word [0x1f7c],byte +0x2 ; @0544E
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
    jmp short sub_5425 ; @05471
sub_5473:
    cmp word [0x1f7c],byte +0x4 ; @05473
    jz loc_5485 ; @05478
    cmp word [0x1f7c],byte +0x2 ; @0547A
    jnz loc_5484 ; @0547F
    jmp loc_5533 ; @05481
loc_5484:
    ret ; @05484
loc_5485:
    lea si,[0x2668] ; @05485
    mov cx,0x1008 ; @05489
sub_548C:
    cli ; @0548C
    cmp byte [0x200c],0xff ; @0548D
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
    cmp byte [0x200c],0xff ; @054B6
    jz loc_54C2 ; @054BB
    pop dx ; @054BD
    pop ax ; @054BE
    and al,0xdf ; @054BF
    out dx,al ; @054C1
loc_54C2:
    sti ; @054C2
    ret ; @054C3
sub_54C4:
    push di ; @054C4
    cli ; @054C5
    cmp byte [0x200c],0xff ; @054C6
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
    lea di,[0x5507] ; @054E1
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
    cmp byte [0x200c],0xff ; @054F8
    jz loc_5504 ; @054FD
    pop dx ; @054FF
    pop ax ; @05500
    and al,0xdf ; @05501
    out dx,al ; @05503
loc_5504:
    sti ; @05504
    pop di ; @05505
    ret ; @05506
; UNKNOWN: unresolved bytes
    db 0x00,0x01,0x02,0x03,0x04,0x05,0x14,0x07,0x38,0x39,0x3a,0x3b,0x3c,0x3d,0x3e,0x3f ; @05507
; UNKNOWN: unresolved bytes
    db 0xbb,0x11,0x03,0x8b,0x16,0xda,0x1f,0x80,0xc2,0x06,0xec,0x52,0xb2,0xc0,0x8a,0xc3 ; @05517
; UNKNOWN: unresolved bytes
    db 0xee,0x8a,0xc7,0xee,0x5a,0xec,0xb2,0xc0,0xb0,0x20,0xee,0xc3 ; @05527
loc_5533:
    lea si,[0x2668] ; @05533
    mov cx,0x808 ; @05537
    jmp sub_5425 ; @0553A
sub_553D:
    mov ax,[0x1f7c] ; @0553D
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
    jmp sub_5425 ; @05566
sub_5569:
    cmp word [0x1f7c],byte +0x4 ; @05569
    jz loc_5593 ; @0556E
    push ds ; @05570
    pop es ; @05571
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05572
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05574
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05576
    lea si,[0x52d4] ; @05578
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0557C
    mov si,[cs:si] ; @0557E
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @05581
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05583
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05585
    lea di,[0x52d4] ; @05587
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @0558B
    mov di,[cs:di] ; @0558D
    jmp sub_563E ; @05590
loc_5593:
    push ds ; @05593
    pop es ; @05594
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05595
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05597
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05599
    lea si,[0x52e4] ; @0559B
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0559F
    mov si,[cs:si] ; @055A1
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @055A4
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @055A6
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @055A8
    lea di,[0x52e4] ; @055AA
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @055AE
    mov di,[cs:di] ; @055B0
    jmp sub_56E2 ; @055B3
; UNKNOWN: unresolved bytes
    db 0xc3 ; @055B6
loc_55B7:
    cmp word [0x1f7c],byte +0x4 ; @055B7
    jz loc_5601 ; @055BC
    push es ; @055BE
    push ds ; @055BF
    pop es ; @055C0
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @055C1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @055C3
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @055C5
    lea si,[0x52d4] ; @055C7
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @055CB
    mov si,[cs:si] ; @055CD
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @055D0
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @055D2
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @055D4
    lea di,[0x52d4] ; @055D6
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @055DA
    mov di,[cs:di] ; @055DC
loc_55DF:
    push cx ; @055DF
    push si ; @055E0
    call sub_5425 ; @055E1
    pop si ; @055E4
    pop cx ; @055E5
    push cx ; @055E6
    push si ; @055E7
    push di ; @055E8
    call sub_563E ; @055E9
    jz loc_55FC ; @055EC
    call sub_1550 ; @055EE
    call sub_1550 ; @055F1
    call sub_1550 ; @055F4
    pop di ; @055F7
    pop si ; @055F8
    pop cx ; @055F9
    jmp short loc_55DF ; @055FA
loc_55FC:
    pop di ; @055FC
    pop si ; @055FD
    pop cx ; @055FE
    pop es ; @055FF
    ret ; @05600
loc_5601:
    push es ; @05601
    push ds ; @05602
    pop es ; @05603
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @05604
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05606
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05608
    lea si,[0x52e4] ; @0560A
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0560E
    mov si,[cs:si] ; @05610
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @05613
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05615
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05617
    lea di,[0x52e4] ; @05619
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @0561D
    mov di,[cs:di] ; @0561F
loc_5622:
    push cx ; @05622
    push si ; @05623
    call sub_54C4 ; @05624
    pop si ; @05627
    pop cx ; @05628
    push cx ; @05629
    push si ; @0562A
    push di ; @0562B
    call sub_56E2 ; @0562C
    jz loc_5639 ; @0562F
    call sub_1550 ; @05631
    pop di ; @05634
    pop si ; @05635
    pop cx ; @05636
    jmp short loc_5622 ; @05637
loc_5639:
    pop di ; @05639
    pop si ; @0563A
    pop cx ; @0563B
    pop es ; @0563C
    ret ; @0563D
sub_563E:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @0563E
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05640
loc_5642:
    push cx ; @05642
    mov dl,[si] ; @05643
    mov cl,[di] ; @05645
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @05647
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05649
    call sub_566C ; @0564B
    db 0x8a,0xf0 ; ENCODED: mov dh,al (NASM chooses a different encoding) ; @0564E
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05650
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @05652
    call sub_5685 ; @05654
    db 0x0a,0xf0 ; ENCODED: or dh,al (NASM chooses a different encoding) ; @05657
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05659
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @0565B
    call sub_5696 ; @0565D
    db 0x0a,0xf0 ; ENCODED: or dh,al (NASM chooses a different encoding) ; @05660
    mov [si],dh ; @05662
    pop cx ; @05664
    inc si ; @05665
    inc di ; @05666
    loop loc_5642 ; @05667
    db 0x23,0xed ; ENCODED: and bp,bp (NASM chooses a different encoding) ; @05669
    ret ; @0566B
sub_566C:
    shr al,1 ; @0566C
    shr bl,1 ; @0566E
    shr al,1 ; @05670
    shr bl,1 ; @05672
    and al,0x9 ; @05674
    and bl,0x9 ; @05676
    call sub_569B ; @05679
    shl al,1 ; @0567C
    shl bl,1 ; @0567E
    shl al,1 ; @05680
    shl bl,1 ; @05682
    ret ; @05684
sub_5685:
    shr al,1 ; @05685
    shr bl,1 ; @05687
    and al,0x9 ; @05689
    and bl,0x9 ; @0568B
    call sub_569B ; @0568E
    shl al,1 ; @05691
    shl bl,1 ; @05693
    ret ; @05695
sub_5696:
    and al,0x9 ; @05696
    and bl,0x9 ; @05698
sub_569B:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0569B
    shr al,1 ; @0569D
    shr al,1 ; @0569F
    shr al,1 ; @056A1
    shl ah,1 ; @056A3
    and ah,0x2 ; @056A5
    and al,0x1 ; @056A8
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @056AA
    db 0x8a,0xfb ; ENCODED: mov bh,bl (NASM chooses a different encoding) ; @056AC
    shr bl,1 ; @056AE
    shr bl,1 ; @056B0
    shr bl,1 ; @056B2
    shl bh,1 ; @056B4
    and bh,0x2 ; @056B6
    and bl,0x1 ; @056B9
    db 0x0a,0xdf ; ENCODED: or bl,bh (NASM chooses a different encoding) ; @056BC
    db 0x3a,0xc3 ; ENCODED: cmp al,bl (NASM chooses a different encoding) ; @056BE
    jz loc_56D0 ; @056C0
    ja loc_56CB ; @056C2
    inc al ; @056C4
    mov bp,0xff ; @056C6
    jmp short loc_56D0 ; @056C9
loc_56CB:
    dec al ; @056CB
    mov bp,0xff ; @056CD
loc_56D0:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @056D0
    shl al,1 ; @056D2
    shl al,1 ; @056D4
    shl al,1 ; @056D6
    shr ah,1 ; @056D8
    and al,0x8 ; @056DA
    and ah,0x1 ; @056DC
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @056DF
    ret ; @056E1
sub_56E2:
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @056E2
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @056E4
loc_56E6:
    mov al,[si] ; @056E6
    mov ah,[di] ; @056E8
    call sub_570C ; @056EA
    mov [si],al ; @056ED
    inc si ; @056EF
    inc di ; @056F0
    mov al,[si] ; @056F1
    mov ah,[di] ; @056F3
    call sub_570C ; @056F5
    mov [si],al ; @056F8
    inc si ; @056FA
    inc di ; @056FB
    mov al,[si] ; @056FC
    mov ah,[di] ; @056FE
    call sub_570C ; @05700
    mov [si],al ; @05703
    inc si ; @05705
    inc di ; @05706
    loop loc_56E6 ; @05707
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @05709
    ret ; @0570B
sub_570C:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @0570C
    jz loc_571E ; @0570E
    jg loc_571F ; @05710
    inc al ; @05712
loc_5714:
    mov bl,0xff ; @05714
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @05716
    jz loc_571E ; @05718
    jg loc_5723 ; @0571A
    inc al ; @0571C
loc_571E:
    ret ; @0571E
loc_571F:
    dec al ; @0571F
    jmp short loc_5714 ; @05721
loc_5723:
    dec al ; @05723
    ret ; @05725
sub_5726:
    mov bx,[di] ; @05726
    add bx,[di+0x4] ; @05728
    jns loc_5731 ; @0572B
    add bx,0x160 ; @0572D
loc_5731:
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @05731
    shr bx,1 ; @05733
    shr bx,1 ; @05735
    shr bx,1 ; @05737
    lea si,[0xea8] ; @05739
    cmp byte [bx+si],0x1 ; @0573D
    jz loc_5745 ; @05740
    jmp loc_57D0 ; @05742
loc_5745:
    sub ax,[0x0] ; @05745
    jns loc_574D ; @05749
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0574B
loc_574D:
    shr ax,1 ; @0574D
    shr ax,1 ; @0574F
    shr ax,1 ; @05751
    add ax,[0x26] ; @05753
    mov bp,[0x26] ; @05757
    add bp,0x321 ; @0575B
    inc ax ; @0575F
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @05760
    mov cx,[di+0x6] ; @05762
    sub cx,byte +0x8 ; @05765
    mov ax,[di+0x2] ; @05768
    cmp byte [di+0x20],0x0 ; @0576B
    jz loc_5774 ; @0576F
    sub cx,byte +0x8 ; @05771
loc_5774:
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05774
    sub ax,0x10 ; @05776
    jns loc_5788 ; @05779
loc_577B:
    add cx,byte +0x8 ; @0577B
    add ax,0x8 ; @0577E
    js loc_577B ; @05781
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05783
    sub cx,byte +0x8 ; @05785
loc_5788:
    neg cx ; @05788
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @0578A
    and ax,0xfff8 ; @0578C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0578F
    shl ax,1 ; @05791
    shl ax,1 ; @05793
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @05795
    mov ch,0x3 ; @05797
    test word [di+0x8],0x2 ; @05799
    jz loc_57A2 ; @0579E
    mov ch,0x5 ; @057A0
loc_57A2:
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @057A2
    shr cl,1 ; @057A4
    shr cl,1 ; @057A6
    shr cl,1 ; @057A8
    test dl,0x7 ; @057AA
    jz loc_57B1 ; @057AD
    inc cl ; @057AF
loc_57B1:
    test al,0x7 ; @057B1
    jz loc_57B7 ; @057B3
    inc cl ; @057B5
loc_57B7:
    mov al,0x1 ; @057B7
loc_57B9:
    push cx ; @057B9
    push si ; @057BA
loc_57BB:
    mov [ss:si],al ; @057BB
    inc si ; @057BE
    dec ch ; @057BF
    jnz loc_57BB ; @057C1
    pop si ; @057C3
    pop cx ; @057C4
    add si,byte +0x28 ; @057C5
    db 0x3b,0xf5 ; ENCODED: cmp si,bp (NASM chooses a different encoding) ; @057C8
    jnc loc_57D0 ; @057CA
    dec cl ; @057CC
    jnz loc_57B9 ; @057CE
loc_57D0:
    ret ; @057D0
sub_57D1:
    push ax ; @057D1
    mov dx,0xa000 ; @057D2
    mov es,dx ; @057D5
    mov dx,0x3ce ; @057D7
    mov ax,0x1 ; @057DA
    mov [ss:0xc],ax ; @057DD
    out dx,ax ; @057E1
    mov ax,0x5 ; @057E2
    mov [ss:0x0],ax ; @057E5
    out dx,ax ; @057E9
    mov ax,0x3 ; @057EA
    mov [ss:0x2],ax ; @057ED
    out dx,ax ; @057F1
    mov ax,0xff08 ; @057F2
    mov [ss:0xe],ax ; @057F5
    out dx,ax ; @057F9
    pop ax ; @057FA
    mov dx,0x102 ; @057FB
loc_57FE:
    push di ; @057FE
    push cx ; @057FF
    push ax ; @05800
    push dx ; @05801
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05802
    mov dx,0x3c4 ; @05804
    mov [ss:0x8],ax ; @05807
    out dx,ax ; @0580B
    pop dx ; @0580C
    pop ax ; @0580D
loc_580E:
    push cx ; @0580E
    push di ; @0580F
    push bx ; @05810
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05811
    db 0x8a,0xcb ; ENCODED: mov cl,bl (NASM chooses a different encoding) ; @05813
    rep movsb ; @05815
    pop bx ; @05817
    pop di ; @05818
    pop cx ; @05819
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @0581A
    loop loc_580E ; @0581C
    pop cx ; @0581E
    pop di ; @0581F
    shl dh,1 ; @05820
    dec bh ; @05822
    jnz loc_57FE ; @05824
    ret ; @05826
sub_5827:
    call sub_715F ; @05827
    mov bx,[0x10] ; @0582A
    mov cl,[0x1fe0] ; @0582E
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05832
    db 0x03,0xd9 ; ENCODED: add bx,cx (NASM chooses a different encoding) ; @05834
    and bl,0x7 ; @05836
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @05839
    shl bx,1 ; @0583B
    shl bx,1 ; @0583D
    shl bx,1 ; @0583F
    shl bx,1 ; @05841
    db 0x8b,0xf3 ; ENCODED: mov si,bx (NASM chooses a different encoding) ; @05843
    shl bx,1 ; @05845
    shl bx,1 ; @05847
    shl bx,1 ; @05849
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @0584B
    cmp byte [0x1a],0xff ; @0584D
    jnz loc_5858 ; @05852
    add si,0x480 ; @05854
loc_5858:
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @05858
    add bx,byte +0x60 ; @0585A
    mov di,[0xc] ; @0585D
    push ds ; @05861
    mov ds,[0x1fea] ; @05862
    call sub_7218 ; @05866
    pop ds ; @05869
    mov ax,[0xc] ; @0586A
    xchg [0xe],ax ; @0586D
    mov [0xc],ax ; @05871
    mov ax,[0x8] ; @05874
    xchg [0xa],ax ; @05877
    mov [0x8],ax ; @0587B
    ret ; @0587E
sub_587F:
    cli ; @0587F
    push cx ; @05880
    mov cx,es ; @05881
    mov ax,0x143e ; @05883
    mov es,ax ; @05886
    mov dx,0x3c4 ; @05888
    mov ax,[es:0x8] ; @0588B
    mov al,0x2 ; @0588F
    out dx,ax ; @05891
    mov dx,0x3ce ; @05892
    mov ax,[es:0x0] ; @05895
    mov al,0x5 ; @05899
    out dx,ax ; @0589B
    mov ax,[es:0x2] ; @0589C
    mov al,0x3 ; @058A0
    out dx,ax ; @058A2
    mov ax,[es:0x4] ; @058A3
    mov al,0x2 ; @058A7
    out dx,ax ; @058A9
    mov ax,[es:0x6] ; @058AA
    mov al,0x7 ; @058AE
    out dx,ax ; @058B0
    mov ax,[es:0xa] ; @058B1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @058B5
    out dx,ax ; @058B7
    mov ax,[es:0xc] ; @058B8
    mov al,0x1 ; @058BC
    out dx,ax ; @058BE
    mov ax,[es:0xe] ; @058BF
    mov al,0x8 ; @058C3
    out dx,ax ; @058C5
    mov ax,[es:0x10] ; @058C6
    mov al,0x4 ; @058CA
    out dx,ax ; @058CC
    mov es,cx ; @058CD
    pop cx ; @058CF
    sti ; @058D0
    ret ; @058D1
LoadMainResourceSections:
    push ds ; @058D2
    mov dx,0x252b ; @058D3
    mov es,[0x1fe4] ; @058D6
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @058DA
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @058DC
    mov cx,es ; @058DE
    call LoadDatResource ; @058E0
    pop ds ; @058E3
    push bx ; @058E4
    call sub_59BB ; @058E5
    call sub_5CC1 ; @058E8
    pop bx ; @058EB
    push ds ; @058EC
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @058ED
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @058EF
    mov es,[0x1fe4] ; @058F1
    mov ds,[0x1fe4] ; @058F5
    call DecodeDatPreservingSegment ; @058F9
    pop ds ; @058FC
    push bx ; @058FD
    call sub_5AC1 ; @058FE
    pop bx ; @05901
    push ds ; @05902
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05903
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05905
    mov es,[0x1fe4] ; @05907
    mov ds,[0x1fe4] ; @0590B
    call DecodeDatPreservingSegment ; @0590F
    pop ds ; @05912
    push bx ; @05913
    push ds ; @05914
    mov di,0xf91f ; @05915
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05918
    mov cx,0x28 ; @0591A
    mov ax,0x2c ; @0591D
    mov bx,0x428 ; @05920
    mov ds,[0x1fe4] ; @05923
    call sub_57D1 ; @05927
    pop ds ; @0592A
    push ds ; @0592B
    mov si,0x1900 ; @0592C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0592F
    mov es,[0x1fec] ; @05931
    mov ds,[0x1fe4] ; @05935
    mov cx,0x3e0 ; @05939
    rep movsw ; @0593C
    pop ds ; @0593E
    pop bx ; @0593F
    push ds ; @05940
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05941
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05943
    mov es,[0x1fee] ; @05945
    mov ds,[0x1fee] ; @05949
    call DecodeDatPreservingSegment ; @0594D
sub_5950:
    pop ds ; @05950
    push ds ; @05951
    mov ax,[0x1fee] ; @05952
    add ax,0xf21 ; @05955
    mov es,ax ; @05958
    mov ds,ax ; @0595A
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0595C
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0595E
    call DecodeDatPreservingSegment ; @05960
    pop ds ; @05963
    push bx ; @05964
    pop bx ; @05965
    push ds ; @05966
    mov ax,0x842 ; @05967
    mov es,ax ; @0596A
    mov ds,ax ; @0596C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0596E
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05970
    call DecodeDatPreservingSegment ; @05972
    pop ds ; @05975
    cmp byte [0x200e],0xff ; @05976
    jnz loc_59BA ; @0597B
sub_597D:
    push ds ; @0597D
    mov es,[0x1fe4] ; @0597E
    mov ds,[0x1fe4] ; @05982
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05986
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05988
    call DecodeDatPreservingSegment ; @0598A
    pop ds ; @0598D
    push ds ; @0598E
    mov di,0xf91f ; @0598F
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05992
    mov cx,0x28 ; @05994
    mov ax,0x2c ; @05997
    mov bx,0x428 ; @0599A
    mov ds,[0x1fe4] ; @0599D
    call sub_57D1 ; @059A1
    pop ds ; @059A4
    push ds ; @059A5
    mov di,0xa0 ; @059A6
    mov si,0x1900 ; @059A9
    mov es,[0x1fec] ; @059AC
    mov ds,[0x1fe4] ; @059B0
    mov cx,0x720 ; @059B4
    rep movsb ; @059B7
    pop ds ; @059B9
loc_59BA:
    ret ; @059BA
sub_59BB:
    push ds ; @059BB
    mov es,[0x1fe6] ; @059BC
    mov ds,[0x1fe4] ; @059C0
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @059C4
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @059C6
    mov cx,0x12 ; @059C8
loc_59CB:
    push cx ; @059CB
    mov dx,0x20a ; @059CC
    call sub_5B11 ; @059CF
    pop cx ; @059D2
    add si,byte +0x28 ; @059D3
    loop loc_59CB ; @059D6
    mov cx,0x10 ; @059D8
loc_59DB:
    push cx ; @059DB
    mov dx,0x30e ; @059DC
    call sub_5BB0 ; @059DF
    pop cx ; @059E2
    add si,byte +0x54 ; @059E3
    loop loc_59DB ; @059E6
    mov cx,0x10 ; @059E8
loc_59EB:
    push cx ; @059EB
    mov dx,0x20c ; @059EC
    call sub_5BB0 ; @059EF
    pop cx ; @059F2
    add si,byte +0x30 ; @059F3
    loop loc_59EB ; @059F6
    mov cx,0x10 ; @059F8
loc_59FB:
    push cx ; @059FB
    mov dx,0x20a ; @059FC
    call sub_5B11 ; @059FF
    pop cx ; @05A02
    add si,byte +0x28 ; @05A03
    loop loc_59FB ; @05A06
    mov cx,0x10 ; @05A08
loc_5A0B:
    push cx ; @05A0B
    mov dx,0x20c ; @05A0C
    call sub_5BB0 ; @05A0F
    pop cx ; @05A12
    add si,byte +0x30 ; @05A13
    loop loc_5A0B ; @05A16
    mov cx,0x20 ; @05A18
loc_5A1B:
    push cx ; @05A1B
    mov dx,0x30d ; @05A1C
    call sub_5BB0 ; @05A1F
    pop cx ; @05A22
    add si,byte +0x4e ; @05A23
    loop loc_5A1B ; @05A26
    mov cx,0x40 ; @05A28
loc_5A2B:
    push cx ; @05A2B
    mov dx,0x30a ; @05A2C
    call sub_5BB0 ; @05A2F
    pop cx ; @05A32
    add si,byte +0x3c ; @05A33
    loop loc_5A2B ; @05A36
    mov cx,0x30 ; @05A38
loc_5A3B:
    push cx ; @05A3B
    mov dx,0x30d ; @05A3C
    call sub_5BB0 ; @05A3F
    pop cx ; @05A42
    add si,byte +0x4e ; @05A43
    loop loc_5A3B ; @05A46
    mov cx,0x8 ; @05A48
loc_5A4B:
    push cx ; @05A4B
    mov dx,0x20a ; @05A4C
    call sub_5B11 ; @05A4F
    pop cx ; @05A52
    add si,byte +0x28 ; @05A53
    loop loc_5A4B ; @05A56
    mov cx,0x10 ; @05A58
loc_5A5B:
    push cx ; @05A5B
    mov dx,0x310 ; @05A5C
    call sub_5BB0 ; @05A5F
    pop cx ; @05A62
    add si,byte +0x60 ; @05A63
    loop loc_5A5B ; @05A66
    mov cx,0x10 ; @05A68
loc_5A6B:
    push cx ; @05A6B
    mov dx,0x20a ; @05A6C
    call sub_5B11 ; @05A6F
    pop cx ; @05A72
    add si,byte +0x28 ; @05A73
    loop loc_5A6B ; @05A76
    mov cx,0x8 ; @05A78
loc_5A7B:
    push cx ; @05A7B
    mov dx,0x20d ; @05A7C
    call sub_5BB0 ; @05A7F
    pop cx ; @05A82
    add si,byte +0x34 ; @05A83
    loop loc_5A7B ; @05A86
    mov cx,0xe ; @05A88
loc_5A8B:
    push cx ; @05A8B
    mov dx,0x40e ; @05A8C
    call sub_5BB0 ; @05A8F
    pop cx ; @05A92
    add si,byte +0x70 ; @05A93
    loop loc_5A8B ; @05A96
    mov cx,0x10 ; @05A98
loc_5A9B:
    push cx ; @05A9B
    mov dx,0x20a ; @05A9C
    call sub_5B11 ; @05A9F
    pop cx ; @05AA2
    add si,byte +0x28 ; @05AA3
    loop loc_5A9B ; @05AA6
    mov cx,0x20 ; @05AA8
loc_5AAB:
    push cx ; @05AAB
    mov dx,0x20a ; @05AAC
    call sub_5B11 ; @05AAF
    pop cx ; @05AB2
    add si,byte +0x28 ; @05AB3
    loop loc_5AAB ; @05AB6
    call sub_5C06 ; @05AB8
    add si,0x180 ; @05ABB
    pop ds ; @05ABF
    ret ; @05AC0
sub_5AC1:
    push ds ; @05AC1
    mov es,[0x1fe8] ; @05AC2
    mov ds,[0x1fe4] ; @05AC6
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05ACA
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05ACC
    mov cx,0x8 ; @05ACE
loc_5AD1:
    push cx ; @05AD1
    mov cx,0xa ; @05AD2
    mov bl,0x1 ; @05AD5
    call sub_5CDD ; @05AD7
    add si,byte +0x14 ; @05ADA
    pop cx ; @05ADD
    loop loc_5AD1 ; @05ADE
    mov cx,0x4 ; @05AE0
loc_5AE3:
    push cx ; @05AE3
    mov cx,0xd ; @05AE4
    mov bl,0x1 ; @05AE7
    call sub_5CDD ; @05AE9
    add si,byte +0x1a ; @05AEC
    pop cx ; @05AEF
    loop loc_5AE3 ; @05AF0
    mov cx,0x16 ; @05AF2
    mov bl,0x1 ; @05AF5
    call sub_5CDD ; @05AF7
    add si,byte +0x2c ; @05AFA
    mov cx,0xa ; @05AFD
loc_5B00:
    push cx ; @05B00
    mov cx,0x8 ; @05B01
    mov bl,0x1 ; @05B04
    call sub_5D66 ; @05B06
    add si,byte +0x8 ; @05B09
    pop cx ; @05B0C
    loop loc_5B00 ; @05B0D
    pop ds ; @05B0F
    ret ; @05B10
sub_5B11:
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @05B11
loc_5B13:
    push cx ; @05B13
    push si ; @05B14
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @05B15
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05B17
loc_5B19:
    push cx ; @05B19
    db 0x8a,0xea ; ENCODED: mov ch,dl (NASM chooses a different encoding) ; @05B1A
loc_5B1C:
    mov ah,[si] ; @05B1C
    mov al,[si+0x1] ; @05B1E
    add si,byte +0x2 ; @05B21
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05B24
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @05B26
    jz loc_5B36 ; @05B28
    db 0x8a,0xf9 ; ENCODED: mov bh,cl (NASM chooses a different encoding) ; @05B2A
loc_5B2C:
    shr ah,1 ; @05B2C
    rcr al,1 ; @05B2E
    rcr bl,1 ; @05B30
    dec bh ; @05B32
    jnz loc_5B2C ; @05B34
loc_5B36:
    mov [es:di],ah ; @05B36
    mov [es:di+0x1],al ; @05B39
    mov [es:di+0x2],bl ; @05B3D
    add di,byte +0x3 ; @05B41
    dec ch ; @05B44
    jnz loc_5B1C ; @05B46
    pop cx ; @05B48
    dec ch ; @05B49
    jnz loc_5B19 ; @05B4B
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @05B4D
    db 0x8a,0xea ; ENCODED: mov ch,dl (NASM chooses a different encoding) ; @05B4F
loc_5B51:
    push si ; @05B51
    push cx ; @05B52
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05B53
    push dx ; @05B55
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @05B56
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @05B58
    db 0x03,0xd2 ; ENCODED: add dx,dx (NASM chooses a different encoding) ; @05B5A
    db 0x03,0xea ; ENCODED: add bp,dx (NASM chooses a different encoding) ; @05B5C
    pop dx ; @05B5E
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05B5F
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05B61
loc_5B63:
    or ah,[es:si] ; @05B63
    or al,[es:si+0x1] ; @05B66
    or bl,[es:si+0x2] ; @05B6A
    db 0x03,0xf5 ; ENCODED: add si,bp (NASM chooses a different encoding) ; @05B6E
    dec ch ; @05B70
    jnz loc_5B63 ; @05B72
    mov [es:di],ah ; @05B74
    mov [es:di+0x1],al ; @05B77
    mov [es:di+0x2],bl ; @05B7B
    add di,byte +0x3 ; @05B7F
    pop cx ; @05B82
    pop si ; @05B83
    add si,byte +0x3 ; @05B84
    dec ch ; @05B87
    jnz loc_5B51 ; @05B89
    pop si ; @05B8B
    pop cx ; @05B8C
    inc cl ; @05B8D
    cmp cl,0x8 ; @05B8F
    jz loc_5B97 ; @05B92
    jmp loc_5B13 ; @05B94
loc_5B97:
    cmp di,byte +0x10 ; @05B97
    jl loc_5BAF ; @05B9A
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @05B9C
    shr ax,1 ; @05B9E
    shr ax,1 ; @05BA0
    shr ax,1 ; @05BA2
    shr ax,1 ; @05BA4
    mov cx,es ; @05BA6
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05BA8
    mov es,ax ; @05BAA
    and di,byte +0xf ; @05BAC
loc_5BAF:
    ret ; @05BAF
sub_5BB0:
    push si ; @05BB0
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @05BB1
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05BB3
loc_5BB5:
    push cx ; @05BB5
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @05BB6
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05BB8
    rep movsw ; @05BBA
    pop cx ; @05BBC
    dec ch ; @05BBD
    jnz loc_5BB5 ; @05BBF
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @05BC1
    db 0x8a,0xea ; ENCODED: mov ch,dl (NASM chooses a different encoding) ; @05BC3
loc_5BC5:
    push si ; @05BC5
    push cx ; @05BC6
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05BC7
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05BC9
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05BCB
    shl ax,1 ; @05BCD
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @05BCF
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05BD1
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05BD3
loc_5BD5:
    or al,[es:si] ; @05BD5
    or ah,[es:si+0x1] ; @05BD8
    db 0x03,0xf5 ; ENCODED: add si,bp (NASM chooses a different encoding) ; @05BDC
    dec ch ; @05BDE
    jnz loc_5BD5 ; @05BE0
    stosw ; @05BE2
    pop cx ; @05BE3
    pop si ; @05BE4
    add si,byte +0x2 ; @05BE5
    dec ch ; @05BE8
    jnz loc_5BC5 ; @05BEA
    pop si ; @05BEC
    cmp di,byte +0x10 ; @05BED
    jl loc_5C05 ; @05BF0
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @05BF2
    shr ax,1 ; @05BF4
    shr ax,1 ; @05BF6
    shr ax,1 ; @05BF8
    shr ax,1 ; @05BFA
    mov cx,es ; @05BFC
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05BFE
    mov es,ax ; @05C00
    and di,byte +0xf ; @05C02
loc_5C05:
    ret ; @05C05
sub_5C06:
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @05C06
loc_5C08:
    push cx ; @05C08
    push si ; @05C09
    push di ; @05C0A
    mov ch,0x3 ; @05C0B
loc_5C0D:
    push cx ; @05C0D
    mov ch,0x20 ; @05C0E
loc_5C10:
    mov ah,[si] ; @05C10
    mov al,[si+0x1] ; @05C12
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @05C15
    mov dh,[si+0x2] ; @05C17
    mov dl,[si+0x3] ; @05C1A
    add si,byte +0x4 ; @05C1D
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05C20
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @05C22
    jz loc_5C32 ; @05C24
    db 0x8a,0xf9 ; ENCODED: mov bh,cl (NASM chooses a different encoding) ; @05C26
loc_5C28:
    shr bp,1 ; @05C28
    rcr dx,1 ; @05C2A
    rcr bl,1 ; @05C2C
    dec bh ; @05C2E
    jnz loc_5C28 ; @05C30
loc_5C32:
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @05C32
    mov [es:di],ah ; @05C34
    mov [es:di+0x1],al ; @05C37
    mov [es:di+0x2],dh ; @05C3B
    mov [es:di+0x3],dl ; @05C3F
    mov [es:di+0x4],bl ; @05C43
    add di,byte +0x5 ; @05C47
    dec ch ; @05C4A
    jnz loc_5C10 ; @05C4C
    pop cx ; @05C4E
    dec ch ; @05C4F
    jnz loc_5C0D ; @05C51
    pop si ; @05C53
    mov ch,0x20 ; @05C54
loc_5C56:
    push si ; @05C56
    push cx ; @05C57
    mov bh,0x3 ; @05C58
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @05C5A
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05C5C
    db 0x33,0xd2 ; ENCODED: xor dx,dx (NASM chooses a different encoding) ; @05C5E
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05C60
loc_5C62:
    or ah,[es:si] ; @05C62
    or al,[es:si+0x1] ; @05C65
    or ch,[es:si+0x2] ; @05C69
    or cl,[es:si+0x3] ; @05C6D
    or dh,[es:si+0x4] ; @05C71
    add si,0xa0 ; @05C75
    dec bh ; @05C79
    jnz loc_5C62 ; @05C7B
    mov [es:di],ah ; @05C7D
    mov [es:di+0x1],al ; @05C80
    mov [es:di+0x2],ch ; @05C84
    mov [es:di+0x3],cl ; @05C88
    mov [es:di+0x4],dh ; @05C8C
    add di,byte +0x5 ; @05C90
    pop cx ; @05C93
    pop si ; @05C94
    add si,byte +0x5 ; @05C95
    dec ch ; @05C98
    jnz loc_5C56 ; @05C9A
    pop si ; @05C9C
    pop cx ; @05C9D
    inc cl ; @05C9E
    cmp cl,0x8 ; @05CA0
    jz loc_5CA8 ; @05CA3
    jmp loc_5C08 ; @05CA5
loc_5CA8:
    cmp di,byte +0x10 ; @05CA8
    jl loc_5CC0 ; @05CAB
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @05CAD
    shr ax,1 ; @05CAF
    shr ax,1 ; @05CB1
    shr ax,1 ; @05CB3
    shr ax,1 ; @05CB5
    mov cx,es ; @05CB7
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05CB9
    mov es,ax ; @05CBB
    and di,byte +0xf ; @05CBD
loc_5CC0:
    ret ; @05CC0
sub_5CC1:
    mov si,0x52bc ; @05CC1
    mov es,[0x1fea] ; @05CC4
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05CC8
    mov cx,0x10 ; @05CCA
    mov bl,0x3 ; @05CCD
    call sub_5CDD ; @05CCF
    mov si,0x531c ; @05CD2
    mov di,0x480 ; @05CD5
    mov bl,0x3 ; @05CD8
    mov cx,0x10 ; @05CDA
sub_5CDD:
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @05CDD
loc_5CDF:
    push dx ; @05CDF
    push bx ; @05CE0
    push si ; @05CE1
loc_5CE2:
    push bx ; @05CE2
    push cx ; @05CE3
loc_5CE4:
    push cx ; @05CE4
    lodsw ; @05CE5
    db 0x32,0xd2 ; ENCODED: xor dl,dl (NASM chooses a different encoding) ; @05CE6
    db 0x22,0xf6 ; ENCODED: and dh,dh (NASM chooses a different encoding) ; @05CE8
    jz loc_5CF8 ; @05CEA
    db 0x8a,0xfe ; ENCODED: mov bh,dh (NASM chooses a different encoding) ; @05CEC
loc_5CEE:
    shr al,1 ; @05CEE
    rcr ah,1 ; @05CF0
    rcr dl,1 ; @05CF2
    dec bh ; @05CF4
    jnz loc_5CEE ; @05CF6
loc_5CF8:
    mov [es:di],al ; @05CF8
    inc di ; @05CFB
    mov [es:di],ah ; @05CFC
    inc di ; @05CFF
    mov [es:di],dl ; @05D00
    inc di ; @05D03
    pop cx ; @05D04
    loop loc_5CE4 ; @05D05
    pop cx ; @05D07
    pop bx ; @05D08
    dec bl ; @05D09
    jnz loc_5CE2 ; @05D0B
    pop si ; @05D0D
    pop bx ; @05D0E
    pop dx ; @05D0F
    inc dh ; @05D10
    cmp dh,0x8 ; @05D12
    jnz loc_5CDF ; @05D15
    ret ; @05D17
; UNKNOWN: unresolved bytes
    db 0x32,0xf6,0x52,0x53,0x56,0x53,0x51,0x51,0x53,0xad,0x8b,0xd8,0xad,0x32,0xd2,0x22 ; @05D18
; UNKNOWN: unresolved bytes
    db 0xf6,0x74,0x12,0x51,0x8a,0xee,0xd0,0xeb,0xd0,0xdf,0xd0,0xd8,0xd0,0xdc,0xd0,0xda ; @05D28
; UNKNOWN: unresolved bytes
    db 0xfe,0xcd,0x75,0xf2,0x59,0x26,0x88,0x1d,0x47,0x26,0x88,0x3d,0x47,0x26,0x88,0x05 ; @05D38
; UNKNOWN: unresolved bytes
    db 0x47,0x26,0x88,0x25,0x47,0x26,0x88,0x15,0x47,0x5b,0x59,0xe2,0xca,0x59,0x5b,0xfe ; @05D48
; UNKNOWN: unresolved bytes
    db 0xcb,0x75,0xc2,0x5e,0x5b,0x5a,0xfe,0xc6,0x80,0xfe,0x08,0x75,0xb5,0xc3 ; @05D58
sub_5D66:
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @05D66
loc_5D68:
    push dx ; @05D68
    push bx ; @05D69
    push si ; @05D6A
loc_5D6B:
    push bx ; @05D6B
    push cx ; @05D6C
loc_5D6D:
    push cx ; @05D6D
    lodsb ; @05D6E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05D6F
    db 0x22,0xf6 ; ENCODED: and dh,dh (NASM chooses a different encoding) ; @05D71
    jz loc_5D7F ; @05D73
    db 0x8a,0xfe ; ENCODED: mov bh,dh (NASM chooses a different encoding) ; @05D75
loc_5D77:
    shr al,1 ; @05D77
    rcr ah,1 ; @05D79
    dec bh ; @05D7B
    jnz loc_5D77 ; @05D7D
loc_5D7F:
    stosw ; @05D7F
    pop cx ; @05D80
    loop loc_5D6D ; @05D81
    pop cx ; @05D83
    pop bx ; @05D84
    dec bl ; @05D85
    jnz loc_5D6B ; @05D87
    pop si ; @05D89
    pop bx ; @05D8A
    pop dx ; @05D8B
    inc dh ; @05D8C
    cmp dh,0x8 ; @05D8E
    jnz loc_5D68 ; @05D91
    ret ; @05D93
sub_5D94:
    mov dx,0x3c4 ; @05D94
    mov ax,0xf02 ; @05D97
    mov [ss:0x8],ax ; @05D9A
    out dx,ax ; @05D9E
    mov dx,0x3ce ; @05D9F
    mov ax,0x805 ; @05DA2
    mov [ss:0x0],ax ; @05DA5
    out dx,ax ; @05DA9
    mov ax,0x807 ; @05DAA
    mov [ss:0x6],ax ; @05DAD
    out dx,ax ; @05DB1
    mov ax,0x802 ; @05DB2
    mov [ss:0x4],ax ; @05DB5
    out dx,ax ; @05DB9
    mov ax,0xa000 ; @05DBA
    mov es,ax ; @05DBD
    mov word [0x4],0xd0 ; @05DBF
    ret ; @05DC5
sub_5DC6:
    mov ax,0xa000 ; @05DC6
    mov es,ax ; @05DC9
    mov di,[si+0x2] ; @05DCB
    sub di,byte +0x10 ; @05DCE
    jns loc_5DD5 ; @05DD1
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05DD3
loc_5DD5:
    push dx ; @05DD5
    mov ax,0xd0 ; @05DD6
    mul di ; @05DD9
    pop dx ; @05DDB
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @05DDC
    mov cx,[si] ; @05DDE
    db 0x8b,0xd9 ; ENCODED: mov bx,cx (NASM chooses a different encoding) ; @05DE0
    shr cx,1 ; @05DE2
    shr cx,1 ; @05DE4
    shr cx,1 ; @05DE6
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @05DE8
    add di,0x4a40 ; @05DEA
    and bx,byte +0x7 ; @05DEE
    add bx,0x547c ; @05DF1
    mov ah,[bx] ; @05DF5
    ret ; @05DF7
sub_5DF8:
    mov dx,0x3ce ; @05DF8
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05DFB
    mov [ss:0xa],ax ; @05DFD
    out dx,ax ; @05E01
    mov ax,0xf01 ; @05E02
    mov [ss:0xc],ax ; @05E05
    out dx,ax ; @05E09
    mov ax,0x3 ; @05E0A
    mov [ss:0x2],ax ; @05E0D
    out dx,ax ; @05E11
    mov ax,0xa000 ; @05E12
    mov es,ax ; @05E15
    mov cx,0x16 ; @05E17
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @05E1A
    mov di,[si+0x2] ; @05E1C
    sub di,byte +0x1e ; @05E1F
    jns loc_5E34 ; @05E22
    db 0x03,0xcf ; ENCODED: add cx,di (NASM chooses a different encoding) ; @05E24
    neg di ; @05E26
    cmp di,byte +0x15 ; @05E28
    jna loc_5E30 ; @05E2B
    jmp loc_5EB9 ; @05E2D
loc_5E30:
    db 0x8b,0xdf ; ENCODED: mov bx,di (NASM chooses a different encoding) ; @05E30
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05E32
loc_5E34:
    push cx ; @05E34
    push bx ; @05E35
    mov ax,0xd0 ; @05E36
    push dx ; @05E39
    mul di ; @05E3A
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @05E3C
    pop dx ; @05E3E
    mov cx,[si] ; @05E3F
    sub cx,byte +0x8 ; @05E41
    shr cx,1 ; @05E44
    shr cx,1 ; @05E46
    shr cx,1 ; @05E48
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @05E4A
    add di,0x4a40 ; @05E4C
    pop ax ; @05E50
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @05E51
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05E53
    db 0x03,0xc3 ; ENCODED: add ax,bx (NASM chooses a different encoding) ; @05E55
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @05E57
    pop cx ; @05E59
    push si ; @05E5A
    mov ax,[si] ; @05E5B
    sub ax,0x8 ; @05E5D
    and ax,0x7 ; @05E60
    shl ax,1 ; @05E63
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @05E65
    shl ax,1 ; @05E67
    shl ax,1 ; @05E69
    shl ax,1 ; @05E6B
    shl ax,1 ; @05E6D
    shl ax,1 ; @05E6F
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @05E71
    add si,0xc60 ; @05E73
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @05E77
    push ds ; @05E79
    mov ds,[0x1fe8] ; @05E7A
    cli ; @05E7E
loc_5E7F:
    lodsw ; @05E7F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @05E80
    mov ah,[es:di] ; @05E82
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05E85
    mov al,0x8 ; @05E87
    mov [ss:0xe],ax ; @05E89
    out dx,ax ; @05E8D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05E8E
    stosb ; @05E90
    mov ah,[es:di] ; @05E91
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @05E94
    mov al,0x8 ; @05E96
    mov [ss:0xe],ax ; @05E98
    out dx,ax ; @05E9C
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05E9D
    stosb ; @05E9F
    lodsb ; @05EA0
    mov ah,[es:di] ; @05EA1
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05EA4
    mov al,0x8 ; @05EA6
    mov [ss:0xe],ax ; @05EA8
    out dx,ax ; @05EAC
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05EAD
    stosb ; @05EAF
    add di,0xcd ; @05EB0
    loop loc_5E7F ; @05EB4
    sti ; @05EB6
    pop ds ; @05EB7
    pop si ; @05EB8
loc_5EB9:
    ret ; @05EB9
sub_5EBA:
    mov dx,0x3ce ; @05EBA
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05EBD
    mov [ss:0xa],ax ; @05EBF
    out dx,ax ; @05EC3
    mov ax,0xf01 ; @05EC4
    mov [ss:0xc],ax ; @05EC7
    out dx,ax ; @05ECB
    mov ax,0x3 ; @05ECC
    mov [ss:0x2],ax ; @05ECF
    out dx,ax ; @05ED3
    mov ax,0xa000 ; @05ED4
    mov es,ax ; @05ED7
    cli ; @05ED9
    mov al,[es:di] ; @05EDA
    xchg bh,al ; @05EDD
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05EDF
    mov al,0x8 ; @05EE1
    mov [ss:0xe],ax ; @05EE3
    out dx,ax ; @05EE7
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05EE8
    stosb ; @05EEA
    mov al,[es:di] ; @05EEB
    xchg bl,al ; @05EEE
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05EF0
    mov al,0x8 ; @05EF2
    mov [ss:0xe],ax ; @05EF4
    out dx,ax ; @05EF8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05EF9
    stosb ; @05EFB
    mov al,[es:di] ; @05EFC
    xchg cl,al ; @05EFF
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05F01
    mov al,0x8 ; @05F03
    mov [ss:0xe],ax ; @05F05
    out dx,ax ; @05F09
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F0A
    stosb ; @05F0C
    sti ; @05F0D
    ret ; @05F0E
sub_5F0F:
    cli ; @05F0F
    mov dx,0x3c4 ; @05F10
    mov ax,0x802 ; @05F13
    mov [ss:0x8],ax ; @05F16
    out dx,ax ; @05F1A
    mov dx,0x3ce ; @05F1B
    mov ax,0x800 ; @05F1E
    mov [ss:0xa],ax ; @05F21
    out dx,ax ; @05F25
    mov ax,0x801 ; @05F26
    mov [ss:0xc],ax ; @05F29
    out dx,ax ; @05F2D
    mov ax,0x3 ; @05F2E
    mov [ss:0x2],ax ; @05F31
    out dx,ax ; @05F35
    mov ax,0xa000 ; @05F36
    mov es,ax ; @05F39
    push word [si+0x2] ; @05F3B
    push word [si] ; @05F3E
    mov ax,[si] ; @05F40
    add ax,[si+0x4] ; @05F42
    cmp byte [si+0x27],0x0 ; @05F45
    jns loc_5F4E ; @05F49
    sub ax,0x4 ; @05F4B
loc_5F4E:
    mov [si],ax ; @05F4E
    push ax ; @05F50
    dec word [si+0x2] ; @05F51
    call sub_5DC6 ; @05F54
    pop cx ; @05F57
    pop word [si] ; @05F58
    pop word [si+0x2] ; @05F5A
    mov bx,0xfc ; @05F5D
    mov dl,0x0 ; @05F60
    and cx,byte +0x7 ; @05F62
    jz loc_5F6D ; @05F65
loc_5F67:
    shr bx,1 ; @05F67
    rcr dl,1 ; @05F69
    loop loc_5F67 ; @05F6B
loc_5F6D:
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @05F6D
    mov dx,0x3ce ; @05F6F
    mov al,[es:di] ; @05F72
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @05F75
    mov al,0x8 ; @05F77
    mov [ss:0xe],ax ; @05F79
    out dx,ax ; @05F7D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F7E
    stosb ; @05F80
    mov al,[es:di] ; @05F81
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @05F84
    mov al,0x8 ; @05F86
    mov [ss:0xe],ax ; @05F88
    out dx,ax ; @05F8C
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F8D
    stosb ; @05F8F
    mov al,[es:di] ; @05F90
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @05F93
    mov al,0x8 ; @05F95
    mov [ss:0xe],ax ; @05F97
    out dx,ax ; @05F9B
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F9C
    stosb ; @05F9E
    mov dx,0x3c4 ; @05F9F
    mov ax,0xf02 ; @05FA2
    mov [ss:0x8],ax ; @05FA5
    out dx,ax ; @05FA9
    sti ; @05FAA
    ret ; @05FAB
sub_5FAC:
    shl ax,1 ; @05FAC
    shl ax,1 ; @05FAE
    shl ax,1 ; @05FB0
    shl ax,1 ; @05FB2
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @05FB4
    shl ax,1 ; @05FB6
    shl ax,1 ; @05FB8
    shl ax,1 ; @05FBA
    shl ax,1 ; @05FBC
    db 0x2b,0xc2 ; ENCODED: sub ax,dx (NASM chooses a different encoding) ; @05FBE
    push ax ; @05FC0
    mov dx,0x3ce ; @05FC1
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05FC4
    mov [ss:0xa],ax ; @05FC6
    out dx,ax ; @05FCA
    mov ax,0xf01 ; @05FCB
    mov [ss:0xc],ax ; @05FCE
    out dx,ax ; @05FD2
    mov ax,0x3 ; @05FD3
    mov [ss:0x2],ax ; @05FD6
    out dx,ax ; @05FDA
    mov ax,0xa000 ; @05FDB
    mov es,ax ; @05FDE
    mov di,[si+0x2] ; @05FE0
    add di,[si+0x6] ; @05FE3
    sub di,byte +0x10 ; @05FE6
    mov ax,0xd0 ; @05FE9
    push dx ; @05FEC
    mul di ; @05FED
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @05FEF
    pop dx ; @05FF1
    mov cx,[si] ; @05FF2
    add cx,[si+0x4] ; @05FF4
    shr cx,1 ; @05FF7
    shr cx,1 ; @05FF9
    shr cx,1 ; @05FFB
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @05FFD
    add di,0x4a40 ; @05FFF
    pop bx ; @06003
    push si ; @06004
    cmp byte [si+0x27],0xff ; @06005
    jnz loc_600F ; @06009
    add bx,0x3c0 ; @0600B
loc_600F:
    mov ax,[si] ; @0600F
    add ax,[si+0x4] ; @06011
    and ax,0x7 ; @06014
    shl ax,1 ; @06017
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06019
    shl si,1 ; @0601B
    shl si,1 ; @0601D
    shl si,1 ; @0601F
    shl si,1 ; @06021
    db 0x2b,0xf0 ; ENCODED: sub si,ax (NASM chooses a different encoding) ; @06023
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @06025
    push ds ; @06027
    mov ds,[0x1fe8] ; @06028
    mov cx,0xa ; @0602C
    cli ; @0602F
loc_6030:
    lodsw ; @06030
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06031
    mov ah,[es:di] ; @06033
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @06036
    mov al,0x8 ; @06038
    mov [ss:0xe],ax ; @0603A
    out dx,ax ; @0603E
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0603F
    stosb ; @06041
    mov ah,[es:di] ; @06042
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06045
    mov al,0x8 ; @06047
    mov [ss:0xe],ax ; @06049
    out dx,ax ; @0604D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0604E
    stosb ; @06050
    lodsb ; @06051
    mov ah,[es:di] ; @06052
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @06055
    mov al,0x8 ; @06057
    mov [ss:0xe],ax ; @06059
    out dx,ax ; @0605D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0605E
    stosb ; @06060
    add di,0xcd ; @06061
    loop loc_6030 ; @06065
    sti ; @06067
    pop ds ; @06068
    pop si ; @06069
    ret ; @0606A
sub_606B:
    shl ax,1 ; @0606B
    shl ax,1 ; @0606D
    shl ax,1 ; @0606F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06071
    shl ax,1 ; @06073
    shl ax,1 ; @06075
    shl ax,1 ; @06077
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @06079
    shl ax,1 ; @0607B
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0607D
    shl ax,1 ; @0607F
    shl ax,1 ; @06081
    db 0x2b,0xc3 ; ENCODED: sub ax,bx (NASM chooses a different encoding) ; @06083
    add ax,0x780 ; @06085
    push ax ; @06088
    mov dx,0x3ce ; @06089
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0608C
    mov [ss:0xa],ax ; @0608E
    out dx,ax ; @06092
    mov ax,0xf01 ; @06093
    mov [ss:0xc],ax ; @06096
    out dx,ax ; @0609A
    mov ax,0x3 ; @0609B
    mov [ss:0x2],ax ; @0609E
    out dx,ax ; @060A2
    mov ax,0xa000 ; @060A3
    mov es,ax ; @060A6
    mov cx,[si] ; @060A8
    mov di,[si+0x2] ; @060AA
    cmp byte [si+0x28],0x2 ; @060AD
    jnz loc_60BA ; @060B1
    inc di ; @060B3
    mov al,[si+0x27] ; @060B4
    cbw ; @060B7
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @060B8
loc_60BA:
    add di,[si+0x6] ; @060BA
    sub di,byte +0x10 ; @060BD
    mov ax,0xd0 ; @060C0
    push dx ; @060C3
    mul di ; @060C4
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @060C6
    pop dx ; @060C8
    add cx,[si+0x4] ; @060C9
    db 0x8b,0xe9 ; ENCODED: mov bp,cx (NASM chooses a different encoding) ; @060CC
    shr cx,1 ; @060CE
    shr cx,1 ; @060D0
    shr cx,1 ; @060D2
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @060D4
    add di,0x4a40 ; @060D6
    pop bx ; @060DA
    push si ; @060DB
    cmp byte [si+0x27],0xff ; @060DC
    jnz loc_60E6 ; @060E0
    add bx,0x270 ; @060E2
loc_60E6:
    and bp,byte +0x7 ; @060E6
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @060E9
    shl si,1 ; @060EB
    shl si,1 ; @060ED
    shl si,1 ; @060EF
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @060F1
    db 0x2b,0xcd ; ENCODED: sub cx,bp (NASM chooses a different encoding) ; @060F3
    shl si,1 ; @060F5
    shl si,1 ; @060F7
    db 0x03,0xf1 ; ENCODED: add si,cx (NASM chooses a different encoding) ; @060F9
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @060FB
    push ds ; @060FD
    mov ds,[0x1fe8] ; @060FE
    mov cx,0xd ; @06102
    cli ; @06105
loc_6106:
    lodsw ; @06106
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06107
    mov ah,[es:di] ; @06109
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0610C
    mov al,0x8 ; @0610E
    mov [ss:0xe],ax ; @06110
    out dx,ax ; @06114
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06115
    stosb ; @06117
    mov ah,[es:di] ; @06118
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @0611B
    mov al,0x8 ; @0611D
    mov [ss:0xe],ax ; @0611F
    out dx,ax ; @06123
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06124
    stosb ; @06126
    lodsb ; @06127
    mov ah,[es:di] ; @06128
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0612B
    mov al,0x8 ; @0612D
    mov [ss:0xe],ax ; @0612F
    out dx,ax ; @06133
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06134
    stosb ; @06136
    add di,0xcd ; @06137
    loop loc_6106 ; @0613B
    sti ; @0613D
    pop ds ; @0613E
    pop si ; @0613F
    ret ; @06140
sub_6141:
    push bx ; @06141
    push cx ; @06142
    mov ax,0xa000 ; @06143
    mov es,ax ; @06146
    db 0x8b,0xfb ; ENCODED: mov di,bx (NASM chooses a different encoding) ; @06148
    sub di,byte +0x10 ; @0614A
    push dx ; @0614D
    mov ax,0xd0 ; @0614E
    mul di ; @06151
    pop dx ; @06153
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @06154
    db 0x8b,0xd9 ; ENCODED: mov bx,cx (NASM chooses a different encoding) ; @06156
    shr cx,1 ; @06158
    shr cx,1 ; @0615A
    shr cx,1 ; @0615C
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @0615E
    add di,0x4a40 ; @06160
    and bx,byte +0x7 ; @06164
    add bx,0x547c ; @06167
    mov ah,[bx] ; @0616B
    pop cx ; @0616D
    pop bx ; @0616E
    ret ; @0616F
sub_6170:
    push ds ; @06170
    mov dx,0x3c4 ; @06171
    mov ax,0xf02 ; @06174
    mov [ss:0x8],ax ; @06177
    out dx,ax ; @0617B
    mov dx,0x3ce ; @0617C
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0617F
    mov [ss:0xa],ax ; @06181
    out dx,ax ; @06185
    mov ax,0xe01 ; @06186
    mov [ss:0xc],ax ; @06189
    out dx,ax ; @0618D
    mov ax,0x5 ; @0618E
    mov [ss:0x0],ax ; @06191
    out dx,ax ; @06195
    mov ax,0x3 ; @06196
    mov [ss:0x2],ax ; @06199
    out dx,ax ; @0619D
    mov ds,cx ; @0619E
    mov cx,0xa000 ; @061A0
    mov es,cx ; @061A3
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @061A5
    mov cx,[bx] ; @061A7
    inc bx ; @061A9
    inc bx ; @061AA
    mov al,0x8 ; @061AB
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @061AD
    mov [ss:0xe],ax ; @061AF
    out dx,ax ; @061B3
    cli ; @061B4
    mov al,[es:di] ; @061B5
    lodsw ; @061B8
    stosb ; @061B9
    sti ; @061BA
    xchg ch,ah ; @061BB
    mov al,0x8 ; @061BD
    mov [ss:0xe],ax ; @061BF
    out dx,ax ; @061C3
    cli ; @061C4
    mov al,[es:di] ; @061C5
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @061C8
    stosb ; @061CA
    sti ; @061CB
    mov ah,[bx] ; @061CC
    inc bx ; @061CE
    mov al,0x8 ; @061CF
    mov [ss:0xe],ax ; @061D1
    out dx,ax ; @061D5
    cli ; @061D6
    mov al,[es:di] ; @061D7
    lodsb ; @061DA
    stosb ; @061DB
    sti ; @061DC
    add di,byte +0x29 ; @061DD
    mov cx,[bx] ; @061E0
    inc bx ; @061E2
    inc bx ; @061E3
    mov al,0x8 ; @061E4
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @061E6
    mov [ss:0xe],ax ; @061E8
    out dx,ax ; @061EC
    cli ; @061ED
    mov al,[es:di] ; @061EE
    lodsw ; @061F1
    stosb ; @061F2
    sti ; @061F3
    xchg ch,ah ; @061F4
    mov al,0x8 ; @061F6
    mov [ss:0xe],ax ; @061F8
    out dx,ax ; @061FC
    cli ; @061FD
    mov al,[es:di] ; @061FE
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06201
    stosb ; @06203
    sti ; @06204
    mov ah,[bx] ; @06205
    inc bx ; @06207
    mov al,0x8 ; @06208
    mov [ss:0xe],ax ; @0620A
    out dx,ax ; @0620E
    cli ; @0620F
    mov al,[es:di] ; @06210
    lodsb ; @06213
    stosb ; @06214
    sti ; @06215
    add di,byte +0x29 ; @06216
    mov cx,[bx] ; @06219
    inc bx ; @0621B
    inc bx ; @0621C
    mov al,0x8 ; @0621D
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0621F
    mov [ss:0xe],ax ; @06221
    out dx,ax ; @06225
    cli ; @06226
    mov al,[es:di] ; @06227
    lodsw ; @0622A
    stosb ; @0622B
    sti ; @0622C
    xchg ch,ah ; @0622D
    mov al,0x8 ; @0622F
    mov [ss:0xe],ax ; @06231
    out dx,ax ; @06235
    cli ; @06236
    mov al,[es:di] ; @06237
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0623A
    stosb ; @0623C
    sti ; @0623D
    mov ah,[bx] ; @0623E
    inc bx ; @06240
    mov al,0x8 ; @06241
    mov [ss:0xe],ax ; @06243
    out dx,ax ; @06247
    cli ; @06248
    mov al,[es:di] ; @06249
    lodsb ; @0624C
    stosb ; @0624D
    sti ; @0624E
    add di,byte +0x29 ; @0624F
    mov cx,[bx] ; @06252
    inc bx ; @06254
    inc bx ; @06255
    mov al,0x8 ; @06256
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06258
    mov [ss:0xe],ax ; @0625A
    out dx,ax ; @0625E
    cli ; @0625F
    mov al,[es:di] ; @06260
    lodsw ; @06263
    stosb ; @06264
    sti ; @06265
    xchg ch,ah ; @06266
    mov al,0x8 ; @06268
    mov [ss:0xe],ax ; @0626A
    out dx,ax ; @0626E
    cli ; @0626F
    mov al,[es:di] ; @06270
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06273
    stosb ; @06275
    sti ; @06276
    mov ah,[bx] ; @06277
    inc bx ; @06279
    mov al,0x8 ; @0627A
    mov [ss:0xe],ax ; @0627C
    out dx,ax ; @06280
    cli ; @06281
    mov al,[es:di] ; @06282
    lodsb ; @06285
    stosb ; @06286
    sti ; @06287
    add di,byte +0x29 ; @06288
    mov cx,[bx] ; @0628B
    inc bx ; @0628D
    inc bx ; @0628E
    mov al,0x8 ; @0628F
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06291
    mov [ss:0xe],ax ; @06293
    out dx,ax ; @06297
    cli ; @06298
    mov al,[es:di] ; @06299
    lodsw ; @0629C
    stosb ; @0629D
    sti ; @0629E
    xchg ch,ah ; @0629F
    mov al,0x8 ; @062A1
    mov [ss:0xe],ax ; @062A3
    out dx,ax ; @062A7
    cli ; @062A8
    mov al,[es:di] ; @062A9
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @062AC
    stosb ; @062AE
    sti ; @062AF
    mov ah,[bx] ; @062B0
    inc bx ; @062B2
    mov al,0x8 ; @062B3
    mov [ss:0xe],ax ; @062B5
    out dx,ax ; @062B9
    cli ; @062BA
    mov al,[es:di] ; @062BB
    lodsb ; @062BE
    stosb ; @062BF
    sti ; @062C0
    add di,byte +0x29 ; @062C1
    mov cx,[bx] ; @062C4
    inc bx ; @062C6
    inc bx ; @062C7
    mov al,0x8 ; @062C8
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @062CA
    mov [ss:0xe],ax ; @062CC
    out dx,ax ; @062D0
    cli ; @062D1
    mov al,[es:di] ; @062D2
    lodsw ; @062D5
    stosb ; @062D6
    sti ; @062D7
    xchg ch,ah ; @062D8
    mov al,0x8 ; @062DA
    mov [ss:0xe],ax ; @062DC
    out dx,ax ; @062E0
    cli ; @062E1
    mov al,[es:di] ; @062E2
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @062E5
    stosb ; @062E7
    sti ; @062E8
    mov ah,[bx] ; @062E9
    inc bx ; @062EB
    mov al,0x8 ; @062EC
    mov [ss:0xe],ax ; @062EE
    out dx,ax ; @062F2
    cli ; @062F3
    mov al,[es:di] ; @062F4
    lodsb ; @062F7
    stosb ; @062F8
    sti ; @062F9
    add di,byte +0x29 ; @062FA
    mov cx,[bx] ; @062FD
    inc bx ; @062FF
    inc bx ; @06300
    mov al,0x8 ; @06301
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06303
    mov [ss:0xe],ax ; @06305
    out dx,ax ; @06309
    cli ; @0630A
    mov al,[es:di] ; @0630B
    lodsw ; @0630E
    stosb ; @0630F
    sti ; @06310
    xchg ch,ah ; @06311
    mov al,0x8 ; @06313
    mov [ss:0xe],ax ; @06315
    out dx,ax ; @06319
    cli ; @0631A
    mov al,[es:di] ; @0631B
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0631E
    stosb ; @06320
    sti ; @06321
    mov ah,[bx] ; @06322
    inc bx ; @06324
    mov al,0x8 ; @06325
    mov [ss:0xe],ax ; @06327
    out dx,ax ; @0632B
    cli ; @0632C
    mov al,[es:di] ; @0632D
    lodsb ; @06330
    stosb ; @06331
    sti ; @06332
    add di,byte +0x29 ; @06333
    mov cx,[bx] ; @06336
    inc bx ; @06338
    inc bx ; @06339
    mov al,0x8 ; @0633A
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0633C
    mov [ss:0xe],ax ; @0633E
    out dx,ax ; @06342
    cli ; @06343
    mov al,[es:di] ; @06344
    lodsw ; @06347
    stosb ; @06348
    sti ; @06349
    xchg ch,ah ; @0634A
    mov al,0x8 ; @0634C
    mov [ss:0xe],ax ; @0634E
    out dx,ax ; @06352
    cli ; @06353
    mov al,[es:di] ; @06354
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06357
    stosb ; @06359
    sti ; @0635A
    mov ah,[bx] ; @0635B
    inc bx ; @0635D
    mov al,0x8 ; @0635E
    mov [ss:0xe],ax ; @06360
    out dx,ax ; @06364
    cli ; @06365
    mov al,[es:di] ; @06366
    lodsb ; @06369
    stosb ; @0636A
    sti ; @0636B
    add di,byte +0x29 ; @0636C
    mov cx,[bx] ; @0636F
    inc bx ; @06371
    inc bx ; @06372
    mov al,0x8 ; @06373
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06375
    mov [ss:0xe],ax ; @06377
    out dx,ax ; @0637B
    cli ; @0637C
    mov al,[es:di] ; @0637D
    lodsw ; @06380
    stosb ; @06381
    sti ; @06382
    xchg ch,ah ; @06383
    mov al,0x8 ; @06385
    mov [ss:0xe],ax ; @06387
    out dx,ax ; @0638B
    cli ; @0638C
    mov al,[es:di] ; @0638D
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06390
    stosb ; @06392
    sti ; @06393
    mov ah,[bx] ; @06394
    inc bx ; @06396
    mov al,0x8 ; @06397
    mov [ss:0xe],ax ; @06399
    out dx,ax ; @0639D
    cli ; @0639E
    mov al,[es:di] ; @0639F
    lodsb ; @063A2
    stosb ; @063A3
    sti ; @063A4
    add di,byte +0x29 ; @063A5
    mov cx,[bx] ; @063A8
    inc bx ; @063AA
    inc bx ; @063AB
    mov al,0x8 ; @063AC
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @063AE
    mov [ss:0xe],ax ; @063B0
    out dx,ax ; @063B4
    cli ; @063B5
    mov al,[es:di] ; @063B6
    lodsw ; @063B9
    stosb ; @063BA
    sti ; @063BB
    xchg ch,ah ; @063BC
    mov al,0x8 ; @063BE
    mov [ss:0xe],ax ; @063C0
    out dx,ax ; @063C4
    cli ; @063C5
    mov al,[es:di] ; @063C6
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @063C9
    stosb ; @063CB
    sti ; @063CC
    mov ah,[bx] ; @063CD
    inc bx ; @063CF
    mov al,0x8 ; @063D0
    mov [ss:0xe],ax ; @063D2
    out dx,ax ; @063D6
    cli ; @063D7
    mov al,[es:di] ; @063D8
    lodsb ; @063DB
    stosb ; @063DC
    sti ; @063DD
    add di,byte +0x29 ; @063DE
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @063E1
    mov ax,0x1 ; @063E3
    mov [ss:0xc],ax ; @063E6
    out dx,ax ; @063EA
    mov ax,0x1003 ; @063EB
    mov [ss:0x2],ax ; @063EE
    out dx,ax ; @063F2
    mov ax,0xff08 ; @063F3
    mov [ss:0xe],ax ; @063F6
    out dx,ax ; @063FA
    mov dl,0xc4 ; @063FB
    mov ax,0x202 ; @063FD
    mov [ss:0x8],ax ; @06400
    out dx,ax ; @06404
    cli ; @06405
    mov al,[es:di] ; @06406
    lodsw ; @06409
    stosb ; @0640A
    mov al,[es:di] ; @0640B
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0640E
    stosb ; @06410
    mov al,[es:di] ; @06411
    lodsb ; @06414
    stosb ; @06415
    sti ; @06416
    add di,byte +0x29 ; @06417
    cli ; @0641A
    mov al,[es:di] ; @0641B
    lodsw ; @0641E
    stosb ; @0641F
    mov al,[es:di] ; @06420
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06423
    stosb ; @06425
    mov al,[es:di] ; @06426
    lodsb ; @06429
    stosb ; @0642A
    sti ; @0642B
    add di,byte +0x29 ; @0642C
    cli ; @0642F
    mov al,[es:di] ; @06430
    lodsw ; @06433
    stosb ; @06434
    mov al,[es:di] ; @06435
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06438
    stosb ; @0643A
    mov al,[es:di] ; @0643B
    lodsb ; @0643E
    stosb ; @0643F
    sti ; @06440
    add di,byte +0x29 ; @06441
    cli ; @06444
    mov al,[es:di] ; @06445
    lodsw ; @06448
    stosb ; @06449
    mov al,[es:di] ; @0644A
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0644D
    stosb ; @0644F
    mov al,[es:di] ; @06450
    lodsb ; @06453
    stosb ; @06454
    sti ; @06455
    add di,byte +0x29 ; @06456
    cli ; @06459
    mov al,[es:di] ; @0645A
    lodsw ; @0645D
    stosb ; @0645E
    mov al,[es:di] ; @0645F
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06462
    stosb ; @06464
    mov al,[es:di] ; @06465
    lodsb ; @06468
    stosb ; @06469
    sti ; @0646A
    add di,byte +0x29 ; @0646B
    cli ; @0646E
    mov al,[es:di] ; @0646F
    lodsw ; @06472
    stosb ; @06473
    mov al,[es:di] ; @06474
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06477
    stosb ; @06479
    mov al,[es:di] ; @0647A
    lodsb ; @0647D
    stosb ; @0647E
    sti ; @0647F
    add di,byte +0x29 ; @06480
    cli ; @06483
    mov al,[es:di] ; @06484
    lodsw ; @06487
    stosb ; @06488
    mov al,[es:di] ; @06489
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0648C
    stosb ; @0648E
    mov al,[es:di] ; @0648F
    lodsb ; @06492
    stosb ; @06493
    sti ; @06494
    add di,byte +0x29 ; @06495
    cli ; @06498
    mov al,[es:di] ; @06499
    lodsw ; @0649C
    stosb ; @0649D
    mov al,[es:di] ; @0649E
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @064A1
    stosb ; @064A3
    mov al,[es:di] ; @064A4
    lodsb ; @064A7
    stosb ; @064A8
    sti ; @064A9
    add di,byte +0x29 ; @064AA
    cli ; @064AD
    mov al,[es:di] ; @064AE
    lodsw ; @064B1
    stosb ; @064B2
    mov al,[es:di] ; @064B3
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @064B6
    stosb ; @064B8
    mov al,[es:di] ; @064B9
    lodsb ; @064BC
    stosb ; @064BD
    sti ; @064BE
    add di,byte +0x29 ; @064BF
    cli ; @064C2
    mov al,[es:di] ; @064C3
    lodsw ; @064C6
    stosb ; @064C7
    mov al,[es:di] ; @064C8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @064CB
    stosb ; @064CD
    mov al,[es:di] ; @064CE
    lodsb ; @064D1
    stosb ; @064D2
    sti ; @064D3
    add di,byte +0x29 ; @064D4
    pop ds ; @064D7
    ret ; @064D8
sub_64D9:
    push ds ; @064D9
    mov ds,cx ; @064DA
    xchg dx,cx ; @064DC
    mov dx,0x3c4 ; @064DE
    mov ax,0xf02 ; @064E1
    mov [ss:0x8],ax ; @064E4
    out dx,ax ; @064E8
    mov dx,0x3ce ; @064E9
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @064EC
    mov [ss:0xa],ax ; @064EE
    out dx,ax ; @064F2
    mov ax,0xe01 ; @064F3
    mov [ss:0xc],ax ; @064F6
    out dx,ax ; @064FA
    mov ax,0x5 ; @064FB
    mov [ss:0x0],ax ; @064FE
    out dx,ax ; @06502
    mov ax,0x3 ; @06503
    mov [ss:0x2],ax ; @06506
    out dx,ax ; @0650A
    mov ax,0xa000 ; @0650B
    mov es,ax ; @0650E
    push di ; @06510
    mov bp,0xc ; @06511
loc_6514:
    push bp ; @06514
    lodsw ; @06515
    push si ; @06516
    xchg al,ah ; @06517
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06519
    mov ax,[bx] ; @0651B
    add bx,byte +0x2 ; @0651D
    xchg al,ah ; @06520
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06522
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06524
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06526
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06528
    jz loc_6538 ; @0652A
loc_652C:
    shr si,1 ; @0652C
    rcr al,1 ; @0652E
    shr bp,1 ; @06530
    rcr ah,1 ; @06532
    dec ch ; @06534
    jnz loc_652C ; @06536
loc_6538:
    push bx ; @06538
    push cx ; @06539
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @0653A
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @0653C
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0653E
    mov al,0x8 ; @06540
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06542
    mov [ss:0xe],ax ; @06544
    out dx,ax ; @06548
    cli ; @06549
    mov al,[es:di] ; @0654A
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0654D
    stosb ; @0654F
    sti ; @06550
    mov al,0x8 ; @06551
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06553
    mov [ss:0xe],ax ; @06555
    out dx,ax ; @06559
    cli ; @0655A
    mov al,[es:di] ; @0655B
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0655E
    stosb ; @06560
    sti ; @06561
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06562
    mov al,0x8 ; @06564
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06566
    mov [ss:0xe],ax ; @06568
    out dx,ax ; @0656C
    cli ; @0656D
    mov al,[es:di] ; @0656E
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06571
    stosb ; @06573
    sti ; @06574
    add di,byte +0x29 ; @06575
    pop cx ; @06578
    pop bx ; @06579
    pop si ; @0657A
    pop bp ; @0657B
    dec bp ; @0657C
    jnz loc_6514 ; @0657D
    pop di ; @0657F
    mov ax,0x1 ; @06580
    mov [ss:0xc],ax ; @06583
    out dx,ax ; @06587
    mov ax,0x1003 ; @06588
    mov [ss:0x2],ax ; @0658B
    out dx,ax ; @0658F
    mov ax,0xff08 ; @06590
    mov [ss:0xe],ax ; @06593
    out dx,ax ; @06597
    mov dl,0xc4 ; @06598
    mov ax,0x202 ; @0659A
    mov [ss:0x8],ax ; @0659D
    out dx,ax ; @065A1
    mov bp,0xc ; @065A2
loc_65A5:
    lodsw ; @065A5
    xchg al,ah ; @065A6
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @065A8
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @065AA
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @065AC
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @065AE
    jz loc_65BA ; @065B0
loc_65B2:
    shr bx,1 ; @065B2
    rcr al,1 ; @065B4
    dec ch ; @065B6
    jnz loc_65B2 ; @065B8
loc_65BA:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @065BA
    cli ; @065BC
    mov al,[es:di] ; @065BD
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @065C0
    stosb ; @065C2
    mov al,[es:di] ; @065C3
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @065C6
    stosb ; @065C8
    mov al,[es:di] ; @065C9
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @065CC
    stosb ; @065CE
    sti ; @065CF
    add di,byte +0x29 ; @065D0
    dec bp ; @065D3
    jnz loc_65A5 ; @065D4
    pop ds ; @065D6
    ret ; @065D7
sub_65D8:
    push ds ; @065D8
    mov ds,cx ; @065D9
    xchg dx,cx ; @065DB
    mov dx,0x3c4 ; @065DD
    mov ax,0xf02 ; @065E0
    mov [ss:0x8],ax ; @065E3
    out dx,ax ; @065E7
    mov dx,0x3ce ; @065E8
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @065EB
    mov [ss:0xa],ax ; @065ED
    out dx,ax ; @065F1
    mov ax,0xe01 ; @065F2
    mov [ss:0xc],ax ; @065F5
    out dx,ax ; @065F9
    mov ax,0x5 ; @065FA
    mov [ss:0x0],ax ; @065FD
    out dx,ax ; @06601
    mov ax,0x3 ; @06602
    mov [ss:0x2],ax ; @06605
    out dx,ax ; @06609
    mov ax,0xa000 ; @0660A
    mov es,ax ; @0660D
    push di ; @0660F
    mov bp,0xd ; @06610
loc_6613:
    push bp ; @06613
    lodsw ; @06614
    push si ; @06615
    xchg al,ah ; @06616
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06618
    mov ax,[bx] ; @0661A
    add bx,byte +0x2 ; @0661C
    xchg al,ah ; @0661F
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06621
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06623
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06625
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06627
    jz loc_6637 ; @06629
loc_662B:
    shr si,1 ; @0662B
    rcr al,1 ; @0662D
    shr bp,1 ; @0662F
    rcr ah,1 ; @06631
    dec ch ; @06633
    jnz loc_662B ; @06635
loc_6637:
    push bx ; @06637
    push cx ; @06638
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06639
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @0663B
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0663D
    mov al,0x8 ; @0663F
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06641
    mov [ss:0xe],ax ; @06643
    out dx,ax ; @06647
    cli ; @06648
    mov al,[es:di] ; @06649
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0664C
    stosb ; @0664E
    sti ; @0664F
    mov al,0x8 ; @06650
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06652
    mov [ss:0xe],ax ; @06654
    out dx,ax ; @06658
    cli ; @06659
    mov al,[es:di] ; @0665A
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0665D
    stosb ; @0665F
    sti ; @06660
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06661
    mov al,0x8 ; @06663
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06665
    mov [ss:0xe],ax ; @06667
    out dx,ax ; @0666B
    cli ; @0666C
    mov al,[es:di] ; @0666D
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06670
    stosb ; @06672
    sti ; @06673
    add di,byte +0x29 ; @06674
    pop cx ; @06677
    pop bx ; @06678
    pop si ; @06679
    pop bp ; @0667A
    dec bp ; @0667B
    jnz loc_6613 ; @0667C
    pop di ; @0667E
    mov ax,0x1 ; @0667F
    mov [ss:0xc],ax ; @06682
    out dx,ax ; @06686
    mov ax,0x1003 ; @06687
    mov [ss:0x2],ax ; @0668A
    out dx,ax ; @0668E
    mov ax,0xff08 ; @0668F
    mov [ss:0xe],ax ; @06692
    out dx,ax ; @06696
    mov dl,0xc4 ; @06697
    mov ax,0x202 ; @06699
    mov [ss:0x8],ax ; @0669C
    out dx,ax ; @066A0
    mov bp,0xd ; @066A1
loc_66A4:
    lodsw ; @066A4
    xchg al,ah ; @066A5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @066A7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @066A9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @066AB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @066AD
    jz loc_66B9 ; @066AF
loc_66B1:
    shr bx,1 ; @066B1
    rcr al,1 ; @066B3
    dec ch ; @066B5
    jnz loc_66B1 ; @066B7
loc_66B9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @066B9
    cli ; @066BB
    mov al,[es:di] ; @066BC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @066BF
    stosb ; @066C1
    mov al,[es:di] ; @066C2
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @066C5
    stosb ; @066C7
    mov al,[es:di] ; @066C8
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @066CB
    stosb ; @066CD
    sti ; @066CE
    add di,byte +0x29 ; @066CF
    dec bp ; @066D2
    jnz loc_66A4 ; @066D3
    pop ds ; @066D5
    ret ; @066D6
sub_66D7:
    push ds ; @066D7
    mov ds,cx ; @066D8
    xchg dx,cx ; @066DA
    mov dx,0x3c4 ; @066DC
    mov ax,0xf02 ; @066DF
    mov [ss:0x8],ax ; @066E2
    out dx,ax ; @066E6
    mov dx,0x3ce ; @066E7
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @066EA
    mov [ss:0xa],ax ; @066EC
    out dx,ax ; @066F0
    mov ax,0xe01 ; @066F1
    mov [ss:0xc],ax ; @066F4
    out dx,ax ; @066F8
    mov ax,0x5 ; @066F9
    mov [ss:0x0],ax ; @066FC
    out dx,ax ; @06700
    mov ax,0x3 ; @06701
    mov [ss:0x2],ax ; @06704
    out dx,ax ; @06708
    mov ax,0xa000 ; @06709
    mov es,ax ; @0670C
    push di ; @0670E
    mov bp,0xa ; @0670F
loc_6712:
    push bp ; @06712
    lodsw ; @06713
    push si ; @06714
    xchg al,ah ; @06715
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06717
    mov ax,[bx] ; @06719
    add bx,byte +0x2 ; @0671B
    xchg al,ah ; @0671E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06720
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06722
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06724
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06726
    jz loc_6736 ; @06728
loc_672A:
    shr si,1 ; @0672A
    rcr al,1 ; @0672C
    shr bp,1 ; @0672E
    rcr ah,1 ; @06730
    dec ch ; @06732
    jnz loc_672A ; @06734
loc_6736:
    push bx ; @06736
    push cx ; @06737
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06738
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @0673A
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0673C
    mov al,0x8 ; @0673E
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06740
    mov [ss:0xe],ax ; @06742
    out dx,ax ; @06746
    cli ; @06747
    mov al,[es:di] ; @06748
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0674B
    stosb ; @0674D
    sti ; @0674E
    mov al,0x8 ; @0674F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06751
    mov [ss:0xe],ax ; @06753
    out dx,ax ; @06757
    cli ; @06758
    mov al,[es:di] ; @06759
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0675C
    stosb ; @0675E
    sti ; @0675F
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06760
    mov al,0x8 ; @06762
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06764
    mov [ss:0xe],ax ; @06766
    out dx,ax ; @0676A
    cli ; @0676B
    mov al,[es:di] ; @0676C
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @0676F
    stosb ; @06771
    sti ; @06772
    add di,byte +0x29 ; @06773
    pop cx ; @06776
    pop bx ; @06777
    pop si ; @06778
    pop bp ; @06779
    dec bp ; @0677A
    jnz loc_6712 ; @0677B
    pop di ; @0677D
    push di ; @0677E
    mov ax,0x1 ; @0677F
    mov [ss:0xc],ax ; @06782
    out dx,ax ; @06786
    mov ax,0x1003 ; @06787
    mov [ss:0x2],ax ; @0678A
    out dx,ax ; @0678E
    mov ax,0xff08 ; @0678F
    mov [ss:0xe],ax ; @06792
    out dx,ax ; @06796
    mov dl,0xc4 ; @06797
    mov ax,0x202 ; @06799
    mov [ss:0x8],ax ; @0679C
    out dx,ax ; @067A0
    mov bp,0xa ; @067A1
loc_67A4:
    lodsw ; @067A4
    xchg al,ah ; @067A5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @067A7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @067A9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @067AB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @067AD
    jz loc_67B9 ; @067AF
loc_67B1:
    shr bx,1 ; @067B1
    rcr al,1 ; @067B3
    dec ch ; @067B5
    jnz loc_67B1 ; @067B7
loc_67B9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @067B9
    cli ; @067BB
    mov al,[es:di] ; @067BC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @067BF
    stosb ; @067C1
    mov al,[es:di] ; @067C2
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @067C5
    stosb ; @067C7
    mov al,[es:di] ; @067C8
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @067CB
    stosb ; @067CD
    sti ; @067CE
    add di,byte +0x29 ; @067CF
    dec bp ; @067D2
    jnz loc_67A4 ; @067D3
    pop di ; @067D5
    mov dx,0x3c4 ; @067D6
    mov ax,0x402 ; @067D9
    mov [ss:0x8],ax ; @067DC
    out dx,ax ; @067E0
    mov bp,0xa ; @067E1
loc_67E4:
    lodsw ; @067E4
    xchg al,ah ; @067E5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @067E7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @067E9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @067EB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @067ED
    jz loc_67F9 ; @067EF
loc_67F1:
    shr bx,1 ; @067F1
    rcr al,1 ; @067F3
    dec ch ; @067F5
    jnz loc_67F1 ; @067F7
loc_67F9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @067F9
    cli ; @067FB
    mov al,[es:di] ; @067FC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @067FF
    stosb ; @06801
    mov al,[es:di] ; @06802
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06805
    stosb ; @06807
    mov al,[es:di] ; @06808
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0680B
    stosb ; @0680D
    sti ; @0680E
    add di,byte +0x29 ; @0680F
    dec bp ; @06812
    jnz loc_67E4 ; @06813
    pop ds ; @06815
    ret ; @06816
sub_6817:
    push ds ; @06817
    mov ds,cx ; @06818
    xchg dx,cx ; @0681A
    mov dx,0x3c4 ; @0681C
    mov ax,0xf02 ; @0681F
    mov [ss:0x8],ax ; @06822
    out dx,ax ; @06826
    mov dx,0x3ce ; @06827
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0682A
    mov [ss:0xa],ax ; @0682C
    out dx,ax ; @06830
    mov ax,0xe01 ; @06831
    mov [ss:0xc],ax ; @06834
    out dx,ax ; @06838
    mov ax,0x5 ; @06839
    mov [ss:0x0],ax ; @0683C
    out dx,ax ; @06840
    mov ax,0x3 ; @06841
    mov [ss:0x2],ax ; @06844
    out dx,ax ; @06848
    mov ax,0xa000 ; @06849
    mov es,ax ; @0684C
    push di ; @0684E
    mov bp,0xd ; @0684F
loc_6852:
    push bp ; @06852
    lodsw ; @06853
    push si ; @06854
    xchg al,ah ; @06855
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06857
    mov ax,[bx] ; @06859
    add bx,byte +0x2 ; @0685B
    xchg al,ah ; @0685E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06860
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06862
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06864
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06866
    jz loc_6876 ; @06868
loc_686A:
    shr si,1 ; @0686A
    rcr al,1 ; @0686C
    shr bp,1 ; @0686E
    rcr ah,1 ; @06870
    dec ch ; @06872
    jnz loc_686A ; @06874
loc_6876:
    push bx ; @06876
    push cx ; @06877
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06878
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @0687A
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0687C
    mov al,0x8 ; @0687E
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06880
    mov [ss:0xe],ax ; @06882
    out dx,ax ; @06886
    cli ; @06887
    mov al,[es:di] ; @06888
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0688B
    stosb ; @0688D
    sti ; @0688E
    mov al,0x8 ; @0688F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06891
    mov [ss:0xe],ax ; @06893
    out dx,ax ; @06897
    cli ; @06898
    mov al,[es:di] ; @06899
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0689C
    stosb ; @0689E
    sti ; @0689F
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @068A0
    mov al,0x8 ; @068A2
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @068A4
    mov [ss:0xe],ax ; @068A6
    out dx,ax ; @068AA
    cli ; @068AB
    mov al,[es:di] ; @068AC
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @068AF
    stosb ; @068B1
    sti ; @068B2
    add di,byte +0x29 ; @068B3
    pop cx ; @068B6
    pop bx ; @068B7
    pop si ; @068B8
    pop bp ; @068B9
    dec bp ; @068BA
    jnz loc_6852 ; @068BB
    pop di ; @068BD
    push di ; @068BE
    mov ax,0x1 ; @068BF
    mov [ss:0xc],ax ; @068C2
    out dx,ax ; @068C6
    mov ax,0x1003 ; @068C7
    mov [ss:0x2],ax ; @068CA
    out dx,ax ; @068CE
    mov ax,0xff08 ; @068CF
    mov [ss:0xe],ax ; @068D2
    out dx,ax ; @068D6
    mov dl,0xc4 ; @068D7
    mov ax,0x202 ; @068D9
    mov [ss:0x8],ax ; @068DC
    out dx,ax ; @068E0
    mov bp,0xd ; @068E1
loc_68E4:
    lodsw ; @068E4
    xchg al,ah ; @068E5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @068E7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @068E9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @068EB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @068ED
    jz loc_68F9 ; @068EF
loc_68F1:
    shr bx,1 ; @068F1
    rcr al,1 ; @068F3
    dec ch ; @068F5
    jnz loc_68F1 ; @068F7
loc_68F9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @068F9
    cli ; @068FB
    mov al,[es:di] ; @068FC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @068FF
    stosb ; @06901
    mov al,[es:di] ; @06902
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06905
    stosb ; @06907
    mov al,[es:di] ; @06908
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0690B
    stosb ; @0690D
    sti ; @0690E
    add di,byte +0x29 ; @0690F
    dec bp ; @06912
    jnz loc_68E4 ; @06913
    pop di ; @06915
    mov dx,0x3c4 ; @06916
    mov ax,0x402 ; @06919
    mov [ss:0x8],ax ; @0691C
    out dx,ax ; @06920
    mov bp,0xd ; @06921
loc_6924:
    lodsw ; @06924
    xchg al,ah ; @06925
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06927
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06929
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0692B
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @0692D
    jz loc_6939 ; @0692F
loc_6931:
    shr bx,1 ; @06931
    rcr al,1 ; @06933
    dec ch ; @06935
    jnz loc_6931 ; @06937
loc_6939:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06939
    cli ; @0693B
    mov al,[es:di] ; @0693C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @0693F
    stosb ; @06941
    mov al,[es:di] ; @06942
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06945
    stosb ; @06947
    mov al,[es:di] ; @06948
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0694B
    stosb ; @0694D
    sti ; @0694E
    add di,byte +0x29 ; @0694F
    dec bp ; @06952
    jnz loc_6924 ; @06953
    pop ds ; @06955
    ret ; @06956
sub_6957:
    push ds ; @06957
    mov ds,cx ; @06958
    xchg dx,cx ; @0695A
    mov dx,0x3c4 ; @0695C
    mov ax,0xf02 ; @0695F
    mov [ss:0x8],ax ; @06962
    out dx,ax ; @06966
    mov dx,0x3ce ; @06967
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0696A
    mov [ss:0xa],ax ; @0696C
    out dx,ax ; @06970
    mov ax,0xe01 ; @06971
    mov [ss:0xc],ax ; @06974
    out dx,ax ; @06978
    mov ax,0x5 ; @06979
    mov [ss:0x0],ax ; @0697C
    out dx,ax ; @06980
    mov ax,0x3 ; @06981
    mov [ss:0x2],ax ; @06984
    out dx,ax ; @06988
    mov ax,0xa000 ; @06989
    mov es,ax ; @0698C
    push di ; @0698E
    mov bp,0xe ; @0698F
loc_6992:
    push bp ; @06992
    lodsw ; @06993
    push si ; @06994
    xchg al,ah ; @06995
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06997
    mov ax,[bx] ; @06999
    add bx,byte +0x2 ; @0699B
    xchg al,ah ; @0699E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @069A0
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @069A2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @069A4
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @069A6
    jz sub_69B6 ; @069A8
sub_69AA:
    shr si,1 ; @069AA
    rcr al,1 ; @069AC
    shr bp,1 ; @069AE
    rcr ah,1 ; @069B0
    dec ch ; @069B2
    jnz sub_69AA ; @069B4
sub_69B6:
    push bx ; @069B6
    push cx ; @069B7
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @069B8
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @069BA
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @069BC
    mov al,0x8 ; @069BE
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @069C0
    mov [ss:0xe],ax ; @069C2
    out dx,ax ; @069C6
    cli ; @069C7
    mov al,[es:di] ; @069C8
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @069CB
    stosb ; @069CD
    sti ; @069CE
    mov al,0x8 ; @069CF
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @069D1
    mov [ss:0xe],ax ; @069D3
    out dx,ax ; @069D7
    cli ; @069D8
    mov al,[es:di] ; @069D9
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @069DC
    stosb ; @069DE
    sti ; @069DF
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @069E0
    mov al,0x8 ; @069E2
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @069E4
    mov [ss:0xe],ax ; @069E6
    out dx,ax ; @069EA
    cli ; @069EB
    mov al,[es:di] ; @069EC
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @069EF
    stosb ; @069F1
    sti ; @069F2
    add di,byte +0x29 ; @069F3
    pop cx ; @069F6
    pop bx ; @069F7
    pop si ; @069F8
    pop bp ; @069F9
    dec bp ; @069FA
    jnz loc_6992 ; @069FB
sub_69FD:
    pop di ; @069FD
    push di ; @069FE
    mov ax,0x1 ; @069FF
    mov [ss:0xc],ax ; @06A02
    out dx,ax ; @06A06
    mov ax,0x1003 ; @06A07
    mov [ss:0x2],ax ; @06A0A
    out dx,ax ; @06A0E
    mov ax,0xff08 ; @06A0F
    mov [ss:0xe],ax ; @06A12
    out dx,ax ; @06A16
    mov dl,0xc4 ; @06A17
    mov ax,0x202 ; @06A19
    mov [ss:0x8],ax ; @06A1C
    out dx,ax ; @06A20
    mov bp,0xe ; @06A21
loc_6A24:
    lodsw ; @06A24
    xchg al,ah ; @06A25
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06A27
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06A29
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06A2B
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06A2D
    jz sub_6A39 ; @06A2F
sub_6A31:
    shr bx,1 ; @06A31
    rcr al,1 ; @06A33
    dec ch ; @06A35
    jnz sub_6A31 ; @06A37
sub_6A39:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06A39
    cli ; @06A3B
    mov al,[es:di] ; @06A3C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06A3F
    stosb ; @06A41
    mov al,[es:di] ; @06A42
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06A45
    stosb ; @06A47
    mov al,[es:di] ; @06A48
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06A4B
    stosb ; @06A4D
    sti ; @06A4E
    add di,byte +0x29 ; @06A4F
    dec bp ; @06A52
    jnz loc_6A24 ; @06A53
sub_6A55:
    pop di ; @06A55
    mov dx,0x3c4 ; @06A56
    mov ax,0x402 ; @06A59
    mov [ss:0x8],ax ; @06A5C
    out dx,ax ; @06A60
    mov bp,0xe ; @06A61
loc_6A64:
    lodsw ; @06A64
    xchg al,ah ; @06A65
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06A67
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06A69
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06A6B
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06A6D
    jz sub_6A79 ; @06A6F
sub_6A71:
    shr bx,1 ; @06A71
    rcr al,1 ; @06A73
    dec ch ; @06A75
    jnz sub_6A71 ; @06A77
sub_6A79:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06A79
    cli ; @06A7B
    mov al,[es:di] ; @06A7C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06A7F
    stosb ; @06A81
    mov al,[es:di] ; @06A82
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06A85
    stosb ; @06A87
    mov al,[es:di] ; @06A88
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06A8B
    stosb ; @06A8D
    sti ; @06A8E
    add di,byte +0x29 ; @06A8F
    dec bp ; @06A92
    jnz loc_6A64 ; @06A93
sub_6A95:
    pop ds ; @06A95
    ret ; @06A96
sub_6A97:
    push ds ; @06A97
    mov ds,cx ; @06A98
    xchg dx,cx ; @06A9A
    mov dx,0x3c4 ; @06A9C
    mov ax,0xf02 ; @06A9F
    mov [ss:0x8],ax ; @06AA2
    out dx,ax ; @06AA6
    mov dx,0x3ce ; @06AA7
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06AAA
    mov [ss:0xa],ax ; @06AAC
    out dx,ax ; @06AB0
    mov ax,0xe01 ; @06AB1
    mov [ss:0xc],ax ; @06AB4
    out dx,ax ; @06AB8
    mov ax,0x5 ; @06AB9
    mov [ss:0x0],ax ; @06ABC
    out dx,ax ; @06AC0
    mov ax,0x3 ; @06AC1
    mov [ss:0x2],ax ; @06AC4
    out dx,ax ; @06AC8
    mov ax,0xa000 ; @06AC9
    mov es,ax ; @06ACC
    push di ; @06ACE
    mov ax,0x10 ; @06ACF
loc_6AD2:
    push ax ; @06AD2
    lodsw ; @06AD3
    push si ; @06AD4
    xchg al,ah ; @06AD5
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06AD7
    mov ax,[bx] ; @06AD9
    add bx,byte +0x2 ; @06ADB
    xchg al,ah ; @06ADE
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06AE0
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06AE2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06AE4
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06AE6
    jz loc_6AF6 ; @06AE8
loc_6AEA:
    shr si,1 ; @06AEA
    rcr al,1 ; @06AEC
    shr bp,1 ; @06AEE
    rcr ah,1 ; @06AF0
    dec ch ; @06AF2
    jnz loc_6AEA ; @06AF4
loc_6AF6:
    push bx ; @06AF6
    push cx ; @06AF7
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06AF8
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @06AFA
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06AFC
    mov al,0x8 ; @06AFE
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06B00
    mov [ss:0xe],ax ; @06B02
    out dx,ax ; @06B06
    cli ; @06B07
    mov al,[es:di] ; @06B08
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06B0B
    stosb ; @06B0D
    sti ; @06B0E
    mov al,0x8 ; @06B0F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06B11
    mov [ss:0xe],ax ; @06B13
    out dx,ax ; @06B17
    cli ; @06B18
    mov al,[es:di] ; @06B19
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @06B1C
    stosb ; @06B1E
    sti ; @06B1F
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06B20
    mov al,0x8 ; @06B22
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06B24
    mov [ss:0xe],ax ; @06B26
    out dx,ax ; @06B2A
    cli ; @06B2B
    mov al,[es:di] ; @06B2C
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06B2F
    stosb ; @06B31
    sti ; @06B32
    add di,byte +0x29 ; @06B33
    pop cx ; @06B36
    pop bx ; @06B37
    pop si ; @06B38
    pop ax ; @06B39
    dec ax ; @06B3A
    jnz loc_6AD2 ; @06B3B
    pop di ; @06B3D
    push di ; @06B3E
    mov ax,0x1 ; @06B3F
    mov [ss:0xc],ax ; @06B42
    out dx,ax ; @06B46
    mov ax,0x1003 ; @06B47
    mov [ss:0x2],ax ; @06B4A
    out dx,ax ; @06B4E
    mov ax,0xff08 ; @06B4F
    mov [ss:0xe],ax ; @06B52
    out dx,ax ; @06B56
    mov dl,0xc4 ; @06B57
    mov ax,0x202 ; @06B59
    mov [ss:0x8],ax ; @06B5C
    out dx,ax ; @06B60
    mov ax,0x10 ; @06B61
loc_6B64:
    push ax ; @06B64
    lodsw ; @06B65
    xchg al,ah ; @06B66
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06B68
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06B6A
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06B6C
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06B6E
    jz loc_6B7A ; @06B70
loc_6B72:
    shr bx,1 ; @06B72
    rcr al,1 ; @06B74
    dec ch ; @06B76
    jnz loc_6B72 ; @06B78
loc_6B7A:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06B7A
    cli ; @06B7C
    mov al,[es:di] ; @06B7D
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06B80
    stosb ; @06B82
    mov al,[es:di] ; @06B83
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06B86
    stosb ; @06B88
    mov al,[es:di] ; @06B89
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06B8C
    stosb ; @06B8E
    sti ; @06B8F
    add di,byte +0x29 ; @06B90
    pop ax ; @06B93
    dec ax ; @06B94
    jnz loc_6B64 ; @06B95
    pop di ; @06B97
    mov dx,0x3c4 ; @06B98
    mov ax,0x402 ; @06B9B
    mov [ss:0x8],ax ; @06B9E
    out dx,ax ; @06BA2
    mov ax,0x10 ; @06BA3
loc_6BA6:
    push ax ; @06BA6
    lodsw ; @06BA7
    xchg al,ah ; @06BA8
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06BAA
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06BAC
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06BAE
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06BB0
    jz loc_6BBC ; @06BB2
loc_6BB4:
    shr bx,1 ; @06BB4
    rcr al,1 ; @06BB6
    dec ch ; @06BB8
    jnz loc_6BB4 ; @06BBA
loc_6BBC:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06BBC
    cli ; @06BBE
    mov al,[es:di] ; @06BBF
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06BC2
    stosb ; @06BC4
    mov al,[es:di] ; @06BC5
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06BC8
    stosb ; @06BCA
    mov al,[es:di] ; @06BCB
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06BCE
    stosb ; @06BD0
    sti ; @06BD1
    add di,byte +0x29 ; @06BD2
    pop ax ; @06BD5
    dec ax ; @06BD6
    jnz loc_6BA6 ; @06BD7
    pop ds ; @06BD9
    ret ; @06BDA
sub_6BDB:
    push ds ; @06BDB
    mov dx,0x3c4 ; @06BDC
    mov ax,0xf02 ; @06BDF
    out dx,ax ; @06BE2
    mov [ss:0x8],ax ; @06BE3
    mov dx,0x3ce ; @06BE7
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06BEA
    out dx,ax ; @06BEC
    mov [ss:0xa],ax ; @06BED
    mov ax,0xe01 ; @06BF1
    out dx,ax ; @06BF4
    mov [ss:0xc],ax ; @06BF5
    mov ax,0x5 ; @06BF9
    out dx,ax ; @06BFC
    mov [ss:0x0],ax ; @06BFD
    mov ax,0x3 ; @06C01
    out dx,ax ; @06C04
    mov [ss:0x2],ax ; @06C05
    mov ds,cx ; @06C09
    mov cx,0xa000 ; @06C0B
    mov es,cx ; @06C0E
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @06C10
    mov cx,0x20 ; @06C12
loc_6C15:
    push cx ; @06C15
    mov cx,[bx] ; @06C16
    inc bx ; @06C18
    inc bx ; @06C19
    mov al,0x8 ; @06C1A
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06C1C
    mov [ss:0xe],ax ; @06C1E
    out dx,ax ; @06C22
    cli ; @06C23
    mov al,[es:di] ; @06C24
    lodsw ; @06C27
    stosb ; @06C28
    sti ; @06C29
    xchg ch,ah ; @06C2A
    mov al,0x8 ; @06C2C
    mov [ss:0xe],ax ; @06C2E
    out dx,ax ; @06C32
    cli ; @06C33
    mov al,[es:di] ; @06C34
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06C37
    stosb ; @06C39
    sti ; @06C3A
    mov cx,[bx] ; @06C3B
    inc bx ; @06C3D
    inc bx ; @06C3E
    mov al,0x8 ; @06C3F
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06C41
    mov [ss:0xe],ax ; @06C43
    out dx,ax ; @06C47
    cli ; @06C48
    mov al,[es:di] ; @06C49
    lodsw ; @06C4C
    stosb ; @06C4D
    sti ; @06C4E
    xchg ch,ah ; @06C4F
    mov al,0x8 ; @06C51
    mov [ss:0xe],ax ; @06C53
    out dx,ax ; @06C57
    cli ; @06C58
    mov al,[es:di] ; @06C59
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06C5C
    stosb ; @06C5E
    sti ; @06C5F
    mov cl,[bx] ; @06C60
    inc bx ; @06C62
    mov al,0x8 ; @06C63
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06C65
    mov [ss:0xe],ax ; @06C67
    out dx,ax ; @06C6B
    cli ; @06C6C
    mov al,[es:di] ; @06C6D
    lodsb ; @06C70
    stosb ; @06C71
    sti ; @06C72
    add di,byte +0x27 ; @06C73
    pop cx ; @06C76
    dec cx ; @06C77
    jz sub_6C7C ; @06C78
sub_6C7A:
    jmp short loc_6C15 ; @06C7A
sub_6C7C:
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @06C7C
    mov ax,0x1 ; @06C7E
    mov [ss:0xc],ax ; @06C81
    out dx,ax ; @06C85
    mov ax,0x1003 ; @06C86
    mov [ss:0x2],ax ; @06C89
    out dx,ax ; @06C8D
    mov ax,0xff08 ; @06C8E
    mov [ss:0xe],ax ; @06C91
    out dx,ax ; @06C95
    mov dl,0xc4 ; @06C96
    mov ax,0x202 ; @06C98
    mov [ss:0x8],ax ; @06C9B
    out dx,ax ; @06C9F
    mov cx,0x20 ; @06CA0
loc_6CA3:
    push cx ; @06CA3
    cli ; @06CA4
    mov al,[es:di] ; @06CA5
    lodsw ; @06CA8
    stosb ; @06CA9
    mov al,[es:di] ; @06CAA
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CAD
    stosb ; @06CAF
    mov al,[es:di] ; @06CB0
    lodsw ; @06CB3
    stosb ; @06CB4
    mov al,[es:di] ; @06CB5
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CB8
    stosb ; @06CBA
    mov al,[es:di] ; @06CBB
    lodsb ; @06CBE
    stosb ; @06CBF
    sti ; @06CC0
    add di,byte +0x27 ; @06CC1
    pop cx ; @06CC4
    loop loc_6CA3 ; @06CC5
sub_6CC7:
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @06CC7
    mov dl,0xc4 ; @06CC9
    mov ax,0x402 ; @06CCB
    mov [ss:0x8],ax ; @06CCE
    out dx,ax ; @06CD2
    mov cx,0x20 ; @06CD3
loc_6CD6:
    push cx ; @06CD6
    cli ; @06CD7
    mov al,[es:di] ; @06CD8
    lodsw ; @06CDB
    stosb ; @06CDC
    mov al,[es:di] ; @06CDD
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CE0
    stosb ; @06CE2
    mov al,[es:di] ; @06CE3
    lodsw ; @06CE6
    stosb ; @06CE7
    mov al,[es:di] ; @06CE8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CEB
    stosb ; @06CED
    mov al,[es:di] ; @06CEE
    lodsb ; @06CF1
    stosb ; @06CF2
    sti ; @06CF3
    add di,byte +0x27 ; @06CF4
    pop cx ; @06CF7
    loop loc_6CD6 ; @06CF8
sub_6CFA:
    pop ds ; @06CFA
    ret ; @06CFB
sub_6CFC:
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
    ret ; @06E82
sub_6E83:
    mov al,[si+0x28] ; @06E83
    sub al,0x1 ; @06E86
    mov bl,0xa0 ; @06E88
    mul bl ; @06E8A
    lea bx,[0x2788] ; @06E8C
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @06E90
    mov dx,0x3c4 ; @06E92
    mov ax,0xf02 ; @06E95
    mov [ss:0x8],ax ; @06E98
    out dx,ax ; @06E9C
    mov dx,0x3ce ; @06E9D
    mov ax,0xf01 ; @06EA0
    mov [ss:0xc],ax ; @06EA3
    out dx,ax ; @06EA7
    mov ax,0x5 ; @06EA8
    mov [ss:0x0],ax ; @06EAB
    out dx,ax ; @06EAF
    mov ax,0x3 ; @06EB0
    mov [ss:0x2],ax ; @06EB3
    out dx,ax ; @06EB7
    mov ax,0xa000 ; @06EB8
    mov es,ax ; @06EBB
    mov bp,[si] ; @06EBD
    sub bp,[0x0] ; @06EBF
    add bp,byte +0x10 ; @06EC3
    mov dx,[si+0x2] ; @06EC6
    sub dx,byte +0x10 ; @06EC9
    mov cl,[0x4d] ; @06ECC
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @06ED0
loc_6ED2:
    mov ax,[bx] ; @06ED2
    add bx,byte +0x2 ; @06ED4
    cmp al,0x80 ; @06ED7
    jnz loc_6EDE ; @06ED9
    jmp loc_6F74 ; @06EDB
loc_6EDE:
    push bp ; @06EDE
    push dx ; @06EDF
    push bx ; @06EE0
    push ax ; @06EE1
    cbw ; @06EE2
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @06EE3
    pop ax ; @06EE5
    jns loc_6EEB ; @06EE6
    jmp loc_6F71 ; @06EE8
loc_6EEB:
    xchg al,ah ; @06EEB
    cbw ; @06EED
    db 0x03,0xd0 ; ENCODED: add dx,ax (NASM chooses a different encoding) ; @06EEE
    js loc_6F71 ; @06EF0
    cmp bp,0x150 ; @06EF2
    jnl loc_6F71 ; @06EF6
    cmp dx,0xa0 ; @06EF8
    jnl loc_6F71 ; @06EFC
    push dx ; @06EFE
    push bp ; @06EFF
    push si ; @06F00
    mov si,[0x26] ; @06F01
    inc si ; @06F05
    sub bp,byte +0x10 ; @06F06
    jns loc_6F0D ; @06F09
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @06F0B
loc_6F0D:
    shr bp,1 ; @06F0D
    shr bp,1 ; @06F0F
    shr bp,1 ; @06F11
    db 0x03,0xf5 ; ENCODED: add si,bp (NASM chooses a different encoding) ; @06F13
    and dx,byte -0x8 ; @06F15
    db 0x03,0xf2 ; ENCODED: add si,dx (NASM chooses a different encoding) ; @06F18
    shl dx,1 ; @06F1A
    shl dx,1 ; @06F1C
    db 0x03,0xf2 ; ENCODED: add si,dx (NASM chooses a different encoding) ; @06F1E
    mov byte [ss:si],0x1 ; @06F20
    pop si ; @06F24
    pop bp ; @06F25
    pop dx ; @06F26
    mov ax,0x2c ; @06F27
    mul dx ; @06F2A
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @06F2C
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @06F2E
    shr bp,1 ; @06F30
    shr bp,1 ; @06F32
    shr bp,1 ; @06F34
    db 0x03,0xfd ; ENCODED: add di,bp (NASM chooses a different encoding) ; @06F36
    add di,[0x1f76] ; @06F38
    add di,[0x1f7a] ; @06F3C
    and ax,0x7 ; @06F40
    lea bx,[0x547c] ; @06F43
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @06F47
    mov ah,[bx] ; @06F49
    mov al,0x8 ; @06F4B
    mov [ss:0xe],ax ; @06F4D
    mov dx,0x3ce ; @06F51
    out dx,ax ; @06F54
    push ax ; @06F55
    db 0x8b,0xd9 ; ENCODED: mov bx,cx (NASM chooses a different encoding) ; @06F56
    and bx,byte +0xf ; @06F58
    add bx,0x2778 ; @06F5B
    mov ah,[bx] ; @06F5F
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06F61
    mov [ss:0xa],ax ; @06F63
    out dx,ax ; @06F67
    pop ax ; @06F68
    cli ; @06F69
    mov al,[es:di] ; @06F6A
    mov [es:di],ah ; @06F6D
    sti ; @06F70
loc_6F71:
    pop bx ; @06F71
    pop dx ; @06F72
    pop bp ; @06F73
loc_6F74:
    dec cx ; @06F74
    jz loc_6F7A ; @06F75
    jmp loc_6ED2 ; @06F77
loc_6F7A:
    ret ; @06F7A
sub_6F7B:
    cli ; @06F7B
    push ds ; @06F7C
    mov dx,0x3c4 ; @06F7D
    mov ax,0xf02 ; @06F80
    mov [ss:0x8],ax ; @06F83
    out dx,ax ; @06F87
    mov dx,0x3ce ; @06F88
    mov ax,0x300 ; @06F8B
    mov [ss:0xa],ax ; @06F8E
    out dx,ax ; @06F92
    mov ax,0xe01 ; @06F93
    mov [ss:0xc],ax ; @06F96
    out dx,ax ; @06F9A
    mov ax,0x5 ; @06F9B
    mov [ss:0x0],ax ; @06F9E
    out dx,ax ; @06FA2
    mov ax,0x3 ; @06FA3
    mov [ss:0x2],ax ; @06FA6
    out dx,ax ; @06FAA
    mov ds,cx ; @06FAB
    mov cx,0xa000 ; @06FAD
    mov es,cx ; @06FB0
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @06FB2
    mov cx,0x8 ; @06FB4
loc_6FB7:
    push cx ; @06FB7
    mov al,[es:di] ; @06FB8
    lodsw ; @06FBB
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @06FBC
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @06FBE
    mov al,0x8 ; @06FC0
    mov [ss:0xe],ax ; @06FC2
    out dx,ax ; @06FC6
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06FC7
    stosb ; @06FC9
    mov al,[es:di] ; @06FCA
    mov al,0x8 ; @06FCD
    db 0x8a,0xe5 ; ENCODED: mov ah,ch (NASM chooses a different encoding) ; @06FCF
    mov [ss:0xe],ax ; @06FD1
    out dx,ax ; @06FD5
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06FD6
    stosb ; @06FD8
    add di,byte +0x2a ; @06FD9
    pop cx ; @06FDC
    loop loc_6FB7 ; @06FDD
    sti ; @06FDF
    pop ds ; @06FE0
    ret ; @06FE1
sub_6FE2:
    mov ax,[di+0x2] ; @06FE2
    cmp ax,0xb0 ; @06FE5
    jl loc_6FED ; @06FE8
    jmp loc_706E ; @06FEA
loc_6FED:
    sub ax,0x20 ; @06FED
    js loc_706E ; @06FF0
    shr ax,1 ; @06FF2
    shr ax,1 ; @06FF4
    shr ax,1 ; @06FF6
    mov dx,0x2c ; @06FF8
    mul dx ; @06FFB
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06FFD
    mov ax,[di] ; @06FFF
    shr ax,1 ; @07001
    shr ax,1 ; @07003
    shr ax,1 ; @07005
    shr ax,1 ; @07007
    push ax ; @07009
    shr ax,1 ; @0700A
    shr ax,1 ; @0700C
    shr ax,1 ; @0700E
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07010
    add si,[0x1f76] ; @07012
    add si,0x2172 ; @07016
    add si,byte +0x2 ; @0701A
    add si,byte +0x2c ; @0701D
    mov dx,0x3c4 ; @07020
    mov ax,0xf02 ; @07023
    mov [ss:0x8],ax ; @07026
    out dx,ax ; @0702A
    mov dx,0x3ce ; @0702B
    mov ax,0x200 ; @0702E
    mov [ss:0xa],ax ; @07031
    out dx,ax ; @07035
    mov ax,0xf01 ; @07036
    mov [ss:0xc],ax ; @07039
    out dx,ax ; @0703D
    mov ax,0x5 ; @0703E
    mov [ss:0x0],ax ; @07041
    out dx,ax ; @07045
    mov ax,0x3 ; @07046
    mov [ss:0x2],ax ; @07049
    out dx,ax ; @0704D
    mov ax,0xa000 ; @0704E
    mov es,ax ; @07051
    pop ax ; @07053
    lea bx,[0x547c] ; @07054
    and ax,0x7 ; @07058
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0705B
    mov ah,[bx] ; @0705D
    mov al,0x8 ; @0705F
    mov [ss:0xe],ax ; @07061
    out dx,ax ; @07065
    cli ; @07066
    mov al,[es:si] ; @07067
    mov [es:si],ah ; @0706A
    sti ; @0706D
loc_706E:
    ret ; @0706E
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
    mov si,0xea8 ; @07083
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
    add di,[0x1f76] ; @0710E
    mov cx,[0x1fe6] ; @07112
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
    mov cx,[0x1fe8] ; @07126
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
    call sub_6F7B ; @07152
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
    add si,[0x1f78] ; @071AD
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
sub_75EF:
    mov di,[0x1f76] ; @075EF
    add di,0x1e42 ; @075F3
    call sub_7602 ; @075F7
    mov di,[0x1f78] ; @075FA
    add di,0x1e42 ; @075FE
sub_7602:
    push ds ; @07602
    mov dx,0x3c4 ; @07603
    mov ax,0xf02 ; @07606
    mov [ss:0x8],ax ; @07609
    out dx,ax ; @0760D
    mov dx,0x3ce ; @0760E
    mov ax,0x105 ; @07611
    mov [ss:0x0],ax ; @07614
    out dx,ax ; @07618
    mov si,0xf91f ; @07619
    mov dx,0xa000 ; @0761C
    mov es,dx ; @0761F
    mov ds,dx ; @07621
    mov cx,0x6e0 ; @07623
    rep movsb ; @07626
    pop ds ; @07628
    ret ; @07629
sub_762A:
    push ds ; @0762A
    push ax ; @0762B
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0762C
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0762E
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07630
    add di,0x212c ; @07632
    add di,[0x1f76] ; @07636
    add di,byte +0x2 ; @0763A
    mov dx,0xa000 ; @0763D
    mov es,dx ; @07640
    mov dx,0x3c4 ; @07642
    mov ax,0xf02 ; @07645
    mov [ss:0x8],ax ; @07648
    out dx,ax ; @0764C
    mov dx,0x3ce ; @0764D
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07650
    mov [ss:0xa],ax ; @07652
    out dx,ax ; @07656
    mov ax,0xc01 ; @07657
    mov [ss:0xc],ax ; @0765A
    out dx,ax ; @0765E
    mov ax,0x5 ; @0765F
    mov [ss:0x0],ax ; @07662
    out dx,ax ; @07666
    mov ax,0x3 ; @07667
    mov [ss:0x2],ax ; @0766A
    out dx,ax ; @0766E
    mov ax,0xf08 ; @0766F
    mov [ss:0xe],ax ; @07672
    out dx,ax ; @07676
    pop ax ; @07677
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @07678
    jz loc_76DB ; @0767A
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0767C
loc_767E:
    inc al ; @0767E
    sub ah,0xa ; @07680
    jnc loc_767E ; @07683
    dec al ; @07685
    add ah,0xa ; @07687
    push ax ; @0768A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0768B
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0768D
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0768F
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07691
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07693
    add ax,0x0 ; @07695
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @07698
    mov ds,[0x1fec] ; @0769A
    push di ; @0769E
    mov cx,0x8 ; @0769F
loc_76A2:
    cli ; @076A2
    mov al,[es:di] ; @076A3
    lodsb ; @076A6
    stosb ; @076A7
    sti ; @076A8
    add di,byte +0x2b ; @076A9
    loop loc_76A2 ; @076AC
    pop di ; @076AE
    inc di ; @076AF
    pop ax ; @076B0
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @076B1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @076B3
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076B5
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076B7
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076B9
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076BB
    add ax,0x8 ; @076BD
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @076C0
    mov ax,0xf008 ; @076C2
    mov [ss:0xe],ax ; @076C5
    out dx,ax ; @076C9
    mov cx,0x8 ; @076CA
loc_76CD:
    cli ; @076CD
    mov al,[es:di] ; @076CE
    lodsb ; @076D1
    stosb ; @076D2
    sti ; @076D3
    add di,byte +0x2b ; @076D4
    loop loc_76CD ; @076D7
    pop ds ; @076D9
    ret ; @076DA
loc_76DB:
    push di ; @076DB
    mov al,0xff ; @076DC
    mov cx,0x8 ; @076DE
loc_76E1:
    cli ; @076E1
    mov ah,[es:di] ; @076E2
    stosb ; @076E5
    sti ; @076E6
    add di,byte +0x2b ; @076E7
    loop loc_76E1 ; @076EA
    pop di ; @076EC
    inc di ; @076ED
    mov ax,0xf008 ; @076EE
    mov [ss:0xe],ax ; @076F1
    out dx,ax ; @076F5
    mov al,0xff ; @076F6
    mov cx,0x8 ; @076F8
loc_76FB:
    cli ; @076FB
    mov ah,[es:di] ; @076FC
    stosb ; @076FF
    sti ; @07700
    add di,byte +0x2b ; @07701
    loop loc_76FB ; @07704
    pop ds ; @07706
    ret ; @07707
sub_7708:
    push ds ; @07708
    push ax ; @07709
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0770A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0770C
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @0770E
    add di,0x1e40 ; @07710
    add di,[0x1f76] ; @07714
    add di,byte +0x2 ; @07718
    mov dx,0xa000 ; @0771B
    mov es,dx ; @0771E
    mov dx,0x3c4 ; @07720
    mov ax,0xf02 ; @07723
    mov [ss:0x8],ax ; @07726
    out dx,ax ; @0772A
    mov dx,0x3ce ; @0772B
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0772E
    mov [ss:0xa],ax ; @07730
    out dx,ax ; @07734
    mov ax,0xe01 ; @07735
    mov [ss:0xc],ax ; @07738
    out dx,ax ; @0773C
    mov ax,0x5 ; @0773D
    mov [ss:0x0],ax ; @07740
    out dx,ax ; @07744
    mov ax,0x3 ; @07745
    mov [ss:0x2],ax ; @07748
    out dx,ax ; @0774C
    mov ax,0xff08 ; @0774D
    mov [ss:0xe],ax ; @07750
    out dx,ax ; @07754
    pop ax ; @07755
    cmp al,0x20 ; @07756
    jnz loc_775D ; @07758
    jmp loc_77FE ; @0775A
loc_775D:
    cmp al,0x25 ; @0775D
    jnz loc_7766 ; @0775F
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @07761
    jmp short loc_77A8 ; @07763
; UNKNOWN: unresolved bytes
    db 0x90 ; @07765
loc_7766:
    cmp al,0x3a ; @07766
    jnz loc_7770 ; @07768
    mov si,0x210 ; @0776A
    jmp short loc_77A8 ; @0776D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0776F
loc_7770:
    cmp al,0x30 ; @07770
    jnl loc_7777 ; @07772
    jmp loc_77FC ; @07774
loc_7777:
    cmp al,0x39 ; @07777
    jg loc_7793 ; @07779
    sub al,0x30 ; @0777B
    mov si,0x30 ; @0777D
loc_7780:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07780
    shl ax,1 ; @07782
    shl ax,1 ; @07784
    shl ax,1 ; @07786
    shl ax,1 ; @07788
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0778A
    shl ax,1 ; @0778C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0778E
    jmp short loc_77A8 ; @07790
; UNKNOWN: unresolved bytes
    db 0x90 ; @07792
loc_7793:
    cmp al,0x41 ; @07793
    jnl loc_779A ; @07795
    jmp short loc_77FC ; @07797
; UNKNOWN: unresolved bytes
    db 0x90 ; @07799
loc_779A:
    cmp al,0x5a ; @0779A
    jng loc_77A1 ; @0779C
    jmp short loc_77FC ; @0779E
; UNKNOWN: unresolved bytes
    db 0x90 ; @077A0
loc_77A1:
    sub al,0x41 ; @077A1
    mov si,0x240 ; @077A3
    jmp short loc_7780 ; @077A6
loc_77A8:
    add si,0xa0 ; @077A8
    mov ds,[0x1fec] ; @077AC
    push di ; @077B0
    mov cx,0x10 ; @077B1
loc_77B4:
    cli ; @077B4
    mov al,[es:di] ; @077B5
    lodsb ; @077B8
    stosb ; @077B9
    sti ; @077BA
    add di,byte +0x2b ; @077BB
    loop loc_77B4 ; @077BE
    pop di ; @077C0
    mov ax,0x1 ; @077C1
    mov [ss:0xc],ax ; @077C4
    out dx,ax ; @077C8
    mov dx,0x3c4 ; @077C9
    mov ax,0x202 ; @077CC
    mov [ss:0x8],ax ; @077CF
    out dx,ax ; @077D3
    push di ; @077D4
    mov cx,0x10 ; @077D5
loc_77D8:
    cli ; @077D8
    mov al,[es:di] ; @077D9
    lodsb ; @077DC
    stosb ; @077DD
    sti ; @077DE
    add di,byte +0x2b ; @077DF
    loop loc_77D8 ; @077E2
    pop di ; @077E4
    mov ax,0x802 ; @077E5
    mov [ss:0x8],ax ; @077E8
    out dx,ax ; @077EC
    mov cx,0x10 ; @077ED
loc_77F0:
    cli ; @077F0
    mov al,[es:di] ; @077F1
    lodsb ; @077F4
    stosb ; @077F5
    sti ; @077F6
    add di,byte +0x2b ; @077F7
    loop loc_77F0 ; @077FA
loc_77FC:
    pop ds ; @077FC
    ret ; @077FD
loc_77FE:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @077FE
    mov cx,0x10 ; @07800
loc_7803:
    cli ; @07803
    stosb ; @07804
    sti ; @07805
    add di,byte +0x2b ; @07806
    loop loc_7803 ; @07809
    pop ds ; @0780B
    ret ; @0780C
sub_780D:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0780D
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0780F
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07811
    add di,0x2100 ; @07813
    add di,[0x1f76] ; @07817
    add di,byte +0x2 ; @0781B
    mov dx,0xa000 ; @0781E
    mov es,dx ; @07821
    mov dx,0x3c4 ; @07823
    mov ax,0xf02 ; @07826
    mov [ss:0x8],ax ; @07829
    out dx,ax ; @0782D
    mov dx,0x3ce ; @0782E
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07831
    mov [ss:0xa],ax ; @07833
    out dx,ax ; @07837
    mov ax,0xc01 ; @07838
    mov [ss:0xc],ax ; @0783B
    out dx,ax ; @0783F
    mov ax,0x5 ; @07840
    mov [ss:0x0],ax ; @07843
    out dx,ax ; @07847
    mov ax,0x3 ; @07848
    mov [ss:0x2],ax ; @0784B
    out dx,ax ; @0784F
    mov ax,0xff08 ; @07850
    mov [ss:0xe],ax ; @07853
    out dx,ax ; @07857
    cli ; @07858
    mov al,0xff ; @07859
    mov ah,[es:di] ; @0785B
    stosb ; @0785E
    mov ah,[es:di] ; @0785F
    stosb ; @07862
    add di,byte +0x2a ; @07863
    mov cx,0x16 ; @07866
loc_7869:
    mov ax,0x8008 ; @07869
    mov [ss:0xe],ax ; @0786C
    out dx,ax ; @07870
    mov ah,[es:di] ; @07871
    mov al,0x80 ; @07874
    stosb ; @07876
    mov ax,0x108 ; @07877
    mov [ss:0xe],ax ; @0787A
    out dx,ax ; @0787E
    mov ah,[es:di] ; @0787F
    mov al,0x1 ; @07882
    stosb ; @07884
    add di,byte +0x2a ; @07885
    loop loc_7869 ; @07888
    mov ax,0xff08 ; @0788A
    mov [ss:0xe],ax ; @0788D
    out dx,ax ; @07891
    mov al,0xff ; @07892
    mov ah,[es:di] ; @07894
    stosb ; @07897
    mov ah,[es:di] ; @07898
    stosb ; @0789B
    sti ; @0789C
    ret ; @0789D
sub_789E:
    cmp al,0xa ; @0789E
    jnl loc_78B3 ; @078A0
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @078A2
    db 0x02,0xdb ; ENCODED: add bl,bl (NASM chooses a different encoding) ; @078A4
    db 0x02,0xd8 ; ENCODED: add bl,al (NASM chooses a different encoding) ; @078A6
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @078A8
    add bx,0x64 ; @078AA
    mov word [bx+0x1],0x0 ; @078AE
loc_78B3:
    push ds ; @078B3
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @078B4
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @078B6
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @078B8
    push di ; @078BA
    add di,0x2100 ; @078BB
    add di,[0x1f76] ; @078BF
    add di,byte +0x2 ; @078C3
    mov dx,0xa000 ; @078C6
    mov es,dx ; @078C9
    mov dx,0x3c4 ; @078CB
    mov ax,0xf02 ; @078CE
    mov [ss:0x8],ax ; @078D1
    out dx,ax ; @078D5
    mov dx,0x3ce ; @078D6
    mov ax,0x105 ; @078D9
    mov [ss:0x0],ax ; @078DC
    out dx,ax ; @078E0
    pop si ; @078E1
    add si,0x2c0 ; @078E2
    add si,0xf91f ; @078E6
    mov dx,0xa000 ; @078EA
    mov es,dx ; @078ED
    mov ds,dx ; @078EF
    mov cx,0x18 ; @078F1
loc_78F4:
    movsb ; @078F4
    movsb ; @078F5
    add di,byte +0x2a ; @078F6
    add si,byte +0x2a ; @078F9
    loop loc_78F4 ; @078FC
    pop ds ; @078FE
    ret ; @078FF
sub_7900:
    mov bp,ds ; @07900
    mov di,[0x1f76] ; @07902
    add di,0x2172 ; @07906
    add di,byte +0x2 ; @0790A
    mov si,0xd320 ; @0790D
    mov dx,0xa000 ; @07910
    mov es,dx ; @07913
    mov ds,dx ; @07915
    mov dx,0x3c4 ; @07917
    mov ax,0xf02 ; @0791A
    mov [ss:0x8],ax ; @0791D
    out dx,ax ; @07921
    mov dx,0x3ce ; @07922
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07925
    mov [ss:0xa],ax ; @07927
    out dx,ax ; @0792B
    mov ax,0xf01 ; @0792C
    mov [ss:0xc],ax ; @0792F
    out dx,ax ; @07933
    mov ax,0x5 ; @07934
    mov [ss:0x0],ax ; @07937
    out dx,ax ; @0793B
    mov ax,0x3 ; @0793C
    mov [ss:0x2],ax ; @0793F
    out dx,ax ; @07943
    mov ax,0xff08 ; @07944
    mov [ss:0xe],ax ; @07947
    out dx,ax ; @0794B
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0794C
    mov cx,0xd ; @0794E
    rep stosb ; @07951
    add di,byte +0x1f ; @07953
    mov ax,0x105 ; @07956
    mov [ss:0x0],ax ; @07959
    out dx,ax ; @0795D
    mov dx,0x13 ; @0795E
loc_7961:
    mov cx,0xd ; @07961
    rep movsb ; @07964
    add di,byte +0x1f ; @07966
    dec dx ; @07969
    jnz loc_7961 ; @0796A
    mov ds,bp ; @0796C
    ret ; @0796E
sub_796F:
    push ds ; @0796F
    lea di,[0x83c1] ; @07970
    mov cx,0xa ; @07974
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07977
    push cs ; @07979
    pop es ; @0797A
    rep stosw ; @0797B
    mov si,[0x56] ; @0797D
    add si,byte +0x10 ; @07981
    cmp si,0xd0 ; @07984
    jl loc_798C ; @07988
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0798A
loc_798C:
    mov [0x56],si ; @0798C
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @07990
    add si,0xd00 ; @07992
    add si,0x4a40 ; @07996
    shr di,1 ; @0799A
    shr di,1 ; @0799C
    shr di,1 ; @0799E
    shr di,1 ; @079A0
    add di,0xd320 ; @079A2
    mov dx,0xa000 ; @079A6
    mov es,dx ; @079A9
    mov dx,0x3c4 ; @079AB
    mov ax,0xf02 ; @079AE
    mov [ss:0x8],ax ; @079B1
    out dx,ax ; @079B5
    mov dx,0x3ce ; @079B6
    mov ax,0x600 ; @079B9
    mov [ss:0xa],ax ; @079BC
    out dx,ax ; @079C0
    mov ax,0x801 ; @079C1
    mov [ss:0xc],ax ; @079C4
    out dx,ax ; @079C8
    mov ax,0x805 ; @079C9
    mov [ss:0x0],ax ; @079CC
    out dx,ax ; @079D0
    mov ax,0x3 ; @079D1
    mov [ss:0x2],ax ; @079D4
    out dx,ax ; @079D8
    mov ax,0x807 ; @079D9
    mov [ss:0x6],ax ; @079DC
    out dx,ax ; @079E0
    mov ax,0x802 ; @079E1
    mov [ss:0x4],ax ; @079E4
    out dx,ax ; @079E8
    mov ax,0xff08 ; @079E9
    mov [ss:0xe],ax ; @079EC
    out dx,ax ; @079F0
    mov cx,0x14 ; @079F1
    lea bx,[0x83c1] ; @079F4
loc_79F8:
    call sub_7A25 ; @079F8
    add si,0x680 ; @079FB
    inc bx ; @079FF
    loop loc_79F8 ; @07A00
    mov dx,0x3ce ; @07A02
    mov ax,0x5 ; @07A05
    mov [ss:0x0],ax ; @07A08
    out dx,ax ; @07A0C
    mov cx,0x13 ; @07A0D
    lea bx,[0x83c1] ; @07A10
loc_7A14:
    mov ah,[cs:bx] ; @07A14
    mov al,[es:di] ; @07A17
    mov [es:di],ah ; @07A1A
    add di,byte +0xd ; @07A1D
    inc bx ; @07A20
    loop loc_7A14 ; @07A21
    pop ds ; @07A23
    ret ; @07A24
sub_7A25:
    push cx ; @07A25
    push si ; @07A26
    mov dl,0x80 ; @07A27
    mov cx,0x8 ; @07A29
loc_7A2C:
    call sub_7A39 ; @07A2C
    add si,byte +0x2 ; @07A2F
    shr dl,1 ; @07A32
    loop loc_7A2C ; @07A34
    pop si ; @07A36
    pop cx ; @07A37
    ret ; @07A38
sub_7A39:
    push cx ; @07A39
    mov ah,[es:si] ; @07A3A
    mov al,[es:si+0x1] ; @07A3D
    mov cx,0x10 ; @07A41
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07A44
loc_7A46:
    shr ax,1 ; @07A46
    jnc loc_7A4C ; @07A48
    inc dh ; @07A4A
loc_7A4C:
    loop loc_7A46 ; @07A4C
    cmp dh,0x8 ; @07A4E
    jg loc_7A55 ; @07A51
    pop cx ; @07A53
    ret ; @07A54
loc_7A55:
    or [cs:bx],dl ; @07A55
    pop cx ; @07A58
    ret ; @07A59
sub_7A5A:
    mov di,[0x0] ; @07A5A
    shr di,1 ; @07A5E
    shr di,1 ; @07A60
    shr di,1 ; @07A62
    shr di,1 ; @07A64
    shr di,1 ; @07A66
    shr di,1 ; @07A68
    shr di,1 ; @07A6A
    add di,0x2172 ; @07A6C
    add di,[0x1f76] ; @07A70
    add di,byte +0x2 ; @07A74
    mov dx,0xa000 ; @07A77
    mov es,dx ; @07A7A
    mov dx,0x3c4 ; @07A7C
    mov ax,0xf02 ; @07A7F
    mov [ss:0x8],ax ; @07A82
    out dx,ax ; @07A86
    mov dx,0x3ce ; @07A87
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07A8A
    mov [ss:0xa],ax ; @07A8C
    out dx,ax ; @07A90
    mov ax,0xc01 ; @07A91
    mov [ss:0xc],ax ; @07A94
    out dx,ax ; @07A98
    mov ax,0x5 ; @07A99
    mov [ss:0x0],ax ; @07A9C
    out dx,ax ; @07AA0
    mov ax,0x3 ; @07AA1
    mov [ss:0x2],ax ; @07AA4
    out dx,ax ; @07AA8
    mov cx,0xffff ; @07AA9
    mov bx,0xff00 ; @07AAC
    mov ax,[0x0] ; @07AAF
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
    mov [ss:0xe],ax ; @07ACC
    out dx,ax ; @07AD0
    cli ; @07AD1
    mov al,[es:di] ; @07AD2
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07AD5
    stosb ; @07AD7
    sti ; @07AD8
    mov al,0x8 ; @07AD9
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07ADB
    mov [ss:0xe],ax ; @07ADD
    out dx,ax ; @07AE1
    cli ; @07AE2
    mov ah,[es:di] ; @07AE3
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07AE6
    stosb ; @07AE8
    sti ; @07AE9
    mov al,0x8 ; @07AEA
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @07AEC
    mov [ss:0xe],ax ; @07AEE
    out dx,ax ; @07AF2
    cli ; @07AF3
    mov ah,[es:di] ; @07AF4
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07AF7
    stosb ; @07AF9
    sti ; @07AFA
    mov al,0x8 ; @07AFB
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @07AFD
    mov [ss:0xe],ax ; @07AFF
    out dx,ax ; @07B03
    cli ; @07B04
    mov ah,[es:di] ; @07B05
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07B08
    stosb ; @07B0A
    sti ; @07B0B
    add di,0x340 ; @07B0C
    mov al,0x8 ; @07B10
    db 0x8a,0xe5 ; ENCODED: mov ah,ch (NASM chooses a different encoding) ; @07B12
    mov [ss:0xe],ax ; @07B14
    out dx,ax ; @07B18
    cli ; @07B19
    mov al,[es:di] ; @07B1A
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07B1D
    stosb ; @07B1F
    sti ; @07B20
    mov al,0x8 ; @07B21
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07B23
    mov [ss:0xe],ax ; @07B25
    out dx,ax ; @07B29
    cli ; @07B2A
    mov ah,[es:di] ; @07B2B
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07B2E
    stosb ; @07B30
    sti ; @07B31
    mov al,0x8 ; @07B32
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @07B34
    mov [ss:0xe],ax ; @07B36
    out dx,ax ; @07B3A
    cli ; @07B3B
    mov ah,[es:di] ; @07B3C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07B3F
    stosb ; @07B41
    sti ; @07B42
    mov al,0x8 ; @07B43
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @07B45
    mov [ss:0xe],ax ; @07B47
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
    mov [ss:0xe],ax ; @07B71
    out dx,ax ; @07B75
    cli ; @07B76
    mov al,[es:di] ; @07B77
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07B7A
    stosb ; @07B7C
    sti ; @07B7D
    mov al,0x8 ; @07B7E
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @07B80
    mov [ss:0xe],ax ; @07B82
    out dx,ax ; @07B86
    cli ; @07B87
    mov al,[es:di] ; @07B88
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07B8B
    stosb ; @07B8D
    sti ; @07B8E
    mov al,0x8 ; @07B8F
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @07B91
    mov [ss:0xe],ax ; @07B93
    out dx,ax ; @07B97
    cli ; @07B98
    mov al,[es:di] ; @07B99
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07B9C
    stosb ; @07B9E
    sti ; @07B9F
    mov al,0x8 ; @07BA0
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @07BA2
    mov [ss:0xe],ax ; @07BA4
    out dx,ax ; @07BA8
    cli ; @07BA9
    mov al,[es:di] ; @07BAA
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07BAD
    stosb ; @07BAF
    sti ; @07BB0
    sub di,byte +0x30 ; @07BB1
    dec bp ; @07BB4
    jnz loc_7B6D ; @07BB5
    ret ; @07BB7
sub_7BB8:
    lea si,[0x17cb] ; @07BB8
    lea di,[0xfeb] ; @07BBC
    mov cx,0x20 ; @07BC0
loc_7BC3:
    mov ah,[di] ; @07BC3
    mov al,[di+0x1] ; @07BC5
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07BC8
    jz loc_7C01 ; @07BCA
    push cx ; @07BCC
    push di ; @07BCD
    push si ; @07BCE
    sub ax,[0x0] ; @07BCF
    add ax,0x10 ; @07BD3
    mov bh,[di+0x2] ; @07BD6
    mov bl,[di+0x3] ; @07BD9
    mov dh,[di+0x6] ; @07BDC
    mov dl,[di+0x7] ; @07BDF
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @07BE2
    and bp,byte -0x2 ; @07BE4
    mov dl,[si+0x4] ; @07BE7
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07BEA
    mov cl,[si+0x5] ; @07BEC
    mov di,[si+0x8] ; @07BEF
    mov si,[si+0x17] ; @07BF2
    db 0x03,0xfe ; ENCODED: add di,si (NASM chooses a different encoding) ; @07BF5
    mov ch,0x4 ; @07BF7
    call 0x0:0x8822 ; @07BF9
    pop si ; @07BFE
    pop di ; @07BFF
    pop cx ; @07C00
loc_7C01:
    add di,byte +0x8 ; @07C01
    add si,byte +0x1c ; @07C04
    loop loc_7BC3 ; @07C07
    ret ; @07C09
loc_7C0A:
    lea si,[0x17cb] ; @07C0A
    lea di,[0xfeb] ; @07C0E
    mov cx,0x20 ; @07C12
loc_7C15:
    mov ah,[di] ; @07C15
    mov al,[di+0x1] ; @07C17
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07C1A
    jz loc_7C5C ; @07C1C
    mov dl,[di+0x5] ; @07C1E
    cmp dl,0x1 ; @07C21
    jnz loc_7C2D ; @07C24
    cmp byte [0x55],0xff ; @07C26
    jnz loc_7C5E ; @07C2B
loc_7C2D:
    mov bx,[si] ; @07C2D
    test bx,0x2 ; @07C2F
    jz loc_7C5C ; @07C33
    mov al,[si+0x2] ; @07C35
    mov ah,[si+0x3] ; @07C38
    inc al ; @07C3B
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @07C3D
    jnz loc_7C4C ; @07C3F
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @07C41
    test bx,0x1 ; @07C43
    jz loc_7C4C ; @07C47
    and bx,byte -0x3 ; @07C49
loc_7C4C:
    mov [si+0x2],al ; @07C4C
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07C4F
    mov bp,[si+0x6] ; @07C51
    mul bp ; @07C54
    add ax,[si+0x15] ; @07C56
    mov [si+0x17],ax ; @07C59
loc_7C5C:
    mov [si],bx ; @07C5C
loc_7C5E:
    add di,byte +0x8 ; @07C5E
    add si,byte +0x1c ; @07C61
    loop loc_7C15 ; @07C64
    ret ; @07C66
sub_7C67:
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
    add ax,0x1d0b ; @07C9F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @07CA2
    mov dl,[bx] ; @07CA4
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07CA6
    mov cl,[bx+0x1] ; @07CA8
    mov si,[bx+0x2] ; @07CAB
    mov di,[bx+0x4] ; @07CAE
    pop ax ; @07CB1
    pop bx ; @07CB2
    mov ch,0x4 ; @07CB3
    call 0x0:0x8822 ; @07CB5
    pop si ; @07CBA
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
    mov [0x1fe4],ax ; @07CE9
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @07CEC
    mov ax,0x30 ; @07CEE
    mov bx,0x14e ; @07CF1
    mov dx,0x230 ; @07CF4
    mov cx,0x410 ; @07CF7
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @07CFA
    call 0x0:0x8822 ; @07CFC
    mov ax,[0x1fee] ; @07D01
    add ax,0x1000 ; @07D04
    mov [0x1fe4],ax ; @07D07
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
    mov ax,[0x1fee] ; @07D97
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
    mov ax,[0x1fee] ; @07DD9
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
loc_7E76:
    mov ax,[0x1fee] ; @07E76
    mov [0x1fe4],ax ; @07E79
    mov cx,0x4 ; @07E7C
loc_7E7F:
    push bx ; @07E7F
    push cx ; @07E80
    push bx ; @07E81
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07E82
    mov bp,0xc ; @07E84
    mov dx,0x140 ; @07E87
    mov cx,0x268 ; @07E8A
    mov si,0x0 ; @07E8D
    call 0x0:0x8822 ; @07E90
    mov ax,0x140 ; @07E95
    pop bx ; @07E98
    mov bp,0xc ; @07E99
    mov dx,0x140 ; @07E9C
    mov cx,0x268 ; @07E9F
    mov si,0x0 ; @07EA2
    call 0x0:0x8822 ; @07EA5
    pop cx ; @07EAA
    pop bx ; @07EAB
    add bx,byte +0x68 ; @07EAC
    loop loc_7E7F ; @07EAF
    ret ; @07EB1
sub_7EB2:
    push ds ; @07EB2
    mov di,[0x1f76] ; @07EB3
    add di,[0x1f7a] ; @07EB7
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
    mov di,[0x26] ; @08115
    mov al,[es:di] ; @08119
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0811C
    jz loc_8123 ; @0811E
    jmp short loc_819D ; @08120
; UNKNOWN: unresolved bytes
    db 0x90 ; @08122
loc_8123:
    push ds ; @08123
    inc di ; @08124
    mov bp,[0x1f76] ; @08125
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
    mov di,[0x26] ; @08153
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
    mov di,[0x1f76] ; @081A3
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
    mov word [0x1f76],0x0 ; @081CC
    mov word [0x1f78],0x2520 ; @081D2
    mov word [0x1f7a],0x2c0 ; @081D8
    mov word [0x26],0x42b2 ; @081DE
    mov word [0x28],0x45d3 ; @081E4
    mov bx,[0x26] ; @081EA
    mov byte [ss:bx],0xff ; @081EE
    mov bx,[0x28] ; @081F2
    mov byte [ss:bx],0xff ; @081F6
    mov byte [0x2a],0xff ; @081FA
    call sub_80FD ; @081FF
    mov ax,[0x1f78] ; @08202
    xchg [0x1f76],ax ; @08205
    mov [0x1f78],ax ; @08209
    mov ax,[0x28] ; @0820C
    xchg [0x26],ax ; @0820F
    mov [0x28],ax ; @08213
    call sub_39CE ; @08216
    call sub_80FD ; @08219
    mov ax,0x160 ; @0821C
    mov bx,0xa0 ; @0821F
    mov dx,[0x1f76] ; @08222
    call 0x0:0x8808 ; @08226
    mov word [0x8],0xd2c0 ; @0822B
    mov word [0xa],0xd2f0 ; @08231
    ret ; @08237
