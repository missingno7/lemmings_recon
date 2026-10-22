; Maintained suffix after view_visibility.asm; physical order unchanged.
times -(($-$$) != 0x414f) db 0 ; module start assertion
loc_414F:
ScrollViewLeft:
    mov ax,[0x0] ; @0414F
    cmp ax,0x10 ; @04152
    jng loc_4179 ; @04155
    sub ax,0x8 ; @04157
    test word [InputButtonsWord-GameDataImage],0x2 ; @0415A
    jz loc_416A ; @04160
    cmp ax,0x10 ; @04162
    jng loc_4179 ; @04165
    sub ax,0x8 ; @04167
loc_416A:
ScrollViewLeftStore:
    mov [0x0],ax ; @0416A
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @0416D
    shr dx,1 ; @0416F
    shr dx,1 ; @04171
    shr dx,1 ; @04173
    mov [0x2],dx ; @04175
loc_4179:
ScrollViewLeftRebuild:
    jmp short RebuildViewVisibilityMap ; @04179
; CONTRACT: live DS:SI NUL scan, no40-character bound; DF and AH wrap remain.
; Actual AX/SI saves and glyph CALL/RET carry returned DS/ES/flags into next scan.
; S8 STORAGE: reader3B23 starts at DS2083; stored40 characters end
;20AA and NUL20AB, inclusive extent2083..20AB. This is separate from4D4D's
; CR/header grammar.2095..97 count writes come from368A->4B68 and3AB7;
;209C..9E percent bytes from3ABD/3AFB..3B1E (non100 leaves209C unchanged).
; Selection3CEE clears2083..208D,3DF3 formats208B..208D and3E58 copies
; seven bytes from a selected status label into2083..2089, all explicitly
; forward even with DF1. Proven fixed7-byte rows start48BF,48C6,48D4,48DB,
;48E2,48E9,48F0,48F7,48FE,490C, without NUL/CR. Candidate rows48CD and
;4905 have no established selector here and remain unclassified.
;20A7 minutes is set36E2;03E7 reset writes20A9/AA at040E/0413; frame
;021F..0246 updates ASCII countdown with borrow, result4707/470A observes it.
; Startup clear ends2011 so stored status/text initialize this separate lifetime;
;4551 excludes them and GROUND's1000 request can cross them. No copied state.
; Keyboard tables201F..202E and202E..2080 share202E=4C: IRQ175A..1766 reads
;16 bindings (first match, FF disabled); character4D1A scans83 state bytes and
; XLAT4D4B reads index0..52. Raw scan0 therefore translates to4C, not1B.
; Both tables are outside startup clear; no ordinary table-writing instruction
; is identified. Longer GROUND reads and live segment/string/stack/provider
; aliases still defeat an unconditional immutability or writer-closure claim.
DrawStatusText:
    lodsb ; @0417B
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0417C
    jz loc_418B ; @0417E
    push ax ; @04180
    push si ; @04181
    call DrawStatusGlyph ; @04182
StatusTextAfterGlyph:
    pop si ; @04185
    pop ax ; @04186
    inc ah ; @04187
    jmp short DrawStatusText ; @04189
loc_418B:
StatusTextReturn:
    ret ; @0418B
times -(($-$$) != 0x418c) db 0 ; module end assertion
