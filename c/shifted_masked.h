#ifndef LEMMINGS_SHIFTED_MASKED_H
#define LEMMINGS_SHIFTED_MASKED_H

#include "special_blit.h"

typedef struct LmnShiftedMaskedCall {
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
} LmnShiftedMaskedCall;

typedef struct LmnShiftedMaskedResult {
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
} LmnShiftedMaskedResult;

/* Logical body at CS:890E through POP DS at 8B40. The untouched RETF at
   8B41 remains in the original image and is consumed only by the adapter. */
LmnShiftedMaskedResult lmn_draw_shifted_masked_core(
    uint8_t *memory, const LmnShiftedMaskedCall *call,
    const LmnRasterBus *bus);
void lmn_draw_shifted_masked_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
