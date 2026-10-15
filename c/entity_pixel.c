#include "entity_pixel.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint16_t word(const uint8_t *memory, uint16_t segment, uint16_t offset) {
    uint32_t p=physical(segment,offset);
    return (uint16_t)(memory[p]|((uint16_t)memory[(p+1u)&0xfffffu]<<8));
}
static void store_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value) {
    uint32_t p=physical(segment,offset);
    memory[p]=(uint8_t)value;
    memory[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static uint16_t table_add_flags(uint16_t flags, uint16_t index) {
    uint16_t value=(uint16_t)(index+SEG09A9_PixelBitMasks);
    uint16_t status=0;
    unsigned parity=0, bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)status|=4u;
    /* The original AND restricts index to 0..7. ADD 547Ch cannot carry,
       overflow, become negative or zero; AF changes at index four. */
    if((index^SEG09A9_PixelBitMasks^value)&0x10u)status|=0x10u;
    return (uint16_t)((flags&~0x8d5u)|status);
}

LmnEntityPixelResult lmn_prepare_entity_pixel_core(
    uint8_t *memory, const LmnEntityPixelCall *call) {
    uint16_t ds=call->data_segment, ss=call->stack_segment;
    uint16_t sp=call->stack_offset, si=call->record_cursor;
    uint16_t y=word(memory,ds,(uint16_t)(si+2u));
    uint16_t row=(uint16_t)(y-0x10u);
    uint16_t product, x, dx, index, mask;
    LmnEntityPixelResult out;
#if MUTATION == 1
    if(y<0x10u || (y&0x8000u))row=0;
#else
    if(row&0x8000u)row=0;
#endif
#if MUTATION == 2
    x=word(memory,ds,si);
#endif
    sp=(uint16_t)(sp-2u);
    store_word(memory,ss,sp,call->saved_value);
    product=(uint16_t)((uint32_t)row*0xd0u);
    dx=word(memory,ss,sp);
    sp=(uint16_t)(sp+2u);
#if MUTATION != 2
    /* 5DDE is after PUSH DX: live stack aliases can change the X word. */
    x=word(memory,ds,si);
#endif
    index=(uint16_t)(x&7u);
    out.column_byte=(uint16_t)(x>>3);
    out.destination_offset=(uint16_t)(product+out.column_byte+0x4a40u);
    out.table_cursor=(uint16_t)(SEG09A9_PixelBitMasks+index);
#if MUTATION == 3
    mask=(uint16_t)(0x80u>>index);
#else
    mask=memory[physical(ds,out.table_cursor)];
#endif
    out.value=(uint16_t)((product&0xffu)|(mask<<8));
#if MUTATION == 4
    out.value&=0xff00u;
#endif
    out.restored_value=dx;
    out.stack_offset=sp;
    out.flags=table_add_flags(call->flags,index);
    return out;
}

void lmn_prepare_entity_pixel_adapter(uint8_t *memory, LmnRegs *r) {
    LmnEntityPixelCall call={r->ds,r->ss,r->sp,r->si,r->dx,r->flags};
    LmnEntityPixelResult out=lmn_prepare_entity_pixel_core(memory,&call);
    r->ax=out.value;
    r->bx=out.table_cursor;
    r->cx=out.column_byte;
    r->di=out.destination_offset;
    r->dx=out.restored_value;
    r->es=0xa000u;
    r->sp=out.stack_offset;
    r->flags=out.flags;
    r->ip=word(memory,r->ss,r->sp);
    r->sp=(uint16_t)(r->sp+2u);
}
