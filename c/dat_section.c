#include "dat_section.h"
#include "dat.h"
#include "lemmings_sym.h"
#ifndef SECTION_MUTATION
#define SECTION_MUTATION 0
#endif
enum { CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5 };
typedef struct DecodeState {
    uint16_t value,handle,bits,stream,source,output,start,ds,es,ss,sp,flags;
} DecodeState;
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
    uint32_t p=physical(seg,off);mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static void push(uint8_t *mem,DecodeState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);putword(mem,s->ss,s->sp,value);
}
static uint16_t pop(const uint8_t *mem,DecodeState *s) {
    uint16_t value=word(mem,s->ss,s->sp);s->sp=(uint16_t)(s->sp+2u);return value;
}
static uint16_t szp(uint16_t value,unsigned width) {
    unsigned i,parity=0;uint16_t out=0;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(width==8 ? 0x80u:0x8000u))out|=SF;
    return out;
}
static uint16_t add_flags(uint16_t flags,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t value=(uint16_t)sum;
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,16)|(sum>0xffffu ? CF:0)|
        ((a^b^value)&AF)|(((0xffffu^(a^b))&(a^value)&0x8000u) ? OF:0));
}
static void read_bits(uint8_t *mem,DecodeState *s,uint8_t count,uint16_t continuation) {
    LmnReverseBitsResult out;
    s->bits=(uint16_t)((s->bits&0xff00u)|count);push(mem,s,continuation);
    out=lmn_dat_read_bits_core(mem,s->ds,s->source,(uint8_t)(s->bits>>8),
        (uint8_t)s->stream,(uint8_t)(s->stream>>8),count,s->flags);
    s->value=out.value;s->source=out.cursor;s->bits=(uint16_t)((uint16_t)out.remaining<<8);
    s->stream=(uint16_t)(((uint16_t)out.checksum<<8)|out.shifted_byte);s->flags=out.flags;
    (void)pop(mem,s);
}
static void read_match(uint8_t *mem,DecodeState *s,uint8_t width,uint16_t continuation) {
    LmnDatCopyResult out;uint16_t count=(uint16_t)(s->handle+1u);
    push(mem,s,continuation);read_bits(mem,s,width,CS_CopyReverseMatch);
    push(mem,s,s->source);push(mem,s,s->ds);push(mem,s,s->bits);push(mem,s,s->es);
    (void)pop(mem,s); /* POP DS selects ES during the live match copy. */
    out=lmn_dat_copy_match_core(mem,s->es,s->output,s->value,s->handle,s->flags);
    s->output=out.cursor;s->handle=(uint16_t)((count&0xff00u)|out.last_byte);s->flags=out.flags;
    s->bits=pop(mem,s);s->ds=pop(mem,s);s->source=pop(mem,s);(void)pop(mem,s);
}
static void literals(uint8_t *mem,DecodeState *s,uint16_t bits_return,uint16_t write_return) {
    do {
        LmnDatCopyResult out;
        push(mem,s,s->value);read_bits(mem,s,8,bits_return);push(mem,s,write_return);
        out=lmn_dat_write_literal_core(mem,s->es,s->output,(uint8_t)s->value,s->flags);
        s->output=out.cursor;s->flags=out.flags;(void)pop(mem,s);
        s->value=(uint16_t)(pop(mem,s)-1u);
    } while(s->value!=0);
}
static void read_data(uint8_t *mem,DecodeState *s,uint16_t data_segment,
    uint16_t continuation,const LmnDatIo *io) {
    LmnDatReadCall call;LmnDatReadResult out;
    push(mem,s,continuation);
    call=(LmnDatReadCall){s->handle,s->bits,s->ds,s->stream,s->source,s->output,
        s->es,s->ss,s->sp,s->flags};
    out=lmn_dat_read_core(mem,data_segment,&call,io);
    s->value=out.value;s->handle=out.handle;s->bits=out.count;s->ds=out.destination_segment;
    s->stream=out.destination_offset;s->source=out.source_cursor;s->output=out.destination_cursor;
    s->es=out.extra_segment;s->sp=out.stack_offset;s->flags=out.flags;(void)pop(mem,s);
}

LmnDatSectionResult lmn_dat_section_core(uint8_t *mem,uint16_t data_segment,
    uint16_t failure_segment,const LmnDatSectionCall *call,const LmnDatIo *io) {
    DecodeState s={0,call->handle,10,call->source_cursor,call->source_cursor,
        call->output_cursor,call->output_cursor,call->source_segment,call->output_segment,
        call->stack_segment,call->stack_offset,(uint16_t)(call->flags|DF)};
    uint16_t failed=0;
    push(mem,&s,s.handle);push(mem,&s,s.handle);
    read_data(mem,&s,data_segment,CS_DatAfterHeaderRead,io);
    if(s.flags&CF)failed=1;
    else {
        uint16_t length,packed;
        s.bits=(uint16_t)(((uint16_t)(uint8_t)(byte(mem,s.ds,s.source)+1u)<<8)|(s.bits&255u));
        s.stream=(uint16_t)(((uint16_t)byte(mem,s.ds,(uint16_t)(s.source+1u))<<8)|(s.stream&255u));
        /* The high length word is loaded into AX, then discarded by POP AX. */
        length=(uint16_t)(((uint16_t)byte(mem,s.ds,(uint16_t)(s.source+4u))<<8)|
            byte(mem,s.ds,(uint16_t)(s.source+5u)));
        s.handle=length;s.output=(uint16_t)(s.output+length);s.value=pop(mem,&s);
        push(mem,&s,s.bits);push(mem,&s,s.stream);
        packed=(uint16_t)(((uint16_t)byte(mem,s.ds,(uint16_t)(s.source+8u))<<8)|
            byte(mem,s.ds,(uint16_t)(s.source+9u)));
        s.bits=(uint16_t)(packed-10u);s.stream=s.source;
        s.flags=add_flags(s.flags,s.source,s.bits);s.source=(uint16_t)(s.source+s.bits);
        s.handle=s.value;read_data(mem,&s,data_segment,CS_DatAfterPayloadRead,io);
        if(s.flags&CF)failed=1;
        else {
            s.stream=pop(mem,&s);s.bits=pop(mem,&s);s.source=(uint16_t)(s.source-1u);
            s.stream=(uint16_t)(((s.stream>>8)^byte(mem,s.ds,s.source))<<8)|byte(mem,s.ds,s.source);
            do {
                read_bits(mem,&s,1,CS_DatAfterTokenBit);
                if(s.value==1) {
                    read_bits(mem,&s,2,CS_DatAfterKindBits);
                    if(s.value<2) {
                        uint8_t width=(uint8_t)(s.value+9u);s.handle=(uint16_t)(s.value+2u);
                        read_match(mem,&s,width,CS_DatAfterShortMatch);
                    } else if(s.value==3) {
                        read_bits(mem,&s,8,CS_DatAfterLongLiteralLength);s.value=(uint16_t)(s.value+9u);
                        literals(mem,&s,CS_DatAfterLongLiteralByte,CS_DatAfterLongLiteralWrite);
                    } else {
                        read_bits(mem,&s,8,CS_DatAfterMatchLength);s.handle=s.value;
                        read_match(mem,&s,12,CS_DatAfterVariableMatch);
                    }
                } else {
                    read_bits(mem,&s,1,CS_DatAfterSecondTokenBit);
                    if(s.value==1) {s.handle=1;read_match(mem,&s,8,CS_sub_1C59);}
                    else {
                        read_bits(mem,&s,3,CS_DatAfterShortLiteralLength);s.value=(uint16_t)(s.value+1u);
                        literals(mem,&s,CS_DatAfterShortLiteralByte,CS_DatAfterShortLiteralWrite);
                    }
                }
            } while(s.output>s.start);
            /* AND DH,DH defines final SZP, clears CF/OF; AF is undefined. */
            s.flags=(uint16_t)((s.flags&(0xffffu^ARITH))|szp((uint16_t)(s.stream>>8),8));
#if SECTION_MUTATION == 1
            s.flags=(uint16_t)((s.flags&(0xffffu^ARITH))|PF|ZF);
#endif
            s.handle=pop(mem,&s);s.flags=(uint16_t)(s.flags&(0xffffu^DF));
#if SECTION_MUTATION == 2
            s.es=call->source_segment;
#endif
        }
    }
    if(failed) {
        s.value=failure_segment;s.ds=failure_segment;
#if SECTION_MUTATION == 3
        s.sp=call->stack_offset;
#endif
    }
    {
        LmnDatSectionResult out={s.value,s.handle,s.bits,s.stream,s.source,s.output,
            s.start,s.ds,s.es,s.sp,s.flags,failed};return out;
    }
}

void lmn_dat_section_adapter(uint8_t *mem,LmnRegs *r,const LmnDatIo *io) {
    LmnDatSectionCall call={r->bx,r->ds,r->si,r->es,r->di,r->ss,r->sp,r->flags};
    uint16_t data_segment=word(mem,r->cs,(uint16_t)(CS_ReadDatBytes+8u));
    uint16_t failure_segment=word(mem,r->cs,(uint16_t)(CS_DatReadFailure+1u));
    LmnDatSectionResult out=lmn_dat_section_core(mem,data_segment,failure_segment,&call,io);
    r->ax=out.value;r->bx=out.handle;r->cx=out.bits_counter;r->dx=out.stream_bytes;
    r->si=out.source_cursor;r->di=out.output_cursor;r->bp=out.output_start;
    r->ds=out.source_segment;r->es=out.output_segment;r->sp=out.stack_offset;r->flags=out.flags;
    if(out.failed_read)r->ip=CS_DatFatalTransfer;
    else {r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);}
}
