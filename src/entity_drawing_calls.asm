; Maintained 3634..368D entity draw-call loop; IRQ/provider seams remain open.
times -(($-$$) != 0x3634) db 0 ; module start assertion
; CONTRACT: zero EntitySlotBound returns without clearing the count or formatting.
; Otherwise each live SS frame preserves CX/DI for a 2Dh-stride record. +26==FF
; skips drawing; the byte pass count increments before either drawing path.
; Children return live DS/ES. The callback comparison and signed +28>=1 select
; the point path; the sprite path brackets 706F with DS:0050 guard FF/00.
; The actual POP DI/CX controls the next record and LOOP, including aliases.
; 368A JMPs to the decimal field tail without a CALL frame; its RET consumes
; this routine's original caller word. UNKNOWN 366F is outside the known body.
DrawEntityRecords:
    mov di,EntityRecordsBase-GameDataImage ; @03634
    mov cl,[EntitySlotBound-GameDataImage] ; @03637
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @0363B
    jz EntityDrawingEarlyReturn ; @0363D
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0363F
    mov [EntityDrawingPassCount-GameDataImage],ch ; @03641
EntityDrawingLoop:
    push cx ; @03645
    push di ; @03646
    cmp byte [di+EntityRecordDrawingSkipGate-EntityRecordsBase],0xff ; @03647
    jz EntityDrawingRestoreRecord ; @0364B
    inc byte [EntityDrawingPassCount-GameDataImage] ; @0364D
    call DrawEntityMinimapPixel ; @03651
EntityDrawingAfterMinimap:
    call MarkEntityDrawingDirty ; @03654
EntityDrawingAfterDirty:
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @03657
    cmp ax,[di+EntityRecordSpriteCallback-EntityRecordsBase] ; @0365A
    jnz loc_3670 ; @0365D
    mov al,[di+EntityRecordFrameSelector-EntityRecordsBase] ; @0365F
    cmp al,0x1 ; @03662
    jl loc_3670 ; @03664
    push di ; @03666
    xchg si,di ; @03667
    call DrawEntityPointCloud ; @03669
EntityDrawingAfterPoints:
    pop di ; @0366C
    jmp short EntityDrawingRestoreRecord ; @0366D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0366F
loc_3670:
    mov byte [EntityWorkGuard-GameDataImage],0xff ; @03670
    call DrawObjectSprite ; @03675
EntityDrawingSpriteResume:
    mov byte [EntityWorkGuard-GameDataImage],0x0 ; @03678
EntityDrawingRestoreRecord:
    pop di ; @0367D
    pop cx ; @0367E
    add di,byte +0x2d ; @0367F
    loop EntityDrawingLoop ; @03682
EntityDrawingDecimalTail:
    mov al,[EntityDrawingPassCount-GameDataImage] ; @03684
    mov si,StatusEntityCountField-GameDataImage ; @03687
EntityDrawingDecimalJump:
    jmp WriteDecimalByteField ; @0368A
EntityDrawingEarlyReturn:
    ret ; @0368D
times -(($-$$) != 0x368e) db 0 ; module end assertion
