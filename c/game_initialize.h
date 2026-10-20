#ifndef LEMMINGS_GAME_INITIALIZE_H
#define LEMMINGS_GAME_INITIALIZE_H
#include "video_probe.h"

enum LmnGameInitializeStatus {
    LMN_GAME_INITIALIZE_AT_BASE_PALETTE = 0,
    LMN_GAME_INITIALIZE_CHILD_STOP = 1,
    LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN = 2
};

typedef struct LmnGameInitializeResult {
    LmnRegs registers;
    uint16_t status,child_status,service_status;
} LmnGameInitializeResult;
_Static_assert(sizeof(LmnGameInitializeResult)==34u,"34-byte game initialization result");

typedef struct LmnGameInitializeServices {
    const LmnVideoProbeServices *video;
    const LmnRasterBus *bus;
} LmnGameInitializeServices;

/* Execute 03E7 state initialization, both live SS map clears, and the actual
   0462 CALL to the verified 0FB2 video setup. Stop at0465 before palette
   publication. Child/provider stops and changed RET words remain live. */
LmnGameInitializeResult lmn_initialize_game_core(uint8_t *memory,
    const LmnRegs *registers,const LmnGameInitializeServices *services);

#endif
