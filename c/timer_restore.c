#include "timer_restore.h"
#include "lemmings_sym.h"

#ifndef TIMER_RESTORE_MUTATION
#define TIMER_RESTORE_MUTATION 0
#endif

#define FLAG_CF 0x0001u
#define FLAG_PF 0x0004u
#define FLAG_ZF 0x0040u
#define FLAG_SF 0x0080u
#define FLAG_IF 0x0200u
#define FLAG_OF 0x0800u

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

static void push_data_segment(uint8_t *memory, LmnTimerRestoreState *state,
                              const LmnRasterBus *bus) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               state->data_segment, state->flags);
}

static void pop_data_segment(uint8_t *memory, LmnTimerRestoreState *state,
                             const LmnRasterBus *bus) {
    state->data_segment = read_word(memory, bus, state->stack_segment,
                                    state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
}

static void xor_zero_flags(LmnTimerRestoreState *state) {
    /* XOR's AF is undefined here; retaining its incoming value is permitted. */
    state->flags = (uint16_t)((state->flags &
        (uint16_t)~(FLAG_CF | FLAG_PF | FLAG_ZF | FLAG_SF | FLAG_OF)) |
        FLAG_PF | FLAG_ZF);
}

static LmnTimerRestoreState call_set_clock(
    const LmnTimerRestoreServices *services, uint8_t *memory,
    const LmnTimerRestoreState *input) {
    LmnTimerRestoreState out = *input;
    services->set_clock(services->context, memory, input, &out);
    return out;
}

static LmnTimerRestoreState state_from_registers(const LmnRegs *registers) {
    LmnTimerRestoreState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnTimerRestoreState *state) {
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

static LmnTimerRestoreResult missing_provider(
    const LmnTimerRestoreState *state, uint16_t continuation) {
    LmnTimerRestoreResult out = {
        *state, continuation, LMN_TIMER_RESTORE_MISSING_PROVIDER
    };
    return out;
}

LmnTimerRestoreResult lmn_restore_timer_state_core(uint8_t *memory,
    const LmnTimerRestoreState *input,
    const LmnTimerRestoreServices *services, const LmnRasterBus *bus) {
    LmnTimerRestoreState state = *input;
#if TIMER_RESTORE_MUTATION == 1
    uint16_t incoming_if = (uint16_t)(state.flags & FLAG_IF);
#endif
    uint16_t vector_offset, vector_segment;
    uint16_t clock_segment;

    /* PUSH DS; CLI; MOV AL,36h. */
    push_data_segment(memory, &state, bus);
    state.flags = (uint16_t)(state.flags & (uint16_t)~FLAG_IF);
    state.value = (uint16_t)((state.value & 0xff00u) | 0x0036u);

    /* The first OUT is the missing-provider boundary. OUT callbacks can make
       device-visible memory changes but do not edit this CPU state. */
    if (!services || !services->out_byte)
        return missing_provider(&state, CS_TimerRestoreControlPort);
    services->out_byte(services->context, 0x43u, 0x36u, state.flags);

    /* XOR AL,AL; OUT 40h,AL; OUT 40h,AL; XOR AX,AX. */
    state.value = (uint16_t)(state.value & 0xff00u);
    xor_zero_flags(&state);
    services->out_byte(services->context, 0x40u, 0x00u, state.flags);
    services->out_byte(services->context, 0x40u, 0x00u, state.flags);
    state.value = 0;
    xor_zero_flags(&state);

    /* LES BX,[DS:1FBE] reads both words through entry DS, offset first. */
    vector_offset = read_word(memory, bus, state.data_segment,
                              SEG09A9_SavedTimerVector, state.flags);
    vector_segment = read_word(memory, bus, state.data_segment,
                               SEG09A9_SavedTimerVector + 2u, state.flags);
    state.base_value = vector_offset;
    state.extra_segment = vector_segment;
    state.data_segment = 0;

    /* The original writes offset then segment; mutation 3 reverses words. */
#if TIMER_RESTORE_MUTATION == 3
    write_word(memory, bus, state.data_segment, 0x0022u,
               state.extra_segment, state.flags);
    write_word(memory, bus, state.data_segment, 0x0020u,
               state.base_value, state.flags);
#else
    write_word(memory, bus, state.data_segment, 0x0020u,
               state.base_value, state.flags);
    write_word(memory, bus, state.data_segment, 0x0022u,
               state.extra_segment, state.flags);
#endif

    /* STI; POP DS from the live SS:SP. */
#if TIMER_RESTORE_MUTATION == 1
    state.flags = (uint16_t)((state.flags & (uint16_t)~FLAG_IF) | incoming_if);
#else
    state.flags = (uint16_t)(state.flags | FLAG_IF);
#endif
    pop_data_segment(memory, &state, bus);

#if TIMER_RESTORE_MUTATION == 2
    clock_segment = input->data_segment;
#else
    clock_segment = state.data_segment;
#endif
    state.count = read_word(memory, bus, clock_segment,
                            SEG09A9_SavedBiosClockHigh, state.flags);
    state.argument = read_word(memory, bus, clock_segment,
                               SEG09A9_SavedBiosClockLow, state.flags);
    /* MOV AH,1 leaves AL zero and changes no flags. */
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x0100u);

    if (!services || !services->set_clock)
        return missing_provider(&state, CS_TimerRestoreClockInterrupt);
    state = call_set_clock(services, memory, &state);

    {
        LmnTimerRestoreResult out = {
            state, CS_TimerRestoreReturn, LMN_TIMER_RESTORE_READY
        };
        return out;
    }
}

static void finish_adapter(uint8_t *memory, LmnRegs *registers,
    LmnTimerRestoreResult result, const LmnRasterBus *bus,
    uint16_t entry_stack_segment, uint16_t entry_stack_offset) {
    apply_state(registers, &result.state);
    registers->ip = result.continuation;
    if (result.status != LMN_TIMER_RESTORE_READY)
        return;

    {
        uint16_t return_segment = registers->ss;
        uint16_t return_offset = registers->sp;
#if TIMER_RESTORE_MUTATION == 4
        return_segment = entry_stack_segment;
        return_offset = entry_stack_offset;
#else
        (void)entry_stack_segment;
        (void)entry_stack_offset;
#endif
        uint32_t address = physical(return_segment, return_offset);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
}

void lmn_restore_timer_state_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnTimerRestoreServices *services, const LmnRasterBus *bus) {
    uint16_t entry_stack_segment = registers->ss;
    uint16_t entry_stack_offset = registers->sp;
    LmnTimerRestoreState input = state_from_registers(registers);
    LmnTimerRestoreResult result = lmn_restore_timer_state_core(
        memory, &input, services, bus);
    finish_adapter(memory, registers, result, bus,
                   entry_stack_segment, entry_stack_offset);
}
