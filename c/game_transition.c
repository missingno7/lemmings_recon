#include "game_transition.h"
#include "game_foreground_internal.h"
#ifndef GAME_TRANSITION_MUTATION
#define GAME_TRANSITION_MUTATION 0
#endif
typedef struct Transition {
    LmnForegroundState cpu;
    LmnGameTransitionResult *out;
    const LmnGameTransitionServices *services;
} Transition;
static int returned(Transition *t,uint16_t cs,uint16_t resume) {
    LmnRegs *r=t->cpu.r;
    if(t->out->status)return 0;
    if(r->cs!=cs||r->ip!=resume) {t->out->status=LMN_GAME_TRANSITION_CHANGED_RETURN;return 0;}
    return 1;
}
static int software61(Transition *t,uint16_t resume) {
    LmnInterruptResult child=lmn_interrupt_service(t->cpu.memory,t->cpu.r,0x61,resume,
        t->services?t->services->int61:0,t->cpu.bus);
    if(child.status) {
        t->out->status=child.status==LMN_INTERRUPT_UNBOUND_SERVICE?LMN_GAME_TRANSITION_UNBOUND_SERVICE:
            child.status==LMN_INTERRUPT_CHANGED_IRET?LMN_GAME_TRANSITION_CHANGED_RETURN:LMN_GAME_TRANSITION_CHILD_STOP;
        t->out->child_status=child.status;t->out->service_status=child.service_status;return 0;
    }return 1;
}
static int palette_step(Transition *t,int opening) {
    LmnForegroundState *s=&t->cpu;LmnRegs *r=s->r;
    if(opening){fg_al(s,(uint8_t)r->ax|4u);fg_logic(s,(uint8_t)r->ax,1);}
    fg_push(s,r->ax);
    if(opening)r->bx=0x0604;
    r->cx=16;r->dx=8;
    uint16_t resume=opening?CS_OpeningFadeAfterPaletteStep:CS_ClosingFadeAfterPaletteStep,cs=r->cs;
    fg_push(s,resume);r->ip=opening?CS_StepSplitPaletteToTargets:CS_StepSplitPaletteToSlot1;
    LmnPaletteTransitionResult child=lmn_step_split_palette_adapter(s->memory,r,
        opening?LMN_SPLIT_PALETTE_TO_TARGETS:LMN_SPLIT_PALETTE_TO_SLOT1,s->bus);
    if(child.status){t->out->status=child.status==LMN_PALETTE_TRANSITION_ROW_CHANGED_RETURN||
        child.status==LMN_PALETTE_TRANSITION_CHANGED_RETURN?LMN_GAME_TRANSITION_CHANGED_RETURN:LMN_GAME_TRANSITION_CHILD_STOP;
        t->out->child_status=(uint16_t)child.status;return 0;}
    if(!returned(t,cs,resume))return 0;
    r->ax=fg_pop(s);
    /* POP AX must leave the palette child's ZF available to JNZ. */
    int complete=(r->flags&FG_ZF)!=0;
    if(complete&&GAME_TRANSITION_MUTATION!=1) {
        fg_al(s,(uint8_t)r->ax&(opening?0xFEu:0xFDu));fg_logic(s,(uint8_t)r->ax,1);
    }
    r->ip=(!opening&&complete)?CS_ClosingFadeAfterPaletteStep+5u:CS_TransitionSharedReturn;
    return 1;
}
static int raster_cycle(Transition *t,int opening) {
    LmnForegroundState *s=&t->cpu;LmnRegs *r=s->r;uint16_t cs=r->cs;
    fg_push(s,r->ax);
    uint16_t resume=opening?CS_TransitionOpeningRasterAfterStatus:CS_TransitionClosingRasterAfterStatus;
    fg_push(s,resume);r->ip=CS_WaitForDisplayStatusBit3Cycle;
    LmnDisplayStatusState in={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,
        r->ds,r->es,r->ss,r->sp,r->flags};
    LmnDisplayStatusResult child=lmn_wait_display_status_bit3_cycle_core(s->memory,&in,
        t->services?t->services->ports:0,s->bus);
    r->ax=child.state.value;r->bx=child.state.base_value;r->cx=child.state.count;r->dx=child.state.argument;
    r->si=child.state.source_cursor;r->di=child.state.output_cursor;r->bp=child.state.frame_cursor;
    r->ds=child.state.data_segment;r->es=child.state.extra_segment;r->ss=child.state.stack_segment;
    r->sp=child.state.stack_offset;r->flags=child.state.flags;r->ip=child.continuation;
    if(child.status){t->out->status=LMN_GAME_TRANSITION_CHILD_STOP;t->out->child_status=(uint16_t)child.status;return 0;}
    r->ip=fg_pop(s);if(!returned(t,cs,resume))return 0;
    resume=opening?CS_TransitionOpeningRasterAfterTimerPalette:CS_TransitionClosingRasterAfterTimerPalette;
    cs=r->cs;fg_push(s,resume);r->ip=CS_UpdateTimerPaletteAfter553D;
    LmnTimerPaletteResult palette=lmn_timer_palette_adapter(s->memory,r,LMN_TIMER_PALETTE_ENTRY_AFTER,
        t->services?t->services->ports:0,s->bus);*r=palette.registers;
    if(palette.status){t->out->status=palette.status==LMN_TIMER_PALETTE_CHANGED_CHILD_RETURN?
        LMN_GAME_TRANSITION_CHANGED_RETURN:LMN_GAME_TRANSITION_CHILD_STOP;t->out->child_status=palette.status;return 0;}
    if(!returned(t,cs,resume))return 0;
    r->ax=fg_pop(s);return 1;
}
LmnGameTransitionResult lmn_game_transition_core(uint8_t *memory,const LmnRegs *registers,
    LmnGameTransitionEntry entry,const LmnGameTransitionServices *services) {
    LmnGameTransitionResult out={*registers,0,0,0};LmnRegs *r=&out.registers;
    Transition t={{memory,services?services->bus:0,r},&out,services};LmnForegroundState *s=&t.cpu;
    if(entry!=LMN_GAME_TRANSITION_ADVANCE){(void)palette_step(&t,entry==LMN_GAME_TRANSITION_OPENING);return out;}
    fg_al(s,fg_read8(s,SEG09A9_GameTransitionFlags));fg_logic(s,(uint8_t)r->ax&1u,1);
    int opening=(r->flags&FG_ZF)==0;
    if(!opening){fg_logic(s,(uint8_t)r->ax&2u,1);if(r->flags&FG_ZF)goto cues;}
    fg_cmp(s,fg_read8(s,SEG09A9_ConfigurationOption200E),255,1);
    int raster=(r->flags&FG_ZF)!=0;
    do {
        uint16_t resume=opening?(raster?CS_TransitionOpeningRasterAfterStep:CS_TransitionOpeningAfterStep):
            (raster?CS_TransitionClosingRasterAfterStep:CS_TransitionDelayedCueCheck),cs=r->cs;
        fg_push(s,resume);r->ip=opening?CS_StepGameOpeningFade:CS_StepGameClosingFade;
        if(!palette_step(&t,opening))return out;
        r->ip=fg_pop(s);if(!returned(&t,cs,resume))return out;
        if(!raster)break;
        if(!raster_cycle(&t,opening))return out;
        fg_logic(s,(uint8_t)r->ax&(opening?1u:2u),1);
        if(GAME_TRANSITION_MUTATION==2)break;
    }while(!(r->flags&FG_ZF));
cues:
    fg_logic(s,(uint8_t)r->ax&4u,1);if(r->flags&FG_ZF)goto publish;
    fg_dl(s,fg_read8(s,SEG09A9_ForegroundCounter0052));
    fg_cmp(s,(uint8_t)r->dx,15,1);
    if(r->flags&FG_ZF) {
        fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
        if(r->flags&FG_ZF){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&3u,1);
            if(!(r->flags&FG_ZF)){r->ax=0x403;if(!software61(&t,CS_TransitionCue0FReturn))return out;}}
        r->ip=CS_TransitionCue0FReturn;goto early;
    }
    fg_cmp(s,(uint8_t)r->dx,35,1);
    if(r->flags&FG_ZF) {
        fg_write8(s,SEG09A9_EntityCreationGate,255);
        fg_cmp(s,fg_read8(s,SEG09A9_ExternalSoundDriverEnabled),255,1);
        if(r->flags&FG_ZF){fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&3u,1);
            if(!(r->flags&FG_ZF)){r->ax=0x402;if(!software61(&t,CS_TransitionCue23Return))return out;}}
        r->ip=CS_TransitionCue23Return;goto early;
    }
    fg_cmp(s,(uint8_t)r->dx,55,1);
    if(r->flags&FG_ZF) {
        fg_logic(s,fg_read8(s,SEG09A9_SoundOptionBits)&2u,1);
        if(r->flags&FG_ZF){r->ip=CS_TransitionSharedReturn;goto early;}
        fg_al(s,fg_read8(s,SEG09A9_LevelSoundId));r->ax=(uint16_t)((r->ax&255u)|0x300u);
        if(!software61(&t,CS_TransitionCue37AfterSelect))return out;
        r->ax=0;if(!software61(&t,CS_TransitionCue37Return))return out;
        r->ip=CS_TransitionCue37Return;goto early;
    }
    if(!(r->flags&FG_CF)){fg_al(s,(uint8_t)r->ax&0xFBu);fg_logic(s,(uint8_t)r->ax,1);}
publish:
    fg_write8(s,SEG09A9_GameTransitionFlags,(uint8_t)r->ax);r->ip=CS_TransitionPublishFlags+3u;return out;
early:
    if(GAME_TRANSITION_MUTATION==3)fg_write8(s,SEG09A9_GameTransitionFlags,(uint8_t)r->ax);
    return out;
}
LmnGameTransitionResult lmn_game_transition_adapter(uint8_t *memory,const LmnRegs *registers,
    LmnGameTransitionEntry entry,const LmnGameTransitionServices *services) {
    LmnGameTransitionResult out=lmn_game_transition_core(memory,registers,entry,services);
    if(!out.status){LmnForegroundState s={memory,services?services->bus:0,&out.registers};out.registers.ip=fg_pop(&s);}
    return out;
}
