#include "palette_transition.h"
#include "lemmings_sym.h"

#ifndef PALETTE_TRANSITION_MUTATION
#define PALETTE_TRANSITION_MUTATION 0
#endif

enum { CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
       SF = 0x0080, OF = 0x0800,
       ARITHMETIC_FLAGS = 0x08d5 };

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

/* Word high bytes use the physical successor, while SP wraps between words. */
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

static uint16_t szp8(uint8_t value) {
    unsigned parity = 0u, bit;
    uint16_t result = 0u;
    for (bit = 0u; bit < 8u; ++bit)
        parity ^= (value >> bit) & 1u;
    if (!parity)
        result |= PF;
    if (value == 0u)
        result |= ZF;
    if (value & 0x80u)
        result |= SF;
    return result;
}

static uint16_t szp16(uint16_t value) {
    uint16_t result = (uint16_t)(szp8((uint8_t)value) &
        (uint16_t)~(SF | ZF));
    if (value == 0u)
        result |= ZF;
    if (value & 0x8000u)
        result |= SF;
    return result;
}

static void logic8(uint16_t *flags, uint8_t value) {
    /* XOR defines CF/OF/SZP; AF is undefined and represented as clear. */
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
                        szp8(value));
}

static uint16_t add16_flags(uint16_t *flags, uint16_t left, uint16_t right) {
    uint32_t sum = (uint32_t)left + (uint32_t)right;
    uint16_t value = (uint16_t)sum;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp16(value) | (sum > 0xffffu ? CF : 0u) |
        (((left ^ right ^ value) & 0x0010u) ? AF : 0u) |
        (((uint16_t)~(left ^ right) & (left ^ value) & 0x8000u) ? OF : 0u));
    return value;
}

static void cmp16_flags(uint16_t *flags, uint16_t left, uint16_t right) {
    uint16_t value = (uint16_t)(left - right);
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp16(value) | (left < right ? CF : 0u) |
        (((left ^ right ^ value) & 0x0010u) ? AF : 0u) |
        (((left ^ right) & (left ^ value) & 0x8000u) ? OF : 0u));
}

static LmnPaletteTransitionResult make_result(
    const LmnVideoRestoreState *state, uint16_t code_segment,
    uint16_t continuation, enum LmnPaletteTransitionStatus status) {
    LmnPaletteTransitionResult result;
    result.state = *state;
    result.code_segment = code_segment;
    result.continuation = continuation;
    result.status = status;
    return result;
}

static int actual_child_return(uint8_t *memory, const LmnRasterBus *bus,
    LmnVideoRestoreState *state, uint16_t expected, uint16_t *continuation) {
    uint16_t returned = pop_word(memory, bus, state);
#if PALETTE_TRANSITION_MUTATION == 6
    /* Mutant: consume the actual RET word, but continue at the expected IP. */
    (void)returned;
    *continuation = expected;
    return 1;
#else
    *continuation = returned;
    return returned == expected;
#endif
}

static void set_al(LmnVideoRestoreState *state, uint8_t value) {
    state->value = (uint16_t)((state->value & 0xff00u) | value);
}

static void set_ah(LmnVideoRestoreState *state, uint8_t value) {
    state->value = (uint16_t)((state->value & 0x00ffu) |
                              ((uint16_t)value << 8));
}

static uint8_t bl(const LmnVideoRestoreState *state) {
    return (uint8_t)state->base_value;
}

static uint8_t bh(const LmnVideoRestoreState *state) {
    return (uint8_t)(state->base_value >> 8);
}

/* The shared prefix selects the table once, then performs the same unchecked
   CS word reads and AX/offset arithmetic as the 5569 row-pointer prefix. */
static void select_transition_pointers(uint8_t *memory, uint16_t code_segment,
    LmnVideoRestoreState *state, int rgb, const LmnRasterBus *bus) {
    uint16_t table = rgb ? CS_RgbPalettePointerTable :
                           CS_PackedPalettePointerTable;
    uint16_t index;

    set_al(state, bl(state));
    set_ah(state, 0u);
    logic8(&state->flags, 0u);             /* XOR AH,AH */
    state->value = add16_flags(&state->flags, state->value, state->value);
    state->source_cursor = table;           /* LEA SI,[table] */
    state->source_cursor = add16_flags(&state->flags,
        state->source_cursor, state->value);
    state->source_cursor = read_word(memory, bus, code_segment,
        state->source_cursor, state->flags);

    set_al(state, bh(state));
    set_ah(state, 0u);
    logic8(&state->flags, 0u);             /* XOR AH,AH */
    state->value = add16_flags(&state->flags, state->value, state->value);
    state->output_cursor = table;           /* LEA DI,[table] */
    state->output_cursor = add16_flags(&state->flags,
        state->output_cursor, state->value);
    index = state->output_cursor;
    state->output_cursor = read_word(memory, bus, code_segment, index,
                                     state->flags);
}

static uint16_t read_mode(uint8_t *memory, LmnVideoRestoreState *state,
                          const LmnRasterBus *bus) {
    uint16_t mode = read_word(memory, bus, state->data_segment,
        SEG09A9_PaletteDisplayModeWord, state->flags);
    cmp16_flags(&state->flags, mode, 4u);
    return mode;
}

static enum LmnPaletteTransitionStatus palette_ports_status(
    enum LmnPalettePortsStatus status) {
    if (status == LMN_PALETTE_PORTS_MISSING_INPUT)
        return LMN_PALETTE_TRANSITION_MISSING_INPUT;
    if (status == LMN_PALETTE_PORTS_MISSING_OUTPUT)
        return LMN_PALETTE_TRANSITION_MISSING_OUTPUT;
    return LMN_PALETTE_TRANSITION_READY;
}

/* CALL writer; run to its declared RET boundary; consume and verify that live
   RET; then execute the caller's real POP SI/POP CX instructions. */
static int call_writer(uint8_t *memory, uint16_t *code_segment,
    LmnVideoRestoreState *state, int rgb,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus,
    LmnPaletteTransitionResult *stopped, uint16_t *continuation) {
    LmnPalettePortsResult child;
    uint16_t expected = rgb ? CS_RgbTransitionAfterOutput5627 :
                              CS_PackedTransitionAfterOutput55E4;
#if PALETTE_TRANSITION_MUTATION == 4
    uint16_t cached_cx = state->count;
    uint16_t cached_si = state->source_cursor;
#endif

    push_word(memory, bus, state, state->count);
    push_word(memory, bus, state, state->source_cursor);
    push_word(memory, bus, state, expected); /* near CALL */
    child = lmn_write_palette_ports_core(memory, *code_segment, state,
        rgb ? LMN_PALETTE_PORTS_ENTRY_MAPPED_DAC :
              LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE, ports, bus);
    *state = child.state;
    *continuation = child.continuation;
    if (child.status != LMN_PALETTE_PORTS_READY) {
        *stopped = make_result(state, *code_segment, child.continuation,
            palette_ports_status(child.status));
        return 0;
    }

    if (!actual_child_return(memory, bus, state, expected, continuation)) {
        *stopped = make_result(state, *code_segment, *continuation,
            LMN_PALETTE_TRANSITION_CHANGED_RETURN);
        return 0;
    }
    *continuation = expected;

    {
        uint16_t popped = pop_word(memory, bus, state);
#if PALETTE_TRANSITION_MUTATION == 4
        (void)popped;
        state->source_cursor = cached_si;
#else
        state->source_cursor = popped;
#endif
    }
    {
        uint16_t popped = pop_word(memory, bus, state);
#if PALETTE_TRANSITION_MUTATION == 4
        (void)popped;
        state->count = cached_cx;
#else
        state->count = popped;
#endif
    }
    return 1;
}

static enum LmnPaletteTransitionStatus palette_row_status(
    enum LmnPaletteRowStatus status) {
    if (status == LMN_PALETTE_ROW_CHANNEL_STOP)
        return LMN_PALETTE_TRANSITION_ROW_CHANNEL_STOP;
    if (status == LMN_PALETTE_ROW_CHANGED_RETURN)
        return LMN_PALETTE_TRANSITION_ROW_CHANGED_RETURN;
    return LMN_PALETTE_TRANSITION_READY;
}

/* CALL row; only READY reaches the caller's actual RET and subsequent JZ. */
static int call_row(uint8_t *memory, uint16_t *code_segment,
    LmnVideoRestoreState *state, int rgb, const LmnRasterBus *bus,
    LmnPaletteTransitionResult *stopped, uint16_t *continuation) {
    LmnPaletteRowResult child;
    uint16_t expected = rgb ? CS_RgbTransitionAfterStep562F :
                              CS_PackedTransitionAfterStep55EC;
    push_word(memory, bus, state, state->count);
    push_word(memory, bus, state, state->source_cursor);
    push_word(memory, bus, state, state->output_cursor);
    push_word(memory, bus, state, expected); /* near CALL */
    child = lmn_step_palette_row_core(memory, *code_segment, state,
        rgb ? LMN_PALETTE_ROW_RGB : LMN_PALETTE_ROW_PACKED, bus);
    *state = child.state;
    *code_segment = child.code_segment;
    *continuation = child.continuation;
    if (child.status != LMN_PALETTE_ROW_READY) {
        *stopped = make_result(state, *code_segment, child.continuation,
            palette_row_status(child.status));
        return 0;
    }

    if (!actual_child_return(memory, bus, state, expected, continuation)) {
        *stopped = make_result(state, *code_segment, *continuation,
            LMN_PALETTE_TRANSITION_CHANGED_RETURN);
        return 0;
    }
    *continuation = expected;
    return 1;
}

static LmnDisplayStatusState display_status_state(
    const LmnVideoRestoreState *state) {
    LmnDisplayStatusState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static void apply_display_status_state(LmnVideoRestoreState *state,
    const LmnDisplayStatusState *from) {
    state->value = from->value;
    state->base_value = from->base_value;
    state->count = from->count;
    state->argument = from->argument;
    state->source_cursor = from->source_cursor;
    state->output_cursor = from->output_cursor;
    state->frame_cursor = from->frame_cursor;
    state->data_segment = from->data_segment;
    state->extra_segment = from->extra_segment;
    state->stack_segment = from->stack_segment;
    state->stack_offset = from->stack_offset;
    state->flags = from->flags;
}

/* CALL WaitForDisplayStatusBit3Cycle and check its actual live near RET. */
static int call_wait(uint8_t *memory, uint16_t code_segment,
    LmnVideoRestoreState *state, uint16_t after_call,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus,
    LmnPaletteTransitionResult *stopped, uint16_t *continuation) {
    LmnDisplayStatusState child_input;
    LmnDisplayStatusResult child;

    push_word(memory, bus, state, after_call); /* near CALL */
    child_input = display_status_state(state);
    child = lmn_wait_display_status_bit3_cycle_core(memory, &child_input,
                                                     ports, bus);
    apply_display_status_state(state, &child.state);
    *continuation = child.continuation;
    if (child.status != LMN_DISPLAY_STATUS_READY) {
        *stopped = make_result(state, code_segment, child.continuation,
            LMN_PALETTE_TRANSITION_MISSING_INPUT);
        return 0;
    }

    if (!actual_child_return(memory, bus, state, after_call, continuation)) {
        *stopped = make_result(state, code_segment, *continuation,
            LMN_PALETTE_TRANSITION_CHANGED_RETURN);
        return 0;
    }
    *continuation = after_call;
    return 1;
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

LmnPaletteTransitionResult lmn_transition_palette_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    enum LmnPaletteTransitionEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    LmnVideoRestoreState state = *input;
    LmnPaletteTransitionResult stopped;
    int rgb;
    uint16_t continuation;
#if PALETTE_TRANSITION_MUTATION == 4
    uint16_t cached_loop_cx, cached_loop_si, cached_loop_di;
#endif
#if PALETTE_TRANSITION_MUTATION == 5
    uint16_t cached_entry_es = state.extra_segment;
#endif

    if (entry != LMN_PALETTE_TRANSITION_SLOT1 &&
        entry != LMN_PALETTE_TRANSITION_SLOT2)
        return make_result(&state, code_segment, 0u,
                           LMN_PALETTE_TRANSITION_CHANGED_RETURN);

    /* 531E/536C: XOR AL,AL; MOV CX,10; MOV BX,100/200; JMP 55B7. */
    set_al(&state, 0u);
    logic8(&state.flags, 0u);
    state.count = 0x0010u;
    state.base_value = entry == LMN_PALETTE_TRANSITION_SLOT1 ?
                       0x0100u : 0x0200u;

    /* The full DS word is compared once. This chooses both writers and row
       cores for the whole original loop, even if a provider later changes it. */
    rgb = read_mode(memory, &state, bus) == 4u;

    /* PUSH ES; PUSH DS; POP ES. Both stack words are live through the bus. */
    push_word(memory, bus, &state, state.extra_segment);
    push_word(memory, bus, &state, state.data_segment);
    state.extra_segment = pop_word(memory, bus, &state);
    select_transition_pointers(memory, code_segment, &state, rgb, bus);

    for (;;) {
        int finished;
#if PALETTE_TRANSITION_MUTATION == 3
        /* Mutant: re-read the mode at each pass and use its other branch. */
        rgb = read_mode(memory, &state, bus) == 4u;
#endif
        if (!call_writer(memory, &code_segment, &state, rgb, ports, bus,
                         &stopped, &continuation))
            return stopped;

#if PALETTE_TRANSITION_MUTATION == 4
        cached_loop_cx = state.count;
        cached_loop_si = state.source_cursor;
        cached_loop_di = state.output_cursor;
#endif
        if (!call_row(memory, &code_segment, &state, rgb, bus,
                      &stopped, &continuation))
            return stopped;

        /* The caller JZ executes before waits. Wait TEST flags must not
           replace that already-taken control-flow decision. */
        finished = (state.flags & ZF) != 0;
#if PALETTE_TRANSITION_MUTATION == 2
        finished = 1;
#endif
        {
            if (!finished) {
                if (rgb) {
                    if (!call_wait(memory, code_segment, &state,
                            CS_RgbTransitionAfterWait5634, ports, bus,
                            &stopped, &continuation))
                        return stopped;
                } else {
#if PALETTE_TRANSITION_MUTATION == 1
                    if (!call_wait(memory, code_segment, &state,
                            CS_PackedTransitionAfterWait1, ports, bus,
                            &stopped, &continuation))
                        return stopped;
#else
                    if (!call_wait(memory, code_segment, &state,
                            CS_PackedTransitionAfterWait1, ports, bus,
                            &stopped, &continuation))
                        return stopped;
                    if (!call_wait(memory, code_segment, &state,
                            CS_PackedTransitionAfterWait2, ports, bus,
                            &stopped, &continuation))
                        return stopped;
                    if (!call_wait(memory, code_segment, &state,
                            CS_PackedTransitionAfterWait3, ports, bus,
                            &stopped, &continuation))
                        return stopped;
#endif
                }
            }
        }

        /* POP DI; POP SI; POP CX, retaining every live SS word/read. */
        {
            uint16_t popped = pop_word(memory, bus, &state);
#if PALETTE_TRANSITION_MUTATION == 4
            (void)popped;
            state.output_cursor = cached_loop_di;
#else
            state.output_cursor = popped;
#endif
        }
        {
            uint16_t popped = pop_word(memory, bus, &state);
#if PALETTE_TRANSITION_MUTATION == 4
            (void)popped;
            state.source_cursor = cached_loop_si;
#else
            state.source_cursor = popped;
#endif
        }
        {
            uint16_t popped = pop_word(memory, bus, &state);
#if PALETTE_TRANSITION_MUTATION == 4
            (void)popped;
            state.count = cached_loop_cx;
#else
            state.count = popped;
#endif
        }

        if (!finished)
            continue;

        /* Final POP ES is live. Mutation 5 still consumes that actual word. */
        {
            uint16_t popped = pop_word(memory, bus, &state);
#if PALETTE_TRANSITION_MUTATION == 5
            (void)popped;
            state.extra_segment = cached_entry_es;
#else
            state.extra_segment = popped;
#endif
        }
        return make_result(&state, code_segment,
            rgb ? CS_RgbPaletteTransitionReturn563D :
                  CS_PackedPaletteTransitionReturn5600,
            LMN_PALETTE_TRANSITION_READY);
    }
}

void lmn_transition_palette_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnPaletteTransitionEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    LmnVideoRestoreState input = state_from_registers(registers);
    LmnPaletteTransitionResult result = lmn_transition_palette_core(memory,
        registers->cs, &input, entry, ports, bus);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status != LMN_PALETTE_TRANSITION_READY)
        return;

    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u,
                                 registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
}
