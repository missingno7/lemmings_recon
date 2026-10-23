; Maintained 706F..715E entity sprite parent; physical order unchanged.
; CALLBACK /715B TARGET CONTRACT. The target is record+14 sampled at 70F0.
; LEGITIMATE WRITERS. Slots DS:002E..003E are written only by 0FC1..0FF1
; (6170,64D9,65D8,66D7,6817,6957,6A97,6BDB,6CFC) in session setup 03E7, after
; the startup/level clears that zero them and before any draw (3634 runs only
; from game frames). Record+14 is zeroed by the 30F3 clear and then written
; only by the 32 explicit word stores (constructor 3140 and the state/action
; stores), each loading AX from one slot. Draws visit constructed records
; k<count; the pinned level headers bound count to 50h (records 0088..0E97).
; Action 5 (347F/3488) and visibility 4119 rewrite +14 only with DF=1. No
; legitimate path has DF=1 there: the only main STD (1BB0) is cleared by CLD
; 1D34, and the game timer (whose commands reach 4119) is installed at 0492/
; 0183 only after DAT decoding and restored at 02FB before the next load.
; TARGET SET: the nine slot values, all decoded.
; Not legitimate: the creation race (timer 1874->3E6F->4013 snapshots the
; limit between 30CC and 314B) lets records spill past 4F; visibility,
; keyboard, animation and palette writers then overlay spilled +14 words. The
; call goes to CS:F(state): a characterized corrupted-control escape where the
; specification ends. A saved-target overwrite by the strip mirrors needs an
; entry SP near 000E, which no legitimate caller has.
times -(($-$$) != 0x706f) db 0 ; module start assertion
; STACK: the strip/callback closure peaks 20h bytes below entry S (caller frame
; additional). DI S-2, alignment S-4, callback S-6 and strip DS S-12 are live
; SS words.
; CONTRACT: live DS:DI entity record; +00/+04 form wrapped X for visibility,
; +02/+06 form signed-clamped Y. +28 plus optional +29 selects the frame;
; +27==1 suppresses that add, +2A==FF suppresses eight-way alignment scaling.
; Full MUL by +10 yields paragraph/cursor parts; +0C/1FE6 supply source CX,
; +0A supplies SI and +12 supplies BX. These uses do not prove record bounds.
; Visibility miss bypasses both children. Restored AL from +20 gates the strip.
; +14 is PUSHed at 70F0, then reread from live SS at 7159 before CALL AX 715B.
; Real 7155/715D child returns, saved DI and outer RET remain live SS words.
; DS is inherited (ordinary frame relocated09A9);706F itself never sets it.
; A near CALL uses the current CS, not an implied far segment from the record.
;
; Let S be entry SP, with intact code, stable SS and ordinary CALL/RET balance.
; Saved DI is SS:S-2, alignment S-4, callback S-6; selector AX at70FF and DX
; at7100 temporarily use S-8/S-0A and are popped before7118. Offsets wrap16.
; No-strip path writes no further parent location S-6, so without asynchronous
; or device/provider writes7159 returns exactly the word read at70F0. This is
; true even if later reads see changed record+14: the record is not reloaded.
; Strip path711E first POPs the live callback toAX, then7121 PUSHes it again;
; a write before711E can therefore also replace the value being preserved.
; Saved DI/CX/SI/BX use S-8/-0A/-0C/-0E; CALL7152 uses S-10 for return7155.
; Child6F7B saves DS atS-12 and row CX atS-14, writes live SS:0000/0002/
; 0008/000A/000C/000E mirrors and VGA ES:A000 destinations, then STI/POP DS/RET.
; Fixed SS mirrors or physical VGA aliases can overwrite S-6 or other saves;
; a changed child RET need not reach7155. Returned DS is the actual saved word.
; Concrete raw-entry exclusion: S=000E puts saved callback atSS:0008. Child
; 6F83 writes0F02 there; with disjoint VGA and intact7155 return,7159 reads
; 0F02, outside the nine targets. Other parent saves also overlap mirrors.
; This is a static alias witness, not proof that ordinary callers use that SP.
; After actual7155..7158 restores,7159 POPs the saved callback and715A alignment;
; CALL715B PUSHes715D atS-4. The callback may alter the remaining DI/outerRET
; saves; the outer pop/RET is not an abstract host restore. No IF/DF promise is
; added: strip and raster children force IF through CLI/STI and retain DF.
; Offsets/SP wrap16; word high byte follows physical low+1 with20-bit wrap.
; DS AT715B: no-strip path inherits706F DS exactly. Strip6F7C saves that DS,
;6FAB sets source DS=CX and6FE0 restores the live saved word;7155..715A do
; not repair DS. CX restored at7157 is the sprite source segment computed
; at7112/7116, not main DS; the strip instead uses1FE8 at7126. Known targets
; save current DS, set source DS from CX and restore the actual save on exit.
; Near CALL715B retains current CS; callback+14 has no segment component.
; SS is the live stack/map/mirror frame, not implicitly DS. For foreground
; SP=P,3634's CALL/save/save/CALL gives706F S=P-8. If P=4AF4 with intact
; balance, callback save is4AE6 and strip DS save4ADA, clear of low SS mirrors
; and the normal dirty maps ending48F3. This is a sufficient local placement,
; not a proof that arbitrary prior execution preserves that SP/SS/DS domain.
; READINESS READY for the legitimate domain: the nine targets above.
; SPILL ESCAPES (characterized, not legitimate): rebuilt visibility gives
; slots 50..54 callbacks in {0000,0001,0100,0101}, keyboard make/break writes
; 00/94 bytes into slots 55/56, animation and palette writers overlay slots
; 84..98 and D3..D8. The transfer then reaches CS:F(state); no nine-callback
; ABI applies and native code reports an unsupported escape.
DrawObjectSprite:
    push di ; @0706F
    mov bx,[di+EntityRecordX-EntityRecordsBase] ; @07070
    add bx,[di+EntityRecordDrawingXBias-EntityRecordsBase] ; @07072
    jns loc_707B ; @07075
    add bx,0x160 ; @07077
loc_707B:
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @0707B
    shr bx,1 ; @0707D
    shr bx,1 ; @0707F
    shr bx,1 ; @07081
    mov si,ViewVisibilityMapBase-GameDataImage ; @07083
    cmp byte [bx+si],0x1 ; @07086
    jz loc_708E ; @07089
    jmp EntitySpriteRestoreDI ; @0708B
loc_708E:
    mov ax,[LevelViewOriginPixels-GameDataImage] ; @0708E
    sub ax,0x10 ; @07091
    db 0x2b,0xd0 ; ENCODED: sub dx,ax (NASM chooses a different encoding) ; @07094
    jns loc_709C ; @07096
    add dx,0x160 ; @07098
loc_709C:
    db 0x8b,0xda ; ENCODED: mov bx,dx (NASM chooses a different encoding) ; @0709C
    and bx,byte +0x7 ; @0709E
    push bx ; @070A1
    mov al,[di+EntityRecordFrameSelector-EntityRecordsBase] ; @070A2
    cmp byte [di+EntityRecordFrameAddGate-EntityRecordsBase],0x1 ; @070A5
    jz loc_70AE ; @070A9
    add al,[di+EntityRecordFrameAddend-EntityRecordsBase] ; @070AB
loc_70AE:
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @070AE
    cmp byte [di+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @070B0
    jz loc_70BE ; @070B4
    shl ax,1 ; @070B6
    shl ax,1 ; @070B8
    shl ax,1 ; @070BA
    db 0x03,0xc3 ; ENCODED: add ax,bx (NASM chooses a different encoding) ; @070BC
loc_70BE:
    push dx ; @070BE
    mov cx,[di+EntityRecordSpriteFrameStride-EntityRecordsBase] ; @070BF
    mul cx ; @070C2
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @070C4
    shr dx,1 ; @070C6
    rcr bp,1 ; @070C8
    shr dx,1 ; @070CA
    rcr bp,1 ; @070CC
    shr dx,1 ; @070CE
    rcr bp,1 ; @070D0
    shr dx,1 ; @070D2
    rcr bp,1 ; @070D4
    add bp,[di+EntityRecordSpriteParagraphOffset-EntityRecordsBase] ; @070D6
    and ax,0xf ; @070D9
    pop dx ; @070DC
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @070DD
    add si,[di+EntityRecordSpriteSourceOffset-EntityRecordsBase] ; @070DF
    db 0x8b,0xde ; ENCODED: mov bx,si (NASM chooses a different encoding) ; @070E2
    add bx,[di+EntityRecordSpriteMaskOffset-EntityRecordsBase] ; @070E4
    shr dx,1 ; @070E7
    shr dx,1 ; @070E9
    shr dx,1 ; @070EB
    mov cx,[di+EntityRecordDrawingYBias-EntityRecordsBase] ; @070ED
; Callback sampled here is saved at SS:S-6 and reread at 7159 (both paths).
    push word [di+EntityRecordSpriteCallback-EntityRecordsBase] ; @070F0
    mov al,[di+EntityRecordStripSelector-EntityRecordsBase] ; @070F3
    mov di,[di+EntityRecordY-EntityRecordsBase] ; @070F6
    db 0x03,0xf9 ; ENCODED: add di,cx (NASM chooses a different encoding) ; @070F9
    jns loc_70FF ; @070FB
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @070FD
loc_70FF:
    push ax ; @070FF
    push dx ; @07100
    db 0x8b,0xc7 ; ENCODED: mov ax,di (NASM chooses a different encoding) ; @07101
    mov di,0x2c ; @07103
    mul di ; @07106
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @07108
    pop dx ; @0710A
    pop ax ; @0710B
    db 0x03,0xfa ; ENCODED: add di,dx (NASM chooses a different encoding) ; @0710C
    add di,[DrawingOrigin-GameDataImage] ; @0710E
    mov cx,[EntitySpriteBufferSegment-GameDataImage] ; @07112
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @07116
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @07118
    jz loc_7159 ; @0711A
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @0711C
    pop ax ; @0711E
    pop dx ; @0711F
    push dx ; @07120
    push ax ; @07121
    push di ; @07122
    push cx ; @07123
    push si ; @07124
    push bx ; @07125
    mov cx,[GeneratedGraphicsBufferSegment-GameDataImage] ; @07126
    shl dl,1 ; @0712A
    shl dl,1 ; @0712C
    shl dl,1 ; @0712E
    shl dl,1 ; @07130
    db 0x32,0xf6 ; ENCODED: xor dh,dh (NASM chooses a different encoding) ; @07132
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @07134
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @07136
    and ah,0xf0 ; @07138
    mov al,0x40 ; @0713B
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @0713D
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0713F
    shl ax,1 ; @07141
    shl ax,1 ; @07143
    shl ax,1 ; @07145
    add ax,0x1070 ; @07147
    db 0x03,0xc2 ; ENCODED: add ax,dx (NASM chooses a different encoding) ; @0714A
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @0714C
    sub di,0x15f ; @0714E
    call DrawEntityTwoByteStrip ; @07152
EntitySpriteStripResume:
    pop bx ; @07155
    pop si ; @07156
    pop cx ; @07157
    pop di ; @07158
loc_7159:
    pop ax ; @07159
    pop dx ; @0715A
; CALL AX in current CS pushes 715D; target set at the module header.
EntitySpriteIndirectCall:
    call ax ; @0715B
EntitySpriteRestoreDI:
    pop di ; @0715D
EntitySpriteReturn:
    ret ; @0715E
times -(($-$$) != 0x715f) db 0 ; module end assertion
