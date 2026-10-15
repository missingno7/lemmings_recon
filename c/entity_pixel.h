#ifndef LEMMINGS_ENTITY_PIXEL_H
#define LEMMINGS_ENTITY_PIXEL_H
#include "regs.h"

typedef struct LmnEntityPixelCall {
    uint16_t data_segment, stack_segment, stack_offset, record_cursor;
    uint16_t saved_value, flags;
} LmnEntityPixelCall;
typedef struct LmnEntityPixelResult {
    uint16_t value, table_cursor, column_byte, destination_offset;
    uint16_t restored_value, stack_offset, flags;
} LmnEntityPixelResult;

/* 5DC6..5DF6, stopping before RET. Live DS record/table and SS save in
   ordinary 20-bit RAM. The leaf selects ES=A000 but accesses no VGA memory. */
LmnEntityPixelResult lmn_prepare_entity_pixel_core(
    uint8_t *memory, const LmnEntityPixelCall *call);
void lmn_prepare_entity_pixel_adapter(uint8_t *memory, LmnRegs *regs);
#endif
