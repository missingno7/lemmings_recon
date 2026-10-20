; Maintained image span080FD..08237; remaining display/dirty suffix.
; Physical order and UNKNOWN bytes are preserved.
sub_80FD:
    mov dx,0x3c4 ; @080FD
    mov ax,0xf02 ; @08100
    mov [ss:0x8],ax ; @08103
    out dx,ax ; @08107
    mov dx,0x3ce ; @08108
    mov ax,0x105 ; @0810B
    mov [ss:0x0],ax ; @0810E
    out dx,ax ; @08112
    push ss ; @08113
    pop es ; @08114
    mov di,[DrawingDirtyCellMapOffset-GameDataImage] ; @08115
    mov al,[es:di] ; @08119
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0811C
    jz loc_8123 ; @0811E
    jmp short loc_819D ; @08120
; UNKNOWN: unresolved bytes
    db 0x90 ; @08122
loc_8123:
    push ds ; @08123
    inc di ; @08124
    mov bp,[DrawingOrigin-GameDataImage] ; @08125
    add bp,0x2c2 ; @08129
    mov si,0x4a40 ; @0812D
    mov ax,[0x2] ; @08130
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @08133
    mov dx,0xa000 ; @08135
    mov ds,dx ; @08138
    mov al,0x1 ; @0813A
    mov cx,0x14 ; @0813C
loc_813F:
    push cx ; @0813F
    mov cx,0x28 ; @08140
loc_8143:
    repne scasb ; @08143
    jz loc_8160 ; @08145
loc_8147:
    pop cx ; @08147
    add bp,0x160 ; @08148
    add si,0x680 ; @0814C
    loop loc_813F ; @08150
    pop ds ; @08152
    mov di,[DrawingDirtyCellMapOffset-GameDataImage] ; @08153
    inc di ; @08157
    mov cx,0x320 ; @08158
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0815B
    rep stosb ; @0815D
    ret ; @0815F
loc_8160:
    push cx ; @08160
    repe scasb ; @08161
    pop bx ; @08163
    inc bx ; @08164
    push cx ; @08165
    push di ; @08166
    push si ; @08167
    push bp ; @08168
    push ax ; @08169
    push es ; @0816A
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @0816B
    mov ax,0x28 ; @0816D
    db 0x2b,0xc3 ; ENCODED: sub ax,bx (NASM chooses a different encoding) ; @08170
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @08172
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @08174
    db 0x2b,0xd9 ; ENCODED: sub bx,cx (NASM chooses a different encoding) ; @08176
    db 0x8b,0xcb ; ENCODED: mov cx,bx (NASM chooses a different encoding) ; @08178
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @0817A
    add dx,byte -0x2c ; @0817C
    add bx,0xff30 ; @0817F
    push ds ; @08183
    pop es ; @08184
    mov al,0x8 ; @08185
loc_8187:
    push cx ; @08187
    rep movsb ; @08188
    pop cx ; @0818A
    db 0x2b,0xf3 ; ENCODED: sub si,bx (NASM chooses a different encoding) ; @0818B
    db 0x2b,0xfa ; ENCODED: sub di,dx (NASM chooses a different encoding) ; @0818D
    dec al ; @0818F
    jnz loc_8187 ; @08191
    pop es ; @08193
    pop ax ; @08194
    pop bp ; @08195
    pop si ; @08196
    pop di ; @08197
    pop cx ; @08198
    jcxz loc_8147 ; @08199
    jmp short loc_8143 ; @0819B
loc_819D:
    mov byte [es:di],0x0 ; @0819D
    mov bp,ds ; @081A1
    mov di,[DrawingOrigin-GameDataImage] ; @081A3
    add di,0x2c2 ; @081A7
    mov si,0x4a40 ; @081AB
    mov ax,[0x2] ; @081AE
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @081B1
    mov dx,0xa000 ; @081B3
    mov es,dx ; @081B6
    mov ds,dx ; @081B8
    mov dx,0xa0 ; @081BA
loc_81BD:
    mov cx,0x2c ; @081BD
    rep movsb ; @081C0
    add si,0xa4 ; @081C2
    dec dx ; @081C6
    jnz loc_81BD ; @081C7
    mov ds,bp ; @081C9
    ret ; @081CB
sub_81CC:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @081CC
    mov word [AlternateDrawingOrigin-GameDataImage],0x2520 ; @081D2
    mov word [DrawingPageByteOffset-GameDataImage],0x2c0 ; @081D8
    mov word [DrawingDirtyCellMapOffset-GameDataImage],0x42b2 ; @081DE
    mov word [AlternateDrawingDirtyCellMapOffset-GameDataImage],0x45d3 ; @081E4
    mov bx,[DrawingDirtyCellMapOffset-GameDataImage] ; @081EA
    mov byte [ss:bx],0xff ; @081EE
    mov bx,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @081F2
    mov byte [ss:bx],0xff ; @081F6
    mov byte [DrawingDirtyCellsEnabledByte-GameDataImage],0xff ; @081FA
    call sub_80FD ; @081FF
    mov ax,[AlternateDrawingOrigin-GameDataImage] ; @08202
    xchg [DrawingOrigin-GameDataImage],ax ; @08205
    mov [AlternateDrawingOrigin-GameDataImage],ax ; @08209
    mov ax,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @0820C
    xchg [DrawingDirtyCellMapOffset-GameDataImage],ax ; @0820F
    mov [AlternateDrawingDirtyCellMapOffset-GameDataImage],ax ; @08213
    call InitializeStatusDisplay ; @08216
    call sub_80FD ; @08219
    mov ax,0x160 ; @0821C
    mov bx,0xa0 ; @0821F
    mov dx,[DrawingOrigin-GameDataImage] ; @08222
    call 0x0:SetDrawingLayout ; @08226
    mov word [FixedPatternVgaOffset0008-GameDataImage],0xd2c0 ; @0822B
    mov word [FixedPatternVgaOffset000A-GameDataImage],0xd2f0 ; @08231
    ret ; @08237
