#include "generated_graphics.h"
#include "lemmings_sym.h"

#ifndef GENERATED_GRAPHICS_MUTATION
#define GENERATED_GRAPHICS_MUTATION 0
#endif

enum { CF=1,PF=4,AF=16,ZF=64,SF=128,OF=0x800,ARITH=0x8d5 };
static uint32_t physical(uint16_t s,uint16_t o) {
    return (((uint32_t)s<<4)+o)&0xfffffu;
}
static uint8_t read8(uint8_t *m,uint32_t p,uint16_t f,const LmnRasterBus *b) {
    return b&&b->read_byte ? b->read_byte(b->context,m,p,f):m[p];
}
static void write8(uint8_t *m,uint32_t p,uint8_t v,uint16_t f,const LmnRasterBus *b) {
    if(b&&b->write_byte)b->write_byte(b->context,m,p,v,f);else m[p]=v;
}
static uint16_t read16(uint8_t *m,uint16_t s,uint16_t o,uint16_t f,const LmnRasterBus *b) {
    uint32_t p=physical(s,o);uint8_t lo=read8(m,p,f,b),hi;
    hi=read8(m,(p+1u)&0xfffffu,f,b);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void push(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t v,uint16_t f,const LmnRasterBus *b) {
    uint32_t p;
    *sp=(uint16_t)(*sp-2u);p=physical(ss,*sp);
    write8(m,p,(uint8_t)v,f,b);write8(m,(p+1u)&0xfffffu,(uint8_t)(v>>8),f,b);
}
static uint16_t pop(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t f,const LmnRasterBus *b) {
    uint16_t v=read16(m,ss,*sp,f,b);*sp=(uint16_t)(*sp+2u);return v;
}
static uint16_t add_flags(uint16_t f,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t v=(uint16_t)sum,out=0;
    unsigned parity=0,n;
    for(n=0;n<8;++n)parity^=(v>>n)&1u;
    if(!parity)out|=PF;
    if(!v)out|=ZF;
    if(v&0x8000u)out|=SF;
    if(sum>0xffffu)out|=CF;
    if((a^b^v)&AF)out|=AF;
    if((~(a^b)&(a^v)&0x8000u)!=0)out|=OF;
    return (uint16_t)((f&~ARITH)|out);
}

LmnGeneratedGraphicsResult lmn_generate_graphics_mask_banks_core(uint8_t *m,
    const LmnGeneratedGraphicsCall *call,const LmnRasterBus *bus) {
    uint16_t ds=call->data_segment,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t bx=call->column_repetitions,dx=call->shift_state,f=call->flags;
    uint16_t es,si=0,di=0,ax=0,cx=0,target;
    unsigned group;
    LmnMaskGeneratorCall child;
    LmnMaskGeneratorResult result;
    LmnGeneratedGraphicsResult out;
    push(m,ss,&sp,ds,f,bus);
#if GENERATED_GRAPHICS_MUTATION == 1
    {
        uint16_t old_ds=ds;
        ds=read16(m,old_ds,SEG09A9_GraphicsResourceSegment,f,bus);
        es=read16(m,old_ds,SEG09A9_GeneratedGraphicsBufferSegment,f,bus);
    }
#else
    es=read16(m,ds,SEG09A9_GeneratedGraphicsBufferSegment,f,bus);
    ds=read16(m,ds,SEG09A9_GraphicsResourceSegment,f,bus);
#endif
    /* XOR SI,SI and XOR DI,DI leave AF undefined. */
    f=(uint16_t)((f&~(CF|PF|ZF|SF|OF))|PF|ZF);
    for(group=0;group<4;++group) {
        cx=group==0?8u:group==1?4u:group==2?0x16u:0xau;
        do {
            uint16_t continuation=group==0?0x5adau:group==1?0x5aecu:
                                  group==2?0x5afau:0x5b09u;
            uint16_t advance=group==0?0x14u:group==1?0x1au:group==2?0x2cu:8u;
#if GENERATED_GRAPHICS_MUTATION == 2
            uint16_t saved_count=cx;
#endif
            if(group!=2)push(m,ss,&sp,cx,f,bus);
            if(group!=2)cx=group==0?0xau:group==1?0xdu:8u;
            bx=(uint16_t)((bx&0xff00u)|1u);
            push(m,ss,&sp,continuation,f,bus);
            child=(LmnMaskGeneratorCall){ds,es,ss,sp,si,di,bx,cx,dx,f};
            result=group==3?lmn_generate_byte_mask_shifts_core(m,&child,bus):
                            lmn_generate_word_mask_shifts_core(m,&child,bus);
            ax=result.value;bx=result.column_repetitions;cx=result.row_count;
            dx=result.shift_state;si=result.source_cursor;di=result.output_cursor;
            sp=result.stack_offset;f=result.flags;
            target=pop(m,ss,&sp,f,bus);
#if GENERATED_GRAPHICS_MUTATION != 3
            if(target!=continuation) {
                out=(LmnGeneratedGraphicsResult){ax,bx,cx,dx,si,di,ds,es,sp,f,target,0};
                return out;
            }
#else
            (void)target;
#endif
#if GENERATED_GRAPHICS_MUTATION == 5
            if(group==0)advance=0x16u;
#endif
            f=add_flags(f,si,advance);si=(uint16_t)(si+advance);
            if(group==2)break;
            cx=pop(m,ss,&sp,f,bus);
#if GENERATED_GRAPHICS_MUTATION == 2
            cx=saved_count;
#endif
            cx=(uint16_t)(cx-1u);
        } while(cx);
    }
    ds=pop(m,ss,&sp,f,bus);
    out=(LmnGeneratedGraphicsResult){ax,bx,cx,dx,si,di,ds,es,sp,f,0x5b10u,1};
    return out;
}

void lmn_generate_graphics_mask_banks_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnGeneratedGraphicsCall call={r->ds,r->ss,r->sp,r->bx,r->dx,r->flags};
#if GENERATED_GRAPHICS_MUTATION == 4
    uint16_t saved_return=read16(m,r->ss,r->sp,r->flags,bus);
#endif
    LmnGeneratedGraphicsResult out=lmn_generate_graphics_mask_banks_core(m,&call,bus);
    r->ax=out.value;r->bx=out.column_repetitions;r->cx=out.row_count;
    r->dx=out.shift_state;r->si=out.source_cursor;r->di=out.output_cursor;
    r->ds=out.source_segment;r->es=out.output_segment;r->sp=out.stack_offset;
    r->flags=out.flags;r->ip=out.continuation;
    if(out.ready_to_return) {
        r->ip=pop(m,r->ss,&r->sp,r->flags,bus);
#if GENERATED_GRAPHICS_MUTATION == 4
        r->ip=saved_return;
#endif
    }
}
