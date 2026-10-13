#include "dat_io.h"
#include "lemmings_sym.h"
#ifndef MUTATION
#define MUTATION 0
#endif
enum { CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5 };

static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t byte(const uint8_t *mem,uint16_t seg,uint16_t off) {
    return mem[physical(seg,off)];
}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);
    return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void putword(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t p=physical(seg,off);mem[p]=(uint8_t)value;
    mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static void push(uint8_t *mem,uint16_t ss,uint16_t *sp,uint16_t value) {
    *sp=(uint16_t)(*sp-2u);putword(mem,ss,*sp,value);
}
static uint16_t pop(const uint8_t *mem,uint16_t ss,uint16_t *sp) {
    uint16_t value=word(mem,ss,*sp);*sp=(uint16_t)(*sp+2u);return value;
}
static uint16_t szp(uint16_t value,unsigned width) {
    unsigned i,parity=0;uint16_t result=0;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)result|=PF;
    if(!value)result|=ZF;
    if(value&(width==8 ? 0x80u:0x8000u))result|=SF;
    return result;
}
static uint16_t subtract_flags(uint16_t flags,uint16_t a,uint16_t b,unsigned width) {
    uint16_t mask=width==8 ? 0xffu:0xffffu,sign=width==8 ? 0x80u:0x8000u;
    uint16_t value=(uint16_t)(((uint32_t)a-(uint32_t)b)&mask);
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,width)|(a<b ? CF:0)|
        ((a^b^value)&AF)|(((a^b)&(a^value)&sign) ? OF:0));
}
static uint16_t add_flags(uint16_t flags,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t value=(uint16_t)sum;
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,16)|(sum>0xffffu ? CF:0)|
        ((a^b^value)&AF)|(((0xffffu^(a^b))&(a^value)&0x8000u) ? OF:0));
}
static void copy_live(uint8_t *mem,uint16_t ds,uint16_t *si,
    uint16_t es,uint16_t *di,uint16_t count,uint16_t flags) {
    uint16_t step=(flags&DF) ? 0xffffu:1u;
    while(count!=0) {
        mem[physical(es,*di)]=byte(mem,ds,*si);
        *si=(uint16_t)(*si+step);*di=(uint16_t)(*di+step);--count;
    }
}

LmnDatReadResult lmn_dat_read_core(uint8_t *mem,uint16_t data_segment,
    const LmnDatReadCall *call,const LmnDatIo *io) {
    uint16_t ss=call->stack_segment,sp=call->stack_offset;
    uint16_t ax=data_segment,bx=call->handle,cx=call->count,dx=call->destination_offset;
    uint16_t si=call->saved_source_cursor,di=call->saved_destination_cursor;
    uint16_t ds=call->destination_segment,es=call->extra_segment;
    uint16_t flags=(uint16_t)(call->flags&(0xffffu^DF));
    unsigned cached=0;LmnDatDosResult service;
    push(mem,ss,&sp,di);push(mem,ss,&sp,si);push(mem,ss,&sp,ds);
    push(mem,ss,&sp,bx);push(mem,ss,&sp,cx);push(mem,ss,&sp,dx);ds=data_segment;
    flags=subtract_flags(flags,byte(mem,ds,SEG09A9_DatCacheEnabled),255,8);
    if(byte(mem,ds,SEG09A9_DatCacheEnabled)==255) {
        flags=subtract_flags(flags,byte(mem,ds,SEG09A9_DatCacheSelected),255,8);
        if(byte(mem,ds,SEG09A9_DatCacheSelected)==255)cached=1;
        else {
            uint16_t low,high,paragraphs,budget;
            dx=SEG09A9_DatCacheFcb;
            putword(mem,ds,(uint16_t)(dx+14u),1);
            io->query_size(io->context,mem,ds,dx,flags,&service);flags=service.flags;
            low=word(mem,ds,(uint16_t)(SEG09A9_DatCacheFcb+33u));
            high=word(mem,ds,(uint16_t)(SEG09A9_DatCacheFcb+35u));
            push(mem,ss,&sp,low);
            paragraphs=(uint16_t)(((uint32_t)high<<12)|(low>>4));
            ax=(uint16_t)(pop(mem,ss,&sp)&15u);
            if(ax!=0)paragraphs=(uint16_t)(paragraphs+1u);
            budget=word(mem,ds,SEG09A9_DatCacheRemainingParagraphs);
            flags=subtract_flags(flags,paragraphs,budget,16);
            if(paragraphs<=budget) {
                uint16_t total;
                cached=1;
                mem[physical(ds,SEG09A9_DatCacheRecordCount)]=(uint8_t)
                    (byte(mem,ds,SEG09A9_DatCacheRecordCount)+1u);
                putword(mem,ds,SEG09A9_DatCacheRemainingParagraphs,(uint16_t)(budget-paragraphs));
                push(mem,ss,&sp,ds);cx=0xffffu;
                dx=word(mem,ds,SEG09A9_DatCacheFreeOffset);ax=word(mem,ds,SEG09A9_DatCacheFreeSegment);
                putword(mem,ds,SEG09A9_DatCacheRecordOffset,dx);
                putword(mem,ds,SEG09A9_DatCacheRecordSegment,ax);
                mem[physical(ds,SEG09A9_DatCacheSelected)]=255;
                flags=add_flags(flags,dx,13);dx=(uint16_t)(dx+13u);
                putword(mem,ds,SEG09A9_DatCacheReadOffset,dx);
                putword(mem,ds,SEG09A9_DatCacheReadSegment,ax);
                push(mem,ss,&sp,ax);push(mem,ss,&sp,dx);ds=ax;
                io->read(io->context,mem,bx,ds,dx,cx,flags,&service);
                flags=service.flags;cx=service.value;
                /* DOS errors are deliberately used as byte counts here. */
#if MUTATION == 2
                if(flags&CF)cx=0;
#endif
                dx=pop(mem,ss,&sp);ax=pop(mem,ss,&sp);ds=pop(mem,ss,&sp);
                total=(uint16_t)(dx+cx);push(mem,ss,&sp,total);
                ax=(uint16_t)(ax+(total>>4));dx=(uint16_t)(pop(mem,ss,&sp)&15u);
                putword(mem,ds,SEG09A9_DatCacheFreeOffset,dx);
                putword(mem,ds,SEG09A9_DatCacheFreeSegment,ax);
                di=word(mem,ds,SEG09A9_DatCacheRecordOffset);es=word(mem,ds,SEG09A9_DatCacheRecordSegment);
                dx=word(mem,ds,(uint16_t)(SEG09A9_DatCacheFcb+35u));
                putword(mem,es,(uint16_t)(di+11u),cx);
                si=(uint16_t)(SEG09A9_DatCacheFcb+1u);flags=add_flags(flags,di,0);
                copy_live(mem,ds,&si,es,&di,11,flags);cx=0;
            }
        }
    }
    if(cached) {
        di=pop(mem,ss,&sp);cx=pop(mem,ss,&sp);bx=pop(mem,ss,&sp);
#if MUTATION == 1
        (void)pop(mem,ss,&sp);
#else
        es=pop(mem,ss,&sp);
#endif
        push(mem,ss,&sp,es);push(mem,ss,&sp,di);push(mem,ss,&sp,ds);
        si=word(mem,ds,SEG09A9_DatCacheReadOffset);ds=word(mem,ds,SEG09A9_DatCacheReadSegment);
        copy_live(mem,ds,&si,es,&di,cx,flags);cx=0;ax=ds;ds=pop(mem,ss,&sp);
        putword(mem,ds,SEG09A9_DatCacheReadSegment,ax);putword(mem,ds,SEG09A9_DatCacheReadOffset,si);
        dx=pop(mem,ss,&sp);ds=pop(mem,ss,&sp);si=pop(mem,ss,&sp);di=pop(mem,ss,&sp);
    } else {
        dx=pop(mem,ss,&sp);cx=pop(mem,ss,&sp);bx=pop(mem,ss,&sp);ds=pop(mem,ss,&sp);
        io->read(io->context,mem,bx,ds,dx,cx,flags,&service);ax=service.value;flags=service.flags;
#if MUTATION == 3
        sp=(uint16_t)(sp+4u);
#else
        si=pop(mem,ss,&sp);di=pop(mem,ss,&sp);
#endif
    }
    {
        LmnDatReadResult out={ax,bx,cx,ds,dx,si,di,es,sp,flags};return out;
    }
}

void lmn_dat_read_adapter(uint8_t *mem,LmnRegs *r,const LmnDatIo *io) {
    LmnDatReadCall call={r->bx,r->cx,r->ds,r->dx,r->si,r->di,r->es,r->ss,r->sp,r->flags};
    /* The original relocated MOV immediate remains live at this oracle boundary. */
    uint16_t data_segment=word(mem,r->cs,(uint16_t)(CS_ReadDatBytes+8u));
    LmnDatReadResult out=lmn_dat_read_core(mem,data_segment,&call,io);
    r->ax=out.value;r->bx=out.handle;r->cx=out.count;r->ds=out.destination_segment;
    r->dx=out.destination_offset;r->si=out.source_cursor;r->di=out.destination_cursor;
    r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=pop(mem,r->ss,&r->sp);
}
