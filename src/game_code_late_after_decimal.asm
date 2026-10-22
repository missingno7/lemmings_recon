; Maintained image span 04BE7..052D3; physical order and UNKNOWN bytes preserved.
times -(($-$$) != 0x4be7) db 0 ; module start assertion
; CONTRACT: CS83BE store precedes CLI/BIOSAX0090; all12returnedCPUfields staylive.
; STI is unconditional. Shared4BF5/4C07 entries skip earlier instructions.
; FarCALL8808 hasrelocation4C14; actualSSfarframe andouterRET remainlive.
; See docs/display-setup.md; no startup/BIOS/timing ownership is inferred.
SetupDisplayModeAndLayout:
    mov byte [cs:MouseIrqMirrorGate83BE],0xff ; @04BE7
    nop ; @04BED
    cli ; @04BEE
    mov ax,0x90 ; @04BEF
DisplaySetupModeInterrupt:
    int 0x10 ; @04BF2
    sti ; @04BF4
InitializeDisplayOrigins:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04BF5
    mov word [AlternateDrawingOrigin-GameDataImage],0x6d60 ; @04BFB
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @04C01
SetupDisplayLayout:
    mov ax,0x280 ; @04C07
    mov bx,0x15e ; @04C0A
    mov dx,[DrawingOrigin-GameDataImage] ; @04C0D
    call 0x0:SetDrawingLayout ; @04C11
DisplaySetupAfterLayout:
    ret ; @04C16
; Preserve the top70 ordinary screen rows; DF remains live in the shared clear.
; No added CALL frame: inherits caller RET4E36. docs/level-briefing.md.
ClearBelowLevelPreview:
    mov di,0x15e0 ; @04C17
    mov cx,0x5780 ; @04C1A
    jmp ClearVgaBytes ; @04C1D
; CONTRACT: Program liveDrawingOrigin via realCALL4C36, consumeactualchildRET,
; then reread/swap liveorigins. Providers canoverwrite saved/returnwords.
; SharedCLI/output/index0C,index0D/unconditionalSTI contract: docs/display-start.md.
SwapDrawingOriginsAndDisplay:
    mov bx,[DrawingOrigin-GameDataImage] ; @04C20
    call ProgramDisplayStartFromValue ; @04C24
DisplaySwapAfterProgram:
    mov ax,[DrawingOrigin-GameDataImage] ; @04C27
    xchg [AlternateDrawingOrigin-GameDataImage],ax ; @04C2A
    mov [DrawingOrigin-GameDataImage],ax ; @04C2E
DisplaySwapReturn:
    ret ; @04C31
ProgramAlternateDisplayStart:
    mov bx,[AlternateDrawingOrigin-GameDataImage] ; @04C32
ProgramDisplayStartFromValue:
    cli ; @04C36
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @04C37
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @04C3B
    mov al,0xc ; @04C3D
DisplayStartFirstOutput:
    out dx,ax ; @04C3F
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @04C40
    inc al ; @04C42
    out dx,ax ; @04C44
    sti ; @04C45
DisplayStartReturn:
    ret ; @04C46
MenuTimerIrqHandler:
; CONTRACT: eight saves AX/BX/CX/DX/SI/DI/BP/DS, then relocated4C50 loadsDS.
; No ES or entryFLAGS save. Shared1FE3 increments modulo4; zero sendsEOI,
; other phases chain through actualFLAGS/CS/4C70 and returnedSS:SP/DS/ES.
; DL alone becomesFF before418C; actual eight pops then hardwareIRET.
; UNKNOWN4C65 remains unresolved. docs/menu-timer.md.
    push ax ; @04C47
    push bx ; @04C48
    push cx ; @04C49
    push dx ; @04C4A
    push si ; @04C4B
    push di ; @04C4C
    push bp ; @04C4D
    push ds ; @04C4E
MenuTimerDataSegmentOperand4C50 equ $+1
    mov ax,0x9a9 ; @04C4F
    mov ds,ax ; @04C52
    mov al,[TimerChainPhase1FE3-GameDataImage] ; @04C54
    inc al ; @04C57
    and al,0x3 ; @04C59
    mov [TimerChainPhase1FE3-GameDataImage],al ; @04C5B
    jnz loc_4C66 ; @04C5E
    call SendMasterPicEoi ; @04C60
MenuTimerAfterEoi4C63:
    jmp short MenuTimerChainReturn4C70 ; @04C63
; S14 U071: [04C65,04C66) stored bytes remain UNKNOWN.
; Neighbours: P 04C63 jmp 0x4c70; N 04C66 mov ax, 0x4c70.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @04C65
loc_4C66:
    mov ax,0x4c70 ; @04C66
    pushf ; @04C69
    push cs ; @04C6A
    push ax ; @04C6B
MenuTimerFarChain4C6C:
    jmp far [SavedTimerVector-GameDataImage] ; @04C6C
MenuTimerChainReturn4C70:
    mov dl,0xff ; @04C70
    call PollInputState418C ; @04C72
MenuTimerAfterInput4C75:
    pop ds ; @04C75
    pop bp ; @04C76
    pop di ; @04C77
    pop si ; @04C78
    pop dx ; @04C79
    pop cx ; @04C7A
    pop bx ; @04C7B
    pop ax ; @04C7C
MenuTimerOuterIret4C7D:
    iret ; @04C7D
; Typed input keeps live outer/inner saves,20-cycle cursor blink and signed A..Z.
; Backspace moves without immediately erasing prior byte; full input replaces
; last slot. Final submit clears1FC7 and tail-JMPs through savedBP.
; READINESS CONDITIONAL:503B is the sole target under4C7E entry, intact code,
; game DS/DF=0, owned saves/return words and the child write contracts below.
; The only decoded external entry is CALL4996; internal entry can inherit any BP.
; Let P=entry SP (all offsets wrap16). Outer six-word frame has BP at P-0C,
; DX -0A,CX -08,BX -06,DI -04,SI -02. Wait/draw inner five-word frames have
; BP at P-16,DX -14,CX -12,SI -10,DI -0E. Wait CALL writes P-18; RET1550
; restores it, then4CA8 restores inner BP. Draw CALL writes4CCB at P-18;
; text RET4D77 consumes it; swap and keyboard CALLs reuse that return slot.
; DrawTextStream assigns BP=0/2 from style: it does NOT preserve callback BP.
;4CD1 rereads the saved inner BP;AL=FF repeats without popping the outer frame.
; A ready key then4CDA rereads the DISTINCT outer BP. Every cycle balances
; only if child RET/RETF words, returned SS:SP and live saves remain intact.
; CURSOR INVARIANT:SI=4DF2,DX=4DFC,DI in[4DF2,4DFB]. Blink/insertion/DEL/CR
; write only those ten bytes. Insertion reads4DFC (CR) before stepping back;
; no insertion stores there. DEL tests the lower bound before decrementing.
; Initial ten bytes must contain no CR (caller497D fills dots); accepted edits
; preserve that property. Header4DEF..4DF1=0F0908 and4DFC/4DFD=0D00 survive.
;503B then traverses one ten-glyph line with DF=0; style08 forces BP0, each
; glyph uses a balanced near frame, BP save and far8822/RETF frame. Planar
; prologue saves balance; aligned opaque rows save/pop DS and row/plane words.
; Glyph source may be arbitrary bytes: it is read, not executed or written.
; Children write DS:0F78..0FCA,491E,1FC7/1FC8,1F76..1F79,1FE4/1FE5 and
; renderer globals; VGA A000 stores, SS mirrors0000..000F and optional9A75
; dirty-map stores must not alias any live frame, text, code or those globals.
;1550 and4C36 use only registers/ports;4C20 has balanced CALL4C24;4D1A has
; no PUSH and never writes BP/segments. Port/IRQ effects remain external seams.
; Sufficient concrete local domain: canonical load1010,DS19B9,SS244E,DF0,
; P in[4940,4AF4], dirty marking off OR map0026 in{42B2,45D3}; fixed text
; header/terminators, no CR inside input, owned renderer state and no external
; frame/state writes (see the concrete renderer inputs in s4 integration report).
; Deepest glyph/dirty stack is P-3A (P-32 with dirty marking off); dirty maps
; end48F3 and cannot hit these saves. This is not a startup stack-range proof.
; Text/stack/SS-mirror aliases, altered text headers/DF or changed child stacks
; invalidate this induction; retain both original indirect frontiers outside it.
ReadCodeInput:
    lea si,[EnteredLevelCode-GameDataImage] ; @04C7E
    mov cx,0xa ; @04C82
    mov bx,0x5a41 ; @04C85
    lea bp,[0x503b] ; @04C88
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04C8C
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @04C8E
    db 0x03,0xd1 ; ENCODED: add dx,cx (NASM chooses a different encoding) ; @04C90
    mov cx,0x5f2e ; @04C92
    mov byte [CodeInputBlinkCountdown-GameDataImage],0x14 ; @04C95
loc_4C9A:
    push si ; @04C9A
    push di ; @04C9B
    push bx ; @04C9C
    push cx ; @04C9D
    push dx ; @04C9E
    push bp ; @04C9F
loc_4CA0:
    push di ; @04CA0
    push si ; @04CA1
    push cx ; @04CA2
    push dx ; @04CA3
    push bp ; @04CA4
    call WaitForDisplayStatusBit3Cycle ; @04CA5
CodeEntryAfterCall4CA5:
    pop bp ; @04CA8
    pop dx ; @04CA9
    pop cx ; @04CAA
    pop si ; @04CAB
    pop di ; @04CAC
    dec byte [CodeInputBlinkCountdown-GameDataImage] ; @04CAD
    jnz loc_4CC4 ; @04CB1
    mov byte [CodeInputBlinkCountdown-GameDataImage],0x14 ; @04CB3
    mov al,[di] ; @04CB8
    db 0x3a,0xc1 ; ENCODED: cmp al,cl (NASM chooses a different encoding) ; @04CBA
    jz loc_4CC2 ; @04CBC
    mov [di],cl ; @04CBE
    jmp short loc_4CC4 ; @04CC0
loc_4CC2:
    mov [di],ch ; @04CC2
loc_4CC4:
    push di ; @04CC4
    push si ; @04CC5
    push cx ; @04CC6
    push dx ; @04CC7
    push bp ; @04CC8
CodeInputDrawCall4CC9:
; BP came from4CA8 (wait save), or intact prior4CD1 across another wait cycle.
; PUSH BP at4CC8 cannot change the already-live register target by alias alone.
    call bp ; @04CC9
CodeEntryAfterCall4CC9:
    call SwapDrawingOriginsAndDisplay ; @04CCB
CodeEntryAfterCall4CCB:
    call ReadKeyboardCharacter ; @04CCE
CodeEntryAfterCall4CCE:
    pop bp ; @04CD1
    pop dx ; @04CD2
    pop cx ; @04CD3
    pop si ; @04CD4
    pop di ; @04CD5
    cmp al,0xff ; @04CD6
    jz loc_4CA0 ; @04CD8
    pop bp ; @04CDA
; This outer BP is now latched in a register through4D18: no later instruction
; here assigns BP. It need not equal the inner value just restored at4CD1.
    pop dx ; @04CDB
    pop cx ; @04CDC
    pop bx ; @04CDD
    pop di ; @04CDE
    pop si ; @04CDF
    cmp al,0x7f ; @04CE0
    jz loc_4D02 ; @04CE2
    cmp al,0xd ; @04CE4
    jz loc_4D10 ; @04CE6
    db 0x3a,0xc3 ; ENCODED: cmp al,bl (NASM chooses a different encoding) ; @04CE8
    jl loc_4C9A ; @04CEA
    db 0x3a,0xc7 ; ENCODED: cmp al,bh (NASM chooses a different encoding) ; @04CEC
    jg loc_4C9A ; @04CEE
    db 0x3b,0xfa ; ENCODED: cmp di,dx (NASM chooses a different encoding) ; @04CF0
    jz loc_4C9A ; @04CF2
    mov [di],al ; @04CF4
    inc di ; @04CF6
    mov cl,[di] ; @04CF7
    db 0x3b,0xfa ; ENCODED: cmp di,dx (NASM chooses a different encoding) ; @04CF9
    jnz loc_4C9A ; @04CFB
    dec di ; @04CFD
    mov cl,[di] ; @04CFE
    jmp short loc_4C9A ; @04D00
loc_4D02:
    mov byte [di],0x2e ; @04D02
    mov cl,0x2e ; @04D05
    db 0x3b,0xfe ; ENCODED: cmp di,si (NASM chooses a different encoding) ; @04D07
    jz loc_4C9A ; @04D09
    dec di ; @04D0B
    mov cl,[di] ; @04D0C
    jmp short loc_4C9A ; @04D0E
loc_4D10:
    mov word [0x1fc7],0x0 ; @04D10
    mov [di],cl ; @04D16
CodeInputDrawTail4D18:
;4D10/4D16 stores cannot change latched BP; aliases CAN change inherited RET,
; text or code. JMP supplies no new frame:503B uses original caller return at P.
    jmp bp ; @04D18
; Scan83 live state bytes. TEST then MOV reread held bytes; low7 decrement wraps.
; Decrement0 reloads86 and emits; stored93 emits; other states continue scanning.
; AH survives. EmptyALFF returns4D2D, readyXLAT uses202E and returns4D4C.
; 202E overlaps final binding201F+15. Actual RET/SS:SP and field aliases stay live.
; See docs/keyboard-input.md for IRQ-to-repeat-to-menu handoffs and limits.
ReadKeyboardCharacter:
    lea si,[KeyboardStateBytes0F78-GameDataImage] ; @04D1A
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04D1E
    mov cx,0x53 ; @04D20
loc_4D23:
    test byte [bx+si],0x80 ; @04D23
    jnz loc_4D2E ; @04D26
loc_4D28:
    inc bx ; @04D28
    loop loc_4D23 ; @04D29
    mov al,0xff ; @04D2B
KeyboardCharacterEmptyReturn4D2D:
    ret ; @04D2D
loc_4D2E:
    mov al,[bx+si] ; @04D2E
    and al,0x7f ; @04D30
    dec al ; @04D32
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D34
    jz loc_4D42 ; @04D36
    or al,0x80 ; @04D38
    mov [bx+si],al ; @04D3A
    cmp al,0x93 ; @04D3C
    jz loc_4D45 ; @04D3E
    jmp short loc_4D28 ; @04D40
loc_4D42:
    mov byte [bx+si],0x86 ; @04D42
loc_4D45:
    db 0x8a,0xc3 ; ENCODED: mov al,bl (NASM chooses a different encoding) ; @04D45
    lea bx,[KeyboardCharacterTable202E-GameDataImage] ; @04D47
    xlatb ; @04D4B
KeyboardCharacterReadyReturn4D4C:
    ret ; @04D4C
; [04D4D] Code-editor callback503B shares this RET4D77. Header style08 gives BP0; this stream intentionally clobbers BP, restored by editor inner POP4CD1 and distinct outer POP4CDA. At normal header0F0908 and ten non-CR input bytes, x=224..368,y=144,width/height16, three planes; DF0 reaches CR4DFC and terminal header4DFD. Changed header/DF/saved SI can destroy this finite traversal; do not infer callback identity from child BP preservation.
; Stream uses live DS:SI and incoming DF. Header: column(1-based), row, style.
; Header column0 terminates; style0=>BP2 elseBP0. Only CR ends each text run.
; Zero inside a run is a glyph. Save CX/BX/SI, consume actual glyph nearRET,
; then live POP SI/BX/CX and byte INC CL. Child DS/ES and frame aliases flow.
DrawTextStream:
    lodsb ; @04D4D
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D4E
    jz TextStreamReturn ; @04D50
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @04D52
    dec cl ; @04D54
    lodsb ; @04D56
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @04D57
    lodsb ; @04D59
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04D5A
    jnz loc_4D63 ; @04D5C
    mov bp,0x2 ; @04D5E
    jmp short TextStreamReadCharacter ; @04D61
loc_4D63:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @04D63
TextStreamReadCharacter:
    lodsb ; @04D65
    cmp al,0xd ; @04D66
    jz DrawTextStream ; @04D68
    push cx ; @04D6A
    push bx ; @04D6B
    push si ; @04D6C
    call DrawTextGlyph ; @04D6D
TextStreamAfterGlyph:
    pop si ; @04D70
    pop bx ; @04D71
    pop cx ; @04D72
    inc cl ; @04D73
    jmp short TextStreamReadCharacter ; @04D75
TextStreamReturn:
    ret ; @04D77
; Space preserves incoming state except CMP flags. Other AL values wrap after SUB21.
; SI=5BC0+96*index; DI=SI+40. Live DS:1FEE+1000 becomes graphics source.
; CH/CL become top/left*16, width16/height16/three planes; BP is saved on live SS.
; Far CALL uses relocated same-CS target; consume actual RETF, then live POP BP.
DrawTextGlyph:
    cmp al,0x20 ; @04D78
    jz TextGlyphReturn ; @04D7A
    sub al,0x21 ; @04D7C
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04D7E
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D80
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D82
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D84
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D86
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D88
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @04D8A
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @04D8C
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @04D8E
    add si,0x5bc0 ; @04D90
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04D94
    add di,byte +0x40 ; @04D96
    mov bx,[UiGraphicsBufferSegment-GameDataImage] ; @04D99
    add bx,0x1000 ; @04D9D
    mov [GraphicsResourceSegment-GameDataImage],bx ; @04DA1
    db 0x8a,0xdd ; ENCODED: mov bl,ch (NASM chooses a different encoding) ; @04DA5
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @04DA7
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @04DA9
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04DAB
    mov cl,0x4 ; @04DAD
    shl bx,cl ; @04DAF
    shl ax,cl ; @04DB1
    mov cl,0x10 ; @04DB3
    mov ch,0x3 ; @04DB5
    mov dx,0x10 ; @04DB7
    push bp ; @04DBA
TextGlyphBitmapCall:
    call 0x0:0x8822 ; @04DBB
TextGlyphAfterBitmap:
    pop bp ; @04DC0
TextGlyphReturn:
    ret ; @04DC1
; SS mirrors precede OUTs; mode1 copies four read latches, not the CPU byte.
; PUSH DS precedes live origin reads. REP copies6D60 bytes with incomingDF,
; wrapping SI/DI16; live POP DS and RET may read overwritten/device words.
; Flags and BX/BP are preserved; ES/AX=A000, DX=3CE,CX=0.
CopyDrawingPageToAlternate:
    mov dx,0x3c4 ; @04DC2
    mov ax,0xf02 ; @04DC5
    mov [ss:0x8],ax ; @04DC8
DisplayPageCopyMapMaskOutput:
    out dx,ax ; @04DCC
    mov dx,0x3ce ; @04DCD
    mov ax,0x105 ; @04DD0
    mov [ss:0x0],ax ; @04DD3
DisplayPageCopyModeOutput:
    out dx,ax ; @04DD7
    push ds ; @04DD8
    mov si,[DrawingOrigin-GameDataImage] ; @04DD9
    mov di,[AlternateDrawingOrigin-GameDataImage] ; @04DDD
    mov ax,0xa000 ; @04DE1
    mov ds,ax ; @04DE4
    mov es,ax ; @04DE6
    mov cx,0x6d60 ; @04DE8
    rep movsb ; @04DEB
DisplayPageCopyRestoreDataSegment:
    pop ds ; @04DED
DisplayPageCopyReturn:
    ret ; @04DEE
; Fixed DI=0,CX=6D60; tail shares ClearVgaBytes and its live outerRET.
; The UNKNOWN byte at4DF7 is skipped and remains unresolved.
ClearFullDrawingPage:
    mov di,0x0 ; @04DEF
    mov cx,0x6d60 ; @04DF2
    jmp short ClearVgaBytes ; @04DF5
; S14 U072: [04DF7,04DF8) stored bytes remain UNKNOWN.
; Neighbours: P 04DF5 jmp 0x4df8; N 04DF8 mov dx, 0x3c4.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @04DF7
; SS mirror words precede six OUTs. ES=A000, AX=A000, DX=3CE.
; REP clears incoming CX bytes from DI with incoming DF; CX=0. No CLI/STI.
; Final XOR defines CF/OF=0, PF/ZF=1,SF=0; AF undefined. RET reads live SS.
ClearVgaBytes:
    mov dx,0x3c4 ; @04DF8
    mov ax,0xf02 ; @04DFB
    mov [ss:0x8],ax ; @04DFE
    out dx,ax ; @04E02
    mov dx,0x3ce ; @04E03
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04E06
    mov [ss:0xa],ax ; @04E08
    out dx,ax ; @04E0C
    mov ax,0xf01 ; @04E0D
    mov [ss:0xc],ax ; @04E10
    out dx,ax ; @04E14
    mov ax,0x5 ; @04E15
    mov [ss:0x0],ax ; @04E18
    out dx,ax ; @04E1C
    mov ax,0x3 ; @04E1D
    mov [ss:0x2],ax ; @04E20
    out dx,ax ; @04E24
    mov ax,0xff08 ; @04E25
    mov [ss:0xe],ax ; @04E28
    out dx,ax ; @04E2C
    mov ax,0xa000 ; @04E2D
    mov es,ax ; @04E30
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04E32
    rep stosb ; @04E34
ClearVgaReturn:
    ret ; @04E36
; Live toggle/cache use marker2 for two page updates, then exact-byte equality.
; Low sound bits select B120 background or EA50/EE30 icons; gate2010 is exactFF.
; AH survives the no-draw return; actual frames/DS/ES/flags stay live.
RefreshMenuSoundGraphic:
    mov al,[MenuSoundRedrawCache-GameDataImage] ; @04E37
    cmp al,0x2 ; @04E3A
    jnz loc_4E46 ; @04E3C
    mov al,[MenuSoundRedrawToggle-GameDataImage] ; @04E3E
    mov [MenuSoundRedrawCache-GameDataImage],al ; @04E41
    jmp short loc_4E51 ; @04E44
loc_4E46:
    cmp [MenuSoundRedrawToggle-GameDataImage],al ; @04E46
    jz loc_4E83 ; @04E4A
    mov byte [MenuSoundRedrawCache-GameDataImage],0x2 ; @04E4C
loc_4E51:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04E51
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04E54
    mov si,0xee30 ; @04E57
    mov al,[0x25a7] ; @04E5A
    test al,0x3 ; @04E5D
    jz loc_4E84 ; @04E5F
    test al,0x2 ; @04E61
    jz loc_4E6F ; @04E63
    cmp byte [0x2010],0xff ; @04E65
    jnz loc_4E6F ; @04E6A
    mov si,0xea50 ; @04E6C
loc_4E6F:
    mov ax,0x15f ; @04E6F
    mov bx,0x92 ; @04E72
    mov dx,0x40 ; @04E75
    mov cx,0x41f ; @04E78
    mov bp,0x1 ; @04E7B
    call 0x0:0x8822 ; @04E7E
loc_4E83:
MenuSoundIconReturn:
    ret ; @04E83
loc_4E84:
    mov bx,0x78 ; @04E84
    mov ax,0x144 ; @04E87
    mov si,0xb120 ; @04E8A
    mov bp,0x3 ; @04E8D
    mov cx,0x43d ; @04E90
    mov dx,0x78 ; @04E93
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04E96
    add di,0xab9 ; @04E98
    call 0x0:0x8822 ; @04E9C
MenuSoundBackgroundReturn:
    ret ; @04EA1
; Marker4 handshake; reread live group index after selector publication.
; BL is zero-extended then doubled; CS source table indexing is unchecked.
; See docs/menu-cache.md for producers and two-page handoffs.
RefreshMenuLevelGroupGraphic:
    mov al,[MenuLevelGroupRedrawCache-GameDataImage] ; @04EA2
    cmp al,0x4 ; @04EA5
    jnz loc_4EB1 ; @04EA7
    mov al,[MenuLevelGroupIndex-GameDataImage] ; @04EA9
    mov [MenuLevelGroupRedrawCache-GameDataImage],al ; @04EAC
    jmp short loc_4EBC ; @04EAF
loc_4EB1:
    cmp [MenuLevelGroupIndex-GameDataImage],al ; @04EB1
    jz loc_4EE6 ; @04EB5
    mov byte [MenuLevelGroupRedrawCache-GameDataImage],0x4 ; @04EB7
loc_4EBC:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04EBC
    add ax,0x1000 ; @04EBF
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04EC2
    mov bl,[MenuLevelGroupIndex-GameDataImage] ; @04EC5
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @04EC9
    shl bx,1 ; @04ECB
    mov si,[cs:bx+MenuLevelGroupGraphicSources] ; @04ECD
    mov ax,0x1e6 ; @04ED2
    mov bx,0x91 ; @04ED5
    mov dx,0x48 ; @04ED8
    mov cx,0x41b ; @04EDB
    mov bp,0x1 ; @04EDE
    call 0x0:0x8822 ; @04EE1
loc_4EE6:
MenuLevelGroupReturn:
    ret ; @04EE6
; S8 Four little-endian CS words57F4,5428,505C,4C90;4ECD reads after zero-extension and doubling
; livegroup1F6E, UI1FEE+1000 published4EC2. Four72x27x4 plane sources of03CCh in MAIN UIbank.
; RET4EE6/code4EEF close exact8 bytes. Startupclear/4827 seed0,4502/4532 cycle nominal0..3 with
; equalityguards,473B/52A1 write selection/30. Unchecked fullbyte permits0..8 fromdecode (FF
; selection ->8) and corruptvalues through255, rawreads4EE7..50E6. No identified direct CS table
; writer. CS input bytes are process-image initialization; checksum8397 may read them as data.
; Lack of direct stores does not exclude dynamic/SS/device/IRQ/protection aliases; not a global
; writer-closure proof.
; UNKNOWN: unresolved bytes
MenuLevelGroupGraphicSources:
    db 0xf4,0x57,0x28,0x54,0x5c,0x50,0x90,0x4c ; @04EE7
; Two direct bitmap calls share the live UI selector; no parent saves.
; Actual relocated far returns and renderer DS/ES/flags feed the second call.
DrawMenuBackdropLayers:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04EEF
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04EF2
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04EF5
    mov bx,0x14 ; @04EF7
    mov bp,0xf42 ; @04EFA
    mov cl,0x5e ; @04EFD
    mov ch,0x4 ; @04EFF
    mov dx,0x278 ; @04F01
    mov si,0x2080 ; @04F04
    mov di,0x7786 ; @04F07
    call 0x0:0x8822 ; @04F0A
MenuBackdropAfterFirstBitmap:
    mov ax,0x8 ; @04F0F
    mov bx,0xa ; @04F12
    mov bp,0x2 ; @04F15
    mov cl,0x5e ; @04F18
    mov ch,0x4 ; @04F1A
    mov dx,0x278 ; @04F1C
    mov si,0x2080 ; @04F1F
    mov di,0x7786 ; @04F22
    call 0x0:0x8822 ; @04F25
MenuBackdropReturn:
    ret ; @04F2A
; First CALL draws four table entries; second two-entry row is fallthrough.
; Six CS source words remain live UNKNOWN storage. docs/menu-animation.md.
DrawMenuDecorationRows:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04F2B
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04F2E
    mov bx,0x78 ; @04F31
    mov ax,0x44 ; @04F34
    mov cx,0x4 ; @04F37
    lea di,[MenuDecorationSourceTable] ; @04F3A
    call DrawMenuDecorationRow ; @04F3E
MenuRowsAfterFirstRow:
    mov bx,0xc5 ; @04F41
    mov ax,0xc4 ; @04F44
    mov cx,0x2 ; @04F47
; Actual CX/AX/BX saves, two near wrapper calls, ADD AX,80 and LOOP.
; CX zero still enters the body; flags and overwritten saves remain observable.
DrawMenuDecorationRow:
    push cx ; @04F4A
    mov si,[cs:di] ; @04F4B
    add di,byte +0x2 ; @04F4E
    mov bp,0xf43 ; @04F51
    push ax ; @04F54
    push bx ; @04F55
    sub ax,0x8 ; @04F56
    add bx,byte +0x8 ; @04F59
    call DrawMenuDecorationBitmap ; @04F5C
MenuRowAfterFirstBitmap:
    pop bx ; @04F5F
    pop ax ; @04F60
    mov bp,0x3 ; @04F61
    call DrawMenuDecorationBitmap ; @04F64
MenuRowAfterSecondBitmap:
    pop cx ; @04F67
    add ax,0x80 ; @04F68
    loop DrawMenuDecorationRow ; @04F6B
MenuDecorationRowReturn:
    ret ; @04F6D
; Push AX/BX/BP/SI/DI; source+AB9 mask,43D/78 geometry, actual far CALL.
; POPs reread live words; CX/DX/DS/ES/flags are not restored by this wrapper.
DrawMenuDecorationBitmap:
    push ax ; @04F6E
    push bx ; @04F6F
    push bp ; @04F70
    push si ; @04F71
    push di ; @04F72
    mov cx,0x43d ; @04F73
    mov dx,0x78 ; @04F76
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04F79
    add di,0xab9 ; @04F7B
    call 0x0:0x8822 ; @04F7F
MenuDecorationAfterBitmap:
    pop di ; @04F84
    pop si ; @04F85
    pop bp ; @04F86
    pop bx ; @04F87
    pop ax ; @04F88
MenuDecorationBitmapReturn:
    ret ; @04F89
; S8 Six little-endian CS words9488,A2D4,B120,BF6C,CDB8,DC04.4F3A initializesDI;4F37 count4
; then4F47 count2 share4F4B read and4F4E DI+=2. Both bitmapwrappers restoreliveDI/SI viaSS;
; sourceUI1FEE, each color/mask pair spans0E4Ch, mask+0AB9. RET4F89/code4F96 bound12
; storedbytes; no tablewrites by these consumers. Raw4F4A CX0 enters body thenLOOP wraps toFFFF,
; arbitraryDI/savedCX/DS/SS aliases can read elsewhere; do not clamp to six. CS input bytes are
; process-image initialization; checksum8397 may read them as data. Lack of direct stores does
; not exclude dynamic/SS/device/IRQ/protection aliases; not a global writer-closure proof.
; UNKNOWN: unresolved bytes
MenuDecorationSourceTable:
    db 0x88,0x94,0xd4,0xa2,0x20,0xb1,0x6c,0xbf,0xb8,0xcd,0x04,0xdc ; @04F8A
; Ten11-byte DS4960 records: +0 live countdown,+2 reset,+4 x,+6 y,+8 source.
; Entry8000 disables; decrement toFFEF reloads +2 without drawing. Other negative
; values derive the frame by literal NEG/DEC/SHR/XCHG/SHR/ADD operations, wrapping.
; Far8822 uses actual CS/IP words; returnedDS/ES and POPSI/POPCX stay live.
; Byte+10 is untouched and its meaning remains unresolved. docs/menu-animation.md.
AdvanceMenuAnimations:
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @04F96
    add ax,0x800 ; @04F99
    mov [GraphicsResourceSegment-GameDataImage],ax ; @04F9C
    lea si,[MenuAnimationRecords-GameDataImage] ; @04F9F
    mov cx,0xa ; @04FA3
loc_4FA6:
    push cx ; @04FA6
    mov ax,[si] ; @04FA7
    cmp ax,0x8000 ; @04FA9
    jz loc_4FF1 ; @04FAC
    dec ax ; @04FAE
    mov [si],ax ; @04FAF
    cmp ax,0xffef ; @04FB1
    jnz loc_4FBD ; @04FB4
    mov ax,[si+0x2] ; @04FB6
    mov [si],ax ; @04FB9
    jmp short loc_4FF1 ; @04FBB
loc_4FBD:
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @04FBD
    jns loc_4FF1 ; @04FBF
    neg ax ; @04FC1
    dec ax ; @04FC3
    shr ax,1 ; @04FC4
    xchg al,ah ; @04FC6
    mov bp,[si+0x8] ; @04FC8
    shr ax,1 ; @04FCB
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @04FCD
    shr ax,1 ; @04FCF
    db 0x03,0xe8 ; ENCODED: add bp,ax (NASM chooses a different encoding) ; @04FD1
    mov ax,[si+0x4] ; @04FD3
    mov bx,[si+0x6] ; @04FD6
    push si ; @04FD9
    db 0x8b,0xf5 ; ENCODED: mov si,bp (NASM chooses a different encoding) ; @04FDA
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @04FDC
    add di,0x90 ; @04FDE
    mov bp,0x1 ; @04FE2
    mov cx,0x40c ; @04FE5
    mov dx,0x20 ; @04FE8
    call 0x0:0x8822 ; @04FEB
MenuAnimationAfterBitmap:
    pop si ; @04FF0
loc_4FF1:
    pop cx ; @04FF1
    add si,byte +0xb ; @04FF2
    loop loc_4FA6 ; @04FF5
MenuAnimationTickReturn:
    ret ; @04FF7
; Initialize only +0: exact +2 sentinel8000 survives, otherwise40*(index+1).
; BX advances even for disabled records; all accesses use liveDS and word order.
InitializeMenuAnimations:
    lea si,[MenuAnimationRecords-GameDataImage] ; @04FF8
    mov cx,0xa ; @04FFC
    mov bx,0x28 ; @04FFF
loc_5002:
    mov ax,[si+0x2] ; @05002
    cmp ax,0x8000 ; @05005
    jz loc_500C ; @05008
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @0500A
loc_500C:
    mov [si],ax ; @0500C
    add bx,byte +0x28 ; @0500E
    add si,byte +0xb ; @05011
    loop loc_5002 ; @05014
MenuAnimationInitializeReturn:
    ret ; @05016
; 5017 resets the row;5019 preserves incoming BX. Both share the7E76 tile loop.
; See docs/background-drawing.md for live saves and changed child returns.
DrawScreenBackground:
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @05017
DrawScreenBackgroundFromRow:
    jmp DrawScreenBackgroundTiles ; @05019
; S14 U075: [0501C,05028) stored bytes remain UNKNOWN.
; Neighbours: P 05019 jmp 0x7e76; N 05028 cli.
; Candidate501C clears AL/stores0 to DS1FCD,then CMP AL,[1FCD]/JE5021 until unequal,RET. No STI/CLI/watchdog; disabled IRQ/no producer may spin indefinitely, byte wrap may hide changes. Clears timer state, never sets004A. Entry unproved.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x32,0xc0,0xa2,0xcd,0x1f,0x3a,0x06,0xcd,0x1f,0x74,0xfa,0xc3 ; @0501C
InstallMenuTimerVector:
; CONTRACT: CLI/PUSHDS before zeroDS. WriteIVT08 IP thenCS as actualwords.
; POPDS and outerRET reread liveSS, including IVT/stack aliases; STI forcesIF.
    cli ; @05028
    push ds ; @05029
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0502A
    mov ds,ax ; @0502C
    mov word [0x20],0x4c47 ; @0502E
    mov [0x22],cs ; @05034
    pop ds ; @05038
    sti ; @05039
MenuTimerInstallReturn503A:
    ret ; @0503A
; [0503B] 4CC9 supplies return4CCB; final4D18 supplies no new word and inherits original4999 return from CALL4996. LEA SI4DEF then JMP4D4D; BP is assigned by text header and not preserved here. Sole503B target proof belongs to editor save ownership, not this bridge.
; Tail bridge sets live SI4DEF and shares text RET4D77/caller stack word.
DrawCodeInputText:
    lea si,[CodeInputText-GameDataImage] ; @0503B
    jmp DrawTextStream ; @0503F
; Live DS template/payload/completion ->10 generated bytes. ORs preserve every
; template bit; low7 rotate right8-(selection&7) times, including8. No flags or
; registers saved. Own RET51A1 consumes live SS. docs/level-code.md.
EncodeLevelCode:
    mov dl,[LevelResourceSelectionByte-GameDataImage] ; @05042
    mov dh,[LevelCodePayloadByte-GameDataImage] ; @05046
    mov cl,[StatusCompletionDisplayValue-GameDataImage] ; @0504A
    lea si,[LevelCodeTemplate-GameDataImage] ; @0504E
    lea di,[GeneratedLevelCode-GameDataImage] ; @05052
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05056
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05058
    and ax,0x101 ; @0505A
    and ch,0x1 ; @0505D
    shl al,1 ; @05060
    shl al,1 ; @05062
    shl al,1 ; @05064
    shl ah,1 ; @05066
    shl ch,1 ; @05068
    shl ch,1 ; @0506A
    or al,[si] ; @0506C
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @0506E
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05070
    mov [di],al ; @05072
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05074
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05076
    and al,0x2 ; @05078
    and ch,0x2 ; @0507A
    shl al,1 ; @0507D
    shr ch,1 ; @0507F
    or al,[si+0x1] ; @05081
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05084
    mov [di+0x1],al ; @05086
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05089
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @0508B
    and ax,0x204 ; @0508D
    and ch,0x4 ; @05090
    shr ah,1 ; @05093
    shr ch,1 ; @05095
    or al,[si+0x2] ; @05097
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @0509A
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @0509C
    mov [di+0x2],al ; @0509E
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @050A1
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050A3
    and al,0x8 ; @050A5
    and ch,0x8 ; @050A7
    shr al,1 ; @050AA
    shr al,1 ; @050AC
    shr al,1 ; @050AE
    shr ch,1 ; @050B0
    shr ch,1 ; @050B2
    or al,[si+0x3] ; @050B4
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @050B7
    mov [di+0x3],al ; @050B9
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @050BC
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050BE
    and ax,0x410 ; @050C0
    and ch,0x10 ; @050C3
    shr al,1 ; @050C6
    shr al,1 ; @050C8
    shr al,1 ; @050CA
    shr ah,1 ; @050CC
    shr ah,1 ; @050CE
    shr ch,1 ; @050D0
    or al,[si+0x4] ; @050D2
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @050D5
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @050D7
    mov [di+0x4],al ; @050D9
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @050DC
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @050DE
    and al,0x20 ; @050E0
    and ah,0x8 ; @050E2
    and ch,0x20 ; @050E5
    shr al,1 ; @050E8
    shr al,1 ; @050EA
    shr al,1 ; @050EC
    shr al,1 ; @050EE
    shr al,1 ; @050F0
    shr ah,1 ; @050F2
    shr ah,1 ; @050F4
    shr ch,1 ; @050F6
    shr ch,1 ; @050F8
    shr ch,1 ; @050FA
    or al,[si+0x5] ; @050FC
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @050FF
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05101
    mov [di+0x5],al ; @05103
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05106
    db 0x8a,0xe9 ; ENCODED: mov ch,cl (NASM chooses a different encoding) ; @05108
    and al,0xc0 ; @0510A
    and ch,0x40 ; @0510C
    shr al,1 ; @0510F
    shr al,1 ; @05111
    shr al,1 ; @05113
    shr al,1 ; @05115
    shr ch,1 ; @05117
    shr ch,1 ; @05119
    shr ch,1 ; @0511B
    shr ch,1 ; @0511D
    shr ch,1 ; @0511F
    shr ch,1 ; @05121
    or al,[si+0x6] ; @05123
    db 0x0a,0xc5 ; ENCODED: or al,ch (NASM chooses a different encoding) ; @05126
    mov [di+0x6],al ; @05128
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @0512B
    and al,0xf ; @0512D
    add al,[si+0x7] ; @0512F
    mov [di+0x7],al ; @05132
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05135
    and al,0xf0 ; @05137
    shr al,1 ; @05139
    shr al,1 ; @0513B
    shr al,1 ; @0513D
    shr al,1 ; @0513F
    add al,[si+0x8] ; @05141
    mov [di+0x8],al ; @05144
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @05147
    add al,[di] ; @05149
    add al,[di+0x1] ; @0514B
    add al,[di+0x2] ; @0514E
    add al,[di+0x3] ; @05151
    add al,[di+0x4] ; @05154
    add al,[di+0x5] ; @05157
    add al,[di+0x6] ; @0515A
    add al,[di+0x7] ; @0515D
    add al,[di+0x8] ; @05160
    and al,0xf ; @05163
    add al,[si+0x9] ; @05165
    mov [di+0x9],al ; @05168
    mov dh,0x7 ; @0516B
    db 0x22,0xd6 ; ENCODED: and dl,dh (NASM chooses a different encoding) ; @0516D
    db 0x2a,0xf2 ; ENCODED: sub dh,dl (NASM chooses a different encoding) ; @0516F
    lea si,[GeneratedLevelCode-GameDataImage+6] ; @05171
loc_5175:
    mov al,[si] ; @05175
    mov ah,[si-0x1] ; @05177
    mov [si],ah ; @0517A
    mov ah,[si-0x2] ; @0517C
    mov [si-0x1],ah ; @0517F
    mov ah,[si-0x3] ; @05182
    mov [si-0x2],ah ; @05185
    mov ah,[si-0x4] ; @05188
    mov [si-0x3],ah ; @0518B
    mov ah,[si-0x5] ; @0518E
    mov [si-0x4],ah ; @05191
    mov ah,[si-0x6] ; @05194
    mov [si-0x5],ah ; @05197
    mov [si-0x6],al ; @0519A
    dec dh ; @0519D
    jns loc_5175 ; @0519F
LevelCodeEncodeReturn:
    ret ; @051A1
; Exact BILLANDTED sets latch before checksum, even when validation fails.
; Checksum failure leaves input untouched; later duplicate-selection failure
; keeps the selection write and in-place inverse rotation. Success updates
; group=unsigned selection/30 and low4 payload, returns ZF1 via SUB AH,AH.
; Live saved SI may alias input/template; no rollback. docs/level-code.md.
DecodeLevelCode:
    lea si,[EnteredLevelCode-GameDataImage] ; @051A2
    cmp word [si],0x4942 ; @051A6
    jnz loc_51CD ; @051AA
    cmp word [si+0x2],0x4c4c ; @051AC
    jnz loc_51CD ; @051B1
    cmp word [si+0x4],0x4e41 ; @051B3
    jnz loc_51CD ; @051B8
    cmp word [si+0x6],0x5444 ; @051BA
    jnz loc_51CD ; @051BF
    cmp word [si+0x8],0x4445 ; @051C1
    jnz loc_51CD ; @051C6
    mov byte [SpecialLevelCodeLatch-GameDataImage],0xff ; @051C8
loc_51CD:
    lea di,[LevelCodeTemplate-GameDataImage] ; @051CD
    mov cx,0x9 ; @051D1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @051D4
    push si ; @051D6
loc_51D7:
    add al,[si] ; @051D7
    inc si ; @051D9
    loop loc_51D7 ; @051DA
    pop si ; @051DC
    and al,0xf ; @051DD
    mov ah,[si+0x9] ; @051DF
    db 0x2a,0xe0 ; ENCODED: sub ah,al (NASM chooses a different encoding) ; @051E2
    cmp [di+0x9],ah ; @051E4
    jz loc_51EC ; @051E7
    jmp loc_52D3 ; @051E9
loc_51EC:
    mov al,[si+0x7] ; @051EC
    sub al,[di+0x7] ; @051EF
    mov ah,[si+0x8] ; @051F2
    sub ah,[di+0x8] ; @051F5
    and ax,0xf0f ; @051F8
    shl ah,1 ; @051FB
    shl ah,1 ; @051FD
    shl ah,1 ; @051FF
    shl ah,1 ; @05201
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @05203
    mov [LevelResourceSelectionByte-GameDataImage],al ; @05205
    mov dh,0x7 ; @05208
    db 0x22,0xc6 ; ENCODED: and al,dh (NASM chooses a different encoding) ; @0520A
    db 0x2a,0xf0 ; ENCODED: sub dh,al (NASM chooses a different encoding) ; @0520C
loc_520E:
    mov al,[si] ; @0520E
    mov ah,[si+0x1] ; @05210
    mov [si],ah ; @05213
    mov ah,[si+0x2] ; @05215
    mov [si+0x1],ah ; @05218
    mov ah,[si+0x3] ; @0521B
    mov [si+0x2],ah ; @0521E
    mov ah,[si+0x4] ; @05221
    mov [si+0x3],ah ; @05224
    mov ah,[si+0x5] ; @05227
    mov [si+0x4],ah ; @0522A
    mov ah,[si+0x6] ; @0522D
    mov [si+0x5],ah ; @05230
    mov [si+0x6],al ; @05233
    dec dh ; @05236
    jns loc_520E ; @05238
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0523A
    mov al,[si] ; @0523C
    shr al,1 ; @0523E
    shr al,1 ; @05240
    shr al,1 ; @05242
    and al,0x1 ; @05244
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05246
    mov al,[si+0x1] ; @05248
    shr al,1 ; @0524B
    and al,0x2 ; @0524D
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @0524F
    mov al,[si+0x2] ; @05251
    and al,0x4 ; @05254
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05256
    mov al,[si+0x3] ; @05258
    shl al,1 ; @0525B
    shl al,1 ; @0525D
    shl al,1 ; @0525F
    and al,0x8 ; @05261
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05263
    mov al,[si+0x4] ; @05265
    shl al,1 ; @05268
    shl al,1 ; @0526A
    shl al,1 ; @0526C
    and al,0x10 ; @0526E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05270
    mov al,[si+0x5] ; @05272
    shl al,1 ; @05275
    shl al,1 ; @05277
    shl al,1 ; @05279
    shl al,1 ; @0527B
    shl al,1 ; @0527D
    and al,0x20 ; @0527F
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05281
    mov al,[si+0x6] ; @05283
    shl al,1 ; @05286
    shl al,1 ; @05288
    shl al,1 ; @0528A
    shl al,1 ; @0528C
    and al,0xc0 ; @0528E
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @05290
    cmp ah,[LevelResourceSelectionByte-GameDataImage] ; @05292
    jnz loc_52D3 ; @05296
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @05298
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0529B
    mov cl,0x1e ; @0529D
    div cl ; @0529F
    mov [MenuLevelGroupIndex-GameDataImage],al ; @052A1
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @052A4
    mov al,[si] ; @052A6
    shr al,1 ; @052A8
    and al,0x1 ; @052AA
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052AC
    mov al,[si+0x2] ; @052AE
    shl al,1 ; @052B1
    and al,0x2 ; @052B3
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052B5
    mov al,[si+0x4] ; @052B7
    shl al,1 ; @052BA
    shl al,1 ; @052BC
    and al,0x4 ; @052BE
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052C0
    mov al,[si+0x5] ; @052C2
    shl al,1 ; @052C5
    shl al,1 ; @052C7
    and al,0x8 ; @052C9
    db 0x0a,0xe0 ; ENCODED: or ah,al (NASM chooses a different encoding) ; @052CB
    mov [LevelCodePayloadByte-GameDataImage],ah ; @052CD
    db 0x2a,0xe4 ; ENCODED: sub ah,ah (NASM chooses a different encoding) ; @052D1
loc_52D3:
LevelCodeDecodeReturn:
    ret ; @052D3
times -(($-$$) != 0x52d4) db 0 ; module end assertion
