#include "mask_generators.h"

#ifndef MUTATION
#define MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800, ARITH=0x08D5 };

typedef struct Generator {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ds, es, ss, sp, si, di, bx, cx, dx, ax, flags;
    unsigned byte_generator;
} Generator;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xFFFFFu;
}

static uint8_t read_physical(Generator *s, uint32_t address) {
    address &= 0xFFFFFu;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address, s->flags);
    return s->memory[address];
}

static void write_physical(Generator *s, uint32_t address, uint8_t value) {
    address &= 0xFFFFFu;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value, s->flags);
    else
        s->memory[address] = value;
}

/* Real-mode word high bytes use the next physical byte, including wrap. */
static uint16_t read_word(Generator *s, uint16_t segment, uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(Generator *s, uint16_t segment, uint16_t offset,
                       uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical(s, address, (uint8_t)value);
    write_physical(s, address + 1u, (uint8_t)(value >> 8));
}

static uint16_t push(Generator *s, uint16_t value) {
    s->sp = (uint16_t)(s->sp - 2u);
    write_word(s, s->ss, s->sp, value);
    return s->sp;
}

static uint16_t pop(Generator *s) {
    uint16_t value = read_word(s, s->ss, s->sp);
    s->sp = (uint16_t)(s->sp + 2u);
    return value;
}

static uint16_t szp8(uint8_t value) {
    unsigned parity = 0, bit;
    uint16_t result = 0;
    for (bit = 0; bit < 8; ++bit) parity ^= (value >> bit) & 1u;
    if (!parity) result |= PF;
    if (!value) result |= ZF;
    if (value & 0x80u) result |= SF;
    return result;
}

static uint16_t szp16(uint16_t value) {
    uint16_t result = (uint16_t)(szp8((uint8_t)value) &
                                 (uint16_t)~(ZF | SF));
    if (!value) result |= ZF;
    if (value & 0x8000u) result |= SF;
    return result;
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    return (uint16_t)((flags & (uint16_t)~ARITH) | szp8(value));
}

static uint16_t inc8_flags(uint16_t flags, uint8_t before) {
    uint8_t value = (uint8_t)(before + 1u);
    uint16_t status = szp8(value);
    if ((before & 0x0Fu) == 0x0Fu) status |= AF;
    if (before == 0x7Fu) status |= OF;
    return (uint16_t)((flags & (uint16_t)~(ARITH & (uint16_t)~CF)) | status);
}

static uint16_t dec8_flags(uint16_t flags, uint8_t before) {
    uint8_t value = (uint8_t)(before - 1u);
    uint16_t status = szp8(value);
    if ((before & 0x0Fu) == 0) status |= AF;
    if (before == 0x80u) status |= OF;
    return (uint16_t)((flags & (uint16_t)~(ARITH & (uint16_t)~CF)) | status);
}

static uint16_t inc16_flags(uint16_t flags, uint16_t before) {
    uint16_t value = (uint16_t)(before + 1u);
    uint16_t status = szp16(value);
    if ((before & 0x0Fu) == 0x0Fu) status |= AF;
    if (before == 0x7FFFu) status |= OF;
    return (uint16_t)((flags & (uint16_t)~(ARITH & (uint16_t)~CF)) | status);
}

#if MUTATION == 1
static uint16_t dec16_flags(uint16_t flags, uint16_t before) {
    uint16_t value = (uint16_t)(before - 1u);
    uint16_t status = szp16(value);
    if ((before & 0x0Fu) == 0) status |= AF;
    if (before == 0x8000u) status |= OF;
    return (uint16_t)((flags & (uint16_t)~(ARITH & (uint16_t)~CF)) | status);
}
#endif

static uint16_t cmp8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint8_t value = (uint8_t)(left - right);
    uint16_t status = szp8(value);
    if (left < right) status |= CF;
    if ((left ^ right ^ value) & 0x10u) status |= AF;
    if (((left ^ right) & (left ^ value) & 0x80u) != 0) status |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | status);
}

static void shr8(Generator *s, uint8_t *reg) {
    uint8_t before = *reg;
    uint8_t value = (uint8_t)(before >> 1);
    uint16_t status = szp8(value);
    if (before & 1u) status |= CF;
    if (before & 0x80u) status |= OF;
    s->flags = (uint16_t)((s->flags & (uint16_t)~ARITH) | status);
    *reg = value;
}

/* RCR count one defines OF as the XOR of the result's top two bits. */
static void rcr8(Generator *s, uint8_t *reg) {
    uint8_t before = *reg;
    uint8_t carry_in = (uint8_t)(s->flags & CF);
    uint8_t value = (uint8_t)((before >> 1) | (carry_in ? 0x80u : 0));
    uint16_t status = s->flags & (uint16_t)~(CF | OF);
    if (before & 1u) status |= CF;
    if (((value >> 7) ^ (value >> 6)) & 1u) status |= OF;
    s->flags = status;
    *reg = value;
}

static void lods(Generator *s) {
    uint16_t step;
    if (s->byte_generator) {
        uint8_t value = read_physical(s, physical(s->ds, s->si));
        s->ax = (uint16_t)((s->ax & 0xFF00u) | value);
        step = 1;
    } else {
        s->ax = read_word(s, s->ds, s->si);
        step = 2;
    }
#if MUTATION == 2
    if (s->byte_generator) {
        s->si = (uint16_t)(s->si + step);
        return;
    }
#endif
    s->si = (uint16_t)(s->si + ((s->flags & DF) ? (uint16_t)(0u - step) : step));
}

static void store_word_mask_byte(Generator *s, uint8_t value) {
    write_physical(s, physical(s->es, s->di), value);
#if MUTATION == 1
    if (s->flags & DF) {
        uint16_t before = s->di;
        s->di = (uint16_t)(s->di - 1u);
        s->flags = dec16_flags(s->flags, before);
        return;
    }
#endif
    {
        uint16_t before = s->di;
        s->di = (uint16_t)(s->di + 1u);
        s->flags = inc16_flags(s->flags, before);
    }
}

static void stosw(Generator *s) {
    uint16_t step = 2;
    write_word(s, s->es, s->di, s->ax);
#if MUTATION == 2
    if (s->byte_generator) {
        s->di = (uint16_t)(s->di + 2u);
        return;
    }
#endif
    if (s->flags & DF) step = (uint16_t)(0u - step);
    s->di = (uint16_t)(s->di + step);
}

static LmnMaskGeneratorResult generate(uint8_t *memory,
    const LmnMaskGeneratorCall *call, const LmnRasterBus *bus,
    unsigned byte_generator) {
    Generator s;
#if MUTATION == 3
    unsigned outer_pass = 0;
#endif
    s.memory = memory;
    s.bus = bus;
    s.ds = call->source_segment;
    s.es = call->output_segment;
    s.ss = call->stack_segment;
    s.sp = call->stack_offset;
    s.si = call->source_cursor;
    s.di = call->output_cursor;
    s.bx = call->column_repetitions;
    s.cx = call->row_count;
    s.dx = call->shift_state;
    s.ax = 0;
    s.flags = call->flags;
    s.byte_generator = byte_generator;

    /* XOR DH,DH: the real routine restarts the bit-shift pass at zero. */
    s.dx &= 0x00FFu;
    s.flags = logic8_flags(s.flags, 0);

    for (;;) {
        (void)push(&s, s.dx);
        (void)push(&s, s.bx);
        (void)push(&s, s.si);
        for (;;) {
            (void)push(&s, s.bx);
            (void)push(&s, s.cx);
            for (;;) {
                (void)push(&s, s.cx);
                lods(&s);
                if (byte_generator) {
                    s.ax &= 0x00FFu;
                    s.flags = logic8_flags(s.flags, 0);
                } else {
                    s.dx &= 0xFF00u;
                    s.flags = logic8_flags(s.flags, 0);
                }
                {
                    uint8_t dh = (uint8_t)(s.dx >> 8);
                    s.flags = logic8_flags(s.flags, dh);
                    if (dh != 0) {
                        uint8_t bh = (uint8_t)(s.bx >> 8);
                        uint8_t al = (uint8_t)s.ax;
                        uint8_t ah = (uint8_t)(s.ax >> 8);
                        uint8_t dl = (uint8_t)s.dx;
                        bh = dh;
                        do {
                            shr8(&s, &al);
                            rcr8(&s, &ah);
                            if (!byte_generator) {
#if MUTATION != 4
                                rcr8(&s, &dl);
#endif
                            }
                            s.bx = (uint16_t)((s.bx & 0x00FFu) |
                                              ((uint16_t)bh << 8));
                            bh = (uint8_t)(bh - 1u);
                            s.flags = dec8_flags(s.flags,
                                (uint8_t)(bh + 1u));
                        } while (bh != 0);
                        s.bx = (uint16_t)((s.bx & 0x00FFu) |
                                          ((uint16_t)bh << 8));
                        s.ax = (uint16_t)(al | ((uint16_t)ah << 8));
                        if (!byte_generator)
                            s.dx = (uint16_t)((s.dx & 0xFF00u) | dl);
                    }
                }
                if (byte_generator) {
                    stosw(&s);
                } else {
                    store_word_mask_byte(&s, (uint8_t)s.ax);
                    store_word_mask_byte(&s, (uint8_t)(s.ax >> 8));
                    store_word_mask_byte(&s, (uint8_t)s.dx);
                }
                s.cx = pop(&s);
                {
                    uint16_t before = s.cx;
                    s.cx = (uint16_t)(s.cx - 1u);
                    /* LOOP does not modify any flags. */
                    (void)before;
                }
                if (s.cx == 0) break;
            }
            s.cx = pop(&s);
            s.bx = pop(&s);
            {
                uint8_t bl = (uint8_t)s.bx;
                s.flags = dec8_flags(s.flags, bl);
                bl = (uint8_t)(bl - 1u);
                s.bx = (uint16_t)((s.bx & 0xFF00u) | bl);
            }
            if ((uint8_t)s.bx == 0) break;
        }
        s.si = pop(&s);
        s.bx = pop(&s);
        s.dx = pop(&s);
        {
            uint8_t dh = (uint8_t)(s.dx >> 8);
            s.flags = inc8_flags(s.flags, dh);
            dh = (uint8_t)(dh + 1u);
            s.dx = (uint16_t)((s.dx & 0x00FFu) | ((uint16_t)dh << 8));
            s.flags = cmp8_flags(s.flags, dh, 8);
        }
#if MUTATION == 3
        ++outer_pass;
        if (outer_pass >= 8) break;
#else
        if ((uint8_t)(s.dx >> 8) == 8) break;
#endif
    }

    {
        LmnMaskGeneratorResult result = {
            s.ax, s.bx, s.cx, s.dx, s.si, s.di, s.sp, s.flags
        };
        return result;
    }
}

LmnMaskGeneratorResult lmn_generate_word_mask_shifts_core(
    uint8_t *memory, const LmnMaskGeneratorCall *call,
    const LmnRasterBus *bus) {
    return generate(memory, call, bus, 0);
}

LmnMaskGeneratorResult lmn_generate_byte_mask_shifts_core(
    uint8_t *memory, const LmnMaskGeneratorCall *call,
    const LmnRasterBus *bus) {
    return generate(memory, call, bus, 1);
}

static void adapter(uint8_t *memory, LmnRegs *r, const LmnRasterBus *bus,
                    unsigned byte_generator) {
    LmnMaskGeneratorCall call;
    LmnMaskGeneratorResult out;
    uint16_t return_word;
    uint32_t address;
#if MUTATION == 5
    address = physical(r->ss, r->sp);
    if (bus && bus->read_byte) {
        uint8_t low = bus->read_byte(bus->context, memory, address, r->flags);
        uint8_t high = bus->read_byte(bus->context, memory,
                                      (address + 1u) & 0xFFFFFu, r->flags);
        return_word = (uint16_t)(low | ((uint16_t)high << 8));
    } else {
        return_word = (uint16_t)(memory[address] |
            ((uint16_t)memory[(address + 1u) & 0xFFFFFu] << 8));
    }
#endif
    call.source_segment = r->ds;
    call.output_segment = r->es;
    call.stack_segment = r->ss;
    call.stack_offset = r->sp;
    call.source_cursor = r->si;
    call.output_cursor = r->di;
    call.column_repetitions = r->bx;
    call.row_count = r->cx;
    call.shift_state = r->dx;
    call.flags = r->flags;
    out = generate(memory, &call, bus, byte_generator);
    r->ax = out.value;
    r->bx = out.column_repetitions;
    r->cx = out.row_count;
    r->dx = out.shift_state;
    r->si = out.source_cursor;
    r->di = out.output_cursor;
    r->sp = out.stack_offset;
    r->flags = out.flags;
#if MUTATION != 5
    address = physical(r->ss, r->sp);
    if (bus && bus->read_byte) {
        uint8_t low = bus->read_byte(bus->context, memory, address, r->flags);
        uint8_t high = bus->read_byte(bus->context, memory,
                                      (address + 1u) & 0xFFFFFu, r->flags);
        return_word = (uint16_t)(low | ((uint16_t)high << 8));
    } else {
        return_word = (uint16_t)(memory[address] |
            ((uint16_t)memory[(address + 1u) & 0xFFFFFu] << 8));
    }
#endif
    r->ip = return_word;
    r->sp = (uint16_t)(r->sp + 2u);
}

void lmn_generate_word_mask_shifts_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    adapter(memory, registers, bus, 0);
}

void lmn_generate_byte_mask_shifts_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    adapter(memory, registers, bus, 1);
}
