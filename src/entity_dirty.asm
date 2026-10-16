; Maintained5726..57D0 dirty-row leaf.
times -(($-$$) != 0x5726) db 0 ; module start assertion
; CONTRACT: live unchecked DS visibility byte and two separate map-offset reads.
; SS row stores can alter saved CX/SI. First row is unconditional, BP is checked
; after writes and CL decrement wraps. Keep raw rows and all segment/flag effects.
MarkEntityDrawingDirty:
    mov bx,[di] ; @05726
    add bx,[di+0x4] ; @05728
    jns loc_5731 ; @0572B
    add bx,0x160 ; @0572D
loc_5731:
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @05731
    shr bx,1 ; @05733
    shr bx,1 ; @05735
    shr bx,1 ; @05737
    lea si,[ViewVisibilityMapBase-GameDataImage] ; @05739
    cmp byte [bx+si],0x1 ; @0573D
    jz loc_5745 ; @05740
    jmp loc_57D0 ; @05742
loc_5745:
    sub ax,[LevelViewOriginPixels-GameDataImage] ; @05745
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
EntityDrawingDirtyReturn:
    ret ; @057D0
times -(($-$$) != 0x57d1) db 0 ; module end assertion
