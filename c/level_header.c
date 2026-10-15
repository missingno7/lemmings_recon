#include "level_header.h"
#include "lemmings_sym.h"

#ifndef LEVEL_HEADER_MUTATION
#define LEVEL_HEADER_MUTATION 0
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

static void write_word(uint8_t *memory, uint16_t data_segment,
                       uint16_t offset, uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(data_segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, (address + 1u) & 0xfffffu,
               (uint8_t)(value >> 8), flags);
}

static uint16_t read_be_word(uint8_t *memory, uint16_t data_segment,
                             uint16_t offset, uint16_t flags,
                             const LmnRasterBus *bus) {
    uint32_t address = physical(data_segment, offset);
    uint8_t high;
    uint8_t low;
#if LEVEL_HEADER_MUTATION == 1
    low = read_byte(memory, bus, (address + 1u) & 0xfffffu, flags);
    high = read_byte(memory, bus, address, flags);
#else
    high = read_byte(memory, bus, address, flags);
    low = read_byte(memory, bus, (address + 1u) & 0xfffffu, flags);
#endif
    return (uint16_t)(((uint16_t)high << 8) | low);
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0u;
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right,
                            uint16_t *result) {
    uint32_t total = (uint32_t)left + right;
    uint16_t value = (uint16_t)total;
    uint16_t set = 0;

    if (total > 0xffffu)
        set |= FLAG_CF;
    if (even_parity8((uint8_t)value))
        set |= FLAG_PF;
    if ((left ^ right ^ value) & 0x0010u)
        set |= FLAG_AF;
    if (value == 0u)
        set |= FLAG_ZF;
    if (value & 0x8000u)
        set |= FLAG_SF;
    if ((uint16_t)(~(left ^ right) & (left ^ value)) & 0x8000u)
        set |= FLAG_OF;

    *result = value;
    return (uint16_t)((flags & (uint16_t)~FLAG_ARITH) | set);
}

static uint16_t shr_one_flags(uint16_t flags, uint16_t before,
                              uint16_t after) {
    uint16_t set = 0;
    if (before & 1u)
        set |= FLAG_CF;
    if (even_parity8((uint8_t)after))
        set |= FLAG_PF;
    if (after == 0u)
        set |= FLAG_ZF;
    if (after & 0x8000u)
        set |= FLAG_SF;
    if (before & 0x8000u)
        set |= FLAG_OF;
    /* SHR leaves AF undefined; retain its representative incoming value. */
    return (uint16_t)((flags & (uint16_t)~(FLAG_CF | FLAG_PF | FLAG_ZF |
                                           FLAG_SF | FLAG_OF)) | set);
}

static void store_low_byte(uint8_t *memory, uint16_t data_segment,
                           uint16_t offset, uint16_t value, uint16_t flags,
                           const LmnRasterBus *bus) {
#if LEVEL_HEADER_MUTATION == 2
    if (offset == SEG09A9_LevelHeaderWord04LowByte) {
        write_word(memory, data_segment, offset, value, flags, bus);
        return;
    }
#endif
    write_byte(memory, bus, physical(data_segment, offset),
               (uint8_t)value, flags);
}

LmnLevelHeaderResult lmn_apply_level_header_core(uint8_t *memory,
    uint16_t data_segment, uint16_t flags, const LmnRasterBus *bus) {
    static const uint16_t action_destinations[8] = {
        SEG09A9_LevelActionCount0,
        SEG09A9_LevelActionCount1,
        SEG09A9_LevelActionCount2,
        SEG09A9_LevelActionCount3,
        SEG09A9_LevelActionCount4,
        SEG09A9_LevelActionCount5,
        SEG09A9_LevelActionCount6,
        SEG09A9_LevelActionCount7
    };
    uint16_t header_cursor = SEG09A9_LoadedLevelRecord;
    uint16_t ax;
    uint16_t source;
    unsigned index;
    LmnLevelHeaderResult out;

    ax = read_be_word(memory, data_segment,
                      SEG09A9_LevelHeaderReleaseSettingWord, flags, bus);
    store_low_byte(memory, data_segment,
                   SEG09A9_LevelReleaseSettingMinimum, ax, flags, bus);
    store_low_byte(memory, data_segment,
                   SEG09A9_LevelReleaseSetting, ax, flags, bus);

    ax = read_be_word(memory, data_segment,
                      SEG09A9_LevelHeaderCreationLimitWord, flags, bus);
    store_low_byte(memory, data_segment, SEG09A9_LevelCreationLimit,
                   ax, flags, bus);

    ax = read_be_word(memory, data_segment, SEG09A9_LevelHeaderWord04,
                      flags, bus);
    store_low_byte(memory, data_segment, SEG09A9_LevelHeaderWord04LowByte,
                   ax, flags, bus);

    ax = read_be_word(memory, data_segment,
                      SEG09A9_LevelHeaderCountdownWord, flags, bus);
    flags = add16_flags(flags, ax, 0x0030u, &ax);
    store_low_byte(memory, data_segment, SEG09A9_LevelCountdownHighDigit,
                   ax, flags, bus);

    source = SEG09A9_LevelHeaderActionCountWords;
    for (index = 0; index < 8u; ++index) {
        ax = read_be_word(memory, data_segment, source, flags, bus);
        store_low_byte(memory, data_segment, action_destinations[index],
                       ax, flags, bus);
        source = (uint16_t)(source + 2u);
    }

    ax = read_be_word(memory, data_segment,
                      SEG09A9_LevelHeaderViewOriginWord, flags, bus);
#if LEVEL_HEADER_MUTATION == 3
    flags = add16_flags(flags, ax, 0x0011u, &ax);
#else
    flags = add16_flags(flags, ax, 0x0010u, &ax);
#endif
    write_word(memory, data_segment, SEG09A9_LevelViewOriginPixels,
               ax, flags, bus);

    {
        uint16_t before = ax;
        ax = (uint16_t)(before >> 1);
        flags = shr_one_flags(flags, before, ax);
        before = ax;
        ax = (uint16_t)(before >> 1);
        flags = shr_one_flags(flags, before, ax);
        before = ax;
        ax = (uint16_t)(before >> 1);
        flags = shr_one_flags(flags, before, ax);
    }
#if LEVEL_HEADER_MUTATION == 4
    flags ^= FLAG_CF;
#endif
    write_word(memory, data_segment, SEG09A9_LevelViewOriginBytes,
               ax, flags, bus);

    out.value = ax;
    out.header_cursor = header_cursor;
    out.flags = flags;
    return out;
}

void lmn_apply_level_header_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus) {
    LmnLevelHeaderResult out = lmn_apply_level_header_core(
        memory, regs->ds, regs->flags, bus);
    regs->ax = out.value;
    regs->di = out.header_cursor;
    regs->flags = out.flags;
    regs->ip = CS_LevelAfterHeader;
}
