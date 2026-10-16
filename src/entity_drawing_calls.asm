; Untranslated 3634..368D entity draw-call loop; IRQ/provider seams remain open.
times -(($-$$) != 0x3634) db 0 ; module start assertion
sub_3634:
    mov di,0x88 ; @03634
    mov cl,[EntitySlotBound-GameDataImage] ; @03637
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @0363B
    jz loc_368D ; @0363D
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0363F
    mov [EntityDrawingPassCount-GameDataImage],ch ; @03641
loc_3645:
    push cx ; @03645
    push di ; @03646
    cmp byte [di+0x26],0xff ; @03647
    jz loc_367D ; @0364B
    inc byte [EntityDrawingPassCount-GameDataImage] ; @0364D
    call DrawEntityMinimapPixel ; @03651
    call MarkEntityDrawingDirty ; @03654
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @03657
    cmp ax,[di+0x14] ; @0365A
    jnz loc_3670 ; @0365D
    mov al,[di+0x28] ; @0365F
    cmp al,0x1 ; @03662
    jl loc_3670 ; @03664
    push di ; @03666
    xchg si,di ; @03667
    call DrawEntityPointCloud ; @03669
    pop di ; @0366C
    jmp short loc_367D ; @0366D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0366F
loc_3670:
    mov byte [EntityWorkGuard-GameDataImage],0xff ; @03670
    call DrawObjectSprite ; @03675
sub_3678:
    mov byte [EntityWorkGuard-GameDataImage],0x0 ; @03678
loc_367D:
    pop di ; @0367D
    pop cx ; @0367E
    add di,byte +0x2d ; @0367F
    loop loc_3645 ; @03682
    mov al,[EntityDrawingPassCount-GameDataImage] ; @03684
    mov si,StatusEntityCountField-GameDataImage ; @03687
    jmp WriteDecimalByteField ; @0368A
loc_368D:
    ret ; @0368D
times -(($-$$) != 0x368e) db 0 ; module end assertion
