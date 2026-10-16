; Sprite-bank producer leaves 5B11..5CC0; physical byte order unchanged.

times -(($-$$) != 0x5b11) db 0 ; module start assertion
; CONTRACT: ordinary DH/DL nonzero inputs generate eight banks for shifts 0..7.
; Each bank emits DH planes of DL three-byte rows from live DS byte pairs,
; then DL OR-mask rows reread from live ES with pitch 3*DL. AH:AL:BL is the
; 24-bit chain; SHR AH/RCR AL/RCR BL execute one-bit steps. No string op: DF
; is preserved and has no cursor effect. Every explicit byte EA wraps at 16 bits.
; CH counters are do-while (zero means 256). CL starts at zero, but actual
; outer POP CX then INC CL/CMP CL,8 owns subsequent shifts/termination. Actual
; POP SI resets each bank; plane/mask POP CX and mask POP SI/DX are live too.
; PUSH DX/XOR DH computes pitch from pre-POP DL; restored DX owns later work.
; Stack words use physical(low)+1 with 20-bit wrap. No alias/disjoint guarantee.
; After the final bank, signed DI<10h skips folding; otherwise ES+=DI>>4 and
; DI&=0Fh, with CX=old ES. DS/SS/DF survive; residual registers/FLAGS are live.
; The core stops before 5BAF; adapter reads the actual caller word at SS:SP.
GenerateThreeByteSpriteBanks:
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @05B11
loc_5B13:
    push cx ; @05B13
    push si ; @05B14
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @05B15
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05B17
loc_5B19:
    push cx ; @05B19
    db 0x8a,0xea ; ENCODED: mov ch,dl (NASM chooses a different encoding) ; @05B1A
loc_5B1C:
    mov ah,[si] ; @05B1C
    mov al,[si+0x1] ; @05B1E
    add si,byte +0x2 ; @05B21
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05B24
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @05B26
    jz loc_5B36 ; @05B28
    db 0x8a,0xf9 ; ENCODED: mov bh,cl (NASM chooses a different encoding) ; @05B2A
loc_5B2C:
    shr ah,1 ; @05B2C
    rcr al,1 ; @05B2E
    rcr bl,1 ; @05B30
    dec bh ; @05B32
    jnz loc_5B2C ; @05B34
loc_5B36:
    mov [es:di],ah ; @05B36
    mov [es:di+0x1],al ; @05B39
    mov [es:di+0x2],bl ; @05B3D
    add di,byte +0x3 ; @05B41
    dec ch ; @05B44
    jnz loc_5B1C ; @05B46
    pop cx ; @05B48
    dec ch ; @05B49
    jnz loc_5B19 ; @05B4B
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @05B4D
    db 0x8a,0xea ; ENCODED: mov ch,dl (NASM chooses a different encoding) ; @05B4F
loc_5B51:
    push si ; @05B51
    push cx ; @05B52
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05B53
    push dx ; @05B55
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @05B56
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @05B58
    db 0x03,0xd2 ; ENCODED: add dx,dx (NASM chooses a different encoding) ; @05B5A
    db 0x03,0xea ; ENCODED: add bp,dx (NASM chooses a different encoding) ; @05B5C
    pop dx ; @05B5E
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05B5F
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05B61
loc_5B63:
    or ah,[es:si] ; @05B63
    or al,[es:si+0x1] ; @05B66
    or bl,[es:si+0x2] ; @05B6A
    db 0x03,0xf5 ; ENCODED: add si,bp (NASM chooses a different encoding) ; @05B6E
    dec ch ; @05B70
    jnz loc_5B63 ; @05B72
    mov [es:di],ah ; @05B74
    mov [es:di+0x1],al ; @05B77
    mov [es:di+0x2],bl ; @05B7B
    add di,byte +0x3 ; @05B7F
    pop cx ; @05B82
    pop si ; @05B83
    add si,byte +0x3 ; @05B84
    dec ch ; @05B87
    jnz loc_5B51 ; @05B89
    pop si ; @05B8B
    pop cx ; @05B8C
    inc cl ; @05B8D
    cmp cl,0x8 ; @05B8F
    jz loc_5B97 ; @05B92
    jmp loc_5B13 ; @05B94
loc_5B97:
    cmp di,byte +0x10 ; @05B97
    jl ThreeByteSpriteBanksReturn ; @05B9A
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @05B9C
    shr ax,1 ; @05B9E
    shr ax,1 ; @05BA0
    shr ax,1 ; @05BA2
    shr ax,1 ; @05BA4
    mov cx,es ; @05BA6
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05BA8
    mov es,ax ; @05BAA
    and di,byte +0xf ; @05BAC
ThreeByteSpriteBanksReturn:
    ret ; @05BAF
; CONTRACT: copy DH planes of DL words from live DS:SI to ES:DI, then append
; DL OR-mask words read back from live ES with pitch 2*DL. This is the ordinary
; nonzero, DF-clear, disjoint-bank layout, not a bound on unchecked inputs.
; CH decrement loops are do-while: zero DH or DL gives 256 iterations. REP's
; zero CX still copies zero words. MOVSW/STOSW follow DF; mask SI adds stay
; forward. Mask bytes use separate ES:SI and ES:(SI+1) operands, so the second
; offset wraps at 16 bits, unlike the physical high byte of a word transfer.
; All CX/SI saves and RET are live SS words. Signed DI<10h skips folding;
; otherwise ES+=DI>>4 and DI&=0Fh, with CX replaced by the previous ES.
; Existing producer witnesses cover ordinary banks only; aliases/zero counts
; and segment/DF quirks require their own bounded native verification.
CopySpritePlanesAndAppendMask:
    push si ; @05BB0
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @05BB1
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05BB3
loc_5BB5:
    push cx ; @05BB5
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @05BB6
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05BB8
    rep movsw ; @05BBA
    pop cx ; @05BBC
    dec ch ; @05BBD
    jnz loc_5BB5 ; @05BBF
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @05BC1
    db 0x8a,0xea ; ENCODED: mov ch,dl (NASM chooses a different encoding) ; @05BC3
loc_5BC5:
    push si ; @05BC5
    push cx ; @05BC6
    db 0x8a,0xee ; ENCODED: mov ch,dh (NASM chooses a different encoding) ; @05BC7
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05BC9
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05BCB
    shl ax,1 ; @05BCD
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @05BCF
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05BD1
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05BD3
loc_5BD5:
    or al,[es:si] ; @05BD5
    or ah,[es:si+0x1] ; @05BD8
    db 0x03,0xf5 ; ENCODED: add si,bp (NASM chooses a different encoding) ; @05BDC
    dec ch ; @05BDE
    jnz loc_5BD5 ; @05BE0
    stosw ; @05BE2
    pop cx ; @05BE3
    pop si ; @05BE4
    add si,byte +0x2 ; @05BE5
    dec ch ; @05BE8
    jnz loc_5BC5 ; @05BEA
    pop si ; @05BEC
    cmp di,byte +0x10 ; @05BED
    jl SpriteBankReturn ; @05BF0
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @05BF2
    shr ax,1 ; @05BF4
    shr ax,1 ; @05BF6
    shr ax,1 ; @05BF8
    shr ax,1 ; @05BFA
    mov cx,es ; @05BFC
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05BFE
    mov es,ax ; @05C00
    and di,byte +0xf ; @05C02
SpriteBankReturn:
    ret ; @05C05
; CONTRACT: ordinary intact-save path emits eight 640-byte banks: three planes
; of 32 five-byte rows then a 32-row OR mask. Four source bytes form a big-endian
; 32-bit word extended with zero BL, shifted via SHR BP/RCR DX/RCR BL one bit.
; All source/destination/mask bytes use separate wrapped 16-bit EAs; no strings,
; so DF is preserved without reversing traversal. Stack words use physical+1.
; Entry PUSH CX/SI/DI: POP SI at 5C53 consumes actual saved DI as mask source;
; final POP SI at 5C9C consumes the actual source cursor. Per-plane and per-mask
; POP CX and mask POP SI remain live, including alias/provider changes. Mask
; pitch is A0h, BH=3 planes, CH=20h rows. Outer POP CX/INC CL/CMP CL,8 controls
; shifts and termination. Saved counts may change the nominal dimensions.
; Signed DI<10h skips folding; otherwise ES+=DI>>4, DI&=0Fh and CX=old ES.
; DS/SS/DF survive; other residual roles/defined FLAGS and actual RET stay live.
GenerateFiveByteSpriteBanks:
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @05C06
loc_5C08:
    push cx ; @05C08
    push si ; @05C09
    push di ; @05C0A
    mov ch,0x3 ; @05C0B
loc_5C0D:
    push cx ; @05C0D
    mov ch,0x20 ; @05C0E
loc_5C10:
    mov ah,[si] ; @05C10
    mov al,[si+0x1] ; @05C12
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @05C15
    mov dh,[si+0x2] ; @05C17
    mov dl,[si+0x3] ; @05C1A
    add si,byte +0x4 ; @05C1D
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05C20
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @05C22
    jz loc_5C32 ; @05C24
    db 0x8a,0xf9 ; ENCODED: mov bh,cl (NASM chooses a different encoding) ; @05C26
loc_5C28:
    shr bp,1 ; @05C28
    rcr dx,1 ; @05C2A
    rcr bl,1 ; @05C2C
    dec bh ; @05C2E
    jnz loc_5C28 ; @05C30
loc_5C32:
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @05C32
    mov [es:di],ah ; @05C34
    mov [es:di+0x1],al ; @05C37
    mov [es:di+0x2],dh ; @05C3B
    mov [es:di+0x3],dl ; @05C3F
    mov [es:di+0x4],bl ; @05C43
    add di,byte +0x5 ; @05C47
    dec ch ; @05C4A
    jnz loc_5C10 ; @05C4C
    pop cx ; @05C4E
    dec ch ; @05C4F
    jnz loc_5C0D ; @05C51
    pop si ; @05C53
    mov ch,0x20 ; @05C54
loc_5C56:
    push si ; @05C56
    push cx ; @05C57
    mov bh,0x3 ; @05C58
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @05C5A
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05C5C
    db 0x33,0xd2 ; ENCODED: xor dx,dx (NASM chooses a different encoding) ; @05C5E
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @05C60
loc_5C62:
    or ah,[es:si] ; @05C62
    or al,[es:si+0x1] ; @05C65
    or ch,[es:si+0x2] ; @05C69
    or cl,[es:si+0x3] ; @05C6D
    or dh,[es:si+0x4] ; @05C71
    add si,0xa0 ; @05C75
    dec bh ; @05C79
    jnz loc_5C62 ; @05C7B
    mov [es:di],ah ; @05C7D
    mov [es:di+0x1],al ; @05C80
    mov [es:di+0x2],ch ; @05C84
    mov [es:di+0x3],cl ; @05C88
    mov [es:di+0x4],dh ; @05C8C
    add di,byte +0x5 ; @05C90
    pop cx ; @05C93
    pop si ; @05C94
    add si,byte +0x5 ; @05C95
    dec ch ; @05C98
    jnz loc_5C56 ; @05C9A
    pop si ; @05C9C
    pop cx ; @05C9D
    inc cl ; @05C9E
    cmp cl,0x8 ; @05CA0
    jz loc_5CA8 ; @05CA3
    jmp loc_5C08 ; @05CA5
loc_5CA8:
    cmp di,byte +0x10 ; @05CA8
    jl FiveByteSpriteBanksReturn ; @05CAB
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @05CAD
    shr ax,1 ; @05CAF
    shr ax,1 ; @05CB1
    shr ax,1 ; @05CB3
    shr ax,1 ; @05CB5
    mov cx,es ; @05CB7
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @05CB9
    mov es,ax ; @05CBB
    and di,byte +0xf ; @05CBD
FiveByteSpriteBanksReturn:
    ret ; @05CC0
