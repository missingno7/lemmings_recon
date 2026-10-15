#ifndef LEMMINGS_ENTITY_PATTERN_H
#define LEMMINGS_ENTITY_PATTERN_H
#include "regs.h"
#include "special_blit.h"

/* Live boundary state; coordinates and pattern stay in the canonical RAM. */
typedef struct LmnEntityPatternCall {
    uint16_t data_segment, stack_segment, stack_offset, record_cursor;
    uint16_t saved_destination, saved_value, saved_segment, flags;
} LmnEntityPatternCall;
typedef struct LmnEntityPatternResult {
    uint16_t product, map_offset, restored_value, record_cursor;
    uint16_t restored_destination, restored_segment, stack_offset, flags;
} LmnEntityPatternResult;

/* 283B..287B, before RET. These legacy entrypoints use ordinary canonical RAM. */
LmnEntityPatternResult lmn_copy_entity_pattern_core(
    uint8_t *memory, const LmnEntityPatternCall *call);
void lmn_copy_entity_pattern_adapter(uint8_t *memory, LmnRegs *regs);

/* Optional bus routes every byte access with instruction-phase FLAGS. */
LmnEntityPatternResult lmn_copy_entity_pattern_bus_core(
    uint8_t *memory, const LmnEntityPatternCall *call,
    const LmnRasterBus *bus);
void lmn_copy_entity_pattern_bus_adapter(
    uint8_t *memory, LmnRegs *regs, const LmnRasterBus *bus);
#endif
