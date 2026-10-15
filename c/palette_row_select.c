#include "palette_row_select.h"
#include "lemmings_sym.h"

#ifndef PALETTE_ROW_SELECT_MUTATION
#define PALETTE_ROW_SELECT_MUTATION 0
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

#if PALETTE_ROW_SELECT_MUTATION != 4
static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}
#endif

/* The high byte is the physical successor, with the 20-bit bus wrap. */
static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

#if PALETTE_ROW_SELECT_MUTATION != 4
static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnVideoRestoreState *state, uint16_t value) {
    uint32_t address;
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    address = physical(state->stack_segment, state->stack_offset);
    write_byte(memory, bus, address, (uint8_t)value, state->flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), state->flags);
}
#endif

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnVideoRestoreState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
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
    uint16_t flags = (uint16_t)(szp8((uint8_t)value) & (uint16_t)~SF);
    if (value == 0)
        flags |= ZF;
    else
        flags &= (uint16_t)~ZF;
    if (value & 0x8000u)
        flags |= SF;
    else
        flags &= (uint16_t)~SF;
    return flags;
}

static void xor_ah_zero(LmnVideoRestoreState *state) {
    state->value &= 0x00ffu;
    state->flags = (uint16_t)((state->flags & (uint16_t)~ARITHMETIC_FLAGS) |
                              szp8(0));
}

static uint16_t add16(uint16_t left, uint16_t right, uint16_t *flags) {
    uint32_t sum = (uint32_t)left + (uint32_t)right;
    uint16_t result = (uint16_t)sum;
    uint16_t changed = szp16(result);
    if (sum > 0xffffu)
        changed |= CF;
    if ((left ^ right ^ result) & 0x0010u)
        changed |= AF;
    if ((~(left ^ right) & (left ^ result) & 0x8000u) != 0)
        changed |= OF;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
    return result;
}

static void cmp_word_four(LmnVideoRestoreState *state, uint16_t left) {
    uint16_t result = (uint16_t)(left - 4u);
    uint16_t changed = szp16(result);
    if (left < 4u)
        changed |= CF;
    if ((left ^ 4u ^ result) & 0x0010u)
        changed |= AF;
    if (((left ^ 4u) & (left ^ result) & 0x8000u) != 0)
        changed |= OF;
    state->flags = (uint16_t)((state->flags & (uint16_t)~ARITHMETIC_FLAGS) |
                              changed);
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

LmnPaletteRowResult lmn_select_and_step_palette_row_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    const LmnRasterBus *bus) {
    LmnVideoRestoreState state = *input;
    uint16_t mode, table_base;
    uint16_t target_pointer;
    enum LmnPaletteRowEntry entry;
#if PALETTE_ROW_SELECT_MUTATION == 5
    uint16_t cached_target_pointer;
#endif

    mode = read_word(memory, bus, state.data_segment,
                     SEG09A9_PaletteDisplayModeWord, state.flags);
#if PALETTE_ROW_SELECT_MUTATION == 1
    cmp_word_four(&state, (uint16_t)(mode & 0x00ffu));
#else
    cmp_word_four(&state, mode);
#endif
    if (state.flags & ZF) {
        entry = LMN_PALETTE_ROW_RGB;
        table_base = CS_RgbPalettePointerTable;
    } else {
        entry = LMN_PALETTE_ROW_PACKED;
        table_base = CS_PackedPalettePointerTable;
    }

#if PALETTE_ROW_SELECT_MUTATION == 5
    /* Mutant: cache BH's target before PUSH DS can alias that table word. */
    cached_target_pointer = read_word(memory, bus, code_segment,
        (uint16_t)(table_base + (uint16_t)((uint16_t)(state.base_value >> 8) * 2u)),
        state.flags);
#endif

#if PALETTE_ROW_SELECT_MUTATION == 4
    state.extra_segment = state.data_segment;
#else
    push_word(memory, bus, &state, state.data_segment);
    state.extra_segment = pop_word(memory, bus, &state);
#endif

#if PALETTE_ROW_SELECT_MUTATION == 2
    state.value = (uint16_t)((state.value & 0xff00u) |
                             ((uint16_t)(uint8_t)state.base_value & 7u));
#else
    state.value = (uint16_t)((state.value & 0xff00u) |
                             (uint8_t)state.base_value);
#endif
    xor_ah_zero(&state);
    state.value = add16(state.value, state.value, &state.flags);
    state.source_cursor = add16(table_base, state.value, &state.flags);
    state.source_cursor = read_word(memory, bus, code_segment,
                                    state.source_cursor, state.flags);

#if PALETTE_ROW_SELECT_MUTATION == 2
    state.value = (uint16_t)((state.value & 0xff00u) |
                             ((uint16_t)(uint8_t)(state.base_value >> 8) & 7u));
#elif PALETTE_ROW_SELECT_MUTATION == 3
    state.value = (uint16_t)((state.value & 0xff00u) |
                             (uint8_t)state.base_value);
#else
    state.value = (uint16_t)((state.value & 0xff00u) |
                             (uint8_t)(state.base_value >> 8));
#endif
    xor_ah_zero(&state);
    state.value = add16(state.value, state.value, &state.flags);
    state.output_cursor = add16(table_base, state.value, &state.flags);
#if PALETTE_ROW_SELECT_MUTATION == 5
    target_pointer = cached_target_pointer;
#else
    target_pointer = read_word(memory, bus, code_segment, state.output_cursor,
                               state.flags);
#endif
    state.output_cursor = target_pointer;

    {
        LmnPaletteRowResult result = lmn_step_palette_row_core(memory,
            code_segment, &state, entry, bus);
#if PALETTE_ROW_SELECT_MUTATION == 7
        if (result.status != LMN_PALETTE_ROW_READY)
            result.status = LMN_PALETTE_ROW_READY;
#endif
        return result;
    }
}

void lmn_select_and_step_palette_row_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnVideoRestoreState input = state_from_registers(registers);
    LmnPaletteRowResult result;
#if PALETTE_ROW_SELECT_MUTATION == 6
    uint16_t cached_outer_return = read_word(memory, bus,
        registers->ss, registers->sp, registers->flags);
#endif

    result = lmn_select_and_step_palette_row_core(memory, registers->cs,
                                                   &input, bus);
    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status != LMN_PALETTE_ROW_READY)
        return;

#if PALETTE_ROW_SELECT_MUTATION == 6
    registers->sp = (uint16_t)(registers->sp + 2u);
    registers->ip = cached_outer_return;
#else
    {
        LmnVideoRestoreState returned_state = result.state;
        registers->ip = pop_word(memory, bus, &returned_state);
        registers->sp = returned_state.stack_offset;
    }
#endif
}
