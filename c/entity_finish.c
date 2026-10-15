#include "entity_finish.h"
#include "lemmings_sym.h"

#ifndef ENTITY_FINISH_MUTATION
#define ENTITY_FINISH_MUTATION 0
#endif

enum {
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,SF=0x0080u,
    OF=0x0800u,ARITH=0x08d5u
};

typedef struct FinishState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} FinishState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(FinishState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(FinishState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(FinishState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(FinishState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* A word's second byte is physical+1, not a second 16-bit offset access. */
static uint16_t read16(FinishState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(FinishState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum,out=(uint16_t)(flags&~ARITH);
    unsigned parity=0,n;
    if(sum>0xffffu) out|=CF;
    if((left^right^value)&AF) out|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0) out|=OF;
    if(!value) out|=ZF;
    if(value&0x8000u) out|=SF;
    for(n=0;n<8;++n) parity^=(value>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t value=(uint16_t)(left-right),out=(uint16_t)(flags&~ARITH);
    unsigned parity=0,n;
    if(left<right) out|=CF;
    if((left^right^value)&AF) out|=AF;
    if(((left^right)&(left^value)&0x8000u)!=0) out|=OF;
    if(!value) out|=ZF;
    if(value&0x8000u) out|=SF;
    for(n=0;n<8;++n) parity^=(value>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned parity=0,n;
    if(!value) out|=ZF;
    if(value&0x8000u) out|=SF;
    for(n=0;n<8;++n) parity^=(value>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t negate8_flags(uint16_t flags,uint8_t value,uint8_t result) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned parity=0,n;
    if(value) out|=CF;
    if(value&0x0fu) out|=AF;
    if(value==0x80u) out|=OF;
    if(!result) out|=ZF;
    if(result&0x80u) out|=SF;
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static LmnEntityFinishResult result(const FinishState *s) {
    LmnEntityFinishResult out;
    out.value=s->value;
    out.map_cursor=s->map_cursor;
    out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;
    out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;
    out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;
    out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;
    out.stack_offset=s->stack_offset;
    out.flags=s->flags;
    out.continuation=s->continuation;
    out.status=s->status;
    return out;
}

static uint16_t interaction_status(uint16_t status) {
    switch(status) {
    case LMN_ENTITY_INTERACTION_RET_READY:
        return LMN_ENTITY_FINISH_RETURNED;
    case LMN_ENTITY_INTERACTION_UNBOUND_VECTOR:
        return LMN_ENTITY_FINISH_UNBOUND_VECTOR;
    case LMN_ENTITY_INTERACTION_UNTRANSLATED_SOUND:
        return LMN_ENTITY_FINISH_UNTRANSLATED_SOUND;
    case LMN_ENTITY_INTERACTION_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_INTERACTION_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN;
    default:
        return LMN_ENTITY_FINISH_INVALID_ENTRY;
    }
}

static void copy_interaction_result(FinishState *s,
                                    const LmnEntityInteractionsResult *child) {
    s->value=child->value;
    s->map_cursor=child->map_cursor;
    s->count=child->count;
    s->auxiliary_value=child->auxiliary_value;
    s->record_cursor=child->record_cursor;
    s->object_cursor=child->object_cursor;
    s->code_segment=child->code_segment;
    s->data_segment=child->data_segment;
    s->stack_segment=child->stack_segment;
    s->stack_offset=child->stack_offset;
    s->flags=child->flags;
    s->continuation=child->continuation;
}

static LmnEntityFinishResult run_interaction_call(FinishState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityInteractionsCall call;
    LmnEntityInteractionsResult child;
#if ENTITY_FINISH_MUTATION != 6
    uint16_t caller_cs=s->code_segment;
#endif
#if ENTITY_FINISH_MUTATION == 1
    uint16_t cached_return=0;
#endif

#if ENTITY_FINISH_MUTATION == 2
    /* Mutant omits CALL's live SS push and its SP decrement. */
#else
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,
            CS_EntityIterationTail,s->flags);
#endif
#if ENTITY_FINISH_MUTATION == 1
    /* Stale prefetch: read the newly pushed word before the child can alter it. */
    cached_return=read16(s,s->stack_segment,s->stack_offset);
#endif

    call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;
    call.object_cursor=s->object_cursor;
    call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;
    call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    child=lmn_entity_interactions_core(s->memory,&call,pc_binding,
                                       sound_binding,s->bus);
    copy_interaction_result(s,&child);
    s->status=interaction_status(child.status);
    if(child.status!=LMN_ENTITY_INTERACTION_RET_READY)
        return result(s);

    /* CALL's return is an actual live word, consumed only after the child. */
#if ENTITY_FINISH_MUTATION == 1
    {
        uint16_t actual_sp=s->stack_offset;
        s->stack_offset=(uint16_t)(actual_sp+2u);
        s->continuation=cached_return;
    }
#else
    {
        uint16_t actual_return=read16(s,s->stack_segment,s->stack_offset);
        s->stack_offset=(uint16_t)(s->stack_offset+2u);
#if ENTITY_FINISH_MUTATION == 6
        (void)actual_return;
        s->continuation=CS_EntityIterationTail;
#else
        s->continuation=actual_return;
#endif
    }
#endif

#if ENTITY_FINISH_MUTATION == 6
    s->status=LMN_ENTITY_FINISH_RETURNED;
#else
    s->status=(s->code_segment==caller_cs &&
               s->continuation==CS_EntityIterationTail)
        ? LMN_ENTITY_FINISH_RETURNED
        : LMN_ENTITY_FINISH_CHANGED_CALL_RETURN;
#endif
    return result(s);
}

static LmnEntityFinishResult mark_inactive(FinishState *s) {
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x26u),
           0xffu,s->flags);
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_FINISH_RETURNED;
    return result(s);
}

#if ENTITY_FINISH_MUTATION != 3
static int signed_ge(uint16_t flags) {
    return ((flags&SF)!=0)==((flags&OF)!=0);
}
#endif

#if ENTITY_FINISH_MUTATION != 4
static int signed_le(uint16_t flags) {
    return (flags&ZF)!=0 || (((flags&SF)!=0)!=((flags&OF)!=0));
}
#endif

static LmnEntityFinishResult store_probe_height(FinishState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    write16(s,s->data_segment,(uint16_t)(s->record_cursor+2u),
            s->candidate_y,s->flags); /* MOV does not change flags. */
    s->flags=sub16_flags(s->flags,s->candidate_y,0x00b4u); /* CMP BP,B4 */
#if ENTITY_FINISH_MUTATION == 3
    if(s->candidate_y>=0x00b4u)
#else
    if(signed_ge(s->flags))
#endif
        return mark_inactive(s);
    return run_interaction_call(s,pc_binding,sound_binding);
}

static LmnEntityFinishResult resolve_step_height(FinishState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t displacement=(uint16_t)(s->record_cursor+6u);
    uint16_t delta;
    uint16_t old=s->candidate_y;
    write16(s,s->data_segment,(uint16_t)(s->record_cursor+2u),
            s->candidate_y,s->flags);
    delta=read16(s,s->data_segment,displacement);
    s->candidate_y=(uint16_t)(old+delta);
    s->flags=add16_flags(s->flags,old,delta); /* ADD BP,[SI+6] */
    s->flags=sub16_flags(s->flags,s->candidate_y,0x000au); /* CMP BP,0A */
#if ENTITY_FINISH_MUTATION == 4
    if(s->candidate_y<=0x000au)
#else
    if(signed_le(s->flags))
#endif
    {
        uint8_t velocity,negated;
        uint16_t entry_flags,updated_flags;
        s->candidate_y=0x0009u;
        old=s->candidate_y;
        delta=read16(s,s->data_segment,displacement);
        s->candidate_y=(uint16_t)(old-delta);
        s->flags=sub16_flags(s->flags,old,delta); /* SUB BP,[SI+6] */
        write16(s,s->data_segment,(uint16_t)(s->record_cursor+2u),
                s->candidate_y,s->flags);

        displacement=(uint16_t)(s->record_cursor+0x27u);
        entry_flags=s->flags;
        velocity=read8(s,s->data_segment,displacement);
        negated=(uint8_t)(0u-velocity);
        updated_flags=negate8_flags(entry_flags,velocity,negated);
#if ENTITY_FINISH_MUTATION == 5
        write8(s,s->data_segment,displacement,negated,updated_flags);
#else
        write8(s,s->data_segment,displacement,negated,entry_flags);
#endif
        s->flags=updated_flags;

        displacement=(uint16_t)(s->record_cursor+8u);
        entry_flags=s->flags;
        old=read16(s,s->data_segment,displacement);
        delta=(uint16_t)(old&0xfff7u);
#if ENTITY_FINISH_MUTATION == 5
        updated_flags=logic16_flags(entry_flags,delta);
        write16(s,s->data_segment,displacement,delta,updated_flags);
#else
        write16(s,s->data_segment,displacement,delta,entry_flags);
        updated_flags=logic16_flags(entry_flags,delta);
#endif
        s->flags=updated_flags;
    }
    return run_interaction_call(s,pc_binding,sound_binding);
}

LmnEntityFinishResult lmn_entity_finish_core(uint8_t *memory,
    const LmnEntityFinishCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    FinishState s;
    s.memory=memory;
    s.bus=bus;
    s.value=call->value;
    s.map_cursor=call->map_cursor;
    s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;
    s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;
    s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;
    s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;
    s.stack_offset=call->stack_offset;
    s.flags=call->flags;
    s.continuation=0;
    s.status=LMN_ENTITY_FINISH_INVALID_ENTRY;

    switch(call->entry) {
    case LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8:
        return run_interaction_call(&s,pc_binding,sound_binding);
    case LMN_ENTITY_FINISH_STORE_HEIGHT_20D6:
        return store_probe_height(&s,pc_binding,sound_binding);
    case LMN_ENTITY_FINISH_MARK_INACTIVE_20E2:
        return mark_inactive(&s);
    case LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148:
        return resolve_step_height(&s,pc_binding,sound_binding);
    default:
        return result(&s);
    }
}

uint16_t lmn_entity_finish_adapter(uint8_t *memory,LmnRegs *registers,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=entry;
    call.value=registers->ax;
    call.map_cursor=registers->bx;
    call.count=registers->cx;
    call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;
    call.object_cursor=registers->di;
    call.candidate_y=registers->bp;
    call.code_segment=registers->cs;
    call.data_segment=registers->ds;
    call.extra_segment=registers->es;
    call.stack_segment=registers->ss;
    call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=lmn_entity_finish_core(memory,&call,pc_binding,sound_binding,bus);
    registers->ax=out.value;
    registers->bx=out.map_cursor;
    registers->cx=out.count;
    registers->dx=out.auxiliary_value;
    registers->si=out.record_cursor;
    registers->di=out.object_cursor;
    registers->bp=out.candidate_y;
    registers->cs=out.code_segment;
    registers->ds=out.data_segment;
    registers->es=out.extra_segment;
    registers->ss=out.stack_segment;
    registers->sp=out.stack_offset;
    registers->flags=out.flags;
    registers->ip=out.continuation;
    return out.status;
}
