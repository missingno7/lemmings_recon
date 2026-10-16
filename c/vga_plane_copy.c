#include "vga_plane_copy.h"

#include "lemmings_sym.h"

#ifndef VGA_PLANE_COPY_MUTATION
#define VGA_PLANE_COPY_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, OF = 0x0800u,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF,
    VGA_APERTURE = 0xa000u,
    VGA_GRAPHICS_CONTROLLER = 0x03ceu,
    VGA_SEQUENCER = 0x03c4u,
    COPY_RET_SITE = CS_VgaPlaneCopyReturn
};

typedef struct VgaPlaneCopyState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
} VgaPlaneCopyState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(VgaPlaneCopyState *s, uint32_t address) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                 s->flags);
    return s->memory[address];
}

static void write_physical(VgaPlaneCopyState *s, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           s->flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(VgaPlaneCopyState *s, uint16_t segment,
                     uint16_t offset) {
    return read_physical(s, physical(segment, offset));
}

static void write8(VgaPlaneCopyState *s, uint16_t segment,
                    uint16_t offset, uint8_t value) {
    write_physical(s, physical(segment, offset), value);
}

static uint16_t read16(VgaPlaneCopyState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(VgaPlaneCopyState *s, uint16_t segment,
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

static uint16_t szp8(uint8_t value) {
    uint16_t out = 0u;
    if (even_parity8(value)) out |= PF;
    if (value == 0u) out |= ZF;
    if (value & 0x80u) out |= SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out = 0u;
    if (even_parity8((uint8_t)value)) out |= PF;
    if (value == 0u) out |= ZF;
    if (value & 0x8000u) out |= SF;
    return out;
}

static uint16_t xor_ch_zero_flags(uint16_t flags) {
    /* XOR CH,CH updates CF/PF/ZF/SF/OF; AF is undefined and left untouched. */
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

static uint16_t shl8_one_flags(uint16_t flags, uint8_t before,
                               uint8_t after) {
    uint16_t out = szp8(after);
    unsigned carry = (unsigned)(before >> 7);
    if (carry) out |= CF;
    if (((unsigned)(after >> 7) ^ carry) != 0u) out |= OF;
    return (uint16_t)((flags & (uint16_t)~LOGIC) | out);
}

static uint16_t dec8_flags(uint16_t flags, uint8_t before) {
    uint8_t result = (uint8_t)(before - 1u);
    uint16_t out = szp8(result);
    if ((before & 0x0fu) == 0u) out |= AF;
    if (before == 0x80u) out |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | out | (flags & CF));
}

static void push_word(VgaPlaneCopyState *s, uint16_t value) {
    s->sp = (uint16_t)(s->sp - 2u);
    write16(s, s->ss, s->sp, value);
}

static uint16_t pop_word(VgaPlaneCopyState *s) {
    uint16_t value = read16(s, s->ss, s->sp);
    s->sp = (uint16_t)(s->sp + 2u);
    return value;
}

#if VGA_PLANE_COPY_MUTATION == 4 || VGA_PLANE_COPY_MUTATION == 6 || \
    VGA_PLANE_COPY_MUTATION == 7
static void discard_word(VgaPlaneCopyState *s) {
    s->sp = (uint16_t)(s->sp + 2u);
}
#endif

static void out_word(VgaPlaneCopyState *s) {
    if (s->bus && s->bus->out_word)
        s->bus->out_word(s->bus->context, s->dx, s->ax, s->flags);
}

static void mirror_and_out(VgaPlaneCopyState *s, uint16_t mirror) {
#if VGA_PLANE_COPY_MUTATION == 5
    out_word(s);
    write16(s, s->ss, mirror, s->ax);
#else
    write16(s, s->ss, mirror, s->ax);
    out_word(s);
#endif
}

static void rep_movsb(VgaPlaneCopyState *s) {
    /* REP with CX=0 performs no transfers; the live offsets wrap at 16 bits. */
    while (s->cx != 0u) {
        uint8_t value = read8(s, s->ds, s->si);
        int direction;
#if VGA_PLANE_COPY_MUTATION == 3
        direction = 1;
#else
        direction = (s->flags & 0x0400u) ? -1 : 1;
#endif
        write8(s, s->es, s->di, value);
        s->si = (uint16_t)(s->si + direction);
        s->di = (uint16_t)(s->di + direction);
        s->cx = (uint16_t)(s->cx - 1u);
    }
}

static void copy_row(VgaPlaneCopyState *s) {
#if VGA_PLANE_COPY_MUTATION == 6
    uint16_t saved_bx = s->bx;
#endif
#if VGA_PLANE_COPY_MUTATION == 7
    uint16_t saved_di = s->di;
#endif
    push_word(s, s->cx);                              /* PUSH CX @580E */
    push_word(s, s->di);                              /* PUSH DI @580F */
    push_word(s, s->bx);                              /* PUSH BX @5810 */

    s->cx = (uint16_t)(s->cx & 0x00ffu);              /* XOR CH,CH @5811 */
    s->flags = xor_ch_zero_flags(s->flags);
    s->cx = (uint16_t)((s->cx & 0xff00u) | (s->bx & 0x00ffu));
    rep_movsb(s);                                     /* REP MOVSB @5815 */

#if VGA_PLANE_COPY_MUTATION == 6
    discard_word(s);
    s->bx = saved_bx;
#else
    s->bx = pop_word(s);                              /* POP BX @5817 */
#endif
#if VGA_PLANE_COPY_MUTATION == 7
    discard_word(s);
    s->di = saved_di;
#else
    s->di = pop_word(s);                              /* POP DI @5818 */
#endif
    s->cx = pop_word(s);                              /* POP CX @5819 */

#if VGA_PLANE_COPY_MUTATION == 8
    {
        uint16_t before = s->di;
        s->di = (uint16_t)(before + 1u);              /* wrong fixed pitch */
        s->flags = add16_flags(s->flags, before, 1u);
    }
#else
    {
        uint16_t before = s->di;
        s->di = (uint16_t)(before + s->ax);
        s->flags = add16_flags(s->flags, before, s->ax); /* ADD DI,AX @581A */
    }
#endif
    s->cx = (uint16_t)(s->cx - 1u);                   /* LOOP @581C */
}

static void initialize(VgaPlaneCopyState *s, uint8_t *memory,
                       const LmnCopyResourcePlanesVgaCall *call,
                       const LmnRasterBus *bus) {
    s->memory = memory;
    s->bus = bus;
    s->ax = call->ax; s->bx = call->bx; s->cx = call->cx;
    s->dx = call->dx; s->si = call->si; s->di = call->di;
    s->bp = call->bp; s->cs = call->code_segment;
    s->ds = call->data_segment; s->es = call->extra_segment;
    s->ss = call->stack_segment; s->sp = call->stack_offset;
    s->flags = call->flags;
    s->continuation = COPY_RET_SITE;
    s->status = LMN_COPY_RESOURCE_PLANES_VGA_READY;
}

static LmnCopyResourcePlanesVgaResult result_of(
    const VgaPlaneCopyState *s) {
    LmnCopyResourcePlanesVgaResult out;
    out.ax = s->ax; out.bx = s->bx; out.cx = s->cx;
    out.dx = s->dx; out.si = s->si; out.di = s->di; out.bp = s->bp;
    out.code_segment = s->cs; out.data_segment = s->ds;
    out.extra_segment = s->es; out.stack_segment = s->ss;
    out.stack_offset = s->sp; out.flags = s->flags;
    out.continuation = s->continuation; out.status = s->status;
    return out;
}

LmnCopyResourcePlanesVgaResult lmn_copy_resource_planes_vga_core(
    uint8_t *memory, const LmnCopyResourcePlanesVgaCall *call,
    const LmnRasterBus *bus) {
    VgaPlaneCopyState s;
#if VGA_PLANE_COPY_MUTATION == 4
    uint16_t entry_ax;
#endif
    initialize(&s, memory, call, bus);

    push_word(&s, s.ax);                              /* PUSH AX @57D1 */
#if VGA_PLANE_COPY_MUTATION == 4
    entry_ax = s.ax;
#endif
    s.dx = VGA_APERTURE;                              /* MOV DX,A000 @57D2 */
    s.es = s.dx;                                      /* MOV ES,DX @57D5 */
    s.dx = VGA_GRAPHICS_CONTROLLER;                   /* MOV DX,3CE @57D7 */
    s.ax = 0x0001u;
    mirror_and_out(&s, SEG143E_VgaEnableSetResetMirror); /* @57DA..57E1 */
    s.ax = 0x0005u;
    mirror_and_out(&s, SEG143E_VgaGraphicsModeMirror);/* @57E2..57E9 */
    s.ax = 0x0003u;
    mirror_and_out(&s, SEG143E_VgaDataRotateMirror);  /* @57EA..57F1 */
    s.ax = 0xff08u;
    mirror_and_out(&s, SEG143E_VgaBitMaskMirror);     /* @57F2..57F9 */
#if VGA_PLANE_COPY_MUTATION == 4
    discard_word(&s);
    s.ax = entry_ax;
#else
    s.ax = pop_word(&s);                              /* POP AX @57FA */
#endif
    s.dx = 0x0102u;                                   /* MOV DX,0102 @57FB */

#if VGA_PLANE_COPY_MUTATION == 1
    if ((s.bx & 0xff00u) != 0u) {
#endif
    do {
        push_word(&s, s.di);                          /* PUSH DI @57FE */
        push_word(&s, s.cx);                          /* PUSH CX @57FF */
        push_word(&s, s.ax);                          /* PUSH AX @5800 */
        push_word(&s, s.dx);                          /* PUSH DX @5801 */
        s.ax = s.dx;                                  /* MOV AX,DX @5802 */
        s.dx = VGA_SEQUENCER;                         /* MOV DX,3C4 @5804 */
        mirror_and_out(&s, SEG143E_VgaMapMaskMirror); /* @5807..580B */
        s.dx = pop_word(&s);                          /* POP DX @580C */
        s.ax = pop_word(&s);                          /* POP AX @580D */

#if VGA_PLANE_COPY_MUTATION == 2
        if (s.cx != 0u) {
#endif
        do {
            copy_row(&s);
        } while (s.cx != 0u);
#if VGA_PLANE_COPY_MUTATION == 2
        }
#endif

        s.cx = pop_word(&s);                          /* POP CX @581E */
        s.di = pop_word(&s);                          /* POP DI @581F */
        {
            uint8_t before = (uint8_t)(s.dx >> 8);
            uint8_t after = (uint8_t)(before << 1);
            s.dx = (uint16_t)((s.dx & 0x00ffu) | ((uint16_t)after << 8));
            s.flags = shl8_one_flags(s.flags, before, after); /* SHL DH @5820 */
        }
        {
            uint8_t before = (uint8_t)(s.bx >> 8);
            uint8_t after = (uint8_t)(before - 1u);
            s.bx = (uint16_t)((s.bx & 0x00ffu) | ((uint16_t)after << 8));
            s.flags = dec8_flags(s.flags, before);     /* DEC BH @5822 */
        }
    } while ((s.bx & 0xff00u) != 0u);                 /* JNZ @5824 */
#if VGA_PLANE_COPY_MUTATION == 1
    }
#endif

    return result_of(&s);                             /* before RET @5826 */
}

static void apply_result(LmnRegs *r,
                         const LmnCopyResourcePlanesVgaResult *out) {
    r->ax = out->ax; r->bx = out->bx; r->cx = out->cx;
    r->dx = out->dx; r->si = out->si; r->di = out->di;
    r->bp = out->bp; r->cs = out->code_segment;
    r->ds = out->data_segment; r->es = out->extra_segment;
    r->ss = out->stack_segment; r->sp = out->stack_offset;
    r->flags = out->flags; r->ip = out->continuation;
}

#if VGA_PLANE_COPY_MUTATION != 10
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

uint16_t lmn_copy_resource_planes_vga_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnCopyResourcePlanesVgaCall call;
    LmnCopyResourcePlanesVgaResult out;
#if VGA_PLANE_COPY_MUTATION == 9
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
    out = lmn_copy_resource_planes_vga_core(memory, &call, bus);
    apply_result(registers, &out);
    if (out.status == LMN_COPY_RESOURCE_PLANES_VGA_READY) {
#if VGA_PLANE_COPY_MUTATION == 10
        return out.status;
#elif VGA_PLANE_COPY_MUTATION == 9
        registers->ip = prefetched_return;
#else
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
#endif
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return out.status;
}
