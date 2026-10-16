; Mixed ownership57D1..5D65; UNKNOWN bytes unchanged.
times -(($-$$) != 0x57d1) db 0 ; module start assertion
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
    mov es,[GraphicsResourceSegment-GameDataImage] ; @058D6
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
    mov es,[GraphicsResourceSegment-GameDataImage] ; @058F1
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @058F5
    call DecodeDatPreservingSegment ; @058F9
    pop ds ; @058FC
    push bx ; @058FD
    call GenerateGraphicsMaskBanks ; @058FE
    pop bx ; @05901
    push ds ; @05902
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05903
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05905
    mov es,[GraphicsResourceSegment-GameDataImage] ; @05907
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @0590B
    call DecodeDatPreservingSegment ; @0590F
    pop ds ; @05912
    push bx ; @05913
    push ds ; @05914
    mov di,0xf91f ; @05915
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05918
    mov cx,0x28 ; @0591A
    mov ax,0x2c ; @0591D
    mov bx,0x428 ; @05920
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05923
    call sub_57D1 ; @05927
    pop ds ; @0592A
    push ds ; @0592B
    mov si,0x1900 ; @0592C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0592F
    mov es,[StatusGlyphBufferSegment-GameDataImage] ; @05931
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05935
    mov cx,0x3e0 ; @05939
    rep movsw ; @0593C
    pop ds ; @0593E
    pop bx ; @0593F
    push ds ; @05940
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05941
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05943
    mov es,[UiGraphicsBufferSegment-GameDataImage] ; @05945
    mov ds,[UiGraphicsBufferSegment-GameDataImage] ; @05949
    call DecodeDatPreservingSegment ; @0594D
sub_5950:
    pop ds ; @05950
    push ds ; @05951
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @05952
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
    mov es,[GraphicsResourceSegment-GameDataImage] ; @0597E
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05982
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
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @0599D
    call sub_57D1 ; @059A1
    pop ds ; @059A4
    push ds ; @059A5
    mov di,0xa0 ; @059A6
    mov si,0x1900 ; @059A9
    mov es,[StatusGlyphBufferSegment-GameDataImage] ; @059AC
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @059B0
    mov cx,0x720 ; @059B4
    rep movsb ; @059B7
    pop ds ; @059B9
loc_59BA:
    ret ; @059BA
sub_59BB:
    push ds ; @059BB
    mov es,[EntitySpriteBufferSegment-GameDataImage] ; @059BC
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @059C0
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
; Producer for the live GeneratedGraphicsBufferSegment; 58FE calls after decode.
; With DF=0 and intact disjoint RAM/save frames: eight10-row*3-byte banks
; start0000, four13-row banks0780, one22-row bank0C60, ten8-row*2-byte banks0E70.
; The8shiftpasses yield outputend1370 and sourceend0184. These are producer
; coordinates, not allocation bounds. 5D66 STOSW changes output direction withDF.
; Callers/unchecked consumers/initialization obligations: generated-graphics.md.
; PUSH DS precedes the two selector reads. Near calls/returns and the outer
; CX/DS saves are live SS memory; changed child return targets stop C handoff.
; DS restores from its actual save, ES stays selected, SS/BP unchanged.
sub_5AC1:
GenerateGraphicsMaskBanks:
    push ds ; @05AC1
    mov es,[GeneratedGraphicsBufferSegment-GameDataImage] ; @05AC2
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05AC6
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05ACA
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05ACC
    mov cx,0x8 ; @05ACE
loc_5AD1:
    push cx ; @05AD1
    mov cx,0xa ; @05AD2
    mov bl,0x1 ; @05AD5
    call GenerateWordMaskShifts ; @05AD7
    add si,byte +0x14 ; @05ADA
    pop cx ; @05ADD
    loop loc_5AD1 ; @05ADE
    mov cx,0x4 ; @05AE0
loc_5AE3:
    push cx ; @05AE3
    mov cx,0xd ; @05AE4
    mov bl,0x1 ; @05AE7
    call GenerateWordMaskShifts ; @05AE9
    add si,byte +0x1a ; @05AEC
    pop cx ; @05AEF
    loop loc_5AE3 ; @05AF0
    mov cx,0x16 ; @05AF2
    mov bl,0x1 ; @05AF5
    call GenerateWordMaskShifts ; @05AF7
    add si,byte +0x2c ; @05AFA
    mov cx,0xa ; @05AFD
loc_5B00:
    push cx ; @05B00
    mov cx,0x8 ; @05B01
    mov bl,0x1 ; @05B04
    call GenerateByteMaskShifts ; @05B06
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
    call GenerateWordMaskShifts ; @05CCF
    mov si,0x531c ; @05CD2
    mov di,0x480 ; @05CD5
    mov bl,0x3 ; @05CD8
    mov cx,0x10 ; @05CDA
; DS:SI source, ES:DI output, BL repetitions, CX rows; DH starts at zero.
; LODSW follows DF; three stores use INC DI regardless of DF. All saves and
; restored loop controls are live SS memory: aliases can change counts/returns.
; AX/BX/CX/DX/SI/DI/flags are outputs; DS/ES/SS/BP unchanged. No loop caps.
sub_5CDD:
GenerateWordMaskShifts:
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
