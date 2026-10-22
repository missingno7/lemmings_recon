; Maintained image span 08343..083BE; reconstruction module, not a historical linker claim.
; Startup integrity sample: 10 bytes beginning inside the CALL operand at188E.
; Physical overlap with minimap797B: DF=1,ES=CS clears83AF..83C2, including
; the83AF MOV AH,AL,83B1 phase store and83B5 JMP (83AF..83B6), boundary83B7,
; and all83B8..83BE state. DF=0 clears only minimap83C1..83D4. There is no
; proven caller-wide DF-clear invariant; altered checksum instructions must not
; be treated as the intact8363 entry. No minimap run executes checksum here.
; 0006/000D call8343, storing AL at83B8/83BD in order; each call resets83B9,
; 83BA then word83BB to188F. 83BE is separate mouse-IRQ mirror gate: writers
; 00B4/4BE7 setFF,00FE sets00;0F89 reads it. None is an immutable constant.
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
; S17 flow-state: The796F local flow-state contract inherits DF at797B; no global DF0
; exclusion was established. DF1 clear83AF..83C2 intersects this instruction stream.
; Treat any later execution as a modified view requiring its own provenance. No static
; caller/reachability of8363 is supplied by this overlap.
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @083AF
    mov [cs:0x83b9],al ; @083B1
    jmp short loc_83A7 ; @083B5
; S14 U096: [083B7,083B8) stored bytes remain UNKNOWN.
; Neighbours: P 083B5 jmp 0x83a7; N 083B8 static_data.
; 8391 compares BX with83B7 and exits before8397:83B7 is excluded from the checksum read. Existing minimap797B DF1 overlay83AF..83C2 zeros this byte; DF0 writes83C1..83D4. Stored90 and bypassing JMP83B5 do not prove padding.
; No checksum read here: equality stop8391 excludes83B7.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
ChecksumLimit:
; Numeric equality stop at8391, not a byte read or executable entry. Stored90
; has no proved padding/NOP lifetime: no decoded incoming edge executes83B7,
; but minimap DF=1 writes it. Keep UNKNOWN; comparison alone cannot classify.
; 8363 reads CS:[BX] after PUSH CS/POP DS; BX==83B7 exits before XOR, including
; on wrap. Incoming cursor>83B7 can scan U097/U098 as data in0800-byte chunks;
; normal8343 initialization starts188F. No static caller of8363 is established.
; UNKNOWN: unresolved bytes
    db 0x90 ; @083B7
; DATA: static_data
StartupCodeChecksumFirstByte:
    db 0x00 ; @083B8
ChecksumPhase:
; DATA: static_data
    db 0x00 ; @083B9
ChecksumAccumulator:
; DATA: static_data
    db 0x00 ; @083BA
ChecksumCursor:
; DATA: static_data
    db 0x00,0x00 ; @083BB
StartupCodeChecksumSecondByte:
    db 0x00,0x00 ; @083BD
