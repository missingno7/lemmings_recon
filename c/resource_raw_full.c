#include "resource_raw_full.h"
#include "lemmings_sym.h"

#ifndef RAW_FULL_MUTATION
#define RAW_FULL_MUTATION 0
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

#if RAW_FULL_MUTATION == 4
static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnRawResourceFullState *state, uint16_t value) {
    uint32_t address;
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    address = physical(state->stack_segment, state->stack_offset);
    if (bus && bus->write_byte) {
        bus->write_byte(bus->context, memory, address, (uint8_t)value,
                        state->flags);
        bus->write_byte(bus->context, memory, (address + 1u) & 0xfffffu,
                        (uint8_t)(value >> 8), state->flags);
    } else {
        memory[address] = (uint8_t)value;
        memory[(address + 1u) & 0xfffffu] = (uint8_t)(value >> 8);
    }
}
#endif

static LmnRawResourceFullResult full_result(
    const LmnRawResourceFullState *state, uint16_t continuation,
    enum LmnRawResourceFullStatus status) {
    LmnRawResourceFullResult out = { *state, continuation, status };
    return out;
}

static LmnRawResourceFullState state_from_raw(
    const LmnRawResourceFullState *input, const LmnRawResourceResult *raw) {
    LmnRawResourceFullState state = *input;
    state.value = raw->value;
    state.base_value = raw->handle;
    state.count = raw->count;
    state.argument = raw->offset;
    state.data_segment = raw->segment;
    state.extra_segment = raw->extra_segment;
    state.stack_offset = raw->stack_offset;
    state.flags = raw->flags;
    return state;
}

LmnRawResourceFullResult lmn_read_raw_resource_full_core(uint8_t *memory,
    uint16_t main_data_segment, const LmnRawResourceFullState *input,
    const LmnRawResourceFullServices *services, const LmnRasterBus *bus) {
    LmnRawResourceCall call = {
        input->data_segment, input->argument, input->extra_segment,
        input->value, input->count, input->base_value,
        input->stack_segment, input->stack_offset, input->flags
    };
    LmnRawResourceResult raw = lmn_read_raw_resource_bus_core(
        memory, &call, services->raw, bus);
    LmnRawResourceFullState state = state_from_raw(input, &raw);

    if (!raw.error_stage)
        return full_result(&state, CS_RawResourceReturn,
                           LMN_RAW_RESOURCE_FULL_READY);

#if RAW_FULL_MUTATION == 3
    state.stack_offset = input->stack_offset;
#elif RAW_FULL_MUTATION == 4
    push_word(memory, bus, &state, CS_DatFileErrorTransfer);
#endif
    {
        LmnFileErrorResult child = lmn_file_error_core(memory,
            main_data_segment, &state, services->file_error, bus);
        enum LmnRawResourceFullStatus status;
        switch (child.status) {
        case LMN_FILE_ERROR_TERMINATED:
            status = LMN_RAW_RESOURCE_FULL_TERMINATED;
            break;
        case LMN_FILE_ERROR_MISSING_PROVIDER:
            status = LMN_RAW_RESOURCE_FULL_MISSING_PROVIDER;
            break;
        case LMN_FILE_ERROR_CHANGED_RETURN:
        default:
            status = LMN_RAW_RESOURCE_FULL_CHANGED_RETURN;
            break;
        }
        return full_result(&child.state, child.continuation, status);
    }
}

static LmnRawResourceFullState state_from_registers(
    const LmnRegs *registers) {
    LmnRawResourceFullState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnRawResourceFullState *state) {
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

void lmn_read_raw_resource_full_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRawResourceFullServices *services, const LmnRasterBus *bus) {
    uint32_t operand = physical(registers->cs,
                                CS_FileErrorDataSegmentOperand);
    /* This relocated immediate is instruction data, not a CPU data access. */
    uint16_t main_data_segment = (uint16_t)(memory[operand] |
        ((uint16_t)memory[(operand + 1u) & 0xfffffu] << 8));
    LmnRawResourceFullState input = state_from_registers(registers);
    LmnRawResourceFullResult out = lmn_read_raw_resource_full_core(memory,
        main_data_segment, &input, services, bus);

    apply_state(registers, &out.state);
    if (out.status == LMN_RAW_RESOURCE_FULL_READY) {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
        registers->sp = (uint16_t)(registers->sp + 2u);
    } else {
        registers->ip = out.continuation;
    }
}
