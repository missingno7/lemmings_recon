#include "main_menu.h"
#include "lemmings_sym.h"
#include "display_status.h"
#include "display_start.h"
#include "display_pages.h"
#include "background_drawing.h"
#include "text_stream.h"
#include "palette_transition.h"
#include "timer_tail.h"
#include "decimal_field.h"

#ifndef MAIN_MENU_MUTATION
#define MAIN_MENU_MUTATION 0
#endif
#ifndef LEVEL_CODE_MUTATION
#define LEVEL_CODE_MUTATION 0
#endif
#ifndef CODE_ENTRY_MUTATION
#define CODE_ENTRY_MUTATION 0
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
static int finish_child(Menu *s,uint16_t cs,uint16_t resume,uint16_t status) {
    if(status){s->status=LMN_MAIN_MENU_CHILD_STOP;s->child_status=status;return 0;}
    s->r.ip=pop(s);
#if MAIN_MENU_MUTATION == 8
    s->r.ip=resume;
#endif
    if(s->r.cs!=cs||s->r.ip!=resume){s->status=LMN_MAIN_MENU_CHANGED_CHILD_RETURN;return 0;}
    return 1;
}
static int child(Menu *s,uint16_t target,uint16_t resume) {
    uint16_t cs=s->r.cs,child_cs=cs,ip=target,status=0;
    LmnVideoRestoreState in,out;
    push(s,resume);in=(LmnVideoRestoreState){INPUT_FIELDS(s)};
    if(target==CS_ReadCodeInput||target==CS_DrawCodeInputText||target==CS_DecodeLevelCode||target==CS_FormatSelectedLevelAndGroup) {
        LmnMainMenuResult c=target==CS_ReadCodeInput?
            lmn_read_code_input_core(s->memory,&s->r,s->game_ds,s->ports,s->bus):target==CS_DrawCodeInputText?
            lmn_draw_code_input_core(s->memory,&s->r,s->game_ds,s->ports,s->bus):target==CS_DecodeLevelCode?
            lmn_decode_level_code_core(s->memory,&s->r,s->bus):lmn_format_selected_level_core(s->memory,&s->r,s->bus);
        s->r=c.registers;
        if(c.status){s->status=c.status;s->child_status=c.child_status;return 0;}
    } else if(target==CS_WriteDecimalByteField) {
        LmnDecimalFieldCall call={s->r.ds,s->r.ax,s->r.bx,s->r.si,s->r.flags};
        LmnDecimalFieldResult c=lmn_write_decimal_field_core(s->memory,&call,s->bus);
        s->r.ax=c.value;s->r.bx=c.prefix_value;s->r.si=c.cursor;s->r.flags=c.flags;
    } else if(target==CS_InitializeDisplayOrigins) {
        LmnDisplaySetupResult c=lmn_setup_display_core(s->memory,cs,&in,LMN_DISPLAY_SETUP_ENTRY_INITIALIZE,0,s->bus);
        apply(s,&c.state,c.code_segment,c.continuation);status=(uint16_t)c.status;
    } else if(target==CS_ReadKeyboardCharacter) {
        LmnKeyboardResult c=lmn_read_keyboard_character_core(s->memory,&s->r,s->bus);
        s->r=c.registers;status=c.status;
    } else if(target==CS_PublishMenuPalette) {
        LmnPalettePublishResult c=lmn_publish_palette_core(s->memory,&s->r,LMN_PALETTE_PUBLISH_MENU,s->ports,s->bus);
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
    return finish_child(s,cs,resume,status);
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

static int dos_call(Menu *s,uint16_t resume,const LmnInterruptService *dos) {
    LmnInterruptResult call=lmn_interrupt_service(s->memory,&s->r,0x21u,resume,dos,s->bus);
    if(call.status==LMN_INTERRUPT_RETURNED)return 1;
    s->status=call.status==LMN_INTERRUPT_UNBOUND_SERVICE?LMN_MAIN_MENU_UNBOUND_DOS:
        call.status==LMN_INTERRUPT_PROVIDER_STOP?LMN_MAIN_MENU_DOS_STOP:LMN_MAIN_MENU_CHANGED_IRET;
    s->child_status=call.service_status;return 0;
}
static void resource_probe(Menu *s,const LmnInterruptService *dos) {
#if MAIN_MENU_MUTATION == 14
    uint16_t entry_ds=s->r.ds;
#endif
    #if MAIN_MENU_MUTATION == 17
    uint8_t media=read8(s,SEG09A9_DatCriticalErrorFlag);
#else
    uint8_t media=read8(s,SEG09A9_StartupFatIdByte1FDE);
#endif
    cmp8(s,media,0xfdu);
#if MAIN_MENU_MUTATION == 11
    if(!media)goto ready;
#else
    if(!(s->r.flags&ZF))goto ready;
#endif
    if(!child(s,CS_TransitionPaletteToSlot1,CS_MenuStartupAfterCall4ACC))return;
redraw:
    if(!child(s,CS_ClearFullDrawingPage,CS_MenuStartupAfterCall4ACF)||
       !child(s,CS_DrawScreenBackground,CS_MenuStartupAfterCall4AD2))return;
    s->r.si=SEG09A9_MenuResourceRetryText;
    if(!child(s,CS_DrawTextStream,CS_MenuStartupAfterCall4AD9)||
       !child(s,CS_CopyDrawingPageToAlternate,CS_MenuStartupAfterCall4ADC)||
       !child(s,CS_WaitForDisplayStatusBit3Cycle,CS_MenuStartupAfterCall4ADF)||
       !child(s,CS_ProgramAlternateDisplayStart,CS_MenuStartupAfterCall4AE2)||
       !child(s,CS_TransitionPaletteToSlot2,CS_MenuStartupAfterCall4AE5))return;
    write8(s,SEG09A9_KeyboardScanCodeByte,0u);
    for(;;) {
        s->r.ax=read16(s,s->r.ds,SEG09A9_InputButtonsWord);(void)logic(s,s->r.ax&7u,0);
        if(!(s->r.flags&ZF))break;
        ah(s,read8(s,SEG09A9_KeyboardScanCodeByte));
#if MAIN_MENU_MUTATION == 15
        (void)logic(s,(uint8_t)s->r.ax,1);
#else
        (void)logic(s,s->r.ax>>8,1);
#endif
        if(!(s->r.flags&ZF))break;
    }
    s->r.dx=SEG09A9_MenuResourceProbeFilename;s->r.ax=0x3d00u;
    if(!dos_call(s,CS_MenuResourceAfterOpen,dos))return;
#if MAIN_MENU_MUTATION != 12
    if(s->r.flags&CF)goto redraw;
#endif
    s->r.bx=s->r.ax;
#if MAIN_MENU_MUTATION == 16
    s->r.ax=0x3e00u;
#else
    ah(s,0x3eu);
#endif
    if(!dos_call(s,CS_MenuResourceAfterClose,dos))return;
#if MAIN_MENU_MUTATION != 13
    if(s->r.flags&CF)goto redraw;
#endif
    if(!child(s,CS_TransitionPaletteToSlot1,CS_MenuStartupAfterCall4B10)||
       !child(s,CS_ClearFullDrawingPage,CS_MenuStartupAfterCall4B13))return;
#if MAIN_MENU_MUTATION == 14
    write_at(s,physical(entry_ds,SEG09A9_DatCriticalErrorFlag),0u);
#else
    write8(s,SEG09A9_DatCriticalErrorFlag,0u);
#endif
ready:
    s->r.ip=CS_MenuResourceProbeReturn;
}
LmnMainMenuResult lmn_check_menu_resource_core(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnInterruptService *dos,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Menu s={memory,ports,bus,*registers,game_ds,0u,0u};resource_probe(&s,dos);return result(&s);
}
LmnMainMenuResult lmn_check_menu_resource_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnInterruptService *dos,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnMainMenuResult out=lmn_check_menu_resource_core(memory,registers,game_ds,dos,ports,bus);
    if(out.status==0u){Menu s={memory,ports,bus,out.registers,game_ds,0u,0u};s.r.ip=pop(&s);out.registers=s.r;}
    return out;
}
LmnMainMenuResult lmn_enter_main_menu(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnVideoRestoreServices *video,const LmnInterruptService *dos,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Menu s={memory,ports,bus,*registers,game_ds,0u,0u};uint16_t cs=s.r.cs;
    push(&s,CS_MenuStartupAfterCall43F2);
    {
        LmnVideoRestoreState in={INPUT_FIELDS(&s)};
        LmnDisplaySetupResult c=lmn_setup_display_core(memory,cs,&in,LMN_DISPLAY_SETUP_ENTRY_FULL,video,bus);
        apply(&s,&c.state,c.code_segment,c.continuation);
        if(!finish_child(&s,cs,CS_MenuStartupAfterCall43F2,(uint16_t)c.status))return result(&s);
    }
    if(!child(&s,CS_ClearFullDrawingPage,CS_MenuStartupAfterCall43F5))return result(&s);
    push(&s,CS_MenuStartupAfterCall43F8);
    {
        LmnTimerTailResult c=lmn_install_menu_timer_core(memory,&s.r,bus);s.r=c.registers;
        if(!finish_child(&s,cs,CS_MenuStartupAfterCall43F8,c.status))return result(&s);
    }
    if(!child(&s,CS_PublishMenuPalette,CS_MenuStartupAfterCall43FB))return result(&s);
    push(&s,CS_MenuStartupAfterCall43FE);resource_probe(&s,dos);
    if(s.status||!finish_child(&s,cs,CS_MenuStartupAfterCall43FE,0u))return result(&s);
    return lmn_run_main_menu(memory,&s.r,game_ds,LMN_MAIN_MENU_REFRESH,ports,bus);
}
static void cl(Menu *s,uint8_t v) {s->r.cx=(uint16_t)((s->r.cx&0xff00u)|v);}
static void ch(Menu *s,uint8_t v) {s->r.cx=(uint16_t)((s->r.cx&0xffu)|((uint16_t)v<<8));}
static void dl(Menu *s,uint8_t v) {s->r.dx=(uint16_t)((s->r.dx&0xff00u)|v);}
static void dh(Menu *s,uint8_t v) {s->r.dx=(uint16_t)((s->r.dx&0xffu)|((uint16_t)v<<8));}
static uint8_t shr8(Menu *s,uint8_t v) {
    uint8_t out=v>>1;
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(out,1)|(v&1u?CF:0u)|(v&0x80u?OF:0u));return out;
}
static uint8_t shift_right(Menu *s,uint8_t v,unsigned count) {while(count--)v=shr8(s,v);return v;}
static uint8_t shift_left(Menu *s,uint8_t v,unsigned count) {while(count--)v=shl8(s,v);return v;}
static void code_template_or(Menu *s,unsigned n,int with_ah) {
#if LEVEL_CODE_MUTATION == 2
    al(s,(uint8_t)logic(s,(uint8_t)s->r.ax^read8(s,(uint16_t)(s->r.si+n)),1));
#else
    al(s,(uint8_t)logic(s,(uint8_t)s->r.ax|read8(s,(uint16_t)(s->r.si+n)),1));
#endif
    if(with_ah)al(s,(uint8_t)logic(s,(uint8_t)s->r.ax|(s->r.ax>>8),1));
    al(s,(uint8_t)logic(s,(uint8_t)s->r.ax|(s->r.cx>>8),1));
    write8(s,(uint16_t)(s->r.di+n),(uint8_t)s->r.ax);
}
static void rotate_code(Menu *s,int right) {
    /* Each source is reread after preceding stores, including stack/DS aliases. */
    do {
        al(s,read8(s,s->r.si));
        for(unsigned n=1;n<=6u;++n) {
            uint16_t source=(uint16_t)(right?s->r.si-n:s->r.si+n);
            uint16_t dest=(uint16_t)(right?s->r.si-n+1u:s->r.si+n-1u);
            ah(s,read8(s,source));write8(s,dest,(uint8_t)(s->r.ax>>8));
        }
        write8(s,(uint16_t)(right?s->r.si-6u:s->r.si+6u),(uint8_t)s->r.ax);
        dh(s,incdec8(s,(uint8_t)(s->r.dx>>8),1));
    } while(!(s->r.flags&SF));
}
LmnMainMenuResult lmn_encode_level_code_core(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus) {
    Menu s={memory,0,bus,*registers,0u,0u,0u};
    dl(&s,read8(&s,SEG09A9_LevelResourceSelectionByte));dh(&s,read8(&s,SEG09A9_LevelCodePayloadByte));
    cl(&s,read8(&s,SEG09A9_StatusCompletionDisplayValue));s.r.si=SEG09A9_LevelCodeTemplate;s.r.di=SEG09A9_GeneratedLevelCode;
    s.r.ax=s.r.dx;ch(&s,(uint8_t)s.r.cx);s.r.ax=logic(&s,s.r.ax&0x101u,0);ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&1u,1));
    al(&s,shift_left(&s,(uint8_t)s.r.ax,3));ah(&s,shl8(&s,(uint8_t)(s.r.ax>>8)));ch(&s,shift_left(&s,(uint8_t)(s.r.cx>>8),2));code_template_or(&s,0,1);
    al(&s,(uint8_t)s.r.dx);ch(&s,(uint8_t)s.r.cx);al(&s,(uint8_t)logic(&s,s.r.ax&2u,1));ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&2u,1));
    al(&s,shl8(&s,(uint8_t)s.r.ax));ch(&s,shr8(&s,(uint8_t)(s.r.cx>>8)));code_template_or(&s,1,0);
    s.r.ax=s.r.dx;ch(&s,(uint8_t)s.r.cx);s.r.ax=logic(&s,s.r.ax&0x204u,0);ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&4u,1));
    ah(&s,shr8(&s,(uint8_t)(s.r.ax>>8)));ch(&s,shr8(&s,(uint8_t)(s.r.cx>>8)));code_template_or(&s,2,1);
    al(&s,(uint8_t)s.r.dx);ch(&s,(uint8_t)s.r.cx);al(&s,(uint8_t)logic(&s,s.r.ax&8u,1));ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&8u,1));
    al(&s,shift_right(&s,(uint8_t)s.r.ax,3));ch(&s,shift_right(&s,(uint8_t)(s.r.cx>>8),2));code_template_or(&s,3,0);
    s.r.ax=s.r.dx;ch(&s,(uint8_t)s.r.cx);s.r.ax=logic(&s,s.r.ax&0x410u,0);ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&0x10u,1));
    al(&s,shift_right(&s,(uint8_t)s.r.ax,3));ah(&s,shift_right(&s,(uint8_t)(s.r.ax>>8),2));ch(&s,shr8(&s,(uint8_t)(s.r.cx>>8)));code_template_or(&s,4,1);
    s.r.ax=s.r.dx;ch(&s,(uint8_t)s.r.cx);al(&s,(uint8_t)logic(&s,s.r.ax&0x20u,1));ah(&s,(uint8_t)logic(&s,(s.r.ax>>8)&8u,1));ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&0x20u,1));
    al(&s,shift_right(&s,(uint8_t)s.r.ax,5));ah(&s,shift_right(&s,(uint8_t)(s.r.ax>>8),2));ch(&s,shift_right(&s,(uint8_t)(s.r.cx>>8),3));code_template_or(&s,5,1);
    al(&s,(uint8_t)s.r.dx);ch(&s,(uint8_t)s.r.cx);al(&s,(uint8_t)logic(&s,s.r.ax&0xc0u,1));ch(&s,(uint8_t)logic(&s,(s.r.cx>>8)&0x40u,1));
    al(&s,shift_right(&s,(uint8_t)s.r.ax,4));ch(&s,shift_right(&s,(uint8_t)(s.r.cx>>8),6));code_template_or(&s,6,0);
    al(&s,(uint8_t)s.r.dx);al(&s,(uint8_t)logic(&s,s.r.ax&15u,1));
    al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,read8(&s,(uint16_t)(s.r.si+7u)),0,1));write8(&s,(uint16_t)(s.r.di+7u),(uint8_t)s.r.ax);
    al(&s,(uint8_t)s.r.dx);al(&s,(uint8_t)logic(&s,s.r.ax&0xf0u,1));al(&s,shift_right(&s,(uint8_t)s.r.ax,4));
    al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,read8(&s,(uint16_t)(s.r.si+8u)),0,1));write8(&s,(uint16_t)(s.r.di+8u),(uint8_t)s.r.ax);
    al(&s,(uint8_t)logic(&s,0u,1));
    for(unsigned n=0;n<9u;++n)al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,read8(&s,(uint16_t)(s.r.di+n)),0,1));
    al(&s,(uint8_t)logic(&s,s.r.ax&15u,1));al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,read8(&s,(uint16_t)(s.r.si+9u)),0,1));
    write8(&s,(uint16_t)(s.r.di+9u),(uint8_t)s.r.ax);
#if LEVEL_CODE_MUTATION == 1
    dh(&s,6u);
#else
    dh(&s,7u);
#endif
    dl(&s,(uint8_t)logic(&s,(uint8_t)s.r.dx&(s.r.dx>>8),1));dh(&s,(uint8_t)arithmetic(&s,s.r.dx>>8,(uint8_t)s.r.dx,1,1));
    s.r.si=(uint16_t)(SEG09A9_GeneratedLevelCode+6u);rotate_code(&s,1);s.r.ip=CS_LevelCodeEncodeReturn;return result(&s);
}
LmnMainMenuResult lmn_decode_level_code_core(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus) {
    Menu s={memory,0,bus,*registers,0u,0u,0u};s.r.si=SEG09A9_EnteredLevelCode;
#if LEVEL_CODE_MUTATION == 9
    write8(&s,SEG09A9_SpecialLevelCodeLatch,0u);
#endif
    static const uint16_t special[5]={0x4942u,0x4c4cu,0x4e41u,0x5444u,0x4445u};
    for(unsigned n=0;n<5u;++n) {
        (void)arithmetic(&s,read16(&s,s.r.ds,(uint16_t)(s.r.si+2u*n)),special[n],1,0);
        if(!(s.r.flags&ZF))goto checksum;
    }
#if LEVEL_CODE_MUTATION != 4
    write8(&s,SEG09A9_SpecialLevelCodeLatch,0xffu);
#endif
checksum:
    s.r.di=SEG09A9_LevelCodeTemplate;s.r.cx=9u;al(&s,(uint8_t)logic(&s,0u,1));push(&s,s.r.si);
    do {
        uint16_t cf;al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,read8(&s,s.r.si),0,1));
        cf=s.r.flags&CF;s.r.si=arithmetic(&s,s.r.si,1u,0,0);s.r.flags=(uint16_t)((s.r.flags&~CF)|cf);--s.r.cx;
    } while(s.r.cx);
    s.r.si=pop(&s);
#if LEVEL_CODE_MUTATION == 10
    s.r.si=SEG09A9_EnteredLevelCode;
#endif
#if LEVEL_CODE_MUTATION != 3
    al(&s,(uint8_t)logic(&s,s.r.ax&15u,1));
#endif
    ah(&s,read8(&s,(uint16_t)(s.r.si+9u)));
    ah(&s,(uint8_t)arithmetic(&s,s.r.ax>>8,(uint8_t)s.r.ax,1,1));cmp8(&s,read8(&s,(uint16_t)(s.r.di+9u)),(uint8_t)(s.r.ax>>8));
    if(!(s.r.flags&ZF))goto done;
    al(&s,read8(&s,(uint16_t)(s.r.si+7u)));al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,read8(&s,(uint16_t)(s.r.di+7u)),1,1));
    ah(&s,read8(&s,(uint16_t)(s.r.si+8u)));ah(&s,(uint8_t)arithmetic(&s,s.r.ax>>8,read8(&s,(uint16_t)(s.r.di+8u)),1,1));
    s.r.ax=logic(&s,s.r.ax&0x0f0fu,0);ah(&s,shift_left(&s,(uint8_t)(s.r.ax>>8),4));al(&s,(uint8_t)logic(&s,(uint8_t)s.r.ax|(s.r.ax>>8),1));
#if LEVEL_CODE_MUTATION != 5
    write8(&s,SEG09A9_LevelResourceSelectionByte,(uint8_t)s.r.ax);
#endif
    dh(&s,7u);al(&s,(uint8_t)logic(&s,(uint8_t)s.r.ax&(s.r.dx>>8),1));dh(&s,(uint8_t)arithmetic(&s,s.r.dx>>8,(uint8_t)s.r.ax,1,1));
#if LEVEL_CODE_MUTATION != 6
    rotate_code(&s,0);
#endif
    ah(&s,(uint8_t)logic(&s,0u,1));
    for(unsigned n=0;n<7u;++n) {
        static const uint8_t right[7]={3,1,0,0,0,0,0},left[7]={0,0,0,3,3,5,4},mask[7]={1,2,4,8,16,32,192};
        al(&s,read8(&s,(uint16_t)(s.r.si+n)));al(&s,shift_right(&s,(uint8_t)s.r.ax,right[n]));al(&s,shift_left(&s,(uint8_t)s.r.ax,left[n]));
        al(&s,(uint8_t)logic(&s,s.r.ax&mask[n],1));ah(&s,(uint8_t)logic(&s,(s.r.ax>>8)|(uint8_t)s.r.ax,1));
    }
    cmp8(&s,(uint8_t)(s.r.ax>>8),read8(&s,SEG09A9_LevelResourceSelectionByte));if(!(s.r.flags&ZF))goto done;
    al(&s,read8(&s,SEG09A9_LevelResourceSelectionByte));ah(&s,(uint8_t)logic(&s,0u,1));cl(&s,30u);
#if LEVEL_CODE_MUTATION == 7
    cl(&s,29u);
#endif
    {uint16_t dividend=s.r.ax,divisor=(uint8_t)s.r.cx;al(&s,(uint8_t)(dividend/divisor));ah(&s,(uint8_t)(dividend%divisor));}
    write8(&s,SEG09A9_MenuLevelGroupIndex,(uint8_t)s.r.ax);ah(&s,(uint8_t)logic(&s,0u,1));
    for(unsigned n=0;n<4u;++n) {
        static const uint8_t index[4]={0,2,4,5},left[4]={0,1,2,2},mask[4]={1,2,4,
#if LEVEL_CODE_MUTATION == 8
        0xf8u
#else
        8u
#endif
        };
        al(&s,read8(&s,(uint16_t)(s.r.si+index[n])));
        al(&s,n?shift_left(&s,(uint8_t)s.r.ax,left[n]):shr8(&s,(uint8_t)s.r.ax));
        al(&s,(uint8_t)logic(&s,s.r.ax&mask[n],1));ah(&s,(uint8_t)logic(&s,(s.r.ax>>8)|(uint8_t)s.r.ax,1));
    }
    write8(&s,SEG09A9_LevelCodePayloadByte,(uint8_t)(s.r.ax>>8));ah(&s,(uint8_t)arithmetic(&s,s.r.ax>>8,s.r.ax>>8,1,1));
done:
    s.r.ip=CS_LevelCodeDecodeReturn;return result(&s);
}
static LmnMainMenuResult code_return(uint8_t *memory,LmnMainMenuResult out,const LmnRasterBus *bus) {
    Menu s={memory,0,bus,out.registers,0u,0u,0u};s.r.ip=pop(&s);out.registers=s.r;return out;
}
LmnMainMenuResult lmn_encode_level_code_adapter(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus) {
    return code_return(memory,lmn_encode_level_code_core(memory,registers,bus),bus);
}
LmnMainMenuResult lmn_decode_level_code_adapter(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus) {
    return code_return(memory,lmn_decode_level_code_core(memory,registers,bus),bus);
}
static uint16_t incdec16(Menu *s,uint16_t v,int dec) {
    uint16_t cf=s->r.flags&CF;v=arithmetic(s,v,1u,dec,0);s->r.flags=(uint16_t)((s->r.flags&~CF)|cf);return v;
}
LmnMainMenuResult lmn_draw_code_input_core(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Menu s={memory,ports,bus,*registers,game_ds,0u,0u};s.r.si=SEG09A9_CodeInputText;
    LmnTextStreamState in={INPUT_FIELDS(&s)};
    LmnTextStreamResult c=lmn_draw_text_stream_core(memory,s.r.cs,game_ds,&in,bus,ports);
    apply(&s,&c.state,c.code_segment,c.continuation);
    if(c.status){s.status=LMN_MAIN_MENU_CHILD_STOP;s.child_status=(uint16_t)c.status;}
    return result(&s);
}
LmnMainMenuResult lmn_draw_code_input_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnMainMenuResult out=lmn_draw_code_input_core(memory,registers,game_ds,ports,bus);
    return out.status?out:code_return(memory,out,bus);
}
LmnMainMenuResult lmn_format_selected_level_core(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus) {
    Menu s={memory,0,bus,*registers,0u,0u,0u};
#if CODE_ENTRY_MUTATION == 2
    uint8_t first_selection;
#endif
    push(&s,s.r.cx);cl(&s,30u);
    al(&s,read8(&s,SEG09A9_LevelResourceSelectionByte));
#if CODE_ENTRY_MUTATION == 2
    first_selection=(uint8_t)s.r.ax;
#endif
    al(&s,incdec8(&s,(uint8_t)s.r.ax,0));ah(&s,(uint8_t)logic(&s,0u,1));
#if CODE_ENTRY_MUTATION == 1
    if(!(uint8_t)s.r.ax)ah(&s,1u);
#endif
    {uint16_t value=s.r.ax;al(&s,(uint8_t)(value/(uint8_t)s.r.cx));ah(&s,(uint8_t)(value%(uint8_t)s.r.cx));}
    ch(&s,(uint8_t)s.r.ax);s.r.ax=(uint16_t)((uint8_t)s.r.ax*(uint8_t)s.r.cx);
    s.r.flags=(uint16_t)((s.r.flags&~(CF|OF))|(s.r.ax>255u?CF|OF:0u));
#if CODE_ENTRY_MUTATION == 2
    cl(&s,first_selection);
#else
    cl(&s,read8(&s,SEG09A9_LevelResourceSelectionByte));
#endif
    cl(&s,incdec8(&s,(uint8_t)s.r.cx,0));
    cl(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.cx,(uint8_t)s.r.ax,1,1));s.r.ax=s.r.cx;
    (void)logic(&s,(uint8_t)s.r.ax,1);
    if(s.r.flags&ZF){al(&s,30u);ah(&s,incdec8(&s,(uint8_t)(s.r.ax>>8),1));}
    s.r.cx=pop(&s);
#if CODE_ENTRY_MUTATION == 15
    s.r.cx=registers->cx;
#endif
    s.r.ip=CS_LevelGroupFormatReturn;return result(&s);
}
LmnMainMenuResult lmn_format_selected_level_adapter(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus) {
    return code_return(memory,lmn_format_selected_level_core(memory,registers,bus),bus);
}
LmnMainMenuResult lmn_read_code_input_core(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Menu s={memory,ports,bus,*registers,game_ds,0u,0u};
    s.r.si=SEG09A9_EnteredLevelCode;s.r.cx=10u;s.r.bx=0x5a41u;s.r.bp=CS_DrawCodeInputText;
    s.r.di=s.r.si;s.r.dx=s.r.si;s.r.dx=arithmetic(&s,s.r.dx,s.r.cx,0,0);s.r.cx=0x5f2eu;
    #if CODE_ENTRY_MUTATION == 3
    write8(&s,SEG09A9_CodeInputBlinkCountdown,19u);
#else
    write8(&s,SEG09A9_CodeInputBlinkCountdown,20u);
#endif
outer:
    push(&s,s.r.si);push(&s,s.r.di);push(&s,s.r.bx);push(&s,s.r.cx);push(&s,s.r.dx);push(&s,s.r.bp);
wait:
    push(&s,s.r.di);push(&s,s.r.si);push(&s,s.r.cx);push(&s,s.r.dx);push(&s,s.r.bp);
    if(!child(&s,CS_WaitForDisplayStatusBit3Cycle,CS_CodeEntryAfterCall4CA5))return result(&s);
    s.r.bp=pop(&s);s.r.dx=pop(&s);s.r.cx=pop(&s);s.r.si=pop(&s);s.r.di=pop(&s);
    {
        uint16_t incoming=s.r.flags,next;uint8_t v=read8(&s,SEG09A9_CodeInputBlinkCountdown);
        v=incdec8(&s,v,1);next=s.r.flags;
#if CODE_ENTRY_MUTATION != 4
        s.r.flags=incoming;
#else
        (void)incoming;
#endif
        write8(&s,SEG09A9_CodeInputBlinkCountdown,v);s.r.flags=next;
    }
    if(s.r.flags&ZF) {
        write8(&s,SEG09A9_CodeInputBlinkCountdown,20u);al(&s,read8(&s,s.r.di));cmp8(&s,(uint8_t)s.r.ax,(uint8_t)s.r.cx);
        write8(&s,s.r.di,(uint8_t)(s.r.flags&ZF?s.r.cx>>8:s.r.cx));
    }
    push(&s,s.r.di);push(&s,s.r.si);push(&s,s.r.cx);push(&s,s.r.dx);push(&s,s.r.bp);
#if CODE_ENTRY_MUTATION == 8
    s.r.bp=CS_DrawCodeInputText;
#endif
    if(s.r.bp!=CS_DrawCodeInputText){s.r.ip=CS_CodeInputDrawCall4CC9;s.status=LMN_MAIN_MENU_UNSUPPORTED_CODE_CALLBACK;return result(&s);}
    if(!child(&s,s.r.bp,CS_CodeEntryAfterCall4CC9)||!child(&s,CS_SwapDrawingOriginsAndDisplay,CS_CodeEntryAfterCall4CCB)||
       !child(&s,CS_ReadKeyboardCharacter,CS_CodeEntryAfterCall4CCE))return result(&s);
    s.r.bp=pop(&s);s.r.dx=pop(&s);s.r.cx=pop(&s);s.r.si=pop(&s);s.r.di=pop(&s);
    cmp8(&s,(uint8_t)s.r.ax,255u);if(s.r.flags&ZF)goto wait;
    s.r.bp=pop(&s);s.r.dx=pop(&s);s.r.cx=pop(&s);s.r.bx=pop(&s);s.r.di=pop(&s);s.r.si=pop(&s);
    cmp8(&s,(uint8_t)s.r.ax,0x7fu);if(s.r.flags&ZF)goto backspace;
    cmp8(&s,(uint8_t)s.r.ax,13u);if(s.r.flags&ZF)goto submit;
    cmp8(&s,(uint8_t)s.r.ax,(uint8_t)s.r.bx);
#if CODE_ENTRY_MUTATION == 7
    if((uint8_t)s.r.ax<(uint8_t)s.r.bx)goto outer;
#else
    if(!!(s.r.flags&SF)!=!!(s.r.flags&OF))goto outer;
#endif
    cmp8(&s,(uint8_t)s.r.ax,(uint8_t)(s.r.bx>>8));if(!(s.r.flags&ZF)&&!!(s.r.flags&SF)==!!(s.r.flags&OF))goto outer;
    (void)arithmetic(&s,s.r.di,s.r.dx,1,0);if(s.r.flags&ZF)goto outer;
    write8(&s,s.r.di,(uint8_t)s.r.ax);s.r.di=incdec16(&s,s.r.di,0);cl(&s,read8(&s,s.r.di));
    (void)arithmetic(&s,s.r.di,s.r.dx,1,0);if(!(s.r.flags&ZF))goto outer;
#if CODE_ENTRY_MUTATION != 6
    s.r.di=incdec16(&s,s.r.di,1);cl(&s,read8(&s,s.r.di));
#endif
    goto outer;
backspace:
    write8(&s,s.r.di,0x2eu);cl(&s,0x2eu);(void)arithmetic(&s,s.r.di,s.r.si,1,0);if(s.r.flags&ZF)goto outer;
    s.r.di=incdec16(&s,s.r.di,1);
#if CODE_ENTRY_MUTATION == 5
    write8(&s,s.r.di,0x2eu);
#endif
    cl(&s,read8(&s,s.r.di));goto outer;
submit:
#if CODE_ENTRY_MUTATION == 10
    write8(&s,SEG09A9_InputKeyMask1FC7,0u);
#else
    write16(&s,SEG09A9_InputKeyMask1FC7,0u);
#endif
    write8(&s,s.r.di,(uint8_t)s.r.cx);
#if CODE_ENTRY_MUTATION == 9
    s.r.bp=CS_DrawCodeInputText;
#endif
    if(s.r.bp!=CS_DrawCodeInputText){s.r.ip=CS_CodeInputDrawTail4D18;s.status=LMN_MAIN_MENU_UNSUPPORTED_CODE_CALLBACK;return result(&s);}
    return lmn_draw_code_input_core(memory,&s.r,game_ds,ports,bus);
}
LmnMainMenuResult lmn_read_code_input_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnMainMenuResult out=lmn_read_code_input_core(memory,registers,game_ds,ports,bus);
    return out.status?out:code_return(memory,out,bus);
}
LmnMainMenuResult lmn_show_code_entry(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Menu s={memory,ports,bus,*registers,game_ds,0u,0u};
    if(!child(&s,CS_ClearFullDrawingPage,CS_CodeEntryAfterCall4967)||!child(&s,CS_InitializeDisplayOrigins,CS_CodeEntryAfterCall496A)||
       !child(&s,CS_TransitionPaletteToSlot1,CS_CodeEntryAfterCall496D)||!child(&s,CS_ClearFullDrawingPage,CS_CodeEntryAfterCall4970)||
       !child(&s,CS_DrawScreenBackground,CS_CodeEntryAfterCall4973))return result(&s);
    s.r.si=SEG09A9_EnteredLevelCode;s.r.cx=10u;
    do {write8(&s,s.r.si,0x2eu);s.r.si=incdec16(&s,s.r.si,0);--s.r.cx;}while(s.r.cx);
    s.r.si=SEG09A9_CodeEntryPromptText;
    if(!child(&s,CS_DrawTextStream,CS_CodeEntryAfterCall4987)||!child(&s,CS_CopyDrawingPageToAlternate,CS_CodeEntryAfterCall498A)||
       !child(&s,CS_WaitForDisplayStatusBit3Cycle,CS_CodeEntryAfterCall498D)||!child(&s,CS_ProgramAlternateDisplayStart,CS_CodeEntryAfterCall4990)||
       !child(&s,CS_TransitionPaletteToSlot2,CS_CodeEntryAfterCall4993)||!child(&s,CS_ReadCodeInput,CS_CodeEntryAfterCall4996)||
       !child(&s,CS_DecodeLevelCode,CS_CodeEntryAfterCall4999))return result(&s);
#if CODE_ENTRY_MUTATION == 11
    if(s.r.flags&ZF)goto rejected;
#else
    if(!(s.r.flags&ZF))goto rejected;
#endif
    al(&s,read8(&s,SEG09A9_LevelResourceSelectionByte));
    if(!child(&s,CS_FormatSelectedLevelAndGroup,CS_CodeEntryAfterCall49A1))return result(&s);
    push(&s,s.r.ax);s.r.si=SEG09A9_CodeAcceptedLevelField;
    if(!child(&s,CS_WriteDecimalByteField,CS_CodeEntryAfterCall49A9))return result(&s);
    s.r.ax=pop(&s);al(&s,(uint8_t)(s.r.ax>>8));
#if CODE_ENTRY_MUTATION == 13
    if((uint8_t)s.r.ax>3u)al(&s,3u);
#endif
    s.r.di=SEG09A9_CodeAcceptedRatingField;s.r.si=SEG09A9_CodeRatingNameRows;
    push(&s,s.r.ds);s.r.es=pop(&s);s.r.cx=6u;s.r.ax=(uint16_t)((uint8_t)s.r.ax*(uint8_t)s.r.cx);
    s.r.flags=(uint16_t)((s.r.flags&~(CF|OF))|(s.r.ax>255u?CF|OF:0u));s.r.si=arithmetic(&s,s.r.si,s.r.ax,0,0);
    while(s.r.cx) {
        uint8_t v=read8(&s,s.r.si);write_at(&s,physical(s.r.es,s.r.di),v);
#if CODE_ENTRY_MUTATION == 12
        ++s.r.si;++s.r.di;
#else
        s.r.si=(uint16_t)(s.r.si+(s.r.flags&0x400u?-1:1));s.r.di=(uint16_t)(s.r.di+(s.r.flags&0x400u?-1:1));
#endif
        --s.r.cx;
    }
    s.r.si=SEG09A9_CodeAcceptedText;
    if(!child(&s,CS_DrawTextStream,CS_CodeEntryAfterCall49C6)||!child(&s,CS_SwapDrawingOriginsAndDisplay,CS_CodeEntryAfterCall49C9))return result(&s);
    s.r.cx=120u;
    do {
        if(!child(&s,CS_WaitForDisplayStatusBit3Cycle,CS_CodeEntryAfterCall49CF))return result(&s);
        s.r.ax=read16(&s,s.r.ds,SEG09A9_InputButtonsWord);(void)logic(&s,s.r.ax&7u,0);if(!(s.r.flags&ZF))break;
        s.r.ax=read16(&s,s.r.ds,SEG09A9_InputKeyMask1FC7);(void)logic(&s,s.r.ax&0x20u,0);if(!(s.r.flags&ZF))break;
#if CODE_ENTRY_MUTATION == 14
        (void)logic(&s,0u,0);
#else
        (void)logic(&s,s.r.ax&0x40u,0);if(!(s.r.flags&ZF))break;
#endif
        --s.r.cx;
    }while(s.r.cx);
    s.r.ip=CS_MenuRefresh4401;return result(&s);
rejected:
    s.r.si=SEG09A9_CodeRejectedText;
    if(!child(&s,CS_DrawTextStream,CS_CodeEntryAfterCall49F0)||!child(&s,CS_SwapDrawingOriginsAndDisplay,CS_CodeEntryAfterCall49F3))return result(&s);
    s.r.cx=60u;do {if(!child(&s,CS_WaitForDisplayStatusBit3Cycle,CS_CodeEntryAfterCall49F9))return result(&s);--s.r.cx;}while(s.r.cx);
    s.r.ip=CS_MenuRefresh4401;return result(&s);
}
