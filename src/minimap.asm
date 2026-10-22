; Maintained closed minimap cluster 0796F..07A59; live segments and stack aliases.
times -(($-$$) != 0x796f) db 0 ; module start assertion
; Minimap column: live DS:0056 adds 16, signed JL against 208; unchecked wrap.
; Clears 20 CS bytes using incoming DF, accumulates 20 rows, writes only 19.
; ES=A000 read mode1/color compare8/care8, then mode0 writes with plane3 SR=0.
; SS owns mirror words and every live CALL/save/RET frame; DS restored from stack.
; Clear overlap, inclusive offsets:7970 sets DI=83C1,797B issues ten STOSW.
; With unaliased PUSH CS/POP ES, DF=0 writes CS:83C1..83D4; DF=1 writes
; CS:83AF..83C2 (words at83C1,83BF,...,83AF), including checksum instructions
; 83AF..83B6, UNKNOWN83B7, sample result83B8, phase83B9, accumulator83BA,
; cursor83BB..BC, sample result83BD and IRQ gate83BE. See checksum.asm/code_tail.
; It does NOT reset checksum cursor/phase to the InitializeCodeChecksum values.
; Twenty sampled bytes83C1..83D4 then OR into live scratch; display reads only
; 83C1..83D3. DF=1 therefore leaves rows83C3..83D4 stale before accumulation.
; PUSH DS precedes clear; PUSH CS/POP ES and POP DS are live SS accesses: a
; device/alias stack can change ES away from CS or DS on exit. No mirror frame
; substitution is valid. Sample direct entry can write arbitrary CS:BX.
; Static callers377D (13-call initialization loop) and3AC8 (status, callers
; 01C2/049E) establish no local CLD. Main STD1BB0 is followed by CALL1D2E,
; whose1D34 CLD and normal1C78 CLD prevent a simple decoder-return DF=1 claim.
; That observation is not a whole-program DF proof: entry FLAGS, service/IRET,
; protected paths and live stack aliases remain unclosed. Keep DF=1 supported
; as a raw-entry footprint and game caller DF domain explicitly OPEN.
; CONDITIONAL: fixed20/19 scratch lifetime assumes intact loop saves, ES=CS
; during clear and no asynchronous writers. Original VGA read-mode/plane/IRQ
; ownership remains an obligation; constructed fixture services cannot close it.
UpdateMinimapColumn:
    push ds ; @0796F
    lea di,[MinimapColumnBits] ; @07970
    mov cx,0xa ; @07974
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07977
    push cs ; @07979
    pop es ; @0797A
    rep stosw ; @0797B
    mov si,[MinimapSourceColumnByteOffset-GameDataImage] ; @0797D
    add si,byte +0x10 ; @07981
    cmp si,0xd0 ; @07984
    jl loc_798C ; @07988
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0798A
loc_798C:
    mov [MinimapSourceColumnByteOffset-GameDataImage],si ; @0798C
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @07990
    add si,0xd00 ; @07992
    add si,0x4a40 ; @07996
    shr di,1 ; @0799A
    shr di,1 ; @0799C
    shr di,1 ; @0799E
    shr di,1 ; @079A0
    add di,0xd320 ; @079A2
    mov dx,0xa000 ; @079A6
    mov es,dx ; @079A9
    mov dx,0x3c4 ; @079AB
    mov ax,0xf02 ; @079AE
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @079B1
    out dx,ax ; @079B5
    mov dx,0x3ce ; @079B6
    mov ax,0x600 ; @079B9
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @079BC
    out dx,ax ; @079C0
    mov ax,0x801 ; @079C1
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @079C4
    out dx,ax ; @079C8
    mov ax,0x805 ; @079C9
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @079CC
    out dx,ax ; @079D0
    mov ax,0x3 ; @079D1
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @079D4
    out dx,ax ; @079D8
    mov ax,0x807 ; @079D9
    mov [ss:VgaColorCareMirror-RuntimeStackFrame],ax ; @079DC
    out dx,ax ; @079E0
    mov ax,0x802 ; @079E1
    mov [ss:VgaColorCompareMirror-RuntimeStackFrame],ax ; @079E4
    out dx,ax ; @079E8
    mov ax,0xff08 ; @079E9
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @079EC
    out dx,ax ; @079F0
    mov cx,0x14 ; @079F1
    lea bx,[MinimapColumnBits] ; @079F4
loc_79F8:
    call AccumulateMinimapRow ; @079F8
MinimapColumnAfterRow:
    add si,0x680 ; @079FB
    inc bx ; @079FF
    loop loc_79F8 ; @07A00
    mov dx,0x3ce ; @07A02
    mov ax,0x5 ; @07A05
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @07A08
    out dx,ax ; @07A0C
    mov cx,0x13 ; @07A0D
    lea bx,[MinimapColumnBits] ; @07A10
loc_7A14:
    mov ah,[cs:bx] ; @07A14
    mov al,[es:di] ; @07A17
    mov [es:di],ah ; @07A1A
    add di,byte +0xd ; @07A1D
    inc bx ; @07A20
    loop loc_7A14 ; @07A21
    pop ds ; @07A23
    ret ; @07A24
; Eight nominal samples, mask 80..01. Saved CX/SI and each callee RET stay live.
; A changed saved CX can extend the unchecked LOOP; no fixed-count replacement.
AccumulateMinimapRow:
    push cx ; @07A25
    push si ; @07A26
    mov dl,0x80 ; @07A27
    mov cx,0x8 ; @07A29
loc_7A2C:
    call AccumulateMinimapSample ; @07A2C
MinimapRowAfterSample:
    add si,byte +0x2 ; @07A2F
    shr dl,1 ; @07A32
    loop loc_7A2C ; @07A34
    pop si ; @07A36
    pop cx ; @07A37
    ret ; @07A38
; ES:SI and ES:(SI+1)&FFFF are separate byte reads after PUSH CX.
; Count 16 bits; if population>8, OR incoming DL into live CS:BX. AX=0.
; DH=population; CX restored from live SS. CMP flags on skip, OR flags on write.
AccumulateMinimapSample:
    push cx ; @07A39
    mov ah,[es:si] ; @07A3A
    mov al,[es:si+0x1] ; @07A3D
    mov cx,0x10 ; @07A41
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07A44
loc_7A46:
    shr ax,1 ; @07A46
    jnc loc_7A4C ; @07A48
    inc dh ; @07A4A
loc_7A4C:
    loop loc_7A46 ; @07A4C
    cmp dh,0x8 ; @07A4E
    jg loc_7A55 ; @07A51
    pop cx ; @07A53
    ret ; @07A54
loc_7A55:
    or [cs:bx],dl ; @07A55
    pop cx ; @07A58
    ret ; @07A59
times -(($-$$) != 0x7a5a) db 0 ; module end assertion
