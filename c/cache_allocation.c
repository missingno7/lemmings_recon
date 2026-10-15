#include "cache_allocation.h"
#include "lemmings_sym.h"

#ifndef CACHE_ALLOCATION_MUTATION
#define CACHE_ALLOCATION_MUTATION 0
#endif

enum {
    CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
    SF = 0x0080, OF = 0x0800, ARITHMETIC_FLAGS = 0x08d5,
    ALLOCATE_FUNCTION = 0x48, ALLOCATE_INITIAL_PARAGRAPHS = 0xffff,
    ALLOCATE_MINIMUM_PARAGRAPHS = 0x0c80,
    REQUEST_BOUNDARY = CS_DatCacheAllocationRequest,
    HIGH_PATH_RET = CS_DatCacheAllocationReadyReturn,
    LOW_PATH_RET = CS_DatCacheAllocationDisabledReturn
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

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

static uint16_t status_flags(uint16_t value, unsigned width) {
    unsigned parity = 0, bit;
    uint16_t flags = 0;
    for (bit = 0; bit < 8; ++bit)
        parity ^= (value >> bit) & 1u;
    if (!parity)
        flags |= PF;
    if ((width == 8u ? (value & 0x00ffu) : value) == 0)
        flags |= ZF;
    if (value & (width == 8u ? 0x0080u : 0x8000u))
        flags |= SF;
    return flags;
}

static uint16_t xor_flags(uint16_t flags, uint16_t value, unsigned width) {
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) |
                      status_flags(value, width));
}

static uint16_t compare_flags(uint16_t flags, uint16_t left,
                              uint16_t right) {
    uint16_t value = (uint16_t)(left - right);
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) |
        status_flags(value, 16) | (left < right ? CF : 0) |
        ((left ^ right ^ value) & AF) |
        (((left ^ right) & (left ^ value) & 0x8000u) ? OF : 0));
}

static LmnCacheAllocationServiceResult invoke_allocator(
    const LmnCacheAllocationServices *services, uint8_t *memory,
    uint16_t value, uint16_t paragraphs, uint16_t flags) {
    LmnCacheAllocationServiceResult out = {value, paragraphs, flags};
    services->allocate(services->context, memory, value, paragraphs, flags,
                       &out);
    return out;
}

LmnCacheAllocationResult lmn_allocate_dat_cache_core(uint8_t *memory,
    uint16_t data_segment, uint16_t incoming_value, uint16_t flags,
    const LmnCacheAllocationServices *services, const LmnRasterBus *bus) {
    uint16_t value = (uint16_t)((incoming_value & 0x00ffu) |
                                (ALLOCATE_FUNCTION << 8));
    uint16_t paragraphs = ALLOCATE_INITIAL_PARAGRAPHS;
    uint16_t continuation, compared_flags;
#if CACHE_ALLOCATION_MUTATION == 1
    uint16_t first_return_flags;
#endif
    unsigned below_threshold;
    LmnCacheAllocationServiceResult allocation;

    if (!services || !services->allocate) {
        LmnCacheAllocationResult out = {
            value, paragraphs, flags, REQUEST_BOUNDARY,
            LMN_CACHE_ALLOCATION_MISSING_PROVIDER
        };
        return out;
    }

    allocation = invoke_allocator(services, memory, value, paragraphs, flags);
    value = allocation.value;
    paragraphs = allocation.paragraphs;
    flags = allocation.flags;
#if CACHE_ALLOCATION_MUTATION == 1
    first_return_flags = flags;
#endif

    compared_flags = compare_flags(flags, paragraphs,
                                   ALLOCATE_MINIMUM_PARAGRAPHS);
    below_threshold = paragraphs < ALLOCATE_MINIMUM_PARAGRAPHS;
#if CACHE_ALLOCATION_MUTATION == 1
    /* Mutant: incorrectly let the first INT's carry force the small path. */
    if (first_return_flags & CF)
        below_threshold = 1u;
#endif
    if (below_threshold) {
        value &= 0xff00u;
#if CACHE_ALLOCATION_MUTATION == 3
        /* Mutant: clear AH too, although the original XOR only clears AL. */
        value = 0;
#endif
        flags = xor_flags(compared_flags, 0, 8);
        write_byte(memory, bus,
                   physical(data_segment, SEG09A9_DatCacheEnabled),
                   (uint8_t)value, flags);
        continuation = LOW_PATH_RET;
    } else {
        write_word(memory, data_segment, SEG09A9_DatCacheRequestedParagraphs,
                   paragraphs, compared_flags, bus);
        write_word(memory, data_segment, SEG09A9_DatCacheRemainingParagraphs,
                   paragraphs, compared_flags, bus);

        value = (uint16_t)((value & 0x00ffu) | (ALLOCATE_FUNCTION << 8));
        allocation = invoke_allocator(services, memory, value, paragraphs,
                                      compared_flags);
        value = allocation.value;
        paragraphs = allocation.paragraphs;
        flags = allocation.flags;
#if CACHE_ALLOCATION_MUTATION == 2
        /* Mutant: invent an AX=0000 result when the second provider sets CF. */
        if (flags & CF)
            value = 0;
#endif

        write_word(memory, data_segment, SEG09A9_DatCacheBaseSegment,
                   value, flags, bus);
        write_word(memory, data_segment, SEG09A9_DatCacheRecordSegment,
                   value, flags, bus);
        write_word(memory, data_segment, SEG09A9_DatCacheReadSegment,
                   value, flags, bus);
        write_word(memory, data_segment, SEG09A9_DatCacheFreeSegment,
                   value, flags, bus);

        value = 0;
        flags = xor_flags(flags, value, 16);
        write_word(memory, data_segment, SEG09A9_DatCacheRecordOffset,
                   value, flags, bus);
        write_word(memory, data_segment, SEG09A9_DatCacheReadOffset,
                   value, flags, bus);
        write_word(memory, data_segment, SEG09A9_DatCacheFreeOffset,
                   value, flags, bus);
        write_byte(memory, bus,
                   physical(data_segment, SEG09A9_DatCacheRecordCount),
                   (uint8_t)value, flags);
        write_byte(memory, bus,
                   physical(data_segment, SEG09A9_DatCacheSelected),
                   (uint8_t)value, flags);
        value = 0x00ffu;
        write_byte(memory, bus,
                   physical(data_segment, SEG09A9_DatCacheEnabled),
                   (uint8_t)value, flags);
        continuation = HIGH_PATH_RET;
    }

    {
        LmnCacheAllocationResult out = {
            value, paragraphs, flags, continuation,
            LMN_CACHE_ALLOCATION_READY
        };
        return out;
    }
}

void lmn_allocate_dat_cache_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnCacheAllocationServices *services, const LmnRasterBus *bus) {
#if CACHE_ALLOCATION_MUTATION == 4
    uint32_t entry_address = physical(registers->ss, registers->sp);
    uint16_t stale_return = (uint16_t)(memory[entry_address] |
        ((uint16_t)memory[(entry_address + 1u) & 0xfffffu] << 8));
#endif
    LmnCacheAllocationResult out = lmn_allocate_dat_cache_core(
        memory, registers->ds, registers->ax, registers->flags, services, bus);

    registers->ax = out.value;
    registers->bx = out.paragraphs;
    registers->flags = out.flags;
    registers->ip = out.continuation;
    if (out.status != LMN_CACHE_ALLOCATION_READY)
        return;

    /* Consume the live near-RET word low byte first; the successor byte uses
       physical+1 with 20-bit wrap, and SP advances modulo 16 bits. */
    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
#if CACHE_ALLOCATION_MUTATION == 4
        /* Mutant: publish the entry-time word instead of the live post-store
           word just consumed through the raster bus. */
        registers->ip = stale_return;
#endif
    }
}
