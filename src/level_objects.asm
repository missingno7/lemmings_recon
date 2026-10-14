; Maintained image span 0378A..03943; live level-object helpers.
; Reconstruction module, not a historical linker claim. See docs/object-records.md.
%if ($-$$) != 0x378a
    %error "level_objects start moved"
%endif
; RECORD HANDOFF: main DS is also copied to ES.32 eight-byte definitions at0FEB
; select28-byte ground records by their big-endian word at+4. Low16-bit MUL/add
; chooses the live source; no type-index check. Destination17CB..1B4A is32 slots.
; A zero first definition word skips the copy, leaving stale destination bytes.
; Incoming DF controls REP MOVSB; SI/DI/CX restores read the original live stack.
; This working array adjoins the ground load at1B4B; it is not separate C state.
; Native core and bounded live saves/return aliases: c/object_graphics.c.
CopyLevelObjectGraphicsRecords:
    push ds ; @0378A
    pop es ; @0378B
    lea bx,[LevelObjectDefinitions-GameDataImage] ; @0378C
    lea si,[GroundResourceBuffer-GameDataImage] ; @03790
    lea di,[LevelObjectGraphicsRecords-GameDataImage] ; @03794
    mov cx,0x20 ; @03798
loc_379B:
    mov ah,[bx] ; @0379B
    mov al,[bx+0x1] ; @0379D
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @037A0
    jz loc_37B9 ; @037A2
    mov ah,[bx+0x4] ; @037A4
    mov al,[bx+0x5] ; @037A7
    push si ; @037AA
    push cx ; @037AB
    push di ; @037AC
    mov cx,0x1c ; @037AD
    mul cx ; @037B0
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @037B2
    rep movsb ; @037B4
    pop di ; @037B6
    pop cx ; @037B7
    pop si ; @037B8
loc_37B9:
    add bx,byte +0x8 ; @037B9
    add di,byte +0x1c ; @037BC
    loop loc_379B ; @037BF
    ret ; @037C1
; OBJECT INTERACTION CELLS: first16 eight-byte definitions, no type bounds check.
; BE type*28 selects ground metadata; zero BE X skips the rectangle. Base SS offset
; =12h+(X>>2+LEtemplate[0E])+416*(Y>>2+LEtemplate[10]-1), wrapped16.
; Cell value=(definition ordinal<<4)|template[14]. Byte dimensions[12]/[13]
; are decrement loops: zero means256 writes/rows. Row-save words remain live inSS.
; SS is also the stack and VGA-register cache; don't substitute a separate map.
sub_37C2:
    lea di,[LevelObjectDefinitions-GameDataImage] ; @037C2
    mov cx,0x10 ; @037C6
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @037C9
loc_37CB:
    mov ah,[di+0x4] ; @037CB
    mov al,[di+0x5] ; @037CE
    mov dx,0x1c ; @037D1
    mul dx ; @037D4
    lea si,[GroundResourceBuffer-GameDataImage] ; @037D6
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @037DA
    mov ah,[di] ; @037DC
    mov al,[di+0x1] ; @037DE
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @037E1
    jz loc_382F ; @037E3
    shr ax,1 ; @037E5
    shr ax,1 ; @037E7
    add ax,[si+0xe] ; @037E9
    mov bh,[di+0x2] ; @037EC
    mov bl,[di+0x3] ; @037EF
    shr bx,1 ; @037F2
    shr bx,1 ; @037F4
    add bx,[si+0x10] ; @037F6
    dec bx ; @037F9
    push ax ; @037FA
    mov ax,0x1a0 ; @037FB
    mul bx ; @037FE
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @03800
    pop ax ; @03802
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @03803
    add bx,byte +0x12 ; @03805
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @03808
    shl ax,1 ; @0380A
    shl ax,1 ; @0380C
    shl ax,1 ; @0380E
    shl ax,1 ; @03810
    or al,[si+0x14] ; @03812
    mov dh,[si+0x12] ; @03815
    mov dl,[si+0x13] ; @03818
loc_381B:
    push dx ; @0381B
    push bx ; @0381C
loc_381D:
    mov [ss:bx],al ; @0381D
    inc bx ; @03820
    dec dh ; @03821
    jnz loc_381D ; @03823
    pop bx ; @03825
    pop dx ; @03826
    add bx,0x1a0 ; @03827
    dec dl ; @0382B
    jnz loc_381B ; @0382D
loc_382F:
    add di,byte +0x8 ; @0382F
    inc bp ; @03832
    dec cx ; @03833
    jz loc_3838 ; @03834
    jmp short loc_37CB ; @03836
loc_3838:
    ret ; @03838
; STEEL INTERACTION CELLS:32 four-byte records atDS172B, skip only if both words0.
; X coordinate combines AH and AL bit7; row is AL&7F. DH high/low nibbles encode
; width/height minus1 (each1..16). Record byte3 participates only in the zero check.
; Writes byte9 at liveSS cells with416-byte row stride, using live stack row saves.
sub_3839:
    lea di,[LevelSteelDefinitions-GameDataImage] ; @03839
    mov cx,0x20 ; @0383D
loc_3840:
    mov ah,[di] ; @03840
    mov al,[di+0x1] ; @03842
    mov dh,[di+0x2] ; @03845
    mov dl,[di+0x3] ; @03848
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @0384B
    db 0x0b,0xda ; ENCODED: or bx,dx (NASM chooses a different encoding) ; @0384D
    jz loc_3899 ; @0384F
    db 0x8a,0xd6 ; ENCODED: mov dl,dh (NASM chooses a different encoding) ; @03851
    and dl,0xf ; @03853
    shr dh,1 ; @03856
    shr dh,1 ; @03858
    shr dh,1 ; @0385A
    shr dh,1 ; @0385C
    and dh,0xf ; @0385E
    push dx ; @03861
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @03862
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @03864
    and bl,0x7f ; @03866
    db 0x8a,0xd0 ; ENCODED: mov dl,al (NASM chooses a different encoding) ; @03869
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0386B
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0386D
    rol dl,1 ; @0386F
    rcl ax,1 ; @03871
    push ax ; @03873
    mov ax,0x1a0 ; @03874
    mul bx ; @03877
    pop bx ; @03879
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0387A
    add bx,byte +0x12 ; @0387C
    pop dx ; @0387F
    add dx,0x101 ; @03880
loc_3884:
    push dx ; @03884
    push bx ; @03885
loc_3886:
    mov byte [ss:bx],0x9 ; @03886
    inc bx ; @0388A
    dec dh ; @0388B
    jnz loc_3886 ; @0388D
    pop bx ; @0388F
    pop dx ; @03890
    add bx,0x1a0 ; @03891
    dec dl ; @03895
    jnz loc_3884 ; @03897
loc_3899:
    add di,byte +0x4 ; @03899
    loop loc_3840 ; @0389C
    ret ; @0389E
; TYPE-ONE COORDINATES: scans32 big-endian definitions, compares full type word+4
; to1 (no first-word presence check). Writes wrapped X+24,Y+30 pairs atDS:0E98.
; Counts0..3 fill four slots with original patterns; counts>=4 are not clamped.
; Default BUG:393A storesY at+0A,393D overwrites it withX at+0A; +0C stays stale.
; Spawn consumer30DB..3100 indexes only four pairs, but that is not a producer bound.
; Native core/default-bug/full-count comparisons: c/object_coordinates.c.
CollectTypeOneObjectCoordinates:
    lea si,[LevelObjectDefinitions-GameDataImage] ; @0389F
    lea bx,[TypeOneObjectCoordinates-GameDataImage] ; @038A3
    mov cx,0x20 ; @038A7
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @038AA
loc_38AC:
    mov ah,[si+0x4] ; @038AC
    mov al,[si+0x5] ; @038AF
    cmp ax,0x1 ; @038B2
    jnz loc_38D1 ; @038B5
    mov ah,[si] ; @038B7
    mov al,[si+0x1] ; @038B9
    add ax,0x18 ; @038BC
    mov [bx],ax ; @038BF
    mov ah,[si+0x2] ; @038C1
    mov al,[si+0x3] ; @038C4
    add ax,0x1e ; @038C7
    mov [bx+0x2],ax ; @038CA
    add bx,byte +0x4 ; @038CD
    inc bp ; @038D0
loc_38D1:
    add si,byte +0x8 ; @038D1
    loop loc_38AC ; @038D4
    db 0x23,0xed ; ENCODED: and bp,bp (NASM chooses a different encoding) ; @038D6
    jz loc_3926 ; @038D8
    cmp bp,byte +0x1 ; @038DA
    jz loc_38EA ; @038DD
    cmp bp,byte +0x2 ; @038DF
    jz loc_3902 ; @038E2
    cmp bp,byte +0x3 ; @038E4
    jz loc_391A ; @038E7
    ret ; @038E9
loc_38EA:
    mov ax,[bx-0x4] ; @038EA
    mov cx,[bx-0x2] ; @038ED
    mov [bx],ax ; @038F0
    mov [bx+0x2],cx ; @038F2
    mov [bx+0x4],ax ; @038F5
    mov [bx+0x6],cx ; @038F8
    mov [bx+0x8],ax ; @038FB
    mov [bx+0xa],cx ; @038FE
    ret ; @03901
loc_3902:
    mov ax,[bx-0x4] ; @03902
    mov cx,[bx-0x2] ; @03905
    mov [bx],ax ; @03908
    mov [bx+0x2],cx ; @0390A
    mov ax,[bx-0x8] ; @0390D
    mov cx,[bx-0x6] ; @03910
    mov [bx+0x4],ax ; @03913
    mov [bx+0x6],cx ; @03916
    ret ; @03919
loc_391A:
    mov ax,[bx-0x8] ; @0391A
    mov cx,[bx-0x6] ; @0391D
    mov [bx],ax ; @03920
    mov [bx+0x2],cx ; @03922
    ret ; @03925
loc_3926:
    mov ax,0x100 ; @03926
    mov cx,0x10 ; @03929
    mov [bx],ax ; @0392C
    mov [bx+0x2],cx ; @0392E
    mov [bx+0x4],ax ; @03931
    mov [bx+0x6],cx ; @03934
    mov [bx+0x8],ax ; @03937
    mov [bx+0xa],cx ; @0393A
    ; Original repeated offset: do not repair to+0C.
    mov [bx+0xa],ax ; @0393D
    mov [bx+0xe],cx ; @03940
    ret ; @03943
%if ($-$$) != 0x3944
    %error "level_objects end moved"
%endif
