#include "main_menu.h"
#include "lemmings_sym.h"
#include "display_status.h"
#include "display_start.h"
#include "display_pages.h"
#include "background_drawing.h"
#include "text_stream.h"
#include "palette_transition.h"

#ifndef MAIN_MENU_MUTATION
#define MAIN_MENU_MUTATION 0
#endif
enum { CF=1,PF=4,ZF=64,SF=128,OF=2048,ARITH=0x8d5 };
typedef struct Menu {
    uint8_t *memory;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t game_ds,status,child_status;
} Menu;
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint8_t read_at(Menu *s,uint32_t at) {
    at&=0xfffffu;
    return s->bus&&s->bus->read_byte?s->bus->read_byte(s->bus->context,s->memory,at,s->r.flags):s->memory[at];
}
static void write_at(Menu *s,uint32_t at,uint8_t v) {
    at&=0xfffffu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,v,s->r.flags);
    else s->memory[at]=v;
}
static uint8_t read8(Menu *s,uint16_t off) {return read_at(s,physical(s->r.ds,off));}
static void write8(Menu *s,uint16_t off,uint8_t v) {write_at(s,physical(s->r.ds,off),v);}
static uint16_t read16(Menu *s,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);uint8_t lo=read_at(s,at),hi=read_at(s,at+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write16(Menu *s,uint16_t off,uint16_t v) {
    uint32_t at=physical(s->r.ds,off);write_at(s,at,(uint8_t)v);write_at(s,at+1u,(uint8_t)(v>>8));
}
static void push(Menu *s,uint16_t v) {
    uint32_t at;s->r.sp=(uint16_t)(s->r.sp-2u);at=physical(s->r.ss,s->r.sp);
    write_at(s,at,(uint8_t)v);write_at(s,at+1u,(uint8_t)(v>>8));
}
static uint16_t pop(Menu *s) {
    uint16_t v=read16(s,s->r.ss,s->r.sp);s->r.sp=(uint16_t)(s->r.sp+2u);return v;
}
static uint16_t szp(uint16_t v,int byte) {
    unsigned parity=0;for(unsigned n=0;n<8u;++n)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0u:PF)|(v?0u:ZF)|(v&(byte?0x80u:0x8000u)?SF:0u));
}
static uint16_t arithmetic(Menu *s,uint16_t a,uint16_t b,int sub,int byte) {
    uint16_t v=(uint16_t)((sub?a-b:a+b)&(byte?0xffu:0xffffu)),sign=byte?0x80u:0x8000u;
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,byte)|((sub?a<b:(uint32_t)a+b>(byte?0xffu:0xffffu))?CF:0u)|
        ((a^b^v)&16u)|(((sub?(a^b):~(a^b))&(a^v)&sign)?OF:0u));return v;
}
static uint16_t logic(Menu *s,uint16_t v,int byte) {s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,byte));return v;}
static void cmp8(Menu *s,uint8_t a,uint8_t b) {(void)arithmetic(s,a,b,1,1);}
static void al(Menu *s,uint8_t v) {s->r.ax=(uint16_t)((s->r.ax&0xff00u)|v);}
static void ah(Menu *s,uint8_t v) {s->r.ax=(uint16_t)((s->r.ax&0xffu)|((uint16_t)v<<8));}
static uint8_t incdec8(Menu *s,uint8_t v,int dec) {
    uint16_t cf=s->r.flags&CF;v=(uint8_t)arithmetic(s,v,1u,dec,1);
    s->r.flags=(uint16_t)((s->r.flags&~CF)|cf);return v;
}
static uint8_t shl8(Menu *s,uint8_t v) {
    uint8_t out=(uint8_t)(v<<1);
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(out,1)|(v&0x80u?CF:0u)|((v^out)&0x80u?OF:0u));return out;
}
#define INPUT_FIELDS(s) (s)->r.ax,(s)->r.bx,(s)->r.cx,(s)->r.dx,(s)->r.si,(s)->r.di,(s)->r.bp, \
    (s)->r.ds,(s)->r.es,(s)->r.ss,(s)->r.sp,(s)->r.flags
static void apply(Menu *s,const LmnVideoRestoreState *v,uint16_t cs,uint16_t ip) {
    s->r=(LmnRegs){v->value,v->base_value,v->count,v->argument,v->source_cursor,v->output_cursor,
        v->frame_cursor,v->stack_offset,cs,v->data_segment,v->extra_segment,v->stack_segment,ip,v->flags};
}
static LmnVideoRestoreState from_display(const LmnDisplayStatusState *v) {
    LmnVideoRestoreState out={v->value,v->base_value,v->count,v->argument,v->source_cursor,v->output_cursor,
        v->frame_cursor,v->data_segment,v->extra_segment,v->stack_segment,v->stack_offset,v->flags};return out;
}
static int child(Menu *s,uint16_t target,uint16_t resume) {
    uint16_t cs=s->r.cs,child_cs=cs,ip=target,status=0;
    LmnVideoRestoreState in,out;
    push(s,resume);in=(LmnVideoRestoreState){INPUT_FIELDS(s)};
    if(target==CS_ReadKeyboardCharacter) {
        LmnKeyboardResult c=lmn_read_keyboard_character_core(s->memory,&s->r,s->bus);
        s->r=c.registers;status=c.status;
    } else {
        if(target==CS_WaitForDisplayStatusBit3Cycle) {
            LmnDisplayStatusState input={INPUT_FIELDS(s)};
            LmnDisplayStatusResult c=lmn_wait_display_status_bit3_cycle_core(s->memory,&input,s->ports,s->bus);
            out=from_display(&c.state);ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_SwapDrawingOriginsAndDisplay||target==CS_ProgramAlternateDisplayStart) {
            LmnDisplayStartState input={INPUT_FIELDS(s)};
            LmnDisplayStartResult c=lmn_program_display_start_core(s->memory,&input,
                target==CS_SwapDrawingOriginsAndDisplay?LMN_DISPLAY_START_ENTRY_SWAP:LMN_DISPLAY_START_ENTRY_SAVED,s->bus);
            out=from_display(&c.state);ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_AdvanceMenuScroll||target==CS_InitializeMenuScroll) {
            LmnMenuScrollResult c=lmn_menu_scroll_core(s->memory,cs,s->game_ds,&in,
                target==CS_AdvanceMenuScroll?LMN_MENU_SCROLL_TICK:LMN_MENU_SCROLL_INITIALIZE,s->bus,s->ports);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_AdvanceMenuAnimations||target==CS_InitializeMenuAnimations) {
            LmnMenuAnimationResult c=lmn_menu_animation_core(s->memory,cs,s->game_ds,&in,
                target==CS_AdvanceMenuAnimations?LMN_MENU_ANIMATION_TICK:LMN_MENU_ANIMATION_INITIALIZE,s->bus,s->ports);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_RefreshMenuSoundGraphic||target==CS_RefreshMenuLevelGroupGraphic) {
            LmnMenuCacheResult c=lmn_menu_cache_core(s->memory,cs,s->game_ds,&in,
                target==CS_RefreshMenuSoundGraphic?LMN_MENU_CACHE_SOUND:LMN_MENU_CACHE_LEVEL_GROUP,s->bus,s->ports);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_DrawMenuBackdropLayers||target==CS_DrawMenuDecorationRows) {
            LmnMenuDrawingResult c=lmn_menu_drawing_core(s->memory,cs,s->game_ds,&in,
                target==CS_DrawMenuBackdropLayers?LMN_MENU_DRAWING_BACKDROP:LMN_MENU_DRAWING_ROWS,s->bus,s->ports);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_ClearFullDrawingPage||target==CS_CopyDrawingPageToAlternate) {
            LmnDisplayPagesResult c=target==CS_ClearFullDrawingPage?
                lmn_clear_full_drawing_page_core(s->memory,&in,s->bus):lmn_copy_drawing_page_core(s->memory,&in,s->bus);
            out=c.state;ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_DrawScreenBackground) {
            LmnBackgroundDrawingResult c=lmn_draw_background_core(s->memory,cs,s->game_ds,&in,LMN_BACKGROUND_DRAWING_FULL,s->bus,s->ports);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        } else if(target==CS_DrawTextStream) {
            LmnTextStreamResult c=lmn_draw_text_stream_core(s->memory,cs,s->game_ds,&in,s->bus,s->ports);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        } else {
            LmnPaletteTransitionResult c=lmn_transition_palette_core(s->memory,cs,&in,
                target==CS_TransitionPaletteToSlot1?LMN_PALETTE_TRANSITION_SLOT1:LMN_PALETTE_TRANSITION_SLOT2,s->ports,s->bus);
            out=c.state;child_cs=c.code_segment;ip=c.continuation;status=(uint16_t)c.status;
        }
        apply(s,&out,child_cs,ip);
    }
    if(status){s->status=LMN_MAIN_MENU_CHILD_STOP;s->child_status=status;return 0;}
    s->r.ip=pop(s);
#if MAIN_MENU_MUTATION == 8
    s->r.ip=resume;
#endif
    if(s->r.cs!=cs||s->r.ip!=resume){s->status=LMN_MAIN_MENU_CHANGED_CHILD_RETURN;return 0;}
    return 1;
}
static LmnMainMenuResult result(Menu *s) {LmnMainMenuResult out={s->r,s->status,s->child_status};return out;}
static void group_selection(Menu *s) {
    al(s,shl8(s,(uint8_t)s->r.ax));ah(s,(uint8_t)s->r.ax);
    al(s,shl8(s,(uint8_t)s->r.ax));ah(s,(uint8_t)arithmetic(s,s->r.ax>>8,(uint8_t)s->r.ax,0,1));
    al(s,shl8(s,(uint8_t)s->r.ax));ah(s,(uint8_t)arithmetic(s,s->r.ax>>8,(uint8_t)s->r.ax,0,1));
    al(s,shl8(s,(uint8_t)s->r.ax));ah(s,(uint8_t)arithmetic(s,s->r.ax>>8,(uint8_t)s->r.ax,0,1));
#if MAIN_MENU_MUTATION == 6
    write8(s,SEG09A9_LevelResourceSelectionByte,(uint8_t)s->r.ax);
#else
    write8(s,SEG09A9_LevelResourceSelectionByte,(uint8_t)(s->r.ax>>8));
#endif
}
LmnMainMenuResult lmn_run_main_menu(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,enum LmnMainMenuEntry entry,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Menu s={memory,ports,bus,*registers,game_ds,0u,0u};
    if(entry==LMN_MAIN_MENU_FRAME)goto frame;
    if(entry==LMN_MAIN_MENU_KEYBOARD)goto keyboard;
    if(entry==LMN_MAIN_MENU_RELEASE)goto release;
    write16(&s,SEG09A9_DrawingOrigin,0u);write16(&s,SEG09A9_AlternateDrawingOrigin,0x6d60u);
    write16(&s,SEG09A9_DrawingPageByteOffset,0u);
    if(!child(&s,CS_ProgramAlternateDisplayStart,CS_MainMenuAfterCall4413))return result(&s);
    write8(&s,SEG09A9_MenuLevelGroupRedrawCache,0xffu);write8(&s,SEG09A9_MenuSoundRedrawCache,0xffu);
    write8(&s,SEG09A9_MenuSoundRedrawToggle,0u);
    if(!child(&s,CS_TransitionPaletteToSlot1,CS_MainMenuAfterCall4425)||
       !child(&s,CS_ClearFullDrawingPage,CS_MainMenuAfterCall4428)||
       !child(&s,CS_DrawScreenBackground,CS_MainMenuAfterCall442B)||
       !child(&s,CS_InitializeMenuScroll,CS_MainMenuAfterCall442E)||
       !child(&s,CS_InitializeMenuAnimations,CS_MainMenuAfterCall4431)||
       !child(&s,CS_DrawMenuBackdropLayers,CS_MainMenuAfterCall4434)||
       !child(&s,CS_DrawMenuDecorationRows,CS_MainMenuAfterCall4437))return result(&s);
    s.r.si=SEG09A9_MainMenuText;
    if(!child(&s,CS_DrawTextStream,CS_MainMenuAfterCall443E)||
       !child(&s,CS_RefreshMenuLevelGroupGraphic,CS_MainMenuAfterCall4441)||
       !child(&s,CS_RefreshMenuSoundGraphic,CS_MainMenuAfterCall4444)||
       !child(&s,CS_CopyDrawingPageToAlternate,CS_MainMenuAfterCall4447)||
       !child(&s,CS_WaitForDisplayStatusBit3Cycle,CS_MainMenuAfterCall444A)||
       !child(&s,CS_ProgramAlternateDisplayStart,CS_MainMenuAfterCall444D)||
       !child(&s,CS_TransitionPaletteToSlot2,CS_MainMenuAfterCall4450))return result(&s);
release:
    do {s.r.ax=read16(&s,s.r.ds,SEG09A9_InputButtonsWord);(void)logic(&s,s.r.ax&7u,0);} while(!(s.r.flags&ZF));
frame:
    if(!child(&s,CS_WaitForDisplayStatusBit3Cycle,CS_MainMenuAfterCall445B)||
       !child(&s,CS_AdvanceMenuScroll,CS_MainMenuAfterCall445E)||
       !child(&s,CS_AdvanceMenuAnimations,CS_MainMenuAfterCall4461)||
       !child(&s,CS_RefreshMenuLevelGroupGraphic,CS_MainMenuAfterCall4464)||
       !child(&s,CS_RefreshMenuSoundGraphic,CS_MainMenuAfterCall4467)||
       !child(&s,CS_SwapDrawingOriginsAndDisplay,CS_MainMenuAfterCall446A))return result(&s);
    s.r.ax=read16(&s,s.r.ds,SEG09A9_InputButtonsWord);(void)logic(&s,s.r.ax&7u,0);
    if(!(s.r.flags&ZF))goto start_level;
keyboard:
    if(!child(&s,CS_ReadKeyboardCharacter,CS_MainMenuAfterCall4478))return result(&s);
    cmp8(&s,(uint8_t)s.r.ax,0x80u);if(s.r.flags&ZF)goto start_level;
    cmp8(&s,(uint8_t)s.r.ax,0x81u);if(s.r.flags&ZF){s.r.ip=CS_MainMenuCodeTransition;return result(&s);}
    cmp8(&s,(uint8_t)s.r.ax,0x82u);if(s.r.flags&ZF)goto sound;
    cmp8(&s,(uint8_t)s.r.ax,0x83u);if(s.r.flags&ZF){s.r.ip=CS_ShowInputSelection4A01;return result(&s);}
    cmp8(&s,(uint8_t)s.r.ax,0x1bu);if(s.r.flags&ZF){s.r.ip=CS_DatFatalTransfer;return result(&s);}
    cmp8(&s,(uint8_t)s.r.ax,0x8au);if(s.r.flags&ZF)goto increase;
    cmp8(&s,(uint8_t)s.r.ax,0x60u);if(s.r.flags&ZF)goto increase;
    cmp8(&s,(uint8_t)s.r.ax,0x8bu);if(s.r.flags&ZF)goto decrease;
    cmp8(&s,(uint8_t)s.r.ax,0x2du);if(s.r.flags&ZF)goto decrease;
    goto frame;
sound:
    cmp8(&s,read8(&s,SEG09A9_MenuSoundRedrawCache),2u);
#if MAIN_MENU_MUTATION != 1
    if(s.r.flags&ZF)goto frame;
#endif
    {
        uint16_t incoming=s.r.flags;uint8_t value=(uint8_t)(read8(&s,SEG09A9_MenuSoundRedrawToggle)^0xffu);
        (void)logic(&s,value,1);
#if MAIN_MENU_MUTATION == 9
        (void)incoming;write8(&s,SEG09A9_MenuSoundRedrawToggle,value);
#else
        {uint16_t after=s.r.flags;s.r.flags=incoming;write8(&s,SEG09A9_MenuSoundRedrawToggle,value);s.r.flags=after;}
#endif
    }
    al(&s,read8(&s,SEG09A9_MenuSoundOptionIndex));al(&s,incdec8(&s,(uint8_t)s.r.ax,0));ah(&s,3u);
    {uint8_t driver=read8(&s,SEG09A9_ExternalSoundDriverEnabled);cmp8(&s,driver,0xffu);
#if MAIN_MENU_MUTATION == 2
    if(!driver)ah(&s,2u);
#else
    if(!(s.r.flags&ZF))ah(&s,2u);
#endif
    }
    cmp8(&s,(uint8_t)s.r.ax,(uint8_t)(s.r.ax>>8));
#if MAIN_MENU_MUTATION == 3
    if((uint8_t)s.r.ax>=(s.r.ax>>8))al(&s,(uint8_t)logic(&s,0u,1));
#else
    if(s.r.flags&ZF)al(&s,(uint8_t)logic(&s,0u,1));
#endif
    write8(&s,SEG09A9_MenuSoundOptionIndex,(uint8_t)s.r.ax);
    s.r.bx=(uint16_t)((s.r.bx&0xff00u)|(uint8_t)s.r.ax);s.r.bx&=0xffu;(void)logic(&s,0u,1);
    s.r.bx=arithmetic(&s,s.r.bx,CS_MenuSoundOptionValues,0,0);
#if MAIN_MENU_MUTATION == 4
    al(&s,read_at(&s,physical(s.r.ds,s.r.bx)));
#else
    al(&s,read_at(&s,physical(s.r.cs,s.r.bx)));
#endif
    write8(&s,SEG09A9_SoundOptionBits,(uint8_t)s.r.ax);goto frame;
increase:
    cmp8(&s,read8(&s,SEG09A9_MenuLevelGroupRedrawCache),4u);if(s.r.flags&ZF)goto frame;
    al(&s,read8(&s,SEG09A9_MenuLevelGroupIndex));cmp8(&s,(uint8_t)s.r.ax,3u);
#if MAIN_MENU_MUTATION == 5
    if((uint8_t)s.r.ax>=3u)goto frame;
#else
    if(s.r.flags&ZF)goto frame;
#endif
    al(&s,incdec8(&s,(uint8_t)s.r.ax,0));write8(&s,SEG09A9_MenuLevelGroupIndex,(uint8_t)s.r.ax);
    group_selection(&s);goto frame;
decrease:
    cmp8(&s,read8(&s,SEG09A9_MenuLevelGroupRedrawCache),4u);if(s.r.flags&ZF)goto frame;
    al(&s,read8(&s,SEG09A9_MenuLevelGroupIndex));al(&s,(uint8_t)logic(&s,(uint8_t)s.r.ax,1));if(s.r.flags&ZF)goto frame;
    al(&s,incdec8(&s,(uint8_t)s.r.ax,1));write8(&s,SEG09A9_MenuLevelGroupIndex,(uint8_t)s.r.ax);
    group_selection(&s);goto frame;
start_level:
#if MAIN_MENU_MUTATION == 7
    s.r.ip=CS_MainMenuCodeTransition;
#else
    s.r.ip=CS_MainMenuStartLevel;
#endif
    return result(&s);
}
