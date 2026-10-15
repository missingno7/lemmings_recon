#include "entity_mask.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif

enum { CF=1,PF=4,AF=16,ZF=64,SF=128,IF=0x200,DF=0x400,OF=0x800,ARITH=0x8d5 };
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
static void write16(uint8_t *m,uint16_t s,uint16_t o,uint16_t v,uint16_t f,const LmnRasterBus *b) {
    uint32_t p=physical(s,o);
    write8(m,p,(uint8_t)v,f,b);write8(m,(p+1u)&0xfffffu,(uint8_t)(v>>8),f,b);
}
static void output(uint8_t *m,uint16_t ss,uint16_t mirror,uint16_t port,
                   uint16_t v,uint16_t f,const LmnRasterBus *b) {
    write16(m,ss,mirror,v,f,b);
    if(b&&b->out_word)b->out_word(b->context,port,v,f);
}
static void push(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t v,uint16_t f,const LmnRasterBus *b) {
    *sp=(uint16_t)(*sp-2u);write16(m,ss,*sp,v,f,b);
}
static uint16_t pop(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t f,const LmnRasterBus *b) {
    uint16_t v=read16(m,ss,*sp,f,b);*sp=(uint16_t)(*sp+2u);return v;
}
static uint16_t szp(uint16_t v) {
    unsigned parity=0,n;uint16_t out=0;
    for(n=0;n<8;++n)parity^=(v>>n)&1u;
    if(!parity)out|=PF;
    if(!v)out|=ZF;
    if(v&0x8000u)out|=SF;
    return out;
}
static uint16_t logic_flags(uint16_t f,uint16_t v) {
    return (uint16_t)((f&~ARITH)|szp(v));
}
static uint16_t add_flags(uint16_t f,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t v=(uint16_t)sum,out=szp(v);
    if(sum>0xffffu)out|=CF;
    if((a^b^v)&AF)out|=AF;
    if((~(a^b)&(a^v)&0x8000u)!=0)out|=OF;
    return (uint16_t)((f&~ARITH)|out);
}
static uint16_t sub_flags(uint16_t f,uint16_t a,uint16_t b) {
    uint16_t v=(uint16_t)(a-b),out=szp(v);
    if(a<b)out|=CF;
    if((a^b^v)&AF)out|=AF;
    if(((a^b)&(a^v)&0x8000u)!=0)out|=OF;
    return (uint16_t)((f&~ARITH)|out);
}
static uint16_t shift_right(uint16_t v,uint16_t *f) {
    uint16_t out=(uint16_t)(v>>1);
    *f=(uint16_t)((*f&~(CF|PF|ZF|SF|OF))|szp(out)|
                 ((v&1u)?CF:0)|((v&0x8000u)?OF:0));
    return out;
}
static uint16_t shift_left(uint16_t v,uint16_t *f) {
    uint16_t out=(uint16_t)(v<<1);
    *f=(uint16_t)((*f&~(CF|PF|ZF|SF|OF))|szp(out)|
                 ((v&0x8000u)?CF:0)|(((v^out)&0x8000u)?OF:0));
    return out;
}
static uint16_t step(uint16_t f,uint16_t amount) {
#if MUTATION == 3
    (void)f;return amount;
#else
    return (f&DF)?(uint16_t)(0u-amount):amount;
#endif
}

LmnEntityMaskResult lmn_draw_clipped_entity_mask_core(uint8_t *m,
    const LmnEntityMaskCall *call,const LmnRasterBus *bus) {
    uint16_t ds=call->data_segment,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t si=call->record_cursor,f=call->flags;
    uint16_t ax=0,bx=0,cx=0x16u,dx=0x3ceu,di,y,n;
    uint32_t product;
#if MUTATION == 2
    uint16_t saved_count;
#endif
    f=logic_flags(f,0);
    output(m,ss,SEG143E_VgaSetResetMirror,dx,0x0000u,f,bus);
    output(m,ss,SEG143E_VgaEnableSetResetMirror,dx,0x0f01u,f,bus);
    output(m,ss,SEG143E_VgaDataRotateMirror,dx,0x0003u,f,bus);
    ax=0xa000u;
    y=read16(m,ds,(uint16_t)(si+2u),f,bus);
    f=sub_flags(f,y,0x1eu);di=(uint16_t)(y-0x1eu);
    if(di&0x8000u) {
        f=add_flags(f,cx,di);cx=(uint16_t)(cx+di);
        f=sub_flags(f,0,di);di=(uint16_t)(0u-di);
#if MUTATION == 1
        f=sub_flags(f,di,0x14u);
        if(di>0x14u)
#else
        f=sub_flags(f,di,0x15u);
        if(di>0x15u)
#endif
            return (LmnEntityMaskResult){ax,bx,cx,dx,si,di,ds,0xa000u,sp,f};
        bx=di;di=0;f=logic_flags(f,0);
    }
#if MUTATION == 2
    saved_count=cx;
#endif
    push(m,ss,&sp,cx,f,bus);push(m,ss,&sp,bx,f,bus);
    ax=0xd0u;push(m,ss,&sp,dx,f,bus);
    product=(uint32_t)ax*di;ax=(uint16_t)product;dx=(uint16_t)(product>>16);
    f=(uint16_t)((f&~(CF|OF))|(dx?(CF|OF):0));
    di=ax;dx=pop(m,ss,&sp,f,bus);
    cx=read16(m,ds,si,f,bus);
    f=sub_flags(f,cx,8);cx=(uint16_t)(cx-8u);
    for(n=0;n<3;++n)cx=shift_right(cx,&f);
    f=add_flags(f,di,cx);di=(uint16_t)(di+cx);
    f=add_flags(f,di,0x4a40u);di=(uint16_t)(di+0x4a40u);
    ax=pop(m,ss,&sp,f,bus);bx=ax;
    f=add_flags(f,ax,ax);ax=(uint16_t)(ax+ax);
    f=add_flags(f,ax,bx);ax=(uint16_t)(ax+bx);bx=ax;
    cx=pop(m,ss,&sp,f,bus);
#if MUTATION == 2
    cx=saved_count;
#endif
    push(m,ss,&sp,si,f,bus);
    ax=read16(m,ds,si,f,bus);
    f=sub_flags(f,ax,8);ax=(uint16_t)(ax-8u);
    ax&=7u;f=logic_flags(f,ax);
    ax=shift_left(ax,&f);si=ax;
    for(n=0;n<5;++n)ax=shift_left(ax,&f);
    f=add_flags(f,si,ax);si=(uint16_t)(si+ax);
    f=add_flags(f,si,0x0c60u);si=(uint16_t)(si+0x0c60u);
    f=add_flags(f,si,bx);si=(uint16_t)(si+bx);
    push(m,ss,&sp,ds,f,bus);
    ds=read16(m,ds,SEG09A9_GeneratedGraphicsBufferSegment,f,bus);
    f&=(uint16_t)~IF;
    do {
        ax=read16(m,ds,si,f,bus);si=(uint16_t)(si+step(f,2));bx=ax;
        for(n=0;n<3;++n) {
            uint8_t mask;
            if(n==2) {
                uint8_t value=read8(m,physical(ds,si),f,bus);
                ax=(uint16_t)((ax&0xff00u)|value);
                si=(uint16_t)(si+step(f,1));
            }
            mask=n==0?(uint8_t)bx:n==1?(uint8_t)(bx>>8):(uint8_t)ax;
#if MUTATION != 4
            (void)read8(m,physical(0xa000u,di),f,bus);
#endif
            ax=(uint16_t)(((uint16_t)mask<<8)|8u);
            output(m,ss,SEG143E_VgaBitMaskMirror,dx,ax,f,bus);
            ax=(uint16_t)(((uint16_t)mask<<8)|mask);
            write8(m,physical(0xa000u,di),mask,f,bus);
            di=(uint16_t)(di+step(f,1));
        }
        f=add_flags(f,di,0xcdu);di=(uint16_t)(di+0xcdu);
        cx=(uint16_t)(cx-1u);
    } while(cx);
#if MUTATION == 6
    f=(uint16_t)(f|(call->flags&IF));
#else
    f|=IF;
#endif
    ds=pop(m,ss,&sp,f,bus);si=pop(m,ss,&sp,f,bus);
    return (LmnEntityMaskResult){ax,bx,cx,dx,si,di,ds,0xa000u,sp,f};
}

void lmn_draw_clipped_entity_mask_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnEntityMaskCall call={r->ds,r->ss,r->sp,r->si,r->flags};
#if MUTATION == 5
    uint16_t target=read16(m,r->ss,r->sp,r->flags,bus);
#endif
    LmnEntityMaskResult out=lmn_draw_clipped_entity_mask_core(m,&call,bus);
    r->ax=out.value;r->bx=out.mask_word;r->cx=out.row_count;r->dx=out.port;
    r->si=out.source_cursor;r->di=out.destination_offset;r->ds=out.data_segment;
    r->es=out.output_segment;r->sp=out.stack_offset;r->flags=out.flags;
#if MUTATION == 5
    r->ip=target;
#else
    r->ip=pop(m,r->ss,&r->sp,r->flags,bus);
#endif
#if MUTATION == 5
    r->sp=(uint16_t)(r->sp+2u);
#endif
}
