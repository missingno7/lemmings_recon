#include "text_stream.h"
#include "lemmings_sym.h"

#ifndef TEXT_STREAM_MUTATION
#define TEXT_STREAM_MUTATION 0
#endif

enum { MEMORY_MASK = 0xfffff, ARITHMETIC_FLAGS = 0x08d5 };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint16_t segment, uint16_t offset,
                         uint16_t flags) {
    uint32_t address = physical(segment, offset);
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static uint8_t read_byte_physical(uint8_t *memory, const LmnRasterBus *bus,
                                  uint32_t address, uint16_t flags) {
    address &= MEMORY_MASK;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_byte_physical(uint8_t *memory, const LmnRasterBus *bus,
                                uint32_t address, uint8_t value,
                                uint16_t flags) {
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
    uint8_t low = read_byte_physical(memory, bus, address, flags);
    uint8_t high = read_byte_physical(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte_physical(memory, bus, address, (uint8_t)value, flags);
    write_byte_physical(memory, bus, address + 1u, (uint8_t)(value >> 8),
                        flags);
}

static void push_word(uint8_t *memory, LmnTextStreamState *state,
                      uint16_t value, const LmnRasterBus *bus) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, state->stack_segment, state->stack_offset, value,
               state->flags, bus);
}

static uint16_t pop_word(uint8_t *memory, LmnTextStreamState *state,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, state->stack_segment,
                               state->stack_offset, state->flags, bus);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static unsigned even_parity(uint8_t value) {
    unsigned parity = 0;
    for (unsigned bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0;
}

static uint16_t szp8(uint8_t value) {
    return (uint16_t)((even_parity(value) ? 0x04u : 0u) |
                      (value == 0 ? 0x40u : 0u) |
                      (value & 0x80u ? 0x80u : 0u));
}

#if TEXT_STREAM_MUTATION == 5
static uint16_t szp16(uint16_t value) {
    return (uint16_t)((even_parity((uint8_t)value) ? 0x04u : 0u) |
                      (value == 0 ? 0x40u : 0u) |
                      (value & 0x8000u ? 0x80u : 0u));
}
#endif

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    /* AF is undefined for AND/XOR; use the cleared representative. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | szp8(value));
}

static uint16_t sub8_flags(uint16_t flags, uint8_t left, uint8_t right,
                           uint8_t result) {
    uint16_t changed = szp8(result);
    if (left < right) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if (((left ^ right) & (left ^ result)) & 0x80u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

#if TEXT_STREAM_MUTATION != 5
static uint16_t inc8_flags(uint16_t flags, uint8_t original,
                           uint8_t result) {
    uint16_t changed = szp8(result);
    if ((original & 0x0fu) == 0x0fu) changed |= 0x10u;
    if (original == 0x7fu) changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | (flags & 0x01u) |
                      changed);
}
#endif

#if TEXT_STREAM_MUTATION == 5
static uint16_t inc16_flags(uint16_t flags, uint16_t original,
                            uint16_t result) {
    uint16_t changed = szp16(result);
    if ((original & 0x0fu) == 0x0fu) changed |= 0x10u;
    if (original == 0x7fffu) changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | (flags & 0x01u) |
                      changed);
}
#endif

static LmnTextStreamResult make_result(const LmnTextStreamState *state,
    uint16_t code_segment, uint16_t continuation,
    enum LmnTextStreamStatus status) {
    LmnTextStreamResult result = {
        *state, code_segment, continuation, status
    };
    return result;
}

LmnTextStreamResult lmn_draw_text_stream_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnTextStreamState *input, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnTextStreamState state = *input;

    for (;;) {
        uint8_t al;

        /* Header column: AND AL,AL; zero reaches the still-live stream RET. */
        al = read_byte(memory, bus, state.data_segment, state.source_cursor,
                       state.flags);
#if TEXT_STREAM_MUTATION == 2
        state.source_cursor = (uint16_t)(state.source_cursor + 1u);
#else
        state.source_cursor = (uint16_t)(state.source_cursor +
            ((state.flags & 0x0400u) ? 0xffffu : 1u));
#endif
        state.value = (uint16_t)((state.value & 0xff00u) | al);
        state.flags = logic8_flags(state.flags, al);
        if (al == 0)
            return make_result(&state, code_segment, CS_TextStreamReturn,
                               LMN_TEXT_STREAM_READY);

        /* MOV CL,AL / DEC CL; CH is preserved while the row is read. */
        state.count = (uint16_t)((state.count & 0xff00u) | al);
        {
            uint8_t cl = (uint8_t)state.count;
            uint8_t result = (uint8_t)(cl - 1u);
            state.count = (uint16_t)((state.count & 0xff00u) | result);
            state.flags = (sub8_flags(state.flags, cl, 1u, result) & (uint16_t)~1u) |
                          (state.flags & 0x0001u);
        }

        /* LODSB / MOV CH,AL. */
        al = read_byte(memory, bus, state.data_segment, state.source_cursor,
                       state.flags);
#if TEXT_STREAM_MUTATION == 2
        state.source_cursor = (uint16_t)(state.source_cursor + 1u);
#else
        state.source_cursor = (uint16_t)(state.source_cursor +
            ((state.flags & 0x0400u) ? 0xffffu : 1u));
#endif
        state.value = (uint16_t)((state.value & 0xff00u) | al);
        state.count = (uint16_t)(((uint16_t)al << 8) | (uint8_t)state.count);

        /* LODSB / AND AL,AL selects BP=2 for style zero, otherwise XOR BP,BP. */
        al = read_byte(memory, bus, state.data_segment, state.source_cursor,
                       state.flags);
#if TEXT_STREAM_MUTATION == 2
        state.source_cursor = (uint16_t)(state.source_cursor + 1u);
#else
        state.source_cursor = (uint16_t)(state.source_cursor +
            ((state.flags & 0x0400u) ? 0xffffu : 1u));
#endif
        state.value = (uint16_t)((state.value & 0xff00u) | al);
        state.flags = logic8_flags(state.flags, al);
        if (al == 0) {
            state.frame_cursor = 2u;
        } else {
            state.frame_cursor = 0;
            state.flags = logic8_flags(state.flags, 0);
        }

        for (;;) {
            uint16_t saved_si;

            /* Character LODSB / CMP AL,0D. */
            al = read_byte(memory, bus, state.data_segment,
                           state.source_cursor, state.flags);
#if TEXT_STREAM_MUTATION == 2
            state.source_cursor = (uint16_t)(state.source_cursor + 1u);
#else
            state.source_cursor = (uint16_t)(state.source_cursor +
                ((state.flags & 0x0400u) ? 0xffffu : 1u));
#endif
            state.value = (uint16_t)((state.value & 0xff00u) | al);
            state.flags = sub8_flags(state.flags, al, 0x0du,
                                     (uint8_t)(al - 0x0du));
            if (al == 0x0du)
                break;

#if TEXT_STREAM_MUTATION == 1
            if (al == 0)
                return make_result(&state, code_segment,
                    CS_TextStreamReturn, LMN_TEXT_STREAM_READY);
#endif

            /* PUSH CX/BX/SI, then the CALL's live near return at 4D70. */
            push_word(memory, &state, state.count, bus);
            push_word(memory, &state, state.base_value, bus);
            saved_si = state.source_cursor;
            push_word(memory, &state, saved_si, bus);
            push_word(memory, &state, CS_TextStreamAfterGlyph, bus);

            {
                LmnTextGlyphResult glyph = lmn_draw_text_glyph_core(
                    memory, code_segment, game_data_segment, &state, bus,
                    ports);
                state = glyph.state;
                code_segment = glyph.code_segment;
                if (glyph.status != LMN_TEXT_GLYPH_READY)
                    return make_result(&state, code_segment,
                        glyph.continuation, LMN_TEXT_STREAM_CHILD_STOP);
            }

            /* Execute the glyph's actual near RET, including a live alias. */
            {
                uint16_t returned = pop_word(memory, &state, bus);
#if TEXT_STREAM_MUTATION != 4
                if (returned != CS_TextStreamAfterGlyph)
                    return make_result(&state, code_segment, returned,
                        LMN_TEXT_STREAM_CHANGED_RETURN);
#else
                (void)returned;
#endif
            }

            /* Original POPs read all saved words from the live stack. */
#if TEXT_STREAM_MUTATION == 3
            (void)pop_word(memory, &state, bus);
            state.source_cursor = saved_si;
#else
            state.source_cursor = pop_word(memory, &state, bus);
#endif
            state.base_value = pop_word(memory, &state, bus);
            state.count = pop_word(memory, &state, bus);

            /* INC CL is byte-sized and leaves CH and CF unchanged. */
#if TEXT_STREAM_MUTATION == 5
            {
                uint16_t original = state.count;
                state.count = (uint16_t)(state.count + 1u);
                state.flags = inc16_flags(state.flags, original, state.count);
            }
#else
            {
                uint8_t original = (uint8_t)state.count;
                uint8_t result = (uint8_t)(original + 1u);
                state.count = (uint16_t)((state.count & 0xff00u) | result);
                state.flags = inc8_flags(state.flags, original, result);
            }
#endif
        }
    }
}

static LmnTextStreamState state_from_registers(const LmnRegs *registers) {
    LmnTextStreamState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnTextStreamState *state) {
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

void lmn_draw_text_stream_adapter(uint8_t *memory, LmnRegs *registers,
    uint16_t game_data_segment, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnTextStreamState input = state_from_registers(registers);
    LmnTextStreamResult result = lmn_draw_text_stream_core(memory,
        registers->cs, game_data_segment, &input, bus, ports);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status == LMN_TEXT_STREAM_READY) {
        registers->ip = pop_word(memory, &result.state, bus);
        registers->sp = result.state.stack_offset;
    }
}
