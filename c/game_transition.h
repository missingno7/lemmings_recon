#ifndef LEMMINGS_GAME_TRANSITION_H
#define LEMMINGS_GAME_TRANSITION_H
#include "palette_transition.h"
#include "interrupt_service.h"
typedef enum LmnGameTransitionEntry {
    LMN_GAME_TRANSITION_ADVANCE,LMN_GAME_TRANSITION_OPENING,LMN_GAME_TRANSITION_CLOSING
} LmnGameTransitionEntry;
enum LmnGameTransitionStatus {
    LMN_GAME_TRANSITION_READY,LMN_GAME_TRANSITION_CHILD_STOP,
    LMN_GAME_TRANSITION_CHANGED_RETURN,LMN_GAME_TRANSITION_UNBOUND_SERVICE
};
typedef struct LmnGameTransitionServices {
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    const LmnInterruptService *int61;
} LmnGameTransitionServices;
typedef struct LmnGameTransitionResult {
    LmnRegs registers;uint16_t status,child_status,service_status;
} LmnGameTransitionResult;
/* Core leaves its active RET pending, including the shared 03D6 return.
   Child calls consume their real SS words and retain all returned CPU roles. */
LmnGameTransitionResult lmn_game_transition_core(uint8_t *,const LmnRegs *,
    LmnGameTransitionEntry,const LmnGameTransitionServices *);
LmnGameTransitionResult lmn_game_transition_adapter(uint8_t *,const LmnRegs *,
    LmnGameTransitionEntry,const LmnGameTransitionServices *);
#endif
