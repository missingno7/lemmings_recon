#include "dat_cache.h"
#include "lemmings_sym.h"
#ifndef MUTATION
#define MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t byte(const uint8_t *mem,uint16_t seg,uint16_t off) {return mem[physical(seg,off)];}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void putword(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t p=physical(seg,off);mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
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
static uint16_t logical_flags(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,width));
}
static uint16_t subtract_flags(uint16_t flags,uint16_t a,uint16_t b) {
    uint16_t value=(uint16_t)((uint32_t)a-b);
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,16)|(a<b ? CF:0)|
        ((a^b^value)&AF)|(((a^b)&(a^value)&0x8000u) ? OF:0));
}
static uint16_t add_flags(uint16_t flags,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t value=(uint16_t)sum;
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,16)|(sum>0xffffu ? CF:0)|
        ((a^b^value)&AF)|(((0xffffu^(a^b))&(a^value)&0x8000u) ? OF:0));
}
static uint8_t consume(const uint8_t *mem,uint16_t seg,uint16_t *cursor,uint16_t step) {
    uint8_t value=byte(mem,seg,*cursor);*cursor=(uint16_t)(*cursor+step);return value;
}
static void emit(uint8_t *mem,uint16_t seg,uint16_t *cursor,uint16_t step,uint8_t value) {
    mem[physical(seg,*cursor)]=value;*cursor=(uint16_t)(*cursor+step);
}
static void spaces(uint8_t *mem,uint16_t seg,uint16_t *cursor,uint16_t step,uint16_t count) {
    while(count!=0) {emit(mem,seg,cursor,step,32);--count;}
}

LmnDatNameResult lmn_dat_prepare_name_core(uint8_t *mem,const LmnDatNameCall *call) {
    uint16_t ds=call->segment,es=call->extra_segment,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t si=call->filename_offset,di=(uint16_t)(SEG09A9_DatCacheFcb+1u),cx=8;
    uint16_t flags=call->flags,step=(flags&DF) ? 0xffffu:1u;uint8_t value;
    unsigned dot=0;
    push(mem,ss,&sp,call->filename_offset);push(mem,ss,&sp,es);
    push(mem,ss,&sp,call->saved_value);push(mem,ss,&sp,call->saved_count);
    push(mem,ss,&sp,ds);es=pop(mem,ss,&sp);
    do {
        value=consume(mem,ds,&si,step);
        if(value=='.') {dot=1;break;}
        emit(mem,es,&di,step,value);--cx;
    } while(cx!=0);
    if(dot) {
        uint16_t count=(uint16_t)(7u-cx);
#if MUTATION == 1
        count=(uint16_t)(count+1u);
#endif
        spaces(mem,es,&di,step,count);
    } else {
        do {value=consume(mem,ds,&si,step);} while(value!='.');
    }
    cx=3;di=(uint16_t)(SEG09A9_DatCacheFcb+9u);
    do {
        value=consume(mem,ds,&si,step);flags=logical_flags(flags,value,8);
        if(value==0) {
            flags=subtract_flags(flags,2,cx);
            spaces(mem,es,&di,step,(uint16_t)(2u-cx));break;
        }
        emit(mem,es,&di,step,value);--cx;
    } while(cx!=0);
    {
        uint16_t restored_count=pop(mem,ss,&sp),restored_value=pop(mem,ss,&sp);
        es=pop(mem,ss,&sp);
        {uint16_t restored_offset=pop(mem,ss,&sp);
         LmnDatNameResult out={restored_offset,restored_value,restored_count,es,si,di,sp,flags};return out;}
    }
}

LmnDatLookupResult lmn_dat_select_cache_core(uint8_t *mem,uint16_t data_segment,
    const LmnDatLookupCall *call) {
    uint16_t ds=call->segment,es=call->extra_segment,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t si=call->source_cursor,di=call->comparison_cursor,ax=call->value;
    uint16_t cx,flags=call->flags,step=(flags&DF) ? 0xffffu:1u;unsigned found=0;
    push(mem,ss,&sp,ds);
    cx=(uint16_t)((call->count&0xff00u)|byte(mem,ds,SEG09A9_DatCacheRecordCount));
    flags=logical_flags(flags,(uint16_t)(cx&255u),8);
    if((cx&255u)!=0) {
        cx&=255u;push(mem,ss,&sp,ds);es=pop(mem,ss,&sp);
        ds=word(mem,ds,SEG09A9_DatCacheBaseSegment);si=0;di=(uint16_t)(SEG09A9_DatCacheFcb+1u);
        do {
            uint16_t remaining=11;unsigned equal;
            push(mem,ss,&sp,cx);push(mem,ss,&sp,ds);push(mem,ss,&sp,si);push(mem,ss,&sp,di);
            do {
                uint8_t source=consume(mem,ds,&si,step),target=consume(mem,es,&di,step);
                equal=source==target;--remaining;
            } while(remaining!=0 && equal);
            di=pop(mem,ss,&sp);si=pop(mem,ss,&sp);flags=logical_flags(flags,remaining,16);
            if(remaining==0
#if MUTATION == 2
                && equal
#endif
            ) {
                found=1;ax=ds;ds=pop(mem,ss,&sp);cx=pop(mem,ss,&sp);
                cx=data_segment;ds=cx;
                putword(mem,ds,SEG09A9_DatCacheRecordOffset,si);putword(mem,ds,SEG09A9_DatCacheRecordSegment,ax);
                flags=add_flags(flags,si,13);si=(uint16_t)(si+13u);
                putword(mem,ds,SEG09A9_DatCacheReadOffset,si);putword(mem,ds,SEG09A9_DatCacheReadSegment,ax);
                mem[physical(ds,SEG09A9_DatCacheSelected)]=255;break;
            }
            ds=pop(mem,ss,&sp);
            {
                uint16_t length=word(mem,ds,(uint16_t)(si+11u));
#if MUTATION == 3
                uint32_t sum=(uint32_t)si+length+13u;ax=(uint16_t)(sum>>4);si=(uint16_t)sum;
#else
                si=(uint16_t)(si+length);si=(uint16_t)(si+13u);ax=(uint16_t)(si>>4);
#endif
            }
            ds=(uint16_t)(ds+ax);si&=15u;flags=logical_flags(flags,si,16);
            cx=pop(mem,ss,&sp);cx=(uint16_t)(cx-1u);
        } while(cx!=0);
    }
    ds=pop(mem,ss,&sp);
    if(found)flags=(uint16_t)(flags&(0xffffu^CF));
    else {mem[physical(ds,SEG09A9_DatCacheSelected)]=0;flags|=CF;}
    {LmnDatLookupResult out={ds,si,di,ax,cx,es,sp,flags};return out;}
}
LmnDatDisableResult lmn_dat_disable_cache_core(uint8_t *mem,uint16_t segment,uint16_t value,uint16_t flags) {
    mem[physical(segment,SEG09A9_DatCacheEnabled)]=0;
    {LmnDatDisableResult out={(uint16_t)(value&0xff00u),logical_flags(flags,0,8)};return out;}
}
static void near_return(uint8_t *mem,LmnRegs *r) {r->ip=pop(mem,r->ss,&r->sp);}
void lmn_dat_prepare_name_adapter(uint8_t *mem,LmnRegs *r) {
    LmnDatNameCall call={r->ds,r->dx,r->ax,r->cx,r->es,r->ss,r->sp,r->flags};
    LmnDatNameResult out=lmn_dat_prepare_name_core(mem,&call);
    r->dx=out.filename_offset;r->ax=out.value;r->cx=out.count;r->es=out.extra_segment;
    r->si=out.source_cursor;r->di=out.output_cursor;r->sp=out.stack_offset;r->flags=out.flags;near_return(mem,r);
}
void lmn_dat_select_cache_adapter(uint8_t *mem,LmnRegs *r) {
    LmnDatLookupCall call={r->ds,r->si,r->di,r->ax,r->cx,r->es,r->ss,r->sp,r->flags};
    uint16_t data_segment=word(mem,r->cs,(uint16_t)(CS_SelectCachedDatFile+0x50u));
    LmnDatLookupResult out=lmn_dat_select_cache_core(mem,data_segment,&call);
    r->ds=out.segment;r->si=out.source_cursor;r->di=out.comparison_cursor;r->ax=out.value;
    r->cx=out.count;r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;near_return(mem,r);
}
void lmn_dat_disable_cache_adapter(uint8_t *mem,LmnRegs *r) {
    LmnDatDisableResult out=lmn_dat_disable_cache_core(mem,r->ds,r->ax,r->flags);
    r->ax=out.value;r->flags=out.flags;near_return(mem,r);
}
