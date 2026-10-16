#include "status_glyph.h"
#include "lemmings_sym.h"

#ifndef STATUS_GLYPH_MUTATION
#define STATUS_GLYPH_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffff,
    CF = 0x0001,
    PF = 0x0004,
    AF = 0x0010,
    ZF = 0x0040,
    SF = 0x0080,
    IF = 0x0200,
    DF = 0x0400,
    OF = 0x0800,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    LOGIC_FLAGS = CF | PF | ZF | SF | OF
};

typedef struct StatusGlyphState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
#if STATUS_GLYPH_MUTATION == 2
    uint16_t pushed_di;
#endif
} StatusGlyphState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(StatusGlyphState *state, uint32_t address) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->read_byte)
        return state->bus->read_byte(state->bus->context, state->memory,
                                     address, state->flags);
    return state->memory[address];
}

static void write_physical(StatusGlyphState *state, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->write_byte)
        state->bus->write_byte(state->bus->context, state->memory, address,
                               value, state->flags);
    else
        state->memory[address] = value;
}

static uint8_t read8(StatusGlyphState *state, uint16_t segment,
                     uint16_t offset) {
    return read_physical(state, physical(segment, offset));
}

static void write8(StatusGlyphState *state, uint16_t segment,
                    uint16_t offset, uint8_t value) {
    write_physical(state, physical(segment, offset), value);
}

static uint16_t read16(StatusGlyphState *state, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(state, address);
    uint8_t high = read_physical(state, (address + 1u) & MEMORY_MASK);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(StatusGlyphState *state, uint16_t segment,
                    uint16_t offset, uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical(state, address, (uint8_t)value);
    write_physical(state, (address + 1u) & MEMORY_MASK,
                   (uint8_t)(value >> 8));
}

static unsigned even_parity(uint8_t value) {
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones += (value >> bit) & 1u;
    return (ones & 1u) == 0;
}

static uint16_t szp8(uint8_t value) {
    uint16_t flags = 0;
    if (even_parity(value)) flags |= PF;
    if (value == 0) flags |= ZF;
    if (value & 0x80u) flags |= SF;
    return flags;
}

static uint16_t szp16(uint16_t value) {
    uint16_t flags = 0;
    if (even_parity((uint8_t)value)) flags |= PF;
    if (value == 0) flags |= ZF;
    if (value & 0x8000u) flags |= SF;
    return flags;
}

/* Logic instructions leave AF undefined; retain it for stable bus values. */
static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    return (uint16_t)((flags & (uint16_t)~LOGIC_FLAGS) | szp8(value));
}

static uint16_t logic16_flags(uint16_t flags, uint16_t value) {
    return (uint16_t)((flags & (uint16_t)~LOGIC_FLAGS) | szp16(value));
}

static uint16_t add_flags(uint16_t flags, uint16_t left, uint16_t right,
                          unsigned bits) {
    uint32_t mask = bits == 8u ? 0xffu : 0xffffu;
    uint32_t l = left & mask;
    uint32_t r = right & mask;
    uint32_t sum = l + r;
    uint16_t result = (uint16_t)(sum & mask);
    uint16_t arithmetic = bits == 8u ? szp8((uint8_t)result) : szp16(result);
    uint32_t sign = 1u << (bits - 1u);
    if (sum > mask) arithmetic |= CF;
    if ((l ^ r ^ result) & AF) arithmetic |= AF;
    if (((~(l ^ r) & (l ^ result)) & sign) != 0) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

static uint16_t sub_flags(uint16_t flags, uint16_t left, uint16_t right,
                          unsigned bits) {
    uint32_t mask = bits == 8u ? 0xffu : 0xffffu;
    uint16_t l = (uint16_t)(left & mask);
    uint16_t r = (uint16_t)(right & mask);
    uint16_t result = (uint16_t)((l - r) & mask);
    uint16_t arithmetic = bits == 8u ? szp8((uint8_t)result) : szp16(result);
    uint32_t sign = 1u << (bits - 1u);
    if (l < r) arithmetic |= CF;
    if ((l ^ r ^ result) & AF) arithmetic |= AF;
    if ((((l ^ r) & (l ^ result)) & sign) != 0) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

static uint8_t al(const StatusGlyphState *state) {
    return (uint8_t)state->ax;
}

static uint8_t ah(const StatusGlyphState *state) {
    return (uint8_t)(state->ax >> 8);
}

static void set_al(StatusGlyphState *state, uint8_t value) {
    state->ax = (uint16_t)((state->ax & 0xff00u) | value);
}

static void set_ah(StatusGlyphState *state, uint8_t value) {
    state->ax = (uint16_t)((state->ax & 0x00ffu) |
                           ((uint16_t)value << 8));
}

static void add_di(StatusGlyphState *state, uint16_t amount) {
    uint16_t before = state->di;
    state->di = (uint16_t)(before + amount);
    state->flags = add_flags(state->flags, before, amount, 16u);
}

static void add_si(StatusGlyphState *state, uint16_t amount) {
    uint16_t before = state->si;
    state->si = (uint16_t)(before + amount);
    state->flags = add_flags(state->flags, before, amount, 16u);
}

static void shl_ax(StatusGlyphState *state) {
    uint16_t before = state->ax;
    uint16_t result = (uint16_t)(before << 1);
    uint16_t arithmetic = szp16(result);
    unsigned carry = (before >> 15) & 1u;
    if (carry) arithmetic |= CF;
    if ((((result >> 15) & 1u) ^ carry) != 0u) arithmetic |= OF;
    state->ax = result;
    state->flags = (uint16_t)((state->flags &
        (uint16_t)~(CF | PF | ZF | SF | OF)) | arithmetic);
}

static void push_word(StatusGlyphState *state, uint16_t value) {
    state->sp = (uint16_t)(state->sp - 2u);
    write16(state, state->ss, state->sp, value);
}

static uint16_t pop_word(StatusGlyphState *state) {
    uint16_t value = read16(state, state->ss, state->sp);
    state->sp = (uint16_t)(state->sp + 2u);
    return value;
}

static void port_word(StatusGlyphState *state) {
    if (state->bus && state->bus->out_word)
        state->bus->out_word(state->bus->context, state->dx, state->ax,
                             state->flags);
}

static void mirror_and_out(StatusGlyphState *state, uint16_t offset) {
    write16(state, state->ss, offset, state->ax);
    port_word(state);
}

static void cli(StatusGlyphState *state) {
    state->flags = (uint16_t)(state->flags & (uint16_t)~IF);
}

static void sti(StatusGlyphState *state) {
    state->flags |= IF;
}

static void lodsb(StatusGlyphState *state) {
    uint16_t offset = state->si;
    uint8_t value = read8(state, state->ds, offset);
    set_al(state, value);
#if STATUS_GLYPH_MUTATION == 6
    state->si = (uint16_t)(offset + 1u);
#else
    state->si = (uint16_t)(offset + ((state->flags & DF) ? -1 : 1));
#endif
}

static void stosb(StatusGlyphState *state) {
    uint16_t offset = state->di;
    write8(state, state->es, offset, al(state));
#if STATUS_GLYPH_MUTATION == 6
    state->di = (uint16_t)(offset + 1u);
#else
    state->di = (uint16_t)(offset + ((state->flags & DF) ? -1 : 1));
#endif
}

static void loop_dec(StatusGlyphState *state) {
    state->cx = (uint16_t)(state->cx - 1u);
}

static void draw_glyph_pass(StatusGlyphState *state, unsigned save_di) {
    unsigned iteration;
    if (save_di) {
#if STATUS_GLYPH_MUTATION == 2
        state->pushed_di = state->di;
#endif
        push_word(state, state->di);                  /* PUSH DI */
    }
    state->cx = 0x0010u;                              /* MOV CX,10h */
    for (iteration = 0; iteration < 16u; ++iteration) {
        cli(state);                                   /* CLI */
        set_al(state, read8(state, state->es, state->di)); /* MOV AL,[ES:DI] */
        lodsb(state);                                 /* LODSB */
        stosb(state);                                 /* STOSB */
        sti(state);                                   /* STI */
        add_di(state, 0x002bu);                       /* ADD DI,2Bh */
        loop_dec(state);                              /* LOOP */
    }
    if (save_di) {
        uint16_t restored = pop_word(state);          /* POP DI from live SS */
#if STATUS_GLYPH_MUTATION == 2
        (void)restored;
        state->di = state->pushed_di;
#else
        state->di = restored;
#endif
    }
}

static void draw_blank_space(StatusGlyphState *state) {
    unsigned iteration;
    set_al(state, 0);                                 /* XOR AL,AL result */
    state->flags = logic8_flags(state->flags, 0);
    state->cx = 0x0010u;                              /* MOV CX,10h */
    for (iteration = 0; iteration < 16u; ++iteration) {
        cli(state);                                   /* CLI */
#if STATUS_GLYPH_MUTATION == 5
        (void)read8(state, state->es, state->di);     /* Extra latch read. */
#endif
        stosb(state);                                 /* STOSB */
        sti(state);                                   /* STI */
        add_di(state, 0x002bu);                       /* ADD DI,2Bh */
        loop_dec(state);                              /* LOOP */
    }
}

static LmnStatusGlyphResult result_of(const StatusGlyphState *state) {
    LmnStatusGlyphResult result;
    result.value = state->ax;
    result.map_cursor = state->bx;
    result.count = state->cx;
    result.auxiliary_value = state->dx;
    result.record_cursor = state->si;
    result.object_cursor = state->di;
    result.candidate_y = state->bp;
    result.code_segment = state->cs;
    result.data_segment = state->ds;
    result.extra_segment = state->es;
    result.stack_segment = state->ss;
    result.stack_offset = state->sp;
    result.flags = state->flags;
    result.continuation = state->continuation;
    result.status = state->status;
    return result;
}

static int signed_ge(const StatusGlyphState *state) {
    return ((state->flags & SF) != 0) == ((state->flags & OF) != 0);
}

static int signed_g(const StatusGlyphState *state) {
    return !(state->flags & ZF) && signed_ge(state);
}

static int signed_le(const StatusGlyphState *state) {
    return (state->flags & ZF) || !signed_ge(state);
}

LmnStatusGlyphResult lmn_draw_status_glyph_core(uint8_t *memory,
    const LmnStatusGlyphCall *call, const LmnRasterBus *bus) {
    StatusGlyphState state;
#if STATUS_GLYPH_MUTATION == 1
    uint16_t saved_ax;
#endif
    uint16_t drawing_origin;
    uint8_t selector;

    state.memory = memory;
    state.bus = bus;
    state.ax = call->value;
    state.bx = call->map_cursor;
    state.cx = call->count;
    state.dx = call->auxiliary_value;
    state.si = call->record_cursor;
    state.di = call->object_cursor;
    state.bp = call->candidate_y;
    state.cs = call->code_segment;
    state.ds = call->data_segment;
    state.es = call->extra_segment;
    state.ss = call->stack_segment;
    state.sp = call->stack_offset;
    state.flags = call->flags;
    state.continuation = CS_StatusGlyphReturn;
    state.status = LMN_STATUS_GLYPH_READY;

#if STATUS_GLYPH_MUTATION == 1
    saved_ax = state.ax;
#endif
    push_word(&state, state.ds);                       /* PUSH DS */
    push_word(&state, state.ax);                       /* PUSH AX */
    set_al(&state, ah(&state));                        /* MOV AL,AH */
    set_ah(&state, 0);                                 /* XOR AH,AH */
    state.flags = logic8_flags(state.flags, 0);
    state.di = state.ax;                               /* MOV DI,AX */
    add_di(&state, 0x1e40u);                           /* ADD DI,1E40h */
    drawing_origin = read16(&state, state.ds, SEG09A9_DrawingOrigin);
    add_di(&state, drawing_origin);                    /* ADD DI,[DrawingOrigin] */
    add_di(&state, 0x0002u);                           /* ADD DI,+2 */

    state.dx = 0xa000u;                                /* MOV DX,A000; MOV ES,DX */
    state.es = state.dx;
    state.dx = 0x03c4u;                                /* MOV DX,3C4 */
    state.ax = 0x0f02u;                                /* MOV AX,0F02 */
    mirror_and_out(&state, 0x0008u);                   /* SS mirror; OUT */
    state.dx = 0x03ceu;                                /* MOV DX,3CE */
    state.ax = 0;
    state.flags = logic16_flags(state.flags, state.ax);/* XOR AX,AX */
    mirror_and_out(&state, 0x000au);
    state.ax = 0x0e01u;                                /* MOV AX,0E01 */
#if STATUS_GLYPH_MUTATION == 7
    state.ax = 0x0d01u;                                /* Wrong valid GC data. */
#endif
    mirror_and_out(&state, 0x000cu);
    state.ax = 0x0005u;
    mirror_and_out(&state, 0x0000u);
    state.ax = 0x0003u;
    mirror_and_out(&state, 0x0002u);
    state.ax = 0xff08u;
    mirror_and_out(&state, 0x000eu);

    state.ax = pop_word(&state);                       /* POP AX from live SS */
#if STATUS_GLYPH_MUTATION == 1
    state.ax = saved_ax;                               /* Ignore the live POP. */
#endif
    selector = al(&state);
    state.flags = sub_flags(state.flags, selector, 0x20u, 8u); /* CMP AL,20h */
    if (selector == 0x20u) {
        state.continuation = CS_StatusGlyphSpaceReturn;
        draw_blank_space(&state);                     /* JMP loc_77FE */
        state.ds = pop_word(&state);                   /* POP DS */
        return result_of(&state);
    }

    state.flags = sub_flags(state.flags, selector, 0x25u, 8u); /* CMP AL,25h */
    if (selector == 0x25u) {
        state.si = 0;                                  /* XOR SI,SI */
        state.flags = logic16_flags(state.flags, state.si);
    } else {
        state.flags = sub_flags(state.flags, selector, 0x3au, 8u); /* CMP AL,3Ah */
        if (selector == 0x3au) {
#if STATUS_GLYPH_MUTATION == 4
            state.si = 0x0211u;                        /* Wrong ':' table base. */
#else
            state.si = 0x0210u;                        /* MOV SI,210h */
#endif
        } else {
            state.flags = sub_flags(state.flags, selector, 0x30u, 8u); /* CMP */
#if STATUS_GLYPH_MUTATION == 3
            if (state.flags & CF)                      /* Mutant: JAE. */
                goto rejected_selector;
#else
            if (!signed_ge(&state))                    /* JNL loc_7777 */
                goto rejected_selector;
#endif
            state.flags = sub_flags(state.flags, selector, 0x39u, 8u); /* CMP */
            if (!signed_g(&state)) {
                set_al(&state, (uint8_t)(selector - 0x30u));
                state.flags = sub_flags(state.flags, selector, 0x30u, 8u); /* SUB */
                state.si = 0x0030u;                    /* MOV SI,30h */
                set_ah(&state, 0);
                state.flags = logic8_flags(state.flags, 0); /* XOR AH,AH */
                shl_ax(&state); shl_ax(&state); shl_ax(&state); shl_ax(&state);
                add_si(&state, state.ax);              /* ADD SI,AX */
                shl_ax(&state);                         /* SHL AX,1 */
                add_si(&state, state.ax);              /* ADD SI,AX */
            } else {
                state.flags = sub_flags(state.flags, selector, 0x41u, 8u); /* CMP */
                if (!signed_ge(&state))                /* JNL loc_779A */
                    goto rejected_selector;
                state.flags = sub_flags(state.flags, selector, 0x5au, 8u); /* CMP */
                if (!signed_le(&state))                /* JNG loc_77A1 */
                    goto rejected_selector;
                set_al(&state, (uint8_t)(selector - 0x41u));
                state.flags = sub_flags(state.flags, selector, 0x41u, 8u); /* SUB */
                state.si = 0x0240u;                    /* MOV SI,240h */
                set_ah(&state, 0);
                state.flags = logic8_flags(state.flags, 0); /* XOR AH,AH */
                shl_ax(&state); shl_ax(&state); shl_ax(&state); shl_ax(&state);
                add_si(&state, state.ax);
                shl_ax(&state);
                add_si(&state, state.ax);
            }
        }
    }

    add_si(&state, 0x00a0u);                           /* ADD SI,A0h */
    state.ds = read16(&state, state.ds, SEG09A9_StatusGlyphBufferSegment);
    draw_glyph_pass(&state, 1u);                       /* map 0F */
    state.ax = 0x0001u;                                /* MOV AX,1 */
    mirror_and_out(&state, 0x000cu);                   /* index 1 */
    state.dx = 0x03c4u;                                /* MOV DX,3C4 */
    state.ax = 0x0202u;
    mirror_and_out(&state, 0x0008u);                   /* map 02 */
    draw_glyph_pass(&state, 1u);
    state.ax = 0x0802u;
    mirror_and_out(&state, 0x0008u);                   /* map 08 */
    draw_glyph_pass(&state, 0u);                       /* final pass keeps DI */
    state.ds = pop_word(&state);                       /* POP DS */
    state.continuation = CS_StatusGlyphReturn;
    return result_of(&state);

rejected_selector:
#if STATUS_GLYPH_MUTATION == 8
    state.flags |= IF;                                 /* Wrongly set IF. */
#endif
    state.ds = pop_word(&state);                       /* POP DS */
    state.continuation = CS_StatusGlyphReturn;
    return result_of(&state);
}

static uint16_t read_stack_return(uint8_t *memory, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(stack_segment, stack_offset);
    uint8_t low;
    uint8_t high;
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

static void apply_result(LmnRegs *registers,
                         const LmnStatusGlyphResult *result) {
    registers->ax = result->value;
    registers->bx = result->map_cursor;
    registers->cx = result->count;
    registers->dx = result->auxiliary_value;
    registers->si = result->record_cursor;
    registers->di = result->object_cursor;
    registers->bp = result->candidate_y;
    registers->cs = result->code_segment;
    registers->ds = result->data_segment;
    registers->es = result->extra_segment;
    registers->ss = result->stack_segment;
    registers->sp = result->stack_offset;
    registers->flags = result->flags;
    registers->ip = result->continuation;
}

uint16_t lmn_draw_status_glyph_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus) {
    LmnStatusGlyphCall call;
    LmnStatusGlyphResult result;
#if STATUS_GLYPH_MUTATION == 9
    uint16_t prefetched_return = read_stack_return(memory, registers->ss,
        registers->sp, registers->flags, bus);
#endif

    call.value = registers->ax;
    call.map_cursor = registers->bx;
    call.count = registers->cx;
    call.auxiliary_value = registers->dx;
    call.record_cursor = registers->si;
    call.object_cursor = registers->di;
    call.candidate_y = registers->bp;
    call.code_segment = registers->cs;
    call.data_segment = registers->ds;
    call.extra_segment = registers->es;
    call.stack_segment = registers->ss;
    call.stack_offset = registers->sp;
    call.flags = registers->flags;
    result = lmn_draw_status_glyph_core(memory, &call, bus);
    apply_result(registers, &result);

    if (result.status == LMN_STATUS_GLYPH_READY) {
#if STATUS_GLYPH_MUTATION == 9
        registers->ip = prefetched_return;
#else
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
#endif
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return result.status;
}
