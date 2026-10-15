#ifndef LEMMINGS_ENTITY_PIXEL_H
#define LEMMINGS_ENTITY_PIXEL_H
#include "regs.h"
#include "special_blit.h"

typedef struct LmnEntityPixelCall {
    uint16_t data_segment, stack_segment, stack_offset, record_cursor;
    uint16_t saved_value, flags;
} LmnEntityPixelCall;
typedef struct LmnEntityPixelResult {
    uint16_t value, table_cursor, column_byte, destination_offset;
    uint16_t restored_value, stack_offset, flags;
} LmnEntityPixelResult;

/* 5DC6..5DF6, stopping before RET. Reads the live DS record/table and pushes
   through SS. A supplied bus owns every byte access, including VGA aliases. */
LmnEntityPixelResult lmn_prepare_entity_pixel_core(
    uint8_t *memory, const LmnEntityPixelCall *call);
LmnEntityPixelResult lmn_prepare_entity_pixel_bus_core(
    uint8_t *memory, const LmnEntityPixelCall *call,
    const LmnRasterBus *bus);
void lmn_prepare_entity_pixel_adapter(uint8_t *memory, LmnRegs *regs);
void lmn_prepare_entity_pixel_bus_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus);
#endif
