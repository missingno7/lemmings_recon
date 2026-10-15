#ifndef LEMMINGS_STEEL_CELLS_BUS_H
#define LEMMINGS_STEEL_CELLS_BUS_H

#include <stdint.h>
#include "steel_cells.h"
#include "special_blit.h"

/* The bus API keeps DS definition reads, live SS saves, cell stores and the
   adapter's RET read on one observable physical-memory path. */
LmnSteelInteractionCellsResult lmn_write_steel_interaction_cells_bus_core(
    uint8_t *memory, const LmnSteelInteractionCellsCall *call,
    const LmnRasterBus *bus);
void lmn_write_steel_interaction_cells_bus_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

#endif
