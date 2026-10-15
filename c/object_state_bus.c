#include "object_state_bus.h"
#include "object_graphics.h"
#include "object_cells_bus.h"
#include "object_coordinates_bus.h"
#include "steel_cells_bus.h"
#include "lemmings_sym.h"

#ifndef STATE_BUS_MUTATION
#define STATE_BUS_MUTATION 0
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

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

/* CALL decrements SP once, then writes the return word low byte first. The
   high byte uses the next physical address, including 20-bit wrap at FFFFF. */
static void push_call(uint8_t *memory, const LmnObjectStateCall *call,
                      LmnObjectStateResult *state, uint16_t return_ip,
                      unsigned ordinal, const LmnRasterBus *bus) {
    uint16_t stack_segment = call->stack_segment;
    uint32_t address;

#if STATE_BUS_MUTATION == 1
    /* Mutant: place CALL frames through DS while the children still use SS. */
    stack_segment = call->data_segment;
#endif
#if STATE_BUS_MUTATION == 3
    /* Mutant: the second CALL stores an off-by-one continuation. */
    if (ordinal == 1u)
        return_ip = (uint16_t)(return_ip + 1u);
#else
    (void)ordinal;
#endif
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    address = physical(stack_segment, state->stack_offset);
#if STATE_BUS_MUTATION == 4
    /* Mutant: same final word, reversed observable byte-access order. */
    write_byte(memory, bus, address + 1u, (uint8_t)(return_ip >> 8),
               state->flags);
    write_byte(memory, bus, address, (uint8_t)return_ip, state->flags);
#else
    write_byte(memory, bus, address, (uint8_t)return_ip, state->flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(return_ip >> 8),
               state->flags);
#endif
}

/* A child leaves its actual caller word live. RET reads low then high through
   the bus and advances the live 16-bit SP only after both bytes are observed. */
static unsigned consume_return(uint8_t *memory, uint16_t stack_segment,
                               LmnObjectStateResult *state,
                               uint16_t expected, const LmnRasterBus *bus) {
    uint32_t address = physical(stack_segment, state->stack_offset);
    uint8_t low = read_byte(memory, bus, address, state->flags);
    uint8_t high = read_byte(memory, bus, address + 1u, state->flags);
    uint16_t actual = (uint16_t)(low | ((uint16_t)high << 8));

    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    state->continuation = actual;
    state->changed_return = (uint16_t)(actual != expected);
#if STATE_BUS_MUTATION == 2
    /* Mutant: report the changed target but continue into the next child. */
    return 0;
#else
    return state->changed_return;
#endif
}

LmnObjectStateResult lmn_prepare_level_object_state_bus_core(
    uint8_t *memory, const LmnObjectStateCall *call,
    const LmnRasterBus *bus) {
    LmnObjectStateResult state = {0};
    LmnObjectGraphicsResult graphics;
    LmnSteelInteractionCellsCall steel_call;
    LmnSteelInteractionCellsResult steel;
    LmnObjectCellsCall cells_call;
    LmnObjectCellsResult cells;
    LmnObjectCoordinatesCall coordinates_call;
    LmnObjectCoordinatesResult coordinates;

    state.stack_offset = call->stack_offset;
    state.base_cursor = call->base_cursor;
    state.dimension_state = call->product_high;
    state.flags = call->flags;

    push_call(memory, call, &state, CS_ObjectStateAfterGraphicsCopy, 0u, bus);
    graphics = lmn_copy_object_graphics_bus_core(memory, call->data_segment,
        call->stack_segment, state.stack_offset, state.dimension_state,
        state.flags, bus);
    state.value = graphics.value;
    state.cell_cursor = graphics.definition_cursor;
    state.remaining_records = graphics.count;
    state.dimension_state = graphics.product_high;
    state.source_cursor = graphics.source_cursor;
    state.definition_cursor = graphics.output_cursor;
    state.extra_segment = graphics.extra_segment;
    state.stack_offset = graphics.stack_offset;
    state.flags = graphics.flags;
    if (consume_return(memory, call->stack_segment, &state,
                       CS_ObjectStateAfterGraphicsCopy, bus))
        return state;

    push_call(memory, call, &state, CS_ObjectStateAfterSteelCells, 1u, bus);
    steel_call = (LmnSteelInteractionCellsCall){
        call->data_segment, call->stack_segment, state.stack_offset, state.flags
    };
    steel = lmn_write_steel_interaction_cells_bus_core(memory, &steel_call,
                                                       bus);
    state.value = steel.value;
    state.cell_cursor = steel.cell_cursor;
    state.remaining_records = steel.records_remaining;
    state.dimension_state = steel.dimensions;
    state.definition_cursor = steel.definition_cursor;
    state.stack_offset = steel.stack_offset;
    state.flags = steel.flags;
    if (consume_return(memory, call->stack_segment, &state,
                       CS_ObjectStateAfterSteelCells, bus))
        return state;

    push_call(memory, call, &state, CS_ObjectStateAfterObjectCells, 2u, bus);
    cells_call = (LmnObjectCellsCall){
        call->data_segment, call->stack_segment, state.stack_offset,
        state.cell_cursor, state.flags
    };
    cells = lmn_write_object_interaction_cells_bus_core(memory, &cells_call,
                                                        bus);
    state.value = cells.value;
    state.cell_cursor = cells.cell_cursor;
    state.remaining_records = cells.remaining_records;
    state.dimension_state = cells.dimension_state;
    state.source_cursor = cells.template_cursor;
    state.definition_cursor = cells.definition_cursor;
    state.base_cursor = cells.object_ordinal;
    state.stack_offset = cells.stack_offset;
    state.flags = cells.flags;
    if (consume_return(memory, call->stack_segment, &state,
                       CS_ObjectStateAfterObjectCells, bus))
        return state;

    push_call(memory, call, &state, CS_ObjectStateAfterCoordinates, 3u, bus);
    coordinates_call = (LmnObjectCoordinatesCall){
        call->data_segment, state.flags
    };
    coordinates = lmn_collect_type_one_object_coordinates_bus_core(
        memory, &coordinates_call, bus);
    state.value = coordinates.value;
    state.cell_cursor = coordinates.output_cursor;
    state.remaining_records = coordinates.count;
    state.source_cursor = coordinates.definition_cursor;
    state.base_cursor = coordinates.selected_count;
    state.flags = coordinates.flags;
    (void)consume_return(memory, call->stack_segment, &state,
                         CS_ObjectStateAfterCoordinates, bus);
    return state;
}

void lmn_prepare_level_object_state_bus_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    LmnObjectStateCall call = {
        registers->ds, registers->ss, registers->sp,
        registers->dx, registers->bp, registers->flags
    };
    LmnObjectStateResult state =
        lmn_prepare_level_object_state_bus_core(memory, &call, bus);

    registers->ax = state.value;
    registers->bx = state.cell_cursor;
    registers->cx = state.remaining_records;
    registers->dx = state.dimension_state;
    registers->si = state.source_cursor;
    registers->di = state.definition_cursor;
    registers->bp = state.base_cursor;
    registers->es = state.extra_segment;
    registers->sp = state.stack_offset;
    registers->flags = state.flags;
    registers->ip = state.continuation;
}
