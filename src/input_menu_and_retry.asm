; Maintained span43CE..4B5B; physical order/UNKNOWN preserved.
; S8 STATIC DATA CONTRACT (classification/name changes are integration proposals):
; Text streams below live in the main DS frame, not at numerically equal CS
; offsets. 4D4D reads {column,row,style,text...,CR} records; column0 ends the
; stream, column is decremented as a byte, row is used directly, style0 sets
; BP2 and any nonzero style sets BP0. NUL inside text is a glyph, not an end.
; LODSB follows incoming DF and wraps SI16; glyph saves/returns are live SS,
; CL wraps per glyph, returned DS/ES remain live. No length or printable check.
; All finite stored-stream boundaries here describe DF0, intact headers/CRs
; and nonaliasing saves; they do not bound arbitrary raw-entry traversal.
; These process-image tables/text survive4551's0000..0FC9 clear. Startup's
; ordinary DF0 clear ends2011. GROUND1A18 can overwrite201F..2B4A on a long
; read (supplied files end1F6A); indexed/string/provider/stack aliases remain.
; No host string copy, muted service or replacement table closes that domain.
times -(($-$$) != 0x43ce) db 0
; Live latch77 returnsCL2 without touching DX/IF. Other bytes poll201 underCLI,
; STI then NOTAL/TESTF0; upper inactivity loops back through the latch read.
; Active bits30 chooseCL0, otherwiseCL1; AH/CH and the full invertedAL stay live.
; Core before43ED; actualRET may alias state. docs/keyboard-input.md.
ChooseInputController:
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @043CE
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @043D1
    jz loc_43D9 ; @043D3
    cmp al,0x77 ; @043D5
    jz loc_43EE ; @043D7
loc_43D9:
    cli ; @043D9
    mov dx,0x201 ; @043DA
    in al,dx ; @043DD
    sti ; @043DE
    not al ; @043DF
    test al,0xf0 ; @043E1
    jz ChooseInputController ; @043E3
    db 0x32,0xc9 ; ENCODED: xor cl,cl (NASM chooses a different encoding) ; @043E5
    test al,0x30 ; @043E7
    jnz loc_43ED ; @043E9
    inc cl ; @043EB
loc_43ED:
InputControllerChoiceReturn43ED:
    ret ; @043ED
loc_43EE:
    mov cl,0x2 ; @043EE
    jmp short loc_43ED ; @043F0
EnterMainMenu:
; Five real child calls precede fallthrough4401. BIOS keeps its existing logical
; service ABI; DOS probe uses actual INT21/IRET frames. No extra menu-entry RET.
    call SetupDisplayModeAndLayout ; @043F2
MenuStartupAfterCall43F2:
    call ClearFullDrawingPage ; @043F5
MenuStartupAfterCall43F5:
    call InstallMenuTimerVector ; @043F8
MenuStartupAfterCall43F8:
    call PublishMenuPalette ; @043FB
MenuStartupAfterCall43FB:
    call CheckMenuResourceAvailability ; @043FE
loc_4401:
; Connected refresh: actual near calls flow through returnedDS/ES/SS/flags.
; Reset origins,caches,toggle; option index1F71 and SoundOptionBits survive.
; Draw/copy both pages then release-wait. No nearRET: exits are actual JMPs.
; Scope4401..454B excludes three UNKNOWN table bytes and two UNKNOWN NOP bytes.
MenuRefresh4401:
MenuStartupAfterCall43FE:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04401
    mov word [AlternateDrawingOrigin-GameDataImage],0x6d60 ; @04407
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @0440D
    call ProgramAlternateDisplayStart ; @04413
MainMenuAfterCall4413:
    mov byte [MenuLevelGroupRedrawCache-GameDataImage],0xff ; @04416
    mov byte [MenuSoundRedrawCache-GameDataImage],0xff ; @0441B
    mov byte [MenuSoundRedrawToggle-GameDataImage],0x0 ; @04420
    call TransitionPaletteToSlot1 ; @04425
MainMenuAfterCall4425:
    call ClearFullDrawingPage ; @04428
MainMenuAfterCall4428:
    call DrawScreenBackground ; @0442B
MainMenuAfterCall442B:
    call InitializeMenuScroll ; @0442E
MainMenuAfterCall442E:
    call InitializeMenuAnimations ; @04431
MainMenuAfterCall4431:
    call DrawMenuBackdropLayers ; @04434
MainMenuAfterCall4434:
    call DrawMenuDecorationRows ; @04437
MainMenuAfterCall4437:
    lea si,[MainMenuText-GameDataImage] ; @0443A
; DS4AD9..4B09: two records, CRs4AF3/4B08, terminal column0 at4B09.
; Credits scroller49CE..4AD8 has a DIFFERENT grammar (FF pause, CR restart).
    call DrawTextStream ; @0443E
MainMenuAfterCall443E:
    call RefreshMenuLevelGroupGraphic ; @04441
MainMenuAfterCall4441:
    call RefreshMenuSoundGraphic ; @04444
MainMenuAfterCall4444:
    call CopyDrawingPageToAlternate ; @04447
MainMenuAfterCall4447:
    call WaitForDisplayStatusBit3Cycle ; @0444A
MainMenuAfterCall444A:
    call ProgramAlternateDisplayStart ; @0444D
MainMenuAfterCall444D:
    call TransitionPaletteToSlot2 ; @04450
loc_4453:
MainMenuReleaseWait:
MainMenuAfterCall4450:
    mov ax,[InputButtonsWord-GameDataImage] ; @04453
    test ax,0x7 ; @04456
    jnz loc_4453 ; @04459
loc_445B:
; Literal frame order: display wait,scroll,animation,group,sound,display swap.
; Read live buttons only after all children; keyboard then drives actual exits.
RunMainMenuFrame:
    call WaitForDisplayStatusBit3Cycle ; @0445B
MainMenuAfterCall445B:
    call AdvanceMenuScroll ; @0445E
MainMenuAfterCall445E:
    call AdvanceMenuAnimations ; @04461
MainMenuAfterCall4461:
    call RefreshMenuLevelGroupGraphic ; @04464
MainMenuAfterCall4464:
    call RefreshMenuSoundGraphic ; @04467
MainMenuAfterCall4467:
    call SwapDrawingOriginsAndDisplay ; @0446A
MainMenuAfterCall446A:
    mov ax,[InputButtonsWord-GameDataImage] ; @0446D
    test ax,0x7 ; @04470
    jz loc_4478 ; @04473
    jmp loc_454C ; @04475
loc_4478:
ReadMainMenuKeyboard:
    call ReadKeyboardCharacter ; @04478
MainMenuAfterCall4478:
    cmp al,0x80 ; @0447B
    jnz loc_4482 ; @0447D
    jmp loc_454C ; @0447F
loc_4482:
    cmp al,0x81 ; @04482
    jz loc_44AD ; @04484
    cmp al,0x82 ; @04486
    jz loc_44B3 ; @04488
    cmp al,0x83 ; @0448A
    jz loc_44B0 ; @0448C
    cmp al,0x1b ; @0448E
    jnz loc_4495 ; @04490
    jmp loc_04D0 ; @04492
loc_4495:
    cmp al,0x8a ; @04495
    jz loc_44EC ; @04497
    cmp al,0x60 ; @04499
    jz loc_44EC ; @0449B
    cmp al,0x8b ; @0449D
    jnz loc_44A4 ; @0449F
    jmp short loc_451C ; @044A1
; S14 U063: [044A3,044A4) stored bytes remain UNKNOWN.
; Neighbours: P 044A1 jmp 0x451c; N 044A4 cmp al, 0x2d.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @044A3
loc_44A4:
    cmp al,0x2d ; @044A4
    jnz loc_44AB ; @044A6
    jmp short loc_451C ; @044A8
; S14 U064: [044AA,044AB) stored bytes remain UNKNOWN.
; Neighbours: P 044A8 jmp 0x451c; N 044AB jmp 0x445b.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @044AA
loc_44AB:
    jmp short loc_445B ; @044AB
loc_44AD:
    jmp loc_4967 ; @044AD
loc_44B0:
    jmp loc_4A01 ; @044B0
loc_44B3:
; Exact marker2 blocks cycling. XOR whole toggle byte under incoming bus flags;
; INC option wraps only on equality with2 or3 (driver must equalFF for3).
; CS table indexing remains unchecked. See docs/main-menu.md.
    cmp byte [MenuSoundRedrawCache-GameDataImage],0x2 ; @044B3
    jz loc_445B ; @044B8
    xor byte [MenuSoundRedrawToggle-GameDataImage],0xff ; @044BA
    mov al,[MenuSoundOptionIndex-GameDataImage] ; @044BF
    inc al ; @044C2
    mov ah,0x3 ; @044C4
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @044C6
    jz loc_44CF ; @044CB
    mov ah,0x2 ; @044CD
loc_44CF:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @044CF
    jnz loc_44D5 ; @044D1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @044D3
loc_44D5:
    mov [MenuSoundOptionIndex-GameDataImage],al ; @044D5
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @044D8
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @044DA
    add bx,MenuSoundOptionValues ; @044DC
    mov al,[cs:bx] ; @044E0
    mov [0x25a7],al ; @044E3
    jmp loc_445B ; @044E6
; UNKNOWN: unresolved bytes
MenuSoundOptionValues:
; Stored CS44E9..44EB =00,01,03, skipped by JMP44E6; no decoded entry here.
; Initial1F71: startup clear0; sound setup0596/0606->1,05AE/05D8->2.
;44D5 writes byte(INC old), resetting only on equality with limit2/3.
; With valid initial index and stable driver gate this selects0..1 or0..2;
; corrupt/stale indices or a changed gate are NOT clamped. CS read window for
; arbitrary prior index is44E9..45E8. No identified ordinary direct table store;
; CS/SS/device aliases and checksum8397's code-as-data read remain possible.
    db 0x00,0x01,0x03 ; @044E9
loc_44EC:
; Marker4 blocks changes. Increase rejects exactly3, decrease rejects exactly0;
; other byte values retain wrap. Literal AH additions publish group*30 modulo256.
    cmp byte [MenuLevelGroupRedrawCache-GameDataImage],0x4 ; @044EC
    jnz loc_44F6 ; @044F1
    jmp loc_445B ; @044F3
loc_44F6:
    mov al,[MenuLevelGroupIndex-GameDataImage] ; @044F6
    cmp al,0x3 ; @044F9
    jnz loc_4500 ; @044FB
    jmp loc_445B ; @044FD
loc_4500:
    inc al ; @04500
    mov [MenuLevelGroupIndex-GameDataImage],al ; @04502
    shl al,1 ; @04505
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @04507
    shl al,1 ; @04509
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0450B
    shl al,1 ; @0450D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0450F
    shl al,1 ; @04511
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04513
    mov [LevelResourceSelectionByte-GameDataImage],ah ; @04515
    jmp loc_445B ; @04519
loc_451C:
    cmp byte [MenuLevelGroupRedrawCache-GameDataImage],0x4 ; @0451C
    jnz loc_4526 ; @04521
    jmp loc_445B ; @04523
loc_4526:
    mov al,[MenuLevelGroupIndex-GameDataImage] ; @04526
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04529
    jnz loc_4530 ; @0452B
    jmp loc_445B ; @0452D
loc_4530:
    dec al ; @04530
    mov [MenuLevelGroupIndex-GameDataImage],al ; @04532
    shl al,1 ; @04535
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @04537
    shl al,1 ; @04539
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0453B
    shl al,1 ; @0453D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0453F
    shl al,1 ; @04541
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04543
    mov [LevelResourceSelectionByte-GameDataImage],ah ; @04545
    jmp loc_445B ; @04549
; LEVEL START: reset1F6D only at454C;47DD enters common4551 without resetting it.
; Actual PUSH DS/POP ES owns the DF-sensitive0FCA-byte clear; AH remains live.
; Real CALL197D returns through4560,then CALL4566 through4563 before JMP00FB.
; Briefing20h consumes its caller word intoAX and JMPs4401; no second POP/RET.
; Native selector-own bus retains DAT/raw RAM/DOS/retry/fatal seams; docs/level-start.md.
loc_454C:
MainMenuStartLevel:
    mov byte [LevelOutcomeSuccessByte-GameDataImage],0x0 ; @0454C
; [04551] Per-level455B DF-clear reset0000..0FC9 zeroes0043 and callback slots.03E7 itself does not clear records;0462->0FB2 reinstalls002E..003F,046B loads header byte0047, then0483 may call creation.455B has no local CLD;DF=1 cannot be treated as equivalent reset. Normal known reuse is this reset plus per-slot30F3 initialization, not an inactive-slot free list.
loc_4551:
LoadAndStartSelectedLevel:
; Per-level state lifetime: DF-clear0000..0FC9 includes entity globals/records;
; loaded record0FCB and resource globals above the clear retain separate owners.
;03E7 later initializes session controls and SS maps, not this record array.
    push ds ; @04551
    pop es ; @04552
    mov di,0x0 ; @04553
    mov cx,0xfca ; @04556
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04559
    rep stosb ; @0455B
    call LoadSelectedLevelResources ; @0455D
LevelStartAfterResources:
    call ShowLevelBriefing ; @04560
LevelStartAfterBriefing:
    jmp loc_00FB ; @04563
; BRIEFING: wrapped byte selection minus30*group, live header fields and byte DIV.
; Zero divisor/quotient overflow remain processor-fault seams, never clamped.
; Actual PUSH DS/POP ES owns the DF-sensitive32-byte title copy; rating row is unchecked.
; Native redraw/preview feed the partial clear, background/text and split-palette wait.
; Button/40h tail-fades with inherited RET;20h calls fade, POPs actual AX, JMPs4401.
; New wrappers and parent use shared bounded verification; docs/level-briefing.md.
ShowLevelBriefing:
; MUTABLE DS4B0A..4B9F, seven records, terminal4B9F. Writers before draw4640:
;4584 pair4B13..14;458E decimal4B50..52;45A5 percent4B57..5A;
;45AF pair4B78..79;45B7 time4B83 (byte+30 wraps);45C2 plural4B8B.
;45D3 copies32 bytes17AB..17CA to4B19..38 only with DF0; DF1 source/dest
; run178D..17AC/4AFB..4B1A. Text CR4B39 is outside either copy, but copied
; title bytes may themselves contain CR/NUL; no sanitization is performed.
;45E5 copies six bytes from4C01+6*zero_extended_group with explicit forward
; INCs to4B98..9D. Four stored rating rows4C01..4C18 are fixed-width, no NUL;
; group is unchecked, so byte255 reads51FB..5200, not a fifth rating row.
; Formatter widths are write footprints, not validation of population/rate.
    mov al,[MenuLevelGroupIndex-GameDataImage] ; @04566
    shl al,1 ; @04569
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0456B
    shl al,1 ; @0456D
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @0456F
    shl al,1 ; @04571
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04573
    shl al,1 ; @04575
    db 0x02,0xe0 ; ENCODED: add ah,al (NASM chooses a different encoding) ; @04577
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @04579
    inc al ; @0457C
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @0457E
    lea si,[0x4b13] ; @04580
    call WriteDecimalBytePair ; @04584
BriefingAfter4584:
    mov al,[0xfce] ; @04587
    lea si,[0x4b50] ; @0458A
    call WriteDecimalByteField ; @0458E
BriefingAfter458E:
    mov al,[0xfd0] ; @04591
    mov cl,0x64 ; @04594
    mul cl ; @04596
    mov cl,[0xfce] ; @04598
BriefingPercentDivide:
    div cl ; @0459C
    mov [0x41],al ; @0459E
    lea si,[0x4b57] ; @045A1
    call WritePercentageByteField ; @045A5
BriefingAfter45A5:
    mov al,[0xfcc] ; @045A8
    lea si,[0x4b78] ; @045AB
    call WriteDecimalBytePair ; @045AF
BriefingAfter45AF:
    mov al,[0xfd2] ; @045B2
    add al,0x30 ; @045B5
    mov [0x4b83],al ; @045B7
    mov ah,0x73 ; @045BA
    cmp al,0x31 ; @045BC
    jnz loc_45C2 ; @045BE
    mov ah,0x20 ; @045C0
loc_45C2:
    mov [0x4b8b],ah ; @045C2
    lea si,[0x17ab] ; @045C6
    lea di,[0x4b19] ; @045CA
    push ds ; @045CE
    pop es ; @045CF
    mov cx,0x10 ; @045D0
    rep movsw ; @045D3
    mov al,[MenuLevelGroupIndex-GameDataImage] ; @045D5
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @045D8
    mov cx,0x6 ; @045DA
    mul cx ; @045DD
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @045DF
    lea si,[0x4b98] ; @045E1
loc_45E5:
    mov al,[bx+0x4c01] ; @045E5
    mov [si],al ; @045E9
    inc bx ; @045EB
    inc si ; @045EC
    loop loc_45E5 ; @045ED
    call ClearFullDrawingPage ; @045EF
loc_45F2:
BriefingAfter45EF:
    mov cx,0x10 ; @045F2
    mov dx,0x10 ; @045F5
    call StepSplitPaletteToSlot1 ; @045F8
BriefingAfter45F8:
    jnz loc_45F2 ; @045FB
    mov al,0x1 ; @045FD
    nop ; @045FF
    call PublishSixteenPaletteColors ; @04600
BriefingAfter4600:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04603
    mov word [AlternateDrawingOrigin-GameDataImage],0x0 ; @04609
    call SwapDrawingOriginsAndDisplay ; @0460F
BriefingAfter460F:
    call RedrawLevel ; @04612
BriefingAfter4612:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04615
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @0461B
    call DrawLevelPreview ; @04621
BriefingAfter4621:
    mov word [DrawingOrigin-GameDataImage],0x0 ; @04624
    mov word [DrawingPageByteOffset-GameDataImage],0x0 ; @0462A
    call ClearBelowLevelPreview ; @04630
BriefingAfter4630:
    call SetupDisplayLayout ; @04633
BriefingAfter4633:
    mov bx,0x4e ; @04636
    call DrawScreenBackgroundFromRow ; @04639
BriefingAfter4639:
    lea si,[0x4b0a] ; @0463C
    call DrawTextStream ; @04640
BriefingAfter4640:
; Continue prompts: mode0 ->4BA0..4BC2, mode1 ->4BC3..4BE4, all other
; byte values ->4BE5..4C00. Each includes its own final CR and column0.
    lea si,[0x4ba0] ; @04643
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @04647
    jz loc_465D ; @0464C
    lea si,[0x4bc3] ; @0464E
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @04652
    jz loc_465D ; @04657
    lea si,[0x4be5] ; @04659
loc_465D:
    call DrawTextStream ; @0465D
loc_4660:
BriefingAfter465D:
    mov ax,[InputButtonsWord-GameDataImage] ; @04660
    test ax,0x7 ; @04663
    jnz loc_4660 ; @04666
loc_4668:
    call RefreshRasterSplitPalette ; @04668
BriefingAfter4668:
    mov al,0x0 ; @0466B
    nop ; @0466D
    call PublishUpperEightPaletteColors ; @0466E
BriefingAfter466E:
    mov cx,0x10 ; @04671
    mov dx,0x10 ; @04674
    mov bx,0x302 ; @04677
    nop ; @0467A
    call StepSplitPaletteToTargets ; @0467B
BriefingAfter467B:
    jnz loc_4668 ; @0467E
loc_4680:
    call RefreshRasterSplitPalette ; @04680
BriefingAfter4680:
    mov ax,[InputButtonsWord-GameDataImage] ; @04683
    test ax,0x7 ; @04686
    jnz FadeAndClearSplitPalette ; @04689
    mov ax,[0x1fc7] ; @0468B
    test ax,0x20 ; @0468E
    jnz loc_469B ; @04691
    test ax,0x40 ; @04693
    jz loc_4680 ; @04696
    jmp short FadeAndClearSplitPalette ; @04698
; S14 U066: [0469A,0469B) stored bytes remain UNKNOWN.
; Neighbours: P 04698 jmp 0x46a2; N 0469B call 0x46a2.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @0469A
loc_469B:
    call FadeAndClearSplitPalette ; @0469B
    pop ax ; @0469E
    jmp loc_4401 ; @0469F
; Repeated raster refresh, upper8 publication and two live row steps. Returned
; ZF decides loop before tailJMP into full-page clear; no extra caller frame.
FadeAndClearSplitPalette:
    call RefreshRasterSplitPalette ; @046A2
SplitPaletteFadeAfterRefresh46A5:
    mov al,0x0 ; @046A5
    nop ; @046A7
    call PublishUpperEightPaletteColors ; @046A8
SplitPaletteFadeAfterUpper46AB:
    mov cx,0x10 ; @046AB
    mov dx,0x10 ; @046AE
    call StepSplitPaletteToSlot1 ; @046B1
SplitPaletteFadeAfterStep46B4:
    jnz FadeAndClearSplitPalette ; @046B4
    jmp ClearFullDrawingPage ; @046B6
; ADDDL6 retainsDH; wait bit3 high->low, CLI/savedDX and publish slot0 first8.
; Pop actualDX, CLI,60 bit0 low->high cycles, publish slot7 first8, STI/RET.
RefreshRasterSplitPalette:
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @046B9
    add dl,0x6 ; @046BD
loc_46C0:
SplitPaletteVerticalHighInput46C0:
    in al,dx ; @046C0
    test al,0x8 ; @046C1
    jz loc_46C0 ; @046C3
loc_46C5:
SplitPaletteVerticalLowInput46C5:
    in al,dx ; @046C5
    test al,0x8 ; @046C6
    jnz loc_46C5 ; @046C8
    cli ; @046CA
    push dx ; @046CB
    mov al,0x0 ; @046CC
    nop ; @046CE
    call PublishEightPaletteColors ; @046CF
SplitPaletteAfterTopPublish46D2:
    pop dx ; @046D2
    cli ; @046D3
    mov cx,0x3c ; @046D4
loc_46D7:
SplitPaletteHorizontalLowInput46D7:
    in al,dx ; @046D7
    test al,0x1 ; @046D8
    jnz loc_46D7 ; @046DA
loc_46DC:
SplitPaletteHorizontalHighInput46DC:
    in al,dx ; @046DC
    test al,0x1 ; @046DD
    jz loc_46DC ; @046DF
    loop loc_46D7 ; @046E1
    mov al,0x7 ; @046E3
    nop ; @046E5
    call PublishEightPaletteColors ; @046E6
SplitPaletteAfterBottomPublish46E9:
    sti ; @046E9
SplitPaletteRasterReturn46EA:
    ret ; @046EA
loc_46EB:
LevelResultScreen:
; RESULT STREAMS (DS, inclusive; final byte is column0): time-up4C19..4C2D,
; all-out4C2E..4C4D; percentages4C4E..4C76, whose four-byte fields4C5D..60
; and4C71..74 are written by48C4/48CE.48EB saves a menu prompt in DS0021:
; mode0 4C77..4C9C, mode1 4C9D..4CB8, other4CB9..4CD2, later drawn47A3.
; Failure retry:4CD3..4CFD /4CFE..4D1F /4D20..4D3E by the same mode rule.
; Success:4D3F..4D73 has level digits4D5D..5F (474F), generated code4D68..71
; (5052..51A1) and CR4D72.4D74 is an extra stored00, not consumed by this
; stream. Next-level prompts start4D75/4DA0/4DC2 and end4D9F/4DC1/4DE0.
; Assessment4955's nine pointers each lead to two records at4F33,4F77,4FBC,
;5003,504E,5091,50DE,512C,517A, ending4F76,4FBB,5002,504D,5090,50DD,
;512B,5179,51CA.48F6 bounds this pointer index0..8 through its comparisons.
; Final completion text51CB..52BB contains six records;47E7 selects it.
; SESSION EXIT (JMP from 0311 after the timer is restored): menu video/palette/
; timer, time-up or all-out text by the 0:00 test, then pass/fail by signed
; completion >= DS:0041. Passed advances the selection; failed keeps it. After
; buttons are released: button0 -> 4551 reloads (clear 0000..0FC9) -> 00FB a
; new session; button1/keys 20/40 -> main menu 4401; 120 levels -> final screen.
; READINESS: READY and translated (c/level_result.c) to the stops at JMP 4401/
; 4551; the button/key spins read IRQ-produced words through LmnForegroundPoll.
; Children keep their menu/palette/timer/text domains; 4728 stays unresolved.
    call ClearFullDrawingPage ; @046EB
    call SetupDisplayModeAndLayout ; @046EE
    call PublishMenuPalette ; @046F1
    call TransitionPaletteToSlot1 ; @046F4
    call ClearFullDrawingPage ; @046F7
    call InstallMenuTimerVector ; @046FA
    call DrawScreenBackground ; @046FD
    call DrawResultPercentagesAndPrompt ; @04700
    lea si,[0x4c19] ; @04703
    mov al,[LevelCountdownHighDigit-GameDataImage] ; @04707
    mov bx,[0x20a9] ; @0470A
    db 0x0a,0xd8 ; ENCODED: or bl,al (NASM chooses a different encoding) ; @0470E
    cmp bx,0x3030 ; @04710
    jz loc_471A ; @04714
    lea si,[0x4c2e] ; @04716
loc_471A:
    call DrawTextStream ; @0471A
    mov al,[StatusCompletionDisplayValue-GameDataImage] ; @0471D
    cmp al,[0x41] ; @04720
    jnl loc_4729 ; @04724
    jmp short loc_4778 ; @04726
; S14 U067: [04728,04729) stored bytes remain UNKNOWN.
; Neighbours: P 04726 jmp 0x4778; N 04729 mov byte ptr [0x1f6d], 0xff.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @04728
loc_4729:
ResultLevelPassed:
    mov byte [LevelOutcomeSuccessByte-GameDataImage],0xff ; @04729
    inc byte [LevelResourceSelectionByte-GameDataImage] ; @0472E
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @04732
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04735
    mov cl,0x1e ; @04737
    div cl ; @04739
    mov [MenuLevelGroupIndex-GameDataImage],al ; @0473B
    cmp byte [LevelResourceSelectionByte-GameDataImage],0x78 ; @0473E
    jc loc_4748 ; @04743
    jmp loc_47E0 ; @04745
loc_4748:
    call FormatSelectedLevelAndGroup ; @04748
    lea si,[0x4d5d] ; @0474B
    call WriteDecimalByteField ; @0474F
    call EncodeLevelCode ; @04752
    lea si,[0x4d3f] ; @04755
    call DrawTextStream ; @04759
    lea bx,[0x4d75] ; @0475C
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @04760
    jz loc_4776 ; @04765
    lea bx,[0x4da0] ; @04767
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @0476B
    jz loc_4776 ; @04770
    lea bx,[0x4dc2] ; @04772
loc_4776:
    jmp short loc_4797 ; @04776
loc_4778:
ResultLevelFailed:
    mov byte [LevelOutcomeSuccessByte-GameDataImage],0x0 ; @04778
    lea bx,[0x4cd3] ; @0477D
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @04781
    jz loc_4797 ; @04786
    lea bx,[0x4cfe] ; @04788
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @0478C
    jz loc_4797 ; @04791
    lea bx,[0x4d20] ; @04793
loc_4797:
    push bx ; @04797
    call DrawResultAssessmentMessage ; @04798
    pop si ; @0479B
    call DrawTextStream ; @0479C
    mov si,[UiScrollPhaseOrPromptPointer-GameDataImage] ; @0479F
    call DrawTextStream ; @047A3
    call TransitionPaletteToSlot2 ; @047A6
loc_47A9:
ResultWaitButtonsReleased:
    mov ax,[InputButtonsWord-GameDataImage] ; @047A9
    test ax,0x7 ; @047AC
    jnz loc_47A9 ; @047AF
loc_47B1:
ResultWaitChoice:
    mov ax,[InputButtonsWord-GameDataImage] ; @047B1
    test ax,0x1 ; @047B4
    jnz loc_47D7 ; @047B7
    test ax,0x2 ; @047B9
    jnz loc_47CB ; @047BC
    mov ax,[0x1fc7] ; @047BE
    test ax,0x20 ; @047C1
    jnz loc_47CB ; @047C4
    test ax,0x40 ; @047C6
    jz loc_47B1 ; @047C9
loc_47CB:
ResultToMainMenu:
    call TransitionPaletteToSlot1 ; @047CB
    call ClearFullDrawingPage ; @047CE
    call SetupDisplayModeAndLayout ; @047D1
    jmp loc_4401 ; @047D4
loc_47D7:
ResultStartSelectedLevel:
    call TransitionPaletteToSlot1 ; @047D7
    call ClearFullDrawingPage ; @047DA
    jmp loc_4551 ; @047DD
loc_47E0:
AllLevelsCompletedScreen:
    call DrawScreenBackground ; @047E0
    lea si,[0x51cb] ; @047E3
    call DrawTextStream ; @047E7
    lea si,[0x4ba0] ; @047EA
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @047EE
    jz loc_4804 ; @047F3
    lea si,[0x4bc3] ; @047F5
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @047F9
    jz loc_4804 ; @047FE
    lea si,[0x4be5] ; @04800
loc_4804:
    call DrawTextStream ; @04804
    call TransitionPaletteToSlot2 ; @04807
loc_480A:
    mov ax,[InputButtonsWord-GameDataImage] ; @0480A
    test ax,0x7 ; @0480D
    jnz loc_481F ; @04810
    mov ax,[0x1fc7] ; @04812
    test ax,0x20 ; @04815
    jnz loc_481F ; @04818
    test ax,0x40 ; @0481A
    jz loc_480A ; @0481D
loc_481F:
    call TransitionPaletteToSlot1 ; @0481F
    mov byte [LevelResourceSelectionByte-GameDataImage],0x0 ; @04822
    mov byte [MenuLevelGroupIndex-GameDataImage],0x0 ; @04827
    jmp loc_4401 ; @0482C
; SOUND ID: any nonzero2010 enables selection. Special byte uses unchecked
; decremented index. Normal success increments1F6C,wraps only exact17 tozero.
; Without success AL remainszero,so select first ID rather than cached1F6C.
; Normal PUSH AX/POP AX is live and can alias output54. UNKNOWN tables remain
; explicit; original-byte lookup is canonical data,not an opcode fallback.
; Native connected setup and all256 byte inputs: docs/game-prepare.md.
; Nominal producers: startup clear gives1F6C=0; only decoded local store4852
; advances it on success.4551's per-level clear excludes it. With stable valid
; state it cycles0..16; special0FE8 comes from LEVEL header (197D load), not
; from this table. Supplied files contain special1..4, normal0; no code guard
; enforces that asset domain. Larger GROUND/other aliases can change1F6C.
SelectLevelSoundId:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0x0 ; @0482F
    jz loc_4865 ; @04834
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @04836
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04839
    jz loc_4840 ; @0483B
    jmp short loc_4866 ; @0483D
; S14 U068: [0483F,04840) stored bytes remain UNKNOWN.
; Neighbours: P 0483D jmp 0x4866; N 04840 cmp byte ptr [0x1f6d], 0.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @0483F
loc_4840:
    cmp byte [LevelOutcomeSuccessByte-GameDataImage],0x0 ; @04840
    jz loc_4855 ; @04845
    mov al,[LevelSoundCycleIndex-GameDataImage] ; @04847
    inc al ; @0484A
    cmp al,0x11 ; @0484C
    jnz loc_4852 ; @0484E
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @04850
loc_4852:
    mov [LevelSoundCycleIndex-GameDataImage],al ; @04852
loc_4855:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04855
    push ax ; @04857
    lea bx,[LevelSoundSequenceIds] ; @04858
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0485C
    mov al,[cs:bx] ; @0485E
    mov [LevelSoundId-GameDataImage],al ; @04861
    pop ax ; @04864
loc_4865:
    ret ; @04865
loc_4866:
    dec al ; @04866
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04868
    lea bx,[SpecialLevelSoundIds] ; @0486A
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0486E
    mov al,[cs:bx] ; @04870
    mov [LevelSoundId-GameDataImage],al ; @04873
    ret ; @04876
; UNKNOWN: unresolved bytes
LevelSoundSequenceIds:
; CS4877..4887:17 IDs 06,07,08,0A,0B,04,0C,0D,0E,0F,05,10..15.
; Normal success resets only INC==11h; no-success keeps AL0 from4839, hence
; chooses ID06 regardless of saved cycle. Arbitrary cycle input can read all
;4877..4976 (including special table and following code), without a clamp.
    db 0x06,0x07,0x08,0x0a,0x0b,0x04,0x0c,0x0d,0x0e,0x0f,0x05,0x10,0x11,0x12,0x13,0x14 ; @04877
; UNKNOWN: unresolved bytes
    db 0x15 ; @04887
SpecialLevelSoundIds:
; CS4888..488B:01,09,03,02; nonzero special byte is decremented before
; zero-extension, so raw1..FF reads4888..4986. Raw00 takes the normal path;
; an internal4866 entry with AL0 instead reads4987. End is RET4876/code488C.
; Both tables are initialized by stored image, read with CS, never rewritten
; by this selector. No direct writer found; aliases/checksum are not excluded.
    db 0x01,0x09,0x03,0x02 ; @04888
; Actual savedCX; byteINC selection beforeDIV30, then reread selection afterMUL.
; Zero remainder ->level30 and DECgroup; FF wraps toAXFF1E. No normalization.
FormatSelectedLevelAndGroup:
    push cx ; @0488C
    mov cl,0x1e ; @0488D
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @0488F
    inc al ; @04892
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @04894
    div cl ; @04896
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @04898
    mul cl ; @0489A
    mov cl,[LevelResourceSelectionByte-GameDataImage] ; @0489C
    inc cl ; @048A0
    db 0x2a,0xc8 ; ENCODED: sub cl,al (NASM chooses a different encoding) ; @048A2
    db 0x8b,0xc1 ; ENCODED: mov ax,cx (NASM chooses a different encoding) ; @048A4
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @048A6
    jnz loc_48AE ; @048A8
    mov al,0x1e ; @048AA
    dec ah ; @048AC
loc_48AE:
    pop cx ; @048AE
LevelGroupFormatReturn:
    ret ; @048AF
; S14 U070: [048B0,048BD) stored bytes remain UNKNOWN.
; Neighbours: P 048AF ret; N 048BD mov al, byte ptr [0x40].
; Candidate48B0 saves CX,CH=entryAL,AL=entryAH,CL1E,MUL CL,ADD AL,CH,restores CX,RET. AL=(30*entryAH+entryAL) mod256; AH remains high product BEFORE ADD (carry is not propagated). AX/flags clobber; no data write/DF use. Entry unproved.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x51,0xb1,0x1e,0x8a,0xe8,0x8a,0xc4,0xf6,0xe1,0x02,0xc5,0x59,0xc3 ; @048B0
DrawResultPercentagesAndPrompt:
; Percentage helper writes exactly a four-byte field with variable percent
; position; no new terminator is inserted.48F3 shares DrawTextStream's RET.
    mov al,[StatusCompletionDisplayValue-GameDataImage] ; @048BD
    lea si,[0x4c5d] ; @048C0
    call WritePercentageByteField ; @048C4
    mov al,[0x41] ; @048C7
    lea si,[0x4c71] ; @048CA
    call WritePercentageByteField ; @048CE
    lea si,[0x4c77] ; @048D1
    cmp byte [InputModeByte25A6-GameDataImage],0x0 ; @048D5
    jz loc_48EB ; @048DA
    lea si,[0x4c9d] ; @048DC
    cmp byte [InputModeByte25A6-GameDataImage],0x1 ; @048E0
    jz loc_48EB ; @048E5
    lea si,[0x4cb9] ; @048E7
loc_48EB:
    mov [UiScrollPhaseOrPromptPointer-GameDataImage],si ; @048EB
    lea si,[0x4c4e] ; @048EF
    jmp DrawTextStream ; @048F3
DrawResultAssessmentMessage:
    mov al,[StatusCompletionDisplayValue-GameDataImage] ; @048F6
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @048F9
    mov dl,[0x41] ; @048FB
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @048FF
    mov bx,0x10 ; @04901
    cmp ax,0x64 ; @04904
    jz loc_494D ; @04907
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @04909
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @0490B
    jz loc_494D ; @0490D
    add bx,byte +0x2 ; @0490F
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04912
    shr cx,1 ; @04914
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04916
    jl loc_494D ; @04918
    add bx,byte +0x2 ; @0491A
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @0491D
    sub cx,byte +0x5 ; @0491F
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04922
    jl loc_494D ; @04924
    add bx,byte +0x2 ; @04926
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04929
    dec cx ; @0492B
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @0492C
    jl loc_494D ; @0492E
    add bx,byte +0x2 ; @04930
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04933
    jz loc_494D ; @04935
    add bx,byte +0x2 ; @04937
    db 0x3b,0xc2 ; ENCODED: cmp ax,dx (NASM chooses a different encoding) ; @0493A
    jz loc_494D ; @0493C
    add bx,byte +0x2 ; @0493E
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM chooses a different encoding) ; @04941
    add cx,byte +0x14 ; @04943
    db 0x3b,0xc1 ; ENCODED: cmp ax,cx (NASM chooses a different encoding) ; @04946
    jl loc_494D ; @04948
    add bx,byte +0x2 ; @0494A
loc_494D:
    mov si,[cs:bx+ResultAssessmentTextOffsets] ; @0494D
    jmp DrawTextStream ; @04952
; Nine DS text offsets selected by 48F6 (completion vs DS:0041 requirement):
; 0 none, 1 below half, 2 below req-5, 3 below req-1, 4 req-1, 5 req, 6 below
; req+20, 7 otherwise, 8 completion 100. All are two-line DrawTextStream starts.
ResultAssessmentTextOffsets:
; DATA: lookup_table
    db 0x33,0x4f,0x77,0x4f,0xbc,0x4f,0x03,0x50,0x4e,0x50,0x91,0x50,0xde,0x50,0x2c,0x51 ; @04955
    db 0x7a,0x51 ; @04965
loc_4967:
; Entry4967 composes editor/decoder and returns via JMP4401. Valid result uses
; byte-wrap formatter,actualDS->ES save and six DF-sensitive string copies.
; Success waits<=120 cycles/three live input predicates; invalid waits60 cycles.
MainMenuCodeTransition:
; CODE TEXT: initial497D fills4DF2..4DFB with ten dots;4DE1..4DFD draws
; prompt and that input line.503B redraw starts at4DEF inside the same stream.
; Header4DEF..F1=0F0908, CR4DFC/column0 4DFD; input edits/rotations own ten
; bytes only in the declared editor domain (4CC9/4D18 stack proofs separate).
; Accepted4DFE..4E26 has three decimal bytes4E10..12 and six rating bytes
;4E1F..24; CRs4E14/4E25 and terminal4E26 are not formatter destinations.
;49C0 uses DF-sensitive MOVSB from4C01+6*formatter_AH. With DF1 destination
; is4E1A..4E1F, source is(row_start-5)..row_start; do not assume row copies
; stay within fields under arbitrary DF. Rejected4E27..4E39 is one record.
    call ClearFullDrawingPage ; @04967
CodeEntryAfterCall4967:
    call InitializeDisplayOrigins ; @0496A
CodeEntryAfterCall496A:
    call TransitionPaletteToSlot1 ; @0496D
CodeEntryAfterCall496D:
    call ClearFullDrawingPage ; @04970
CodeEntryAfterCall4970:
    call DrawScreenBackground ; @04973
CodeEntryAfterCall4973:
    lea si,[0x4df2] ; @04976
    mov cx,0xa ; @0497A
loc_497D:
    mov byte [si],0x2e ; @0497D
    inc si ; @04980
    loop loc_497D ; @04981
    lea si,[CodeEntryPromptText-GameDataImage] ; @04983
    call DrawTextStream ; @04987
CodeEntryAfterCall4987:
    call CopyDrawingPageToAlternate ; @0498A
CodeEntryAfterCall498A:
    call WaitForDisplayStatusBit3Cycle ; @0498D
CodeEntryAfterCall498D:
    call ProgramAlternateDisplayStart ; @04990
CodeEntryAfterCall4990:
    call TransitionPaletteToSlot2 ; @04993
CodeEntryAfterCall4993:
    call ReadCodeInput ; @04996
CodeEntryAfterCall4996:
    call DecodeLevelCode ; @04999
CodeEntryAfterCall4999:
    jnz loc_49EC ; @0499C
    mov al,[LevelResourceSelectionByte-GameDataImage] ; @0499E
    call FormatSelectedLevelAndGroup ; @049A1
CodeEntryAfterCall49A1:
    push ax ; @049A4
    lea si,[CodeAcceptedLevelField-GameDataImage] ; @049A5
    call WriteDecimalByteField ; @049A9
CodeEntryAfterCall49A9:
    pop ax ; @049AC
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @049AD
    lea di,[CodeAcceptedRatingField-GameDataImage] ; @049AF
    lea si,[CodeRatingNameRows-GameDataImage] ; @049B3
    push ds ; @049B7
    pop es ; @049B8
    mov cx,0x6 ; @049B9
    mul cl ; @049BC
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @049BE
    rep movsb ; @049C0
    lea si,[CodeAcceptedText-GameDataImage] ; @049C2
    call DrawTextStream ; @049C6
CodeEntryAfterCall49C6:
    call SwapDrawingOriginsAndDisplay ; @049C9
CodeEntryAfterCall49C9:
    mov cx,0x78 ; @049CC
loc_49CF:
    call WaitForDisplayStatusBit3Cycle ; @049CF
CodeEntryAfterCall49CF:
    mov ax,[InputButtonsWord-GameDataImage] ; @049D2
    test ax,0x7 ; @049D5
    jnz loc_49E9 ; @049D8
    mov ax,[0x1fc7] ; @049DA
    test ax,0x20 ; @049DD
    jnz loc_49E9 ; @049E0
    test ax,0x40 ; @049E2
    jnz loc_49E9 ; @049E5
    loop loc_49CF ; @049E7
loc_49E9:
    jmp loc_4401 ; @049E9
loc_49EC:
    lea si,[CodeRejectedText-GameDataImage] ; @049EC
    call DrawTextStream ; @049F0
CodeEntryAfterCall49F0:
    call SwapDrawingOriginsAndDisplay ; @049F3
CodeEntryAfterCall49F3:
    mov cx,0x3c ; @049F6
loc_49F9:
    call WaitForDisplayStatusBit3Cycle ; @049F9
CodeEntryAfterCall49F9:
    loop loc_49F9 ; @049FC
    jmp loc_4401 ; @049FE
loc_4A01:
ShowInputSelection4A01:
; Clear precedes origin initialization. Actual near/far child frames and live
; palette/background/text state flow to4A2E with no invented parent RET.
; Mouse prompt is skipped only for exactFF. docs/keyboard-input.md.
    call ClearFullDrawingPage ; @04A01
InputScreenAfterClear4A04:
    call InitializeDisplayOrigins ; @04A04
InputScreenAfterLayout4A07:
    call TransitionPaletteToSlot1 ; @04A07
InputScreenAfterPalette1_4A0A:
    call DrawScreenBackground ; @04A0A
InputScreenAfterBackground4A0D:
    lea si,[InputChoiceText4E3A-GameDataImage] ; @04A0D
    call DrawTextStream ; @04A11
InputScreenAfterText4A14:
    cmp byte [MouseServicesDisabledByte-GameDataImage],0xff ; @04A14
    jz loc_4A22 ; @04A19
    lea si,[MouseChoiceText4E6E-GameDataImage] ; @04A1B
    call DrawTextStream ; @04A1F
loc_4A22:
InputScreenAfterMouseText4A22:
    call CopyDrawingPageToAlternate ; @04A22
InputScreenAfterCopy4A25:
    call WaitForDisplayStatusBit3Cycle ; @04A25
InputScreenAfterWait4A28:
    call ProgramAlternateDisplayStart ; @04A28
InputScreenAfterDisplay4A2B:
    call TransitionPaletteToSlot2 ; @04A2B
loc_4A2E:
; Active input menu: actual display/character CALLs, exactFF mouse gate1F73,
; controller calibration, mode0/2 stores and scale loop. Escape preserves mode.
; Active selection4A2E..4AC4 ends at4401; screen preparation is composed above.
; See docs/keyboard-input.md for constructed-state and RETF reference limits.
SelectInputMode4A2E:
    call WaitForDisplayStatusBit3Cycle ; @04A2E
InputModeAfterWait4A31:
    call ReadKeyboardCharacter ; @04A31
InputModeAfterCharacter4A34:
    cmp byte [MouseServicesDisabledByte-GameDataImage],0xff ; @04A34
    jz loc_4A3F ; @04A39
    cmp al,0x31 ; @04A3B
    jz short loc_4ABD ; original +126-byte branch; prevent -O0 forward-pass widening ; @04A3D
loc_4A3F:
    cmp al,0x32 ; @04A3F
    jz loc_4A4E ; @04A41
    cmp al,0x33 ; @04A43
    jz loc_4AB5 ; @04A45
    cmp al,0x1b ; @04A47
    jnz loc_4A2E ; @04A49
    jmp loc_4401 ; @04A4B
loc_4A4E:
; Native menu domain4A4E..4ABC: real text/swap/choice/port/scale child frames.
; ReturnedCL2 sets mode2 andJMP4401. Other choices store callback/mode1 before
; measurement, then actualBX/CX baselines before drawing the scale prompt.
; LiveDS/ES/SS/flags and each child return propagate; no invented outerRET.
; Surrounding43F2/4401 remain untranslated. docs/keyboard-input.md.
SelectInputController4A4E:
    lea si,[ControllerChoiceText4E85-GameDataImage] ; @04A4E
    call DrawTextStream ; @04A52
ControllerMenuAfterText4A55:
    call SwapDrawingOriginsAndDisplay ; @04A55
ControllerMenuAfterSwap4A58:
    call ChooseInputController ; @04A58
ControllerMenuAfterChoice4A5B:
    cmp cl,0x2 ; @04A5B
    jz loc_4AB5 ; @04A5E
    cmp cl,0x1 ; @04A60
    jz loc_4A7D ; @04A63
    mov ax,0x4334 ; @04A65
    mov [InputPollCallback-GameDataImage],ax ; @04A68
    mov al,0x1 ; @04A6B
    mov [InputModeByte25A6-GameDataImage],al ; @04A6D
    call PollPort201ButtonsLow ; @04A70
ControllerMenuAfterLow4A73:
    mov [InputAxisBaselineX25A2-GameDataImage],bx ; @04A73
    mov [InputAxisBaselineY25A4-GameDataImage],cx ; @04A77
    jmp short loc_4A95 ; @04A7B
loc_4A7D:
    mov ax,0x4359 ; @04A7D
    mov [InputPollCallback-GameDataImage],ax ; @04A80
    mov al,0x1 ; @04A83
    mov [InputModeByte25A6-GameDataImage],al ; @04A85
    call PollPort201ButtonsHigh ; @04A88
ControllerMenuAfterHigh4A8B:
    mov [InputAxisBaselineX25A2-GameDataImage],bx ; @04A8B
    mov [InputAxisBaselineY25A4-GameDataImage],cx ; @04A8F
    jmp short loc_4A95 ; @04A93
loc_4A95:
    lea si,[ControllerScaleText4EA9-GameDataImage] ; @04A95
    call DrawTextStream ; @04A99
ControllerMenuAfterScaleText4A9C:
    call SwapDrawingOriginsAndDisplay ; @04A9C
loc_4A9F:
; Scoped menu loop: actual display/character CALL frames; unsigned31..34 acceptance.
; SUBAL30 stores2005, then actual JMP4401. No invented RET; surrounding menu open.
; See docs/keyboard-input.md. Both waits retain their original unbounded loops.
SelectInputScale4A9F:
    call WaitForDisplayStatusBit3Cycle ; @04A9F
InputScaleAfterWait4AA2:
    call ReadKeyboardCharacter ; @04AA2
InputScaleAfterCharacter4AA5:
    cmp al,0x31 ; @04AA5
    jc loc_4A9F ; @04AA7
    cmp al,0x34 ; @04AA9
    ja loc_4A9F ; @04AAB
    sub al,0x30 ; @04AAD
    mov [InputAxisScaleSelector2005-GameDataImage],al ; @04AAF
    jmp loc_4401 ; @04AB2
loc_4AB5:
    mov byte [InputModeByte25A6-GameDataImage],0x2 ; @04AB5
    jmp loc_4401 ; @04ABA
loc_4ABD:
    mov byte [InputModeByte25A6-GameDataImage],0x0 ; @04ABD
    jmp loc_4401 ; @04AC2
CheckMenuResourceAvailability:
; 1FDE is the FAT-ID byte sampled from AH1B's returnedDS:BX at009A/009D,
; not the neighboring INT24 critical-error flag1FDF. Only exactFD enters here.
; Both DOS open and close CF failures redraw/retry with returnedDS/SS live.
; AX open handle becomesBX; MOV AH,3E preservesAL. Success clears liveDS:1FDF.
; Input waits test buttons low3 or AH latch; the whole keyboard byte is live.
    cmp byte [StartupFatIdByte1FDE-GameDataImage],0xfd ; @04AC5
    jnz loc_4B1B ; @04ACA
    call TransitionPaletteToSlot1 ; @04ACC
loc_4ACF:
MenuStartupAfterCall4ACC:
    call ClearFullDrawingPage ; @04ACF
MenuStartupAfterCall4ACF:
    call DrawScreenBackground ; @04AD2
MenuStartupAfterCall4AD2:
    lea si,[MenuResourceRetryText-GameDataImage] ; @04AD5
    call DrawTextStream ; @04AD9
MenuStartupAfterCall4AD9:
    call CopyDrawingPageToAlternate ; @04ADC
MenuStartupAfterCall4ADC:
    call WaitForDisplayStatusBit3Cycle ; @04ADF
MenuStartupAfterCall4ADF:
    call ProgramAlternateDisplayStart ; @04AE2
MenuStartupAfterCall4AE2:
    call TransitionPaletteToSlot2 ; @04AE5
MenuStartupAfterCall4AE5:
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @04AE8
loc_4AED:
    mov ax,[InputButtonsWord-GameDataImage] ; @04AED
    test ax,0x7 ; @04AF0
    jnz loc_4AFD ; @04AF3
    mov ah,[KeyboardScanCodeByte-GameDataImage] ; @04AF5
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04AF9
    jz loc_4AED ; @04AFB
loc_4AFD:
    lea dx,[MenuResourceProbeFilename-GameDataImage] ; @04AFD
    mov ax,0x3d00 ; @04B01
    int 0x21 ; @04B04
MenuResourceAfterOpen:
    jc loc_4ACF ; @04B06
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @04B08
    mov ah,0x3e ; @04B0A
    int 0x21 ; @04B0C
MenuResourceAfterClose:
    jc loc_4ACF ; @04B0E
    call TransitionPaletteToSlot1 ; @04B10
MenuStartupAfterCall4B10:
    call ClearFullDrawingPage ; @04B13
MenuStartupAfterCall4B13:
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @04B16
loc_4B1B:
MenuResourceProbeReturn:
    ret ; @04B1B
ShowResourceRetryScreen:
    call SetupDisplayModeAndLayout ; @04B1C
RetryUiAfterSetup:
    call TransitionPaletteToSlot1 ; @04B1F
RetryUiAfterPalette1:
    call ClearFullDrawingPage ; @04B22
RetryUiAfterFirstClear:
    call DrawScreenBackground ; @04B25
RetryUiAfterBackground:
    lea si,[ResourceRetryPromptText-GameDataImage] ; @04B28
    call DrawTextStream ; @04B2C
RetryUiAfterText:
    call CopyDrawingPageToAlternate ; @04B2F
RetryUiAfterCopy:
    call WaitForDisplayStatusBit3Cycle ; @04B32
RetryUiAfterStatus:
    call ProgramAlternateDisplayStart ; @04B35
RetryUiAfterDisplayStart:
    call TransitionPaletteToSlot2 ; @04B38
; CONTRACT: Canonical button word / raw scan-code latch, no CALL/RET frame.
; TEST AX,7 short-circuits scan read; MOV AH retains earlier AL.
; Unbounded original wait, finite providers only in tests; docs/retry-input.md.
RetryInputReset:
RetryUiAfterPalette2:
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @04B3B
WaitForRetryInput:
    mov ax,[InputButtonsWord-GameDataImage] ; @04B40
    test ax,0x7 ; @04B43
    jnz RetryInputReady ; @04B46
    mov ah,[KeyboardScanCodeByte-GameDataImage] ; @04B48
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @04B4C
    jz WaitForRetryInput ; @04B4E
RetryInputReady:
    call TransitionPaletteToSlot1 ; @04B50
RetryUiAfterExitPalette:
    call ClearFullDrawingPage ; @04B53
RetryUiAfterFinalClear:
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @04B56
RetryUiReturn:
    ret ; @04B5B
times -(($-$$) != 0x4b5c) db 0 ; module end assertion
