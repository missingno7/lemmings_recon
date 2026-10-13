#include "special_blit.h"
#include "lemmings_sym.h"
#ifndef MUTATION
#define MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,IF=512,DF=1024,OF=2048,ARITH=0x8d5};
typedef struct Raster {
    uint8_t *mem;const LmnRasterBus *bus;
    uint16_t value,count,si,di,bx,dx,ds,es,ss,sp,flags;
} Raster;
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint8_t read_byte(Raster *s,uint32_t p) {return s->bus->read_byte(s->bus->context,s->mem,p,s->flags);}
static void write_byte(Raster *s,uint32_t p,uint8_t value) {s->bus->write_byte(s->bus->context,s->mem,p,value,s->flags);}
static uint16_t word(Raster *s,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);uint8_t low=read_byte(s,p);
    return (uint16_t)(low|((uint16_t)read_byte(s,(p+1u)&0xfffffu)<<8));
}
static void putword(Raster *s,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t p=physical(seg,off);write_byte(s,p,(uint8_t)value);write_byte(s,(p+1u)&0xfffffu,(uint8_t)(value>>8));
}
static void push(Raster *s,uint16_t value) {s->sp=(uint16_t)(s->sp-2u);putword(s,s->ss,s->sp,value);}
static uint16_t pop(Raster *s) {uint16_t out=word(s,s->ss,s->sp);s->sp=(uint16_t)(s->sp+2u);return out;}
static uint16_t szp(uint16_t value,unsigned width) {
    unsigned i,parity=0;uint16_t out=0;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(width==8 ? 0x80u:0x8000u))out|=SF;
    return out;
}
static uint16_t logical(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,width));
}
static uint16_t addition(uint16_t flags,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t value=(uint16_t)sum;
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,16)|(sum>0xffffu ? CF:0)|
        ((a^b^value)&AF)|(((0xffffu^(a^b))&(a^value)&0x8000u) ? OF:0));
}
static void output(Raster *s,uint16_t mirror,uint16_t value) {
    s->value=value;putword(s,s->ss,mirror,value);s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}
static void rows(Raster *s) {
    uint16_t step=(s->flags&DF) ? 0xffffu:1u;
    do {
        uint16_t before;uint32_t sum;
        push(s,s->count);s->count&=255u;s->flags=(uint16_t)(logical(s->flags,0,8)&(0xffffu^IF));
        do {
            uint8_t old=read_byte(s,physical(s->es,s->di));
            uint8_t source=read_byte(s,physical(s->ds,s->si));
            s->value=(uint16_t)((s->value&0xff00u)|old);write_byte(s,physical(s->es,s->di),source);
            s->si=(uint16_t)(s->si+step);s->di=(uint16_t)(s->di+step);s->count=(uint16_t)(s->count-1u);
        } while(s->count!=0);
        s->flags|=IF;before=s->di;
#if MUTATION == 2
        sum=(uint32_t)before+0x57u;
#else
        sum=(uint32_t)before+0x58u;
#endif
        s->flags=addition(s->flags,before,(uint16_t)(sum-before));s->di=(uint16_t)sum;s->count=pop(s);
        {
            uint8_t ch=(uint8_t)(s->count>>8),next=(uint8_t)(ch-1u);
            s->count=(uint16_t)((s->count&255u)|((uint16_t)next<<8));
            s->flags=(uint16_t)((s->flags&(0xffffu^ARITH))|szp(next,8)|(sum>0xffffu ? CF:0)|
                ((ch&15u)==0 ? AF:0)|(ch==0x80u ? OF:0));
        }
    } while((s->count>>8)!=0);
}
LmnSpecialBlitResult lmn_blit_special_strip_core(uint8_t *mem,uint16_t data_segment,
    uint16_t stack_segment,uint16_t stack_offset,uint16_t vertical_offset,
    unsigned publish_graphics_segment,uint16_t flags,const LmnRasterBus *bus) {
    Raster s={mem,bus,0,0,0x8000,0xb840,vertical_offset,0,data_segment,0,stack_segment,stack_offset,flags};
    uint16_t step=(flags&DF) ? 0xfffeu:2u;
    if(publish_graphics_segment) {
        s.value=word(&s,s.ds,SEG09A9_LevelGraphicsSegment);putword(&s,s.ds,SEG09A9_GraphicsResourceSegment,s.value);
        s.flags=logical(s.flags,0,16);
    }
    s.es=word(&s,s.ds,SEG09A9_LevelGraphicsSegment);s.count=0x960;
    do {
        s.value=word(&s,s.es,s.si);s.value|=word(&s,s.es,(uint16_t)(s.si+0x12c0u));s.flags=logical(s.flags,s.value,16);
#if MUTATION != 1
        s.value|=word(&s,s.es,(uint16_t)(s.si+0x2580u));
        s.flags=logical(s.flags,s.value,16);
#endif
        putword(&s,s.es,s.di,s.value);s.di=(uint16_t)(s.di+step);s.flags=addition(s.flags,s.si,2);s.si=(uint16_t)(s.si+2u);--s.count;
    } while(s.count!=0);
    s.value=(uint16_t)((uint32_t)0xd0u*s.bx);s.flags=addition(s.flags,s.value,0x4a40);
    s.di=(uint16_t)(s.value+0x4a40u);s.flags=addition(s.flags,s.di,0x28);s.di=(uint16_t)(s.di+0x28u);s.si=0x8000;
    push(&s,s.ds);s.ds=word(&s,s.ds,SEG09A9_LevelGraphicsSegment);s.es=0xa000;
    s.dx=0x3c4;output(&s,SEG143E_VgaMapMaskMirror,0x0f02);s.dx=0x3ce;s.flags=logical(s.flags,0,16);
    output(&s,SEG143E_VgaSetResetMirror,0x0000);output(&s,SEG143E_VgaEnableSetResetMirror,0x0e01);
    output(&s,SEG143E_VgaGraphicsModeMirror,0x0005);output(&s,SEG143E_VgaDataRotateMirror,0x0003);output(&s,SEG143E_VgaBitMaskMirror,0xff08);
    s.count=0x2878;push(&s,s.di);push(&s,s.count);rows(&s);s.count=pop(&s);s.di=pop(&s);
    output(&s,SEG143E_VgaEnableSetResetMirror,0x0001);s.dx=0x3c4;output(&s,SEG143E_VgaMapMaskMirror,0x0202);
    push(&s,s.di);push(&s,s.count);rows(&s);s.count=pop(&s);s.di=pop(&s);
    output(&s,SEG143E_VgaMapMaskMirror,0x0402);push(&s,s.di);push(&s,s.count);rows(&s);s.count=pop(&s);s.di=pop(&s);
#if MUTATION == 3
    output(&s,SEG143E_VgaMapMaskMirror,0x0402);
#else
    output(&s,SEG143E_VgaMapMaskMirror,0x0802);
#endif
    rows(&s);s.ds=pop(&s);
    {LmnSpecialBlitResult out={s.value,s.count,s.si,s.di,s.bx,s.dx,s.ds,s.es,s.sp,s.flags};return out;}
}
void lmn_blit_special_strip_adapter(uint8_t *mem,LmnRegs *r,uint16_t strip,const LmnRasterBus *bus) {
    LmnSpecialBlitResult out=lmn_blit_special_strip_core(mem,r->ds,r->ss,r->sp,(uint16_t)(strip*40u),strip==0,r->flags,bus);
    uint32_t p;
    r->ax=out.value;r->cx=out.count;r->si=out.source_cursor;r->di=out.output_cursor;r->bx=out.vertical_offset;r->dx=out.port;
    r->ds=out.source_segment;r->es=out.output_segment;r->sp=out.stack_offset;r->flags=out.flags;
    p=physical(r->ss,r->sp);r->ip=(uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));r->sp=(uint16_t)(r->sp+2u);
}
