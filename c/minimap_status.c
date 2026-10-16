#include "minimap_status.h"
#include "minimap_column.h"
#include "minimap_viewport.h"
#include "lemmings_sym.h"

#ifndef MINIMAP_STATUS_MUTATION
#define MINIMAP_STATUS_MUTATION 0
#endif

typedef struct MinimapStatusState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} MinimapStatusState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(MinimapStatusState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(MinimapStatusState *s,uint32_t address,
                           uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint16_t read_word(MinimapStatusState *s,uint16_t segment,
                          uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(MinimapStatusState *s,uint16_t segment,
                       uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t pop_word(MinimapStatusState *s) {
    uint16_t value=read_word(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static void push_word(MinimapStatusState *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write_word(s,s->stack_segment,s->stack_offset,value);
}

static LmnMinimapStatusResult result_of(const MinimapStatusState *s) {
    LmnMinimapStatusResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    out.child_entry=s->child_entry;out.child_status=s->child_status;
    return out;
}

#if MINIMAP_STATUS_MUTATION != 1
static void take_column(MinimapStatusState *s,
                        const LmnMinimapColumnResult *child) {
    s->value=child->value;s->map_cursor=child->target_cursor;
    s->count=child->count;s->auxiliary_value=child->port_or_population;
    s->record_cursor=child->source_cursor;
    s->object_cursor=child->output_cursor;
    s->data_segment=child->data_segment;s->extra_segment=child->extra_segment;
    s->stack_offset=child->stack_offset;s->flags=child->flags;
    s->continuation=child->continuation;
}
#endif

static void take_viewport(MinimapStatusState *s,
                          const LmnMinimapViewportResult *child) {
    s->value=child->value;s->map_cursor=child->map_cursor;
    s->count=child->count;s->auxiliary_value=child->auxiliary_value;
    s->record_cursor=child->record_cursor;
    s->object_cursor=child->object_cursor;
    s->candidate_y=child->candidate_y;
    s->code_segment=child->code_segment;s->data_segment=child->data_segment;
    s->extra_segment=child->extra_segment;
    s->stack_segment=child->stack_segment;s->stack_offset=child->stack_offset;
    s->flags=child->flags;s->continuation=child->continuation;
}

LmnMinimapStatusResult lmn_update_minimap_status_core(uint8_t *memory,
    const LmnMinimapStatusCall *call,const LmnRasterBus *bus) {
    MinimapStatusState s;
    uint16_t actual_return,expected_code_segment;
#if MINIMAP_STATUS_MUTATION == 2
    uint16_t entry_data_segment;
#endif
#if MINIMAP_STATUS_MUTATION == 3
    uint16_t prefetched_column_return;
#endif

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;
    s.count=call->count;s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_UpdateStatusDisplay;
    s.status=LMN_MINIMAP_STATUS_READY;s.child_entry=0u;
    s.child_status=LMN_MINIMAP_STATUS_NO_CHILD_STATUS;
#if MINIMAP_STATUS_MUTATION == 2
    entry_data_segment=s.data_segment;
#endif

#if MINIMAP_STATUS_MUTATION == 1
    /* Skip UpdateMinimapColumn while retaining the real prefix CALL/RET. */
    expected_code_segment=s.code_segment;
    push_word(&s,CS_StatusDisplayAfterMinimapColumn);
    actual_return=pop_word(&s);
    if(actual_return!=CS_StatusDisplayAfterMinimapColumn ||
       s.code_segment!=expected_code_segment) {
#if MINIMAP_STATUS_MUTATION == 5
        s.continuation=CS_StatusDisplayAfterMinimapColumn;
#else
        s.continuation=actual_return;
        s.status=LMN_MINIMAP_STATUS_CHANGED_CALL_RETURN;
        s.child_entry=CS_UpdateMinimapColumn;s.child_status=0u;
        return result_of(&s);
#endif
    }
    s.continuation=CS_StatusDisplayAfterMinimapColumn;
#else
    /* CALL 796F at 3AC8 pushes the actual 3ACB continuation. */
    expected_code_segment=s.code_segment;
    push_word(&s,CS_StatusDisplayAfterMinimapColumn);
#if MINIMAP_STATUS_MUTATION == 3
    prefetched_column_return=read_word(&s,s.stack_segment,s.stack_offset);
#endif
    {
        LmnMinimapColumnCall child_call;
        LmnMinimapColumnResult child_result;
        child_call.code_segment=s.code_segment;
        child_call.data_segment=s.data_segment;
        child_call.stack_segment=s.stack_segment;
        child_call.stack_offset=s.stack_offset;child_call.flags=s.flags;
        child_result=lmn_update_minimap_column_core(memory,&child_call,bus);
        take_column(&s,&child_result);
#if MINIMAP_STATUS_MUTATION == 2
        /* Mutant discards the child-returned DS before the second CALL. */
        s.data_segment=entry_data_segment;
#endif
        if(child_result.changed_return) {
#if MINIMAP_STATUS_MUTATION == 4
            /* Mutant ignores the inner row's changed RET target. */
#else
            s.status=LMN_MINIMAP_STATUS_CHILD_BOUNDARY;
            s.child_entry=CS_UpdateMinimapColumn;s.child_status=1u;
            s.continuation=child_result.continuation;
            return result_of(&s);
#endif
        }
    }
    actual_return=pop_word(&s);
#if MINIMAP_STATUS_MUTATION == 3
    actual_return=prefetched_column_return;
#endif
    if(actual_return!=CS_StatusDisplayAfterMinimapColumn ||
       s.code_segment!=expected_code_segment) {
#if MINIMAP_STATUS_MUTATION == 5
        s.continuation=CS_StatusDisplayAfterMinimapColumn;
#else
        s.continuation=actual_return;
        s.status=LMN_MINIMAP_STATUS_CHANGED_CALL_RETURN;
        s.child_entry=CS_UpdateMinimapColumn;s.child_status=0u;
        return result_of(&s);
#endif
    }
    s.continuation=CS_StatusDisplayAfterMinimapColumn;
#endif

    /* CALL 7A5A at 3ACB pushes the actual 3ACE continuation. */
    expected_code_segment=s.code_segment;
    push_word(&s,CS_StatusDisplayAfterMinimapViewport);
    {
        LmnMinimapViewportCall child_call;
        LmnMinimapViewportResult child_result;
        child_call.value=s.value;child_call.map_cursor=s.map_cursor;
        child_call.count=s.count;child_call.auxiliary_value=s.auxiliary_value;
        child_call.record_cursor=s.record_cursor;
        child_call.object_cursor=s.object_cursor;
        child_call.candidate_y=s.candidate_y;
        child_call.code_segment=s.code_segment;
        child_call.data_segment=s.data_segment;
        child_call.extra_segment=s.extra_segment;
        child_call.stack_segment=s.stack_segment;
        child_call.stack_offset=s.stack_offset;child_call.flags=s.flags;
#if MINIMAP_STATUS_MUTATION == 2
        /* Also expose a stale DS input at the next translated child. */
        child_call.data_segment=entry_data_segment;
#endif
        child_result=lmn_draw_minimap_viewport_core(memory,&child_call,bus);
        take_viewport(&s,&child_result);
        if(child_result.status!=LMN_MINIMAP_VIEWPORT_READY) {
            s.status=LMN_MINIMAP_STATUS_CHILD_BOUNDARY;
            s.child_entry=CS_DrawMinimapViewport;
            s.child_status=child_result.status;
            s.continuation=child_result.continuation;
            return result_of(&s);
        }
        s.continuation=CS_StatusDisplayAfterMinimapViewport;
    }
    actual_return=pop_word(&s);
    if(actual_return!=CS_StatusDisplayAfterMinimapViewport ||
       s.code_segment!=expected_code_segment) {
#if MINIMAP_STATUS_MUTATION == 5
        s.continuation=CS_StatusDisplayAfterMinimapViewport;
#else
        s.continuation=actual_return;
        s.status=LMN_MINIMAP_STATUS_CHANGED_CALL_RETURN;
        s.child_entry=CS_DrawMinimapViewport;s.child_status=0u;
        return result_of(&s);
#endif
    }
    s.continuation=CS_StatusDisplayAfterMinimapViewport;
    s.status=LMN_MINIMAP_STATUS_READY;
    s.child_entry=0u;s.child_status=LMN_MINIMAP_STATUS_NO_CHILD_STATUS;
    return result_of(&s);
}

uint16_t lmn_update_minimap_status_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnMinimapStatusCall call;
    LmnMinimapStatusResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_update_minimap_status_core(memory,&call,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;r->es=out.extra_segment;
    r->ss=out.stack_segment;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=out.continuation;
    return out.status;
}
