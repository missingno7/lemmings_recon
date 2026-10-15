#include "entity_pixel.h"
#include "lemmings_sym.h"
#include <stddef.h>

#ifndef MUTATION
#define MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800 };
enum { ARITH=CF|PF|AF|ZF|SF|OF, LOGIC=CF|PF|ZF|SF|OF };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}

static uint8_t read_physical(uint8_t *memory, uint32_t address,
                             uint16_t flags, const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->read_byte)
        return bus->read_byte(bus->context,memory,address,flags);
    return memory[address];
}

static void write_physical(uint8_t *memory, uint32_t address, uint8_t value,
                           uint16_t flags, const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->write_byte)
        bus->write_byte(bus->context,memory,address,value,flags);
    else
        memory[address]=value;
}

/* A real-mode word access uses the following physical byte, even when its
   segment offset is FFFFh or its physical address wraps at 20 bits. */
static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(memory,address,flags,bus);
    uint8_t high=read_physical(memory,address+1u,flags,bus);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    write_physical(memory,address,(uint8_t)value,flags,bus);
    write_physical(memory,address+1u,(uint8_t)(value>>8),flags,bus);
}

static uint16_t sub16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t subtrahend=(uint32_t)right;
    uint16_t value=(uint16_t)(left-right);
    uint16_t status=0;
    unsigned parity=0, bit;
    if((uint32_t)left<subtrahend)status|=CF;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)status|=PF;
    if((left^right^value)&0x10u)status|=AF;
    if(!value)status|=ZF;
    if(value&0x8000u)status|=SF;
    if(((left^right)&(left^value)&0x8000u)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

#if MUTATION != 1
static uint16_t xor_zero_flags(uint16_t flags) {
    uint16_t status=(uint16_t)(ZF|PF); /* XOR DI,DI produces zero. */
    return (uint16_t)((flags&~LOGIC)|status);
}
#endif

static uint16_t mul16_flags(uint16_t flags, uint32_t product) {
    /* MUL defines only CF and OF; keep the other arithmetic bits opaque. */
    uint16_t status=(product>>16) ? (CF|OF):0;
    return (uint16_t)((flags&~(CF|OF))|status);
}

static uint16_t table_add_flags(uint16_t flags, uint16_t index) {
    uint16_t value=(uint16_t)(index+SEG09A9_PixelBitMasks);
    uint16_t status=0;
    unsigned parity=0, bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)status|=PF;
    /* Index is 0..7: ADD 547Ch cannot carry, overflow, become negative or zero. */
    if((index^SEG09A9_PixelBitMasks^value)&0x10u)status|=AF;
    return (uint16_t)((flags&~ARITH)|status);
}

LmnEntityPixelResult lmn_prepare_entity_pixel_bus_core(
    uint8_t *memory, const LmnEntityPixelCall *call,
    const LmnRasterBus *bus) {
    uint16_t ds=call->data_segment, ss=call->stack_segment;
    uint16_t sp=call->stack_offset, si=call->record_cursor;
    uint16_t flags=call->flags;
    const LmnRasterBus *access_bus=bus;
#if MUTATION == 5
    access_bus=NULL;
#endif
    uint16_t y=read_word(memory,ds,(uint16_t)(si+2u),flags,access_bus);
    uint16_t row=(uint16_t)(y-0x10u);
    uint32_t product;
    uint16_t x, dx, index, mask, final_flags;
    LmnEntityPixelResult out;
#if MUTATION == 1
    if(y<0x10u || (y&0x8000u)) {
        row=0;
        flags=sub16_flags(flags,y,0x10u);
    } else {
        flags=sub16_flags(flags,y,0x10u);
    }
#else
    flags=sub16_flags(flags,y,0x10u);
    if(row&0x8000u) {
        row=0;
        flags=xor_zero_flags(flags);
    }
#endif
#if MUTATION == 2
    x=read_word(memory,ds,si,flags,access_bus);
#endif
    sp=(uint16_t)(sp-2u);
    write_word(memory,ss,sp,call->saved_value,flags,access_bus);
    product=(uint32_t)row*0xd0u;
    flags=mul16_flags(flags,product);
    dx=read_word(memory,ss,sp,flags,access_bus);
    sp=(uint16_t)(sp+2u);
#if MUTATION != 2
    x=read_word(memory,ds,si,flags,access_bus);
#endif
    index=(uint16_t)(x&7u);
    final_flags=table_add_flags(flags,index);
    out.column_byte=(uint16_t)(x>>3);
    out.destination_offset=(uint16_t)((uint16_t)product+
                                      out.column_byte+0x4a40u);
    out.table_cursor=(uint16_t)(SEG09A9_PixelBitMasks+index);
#if MUTATION == 3
    mask=(uint16_t)(0x80u>>index);
#else
    mask=read_physical(memory,physical(ds,out.table_cursor),final_flags,access_bus);
#endif
    out.value=(uint16_t)(((uint16_t)product&0xffu)|(mask<<8));
#if MUTATION == 4
    out.value&=0xff00u;
#endif
    out.restored_value=dx;
    out.stack_offset=sp;
    out.flags=final_flags;
    return out;
}

LmnEntityPixelResult lmn_prepare_entity_pixel_core(
    uint8_t *memory, const LmnEntityPixelCall *call) {
    return lmn_prepare_entity_pixel_bus_core(memory,call,NULL);
}

void lmn_prepare_entity_pixel_bus_adapter(uint8_t *memory, LmnRegs *r,
                                          const LmnRasterBus *bus) {
    LmnEntityPixelCall call={r->ds,r->ss,r->sp,r->si,r->dx,r->flags};
    LmnEntityPixelResult out=lmn_prepare_entity_pixel_bus_core(memory,&call,bus);
    r->ax=out.value;
    r->bx=out.table_cursor;
    r->cx=out.column_byte;
    r->di=out.destination_offset;
    r->dx=out.restored_value;
    r->es=0xa000u;
    r->sp=out.stack_offset;
    r->flags=out.flags;
    r->ip=read_word(memory,r->ss,r->sp,r->flags,bus);
    r->sp=(uint16_t)(r->sp+2u);
}

void lmn_prepare_entity_pixel_adapter(uint8_t *memory, LmnRegs *r) {
    lmn_prepare_entity_pixel_bus_adapter(memory,r,NULL);
}
