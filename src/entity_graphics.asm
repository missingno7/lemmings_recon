; Maintained image span 05D66..0616F: generated masks and entity pixel drawing.
; Reconstruction module, not a historical linker claim. See docs/entity-mask.md.
times -(($-$$) != 0x5d66) db 0 ; module start assertion
; DS:SI source, ES:DI output, BL repetitions, CX rows; DH starts at zero.
; LODSB and STOSW both follow DF. All SS saves/controls and final RET stay live.
; AX/BX/CX/DX/SI/DI/flags are outputs; DS/ES/SS/BP unchanged. No loop caps.
sub_5D66:
GenerateByteMaskShifts:
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @05D66
loc_5D68:
    push dx ; @05D68
    push bx ; @05D69
    push si ; @05D6A
loc_5D6B:
    push bx ; @05D6B
    push cx ; @05D6C
loc_5D6D:
    push cx ; @05D6D
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @05D6E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @05D6F
    db 0x22,0xf6 ; ENCODED: and dh,dh (NASM chooses a different encoding) ; @05D71
    jz loc_5D7F ; @05D73
    db 0x8a,0xfe ; ENCODED: mov bh,dh (NASM chooses a different encoding) ; @05D75
loc_5D77:
    shr al,1 ; @05D77
    rcr ah,1 ; @05D79
    dec bh ; @05D7B
    jnz loc_5D77 ; @05D7D
; S19 DF-site census stosw word ptr es:[di], ax: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_5D7F:
    stosw ; @05D7F
    pop cx ; @05D80
    loop loc_5D6D ; @05D81
    pop cx ; @05D83
    pop bx ; @05D84
    dec bl ; @05D85
    jnz loc_5D6B ; @05D87
    pop si ; @05D89
    pop bx ; @05D8A
    pop dx ; @05D8B
    inc dh ; @05D8C
    cmp dh,0x8 ; @05D8E
    jnz loc_5D68 ; @05D91
    ret ; @05D93
; 5D94..5DC5: configure entity pixel readback. Entry flags stay live.
; SEQ2=0F; GC5=08 (read mode1/write mode0), GC7=08, GC2=08.
; Each SS mirror store precedes its OUT. AX/ES=A000, DX=03CE.
; DS row-pitch word0004=D0 is written last; aliases can stale a mirror/RET.
; Other registers unchanged. Device state not explicitly written remains live.
ConfigureEntityPixelReadback:
sub_5D94:
    mov dx,0x3c4 ; @05D94
    mov ax,0xf02 ; @05D97
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @05D9A
    out dx,ax ; @05D9E
    mov dx,0x3ce ; @05D9F
    mov ax,0x805 ; @05DA2
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @05DA5
    out dx,ax ; @05DA9
    mov ax,0x807 ; @05DAA
    mov [ss:VgaColorCareMirror-RuntimeStackFrame],ax ; @05DAD
    out dx,ax ; @05DB1
    mov ax,0x802 ; @05DB2
    mov [ss:VgaColorCompareMirror-RuntimeStackFrame],ax ; @05DB5
    out dx,ax ; @05DB9
    mov ax,0xa000 ; @05DBA
    mov es,ax ; @05DBD
    mov word [EntityPixelRowPitchBytes-GameDataImage],0xd0 ; @05DBF
    ret ; @05DC5
; 5DC6..5DF7: prepare a record pixel sample; no VGA reads occur here.
; DS:SI+2 gives wrapped Y-10h. Clamp when the subtraction result is negative,
; rather than comparing signed Y. Low MUL(D0h,row) supplies DI and residual AL.
; PUSH DX precedes the later DS:SI X read; SS aliases can change X or the mask.
; ES=A000h; DI=low_product+(X>>3)+4A40h; CX=X>>3 (logical shifts).
; BX=PixelBitMasks+(X&7); AH is the live DS table byte; AL keeps low product.
; DX is popped live, SI/BP/DS/SS unchanged. Final flags: ADD BX,547Ch at5DF1.
; RET consumes the live near word. RAM core contract: entity-pixel.md.
PrepareEntityPixelSample:
sub_5DC6:
    mov ax,0xa000 ; @05DC6
    mov es,ax ; @05DC9
    mov di,[si+0x2] ; @05DCB
    sub di,byte +0x10 ; @05DCE
    jns loc_5DD5 ; @05DD1
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05DD3
loc_5DD5:
    push dx ; @05DD5
    mov ax,0xd0 ; @05DD6
    mul di ; @05DD9
    pop dx ; @05DDB
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @05DDC
    mov cx,[si] ; @05DDE
    db 0x8b,0xd9 ; ENCODED: mov bx,cx (NASM chooses a different encoding) ; @05DE0
    shr cx,1 ; @05DE2
    shr cx,1 ; @05DE4
    shr cx,1 ; @05DE6
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @05DE8
    add di,0x4a40 ; @05DEA
    and bx,byte +0x7 ; @05DEE
    add bx,PixelBitMasks-GameDataImage ; @05DF1
    mov ah,[bx] ; @05DF5
    ret ; @05DF7
; 5DF8..5EB9: draw generated 22-row/three-byte mask, top clip only.
; Wrapped (Y-1Eh) sign controls clipping; unsigned NEG result>21 returns early.
; Early return leaves IF unchanged. Drawing CLI is followed by unconditional STI.
; DS source = live GeneratedGraphicsBufferSegment after PUSH DS; source cursor
; 0C60h+66*((X-8)&7)+3*live popped clip word, all arithmetic wraps16 bits.
; DS record X is read twice, after different SS saves. CX/clip/DX/DS/SI/RET
; restore actual SS words. Zero popped CX still enters LOOP and wraps.
; Every source/ES:A000 latch read, SS mirror/OUT08, and DF STOSB stays ordered.
; Incoming mode/map/compare/care/SEQ state stays live; output port is popped DX.
; Source LODSW/LODSB follow DF; DI adds CDh after each three-byte row.
; No bottom clip or selector/count bounds. Full contract: docs/entity-mask.md.
sub_5DF8:
DrawClippedEntityMask:
    mov dx,0x3ce ; @05DF8
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05DFB
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @05DFD
    out dx,ax ; @05E01
    mov ax,0xf01 ; @05E02
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @05E05
    out dx,ax ; @05E09
    mov ax,0x3 ; @05E0A
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @05E0D
    out dx,ax ; @05E11
    mov ax,0xa000 ; @05E12
    mov es,ax ; @05E15
    mov cx,0x16 ; @05E17
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @05E1A
    mov di,[si+0x2] ; @05E1C
    sub di,byte +0x1e ; @05E1F
    jns loc_5E34 ; @05E22
    db 0x03,0xcf ; ENCODED: add cx,di (NASM chooses a different encoding) ; @05E24
    neg di ; @05E26
    cmp di,byte +0x15 ; @05E28
    jna loc_5E30 ; @05E2B
    jmp loc_5EB9 ; @05E2D
loc_5E30:
    db 0x8b,0xdf ; ENCODED: mov bx,di (NASM chooses a different encoding) ; @05E30
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05E32
loc_5E34:
    push cx ; @05E34
    push bx ; @05E35
    mov ax,0xd0 ; @05E36
    push dx ; @05E39
    mul di ; @05E3A
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @05E3C
    pop dx ; @05E3E
    mov cx,[si] ; @05E3F
    sub cx,byte +0x8 ; @05E41
    shr cx,1 ; @05E44
    shr cx,1 ; @05E46
    shr cx,1 ; @05E48
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @05E4A
    add di,0x4a40 ; @05E4C
    pop ax ; @05E50
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @05E51
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @05E53
    db 0x03,0xc3 ; ENCODED: add ax,bx (NASM chooses a different encoding) ; @05E55
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @05E57
    pop cx ; @05E59
    push si ; @05E5A
    mov ax,[si] ; @05E5B
    sub ax,0x8 ; @05E5D
    and ax,0x7 ; @05E60
    shl ax,1 ; @05E63
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @05E65
    shl ax,1 ; @05E67
    shl ax,1 ; @05E69
    shl ax,1 ; @05E6B
    shl ax,1 ; @05E6D
    shl ax,1 ; @05E6F
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @05E71
    add si,0xc60 ; @05E73
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @05E77
    push ds ; @05E79
    mov ds,[GeneratedGraphicsBufferSegment-GameDataImage] ; @05E7A
    cli ; @05E7E
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_5E7F:
    lodsw ; @05E7F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @05E80
    mov ah,[es:di] ; @05E82
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05E85
    mov al,0x8 ; @05E87
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @05E89
    out dx,ax ; @05E8D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05E8E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05E90
    mov ah,[es:di] ; @05E91
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @05E94
    mov al,0x8 ; @05E96
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @05E98
    out dx,ax ; @05E9C
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05E9D
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05E9F
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @05EA0
    mov ah,[es:di] ; @05EA1
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05EA4
    mov al,0x8 ; @05EA6
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @05EA8
    out dx,ax ; @05EAC
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05EAD
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05EAF
    add di,0xcd ; @05EB0
    loop loc_5E7F ; @05EB4
    sti ; @05EB6
    pop ds ; @05EB7
    pop si ; @05EB8
loc_5EB9:
    ret ; @05EB9
; 5EBA..5F0E: exchange 3 VGA read bytes for original BH/BL/CL masks.
; GC0=0, GC1=0F, GC3=0 (replace/rotate0) via live SS mirrors, then CLI.
; Incoming GC mode/SEQ mask/compare/care stay live; reads load VGA latches.
; Each read precedes its mask mirror/OUT08 and DF-sensitive STOSB.
; BX returns first/second read bytes; CL third, CH unchanged; AH=AL=last mask.
; ES=A000, DX=03CE, DI+=3 or-3, flags from XORAX0 plus unconditional STI.
; RET reads actual SS:SP after all writes, including mirror/VGA aliases.
ExchangeThreeEntityPixelBytes:
sub_5EBA:
    mov dx,0x3ce ; @05EBA
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05EBD
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @05EBF
    out dx,ax ; @05EC3
    mov ax,0xf01 ; @05EC4
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @05EC7
    out dx,ax ; @05ECB
    mov ax,0x3 ; @05ECC
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @05ECF
    out dx,ax ; @05ED3
    mov ax,0xa000 ; @05ED4
    mov es,ax ; @05ED7
    cli ; @05ED9
    mov al,[es:di] ; @05EDA
    xchg bh,al ; @05EDD
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05EDF
    mov al,0x8 ; @05EE1
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @05EE3
    out dx,ax ; @05EE7
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05EE8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05EEA
    mov al,[es:di] ; @05EEB
    xchg bl,al ; @05EEE
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05EF0
    mov al,0x8 ; @05EF2
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @05EF4
    out dx,ax ; @05EF8
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05EF9
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05EFB
    mov al,[es:di] ; @05EFC
    xchg cl,al ; @05EFF
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @05F01
    mov al,0x8 ; @05F03
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @05F05
    out dx,ax ; @05F09
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F0A
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05F0C
    sti ; @05F0D
    ret ; @05F0E
; 5F0F..5FAB: temporary record-coordinate stroke through plane3.
; CLI; SEQ2=08, GC0=08, GC1=08, GC3=00 via live SS mirrors.
; PUSH original Y, X; reread X and add +4 field, subtract4 if +27 byte negative.
; Store temporary X, PUSH it, DEC live Y, CALL5DC6; actualRET may be changed.
; Restore coordinates from live popped words, not cached record values.
; Shift BX=00FC/DL=0 by popped temporaryX&7; SHR/RCR/LOOP retain flags.
; Three read-latch/maskOUT/STOSB writes retain DF and SS/VGA alias order.
; Tail SEQ2=0F and unconditional STI. Actual outerRET follows all writes.
; Child bus contract and changed-target boundary: entity-stroke.md.
DrawEntityStroke:
sub_5F0F:
    cli ; @05F0F
    mov dx,0x3c4 ; @05F10
    mov ax,0x802 ; @05F13
    mov [ss:0x8],ax ; @05F16
    out dx,ax ; @05F1A
    mov dx,0x3ce ; @05F1B
    mov ax,0x800 ; @05F1E
    mov [ss:0xa],ax ; @05F21
    out dx,ax ; @05F25
    mov ax,0x801 ; @05F26
    mov [ss:0xc],ax ; @05F29
    out dx,ax ; @05F2D
    mov ax,0x3 ; @05F2E
    mov [ss:0x2],ax ; @05F31
    out dx,ax ; @05F35
    mov ax,0xa000 ; @05F36
    mov es,ax ; @05F39
    push word [si+0x2] ; @05F3B
    push word [si] ; @05F3E
    mov ax,[si] ; @05F40
    add ax,[si+0x4] ; @05F42
    cmp byte [si+0x27],0x0 ; @05F45
    jns loc_5F4E ; @05F49
    sub ax,0x4 ; @05F4B
loc_5F4E:
    mov [si],ax ; @05F4E
    push ax ; @05F50
    dec word [si+0x2] ; @05F51
    call PrepareEntityPixelSample ; @05F54
    pop cx ; @05F57
    pop word [si] ; @05F58
    pop word [si+0x2] ; @05F5A
    mov bx,0xfc ; @05F5D
    mov dl,0x0 ; @05F60
    and cx,byte +0x7 ; @05F62
    jz loc_5F6D ; @05F65
loc_5F67:
    shr bx,1 ; @05F67
    rcr dl,1 ; @05F69
    loop loc_5F67 ; @05F6B
loc_5F6D:
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @05F6D
    mov dx,0x3ce ; @05F6F
    mov al,[es:di] ; @05F72
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @05F75
    mov al,0x8 ; @05F77
    mov [ss:0xe],ax ; @05F79
    out dx,ax ; @05F7D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F7E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05F80
    mov al,[es:di] ; @05F81
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @05F84
    mov al,0x8 ; @05F86
    mov [ss:0xe],ax ; @05F88
    out dx,ax ; @05F8C
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F8D
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05F8F
    mov al,[es:di] ; @05F90
    db 0x8a,0xe1 ; ENCODED: mov ah,cl (NASM chooses a different encoding) ; @05F93
    mov al,0x8 ; @05F95
    mov [ss:0xe],ax ; @05F97
    out dx,ax ; @05F9B
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @05F9C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @05F9E
    mov dx,0x3c4 ; @05F9F
    mov ax,0xf02 ; @05FA2
    mov [ss:0x8],ax ; @05FA5
    out dx,ax ; @05FA9
    sti ; @05FAA
    ret ; @05FAB
; 5FAC..606A: unchecked incoming AX -> wrapped240*AX saved in live SS word.
; POP BX may change base; +03C0h iff live record[27h]==FFh.
; Mask = base+30*((reread X+record[4])&7), 10 three-byte rows, no clip.
; Destination low(D0h*(Y+record[6]-10h))+((X+record[4])>>3)+4A40h.
; PUSH SI precedes record rereads; PUSH DS precedes live selector read1FE8.
; Source/ES stores follow DF, ADD DI,CDh stays forward; latch/mirror/OUT order
; and incoming VGA state stay live. STI then actual POP DS/SI/RET; BP unchanged.
; Caller28A1 masks its selector into AX0..3; this is not a callee bound.
; Native core/RET adapter verified within bounded bus domains: docs/entity-mask.md.
sub_5FAC:
DrawTenRowEntityMask:
    shl ax,1 ; @05FAC
    shl ax,1 ; @05FAE
    shl ax,1 ; @05FB0
    shl ax,1 ; @05FB2
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @05FB4
    shl ax,1 ; @05FB6
    shl ax,1 ; @05FB8
    shl ax,1 ; @05FBA
    shl ax,1 ; @05FBC
    db 0x2b,0xc2 ; ENCODED: sub ax,dx (NASM chooses a different encoding) ; @05FBE
    push ax ; @05FC0
    mov dx,0x3ce ; @05FC1
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @05FC4
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @05FC6
    out dx,ax ; @05FCA
    mov ax,0xf01 ; @05FCB
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @05FCE
    out dx,ax ; @05FD2
    mov ax,0x3 ; @05FD3
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @05FD6
    out dx,ax ; @05FDA
    mov ax,0xa000 ; @05FDB
    mov es,ax ; @05FDE
    mov di,[si+0x2] ; @05FE0
    add di,[si+0x6] ; @05FE3
    sub di,byte +0x10 ; @05FE6
    mov ax,0xd0 ; @05FE9
    push dx ; @05FEC
    mul di ; @05FED
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @05FEF
    pop dx ; @05FF1
    mov cx,[si] ; @05FF2
    add cx,[si+0x4] ; @05FF4
    shr cx,1 ; @05FF7
    shr cx,1 ; @05FF9
    shr cx,1 ; @05FFB
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @05FFD
    add di,0x4a40 ; @05FFF
    pop bx ; @06003
    push si ; @06004
    cmp byte [si+0x27],0xff ; @06005
    jnz loc_600F ; @06009
    add bx,0x3c0 ; @0600B
loc_600F:
    mov ax,[si] ; @0600F
    add ax,[si+0x4] ; @06011
    and ax,0x7 ; @06014
    shl ax,1 ; @06017
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06019
    shl si,1 ; @0601B
    shl si,1 ; @0601D
    shl si,1 ; @0601F
    shl si,1 ; @06021
    db 0x2b,0xf0 ; ENCODED: sub si,ax (NASM chooses a different encoding) ; @06023
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @06025
    push ds ; @06027
    mov ds,[GeneratedGraphicsBufferSegment-GameDataImage] ; @06028
    mov cx,0xa ; @0602C
    cli ; @0602F
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_6030:
    lodsw ; @06030
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06031
    mov ah,[es:di] ; @06033
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @06036
    mov al,0x8 ; @06038
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @0603A
    out dx,ax ; @0603E
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0603F
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06041
    mov ah,[es:di] ; @06042
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06045
    mov al,0x8 ; @06047
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @06049
    out dx,ax ; @0604D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0604E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06050
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06051
    mov ah,[es:di] ; @06052
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @06055
    mov al,0x8 ; @06057
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @06059
    out dx,ax ; @0605D
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0605E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06060
    add di,0xcd ; @06061
    loop loc_6030 ; @06065
    sti ; @06067
    pop ds ; @06068
    pop si ; @06069
    ret ; @0606A
; 606B..6140: unchecked AX -> wrapped312*AX+0780h saved in live SS word.
; POP BX may change base; +0270h iff record[27h]==FFh; then39*(sum&7).
; sum startsX; if record[28h]==2, INC localY and add CBW(record[27h]) tosum;
; add record[4], store BP=sum before logicalSHR3. BP returns(sum&7), not saved.
; Destination low(D0h*(adjustedY+record[6]-10h))+(sum>>3)+4A40h.
; 13 three-byte rows, no clip; live DX/DS/SI/RET saves and VGA/DF ordering
; match the ten-row sibling. The signed JL at2B58 admits other AX values;
; intended AX0..1 is not a proven caller-state invariant or a callee bound.
; Native core/RET adapter verified within bounded bus domains: docs/entity-mask.md.
sub_606B:
DrawThirteenRowEntityMask:
    shl ax,1 ; @0606B
    shl ax,1 ; @0606D
    shl ax,1 ; @0606F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06071
    shl ax,1 ; @06073
    shl ax,1 ; @06075
    shl ax,1 ; @06077
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @06079
    shl ax,1 ; @0607B
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0607D
    shl ax,1 ; @0607F
    shl ax,1 ; @06081
    db 0x2b,0xc3 ; ENCODED: sub ax,bx (NASM chooses a different encoding) ; @06083
    add ax,0x780 ; @06085
    push ax ; @06088
    mov dx,0x3ce ; @06089
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0608C
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @0608E
    out dx,ax ; @06092
    mov ax,0xf01 ; @06093
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @06096
    out dx,ax ; @0609A
    mov ax,0x3 ; @0609B
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @0609E
    out dx,ax ; @060A2
    mov ax,0xa000 ; @060A3
    mov es,ax ; @060A6
    mov cx,[si] ; @060A8
    mov di,[si+0x2] ; @060AA
    cmp byte [si+0x28],0x2 ; @060AD
    jnz loc_60BA ; @060B1
    inc di ; @060B3
    mov al,[si+0x27] ; @060B4
    cbw ; @060B7
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @060B8
loc_60BA:
    add di,[si+0x6] ; @060BA
    sub di,byte +0x10 ; @060BD
    mov ax,0xd0 ; @060C0
    push dx ; @060C3
    mul di ; @060C4
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @060C6
    pop dx ; @060C8
    add cx,[si+0x4] ; @060C9
    db 0x8b,0xe9 ; ENCODED: mov bp,cx (NASM chooses a different encoding) ; @060CC
    shr cx,1 ; @060CE
    shr cx,1 ; @060D0
    shr cx,1 ; @060D2
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @060D4
    add di,0x4a40 ; @060D6
    pop bx ; @060DA
    push si ; @060DB
    cmp byte [si+0x27],0xff ; @060DC
    jnz loc_60E6 ; @060E0
    add bx,0x270 ; @060E2
loc_60E6:
    and bp,byte +0x7 ; @060E6
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @060E9
    shl si,1 ; @060EB
    shl si,1 ; @060ED
    shl si,1 ; @060EF
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @060F1
    db 0x2b,0xcd ; ENCODED: sub cx,bp (NASM chooses a different encoding) ; @060F3
    shl si,1 ; @060F5
    shl si,1 ; @060F7
    db 0x03,0xf1 ; ENCODED: add si,cx (NASM chooses a different encoding) ; @060F9
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @060FB
    push ds ; @060FD
    mov ds,[GeneratedGraphicsBufferSegment-GameDataImage] ; @060FE
    mov cx,0xd ; @06102
    cli ; @06105
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_6106:
    lodsw ; @06106
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06107
    mov ah,[es:di] ; @06109
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0610C
    mov al,0x8 ; @0610E
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @06110
    out dx,ax ; @06114
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06115
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06117
    mov ah,[es:di] ; @06118
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @0611B
    mov al,0x8 ; @0611D
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @0611F
    out dx,ax ; @06123
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06124
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06126
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @06127
    mov ah,[es:di] ; @06128
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0612B
    mov al,0x8 ; @0612D
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @0612F
    out dx,ax ; @06133
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @06134
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06136
    add di,0xcd ; @06137
    loop loc_6106 ; @0613B
    sti ; @0613D
    pop ds ; @0613E
    pop si ; @0613F
    ret ; @06140
; 6141..616F: coordinate input BX=Y,CX=X, unlike record-based5DC6.
; Save BX/CX in live SS before SUB DI,10h; no negative-Y clamp.
; ES=A000, DI=low(D0h*(Y-10h))+(X>>3)+4A40h, offsets wrap16bits.
; Original CX supplies DS PixelBitMasks[X&7]; AH=live mask, AL=low product.
; DX/CX/BX restore actual SS words, in that order. SI/BP/DS/SS unchanged.
; Flags from ADD BX,PixelBitMasks; IF/DF unchanged; RET consumes actual word.
; Optional bus preserves DS/SS/device aliases. Full contract: coordinate-pixel.md.
sub_6141:
PrepareCoordinatePixelSample:
    push bx ; @06141
    push cx ; @06142
    mov ax,0xa000 ; @06143
    mov es,ax ; @06146
    db 0x8b,0xfb ; ENCODED: mov di,bx (NASM chooses a different encoding) ; @06148
    sub di,byte +0x10 ; @0614A
    push dx ; @0614D
    mov ax,0xd0 ; @0614E
    mul di ; @06151
    pop dx ; @06153
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @06154
    db 0x8b,0xd9 ; ENCODED: mov bx,cx (NASM chooses a different encoding) ; @06156
    shr cx,1 ; @06158
    shr cx,1 ; @0615A
    shr cx,1 ; @0615C
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @0615E
    add di,0x4a40 ; @06160
    and bx,byte +0x7 ; @06164
    add bx,PixelBitMasks-GameDataImage ; @06167
    mov ah,[bx] ; @0616B
    pop cx ; @0616D
    pop bx ; @0616E
    ret ; @0616F
