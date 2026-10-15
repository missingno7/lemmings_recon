#ifndef LEMMINGS_OBJECT_CELLS_BUS_H
#define LEMMINGS_OBJECT_CELLS_BUS_H
#include <stdint.h>
#include "object_cells.h"
#include "special_blit.h"

/* Bus-aware form of the 37C2 leaf. The core leaves its caller's live RET
   word at stack_offset; only the adapter reads and consumes that word. */
LmnObjectCellsResult lmn_write_object_interaction_cells_bus_core(
    uint8_t *memory, const LmnObjectCellsCall *call, const LmnRasterBus *bus);
void lmn_write_object_interaction_cells_bus_adapter(
    uint8_t *memory, LmnRegs *regs, const LmnRasterBus *bus);

#endif
