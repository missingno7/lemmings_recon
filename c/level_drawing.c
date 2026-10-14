#include "level_drawing.h"
#include "vga_clear.h"
#include "drawing_layout.h"
#include "lemmings_sym.h"
#ifndef DRAWING_MUTATION
#define DRAWING_MUTATION 0
#endif
static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint8_t byte(uint8_t *m,uint32_t p,uint16_t f,const LmnRasterBus *b) {
    return b&&b->read_byte?b->read_byte(b->context,m,p,f):m[p];
}
static uint16_t word(uint8_t *m,uint16_t seg,uint16_t off,uint16_t f,const LmnRasterBus *b) {
    uint32_t p=physical(seg,off);
    uint8_t lo=byte(m,p,f,b),hi=byte(m,(p+1u)&0xfffffu,f,b);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void putword(uint8_t *m,uint16_t seg,uint16_t off,uint16_t v,uint16_t f,const LmnRasterBus *b) {
    uint32_t p=physical(seg,off);
    if(b&&b->write_byte) {
        b->write_byte(b->context,m,p,(uint8_t)v,f);
        b->write_byte(b->context,m,(p+1u)&0xfffffu,(uint8_t)(v>>8),f);
    } else {m[p]=(uint8_t)v;m[(p+1u)&0xfffffu]=(uint8_t)(v>>8);}
}
static void push(uint8_t *m,const LmnLevelDrawingCall *c,LmnLevelDrawingResult *s,uint16_t value,const LmnRasterBus *b) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    putword(m,c->stack_segment,s->stack_offset,value,s->flags,b);
}
static uint16_t pop(uint8_t *m,uint16_t ss,LmnLevelDrawingResult *s,const LmnRasterBus *b) {
    uint16_t value=word(m,ss,s->stack_offset,s->flags,b);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);return value;
}
static uint16_t increment_flags(uint16_t value,uint16_t flags) {
    uint16_t out=(uint16_t)(value+1u);unsigned low=out&255u,parity=0;
    for(unsigned i=0;i<8;i++)parity^=(low>>i)&1u;
    return (uint16_t)((flags&~0x8d4u)|(parity?0:4u)|((value&15u)==15u?0x10u:0u)|
        (out==0?0x40u:0u)|(out&0x8000u?0x80u:0u)|(value==0x7fffu?0x800u:0u));
}
LmnLevelDrawingResult lmn_initialize_level_drawing_core(uint8_t *m,const LmnLevelDrawingCall *c,const LmnRasterBus *bus) {
    LmnLevelDrawingResult s={0};LmnVgaClearResult clear;LmnDrawingLayoutResult layout;
    s.height_state=c->height_state;s.stack_offset=c->stack_offset;s.flags=c->flags;s.code_segment=c->code_segment;
    push(m,c,&s,CS_LevelDrawingAfterClear,bus);
    clear=lmn_clear_vga_bytes_core(m,c->stack_segment,s.stack_offset,0x4a40u,0x8880u,s.flags,bus);
    s.value=clear.value;s.count=clear.count;s.product_high=clear.port;
    s.output_cursor=clear.output_cursor;s.output_segment=clear.output_segment;s.stack_offset=clear.stack_offset;s.flags=clear.flags;
    s.continuation=pop(m,c->stack_segment,&s,bus);
    if(s.continuation!=CS_LevelDrawingAfterClear){s.changed_return=1;return s;}
    s.value=0x680u;s.height_state=0xa4u;s.product_high=0x4a40u;
    /* x86 far CALL pushes CS first, then the following IP. */
    push(m,c,&s,c->code_segment,bus);push(m,c,&s,CS_LevelDrawingAfterLayout,bus);
    layout=lmn_set_drawing_layout_core(m,c->data_segment,s.value,s.height_state,s.product_high,s.flags,bus);
    s.value=layout.value;s.product_high=layout.product_high;s.flags=layout.flags;
    s.continuation=pop(m,c->stack_segment,&s,bus);s.code_segment=pop(m,c->stack_segment,&s,bus);
#if DRAWING_MUTATION == 3
    s.continuation=CS_LevelDrawingAfterLayout;s.code_segment=c->code_segment;
#endif
    if(s.continuation!=CS_LevelDrawingAfterLayout||s.code_segment!=c->code_segment){s.changed_return=1;return s;}
    s.value=word(m,c->data_segment,SEG09A9_GraphicsResourceInputSegment,s.flags,bus);
    s.flags=increment_flags(s.value,s.flags);s.value=(uint16_t)(s.value+1u);
#if DRAWING_MUTATION == 1
    s.value=(uint16_t)(s.value+1u);
#endif
    putword(m,c->data_segment,SEG09A9_GraphicsResourceSegment,s.value,s.flags,bus);
    s.continuation=CS_InitializeLevelDrawing+30u;
    return s;
}
void lmn_level_drawing_adapter(uint8_t *m,LmnRegs *r,unsigned tail,const LmnRasterBus *bus) {
    LmnLevelDrawingResult s={0};
    if(tail) {
        LmnVgaClearResult clear=lmn_clear_vga_bytes_core(m,r->ss,r->sp,0xcc40u,
#if DRAWING_MUTATION == 2
            0x341u,
#else
            0x340u,
#endif
            r->flags,bus);
        s.value=clear.value;s.height_state=r->bx;s.count=clear.count;s.product_high=clear.port;
        s.output_cursor=clear.output_cursor;s.output_segment=clear.output_segment;
        s.stack_offset=clear.stack_offset;s.flags=clear.flags;s.code_segment=r->cs;
    } else {
        LmnLevelDrawingCall c={r->ds,r->ss,r->sp,r->cs,r->bx,r->flags};
        s=lmn_initialize_level_drawing_core(m,&c,bus);
    }
    r->ax=s.value;r->bx=s.height_state;r->cx=s.count;r->dx=s.product_high;r->di=s.output_cursor;r->es=s.output_segment;
    r->flags=s.flags;r->cs=s.code_segment;r->sp=s.stack_offset;
    r->ip=s.changed_return?s.continuation:pop(m,r->ss,&s,bus);r->sp=s.stack_offset;
}
