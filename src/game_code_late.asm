; Maintained image span 03944..03CDD; physical order and UNKNOWN bytes preserved.
times -(($-$$) != 0x3944) db 0 ; module start assertion
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
    call WriteDecimalByteField ; @03AB7
    mov si,0x209d ; @03ABA
    mov byte [si-0x1],0x20 ; @03ABD
    mov al,[EntityActionSelector-GameDataImage] ; @03AC1
    call DrawStatusIconOutline ; @03AC4
    ret ; @03AC7
; Scoped C prefix composes actual column/viewport CALLs and stops3ACE.
; Remaining status text/input/count display body is untranslated.
UpdateStatusDisplay:
    call UpdateMinimapColumn ; @03AC8
StatusDisplayAfterMinimapColumn:
    call DrawMinimapViewport ; @03ACB
StatusDisplayAfterMinimapViewport:
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
    call DrawStatusIconOutline ; @03B36
    mov al,[0x83] ; @03B39
    call RestoreStatusIcon ; @03B3C
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
times -(($-$$) != 0x3cde) db 0 ; module end assertion
