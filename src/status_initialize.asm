; Maintained 39CE..3AC7 status contract.
times -(($-$$) != 0x39ce) db 0 ; module start assertion
; CONTRACT: copy both origins first; carry live returned roles through all
; ten count CALLs, decimal field and outline. Keep wrapped byte release-rate
; arithmetic, ordered refresh/snapshot stores and actual SS return words.
; DS0045 is the last drawing-pass count; zero slot bound can leave it stale.
InitializeStatusDisplay:
    call CopyStatusRegionToBothDrawingOrigins ; @039CE
InitializeStatusAfterCopy:
    mov byte [EntityCreationCountdown-GameDataImage],0x14 ; @039D1
    mov al,0x63 ; @039D6
    sub al,[LevelReleaseSetting-GameDataImage] ; @039D8
    shr al,1 ; @039DC
    neg al ; @039DE
    add al,0x35 ; @039E0
    neg al ; @039E2
    add al,0x39 ; @039E4
    mov [EntityCreationReload-GameDataImage],al ; @039E6
    mov byte [LevelReleaseMinimumRefreshCounter-GameDataImage],0x0 ; @039E9
    mov byte [LevelReleaseSettingRefreshCounter-GameDataImage],0x0 ; @039EE
    mov byte [LevelActionCountRefreshCounter2-GameDataImage],0x0 ; @039F3
    mov byte [LevelActionCountRefreshCounter7-GameDataImage],0x0 ; @039F8
    mov byte [LevelActionCountRefreshCounter0-GameDataImage],0x0 ; @039FD
    mov byte [LevelActionCountRefreshCounter4-GameDataImage],0x0 ; @03A02
    mov byte [LevelActionCountRefreshCounter3-GameDataImage],0x0 ; @03A07
    mov byte [LevelActionCountRefreshCounter5-GameDataImage],0x0 ; @03A0C
    mov byte [LevelActionCountRefreshCounter1-GameDataImage],0x0 ; @03A11
    mov byte [LevelActionCountRefreshCounter6-GameDataImage],0x0 ; @03A16
    mov byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @03A1B
    mov byte [LevelReleaseMinimumDisplaySnapshot-GameDataImage],0xff ; @03A20
    mov byte [LevelReleaseSettingDisplaySnapshot-GameDataImage],0xff ; @03A25
    mov byte [LevelActionCountDisplaySnapshot2-GameDataImage],0xff ; @03A2A
    mov byte [LevelActionCountDisplaySnapshot7-GameDataImage],0xff ; @03A2F
    mov byte [LevelActionCountDisplaySnapshot0-GameDataImage],0xff ; @03A34
    mov byte [LevelActionCountDisplaySnapshot4-GameDataImage],0xff ; @03A39
    mov byte [LevelActionCountDisplaySnapshot3-GameDataImage],0xff ; @03A3E
    mov byte [LevelActionCountDisplaySnapshot5-GameDataImage],0xff ; @03A43
    mov byte [LevelActionCountDisplaySnapshot1-GameDataImage],0xff ; @03A48
    mov byte [LevelActionCountDisplaySnapshot6-GameDataImage],0xff ; @03A4D
    mov byte [StatusIconDisplaySnapshot-GameDataImage],0x3 ; @03A52
    mov ah,[LevelReleaseSettingMinimum-GameDataImage] ; @03A57
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @03A5B
    call DrawStatusCount ; @03A5D
InitializeStatusAfterMinimum:
    mov ah,[LevelReleaseSetting-GameDataImage] ; @03A60
    mov al,0x1 ; @03A64
    call DrawStatusCount ; @03A66
InitializeStatusAfterRelease:
    mov ah,[LevelActionCount2-GameDataImage] ; @03A69
    mov al,0x4 ; @03A6D
    call DrawStatusCount ; @03A6F
InitializeStatusAfterAction2:
    mov ah,[LevelActionCount7-GameDataImage] ; @03A72
    mov al,0x9 ; @03A76
    call DrawStatusCount ; @03A78
InitializeStatusAfterAction7:
    mov ah,[LevelActionCount0-GameDataImage] ; @03A7B
    mov al,0x2 ; @03A7F
    call DrawStatusCount ; @03A81
InitializeStatusAfterAction0:
    mov ah,[LevelActionCount4-GameDataImage] ; @03A84
    mov al,0x6 ; @03A88
    call DrawStatusCount ; @03A8A
InitializeStatusAfterAction4:
    mov ah,[LevelActionCount3-GameDataImage] ; @03A8D
    mov al,0x5 ; @03A91
    call DrawStatusCount ; @03A93
InitializeStatusAfterAction3:
    mov ah,[LevelActionCount5-GameDataImage] ; @03A96
    mov al,0x7 ; @03A9A
    call DrawStatusCount ; @03A9C
InitializeStatusAfterAction5:
    mov ah,[LevelActionCount1-GameDataImage] ; @03A9F
    mov al,0x3 ; @03AA3
    call DrawStatusCount ; @03AA5
InitializeStatusAfterAction1:
    mov ah,[LevelActionCount6-GameDataImage] ; @03AA8
    mov al,0x8 ; @03AAC
    call DrawStatusCount ; @03AAE
InitializeStatusAfterAction6:
    mov al,[EntityDrawingPassCount-GameDataImage] ; @03AB1
    mov si,StatusEntityCountField-GameDataImage ; @03AB4
    call WriteDecimalByteField ; @03AB7
InitializeStatusAfterDecimal:
    mov si,StatusPercentDigits-GameDataImage+1 ; @03ABA
    mov byte [si-0x1],0x20 ; @03ABD
    mov al,[EntityActionSelector-GameDataImage] ; @03AC1
    call DrawStatusIconOutline ; @03AC4
InitializeStatusReturn:
    ret ; @03AC7
times -(($-$$) != 0x3ac8) db 0 ; module end assertion
