; Connected input-command parent3E6F..4084; UNKNOWN bytes remain explicit.
; Shared foreground counters and latches retain byte wrap and signed/unsigned tests.
; INT61/60 can return fullsegments/frame state; later gates use returnedDS.
; Actual CALL410F/RET3FE1 and relocated MOVoperand4137 remain live.
; docs/input-commands.md; shared C/verification boundaries do not close unknowncode.
times -(($-$$) != 0x3e6f) db 0
ProcessInputCommands3E6F:
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @03E6F
    cmp al,0x3b ; @03E72
    jnz loc_3E79 ; @03E74
    jmp loc_4068 ; @03E76
loc_3E79:
    cmp al,0x3c ; @03E79
    jnz loc_3E80 ; @03E7B
    jmp loc_403D ; @03E7D
loc_3E80:
    cmp al,0x4e ; @03E80
    jnz loc_3E87 ; @03E82
    jmp loc_4018 ; @03E84
loc_3E87:
    cmp al,0x57 ; @03E87
    jnz loc_3E8E ; @03E89
    jmp loc_4018 ; @03E8B
loc_3E8E:
    cmp al,0x58 ; @03E8E
    jnz loc_3E95 ; @03E90
    jmp loc_3FEF ; @03E92
loc_3E95:
    cmp al,0x53 ; @03E95
    jnz loc_3E9C ; @03E97
    jmp loc_3FEF ; @03E99
loc_3E9C:
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @03E9C
    mov al,0x2 ; @03E9E
    cmp ah,0x3d ; @03EA0
    jnz loc_3EA8 ; @03EA3
    jmp loc_3F5C ; @03EA5
loc_3EA8:
    inc al ; @03EA8
    cmp ah,0x3e ; @03EAA
    jnz loc_3EB2 ; @03EAD
    jmp loc_3F5C ; @03EAF
loc_3EB2:
    inc al ; @03EB2
    cmp ah,0x3f ; @03EB4
    jnz loc_3EBC ; @03EB7
    jmp loc_3F5C ; @03EB9
loc_3EBC:
    inc al ; @03EBC
    cmp ah,0x40 ; @03EBE
    jnz loc_3EC6 ; @03EC1
    jmp loc_3F5C ; @03EC3
loc_3EC6:
    inc al ; @03EC6
    cmp ah,0x41 ; @03EC8
    jnz loc_3ED0 ; @03ECB
    jmp loc_3F5C ; @03ECD
loc_3ED0:
    inc al ; @03ED0
    cmp ah,0x42 ; @03ED2
    jnz loc_3EDA ; @03ED5
    jmp loc_3F5C ; @03ED7
loc_3EDA:
    inc al ; @03EDA
    cmp ah,0x43 ; @03EDC
    jnz loc_3EE4 ; @03EDF
    jmp short loc_3F5C ; @03EE1
; S14 U054: [03EE3,03EE4) stored bytes remain UNKNOWN.
; Neighbours: P 03EE1 jmp 0x3f5c; N 03EE4 inc al.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EE3
loc_3EE4:
    inc al ; @03EE4
    cmp ah,0x44 ; @03EE6
    jnz loc_3EEE ; @03EE9
    jmp short loc_3F5C ; @03EEB
; S14 U055: [03EED,03EEE) stored bytes remain UNKNOWN.
; Neighbours: P 03EEB jmp 0x3f5c; N 03EEE mov ax, word ptr [0x14].
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EED
loc_3EEE:
    mov ax,[InputButtonsWord-GameDataImage] ; @03EEE
    test ax,0x1 ; @03EF1
    jnz loc_3EF9 ; @03EF4
    jmp loc_3FE3 ; @03EF6
loc_3EF9:
    mov ax,[PointerY-GameDataImage] ; @03EF9
    add ax,0x8 ; @03EFC
    cmp ax,0xc0 ; @03EFF
    jnl loc_3F07 ; @03F02
    jmp loc_3FE9 ; @03F04
loc_3F07:
    mov ax,[PointerX-GameDataImage] ; @03F07
    add ax,0xfff8 ; @03F0A
    cmp ax,0xd0 ; @03F0D
    jl loc_3F15 ; @03F10
    jmp short loc_3F92 ; @03F12
; S14 U056: [03F14,03F15) stored bytes remain UNKNOWN.
; Neighbours: P 03F12 jmp 0x3f92; N 03F15 cmp byte ptr [0x84], 0.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F14
loc_3F15:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @03F15
    jz loc_3F1F ; @03F1A
    jmp loc_3FE9 ; @03F1C
loc_3F1F:
    shr ax,1 ; @03F1F
    shr ax,1 ; @03F21
    shr ax,1 ; @03F23
    shr ax,1 ; @03F25
    cmp al,0x2 ; @03F27
    jnl loc_3F2E ; @03F29
    jmp loc_4032 ; @03F2B
loc_3F2E:
    cmp byte [PanelClickLatch0062-GameDataImage],0xff ; @03F2E
    jnz loc_3F38 ; @03F33
    jmp loc_3FE9 ; @03F35
loc_3F38:
    mov byte [PanelClickLatch0062-GameDataImage],0xff ; @03F38
    cmp al,0xa ; @03F3D
    jnz loc_3F44 ; @03F3F
    jmp loc_4018 ; @03F41
loc_3F44:
    cmp al,0xb ; @03F44
    jnz loc_3F4B ; @03F46
    jmp loc_3FEF ; @03F48
loc_3F4B:
    cmp al,0xc ; @03F4B
    jnz loc_3F52 ; @03F4D
    jmp loc_3FEE ; @03F4F
loc_3F52:
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @03F52
    jnz loc_3F5C ; @03F57
    jmp loc_3FE9 ; @03F59
loc_3F5C:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @03F5C
    jz loc_3F66 ; @03F61
    jmp loc_3FE9 ; @03F63
loc_3F66:
    mov [EntityActionSelector-GameDataImage],al ; @03F66
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @03F69
    jnz loc_3F7C ; @03F6E
    test byte [SoundOptionBits-GameDataImage],0x3 ; @03F70
    jz loc_3F7C ; @03F75
    mov ax,0x401 ; @03F77
InputCommandsInt613F7A:
    int 0x61 ; @03F7A
loc_3F7C:
InputCommandsAfterInt613F7C:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @03F7C
    jz loc_3F8F ; @03F81
    test byte [SoundOptionBits-GameDataImage],0x1 ; @03F83
    jz loc_3F8F ; @03F88
    mov ax,0x313 ; @03F8A
InputCommandsInt603F8D:
    int 0x60 ; @03F8D
loc_3F8F:
InputCommandsAfterInt603F8F:
    jmp short loc_3FE9 ; @03F8F
; S14 U057: [03F91,03F92) stored bytes remain UNKNOWN.
; Neighbours: P 03F8F jmp 0x3fe9; N 03F92 mov byte ptr [0x62], 0xff.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F91
loc_3F92:
    mov byte [PanelClickLatch0062-GameDataImage],0xff ; @03F92
    cmp byte [TimerChainFlag1FCF-GameDataImage],0x0 ; @03F97
    jnz loc_3FEE ; @03F9C
    mov bx,[LevelViewOriginPixels-GameDataImage] ; @03F9E
    shr bx,1 ; @03FA2
    shr bx,1 ; @03FA4
    shr bx,1 ; @03FA6
    shr bx,1 ; @03FA8
    add bx,0xd0 ; @03FAA
    db 0x3b,0xc3 ; ENCODED: cmp ax,bx (NASM chooses a different encoding) ; @03FAE
    jnl loc_3FBE ; @03FB0
    add bx,byte +0x18 ; @03FB2
    db 0x3b,0xc3 ; ENCODED: cmp ax,bx (NASM chooses a different encoding) ; @03FB5
    jl loc_3FBE ; @03FB7
    cmp ax,0xd0 ; @03FB9
    jl loc_3FE9 ; @03FBC
loc_3FBE:
    sub ax,0xda ; @03FBE
    jns loc_3FC5 ; @03FC1
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @03FC3
loc_3FC5:
    cmp ax,0x4f ; @03FC5
    jng loc_3FCD ; @03FC8
    mov ax,0x4f ; @03FCA
loc_3FCD:
    shl ax,1 ; @03FCD
    add ax,0x2 ; @03FCF
    mov [LevelViewOriginBytes-GameDataImage],ax ; @03FD2
    shl ax,1 ; @03FD5
    shl ax,1 ; @03FD7
    shl ax,1 ; @03FD9
    mov [LevelViewOriginPixels-GameDataImage],ax ; @03FDB
InputCommandsViewCall3FDE:
    call RebuildViewVisibilityMap ; @03FDE
InputCommandsAfterView3FE1:
    jmp short loc_3FE9 ; @03FE1
loc_3FE3:
    mov byte [PanelClickLatch0062-GameDataImage],0x0 ; @03FE3
InputCommandsReleaseReturn3FE8:
    ret ; @03FE8
loc_3FE9:
    mov byte [PanelClickLatch0062-GameDataImage],0xff ; @03FE9
loc_3FEE:
InputCommandsReturn3FEE:
    ret ; @03FEE
loc_3FEF:
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @03FEF
    jz loc_3FEE ; @03FF4
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @03FF6
    mov al,[ForegroundCounter1FD3-GameDataImage] ; @03FFB
    mov ah,[InputActionSnapshot1FD4-GameDataImage] ; @03FFE
    mov [InputActionSnapshot1FD4-GameDataImage],al ; @04002
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @04005
    cmp al,0x5 ; @04007
    jg loc_3FEE ; @04009
    mov byte [EntityScanRequest-GameDataImage],0xff ; @0400B
    mov al,[EntitySlotBound-GameDataImage] ; @04010
; S17 flow-state: The foreground constructor retains IF across30CC..314B. Under the
; documented timer/command eligibility and intact IRET saves, this store may snapshot old
; boundB after limit sampling, then foreground publication producesB+1 without recheck.
; No <=50h population proof follows solely from supplied header bounds. Native
; IRQ-at-poll scheduling omits this original schedule.
; PUBLICATION RACE: this command runs from IRQ1874->3E6F. If4010/4013 snapshots B after30D5 passed and before314B, it installs limit B while the pending constructor later publishes B+1. There is no constructor recheck/CLI, and scan request004B does not close0055. Next due creation sees inequality and can spill; B4F/header50 permits index50 on the following due call. Outside an in-flight creation, snapshotting the bound stops further creation normally. The stale-limit window begins after30CC reads0047; IRQ-before-CMP restores the old AL. Serialize sampling through314B.
    mov [LevelCreationLimit-GameDataImage],al ; @04013
    jmp short loc_3FEE ; @04016
loc_4018:
    mov al,[ForegroundCounter0052-GameDataImage] ; @04018
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @0401B
    sub bl,[InputToggleSnapshot0053-GameDataImage] ; @0401D
    cmp bl,0x2 ; @04021
    jnc loc_4028 ; @04024
    jmp short loc_3FEE ; @04026
loc_4028:
    xor byte [EntityUpdateGate-GameDataImage],0xff ; @04028
    mov [InputToggleSnapshot0053-GameDataImage],al ; @0402D
    jmp short loc_3FEE ; @04030
loc_4032:
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @04032
    jz loc_3FEE ; @04037
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @04039
    jz loc_4068 ; @0403B
loc_403D:
    cmp byte [LevelReleaseSettingRefreshCounter-GameDataImage],0x0 ; @0403D
    jz loc_4046 ; @04042
    jmp short loc_3FE9 ; @04044
loc_4046:
    cmp byte [LevelReleaseSetting-GameDataImage],0x63 ; @04046
    jnz loc_404F ; @0404B
    jmp short loc_3FE9 ; @0404D
loc_404F:
    inc byte [LevelReleaseSetting-GameDataImage] ; @0404F
loc_4053:
    mov al,0x63 ; @04053
    sub al,[LevelReleaseSetting-GameDataImage] ; @04055
    shr al,1 ; @04059
    neg al ; @0405B
    add al,0x35 ; @0405D
    neg al ; @0405F
    add al,0x39 ; @04061
    mov [EntityCreationReload-GameDataImage],al ; @04063
    jmp short loc_3FE9 ; @04066
loc_4068:
    mov bl,[LevelReleaseSettingMinimum-GameDataImage] ; @04068
    cmp byte [LevelReleaseSettingRefreshCounter-GameDataImage],0x0 ; @0406C
    jz loc_4076 ; @04071
    jmp loc_3FE9 ; @04073
loc_4076:
    cmp [LevelReleaseSetting-GameDataImage],bl ; @04076
    jnz loc_407F ; @0407A
    jmp loc_3FE9 ; @0407C
loc_407F:
    dec byte [LevelReleaseSetting-GameDataImage] ; @0407F
    jmp short loc_4053 ; @04083
times -(($-$$) != 0x4085) db 0
