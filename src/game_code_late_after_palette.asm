; Mixed ownership after palette arithmetic, original5726..796E.
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
    add ax,[DrawingDirtyCellMapOffset-GameDataImage] ; @05753
    mov bp,[DrawingDirtyCellMapOffset-GameDataImage] ; @05757
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
    call sub_5AC1 ; @058FE
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
    mov es,[0x1fec] ; @05931
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
    mov es,[0x1fec] ; @059AC
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @059B0
    mov cx,0x720 ; @059B4
    rep movsb ; @059B7
    pop ds ; @059B9
loc_59BA:
    ret ; @059BA
sub_59BB:
    push ds ; @059BB
    mov es,[0x1fe6] ; @059BC
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
sub_5AC1:
    push ds ; @05AC1
    mov es,[0x1fe8] ; @05AC2
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05AC6
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
; 5DC6..5DF7: prepare a record pixel sample; no VGA reads occur here.
; DS:SI+2 gives wrapped Y-10h. Clamp when the subtraction result is negative,
; rather than comparing signed Y. Low MUL(D0h,row) supplies DI and residual AL.
; PUSH DX precedes the later DS:SI X read; SS aliases can change X or the mask.
; ES=A000h; DI=low_product+(X>>3)+4A40h; CX=X>>3 (logical shifts).
; BX=PixelBitMasks+(X&7); AH is the live DS table byte; AL keeps low product.
; DX is popped live, SI/BP/DS/SS unchanged. Final flags: ADD BX,547Ch at5DF1.
; RET consumes the live near word. RAM core contract: entity-pixel.md.
PrepareEntityPixelSample:
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
    add bx,PixelBitMasks-GameDataImage ; @05DF1
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
    call PrepareEntityPixelSample ; @05F54
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
    add bx,PixelBitMasks-GameDataImage ; @06167
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
    mov si,[DrawingDirtyCellMapOffset-GameDataImage] ; @06F01
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
    add di,[DrawingOrigin-GameDataImage] ; @06F38
    add di,[DrawingPageByteOffset-GameDataImage] ; @06F3C
    and ax,0x7 ; @06F40
    lea bx,[PixelBitMasks-GameDataImage] ; @06F43
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
    add si,[DrawingOrigin-GameDataImage] ; @07012
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
    lea bx,[PixelBitMasks-GameDataImage] ; @07054
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
    add di,[DrawingOrigin-GameDataImage] ; @0710E
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
sub_75EF:
    mov di,[DrawingOrigin-GameDataImage] ; @075EF
    add di,0x1e42 ; @075F3
    call sub_7602 ; @075F7
    mov di,[AlternateDrawingOrigin-GameDataImage] ; @075FA
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
    add di,[DrawingOrigin-GameDataImage] ; @07636
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
    add di,[DrawingOrigin-GameDataImage] ; @07714
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
    add di,[DrawingOrigin-GameDataImage] ; @07817
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
    add di,[DrawingOrigin-GameDataImage] ; @078BF
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
    mov di,[DrawingOrigin-GameDataImage] ; @07902
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
