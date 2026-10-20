#ifndef LEMMINGS_GAME_SESSION_H
#define LEMMINGS_GAME_SESSION_H
#include "game_initialize.h"
#include "game_frame.h"

/* Observation only, at0105 before a swap and at46EB after session exit.
   It must not mutate memory/registers, deliver IRQs or call back into gameplay.
   Asynchronous delivery/cancellation remains solely LmnForegroundPoll. */
typedef void (*LmnGameSessionObserveFn)(void *context,const uint8_t *,const LmnRegs *);
typedef struct LmnGameSessionServices {
    const LmnGameInitializeServices *initialize;
    const LmnGameFrameServices *frame;
    void *observer_context;
    LmnGameSessionObserveFn observe;
} LmnGameSessionServices;
enum LmnGameSessionStatus {
    LMN_GAME_SESSION_EXIT, LMN_GAME_SESSION_INITIALIZE_STOP,
    LMN_GAME_SESSION_CHANGED_RETURN, LMN_GAME_SESSION_FRAME_STOP
};
typedef struct LmnGameSessionResult {
    LmnRegs registers;
    uint16_t status, child_entry, child_status, service_status;
} LmnGameSessionResult;
/* 00FB..0104, then the connected foreground until46EB or a child/poll stop.
   Actual CALL/RET words and the mutable CS:83BE byte stay on the live bus.
   There is no frame limit: the platform's foreground poll owns cancellation.
   CONDITIONAL READY in the existing child/provider domains, with IRQs only
   at explicit foreground polls. See src/entry_services.asm's00FB contract. */
LmnGameSessionResult lmn_game_session_core(uint8_t *,const LmnRegs *,
    const LmnGameSessionServices *);
#endif
