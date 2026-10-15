#ifndef LEMMINGS_FILE_ERROR_H
#define LEMMINGS_FILE_ERROR_H

#include "fatal_cleanup.h"

/* Transient register state flowing through the 1949 file-error transfer. */
typedef LmnFatalCleanupState LmnFileErrorState;

typedef struct LmnFileErrorServices {
    const LmnVideoRestoreServices *video;
    const LmnFatalCleanupServices *cleanup;
    void *context;
    /* Returning DOS INT 21h/AH=09h and AH=02h boundaries. Each may mutate
       canonical memory and returns all twelve CPU fields. */
    void (*write_message)(void *, uint8_t *memory,
        const LmnFileErrorState *input, LmnFileErrorState *out);
    void (*write_character)(void *, uint8_t *memory,
        const LmnFileErrorState *input, LmnFileErrorState *out);
} LmnFileErrorServices;

typedef enum LmnFileErrorStatus {
    LMN_FILE_ERROR_TERMINATED = 0,
    LMN_FILE_ERROR_MISSING_PROVIDER = 1,
    LMN_FILE_ERROR_CHANGED_RETURN = 2
} LmnFileErrorStatus;

typedef struct LmnFileErrorResult {
    LmnFileErrorState state;
    uint16_t continuation;
    enum LmnFileErrorStatus status;
} LmnFileErrorResult;

/* Models the 1949 transfer through the direct JMP to fatal-cleanup suffix
   04EA. The relocated main-data segment is supplied by the caller. */
LmnFileErrorResult lmn_file_error_core(uint8_t *memory,
    uint16_t main_data_segment, const LmnFileErrorState *input,
    const LmnFileErrorServices *services, const LmnRasterBus *bus);

/* Reads the relocated MOV DX immediate at live CS:194B, maps returned state,
   and leaves the original caller's outer return untouched. */
void lmn_file_error_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnFileErrorServices *services, const LmnRasterBus *bus);

#endif
