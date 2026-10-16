; Maintained suffix after view_visibility.asm; physical order unchanged.
times -(($-$$) != 0x414f) db 0 ; module start assertion
loc_414F:
    mov ax,[0x0] ; @0414F
    cmp ax,0x10 ; @04152
    jng loc_4179 ; @04155
    sub ax,0x8 ; @04157
    test word [InputButtonsWord-GameDataImage],0x2 ; @0415A
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
    jmp short RebuildViewVisibilityMap ; @04179
; CONTRACT: live DS:SI NUL scan, no40-character bound; DF and AH wrap remain.
; Actual AX/SI saves and glyph CALL/RET carry returned DS/ES/flags into next scan.
DrawStatusText:
    lodsb ; @0417B
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0417C
    jz loc_418B ; @0417E
    push ax ; @04180
    push si ; @04181
    call DrawStatusGlyph ; @04182
StatusTextAfterGlyph:
    pop si ; @04185
    pop ax ; @04186
    inc ah ; @04187
    jmp short DrawStatusText ; @04189
loc_418B:
StatusTextReturn:
    ret ; @0418B
times -(($-$$) != 0x418c) db 0 ; module end assertion
