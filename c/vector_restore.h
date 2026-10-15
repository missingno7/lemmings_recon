#ifndef LEMMINGS_VECTOR_RESTORE_H
#define LEMMINGS_VECTOR_RESTORE_H
#include "special_blit.h"

/* Transient register state at the DOS interrupt boundary, not persistent
   game state. DOS providers may mutate the canonical memory pointer directly. */
typedef struct LmnVectorRestoreState {
    uint16_t value, base_value, count, argument;
    uint16_t source_cursor, output_cursor, frame_cursor;
    uint16_t data_segment, extra_segment, stack_segment, stack_offset, flags;
} LmnVectorRestoreState;

typedef struct LmnVectorRestoreServices {
    void *context;
    /* Models DOS INT 21h/AH=25h. It may update all twelve fields and memory;
       CS remains caller-owned and the provider resumes after the INT. */
    void (*set_vector)(void *, uint8_t *memory,
        const LmnVectorRestoreState *input, LmnVectorRestoreState *out);
} LmnVectorRestoreServices;

typedef enum LmnVectorRestoreStatus {
    LMN_VECTOR_RESTORE_READY = 0,
    LMN_VECTOR_RESTORE_MISSING_PROVIDER = 1
} LmnVectorRestoreStatus;

typedef struct LmnVectorRestoreResult {
    LmnVectorRestoreState state;
    uint16_t continuation;
    enum LmnVectorRestoreStatus status;
} LmnVectorRestoreResult;

/* Pushes incoming DS, reads live vector fields, calls DOS, and pops DS from
   the returned SS:SP. The core adds no other stack frame or state copy. Bus
   accesses use canonical 20-bit physical addresses and current flags; words
   access low byte then physical+1 with wrap. */
LmnVectorRestoreResult lmn_restore_keyboard_vector_core(uint8_t *memory,
    const LmnVectorRestoreState *input,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus);
LmnVectorRestoreResult lmn_restore_private_vector_core(uint8_t *memory,
    const LmnVectorRestoreState *input,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus);

void lmn_restore_keyboard_vector_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus);
void lmn_restore_private_vector_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus);

#endif
