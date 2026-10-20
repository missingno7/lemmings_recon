#include "level_preview.h"
#include "lemmings_sym.h"

#ifndef LEVEL_PREVIEW_MUTATION
#define LEVEL_PREVIEW_MUTATION 0
#endif

enum { CF=1,PF=4,AF=16,ZF=64,SF=128,IF=512,OF=2048,ARITH=0x8D5 };
typedef struct Preview {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t continuation;
    LmnLevelPreviewStatus status;
} Preview;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xFFFFFu;
}
static uint8_t read_byte(Preview *p,uint32_t address) {
    address&=0xFFFFFu;
    return p->bus&&p->bus->read_byte?
        p->bus->read_byte(p->bus->context,p->memory,address,p->r.flags):p->memory[address];
}
static void write_byte(Preview *p,uint32_t address,uint8_t value) {
    address&=0xFFFFFu;
    if(p->bus&&p->bus->write_byte)
        p->bus->write_byte(p->bus->context,p->memory,address,value,p->r.flags);
    else p->memory[address]=value;
}
static uint16_t read_word(Preview *p,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(p,address),high=read_byte(p,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}
static void write_word(Preview *p,uint16_t segment,uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(p,address,(uint8_t)value);write_byte(p,address+1u,(uint8_t)(value>>8));
}
static void push(Preview *p,uint16_t value) {
    p->r.sp=(uint16_t)(p->r.sp-2u);write_word(p,p->r.ss,p->r.sp,value);
}
static uint16_t pop(Preview *p) {
    uint16_t value=read_word(p,p->r.ss,p->r.sp);p->r.sp=(uint16_t)(p->r.sp+2u);return value;
}
static uint16_t szp(uint16_t value,unsigned sign) {
    uint8_t low=(uint8_t)value;unsigned parity=0;
    for(unsigned bit=0;bit<8;bit++)parity^=(low>>bit)&1u;
    return (uint16_t)((parity?0:PF)|(value==0?ZF:0)|(value&sign?SF:0));
}
static void logic(Preview *p,uint16_t value,unsigned sign) {
    p->r.flags=(uint16_t)((p->r.flags&~ARITH)|szp(value,sign));
}
static uint16_t add(Preview *p,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+right;uint16_t value=(uint16_t)wide;
    p->r.flags=(uint16_t)((p->r.flags&~ARITH)|szp(value,0x8000u)|
        (wide>65535u?CF:0)|((left^right^value)&AF)|
        ((~(left^right)&(left^value)&0x8000u)?OF:0));return value;
}
static uint16_t change(Preview *p,uint16_t before,int increment) {
    uint16_t value=(uint16_t)(before+(increment?1u:0xFFFFu));
    p->r.flags=(uint16_t)((p->r.flags&~(ARITH&~CF))|szp(value,0x8000u)|
        ((before^1u^value)&AF)|((increment?before==0x7FFFu:before==0x8000u)?OF:0));
    return value;
}
static int output(Preview *p,uint16_t mirror,uint16_t value,uint16_t ip) {
    p->r.ax=value;write_word(p,p->r.ss,mirror,value);
    if(!p->bus||!p->bus->out_word) {
        p->continuation=ip;p->status=LMN_LEVEL_PREVIEW_MISSING_WORD_OUTPUT;return 0;
    }
    p->bus->out_word(p->bus->context,p->r.dx,p->r.ax,p->r.flags);return 1;
}
static uint8_t sampled_bits(uint8_t a,uint8_t b,uint8_t c,uint8_t d) {
    uint8_t value=(uint8_t)(((a&0x20u)<<2)|((a&2u)<<5)|(b&0x20u)|((b&2u)<<3)|
        ((c&0x20u)>>2)|((c&2u)<<1)|((d&0x20u)>>4)|((d&2u)>>1));
#if LEVEL_PREVIEW_MUTATION == 1
    value^=1u;
#endif
    return value;
}
static LmnLevelPreviewResult result(const Preview *p) {
    const LmnRegs *r=&p->r;
    LmnLevelPreviewResult out={{r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,
        r->ds,r->es,r->ss,r->sp,r->flags},r->cs,p->continuation,p->status};return out;
}
LmnLevelPreviewResult lmn_draw_level_preview_core(uint8_t *memory,
    uint16_t cs,const LmnLevelPreviewState *input,const LmnRasterBus *bus) {
    const LmnLevelPreviewState *s=input;
    Preview p={memory,bus,{s->value,s->base_value,s->count,s->argument,
        s->source_cursor,s->output_cursor,s->frame_cursor,s->stack_offset,
        cs,s->data_segment,s->extra_segment,s->stack_segment,0,s->flags},
        CS_LevelPreviewReturn,LMN_LEVEL_PREVIEW_READY};
    LmnRegs *r=&p.r;push(&p,r->ds);
    r->di=read_word(&p,r->ds,SEG09A9_DrawingOrigin);
    uint16_t page=read_word(&p,r->ds,SEG09A9_DrawingPageByteOffset);
    r->di=add(&p,r->di,page);r->di=add(&p,r->di,0x64Fu);r->si=0x4F22u;
    r->dx=0x3C4u;
    if(!output(&p,8,0x0F02u,CS_LevelPreviewInitialOutput))return result(&p);
    r->dx=0x3CEu;r->ax=0;logic(&p,0,0x8000u);
    if(!output(&p,10,0,CS_DrawLevelPreview+0x24u))return result(&p);
    if(!output(&p,12,1,CS_DrawLevelPreview+0x2Cu))return result(&p);
    if(!output(&p,0,5,CS_DrawLevelPreview+0x34u))return result(&p);
    if(!output(&p,2,
#if LEVEL_PREVIEW_MUTATION == 3
        3u,
#else
        0x1003u,
#endif
        CS_DrawLevelPreview+0x3Cu))return result(&p);
    if(!output(&p,14,0xFF08u,CS_DrawLevelPreview+0x44u))return result(&p);
    r->ax=0xA000u;r->es=r->ax;r->ds=r->ax;r->cx=39u;
    do {
        push(&p,r->cx);push(&p,r->si);push(&p,r->di);r->cx=52u;
        do {
            push(&p,r->cx);
            for(unsigned plane=0;plane<4;plane++) {
                push(&p,r->dx);r->dx=0x3C4u;
                if(!output(&p,8,
#if LEVEL_PREVIEW_MUTATION == 4
                    0x0102u,
#else
                    (uint16_t)((0x100u<<plane)|2u),
#endif
                    (uint16_t)(CS_DrawLevelPreview+0x61u+plane*0x76u)))return result(&p);
                r->dx=pop(&p);
                if(!output(&p,16,(uint16_t)((plane<<8)|4u),
                    (uint16_t)(CS_DrawLevelPreview+0x6Au+plane*0x76u)))return result(&p);
                uint8_t a=read_byte(&p,physical(r->ds,r->si));
                uint8_t b=read_byte(&p,physical(r->ds,(uint16_t)(r->si+1u)));
                r->cx=(uint16_t)(((uint16_t)a<<8)|b);
                uint8_t c=read_byte(&p,physical(r->ds,(uint16_t)(r->si+2u)));
                uint8_t d=read_byte(&p,physical(r->ds,(uint16_t)(r->si+3u)));
                r->bx=(uint16_t)(((uint16_t)c<<8)|d);
                uint8_t packed=sampled_bits(a,b,c,d);logic(&p,packed,0x80u);
                r->ax=(uint16_t)(((uint16_t)packed<<8)|((d>>1)&1u));r->flags&=(uint16_t)~IF;
#if LEVEL_PREVIEW_MUTATION != 2
                r->ax=(uint16_t)((r->ax&0xFF00u)|read_byte(&p,physical(r->ds,r->di)));
#endif
                write_byte(&p,physical(r->ds,r->di),(uint8_t)(r->ax>>8));
#if LEVEL_PREVIEW_MUTATION != 7
                r->flags|=IF;
#endif
            }
            r->di=change(&p,r->di,1);r->si=add(&p,r->si,4u);r->cx=pop(&p);
#if LEVEL_PREVIEW_MUTATION == 9
            r->cx=1u;
#endif
            r->cx=change(&p,r->cx,0);
        }while(r->cx);
        r->di=pop(&p);r->si=pop(&p);
        r->di=add(&p,r->di,
#if LEVEL_PREVIEW_MUTATION == 6
            52u
#else
            80u
#endif
            );
        r->si=add(&p,r->si,
#if LEVEL_PREVIEW_MUTATION == 5
            208u
#else
            832u
#endif
            );
        r->cx=pop(&p);r->cx=change(&p,r->cx,0);
    }while(r->cx);
    r->ds=pop(&p);
#if LEVEL_PREVIEW_MUTATION == 8
    r->ds=input->data_segment;
#endif
    return result(&p);
}
LmnLevelPreviewResult lmn_draw_level_preview_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    LmnLevelPreviewState s={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,
        r->ds,r->es,r->ss,r->sp,r->flags};
    LmnLevelPreviewResult out=lmn_draw_level_preview_core(memory,r->cs,&s,bus);
    if(!out.status) {
        Preview p={memory,bus,{0},out.continuation,out.status};
        p.r.ss=out.state.stack_segment;p.r.sp=out.state.stack_offset;p.r.flags=out.state.flags;
        out.continuation=pop(&p);out.state.stack_offset=p.r.sp;
    }
    s=out.state;r->ax=s.value;r->bx=s.base_value;r->cx=s.count;r->dx=s.argument;
    r->si=s.source_cursor;r->di=s.output_cursor;r->bp=s.frame_cursor;
    r->ds=s.data_segment;r->es=s.extra_segment;r->ss=s.stack_segment;r->sp=s.stack_offset;
    r->flags=s.flags;r->cs=out.code_segment;r->ip=out.continuation;return out;
}
