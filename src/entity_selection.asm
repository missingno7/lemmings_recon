; Maintained image span 03CDE..03E6E; physical order and UNKNOWN bytes preserved.
times -(($-$$) != 0x3cde) db 0 ; module start assertion
; T2 UNCONDITIONAL: intact reset/producer words give0 or0088+2D*k,k00..FE;byte count never scansFF. Zero bound skips0063/index/pointer resets,so wrap retains stale above-new-bound selection. Actions validate neither range nor+26. Forward455B reset clears these globals;other writers/aliases UNRESOLVED.
; CONTRACT: frozen entry CL controls the scan; zero leaves all candidate state stale.
; Live0043-CL determines bucket index. Last matching record wins in each bucket;
; pointer fields survive sentinel resets. Signed wrapped geometry retains0680->00D0.
; PUSH/POP AX, formatter CALL/RET, selected pointer and templates remain live.
; See docs/entity-actions.md; UNKNOWN holes and record extents remain unresolved.
SelectEntityCandidate:
    mov cl,[EntitySlotBound-GameDataImage] ; @03CDE
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @03CE2
    jnz loc_3CE9 ; @03CE4
    jmp EntitySelectionReturn ; @03CE6
loc_3CE9:
    mov si,0x2083 ; @03CE9
    mov ah,0xb ; @03CEC
loc_3CEE:
    mov byte [si],0x20 ; @03CEE
    inc si ; @03CF1
    dec ah ; @03CF2
    jnz loc_3CEE ; @03CF4
    mov byte [EntityCandidateCount-GameDataImage],0x0 ; @03CF6
    mov byte [EntitySelectedSlotIndex-GameDataImage],0xff ; @03CFB
    mov byte [EntityPreferredSlotIndex-GameDataImage],0xff ; @03D00
    mov byte [EntityAlternateSlotIndex-GameDataImage],0xff ; @03D05
    mov ax,[0x0] ; @03D0A
    sub ax,0x10 ; @03D0D
    add ax,[0x10] ; @03D10
    mov bx,[0x12] ; @03D14
    add bx,byte +0x8 ; @03D18
    mov si,0x88 ; @03D1B
loc_3D1E:
    cmp byte [si+0x26],0xff ; @03D1E
    jnz loc_3D27 ; @03D22
    jmp short loc_3DA5 ; @03D24
; S14 U046: [03D26,03D27) stored bytes remain UNKNOWN.
; Neighbours: P 03D24 jmp 0x3da5; N 03D27 mov bp, word ptr [si].
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D26
loc_3D27:
    mov bp,[si] ; @03D27
    add bp,[si+0x4] ; @03D29
    sub bp,byte +0x4 ; @03D2C
    jns loc_3D33 ; @03D2F
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @03D31
loc_3D33:
    mov di,[si+0x2] ; @03D33
    add di,[si+0x6] ; @03D36
    dec di ; @03D39
    jns loc_3D3E ; @03D3A
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @03D3C
loc_3D3E:
    db 0x3b,0xc5 ; ENCODED: cmp ax,bp (NASM chooses a different encoding) ; @03D3E
    jnl loc_3D45 ; @03D40
    jmp short loc_3DA5 ; @03D42
; S14 U047: [03D44,03D45) stored bytes remain UNKNOWN.
; Neighbours: P 03D42 jmp 0x3da5; N 03D45 cmp bx, di.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D44
loc_3D45:
    db 0x3b,0xdf ; ENCODED: cmp bx,di (NASM chooses a different encoding) ; @03D45
    jnl loc_3D4C ; @03D47
    jmp short loc_3DA5 ; @03D49
; S14 U048: [03D4B,03D4C) stored bytes remain UNKNOWN.
; Neighbours: P 03D49 jmp 0x3da5; N 03D4C add bp, 0xc.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D4B
loc_3D4C:
    add bp,byte +0xc ; @03D4C
    cmp bp,0x680 ; @03D4F
    jnl loc_3D58 ; @03D53
    jmp short loc_3D5B ; @03D55
; S14 U049: [03D57,03D58) stored bytes remain UNKNOWN.
; Neighbours: P 03D55 jmp 0x3d5b; N 03D58 mov bp, 0xd0.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D57
loc_3D58:
    mov bp,0xd0 ; @03D58
loc_3D5B:
    add di,byte +0xc ; @03D5B
    cmp di,0xb0 ; @03D5E
    jnl loc_3D67 ; @03D62
    jmp short loc_3D6A ; @03D64
; S14 U050: [03D66,03D67) stored bytes remain UNKNOWN.
; Neighbours: P 03D64 jmp 0x3d6a; N 03D67 mov di, 0xb0.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D66
loc_3D67:
    mov di,0xb0 ; @03D67
loc_3D6A:
    db 0x3b,0xc5 ; ENCODED: cmp ax,bp (NASM chooses a different encoding) ; @03D6A
    jng loc_3D71 ; @03D6C
    jmp short loc_3DA5 ; @03D6E
; S14 U051: [03D70,03D71) stored bytes remain UNKNOWN.
; Neighbours: P 03D6E jmp 0x3da5; N 03D71 cmp bx, di.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D70
loc_3D71:
    db 0x3b,0xdf ; ENCODED: cmp bx,di (NASM chooses a different encoding) ; @03D71
    jng loc_3D78 ; @03D73
    jmp short loc_3DA5 ; @03D75
; S14 U052: [03D77,03D78) stored bytes remain UNKNOWN.
; Neighbours: P 03D75 jmp 0x3da5; N 03D78 push ax.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D77
loc_3D78:
    push ax ; @03D78
    test byte [si+0x24],0x80 ; @03D79
    jnz loc_3D86 ; @03D7D
    test word [si+0x8],0x8b90 ; @03D7F
    jz loc_3D94 ; @03D84
loc_3D86:
    mov al,[EntitySlotBound-GameDataImage] ; @03D86
    db 0x2a,0xc1 ; ENCODED: sub al,cl (NASM chooses a different encoding) ; @03D89
    mov [EntityPreferredSlotIndex-GameDataImage],al ; @03D8B
    mov [EntityPreferredRecordOffset-GameDataImage],si ; @03D8E
    jmp short loc_3DA0 ; @03D92
loc_3D94:
    mov al,[EntitySlotBound-GameDataImage] ; @03D94
    db 0x2a,0xc1 ; ENCODED: sub al,cl (NASM chooses a different encoding) ; @03D97
    mov [EntityAlternateSlotIndex-GameDataImage],al ; @03D99
    mov [EntityAlternateRecordOffset-GameDataImage],si ; @03D9C
loc_3DA0:
    pop ax ; @03DA0
    inc byte [EntityCandidateCount-GameDataImage] ; @03DA1
loc_3DA5:
    add si,byte +0x2d ; @03DA5
    dec cl ; @03DA8
    jz loc_3DAF ; @03DAA
    jmp loc_3D1E ; @03DAC
loc_3DAF:
    mov byte [EntitySelectionPresent-GameDataImage],0x0 ; @03DAF
    mov ax,[InputButtonsWord-GameDataImage] ; @03DB4
    test ax,0x2 ; @03DB7
    jz loc_3DCC ; @03DBA
loc_3DBC:
    mov al,[EntityAlternateSlotIndex-GameDataImage] ; @03DBC
    mov si,[EntityAlternateRecordOffset-GameDataImage] ; @03DBF
    mov [EntitySelectedSlotIndex-GameDataImage],al ; @03DC3
    mov [EntitySelectedRecordOffset-GameDataImage],si ; @03DC6
    jmp short loc_3DDE ; @03DCA
loc_3DCC:
    mov al,[EntityPreferredSlotIndex-GameDataImage] ; @03DCC
    cmp al,0xff ; @03DCF
    jz loc_3DBC ; @03DD1
    mov si,[EntityPreferredRecordOffset-GameDataImage] ; @03DD3
    mov [EntitySelectedSlotIndex-GameDataImage],al ; @03DD7
    mov [EntitySelectedRecordOffset-GameDataImage],si ; @03DDA
loc_3DDE:
    cmp byte [EntitySelectedSlotIndex-GameDataImage],0xff ; @03DDE
    jnz loc_3DE8 ; @03DE3
    jmp short EntitySelectionReturn ; @03DE5
; S14 U053: [03DE7,03DE8) stored bytes remain UNKNOWN.
; Neighbours: P 03DE5 jmp 0x3e62; N 03DE8 mov byte ptr [0x1a], 0xff.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03DE7
loc_3DE8:
    mov byte [EntitySelectionPresent-GameDataImage],0xff ; @03DE8
    mov si,0x208b ; @03DED
    mov al,[EntityCandidateCount-GameDataImage] ; @03DF0
    call WriteDecimalByteField ; @03DF3
EntitySelectionAfterFormatter:
    mov si,[EntitySelectedRecordOffset-GameDataImage] ; @03DF6
    mov bx,0x48db ; @03DFA
    mov al,[si+0x24] ; @03DFD
    test al,0x80 ; @03E00
    jnz loc_3E53 ; @03E02
    mov bx,0x48bf ; @03E04
    test al,0x1 ; @03E07
    jnz loc_3E63 ; @03E09
    mov bx,0x48c6 ; @03E0B
    cmp byte [si+0x25],0x0 ; @03E0E
    jnz loc_3E53 ; @03E12
    mov bx,0x48d4 ; @03E14
    test word [si+0x8],0x100 ; @03E17
    jnz loc_3E53 ; @03E1C
    mov bx,0x48db ; @03E1E
    test word [si+0x8],0x80 ; @03E21
    jnz loc_3E53 ; @03E26
    mov bx,0x48e2 ; @03E28
    test word [si+0x8],0x200 ; @03E2B
    jnz loc_3E53 ; @03E30
    mov bx,0x48e9 ; @03E32
    test word [si+0x8],0x800 ; @03E35
    jnz loc_3E53 ; @03E3A
    mov bx,0x48f0 ; @03E3C
    test word [si+0x8],0x10 ; @03E3F
    jnz loc_3E53 ; @03E44
    mov bx,0x48fe ; @03E46
    test word [si+0x8],0x4 ; @03E49
    jnz loc_3E53 ; @03E4E
    mov bx,0x48f7 ; @03E50
loc_3E53:
    mov si,0x2083 ; @03E53
    mov ah,0x7 ; @03E56
loc_3E58:
    mov al,[bx] ; @03E58
    mov [si],al ; @03E5A
    inc si ; @03E5C
    inc bx ; @03E5D
    dec ah ; @03E5E
    jnz loc_3E58 ; @03E60
EntitySelectionReturn:
    ret ; @03E62
loc_3E63:
    cmp byte [si+0x25],0x0 ; @03E63
    jz loc_3E53 ; @03E67
    lea bx,[0x490c] ; @03E69
    jmp short loc_3E53 ; @03E6D
times -(($-$$) != 0x3e6f) db 0 ; module end assertion
