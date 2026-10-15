#include "entity_mask_rows.h"
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
static uint16_t szp(uint16_t v,unsigned bits) {
    unsigned parity=0,n;uint16_t out=0;
    for(n=0;n<8;++n)parity^=(v>>n)&1u;
    if(!parity)out|=PF;
    if(!v)out|=ZF;
    if(v&(1u<<(bits-1u)))out|=SF;
    return out;
}
static uint16_t logic_flags(uint16_t f,uint16_t v) {
    return (uint16_t)((f&~ARITH)|szp(v,16));
}
static uint16_t add_flags(uint16_t f,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t v=(uint16_t)sum,out=szp(v,16);
    if(sum>0xffffu)out|=CF;
    if((a^b^v)&AF)out|=AF;
    if((~(a^b)&(a^v)&0x8000u)!=0)out|=OF;
    return (uint16_t)((f&~ARITH)|out);
}
static uint16_t sub_flags(uint16_t f,uint16_t a,uint16_t b,unsigned bits) {
    uint16_t v=(uint16_t)(a-b),out;
    if(bits==8)v&=0xffu;
    out=szp(v,bits);
    if(a<b)out|=CF;
    if((a^b^v)&AF)out|=AF;
    if(((a^b)&(a^v)&(1u<<(bits-1u)))!=0)out|=OF;
    return (uint16_t)((f&~ARITH)|out);
}
static uint16_t shift_right(uint16_t v,uint16_t *f) {
    uint16_t out=(uint16_t)(v>>1);
    *f=(uint16_t)((*f&~(CF|PF|ZF|SF|OF))|szp(out,16)|
                 ((v&1u)?CF:0)|((v&0x8000u)?OF:0));
    return out;
}
static uint16_t shift_left(uint16_t v,uint16_t *f) {
    uint16_t out=(uint16_t)(v<<1);
    *f=(uint16_t)((*f&~(CF|PF|ZF|SF|OF))|szp(out,16)|
                 ((v&0x8000u)?CF:0)|(((v^out)&0x8000u)?OF:0));
    return out;
}
static uint16_t step(uint16_t f,uint16_t amount) {
#if MUTATION == 4
    (void)f;return amount;
#else
    return (f&DF)?(uint16_t)(0u-amount):amount;
#endif
}

/* Register temporaries only. Every saved word and source byte stays in the
   caller's canonical memory; this is not a converted record or mask cache. */
typedef struct MaskRows {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ds,ss,sp,si,ax,bx,cx,dx,di,bp,flags;
} MaskRows;

static void setup(MaskRows *s) {
    s->dx=0x3ceu;s->ax=0;s->flags=logic_flags(s->flags,0);
    output(s->memory,s->ss,SEG143E_VgaSetResetMirror,s->dx,s->ax,s->flags,s->bus);
    s->ax=0x0f01u;
    output(s->memory,s->ss,SEG143E_VgaEnableSetResetMirror,s->dx,s->ax,s->flags,s->bus);
    s->ax=3;
    output(s->memory,s->ss,SEG143E_VgaDataRotateMirror,s->dx,s->ax,s->flags,s->bus);
    s->ax=0xa000u;
}

static void draw_rows(MaskRows *s,uint16_t entry_flags) {
    unsigned n;
    s->flags&=(uint16_t)~IF;
    do {
        s->ax=read16(s->memory,s->ds,s->si,s->flags,s->bus);
        s->si=(uint16_t)(s->si+step(s->flags,2));s->bx=s->ax;
        for(n=0;n<3;++n) {
            uint8_t mask;
            if(n==2) {
                uint8_t value=read8(s->memory,physical(s->ds,s->si),s->flags,s->bus);
                s->ax=(uint16_t)((s->ax&0xff00u)|value);
                s->si=(uint16_t)(s->si+step(s->flags,1));
            }
            mask=n==0?(uint8_t)s->bx:n==1?(uint8_t)(s->bx>>8):(uint8_t)s->ax;
#if MUTATION != 5
            (void)read8(s->memory,physical(0xa000u,s->di),s->flags,s->bus);
#endif
            s->ax=(uint16_t)(((uint16_t)mask<<8)|8u);
            output(s->memory,s->ss,SEG143E_VgaBitMaskMirror,s->dx,s->ax,s->flags,s->bus);
            s->ax=(uint16_t)(((uint16_t)mask<<8)|mask);
            write8(s->memory,physical(0xa000u,s->di),mask,s->flags,s->bus);
            s->di=(uint16_t)(s->di+step(s->flags,1));
        }
        s->flags=add_flags(s->flags,s->di,0xcdu);s->di=(uint16_t)(s->di+0xcdu);
        s->cx=(uint16_t)(s->cx-1u);
    } while(s->cx);
#if MUTATION == 7
    s->flags=(uint16_t)(s->flags|(entry_flags&IF));
#else
    (void)entry_flags;s->flags|=IF;
#endif
    s->ds=pop(s->memory,s->ss,&s->sp,s->flags,s->bus);
    s->si=pop(s->memory,s->ss,&s->sp,s->flags,s->bus);
}

static LmnEntityMaskRowsResult draw(uint8_t *memory,
    const LmnEntityMaskRowsCall *call,const LmnRasterBus *bus,unsigned thirteen) {
    MaskRows s={memory,bus,call->data_segment,call->stack_segment,
                call->stack_offset,call->record_cursor,call->selection,
                0,0,0,0,call->alignment_index,call->flags};
    uint16_t word;uint32_t product;unsigned n;
#if MUTATION == 3
    uint16_t saved_base;
#endif
#if MUTATION == 9
    uint16_t saved_sum=0;
#endif
    if(!thirteen) {
        for(n=0;n<4;++n)s.ax=shift_left(s.ax,&s.flags);
        s.dx=s.ax;
        for(n=0;n<4;++n)s.ax=shift_left(s.ax,&s.flags);
        s.flags=sub_flags(s.flags,s.ax,s.dx,16);s.ax=(uint16_t)(s.ax-s.dx);
#if MUTATION == 1
        s.ax=(uint16_t)(s.ax+1u);
#endif
    } else {
        for(n=0;n<3;++n)s.ax=shift_left(s.ax,&s.flags);
        s.bx=s.ax;
        for(n=0;n<3;++n)s.ax=shift_left(s.ax,&s.flags);
        s.flags=add_flags(s.flags,s.bx,s.ax);s.bx=(uint16_t)(s.bx+s.ax);
        s.ax=shift_left(s.ax,&s.flags);
        s.flags=add_flags(s.flags,s.bx,s.ax);s.bx=(uint16_t)(s.bx+s.ax);
        for(n=0;n<2;++n)s.ax=shift_left(s.ax,&s.flags);
        s.flags=sub_flags(s.flags,s.ax,s.bx,16);s.ax=(uint16_t)(s.ax-s.bx);
        s.flags=add_flags(s.flags,s.ax,0x780u);s.ax=(uint16_t)(s.ax+0x780u);
    }
#if MUTATION == 3
    saved_base=s.ax;
#endif
    push(memory,s.ss,&s.sp,s.ax,s.flags,bus);
    setup(&s);
    if(thirteen)s.cx=read16(memory,s.ds,s.si,s.flags,bus);
    s.di=read16(memory,s.ds,(uint16_t)(s.si+2u),s.flags,bus);
    if(thirteen) {
        uint8_t state=read8(memory,physical(s.ds,(uint16_t)(s.si+0x28u)),s.flags,bus);
        s.flags=sub_flags(s.flags,state,2,8);
#if MUTATION != 2
        if(state==2) {
            uint16_t before=s.flags;
            uint8_t direction;
            s.flags=(uint16_t)((add_flags(s.flags,s.di,1)&~CF)|(before&CF));
            s.di=(uint16_t)(s.di+1u);
            direction=read8(memory,physical(s.ds,(uint16_t)(s.si+0x27u)),s.flags,bus);
            s.ax=direction&0x80u?(uint16_t)(0xff00u|direction):direction;
            s.flags=add_flags(s.flags,s.cx,s.ax);s.cx=(uint16_t)(s.cx+s.ax);
        }
#endif
    }
    word=read16(memory,s.ds,(uint16_t)(s.si+6u),s.flags,bus);
    s.flags=add_flags(s.flags,s.di,word);s.di=(uint16_t)(s.di+word);
    s.flags=sub_flags(s.flags,s.di,0x10u,16);s.di=(uint16_t)(s.di-0x10u);
    s.ax=0xd0u;push(memory,s.ss,&s.sp,s.dx,s.flags,bus);
    product=(uint32_t)s.ax*s.di;s.ax=(uint16_t)product;s.dx=(uint16_t)(product>>16);
    s.flags=(uint16_t)((s.flags&~(CF|OF))|(s.dx?(CF|OF):0));
    s.di=s.ax;s.dx=pop(memory,s.ss,&s.sp,s.flags,bus);
    if(!thirteen)s.cx=read16(memory,s.ds,s.si,s.flags,bus);
    word=read16(memory,s.ds,(uint16_t)(s.si+4u),s.flags,bus);
    s.flags=add_flags(s.flags,s.cx,word);s.cx=(uint16_t)(s.cx+word);
    if(thirteen)s.bp=s.cx;
#if MUTATION == 9
    else saved_sum=s.cx;
#endif
    for(n=0;n<3;++n)s.cx=shift_right(s.cx,&s.flags);
    s.flags=add_flags(s.flags,s.di,s.cx);s.di=(uint16_t)(s.di+s.cx);
    s.flags=add_flags(s.flags,s.di,0x4a40u);s.di=(uint16_t)(s.di+0x4a40u);
    s.bx=pop(memory,s.ss,&s.sp,s.flags,bus);
#if MUTATION == 3
    s.bx=saved_base;
#endif
    push(memory,s.ss,&s.sp,s.si,s.flags,bus);
    {
        uint8_t direction=read8(memory,physical(s.ds,(uint16_t)(s.si+0x27u)),s.flags,bus);
        s.flags=sub_flags(s.flags,direction,0xffu,8);
        if(direction==0xffu) {
            uint16_t offset=thirteen?0x270u:0x3c0u;
            s.flags=add_flags(s.flags,s.bx,offset);s.bx=(uint16_t)(s.bx+offset);
        }
    }
    if(!thirteen) {
        s.ax=read16(memory,s.ds,s.si,s.flags,bus);
        word=read16(memory,s.ds,(uint16_t)(s.si+4u),s.flags,bus);
        s.flags=add_flags(s.flags,s.ax,word);s.ax=(uint16_t)(s.ax+word);
#if MUTATION == 9
        s.ax=saved_sum;
#endif
        s.ax&=7u;s.flags=logic_flags(s.flags,s.ax);
        s.ax=shift_left(s.ax,&s.flags);s.si=s.ax;
        for(n=0;n<4;++n)s.si=shift_left(s.si,&s.flags);
        s.flags=sub_flags(s.flags,s.si,s.ax,16);s.si=(uint16_t)(s.si-s.ax);
    } else {
        s.bp&=7u;s.flags=logic_flags(s.flags,s.bp);s.si=s.bp;
        for(n=0;n<3;++n)s.si=shift_left(s.si,&s.flags);
        s.cx=s.si;s.flags=sub_flags(s.flags,s.cx,s.bp,16);s.cx=(uint16_t)(s.cx-s.bp);
        for(n=0;n<2;++n)s.si=shift_left(s.si,&s.flags);
        s.flags=add_flags(s.flags,s.si,s.cx);s.si=(uint16_t)(s.si+s.cx);
    }
    s.flags=add_flags(s.flags,s.si,s.bx);s.si=(uint16_t)(s.si+s.bx);
    push(memory,s.ss,&s.sp,s.ds,s.flags,bus);
    s.ds=read16(memory,s.ds,SEG09A9_GeneratedGraphicsBufferSegment,s.flags,bus);
    s.cx=thirteen?13u:10u;
    draw_rows(&s,call->flags);
#if MUTATION == 8
    if(thirteen)s.bp=call->alignment_index;
#endif
    return (LmnEntityMaskRowsResult){s.ax,s.bx,s.cx,s.dx,s.si,s.di,s.ds,
                                    0xa000u,s.sp,s.bp,s.flags};
}

LmnEntityMaskRowsResult lmn_draw_ten_row_entity_mask_core(uint8_t *m,
    const LmnEntityMaskRowsCall *call,const LmnRasterBus *bus) {
    return draw(m,call,bus,0);
}
LmnEntityMaskRowsResult lmn_draw_thirteen_row_entity_mask_core(uint8_t *m,
    const LmnEntityMaskRowsCall *call,const LmnRasterBus *bus) {
    return draw(m,call,bus,1);
}
static void adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus,unsigned thirteen) {
    LmnEntityMaskRowsCall call={r->ds,r->ss,r->sp,r->si,r->ax,r->bp,r->flags};
#if MUTATION == 6
    uint16_t target=read16(m,r->ss,r->sp,r->flags,bus);
#endif
    LmnEntityMaskRowsResult out=draw(m,&call,bus,thirteen);
    r->ax=out.value;r->bx=out.mask_word;r->cx=out.row_count;r->dx=out.port;
    r->si=out.source_cursor;r->di=out.destination_offset;r->ds=out.data_segment;
    r->es=out.output_segment;r->sp=out.stack_offset;r->bp=out.alignment_index;r->flags=out.flags;
#if MUTATION == 6
    r->ip=target;r->sp=(uint16_t)(r->sp+2u);
#else
    r->ip=pop(m,r->ss,&r->sp,r->flags,bus);
#endif
}
void lmn_draw_ten_row_entity_mask_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    adapter(m,r,bus,0);
}
void lmn_draw_thirteen_row_entity_mask_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    adapter(m,r,bus,1);
}
