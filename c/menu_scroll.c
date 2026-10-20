#include "menu_scroll.h"
#include "lemmings_sym.h"

#ifndef MENU_SCROLL_MUTATION
#define MENU_SCROLL_MUTATION 0
#endif
enum { CF=1,PF=4,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5 };
typedef struct Scroll {
    uint8_t *memory;
    const LmnRasterBus *bus;
    const LmnRasterBytePorts *ports;
    LmnVideoRestoreState r;
    uint16_t cs,game_ds,ip;
    enum LmnMenuScrollStatus status;
} Scroll;
static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t read8(Scroll *s,uint32_t at) {
    at&=0xfffffu;
    return s->bus&&s->bus->read_byte?
        s->bus->read_byte(s->bus->context,s->memory,at,s->r.flags):s->memory[at];
}
static void write8(Scroll *s,uint32_t at,uint8_t value) {
    at&=0xfffffu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,value,s->r.flags);
    else s->memory[at]=value;
}
static uint16_t read16(Scroll *s,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);uint8_t lo=read8(s,at),hi=read8(s,at+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write16(Scroll *s,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t at=physical(seg,off);write8(s,at,(uint8_t)value);write8(s,at+1u,(uint8_t)(value>>8));
}
static uint16_t field(Scroll *s,uint16_t off) {return read16(s,s->r.data_segment,off);}
static void store(Scroll *s,uint16_t off,uint16_t value) {write16(s,s->r.data_segment,off,value);}
static void push(Scroll *s,uint16_t v) {
    s->r.stack_offset=(uint16_t)(s->r.stack_offset-2u);write16(s,s->r.stack_segment,s->r.stack_offset,v);
}
static uint16_t pop(Scroll *s) {
    uint16_t v=read16(s,s->r.stack_segment,s->r.stack_offset);
    s->r.stack_offset=(uint16_t)(s->r.stack_offset+2u);return v;
}
static uint16_t szp(uint16_t v,uint16_t sign) {
    unsigned parity=0;for(unsigned n=0;n<8u;++n)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0u:PF)|(v?0u:ZF)|(v&sign?SF:0u));
}
static uint16_t arithmetic(Scroll *s,uint16_t a,uint16_t b,int subtract,int byte) {
    uint16_t mask=byte?0xffu:0xffffu,sign=byte?0x80u:0x8000u;
    uint16_t v=(uint16_t)((subtract?a-b:a+b)&mask);
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,sign)|
        ((subtract?a<b:(uint32_t)a+b>mask)?CF:0u)|((a^b^v)&16u)|
        (((subtract?(a^b):~(a^b))&(a^v)&sign)?OF:0u));return v;
}
static uint16_t add(Scroll *s,uint16_t a,uint16_t b) {return arithmetic(s,a,b,0,0);}
static uint16_t incdec(Scroll *s,uint16_t v,int dec,int byte) {
    uint16_t cf=s->r.flags&CF;v=arithmetic(s,v,1u,dec,byte);
    s->r.flags=(uint16_t)((s->r.flags&~CF)|cf);return v;
}
static uint16_t logic(Scroll *s,uint16_t v,int byte) {
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,byte?0x80u:0x8000u));return v;
}
static uint16_t shr(Scroll *s,uint16_t v) {
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp((uint16_t)(v>>1),0x8000u)|
        (v&1u)|(v&0x8000u?OF:0u));return (uint16_t)(v>>1);
}
static uint16_t rcl(Scroll *s,uint16_t v) {
    uint16_t cf=(v&0x8000u)?CF:0u,res=(uint16_t)((v<<1)|(s->r.flags&CF));
    s->r.flags=(uint16_t)((s->r.flags&~(CF|OF))|cf|(((res>>15)^cf)?OF:0u));return res;
}
static void al(Scroll *s,uint8_t v) {s->r.value=(uint16_t)((s->r.value&0xff00u)|v);}
static void bl(Scroll *s,uint8_t v) {s->r.base_value=(uint16_t)((s->r.base_value&0xff00u)|v);}
static uint16_t step(Scroll *s,unsigned width) {
#if MENU_SCROLL_MUTATION == 1
    (void)s;return (uint16_t)width;
#else
    return (uint16_t)(s->r.flags&DF?0u-width:width);
#endif
}
static void lodsb(Scroll *s) {
    al(s,read8(s,physical(s->r.data_segment,s->r.source_cursor)));
    s->r.source_cursor=(uint16_t)(s->r.source_cursor+step(s,1u));
}
static void stosb(Scroll *s) {
    write8(s,physical(s->r.extra_segment,s->r.output_cursor),(uint8_t)s->r.value);
    s->r.output_cursor=(uint16_t)(s->r.output_cursor+step(s,1u));
}
static void bitmap(Scroll *s,uint16_t resume) {
    uint16_t cs=s->cs,ip;push(s,cs);push(s,resume);
    {
        LmnPlanarBitmapCall call={s->r.data_segment,s->game_ds,s->r.stack_segment,s->r.stack_offset,
            s->r.value,s->r.base_value,s->r.count,s->r.argument,s->r.source_cursor,
            s->r.output_cursor,s->r.frame_cursor,s->r.extra_segment,s->r.flags};
        LmnDrawingRenderResult drawing=lmn_draw_planar_bitmap_core(s->memory,&call,s->bus,s->ports);
        const LmnDrawingSourceResult *r=&drawing.plan.state;
        s->r=(LmnVideoRestoreState){r->work_value,r->second_source_cursor,r->packed_counts,r->width_state,
            r->source_cursor,r->destination_cursor,r->control,drawing.source_segment,
            drawing.output_segment,s->r.stack_segment,r->stack_offset,r->flags};
        if(!drawing.body_returned){s->ip=r->continuation;s->status=LMN_MENU_SCROLL_RENDERER_STOP;return;}
    }
    ip=pop(s);s->cs=pop(s);s->ip=ip;
    if(ip!=resume||s->cs!=cs)s->status=LMN_MENU_SCROLL_CHANGED_RETURN;
}
typedef void (*Routine)(Scroll *);
static int near_call(Scroll *s,Routine routine,uint16_t resume) {
    push(s,resume);routine(s);
    if(s->status!=LMN_MENU_SCROLL_READY)return 0;
    s->ip=pop(s);
#if MENU_SCROLL_MUTATION == 7
    s->ip=resume;
#endif
    if(s->ip!=resume){s->status=LMN_MENU_SCROLL_CHANGED_RETURN;return 0;}
    return 1;
}
static void copy_tile(Scroll *s) {
    push(s,s->r.data_segment);s->r.source_cursor=0x4c10u;
    s->r.value&=0x00ffu;(void)logic(s,0u,1);
    s->r.value=add(s,s->r.value,s->r.value);s->r.output_cursor=s->r.value;
    s->r.value=field(s,SEG09A9_UiGraphicsBufferSegment);s->r.value=add(s,s->r.value,0x1000u);
    s->r.data_segment=s->r.value;s->r.count=4u;
    do {
        push(s,s->r.count);push(s,s->r.output_cursor);s->r.count=16u;
        do {
            uint16_t word=read16(s,s->r.data_segment,s->r.source_cursor);
            write16(s,s->r.extra_segment,s->r.output_cursor,word);
            s->r.source_cursor=(uint16_t)(s->r.source_cursor+step(s,2u));
            s->r.output_cursor=(uint16_t)(s->r.output_cursor+step(s,2u));
            s->r.output_cursor=add(s,s->r.output_cursor,0x44u);--s->r.count;
        } while(s->r.count);
        s->r.output_cursor=pop(s);s->r.count=pop(s);
        s->r.output_cursor=add(s,s->r.output_cursor,0x460u);--s->r.count;
    } while(s->r.count);
#if MENU_SCROLL_MUTATION == 2
    (void)pop(s);
#else
    s->r.data_segment=pop(s);
#endif
    s->ip=CS_MenuScrollTileReturn;
}
static void glyph(Scroll *s) {
    push(s,s->r.data_segment);(void)arithmetic(s,(uint8_t)s->r.value,0x20u,1,1);
    if(!(s->r.flags&ZF)) {
        al(s,(uint8_t)arithmetic(s,(uint8_t)s->r.value,0x21u,1,1));
        s->r.value&=0x00ffu;(void)logic(s,0u,1);
        for(unsigned n=0;n<5u;++n)s->r.value=add(s,s->r.value,s->r.value);
        s->r.source_cursor=s->r.value;s->r.value=add(s,s->r.value,s->r.value);
        s->r.source_cursor=add(s,s->r.source_cursor,s->r.value);
        s->r.source_cursor=add(s,s->r.source_cursor,0x5bc0u);
        s->r.base_value=s->r.source_cursor;s->r.base_value=add(s,s->r.base_value,0x40u);
        s->r.value=field(s,SEG09A9_UiGraphicsBufferSegment);s->r.value=add(s,s->r.value,0x1000u);
        s->r.data_segment=s->r.value;s->r.output_cursor=0x44u;s->r.count=3u;
        do {
            push(s,s->r.count);push(s,s->r.output_cursor);push(s,s->r.base_value);s->r.count=16u;
            do {
                for(unsigned byte=0;byte<2u;++byte) {
                    al(s,read8(s,physical(s->r.data_segment,s->r.base_value)));al(s,(uint8_t)~s->r.value);
                    al(s,(uint8_t)logic(s,(uint8_t)s->r.value&read8(s,physical(s->r.extra_segment,s->r.output_cursor)),1));
                    al(s,(uint8_t)logic(s,(uint8_t)s->r.value|read8(s,physical(s->r.data_segment,s->r.source_cursor)),1));
                    stosb(s);s->r.source_cursor=incdec(s,s->r.source_cursor,0,0);s->r.base_value=incdec(s,s->r.base_value,0,0);
                }
                s->r.output_cursor=add(s,s->r.output_cursor,0x44u);--s->r.count;
            } while(s->r.count);
            s->r.base_value=pop(s);s->r.output_cursor=pop(s);s->r.count=pop(s);
            s->r.output_cursor=add(s,s->r.output_cursor,0x460u);--s->r.count;
        } while(s->r.count);
        s->r.count=16u;
        do {
            for(unsigned byte=0;byte<2u;++byte) {
                al(s,read8(s,physical(s->r.data_segment,s->r.base_value)));al(s,(uint8_t)~s->r.value);
                al(s,(uint8_t)logic(s,(uint8_t)s->r.value&read8(s,physical(s->r.extra_segment,s->r.output_cursor)),1));
#if MENU_SCROLL_MUTATION != 3
                stosb(s);
#else
                s->r.output_cursor=(uint16_t)(s->r.output_cursor+step(s,1u));
#endif
                s->r.base_value=incdec(s,s->r.base_value,0,0);
            }
            s->r.output_cursor=add(s,s->r.output_cursor,0x44u);--s->r.count;
        } while(s->r.count);
    }
    s->r.data_segment=pop(s);s->ip=CS_MenuScrollGlyphReturn;
}
static void edge(Scroll *s) {
    s->r.frame_cursor=logic(s,0u,0);s->r.argument=48u;s->r.count=0x410u;s->r.base_value=334u;
    bitmap(s,CS_MenuScrollEdgeReturn);
}
static void edges(Scroll *s) {
    s->r.source_cursor=0x1c10u;s->r.value=field(s,SEG09A9_UiScrollPhaseOrPromptPointer);
#if MENU_SCROLL_MUTATION == 8
    uint16_t saved_phase=s->r.value;
#endif
    s->r.value=shr(s,shr(s,s->r.value));s->r.value=logic(s,s->r.value&15u,0);
    s->r.value=(uint16_t)((s->r.value<<8)|(s->r.value>>8));
    s->r.source_cursor=add(s,s->r.source_cursor,s->r.value);s->r.value=shr(s,s->r.value);
    s->r.source_cursor=add(s,s->r.source_cursor,s->r.value);s->r.value=logic(s,0u,0);
    if(!near_call(s,edge,CS_MenuScrollAfterFirstEdge))return;
    s->r.source_cursor=0x1c10u;
#if MENU_SCROLL_MUTATION == 8
    s->r.value=saved_phase;
#else
    s->r.value=field(s,SEG09A9_UiScrollPhaseOrPromptPointer); /* reload after first child */
#endif
    s->r.value=shr(s,shr(s,s->r.value));s->r.value=logic(s,s->r.value&15u,0);
    s->r.value=(uint16_t)((s->r.value<<8)|(s->r.value>>8));
    s->r.source_cursor=add(s,s->r.source_cursor,s->r.value);s->r.value=shr(s,s->r.value);
    s->r.source_cursor=add(s,s->r.source_cursor,s->r.value);s->r.source_cursor=add(s,s->r.source_cursor,0x1800u);
    s->r.value=592u;edge(s); /* physical fallthrough; no invented near frame */
}
static void draw(Scroll *s) {
    s->r.value=field(s,SEG09A9_LevelGraphicsSegment);store(s,SEG09A9_GraphicsResourceSegment,s->r.value);
    s->r.frame_cursor=logic(s,0u,0);s->r.value=48u;s->r.base_value=334u;
    s->r.argument=560u;s->r.count=0x410u;s->r.source_cursor=logic(s,0u,0);
    bitmap(s,CS_MenuScrollAfterBitmap);if(s->status!=LMN_MENU_SCROLL_READY)return;
    s->r.value=field(s,SEG09A9_UiGraphicsBufferSegment);s->r.value=add(s,s->r.value,0x1000u);
    store(s,SEG09A9_GraphicsResourceSegment,s->r.value);edges(s);
}
static void initialize(Scroll *s) {
    s->r.value=SEG09A9_MenuScrollText;store(s,SEG09A9_MenuScrollTextStart,s->r.value);
    store(s,SEG09A9_MenuScrollTextCursor,s->r.value);store(s,SEG09A9_UiScrollPhaseOrPromptPointer,4u);
    store(s,SEG09A9_MenuScrollPauseTicks,0u);s->r.extra_segment=field(s,SEG09A9_LevelGraphicsSegment);
    al(s,(uint8_t)logic(s,0u,1));s->r.count=35u;
    do {
        push(s,s->r.count);push(s,s->r.value);
        if(!near_call(s,copy_tile,CS_MenuScrollInitializeAfterTile))return;
        s->r.value=pop(s);s->r.count=pop(s);al(s,(uint8_t)incdec(s,(uint8_t)s->r.value,0,1));--s->r.count;
    } while(s->r.count);
    draw(s);
}
static void tick(Scroll *s) {
    if(!near_call(s,draw,CS_MenuScrollAfterDraw))return;
    s->r.value=field(s,SEG09A9_MenuScrollPauseTicks);s->r.value=logic(s,s->r.value,0);
    if(!(s->r.flags&ZF)) {
        uint16_t value=field(s,SEG09A9_MenuScrollPauseTicks),incoming=s->r.flags,after;
        value=incdec(s,value,1,0);after=s->r.flags;
        /* DEC [mem] performs its bus write under the instruction's incoming
           flags; only the following instruction observes the new arithmetic. */
#if MENU_SCROLL_MUTATION == 9
        (void)incoming;
#else
        s->r.flags=incoming;
#endif
        store(s,SEG09A9_MenuScrollPauseTicks,value);s->r.flags=after;
        s->ip=CS_MenuScrollPauseReturn;return;
    }
    s->r.extra_segment=field(s,SEG09A9_LevelGraphicsSegment);
    s->r.value=field(s,SEG09A9_UiScrollPhaseOrPromptPointer);s->r.value=add(s,s->r.value,4u);
    store(s,SEG09A9_UiScrollPhaseOrPromptPointer,s->r.value);s->r.value=logic(s,s->r.value&15u,0);
    if(s->r.flags&ZF) {
        al(s,0x22u);if(!near_call(s,copy_tile,CS_MenuScrollAfterTile))return;
        s->r.source_cursor=field(s,SEG09A9_MenuScrollTextCursor);lodsb(s);
        (void)arithmetic(s,(uint8_t)s->r.value,0xffu,1,1);
        if(s->r.flags&ZF) {
#if MENU_SCROLL_MUTATION == 4
            store(s,SEG09A9_MenuScrollPauseTicks,99u);
#else
            store(s,SEG09A9_MenuScrollPauseTicks,100u);
#endif
            lodsb(s); /* FF takes exactly one following byte, even if CR/FF */
        } else {
            (void)arithmetic(s,(uint8_t)s->r.value,0x0du,1,1);
            if(s->r.flags&ZF){s->r.source_cursor=field(s,SEG09A9_MenuScrollTextStart);lodsb(s);}
        }
        store(s,SEG09A9_MenuScrollTextCursor,s->r.source_cursor);
        if(!near_call(s,glyph,CS_MenuScrollAfterGlyph))return;
    }
    s->r.output_cursor=0x45u;s->r.count=4u;
    do {
        push(s,s->r.count);push(s,s->r.output_cursor);s->r.count=16u;
        do {
            push(s,s->r.count);push(s,s->r.output_cursor);s->r.count=70u;
            bl(s,(uint8_t)logic(s,0u,1));
            do {
                al(s,read8(s,physical(s->r.extra_segment,s->r.output_cursor)));
                s->r.value&=0x00ffu;(void)logic(s,0u,1);
                /* SHL then three single-bit RCLs; OR merges the next nibble. */
                s->r.value=add(s,s->r.value,s->r.value);
                s->r.flags&=(uint16_t)~16u; /* SHL's AF undefined */
                for(unsigned n=0;n<3u;++n)s->r.value=rcl(s,s->r.value);
#if MENU_SCROLL_MUTATION != 5
                al(s,(uint8_t)logic(s,(uint8_t)s->r.value|(uint8_t)s->r.base_value,1));
#else
                al(s,(uint8_t)logic(s,(uint8_t)s->r.value,1));
#endif
                write8(s,physical(s->r.extra_segment,s->r.output_cursor),(uint8_t)s->r.value);
                bl(s,(uint8_t)(s->r.value>>8));s->r.output_cursor=incdec(s,s->r.output_cursor,1,0);--s->r.count;
            } while(s->r.count);
            s->r.output_cursor=pop(s);s->r.count=pop(s);s->r.output_cursor=add(s,s->r.output_cursor,70u);--s->r.count;
        } while(s->r.count);
        s->r.output_cursor=pop(s);s->r.count=pop(s);
#if MENU_SCROLL_MUTATION == 6
        s->r.output_cursor=add(s,s->r.output_cursor,0x45fu);
#else
        s->r.output_cursor=add(s,s->r.output_cursor,0x460u);
#endif
        --s->r.count;
    } while(s->r.count);
    s->ip=CS_MenuScrollTickReturn;
}
LmnMenuScrollResult lmn_menu_scroll_core(uint8_t *memory,uint16_t cs,uint16_t game_ds,
    const LmnVideoRestoreState *input,enum LmnMenuScrollEntry entry,
    const LmnRasterBus *bus,const LmnRasterBytePorts *ports) {
    Scroll s={memory,bus,ports,*input,cs,game_ds,0u,LMN_MENU_SCROLL_READY};
    switch(entry) {
    case LMN_MENU_SCROLL_INITIALIZE:initialize(&s);break;
    case LMN_MENU_SCROLL_DRAW:draw(&s);break;
    case LMN_MENU_SCROLL_TICK:tick(&s);break;
    case LMN_MENU_SCROLL_TILE:copy_tile(&s);break;
    case LMN_MENU_SCROLL_GLYPH:glyph(&s);break;
    case LMN_MENU_SCROLL_EDGE:edge(&s);break;
    }
    {LmnMenuScrollResult out={s.r,s.cs,s.ip,s.status};return out;}
}
LmnMenuScrollResult lmn_menu_scroll_adapter(uint8_t *memory,const LmnRegs *r,
    uint16_t game_ds,enum LmnMenuScrollEntry entry,const LmnRasterBus *bus,const LmnRasterBytePorts *ports) {
    LmnVideoRestoreState in={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnMenuScrollResult out=lmn_menu_scroll_core(memory,r->cs,game_ds,&in,entry,bus,ports);
    Scroll s={memory,bus,ports,out.state,out.code_segment,game_ds,out.continuation,out.status};
    if(out.status==LMN_MENU_SCROLL_READY){out.continuation=pop(&s);out.state=s.r;}
    return out;
}
