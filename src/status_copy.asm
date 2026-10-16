; Maintained 75EF..7629 status contract.
times -(($-$$) != 0x75ef) db 0 ; module start assertion
; CONTRACT: one actual CALL, then second-origin read through returned DS and
; fallthrough into the same leaf. Every pass copies all06E0 bytes, sequentially
; with DF, from A000:F91F (clear-DF last FFFE; reverse last F240). Live SS DS
; save,0008/0000 mirrors, latch-mode OUTs and actual near return words remain.
; The leaf preserves FLAGS, leaves ES/DS during copying A000, then POPs live DS.
CopyStatusRegionToBothDrawingOrigins:
    mov di,[DrawingOrigin-GameDataImage] ; @075EF
    add di,0x1e42 ; @075F3
    call CopyStatusRegionToVga ; @075F7
StatusCopyAfterFirst:
    mov di,[AlternateDrawingOrigin-GameDataImage] ; @075FA
    add di,0x1e42 ; @075FE
CopyStatusRegionToVga:
    push ds ; @07602
    mov dx,0x3c4 ; @07603
    mov ax,0xf02 ; @07606
    mov [ss:0x8],ax ; @07609
    out dx,ax ; @0760D
    mov dx,0x3ce ; @0760E
    mov ax,0x105 ; @07611
    mov [ss:0x0],ax ; @07614
    out dx,ax ; @07618
    mov si,0xf91f ; @07619
    mov dx,0xa000 ; @0761C
    mov es,dx ; @0761F
    mov ds,dx ; @07621
    mov cx,0x6e0 ; @07623
    rep movsb ; @07626
    pop ds ; @07628
StatusCopyReturn:
    ret ; @07629
times -(($-$$) != 0x762a) db 0 ; module end assertion
