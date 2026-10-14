#ifndef LEMMINGS_ALIGNED_MASK_EFFECTS_H
#define LEMMINGS_ALIGNED_MASK_EFFECTS_H

#include "special_blit.h"

typedef struct LmnAlignedMaskEffectCall {
    uint16_t initial_data_segment;
    uint16_t game_data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t packed_counts;
    uint16_t mask_cursor;
    uint16_t destination_cursor;
    uint16_t control;
    uint16_t flags;
} LmnAlignedMaskEffectCall;

typedef struct LmnAlignedMaskEffectResult {
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
} LmnAlignedMaskEffectResult;

/* Core boundaries stop after POP DS at 97A2/980E. The adapter consumes the
   untouched RETF at 97A3/980F from the live SS:SP frame. */
LmnAlignedMaskEffectResult lmn_draw_aligned_mask20_core(
    uint8_t *memory, const LmnAlignedMaskEffectCall *call,
    const LmnRasterBus *bus);
LmnAlignedMaskEffectResult lmn_draw_aligned_mask40_core(
    uint8_t *memory, const LmnAlignedMaskEffectCall *call,
    const LmnRasterBus *bus);
void lmn_draw_aligned_mask20_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);
void lmn_draw_aligned_mask40_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus);

#endif
