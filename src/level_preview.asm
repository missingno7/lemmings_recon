; Level preview: sample source bits5/1 in each of four plane bytes.
; Ordinary geometry is39 rows,52 output bytes; source pitch0340, destination0050.
; PUSH/POP counts/cursors/port/DS are live SS words, not host loop bounds.
; DS=ES=A000 for sampling; destination read supplies OR-mode write latches.
; CLI encloses each destination read/write, STI is unconditional. DF is untouched.
; SS mirrors precede OUT; changed saved DX selects the actual later port.
; Caller4621 follows RedrawLevel; briefing preserves this upper-screen preview.
; See docs/level-preview.md for scope, providers and independent plane checks.
DrawLevelPreview:
    push ds ; @07EB2
    mov di,[DrawingOrigin-GameDataImage] ; @07EB3
    add di,[DrawingPageByteOffset-GameDataImage] ; @07EB7
    add di,0x64f ; @07EBB
    mov si,0x4f22 ; @07EBF
    mov dx,0x3c4 ; @07EC2
    mov ax,0xf02 ; @07EC5
    mov [ss:0x8],ax ; @07EC8
LevelPreviewInitialOutput:
    out dx,ax ; @07ECC
    mov dx,0x3ce ; @07ECD
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07ED0
    mov [ss:0xa],ax ; @07ED2
    out dx,ax ; @07ED6
    mov ax,0x1 ; @07ED7
    mov [ss:0xc],ax ; @07EDA
    out dx,ax ; @07EDE
    mov ax,0x5 ; @07EDF
    mov [ss:0x0],ax ; @07EE2
    out dx,ax ; @07EE6
    mov ax,0x1003 ; @07EE7
    mov [ss:0x2],ax ; @07EEA
    out dx,ax ; @07EEE
    mov ax,0xff08 ; @07EEF
    mov [ss:0xe],ax ; @07EF2
    out dx,ax ; @07EF6
    mov ax,0xa000 ; @07EF7
    mov es,ax ; @07EFA
    mov ds,ax ; @07EFC
    mov cx,0x27 ; @07EFE
loc_7F01:
    push cx ; @07F01
    push si ; @07F02
    push di ; @07F03
    mov cx,0x34 ; @07F04
loc_7F07:
    push cx ; @07F07
    push dx ; @07F08
    mov dx,0x3c4 ; @07F09
    mov ax,0x102 ; @07F0C
    mov [ss:0x8],ax ; @07F0F
    out dx,ax ; @07F13
    pop dx ; @07F14
    mov ax,0x4 ; @07F15
    mov [ss:0x10],ax ; @07F18
    out dx,ax ; @07F1C
    mov ch,[si] ; @07F1D
    mov cl,[si+0x1] ; @07F1F
    mov bh,[si+0x2] ; @07F22
    mov bl,[si+0x3] ; @07F25
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07F28
    rol al,1 ; @07F2A
    rol al,1 ; @07F2C
    and al,0x80 ; @07F2E
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @07F30
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07F32
    ror al,1 ; @07F34
    ror al,1 ; @07F36
    ror al,1 ; @07F38
    and al,0x40 ; @07F3A
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F3C
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07F3E
    and al,0x20 ; @07F40
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F42
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07F44
    rol al,1 ; @07F46
    rol al,1 ; @07F48
    rol al,1 ; @07F4A
    and al,0x10 ; @07F4C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F4E
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07F50
    ror al,1 ; @07F52
    ror al,1 ; @07F54
    and al,0x8 ; @07F56
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F58
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07F5A
    rol al,1 ; @07F5C
    and al,0x4 ; @07F5E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F60
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07F62
    rol al,1 ; @07F64
    rol al,1 ; @07F66
    rol al,1 ; @07F68
    rol al,1 ; @07F6A
    and al,0x2 ; @07F6C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F6E
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07F70
    ror al,1 ; @07F72
    and al,0x1 ; @07F74
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07F76
    cli ; @07F78
    mov al,[di] ; @07F79
    mov [di],ah ; @07F7B
    sti ; @07F7D
    push dx ; @07F7E
    mov dx,0x3c4 ; @07F7F
    mov ax,0x202 ; @07F82
    mov [ss:0x8],ax ; @07F85
    out dx,ax ; @07F89
    pop dx ; @07F8A
    mov ax,0x104 ; @07F8B
    mov [ss:0x10],ax ; @07F8E
    out dx,ax ; @07F92
    mov ch,[si] ; @07F93
    mov cl,[si+0x1] ; @07F95
    mov bh,[si+0x2] ; @07F98
    mov bl,[si+0x3] ; @07F9B
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07F9E
    rol al,1 ; @07FA0
    rol al,1 ; @07FA2
    and al,0x80 ; @07FA4
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @07FA6
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @07FA8
    ror al,1 ; @07FAA
    ror al,1 ; @07FAC
    ror al,1 ; @07FAE
    and al,0x40 ; @07FB0
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FB2
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07FB4
    and al,0x20 ; @07FB6
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FB8
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @07FBA
    rol al,1 ; @07FBC
    rol al,1 ; @07FBE
    rol al,1 ; @07FC0
    and al,0x10 ; @07FC2
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FC4
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07FC6
    ror al,1 ; @07FC8
    ror al,1 ; @07FCA
    and al,0x8 ; @07FCC
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FCE
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @07FD0
    rol al,1 ; @07FD2
    and al,0x4 ; @07FD4
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FD6
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07FD8
    rol al,1 ; @07FDA
    rol al,1 ; @07FDC
    rol al,1 ; @07FDE
    rol al,1 ; @07FE0
    and al,0x2 ; @07FE2
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FE4
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @07FE6
    ror al,1 ; @07FE8
    and al,0x1 ; @07FEA
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @07FEC
    cli ; @07FEE
    mov al,[di] ; @07FEF
    mov [di],ah ; @07FF1
    sti ; @07FF3
    push dx ; @07FF4
    mov dx,0x3c4 ; @07FF5
    mov ax,0x402 ; @07FF8
    mov [ss:0x8],ax ; @07FFB
    out dx,ax ; @07FFF
    pop dx ; @08000
    mov ax,0x204 ; @08001
    mov [ss:0x10],ax ; @08004
    out dx,ax ; @08008
    mov ch,[si] ; @08009
    mov cl,[si+0x1] ; @0800B
    mov bh,[si+0x2] ; @0800E
    mov bl,[si+0x3] ; @08011
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @08014
    rol al,1 ; @08016
    rol al,1 ; @08018
    and al,0x80 ; @0801A
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0801C
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0801E
    ror al,1 ; @08020
    ror al,1 ; @08022
    ror al,1 ; @08024
    and al,0x40 ; @08026
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @08028
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0802A
    and al,0x20 ; @0802C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0802E
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @08030
    rol al,1 ; @08032
    rol al,1 ; @08034
    rol al,1 ; @08036
    and al,0x10 ; @08038
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0803A
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @0803C
    ror al,1 ; @0803E
    ror al,1 ; @08040
    and al,0x8 ; @08042
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @08044
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @08046
    rol al,1 ; @08048
    and al,0x4 ; @0804A
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0804C
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @0804E
    rol al,1 ; @08050
    rol al,1 ; @08052
    rol al,1 ; @08054
    rol al,1 ; @08056
    and al,0x2 ; @08058
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0805A
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @0805C
    ror al,1 ; @0805E
    and al,0x1 ; @08060
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @08062
    cli ; @08064
    mov al,[di] ; @08065
    mov [di],ah ; @08067
    sti ; @08069
    push dx ; @0806A
    mov dx,0x3c4 ; @0806B
    mov ax,0x802 ; @0806E
    mov [ss:0x8],ax ; @08071
    out dx,ax ; @08075
    pop dx ; @08076
    mov ax,0x304 ; @08077
    mov [ss:0x10],ax ; @0807A
    out dx,ax ; @0807E
    mov ch,[si] ; @0807F
    mov cl,[si+0x1] ; @08081
    mov bh,[si+0x2] ; @08084
    mov bl,[si+0x3] ; @08087
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0808A
    rol al,1 ; @0808C
    rol al,1 ; @0808E
    and al,0x80 ; @08090
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @08092
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @08094
    ror al,1 ; @08096
    ror al,1 ; @08098
    ror al,1 ; @0809A
    and al,0x40 ; @0809C
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0809E
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @080A0
    and al,0x20 ; @080A2
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080A4
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @080A6
    rol al,1 ; @080A8
    rol al,1 ; @080AA
    rol al,1 ; @080AC
    and al,0x10 ; @080AE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080B0
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @080B2
    ror al,1 ; @080B4
    ror al,1 ; @080B6
    and al,0x8 ; @080B8
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080BA
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @080BC
    rol al,1 ; @080BE
    and al,0x4 ; @080C0
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080C2
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @080C4
    rol al,1 ; @080C6
    rol al,1 ; @080C8
    rol al,1 ; @080CA
    rol al,1 ; @080CC
    and al,0x2 ; @080CE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080D0
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @080D2
    ror al,1 ; @080D4
    and al,0x1 ; @080D6
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @080D8
    cli ; @080DA
    mov al,[di] ; @080DB
    mov [di],ah ; @080DD
    sti ; @080DF
    inc di ; @080E0
    add si,byte +0x4 ; @080E1
    pop cx ; @080E4
    dec cx ; @080E5
    jz loc_80EB ; @080E6
    jmp loc_7F07 ; @080E8
loc_80EB:
    pop di ; @080EB
    pop si ; @080EC
    add di,byte +0x50 ; @080ED
    add si,0x340 ; @080F0
    pop cx ; @080F4
    dec cx ; @080F5
    jz loc_80FB ; @080F6
    jmp loc_7F01 ; @080F8
loc_80FB:
    pop ds ; @080FB
LevelPreviewReturn:
    ret ; @080FC
