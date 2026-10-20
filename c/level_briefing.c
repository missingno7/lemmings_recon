#include "level_briefing.h"
#include "lemmings_sym.h"
#include "decimal_field.h"
#include "display_pages.h"
#include "display_start.h"
#include "display_setup.h"
#include "background_drawing.h"
#include "text_stream.h"
#include "level_preview.h"

#ifndef LEVEL_BRIEFING_MUTATION
#define LEVEL_BRIEFING_MUTATION 0
#endif
enum { CF=1,PF=4,ZF=64,SF=128,OF=2048,ARITH=0x8D5 };
typedef struct Briefing {
    uint8_t *memory;
    LmnRegs r;
    const LmnRasterBus *bus;
    const LmnRasterBytePorts *ports;
    uint16_t game_ds,status,child_status;
    const LmnLevelRedrawServices *redraw;
} Briefing;
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xFFFFFu;}
static uint8_t read_at(Briefing *s,uint32_t at) {
    at&=0xFFFFFu;return s->bus&&s->bus->read_byte?
        s->bus->read_byte(s->bus->context,s->memory,at,s->r.flags):s->memory[at];
}
static void write_at(Briefing *s,uint32_t at,uint8_t v) {
    at&=0xFFFFFu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,v,s->r.flags);
    else s->memory[at]=v;
}
static uint8_t read8(Briefing *s,uint16_t off) {return read_at(s,physical(s->r.ds,off));}
static void write8(Briefing *s,uint16_t off,uint8_t v) {write_at(s,physical(s->r.ds,off),v);}
static uint16_t read16(Briefing *s,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);uint8_t a=read_at(s,at),b=read_at(s,at+1u);return (uint16_t)(a|((uint16_t)b<<8));
}
static void write16(Briefing *s,uint16_t seg,uint16_t off,uint16_t v) {
    uint32_t at=physical(seg,off);write_at(s,at,(uint8_t)v);write_at(s,at+1u,(uint8_t)(v>>8));
}
static void push(Briefing *s,uint16_t value) {s->r.sp=(uint16_t)(s->r.sp-2u);write16(s,s->r.ss,s->r.sp,value);}
static uint16_t pop(Briefing *s) {uint16_t v=read16(s,s->r.ss,s->r.sp);s->r.sp=(uint16_t)(s->r.sp+2u);return v;}
static uint16_t szp(uint16_t v,int byte) {
    unsigned parity=0;for(unsigned n=0;n<8;n++)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0:PF)|(v?0:ZF)|(v&(byte?0x80u:0x8000u)?SF:0));
}
static uint16_t arithmetic(Briefing *s,uint16_t a,uint16_t b,int sub,int byte) {
    uint16_t v=(uint16_t)((sub?a-b:a+b)&(byte?255u:65535u)),sign=byte?0x80u:0x8000u;
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,byte)|((sub?a<b:(uint32_t)a+b>(byte?255u:65535u))?CF:0)|
        ((a^b^v)&16u)|(((sub?(a^b):~(a^b))&(a^v)&sign)?OF:0));return v;
}
static void logic(Briefing *s,uint16_t v) {s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,0));}
static void al(Briefing *s,uint8_t v) {s->r.ax=(uint16_t)((s->r.ax&0xFF00u)|v);}
static void ah(Briefing *s,uint8_t v) {s->r.ax=(uint16_t)((s->r.ax&255u)|((uint16_t)v<<8));}
static uint16_t inc(Briefing *s,uint16_t v,int byte) {
    uint16_t cf=s->r.flags&CF;v=arithmetic(s,v,1,0,byte);s->r.flags=(uint16_t)((s->r.flags&~CF)|cf);return v;
}
static uint8_t shl(Briefing *s,uint8_t v) {
    uint8_t out=(uint8_t)(v<<1);s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(out,1)|
        (v&128u?CF:0)|((v^out)&128u?OF:0));return out;
}
static LmnVideoRestoreState state(const Briefing *s) {
    const LmnRegs *r=&s->r;LmnVideoRestoreState v={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};return v;
}
static void apply(Briefing *s,const LmnVideoRestoreState *v,uint16_t cs,uint16_t ip) {
    s->r=(LmnRegs){v->value,v->base_value,v->count,v->argument,v->source_cursor,v->output_cursor,
        v->frame_cursor,v->stack_offset,cs,v->data_segment,v->extra_segment,v->stack_segment,ip,v->flags};
}
static LmnBriefingResult result(const Briefing *s) {LmnBriefingResult r={s->r,s->status,s->child_status};return r;}
static int poll_at(Briefing *s,const LmnForegroundPoll *poll,uint16_t site) {
    if(poll&&poll->poll) {
        s->r.ip=site;uint16_t status=poll->poll(poll->context,s->memory,&s->r,site);
        if(status){s->status=LMN_BRIEFING_POLL_STOP;s->child_status=status;return 0;}
    }
    return 1;
}
static int stopped(Briefing *s,uint16_t status) {
    if(!status)return 0;
    s->status=LMN_BRIEFING_CHILD_STOP;s->child_status=status;return 1;
}
static int returned(Briefing *s,uint16_t cs,uint16_t resume) {
    if(s->status)return 0;
    s->r.ip=pop(s);
#if LEVEL_BRIEFING_MUTATION == 1
    s->r.ip=resume;
#endif
    if(s->r.cs!=cs||s->r.ip!=resume){s->status=LMN_BRIEFING_CHANGED_RETURN;return 0;}return 1;
}
static void decimal(Briefing *s,int pair) {
    LmnDecimalFieldCall call={s->r.ds,s->r.ax,s->r.bx,s->r.si,s->r.flags};
    LmnDecimalFieldResult c=pair?lmn_write_decimal_pair_core(s->memory,&call,s->bus):lmn_write_decimal_field_core(s->memory,&call,s->bus);
    s->r.ax=c.value;s->r.bx=c.prefix_value;s->r.si=c.cursor;s->r.flags=c.flags;
}
static void percent(Briefing *s) {
    write8(s,(uint16_t)(s->r.si+3u),32u);uint16_t cs=s->r.cs;
    push(s,CS_PercentageAfterDecimal);decimal(s,0);
    if(!returned(s,cs,CS_PercentageAfterDecimal))return;
    write8(s,s->r.si,37u);
    s->r.si=inc(s,s->r.si,0);s->r.ip=CS_WritePercentageByteField+11u;
}
static void clear_lower(Briefing *s) {
    s->r.di=0x15E0u;s->r.cx=0x5780u;s->r.ip=CS_ClearVgaBytes;
#if LEVEL_BRIEFING_MUTATION == 2
    s->r.di=0;
#endif
    if(!s->bus||!s->bus->read_byte||!s->bus->write_byte||!s->bus->out_word){stopped(s,LMN_DISPLAY_PAGES_MISSING_CLEAR_BUS);return;}
    LmnVgaClearResult c=lmn_clear_vga_bytes_core(s->memory,s->r.ss,s->r.sp,s->r.di,s->r.cx,s->r.flags,s->bus);
    s->r.ax=c.value;s->r.cx=c.count;s->r.dx=c.port;s->r.di=c.output_cursor;s->r.es=c.output_segment;
    s->r.sp=c.stack_offset;s->r.flags=c.flags;s->r.ip=CS_ClearVgaReturn;
}
static void palette_writer(Briefing *s,LmnPalettePortsEntry entry) {
    LmnVideoRestoreState in=state(s);LmnPalettePortsResult c=lmn_write_palette_ports_core(s->memory,s->r.cs,&in,entry,s->ports,s->bus);
    apply(s,&c.state,s->r.cs,c.continuation);stopped(s,(uint16_t)c.status);
}
static void base_palette(Briefing *s) {
    uint16_t mode=read16(s,s->r.ds,SEG09A9_PaletteDisplayModeWord);
    (void)arithmetic(s,mode,4,1,0);
    if(mode==4) {
        s->r.si=SEG09A9_BasePaletteSource2608;s->r.cx=8;uint16_t cs=s->r.cs;
        push(s,CS_BasePaletteAfterFirstDac);palette_writer(s,LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC);
        if(!returned(s,cs,CS_BasePaletteAfterFirstDac))return;
        s->r.si=SEG09A9_BasePaletteSource2608;s->r.cx=0x1008u;
#if LEVEL_BRIEFING_MUTATION == 3
        s->r.si=(uint16_t)(s->r.si+24u);
#endif
        palette_writer(s,LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC);return;
    }
    mode=read16(s,s->r.ds,SEG09A9_PaletteDisplayModeWord);(void)arithmetic(s,mode,2,1,0);
    if(mode==2){s->r.si=SEG09A9_BasePaletteSource2608;s->r.cx=16;palette_writer(s,LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE);}
    else s->r.ip=CS_PublishBasePaletteBothBanks+14u;
}
LmnBriefingResult lmn_briefing_helper_core(uint8_t *memory,const LmnRegs *registers,
    LmnBriefingHelper entry,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    Briefing s={memory,*registers,bus,ports,0,0,0,0};
    if(entry==LMN_BRIEFING_PERCENT)percent(&s);
    else if(entry==LMN_BRIEFING_CLEAR_LOWER)clear_lower(&s);
    else base_palette(&s);
    return result(&s);
}
static int child(Briefing *s,uint16_t target,uint16_t resume) {
    uint16_t cs=s->r.cs;push(s,resume);LmnVideoRestoreState in=state(s);
    if(target==CS_WritePercentageByteField)percent(s);
    else if(target==CS_WriteDecimalByteField||target==CS_WriteDecimalBytePair)decimal(s,target==CS_WriteDecimalBytePair);
    else if(target==CS_ClearBelowLevelPreview)clear_lower(s);
    else if(target==CS_PublishSixteenPaletteColors||target==CS_PublishUpperEightPaletteColors) {
        LmnPalettePublishResult c=lmn_publish_palette_core(s->memory,&s->r,target==CS_PublishSixteenPaletteColors?
            LMN_PALETTE_PUBLISH_SIXTEEN:LMN_PALETTE_PUBLISH_UPPER_EIGHT,s->ports,s->bus);s->r=c.registers;stopped(s,c.status);
    } else if(target==CS_StepSplitPaletteToSlot1||target==CS_StepSplitPaletteToTargets||target==CS_RefreshRasterSplitPalette||target==CS_FadeAndClearSplitPalette) {
        LmnPaletteTransitionResult c=target==CS_RefreshRasterSplitPalette?lmn_refresh_split_palette_core(s->memory,cs,&in,s->ports,s->bus):
            target==CS_FadeAndClearSplitPalette?lmn_fade_split_palette_core(s->memory,cs,&in,s->ports,s->bus):
            lmn_step_split_palette_core(s->memory,cs,&in,target==CS_StepSplitPaletteToSlot1?LMN_SPLIT_PALETTE_TO_SLOT1:LMN_SPLIT_PALETTE_TO_TARGETS,s->bus);
        apply(s,&c.state,c.code_segment,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_ClearFullDrawingPage) {
        LmnDisplayPagesResult c=lmn_clear_full_drawing_page_core(s->memory,&in,s->bus);apply(s,&c.state,cs,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_SwapDrawingOriginsAndDisplay) {
        LmnDisplayStartState v={in.value,in.base_value,in.count,in.argument,in.source_cursor,in.output_cursor,in.frame_cursor,in.data_segment,in.extra_segment,in.stack_segment,in.stack_offset,in.flags};
        LmnDisplayStartResult c=lmn_program_display_start_core(s->memory,&v,LMN_DISPLAY_START_ENTRY_SWAP,s->bus);
        LmnVideoRestoreState out={c.state.value,c.state.base_value,c.state.count,c.state.argument,c.state.source_cursor,c.state.output_cursor,c.state.frame_cursor,c.state.data_segment,c.state.extra_segment,c.state.stack_segment,c.state.stack_offset,c.state.flags};
        apply(s,&out,cs,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_SetupDisplayLayout) {
        LmnDisplaySetupResult c=lmn_setup_display_core(s->memory,cs,&in,LMN_DISPLAY_SETUP_ENTRY_LAYOUT,0,s->bus);
        apply(s,&c.state,c.code_segment,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_DrawLevelPreview) {
        LmnLevelPreviewResult c=lmn_draw_level_preview_core(s->memory,cs,&in,s->bus);
        apply(s,&c.state,c.code_segment,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_DrawScreenBackgroundFromRow) {
        LmnBackgroundDrawingResult c=lmn_draw_background_core(s->memory,cs,s->game_ds,&in,LMN_BACKGROUND_DRAWING_FROM_ROW,s->bus,s->ports);
        apply(s,&c.state,c.code_segment,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_DrawTextStream) {
        LmnTextStreamResult c=lmn_draw_text_stream_core(s->memory,cs,s->game_ds,&in,s->bus,s->ports);
        apply(s,&c.state,c.code_segment,c.continuation);stopped(s,(uint16_t)c.status);
    } else if(target==CS_RedrawLevel) {
        LmnLevelRedrawCall call={{s->r.ax,s->r.bx,s->r.cx,s->r.dx,s->r.si,s->r.di,s->r.bp,s->r.sp,s->r.flags,s->r.ip},s->r.ds,s->r.es,s->r.cs,s->r.ss,s->game_ds};
        LmnLevelRedrawServices service=s->redraw?*s->redraw:(LmnLevelRedrawServices){0};service.raster=s->bus;service.ports=s->ports;
        LmnLevelRedrawResult c=lmn_redraw_level_core(s->memory,&call,&service);
        s->r.ax=c.state.work_value;s->r.bx=c.state.second_source_cursor;s->r.cx=c.state.packed_counts;s->r.dx=c.state.width_state;
        s->r.si=c.state.source_cursor;s->r.di=c.state.destination_cursor;s->r.bp=c.state.control;s->r.sp=c.state.stack_offset;s->r.flags=c.state.flags;
        s->r.ds=c.data_segment;s->r.es=c.output_segment;s->r.cs=c.code_segment;s->r.ip=c.state.continuation;stopped(s,(uint16_t)c.status);
    }
    return returned(s,cs,resume);
}
LmnBriefingResult lmn_show_level_briefing_core_polled(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnBriefingServices *services,const LmnForegroundPoll *poll) {
    Briefing s={memory,*registers,services?services->bus:0,services?services->ports:0,game_ds,0,0,services?services->redraw:0};
    al(&s,read8(&s,SEG09A9_MenuLevelGroupIndex));al(&s,shl(&s,(uint8_t)s.r.ax));ah(&s,(uint8_t)s.r.ax);
    al(&s,shl(&s,(uint8_t)s.r.ax));ah(&s,(uint8_t)arithmetic(&s,s.r.ax>>8,(uint8_t)s.r.ax,0,1));
    al(&s,shl(&s,(uint8_t)s.r.ax));ah(&s,(uint8_t)arithmetic(&s,s.r.ax>>8,(uint8_t)s.r.ax,0,1));
    al(&s,shl(&s,(uint8_t)s.r.ax));ah(&s,(uint8_t)arithmetic(&s,s.r.ax>>8,(uint8_t)s.r.ax,0,1));
    al(&s,read8(&s,SEG09A9_LevelResourceSelectionByte));al(&s,(uint8_t)inc(&s,(uint8_t)s.r.ax,1));
    al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,s.r.ax>>8,1,1));s.r.si=SEG09A9_BriefingLevelDigits;
    if(!child(&s,CS_WriteDecimalBytePair,CS_BriefingAfter4584))return result(&s);
    al(&s,read8(&s,SEG09A9_LevelHeaderCreationLimitWord+1u));s.r.si=SEG09A9_BriefingPopulationDigits;
    if(!child(&s,CS_WriteDecimalByteField,CS_BriefingAfter458E))return result(&s);
    al(&s,read8(&s,SEG09A9_LevelHeaderWord04+1u));s.r.cx=(uint16_t)((s.r.cx&0xFF00u)|100u);
    s.r.ax=(uint16_t)((uint8_t)s.r.ax*(uint8_t)s.r.cx);
    s.r.flags=(uint16_t)((s.r.flags&~(CF|OF))|(s.r.ax>255u?CF|OF:0));
    s.r.cx=(uint16_t)((s.r.cx&0xFF00u)|read8(&s,SEG09A9_LevelHeaderCreationLimitWord+1u));
    s.r.ip=CS_BriefingPercentDivide;
    if(!(s.r.cx&255u)||s.r.ax/(s.r.cx&255u)>255u){s.status=LMN_BRIEFING_DIVIDE_ERROR;return result(&s);}
    {uint16_t dividend=s.r.ax,divisor=s.r.cx&255u;s.r.ax=(uint16_t)(((dividend%divisor)<<8)|(dividend/divisor));}
    write8(&s,SEG09A9_BriefingPercentageByte,(uint8_t)s.r.ax);s.r.si=SEG09A9_BriefingPercentDigits;
    if(!child(&s,CS_WritePercentageByteField,CS_BriefingAfter45A5))return result(&s);
    al(&s,read8(&s,SEG09A9_LevelHeaderReleaseSettingWord+1u));s.r.si=SEG09A9_BriefingReleaseDigits;
    if(!child(&s,CS_WriteDecimalBytePair,CS_BriefingAfter45AF))return result(&s);
    al(&s,read8(&s,SEG09A9_LevelHeaderCountdownWord+1u));al(&s,(uint8_t)arithmetic(&s,(uint8_t)s.r.ax,48,0,1));
    write8(&s,SEG09A9_BriefingTimeDigit,(uint8_t)s.r.ax);ah(&s,0x73);(void)arithmetic(&s,(uint8_t)s.r.ax,0x31,1,1);
    if(s.r.flags&ZF)ah(&s,32);
    write8(&s,SEG09A9_BriefingTimePluralByte,(uint8_t)(s.r.ax>>8));
    s.r.si=SEG09A9_LoadedLevelFooterBytes;s.r.di=SEG09A9_BriefingTitleBytes;push(&s,s.r.ds);s.r.es=pop(&s);s.r.cx=16;
    do {uint16_t v=read16(&s,s.r.ds,s.r.si);write16(&s,s.r.es,s.r.di,v);uint16_t step=(s.r.flags&0x400u)?0xFFFEu:2u;
#if LEVEL_BRIEFING_MUTATION == 4
        step=2;
#endif
        s.r.si=(uint16_t)(s.r.si+step);s.r.di=(uint16_t)(s.r.di+step);--s.r.cx;
    }while(s.r.cx);
    al(&s,read8(&s,SEG09A9_MenuLevelGroupIndex));ah(&s,0);logic(&s,0);s.r.cx=6;
    s.r.ax=(uint16_t)(s.r.ax*s.r.cx);s.r.dx=0;s.r.flags&=(uint16_t)~(CF|OF);s.r.bx=s.r.ax;s.r.si=SEG09A9_BriefingGroupText;
    do {al(&s,read8(&s,(uint16_t)(SEG09A9_CodeRatingNameRows+s.r.bx)));write8(&s,s.r.si,(uint8_t)s.r.ax);
        s.r.bx=inc(&s,s.r.bx,0);s.r.si=inc(&s,s.r.si,0);--s.r.cx;
    }while(s.r.cx);
    if(!child(&s,CS_ClearFullDrawingPage,CS_BriefingAfter45EF))return result(&s);
    do {s.r.cx=16;s.r.dx=16;if(!child(&s,CS_StepSplitPaletteToSlot1,CS_BriefingAfter45F8))return result(&s);}while(!(s.r.flags&ZF));
    al(&s,1);if(!child(&s,CS_PublishSixteenPaletteColors,CS_BriefingAfter4600))return result(&s);
    write16(&s,s.r.ds,SEG09A9_DrawingOrigin,0);write16(&s,s.r.ds,SEG09A9_AlternateDrawingOrigin,0);
    if(!child(&s,CS_SwapDrawingOriginsAndDisplay,CS_BriefingAfter460F))return result(&s);
    if(!child(&s,CS_RedrawLevel,CS_BriefingAfter4612))return result(&s);
    write16(&s,s.r.ds,SEG09A9_DrawingOrigin,0);write16(&s,s.r.ds,SEG09A9_DrawingPageByteOffset,0);
    if(!child(&s,CS_DrawLevelPreview,CS_BriefingAfter4621))return result(&s);
    write16(&s,s.r.ds,SEG09A9_DrawingOrigin,0);write16(&s,s.r.ds,SEG09A9_DrawingPageByteOffset,0);
    if(!child(&s,CS_ClearBelowLevelPreview,CS_BriefingAfter4630))return result(&s);
    if(!child(&s,CS_SetupDisplayLayout,CS_BriefingAfter4633))return result(&s);
    s.r.bx=0x4E;if(!child(&s,CS_DrawScreenBackgroundFromRow,CS_BriefingAfter4639))return result(&s);
    s.r.si=0x4B0A;if(!child(&s,CS_DrawTextStream,CS_BriefingAfter4640))return result(&s);
    s.r.si=0x4BA0;{uint8_t mode=read8(&s,SEG09A9_InputModeByte25A6);(void)arithmetic(&s,mode,0,1,1);
        if(!(s.r.flags&ZF)){s.r.si=0x4BC3;mode=read8(&s,SEG09A9_InputModeByte25A6);(void)arithmetic(&s,mode,1,1,1);if(!(s.r.flags&ZF))s.r.si=0x4BE5;}}
    if(!child(&s,CS_DrawTextStream,CS_BriefingAfter465D))return result(&s);
    do {if(!poll_at(&s,poll,0x4660))return result(&s);s.r.ax=read16(&s,s.r.ds,SEG09A9_InputButtonsWord);logic(&s,s.r.ax&7u);}while(!(s.r.flags&ZF));
    do {
        if(!child(&s,CS_RefreshRasterSplitPalette,CS_BriefingAfter4668))return result(&s);
        al(&s,0);if(!child(&s,CS_PublishUpperEightPaletteColors,CS_BriefingAfter466E))return result(&s);
        s.r.cx=16;s.r.dx=16;s.r.bx=0x0302;
        if(!child(&s,CS_StepSplitPaletteToTargets,CS_BriefingAfter467B))return result(&s);
    }while(!(s.r.flags&ZF));
    for(;;) {
        if(!child(&s,CS_RefreshRasterSplitPalette,CS_BriefingAfter4680))return result(&s);
        if(!poll_at(&s,poll,0x4683))return result(&s);
        s.r.ax=read16(&s,s.r.ds,SEG09A9_InputButtonsWord);logic(&s,s.r.ax&7u);
        if(!(s.r.flags&ZF))break;
        if(!poll_at(&s,poll,0x468B))return result(&s);
        s.r.ax=read16(&s,s.r.ds,0x1FC7);logic(&s,s.r.ax&0x20u);
        if(!(s.r.flags&ZF)) {
            if(!child(&s,CS_FadeAndClearSplitPalette,CS_ShowLevelBriefing+0x138u))return result(&s);
#if LEVEL_BRIEFING_MUTATION != 5
            s.r.ax=pop(&s);
#endif
            s.r.ip=CS_MenuRefresh4401;return result(&s);
        }
        logic(&s,s.r.ax&0x40u);if(!(s.r.flags&ZF))break;
    }
    LmnVideoRestoreState in=state(&s);LmnPaletteTransitionResult c=lmn_fade_split_palette_core(s.memory,s.r.cs,&in,s.ports,s.bus);
    apply(&s,&c.state,c.code_segment,c.continuation);stopped(&s,(uint16_t)c.status);return result(&s);
}
LmnBriefingResult lmn_briefing_helper_adapter(uint8_t *memory,const LmnRegs *registers,
    LmnBriefingHelper entry,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnBriefingResult out=lmn_briefing_helper_core(memory,registers,entry,ports,bus);
    if(!out.status){Briefing s={memory,out.registers,bus,ports,0,0,0,0};s.r.ip=pop(&s);out=result(&s);}return out;
}
LmnBriefingResult lmn_show_level_briefing_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnBriefingServices *services) {
    LmnBriefingResult out=lmn_show_level_briefing_core(memory,registers,game_ds,services);
    if(!out.status&&out.registers.ip==CS_ClearVgaReturn){Briefing s={memory,out.registers,services?services->bus:0,services?services->ports:0,game_ds,0,0,0};s.r.ip=pop(&s);out=result(&s);}return out;
}

LmnBriefingResult lmn_show_level_briefing_core(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,const LmnBriefingServices *services) {return lmn_show_level_briefing_core_polled(memory,registers,game_ds,services,0);}
