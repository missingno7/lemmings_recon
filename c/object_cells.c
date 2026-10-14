#include "object_cells.h"
#include "lemmings_sym.h"

#ifndef CELL_MUTATION
#define CELL_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800, ARITH=0x08d5 };

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

static uint16_t read_be16(const uint8_t *memory, uint16_t segment,
                          uint16_t offset) {
    return (uint16_t)(((uint16_t)read8(memory, segment, offset) << 8) |
        read8(memory, segment, (uint16_t)(offset+1u)));
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

static uint16_t pop16(const uint8_t *memory, uint16_t segment, uint16_t *sp) {
    uint16_t value=read16(memory, segment, *sp);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

static uint16_t inc16(uint16_t value) {
    return (uint16_t)(value+1u);
}

static uint16_t add_di_flags(uint16_t flags, uint16_t left, uint16_t right) {
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

static uint16_t dec16_flags(uint16_t flags, uint16_t value) {
    uint16_t result=(uint16_t)(value-1u);
    uint16_t arithmetic=(uint16_t)((result==0 ? ZF:0) |
        ((result&0x8000u) ? SF:0) |
        (((value^1u^result)&0x0010u) ? AF:0) |
        (value==0x8000u ? OF:0));
    unsigned ones=0;
    unsigned bit;
    for(bit=0;bit<8;++bit)ones+=(result>>bit)&1u;
    if((ones&1u)==0)arithmetic|=PF;
    /* DEC preserves CF from the preceding ADD DI,8. */
    return (uint16_t)((flags&(uint16_t)~(ARITH^CF))|arithmetic);
}

LmnObjectCellsResult lmn_write_object_interaction_cells_core(
    uint8_t *memory, const LmnObjectCellsCall *call) {
    uint16_t ds=call->data_segment;
    uint16_t ss=call->stack_segment;
    uint16_t sp=call->stack_offset;
    uint16_t bx=call->cell_cursor;
    uint16_t flags=call->flags;
    uint16_t ax=0, cx=0x0010u, dx=0, si=0;
    uint16_t di=SEG09A9_LevelObjectDefinitions;
    uint16_t bp=0;

    while(cx!=0) {
        uint16_t type=read_be16(memory, ds, (uint16_t)(di+4u));
        uint32_t product=(uint32_t)type*0x001cu;
        ax=(uint16_t)product;
        dx=(uint16_t)(product>>16);
        si=(uint16_t)(SEG09A9_GroundResourceBuffer+ax);

#if CELL_MUTATION == 3
        /* Test mutant: incorrectly clamp unchecked template selection. */
        if(type>15u) {
            type=15u;
            product=(uint32_t)type*0x001cu;
            ax=(uint16_t)product;
            dx=(uint16_t)(product>>16);
            si=(uint16_t)(SEG09A9_GroundResourceBuffer+ax);
        }
#endif

        ax=read_be16(memory, ds, di);
        if(ax!=0) {
            uint16_t y;
            uint16_t width;
            uint16_t height;
            uint16_t kind;

            ax=(uint16_t)((ax>>2)+read16(memory, ds,
                (uint16_t)(si+0x000eu)));
            y=read_be16(memory, ds, (uint16_t)(di+2u));
            bx=(uint16_t)((y>>2)+read16(memory, ds,
                (uint16_t)(si+0x0010u)));
            bx=(uint16_t)(bx-1u);

            sp=push16(memory, ss, sp, ax);
            product=(uint32_t)0x01a0u*bx;
            ax=(uint16_t)product;
            dx=(uint16_t)(product>>16);
            bx=ax;
            ax=pop16(memory, ss, &sp);
            bx=(uint16_t)(bx+ax);
            bx=(uint16_t)(bx+SEG143E_InteractionCellMapBase);

            ax=(uint16_t)(bp<<4);
            kind=read8(memory, ds, (uint16_t)(si+0x0014u));
            ax=(uint16_t)((ax&0xff00u) |
                (uint8_t)((uint8_t)ax | (uint8_t)kind));
            width=read8(memory, ds, (uint16_t)(si+0x0012u));
            height=read8(memory, ds, (uint16_t)(si+0x0013u));
            dx=(uint16_t)((width<<8)|height);

            do {
                sp=push16(memory, ss, sp, dx);
                sp=push16(memory, ss, sp, bx);
#if CELL_MUTATION == 2
                uint16_t saved_bx=bx;
                uint16_t saved_dx=dx;
#endif
                {
                    uint8_t dh=(uint8_t)(dx>>8);
                    do {
                        write8(memory, ss, bx, (uint8_t)ax);
                        bx=inc16(bx);
                        dh=(uint8_t)(dh-1u);
#if CELL_MUTATION == 1
                        /* Test mutant: zero width incorrectly writes no cells. */
                        if(width==0)dh=0;
#endif
                    } while(dh!=0);
                }
#if CELL_MUTATION == 2
                (void)pop16(memory, ss, &sp);
                (void)pop16(memory, ss, &sp);
                bx=saved_bx;
                dx=saved_dx;
#else
                bx=pop16(memory, ss, &sp);
                dx=pop16(memory, ss, &sp);
#endif
                bx=(uint16_t)(bx+0x01a0u);
                dx=(uint16_t)((dx&0xff00u) |
                    (uint8_t)((uint8_t)dx-1u));
            } while((uint8_t)dx!=0);
        }

        di=(uint16_t)(di+8u);
        /* The original ADD is performed before DI changes. */
        flags=add_di_flags(flags, (uint16_t)(di-8u), 8u);
        ++bp;
        cx=(uint16_t)(cx-1u);
        flags=dec16_flags(flags, (uint16_t)(cx+1u));
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

void lmn_write_object_interaction_cells_adapter(uint8_t *memory, LmnRegs *r) {
    LmnObjectCellsCall call={r->ds, r->ss, r->sp, r->bx, r->flags};
    LmnObjectCellsResult result=
        lmn_write_object_interaction_cells_core(memory, &call);
    uint32_t address=physical(r->ss, result.stack_offset);

    r->ax=result.value;
    r->bx=result.cell_cursor;
    r->cx=result.remaining_records;
    r->dx=result.dimension_state;
    r->si=result.template_cursor;
    r->di=result.definition_cursor;
    r->bp=result.object_ordinal;
    r->sp=result.stack_offset;
    r->flags=result.flags;
    /* The caller's RET remains live and is read after all map writes. */
    r->ip=(uint16_t)(memory[address] |
        ((uint16_t)memory[(address+1u)&0xfffffu] << 8));
    r->sp=(uint16_t)(r->sp+2u);
}
