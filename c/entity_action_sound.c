#include "entity_action_sound.h"
#include "lemmings_sym.h"

#ifndef ENTITY_ACTION_SOUND_MUTATION
#define ENTITY_ACTION_SOUND_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct ActionSoundState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} ActionSoundState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(ActionSoundState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=szp8(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t test8_flags(uint16_t flags,uint8_t result) {
    /* TEST clears CF/OF; AF is undefined and represented as zero. */
    return (uint16_t)((flags&~ARITH)|szp8(result));
}

static uint8_t read8(ActionSoundState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static uint16_t read16_at(uint8_t *memory,const LmnRasterBus *bus,
                          uint16_t segment,uint16_t offset,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&0xfffffu,flags);
    } else {
        low=memory[address&0xfffffu];
        high=memory[(address+1u)&0xfffffu];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

static LmnEntityActionSoundResult result_of(const ActionSoundState *s) {
    LmnEntityActionSoundResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void regs_from_state(const ActionSoundState *s,LmnRegs *r,
                            uint16_t ip) {
    r->ax=s->value;r->bx=s->map_cursor;r->cx=s->count;
    r->dx=s->auxiliary_value;r->si=s->record_cursor;
    r->di=s->object_cursor;r->bp=s->candidate_y;r->sp=s->stack_offset;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->ip=ip;r->flags=s->flags;
}

static void state_from_regs(ActionSoundState *s,const LmnRegs *r) {
    s->value=r->ax;s->map_cursor=r->bx;s->count=r->cx;
    s->auxiliary_value=r->dx;s->record_cursor=r->si;
    s->object_cursor=r->di;s->candidate_y=r->bp;
    s->stack_offset=r->sp;s->code_segment=r->cs;
    s->data_segment=r->ds;s->extra_segment=r->es;
    s->stack_segment=r->ss;s->flags=r->flags;s->continuation=r->ip;
}

static uint16_t map_pc_status(uint16_t status) {
    switch(status) {
    case LMN_PC_INTERRUPT_RETURNED:return LMN_ENTITY_ACTION_SOUND_READY;
    case LMN_PC_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_ACTION_SOUND_UNBOUND_VECTOR;
    case LMN_PC_INTERRUPT_UNTRANSLATED_CHILD:
        return LMN_ENTITY_ACTION_SOUND_UNTRANSLATED_CHILD;
    case LMN_PC_INTERRUPT_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_ACTION_SOUND_CHANGED_DRIVER_CHILD;
    case LMN_PC_INTERRUPT_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN;
    default:return LMN_ENTITY_ACTION_SOUND_INVALID_CHILD;
    }
}

static uint16_t invoke_pc_feedback(ActionSoundState *s,
    const LmnPcSpeakerBinding *binding) {
    LmnPcSpeakerInterruptCall call;
    LmnPcSpeakerInterruptResult out;
#if ENTITY_ACTION_SOUND_MUTATION == 6
    uint16_t entry_ds=s->data_segment,entry_si=s->record_cursor;
    uint16_t entry_ss=s->stack_segment,entry_sp=s->stack_offset;
#endif
    regs_from_state(s,&call.registers,
                    (uint16_t)(CS_EntityActionAfterPcFeedback-2u));
    call.return_offset=CS_EntityActionAfterPcFeedback;
    out=lmn_pc_speaker_interrupt60_core(s->memory,&call,binding,s->bus);
    state_from_regs(s,&out.registers);
    s->status=map_pc_status(out.status);
#if ENTITY_ACTION_SOUND_MUTATION == 6
    if(out.status==LMN_PC_INTERRUPT_RETURNED) {
        s->data_segment=entry_ds;s->record_cursor=entry_si;
        s->stack_segment=entry_ss;s->stack_offset=entry_sp;
    }
#endif
#if ENTITY_ACTION_SOUND_MUTATION == 7
    if(s->status==LMN_ENTITY_ACTION_SOUND_CHANGED_DRIVER_CHILD ||
       s->status==LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN) {
        s->status=LMN_ENTITY_ACTION_SOUND_READY;
        s->continuation=CS_EntityActionAfterPcFeedback;
    }
#else
    if(out.status==LMN_PC_INTERRUPT_RETURNED)
        s->continuation=CS_EntityActionAfterPcFeedback;
#endif
    return s->status;
}

static uint16_t map_sound_status(uint16_t status) {
    switch(status) {
    case LMN_SOUND_INTERRUPT_RETURNED:return LMN_ENTITY_ACTION_SOUND_READY;
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_ACTION_SOUND_UNBOUND_VECTOR;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        return LMN_ENTITY_ACTION_SOUND_UNTRANSLATED_CHILD;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        return LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN;
    default:return LMN_ENTITY_ACTION_SOUND_INVALID_CHILD;
    }
}

static uint16_t invoke_external_service(ActionSoundState *s,
    const LmnSoundDriverBinding *binding,uint16_t value,
    uint16_t return_offset) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult out;
    s->value=value; /* MOV AX,service. FLAGS are unchanged. */
    call.value=s->value;call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    call.return_offset=return_offset;
    out=lmn_sound_interrupt61_core(s->memory,&call,binding,s->bus);
    s->value=out.value;s->data_segment=out.data_segment;
    s->code_segment=out.code_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_sound_status(out.status);
#if ENTITY_ACTION_SOUND_MUTATION == 7
    if(s->status==LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN) {
        s->status=LMN_ENTITY_ACTION_SOUND_READY;
        s->continuation=return_offset;
    }
#else
    if(out.status==LMN_SOUND_INTERRUPT_RETURNED)
        s->continuation=return_offset;
#endif
    return s->status;
}

static LmnEntityActionSoundResult finish_at_return(ActionSoundState *s,
                                                    uint16_t return_offset) {
    s->continuation=return_offset;
    s->status=LMN_ENTITY_ACTION_SOUND_READY;
    return result_of(s);
}

static LmnEntityActionSoundResult run_dual_feedback(ActionSoundState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
#if ENTITY_ACTION_SOUND_MUTATION == 3
    uint16_t entry_ds=s->data_segment;
#endif
    uint8_t enabled=read8(s,s->data_segment,SEG09A9_ExternalSoundDriverEnabled);
    s->flags=sub8_flags(s->flags,enabled,0xffu);
#if ENTITY_ACTION_SOUND_MUTATION == 1
    if(enabled!=0xffu)goto after_pc_gate;
#else
    if(enabled==0xffu)goto after_pc_gate;
#endif
    {
        uint8_t options=read8(s,s->data_segment,SEG09A9_SoundOptionBits);
#if ENTITY_ACTION_SOUND_MUTATION == 2
        s->flags=test8_flags(s->flags,(uint8_t)(options&0x03u));
#else
        s->flags=test8_flags(s->flags,(uint8_t)(options&0x01u));
#endif
        if((s->flags&ZF)!=0u)goto after_pc_gate;
    }
    s->value=0x0313u; /* MOV AX,0313h; flags remain from TEST. */
    if(invoke_pc_feedback(s,pc_binding)!=LMN_ENTITY_ACTION_SOUND_READY)
        return result_of(s);
    s->continuation=CS_EntityActionAfterPcFeedback;

after_pc_gate:
    {
        uint16_t gate_segment=s->data_segment;
        uint16_t options_segment=s->data_segment;
        uint8_t fresh_enabled;
#if ENTITY_ACTION_SOUND_MUTATION == 3
        gate_segment=entry_ds;
#endif
        fresh_enabled=read8(s,gate_segment,
                            SEG09A9_ExternalSoundDriverEnabled);
        s->flags=sub8_flags(s->flags,fresh_enabled,0xffu);
#if ENTITY_ACTION_SOUND_MUTATION == 4
        if(fresh_enabled==0xffu)
            return finish_at_return(s,CS_EntityActionFeedbackReturn);
#else
        if(fresh_enabled!=0xffu)
            return finish_at_return(s,CS_EntityActionFeedbackReturn);
#endif
        {
            uint8_t options=read8(s,options_segment,SEG09A9_SoundOptionBits);
#if ENTITY_ACTION_SOUND_MUTATION == 5
            s->flags=test8_flags(s->flags,(uint8_t)(options&0x01u));
#else
            s->flags=test8_flags(s->flags,(uint8_t)(options&0x03u));
#endif
            if((s->flags&ZF)!=0u)
                return finish_at_return(s,CS_EntityActionFeedbackReturn);
        }
    }
    if(invoke_external_service(s,sound_binding,0x0404u,
                               CS_EntityActionFeedbackReturn)!=
       LMN_ENTITY_ACTION_SOUND_READY)
        return result_of(s);
    return finish_at_return(s,CS_EntityActionFeedbackReturn);
}

static LmnEntityActionSoundResult run_external_service(ActionSoundState *s,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t enabled=read8(s,s->data_segment,SEG09A9_ExternalSoundDriverEnabled);
    s->flags=sub8_flags(s->flags,enabled,0xffu);
#if ENTITY_ACTION_SOUND_MUTATION == 4
    if(enabled==0xffu)return finish_at_return(s,
                                CS_EntityActionService0412Return);
#else
    if(enabled!=0xffu)return finish_at_return(s,
                                CS_EntityActionService0412Return);
#endif
    {
        uint8_t options=read8(s,s->data_segment,SEG09A9_SoundOptionBits);
#if ENTITY_ACTION_SOUND_MUTATION == 5
        s->flags=test8_flags(s->flags,(uint8_t)(options&0x01u));
#else
        s->flags=test8_flags(s->flags,(uint8_t)(options&0x03u));
#endif
        if((s->flags&ZF)!=0u)
            return finish_at_return(s,CS_EntityActionService0412Return);
    }
    if(invoke_external_service(s,sound_binding,0x0412u,
                               CS_EntityActionService0412Return)!=
       LMN_ENTITY_ACTION_SOUND_READY)
        return result_of(s);
    return finish_at_return(s,CS_EntityActionService0412Return);
}

LmnEntityActionSoundResult lmn_entity_action_sound_core(uint8_t *memory,
    const LmnEntityActionSoundCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    ActionSoundState s;
    s.entry=call->entry;s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0u;
    s.status=LMN_ENTITY_ACTION_SOUND_READY;
    switch(s.entry) {
    case LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5:
        return run_dual_feedback(&s,pc_binding,sound_binding);
    case LMN_ENTITY_ACTION_SOUND_SERVICE_0412_3287:
        return run_external_service(&s,sound_binding);
    default:
        s.status=LMN_ENTITY_ACTION_SOUND_INVALID_ENTRY;
        return result_of(&s);
    }
}

uint16_t lmn_entity_action_sound_adapter(uint8_t *memory,LmnRegs *r,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityActionSoundCall call;
    LmnEntityActionSoundResult out;
    call.entry=entry;call.value=r->ax;call.map_cursor=r->bx;
    call.count=r->cx;call.auxiliary_value=r->dx;
    call.record_cursor=r->si;call.object_cursor=r->di;
    call.candidate_y=r->bp;call.code_segment=r->cs;
    call.data_segment=r->ds;call.extra_segment=r->es;
    call.stack_segment=r->ss;call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_action_sound_core(memory,&call,pc_binding,
                                     sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    if(out.status==LMN_ENTITY_ACTION_SOUND_READY) {
        uint16_t actual_return=read16_at(memory,bus,r->ss,r->sp,r->flags);
#if ENTITY_ACTION_SOUND_MUTATION == 8
        (void)actual_return;
        /* Mutation: RET consumes its live word but reports the pre-RET IP. */
        r->ip=out.continuation;
#else
        r->ip=actual_return;
#endif
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}
