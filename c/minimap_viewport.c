#include "minimap_viewport.h"
#include "lemmings_sym.h"

#ifndef MINIMAP_VIEWPORT_MUTATION
#define MINIMAP_VIEWPORT_MUTATION 0
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
    INC_FLAGS = PF | AF | ZF | SF | OF
};

typedef struct ViewportState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
#if MINIMAP_VIEWPORT_MUTATION == 3
    uint16_t pushed_ax;
#endif
} ViewportState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_physical(ViewportState *state, uint32_t address) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->read_byte)
        return state->bus->read_byte(state->bus->context, state->memory,
                                     address, state->flags);
    return state->memory[address];
}

static void write_physical(ViewportState *state, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->write_byte)
        state->bus->write_byte(state->bus->context, state->memory, address,
                               value, state->flags);
    else
        state->memory[address] = value;
}

static uint16_t read16(ViewportState *state, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(state, address);
    uint8_t high = read_physical(state, (address + 1u) & MEMORY_MASK);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(ViewportState *state, uint16_t segment,
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

static uint16_t szp16(uint16_t value) {
    uint16_t flags = 0;
    if (even_parity((uint8_t)value)) flags |= PF;
    if (value == 0) flags |= ZF;
    if (value & 0x8000u) flags |= SF;
    return flags;
}

static uint16_t logic16_flags(uint16_t flags, uint16_t value) {
    /* AND leaves AF undefined; retaining it keeps the callback value stable. */
    return (uint16_t)((flags & (uint16_t)~(CF | PF | ZF | SF | OF)) |
                      szp16(value));
}

#if MINIMAP_VIEWPORT_MUTATION == 4
static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    uint16_t szp = 0;
    if (even_parity(value)) szp |= PF;
    if (value == 0) szp |= ZF;
    if (value & 0x80u) szp |= SF;
    return (uint16_t)((flags & (uint16_t)~(CF | PF | ZF | SF | OF)) | szp);
}
#endif

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t wide = (uint32_t)left + right;
    uint16_t result = (uint16_t)wide;
    uint16_t arithmetic = szp16(result);
    if (wide > 0xffffu) arithmetic |= CF;
    if ((left ^ right ^ result) & AF) arithmetic |= AF;
    if (((uint16_t)~(left ^ right) & (left ^ result) & 0x8000u) != 0)
        arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

static uint16_t sub16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint16_t result = (uint16_t)(left - right);
    uint16_t arithmetic = szp16(result);
    if (left < right) arithmetic |= CF;
    if ((left ^ right ^ result) & AF) arithmetic |= AF;
    if (((left ^ right) & (left ^ result) & 0x8000u) != 0)
        arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

static uint16_t shr16_flags(uint16_t flags, uint16_t before) {
    uint16_t result = (uint16_t)(before >> 1);
    uint16_t arithmetic = szp16(result);
    if (before & 1u) arithmetic |= CF;
    if (before & 0x8000u) arithmetic |= OF;
    /* SHR leaves AF undefined; preserve its previous value. */
    flags = (uint16_t)(flags & (uint16_t)~(CF | PF | ZF | SF | OF));
    return (uint16_t)(flags | arithmetic);
}

static uint16_t rcr16_flags(uint16_t flags, uint16_t before,
                            unsigned carry_in) {
    unsigned carry_out = before & 1u;
    unsigned msb = carry_in;
    unsigned next_msb = (before >> 15) & 1u;
    uint16_t defined = (uint16_t)((carry_out ? CF : 0u) |
                                  ((msb ^ next_msb) ? OF : 0u));
    return (uint16_t)((flags & (uint16_t)~(CF | OF)) | defined);
}

static uint16_t dec8_flags(uint16_t flags, uint8_t before) {
    uint8_t result = (uint8_t)(before - 1u);
    uint16_t arithmetic = 0;
    if (even_parity(result)) arithmetic |= PF;
    if (result == 0) arithmetic |= ZF;
    if (result & 0x80u) arithmetic |= SF;
    if ((before & 0x0fu) == 0) arithmetic |= AF;
    if (before == 0x80u) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

static uint16_t dec16_flags(uint16_t flags, uint16_t before) {
    uint16_t result = (uint16_t)(before - 1u);
    uint16_t arithmetic = szp16(result);
    if ((before & 0x000fu) == 0) arithmetic |= AF;
    if (before == 0x8000u) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

static void add_di(ViewportState *state, uint16_t amount) {
    uint16_t before = state->di;
    state->di = (uint16_t)(before + amount);
    state->flags = add16_flags(state->flags, before, amount);
}

static void sub_di(ViewportState *state, uint16_t amount) {
    uint16_t before = state->di;
    state->di = (uint16_t)(before - amount);
    state->flags = sub16_flags(state->flags, before, amount);
}

static void shr_register16(uint16_t *reg, uint16_t *flags) {
    uint16_t before = *reg;
    *reg = (uint16_t)(before >> 1);
    *flags = shr16_flags(*flags, before);
}

static void rcr_register16(uint16_t *reg, uint16_t *flags) {
    uint16_t before = *reg;
    unsigned carry_in = (*flags & CF) != 0;
#if MINIMAP_VIEWPORT_MUTATION == 8
    carry_in = 0;
#endif
    *reg = (uint16_t)((before >> 1) | (carry_in ? 0x8000u : 0u));
    *flags = rcr16_flags(*flags, before, carry_in);
}

static void set_al(ViewportState *state, uint8_t value) {
    state->ax = (uint16_t)((state->ax & 0xff00u) | value);
}

static void set_ah(ViewportState *state, uint8_t value) {
    state->ax = (uint16_t)((state->ax & 0x00ffu) |
                           ((uint16_t)value << 8));
}

static uint8_t get_al(const ViewportState *state) {
    return (uint8_t)state->ax;
}

static void port_word(ViewportState *state) {
    if (state->bus && state->bus->out_word)
        state->bus->out_word(state->bus->context, state->dx, state->ax,
                             state->flags);
}

static void mirror_and_out(ViewportState *state) {
    write16(state, state->ss, 0x000eu, state->ax);
    port_word(state);
}

static uint8_t read_pixel_latch(ViewportState *state) {
    uint32_t address = physical(state->es, state->di);
#if MINIMAP_VIEWPORT_MUTATION == 6
    /* Mutant: bypass the VGA read/latch phase but keep RAM observations. */
    return state->memory[address];
#else
    return read_physical(state, address);
#endif
}

static void stosb(ViewportState *state) {
    uint16_t offset = state->di;
    uint32_t address = physical(state->es, offset);
    write_physical(state, address, get_al(state));
#if MINIMAP_VIEWPORT_MUTATION == 5
    state->di = (uint16_t)(offset + 1u);
#else
    state->di = (uint16_t)(offset + ((state->flags & DF) ? -1 : 1));
#endif
}

static void write_viewport_byte(ViewportState *state, uint8_t mask,
                                unsigned read_into_ah) {
    set_al(state, 0x08u);                            /* MOV AL,08h */
    set_ah(state, mask);                             /* MOV AH,mask */
    mirror_and_out(state);                           /* MOV [SS:E],AX; OUT DX,AX */
    state->flags &= (uint16_t)~IF;                   /* CLI */
    if (read_into_ah)                               /* MOV AH,[ES:DI] */
        set_ah(state, read_pixel_latch(state));
    else                                            /* MOV AL,[ES:DI] */
        set_al(state, read_pixel_latch(state));
    set_al(state, mask);                             /* MOV AL,mask */
    stosb(state);                                    /* STOSB, DF controls DI */
    state->flags |= IF;                              /* STI */
}

static void shift_pair(ViewportState *state) {
    shr_register16(&state->cx, &state->flags);
    rcr_register16(&state->bx, &state->flags);
    {
        uint8_t before = get_al(state);
        set_al(state, (uint8_t)(before - 1u));
        state->flags = dec8_flags(state->flags, before);
    }
}

static void push_ax(ViewportState *state) {
    state->sp = (uint16_t)(state->sp - 2u);
    write16(state, state->ss, state->sp, state->ax);
}

static uint16_t pop_ax(ViewportState *state) {
    uint16_t value = read16(state, state->ss, state->sp);
    state->sp = (uint16_t)(state->sp + 2u);
    return value;
}

static LmnMinimapViewportResult result_of(const ViewportState *state) {
    LmnMinimapViewportResult result;
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

LmnMinimapViewportResult lmn_draw_minimap_viewport_core(uint8_t *memory,
    const LmnMinimapViewportCall *call, const LmnRasterBus *bus) {
    ViewportState state;
    uint16_t source_origin;
    uint16_t drawing_origin;
    unsigned shift_count, iteration;

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
    state.continuation = CS_MinimapViewportReturn;
    state.status = LMN_MINIMAP_VIEWPORT_READY;
#if MINIMAP_VIEWPORT_MUTATION == 3
    state.pushed_ax = 0;
#endif

    source_origin = read16(&state, state.ds, 0x0000u);
    state.di = source_origin;                         /* MOV DI,[DS:0000] */
#if MINIMAP_VIEWPORT_MUTATION == 1
    shift_count = 8;
#else
    shift_count = 7;
#endif
    for (iteration = 0; iteration < shift_count; ++iteration)
        shr_register16(&state.di, &state.flags);      /* seven SHR DI,1 */
    add_di(&state, 0x2172u);                          /* ADD DI,2172h */
    drawing_origin = read16(&state, state.ds, SEG09A9_DrawingOrigin);
    add_di(&state, drawing_origin);                   /* ADD DI,[DrawingOrigin] */
    add_di(&state, 0x0002u);                          /* ADD DI,+2 */

    state.dx = 0xa000u;                               /* MOV DX,A000; MOV ES,DX */
    state.es = state.dx;
    state.dx = 0x03c4u;                               /* MOV DX,3C4 */
    state.ax = 0x0f02u;                               /* MOV AX,0F02 */
    write16(&state, state.ss, 0x0008u, state.ax);
    port_word(&state);                                /* OUT DX,AX */

    state.dx = 0x03ceu;                               /* MOV DX,3CE */
    state.ax = 0;
    state.flags = logic16_flags(state.flags, state.ax);/* XOR AX,AX */
#if MINIMAP_VIEWPORT_MUTATION == 7
    state.ax = 1u;                                     /* Wrong valid GC index. */
#endif
    write16(&state, state.ss, 0x000au, state.ax);
    port_word(&state);
    state.ax = 0x0c01u;
    write16(&state, state.ss, 0x000cu, state.ax);
    port_word(&state);
    state.ax = 0x0005u;
    write16(&state, state.ss, 0x0000u, state.ax);
    port_word(&state);
    state.ax = 0x0003u;
    write16(&state, state.ss, 0x0002u, state.ax);
    port_word(&state);

    state.cx = 0xffffu;                               /* MOV CX,FFFF */
    state.bx = 0xff00u;                               /* MOV BX,FF00 */
#if MINIMAP_VIEWPORT_MUTATION == 2
    state.ax = source_origin;                          /* Cached first DS:0000 read. */
#else
    state.ax = read16(&state, state.ds, 0x0000u);     /* MOV AX,[DS:0000] */
#endif
    for (iteration = 0; iteration < 4u; ++iteration)
        shr_register16(&state.ax, &state.flags);      /* four SHR AX,1 */
    state.ax &= 0x0007u;                              /* AND AX,7 */
    state.flags = logic16_flags(state.flags, state.ax);
#if MINIMAP_VIEWPORT_MUTATION == 3
    state.pushed_ax = state.ax;
#endif
    push_ax(&state);                                  /* PUSH AX */
    if (!(state.flags & ZF)) {
        do {
            shift_pair(&state);                       /* SHR CX; RCR BX; DEC AL */
        } while (!(state.flags & ZF));
    }

    write_viewport_byte(&state, (uint8_t)(state.cx >> 8), 0);
    write_viewport_byte(&state, (uint8_t)state.cx, 1);
    write_viewport_byte(&state, (uint8_t)(state.bx >> 8), 1);
    write_viewport_byte(&state, (uint8_t)state.bx, 1);

    add_di(&state, 0x0340u);                          /* ADD DI,340h */
    write_viewport_byte(&state, (uint8_t)(state.cx >> 8), 0);
    write_viewport_byte(&state, (uint8_t)state.cx, 1);
    write_viewport_byte(&state, (uint8_t)(state.bx >> 8), 1);
    write_viewport_byte(&state, (uint8_t)state.bx, 1);
    sub_di(&state, 0x0030u);                          /* SUB DI,30h */

    state.cx = 0x8000u;                               /* MOV CX,8000 */
    state.bx = 0x0100u;                               /* MOV BX,0100 */
    state.ax = pop_ax(&state);                        /* POP AX from live SS */
#if MINIMAP_VIEWPORT_MUTATION == 3
    state.ax = state.pushed_ax;                       /* Cache ignores live POP value. */
#endif
#if MINIMAP_VIEWPORT_MUTATION == 4
    state.flags = logic8_flags(state.flags, get_al(&state));
#else
    state.flags = logic16_flags(state.flags, state.ax);/* AND AX,AX */
#endif
    if (!(state.flags & ZF)) {
        do {
            shift_pair(&state);                       /* 256 iterations if AH!=0, AL=0 */
        } while (!(state.flags & ZF));
    }

    state.bp = 0x0012u;                               /* MOV BP,12h */
    do {
        write_viewport_byte(&state, (uint8_t)(state.cx >> 8), 0);
        write_viewport_byte(&state, (uint8_t)state.cx, 0);
        write_viewport_byte(&state, (uint8_t)(state.bx >> 8), 0);
        write_viewport_byte(&state, (uint8_t)state.bx, 0);
        sub_di(&state, 0x0030u);                      /* SUB DI,30h */
        {
            uint16_t before = state.bp;
            state.bp = (uint16_t)(before - 1u);
            state.flags = dec16_flags(state.flags, before);
        }
    } while (!(state.flags & ZF));                    /* JNZ 7B6D */

    state.continuation = CS_MinimapViewportReturn;
    state.status = LMN_MINIMAP_VIEWPORT_READY;
    return result_of(&state);
}

static uint16_t read_stack_return(uint8_t *memory, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(stack_segment, stack_offset);
    uint8_t low;
    uint8_t high;
    address &= MEMORY_MASK;
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
                         const LmnMinimapViewportResult *result) {
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

uint16_t lmn_draw_minimap_viewport_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnMinimapViewportCall call;
    LmnMinimapViewportResult result;
#if MINIMAP_VIEWPORT_MUTATION == 9
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
    result = lmn_draw_minimap_viewport_core(memory, &call, bus);
    apply_result(registers, &result);

    if (result.status == LMN_MINIMAP_VIEWPORT_READY) {
#if MINIMAP_VIEWPORT_MUTATION == 9
        registers->ip = prefetched_return;
#else
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
#endif
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return result.status;
}
