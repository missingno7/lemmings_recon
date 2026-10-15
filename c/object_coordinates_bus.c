#include "object_coordinates_bus.h"
#include "lemmings_sym.h"

#ifndef COORD_BUS_MUTATION
#define COORD_BUS_MUTATION 0
#endif

enum {
    FLAG_CF = 0x0001,
    FLAG_PF = 0x0004,
    FLAG_AF = 0x0010,
    FLAG_ZF = 0x0040,
    FLAG_SF = 0x0080,
    FLAG_OF = 0x0800,
    FLAG_ARITH = 0x08d5
};

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
        memory[address] = value;
}

static uint16_t read_be_word(uint8_t *memory, uint16_t data_segment,
                             uint16_t offset, uint16_t flags,
                             const LmnRasterBus *bus) {
    uint16_t low_offset = (uint16_t)(offset + 1u);
    uint8_t high;
    uint8_t low;

#if COORD_BUS_MUTATION == 2
    low = read_byte(memory, bus, physical(data_segment, low_offset), flags);
    high = read_byte(memory, bus, physical(data_segment, offset), flags);
#else
    high = read_byte(memory, bus, physical(data_segment, offset), flags);
    low = read_byte(memory, bus, physical(data_segment, low_offset), flags);
#endif
    return (uint16_t)(((uint16_t)high << 8) | low);
}

static uint16_t read_le_word(uint8_t *memory, uint16_t data_segment,
                             uint16_t offset, uint16_t flags,
                             const LmnRasterBus *bus) {
    uint32_t address = physical(data_segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, (address + 1u) & 0xfffffu, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_le_word(uint8_t *memory, uint16_t data_segment,
                          uint16_t offset, uint16_t value, uint16_t flags,
                          const LmnRasterBus *bus) {
    uint32_t address = physical(data_segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, (address + 1u) & 0xfffffu,
               (uint8_t)(value >> 8), flags);
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0u;
}

static uint16_t szp16(uint16_t value) {
    uint16_t flags = 0;
    if (even_parity8((uint8_t)value))
        flags |= FLAG_PF;
    if (value == 0u)
        flags |= FLAG_ZF;
    if (value & 0x8000u)
        flags |= FLAG_SF;
    return flags;
}

static uint16_t logical16(uint16_t flags, uint16_t value) {
    /* XOR/AND leave AF undefined; use the existing RAM core's zero representative. */
    return (uint16_t)((flags & (uint16_t)~FLAG_ARITH) | szp16(value));
}

static uint16_t cmp16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint16_t value = (uint16_t)(left - right);
    uint16_t result = szp16(value);
    if (left < right)
        result |= FLAG_CF;
    if ((left ^ right ^ value) & 0x0010u)
        result |= FLAG_AF;
    if (((left ^ right) & (left ^ value) & 0x8000u) != 0u)
        result |= FLAG_OF;
    return (uint16_t)((flags & (uint16_t)~FLAG_ARITH) | result);
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right,
                            uint16_t *value) {
    uint32_t total = (uint32_t)left + right;
    uint16_t result = (uint16_t)total;
    uint16_t set = 0;
    if (total > 0xffffu)
        set |= FLAG_CF;
    if (even_parity8((uint8_t)result))
        set |= FLAG_PF;
    if ((left ^ right ^ result) & 0x0010u)
        set |= FLAG_AF;
    if (result == 0u)
        set |= FLAG_ZF;
    if (result & 0x8000u)
        set |= FLAG_SF;
    if ((uint16_t)(~(left ^ right) & (left ^ result)) & 0x8000u)
        set |= FLAG_OF;
    *value = result;
    return (uint16_t)((flags & (uint16_t)~FLAG_ARITH) | set);
}

static uint16_t inc16_flags(uint16_t flags, uint16_t before,
                            uint16_t after) {
    uint16_t set = szp16(after);
    if ((before ^ after) & 0x0010u)
        set |= FLAG_AF;
    if (before == 0x7fffu)
        set |= FLAG_OF;
    /* INC preserves CF; all other arithmetic flags are defined here. */
    return (uint16_t)((flags & (uint16_t)~(FLAG_PF | FLAG_AF | FLAG_ZF |
                                           FLAG_SF | FLAG_OF)) | set);
}

static void store_pair(uint8_t *memory, uint16_t data_segment,
                       uint16_t offset, uint16_t x, uint16_t y,
                       uint16_t flags, const LmnRasterBus *bus) {
    write_le_word(memory, data_segment, offset, x, flags, bus);
    write_le_word(memory, data_segment, (uint16_t)(offset + 2u), y,
                  flags, bus);
}

LmnObjectCoordinatesResult lmn_collect_type_one_object_coordinates_bus_core(
    uint8_t *memory, const LmnObjectCoordinatesCall *call,
    const LmnRasterBus *bus) {
    uint16_t data_segment = call->data_segment;
    uint16_t value = 0;
    uint16_t output_cursor = SEG09A9_TypeOneObjectCoordinates;
    uint16_t remaining_records = 0x0020u;
    uint16_t definition_cursor = SEG09A9_LevelObjectDefinitions;
    uint16_t selected_count = 0;
    uint16_t result_count = 0;
    uint16_t flags = logical16(call->flags, 0);

    while (remaining_records != 0u) {
        uint16_t type = read_be_word(memory, data_segment,
            (uint16_t)(definition_cursor + 4u), flags, bus);
        value = type;
        flags = cmp16_flags(flags, value, 1u);
        if (type == 1u) {
            uint16_t x = read_be_word(memory, data_segment,
                                      definition_cursor, flags, bus);
            uint16_t y;
#if COORD_BUS_MUTATION == 1
            /* Deliberate mutation: fetch Y before the X store. */
            y = read_be_word(memory, data_segment,
                (uint16_t)(definition_cursor + 2u), flags, bus);
#endif
#if COORD_BUS_MUTATION == 4
            /* Keep X's value but omit the ADD flags visible at the X store. */
            value = (uint16_t)(x + 0x0018u);
#else
            flags = add16_flags(flags, x, 0x0018u, &value);
#endif
            write_le_word(memory, data_segment, output_cursor, value, flags, bus);
#if COORD_BUS_MUTATION != 1
            y = read_be_word(memory, data_segment,
                (uint16_t)(definition_cursor + 2u), flags, bus);
#endif
            flags = add16_flags(flags, y, 0x001eu, &value);
            write_le_word(memory, data_segment,
                (uint16_t)(output_cursor + 2u), value, flags, bus);
            flags = add16_flags(flags, output_cursor, 4u, &output_cursor);
            {
                uint16_t before = selected_count;
                selected_count = (uint16_t)(selected_count + 1u);
                flags = inc16_flags(flags, before, selected_count);
            }
        }
        flags = add16_flags(flags, definition_cursor, 8u, &definition_cursor);
        remaining_records = (uint16_t)(remaining_records - 1u);
    }

    flags = logical16(flags, selected_count); /* AND BP,BP */
    if (selected_count == 0u) {
        value = 0x0100u;
        result_count = 0x0010u;
        write_le_word(memory, data_segment, output_cursor, value, flags, bus);
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 2u), result_count, flags, bus);
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 4u), value, flags, bus);
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 6u), result_count, flags, bus);
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 8u), value, flags, bus);
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 0x0au), result_count, flags, bus);
#if COORD_BUS_MUTATION == 3
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 0x0cu), value, flags, bus);
#else
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 0x0au), value, flags, bus);
#endif
        write_le_word(memory, data_segment,
            (uint16_t)(output_cursor + 0x0eu), result_count, flags, bus);
    } else {
        flags = cmp16_flags(flags, selected_count, 1u);
        if (selected_count == 1u) {
            value = read_le_word(memory, data_segment,
                (uint16_t)(output_cursor - 4u), flags, bus);
            result_count = read_le_word(memory, data_segment,
                (uint16_t)(output_cursor - 2u), flags, bus);
            store_pair(memory, data_segment, output_cursor, value,
                       result_count, flags, bus);
            store_pair(memory, data_segment,
                (uint16_t)(output_cursor + 4u), value, result_count, flags, bus);
            store_pair(memory, data_segment,
                (uint16_t)(output_cursor + 8u), value, result_count, flags, bus);
        } else {
            flags = cmp16_flags(flags, selected_count, 2u);
            if (selected_count == 2u) {
                value = read_le_word(memory, data_segment,
                    (uint16_t)(output_cursor - 4u), flags, bus);
                result_count = read_le_word(memory, data_segment,
                    (uint16_t)(output_cursor - 2u), flags, bus);
                store_pair(memory, data_segment, output_cursor, value,
                           result_count, flags, bus);
                value = read_le_word(memory, data_segment,
                    (uint16_t)(output_cursor - 8u), flags, bus);
                result_count = read_le_word(memory, data_segment,
                    (uint16_t)(output_cursor - 6u), flags, bus);
                store_pair(memory, data_segment,
                    (uint16_t)(output_cursor + 4u), value, result_count,
                    flags, bus);
            } else {
                flags = cmp16_flags(flags, selected_count, 3u);
                if (selected_count == 3u) {
                    value = read_le_word(memory, data_segment,
                        (uint16_t)(output_cursor - 8u), flags, bus);
                    result_count = read_le_word(memory, data_segment,
                        (uint16_t)(output_cursor - 6u), flags, bus);
                    store_pair(memory, data_segment, output_cursor, value,
                               result_count, flags, bus);
                }
            }
        }
    }

    {
        LmnObjectCoordinatesResult result;
        result.value = value;
        result.count = result_count;
        result.definition_cursor = definition_cursor;
        result.output_cursor = output_cursor;
        result.selected_count = selected_count;
        result.flags = flags;
        return result;
    }
}

void lmn_collect_type_one_object_coordinates_bus_adapter(uint8_t *memory,
    LmnRegs *regs, const LmnRasterBus *bus) {
    LmnObjectCoordinatesCall call = {regs->ds, regs->flags};
    LmnObjectCoordinatesResult result =
        lmn_collect_type_one_object_coordinates_bus_core(memory, &call, bus);
    uint32_t stack_address;
    uint8_t low;
    uint8_t high;

    regs->ax = result.value;
    regs->bx = result.output_cursor;
    regs->cx = result.count;
    regs->si = result.definition_cursor;
    regs->bp = result.selected_count;
    regs->flags = result.flags;

    /* RET reads the live stack after output stores; high byte is physical+1. */
    stack_address = physical(regs->ss, regs->sp);
    low = read_byte(memory, bus, stack_address, result.flags);
    high = read_byte(memory, bus, (stack_address + 1u) & 0xfffffu,
                     result.flags);
    regs->ip = (uint16_t)(low | ((uint16_t)high << 8));
    regs->sp = (uint16_t)(regs->sp + 2u);
}
