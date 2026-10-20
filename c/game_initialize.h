#ifndef LEMMINGS_GAME_INITIALIZE_H
#define LEMMINGS_GAME_INITIALIZE_H
#include "video_probe.h"
#include "game_prepare.h"
#include "level_initialize.h"

enum LmnGameInitializeStatus {
    LMN_GAME_INITIALIZE_AT_MOUSE_SERVICE_CHECK = 0,
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
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    const LmnLevelInitializeServices *level;
    uint16_t game_data_segment;
} LmnGameInitializeServices;

/* Execute 03E7 state initialization, both live SS map clears, and the actual
   0462/0465/0468/046B CALLs through level-record initialization. The ordinary
   continuation is 046E. Child/provider stops and changed RETs remain live. */
LmnGameInitializeResult lmn_initialize_game_core(uint8_t *memory,
    const LmnRegs *registers,const LmnGameInitializeServices *services);

#endif
