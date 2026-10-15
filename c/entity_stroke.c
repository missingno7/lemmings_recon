#include "entity_stroke.h"
#include "lemmings_sym.h"

#ifndef STROKE_MUTATION
#define STROKE_MUTATION 0
#endif

enum { CF=1,PF=4,AF=16,ZF=64,SF=128,IF=0x200,DF=0x400,OF=0x800,ARITH=0x8d5 };
static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint8_t read8(uint8_t *m,uint32_t p,uint16_t f,const LmnRasterBus *b) {
    return b&&b->read_byte ? b->read_byte(b->context,m,p,f):m[p];
}
static void write8(uint8_t *m,uint32_t p,uint8_t v,uint16_t f,const LmnRasterBus *b) {
    if(b&&b->write_byte)b->write_byte(b->context,m,p,v,f);else m[p]=v;
}
static uint16_t read16(uint8_t *m,uint16_t s,uint16_t o,uint16_t f,const LmnRasterBus *b) {
    uint32_t p=physical(s,o);
    uint8_t lo=read8(m,p,f,b),hi;
    hi=read8(m,(p+1u)&0xfffffu,f,b);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write16(uint8_t *m,uint16_t s,uint16_t o,uint16_t v,uint16_t f,const LmnRasterBus *b) {
    uint32_t p=physical(s,o);
    write8(m,p,(uint8_t)v,f,b);write8(m,(p+1u)&0xfffffu,(uint8_t)(v>>8),f,b);
}
static void output(uint8_t *m,uint16_t ss,uint16_t mirror,uint16_t port,
                   uint16_t value,uint16_t f,const LmnRasterBus *b) {
    write16(m,ss,mirror,value,f,b);
    if(b&&b->out_word)b->out_word(b->context,port,value,f);
}
static void push(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t v,uint16_t f,const LmnRasterBus *b) {
    *sp=(uint16_t)(*sp-2u);write16(m,ss,*sp,v,f,b);
}
static uint16_t pop(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t f,const LmnRasterBus *b) {
    uint16_t v=read16(m,ss,*sp,f,b);*sp=(uint16_t)(*sp+2u);return v;
}
static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0,n;uint16_t out=0;
    for(n=0;n<8;++n)parity^=(value>>n)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(1u<<(bits-1u)))out|=SF;
    return out;
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

LmnEntityStrokeResult lmn_draw_entity_stroke_core(uint8_t *m,
    const LmnEntityStrokeCall *call,const LmnRasterBus *bus) {
    uint16_t ds=call->data_segment,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t si=call->record_cursor,f=(uint16_t)(call->flags&~IF);
    uint16_t value,x,y,horizontal_offset,di,bx,cx,dx,es,target;
    uint8_t direction,spill=0;
    unsigned n;
    LmnEntityStrokeResult out;
    LmnEntityPixelCall child;
    LmnEntityPixelResult pixel;
#if STROKE_MUTATION == 2
    uint16_t saved_y,saved_x;
#endif
    output(m,ss,SEG143E_VgaMapMaskMirror,0x3c4u,0x0802u,f,bus);
    output(m,ss,SEG143E_VgaSetResetMirror,0x3ceu,0x0800u,f,bus);
    output(m,ss,SEG143E_VgaEnableSetResetMirror,0x3ceu,0x0801u,f,bus);
    output(m,ss,SEG143E_VgaDataRotateMirror,0x3ceu,0x0003u,f,bus);
    y=read16(m,ds,(uint16_t)(si+2u),f,bus);
#if STROKE_MUTATION == 2
    saved_y=y;
#endif
    push(m,ss,&sp,y,f,bus);
    x=read16(m,ds,si,f,bus);
#if STROKE_MUTATION == 2
    saved_x=x;
#endif
    push(m,ss,&sp,x,f,bus);
    x=read16(m,ds,si,f,bus);
    horizontal_offset=read16(m,ds,(uint16_t)(si+4u),f,bus);
    value=(uint16_t)(x+horizontal_offset);f=add_flags(f,x,horizontal_offset);
    direction=read8(m,physical(ds,(uint16_t)(si+0x27u)),f,bus);
    f=sub_flags(f,direction,0,8);
    if(direction&0x80u) {
#if STROKE_MUTATION == 1
        f=sub_flags(f,value,0,16);
#else
        f=sub_flags(f,value,4,16);value=(uint16_t)(value-4u);
#endif
    }
    write16(m,ds,si,value,f,bus);push(m,ss,&sp,value,f,bus);
    y=read16(m,ds,(uint16_t)(si+2u),f,bus);
    {
        uint16_t before=f;
        uint16_t after=sub_flags(f,y,1,16);
        /* The memory instruction's bus observes its entry flags. Publish
           DEC's defined result only after the RMW write, before CALL. */
        write16(m,ds,(uint16_t)(si+2u),(uint16_t)(y-1u),before,bus);
        f=(uint16_t)((after&~CF)|(before&CF));
    }
    push(m,ss,&sp,0x5f57u,f,bus);
    child.data_segment=ds;child.stack_segment=ss;child.stack_offset=sp;
    child.record_cursor=si;child.saved_value=0x3ceu;child.flags=f;
    pixel=lmn_prepare_entity_pixel_bus_core(m,&child,bus);
    sp=pixel.stack_offset;f=pixel.flags;
    value=pixel.value;bx=pixel.table_cursor;cx=pixel.column_byte;
    di=pixel.destination_offset;dx=pixel.restored_value;es=0xa000u;
    target=pop(m,ss,&sp,f,bus);
#if STROKE_MUTATION != 4
    if(target!=0x5f57u) {
        out=(LmnEntityStrokeResult){value,bx,cx,di,es,dx,sp,f,target,0};
        return out;
    }
#else
    (void)target;
    (void)dx;
#endif
    cx=pop(m,ss,&sp,f,bus);
    x=pop(m,ss,&sp,f,bus);
#if STROKE_MUTATION == 2
    x=saved_x;
#endif
    write16(m,ds,si,x,f,bus);
    y=pop(m,ss,&sp,f,bus);
#if STROKE_MUTATION == 2
    y=saved_y;
#endif
    write16(m,ds,(uint16_t)(si+2u),y,f,bus);
    bx=0xfcu;cx&=7u;
    f=(uint16_t)((f&~(CF|PF|ZF|SF|OF))|szp(cx,16));
    while(cx) {
        uint16_t old=bx;uint8_t previous_spill=spill;
        bx>>=1;
        f=(uint16_t)((f&~(CF|PF|ZF|SF|OF))|szp(bx,16)|
                     ((old&1u)?CF:0)|((old&0x8000u)?OF:0));
        spill=(uint8_t)((spill>>1)|((f&CF)?0x80u:0));
        f=(uint16_t)((f&~(CF|OF))|((previous_spill&1u)?CF:0)|
                     ((((spill>>7)^(spill>>6))&1u)?OF:0));
        --cx;
    }
    cx=spill;
    for(n=0;n<3;++n) {
        uint8_t mask=n==0?(uint8_t)(bx>>8):n==1?(uint8_t)bx:(uint8_t)cx;
        uint16_t step=(f&DF)?0xffffu:1u;
        (void)read8(m,physical(es,di),f,bus);
        output(m,ss,SEG143E_VgaBitMaskMirror,0x3ceu,
               (uint16_t)(((uint16_t)mask<<8)|8u),f,bus);
        write8(m,physical(es,di),mask,f,bus);
#if STROKE_MUTATION == 3
        step=1u;
#endif
        di=(uint16_t)(di+step);
    }
#if STROKE_MUTATION != 5
    output(m,ss,SEG143E_VgaMapMaskMirror,0x3c4u,0x0f02u,f,bus);
#endif
    f|=IF;
    out=(LmnEntityStrokeResult){0x0f02u,bx,cx,di,es,0x3c4u,sp,f,0x5fabu,1};
    return out;
}

void lmn_draw_entity_stroke_adapter(uint8_t *memory,LmnRegs *r,const LmnRasterBus *bus) {
    LmnEntityStrokeCall call={r->ds,r->ss,r->sp,r->si,r->flags};
    LmnEntityStrokeResult out=lmn_draw_entity_stroke_core(memory,&call,bus);
    r->ax=out.value;r->bx=out.mask_word;r->cx=out.spill_word;r->di=out.destination_offset;
    r->es=out.output_segment;r->dx=out.port;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=out.continuation;
    if(out.ready_to_return)r->ip=pop(memory,r->ss,&r->sp,r->flags,bus);
}
