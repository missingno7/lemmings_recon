#ifndef LEMMINGS_GAME_FRAME_H
#define LEMMINGS_GAME_FRAME_H
#include "game_transition.h"
#include "foreground_poll.h"
#include "entity_batch.h"
typedef struct LmnGameFrameServices {
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    const LmnInterruptService *int60,*int61,*dos,*bios_clock;
    const LmnPcSpeakerBinding *pc;
    const LmnSoundDriverBinding *sound;
    const LmnForegroundPoll *poll;
    uint16_t game_data_segment;
} LmnGameFrameServices;
enum LmnGameFrameStatus {
    LMN_GAME_FRAME_NEXT,LMN_GAME_FRAME_SESSION_EXIT,LMN_GAME_FRAME_POLL_STOP,
    LMN_GAME_FRAME_CHILD_STOP,LMN_GAME_FRAME_CHANGED_RETURN,
    LMN_GAME_FRAME_UNBOUND_SERVICE,LMN_GAME_FRAME_WAITING_FOR_IRQ
};
typedef struct LmnGameFrameResult {
    LmnRegs registers;uint16_t status,child_entry,child_status,service_status;
} LmnGameFrameResult;
/* Enter at GameFrameSwapAndPace or GameFrameTickGate. NEXT stops on the JMP
   back to0105 before executing the next swap. EXIT stops at46EB. Timer IRQs
   enter only through the explicit foreground poll service; without one the
   split budget runs literally, and a stationary01DF spin returns WAITING. */
LmnGameFrameResult lmn_game_frame_core(uint8_t *,const LmnRegs *,const LmnGameFrameServices *);
#endif
