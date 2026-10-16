#ifndef LEMMINGS_FIXED_PATTERN_DRAW_H
#define LEMMINGS_FIXED_PATTERN_DRAW_H

#include "special_blit.h"

enum LmnFixedPatternDrawStatus {
    LMN_FIXED_PATTERN_DRAW_READY = 0
};

/* Live roles at DrawFixedWordPattern (7218). */
typedef struct LmnFixedPatternDrawCall {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnFixedPatternDrawCall;

typedef struct LmnFixedPatternDrawResult {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnFixedPatternDrawResult;

/* Executes the leaf through STI, stopping at the RET instruction at 75EE. */
LmnFixedPatternDrawResult lmn_draw_fixed_word_pattern_core(
    uint8_t *memory, const LmnFixedPatternDrawCall *call,
    const LmnRasterBus *bus);

/* Applies the result and consumes the actual live SS:SP near-RET word. */
uint16_t lmn_draw_fixed_word_pattern_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif
