; Maintained762A..780C count and glyph leaves;5 UNKNOWN bytes remain unresolved.
times -(($-$$) != 0x762a) db 0 ; module start assertion
; CONTRACT count: initial AL owns destination, actual saved AX owns AH count.
; Repeated subtraction preserves unnormalized quotients up to25; source halves
; are10h*quotient and8+10h*remainder. Zero blanks without source reads.
; CONTRACT glyph: initial AH owns position, actual popped AL owns signed dispatch.
; Glyph passes use map masks0F/02/08 with live1FEC DS and sequential source reads.
; Space blanks16 rows without latch/source reads; invalid selectors preserve IF.
; Both retain live SS saves/mirrors/RET, DF strings and literal +2B row adjustment.
; S8 SELECTOR CONTRACT: glyph accepts only20,25,3A,30..39,41..5A by signed
; byte comparisons;80..FF fail the first signed lower bound. Space clears;
; percent selects source00A0, colon02B0, digits00D0+30h*n, capitals02E0+30h*n
; within live1FEC bank. Each drawn glyph consumes three consecutive16-byte
; source passes only with DF0; incoming DF1 walks backward instead. Unknown
; character/control bytes from status text are skipped after VGA setup; they
; do not terminate DrawStatusText (only its LODSB NUL does). Status count's
; unnormalized quotient permits glyph-index25 for byte255, not just0..9.
DrawStatusCount:
    push ds ; @0762A
    push ax ; @0762B
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0762C
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0762E
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07630
    add di,0x212c ; @07632
    add di,[DrawingOrigin-GameDataImage] ; @07636
    add di,byte +0x2 ; @0763A
    mov dx,0xa000 ; @0763D
    mov es,dx ; @07640
    mov dx,0x3c4 ; @07642
    mov ax,0xf02 ; @07645
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @07648
    out dx,ax ; @0764C
    mov dx,0x3ce ; @0764D
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @07650
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @07652
    out dx,ax ; @07656
    mov ax,0xc01 ; @07657
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @0765A
    out dx,ax ; @0765E
    mov ax,0x5 ; @0765F
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @07662
    out dx,ax ; @07666
    mov ax,0x3 ; @07667
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @0766A
    out dx,ax ; @0766E
    mov ax,0xf08 ; @0766F
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07672
    out dx,ax ; @07676
    pop ax ; @07677
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @07678
    jz loc_76DB ; @0767A
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0767C
loc_767E:
    inc al ; @0767E
    sub ah,0xa ; @07680
    jnc loc_767E ; @07683
    dec al ; @07685
    add ah,0xa ; @07687
    push ax ; @0768A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0768B
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0768D
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0768F
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07691
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @07693
    add ax,0x0 ; @07695
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @07698
    mov ds,[StatusGlyphBufferSegment-GameDataImage] ; @0769A
    push di ; @0769E
    mov cx,0x8 ; @0769F
loc_76A2:
    cli ; @076A2
    mov al,[es:di] ; @076A3
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @076A6
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @076A7
    sti ; @076A8
    add di,byte +0x2b ; @076A9
    loop loc_76A2 ; @076AC
    pop di ; @076AE
    inc di ; @076AF
    pop ax ; @076B0
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @076B1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @076B3
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076B5
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076B7
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076B9
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @076BB
    add ax,0x8 ; @076BD
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @076C0
    mov ax,0xf008 ; @076C2
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @076C5
    out dx,ax ; @076C9
    mov cx,0x8 ; @076CA
loc_76CD:
    cli ; @076CD
    mov al,[es:di] ; @076CE
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @076D1
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @076D2
    sti ; @076D3
    add di,byte +0x2b ; @076D4
    loop loc_76CD ; @076D7
    pop ds ; @076D9
StatusCountReturn:
    ret ; @076DA
loc_76DB:
    push di ; @076DB
    mov al,0xff ; @076DC
    mov cx,0x8 ; @076DE
loc_76E1:
    cli ; @076E1
    mov ah,[es:di] ; @076E2
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @076E5
    sti ; @076E6
    add di,byte +0x2b ; @076E7
    loop loc_76E1 ; @076EA
    pop di ; @076EC
    inc di ; @076ED
    mov ax,0xf008 ; @076EE
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @076F1
    out dx,ax ; @076F5
    mov al,0xff ; @076F6
    mov cx,0x8 ; @076F8
loc_76FB:
    cli ; @076FB
    mov ah,[es:di] ; @076FC
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @076FF
    sti ; @07700
    add di,byte +0x2b ; @07701
    loop loc_76FB ; @07704
    pop ds ; @07706
StatusCountBlankReturn:
    ret ; @07707
DrawStatusGlyph:
    push ds ; @07708
    push ax ; @07709
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0770A
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0770C
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @0770E
    add di,0x1e40 ; @07710
    add di,[DrawingOrigin-GameDataImage] ; @07714
    add di,byte +0x2 ; @07718
    mov dx,0xa000 ; @0771B
    mov es,dx ; @0771E
    mov dx,0x3c4 ; @07720
    mov ax,0xf02 ; @07723
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @07726
    out dx,ax ; @0772A
    mov dx,0x3ce ; @0772B
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0772E
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @07730
    out dx,ax ; @07734
    mov ax,0xe01 ; @07735
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @07738
    out dx,ax ; @0773C
    mov ax,0x5 ; @0773D
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @07740
    out dx,ax ; @07744
    mov ax,0x3 ; @07745
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @07748
    out dx,ax ; @0774C
    mov ax,0xff08 ; @0774D
    mov [ss:VgaBitMaskMirror-RuntimeStackFrame],ax ; @07750
    out dx,ax ; @07754
    pop ax ; @07755
    cmp al,0x20 ; @07756
    jnz loc_775D ; @07758
    jmp loc_77FE ; @0775A
loc_775D:
    cmp al,0x25 ; @0775D
    jnz loc_7766 ; @0775F
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @07761
    jmp short loc_77A8 ; @07763
; S14 U087: [07765,07766) stored bytes remain UNKNOWN.
; Neighbours: P 07763 jmp 0x77a8; N 07766 cmp al, 0x3a.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @07765
loc_7766:
    cmp al,0x3a ; @07766
    jnz loc_7770 ; @07768
    mov si,0x210 ; @0776A
    jmp short loc_77A8 ; @0776D
; S14 U088: [0776F,07770) stored bytes remain UNKNOWN.
; Neighbours: P 0776D jmp 0x77a8; N 07770 cmp al, 0x30.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @0776F
loc_7770:
    cmp al,0x30 ; @07770
    jnl loc_7777 ; @07772
    jmp loc_77FC ; @07774
loc_7777:
    cmp al,0x39 ; @07777
    jg loc_7793 ; @07779
    sub al,0x30 ; @0777B
    mov si,0x30 ; @0777D
loc_7780:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @07780
    shl ax,1 ; @07782
    shl ax,1 ; @07784
    shl ax,1 ; @07786
    shl ax,1 ; @07788
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0778A
    shl ax,1 ; @0778C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0778E
    jmp short loc_77A8 ; @07790
; S14 U089: [07792,07793) stored bytes remain UNKNOWN.
; Neighbours: P 07790 jmp 0x77a8; N 07793 cmp al, 0x41.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @07792
loc_7793:
    cmp al,0x41 ; @07793
    jnl loc_779A ; @07795
    jmp short loc_77FC ; @07797
; S14 U090: [07799,0779A) stored bytes remain UNKNOWN.
; Neighbours: P 07797 jmp 0x77fc; N 0779A cmp al, 0x5a.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @07799
loc_779A:
    cmp al,0x5a ; @0779A
    jng loc_77A1 ; @0779C
    jmp short loc_77FC ; @0779E
; S14 U091: [077A0,077A1) stored bytes remain UNKNOWN.
; Neighbours: P 0779E jmp 0x77fc; N 077A1 sub al, 0x41.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @077A0
loc_77A1:
    sub al,0x41 ; @077A1
    mov si,0x240 ; @077A3
    jmp short loc_7780 ; @077A6
loc_77A8:
    add si,0xa0 ; @077A8
    mov ds,[StatusGlyphBufferSegment-GameDataImage] ; @077AC
    push di ; @077B0
    mov cx,0x10 ; @077B1
loc_77B4:
    cli ; @077B4
    mov al,[es:di] ; @077B5
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @077B8
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @077B9
    sti ; @077BA
    add di,byte +0x2b ; @077BB
    loop loc_77B4 ; @077BE
    pop di ; @077C0
    mov ax,0x1 ; @077C1
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @077C4
    out dx,ax ; @077C8
    mov dx,0x3c4 ; @077C9
    mov ax,0x202 ; @077CC
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @077CF
    out dx,ax ; @077D3
    push di ; @077D4
    mov cx,0x10 ; @077D5
loc_77D8:
    cli ; @077D8
    mov al,[es:di] ; @077D9
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @077DC
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @077DD
    sti ; @077DE
    add di,byte +0x2b ; @077DF
    loop loc_77D8 ; @077E2
    pop di ; @077E4
    mov ax,0x802 ; @077E5
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @077E8
    out dx,ax ; @077EC
    mov cx,0x10 ; @077ED
loc_77F0:
    cli ; @077F0
    mov al,[es:di] ; @077F1
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @077F4
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @077F5
    sti ; @077F6
    add di,byte +0x2b ; @077F7
    loop loc_77F0 ; @077FA
loc_77FC:
    pop ds ; @077FC
StatusGlyphReturn:
    ret ; @077FD
loc_77FE:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @077FE
    mov cx,0x10 ; @07800
loc_7803:
    cli ; @07803
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @07804
    sti ; @07805
    add di,byte +0x2b ; @07806
    loop loc_7803 ; @07809
    pop ds ; @0780B
StatusGlyphSpaceReturn:
    ret ; @0780C
times -(($-$$) != 0x780d) db 0 ; module end assertion
