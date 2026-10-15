#include "resource_select_full.h"
#include "lemmings_sym.h"
#include <stddef.h>

#ifndef SELECT_FULL_MUTATION
#define SELECT_FULL_MUTATION 0
#endif

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint16_t read_word(const uint8_t *memory, uint16_t segment,
                          uint16_t offset) {
    uint32_t address = physical(segment, offset);
    return (uint16_t)(memory[address] |
        ((uint16_t)memory[(address + 1u) & 0xfffffu] << 8));
}

#if SELECT_FULL_MUTATION == 3
static void push_word(uint8_t *memory, LmnResourceSelectionFullState *state,
                      uint16_t value) {
    uint32_t address;
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    address = physical(state->stack_segment, state->stack_offset);
    memory[address] = (uint8_t)value;
    memory[(address + 1u) & 0xfffffu] = (uint8_t)(value >> 8);
}
#endif

static LmnResourceSelectionFullState state_from_selection(
    const LmnDatFileCall *selection) {
    LmnResourceSelectionFullState state = {
        selection->value, selection->handle, selection->count,
        selection->filename_offset, selection->source_cursor,
        selection->output_cursor, selection->base_cursor,
        selection->segment, selection->extra_segment,
        selection->stack_segment, selection->stack_offset, selection->flags
    };
    return state;
}

static LmnResourceSelectionFullResult full_result(
    const LmnResourceSelectionFullState *state, uint16_t continuation,
    enum LmnResourceSelectionFullStatus status) {
    LmnResourceSelectionFullResult out = { *state, continuation, status };
    return out;
}

static enum LmnResourceSelectionFullStatus file_error_status(
    enum LmnFileErrorStatus status) {
    switch (status) {
    case LMN_FILE_ERROR_TERMINATED:
        return LMN_RESOURCE_SELECTION_FULL_TERMINATED;
    case LMN_FILE_ERROR_MISSING_PROVIDER:
        return LMN_RESOURCE_SELECTION_FULL_MISSING_PROVIDER;
    case LMN_FILE_ERROR_CHANGED_RETURN:
    default:
        return LMN_RESOURCE_SELECTION_FULL_CHANGED_RETURN;
    }
}

static enum LmnResourceSelectionFullStatus cleanup_status(
    enum LmnFatalCleanupStatus status) {
    switch (status) {
    case LMN_FATAL_CLEANUP_TERMINATED:
        return LMN_RESOURCE_SELECTION_FULL_TERMINATED;
    case LMN_FATAL_CLEANUP_MISSING_PROVIDER:
        return LMN_RESOURCE_SELECTION_FULL_MISSING_PROVIDER;
    case LMN_FATAL_CLEANUP_CHANGED_RETURN:
    default:
        return LMN_RESOURCE_SELECTION_FULL_CHANGED_RETURN;
    }
}

LmnResourceSelectionFullResult lmn_load_selected_resources_full_core(
    uint8_t *memory, uint16_t error_main_data_segment,
    const LmnDatFileCall *input, const LmnDatLoadSegments *segments,
    const LmnResourceSelectionFullServices *services) {
    LmnResourceSelectionExecution selection =
        lmn_load_selected_resources_execution_core(memory, input, segments,
                                                   services->selection);
    LmnResourceSelectionFullState state = state_from_selection(&selection.state);
    enum LmnResourceSelectionStatus transfer = selection.status;

#if SELECT_FULL_MUTATION == 4
    if (transfer == LMN_RESOURCE_SELECTION_CHANGED_RETURN &&
        selection.continuation == CS_DatFileErrorTransfer)
        transfer = LMN_RESOURCE_SELECTION_FILE_ERROR;
    else if (transfer == LMN_RESOURCE_SELECTION_CHANGED_RETURN &&
             selection.continuation == CS_DatFatalTransfer)
        transfer = LMN_RESOURCE_SELECTION_CLEANUP;
#endif

    if (transfer == LMN_RESOURCE_SELECTION_READY)
        return full_result(&state, selection.continuation,
                           LMN_RESOURCE_SELECTION_FULL_READY);
    if (transfer == LMN_RESOURCE_SELECTION_CHANGED_RETURN)
        return full_result(&state, selection.continuation,
                           LMN_RESOURCE_SELECTION_FULL_CHANGED_RETURN);

#if SELECT_FULL_MUTATION == 2
    state.stack_offset = input->stack_offset;
#elif SELECT_FULL_MUTATION == 3
    push_word(memory, &state, selection.continuation);
#endif

    if (transfer == LMN_RESOURCE_SELECTION_FILE_ERROR) {
        LmnFileErrorResult child = lmn_file_error_core(memory,
            error_main_data_segment, &state, services->file_error, NULL);
        return full_result(&child.state, child.continuation,
                           file_error_status(child.status));
    } else {
        LmnFatalCleanupResult child = lmn_fatal_cleanup_core(memory, &state,
            0, services->cleanup, NULL);
        return full_result(&child.state, child.continuation,
                           cleanup_status(child.status));
    }
}

static void apply_state(LmnRegs *registers,
                        const LmnResourceSelectionFullState *state) {
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

void lmn_load_selected_resources_full_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnResourceSelectionFullServices *services) {
    uint32_t operand = physical(registers->cs,
                                CS_FileErrorDataSegmentOperand);
    uint16_t error_main_data_segment = (uint16_t)(memory[operand] |
        ((uint16_t)memory[(operand + 1u) & 0xfffffu] << 8));
    LmnDatFileCall input = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    LmnDatLoadSegments segments = {
        read_word(memory, registers->cs,
                  (uint16_t)(CS_CheckDatFile + 0x33u)),
        read_word(memory, registers->cs,
                  (uint16_t)(CS_SelectCachedDatFile + 0x50u)),
        read_word(memory, registers->cs,
                  (uint16_t)(CS_ReadDatBytes + 8u)),
        read_word(memory, registers->cs,
                  (uint16_t)(CS_DatReadFailure + 1u))
    };
    LmnResourceSelectionFullResult out =
        lmn_load_selected_resources_full_core(memory,
            error_main_data_segment, &input, &segments, services);

    apply_state(registers, &out.state);
    if (out.status == LMN_RESOURCE_SELECTION_FULL_READY) {
        registers->ip = read_word(memory, registers->ss, registers->sp);
        registers->sp = (uint16_t)(registers->sp + 2u);
    } else {
        registers->ip = out.continuation;
    }
}
