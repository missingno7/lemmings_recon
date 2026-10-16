#include "fixed_pattern_copy.h"

#include "lemmings_sym.h"

#ifndef FIXED_PATTERN_COPY_MUTATION
#define FIXED_PATTERN_COPY_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, TF = 0x0100u, IF = 0x0200u, DF = 0x0400u,
    OF = 0x0800u,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF,
    VGA_APERTURE = 0xa000u,
    VGA_GRAPHICS_CONTROLLER = 0x03ceu,
    VGA_SEQUENCER = 0x03c4u,
    FIXED_PATTERN_COPY_RET = CS_FixedPatternCopyReturn,
    FIXED_PATTERN_BIAS = SEG09A9_FixedPatternOffsetBias1FE0,
    FIXED_PATTERN_POINTER_X = SEG09A9_PointerX,
    FIXED_PATTERN_POINTER_Y = SEG09A9_PointerY,
    FIXED_PATTERN_SOURCE = SEG09A9_FixedPatternVgaOffset000A,
    FIXED_PATTERN_FIRST_DESTINATION = SEG09A9_FixedPatternVgaOffset000E,
    FIXED_PATTERN_SECOND_DESTINATION = SEG09A9_FixedPatternVgaOffset0008,
    FIXED_PATTERN_SECOND_SOURCE = SEG09A9_FixedPatternVgaOffset000C
};

typedef struct FixedPatternCopyState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
} FixedPatternCopyState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(FixedPatternCopyState *s, uint32_t address) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                 s->flags);
    return s->memory[address];
}

static void write_physical(FixedPatternCopyState *s, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           s->flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(FixedPatternCopyState *s, uint16_t segment,
                     uint16_t offset) {
    return read_physical(s, physical(segment, offset));
}

static void write8(FixedPatternCopyState *s, uint16_t segment,
                   uint16_t offset, uint8_t value) {
    write_physical(s, physical(segment, offset), value);
}

static uint16_t read16(FixedPatternCopyState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(FixedPatternCopyState *s, uint16_t segment,
                    uint16_t offset, uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical(s, address, (uint8_t)value);
    write_physical(s, address + 1u, (uint8_t)(value >> 8));
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

static uint16_t xor8_zero_flags(uint16_t flags) {
    /* XOR DH,DH @7190; AF is undefined, so retain its prior value. */
    return (uint16_t)((flags & (uint16_t)~LOGIC) | PF | ZF);
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

static uint16_t shr16_one_flags(uint16_t flags, uint16_t before,
                                uint16_t after) {
    uint16_t out = szp16(after);
    if (before & 1u) out |= CF;
    /* For a one-bit SHR, OF is the old most-significant bit. */
    if (before & 0x8000u) out |= OF;
    return (uint16_t)((flags & (uint16_t)~LOGIC) | out);
}

static uint16_t mul16_flags(uint16_t flags, uint32_t product) {
    /* MUL defines only CF and OF; other arithmetic flags are undefined. */
    uint16_t out = 0u;
    if ((product >> 16) != 0u) out = CF | OF;
    return (uint16_t)((flags & (uint16_t)~(CF | OF)) | out);
}

static void push_word(FixedPatternCopyState *s, uint16_t value) {
    s->sp = (uint16_t)(s->sp - 2u);
    write16(s, s->ss, s->sp, value);
}

static uint16_t pop_word(FixedPatternCopyState *s) {
    uint16_t value = read16(s, s->ss, s->sp);
    s->sp = (uint16_t)(s->sp + 2u);
    return value;
}

static void out_word(FixedPatternCopyState *s) {
    if (s->bus && s->bus->out_word)
        s->bus->out_word(s->bus->context, s->dx, s->ax, s->flags);
}

static int string_direction(const FixedPatternCopyState *s) {
#if FIXED_PATTERN_COPY_MUTATION == 3
    (void)s;
    return 1;
#else
    return (s->flags & DF) ? -1 : 1;
#endif
}

static void movsb(FixedPatternCopyState *s) {
    uint8_t value;
    int direction = string_direction(s);
#if FIXED_PATTERN_COPY_MUTATION == 7
    /* Use backing RAM for the value, then report write before source read. */
    value = s->memory[physical(s->ds, s->si)];
    write8(s, s->es, s->di, value);
    (void)read8(s, s->ds, s->si);
#else
    value = read8(s, s->ds, s->si);                  /* source read first */
    write8(s, s->es, s->di, value);                  /* destination write */
#endif
    s->si = (uint16_t)(s->si + direction);
    s->di = (uint16_t)(s->di + direction);
}

static void add_first_row_pitch(FixedPatternCopyState *s) {
    uint16_t pitch = 0x29u;
#if FIXED_PATTERN_COPY_MUTATION == 4
    pitch = 0x28u;
#endif
    {
        uint16_t before = s->di;
        s->di = (uint16_t)(before + pitch);
        s->flags = add16_flags(s->flags, before, pitch); /* ADD DI,29 @7185 */
    }
}

static void add_second_row_pitch(FixedPatternCopyState *s) {
    uint16_t pitch = 0x29u;
#if FIXED_PATTERN_COPY_MUTATION == 8
    pitch = 0x28u;
#endif
    {
        uint16_t before = s->si;
        s->si = (uint16_t)(before + pitch);
        s->flags = add16_flags(s->flags, before, pitch); /* ADD SI,29 @71C1 */
    }
}

static void copy_first_pass(FixedPatternCopyState *s) {
    s->cx = 0x10u;                                    /* MOV CX,10 @717F */
    do {
        movsb(s);                                     /* MOVSB @7182 */
        movsb(s);                                     /* MOVSB @7183 */
        movsb(s);                                     /* MOVSB @7184 */
        add_first_row_pitch(s);
        s->cx = (uint16_t)(s->cx - 1u);               /* LOOP @7188 */
    } while (s->cx != 0u);
}

static void copy_second_pass(FixedPatternCopyState *s) {
    s->cx = 0x10u;                                    /* MOV CX,10 @71BB */
    do {
        movsb(s);                                     /* MOVSB @71BE */
        movsb(s);                                     /* MOVSB @71BF */
        movsb(s);                                     /* MOVSB @71C0 */
        add_second_row_pitch(s);
        s->cx = (uint16_t)(s->cx - 1u);               /* LOOP @71C4 */
    } while (s->cx != 0u);
}

static void initialize(FixedPatternCopyState *s, uint8_t *memory,
                       const LmnFixedPatternCopyCall *call,
                       const LmnRasterBus *bus) {
    s->memory = memory;
    s->bus = bus;
    s->ax = call->ax; s->bx = call->bx; s->cx = call->cx;
    s->dx = call->dx; s->si = call->si; s->di = call->di;
    s->bp = call->bp; s->cs = call->code_segment;
    s->ds = call->data_segment; s->es = call->extra_segment;
    s->ss = call->stack_segment; s->sp = call->stack_offset;
    s->flags = call->flags;
    s->continuation = FIXED_PATTERN_COPY_RET;
    s->status = LMN_FIXED_PATTERN_COPY_READY;
}

static LmnFixedPatternCopyResult result_of(const FixedPatternCopyState *s) {
    LmnFixedPatternCopyResult out;
    out.ax = s->ax; out.bx = s->bx; out.cx = s->cx;
    out.dx = s->dx; out.si = s->si; out.di = s->di; out.bp = s->bp;
    out.code_segment = s->cs; out.data_segment = s->ds;
    out.extra_segment = s->es; out.stack_segment = s->ss;
    out.stack_offset = s->sp; out.flags = s->flags;
    out.continuation = s->continuation; out.status = s->status;
    return out;
}

LmnFixedPatternCopyResult lmn_copy_fixed_pattern_vga_spans_core(
    uint8_t *memory, const LmnFixedPatternCopyCall *call,
    const LmnRasterBus *bus) {
    FixedPatternCopyState s;
#if FIXED_PATTERN_COPY_MUTATION == 6
    uint16_t saved_quotient;
#endif
    initialize(&s, memory, call, bus);

    s.bp = s.ds;                                      /* MOV BP,DS @715F */
#if FIXED_PATTERN_COPY_MUTATION != 1
    s.flags = (uint16_t)(s.flags & (uint16_t)~IF);    /* CLI @7161 */
#endif
    s.dx = VGA_SEQUENCER;                             /* MOV DX,3C4 @7162 */
    s.ax = 0x0f02u;                                   /* MOV AX,0F02 @7165 */
    out_word(&s);                                     /* OUT DX,AX @7168 */
    s.dx = VGA_GRAPHICS_CONTROLLER;                   /* MOV DX,3CE @7169 */
    s.ax = 0x0105u;                                   /* MOV AX,0105 @716C */
    out_word(&s);                                     /* OUT DX,AX @716F */
#if FIXED_PATTERN_COPY_MUTATION == 2
    s.si = read16(&s, s.ds, FIXED_PATTERN_FIRST_DESTINATION); /* wrong order */
    s.di = read16(&s, s.ds, FIXED_PATTERN_SOURCE);
#else
    s.di = read16(&s, s.ds, FIXED_PATTERN_FIRST_DESTINATION); /* MOV DI,[E] */
    s.si = read16(&s, s.ds, FIXED_PATTERN_SOURCE);             /* MOV SI,[A] */
#endif
    s.dx = VGA_APERTURE;                              /* MOV DX,A000 @7178 */
    s.es = s.dx;                                      /* MOV ES,DX @717B */
    s.ds = s.dx;                                      /* MOV DS,DX @717D */
    copy_first_pass(&s);

    s.ds = s.bp;                                      /* MOV DS,BP @718A */
    s.dx = (uint16_t)((s.dx & 0xff00u) |
        read8(&s, s.ds, FIXED_PATTERN_BIAS));         /* MOV DL,[1FE0] @718C */
    s.dx = (uint16_t)(s.dx & 0x00ffu);                /* XOR DH,DH @7190 */
    s.flags = xor8_zero_flags(s.flags);
    {
        uint16_t pointer_x = read16(&s, s.ds, FIXED_PATTERN_POINTER_X);
        uint16_t before = s.dx;
        s.dx = (uint16_t)(before + pointer_x);        /* ADD DX,[0010] @7192 */
        s.flags = add16_flags(s.flags, before, pointer_x);
    }
    {
        unsigned i;
        for (i = 0u; i < 3u; ++i) {
            uint16_t before = s.dx;
            uint16_t after = (uint16_t)(before >> 1);
            s.dx = after;                             /* SHR DX,1 @7196/98/9A */
            s.flags = shr16_one_flags(s.flags, before, after);
        }
    }
    s.si = read16(&s, s.ds, FIXED_PATTERN_POINTER_Y); /* MOV SI,[0012] @719C */
#if FIXED_PATTERN_COPY_MUTATION == 6
    saved_quotient = s.dx;
#else
    push_word(&s, s.dx);                              /* PUSH DX @71A0 */
#endif
    s.ax = s.si;                                      /* MOV AX,SI @71A1 */
    s.si = 0x002cu;                                   /* MOV SI,2C @71A3 */
    {
        uint32_t product = (uint32_t)s.ax * (uint32_t)s.si;
        s.ax = (uint16_t)product;
        s.dx = (uint16_t)(product >> 16);             /* MUL SI @71A6 */
        s.flags = mul16_flags(s.flags, product);
    }
    s.si = s.ax;                                      /* MOV SI,AX @71A8 */
#if FIXED_PATTERN_COPY_MUTATION == 6
    s.dx = saved_quotient;                            /* omits live PUSH/POP DX */
#else
    s.dx = pop_word(&s);                              /* POP DX @71AA */
#endif
    {
        uint16_t before = s.si;
        s.si = (uint16_t)(before + s.dx);             /* ADD SI,DX @71AB */
        s.flags = add16_flags(s.flags, before, s.dx);
    }
    {
        uint16_t origin = read16(&s, s.ds,
                                  SEG09A9_AlternateDrawingOrigin);
        uint16_t before = s.si;
        s.si = (uint16_t)(before + origin);           /* ADD SI,[1F78] @71AD */
        s.flags = add16_flags(s.flags, before, origin);
    }
    write16(&s, s.ds, FIXED_PATTERN_SECOND_SOURCE, s.si); /* MOV [000C],SI @71B1 */
    s.di = read16(&s, s.ds, FIXED_PATTERN_SECOND_DESTINATION); /* @71B5 */
    push_word(&s, s.es);                              /* PUSH ES @71B9 */
#if FIXED_PATTERN_COPY_MUTATION == 5
    (void)pop_word(&s);
    s.ds = VGA_APERTURE;                              /* bypasses live stack data */
#else
    s.ds = pop_word(&s);                              /* POP DS @71BA */
#endif
    copy_second_pass(&s);
#if FIXED_PATTERN_COPY_MUTATION != 9
    s.flags = (uint16_t)(s.flags | IF);               /* STI @71C6 */
#endif
    s.ds = s.bp;                                      /* MOV DS,BP @71C7 */
    return result_of(&s);                             /* before RET @71C9 */
}

static void apply_result(LmnRegs *r,
                         const LmnFixedPatternCopyResult *out) {
    r->ax = out->ax; r->bx = out->bx; r->cx = out->cx;
    r->dx = out->dx; r->si = out->si; r->di = out->di;
    r->bp = out->bp; r->cs = out->code_segment;
    r->ds = out->data_segment; r->es = out->extra_segment;
    r->ss = out->stack_segment; r->sp = out->stack_offset;
    r->flags = out->flags; r->ip = out->continuation;
}

#if FIXED_PATTERN_COPY_MUTATION != 10
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
#endif

uint16_t lmn_copy_fixed_pattern_vga_spans_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnFixedPatternCopyCall call;
    LmnFixedPatternCopyResult out;
    call.ax = registers->ax; call.bx = registers->bx;
    call.cx = registers->cx; call.dx = registers->dx;
    call.si = registers->si; call.di = registers->di;
    call.bp = registers->bp; call.code_segment = registers->cs;
    call.data_segment = registers->ds; call.extra_segment = registers->es;
    call.stack_segment = registers->ss; call.stack_offset = registers->sp;
    call.flags = registers->flags;
    out = lmn_copy_fixed_pattern_vga_spans_core(memory, &call, bus);
    apply_result(registers, &out);
    if (out.status == LMN_FIXED_PATTERN_COPY_READY) {
#if FIXED_PATTERN_COPY_MUTATION == 10
        registers->ip = out.continuation;
#else
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
        registers->sp = (uint16_t)(registers->sp + 2u);
#endif
    }
    return out.status;
}
