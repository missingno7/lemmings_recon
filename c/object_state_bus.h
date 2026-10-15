#ifndef LEMMINGS_OBJECT_STATE_BUS_H
#define LEMMINGS_OBJECT_STATE_BUS_H
#include "object_state.h"
#include "special_blit.h"

/* Bus-aware composition of the four CALLs at 376A..3775. Each CALL frame,
   child access and live near-RET read uses the same physical raster bus.
   The fragment ends after the 3773 child RET; it does not execute 3776. */
LmnObjectStateResult lmn_prepare_level_object_state_bus_core(
    uint8_t *memory, const LmnObjectStateCall *call,
    const LmnRasterBus *bus);
void lmn_prepare_level_object_state_bus_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

#endif
