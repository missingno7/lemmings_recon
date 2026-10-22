; Maintained6170..64D8 sprite leaf; no child calls or guest branches.
times -(($-$$) != 0x6170) db 0 ; module start assertion
; CONTRACT: real PUSH DS precedes setup, then source DS is incoming CX.
; Ten literal masked three-byte rows consume live forward BX and DF LODS.
; DI=BP restarts ten OR plane02 rows (GC3 data10h). STOS follows DF; +29h stays literal.
; Per-pixel latch/CLI/STI phases, SS mirrors, final POP DS/RET stay live.
DrawEntityAlignedSprite:
    push ds ; @06170
    mov dx,0x3c4 ; @06171
    mov ax,0xf02 ; @06174
    mov [ss:0x8],ax ; @06177
    out dx,ax ; @0617B
    mov dx,0x3ce ; @0617C
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0617F
    mov [ss:0xa],ax ; @06181
    out dx,ax ; @06185
    mov ax,0xe01 ; @06186
    mov [ss:0xc],ax ; @06189
    out dx,ax ; @0618D
    mov ax,0x5 ; @0618E
    mov [ss:0x0],ax ; @06191
    out dx,ax ; @06195
    mov ax,0x3 ; @06196
    mov [ss:0x2],ax ; @06199
    out dx,ax ; @0619D
    mov ds,cx ; @0619E
    mov cx,0xa000 ; @061A0
    mov es,cx ; @061A3
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @061A5
    mov cx,[bx] ; @061A7
    inc bx ; @061A9
    inc bx ; @061AA
    mov al,0x8 ; @061AB
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @061AD
    mov [ss:0xe],ax ; @061AF
    out dx,ax ; @061B3
    cli ; @061B4
    mov al,[es:di] ; @061B5
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @061B8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @061B9
    sti ; @061BA
    xchg ch,ah ; @061BB
    mov al,0x8 ; @061BD
    mov [ss:0xe],ax ; @061BF
    out dx,ax ; @061C3
    cli ; @061C4
    mov al,[es:di] ; @061C5
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @061C8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @061CA
    sti ; @061CB
    mov ah,[bx] ; @061CC
    inc bx ; @061CE
    mov al,0x8 ; @061CF
    mov [ss:0xe],ax ; @061D1
    out dx,ax ; @061D5
    cli ; @061D6
    mov al,[es:di] ; @061D7
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @061DA
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @061DB
    sti ; @061DC
    add di,byte +0x29 ; @061DD
    mov cx,[bx] ; @061E0
    inc bx ; @061E2
    inc bx ; @061E3
    mov al,0x8 ; @061E4
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @061E6
    mov [ss:0xe],ax ; @061E8
    out dx,ax ; @061EC
    cli ; @061ED
    mov al,[es:di] ; @061EE
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @061F1
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @061F2
    sti ; @061F3
    xchg ch,ah ; @061F4
    mov al,0x8 ; @061F6
    mov [ss:0xe],ax ; @061F8
    out dx,ax ; @061FC
    cli ; @061FD
    mov al,[es:di] ; @061FE
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06201
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06203
    sti ; @06204
    mov ah,[bx] ; @06205
    inc bx ; @06207
    mov al,0x8 ; @06208
    mov [ss:0xe],ax ; @0620A
    out dx,ax ; @0620E
    cli ; @0620F
    mov al,[es:di] ; @06210
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06213
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06214
    sti ; @06215
    add di,byte +0x29 ; @06216
    mov cx,[bx] ; @06219
    inc bx ; @0621B
    inc bx ; @0621C
    mov al,0x8 ; @0621D
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0621F
    mov [ss:0xe],ax ; @06221
    out dx,ax ; @06225
    cli ; @06226
    mov al,[es:di] ; @06227
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @0622A
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0622B
    sti ; @0622C
    xchg ch,ah ; @0622D
    mov al,0x8 ; @0622F
    mov [ss:0xe],ax ; @06231
    out dx,ax ; @06235
    cli ; @06236
    mov al,[es:di] ; @06237
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0623A
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0623C
    sti ; @0623D
    mov ah,[bx] ; @0623E
    inc bx ; @06240
    mov al,0x8 ; @06241
    mov [ss:0xe],ax ; @06243
    out dx,ax ; @06247
    cli ; @06248
    mov al,[es:di] ; @06249
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @0624C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0624D
    sti ; @0624E
    add di,byte +0x29 ; @0624F
    mov cx,[bx] ; @06252
    inc bx ; @06254
    inc bx ; @06255
    mov al,0x8 ; @06256
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06258
    mov [ss:0xe],ax ; @0625A
    out dx,ax ; @0625E
    cli ; @0625F
    mov al,[es:di] ; @06260
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06263
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06264
    sti ; @06265
    xchg ch,ah ; @06266
    mov al,0x8 ; @06268
    mov [ss:0xe],ax ; @0626A
    out dx,ax ; @0626E
    cli ; @0626F
    mov al,[es:di] ; @06270
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06273
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06275
    sti ; @06276
    mov ah,[bx] ; @06277
    inc bx ; @06279
    mov al,0x8 ; @0627A
    mov [ss:0xe],ax ; @0627C
    out dx,ax ; @06280
    cli ; @06281
    mov al,[es:di] ; @06282
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06285
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06286
    sti ; @06287
    add di,byte +0x29 ; @06288
    mov cx,[bx] ; @0628B
    inc bx ; @0628D
    inc bx ; @0628E
    mov al,0x8 ; @0628F
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06291
    mov [ss:0xe],ax ; @06293
    out dx,ax ; @06297
    cli ; @06298
    mov al,[es:di] ; @06299
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @0629C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0629D
    sti ; @0629E
    xchg ch,ah ; @0629F
    mov al,0x8 ; @062A1
    mov [ss:0xe],ax ; @062A3
    out dx,ax ; @062A7
    cli ; @062A8
    mov al,[es:di] ; @062A9
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @062AC
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @062AE
    sti ; @062AF
    mov ah,[bx] ; @062B0
    inc bx ; @062B2
    mov al,0x8 ; @062B3
    mov [ss:0xe],ax ; @062B5
    out dx,ax ; @062B9
    cli ; @062BA
    mov al,[es:di] ; @062BB
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @062BE
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @062BF
    sti ; @062C0
    add di,byte +0x29 ; @062C1
    mov cx,[bx] ; @062C4
    inc bx ; @062C6
    inc bx ; @062C7
    mov al,0x8 ; @062C8
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @062CA
    mov [ss:0xe],ax ; @062CC
    out dx,ax ; @062D0
    cli ; @062D1
    mov al,[es:di] ; @062D2
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @062D5
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @062D6
    sti ; @062D7
    xchg ch,ah ; @062D8
    mov al,0x8 ; @062DA
    mov [ss:0xe],ax ; @062DC
    out dx,ax ; @062E0
    cli ; @062E1
    mov al,[es:di] ; @062E2
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @062E5
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @062E7
    sti ; @062E8
    mov ah,[bx] ; @062E9
    inc bx ; @062EB
    mov al,0x8 ; @062EC
    mov [ss:0xe],ax ; @062EE
    out dx,ax ; @062F2
    cli ; @062F3
    mov al,[es:di] ; @062F4
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @062F7
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @062F8
    sti ; @062F9
    add di,byte +0x29 ; @062FA
    mov cx,[bx] ; @062FD
    inc bx ; @062FF
    inc bx ; @06300
    mov al,0x8 ; @06301
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06303
    mov [ss:0xe],ax ; @06305
    out dx,ax ; @06309
    cli ; @0630A
    mov al,[es:di] ; @0630B
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @0630E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0630F
    sti ; @06310
    xchg ch,ah ; @06311
    mov al,0x8 ; @06313
    mov [ss:0xe],ax ; @06315
    out dx,ax ; @06319
    cli ; @0631A
    mov al,[es:di] ; @0631B
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0631E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06320
    sti ; @06321
    mov ah,[bx] ; @06322
    inc bx ; @06324
    mov al,0x8 ; @06325
    mov [ss:0xe],ax ; @06327
    out dx,ax ; @0632B
    cli ; @0632C
    mov al,[es:di] ; @0632D
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06330
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06331
    sti ; @06332
    add di,byte +0x29 ; @06333
    mov cx,[bx] ; @06336
    inc bx ; @06338
    inc bx ; @06339
    mov al,0x8 ; @0633A
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @0633C
    mov [ss:0xe],ax ; @0633E
    out dx,ax ; @06342
    cli ; @06343
    mov al,[es:di] ; @06344
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06347
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06348
    sti ; @06349
    xchg ch,ah ; @0634A
    mov al,0x8 ; @0634C
    mov [ss:0xe],ax ; @0634E
    out dx,ax ; @06352
    cli ; @06353
    mov al,[es:di] ; @06354
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06357
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06359
    sti ; @0635A
    mov ah,[bx] ; @0635B
    inc bx ; @0635D
    mov al,0x8 ; @0635E
    mov [ss:0xe],ax ; @06360
    out dx,ax ; @06364
    cli ; @06365
    mov al,[es:di] ; @06366
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06369
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0636A
    sti ; @0636B
    add di,byte +0x29 ; @0636C
    mov cx,[bx] ; @0636F
    inc bx ; @06371
    inc bx ; @06372
    mov al,0x8 ; @06373
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06375
    mov [ss:0xe],ax ; @06377
    out dx,ax ; @0637B
    cli ; @0637C
    mov al,[es:di] ; @0637D
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06380
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06381
    sti ; @06382
    xchg ch,ah ; @06383
    mov al,0x8 ; @06385
    mov [ss:0xe],ax ; @06387
    out dx,ax ; @0638B
    cli ; @0638C
    mov al,[es:di] ; @0638D
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06390
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06392
    sti ; @06393
    mov ah,[bx] ; @06394
    inc bx ; @06396
    mov al,0x8 ; @06397
    mov [ss:0xe],ax ; @06399
    out dx,ax ; @0639D
    cli ; @0639E
    mov al,[es:di] ; @0639F
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @063A2
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @063A3
    sti ; @063A4
    add di,byte +0x29 ; @063A5
    mov cx,[bx] ; @063A8
    inc bx ; @063AA
    inc bx ; @063AB
    mov al,0x8 ; @063AC
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @063AE
    mov [ss:0xe],ax ; @063B0
    out dx,ax ; @063B4
    cli ; @063B5
    mov al,[es:di] ; @063B6
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @063B9
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @063BA
    sti ; @063BB
    xchg ch,ah ; @063BC
    mov al,0x8 ; @063BE
    mov [ss:0xe],ax ; @063C0
    out dx,ax ; @063C4
    cli ; @063C5
    mov al,[es:di] ; @063C6
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @063C9
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @063CB
    sti ; @063CC
    mov ah,[bx] ; @063CD
    inc bx ; @063CF
    mov al,0x8 ; @063D0
    mov [ss:0xe],ax ; @063D2
    out dx,ax ; @063D6
    cli ; @063D7
    mov al,[es:di] ; @063D8
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @063DB
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @063DC
    sti ; @063DD
    add di,byte +0x29 ; @063DE
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @063E1
    mov ax,0x1 ; @063E3
    mov [ss:0xc],ax ; @063E6
    out dx,ax ; @063EA
    mov ax,0x1003 ; @063EB
    mov [ss:0x2],ax ; @063EE
    out dx,ax ; @063F2
    mov ax,0xff08 ; @063F3
    mov [ss:0xe],ax ; @063F6
    out dx,ax ; @063FA
    mov dl,0xc4 ; @063FB
    mov ax,0x202 ; @063FD
    mov [ss:0x8],ax ; @06400
    out dx,ax ; @06404
    cli ; @06405
    mov al,[es:di] ; @06406
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06409
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0640A
    mov al,[es:di] ; @0640B
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0640E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06410
    mov al,[es:di] ; @06411
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06414
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06415
    sti ; @06416
    add di,byte +0x29 ; @06417
    cli ; @0641A
    mov al,[es:di] ; @0641B
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @0641E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0641F
    mov al,[es:di] ; @06420
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06423
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06425
    mov al,[es:di] ; @06426
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06429
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0642A
    sti ; @0642B
    add di,byte +0x29 ; @0642C
    cli ; @0642F
    mov al,[es:di] ; @06430
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06433
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06434
    mov al,[es:di] ; @06435
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06438
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0643A
    mov al,[es:di] ; @0643B
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @0643E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0643F
    sti ; @06440
    add di,byte +0x29 ; @06441
    cli ; @06444
    mov al,[es:di] ; @06445
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06448
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06449
    mov al,[es:di] ; @0644A
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0644D
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0644F
    mov al,[es:di] ; @06450
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06453
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06454
    sti ; @06455
    add di,byte +0x29 ; @06456
    cli ; @06459
    mov al,[es:di] ; @0645A
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @0645D
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0645E
    mov al,[es:di] ; @0645F
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06462
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06464
    mov al,[es:di] ; @06465
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06468
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06469
    sti ; @0646A
    add di,byte +0x29 ; @0646B
    cli ; @0646E
    mov al,[es:di] ; @0646F
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06472
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06473
    mov al,[es:di] ; @06474
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06477
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06479
    mov al,[es:di] ; @0647A
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @0647D
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0647E
    sti ; @0647F
    add di,byte +0x29 ; @06480
    cli ; @06483
    mov al,[es:di] ; @06484
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06487
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06488
    mov al,[es:di] ; @06489
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0648C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0648E
    mov al,[es:di] ; @0648F
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06492
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06493
    sti ; @06494
    add di,byte +0x29 ; @06495
    cli ; @06498
    mov al,[es:di] ; @06499
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @0649C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0649D
    mov al,[es:di] ; @0649E
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @064A1
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064A3
    mov al,[es:di] ; @064A4
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @064A7
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064A8
    sti ; @064A9
    add di,byte +0x29 ; @064AA
    cli ; @064AD
    mov al,[es:di] ; @064AE
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @064B1
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064B2
    mov al,[es:di] ; @064B3
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @064B6
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064B8
    mov al,[es:di] ; @064B9
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @064BC
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064BD
    sti ; @064BE
    add di,byte +0x29 ; @064BF
    cli ; @064C2
    mov al,[es:di] ; @064C3
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @064C6
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064C7
    mov al,[es:di] ; @064C8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @064CB
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064CD
    mov al,[es:di] ; @064CE
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @064D1
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @064D2
    sti ; @064D3
    add di,byte +0x29 ; @064D4
    pop ds ; @064D7
EntityAlignedSpriteReturn:
    ret ; @064D8
times -(($-$$) != 0x64d9) db 0 ; module end assertion
