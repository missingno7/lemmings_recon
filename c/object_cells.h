#ifndef LEMMINGS_OBJECT_CELLS_H
#define LEMMINGS_OBJECT_CELLS_H
#include <stdint.h>
#include "regs.h"

typedef struct LmnObjectCellsCall {
    uint16_t data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t cell_cursor;
    uint16_t flags;
} LmnObjectCellsCall;

typedef struct LmnObjectCellsResult {
    uint16_t value;
    uint16_t cell_cursor;
    uint16_t remaining_records;
    uint16_t dimension_state;
    uint16_t template_cursor;
    uint16_t definition_cursor;
    uint16_t object_ordinal;
    uint16_t stack_offset;
    uint16_t flags;
} LmnObjectCellsResult;

/* Writes the first sixteen object interaction rectangles directly to live
   SS memory. The SS stack saves remain part of that same memory image. */
LmnObjectCellsResult lmn_write_object_interaction_cells_core(
    uint8_t *memory, const LmnObjectCellsCall *call);
void lmn_write_object_interaction_cells_adapter(uint8_t *memory, LmnRegs *r);

#endif
