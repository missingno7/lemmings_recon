#ifndef LEMMINGS_DISPLAY_SETUP_H
#define LEMMINGS_DISPLAY_SETUP_H
#include "video_restore.h"

/* Transient CPU state shared with the video-restore BIOS boundary. */
typedef LmnVideoRestoreState LmnDisplaySetupState;

typedef enum LmnDisplaySetupEntry {
    LMN_DISPLAY_SETUP_ENTRY_FULL = 0,      /* 4BE7: BIOS setup then layout */
    LMN_DISPLAY_SETUP_ENTRY_INITIALIZE = 1,/* 4BF5: initialize DS origins */
    LMN_DISPLAY_SETUP_ENTRY_LAYOUT = 2     /* 4C07: shared layout setup */
} LmnDisplaySetupEntry;

typedef enum LmnDisplaySetupStatus {
    LMN_DISPLAY_SETUP_READY = 0,
    LMN_DISPLAY_SETUP_MISSING_MODE = 1,
    LMN_DISPLAY_SETUP_CHANGED_RETURN = 2
} LmnDisplaySetupStatus;

typedef struct LmnDisplaySetupResult {
    LmnDisplaySetupState state;
    uint16_t code_segment;
    uint16_t continuation;
    enum LmnDisplaySetupStatus status;
} LmnDisplaySetupResult;

/* Runs a pinned entry on canonical memory. FULL requires the 4BE7 INT 10h
   set_mode service; its twelve returned fields feed the remaining code and
   CS returns unchanged. INITIALIZE and LAYOUT begin after that interrupt and
   preserve incoming fields until the corresponding original instructions
   change them.

   Precondition: the intact far CALL at 4C11 is encoded as 0000:8808 and the
   loaded image's relocation makes its target same-code_segment:8808 (including
   the 4C14 word among the image's 63 fixups). Its CALL/RETF words use live
   SS:SP and the optional bus. A changed child return stops at its actual
   CS:IP before 4C16; it does not execute an arbitrary target. READY stops
   before the outer near RET at 4C16. */
LmnDisplaySetupResult lmn_setup_display_core(uint8_t *memory,
    uint16_t code_segment, const LmnDisplaySetupState *input,
    enum LmnDisplaySetupEntry entry,
    const LmnVideoRestoreServices *services, const LmnRasterBus *bus);

/* Applies the core result and consumes the live outer near RET only for a
   READY result. BIOS-returned SS:SP selects both child and outer stack words. */
void lmn_setup_display_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnDisplaySetupEntry entry,
    const LmnVideoRestoreServices *services, const LmnRasterBus *bus);

#endif
