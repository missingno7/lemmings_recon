#include "decimal_field.h"
#include "lemmings_sym.h"

#ifndef DECIMAL_FIELD_MUTATION
#define DECIMAL_FIELD_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffff,
    CF = 0x0001,
    PF = 0x0004,
    AF = 0x0010,
    ZF = 0x0040,
    SF = 0x0080,
    DF = 0x0400,
    OF = 0x0800,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    INC_FLAGS = PF | AF | ZF | SF | OF
};

typedef struct DecimalState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t data_segment;
    uint16_t value;
    uint16_t prefix_value;
    uint16_t cursor;
    uint16_t flags;
    unsigned pair_entry;
} DecimalState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static void write_byte(DecimalState *state, uint16_t offset, uint8_t value) {
    uint32_t address = physical(state->data_segment, offset);
    if (state->bus && state->bus->write_byte) {
        state->bus->write_byte(state->bus->context, state->memory, address,
                               value, state->flags);
    } else {
        state->memory[address] = value;
    }
}

static uint8_t read_physical(uint8_t *memory, uint32_t address,
                             uint16_t flags, const LmnRasterBus *bus) {
    address &= MEMORY_MASK;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static unsigned even_parity(uint8_t value) {
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones += (value >> bit) & 1u;
    return (ones & 1u) == 0;
}

static uint16_t szp8(uint16_t flags, uint8_t value) {
    flags = (uint16_t)(flags & (uint16_t)~(PF | ZF | SF));
    if (even_parity(value)) flags |= PF;
    if (value == 0) flags |= ZF;
    if (value & 0x80u) flags |= SF;
    return flags;
}

/* XOR/AND leave AF undefined; retain its prior value outside the defined mask. */
static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    flags = (uint16_t)(flags & (uint16_t)~(CF | OF));
    return szp8(flags, value);
}

static uint16_t add8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint16_t wide = (uint16_t)left + right;
    uint8_t result = (uint8_t)wide;
    uint16_t arithmetic = (uint16_t)((wide > 0xffu ? CF : 0u) |
        (result == 0 ? ZF : 0u) | (result & SF) |
        (((left ^ right ^ result) & 0x10u) ? AF : 0u) |
        (((uint8_t)~(left ^ right) & (left ^ result) & 0x80u) ? OF : 0u) |
        (even_parity(result) ? PF : 0u));
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

static uint16_t sub8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint8_t result = (uint8_t)(left - right);
    uint16_t arithmetic = (uint16_t)((left < right ? CF : 0u) |
        (result == 0 ? ZF : 0u) | (result & SF) |
        (((left ^ right ^ result) & 0x10u) ? AF : 0u) |
        (((left ^ right) & (left ^ result) & 0x80u) ? OF : 0u) |
        (even_parity(result) ? PF : 0u));
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | arithmetic);
}

static uint16_t inc8_flags(uint16_t flags, uint8_t before) {
    uint8_t result = (uint8_t)(before + 1u);
    uint16_t arithmetic = (uint16_t)((result == 0 ? ZF : 0u) |
        (result & SF) | ((before & 0x0fu) == 0x0fu ? AF : 0u) |
        (before == 0x7fu ? OF : 0u) |
        (even_parity(result) ? PF : 0u));
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

static uint16_t dec8_flags(uint16_t flags, uint8_t before) {
    uint8_t result = (uint8_t)(before - 1u);
    uint16_t arithmetic = (uint16_t)((result == 0 ? ZF : 0u) |
        (result & SF) | ((before & 0x0fu) == 0 ? AF : 0u) |
        (before == 0x80u ? OF : 0u) |
        (even_parity(result) ? PF : 0u));
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

static uint16_t inc16_flags(uint16_t flags, uint16_t before) {
    uint16_t result = (uint16_t)(before + 1u);
    uint16_t arithmetic = (uint16_t)((result == 0 ? ZF : 0u) |
        (result & 0x8000u ? SF : 0u) |
        ((before & 0x000fu) == 0x000fu ? AF : 0u) |
        (before == 0x7fffu ? OF : 0u) |
        (even_parity((uint8_t)result) ? PF : 0u));
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}

#if DECIMAL_FIELD_MUTATION == 4
static uint16_t dec16_flags(uint16_t flags, uint16_t before) {
    uint16_t result = (uint16_t)(before - 1u);
    uint16_t arithmetic = (uint16_t)((result == 0 ? ZF : 0u) |
        (result & 0x8000u ? SF : 0u) |
        ((before & 0x000fu) == 0 ? AF : 0u) |
        (before == 0x8000u ? OF : 0u) |
        (even_parity((uint8_t)result) ? PF : 0u));
    return (uint16_t)((flags & (uint16_t)~INC_FLAGS) | arithmetic);
}
#endif

static void xor_bl(DecimalState *state) {
    state->prefix_value = (uint16_t)(
#if DECIMAL_FIELD_MUTATION == 5
        0u
#else
        state->prefix_value & 0xff00u
#endif
    );
    state->flags = logic8_flags(state->flags, 0);
}

static void xor_ah(DecimalState *state) {
    state->value &= 0x00ffu;
    state->flags = logic8_flags(state->flags, 0);
}

static void and8_flags_state(DecimalState *state, uint8_t value) {
    state->flags = logic8_flags(state->flags, value);
}

static uint8_t al(const DecimalState *state) {
    return (uint8_t)state->value;
}

static uint8_t ah(const DecimalState *state) {
    return (uint8_t)(state->value >> 8);
}

static uint8_t bl(const DecimalState *state) {
    return (uint8_t)state->prefix_value;
}

static void set_al(DecimalState *state, uint8_t value) {
    state->value = (uint16_t)((state->value & 0xff00u) | value);
}

static void set_ah(DecimalState *state, uint8_t value) {
    state->value = (uint16_t)((state->value & 0x00ffu) |
                              ((uint16_t)value << 8));
}

static void set_bl(DecimalState *state, uint8_t value) {
    state->prefix_value = (uint16_t)((state->prefix_value & 0xff00u) | value);
}

static void increment_cursor(DecimalState *state) {
    uint16_t before = state->cursor;
#if DECIMAL_FIELD_MUTATION == 4
    if (state->flags & DF) {
        state->cursor = (uint16_t)(before - 1u);
        state->flags = dec16_flags(state->flags, before);
        return;
    }
#endif
    state->cursor = (uint16_t)(before + 1u);
    state->flags = inc16_flags(state->flags, before);
}

static void fill_spaces(DecimalState *state, unsigned count) {
    unsigned index;
    for (index = 0; index < count; ++index)
        write_byte(state, (uint16_t)(state->cursor + index), 0x20u);
}

static void hundred_path(DecimalState *state) {
    uint8_t before;
    for (;;) {
        before = ah(state);
        set_ah(state, (uint8_t)(before + 1u));       /* INC AH */
        state->flags = inc8_flags(state->flags, before);
        before = al(state);
        set_al(state, (uint8_t)(before - 100u));     /* SUB AL,64h */
        state->flags = sub8_flags(state->flags, before, 100u);
        if (state->flags & CF) break;                /* JNC 4B77 */
    }
    before = al(state);
    set_al(state, (uint8_t)(before + 100u));         /* ADD AL,64h */
    state->flags = add8_flags(state->flags, before, 100u);
    before = ah(state);
    set_ah(state, (uint8_t)(before - 1u));           /* DEC AH */
    state->flags = dec8_flags(state->flags, before);
    and8_flags_state(state, ah(state));              /* AND AH,AH */

    {
        unsigned emit_hundreds = ah(state) != 0;
#if DECIMAL_FIELD_MUTATION == 1
        emit_hundreds = 1;
#endif
        if (emit_hundreds) {
            before = ah(state);
            set_ah(state, (uint8_t)(before + 0x30u));     /* ADD AH,30h */
            state->flags = add8_flags(state->flags, before, 0x30u);
            before = bl(state);
            set_bl(state, (uint8_t)(before + 1u));        /* INC BL */
            state->flags = inc8_flags(state->flags, before);
            write_byte(state, state->cursor, ah(state)); /* MOV [SI],AH */
            increment_cursor(state);                     /* INC SI */
        } else {
            set_ah(state, 0x20u);                         /* MOV AH,20h */
        }
    }
}

static void decimal_tail(DecimalState *state) {
    uint8_t before;
    unsigned emit_tens;
#if DECIMAL_FIELD_MUTATION == 3
    if (!state->pair_entry)
#endif
        fill_spaces(state, 2);                       /* MOV [SI],20; [SI+1],20 */
    xor_ah(state);                                    /* XOR AH,AH */
    for (;;) {
        before = ah(state);
        set_ah(state, (uint8_t)(before + 1u));        /* INC AH */
        state->flags = inc8_flags(state->flags, before);
        before = al(state);
        set_al(state, (uint8_t)(before - 10u));       /* SUB AL,0Ah */
        state->flags = sub8_flags(state->flags, before, 10u);
        if (state->flags & CF) break;                 /* JNC 4B9A */
    }
    before = al(state);
    set_al(state, (uint8_t)(before + 10u));           /* ADD AL,0Ah */
    state->flags = add8_flags(state->flags, before, 10u);
    before = ah(state);
    set_ah(state, (uint8_t)(before - 1u));             /* DEC AH */
    state->flags = dec8_flags(state->flags, before);
    and8_flags_state(state, ah(state));                /* AND AH,AH */

    emit_tens = ah(state) != 0;
    if (!emit_tens) {
        and8_flags_state(state, bl(state));            /* AND BL,BL */
        if (state->flags & ZF) {                       /* JNZ 4BB0 */
            set_ah(state, 0x20u);                       /* MOV AH,20h */
        } else {
            emit_tens = 1;
        }
    }
    if (emit_tens) {
        before = ah(state);
        set_ah(state, (uint8_t)(before + 0x30u));       /* ADD AH,30h */
        state->flags = add8_flags(state->flags, before, 0x30u);
        before = bl(state);
        set_bl(state, (uint8_t)(before + 1u));          /* INC BL */
        state->flags = inc8_flags(state->flags, before);
        write_byte(state, state->cursor, ah(state));   /* MOV [SI],AH */
        increment_cursor(state);                       /* INC SI */
    }

    before = al(state);
    set_al(state, (uint8_t)(before + 0x30u));           /* ADD AL,30h */
    state->flags = add8_flags(state->flags, before, 0x30u);
    {
        uint16_t add_flags = state->flags;
        write_byte(state, state->cursor, al(state));    /* MOV [SI],AL */
        increment_cursor(state);                       /* INC SI */
#if DECIMAL_FIELD_MUTATION == 6
        state->flags = add_flags;
#else
        (void)add_flags;
#endif
    }
}

static LmnDecimalFieldResult run_field(uint8_t *memory,
    const LmnDecimalFieldCall *call, const LmnRasterBus *bus, unsigned pair) {
    DecimalState state;
    LmnDecimalFieldResult result;

    state.memory = memory;
    state.bus = bus;
    state.data_segment = call->data_segment;
    state.value = call->value;
    state.prefix_value = call->prefix_value;
    state.cursor = call->cursor;
    state.flags = call->flags;

#if DECIMAL_FIELD_MUTATION == 2
    if (pair) pair = 0;
#endif
    state.pair_entry = pair;

    if (pair) {
        xor_bl(&state);                              /* 4BBE: XOR BL,BL */
    } else {
#if DECIMAL_FIELD_MUTATION != 3
        fill_spaces(&state, 3);                      /* 4B68..4B72 */
#endif
        xor_ah(&state);                              /* 4B73: XOR AH,AH */
        xor_bl(&state);                              /* 4B75: XOR BL,BL */
        hundred_path(&state);
    }

    decimal_tail(&state);
    result.value = state.value;
    result.prefix_value = state.prefix_value;
    result.cursor = state.cursor;
    result.flags = state.flags;
    return result;
}

LmnDecimalFieldResult lmn_write_decimal_field_core(uint8_t *memory,
    const LmnDecimalFieldCall *call, const LmnRasterBus *bus) {
    return run_field(memory, call, bus, 0);
}

LmnDecimalFieldResult lmn_write_decimal_pair_core(uint8_t *memory,
    const LmnDecimalFieldCall *call, const LmnRasterBus *bus) {
    return run_field(memory, call, bus, 1);
}

static void apply_result(LmnRegs *registers,
    const LmnDecimalFieldResult *result) {
    registers->ax = result->value;
    registers->bx = result->prefix_value;
    registers->si = result->cursor;
    registers->flags = result->flags;
}

static uint16_t read_return_ip(uint8_t *memory, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(stack_segment, stack_offset);
    uint8_t low = read_physical(memory, address, flags, bus);
    uint8_t high = read_physical(memory, (address + 1u) & MEMORY_MASK,
                                 flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void adapt(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus,
    LmnDecimalFieldResult (*core)(uint8_t *, const LmnDecimalFieldCall *,
                                  const LmnRasterBus *)) {
    LmnDecimalFieldCall call;
    LmnDecimalFieldResult result;
#if DECIMAL_FIELD_MUTATION == 7
    uint16_t prefetched_return = 0;
#endif

    call.data_segment = registers->ds;
    call.value = registers->ax;
    call.prefix_value = registers->bx;
    call.cursor = registers->si;
    call.flags = registers->flags;
#if DECIMAL_FIELD_MUTATION == 7
    prefetched_return = read_return_ip(memory, registers->ss, registers->sp,
                                       registers->flags, bus);
#endif
    result = core(memory, &call, bus);
    apply_result(registers, &result);
#if DECIMAL_FIELD_MUTATION == 7
    registers->ip = prefetched_return;
#else
    registers->ip = read_return_ip(memory, registers->ss, registers->sp,
                                   registers->flags, bus);
#endif
    registers->sp = (uint16_t)(registers->sp + 2u);
}

void lmn_write_decimal_field_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus) {
    adapt(memory, registers, bus, lmn_write_decimal_field_core);
}

void lmn_write_decimal_pair_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus) {
    adapt(memory, registers, bus, lmn_write_decimal_pair_core);
}
