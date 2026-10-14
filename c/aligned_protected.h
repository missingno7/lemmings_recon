#ifndef LEMMINGS_ALIGNED_PROTECTED_H
#define LEMMINGS_ALIGNED_PROTECTED_H

#include "special_blit.h"

typedef struct LmnAlignedProtectedCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t width_state;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t flags;
} LmnAlignedProtectedCall;

typedef struct LmnAlignedProtectedResult {
    uint16_t work_value;
    uint16_t packed_counts;
    uint16_t port;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t plane_counter;
    uint16_t stack_offset;
    uint16_t source_segment;
    uint16_t output_segment;
    uint16_t flags;
} LmnAlignedProtectedResult;

/* Logical entry at CS:953E. Runs through POP DS at 969A and leaves the live
   far-return frame at SS:SP for the boundary adapter. */
LmnAlignedProtectedResult lmn_draw_aligned_protected_core(
    uint8_t *memory, const LmnAlignedProtectedCall *call,
    const LmnRasterBus *bus);

/* Boundary adapter for 953E..969B. It consumes the live far-return frame
   through sequenced physical byte reads and does not execute its target. */
void lmn_draw_aligned_protected_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
