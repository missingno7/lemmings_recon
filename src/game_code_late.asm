; Maintained image span 03944..0796E; mixed ownership remains provisional.
sub_3944:
    cmp byte [0x2b],0xff ; @03944
    jz loc_394E ; @03949
    jmp loc_7C0A ; @0394B
loc_394E:
    ret ; @0394E
; LEVEL-DISPLAY REBUILD: native composition preserves live DS/ES/SS and actual
; near/far frames through initialization,special/terrain,copy and object drawing.
;126 decoded bytes/50 sites;UNKNOWN395E stays excluded. Tests retain ordinary-RAM
; special input/heap/stack,intact internal returns,DOS/VGA and IRQ seams;
; docs/level-redraw.md. This is not native gameplay/platform closure.
RedrawLevel:
    call InitializeLevelDrawing ; @0394F
LevelRedrawAfterInitialize:
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @03952
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @03955
    jz RedrawLevelTerrainStream ; @03957
    call SetupSpecialGraphicsResource ; @03959
LevelRedrawAfterSpecial:
    jmp short RedrawTerrainFinished ; @0395C
; UNKNOWN: unresolved bytes
    db 0x90 ; @0395E
; TERRAIN STREAM: four separate BEbyte reads,liveSI+4,FFFF sentinel; no400record limit.
; Child7C67 preserves or changes liveiterator/segments/returnwords; expose changedtargets.
RedrawLevelTerrainStream:
    mov si,LevelTerrainDefinitions-GameDataImage ; @0395F
RedrawTerrainCommand:
    mov ah,[si] ; @03962
    mov al,[si+0x1] ; @03964
    mov bh,[si+0x2] ; @03967
    mov bl,[si+0x3] ; @0396A
    add si,byte +0x4 ; @0396D
    cmp ax,0xffff ; @03970
    jz RedrawTerrainFinished ; @03973
RedrawTerrainPieceCall:
    call DrawPackedTerrainPiece ; @03975
RedrawTerrainAfterPiece:
    jmp short RedrawTerrainCommand ; @03978
RedrawTerrainFinished:
    call CopyLevelObjectGraphicsRecords ; @0397A
; OBJECT SUFFIX: BE X/Y/flags,byte dimensions,LE mask/frame offsets;
; bit0 always cleared. PUSH CX/DI/SI and far-return words stay live on SS.
; Child DS/ES and restored cursors/count control later iterations;no fixed32 cap.
; Core stops before own RET or changed child target;docs/object-drawing.md.
DrawLevelObjects:
    lea si,[LevelObjectGraphicsRecords-GameDataImage] ; @0397D
    lea di,[LevelObjectDefinitions-GameDataImage] ; @03981
    mov cx,0x20 ; @03985
    mov ax,[LevelGraphicsSegment-GameDataImage] ; @03988
    mov [GraphicsResourceSegment-GameDataImage],ax ; @0398B
LevelObjectsLoop:
    mov ah,[di] ; @0398E
    mov al,[di+0x1] ; @03990
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @03993
    jz LevelObjectsNext ; @03995
    push cx ; @03997
    push di ; @03998
    push si ; @03999
    ; Forward field equates need explicit byte displacements at NASM -O0.
    mov bh,[byte di+FirstObjectDefinitionY-LevelObjectDefinitions] ; @0399A
    mov bl,[byte di+FirstObjectDefinitionY+1-LevelObjectDefinitions] ; @0399D
    mov dh,[byte di+FirstObjectDefinitionFlags-LevelObjectDefinitions] ; @039A0
    mov dl,[byte di+FirstObjectDefinitionFlags+1-LevelObjectDefinitions] ; @039A3
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @039A6
    and bp,byte -0x2 ; @039A8
    mov dl,[byte si+FirstObjectGraphicsWidth-LevelObjectGraphicsRecords] ; @039AB
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @039AE
    mov cl,[byte si+FirstObjectGraphicsHeight-LevelObjectGraphicsRecords] ; @039B0
    mov di,[byte si+FirstObjectGraphicsMaskOffset-LevelObjectGraphicsRecords] ; @039B3
    mov si,[byte si+FirstObjectGraphicsFrameOffset-LevelObjectGraphicsRecords] ; @039B6
    db 0x03,0xfe ; ENCODED: add di,si (NASM chooses a different encoding) ; @039B9
    mov ch,0x4 ; @039BB
    call 0x0:0x8822 ; @039BD
LevelObjectsAfterBitmap:
    pop si ; @039C2
    pop di ; @039C3
    pop cx ; @039C4
LevelObjectsNext:
    add di,byte +0x8 ; @039C5
    add si,byte +0x1c ; @039C8
    loop LevelObjectsLoop ; @039CB
LevelObjectsReturn:
    ret ; @039CD
sub_39CE:
    call sub_75EF ; @039CE
    mov byte [EntityCreationCountdown-GameDataImage],0x14 ; @039D1
    mov al,0x63 ; @039D6
    sub al,[0x67] ; @039D8
    shr al,1 ; @039DC
    neg al ; @039DE
    add al,0x35 ; @039E0
    neg al ; @039E2
    add al,0x39 ; @039E4
    mov [EntityCreationReload-GameDataImage],al ; @039E6
    mov byte [0x66],0x0 ; @039E9
    mov byte [0x69],0x0 ; @039EE
    mov byte [LevelActionCountRefreshCounter2-GameDataImage],0x0 ; @039F3
    mov byte [LevelActionCountRefreshCounter7-GameDataImage],0x0 ; @039F8
    mov byte [LevelActionCountRefreshCounter0-GameDataImage],0x0 ; @039FD
    mov byte [LevelActionCountRefreshCounter4-GameDataImage],0x0 ; @03A02
    mov byte [LevelActionCountRefreshCounter3-GameDataImage],0x0 ; @03A07
    mov byte [LevelActionCountRefreshCounter5-GameDataImage],0x0 ; @03A0C
    mov byte [LevelActionCountRefreshCounter1-GameDataImage],0x0 ; @03A11
    mov byte [LevelActionCountRefreshCounter6-GameDataImage],0x0 ; @03A16
    mov byte [0x84],0x0 ; @03A1B
    mov byte [0x65],0xff ; @03A20
    mov byte [0x68],0xff ; @03A25
    mov byte [LevelActionCountDisplaySnapshot2-GameDataImage],0xff ; @03A2A
    mov byte [LevelActionCountDisplaySnapshot7-GameDataImage],0xff ; @03A2F
    mov byte [LevelActionCountDisplaySnapshot0-GameDataImage],0xff ; @03A34
    mov byte [LevelActionCountDisplaySnapshot4-GameDataImage],0xff ; @03A39
    mov byte [LevelActionCountDisplaySnapshot3-GameDataImage],0xff ; @03A3E
    mov byte [LevelActionCountDisplaySnapshot5-GameDataImage],0xff ; @03A43
    mov byte [LevelActionCountDisplaySnapshot1-GameDataImage],0xff ; @03A48
    mov byte [LevelActionCountDisplaySnapshot6-GameDataImage],0xff ; @03A4D
    mov byte [0x83],0x3 ; @03A52
    mov ah,[0x64] ; @03A57
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @03A5B
    call sub_762A ; @03A5D
    mov ah,[0x67] ; @03A60
    mov al,0x1 ; @03A64
    call sub_762A ; @03A66
    mov ah,[LevelActionCount2-GameDataImage] ; @03A69
    mov al,0x4 ; @03A6D
    call sub_762A ; @03A6F
    mov ah,[LevelActionCount7-GameDataImage] ; @03A72
    mov al,0x9 ; @03A76
    call sub_762A ; @03A78
    mov ah,[LevelActionCount0-GameDataImage] ; @03A7B
    mov al,0x2 ; @03A7F
    call sub_762A ; @03A81
    mov ah,[LevelActionCount4-GameDataImage] ; @03A84
    mov al,0x6 ; @03A88
    call sub_762A ; @03A8A
    mov ah,[LevelActionCount3-GameDataImage] ; @03A8D
    mov al,0x5 ; @03A91
    call sub_762A ; @03A93
    mov ah,[LevelActionCount5-GameDataImage] ; @03A96
    mov al,0x7 ; @03A9A
    call sub_762A ; @03A9C
    mov ah,[LevelActionCount1-GameDataImage] ; @03A9F
    mov al,0x3 ; @03AA3
    call sub_762A ; @03AA5
    mov ah,[LevelActionCount6-GameDataImage] ; @03AA8
    mov al,0x8 ; @03AAC
    call sub_762A ; @03AAE
    mov al,[0x45] ; @03AB1
    mov si,0x2095 ; @03AB4
    call sub_4B68 ; @03AB7
    mov si,0x209d ; @03ABA
    mov byte [si-0x1],0x20 ; @03ABD
    mov al,[EntityActionSelector-GameDataImage] ; @03AC1
    call sub_780D ; @03AC4
    ret ; @03AC7
sub_3AC8:
    call UpdateMinimapColumn ; @03AC8
    call sub_7A5A ; @03ACB
    mov al,[EntityCompletionCounter-GameDataImage] ; @03ACE
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03AD1
    shl ax,1 ; @03AD3
    shl ax,1 ; @03AD5
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @03AD7
    shl ax,1 ; @03AD9
    shl ax,1 ; @03ADB
    shl ax,1 ; @03ADD
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @03ADF
    shl ax,1 ; @03AE1
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @03AE3
    mov cl,[LevelCreationLimit-GameDataImage] ; @03AE5
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @03AE9
    jz loc_3AEF ; @03AEB
    div cl ; @03AED
loc_3AEF:
    mov si,0x209d ; @03AEF
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03AF2
    mov [0x40],al ; @03AF4
    cmp al,0x64 ; @03AF7
    jnz loc_3B09 ; @03AF9
    mov byte [si-0x1],0x31 ; @03AFB
    mov byte [si],0x30 ; @03AFF
    mov byte [si+0x1],0x30 ; @03B02
    jmp short loc_3B21 ; @03B06
; UNKNOWN: unresolved bytes
    db 0x90 ; @03B08
loc_3B09:
    inc ah ; @03B09
    sub al,0xa ; @03B0B
    jnc loc_3B09 ; @03B0D
    add al,0x3a ; @03B0F
    dec ah ; @03B11
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B13
    jnz loc_3B19 ; @03B15
    mov ah,0xf0 ; @03B17
loc_3B19:
    add ah,0x30 ; @03B19
    mov [si],ah ; @03B1C
    mov [si+0x1],al ; @03B1E
loc_3B21:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03B21
    mov si,0x2083 ; @03B23
    call sub_417B ; @03B26
    mov ah,[EntityActionSelector-GameDataImage] ; @03B29
    cmp [0x83],ah ; @03B2D
    jz loc_3B57 ; @03B31
    mov al,[EntityActionSelector-GameDataImage] ; @03B33
    call sub_780D ; @03B36
    mov al,[0x83] ; @03B39
    call sub_789E ; @03B3C
    cmp byte [0x84],0x2 ; @03B3F
    jnz loc_3B53 ; @03B44
    mov ah,[EntityActionSelector-GameDataImage] ; @03B46
    mov [0x83],ah ; @03B4A
    mov byte [0x84],0xff ; @03B4E
loc_3B53:
    inc byte [0x84] ; @03B53
loc_3B57:
    mov ah,[0x64] ; @03B57
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B5B
    jz loc_3B65 ; @03B5D
    cmp [0x65],ah ; @03B5F
    jz loc_3B7E ; @03B63
loc_3B65:
    cmp byte [0x66],0x2 ; @03B65
    jnz loc_3B75 ; @03B6A
    mov [0x65],ah ; @03B6C
    mov byte [0x66],0xff ; @03B70
loc_3B75:
    inc byte [0x66] ; @03B75
    mov al,0x0 ; @03B79
    call sub_762A ; @03B7B
loc_3B7E:
    mov ah,[0x67] ; @03B7E
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B82
    jz loc_3B8C ; @03B84
    cmp [0x68],ah ; @03B86
    jz loc_3BA5 ; @03B8A
loc_3B8C:
    cmp byte [0x69],0x2 ; @03B8C
    jnz loc_3B9C ; @03B91
    mov [0x68],ah ; @03B93
    mov byte [0x69],0xff ; @03B97
loc_3B9C:
    inc byte [0x69] ; @03B9C
    mov al,0x1 ; @03BA0
    call sub_762A ; @03BA2
loc_3BA5:
    mov ah,[LevelActionCount2-GameDataImage] ; @03BA5
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BA9
    jz loc_3BB3 ; @03BAB
    cmp [LevelActionCountDisplaySnapshot2-GameDataImage],ah ; @03BAD
    jz loc_3BCC ; @03BB1
loc_3BB3:
    cmp byte [LevelActionCountRefreshCounter2-GameDataImage],0x2 ; @03BB3
    jnz loc_3BC3 ; @03BB8
    mov [LevelActionCountDisplaySnapshot2-GameDataImage],ah ; @03BBA
    mov byte [LevelActionCountRefreshCounter2-GameDataImage],0xff ; @03BBE
loc_3BC3:
    inc byte [LevelActionCountRefreshCounter2-GameDataImage] ; @03BC3
    mov al,0x4 ; @03BC7
    call sub_762A ; @03BC9
loc_3BCC:
    mov ah,[LevelActionCount7-GameDataImage] ; @03BCC
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BD0
    jz loc_3BDA ; @03BD2
    cmp [LevelActionCountDisplaySnapshot7-GameDataImage],ah ; @03BD4
    jz loc_3BF3 ; @03BD8
loc_3BDA:
    cmp byte [LevelActionCountRefreshCounter7-GameDataImage],0x2 ; @03BDA
    jnz loc_3BEA ; @03BDF
    mov [LevelActionCountDisplaySnapshot7-GameDataImage],ah ; @03BE1
    mov byte [LevelActionCountRefreshCounter7-GameDataImage],0xff ; @03BE5
loc_3BEA:
    inc byte [LevelActionCountRefreshCounter7-GameDataImage] ; @03BEA
    mov al,0x9 ; @03BEE
    call sub_762A ; @03BF0
loc_3BF3:
    mov ah,[LevelActionCount0-GameDataImage] ; @03BF3
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BF7
    jz loc_3C01 ; @03BF9
    cmp [LevelActionCountDisplaySnapshot0-GameDataImage],ah ; @03BFB
    jz loc_3C1A ; @03BFF
loc_3C01:
    cmp byte [LevelActionCountRefreshCounter0-GameDataImage],0x2 ; @03C01
    jnz loc_3C11 ; @03C06
    mov [LevelActionCountDisplaySnapshot0-GameDataImage],ah ; @03C08
    mov byte [LevelActionCountRefreshCounter0-GameDataImage],0xff ; @03C0C
loc_3C11:
    inc byte [LevelActionCountRefreshCounter0-GameDataImage] ; @03C11
    mov al,0x2 ; @03C15
    call sub_762A ; @03C17
loc_3C1A:
    mov ah,[LevelActionCount4-GameDataImage] ; @03C1A
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C1E
    jz loc_3C28 ; @03C20
    cmp [LevelActionCountDisplaySnapshot4-GameDataImage],ah ; @03C22
    jz loc_3C41 ; @03C26
loc_3C28:
    cmp byte [LevelActionCountRefreshCounter4-GameDataImage],0x2 ; @03C28
    jnz loc_3C38 ; @03C2D
    mov [LevelActionCountDisplaySnapshot4-GameDataImage],ah ; @03C2F
    mov byte [LevelActionCountRefreshCounter4-GameDataImage],0xff ; @03C33
loc_3C38:
    inc byte [LevelActionCountRefreshCounter4-GameDataImage] ; @03C38
    mov al,0x6 ; @03C3C
    call sub_762A ; @03C3E
loc_3C41:
    mov ah,[LevelActionCount3-GameDataImage] ; @03C41
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C45
    jz loc_3C4F ; @03C47
    cmp [LevelActionCountDisplaySnapshot3-GameDataImage],ah ; @03C49
    jz loc_3C68 ; @03C4D
loc_3C4F:
    cmp byte [LevelActionCountRefreshCounter3-GameDataImage],0x2 ; @03C4F
    jnz loc_3C5F ; @03C54
    mov [LevelActionCountDisplaySnapshot3-GameDataImage],ah ; @03C56
    mov byte [LevelActionCountRefreshCounter3-GameDataImage],0xff ; @03C5A
loc_3C5F:
    inc byte [LevelActionCountRefreshCounter3-GameDataImage] ; @03C5F
    mov al,0x5 ; @03C63
    call sub_762A ; @03C65
loc_3C68:
    mov ah,[LevelActionCount5-GameDataImage] ; @03C68
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C6C
    jz loc_3C76 ; @03C6E
    cmp [LevelActionCountDisplaySnapshot5-GameDataImage],ah ; @03C70
    jz loc_3C8F ; @03C74
loc_3C76:
    cmp byte [LevelActionCountRefreshCounter5-GameDataImage],0x2 ; @03C76
    jnz loc_3C86 ; @03C7B
    mov [LevelActionCountDisplaySnapshot5-GameDataImage],ah ; @03C7D
    mov byte [LevelActionCountRefreshCounter5-GameDataImage],0xff ; @03C81
loc_3C86:
    inc byte [LevelActionCountRefreshCounter5-GameDataImage] ; @03C86
    mov al,0x7 ; @03C8A
    call sub_762A ; @03C8C
loc_3C8F:
    mov ah,[LevelActionCount1-GameDataImage] ; @03C8F
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C93
    jz loc_3C9D ; @03C95
    cmp [LevelActionCountDisplaySnapshot1-GameDataImage],ah ; @03C97
    jz loc_3CB6 ; @03C9B
loc_3C9D:
    cmp byte [LevelActionCountRefreshCounter1-GameDataImage],0x2 ; @03C9D
    jnz loc_3CAD ; @03CA2
    mov [LevelActionCountDisplaySnapshot1-GameDataImage],ah ; @03CA4
    mov byte [LevelActionCountRefreshCounter1-GameDataImage],0xff ; @03CA8
loc_3CAD:
    inc byte [LevelActionCountRefreshCounter1-GameDataImage] ; @03CAD
    mov al,0x3 ; @03CB1
    call sub_762A ; @03CB3
loc_3CB6:
    mov ah,[LevelActionCount6-GameDataImage] ; @03CB6
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03CBA
    jz loc_3CC4 ; @03CBC
    cmp [LevelActionCountDisplaySnapshot6-GameDataImage],ah ; @03CBE
    jz loc_3CDD ; @03CC2
loc_3CC4:
    cmp byte [LevelActionCountRefreshCounter6-GameDataImage],0x2 ; @03CC4
    jnz loc_3CD4 ; @03CC9
    mov [LevelActionCountDisplaySnapshot6-GameDataImage],ah ; @03CCB
    mov byte [LevelActionCountRefreshCounter6-GameDataImage],0xff ; @03CCF
loc_3CD4:
    inc byte [LevelActionCountRefreshCounter6-GameDataImage] ; @03CD4
    mov al,0x8 ; @03CD8
    call sub_762A ; @03CDA
loc_3CDD:
    ret ; @03CDD
sub_3CDE:
    mov cl,[0x43] ; @03CDE
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @03CE2
    jnz loc_3CE9 ; @03CE4
    jmp loc_3E62 ; @03CE6
loc_3CE9:
    mov si,0x2083 ; @03CE9
    mov ah,0xb ; @03CEC
loc_3CEE:
    mov byte [si],0x20 ; @03CEE
    inc si ; @03CF1
    dec ah ; @03CF2
    jnz loc_3CEE ; @03CF4
    mov byte [EntityCandidateCount-GameDataImage],0x0 ; @03CF6
    mov byte [0x5e],0xff ; @03CFB
    mov byte [0x60],0xff ; @03D00
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
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D44
loc_3D45:
    db 0x3b,0xdf ; ENCODED: cmp bx,di (NASM chooses a different encoding) ; @03D45
    jnl loc_3D4C ; @03D47
    jmp short loc_3DA5 ; @03D49
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D4B
loc_3D4C:
    add bp,byte +0xc ; @03D4C
    cmp bp,0x680 ; @03D4F
    jnl loc_3D58 ; @03D53
    jmp short loc_3D5B ; @03D55
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D57
loc_3D58:
    mov bp,0xd0 ; @03D58
loc_3D5B:
    add di,byte +0xc ; @03D5B
    cmp di,0xb0 ; @03D5E
    jnl loc_3D67 ; @03D62
    jmp short loc_3D6A ; @03D64
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D66
loc_3D67:
    mov di,0xb0 ; @03D67
loc_3D6A:
    db 0x3b,0xc5 ; ENCODED: cmp ax,bp (NASM chooses a different encoding) ; @03D6A
    jng loc_3D71 ; @03D6C
    jmp short loc_3DA5 ; @03D6E
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D70
loc_3D71:
    db 0x3b,0xdf ; ENCODED: cmp bx,di (NASM chooses a different encoding) ; @03D71
    jng loc_3D78 ; @03D73
    jmp short loc_3DA5 ; @03D75
; UNKNOWN: unresolved bytes
    db 0x90 ; @03D77
loc_3D78:
    push ax ; @03D78
    test byte [si+0x24],0x80 ; @03D79
    jnz loc_3D86 ; @03D7D
    test word [si+0x8],0x8b90 ; @03D7F
    jz loc_3D94 ; @03D84
loc_3D86:
    mov al,[0x43] ; @03D86
    db 0x2a,0xc1 ; ENCODED: sub al,cl (NASM chooses a different encoding) ; @03D89
    mov [0x60],al ; @03D8B
    mov [0x5c],si ; @03D8E
    jmp short loc_3DA0 ; @03D92
loc_3D94:
    mov al,[0x43] ; @03D94
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
    mov byte [0x1a],0x0 ; @03DAF
    mov ax,[InputButtonsWord-GameDataImage] ; @03DB4
    test ax,0x2 ; @03DB7
    jz loc_3DCC ; @03DBA
loc_3DBC:
    mov al,[EntityAlternateSlotIndex-GameDataImage] ; @03DBC
    mov si,[EntityAlternateRecordOffset-GameDataImage] ; @03DBF
    mov [0x5e],al ; @03DC3
    mov [EntitySelectedRecordOffset-GameDataImage],si ; @03DC6
    jmp short loc_3DDE ; @03DCA
loc_3DCC:
    mov al,[0x60] ; @03DCC
    cmp al,0xff ; @03DCF
    jz loc_3DBC ; @03DD1
    mov si,[0x5c] ; @03DD3
    mov [0x5e],al ; @03DD7
    mov [EntitySelectedRecordOffset-GameDataImage],si ; @03DDA
loc_3DDE:
    cmp byte [0x5e],0xff ; @03DDE
    jnz loc_3DE8 ; @03DE3
    jmp short loc_3E62 ; @03DE5
; UNKNOWN: unresolved bytes
    db 0x90 ; @03DE7
loc_3DE8:
    mov byte [0x1a],0xff ; @03DE8
    mov si,0x208b ; @03DED
    mov al,[EntityCandidateCount-GameDataImage] ; @03DF0
    call sub_4B68 ; @03DF3
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
loc_3E62:
    ret ; @03E62
loc_3E63:
    cmp byte [si+0x25],0x0 ; @03E63
    jz loc_3E53 ; @03E67
    lea bx,[0x490c] ; @03E69
    jmp short loc_3E53 ; @03E6D
sub_3E6F:
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @03E6F
    cmp al,0x3b ; @03E72
    jnz loc_3E79 ; @03E74
    jmp loc_4068 ; @03E76
loc_3E79:
    cmp al,0x3c ; @03E79
    jnz loc_3E80 ; @03E7B
    jmp loc_403D ; @03E7D
loc_3E80:
    cmp al,0x4e ; @03E80
    jnz loc_3E87 ; @03E82
    jmp loc_4018 ; @03E84
loc_3E87:
    cmp al,0x57 ; @03E87
    jnz loc_3E8E ; @03E89
    jmp loc_4018 ; @03E8B
loc_3E8E:
    cmp al,0x58 ; @03E8E
    jnz loc_3E95 ; @03E90
    jmp loc_3FEF ; @03E92
loc_3E95:
    cmp al,0x53 ; @03E95
    jnz loc_3E9C ; @03E97
    jmp loc_3FEF ; @03E99
loc_3E9C:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @03E9C
    mov al,0x2 ; @03E9E
    cmp ah,0x3d ; @03EA0
    jnz loc_3EA8 ; @03EA3
    jmp loc_3F5C ; @03EA5
loc_3EA8:
    inc al ; @03EA8
    cmp ah,0x3e ; @03EAA
    jnz loc_3EB2 ; @03EAD
    jmp loc_3F5C ; @03EAF
loc_3EB2:
    inc al ; @03EB2
    cmp ah,0x3f ; @03EB4
    jnz loc_3EBC ; @03EB7
    jmp loc_3F5C ; @03EB9
loc_3EBC:
    inc al ; @03EBC
    cmp ah,0x40 ; @03EBE
    jnz loc_3EC6 ; @03EC1
    jmp loc_3F5C ; @03EC3
loc_3EC6:
    inc al ; @03EC6
    cmp ah,0x41 ; @03EC8
    jnz loc_3ED0 ; @03ECB
    jmp loc_3F5C ; @03ECD
loc_3ED0:
    inc al ; @03ED0
    cmp ah,0x42 ; @03ED2
    jnz loc_3EDA ; @03ED5
    jmp loc_3F5C ; @03ED7
loc_3EDA:
    inc al ; @03EDA
    cmp ah,0x43 ; @03EDC
    jnz loc_3EE4 ; @03EDF
    jmp short loc_3F5C ; @03EE1
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EE3
loc_3EE4:
    inc al ; @03EE4
    cmp ah,0x44 ; @03EE6
    jnz loc_3EEE ; @03EE9
    jmp short loc_3F5C ; @03EEB
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EED
loc_3EEE:
    mov ax,[InputButtonsWord-GameDataImage] ; @03EEE
    test ax,0x1 ; @03EF1
    jnz loc_3EF9 ; @03EF4
    jmp loc_3FE3 ; @03EF6
loc_3EF9:
    mov ax,[0x12] ; @03EF9
    add ax,0x8 ; @03EFC
    cmp ax,0xc0 ; @03EFF
    jnl loc_3F07 ; @03F02
    jmp loc_3FE9 ; @03F04
loc_3F07:
    mov ax,[0x10] ; @03F07
    add ax,0xfff8 ; @03F0A
    cmp ax,0xd0 ; @03F0D
    jl loc_3F15 ; @03F10
    jmp short loc_3F92 ; @03F12
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F14
loc_3F15:
    cmp byte [0x84],0x0 ; @03F15
    jz loc_3F1F ; @03F1A
    jmp loc_3FE9 ; @03F1C
loc_3F1F:
    shr ax,1 ; @03F1F
    shr ax,1 ; @03F21
    shr ax,1 ; @03F23
    shr ax,1 ; @03F25
    cmp al,0x2 ; @03F27
    jnl loc_3F2E ; @03F29
    jmp loc_4032 ; @03F2B
loc_3F2E:
    cmp byte [0x62],0xff ; @03F2E
    jnz loc_3F38 ; @03F33
    jmp loc_3FE9 ; @03F35
loc_3F38:
    mov byte [0x62],0xff ; @03F38
    cmp al,0xa ; @03F3D
    jnz loc_3F44 ; @03F3F
    jmp loc_4018 ; @03F41
loc_3F44:
    cmp al,0xb ; @03F44
    jnz loc_3F4B ; @03F46
    jmp loc_3FEF ; @03F48
loc_3F4B:
    cmp al,0xc ; @03F4B
    jnz loc_3F52 ; @03F4D
    jmp loc_3FEE ; @03F4F
loc_3F52:
    cmp byte [0x2b],0xff ; @03F52
    jnz loc_3F5C ; @03F57
    jmp loc_3FE9 ; @03F59
loc_3F5C:
    cmp byte [0x84],0x0 ; @03F5C
    jz loc_3F66 ; @03F61
    jmp loc_3FE9 ; @03F63
loc_3F66:
    mov [EntityActionSelector-GameDataImage],al ; @03F66
    cmp byte [0x2010],0xff ; @03F69
    jnz loc_3F7C ; @03F6E
    test byte [0x25a7],0x3 ; @03F70
    jz loc_3F7C ; @03F75
    mov ax,0x401 ; @03F77
    int 0x61 ; @03F7A
loc_3F7C:
    cmp byte [0x2010],0xff ; @03F7C
    jz loc_3F8F ; @03F81
    test byte [0x25a7],0x1 ; @03F83
    jz loc_3F8F ; @03F88
    mov ax,0x313 ; @03F8A
    int 0x60 ; @03F8D
loc_3F8F:
    jmp short loc_3FE9 ; @03F8F
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F91
loc_3F92:
    mov byte [0x62],0xff ; @03F92
    cmp byte [0x1fcf],0x0 ; @03F97
    jnz loc_3FEE ; @03F9C
    mov bx,[0x0] ; @03F9E
    shr bx,1 ; @03FA2
    shr bx,1 ; @03FA4
    shr bx,1 ; @03FA6
    shr bx,1 ; @03FA8
    add bx,0xd0 ; @03FAA
    db 0x3b,0xc3 ; ENCODED: cmp ax,bx (NASM chooses a different encoding) ; @03FAE
    jnl loc_3FBE ; @03FB0
    add bx,byte +0x18 ; @03FB2
    db 0x3b,0xc3 ; ENCODED: cmp ax,bx (NASM chooses a different encoding) ; @03FB5
    jl loc_3FBE ; @03FB7
    cmp ax,0xd0 ; @03FB9
    jl loc_3FE9 ; @03FBC
loc_3FBE:
    sub ax,0xda ; @03FBE
    jns loc_3FC5 ; @03FC1
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @03FC3
loc_3FC5:
    cmp ax,0x4f ; @03FC5
    jng loc_3FCD ; @03FC8
    mov ax,0x4f ; @03FCA
loc_3FCD:
    shl ax,1 ; @03FCD
    add ax,0x2 ; @03FCF
    mov [0x2],ax ; @03FD2
    shl ax,1 ; @03FD5
    shl ax,1 ; @03FD7
    shl ax,1 ; @03FD9
    mov [0x0],ax ; @03FDB
    call sub_410F ; @03FDE
    jmp short loc_3FE9 ; @03FE1
loc_3FE3:
    mov byte [0x62],0x0 ; @03FE3
    ret ; @03FE8
loc_3FE9:
    mov byte [0x62],0xff ; @03FE9
loc_3FEE:
    ret ; @03FEE
loc_3FEF:
    cmp byte [0x2b],0xff ; @03FEF
    jz loc_3FEE ; @03FF4
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @03FF6
    mov al,[0x1fd3] ; @03FFB
    mov ah,[0x1fd4] ; @03FFE
    mov [0x1fd4],al ; @04002
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @04005
    cmp al,0x5 ; @04007
    jg loc_3FEE ; @04009
    mov byte [0x4b],0xff ; @0400B
    mov al,[0x43] ; @04010
    mov [LevelCreationLimit-GameDataImage],al ; @04013
    jmp short loc_3FEE ; @04016
loc_4018:
    mov al,[0x52] ; @04018
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @0401B
    sub bl,[0x53] ; @0401D
    cmp bl,0x2 ; @04021
    jnc loc_4028 ; @04024
    jmp short loc_3FEE ; @04026
loc_4028:
    xor byte [0x2b],0xff ; @04028
    mov [0x53],al ; @0402D
    jmp short loc_3FEE ; @04030
loc_4032:
    cmp byte [0x2b],0xff ; @04032
    jz loc_3FEE ; @04037
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04039
    jz loc_4068 ; @0403B
loc_403D:
    cmp byte [0x69],0x0 ; @0403D
    jz loc_4046 ; @04042
    jmp short loc_3FE9 ; @04044
loc_4046:
    cmp byte [0x67],0x63 ; @04046
    jnz loc_404F ; @0404B
    jmp short loc_3FE9 ; @0404D
loc_404F:
    inc byte [0x67] ; @0404F
loc_4053:
    mov al,0x63 ; @04053
    sub al,[0x67] ; @04055
    shr al,1 ; @04059
    neg al ; @0405B
    add al,0x35 ; @0405D
    neg al ; @0405F
    add al,0x39 ; @04061
    mov [EntityCreationReload-GameDataImage],al ; @04063
    jmp short loc_3FE9 ; @04066
loc_4068:
    mov bl,[0x64] ; @04068
    cmp byte [0x69],0x0 ; @0406C
    jz loc_4076 ; @04071
    jmp loc_3FE9 ; @04073
loc_4076:
    cmp [0x67],bl ; @04076
    jnz loc_407F ; @0407A
    jmp loc_3FE9 ; @0407C
loc_407F:
    dec byte [0x67] ; @0407F
    jmp short loc_4053 ; @04083
sub_4085:
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @04085
    cmp al,0x2c ; @04088
    jnz loc_408F ; @0408A
    jmp short loc_40B5 ; @0408C
; UNKNOWN: unresolved bytes
    db 0x90 ; @0408E
loc_408F:
    cmp al,0x2d ; @0408F
    jnz loc_4096 ; @04091
    jmp short loc_40CD ; @04093
; UNKNOWN: unresolved bytes
    db 0x90 ; @04095
loc_4096:
    mov ax,[0x12] ; @04096
    add ax,0x8 ; @04099
    cmp ax,0xc0 ; @0409C
    jnl loc_40B4 ; @0409F
    mov ax,[0x10] ; @040A1
    cmp ax,0x8 ; @040A4
    jnz loc_40AC ; @040A7
    jmp loc_414F ; @040A9
loc_40AC:
    cmp ax,0x148 ; @040AC
    jnz loc_40B4 ; @040AF
    jmp short loc_40E5 ; @040B1
; UNKNOWN: unresolved bytes
    db 0x90 ; @040B3
loc_40B4:
    ret ; @040B4
loc_40B5:
    cmp byte [0x84],0x0 ; @040B5
    jnz loc_40CC ; @040BA
    dec byte [EntityActionSelector-GameDataImage] ; @040BC
    cmp byte [EntityActionSelector-GameDataImage],0x1 ; @040C0
    jnz loc_40CC ; @040C5
    mov byte [EntityActionSelector-GameDataImage],0x9 ; @040C7
loc_40CC:
    ret ; @040CC
loc_40CD:
    cmp byte [0x84],0x0 ; @040CD
    jnz loc_40CC ; @040D2
    inc byte [EntityActionSelector-GameDataImage] ; @040D4
    cmp byte [EntityActionSelector-GameDataImage],0xa ; @040D8
    jnz loc_40CC ; @040DD
    mov byte [EntityActionSelector-GameDataImage],0x2 ; @040DF
    ret ; @040E4
loc_40E5:
    mov ax,[0x0] ; @040E5
    cmp ax,0x500 ; @040E8
    jz sub_410F ; @040EB
    add ax,0x8 ; @040ED
    test word [InputButtonsWord-GameDataImage],0x2 ; @040F0
    jz loc_4100 ; @040F6
    cmp ax,0x500 ; @040F8
    jz loc_4100 ; @040FB
    add ax,0x8 ; @040FD
loc_4100:
    mov [0x0],ax ; @04100
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @04103
    shr dx,1 ; @04105
    shr dx,1 ; @04107
    shr dx,1 ; @04109
    mov [0x2],dx ; @0410B
sub_410F:
    push ds ; @0410F
    pop es ; @04110
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04111
    mov di,0xea8 ; @04113
    mov cx,0x68 ; @04116
    rep stosw ; @04119
    mov di,[0x0] ; @0411B
    shr di,1 ; @0411F
    shr di,1 ; @04121
    shr di,1 ; @04123
    dec di ; @04125
    dec di ; @04126
    add di,0xea8 ; @04127
    mov cx,0x29 ; @0412B
    mov ax,0x101 ; @0412E
    rep stosb ; @04131
    cli ; @04133
    mov ax,es ; @04134
    mov cx,0x143e ; @04136
    mov es,cx ; @04139
    mov bx,[DrawingDirtyCellMapOffset-GameDataImage] ; @0413B
    mov byte [es:bx],0xff ; @0413F
    mov bx,[0x28] ; @04143
    mov byte [es:bx],0xff ; @04147
    mov es,ax ; @0414B
    sti ; @0414D
    ret ; @0414E
loc_414F:
    mov ax,[0x0] ; @0414F
    cmp ax,0x10 ; @04152
    jng loc_4179 ; @04155
    sub ax,0x8 ; @04157
    test word [InputButtonsWord-GameDataImage],0x2 ; @0415A
    jz loc_416A ; @04160
    cmp ax,0x10 ; @04162
    jng loc_4179 ; @04165
    sub ax,0x8 ; @04167
loc_416A:
    mov [0x0],ax ; @0416A
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @0416D
    shr dx,1 ; @0416F
    shr dx,1 ; @04171
    shr dx,1 ; @04173
    mov [0x2],dx ; @04175
loc_4179:
    jmp short sub_410F ; @04179
sub_417B:
    lodsb ; @0417B
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0417C
    jz loc_418B ; @0417E
    push ax ; @04180
    push si ; @04181
    call sub_7708 ; @04182
    pop si ; @04185
    pop ax ; @04186
    inc ah ; @04187
    jmp short sub_417B ; @04189
loc_418B:
    ret ; @0418B
sub_418C:
    cmp byte [0x25a6],0x0 ; @0418C
    jnz loc_4196 ; @04191
    jmp PollMousePosition ; @04193
loc_4196:
    cmp byte [0x25a6],0x1 ; @04196
    jnz loc_41A0 ; @0419B
    jmp loc_42A1 ; @0419D
loc_41A0:
    mov bx,[0x16] ; @041A0
    mov cx,[0x18] ; @041A4
    mov ax,[0x1fc7] ; @041A8
    test ax,0xc03 ; @041AB
    jnz loc_41B5 ; @041AE
    mov cx,0x10 ; @041B0
    jmp short loc_41D1 ; @041B3
loc_41B5:
    test ax,0x401 ; @041B5
    jz loc_41C1 ; @041B8
    sub cx,byte +0x1 ; @041BA
    jns loc_41C1 ; @041BD
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @041BF
loc_41C1:
    test ax,0x802 ; @041C1
    jz loc_41D1 ; @041C4
    add cx,byte +0x1 ; @041C6
    cmp cx,byte +0x20 ; @041C9
    jng loc_41D1 ; @041CC
    mov cx,0x20 ; @041CE
loc_41D1:
    test ax,0x300c ; @041D1
    jnz loc_41DB ; @041D4
    mov bx,0x10 ; @041D6
    jmp short loc_41F7 ; @041D9
loc_41DB:
    test ax,0x1004 ; @041DB
    jz loc_41E7 ; @041DE
    sub bx,byte +0x1 ; @041E0
    jns loc_41E7 ; @041E3
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @041E5
loc_41E7:
    test ax,0x2008 ; @041E7
    jz loc_41F7 ; @041EA
    add bx,byte +0x1 ; @041EC
    cmp bx,byte +0x20 ; @041EF
    jng loc_41F7 ; @041F2
    mov bx,0x20 ; @041F4
loc_41F7:
    mov [0x16],bx ; @041F7
    mov [0x18],cx ; @041FB
    shr bx,1 ; @041FF
    shr cx,1 ; @04201
    shr bx,1 ; @04203
    shr cx,1 ; @04205
    sub bx,byte +0x4 ; @04207
    sub cx,byte +0x4 ; @0420A
    add bx,[0x10] ; @0420D
    cmp bx,byte +0x8 ; @04211
    jg loc_421B ; @04214
    mov bx,0x8 ; @04216
    jmp short loc_4224 ; @04219
loc_421B:
    cmp bx,0x148 ; @0421B
    jng loc_4224 ; @0421F
    mov bx,0x148 ; @04221
loc_4224:
    mov [0x10],bx ; @04224
    add cx,[0x12] ; @04228
    cmp cx,byte +0x8 ; @0422C
    jg loc_4236 ; @0422F
    mov cx,0x8 ; @04231
    jmp short loc_423F ; @04234
loc_4236:
    cmp cx,0xc8 ; @04236
    jng loc_423F ; @0423A
    mov cx,0xc8 ; @0423C
loc_423F:
    mov [0x12],cx ; @0423F
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04243
    test ax,0x4010 ; @04245
    jz loc_424D ; @04248
    or bx,byte +0x1 ; @0424A
loc_424D:
    mov [InputButtonsWord-GameDataImage],bx ; @0424D
    ret ; @04251
PollMousePosition:
    push es ; @04252
    push ds ; @04253
    push bp ; @04254
    push si ; @04255
    push di ; @04256
    push ax ; @04257
    push bx ; @04258
    push cx ; @04259
    push dx ; @0425A
    push ds ; @0425B
    mov ax,0x3 ; @0425C
    int 0x33 ; @0425F
    pop ds ; @04261
    cmp byte [0x200b],0xff ; @04262
    jz loc_426D ; @04267
    mov [InputButtonsWord-GameDataImage],bx ; @04269
loc_426D:
    cmp cx,byte +0x8 ; @0426D
    jnl loc_4275 ; @04270
    mov cx,0x8 ; @04272
loc_4275:
    cmp cx,0x148 ; @04275
    jng loc_427E ; @04279
    mov cx,0x148 ; @0427B
loc_427E:
    mov [0x10],cx ; @0427E
    cmp dx,byte +0x8 ; @04282
    jnl loc_428A ; @04285
    mov dx,0x8 ; @04287
loc_428A:
    cmp dx,0xc8 ; @0428A
    jng loc_4293 ; @0428E
    mov dx,0xc8 ; @04290
loc_4293:
    mov [0x12],dx ; @04293
    pop dx ; @04297
    pop cx ; @04298
    pop bx ; @04299
    pop ax ; @0429A
    pop di ; @0429B
    pop si ; @0429C
    pop bp ; @0429D
    pop ds ; @0429E
    pop es ; @0429F
    ret ; @042A0
loc_42A1:
    mov ax,[InputPollCallback-GameDataImage] ; @042A1
    push dx ; @042A4
    call ax ; @042A5
    pop dx ; @042A7
    cmp dl,0xff ; @042A8
    jnz loc_42B0 ; @042AB
    jmp loc_4333 ; @042AD
loc_42B0:
    sub bx,[0x25a2] ; @042B0
    sub cx,[0x25a4] ; @042B4
    mov al,[0x2005] ; @042B8
    cmp bx,byte +0x8 ; @042BB
    jg loc_42C5 ; @042BE
    cmp bx,byte -0x8 ; @042C0
    jnl loc_42F8 ; @042C3
loc_42C5:
    cmp al,0x2 ; @042C5
    jz loc_42D3 ; @042C7
    cmp al,0x3 ; @042C9
    jz loc_42D7 ; @042CB
    cmp al,0x4 ; @042CD
    jz loc_42D9 ; @042CF
    sar bx,1 ; @042D1
loc_42D3:
    sar bx,1 ; @042D3
    sar bx,1 ; @042D5
loc_42D7:
    sar bx,1 ; @042D7
loc_42D9:
    sar bx,1 ; @042D9
    sar bx,1 ; @042DB
    add bx,[0x10] ; @042DD
    cmp bx,byte +0x8 ; @042E1
    jg loc_42EB ; @042E4
    mov bx,0x8 ; @042E6
    jmp short loc_42F4 ; @042E9
loc_42EB:
    cmp bx,0x148 ; @042EB
    jng loc_42F4 ; @042EF
    mov bx,0x148 ; @042F1
loc_42F4:
    mov [0x10],bx ; @042F4
loc_42F8:
    cmp cx,byte +0x8 ; @042F8
    jg loc_4302 ; @042FB
    cmp cx,byte -0x8 ; @042FD
    jnl loc_4333 ; @04300
loc_4302:
    cmp al,0x2 ; @04302
    jz loc_4310 ; @04304
    cmp al,0x3 ; @04306
    jz loc_4314 ; @04308
    cmp al,0x4 ; @0430A
    jz loc_4316 ; @0430C
    sar cx,1 ; @0430E
loc_4310:
    sar cx,1 ; @04310
    sar cx,1 ; @04312
loc_4314:
    sar cx,1 ; @04314
loc_4316:
    sar cx,1 ; @04316
    add cx,[0x12] ; @04318
    cmp cx,byte +0x8 ; @0431C
    jg loc_4326 ; @0431F
    mov cx,0x8 ; @04321
    jmp short loc_432F ; @04324
loc_4326:
    cmp cx,0xc8 ; @04326
    jng loc_432F ; @0432A
    mov cx,0xc8 ; @0432C
loc_432F:
    mov [0x12],cx ; @0432F
loc_4333:
    ret ; @04333
sub_4334:
    mov byte [0x51],0x3 ; @04334
    cmp dl,0xff ; @04339
    jz loc_4341 ; @0433C
    call sub_4386 ; @0433E
loc_4341:
    cli ; @04341
    mov dx,0x201 ; @04342
    in al,dx ; @04345
    sti ; @04346
    not al ; @04347
    ror al,1 ; @04349
    ror al,1 ; @0434B
    ror al,1 ; @0434D
    ror al,1 ; @0434F
    and al,0x3 ; @04351
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04353
    mov [InputButtonsWord-GameDataImage],ax ; @04355
    ret ; @04358
sub_4359:
    mov byte [0x51],0xc ; @04359
    cmp dl,0xff ; @0435E
    jz loc_436A ; @04361
    call sub_4386 ; @04363
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @04366
    db 0x8b,0xcf ; ENCODED: mov cx,di (NASM chooses a different encoding) ; @04368
loc_436A:
    cli ; @0436A
    mov dx,0x201 ; @0436B
    in al,dx ; @0436E
    sti ; @0436F
    not al ; @04370
    ror al,1 ; @04372
    ror al,1 ; @04374
    ror al,1 ; @04376
    ror al,1 ; @04378
    ror al,1 ; @0437A
    ror al,1 ; @0437C
    and al,0x3 ; @0437E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04380
    mov [InputButtonsWord-GameDataImage],ax ; @04382
    ret ; @04385
sub_4386:
    cli ; @04386
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04387
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @04389
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0438B
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0438D
    mov dx,0x201 ; @0438F
    out dx,al ; @04392
    jmp short loc_4396 ; @04393
; UNKNOWN: unresolved bytes
    db 0x90 ; @04395
loc_4396:
    jmp short loc_4399 ; @04396
; UNKNOWN: unresolved bytes
    db 0x90 ; @04398
loc_4399:
    in al,dx ; @04399
    and al,[0x51] ; @0439A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0439E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @043A0
    and ax,0x1 ; @043A2
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @043A5
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043A7
    and ax,0x2 ; @043A9
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @043AC
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043AE
    and ax,0x4 ; @043B0
    shr ax,1 ; @043B3
    shr ax,1 ; @043B5
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @043B7
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043B9
    and ax,0x8 ; @043BB
    shr ax,1 ; @043BE
    shr ax,1 ; @043C0
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @043C2
    db 0x0b,0xed ; ENCODED: or bp,bp (NASM chooses a different encoding) ; @043C4
    jnz loc_4399 ; @043C6
    sti ; @043C8
    sar cx,1 ; @043C9
    sar di,1 ; @043CB
    ret ; @043CD
sub_43CE:
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @043CE
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @043D1
    jz loc_43D9 ; @043D3
    cmp al,0x77 ; @043D5
    jz loc_43EE ; @043D7
loc_43D9:
    cli ; @043D9
    mov dx,0x201 ; @043DA
    in al,dx ; @043DD
    sti ; @043DE
    not al ; @043DF
    test al,0xf0 ; @043E1
    jz sub_43CE ; @043E3
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @043E5
    test al,0x30 ; @043E7
    jnz loc_43ED ; @043E9
    inc cl ; @043EB
loc_43ED:
    ret ; @043ED
loc_43EE:
    mov cl,0x2 ; @043EE
    jmp short loc_43ED ; @043F0
sub_43F2:
    call SetupDisplayModeAndLayout ; @043F2
    call ClearFullDrawingPage ; @043F5
    call InstallMenuTimerVector ; @043F8
    call sub_53FC ; @043FB
    call sub_4AC5 ; @043FE
loc_4401:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04401
    mov word [AlternateDrawingOrigin-GameDataImage],0x6d60 ; @04407
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @0440D
    call ProgramAlternateDisplayStart ; @04413
    mov byte [0x1f6f],0xff ; @04416
    mov byte [0x1f72],0xff ; @0441B
    mov byte [0x1f70],0x0 ; @04420
    call TransitionPaletteToSlot1 ; @04425
    call ClearFullDrawingPage ; @04428
    call DrawScreenBackground ; @0442B
    call sub_7CBC ; @0442E
    call sub_4FF8 ; @04431
    call sub_4EEF ; @04434
    call sub_4F2B ; @04437
    lea si,[0x4ad9] ; @0443A
    call DrawTextStream ; @0443E
    call sub_4EA2 ; @04441
    call sub_4E37 ; @04444
    call CopyDrawingPageToAlternate ; @04447
    call WaitForDisplayStatusBit3Cycle ; @0444A
    call ProgramAlternateDisplayStart ; @0444D
    call TransitionPaletteToSlot2 ; @04450
loc_4453:
    mov ax,[InputButtonsWord-GameDataImage] ; @04453
    test ax,0x7 ; @04456
    jnz loc_4453 ; @04459
loc_445B:
    call WaitForDisplayStatusBit3Cycle ; @0445B
    call sub_7D0D ; @0445E
    call sub_4F96 ; @04461
    call sub_4EA2 ; @04464
    call sub_4E37 ; @04467
    call SwapDrawingOriginsAndDisplay ; @0446A
    mov ax,[InputButtonsWord-GameDataImage] ; @0446D
    test ax,0x7 ; @04470
    jz loc_4478 ; @04473
    jmp loc_454C ; @04475
loc_4478:
    call sub_4D1A ; @04478
    cmp al,0x80 ; @0447B
    jnz loc_4482 ; @0447D
    jmp loc_454C ; @0447F
loc_4482:
    cmp al,0x81 ; @04482
    jz loc_44AD ; @04484
    cmp al,0x82 ; @04486
    jz loc_44B3 ; @04488
    cmp al,0x83 ; @0448A
    jz loc_44B0 ; @0448C
    cmp al,0x1b ; @0448E
    jnz loc_4495 ; @04490
    jmp loc_04D0 ; @04492
loc_4495:
    cmp al,0x8a ; @04495
    jz loc_44EC ; @04497
    cmp al,0x60 ; @04499
    jz loc_44EC ; @0449B
    cmp al,0x8b ; @0449D
    jnz loc_44A4 ; @0449F
    jmp short loc_451C ; @044A1
; UNKNOWN: unresolved bytes
    db 0x90 ; @044A3
loc_44A4:
    cmp al,0x2d ; @044A4
    jnz loc_44AB ; @044A6
    jmp short loc_451C ; @044A8
; UNKNOWN: unresolved bytes
    db 0x90 ; @044AA
loc_44AB:
    jmp short loc_445B ; @044AB
loc_44AD:
    jmp loc_4967 ; @044AD
loc_44B0:
    jmp loc_4A01 ; @044B0
loc_44B3:
    cmp byte [0x1f72],0x2 ; @044B3
    jz loc_445B ; @044B8
    xor byte [0x1f70],0xff ; @044BA
    mov al,[0x1f71] ; @044BF
    inc al ; @044C2
    mov ah,0x3 ; @044C4
    cmp byte [0x2010],0xff ; @044C6
    jz loc_44CF ; @044CB
    mov ah,0x2 ; @044CD
loc_44CF:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @044CF
    jnz loc_44D5 ; @044D1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @044D3
loc_44D5:
    mov [0x1f71],al ; @044D5
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @044D8
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @044DA
    add bx,0x44e9 ; @044DC
    mov al,[cs:bx] ; @044E0
    mov [0x25a7],al ; @044E3
    jmp loc_445B ; @044E6
; UNKNOWN: unresolved bytes
    db 0x00,0x01,0x03 ; @044E9
loc_44EC:
    cmp byte [0x1f6f],0x4 ; @044EC
    jnz loc_44F6 ; @044F1
    jmp loc_445B ; @044F3
loc_44F6:
    mov al,[0x1f6e] ; @044F6
    cmp al,0x3 ; @044F9
    jnz loc_4500 ; @044FB
    jmp loc_445B ; @044FD
loc_4500:
    inc al ; @04500
    mov [0x1f6e],al ; @04502
    shl al,1 ; @04505
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @04507
    shl al,1 ; @04509
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0450B
    shl al,1 ; @0450D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0450F
    shl al,1 ; @04511
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04513
    mov [LevelResourceSelectionByte-GameDataImage],ah ; @04515
    jmp loc_445B ; @04519
loc_451C:
    cmp byte [0x1f6f],0x4 ; @0451C
    jnz loc_4526 ; @04521
    jmp loc_445B ; @04523
loc_4526:
    mov al,[0x1f6e] ; @04526
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04529
    jnz loc_4530 ; @0452B
    jmp loc_445B ; @0452D
loc_4530:
    dec al ; @04530
    mov [0x1f6e],al ; @04532
    shl al,1 ; @04535
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @04537
    shl al,1 ; @04539
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0453B
    shl al,1 ; @0453D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0453F
    shl al,1 ; @04541
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04543
    mov [LevelResourceSelectionByte-GameDataImage],ah ; @04545
    jmp loc_445B ; @04549
loc_454C:
    mov byte [0x1f6d],0x0 ; @0454C
loc_4551:
    push ds ; @04551
    pop es ; @04552
    mov di,0x0 ; @04553
    mov cx,0xfca ; @04556
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04559
    rep stosb ; @0455B
    call LoadSelectedLevelResources ; @0455D
    call sub_4566 ; @04560
    jmp loc_00FB ; @04563
sub_4566:
    mov al,[0x1f6e] ; @04566
    shl al,1 ; @04569
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0456B
    shl al,1 ; @0456D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0456F
    shl al,1 ; @04571
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04573
    shl al,1 ; @04575
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04577
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @04579
    inc al ; @0457C
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @0457E
    lea si,[0x4b13] ; @04580
    call sub_4BBE ; @04584
    mov al,[0xfce] ; @04587
    lea si,[0x4b50] ; @0458A
    call sub_4B68 ; @0458E
    mov al,[0xfd0] ; @04591
    mov cl,0x64 ; @04594
    mul cl ; @04596
    mov cl,[0xfce] ; @04598
    div cl ; @0459C
    mov [0x41],al ; @0459E
    lea si,[0x4b57] ; @045A1
    call sub_4B5C ; @045A5
    mov al,[0xfcc] ; @045A8
    lea si,[0x4b78] ; @045AB
    call sub_4BBE ; @045AF
    mov al,[0xfd2] ; @045B2
    add al,0x30 ; @045B5
    mov [0x4b83],al ; @045B7
    mov ah,0x73 ; @045BA
    cmp al,0x31 ; @045BC
    jnz loc_45C2 ; @045BE
    mov ah,0x20 ; @045C0
loc_45C2:
    mov [0x4b8b],ah ; @045C2
    lea si,[0x17ab] ; @045C6
    lea di,[0x4b19] ; @045CA
    push ds ; @045CE
    pop es ; @045CF
    mov cx,0x10 ; @045D0
    rep movsw ; @045D3
    mov al,[0x1f6e] ; @045D5
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @045D8
    mov cx,0x6 ; @045DA
    mul cx ; @045DD
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @045DF
    lea si,[0x4b98] ; @045E1
loc_45E5:
    mov al,[bx+0x4c01] ; @045E5
    mov [si],al ; @045E9
    inc bx ; @045EB
    inc si ; @045EC
    loop loc_45E5 ; @045ED
    call ClearFullDrawingPage ; @045EF
loc_45F2:
    mov cx,0x10 ; @045F2
    mov dx,0x10 ; @045F5
    call sub_5329 ; @045F8
    jnz loc_45F2 ; @045FB
    mov al,0x1 ; @045FD
    nop ; @045FF
    call sub_53FE ; @04600
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04603
    mov word [AlternateDrawingOrigin-GameDataImage],0x0 ; @04609
    call SwapDrawingOriginsAndDisplay ; @0460F
    call RedrawLevel ; @04612
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04615
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @0461B
    call sub_7EB2 ; @04621
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04624
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @0462A
    call sub_4C17 ; @04630
    call SetupDisplayLayout ; @04633
    mov bx,0x4e ; @04636
    call DrawScreenBackgroundFromRow ; @04639
    lea si,[0x4b0a] ; @0463C
    call DrawTextStream ; @04640
    lea si,[0x4ba0] ; @04643
    cmp byte [0x25a6],0x0 ; @04647
    jz loc_465D ; @0464C
    lea si,[0x4bc3] ; @0464E
    cmp byte [0x25a6],0x1 ; @04652
    jz loc_465D ; @04657
    lea si,[0x4be5] ; @04659
loc_465D:
    call DrawTextStream ; @0465D
loc_4660:
    mov ax,[InputButtonsWord-GameDataImage] ; @04660
    test ax,0x7 ; @04663
    jnz loc_4660 ; @04666
loc_4668:
    call sub_46B9 ; @04668
    mov al,0x0 ; @0466B
    nop ; @0466D
    call sub_53CA ; @0466E
    mov cx,0x10 ; @04671
    mov dx,0x10 ; @04674
    mov bx,0x302 ; @04677
    nop ; @0467A
    call sub_534B ; @0467B
    jnz loc_4668 ; @0467E
loc_4680:
    call sub_46B9 ; @04680
    mov ax,[InputButtonsWord-GameDataImage] ; @04683
    test ax,0x7 ; @04686
    jnz sub_46A2 ; @04689
    mov ax,[0x1fc7] ; @0468B
    test ax,0x20 ; @0468E
    jnz loc_469B ; @04691
    test ax,0x40 ; @04693
    jz loc_4680 ; @04696
    jmp short sub_46A2 ; @04698
; UNKNOWN: unresolved bytes
    db 0x90 ; @0469A
loc_469B:
    call sub_46A2 ; @0469B
    pop ax ; @0469E
    jmp loc_4401 ; @0469F
sub_46A2:
    call sub_46B9 ; @046A2
    mov al,0x0 ; @046A5
    nop ; @046A7
    call sub_53CA ; @046A8
    mov cx,0x10 ; @046AB
    mov dx,0x10 ; @046AE
    call sub_5329 ; @046B1
    jnz sub_46A2 ; @046B4
    jmp ClearFullDrawingPage ; @046B6
sub_46B9:
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @046B9
    add dl,0x6 ; @046BD
loc_46C0:
    in al,dx ; @046C0
    test al,0x8 ; @046C1
    jz loc_46C0 ; @046C3
loc_46C5:
    in al,dx ; @046C5
    test al,0x8 ; @046C6
    jnz loc_46C5 ; @046C8
    cli ; @046CA
    push dx ; @046CB
    mov al,0x0 ; @046CC
    nop ; @046CE
    call sub_53F6 ; @046CF
    pop dx ; @046D2
    cli ; @046D3
    mov cx,0x3c ; @046D4
loc_46D7:
    in al,dx ; @046D7
    test al,0x1 ; @046D8
    jnz loc_46D7 ; @046DA
loc_46DC:
    in al,dx ; @046DC
    test al,0x1 ; @046DD
    jz loc_46DC ; @046DF
    loop loc_46D7 ; @046E1
    mov al,0x7 ; @046E3
    nop ; @046E5
    call sub_53F6 ; @046E6
    sti ; @046E9
    ret ; @046EA
loc_46EB:
    call ClearFullDrawingPage ; @046EB
    call SetupDisplayModeAndLayout ; @046EE
    call sub_53FC ; @046F1
    call TransitionPaletteToSlot1 ; @046F4
    call ClearFullDrawingPage ; @046F7
    call InstallMenuTimerVector ; @046FA
    call DrawScreenBackground ; @046FD
    call sub_48BD ; @04700
    lea si,[0x4c19] ; @04703
    mov al,[0x20a7] ; @04707
    mov bx,[0x20a9] ; @0470A
    db 0x0a,0xd8 ; ENCODED: or bl,al (NASM chooses a different encoding) ; @0470E
    cmp bx,0x3030 ; @04710
    jz loc_471A ; @04714
    lea si,[0x4c2e] ; @04716
loc_471A:
    call DrawTextStream ; @0471A
    mov al,[0x40] ; @0471D
    cmp al,[0x41] ; @04720
    jnl loc_4729 ; @04724
    jmp short loc_4778 ; @04726
; UNKNOWN: unresolved bytes
    db 0x90 ; @04728
loc_4729:
    mov byte [0x1f6d],0xff ; @04729
    inc byte [LevelResourceSelectionByte-GameDataImage] ; @0472E
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @04732
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04735
    mov cl,0x1e ; @04737
    div cl ; @04739
    mov [0x1f6e],al ; @0473B
    cmp byte [LevelResourceSelectionByte-GameDataImage],0x78 ; @0473E
    jc loc_4748 ; @04743
    jmp loc_47E0 ; @04745
loc_4748:
    call sub_488C ; @04748
    lea si,[0x4d5d] ; @0474B
    call sub_4B68 ; @0474F
    call sub_5042 ; @04752
    lea si,[0x4d3f] ; @04755
    call DrawTextStream ; @04759
    lea bx,[0x4d75] ; @0475C
    cmp byte [0x25a6],0x0 ; @04760
    jz loc_4776 ; @04765
    lea bx,[0x4da0] ; @04767
    cmp byte [0x25a6],0x1 ; @0476B
    jz loc_4776 ; @04770
    lea bx,[0x4dc2] ; @04772
loc_4776:
    jmp short loc_4797 ; @04776
loc_4778:
    mov byte [0x1f6d],0x0 ; @04778
    lea bx,[0x4cd3] ; @0477D
    cmp byte [0x25a6],0x0 ; @04781
    jz loc_4797 ; @04786
    lea bx,[0x4cfe] ; @04788
    cmp byte [0x25a6],0x1 ; @0478C
    jz loc_4797 ; @04791
    lea bx,[0x4d20] ; @04793
loc_4797:
    push bx ; @04797
    call sub_48F6 ; @04798
    pop si ; @0479B
    call DrawTextStream ; @0479C
    mov si,[0x21] ; @0479F
    call DrawTextStream ; @047A3
    call TransitionPaletteToSlot2 ; @047A6
loc_47A9:
    mov ax,[InputButtonsWord-GameDataImage] ; @047A9
    test ax,0x7 ; @047AC
    jnz loc_47A9 ; @047AF
loc_47B1:
    mov ax,[InputButtonsWord-GameDataImage] ; @047B1
    test ax,0x1 ; @047B4
    jnz loc_47D7 ; @047B7
    test ax,0x2 ; @047B9
    jnz loc_47CB ; @047BC
    mov ax,[0x1fc7] ; @047BE
    test ax,0x20 ; @047C1
    jnz loc_47CB ; @047C4
    test ax,0x40 ; @047C6
    jz loc_47B1 ; @047C9
loc_47CB:
    call TransitionPaletteToSlot1 ; @047CB
    call ClearFullDrawingPage ; @047CE
    call SetupDisplayModeAndLayout ; @047D1
    jmp loc_4401 ; @047D4
loc_47D7:
    call TransitionPaletteToSlot1 ; @047D7
    call ClearFullDrawingPage ; @047DA
    jmp loc_4551 ; @047DD
loc_47E0:
    call DrawScreenBackground ; @047E0
    lea si,[0x51cb] ; @047E3
    call DrawTextStream ; @047E7
    lea si,[0x4ba0] ; @047EA
    cmp byte [0x25a6],0x0 ; @047EE
    jz loc_4804 ; @047F3
    lea si,[0x4bc3] ; @047F5
    cmp byte [0x25a6],0x1 ; @047F9
    jz loc_4804 ; @047FE
    lea si,[0x4be5] ; @04800
loc_4804:
    call DrawTextStream ; @04804
    call TransitionPaletteToSlot2 ; @04807
loc_480A:
    mov ax,[InputButtonsWord-GameDataImage] ; @0480A
    test ax,0x7 ; @0480D
    jnz loc_481F ; @04810
    mov ax,[0x1fc7] ; @04812
    test ax,0x20 ; @04815
    jnz loc_481F ; @04818
    test ax,0x40 ; @0481A
    jz loc_480A ; @0481D
loc_481F:
    call TransitionPaletteToSlot1 ; @0481F
    mov byte [LevelResourceSelectionByte-GameDataImage],0x0 ; @04822
    mov byte [0x1f6e],0x0 ; @04827
    jmp loc_4401 ; @0482C
sub_482F:
    cmp byte [0x2010],0x0 ; @0482F
    jz loc_4865 ; @04834
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @04836
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04839
    jz loc_4840 ; @0483B
    jmp short loc_4866 ; @0483D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0483F
loc_4840:
    cmp byte [0x1f6d],0x0 ; @04840
    jz loc_4855 ; @04845
    mov al,[0x1f6c] ; @04847
    inc al ; @0484A
    cmp al,0x11 ; @0484C
    jnz loc_4852 ; @0484E
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04850
loc_4852:
    mov [0x1f6c],al ; @04852
loc_4855:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04855
    push ax ; @04857
    lea bx,[0x4877] ; @04858
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0485C
    mov al,[cs:bx] ; @0485E
    mov [0x54],al ; @04861
    pop ax ; @04864
loc_4865:
    ret ; @04865
loc_4866:
    dec al ; @04866
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04868
    lea bx,[0x4888] ; @0486A
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0486E
    mov al,[cs:bx] ; @04870
    mov [0x54],al ; @04873
    ret ; @04876
; UNKNOWN: unresolved bytes
    db 0x06,0x07,0x08,0x0a,0x0b,0x04,0x0c,0x0d,0x0e,0x0f,0x05,0x10,0x11,0x12,0x13,0x14 ; @04877
; UNKNOWN: unresolved bytes
    db 0x15,0x01,0x09,0x03,0x02 ; @04887
sub_488C:
    push cx ; @0488C
    mov cl,0x1e ; @0488D
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @0488F
    inc al ; @04892
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04894
    div cl ; @04896
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @04898
    mul cl ; @0489A
    mov cl,[LevelResourceSelectionByte-GameDataImage] ; @0489C
    inc cl ; @048A0
    db 0x2a,0xc8 ; ENCODED: sub cl,al (NASM chooses a different encoding) ; @048A2
    db 0x8b,0xc1 ; ENCODED: mov ax,cx (NASM chooses a different encoding) ; @048A4
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @048A6
    jnz loc_48AE ; @048A8
    mov al,0x1e ; @048AA
    dec ah ; @048AC
loc_48AE:
    pop cx ; @048AE
    ret ; @048AF
; UNKNOWN: unresolved bytes
    db 0x51,0xb1,0x1e,0x8a,0xe8,0x8a,0xc4,0xf6,0xe1,0x02,0xc5,0x59,0xc3 ; @048B0
sub_48BD:
    mov al,[0x40] ; @048BD
    lea si,[0x4c5d] ; @048C0
    call sub_4B5C ; @048C4
    mov al,[0x41] ; @048C7
    lea si,[0x4c71] ; @048CA
    call sub_4B5C ; @048CE
    lea si,[0x4c77] ; @048D1
    cmp byte [0x25a6],0x0 ; @048D5
    jz loc_48EB ; @048DA
    lea si,[0x4c9d] ; @048DC
    cmp byte [0x25a6],0x1 ; @048E0
    jz loc_48EB ; @048E5
    lea si,[0x4cb9] ; @048E7
loc_48EB:
    mov [0x21],si ; @048EB
    lea si,[0x4c4e] ; @048EF
    jmp DrawTextStream ; @048F3
sub_48F6:
    mov al,[0x40] ; @048F6
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @048F9
    mov dl,[0x41] ; @048FB
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @048FF
    mov bx,0x10 ; @04901
    cmp ax,0x64 ; @04904
    jz loc_494D ; @04907
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04909
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @0490B
    jz loc_494D ; @0490D
    add bx,byte +0x2 ; @0490F
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04912
    shr cx,1 ; @04914
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04916
    jl loc_494D ; @04918
    add bx,byte +0x2 ; @0491A
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @0491D
    sub cx,byte +0x5 ; @0491F
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04922
    jl loc_494D ; @04924
    add bx,byte +0x2 ; @04926
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04929
    dec cx ; @0492B
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @0492C
    jl loc_494D ; @0492E
    add bx,byte +0x2 ; @04930
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04933
    jz loc_494D ; @04935
    add bx,byte +0x2 ; @04937
    db 0x3b,0xc2 ; ENCODED: cmp ax,dx (NASM chooses a different encoding) ; @0493A
    jz loc_494D ; @0493C
    add bx,byte +0x2 ; @0493E
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04941
    add cx,byte +0x14 ; @04943
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04946
    jl loc_494D ; @04948
    add bx,byte +0x2 ; @0494A
loc_494D:
    mov si,[cs:bx+0x4955] ; @0494D
    jmp DrawTextStream ; @04952
; UNKNOWN: unresolved bytes
    db 0x33,0x4f,0x77,0x4f,0xbc,0x4f,0x03,0x50,0x4e,0x50,0x91,0x50,0xde,0x50,0x2c,0x51 ; @04955
; UNKNOWN: unresolved bytes
    db 0x7a,0x51 ; @04965
loc_4967:
    call ClearFullDrawingPage ; @04967
    call InitializeDisplayOrigins ; @0496A
    call TransitionPaletteToSlot1 ; @0496D
    call ClearFullDrawingPage ; @04970
    call DrawScreenBackground ; @04973
    lea si,[0x4df2] ; @04976
    mov cx,0xa ; @0497A
loc_497D:
    mov byte [si],0x2e ; @0497D
    inc si ; @04980
    loop loc_497D ; @04981
    lea si,[0x4de1] ; @04983
    call DrawTextStream ; @04987
    call CopyDrawingPageToAlternate ; @0498A
    call WaitForDisplayStatusBit3Cycle ; @0498D
    call ProgramAlternateDisplayStart ; @04990
    call TransitionPaletteToSlot2 ; @04993
    call ReadCodeInput ; @04996
    call sub_51A2 ; @04999
    jnz loc_49EC ; @0499C
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @0499E
    call sub_488C ; @049A1
    push ax ; @049A4
    lea si,[0x4e10] ; @049A5
    call sub_4B68 ; @049A9
    pop ax ; @049AC
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @049AD
    lea di,[0x4e1f] ; @049AF
    lea si,[0x4c01] ; @049B3
    push ds ; @049B7
    pop es ; @049B8
    mov cx,0x6 ; @049B9
    mul cl ; @049BC
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @049BE
    rep movsb ; @049C0
    lea si,[0x4dfe] ; @049C2
    call DrawTextStream ; @049C6
    call SwapDrawingOriginsAndDisplay ; @049C9
    mov cx,0x78 ; @049CC
loc_49CF:
    call WaitForDisplayStatusBit3Cycle ; @049CF
    mov ax,[InputButtonsWord-GameDataImage] ; @049D2
    test ax,0x7 ; @049D5
    jnz loc_49E9 ; @049D8
    mov ax,[0x1fc7] ; @049DA
    test ax,0x20 ; @049DD
    jnz loc_49E9 ; @049E0
    test ax,0x40 ; @049E2
    jnz loc_49E9 ; @049E5
    loop loc_49CF ; @049E7
loc_49E9:
    jmp loc_4401 ; @049E9
loc_49EC:
    lea si,[0x4e27] ; @049EC
    call DrawTextStream ; @049F0
    call SwapDrawingOriginsAndDisplay ; @049F3
    mov cx,0x3c ; @049F6
loc_49F9:
    call WaitForDisplayStatusBit3Cycle ; @049F9
    loop loc_49F9 ; @049FC
    jmp loc_4401 ; @049FE
loc_4A01:
    call ClearFullDrawingPage ; @04A01
    call InitializeDisplayOrigins ; @04A04
    call TransitionPaletteToSlot1 ; @04A07
    call DrawScreenBackground ; @04A0A
    lea si,[0x4e3a] ; @04A0D
    call DrawTextStream ; @04A11
    cmp byte [0x1f73],0xff ; @04A14
    jz loc_4A22 ; @04A19
    lea si,[0x4e6e] ; @04A1B
    call DrawTextStream ; @04A1F
loc_4A22:
    call CopyDrawingPageToAlternate ; @04A22
    call WaitForDisplayStatusBit3Cycle ; @04A25
    call ProgramAlternateDisplayStart ; @04A28
    call TransitionPaletteToSlot2 ; @04A2B
loc_4A2E:
    call WaitForDisplayStatusBit3Cycle ; @04A2E
    call sub_4D1A ; @04A31
    cmp byte [0x1f73],0xff ; @04A34
    jz loc_4A3F ; @04A39
    cmp al,0x31 ; @04A3B
    jz short loc_4ABD ; original +126-byte branch; prevent -O0 forward-pass widening ; @04A3D
loc_4A3F:
    cmp al,0x32 ; @04A3F
    jz loc_4A4E ; @04A41
    cmp al,0x33 ; @04A43
    jz loc_4AB5 ; @04A45
    cmp al,0x1b ; @04A47
    jnz loc_4A2E ; @04A49
    jmp loc_4401 ; @04A4B
loc_4A4E:
    lea si,[0x4e85] ; @04A4E
    call DrawTextStream ; @04A52
    call SwapDrawingOriginsAndDisplay ; @04A55
    call sub_43CE ; @04A58
    cmp cl,0x2 ; @04A5B
    jz loc_4AB5 ; @04A5E
    cmp cl,0x1 ; @04A60
    jz loc_4A7D ; @04A63
    mov ax,0x4334 ; @04A65
    mov [InputPollCallback-GameDataImage],ax ; @04A68
    mov al,0x1 ; @04A6B
    mov [0x25a6],al ; @04A6D
    call sub_4334 ; @04A70
    mov [0x25a2],bx ; @04A73
    mov [0x25a4],cx ; @04A77
    jmp short loc_4A95 ; @04A7B
loc_4A7D:
    mov ax,0x4359 ; @04A7D
    mov [InputPollCallback-GameDataImage],ax ; @04A80
    mov al,0x1 ; @04A83
    mov [0x25a6],al ; @04A85
    call sub_4359 ; @04A88
    mov [0x25a2],bx ; @04A8B
    mov [0x25a4],cx ; @04A8F
    jmp short loc_4A95 ; @04A93
loc_4A95:
    lea si,[0x4ea9] ; @04A95
    call DrawTextStream ; @04A99
    call SwapDrawingOriginsAndDisplay ; @04A9C
loc_4A9F:
    call WaitForDisplayStatusBit3Cycle ; @04A9F
    call sub_4D1A ; @04AA2
    cmp al,0x31 ; @04AA5
    jc loc_4A9F ; @04AA7
    cmp al,0x34 ; @04AA9
    ja loc_4A9F ; @04AAB
    sub al,0x30 ; @04AAD
    mov [0x2005],al ; @04AAF
    jmp loc_4401 ; @04AB2
loc_4AB5:
    mov byte [0x25a6],0x2 ; @04AB5
    jmp loc_4401 ; @04ABA
loc_4ABD:
    mov byte [0x25a6],0x0 ; @04ABD
    jmp loc_4401 ; @04AC2
sub_4AC5:
    cmp byte [0x1fde],0xfd ; @04AC5
    jnz loc_4B1B ; @04ACA
    call TransitionPaletteToSlot1 ; @04ACC
loc_4ACF:
    call ClearFullDrawingPage ; @04ACF
    call DrawScreenBackground ; @04AD2
    lea si,[0x4f00] ; @04AD5
    call DrawTextStream ; @04AD9
    call CopyDrawingPageToAlternate ; @04ADC
    call WaitForDisplayStatusBit3Cycle ; @04ADF
    call ProgramAlternateDisplayStart ; @04AE2
    call TransitionPaletteToSlot2 ; @04AE5
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @04AE8
loc_4AED:
    mov ax,[InputButtonsWord-GameDataImage] ; @04AED
    test ax,0x7 ; @04AF0
    jnz loc_4AFD ; @04AF3
    mov ah,[KeyboardScanCodeByte-GameDataImage] ; @04AF5
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04AF9
    jz loc_4AED ; @04AFB
loc_4AFD:
    lea dx,[0x2534] ; @04AFD
    mov ax,0x3d00 ; @04B01
    int 0x21 ; @04B04
    jc loc_4ACF ; @04B06
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @04B08
    mov ah,0x3e ; @04B0A
    int 0x21 ; @04B0C
    jc loc_4ACF ; @04B0E
    call TransitionPaletteToSlot1 ; @04B10
    call ClearFullDrawingPage ; @04B13
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @04B16
loc_4B1B:
    ret ; @04B1B
ShowResourceRetryScreen:
    call SetupDisplayModeAndLayout ; @04B1C
RetryUiAfterSetup:
    call TransitionPaletteToSlot1 ; @04B1F
RetryUiAfterPalette1:
    call ClearFullDrawingPage ; @04B22
RetryUiAfterFirstClear:
    call DrawScreenBackground ; @04B25
RetryUiAfterBackground:
    lea si,[ResourceRetryPromptText-GameDataImage] ; @04B28
    call DrawTextStream ; @04B2C
RetryUiAfterText:
    call CopyDrawingPageToAlternate ; @04B2F
RetryUiAfterCopy:
    call WaitForDisplayStatusBit3Cycle ; @04B32
RetryUiAfterStatus:
    call ProgramAlternateDisplayStart ; @04B35
RetryUiAfterDisplayStart:
    call TransitionPaletteToSlot2 ; @04B38
; CONTRACT: Canonical button word / raw scan-code latch, no CALL/RET frame.
; TEST AX,7 short-circuits scan read; MOV AH retains earlier AL.
; Unbounded original wait, finite providers only in tests; docs/retry-input.md.
RetryInputReset:
RetryUiAfterPalette2:
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @04B3B
WaitForRetryInput:
    mov ax,[InputButtonsWord-GameDataImage] ; @04B40
    test ax,0x7 ; @04B43
    jnz RetryInputReady ; @04B46
    mov ah,[KeyboardScanCodeByte-GameDataImage] ; @04B48
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04B4C
    jz WaitForRetryInput ; @04B4E
RetryInputReady:
    call TransitionPaletteToSlot1 ; @04B50
RetryUiAfterExitPalette:
    call ClearFullDrawingPage ; @04B53
RetryUiAfterFinalClear:
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @04B56
RetryUiReturn:
    ret ; @04B5B
sub_4B5C:
    mov byte [si+0x3],0x20 ; @04B5C
    call sub_4B68 ; @04B60
    mov byte [si],0x25 ; @04B63
    inc si ; @04B66
    ret ; @04B67
sub_4B68:
    mov byte [si],0x20 ; @04B68
    mov byte [si+0x1],0x20 ; @04B6B
    mov byte [si+0x2],0x20 ; @04B6F
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04B73
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @04B75
loc_4B77:
    inc ah ; @04B77
    sub al,0x64 ; @04B79
    jnc loc_4B77 ; @04B7B
    add al,0x64 ; @04B7D
    dec ah ; @04B7F
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04B81
    jnz loc_4B89 ; @04B83
    mov ah,0x20 ; @04B85
    jmp short loc_4B91 ; @04B87
loc_4B89:
    add ah,0x30 ; @04B89
    inc bl ; @04B8C
    mov [si],ah ; @04B8E
    inc si ; @04B90
loc_4B91:
    mov byte [si],0x20 ; @04B91
    mov byte [si+0x1],0x20 ; @04B94
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04B98
loc_4B9A:
    inc ah ; @04B9A
    sub al,0xa ; @04B9C
    jnc loc_4B9A ; @04B9E
    add al,0xa ; @04BA0
    dec ah ; @04BA2
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04BA4
    jnz loc_4BB0 ; @04BA6
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @04BA8
    jnz loc_4BB0 ; @04BAA
    mov ah,0x20 ; @04BAC
    jmp short loc_4BB8 ; @04BAE
loc_4BB0:
    add ah,0x30 ; @04BB0
    inc bl ; @04BB3
    mov [si],ah ; @04BB5
    inc si ; @04BB7
loc_4BB8:
    add al,0x30 ; @04BB8
    mov [si],al ; @04BBA
    inc si ; @04BBC
    ret ; @04BBD
sub_4BBE:
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @04BBE
    jmp short loc_4B91 ; @04BC0
; CONTRACT: AL unsigned byte ->three ASCII digits atDS:SI; incoming AH discarded.
; AX returns tens ASCII inAH, units ASCII inAL; SI advances2 with16-bit wrap.
; Writes are live and increment forwards even withDF set. Other registers/segments
; are unchanged; final ADD AL,30 defines arithmetic flags, preserves control flags.
; Native C and active-return alias checks: tests/decimal_digits_c.py.
; Separate original-only contract check: tests/decimal_digits.py; docs/decimal-digits.md.
WriteDecimalByteDigits:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04BC2
loc_4BC4:
    inc ah ; @04BC4
    sub al,0x64 ; @04BC6
    jnc loc_4BC4 ; @04BC8
    add al,0x64 ; @04BCA
    add ah,0x2f ; @04BCC
    mov [si],ah ; @04BCF
    inc si ; @04BD1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04BD2
loc_4BD4:
    inc ah ; @04BD4
    sub al,0xa ; @04BD6
    jnc loc_4BD4 ; @04BD8
    add al,0xa ; @04BDA
    add ah,0x2f ; @04BDC
    mov [si],ah ; @04BDF
    inc si ; @04BE1
    add al,0x30 ; @04BE2
    mov [si],al ; @04BE4
    ret ; @04BE6
; CONTRACT: CS83BE store precedes CLI/BIOSAX0090; all12returnedCPUfields staylive.
; STI is unconditional. Shared4BF5/4C07 entries skip earlier instructions.
; FarCALL8808 hasrelocation4C14; actualSSfarframe andouterRET remainlive.
; See docs/display-setup.md; no startup/BIOS/timing ownership is inferred.
SetupDisplayModeAndLayout:
    mov byte [cs:ChecksumCursor+3],0xff ; @04BE7
    nop ; @04BED
    cli ; @04BEE
    mov ax,0x90 ; @04BEF
DisplaySetupModeInterrupt:
    int 0x10 ; @04BF2
    sti ; @04BF4
InitializeDisplayOrigins:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04BF5
    mov word [AlternateDrawingOrigin-GameDataImage],0x6d60 ; @04BFB
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @04C01
SetupDisplayLayout:
    mov ax,0x280 ; @04C07
    mov bx,0x15e ; @04C0A
    mov dx,[DrawingOrigin-GameDataImage] ; @04C0D
    call 0x0:SetDrawingLayout ; @04C11
DisplaySetupAfterLayout:
    ret ; @04C16
sub_4C17:
    mov di,0x15e0 ; @04C17
    mov cx,0x5780 ; @04C1A
    jmp ClearVgaBytes ; @04C1D
; CONTRACT: Program liveDrawingOrigin via realCALL4C36, consumeactualchildRET,
; then reread/swap liveorigins. Providers canoverwrite saved/returnwords.
; SharedCLI/output/index0C,index0D/unconditionalSTI contract: docs/display-start.md.
SwapDrawingOriginsAndDisplay:
    mov bx,[DrawingOrigin-GameDataImage] ; @04C20
    call ProgramDisplayStartFromValue ; @04C24
DisplaySwapAfterProgram:
    mov ax,[DrawingOrigin-GameDataImage] ; @04C27
    xchg [AlternateDrawingOrigin-GameDataImage],ax ; @04C2A
    mov [DrawingOrigin-GameDataImage],ax ; @04C2E
DisplaySwapReturn:
    ret ; @04C31
ProgramAlternateDisplayStart:
    mov bx,[AlternateDrawingOrigin-GameDataImage] ; @04C32
ProgramDisplayStartFromValue:
    cli ; @04C36
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @04C37
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @04C3B
    mov al,0xc ; @04C3D
DisplayStartFirstOutput:
    out dx,ax ; @04C3F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @04C40
    inc al ; @04C42
    out dx,ax ; @04C44
    sti ; @04C45
DisplayStartReturn:
    ret ; @04C46
MenuTimerIrqHandler:
    push ax ; @04C47
    push bx ; @04C48
    push cx ; @04C49
    push dx ; @04C4A
    push si ; @04C4B
    push di ; @04C4C
    push bp ; @04C4D
    push ds ; @04C4E
    mov ax,0x9a9 ; @04C4F
    mov ds,ax ; @04C52
    mov al,[0x1fe3] ; @04C54
    inc al ; @04C57
    and al,0x3 ; @04C59
    mov [0x1fe3],al ; @04C5B
    jnz loc_4C66 ; @04C5E
    call sub_18B2 ; @04C60
    jmp short loc_4C70 ; @04C63
; UNKNOWN: unresolved bytes
    db 0x90 ; @04C65
loc_4C66:
    mov ax,0x4c70 ; @04C66
    pushf ; @04C69
    push cs ; @04C6A
    push ax ; @04C6B
    jmp far [SavedTimerVector-GameDataImage] ; @04C6C
loc_4C70:
    mov dl,0xff ; @04C70
    call sub_418C ; @04C72
    pop ds ; @04C75
    pop bp ; @04C76
    pop di ; @04C77
    pop si ; @04C78
    pop dx ; @04C79
    pop cx ; @04C7A
    pop bx ; @04C7B
    pop ax ; @04C7C
    iret ; @04C7D
ReadCodeInput:
    lea si,[0x4df2] ; @04C7E
    mov cx,0xa ; @04C82
    mov bx,0x5a41 ; @04C85
    lea bp,[0x503b] ; @04C88
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04C8C
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @04C8E
    db 0x03,0xd1 ; ENCODED: add dx,cx (NASM chooses a different encoding) ; @04C90
    mov cx,0x5f2e ; @04C92
    mov byte [0x491e],0x14 ; @04C95
loc_4C9A:
    push si ; @04C9A
    push di ; @04C9B
    push bx ; @04C9C
    push cx ; @04C9D
    push dx ; @04C9E
    push bp ; @04C9F
loc_4CA0:
    push di ; @04CA0
    push si ; @04CA1
    push cx ; @04CA2
    push dx ; @04CA3
    push bp ; @04CA4
    call WaitForDisplayStatusBit3Cycle ; @04CA5
    pop bp ; @04CA8
    pop dx ; @04CA9
    pop cx ; @04CAA
    pop si ; @04CAB
    pop di ; @04CAC
    dec byte [0x491e] ; @04CAD
    jnz loc_4CC4 ; @04CB1
    mov byte [0x491e],0x14 ; @04CB3
    mov al,[di] ; @04CB8
    db 0x3a,0xc1 ; ENCODED: cmp al,cl (NASM chooses a different encoding) ; @04CBA
    jz loc_4CC2 ; @04CBC
    mov [di],cl ; @04CBE
    jmp short loc_4CC4 ; @04CC0
loc_4CC2:
    mov [di],ch ; @04CC2
loc_4CC4:
    push di ; @04CC4
    push si ; @04CC5
    push cx ; @04CC6
    push dx ; @04CC7
    push bp ; @04CC8
    call bp ; @04CC9
    call SwapDrawingOriginsAndDisplay ; @04CCB
    call sub_4D1A ; @04CCE
    pop bp ; @04CD1
    pop dx ; @04CD2
    pop cx ; @04CD3
    pop si ; @04CD4
    pop di ; @04CD5
    cmp al,0xff ; @04CD6
    jz loc_4CA0 ; @04CD8
    pop bp ; @04CDA
    pop dx ; @04CDB
    pop cx ; @04CDC
    pop bx ; @04CDD
    pop di ; @04CDE
    pop si ; @04CDF
    cmp al,0x7f ; @04CE0
    jz loc_4D02 ; @04CE2
    cmp al,0xd ; @04CE4
    jz loc_4D10 ; @04CE6
    db 0x3a,0xc3 ; ENCODED: cmp al,bl (NASM chooses a different encoding) ; @04CE8
    jl loc_4C9A ; @04CEA
    db 0x3a,0xc7 ; ENCODED: cmp al,bh (NASM chooses a different encoding) ; @04CEC
    jg loc_4C9A ; @04CEE
    db 0x3b,0xfa ; ENCODED: cmp di,dx (NASM chooses a different encoding) ; @04CF0
    jz loc_4C9A ; @04CF2
    mov [di],al ; @04CF4
    inc di ; @04CF6
    mov cl,[di] ; @04CF7
    db 0x3b,0xfa ; ENCODED: cmp di,dx (NASM chooses a different encoding) ; @04CF9
    jnz loc_4C9A ; @04CFB
    dec di ; @04CFD
    mov cl,[di] ; @04CFE
    jmp short loc_4C9A ; @04D00
loc_4D02:
    mov byte [di],0x2e ; @04D02
    mov cl,0x2e ; @04D05
    db 0x3b,0xfe ; ENCODED: cmp di,si (NASM chooses a different encoding) ; @04D07
    jz loc_4C9A ; @04D09
    dec di ; @04D0B
    mov cl,[di] ; @04D0C
    jmp short loc_4C9A ; @04D0E
loc_4D10:
    mov word [0x1fc7],0x0 ; @04D10
    mov [di],cl ; @04D16
    jmp bp ; @04D18
sub_4D1A:
    lea si,[0xf78] ; @04D1A
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04D1E
    mov cx,0x53 ; @04D20
loc_4D23:
    test byte [bx+si],0x80 ; @04D23
    jnz loc_4D2E ; @04D26
loc_4D28:
    inc bx ; @04D28
    loop loc_4D23 ; @04D29
    mov al,0xff ; @04D2B
    ret ; @04D2D
loc_4D2E:
    mov al,[bx+si] ; @04D2E
    and al,0x7f ; @04D30
    dec al ; @04D32
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D34
    jz loc_4D42 ; @04D36
    or al,0x80 ; @04D38
    mov [bx+si],al ; @04D3A
    cmp al,0x93 ; @04D3C
    jz loc_4D45 ; @04D3E
    jmp short loc_4D28 ; @04D40
loc_4D42:
    mov byte [bx+si],0x86 ; @04D42
loc_4D45:
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @04D45
    lea bx,[0x202e] ; @04D47
    xlatb ; @04D4B
    ret ; @04D4C
; Stream uses live DS:SI and incoming DF. Header: column(1-based), row, style.
; Header column0 terminates; style0=>BP2 elseBP0. Only CR ends each text run.
; Zero inside a run is a glyph. Save CX/BX/SI, consume actual glyph nearRET,
; then live POP SI/BX/CX and byte INC CL. Child DS/ES and frame aliases flow.
DrawTextStream:
    lodsb ; @04D4D
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D4E
    jz TextStreamReturn ; @04D50
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @04D52
    dec cl ; @04D54
    lodsb ; @04D56
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @04D57
    lodsb ; @04D59
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D5A
    jnz loc_4D63 ; @04D5C
    mov bp,0x2 ; @04D5E
    jmp short TextStreamReadCharacter ; @04D61
loc_4D63:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @04D63
TextStreamReadCharacter:
    lodsb ; @04D65
    cmp al,0xd ; @04D66
    jz DrawTextStream ; @04D68
    push cx ; @04D6A
    push bx ; @04D6B
    push si ; @04D6C
    call DrawTextGlyph ; @04D6D
TextStreamAfterGlyph:
    pop si ; @04D70
    pop bx ; @04D71
    pop cx ; @04D72
    inc cl ; @04D73
    jmp short TextStreamReadCharacter ; @04D75
TextStreamReturn:
    ret ; @04D77
; Space preserves incoming state except CMP flags. Other AL values wrap after SUB21.
; SI=5BC0+96*index; DI=SI+40. Live DS:1FEE+1000 becomes graphics source.
; CH/CL become top/left*16, width16/height16/three planes; BP is saved on live SS.
; Far CALL uses relocated same-CS target; consume actual RETF, then live POP BP.
DrawTextGlyph:
    cmp al,0x20 ; @04D78
    jz TextGlyphReturn ; @04D7A
    sub al,0x21 ; @04D7C
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04D7E
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D80
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D82
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D84
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D86
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D88
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @04D8A
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D8C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @04D8E
    add si,0x5bc0 ; @04D90
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04D94
    add di,byte +0x40 ; @04D96
    mov bx,[UiGraphicsBufferSegment-GameDataImage] ; @04D99
    add bx,0x1000 ; @04D9D
    mov [GraphicsResourceSegment-GameDataImage],bx ; @04DA1
    db 0x8a,0xdd ; ENCODED: mov bl,ch (NASM chooses a different encoding) ; @04DA5
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @04DA7
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @04DA9
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04DAB
    mov cl,0x4 ; @04DAD
    shl bx,cl ; @04DAF
    shl ax,cl ; @04DB1
    mov cl,0x10 ; @04DB3
    mov ch,0x3 ; @04DB5
    mov dx,0x10 ; @04DB7
    push bp ; @04DBA
TextGlyphBitmapCall:
    call 0x0:0x8822 ; @04DBB
TextGlyphAfterBitmap:
    pop bp ; @04DC0
TextGlyphReturn:
    ret ; @04DC1
; SS mirrors precede OUTs; mode1 copies four read latches, not the CPU byte.
; PUSH DS precedes live origin reads. REP copies6D60 bytes with incomingDF,
; wrapping SI/DI16; live POP DS and RET may read overwritten/device words.
; Flags and BX/BP are preserved; ES/AX=A000, DX=3CE,CX=0.
CopyDrawingPageToAlternate:
    mov dx,0x3c4 ; @04DC2
    mov ax,0xf02 ; @04DC5
    mov [ss:0x8],ax ; @04DC8
DisplayPageCopyMapMaskOutput:
    out dx,ax ; @04DCC
    mov dx,0x3ce ; @04DCD
    mov ax,0x105 ; @04DD0
    mov [ss:0x0],ax ; @04DD3
DisplayPageCopyModeOutput:
    out dx,ax ; @04DD7
    push ds ; @04DD8
    mov si,[DrawingOrigin-GameDataImage] ; @04DD9
    mov di,[AlternateDrawingOrigin-GameDataImage] ; @04DDD
    mov ax,0xa000 ; @04DE1
    mov ds,ax ; @04DE4
    mov es,ax ; @04DE6
    mov cx,0x6d60 ; @04DE8
    rep movsb ; @04DEB
DisplayPageCopyRestoreDataSegment:
    pop ds ; @04DED
DisplayPageCopyReturn:
    ret ; @04DEE
; Fixed DI=0,CX=6D60; tail shares ClearVgaBytes and its live outerRET.
; The UNKNOWN byte at4DF7 is skipped and remains unresolved.
ClearFullDrawingPage:
    mov di,0x0 ; @04DEF
    mov cx,0x6d60 ; @04DF2
    jmp short ClearVgaBytes ; @04DF5
; UNKNOWN: unresolved bytes
    db 0x90 ; @04DF7
; SS mirror words precede six OUTs. ES=A000, AX=A000, DX=3CE.
; REP clears incoming CX bytes from DI with incoming DF; CX=0. No CLI/STI.
; Final XOR defines CF/OF=0, PF/ZF=1,SF=0; AF undefined. RET reads live SS.
ClearVgaBytes:
    mov dx,0x3c4 ; @04DF8
    mov ax,0xf02 ; @04DFB
    mov [ss:0x8],ax ; @04DFE
    out dx,ax ; @04E02
    mov dx,0x3ce ; @04E03
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04E06
    mov [ss:0xa],ax ; @04E08
    out dx,ax ; @04E0C
    mov ax,0xf01 ; @04E0D
    mov [ss:0xc],ax ; @04E10
    out dx,ax ; @04E14
    mov ax,0x5 ; @04E15
    mov [ss:0x0],ax ; @04E18
    out dx,ax ; @04E1C
    mov ax,0x3 ; @04E1D
    mov [ss:0x2],ax ; @04E20
    out dx,ax ; @04E24
    mov ax,0xff08 ; @04E25
    mov [ss:0xe],ax ; @04E28
    out dx,ax ; @04E2C
    mov ax,0xa000 ; @04E2D
    mov es,ax ; @04E30
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04E32
    rep stosb ; @04E34
ClearVgaReturn:
    ret ; @04E36
sub_4E37:
    mov al,[0x1f72] ; @04E37
    cmp al,0x2 ; @04E3A
    jnz loc_4E46 ; @04E3C
    mov al,[0x1f70] ; @04E3E
    mov [0x1f72],al ; @04E41
    jmp short loc_4E51 ; @04E44
loc_4E46:
    cmp [0x1f70],al ; @04E46
    jz loc_4E83 ; @04E4A
    mov byte [0x1f72],0x2 ; @04E4C
loc_4E51:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04E51
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04E54
    mov si,0xee30 ; @04E57
    mov al,[0x25a7] ; @04E5A
    test al,0x3 ; @04E5D
    jz loc_4E84 ; @04E5F
    test al,0x2 ; @04E61
    jz loc_4E6F ; @04E63
    cmp byte [0x2010],0xff ; @04E65
    jnz loc_4E6F ; @04E6A
    mov si,0xea50 ; @04E6C
loc_4E6F:
    mov ax,0x15f ; @04E6F
    mov bx,0x92 ; @04E72
    mov dx,0x40 ; @04E75
    mov cx,0x41f ; @04E78
    mov bp,0x1 ; @04E7B
    call 0x0:0x8822 ; @04E7E
loc_4E83:
    ret ; @04E83
loc_4E84:
    mov bx,0x78 ; @04E84
    mov ax,0x144 ; @04E87
    mov si,0xb120 ; @04E8A
    mov bp,0x3 ; @04E8D
    mov cx,0x43d ; @04E90
    mov dx,0x78 ; @04E93
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04E96
    add di,0xab9 ; @04E98
    call 0x0:0x8822 ; @04E9C
    ret ; @04EA1
sub_4EA2:
    mov al,[0x1f6f] ; @04EA2
    cmp al,0x4 ; @04EA5
    jnz loc_4EB1 ; @04EA7
    mov al,[0x1f6e] ; @04EA9
    mov [0x1f6f],al ; @04EAC
    jmp short loc_4EBC ; @04EAF
loc_4EB1:
    cmp [0x1f6e],al ; @04EB1
    jz loc_4EE6 ; @04EB5
    mov byte [0x1f6f],0x4 ; @04EB7
loc_4EBC:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04EBC
    add ax,0x1000 ; @04EBF
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04EC2
    mov bl,[0x1f6e] ; @04EC5
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @04EC9
    shl bx,1 ; @04ECB
    mov si,[cs:bx+0x4ee7] ; @04ECD
    mov ax,0x1e6 ; @04ED2
    mov bx,0x91 ; @04ED5
    mov dx,0x48 ; @04ED8
    mov cx,0x41b ; @04EDB
    mov bp,0x1 ; @04EDE
    call 0x0:0x8822 ; @04EE1
loc_4EE6:
    ret ; @04EE6
; UNKNOWN: unresolved bytes
    db 0xf4,0x57,0x28,0x54,0x5c,0x50,0x90,0x4c ; @04EE7
sub_4EEF:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04EEF
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04EF2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04EF5
    mov bx,0x14 ; @04EF7
    mov bp,0xf42 ; @04EFA
    mov cl,0x5e ; @04EFD
    mov ch,0x4 ; @04EFF
    mov dx,0x278 ; @04F01
    mov si,0x2080 ; @04F04
    mov di,0x7786 ; @04F07
    call 0x0:0x8822 ; @04F0A
    mov ax,0x8 ; @04F0F
    mov bx,0xa ; @04F12
    mov bp,0x2 ; @04F15
    mov cl,0x5e ; @04F18
    mov ch,0x4 ; @04F1A
    mov dx,0x278 ; @04F1C
    mov si,0x2080 ; @04F1F
    mov di,0x7786 ; @04F22
    call 0x0:0x8822 ; @04F25
    ret ; @04F2A
sub_4F2B:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04F2B
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04F2E
    mov bx,0x78 ; @04F31
    mov ax,0x44 ; @04F34
    mov cx,0x4 ; @04F37
    lea di,[0x4f8a] ; @04F3A
    call sub_4F4A ; @04F3E
    mov bx,0xc5 ; @04F41
    mov ax,0xc4 ; @04F44
    mov cx,0x2 ; @04F47
sub_4F4A:
    push cx ; @04F4A
    mov si,[cs:di] ; @04F4B
    add di,byte +0x2 ; @04F4E
    mov bp,0xf43 ; @04F51
    push ax ; @04F54
    push bx ; @04F55
    sub ax,0x8 ; @04F56
    add bx,byte +0x8 ; @04F59
    call sub_4F6E ; @04F5C
    pop bx ; @04F5F
    pop ax ; @04F60
    mov bp,0x3 ; @04F61
    call sub_4F6E ; @04F64
    pop cx ; @04F67
    add ax,0x80 ; @04F68
    loop sub_4F4A ; @04F6B
    ret ; @04F6D
sub_4F6E:
    push ax ; @04F6E
    push bx ; @04F6F
    push bp ; @04F70
    push si ; @04F71
    push di ; @04F72
    mov cx,0x43d ; @04F73
    mov dx,0x78 ; @04F76
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04F79
    add di,0xab9 ; @04F7B
    call 0x0:0x8822 ; @04F7F
    pop di ; @04F84
    pop si ; @04F85
    pop bp ; @04F86
    pop bx ; @04F87
    pop ax ; @04F88
    ret ; @04F89
; UNKNOWN: unresolved bytes
    db 0x88,0x94,0xd4,0xa2,0x20,0xb1,0x6c,0xbf,0xb8,0xcd,0x04,0xdc ; @04F8A
sub_4F96:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04F96
    add ax,0x800 ; @04F99
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04F9C
    lea si,[0x4960] ; @04F9F
    mov cx,0xa ; @04FA3
loc_4FA6:
    push cx ; @04FA6
    mov ax,[si] ; @04FA7
    cmp ax,0x8000 ; @04FA9
    jz loc_4FF1 ; @04FAC
    dec ax ; @04FAE
    mov [si],ax ; @04FAF
    cmp ax,0xffef ; @04FB1
    jnz loc_4FBD ; @04FB4
    mov ax,[si+0x2] ; @04FB6
    mov [si],ax ; @04FB9
    jmp short loc_4FF1 ; @04FBB
loc_4FBD:
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @04FBD
    jns loc_4FF1 ; @04FBF
    neg ax ; @04FC1
    dec ax ; @04FC3
    shr ax,1 ; @04FC4
    xchg al,ah ; @04FC6
    mov bp,[si+0x8] ; @04FC8
    shr ax,1 ; @04FCB
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @04FCD
    shr ax,1 ; @04FCF
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @04FD1
    mov ax,[si+0x4] ; @04FD3
    mov bx,[si+0x6] ; @04FD6
    push si ; @04FD9
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @04FDA
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04FDC
    add di,0x90 ; @04FDE
    mov bp,0x1 ; @04FE2
    mov cx,0x40c ; @04FE5
    mov dx,0x20 ; @04FE8
    call 0x0:0x8822 ; @04FEB
    pop si ; @04FF0
loc_4FF1:
    pop cx ; @04FF1
    add si,byte +0xb ; @04FF2
    loop loc_4FA6 ; @04FF5
    ret ; @04FF7
sub_4FF8:
    lea si,[0x4960] ; @04FF8
    mov cx,0xa ; @04FFC
    mov bx,0x28 ; @04FFF
loc_5002:
    mov ax,[si+0x2] ; @05002
    cmp ax,0x8000 ; @05005
    jz loc_500C ; @05008
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @0500A
loc_500C:
    mov [si],ax ; @0500C
    add bx,byte +0x28 ; @0500E
    add si,byte +0xb ; @05011
    loop loc_5002 ; @05014
    ret ; @05016
; 5017 resets the row;5019 preserves incoming BX. Both share the7E76 tile loop.
; See docs/background-drawing.md for live saves and changed child returns.
DrawScreenBackground:
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @05017
DrawScreenBackgroundFromRow:
    jmp DrawScreenBackgroundTiles ; @05019
; UNKNOWN: unresolved bytes
    db 0x32,0xc0,0xa2,0xcd,0x1f,0x3a,0x06,0xcd,0x1f,0x74,0xfa,0xc3 ; @0501C
InstallMenuTimerVector:
    cli ; @05028
    push ds ; @05029
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0502A
    mov ds,ax ; @0502C
    mov word [0x20],0x4c47 ; @0502E
    mov [0x22],cs ; @05034
    pop ds ; @05038
    sti ; @05039
    ret ; @0503A
DrawCodeInputText:
    lea si,[0x4def] ; @0503B
    jmp DrawTextStream ; @0503F
sub_5042:
    mov dl,[LevelResourceSelectionByte-GameDataImage] ; @05042
    mov dh,[0x491d] ; @05046
    mov cl,[0x40] ; @0504A
    lea si,[0x4913] ; @0504E
    lea di,[0x4d68] ; @05052
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05056
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05058
    and ax,0x101 ; @0505A
    and ch,0x1 ; @0505D
    shl al,1 ; @05060
    shl al,1 ; @05062
    shl al,1 ; @05064
    shl ah,1 ; @05066
    shl ch,1 ; @05068
    shl ch,1 ; @0506A
    or al,[si] ; @0506C
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @0506E
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05070
    mov [di],al ; @05072
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05074
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05076
    and al,0x2 ; @05078
    and ch,0x2 ; @0507A
    shl al,1 ; @0507D
    shr ch,1 ; @0507F
    or al,[si+0x1] ; @05081
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05084
    mov [di+0x1],al ; @05086
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05089
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @0508B
    and ax,0x204 ; @0508D
    and ch,0x4 ; @05090
    shr ah,1 ; @05093
    shr ch,1 ; @05095
    or al,[si+0x2] ; @05097
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @0509A
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @0509C
    mov [di+0x2],al ; @0509E
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @050A1
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050A3
    and al,0x8 ; @050A5
    and ch,0x8 ; @050A7
    shr al,1 ; @050AA
    shr al,1 ; @050AC
    shr al,1 ; @050AE
    shr ch,1 ; @050B0
    shr ch,1 ; @050B2
    or al,[si+0x3] ; @050B4
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @050B7
    mov [di+0x3],al ; @050B9
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @050BC
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050BE
    and ax,0x410 ; @050C0
    and ch,0x10 ; @050C3
    shr al,1 ; @050C6
    shr al,1 ; @050C8
    shr al,1 ; @050CA
    shr ah,1 ; @050CC
    shr ah,1 ; @050CE
    shr ch,1 ; @050D0
    or al,[si+0x4] ; @050D2
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @050D5
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @050D7
    mov [di+0x4],al ; @050D9
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @050DC
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050DE
    and al,0x20 ; @050E0
    and ah,0x8 ; @050E2
    and ch,0x20 ; @050E5
    shr al,1 ; @050E8
    shr al,1 ; @050EA
    shr al,1 ; @050EC
    shr al,1 ; @050EE
    shr al,1 ; @050F0
    shr ah,1 ; @050F2
    shr ah,1 ; @050F4
    shr ch,1 ; @050F6
    shr ch,1 ; @050F8
    shr ch,1 ; @050FA
    or al,[si+0x5] ; @050FC
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @050FF
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05101
    mov [di+0x5],al ; @05103
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05106
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05108
    and al,0xc0 ; @0510A
    and ch,0x40 ; @0510C
    shr al,1 ; @0510F
    shr al,1 ; @05111
    shr al,1 ; @05113
    shr al,1 ; @05115
    shr ch,1 ; @05117
    shr ch,1 ; @05119
    shr ch,1 ; @0511B
    shr ch,1 ; @0511D
    shr ch,1 ; @0511F
    shr ch,1 ; @05121
    or al,[si+0x6] ; @05123
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05126
    mov [di+0x6],al ; @05128
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @0512B
    and al,0xf ; @0512D
    add al,[si+0x7] ; @0512F
    mov [di+0x7],al ; @05132
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05135
    and al,0xf0 ; @05137
    shr al,1 ; @05139
    shr al,1 ; @0513B
    shr al,1 ; @0513D
    shr al,1 ; @0513F
    add al,[si+0x8] ; @05141
    mov [di+0x8],al ; @05144
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @05147
    add al,[di] ; @05149
    add al,[di+0x1] ; @0514B
    add al,[di+0x2] ; @0514E
    add al,[di+0x3] ; @05151
    add al,[di+0x4] ; @05154
    add al,[di+0x5] ; @05157
    add al,[di+0x6] ; @0515A
    add al,[di+0x7] ; @0515D
    add al,[di+0x8] ; @05160
    and al,0xf ; @05163
    add al,[si+0x9] ; @05165
    mov [di+0x9],al ; @05168
    mov dh,0x7 ; @0516B
    db 0x22,0xd6 ; ENCODED: and dl,dh (NASM chooses a different encoding) ; @0516D
    db 0x2a,0xf2 ; ENCODED: sub dh,dl (NASM chooses a different encoding) ; @0516F
    lea si,[0x4d6e] ; @05171
loc_5175:
    mov al,[si] ; @05175
    mov ah,[si-0x1] ; @05177
    mov [si],ah ; @0517A
    mov ah,[si-0x2] ; @0517C
    mov [si-0x1],ah ; @0517F
    mov ah,[si-0x3] ; @05182
    mov [si-0x2],ah ; @05185
    mov ah,[si-0x4] ; @05188
    mov [si-0x3],ah ; @0518B
    mov ah,[si-0x5] ; @0518E
    mov [si-0x4],ah ; @05191
    mov ah,[si-0x6] ; @05194
    mov [si-0x5],ah ; @05197
    mov [si-0x6],al ; @0519A
    dec dh ; @0519D
    jns loc_5175 ; @0519F
    ret ; @051A1
sub_51A2:
    lea si,[0x4df2] ; @051A2
    cmp word [si],0x4942 ; @051A6
    jnz loc_51CD ; @051AA
    cmp word [si+0x2],0x4c4c ; @051AC
    jnz loc_51CD ; @051B1
    cmp word [si+0x4],0x4e41 ; @051B3
    jnz loc_51CD ; @051B8
    cmp word [si+0x6],0x5444 ; @051BA
    jnz loc_51CD ; @051BF
    cmp word [si+0x8],0x4445 ; @051C1
    jnz loc_51CD ; @051C6
    mov byte [0x1f74],0xff ; @051C8
loc_51CD:
    lea di,[0x4913] ; @051CD
    mov cx,0x9 ; @051D1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @051D4
    push si ; @051D6
loc_51D7:
    add al,[si] ; @051D7
    inc si ; @051D9
    loop loc_51D7 ; @051DA
    pop si ; @051DC
    and al,0xf ; @051DD
    mov ah,[si+0x9] ; @051DF
    db 0x2a,0xe0 ; ENCODED: sub ah,al (NASM chooses a different encoding) ; @051E2
    cmp [di+0x9],ah ; @051E4
    jz loc_51EC ; @051E7
    jmp loc_52D3 ; @051E9
loc_51EC:
    mov al,[si+0x7] ; @051EC
    sub al,[di+0x7] ; @051EF
    mov ah,[si+0x8] ; @051F2
    sub ah,[di+0x8] ; @051F5
    and ax,0xf0f ; @051F8
    shl ah,1 ; @051FB
    shl ah,1 ; @051FD
    shl ah,1 ; @051FF
    shl ah,1 ; @05201
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @05203
    mov [LevelResourceSelectionByte-GameDataImage],al ; @05205
    mov dh,0x7 ; @05208
    db 0x22,0xc6 ; ENCODED: and al,dh (NASM chooses a different encoding) ; @0520A
    db 0x2a,0xf0 ; ENCODED: sub dh,al (NASM chooses a different encoding) ; @0520C
loc_520E:
    mov al,[si] ; @0520E
    mov ah,[si+0x1] ; @05210
    mov [si],ah ; @05213
    mov ah,[si+0x2] ; @05215
    mov [si+0x1],ah ; @05218
    mov ah,[si+0x3] ; @0521B
    mov [si+0x2],ah ; @0521E
    mov ah,[si+0x4] ; @05221
    mov [si+0x3],ah ; @05224
    mov ah,[si+0x5] ; @05227
    mov [si+0x4],ah ; @0522A
    mov ah,[si+0x6] ; @0522D
    mov [si+0x5],ah ; @05230
    mov [si+0x6],al ; @05233
    dec dh ; @05236
    jns loc_520E ; @05238
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0523A
    mov al,[si] ; @0523C
    shr al,1 ; @0523E
    shr al,1 ; @05240
    shr al,1 ; @05242
    and al,0x1 ; @05244
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05246
    mov al,[si+0x1] ; @05248
    shr al,1 ; @0524B
    and al,0x2 ; @0524D
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0524F
    mov al,[si+0x2] ; @05251
    and al,0x4 ; @05254
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05256
    mov al,[si+0x3] ; @05258
    shl al,1 ; @0525B
    shl al,1 ; @0525D
    shl al,1 ; @0525F
    and al,0x8 ; @05261
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05263
    mov al,[si+0x4] ; @05265
    shl al,1 ; @05268
    shl al,1 ; @0526A
    shl al,1 ; @0526C
    and al,0x10 ; @0526E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05270
    mov al,[si+0x5] ; @05272
    shl al,1 ; @05275
    shl al,1 ; @05277
    shl al,1 ; @05279
    shl al,1 ; @0527B
    shl al,1 ; @0527D
    and al,0x20 ; @0527F
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05281
    mov al,[si+0x6] ; @05283
    shl al,1 ; @05286
    shl al,1 ; @05288
    shl al,1 ; @0528A
    shl al,1 ; @0528C
    and al,0xc0 ; @0528E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05290
    cmp ah,[LevelResourceSelectionByte-GameDataImage] ; @05292
    jnz loc_52D3 ; @05296
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @05298
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0529B
    mov cl,0x1e ; @0529D
    div cl ; @0529F
    mov [0x1f6e],al ; @052A1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @052A4
    mov al,[si] ; @052A6
    shr al,1 ; @052A8
    and al,0x1 ; @052AA
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052AC
    mov al,[si+0x2] ; @052AE
    shl al,1 ; @052B1
    and al,0x2 ; @052B3
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052B5
    mov al,[si+0x4] ; @052B7
    shl al,1 ; @052BA
    shl al,1 ; @052BC
    and al,0x4 ; @052BE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052C0
    mov al,[si+0x5] ; @052C2
    shl al,1 ; @052C5
    shl al,1 ; @052C7
    and al,0x8 ; @052C9
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052CB
    mov [0x491d],ah ; @052CD
    db 0x2a,0xe4 ; ENCODED: sub ah,ah (NASM chooses a different encoding) ; @052D1
loc_52D3:
    ret ; @052D3
