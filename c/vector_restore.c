#include "vector_restore.h"
#include "lemmings_sym.h"

#ifndef VECTOR_RESTORE_MUTATION
#define VECTOR_RESTORE_MUTATION 0
#endif

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset, uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

#if VECTOR_RESTORE_MUTATION == 1 || VECTOR_RESTORE_MUTATION == 4
static uint8_t direct_byte(const uint8_t *memory, uint32_t address) {
    return memory[address & 0xfffffu];
}

static uint16_t direct_word(const uint8_t *memory, uint16_t segment,
                            uint16_t offset) {
    uint32_t address = physical(segment, offset);
    return (uint16_t)(direct_byte(memory, address) |
        ((uint16_t)direct_byte(memory, address + 1u) << 8));
}
#endif

static void push_data_segment(uint8_t *memory, LmnVectorRestoreState *state,
                              const LmnRasterBus *bus) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               state->data_segment, state->flags);
}

static void pop_data_segment(uint8_t *memory, LmnVectorRestoreState *state,
                             const LmnRasterBus *bus) {
    state->data_segment = read_word(memory, bus, state->stack_segment,
                                    state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
}

static LmnVectorRestoreState call_set_vector(
    const LmnVectorRestoreServices *services, uint8_t *memory,
    const LmnVectorRestoreState *input) {
    LmnVectorRestoreState out = *input;
    services->set_vector(services->context, memory, input, &out);
    return out;
}

static LmnVectorRestoreState state_from_registers(const LmnRegs *registers) {
    LmnVectorRestoreState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnVectorRestoreState *state) {
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

static LmnVectorRestoreResult missing_provider(
    const LmnVectorRestoreState *state, uint16_t continuation) {
    LmnVectorRestoreResult out = {
        *state, continuation, LMN_VECTOR_RESTORE_MISSING_PROVIDER
    };
    return out;
}

LmnVectorRestoreResult lmn_restore_keyboard_vector_core(uint8_t *memory,
    const LmnVectorRestoreState *input,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus) {
    LmnVectorRestoreState state = *input;
    uint16_t saved_pointer, saved_segment;
#if VECTOR_RESTORE_MUTATION == 2
    uint16_t entry_stack_segment = input->stack_segment;
    uint16_t entry_pushed_offset = (uint16_t)(input->stack_offset - 2u);
#endif
#if VECTOR_RESTORE_MUTATION == 3
    uint16_t entry_data_segment = input->data_segment;
#endif
#if VECTOR_RESTORE_MUTATION == 1
    uint16_t cached_pointer = direct_word(memory, input->data_segment,
                                          SEG09A9_SavedKeyboardVector);
    uint16_t cached_segment = direct_word(memory, input->data_segment,
                                          SEG09A9_SavedKeyboardVector + 2u);
#endif

    push_data_segment(memory, &state, bus);
    state.value = 0x2509u;
    saved_pointer = read_word(memory, bus, state.data_segment,
                              SEG09A9_SavedKeyboardVector, state.flags);
    saved_segment = read_word(memory, bus, state.data_segment,
                              SEG09A9_SavedKeyboardVector + 2u, state.flags);
#if VECTOR_RESTORE_MUTATION == 1
    saved_pointer = cached_pointer;
    saved_segment = cached_segment;
#endif
    state.argument = saved_pointer;
    state.data_segment = saved_segment;

    if (!services || !services->set_vector)
        return missing_provider(&state, CS_RestoreKeyboardVectorInterrupt);
    state = call_set_vector(services, memory, &state);
#if VECTOR_RESTORE_MUTATION == 2
    state.stack_segment = entry_stack_segment;
    state.stack_offset = entry_pushed_offset;
#endif
    pop_data_segment(memory, &state, bus);
#if VECTOR_RESTORE_MUTATION == 3
    state.data_segment = entry_data_segment;
#endif
    {
        LmnVectorRestoreResult out = {
            state, CS_RestoreKeyboardVectorReturn, LMN_VECTOR_RESTORE_READY
        };
        return out;
    }
}

LmnVectorRestoreResult lmn_restore_private_vector_core(uint8_t *memory,
    const LmnVectorRestoreState *input,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus) {
    LmnVectorRestoreState state = *input;
    uint8_t vector_number;
    uint16_t saved_pointer, saved_segment;
#if VECTOR_RESTORE_MUTATION == 2
    uint16_t entry_stack_segment = input->stack_segment;
    uint16_t entry_pushed_offset = (uint16_t)(input->stack_offset - 2u);
#endif
#if VECTOR_RESTORE_MUTATION == 3
    uint16_t entry_data_segment = input->data_segment;
#endif
#if VECTOR_RESTORE_MUTATION == 1
    uint8_t cached_number = direct_byte(memory,
        physical(input->data_segment, SEG09A9_PrivateVectorNumber));
    uint16_t cached_pointer = direct_word(memory, input->data_segment,
                                          SEG09A9_SavedPrivateVector);
    uint16_t cached_segment = direct_word(memory, input->data_segment,
                                          SEG09A9_SavedPrivateVector + 2u);
#endif

    push_data_segment(memory, &state, bus);
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x2500u);
    vector_number = read_byte(memory, bus,
        physical(state.data_segment, SEG09A9_PrivateVectorNumber), state.flags);
    saved_pointer = read_word(memory, bus, state.data_segment,
                              SEG09A9_SavedPrivateVector, state.flags);
    saved_segment = read_word(memory, bus, state.data_segment,
                              SEG09A9_SavedPrivateVector + 2u, state.flags);
#if VECTOR_RESTORE_MUTATION == 1
    vector_number = cached_number;
    saved_pointer = cached_pointer;
    saved_segment = cached_segment;
#endif
    state.value = (uint16_t)(0x2500u | vector_number);
    state.argument = saved_pointer;
    state.data_segment = saved_segment;

    if (!services || !services->set_vector)
        return missing_provider(&state, CS_RestorePrivateVectorInterrupt);
    state = call_set_vector(services, memory, &state);
#if VECTOR_RESTORE_MUTATION == 2
    state.stack_segment = entry_stack_segment;
    state.stack_offset = entry_pushed_offset;
#endif
    pop_data_segment(memory, &state, bus);
#if VECTOR_RESTORE_MUTATION == 3
    state.data_segment = entry_data_segment;
#endif
    {
        LmnVectorRestoreResult out = {
            state, CS_RestorePrivateVectorReturn, LMN_VECTOR_RESTORE_READY
        };
        return out;
    }
}

static void finish_adapter(uint8_t *memory, LmnRegs *registers,
    LmnVectorRestoreResult result, const LmnRasterBus *bus) {
    apply_state(registers, &result.state);
    registers->ip = result.continuation;
    if (result.status != LMN_VECTOR_RESTORE_READY)
        return;

    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
}

void lmn_restore_keyboard_vector_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus) {
#if VECTOR_RESTORE_MUTATION == 4
    uint16_t entry_return = direct_word(memory, registers->ss, registers->sp);
#endif
    LmnVectorRestoreState input = state_from_registers(registers);
    LmnVectorRestoreResult result = lmn_restore_keyboard_vector_core(
        memory, &input, services, bus);
    finish_adapter(memory, registers, result, bus);
#if VECTOR_RESTORE_MUTATION == 4
    if (result.status == LMN_VECTOR_RESTORE_READY)
        registers->ip = entry_return;
#endif
}

void lmn_restore_private_vector_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnVectorRestoreServices *services, const LmnRasterBus *bus) {
#if VECTOR_RESTORE_MUTATION == 4
    uint16_t entry_return = direct_word(memory, registers->ss, registers->sp);
#endif
    LmnVectorRestoreState input = state_from_registers(registers);
    LmnVectorRestoreResult result = lmn_restore_private_vector_core(
        memory, &input, services, bus);
    finish_adapter(memory, registers, result, bus);
#if VECTOR_RESTORE_MUTATION == 4
    if (result.status == LMN_VECTOR_RESTORE_READY)
        registers->ip = entry_return;
#endif
}
