times -(($-$$) != 0x18b2) db 0
SendMasterPicEoi:
; MOV AL,20; byte OUT20 preserves AH/FLAGS, then actual live near RET.
; docs/port-io.md; no IRQ/PIC scheduling or hardware status is invented.
    mov al,0x20 ; @018B2
MasterPicEoiOut18B4:
    out 0x20,al ; @018B4
MasterPicEoiReturn18B6:
    ret ; @018B6
; S14 U016: [018B7,018F8) stored bytes remain UNKNOWN.
; Neighbours: P 018B6 ret; N 018F8 sti.
; Candidate PIC helper18B7: command0B/read20,TEST7F; nonzero sends master EOI20 at18ED. Otherwise sends slaveA0 EOI20,command0B/readA0; nonzero skips master EOI, zero sends master20. EB00 branches are internal candidate delays. No STI/CLI/data store; AL/flags clobber. Hardware contract and incoming entry unproved.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0xb0,0x0b,0xe6,0x20,0xeb,0x00,0xeb,0x00,0xeb,0x00,0xe4,0x20,0xeb,0x00,0xeb,0x00 ; @018B7
; UNKNOWN: unresolved bytes
    db 0xeb,0x00,0xa8,0x7f,0x75,0x20,0xb0,0x20,0xe6,0xa0,0xeb,0x00,0xeb,0x00,0xeb,0x00 ; @018C7
; UNKNOWN: unresolved bytes
    db 0xb0,0x0b,0xe6,0xa0,0xeb,0x00,0xeb,0x00,0xeb,0x00,0xe4,0xa0,0xeb,0x00,0xeb,0x00 ; @018D7
; UNKNOWN: unresolved bytes
    db 0xeb,0x00,0x0a,0xc0,0x75,0x0a,0xb0,0x20,0xe6,0x20,0xeb,0x00,0xeb,0x00,0xeb,0x00 ; @018E7
; UNKNOWN: unresolved bytes
    db 0xc3 ; @018F7
; UNCONDITIONAL local stack cost8 including CPU6 and savedDS2. STI beforePUSH DS permits later IRQ nesting subject to the shadow. UNRESOLVED DOS internal stack depth/stack switching before this callback and all active-frame aliases;INT24 cost8 does not bound the DOS operation that invoked it.
; S19 original-int24: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; CPU entry retains DF,clears IF/TF.18F8 STI enables nesting;handler sets1FDF/AL0,restoresDS,IRET
; restores actual savedFLAGS. AH is high relocated game segment,not universally09.
; Dependencies: Local effect with intact frame/saves; nested IRQ/aliases remain unresolved.
CriticalErrorHandler:
    sti ; @018F8
    push ds ; @018F9
    mov ax,0x9a9 ; @018FA
    mov ds,ax ; @018FD
    mov byte [DatCriticalErrorFlag-GameDataImage],0xff ; @018FF
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @01904
    pop ds ; @01906
    iret ; @01907
; S14 U017: [01908,01916) stored bytes remain UNKNOWN.
; Neighbours: P 01907 iret; N 01916 push ds.
; Candidate1908 compares DS1FDE withF8; equal RET1915,else DX03F2/AL03/OUT DX,AL/RET. Would touch floppy DOR only for non-hard-disk FAT ID. No data write/004A producer. Entry unproved.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x80,0x3e,0xde,0x1f,0xf8,0x74,0x06,0xba,0xf2,0x03,0xb0,0x03,0xee,0xc3 ; @01908
times -(($-$$) != 0x1916) db 0
