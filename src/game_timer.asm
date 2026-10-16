; Game timer physical module17C7..18B1, with shared tail183E.
; Entry183E inherits FLAGS,DI,SI,BP,BX,DX,CX,ES,DS,AX,IP,CS,FLAGS on liveSS:SP.
; Children consume actual CALL frames; chain1899 consumes its synthetic IRET frame.
; ReturnedDS owns1FCF/1FCD before POPDS; outer IRET remains independent.
; The ten checksum bytes188F..1898 retain their overlapping code/data meaning.
; Prefix17C7..183D remains untranslated; docs/timer-frontier.md.
times -(($-$$) != 0x17c7) db 0
GameTimerIrqHandler:
    push ax ; @017C7
    push ds ; @017C8
    push es ; @017C9
    push cx ; @017CA
    push dx ; @017CB
    push bx ; @017CC
    push bp ; @017CD
    push si ; @017CE
    push di ; @017CF
    pushf ; @017D0
    mov ax,0x9a9 ; @017D1
    mov ds,ax ; @017D4
    cmp byte [ConfigurationOption200E-GameDataImage],0xff ; @017D6
    jz GameTimerTail183E ; @017DB
    call sub_5473 ; @017DD
    cli ; @017E0
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @017E1
    mov bx,[AlternateDrawingOrigin-GameDataImage] ; @017E5
    add bx,[DrawingPageByteOffset-GameDataImage] ; @017E9
    add bx,byte +0x2 ; @017ED
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @017F0
    mov al,0xc ; @017F2
    out dx,ax ; @017F4
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @017F5
    inc al ; @017F7
    out dx,ax ; @017F9
    add dl,0x6 ; @017FA
    sti ; @017FD
loc_17FE:
    in al,dx ; @017FE
    jmp short loc_1801 ; @017FF
loc_1801:
    jmp short loc_1803 ; @01801
loc_1803:
    jmp short loc_1805 ; @01803
loc_1805:
    test al,0x8 ; @01805
    jz loc_17FE ; @01807
loc_1809:
    in al,dx ; @01809
    jmp short loc_180C ; @0180A
loc_180C:
    jmp short loc_180E ; @0180C
loc_180E:
    jmp short loc_1810 ; @0180E
loc_1810:
    test al,0x8 ; @01810
    jnz loc_1809 ; @01812
    cli ; @01814
    mov cx,[0x1fc9] ; @01815
    mov al,0x36 ; @01819
    out 0x43,al ; @0181B
    jmp short loc_181F ; @0181D
loc_181F:
    jmp short loc_1821 ; @0181F
loc_1821:
    jmp short loc_1823 ; @01821
loc_1823:
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @01823
    out 0x40,al ; @01825
    jmp short loc_1829 ; @01827
loc_1829:
    jmp short loc_182B ; @01829
loc_182B:
    jmp short loc_182D ; @0182B
loc_182D:
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0182D
    out 0x40,al ; @0182F
    jmp short loc_1833 ; @01831
loc_1833:
    jmp short loc_1835 ; @01833
loc_1835:
    jmp short loc_1837 ; @01835
loc_1837:
    sti ; @01837
    call sub_553D ; @01838
    call UpdateFixedWordPattern ; @0183B
GameTimerTail183E:
    db 0x32,0xd2 ; ENCODED: xor dl,dl (NASM chooses a different encoding) ; @0183E
    call PollInputState418C ; @01840
GameTimerAfterInput1843:
    inc byte [TimerCadenceCounter001C-GameDataImage] ; @01843
    mov al,[TimerCadenceCounter001C-GameDataImage] ; @01847
    and al,0x1 ; @0184A
    jz GameTimerAfterInt601861 ; @0184C
sub_184E:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @0184E
    jz GameTimerAfterInt601861 ; @01853
    test byte [SoundOptionBits-GameDataImage],0x1 ; @01855
    jz GameTimerAfterInt601861 ; @0185A
    mov ax,0x0 ; @0185C
GameTimerInt60185F:
    int 0x60 ; @0185F
GameTimerAfterInt601861:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @01861
    jnz loc_1874 ; @01866
sub_1868:
    test byte [SoundOptionBits-GameDataImage],0x3 ; @01868
    jz loc_1874 ; @0186D
sub_186F:
    mov ax,0x0 ; @0186F
GameTimerInt611872:
    int 0x61 ; @01872
loc_1874:
GameTimerAfterInt611874:
    call ProcessInputCommands3E6F ; @01874
GameTimerAfterCommands1877:
    cmp byte [PrivateIrqCounter2002-GameDataImage],0x0 ; @01877
    jnz loc_1881 ; @0187C
sub_187E:
    call RestoreVgaRegisterMirrors ; @0187E
loc_1881:
GameTimerAfterMirrors1881:
    cli ; @01881
    mov al,[TimerChainPhase1FE3-GameDataImage] ; @01882
    inc al ; @01885
    and al,0x3 ; @01887
    mov [TimerChainPhase1FE3-GameDataImage],al ; @01889
    jz GameTimerChain1893 ; @0188C
sub_188E:
    call SendMasterPicEoi ; @0188E
GameTimerAfterEoi1891:
    jmp short GameTimerChainReturn189D ; @01891
GameTimerChain1893:
    mov ax,0x189d ; @01893
    pushf ; @01896
    push cs ; @01897
    push ax ; @01898
ChecksumWindowEnd:
GameTimerFarChain1899:
    jmp far [SavedTimerVector-GameDataImage] ; @01899
GameTimerChainReturn189D:
    sti ; @0189D
    mov byte [TimerChainFlag1FCF-GameDataImage],0xff ; @0189E
    inc byte [TimerForegroundCounter1FCD-GameDataImage] ; @018A3
    popf ; @018A7
    pop di ; @018A8
    pop si ; @018A9
    pop bp ; @018AA
    pop bx ; @018AB
    pop dx ; @018AC
    pop cx ; @018AD
    pop es ; @018AE
    pop ds ; @018AF
    pop ax ; @018B0
GameTimerOuterIret18B1:
    iret ; @018B1
times -(($-$$) != 0x18b2) db 0
