#include "resource_raw.h"
#include "lemmings_sym.h"
#ifndef MUTATION
#define MUTATION 0
#endif
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void putword(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t p=physical(seg,off);mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static void push(uint8_t *mem,uint16_t ss,uint16_t *sp,uint16_t value) {*sp=(uint16_t)(*sp-2u);putword(mem,ss,*sp,value);}
static uint16_t pop(const uint8_t *mem,uint16_t ss,uint16_t *sp) {
    uint16_t value=word(mem,ss,*sp);*sp=(uint16_t)(*sp+2u);return value;
}
LmnRawResourceResult lmn_read_raw_resource_core(uint8_t *mem,const LmnRawResourceCall *call,const LmnRawResourceServices *services) {
    uint16_t ds=call->filename_segment,es=call->destination_segment,dx=call->filename_offset;
    uint16_t cx=call->count,bx=call->initial_handle,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t value=call->destination_offset,flags=call->flags,error=0;LmnDatDosResult service;
    push(mem,ss,&sp,ds);push(mem,ss,&sp,es);push(mem,ss,&sp,value);push(mem,ss,&sp,es);push(mem,ss,&sp,cx);
    putword(mem,ds,SEG09A9_LastResourceFilenameOffset,dx);
    services->open_readonly(services->context,mem,ds,dx,flags,&service);value=service.value;flags=service.flags;
    if(flags&1u) {error=1;dx=SEG09A9_DatFileErrorMessage;}
    else {
        bx=value;cx=pop(mem,ss,&sp);ds=pop(mem,ss,&sp);dx=pop(mem,ss,&sp);
        services->read(services->context,mem,bx,ds,dx,cx,flags,&service);value=service.value;flags=service.flags;
        if(flags&1u) {error=2;dx=SEG09A9_ResourceReadErrorMessage;}
        else {
            value=(uint16_t)(0x3e00u|(value&255u));
#if MUTATION == 1
            value=0x3e00;
#endif
            services->close(services->context,mem,bx,value,flags,&service);value=service.value;flags=service.flags;
            if(flags&1u) {error=3;dx=SEG09A9_ResourceCloseErrorMessage;}
            else {
#if MUTATION == 2
                (void)pop(mem,ss,&sp);(void)pop(mem,ss,&sp);es=call->destination_segment;ds=call->filename_segment;
#else
                es=pop(mem,ss,&sp);ds=pop(mem,ss,&sp);
#endif
            }
        }
    }
#if MUTATION == 3
    if(error)sp=call->stack_offset;
#endif
    {LmnRawResourceResult out={value,bx,cx,dx,ds,es,sp,flags,error};return out;}
}
void lmn_read_raw_resource_adapter(uint8_t *mem,LmnRegs *r,const LmnRawResourceServices *services) {
    LmnRawResourceCall call={r->ds,r->dx,r->es,r->ax,r->cx,r->bx,r->ss,r->sp,r->flags};
    LmnRawResourceResult out=lmn_read_raw_resource_core(mem,&call,services);
    r->ax=out.value;r->bx=out.handle;r->cx=out.count;r->dx=out.offset;r->ds=out.segment;
    r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    if(out.error_stage)r->ip=CS_DatFileErrorTransfer;
    else {r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);}
}
