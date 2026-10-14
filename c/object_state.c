#include "object_state.h"
#include "object_graphics.h"
#include "steel_cells.h"
#include "object_cells.h"
#include "object_coordinates.h"
#include "lemmings_sym.h"
#ifndef STATE_MUTATION
#define STATE_MUTATION 0
#endif

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint16_t word(const uint8_t *memory,uint16_t segment,uint16_t offset) {
    uint32_t p=physical(segment,offset);
    return (uint16_t)(memory[p]|((uint16_t)memory[(p+1u)&0xfffffu]<<8));
}
static void push(uint8_t *memory,uint16_t segment,uint16_t *offset,uint16_t value) {
    uint32_t p;*offset=(uint16_t)(*offset-2u);p=physical(segment,*offset);
    memory[p]=(uint8_t)value;memory[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static unsigned returned(const uint8_t *memory,uint16_t stack,LmnObjectStateResult *s,uint16_t expected) {
    uint16_t actual=word(memory,stack,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
#if STATE_MUTATION == 3
    actual=expected;
#endif
    s->continuation=actual;s->changed_return=(uint16_t)(actual!=expected);
    return s->changed_return;
}
LmnObjectStateResult lmn_prepare_level_object_state_core(uint8_t *memory,const LmnObjectStateCall *call) {
    LmnObjectStateResult s={0};
    LmnObjectGraphicsResult graphics;
    LmnSteelInteractionCellsCall steel_call;
    LmnSteelInteractionCellsResult steel;
    LmnObjectCellsCall cells_call;
    LmnObjectCellsResult cells;
    LmnObjectCoordinatesCall coordinates_call;
    LmnObjectCoordinatesResult coordinates;
    s.stack_offset=call->stack_offset;s.base_cursor=call->base_cursor;s.flags=call->flags;
    push(memory,call->stack_segment,&s.stack_offset,CS_ObjectStateAfterGraphicsCopy);
    graphics=lmn_copy_object_graphics_core(memory,call->data_segment,call->stack_segment,
        s.stack_offset,call->product_high,s.flags);
    s.value=graphics.value;s.cell_cursor=graphics.definition_cursor;s.remaining_records=graphics.count;
    s.dimension_state=graphics.product_high;s.source_cursor=graphics.source_cursor;
    s.definition_cursor=graphics.output_cursor;s.extra_segment=graphics.extra_segment;
    s.stack_offset=graphics.stack_offset;s.flags=graphics.flags;
    if(returned(memory,call->stack_segment,&s,CS_ObjectStateAfterGraphicsCopy))return s;

    push(memory,call->stack_segment,&s.stack_offset,CS_ObjectStateAfterSteelCells);
    steel_call=(LmnSteelInteractionCellsCall){call->data_segment,call->stack_segment,s.stack_offset,s.flags};
    steel=lmn_write_steel_interaction_cells_core(memory,&steel_call);
    s.value=steel.value;s.cell_cursor=steel.cell_cursor;s.remaining_records=steel.records_remaining;
    s.dimension_state=steel.dimensions;s.definition_cursor=steel.definition_cursor;
    s.stack_offset=steel.stack_offset;s.flags=steel.flags;
    if(returned(memory,call->stack_segment,&s,CS_ObjectStateAfterSteelCells))return s;

    push(memory,call->stack_segment,&s.stack_offset,CS_ObjectStateAfterObjectCells);
    cells_call=(LmnObjectCellsCall){call->data_segment,call->stack_segment,s.stack_offset,s.cell_cursor,s.flags};
#if STATE_MUTATION == 1
    cells_call.stack_segment=call->data_segment;
#endif
    cells=lmn_write_object_interaction_cells_core(memory,&cells_call);
    s.value=cells.value;s.cell_cursor=cells.cell_cursor;s.remaining_records=cells.remaining_records;
    s.dimension_state=cells.dimension_state;s.source_cursor=cells.template_cursor;
    s.definition_cursor=cells.definition_cursor;s.base_cursor=cells.object_ordinal;
    s.stack_offset=cells.stack_offset;s.flags=cells.flags;
    if(returned(memory,call->stack_segment,&s,CS_ObjectStateAfterObjectCells))return s;

    push(memory,call->stack_segment,&s.stack_offset,CS_ObjectStateAfterCoordinates);
    coordinates_call=(LmnObjectCoordinatesCall){call->data_segment,s.flags};
    coordinates=lmn_collect_type_one_object_coordinates_core(memory,&coordinates_call);
    s.value=coordinates.value;s.cell_cursor=coordinates.output_cursor;s.remaining_records=coordinates.count;
    s.source_cursor=coordinates.definition_cursor;s.base_cursor=coordinates.selected_count;s.flags=coordinates.flags;
#if STATE_MUTATION == 2
    s.base_cursor=16;
#endif
    (void)returned(memory,call->stack_segment,&s,CS_ObjectStateAfterCoordinates);
    return s;
}
void lmn_prepare_level_object_state_adapter(uint8_t *memory,LmnRegs *r) {
    LmnObjectStateCall call={r->ds,r->ss,r->sp,r->dx,r->bp,r->flags};
    LmnObjectStateResult s=lmn_prepare_level_object_state_core(memory,&call);
    r->ax=s.value;r->bx=s.cell_cursor;r->cx=s.remaining_records;r->dx=s.dimension_state;
    r->si=s.source_cursor;r->di=s.definition_cursor;r->bp=s.base_cursor;r->es=s.extra_segment;
    r->sp=s.stack_offset;r->flags=s.flags;r->ip=s.continuation;
}
