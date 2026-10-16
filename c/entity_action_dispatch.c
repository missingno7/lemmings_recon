#include "entity_action_dispatch.h"
#include "entity_actions_advanced.h"
#include "entity_action_map.h"
#include "lemmings_sym.h"

#ifndef ENTITY_ACTION_DISPATCH_MUTATION
#define ENTITY_ACTION_DISPATCH_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct ActionDispatchState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} ActionDispatchState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(ActionDispatchState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(ActionDispatchState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(ActionDispatchState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static uint16_t read16(ActionDispatchState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t read16_at(uint8_t *memory,const LmnRasterBus *bus,
                          uint16_t segment,uint16_t offset,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address&0xfffffu,flags);
        high=bus->read_byte(bus->context,memory,
                            (address+1u)&0xfffffu,flags);
    } else {
        low=memory[address&0xfffffu];
        high=memory[(address+1u)&0xfffffu];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

#if ENTITY_ACTION_DISPATCH_MUTATION == 6
static void write16(ActionDispatchState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}
#endif

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

#if ENTITY_ACTION_DISPATCH_MUTATION != 5
static uint16_t and16_flags(uint16_t flags,uint16_t value) {
    uint16_t out=szp8((uint8_t)value);
    out=(uint16_t)(out&~(SF|ZF));
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    /* AND clears CF/OF; AF is undefined and represented as zero. */
    return (uint16_t)((flags&~ARITH)|out);
}
#endif

static LmnEntityActionDispatchResult result_of(const ActionDispatchState *s) {
    LmnEntityActionDispatchResult out;
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

static LmnEntityActionDispatchResult return_at(ActionDispatchState *s,
                                               uint16_t continuation) {
    s->continuation=continuation;
    s->status=LMN_ENTITY_ACTION_DISPATCH_READY;
    return result_of(s);
}

#if ENTITY_ACTION_DISPATCH_MUTATION == 6
static void push_synthetic_call(ActionDispatchState *s) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,
            CS_DispatchEntityAction,s->flags);
}
#endif

typedef LmnEntityActionsBasicResult (*EntityActionCore)(uint8_t *,
    const LmnEntityActionsBasicCall *,const LmnPcSpeakerBinding *,
    const LmnSoundDriverBinding *,const LmnRasterBus *);

static LmnEntityActionDispatchResult apply_action(
    ActionDispatchState *s,uint16_t entry,uint16_t target,EntityActionCore core,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityActionsBasicCall call;
    LmnEntityActionsBasicResult out;
    call.entry=entry;call.value=s->value;call.map_cursor=s->map_cursor;
    call.count=s->count;call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
#if ENTITY_ACTION_DISPATCH_MUTATION == 6
    /* Mutation: a JMP child is given a fabricated CALL return word. */
    push_synthetic_call(s);
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
#endif
    out=core(s->memory,&call,pc_binding,
                                      sound_binding,s->bus);
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->child_entry=target;s->child_status=out.status;
    s->status=(out.status==LMN_ENTITY_ACTIONS_BASIC_READY)
        ?LMN_ENTITY_ACTION_DISPATCH_READY
        :LMN_ENTITY_ACTION_DISPATCH_CHILD_STOP;
    return result_of(s);
}

#if ENTITY_ACTION_DISPATCH_MUTATION != 2
static void load_selected(ActionDispatchState *s) {
    s->record_cursor=read16(s,s->data_segment,
                            SEG09A9_EntitySelectedRecordOffset);
    s->value=(uint16_t)((s->value&0xff00u)|
        read8(s,s->data_segment,SEG09A9_EntityActionSelector));
}
#endif

LmnEntityActionDispatchResult lmn_entity_action_dispatch_core(
    uint8_t *memory,const LmnEntityActionDispatchCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    ActionDispatchState s;
    uint8_t byte_value,selector;
    uint16_t input;
    s.memory=memory;s.bus=bus;s.value=call->value;s.map_cursor=call->map_cursor;
    s.count=call->count;s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0u;
    s.status=LMN_ENTITY_ACTION_DISPATCH_READY;
    s.child_entry=0u;s.child_status=0xffffu;

#if ENTITY_ACTION_DISPATCH_MUTATION == 1
    /* Mutation: latch is cleared before the entry gates are tested. */
    write_physical(&s,physical(s.data_segment,
                     SEG09A9_EntityActionPressLatch),0u,s.flags);
#endif
    byte_value=read8(&s,s.data_segment,SEG09A9_EntityUpdateGate);
    s.flags=sub8_flags(s.flags,byte_value,0xffu); /* CMP [002B],FF. */
    if(byte_value==0xffu)return return_at(&s,CS_EntityActionDispatchReturn);

    byte_value=read8(&s,s.data_segment,SEG09A9_EntityWorkGuard);
    s.flags=sub8_flags(s.flags,byte_value,0xffu); /* CMP [0050],FF. */
    if(byte_value==0xffu)return return_at(&s,CS_EntityActionDispatchReturn);

    byte_value=read8(&s,s.data_segment,SEG09A9_EntityCandidateCount);
    s.flags=sub8_flags(s.flags,byte_value,0u); /* CMP [0063],0. */
    if(byte_value==0u)return return_at(&s,CS_EntityActionDispatchReturn);

    input=read16(&s,s.data_segment,SEG09A9_InputButtonsWord);
    s.value=input; /* MOV AX,[0014]. */
#if ENTITY_ACTION_DISPATCH_MUTATION == 5
    /* Mutation: omit AND AX,1, retaining the input word and old FLAGS. */
#else
    s.value=(uint16_t)(s.value&1u);
    s.flags=and16_flags(s.flags,s.value); /* AND AX,1. */
#endif
    if((input&1u)==0u) {
        write_physical(&s,physical(s.data_segment,
                         SEG09A9_EntityActionPressLatch),0u,s.flags);
        return return_at(&s,CS_EntityActionReleasedReturn);
    }

    byte_value=read8(&s,s.data_segment,SEG09A9_EntityActionPressLatch);
    s.flags=sub8_flags(s.flags,byte_value,0xffu); /* CMP latch,FF. */
    if(byte_value==0xffu)return return_at(&s,CS_EntityActionDispatchReturn);

#if ENTITY_ACTION_DISPATCH_MUTATION == 4
    /* Mutation: cache selected SI and selector before the latch store. */
    load_selected(&s);
    write_physical(&s,physical(s.data_segment,
                     SEG09A9_EntityActionPressLatch),0xffu,s.flags);
#elif ENTITY_ACTION_DISPATCH_MUTATION == 2
    /* Mutation: selector read is moved before latch store; SI stays live-late. */
    selector=read8(&s,s.data_segment,SEG09A9_EntityActionSelector);
    s.value=(uint16_t)((s.value&0xff00u)|selector);
    write_physical(&s,physical(s.data_segment,
                     SEG09A9_EntityActionPressLatch),0xffu,s.flags);
    s.record_cursor=read16(&s,s.data_segment,
                           SEG09A9_EntitySelectedRecordOffset);
#else
    write_physical(&s,physical(s.data_segment,
                     SEG09A9_EntityActionPressLatch),0xffu,s.flags);
    load_selected(&s);
#endif
    selector=(uint8_t)s.value;
    s.flags=sub8_flags(s.flags,selector,0x02u); /* CMP AL,2. */
#if ENTITY_ACTION_DISPATCH_MUTATION == 3
    if(selector<0x02u)return return_at(&s,CS_EntityActionDispatchReturn);
#else
    if(((s.flags&SF)!=0u)!=((s.flags&OF)!=0u))
        return return_at(&s,CS_EntityActionDispatchReturn); /* JL. */
#endif
    if(selector==0x02u)
        return apply_action(&s,LMN_ENTITY_ACTIONS_BASIC_SELECTOR_2,
            CS_ApplyEntityAction2,lmn_entity_actions_basic_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x03u); /* CMP AL,3. */
    if(selector==0x03u)
        return apply_action(&s,LMN_ENTITY_ACTIONS_BASIC_SELECTOR_3,
            CS_ApplyEntityAction3,lmn_entity_actions_basic_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x04u); /* CMP AL,4. */
    if(selector==0x04u)
        return apply_action(&s,LMN_ENTITY_ACTIONS_BASIC_SELECTOR_4,
            CS_ApplyEntityAction4,lmn_entity_actions_basic_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x05u); /* CMP AL,5. */
    if(selector==0x05u)
        return apply_action(&s,5u,CS_ApplyEntityAction5,
            lmn_entity_action_map_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x06u); /* CMP AL,6. */
    if(selector==0x06u)
        return apply_action(&s,6u,CS_ApplyEntityAction6,
            lmn_entity_actions_advanced_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x07u); /* CMP AL,7. */
    if(selector==0x07u)
        return apply_action(&s,7u,CS_ApplyEntityAction7,
            lmn_entity_actions_advanced_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x08u); /* CMP AL,8. */
    if(selector==0x08u)
        return apply_action(&s,8u,CS_ApplyEntityAction8,
            lmn_entity_actions_advanced_core,pc_binding,sound_binding);

    s.flags=sub8_flags(s.flags,selector,0x09u); /* CMP AL,9. */
    if(selector==0x09u)
        return apply_action(&s,9u,CS_ApplyEntityAction9,
            lmn_entity_actions_advanced_core,pc_binding,sound_binding);

    return return_at(&s,CS_EntityActionDispatchReturn);
}

uint16_t lmn_entity_action_dispatch_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityActionDispatchCall call;
    LmnEntityActionDispatchResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;call.code_segment=r->cs;
    call.data_segment=r->ds;call.extra_segment=r->es;
    call.stack_segment=r->ss;call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_action_dispatch_core(memory,&call,pc_binding,
                                        sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;r->es=out.extra_segment;
    r->ss=out.stack_segment;r->sp=out.stack_offset;
    r->flags=out.flags;r->ip=out.continuation;
    if(out.status==LMN_ENTITY_ACTION_DISPATCH_READY) {
        r->ip=read16_at(memory,bus,r->ss,r->sp,r->flags);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}
