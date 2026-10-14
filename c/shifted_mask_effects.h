#ifndef LEMMINGS_SHIFTED_MASK_EFFECTS_H
#define LEMMINGS_SHIFTED_MASK_EFFECTS_H

#include "special_blit.h"

typedef struct LmnShiftedMaskEffectCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t mask_cursor;
    uint16_t destination_cursor;
    uint16_t control;
    uint16_t flags;
} LmnShiftedMaskEffectCall;

typedef struct LmnShiftedMaskEffectResult {
    uint16_t work_value;
    uint16_t packed_counts;
    uint16_t port;
    uint16_t source_cursor;
    uint16_t mask_cursor;
    uint16_t destination_cursor;
    uint16_t control;
    uint16_t stack_offset;
    uint16_t source_segment;
    uint16_t output_segment;
    uint16_t flags;
} LmnShiftedMaskEffectResult;

/* Core boundaries stop after POP DS at 909A/913E. The adapter consumes the
   untouched RETF at 909B/913F from the caller's live SS:SP frame. */
LmnShiftedMaskEffectResult lmn_draw_shifted_mask20_core(
    uint8_t *memory, const LmnShiftedMaskEffectCall *call,
    const LmnRasterBus *bus);
LmnShiftedMaskEffectResult lmn_draw_shifted_mask40_core(
    uint8_t *memory, const LmnShiftedMaskEffectCall *call,
    const LmnRasterBus *bus);
void lmn_draw_shifted_mask20_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);
void lmn_draw_shifted_mask40_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
