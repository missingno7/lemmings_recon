#include "resource_raw.h"
#include "lemmings_sym.h"
#ifndef MUTATION
#define MUTATION 0
#endif
#ifndef RAW_BUS_MUTATION
#define RAW_BUS_MUTATION 0
#endif
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint8_t read_byte(uint8_t *mem,const LmnRasterBus *bus,uint32_t address,uint16_t flags) {
    address&=0xfffffu;
    if(bus&&bus->read_byte)return bus->read_byte(bus->context,mem,address,flags);
    return mem[address];
}
static void write_byte(uint8_t *mem,const LmnRasterBus *bus,uint32_t address,uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(bus&&bus->write_byte)bus->write_byte(bus->context,mem,address,value,flags);
    else mem[address]=value;
}
static uint16_t read_word(uint8_t *mem,const LmnRasterBus *bus,uint16_t seg,uint16_t off,uint16_t flags) {
    uint32_t p=physical(seg,off);
    uint8_t low=read_byte(mem,bus,p,flags);
    uint8_t high=read_byte(mem,bus,p+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}
static void write_word(uint8_t *mem,const LmnRasterBus *bus,uint16_t seg,uint16_t off,uint16_t value,uint16_t flags,unsigned reverse) {
    uint32_t p=physical(seg,off);
    if(reverse) {
        write_byte(mem,bus,p+1u,(uint8_t)(value>>8),flags);
        write_byte(mem,bus,p,(uint8_t)value,flags);
    } else {
        write_byte(mem,bus,p,(uint8_t)value,flags);
        write_byte(mem,bus,p+1u,(uint8_t)(value>>8),flags);
    }
}
static void push(uint8_t *mem,const LmnRasterBus *bus,uint16_t ss,uint16_t *sp,uint16_t value,uint16_t flags) {
    *sp=(uint16_t)(*sp-2u);write_word(mem,bus,ss,*sp,value,flags,0);
}
static uint16_t pop(uint8_t *mem,const LmnRasterBus *bus,uint16_t ss,uint16_t *sp,uint16_t flags) {
    uint16_t value=read_word(mem,bus,ss,*sp,flags);*sp=(uint16_t)(*sp+2u);return value;
}
LmnRawResourceResult lmn_read_raw_resource_bus_core(uint8_t *mem,const LmnRawResourceCall *call,const LmnRawResourceServices *services,const LmnRasterBus *bus) {
    uint16_t ds=call->filename_segment,es=call->destination_segment,dx=call->filename_offset;
    uint16_t cx=call->count,bx=call->initial_handle,ss=call->stack_segment,sp=call->stack_offset;
    uint16_t value=call->destination_offset,flags=call->flags,error=0;LmnDatDosResult service;
    push(mem,bus,ss,&sp,ds,flags);push(mem,bus,ss,&sp,es,flags);push(mem,bus,ss,&sp,value,flags);
    push(mem,bus,ss,&sp,es,flags);push(mem,bus,ss,&sp,cx,flags);
    write_word(mem,bus,ds,SEG09A9_LastResourceFilenameOffset,dx,flags,RAW_BUS_MUTATION==1);
    services->open_readonly(services->context,mem,ds,dx,flags,&service);value=service.value;flags=service.flags;
    if(flags&1u) {error=1;dx=SEG09A9_DatFileErrorMessage;}
    else {
        bx=value;cx=pop(mem,bus,ss,&sp,flags);ds=pop(mem,bus,ss,&sp,flags);dx=pop(mem,bus,ss,&sp,flags);
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
                (void)pop(mem,bus,ss,&sp,flags);(void)pop(mem,bus,ss,&sp,flags);es=call->destination_segment;ds=call->filename_segment;
#elif RAW_BUS_MUTATION == 2
                (void)pop(mem,bus,ss,&sp,flags);(void)pop(mem,bus,ss,&sp,flags);es=call->destination_segment;ds=call->filename_segment;
#else
                es=pop(mem,bus,ss,&sp,flags);ds=pop(mem,bus,ss,&sp,flags);
#endif
            }
        }
    }
#if MUTATION == 3
    if(error)sp=call->stack_offset;
#endif
    {LmnRawResourceResult out={value,bx,cx,dx,ds,es,sp,flags,error};return out;}
}
LmnRawResourceResult lmn_read_raw_resource_core(uint8_t *mem,const LmnRawResourceCall *call,const LmnRawResourceServices *services) {
    return lmn_read_raw_resource_bus_core(mem,call,services,0);
}
static void raw_bus_ret(uint8_t *mem,LmnRegs *r,const LmnRasterBus *bus) {
    uint32_t p=physical(r->ss,r->sp);
    uint8_t low=read_byte(mem,bus,p,r->flags);
    uint8_t high=read_byte(mem,bus,p+1u,r->flags);
    r->ip=(uint16_t)(low|((uint16_t)high<<8));r->sp=(uint16_t)(r->sp+2u);
}
void lmn_read_raw_resource_bus_adapter(uint8_t *mem,LmnRegs *r,const LmnRawResourceServices *services,const LmnRasterBus *bus) {
    LmnRawResourceCall call={r->ds,r->dx,r->es,r->ax,r->cx,r->bx,r->ss,r->sp,r->flags};
    LmnRawResourceResult out=lmn_read_raw_resource_bus_core(mem,&call,services,bus);
    r->ax=out.value;r->bx=out.handle;r->cx=out.count;r->dx=out.offset;r->ds=out.segment;
    r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    if(out.error_stage)r->ip=CS_DatFileErrorTransfer;
    else raw_bus_ret(mem,r,bus);
}
void lmn_read_raw_resource_adapter(uint8_t *mem,LmnRegs *r,const LmnRawResourceServices *services) {
    lmn_read_raw_resource_bus_adapter(mem,r,services,0);
}
