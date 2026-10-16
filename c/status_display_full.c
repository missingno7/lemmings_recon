#include "status_display_full.h"

#include "lemmings_sym.h"
#include "minimap_status.h"

#ifndef STATUS_DISPLAY_FULL_MUTATION
#define STATUS_DISPLAY_FULL_MUTATION 0
#endif

enum { MEMORY_MASK = 0xfffffu };

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

#if STATUS_DISPLAY_FULL_MUTATION != 1
static LmnMinimapStatusCall minimap_call_from_full(
    const LmnStatusDisplayFullCall *call) {
    LmnMinimapStatusCall out;
    out.value=call->value;out.map_cursor=call->map_cursor;
    out.count=call->count;out.auxiliary_value=call->auxiliary_value;
    out.record_cursor=call->record_cursor;out.object_cursor=call->object_cursor;
    out.candidate_y=call->candidate_y;out.code_segment=call->code_segment;
    out.data_segment=call->data_segment;out.extra_segment=call->extra_segment;
    out.stack_segment=call->stack_segment;out.stack_offset=call->stack_offset;
    out.flags=call->flags;
    return out;
}

static LmnStatusDisplayCall suffix_call_from_minimap(
    const LmnMinimapStatusResult *prefix) {
    LmnStatusDisplayCall out;
    out.value=prefix->value;out.map_cursor=prefix->map_cursor;
    out.count=prefix->count;out.auxiliary_value=prefix->auxiliary_value;
    out.record_cursor=prefix->record_cursor;
    out.object_cursor=prefix->object_cursor;out.candidate_y=prefix->candidate_y;
    out.code_segment=prefix->code_segment;out.data_segment=prefix->data_segment;
    out.extra_segment=prefix->extra_segment;
    out.stack_segment=prefix->stack_segment;out.stack_offset=prefix->stack_offset;
    out.flags=prefix->flags;
    return out;
}

#if STATUS_DISPLAY_FULL_MUTATION != 3
static LmnStatusDisplayFullResult boundary_result(
    const LmnMinimapStatusResult *prefix) {
    LmnStatusDisplayFullResult out;
    out.value=prefix->value;out.map_cursor=prefix->map_cursor;
    out.count=prefix->count;out.auxiliary_value=prefix->auxiliary_value;
    out.record_cursor=prefix->record_cursor;
    out.object_cursor=prefix->object_cursor;out.candidate_y=prefix->candidate_y;
    out.code_segment=prefix->code_segment;out.data_segment=prefix->data_segment;
    out.extra_segment=prefix->extra_segment;
    out.stack_segment=prefix->stack_segment;out.stack_offset=prefix->stack_offset;
    out.flags=prefix->flags;out.continuation=prefix->continuation;
    out.status=LMN_STATUS_DISPLAY_MINIMAP_BOUNDARY;
    out.child_entry=CS_UpdateStatusDisplay;
    out.child_status=prefix->status;
    return out;
}
#endif
#endif

LmnStatusDisplayFullResult lmn_update_status_display_full_core(uint8_t *memory,
    const LmnStatusDisplayFullCall *call,const LmnRasterBus *bus) {
#if STATUS_DISPLAY_FULL_MUTATION != 1
    LmnMinimapStatusResult prefix;
#endif
    LmnStatusDisplayCall suffix_call;

#if STATUS_DISPLAY_FULL_MUTATION == 1
    /* Mutant skips the 3AC8..3ACE prefix and enters at its fallthrough. */
    suffix_call.value=call->value;suffix_call.map_cursor=call->map_cursor;
    suffix_call.count=call->count;
    suffix_call.auxiliary_value=call->auxiliary_value;
    suffix_call.record_cursor=call->record_cursor;
    suffix_call.object_cursor=call->object_cursor;
    suffix_call.candidate_y=call->candidate_y;
    suffix_call.code_segment=call->code_segment;
    suffix_call.data_segment=call->data_segment;
    suffix_call.extra_segment=call->extra_segment;
    suffix_call.stack_segment=call->stack_segment;
    suffix_call.stack_offset=call->stack_offset;suffix_call.flags=call->flags;
    return lmn_update_status_display_suffix_core(memory,&suffix_call,bus);
#else
    {
        LmnMinimapStatusCall prefix_call=minimap_call_from_full(call);
        prefix=lmn_update_minimap_status_core(memory,&prefix_call,bus);
    }
#if STATUS_DISPLAY_FULL_MUTATION != 3
    if(prefix.status!=LMN_MINIMAP_STATUS_READY) {
        /* The prefix may stop at a child target even when IP is 3ACE. */
        return boundary_result(&prefix);
    }
#endif
    suffix_call=suffix_call_from_minimap(&prefix);
#if STATUS_DISPLAY_FULL_MUTATION == 2
    /* Mutant discards DS returned by the completed minimap prefix. */
    suffix_call.data_segment=call->data_segment;
#endif
    return lmn_update_status_display_suffix_core(memory,&suffix_call,bus);
#endif
}

static void apply_result(LmnRegs *r,const LmnStatusDisplayFullResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;r->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t ss,uint16_t sp,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];
        high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_update_status_display_full_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnStatusDisplayFullCall call;
    LmnStatusDisplayFullResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_update_status_display_full_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_STATUS_DISPLAY_FULL_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}
