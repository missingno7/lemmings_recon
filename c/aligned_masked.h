#ifndef LEMMINGS_ALIGNED_MASKED_H
#define LEMMINGS_ALIGNED_MASKED_H

#include "special_blit.h"

typedef struct LmnAlignedMaskedCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t width_state;
    uint16_t source_cursor;
    uint16_t mask_cursor;
    uint16_t destination_cursor;
    uint16_t flags;
} LmnAlignedMaskedCall;

typedef struct LmnAlignedMaskedResult {
    uint16_t work_value;
    uint16_t packed_counts;
    uint16_t port;
    uint16_t source_cursor;
    uint16_t mask_cursor;
    uint16_t destination_cursor;
    uint16_t plane_counter;
    uint16_t stack_offset;
    uint16_t source_segment;
    uint16_t output_segment;
    uint16_t flags;
} LmnAlignedMaskedResult;

/* Logical entry at CS:93F6. Runs through POP DS at 953C and leaves the live
   far-return frame at SS:SP for the boundary adapter. */
LmnAlignedMaskedResult lmn_draw_aligned_masked_core(
    uint8_t *memory, const LmnAlignedMaskedCall *call,
    const LmnRasterBus *bus);

/* Boundary adapter for 93F6..953D. It consumes the live far-return frame
   through sequenced physical byte reads and does not execute its target. */
void lmn_draw_aligned_masked_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
