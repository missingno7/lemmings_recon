#ifndef LEMMINGS_FATAL_CLEANUP_H
#define LEMMINGS_FATAL_CLEANUP_H

#include "timer_restore.h"
#include "vector_restore.h"
#include "video_restore.h"

/* Transient state flowing through the fatal cleanup caller. The field order
   matches each restore leaf so all provider-returned CPU state remains live. */
typedef LmnVectorRestoreState LmnFatalCleanupState;

typedef struct LmnFatalCleanupServices {
    const LmnTimerRestoreServices *timer;
    const LmnVectorRestoreServices *vectors;
    const LmnVideoRestoreServices *video;
    void *context;
    /* Models INT 33h/AX=000Ch and DOS INT 21h/AH=09h. Each may mutate the
       canonical memory and returns all twelve logical CPU fields. */
    void (*disable_mouse)(void *, uint8_t *memory,
        const LmnFatalCleanupState *input, LmnFatalCleanupState *out);
    void (*write_message)(void *, uint8_t *memory,
        const LmnFatalCleanupState *input, LmnFatalCleanupState *out);
    /* Models the terminal DOS INT 21h/AH=4Ch call. It has no returned CPU
       state; it may still mutate canonical memory. */
    void (*terminate)(void *, uint8_t *memory,
        const LmnFatalCleanupState *input);
} LmnFatalCleanupServices;

typedef enum LmnFatalCleanupStatus {
    LMN_FATAL_CLEANUP_TERMINATED = 0,
    LMN_FATAL_CLEANUP_MISSING_PROVIDER = 1,
    LMN_FATAL_CLEANUP_CHANGED_RETURN = 2
} LmnFatalCleanupStatus;

typedef struct LmnFatalCleanupResult {
    LmnFatalCleanupState state;
    uint16_t continuation;
    enum LmnFatalCleanupStatus status;
} LmnFatalCleanupResult;

/* suffix==0 enters 04D0; nonzero enters the independently reached 04EA
   suffix. Child restore cores receive real CALL frames and stop before RET.
   Optional bus accesses use canonical 20-bit physical addresses. */
LmnFatalCleanupResult lmn_fatal_cleanup_core(uint8_t *memory,
    const LmnFatalCleanupState *input, unsigned suffix,
    const LmnFatalCleanupServices *services, const LmnRasterBus *bus);

/* Maps the core's returned state and continuation only. This adapter never
   executes an outer RET because 04D0 ends in terminal DOS service. */
void lmn_fatal_cleanup_adapter(uint8_t *memory, LmnRegs *registers,
    unsigned suffix, const LmnFatalCleanupServices *services,
    const LmnRasterBus *bus);

#endif
