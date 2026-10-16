#ifndef LEMMINGS_STATUS_DISPLAY_FULL_H
#define LEMMINGS_STATUS_DISPLAY_FULL_H

#include "status_display.h"

enum LmnStatusDisplayFullStatus {
    LMN_STATUS_DISPLAY_FULL_READY = 0,
    /* The 3AC8 minimap prefix stopped before its 3ACE fallthrough. */
    LMN_STATUS_DISPLAY_MINIMAP_BOUNDARY = 5
};

/* The full caller and suffix have the same live register-role boundary. */
typedef LmnStatusDisplayCall LmnStatusDisplayFullCall;
typedef LmnStatusDisplayResult LmnStatusDisplayFullResult;

/* Composes the 3AC8 prefix and the 3ACE suffix without adding a frame at the
   fallthrough. READY stops before the outer RET at 3CDD. */
LmnStatusDisplayFullResult lmn_update_status_display_full_core(
    uint8_t *memory,const LmnStatusDisplayFullCall *call,
    const LmnRasterBus *bus);

/* Applies returned roles and consumes the live outer RET only on READY. */
uint16_t lmn_update_status_display_full_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif
