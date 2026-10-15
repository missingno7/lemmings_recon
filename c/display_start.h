#ifndef LEMMINGS_DISPLAY_START_H
#define LEMMINGS_DISPLAY_START_H
#include "display_status.h"

/* Register state is identical to the neighboring display-status leaves. */
typedef LmnDisplayStatusState LmnDisplayStartState;

typedef enum LmnDisplayStartEntry {
    LMN_DISPLAY_START_ENTRY_SAVED = 0, /* 4C32: BX <- [DS:1F78] */
    LMN_DISPLAY_START_ENTRY_VALUE = 1, /* 4C36: use input BX */
    LMN_DISPLAY_START_ENTRY_SWAP = 2  /* 4C20: exchange the origins */
} LmnDisplayStartEntry;

typedef enum LmnDisplayStartStatus {
    LMN_DISPLAY_START_READY = 0,
    LMN_DISPLAY_START_MISSING_PORT = 1,
    LMN_DISPLAY_START_CHANGED_RETURN = 2
} LmnDisplayStartStatus;

typedef struct LmnDisplayStartResult {
    LmnDisplayStartState state;
    uint16_t continuation;
    enum LmnDisplayStartStatus status;
} LmnDisplayStartResult;

/* Runs one of 4C20, 4C32, or the shared 4C36 tail on canonical memory.
   The OUT word provider is mandatory. A missing provider stops at 4C3F,
   after CLI and the original DX/AH/AL setup. READY stops before the RET at
   4C46 or 4C31; SWAP consumes its internal CALL/RET through the live bus. */
LmnDisplayStartResult lmn_program_display_start_core(
    uint8_t *memory, const LmnDisplayStartState *input,
    enum LmnDisplayStartEntry entry, const LmnRasterBus *bus);

/* Maps the logical result back to registers. READY consumes the actual outer
   RET word through the bus; missing-provider and changed-return exits retain
   their logical continuation and stack state. */
void lmn_program_display_start_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnDisplayStartEntry entry, const LmnRasterBus *bus);

#endif
