#ifndef LEMMINGS_GAME_INITIALIZE_H
#define LEMMINGS_GAME_INITIALIZE_H
#include "video_probe.h"
#include "game_prepare.h"
#include "level_initialize.h"
#include "foreground_poll.h"

enum LmnGameInitializeStatus {
    LMN_GAME_INITIALIZE_AT_MOUSE_SERVICE_CHECK = 0,
    LMN_GAME_INITIALIZE_CHILD_STOP = 1,
    LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN = 2,
    LMN_GAME_INITIALIZE_RETURNED = 3,
    LMN_GAME_INITIALIZE_POLL_REQUIRED = 4,
    LMN_GAME_INITIALIZE_POLL_STOP = 5
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
    /* Explicit compatibility checkpoint for prefix-only consumers. */
    uint16_t stop_at_mouse_check;
    const LmnInterruptService *mouse;
    const LmnInterruptService *dos;
    const LmnForegroundPoll *foreground;
} LmnGameInitializeServices;

/* Execute 03E7..04CF, including the actual outer RET. Each child sees its
   predecessor's returned state. NULL foreground stops before CMP at04AA;
   nonzero poll results stop before that site's CMP with service_status live.
   stop_at_mouse_check retains the old046E checkpoint/status. */
LmnGameInitializeResult lmn_initialize_game_core(uint8_t *memory,
    const LmnRegs *registers,const LmnGameInitializeServices *services);

#endif
