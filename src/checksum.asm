; Maintained image span 08343..083BE; reconstruction module, not a historical linker claim.
; Startup integrity sample: 10 bytes beginning inside the CALL operand at188E.
; AH and DS survive; AL returns XOR, BX=1899, CX=0. Metadata is reset.
InitializeCodeChecksum:
    push ds ; @08343
    push cs ; @08344
    pop ds ; @08345
    mov bx,0x188f ; @08346
    mov cx,0xa ; @08349
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0834C
    mov [cs:0x83b9],al ; @0834E
    mov [cs:0x83ba],al ; @08352
    mov [cs:0x83bb],bx ; @08356
loc_835B:
    xor al,[cs:bx] ; @0835B
    inc bx ; @0835E
    loop loc_835B ; @0835F
    pop ds ; @08361
    ret ; @08362
; Incremental checksum candidate; static reachability is unresolved.
; Phase wraps every256 calls. Cursor stops on equality only, not >=83B7.
; Cursor is not stored on the early-limit path; preserve that stale value.
AdvanceCodeChecksum:
    push ds ; @08363
    push cs ; @08364
    pop ds ; @08365
    inc byte [cs:0x83b9] ; @08366
    mov al,[cs:0x83b9] ; @0836B
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0836F
    jnz loc_8385 ; @08371
    lea bx,[0x0] ; @08373
    mov [cs:0x83bb],bx ; @08377
    xchg [cs:0x83ba],al ; @0837C
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @08381
    jmp short loc_83A7 ; @08383
loc_8385:
    mov cx,0x800 ; @08385
    mov bx,[cs:0x83bb] ; @08388
    mov al,[cs:0x83ba] ; @0838D
loc_8391:
    cmp bx,0x83b7 ; @08391
    jz loc_83A9 ; @08395
    xor al,[bx] ; @08397
    inc bx ; @08399
    loop loc_8391 ; @0839A
    mov [cs:0x83ba],al ; @0839C
    mov [cs:0x83bb],bx ; @083A0
    mov ah,0xff ; @083A5
loc_83A7:
    pop ds ; @083A7
    ret ; @083A8
loc_83A9:
    mov [cs:0x83ba],al ; @083A9
    mov al,0xff ; @083AD
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @083AF
    mov [cs:0x83b9],al ; @083B1
    jmp short loc_83A7 ; @083B5
ChecksumLimit:
; UNKNOWN: unresolved bytes
    db 0x90 ; @083B7
; DATA: static_data
    db 0x00 ; @083B8
ChecksumPhase:
; DATA: static_data
    db 0x00 ; @083B9
ChecksumAccumulator:
; DATA: static_data
    db 0x00 ; @083BA
ChecksumCursor:
; DATA: static_data
    db 0x00,0x00,0x00,0x00 ; @083BB
