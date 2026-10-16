#include "entity_action_map.h"
#include "lemmings_sym.h"

#ifndef ENTITY_ACTION_MAP_MUTATION
#define ENTITY_ACTION_MAP_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,DF=0x0400u,OF=0x0800u,ARITH=0x08d5u };

typedef struct EntityActionMapState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} EntityActionMapState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(EntityActionMapState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityActionMapState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntityActionMapState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityActionMapState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

static uint16_t read16(EntityActionMapState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityActionMapState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
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

static uint16_t szp16(uint16_t value) {
    uint16_t out=szp8((uint8_t)value);
    out=(uint16_t)(out&~(SF|ZF));
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
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
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)sum,out=szp16(result);
    if(sum>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before+1u),out=szp16(result);
    if((before^1u^result)&AF)out|=AF;
    if(before==0x7fffu)out|=OF;
    return (uint16_t)((flags&~(ARITH&~CF))|out|(flags&CF));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before-1u);
    uint16_t out=szp8(result);
    if((before^1u^result)&AF)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~(ARITH&~CF))|out|(flags&CF));
}

static uint16_t shr16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before>>1),out=szp16(result);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    /* SHR leaves AF undefined; retain its incoming opaque bit. */
    return (uint16_t)((flags&~(ARITH&~AF))|out);
}

static uint16_t and16_flags(uint16_t flags,uint16_t result) {
    /* AND clears CF/OF; undefined AF is represented as zero. */
    return (uint16_t)((flags&~ARITH)|szp16(result));
}

static uint16_t and8_flags(uint16_t flags,uint8_t result) {
    /* AND clears CF/OF; undefined AF is represented as zero. */
    return (uint16_t)((flags&~ARITH)|szp8(result));
}

static uint16_t mul_flags(uint16_t flags,uint32_t product) {
    uint16_t out=(product>>16)?(CF|OF):0u;
    /* MUL defines CF/OF only; remaining arithmetic flags stay opaque. */
    return (uint16_t)((flags&~(CF|OF))|out);
}

static void push_word(EntityActionMapState *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(EntityActionMapState *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityActionMapResult result_of(const EntityActionMapState *s) {
    LmnEntityActionMapResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;
    out.count=s->count;out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static LmnEntityActionMapResult failure_return(EntityActionMapState *s) {
    s->continuation=CS_EntityActionFailureReturn;
    s->status=LMN_ENTITY_ACTION_MAP_READY;
    return result_of(s);
}

static uint8_t record_byte(EntityActionMapState *s,uint16_t offset) {
    return read8(s,s->data_segment,(uint16_t)(s->record_cursor+offset));
}

static uint16_t record_word(EntityActionMapState *s,uint16_t offset) {
    return read16(s,s->data_segment,(uint16_t)(s->record_cursor+offset));
}

static void store_record_byte(EntityActionMapState *s,uint16_t offset,
                              uint8_t value) {
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+offset),value,
           s->flags);
}

static void store_record_word(EntityActionMapState *s,uint16_t offset,
                              uint16_t value) {
    write16(s,s->data_segment,(uint16_t)(s->record_cursor+offset),value,
            s->flags);
}

static void update_decrement_counter(EntityActionMapState *s) {
    uint8_t before=read8(s,s->data_segment,SEG09A9_LevelActionCount3);
    uint8_t after=(uint8_t)(before-1u);
    uint16_t entry_flags=s->flags;
    uint16_t updated_flags=dec8_flags(entry_flags,before);
#if ENTITY_ACTION_MAP_MUTATION == 5
    /* Mutation: memory DEC's write phase incorrectly sees resulting FLAGS. */
    write8(s,s->data_segment,SEG09A9_LevelActionCount3,after,updated_flags);
#else
    write8(s,s->data_segment,SEG09A9_LevelActionCount3,after,entry_flags);
#endif
    s->flags=updated_flags;
}

static void store_height_and_callback(EntityActionMapState *s) {
    uint8_t before,after;
    uint16_t entry_flags;
    update_decrement_counter(s);
    write8(s,s->data_segment,SEG09A9_LevelActionCountRefreshCounter3,0u,
           s->flags);
    store_record_word(s,0x08u,0x0100u);
    store_record_byte(s,0x28u,0u);
    store_record_word(s,0x0au,0x0008u);
    store_record_word(s,0x0cu,0x0f9bu);
    store_record_word(s,0x10u,0x005au);
    store_record_word(s,0x12u,0x003cu);
    store_record_byte(s,0x29u,0u);
    store_record_word(s,0x04u,0xfff8u);
    store_record_word(s,0x06u,0xfff6u);
    s->value=read16(s,s->data_segment,
                    (uint16_t)(SEG09A9_DrawingCallbackSlots+0x00u));
    store_record_word(s,0x14u,s->value);
    store_record_byte(s,0x2au,0u);

    entry_flags=s->flags;
    before=record_byte(s,0x24u);
    after=(uint8_t)(before&1u);
#if ENTITY_ACTION_MAP_MUTATION == 6
    s->flags=and8_flags(entry_flags,after);
    store_record_byte(s,0x24u,after);
#else
    store_record_byte(s,0x24u,after);
    s->flags=and8_flags(entry_flags,after);
#endif
}

static void save_replaced_map_cells(EntityActionMapState *s) {
    uint16_t di,si,prior;
    uint8_t code[9]={0x02u,0x0au,0x03u,
                     0x02u,0x0au,0x03u,
                     0x02u,0x0au,0x03u};
    unsigned i;

    /* PUSH SI; PUSH DS; POP ES; MOV DI,BX; ADD SI,16h; XCHG SI,DI. */
    push_word(s,s->record_cursor);
    push_word(s,s->data_segment);
    s->extra_segment=pop_word(s);
#if ENTITY_ACTION_MAP_MUTATION == 8
    /* Mutation: discard the live popped segment and force the entry DS. */
    s->extra_segment=s->data_segment;
#endif
    s->object_cursor=s->map_cursor;
    prior=s->record_cursor;
    s->record_cursor=(uint16_t)(s->record_cursor+0x16u);
    s->flags=add16_flags(s->flags,prior,0x16u);
    di=s->object_cursor;
    si=s->record_cursor;
    s->record_cursor=di;
    di=si;
    s->object_cursor=di;
    si=s->record_cursor;

    for(i=0;i<9u;++i) {
        uint8_t old=read8(s,s->stack_segment,si);
        uint16_t write_flags=s->flags;
        s->value=(uint16_t)((s->value&0xff00u)|old);
        write8(s,s->stack_segment,si,code[i],write_flags);
        prior=si;
        si=(uint16_t)(si+1u);
        s->flags=inc16_flags(s->flags,prior);
#if ENTITY_ACTION_MAP_MUTATION == 7
        write8(s,s->extra_segment,di,old, s->flags);
        di=(uint16_t)(di+1u);
#else
        write8(s,s->extra_segment,di,old,s->flags);
        di=(uint16_t)(di+((s->flags&DF)?0xffffu:1u));
#endif
        if(i==2u||i==5u) {
            prior=si;
            si=(uint16_t)(si+0x019du);
            s->flags=add16_flags(s->flags,prior,0x019du);
        }
    }

    /* POP SI rereads its true SS save, including map/stack aliasing. */
    s->object_cursor=di;
    s->record_cursor=pop_word(s);
}

static LmnEntityActionMapResult request_feedback(EntityActionMapState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityActionSoundCall call;
    LmnEntityActionSoundResult out;
    call.entry=LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    out=lmn_entity_action_sound_core(s->memory,&call,pc_binding,
                                     sound_binding,s->bus);
    /* PC transport can return every register and segment.  The sound core
       already merges the external transport's narrower result with these
       incoming roles, so copy the complete child state here. */
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=out.status;
    return result_of(s);
}

static void transition_to_feedback(EntityActionMapState *s) {
    store_height_and_callback(s);
    save_replaced_map_cells(s);
}

static int reject_byte(EntityActionMapState *s,uint8_t value) {
    s->flags=sub8_flags(s->flags,value,0x02u);
    if(value==0x02u)return 1;
    s->flags=sub8_flags(s->flags,value,0x0au);
    if(value==0x0au)return 1;
    s->flags=sub8_flags(s->flags,value,0x03u);
    return value==0x03u;
}

static int reject_high_byte(EntityActionMapState *s,uint8_t value) {
    s->flags=sub8_flags(s->flags,value,0x02u);
    if(value==0x02u)return 1;
    s->flags=sub8_flags(s->flags,value,0x0au);
    if(value==0x0au)return 1;
    s->flags=sub8_flags(s->flags,value,0x03u);
    return value==0x03u;
}

static LmnEntityActionMapResult run_selector5(EntityActionMapState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t count;
    uint16_t before;
    uint32_t product;
#if ENTITY_ACTION_MAP_MUTATION == 3
    uint16_t saved_x;
#endif
#if ENTITY_ACTION_MAP_MUTATION == 2
    uint16_t entry_auxiliary=s->auxiliary_value;
#endif
#if ENTITY_ACTION_MAP_MUTATION == 4
    uint16_t first_probe=0u;
#endif

    count=read8(s,s->data_segment,SEG09A9_LevelActionCount3);
    s->flags=sub8_flags(s->flags,count,0u); /* CMP count,0. */
    if(count==0u)return failure_return(s);

    s->value=record_word(s,0x08u); /* MOV AX,[SI+8]. */
    s->value=(uint16_t)(s->value&0xf56fu);
    s->flags=and16_flags(s->flags,s->value); /* AND AX,F56F. */
    if(s->value!=0u)return failure_return(s); /* JNZ failure. */

    s->value=record_word(s,0x00u); /* MOV AX,[SI]. */
    s->map_cursor=record_word(s,0x02u); /* MOV BX,[SI+2]. */
    before=s->value;s->value=(uint16_t)(before-0x0004u);
    s->flags=sub16_flags(s->flags,before,0x0004u);
    before=s->map_cursor;s->map_cursor=(uint16_t)(before-0x0006u);
    s->flags=sub16_flags(s->flags,before,0x0006u);
#if ENTITY_ACTION_MAP_MUTATION == 1
    before=s->map_cursor;s->map_cursor=(uint16_t)(before-0x000eu);
    s->flags=sub16_flags(s->flags,before,0x000eu);
#else
    before=s->map_cursor;s->map_cursor=(uint16_t)(before-0x0010u);
    s->flags=sub16_flags(s->flags,before,0x0010u);
#endif
    before=s->value;s->value=(uint16_t)(before>>1);
    s->flags=shr16_flags(s->flags,before);
    before=s->value;s->value=(uint16_t)(before>>1);
    s->flags=shr16_flags(s->flags,before);
    before=s->map_cursor;s->map_cursor=(uint16_t)(before>>1);
    s->flags=shr16_flags(s->flags,before);
    before=s->map_cursor;s->map_cursor=(uint16_t)(before>>1);
    s->flags=shr16_flags(s->flags,before);
#if ENTITY_ACTION_MAP_MUTATION == 3
    saved_x=s->value;
#endif

    /* PUSH AX; PUSH DX; MOV AX,BX; MOV DX,01A0; MUL DX. */
    push_word(s,s->value);
    push_word(s,s->auxiliary_value);
    s->value=s->map_cursor;
    s->auxiliary_value=0x01a0u;
    product=(uint32_t)s->value*s->auxiliary_value;
    s->value=(uint16_t)product;
    s->auxiliary_value=(uint16_t)(product>>16);
    s->flags=mul_flags(s->flags,product);

    /* POP DX and POP BX use the live SS words even under mutations. */
    {
        uint16_t popped_dx=pop_word(s);
#if ENTITY_ACTION_MAP_MUTATION == 2
        (void)popped_dx;
        s->auxiliary_value=entry_auxiliary;
#else
        s->auxiliary_value=popped_dx;
#endif
    }
    {
        uint16_t popped_bx=pop_word(s);
#if ENTITY_ACTION_MAP_MUTATION == 3
        (void)popped_bx;
        s->map_cursor=saved_x;
#else
        s->map_cursor=popped_bx;
#endif
    }
    before=s->map_cursor;
    s->map_cursor=(uint16_t)(s->map_cursor+s->value);
    s->flags=add16_flags(s->flags,before,s->value);
    before=s->map_cursor;
    s->map_cursor=(uint16_t)(s->map_cursor+SEG143E_InteractionCellMapBase);
    s->flags=add16_flags(s->flags,before,SEG143E_InteractionCellMapBase);

    s->value=read16(s,s->stack_segment,s->map_cursor);
#if ENTITY_ACTION_MAP_MUTATION == 4
    first_probe=s->value;
#endif
    if(reject_byte(s,(uint8_t)s->value))return failure_return(s);
    if(reject_high_byte(s,(uint8_t)(s->value>>8)))
        return failure_return(s);

    s->value=(uint16_t)((s->value&0xff00u)|
        read8(s,s->stack_segment,(uint16_t)(s->map_cursor+0x0002u)));
    if(reject_byte(s,(uint8_t)s->value))return failure_return(s);

#if ENTITY_ACTION_MAP_MUTATION == 4
    /* Mutation: reuse the first map word at the later +01A0 probe. */
    s->value=first_probe;
#else
    s->value=read16(s,s->stack_segment,
                    (uint16_t)(s->map_cursor+0x01a0u));
#endif
    if(reject_byte(s,(uint8_t)s->value))return failure_return(s);
    if(reject_high_byte(s,(uint8_t)(s->value>>8)))
        return failure_return(s);

    s->value=(uint16_t)((s->value&0xff00u)|
        read8(s,s->stack_segment,(uint16_t)(s->map_cursor+0x01a2u)));
    if(reject_byte(s,(uint8_t)s->value))return failure_return(s);

    s->value=read16(s,s->stack_segment,
                    (uint16_t)(s->map_cursor+0x0340u));
    if(reject_byte(s,(uint8_t)s->value))return failure_return(s);
    if(reject_high_byte(s,(uint8_t)(s->value>>8)))
        return failure_return(s);

    s->value=(uint16_t)((s->value&0xff00u)|
        read8(s,s->stack_segment,(uint16_t)(s->map_cursor+0x0342u)));
    if(reject_byte(s,(uint8_t)s->value))return failure_return(s);

    transition_to_feedback(s);
    return request_feedback(s,pc_binding,sound_binding);
}

LmnEntityActionMapResult lmn_entity_action_map_core(uint8_t *memory,
    const LmnEntityActionMapCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    EntityActionMapState s;
    s.memory=memory;s.bus=bus;s.entry=call->entry;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0u;
    s.status=LMN_ENTITY_ACTION_MAP_READY;
    if(s.entry!=LMN_ENTITY_ACTION_MAP_SELECTOR_5) {
        s.status=LMN_ENTITY_ACTION_MAP_INVALID_ENTRY;
        return result_of(&s);
    }
    return run_selector5(&s,pc_binding,sound_binding);
}

static uint16_t read_return(uint8_t *memory,const LmnRasterBus *bus,
                            uint16_t ss,uint16_t sp,uint16_t flags) {
    uint32_t address=physical(ss,sp);
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

uint16_t lmn_entity_action_map_adapter(uint8_t *memory,LmnRegs *r,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityActionMapCall call;
    LmnEntityActionMapResult out;
    call.entry=entry;call.value=r->ax;call.map_cursor=r->bx;
    call.count=r->cx;call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;call.code_segment=r->cs;
    call.data_segment=r->ds;call.extra_segment=r->es;
    call.stack_segment=r->ss;call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_action_map_core(memory,&call,pc_binding,
                                   sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;r->es=out.extra_segment;
    r->ss=out.stack_segment;r->sp=out.stack_offset;
    r->flags=out.flags;r->ip=out.continuation;
    if(out.status==LMN_ENTITY_ACTION_MAP_READY) {
        r->ip=read_return(memory,bus,r->ss,r->sp,r->flags);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}
