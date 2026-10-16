; Maintained3AC8..3CDD status display, preserving UNKNOWN3B08.
times -(($-$$) != 0x3ac8) db 0 ; module start assertion
; CONTRACT: two minimap CALLs fall through into live status rendering at3ACE.
; The100*completion byte DIV uses live CL; divisor0 skips DIV, overflow is#DE.
; Non100 formatting retains the leading209C byte. All child frames are actual SS.
; Counts use live value/snapshot/refresh triples; zero forces drawing, counter2
; acknowledges through FF then INC0. Counters and selectors also gate input.
; Every child-returned register/segment/flag flows into subsequent live reads.
; Scoped native suffix/full-entry gates retain processor and changed-return seams.
UpdateStatusDisplay:
    call UpdateMinimapColumn ; @03AC8
StatusDisplayAfterMinimapColumn:
    call DrawMinimapViewport ; @03ACB
StatusDisplayAfterMinimapViewport:
    mov al,[EntityCompletionCounter-GameDataImage] ; @03ACE
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03AD1
    shl ax,1 ; @03AD3
    shl ax,1 ; @03AD5
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @03AD7
    shl ax,1 ; @03AD9
    shl ax,1 ; @03ADB
    shl ax,1 ; @03ADD
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @03ADF
    shl ax,1 ; @03AE1
    db 0x03,0xc1 ; ENCODED: add ax,cx (NASM chooses a different encoding) ; @03AE3
    mov cl,[LevelCreationLimit-GameDataImage] ; @03AE5
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @03AE9
    jz loc_3AEF ; @03AEB
StatusDisplayDivide:
    div cl ; @03AED
loc_3AEF:
    mov si,StatusPercentDigits-GameDataImage+1 ; @03AEF
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03AF2
    mov [StatusCompletionDisplayValue-GameDataImage],al ; @03AF4
    cmp al,0x64 ; @03AF7
    jnz loc_3B09 ; @03AF9
    mov byte [si-0x1],0x31 ; @03AFB
    mov byte [si],0x30 ; @03AFF
    mov byte [si+0x1],0x30 ; @03B02
    jmp short loc_3B21 ; @03B06
; UNKNOWN: unresolved bytes
    db 0x90 ; @03B08
loc_3B09:
    inc ah ; @03B09
    sub al,0xa ; @03B0B
    jnc loc_3B09 ; @03B0D
    add al,0x3a ; @03B0F
    dec ah ; @03B11
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B13
    jnz loc_3B19 ; @03B15
    mov ah,0xf0 ; @03B17
loc_3B19:
    add ah,0x30 ; @03B19
    mov [si],ah ; @03B1C
    mov [si+0x1],al ; @03B1E
loc_3B21:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @03B21
    mov si,0x2083 ; @03B23
    call DrawStatusText ; @03B26
StatusDisplayAfterText:
    mov ah,[EntityActionSelector-GameDataImage] ; @03B29
    cmp [StatusIconDisplaySnapshot-GameDataImage],ah ; @03B2D
    jz loc_3B57 ; @03B31
    mov al,[EntityActionSelector-GameDataImage] ; @03B33
    call DrawStatusIconOutline ; @03B36
StatusDisplayAfterIconOutline:
    mov al,[StatusIconDisplaySnapshot-GameDataImage] ; @03B39
    call RestoreStatusIcon ; @03B3C
StatusDisplayAfterIconRestore:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x2 ; @03B3F
    jnz loc_3B53 ; @03B44
    mov ah,[EntityActionSelector-GameDataImage] ; @03B46
    mov [StatusIconDisplaySnapshot-GameDataImage],ah ; @03B4A
    mov byte [StatusIconRefreshCounter-GameDataImage],0xff ; @03B4E
loc_3B53:
    inc byte [StatusIconRefreshCounter-GameDataImage] ; @03B53
loc_3B57:
    mov ah,[LevelReleaseSettingMinimum-GameDataImage] ; @03B57
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B5B
    jz loc_3B65 ; @03B5D
    cmp [LevelReleaseMinimumDisplaySnapshot-GameDataImage],ah ; @03B5F
    jz loc_3B7E ; @03B63
loc_3B65:
    cmp byte [LevelReleaseMinimumRefreshCounter-GameDataImage],0x2 ; @03B65
    jnz loc_3B75 ; @03B6A
    mov [LevelReleaseMinimumDisplaySnapshot-GameDataImage],ah ; @03B6C
    mov byte [LevelReleaseMinimumRefreshCounter-GameDataImage],0xff ; @03B70
loc_3B75:
    inc byte [LevelReleaseMinimumRefreshCounter-GameDataImage] ; @03B75
    mov al,0x0 ; @03B79
    call DrawStatusCount ; @03B7B
loc_3B7E:
    mov ah,[LevelReleaseSetting-GameDataImage] ; @03B7E
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03B82
    jz loc_3B8C ; @03B84
    cmp [LevelReleaseSettingDisplaySnapshot-GameDataImage],ah ; @03B86
    jz loc_3BA5 ; @03B8A
loc_3B8C:
    cmp byte [LevelReleaseSettingRefreshCounter-GameDataImage],0x2 ; @03B8C
    jnz loc_3B9C ; @03B91
    mov [LevelReleaseSettingDisplaySnapshot-GameDataImage],ah ; @03B93
    mov byte [LevelReleaseSettingRefreshCounter-GameDataImage],0xff ; @03B97
loc_3B9C:
    inc byte [LevelReleaseSettingRefreshCounter-GameDataImage] ; @03B9C
    mov al,0x1 ; @03BA0
    call DrawStatusCount ; @03BA2
loc_3BA5:
    mov ah,[LevelActionCount2-GameDataImage] ; @03BA5
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BA9
    jz loc_3BB3 ; @03BAB
    cmp [LevelActionCountDisplaySnapshot2-GameDataImage],ah ; @03BAD
    jz loc_3BCC ; @03BB1
loc_3BB3:
    cmp byte [LevelActionCountRefreshCounter2-GameDataImage],0x2 ; @03BB3
    jnz loc_3BC3 ; @03BB8
    mov [LevelActionCountDisplaySnapshot2-GameDataImage],ah ; @03BBA
    mov byte [LevelActionCountRefreshCounter2-GameDataImage],0xff ; @03BBE
loc_3BC3:
    inc byte [LevelActionCountRefreshCounter2-GameDataImage] ; @03BC3
    mov al,0x4 ; @03BC7
    call DrawStatusCount ; @03BC9
loc_3BCC:
    mov ah,[LevelActionCount7-GameDataImage] ; @03BCC
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BD0
    jz loc_3BDA ; @03BD2
    cmp [LevelActionCountDisplaySnapshot7-GameDataImage],ah ; @03BD4
    jz loc_3BF3 ; @03BD8
loc_3BDA:
    cmp byte [LevelActionCountRefreshCounter7-GameDataImage],0x2 ; @03BDA
    jnz loc_3BEA ; @03BDF
    mov [LevelActionCountDisplaySnapshot7-GameDataImage],ah ; @03BE1
    mov byte [LevelActionCountRefreshCounter7-GameDataImage],0xff ; @03BE5
loc_3BEA:
    inc byte [LevelActionCountRefreshCounter7-GameDataImage] ; @03BEA
    mov al,0x9 ; @03BEE
    call DrawStatusCount ; @03BF0
loc_3BF3:
    mov ah,[LevelActionCount0-GameDataImage] ; @03BF3
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03BF7
    jz loc_3C01 ; @03BF9
    cmp [LevelActionCountDisplaySnapshot0-GameDataImage],ah ; @03BFB
    jz loc_3C1A ; @03BFF
loc_3C01:
    cmp byte [LevelActionCountRefreshCounter0-GameDataImage],0x2 ; @03C01
    jnz loc_3C11 ; @03C06
    mov [LevelActionCountDisplaySnapshot0-GameDataImage],ah ; @03C08
    mov byte [LevelActionCountRefreshCounter0-GameDataImage],0xff ; @03C0C
loc_3C11:
    inc byte [LevelActionCountRefreshCounter0-GameDataImage] ; @03C11
    mov al,0x2 ; @03C15
    call DrawStatusCount ; @03C17
loc_3C1A:
    mov ah,[LevelActionCount4-GameDataImage] ; @03C1A
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C1E
    jz loc_3C28 ; @03C20
    cmp [LevelActionCountDisplaySnapshot4-GameDataImage],ah ; @03C22
    jz loc_3C41 ; @03C26
loc_3C28:
    cmp byte [LevelActionCountRefreshCounter4-GameDataImage],0x2 ; @03C28
    jnz loc_3C38 ; @03C2D
    mov [LevelActionCountDisplaySnapshot4-GameDataImage],ah ; @03C2F
    mov byte [LevelActionCountRefreshCounter4-GameDataImage],0xff ; @03C33
loc_3C38:
    inc byte [LevelActionCountRefreshCounter4-GameDataImage] ; @03C38
    mov al,0x6 ; @03C3C
    call DrawStatusCount ; @03C3E
loc_3C41:
    mov ah,[LevelActionCount3-GameDataImage] ; @03C41
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C45
    jz loc_3C4F ; @03C47
    cmp [LevelActionCountDisplaySnapshot3-GameDataImage],ah ; @03C49
    jz loc_3C68 ; @03C4D
loc_3C4F:
    cmp byte [LevelActionCountRefreshCounter3-GameDataImage],0x2 ; @03C4F
    jnz loc_3C5F ; @03C54
    mov [LevelActionCountDisplaySnapshot3-GameDataImage],ah ; @03C56
    mov byte [LevelActionCountRefreshCounter3-GameDataImage],0xff ; @03C5A
loc_3C5F:
    inc byte [LevelActionCountRefreshCounter3-GameDataImage] ; @03C5F
    mov al,0x5 ; @03C63
    call DrawStatusCount ; @03C65
loc_3C68:
    mov ah,[LevelActionCount5-GameDataImage] ; @03C68
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C6C
    jz loc_3C76 ; @03C6E
    cmp [LevelActionCountDisplaySnapshot5-GameDataImage],ah ; @03C70
    jz loc_3C8F ; @03C74
loc_3C76:
    cmp byte [LevelActionCountRefreshCounter5-GameDataImage],0x2 ; @03C76
    jnz loc_3C86 ; @03C7B
    mov [LevelActionCountDisplaySnapshot5-GameDataImage],ah ; @03C7D
    mov byte [LevelActionCountRefreshCounter5-GameDataImage],0xff ; @03C81
loc_3C86:
    inc byte [LevelActionCountRefreshCounter5-GameDataImage] ; @03C86
    mov al,0x7 ; @03C8A
    call DrawStatusCount ; @03C8C
loc_3C8F:
    mov ah,[LevelActionCount1-GameDataImage] ; @03C8F
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03C93
    jz loc_3C9D ; @03C95
    cmp [LevelActionCountDisplaySnapshot1-GameDataImage],ah ; @03C97
    jz loc_3CB6 ; @03C9B
loc_3C9D:
    cmp byte [LevelActionCountRefreshCounter1-GameDataImage],0x2 ; @03C9D
    jnz loc_3CAD ; @03CA2
    mov [LevelActionCountDisplaySnapshot1-GameDataImage],ah ; @03CA4
    mov byte [LevelActionCountRefreshCounter1-GameDataImage],0xff ; @03CA8
loc_3CAD:
    inc byte [LevelActionCountRefreshCounter1-GameDataImage] ; @03CAD
    mov al,0x3 ; @03CB1
    call DrawStatusCount ; @03CB3
loc_3CB6:
    mov ah,[LevelActionCount6-GameDataImage] ; @03CB6
    db 0x22,0xe4 ; ENCODED: and ah,ah (NASM chooses a different encoding) ; @03CBA
    jz loc_3CC4 ; @03CBC
    cmp [LevelActionCountDisplaySnapshot6-GameDataImage],ah ; @03CBE
    jz loc_3CDD ; @03CC2
loc_3CC4:
    cmp byte [LevelActionCountRefreshCounter6-GameDataImage],0x2 ; @03CC4
    jnz loc_3CD4 ; @03CC9
    mov [LevelActionCountDisplaySnapshot6-GameDataImage],ah ; @03CCB
    mov byte [LevelActionCountRefreshCounter6-GameDataImage],0xff ; @03CCF
loc_3CD4:
    inc byte [LevelActionCountRefreshCounter6-GameDataImage] ; @03CD4
    mov al,0x8 ; @03CD8
    call DrawStatusCount ; @03CDA
loc_3CDD:
StatusDisplayReturn:
    ret ; @03CDD
times -(($-$$) != 0x3cde) db 0 ; module end assertion
