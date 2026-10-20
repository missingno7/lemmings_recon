#include "level_result.h"
#include "game_foreground_internal.h"
#include "display_pages.h"
#include "palette_transition.h"
#include "background_drawing.h"
#include "text_stream.h"
#include "timer_tail.h"
#include "main_menu.h"
#include "level_briefing.h"
#include "decimal_field.h"
#ifndef LEVEL_RESULT_MUTATION
#define LEVEL_RESULT_MUTATION 0
#endif

typedef struct ResultScreen {
    LmnForegroundState cpu;
    LmnLevelResultResult *out;
    const LmnLevelResultServices *services;
} ResultScreen;
static LmnVideoRestoreState state(const LmnRegs *r) {
    LmnVideoRestoreState v={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,
        r->ds,r->es,r->ss,r->sp,r->flags};return v;
}
static void apply(LmnRegs *r,const LmnVideoRestoreState *v,uint16_t cs,uint16_t ip) {
    *r=(LmnRegs){v->value,v->base_value,v->count,v->argument,v->source_cursor,
        v->output_cursor,v->frame_cursor,v->stack_offset,cs,v->data_segment,
        v->extra_segment,v->stack_segment,ip,v->flags};
}
static int child(ResultScreen *,uint16_t,uint16_t);
static int body(ResultScreen *f,uint16_t entry) {
    LmnForegroundState *s=&f->cpu;LmnRegs *r=s->r;
    const LmnLevelResultServices *v=f->services;
    const LmnRasterBytePorts *ports=v?v->ports:0;
    uint16_t cs=r->cs,status=0,changed=0;
    LmnVideoRestoreState in=state(r);
    r->ip=entry;
    if(entry==CS_DrawResultPercentagesAndPrompt) {
        fg_al(s,fg_read8(s,SEG09A9_StatusCompletionDisplayValue));r->si=0x4C5D;
        if(!child(f,CS_WritePercentageByteField,0x48C7))return 0;
        fg_al(s,fg_read8(s,0x41));r->si=0x4C71;
        if(!child(f,CS_WritePercentageByteField,0x48D1))return 0;
        r->si=0x4C77;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),0,1);
        if(!(r->flags&FG_ZF)) {
            r->si=0x4C9D;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),1,1);
            if(!(r->flags&FG_ZF))r->si=0x4CB9;
        }
        fg_write16(s,SEG09A9_UiScrollPhaseOrPromptPointer,r->si);r->si=0x4C4E;
        return body(f,CS_DrawTextStream);
    }
    if(entry==CS_DrawResultAssessmentMessage) {
        fg_al(s,fg_read8(s,SEG09A9_StatusCompletionDisplayValue));r->ax&=255u;fg_logic(s,0,1);
        fg_dl(s,fg_read8(s,0x41));r->dx&=255u;fg_logic(s,0,1);
        r->bx=16;fg_cmp(s,r->ax,100,0);if(r->flags&FG_ZF)goto message;
        r->bx=0;fg_logic(s,0,0);fg_logic(s,r->ax,0);if(r->flags&FG_ZF)goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);r->cx=r->dx;r->cx=fg_shr_one(s,r->cx);
        fg_cmp(s,r->ax,r->cx,0);if(fg_less(s))goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);r->cx=r->dx;r->cx=fg_arithmetic(s,r->cx,5,1,0);
        fg_cmp(s,r->ax,r->cx,0);if(fg_less(s))goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);r->cx=r->dx;r->cx=fg_incdec(s,r->cx,1,0);
        fg_cmp(s,r->ax,r->cx,0);if(fg_less(s))goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);fg_cmp(s,r->ax,r->cx,0);if(r->flags&FG_ZF)goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);fg_cmp(s,r->ax,r->dx,0);if(r->flags&FG_ZF)goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);r->cx=r->dx;r->cx=fg_arithmetic(s,r->cx,20,0,0);
        fg_cmp(s,r->ax,r->cx,0);if(fg_less(s))goto message;
        r->bx=fg_arithmetic(s,r->bx,2,0,0);
message:
        r->si=fg_word(s,LEVEL_RESULT_MUTATION==7?r->ds:r->cs,(uint16_t)(r->bx+0x4955u));
        return body(f,CS_DrawTextStream);
    }
    if(entry==CS_FormatSelectedLevelAndGroup||entry==CS_EncodeLevelCode) {
        LmnMainMenuResult c=entry==CS_FormatSelectedLevelAndGroup?
            lmn_format_selected_level_core(s->memory,r,s->bus):lmn_encode_level_code_core(s->memory,r,s->bus);
        *r=c.registers;status=c.status;changed=status==LMN_MAIN_MENU_CHANGED_CHILD_RETURN;
    } else if(entry==CS_WriteDecimalByteField) {
        LmnDecimalFieldCall call={r->ds,r->ax,r->bx,r->si,r->flags};
        LmnDecimalFieldResult c=lmn_write_decimal_field_core(s->memory,&call,s->bus);
        r->ax=c.value;r->bx=c.prefix_value;r->si=c.cursor;r->flags=c.flags;
    } else if(entry==CS_WritePercentageByteField) {
        LmnBriefingResult c=lmn_briefing_helper_core(s->memory,r,LMN_BRIEFING_PERCENT,ports,s->bus);
        *r=c.registers;status=c.status;changed=status==LMN_BRIEFING_CHANGED_RETURN;
    } else if(entry==CS_InstallMenuTimerVector) {
        LmnTimerTailResult c=lmn_install_menu_timer_core(s->memory,r,s->bus);
        *r=c.registers;status=c.status;f->out->service_status=c.service_status;
    } else if(entry==CS_ClearFullDrawingPage) {
        LmnDisplayPagesResult c=lmn_clear_full_drawing_page_core(s->memory,&in,s->bus);
        apply(r,&c.state,cs,c.continuation);status=(uint16_t)c.status;
    } else if(entry==CS_SetupDisplayModeAndLayout) {
        LmnDisplaySetupResult c=lmn_setup_display_core(s->memory,cs,&in,LMN_DISPLAY_SETUP_ENTRY_FULL,v?v->video:0,s->bus);
        apply(r,&c.state,c.code_segment,c.continuation);status=(uint16_t)c.status;changed=status==LMN_DISPLAY_SETUP_CHANGED_RETURN;
    } else if(entry==CS_PublishMenuPalette) {
        LmnPalettePublishResult c=lmn_publish_palette_core(s->memory,r,LMN_PALETTE_PUBLISH_MENU,ports,s->bus);
        *r=c.registers;status=c.status;
    } else if(entry==CS_TransitionPaletteToSlot1||entry==CS_TransitionPaletteToSlot2) {
        LmnPaletteTransitionResult c=lmn_transition_palette_core(s->memory,cs,&in,
            entry==CS_TransitionPaletteToSlot1?LMN_PALETTE_TRANSITION_SLOT1:LMN_PALETTE_TRANSITION_SLOT2,ports,s->bus);
        apply(r,&c.state,c.code_segment,c.continuation);status=(uint16_t)c.status;
        changed=status==LMN_PALETTE_TRANSITION_CHANGED_RETURN||status==LMN_PALETTE_TRANSITION_ROW_CHANGED_RETURN;
    } else if(entry==CS_DrawScreenBackground) {
        LmnBackgroundDrawingResult c=lmn_draw_background_core(s->memory,cs,v?v->game_data_segment:0,&in,LMN_BACKGROUND_DRAWING_FULL,s->bus,ports);
        apply(r,&c.state,c.code_segment,c.continuation);status=(uint16_t)c.status;changed=status==LMN_BACKGROUND_DRAWING_CHANGED_RETURN;
    } else if(entry==CS_DrawTextStream) {
        LmnTextStreamResult c=lmn_draw_text_stream_core(s->memory,cs,v?v->game_data_segment:0,&in,s->bus,ports);
        apply(r,&c.state,c.code_segment,c.continuation);status=(uint16_t)c.status;changed=status==LMN_TEXT_STREAM_CHANGED_RETURN;
    }
    if(status) {
        f->out->status=changed?LMN_LEVEL_RESULT_CHANGED_RETURN:LMN_LEVEL_RESULT_CHILD_STOP;
        f->out->child_entry=entry;f->out->child_status=status;return 0;
    }
    return 1;
}
static int child(ResultScreen *f,uint16_t entry,uint16_t resume) {
    LmnRegs *r=f->cpu.r;uint16_t cs=r->cs;fg_push(&f->cpu,resume);
    if(!body(f,entry))return 0;
    r->ip=fg_pop(&f->cpu);
    if(LEVEL_RESULT_MUTATION==8)r->ip=resume;
    if(r->cs!=cs||r->ip!=resume) {
        f->out->status=LMN_LEVEL_RESULT_CHANGED_RETURN;f->out->child_entry=entry;return 0;
    }
    return 1;
}
static int poll(ResultScreen *f,uint16_t site) {
    LmnRegs *r=f->cpu.r;r->ip=site;
    const LmnForegroundPoll *p=f->services?f->services->poll:0;
    if(p&&p->poll) {
        uint16_t status=p->poll(p->context,f->cpu.memory,r,site);
        if(status){f->out->status=LMN_LEVEL_RESULT_POLL_STOP;f->out->service_status=status;return 0;}
    }
    return 1;
}
static int waiting(ResultScreen *f,uint16_t site) {
    const LmnForegroundPoll *p=f->services?f->services->poll:0;
    if(!p||!p->poll){f->cpu.r->ip=site;f->out->status=LMN_LEVEL_RESULT_WAITING;return 1;}return 0;
}
LmnLevelResultResult lmn_level_result_core(uint8_t *memory,const LmnRegs *registers,const LmnLevelResultServices *services) {
    LmnLevelResultResult out={*registers,0,0,0,0};LmnRegs *r=&out.registers;
    ResultScreen f={{memory,services?services->bus:0,r},&out,services};LmnForegroundState *s=&f.cpu;
    switch(r->ip) {
    case CS_DrawResultPercentagesAndPrompt:case CS_DrawResultAssessmentMessage:body(&f,r->ip);return out;
    case CS_ResultWaitButtonsReleased:goto release;
    case CS_ResultWaitChoice:goto choice;
    case 0x47BE:goto keys;
    case 0x480A:goto final_choice;
    case 0x4812:goto final_keys;
    case CS_LevelResultScreen:break;
    default:out.status=LMN_LEVEL_RESULT_INVALID_ENTRY;return out;
    }
    static const uint16_t entries[]={CS_ClearFullDrawingPage,CS_SetupDisplayModeAndLayout,CS_PublishMenuPalette,
        CS_TransitionPaletteToSlot1,CS_ClearFullDrawingPage,CS_InstallMenuTimerVector,CS_DrawScreenBackground,CS_DrawResultPercentagesAndPrompt};
    for(unsigned n=0;n<8;n++)if(!child(&f,entries[n],(uint16_t)(0x46EEu+3u*n)))return out;
    r->si=0x4C19;fg_al(s,fg_read8(s,SEG09A9_LevelCountdownHighDigit));r->bx=fg_read16(s,0x20A9);
    r->bx=(uint16_t)((r->bx&0xFF00u)|((r->bx|(uint8_t)r->ax)&255u));fg_logic(s,(uint8_t)r->bx,1);
    fg_cmp(s,r->bx,0x3030,0);
    if(LEVEL_RESULT_MUTATION==5?!!(r->flags&FG_ZF):!(r->flags&FG_ZF))r->si=0x4C2E;
    if(!child(&f,CS_DrawTextStream,0x471D))return out;
    fg_al(s,fg_read8(s,SEG09A9_StatusCompletionDisplayValue));fg_cmp(s,(uint8_t)r->ax,fg_read8(s,0x41),1);
    if(LEVEL_RESULT_MUTATION==1?!!(r->flags&FG_CF):fg_less(s))goto failed;
    fg_write8(s,SEG09A9_LevelOutcomeSuccessByte,255);fg_incdec_memory(s,SEG09A9_LevelResourceSelectionByte,0);
    fg_al(s,fg_read8(s,SEG09A9_LevelResourceSelectionByte));r->ax&=255u;fg_logic(s,0,1);
    r->cx=(uint16_t)((r->cx&0xFF00u)|30u);r->ip=0x4739;
    /* DIV leaves arithmetic flags undefined; retain them without inventing a
       result. Its actual byte divisor is fixed30 here, so fault is unreachable
       in the unmodified body, but the arithmetic check stays explicit. */
    {uint16_t divisor=r->cx&255u,value=r->ax;
        if(!divisor||value/divisor>255u){out.status=LMN_LEVEL_RESULT_DIVIDE_ERROR;return out;}
        r->ax=(uint16_t)(((value%divisor)<<8)|(value/divisor));}
    fg_write8(s,SEG09A9_MenuLevelGroupIndex,(uint8_t)r->ax);
    fg_cmp(s,fg_read8(s,SEG09A9_LevelResourceSelectionByte),LEVEL_RESULT_MUTATION==2?0x79:0x78,1);
    if(!(r->flags&FG_CF))goto final_screen;
    if(!child(&f,CS_FormatSelectedLevelAndGroup,0x474B))return out;
    r->si=0x4D5D;if(!child(&f,CS_WriteDecimalByteField,0x4752))return out;
    if(LEVEL_RESULT_MUTATION!=6&&!child(&f,CS_EncodeLevelCode,0x4755))return out;
    r->si=0x4D3F;if(!child(&f,CS_DrawTextStream,0x475C))return out;
    r->bx=0x4D75;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),0,1);
    if(!(r->flags&FG_ZF)){r->bx=0x4DA0;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),1,1);if(!(r->flags&FG_ZF))r->bx=0x4DC2;}
    goto prompts;
failed:
    fg_write8(s,SEG09A9_LevelOutcomeSuccessByte,0);r->bx=0x4CD3;
    fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),0,1);
    if(!(r->flags&FG_ZF)){r->bx=0x4CFE;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),1,1);if(!(r->flags&FG_ZF))r->bx=0x4D20;}
prompts:
    fg_push(s,r->bx);if(!child(&f,CS_DrawResultAssessmentMessage,0x479B))return out;r->si=fg_pop(s);
    if(!child(&f,CS_DrawTextStream,0x479F))return out;
    r->si=fg_read16(s,SEG09A9_UiScrollPhaseOrPromptPointer);
    if(!child(&f,CS_DrawTextStream,0x47A6)||!child(&f,CS_TransitionPaletteToSlot2,0x47A9))return out;
release:
    if(!poll(&f,0x47A9))return out;
    r->ax=fg_read16(s,SEG09A9_InputButtonsWord);fg_logic(s,r->ax&7u,0);
    if(LEVEL_RESULT_MUTATION!=3&&!(r->flags&FG_ZF)){if(waiting(&f,0x47A9))return out;
    goto release;}
choice:
    if(!poll(&f,0x47B1))return out;
    r->ax=fg_read16(s,SEG09A9_InputButtonsWord);fg_logic(s,r->ax&1u,0);
    if(!(r->flags&FG_ZF))goto start;
    fg_logic(s,r->ax&2u,0);if(!(r->flags&FG_ZF))goto menu;
keys:
    if(!poll(&f,0x47BE))return out;
    r->ax=fg_read16(s,SEG09A9_InputKeyMask1FC7);fg_logic(s,r->ax&0x20u,0);
    if(!(r->flags&FG_ZF))goto menu;
    fg_logic(s,r->ax&(LEVEL_RESULT_MUTATION==4?0x80u:0x40u),0);if(!(r->flags&FG_ZF))goto menu;
    if(waiting(&f,0x47B1))return out;
    goto choice;
menu:
    if(!child(&f,CS_TransitionPaletteToSlot1,0x47CE)||!child(&f,CS_ClearFullDrawingPage,0x47D1)||
       !child(&f,CS_SetupDisplayModeAndLayout,0x47D4))return out;
    r->ip=0x4401;out.status=LMN_LEVEL_RESULT_MAIN_MENU;return out;
start:
    if(!child(&f,CS_TransitionPaletteToSlot1,0x47DA)||!child(&f,CS_ClearFullDrawingPage,0x47DD))return out;
    r->ip=0x4551;out.status=LMN_LEVEL_RESULT_START_LEVEL;return out;
final_screen:
    if(!child(&f,CS_DrawScreenBackground,0x47E3))return out;
    r->si=0x51CB;if(!child(&f,CS_DrawTextStream,0x47EA))return out;
    r->si=0x4BA0;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),0,1);
    if(!(r->flags&FG_ZF)){r->si=0x4BC3;fg_cmp(s,fg_read8(s,SEG09A9_InputModeByte25A6),1,1);if(!(r->flags&FG_ZF))r->si=0x4BE5;}
    if(!child(&f,CS_DrawTextStream,0x4807)||!child(&f,CS_TransitionPaletteToSlot2,0x480A))return out;
final_choice:
    if(!poll(&f,0x480A))return out;
    r->ax=fg_read16(s,SEG09A9_InputButtonsWord);fg_logic(s,r->ax&7u,0);
    if(!(r->flags&FG_ZF))goto final_exit;
final_keys:
    if(!poll(&f,0x4812))return out;
    r->ax=fg_read16(s,SEG09A9_InputKeyMask1FC7);fg_logic(s,r->ax&0x20u,0);
    if(!(r->flags&FG_ZF))goto final_exit;
    fg_logic(s,r->ax&0x40u,0);if(!(r->flags&FG_ZF))goto final_exit;
    if(waiting(&f,0x480A))return out;
    goto final_choice;
final_exit:
    if(!child(&f,CS_TransitionPaletteToSlot1,0x4822))return out;
    fg_write8(s,SEG09A9_LevelResourceSelectionByte,0);fg_write8(s,SEG09A9_MenuLevelGroupIndex,0);
    r->ip=0x4401;out.status=LMN_LEVEL_RESULT_MAIN_MENU;return out;
}
LmnLevelResultResult lmn_level_result_adapter(uint8_t *memory,const LmnRegs *registers,const LmnLevelResultServices *services) {
    LmnLevelResultResult out=lmn_level_result_core(memory,registers,services);
    if(!out.status&&(registers->ip==CS_DrawResultPercentagesAndPrompt||registers->ip==CS_DrawResultAssessmentMessage)) {
        LmnForegroundState s={memory,services?services->bus:0,&out.registers};out.registers.ip=fg_pop(&s);
    }
    return out;
}
