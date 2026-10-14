#ifndef LEMMINGS_SHIFTED_OPAQUE_H
#define LEMMINGS_SHIFTED_OPAQUE_H

#include "special_blit.h"

typedef struct LmnShiftedOpaqueCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t width_state;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t flags;
} LmnShiftedOpaqueCall;

typedef struct LmnShiftedOpaqueResult {
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
} LmnShiftedOpaqueResult;

/* Core stops after POP DS at 939C. The adapter consumes the live RETF at
   939D from the caller's original SS:SP frame. */
LmnShiftedOpaqueResult lmn_draw_shifted_opaque_core(
    uint8_t *memory, const LmnShiftedOpaqueCall *call,
    const LmnRasterBus *bus);
void lmn_draw_shifted_opaque_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
