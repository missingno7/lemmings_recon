#ifndef LEMMINGS_TIMER_RESTORE_H
#define LEMMINGS_TIMER_RESTORE_H
#include "special_blit.h"

/* Transient register state at the INT 1Ah boundary, not persistent game
   state. Providers may mutate canonical memory directly. */
typedef struct LmnTimerRestoreState {
    uint16_t value, base_value, count, argument;
    uint16_t source_cursor, output_cursor, frame_cursor;
    uint16_t data_segment, extra_segment, stack_segment, stack_offset, flags;
} LmnTimerRestoreState;

typedef struct LmnTimerRestoreServices {
    void *context;
    /* Byte OUT preserves CPU registers and flags; device effects live in the
       service context and may update canonical memory there. */
    void (*out_byte)(void *, uint16_t port, uint8_t value, uint16_t flags);
    /* Models BIOS INT 1Ah/AH=01h. It may update all twelve fields and memory;
       CS remains caller-owned and execution resumes after the interrupt. */
    void (*set_clock)(void *, uint8_t *memory,
        const LmnTimerRestoreState *input, LmnTimerRestoreState *out);
} LmnTimerRestoreServices;

typedef enum LmnTimerRestoreStatus {
    LMN_TIMER_RESTORE_READY = 0,
    LMN_TIMER_RESTORE_MISSING_PROVIDER = 1
} LmnTimerRestoreStatus;

typedef struct LmnTimerRestoreResult {
    LmnTimerRestoreState state;
    uint16_t continuation;
    enum LmnTimerRestoreStatus status;
} LmnTimerRestoreResult;

/* Restores the PIT, IVT timer vector and BIOS clock. The core adds no stack
   frame. Every memory byte, including PUSH/POP and adapter RET, goes through
   the optional canonical 20-bit bus; words access low byte then physical+1,
   wrapping at A20, while SP wraps at 16 bits between stack words. */
LmnTimerRestoreResult lmn_restore_timer_state_core(uint8_t *memory,
    const LmnTimerRestoreState *input,
    const LmnTimerRestoreServices *services, const LmnRasterBus *bus);

void lmn_restore_timer_state_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnTimerRestoreServices *services, const LmnRasterBus *bus);

#endif
