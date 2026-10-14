#include "drawing_plan.h"
#include "drawing_dispatch.h"
#include "lemmings_sym.h"
#ifndef PLAN_MUTATION
#define PLAN_MUTATION 0
#endif
LmnDrawingPlanResult lmn_prepare_planar_drawing_plan_core(
    uint8_t *memory, const LmnDrawingInputsCall *call, const LmnRasterBus *bus) {
    LmnDrawingInputsResult prepared =
        lmn_prepare_planar_drawing_inputs_core(memory, call, bus);
    LmnDrawingPlanResult result = {{prepared.left, prepared.top,
        prepared.packed_height, prepared.width, prepared.source_cursor,
        prepared.destination_cursor, prepared.control, prepared.stack_offset,
        prepared.flags, prepared.continuation}, prepared.changed_return};
    LmnDrawingDispatchCall dispatch_call;
    LmnDrawingDispatchResult selected;
    LmnDrawingSourceCall source_call;
    if (prepared.changed_return || prepared.continuation != CS_PlanarInputsReady)
        return result;
#if PLAN_MUTATION == 2
    prepared.packed_height = call->packed_height;
#endif
    dispatch_call = (LmnDrawingDispatchCall){call->data_segment,
        call->stack_segment, prepared.stack_offset, prepared.left, prepared.top,
        prepared.packed_height, prepared.width, prepared.source_cursor,
        prepared.destination_cursor, prepared.control, prepared.flags};
    selected = lmn_prepare_planar_drawing_dispatch_core(memory, &dispatch_call, bus);
    result.state = (LmnDrawingSourceResult){selected.work_value,
        selected.second_source_cursor, selected.packed_counts, selected.width_state,
        selected.source_cursor, selected.destination_cursor, selected.control,
        selected.stack_offset, selected.flags, selected.continuation};
#if PLAN_MUTATION == 1
    return result;
#endif
    if (selected.continuation != CS_PrepareShiftedMaskedPlanarRows &&
        selected.continuation != CS_PrepareShiftedOpaquePlanarRows &&
        selected.continuation != CS_PrepareAlignedMaskedPlanarRows &&
        selected.continuation != CS_PrepareAlignedOpaquePlanarRows)
        return result;
#if PLAN_MUTATION == 3
    selected.continuation = (selected.continuation == CS_PrepareShiftedMaskedPlanarRows ||
        selected.continuation == CS_PrepareShiftedOpaquePlanarRows) ?
        ((call->control & 2u) ? CS_PrepareShiftedMaskedPlanarRows : CS_PrepareShiftedOpaquePlanarRows) :
        ((call->control & 2u) ? CS_PrepareAlignedMaskedPlanarRows : CS_PrepareAlignedOpaquePlanarRows);
#endif
    source_call = (LmnDrawingSourceCall){call->data_segment, call->stack_segment,
        selected.stack_offset, selected.work_value, selected.second_source_cursor,
        selected.packed_counts, selected.width_state, selected.source_cursor,
        selected.destination_cursor, selected.control, selected.flags, selected.continuation};
    result.state = lmn_prepare_planar_source_rows_core(memory, &source_call, bus);
    return result;
}
void lmn_prepare_planar_drawing_plan_adapter(
    uint8_t *memory, LmnRegs *regs, const LmnRasterBus *bus) {
    LmnDrawingInputsCall call = {regs->ds, regs->ss, regs->sp, regs->ax, regs->bx,
        regs->cx, regs->dx, regs->si, regs->di, regs->bp, regs->flags};
    LmnDrawingPlanResult result = lmn_prepare_planar_drawing_plan_core(memory, &call, bus);
    regs->ax = result.state.work_value;
    regs->bx = result.state.second_source_cursor;
    regs->cx = result.state.packed_counts;
    regs->dx = result.state.width_state;
    regs->si = result.state.source_cursor;
    regs->di = result.state.destination_cursor;
    regs->bp = result.state.control;
    regs->sp = result.state.stack_offset;
    regs->flags = result.state.flags;
    regs->ip = result.state.continuation;
}
