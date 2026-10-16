; Mixed resource ownership 57D1..5B10; UNKNOWN bytes unchanged.
times -(($-$$) != 0x57d1) db 0 ; module start assertion
sub_57D1:
CopyResourcePlanesToVga:
; DS:SI bytes -> ES=A000. BH planes (zero means 256), CX rows (zero wraps
; through FFFF), BL bytes per REP (zero copies none), AX literal row pitch.
; All row/plane/AX saves reread live SS words; mirrors precede OUT. REP follows
; live DF, SI flows across planes, DI/CX restore per plane. DS/SS/BP unchanged.
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
VgaPlaneCopyReturn:
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
    mov ds,[GeneratedWordPatternBufferSegment-GameDataImage] ; @05862
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
    call GenerateEntitySpriteBanks ; @058E5
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
; CONTRACT: PUSH DS occurs before ordered reads of incoming DS:1FE6 (ES)
; and DS:1FE4 (source DS). SI=DI=0. Fifteen immediate groups push actual CX,
; call a native-understood leaf through its actual near frame, pop live CX,
; advance SI by the literal source stride, then LOOP without changing FLAGS.
; Returned ES/DI/DS/SS/SP/FLAGS and saved counts remain authoritative. Child
; RET aliases stop native composition at the changed CS:IP before parent POP.
; With intact saves, DF clear and disjoint memory, the 336 grouped calls read
; 50F0h source bytes and emit 180B8h bytes; the final 5C06 call adds 0180h
; source bytes and 1400h output bytes. These are coordinates, not bounds.
; Final ADD SI,0180 precedes actual POP DS and the caller RET at 5AC0.
; The core stops before that RET. No converted sprite data or cached saves.
GenerateEntitySpriteBanks:
    push ds ; @059BB
    mov es,[EntitySpriteBufferSegment-GameDataImage] ; @059BC
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @059C0
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @059C4
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @059C6
    mov cx,0x12 ; @059C8
loc_59CB:
    push cx ; @059CB
    mov dx,0x20a ; @059CC
    call GenerateThreeByteSpriteBanks ; @059CF
    pop cx ; @059D2
    add si,byte +0x28 ; @059D3
    loop loc_59CB ; @059D6
    mov cx,0x10 ; @059D8
loc_59DB:
    push cx ; @059DB
    mov dx,0x30e ; @059DC
    call CopySpritePlanesAndAppendMask ; @059DF
    pop cx ; @059E2
    add si,byte +0x54 ; @059E3
    loop loc_59DB ; @059E6
    mov cx,0x10 ; @059E8
loc_59EB:
    push cx ; @059EB
    mov dx,0x20c ; @059EC
    call CopySpritePlanesAndAppendMask ; @059EF
    pop cx ; @059F2
    add si,byte +0x30 ; @059F3
    loop loc_59EB ; @059F6
    mov cx,0x10 ; @059F8
loc_59FB:
    push cx ; @059FB
    mov dx,0x20a ; @059FC
    call GenerateThreeByteSpriteBanks ; @059FF
    pop cx ; @05A02
    add si,byte +0x28 ; @05A03
    loop loc_59FB ; @05A06
    mov cx,0x10 ; @05A08
loc_5A0B:
    push cx ; @05A0B
    mov dx,0x20c ; @05A0C
    call CopySpritePlanesAndAppendMask ; @05A0F
    pop cx ; @05A12
    add si,byte +0x30 ; @05A13
    loop loc_5A0B ; @05A16
    mov cx,0x20 ; @05A18
loc_5A1B:
    push cx ; @05A1B
    mov dx,0x30d ; @05A1C
    call CopySpritePlanesAndAppendMask ; @05A1F
    pop cx ; @05A22
    add si,byte +0x4e ; @05A23
    loop loc_5A1B ; @05A26
    mov cx,0x40 ; @05A28
loc_5A2B:
    push cx ; @05A2B
    mov dx,0x30a ; @05A2C
    call CopySpritePlanesAndAppendMask ; @05A2F
    pop cx ; @05A32
    add si,byte +0x3c ; @05A33
    loop loc_5A2B ; @05A36
    mov cx,0x30 ; @05A38
loc_5A3B:
    push cx ; @05A3B
    mov dx,0x30d ; @05A3C
    call CopySpritePlanesAndAppendMask ; @05A3F
    pop cx ; @05A42
    add si,byte +0x4e ; @05A43
    loop loc_5A3B ; @05A46
    mov cx,0x8 ; @05A48
loc_5A4B:
    push cx ; @05A4B
    mov dx,0x20a ; @05A4C
    call GenerateThreeByteSpriteBanks ; @05A4F
    pop cx ; @05A52
    add si,byte +0x28 ; @05A53
    loop loc_5A4B ; @05A56
    mov cx,0x10 ; @05A58
loc_5A5B:
    push cx ; @05A5B
    mov dx,0x310 ; @05A5C
    call CopySpritePlanesAndAppendMask ; @05A5F
    pop cx ; @05A62
    add si,byte +0x60 ; @05A63
    loop loc_5A5B ; @05A66
    mov cx,0x10 ; @05A68
loc_5A6B:
    push cx ; @05A6B
    mov dx,0x20a ; @05A6C
    call GenerateThreeByteSpriteBanks ; @05A6F
    pop cx ; @05A72
    add si,byte +0x28 ; @05A73
    loop loc_5A6B ; @05A76
    mov cx,0x8 ; @05A78
loc_5A7B:
    push cx ; @05A7B
    mov dx,0x20d ; @05A7C
    call CopySpritePlanesAndAppendMask ; @05A7F
    pop cx ; @05A82
    add si,byte +0x34 ; @05A83
    loop loc_5A7B ; @05A86
    mov cx,0xe ; @05A88
loc_5A8B:
    push cx ; @05A8B
    mov dx,0x40e ; @05A8C
    call CopySpritePlanesAndAppendMask ; @05A8F
    pop cx ; @05A92
    add si,byte +0x70 ; @05A93
    loop loc_5A8B ; @05A96
    mov cx,0x10 ; @05A98
loc_5A9B:
    push cx ; @05A9B
    mov dx,0x20a ; @05A9C
    call GenerateThreeByteSpriteBanks ; @05A9F
    pop cx ; @05AA2
    add si,byte +0x28 ; @05AA3
    loop loc_5A9B ; @05AA6
    mov cx,0x20 ; @05AA8
loc_5AAB:
    push cx ; @05AAB
    mov dx,0x20a ; @05AAC
    call GenerateThreeByteSpriteBanks ; @05AAF
    pop cx ; @05AB2
    add si,byte +0x28 ; @05AB3
    loop loc_5AAB ; @05AB6
    call GenerateFiveByteSpriteBanks ; @05AB8
    add si,0x180 ; @05ABB
    pop ds ; @05ABF
EntitySpriteBanksReturn:
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
