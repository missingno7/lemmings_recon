; Maintained64D9..66D6 shifted sprite siblings; separate12/13-row entries.
times -(($-$$) != 0x64d9) db 0 ; module start assertion
; CONTRACT: source DS=incoming CX; incoming DL becomes unchecked CL shift.
; Per-bit SHR/RCR loops retain all256 counts. First-pass BP/SI/BX/CX and
; phase DI saves are live SS words; no cached row/count/cursor restores.
; Masked data/mask words shift into three bytes, then OR plane02 follows (GC3=10h).
; DF strings, literal +29h pitch, ordered VGA phases and POP DS/RET remain.
DrawEntityShiftedSprite12:
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
EntityShiftedSprite12Return:
    ret ; @065D7
DrawEntityShiftedSprite13:
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
EntityShiftedSprite13Return:
    ret ; @066D6
times -(($-$$) != 0x66d7) db 0 ; module end assertion
