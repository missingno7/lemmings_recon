; Maintained image span 03944..03AC7; physical order and UNKNOWN bytes preserved.
times -(($-$$) != 0x3944) db 0 ; module start assertion
; ANIMATION GATE: exactly FF at live DS:002B returns before touching records.
; The JMP enters the shared32-record tail without adding a guest stack frame.
AdvanceLevelObjectAnimations:
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @03944
    jz ObjectAnimationEarlyReturn ; @03949
    jmp AdvanceLevelObjectAnimationRecords ; @0394B
ObjectAnimationEarlyReturn:
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
; S14 U044: [0395E,0395F) stored bytes remain UNKNOWN.
; Neighbours: P 0395C jmp 0x397a; N 0395F mov si, 0x10eb.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
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
times -(($-$$) != 0x39ce) db 0 ; module end assertion
