#include "entity_actions_advanced.h"
#include "lemmings_sym.h"

#ifndef ENTITY_ACTIONS_ADVANCED_MUTATION
#define ENTITY_ACTIONS_ADVANCED_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct AdvancedActionState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} AdvancedActionState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(AdvancedActionState *s,uint32_t address,
                             uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(AdvancedActionState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8_at_flags(AdvancedActionState *s,uint16_t segment,
    uint16_t offset,uint16_t flags) {
    return read_physical(s,physical(segment,offset),flags);
}

static uint8_t read8(AdvancedActionState *s,uint16_t segment,uint16_t offset) {
    return read8_at_flags(s,segment,offset,s->flags);
}

static void write8_at_flags(AdvancedActionState *s,uint16_t segment,
    uint16_t offset,uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

static void write8(AdvancedActionState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write8_at_flags(s,segment,offset,value,s->flags);
}

static uint16_t read16_at_flags(AdvancedActionState *s,uint16_t segment,
    uint16_t offset,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t read16(AdvancedActionState *s,uint16_t segment,
                       uint16_t offset) {
    return read16_at_flags(s,segment,offset,s->flags);
}

static void write16_at_flags(AdvancedActionState *s,uint16_t segment,
    uint16_t offset,uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static void write16(AdvancedActionState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    write16_at_flags(s,segment,offset,value,s->flags);
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

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t result=(uint16_t)(left-right);
    uint16_t out=szp16(result);
    if(left<right)out|=CF;
    if((left^right^result)&0x0010u)out|=AF;
    if(((left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide;
    uint16_t out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&0x0010u)out|=AF;
    if(((~(left^right))&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t and8_flags(uint16_t flags,uint8_t result) {
    return (uint16_t)((flags&~ARITH)|szp8(result));
}

static uint16_t and16_flags(uint16_t flags,uint16_t result) {
    return (uint16_t)((flags&~ARITH)|szp16(result));
}

static uint16_t or16_flags(uint16_t flags,uint16_t result) {
    return (uint16_t)((flags&~ARITH)|szp16(result));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before-1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}

#if ENTITY_ACTIONS_ADVANCED_MUTATION == 10
static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before+1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0x0fu)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}
#endif

#if ENTITY_ACTIONS_ADVANCED_MUTATION != 10
static uint16_t inc16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before+1u);
    uint16_t out=szp16(result);
    if((before&0x000fu)==0x000fu)out|=AF;
    if(before==0x7fffu)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}
#endif

static void dec_memory8(AdvancedActionState *s,uint16_t segment,
                        uint16_t offset) {
    uint16_t instruction_flags=s->flags;
    uint8_t before=read8_at_flags(s,segment,offset,instruction_flags);
    write8_at_flags(s,segment,offset,(uint8_t)(before-1u),instruction_flags);
    s->flags=dec8_flags(instruction_flags,before);
}

static void and_memory8(AdvancedActionState *s,uint16_t segment,
                        uint16_t offset,uint8_t mask) {
    uint16_t instruction_flags=s->flags;
    uint8_t before=read8_at_flags(s,segment,offset,instruction_flags);
    uint8_t result=(uint8_t)(before&mask);
    write8_at_flags(s,segment,offset,result,instruction_flags);
    s->flags=and8_flags(instruction_flags,result);
}

static void and_memory16(AdvancedActionState *s,uint16_t segment,
                         uint16_t offset,uint16_t mask) {
    uint16_t instruction_flags=s->flags;
    uint16_t before=read16_at_flags(s,segment,offset,instruction_flags);
    uint16_t result=(uint16_t)(before&mask);
    write16_at_flags(s,segment,offset,result,instruction_flags);
    s->flags=and16_flags(instruction_flags,result);
}

static void or_memory16(AdvancedActionState *s,uint16_t segment,
                        uint16_t offset,uint16_t mask) {
    uint16_t instruction_flags=s->flags;
    uint16_t before=read16_at_flags(s,segment,offset,instruction_flags);
    uint16_t result=(uint16_t)(before|mask);
    write16_at_flags(s,segment,offset,result,instruction_flags);
    s->flags=or16_flags(instruction_flags,result);
}

#if ENTITY_ACTIONS_ADVANCED_MUTATION != 10
static void inc_memory16(AdvancedActionState *s,uint16_t segment,
                         uint16_t offset) {
    uint16_t instruction_flags=s->flags;
    uint16_t before=read16_at_flags(s,segment,offset,instruction_flags);
    write16_at_flags(s,segment,offset,(uint16_t)(before+1u),
                     instruction_flags);
    s->flags=inc16_flags(instruction_flags,before);
}
#endif

#if ENTITY_ACTIONS_ADVANCED_MUTATION == 10
static void inc_memory8(AdvancedActionState *s,uint16_t segment,
                        uint16_t offset) {
    uint16_t instruction_flags=s->flags;
    uint8_t before=read8_at_flags(s,segment,offset,instruction_flags);
    write8_at_flags(s,segment,offset,(uint8_t)(before+1u),instruction_flags);
    s->flags=inc8_flags(instruction_flags,before);
}
#endif

static LmnEntityActionsAdvancedResult result_of(const AdvancedActionState *s) {
    LmnEntityActionsAdvancedResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void copy_sound_state(AdvancedActionState *s,
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

static LmnEntityActionsAdvancedResult enter_sound(AdvancedActionState *s,
    uint16_t sound_entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityActionSoundCall child_call;
    LmnEntityActionSoundResult child;
    child_call.entry=sound_entry;
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

static LmnEntityActionsAdvancedResult fail_to_shared_ret(
    AdvancedActionState *s) {
    s->continuation=CS_EntityActionFailureReturn;
    s->status=LMN_ENTITY_ACTIONS_ADVANCED_READY;
    return result_of(s);
}

static void clear_refresh_counter(AdvancedActionState *s,uint16_t offset) {
    write8(s,s->data_segment,offset,0u);
}

static void write_record_word(AdvancedActionState *s,uint16_t offset,
                              uint16_t value) {
    write16(s,s->data_segment,(uint16_t)(s->record_cursor+offset),value);
}

static void write_record_byte(AdvancedActionState *s,uint16_t offset,
                              uint8_t value) {
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+offset),value);
}

static uint16_t selected_word(AdvancedActionState *s,uint16_t offset) {
    return read16(s,s->data_segment,(uint16_t)(s->record_cursor+offset));
}

static uint8_t selected_byte(AdvancedActionState *s,uint16_t offset) {
    return read8(s,s->data_segment,(uint16_t)(s->record_cursor+offset));
}

static void compare_selected_word(AdvancedActionState *s,uint16_t offset,
                                  uint16_t mask) {
    uint16_t value=selected_word(s,offset);
    s->flags=(uint16_t)((s->flags&~ARITH)|szp16((uint16_t)(value&mask)));
}

static LmnEntityActionsAdvancedResult selector6_transition(
    AdvancedActionState *s,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount4);
    clear_refresh_counter(s,SEG09A9_LevelActionCountRefreshCounter4);
    write_record_word(s,0x08u,0x0080u);
    write_record_word(s,0x04u,0xfff8u);
    write_record_word(s,0x06u,0xfff3u);
    write_record_byte(s,0x28u,0x00u);
    write_record_byte(s,0x21u,0x0cu);
    write_record_word(s,0x0au,0x0000u);
    write_record_word(s,0x0cu,0x06fau);
    write_record_word(s,0x10u,0x0068u);
    write_record_word(s,0x12u,0x004eu);
    write_record_byte(s,0x29u,0x10u);
    s->value=read16(s,s->data_segment,
                    (uint16_t)(SEG09A9_DrawingCallbackSlots+0x08u));
    write_record_byte(s,0x2au,0xffu);
    write_record_word(s,0x14u,s->value);
    and_memory8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u),0x01u);
    return enter_sound(s,LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5,
                       pc_binding,sound_binding);
}

static void selector6_initial_sum(AdvancedActionState *s) {
    uint16_t x=read16(s,s->data_segment,(uint16_t)(s->record_cursor+0x02u));
    uint16_t y=read16(s,s->data_segment,(uint16_t)(s->record_cursor+0x06u));
    uint16_t sum=(uint16_t)(x+y);
    s->value=sum;
    s->flags=add16_flags(s->flags,x,y);
    s->flags=sub16_flags(s->flags,sum,0x000au);
}

static uint16_t selector6_eligibility_mask(void) {
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 2
    return 0xf56fu;
#else
    return 0xf5efu;
#endif
}

static LmnEntityActionsAdvancedResult selector6(AdvancedActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount4);
    uint16_t state;
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    selector6_initial_sum(s);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 1
    if((s->flags&CF)!=0u)return fail_to_shared_ret(s);
#else
    if((s->flags&(CF|ZF))!=0u)return fail_to_shared_ret(s);
#endif

    state=selected_word(s,0x08u);
    s->flags=(uint16_t)((s->flags&~ARITH)|
        szp16((uint16_t)(state&selector6_eligibility_mask())));
    if((s->flags&ZF)!=0u)
        return selector6_transition(s,pc_binding,sound_binding);

    {
        uint8_t slot=read8(s,s->data_segment,
                           SEG09A9_EntityAlternateSlotIndex);
        s->flags=sub8_flags(s->flags,slot,0xffu);
        if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
    }
    s->record_cursor=read16(s,s->data_segment,
                            SEG09A9_EntityAlternateRecordOffset);
    state=selected_word(s,0x08u);
    s->flags=(uint16_t)((s->flags&~ARITH)|
        szp16((uint16_t)(state&selector6_eligibility_mask())));
    if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 3
    selector6_initial_sum(s);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 1
    if((s->flags&CF)!=0u)return fail_to_shared_ret(s);
#else
    if((s->flags&(CF|ZF))!=0u)return fail_to_shared_ret(s);
#endif
#endif
    return selector6_transition(s,pc_binding,sound_binding);
}

static uint16_t selector7_eligibility_mask(void) {
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 4
    return 0xf56fu;
#else
    return 0xf76fu;
#endif
}

static uint16_t selector7_transition_mask(void) {
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 5
    return 0xf76fu;
#else
    return 0xf56fu;
#endif
}

static int direction_nibbles_reject(AdvancedActionState *s) {
    uint8_t direction=selected_byte(s,0x2bu);
    direction=(uint8_t)(direction&0x0fu);
    s->value=(uint16_t)((s->value&0xff00u)|direction);
    s->flags=and8_flags(s->flags,direction);
    s->value=(uint16_t)((s->value&0x00ffu)|0x0700u);
    {
        uint8_t direction_state=selected_byte(s,0x27u);
        s->flags=sub8_flags(s->flags,direction_state,0x01u);
        if((s->flags&ZF)==0u)
            s->value=(uint16_t)((s->value&0x00ffu)|0x0800u);
    }
    {
        uint8_t al=(uint8_t)s->value;
        uint8_t ah=(uint8_t)(s->value>>8);
        s->flags=sub8_flags(s->flags,al,ah);
        if((s->flags&ZF)!=0u)return 1;
    }
    s->flags=sub8_flags(s->flags,(uint8_t)s->value,0x09u);
    return 0;
}

static LmnEntityActionsAdvancedResult selector7_transition(
    AdvancedActionState *s,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount5);
    clear_refresh_counter(s,SEG09A9_LevelActionCountRefreshCounter5);
    and_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x08u),
                 selector7_transition_mask());
    or_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x08u),
                0x0200u);
    write_record_word(s,0x04u,0xfff8u);
    write_record_word(s,0x06u,0xfff6u);
    write_record_byte(s,0x28u,0x00u);
    write_record_word(s,0x0au,0x0000u);
    write_record_word(s,0x0cu,0x07cau);
    write_record_word(s,0x10u,0x0050u);
    write_record_word(s,0x12u,0x003cu);
    write_record_byte(s,0x29u,0x20u);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 6
    s->value=read16(s,s->data_segment,
                    (uint16_t)(SEG09A9_DrawingCallbackSlots+0x06u));
    write_record_byte(s,0x2au,0xffu);
#else
    write_record_byte(s,0x2au,0xffu);
    s->value=read16(s,s->data_segment,
                    (uint16_t)(SEG09A9_DrawingCallbackSlots+0x06u));
#endif
    write_record_word(s,0x14u,s->value);
    and_memory8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u),0x01u);
    return enter_sound(s,LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5,
                       pc_binding,sound_binding);
}

static LmnEntityActionsAdvancedResult selector7(AdvancedActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount5);
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    compare_selected_word(s,0x08u,selector7_eligibility_mask());
    if((s->flags&ZF)==0u) {
        uint8_t slot=read8(s,s->data_segment,
                           SEG09A9_EntityAlternateSlotIndex);
        s->flags=sub8_flags(s->flags,slot,0xffu);
        if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
        s->record_cursor=read16(s,s->data_segment,
                                SEG09A9_EntityAlternateRecordOffset);
        compare_selected_word(s,0x08u,selector7_eligibility_mask());
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
    }

    if(direction_nibbles_reject(s))return fail_to_shared_ret(s);
    if((s->flags&ZF)!=0u) {
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 7
        return enter_sound(s,LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5,
                           pc_binding,sound_binding);
#else
        return enter_sound(s,LMN_ENTITY_ACTION_SOUND_SERVICE_0412_3287,
                           pc_binding,sound_binding);
#endif
    }
    return selector7_transition(s,pc_binding,sound_binding);
}

static LmnEntityActionsAdvancedResult selector9_transition(
    AdvancedActionState *s,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount7);
    clear_refresh_counter(s,SEG09A9_LevelActionCountRefreshCounter7);
    and_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x08u),
                 0xf57fu);
    or_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x08u),
                0x0010u);
    write_record_word(s,0x0au,0x0000u);
    write_record_word(s,0x0cu,0x032au);
    write_record_word(s,0x10u,0x0070u);
    write_record_word(s,0x12u,0x0054u);
    write_record_byte(s,0x28u,0x11u);
    write_record_word(s,0x04u,0xfff8u);
    write_record_word(s,0x06u,0xfff4u);
    write_record_byte(s,0x29u,0x00u);
    s->value=read16(s,s->data_segment,
                    (uint16_t)(SEG09A9_DrawingCallbackSlots+0x0au));
    write_record_word(s,0x14u,s->value);
    write_record_byte(s,0x1fu,0x08u);
    write_record_byte(s,0x2au,0xffu);
    and_memory8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u),0x01u);
    return enter_sound(s,LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5,
                       pc_binding,sound_binding);
}

static void selector9_initial_gates(AdvancedActionState *s) {
    uint8_t nibble=selected_byte(s,0x2cu);
    nibble=(uint8_t)(nibble&0x0fu);
    s->value=(uint16_t)((s->value&0xff00u)|nibble);
    s->flags=and8_flags(s->flags,nibble);
    s->flags=sub8_flags(s->flags,nibble,0x09u);
}

static LmnEntityActionsAdvancedResult selector9(AdvancedActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount7);
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    selector9_initial_gates(s);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
    compare_selected_word(s,0x08u,0xf57fu);
    if((s->flags&ZF)!=0u)
        return selector9_transition(s,pc_binding,sound_binding);

    {
        uint8_t slot=read8(s,s->data_segment,
                           SEG09A9_EntityAlternateSlotIndex);
        s->flags=sub8_flags(s->flags,slot,0xffu);
        if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
    }
    s->record_cursor=read16(s,s->data_segment,
                            SEG09A9_EntityAlternateRecordOffset);
    compare_selected_word(s,0x08u,0xf57fu);
    if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 8
    action_count=read8(s,s->data_segment,SEG09A9_LevelActionCount7);
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
    selector9_initial_gates(s);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
#endif
    return selector9_transition(s,pc_binding,sound_binding);
}

static LmnEntityActionsAdvancedResult selector8_transition(
    AdvancedActionState *s,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    dec_memory8(s,s->data_segment,SEG09A9_LevelActionCount6);
    clear_refresh_counter(s,SEG09A9_LevelActionCountRefreshCounter6);
    and_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x08u),
                 0xfd6fu);
    or_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x08u),
                0x0800u);
    write_record_word(s,0x04u,0xfff8u);
    write_record_word(s,0x06u,0xfff3u);
    write_record_byte(s,0x28u,0x00u);
    write_record_word(s,0x0au,0x0000u);
    write_record_word(s,0x0cu,0x090au);
    write_record_word(s,0x10u,0x0068u);
    write_record_word(s,0x12u,0x004eu);
    write_record_byte(s,0x29u,0x18u);
    s->value=read16(s,s->data_segment,
                    (uint16_t)(SEG09A9_DrawingCallbackSlots+0x08u));
    write_record_word(s,0x14u,s->value);
    write_record_byte(s,0x2au,0xffu);
    and_memory8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u),0x01u);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 10
    inc_memory8(s,s->data_segment,(uint16_t)(s->record_cursor+0x02u));
#else
    inc_memory16(s,s->data_segment,(uint16_t)(s->record_cursor+0x02u));
#endif
    return enter_sound(s,LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5,
                       pc_binding,sound_binding);
}

static LmnEntityActionsAdvancedResult selector8(AdvancedActionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t action_count=read8(s,s->data_segment,
                               SEG09A9_LevelActionCount6);
    uint16_t state;
    s->flags=sub8_flags(s->flags,action_count,0u);
    if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);

    state=selected_word(s,0x08u);
    s->flags=(uint16_t)((s->flags&~ARITH)|
                        szp16((uint16_t)(state&0xfd6fu)));
    if((s->flags&ZF)==0u) {
        uint8_t slot=read8(s,s->data_segment,
                           SEG09A9_EntityAlternateSlotIndex);
        s->flags=sub8_flags(s->flags,slot,0xffu);
        if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
        s->record_cursor=read16(s,s->data_segment,
                                SEG09A9_EntityAlternateRecordOffset);
        state=selected_word(s,0x08u);
        s->flags=(uint16_t)((s->flags&~ARITH)|
                            szp16((uint16_t)(state&0xfd6fu)));
        if((s->flags&ZF)==0u)return fail_to_shared_ret(s);
#if ENTITY_ACTIONS_ADVANCED_MUTATION == 9
        return selector8_transition(s,pc_binding,sound_binding);
#endif
    }

    {
        uint8_t nibble=selected_byte(s,0x2cu);
        nibble=(uint8_t)(nibble&0x0fu);
        s->value=(uint16_t)((s->value&0xff00u)|nibble);
        s->flags=and8_flags(s->flags,nibble);
        s->flags=sub8_flags(s->flags,nibble,0x09u);
        if((s->flags&ZF)!=0u)return fail_to_shared_ret(s);
    }
    if(direction_nibbles_reject(s))return fail_to_shared_ret(s);
    if((s->flags&ZF)!=0u)
        return enter_sound(s,LMN_ENTITY_ACTION_SOUND_SERVICE_0412_3287,
                           pc_binding,sound_binding);
    return selector8_transition(s,pc_binding,sound_binding);
}

LmnEntityActionsAdvancedResult lmn_entity_actions_advanced_core(
    uint8_t *memory,const LmnEntityActionsAdvancedCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    AdvancedActionState s;
    s.memory=memory;s.bus=bus;s.entry=call->entry;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0u;
    s.status=LMN_ENTITY_ACTIONS_ADVANCED_READY;
    switch(s.entry) {
    case LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_6:
        return selector6(&s,pc_binding,sound_binding);
    case LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_7:
        return selector7(&s,pc_binding,sound_binding);
    case LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_8:
        return selector8(&s,pc_binding,sound_binding);
    case LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_9:
        return selector9(&s,pc_binding,sound_binding);
    default:
        s.status=LMN_ENTITY_ACTIONS_ADVANCED_INVALID_ENTRY;
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

uint16_t lmn_entity_actions_advanced_adapter(uint8_t *memory,LmnRegs *r,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityActionsAdvancedCall call;
    LmnEntityActionsAdvancedResult out;
    call.entry=entry;call.value=r->ax;call.map_cursor=r->bx;
    call.count=r->cx;call.auxiliary_value=r->dx;
    call.record_cursor=r->si;call.object_cursor=r->di;
    call.candidate_y=r->bp;call.code_segment=r->cs;
    call.data_segment=r->ds;call.extra_segment=r->es;
    call.stack_segment=r->ss;call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_actions_advanced_core(memory,&call,pc_binding,
                                         sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    if(out.status==LMN_ENTITY_ACTIONS_ADVANCED_READY) {
        r->ip=read_return_word(memory,bus,r->ss,r->sp,r->flags);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}
