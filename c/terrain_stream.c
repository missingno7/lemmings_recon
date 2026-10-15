#include "terrain_stream.h"
#include "lemmings_sym.h"

#ifndef TERRAIN_STREAM_MUTATION
#define TERRAIN_STREAM_MUTATION 0
#endif

#define MEMORY_MASK 0xfffffu
#define ARITHMETIC_FLAGS 0x08d5u

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_byte(uint8_t *memory, uint32_t address, uint16_t flags,
                         const LmnRasterBus *bus) {
    address &= MEMORY_MASK;
    return bus && bus->read_byte
        ? bus->read_byte(bus->context, memory, address, flags)
        : memory[address];
}

static void write_byte(uint8_t *memory, uint32_t address, uint8_t value,
                       uint16_t flags, const LmnRasterBus *bus) {
    address &= MEMORY_MASK;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, address, (uint8_t)value, flags, bus);
    write_byte(memory, (address + 1u) & MEMORY_MASK,
               (uint8_t)(value >> 8), flags, bus);
}

static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, address, flags, bus);
    uint8_t high = read_byte(memory, (address + 1u) & MEMORY_MASK, flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void push_word(uint8_t *memory, uint16_t segment,
                      uint16_t *stack_offset, uint16_t value,
                      uint16_t flags, const LmnRasterBus *bus) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, segment, *stack_offset, value, flags, bus);
}

static uint16_t even_parity_flag(uint8_t value) {
    unsigned parity = 0;
    for (unsigned bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0 ? 0x04u : 0u;
}

static uint16_t cmp_ax_ffff_flags(uint16_t flags, uint16_t ax) {
    uint16_t result = (uint16_t)(ax - 0xffffu);
    uint16_t changed = even_parity_flag((uint8_t)result);
    if (ax < 0xffffu) changed |= 0x01u;
    if ((ax ^ 0xffffu ^ result) & 0x10u) changed |= 0x10u;
    if (((ax ^ 0xffffu) & (ax ^ result)) & 0x8000u)
        changed |= 0x0800u;
    if (result == 0) changed |= 0x0040u;
    if (result & 0x8000u) changed |= 0x0080u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

LmnTerrainCommand lmn_read_terrain_command_core(
    uint8_t *memory, uint16_t data_segment, uint16_t command_cursor,
    uint16_t flags, const LmnRasterBus *bus) {
    uint8_t high_x = read_byte(memory,
        physical(data_segment, command_cursor), flags, bus);
    uint8_t low_x = read_byte(memory,
        physical(data_segment, (uint16_t)(command_cursor + 1u)), flags, bus);
    uint8_t high_y = read_byte(memory,
        physical(data_segment, (uint16_t)(command_cursor + 2u)), flags, bus);
    uint8_t low_y = read_byte(memory,
        physical(data_segment, (uint16_t)(command_cursor + 3u)), flags, bus);
#if TERRAIN_STREAM_MUTATION == 1
    uint16_t packed_horizontal = (uint16_t)(((uint16_t)low_x << 8) | high_x);
#else
    uint16_t packed_horizontal = (uint16_t)(((uint16_t)high_x << 8) | low_x);
#endif
    uint16_t packed_vertical = (uint16_t)(((uint16_t)high_y << 8) | low_y);
#if TERRAIN_STREAM_MUTATION == 3
    uint16_t advanced_cursor = (uint16_t)(command_cursor + 2u);
#else
    uint16_t advanced_cursor = (uint16_t)(command_cursor + 4u);
#endif
    uint16_t final_flags = cmp_ax_ffff_flags(flags, packed_horizontal);
#if TERRAIN_STREAM_MUTATION == 2
    uint16_t end_of_stream = (high_x == 0xffu);
#else
    uint16_t end_of_stream = (packed_horizontal == 0xffffu);
#endif
    return (LmnTerrainCommand){packed_horizontal, packed_vertical,
        advanced_cursor, final_flags, end_of_stream};
}

void lmn_read_terrain_command_adapter(
    uint8_t *memory, LmnRegs *regs, unsigned redraw,
    const LmnRasterBus *bus) {
    LmnTerrainCommand command = lmn_read_terrain_command_core(
        memory, regs->ds, regs->si, regs->flags, bus);
    regs->ax = command.packed_horizontal;
    regs->bx = command.packed_vertical;
    regs->si = command.command_cursor;
    regs->flags = command.flags;
    if (redraw)
        regs->ip = command.end_of_stream
            ? CS_RedrawTerrainFinished : CS_RedrawTerrainPieceCall;
    else
        regs->ip = command.end_of_stream
            ? CS_PrepareLevelObjectState : CS_SetupTerrainPieceCall;
}

static void copy_child_state(LmnDrawingSourceResult *destination,
                             const LmnDrawingSourceResult *source) {
    destination->work_value = source->work_value;
    destination->second_source_cursor = source->second_source_cursor;
    destination->packed_counts = source->packed_counts;
    destination->width_state = source->width_state;
    destination->source_cursor = source->source_cursor;
    destination->destination_cursor = source->destination_cursor;
    destination->control = source->control;
    destination->stack_offset = source->stack_offset;
    destination->flags = source->flags;
    destination->continuation = source->continuation;
}

LmnTerrainStreamResult lmn_draw_terrain_stream_core(
    uint8_t *memory, const LmnTerrainStreamCall *call, unsigned redraw,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnTerrainStreamResult result = {0};
    uint16_t command_entry = redraw ? CS_RedrawTerrainCommand
                                    : CS_SetupTerrainCommand;
    uint16_t after_piece = redraw ? CS_RedrawTerrainAfterPiece
                                  : CS_SetupTerrainAfterPiece;
    uint16_t finished = redraw ? CS_RedrawTerrainFinished
                               : CS_PrepareLevelObjectState;

    result.data_segment = call->data_segment;
    result.output_segment = call->output_segment;
    result.code_segment = call->code_segment;
    result.state.packed_counts = call->packed_counts;
    result.state.width_state = call->width_state;
    result.state.destination_cursor = call->mask_cursor;
    result.state.control = call->control;
    result.state.stack_offset = call->stack_offset;
    result.state.flags = call->flags;
    result.state.continuation = command_entry;

    /* The entry MOV SI,imm is independent of the initial register contents. */
    result.state.source_cursor = SEG09A9_LevelTerrainDefinitions;

    for (;;) {
        uint16_t cursor = result.state.source_cursor;
        LmnTerrainCommand command = lmn_read_terrain_command_core(
            memory, result.data_segment, cursor, result.state.flags, bus);
        result.state.work_value = command.packed_horizontal;
        result.state.second_source_cursor = command.packed_vertical;
        result.state.source_cursor = command.command_cursor;
        result.state.flags = command.flags;
        if (command.end_of_stream) {
            result.state.continuation = finished;
            return result;
        }

        /* CALL7C67 pushes the live near continuation before the child starts. */
        uint16_t stack_offset = result.state.stack_offset;
        push_word(memory, call->stack_segment, &stack_offset, after_piece,
                  command.flags, bus);
        LmnTerrainPieceCall piece_call = {
            result.data_segment, call->game_data_segment,
            call->stack_segment, stack_offset, result.code_segment,
            command.packed_horizontal, command.packed_vertical,
            command.command_cursor, result.output_segment, command.flags
        };
        LmnTerrainPieceResult child = lmn_draw_terrain_piece_core(
            memory, &piece_call, bus, ports);
        copy_child_state(&result.state, &child.drawing.plan.state);
        result.data_segment = child.drawing.source_segment;
        result.output_segment = child.drawing.output_segment;
        result.code_segment = child.code_segment;
#if TERRAIN_STREAM_MUTATION == 4
        result.data_segment = call->data_segment;
#endif

        if (!child.ready_to_return) {
            result.stopped = 1;
            result.changed_return = (uint16_t)(
                child.changed_far_return ||
                child.drawing.plan.changed_return);
            return result;
        }

        /* The child's7CBA POP SI is complete. RET reads the actual live word. */
        stack_offset = result.state.stack_offset;
        uint16_t returned_to = read_word(memory, call->stack_segment,
            stack_offset, result.state.flags, bus);
        stack_offset = (uint16_t)(stack_offset + 2u);
        result.state.stack_offset = stack_offset;
#if TERRAIN_STREAM_MUTATION == 5
        returned_to = after_piece;
#endif
        if (returned_to != after_piece) {
            result.state.continuation = returned_to;
            result.stopped = 1;
            result.changed_return = 1;
            return result;
        }

        result.state.continuation = command_entry;
    }
}

void lmn_draw_terrain_stream_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    unsigned redraw, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnTerrainStreamCall call = {
        regs->ds, game_data_segment, regs->cs,
        regs->ss, regs->sp, regs->cx, regs->dx,
        regs->di, regs->bp, regs->es, regs->flags
    };
    LmnTerrainStreamResult result = lmn_draw_terrain_stream_core(
        memory, &call, redraw, bus, ports);
    regs->ax = result.state.work_value;
    regs->bx = result.state.second_source_cursor;
    regs->cx = result.state.packed_counts;
    regs->dx = result.state.width_state;
    regs->si = result.state.source_cursor;
    regs->di = result.state.destination_cursor;
    regs->bp = result.state.control;
    regs->sp = result.state.stack_offset;
    regs->ds = result.data_segment;
    regs->es = result.output_segment;
    regs->cs = result.code_segment;
    regs->ip = result.state.continuation;
    regs->flags = result.state.flags;
}
