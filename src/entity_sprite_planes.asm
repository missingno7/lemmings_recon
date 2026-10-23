; Maintained sprite callbacks 66D7..6BDA; physical order unchanged.

times -(($-$$) != 0x66d7) db 0 ; module start assertion
; CONTRACT: source DS=incoming CX; incoming DL is unchecked CL shift.
; Three-plane callbacks use live SS DI saves between masked and OR passes.
; First three entries count in BP; sixteen-row entry PUSHes/POPs AX per row.
; Mask/data SHR/RCR spills, all256 shift counts, DF strings and +29h pitch
; retain flags, SS aliases, ordered VGA latch/port/mirror phases and POP DS/RET.
DrawEntityShiftedSprite3Plane10:
    push ds ; @066D7
    mov ds,cx ; @066D8
    xchg dx,cx ; @066DA
    mov dx,0x3c4 ; @066DC
    mov ax,0xf02 ; @066DF
    mov [ss:0x8],ax ; @066E2
    out dx,ax ; @066E6
    mov dx,0x3ce ; @066E7
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @066EA
    mov [ss:0xa],ax ; @066EC
    out dx,ax ; @066F0
    mov ax,0xe01 ; @066F1
    mov [ss:0xc],ax ; @066F4
    out dx,ax ; @066F8
    mov ax,0x5 ; @066F9
    mov [ss:0x0],ax ; @066FC
    out dx,ax ; @06700
    mov ax,0x3 ; @06701
    mov [ss:0x2],ax ; @06704
    out dx,ax ; @06708
    mov ax,0xa000 ; @06709
    mov es,ax ; @0670C
    push di ; @0670E
    mov bp,0xa ; @0670F
loc_6712:
    push bp ; @06712
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06713
    push si ; @06714
    xchg al,ah ; @06715
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06717
    mov ax,[bx] ; @06719
    add bx,byte +0x2 ; @0671B
    xchg al,ah ; @0671E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06720
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06722
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06724
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06726
    jz loc_6736 ; @06728
loc_672A:
    shr si,1 ; @0672A
    rcr al,1 ; @0672C
    shr bp,1 ; @0672E
    rcr ah,1 ; @06730
    dec ch ; @06732
    jnz loc_672A ; @06734
loc_6736:
    push bx ; @06736
    push cx ; @06737
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06738
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @0673A
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0673C
    mov al,0x8 ; @0673E
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06740
    mov [ss:0xe],ax ; @06742
    out dx,ax ; @06746
    cli ; @06747
    mov al,[es:di] ; @06748
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0674B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0674D
    sti ; @0674E
    mov al,0x8 ; @0674F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06751
    mov [ss:0xe],ax ; @06753
    out dx,ax ; @06757
    cli ; @06758
    mov al,[es:di] ; @06759
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0675C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0675E
    sti ; @0675F
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06760
    mov al,0x8 ; @06762
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06764
    mov [ss:0xe],ax ; @06766
    out dx,ax ; @0676A
    cli ; @0676B
    mov al,[es:di] ; @0676C
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @0676F
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06771
    sti ; @06772
    add di,byte +0x29 ; @06773
    pop cx ; @06776
    pop bx ; @06777
    pop si ; @06778
    pop bp ; @06779
    dec bp ; @0677A
    jnz loc_6712 ; @0677B
    pop di ; @0677D
    push di ; @0677E
    mov ax,0x1 ; @0677F
    mov [ss:0xc],ax ; @06782
    out dx,ax ; @06786
    mov ax,0x1003 ; @06787
    mov [ss:0x2],ax ; @0678A
    out dx,ax ; @0678E
    mov ax,0xff08 ; @0678F
    mov [ss:0xe],ax ; @06792
    out dx,ax ; @06796
    mov dl,0xc4 ; @06797
    mov ax,0x202 ; @06799
    mov [ss:0x8],ax ; @0679C
    out dx,ax ; @067A0
    mov bp,0xa ; @067A1
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_67A4:
    lodsw ; @067A4
    xchg al,ah ; @067A5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @067A7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @067A9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @067AB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @067AD
    jz loc_67B9 ; @067AF
loc_67B1:
    shr bx,1 ; @067B1
    rcr al,1 ; @067B3
    dec ch ; @067B5
    jnz loc_67B1 ; @067B7
loc_67B9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @067B9
    cli ; @067BB
    mov al,[es:di] ; @067BC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @067BF
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @067C1
    mov al,[es:di] ; @067C2
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @067C5
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @067C7
    mov al,[es:di] ; @067C8
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @067CB
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @067CD
    sti ; @067CE
    add di,byte +0x29 ; @067CF
    dec bp ; @067D2
    jnz loc_67A4 ; @067D3
    pop di ; @067D5
    mov dx,0x3c4 ; @067D6
    mov ax,0x402 ; @067D9
    mov [ss:0x8],ax ; @067DC
    out dx,ax ; @067E0
    mov bp,0xa ; @067E1
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_67E4:
    lodsw ; @067E4
    xchg al,ah ; @067E5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @067E7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @067E9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @067EB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @067ED
    jz loc_67F9 ; @067EF
loc_67F1:
    shr bx,1 ; @067F1
    rcr al,1 ; @067F3
    dec ch ; @067F5
    jnz loc_67F1 ; @067F7
loc_67F9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @067F9
    cli ; @067FB
    mov al,[es:di] ; @067FC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @067FF
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06801
    mov al,[es:di] ; @06802
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06805
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06807
    mov al,[es:di] ; @06808
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0680B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0680D
    sti ; @0680E
    add di,byte +0x29 ; @0680F
    dec bp ; @06812
    jnz loc_67E4 ; @06813
    pop ds ; @06815
EntitySprite3Plane10Return:
    ret ; @06816
DrawEntityShiftedSprite3Plane13:
    push ds ; @06817
    mov ds,cx ; @06818
    xchg dx,cx ; @0681A
    mov dx,0x3c4 ; @0681C
    mov ax,0xf02 ; @0681F
    mov [ss:0x8],ax ; @06822
    out dx,ax ; @06826
    mov dx,0x3ce ; @06827
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0682A
    mov [ss:0xa],ax ; @0682C
    out dx,ax ; @06830
    mov ax,0xe01 ; @06831
    mov [ss:0xc],ax ; @06834
    out dx,ax ; @06838
    mov ax,0x5 ; @06839
    mov [ss:0x0],ax ; @0683C
    out dx,ax ; @06840
    mov ax,0x3 ; @06841
    mov [ss:0x2],ax ; @06844
    out dx,ax ; @06848
    mov ax,0xa000 ; @06849
    mov es,ax ; @0684C
    push di ; @0684E
    mov bp,0xd ; @0684F
loc_6852:
    push bp ; @06852
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06853
    push si ; @06854
    xchg al,ah ; @06855
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06857
    mov ax,[bx] ; @06859
    add bx,byte +0x2 ; @0685B
    xchg al,ah ; @0685E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06860
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06862
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06864
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06866
    jz loc_6876 ; @06868
loc_686A:
    shr si,1 ; @0686A
    rcr al,1 ; @0686C
    shr bp,1 ; @0686E
    rcr ah,1 ; @06870
    dec ch ; @06872
    jnz loc_686A ; @06874
loc_6876:
    push bx ; @06876
    push cx ; @06877
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06878
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @0687A
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0687C
    mov al,0x8 ; @0687E
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06880
    mov [ss:0xe],ax ; @06882
    out dx,ax ; @06886
    cli ; @06887
    mov al,[es:di] ; @06888
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0688B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0688D
    sti ; @0688E
    mov al,0x8 ; @0688F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06891
    mov [ss:0xe],ax ; @06893
    out dx,ax ; @06897
    cli ; @06898
    mov al,[es:di] ; @06899
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0689C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0689E
    sti ; @0689F
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @068A0
    mov al,0x8 ; @068A2
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @068A4
    mov [ss:0xe],ax ; @068A6
    out dx,ax ; @068AA
    cli ; @068AB
    mov al,[es:di] ; @068AC
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @068AF
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @068B1
    sti ; @068B2
    add di,byte +0x29 ; @068B3
    pop cx ; @068B6
    pop bx ; @068B7
    pop si ; @068B8
    pop bp ; @068B9
    dec bp ; @068BA
    jnz loc_6852 ; @068BB
    pop di ; @068BD
    push di ; @068BE
    mov ax,0x1 ; @068BF
    mov [ss:0xc],ax ; @068C2
    out dx,ax ; @068C6
    mov ax,0x1003 ; @068C7
    mov [ss:0x2],ax ; @068CA
    out dx,ax ; @068CE
    mov ax,0xff08 ; @068CF
    mov [ss:0xe],ax ; @068D2
    out dx,ax ; @068D6
    mov dl,0xc4 ; @068D7
    mov ax,0x202 ; @068D9
    mov [ss:0x8],ax ; @068DC
    out dx,ax ; @068E0
    mov bp,0xd ; @068E1
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_68E4:
    lodsw ; @068E4
    xchg al,ah ; @068E5
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @068E7
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @068E9
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @068EB
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @068ED
    jz loc_68F9 ; @068EF
loc_68F1:
    shr bx,1 ; @068F1
    rcr al,1 ; @068F3
    dec ch ; @068F5
    jnz loc_68F1 ; @068F7
loc_68F9:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @068F9
    cli ; @068FB
    mov al,[es:di] ; @068FC
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @068FF
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06901
    mov al,[es:di] ; @06902
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06905
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06907
    mov al,[es:di] ; @06908
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0690B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0690D
    sti ; @0690E
    add di,byte +0x29 ; @0690F
    dec bp ; @06912
    jnz loc_68E4 ; @06913
    pop di ; @06915
    mov dx,0x3c4 ; @06916
    mov ax,0x402 ; @06919
    mov [ss:0x8],ax ; @0691C
    out dx,ax ; @06920
    mov bp,0xd ; @06921
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_6924:
    lodsw ; @06924
    xchg al,ah ; @06925
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06927
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06929
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0692B
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @0692D
    jz loc_6939 ; @0692F
loc_6931:
    shr bx,1 ; @06931
    rcr al,1 ; @06933
    dec ch ; @06935
    jnz loc_6931 ; @06937
loc_6939:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06939
    cli ; @0693B
    mov al,[es:di] ; @0693C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @0693F
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06941
    mov al,[es:di] ; @06942
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06945
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06947
    mov al,[es:di] ; @06948
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0694B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0694D
    sti ; @0694E
    add di,byte +0x29 ; @0694F
    dec bp ; @06952
    jnz loc_6924 ; @06953
    pop ds ; @06955
EntitySprite3Plane13Return:
    ret ; @06956
DrawEntityShiftedSprite3Plane14:
    push ds ; @06957
    mov ds,cx ; @06958
    xchg dx,cx ; @0695A
    mov dx,0x3c4 ; @0695C
    mov ax,0xf02 ; @0695F
    mov [ss:0x8],ax ; @06962
    out dx,ax ; @06966
    mov dx,0x3ce ; @06967
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0696A
    mov [ss:0xa],ax ; @0696C
    out dx,ax ; @06970
    mov ax,0xe01 ; @06971
    mov [ss:0xc],ax ; @06974
    out dx,ax ; @06978
    mov ax,0x5 ; @06979
    mov [ss:0x0],ax ; @0697C
    out dx,ax ; @06980
    mov ax,0x3 ; @06981
    mov [ss:0x2],ax ; @06984
    out dx,ax ; @06988
    mov ax,0xa000 ; @06989
    mov es,ax ; @0698C
    push di ; @0698E
    mov bp,0xe ; @0698F
loc_6992:
    push bp ; @06992
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06993
    push si ; @06994
    xchg al,ah ; @06995
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06997
    mov ax,[bx] ; @06999
    add bx,byte +0x2 ; @0699B
    xchg al,ah ; @0699E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @069A0
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @069A2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @069A4
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @069A6
    jz EntitySprite3Plane14MaskedWrite ; @069A8
; Interior blocks of DrawEntityShiftedSprite3Plane14 (6957..6A96) down to 6A95:
; legacy lifter splits, not entries (only local branches/fall-throughs reach
; them; none is a known 715B callback target). Sibling callbacks keep plain
; loc_ labels. Pass 1 (map 0Fh, set/reset planes 1..3 = 0) shift step: CH=CL
; one-bit SHR/RCR steps move the byte-swapped data word (SI) and mask word (BP)
; right, spilling into AL (data) and AH (mask). CL is the unchecked 0..255 shift.
EntitySprite3Plane14MaskShift:
    shr si,1 ; @069AA
    rcr al,1 ; @069AC
    shr bp,1 ; @069AE
    rcr ah,1 ; @069B0
    dec ch ; @069B2
    jnz EntitySprite3Plane14MaskShift ; @069B4
; Pass 1 row write: three bit-mask/latch-read/STOSB groups (mask BH/data CH,
; mask BL/data CL, mask spill/data spill), each under its own CLI..STI, then
; ADD DI,29h. Restores the stacked CX/BX/SI/BP; DEC BP of the saved row count.
EntitySprite3Plane14MaskedWrite:
    push bx ; @069B6
    push cx ; @069B7
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @069B8
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @069BA
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @069BC
    mov al,0x8 ; @069BE
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @069C0
    mov [ss:0xe],ax ; @069C2
    out dx,ax ; @069C6
    cli ; @069C7
    mov al,[es:di] ; @069C8
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @069CB
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @069CD
    sti ; @069CE
    mov al,0x8 ; @069CF
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @069D1
    mov [ss:0xe],ax ; @069D3
    out dx,ax ; @069D7
    cli ; @069D8
    mov al,[es:di] ; @069D9
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @069DC
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @069DE
    sti ; @069DF
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @069E0
    mov al,0x8 ; @069E2
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @069E4
    mov [ss:0xe],ax ; @069E6
    out dx,ax ; @069EA
    cli ; @069EB
    mov al,[es:di] ; @069EC
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @069EF
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @069F1
    sti ; @069F2
    add di,byte +0x29 ; @069F3
    pop cx ; @069F6
    pop bx ; @069F7
    pop si ; @069F8
    pop bp ; @069F9
    dec bp ; @069FA
    jnz loc_6992 ; @069FB
; Pass 2 setup (after 14 masked rows): DI reread from the live stack, set/reset
; off, GC3=10h (OR), bit mask FFh, map mask 02h (plane 1), BP=0Eh rows.
EntitySprite3Plane14OrPlane1:
    pop di ; @069FD
    push di ; @069FE
    mov ax,0x1 ; @069FF
    mov [ss:0xc],ax ; @06A02
    out dx,ax ; @06A06
    mov ax,0x1003 ; @06A07
    mov [ss:0x2],ax ; @06A0A
    out dx,ax ; @06A0E
    mov ax,0xff08 ; @06A0F
    mov [ss:0xe],ax ; @06A12
    out dx,ax ; @06A16
    mov dl,0xc4 ; @06A17
    mov ax,0x202 ; @06A19
    mov [ss:0x8],ax ; @06A1C
    out dx,ax ; @06A20
    mov bp,0xe ; @06A21
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_6A24:
    lodsw ; @06A24
    xchg al,ah ; @06A25
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06A27
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06A29
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06A2B
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06A2D
    jz EntitySprite3Plane14OrPlane1Write ; @06A2F
; Pass 2 shift step: data word shifted right by CL, spill into AL.
EntitySprite3Plane14OrPlane1Shift:
    shr bx,1 ; @06A31
    rcr al,1 ; @06A33
    dec ch ; @06A35
    jnz EntitySprite3Plane14OrPlane1Shift ; @06A37
; Pass 2 row write: latch read before each of three OR writes, whole row under
; one CLI..STI, ADD DI,29h.
EntitySprite3Plane14OrPlane1Write:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06A39
    cli ; @06A3B
    mov al,[es:di] ; @06A3C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06A3F
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06A41
    mov al,[es:di] ; @06A42
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06A45
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06A47
    mov al,[es:di] ; @06A48
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06A4B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06A4D
    sti ; @06A4E
    add di,byte +0x29 ; @06A4F
    dec bp ; @06A52
    jnz loc_6A24 ; @06A53
; Pass 3 setup: POP DI (final saved destination), DX=3C4h, map mask 04h
; (plane 2), BP=0Eh rows.
EntitySprite3Plane14OrPlane2:
    pop di ; @06A55
    mov dx,0x3c4 ; @06A56
    mov ax,0x402 ; @06A59
    mov [ss:0x8],ax ; @06A5C
    out dx,ax ; @06A60
    mov bp,0xe ; @06A61
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_6A64:
    lodsw ; @06A64
    xchg al,ah ; @06A65
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06A67
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06A69
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06A6B
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06A6D
    jz EntitySprite3Plane14OrPlane2Write ; @06A6F
; Pass 3 shift step (as pass 2).
EntitySprite3Plane14OrPlane2Shift:
    shr bx,1 ; @06A71
    rcr al,1 ; @06A73
    dec ch ; @06A75
    jnz EntitySprite3Plane14OrPlane2Shift ; @06A77
; Pass 3 row write (as pass 2).
EntitySprite3Plane14OrPlane2Write:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06A79
    cli ; @06A7B
    mov al,[es:di] ; @06A7C
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06A7F
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06A81
    mov al,[es:di] ; @06A82
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06A85
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06A87
    mov al,[es:di] ; @06A88
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06A8B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06A8D
    sti ; @06A8E
    add di,byte +0x29 ; @06A8F
    dec bp ; @06A92
    jnz loc_6A64 ; @06A93
; Exit: POP DS restores the caller DS saved at 6957, then RET 6A96.
EntitySprite3Plane14RestoreDs:
    pop ds ; @06A95
EntitySprite3Plane14Return:
    ret ; @06A96
DrawEntityShiftedSprite3Plane16:
    push ds ; @06A97
    mov ds,cx ; @06A98
    xchg dx,cx ; @06A9A
    mov dx,0x3c4 ; @06A9C
    mov ax,0xf02 ; @06A9F
    mov [ss:0x8],ax ; @06AA2
    out dx,ax ; @06AA6
    mov dx,0x3ce ; @06AA7
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06AAA
    mov [ss:0xa],ax ; @06AAC
    out dx,ax ; @06AB0
    mov ax,0xe01 ; @06AB1
    mov [ss:0xc],ax ; @06AB4
    out dx,ax ; @06AB8
    mov ax,0x5 ; @06AB9
    mov [ss:0x0],ax ; @06ABC
    out dx,ax ; @06AC0
    mov ax,0x3 ; @06AC1
    mov [ss:0x2],ax ; @06AC4
    out dx,ax ; @06AC8
    mov ax,0xa000 ; @06AC9
    mov es,ax ; @06ACC
    push di ; @06ACE
    mov ax,0x10 ; @06ACF
loc_6AD2:
    push ax ; @06AD2
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06AD3
    push si ; @06AD4
    xchg al,ah ; @06AD5
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @06AD7
    mov ax,[bx] ; @06AD9
    add bx,byte +0x2 ; @06ADB
    xchg al,ah ; @06ADE
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06AE0
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06AE2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @06AE4
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06AE6
    jz loc_6AF6 ; @06AE8
loc_6AEA:
    shr si,1 ; @06AEA
    rcr al,1 ; @06AEC
    shr bp,1 ; @06AEE
    rcr ah,1 ; @06AF0
    dec ch ; @06AF2
    jnz loc_6AEA ; @06AF4
loc_6AF6:
    push bx ; @06AF6
    push cx ; @06AF7
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06AF8
    db 0x8b,0xce ; ENCODED: mov cx,si (NASM chooses a different encoding) ; @06AFA
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @06AFC
    mov al,0x8 ; @06AFE
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06B00
    mov [ss:0xe],ax ; @06B02
    out dx,ax ; @06B06
    cli ; @06B07
    mov al,[es:di] ; @06B08
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06B0B
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06B0D
    sti ; @06B0E
    mov al,0x8 ; @06B0F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @06B11
    mov [ss:0xe],ax ; @06B13
    out dx,ax ; @06B17
    cli ; @06B18
    mov al,[es:di] ; @06B19
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @06B1C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06B1E
    sti ; @06B1F
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @06B20
    mov al,0x8 ; @06B22
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @06B24
    mov [ss:0xe],ax ; @06B26
    out dx,ax ; @06B2A
    cli ; @06B2B
    mov al,[es:di] ; @06B2C
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06B2F
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06B31
    sti ; @06B32
    add di,byte +0x29 ; @06B33
    pop cx ; @06B36
    pop bx ; @06B37
    pop si ; @06B38
    pop ax ; @06B39
    dec ax ; @06B3A
    jnz loc_6AD2 ; @06B3B
    pop di ; @06B3D
    push di ; @06B3E
    mov ax,0x1 ; @06B3F
    mov [ss:0xc],ax ; @06B42
    out dx,ax ; @06B46
    mov ax,0x1003 ; @06B47
    mov [ss:0x2],ax ; @06B4A
    out dx,ax ; @06B4E
    mov ax,0xff08 ; @06B4F
    mov [ss:0xe],ax ; @06B52
    out dx,ax ; @06B56
    mov dl,0xc4 ; @06B57
    mov ax,0x202 ; @06B59
    mov [ss:0x8],ax ; @06B5C
    out dx,ax ; @06B60
    mov ax,0x10 ; @06B61
loc_6B64:
    push ax ; @06B64
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06B65
    xchg al,ah ; @06B66
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06B68
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06B6A
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06B6C
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06B6E
    jz loc_6B7A ; @06B70
loc_6B72:
    shr bx,1 ; @06B72
    rcr al,1 ; @06B74
    dec ch ; @06B76
    jnz loc_6B72 ; @06B78
loc_6B7A:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06B7A
    cli ; @06B7C
    mov al,[es:di] ; @06B7D
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06B80
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06B82
    mov al,[es:di] ; @06B83
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06B86
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06B88
    mov al,[es:di] ; @06B89
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06B8C
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06B8E
    sti ; @06B8F
    add di,byte +0x29 ; @06B90
    pop ax ; @06B93
    dec ax ; @06B94
    jnz loc_6B64 ; @06B95
    pop di ; @06B97
    mov dx,0x3c4 ; @06B98
    mov ax,0x402 ; @06B9B
    mov [ss:0x8],ax ; @06B9E
    out dx,ax ; @06BA2
    mov ax,0x10 ; @06BA3
loc_6BA6:
    push ax ; @06BA6
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @06BA7
    xchg al,ah ; @06BA8
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @06BAA
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @06BAC
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @06BAE
    db 0x22,0xed ; ENCODED: and ch,ch (NASM chooses a different encoding) ; @06BB0
    jz loc_6BBC ; @06BB2
loc_6BB4:
    shr bx,1 ; @06BB4
    rcr al,1 ; @06BB6
    dec ch ; @06BB8
    jnz loc_6BB4 ; @06BBA
loc_6BBC:
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @06BBC
    cli ; @06BBE
    mov al,[es:di] ; @06BBF
    db 0x8a,0xc7 ; ENCODED: mov al,bh (NASM chooses a different encoding) ; @06BC2
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06BC4
    mov al,[es:di] ; @06BC5
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @06BC8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06BCA
    mov al,[es:di] ; @06BCB
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @06BCE
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @06BD0
    sti ; @06BD1
    add di,byte +0x29 ; @06BD2
    pop ax ; @06BD5
    dec ax ; @06BD6
    jnz loc_6BA6 ; @06BD7
    pop ds ; @06BD9
EntitySprite3Plane16Return:
    ret ; @06BDA
times -(($-$$) != 0x6bdb) db 0 ; module end assertion
