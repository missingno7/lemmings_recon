; Maintained780D..78FF status icon outline and restoration.
times -(($-$$) != 0x780d) db 0 ; module start assertion
; CONTRACT: AL selects unchecked destination; zero-extend then double to DI.
;24 rows: two full16-pixel bands and22 side rows. CLI covers the entire body;
; final STI is unconditional. Mirror/OUT/latch/STOSB order and DF remain live.
DrawStatusIconOutline:
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
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @07829
    out dx,ax ; @0782D
    mov dx,0x3ce ; @0782E
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07831
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @07833
    out dx,ax ; @07837
    mov ax,0xc01 ; @07838
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @0783B
    out dx,ax ; @0783F
    mov ax,0x5 ; @07840
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @07843
    out dx,ax ; @07847
    mov ax,0x3 ; @07848
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @0784B
    out dx,ax ; @0784F
    mov ax,0xff08 ; @07850
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07853
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
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @0786C
    out dx,ax ; @07870
    mov ah,[es:di] ; @07871
    mov al,0x80 ; @07874
    stosb ; @07876
    mov ax,0x108 ; @07877
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @0787A
    out dx,ax ; @0787E
    mov ah,[es:di] ; @0787F
    mov al,0x1 ; @07882
    stosb ; @07884
    add di,byte +0x2a ; @07885
    loop loc_7869 ; @07888
    mov ax,0xff08 ; @0788A
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @0788D
    out dx,ax ; @07891
    mov al,0xff ; @07892
    mov ah,[es:di] ; @07894
    stosb ; @07897
    mov ah,[es:di] ; @07898
    stosb ; @0789B
    sti ; @0789C
StatusIconOutlineReturn:
    ret ; @0789D
; CONTRACT: SIGNED AL<10 includes80..FF. BL=3*AL wraps to byte before BH=0;
; word[DS:64+BL+1]=0 precedes PUSH DS. Actual saved DI/DS and RET stay live.
;24 pairs of MOVSB use VGA mode1, DF and explicit +2A row adjustments.
RestoreStatusIcon:
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
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @078D1
    out dx,ax ; @078D5
    mov dx,0x3ce ; @078D6
    mov ax,0x105 ; @078D9
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @078DC
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
StatusIconRestoreReturn:
    ret ; @078FF
times -(($-$$) != 0x7900) db 0 ; module end assertion
