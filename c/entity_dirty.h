#ifndef LEMMINGS_ENTITY_DIRTY_H
#define LEMMINGS_ENTITY_DIRTY_H

#include "special_blit.h"

enum LmnEntityDirtyStatus {
    LMN_ENTITY_DIRTY_READY = 0
};

/* Live register roles at MarkEntityDrawingDirty (5726). */
typedef struct LmnEntityDirtyCall {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnEntityDirtyCall;

typedef struct LmnEntityDirtyResult {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnEntityDirtyResult;

/* The core stops before RET 57D0; the adapter consumes its live SS:SP word. */
LmnEntityDirtyResult lmn_mark_entity_drawing_dirty_core(uint8_t *memory,
    const LmnEntityDirtyCall *call, const LmnRasterBus *bus);
uint16_t lmn_mark_entity_drawing_dirty_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif
