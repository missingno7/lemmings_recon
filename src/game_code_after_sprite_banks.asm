; Word-mask generator prefix and unresolved suffix 5CC1..5D65.

times -(($-$$) != 0x5cc1) db 0 ; module start assertion
sub_5CC1:
    mov si,0x52bc ; @05CC1
    mov es,[0x1fea] ; @05CC4
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05CC8
    mov cx,0x10 ; @05CCA
    mov bl,0x3 ; @05CCD
    call GenerateWordMaskShifts ; @05CCF
    mov si,0x531c ; @05CD2
    mov di,0x480 ; @05CD5
    mov bl,0x3 ; @05CD8
    mov cx,0x10 ; @05CDA
; DS:SI source, ES:DI output, BL repetitions, CX rows; DH starts at zero.
; LODSW follows DF; three stores use INC DI regardless of DF. All saves and
; restored loop controls are live SS memory: aliases can change counts/returns.
; AX/BX/CX/DX/SI/DI/flags are outputs; DS/ES/SS/BP unchanged. No loop caps.
sub_5CDD:
GenerateWordMaskShifts:
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
