#include "display_pages.h"
#include "lemmings_sym.h"

#ifndef DISPLAY_PAGES_MUTATION
#define DISPLAY_PAGES_MUTATION 0
#endif

enum { DF = 0x0400, VGA_SEGMENT = 0xa000, VGA_SEQUENCER = 0x3c4,
       VGA_GRAPHICS = 0x3ce, PAGE_BYTES = 0x6d60 };

/* Segmented byte accesses use a 20-bit physical address and wrap at 1 MiB. */
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

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

/* Words read low byte first; the second byte is the physical successor. */
static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnDisplayPagesState *state, uint16_t value) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               value, state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnDisplayPagesState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static LmnDisplayPagesResult make_result(
    const LmnDisplayPagesState *state, uint16_t continuation,
    enum LmnDisplayPagesStatus status) {
    LmnDisplayPagesResult result = { *state, continuation, status };
    return result;
}

LmnDisplayPagesResult lmn_copy_drawing_page_core(uint8_t *memory,
    const LmnDisplayPagesState *input, const LmnRasterBus *bus) {
    LmnDisplayPagesState state = *input;
    uint16_t source_step, destination_step;
#if DISPLAY_PAGES_MUTATION == 1
    uint16_t cached_source_origin = read_word(memory, bus,
        input->data_segment, SEG09A9_DrawingOrigin, input->flags);
    uint16_t cached_destination_origin = read_word(memory, bus,
        input->data_segment, SEG09A9_AlternateDrawingOrigin, input->flags);
#endif

    /* MOV DX,3C4 / MOV AX,0F02 / MOV [SS:0008],AX precede the OUT. */
    state.argument = VGA_SEQUENCER;
    state.value = 0x0f02u;
    write_word(memory, bus, state.stack_segment, SEG143E_VgaMapMaskMirror, state.value,
               state.flags);
    if (!bus || !bus->out_word)
        return make_result(&state, CS_DisplayPageCopyMapMaskOutput,
                           LMN_DISPLAY_PAGES_MISSING_PORT);
    bus->out_word(bus->context, state.argument, state.value, state.flags);

    /* MOV DX,3CE / MOV AX,0105 / MOV [SS:0000],AX precede the second OUT. */
    state.argument = VGA_GRAPHICS;
    state.value = 0x0105u;
    write_word(memory, bus, state.stack_segment, SEG143E_VgaGraphicsModeMirror, state.value,
               state.flags);
    if (!bus || !bus->out_word)
        return make_result(&state, CS_DisplayPageCopyModeOutput,
                           LMN_DISPLAY_PAGES_MISSING_PORT);
    bus->out_word(bus->context, state.argument, state.value, state.flags);

    /* PUSH DS occurs before the two origin words are read from live DS. */
    push_word(memory, bus, &state, state.data_segment);
#if DISPLAY_PAGES_MUTATION == 1
    state.source_cursor = cached_source_origin;
    state.output_cursor = cached_destination_origin;
#else
    state.source_cursor = read_word(memory, bus, state.data_segment,
        SEG09A9_DrawingOrigin, state.flags);
    state.output_cursor = read_word(memory, bus, state.data_segment,
        SEG09A9_AlternateDrawingOrigin, state.flags);
#endif

    state.value = VGA_SEGMENT;
    state.data_segment = VGA_SEGMENT;
    state.extra_segment = VGA_SEGMENT;
    state.count = PAGE_BYTES;
    destination_step = (state.flags & DF) ? 0xffffu : 1u;
#if DISPLAY_PAGES_MUTATION == 2
    destination_step = 1u;
#endif
    source_step = destination_step;
#if DISPLAY_PAGES_MUTATION == 3
    source_step = 0u;
#endif

    /* MOVSB reads the source before writing the destination on every byte. */
    while (state.count != 0u) {
        uint8_t value = read_byte(memory, bus,
            physical(state.data_segment, state.source_cursor), state.flags);
        write_byte(memory, bus,
            physical(state.extra_segment, state.output_cursor), value,
            state.flags);
        state.source_cursor = (uint16_t)(state.source_cursor + source_step);
        state.output_cursor = (uint16_t)(state.output_cursor + destination_step);
        state.count = (uint16_t)(state.count - 1u);
    }

    /* POP DS consumes the live SS:SP word after all possible aliases. */
    {
        uint16_t popped_data_segment = pop_word(memory, bus, &state);
#if DISPLAY_PAGES_MUTATION == 4
        (void)popped_data_segment; /* Still perform the actual word read. */
        state.data_segment = input->data_segment;
#else
        state.data_segment = popped_data_segment;
#endif
    }
    return make_result(&state, CS_DisplayPageCopyReturn,
                       LMN_DISPLAY_PAGES_READY);
}

LmnDisplayPagesResult lmn_clear_full_drawing_page_core(uint8_t *memory,
    const LmnDisplayPagesState *input, const LmnRasterBus *bus) {
    LmnDisplayPagesState state = *input;
    LmnVgaClearResult cleared;

#if DISPLAY_PAGES_MUTATION == 5
    state.output_cursor = input->output_cursor;
#else
    state.output_cursor = 0u;
#endif
#if DISPLAY_PAGES_MUTATION == 6
    state.count = (uint16_t)(PAGE_BYTES - 1u);
#else
    state.count = PAGE_BYTES;
#endif

    if (!bus || !bus->read_byte || !bus->write_byte || !bus->out_word)
        return make_result(&state, CS_ClearVgaBytes,
                           LMN_DISPLAY_PAGES_MISSING_CLEAR_BUS);

    /* The child core owns the original setup, VGA bus traffic and REP STOSB. */
    cleared = lmn_clear_vga_bytes_core(memory, state.stack_segment,
        state.stack_offset, state.output_cursor, state.count, state.flags, bus);
    state.value = cleared.value;
    state.count = cleared.count;
    state.output_cursor = cleared.output_cursor;
    state.extra_segment = cleared.output_segment;
    state.stack_offset = cleared.stack_offset;
    state.flags = cleared.flags;
    state.argument = cleared.port;

    /* Leave the shared clear tail's outer RET to the adapter. */
    return make_result(&state, CS_ClearVgaReturn, LMN_DISPLAY_PAGES_READY);
}

static LmnDisplayPagesState state_from_registers(const LmnRegs *registers) {
    LmnDisplayPagesState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnDisplayPagesState *state) {
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

static void apply_result_and_return(uint8_t *memory, LmnRegs *registers,
                                   const LmnDisplayPagesResult *result,
                                   const LmnRasterBus *bus) {
    LmnDisplayPagesState state = result->state;
    apply_state(registers, &state);
    registers->ip = result->continuation;
    if (result->status != LMN_DISPLAY_PAGES_READY)
        return;

    registers->ip = pop_word(memory, bus, &state);
    registers->sp = state.stack_offset;
}

void lmn_copy_drawing_page_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus) {
    LmnDisplayPagesState input = state_from_registers(registers);
    LmnDisplayPagesResult result = lmn_copy_drawing_page_core(
        memory, &input, bus);
    apply_result_and_return(memory, registers, &result, bus);
}

void lmn_clear_full_drawing_page_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus) {
    LmnDisplayPagesState input = state_from_registers(registers);
    LmnDisplayPagesResult result = lmn_clear_full_drawing_page_core(
        memory, &input, bus);
    apply_result_and_return(memory, registers, &result, bus);
}
