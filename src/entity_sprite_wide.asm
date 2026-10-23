; Maintained sprite callbacks 6BDB..6CFB; physical order unchanged.

times -(($-$$) != 0x6bdb) db 0 ; module start assertion
; CONTRACT: source DS=incoming CX, three planes, five bytes per nominal row.
; Initial OUT precedes each SS mirror. Later OR setup mirrors precede OUT.
; BP holds live destination base; each row POPs actual CX. First pass DEC/JZ,
; later LOOP, literal +27h pitch and DF strings remain distinct. MOV DL,C4
; preserves DH. Physical word-high wrap, aliases, POP DS and RET remain live.
DrawEntityWideSprite32:
    push ds ; @06BDB
    mov dx,0x3c4 ; @06BDC
    mov ax,0xf02 ; @06BDF
    out dx,ax ; @06BE2
    mov [ss:0x8],ax ; @06BE3
    mov dx,0x3ce ; @06BE7
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06BEA
    out dx,ax ; @06BEC
    mov [ss:0xa],ax ; @06BED
    mov ax,0xe01 ; @06BF1
    out dx,ax ; @06BF4
    mov [ss:0xc],ax ; @06BF5
    mov ax,0x5 ; @06BF9
    out dx,ax ; @06BFC
    mov [ss:0x0],ax ; @06BFD
    mov ax,0x3 ; @06C01
    out dx,ax ; @06C04
    mov [ss:0x2],ax ; @06C05
    mov ds,cx ; @06C09
    mov cx,0xa000 ; @06C0B
    mov es,cx ; @06C0E
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @06C10
    mov cx,0x20 ; @06C12
loc_6C15:
    push cx ; @06C15
    mov cx,[bx] ; @06C16
    inc bx ; @06C18
    inc bx ; @06C19
    mov al,0x8 ; @06C1A
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06C1C
    mov [ss:0xe],ax ; @06C1E
    out dx,ax ; @06C22
    cli ; @06C23
    mov al,[es:di] ; @06C24
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06C27
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06C28
    sti ; @06C29
    xchg ch,ah ; @06C2A
    mov al,0x8 ; @06C2C
    mov [ss:0xe],ax ; @06C2E
    out dx,ax ; @06C32
    cli ; @06C33
    mov al,[es:di] ; @06C34
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06C37
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06C39
    sti ; @06C3A
    mov cx,[bx] ; @06C3B
    inc bx ; @06C3D
    inc bx ; @06C3E
    mov al,0x8 ; @06C3F
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06C41
    mov [ss:0xe],ax ; @06C43
    out dx,ax ; @06C47
    cli ; @06C48
    mov al,[es:di] ; @06C49
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06C4C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06C4D
    sti ; @06C4E
    xchg ch,ah ; @06C4F
    mov al,0x8 ; @06C51
    mov [ss:0xe],ax ; @06C53
    out dx,ax ; @06C57
    cli ; @06C58
    mov al,[es:di] ; @06C59
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06C5C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06C5E
    sti ; @06C5F
    mov cl,[bx] ; @06C60
    inc bx ; @06C62
    mov al,0x8 ; @06C63
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @06C65
    mov [ss:0xe],ax ; @06C67
    out dx,ax ; @06C6B
    cli ; @06C6C
    mov al,[es:di] ; @06C6D
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06C70
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06C71
    sti ; @06C72
    add di,byte +0x27 ; @06C73
    pop cx ; @06C76
    dec cx ; @06C77
    jz EntityWideSprite32OrPlane1 ; @06C78
; Interior blocks of DrawEntityWideSprite32 (6BDB..6CFB) down to 6CFA: legacy
; lifter splits, not entries (only local branches/fall-throughs reach them; none
; is a known 715B callback target). Here: pass 1 row back edge, taken while the
; count reread from the stack and decremented is nonzero (DEC CX/JZ/JMP form).
EntityWideSprite32NextMaskedRow:
    jmp short loc_6C15 ; @06C7A
; Pass 2 setup after the masked pass: DI=BP (destination base), set/reset
; off, GC3=10h (OR), bit mask FFh, MOV DL,C4h keeps DH, map mask 02h (plane 1),
; CX=20h rows. Each row: latch read before each of five writes (LODSW, AH,
; LODSW, AH, LODSB) under one CLI..STI, ADD DI,27h, POP CX, LOOP.
EntityWideSprite32OrPlane1:
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @06C7C
    mov ax,0x1 ; @06C7E
    mov [ss:0xc],ax ; @06C81
    out dx,ax ; @06C85
    mov ax,0x1003 ; @06C86
    mov [ss:0x2],ax ; @06C89
    out dx,ax ; @06C8D
    mov ax,0xff08 ; @06C8E
    mov [ss:0xe],ax ; @06C91
    out dx,ax ; @06C95
    mov dl,0xc4 ; @06C96
    mov ax,0x202 ; @06C98
    mov [ss:0x8],ax ; @06C9B
    out dx,ax ; @06C9F
    mov cx,0x20 ; @06CA0
loc_6CA3:
    push cx ; @06CA3
    cli ; @06CA4
    mov al,[es:di] ; @06CA5
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06CA8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CA9
    mov al,[es:di] ; @06CAA
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CAD
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CAF
    mov al,[es:di] ; @06CB0
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06CB3
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CB4
    mov al,[es:di] ; @06CB5
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CB8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CBA
    mov al,[es:di] ; @06CBB
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06CBE
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CBF
    sti ; @06CC0
    add di,byte +0x27 ; @06CC1
    pop cx ; @06CC4
    loop loc_6CA3 ; @06CC5
; Pass 3 setup: DI=BP again, map mask 04h (plane 2), CX=20h rows; same row
; body as pass 2.
EntityWideSprite32OrPlane2:
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @06CC7
    mov dl,0xc4 ; @06CC9
    mov ax,0x402 ; @06CCB
    mov [ss:0x8],ax ; @06CCE
    out dx,ax ; @06CD2
    mov cx,0x20 ; @06CD3
loc_6CD6:
    push cx ; @06CD6
    cli ; @06CD7
    mov al,[es:di] ; @06CD8
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06CDB
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CDC
    mov al,[es:di] ; @06CDD
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CE0
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CE2
    mov al,[es:di] ; @06CE3
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06CE6
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CE7
    mov al,[es:di] ; @06CE8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06CEB
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CED
    mov al,[es:di] ; @06CEE
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06CF1
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06CF2
    sti ; @06CF3
    add di,byte +0x27 ; @06CF4
    pop cx ; @06CF7
    loop loc_6CD6 ; @06CF8
; Exit: POP DS restores the caller DS saved at 6BDB, then RET 6CFB.
EntityWideSprite32RestoreDs:
    pop ds ; @06CFA
EntityWideSprite32Return:
    ret ; @06CFB
times -(($-$$) != 0x6cfc) db 0 ; module end assertion
