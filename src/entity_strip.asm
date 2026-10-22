; Maintained 6F7B..6FE1 two-byte strip leaf.
times -(($-$$) != 0x6f7b) db 0 ; module start assertion
; CONTRACT: incoming CX supplies source DS. CLI precedes saved DS; each
; actual POP CX controls LOOP. LODSW/STOSB follow DF; literal +2Ah yields
; row stride 44 forward or 40 backward. STI precedes actual POP DS/RET.
DrawEntityTwoByteStrip:
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
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06FBB
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @06FBC
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @06FBE
    mov al,0x8 ; @06FC0
    mov [ss:0xe],ax ; @06FC2
    out dx,ax ; @06FC6
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06FC7
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06FC9
    mov al,[es:di] ; @06FCA
    mov al,0x8 ; @06FCD
    db 0x8a,0xe5 ; ENCODED: mov ah,ch (NASM chooses a different encoding) ; @06FCF
    mov [ss:0xe],ax ; @06FD1
    out dx,ax ; @06FD5
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06FD6
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06FD8
    add di,byte +0x2a ; @06FD9
    pop cx ; @06FDC
    loop loc_6FB7 ; @06FDD
    sti ; @06FDF
    pop ds ; @06FE0
EntityTwoByteStripReturn:
    ret ; @06FE1
times -(($-$$) != 0x6fe2) db 0 ; module end assertion
