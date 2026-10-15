#include "coordinate_pixel.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, OF=0x0800,
       ARITH=CF|PF|AF|ZF|SF|OF, LOGIC=CF|PF|ZF|SF|OF };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xFFFFFu;
}

static uint8_t read_physical(uint8_t *memory, uint32_t address,
                             uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xFFFFFu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_physical(uint8_t *memory, uint32_t address, uint8_t value,
                           uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xFFFFFu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

/* Real-mode word accesses are two physical bytes, with 20-bit wrap. */
static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(memory, address, flags, bus);
    uint8_t high = read_physical(memory, address + 1u, flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_physical(memory, address, (uint8_t)value, flags, bus);
    write_physical(memory, address + 1u, (uint8_t)(value >> 8), flags, bus);
}

static uint16_t parity_flags(uint16_t value) {
    unsigned parity = 0, bit;
    for (bit = 0; bit < 8; ++bit) parity ^= (value >> bit) & 1u;
    return parity ? 0 : PF;
}

static uint16_t sub16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint16_t value = (uint16_t)(left - right);
    uint16_t status = parity_flags(value);
    if (left < right) status |= CF;
    if ((left ^ right ^ value) & 0x10u) status |= AF;
    if (!value) status |= ZF;
    if (value & 0x8000u) status |= SF;
    if (((left ^ right) & (left ^ value) & 0x8000u) != 0) status |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | status);
}

#if MUTATION == 1
static uint16_t xor_zero_flags(uint16_t flags) {
    return (uint16_t)((flags & (uint16_t)~LOGIC) | PF | ZF);
}
#endif

static uint16_t mul_flags(uint16_t flags, uint32_t product) {
    uint16_t status = product > 0xFFFFu ? (CF | OF) : 0;
    return (uint16_t)((flags & (uint16_t)~(CF | OF)) | status);
}

static uint16_t shr16_flags(uint16_t flags, uint16_t before) {
    uint16_t value = (uint16_t)(before >> 1);
    uint16_t status = parity_flags(value);
    if (before & 1u) status |= CF;
    if (!value) status |= ZF;
    if (value & 0x8000u) status |= SF;
    if (before & 0x8000u) status |= OF;
    return (uint16_t)((flags & (uint16_t)~(ARITH & (uint16_t)~AF)) | status);
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t sum = (uint32_t)left + right;
    uint16_t value = (uint16_t)sum;
    uint16_t status = parity_flags(value);
    if (sum > 0xFFFFu) status |= CF;
    if ((left ^ right ^ value) & 0x10u) status |= AF;
    if (!value) status |= ZF;
    if (value & 0x8000u) status |= SF;
    if ((~(left ^ right) & (left ^ value) & 0x8000u) != 0) status |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | status);
}

static uint16_t and7_flags(uint16_t flags, uint16_t value) {
    uint16_t status = parity_flags(value);
    /* AND BX,7 yields 0..7, clears CF/OF, and leaves AF undefined. */
    if (!value) status |= ZF;
    return (uint16_t)((flags & (uint16_t)~LOGIC) | status);
}

LmnCoordinatePixelResult lmn_prepare_coordinate_pixel_core(
    uint8_t *memory, const LmnCoordinatePixelCall *call,
    const LmnRasterBus *bus) {
    uint16_t bx = call->row_value;    /* Input Y. */
    uint16_t cx = call->column_value; /* Input X. */
    uint16_t dx = call->saved_value;
    uint16_t sp = call->stack_offset;
    uint16_t flags = call->flags;
    uint16_t di = bx;
    uint16_t row;
    uint32_t product;
    uint8_t mask;
    LmnCoordinatePixelResult result;

    /* PUSH BX; PUSH CX. Values are written to canonical SS memory. */
    sp = (uint16_t)(sp - 2u);
    write_word(memory, call->stack_segment, sp, bx, flags, bus);
    sp = (uint16_t)(sp - 2u);
    write_word(memory, call->stack_segment, sp, cx, flags, bus);

    /* The original does not clamp: negative wrapped DI flows into MUL. */
    di = (uint16_t)(di - 0x10u);
    flags = sub16_flags(flags, bx, 0x10u);
#if MUTATION == 1
    if (bx < 0x10u || (bx & 0x8000u)) {
        di = 0;
        flags = xor_zero_flags(flags);
    }
#endif

    /* PUSH DX; MOV AX,D0h; MUL DI; POP DX consumes the live save. */
    sp = (uint16_t)(sp - 2u);
    write_word(memory, call->stack_segment, sp, dx, flags, bus);
    row = di;
    product = (uint32_t)row * 0xD0u;
    flags = mul_flags(flags, product);
    dx = read_word(memory, call->stack_segment, sp, flags, bus);
    sp = (uint16_t)(sp + 2u);

    /* MOV DI,AX; MOV BX,CX; SHR CX,1 three times. */
    di = (uint16_t)product;
    bx = cx;
    flags = shr16_flags(flags, cx);
    cx = (uint16_t)(cx >> 1);
    flags = shr16_flags(flags, cx);
    cx = (uint16_t)(cx >> 1);
    flags = shr16_flags(flags, cx);
    cx = (uint16_t)(cx >> 1);

    {
        uint16_t before = di;
        di = (uint16_t)(di + cx);
        flags = add16_flags(flags, before, cx);
        before = di;
        di = (uint16_t)(di + 0x4A40u);
        flags = add16_flags(flags, before, 0x4A40u);
    }

    bx &= 7u;
    flags = and7_flags(flags, bx);
    {
        uint16_t before = bx;
        bx = (uint16_t)(bx + SEG09A9_PixelBitMasks);
        flags = add16_flags(flags, before, SEG09A9_PixelBitMasks);
    }
    mask = read_physical(memory,
        physical(call->data_segment, bx), flags, bus);

    result.value = (uint16_t)(((uint16_t)mask << 8) | (product & 0xFFu));
#if MUTATION == 3
    result.value &= 0xFF00u;
#endif

    /* POP CX; POP BX. Both words are read live from the original SS. */
    cx = read_word(memory, call->stack_segment, sp, flags, bus);
    sp = (uint16_t)(sp + 2u);
    bx = read_word(memory, call->stack_segment, sp, flags, bus);
    sp = (uint16_t)(sp + 2u);

#if MUTATION == 2
    bx = call->row_value;
    cx = call->column_value;
#endif
    result.row_value = bx;
    result.column_value = cx;
    result.restored_value = dx;
    result.destination_offset = di;
    result.output_segment = 0xA000u;
    result.stack_offset = sp;
    result.flags = flags;
    return result;
}

static void adapter(uint8_t *memory, LmnRegs *registers,
                    const LmnRasterBus *bus) {
    LmnCoordinatePixelCall call = {
        registers->ds, registers->ss, registers->sp,
        registers->cx, registers->bx, registers->dx, registers->flags
    };
    LmnCoordinatePixelResult result;
    uint16_t return_word;

#if MUTATION == 4
    return_word = read_word(memory, registers->ss, registers->sp,
                            registers->flags, bus);
#endif

    result = lmn_prepare_coordinate_pixel_core(memory, &call, bus);
    registers->ax = result.value;
    registers->bx = result.row_value;
    registers->cx = result.column_value;
    registers->dx = result.restored_value;
    registers->di = result.destination_offset;
    registers->es = result.output_segment;
    registers->sp = result.stack_offset;
    registers->flags = result.flags;
#if MUTATION != 4
    return_word = read_word(memory, registers->ss, registers->sp,
                            registers->flags, bus);
#endif
    registers->ip = return_word;
    registers->sp = (uint16_t)(registers->sp + 2u);
}

void lmn_prepare_coordinate_pixel_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    adapter(memory, registers, bus);
}
