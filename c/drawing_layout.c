#include "drawing_layout.h"
#include "lemmings_sym.h"

#ifndef LAYOUT_MUTATION
#define LAYOUT_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040, SF=0x0080,
       IF=0x0200, DF=0x0400, OF=0x0800, ARITH=0x08d5 };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address]=value;
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_byte(memory,bus,address,(uint8_t)value,flags);
    write_byte(memory,bus,(address+1u)&0xfffffu,(uint8_t)(value>>8),flags);
}

static uint16_t read_word_at(uint8_t *memory, const LmnRasterBus *bus,
                             uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    uint8_t low=read_byte(memory,bus,address,flags);
    uint8_t high=read_byte(memory,bus,(address+1u)&0xfffffu,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity=0;
    unsigned bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    return parity==0u;
}

/* Keep the representative value of undefined AF; update every defined SHR
   flag, then let MUL replace only CF/OF in the final architectural result. */
static uint16_t shr_one_flags(uint16_t flags, uint16_t before,
                              uint16_t after) {
    uint16_t set=0;
    if(before&1u)set|=CF;
    if(even_parity8((uint8_t)after))set|=PF;
    if(after==0u)set|=ZF;
    if(before&0x8000u)set|=OF;
    return (uint16_t)((flags & (uint16_t)~(CF|PF|ZF|SF|OF)) | set);
}

LmnDrawingLayoutResult lmn_set_drawing_layout_core(uint8_t *memory,
    uint16_t data_segment, uint16_t width_pixels, uint16_t height_pixels,
    uint16_t origin, uint16_t flags, const LmnRasterBus *bus) {
    uint16_t pitch;
    uint32_t product;
    LmnDrawingLayoutResult out;

    write_word(memory,bus,data_segment,SEG09A9_DrawingWidthPixels,
               width_pixels,flags);
    write_word(memory,bus,data_segment,SEG09A9_DrawingHeight,
               height_pixels,flags);
    write_word(memory,bus,data_segment,SEG09A9_DrawingOrigin,origin,flags);

    pitch=width_pixels;
#if LAYOUT_MUTATION == 1
    pitch=(uint16_t)(pitch+7u);
#endif
    pitch=(uint16_t)(pitch>>1);flags=shr_one_flags(flags,
        (uint16_t)(width_pixels),pitch);
#if LAYOUT_MUTATION == 1
    pitch=(uint16_t)(pitch>>1);
    pitch=(uint16_t)(pitch>>1);
#else
    pitch=(uint16_t)(pitch>>1);flags=shr_one_flags(flags,(uint16_t)(width_pixels>>1),pitch);
    pitch=(uint16_t)(pitch>>1);flags=shr_one_flags(flags,(uint16_t)(width_pixels>>2),pitch);
#endif
    write_word(memory,bus,data_segment,SEG09A9_DrawingPitchBytes,pitch,flags);

#if LAYOUT_MUTATION == 2
    product=(uint32_t)pitch*(uint16_t)(height_pixels-1u);
#elif LAYOUT_MUTATION == 3
    product=(uint32_t)width_pixels*height_pixels;
#else
    product=(uint32_t)pitch*height_pixels;
#endif
    out.value=(uint16_t)product;
    out.product_high=(uint16_t)(product>>16);
    /* MUL defines CF and OF only; all other arithmetic flags are undefined. */
    out.flags=(uint16_t)((flags & (uint16_t)~(CF|OF)) |
        (out.product_high ? (CF|OF) : 0u));
    out.pitch_bytes=pitch;
    out.extent_bytes=out.value;
    write_word(memory,bus,data_segment,SEG09A9_DrawingExtentBytes,
               out.extent_bytes,out.flags);
    return out;
}

void lmn_set_drawing_layout_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus) {
    LmnDrawingLayoutResult out=lmn_set_drawing_layout_core(memory,regs->ds,
        regs->ax,regs->bx,regs->dx,regs->flags,bus);
    uint16_t stack_offset=regs->sp;

    regs->ax=out.value;
    regs->dx=out.product_high;
    regs->flags=out.flags;
    regs->ip=read_word_at(memory,bus,physical(regs->ss,stack_offset),regs->flags);
    stack_offset=(uint16_t)(stack_offset+2u);
    regs->sp=stack_offset;
    regs->cs=read_word_at(memory,bus,physical(regs->ss,stack_offset),regs->flags);
    stack_offset=(uint16_t)(stack_offset+2u);
    regs->sp=stack_offset;
}
