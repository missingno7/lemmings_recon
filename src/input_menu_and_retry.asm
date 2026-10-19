; Maintained span43CE..4B5B; physical order/UNKNOWN preserved.
times -(($-$$) != 0x43ce) db 0
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
MenuRefresh4401:
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
    call ReadKeyboardCharacter ; @04478
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
    call WriteDecimalBytePair ; @04584
    mov al,[0xfce] ; @04587
    lea si,[0x4b50] ; @0458A
    call WriteDecimalByteField ; @0458E
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
    call WriteDecimalBytePair ; @045AF
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
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @04647
    jz loc_465D ; @0464C
    lea si,[0x4bc3] ; @0464E
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @04652
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
    mov al,[StatusCompletionDisplayValue-GameDataImage] ; @0471D
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
    call WriteDecimalByteField ; @0474F
    call sub_5042 ; @04752
    lea si,[0x4d3f] ; @04755
    call DrawTextStream ; @04759
    lea bx,[0x4d75] ; @0475C
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @04760
    jz loc_4776 ; @04765
    lea bx,[0x4da0] ; @04767
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @0476B
    jz loc_4776 ; @04770
    lea bx,[0x4dc2] ; @04772
loc_4776:
    jmp short loc_4797 ; @04776
loc_4778:
    mov byte [0x1f6d],0x0 ; @04778
    lea bx,[0x4cd3] ; @0477D
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @04781
    jz loc_4797 ; @04786
    lea bx,[0x4cfe] ; @04788
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @0478C
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
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @047EE
    jz loc_4804 ; @047F3
    lea si,[0x4bc3] ; @047F5
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @047F9
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
    mov al,[StatusCompletionDisplayValue-GameDataImage] ; @048BD
    lea si,[0x4c5d] ; @048C0
    call sub_4B5C ; @048C4
    mov al,[0x41] ; @048C7
    lea si,[0x4c71] ; @048CA
    call sub_4B5C ; @048CE
    lea si,[0x4c77] ; @048D1
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @048D5
    jz loc_48EB ; @048DA
    lea si,[0x4c9d] ; @048DC
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @048E0
    jz loc_48EB ; @048E5
    lea si,[0x4cb9] ; @048E7
loc_48EB:
    mov [0x21],si ; @048EB
    lea si,[0x4c4e] ; @048EF
    jmp DrawTextStream ; @048F3
sub_48F6:
    mov al,[StatusCompletionDisplayValue-GameDataImage] ; @048F6
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
    call WriteDecimalByteField ; @049A9
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
    call ReadKeyboardCharacter ; @04A31
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
    mov [InputModeByte25A6-GameDataImage],al ; @04A6D
    call PollPort201ButtonsLow ; @04A70
    mov [InputAxisBaselineX25A2-GameDataImage],bx ; @04A73
    mov [InputAxisBaselineY25A4-GameDataImage],cx ; @04A77
    jmp short loc_4A95 ; @04A7B
loc_4A7D:
    mov ax,0x4359 ; @04A7D
    mov [InputPollCallback-GameDataImage],ax ; @04A80
    mov al,0x1 ; @04A83
    mov [InputModeByte25A6-GameDataImage],al ; @04A85
    call PollPort201ButtonsHigh ; @04A88
    mov [InputAxisBaselineX25A2-GameDataImage],bx ; @04A8B
    mov [InputAxisBaselineY25A4-GameDataImage],cx ; @04A8F
    jmp short loc_4A95 ; @04A93
loc_4A95:
    lea si,[0x4ea9] ; @04A95
    call DrawTextStream ; @04A99
    call SwapDrawingOriginsAndDisplay ; @04A9C
loc_4A9F:
; Scoped menu loop: actual display/character CALL frames; unsigned31..34 acceptance.
; SUBAL30 stores2005, then actual JMP4401. No invented RET; surrounding menu open.
; See docs/keyboard-input.md. Both waits retain their original unbounded loops.
SelectInputScale4A9F:
    call WaitForDisplayStatusBit3Cycle ; @04A9F
InputScaleAfterWait4AA2:
    call ReadKeyboardCharacter ; @04AA2
InputScaleAfterCharacter4AA5:
    cmp al,0x31 ; @04AA5
    jc loc_4A9F ; @04AA7
    cmp al,0x34 ; @04AA9
    ja loc_4A9F ; @04AAB
    sub al,0x30 ; @04AAD
    mov [InputAxisScaleSelector2005-GameDataImage],al ; @04AAF
    jmp loc_4401 ; @04AB2
loc_4AB5:
    mov byte [InputModeByte25A6-GameDataImage],0x2 ; @04AB5
    jmp loc_4401 ; @04ABA
loc_4ABD:
    mov byte [InputModeByte25A6-GameDataImage],0x0 ; @04ABD
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
times -(($-$$) != 0x4b5c) db 0 ; module end assertion
