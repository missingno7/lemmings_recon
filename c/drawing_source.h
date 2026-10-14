#ifndef LEMMINGS_DRAWING_SOURCE_H
#define LEMMINGS_DRAWING_SOURCE_H

#include "special_blit.h"

typedef struct LmnDrawingSourceCall {
    uint16_t data_segment, stack_segment, stack_offset;
    uint16_t work_value, second_source_cursor, packed_counts, width_state;
    uint16_t source_cursor, destination_cursor, control, flags, entry;
} LmnDrawingSourceCall;

typedef struct LmnDrawingSourceResult {
    uint16_t work_value, second_source_cursor, packed_counts, width_state;
    uint16_t source_cursor, destination_cursor, control;
    uint16_t stack_offset, flags, continuation;
} LmnDrawingSourceResult;

/* Executes only the source-row setup prefix. The selected continuation is a
   renderer entry or the first instruction after this scoped preparation. */
LmnDrawingSourceResult lmn_prepare_planar_source_rows_core(
    uint8_t *memory, const LmnDrawingSourceCall *call,
    const LmnRasterBus *bus);
void lmn_prepare_planar_source_rows_adapter(
    uint8_t *memory, LmnRegs *regs, const LmnRasterBus *bus);

#endif
