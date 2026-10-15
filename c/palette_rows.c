#include "palette_rows.h"
#include "lemmings_sym.h"

#ifndef PALETTE_ROWS_MUTATION
#define PALETTE_ROWS_MUTATION 0
#endif

enum {
    CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
    SF = 0x0080, DF = 0x0400, OF = 0x0800,
    ARITHMETIC_FLAGS = 0x08d5
};

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + (uint32_t)offset) & 0xfffffu;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnVideoRestoreState *state, uint16_t value) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               value, state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnVideoRestoreState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static uint8_t al(const LmnVideoRestoreState *state) {
    return (uint8_t)state->value;
}

static uint8_t bl(const LmnVideoRestoreState *state) {
    return (uint8_t)state->base_value;
}

static uint8_t cl(const LmnVideoRestoreState *state) {
    return (uint8_t)state->count;
}

static uint8_t dl(const LmnVideoRestoreState *state) {
    return (uint8_t)state->argument;
}

static uint8_t dh(const LmnVideoRestoreState *state) {
    return (uint8_t)(state->argument >> 8);
}

static void set_al(LmnVideoRestoreState *state, uint8_t value) {
    state->value = (uint16_t)((state->value & 0xff00u) | value);
}

static void set_ah(LmnVideoRestoreState *state, uint8_t value) {
    state->value = (uint16_t)((state->value & 0x00ffu) |
                              ((uint16_t)value << 8));
}

static void set_bl(LmnVideoRestoreState *state, uint8_t value) {
    state->base_value = (uint16_t)((state->base_value & 0xff00u) | value);
}

static void set_cl(LmnVideoRestoreState *state, uint8_t value) {
    state->count = (uint16_t)((state->count & 0xff00u) | value);
}

static void set_dl(LmnVideoRestoreState *state, uint8_t value) {
    state->argument = (uint16_t)((state->argument & 0xff00u) | value);
}

static void set_dh(LmnVideoRestoreState *state, uint8_t value) {
    state->argument = (uint16_t)((state->argument & 0x00ffu) |
                                 ((uint16_t)value << 8));
}

static uint16_t szp8(uint8_t value) {
    unsigned ones = 0, bit;
    uint16_t flags = 0;
    for (bit = 0; bit < 8; ++bit)
        ones += (value >> bit) & 1u;
    if ((ones & 1u) == 0)
        flags |= PF;
    if (value == 0)
        flags |= ZF;
    if (value & 0x80u)
        flags |= SF;
    return flags;
}

static uint16_t szp16(uint16_t value) {
    uint16_t flags = (uint16_t)(szp8((uint8_t)value) & (uint16_t)~(SF | ZF));
    if (value == 0)
        flags |= ZF;
    if (value & 0x8000u)
        flags |= SF;
    return flags;
}

static uint8_t logic8(uint8_t value, uint16_t *flags) {
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
                        szp8(value));
    return value;
}

static uint16_t logic16(uint16_t value, uint16_t *flags) {
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
                        szp16(value));
    return value;
}

static void inc16(uint16_t *value, uint16_t *flags) {
    uint16_t before = *value;
    uint16_t result = (uint16_t)(before + 1u);
    uint16_t changed = (uint16_t)(szp16(result) | (*flags & CF));
    if ((before ^ 1u ^ result) & 0x0010u)
        changed |= AF;
    if (before == 0x7fffu)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    *value = result;
}

#if PALETTE_ROWS_MUTATION == 2
static void dec16(uint16_t *value, uint16_t *flags) {
    uint16_t before = *value;
    uint16_t result = (uint16_t)(before - 1u);
    uint16_t changed = (uint16_t)(szp16(result) | (*flags & CF));
    if ((before ^ 1u ^ result) & 0x0010u)
        changed |= AF;
    if (before == 0x8000u)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    *value = result;
}

#endif

static LmnPaletteRowResult make_result(const LmnVideoRestoreState *state,
    uint16_t code_segment, uint16_t continuation,
    enum LmnPaletteRowStatus status) {
    LmnPaletteRowResult result;
    result.state = *state;
    result.code_segment = code_segment;
    result.continuation = continuation;
    result.status = status;
    return result;
}

/* Model CALL, the native child through its RET instruction, and the actual
   live-word RET. A changed child-internal return stops in that child. */
static int call_channel(uint8_t *memory, uint16_t *code_segment,
    LmnVideoRestoreState *state, enum LmnPaletteChannelEntry entry,
    uint16_t after_call, const LmnRasterBus *bus, uint16_t *continuation,
    enum LmnPaletteRowStatus *status) {
    LmnPaletteChannelResult child;
    uint16_t returned;
    push_word(memory, bus, state, after_call);
    child = lmn_step_palette_channel_core(memory, *code_segment, state,
                                           entry, bus);
    *state = child.state;
    *code_segment = child.code_segment;
    *continuation = child.continuation;

    if (child.status == LMN_PALETTE_CHANNEL_CHANGED_RETURN) {
        *status = LMN_PALETTE_ROW_CHANNEL_STOP;
        return 0;
    }

    /* READY ends immediately before the child's actual outer near RET. */
    returned = pop_word(memory, bus, state);
    if (returned != after_call) {
#if PALETTE_ROWS_MUTATION == 5
        /* Mutant: ignore a changed target from this actual child RET. */
        *continuation = after_call;
        return 1;
#else
        *continuation = returned;
        *status = LMN_PALETTE_ROW_CHANGED_RETURN;
        return 0;
#endif
    }
    *continuation = after_call;
    return 1;
}

static LmnPaletteRowResult packed_row(uint8_t *memory, uint16_t code_segment,
    LmnVideoRestoreState *state, const LmnRasterBus *bus) {
    enum LmnPaletteRowStatus status = LMN_PALETTE_ROW_READY;
    uint16_t continuation = CS_PackedPaletteRowReturn566B;

    state->frame_cursor = 0;
    (void)logic16(state->frame_cursor, &state->flags); /* XOR BP,BP */
    state->count &= 0x00ffu;                                     /* XOR CH,CH */
    (void)logic8(0, &state->flags);

#if PALETTE_ROWS_MUTATION == 6
    if (cl(state) == 0u)
        goto packed_finish;
#endif

    for (;;) {
#if PALETTE_ROWS_MUTATION == 1
        uint16_t entry_count = state->count;
#endif
        uint16_t restored_count;
        uint8_t source, target;

        /* PUSH CX; MOV DL,[DS:SI]; MOV CL,[DS:DI]; MOV BL,CL; MOV AL,DL. */
        push_word(memory, bus, state, state->count);
        source = read_byte(memory, bus,
            physical(state->data_segment, state->source_cursor), state->flags);
        set_dl(state, source);
        target = read_byte(memory, bus,
            physical(state->data_segment, state->output_cursor), state->flags);
        set_cl(state, target);
        set_bl(state, cl(state));
        set_al(state, dl(state));

        if (!call_channel(memory, &code_segment, state,
                LMN_PALETTE_CHANNEL_HIGH,
                CS_PackedPaletteRowAfterHigh564E, bus,
                &continuation, &status))
            return make_result(state, code_segment, continuation, status);

        /* MOV DH,AL; MOV AL,DL; MOV BL,CL. */
        set_dh(state, al(state));
        set_al(state, dl(state));
        set_bl(state, cl(state));
        if (!call_channel(memory, &code_segment, state,
                LMN_PALETTE_CHANNEL_MIDDLE,
                CS_PackedPaletteRowAfterMiddle5657, bus,
                &continuation, &status))
            return make_result(state, code_segment, continuation, status);

        /* OR DH,AL; MOV AL,DL; MOV BL,CL. */
        set_dh(state, logic8((uint8_t)(dh(state) | al(state)),
                             &state->flags));
        set_al(state, dl(state));
        set_bl(state, cl(state));
        if (!call_channel(memory, &code_segment, state,
                LMN_PALETTE_CHANNEL_LOW,
                CS_PackedPaletteRowAfterLow5660, bus,
                &continuation, &status))
            return make_result(state, code_segment, continuation, status);

        /* OR DH,AL; MOV [DS:SI],DH; POP CX. */
        set_dh(state, logic8((uint8_t)(dh(state) | al(state)),
                             &state->flags));
        write_byte(memory, bus,
            physical(state->data_segment, state->source_cursor), dh(state),
            state->flags);
        restored_count = pop_word(memory, bus, state);
#if PALETTE_ROWS_MUTATION == 1
        /* Cache the iteration's entry count instead of trusting live SS:SP. */
        (void)restored_count;
        state->count = entry_count;
#else
        state->count = restored_count;
#endif

        /* INC SI; INC DI; LOOP. INC preserves CF; LOOP changes no flags. */
#if PALETTE_ROWS_MUTATION == 2
        if (state->flags & DF) {
            dec16(&state->source_cursor, &state->flags);
            dec16(&state->output_cursor, &state->flags);
        } else
#endif
        {
            inc16(&state->source_cursor, &state->flags);
            inc16(&state->output_cursor, &state->flags);
        }
        state->count = (uint16_t)(state->count - 1u);
        if (state->count == 0u)
            break;
    }

#if PALETTE_ROWS_MUTATION == 6
packed_finish:
#endif
    (void)logic16(state->frame_cursor, &state->flags); /* AND BP,BP */
    return make_result(state, code_segment, CS_PackedPaletteRowReturn566B,
                       LMN_PALETTE_ROW_READY);
}

static LmnPaletteRowResult rgb_row(uint8_t *memory, uint16_t code_segment,
    LmnVideoRestoreState *state, const LmnRasterBus *bus) {
    enum LmnPaletteRowStatus status = LMN_PALETTE_ROW_READY;
    uint16_t continuation = CS_RgbPaletteRowReturn570B;
#if PALETTE_ROWS_MUTATION == 3
    uint8_t saved_targets[3];
#endif

    set_bl(state, 0);                    /* XOR BL,BL */
    (void)logic8(bl(state), &state->flags);
    state->count &= 0x00ffu;             /* XOR CH,CH */
    (void)logic8(0, &state->flags);

#if PALETTE_ROWS_MUTATION == 6
    if (cl(state) == 0u)
        goto rgb_finish;
#endif

    for (;;) {
        unsigned component;

#if PALETTE_ROWS_MUTATION == 3
        /* The mutated path snapshots this unrolled triple before its writes. */
        for (component = 0; component < 3u; ++component)
            saved_targets[component] = read_byte(memory, bus,
                physical(state->data_segment,
                    (uint16_t)(state->output_cursor + component)),
                state->flags);
#endif

        for (component = 0; component < 3u; ++component) {
            uint8_t source, target;
            uint16_t after_call = component == 0u ?
                CS_RgbPaletteRowAfterFirst56ED : component == 1u ?
                CS_RgbPaletteRowAfterSecond56F8 :
                CS_RgbPaletteRowAfterThird5703;

            /* Each unrolled component reads its source before its target. */
            source = read_byte(memory, bus,
                physical(state->data_segment, state->source_cursor),
                state->flags);
            set_al(state, source);
#if PALETTE_ROWS_MUTATION == 3
            target = saved_targets[component];
#else
            target = read_byte(memory, bus,
                physical(state->data_segment, state->output_cursor),
                state->flags);
#endif
            set_ah(state, target);

#if PALETTE_ROWS_MUTATION == 4
            set_bl(state, 0);            /* Mutant: clear sticky XOR BL. */
            (void)logic8(bl(state), &state->flags);
#endif
            if (!call_channel(memory, &code_segment, state,
                    LMN_PALETTE_CHANNEL_RGB, after_call, bus,
                    &continuation, &status))
                return make_result(state, code_segment, continuation, status);

            /* MOV [DS:SI],AL; INC SI; INC DI. */
            write_byte(memory, bus,
                physical(state->data_segment, state->source_cursor),
                al(state), state->flags);
#if PALETTE_ROWS_MUTATION == 2
            if (state->flags & DF) {
                dec16(&state->source_cursor, &state->flags);
                dec16(&state->output_cursor, &state->flags);
            } else {
                inc16(&state->source_cursor, &state->flags);
                inc16(&state->output_cursor, &state->flags);
            }
#else
            inc16(&state->source_cursor, &state->flags);
            inc16(&state->output_cursor, &state->flags);
#endif
        }

        /* LOOP decrements CX once after the three unrolled components. */
        state->count = (uint16_t)(state->count - 1u);
        if (state->count == 0u)
            break;
    }

#if PALETTE_ROWS_MUTATION == 6
rgb_finish:
#endif
    (void)logic8(bl(state), &state->flags); /* AND BL,BL */
    return make_result(state, code_segment, CS_RgbPaletteRowReturn570B,
                       LMN_PALETTE_ROW_READY);
}

LmnPaletteRowResult lmn_step_palette_row_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    enum LmnPaletteRowEntry entry, const LmnRasterBus *bus) {
    LmnVideoRestoreState state = *input;
    if (entry == LMN_PALETTE_ROW_PACKED)
        return packed_row(memory, code_segment, &state, bus);
    if (entry == LMN_PALETTE_ROW_RGB)
        return rgb_row(memory, code_segment, &state, bus);
    return make_result(&state, code_segment, 0,
                       LMN_PALETTE_ROW_CHANGED_RETURN);
}

static LmnVideoRestoreState state_from_registers(const LmnRegs *registers) {
    LmnVideoRestoreState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnVideoRestoreState *state) {
    registers->ax = state->value;
    registers->bx = state->base_value;
    registers->cx = state->count;
    registers->dx = state->argument;
    registers->si = state->source_cursor;
    registers->di = state->output_cursor;
    registers->bp = state->frame_cursor;
    registers->ds = state->data_segment;
    registers->es = state->extra_segment;
    registers->ss = state->stack_segment;
    registers->sp = state->stack_offset;
    registers->flags = state->flags;
}

void lmn_step_palette_row_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnPaletteRowEntry entry, const LmnRasterBus *bus) {
    LmnVideoRestoreState input = state_from_registers(registers);
    LmnPaletteRowResult result = lmn_step_palette_row_core(memory,
        registers->cs, &input, entry, bus);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status != LMN_PALETTE_ROW_READY)
        return;

    /* The boundary adapter alone consumes the live outer near RET. */
    {
        uint16_t returned;
        input = result.state;
        returned = pop_word(memory, bus, &input);
        registers->sp = input.stack_offset;
        registers->ip = returned;
    }
}
