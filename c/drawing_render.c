#include "drawing_render.h"
#include "aligned_opaque.h"
#include "aligned_masked.h"
#include "aligned_mask_effects.h"
#include "aligned_protected.h"
#include "shifted_mask_effects.h"
#include "shifted_opaque.h"
#include "shifted_masked.h"
#include "shifted_protected.h"
#include "shifted_read_mask.h"
#include "lemmings_sym.h"
#ifndef RENDER_MUTATION
#define RENDER_MUTATION 0
#endif
static LmnDrawingRenderResult draw_prepared(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus,
    unsigned scope, const LmnRasterBytePorts *ports) {
    LmnDrawingRenderResult result = {
        lmn_prepare_planar_drawing_plan_core(memory, &call->inputs, bus),
        call->inputs.data_segment, call->output_segment, 0};
    LmnDrawingSourceResult *state = &result.plan.state;
    LmnAlignedOpaqueCall body_call;
    LmnAlignedOpaqueResult drawn;
    unsigned supported = state->continuation == CS_PlanarAlignedOpaqueBody ||
        (scope >= 1 && state->continuation == CS_PlanarAlignedMaskedDefaultBody) ||
        (scope >= 2 && (state->continuation == CS_PlanarAlignedMasked8000Body ||
         state->continuation == CS_PlanarAlignedMasked20Body ||
         state->continuation == CS_PlanarAlignedMasked40Body ||
         (state->continuation == CS_PlanarAlignedMasked4000Body && ports))) ||
        (scope >= 3 && (state->continuation == CS_PlanarShiftedMasked20Body ||
                       state->continuation == CS_PlanarShiftedMasked40Body)) ||
        (scope >= 4 && (state->continuation == CS_PlanarShiftedOpaqueBody ||
         state->continuation == CS_PlanarShiftedMaskedDefaultBody ||
         state->continuation == CS_PlanarShiftedMasked8000Body ||
         state->continuation == CS_PlanarShiftedMasked4000Body));
    if (result.plan.changed_return || !supported)
        return result;
#if RENDER_MUTATION == 1
    return result;
#endif
#if RENDER_MUTATION == 2
    state->flags = (uint16_t)(state->flags & ~0x400u);
#endif
    if (state->continuation == CS_PlanarShiftedOpaqueBody) {
        LmnShiftedOpaqueCall shifted_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->destination_cursor, state->flags};
        LmnShiftedOpaqueResult shifted = lmn_draw_shifted_opaque_core(memory, &shifted_call, bus);
        state->work_value = shifted.work_value; state->packed_counts = shifted.packed_counts;
        state->width_state = shifted.port; state->source_cursor = shifted.source_cursor;
        state->second_source_cursor = shifted.mask_cursor;
        state->destination_cursor = shifted.destination_cursor;
        state->control = shifted.plane_counter; state->stack_offset = shifted.stack_offset;
        state->flags = shifted.flags; state->continuation = CS_PlanarShiftedOpaqueFarReturn;
        result.source_segment = shifted.source_segment; result.output_segment = shifted.output_segment;
        result.body_returned = 1; return result;
    }
    if (state->continuation == CS_PlanarShiftedMasked8000Body) {
        LmnShiftedProtectedCall shifted_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->destination_cursor, state->flags};
        LmnShiftedProtectedResult shifted = lmn_draw_shifted_protected_core(memory, &shifted_call, bus);
        state->work_value = shifted.work_value; state->packed_counts = shifted.packed_counts;
        state->width_state = shifted.port; state->source_cursor = shifted.source_cursor;
        state->destination_cursor = shifted.destination_cursor;
        state->control = shifted.plane_counter; state->stack_offset = shifted.stack_offset;
        state->flags = shifted.flags; state->continuation = CS_PlanarShiftedProtectedFarReturn;
        result.source_segment = shifted.source_segment; result.output_segment = shifted.output_segment;
        result.body_returned = 1; return result;
    }
    if (state->continuation == CS_PlanarShiftedMaskedDefaultBody) {
        LmnShiftedMaskedCall shifted_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->second_source_cursor, state->destination_cursor, state->flags};
        LmnShiftedMaskedResult shifted = lmn_draw_shifted_masked_core(memory, &shifted_call, bus);
        state->work_value = shifted.work_value; state->packed_counts = shifted.packed_counts;
        state->width_state = shifted.port; state->source_cursor = shifted.source_cursor;
        state->second_source_cursor = shifted.mask_cursor;
        state->destination_cursor = shifted.destination_cursor;
        state->control = shifted.plane_counter; state->stack_offset = shifted.stack_offset;
        state->flags = shifted.flags; state->continuation = CS_PlanarShiftedMaskedFarReturn;
        result.source_segment = shifted.source_segment; result.output_segment = shifted.output_segment;
        result.body_returned = 1; return result;
    }
    if (state->continuation == CS_PlanarShiftedMasked4000Body) {
        LmnShiftedReadMaskCall shifted_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->second_source_cursor, state->destination_cursor, state->flags};
        LmnShiftedReadMaskResult shifted = lmn_draw_shifted_read_mask_core(memory, &shifted_call, bus);
        state->work_value = shifted.work_value; state->packed_counts = shifted.packed_counts;
        state->width_state = shifted.port; state->source_cursor = shifted.source_cursor;
        state->second_source_cursor = shifted.mask_cursor;
        state->destination_cursor = shifted.destination_cursor;
        state->control = shifted.plane_counter; state->stack_offset = shifted.stack_offset;
        state->flags = shifted.flags; state->continuation = CS_PlanarShiftedReadMaskFarReturn;
        result.source_segment = shifted.source_segment; result.output_segment = shifted.output_segment;
        result.body_returned = 1; return result;
    }
    if (state->continuation == CS_PlanarShiftedMasked20Body ||
        state->continuation == CS_PlanarShiftedMasked40Body) {
        unsigned forty = state->continuation == CS_PlanarShiftedMasked40Body;
        LmnShiftedMaskEffectCall effect_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->second_source_cursor, state->destination_cursor,
            state->control, state->flags};
        LmnShiftedMaskEffectResult effect = forty ?
            lmn_draw_shifted_mask40_core(memory, &effect_call, bus) :
            lmn_draw_shifted_mask20_core(memory, &effect_call, bus);
        state->work_value = effect.work_value; state->packed_counts = effect.packed_counts;
        state->width_state = effect.port; state->source_cursor = effect.source_cursor;
        state->second_source_cursor = effect.mask_cursor;
        state->destination_cursor = effect.destination_cursor;
        state->control = effect.control; state->stack_offset = effect.stack_offset;
        state->flags = effect.flags;
        state->continuation = forty ? CS_PlanarShiftedMask40FarReturn : CS_PlanarShiftedMask20FarReturn;
        result.source_segment = effect.source_segment; result.output_segment = effect.output_segment;
        result.body_returned = 1;
        return result;
    }
    if (state->continuation == CS_PlanarAlignedMasked20Body ||
        state->continuation == CS_PlanarAlignedMasked40Body) {
        unsigned forty = state->continuation == CS_PlanarAlignedMasked40Body;
        LmnAlignedMaskEffectCall effect_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->second_source_cursor, state->destination_cursor,
            state->control, state->flags};
        LmnAlignedMaskEffectResult effect = forty ?
            lmn_draw_aligned_mask40_core(memory, &effect_call, bus) :
            lmn_draw_aligned_mask20_core(memory, &effect_call, bus);
        state->work_value = effect.work_value; state->packed_counts = effect.packed_counts;
        state->width_state = effect.port; state->source_cursor = effect.source_cursor;
        state->second_source_cursor = effect.mask_cursor;
        state->destination_cursor = effect.destination_cursor;
        state->control = effect.control; state->stack_offset = effect.stack_offset;
        state->flags = effect.flags;
        state->continuation = forty ? CS_PlanarAlignedMask40FarReturn : CS_PlanarAlignedMask20FarReturn;
        result.source_segment = effect.source_segment; result.output_segment = effect.output_segment;
        result.body_returned = 1;
        return result;
    }
    if (state->continuation == CS_PlanarAlignedMasked8000Body) {
        LmnAlignedProtectedCall protected_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->destination_cursor, state->flags};
        LmnAlignedProtectedResult protected_result =
            lmn_draw_aligned_protected_core(memory, &protected_call, bus);
        state->work_value = protected_result.work_value;
        state->packed_counts = protected_result.packed_counts;
        state->width_state = protected_result.port; state->source_cursor = protected_result.source_cursor;
        state->destination_cursor = protected_result.destination_cursor;
        state->control = protected_result.plane_counter; state->stack_offset = protected_result.stack_offset;
        state->flags = protected_result.flags; state->continuation = CS_PlanarAlignedProtectedFarReturn;
        result.source_segment = protected_result.source_segment;
        result.output_segment = protected_result.output_segment; result.body_returned = 1;
        return result;
    }
    if (state->continuation == CS_PlanarAlignedMasked4000Body) {
        LmnAlignedReadMaskCall read_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->second_source_cursor, state->destination_cursor, state->flags};
        LmnAlignedReadMaskResult read_result =
            lmn_draw_aligned_read_mask_core(memory, &read_call, bus, ports);
        state->work_value = read_result.work_value; state->packed_counts = read_result.packed_counts;
        state->width_state = read_result.port; state->source_cursor = read_result.source_cursor;
        state->second_source_cursor = read_result.mask_cursor;
        state->destination_cursor = read_result.destination_cursor;
        state->control = read_result.plane_counter; state->stack_offset = read_result.stack_offset;
        state->flags = read_result.flags; state->continuation = CS_PlanarAlignedReadMaskFarReturn;
        result.source_segment = read_result.source_segment; result.output_segment = read_result.output_segment;
        result.body_returned = 1;
        return result;
    }
    if (state->continuation == CS_PlanarAlignedMaskedDefaultBody) {
        LmnAlignedMaskedCall masked_call = {call->inputs.data_segment,
            call->game_data_segment, call->inputs.stack_segment, state->stack_offset,
            state->packed_counts, state->width_state, state->source_cursor,
            state->second_source_cursor, state->destination_cursor, state->flags};
        LmnAlignedMaskedResult masked =
            lmn_draw_aligned_masked_core(memory, &masked_call, bus);
        state->work_value = masked.work_value;
        state->packed_counts = masked.packed_counts;
        state->width_state = masked.port;
        state->source_cursor = masked.source_cursor;
        state->second_source_cursor = masked.mask_cursor;
        state->destination_cursor = masked.destination_cursor;
        state->control = masked.plane_counter;
        state->stack_offset = masked.stack_offset;
        state->flags = masked.flags;
        state->continuation = CS_PlanarAlignedMaskedFarReturn;
        result.source_segment = masked.source_segment;
        result.output_segment = masked.output_segment;
        result.body_returned = 1;
        return result;
    }
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
LmnDrawingRenderResult lmn_draw_prepared_aligned_opaque_core(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus) {
    return draw_prepared(memory, call, bus, 0, 0);
}
LmnDrawingRenderResult lmn_draw_prepared_planar_core(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus) {
    return draw_prepared(memory, call, bus, 1, 0);
}
LmnDrawingRenderResult lmn_draw_prepared_aligned_core(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    return draw_prepared(memory, call, bus, 2, ports);
}
LmnDrawingRenderResult lmn_draw_prepared_planar_effects_core(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    return draw_prepared(memory, call, bus, 3, ports);
}
LmnDrawingRenderResult lmn_draw_prepared_bitmap_core(
    uint8_t *memory, const LmnDrawingRenderCall *call, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    return draw_prepared(memory, call, bus, 4, ports);
}
static void entry_push(uint8_t *memory, uint16_t ss, uint16_t *sp,
    uint16_t value, uint16_t flags, const LmnRasterBus *bus) {
    uint32_t p;
    *sp = (uint16_t)(*sp - 2u);
    p = (((uint32_t)ss << 4) + *sp) & 0xfffffu;
    if (bus && bus->write_byte) {
        bus->write_byte(bus->context, memory, p, (uint8_t)value, flags);
        bus->write_byte(bus->context, memory, (p + 1u) & 0xfffffu, (uint8_t)(value >> 8), flags);
    } else {
        memory[p] = (uint8_t)value;
        memory[(p + 1u) & 0xfffffu] = (uint8_t)(value >> 8);
    }
}
static uint16_t entry_shift_flags(uint16_t flags, uint16_t value) {
    uint16_t pitch = (uint16_t)(value >> 3);
    unsigned parity = 0;
    for (unsigned bit = 0; bit < 8; ++bit) parity ^= (pitch >> bit) & 1u;
    /* Three SHR count-one instructions: last CF is input bit2, last OF zero.
       AF is undefined; all other status and control bits follow the original. */
    return (uint16_t)((flags & ~0x8c5u) | ((value >> 2) & 1u) |
        (parity ? 0u : 4u) | (pitch ? 0u : 0x40u));
}
LmnDrawingRenderResult lmn_draw_planar_bitmap_core(uint8_t *memory,
    const LmnPlanarBitmapCall *call, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    uint16_t sp = call->stack_offset;
    LmnDrawingRenderCall prepared;
    LmnDrawingRenderResult result;
    entry_push(memory, call->stack_segment, &sp, call->left, call->flags, bus);
    entry_push(memory, call->stack_segment, &sp, call->width, call->flags, bus);
    entry_push(memory, call->stack_segment, &sp, call->packed_height, call->flags, bus);
    prepared = (LmnDrawingRenderCall){{call->data_segment, call->stack_segment, sp,
        (uint16_t)(call->width >> 3), call->top, call->packed_height, call->width,
        call->source_cursor, call->destination_cursor, call->control,
        entry_shift_flags(call->flags, call->width)}, call->game_data_segment,
        call->output_segment};
    result = draw_prepared(memory, &prepared, bus, 4, ports);
    if (!result.plan.changed_return &&
        result.plan.state.continuation == CS_PlanarDrawingAbortReturn)
        result.body_returned = 1; /* The no-draw branch also has a live RETF. */
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
static void apply_boundary_result(uint8_t *memory, LmnRegs *regs,
    LmnDrawingRenderResult result, const LmnRasterBus *bus) {
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
    (void)memory;
    (void)bus;
#endif
}
void lmn_draw_prepared_aligned_opaque_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment, const LmnRasterBus *bus) {
    LmnDrawingRenderCall call = {{regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags}, game_data_segment, regs->es};
    apply_boundary_result(memory, regs,
        lmn_draw_prepared_aligned_opaque_core(memory, &call, bus), bus);
}
void lmn_draw_prepared_planar_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment, const LmnRasterBus *bus) {
    LmnDrawingRenderCall call = {{regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags}, game_data_segment, regs->es};
    apply_boundary_result(memory, regs,
        lmn_draw_prepared_planar_core(memory, &call, bus), bus);
}
void lmn_draw_prepared_aligned_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnDrawingRenderCall call = {{regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags}, game_data_segment, regs->es};
    apply_boundary_result(memory, regs,
        lmn_draw_prepared_aligned_core(memory, &call, bus, ports), bus);
}
void lmn_draw_prepared_planar_effects_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnDrawingRenderCall call = {{regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags}, game_data_segment, regs->es};
    apply_boundary_result(memory, regs,
        lmn_draw_prepared_planar_effects_core(memory, &call, bus, ports), bus);
}
void lmn_draw_prepared_bitmap_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnDrawingRenderCall call = {{regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags}, game_data_segment, regs->es};
    apply_boundary_result(memory, regs,
        lmn_draw_prepared_bitmap_core(memory, &call, bus, ports), bus);
}
void lmn_draw_planar_bitmap_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnPlanarBitmapCall call = {regs->ds, game_data_segment, regs->ss, regs->sp,
        regs->ax, regs->bx, regs->cx, regs->dx, regs->si, regs->di, regs->bp,
        regs->es, regs->flags};
    apply_boundary_result(memory, regs,
        lmn_draw_planar_bitmap_core(memory, &call, bus, ports), bus);
}
