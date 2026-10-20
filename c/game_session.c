#include "game_session.h"
#include "game_foreground_internal.h"
#ifndef GAME_SESSION_MUTATION
#define GAME_SESSION_MUTATION 0
#endif
LmnGameSessionResult lmn_game_session_core(uint8_t *memory,const LmnRegs *registers,
    const LmnGameSessionServices *services) {
    LmnGameSessionResult out={*registers,0,0,0,0};LmnRegs *r=&out.registers;
    const LmnGameInitializeServices *init=services?services->initialize:0;
    LmnForegroundState cpu={memory,init?init->bus:0,r};
    uint16_t cs=r->cs;
    fg_push(&cpu,GAME_SESSION_MUTATION==3?0x00FF:0x00FE);
    r->ip=CS_InitializeGameSession;
    LmnGameInitializeResult initialized=lmn_initialize_game_core(memory,r,init);
    *r=initialized.registers;
    if(initialized.status!=LMN_GAME_INITIALIZE_RETURNED) {
        out.status=LMN_GAME_SESSION_INITIALIZE_STOP;out.child_entry=CS_InitializeGameSession;
        out.child_status=initialized.status;out.service_status=initialized.service_status;return out;
    }
    if(r->cs!=cs||r->ip!=0x00FE) {out.status=LMN_GAME_SESSION_CHANGED_RETURN;return out;}
    if(GAME_SESSION_MUTATION!=1)fg_write_at(&cpu,fg_physical(r->cs,CS_MouseIrqMirrorGate83BE),0);
    r->ip=CS_GameFrameSwapAndPace;
    for(;;) {
        if(services&&services->observe)services->observe(services->observer_context,memory,r);
        LmnGameFrameResult frame=lmn_game_frame_core(memory,r,services?services->frame:0);
        *r=frame.registers;
        if(frame.status==LMN_GAME_FRAME_SESSION_EXIT) {
            if(services&&services->observe)services->observe(services->observer_context,memory,r);
            return out;
        }
        if(frame.status!=LMN_GAME_FRAME_NEXT) {
            out.status=LMN_GAME_SESSION_FRAME_STOP;out.child_entry=frame.child_entry;
            out.child_status=frame.status;out.service_status=frame.service_status;return out;
        }
    }
}
