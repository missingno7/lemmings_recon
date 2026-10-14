#include "steel_cells.h"
#include "lemmings_sym.h"

#ifndef STEEL_MUTATION
#define STEEL_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, OF=0x0800, ARITH=0x08d5 };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read8(const uint8_t *memory, uint16_t segment,
                     uint16_t offset) {
    return memory[physical(segment, offset)];
}

static uint16_t read16(const uint8_t *memory, uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment, offset);
    return (uint16_t)(memory[address] |
        ((uint16_t)memory[(address+1u)&0xfffffu] << 8));
}

static void write8(uint8_t *memory, uint16_t segment, uint16_t offset,
                   uint8_t value) {
    memory[physical(segment, offset)]=value;
}

static void write16(uint8_t *memory, uint16_t segment, uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment, offset);
    memory[address]=(uint8_t)value;
    memory[(address+1u)&0xfffffu]=(uint8_t)(value>>8);
}

static uint16_t push16(uint8_t *memory, uint16_t segment, uint16_t sp,
                       uint16_t value) {
    sp=(uint16_t)(sp-2u);
    write16(memory, segment, sp, value);
    return sp;
}

static uint16_t pop16(const uint8_t *memory, uint16_t segment,
                      uint16_t *sp) {
    uint16_t value=read16(memory, segment, *sp);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t wide=(uint32_t)left+right;
    uint16_t value=(uint16_t)wide;
    uint16_t arithmetic=(uint16_t)((wide>0xffffu ? CF:0) |
        (value==0 ? ZF:0) | ((value&0x8000u) ? SF:0) |
        (((left^right^value)&0x0010u) ? AF:0) |
        (((~(left^right)&(left^value))&0x8000u) ? OF:0));
    unsigned ones=0;
    unsigned bit;
    for(bit=0;bit<8;++bit)ones+=(value>>bit)&1u;
    if((ones&1u)==0)arithmetic|=PF;
    return (uint16_t)((flags&(uint16_t)~ARITH)|arithmetic);
}

LmnSteelInteractionCellsResult lmn_write_steel_interaction_cells_core(
    uint8_t *memory, const LmnSteelInteractionCellsCall *call) {
    uint16_t di=SEG09A9_LevelSteelDefinitions;
    uint16_t cx=0x20u;
    uint16_t ax=0,bx=0,dx=0,sp=call->stack_offset;
    uint16_t flags=call->flags;

    while(cx) {
        uint8_t byte0=read8(memory, call->data_segment, di);
        uint8_t byte1=read8(memory, call->data_segment, (uint16_t)(di+1u));
        uint8_t byte2=read8(memory, call->data_segment, (uint16_t)(di+2u));
        uint8_t byte3=read8(memory, call->data_segment, (uint16_t)(di+3u));
        uint16_t first=(uint16_t)(((uint16_t)byte0<<8)|byte1);
        uint16_t second=(uint16_t)(((uint16_t)byte2<<8)|byte3);
        uint16_t presence=(uint16_t)(first|second);
#if STEEL_MUTATION == 1
        /* Test mutation: byte 3 is erroneously absent from the zero check. */
        presence=(uint16_t)(first|((uint16_t)byte2<<8));
#endif
        ax=first;
        dx=second;
        bx=(uint16_t)(first|second);
        if(presence!=0u) {
            uint8_t dimension_byte=byte2;
            uint8_t dl=(uint8_t)(dimension_byte&0x0fu);
            uint8_t dh=(uint8_t)((dimension_byte>>4)&0x0fu);
            uint8_t row=(uint8_t)(byte1&0x7fu);
            uint16_t x=(uint16_t)(((uint16_t)byte0<<1)|(byte1>>7));
            uint32_t product;

            dx=(uint16_t)(((uint16_t)dh<<8)|dl);
            sp=push16(memory, call->stack_segment, sp, dx);

#if STEEL_MUTATION == 2
            /* Test mutation: drops byte 1 bit 7 from the X coordinate. */
            x=(uint16_t)((uint16_t)byte0<<1);
#endif
            ax=x;
            sp=push16(memory, call->stack_segment, sp, ax);
            product=(uint32_t)0x01a0u*row;
            ax=(uint16_t)product;
            dx=(uint16_t)(product>>16);
            bx=pop16(memory, call->stack_segment, &sp);
            bx=(uint16_t)(bx+ax);
            bx=(uint16_t)(bx+SEG143E_InteractionCellMapBase);
            dx=pop16(memory, call->stack_segment, &sp);
            dx=(uint16_t)(dx+0x0101u);

            do {
                sp=push16(memory, call->stack_segment, sp, dx);
                sp=push16(memory, call->stack_segment, sp, bx);
                do {
                    write8(memory, call->stack_segment, bx, 0x09u);
                    bx=(uint16_t)(bx+1u);
                    dh=(uint8_t)(dx>>8);
                    dh=(uint8_t)(dh-1u);
                    dx=(uint16_t)(((uint16_t)dh<<8)|(dx&0x00ffu));
                } while(dh!=0u);
                bx=pop16(memory, call->stack_segment, &sp);
                dx=pop16(memory, call->stack_segment, &sp);
#if STEEL_MUTATION == 3
                bx=(uint16_t)(bx+0x019fu);
#else
                bx=(uint16_t)(bx+0x01a0u);
#endif
                dl=(uint8_t)dx;
                dl=(uint8_t)(dl-1u);
                dx=(uint16_t)((dx&0xff00u)|dl);
            } while(dl!=0u);
        }

        di=(uint16_t)(di+4u);
        flags=add16_flags(flags, di-4u, 4u);
        cx=(uint16_t)(cx-1u);
    }

    {
        LmnSteelInteractionCellsResult out={
            .value=ax,
            .cell_cursor=bx,
            .records_remaining=cx,
            .dimensions=dx,
            .definition_cursor=di,
            .stack_offset=sp,
            .flags=flags
        };
        return out;
    }
}

void lmn_write_steel_interaction_cells_adapter(uint8_t *memory, LmnRegs *r) {
    LmnSteelInteractionCellsCall call={r->ds,r->ss,r->sp,r->flags};
    LmnSteelInteractionCellsResult out=
        lmn_write_steel_interaction_cells_core(memory, &call);
    uint32_t address=physical(r->ss, out.stack_offset);

    r->ax=out.value;
    r->bx=out.cell_cursor;
    r->cx=out.records_remaining;
    r->dx=out.dimensions;
    r->di=out.definition_cursor;
    r->sp=out.stack_offset;
    r->flags=out.flags;
    r->ip=(uint16_t)(memory[address] |
        ((uint16_t)memory[(address+1u)&0xfffffu] << 8));
    r->sp=(uint16_t)(r->sp+2u);
}
