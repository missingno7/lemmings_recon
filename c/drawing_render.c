#include "drawing_render.h"
#include "aligned_opaque.h"
#include "lemmings_sym.h"
#ifndef RENDER_MUTATION
#define RENDER_MUTATION 0
#endif
LmnDrawingRenderResult lmn_draw_prepared_aligned_opaque_core(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus) {
    LmnDrawingRenderResult result = {
        lmn_prepare_planar_drawing_plan_core(memory, &call->inputs, bus),
        call->inputs.data_segment, call->output_segment, 0};
    LmnDrawingSourceResult *state = &result.plan.state;
    LmnAlignedOpaqueCall body_call;
    LmnAlignedOpaqueResult drawn;
    if (result.plan.changed_return || state->continuation != CS_PlanarAlignedOpaqueBody)
        return result;
#if RENDER_MUTATION == 1
    return result;
#endif
#if RENDER_MUTATION == 2
    state->flags = (uint16_t)(state->flags & ~0x400u);
#endif
    body_call = (LmnAlignedOpaqueCall){call->inputs.data_segment,
        call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
        state->packed_counts, state->width_state, state->source_cursor,
        state->destination_cursor, state->flags};
    drawn = lmn_draw_aligned_opaque_core(memory, &body_call, bus);
    state->work_value = drawn.work_value;
    state->packed_counts = drawn.packed_counts;
    state->width_state = drawn.port;
    state->source_cursor = drawn.source_cursor;
    state->destination_cursor = drawn.destination_cursor;
    state->control = drawn.plane_counter;
    state->stack_offset = drawn.stack_offset;
    state->flags = drawn.flags;
    state->continuation = CS_PlanarAlignedOpaqueFarReturn;
    result.source_segment = drawn.source_segment;
    result.output_segment = drawn.output_segment;
    result.body_returned = 1;
    return result;
}
static uint16_t return_word(uint8_t *memory, uint16_t ss, uint16_t offset,
    uint16_t flags, const LmnRasterBus *bus) {
    uint32_t p = (((uint32_t)ss << 4) + offset) & 0xfffffu;
    uint8_t low = bus && bus->read_byte ? bus->read_byte(bus->context, memory, p, flags) : memory[p];
    uint32_t high_address = (p + 1u) & 0xfffffu;
    uint8_t high = bus && bus->read_byte ? bus->read_byte(bus->context, memory, high_address, flags) : memory[high_address];
    return (uint16_t)(low | ((uint16_t)high << 8));
}
void lmn_draw_prepared_aligned_opaque_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment, const LmnRasterBus *bus) {
    LmnDrawingRenderCall call = {{regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags}, game_data_segment, regs->es};
    LmnDrawingRenderResult result = lmn_draw_prepared_aligned_opaque_core(memory, &call, bus);
    LmnDrawingSourceResult *state = &result.plan.state;
    regs->ax = state->work_value; regs->bx = state->second_source_cursor;
    regs->cx = state->packed_counts; regs->dx = state->width_state;
    regs->si = state->source_cursor; regs->di = state->destination_cursor;
    regs->bp = state->control; regs->sp = state->stack_offset;
    regs->ds = result.source_segment; regs->es = result.output_segment;
    regs->flags = state->flags; regs->ip = state->continuation;
#if RENDER_MUTATION != 3
    if (result.body_returned) {
        regs->ip = return_word(memory, regs->ss, regs->sp, regs->flags, bus);
        regs->sp = (uint16_t)(regs->sp + 2u);
        regs->cs = return_word(memory, regs->ss, regs->sp, regs->flags, bus);
        regs->sp = (uint16_t)(regs->sp + 2u);
    }
#else
    (void)return_word;
#endif
}
