#include "entity_state400.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE400_MUTATION
#define ENTITY_STATE400_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State400 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State400;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State400 *s,uint32_t address,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(State400 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State400 *s,uint16_t segment,uint16_t offset,
                     uint16_t flags) {
    return read_physical(s,physical(segment,offset),flags);
}

static void write8(State400 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Word accesses use the adjacent physical byte even at 20-bit wrap. */
static uint16_t read16(State400 *s,uint16_t segment,uint16_t offset,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(State400 *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t record_offset(const State400 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    uint16_t mask=(uint16_t)(bits==8u?0x00ffu:0xffffu);
    value=(uint16_t)(value&mask);
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(uint16_t)(1u<<(bits-1u)))out|=SF;
    return out;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t lhs=(uint32_t)(left&mask),rhs=(uint32_t)(right&mask);
    uint32_t sum=lhs+rhs;
    uint16_t result=(uint16_t)(sum&mask),out=szp(result,bits);
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint16_t lhs=(uint16_t)(left&mask),rhs=(uint16_t)(right&mask);
    uint16_t result=(uint16_t)(((uint32_t)lhs-(uint32_t)rhs)&mask);
    uint16_t out=szp(result,bits);
    uint32_t sign=1u<<(bits-1u);
    if(lhs<rhs)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc16_flags(uint16_t flags,uint16_t before) {
    uint16_t carry=(uint16_t)(flags&CF);
    uint16_t out=add_flags(flags,before,1u,16u);
    return (uint16_t)((out&~CF)|carry);
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    /* AND leaves AF undefined; this oracle represents it as zero. */
    return (uint16_t)((flags&~ARITH)|szp(value,8u));
}

static uint16_t pop_word(State400 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset,s->flags);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static void push_word(State400 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static LmnEntityState400Result result_of(const State400 *s) {
    LmnEntityState400Result out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static uint16_t map_finish_status(uint16_t status) {
    switch(status) {
    case LMN_ENTITY_FINISH_RETURNED:return LMN_ENTITY_STATE400_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE400_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE400_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE400_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE400_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE400_CHANGED_FINISH_CALL_RETURN;
    default:return LMN_ENTITY_STATE400_INVALID_CHILD;
    }
}

static LmnEntityState400Result finish(State400 *s,uint16_t entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=entry;call.value=s->value;call.map_cursor=s->map_cursor;
    call.count=s->count;call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    out=lmn_entity_finish_core(s->memory,&call,pc_binding,sound_binding,s->bus);
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_finish_status(out.status);
    return result_of(s);
}

static uint16_t call_pixel(State400 *s,uint16_t return_offset) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult child;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;call.flags=s->flags;
    child=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=child.value;s->map_cursor=child.table_cursor;
    s->count=child.column_byte;s->object_cursor=child.destination_offset;
    s->auxiliary_value=child.restored_value;s->extra_segment=0xa000u;
    s->stack_offset=child.stack_offset;s->flags=child.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE400_MUTATION == 3
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE400_CHANGED_PIXEL_RETURN;
        return 0u;
    }
#endif
    return 1u;
}

static uint16_t cmp_ge_signed(uint16_t flags,uint16_t left,uint16_t right) {
#if ENTITY_STATE400_MUTATION == 7
    (void)flags;
    return left>=right;
#else
    (void)left;(void)right;
    return (((flags&SF)!=0u)==((flags&OF)!=0u));
#endif
}

static void add_record_word(State400 *s,uint16_t displacement,uint16_t value) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old+value);
    uint16_t result_flags=add_flags(entry,old,value,16u);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=result_flags;
}

static void inc_record_word(State400 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old+1u);
    uint16_t result_flags=inc16_flags(entry,old);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=result_flags;
}

static uint8_t sample_pixel(State400 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor,s->flags);
    uint8_t al=(uint8_t)(pixel&(uint8_t)(s->value>>8));
    /* MOV AL,[ES:DI]; AND AL,AH. */
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic8_flags(s->flags,al);
    return al;
}

static void add_live_pitch(State400 *s,uint16_t *cached_pitch,
                           uint16_t *pitch_cached) {
    uint16_t pitch;
#if ENTITY_STATE400_MUTATION == 4
    if(!*pitch_cached) {
        *cached_pitch=read16(s,s->data_segment,
            SEG09A9_EntityPixelRowPitchBytes,s->flags);
        *pitch_cached=1u;
    }
    pitch=*cached_pitch;
#else
    (void)cached_pitch;(void)pitch_cached;
    pitch=read16(s,s->data_segment,SEG09A9_EntityPixelRowPitchBytes,s->flags);
#endif
    {
        uint16_t old=s->object_cursor;
        s->object_cursor=(uint16_t)(old+pitch);
        s->flags=add_flags(s->flags,old,pitch,16u);
    }
}

static LmnEntityState400Result collision(State400 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t callback=0u;
#if ENTITY_STATE400_MUTATION == 6
    callback=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots,s->flags);
#endif
    /* 2AEC..2B1D: ordered transition stores, then late callback fetch. */
    write16(s,s->data_segment,record_offset(s,0x08u),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x0au),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x0cu),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x10u),0x005au,s->flags);
    write16(s,s->data_segment,record_offset(s,0x12u),0x003cu,s->flags);
    write8(s,s->data_segment,record_offset(s,0x28u),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x04u),0xfff8u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x06u),0xfff6u,s->flags);
    write8(s,s->data_segment,record_offset(s,0x29u),9u,s->flags);
#if ENTITY_STATE400_MUTATION != 6
    callback=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots,s->flags);
#endif
    write16(s,s->data_segment,record_offset(s,0x14u),callback,s->flags);
    write8(s,s->data_segment,record_offset(s,0x2au),0u,s->flags);
    {
        uint16_t entry=s->flags,offset=record_offset(s,0x24u);
        uint8_t old=read8(s,s->data_segment,offset,entry);
        uint8_t updated=(uint8_t)(old&1u);
        write8(s,s->data_segment,offset,updated,entry);
        s->flags=logic8_flags(entry,updated);
    }
    return finish(s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

LmnEntityState400Result lmn_entity_state400_core(uint8_t *memory,
    const LmnEntityState400Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State400 s;
    uint16_t pair_offset,pitch_cache=0u,pitch_cached=0u;
    uint8_t first,delta;
    uint16_t return_offset=0u,sample_count=0u;
    unsigned probe;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_EntityIterationTail;
    s.status=LMN_ENTITY_STATE400_READY;

    /* MOV BX,2698; ADD BX,[SI+0E] uses the live unchecked index. */
    s.map_cursor=SEG09A9_EntityState0400PairBase;
    pair_offset=read16(&s,s.data_segment,record_offset(&s,0x0eu),s.flags);
    {
        uint16_t base=s.map_cursor;
        s.map_cursor=(uint16_t)(base+pair_offset);
        s.flags=add_flags(s.flags,base,pair_offset,16u);
    }

    /* Fetch and publish the first pair byte before fetching the second. */
    first=read8(&s,s.data_segment,s.map_cursor,s.flags);
#if ENTITY_STATE400_MUTATION == 1
    delta=read8(&s,s.data_segment,(uint16_t)(s.map_cursor+1u),s.flags);
#endif
    s.value=(uint16_t)((s.value&0xff00u)|first);
    write8(&s,s.data_segment,record_offset(&s,0x28u),first,s.flags);
#if ENTITY_STATE400_MUTATION != 1
    delta=read8(&s,s.data_segment,(uint16_t)(s.map_cursor+1u),s.flags);
#endif
    s.value=(uint16_t)((s.value&0xff00u)|delta);

    /* ADD word [SI+0E],2 is a live memory RMW with entry-phase callbacks. */
    add_record_word(&s,0x0eu,2u);

    /* CBW sign-extends the second pair byte; it does not affect FLAGS. */
#if ENTITY_STATE400_MUTATION == 2
    s.value=(uint16_t)delta;
#else
    s.value=(delta&0x80u)?(uint16_t)(0xff00u|delta):(uint16_t)delta;
#endif

    /* CMP AL,3 / CMP AL,2 / CMP AL,1, in original priority order. */
    s.flags=sub_flags(s.flags,delta,3u,8u);
#if ENTITY_STATE400_MUTATION == 8
    if(delta==2u) {
        return_offset=CS_EntityState0400AfterThreeProbePixelCall;
        sample_count=3u;
    } else
#else
    if(delta==3u) {
        return_offset=CS_EntityState0400AfterThreeProbePixelCall;
        sample_count=3u;
    } else
#endif
    {
        s.flags=sub_flags(s.flags,delta,2u,8u);
#if ENTITY_STATE400_MUTATION == 8
        if(delta==3u) {
            return_offset=CS_EntityState0400AfterTwoProbePixelCall;
            sample_count=2u;
        } else
#else
        if(delta==2u) {
            return_offset=CS_EntityState0400AfterTwoProbePixelCall;
            sample_count=2u;
        } else
#endif
        {
            s.flags=sub_flags(s.flags,delta,1u,8u);
            if(delta==1u) {
                return_offset=CS_EntityState0400AfterOneProbePixelCall;
                sample_count=1u;
            }
        }
    }

    if(sample_count==0u) {
        add_record_word(&s,0x02u,s.value);
        {
            uint16_t y=read16(&s,s.data_segment,
                              record_offset(&s,0x02u),s.flags);
            s.flags=sub_flags(s.flags,y,0x00b4u,16u);
            if(cmp_ge_signed(s.flags,y,0x00b4u)) {
            return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                          pc_binding,sound_binding);
            }
        }
        return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                      pc_binding,sound_binding);
    }

    if(!call_pixel(&s,return_offset))return result_of(&s);
    for(probe=0u;probe<sample_count;++probe) {
        if(sample_pixel(&s)!=0u)
            return collision(&s,pc_binding,sound_binding);
        if(ENTITY_STATE400_MUTATION != 5 || probe+1u!=sample_count)
            inc_record_word(&s,0x02u);
#if ENTITY_STATE400_MUTATION == 5
        if(probe+1u==sample_count)break;
#endif
        if(probe+1u<sample_count)
            add_live_pitch(&s,&pitch_cache,&pitch_cached);
    }

    /* 2B28 CMP [SI+2],00B4 / signed JNL to the inactive finish entry. */
    {
        uint16_t y=read16(&s,s.data_segment,record_offset(&s,0x02u),s.flags);
        s.flags=sub_flags(s.flags,y,0x00b4u,16u);
        if(cmp_ge_signed(s.flags,y,0x00b4u))
            return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                          pc_binding,sound_binding);
    }
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

uint16_t lmn_entity_state400_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState400Call call;
    LmnEntityState400Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state400_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}
