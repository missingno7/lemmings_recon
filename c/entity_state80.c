#include "entity_state80.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE80_MUTATION
#define ENTITY_STATE80_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State80 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
#if ENTITY_STATE80_MUTATION == 2
    uint16_t entry_data_segment;
#endif
#if ENTITY_STATE80_MUTATION == 4
    uint16_t cached_pitch;
#endif
} State80;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State80 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State80 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State80 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State80 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* The high byte of a word is physical+1, including at a 20-bit wrap. */
static uint16_t read16(State80 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address);
    uint8_t hi=read_physical(s,address+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State80 *s,uint16_t segment,uint16_t offset,uint16_t value,
                    uint16_t flags) {
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
    uint32_t sum=(uint32_t)left+(uint32_t)right;
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
    uint16_t value=(uint16_t)(((uint32_t)left-(uint32_t)right)&mask);
    uint16_t out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if((left&mask)<(right&mask))out|=CF;
    if((left^right^value)&AF)out|=AF;
    if(((left^right)&(left^value)&sign)!=0)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    return (uint16_t)((add_flags(flags,value,1u,bits)&~CF)|old_cf);
}

static uint16_t dec_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    return (uint16_t)((sub_flags(flags,value,1u,bits)&~CF)|old_cf);
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AND/OR leave AF undefined; the declared oracle value chooses zero. */
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t neg8_flags(uint16_t flags,uint8_t value) {
    uint8_t result=(uint8_t)(0u-value);
    uint16_t out=szp(result,8u);
    if(value)out|=CF;
    if(((uint8_t)(value^result)&0x10u)!=0)out|=AF;
    if(value==0x80u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t shl16_flags(uint16_t flags,uint16_t value) {
    uint16_t result=(uint16_t)(value<<1);
    uint16_t out=szp(result,16u);
    unsigned carry=(value&0x8000u)!=0;
    if(carry)out|=CF;
    if(((result&0x8000u)!=0)!=carry)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static int signed_greater(uint16_t flags) {
    return (flags&ZF)==0u && (!!(flags&SF)==!!(flags&OF));
}

static int signed_less(uint16_t flags) {
    return (!!(flags&SF)!=!!(flags&OF));
}

static int signed_less_equal(uint16_t flags) {
    return (flags&ZF)!=0u || (!!(flags&SF)!=!!(flags&OF));
}

static int signed_greater_equal(uint16_t flags) {
    return (!!(flags&SF)==!!(flags&OF));
}

static int unsigned_above(uint16_t flags) {
    return (flags&(CF|ZF))==0u;
}

static uint16_t record_offset(const State80 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State80 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement));
}

static uint16_t record_word(State80 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_byte(State80 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void set_record_word(State80 *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static uint16_t rmw_add_record_word(State80 *s,uint16_t displacement,
                                    uint16_t amount) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old+amount);
    uint16_t updated=add_flags(entry,old,amount,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
    return value;
}

static uint16_t rmw_dec_record_word(State80 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old-1u);
    uint16_t updated=dec_flags(entry,old,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
    return value;
}

static uint8_t rmw_dec_record_byte(State80 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old-1u);
    uint16_t updated=dec_flags(entry,old,8u);
#if ENTITY_STATE80_MUTATION == 6
    /* Mutation: DEC's result is used, but the memory byte is not written. */
#else
    write8(s,s->data_segment,offset,value,entry);
#endif
    s->flags=updated;
    return value;
}

static void and_record_byte(State80 *s,uint16_t displacement,uint8_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,8u);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void or_record_byte(State80 *s,uint16_t displacement,uint8_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old|mask);
    uint16_t updated=logic_flags(entry,value,8u);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void neg_record_byte(State80 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(0u-old);
    uint16_t updated=neg8_flags(entry,old);
#if ENTITY_STATE80_MUTATION == 7
    /* Mutation: publish NEG flags before the memory RMW write. */
    write8(s,s->data_segment,offset,value,updated);
#else
    write8(s,s->data_segment,offset,value,entry);
#endif
    s->flags=updated;
}

static void push_word(State80 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State80 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState80Result result_of(const State80 *s) {
    LmnEntityState80Result out;
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
    case LMN_ENTITY_FINISH_RETURNED:return LMN_ENTITY_STATE80_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE80_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE80_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE80_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE80_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE80_CHANGED_FINISH_CALL_RETURN;
    default:return LMN_ENTITY_STATE80_INVALID_CHILD;
    }
}

static LmnEntityState80Result finish(State80 *s,uint16_t entry,
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

static void regs_from_state(const State80 *s,LmnRegs *r,uint16_t ip) {
    r->ax=s->value;r->bx=s->map_cursor;r->cx=s->count;
    r->dx=s->auxiliary_value;r->si=s->record_cursor;
    r->di=s->object_cursor;r->bp=s->candidate_y;r->sp=s->stack_offset;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->ip=ip;r->flags=s->flags;
}

static void state_from_regs(State80 *s,const LmnRegs *r) {
    s->value=r->ax;s->map_cursor=r->bx;s->count=r->cx;
    s->auxiliary_value=r->dx;s->record_cursor=r->si;
    s->object_cursor=r->di;s->candidate_y=r->bp;
    s->stack_offset=r->sp;s->code_segment=r->cs;s->data_segment=r->ds;
    s->extra_segment=r->es;s->stack_segment=r->ss;s->flags=r->flags;
    s->continuation=r->ip;
}

static uint16_t map_pc_status(uint16_t status) {
    switch(status) {
    case LMN_PC_INTERRUPT_RETURNED:return LMN_ENTITY_STATE80_READY;
    case LMN_PC_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE80_UNBOUND_VECTOR;
    case LMN_PC_INTERRUPT_UNTRANSLATED_CHILD:
        return LMN_ENTITY_STATE80_UNTRANSLATED_CHILD;
    case LMN_PC_INTERRUPT_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE80_CHANGED_CHILD_RETURN;
    case LMN_PC_INTERRUPT_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE80_CHANGED_INTERRUPT_RETURN;
    default:return LMN_ENTITY_STATE80_INVALID_CHILD;
    }
}

static LmnEntityState80Result call_pc_sound(State80 *s,
    const LmnPcSpeakerBinding *binding) {
    LmnPcSpeakerInterruptCall call;
    LmnPcSpeakerInterruptResult out;
    regs_from_state(s,&call.registers,
        (uint16_t)(CS_EntityState0080AfterPcSound-2u));
    call.return_offset=CS_EntityState0080AfterPcSound;
    out=lmn_pc_speaker_interrupt60_core(s->memory,&call,binding,s->bus);
    state_from_regs(s,&out.registers);
    s->status=map_pc_status(out.status);
    if(out.status==LMN_PC_INTERRUPT_RETURNED)
        s->continuation=CS_EntityState0080AfterPcSound;
    return result_of(s);
}

static uint16_t map_sound_status(uint16_t status) {
    switch(status) {
    case LMN_SOUND_INTERRUPT_RETURNED:return LMN_ENTITY_STATE80_READY;
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE80_UNBOUND_VECTOR;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        return LMN_ENTITY_STATE80_UNTRANSLATED_CHILD;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        return LMN_ENTITY_STATE80_CHANGED_INTERRUPT_RETURN;
    default:return LMN_ENTITY_STATE80_INVALID_CHILD;
    }
}

static LmnEntityState80Result call_external_sound(State80 *s,
    const LmnSoundDriverBinding *binding) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult out;
    call.value=0x0412u;call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    call.return_offset=CS_EntityState0080AfterExternalSound;
    out=lmn_sound_interrupt61_core(s->memory,&call,binding,s->bus);
    s->value=out.value;s->data_segment=out.data_segment;
    s->code_segment=out.code_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_sound_status(out.status);
    if(out.status==LMN_SOUND_INTERRUPT_RETURNED)
        s->continuation=CS_EntityState0080AfterExternalSound;
    return result_of(s);
}

static LmnEntityState80Result call_pixel(State80 *s,uint16_t return_offset) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
#if ENTITY_STATE80_MUTATION == 4
    /* Mutation: sample row pitch before the child can update its live word. */
    s->cached_pitch=read16(s,s->data_segment,
                           SEG09A9_EntityPixelRowPitchBytes);
#endif
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
#if ENTITY_STATE80_MUTATION != 8
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE80_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
#else
    (void)actual_return;
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE80_READY;
    return result_of(s);
}

static uint16_t live_pitch(State80 *s) {
#if ENTITY_STATE80_MUTATION == 4
    return s->cached_pitch;
#else
    return read16(s,s->data_segment,SEG09A9_EntityPixelRowPitchBytes);
#endif
}

static void subtract_live_pitch(State80 *s) {
    uint16_t pitch=live_pitch(s),old=s->object_cursor;
    s->object_cursor=(uint16_t)(old-pitch);
    s->flags=sub_flags(s->flags,old,pitch,16u);
}

static void sample_pixel(State80 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    uint8_t al=(uint8_t)(pixel&(uint8_t)(s->value>>8));
#if ENTITY_STATE80_MUTATION == 5
    al=(uint8_t)(al&(uint8_t)s->value);
#endif
    /* MOV AL,[ES:DI] replaces the old low byte before AND AL,AH. */
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8u);
}

static LmnEntityState80Result call_stroke(State80 *s) {
    LmnEntityStrokeCall call;
    LmnEntityStrokeResult out;
    uint16_t actual_return;
    push_word(s,CS_EntityState0080AfterStrokeCall);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.flags=s->flags;
    out=lmn_draw_entity_stroke_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.mask_word;s->count=out.spill_word;
    s->object_cursor=out.destination_offset;s->extra_segment=out.output_segment;
    s->auxiliary_value=out.port;s->stack_offset=out.stack_offset;
    s->flags=out.flags;
    if(!out.ready_to_return) {
#if ENTITY_STATE80_MUTATION != 8
        s->continuation=out.continuation;
        s->status=LMN_ENTITY_STATE80_CHANGED_STROKE_PIXEL_RETURN;
        return result_of(s);
#endif
    }
    actual_return=pop_word(s);
#if ENTITY_STATE80_MUTATION != 8
    if(actual_return!=CS_EntityState0080AfterStrokeCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE80_CHANGED_STROKE_CALL_RETURN;
        return result_of(s);
    }
#else
    (void)actual_return;
#endif
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_STATE80_READY;
    return result_of(s);
}

static LmnEntityState80Result transition_zero_profile(State80 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
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
    and_record_byte(s,0x24u,0x01u);
    s->candidate_y=record_word(s,0x02u);
    return finish(s,LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148,
                  pc_binding,sound_binding);
}

static LmnEntityState80Result transition_countdown_profile(State80 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    set_record_word(s,0x08u,0x0000u);
    set_record_word(s,0x0au,0x0008u);
    set_record_word(s,0x0cu,0x126bu);
    set_record_word(s,0x10u,0x005au);
    set_record_word(s,0x12u,0x003cu);
    set_record_byte(s,0x28u,0x00u);
    set_record_word(s,0x04u,0xfff8u);
    set_record_word(s,0x06u,0xfff6u);
    set_record_byte(s,0x29u,0x08u);
    s->value=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots);
    set_record_word(s,0x14u,s->value);
    set_record_byte(s,0x2au,0x00u);
    and_record_byte(s,0x24u,0x01u);
    or_record_byte(s,0x24u,0x80u);
    s->candidate_y=record_word(s,0x02u);
    return finish(s,LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148,
                  pc_binding,sound_binding);
}

LmnEntityState80Result lmn_entity_state80_core(uint8_t *memory,
    const LmnEntityState80Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State80 s;
    LmnEntityState80Result child;
    uint8_t al,byte_value;
    uint16_t old,value;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0080;
    s.status=LMN_ENTITY_STATE80_READY;
#if ENTITY_STATE80_MUTATION == 2
    s.entry_data_segment=s.data_segment;
#endif

    /* 2693..26A2: modulo-16 byte cadence; 26A1 remains UNKNOWN. */
    al=record_byte(&s,0x28u);
    s.flags=inc_flags(s.flags,al,8u);
    al=(uint8_t)(al+1u);
#if ENTITY_STATE80_MUTATION == 1
    al&=0x07u;
#else
    al&=0x0fu;
#endif
    s.flags=logic_flags(s.flags,al,8u);
    set_record_byte(&s,0x28u,al);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    if(al==0u)goto upward_probe;

    /* 26A2..26D6: optional PC and external sound with live saved AX/ES. */
    s.flags=sub_flags(s.flags,al,0x0au,8u); /* CMP AL,0A */
    if((s.flags&ZF)==0u)goto select_tail;
    al=record_byte(&s,0x21u);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=sub_flags(s.flags,al,0x03u,8u); /* CMP AL,03 */
    if(unsigned_above(s.flags))goto select_tail;
    push_word(&s,s.value); /* PUSH AX */
    s.stack_offset=(uint16_t)(s.stack_offset-2u);
    write16(&s,s.stack_segment,s.stack_offset,s.extra_segment,s.flags); /* PUSH ES */

    byte_value=read8(&s,s.data_segment,
                     SEG09A9_ExternalSoundDriverEnabled);
    s.flags=sub_flags(s.flags,byte_value,0xffu,8u); /* CMP enabled,FF */
    if((s.flags&ZF)==0u) {
        al=read8(&s,s.data_segment,SEG09A9_SoundOptionBits);
        s.flags=logic_flags(s.flags,(uint16_t)(al&0x01u),8u); /* TEST bit0 */
        if((s.flags&ZF)==0u) {
            s.value=0x0313u; /* MOV AX,0313 */
            child=call_pc_sound(&s,pc_binding);
            if(child.status!=LMN_ENTITY_STATE80_READY)return child;
        }
    }

    {
        uint16_t gate_segment=s.data_segment;
#if ENTITY_STATE80_MUTATION == 2
        gate_segment=s.entry_data_segment;
#endif
        byte_value=read8(&s,gate_segment,
                         SEG09A9_ExternalSoundDriverEnabled);
        s.flags=sub_flags(s.flags,byte_value,0xffu,8u);
        if((s.flags&ZF)!=0u) {
            al=read8(&s,gate_segment,SEG09A9_SoundOptionBits);
#if ENTITY_STATE80_MUTATION == 3
            s.flags=logic_flags(s.flags,(uint16_t)(al&0x01u),8u);
#else
            s.flags=logic_flags(s.flags,(uint16_t)(al&0x03u),8u);
#endif
            if((s.flags&ZF)==0u) {
                s.value=0x0412u; /* MOV AX,0412 */
                child=call_external_sound(&s,sound_binding);
                if(child.status!=LMN_ENTITY_STATE80_READY)return child;
            }
        }
    }

    /* POP ES / POP AX use the returned live SS:SP, after both service gates. */
    s.extra_segment=pop_word(&s);
    s.value=pop_word(&s);

select_tail:
    s.flags=sub_flags(s.flags,(uint8_t)s.value,0x09u,8u); /* CMP AL,09 */
    if((s.value&0x00ffu)!=0x09u)
        return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                      pc_binding,sound_binding);
    child=call_stroke(&s);
    return child;

upward_probe:
    /* 26E4..271C: signed velocity update, bounds, then two clear probes. */
    al=record_byte(&s,0x27u);
    s.value=(al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al; /* CBW */
    rmw_add_record_word(&s,0x00u,s.value); /* ADD [SI],AX */
    rmw_dec_record_word(&s,0x02u); /* DEC word [SI+2]. */
    s.candidate_y=s.value; /* MOV BP,AX; AX remains signed velocity. */

    old=record_word(&s,0x00u);
    s.flags=sub_flags(s.flags,old,0x0010u,16u); /* CMP word [SI],10 */
    if(!signed_greater(s.flags))goto negate_and_transition;
    old=record_word(&s,0x00u);
    s.flags=sub_flags(s.flags,old,0x0680u,16u); /* CMP word [SI],680 */
    if(signed_less(s.flags))goto first_pixel_probe;
    goto negate_and_transition;

first_pixel_probe:
    child=call_pixel(&s,CS_EntityState0080AfterFirstPixelCall);
    if(child.status!=LMN_ENTITY_STATE80_READY)return child;
    subtract_live_pitch(&s); /* SUB DI,[DS:0004], read after child. */
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)goto negate_and_transition;

    rmw_add_record_word(&s,0x00u,s.candidate_y); /* ADD [SI],BP. */
    child=call_pixel(&s,CS_EntityState0080AfterSecondPixelCall);
    if(child.status!=LMN_ENTITY_STATE80_READY)return child;
    subtract_live_pitch(&s);
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)goto negate_and_transition;

    byte_value=rmw_dec_record_byte(&s,0x21u); /* DEC byte [SI+21]. */
    if(byte_value==0u)return transition_countdown_profile(&s,pc_binding,
                                                          sound_binding);

    /* 2726..272F: save X live, move twice, then consume CALL's actual RET. */
    old=record_word(&s,0x00u); /* PUSH word [SI] reads before stack update. */
    push_word(&s,old);
    rmw_add_record_word(&s,0x00u,s.candidate_y);
    rmw_add_record_word(&s,0x00u,s.candidate_y);
    child=call_pixel(&s,CS_EntityState0080AfterThirdPixelCall);
    if(child.status!=LMN_ENTITY_STATE80_READY)return child;
    value=pop_word(&s); /* POP word [SI]; POP does not change FLAGS. */
    set_record_word(&s,0x00u,value);
    push_word(&s,s.value); /* PUSH AX, whose low byte is later replaced. */
    s.value=read16(&s,s.data_segment,SEG09A9_EntityPixelRowPitchBytes);
    old=s.object_cursor;
    s.object_cursor=(uint16_t)(old-s.value); /* SUB DI,AX. */
    s.flags=sub_flags(s.flags,old,s.value,16u);
    {
        unsigned n;
        for(n=0;n<3u;++n) {
            uint16_t before=s.value;
            s.value=(uint16_t)(before<<1);
            s.flags=shl16_flags(s.flags,before);
        }
    }
    old=s.object_cursor;
    s.object_cursor=(uint16_t)(old-s.value); /* SUB DI,AX (pitch*8). */
    s.flags=sub_flags(s.flags,old,s.value,16u);
    s.value=pop_word(&s); /* POP AX restores the third sample mask/result. */
    sample_pixel(&s);
    if((s.value&0x00ffu)!=0u)goto negate_and_transition;

    old=record_word(&s,0x00u);
    s.flags=sub_flags(s.flags,old,0x0010u,16u); /* CMP X,10; JNG. */
    if(signed_less_equal(s.flags))goto negate_and_transition;
    old=record_word(&s,0x00u);
    s.flags=sub_flags(s.flags,old,0x0680u,16u); /* CMP X,680; JNL. */
    if(signed_greater_equal(s.flags))goto negate_and_transition;

    s.value=record_word(&s,0x02u); /* MOV AX,[SI+2]. */
    old=s.value;
    value=record_word(&s,0x06u);
    s.value=(uint16_t)(old+value);
    s.flags=add_flags(s.flags,old,value,16u); /* ADD AX,[SI+6]. */
    s.flags=sub_flags(s.flags,s.value,0x000au,16u); /* CMP AX,0A; JNG. */
    if(signed_less_equal(s.flags))
        return transition_zero_profile(&s,pc_binding,sound_binding);
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);

negate_and_transition:
    neg_record_byte(&s,0x27u); /* Memory NEG: writes with entry FLAGS. */
    return transition_zero_profile(&s,pc_binding,sound_binding);
}

uint16_t lmn_entity_state80_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState80Call call;
    LmnEntityState80Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;call.extra_segment=r->es;
    call.stack_segment=r->ss;call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state80_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;r->es=out.extra_segment;
    r->ss=out.stack_segment;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=out.continuation;
    return out.status;
}
