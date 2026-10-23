times -(($-$$) != 0x18b2) db 0
SendMasterPicEoi:
; MOV AL,20; byte OUT20 preserves AH/FLAGS, then actual live near RET.
; docs/port-io.md; no IRQ/PIC scheduling or hardware status is invented.
    mov al,0x20 ; @018B2
MasterPicEoiOut18B4:
    out 0x20,al ; @018B4
MasterPicEoiReturn18B6:
    ret ; @018B6
; No incoming edge identified for 18B7..18F7: no direct, table, vector, relocated or
; protected-view reference reaches it and no data reader uses it, so the bytes
; stay UNKNOWN (code-looking). Recovered paths bypass it; translators of the
; neighbouring routines need nothing from it.
; Read as code: a PIC end-of-interrupt helper. It reads the master ISR (OCW3
; 0Bh) and sends EOI to port 20h if any of IRQ0..6 is in service; otherwise it
; sends EOI to the slave (A0h), rereads the slave ISR and sends the master EOI
; only when no slave IRQ remains in service. JMP $+2 pairs are I/O delays.
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
; DOS INT24 CRITICAL-ERROR HANDLER. Installed by ProgramEntry at 0085..008D
; (AH25, DS=CS, DX=18F8); reached only through IVT 24 when DOS reports a device
; error (typically drive not ready while opening/reading a DAT file).
; In: DOS critical-error registers (AH/AL/DI/BP:SI) are ignored.
; Out: DatCriticalErrorFlag 1FDF=FF in the game data segment; AL=00 (ignore);
; AH = high byte of the relocated game data segment (side effect of MOV AX);
; DS restored; IRET restores the DOS caller's FLAGS. Everything else unchanged.
; Consumers: CheckDatFile 1CF7 and LoadDatResource 1B80/1B8A test the flag and
; route to the resource retry screen; startup 0090, CheckMenuResourceAvailability
; 4B16 and ShowResourceRetryScreen 4B56 clear it. The handler never aborts or retries itself; what DOS does with
; AL=00 after return is DOS behavior, not game logic.
; Platform callback. READY for C: tiny body; host it as the critical-error
; callback of the DOS file-service seam (c/dat_files.c) that sets the flag.
CriticalErrorHandler:
    sti ; @018F8
    push ds ; @018F9
    mov ax,0x9a9 ; @018FA
    mov ds,ax ; @018FD
    mov byte [DatCriticalErrorFlag-GameDataImage],0xff ; @018FF
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @01904
    pop ds ; @01906
    iret ; @01907
; No incoming edge identified for 1908..1915: no direct, table, vector, relocated or
; protected-view reference reaches it and no data reader uses it, so the bytes
; stay UNKNOWN (code-looking). Recovered paths bypass it; translators of the
; neighbouring routines need nothing from it.
; Read as code: unless StartupFatIdByte1FDE is F8 (hard disk) it writes 03 to
; the floppy digital output register 3F2h (motor bits clear), then RETs.
; (Immediate 1911 at 0022 is the DOS AH=4A paragraph count, not a pointer.)
; UNKNOWN: unresolved bytes
    db 0x80,0x3e,0xde,0x1f,0xf8,0x74,0x06,0xba,0xf2,0x03,0xb0,0x03,0xee,0xc3 ; @01908
times -(($-$$) != 0x1916) db 0
