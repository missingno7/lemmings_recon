#include "entity_state200.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE200_MUTATION
#define ENTITY_STATE200_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,
       ARITH=0x08d5u };

typedef struct State200 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
#if ENTITY_STATE200_MUTATION == 4
    uint16_t cached_pitch;
#endif
} State200;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State200 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State200 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State200 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State200 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Real-mode word accesses are low-byte first; the high byte follows the
   physical address and wraps at 20 bits independently of the segment offset. */
static uint16_t read16(State200 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address);
    uint8_t hi=read_physical(s,address+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State200 *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0,bit;
    uint16_t out=0;
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
    uint32_t sum=(uint32_t)(left&mask)+(uint32_t)(right&mask);
    uint16_t value=(uint16_t)(sum&mask),out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&sign)!=0)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint16_t a=(uint16_t)(left&mask),b=(uint16_t)(right&mask);
    uint16_t value=(uint16_t)((a-b)&mask),out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(a<b)out|=CF;
    if((a^b^value)&AF)out|=AF;
    if(((a^b)&(a^value)&sign)!=0)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    return (uint16_t)((add_flags(flags,value,1u,bits)&~CF)|old_cf);
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AF is undefined for logical operations; this oracle contract chooses 0. */
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t mul_flags(uint16_t flags,uint32_t product) {
    /* MUL defines CF/OF; retain the other architecturally undefined bits. */
    return (uint16_t)((flags&~(CF|OF))|
                      ((product>>16)?(CF|OF):0u));
}

static uint16_t shr16_flags(uint16_t flags,uint16_t before) {
    uint16_t value=(uint16_t)(before>>1);
    uint16_t out=szp(value,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    /* SHR leaves AF undefined; the selected contract value is zero. */
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t neg8_flags(uint16_t flags,uint8_t value) {
    uint8_t result=(uint8_t)(0u-value);
    uint16_t out=szp(result,8u);
    if(value)out|=CF;
    if(((uint8_t)(value^result)&0x10u)!=0)out|=AF;
    if(value==0x80u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static int signed_less(uint16_t flags) {
    return ((flags&SF)!=0)!=((flags&OF)!=0);
}

static int signed_le(uint16_t flags) {
    return (flags&ZF)!=0 || signed_less(flags);
}

static uint16_t record_offset(const State200 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State200 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement));
}

static uint16_t record_word(State200 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_byte(State200 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void set_record_word(State200 *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static uint8_t rmw_inc_record_byte(State200 *s,uint16_t displacement) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old+1u);
    uint16_t updated=inc_flags(entry,old,8u);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
    return value;
}

static void rmw_and_record_byte(State200 *s,uint16_t displacement,
                                uint8_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,8u);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_inc_record_word(State200 *s,uint16_t displacement) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old+1u);
    uint16_t updated=inc_flags(entry,old,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_add_record_word(State200 *s,uint16_t displacement,
                                uint16_t amount) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old+amount);
    uint16_t updated=add_flags(entry,old,amount,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_or_record_word(State200 *s,uint16_t displacement,
                               uint16_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old|mask);
    uint16_t updated=logic_flags(entry,value,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_and_record_word(State200 *s,uint16_t displacement,
                                uint16_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void rmw_neg_record_byte(State200 *s,uint16_t displacement) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(0u-old);
    uint16_t updated=neg8_flags(entry,old);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void push_word(State200 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State200 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState200Result result_of(const State200 *s) {
    LmnEntityState200Result out;
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
    case LMN_ENTITY_FINISH_RETURNED: return LMN_ENTITY_STATE200_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE200_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE200_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE200_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE200_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE200_CHANGED_FINISH_CALL_RETURN;
    default: return LMN_ENTITY_STATE200_INVALID_CHILD;
    }
}

static LmnEntityState200Result finish_interaction(State200 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
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

static LmnEntityState200Result iteration_tail(State200 *s) {
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_STATE200_READY;
    return result_of(s);
}

static LmnEntityState200Result call_mask_rows(State200 *s,
    uint16_t return_offset) {
    LmnEntityMaskRowsCall call;
    LmnEntityMaskRowsResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.selection=s->value;call.alignment_index=s->candidate_y;
    call.flags=s->flags;
    out=lmn_draw_ten_row_entity_mask_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.mask_word;s->count=out.row_count;
    s->auxiliary_value=out.port;s->record_cursor=out.source_cursor;
    s->object_cursor=out.destination_offset;s->candidate_y=out.alignment_index;
    s->data_segment=out.data_segment;s->extra_segment=out.output_segment;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE200_MUTATION == 5
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE200_CHANGED_MASK_RETURN;
        return result_of(s);
    }
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE200_READY;
    return result_of(s);
}

static LmnEntityState200Result call_coordinate(State200 *s,
    uint16_t return_offset) {
    LmnCoordinatePixelCall call;
    LmnCoordinatePixelResult out;
    uint16_t actual_return;
#if ENTITY_STATE200_MUTATION == 3
    uint16_t input_bx=s->map_cursor,input_cx=s->count,input_dx=s->auxiliary_value;
#endif
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.column_value=s->count;
    call.row_value=s->map_cursor;call.saved_value=s->auxiliary_value;
    call.flags=s->flags;
    out=lmn_prepare_coordinate_pixel_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.row_value;s->count=out.column_value;
    s->auxiliary_value=out.restored_value;
    s->object_cursor=out.destination_offset;s->extra_segment=out.output_segment;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
#if ENTITY_STATE200_MUTATION == 3
    s->map_cursor=input_bx;s->count=input_cx;s->auxiliary_value=input_dx;
#endif
    actual_return=pop_word(s);
#if ENTITY_STATE200_MUTATION == 6
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE200_CHANGED_COORDINATE_RETURN;
        return result_of(s);
    }
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE200_READY;
    return result_of(s);
}

static LmnEntityState200Result call_pixel(State200 *s,
    uint16_t return_offset) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;call.flags=s->flags;
    out=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.table_cursor;s->count=out.column_byte;
    s->object_cursor=out.destination_offset;
    s->auxiliary_value=out.restored_value;s->extra_segment=0xa000u;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE200_MUTATION == 7
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE200_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE200_READY;
    return result_of(s);
}

static void sample_pixel(State200 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    uint8_t al=(uint8_t)(pixel&(uint8_t)(s->value>>8));
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8u);
}

static void add_live_pitch(State200 *s) {
    uint16_t old_di=s->object_cursor;
    uint16_t pitch=read16(s,s->data_segment,SEG09A9_EntityPixelRowPitchBytes);
    s->object_cursor=(uint16_t)(old_di+pitch);
    s->flags=add_flags(s->flags,old_di,pitch,16u);
}

static void zero_state_transition(State200 *s) {
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
    (void)iteration_tail(s);
}

static void negated_transition(State200 *s,
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
    (void)finish_interaction(s,pc_binding,sound_binding);
}

static void zero_pixel_transition(State200 *s,
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
    rmw_and_record_word(s,0x08u,0xfdffu);
    (void)finish_interaction(s,pc_binding,sound_binding);
}

static void movement_transition(State200 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t al=record_byte(s,0x27u);
    s->value=(al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al;
    rmw_add_record_word(s,0x00u,s->value); /* ADD [SI],AX. */
    s->flags=sub_flags(s->flags,record_word(s,0x00u),0x0010u,16u);
    if(signed_less(s->flags)) {
        negated_transition(s,pc_binding,sound_binding);
        return;
    }
    s->flags=sub_flags(s->flags,record_word(s,0x00u),0x0680u,16u);
    if(!signed_less(s->flags)) {
        negated_transition(s,pc_binding,sound_binding);
        return;
    }

#if ENTITY_STATE200_MUTATION == 4
    s->cached_pitch=read16(s,s->data_segment,
                            SEG09A9_EntityPixelRowPitchBytes);
#endif
    {
        LmnEntityState200Result child=call_pixel(s,
                                      CS_EntityState0200AfterPixelCall);
        if(child.status!=LMN_ENTITY_STATE200_READY)return;
    }
    sample_pixel(s);
    if((s->value&0x00ffu)!=0u)goto map_transition;

    rmw_inc_record_word(s,0x02u);
#if ENTITY_STATE200_MUTATION == 4
    {
        uint16_t old_di=s->object_cursor;
        s->object_cursor=(uint16_t)(old_di+s->cached_pitch);
        s->flags=add_flags(s->flags,old_di,s->cached_pitch,16u);
    }
#else
    add_live_pitch(s);
#endif
    sample_pixel(s);
    if((s->value&0x00ffu)!=0u)goto map_transition;

    rmw_inc_record_word(s,0x02u);
    add_live_pitch(s);
    sample_pixel(s);
    if((s->value&0x00ffu)!=0u)goto map_transition;

    rmw_inc_record_word(s,0x02u);
    zero_pixel_transition(s,pc_binding,sound_binding);
    return;

map_transition:
    /* The SS map lookup is intentionally deferred until after the pixel
       decision and its live AX/DX save/restore sequence. */
    {
        uint16_t old_ax,old_dx,product;
        uint8_t nibble;
        uint32_t wide_product;

        s->value=record_word(s,0x00u); /* MOV AX,[SI]. */
        s->map_cursor=record_word(s,0x02u); /* MOV BX,[SI+2]. */
        {
            uint16_t old=s->map_cursor;
            s->map_cursor=(uint16_t)(old-0x0010u);
            s->flags=sub_flags(s->flags,old,0x0010u,16u);
        }
        old_ax=s->value;
        s->value=(uint16_t)(old_ax>>1);
        s->flags=shr16_flags(s->flags,old_ax);
        old_ax=s->value;
        s->value=(uint16_t)(old_ax>>1);
        s->flags=shr16_flags(s->flags,old_ax);
        old_dx=s->map_cursor;
        s->map_cursor=(uint16_t)(old_dx>>1);
        s->flags=shr16_flags(s->flags,old_dx);
        old_dx=s->map_cursor;
        s->map_cursor=(uint16_t)(old_dx>>1);
        s->flags=shr16_flags(s->flags,old_dx);

        push_word(s,s->value); /* PUSH AX, then PUSH DX. */
        push_word(s,s->auxiliary_value);
        s->value=s->map_cursor; /* MOV AX,BX. */
        s->auxiliary_value=0x01a0u; /* MOV DX,01A0. */
        wide_product=(uint32_t)s->value*s->auxiliary_value;
        product=(uint16_t)wide_product;
        s->value=product;s->auxiliary_value=(uint16_t)(wide_product>>16);
        s->flags=mul_flags(s->flags,wide_product);
        s->auxiliary_value=pop_word(s); /* POP DX uses actual SS:SP. */
        s->map_cursor=pop_word(s);      /* POP BX uses actual SS:SP. */
        {
            uint16_t old=s->map_cursor;
            s->map_cursor=(uint16_t)(old+s->value);
            s->flags=add_flags(s->flags,old,s->value,16u);
            old=s->map_cursor;
            s->map_cursor=(uint16_t)(old+0x0012u);
            s->flags=add_flags(s->flags,old,0x0012u,16u);
            old=s->map_cursor;
            s->map_cursor=(uint16_t)(old-0x0340u);
            s->flags=sub_flags(s->flags,old,0x0340u,16u);
        }
        al=record_byte(s,0x27u);
        s->value=(al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al;
        {
            uint16_t old=s->map_cursor;
            s->map_cursor=(uint16_t)(old+s->value);
            s->flags=add_flags(s->flags,old,s->value,16u);
            old=s->map_cursor;
            s->map_cursor=(uint16_t)(old+s->value);
            s->flags=add_flags(s->flags,old,s->value,16u);
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
#if ENTITY_STATE200_MUTATION == 8
            if(enabled==0xffu)goto sound_gate_skip;
#else
            if(enabled!=0xffu)goto sound_gate_skip;
#endif
            al=read8(s,s->data_segment,SEG09A9_SoundOptionBits);
            s->flags=logic_flags(s->flags,(uint16_t)(al&0x03u),8u);
            if((s->flags&ZF)==0u) {
                LmnSoundInterruptCall call;
                LmnSoundInterruptResult out;
#if ENTITY_STATE200_MUTATION == 9
                uint16_t entry_ds=s->data_segment;
#endif
                s->value=0x040au;
                call.value=s->value;call.data_segment=s->data_segment;
                call.code_segment=s->code_segment;
                call.stack_segment=s->stack_segment;
                call.stack_offset=s->stack_offset;call.flags=s->flags;
                call.return_offset=CS_EntityState0200AfterSound;
                out=lmn_sound_interrupt61_core(s->memory,&call,
                                                sound_binding,s->bus);
                s->value=out.value;s->data_segment=out.data_segment;
                s->code_segment=out.code_segment;
                s->stack_offset=out.stack_offset;s->flags=out.flags;
                s->continuation=out.continuation;
                switch(out.status) {
                case LMN_SOUND_INTERRUPT_RETURNED:
                    s->status=LMN_ENTITY_STATE200_READY;
#if ENTITY_STATE200_MUTATION == 9
                    s->data_segment=entry_ds;
#endif
                    break;
                case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
                    s->status=LMN_ENTITY_STATE200_UNBOUND_VECTOR;
                    return;
                case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
                    s->status=LMN_ENTITY_STATE200_UNTRANSLATED_CHILD;
                    return;
                case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
                    s->status=LMN_ENTITY_STATE200_CHANGED_INTERRUPT_RETURN;
                    return;
                default:
                    s->status=LMN_ENTITY_STATE200_INVALID_CHILD;
                    return;
                }
            }
sound_gate_skip:
            negated_transition(s,pc_binding,sound_binding);
            return;
        }

        s->flags=sub_flags(s->flags,nibble,0x07u,8u); /* CMP AL,7. */
        if(nibble==0x07u) {
            al=record_byte(s,0x27u); /* Fresh MOV AL,[SI+27]. */
            s->value=(uint16_t)((s->value&0xff00u)|al);
            s->flags=logic_flags(s->flags,al,8u); /* AND AL,AL. */
            if((al&0x80u)==0u)negated_transition(s,pc_binding,sound_binding);
            else (void)finish_interaction(s,pc_binding,sound_binding);
            return;
        }
        s->flags=sub_flags(s->flags,nibble,0x08u,8u); /* CMP AL,8. */
        if(nibble==0x08u) {
            al=record_byte(s,0x27u); /* Fresh MOV AL,[SI+27]. */
            s->value=(uint16_t)((s->value&0xff00u)|al);
            s->flags=logic_flags(s->flags,al,8u); /* AND AL,AL. */
            if((al&0x80u)==0u)
                (void)finish_interaction(s,pc_binding,sound_binding);
            else
                negated_transition(s,pc_binding,sound_binding);
            return;
        }
        (void)finish_interaction(s,pc_binding,sound_binding);
    }
}

LmnEntityState200Result lmn_entity_state200_core(uint8_t *memory,
    const LmnEntityState200Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State200 s;
    LmnEntityState200Result child;
    uint8_t al;
#if ENTITY_STATE200_MUTATION == 2
    uint8_t pre_mask_raw;
#endif

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0200;
    s.status=LMN_ENTITY_STATE200_READY;

    /* 287D/2880 are separate memory RMWs. The AND rereads the live byte. */
    al=rmw_inc_record_byte(&s,0x28u);
#if ENTITY_STATE200_MUTATION == 1
    {
        uint16_t entry=s.flags;
        uint8_t value=(uint8_t)(al&0x1fu);
        uint16_t updated=logic_flags(entry,value,8u);
        write8(&s,s.data_segment,record_offset(&s,0x28u),value,entry);
        s.flags=updated;
    }
#else
    rmw_and_record_byte(&s,0x28u,0x1fu);
#endif
    al=record_byte(&s,0x28u); /* MOV AL,[SI+28]. */
#if ENTITY_STATE200_MUTATION == 2
    pre_mask_raw=al;
#endif
    s.value=(uint16_t)((s.value&0xff00u)|al);
    al=(uint8_t)(al&0x0fu);   /* AND AL,0F; AH remains live. */
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=logic_flags(s.flags,al,8u);

    s.flags=sub_flags(s.flags,al,0x0bu,8u); /* CMP AL,0B; signed JL. */
    if(!signed_less(s.flags))goto movement;
    s.flags=sub_flags(s.flags,al,0x02u,8u); /* CMP AL,2; signed JNL. */
    if(signed_less(s.flags))return iteration_tail(&s);
    s.flags=sub_flags(s.flags,al,0x05u,8u); /* CMP AL,5; signed JNG. */
    if(!signed_le(s.flags))return iteration_tail(&s);

    {
        uint8_t old_al=(uint8_t)s.value;
        uint8_t result=(uint8_t)(old_al-2u);
        s.value=(uint16_t)((s.value&0xff00u)|result);
        s.flags=sub_flags(s.flags,old_al,0x02u,8u); /* SUB AL,2. */
        s.value=(result&0x80u)?(uint16_t)(0xff00u|result):(uint16_t)result;
    }
#if ENTITY_STATE200_MUTATION == 2
    /* Mutation: reuse the pre-CALL raw cadence instead of rereading the live
       record through the mask child's returned DS:SI. */
    child=call_mask_rows(&s,CS_EntityState0200AfterMaskCall);
    if(child.status!=LMN_ENTITY_STATE200_READY)return child;
    al=pre_mask_raw;
#else
    child=call_mask_rows(&s,CS_EntityState0200AfterMaskCall);
    if(child.status!=LMN_ENTITY_STATE200_READY)return child;
    al=record_byte(&s,0x28u); /* Reread returned DS:SI+28 raw, before mask. */
#endif
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=sub_flags(s.flags,al,0x05u,8u); /* CMP AL,5. */
    if((s.flags&ZF)==0u)return iteration_tail(&s);

    s.count=record_word(&s,0x00u); /* MOV CX,[SI]. */
    s.map_cursor=record_word(&s,0x02u); /* MOV BX,[SI+2]. */
    {
        uint16_t old=s.map_cursor;
        s.map_cursor=(uint16_t)(old-0x0006u);
        s.flags=sub_flags(s.flags,old,0x0006u,16u);
    }
    al=record_byte(&s,0x27u);
    s.value=(al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al;
    s.candidate_y=s.value; /* MOV BP,AX. */
    {
        unsigned n;
        for(n=0;n<3u;++n) {
            uint16_t old=s.value;
            s.value=(uint16_t)(old+old);
            s.flags=add_flags(s.flags,old,old,16u);
        }
    }
    {
        uint16_t old=s.count;
        s.count=(uint16_t)(old+s.value);
        s.flags=add_flags(s.flags,old,s.value,16u);
    }
    child=call_coordinate(&s,CS_EntityState0200AfterFirstCoordinateCall);
    if(child.status!=LMN_ENTITY_STATE200_READY)return child;
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)return iteration_tail(&s);

    {
        uint16_t old=s.count;
        s.count=(uint16_t)(old+s.candidate_y);
        s.flags=add_flags(s.flags,old,s.candidate_y,16u);
    }
    child=call_coordinate(&s,CS_EntityState0200AfterSecondCoordinateCall);
    if(child.status!=LMN_ENTITY_STATE200_READY)return child;
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)return iteration_tail(&s);

    {
        uint16_t old=s.count;
        s.count=(uint16_t)(old+s.candidate_y);
        s.flags=add_flags(s.flags,old,s.candidate_y,16u);
    }
    child=call_coordinate(&s,CS_EntityState0200AfterThirdCoordinateCall);
    if(child.status!=LMN_ENTITY_STATE200_READY)return child;
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)return iteration_tail(&s);

    {
        uint16_t old=s.count;
        s.count=(uint16_t)(old+s.candidate_y);
        s.flags=add_flags(s.flags,old,s.candidate_y,16u);
    }
    child=call_coordinate(&s,CS_EntityState0200AfterFourthCoordinateCall);
    if(child.status!=LMN_ENTITY_STATE200_READY)return child;
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)return iteration_tail(&s);
    zero_state_transition(&s);
    return result_of(&s);

movement:
    movement_transition(&s,pc_binding,sound_binding);
    return result_of(&s);
}

uint16_t lmn_entity_state200_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState200Call call;
    LmnEntityState200Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state200_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}
