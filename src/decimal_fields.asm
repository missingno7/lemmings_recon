; Maintained image span 04B5C..04BE6; physical order and UNKNOWN bytes preserved.
times -(($-$$) != 0x4b5c) db 0 ; module start assertion
; Percent field: space at liveSI+3 before actual decimal CALL/RET, then percent at
; returnedSI and forward INC. Changed child return stops before the store.
WritePercentageByteField:
    mov byte [si+0x3],0x20 ; @04B5C
    call WriteDecimalByteField ; @04B60
PercentageAfterDecimal:
    mov byte [si],0x25 ; @04B63
    inc si ; @04B66
    ret ; @04B67
; CONTRACT: AL byte -> left-aligned digits with trailing spaces at live DS:SI.
; Three initial space writes precede conversion. AH is discarded; BH is retained.
; BL counts prefix digits, SI advances past units by explicit INC even with DF.
; Every write observes current defined FLAGS; final INC SI retains ADD AL carry.
; RET fetches the actual post-write SS word. See docs/entity-actions.md.
WriteDecimalByteField:
    mov byte [si],0x20 ; @04B68
    mov byte [si+0x1],0x20 ; @04B6B
    mov byte [si+0x2],0x20 ; @04B6F
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04B73
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @04B75
loc_4B77:
    inc ah ; @04B77
    sub al,0x64 ; @04B79
    jnc loc_4B77 ; @04B7B
    add al,0x64 ; @04B7D
    dec ah ; @04B7F
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04B81
    jnz loc_4B89 ; @04B83
    mov ah,0x20 ; @04B85
    jmp short loc_4B91 ; @04B87
loc_4B89:
    add ah,0x30 ; @04B89
    inc bl ; @04B8C
    mov [si],ah ; @04B8E
    inc si ; @04B90
loc_4B91:
    mov byte [si],0x20 ; @04B91
    mov byte [si+0x1],0x20 ; @04B94
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04B98
loc_4B9A:
    inc ah ; @04B9A
    sub al,0xa ; @04B9C
    jnc loc_4B9A ; @04B9E
    add al,0xa ; @04BA0
    dec ah ; @04BA2
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04BA4
    jnz loc_4BB0 ; @04BA6
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @04BA8
    jnz loc_4BB0 ; @04BAA
    mov ah,0x20 ; @04BAC
    jmp short loc_4BB8 ; @04BAE
loc_4BB0:
    add ah,0x30 ; @04BB0
    inc bl ; @04BB3
    mov [si],ah ; @04BB5
    inc si ; @04BB7
loc_4BB8:
    add al,0x30 ; @04BB8
    mov [si],al ; @04BBA
    inc si ; @04BBC
DecimalFieldReturn:
    ret ; @04BBD
; CONTRACT: clear BL and join4B91, filling two spaces. No hundreds reduction:
; AL>=100 can emit a nondecimal tens character (255 -> I5). Shared RET4BBD.
WriteDecimalBytePair:
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @04BBE
    jmp short loc_4B91 ; @04BC0
; CONTRACT: AL unsigned byte ->three ASCII digits atDS:SI; incoming AH discarded.
; AX returns tens ASCII inAH, units ASCII inAL; SI advances2 with16-bit wrap.
; Writes are live and increment forwards even withDF set. Other registers/segments
; are unchanged; final ADD AL,30 defines arithmetic flags, preserves control flags.
; Native C and active-return alias checks: tests/decimal_digits_c.py.
; Optional bus exposes each digit store after its actual ADD flags;
; all256 values and wrapped/DF stores rechecked in tests/level_start.py.
; Separate original-only contract check: tests/decimal_digits.py; docs/decimal-digits.md.
WriteDecimalByteDigits:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04BC2
loc_4BC4:
    inc ah ; @04BC4
    sub al,0x64 ; @04BC6
    jnc loc_4BC4 ; @04BC8
    add al,0x64 ; @04BCA
    add ah,0x2f ; @04BCC
    mov [si],ah ; @04BCF
    inc si ; @04BD1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04BD2
loc_4BD4:
    inc ah ; @04BD4
    sub al,0xa ; @04BD6
    jnc loc_4BD4 ; @04BD8
    add al,0xa ; @04BDA
    add ah,0x2f ; @04BDC
    mov [si],ah ; @04BDF
    inc si ; @04BE1
    add al,0x30 ; @04BE2
    mov [si],al ; @04BE4
    ret ; @04BE6
times -(($-$$) != 0x4be7) db 0 ; module end assertion
