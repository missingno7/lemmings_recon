#include "dat_files.h"
#include "dat_cache.h"
#include "lemmings_sym.h"
#ifndef FILE_MUTATION
#define FILE_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,OF=2048,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint8_t byte(const uint8_t *mem,uint16_t seg,uint16_t off) {return mem[physical(seg,off)];}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void push(uint8_t *mem,LmnDatFileCall *s,uint16_t value) {
    uint32_t p;s->stack_offset=(uint16_t)(s->stack_offset-2u);p=physical(s->stack_segment,s->stack_offset);
    mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static uint16_t pop(const uint8_t *mem,LmnDatFileCall *s) {
    uint16_t value=word(mem,s->stack_segment,s->stack_offset);s->stack_offset=(uint16_t)(s->stack_offset+2u);return value;
}
static uint16_t compare_byte(uint16_t flags,uint8_t a,uint8_t b) {
    uint8_t value=(uint8_t)(a-b);unsigned i,parity=0;
    uint16_t out=(uint16_t)(flags&(0xffffu^ARITH));
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&128u)out|=SF;
    if(a<b)out|=CF;
    out|=(uint16_t)((a^b^value)&AF);
    if((a^b)&(a^value)&128u)out|=OF;
    return out;
}
static void save(uint8_t *mem,LmnDatFileCall *s) {
    push(mem,s,s->segment);push(mem,s,s->filename_offset);push(mem,s,s->extra_segment);
    push(mem,s,s->output_cursor);push(mem,s,s->count);push(mem,s,s->source_cursor);
}
static void restore(const uint8_t *mem,LmnDatFileCall *s) {
    s->source_cursor=pop(mem,s);s->count=pop(mem,s);s->output_cursor=pop(mem,s);
    s->extra_segment=pop(mem,s);s->filename_offset=pop(mem,s);s->segment=pop(mem,s);
}
static void save_retry(uint8_t *mem,LmnDatFileCall *s) {
    push(mem,s,s->filename_offset);push(mem,s,s->count);push(mem,s,s->extra_segment);
    push(mem,s,s->segment);push(mem,s,s->output_cursor);push(mem,s,s->source_cursor);
}
static void restore_retry(const uint8_t *mem,LmnDatFileCall *s) {
    s->source_cursor=pop(mem,s);s->output_cursor=pop(mem,s);s->segment=pop(mem,s);
    s->extra_segment=pop(mem,s);s->count=pop(mem,s);s->filename_offset=pop(mem,s);
}
static LmnDatFileResult result(const LmnDatFileCall *s,uint16_t fatal) {
    LmnDatFileResult out={s->value,s->handle,s->count,s->filename_offset,s->source_cursor,
        s->output_cursor,s->base_cursor,s->segment,s->extra_segment,s->stack_offset,s->flags,fatal};return out;
}
LmnDatFileResult lmn_dat_open_file_core(uint8_t *mem,const LmnDatFileCall *call,const LmnDatFileServices *services) {
    LmnDatFileCall s=*call;LmnDatFileServiceResult out;unsigned skip=0;
    save(mem,&s);s.flags=compare_byte(s.flags,byte(mem,s.segment,SEG09A9_DatCacheEnabled),255);
    if(byte(mem,s.segment,SEG09A9_DatCacheEnabled)==255) {
        s.flags=compare_byte(s.flags,byte(mem,s.segment,SEG09A9_DatCacheSelected),255);
        skip=byte(mem,s.segment,SEG09A9_DatCacheSelected)==255;
    }
#if FILE_MUTATION == 1
    skip=0;
#endif
    if(!skip) {
        services->open_readonly(services->context,mem,s.segment,s.filename_offset,s.flags,&out);
        s.value=out.value;s.flags=out.flags;
    }
    restore(mem,&s);return result(&s,0);
}
LmnDatFileResult lmn_dat_check_file_core(uint8_t *mem,uint16_t retry_data_segment,
    uint16_t lookup_data_segment,const LmnDatFileCall *call,const LmnDatFileServices *services) {
    LmnDatFileCall s=*call;LmnDatFileServiceResult service;
    save(mem,&s);s.flags=compare_byte(s.flags,byte(mem,s.segment,SEG09A9_DatCacheEnabled),255);
    if(byte(mem,s.segment,SEG09A9_DatCacheEnabled)==255) {
        LmnDatNameCall name;LmnDatNameResult prepared;LmnDatLookupCall lookup;LmnDatLookupResult selected;
        push(mem,&s,CS_DatAfterNamePreparation);
        name=(LmnDatNameCall){s.segment,s.filename_offset,s.value,s.count,s.extra_segment,s.stack_segment,s.stack_offset,s.flags};
        prepared=lmn_dat_prepare_name_core(mem,&name);
        s.filename_offset=prepared.filename_offset;s.value=prepared.value;s.count=prepared.count;s.extra_segment=prepared.extra_segment;
        s.source_cursor=prepared.source_cursor;s.output_cursor=prepared.output_cursor;s.stack_offset=prepared.stack_offset;s.flags=prepared.flags;
        (void)pop(mem,&s);push(mem,&s,CS_DatAfterCacheSelection);
        lookup=(LmnDatLookupCall){s.segment,s.source_cursor,s.output_cursor,s.value,s.count,s.extra_segment,s.stack_segment,s.stack_offset,s.flags};
        selected=lmn_dat_select_cache_core(mem,lookup_data_segment,&lookup);
        s.segment=selected.segment;s.source_cursor=selected.source_cursor;s.output_cursor=selected.comparison_cursor;
        s.value=selected.value;s.count=selected.count;s.extra_segment=selected.extra_segment;s.stack_offset=selected.stack_offset;s.flags=selected.flags;
        (void)pop(mem,&s);
        if(!(s.flags&CF)) {restore(mem,&s);return result(&s,0);}
    }
    for(;;) {
        unsigned error;
        s.value=0x4300;s.count=0;s.flags=(uint16_t)((s.flags&(0xffffu^ARITH))|PF|ZF);
        services->attributes(services->context,mem,s.segment,s.filename_offset,s.flags,&service);
        s.value=service.value;s.count=service.count;s.flags=service.flags;error=(s.flags&CF)!=0;
        if(!error) {
            s.flags=compare_byte(s.flags,byte(mem,s.segment,SEG09A9_DatCriticalErrorFlag),0);
            error=byte(mem,s.segment,SEG09A9_DatCriticalErrorFlag)!=0;
        }
#if FILE_MUTATION == 2
        error=(s.flags&CF)!=0;
#endif
        if(!error) {restore(mem,&s);return result(&s,0);}
        save_retry(mem,&s);s.value=retry_data_segment;s.segment=retry_data_segment;
        s.flags=compare_byte(s.flags,byte(mem,s.segment,SEG09A9_DatRetryEnabled),0);
        if(byte(mem,s.segment,SEG09A9_DatRetryEnabled)==0) {
            restore_retry(mem,&s);s.filename_offset=SEG09A9_DatFileErrorMessage;
#if FILE_MUTATION == 3
            restore(mem,&s);
#endif
            return result(&s,1);
        } else {
            LmnDatRetryResult retried;
            push(mem,&s,CS_DatAfterFileRetry);services->retry_ui(services->context,mem,&s,&retried);
            s.value=retried.value;s.handle=retried.handle;s.base_cursor=retried.base_cursor;s.flags=retried.flags;
            (void)pop(mem,&s);restore_retry(mem,&s);
        }
    }
}
static LmnDatFileCall call_from_regs(const LmnRegs *r) {
    LmnDatFileCall call={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};return call;
}
static void apply(uint8_t *mem,LmnRegs *r,const LmnDatFileResult *out) {
    r->ax=out->value;r->bx=out->handle;r->cx=out->count;r->dx=out->filename_offset;
    r->si=out->source_cursor;r->di=out->output_cursor;r->bp=out->base_cursor;
    r->ds=out->segment;r->es=out->extra_segment;r->sp=out->stack_offset;r->flags=out->flags;
    if(out->fatal)r->ip=CS_DatFileErrorTransfer;
    else {r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);}
}
void lmn_dat_open_file_adapter(uint8_t *mem,LmnRegs *r,const LmnDatFileServices *services) {
    LmnDatFileCall call=call_from_regs(r);LmnDatFileResult out=lmn_dat_open_file_core(mem,&call,services);apply(mem,r,&out);
}
void lmn_dat_check_file_adapter(uint8_t *mem,LmnRegs *r,const LmnDatFileServices *services) {
    LmnDatFileCall call=call_from_regs(r);
    uint16_t retry_segment=word(mem,r->cs,(uint16_t)(CS_CheckDatFile+0x33u));
    uint16_t lookup_segment=word(mem,r->cs,(uint16_t)(CS_SelectCachedDatFile+0x50u));
    LmnDatFileResult out=lmn_dat_check_file_core(mem,retry_segment,lookup_segment,&call,services);apply(mem,r,&out);
}
