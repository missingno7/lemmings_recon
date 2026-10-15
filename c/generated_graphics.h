#ifndef LEMMINGS_GENERATED_GRAPHICS_H
#define LEMMINGS_GENERATED_GRAPHICS_H
#include "mask_generators.h"

typedef struct LmnGeneratedGraphicsCall {
    uint16_t data_segment, stack_segment, stack_offset;
    uint16_t column_repetitions, shift_state, flags;
} LmnGeneratedGraphicsCall;

typedef struct LmnGeneratedGraphicsResult {
    uint16_t value, column_repetitions, row_count, shift_state;
    uint16_t source_cursor, output_cursor, source_segment, output_segment;
    uint16_t stack_offset, flags, continuation, ready_to_return;
} LmnGeneratedGraphicsResult;

/* 5AC1..5B0F, composing the two mask generators through live near-call
   frames. A changed child return stops at that target (ready_to_return=0).
   Normal completion stops before the outer RET at 5B10. */
LmnGeneratedGraphicsResult lmn_generate_graphics_mask_banks_core(uint8_t *,
    const LmnGeneratedGraphicsCall *, const LmnRasterBus *);
void lmn_generate_graphics_mask_banks_adapter(uint8_t *, LmnRegs *,
    const LmnRasterBus *);
#endif
