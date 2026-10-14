#ifndef LEMMINGS_SHIFTED_READ_MASK_H
#define LEMMINGS_SHIFTED_READ_MASK_H

#include "special_blit.h"

typedef struct LmnShiftedReadMaskCall {
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
} LmnShiftedReadMaskCall;

typedef struct LmnShiftedReadMaskResult {
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
} LmnShiftedReadMaskResult;

/* Core runs 8D66 through POP DS at 8FF5. The adapter then executes the live
   far-return words through the unchanged RETF at 8FF6. */
LmnShiftedReadMaskResult lmn_draw_shifted_read_mask_core(
    uint8_t *memory, const LmnShiftedReadMaskCall *call,
    const LmnRasterBus *bus);
void lmn_draw_shifted_read_mask_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnRasterBus *bus);

#endif
