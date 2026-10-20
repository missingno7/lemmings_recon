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
#include "palette_row_select.h"
#include "display_pages.h"
#ifndef SPLIT_PALETTE_MUTATION
#define SPLIT_PALETTE_MUTATION 0
#endif

static uint8_t split_dec(uint16_t *flags,uint8_t v) {
    uint8_t out=(uint8_t)(v-1u);
    *flags=(uint16_t)((*flags&~(ARITHMETIC_FLAGS&~CF))|szp8(out)|
        ((v^1u^out)&AF)|(v==0x80u?OF:0u));return out;
}
static int split_ret(uint8_t *memory,uint16_t before_cs,LmnPaletteTransitionResult *r,
    uint16_t expected,const LmnRasterBus *bus) {
    if(r->status!=LMN_PALETTE_TRANSITION_READY)return 0;
    r->continuation=pop_word(memory,bus,&r->state);
#if SPLIT_PALETTE_MUTATION == 1
    r->continuation=expected;
#endif
    if(r->code_segment!=before_cs||r->continuation!=expected) {
        r->status=LMN_PALETTE_TRANSITION_CHANGED_RETURN;return 0;
    }
    return 1;
}
static LmnPaletteTransitionResult split_step(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,uint16_t expected,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=*input;push_word(memory,bus,&s,expected);
    LmnPaletteRowResult c=lmn_select_and_step_palette_row_core(memory,cs,&s,bus);
    LmnPaletteTransitionResult out=make_result(&c.state,c.code_segment,c.continuation,palette_row_status(c.status));
    (void)split_ret(memory,cs,&out,expected,bus);return out;
}
LmnPaletteTransitionResult lmn_step_split_palette_core(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,LmnSplitPaletteStepEntry entry,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=*input;LmnPaletteTransitionResult c;int targets=entry==LMN_SPLIT_PALETTE_TO_TARGETS;
    if(targets)push_word(memory,bus,&s,s.base_value);
    push_word(memory,bus,&s,s.argument);
    s.base_value=targets?(uint16_t)(s.base_value&0xff00u):0x0100u;
    c=split_step(memory,cs,&s,targets?CS_SplitPaletteAfterFirstStep5352:CS_SplitPaletteAfterFirstStep5330,bus);
    if(c.status)return c;
    s=c.state;cs=c.code_segment;
    if(targets) {
        s.count=pop_word(memory,bus,&s);
#if SPLIT_PALETTE_MUTATION == 3
        s.count=16u;
#endif
        s.base_value=pop_word(memory,bus,&s);
        s.argument=(uint16_t)((s.argument&0xff00u)|1u);
        if(s.flags&ZF)s.argument=(uint16_t)((s.argument&0xff00u)|split_dec(&s.flags,(uint8_t)s.argument));
        push_word(memory,bus,&s,s.argument);
#if SPLIT_PALETTE_MUTATION == 12
        s.base_value=(uint16_t)(((s.base_value&7u)<<8)|7u);
#else
        s.base_value=(uint16_t)(((s.base_value&255u)<<8)|7u);
#endif
    } else {
        s.base_value=(uint16_t)((s.base_value&0xff00u)|1u);
        if(s.flags&ZF)s.base_value=(uint16_t)((s.base_value&0xff00u)|split_dec(&s.flags,(uint8_t)s.base_value));
        s.count=pop_word(memory,bus,&s);push_word(memory,bus,&s,s.base_value);s.count=16u;s.base_value=0x0107u;
    }
    c=split_step(memory,cs,&s,targets?CS_SplitPaletteAfterSecondStep5362:CS_SplitPaletteAfterSecondStep5341,bus);
    if(c.status)return c;
    s=c.state;cs=c.code_segment;set_al(&s,1u);
    if(s.flags&ZF)set_al(&s,split_dec(&s.flags,(uint8_t)s.value));
    s.base_value=pop_word(memory,bus,&s);
#if SPLIT_PALETTE_MUTATION == 4
    s.base_value=input->base_value;
#endif
#if SPLIT_PALETTE_MUTATION == 2
    set_al(&s,!!((uint8_t)s.value|(uint8_t)s.base_value));
#else
    set_al(&s,(uint8_t)s.value|(uint8_t)s.base_value);
#endif
    logic8(&s.flags,(uint8_t)s.value);
    return make_result(&s,cs,targets?CS_SplitPaletteTargetsReturn536B:CS_SplitPaletteSlot1Return534A,LMN_PALETTE_TRANSITION_READY);
}
static LmnRegs split_registers(uint16_t cs,const LmnVideoRestoreState *s) {
    LmnRegs r={s->value,s->base_value,s->count,s->argument,s->source_cursor,s->output_cursor,s->frame_cursor,
        s->stack_offset,cs,s->data_segment,s->extra_segment,s->stack_segment,0u,s->flags};return r;
}
static LmnPaletteTransitionResult split_publish(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,LmnPalettePublishEntry entry,uint16_t expected,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=*input;push_word(memory,bus,&s,expected);LmnRegs r=split_registers(cs,&s);
    LmnPalettePublishResult child=lmn_publish_palette_core(memory,&r,entry,ports,bus);
    s=state_from_registers(&child.registers);
    LmnPaletteTransitionResult out=make_result(&s,child.registers.cs,child.registers.ip,
        palette_ports_status((enum LmnPalettePortsStatus)child.status));
    (void)split_ret(memory,cs,&out,expected,bus);return out;
}
static int split_input(uint8_t *memory,LmnVideoRestoreState *s,uint16_t ip,
    const LmnRasterBytePorts *ports,LmnPaletteTransitionResult *out) {
    if(!ports||!ports->in_byte){out->continuation=ip;out->state=*s;out->status=LMN_PALETTE_TRANSITION_MISSING_INPUT;return 0;}
    set_al(s,ports->in_byte(ports->context,memory,s->argument,s->flags));return 1;
}
LmnPaletteTransitionResult lmn_refresh_split_palette_core(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=*input;LmnPaletteTransitionResult out=make_result(&s,cs,0u,LMN_PALETTE_TRANSITION_READY);
    s.argument=read_word(memory,bus,s.data_segment,SEG09A9_DisplayControllerBasePort,s.flags);
    {uint8_t v=(uint8_t)s.argument,n=(uint8_t)(v+6u);
        s.flags=(uint16_t)((s.flags&~ARITHMETIC_FLAGS)|szp8(n)|(v>249u?CF:0u)|((v^6u^n)&AF)|((~(v^6u)&(v^n)&0x80u)?OF:0u));
#if SPLIT_PALETTE_MUTATION == 6
        s.argument=(uint16_t)(s.argument+6u);
#else
        s.argument=(uint16_t)((s.argument&0xff00u)|n);
#endif
    }
    do {if(!split_input(memory,&s,CS_SplitPaletteVerticalHighInput46C0,ports,&out))return out;logic8(&s.flags,(uint8_t)s.value&8u);}while(s.flags&ZF);
    do {if(!split_input(memory,&s,CS_SplitPaletteVerticalLowInput46C5,ports,&out))return out;logic8(&s.flags,(uint8_t)s.value&8u);}while(!(s.flags&ZF));
    s.flags&=(uint16_t)~0x200u;push_word(memory,bus,&s,s.argument);set_al(&s,0u);
    out=split_publish(memory,cs,&s,LMN_PALETTE_PUBLISH_EIGHT,CS_SplitPaletteAfterTopPublish46D2,ports,bus);
    if(out.status)return out;
    s=out.state;cs=out.code_segment;s.argument=pop_word(memory,bus,&s);
#if SPLIT_PALETTE_MUTATION == 5
    s.argument=0x3DAu;
#endif
#if SPLIT_PALETTE_MUTATION != 11
    s.flags&=(uint16_t)~0x200u;
#endif
    s.count=60u;
#if SPLIT_PALETTE_MUTATION == 7
    s.count=59u;
#endif
    do {
        do {if(!split_input(memory,&s,CS_SplitPaletteHorizontalLowInput46D7,ports,&out))return out;logic8(&s.flags,(uint8_t)s.value&1u);}while(!(s.flags&ZF));
        do {if(!split_input(memory,&s,CS_SplitPaletteHorizontalHighInput46DC,ports,&out))return out;logic8(&s.flags,(uint8_t)s.value&1u);}while(s.flags&ZF);
        --s.count;
    }while(s.count);
    set_al(&s,7u);out=split_publish(memory,cs,&s,LMN_PALETTE_PUBLISH_EIGHT,CS_SplitPaletteAfterBottomPublish46E9,ports,bus);
    if(out.status)return out;
    s=out.state;s.flags|=0x200u;return make_result(&s,out.code_segment,CS_SplitPaletteRasterReturn46EA,LMN_PALETTE_TRANSITION_READY);
}
LmnPaletteTransitionResult lmn_fade_split_palette_core(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=*input;LmnPaletteTransitionResult out;
    for(;;) {
        push_word(memory,bus,&s,CS_SplitPaletteFadeAfterRefresh46A5);
        out=lmn_refresh_split_palette_core(memory,cs,&s,ports,bus);
        if(!split_ret(memory,cs,&out,CS_SplitPaletteFadeAfterRefresh46A5,bus))return out;
        s=out.state;cs=out.code_segment;
        set_al(&s,0u);out=split_publish(memory,cs,&s,LMN_PALETTE_PUBLISH_UPPER_EIGHT,CS_SplitPaletteFadeAfterUpper46AB,ports,bus);
        if(out.status)return out;
    s=out.state;cs=out.code_segment;s.count=16u;s.argument=16u;
        push_word(memory,bus,&s,CS_SplitPaletteFadeAfterStep46B4);out=lmn_step_split_palette_core(memory,cs,&s,LMN_SPLIT_PALETTE_TO_SLOT1,bus);
        if(!split_ret(memory,cs,&out,CS_SplitPaletteFadeAfterStep46B4,bus))return out;
        s=out.state;cs=out.code_segment;
#if SPLIT_PALETTE_MUTATION == 10
        break;
#else
        if(s.flags&ZF)break;
#endif
    }
#if SPLIT_PALETTE_MUTATION == 13
    push_word(memory,bus,&s,CS_SplitPaletteFadeAfterStep46B4);
#endif
    LmnDisplayPagesResult clear=lmn_clear_full_drawing_page_core(memory,&s,bus);
    return make_result(&clear.state,cs,clear.continuation,clear.status==LMN_DISPLAY_PAGES_MISSING_CLEAR_BUS?LMN_PALETTE_TRANSITION_MISSING_CLEAR_BUS:
        clear.status?LMN_PALETTE_TRANSITION_MISSING_WORD_OUTPUT:LMN_PALETTE_TRANSITION_READY);
}
static LmnPaletteTransitionResult split_adapter_result(uint8_t *memory,LmnRegs *registers,
    LmnPaletteTransitionResult out,const LmnRasterBus *bus) {
    if(!out.status)out.continuation=pop_word(memory,bus,&out.state);
    apply_state(registers,&out.state);registers->cs=out.code_segment;registers->ip=out.continuation;return out;
}
LmnPaletteTransitionResult lmn_step_split_palette_adapter(uint8_t *memory,LmnRegs *registers,
    LmnSplitPaletteStepEntry entry,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=state_from_registers(registers);
    return split_adapter_result(memory,registers,lmn_step_split_palette_core(memory,registers->cs,&s,entry,bus),bus);
}
LmnPaletteTransitionResult lmn_refresh_split_palette_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=state_from_registers(registers);
    return split_adapter_result(memory,registers,lmn_refresh_split_palette_core(memory,registers->cs,&s,ports,bus),bus);
}
LmnPaletteTransitionResult lmn_fade_split_palette_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnVideoRestoreState s=state_from_registers(registers);
    return split_adapter_result(memory,registers,lmn_fade_split_palette_core(memory,registers->cs,&s,ports,bus),bus);
}
