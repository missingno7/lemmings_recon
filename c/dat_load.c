#include "dat_load.h"
#include "lemmings_sym.h"
#ifndef LOAD_MUTATION
#define LOAD_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,OF=2048,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void push(uint8_t *mem,LmnDatFileCall *s,uint16_t value) {
    uint32_t p;s->stack_offset=(uint16_t)(s->stack_offset-2u);p=physical(s->stack_segment,s->stack_offset);
    mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static uint16_t pop(const uint8_t *mem,LmnDatFileCall *s) {
    uint16_t out=word(mem,s->stack_segment,s->stack_offset);s->stack_offset=(uint16_t)(s->stack_offset+2u);return out;
}
static uint16_t compare_zero(uint16_t flags,uint8_t value) {
    unsigned i,parity=0;uint16_t out=(uint16_t)(flags&(0xffffu^ARITH));
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&128u)out|=SF;
    return out;
}
static LmnDatFileCall state_from_result(const LmnDatFileResult *out,uint16_t ss) {
    LmnDatFileCall s={out->value,out->handle,out->count,out->filename_offset,out->source_cursor,
        out->output_cursor,out->base_cursor,out->segment,out->extra_segment,ss,out->stack_offset,out->flags};return s;
}
static LmnDatFileResult result(const LmnDatFileCall *s,uint16_t fatal) {
    LmnDatFileResult out={s->value,s->handle,s->count,s->filename_offset,s->source_cursor,
        s->output_cursor,s->base_cursor,s->segment,s->extra_segment,s->stack_offset,s->flags,fatal};return out;
}
LmnDatFileResult lmn_dat_decode_preserving_segment_core(uint8_t *mem,const LmnDatFileCall *call,
    const LmnDatLoadSegments *segments,const LmnDatIo *io) {
    LmnDatFileCall s=*call;LmnDatSectionCall decoder;LmnDatSectionResult decoded;
    push(mem,&s,s.segment);push(mem,&s,CS_sub_1BAD);
    decoder=(LmnDatSectionCall){s.handle,s.segment,s.source_cursor,s.extra_segment,s.output_cursor,
        s.stack_segment,s.stack_offset,s.flags};
    decoded=lmn_dat_section_core(mem,segments->read_data,segments->decode_failure_data,&decoder,io);
    s.value=decoded.value;s.handle=decoded.handle;s.count=decoded.bits_counter;s.filename_offset=decoded.stream_bytes;
    s.source_cursor=decoded.source_cursor;s.output_cursor=decoded.output_cursor;s.base_cursor=decoded.output_start;
    s.segment=decoded.source_segment;s.extra_segment=decoded.output_segment;s.stack_offset=decoded.stack_offset;s.flags=decoded.flags;
    if(decoded.failed_read) {
#if LOAD_MUTATION == 3
        s.segment=pop(mem,&s);
#endif
        return result(&s,2);
    }
    (void)pop(mem,&s);
#if LOAD_MUTATION == 2
    (void)pop(mem,&s);s.segment=call->segment;
#else
    s.segment=pop(mem,&s);
#endif
    return result(&s,0);
}
static LmnDatFileResult load(uint8_t *mem,const LmnDatFileCall *call,const LmnDatLoadSegments *segments,
    const LmnDatFileServices *files,const LmnDatIo *io,unsigned after_check) {
    LmnDatFileCall s=*call;
    for(;;) {
        unsigned retry;
        if(!after_check) {
            LmnDatFileResult checked;
            push(mem,&s,s.count);push(mem,&s,CS_DatAfterResourceCheck);
            checked=lmn_dat_check_file_core(mem,segments->retry_data,segments->lookup_data,&s,files);
            s=state_from_result(&checked,s.stack_segment);
            if(checked.fatal)return result(&s,1);
            (void)pop(mem,&s);
        }
        after_check=0;s.count=pop(mem,&s);retry=(s.flags&CF)!=0;
        if(!retry) {
            uint8_t critical=mem[physical(s.segment,SEG09A9_DatCriticalErrorFlag)];
            s.flags=compare_zero(s.flags,critical);retry=critical!=0;
        }
        if(!retry) {
            LmnDatFileResult opened;unsigned open_carry;
            push(mem,&s,CS_DatAfterResourceOpen);opened=lmn_dat_open_file_core(mem,&s,files);
            s=state_from_result(&opened,s.stack_segment);(void)pop(mem,&s);open_carry=(s.flags&CF)!=0;
            {
                uint8_t critical=mem[physical(s.segment,SEG09A9_DatCriticalErrorFlag)];
                s.flags=compare_zero(s.flags,critical);retry=critical!=0;
            }
#if LOAD_MUTATION == 1
            if(open_carry)retry=1;
#else
            (void)open_carry;
#endif
            if(!retry) {
                s.handle=s.value;s.segment=s.count;
                return lmn_dat_decode_preserving_segment_core(mem,&s,segments,io);
            }
        }
        {
            LmnDatRetryResult retried;
            push(mem,&s,s.filename_offset);push(mem,&s,s.count);push(mem,&s,s.extra_segment);
            push(mem,&s,s.segment);push(mem,&s,s.output_cursor);push(mem,&s,s.source_cursor);
            push(mem,&s,CS_DatAfterResourceRetry);files->retry_ui(files->context,mem,&s,&retried);
            s.value=retried.value;s.handle=retried.handle;s.base_cursor=retried.base_cursor;s.flags=retried.flags;
            (void)pop(mem,&s);s.source_cursor=pop(mem,&s);s.output_cursor=pop(mem,&s);s.segment=pop(mem,&s);
            s.extra_segment=pop(mem,&s);s.count=pop(mem,&s);s.filename_offset=pop(mem,&s);
        }
    }
}
LmnDatFileResult lmn_dat_load_core(uint8_t *mem,const LmnDatFileCall *call,const LmnDatLoadSegments *segments,
    const LmnDatFileServices *files,const LmnDatIo *io) {return load(mem,call,segments,files,io,0);}
static LmnDatFileCall call_from_regs(const LmnRegs *r) {
    LmnDatFileCall s={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};return s;
}
static LmnDatLoadSegments segments_from_memory(const uint8_t *mem,uint16_t cs) {
    LmnDatLoadSegments segments={word(mem,cs,(uint16_t)(CS_CheckDatFile+0x33u)),
        word(mem,cs,(uint16_t)(CS_SelectCachedDatFile+0x50u)),word(mem,cs,(uint16_t)(CS_ReadDatBytes+8u)),
        word(mem,cs,(uint16_t)(CS_DatReadFailure+1u))};return segments;
}
static void apply(uint8_t *mem,LmnRegs *r,const LmnDatFileResult *out) {
    r->ax=out->value;r->bx=out->handle;r->cx=out->count;r->dx=out->filename_offset;
    r->si=out->source_cursor;r->di=out->output_cursor;r->bp=out->base_cursor;
    r->ds=out->segment;r->es=out->extra_segment;r->sp=out->stack_offset;r->flags=out->flags;
    if(out->fatal)r->ip=out->fatal==1 ? CS_DatFileErrorTransfer:CS_DatFatalTransfer;
    else {r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);}
}
void lmn_dat_load_adapter(uint8_t *mem,LmnRegs *r,const LmnDatFileServices *files,const LmnDatIo *io) {
    LmnDatFileCall call=call_from_regs(r);LmnDatLoadSegments segments=segments_from_memory(mem,r->cs);
    LmnDatFileResult out=lmn_dat_load_core(mem,&call,&segments,files,io);apply(mem,r,&out);
}
void lmn_dat_load_after_check_adapter(uint8_t *mem,LmnRegs *r,const LmnDatFileServices *files,const LmnDatIo *io) {
    LmnDatFileCall call=call_from_regs(r);LmnDatLoadSegments segments=segments_from_memory(mem,r->cs);
    LmnDatFileResult out=load(mem,&call,&segments,files,io,1);apply(mem,r,&out);
}
void lmn_dat_decode_preserving_segment_adapter(uint8_t *mem,LmnRegs *r,const LmnDatIo *io) {
    LmnDatFileCall call=call_from_regs(r);LmnDatLoadSegments segments=segments_from_memory(mem,r->cs);
    LmnDatFileResult out=lmn_dat_decode_preserving_segment_core(mem,&call,&segments,io);apply(mem,r,&out);
}
