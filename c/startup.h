#ifndef LEMMINGS_STARTUP_H
#define LEMMINGS_STARTUP_H
#include "video_probe.h"
#include "main_resources.h"
#include "keyboard_input.h"
#include "sound_driver_init.h"

/* A declared pre-RET outcome, never an implementation of protection. The
   provider receives the real 00E3 near return at live SS:SP. Zero means that
   the identified child reached its RET; all returned state remains live. */
typedef uint16_t (*LmnStartupChild)(void *,uint8_t *,LmnRegs *,const LmnRasterBus *);
typedef struct LmnStartupServices {
    const LmnInterruptService *dos,*bios,*clock,*mouse;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    const LmnDatFileServices *files;
    const LmnDatIo *io;
    void *child_context;
    const LmnSoundDriverInitServices *sound;
    LmnStartupChild protection;
} LmnStartupServices;
enum LmnStartupEntry {
    LMN_STARTUP_PROGRAM,LMN_STARTUP_COMMAND_LINE,LMN_STARTUP_OPTIONS,
    LMN_STARTUP_ALLOCATE,LMN_STARTUP_MOUSE
};
enum LmnStartupStatus {
    LMN_STARTUP_READY,LMN_STARTUP_INTERRUPT_STOP,LMN_STARTUP_CHANGED_RETURN,
    LMN_STARTUP_CHILD_STOP,LMN_STARTUP_PROTECTION_SEAM,
    LMN_STARTUP_SOUND_SEAM,LMN_STARTUP_MISSING_PORT,LMN_STARTUP_DOS_EXIT
};
typedef struct LmnStartupResult {
    LmnRegs registers;
    uint16_t status,child_entry,child_status,service_status;
} LmnStartupResult;

/* CONDITIONAL: DOS entry uses the live relocated operand0001, ES=PSP and
   loaded SS:SP; TF clear, external IRQs quiescent. String clear follows DF.
   Every CALL/save/RET/INT is canonical. Existing children keep their typed
   file/bus domains. Program stops at JMP43F2 or before an unbound child seam;
   other entries stop before their own RET. No implicit outer return or cap.
   Contracts/proposed ledger names: build/worker-startup-report.md. */
LmnStartupResult lmn_startup_core(uint8_t *,const LmnRegs *,enum LmnStartupEntry,
    const LmnStartupServices *);
#endif
