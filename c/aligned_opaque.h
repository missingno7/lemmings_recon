#ifndef LEMMINGS_ALIGNED_OPAQUE_H
#define LEMMINGS_ALIGNED_OPAQUE_H

#include "special_blit.h"

typedef struct LmnAlignedOpaqueCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t width_state;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t flags;
} LmnAlignedOpaqueCall;

typedef struct LmnAlignedOpaqueResult {
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
} LmnAlignedOpaqueResult;

/* Logical entry at CS:983B. Runs through POP DS at 9965 and stops before the
   live far return at 9966. Segment and stack aliases remain canonical RAM. */
LmnAlignedOpaqueResult lmn_draw_aligned_opaque_core(
    uint8_t *memory, const LmnAlignedOpaqueCall *call,
    const LmnRasterBus *bus);

/* Boundary adapter for 983B..9966. It consumes the live far-return frame
   with sequenced physical byte reads and does not execute the return target. */
void lmn_draw_aligned_opaque_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
