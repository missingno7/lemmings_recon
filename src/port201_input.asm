; Maintained port-201 module4334..43CD; physical order and UNKNOWN bytes retained.
; DS:0051 is live after every IN. CALL frames may overwrite this mask.
; Only DL==FF skips measurement; high wrapper moves SI/DI only after actual RET.
; Pulse emits incoming AL. Loop is unbounded until whole masked BP is zero;
; counters wrap16 and CX/DI finish with signed SAR. CLI/STI and flags stay exact.
; See docs/port-io.md. No interpretation of UNKNOWN4395/4398 is added.
times -(($-$$) != 0x4334) db 0
PollPort201ButtonsLow:
    mov byte [Port201MaskByte0051-GameDataImage],0x3 ; @04334
    cmp dl,0xff ; @04339
    jz loc_4341 ; @0433C
    call MeasurePort201Axes ; @0433E
loc_4341:
Port201LowAfterAxes:
    cli ; @04341
    mov dx,0x201 ; @04342
Port201LowInput4345:
    in al,dx ; @04345
    sti ; @04346
    not al ; @04347
    ror al,1 ; @04349
    ror al,1 ; @0434B
    ror al,1 ; @0434D
    ror al,1 ; @0434F
    and al,0x3 ; @04351
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04353
    mov [InputButtonsWord-GameDataImage],ax ; @04355
Port201LowReturn4358:
    ret ; @04358
PollPort201ButtonsHigh:
    mov byte [Port201MaskByte0051-GameDataImage],0xc ; @04359
    cmp dl,0xff ; @0435E
    jz loc_436A ; @04361
    call MeasurePort201Axes ; @04363
Port201HighAfterAxes:
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @04366
    db 0x8b,0xcf ; ENCODED: mov cx,di (NASM chooses a different encoding) ; @04368
loc_436A:
    cli ; @0436A
    mov dx,0x201 ; @0436B
Port201HighInput436E:
    in al,dx ; @0436E
    sti ; @0436F
    not al ; @04370
    ror al,1 ; @04372
    ror al,1 ; @04374
    ror al,1 ; @04376
    ror al,1 ; @04378
    ror al,1 ; @0437A
    ror al,1 ; @0437C
    and al,0x3 ; @0437E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04380
    mov [InputButtonsWord-GameDataImage],ax ; @04382
Port201HighReturn4385:
    ret ; @04385
MeasurePort201Axes:
    cli ; @04386
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04387
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @04389
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0438B
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0438D
    mov dx,0x201 ; @0438F
Port201PulseOut4392:
    out dx,al ; @04392
    jmp short loc_4396 ; @04393
; UNKNOWN: unresolved bytes
    db 0x90 ; @04395
loc_4396:
    jmp short loc_4399 ; @04396
; UNKNOWN: unresolved bytes
    db 0x90 ; @04398
loc_4399:
Port201SampleIn4399:
    in al,dx ; @04399
    and al,[Port201MaskByte0051-GameDataImage] ; @0439A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0439E
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @043A0
    and ax,0x1 ; @043A2
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @043A5
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043A7
    and ax,0x2 ; @043A9
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @043AC
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043AE
    and ax,0x4 ; @043B0
    shr ax,1 ; @043B3
    shr ax,1 ; @043B5
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @043B7
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @043B9
    and ax,0x8 ; @043BB
    shr ax,1 ; @043BE
    shr ax,1 ; @043C0
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @043C2
    db 0x0b,0xed ; ENCODED: or bp,bp (NASM chooses a different encoding) ; @043C4
    jnz loc_4399 ; @043C6
    sti ; @043C8
    sar cx,1 ; @043C9
    sar di,1 ; @043CB
Port201MeasureReturn43CD:
    ret ; @043CD
times -(($-$$) != 0x43ce) db 0
