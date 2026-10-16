#include "entity_state20.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE20_MUTATION
#define ENTITY_STATE20_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State20 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
#if ENTITY_STATE20_MUTATION == 2
    uint16_t cached_pitch;
#endif
} State20;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State20 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State20 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State20 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State20 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Word accesses are low byte first; the high byte is physical+1 with 20-bit
   wrapping, independently of the 16-bit segment offset. */
static uint16_t read16(State20 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address);
    uint8_t hi=read_physical(s,address+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State20 *s,uint16_t segment,uint16_t offset,uint16_t value,
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
    /* AND leaves AF undefined; this declared oracle value chooses zero. */
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
    return (flags&ZF)==0 && (!!(flags&SF)==!!(flags&OF));
}

#if ENTITY_STATE20_MUTATION == 3
static int signed_less_equal(uint16_t flags) {
    return (flags&ZF)!=0 || (!!(flags&SF)!=!!(flags&OF));
}
#endif

static uint16_t record_offset(const State20 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State20 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement));
}

static uint16_t record_word(State20 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_byte(State20 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void set_record_word(State20 *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static uint16_t rmw_add_record_word(State20 *s,uint16_t displacement,
                                    uint16_t amount) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old+amount);
    uint16_t updated=add_flags(entry,old,amount,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
    return value;
}

static uint16_t rmw_sub_record_word(State20 *s,uint16_t displacement,
                                    uint16_t amount) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old-amount);
    uint16_t updated=sub_flags(entry,old,amount,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
    return value;
}

static uint16_t rmw_dec_record_word(State20 *s,uint16_t displacement) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old-1u);
    uint16_t updated=dec_flags(entry,old,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
    return value;
}

static void and_record_word(State20 *s,uint16_t displacement,uint16_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
#if ENTITY_STATE20_MUTATION == 6
    (void)mask;
    uint16_t value=old;
#else
    uint16_t value=(uint16_t)(old&mask);
#endif
    uint16_t updated=logic_flags(entry,value,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void or_record_word(State20 *s,uint16_t displacement,uint16_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old|mask);
    uint16_t updated=logic_flags(entry,value,16u);
    write16(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void and_record_byte(State20 *s,uint16_t displacement,uint8_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,8u);
    write8(s,s->data_segment,offset,value,entry);
    s->flags=updated;
}

static void push_word(State20 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State20 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState20Result result_of(const State20 *s) {
    LmnEntityState20Result out;
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
    case LMN_ENTITY_FINISH_RETURNED: return LMN_ENTITY_STATE20_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE20_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE20_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE20_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE20_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE20_CHANGED_FINISH_CALL_RETURN;
    default: return LMN_ENTITY_STATE20_INVALID_CHILD;
    }
}

static LmnEntityState20Result finish(State20 *s,uint16_t entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=entry;
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
    s->status=map_finish_status(out.status);
    return result_of(s);
}

static void sample_pixel(State20 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    uint8_t al=(uint8_t)(pixel&(uint8_t)(s->value>>8));
#if ENTITY_STATE20_MUTATION == 4
    al=(uint8_t)(al&(uint8_t)s->value);
#endif
    /* MOV AL,[ES:DI] replaces the old low byte before AND AL,AH. */
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8u);
}

static uint16_t cbw_value(uint8_t al) {
#if ENTITY_STATE20_MUTATION == 5
    return al;
#else
    return (al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al;
#endif
}

static LmnEntityState20Result call_pixel(State20 *s,uint16_t return_offset) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;
    call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;
    call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;
    call.flags=s->flags;
    out=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.table_cursor;s->count=out.column_byte;
    s->object_cursor=out.destination_offset;
    s->auxiliary_value=out.restored_value;s->stack_offset=out.stack_offset;
    s->extra_segment=0xa000u;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE20_MUTATION == 8
    (void)actual_return;
#else
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE20_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
#endif
    s->continuation=return_offset;
    s->status=LMN_ENTITY_STATE20_READY;
    return result_of(s);
}

static void increment_row_pitch(State20 *s) {
    unsigned i;
    for(i=0;i<3u;++i) {
        uint16_t old=s->auxiliary_value;
        uint16_t updated=shl16_flags(s->flags,old);
        s->auxiliary_value=(uint16_t)(old<<1);
        s->flags=updated;
    }
}

static void transition_to_state4(State20 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t callback=0;
#if ENTITY_STATE20_MUTATION == 7
    /* Mutation: prefetch the callback before stores that can alias DS:002E. */
    callback=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots);
#endif
    and_record_word(s,0x08u,0xffdfu);
    or_record_word(s,0x08u,0x0004u);
    set_record_word(s,0x0au,0x0000u);
    set_record_word(s,0x0cu,0x0a42u);
    set_record_word(s,0x10u,0x005au);
    set_record_word(s,0x12u,0x003cu);
    set_record_byte(s,0x28u,0x00u);
    set_record_byte(s,0x23u,0x03u);
    set_record_word(s,0x04u,0xfff8u);
    set_record_word(s,0x06u,0xfff6u);
    set_record_byte(s,0x29u,0x04u);
#if ENTITY_STATE20_MUTATION != 7
    callback=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots);
#endif
    set_record_word(s,0x14u,callback);
    set_record_byte(s,0x2au,0x00u);
    and_record_byte(s,0x24u,0x01u);

    {
        uint16_t entry=s->flags;
        uint16_t offset=record_offset(s,0x27u);
        uint8_t old=record_byte(s,0x27u);
        uint8_t value=(uint8_t)(0u-old);
        uint16_t updated=neg8_flags(entry,old);
        write8(s,s->data_segment,offset,value,updated);
        s->flags=updated;
        s->value=cbw_value(value);
    }
    rmw_add_record_word(s,0x00u,s->value);
    rmw_add_record_word(s,0x00u,s->value);
    (void)finish(s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                 pc_binding,sound_binding);
}

static LmnEntityState20Result transition_to_state40(State20 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    and_record_word(s,0x08u,0xffdfu);
    or_record_word(s,0x08u,0x0040u);
    set_record_word(s,0x0au,0x0000u);
    set_record_word(s,0x0cu,0x06b2u);
    set_record_word(s,0x10u,0x0048u);
    set_record_word(s,0x12u,0x0030u);
    set_record_byte(s,0x28u,0x00u);
    set_record_byte(s,0x29u,0x08u);
    and_record_byte(s,0x24u,0x01u);
    s->candidate_y=record_word(s,0x02u);
    return finish(s,LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148,
                  pc_binding,sound_binding);
}

LmnEntityState20Result lmn_entity_state20_core(uint8_t *memory,
    const LmnEntityState20Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State20 s;
    LmnEntityState20Result child;
    uint8_t al;
    uint16_t compare_value;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0020;
    s.status=LMN_ENTITY_STATE20_READY;

    /* 254F..2559: full byte INC, then modulo-eight cadence. */
    al=record_byte(&s,0x28u);
    s.flags=inc_flags(s.flags,al,8u);
    al=(uint8_t)(al+1u);
#if ENTITY_STATE20_MUTATION == 1
    al&=3u;
#else
    al&=7u;
#endif
    s.flags=logic_flags(s.flags,al,8u);
    set_record_byte(&s,0x28u,al);
    s.value=(uint16_t)((s.value&0xff00u)|al); /* INC/AND leave AX's AH live. */
    s.flags=sub_flags(s.flags,al,0x03u,8u); /* CMP AL,03h; signed JG. */

    if(!signed_greater(s.flags)) {
        /* 25E1: temporarily probe Y-7-frame; MOV/XOR preserve AL cadence. */
        s.candidate_y=record_word(&s,0x02u);
        rmw_sub_record_word(&s,0x02u,0x0007u);
        s.value=(uint16_t)(s.value&0x00ffu); /* XOR AH,AH. */
        s.flags=logic_flags(s.flags,0u,8u);
        rmw_sub_record_word(&s,0x02u,s.value);
        child=call_pixel(&s,CS_EntityState0020AfterSecondPixelCall);
        if(child.status!=LMN_ENTITY_STATE20_READY)return child;
        set_record_word(&s,0x02u,s.candidate_y); /* restore Y from BP */
        sample_pixel(&s);
        if(s.value&0x00ffu)
            return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                          pc_binding,sound_binding);

        rmw_add_record_word(&s,0x02u,0x0002u);
        al=record_byte(&s,0x28u);
        s.value=(uint16_t)al; /* MOV AL,[SI+28], then XOR AH,AH. */
        s.flags=logic_flags(s.flags,0u,8u);
        rmw_sub_record_word(&s,0x02u,s.value);
        return transition_to_state40(&s,pc_binding,sound_binding);
    }

    /* 2560..256C: DEC Y; unsigned Y+height <= 10 selects the early change. */
    rmw_dec_record_word(&s,0x02u);
    s.value=record_word(&s,0x02u);
    compare_value=record_word(&s,0x06u);
    s.value=(uint16_t)(s.value+compare_value); /* ADD AX,[SI+6]. */
    s.flags=add_flags(s.flags,(uint16_t)(s.value-compare_value),
                      compare_value,16u);
    s.flags=sub_flags(s.flags,s.value,0x000au,16u); /* CMP AX,0Ah. */
#if ENTITY_STATE20_MUTATION == 3
    if(signed_less_equal(s.flags)) {
#else
    if((s.flags&(CF|ZF))!=0) {
#endif
        transition_to_state4(&s,pc_binding,sound_binding);
        return result_of(&s);
    }

    /* 256E..2576: MOV AL replaces low AX; CBW sign-extends velocity. */
    s.candidate_y=record_word(&s,0x00u); /* MOV BP,[SI]. */
    al=record_byte(&s,0x27u);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.value=cbw_value(al);
    rmw_sub_record_word(&s,0x00u,s.value);
#if ENTITY_STATE20_MUTATION == 2
    s.cached_pitch=read16(&s,s.data_segment,
                          SEG09A9_EntityPixelRowPitchBytes);
#endif
    child=call_pixel(&s,CS_EntityState0020AfterFirstPixelCall);
    if(child.status!=LMN_ENTITY_STATE20_READY)return child;
    set_record_word(&s,0x00u,s.candidate_y); /* MOV [SI],BP. */

#if ENTITY_STATE20_MUTATION == 2
    s.auxiliary_value=s.cached_pitch;
#else
    s.auxiliary_value=read16(&s,s.data_segment,
                             SEG09A9_EntityPixelRowPitchBytes);
#endif
    increment_row_pitch(&s); /* DX <<= 3; three count-one SHLs. */
    {
        uint16_t old=s.object_cursor;
        s.object_cursor=(uint16_t)(old-s.auxiliary_value);
        s.flags=sub_flags(s.flags,old,s.auxiliary_value,16u); /* SUB DI,DX. */
    }
    sample_pixel(&s); /* MOV AL,[ES:DI], AND AL,AH. */
    if((s.value&0x00ffu)!=0) {
        transition_to_state4(&s,pc_binding,sound_binding);
        return result_of(&s);
    }
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

uint16_t lmn_entity_state20_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState20Call call;
    LmnEntityState20Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state20_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}
