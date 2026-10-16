; Maintained7900..796E display preparation; untranslated.
times -(($-$$) != 0x7900) db 0 ; module start assertion
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
times -(($-$$) != 0x796f) db 0 ; module end assertion
