; Maintained port-201 module4334..43CD; physical order and UNKNOWN bytes retained.
; DS:0051 is live after every IN. CALL frames may overwrite this mask.
; Only DL==FF skips measurement; high wrapper moves SI/DI only after actual RET.
; Pulse emits incoming AL. Loop is unbounded until whole masked BP is zero;
; counters wrap16 and CX/DI finish with signed SAR. CLI/STI and flags stay exact.
; See docs/port-io.md. No interpretation of UNKNOWN4395/4398 is added.
;
; S18 ALTERNATE-HARDWARE INVENTORY / scoped readiness CONDITIONAL:
; 4A01 input menu key2 ->4A4E ->CALL43CE. Choice polls keyboard latch and
; port201; latch77 returnsCL2 without IN/CLI/STI. Otherwise active-low upper
; buttons30 chooseCL0, upperC0 alone choosesCL1, neither loops indefinitely.
; CL2 ->4AB5 publishes keyboard mode2. CL0 ->4A68 installs4334, CL1 ->4A80
; installs4359; both publish25A6=1 BEFORE measuring/storing25A2/25A4.
; The first calibration call inheritsDL (not forced non-FF); ifFF, measurement
; is skipped and old BX/CX can become the baselines. Calibration is not atomic.
; 4A9F accepts ASCII1..4 into scale2005. Later mode1 polling418C/42A1 reads
; live25A0 then CALL42A5; DLFF is the IRQ/menu buttons-only domain. DL!=FF
; measures axes, subtracts live baselines, applies signed deadband[-8,+8]
; and SARs: X shifts6/5/3/2, Y5/4/2/1 for scales1/2/3/4. Other scale bytes
; take the scale1 chain. Adds wrap16 BEFORE signed bounds0008..0148/0008..00C8.
; Low wrapper counts axes0/1,high wrapper2/3;button pairs are original4/5
; and6/7 inverted. Both finishIF1, do not save the incoming BP, and leave
; DF/segments untouched. Measure uses incomingAL forOUT201, not a constant.
; Mouse menu key1 ->4ABD mode0 (prompt only if1F73!=FF); key3 or choice77
; ->mode2. Neither restores25A0/baselines. Mouse reset failure or/n also
; selects mode2 at0F64. Mode other than0/1 uses keyboard acceleration.
; Known callback set4252/4334/4359 is conditional on slot/DS/stack ownership;
; see42A1 for long GROUND, record, string, provider and SS-alias writers.
; No joystick-present test, timeout or neutral substitute exists here. Timed
; analog discharge and IRQ interleavings remain platform obligations. Native
; unbound-port/target stops and the host's unbound joystick omit this behavior;
; existing port_io/input_poll/keyboard_input evidence is only its stated domain.
times -(($-$$) != 0x4334) db 0
; T3 caller refinement supersedes the earlier unrestricted-DL warning ONLY for the
; natural4A58->43CE->4A5B path: CL0/1 imply DX0201, so4A70/4A88 cannot inherit DLFF there
; with intact returns. Measurement receives AL01 from MOV AL,1 after the callback literal.
; Raw direct callback/calibration entries keep arbitrary DL, including FF. Wrappers still STI
; unconditionally and retain unbounded/wrapped timing; no hardware equivalence is supplied.
PollPort201ButtonsLow:
; CALLBACK PRODUCER:4A68 stores4334 before4A6D publishes mode1;4A70 calibrates
; through this same entry. DS must still name the game frame at each access.
; This wrapper writes only0051 and0014 directly, not25A0. Its CALL/IRQ stack
; writes and external port effects still require physical non-alias ownership.
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
;4A80 stores4359 before4A85 publishes mode1;4A88 calibrates this entry.
; No callback-slot restoration occurs here or on changing input mode later.
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
; BP is an axis-loop scratch word, finishing zero on normal termination;
; this child does NOT preserve an incoming callback BP. Callers needing BP
; must save it on owned SS storage. DS/ES/SS and DF are not assigned here.
    cli ; @04386
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04387
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @04389
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0438B
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0438D
    mov dx,0x201 ; @0438F
Port201PulseOut4392:
    out dx,al ; @04392
    jmp short loc_4396 ; @04393
; S14 U061: [04395,04396) stored bytes remain UNKNOWN.
; Neighbours: P 04393 jmp 0x4396; N 04396 jmp 0x4399.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @04395
loc_4396:
    jmp short loc_4399 ; @04396
; S14 U062: [04398,04399) stored bytes remain UNKNOWN.
; Neighbours: P 04396 jmp 0x4399; N 04399 in al, dx.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
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
