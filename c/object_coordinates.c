#include "object_coordinates.h"
#include "lemmings_sym.h"

#ifndef COORD_MUTATION
#define COORD_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800, ARITH=0x08d5 };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t get8(const uint8_t *memory, uint16_t segment, uint16_t offset) {
    return memory[physical(segment, offset)];
}

static uint16_t get16(const uint8_t *memory, uint16_t segment, uint16_t offset) {
    uint32_t address=physical(segment, offset);
    return (uint16_t)(memory[address] |
        ((uint16_t)memory[(address+1u)&0xfffffu] << 8));
}

static uint16_t get_be16(const uint8_t *memory, uint16_t segment, uint16_t offset) {
    return (uint16_t)(((uint16_t)get8(memory, segment, offset) << 8) |
        get8(memory, segment, (uint16_t)(offset+1u)));
}

static void put16(uint8_t *memory, uint16_t segment, uint16_t offset, uint16_t value) {
    uint32_t address=physical(segment, offset);
    memory[address]=(uint8_t)value;
    memory[(address+1u)&0xfffffu]=(uint8_t)(value >> 8);
}

static uint16_t szp16(uint16_t value) {
    unsigned parity=0;
    unsigned bit;
    uint16_t out=0;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t cmp16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint16_t value=(uint16_t)(left-right);
    uint16_t out=szp16(value);
    if(left<right)out|=CF;
    if((left^right^value)&0x0010u)out|=AF;
    if(((left^right)&(left^value)&0x8000u)!=0)out|=OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | out);
}

static uint16_t and16_flags(uint16_t flags, uint16_t value) {
    /* 38D6 is AND BP,BP. AF is architecturally undefined for this path. */
    return (uint16_t)((flags & (uint16_t)~ARITH) | szp16(value));
}

LmnObjectCoordinatesResult lmn_collect_type_one_object_coordinates_core(
    uint8_t *memory, const LmnObjectCoordinatesCall *call) {
    uint16_t ds=call->data_segment;
    uint16_t si=SEG09A9_LevelObjectDefinitions;
    uint16_t bx=SEG09A9_TypeOneObjectCoordinates;
    uint16_t cx=0x20u;
    uint16_t bp=0;
    uint16_t ax=0;
    uint16_t flags=call->flags;

    while(cx) {
        uint16_t type=get_be16(memory, ds, (uint16_t)(si+4u));
        ax=type;
        if(type==1u) {
            uint16_t x=get_be16(memory, ds, si);
            uint16_t y=get_be16(memory, ds, (uint16_t)(si+2u));
            x=(uint16_t)(x+24u);
            y=(uint16_t)(y+30u);
#if COORD_MUTATION == 3
            /* Test mutant: incorrectly treats a zero first word as absent. */
            if(get_be16(memory, ds, si)!=0u)
#endif
            {
#if COORD_MUTATION == 2
                if(bp<4u) {
#endif
                    put16(memory, ds, bx, x);
                    put16(memory, ds, (uint16_t)(bx+2u), y);
                    bx=(uint16_t)(bx+4u);
                    ++bp;
#if COORD_MUTATION == 2
                }
#endif
            }
            /* The body leaves AX as the wrapped Y value after its final store. */
            ax=y;
        }
        si=(uint16_t)(si+8u);
        --cx;
    }

    if(bp==0u) {
        ax=0x0100u;
        cx=0x0010u;
        put16(memory, ds, bx, ax);
        put16(memory, ds, (uint16_t)(bx+2u), cx);
        put16(memory, ds, (uint16_t)(bx+4u), ax);
        put16(memory, ds, (uint16_t)(bx+6u), cx);
        put16(memory, ds, (uint16_t)(bx+8u), ax);
        put16(memory, ds, (uint16_t)(bx+0x0au), cx);
#if COORD_MUTATION == 1
        /* Test mutant: repairs the original repeated +0A destination. */
        put16(memory, ds, (uint16_t)(bx+0x0cu), ax);
#else
        put16(memory, ds, (uint16_t)(bx+0x0au), ax);
#endif
        put16(memory, ds, (uint16_t)(bx+0x0eu), cx);
        flags=and16_flags(flags, bp);
    } else {
#if COORD_MUTATION == 2
        /* `bp` is the intentionally clamped match count in this mutant. */
#endif
        if(bp==1u) {
            ax=get16(memory, ds, (uint16_t)(bx-4u));
            cx=get16(memory, ds, (uint16_t)(bx-2u));
            put16(memory, ds, bx, ax);
            put16(memory, ds, (uint16_t)(bx+2u), cx);
            put16(memory, ds, (uint16_t)(bx+4u), ax);
            put16(memory, ds, (uint16_t)(bx+6u), cx);
            put16(memory, ds, (uint16_t)(bx+8u), ax);
            put16(memory, ds, (uint16_t)(bx+0x0au), cx);
            flags=cmp16_flags(flags, bp, 1u);
        } else if(bp==2u) {
            ax=get16(memory, ds, (uint16_t)(bx-4u));
            cx=get16(memory, ds, (uint16_t)(bx-2u));
            put16(memory, ds, bx, ax);
            put16(memory, ds, (uint16_t)(bx+2u), cx);
            ax=get16(memory, ds, (uint16_t)(bx-8u));
            cx=get16(memory, ds, (uint16_t)(bx-6u));
            put16(memory, ds, (uint16_t)(bx+4u), ax);
            put16(memory, ds, (uint16_t)(bx+6u), cx);
            flags=cmp16_flags(flags, bp, 2u);
        } else if(bp==3u) {
            ax=get16(memory, ds, (uint16_t)(bx-8u));
            cx=get16(memory, ds, (uint16_t)(bx-6u));
            put16(memory, ds, bx, ax);
            put16(memory, ds, (uint16_t)(bx+2u), cx);
            flags=cmp16_flags(flags, bp, 3u);
        } else {
            flags=cmp16_flags(flags, bp, 3u);
        }
    }

    {
        LmnObjectCoordinatesResult out;
        out.value=ax;
        out.count=cx;
        out.definition_cursor=si;
        out.output_cursor=bx;
        out.selected_count=bp;
        out.flags=flags;
        return out;
    }
}

void lmn_collect_type_one_object_coordinates_adapter(uint8_t *memory, LmnRegs *r) {
    LmnObjectCoordinatesCall call={r->ds,r->flags};
    LmnObjectCoordinatesResult out=
        lmn_collect_type_one_object_coordinates_core(memory, &call);
    uint32_t stack=physical(r->ss, r->sp);

    r->ax=out.value;
    r->bx=out.output_cursor;
    r->cx=out.count;
    r->si=out.definition_cursor;
    r->bp=out.selected_count;
    r->flags=out.flags;
    /* RET reads the word after all output writes, so DS:BX may alias SS:SP. */
    r->ip=(uint16_t)(memory[stack] |
        ((uint16_t)memory[(stack+1u)&0xfffffu] << 8));
    r->sp=(uint16_t)(r->sp+2u);
}
