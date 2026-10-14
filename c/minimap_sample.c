#include "minimap_sample.h"

#ifndef SAMPLE_MUTATION
#define SAMPLE_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040, SF=0x0080,
       OF=0x0800, ARITH=0x08d5 };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_physical(uint8_t *mem, uint32_t address, uint16_t flags,
                             const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, mem, address, flags);
    return mem[address];
}

static void write_physical(uint8_t *mem, uint32_t address, uint8_t value,
                           uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, mem, address, value, flags);
    else
        mem[address] = value;
}

static uint8_t read_segment_byte(uint8_t *mem, uint16_t segment,
                                 uint16_t offset, uint16_t flags,
                                 const LmnRasterBus *bus) {
    return read_physical(mem, physical(segment, offset), flags, bus);
}

/* A 16-bit stack word occupies contiguous physical bytes.  Offset wrap applies
   when the next instruction addresses SS:SP again, not between these bytes. */
static uint16_t read_stack_word(uint8_t *mem, uint16_t segment,
                                uint16_t offset, uint16_t flags,
                                const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(mem, address, flags, bus);
    uint8_t high = read_physical(mem, address + 1u, flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_stack_word(uint8_t *mem, uint16_t segment,
                             uint16_t offset, uint16_t value,
                             uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_physical(mem, address, (uint8_t)value, flags, bus);
    write_physical(mem, address + 1u, (uint8_t)(value >> 8), flags, bus);
}

static unsigned even_parity(uint8_t value) {
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones ^= (value >> bit) & 1u;
    return ones == 0u;
}

static uint16_t compare_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint8_t result = (uint8_t)(left - right);
    uint16_t set = 0;
    if (left < right)
        set |= CF;
    if (even_parity(result))
        set |= PF;
    if ((left ^ right ^ result) & 0x10u)
        set |= AF;
    if (result == 0u)
        set |= ZF;
    if (result & 0x80u)
        set |= SF;
    if ((left ^ right) & (left ^ result) & 0x80u)
        set |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | set);
}

static uint16_t or_flags(uint16_t flags, uint8_t result) {
    uint16_t set = 0;
    if (even_parity(result))
        set |= PF;
    if (result == 0u)
        set |= ZF;
    if (result & 0x80u)
        set |= SF;
    /* OR defines CF/PF/ZF/SF/OF.  AF is undefined, so keep its representative. */
    return (uint16_t)((flags & (uint16_t)~(CF | PF | ZF | SF | OF)) | set);
}

LmnMinimapSampleResult lmn_accumulate_minimap_sample_core(uint8_t *mem,
    uint16_t code_segment, uint16_t extra_segment, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t source_cursor, uint16_t target_cursor,
    uint8_t mask, uint16_t count, uint16_t flags, const LmnRasterBus *bus) {
    uint16_t pushed_offset = (uint16_t)(stack_offset - 2u);
    uint8_t high, low, population = 0;
    uint16_t ax, dx, restored_count, final_flags;
    uint16_t iteration;

    /* PUSH CX precedes both byte reads and may change their live source. */
    write_stack_word(mem, stack_segment, pushed_offset, count, flags, bus);
    high = read_segment_byte(mem, extra_segment, source_cursor, flags, bus);
#if SAMPLE_MUTATION == 2
    /* Deliberately wrong: physical-word continuation ignores SI's 16-bit wrap. */
    low = read_physical(mem,
        physical(extra_segment, source_cursor) + 1u, flags, bus);
#else
    low = read_segment_byte(mem, extra_segment,
        (uint16_t)(source_cursor + 1u), flags, bus);
#endif
    ax = (uint16_t)(((uint16_t)high << 8) | low);

    /* The original executes sixteen separate SHR/conditional-INC pairs. */
    for (iteration = 0; iteration < 16u; ++iteration) {
        if (ax & 1u)
            ++population;
        ax >>= 1;
    }
    dx = (uint16_t)(((uint16_t)population << 8) | mask);
    final_flags = compare_flags(flags, population, 8u);

#if SAMPLE_MUTATION == 1
    if (population >= 8u) {
#else
    if (population > 8u) {
#endif
        uint32_t target_address = physical(code_segment, target_cursor);
        uint8_t old_value = read_physical(mem, target_address, final_flags, bus);
        uint8_t result = (uint8_t)(old_value | mask);
        /* The memory read/write observe CMP flags; OR changes flags afterwards. */
        write_physical(mem, target_address, result, final_flags, bus);
        final_flags = or_flags(final_flags, result);
    }

    restored_count = read_stack_word(mem, stack_segment, pushed_offset,
                                     final_flags, bus);
#if SAMPLE_MUTATION == 3
    /* Deliberately stale: the real POP rereads the live SS word. */
    (void)restored_count;
    restored_count = count;
#endif
    stack_offset = (uint16_t)(pushed_offset + 2u);

    {
        LmnMinimapSampleResult result = { 0, dx, restored_count,
                                          stack_offset, final_flags };
        return result;
    }
}

void lmn_accumulate_minimap_sample_adapter(uint8_t *mem, LmnRegs *regs,
    const LmnRasterBus *bus) {
    LmnMinimapSampleResult result = lmn_accumulate_minimap_sample_core(mem,
        regs->cs, regs->es, regs->ss, regs->sp, regs->si, regs->bx,
        (uint8_t)regs->dx, regs->cx, regs->flags, bus);
    uint16_t return_offset = result.stack_offset;

    regs->ax = result.value;
    regs->cx = result.count;
    regs->dx = result.population_mask;
    regs->flags = result.flags;
    /* RET consumes the live, contiguous physical SS word after POP CX. */
    regs->ip = read_stack_word(mem, regs->ss, return_offset, result.flags, bus);
    regs->sp = (uint16_t)(return_offset + 2u);
}
