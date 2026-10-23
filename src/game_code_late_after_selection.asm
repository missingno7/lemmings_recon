; Remaining input edge/selection suffix4085..410E; original order retained.
times -(($-$$) != 0x4085) db 0
HandleSelectorKeysAndEdgeScroll:
; CALLed only at 01A0. Scan 2C/2D cycle EntityActionSelector 2..9 when the
; status refresh counter 0084 is zero (see 0194 clear quirk). Otherwise pointer
; Y+8 signed below C0 with X exactly 8/148 scrolls the view 8 pixels (16 with
; button bit1) toward 10/500; both scroll paths and the 500 limit enter
; RebuildViewVisibilityMap by JMP/fallthrough, whose RET returns to 01A3.
; Right limit is an exact JZ 500 test; origins beyond 500 keep growing.
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @04085
    cmp al,0x2c ; @04088
    jnz loc_408F ; @0408A
    jmp short loc_40B5 ; @0408C
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @0408E
loc_408F:
SelectorKeyCheckNext:
    cmp al,0x2d ; @0408F
    jnz loc_4096 ; @04091
    jmp short loc_40CD ; @04093
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @04095
loc_4096:
EdgeScrollCheck:
    mov ax,[0x12] ; @04096
    add ax,0x8 ; @04099
    cmp ax,0xc0 ; @0409C
    jnl loc_40B4 ; @0409F
    mov ax,[0x10] ; @040A1
    cmp ax,0x8 ; @040A4
    jnz loc_40AC ; @040A7
    jmp loc_414F ; @040A9
loc_40AC:
EdgeScrollCheckRight:
    cmp ax,0x148 ; @040AC
    jnz loc_40B4 ; @040AF
    jmp short loc_40E5 ; @040B1
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @040B3
loc_40B4:
EdgeScrollNoneReturn:
    ret ; @040B4
loc_40B5:
SelectPreviousActionKey:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @040B5
    jnz loc_40CC ; @040BA
    dec byte [EntityActionSelector-GameDataImage] ; @040BC
    cmp byte [EntityActionSelector-GameDataImage],0x1 ; @040C0
    jnz loc_40CC ; @040C5
    mov byte [EntityActionSelector-GameDataImage],0x9 ; @040C7
loc_40CC:
SelectorKeyReturn:
    ret ; @040CC
loc_40CD:
SelectNextActionKey:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @040CD
    jnz loc_40CC ; @040D2
    inc byte [EntityActionSelector-GameDataImage] ; @040D4
    cmp byte [EntityActionSelector-GameDataImage],0xa ; @040D8
    jnz loc_40CC ; @040DD
    mov byte [EntityActionSelector-GameDataImage],0x2 ; @040DF
    ret ; @040E4
loc_40E5:
ScrollViewRight:
    mov ax,[0x0] ; @040E5
    cmp ax,0x500 ; @040E8
    jz RebuildViewVisibilityMap ; @040EB
    add ax,0x8 ; @040ED
    test word [InputButtonsWord-GameDataImage],0x2 ; @040F0
    jz loc_4100 ; @040F6
    cmp ax,0x500 ; @040F8
    jz loc_4100 ; @040FB
    add ax,0x8 ; @040FD
loc_4100:
ScrollViewRightStore:
    mov [0x0],ax ; @04100
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @04103
    shr dx,1 ; @04105
    shr dx,1 ; @04107
    shr dx,1 ; @04109
    mov [0x2],dx ; @0410B
times -(($-$$) != 0x410f) db 0 ; module end assertion
