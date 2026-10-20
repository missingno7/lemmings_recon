; Maintained image span07C67..07EB1; terrain, scroll and background contracts.
times -(($-$$) != 0x7c67) db 0 ; module start assertion
; TERRAIN: packed AX x/flags, BX signed-y/type; index low6 selects liveGROUNDrecord.
; Preserve live SS savedSI/coordinates, relocated farCALL frame, returnedDS/ES/flags.
; Prefix7C67..7CB4, farcallee8822, livePOPSI7CBA andnearRET7CBB; no hidden state.
DrawPackedTerrainPiece:
    push si ; @07C67
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @07C68
    mov cl,0x7 ; @07C6A
    shr dx,cl ; @07C6C
    and dx,0xc0 ; @07C6E
    or dx,byte +0xf ; @07C72
    test dx,0x40 ; @07C75
    jz loc_7C7F ; @07C79
    or dx,0xf00 ; @07C7B
loc_7C7F:
    rcl ax,1 ; @07C7F
    jnc loc_7C87 ; @07C81
    or dx,0x8000 ; @07C83
loc_7C87:
    shr ax,1 ; @07C87
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @07C89
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @07C8B
    and dx,byte +0x3f ; @07C8D
    sar bx,cl ; @07C90
    sub bx,byte +0x4 ; @07C92
    and ax,0x1fff ; @07C95
    push bx ; @07C98
    push ax ; @07C99
    mov ax,0x8 ; @07C9A
    mul dx ; @07C9D
    add ax,GroundTerrainGraphicsRecords-GameDataImage ; @07C9F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @07CA2
    mov dl,[bx+GroundTerrainRecordWidthByte-GroundTerrainGraphicsRecords] ; @07CA4
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07CA6
    mov cl,[bx+GroundTerrainRecordHeightByte-GroundTerrainGraphicsRecords] ; @07CA8
    mov si,[bx+GroundTerrainRecordSourceOffset-GroundTerrainGraphicsRecords] ; @07CAB
    mov di,[bx+GroundTerrainRecordMaskOffset-GroundTerrainGraphicsRecords] ; @07CAE
    pop ax ; @07CB1
    pop bx ; @07CB2
    mov ch,0x4 ; @07CB3
TerrainPieceBitmapCall:
    call 0x0:0x8822 ; @07CB5
TerrainPieceAfterBitmap:
    pop si ; @07CBA
TerrainPieceReturn:
    ret ; @07CBB
; One canonical level-graphics buffer, four70x16 byte planes (stride0460).
; DS001D/001F own live text start/cursor;0021 is phase here but prompt pointer48EB.
; Initialize35 two-byte columns with real savedAX/CX/DS and fall through to draw.
; No host page/text copy; sourceUI+1000:4C10, incomingDF affects MOVSW. menu-scroll.md.
InitializeMenuScroll:
    lea ax,[MenuScrollText-GameDataImage] ; @07CBC
    mov [MenuScrollTextStart-GameDataImage],ax ; @07CC0
    mov [MenuScrollTextCursor-GameDataImage],ax ; @07CC3
    mov word [UiScrollPhaseOrPromptPointer-GameDataImage],0x4 ; @07CC6
    mov word [MenuScrollPauseTicks-GameDataImage],0x0 ; @07CCC
    mov es,[LevelGraphicsSegment-GameDataImage] ; @07CD2
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @07CD6
    mov cx,0x23 ; @07CD8
loc_7CDB:
    push cx ; @07CDB
    push ax ; @07CDC
    call CopyMenuScrollTile ; @07CDD
MenuScrollInitializeAfterTile:
    pop ax ; @07CE0
    pop cx ; @07CE1
    inc al ; @07CE2
    loop loc_7CDB ; @07CE4
; Draw560x16 center from live LevelGraphicsSegment, then publish UI+1000.
; Shared7E2F tail draws two48x16 edges, rereading phase after the first child.
; Actual near/far frames, returnedDS/ES and all flags remain live.
DrawMenuScroll:
    mov ax,[LevelGraphicsSegment-GameDataImage] ; @07CE6
    mov [GraphicsResourceSegment-GameDataImage],ax ; @07CE9
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @07CEC
    mov ax,0x30 ; @07CEE
    mov bx,0x14e ; @07CF1
    mov dx,0x230 ; @07CF4
    mov cx,0x410 ; @07CF7
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @07CFA
    call 0x0:0x8822 ; @07CFC
MenuScrollAfterBitmap:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07D01
    add ax,0x1000 ; @07D04
    mov [GraphicsResourceSegment-GameDataImage],ax ; @07D07
    jmp loc_7E2F ; @07D0A
; Draw first. Nonzero0023 decrements in memory and returns without shifting.
; Otherwise phase+=4; every low-nibble zero inserts a tile and one live text byte.
; FF sets pause100 and consumes exactly one next byte; CR reloads001D once.
; Four plane/16 row/70 byte backward loops shift by4 with BL nibble carry.
AdvanceMenuScroll:
    call DrawMenuScroll ; @07D0D
MenuScrollAfterDraw:
    mov ax,[MenuScrollPauseTicks-GameDataImage] ; @07D10
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07D13
    jz loc_7D1C ; @07D15
    dec word [MenuScrollPauseTicks-GameDataImage] ; @07D17
MenuScrollPauseReturn:
    ret ; @07D1B
loc_7D1C:
    mov es,[LevelGraphicsSegment-GameDataImage] ; @07D1C
    mov ax,[UiScrollPhaseOrPromptPointer-GameDataImage] ; @07D20
    add ax,0x4 ; @07D23
    mov [UiScrollPhaseOrPromptPointer-GameDataImage],ax ; @07D26
    and ax,0xf ; @07D29
    jnz loc_7D54 ; @07D2C
    mov al,0x22 ; @07D2E
    call CopyMenuScrollTile ; @07D30
MenuScrollAfterTile:
    mov si,[MenuScrollTextCursor-GameDataImage] ; @07D33
    lodsb ; @07D37
    cmp al,0xff ; @07D38
    jnz loc_7D44 ; @07D3A
    mov word [MenuScrollPauseTicks-GameDataImage],0x64 ; @07D3C
    jmp short loc_7D4C ; @07D42
loc_7D44:
    cmp al,0xd ; @07D44
    jnz loc_7D4D ; @07D46
    mov si,[MenuScrollTextStart-GameDataImage] ; @07D48
loc_7D4C:
    lodsb ; @07D4C
loc_7D4D:
    mov [MenuScrollTextCursor-GameDataImage],si ; @07D4D
    call InsertMenuScrollGlyph ; @07D51
loc_7D54:
MenuScrollAfterGlyph:
    mov di,0x45 ; @07D54
    mov cx,0x4 ; @07D57
loc_7D5A:
    push cx ; @07D5A
    push di ; @07D5B
    mov cx,0x10 ; @07D5C
loc_7D5F:
    push cx ; @07D5F
    push di ; @07D60
    mov cx,0x46 ; @07D61
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @07D64
loc_7D66:
    mov al,[es:di] ; @07D66
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07D69
    shl ax,1 ; @07D6B
    rcl ax,1 ; @07D6D
    rcl ax,1 ; @07D6F
    rcl ax,1 ; @07D71
    db 0x0a,0xc3 ; ENCODED: or al,bl (NASM chooses a different encoding) ; @07D73
    mov [es:di],al ; @07D75
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM chooses a different encoding) ; @07D78
    dec di ; @07D7A
    loop loc_7D66 ; @07D7B
    pop di ; @07D7D
    pop cx ; @07D7E
    add di,byte +0x46 ; @07D7F
    loop loc_7D5F ; @07D82
    pop di ; @07D84
    pop cx ; @07D85
    add di,0x460 ; @07D86
    loop loc_7D5A ; @07D8A
MenuScrollTickReturn:
    ret ; @07D8C
; AL indexes an unchecked two-byte column. PUSH DS precedes selector read;
; MOVSW source is linear4x16 words; destination stride70/plane1120; preserve DF.
; Actual savedDI/CX/DS words are reread; stack aliases may change them.
CopyMenuScrollTile:
    push ds ; @07D8D
    mov si,0x4c10 ; @07D8E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07D91
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07D93
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07D95
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07D97
    add ax,0x1000 ; @07D9A
    mov ds,ax ; @07D9D
    mov cx,0x4 ; @07D9F
loc_7DA2:
    push cx ; @07DA2
    push di ; @07DA3
    mov cx,0x10 ; @07DA4
loc_7DA7:
    movsw ; @07DA7
    add di,byte +0x44 ; @07DA8
    loop loc_7DA7 ; @07DAB
    pop di ; @07DAD
    pop cx ; @07DAE
    add di,0x460 ; @07DAF
    loop loc_7DA2 ; @07DB3
    pop ds ; @07DB5
MenuScrollTileReturn:
    ret ; @07DB6
; Space only saves/restoresDS and CMP flags. OtherAL wraps after SUB21.
; Source5BC0+96*index,masksource+40; three OR passes then one mask-only plane.
; STOSB follows DF, while explicit source INCs remain forward. Live savedBX/DI/CX.
InsertMenuScrollGlyph:
    push ds ; @07DB7
    cmp al,0x20 ; @07DB8
    jz loc_7E2D ; @07DBA
    sub al,0x21 ; @07DBC
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07DBE
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC0
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC2
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC4
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC6
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DC8
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @07DCA
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07DCC
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07DCE
    add si,0x5bc0 ; @07DD0
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @07DD4
    add bx,byte +0x40 ; @07DD6
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07DD9
    add ax,0x1000 ; @07DDC
    mov ds,ax ; @07DDF
    mov di,0x44 ; @07DE1
    mov cx,0x3 ; @07DE4
loc_7DE7:
    push cx ; @07DE7
    push di ; @07DE8
    push bx ; @07DE9
    mov cx,0x10 ; @07DEA
loc_7DED:
    mov al,[bx] ; @07DED
    not al ; @07DEF
    and al,[es:di] ; @07DF1
    or al,[si] ; @07DF4
    stosb ; @07DF6
    inc si ; @07DF7
    inc bx ; @07DF8
    mov al,[bx] ; @07DF9
    not al ; @07DFB
    and al,[es:di] ; @07DFD
    or al,[si] ; @07E00
    stosb ; @07E02
    inc si ; @07E03
    inc bx ; @07E04
    add di,byte +0x44 ; @07E05
    loop loc_7DED ; @07E08
    pop bx ; @07E0A
    pop di ; @07E0B
    pop cx ; @07E0C
    add di,0x460 ; @07E0D
    loop loc_7DE7 ; @07E11
    mov cx,0x10 ; @07E13
loc_7E16:
    mov al,[bx] ; @07E16
    not al ; @07E18
    and al,[es:di] ; @07E1A
    stosb ; @07E1D
    inc bx ; @07E1E
    mov al,[bx] ; @07E1F
    not al ; @07E21
    and al,[es:di] ; @07E23
    stosb ; @07E26
    inc bx ; @07E27
    add di,byte +0x44 ; @07E28
    loop loc_7E16 ; @07E2B
loc_7E2D:
    pop ds ; @07E2D
MenuScrollGlyphReturn:
    ret ; @07E2E
loc_7E2F:
DrawMenuScrollEdges:
    mov si,0x1c10 ; @07E2F
    mov ax,[UiScrollPhaseOrPromptPointer-GameDataImage] ; @07E32
    shr ax,1 ; @07E35
    shr ax,1 ; @07E37
    and ax,0xf ; @07E39
    xchg al,ah ; @07E3C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E3E
    shr ax,1 ; @07E40
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E42
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07E44
    call DrawMenuScrollEdge ; @07E46
MenuScrollAfterFirstEdge:
    mov si,0x1c10 ; @07E49
    mov ax,[UiScrollPhaseOrPromptPointer-GameDataImage] ; @07E4C
    shr ax,1 ; @07E4F
    shr ax,1 ; @07E51
    and ax,0xf ; @07E53
    xchg al,ah ; @07E56
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E58
    shr ax,1 ; @07E5A
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @07E5C
    add si,0x1800 ; @07E5E
    mov ax,0x250 ; @07E62
DrawMenuScrollEdge:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @07E65
    mov dx,0x30 ; @07E67
    mov cx,0x410 ; @07E6A
    mov bx,0x14e ; @07E6D
    call 0x0:0x8822 ; @07E70
MenuScrollEdgeReturn:
    ret ; @07E75
; Publish the UI graphics segment once, then two320x104/two-plane calls per row.
; Saved BX,CX,BX remain live: dirty/stack aliases can change rows and loop count.
; Relocated far frames return to7E95/7EAA; preserve all child DS/ES/flag effects.
DrawScreenBackgroundTiles:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @07E76
    mov [GraphicsResourceSegment-GameDataImage],ax ; @07E79
    mov cx,0x4 ; @07E7C
BackgroundRowLoop:
    push bx ; @07E7F
    push cx ; @07E80
    push bx ; @07E81
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07E82
    mov bp,0xc ; @07E84
    mov dx,0x140 ; @07E87
    mov cx,0x268 ; @07E8A
    mov si,0x0 ; @07E8D
    call 0x0:0x8822 ; @07E90
BackgroundFirstAfterBitmap:
    mov ax,0x140 ; @07E95
    pop bx ; @07E98
    mov bp,0xc ; @07E99
    mov dx,0x140 ; @07E9C
    mov cx,0x268 ; @07E9F
    mov si,0x0 ; @07EA2
    call 0x0:0x8822 ; @07EA5
BackgroundSecondAfterBitmap:
    pop cx ; @07EAA
    pop bx ; @07EAB
    add bx,byte +0x68 ; @07EAC
    loop BackgroundRowLoop ; @07EAF
BackgroundReturn:
    ret ; @07EB1
