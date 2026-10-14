; Maintained image span 01916..01ED6; reconstruction module, not a historical linker claim.
; CONTRACT: DS:DX filename, ES:AX destination, CX maximum byte count.
; Open/read/close preserve live save frames; short reads are accepted.
; Failures transfer to the shared error printer with stage-specific message.
; Native domain and aliases: docs/resource-raw.md.
ReadRawResourceFile:
    push ds ; @01916
    push es ; @01917
    push ax ; @01918
    push es ; @01919
    push cx ; @0191A
    mov [LastResourceFilenameOffset-GameDataImage],dx ; @0191B
    mov ax,0x3d00 ; @0191F
    int 0x21 ; @01922
    jc loc_193A ; @01924
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01926
    mov ah,0x3f ; @01928
    pop cx ; @0192A
    pop ds ; @0192B
    pop dx ; @0192C
    int 0x21 ; @0192D
    jc loc_1940 ; @0192F
    mov ah,0x3e ; @01931
    int 0x21 ; @01933
    jc loc_1946 ; @01935
    pop es ; @01937
    pop ds ; @01938
    ret ; @01939
loc_193A:
    mov dx,DatFileErrorMessage-GameDataImage ; @0193A
    jmp short loc_1949 ; @0193D
; UNKNOWN: unresolved bytes
    db 0x90 ; @0193F
loc_1940:
    mov dx,ResourceReadErrorMessage-GameDataImage ; @01940
    jmp short loc_1949 ; @01943
; UNKNOWN: unresolved bytes
    db 0x90 ; @01945
loc_1946:
    mov dx,ResourceCloseErrorMessage-GameDataImage ; @01946
loc_1949:
DatFileErrorTransfer:
    push dx ; @01949
    mov dx,0x9a9 ; @0194A
    mov ds,dx ; @0194D
    call sub_0FF8 ; @0194F
    pop dx ; @01952
    mov ah,0x9 ; @01953
    int 0x21 ; @01955
    mov ah,0x2 ; @01957
    mov dl,0x20 ; @01959
    int 0x21 ; @0195B
    mov bx,[LastResourceFilenameOffset-GameDataImage] ; @0195D
loc_1961:
    mov dl,[bx] ; @01961
    db 0x22,0xd2 ; ENCODED: and dl,dl (NASM chooses a different encoding) ; @01963
    jz loc_196E ; @01965
    inc bx ; @01967
    mov ah,0x2 ; @01968
    int 0x21 ; @0196A
    jmp short loc_1961 ; @0196C
loc_196E:
    mov dl,0xd ; @0196E
    mov ah,0x2 ; @01970
    int 0x21 ; @01972
    mov dl,0xa ; @01974
    mov ah,0x2 ; @01976
    int 0x21 ; @01978
    jmp loc_04EA ; @0197A
; CONTRACT: incoming DS is the live main-data frame; no bounds checks on selector.
; Order byte minus1 wraps; bit0 selects an odd-table override. Group=(value>>4),
; section=(value>>1)&7. The decimal leaf changes SI; selected DAT sections overwrite
; LoadedLevelRecord. Odd overrides copy24 header bytes and32 footer bytes.
; Ground/VGAGR selectors come from the resulting record; special value0 uses
; two VGAGR sections, nonzero loads VGASPEC first section. Close carry is ignored.
; Native decimal/raw/file/cache/decoder composition: c/resource_select.c.
; Bounded live ES/DS/stack, DF and fatal contracts: docs/resource-select.md.
; DOS, 4B1C retry UI and 1949/04D0 fatal bodies remain explicit unported seams.
LoadSelectedLevelResources:
    mov bl,[LevelResourceSelectionByte-GameDataImage] ; @0197D
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @01981
    lea si,[LevelResourceOrderBytes-GameDataImage] ; @01983
    mov cl,[bx+si] ; @01987
    dec cl ; @01989
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0198B
    push cx ; @0198D
    shr cx,1 ; @0198E
    db 0x8b,0xc1 ; ENCODED: mov ax,cx (NASM chooses a different encoding) ; @01990
    shr ax,1 ; @01992
    shr ax,1 ; @01994
    shr ax,1 ; @01996
    and cx,byte +0x7 ; @01998
    lea si,[LevelResourceFilenameDigits-GameDataImage] ; @0199B
    push cx ; @0199F
    call WriteDecimalByteDigits ; @019A0
SelectionAfterDecimal:
    pop cx ; @019A3
    lea dx,[LevelResourceFilename-GameDataImage] ; @019A4
    push ds ; @019A8
    pop es ; @019A9
    lea di,[LoadedLevelRecord-GameDataImage] ; @019AA
    push cx ; @019AE
    mov cx,es ; @019AF
    db 0x8b,0xf7 ; ENCODED: mov si,di (NASM chooses a different encoding) ; @019B1
    call LoadDatResource ; @019B3
SelectionAfterFirstLevelSection:
    pop cx ; @019B6
    jcxz loc_19C4 ; @019B7
loc_19B9:
    push cx ; @019B9
    lea di,[LoadedLevelRecord-GameDataImage] ; @019BA
    call DecodeDatPreservingSegment ; @019BE
SelectionAfterNextLevelSection:
    pop cx ; @019C1
    loop loc_19B9 ; @019C2
loc_19C4:
    mov ah,0x3e ; @019C4
    int 0x21 ; @019C6
    pop ax ; @019C8
    test ax,0x1 ; @019C9
    jz loc_1A00 ; @019CC
    push ax ; @019CE
    push ds ; @019CF
    pop es ; @019D0
    lea dx,[OddLevelOverrideFilename-GameDataImage] ; @019D1
    lea ax,[OddLevelOverrideBuffer-GameDataImage] ; @019D5
    mov cx,0x1180 ; @019D9
    call ReadRawResourceFile ; @019DC
SelectionAfterOddOverrideRead:
    pop ax ; @019DF
    shr al,1 ; @019E0
    mov dh,0x38 ; @019E2
    mul dh ; @019E4
    lea di,[LoadedLevelRecord-GameDataImage] ; @019E6
    lea si,[OddLevelOverrideBuffer-GameDataImage] ; @019EA
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @019EE
    mov cx,0xc ; @019F0
    push ds ; @019F3
    pop es ; @019F4
    rep movsw ; @019F5
    lea di,[LoadedLevelFooterBytes-GameDataImage] ; @019F7
    mov cx,0x10 ; @019FB
    rep movsw ; @019FE
loc_1A00:
    mov al,[LevelGraphicsSetByte-GameDataImage] ; @01A00
    lea si,[GroundFilenameSelector-GameDataImage] ; @01A03
    add al,0x30 ; @01A07
    mov [si],al ; @01A09
    lea dx,[GroundResourceFilename-GameDataImage] ; @01A0B
    push ds ; @01A0F
    pop es ; @01A10
    lea ax,[GroundResourceBuffer-GameDataImage] ; @01A11
    mov cx,0x1000 ; @01A15
    call ReadRawResourceFile ; @01A18
SelectionAfterGroundRead:
    mov al,[LevelGraphicsSetByte-GameDataImage] ; @01A1B
    lea si,[GraphicsFilenameSelector-GameDataImage] ; @01A1E
    add al,0x30 ; @01A22
    mov [si],al ; @01A24
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @01A26
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01A29
    jz loc_1A30 ; @01A2B
    jmp short loc_1A5A ; @01A2D
; UNKNOWN: unresolved bytes
    db 0x90 ; @01A2F
loc_1A30:
    push ds ; @01A30
    lea dx,[GraphicsDatFilename-GameDataImage] ; @01A31
    mov es,[GraphicsResourceInputSegment-GameDataImage] ; @01A35
    mov di,0x10 ; @01A39
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01A3C
    mov cx,es ; @01A3E
    call LoadDatResource ; @01A40
SelectionAfterGraphicsLoad:
    pop ds ; @01A43
    push ds ; @01A44
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @01A45
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01A47
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01A49
    mov ds,[LevelGraphicsSegment-GameDataImage] ; @01A4D
    call DecodeDatPreservingSegment ; @01A51
SelectionAfterGraphicsDecode:
    pop ds ; @01A54
    mov ah,0x3e ; @01A55
    int 0x21 ; @01A57
    ret ; @01A59
loc_1A5A:
    lea si,[SpecialFilenameSelector-GameDataImage] ; @01A5A
    add al,0x2f ; @01A5E
    mov [si],al ; @01A60
    push ds ; @01A62
    lea dx,[SpecialResourceFilename-GameDataImage] ; @01A63
    mov es,[GraphicsResourceInputSegment-GameDataImage] ; @01A67
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01A6B
    mov di,0x10 ; @01A6D
    mov cx,es ; @01A70
    call LoadDatResource ; @01A72
SelectionAfterSpecialLoad:
    pop ds ; @01A75
    mov ah,0x3e ; @01A76
    int 0x21 ; @01A78
    ret ; @01A7A
; CONTRACT: loaded VGASPEC input atsegment[1FF4]:0010; main DS owns metadata.
; Prefix40 bytes ->four live metadata destinations; four RLE/strip pairs consume
; input from0038 and reuse heap[1FF0]:8000. Re-read pointers after saved-DS pushes.
; VGAGR reload follows drawing; final close exposes AX/flags without checking CF.
; Native bounded contract: docs/special-setup.md; VGA/IRQ/platform seams remain.
SetupSpecialGraphicsResource:
    push ds ; @01A7B
    mov cx,0x18 ; @01A7C
    lea di,[SpecialMetadata24-GameDataImage] ; @01A7F
    mov si,0x10 ; @01A83
    push ds ; @01A86
    pop es ; @01A87
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01A88
    push di ; @01A8C
    rep movsb ; @01A8D
    pop di ; @01A8F
    mov al,0x1f ; @01A90
    stosb ; @01A92
    stosb ; @01A93
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @01A94
    stosb ; @01A96
    mov cx,0x18 ; @01A97
    lea di,[SpecialMetadataDuplicateBase-GameDataImage] ; @01A9A
    add di,byte +0x18 ; @01A9E
    mov si,0x10 ; @01AA1
    rep movsb ; @01AA4
    mov cx,0x8 ; @01AA6
    lea di,[SpecialMetadata8Base-GameDataImage] ; @01AA9
    add di,byte +0x8 ; @01AAD
    rep movsb ; @01AB0
    mov cx,0x8 ; @01AB2
    lea di,[SpecialMetadataRemap8-GameDataImage] ; @01AB5
    push di ; @01AB9
    rep movsb ; @01ABA
    pop di ; @01ABC
    mov al,0x6 ; @01ABD
    stosb ; @01ABF
    pop ds ; @01AC0
    push ds ; @01AC1
    mov di,0x8000 ; @01AC2
    mov si,0x38 ; @01AC5
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01AC8
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01ACC
    call DecodeResourceRle ; @01AD0
SpecialAfterRle0:
    pop ds ; @01AD3
    push si ; @01AD4
    call BlitSpecialResourceStrip0 ; @01AD5
SpecialAfterStrip0:
    pop si ; @01AD8
    push ds ; @01AD9
    mov di,0x8000 ; @01ADA
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01ADD
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01AE1
    call DecodeResourceRle ; @01AE5
SpecialAfterRle1:
    pop ds ; @01AE8
    push si ; @01AE9
    call BlitSpecialResourceStrip1 ; @01AEA
SpecialAfterStrip1:
    pop si ; @01AED
    push ds ; @01AEE
    mov di,0x8000 ; @01AEF
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01AF2
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01AF6
    call DecodeResourceRle ; @01AFA
SpecialAfterRle2:
    pop ds ; @01AFD
    push si ; @01AFE
    call BlitSpecialResourceStrip2 ; @01AFF
SpecialAfterStrip2:
    pop si ; @01B02
    push ds ; @01B03
    mov di,0x8000 ; @01B04
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01B07
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01B0B
    call DecodeResourceRle ; @01B0F
SpecialAfterRle3:
    pop ds ; @01B12
    push si ; @01B13
    call BlitSpecialResourceStrip3 ; @01B14
SpecialAfterStrip3:
    pop si ; @01B17
    push ds ; @01B18
    lea dx,[GraphicsDatFilename-GameDataImage] ; @01B19
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01B1D
    mov di,0x10 ; @01B21
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01B24
    mov cx,es ; @01B26
    call LoadDatResource ; @01B28
SpecialAfterDatLoad:
    pop ds ; @01B2B
    push ds ; @01B2C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @01B2D
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01B2F
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01B31
    mov ds,[LevelGraphicsSegment-GameDataImage] ; @01B35
    call DecodeDatPreservingSegment ; @01B39
SpecialAfterDatDecode:
    pop ds ; @01B3C
    mov ah,0x3e ; @01B3D
    int 0x21 ; @01B3F
    ret ; @01B41
DecodeResourceRle:
    lodsb ; @01B42
    cmp al,0x80 ; @01B43
    jz loc_1B78 ; @01B45
    jc loc_1B62 ; @01B47
    neg al ; @01B49
    inc al ; @01B4B
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @01B4D
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @01B4F
    lodsb ; @01B51
loc_1B52:
    stosb ; @01B52
    db 0x23,0xff ; ENCODED: and di,di (NASM chooses a different encoding) ; @01B53
    jnz loc_1B5E ; @01B55
    mov ax,es ; @01B57
    add ax,0x1000 ; @01B59
    mov es,ax ; @01B5C
loc_1B5E:
    loop loc_1B52 ; @01B5E
    jmp short DecodeResourceRle ; @01B60
loc_1B62:
    inc al ; @01B62
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @01B64
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @01B66
loc_1B68:
    movsb ; @01B68
    db 0x23,0xff ; ENCODED: and di,di (NASM chooses a different encoding) ; @01B69
    jnz loc_1B74 ; @01B6B
    mov ax,es ; @01B6D
    add ax,0x1000 ; @01B6F
    mov es,ax ; @01B72
loc_1B74:
    loop loc_1B68 ; @01B74
    jmp short DecodeResourceRle ; @01B76
loc_1B78:
    ret ; @01B78
; CONTRACT: DS:DX filename, CX decoder source segment, ES:DI output, SI source offset.
; Connect check/open/decode; ignored open carry and both fatal frames are original.
; Shared tail DecodeDatPreservingSegment keeps DS through a live stack restore.
; Native/provider domain: docs/dat-load.md.
LoadDatResource:
    push cx ; @01B79
    call CheckDatFile ; @01B7A
DatAfterResourceCheck:
    pop cx ; @01B7D
    jc loc_1B98 ; @01B7E
    cmp byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @01B80
    jnz loc_1B98 ; @01B85
    call OpenDatFile ; @01B87
DatAfterResourceOpen:
    cmp byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @01B8A
    jnz loc_1B98 ; @01B8F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01B91
    mov ds,cx ; @01B93
    jmp short DecodeDatPreservingSegment ; @01B95
; UNKNOWN: unresolved bytes
    db 0x90 ; @01B97
loc_1B98:
    push dx ; @01B98
    push cx ; @01B99
    push es ; @01B9A
    push ds ; @01B9B
    push di ; @01B9C
    push si ; @01B9D
    call sub_4B1C ; @01B9E
DatAfterResourceRetry:
    pop si ; @01BA1
    pop di ; @01BA2
    pop ds ; @01BA3
    pop es ; @01BA4
    pop cx ; @01BA5
    pop dx ; @01BA6
    jmp short LoadDatResource ; @01BA7
DecodeDatPreservingSegment:
    push ds ; @01BA9
    call DecodeDatSection ; @01BAA
sub_1BAD:
    pop ds ; @01BAD
    ret ; @01BAE
; CONTRACT: BX handle, DS:SI source buffer, ES:DI output; incoming ES may change
; inside ReadDatBytes. Sizes use low16-bit header words, with original wrap.
; Header bit count0 is valid:seed DL joins checksum, first read refills backwards.
; Short reads/malformed lengths are unchecked; normal exit clears DF, error exits
; preserve the live frame at04D0. Native bounded contract: docs/dat-section.md.
DecodeDatSection:
    push bx ; @01BAF
    std ; @01BB0
    push bx ; @01BB1
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @01BB2
    mov cx,0xa ; @01BB4
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @01BB7
    call ReadDatBytes ; @01BB9
DatAfterHeaderRead:
    jnc loc_1BC1 ; @01BBC
    jmp loc_1C7A ; @01BBE
loc_1BC1:
    mov ch,[si] ; @01BC1
    inc ch ; @01BC3
    mov dh,[si+0x1] ; @01BC5
    mov ah,[si+0x2] ; @01BC8
    mov al,[si+0x3] ; @01BCB
    mov bh,[si+0x4] ; @01BCE
    mov bl,[si+0x5] ; @01BD1
    db 0x03,0xfb ; ENCODED: add di,bx (NASM chooses a different encoding) ; @01BD4
    pop ax ; @01BD6
    push cx ; @01BD7
    push dx ; @01BD8
    mov ch,[si+0x8] ; @01BD9
    mov cl,[si+0x9] ; @01BDC
    sub cx,byte +0xa ; @01BDF
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @01BE2
    db 0x03,0xf1 ; ENCODED: add si,cx (NASM chooses a different encoding) ; @01BE4
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01BE6
    call ReadDatBytes ; @01BE8
DatAfterPayloadRead:
    jnc loc_1BF0 ; @01BEB
    jmp loc_1C7A ; @01BED
loc_1BF0:
    pop dx ; @01BF0
    pop cx ; @01BF1
    dec si ; @01BF2
    mov dl,[si] ; @01BF3
    db 0x32,0xf2 ; ENCODED: xor dh,dl (NASM chooses a different encoding) ; @01BF5
sub_1BF7:
    mov cl,0x1 ; @01BF7
    call ReadReverseBits ; @01BF9
DatAfterTokenBit:
    cmp ax,0x1 ; @01BFC
    jnz sub_1C47 ; @01BFF
sub_1C01:
    mov cl,0x2 ; @01C01
    call ReadReverseBits ; @01C03
DatAfterKindBits:
    cmp ax,0x2 ; @01C06
    jnc sub_1C1B ; @01C09
sub_1C0B:
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01C0B
    add bx,byte +0x2 ; @01C0D
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @01C10
    add cl,0x9 ; @01C12
    call ReadAndCopyReverseMatch ; @01C15
DatAfterShortMatch:
    jmp short sub_1C6F ; @01C18
; UNKNOWN: unresolved bytes
    db 0x90 ; @01C1A
sub_1C1B:
    cmp ax,0x3 ; @01C1B
    jnz sub_1C38 ; @01C1E
sub_1C20:
    mov cl,0x8 ; @01C20
    call ReadReverseBits ; @01C22
DatAfterLongLiteralLength:
    add ax,0x9 ; @01C25
loc_1C28:
    push ax ; @01C28
    mov cl,0x8 ; @01C29
    call ReadReverseBits ; @01C2B
DatAfterLongLiteralByte:
    call WriteReverseLiteral ; @01C2E
DatAfterLongLiteralWrite:
    pop ax ; @01C31
    dec ax ; @01C32
    jnz loc_1C28 ; @01C33
sub_1C35:
    jmp short sub_1C6F ; @01C35
; UNKNOWN: unresolved bytes
    db 0x90 ; @01C37
sub_1C38:
    mov cl,0x8 ; @01C38
    call ReadReverseBits ; @01C3A
DatAfterMatchLength:
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01C3D
    mov cl,0xc ; @01C3F
    call ReadAndCopyReverseMatch ; @01C41
DatAfterVariableMatch:
    jmp short sub_1C6F ; @01C44
; UNKNOWN: unresolved bytes
    db 0x90 ; @01C46
sub_1C47:
    mov cl,0x1 ; @01C47
    call ReadReverseBits ; @01C49
DatAfterSecondTokenBit:
    cmp ax,0x1 ; @01C4C
    jnz sub_1C5C ; @01C4F
sub_1C51:
    mov bx,0x1 ; @01C51
    mov cl,0x8 ; @01C54
    call ReadAndCopyReverseMatch ; @01C56
sub_1C59:
    jmp short sub_1C6F ; @01C59
; UNKNOWN: unresolved bytes
    db 0x90 ; @01C5B
sub_1C5C:
    mov cl,0x3 ; @01C5C
    call ReadReverseBits ; @01C5E
DatAfterShortLiteralLength:
    inc ax ; @01C61
loc_1C62:
    push ax ; @01C62
    mov cl,0x8 ; @01C63
    call ReadReverseBits ; @01C65
DatAfterShortLiteralByte:
    call WriteReverseLiteral ; @01C68
DatAfterShortLiteralWrite:
    pop ax ; @01C6B
    dec ax ; @01C6C
    jnz loc_1C62 ; @01C6D
sub_1C6F:
    db 0x3b,0xfd ; ENCODED: cmp di,bp (NASM chooses a different encoding) ; @01C6F
    jna sub_1C75 ; @01C71
sub_1C73:
    jmp short sub_1BF7 ; @01C73
sub_1C75:
    db 0x22,0xf6 ; ENCODED: and dh,dh (NASM chooses a different encoding) ; @01C75
    pop bx ; @01C77
    cld ; @01C78
    ret ; @01C79
loc_1C7A:
DatReadFailure:
    mov ax,0x9a9 ; @01C7A
    mov ds,ax ; @01C7D
    jmp loc_04D0 ; @01C7F
WriteReverseLiteral:
    dec di ; @01C82
    mov [es:di],al ; @01C83
    ret ; @01C86
ReadAndCopyReverseMatch:
    call ReadReverseBits ; @01C87
CopyReverseMatch:
    inc bx ; @01C8A
    push si ; @01C8B
    push ds ; @01C8C
    push cx ; @01C8D
    push es ; @01C8E
    pop ds ; @01C8F
    db 0x8b,0xcb ; ENCODED: mov cx,bx (NASM chooses a different encoding) ; @01C90
loc_1C92:
    dec di ; @01C92
    db 0x8b,0xf7 ; ENCODED: mov si,di (NASM chooses a different encoding) ; @01C93
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @01C95
    inc si ; @01C97
    mov bl,[si] ; @01C98
    mov [es:di],bl ; @01C9A
    loop loc_1C92 ; @01C9D
sub_1C9F:
    pop cx ; @01C9F
    pop ds ; @01CA0
    pop si ; @01CA1
    ret ; @01CA2
ReadReverseBits:
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @01CA3
loc_1CA5:
    dec ch ; @01CA5
    jnz loc_1CB0 ; @01CA7
    dec si ; @01CA9
    mov dl,[si] ; @01CAA
    db 0x32,0xf2 ; ENCODED: xor dh,dl (NASM chooses a different encoding) ; @01CAC
    mov ch,0x8 ; @01CAE
loc_1CB0:
    shr dl,1 ; @01CB0
    rcl ax,1 ; @01CB2
    dec cl ; @01CB4
    jnz loc_1CA5 ; @01CB6
    ret ; @01CB8
OpenDatFile:
    push ds ; @01CB9
    push dx ; @01CBA
    push es ; @01CBB
    push di ; @01CBC
    push cx ; @01CBD
    push si ; @01CBE
    cmp byte [DatCacheEnabled-GameDataImage],0xff ; @01CBF
    jnz loc_1CCD ; @01CC4
    cmp byte [DatCacheSelected-GameDataImage],0xff ; @01CC6
    jz loc_1CD2 ; @01CCB
loc_1CCD:
    mov ax,0x3d00 ; @01CCD
    int 0x21 ; @01CD0
loc_1CD2:
    pop si ; @01CD2
    pop cx ; @01CD3
    pop di ; @01CD4
    pop es ; @01CD5
    pop dx ; @01CD6
    pop ds ; @01CD7
    ret ; @01CD8
CheckDatFile:
    push ds ; @01CD9
    push dx ; @01CDA
    push es ; @01CDB
    push di ; @01CDC
    push cx ; @01CDD
    push si ; @01CDE
    cmp byte [DatCacheEnabled-GameDataImage],0xff ; @01CDF
    jnz loc_1CEE ; @01CE4
    call PrepareDatCacheName ; @01CE6
DatAfterNamePreparation:
    call SelectCachedDatFile ; @01CE9
DatAfterCacheSelection:
    jnc loc_1CFE ; @01CEC
loc_1CEE:
    mov ax,0x4300 ; @01CEE
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @01CF1
    int 0x21 ; @01CF3
    jc loc_1D05 ; @01CF5
    cmp byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @01CF7
    jnz loc_1D05 ; @01CFC
loc_1CFE:
    pop si ; @01CFE
    pop cx ; @01CFF
    pop di ; @01D00
    pop es ; @01D01
    pop dx ; @01D02
    pop ds ; @01D03
    ret ; @01D04
loc_1D05:
    push dx ; @01D05
    push cx ; @01D06
    push es ; @01D07
    push ds ; @01D08
    push di ; @01D09
    push si ; @01D0A
    mov ax,0x9a9 ; @01D0B
    mov ds,ax ; @01D0E
    cmp byte [DatRetryEnabled-GameDataImage],0x0 ; @01D10
    jz loc_1D22 ; @01D15
    call sub_4B1C ; @01D17
DatAfterFileRetry:
    pop si ; @01D1A
    pop di ; @01D1B
    pop ds ; @01D1C
    pop es ; @01D1D
    pop cx ; @01D1E
    pop dx ; @01D1F
    jmp short loc_1CEE ; @01D20
loc_1D22:
    pop si ; @01D22
    pop di ; @01D23
    pop ds ; @01D24
    pop es ; @01D25
    pop cx ; @01D26
    pop dx ; @01D27
    mov dx,DatFileErrorMessage-GameDataImage ; @01D28
    jmp loc_1949 ; @01D2B
ReadDatBytes:
    push di ; @01D2E
    push si ; @01D2F
    push ds ; @01D30
    push bx ; @01D31
    push cx ; @01D32
    push dx ; @01D33
    cld ; @01D34
    mov ax,0x9a9 ; @01D35
    mov ds,ax ; @01D38
    cmp byte [DatCacheEnabled-GameDataImage],0xff ; @01D3A
    jz loc_1D44 ; @01D3F
    jmp loc_1E11 ; @01D41
loc_1D44:
    cmp byte [DatCacheSelected-GameDataImage],0xff ; @01D44
    jnz loc_1D4E ; @01D49
    jmp loc_1DF1 ; @01D4B
loc_1D4E:
    mov ah,0x23 ; @01D4E
    lea dx,[DatCacheFcb-GameDataImage] ; @01D50
    mov word [0x1fa3],0x1 ; @01D54
    int 0x21 ; @01D5A
    mov dx,[0x1fb6] ; @01D5C
    mov ax,[0x1fb8] ; @01D60
    push dx ; @01D63
    shr ax,1 ; @01D64
    rcr dx,1 ; @01D66
    shr ax,1 ; @01D68
    rcr dx,1 ; @01D6A
    shr ax,1 ; @01D6C
    rcr dx,1 ; @01D6E
    shr ax,1 ; @01D70
    rcr dx,1 ; @01D72
    pop ax ; @01D74
    and ax,0xf ; @01D75
    jnz loc_1D7D ; @01D78
    jmp short loc_1D7E ; @01D7A
; UNKNOWN: unresolved bytes
    db 0x90 ; @01D7C
loc_1D7D:
    inc dx ; @01D7D
loc_1D7E:
    cmp dx,[DatCacheRemainingParagraphs-GameDataImage] ; @01D7E
    jna loc_1D87 ; @01D82
    jmp loc_1E11 ; @01D84
loc_1D87:
    inc byte [DatCacheRecordCount-GameDataImage] ; @01D87
    sub [DatCacheRemainingParagraphs-GameDataImage],dx ; @01D8B
    push ds ; @01D8F
    mov cx,0xffff ; @01D90
    mov dx,[DatCacheFreeOffset-GameDataImage] ; @01D93
    mov ax,[DatCacheFreeSegment-GameDataImage] ; @01D97
    mov [DatCacheRecordOffset-GameDataImage],dx ; @01D9A
    mov [DatCacheRecordSegment-GameDataImage],ax ; @01D9E
    mov byte [DatCacheSelected-GameDataImage],0xff ; @01DA1
    add dx,byte +0xd ; @01DA6
    mov [DatCacheReadOffset-GameDataImage],dx ; @01DA9
    mov [DatCacheReadSegment-GameDataImage],ax ; @01DAD
    push ax ; @01DB0
    push dx ; @01DB1
    mov ds,ax ; @01DB2
    mov ah,0x3f ; @01DB4
    int 0x21 ; @01DB6
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @01DB8
    pop dx ; @01DBA
    pop ax ; @01DBB
    pop ds ; @01DBC
    db 0x03,0xd1 ; ENCODED: add dx,cx (NASM chooses a different encoding) ; @01DBD
    push dx ; @01DBF
    shr dx,1 ; @01DC0
    shr dx,1 ; @01DC2
    shr dx,1 ; @01DC4
    shr dx,1 ; @01DC6
    db 0x03,0xc2 ; ENCODED: add ax,dx (NASM chooses a different encoding) ; @01DC8
    pop dx ; @01DCA
    and dx,byte +0xf ; @01DCB
    mov [DatCacheFreeOffset-GameDataImage],dx ; @01DCE
    mov [DatCacheFreeSegment-GameDataImage],ax ; @01DD2
    mov di,[DatCacheRecordOffset-GameDataImage] ; @01DD5
    mov es,[DatCacheRecordSegment-GameDataImage] ; @01DD9
    mov dx,[0x1fb8] ; @01DDD
    mov [es:di+0xb],cx ; @01DE1
    lea si,[0x1f96] ; @01DE5
    add di,byte +0x0 ; @01DE9
    mov cx,0xb ; @01DEC
    rep movsb ; @01DEF
loc_1DF1:
    pop di ; @01DF1
    pop cx ; @01DF2
    pop bx ; @01DF3
    pop es ; @01DF4
    push es ; @01DF5
    push di ; @01DF6
    push ds ; @01DF7
    mov si,[DatCacheReadOffset-GameDataImage] ; @01DF8
    mov ds,[DatCacheReadSegment-GameDataImage] ; @01DFC
    rep movsb ; @01E00
    mov ax,ds ; @01E02
    pop ds ; @01E04
    mov [DatCacheReadSegment-GameDataImage],ax ; @01E05
    mov [DatCacheReadOffset-GameDataImage],si ; @01E08
    pop dx ; @01E0C
    pop ds ; @01E0D
    pop si ; @01E0E
    pop di ; @01E0F
    ret ; @01E10
loc_1E11:
    pop dx ; @01E11
    pop cx ; @01E12
    pop bx ; @01E13
    pop ds ; @01E14
    mov ah,0x3f ; @01E15
    int 0x21 ; @01E17
    pop si ; @01E19
    pop di ; @01E1A
    ret ; @01E1B
PrepareDatCacheName:
    push dx ; @01E1C
    push es ; @01E1D
    push ax ; @01E1E
    push cx ; @01E1F
    push ds ; @01E20
    pop es ; @01E21
    db 0x8b,0xf2 ; ENCODED: mov si,dx (NASM chooses a different encoding) ; @01E22
    mov cx,0x8 ; @01E24
    lea di,[0x1f96] ; @01E27
loc_1E2B:
    lodsb ; @01E2B
    cmp al,0x2e ; @01E2C
    jz loc_1E58 ; @01E2E
    stosb ; @01E30
    loop loc_1E2B ; @01E31
loc_1E33:
    lodsb ; @01E33
    cmp al,0x2e ; @01E34
    jnz loc_1E33 ; @01E36
loc_1E38:
    mov cx,0x3 ; @01E38
    lea di,[0x1f9e] ; @01E3B
loc_1E3F:
    lodsb ; @01E3F
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01E40
    jz loc_1E49 ; @01E42
    stosb ; @01E44
    loop loc_1E3F ; @01E45
    jmp short loc_1E53 ; @01E47
loc_1E49:
    mov ax,0x2 ; @01E49
    db 0x2b,0xc1 ; ENCODED: sub ax,cx (NASM chooses a different encoding) ; @01E4C
    xchg ax,cx ; @01E4E
    mov al,0x20 ; @01E4F
    rep stosb ; @01E51
loc_1E53:
    pop cx ; @01E53
    pop ax ; @01E54
    pop es ; @01E55
    pop dx ; @01E56
    ret ; @01E57
loc_1E58:
    mov ax,0x7 ; @01E58
    db 0x2b,0xc1 ; ENCODED: sub ax,cx (NASM chooses a different encoding) ; @01E5B
    xchg ax,cx ; @01E5D
    mov al,0x20 ; @01E5E
    rep stosb ; @01E60
    jmp short loc_1E38 ; @01E62
SelectCachedDatFile:
    push ds ; @01E64
    mov cl,[DatCacheRecordCount-GameDataImage] ; @01E65
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @01E69
    jz loc_1EA7 ; @01E6B
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @01E6D
    push ds ; @01E6F
    pop es ; @01E70
    mov ds,[DatCacheBaseSegment-GameDataImage] ; @01E71
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01E75
    lea di,[0x1f96] ; @01E77
loc_1E7B:
    push cx ; @01E7B
    push ds ; @01E7C
    push si ; @01E7D
    push di ; @01E7E
    mov cx,0xb ; @01E7F
    repe cmpsb ; @01E82
    pop di ; @01E84
    pop si ; @01E85
    db 0x23,0xc9 ; ENCODED: and cx,cx (NASM chooses a different encoding) ; @01E86
    jz loc_1EAF ; @01E88
    pop ds ; @01E8A
    add si,[si+0xb] ; @01E8B
    add si,byte +0xd ; @01E8E
    db 0x8b,0xc6 ; ENCODED: mov ax,si (NASM chooses a different encoding) ; @01E91
    shr ax,1 ; @01E93
    shr ax,1 ; @01E95
    shr ax,1 ; @01E97
    shr ax,1 ; @01E99
    mov cx,ds ; @01E9B
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @01E9D
    mov ds,cx ; @01E9F
    and si,byte +0xf ; @01EA1
    pop cx ; @01EA4
    loop loc_1E7B ; @01EA5
loc_1EA7:
    pop ds ; @01EA7
    mov byte [DatCacheSelected-GameDataImage],0x0 ; @01EA8
    stc ; @01EAD
    ret ; @01EAE
loc_1EAF:
    mov ax,ds ; @01EAF
    pop ds ; @01EB1
    pop cx ; @01EB2
    mov cx,0x9a9 ; @01EB3
    mov ds,cx ; @01EB6
    mov [DatCacheRecordOffset-GameDataImage],si ; @01EB8
    mov [DatCacheRecordSegment-GameDataImage],ax ; @01EBC
    add si,byte +0xd ; @01EBF
    mov [DatCacheReadOffset-GameDataImage],si ; @01EC2
    mov [DatCacheReadSegment-GameDataImage],ax ; @01EC6
    mov byte [DatCacheSelected-GameDataImage],0xff ; @01EC9
    pop ds ; @01ECE
    clc ; @01ECF
    ret ; @01ED0
DisableDatCache:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @01ED1
    mov [DatCacheEnabled-GameDataImage],al ; @01ED3
    ret ; @01ED6
