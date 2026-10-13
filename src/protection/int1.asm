; Derived execution view. Canonical load bytes are in src/program.asm.
; Stream instructions show bytes visible while TF is on/off; first-word patches can overlap.
; Bytes outside this view retain stored encoding and canonical region classifications.
bits 16
org 0x0dff
ProtectionInt1Handler:
    sti ; @00DFF int1_plaintext
    push ax ; @00E00 int1_plaintext
    push si ; @00E01 int1_plaintext
    push ds ; @00E02 int1_plaintext
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00E03 int1_plaintext
    mov ds,ax ; @00E05 int1_plaintext
    lds si,[0x0] ; @00E07 int1_plaintext
    mov ax,[si-0x2] ; @00E0B int1_plaintext
    not ax ; @00E0E int1_plaintext
    rol ax,1 ; @00E10 int1_plaintext
    xor ax,[si] ; @00E12 int1_plaintext
    xchg [si],ax ; @00E14 int1_plaintext
    cmp al,0xcc ; @00E16 int1_plaintext
    jz protected_loc_0E36 ; @00E18 int1_plaintext
    db 0x8b,0xf4 ; ENCODED: mov si,sp (NASM chooses a different encoding) ; @00E1A int1_plaintext
ProtectionDecodeNextWord:
    lds si,[ss:si+0x6] ; @00E1C int1_plaintext
    mov ax,[si-0x2] ; @00E20 int1_plaintext
    not ax ; @00E23 int1_plaintext
    rol ax,1 ; @00E25 int1_plaintext
    xor [si],ax ; @00E27 int1_plaintext
    push ds ; @00E29 int1_plaintext
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00E2A int1_plaintext
    mov ds,ax ; @00E2C int1_plaintext
    mov [0x0],si ; @00E2E int1_plaintext
    pop word [0x2] ; @00E32 int1_plaintext
protected_loc_0E36:
    pop ds ; @00E36 int1_plaintext
    pop si ; @00E37 int1_plaintext
    pop ax ; @00E38 int1_plaintext
    iret ; @00E39 int1_plaintext
