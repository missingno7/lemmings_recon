#include "entity_actions_basic.h"
#include "lemmings_sym.h"

#ifndef ENTITY_ACTIONS_BASIC_MUTATION
#define ENTITY_ACTIONS_BASIC_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct BasicActionState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} BasicActionState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(BasicActionState *s,uint32_t address,
                             uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(BasicActionState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(BasicActionState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset),s->flags);
}

static void write8(BasicActionState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value,s->flags);
}

static uint16_t read16(BasicActionState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint16_t flags=s->flags;
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if((value&0x80u)!=0u)out|=SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out=szp8((uint8_t)value)&PF;
    if(value==0u)out|=ZF;
    if((value&0x8000u)!=0u)out|=SF;
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

static uint16_t test8_flags(uint16_t flags,uint8_t value) {
    /* TEST leaves AF undefined; the model clears it like sibling cores. */
    return (uint16_t)((flags&~ARITH)|szp8(value));
}

static uint16_t test16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~ARITH)|szp16(value));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before-1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}

static void dec_memory8(BasicActionState *s,uint16_t segment,
                        uint16_t offset) {
    uint16_t instruction_flags=s->flags;
    uint8_t before=read_physical(s,physical(segment,offset),instruction_flags);
    write_physical(s,physical(segment,offset),(uint8_t)(before-1u),
                   instruction_flags);
    s->flags=dec8_flags(instruction_flags,before);
}

static LmnEntityActionsBasicResult result_of(const BasicActionState *s) {
    LmnEntityActionsBasicResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void copy_sound_state(BasicActionState *s,
                             const LmnEntityActionSoundResult *child) {
    s->value=child->value;s->map_cursor=child->map_cursor;
    s->count=child->count;s->auxiliary_value=child->auxiliary_value;
    s->record_cursor=child->record_cursor;
    s->object_cursor=child->object_cursor;s->candidate_y=child->candidate_y;
    s->code_segment=child->code_segment;s->data_segment=child->data_segment;
    s->extra_segment=child->extra_segment;s->stack_segment=child->stack_segment;
    s->stack_offset=child->stack_offset;s->flags=child->flags;
    s->continuation=child->continuation;s->status=child->status;
}

static LmnEntityActionsBasicResult enter_feedback(BasicActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityActionSoundCall child_call;
    LmnEntityActionSoundResult child;
    child_call.entry=LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5;
    child_call.value=s->value;child_call.map_cursor=s->map_cursor;
    child_call.count=s->count;child_call.auxiliary_value=s->auxiliary_value;
    child_call.record_cursor=s->record_cursor;
    child_call.object_cursor=s->object_cursor;
    child_call.candidate_y=s->candidate_y;
    child_call.code_segment=s->code_segment;
    child_call.data_segment=s->data_segment;
    child_call.extra_segment=s->extra_segment;
    child_call.stack_segment=s->stack_segment;
    child_call.stack_offset=s->stack_offset;child_call.flags=s->flags;
    child=lmn_entity_action_sound_core(s->memory,&child_call,pc_binding,
                                       sound_binding,s->bus);
    copy_sound_state(s,&child);
    return result_of(s);
}

static LmnEntityActionsBasicResult fail_to_shared_ret(BasicActionState *s) {
    s->continuation=CS_EntityActionFailureReturn;
    s->status=LMN_ENTITY_ACTIONS_BASIC_READY;
    return result_of(s);
}

static LmnEntityActionsBasicResult selector2(BasicActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount0);
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    {
        uint8_t action_flags=read8(s,s->data_segment,
                                   (uint16_t)(s->record_cursor+0x24u));
#if ENTITY_ACTIONS_BASIC_MUTATION == 1
        s->flags=test8_flags(s->flags,action_flags);
#else
        s->flags=test8_flags(s->flags,(uint8_t)(action_flags&0x01u));
#endif
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }
    {
        uint16_t state=read16(s,s->data_segment,
                              (uint16_t)(s->record_cursor+0x08u));
#if ENTITY_ACTIONS_BASIC_MUTATION == 2
        s->flags=test16_flags(s->flags,(uint16_t)(state&0x0003u));
#else
        s->flags=test16_flags(s->flags,(uint16_t)(state&0x0103u));
#endif
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }

    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount0);
#if ENTITY_ACTIONS_BASIC_MUTATION == 3
    {
        uint8_t previous=read8(s,s->data_segment,
                               (uint16_t)(s->record_cursor+0x24u));
        write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u),
               (uint8_t)(previous|0x01u));
    }
#else
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u),0x01u);
#endif
    return enter_feedback(s,pc_binding,sound_binding);
}

static LmnEntityActionsBasicResult selector3(BasicActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount1);
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    {
        uint8_t marker=read8(s,s->data_segment,
                             (uint16_t)(s->record_cursor+0x25u));
        s->flags=sub8_flags(s->flags,marker,0u);
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }
    {
        uint16_t state=read16(s,s->data_segment,
                              (uint16_t)(s->record_cursor+0x08u));
        s->flags=test16_flags(s->flags,(uint16_t)(state&0x0103u));
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }

#if ENTITY_ACTIONS_BASIC_MUTATION == 4
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount1);
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x25u),0xffu);
#else
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x25u),0xffu);
#if ENTITY_ACTIONS_BASIC_MUTATION == 5
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount0);
#else
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount1);
#endif
#endif
    write8(s,s->data_segment,SEG09A9_LevelActionCountRefreshCounter1,0u);
    return enter_feedback(s,pc_binding,sound_binding);
}

static LmnEntityActionsBasicResult selector4(BasicActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount2);
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    {
        uint8_t action_flags=read8(s,s->data_segment,
                                   (uint16_t)(s->record_cursor+0x20u));
        s->flags=sub8_flags(s->flags,action_flags,0u);
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }
    {
        uint16_t state=read16(s,s->data_segment,
                              (uint16_t)(s->record_cursor+0x08u));
        s->flags=test16_flags(s->flags,(uint16_t)(state&0xc003u));
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }

    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount2);
#if ENTITY_ACTIONS_BASIC_MUTATION == 6
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x20u),0x4fu);
    write8(s,s->data_segment,SEG09A9_LevelActionCountRefreshCounter2,0u);
#else
    write8(s,s->data_segment,SEG09A9_LevelActionCountRefreshCounter2,0u);
#if ENTITY_ACTIONS_BASIC_MUTATION == 7
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x20u),0x40u);
#else
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+0x20u),0x4fu);
#endif
#endif
    return enter_feedback(s,pc_binding,sound_binding);
}

LmnEntityActionsBasicResult lmn_entity_actions_basic_core(uint8_t *memory,
    const LmnEntityActionsBasicCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    BasicActionState s;
    s.memory=memory;s.bus=bus;s.entry=call->entry;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0u;
    s.status=LMN_ENTITY_ACTIONS_BASIC_READY;
    switch(s.entry) {
    case LMN_ENTITY_ACTIONS_BASIC_SELECTOR_2:
        return selector2(&s,pc_binding,sound_binding);
    case LMN_ENTITY_ACTIONS_BASIC_SELECTOR_3:
        return selector3(&s,pc_binding,sound_binding);
    case LMN_ENTITY_ACTIONS_BASIC_SELECTOR_4:
        return selector4(&s,pc_binding,sound_binding);
    default:
        s.status=LMN_ENTITY_ACTIONS_BASIC_INVALID_ENTRY;
        return result_of(&s);
    }
}

static uint16_t read_return_word(uint8_t *memory,const LmnRasterBus *bus,
                                 uint16_t segment,uint16_t offset,
                                 uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&0xfffffu,flags);
    } else {
        low=memory[address];
        high=memory[(address+1u)&0xfffffu];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_entity_actions_basic_adapter(uint8_t *memory,LmnRegs *r,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityActionsBasicCall call;
    LmnEntityActionsBasicResult out;
    call.entry=entry;call.value=r->ax;call.map_cursor=r->bx;
    call.count=r->cx;call.auxiliary_value=r->dx;
    call.record_cursor=r->si;call.object_cursor=r->di;
    call.candidate_y=r->bp;call.code_segment=r->cs;
    call.data_segment=r->ds;call.extra_segment=r->es;
    call.stack_segment=r->ss;call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_actions_basic_core(memory,&call,pc_binding,
                                      sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    if(out.status==LMN_ENTITY_ACTIONS_BASIC_READY) {
        r->ip=read_return_word(memory,bus,r->ss,r->sp,r->flags);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}
