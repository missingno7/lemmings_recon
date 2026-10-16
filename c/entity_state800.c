#include "entity_state800.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE800_MUTATION
#define ENTITY_STATE800_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State800 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State800;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State800 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State800 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State800 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State800 *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Word high bytes follow the physical address, including 20-bit wrap. */
static uint16_t read16(State800 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address);
    uint8_t hi=read_physical(s,address+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State800 *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
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

static uint16_t inc_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    uint16_t out=add_flags(flags,value,1u,bits);
    return (uint16_t)((out&~CF)|old_cf);
}

static uint16_t dec_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    uint16_t out=sub_flags(flags,value,1u,bits);
    return (uint16_t)((out&~CF)|old_cf);
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AF is architecturally undefined for logical operations; choose zero. */
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t mul_flags(uint16_t flags,uint32_t product) {
    /* MUL defines CF/OF. Preserve the chosen values for its undefined flags. */
    return (uint16_t)((flags&~(CF|OF))|
                      ((product>>16)?(CF|OF):0u));
}

static uint16_t shr1_flags(uint16_t flags,uint16_t before) {
    uint16_t value=(uint16_t)(before>>1);
    uint16_t out=szp(value,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t neg8_flags(uint16_t flags,uint8_t value) {
    uint8_t result=(uint8_t)(0u-value);
    uint16_t out=szp(result,8u);
    if(value)out|=CF;
    if(((uint8_t)(value^result)&0x10u)!=0u)out|=AF;
    if(value==0x80u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static int signed_less(uint16_t flags) {
    return (((flags&SF)!=0u)!=((flags&OF)!=0u));
}

#if ENTITY_STATE800_MUTATION != 4
static int signed_ge(uint16_t flags) {
    return !signed_less(flags);
}
#endif

static uint16_t record_offset(const State800 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State800 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement));
}

static uint16_t record_word(State800 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_byte(State800 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void set_record_word(State800 *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void rmw_and_record_byte(State800 *s,uint16_t displacement,
                                uint8_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,8u);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_inc_record_word(State800 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old+1u);
    uint16_t updated=inc_flags(entry,old,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_add_record_word(State800 *s,uint16_t displacement,
                                uint16_t amount) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old+amount);
    uint16_t updated=add_flags(entry,old,amount,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_or_record_word(State800 *s,uint16_t displacement,
                               uint16_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old|mask);
    uint16_t updated=logic_flags(entry,value,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_and_record_word(State800 *s,uint16_t displacement,
                                uint16_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_neg_record_byte(State800 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(0u-old);
    uint16_t updated=neg8_flags(entry,old);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void push_word(State800 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State800 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState800Result result_of(const State800 *s) {
    LmnEntityState800Result out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static uint16_t finish_status(uint16_t status) {
    switch(status) {
    case LMN_ENTITY_FINISH_RETURNED:return LMN_ENTITY_STATE800_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE800_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE800_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE800_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE800_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE800_CHANGED_FINISH_CALL_RETURN;
    default:return LMN_ENTITY_STATE800_INVALID_CHILD;
    }
}

static LmnEntityState800Result finish(State800 *s,uint16_t entry,
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
    s->status=finish_status(out.status);
    return result_of(s);
}

static LmnEntityState800Result finish_interaction(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    return finish(s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

static LmnEntityState800Result mark_inactive(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    return finish(s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                  pc_binding,sound_binding);
}

static LmnEntityState800Result iteration_tail(State800 *s) {
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_STATE800_READY;
    return result_of(s);
}

static uint16_t call_mask(State800 *s,uint16_t return_offset) {
    LmnEntityMaskRowsCall call;
    LmnEntityMaskRowsResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.selection=s->value;call.alignment_index=s->candidate_y;
    call.flags=s->flags;
    out=lmn_draw_thirteen_row_entity_mask_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.mask_word;s->count=out.row_count;
    s->auxiliary_value=out.port;s->record_cursor=out.source_cursor;
    s->object_cursor=out.destination_offset;
    s->candidate_y=out.alignment_index;s->data_segment=out.data_segment;
    s->extra_segment=out.output_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE800_MUTATION == 5
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE800_CHANGED_MASK_RETURN;
        return 0u;
    }
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE800_READY;
    return 1u;
}

static uint16_t call_pixel(State800 *s,uint16_t return_offset) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;call.flags=s->flags;
    out=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.table_cursor;
    s->count=out.column_byte;s->object_cursor=out.destination_offset;
    s->auxiliary_value=out.restored_value;s->extra_segment=0xa000u;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE800_MUTATION == 6
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE800_CHANGED_PIXEL_RETURN;
        return 0u;
    }
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE800_READY;
    return 1u;
}

static uint8_t sample_pixel(State800 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    uint8_t al=(uint8_t)(pixel&(uint8_t)(s->value>>8));
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8u);
    return al;
}

static LmnEntityState800Result zero_pixel_transition(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    rmw_or_record_word(s,0x08u,0x0004u);
    set_record_word(s,0x0au,0x0000u);
    set_record_word(s,0x0cu,0x0a42u);
    set_record_word(s,0x10u,0x005au);
    set_record_word(s,0x12u,0x003cu);
    set_record_byte(s,0x28u,0x00u);
    set_record_byte(s,0x23u,0x03u);
    set_record_word(s,0x04u,0xfff8u);
    set_record_word(s,0x06u,0xfff6u);
    set_record_byte(s,0x29u,0x04u);
    s->value=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots);
    set_record_word(s,0x14u,s->value);
    set_record_byte(s,0x2au,0x00u);
    rmw_and_record_byte(s,0x24u,0x01u);
    rmw_and_record_word(s,0x08u,0xf7ffu);
    return finish_interaction(s,pc_binding,sound_binding);
}

static LmnEntityState800Result negated_transition(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    rmw_neg_record_byte(s,0x27u);
    set_record_word(s,0x08u,0x0000u);
    set_record_word(s,0x0au,0x0000u);
    set_record_word(s,0x0cu,0x0000u);
    set_record_word(s,0x10u,0x005au);
    set_record_word(s,0x12u,0x003cu);
    set_record_byte(s,0x28u,0x00u);
    set_record_word(s,0x04u,0xfff8u);
    set_record_word(s,0x06u,0xfff6u);
    set_record_byte(s,0x29u,0x09u);
    s->value=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots);
    set_record_word(s,0x14u,s->value);
    set_record_byte(s,0x2au,0x00u);
    rmw_and_record_byte(s,0x24u,0x01u);
    return finish_interaction(s,pc_binding,sound_binding);
}

static LmnEntityState800Result call_sound(State800 *s,
    const LmnSoundDriverBinding *sound_binding) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult out;
#if ENTITY_STATE800_MUTATION == 8
    uint16_t entry_ds=s->data_segment;
#endif
    s->value=0x040au;
    call.value=s->value;call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    call.return_offset=CS_EntityState0800AfterSound;
    out=lmn_sound_interrupt61_core(s->memory,&call,sound_binding,s->bus);
    s->value=out.value;s->data_segment=out.data_segment;
    s->code_segment=out.code_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    switch(out.status) {
    case LMN_SOUND_INTERRUPT_RETURNED:
        s->status=LMN_ENTITY_STATE800_READY;
#if ENTITY_STATE800_MUTATION == 8
        s->data_segment=entry_ds;
#endif
        return result_of(s);
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        s->status=LMN_ENTITY_STATE800_UNBOUND_VECTOR;
        return result_of(s);
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        s->status=LMN_ENTITY_STATE800_UNTRANSLATED_CHILD;
        return result_of(s);
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        s->status=LMN_ENTITY_STATE800_CHANGED_INTERRUPT_RETURN;
        return result_of(s);
    default:
        s->status=LMN_ENTITY_STATE800_INVALID_CHILD;
        return result_of(s);
    }
}

static LmnEntityState800Result map_transition(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t product_low;
    uint8_t nibble,al;
    uint32_t product;

    s->value=record_word(s,0x00u); /* MOV AX,[SI]. */
    s->map_cursor=record_word(s,0x02u); /* MOV BX,[SI+2]. */
    {
        uint16_t old=s->map_cursor;
        s->map_cursor=(uint16_t)(old-0x0010u);
        s->flags=sub_flags(s->flags,old,0x0010u,16u);
    }
    {
        uint16_t old=s->value;
        s->value=(uint16_t)(old>>1);s->flags=shr1_flags(s->flags,old);
        old=s->value;
        s->value=(uint16_t)(old>>1);s->flags=shr1_flags(s->flags,old);
    }
    {
        uint16_t old=s->map_cursor;
        s->map_cursor=(uint16_t)(old>>1);s->flags=shr1_flags(s->flags,old);
        old=s->map_cursor;
        s->map_cursor=(uint16_t)(old>>1);s->flags=shr1_flags(s->flags,old);
    }

    /* PUSH AX / PUSH DX and the later POPs use the live SS:SP words. */
    push_word(s,s->value);
    push_word(s,s->auxiliary_value);
    s->value=s->map_cursor; /* MOV AX,BX. */
    s->auxiliary_value=0x01a0u; /* MOV DX,01A0. */
    product=(uint32_t)s->value*s->auxiliary_value;
    product_low=(uint16_t)product;
    s->value=product_low;s->auxiliary_value=(uint16_t)(product>>16);
    s->flags=mul_flags(s->flags,product);
    s->auxiliary_value=pop_word(s); /* POP DX. */
    s->map_cursor=pop_word(s);      /* POP BX. */
    {
        uint16_t old=s->map_cursor;
        s->map_cursor=(uint16_t)(old+s->value);
        s->flags=add_flags(s->flags,old,s->value,16u);
        old=s->map_cursor;
        s->map_cursor=(uint16_t)(old+0x0012u);
        s->flags=add_flags(s->flags,old,0x0012u,16u);
    }
    al=read8(s,s->stack_segment,s->map_cursor);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    al=(uint8_t)(al&0x0fu);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8u); /* AND AL,0F. */
    nibble=al;
    s->flags=sub_flags(s->flags,nibble,0x09u,8u); /* CMP AL,9. */
    if(nibble==0x09u) {
        uint8_t enabled=read8(s,s->data_segment,
                              SEG09A9_ExternalSoundDriverEnabled);
        s->flags=sub_flags(s->flags,enabled,0xffu,8u);
#if ENTITY_STATE800_MUTATION == 7
        if(enabled==0xffu)return negated_transition(s,pc_binding,sound_binding);
#else
        if(enabled!=0xffu)return negated_transition(s,pc_binding,sound_binding);
#endif
        al=read8(s,s->data_segment,SEG09A9_SoundOptionBits);
        s->flags=logic_flags(s->flags,(uint16_t)(al&0x03u),8u);
        if((s->flags&ZF)!=0u)return negated_transition(s,pc_binding,
                                                        sound_binding);
        {
            LmnEntityState800Result out=call_sound(s,sound_binding);
            if(out.status!=LMN_ENTITY_STATE800_READY)return out;
        }
        return negated_transition(s,pc_binding,sound_binding);
    }

    s->flags=sub_flags(s->flags,nibble,0x07u,8u); /* CMP AL,7. */
    if(nibble==0x07u) {
        al=record_byte(s,0x27u); /* MOV AL,[SI+27]. */
        s->value=(uint16_t)((s->value&0xff00u)|al);
        s->flags=logic_flags(s->flags,al,8u); /* AND AL,AL. */
        if((s->flags&SF)==0u)
            return negated_transition(s,pc_binding,sound_binding);
        return finish_interaction(s,pc_binding,sound_binding);
    }

    s->flags=sub_flags(s->flags,nibble,0x08u,8u); /* CMP AL,8. */
    if(nibble==0x08u) {
#if ENTITY_STATE800_MUTATION != 9
        al=record_byte(s,0x27u); /* Fresh MOV AL,[SI+27]. */
        s->value=(uint16_t)((s->value&0xff00u)|al);
        s->flags=logic_flags(s->flags,al,8u); /* AND AL,AL. */
#endif
        /* JNS2CB9 and its fallthrough both reach 2CBB; retain its flags. */
        return negated_transition(s,pc_binding,sound_binding);
    }
    return finish_interaction(s,pc_binding,sound_binding);
}

static LmnEntityState800Result transition_to_neg(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    return negated_transition(s,pc_binding,sound_binding);
}

static uint16_t x_in_bounds(State800 *s) {
    uint16_t x=record_word(s,0x00u);
    s->flags=sub_flags(s->flags,x,0x0010u,16u);
#if ENTITY_STATE800_MUTATION == 4
    if(x<0x0010u)return 0u;
#else
    if(!signed_ge(s->flags))return 0u;
#endif
    x=record_word(s,0x00u);
    s->flags=sub_flags(s->flags,x,0x0680u,16u);
#if ENTITY_STATE800_MUTATION == 4
    return (uint16_t)(x<0x0680u);
#else
    return (uint16_t)signed_less(s->flags);
#endif
}

static uint16_t advance_x_twice(State800 *s) {
    uint8_t al=record_byte(s,0x27u); /* MOV AL,[SI+27]. */
    s->value=(al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al;
    rmw_add_record_word(s,0x00u,s->value); /* ADD [SI],AX. */
    if(!x_in_bounds(s))return 0u;
#if ENTITY_STATE800_MUTATION != 3
    rmw_add_record_word(s,0x00u,s->value);
#endif
    return x_in_bounds(s);
}

static LmnEntityState800Result move_or_probe(State800 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,uint16_t pixel_return) {
    if(!advance_x_twice(s))
        return transition_to_neg(s,pc_binding,sound_binding);
    if(pixel_return==CS_EntityState0800AfterSecondPixelCall) {
        rmw_inc_record_word(s,0x02u);
        {
            uint16_t y=record_word(s,0x02u);
            s->flags=sub_flags(s->flags,y,0x00b4u,16u);
            if(!signed_less(s->flags))
                return mark_inactive(s,pc_binding,sound_binding);
        }
    }
    if(!call_pixel(s,pixel_return))return result_of(s);
    if(sample_pixel(s)!=0u)
        return map_transition(s,pc_binding,sound_binding);
    return zero_pixel_transition(s,pc_binding,sound_binding);
}

LmnEntityState800Result lmn_entity_state800_core(uint8_t *memory,
    const LmnEntityState800Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State800 s;
    uint8_t al;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0800;
    s.status=LMN_ENTITY_STATE800_READY;

    al=record_byte(&s,0x28u); /* MOV AL,[SI+28]. */
    al=(uint8_t)(al+1u);s.flags=inc_flags(s.flags,(uint8_t)(al-1u),8u);
    s.flags=sub_flags(s.flags,al,0x18u,8u); /* CMP AL,18h. */
#if ENTITY_STATE800_MUTATION == 1
    if(al>=0x18u) {
#else
    if(al==0x18u) {
#endif
        al=0u;s.flags=logic_flags(s.flags,0u,8u); /* XOR AL,AL. */
    }
    set_record_byte(&s,0x28u,al); /* MOV [SI+28],AL. */
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=logic_flags(s.flags,al,8u); /* AND AL,AL. */
    if(al==0u) {
        rmw_inc_record_word(&s,0x02u);
        {
            uint16_t y=record_word(&s,0x02u);
            s.flags=sub_flags(s.flags,y,0x00b4u,16u);
            if(signed_less(s.flags))
                return finish_interaction(&s,pc_binding,sound_binding);
        }
        return mark_inactive(&s,pc_binding,sound_binding);
    }

    s.flags=sub_flags(s.flags,al,0x0fu,8u); /* CMP AL,0Fh. */
    if(al==0x0fu)
        return move_or_probe(&s,pc_binding,sound_binding,
                             CS_EntityState0800AfterFirstPixelCall);

    s.flags=sub_flags(s.flags,al,0x03u,8u); /* CMP AL,3. */
    if(al==0x03u)
        return move_or_probe(&s,pc_binding,sound_binding,
                             CS_EntityState0800AfterSecondPixelCall);
#if ENTITY_STATE800_MUTATION == 2
    if(al<0x03u) {
#else
    if(signed_less(s.flags)) {
#endif
        uint8_t selected=(uint8_t)(al-1u);
        s.flags=dec_flags(s.flags,al,8u); /* DEC AL; CF is preserved. */
        s.value=(selected&0x80u)?(uint16_t)(0xff00u|selected):selected;
        if(!call_mask(&s,CS_EntityState0800AfterMaskCall))return result_of(&s);
        return iteration_tail(&s);
    }
    return iteration_tail(&s);
}

uint16_t lmn_entity_state800_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState800Call call;
    LmnEntityState800Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state800_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}
