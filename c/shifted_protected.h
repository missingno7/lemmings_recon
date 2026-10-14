#ifndef LEMMINGS_SHIFTED_PROTECTED_H
#define LEMMINGS_SHIFTED_PROTECTED_H

#include "special_blit.h"

typedef struct LmnShiftedProtectedCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t width_state;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t flags;
} LmnShiftedProtectedCall;

typedef struct LmnShiftedProtectedResult {
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
} LmnShiftedProtectedResult;

/* Runs the body at 8B42 through POP DS at 8D64. The untouched RETF at 8D65
   remains the responsibility of the boundary adapter. BX is never read or
   written by this body and is intentionally absent from the logical API. */
LmnShiftedProtectedResult lmn_draw_shifted_protected_core(
    uint8_t *memory, const LmnShiftedProtectedCall *call,
    const LmnRasterBus *bus);

void lmn_draw_shifted_protected_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
