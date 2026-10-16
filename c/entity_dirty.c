#include "entity_dirty.h"
#include "lemmings_sym.h"

#ifndef ENTITY_DIRTY_MUTATION
#define ENTITY_DIRTY_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffff,
    CF = 0x0001,
    PF = 0x0004,
    AF = 0x0010,
    ZF = 0x0040,
    SF = 0x0080,
    OF = 0x0800,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    LOGIC_FLAGS = CF | PF | ZF | SF | OF,
    INC_FLAGS = PF | AF | ZF | SF | OF
};

typedef struct EntityDirtyState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
} EntityDirtyState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(EntityDirtyState *state, uint32_t address) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->read_byte)
        return state->bus->read_byte(state->bus->context, state->memory,
                                     address, state->flags);
    return state->memory[address];
}

static void write_physical(EntityDirtyState *state, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->write_byte)
        state->bus->write_byte(state->bus->context, state->memory, address,
                               value, state->flags);
    else
        state->memory[address] = value;
}

static uint8_t read8(EntityDirtyState *state, uint16_t segment,
                     uint16_t offset) {
    return read_physical(state, physical(segment, offset));
}

static void write8(EntityDirtyState *state, uint16_t segment,
                    uint16_t offset, uint8_t value) {
    write_physical(state, physical(segment, offset), value);
}

static uint16_t read16(EntityDirtyState *state, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(state, address);
    uint8_t high = read_physical(state, (address + 1u) & MEMORY_MASK);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(EntityDirtyState *state, uint16_t segment,
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

/* Logic leaves AF undefined; retain it for deterministic callback snapshots. */
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

static uint16_t inc_flags(uint16_t flags, uint16_t before, unsigned bits) {
    uint32_t mask = bits == 8u ? 0xffu : 0xffffu;
    uint16_t result = (uint16_t)((before + 1u) & mask);
    uint16_t arithmetic = bits == 8u ? szp8((uint8_t)result) : szp16(result);
    if ((before & 0x0fu) == 0x0fu) arithmetic |= AF;
    if (before == (bits == 8u ? 0x7fu : 0x7fffu)) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

static uint16_t dec_flags(uint16_t flags, uint16_t before, unsigned bits) {
    uint32_t mask = bits == 8u ? 0xffu : 0xffffu;
    uint16_t result = (uint16_t)((before - 1u) & mask);
    uint16_t arithmetic = bits == 8u ? szp8((uint8_t)result) : szp16(result);
    if ((before & 0x0fu) == 0u) arithmetic |= AF;
    if (before == (bits == 8u ? 0x80u : 0x8000u)) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

static uint16_t shr_flags(uint16_t flags, uint16_t before, unsigned bits) {
    uint32_t mask = bits == 8u ? 0xffu : 0xffffu;
    uint32_t sign = 1u << (bits - 1u);
    uint16_t result = (uint16_t)((before >> 1) & mask);
    uint16_t arithmetic = bits == 8u ? szp8((uint8_t)result) : szp16(result);
    if (before & 1u) arithmetic |= CF;
    if (before & sign) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~(CF | PF | ZF | SF | OF)) |
                      arithmetic);
}

static uint16_t neg16_flags(uint16_t flags, uint16_t before) {
    uint16_t result = (uint16_t)(0u - before);
    uint16_t arithmetic = szp16(result);
    if (before != 0u) arithmetic |= CF;
    if ((before & 0x000fu) != 0u) arithmetic |= AF;
    if (before == 0x8000u) arithmetic |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

#if ENTITY_DIRTY_MUTATION != 1
static void add_bx(EntityDirtyState *state, uint16_t amount) {
    uint16_t before = state->bx;
    state->bx = (uint16_t)(before + amount);
    state->flags = add_flags(state->flags, before, amount, 16u);
}
#endif

static void add_ax(EntityDirtyState *state, uint16_t amount) {
    uint16_t before = state->ax;
    state->ax = (uint16_t)(before + amount);
    state->flags = add_flags(state->flags, before, amount, 16u);
}

#if ENTITY_DIRTY_MUTATION != 4
static void add_cx(EntityDirtyState *state, uint16_t amount) {
    uint16_t before = state->cx;
    state->cx = (uint16_t)(before + amount);
    state->flags = add_flags(state->flags, before, amount, 16u);
}
#endif

static void add_si(EntityDirtyState *state, uint16_t amount) {
    uint16_t before = state->si;
    state->si = (uint16_t)(before + amount);
    state->flags = add_flags(state->flags, before, amount, 16u);
}

static void shift_bx_right(EntityDirtyState *state) {
    uint16_t before = state->bx;
    state->bx = (uint16_t)(before >> 1);
    state->flags = shr_flags(state->flags, before, 16u);
}

static void shift_ax_right(EntityDirtyState *state) {
    uint16_t before = state->ax;
    state->ax = (uint16_t)(before >> 1);
    state->flags = shr_flags(state->flags, before, 16u);
}

static void shift_cl_right(EntityDirtyState *state) {
    uint8_t before = (uint8_t)state->cx;
    uint8_t after = (uint8_t)(before >> 1);
    state->cx = (uint16_t)((state->cx & 0xff00u) | after);
    state->flags = shr_flags(state->flags, before, 8u);
}

static void push_word(EntityDirtyState *state, uint16_t value) {
    state->sp = (uint16_t)(state->sp - 2u);
    write16(state, state->ss, state->sp, value);
}

static uint16_t pop_word(EntityDirtyState *state) {
    uint16_t value = read16(state, state->ss, state->sp);
    state->sp = (uint16_t)(state->sp + 2u);
    return value;
}

static LmnEntityDirtyResult result_of(const EntityDirtyState *state) {
    LmnEntityDirtyResult result;
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

LmnEntityDirtyResult lmn_mark_entity_drawing_dirty_core(uint8_t *memory,
    const LmnEntityDirtyCall *call, const LmnRasterBus *bus) {
    EntityDirtyState state;
    uint16_t record_x, record_x_delta, cell_map_offset;
    uint16_t view_origin;
    uint8_t vertical_adjustment_flag;
    uint8_t map_value;

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
    state.continuation = CS_EntityDrawingDirtyReturn;
    state.status = LMN_ENTITY_DIRTY_READY;

    state.bx = read16(&state, state.ds, state.di);    /* MOV BX,[DI] */
    record_x_delta = read16(&state, state.ds,
                            (uint16_t)(state.di + 0x0004u));
    record_x = state.bx;
    state.bx = (uint16_t)(record_x + record_x_delta); /* ADD BX,[DI+4] */
    state.flags = add_flags(state.flags, record_x, record_x_delta, 16u);
    if (state.flags & SF) {                            /* JNS 5731 */
#if ENTITY_DIRTY_MUTATION != 1
        add_bx(&state, 0x0160u);                       /* ADD BX,160h */
#endif
    }
    state.ax = state.bx;                               /* MOV AX,BX */
    shift_bx_right(&state);                            /* SHR BX,1 */
    shift_bx_right(&state);
    shift_bx_right(&state);
    state.si = SEG09A9_ViewVisibilityMapBase;          /* LEA SI,[EA8] */
    map_value = read8(&state, state.ds,
                      (uint16_t)(state.bx + state.si)); /* CMP [BX+SI],1 */
    state.flags = sub_flags(state.flags, map_value, 1u, 8u);
#if ENTITY_DIRTY_MUTATION != 2
    if (!(state.flags & ZF))
        return result_of(&state);                      /* JMP 57D0 */
#endif

    view_origin = read16(&state, state.ds, SEG09A9_LevelViewOriginPixels);
    {
        uint16_t before = state.ax;
        state.ax = (uint16_t)(before - view_origin);         /* SUB AX,[0] */
        state.flags = sub_flags(state.flags, before, view_origin, 16u);
    }
    if (state.flags & SF) {                            /* JNS 574D */
        state.ax = 0;
        state.flags = logic16_flags(state.flags, 0);   /* XOR AX,AX */
    }
    shift_ax_right(&state);
    shift_ax_right(&state);
    shift_ax_right(&state);
    cell_map_offset = read16(&state, state.ds, SEG09A9_DrawingDirtyCellMapOffset);
    add_ax(&state, cell_map_offset);                   /* ADD AX,[26] */
#if ENTITY_DIRTY_MUTATION == 3
    state.bp = cell_map_offset;                        /* Reuse first read. */
#else
    state.bp = read16(&state, state.ds,
                      SEG09A9_DrawingDirtyCellMapOffset); /* MOV BP,[26] */
#endif
    {
        uint16_t before = state.bp;
        state.bp = (uint16_t)(before + 0x0321u);
        state.flags = add_flags(state.flags, before, 0x0321u, 16u);
    }
    {
        uint16_t before = state.ax;
        state.ax = (uint16_t)(before + 1u);
        state.flags = inc_flags(state.flags, before, 16u); /* INC AX */
    }
    state.si = state.ax;                               /* MOV SI,AX */
    state.cx = read16(&state, state.ds,
                      (uint16_t)(state.di + 0x0006u));  /* MOV CX,[DI+6] */
    state.cx = (uint16_t)(state.cx - 0x0008u);          /* SUB CX,8 */
    state.flags = sub_flags(state.flags,
                            (uint16_t)(state.cx + 0x0008u), 0x0008u, 16u);
    state.ax = read16(&state, state.ds,
                      (uint16_t)(state.di + 0x0002u));  /* MOV AX,[DI+2] */
    vertical_adjustment_flag = read8(&state, state.ds,
                        (uint16_t)(state.di + 0x0020u)); /* CMP byte [DI+20],0 */
    state.flags = sub_flags(state.flags, vertical_adjustment_flag, 0u, 8u);
    if (!(state.flags & ZF)) {
        uint16_t before = state.cx;
        state.cx = (uint16_t)(before - 0x0008u);
        state.flags = sub_flags(state.flags, before, 0x0008u, 16u);
    }
    {
        uint16_t before = state.ax;
        state.ax = (uint16_t)(before + state.cx);
        state.flags = add_flags(state.flags, before, state.cx, 16u);
    }
    state.ax = (uint16_t)(state.ax - 0x0010u);
    state.flags = sub_flags(state.flags,
                            (uint16_t)(state.ax + 0x0010u), 0x0010u, 16u);
    if (state.flags & SF) {                            /* JS 577B */
#if ENTITY_DIRTY_MUTATION == 4
        state.ax = 0;
        state.flags = logic16_flags(state.flags, state.ax);
        state.cx = (uint16_t)(state.cx - 0x0008u);
        state.flags = sub_flags(state.flags,
                                (uint16_t)(state.cx + 0x0008u), 0x0008u, 16u);
#else
        do {
            add_cx(&state, 0x0008u);                   /* ADD CX,8 */
            add_ax(&state, 0x0008u);                   /* ADD AX,8 */
        } while (state.flags & SF);
        state.ax = 0;
        state.flags = logic16_flags(state.flags, 0);   /* XOR AX,AX */
        state.cx = (uint16_t)(state.cx - 0x0008u);
        state.flags = sub_flags(state.flags,
                                (uint16_t)(state.cx + 0x0008u), 0x0008u, 16u);
#endif
    }
    {
        uint16_t before = state.cx;
        state.cx = (uint16_t)(0u - before);
        state.flags = neg16_flags(state.flags, before); /* NEG CX */
    }
    state.dx = state.ax;                               /* MOV DX,AX */
    state.ax &= 0xfff8u;                               /* AND AX,FFF8h */
    state.flags = logic16_flags(state.flags, state.ax);
    add_si(&state, state.ax);                          /* ADD SI,AX */
    {
        uint16_t before = state.ax;
        uint16_t result = (uint16_t)(before << 1);
        uint16_t arithmetic = szp16(result);
        unsigned carry = (before >> 15) & 1u;
        if (carry) arithmetic |= CF;
        if ((((result >> 15) & 1u) ^ carry) != 0u) arithmetic |= OF;
        state.ax = result;
        state.flags = (uint16_t)((state.flags &
            (uint16_t)~(CF | PF | ZF | SF | OF)) | arithmetic); /* SHL AX */
    }
    {
        uint16_t before = state.ax;
        uint16_t result = (uint16_t)(before << 1);
        uint16_t arithmetic = szp16(result);
        unsigned carry = (before >> 15) & 1u;
        if (carry) arithmetic |= CF;
        if ((((result >> 15) & 1u) ^ carry) != 0u) arithmetic |= OF;
        state.ax = result;
        state.flags = (uint16_t)((state.flags &
            (uint16_t)~(CF | PF | ZF | SF | OF)) | arithmetic);
    }
    add_si(&state, state.ax);                          /* ADD SI,AX */
    state.cx = (uint16_t)((state.cx & 0x00ffu) | 0x0300u); /* MOV CH,3 */
    map_value = (uint8_t)(read16(&state, state.ds,
        (uint16_t)(state.di + 0x0008u)) & 0x0002u);    /* TEST word,2 */
    state.flags = logic16_flags(state.flags, map_value);
    if (!(state.flags & ZF)) {
#if ENTITY_DIRTY_MUTATION != 5
        state.cx = (uint16_t)((state.cx & 0x00ffu) | 0x0500u); /* MOV CH,5 */
#endif
    }
    {
        uint8_t before = (uint8_t)state.cx;            /* MOV AL,CL */
        state.ax = (uint16_t)((state.ax & 0xff00u) | before);
    }
    shift_cl_right(&state);
    shift_cl_right(&state);
    shift_cl_right(&state);
    state.flags = logic8_flags(state.flags, (uint8_t)(state.dx & 0x0007u));
    if (!(state.flags & ZF)) {
        uint8_t before = (uint8_t)state.cx;
        state.cx = (uint16_t)((state.cx & 0xff00u) |
                              (uint8_t)(before + 1u));
        state.flags = inc_flags(state.flags, before, 8u); /* INC CL */
    }
    state.flags = logic8_flags(state.flags, (uint8_t)(state.ax & 0x0007u));
    if (!(state.flags & ZF)) {
        uint8_t before = (uint8_t)state.cx;
        state.cx = (uint16_t)((state.cx & 0xff00u) |
                              (uint8_t)(before + 1u));
        state.flags = inc_flags(state.flags, before, 8u); /* INC CL */
    }
    state.ax = (uint16_t)((state.ax & 0xff00u) | 0x0001u); /* MOV AL,1 */

    for (;;) {                                          /* First row unconditional. */
#if ENTITY_DIRTY_MUTATION == 7
        uint16_t row_cx = state.cx;
        uint16_t row_si = state.si;
#endif
        push_word(&state, state.cx);                   /* PUSH CX */
        push_word(&state, state.si);                   /* PUSH SI */
        do {                                             /* First byte unconditional. */
            uint16_t segment = state.ss;
#if ENTITY_DIRTY_MUTATION == 6
            segment = state.ds;
#endif
            write8(&state, segment, state.si, (uint8_t)state.ax); /* MOV [SS:SI],AL */
            {
                uint16_t before = state.si;
                state.si = (uint16_t)(before + 1u);
                state.flags = inc_flags(state.flags, before, 16u); /* INC SI */
            }
            {
                uint8_t before = (uint8_t)(state.cx >> 8);
                uint8_t after = (uint8_t)(before - 1u);
                state.cx = (uint16_t)((state.cx & 0x00ffu) |
                                      ((uint16_t)after << 8));
                state.flags = dec_flags(state.flags, before, 8u); /* DEC CH */
            }
        } while ((state.cx & 0xff00u) != 0u);            /* JNZ loc_57BB */
        {
            uint16_t restored_si = pop_word(&state);   /* POP SI, live stack */
            uint16_t restored_cx = pop_word(&state);   /* POP CX, live stack */
#if ENTITY_DIRTY_MUTATION == 7
            (void)restored_si;
            (void)restored_cx;
            state.si = row_si;
            state.cx = row_cx;
#else
            state.si = restored_si;
            state.cx = restored_cx;
#endif
        }
        add_si(&state, 0x0028u);                       /* ADD SI,28h */
        state.flags = sub_flags(state.flags, state.si, state.bp, 16u); /* CMP */
        if (!(state.flags & CF))                      /* JNC 57D0 */
            break;
        {
            uint8_t before = (uint8_t)state.cx;
            uint8_t after = (uint8_t)(before - 1u);
            state.cx = (uint16_t)((state.cx & 0xff00u) | after);
            state.flags = dec_flags(state.flags, before, 8u); /* DEC CL */
        }
        if (state.flags & ZF)                          /* JNZ 57B9 */
            break;
    }

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
                         const LmnEntityDirtyResult *result) {
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

uint16_t lmn_mark_entity_drawing_dirty_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnEntityDirtyCall call;
    LmnEntityDirtyResult result;
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
    result = lmn_mark_entity_drawing_dirty_core(memory, &call, bus);
    apply_result(registers, &result);
    if (result.status == LMN_ENTITY_DIRTY_READY) {
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return result.status;
}
