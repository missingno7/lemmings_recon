#ifndef LEMMINGS_STEEL_CELLS_H
#define LEMMINGS_STEEL_CELLS_H
#include <stdint.h>
#include "regs.h"

typedef struct LmnSteelInteractionCellsCall {
    uint16_t data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t flags;
} LmnSteelInteractionCellsCall;

typedef struct LmnSteelInteractionCellsResult {
    uint16_t value;              /* AX */
    uint16_t cell_cursor;         /* BX */
    uint16_t records_remaining;   /* CX */
    uint16_t dimensions;          /* DX */
    uint16_t definition_cursor;   /* DI */
    uint16_t stack_offset;        /* SP, before the adapter's RET */
    uint16_t flags;
} LmnSteelInteractionCellsResult;

/* Writes the 32 live steel-cell rectangles to SS memory. The canonical memory
   image includes both the interaction map and the live caller stack. */
LmnSteelInteractionCellsResult lmn_write_steel_interaction_cells_core(
    uint8_t *memory, const LmnSteelInteractionCellsCall *call);
void lmn_write_steel_interaction_cells_adapter(uint8_t *memory, LmnRegs *r);

#endif
