#ifndef LEMMINGS_OBJECT_COORDINATES_BUS_H
#define LEMMINGS_OBJECT_COORDINATES_BUS_H

#include "object_coordinates.h"
#include "special_blit.h"

/* Bus-aware form of the existing 389F logical API. A null bus follows the
   same ordinary-RAM path as lmn_collect_type_one_object_coordinates_core. */
LmnObjectCoordinatesResult lmn_collect_type_one_object_coordinates_bus_core(
    uint8_t *memory, const LmnObjectCoordinatesCall *call,
    const LmnRasterBus *bus);

/* Executes the same entry through a raster bus, including the live near RET
   reads after all coordinate writes. */
void lmn_collect_type_one_object_coordinates_bus_adapter(uint8_t *memory,
    LmnRegs *regs, const LmnRasterBus *bus);

#endif
