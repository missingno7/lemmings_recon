; Maintained7BB8..7C66 object drawing and shared animation tail; exact physical order.
times -(($-$$) != 0x7bb8) db 0 ; module start assertion
; DRAW: initialCX32, live savedSI/DI/CX after each8822 far return; no hard cap.
; Read live scroll after PUSHes; big-endian X/Y/flags and unchecked graphics.
; Clearing flagbit0 forces the original unshifted renderer selection even if
; X is not byte-aligned. No resource-segment initialization occurs here.
; Child-returned DS/ES/general state and actual IP/CS control continuation.
; Scoped native caller/animation handoff; device timing and IRQ seams stay open.
DrawLevelObjectGraphics:
    lea si,[LevelObjectGraphicsRecords-GameDataImage] ; @07BB8
    lea di,[LevelObjectDefinitions-GameDataImage] ; @07BBC
    mov cx,0x20 ; @07BC0
loc_7BC3:
    mov ah,[di] ; @07BC3
    mov al,[di+0x1] ; @07BC5
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07BC8
    jz loc_7C01 ; @07BCA
    push cx ; @07BCC
    push di ; @07BCD
    push si ; @07BCE
    sub ax,[LevelViewOriginPixels-GameDataImage] ; @07BCF
    add ax,0x10 ; @07BD3
    mov bh,[byte di+FirstObjectDefinitionY-LevelObjectDefinitions] ; @07BD6
    mov bl,[byte di+FirstObjectDefinitionY+1-LevelObjectDefinitions] ; @07BD9
    mov dh,[byte di+FirstObjectDefinitionFlags-LevelObjectDefinitions] ; @07BDC
    mov dl,[byte di+FirstObjectDefinitionFlags+1-LevelObjectDefinitions] ; @07BDF
    db 0x8b,0xea ; ENCODED: mov bp,dx (NASM chooses a different encoding) ; @07BE2
; U1 caller-specific stack: AND BP,FFFE clears bit0, so8822 selects unshifted rendering. Its14-byte unshifted bodies are smaller than CALL9A15+18=20. 01B9 nearCALL2 +caller CX/DI/SI6 +farCALL4 +dirty child20 =32 below foreground4AF4, reaching4AD4 at9A75 with ordinaryIF1. Generic shifted-masked24 cannot be charged to this caller. During0498 initialization the live00FB CALL03E7 adds2, giving34; game08 was installed at0492. These are intact known-path implications, not callback/provider/global stack closure.
    and bp,byte -0x2 ; @07BE4
    mov dl,[byte si+FirstObjectGraphicsWidth-LevelObjectGraphicsRecords] ; @07BE7
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07BEA
    mov cl,[byte si+FirstObjectGraphicsHeight-LevelObjectGraphicsRecords] ; @07BEC
    mov di,[byte si+FirstObjectGraphicsMaskOffset-LevelObjectGraphicsRecords] ; @07BEF
    mov si,[byte si+FirstObjectGraphicsFrameOffset-LevelObjectGraphicsRecords] ; @07BF2
    db 0x03,0xfe ; ENCODED: add di,si (NASM chooses a different encoding) ; @07BF5
    mov ch,0x4 ; @07BF7
    call 0x0:0x8822 ; @07BF9
DrawLevelObjectGraphicsAfterBitmap:
    pop si ; @07BFE
    pop di ; @07BFF
    pop cx ; @07C00
loc_7C01:
    add di,byte +0x8 ; @07C01
    add si,byte +0x1c ; @07C04
    loop loc_7BC3 ; @07C07
DrawLevelObjectGraphicsReturn:
    ret ; @07C09
; V4 FIELD HANDOFF: active working records are copied from live GROUND types
; at setup/redraw. Opaque+0A..0D/+19..1A has no established typed consumer.
; Animation writes frame before live stride/base reads, then+17 and flags.
; Reset occurs only on equal limit; no >= clamp; limit0 retains byte wrap.
; This type gate uses definition low+5, while389F compares full BE word1.
; Malformed0101 therefore differs between consumers. Trigger2FCE sets bit1;
; 2FE9 reads working+1B and sends the full nonzero byte as AH04 INT61.
; AdLib's validation belongs to051C, not the working-record schema.
; V1 Mixed object/entity rule and all84..98 field hits are in level_objects.asm/V1 report. Callback85 high=lo(O01);87=B05 including staleBX;8A=O09;8C low=hi(B0D),high=F0D;8F low=hi(O11);91 low=F15. Fresh retained8A descriptor givesF09*(F800|Y-high)+003C. No template immutability or actual gate/survival proof.
; T2 UNCONDITIONAL:7C4C/7C59/7C5C intersect entity callback bytes85:17FE,87:1857/1858,8A:18DE/18DF,8C:1938/1939,8F:19BF,91:1A19. Respect definition/flag/frame gates and staleBX. Frame01B6 precedes entity draw01BC;actual high-spill survival UNRESOLVED.
; ANIMATION:32 big-endian definitions stride8; mutable graphics stride1C.
; ZeroX stores staleBX at+00, without loading flags; type gating reads only+05.
; Live0055 must equalFF for low-type1. Flagsbit1 enables byteINC/equality wrap;
; bit0 clears bit1 only at that wrap. No >= clamp; limit0 keeps byte overflow.
; Frame+02 is stored before live stride+06 and base+15 reads; MUL returns DX:AX.
; The+17 offset and flags stores follow. DS/ES/SS and DF/IF stay live/unchanged.
; NearRET owns actual SS:SP after all writes, including record/return aliases.
AdvanceLevelObjectAnimationRecords:
    lea si,[LevelObjectGraphicsRecords-GameDataImage] ; @07C0A
    lea di,[LevelObjectDefinitions-GameDataImage] ; @07C0E
    mov cx,0x20 ; @07C12
loc_7C15:
    mov ah,[di] ; @07C15
    mov al,[di+0x1] ; @07C17
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @07C1A
    jz loc_7C5C ; @07C1C
    mov dl,[di+0x5] ; @07C1E
    cmp dl,0x1 ; @07C21
    jnz loc_7C2D ; @07C24
    cmp byte [EntityCreationGate-GameDataImage],0xff ; @07C26
    jnz loc_7C5E ; @07C2B
loc_7C2D:
    mov bx,[si] ; @07C2D
    test bx,0x2 ; @07C2F
    jz loc_7C5C ; @07C33
    mov al,[byte si+FirstObjectGraphicsAnimationFrame-LevelObjectGraphicsRecords] ; @07C35
    mov ah,[byte si+FirstObjectGraphicsAnimationLimit-LevelObjectGraphicsRecords] ; @07C38
    inc al ; @07C3B
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @07C3D
    jnz loc_7C4C ; @07C3F
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @07C41
    test bx,0x1 ; @07C43
    jz loc_7C4C ; @07C47
    and bx,byte -0x3 ; @07C49
loc_7C4C:
    mov [byte si+FirstObjectGraphicsAnimationFrame-LevelObjectGraphicsRecords],al ; @07C4C
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07C4F
    mov bp,[byte si+FirstObjectGraphicsFrameStride-LevelObjectGraphicsRecords] ; @07C51
    mul bp ; @07C54
    add ax,[byte si+FirstObjectGraphicsAnimationBase-LevelObjectGraphicsRecords] ; @07C56
    mov [byte si+FirstObjectGraphicsFrameOffset-LevelObjectGraphicsRecords],ax ; @07C59
loc_7C5C:
    mov [si],bx ; @07C5C
loc_7C5E:
    add di,byte +0x8 ; @07C5E
    add si,byte +0x1c ; @07C61
    loop loc_7C15 ; @07C64
ObjectAnimationReturn:
    ret ; @07C66
times -(($-$$) != 0x7c67) db 0 ; module end assertion
