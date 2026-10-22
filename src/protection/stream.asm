; Derived execution view. Canonical load bytes are in src/program.asm.
; Stream instructions show bytes visible while TF is on/off; first-word patches can overlap.
; Bytes outside this view retain stored encoding and canonical region classifications.
bits 16
org 0x066d
; R1 PLATFORM-CONDITIONAL sufficient DF domain:063E entryDF0,knownDL0/1 floppy paths,\n; original identified TF/INT1/INT3 views and intact nonalias saves retainDF0 on every known\n; normal return with profile13:AH=0000/0002. Sole live setter08D2 clears;070E/0718,094A/096D\n; and0970/0982 restore their own saved FLAGS;INT3 XOR high03 leavesDF intact.\n; CONSERVATIVE disk-return DF is unknown. Actual dynamic views/frames/caller provenance,\n; IRQ scheduling/aliases and absolute/raw write alternatives remain separate obligations.
; State inventory (half-open byte ranges; not one simultaneously loaded image):
; tf_on: [066D,084D),[0852,087E),[0883,0970),[0D9E,0D9F),
;        [0DA2,0DA4),[0DAA,0DAC),[0DB2,0DB3).
; tf_off: [0970,098C),[0D9F,0DA2),[0DA4,0DAA),[0DAC,0DB2),[0E3A,0E66).
; Canonical INT3 [0DB3,0DFF) executes unchanged; active INT1 [0DFF,0E3A)
; is the separate byte-negated plaintext view in int1.asm. INT3 at 066C
; creates the first TF-on point; the table below's gates toggle saved TF/IF.
; Conditional CFG alternatives are retained, not proof every arm is reachable.
; READINESS: CONDITIONAL known startup DL=0, TF clear, disjoint RAM and bounded
; INT13 services; arbitrary incoming frames, aliases and IRQ interleavings open.
ProtectedDiskEntry:
    push ax ; @0066D tf_on
    call ProtectionBufferAddressFromCall ; @0066E tf_on
ProtectionBufferAddressFromCall:
; CALL-next address discovery consumes 0671, not an ordinary child return.
; 0671+031B=098C; SI=(entry CS+0098) mod 10000, DI=000C. If low12(SI)>0FDF,
; DI+=0210 ->021C, a physical alias of CS:0B9C instead of CS:098C. Each
; selection holds 512 bytes within one DMA 64 KiB page (20-bit address wrap).
; Save this far pointer at SS:BP+0A/+0C; no permanent DS buffer is allocated.
    pop ax ; @00671 tf_on
    add ax,0x31b ; @00672 tf_on
    nop ; @00675 tf_on
    push ax ; @00676 tf_on
    mov cl,0x4 ; @00677 tf_on
    shr ax,cl ; @00679 tf_on
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @0067B tf_on
    pop di ; @0067D tf_on
    and di,byte +0xf ; @0067E tf_on
    db 0x8b,0xc6 ; ENCODED: mov ax,si (NASM chooses a different encoding) ; @00681 tf_on
    and ax,0xfff ; @00683 tf_on
    cmp ax,0xfdf ; @00686 tf_on
    jna protected_loc_068F ; @00689 tf_on
    add di,0x210 ; @0068B tf_on
protected_loc_068F:
    pop ax ; @0068F tf_on
; UNCONDITIONAL protected stack frame: SUB SP,22/MOV BP,SP reserves[BP,BP+21];all decoded BP-local stores and093A eleven-byte table save[BP+13,BP+1D] fit.0715 ADD BP,22/0719 MOV SP,BP releases it.063E contributes32 resident register/IVT bytes before066D. Known deepest protected call chain reaches50 below066D;one INT1/INT3 frame+locals adds14. With two outer near frames the identified arithmetic total is100,SP4A90 from4AF4,excluding BIOS/DOS internal use and maskable IRQs. Universal max and actual BP/SS/frame/CS:IP survival remain UNRESOLVED;0DA6/0DAE discard DOS25/26 extraFLAGS,not ordinary locals.
; UNCONDITIONAL installer ordering:00E0 protection precedes00E3 keyboard16D4 and43F8 menu08 install;game08 at0492 is later. Do not combine their maxima without an actual lifetime path. Already-installed INT24/privateIRQ and old08/providers remain stack/nesting seams.
    sub sp,byte +0x22 ; @00690 tf_on
    db 0x8b,0xec ; ENCODED: mov bp,sp (NASM chooses a different encoding) ; @00693 tf_on
    call InitializeProtectionLocalFrame ; @00695 tf_on
; 063E forces DL=0; 0786 preserves DL, so the ordinary startup caller uses
; only the BIOS floppy arm. Keep absolute read/INT26 alternatives inventoried;
; neither their CFG edges nor the skipped selector bytes prove startup writes.
    cmp dl,0x2 ; @00698 tf_on
    jnc protected_loc_06D7 ; @0069B tf_on
    mov bx,0xc02 ; @0069D tf_on
    call SaveAndPatchFloppyParameterTable ; @006A0 tf_on
    call ResetProtectionBiosDisk ; @006A3 tf_on
protected_loc_06A6:
    call ProbeProtectionFloppyPattern ; @006A6 tf_on
    jnc protected_loc_06C1 ; @006A9 tf_on
    cmp byte [bp+0x2],0xc ; @006AB tf_on
    jz protected_loc_0709 ; @006AF tf_on
    mov al,[bp+0x3] ; @006B1 tf_on
    and al,0x3 ; @006B4 tf_on
    inc al ; @006B6 tf_on
    mov [bp+0x3],al ; @006B8 tf_on
    cmp al,0x4 ; @006BB tf_on
    jnz protected_loc_06A6 ; @006BD tf_on
    jz protected_loc_0709 ; @006BF tf_on
protected_loc_06C1:
    les si,[bp+0xa] ; @006C1 tf_on
    mov ax,0x87 ; @006C4 tf_on
    call ComputeProtectionCrc16 ; @006C7 tf_on
    xchg ax,bx ; @006CA tf_on
    les si,[bp+0xa] ; @006CB tf_on
    mov ax,0x4e ; @006CE tf_on
    call ComputeProtectionCrc16 ; @006D1 tf_on
    clc ; @006D4 tf_on
    jnc protected_loc_070E ; @006D5 tf_on
protected_loc_06D7:
; S18 initial-storage reader, distinct from the DL<2 floppy prefill path:
; 0878/0883 issues INT25 without calling08CB. The helper's returned CF
; is ignored here:06DA reloads the selected pointer,08D7 reads bytes00..FD,
; and06E3 reads word+FE. If DOS leaves RAM unchanged on failure, these are
; the INITIAL stored first256 bytes (or prior-call zeros), not fresh disk data.
; Initial primary CRC90AA != EFFE;fallback0508 !=45D0, so unchanged initial
; bytes fail06E3. These are static CRC calculations, not executed disk probes.
; Startup063E forcesDL0, excluding this arm only in its ordinary caller domain.
; Its retry branch08AC does not see DOS CF transparently:0DA6 ADD SP,2
; changes arithmetic flags before INT3 reenables TF (see gate contract).
    call ReadProtectionAbsoluteSector ; @006D7 tf_on
    les si,[bp+0xa] ; @006DA tf_on
    mov ax,0xfe ; @006DD tf_on
    call ComputeProtectionCrc16 ; @006E0 tf_on
    cmp ax,[es:si] ; @006E3 tf_on
    jnz protected_loc_0709 ; @006E6 tf_on
    mov word [bp+0x20],0xffe0 ; @006E8 tf_on
    les si,[bp+0x1e] ; @006ED tf_on
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @006F0 tf_on
    mov ax,0x200 ; @006F2 tf_on
    call ComputeProtectionCrc16 ; @006F5 tf_on
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @006F8 tf_on
    les si,[bp+0xa] ; @006FA tf_on
    xor ax,[es:si+0xfa] ; @006FD tf_on
    xor bx,[es:si+0xfc] ; @00702 tf_on
    jnc protected_loc_070E ; @00707 tf_on
protected_loc_0709:
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00709 tf_on
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @0070B tf_on
    stc ; @0070D tf_on
protected_loc_070E:
; All identified body exits converge here. Preserve result FLAGS/AX across
; selected-buffer clear/table restore, recover drive DL, discard 22h locals;
; 096F disables TF and 0976 restores all 10 saved IVT words before result check.
    pushf ; @0070E tf_on
    call ClearProtectionBufferAndRestoreFloppyParameters ; @0070F tf_on
    mov dl,[bp+0x0] ; @00712 tf_on
    add bp,byte +0x22 ; @00715 tf_on
    popf ; @00718 tf_on
    db 0x8b,0xe5 ; ENCODED: mov sp,bp (NASM chooses a different encoding) ; @00719 tf_on
    jmp protected_loc_096F ; @0071B tf_on
ProbeProtectionFloppyPattern:
    mov cx,0x3 ; @0071E tf_on
protected_loc_0721:
    mov byte [bp+0x2],0x1 ; @00721 tf_on
    call ReadAndValidateProtectionSector ; @00725 tf_on
    jc protected_loc_0733 ; @00728 tf_on
    mov byte [bp+0x2],0xc ; @0072A tf_on
    call ReadAndValidateProtectionSector ; @0072E tf_on
    jnc protected_loc_0752 ; @00731 tf_on
protected_loc_0733:
    mov al,0x1 ; @00733 tf_on
    sub al,[bp+0x0] ; @00735 tf_on
    jc protected_loc_077E ; @00738 tf_on
    mov [bp+0x0],al ; @0073A tf_on
    call ResetProtectionBiosDisk ; @0073D tf_on
    mov byte [bp+0x2],0x1 ; @00740 tf_on
    call ReadAndValidateProtectionSector ; @00744 tf_on
    jc protected_loc_077E ; @00747 tf_on
    mov byte [bp+0x2],0xc ; @00749 tf_on
    call ReadAndValidateProtectionSector ; @0074D tf_on
    jc protected_loc_077E ; @00750 tf_on
protected_loc_0752:
    mov [bp+0x1e],ax ; @00752 tf_on
    mov byte [bp+0x2],0xb ; @00755 tf_on
    call ReadAndValidateProtectionSector ; @00759 tf_on
    jc protected_loc_077E ; @0075C tf_on
    add ax,[bp+0x1e] ; @0075E tf_on
    cmp ax,0x54 ; @00761 tf_on
    jnc protected_loc_0782 ; @00764 tf_on
    cmp byte [bp+0x3],0x2 ; @00766 tf_on
    jz protected_loc_0779 ; @0076A tf_on
    cmp byte [bp+0x3],0x3 ; @0076C tf_on
    jz protected_loc_0779 ; @00770 tf_on
    mov di,0xc ; @00772 tf_on
    db 0x3b,0xf8 ; ENCODED: cmp di,ax (NASM chooses a different encoding) ; @00775 tf_on
    jnc protected_loc_0782 ; @00777 tf_on
protected_loc_0779:
    dec cx ; @00779 tf_on
    jz protected_loc_077E ; @0077A tf_on
    jmp short protected_loc_0721 ; @0077C tf_on
protected_loc_077E:
    mov ax,0xffff ; @0077E tf_on
    stc ; @00781 tf_on
protected_loc_0782:
    mov [bp+0x1e],ax ; @00782 tf_on
    ret ; @00785 tf_on
InitializeProtectionLocalFrame:
; Local schema: 22h bytes at live SS:BP, allocated at 0690 for this call only.
; +00 drive, +01 head; +02 sector, +03 cylinder (word +02 -> BIOS CX).
; +04/+06 saved entry AX/BX, also low/high logical-sector words; +08 DOS
; sector count; +0A/+0C selected buffer offset/segment; +0E service selector.
; +0F/+11 unaligned saved INT1E far pointer; +13..+1D its 11 saved bytes.
; +1E scratch count/result; +20 scratch segment (0, later FFE0 on absolute arm).
; Not a zeroed struct: +1E is read by LES before initialization, but ES=0
; from +20, and tick read is constant ES:046C, ignoring the loaded SI value.
; CX=9299 bypasses tick read and uses input DH; initial head=bit0, cylinder=bit2.
; Default BP operands use SS even when LDS in an absolute arm changes DS.
    mov [bp+0x4],ax ; @00786 tf_on
    mov [bp+0x6],bx ; @00789 tf_on
    mov [bp+0x0],dl ; @0078C tf_on
    mov [bp+0xa],di ; @0078F tf_on
    mov [bp+0xc],si ; @00792 tf_on
    mov word [bp+0x20],0x0 ; @00795 tf_on
    cmp cx,0x9299 ; @0079A tf_on
    jz protected_loc_07A8 ; @0079E tf_on
    les bx,[bp+0x1e] ; @007A0 tf_on
    mov dh,[es:0x46c] ; @007A3 tf_on
protected_loc_07A8:
    push dx ; @007A8 tf_on
    and dh,0x4 ; @007A9 tf_on
    mov [bp+0x3],dh ; @007AC tf_on
    pop dx ; @007AF tf_on
    and dh,0x1 ; @007B0 tf_on
    mov [bp+0x1],dh ; @007B3 tf_on
    ret ; @007B6 tf_on
ReadAndValidateProtectionSector:
; Three-attempt sector/signature worker: fill whole buffer with word 1234,
; then BIOS read. AH=80 fails immediately; sector 1 requires AH=0, but other
; sectors inspect the live bytes despite other BIOS error results. +38/+39
; XOR cylinder/head and +3C gets 33BC before CRC checks; all are buffer writes.
    push cx ; @007B7 tf_on
    mov cx,0x3 ; @007B8 tf_on
protected_loc_07BB:
    mov ax,0x1234 ; @007BB tf_on
    call FillProtectionSectorBuffer ; @007BE tf_on
    call ReadProtectionBiosSector ; @007C1 tf_on
    cmp ah,0x80 ; @007C4 tf_on
    jz protected_loc_0844 ; @007C7 tf_on
    cmp byte [bp+0x2],0x1 ; @007C9 tf_on
    jnz protected_loc_07D5 ; @007CD tf_on
    db 0x0a,0xe4 ; ENCODED: or ah,ah (NASM chooses a different encoding) ; @007CF tf_on
    jz protected_loc_0845 ; @007D1 tf_on
    jnz protected_loc_083B ; @007D3 tf_on
protected_loc_07D5:
    les si,[bp+0xa] ; @007D5 tf_on
    mov di,0xd597 ; @007D8 tf_on
    mov ax,0x20 ; @007DB tf_on
    cmp byte [bp+0x2],0xc ; @007DE tf_on
    jz protected_loc_0814 ; @007E2 tf_on
    mov al,[bp+0x3] ; @007E4 tf_on
    xor [es:si+0x38],al ; @007E7 tf_on
    jnz protected_loc_083B ; @007EB tf_on
    mov al,[bp+0x1] ; @007ED tf_on
    xor [es:si+0x39],al ; @007F0 tf_on
    jnz protected_loc_083B ; @007F4 tf_on
    mov ax,0x33bc ; @007F6 tf_on
    mov [es:si+0x3c],ax ; @007F9 tf_on
    mov ax,0x46 ; @007FD tf_on
    call ComputeProtectionCrc16 ; @00800 tf_on
    cmp ax,0x6e62 ; @00803 tf_on
    jnz protected_loc_083B ; @00806 tf_on
    les si,[bp+0xa] ; @00808 tf_on
    add si,byte +0x4e ; @0080B tf_on
    mov di,0xbf60 ; @0080E tf_on
    mov ax,0x39 ; @00811 tf_on
protected_loc_0814:
    call ComputeProtectionCrc16 ; @00814 tf_on
    db 0x3b,0xc7 ; ENCODED: cmp ax,di (NASM chooses a different encoding) ; @00817 tf_on
    jnz protected_loc_083B ; @00819 tf_on
    les si,[bp+0xa] ; @0081B tf_on
    cmp byte [bp+0x2],0xc ; @0081E tf_on
    jz protected_loc_0827 ; @00822 tf_on
    add si,byte +0x66 ; @00824 tf_on
protected_loc_0827:
    mov ax,0x28 ; @00827 tf_on
    sub al,[bp+0x3] ; @0082A tf_on
    add al,[bp+0x1] ; @0082D tf_on
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @00830 tf_on
    mov ax,0x6 ; @00832 tf_on
    call CountProtectionSetBits ; @00835 tf_on
    clc ; @00838 tf_on
    jnc protected_loc_0845 ; @00839 tf_on
protected_loc_083B:
    call ResetProtectionBiosDisk ; @0083B tf_on
    dec cx ; @0083E tf_on
    jz protected_loc_0844 ; @0083F tf_on
    jmp protected_loc_07BB ; @00841 tf_on
protected_loc_0844:
    stc ; @00844 tf_on
protected_loc_0845:
    pop cx ; @00845 tf_on
    ret ; @00846 tf_on
ReadProtectionBiosSector:
; Producer sets BIOS function +0E=02; 084B jumps over five stored bytes.
; Only CX/BP are saved around INT13. Read uses AX=0201, ES:BX=buffer,
; CX=sector/cylinder and DX=drive/head. Other returned registers/flags are live.
    mov byte [bp+0xe],0x2 ; @00847 tf_on
    jmp short protected_loc_0852 ; @0084B tf_on
; 084D..0851 is skipped, not proved padding or a BIOS-write entry. Decoder
; for 0852 reads word 0850..0851=030E; decoding 0853 also reads byte 0851.
; Thus 0850..0851 have a key-data role; 084D..084F have no specific role
; proved by this path. Keep all five canonical UNKNOWN and any code role open.
; S18 alternate-state candidate: applying the actual first-word transform at
; 084D exposes90 (NOP); after restoration,084E exposesC6460E03, MOV byte
; [SS:BP+0E],03, then falls into0852. Thus the first three bytes have a
; coherent encoded BIOS-write-selector interpretation using the SAME decoder,
; not an alternate key algorithm. Neither084B nor any recovered edge enters
; 084D/084E. This proves a candidate spelling, not a reachable write service;
; leave UNKNOWN. Its immediate/key bytes0850/0851 have overlapping roles.
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x7e,0xc5,0x44,0x0e,0x03 ; @0084D
protected_loc_0852:
    push cx ; @00852 tf_on
    mov cx,0x3 ; @00853 tf_on
protected_loc_0856:
    push cx ; @00856 tf_on
    push bp ; @00857 tf_on
    mov al,0x1 ; @00858 tf_on
    mov ah,[bp+0xe] ; @0085A tf_on
    les bx,[bp+0xa] ; @0085D tf_on
    mov cx,[bp+0x2] ; @00860 tf_on
    mov dx,[bp+0x0] ; @00863 tf_on
    call ProtectionBiosInt13Gate ; @00866 tf_on
    pop bp ; @00869 tf_on
    pop cx ; @0086A tf_on
    jnc protected_loc_0876 ; @0086B tf_on
    cmp byte [bp+0xe],0x2 ; @0086D tf_on
    stc ; @00871 tf_on
    jz protected_loc_0876 ; @00872 tf_on
    loop protected_loc_0856 ; @00874 tf_on
protected_loc_0876:
    pop cx ; @00876 tf_on
    ret ; @00877 tf_on
ReadProtectionAbsoluteSector:
; Absolute read producer +0E=25; skipped 087E..0882 does not prove a reachable
; +0E=26 write producer. With saved BX!=FFFF, DS:BX=SS:(BP+04), CX=FFFF
; supplies 32-bit sector/count/buffer packet; BX=FFFF selects legacy buffer
; DS:BX,CX=1,DX=entry AX. Keep the TF-off DOS extra-FLAGS transport below.
    mov byte [bp+0xe],0x25 ; @00878 tf_on
    jmp short protected_loc_0883 ; @0087C tf_on
; 087E..0882 is skipped. Decoder for 0883 reads word 0881..0882=260E;
; decoding 0884 also reads byte 0882. Last two bytes have a key-data role;
; first three remain unexplained. No direct entry or runtime writer is proved.
; S18 same-rule candidate:087E ->90 NOP,087F ->C6460E26 MOV byte
; [SS:BP+0E],26, then0883. Selector26 already has a real consumer08B2
; and TF-off INT26 gate0DAC, but no recovered entry supplies this candidate
; producer. Preserve UNKNOWN and the conditional absolute-write alternative;
; raw linear decoding alone does not expose this interpretation.
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x7e,0x59,0x44,0x0e,0x26 ; @0087E
protected_loc_0883:
    push cx ; @00883 tf_on
    mov cx,0x3 ; @00884 tf_on
protected_loc_0887:
    push cx ; @00887 tf_on
    push bp ; @00888 tf_on
    mov al,[bp+0x0] ; @00889 tf_on
    mov word [bp+0x8],0x1 ; @0088C tf_on
    db 0x8b,0xdd ; ENCODED: mov bx,bp (NASM chooses a different encoding) ; @00891 tf_on
    add bx,byte +0x4 ; @00893 tf_on
    mov cx,0xffff ; @00896 tf_on
    cmp [bp+0x6],cx ; @00899 tf_on
    jnz protected_loc_08A7 ; @0089C tf_on
    lds bx,[bp+0xa] ; @0089E tf_on
    mov cx,0x1 ; @008A1 tf_on
    mov dx,[bp+0x4] ; @008A4 tf_on
protected_loc_08A7:
    call DispatchProtectionAbsoluteDiskService ; @008A7 tf_on
    pop bp ; @008AA tf_on
    pop cx ; @008AB tf_on
    jnc protected_loc_08B0 ; @008AC tf_on
    loop protected_loc_0887 ; @008AE tf_on
protected_loc_08B0:
    pop cx ; @008B0 tf_on
    ret ; @008B1 tf_on
DispatchProtectionAbsoluteDiskService:
; Selector==26 dispatches INT26, everything else INT25. Known entry 0878
; writes 25; no identified startup producer supplies 26. Retain both gates.
    cmp byte [bp+0xe],0x26 ; @008B2 tf_on
    jz protected_loc_08BB ; @008B6 tf_on
    jmp protected_loc_0DA3 ; @008B8 tf_on
protected_loc_08BB:
    jmp protected_loc_0DAB ; @008BB tf_on
ResetProtectionBiosDisk:
; Reset quirk: load frame.drive into AL, not DL, before AH=00 INT13. The
; actual BIOS reset drive is live DL, which prior arithmetic/services can alter.
    push cx ; @008BE tf_on
    push bp ; @008BF tf_on
    mov al,[bp+0x0] ; @008C0 tf_on
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @008C3 tf_on
    call ProtectionBiosInt13Gate ; @008C5 tf_on
    pop bp ; @008C8 tf_on
    pop cx ; @008C9 tf_on
    ret ; @008CA tf_on
FillProtectionSectorBuffer:
; Whole selected-buffer writer: AX word -> 0100 forward words at +0A/+0C.
; CLD persists after RET; CX restored, ES/DI follow LES and STOSW. Exactly
; 098C..0B8B OR 0B9C..0D9B in the ordinary pointer domain, never gap or seed.
    push cx ; @008CB tf_on
    les di,[bp+0xa] ; @008CC tf_on
    mov cx,0x100 ; @008CF tf_on
; R1 UNCONDITIONAL TF-on helper result:08CB fill clears DF before08D3 REP STOSW and
; returns0. This is not a protection-wide CLD:094A saves entry FLAGS,096D POPF restores
; them after fill;070E/0718 and0970..0982 also preserve their live saved DF. Service-returned
; DF and actual protected/root composition remain unresolved without their explicit domain.
    cld ; @008D2 tf_on
    rep stosw ; @008D3 tf_on
    pop cx ; @008D5 tf_on
    ret ; @008D6 tf_on
ComputeProtectionCrc16:
; CRC-16, initial 0EDC, MSB-first polynomial 1021 (XOR0810,STC,RCL form).
; AX input byte count -> DX; read ES:SI, INC SI modulo 10000 (independent of
; DF), return AX CRC, DX=0, advanced SI; BX/CX saved. Count 0 wraps to 65536
; reads, not empty input. Callers here supply explicit positive lengths.
    push bx ; @008D7 tf_on
    push cx ; @008D8 tf_on
    xchg ax,dx ; @008D9 tf_on
    mov ax,0xedc ; @008DA tf_on
protected_loc_08DD:
    mov bh,[es:si] ; @008DD tf_on
    inc si ; @008E0 tf_on
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @008E1 tf_on
    db 0x33,0xc3 ; ENCODED: xor ax,bx (NASM chooses a different encoding) ; @008E3 tf_on
    mov cx,0x8 ; @008E5 tf_on
protected_loc_08E8:
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @008E8 tf_on
    rcl bx,1 ; @008EA tf_on
    jnc protected_loc_08F2 ; @008EC tf_on
    xor ax,0x810 ; @008EE tf_on
    stc ; @008F1 tf_on
protected_loc_08F2:
    rcl ax,1 ; @008F2 tf_on
    loop protected_loc_08E8 ; @008F4 tf_on
    dec dx ; @008F6 tf_on
    jnz protected_loc_08DD ; @008F7 tf_on
    pop cx ; @008F9 tf_on
    pop bx ; @008FA tf_on
    ret ; @008FB tf_on
CountProtectionSetBits:
; Count set bits in AX bytes at ES:SI, with INC SI rather than a DF string.
; Return AX count modulo 10000, DX=0, SI advanced; CX saved, BL destroyed.
; Input count 0 performs 65536 reads. Known signature calls supply 6 bytes.
    push cx ; @008FC tf_on
    xchg ax,dx ; @008FD tf_on
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @008FE tf_on
protected_loc_0900:
    mov bl,[es:si] ; @00900 tf_on
    inc si ; @00903 tf_on
    mov cx,0x8 ; @00904 tf_on
protected_loc_0907:
    rcl bl,1 ; @00907 tf_on
    jnc protected_loc_090C ; @00909 tf_on
    inc ax ; @0090B tf_on
protected_loc_090C:
    loop protected_loc_0907 ; @0090C tf_on
    dec dx ; @0090E tf_on
    jnz protected_loc_0900 ; @0090F tf_on
    pop cx ; @00911 tf_on
    ret ; @00912 tf_on
SaveAndPatchFloppyParameterTable:
; Drive<2 saves vector INT1E's far table pointer and 11 table bytes, then
; writes BX at table+3 (normal BX=0C02). INT1E vector itself is not changed.
; Copies use explicit INC, independent of DF; table/stack aliases remain live.
    cmp byte [bp+0x0],0x2 ; @00913 tf_on
    jnc protected_loc_0949 ; @00917 tf_on
    mov word [bp+0x20],0x0 ; @00919 tf_on
    les si,[bp+0x1e] ; @0091E tf_on
    mov ax,[es:0x78] ; @00921 tf_on
    mov [bp+0xf],ax ; @00925 tf_on
    mov ax,[es:0x7a] ; @00928 tf_on
    mov [bp+0x11],ax ; @0092C tf_on
    les si,[bp+0xf] ; @0092F tf_on
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @00932 tf_on
    mov cx,0xb ; @00934 tf_on
protected_loc_0937:
    mov al,[es:si] ; @00937 tf_on
    mov [ss:di+0x13],al ; @0093A tf_on
    inc si ; @0093E tf_on
    inc di ; @0093F tf_on
    loop protected_loc_0937 ; @00940 tf_on
    les si,[bp+0xf] ; @00942 tf_on
    mov [es:si+0x3],bx ; @00945 tf_on
protected_loc_0949:
    ret ; @00949 tf_on
ClearProtectionBufferAndRestoreFloppyParameters:
; On every identified body exit, zero all 512 selected bytes and, drive<2,
; restore the saved 11-byte floppy table. Preserve AX/FLAGS, not the transient
; code/vector/stack traffic. Buffer stays zero after the ordinary completed call.
    pushf ; @0094A tf_on
    push ax ; @0094B tf_on
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0094C tf_on
    call FillProtectionSectorBuffer ; @0094E tf_on
    cmp byte [bp+0x0],0x2 ; @00951 tf_on
    jnc protected_loc_096C ; @00955 tf_on
    les si,[bp+0xf] ; @00957 tf_on
    db 0x8b,0xfd ; ENCODED: mov di,bp (NASM chooses a different encoding) ; @0095A tf_on
    push cx ; @0095C tf_on
    mov cx,0xb ; @0095D tf_on
protected_loc_0960:
    mov al,[ss:di+0x13] ; @00960 tf_on
    mov [es:si],al ; @00964 tf_on
    inc si ; @00967 tf_on
    inc di ; @00968 tf_on
    loop protected_loc_0960 ; @00969 tf_on
    pop cx ; @0096B tf_on
protected_loc_096C:
    pop ax ; @0096C tf_on
    popf ; @0096D tf_on
    ret ; @0096E tf_on
protected_loc_096F:
; INT3 toggles TF off/IF back and re-encodes INT1. 0970..0988 uses raw bytes,
; restoring IVT0..4 and saved registers; JMP0989 bypasses all storage to 0E3A.
    int3 ; @0096F tf_on
protected_loc_0970:
    pushf ; @00970 tf_off
    pop cx ; @00971 tf_off
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @00972 tf_off
    mov ds,si ; @00974 tf_off
protected_loc_0976:
    pop word [si+0x12] ; @00976 tf_off
    sub si,byte +0x2 ; @00979 tf_off
    cmp si,byte -0x14 ; @0097C tf_off
    jnz protected_loc_0976 ; @0097F tf_off
    push cx ; @00981 tf_off
    popf ; @00982 tf_off
    pop bp ; @00983 tf_off
    pop di ; @00984 tf_off
    pop si ; @00985 tf_off
    pop cx ; @00986 tf_off
    pop es ; @00987 tf_off
    pop ds ; @00988 tf_off
    jmp protected_loc_0E3A ; @00989 tf_off
; No instruction in this graph lies in 098C..0D9D. Runtime overlay inventory:
; 098C..0B8B primary512; 0B8C..0B9B unknown16; 0B9C..0D9B fallback512;
; 0D9C..0D9D decode seed2. Fills/read/validation/clear prove the buffer role,
; not initial stored meaning or global absence of code. Canonical UNKNOWN stays.
; S18 stored-role boundary: INT3 negates ONLY0DFF..0E39, not this run; INT1
; restores IVT0's previous word and patches the live interrupted far CS:IP.
; It has no separate seed/cursor stream that linearly decrypts098C..0D9B.
; JMP0989 executes with TF off and bypasses all1040 bytes, including the16
; between the two buffers. No recovered main/protected edge or relocation
; enters them. These negatives do not exclude other frames/aliases/entries.
; Floppy07BE fills1234 before read/validation; absolute06D7 instead consumes
; initial first256 bytes on unchanged failed reads (see06D7). Cleanup094A
; zeros selected512 only. Unselected512 and gap16 retain their entry contents.
; Checksum8363, if invoked through its reset/advance lifetime, reads every
; byte here and both084D/087E gaps as CS data at8397; no static caller to8363
; is known. Startup8343 reads188F..1898 only. Checksum coverage does not
; classify the protected stored run or prove that it was initialized as code.
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xb5,0xa2,0x6b,0x88,0xd7,0x53,0xae,0xea,0x5c,0x18,0xb9,0x73,0x72,0x2a,0xe4,0x97 ; @0098C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xc9,0x72,0x92,0x28,0x24,0x94,0x49,0x6b,0x93,0x19,0x26,0x76,0x4d,0x2f,0x9a,0xa1 ; @0099C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x34,0x86,0x68,0x4f,0xd1,0xe1,0xa3,0x06,0x47,0x50,0x8e,0xe3,0x1c,0x0a,0x38,0x57 ; @009AC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x71,0xf1,0xe2,0x25,0xc4,0x8e,0x89,0x60,0x13,0x04,0x27,0x4b,0x4f,0xd9,0x9e,0xf5 ; @009BC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x3d,0x2e,0x7b,0x9f,0xf7,0x81,0xef,0x46,0xdf,0xd0,0xbe,0xe4,0x7c,0x0c,0xf8,0x5b ; @009CC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xf1,0xfa,0xe2,0x38,0xc5,0xb4,0x8a,0xac,0x14,0x9c,0x29,0x7b,0x52,0x39,0xa5,0xb5 ; @009DC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x4a,0xae,0x94,0x9f,0x28,0x82,0x50,0x47,0xa0,0xd1,0x41,0xe6,0x83,0x0f,0x06,0x62 ; @009EC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x0c,0x07,0x18,0x51,0x31,0xe5,0x63,0x0d,0xc7,0x5d,0x8e,0xfe,0x1c,0x40,0x38,0xc3 ; @009FC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x70,0xc9,0xe0,0xd5,0xc1,0xee,0x82,0x20,0x04,0x84,0x08,0x4b,0x10,0xd9,0x21,0xf5 ; @00A0C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x42,0x2d,0x84,0x9d,0x09,0x7e,0x12,0x3f,0x24,0xc1,0x48,0xc5,0x90,0xcd,0x20,0xde ; @00A1C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x41,0xff,0x83,0x41,0x07,0xc6,0x0f,0xcf,0x1e,0xe1,0x3c,0x05,0x78,0x4d,0xf0,0xdd ; @00A2C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xe1,0xfe,0xc3,0x40,0x87,0xc4,0x0f,0xcc,0x1f,0xdb,0x3e,0xf9,0x7d,0x35,0xfa,0xad ; @00A3C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xf4,0x9e,0xe8,0x80,0xd0,0x44,0xa0,0xcc,0x40,0xdc,0x81,0xfb,0x02,0x3a,0x05,0xb7 ; @00A4C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x0a,0xb1,0x15,0xa5,0x2b,0x8d,0x57,0x5d,0xae,0xfd,0x5d,0x3e,0xba,0xbf,0x74,0xc2 ; @00A5C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xe8,0xc7,0xd0,0xd2,0xa1,0xe8,0x43,0x14,0x86,0x6b,0x0c,0x1a,0x19,0x77,0x32,0x31 ; @00A6C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x65,0xa5,0xcb,0x8d,0x97,0x5e,0x2f,0x00,0x5f,0x43,0xbf,0xc9,0x7f,0xd6,0xfe,0xef ; @00A7C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xfd,0x22,0xfb,0x88,0xf7,0x54,0xee,0xec,0xdc,0x1c,0xb9,0x7c,0x72,0x3c,0xe5,0xbb ; @00A8C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xca,0xba,0x95,0xb8,0x2a,0xb4,0x55,0xab,0xab,0x99,0x56,0x76,0xad,0x2f,0x5a,0xa2 ; @00A9C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xb4,0x87,0x68,0x52,0xd1,0xe7,0xa3,0x12,0x46,0x68,0x8c,0x13,0x19,0x6a,0x33,0x17 ; @00AAC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x66,0x71,0xcd,0x25,0x9b,0x8e,0x36,0x60,0x6c,0x03,0xd8,0x49,0xb0,0xd6,0x61,0xf0 ; @00ABC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xc2,0x23,0x84,0x8a,0x08,0x58,0x11,0xf3,0x22,0x29,0x44,0x95,0x89,0x6d,0x13,0x1e ; @00ACC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x26,0x7f,0x4c,0x41,0x98,0xc5,0x30,0xce,0x60,0xdf,0xc0,0x01,0x80,0x46,0x00,0xd0 ; @00ADC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x01,0xe3,0x03,0x09,0x07,0x55,0x0e,0xed,0x1c,0x1d,0x39,0x7d,0x72,0x3d,0xe5,0xbd ; @00AEC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xca,0xbe,0x94,0xc0,0x28,0xc4,0x50,0xcb,0xa0,0xd9,0x41,0xf6,0x82,0x2f,0x05,0xa2 ; @00AFC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x0b,0x87,0x17,0x51,0x2e,0xe5,0x5c,0x0d,0xb8,0x5d,0x71,0xfe,0xe2,0x3f,0xc4,0xc2 ; @00B0C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x88,0xc8,0x10,0xd4,0x21,0xeb,0x43,0x19,0x86,0x75,0x0d,0x2e,0x1b,0x9f,0x37,0x81 ; @00B1C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x6f,0x45,0xdf,0xcd,0xbf,0xde,0x7f,0x00,0xff,0x43,0xff,0xca,0xff,0xd8,0xfe,0xf4 ; @00B2C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xfd,0x2c,0xfb,0x9c,0xf6,0x7c,0xed,0x3c,0xda,0xbc,0xb5,0xbc,0x6a,0xbc,0xd5,0xbb ; @00B3C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xaa,0xba,0x55,0xb8,0xaa,0xb3,0x55,0xaa,0xab,0x97,0x56,0x72,0xad,0x27,0x5b,0x92 ; @00B4C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xb6,0x67,0x6c,0x12,0xd9,0x67,0xb3,0x12,0x66,0x68,0xcc,0x13,0x99,0x6a,0x33,0x18 ; @00B5C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x66,0x73,0xcd,0x29,0x9b,0x96,0x36,0x70,0x6d,0x23,0xdb,0x89,0xb7,0x56,0x6e,0xf0 ; @00B6C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xdd,0x23,0xbb,0x8a,0x77,0x58,0xee,0xf3,0xdd,0x2a,0xbb,0x98,0x76,0x74,0xed,0x2b ; @00B7C
; Outside both 512-byte windows; no protection-specific role for these 16 bytes.
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xdb,0x9a,0xb6,0x78,0x6d,0x34,0xda,0xab,0xb4,0x9a,0x69,0x78,0xd2,0x33,0xa5,0xaa ; @00B8C
; Alternative buffer selection; unselected bytes retain their entry contents
; in the disjoint call domain.
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x4b,0x98,0x96,0x73,0x2d,0x2a,0x5b,0x97,0xb6,0x71,0x6d,0x26,0xdb,0x8f,0xb6,0x62 ; @00B9C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x6c,0x08,0xd8,0x53,0xb1,0xea,0x63,0x18,0xc6,0x73,0x8d,0x2a,0x1b,0x98,0x36,0x73 ; @00BAC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x6d,0x29,0xdb,0x95,0xb6,0x6e,0x6d,0x20,0xdb,0x83,0xb7,0x4a,0x6f,0xd8,0xde,0xf3 ; @00BBC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xbd,0x2a,0x7b,0x98,0xf6,0x73,0xed,0x2a,0xdb,0x98,0xb6,0x74,0x6d,0x2c,0xdb,0x9b ; @00BCC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xb6,0x7a,0x6d,0x38,0xda,0xb3,0xb5,0xaa,0x6b,0x98,0xd6,0x73,0xad,0x2a,0x5b,0x98 ; @00BDC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xb6,0x73,0x6d,0x2a,0xdb,0x97,0xb6,0x72,0x6d,0x28,0xdb,0x93,0xb6,0x6a,0x6c,0x18 ; @00BEC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xd9,0x73,0xb2,0x2a,0x64,0x98,0xc9,0x73,0x92,0x2a,0x24,0x98,0x49,0x73,0x92,0x29 ; @00BFC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x24,0x96,0x49,0x6f,0x92,0x21,0x24,0x86,0x48,0x4f,0x91,0xe1,0x23,0x06,0x47,0x4f ; @00C0C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x8e,0xe1,0x1c,0x06,0x38,0x4f,0x71,0xe1,0xe3,0x05,0xc7,0x4e,0x8e,0xe0,0x1c,0x04 ; @00C1C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x38,0x4b,0x70,0xd9,0xe1,0xf5,0xc2,0x2e,0x85,0xa0,0x0b,0x84,0x17,0x4b,0x2f,0xd9 ; @00C2C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x5e,0xf5,0xbd,0x2d,0x7b,0x9e,0xf6,0x7f,0xec,0x42,0xd8,0xc8,0xb0,0xd4,0x61,0xec ; @00C3C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xc3,0x1b,0x86,0x7a,0x0d,0x38,0x1a,0xb3,0x35,0xa9,0x6b,0x95,0xd6,0x6d,0xac,0x1e ; @00C4C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x58,0x80,0xb0,0x43,0x60,0xca,0xc0,0xd7,0x81,0xf2,0x02,0x28,0x04,0x93,0x09,0x69 ; @00C5C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x13,0x15,0x26,0x6d,0x4c,0x1d,0x99,0x7d,0x32,0x3e,0x65,0xbf,0xcb,0xc1,0x97,0xc6 ; @00C6C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x2f,0xd0,0x5e,0xe3,0xbc,0x09,0x78,0x56,0xf1,0xef,0xe2,0x22,0xc4,0x88,0x88,0x54 ; @00C7C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x11,0xec,0x23,0x1b,0x46,0x79,0x8d,0x35,0x1a,0xae,0x34,0x9f,0x68,0x81,0xd0,0x45 ; @00C8C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xa0,0xce,0x41,0xe0,0x83,0x03,0x07,0x4a,0x0f,0xd7,0x1e,0xf1,0x3d,0x25,0x7b,0x8d ; @00C9C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xf7,0x5d,0xee,0xfe,0xdc,0x40,0xb8,0xc4,0x70,0xcc,0xe0,0xdb,0xc1,0xfa,0x82,0x38 ; @00CAC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x05,0xb4,0x0a,0xab,0x14,0x99,0x29,0x75,0x52,0x2d,0xa4,0x9d,0x49,0x7e,0x92,0x3f ; @00CBC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x24,0xc2,0x48,0xc7,0x90,0xd1,0x21,0xe6,0x43,0x0f,0x86,0x61,0x0c,0x06,0x18,0x4f ; @00CCC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x31,0xe1,0x63,0x05,0xc7,0x4d,0x8f,0xde,0x1f,0x00,0x3f,0x43,0x7f,0xc9,0xff,0xd5 ; @00CDC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xfe,0xee,0xfd,0x20,0xfb,0x84,0xf7,0x4c,0xef,0xdc,0xde,0xfc,0xbd,0x3c,0x7a,0xbc ; @00CEC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xf5,0xbb,0xea,0xba,0xd5,0xb8,0xaa,0xb4,0x55,0xac,0xab,0x9b,0x56,0x7a,0xad,0x37 ; @00CFC
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x5a,0xb2,0xb5,0xa7,0x6b,0x92,0xd6,0x67,0xac,0x12,0x59,0x68,0xb3,0x13,0x66,0x6a ; @00D0C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xcc,0x17,0x99,0x72,0x32,0x28,0x64,0x93,0xc9,0x69,0x93,0x16,0x26,0x70,0x4d,0x23 ; @00D1C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x9b,0x89,0x37,0x56,0x6e,0xef,0xdd,0x21,0xbb,0x86,0x77,0x50,0xee,0xe3,0xdc,0x0a ; @00D2C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xb8,0x58,0x71,0xf4,0xe2,0x2b,0xc4,0x9a,0x89,0x78,0x12,0x34,0x25,0xab,0x4b,0x99 ; @00D3C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x96,0x75,0x2d,0x2e,0x5b,0x9f,0xb7,0x81,0x6f,0x46,0xdf,0xcf,0xbe,0xe2,0x7c,0x08 ; @00D4C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xf8,0x53,0xf1,0xea,0xe3,0x18,0xc6,0x74,0x8d,0x2c,0x1b,0x9c,0x36,0x7b,0x6d,0x39 ; @00D5C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0xda,0xb5,0xb5,0xae,0x6a,0xa0,0xd4,0x83,0xa8,0x4a,0x50,0xd8,0xa1,0xf3,0x42,0x2a ; @00D6C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x84,0x97,0x09,0x72,0x12,0x27,0x24,0x91,0x49,0x65,0x93,0x0d,0x27,0x5e,0x4e,0xff ; @00D7C
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x9c,0x41,0x38,0xc6,0x70,0xcf,0xe1,0xe1,0xc3,0x06,0x87,0x50,0x0e,0xe4,0x1c,0x0b ; @00D8C
; Retained key word 9090: int1 0E20 at nextIP0D9E reads it, yielding keyDEDE
; and visible word13CC from storedCD12. Both buffer windows end before it.
; Known data use, not executed NOPs; alternate interpretation still unresolved.
; UNKNOWN: stored bytes outside the derived instruction graph
    db 0x90,0x90 ; @00D9C
ProtectionBiosInt13Gate:
; TF-on INT3 -> TF-off INT13 -> raw INT3 -> TF-on RET. Paired INT3s toggle
; saved IF with TF; service must return TF clear with explicit register/FLAGS,
; segment and memory effects. This gate does not invent a successful read.
    int3 ; @00D9E tf_on
protected_loc_0D9F:
    int 0x13 ; @00D9F tf_off
    int3 ; @00DA1 tf_off
protected_loc_0DA2:
    ret ; @00DA2 tf_on
protected_loc_0DA3:
; TF-off INT25 returns an extra FLAGS word on the stack; ADD SP,2 discards it
; and changes arithmetic FLAGS including CF. Preserve 16-bit SP wrap. Then
; raw INT3 enables TF before RET; DOS carry is not transparently propagated.
    int3 ; @00DA3 tf_on
protected_loc_0DA4:
    int 0x25 ; @00DA4 tf_off
    add sp,byte +0x2 ; @00DA6 tf_off
    int3 ; @00DA9 tf_off
protected_loc_0DAA:
    ret ; @00DAA tf_on
protected_loc_0DAB:
; Same extra-FLAGS/ADD/INT3 transport for INT26. Decoded alternative retained;
; no ordinary startup write request follows merely from this gate's existence.
    int3 ; @00DAB tf_on
protected_loc_0DAC:
    int 0x26 ; @00DAC tf_off
    add sp,byte +0x2 ; @00DAE tf_off
    int3 ; @00DB1 tf_off
protected_loc_0DB2:
    ret ; @00DB2 tf_on
; STORED: outside this execution view; canonical instruction
    db 0x50,0x56,0x1e,0x33,0xc0,0x8e,0xd8,0xe8,0x00,0x00,0x8f,0x06,0x04,0x00,0x81,0x06 ; @00DB3
; STORED: outside this execution view; canonical instruction
    db 0x04,0x00,0x42,0x00,0x0e,0x8f,0x06,0x06,0x00,0x8b,0x36,0x04,0x00,0xb8,0x3b,0x00 ; @00DC3
; STORED: outside this execution view; canonical instruction
    db 0x2e,0xf6,0x1c,0x46,0x48,0x75,0xf9,0x8b,0xf4,0x36,0x80,0x74,0x0b,0x03,0x36,0xf6 ; @00DD3
; STORED: outside this execution view; canonical instruction
    db 0x44,0x0b,0x01,0x75,0x34,0xc5,0x36,0x00,0x00,0x8b,0x44,0xfe,0xf7,0xd0,0xd1,0xc0 ; @00DE3
; STORED: outside this execution view; canonical instruction
    db 0x33,0x04,0x3c,0xcc,0x74,0x02,0x87,0x04,0x1f,0x5e,0x58,0xcf ; @00DF3
; STORED: outside this execution view; canonical runtime_modified_code
    db 0x05,0xb0,0xaa,0xe2,0xcd,0x40,0x72,0x28,0x3b,0xca,0x00,0x00,0x75,0xbc,0x02,0x09 ; @00DFF
; STORED: outside this execution view; canonical runtime_modified_code
    db 0x30,0x2f,0x40,0xcd,0xfc,0x79,0xfc,0xc4,0x34,0x8c,0xe4,0x75,0x0c,0xca,0x3b,0x8c ; @00E0F
; STORED: outside this execution view; canonical runtime_modified_code
    db 0xfa,0x75,0xbc,0x02,0x09,0x30,0x2f,0x40,0xcf,0xfc,0xe2,0xcd,0x40,0x72,0x28,0x77 ; @00E1F
; STORED: outside this execution view; canonical runtime_modified_code
    db 0xca,0x00,0x00,0x71,0xfa,0xfe,0x00,0xe1,0xa2,0xa8,0x31 ; @00E2F
protected_loc_0E3A:
; Raw TF-off admission tail: existing CF failure returns unchanged; otherwise
; accept exactly AX/BX=(581C,A9F2),(D950,270A),(9CF8,1A8C), clearing CF.
; Mismatch sets CF. Other arithmetic flags come from the actual final CMP;
; no pass latch is stored. RET uses the original 063E caller's live near word.
    jnc protected_loc_0E3D ; @00E3A tf_off
    ret ; @00E3C tf_off
protected_loc_0E3D:
    cmp ax,0x581c ; @00E3D tf_off
    jnz protected_loc_0E4A ; @00E40 tf_off
    cmp bx,0xa9f2 ; @00E42 tf_off
    jnz protected_loc_0E4A ; @00E46 tf_off
    clc ; @00E48 tf_off
    ret ; @00E49 tf_off
protected_loc_0E4A:
    cmp ax,0xd950 ; @00E4A tf_off
    jnz protected_loc_0E57 ; @00E4D tf_off
    cmp bx,0x270a ; @00E4F tf_off
    jnz protected_loc_0E57 ; @00E53 tf_off
    clc ; @00E55 tf_off
    ret ; @00E56 tf_off
protected_loc_0E57:
    cmp ax,0x9cf8 ; @00E57 tf_off
    jnz protected_loc_0E64 ; @00E5A tf_off
    cmp bx,0x1a8c ; @00E5C tf_off
    jnz protected_loc_0E64 ; @00E60 tf_off
    clc ; @00E62 tf_off
    ret ; @00E63 tf_off
protected_loc_0E64:
    stc ; @00E64 tf_off
    ret ; @00E65 tf_off
