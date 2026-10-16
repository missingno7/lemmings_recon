#ifndef LEMMINGS_FIXED_PATTERN_UPDATE_H
#define LEMMINGS_FIXED_PATTERN_UPDATE_H

#include "special_blit.h"

enum LmnFixedPatternUpdateStatus {
    LMN_FIXED_PATTERN_UPDATE_READY = 0,
    LMN_FIXED_PATTERN_UPDATE_CHANGED_CHILD_RETURN = 1
};

typedef struct LmnFixedPatternUpdateCall {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnFixedPatternUpdateCall;

typedef struct LmnFixedPatternUpdateResult {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status, child_entry;
} LmnFixedPatternUpdateResult;

/* Composes the two actual near frames and stops before RET at 587E.
   A changed child return preserves its state before any following parent work. */
LmnFixedPatternUpdateResult lmn_update_fixed_word_pattern_core(
    uint8_t *memory, const LmnFixedPatternUpdateCall *call,
    const LmnRasterBus *bus);

/* Consumes the live outer RET only after READY. */
uint16_t lmn_update_fixed_word_pattern_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif
