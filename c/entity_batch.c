#include "entity_batch.h"
#include "lemmings_sym.h"

#ifndef ENTITY_BATCH_MUTATION
#define ENTITY_BATCH_MUTATION 0
#endif

typedef struct BatchState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} BatchState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(BatchState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(BatchState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

/* A near CALL/RET word advances physically and wraps at 20 bits. */
static uint16_t read_word(BatchState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(BatchState *s,uint16_t segment,uint16_t offset,
                       uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static void push_near_return(BatchState *s,uint16_t return_offset) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write_word(s,s->stack_segment,s->stack_offset,return_offset);
}

static uint16_t pop_near_return(BatchState *s) {
    uint16_t target=read_word(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return target;
}

static LmnEntityBatchResult result_of(const BatchState *s) {
    LmnEntityBatchResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;
    out.count=s->count;out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;
    out.status=s->status;out.child_entry=s->child_entry;
    out.child_status=s->child_status;
    return out;
}

static void update_from_create(BatchState *s,
                               const LmnEntityCreateResult *r) {
    s->value=r->value;s->map_cursor=r->map_cursor;
    s->count=r->count;s->auxiliary_value=r->auxiliary_value;
    s->record_cursor=r->record_cursor;s->object_cursor=r->object_cursor;
    s->candidate_y=r->candidate_y;s->code_segment=r->code_segment;
    s->data_segment=r->data_segment;s->extra_segment=r->extra_segment;
    s->stack_segment=r->stack_segment;s->stack_offset=r->stack_offset;
    s->flags=r->flags;
}

#if ENTITY_BATCH_MUTATION != 1
static void update_from_update(BatchState *s,
                               const LmnEntityUpdateResult *r) {
    s->value=r->value;s->map_cursor=r->map_cursor;
    s->count=r->count;s->auxiliary_value=r->auxiliary_value;
    s->record_cursor=r->record_cursor;s->object_cursor=r->object_cursor;
    s->candidate_y=r->candidate_y;s->code_segment=r->code_segment;
    s->data_segment=r->data_segment;s->extra_segment=r->extra_segment;
    s->stack_segment=r->stack_segment;s->stack_offset=r->stack_offset;
    s->flags=r->flags;s->continuation=r->continuation;
}
#endif

static LmnEntityCreateCall create_call(const BatchState *s) {
    LmnEntityCreateCall call;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    return call;
}

#if ENTITY_BATCH_MUTATION != 1
static LmnEntityUpdateCall update_call(const BatchState *s,
    const LmnEntityBatchCall *entry) {
    LmnEntityUpdateCall call;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
#if ENTITY_BATCH_MUTATION == 2
    /* Keep the actual live CALL frame, but pass stale entry registers. */
    call.value=entry->value;call.map_cursor=entry->map_cursor;
    call.count=entry->count;call.auxiliary_value=entry->auxiliary_value;
    call.record_cursor=entry->record_cursor;
    call.object_cursor=entry->object_cursor;
    call.candidate_y=entry->candidate_y;
    call.data_segment=entry->data_segment;
    call.extra_segment=entry->extra_segment;call.flags=entry->flags;
#else
    (void)entry;
#endif
    return call;
}
#endif

LmnEntityBatchResult lmn_entity_batch_core(uint8_t *memory,
    const LmnEntityBatchCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    BatchState s;
    LmnEntityCreateCall create_input;
    LmnEntityCreateResult create_result;
    uint16_t actual_return,create_return;
#if ENTITY_BATCH_MUTATION == 3
    uint16_t cached_create_return;
#endif

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;
    s.count=call->count;s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_CreateAndAdvanceEntityRecords;
    s.status=LMN_ENTITY_BATCH_READY;s.child_entry=0u;
    s.child_status=LMN_ENTITY_BATCH_NO_CHILD_STATUS;
#if ENTITY_BATCH_MUTATION == 1
    (void)pc_binding;
    (void)sound_binding;
#endif

    /* CALL 30A6 at 01B0 pushes the actual 01B3 continuation. */
    push_near_return(&s,CS_EntityBatchAfterCreateCall);
#if ENTITY_BATCH_MUTATION == 3
    cached_create_return=read_word(&s,s.stack_segment,s.stack_offset);
#endif
    create_input=create_call(&s);
    create_result=lmn_create_entity_record_core(memory,&create_input,bus);
    update_from_create(&s,&create_result);
    actual_return=pop_near_return(&s);
#if ENTITY_BATCH_MUTATION == 3
    create_return=cached_create_return;
#else
    create_return=actual_return;
#endif
    if(create_return!=CS_EntityBatchAfterCreateCall) {
        s.continuation=actual_return;
        s.status=LMN_ENTITY_BATCH_CHANGED_CALL_RETURN;
        s.child_entry=CS_CreateEntityRecordIfDue;
        s.child_status=create_result.status;
        return result_of(&s);
    }
    s.continuation=CS_EntityBatchAfterCreateCall;

#if ENTITY_BATCH_MUTATION == 1
    /* Mutant omits the actual second CALL and its state transition. */
    s.continuation=CS_EntityBatchNextCaller;
    s.status=LMN_ENTITY_BATCH_READY;
    return result_of(&s);
#else
    {
        LmnEntityUpdateCall update_input;
        LmnEntityUpdateResult update_result;
        uint16_t update_return;

        /* CALL 1F19 at 01B3 pushes the actual 01B6 continuation. */
        push_near_return(&s,CS_EntityBatchNextCaller);
        update_input=update_call(&s,call);
        update_result=lmn_entity_update_core(memory,&update_input,pc_binding,
            sound_binding,bus);
        update_from_update(&s,&update_result);
        s.child_entry=update_result.child_entry;
        s.child_status=update_result.child_status;

        if(update_result.status!=LMN_ENTITY_UPDATE_RETURN_PENDING) {
#if ENTITY_BATCH_MUTATION == 4
            s.continuation=CS_EntityBatchNextCaller;
            s.status=LMN_ENTITY_BATCH_READY;
            s.child_entry=0u;
            s.child_status=LMN_ENTITY_BATCH_NO_CHILD_STATUS;
#else
            s.status=LMN_ENTITY_BATCH_CHILD_BOUNDARY;
#endif
            return result_of(&s);
        }

        update_return=pop_near_return(&s);
        if(update_return!=CS_EntityBatchNextCaller) {
            s.continuation=update_return;
            s.status=LMN_ENTITY_BATCH_CHANGED_CALL_RETURN;
            s.child_entry=CS_AdvanceEntityRecords;
            s.child_status=update_result.status;
            return result_of(&s);
        }
        s.continuation=CS_EntityBatchNextCaller;
        s.status=LMN_ENTITY_BATCH_READY;
        s.child_entry=0u;
        s.child_status=LMN_ENTITY_BATCH_NO_CHILD_STATUS;
#if ENTITY_BATCH_MUTATION == 5
        s.count=call->count;
        s.data_segment=call->data_segment;
#endif
        return result_of(&s);
    }
#endif
}

uint16_t lmn_entity_batch_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityBatchCall call;
    LmnEntityBatchResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_batch_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}
