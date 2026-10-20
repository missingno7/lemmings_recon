#include "game_frame.h"
#include "game_foreground_internal.h"
#include "view_scroll.h"
#include "game_prepare.h"
#include "fixed_pattern_update.h"
#include "entity_action_dispatch.h"
#include "object_animation.h"
#include "object_drawing_tick.h"
#include "entity_drawing.h"
#include "entity_select.h"
#include "status_display_full.h"
#include "timer_tail.h"
#include "level_briefing.h"
#ifndef GAME_FRAME_MUTATION
#define GAME_FRAME_MUTATION 0
#endif
typedef struct Frame {
    LmnForegroundState cpu;LmnGameFrameResult *out;const LmnGameFrameServices *services;
} Frame;
static int poll_irq(Frame *f,uint16_t site) {
    LmnRegs *r=f->cpu.r;r->ip=site;
    const LmnForegroundPoll *poll=f->services?f->services->poll:0;
    if(poll&&poll->poll) {
        uint16_t status=poll->poll(poll->context,f->cpu.memory,r,site);
        if(status){f->out->status=LMN_GAME_FRAME_POLL_STOP;f->out->service_status=status;return 0;}
    }return 1;
}
static int software(Frame *f,uint16_t number,uint16_t resume) {
    const LmnGameFrameServices *v=f->services;
    LmnInterruptResult c=lmn_interrupt_service(f->cpu.memory,f->cpu.r,number,resume,
        v?(number==0x60?v->int60:v->int61):0,f->cpu.bus);
    if(c.status){f->out->status=c.status==LMN_INTERRUPT_UNBOUND_SERVICE?LMN_GAME_FRAME_UNBOUND_SERVICE:
        c.status==LMN_INTERRUPT_CHANGED_IRET?LMN_GAME_FRAME_CHANGED_RETURN:LMN_GAME_FRAME_CHILD_STOP;
        f->out->child_status=c.status;f->out->service_status=c.service_status;return 0;}
    return 1;
}
static int child(Frame *f,uint16_t entry,uint16_t resume) {
    LmnForegroundState *s=&f->cpu;LmnRegs *r=s->r;const LmnGameFrameServices *v=f->services;
    uint16_t cs=r->cs,status=0,changed=0,detail=0;
    fg_push(s,resume);r->ip=entry;
    if(entry==CS_AdvanceGameTransitionEffects) {
        LmnGameTransitionServices services={v?v->ports:0,s->bus,v?v->int61:0};
        LmnGameTransitionResult c=lmn_game_transition_adapter(s->memory,r,LMN_GAME_TRANSITION_ADVANCE,&services);
        *r=c.registers;status=c.status;detail=c.child_status;f->out->service_status=c.service_status;
        changed=status==LMN_GAME_TRANSITION_CHANGED_RETURN;
        if(status==LMN_GAME_TRANSITION_UNBOUND_SERVICE)f->out->status=LMN_GAME_FRAME_UNBOUND_SERVICE;
    } else if(entry==CS_HandleSelectorKeysAndEdgeScroll) {
        LmnViewScrollResult c=lmn_view_scroll_adapter(s->memory,r,LMN_VIEW_SCROLL_SELECTOR,s->bus);*r=c.registers;status=c.status;
    } else if(entry==CS_CopyDirtyLevelRowsToDrawingPage||entry==CS_CopyStatusBackdropToDrawingPage) {
        LmnGamePrepareResult c=lmn_game_prepare_adapter(s->memory,r,entry==CS_CopyDirtyLevelRowsToDrawingPage?
            LMN_GAME_PREPARE_DIRTY_ROWS:LMN_GAME_PREPARE_STATUS_BACKDROP,v?v->ports:0,s->bus);
        *r=c.registers;status=c.status;detail=c.child_status;changed=status==LMN_GAME_PREPARE_CHANGED_RETURN;
    } else if(entry==CS_DispatchEntityAction) {
        status=lmn_entity_action_dispatch_adapter(s->memory,r,v?v->pc:0,v?v->sound:0,s->bus);
    } else if(entry==CS_AdvanceLevelObjectAnimations) {
        status=lmn_advance_level_object_animations_adapter(s->memory,r,s->bus);
    } else if(entry==CS_DrawLevelObjectGraphics) {
        status=lmn_draw_level_object_graphics_adapter(s->memory,r,v?v->game_data_segment:0,s->bus,v?v->ports:0);
        changed=status==LMN_OBJECT_DRAWING_TICK_CHANGED_CHILD_NEAR||status==LMN_OBJECT_DRAWING_TICK_CHANGED_FAR_RETURN;
    } else if(entry==CS_DrawEntityRecords) {
        status=lmn_draw_entity_records_adapter(s->memory,r,s->bus);changed=status==LMN_ENTITY_DRAWING_CHANGED_CHILD_RETURN;
    } else if(entry==CS_SelectEntityCandidate) {
        status=lmn_select_entity_adapter(s->memory,r,s->bus);changed=status==LMN_ENTITY_SELECT_CHANGED_FORMATTER_RETURN;
    } else if(entry==CS_UpdateStatusDisplay) {
        status=lmn_update_status_display_full_adapter(s->memory,r,s->bus);
        changed=status==LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN;
    } else if(entry==CS_UpdateFixedWordPattern) {
        status=lmn_update_fixed_word_pattern_adapter(s->memory,r,s->bus);changed=status==LMN_FIXED_PATTERN_UPDATE_CHANGED_CHILD_RETURN;
    } else if(entry==CS_InstallGameTimerVector||entry==CS_RestoreTimerState) {
        LmnTimerTailResult c=entry==CS_InstallGameTimerVector?
            lmn_install_game_timer_adapter(s->memory,r,v?v->dos:0,v?v->ports:0,s->bus):
            lmn_restore_timer_interrupt_adapter(s->memory,r,v?v->bios_clock:0,v?v->ports:0,s->bus);
        *r=c.registers;status=c.status;detail=c.child_status;f->out->service_status=c.service_status;
        changed=status==LMN_TIMER_TAIL_CHANGED_CHILD_RETURN||status==LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN;
        if(status==LMN_TIMER_TAIL_UNBOUND_SERVICE)f->out->status=LMN_GAME_FRAME_UNBOUND_SERVICE;
    } else if(entry==CS_PublishBasePaletteBothBanks) {
        LmnBriefingResult c=lmn_briefing_helper_adapter(s->memory,r,LMN_BRIEFING_BASE_PALETTE,v?v->ports:0,s->bus);
        *r=c.registers;status=c.status;detail=c.child_status;changed=status==LMN_BRIEFING_CHANGED_RETURN;
    }
    if(status){if(!f->out->status)f->out->status=changed?LMN_GAME_FRAME_CHANGED_RETURN:LMN_GAME_FRAME_CHILD_STOP;
        f->out->child_entry=entry;f->out->child_status=status;
        if(!f->out->service_status)f->out->service_status=detail;
        return 0;}
    if(GAME_FRAME_MUTATION==4)r->ip=resume;
    if(r->cs!=cs||r->ip!=resume){f->out->status=LMN_GAME_FRAME_CHANGED_RETURN;f->out->child_entry=entry;return 0;}
    return 1;
}
static int input(Frame *f,uint16_t site) {
    LmnRegs *r=f->cpu.r;const LmnRasterBytePorts *p=f->services?f->services->ports:0;r->ip=site;
    if(!p||!p->in_byte){f->out->status=LMN_GAME_FRAME_CHILD_STOP;f->out->child_status=1;return 0;}
    fg_al(&f->cpu,p->in_byte(p->context,f->cpu.memory,r->dx,r->flags));return 1;
}
static int output_word(Frame *f,uint16_t site) {
    LmnRegs *r=f->cpu.r;r->ip=site;
    if(!f->cpu.bus||!f->cpu.bus->out_word){f->out->status=LMN_GAME_FRAME_CHILD_STOP;f->out->child_status=2;return 0;}
    f->cpu.bus->out_word(f->cpu.bus->context,r->dx,r->ax,r->flags);return 1;
}
LmnGameFrameResult lmn_game_frame_core(uint8_t *memory,const LmnRegs *registers,const LmnGameFrameServices *services) {
    LmnGameFrameResult out={*registers,0,0,0,0};LmnRegs *r=&out.registers;
    Frame f={{memory,services?services->bus:0,r},&out,services};LmnForegroundState *s=&f.cpu;
    if(r->ip==CS_GameFrameTickGate)goto tick_gate;
    r->ax=fg_read16(s,SEG09A9_AlternateDrawingOrigin);
    uint16_t old=fg_read16(s,SEG09A9_DrawingOrigin);fg_write16(s,SEG09A9_DrawingOrigin,r->ax);
    r->ax=old;fg_write16(s,SEG09A9_AlternateDrawingOrigin,r->ax);
    r->ax=fg_read16(s,SEG09A9_AlternateDrawingDirtyCellMapOffset);
    old=fg_read16(s,SEG09A9_DrawingDirtyCellMapOffset);fg_write16(s,SEG09A9_DrawingDirtyCellMapOffset,r->ax);
    r->ax=old;fg_write16(s,SEG09A9_AlternateDrawingDirtyCellMapOffset,r->ax);
    fg_cmp(s,fg_read8(s,SEG09A9_ConfigurationOption200E),255,1);
    if(!(r->flags&FG_ZF))goto wait;
raster_retry:
    fg_write8(s,SEG09A9_TimerChainFlag1FCF,0);r->dx=fg_read16(s,SEG09A9_DisplayControllerBasePort);
    fg_dl(s,fg_arithmetic(s,(uint8_t)r->dx,6,0,1));
    do{if(!input(&f,CS_GameFrameWaitRetraceEnd))return out;fg_logic(s,(uint8_t)r->ax&8u,1);}while(!(r->flags&FG_ZF));
    if(!poll_irq(&f,CS_GameFrameWaitRetraceEnd+5u))return out;
    fg_cmp(s,fg_read8(s,SEG09A9_TimerChainFlag1FCF),255,1);
    if(r->flags&FG_ZF){
        do{if(!input(&f,CS_GameFrameRetraceAfterTimerEdge))return out;fg_logic(s,(uint8_t)r->ax&8u,1);}while(r->flags&FG_ZF);
        goto raster_retry;
    }
    fg_dl(s,fg_arithmetic(s,(uint8_t)r->dx,6,1,1));r->flags&=(uint16_t)~FG_IF;
    r->bx=fg_read16(s,SEG09A9_AlternateDrawingOrigin);
    r->bx=fg_arithmetic(s,r->bx,fg_read16(s,SEG09A9_DrawingPageByteOffset),0,0);
    r->bx=fg_arithmetic(s,r->bx,2,0,0);r->ax=(uint16_t)((r->bx&0xFF00u)|12u);
    if(!output_word(&f,CS_GameFrameProgramDisplayStart+19u))return out;
    r->ax=(uint16_t)(((r->bx&255u)<<8)|(r->ax&255u));fg_al(s,fg_incdec(s,(uint8_t)r->ax,0,1));
    if(!output_word(&f,CS_GameFrameProgramDisplayStart+24u))return out;
    r->flags|=FG_IF;fg_dl(s,fg_arithmetic(s,(uint8_t)r->dx,6,0,1));
    do{if(!input(&f,CS_GameFrameWaitRetraceStart))return out;fg_logic(s,(uint8_t)r->ax&8u,1);}while(r->flags&FG_ZF);
    if(!child(&f,CS_UpdateFixedWordPattern,CS_GameFrameWaitForTimer))return out;
wait:
    r->cx=fg_read16(s,SEG09A9_ForegroundWaitLowWord);r->dx=fg_read16(s,SEG09A9_ForegroundWaitHighWord);
    fg_write8(s,SEG09A9_TimerChainFlag1FCF,0);
    for(;;){
        r->cx=fg_incdec(s,r->cx,1,0);
        if(r->flags&FG_ZF){fg_logic(s,r->dx,0);if(r->flags&FG_ZF){
                if(!child(&f,CS_InstallGameTimerVector,CS_GameFrameTickGate))return out;
                break;}
            r->dx=fg_incdec(s,r->dx,1,0);}
        if(!poll_irq(&f,CS_GameFrameWaitCheckTimerFlag))return out;
        fg_cmp(s,fg_read8(s,SEG09A9_TimerChainFlag1FCF),255,1);if(r->flags&FG_ZF)break;
    }
tick_gate:
    fg_al(s,fg_read8(s,SEG09A9_TimerForegroundCounter1FCD));r->cx=(uint16_t)((r->cx&0xFF00u)|4u);
    fg_cmp(s,(uint8_t)r->ax,(uint8_t)r->cx,1);
    if(GAME_FRAME_MUTATION==1?((uint8_t)r->ax<=4u):!fg_greater(s))goto wait;
    fg_write8(s,SEG09A9_TimerForegroundCounter1FCD,0);fg_write8(s,SEG09A9_KeyboardScanCodeByte,0);
    fg_incdec_memory(s,SEG09A9_ForegroundCounter1FD3,0);
    if(!child(&f,CS_AdvanceGameTransitionEffects,CS_GameFrameAfterTransition))return out;
    if(!child(&f,CS_HandleSelectorKeysAndEdgeScroll,CS_GameFrameAfterSelectorScroll))return out;
    fg_incdec_memory(s,SEG09A9_ForegroundCounter0052,0);
    if(!child(&f,CS_CopyDirtyLevelRowsToDrawingPage,CS_GameFrameAfterDirtyRows))return out;
    if(!child(&f,CS_CopyStatusBackdropToDrawingPage,CS_GameFrameAfterStatusBackdrop))return out;
    if(!child(&f,CS_DispatchEntityAction,CS_CreateAndAdvanceEntityRecords))return out;
    /* The connected two-call child owns exactly the01B0/01B3 frames. */
    {
        uint16_t status=lmn_entity_batch_adapter(memory,r,services?services->pc:0,services?services->sound:0,s->bus);
        if(status){out.status=status==LMN_ENTITY_BATCH_CHANGED_CALL_RETURN?LMN_GAME_FRAME_CHANGED_RETURN:LMN_GAME_FRAME_CHILD_STOP;
            out.child_entry=CS_CreateAndAdvanceEntityRecords;out.child_status=status;return out;}
    }
    if(!child(&f,CS_AdvanceLevelObjectAnimations,CS_GameFrameAfterObjectAnimations))return out;
    if(!child(&f,CS_DrawLevelObjectGraphics,CS_GameFrameAfterObjectGraphics))return out;
    if(!child(&f,CS_DrawEntityRecords,CS_GameFrameAfterEntityDrawing))return out;
    if(!child(&f,CS_SelectEntityCandidate,CS_GameFrameAfterSelection))return out;
    if(!child(&f,CS_UpdateStatusDisplay,CS_GameFrameAfterStatusDisplay))return out;
    if(GAME_FRAME_MUTATION!=2&&!child(&f,CS_DispatchEntityAction,CS_GameFrameAfterSecondDispatch))return out;
    fg_cmp(s,fg_read8(s,SEG09A9_GameEndRequested),255,1);if(r->flags&FG_ZF)goto end_wait;
    fg_cmp(s,fg_read8(s,SEG09A9_FrameDoubleWaitFlag004A),255,1);
    if(r->flags&FG_ZF){r->cx=2;do{
        fg_al(s,fg_read8(s,SEG09A9_TimerForegroundCounter1FCD));
        for(;;){if(!poll_irq(&f,CS_GameFrameDoubleWaitSpin))return out;
            if(!services||!services->poll||!services->poll->poll){out.status=LMN_GAME_FRAME_WAITING_FOR_IRQ;return out;}
            fg_cmp(s,fg_read8(s,SEG09A9_TimerForegroundCounter1FCD),(uint8_t)r->ax,1);
            if(!(r->flags&FG_ZF))break;}
        r->cx=(uint16_t)(r->cx-1u);
    }while(r->cx);}
    fg_al(s,fg_read8(s,SEG09A9_EntitySlotBound));fg_cmp(s,(uint8_t)r->ax,fg_read8(s,SEG09A9_LevelCreationLimit),1);
    if(r->flags&FG_ZF){fg_al(s,fg_read8(s,SEG09A9_EntityDrawingPassCount));fg_logic(s,(uint8_t)r->ax,1);if(r->flags&FG_ZF)goto fade_out;}
    fg_al(s,fg_read8(s,SEG09A9_LevelCountdownHighDigit));
    fg_al(s,(uint8_t)r->ax|fg_read8(s,SEG09A9_LevelCountdownTensDigit));fg_logic(s,(uint8_t)r->ax,1);
    fg_al(s,(uint8_t)r->ax|fg_read8(s,SEG09A9_LevelCountdownOnesDigit));fg_logic(s,(uint8_t)r->ax,1);
    fg_cmp(s,(uint8_t)r->ax,0x30,1);if(r->flags&FG_ZF)goto fade_out;
    fg_cmp(s,fg_read8(s,SEG09A9_EntityUpdateGate),255,1);if(r->flags&FG_ZF)goto commands;
    fg_incdec_memory(s,SEG09A9_GameCountdownTickCounter,1);if(!(r->flags&FG_ZF))goto commands;
    fg_al(s,fg_read8(s,SEG09A9_GameCountdownTickReload));fg_write8(s,SEG09A9_GameCountdownTickCounter,(uint8_t)r->ax);
    fg_al(s,fg_read8(s,SEG09A9_LevelCountdownHighDigit));r->bx=fg_read16(s,SEG09A9_LevelCountdownTensDigit);
    r->bx=(uint16_t)((r->bx&255u)|(fg_incdec(s,r->bx>>8,1,1)<<8));fg_cmp(s,r->bx>>8,0x2F,1);
    if(r->flags&FG_ZF){r->bx=(uint16_t)((r->bx&255u)|0x3900u);
        r->bx=(uint16_t)((r->bx&0xFF00u)|fg_incdec(s,(uint8_t)r->bx,1,1));fg_cmp(s,(uint8_t)r->bx,0x2F,1);
        if(r->flags&FG_ZF){r->bx=(uint16_t)((r->bx&0xFF00u)|0x35u);fg_al(s,fg_incdec(s,(uint8_t)r->ax,1,1));fg_cmp(s,(uint8_t)r->ax,0x2F,1);
            if(r->flags&FG_ZF){fg_al(s,0x30);r->bx=0x3030;}}}
    fg_write8(s,SEG09A9_LevelCountdownHighDigit,(uint8_t)r->ax);fg_write16(s,SEG09A9_LevelCountdownTensDigit,r->bx);
commands:
    r->ax=fg_read16(s,SEG09A9_InputKeyMask1FC7);fg_cmp(s,fg_read8(s,SEG09A9_SpecialLevelCodeLatch),255,1);
    if(r->flags&FG_ZF){fg_logic(s,r->ax&0x8000u,0);if(!(r->flags&FG_ZF)){
        fg_write8(s,SEG09A9_StatusCompletionDisplayValue,100);
        if(!child(&f,CS_PublishBasePaletteBothBanks,CS_GameLevelSkipAfterPalette))return out;
        goto end_wait;}}
    fg_logic(s,r->ax&0x80u,0);if(r->flags&FG_ZF)goto sound_enable;
    fg_push(s,r->ax);
    fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
    if(!(r->flags&FG_ZF)){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&1u,1);if(!(r->flags&FG_ZF)){
        r->ax=0x100;if(!software(&f,0x60,CS_GameFrameMusicToggleAfterInt60Stop))return out;}}
    fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
    if(!(r->flags&FG_ZF)){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&1u,1);if(!(r->flags&FG_ZF)){
        r->ax=0;if(!software(&f,0x60,CS_GameFrameMusicToggleRestore))return out;}}
    r->ax=fg_pop(s);fg_write8(s,SEG09A9_SoundOptionBits,0);
    fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
    if(r->flags&FG_ZF){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&3u,1);if(!(r->flags&FG_ZF)){
        r->ax=0x200;if(!software(&f,0x61,CS_GameFrameSoundEnableCheck))return out;}}
sound_enable:
    fg_logic(s,r->ax&0x100u,0);if(!(r->flags&FG_ZF))fg_write8(s,SEG09A9_SoundOptionBits,3);
    fg_logic(s,r->ax&0x20u,0);if(!(r->flags&FG_ZF))goto fade_out;goto next;
fade_out:
    fg_write8(s,SEG09A9_GameEndRequested,255);fg_al(s,fg_read8(s,SEG09A9_GameTransitionFlags));
    fg_al(s,(uint8_t)r->ax|2u);fg_logic(s,(uint8_t)r->ax,1);fg_write8(s,SEG09A9_GameTransitionFlags,(uint8_t)r->ax);goto next;
end_wait:
    fg_al(s,fg_read8(s,SEG09A9_GameTransitionFlags));fg_logic(s,(uint8_t)r->ax&2u,1);if(!(r->flags&FG_ZF))goto next;
    if(!child(&f,CS_PublishBasePaletteBothBanks,CS_GameEndAfterBasePalette))return out;
    fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
    if(!(r->flags&FG_ZF)){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&1u,1);if(!(r->flags&FG_ZF)){
        r->ax=0x100;if(!software(&f,0x60,CS_GameEndAfterInt60Stop))return out;}}
    fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
    if(!(r->flags&FG_ZF)){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&1u,1);if(!(r->flags&FG_ZF)){
        r->ax=0;if(!software(&f,0x60,CS_GameEndDisableDirtyCells))return out;}}
    fg_write8(s,SEG09A9_DrawingDirtyCellsEnabledByte,0);
    if(!child(&f,CS_RestoreTimerState,CS_GameEndAfterTimerRestore))return out;
    fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
    if(r->flags&FG_ZF){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&3u,1);if(!(r->flags&FG_ZF)){
        r->ax=0x200;if(!software(&f,0x61,CS_GameEndToResultScreen))return out;}}
    r->ip=CS_LevelResultScreen;out.status=LMN_GAME_FRAME_SESSION_EXIT;return out;
next:
    if(GAME_FRAME_MUTATION==3)fg_write8(s,SEG09A9_TimerForegroundCounter1FCD,0);
    r->ip=CS_GameFrameSwapAndPace;return out;
}
