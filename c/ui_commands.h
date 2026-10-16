#ifndef LEMMINGS_UI_COMMANDS_H
#define LEMMINGS_UI_COMMANDS_H

#include "interrupt_service.h"

typedef struct LmnUiCommandsResult {
    LmnRegs registers;
    uint16_t status;
    uint16_t service_status;
} LmnUiCommandsResult;

enum LmnUiCommandsStatus {
    LMN_UI_COMMANDS_READY = 0,
    LMN_UI_COMMANDS_UNBOUND_SERVICE = 1,
    LMN_UI_COMMANDS_EXTERNAL_STOP = 2,
    LMN_UI_COMMANDS_CHANGED_INTERRUPT_RETURN = 3,
    LMN_UI_COMMANDS_CHANGED_CHILD_RETURN = 4,
    LMN_UI_COMMANDS_CHILD_STOP = 5
};

/* Stops immediately before the actual RET at 3FE8 or 3FEE. */
LmnUiCommandsResult lmn_process_input_commands_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnRasterBus *bus);

/* Consumes the live near RET only when the core returns READY. */
LmnUiCommandsResult lmn_process_input_commands_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnRasterBus *bus);

#endif
