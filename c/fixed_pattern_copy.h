#ifndef LEMMINGS_FIXED_PATTERN_COPY_H
#define LEMMINGS_FIXED_PATTERN_COPY_H

#include "special_blit.h"

enum LmnFixedPatternCopyStatus {
    LMN_FIXED_PATTERN_COPY_READY = 0
};

/* Live register roles at CopyFixedPatternVgaSpans (715F). */
typedef struct LmnFixedPatternCopyCall {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnFixedPatternCopyCall;

typedef struct LmnFixedPatternCopyResult {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnFixedPatternCopyResult;

/* Executes through the instruction immediately before RET at 71C9. */
LmnFixedPatternCopyResult lmn_copy_fixed_pattern_vga_spans_core(
    uint8_t *memory, const LmnFixedPatternCopyCall *call,
    const LmnRasterBus *bus);

/* Applies the result and reads the actual live near-RET word. */
uint16_t lmn_copy_fixed_pattern_vga_spans_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif
