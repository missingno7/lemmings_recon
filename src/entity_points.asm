; Maintained 6E83..6F7A point-cloud leaf.
times -(($-$$) != 0x6e83) db 0 ; module start assertion
; CONTRACT: unchecked byte selector, live DS point/color/mask inputs.
; Count zero executes 65536 iterations; low 80h skips only its point.
; Low signed delta is X, high signed delta is Y. SS dirty writes precede
; actual coordinate POPs; mirrors, saved mask, live RET and IF remain live.
; TABLE/PRODUCER CONTRACT: frame schema is50h LE words/A0h bytes. Each word
; stores signed X in low byte and signed Y in high; low80h skips this point,
; irrespective of high byte. First stored pair is9CCC (X=-34h,Y=-64h).
; 042C sets DS004D=50h after per-level clear;6ECC reads it once (not a bound
; on arbitrary entry). 365A compares callback to live003C;365F/3664 signed
; frame>=1 admits01..7F, not merely the normal animation's01..33.
; Normal bit0002 producers:2D33/2E7B set frame0 with callback from003C
; (normally6BDB);2353 increments frame,2358 deactivates at34 before drawing.
; With intact record/slots, no intervening alias/service change, this produces
; frames1..33, offsets2788..4767 at50 words each. Do NOT infer total extent
; from adjacent text4913 or assume the code clamps a different starting frame.
; Stored frame-like bytes continue beyond4767; their total ownership remains
; unresolved. 6E83 subtracts1 as BYTE then MUL A0:raw selector0 selectsFF,
; baseC6E8;caller7F selects7E,base7648. No saturation or table-end sentinel.
;
; COLOR TABLE:DS2778..2787 stores04,02,06,07,08,09,0A,0B,08,09,0A,0B,
;0C,0D,0E,0F;one byte/entry, index is remainingCX&0F at6F56..6F5F. Normal
; count50 starts index0 thenF..1, five cycles;skipped/clipped points do not
; fetch a color but still decrement CX. Color is sent live to GC set/reset.
; It is a VGA plane-bit color, not an RGB/palette-pointer-table selector.
;
; PAIR TABLE CROSS-DEPENDENCY:state0400 at2A6D usesDS2698+recordWord0E;
;21E3 initializes0,2A7B adds2 with word wrap and no count/terminator. First
;byte becomes frame+28 BEFORE second-byte read;second is signed Y delta except
;1/2/3 request that many collision probes. This state uses callback003A on its
;normal producer, so those pair frame bytes are not point-frame producers.
; Apparent2698..2777 schema:8 lead pairs then13 repetitions of8 pairs;
;lead(01,03)(02,03)(03,03)(05,03)(05,FF)(05,00)(05,01)(05,01), repeat
;(05,02)(06,02)(07,02)(07,02)(06,02)(05,02)(04,02)(04,02). The112-pair
;stored candidate has NO proved terminal index; keep its extent unresolved.
;
; LIFETIME/WRITERS:stored DS colors/frames/pairs survive startup0000..2011
;and level0000..0FC9 clears. No dedicated normal table-mutator is decoded;
;this leaf only reads them. GROUND request1B4B..2B4A can replace pairs/colors
;and2788..2B4A prefix;supplied0420 bytes stop1F6A. Unchecked2Dh record spans
;fromDD touch colors/first frame, throughFF end2D87;D8 touches pair storage.
;Cache name-padding1E51/1E60 can underflow/wrap across DS;live row/formatter
;cursors, returned heap selectors, SS/data/VGA/provider aliases remain writers
;outside nominal domains. Canonical DS09A9 and SS143E are distinct frames;
;dirty bytes at6F20 use SS,not these DS tables by equal numeric offset.
; READINESS: CONDITIONAL on those explicit lifetime/segment/alias domains.
;Classification proposals cover only the color window and normal point prefix;
;they neither close all aliases nor classify the entire neighboring UNKNOWN run.
DrawEntityPointCloud:
    mov al,[si+0x28] ; @06E83
    sub al,0x1 ; @06E86
    mov bl,0xa0 ; @06E88
    mul bl ; @06E8A
    lea bx,[EntityPointFrames-GameDataImage] ; @06E8C
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @06E90
    mov dx,0x3c4 ; @06E92
    mov ax,0xf02 ; @06E95
    mov [ss:0x8],ax ; @06E98
    out dx,ax ; @06E9C
    mov dx,0x3ce ; @06E9D
    mov ax,0xf01 ; @06EA0
    mov [ss:0xc],ax ; @06EA3
    out dx,ax ; @06EA7
    mov ax,0x5 ; @06EA8
    mov [ss:0x0],ax ; @06EAB
    out dx,ax ; @06EAF
    mov ax,0x3 ; @06EB0
    mov [ss:0x2],ax ; @06EB3
    out dx,ax ; @06EB7
    mov ax,0xa000 ; @06EB8
    mov es,ax ; @06EBB
    mov bp,[si] ; @06EBD
    sub bp,[LevelViewOriginPixels-GameDataImage] ; @06EBF
    add bp,byte +0x10 ; @06EC3
    mov dx,[si+0x2] ; @06EC6
    sub dx,byte +0x10 ; @06EC9
    mov cl,[EntityPointCount-GameDataImage] ; @06ECC
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @06ED0
loc_6ED2:
    mov ax,[bx] ; @06ED2
    add bx,byte +0x2 ; @06ED4
    cmp al,0x80 ; @06ED7
    jnz loc_6EDE ; @06ED9
    jmp loc_6F74 ; @06EDB
loc_6EDE:
    push bp ; @06EDE
    push dx ; @06EDF
    push bx ; @06EE0
    push ax ; @06EE1
    cbw ; @06EE2
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @06EE3
    pop ax ; @06EE5
    jns loc_6EEB ; @06EE6
    jmp loc_6F71 ; @06EE8
loc_6EEB:
    xchg al,ah ; @06EEB
    cbw ; @06EED
    db 0x03,0xd0 ; ENCODED: add dx,ax (NASM chooses a different encoding) ; @06EEE
    js short loc_6F71 ; original +127-byte branch; preserve short encoding at its limit ; @06EF0
    cmp bp,0x150 ; @06EF2
    jnl loc_6F71 ; @06EF6
    cmp dx,0xa0 ; @06EF8
    jnl loc_6F71 ; @06EFC
    push dx ; @06EFE
    push bp ; @06EFF
    push si ; @06F00
    mov si,[DrawingDirtyCellMapOffset-GameDataImage] ; @06F01
    inc si ; @06F05
    sub bp,byte +0x10 ; @06F06
    jns loc_6F0D ; @06F09
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @06F0B
loc_6F0D:
    shr bp,1 ; @06F0D
    shr bp,1 ; @06F0F
    shr bp,1 ; @06F11
    db 0x03,0xf5 ; ENCODED: add si,bp (NASM chooses a different encoding) ; @06F13
    and dx,byte -0x8 ; @06F15
    db 0x03,0xf2 ; ENCODED: add si,dx (NASM chooses a different encoding) ; @06F18
    shl dx,1 ; @06F1A
    shl dx,1 ; @06F1C
    db 0x03,0xf2 ; ENCODED: add si,dx (NASM chooses a different encoding) ; @06F1E
    mov byte [ss:si],0x1 ; @06F20
    pop si ; @06F24
    pop bp ; @06F25
    pop dx ; @06F26
    mov ax,0x2c ; @06F27
    mul dx ; @06F2A
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @06F2C
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @06F2E
    shr bp,1 ; @06F30
    shr bp,1 ; @06F32
    shr bp,1 ; @06F34
    db 0x03,0xfd ; ENCODED: add di,bp (NASM chooses a different encoding) ; @06F36
    add di,[DrawingOrigin-GameDataImage] ; @06F38
    add di,[DrawingPageByteOffset-GameDataImage] ; @06F3C
    and ax,0x7 ; @06F40
    lea bx,[PixelBitMasks-GameDataImage] ; @06F43
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @06F47
    mov ah,[bx] ; @06F49
    mov al,0x8 ; @06F4B
    mov [ss:0xe],ax ; @06F4D
    mov dx,0x3ce ; @06F51
    out dx,ax ; @06F54
    push ax ; @06F55
    db 0x8b,0xd9 ; ENCODED: mov bx,cx (NASM chooses a different encoding) ; @06F56
    and bx,byte +0xf ; @06F58
    add bx,EntityPointColors-GameDataImage ; @06F5B
    mov ah,[bx] ; @06F5F
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06F61
    mov [ss:0xa],ax ; @06F63
    out dx,ax ; @06F67
    pop ax ; @06F68
    cli ; @06F69
    mov al,[es:di] ; @06F6A
    mov [es:di],ah ; @06F6D
    sti ; @06F70
loc_6F71:
    pop bx ; @06F71
    pop dx ; @06F72
    pop bp ; @06F73
loc_6F74:
    dec cx ; @06F74
    jz EntityPointCloudReturn ; @06F75
    jmp loc_6ED2 ; @06F77
EntityPointCloudReturn:
    ret ; @06F7A
times -(($-$$) != 0x6f7b) db 0 ; module end assertion
