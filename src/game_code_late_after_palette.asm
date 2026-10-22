; Mixed resource ownership 57D1..5B10; UNKNOWN bytes unchanged.
times -(($-$$) != 0x57d1) db 0 ; module start assertion
sub_57D1:
CopyResourcePlanesToVga:
; DS:SI bytes -> ES=A000. BH planes (zero means 256), CX rows (zero wraps
; through FFFF), BL bytes per REP (zero copies none), AX literal row pitch.
; All row/plane/AX saves reread live SS words; mirrors precede OUT. REP follows
; live DF, SI flows across planes, DI/CX restore per plane. DS/SS/BP unchanged.
    push ax ; @057D1
    mov dx,0xa000 ; @057D2
    mov es,dx ; @057D5
    mov dx,0x3ce ; @057D7
    mov ax,0x1 ; @057DA
    mov [ss:0xc],ax ; @057DD
    out dx,ax ; @057E1
    mov ax,0x5 ; @057E2
    mov [ss:0x0],ax ; @057E5
    out dx,ax ; @057E9
    mov ax,0x3 ; @057EA
    mov [ss:0x2],ax ; @057ED
    out dx,ax ; @057F1
    mov ax,0xff08 ; @057F2
    mov [ss:0xe],ax ; @057F5
    out dx,ax ; @057F9
    pop ax ; @057FA
    mov dx,0x102 ; @057FB
loc_57FE:
    push di ; @057FE
    push cx ; @057FF
    push ax ; @05800
    push dx ; @05801
    db 0x8b,0xc2 ; ENCODED: mov ax,dx (NASM chooses a different encoding) ; @05802
    mov dx,0x3c4 ; @05804
    mov [ss:0x8],ax ; @05807
    out dx,ax ; @0580B
    pop dx ; @0580C
    pop ax ; @0580D
loc_580E:
    push cx ; @0580E
    push di ; @0580F
    push bx ; @05810
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05811
    db 0x8a,0xcb ; ENCODED: mov cl,bl (NASM chooses a different encoding) ; @05813
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @05815
    pop bx ; @05817
    pop di ; @05818
    pop cx ; @05819
    db 0x03,0xf8 ; ENCODED: add di,ax (NASM chooses a different encoding) ; @0581A
    loop loc_580E ; @0581C
    pop cx ; @0581E
    pop di ; @0581F
    shl dh,1 ; @05820
    dec bh ; @05822
    jnz loc_57FE ; @05824
VgaPlaneCopyReturn:
    ret ; @05826
; TABLE HANDOFF:58E8->5CC1 generates the two banks from stored game-DS
;52BC/531C, not from MAIN0's transient decoded frame. Each source is3*16 LE16
;rows, producing8*90h bytes;1FEA is the arena+2E72 selector published1025.
;The90h-paragraph gap to glyph selector1FEC matches900h normal output bytes.
;With intact pointers/saves, selection below is bounded to16 slices0..0870,
;each[+00,+2F] first data,[+30,+5F] second data,[+60,+8F] GC8 controls.
;The two16-row passes at7218 consume all three groups;see its local contract.
;Source/state aliases and allocation failure do not inherit this layout bound.
UpdateFixedWordPattern:
; CONTRACT: actual CALL frames715F then7218; stop on changed child returns.
; Live pointer+bias alignment selects a0090h-byte bank slice, plus0480h only
; when EntitySelectionPresent is exactlyFF. Keep actual PUSH/POP DS and both
; live word-pair swaps. Child STI means finalIF=1; DF remains unchanged.
    call CopyFixedPatternVgaSpans ; @05827
    mov bx,[PointerX-GameDataImage] ; @0582A
    mov cl,[FixedPatternOffsetBias1FE0-GameDataImage] ; @0582E
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05832
    db 0x03,0xd9 ; ENCODED: add bx,cx (NASM chooses a different encoding) ; @05834
    and bl,0x7 ; @05836
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @05839
    shl bx,1 ; @0583B
    shl bx,1 ; @0583D
    shl bx,1 ; @0583F
    shl bx,1 ; @05841
    db 0x8b,0xf3 ; ENCODED: mov si,bx (NASM chooses a different encoding) ; @05843
    shl bx,1 ; @05845
    shl bx,1 ; @05847
    shl bx,1 ; @05849
    db 0x03,0xf3 ; ENCODED: add si,bx (NASM chooses a different encoding) ; @0584B
    cmp byte [EntitySelectionPresent-GameDataImage],0xff ; @0584D
    jnz loc_5858 ; @05852
    add si,0x480 ; @05854
loc_5858:
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @05858
    add bx,byte +0x60 ; @0585A
    mov di,[FixedPatternVgaOffset000C-GameDataImage] ; @0585D
    push ds ; @05861
    mov ds,[GeneratedWordPatternBufferSegment-GameDataImage] ; @05862
    call DrawFixedWordPattern ; @05866
    pop ds ; @05869
    mov ax,[FixedPatternVgaOffset000C-GameDataImage] ; @0586A
    xchg [FixedPatternVgaOffset000E-GameDataImage],ax ; @0586D
    mov [FixedPatternVgaOffset000C-GameDataImage],ax ; @05871
    mov ax,[FixedPatternVgaOffset0008-GameDataImage] ; @05874
    xchg [FixedPatternVgaOffset000A-GameDataImage],ax ; @05877
    mov [FixedPatternVgaOffset0008-GameDataImage],ax ; @0587B
FixedPatternUpdateReturn:
    ret ; @0587E
RestoreVgaRegisterMirrors:
; CONTRACT: CLI then actual PUSH CX, before reading live relocated CS:5884.
; Fixed ES mirror frame is independent of live SS. Each word supplies AH;
; AL is replaced with its literal register index before the ordered OUT.
; XOR AL,AL at58B5 defines arithmetic flags except AF. Restore entry ES from
; CX before live POP CX; STI forces IF before the actual RET58D1.
; Stack/mirror/code aliases and startup's duplicate SS:10 store remain live.
; docs/vga-mirror-restore.md.
    cli ; @0587F
    push cx ; @05880
    mov cx,es ; @05881
VgaMirrorFrameOperand5884 equ $+1
    mov ax,0x143e ; @05883
    mov es,ax ; @05886
    mov dx,0x3c4 ; @05888
    mov ax,[es:VgaMapMaskMirror-RuntimeStackFrame] ; @0588B
    mov al,0x2 ; @0588F
    out dx,ax ; @05891
    mov dx,0x3ce ; @05892
    mov ax,[es:VgaGraphicsModeMirror-RuntimeStackFrame] ; @05895
    mov al,0x5 ; @05899
    out dx,ax ; @0589B
    mov ax,[es:VgaDataRotateMirror-RuntimeStackFrame] ; @0589C
    mov al,0x3 ; @058A0
    out dx,ax ; @058A2
    mov ax,[es:VgaColorCompareMirror-RuntimeStackFrame] ; @058A3
    mov al,0x2 ; @058A7
    out dx,ax ; @058A9
    mov ax,[es:VgaColorCareMirror-RuntimeStackFrame] ; @058AA
    mov al,0x7 ; @058AE
    out dx,ax ; @058B0
    mov ax,[es:VgaSetResetMirror-RuntimeStackFrame] ; @058B1
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @058B5
    out dx,ax ; @058B7
    mov ax,[es:VgaEnableSetResetMirror-RuntimeStackFrame] ; @058B8
    mov al,0x1 ; @058BC
    out dx,ax ; @058BE
    mov ax,[es:VgaBitMaskMirror-RuntimeStackFrame] ; @058BF
    mov al,0x8 ; @058C3
    out dx,ax ; @058C5
    mov ax,[es:VgaReadMapMirror-RuntimeStackFrame] ; @058C6
    mov al,0x4 ; @058CA
    out dx,ax ; @058CC
    mov es,cx ; @058CD
    pop cx ; @058CF
    sti ; @058D0
VgaMirrorRestoreReturn:
    ret ; @058D1
; R1 UNCONDITIONAL normal-startup continuation implication, both modes:1C78 CLD dominates
; the recognized returning DAT handoffs.58E0 ->59BB/5CC1,58F9 ->5AC1,590F ->5927/593C,
; 598A ->59A1/59B7 retain0 through their service-free fixed closures. Thus5815,593C,59B7,
; 5BBA,5BE2,5CE5,5D6E,5D7F useDF0 on those ordinary58D2 call paths. No predecode DF or
; profile assumption is needed for this local reset result. Total returns, raw reentry,
; code/save/source/allocation aliases and IRQ timing remain independent obligations.
; [058D2] MAIN RESOURCE LIFETIMES (full pinned reads, intact selectors/saves):
; all sections read000Ah header then listed payload into source offset0.
; Sec0 payload21D4h/output5270h at[1FE4]:0 ->58E5/58E8 transforms; sec1
; payload00FEh/output0184h replaces same source ->58FE; sec2 payload0CCDh/
; output20C0h replaces it ->5927 plus1900..20BF glyph copy. Sec3 payload
;6D5Eh/outputF210h at[1FEE]:0; sec4 payload344Bh/output8CF0h at
; ([1FEE]+0F21h):0, nominal concatenated UI image[0,17F00h). Segment
; addition wraps as a word. Sec5 payload0295h/output02F6h atliveCS5968
; segment overlays image08420..08715; INT60 later0842:0182, excluding
; unknown8716 onward. Optionalsec6 payload0875h/output2020h reuses[1FE4];
;1900..201F copies to[1FEC]:00A0..07BF, keeping firstA0 glyph bytes.
; Source0/1/2/6 is transient startup work; UI/glyph/generated banks persist
; across levels/sessions.1FE4 later selects level/UI sources; it is not a
; permanent owner. No size/nonalias guard is enforced by1BAF.
LoadMainResourceSections:
; Twelve actual near frames compose the DAT pipeline and graphics producers.
; Every DS/BX restore rereads live SS, including PUSH/POP BX at5964/5965.
; Ordered selector reads remain relative to current DS. Section5's MOV operand
; at5968 is relocated and live (stored0842, loaded1852 at canonical load1010).
; REP copies retain DF and word physical+1 addressing. Child fatal/changed
; returns stop before parent restores. ExactFF gate200E selects section6.
; Core boundary is the actual outer RET59BA. docs/main-resource-sections.md.
    push ds ; @058D2
    mov dx,0x252b ; @058D3
    mov es,[GraphicsResourceSegment-GameDataImage] ; @058D6
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @058DA
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @058DC
    mov cx,es ; @058DE
    call LoadDatResource ; @058E0
    pop ds ; @058E3
    push bx ; @058E4
    call GenerateEntitySpriteBanks ; @058E5
    call GenerateFixedWordMaskBanks ; @058E8
    pop bx ; @058EB
    push ds ; @058EC
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @058ED
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @058EF
    mov es,[GraphicsResourceSegment-GameDataImage] ; @058F1
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @058F5
    call DecodeDatPreservingSegment ; @058F9
    pop ds ; @058FC
    push bx ; @058FD
    call GenerateGraphicsMaskBanks ; @058FE
    pop bx ; @05901
    push ds ; @05902
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05903
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05905
    mov es,[GraphicsResourceSegment-GameDataImage] ; @05907
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @0590B
    call DecodeDatPreservingSegment ; @0590F
    pop ds ; @05912
    push bx ; @05913
    push ds ; @05914
    mov di,0xf91f ; @05915
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05918
    mov cx,0x28 ; @0591A
    mov ax,0x2c ; @0591D
    mov bx,0x428 ; @05920
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05923
    call CopyResourcePlanesToVga ; @05927
    pop ds ; @0592A
    push ds ; @0592B
    mov si,0x1900 ; @0592C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0592F
    mov es,[StatusGlyphBufferSegment-GameDataImage] ; @05931
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05935
    mov cx,0x3e0 ; @05939
; S19 DF-site census rep movsw word ptr es:[di], word ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsw ; @0593C
    pop ds ; @0593E
    pop bx ; @0593F
    push ds ; @05940
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05941
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05943
    mov es,[UiGraphicsBufferSegment-GameDataImage] ; @05945
    mov ds,[UiGraphicsBufferSegment-GameDataImage] ; @05949
    call DecodeDatPreservingSegment ; @0594D
sub_5950:
    pop ds ; @05950
    push ds ; @05951
    mov ax,[UiGraphicsBufferSegment-GameDataImage] ; @05952
    add ax,0xf21 ; @05955
    mov es,ax ; @05958
    mov ds,ax ; @0595A
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0595C
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @0595E
    call DecodeDatPreservingSegment ; @05960
    pop ds ; @05963
    push bx ; @05964
    pop bx ; @05965
    push ds ; @05966
MainResourceSoundSegmentOperand5968 equ $+1
    mov ax,0x842 ; @05967
    mov es,ax ; @0596A
    mov ds,ax ; @0596C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @0596E
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05970
    call DecodeDatPreservingSegment ; @05972
    pop ds ; @05975
    cmp byte [ConfigurationOption200E-GameDataImage],0xff ; @05976
    jnz loc_59BA ; @0597B
sub_597D:
    push ds ; @0597D
    mov es,[GraphicsResourceSegment-GameDataImage] ; @0597E
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05982
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05986
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05988
    call DecodeDatPreservingSegment ; @0598A
    pop ds ; @0598D
    push ds ; @0598E
    mov di,0xf91f ; @0598F
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05992
    mov cx,0x28 ; @05994
    mov ax,0x2c ; @05997
    mov bx,0x428 ; @0599A
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @0599D
    call CopyResourcePlanesToVga ; @059A1
    pop ds ; @059A4
    push ds ; @059A5
    mov di,0xa0 ; @059A6
    mov si,0x1900 ; @059A9
    mov es,[StatusGlyphBufferSegment-GameDataImage] ; @059AC
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @059B0
    mov cx,0x720 ; @059B4
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @059B7
    pop ds ; @059B9
loc_59BA:
MainResourceSectionsReturn:
    ret ; @059BA
; CONTRACT: PUSH DS occurs before ordered reads of incoming DS:1FE6 (ES)
; and DS:1FE4 (source DS). SI=DI=0. Fifteen immediate groups push actual CX,
; call a native-understood leaf through its actual near frame, pop live CX,
; advance SI by the literal source stride, then LOOP without changing FLAGS.
; Returned ES/DI/DS/SS/SP/FLAGS and saved counts remain authoritative. Child
; RET aliases stop native composition at the changed CS:IP before parent POP.
; With intact saves, DF clear and disjoint memory, the 336 grouped calls read
; 50F0h source bytes and emit 180B8h bytes; the final 5C06 call adds 0180h
; source bytes and 1400h output bytes. These are coordinates, not bounds.
; Final ADD SI,0180 precedes actual POP DS and the caller RET at 5AC0.
; The core stops before that RET. No converted sprite data or cached saves.
GenerateEntitySpriteBanks:
    push ds ; @059BB
    mov es,[EntitySpriteBufferSegment-GameDataImage] ; @059BC
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @059C0
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @059C4
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @059C6
    mov cx,0x12 ; @059C8
loc_59CB:
    push cx ; @059CB
    mov dx,0x20a ; @059CC
    call GenerateThreeByteSpriteBanks ; @059CF
    pop cx ; @059D2
    add si,byte +0x28 ; @059D3
    loop loc_59CB ; @059D6
    mov cx,0x10 ; @059D8
loc_59DB:
    push cx ; @059DB
    mov dx,0x30e ; @059DC
    call CopySpritePlanesAndAppendMask ; @059DF
    pop cx ; @059E2
    add si,byte +0x54 ; @059E3
    loop loc_59DB ; @059E6
    mov cx,0x10 ; @059E8
loc_59EB:
    push cx ; @059EB
    mov dx,0x20c ; @059EC
    call CopySpritePlanesAndAppendMask ; @059EF
    pop cx ; @059F2
    add si,byte +0x30 ; @059F3
    loop loc_59EB ; @059F6
    mov cx,0x10 ; @059F8
loc_59FB:
    push cx ; @059FB
    mov dx,0x20a ; @059FC
    call GenerateThreeByteSpriteBanks ; @059FF
    pop cx ; @05A02
    add si,byte +0x28 ; @05A03
    loop loc_59FB ; @05A06
    mov cx,0x10 ; @05A08
loc_5A0B:
    push cx ; @05A0B
    mov dx,0x20c ; @05A0C
    call CopySpritePlanesAndAppendMask ; @05A0F
    pop cx ; @05A12
    add si,byte +0x30 ; @05A13
    loop loc_5A0B ; @05A16
    mov cx,0x20 ; @05A18
loc_5A1B:
    push cx ; @05A1B
    mov dx,0x30d ; @05A1C
    call CopySpritePlanesAndAppendMask ; @05A1F
    pop cx ; @05A22
    add si,byte +0x4e ; @05A23
    loop loc_5A1B ; @05A26
    mov cx,0x40 ; @05A28
loc_5A2B:
    push cx ; @05A2B
    mov dx,0x30a ; @05A2C
    call CopySpritePlanesAndAppendMask ; @05A2F
    pop cx ; @05A32
    add si,byte +0x3c ; @05A33
    loop loc_5A2B ; @05A36
    mov cx,0x30 ; @05A38
loc_5A3B:
    push cx ; @05A3B
    mov dx,0x30d ; @05A3C
    call CopySpritePlanesAndAppendMask ; @05A3F
    pop cx ; @05A42
    add si,byte +0x4e ; @05A43
    loop loc_5A3B ; @05A46
    mov cx,0x8 ; @05A48
loc_5A4B:
    push cx ; @05A4B
    mov dx,0x20a ; @05A4C
    call GenerateThreeByteSpriteBanks ; @05A4F
    pop cx ; @05A52
    add si,byte +0x28 ; @05A53
    loop loc_5A4B ; @05A56
    mov cx,0x10 ; @05A58
loc_5A5B:
    push cx ; @05A5B
    mov dx,0x310 ; @05A5C
    call CopySpritePlanesAndAppendMask ; @05A5F
    pop cx ; @05A62
    add si,byte +0x60 ; @05A63
    loop loc_5A5B ; @05A66
    mov cx,0x10 ; @05A68
loc_5A6B:
    push cx ; @05A6B
    mov dx,0x20a ; @05A6C
    call GenerateThreeByteSpriteBanks ; @05A6F
    pop cx ; @05A72
    add si,byte +0x28 ; @05A73
    loop loc_5A6B ; @05A76
    mov cx,0x8 ; @05A78
loc_5A7B:
    push cx ; @05A7B
    mov dx,0x20d ; @05A7C
    call CopySpritePlanesAndAppendMask ; @05A7F
    pop cx ; @05A82
    add si,byte +0x34 ; @05A83
    loop loc_5A7B ; @05A86
    mov cx,0xe ; @05A88
loc_5A8B:
    push cx ; @05A8B
    mov dx,0x40e ; @05A8C
    call CopySpritePlanesAndAppendMask ; @05A8F
    pop cx ; @05A92
    add si,byte +0x70 ; @05A93
    loop loc_5A8B ; @05A96
    mov cx,0x10 ; @05A98
loc_5A9B:
    push cx ; @05A9B
    mov dx,0x20a ; @05A9C
    call GenerateThreeByteSpriteBanks ; @05A9F
    pop cx ; @05AA2
    add si,byte +0x28 ; @05AA3
    loop loc_5A9B ; @05AA6
    mov cx,0x20 ; @05AA8
loc_5AAB:
    push cx ; @05AAB
    mov dx,0x20a ; @05AAC
    call GenerateThreeByteSpriteBanks ; @05AAF
    pop cx ; @05AB2
    add si,byte +0x28 ; @05AB3
    loop loc_5AAB ; @05AB6
    call GenerateFiveByteSpriteBanks ; @05AB8
    add si,0x180 ; @05ABB
    pop ds ; @05ABF
EntitySpriteBanksReturn:
    ret ; @05AC0
; Producer for the live GeneratedGraphicsBufferSegment; 58FE calls after decode.
; With DF=0 and intact disjoint RAM/save frames: eight10-row*3-byte banks
; start0000, four13-row banks0780, one22-row bank0C60, ten8-row*2-byte banks0E70.
; The8shiftpasses yield outputend1370 and sourceend0184. These are producer
; coordinates, not allocation bounds. 5D66 STOSW changes output direction withDF.
; Callers/unchecked consumers/initialization obligations: generated-graphics.md.
; PUSH DS precedes the two selector reads. Near calls/returns and the outer
; CX/DS saves are live SS memory; changed child return targets stop C handoff.
; DS restores from its actual save, ES stays selected, SS/BP unchanged.
sub_5AC1:
GenerateGraphicsMaskBanks:
    push ds ; @05AC1
    mov es,[GeneratedGraphicsBufferSegment-GameDataImage] ; @05AC2
    mov ds,[GraphicsResourceSegment-GameDataImage] ; @05AC6
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @05ACA
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @05ACC
    mov cx,0x8 ; @05ACE
loc_5AD1:
    push cx ; @05AD1
    mov cx,0xa ; @05AD2
    mov bl,0x1 ; @05AD5
    call GenerateWordMaskShifts ; @05AD7
    add si,byte +0x14 ; @05ADA
    pop cx ; @05ADD
    loop loc_5AD1 ; @05ADE
    mov cx,0x4 ; @05AE0
loc_5AE3:
    push cx ; @05AE3
    mov cx,0xd ; @05AE4
    mov bl,0x1 ; @05AE7
    call GenerateWordMaskShifts ; @05AE9
    add si,byte +0x1a ; @05AEC
    pop cx ; @05AEF
    loop loc_5AE3 ; @05AF0
    mov cx,0x16 ; @05AF2
    mov bl,0x1 ; @05AF5
    call GenerateWordMaskShifts ; @05AF7
    add si,byte +0x2c ; @05AFA
    mov cx,0xa ; @05AFD
loc_5B00:
    push cx ; @05B00
    mov cx,0x8 ; @05B01
    mov bl,0x1 ; @05B04
    call GenerateByteMaskShifts ; @05B06
    add si,byte +0x8 ; @05B09
    pop cx ; @05B0C
    loop loc_5B00 ; @05B0D
    pop ds ; @05B0F
    ret ; @05B10
