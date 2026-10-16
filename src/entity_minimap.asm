; Maintained 6FE2..706E leaf.
times -(($-$$) != 0x6fe2) db 0 ; module start assertion
; CONTRACT: signed Y guards retain entry IF. Drawing uses wrapped MUL/offsets,
; live DrawingOrigin, saved X after SS mirrors/OUTs and the live DS mask table.
; CLI surrounds the actual VGA read/write, STI follows; real RET word stays live.
DrawEntityMinimapPixel:
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
EntityMinimapPixelReturn:
    ret ; @0706E
times -(($-$$) != 0x706f) db 0 ; module end assertion
