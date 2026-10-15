#include "background_drawing.h"
#include "lemmings_sym.h"

#ifndef BACKGROUND_DRAWING_MUTATION
#define BACKGROUND_DRAWING_MUTATION 0
#endif

enum { MEMORY_MASK = 0xfffff, ARITHMETIC_FLAGS = 0x08d5 };

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

static uint16_t read_word(uint8_t *memory, uint16_t segment,
                          uint16_t offset, uint16_t flags,
                          const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, address, flags, bus);
    uint8_t high = read_byte(memory, (address + 1u) & MEMORY_MASK,
                             flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, address, (uint8_t)value, flags, bus);
    write_byte(memory, (address + 1u) & MEMORY_MASK,
               (uint8_t)(value >> 8), flags, bus);
}

static void push_word(uint8_t *memory, uint16_t segment, uint16_t *sp,
                      uint16_t value, uint16_t flags,
                      const LmnRasterBus *bus) {
    *sp = (uint16_t)(*sp - 2u);
    write_word(memory, segment, *sp, value, flags, bus);
}

static uint16_t pop_word(uint8_t *memory, uint16_t segment, uint16_t *sp,
                         uint16_t flags, const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, segment, *sp, flags, bus);
    *sp = (uint16_t)(*sp + 2u);
    return value;
}

static unsigned even_parity(uint8_t value) {
    unsigned parity = 0;
    for (unsigned bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0;
}

static uint16_t szp16(uint16_t value) {
    return (uint16_t)((even_parity((uint8_t)value) ? 0x04u : 0u) |
                      (value == 0 ? 0x40u : 0u) |
                      (value & 0x8000u ? 0x80u : 0u));
}

static uint16_t logic16_flags(uint16_t flags, uint16_t value) {
    /* AF is undefined for XOR; use the cleared representative. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | szp16(value));
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right,
                            uint16_t result) {
    uint32_t sum = (uint32_t)left + right;
    uint16_t changed = szp16(result);
    if (sum > 0xffffu) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if ((~(left ^ right) & (left ^ result)) & 0x8000u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static void copy_renderer_state(LmnBackgroundDrawingState *state,
                                const LmnDrawingRenderResult *drawing) {
    const LmnDrawingSourceResult *render = &drawing->plan.state;
    state->value = render->work_value;
    state->base_value = render->second_source_cursor;
    state->count = render->packed_counts;
    state->argument = render->width_state;
    state->source_cursor = render->source_cursor;
    state->output_cursor = render->destination_cursor;
    state->frame_cursor = render->control;
    state->stack_offset = render->stack_offset;
    state->flags = render->flags;
    state->data_segment = drawing->source_segment;
    state->extra_segment = drawing->output_segment;
}

/* Compose the pinned same-CS far CALL. Intact relocated instruction operands
   are an entry precondition, as for the other direct native drawing callers.
   Instruction fetches are not data-bus reads. */
static int run_bitmap_call(uint8_t *memory,
    LmnBackgroundDrawingResult *result, uint16_t game_data_segment,
    uint16_t return_ip, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    uint16_t caller_segment = result->code_segment;
    uint16_t returned_ip, returned_cs;
    uint16_t stack_offset;
    LmnDrawingRenderResult drawing;

    /* 9A pushes CS first and the following IP second. */
    push_word(memory, result->state.stack_segment,
        &result->state.stack_offset, caller_segment, result->state.flags, bus);
    push_word(memory, result->state.stack_segment,
        &result->state.stack_offset, return_ip, result->state.flags, bus);

    {
        LmnPlanarBitmapCall call = {
            result->state.data_segment, game_data_segment,
            result->state.stack_segment, result->state.stack_offset,
            result->state.value, result->state.base_value,
            result->state.count, result->state.argument,
            result->state.source_cursor, result->state.output_cursor,
            result->state.frame_cursor, result->state.extra_segment,
            result->state.flags
        };
        drawing = lmn_draw_planar_bitmap_core(memory, &call, bus, ports);
    }
    copy_renderer_state(&result->state, &drawing);
    if (!drawing.body_returned) {
        result->continuation = drawing.plan.state.continuation;
        result->status = LMN_BACKGROUND_DRAWING_RENDERER_STOP;
        return 0;
    }

    /* The caller consumes the actual RETF frame, including overwritten words. */
    stack_offset = result->state.stack_offset;
    returned_ip = pop_word(memory, result->state.stack_segment, &stack_offset,
                           result->state.flags, bus);
    returned_cs = pop_word(memory, result->state.stack_segment, &stack_offset,
                           result->state.flags, bus);
    result->state.stack_offset = stack_offset;
    result->code_segment = returned_cs;
    result->continuation = returned_ip;

    if (returned_ip != return_ip || returned_cs != caller_segment) {
#if BACKGROUND_DRAWING_MUTATION == 6
        /* Mutant: hide a changed child RETF and resume the caller. */
        result->code_segment = caller_segment;
        result->continuation = return_ip;
        return 1;
#else
        result->status = LMN_BACKGROUND_DRAWING_CHANGED_RETURN;
        return 0;
#endif
    }

    result->continuation = return_ip;
    return 1;
}

static LmnBackgroundDrawingResult make_result(
    const LmnBackgroundDrawingState *state, uint16_t code_segment,
    uint16_t continuation, enum LmnBackgroundDrawingStatus status) {
    LmnBackgroundDrawingResult result = {
        *state, code_segment, continuation, status
    };
    return result;
}

LmnBackgroundDrawingResult lmn_draw_background_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnBackgroundDrawingState *input,
    enum LmnBackgroundDrawingEntry entry, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnBackgroundDrawingState state = *input;
    LmnBackgroundDrawingResult result;

    if (entry != LMN_BACKGROUND_DRAWING_FULL &&
        entry != LMN_BACKGROUND_DRAWING_FROM_ROW &&
        entry != LMN_BACKGROUND_DRAWING_TILES) {
        uint16_t stopped_at = CS_DrawScreenBackground;
        return make_result(&state, code_segment, stopped_at,
                           LMN_BACKGROUND_DRAWING_RENDERER_STOP);
    }

    if (entry == LMN_BACKGROUND_DRAWING_FULL) {
#if BACKGROUND_DRAWING_MUTATION != 1
        state.base_value = 0;
        state.flags = logic16_flags(state.flags, 0); /* XOR BX,BX */
#endif
    }

    /* 7E76 MOV AX,[DS:1FEE] / MOV [DS:1FE4],AX. */
    state.value = read_word(memory, state.data_segment,
        SEG09A9_UiGraphicsBufferSegment, state.flags, bus);
    write_word(memory, state.data_segment,
        SEG09A9_GraphicsResourceSegment, state.value, state.flags, bus);
    state.count = 4; /* MOV CX,4 */

    result = make_result(&state, code_segment, CS_BackgroundReturn,
                         LMN_BACKGROUND_DRAWING_READY);
    for (;;) {
#if BACKGROUND_DRAWING_MUTATION == 2
        uint16_t saved_row = result.state.base_value;
#endif
#if BACKGROUND_DRAWING_MUTATION == 3
        uint16_t saved_counter = result.state.count;
#endif
        uint16_t before, increment;

        /* 7E7F PUSH BX / 7E80 PUSH CX / 7E81 PUSH BX. */
        push_word(memory, result.state.stack_segment,
            &result.state.stack_offset, result.state.base_value,
            result.state.flags, bus);
        push_word(memory, result.state.stack_segment,
            &result.state.stack_offset, result.state.count,
            result.state.flags, bus);
        push_word(memory, result.state.stack_segment,
            &result.state.stack_offset, result.state.base_value,
            result.state.flags, bus);

        result.state.value = 0;
        result.state.flags = logic16_flags(result.state.flags, 0); /* XOR AX,AX */
        result.state.frame_cursor = 0x000cu;
        result.state.argument = 0x0140u;
        result.state.count = 0x0268u;
        result.state.source_cursor = 0;

        if (!run_bitmap_call(memory, &result, game_data_segment,
                CS_BackgroundFirstAfterBitmap, bus, ports))
            return result;

        result.state.value = 0x0140u; /* MOV AX,140h */
#if BACKGROUND_DRAWING_MUTATION == 2
        result.state.stack_offset = (uint16_t)(result.state.stack_offset + 2u);
        result.state.base_value = saved_row;
#else
        result.state.base_value = pop_word(memory, result.state.stack_segment,
            &result.state.stack_offset, result.state.flags, bus);
#endif
        result.state.frame_cursor = 0x000cu;
        result.state.argument = 0x0140u;
        result.state.count = 0x0268u;
        result.state.source_cursor = 0;

#if BACKGROUND_DRAWING_MUTATION == 4
        result.state.value = 0;
#endif
        if (!run_bitmap_call(memory, &result, game_data_segment,
                CS_BackgroundSecondAfterBitmap, bus, ports))
            return result;

#if BACKGROUND_DRAWING_MUTATION == 3
        result.state.stack_offset = (uint16_t)(result.state.stack_offset + 2u);
        result.state.count = saved_counter;
#else
        result.state.count = pop_word(memory, result.state.stack_segment,
            &result.state.stack_offset, result.state.flags, bus);
#endif
        result.state.base_value = pop_word(memory, result.state.stack_segment,
            &result.state.stack_offset, result.state.flags, bus);

        before = result.state.base_value;
#if BACKGROUND_DRAWING_MUTATION == 5
        increment = 0x0067u;
#else
        increment = 0x0068u;
#endif
        result.state.base_value = (uint16_t)(before + increment);
        result.state.flags = add16_flags(result.state.flags, before,
            increment, result.state.base_value);

        /* LOOP decrements CX and branches without changing flags. */
        result.state.count = (uint16_t)(result.state.count - 1u);
        if (result.state.count == 0)
            break;
    }

    result.continuation = CS_BackgroundReturn;
    result.status = LMN_BACKGROUND_DRAWING_READY;
    return result;
}

static LmnBackgroundDrawingState state_from_registers(
    const LmnRegs *registers) {
    LmnBackgroundDrawingState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnBackgroundDrawingState *state) {
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

void lmn_draw_background_adapter(uint8_t *memory, LmnRegs *registers,
    uint16_t game_data_segment, enum LmnBackgroundDrawingEntry entry,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnBackgroundDrawingState input = state_from_registers(registers);
    LmnBackgroundDrawingResult result = lmn_draw_background_core(memory,
        registers->cs, game_data_segment, &input, entry, bus, ports);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status == LMN_BACKGROUND_DRAWING_READY) {
        registers->ip = pop_word(memory, registers->ss, &registers->sp,
                                 registers->flags, bus);
    }
}
