; Maintained image span 03944..03AC7; physical order and UNKNOWN bytes preserved.
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
    sub al,[LevelReleaseSetting-GameDataImage] ; @039D8
    shr al,1 ; @039DC
    neg al ; @039DE
    add al,0x35 ; @039E0
    neg al ; @039E2
    add al,0x39 ; @039E4
    mov [EntityCreationReload-GameDataImage],al ; @039E6
    mov byte [LevelReleaseMinimumRefreshCounter-GameDataImage],0x0 ; @039E9
    mov byte [LevelReleaseSettingRefreshCounter-GameDataImage],0x0 ; @039EE
    mov byte [LevelActionCountRefreshCounter2-GameDataImage],0x0 ; @039F3
    mov byte [LevelActionCountRefreshCounter7-GameDataImage],0x0 ; @039F8
    mov byte [LevelActionCountRefreshCounter0-GameDataImage],0x0 ; @039FD
    mov byte [LevelActionCountRefreshCounter4-GameDataImage],0x0 ; @03A02
    mov byte [LevelActionCountRefreshCounter3-GameDataImage],0x0 ; @03A07
    mov byte [LevelActionCountRefreshCounter5-GameDataImage],0x0 ; @03A0C
    mov byte [LevelActionCountRefreshCounter1-GameDataImage],0x0 ; @03A11
    mov byte [LevelActionCountRefreshCounter6-GameDataImage],0x0 ; @03A16
    mov byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @03A1B
    mov byte [LevelReleaseMinimumDisplaySnapshot-GameDataImage],0xff ; @03A20
    mov byte [LevelReleaseSettingDisplaySnapshot-GameDataImage],0xff ; @03A25
    mov byte [LevelActionCountDisplaySnapshot2-GameDataImage],0xff ; @03A2A
    mov byte [LevelActionCountDisplaySnapshot7-GameDataImage],0xff ; @03A2F
    mov byte [LevelActionCountDisplaySnapshot0-GameDataImage],0xff ; @03A34
    mov byte [LevelActionCountDisplaySnapshot4-GameDataImage],0xff ; @03A39
    mov byte [LevelActionCountDisplaySnapshot3-GameDataImage],0xff ; @03A3E
    mov byte [LevelActionCountDisplaySnapshot5-GameDataImage],0xff ; @03A43
    mov byte [LevelActionCountDisplaySnapshot1-GameDataImage],0xff ; @03A48
    mov byte [LevelActionCountDisplaySnapshot6-GameDataImage],0xff ; @03A4D
    mov byte [StatusIconDisplaySnapshot-GameDataImage],0x3 ; @03A52
    mov ah,[LevelReleaseSettingMinimum-GameDataImage] ; @03A57
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @03A5B
    call DrawStatusCount ; @03A5D
    mov ah,[LevelReleaseSetting-GameDataImage] ; @03A60
    mov al,0x1 ; @03A64
    call DrawStatusCount ; @03A66
    mov ah,[LevelActionCount2-GameDataImage] ; @03A69
    mov al,0x4 ; @03A6D
    call DrawStatusCount ; @03A6F
    mov ah,[LevelActionCount7-GameDataImage] ; @03A72
    mov al,0x9 ; @03A76
    call DrawStatusCount ; @03A78
    mov ah,[LevelActionCount0-GameDataImage] ; @03A7B
    mov al,0x2 ; @03A7F
    call DrawStatusCount ; @03A81
    mov ah,[LevelActionCount4-GameDataImage] ; @03A84
    mov al,0x6 ; @03A88
    call DrawStatusCount ; @03A8A
    mov ah,[LevelActionCount3-GameDataImage] ; @03A8D
    mov al,0x5 ; @03A91
    call DrawStatusCount ; @03A93
    mov ah,[LevelActionCount5-GameDataImage] ; @03A96
    mov al,0x7 ; @03A9A
    call DrawStatusCount ; @03A9C
    mov ah,[LevelActionCount1-GameDataImage] ; @03A9F
    mov al,0x3 ; @03AA3
    call DrawStatusCount ; @03AA5
    mov ah,[LevelActionCount6-GameDataImage] ; @03AA8
    mov al,0x8 ; @03AAC
    call DrawStatusCount ; @03AAE
    mov al,[0x45] ; @03AB1
    mov si,0x2095 ; @03AB4
    call WriteDecimalByteField ; @03AB7
    mov si,StatusPercentDigits-GameDataImage+1 ; @03ABA
    mov byte [si-0x1],0x20 ; @03ABD
    mov al,[EntityActionSelector-GameDataImage] ; @03AC1
    call DrawStatusIconOutline ; @03AC4
    ret ; @03AC7
times -(($-$$) != 0x3ac8) db 0 ; module end assertion
