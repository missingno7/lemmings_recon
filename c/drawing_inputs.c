#include "drawing_inputs.h"
#include "drawing_clip.h"
#include "drawing_dirty.h"
#include "lemmings_sym.h"
#ifndef INPUTS_MUTATION
#define INPUTS_MUTATION 0
#endif
static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint8_t byte(uint8_t *m,uint32_t p,uint16_t flags,const LmnRasterBus *b) {
    return b&&b->read_byte?b->read_byte(b->context,m,p,flags):m[p];
}
static uint16_t word(uint8_t *m,uint16_t seg,uint16_t off,uint16_t flags,const LmnRasterBus *b) {
    uint32_t p=physical(seg,off);uint8_t low=byte(m,p,flags,b);
    return (uint16_t)(low|((uint16_t)byte(m,(p+1u)&0xfffffu,flags,b)<<8));
}
static void putword(uint8_t *m,uint16_t seg,uint16_t off,uint16_t value,uint16_t flags,const LmnRasterBus *b) {
    uint32_t p=physical(seg,off);
    if(b&&b->write_byte){b->write_byte(b->context,m,p,(uint8_t)value,flags);b->write_byte(b->context,m,(p+1u)&0xfffffu,(uint8_t)(value>>8),flags);}
    else {m[p]=(uint8_t)value;m[(p+1u)&0xfffffu]=(uint8_t)(value>>8);}
}
static uint16_t pop(uint8_t *m,uint16_t ss,LmnDrawingInputsResult *s,const LmnRasterBus *b) {
    uint16_t value=word(m,ss,s->stack_offset,s->flags,b);s->stack_offset=(uint16_t)(s->stack_offset+2u);return value;
}
static void push(uint8_t *m,uint16_t ss,LmnDrawingInputsResult *s,uint16_t value,const LmnRasterBus *b) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);putword(m,ss,s->stack_offset,value,s->flags,b);
}
static uint16_t szp(uint16_t value,unsigned width) {
    unsigned parity=0;for(unsigned i=0;i<8;i++)parity^=(value>>i)&1u;
    return (uint16_t)((parity?0u:4u)|(value?0u:0x40u)|(value&(width==8?0x80u:0x8000u)?0x80u:0u));
}
static uint16_t logic(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&~0x8d5u)|szp(value,width));
}
static uint16_t cmp8(uint16_t flags,uint8_t a,uint8_t b) {
    uint8_t v=(uint8_t)(a-b);
    return (uint16_t)((flags&~0x8d5u)|szp(v,8)|(a<b?1u:0u)|((a^b^v)&16u)|(((a^b)&(a^v)&0x80u)?0x800u:0u));
}
LmnDrawingInputsResult lmn_prepare_planar_drawing_inputs_core(uint8_t *m,const LmnDrawingInputsCall *c,const LmnRasterBus *bus) {
    LmnDrawingInputsResult s={0};uint32_t extent;uint8_t enabled;
    s.left=c->source_pitch;s.top=c->top;s.packed_height=c->packed_height;s.width=c->width;
    s.source_cursor=c->source_cursor;s.destination_cursor=c->destination_cursor;s.control=c->control;
    s.stack_offset=c->stack_offset;s.flags=c->flags;
    putword(m,c->data_segment,SEG09A9_DrawingSourcePitchBytes,s.left,s.flags,bus);
    s.packed_height&=255u;s.flags=logic(s.flags,0,8);extent=(uint32_t)s.left*s.packed_height;
    s.left=(uint16_t)extent;s.width=(uint16_t)(extent>>16);
    /* MUL defines CF/OF only; its other arithmetic bits stay representative. */
    s.flags=(uint16_t)((s.flags&~0x801u)|(s.width?0x801u:0u));
    putword(m,c->data_segment,SEG09A9_DrawingSourcePlaneExtent,s.left,s.flags,bus);
    s.packed_height=pop(m,c->stack_segment,&s,bus);s.width=pop(m,c->stack_segment,&s,bus);s.left=pop(m,c->stack_segment,&s,bus);
    putword(m,c->data_segment,SEG09A9_DrawingVerticalSkipBytes,0,s.flags,bus);
    putword(m,c->data_segment,SEG09A9_DrawingHorizontalSkipBytes,0,s.flags,bus);
    s.flags=logic(s.flags,(uint16_t)(s.control&12u),16);
    if(s.control&12u) {
        LmnDrawingClipCall cc;LmnDrawingClipResult clipped;
        push(m,c->stack_segment,&s,CS_PlanarInputsAfterClip,bus);
        cc=(LmnDrawingClipCall){c->data_segment,c->stack_segment,s.stack_offset,s.left,s.top,s.packed_height,s.width,
            s.source_cursor,s.destination_cursor,s.control,s.flags};
        clipped=lmn_clip_planar_drawing_rectangle_core(m,&cc,bus);
        s.left=clipped.left;s.top=clipped.top;s.packed_height=clipped.packed_height;s.width=clipped.width;
        s.source_cursor=clipped.source_cursor;s.destination_cursor=clipped.destination_cursor;s.control=clipped.control;
        s.stack_offset=clipped.stack_offset;s.flags=clipped.flags;s.continuation=pop(m,c->stack_segment,&s,bus);
        if(s.continuation!=CS_PlanarInputsAfterClip){s.changed_return=1;return s;}
        s.flags=logic(s.flags,s.left,16);
        if(s.flags&0x80u){s.continuation=CS_PlanarDrawingAbortReturn;return s;}
    }
    enabled=byte(m,physical(c->data_segment,SEG09A9_DrawingDirtyCellsEnabledByte),s.flags,bus);
    s.flags=cmp8(s.flags,enabled,255u);
#if INPUTS_MUTATION == 1
    enabled=0;
#endif
    if(enabled==255u) {
        LmnDrawingDirtyCall dc;LmnDrawingDirtyResult dirty;
        push(m,c->stack_segment,&s,CS_PlanarInputsReady,bus);
        dc=(LmnDrawingDirtyCall){c->data_segment,c->stack_segment,s.stack_offset,s.left,s.top,s.packed_height,s.width,
            s.source_cursor,s.destination_cursor,s.control,s.flags};
        dirty=lmn_mark_drawing_dirty_cells_core(m,&dc,bus);
        s.left=dirty.left;s.top=dirty.top;s.packed_height=dirty.packed_height;s.width=dirty.width;
        s.source_cursor=dirty.source_cursor;s.destination_cursor=dirty.destination_cursor;s.control=dirty.control;
        s.stack_offset=dirty.stack_offset;s.flags=dirty.flags;s.continuation=pop(m,c->stack_segment,&s,bus);
#if INPUTS_MUTATION == 3
        s.continuation=CS_PlanarInputsReady;
#endif
        if(s.continuation!=CS_PlanarInputsReady){s.changed_return=1;return s;}
    }
#if INPUTS_MUTATION == 2
    s.packed_height=c->packed_height;
#endif
    s.continuation=CS_PlanarInputsReady;return s;
}
void lmn_prepare_planar_drawing_inputs_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnDrawingInputsCall c={r->ds,r->ss,r->sp,r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->flags};
    LmnDrawingInputsResult s=lmn_prepare_planar_drawing_inputs_core(m,&c,bus);
    r->ax=s.left;r->bx=s.top;r->cx=s.packed_height;r->dx=s.width;r->si=s.source_cursor;r->di=s.destination_cursor;
    r->bp=s.control;r->sp=s.stack_offset;r->flags=s.flags;r->ip=s.continuation;
}
