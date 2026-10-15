#include "display_status.h"
#include "lemmings_sym.h"

#ifndef DISPLAY_STATUS_MUTATION
#define DISPLAY_STATUS_MUTATION 0
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

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static uint16_t szp8(uint8_t value) {
    unsigned parity = 0, bit;
    uint16_t result = 0;
    for (bit = 0; bit < 8; ++bit)
        parity ^= (value >> bit) & 1u;
    if (!parity)
        result |= PF;
    if (value == 0)
        result |= ZF;
    if (value & 0x80u)
        result |= SF;
    return result;
}

#if DISPLAY_STATUS_MUTATION == 1
static uint16_t szp16(uint16_t value) {
    uint16_t result = szp8((uint8_t)value);
    if (value == 0)
        result |= ZF;
    else
        result &= (uint16_t)~ZF;
    if (value & 0x8000u)
        result |= SF;
    else
        result &= (uint16_t)~SF;
    return result;
}
#endif

static uint8_t add_port_offset(LmnDisplayStatusState *state) {
#if DISPLAY_STATUS_MUTATION == 1
    uint16_t before = state->argument;
    uint32_t sum = (uint32_t)before + 6u;
    uint16_t value = (uint16_t)sum;
    uint16_t changed = szp16(value);
    state->argument = value;
    state->flags = (uint16_t)((state->flags & (uint16_t)~ARITHMETIC_FLAGS) |
        changed | (sum > 0xffffu ? CF : 0u) |
        (((before ^ 6u ^ value) & 0x0010u) ? AF : 0u) |
        (((uint16_t)~(before ^ 6u) & (before ^ value) & 0x8000u) ? OF : 0u));
    return (uint8_t)value;
#else
    uint8_t before = (uint8_t)state->argument;
    uint16_t sum = (uint16_t)before + 6u;
    uint8_t value = (uint8_t)sum;
    state->argument = (uint16_t)((state->argument & 0xff00u) | value);
    state->flags = (uint16_t)((state->flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp8(value) | (sum > 0xffu ? CF : 0u) |
        (((before ^ 6u ^ value) & 0x10u) ? AF : 0u) |
        (((uint8_t)~(before ^ 6u) & (before ^ value) & 0x80u) ? OF : 0u));
    return value;
#endif
}

static void test_status_bit(LmnDisplayStatusState *state, uint8_t value) {
    uint8_t tested = (uint8_t)(value & 0x08u);
    /* TEST defines CF/OF as zero and sets SZP; AF is undefined here, so this
       core chooses a clear value while preserving controls. */
    state->flags = (uint16_t)((state->flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp8(tested));
}

static void refresh_port(uint8_t *memory, LmnDisplayStatusState *state,
                         const LmnRasterBus *bus) {
    state->argument = read_word(memory, bus, state->data_segment,
        SEG09A9_DisplayControllerBasePort, state->flags);
    (void)add_port_offset(state);
}

static LmnDisplayStatusResult missing_provider(
    const LmnDisplayStatusState *state) {
    LmnDisplayStatusResult result = {
        *state, CS_DisplayStatusWaitSet,
        LMN_DISPLAY_STATUS_MISSING_PROVIDER
    };
    return result;
}

LmnDisplayStatusResult lmn_wait_display_status_bit3_cycle_core(
    uint8_t *memory, const LmnDisplayStatusState *input,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    LmnDisplayStatusState state = *input;

    refresh_port(memory, &state, bus);
    if (!ports || !ports->in_byte)
        return missing_provider(&state);

#if DISPLAY_STATUS_MUTATION != 2
    for (;;) {
#if DISPLAY_STATUS_MUTATION == 3
        refresh_port(memory, &state, bus);
#endif
        state.value = (uint16_t)((state.value & 0xff00u) |
            ports->in_byte(ports->context, memory, state.argument, state.flags));
        test_status_bit(&state, (uint8_t)state.value);
        if (!(state.flags & ZF))
            break;
    }
#endif

    for (;;) {
#if DISPLAY_STATUS_MUTATION == 3
        refresh_port(memory, &state, bus);
#endif
        state.value = (uint16_t)((state.value & 0xff00u) |
            ports->in_byte(ports->context, memory, state.argument, state.flags));
        test_status_bit(&state, (uint8_t)state.value);
        if (state.flags & ZF)
            break;
    }

    {
        LmnDisplayStatusResult result = {
            state, CS_DisplayStatusReturn, LMN_DISPLAY_STATUS_READY
        };
        return result;
    }
}

static LmnDisplayStatusState state_from_registers(const LmnRegs *registers) {
    LmnDisplayStatusState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnDisplayStatusState *state) {
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

void lmn_wait_display_status_bit3_cycle_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
#if DISPLAY_STATUS_MUTATION == 4
    uint16_t cached_return = read_word(memory, bus, registers->ss,
        registers->sp, registers->flags);
#endif
    LmnDisplayStatusState input = state_from_registers(registers);
    LmnDisplayStatusResult result = lmn_wait_display_status_bit3_cycle_core(
        memory, &input, ports, bus);

    apply_state(registers, &result.state);
    registers->ip = result.continuation;
    if (result.status != LMN_DISPLAY_STATUS_READY)
        return;

#if DISPLAY_STATUS_MUTATION == 4
    registers->sp = (uint16_t)(registers->sp + 2u);
    registers->ip = cached_return;
#else
    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
#endif
}
