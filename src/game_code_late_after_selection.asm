; Maintained image span03E6F..0410E; physical order and UNKNOWN bytes preserved.
times -(($-$$) != 0x3e6f) db 0 ; module start assertion
sub_3E6F:
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
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EE3
loc_3EE4:
    inc al ; @03EE4
    cmp ah,0x44 ; @03EE6
    jnz loc_3EEE ; @03EE9
    jmp short loc_3F5C ; @03EEB
; UNKNOWN: unresolved bytes
    db 0x90 ; @03EED
loc_3EEE:
    mov ax,[InputButtonsWord-GameDataImage] ; @03EEE
    test ax,0x1 ; @03EF1
    jnz loc_3EF9 ; @03EF4
    jmp loc_3FE3 ; @03EF6
loc_3EF9:
    mov ax,[0x12] ; @03EF9
    add ax,0x8 ; @03EFC
    cmp ax,0xc0 ; @03EFF
    jnl loc_3F07 ; @03F02
    jmp loc_3FE9 ; @03F04
loc_3F07:
    mov ax,[0x10] ; @03F07
    add ax,0xfff8 ; @03F0A
    cmp ax,0xd0 ; @03F0D
    jl loc_3F15 ; @03F10
    jmp short loc_3F92 ; @03F12
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
    cmp byte [0x62],0xff ; @03F2E
    jnz loc_3F38 ; @03F33
    jmp loc_3FE9 ; @03F35
loc_3F38:
    mov byte [0x62],0xff ; @03F38
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
    cmp byte [0x2b],0xff ; @03F52
    jnz loc_3F5C ; @03F57
    jmp loc_3FE9 ; @03F59
loc_3F5C:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @03F5C
    jz loc_3F66 ; @03F61
    jmp loc_3FE9 ; @03F63
loc_3F66:
    mov [EntityActionSelector-GameDataImage],al ; @03F66
    cmp byte [0x2010],0xff ; @03F69
    jnz loc_3F7C ; @03F6E
    test byte [0x25a7],0x3 ; @03F70
    jz loc_3F7C ; @03F75
    mov ax,0x401 ; @03F77
    int 0x61 ; @03F7A
loc_3F7C:
    cmp byte [0x2010],0xff ; @03F7C
    jz loc_3F8F ; @03F81
    test byte [0x25a7],0x1 ; @03F83
    jz loc_3F8F ; @03F88
    mov ax,0x313 ; @03F8A
    int 0x60 ; @03F8D
loc_3F8F:
    jmp short loc_3FE9 ; @03F8F
; UNKNOWN: unresolved bytes
    db 0x90 ; @03F91
loc_3F92:
    mov byte [0x62],0xff ; @03F92
    cmp byte [0x1fcf],0x0 ; @03F97
    jnz loc_3FEE ; @03F9C
    mov bx,[0x0] ; @03F9E
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
    mov [0x2],ax ; @03FD2
    shl ax,1 ; @03FD5
    shl ax,1 ; @03FD7
    shl ax,1 ; @03FD9
    mov [0x0],ax ; @03FDB
    call RebuildViewVisibilityMap ; @03FDE
    jmp short loc_3FE9 ; @03FE1
loc_3FE3:
    mov byte [0x62],0x0 ; @03FE3
    ret ; @03FE8
loc_3FE9:
    mov byte [0x62],0xff ; @03FE9
loc_3FEE:
    ret ; @03FEE
loc_3FEF:
    cmp byte [0x2b],0xff ; @03FEF
    jz loc_3FEE ; @03FF4
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @03FF6
    mov al,[0x1fd3] ; @03FFB
    mov ah,[0x1fd4] ; @03FFE
    mov [0x1fd4],al ; @04002
    db 0x2a,0xc4 ; ENCODED: sub al,ah (NASM chooses a different encoding) ; @04005
    cmp al,0x5 ; @04007
    jg loc_3FEE ; @04009
    mov byte [0x4b],0xff ; @0400B
    mov al,[0x43] ; @04010
    mov [LevelCreationLimit-GameDataImage],al ; @04013
    jmp short loc_3FEE ; @04016
loc_4018:
    mov al,[0x52] ; @04018
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @0401B
    sub bl,[0x53] ; @0401D
    cmp bl,0x2 ; @04021
    jnc loc_4028 ; @04024
    jmp short loc_3FEE ; @04026
loc_4028:
    xor byte [0x2b],0xff ; @04028
    mov [0x53],al ; @0402D
    jmp short loc_3FEE ; @04030
loc_4032:
    cmp byte [0x2b],0xff ; @04032
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
sub_4085:
    mov al,[KeyboardScanCodeByte-GameDataImage] ; @04085
    cmp al,0x2c ; @04088
    jnz loc_408F ; @0408A
    jmp short loc_40B5 ; @0408C
; UNKNOWN: unresolved bytes
    db 0x90 ; @0408E
loc_408F:
    cmp al,0x2d ; @0408F
    jnz loc_4096 ; @04091
    jmp short loc_40CD ; @04093
; UNKNOWN: unresolved bytes
    db 0x90 ; @04095
loc_4096:
    mov ax,[0x12] ; @04096
    add ax,0x8 ; @04099
    cmp ax,0xc0 ; @0409C
    jnl loc_40B4 ; @0409F
    mov ax,[0x10] ; @040A1
    cmp ax,0x8 ; @040A4
    jnz loc_40AC ; @040A7
    jmp loc_414F ; @040A9
loc_40AC:
    cmp ax,0x148 ; @040AC
    jnz loc_40B4 ; @040AF
    jmp short loc_40E5 ; @040B1
; UNKNOWN: unresolved bytes
    db 0x90 ; @040B3
loc_40B4:
    ret ; @040B4
loc_40B5:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @040B5
    jnz loc_40CC ; @040BA
    dec byte [EntityActionSelector-GameDataImage] ; @040BC
    cmp byte [EntityActionSelector-GameDataImage],0x1 ; @040C0
    jnz loc_40CC ; @040C5
    mov byte [EntityActionSelector-GameDataImage],0x9 ; @040C7
loc_40CC:
    ret ; @040CC
loc_40CD:
    cmp byte [StatusIconRefreshCounter-GameDataImage],0x0 ; @040CD
    jnz loc_40CC ; @040D2
    inc byte [EntityActionSelector-GameDataImage] ; @040D4
    cmp byte [EntityActionSelector-GameDataImage],0xa ; @040D8
    jnz loc_40CC ; @040DD
    mov byte [EntityActionSelector-GameDataImage],0x2 ; @040DF
    ret ; @040E4
loc_40E5:
    mov ax,[0x0] ; @040E5
    cmp ax,0x500 ; @040E8
    jz RebuildViewVisibilityMap ; @040EB
    add ax,0x8 ; @040ED
    test word [InputButtonsWord-GameDataImage],0x2 ; @040F0
    jz loc_4100 ; @040F6
    cmp ax,0x500 ; @040F8
    jz loc_4100 ; @040FB
    add ax,0x8 ; @040FD
loc_4100:
    mov [0x0],ax ; @04100
    db 0x8b,0xd0 ; ENCODED: mov dx,ax (NASM chooses a different encoding) ; @04103
    shr dx,1 ; @04105
    shr dx,1 ; @04107
    shr dx,1 ; @04109
    mov [0x2],dx ; @0410B
times -(($-$$) != 0x410f) db 0 ; module end assertion
