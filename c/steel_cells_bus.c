#include "steel_cells_bus.h"
#include "lemmings_sym.h"

#ifndef STEEL_BUS_MUTATION
#define STEEL_BUS_MUTATION 0
#endif

enum {
    CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
    SF = 0x0080, OF = 0x0800,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF
};

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read8(uint8_t *memory, uint16_t segment, uint16_t offset,
                     uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static uint8_t read_physical8(uint8_t *memory, uint32_t address,
                              uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write8(uint8_t *memory, uint16_t segment, uint16_t offset,
                   uint8_t value, uint16_t flags,
                   const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static void write_physical8(uint8_t *memory, uint32_t address,
                            uint8_t value, uint16_t flags,
                            const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

/* Machine words are physically contiguous even when the segment offset is FFFF. */
static uint16_t read16(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read8(memory, segment, offset, flags, bus);
    uint8_t high = read_physical8(memory, address + 1u, flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(uint8_t *memory, uint16_t segment, uint16_t offset,
                    uint16_t value, uint16_t flags,
                    const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write8(memory, segment, offset, (uint8_t)value, flags, bus);
    write_physical8(memory, address + 1u, (uint8_t)(value >> 8), flags, bus);
}

static uint16_t push16(uint8_t *memory, uint16_t segment, uint16_t sp,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    sp = (uint16_t)(sp - 2u);
    write16(memory, segment, sp, value, flags, bus);
    return sp;
}

static uint16_t pop16(uint8_t *memory, uint16_t segment, uint16_t *sp,
                      uint16_t flags, const LmnRasterBus *bus) {
    uint16_t value = read16(memory, segment, *sp, flags, bus);
    *sp = (uint16_t)(*sp + 2u);
    return value;
}

static uint16_t parity_flag8(uint8_t value) {
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones += (value >> bit) & 1u;
    return (ones & 1u) == 0 ? PF : 0;
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    uint16_t arithmetic = (value == 0 ? ZF : 0) |
        ((value & 0x80u) ? SF : 0) | parity_flag8(value);
    return (uint16_t)((flags & (uint16_t)~LOGIC) | arithmetic);
}

static uint16_t logic16_flags(uint16_t flags, uint16_t value) {
    uint16_t arithmetic = (value == 0 ? ZF : 0) |
        ((value & 0x8000u) ? SF : 0) | parity_flag8((uint8_t)value);
    return (uint16_t)((flags & (uint16_t)~LOGIC) | arithmetic);
}

static uint16_t xor8_flags(uint16_t flags, uint8_t value) {
    return logic8_flags(flags, value);
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t wide = (uint32_t)left + right;
    uint16_t value = (uint16_t)wide;
    uint16_t arithmetic = (uint16_t)((wide > 0xffffu ? CF : 0) |
        (value == 0 ? ZF : 0) | ((value & 0x8000u) ? SF : 0) |
        (((left ^ right ^ value) & 0x0010u) ? AF : 0) |
        (((~(left ^ right) & (left ^ value)) & 0x8000u) ? OF : 0) |
        parity_flag8((uint8_t)value));
    return (uint16_t)((flags & (uint16_t)~ARITH) | arithmetic);
}

static uint16_t inc16_flags(uint16_t flags, uint16_t left) {
    uint16_t carry = (uint16_t)(flags & CF);
    uint16_t result = add16_flags(flags, left, 1u);
    return (uint16_t)((result & (uint16_t)~CF) | carry);
}

static uint16_t dec8_flags(uint16_t flags, uint8_t left) {
    uint8_t result = (uint8_t)(left - 1u);
    uint16_t arithmetic = (result == 0 ? ZF : 0) |
        ((result & 0x80u) ? SF : 0) |
        (((left ^ 1u ^ result) & 0x10u) ? AF : 0) |
        (left == 0x80u ? OF : 0) | parity_flag8(result);
    uint16_t dec_defined = (uint16_t)(ARITH & (uint16_t)~CF);
    return (uint16_t)((flags & (uint16_t)~dec_defined) | arithmetic);
}

static uint16_t shr8_one_flags(uint16_t flags, uint8_t left) {
    uint8_t result = (uint8_t)(left >> 1);
    uint16_t arithmetic = (left & 1u ? CF : 0) |
        ((left & 0x80u) ? OF : 0) |
        (result == 0 ? ZF : 0) | ((result & 0x80u) ? SF : 0) |
        parity_flag8(result);
    return (uint16_t)((flags & (uint16_t)~LOGIC) | arithmetic);
}

static uint8_t rol8_one(uint16_t *flags, uint8_t value) {
    uint8_t carry = (uint8_t)(value >> 7);
    uint8_t result = (uint8_t)((value << 1) | carry);
    uint16_t overflow = (uint16_t)((((result >> 7) & 1u) ^ carry) ? OF : 0);
    *flags = (uint16_t)((*flags & (uint16_t)~(CF | OF)) |
                        (carry ? CF : 0) | overflow);
    return result;
}

static uint16_t rcl16_one(uint16_t *flags, uint16_t value) {
    uint16_t carry_in = (uint16_t)(*flags & CF);
    uint16_t carry_out = (uint16_t)(value >> 15);
    uint16_t result = (uint16_t)((value << 1) | carry_in);
    uint16_t overflow = (uint16_t)((((result >> 15) & 1u) ^ carry_out) ? OF : 0);
    *flags = (uint16_t)((*flags & (uint16_t)~(CF | OF)) |
                        (carry_out ? CF : 0) | overflow);
    return result;
}

LmnSteelInteractionCellsResult lmn_write_steel_interaction_cells_bus_core(
    uint8_t *memory, const LmnSteelInteractionCellsCall *call,
    const LmnRasterBus *bus) {
    uint16_t di = SEG09A9_LevelSteelDefinitions;
    uint16_t cx = 0x20u;
    uint16_t ax = 0, bx = 0, dx = 0, sp = call->stack_offset;
    uint16_t flags = call->flags;

    while (cx != 0) {
        uint8_t ah = read8(memory, call->data_segment, di, flags, bus);
        uint8_t al = read8(memory, call->data_segment,
                           (uint16_t)(di + 1u), flags, bus);
        uint8_t dh = read8(memory, call->data_segment,
                           (uint16_t)(di + 2u), flags, bus);
        uint8_t dl = read8(memory, call->data_segment,
                           (uint16_t)(di + 3u), flags, bus);
        uint32_t product;

        ax = (uint16_t)(((uint16_t)ah << 8) | al);
        dx = (uint16_t)(((uint16_t)dh << 8) | dl);
        bx = ax;
        bx = (uint16_t)(bx | dx);
        flags = logic16_flags(flags, bx); /* OR BX,DX */

#if STEEL_BUS_MUTATION == 1
        /* Mutation: byte 3 is missing from the record-presence OR. */
        if ((ax | ((uint16_t)dh << 8)) != 0u) {
#else
        if (bx != 0u) {
#endif
            uint16_t old_bx;

            dl = dh;
            dl = (uint8_t)(dl & 0x0fu);
            flags = logic8_flags(flags, dl); /* AND DL,0F */
            for (unsigned shift = 0; shift < 4; ++shift) {
                uint8_t old_dh = dh;
                dh = (uint8_t)(dh >> 1);
                flags = shr8_one_flags(flags, old_dh);
            }
            dh = (uint8_t)(dh & 0x0fu);
            flags = logic8_flags(flags, dh); /* AND DH,0F */
            dx = (uint16_t)(((uint16_t)dh << 8) | dl);
            sp = push16(memory, call->stack_segment, sp, dx, flags, bus);

            bx = (uint16_t)((bx & 0xff00u) | al); /* MOV BL,AL */
            bx = (uint16_t)(bx & 0x00ffu);        /* XOR BH,BH */
            flags = xor8_flags(flags, 0);
            {
                uint8_t old_bl = (uint8_t)bx;
                uint8_t bl = (uint8_t)(old_bl & 0x7fu);
                bx = bl;
                flags = logic8_flags(flags, bl); /* AND BL,7F */
            }

            dl = al;
            al = ah;
            ah = 0;
            ax = al;
            flags = xor8_flags(flags, ah); /* XOR AH,AH */
#if STEEL_BUS_MUTATION == 2
            /* Mutation: lose the packed X coordinate's bit-7 contribution. */
            dl = (uint8_t)(dl & 0x7fu);
#endif
            dl = rol8_one(&flags, dl);
            ax = rcl16_one(&flags, ax);
            sp = push16(memory, call->stack_segment, sp, ax, flags, bus);

            ax = 0x01a0u;
            product = (uint32_t)ax * (uint32_t)bx;
            dx = (uint16_t)(product >> 16);
            /* MUL defines CF and OF only; other arithmetic bits stay opaque. */
            flags = (uint16_t)((flags & (uint16_t)~(CF | OF)) |
                (dx != 0 ? (CF | OF) : 0));
            ax = (uint16_t)product;

            bx = pop16(memory, call->stack_segment, &sp, flags, bus);
            old_bx = bx;
            bx = (uint16_t)(bx + ax);
            flags = add16_flags(flags, old_bx, ax);
            old_bx = bx;
            bx = (uint16_t)(bx + SEG143E_InteractionCellMapBase);
            flags = add16_flags(flags, old_bx,
                                SEG143E_InteractionCellMapBase);
            dx = pop16(memory, call->stack_segment, &sp, flags, bus);
            {
#if STEEL_BUS_MUTATION == 4
                /* Mutation: retain the previous ADD flags at the first row PUSH. */
                dx = (uint16_t)(dx + 0x0101u);
#else
                uint16_t old_dx = dx;
                dx = (uint16_t)(dx + 0x0101u);
                flags = add16_flags(flags, old_dx, 0x0101u);
#endif
            }

            do {
                sp = push16(memory, call->stack_segment, sp, dx, flags, bus);
                sp = push16(memory, call->stack_segment, sp, bx, flags, bus);
                do {
                    write8(memory, call->stack_segment, bx, 0x09u,
                           flags, bus);
                    {
                        uint16_t old_bx = bx;
                        bx = (uint16_t)(bx + 1u);
                        flags = inc16_flags(flags, old_bx);
                    }
                    {
                        uint8_t old_dh = (uint8_t)(dx >> 8);
                        dh = (uint8_t)(old_dh - 1u);
                        dx = (uint16_t)(((uint16_t)dh << 8) | (dx & 0x00ffu));
                        flags = dec8_flags(flags, old_dh);
                    }
                } while (dh != 0u);

                bx = pop16(memory, call->stack_segment, &sp, flags, bus);
                dx = pop16(memory, call->stack_segment, &sp, flags, bus);
                {
                    uint16_t old_bx = bx;
#if STEEL_BUS_MUTATION == 3
                    bx = (uint16_t)(bx + 0x019fu);
                    flags = add16_flags(flags, old_bx, 0x019fu);
#else
                    bx = (uint16_t)(bx + 0x01a0u);
                    flags = add16_flags(flags, old_bx, 0x01a0u);
#endif
                }
                {
                    uint8_t old_dl = (uint8_t)dx;
                    dl = (uint8_t)(old_dl - 1u);
                    dx = (uint16_t)((dx & 0xff00u) | dl);
                    flags = dec8_flags(flags, old_dl);
                }
            } while (dl != 0u);
        }

        {
            uint16_t old_di = di;
            di = (uint16_t)(di + 4u);
            flags = add16_flags(flags, old_di, 4u);
        }
        cx = (uint16_t)(cx - 1u); /* LOOP preserves the ADD flags. */
    }

    {
        LmnSteelInteractionCellsResult out = {
            .value = ax,
            .cell_cursor = bx,
            .records_remaining = cx,
            .dimensions = dx,
            .definition_cursor = di,
            .stack_offset = sp,
            .flags = flags
        };
        return out;
    }
}

void lmn_write_steel_interaction_cells_bus_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    LmnSteelInteractionCellsCall call = {
        registers->ds, registers->ss, registers->sp, registers->flags
    };
    LmnSteelInteractionCellsResult out =
        lmn_write_steel_interaction_cells_bus_core(memory, &call, bus);

    registers->ax = out.value;
    registers->bx = out.cell_cursor;
    registers->cx = out.records_remaining;
    registers->dx = out.dimensions;
    registers->di = out.definition_cursor;
    registers->sp = out.stack_offset;
    registers->flags = out.flags;
    registers->ip = read16(memory, registers->ss, registers->sp,
                           registers->flags, bus);
    registers->sp = (uint16_t)(registers->sp + 2u);
}
