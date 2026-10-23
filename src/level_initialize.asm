; Level initialization ownership:368E..3789, including live clear tail and header prefix.
; Physical order and UNKNOWN374E are retained; this is not a historical linker claim.
; Clear 34944 VGA bytes at 4A40 with incoming DF, then set 1664x164 layout.
; Live near/far return frames and DS input-segment publication follow both calls.
InitializeLevelDrawing:
    mov di,0x4a40 ; @0368E
    mov cx,0x8880 ; @03691
    call ClearVgaBytes ; @03694
LevelDrawingAfterClear:
    mov ax,0x680 ; @03697
    mov bx,0xa4 ; @0369A
    mov dx,0x4a40 ; @0369D
    call 0x0:SetDrawingLayout ; @036A0
LevelDrawingAfterLayout:
    mov ax,[GraphicsResourceInputSegment-GameDataImage] ; @036A5
    inc ax ; @036A8
    mov [GraphicsResourceSegment-GameDataImage],ax ; @036A9
    ret ; @036AC
; Tail entry: clear 832 bytes at CC40 through ClearVgaBytes, using the outer RET.
ClearLevelDrawingTail:
    mov di,0xcc40 ; @036AD
    mov cx,0x340 ; @036B0
    jmp ClearVgaBytes ; @036B3
; LEVEL-RECORD CONSUMER: main DS, LoadedLevelRecord big-endian header words.
; Copies low bytes to64/67,47,44 and eight skill counters; time word+30 contributes
; only AL to20A7. Camera word+10 feeds pixel and byte offsets.
; Selects special setup or sentinel-terminated terrain records, then object helpers
; and nominal13 live-counter calls to796F. Native composition:c/level_initialize.c;
; inherited provider/alias domains and UNKNOWN374E remain explicit in its contract.
InitializeLevelFromRecord:
sub_36B6 equ InitializeLevelFromRecord
    call InitializeLevelDrawing ; @036B6
; V4 LEVEL FIELD CONTRACT (DS:0FCB, nominal 0800 bytes from LEVEL000..009):
; +00 release, +02 creation, +04 required numerator, +06 time, +08..16 eight
; skill counts are BE words, read high then low. Only low bytes are published,
; except +18: wrapped word+10 ->0000, then three logical SHRs ->0002.
; 36D6's 0044 copy has no closed all-consumer role; 4591 separately uses raw
; +05*64h / raw+03 at459C (byte DIV faults for zero or quotient>FF).
; Header +1B/+1D are byte-only graphics/special selectors (1A00/1A26/3742).
; +1A/+1C/+1E..1F roles remain UNRESOLVED; zero file values do not mean padding.
; 4551 forward clear stops at0FC9; resource/working bytes survive until replaced.
; DAT short counts/malformed tokens use mixed prior/header/payload bytes;
; a C shadow header or zero-fill would change that behavior.
ApplyLevelHeader:
    mov di,LoadedLevelRecord-GameDataImage ; @036B9
    mov ah,[di] ; @036BC
    mov al,[di+0x1] ; @036BE
    mov [LevelReleaseSettingMinimum-GameDataImage],al ; @036C1
    mov [LevelReleaseSetting-GameDataImage],al ; @036C4
    mov ah,[di+0x2] ; @036C7
    mov al,[di+0x3] ; @036CA
; T2 DATA-CONDITIONAL original LEVEL000..009/ODDTABLE/54EE order gives low limit<=50;0047 takes low byte only. Prefix theorem also excludes4013 race30CC..314B and other writers. Later spill over loaded header does not itself reassign0047.
; CAPACITY: only header+03 reaches byte0047; high+02 is discarded. Static pinned80 LEVEL sections plus40 forward odd rows selected by nominal120 order have high00/max50h (80 decimal). Other40 odd rows hold0063. This producer bound requires complete reads/intact order/DF0 override; it is not a constructor check. IRQ4013 racing30D5..314B can still step the published count past a reduced limit.
    mov [LevelCreationLimit-GameDataImage],al ; @036CD
    mov ah,[di+0x4] ; @036D0
    mov al,[di+0x5] ; @036D3
    mov [LevelHeaderWord04LowByte-GameDataImage],al ; @036D6
    mov ah,[di+0x6] ; @036D9
    mov al,[di+0x7] ; @036DC
    add ax,0x30 ; @036DF
    mov [LevelCountdownHighDigit-GameDataImage],al ; @036E2
    mov ah,[di+0x8] ; @036E5
    mov al,[di+0x9] ; @036E8
    mov [LevelActionCount0-GameDataImage],al ; @036EB
    mov ah,[di+0xa] ; @036EE
    mov al,[di+0xb] ; @036F1
    mov [LevelActionCount1-GameDataImage],al ; @036F4
    mov ah,[di+0xc] ; @036F7
    mov al,[di+0xd] ; @036FA
    mov [LevelActionCount2-GameDataImage],al ; @036FD
    mov ah,[di+0xe] ; @03700
    mov al,[di+0xf] ; @03703
    mov [LevelActionCount3-GameDataImage],al ; @03706
    mov ah,[di+0x10] ; @03709
    mov al,[di+0x11] ; @0370C
    mov [LevelActionCount4-GameDataImage],al ; @0370F
    mov ah,[di+0x12] ; @03712
    mov al,[di+0x13] ; @03715
    mov [LevelActionCount5-GameDataImage],al ; @03718
    mov ah,[di+0x14] ; @0371B
    mov al,[di+0x15] ; @0371E
    mov [LevelActionCount6-GameDataImage],al ; @03721
    mov ah,[di+0x16] ; @03724
    mov al,[di+0x17] ; @03727
    mov [LevelActionCount7-GameDataImage],al ; @0372A
    mov ah,[di+0x18] ; @0372D
    mov al,[di+0x19] ; @03730
    add ax,0x10 ; @03733
; R3 DATA-A origin bound:all80 supplied LEVEL headers and120 nominal selected
; headers yield(headerBE16+18+0010) in0010..04A0,multiples0010. Odd override
; copies first18 bytes only,retaining this field. Minimap3FBE..3FDB and aligned
; scroll40E5/414F preserve0010..0500; their equality checks do not clamp corrupt
; origins. This condition bounds4131 away from2013/25A0,not all writer domains.
    mov [LevelViewOriginPixels-GameDataImage],ax ; @03736
    shr ax,1 ; @03739
    shr ax,1 ; @0373B
    shr ax,1 ; @0373D
    mov [LevelViewOriginBytes-GameDataImage],ax ; @0373F
LevelAfterHeader:
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @03742
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @03745
    jz DrawLevelTerrainStream ; @03747
    call SetupSpecialGraphicsResource ; @03749
LevelInitializeAfterSpecial:
    jmp short loc_376A ; @0374C
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @0374E
; TERRAIN STREAM: four separate BEbyte reads,liveSI+4,FFFF sentinel; no400record limit.
; Child7C67 preserves or changes liveiterator/segments/returnwords; expose changedtargets.
DrawLevelTerrainStream:
    mov si,LevelTerrainDefinitions-GameDataImage ; @0374F
SetupTerrainCommand:
    mov ah,[si] ; @03752
    mov al,[si+0x1] ; @03754
    mov bh,[si+0x2] ; @03757
    mov bl,[si+0x3] ; @0375A
    add si,byte +0x4 ; @0375D
    cmp ax,0xffff ; @03760
    jz loc_376A ; @03763
SetupTerrainPieceCall:
    call DrawPackedTerrainPiece ; @03765
SetupTerrainAfterPiece:
    jmp short SetupTerrainCommand ; @03768
loc_376A:
PrepareLevelObjectState:
    ; Native four-call span ends at3776 or an exposed changed near-return target.
    ; No complete36B6 C implementation implied; docs/interaction-cells.md.
    call CopyLevelObjectGraphicsRecords ; @0376A
ObjectStateAfterGraphicsCopy:
    call WriteSteelInteractionCells ; @0376D
ObjectStateAfterSteelCells:
    call WriteObjectInteractionCells ; @03770
ObjectStateAfterObjectCells:
    call CollectTypeOneObjectCoordinates ; @03773
ObjectStateAfterCoordinates:
FinishLevelInitialization:
    ; Logical tail: live clear return, thirteen initial minimap iterations;
    ; each restored SS:CX controls LOOP, including aliases and16-bit wrap.
    call ClearLevelDrawingTail ; @03776
LevelFinishAfterClear:
    mov cx,0xd ; @03779
loc_377C:
LevelFinishMinimapLoop:
    push cx ; @0377C
; Thirteen CALL796F iterations carry live DF; outer PUSH/POP CX does not clear it.
; With DF1 each minimap clear writes83AF..83C2; no local CLD establishes a game-wide invariant.
    call UpdateMinimapColumn ; @0377D
LevelFinishAfterColumn:
    pop cx ; @03780
    loop LevelFinishMinimapLoop ; @03781
    mov ax,[LevelGraphicsSegment-GameDataImage] ; @03783
    mov [GraphicsResourceSegment-GameDataImage],ax ; @03786
LevelFinishNearReturn:
    ret ; @03789
