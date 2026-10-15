#include "object_graphics.h"
#include "lemmings_sym.h"

#ifndef OBJECT_MUTATION
#define OBJECT_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800 };
enum { ARITH=CF|PF|AF|ZF|SF|OF };
enum { LOGIC_DEFINED=CF|PF|ZF|SF|OF };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read8(uint8_t *mem, uint16_t segment, uint16_t offset,
                     uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    if(bus&&bus->read_byte)
        return bus->read_byte(bus->context,mem,address,flags);
    return mem[address];
}

static void write8(uint8_t *mem, uint16_t segment, uint16_t offset,
                   uint8_t value, uint16_t flags,
                   const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    if(bus&&bus->write_byte)
        bus->write_byte(bus->context,mem,address,value,flags);
    else
        mem[address]=value;
}

/* Word accesses use two physically consecutive bytes even at offset FFFF. */
static uint16_t read16(uint8_t *mem, uint16_t segment, uint16_t offset,
                       uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read8(mem,segment,offset,flags,bus);
    uint8_t high;
    if(bus&&bus->read_byte)
        high=bus->read_byte(bus->context,mem,(address+1u)&0xfffffu,flags);
    else
        high=mem[(address+1u)&0xfffffu];
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(uint8_t *mem, uint16_t segment, uint16_t offset,
                    uint16_t value, uint16_t flags,
                    const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    write8(mem,segment,offset,(uint8_t)value,flags,bus);
    if(bus&&bus->write_byte)
        bus->write_byte(bus->context,mem,(address+1u)&0xfffffu,
                        (uint8_t)(value>>8),flags);
    else
        mem[(address+1u)&0xfffffu]=(uint8_t)(value>>8);
}

static uint16_t push16(uint8_t *mem, uint16_t segment, uint16_t sp,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    sp=(uint16_t)(sp-2u);
    write16(mem,segment,sp,value,flags,bus);
    return sp;
}

static uint16_t pop16(uint8_t *mem, uint16_t segment, uint16_t *sp,
                      uint16_t flags, const LmnRasterBus *bus) {
    uint16_t value=read16(mem,segment,*sp,flags,bus);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

static uint16_t and16_flags(uint16_t flags, uint16_t value) {
    uint16_t arithmetic=(value==0 ? ZF:0) | ((value&0x8000u) ? SF:0);
    unsigned bits=0;
    unsigned n;
    for(n=0;n<8;++n)bits+=(value>>n)&1u;
    if((bits&1u)==0)arithmetic|=PF;
    return (uint16_t)((flags&(uint16_t)~LOGIC_DEFINED)|arithmetic);
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t result=(uint32_t)left+right;
    uint16_t value=(uint16_t)result;
    uint16_t arithmetic=(uint16_t)((result>0xffffu ? CF:0) |
        (value==0 ? ZF:0) | ((value&0x8000u) ? SF:0) |
        (((left^right^value)&0x0010u) ? AF:0) |
        (((~(left^right)&(left^value))&0x8000u) ? OF:0));
    unsigned bits=0;
    unsigned n;
    for(n=0;n<8;++n)bits+=(value>>n)&1u;
    if((bits&1u)==0)arithmetic|=PF;
    return (uint16_t)((flags&(uint16_t)~ARITH)|arithmetic);
}

LmnObjectGraphicsResult lmn_copy_object_graphics_bus_core(uint8_t *mem,
    uint16_t data_segment, uint16_t stack_segment, uint16_t stack_offset,
    uint16_t product_high, uint16_t flags, const LmnRasterBus *bus) {
    uint16_t ax=0,bx,cx,si,di,es;

    /* PUSH DS / POP ES are live stack operations, including their memory write. */
    stack_offset=push16(mem,stack_segment,stack_offset,data_segment,flags,bus);
    es=pop16(mem,stack_segment,&stack_offset,flags,bus);
    bx=SEG09A9_LevelObjectDefinitions;
    si=SEG09A9_GroundResourceBuffer;
    di=SEG09A9_LevelObjectGraphicsRecords;
    cx=0x0020;

    do {
        uint8_t active_high=read8(mem,data_segment,bx,flags,bus);
        uint8_t active_low=read8(mem,data_segment,(uint16_t)(bx+1u),flags,bus);
        uint16_t active_word=(uint16_t)(((uint16_t)active_high<<8) | active_low);
        ax=active_word;
        flags=and16_flags(flags,ax);
        if(active_word!=0) {
            uint8_t type_high=read8(mem,data_segment,(uint16_t)(bx+4u),flags,bus);
            uint8_t type_low=read8(mem,data_segment,(uint16_t)(bx+5u),flags,bus);
            uint16_t type=(uint16_t)(((uint16_t)type_high<<8) | type_low);
            uint32_t product;
            uint16_t source_step=(flags&DF) ? 0xffffu:1u;
            uint16_t dest_step=source_step;
            unsigned n;
#if OBJECT_MUTATION == 2
            if(type>37u)type=37u;
#endif
            stack_offset=push16(mem,stack_segment,stack_offset,si,flags,bus);
            stack_offset=push16(mem,stack_segment,stack_offset,cx,flags,bus);
            stack_offset=push16(mem,stack_segment,stack_offset,di,flags,bus);
            cx=0x001c;
            product=(uint32_t)type*cx;
            ax=(uint16_t)product;
            product_high=(uint16_t)(product>>16);
            {
                uint16_t previous_si=si;
                si=(uint16_t)(si+ax);
                flags=add16_flags(flags,previous_si,ax);
            }
#if OBJECT_MUTATION == 3
            source_step=1;
            dest_step=1;
#endif
            for(n=0;n<0x1cu;++n) {
                uint8_t value=read8(mem,data_segment,si,flags,bus);
                write8(mem,es,di,value,flags,bus);
                si=(uint16_t)(si+source_step);
                di=(uint16_t)(di+dest_step);
                cx=(uint16_t)(cx-1u);
            }
            di=pop16(mem,stack_segment,&stack_offset,flags,bus);
            cx=pop16(mem,stack_segment,&stack_offset,flags,bus);
            si=pop16(mem,stack_segment,&stack_offset,flags,bus);
        }
#if OBJECT_MUTATION == 1
        else {
            unsigned n;
            for(n=0;n<0x1cu;++n)
                write8(mem,es,(uint16_t)(di+n),0,flags,bus);
        }
#endif
        bx=(uint16_t)(bx+8u);
        flags=add16_flags(flags,(uint16_t)(bx-8u),8u);
        {
            uint16_t previous_di=di;
            di=(uint16_t)(di+0x1cu);
            flags=add16_flags(flags,previous_di,0x1cu);
        }
        cx=(uint16_t)(cx-1u); /* LOOP changes CX but leaves the ADD flags live. */
    } while(cx!=0);

    {
        LmnObjectGraphicsResult out={
            .value=ax,
            .definition_cursor=bx,
            .count=cx,
            .product_high=product_high,
            .source_cursor=si,
            .output_cursor=di,
            .extra_segment=es,
            .stack_offset=stack_offset,
            .flags=flags
        };
        return out;
    }
}

LmnObjectGraphicsResult lmn_copy_object_graphics_core(uint8_t *mem,
    uint16_t data_segment, uint16_t stack_segment, uint16_t stack_offset,
    uint16_t product_high, uint16_t flags) {
    return lmn_copy_object_graphics_bus_core(mem,data_segment,stack_segment,
        stack_offset,product_high,flags,NULL);
}

void lmn_copy_object_graphics_bus_adapter(uint8_t *mem, LmnRegs *r,
                                          const LmnRasterBus *bus) {
    LmnObjectGraphicsResult out=lmn_copy_object_graphics_bus_core(mem,r->ds,r->ss,
        r->sp,r->dx,r->flags,bus);
    r->ax=out.value;r->bx=out.definition_cursor;r->cx=out.count;
    r->dx=out.product_high;r->si=out.source_cursor;r->di=out.output_cursor;
    r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=read16(mem,r->ss,r->sp,r->flags,bus);
    r->sp=(uint16_t)(r->sp+2u);
}

void lmn_copy_object_graphics_adapter(uint8_t *mem, LmnRegs *r) {
    lmn_copy_object_graphics_bus_adapter(mem,r,NULL);
}
