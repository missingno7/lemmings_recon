#ifndef LEMMINGS_ENTITY_STROKE_H
#define LEMMINGS_ENTITY_STROKE_H
#include "entity_pixel.h"

typedef struct LmnEntityStrokeCall {
    uint16_t data_segment, stack_segment, stack_offset, record_cursor, flags;
} LmnEntityStrokeCall;
typedef struct LmnEntityStrokeResult {
    uint16_t value, mask_word, spill_word, destination_offset, output_segment;
    uint16_t port, stack_offset, flags, continuation, ready_to_return;
} LmnEntityStrokeResult;

/* 5F0F..5FAA, with a direct 5DC6 child and its actual near RET. A changed
   child target returns ready_to_return=0 before executing that target.
   Otherwise continuation=5FAB is the boundary before the outer RET. */
LmnEntityStrokeResult lmn_draw_entity_stroke_core(uint8_t *,
    const LmnEntityStrokeCall *, const LmnRasterBus *);
void lmn_draw_entity_stroke_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
#endif
