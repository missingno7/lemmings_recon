#include "entity_state4.h"
#include "sound_interrupt.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE4_MUTATION
#define ENTITY_STATE4_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State4 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State4;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State4 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State4 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State4 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State4 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* The high byte follows the physical low byte, including at offset/20-bit
   wrap boundaries. */
static uint16_t read16(State4 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address);
    uint8_t hi=read_physical(s,address+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State4 *s,uint16_t segment,uint16_t offset,uint16_t value,
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
    /* AF is architecturally defined by ADD. */
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

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AF is undefined after AND; this oracle chooses zero. */
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

#if ENTITY_STATE4_MUTATION != 4
static int signed_lt(uint16_t flags) {
    return (!!(flags&SF)!=!!(flags&OF));
}

static int signed_ge(uint16_t flags) {
    return (!!(flags&SF)==!!(flags&OF));
}
#endif

static uint16_t record_offset(const State4 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State4 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_byte(State4 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static uint16_t record_word(State4 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_word(State4 *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void add_record_byte(State4 *s,uint16_t displacement,uint8_t amount) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old+amount);
    uint16_t updated=add_flags(entry,old,amount,8);
    uint16_t write_flags=entry;
#if ENTITY_STATE4_MUTATION == 7
    write_flags=updated;
#endif
    write8(s,s->data_segment,offset,value,write_flags);
    s->flags=updated;
}

static void and_record_byte(State4 *s,uint16_t displacement,uint8_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old&mask);
    uint16_t updated=logic_flags(entry,value,8);
    uint16_t write_flags=entry;
#if ENTITY_STATE4_MUTATION == 7
    write_flags=updated;
#endif
    write8(s,s->data_segment,offset,value,write_flags);
    s->flags=updated;
}

static void push_word(State4 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State4 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState4Result result_of(const State4 *s) {
    LmnEntityState4Result out;
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
    case LMN_ENTITY_FINISH_RETURNED: return LMN_ENTITY_STATE4_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE4_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE4_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE4_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE4_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE4_CHANGED_FINISH_CALL_RETURN;
    default: return LMN_ENTITY_STATE4_INVALID_CHILD;
    }
}

static LmnEntityState4Result finish(State4 *s,uint16_t entry,
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

static void sample_pixel(State4 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    uint8_t al=(uint8_t)(pixel&(uint8_t)(s->value>>8));
    /* MOV AL,[ES:DI] overwrites old AL before AND AL,AH. */
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8);
}

static void add_live_row_pitch(State4 *s) {
    uint16_t entry=s->flags;
    uint16_t pitch=read16(s,s->data_segment,
                          SEG09A9_EntityPixelRowPitchBytes);
    uint16_t old=s->object_cursor;
    s->object_cursor=(uint16_t)(old+pitch);
    s->flags=add_flags(entry,old,pitch,16);
}

static void inc_candidate_y(State4 *s) {
    s->flags=inc_flags(s->flags,s->candidate_y,16);
    s->candidate_y=(uint16_t)(s->candidate_y+1u);
}

static LmnEntityState4Result call_pixel(State4 *s) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    push_word(s,CS_EntityState0004AfterPixelCall);
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
#if ENTITY_STATE4_MUTATION == 8
    (void)actual_return;
#else
    if(actual_return!=CS_EntityState0004AfterPixelCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE4_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
#endif
    s->continuation=CS_EntityState0004AfterPixelCall;
    s->status=LMN_ENTITY_STATE4_READY;
    return result_of(s);
}

static LmnEntityState4Result run_sound(State4 *s,
    const LmnSoundDriverBinding *sound_binding) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult out;
    call.value=0x0408u;call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    call.return_offset=CS_EntityState0004AfterSound;
    out=lmn_sound_interrupt61_core(s->memory,&call,sound_binding,s->bus);
    s->value=out.value;s->data_segment=out.data_segment;
    s->code_segment=out.code_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    switch(out.status) {
    case LMN_SOUND_INTERRUPT_RETURNED:
        s->continuation=CS_EntityState0004AfterSound;
        s->status=LMN_ENTITY_STATE4_READY;
        break;
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        s->status=LMN_ENTITY_STATE4_UNBOUND_VECTOR;
        break;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        s->status=LMN_ENTITY_STATE4_UNTRANSLATED_CHILD;
        break;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        s->status=LMN_ENTITY_STATE4_CHANGED_INTERRUPT_RETURN;
        break;
    default:
        s->status=LMN_ENTITY_STATE4_INVALID_CHILD;
        break;
    }
    return result_of(s);
}

LmnEntityState4Result lmn_entity_state4_core(uint8_t *memory,
    const LmnEntityState4Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State4 s;
    LmnEntityState4Result child;
    uint8_t al,field;
    uint16_t comparison;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0004;
    s.status=LMN_ENTITY_STATE4_READY;

    /* 21B0..21B7: byte cadence wraps, then is masked to two low bits. */
    al=record_byte(&s,0x28u);
    s.flags=inc_flags(s.flags,al,8);
    al=(uint8_t)(al+1u);
#if ENTITY_STATE4_MUTATION == 1
    al&=7u;
#else
    al&=3u;
#endif
    s.flags=logic_flags(s.flags,al,8);
    set_record_byte(&s,0x28u,al);

    /* Unsigned byte branches select the transition or first pixel call. */
    field=record_byte(&s,0x23u);
#if ENTITY_STATE4_MUTATION == 2
    comparison=sub_flags(s.flags,field,0x11u,8);
#else
    comparison=sub_flags(s.flags,field,0x10u,8);
#endif
    s.flags=comparison;
    if((s.flags&(CF|ZF))!=0)goto pixel_call;
    field=record_byte(&s,0x25u);
    s.flags=sub_flags(s.flags,field,0u,8);
#if ENTITY_STATE4_MUTATION == 3
    if((s.flags&ZF)==0)goto pixel_call;
#else
    if(s.flags&ZF)goto pixel_call;
#endif

    /* 21C6 transition stores are reached by the nonzero +25 fallthrough. */
    set_record_word(&s,0x08u,0x0400u);
    set_record_word(&s,0x0au,0x0000u);
    set_record_word(&s,0x0cu,0x0baau);
    set_record_word(&s,0x10u,0x0080u);
    set_record_word(&s,0x12u,0x0060u);
    set_record_byte(&s,0x28u,0x00u);
    set_record_word(&s,0x0eu,0x0000u);
    set_record_word(&s,0x06u,0xfff0u);
    set_record_byte(&s,0x29u,0x08u);
#if ENTITY_STATE4_MUTATION == 6
    s.value=read16(&s,s.data_segment,
                   (uint16_t)(SEG09A9_DrawingCallbackSlots+0u));
#else
    s.value=read16(&s,s.data_segment,
                   (uint16_t)(SEG09A9_DrawingCallbackSlots+0x0cu));
#endif
    set_record_word(&s,0x14u,s.value);
    set_record_byte(&s,0x2au,0xffu);
    and_record_byte(&s,0x24u,0x01u);
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);

pixel_call:
    child=call_pixel(&s);
    if(child.status!=LMN_ENTITY_STATE4_READY)return child;

    /* CALL returns at 2205. BP is then reloaded from the live record and the
       VGA byte replaces AL before the AND with AH. */
    s.candidate_y=record_word(&s,0x02u);
    sample_pixel(&s);
    if(s.value&0x00ffu)goto occupied_224d;

    inc_candidate_y(&s);
    comparison=sub_flags(s.flags,s.candidate_y,0x00b4u,16);
    s.flags=comparison;
#if ENTITY_STATE4_MUTATION == 4
    if(s.candidate_y<0x00b4u)goto probe_second;
#else
    if(signed_lt(s.flags))goto probe_second;
#endif
    return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                  pc_binding,sound_binding);

probe_second:
    add_live_row_pitch(&s);
    sample_pixel(&s);
    if(s.value&0x00ffu)goto occupied_224d;

    inc_candidate_y(&s);
    comparison=sub_flags(s.flags,s.candidate_y,0x00b4u,16);
    s.flags=comparison;
#if ENTITY_STATE4_MUTATION == 4
    if(s.candidate_y<0x00b4u)goto probe_third;
#else
    if(signed_lt(s.flags))goto probe_third;
#endif
    return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                  pc_binding,sound_binding);

probe_third:
    add_live_row_pitch(&s);
    sample_pixel(&s);
    if(s.value&0x00ffu)goto occupied_224d;

    inc_candidate_y(&s); /* 2239 INC BP precedes ADD byte [SI+23],3. */
#if ENTITY_STATE4_MUTATION == 5
    add_record_byte(&s,0x23u,0x02u);
#else
    add_record_byte(&s,0x23u,0x03u);
#endif
    set_record_word(&s,0x02u,s.candidate_y);
    comparison=sub_flags(s.flags,s.candidate_y,0x00b4u,16);
    s.flags=comparison;
#if ENTITY_STATE4_MUTATION == 4
    if(s.candidate_y>=0x00b4u)
#else
    if(signed_ge(s.flags))
#endif
        return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                      pc_binding,sound_binding);
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);

occupied_224d:
    set_record_word(&s,0x02u,s.candidate_y);
    field=record_byte(&s,0x23u);
    comparison=sub_flags(s.flags,field,0x3cu,8);
    s.flags=comparison;
    if((s.flags&(CF|ZF))!=0)goto stable_22a3;

    set_record_word(&s,0x08u,0x0001u);
    set_record_word(&s,0x0au,0x0000u);
    set_record_word(&s,0x0cu,0x0c2au);
    set_record_word(&s,0x10u,0x005au);
    set_record_word(&s,0x12u,0x003cu);
    set_record_byte(&s,0x28u,0x00u);
    set_record_byte(&s,0x27u,0x00u);
    set_record_byte(&s,0x20u,0x00u);
    set_record_byte(&s,0x29u,0x00u);
    s.value=read16(&s,s.data_segment,
                   (uint16_t)(SEG09A9_DrawingCallbackSlots+0u));
    set_record_word(&s,0x14u,s.value);
    set_record_byte(&s,0x2au,0x00u);
    and_record_byte(&s,0x24u,0x01u);

    field=read8(&s,s.data_segment,SEG09A9_ExternalSoundDriverEnabled);
    s.flags=sub_flags(s.flags,field,0xffu,8);
    if(s.flags&ZF)goto play_sound_gate;
    goto finish_transition_1fe8;

play_sound_gate:
    field=read8(&s,s.data_segment,SEG09A9_SoundOptionBits);
    al=(uint8_t)(field&0x03u);
    s.flags=logic_flags(s.flags,al,8); /* TEST byte [25A7],03h */
    if((s.flags&ZF)==0) {
        child=run_sound(&s,sound_binding);
        if(child.status!=LMN_ENTITY_STATE4_READY)return child;
    }
    goto finish_transition_1fe8;

stable_22a3:
    set_record_word(&s,0x08u,0x0000u);
    set_record_word(&s,0x0au,0x0000u);
    set_record_word(&s,0x0cu,0x0000u);
    set_record_word(&s,0x10u,0x005au);
    set_record_word(&s,0x12u,0x003cu);
    set_record_byte(&s,0x28u,0x00u);
    set_record_word(&s,0x04u,0xfff8u);
    set_record_word(&s,0x06u,0xfff6u);
    set_record_byte(&s,0x29u,0x09u);
    s.value=read16(&s,s.data_segment,
                   (uint16_t)(SEG09A9_DrawingCallbackSlots+0u));
    set_record_word(&s,0x14u,s.value);
    set_record_byte(&s,0x2au,0x00u);
    and_record_byte(&s,0x24u,0x01u);

finish_transition_1fe8:
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

uint16_t lmn_entity_state4_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState4Call call;
    LmnEntityState4Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state4_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}
