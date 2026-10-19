#include "menu_animation.h"
#include "lemmings_sym.h"

#ifndef MENU_ANIMATION_MUTATION
#define MENU_ANIMATION_MUTATION 0
#endif
enum { CF=1, PF=4, AF=16, ZF=64, SF=128, OF=2048, ARITH=0x8d5 };

typedef struct Animation {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnVideoRestoreState r;
    uint16_t cs;
} Animation;
static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t read8(Animation *s,uint32_t at) {
    at&=0xfffffu;
    return s->bus&&s->bus->read_byte ?
        s->bus->read_byte(s->bus->context,s->memory,at,s->r.flags):s->memory[at];
}
static void write8(Animation *s,uint32_t at,uint8_t value) {
    at&=0xfffffu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,value,s->r.flags);
    else s->memory[at]=value;
}
static uint16_t read16(Animation *s,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);
    uint8_t low=read8(s,at),high=read8(s,at+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}
static void write16(Animation *s,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t at=physical(seg,off);
    write8(s,at,(uint8_t)value);write8(s,at+1u,(uint8_t)(value>>8));
}
static uint16_t record_word(Animation *s,uint16_t field) {
    return read16(s,s->r.data_segment,(uint16_t)(s->r.source_cursor+field));
}
static void push(Animation *s,uint16_t value) {
    s->r.stack_offset=(uint16_t)(s->r.stack_offset-2u);
    write16(s,s->r.stack_segment,s->r.stack_offset,value);
}
static uint16_t pop(Animation *s) {
    uint16_t v=read16(s,s->r.stack_segment,s->r.stack_offset);
    s->r.stack_offset=(uint16_t)(s->r.stack_offset+2u);return v;
}
static uint16_t szp(uint16_t v) {
    unsigned parity=0;
    for(unsigned n=0;n<8u;++n)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0u:PF)|(v?0u:ZF)|(v&0x8000u?SF:0u));
}
static uint16_t arithmetic(Animation *s,uint16_t a,uint16_t b,int subtract) {
    uint16_t v=(uint16_t)(subtract?a-b:a+b);
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v)|
        ((subtract?a<b:(uint32_t)a+b>0xffffu)?CF:0u)|
        (((a^b^v)&16u)?AF:0u)|
        (((subtract?(a^b):~(a^b))&(a^v)&0x8000u)?OF:0u));
    return v;
}
static uint16_t decrement(Animation *s,uint16_t v) {
    uint16_t cf=s->r.flags&CF;
    v=arithmetic(s,v,1u,1);s->r.flags=(uint16_t)((s->r.flags&~CF)|cf);return v;
}
static uint16_t shr(Animation *s,uint16_t v) {
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp((uint16_t)(v>>1))|
        (v&1u)|(v&0x8000u?OF:0u));
    return (uint16_t)(v>>1);
}
static LmnMenuAnimationResult result(Animation *s,uint16_t ip,enum LmnMenuAnimationStatus status) {
    LmnMenuAnimationResult out={s->r,s->cs,ip,status};return out;
}
static LmnMenuAnimationResult bitmap(Animation *s,uint16_t game_ds,const LmnRasterBytePorts *ports) {
    uint16_t caller_cs=s->cs,ip;
    push(s,caller_cs);push(s,CS_MenuAnimationAfterBitmap);
    {
        LmnPlanarBitmapCall call={s->r.data_segment,game_ds,s->r.stack_segment,s->r.stack_offset,
            s->r.value,s->r.base_value,s->r.count,s->r.argument,s->r.source_cursor,
            s->r.output_cursor,s->r.frame_cursor,s->r.extra_segment,s->r.flags};
        LmnDrawingRenderResult drawing=lmn_draw_planar_bitmap_core(s->memory,&call,s->bus,ports);
        const LmnDrawingSourceResult *r=&drawing.plan.state;
        s->r=(LmnVideoRestoreState){r->work_value,r->second_source_cursor,r->packed_counts,r->width_state,
            r->source_cursor,r->destination_cursor,r->control,drawing.source_segment,
            drawing.output_segment,s->r.stack_segment,r->stack_offset,r->flags};
        if(!drawing.body_returned)return result(s,r->continuation,LMN_MENU_ANIMATION_RENDERER_STOP);
    }
    ip=pop(s);s->cs=pop(s);
#if MENU_ANIMATION_MUTATION != 5
    if(s->cs!=caller_cs||ip!=CS_MenuAnimationAfterBitmap)
        return result(s,ip,LMN_MENU_ANIMATION_CHANGED_RETURN);
#else
    (void)caller_cs;(void)ip;
    s->cs=caller_cs;
#endif
    return result(s,CS_MenuAnimationAfterBitmap,LMN_MENU_ANIMATION_READY);
}

LmnMenuAnimationResult lmn_menu_animation_core(uint8_t *memory,
    uint16_t cs,uint16_t game_ds,const LmnVideoRestoreState *input,
    enum LmnMenuAnimationEntry entry,const LmnRasterBus *bus,const LmnRasterBytePorts *ports) {
    Animation s={memory,bus,*input,cs};
    if(entry==LMN_MENU_ANIMATION_INITIALIZE) {
        s.r.source_cursor=SEG09A9_MenuAnimationRecords;s.r.count=10u;s.r.base_value=40u;
        do {
            s.r.value=record_word(&s,SEG09A9_MenuAnimationResetWord-SEG09A9_MenuAnimationRecords);
            (void)arithmetic(&s,s.r.value,0x8000u,1);
#if MENU_ANIMATION_MUTATION == 1
            s.r.value=s.r.base_value;
#else
            if(!(s.r.flags&ZF))s.r.value=s.r.base_value;
#endif
            write16(&s,s.r.data_segment,s.r.source_cursor,s.r.value);
            s.r.base_value=arithmetic(&s,s.r.base_value,40u,0);
            s.r.source_cursor=arithmetic(&s,s.r.source_cursor,11u,0);
            s.r.count=(uint16_t)(s.r.count-1u);
        } while(s.r.count);
        return result(&s,CS_MenuAnimationInitializeReturn,LMN_MENU_ANIMATION_READY);
    }
    s.r.value=read16(&s,s.r.data_segment,SEG09A9_UiGraphicsBufferSegment);
    s.r.value=arithmetic(&s,s.r.value,0x0800u,0);
    write16(&s,s.r.data_segment,SEG09A9_GraphicsResourceSegment,s.r.value);
    s.r.source_cursor=SEG09A9_MenuAnimationRecords;s.r.count=10u;
    do {
#if MENU_ANIMATION_MUTATION == 4
        uint16_t saved_count=s.r.count;
#endif
        push(&s,s.r.count);
        s.r.value=record_word(&s,0u);
        (void)arithmetic(&s,s.r.value,0x8000u,1);
        if(!(s.r.flags&ZF)) {
            s.r.value=decrement(&s,s.r.value);
            write16(&s,s.r.data_segment,s.r.source_cursor,s.r.value);
#if MENU_ANIMATION_MUTATION == 2
            (void)arithmetic(&s,s.r.value,0xfff0u,1);
#else
            (void)arithmetic(&s,s.r.value,0xffefu,1);
#endif
            if(s.r.flags&ZF) {
                s.r.value=record_word(&s,SEG09A9_MenuAnimationResetWord-SEG09A9_MenuAnimationRecords);
                write16(&s,s.r.data_segment,s.r.source_cursor,s.r.value);
            } else {
                s.r.flags=(uint16_t)((s.r.flags&~ARITH)|szp(s.r.value)); /* AND AX,AX */
                if(s.r.flags&SF) {
                    s.r.value=arithmetic(&s,0u,s.r.value,1); /* NEG */
                    s.r.value=decrement(&s,s.r.value);
                    s.r.value=shr(&s,s.r.value);
                    s.r.value=(uint16_t)((s.r.value<<8)|(s.r.value>>8));
                    s.r.frame_cursor=record_word(&s,SEG09A9_MenuAnimationSourceWord-SEG09A9_MenuAnimationRecords);
                    s.r.value=shr(&s,s.r.value);
                    s.r.frame_cursor=arithmetic(&s,s.r.frame_cursor,s.r.value,0);
                    s.r.value=shr(&s,s.r.value);
                    s.r.frame_cursor=arithmetic(&s,s.r.frame_cursor,s.r.value,0);
                    s.r.value=record_word(&s,SEG09A9_MenuAnimationLeftWord-SEG09A9_MenuAnimationRecords);
                    s.r.base_value=record_word(&s,SEG09A9_MenuAnimationTopWord-SEG09A9_MenuAnimationRecords);
                    push(&s,s.r.source_cursor);
                    s.r.source_cursor=s.r.frame_cursor;s.r.output_cursor=s.r.source_cursor;
#if MENU_ANIMATION_MUTATION == 3
                    s.r.output_cursor=arithmetic(&s,s.r.output_cursor,0x0091u,0);
#else
                    s.r.output_cursor=arithmetic(&s,s.r.output_cursor,0x0090u,0);
#endif
                    s.r.frame_cursor=1u;s.r.count=0x040cu;s.r.argument=32u;
                    {
                        LmnMenuAnimationResult out=bitmap(&s,game_ds,ports);
                        if(out.status)return out;
                    }
                    s.r.source_cursor=pop(&s);
                }
            }
        }
#if MENU_ANIMATION_MUTATION == 4
        (void)pop(&s);s.r.count=saved_count;
#else
        s.r.count=pop(&s);
#endif
        s.r.source_cursor=arithmetic(&s,s.r.source_cursor,11u,0);
        s.r.count=(uint16_t)(s.r.count-1u);
    } while(s.r.count);
    return result(&s,CS_MenuAnimationTickReturn,LMN_MENU_ANIMATION_READY);
}

LmnMenuAnimationResult lmn_menu_animation_adapter(uint8_t *memory,const LmnRegs *r,uint16_t game_ds,
    enum LmnMenuAnimationEntry entry,const LmnRasterBus *bus,const LmnRasterBytePorts *ports) {
    LmnVideoRestoreState in={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnMenuAnimationResult out=lmn_menu_animation_core(memory,r->cs,game_ds,&in,entry,bus,ports);
    Animation s={memory,bus,out.state,out.code_segment};
    uint16_t ip=out.continuation;
    if(out.status==LMN_MENU_ANIMATION_READY)ip=pop(&s);
    out.state=s.r;out.continuation=ip;return out;
}
