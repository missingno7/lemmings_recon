#include "object_cells_bus.h"
#include "lemmings_sym.h"

#ifndef OBJECT_CELLS_BUS_MUTATION
#define OBJECT_CELLS_BUS_MUTATION 0
#endif

enum {
    CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040, SF=0x0080,
    DF=0x0400, OF=0x0800,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_at(uint8_t *memory, uint32_t address,
                       uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_at(uint8_t *memory, uint32_t address, uint8_t value,
                     uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address]=value;
}

static uint8_t read8(uint8_t *memory, uint16_t segment, uint16_t offset,
                     uint16_t flags, const LmnRasterBus *bus) {
    return read_at(memory, physical(segment, offset), flags, bus);
}

/* A word is two physically adjacent bytes. Its high byte does not wrap the
   segment offset when offset is FFFF. */
static uint16_t read16(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_at(memory,address,flags,bus);
    uint8_t high=read_at(memory,address+1u,flags,bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

/* The original big-endian words are two byte instructions. Each effective
   offset wraps independently before its physical address is formed. */
static uint16_t read_be16(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint8_t high=read8(memory,segment,offset,flags,bus);
    uint8_t low=read8(memory,segment,(uint16_t)(offset+1u),flags,bus);
    return (uint16_t)(((uint16_t)high << 8) | low);
}

static void write8(uint8_t *memory, uint16_t segment, uint16_t offset,
                   uint8_t value, uint16_t flags, const LmnRasterBus *bus) {
    write_at(memory,physical(segment,offset),value,flags,bus);
}

static void write16(uint8_t *memory, uint16_t segment, uint16_t offset,
                    uint16_t value, uint16_t flags,
                    const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    write_at(memory,address,(uint8_t)value,flags,bus);
    write_at(memory,address+1u,(uint8_t)(value>>8),flags,bus);
}

static uint16_t push16(uint8_t *memory, uint16_t segment, uint16_t sp,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    sp=(uint16_t)(sp-2u);
    write16(memory,segment,sp,value,flags,bus);
    return sp;
}

static uint16_t pop16(uint8_t *memory, uint16_t segment, uint16_t *sp,
                      uint16_t flags, const LmnRasterBus *bus) {
    uint16_t value=read16(memory,segment,*sp,flags,bus);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

static unsigned parity_even(uint8_t value) {
    unsigned ones=0;
    unsigned bit;
    for(bit=0;bit<8;++bit) ones+=(value>>bit)&1u;
    return (ones&1u)==0;
}

static uint16_t logic_flags(uint16_t flags, uint16_t value) {
    uint16_t arithmetic=(uint16_t)((value==0 ? ZF:0) |
        ((value&0x8000u) ? SF:0) | (parity_even((uint8_t)value) ? PF:0));
    /* AF is undefined after AND/OR and remains an explicit unknown. */
    return (uint16_t)((flags&(uint16_t)~LOGIC)|arithmetic);
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    uint16_t arithmetic=(uint16_t)((value==0 ? ZF:0) |
        ((value&0x80u) ? SF:0) | (parity_even(value) ? PF:0));
    return (uint16_t)((flags&(uint16_t)~LOGIC)|arithmetic);
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t wide=(uint32_t)left+right;
    uint16_t value=(uint16_t)wide;
    uint16_t arithmetic=(uint16_t)((wide>0xffffu ? CF:0) |
        (value==0 ? ZF:0) | ((value&0x8000u) ? SF:0) |
        (((left^right^value)&0x0010u) ? AF:0) |
        (((~(left^right)&(left^value))&0x8000u) ? OF:0) |
        (parity_even((uint8_t)value) ? PF:0));
    return (uint16_t)((flags&(uint16_t)~ARITH)|arithmetic);
}

static uint16_t dec16_flags(uint16_t flags, uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t arithmetic=(uint16_t)((value==0 ? ZF:0) |
        ((value&0x8000u) ? SF:0) |
        (((before^1u^value)&0x0010u) ? AF:0) |
        (before==0x8000u ? OF:0) |
        (parity_even((uint8_t)value) ? PF:0));
    return (uint16_t)((flags&(uint16_t)~(ARITH^CF))|arithmetic);
}

static uint16_t inc16_flags(uint16_t flags, uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t arithmetic=(uint16_t)((value==0 ? ZF:0) |
        ((value&0x8000u) ? SF:0) |
        (((before^1u^value)&0x0010u) ? AF:0) |
        (before==0x7fffu ? OF:0) |
        (parity_even((uint8_t)value) ? PF:0));
    return (uint16_t)((flags&(uint16_t)~(ARITH^CF))|arithmetic);
}

static uint16_t dec8_flags(uint16_t flags, uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t arithmetic=(uint16_t)((value==0 ? ZF:0) |
        ((value&0x80u) ? SF:0) |
        (((before^1u^value)&0x10u) ? AF:0) |
        (before==0x80u ? OF:0) |
        (parity_even(value) ? PF:0));
    return (uint16_t)((flags&(uint16_t)~(ARITH^CF))|arithmetic);
}

static uint16_t shr1_flags(uint16_t flags, uint16_t before) {
    uint16_t value=(uint16_t)(before>>1);
    uint16_t defined=(uint16_t)((before&1u ? CF:0) |
        ((before&0x8000u) ? OF:0) | (value==0 ? ZF:0) |
        ((value&0x8000u) ? SF:0) |
        (parity_even((uint8_t)value) ? PF:0));
    uint16_t mask=(uint16_t)(CF|PF|ZF|SF|OF);
    return (uint16_t)((flags&(uint16_t)~mask)|defined);
}

static uint16_t shl1_flags(uint16_t flags, uint16_t before) {
    uint16_t value=(uint16_t)(before<<1);
    uint16_t carry=(before&0x8000u) ? CF:0;
    uint16_t overflow=(((value&0x8000u)!=0) != (carry!=0)) ? OF:0;
    uint16_t defined=(uint16_t)(carry|overflow|(value==0 ? ZF:0) |
        ((value&0x8000u) ? SF:0) |
        (parity_even((uint8_t)value) ? PF:0));
    uint16_t mask=(uint16_t)(CF|PF|ZF|SF|OF);
    return (uint16_t)((flags&(uint16_t)~mask)|defined);
}

static uint16_t mul_flags(uint16_t flags, uint32_t product) {
    uint16_t defined=(product>>16) ? (uint16_t)(CF|OF):0;
    return (uint16_t)((flags&(uint16_t)~(CF|OF))|defined);
}

LmnObjectCellsResult lmn_write_object_interaction_cells_bus_core(
    uint8_t *memory, const LmnObjectCellsCall *call, const LmnRasterBus *bus) {
    uint16_t ds=call->data_segment;
    uint16_t ss=call->stack_segment;
    uint16_t sp=call->stack_offset;
    uint16_t bx=call->cell_cursor;
    uint16_t flags=call->flags;
    uint16_t ax=0,cx=0x0010u,dx=0,si=0;
    uint16_t di=SEG09A9_LevelObjectDefinitions;
    uint16_t bp=0;

    /* XOR BP,BP at 37C9 precedes the first definition-byte reads. */
    flags=logic_flags(flags,0);

    while(cx!=0) {
        uint16_t type=read_be16(memory,ds,(uint16_t)(di+4u),flags,bus);
        uint32_t product=(uint32_t)type*0x001cu;
        ax=(uint16_t)product;
        dx=(uint16_t)(product>>16);
        flags=mul_flags(flags,product);
        si=(uint16_t)(SEG09A9_GroundResourceBuffer+ax);
#if OBJECT_CELLS_BUS_MUTATION != 4
        flags=add16_flags(flags,SEG09A9_GroundResourceBuffer,ax);
#endif

#if OBJECT_CELLS_BUS_MUTATION == 3
        /* Test mutant: clamp the original unchecked template type. */
        if(type>15u) {
            type=15u;
            product=(uint32_t)type*0x001cu;
            ax=(uint16_t)product;
            dx=(uint16_t)(product>>16);
            flags=mul_flags(flags,product);
            si=(uint16_t)(SEG09A9_GroundResourceBuffer+ax);
            flags=add16_flags(flags,SEG09A9_GroundResourceBuffer,ax);
        }
#endif

        ax=read_be16(memory,ds,di,flags,bus);
        flags=logic_flags(flags,ax); /* AND AX,AX */
        if(ax!=0) {
            uint16_t y;
            uint16_t width;
            uint16_t height;
            uint16_t kind;

            {
                uint16_t before=ax;
                ax=(uint16_t)(before>>1);
                flags=shr1_flags(flags,before);
            }
            {
                uint16_t before=ax;
                ax=(uint16_t)(before>>1);
                flags=shr1_flags(flags,before);
            }
            {
                uint16_t source=read16(memory,ds,(uint16_t)(si+0x000eu),flags,bus);
                uint16_t before=ax;
                ax=(uint16_t)(ax+source);
                flags=add16_flags(flags,before,source);
            }
            y=read_be16(memory,ds,(uint16_t)(di+2u),flags,bus);
            bx=(uint16_t)(y>>1); flags=shr1_flags(flags,y);
            {
                uint16_t before=bx;
                bx=(uint16_t)(before>>1);
                flags=shr1_flags(flags,before);
            }
            {
                uint16_t source=read16(memory,ds,(uint16_t)(si+0x0010u),flags,bus);
                uint16_t before=bx;
                bx=(uint16_t)(bx+source);
                flags=add16_flags(flags,before,source);
            }
            {
                uint16_t before=bx;
                bx=(uint16_t)(bx-1u);
                flags=dec16_flags(flags,before);
            }
            sp=push16(memory,ss,sp,ax,flags,bus);
            ax=0x01a0u;
            product=(uint32_t)ax*bx;
            ax=(uint16_t)product;
            dx=(uint16_t)(product>>16);
            flags=mul_flags(flags,product);
            bx=ax;
            ax=pop16(memory,ss,&sp,flags,bus);
            {
                uint16_t before=bx;
                bx=(uint16_t)(bx+ax);
                flags=add16_flags(flags,before,ax);
            }
            {
                uint16_t before=bx;
                bx=(uint16_t)(bx+SEG143E_InteractionCellMapBase);
                flags=add16_flags(flags,before,SEG143E_InteractionCellMapBase);
            }
            ax=bp;
            {
                unsigned shift;
                for(shift=0;shift<4;++shift) {
                    uint16_t before=ax;
                    ax=(uint16_t)(before<<1);
                    flags=shl1_flags(flags,before);
                }
            }
            kind=read8(memory,ds,(uint16_t)(si+0x0014u),flags,bus);
            ax=(uint16_t)((ax&0xff00u) | ((uint8_t)ax | kind));
            flags=logic8_flags(flags,(uint8_t)ax); /* OR AL,[SI+14] */
            width=read8(memory,ds,(uint16_t)(si+0x0012u),flags,bus);
            height=read8(memory,ds,(uint16_t)(si+0x0013u),flags,bus);
            dx=(uint16_t)((width<<8)|height);

            do {
                uint8_t dh=(uint8_t)(dx>>8);
                sp=push16(memory,ss,sp,dx,flags,bus);
                sp=push16(memory,ss,sp,bx,flags,bus);
#if OBJECT_CELLS_BUS_MUTATION == 2
                /* Test mutant: discard the original live row-save reads. */
                {
                    uint16_t saved_dx=dx;
                    uint16_t saved_bx=bx;
#endif
                    do {
                        write8(memory,ss,bx,(uint8_t)ax,flags,bus);
                        {
                            uint16_t before=bx;
                            bx=(uint16_t)(bx+1u);
                            flags=inc16_flags(flags,before);
                        }
                        {
                            uint8_t before=dh;
                            dh=(uint8_t)(dh-1u);
#if OBJECT_CELLS_BUS_MUTATION == 1
                            /* Test mutant: zero width incorrectly exits. */
                            if(width==0) dh=0;
#endif
                            flags=dec8_flags(flags,before);
                        }
                    } while(dh!=0);
#if OBJECT_CELLS_BUS_MUTATION == 2
                    (void)pop16(memory,ss,&sp,flags,bus);
                    (void)pop16(memory,ss,&sp,flags,bus);
                    bx=saved_bx;
                    dx=saved_dx;
                }
#else
                bx=pop16(memory,ss,&sp,flags,bus);
                dx=pop16(memory,ss,&sp,flags,bus);
#endif
                {
                    uint16_t before=bx;
                    bx=(uint16_t)(bx+0x01a0u);
                    flags=add16_flags(flags,before,0x01a0u);
                }
                {
                    uint8_t before=(uint8_t)dx;
                    dx=(uint16_t)((dx&0xff00u) | (uint8_t)(before-1u));
                    flags=dec8_flags(flags,before);
                }
            } while((uint8_t)dx!=0);
        }

        {
            uint16_t before=di;
            di=(uint16_t)(di+8u);
            flags=add16_flags(flags,before,8u);
        }
        {
            uint16_t before=bp;
            bp=(uint16_t)(bp+1u);
            flags=inc16_flags(flags,before);
        }
        {
            uint16_t before=cx;
            cx=(uint16_t)(cx-1u);
            flags=dec16_flags(flags,before);
        }
    }

    {
        LmnObjectCellsResult result;
        result.value=ax;
        result.cell_cursor=bx;
        result.remaining_records=cx;
        result.dimension_state=dx;
        result.template_cursor=si;
        result.definition_cursor=di;
        result.object_ordinal=bp;
        result.stack_offset=sp;
        result.flags=flags;
        return result;
    }
}

void lmn_write_object_interaction_cells_bus_adapter(
    uint8_t *memory, LmnRegs *regs, const LmnRasterBus *bus) {
    LmnObjectCellsCall call={regs->ds,regs->ss,regs->sp,regs->bx,regs->flags};
    LmnObjectCellsResult result=
        lmn_write_object_interaction_cells_bus_core(memory,&call,bus);
    regs->ax=result.value;
    regs->bx=result.cell_cursor;
    regs->cx=result.remaining_records;
    regs->dx=result.dimension_state;
    regs->si=result.template_cursor;
    regs->di=result.definition_cursor;
    regs->bp=result.object_ordinal;
    regs->sp=result.stack_offset;
    regs->flags=result.flags;
    /* RET is a live word, sequenced after every leaf store and read via SS. */
    regs->ip=read16(memory,regs->ss,regs->sp,regs->flags,bus);
    regs->sp=(uint16_t)(regs->sp+2u);
}
