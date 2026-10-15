#include "entity_vga.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint8_t read_byte(uint8_t *memory, uint32_t address, uint16_t flags,
                         const LmnRasterBus *bus) {
    if(bus && bus->read_byte)return bus->read_byte(bus->context,memory,address,flags);
    return memory[address];
}
static void write_byte(uint8_t *memory, uint32_t address, uint8_t value,
                       uint16_t flags, const LmnRasterBus *bus) {
    if(bus && bus->write_byte)bus->write_byte(bus->context,memory,address,value,flags);
    else memory[address]=value;
}
static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(memory,address,flags,bus);
    uint8_t high=read_byte(memory,(address+1u)&0xfffffu,flags,bus);
    return (uint16_t)(low|((uint16_t)high<<8));
}
static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    write_byte(memory,address,(uint8_t)value,flags,bus);
    write_byte(memory,(address+1u)&0xfffffu,(uint8_t)(value>>8),flags,bus);
}
static void output(uint8_t *memory, uint16_t ss, uint16_t mirror, uint16_t port,
                   uint16_t value, uint16_t flags, const LmnRasterBus *bus) {
    write_word(memory,ss,mirror,value,flags,bus);
    if(bus && bus->out_word)bus->out_word(bus->context,port,value,flags);
}

LmnEntityReadbackResult lmn_configure_entity_readback_core(uint8_t *memory,
    uint16_t data_segment, uint16_t stack_segment, uint16_t flags,
    const LmnRasterBus *bus) {
    LmnEntityReadbackResult result={0xa000u,0xa000u,0x3ceu,flags};
    uint16_t care=0x0807u;
#if MUTATION == 1
    care=0x0f07u;
#endif
    output(memory,stack_segment,SEG143E_VgaMapMaskMirror,0x3c4u,0x0f02u,flags,bus);
    output(memory,stack_segment,SEG143E_VgaGraphicsModeMirror,0x3ceu,0x0805u,flags,bus);
    output(memory,stack_segment,SEG143E_VgaColorCareMirror,0x3ceu,care,flags,bus);
    output(memory,stack_segment,SEG143E_VgaColorCompareMirror,0x3ceu,0x0802u,flags,bus);
    write_word(memory,data_segment,SEG09A9_EntityPixelRowPitchBytes,0x00d0u,flags,bus);
    return result;
}

LmnEntityPixelExchangeResult lmn_exchange_entity_pixel_bytes_core(uint8_t *memory,
    uint16_t stack_segment, uint16_t destination_offset, uint16_t packed_masks,
    uint16_t third_mask_word, uint16_t flags, const LmnRasterBus *bus) {
    LmnEntityPixelExchangeResult result;
    uint16_t original_flags=flags;
    uint16_t step;
    uint8_t masks[3]={(uint8_t)(packed_masks>>8),(uint8_t)packed_masks,
                      (uint8_t)third_mask_word};
    uint8_t samples[3];
    unsigned n;
    /* XOR AX,AX defines CF/PF/ZF/SF/OF; AF is undefined. */
    flags=(uint16_t)((flags&~0x8d5u)|0x44u);
    output(memory,stack_segment,SEG143E_VgaSetResetMirror,0x3ceu,0x0000u,flags,bus);
    output(memory,stack_segment,SEG143E_VgaEnableSetResetMirror,0x3ceu,0x0f01u,flags,bus);
    output(memory,stack_segment,SEG143E_VgaDataRotateMirror,0x3ceu,0x0003u,flags,bus);
    flags=(uint16_t)(flags&~0x200u);
    step=(flags&0x400u)?0xffffu:1u;
#if MUTATION == 2
    step=1u;
#endif
    for(n=0;n<3;++n) {
#if MUTATION == 3
        samples[n]=0;
#else
        samples[n]=read_byte(memory,physical(0xa000u,destination_offset),flags,bus);
#endif
        output(memory,stack_segment,SEG143E_VgaBitMaskMirror,0x3ceu,
               (uint16_t)(((uint16_t)masks[n]<<8)|8u),flags,bus);
        write_byte(memory,physical(0xa000u,destination_offset),masks[n],flags,bus);
        destination_offset=(uint16_t)(destination_offset+step);
    }
#if MUTATION == 5
    flags=(uint16_t)(flags|(original_flags&0x200u));
#else
    (void)original_flags;
    flags=(uint16_t)(flags|0x200u);
#endif
    result.value=(uint16_t)(((uint16_t)masks[2]<<8)|masks[2]);
    result.packed_bytes=(uint16_t)(((uint16_t)samples[0]<<8)|samples[1]);
    result.third_byte_word=(uint16_t)((third_mask_word&0xff00u)|samples[2]);
    result.destination_offset=destination_offset;
    result.output_segment=0xa000u;
    result.port=0x3ceu;
    result.flags=flags;
    return result;
}

void lmn_configure_entity_readback_adapter(uint8_t *memory, LmnRegs *r,
                                           const LmnRasterBus *bus) {
#if MUTATION == 4
    uint16_t target=read_word(memory,r->ss,r->sp,r->flags,bus);
#endif
    LmnEntityReadbackResult result=lmn_configure_entity_readback_core(
        memory,r->ds,r->ss,r->flags,bus);
    r->ax=result.value;
    r->es=result.output_segment;
    r->dx=result.port;
    r->flags=result.flags;
#if MUTATION == 4
    r->ip=target;
#else
    r->ip=read_word(memory,r->ss,r->sp,r->flags,bus);
#endif
    r->sp=(uint16_t)(r->sp+2u);
}

void lmn_exchange_entity_pixel_bytes_adapter(uint8_t *memory, LmnRegs *r,
                                              const LmnRasterBus *bus) {
#if MUTATION == 4
    uint16_t target=read_word(memory,r->ss,r->sp,r->flags,bus);
#endif
    LmnEntityPixelExchangeResult result=lmn_exchange_entity_pixel_bytes_core(
        memory,r->ss,r->di,r->bx,r->cx,r->flags,bus);
    r->ax=result.value;
    r->bx=result.packed_bytes;
    r->cx=result.third_byte_word;
    r->di=result.destination_offset;
    r->es=result.output_segment;
    r->dx=result.port;
    r->flags=result.flags;
#if MUTATION == 4
    r->ip=target;
#else
    r->ip=read_word(memory,r->ss,r->sp,r->flags,bus);
#endif
    r->sp=(uint16_t)(r->sp+2u);
}
