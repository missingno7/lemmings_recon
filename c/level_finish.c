#include "level_finish.h"
#include "lemmings_sym.h"
#include "minimap_column.h"
#include "vga_clear.h"

#ifndef LEVEL_FINISH_MUTATION
#define LEVEL_FINISH_MUTATION 0
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

/* Word memory operands use the physical successor byte, even at offset FFFF. */
static uint16_t read_word(uint8_t *memory, uint16_t segment,
                          uint16_t offset, uint16_t flags,
                          const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

static void push_word(uint8_t *memory, uint16_t stack_segment,
                      uint16_t *stack_offset, uint16_t value, uint16_t flags,
                      const LmnRasterBus *bus) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, stack_segment, *stack_offset, value, flags, bus);
}

/* Near CALL writes its return word low then high at the physical successor. */
static void push_call(uint8_t *memory, uint16_t stack_segment,
                      uint16_t *stack_offset, uint16_t return_ip,
                      uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address;
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    address = physical(stack_segment, *stack_offset);
#if LEVEL_FINISH_MUTATION == 4
    /* Mutant: preserve the word but reverse the observable CALL byte order. */
    write_byte(memory, bus, address + 1u, (uint8_t)(return_ip >> 8), flags);
    write_byte(memory, bus, address, (uint8_t)return_ip, flags);
#else
    write_byte(memory, bus, address, (uint8_t)return_ip, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(return_ip >> 8), flags);
#endif
}

static uint16_t pop_word(uint8_t *memory, uint16_t stack_segment,
                         uint16_t *stack_offset, uint16_t flags,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, stack_segment, *stack_offset, flags,
                               bus);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

/* Consumes the actual CALL word after a normal child result. */
static unsigned consume_call_return(uint8_t *memory,
                                    LmnLevelFinishResult *state,
                                    uint16_t stack_segment,
                                    uint16_t expected,
                                    const LmnRasterBus *bus) {
    uint16_t actual = pop_word(memory, stack_segment, &state->stack_offset,
                               state->flags, bus);
    state->continuation = actual;
    if (actual != expected) {
        state->changed_return = 1u;
#if LEVEL_FINISH_MUTATION == 3
        /* Mutant 3 ignores only ClearLevelDrawingTail's changed RET. */
        if (expected == CS_LevelFinishAfterClear) {
            state->changed_return = 0u;
            return 1u;
        }
#endif
        return 0u;
    }
    state->changed_return = 0u;
    return 1u;
}

static void copy_column_result(LmnLevelFinishResult *state,
                               const LmnMinimapColumnResult *column) {
    state->value = column->value;
    state->target_cursor = column->target_cursor;
    state->count = column->count;
    state->port_or_population = column->port_or_population;
    state->source_cursor = column->source_cursor;
    state->output_cursor = column->output_cursor;
    state->data_segment = column->data_segment;
    state->extra_segment = column->extra_segment;
    state->stack_offset = column->stack_offset;
    state->flags = column->flags;
    state->continuation = column->continuation;
    state->changed_return = column->changed_return;
}

LmnLevelFinishResult lmn_finish_level_initialization_core(
    uint8_t *memory, const LmnLevelFinishCall *call,
    const LmnRasterBus *bus) {
    LmnLevelFinishResult state = {0};
#if LEVEL_FINISH_MUTATION == 2
    uint16_t entry_data_segment = call->data_segment;
#endif
#if LEVEL_FINISH_MUTATION == 1
    unsigned fixed_iterations = 0u;
#endif

    state.target_cursor = call->height_state;
    state.source_cursor = call->source_cursor;
    state.data_segment = call->data_segment;
    state.stack_offset = call->stack_offset;
    state.flags = call->flags;
    state.continuation = CS_FinishLevelInitialization;

    /* CALL 3776 -> 36AD; that stub sets DI/CX then JMPs to the clear leaf. */
    push_call(memory, call->stack_segment, &state.stack_offset,
              CS_LevelFinishAfterClear, state.flags, bus);
    {
        LmnVgaClearResult clear = lmn_clear_vga_bytes_core(
            memory, call->stack_segment, state.stack_offset,
            0xcc40u, 0x0340u, state.flags, bus);
        state.value = clear.value;
        state.count = clear.count;
        state.port_or_population = clear.port;
        state.output_cursor = clear.output_cursor;
        state.extra_segment = clear.output_segment;
        state.stack_offset = clear.stack_offset;
        state.flags = clear.flags;
    }
    if (!consume_call_return(memory, &state, call->stack_segment,
                             CS_LevelFinishAfterClear, bus))
        return state;

    /* MOV CX,13 does not alter the clear child's flags. */
    state.count = 0x000du;
    state.continuation = CS_LevelFinishMinimapLoop;
    for (;;) {
        LmnMinimapColumnCall column_call;
        LmnMinimapColumnResult column;

        /* The PUSH observes the live CX from LOOP's previous iteration. */
        push_word(memory, call->stack_segment, &state.stack_offset,
                  state.count, state.flags, bus);
        push_call(memory, call->stack_segment, &state.stack_offset,
                  CS_LevelFinishAfterColumn, state.flags, bus);
        column_call = (LmnMinimapColumnCall){
            call->code_segment, state.data_segment, call->stack_segment,
            state.stack_offset, state.flags
        };
        column = lmn_update_minimap_column_core(memory, &column_call, bus);
        copy_column_result(&state, &column);

        if (column.changed_return) {
            return state;
        }

        if (!consume_call_return(memory, &state, call->stack_segment,
                                 CS_LevelFinishAfterColumn, bus))
            return state;

        /* POP CX reads the live SS save; LOOP then decrements without flags. */
        state.count = pop_word(memory, call->stack_segment, &state.stack_offset,
                               state.flags, bus);
        state.count = (uint16_t)(state.count - 1u);
#if LEVEL_FINISH_MUTATION == 1
        /* Mutant: use thirteen host iterations rather than the live LOOP CX. */
        ++fixed_iterations;
        if (fixed_iterations >= 13u)
            break;
#else
        if (state.count == 0u)
            break;
#endif
        state.continuation = CS_LevelFinishMinimapLoop;
    }

    /* MOV AX,[DS:1FF0] / MOV [DS:1FE4],AX use the live returned DS. */
#if LEVEL_FINISH_MUTATION == 2
    state.value = read_word(memory, entry_data_segment,
                            SEG09A9_LevelGraphicsSegment, state.flags, bus);
#else
    state.value = read_word(memory, state.data_segment,
                            SEG09A9_LevelGraphicsSegment, state.flags, bus);
#endif
    write_word(memory, state.data_segment, SEG09A9_GraphicsResourceSegment,
               state.value, state.flags, bus);
    state.continuation = CS_LevelFinishNearReturn;
    return state;
}

void lmn_finish_level_initialization_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    LmnLevelFinishCall call = {
        registers->cs, registers->ds, registers->ss, registers->sp,
        registers->bx, registers->si, registers->flags
    };
    LmnLevelFinishResult state =
        lmn_finish_level_initialization_core(memory, &call, bus);

    registers->ax = state.value;
    registers->bx = state.target_cursor;
    registers->cx = state.count;
    registers->dx = state.port_or_population;
    registers->si = state.source_cursor;
    registers->di = state.output_cursor;
    registers->ds = state.data_segment;
    registers->es = state.extra_segment;
    registers->sp = state.stack_offset;
    registers->flags = state.flags;
    if (state.changed_return) {
        registers->ip = state.continuation;
    } else {
        registers->ip = pop_word(memory, registers->ss, &registers->sp,
                                 state.flags, bus);
    }
}
