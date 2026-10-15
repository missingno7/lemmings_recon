#include "palette_channels.h"
#include "lemmings_sym.h"

#ifndef PALETTE_CHANNELS_MUTATION
#define PALETTE_CHANNELS_MUTATION 0
#endif

enum { CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
       SF = 0x0080, OF = 0x0800, ARITHMETIC_FLAGS = 0x08d5 };

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

static uint16_t read_stack_word16(uint8_t *memory, const LmnRasterBus *bus,
                                  uint16_t segment, uint16_t offset,
                                  uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnVideoRestoreState *state, uint16_t value) {
    uint32_t address;
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    address = physical(state->stack_segment, state->stack_offset);
    write_byte(memory, bus, address, (uint8_t)value, state->flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnVideoRestoreState *state) {
    uint16_t value = read_stack_word16(memory, bus, state->stack_segment,
                                       state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static uint8_t al(const LmnVideoRestoreState *state) {
    return (uint8_t)state->value;
}

static uint8_t ah(const LmnVideoRestoreState *state) {
    return (uint8_t)(state->value >> 8);
}

static uint8_t bl(const LmnVideoRestoreState *state) {
    return (uint8_t)state->base_value;
}

static uint8_t bh(const LmnVideoRestoreState *state) {
    return (uint8_t)(state->base_value >> 8);
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

static void set_bh(LmnVideoRestoreState *state, uint8_t value) {
    state->base_value = (uint16_t)((state->base_value & 0x00ffu) |
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

static uint8_t shr1(uint8_t value, uint16_t *flags) {
    uint8_t result = (uint8_t)(value >> 1);
    uint16_t changed = (uint16_t)(szp8(result) | (value & 1u));
    /* For SHR by one, OF receives the old most-significant bit. */
    if (value & 0x80u)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    return result;
}

static uint8_t shl1(uint8_t value, uint16_t *flags) {
    uint8_t result = (uint8_t)(value << 1);
    uint16_t carry = (uint16_t)((value & 0x80u) ? CF : 0u);
    uint16_t changed = (uint16_t)(szp8(result) | carry);
    /* For SHL by one, OF is the XOR of the result sign and carry. */
    if (((result >> 7) ^ (carry ? 1u : 0u)) != 0)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    return result;
}

static uint8_t and8(uint8_t left, uint8_t right, uint16_t *flags) {
    uint8_t result = (uint8_t)(left & right);
    /* AND clears CF/OF; AF is undefined and is represented as clear. */
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
                        szp8(result));
    return result;
}

static uint8_t or8(uint8_t left, uint8_t right, uint16_t *flags) {
    uint8_t result = (uint8_t)(left | right);
    /* OR clears CF/OF; AF is undefined and is represented as clear. */
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
                        szp8(result));
    return result;
}

static void cmp8(uint8_t left, uint8_t right, uint16_t *flags) {
    uint8_t result = (uint8_t)(left - right);
    uint16_t changed = szp8(result);
    if (left < right)
        changed |= CF;
    if ((left ^ right ^ result) & 0x10u)
        changed |= AF;
    if (((left ^ right) & (left ^ result) & 0x80u) != 0)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
}

static uint8_t inc8(uint8_t value, uint16_t *flags) {
    uint8_t result = (uint8_t)(value + 1u);
    uint16_t changed = (uint16_t)(szp8(result) | (*flags & CF));
    if ((value ^ 1u ^ result) & 0x10u)
        changed |= AF;
    if (value == 0x7fu)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    return result;
}

static uint8_t dec8(uint8_t value, uint16_t *flags) {
    uint8_t result = (uint8_t)(value - 1u);
    uint16_t changed = (uint16_t)(szp8(result) | (*flags & CF));
    if ((value ^ 1u ^ result) & 0x10u)
        changed |= AF;
    if (value == 0x80u)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    return result;
}

static int is_greater(const LmnVideoRestoreState *state) {
#if PALETTE_CHANNELS_MUTATION == 1
    /* Mutant: replace the two signed JG tests with unsigned JA tests. */
    return !(state->flags & ZF) && !(state->flags & CF);
#else
    return !(state->flags & ZF) &&
           (!!(state->flags & SF) == !!(state->flags & OF));
#endif
}

static void packed_step(LmnVideoRestoreState *state) {
    uint8_t decoded_target_source = bl(state);
    uint8_t decoded_target, high;
#if PALETTE_CHANNELS_MUTATION == 4
    uint8_t original_bh = bh(state);
#endif

#if PALETTE_CHANNELS_MUTATION == 4
    /* Mutant: decode the target's high selector bit from incoming BH. */
    decoded_target_source = original_bh;
#endif

    /* MOV AH,AL; SHR AL three times; SHL AH; AND AH,2; AND AL,1; OR. */
    set_ah(state, al(state));
    set_al(state, shr1(al(state), &state->flags));
    set_al(state, shr1(al(state), &state->flags));
    set_al(state, shr1(al(state), &state->flags));
    high = shl1(ah(state), &state->flags);
    high = and8(high, 0x02u, &state->flags);
    set_ah(state, high);
    set_al(state, and8(al(state), 0x01u, &state->flags));
    set_al(state, or8(al(state), ah(state), &state->flags));

    /* MOV BH,BL; SHR BL three times; SHL BH; AND BH,2; AND BL,1; OR. */
    set_bh(state, decoded_target_source);
    set_bl(state, shr1(bl(state), &state->flags));
    set_bl(state, shr1(bl(state), &state->flags));
    set_bl(state, shr1(bl(state), &state->flags));
    high = shl1(bh(state), &state->flags);
    high = and8(high, 0x02u, &state->flags);
    set_bh(state, high);
    set_bl(state, and8(bl(state), 0x01u, &state->flags));
    set_bl(state, or8(bl(state), bh(state), &state->flags));
    decoded_target = bl(state);

    /* CMP AL,BL; equal preserves BP, otherwise one unsigned step sets BP. */
    cmp8(al(state), decoded_target, &state->flags);
    if (state->flags & ZF) {
#if PALETTE_CHANNELS_MUTATION == 3
        /* Mutant: equal channels incorrectly clear BP instead of preserving it. */
        state->frame_cursor = 0;
#endif
    } else {
        if (state->flags & CF)
            set_al(state, inc8(al(state), &state->flags));
        else
            set_al(state, dec8(al(state), &state->flags));
        state->frame_cursor = 0x00ffu;
    }

    /* MOV AH,AL; SHL AL three times; SHR AH; AND AL,8; AND AH,1; OR. */
    set_ah(state, al(state));
    set_al(state, shl1(al(state), &state->flags));
    set_al(state, shl1(al(state), &state->flags));
    set_al(state, shl1(al(state), &state->flags));
    set_ah(state, shr1(ah(state), &state->flags));
    set_al(state, and8(al(state), 0x08u, &state->flags));
    set_ah(state, and8(ah(state), 0x01u, &state->flags));
    set_al(state, or8(al(state), ah(state), &state->flags));

#if PALETTE_CHANNELS_MUTATION == 4
    (void)original_bh;
#endif
}

static void rgb_step(LmnVideoRestoreState *state, uint16_t *continuation) {
    uint8_t target = ah(state);

    cmp8(al(state), target, &state->flags);
    if (state->flags & ZF) {
        *continuation = CS_PaletteRgbReturn571E;
        return;
    }

    if (is_greater(state))
        set_al(state, dec8(al(state), &state->flags));
    else
        set_al(state, inc8(al(state), &state->flags));

    set_bl(state, 0xffu); /* MOV BL,FF; does not change flags. */
    cmp8(al(state), target, &state->flags);

#if PALETTE_CHANNELS_MUTATION == 2
    /* Mutant: retain just the first RGB step and return after its CMP. */
    *continuation = CS_PaletteRgbReturn571E;
    return;
#endif

    if (state->flags & ZF) {
        *continuation = CS_PaletteRgbReturn571E;
        return;
    }
    if (is_greater(state)) {
        set_al(state, dec8(al(state), &state->flags));
        *continuation = CS_PaletteRgbDecrementReturn5725;
    } else {
        set_al(state, inc8(al(state), &state->flags));
        *continuation = CS_PaletteRgbReturn571E;
    }
}

static LmnPaletteChannelResult make_result(const LmnVideoRestoreState *state,
    uint16_t code_segment, uint16_t continuation,
    enum LmnPaletteChannelStatus status) {
    LmnPaletteChannelResult result;
    result.state = *state;
    result.code_segment = code_segment;
    result.continuation = continuation;
    result.status = status;
    return result;
}

LmnPaletteChannelResult lmn_step_palette_channel_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    enum LmnPaletteChannelEntry entry, const LmnRasterBus *bus) {
    LmnVideoRestoreState state = *input;
    uint16_t continuation = 0;
    enum LmnPaletteChannelStatus status = LMN_PALETTE_CHANNEL_READY;

    switch (entry) {
    case LMN_PALETTE_CHANNEL_HIGH:
        /* SHR AL,BL,AL,BL; AND AL,9; AND BL,9. */
        set_al(&state, shr1(al(&state), &state.flags));
        set_bl(&state, shr1(bl(&state), &state.flags));
        set_al(&state, shr1(al(&state), &state.flags));
        set_bl(&state, shr1(bl(&state), &state.flags));
        set_al(&state, and8(al(&state), 0x09u, &state.flags));
        set_bl(&state, and8(bl(&state), 0x09u, &state.flags));
        push_word(memory, bus, &state, CS_PaletteHighAfterStep567C);
        packed_step(&state);
        continuation = pop_word(memory, bus, &state);
        if (continuation != CS_PaletteHighAfterStep567C) {
#if PALETTE_CHANNELS_MUTATION != 6
            return make_result(&state, code_segment, continuation,
                               LMN_PALETTE_CHANNEL_CHANGED_RETURN);
#endif
        }
        set_al(&state, shl1(al(&state), &state.flags));
        set_bl(&state, shl1(bl(&state), &state.flags));
#if PALETTE_CHANNELS_MUTATION != 5
        set_al(&state, shl1(al(&state), &state.flags));
        set_bl(&state, shl1(bl(&state), &state.flags));
#endif
        continuation = CS_PaletteHighReturn5684;
        break;

    case LMN_PALETTE_CHANNEL_MIDDLE:
        /* SHR AL,BL; AND AL,9; AND BL,9. */
        set_al(&state, shr1(al(&state), &state.flags));
        set_bl(&state, shr1(bl(&state), &state.flags));
        set_al(&state, and8(al(&state), 0x09u, &state.flags));
        set_bl(&state, and8(bl(&state), 0x09u, &state.flags));
        push_word(memory, bus, &state, CS_PaletteMiddleAfterStep5691);
        packed_step(&state);
        continuation = pop_word(memory, bus, &state);
        if (continuation != CS_PaletteMiddleAfterStep5691) {
#if PALETTE_CHANNELS_MUTATION != 6
            return make_result(&state, code_segment, continuation,
                               LMN_PALETTE_CHANNEL_CHANGED_RETURN);
#endif
        }
        set_al(&state, shl1(al(&state), &state.flags));
        set_bl(&state, shl1(bl(&state), &state.flags));
        continuation = CS_PaletteMiddleReturn5695;
        break;

    case LMN_PALETTE_CHANNEL_LOW:
        /* This entry falls through two AND instructions into the shared body. */
        set_al(&state, and8(al(&state), 0x09u, &state.flags));
        set_bl(&state, and8(bl(&state), 0x09u, &state.flags));
        packed_step(&state);
        continuation = CS_PalettePackedReturn56E1;
        break;

    case LMN_PALETTE_CHANNEL_PACKED:
        /* Entry directly at the shared helper before its MOV/shift decoders. */
        packed_step(&state);
        continuation = CS_PalettePackedReturn56E1;
        break;

    case LMN_PALETTE_CHANNEL_RGB:
        rgb_step(&state, &continuation);
        break;
    }

    return make_result(&state, code_segment, continuation, status);
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

void lmn_step_palette_channel_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnPaletteChannelEntry entry, const LmnRasterBus *bus) {
    LmnVideoRestoreState input = state_from_registers(registers);
    LmnPaletteChannelResult result = lmn_step_palette_channel_core(memory,
        registers->cs, &input, entry, bus);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status != LMN_PALETTE_CHANNEL_READY)
        return;

    /* Outer RET observes the live returned SS:SP and reads low byte first. */
    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
}
