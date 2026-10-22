; Palette channel arithmetic and sequential packed/RGB rows, original563E..5725.
; Native contracts: docs/palette-channels.md and docs/palette-rows.md.
; Explicit INC cursors ignore DF; zeroCL loops65536 times. Stack saves/RET stay live.
; Packed BP and RGB BL markers deliberately produce different final sign flags.
; ROW OWNERSHIP: nominal selectors in palette_frontends.asm use DS2638 and
; DS2668 as current/source rows, updating toward black/menu/ground/UI targets.
; Packed width is CL bytes (nominal10 or08);RGB width is3*CL (30 or18).
; 2650 is an interior alias of RGB2638, not a third separately initialized row.
; These source/target loads BOTH use DS (not ES despite prefix PUSH DS/POP ES).
; All original byte stores and later reads remain live under overlap: neither
; row is snapshotted and target data can be changed by an earlier source write.
; READINESS: CONDITIONAL for intact instructions/live segmented memory and
; declared port/IRQ services; nominal stored extents do not bound raw entry,
; source-selector corruption, zeroCL, cache/record/resource or stack aliases.
StepPackedPaletteRow:
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @0563E
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @05640
loc_5642:
    push cx ; @05642
    mov dl,[si] ; @05643
    mov cl,[di] ; @05645
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @05647
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05649
    call StepHighPaletteChannel ; @0564B
PackedPaletteRowAfterHigh564E:
    db 0x8a,0xf0 ; ENCODED: mov dh,al (NASM chooses a different encoding) ; @0564E
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05650
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @05652
    call StepMiddlePaletteChannel ; @05654
PackedPaletteRowAfterMiddle5657:
    db 0x0a,0xf0 ; ENCODED: or dh,al (NASM chooses a different encoding) ; @05657
    db 0x8a,0xc2 ; ENCODED: mov al,dl (NASM chooses a different encoding) ; @05659
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @0565B
    call StepLowPaletteChannel ; @0565D
PackedPaletteRowAfterLow5660:
    db 0x0a,0xf0 ; ENCODED: or dh,al (NASM chooses a different encoding) ; @05660
    mov [si],dh ; @05662
    pop cx ; @05664
    inc si ; @05665
    inc di ; @05666
    loop loc_5642 ; @05667
    db 0x23,0xed ; ENCODED: and bp,bp (NASM chooses a different encoding) ; @05669
PackedPaletteRowReturn566B:
    ret ; @0566B
; Packed channel wrappers retain decoded AH/BH, shifted BL, and live near CALL frames.
; The shared helper preserves BP on equality, otherwise writes BP=00FF.
; Contracts and five-entry byte-pair gate: docs/palette-channels.md.
StepHighPaletteChannel:
    shr al,1 ; @0566C
    shr bl,1 ; @0566E
    shr al,1 ; @05670
    shr bl,1 ; @05672
    and al,0x9 ; @05674
    and bl,0x9 ; @05676
    call StepPackedPaletteChannel ; @05679
PaletteHighAfterStep567C:
    shl al,1 ; @0567C
    shl bl,1 ; @0567E
    shl al,1 ; @05680
    shl bl,1 ; @05682
PaletteHighReturn5684:
    ret ; @05684
StepMiddlePaletteChannel:
    shr al,1 ; @05685
    shr bl,1 ; @05687
    and al,0x9 ; @05689
    and bl,0x9 ; @0568B
    call StepPackedPaletteChannel ; @0568E
PaletteMiddleAfterStep5691:
    shl al,1 ; @05691
    shl bl,1 ; @05693
PaletteMiddleReturn5695:
    ret ; @05695
StepLowPaletteChannel:
    and al,0x9 ; @05696
    and bl,0x9 ; @05698
; Bits3/0 encode a two-bit channel: decode, unsigned single step, repack AL.
; BL stays decoded; BH and AH are original working-byte side effects.
StepPackedPaletteChannel:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @0569B
    shr al,1 ; @0569D
    shr al,1 ; @0569F
    shr al,1 ; @056A1
    shl ah,1 ; @056A3
    and ah,0x2 ; @056A5
    and al,0x1 ; @056A8
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @056AA
    db 0x8a,0xfb ; ENCODED: mov bh,bl (NASM chooses a different encoding) ; @056AC
    shr bl,1 ; @056AE
    shr bl,1 ; @056B0
    shr bl,1 ; @056B2
    shl bh,1 ; @056B4
    and bh,0x2 ; @056B6
    and bl,0x1 ; @056B9
    db 0x0a,0xdf ; ENCODED: or bl,bh (NASM chooses a different encoding) ; @056BC
    db 0x3a,0xc3 ; ENCODED: cmp al,bl (NASM chooses a different encoding) ; @056BE
    jz loc_56D0 ; @056C0
    ja loc_56CB ; @056C2
    inc al ; @056C4
    mov bp,0xff ; @056C6
    jmp short loc_56D0 ; @056C9
loc_56CB:
    dec al ; @056CB
    mov bp,0xff ; @056CD
loc_56D0:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @056D0
    shl al,1 ; @056D2
    shl al,1 ; @056D4
    shl al,1 ; @056D6
    shr ah,1 ; @056D8
    and al,0x8 ; @056DA
    and ah,0x1 ; @056DC
    db 0x0a,0xc4 ; ENCODED: or al,ah (NASM chooses a different encoding) ; @056DF
PalettePackedReturn56E1:
    ret ; @056E1
StepRgbPaletteRow:
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @056E2
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @056E4
loc_56E6:
    mov al,[si] ; @056E6
    mov ah,[di] ; @056E8
    call StepSignedRgbChannel ; @056EA
RgbPaletteRowAfterFirst56ED:
    mov [si],al ; @056ED
    inc si ; @056EF
    inc di ; @056F0
    mov al,[si] ; @056F1
    mov ah,[di] ; @056F3
    call StepSignedRgbChannel ; @056F5
RgbPaletteRowAfterSecond56F8:
    mov [si],al ; @056F8
    inc si ; @056FA
    inc di ; @056FB
    mov al,[si] ; @056FC
    mov ah,[di] ; @056FE
    call StepSignedRgbChannel ; @05700
RgbPaletteRowAfterThird5703:
    mov [si],al ; @05703
    inc si ; @05705
    inc di ; @05706
    loop loc_56E6 ; @05707
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @05709
RgbPaletteRowReturn570B:
    ret ; @0570B
; Signed JG is intentional for every byte pattern. Step at most twice toward AH;
; initial inequality sets BL=FF even when the first step reaches the target.
; Last CMP/INC/DEC flags and the two distinct RET sites remain observable.
StepSignedRgbChannel:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @0570C
    jz PaletteRgbReturn571E ; @0570E
    jg loc_571F ; @05710
    inc al ; @05712
loc_5714:
    mov bl,0xff ; @05714
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @05716
    jz PaletteRgbReturn571E ; @05718
    jg loc_5723 ; @0571A
    inc al ; @0571C
PaletteRgbReturn571E:
    ret ; @0571E
loc_571F:
    dec al ; @0571F
    jmp short loc_5714 ; @05721
loc_5723:
    dec al ; @05723
PaletteRgbDecrementReturn5725:
    ret ; @05725
