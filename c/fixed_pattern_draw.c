#include "fixed_pattern_draw.h"

#include "lemmings_sym.h"

#ifndef FIXED_PATTERN_DRAW_MUTATION
#define FIXED_PATTERN_DRAW_MUTATION 0
#endif

#if FIXED_PATTERN_DRAW_MUTATION < 0 || FIXED_PATTERN_DRAW_MUTATION > 10
#error "FIXED_PATTERN_DRAW_MUTATION must be in the range 0..10"
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, IF = 0x0200u, DF = 0x0400u, OF = 0x0800u,
    ARITH = CF | PF | AF | ZF | SF | OF,
    VGA_APERTURE = 0xa000u,
    GRAPHICS_CONTROLLER = 0x03ceu,
    SEQUENCER = 0x03c4u,
    RETURN_SITE = CS_FixedPatternDrawReturn
};

typedef struct FixedPatternDrawState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
} FixedPatternDrawState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(FixedPatternDrawState *s, uint32_t address) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                 s->flags);
    return s->memory[address];
}

static void write_physical(FixedPatternDrawState *s, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           s->flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(FixedPatternDrawState *s, uint16_t segment,
                     uint16_t offset) {
    return read_physical(s, physical(segment, offset));
}

static uint16_t read16(FixedPatternDrawState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high;
#if FIXED_PATTERN_DRAW_MUTATION == 3
    if (offset == 0xffffu)
        high = read_physical(s, physical(segment, 0u));
    else
#endif
        high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write8(FixedPatternDrawState *s, uint16_t segment,
                   uint16_t offset, uint8_t value) {
    write_physical(s, physical(segment, offset), value);
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0u;
    unsigned bit;
    for (bit = 0u; bit < 8u; ++bit)
        parity ^= (unsigned)((value >> bit) & 1u);
    return parity == 0u;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out = 0u;
    if (even_parity8((uint8_t)value)) out |= PF;
    if (value == 0u) out |= ZF;
    if (value & 0x8000u) out |= SF;
    return out;
}

static uint16_t xor_ax_zero_flags(uint16_t flags) {
    /* XOR AX,AX defines CF/PF/ZF/SF/OF and leaves AF undefined. */
    return (uint16_t)((flags & (uint16_t)~(CF | PF | ZF | SF | OF)) |
                      PF | ZF);
}

static uint16_t inc16_flags(uint16_t flags, uint16_t before) {
    uint16_t value = (uint16_t)(before + 1u);
    uint16_t out = szp16(value);
    if ((before & 0x000fu) == 0x000fu) out |= AF;
    if (before == 0x7fffu) out |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | out | (flags & CF));
}

static uint16_t add16_flags(uint16_t flags, uint16_t left,
                            uint16_t right) {
    uint32_t wide = (uint32_t)left + (uint32_t)right;
    uint16_t result = (uint16_t)wide;
    uint16_t out = szp16(result);
    if (wide > 0xffffu) out |= CF;
    if ((left ^ right ^ result) & AF) out |= AF;
    if ((~(left ^ right) & (left ^ result) & 0x8000u) != 0u) out |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | out);
}

static uint16_t direction_step(uint16_t flags, uint16_t amount) {
#if FIXED_PATTERN_DRAW_MUTATION == 4
    (void)flags;
    return amount;
#else
    return (flags & DF) ? (uint16_t)(0u - amount) : amount;
#endif
}

static void out_word(FixedPatternDrawState *s) {
    if (s->bus && s->bus->out_word)
        s->bus->out_word(s->bus->context, s->dx, s->ax, s->flags);
}

static void read_latch(FixedPatternDrawState *s) {
    (void)read8(s, s->es, s->di);
}

static void lodsw(FixedPatternDrawState *s) {
    uint32_t address = physical(s->ds, s->si);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    s->ax = (uint16_t)(low | ((uint16_t)high << 8));
    s->si = (uint16_t)(s->si + direction_step(s->flags, 2u));
}

static void lodsb(FixedPatternDrawState *s) {
    uint8_t value = read8(s, s->ds, s->si);
    s->ax = (uint16_t)((s->ax & 0xff00u) | value);
    s->si = (uint16_t)(s->si + direction_step(s->flags, 1u));
}

static void stosb(FixedPatternDrawState *s) {
    write8(s, s->es, s->di, (uint8_t)s->ax);
    s->di = (uint16_t)(s->di + direction_step(s->flags, 1u));
}

static void add_di_pitch(FixedPatternDrawState *s) {
    uint16_t before = s->di;
#if FIXED_PATTERN_DRAW_MUTATION == 8
    const uint16_t pitch = 0x28u;
#else
    const uint16_t pitch = 0x29u;
#endif
    s->di = (uint16_t)(before + pitch);
    s->flags = add16_flags(s->flags, before, pitch);
}

static void first_pass_row(FixedPatternDrawState *s) {
    uint16_t control_offset = s->bx;
#if FIXED_PATTERN_DRAW_MUTATION == 1
    control_offset = s->si;
#endif
    s->cx = read16(s, s->ds, control_offset);         /* MOV CX,[BX] */
    s->flags = inc16_flags(s->flags, s->bx);          /* INC BX */
    s->bx = (uint16_t)(s->bx + 1u);
#if FIXED_PATTERN_DRAW_MUTATION != 9
    s->flags = inc16_flags(s->flags, s->bx);          /* INC BX */
    s->bx = (uint16_t)(s->bx + 1u);
#endif

    s->ax = (uint16_t)((s->ax & 0xff00u) | 0x08u);    /* MOV AL,08 */
#if FIXED_PATTERN_DRAW_MUTATION == 2
    s->ax = (uint16_t)((s->ax & 0x00ffu) |
                       (s->cx & 0xff00u));            /* swapped mask byte */
#else
    s->ax = (uint16_t)((s->ax & 0x00ffu) |
                       ((s->cx & 0x00ffu) << 8));     /* MOV AH,CL */
#endif
    out_word(s);                                      /* OUT DX,AX */
#if FIXED_PATTERN_DRAW_MUTATION != 5
    read_latch(s);                                    /* MOV AL,[ES:DI] */
#endif
    lodsw(s);                                         /* LODSW */
    stosb(s);                                         /* STOSB */

    {
        uint8_t old_ch = (uint8_t)(s->cx >> 8);
        uint8_t old_ah = (uint8_t)(s->ax >> 8);
        s->cx = (uint16_t)((s->cx & 0x00ffu) | ((uint16_t)old_ah << 8));
        s->ax = (uint16_t)((s->ax & 0x00ffu) | ((uint16_t)old_ch << 8));
    }                                                 /* XCHG CH,AH */
    s->ax = (uint16_t)((s->ax & 0xff00u) | 0x08u);    /* MOV AL,08 */
#if FIXED_PATTERN_DRAW_MUTATION == 2
    s->ax = (uint16_t)((s->ax & 0x00ffu) |
                       ((s->cx & 0x00ffu) << 8));     /* swapped mask byte */
#endif
    out_word(s);                                      /* OUT DX,AX */
#if FIXED_PATTERN_DRAW_MUTATION != 5
    read_latch(s);                                    /* MOV AL,[ES:DI] */
#endif
    s->ax = (uint16_t)((s->ax & 0xff00u) |
                       ((s->cx >> 8) & 0x00ffu));     /* MOV AL,CH */
    stosb(s);                                         /* STOSB */

    {
        uint8_t mask = read8(s, s->ds, s->bx);         /* MOV AH,[BX] */
        s->ax = (uint16_t)((s->ax & 0x00ffu) | ((uint16_t)mask << 8));
    }
    s->flags = inc16_flags(s->flags, s->bx);          /* INC BX */
    s->bx = (uint16_t)(s->bx + 1u);
    s->ax = (uint16_t)((s->ax & 0xff00u) | 0x08u);    /* MOV AL,08 */
    out_word(s);                                      /* OUT DX,AX */
#if FIXED_PATTERN_DRAW_MUTATION != 5
    read_latch(s);                                    /* MOV AL,[ES:DI] */
#endif
    lodsb(s);                                         /* LODSB */
    stosb(s);                                         /* STOSB */
    add_di_pitch(s);                                  /* ADD DI,29 */
}

static void second_pass_row(FixedPatternDrawState *s) {
#if FIXED_PATTERN_DRAW_MUTATION != 6
    read_latch(s);                                    /* MOV AL,[ES:DI] */
#endif
    lodsw(s);                                         /* LODSW */
    stosb(s);                                         /* STOSB */
#if FIXED_PATTERN_DRAW_MUTATION != 6
    read_latch(s);                                    /* MOV AL,[ES:DI] */
#endif
    s->ax = (uint16_t)((s->ax & 0xff00u) |
                       ((s->ax >> 8) & 0x00ffu));     /* MOV AL,AH */
    stosb(s);                                         /* STOSB */
#if FIXED_PATTERN_DRAW_MUTATION != 6
    read_latch(s);                                    /* MOV AL,[ES:DI] */
#endif
    lodsb(s);                                         /* LODSB */
    stosb(s);                                         /* STOSB */
    add_di_pitch(s);                                  /* ADD DI,29 */
}

static void initialize(FixedPatternDrawState *s, uint8_t *memory,
                       const LmnFixedPatternDrawCall *call,
                       const LmnRasterBus *bus) {
    s->memory = memory;
    s->bus = bus;
    s->ax = call->ax; s->bx = call->bx; s->cx = call->cx;
    s->dx = call->dx; s->si = call->si; s->di = call->di;
    s->bp = call->bp; s->cs = call->code_segment;
    s->ds = call->data_segment; s->es = call->extra_segment;
    s->ss = call->stack_segment; s->sp = call->stack_offset;
    s->flags = call->flags;
    s->continuation = RETURN_SITE;
    s->status = LMN_FIXED_PATTERN_DRAW_READY;
}

static LmnFixedPatternDrawResult result_of(const FixedPatternDrawState *s) {
    LmnFixedPatternDrawResult out;
    out.ax = s->ax; out.bx = s->bx; out.cx = s->cx;
    out.dx = s->dx; out.si = s->si; out.di = s->di; out.bp = s->bp;
    out.code_segment = s->cs; out.data_segment = s->ds;
    out.extra_segment = s->es; out.stack_segment = s->ss;
    out.stack_offset = s->sp; out.flags = s->flags;
    out.continuation = s->continuation; out.status = s->status;
    return out;
}

LmnFixedPatternDrawResult lmn_draw_fixed_word_pattern_core(
    uint8_t *memory, const LmnFixedPatternDrawCall *call,
    const LmnRasterBus *bus) {
    FixedPatternDrawState s;
    unsigned row;
    initialize(&s, memory, call, bus);

    s.flags = (uint16_t)(s.flags & (uint16_t)~IF);     /* CLI */
    s.dx = SEQUENCER;                                  /* MOV DX,3C4 */
    s.ax = 0x0f02u;                                    /* MOV AX,0F02 */
    out_word(&s);                                      /* OUT DX,AX */
    s.dx = GRAPHICS_CONTROLLER;                        /* MOV DX,3CE */
    s.ax = 0u;                                         /* XOR AX,AX */
    s.flags = xor_ax_zero_flags(s.flags);
    out_word(&s);                                      /* OUT DX,AX */
    s.ax = 0x0e01u;
    out_word(&s);
    s.ax = 0x0005u;
    out_word(&s);
    s.ax = 0x0003u;
    out_word(&s);
    s.cx = VGA_APERTURE;                               /* MOV CX,A000 */
    s.es = s.cx;                                       /* MOV ES,CX */
    s.bp = s.di;                                       /* MOV BP,DI */

    for (row = 0u; row < 16u; ++row)
        first_pass_row(&s);

    s.di = s.bp;                                       /* MOV DI,BP */
    s.ax = 0x0001u;
    out_word(&s);                                      /* OUT DX,AX */
    s.ax = 0x1003u;
    out_word(&s);
#if FIXED_PATTERN_DRAW_MUTATION == 7
    s.ax = 0xfe08u;
#else
    s.ax = 0xff08u;
#endif
    out_word(&s);
    s.dx = (uint16_t)((s.dx & 0xff00u) | 0x00c4u);     /* MOV DL,C4 */
    s.ax = 0x0202u;
    out_word(&s);                                      /* OUT DX,AX */

    for (row = 0u; row < 16u; ++row)
        second_pass_row(&s);

    s.flags = (uint16_t)(s.flags | IF);                /* STI */
    return result_of(&s);                              /* before RET @75EE */
}

static void apply_result(LmnRegs *r,
                         const LmnFixedPatternDrawResult *out) {
    r->ax = out->ax; r->bx = out->bx; r->cx = out->cx;
    r->dx = out->dx; r->si = out->si; r->di = out->di;
    r->bp = out->bp; r->cs = out->code_segment;
    r->ds = out->data_segment; r->es = out->extra_segment;
    r->ss = out->stack_segment; r->sp = out->stack_offset;
    r->flags = out->flags; r->ip = out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory, uint16_t ss,
                                  uint16_t sp, uint16_t flags,
                                  const LmnRasterBus *bus) {
    uint32_t address = physical(ss, sp);
    uint8_t low, high;
    if (bus && bus->read_byte) {
        low = bus->read_byte(bus->context, memory, address, flags);
        high = bus->read_byte(bus->context, memory,
                              (address + 1u) & MEMORY_MASK, flags);
    } else {
        low = memory[address];
        high = memory[(address + 1u) & MEMORY_MASK];
    }
    return (uint16_t)(low | ((uint16_t)high << 8));
}

uint16_t lmn_draw_fixed_word_pattern_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnFixedPatternDrawCall call;
    LmnFixedPatternDrawResult out;
#if FIXED_PATTERN_DRAW_MUTATION == 10
    uint16_t prefetched_return = read_stack_return(memory, registers->ss,
        registers->sp, registers->flags, bus);
#endif
    call.ax = registers->ax; call.bx = registers->bx;
    call.cx = registers->cx; call.dx = registers->dx;
    call.si = registers->si; call.di = registers->di;
    call.bp = registers->bp; call.code_segment = registers->cs;
    call.data_segment = registers->ds; call.extra_segment = registers->es;
    call.stack_segment = registers->ss; call.stack_offset = registers->sp;
    call.flags = registers->flags;
    out = lmn_draw_fixed_word_pattern_core(memory, &call, bus);
    apply_result(registers, &out);
    if (out.status == LMN_FIXED_PATTERN_DRAW_READY) {
#if FIXED_PATTERN_DRAW_MUTATION == 10
        registers->ip = prefetched_return;
#else
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
#endif
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return out.status;
}
