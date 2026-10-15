#include "text_glyph.h"
#include "lemmings_sym.h"

#ifndef TEXT_GLYPH_MUTATION
#define TEXT_GLYPH_MUTATION 0
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

static uint16_t szp8(uint8_t value) {
    return (uint16_t)((even_parity(value) ? 0x04u : 0u) |
                      (value == 0 ? 0x40u : 0u) |
                      (value & 0x80u ? 0x80u : 0u));
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    /* AF is undefined for XOR; use the cleared representative. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | szp8(value));
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

static uint16_t sub8_flags(uint16_t flags, uint8_t left, uint8_t right,
                           uint8_t result) {
    uint16_t changed = szp8(result);
    if (left < right) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if (((left ^ right) & (left ^ result)) & 0x80u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static uint16_t shift_left_flags(uint16_t flags, uint16_t original,
                                 uint16_t result, unsigned count) {
    uint16_t changed = szp16(result);
    if ((original >> (16u - count)) & 1u) changed |= 0x01u;
    /* For this count-four shift, OF and AF are undefined; both use zero. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static LmnTextGlyphResult make_result(const LmnTextGlyphState *state,
    uint16_t code_segment, uint16_t continuation,
    enum LmnTextGlyphStatus status) {
    LmnTextGlyphResult result = {
        *state, code_segment, continuation, status
    };
    return result;
}

LmnTextGlyphResult lmn_prepare_text_glyph_core(uint8_t *memory,
    uint16_t code_segment, const LmnTextGlyphState *input,
    const LmnRasterBus *bus) {
    LmnTextGlyphState state = *input;
    uint8_t al = (uint8_t)state.value;
    uint8_t top_cell = (uint8_t)(state.count >> 8);
    uint8_t left_cell = (uint8_t)state.count;
    uint16_t ax, bx, si, di, before, graphics_segment;
    uint16_t flags = state.flags;

    /* 4D78 CMP AL,20. The space branch leaves every other field untouched. */
    flags = sub8_flags(flags, al, 0x20u, (uint8_t)(al - 0x20u));
    state.flags = flags;
    if (al == 0x20u)
        return make_result(&state, code_segment, CS_TextGlyphReturn,
                           LMN_TEXT_GLYPH_READY);

    /* 4D7C..4D92 builds 96*glyph while retaining each ADD's flags. */
    al = (uint8_t)(al - 0x21u);
    flags = sub8_flags(flags, (uint8_t)state.value, 0x21u, al);
    state.value = (uint16_t)((state.value & 0xff00u) | al);
    flags = logic8_flags(flags, 0); /* XOR AH,AH */
    ax = al;
    for (unsigned doubled = 0; doubled != 5; ++doubled) {
        before = ax;
        ax = (uint16_t)(ax << 1);
        flags = add16_flags(flags, before, before, ax);
    }
    si = ax; /* MOV SI,AX */
    before = ax;
    ax = (uint16_t)(ax << 1);
    flags = add16_flags(flags, before, before, ax);
#if TEXT_GLYPH_MUTATION != 1
    before = si;
    si = (uint16_t)(si + ax);
    flags = add16_flags(flags, before, ax, si);
#endif
    before = si;
    si = (uint16_t)(si + 0x5bc0u);
    flags = add16_flags(flags, before, 0x5bc0u, si);
    di = si; /* MOV DI,SI */
    before = di;
    di = (uint16_t)(di + 0x0040u);
    flags = add16_flags(flags, before, 0x0040u, di);

    /* Read and publish the relocated UI graphics segment through live DS. */
    graphics_segment = read_word(memory, state.data_segment,
        SEG09A9_UiGraphicsBufferSegment, flags, bus);
#if TEXT_GLYPH_MUTATION != 2
    before = graphics_segment;
    graphics_segment = (uint16_t)(graphics_segment + 0x1000u);
    flags = add16_flags(flags, before, 0x1000u, graphics_segment);
#endif
    write_word(memory, state.data_segment,
        SEG09A9_GraphicsResourceSegment, graphics_segment, flags, bus);

    /* MOV BL,CH / XOR BH,BH; CH remains live for the later CX setup. */
    bx = top_cell;
    flags = logic8_flags(flags, 0); /* XOR BH,BH */
    ax = left_cell;
    flags = logic8_flags(flags, 0); /* MOV AL,CL / XOR AH,AH */
    before = bx;
    bx = (uint16_t)(bx << 4);
    flags = shift_left_flags(flags, before, bx, 4);
    before = ax;
    ax = (uint16_t)(ax << 4);
    flags = shift_left_flags(flags, before, ax, 4);

    state.value = ax;
    state.base_value = bx;
    state.count = 0x0310u; /* MOV CL,10; MOV CH,3 */
    state.argument = 0x0010u;
    state.source_cursor = si;
    state.output_cursor = di;
    state.flags = flags;

    /* 4DBA PUSH BP writes the live value to SS and leaves SP wrapped at16b. */
    push_word(memory, state.stack_segment, &state.stack_offset,
              state.frame_cursor, flags, bus);
    return make_result(&state, code_segment, CS_TextGlyphBitmapCall,
                       LMN_TEXT_GLYPH_PREPARED);
}

LmnTextGlyphResult lmn_draw_text_glyph_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnTextGlyphState *input, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnTextGlyphResult result = lmn_prepare_text_glyph_core(
        memory, code_segment, input, bus);
    uint16_t stack_offset, returned_ip, returned_cs;
    LmnDrawingRenderResult drawing;

    if (result.status != LMN_TEXT_GLYPH_PREPARED)
        return result;

    /* The far CALL pushes CS, then its following IP at the top of SS:SP. */
    stack_offset = result.state.stack_offset;
    push_word(memory, result.state.stack_segment, &stack_offset,
              code_segment, result.state.flags, bus);
    push_word(memory, result.state.stack_segment, &stack_offset,
              CS_TextGlyphAfterBitmap, result.state.flags, bus);

    {
        LmnPlanarBitmapCall call = {
            result.state.data_segment, game_data_segment,
            result.state.stack_segment, stack_offset,
            result.state.value, result.state.base_value,
            result.state.count, result.state.argument,
            result.state.source_cursor, result.state.output_cursor,
            result.state.frame_cursor, result.state.extra_segment,
            result.state.flags
        };
        drawing = lmn_draw_planar_bitmap_core(memory, &call, bus, ports);
    }

    /* Every logical register and both flowing data segments come from the
       renderer's returned state; SS remains the caller's live stack segment. */
    result.state.value = drawing.plan.state.work_value;
    result.state.base_value = drawing.plan.state.second_source_cursor;
    result.state.count = drawing.plan.state.packed_counts;
    result.state.argument = drawing.plan.state.width_state;
    result.state.source_cursor = drawing.plan.state.source_cursor;
    result.state.output_cursor = drawing.plan.state.destination_cursor;
    result.state.frame_cursor = drawing.plan.state.control;
    result.state.stack_offset = drawing.plan.state.stack_offset;
    result.state.flags = drawing.plan.state.flags;
    result.state.data_segment = drawing.source_segment;
    result.state.extra_segment = drawing.output_segment;

    if (!drawing.body_returned) {
        result.continuation = drawing.plan.state.continuation;
        result.status = LMN_TEXT_GLYPH_RENDERER_STOP;
        return result;
    }

    stack_offset = result.state.stack_offset;
    returned_ip = pop_word(memory, result.state.stack_segment, &stack_offset,
                           result.state.flags, bus);
    returned_cs = pop_word(memory, result.state.stack_segment, &stack_offset,
                           result.state.flags, bus);
    result.state.stack_offset = stack_offset;
    result.continuation = returned_ip;
    result.code_segment = returned_cs;

#if TEXT_GLYPH_MUTATION != 4
    if (returned_ip != CS_TextGlyphAfterBitmap ||
        returned_cs != code_segment) {
        result.status = LMN_TEXT_GLYPH_CHANGED_RETURN;
        return result;
    }
#else
    /* Mutant: discard a changed RETF target and continue through POP BP. */
    result.code_segment = code_segment;
#endif

#if TEXT_GLYPH_MUTATION == 3
    result.state.frame_cursor = input->frame_cursor;
    result.state.stack_offset = (uint16_t)(result.state.stack_offset + 2u);
#else
    result.state.frame_cursor = pop_word(memory, result.state.stack_segment,
        &result.state.stack_offset, result.state.flags, bus);
#endif
    result.continuation = CS_TextGlyphReturn;
    result.status = LMN_TEXT_GLYPH_READY;
    return result;
}

static LmnTextGlyphState state_from_registers(const LmnRegs *registers) {
    LmnTextGlyphState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnTextGlyphState *state) {
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

void lmn_draw_text_glyph_adapter(uint8_t *memory, LmnRegs *registers,
    uint16_t game_data_segment, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnTextGlyphState input = state_from_registers(registers);
    LmnTextGlyphResult result = lmn_draw_text_glyph_core(memory,
        registers->cs, game_data_segment, &input, bus, ports);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status == LMN_TEXT_GLYPH_READY) {
        registers->ip = pop_word(memory, registers->ss, &registers->sp,
                                 registers->flags, bus);
    }
}
